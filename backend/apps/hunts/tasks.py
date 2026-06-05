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

from .costs import estimate_cost_usd
from .crew_factory import build_crew_factory
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
    from redweaver_engine.crews.bug_hunt.callbacks import (
        CrewAIEventBridge,
        _extract_report_markdown,
    )
    from redweaver_engine.huntflow_types import HuntflowTree
    from redweaver_engine.tools.instrumentation import run_context

    keys = keys_provider_for_user(run.created_by)
    factory = build_crew_factory(keys)
    if factory is None:
        callback("hunt_error", {"error": "No LLM API key configured"})
        run.status = RunStatus.FAILED
        run.error_message = "No LLM API key configured"
        run.save(update_fields=["status", "error_message", "updated_at"])
        return

    tree = HuntflowTree(str(run.id), run.target or "")
    bridge = CrewAIEventBridge(tree=tree, event_callback=callback, run_id=str(run.id))

    callback("graph_state", {
        "current_node": "orchestrator", "action": "start",
        "active_nodes": ["orchestrator"], "completed_nodes": [],
    })

    with run_context(str(run.id), None):
        try:
            crew = factory.create_crew(
                target=run.target or "",
                scope=run.scope or "",
                objective=run.objective or "comprehensive",
                ssh_config=run.ssh_config if isinstance(run.ssh_config, dict) else None,
                step_callback=bridge.step_callback,
                task_callback=bridge.task_callback,
                event_bridge=bridge,
                run_id=str(run.id),
                attack_techniques=run.attack_focus or None,
            )
            logger.info("CrewAI kickoff for run %s (target=%s)", run.id, run.target)
            result = crew.kickoff()

            report_md = bridge.report_markdown
            for t_out in (getattr(result, "tasks_output", None) or []):
                md = _extract_report_markdown(t_out)
                if md and len(md) > len(report_md):
                    report_md = md
            md = _extract_report_markdown(result)
            if md and len(md) > len(report_md):
                report_md = md

            # Capture LLM token usage + estimated cost from the crew result.
            usage = getattr(result, "token_usage", None)
            if usage is not None:
                pt = int(getattr(usage, "prompt_tokens", 0) or 0)
                ct = int(getattr(usage, "completion_tokens", 0) or 0)
                run.prompt_tokens = pt
                run.completion_tokens = ct
                run.total_tokens = int(getattr(usage, "total_tokens", 0) or (pt + ct))
                try:
                    model = (keys.get_all() or {}).get("selected_model") or ""
                except Exception:
                    model = ""
                run.cost_usd = estimate_cost_usd(model, pt, ct)

            findings_count = run.findings.count()
            completed = bridge.completed_agents
            run.report_markdown = report_md
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
            run.status = RunStatus.FAILED
            run.error_message = str(exc)
            run.completed_at = timezone.now()
            run.save(update_fields=["status", "error_message", "completed_at", "updated_at"])
            callback("hunt_error", {"error": str(exc)})
        finally:
            try:
                from redweaver_engine.tools.ssh.session_manager import SSHSessionManager
                SSHSessionManager.reset()
            except Exception:
                pass
