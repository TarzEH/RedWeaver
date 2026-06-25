"""Celery task that runs a hunt (crew.kickoff) out-of-process.

Port of the legacy HuntExecutionService.execute, with state writes going to
Postgres (via the observability sink) and live events to Channels. Runs
synchronously inside the Celery worker (no asyncio / thread pool).
"""
from __future__ import annotations

import logging

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db.models import Q
from django.utils import timezone

from apps.accounts.keys import keys_provider_for_user
from apps.common.redaction import scrub_secrets

from .costs import estimate_cost_usd
from .models import Run, RunStatus
from .observability_sink import make_event_callback

# Register the OffSec task with Celery (autodiscover only imports tasks.py).
from .offsec_tasks import generate_offsec_playbook  # noqa: E402,F401

logger = logging.getLogger(__name__)


@shared_task
def run_due_schedules() -> None:
    """Celery-beat tick: enqueue any recurring scans whose interval has elapsed."""
    from datetime import timedelta

    now = timezone.now()
    from .models import Schedule

    schedules = Schedule.objects.filter(enabled=True).filter(
        Q(next_run_at__isnull=True) | Q(next_run_at__lte=now)
    )
    for sch in schedules:
        run = Run.objects.create(
            target=sch.target,
            scope=sch.scope or sch.target,
            objective=sch.objective or "comprehensive",
            created_by=sch.created_by,
            session=sch.session,
        )
        from .views import _enqueue_run
        _enqueue_run(run)
        sch.last_run_at = now
        sch.next_run_at = now + timedelta(minutes=sch.interval_minutes or 1440)
        sch.save(update_fields=["last_run_at", "next_run_at", "updated_at"])
    logger.info("run_due_schedules: enqueued %d scheduled scans", len(schedules))


# Grace period (seconds) added to a run's own timeout before the watchdog reaps it.
REAP_GRACE_SECONDS = 120


@shared_task
def reap_stuck_runs() -> None:
    """Celery-beat watchdog: fail runs orphaned by a worker restart/crash.

    A run's timeout is only enforced inside the live Celery task; if the worker
    is restarted or killed mid-run, the run is stranded in 'running' forever.
    This periodic sweep marks any running/queued run whose age exceeds its own
    timeout_seconds + grace as failed so the UI and metrics stay truthful.
    """
    from datetime import timedelta  # noqa: F401  (kept for parity / future use)

    now = timezone.now()
    candidates = Run.objects.filter(
        status__in=[RunStatus.RUNNING, RunStatus.QUEUED]
    )
    reaped = 0
    for run in candidates:
        anchor = run.started_at or run.created_at
        if not anchor:
            continue
        limit = (run.timeout_seconds or 900) + REAP_GRACE_SECONDS
        if (now - anchor).total_seconds() <= limit:
            continue
        run.status = RunStatus.FAILED
        run.completed_at = run.completed_at or now
        run.error_message = (
            (run.error_message or "")
            + f" [reaped: exceeded timeout ({run.timeout_seconds}s) — orphaned by watchdog]"
        ).strip()
        run.save(update_fields=["status", "completed_at", "error_message", "updated_at"])
        reaped += 1
    if reaped:
        logger.warning("reap_stuck_runs: marked %d stuck run(s) as failed", reaped)


@shared_task(bind=True)
def execute_run(self, run_id: str) -> None:
    run = Run.objects.filter(id=run_id).select_related("created_by").first()
    if not run:
        logger.warning("execute_run: run %s not found", run_id)
        return

    run.status = RunStatus.RUNNING
    run.started_at = timezone.now()
    run.error_message = ""
    run.celery_task_id = getattr(self.request, "id", "") or ""
    run.save(update_fields=[
        "status", "started_at", "error_message", "celery_task_id", "updated_at",
    ])

    callback = make_event_callback(run)

    # Engine imports are deferred so the web process / mgmt commands stay light.
    from redweaver_engine.tools.instrumentation import run_context

    from .engines import NoLLMKeyError, get_hunt_engine

    keys = keys_provider_for_user(run.created_by)
    engine = get_hunt_engine()

    with run_context(str(run.id), None):
        try:
            try:
                result = engine.run_hunt(run=run, keys_provider=keys, callback=callback)
            except NoLLMKeyError:
                callback("hunt_error", {"error": "No LLM API key configured"})
                run.status = RunStatus.FAILED
                run.error_message = "No LLM API key configured"
                run.save(update_fields=["status", "error_message", "updated_at"])
                return

            # Capture LLM token usage + estimated cost from the engine result.
            if result.total_tokens or result.prompt_tokens or result.completion_tokens:
                run.prompt_tokens = result.prompt_tokens
                run.completion_tokens = result.completion_tokens
                run.total_tokens = result.total_tokens or (
                    result.prompt_tokens + result.completion_tokens
                )
                run.cost_usd = estimate_cost_usd(
                    result.model, result.prompt_tokens, result.completion_tokens
                )

            findings_count = run.findings.count()
            completed = result.completed_agents
            run.report_markdown = result.report_markdown
            run.status = RunStatus.COMPLETED
            run.completed_at = timezone.now()
            run.messages = [
                {"role": "user", "content": f"Hunt target: {run.target}"},
                {"role": "assistant",
                 "content": f"Hunt completed for {run.target}. "
                            f"{len(completed)} agents executed. "
                            f"Found {findings_count} potential findings."},
            ]
            run.save()
            callback("hunt_complete", {
                "findings_count": findings_count,
                "agents_completed": completed,
            })
            try:
                from collections import Counter
                from .notify import notify_run_complete
                sev = dict(Counter(run.findings.values_list("severity", flat=True)))
                notify_run_complete(run, findings_count, sev)
            except Exception:
                pass
        except SoftTimeLimitExceeded:
            logger.warning("execute_run timed out for %s", run_id)
            run.status = RunStatus.FAILED
            run.error_message = f"Hunt exceeded its time limit ({run.timeout_seconds}s)"
            run.completed_at = timezone.now()
            run.save(update_fields=["status", "error_message", "completed_at", "updated_at"])
            callback("hunt_error", {"error": run.error_message})
        except Exception as exc:  # noqa: BLE001
            logger.exception("execute_run failed for %s", run_id)
            # Provider errors echo back credential fragments (e.g. OpenAI 401) —
            # scrub before this reaches the DB and the UI.
            safe_error = scrub_secrets(str(exc))
            run.status = RunStatus.FAILED
            run.error_message = safe_error
            run.completed_at = timezone.now()
            run.save(update_fields=["status", "error_message", "completed_at", "updated_at"])
            callback("hunt_error", {"error": safe_error})
        finally:
            try:
                from redweaver_engine.tools.ssh.session_manager import SSHSessionManager
                SSHSessionManager.reset()
            except Exception:
                pass
