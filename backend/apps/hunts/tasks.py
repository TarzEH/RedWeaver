"""Celery task that runs a hunt (crew.kickoff) out-of-process.

Port of the legacy HuntExecutionService.execute, with state writes going to
Postgres (via the observability sink) and live events to Channels. Runs
synchronously inside the Celery worker (no asyncio / thread pool).
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from apps.accounts.keys import keys_provider_for_user

from .crew_factory import build_crew_factory
from .models import Run, RunStatus
from .observability_sink import make_event_callback

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def execute_run(self, run_id: str) -> None:
    run = Run.objects.filter(id=run_id).select_related("created_by").first()
    if not run:
        logger.warning("execute_run: run %s not found", run_id)
        return

    run.status = RunStatus.RUNNING
    run.started_at = timezone.now()
    run.error_message = ""
    run.save(update_fields=["status", "started_at", "error_message", "updated_at"])

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
