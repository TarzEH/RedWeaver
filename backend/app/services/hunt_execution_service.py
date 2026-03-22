"""Hunt execution service: orchestrates hunt runs using CrewAI.

Uses CrewFactory to build a Crew of specialized agents, kicks off
the hunt in a thread executor (CrewAI is synchronous), and bridges
lifecycle events to the SSE EventBus via CrewAIEventBridge.

Best practices:
- Configures memory embedder based on LLM provider
- Passes embedder config through CrewFactory for cross-run memory
- Structured SSH config extraction from run metadata
- Comprehensive error handling with cleanup
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
import time
import uuid
from typing import Any, Callable

logger = logging.getLogger(__name__)

from app.core.crew_factory_provider import build_crew_factory
from app.crews.bug_hunt.callbacks import CrewAIEventBridge, _extract_report_markdown
from app.core.event_bus import EventBus
from app.models.huntflow import HuntflowTree
from app.repositories.api_keys_repository import ApiKeysRepositoryProtocol
from app.repositories.huntflow_repository import HuntflowRepositoryProtocol
from app.repositories.run_repository import RunRepositoryProtocol

_CREW_EXECUTOR: concurrent.futures.ThreadPoolExecutor | None = None

# Persisted into graph_state.steps for reload (SSE event types only).
_REASONING_PERSIST_EVENTS = frozenset({
    "agent_start",
    "agent_thinking",
    "tool_call",
    "tool_result",
    "agent_complete",
    "finding",
    "todo_update",
    "agent_handoff",
})


def _crew_executor() -> concurrent.futures.ThreadPoolExecutor:
    """Bounded pool for CrewAI kickoff so the default executor is not saturated."""
    global _CREW_EXECUTOR
    if _CREW_EXECUTOR is None:
        workers = max(1, int(os.environ.get("CREW_EXECUTOR_WORKERS", "4")))
        _CREW_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
            max_workers=workers,
            thread_name_prefix="crew_kickoff",
        )
    return _CREW_EXECUTOR


class HuntExecutionService:
    """Orchestrates hunt execution with CrewAI."""

    def __init__(
        self,
        run_repository: RunRepositoryProtocol,
        huntflow_repository: HuntflowRepositoryProtocol,
        api_keys_repository: ApiKeysRepositoryProtocol,
        event_bus: EventBus,
    ) -> None:
        self._runs = run_repository
        self._huntflows = huntflow_repository
        self._keys = api_keys_repository
        self._event_bus = event_bus

    async def execute(self, run_id: str) -> None:
        """Execute a hunt run. Must be called via asyncio.create_task()."""
        logger.info("Execute start: run_id=%s", run_id)
        run = self._runs.get(run_id)
        if not run:
            logger.warning("run_id=%s not found", run_id)
            return

        # Mark as running with initialized graph state (single atomic update)
        self._runs.update(run_id, {
            "status": "running",
            "graph_state": {
                "current_node": "orchestrator",
                "active_nodes": [],
                "completed_nodes": [],
                "plan": [],
                "steps": [],
            },
        })

        # Yield before any heavy work. create_task(execute) runs the coroutine until the
        # first await — without this, build_crew_factory + create_crew (HTTP template,
        # imports) block the event loop and delay POST /api/chat responses by seconds.
        await asyncio.sleep(0)

        # Create Huntflow tree
        tree = self._huntflows.create_tree(run_id, run.target or "")

        # Build CrewAI factory
        crew_factory = build_crew_factory(self._keys)
        if crew_factory is None:
            logger.error("No LLM configured for %s", run_id)
            self._runs.update(run_id, {"status": "failed"})
            self._publish(run_id, "hunt_error", {"error": "No LLM API key configured"})
            return

        # State tracking for run repository updates
        tracker = _RunStateTracker(run_id, self._runs)
        _event_counter = [0]

        def event_callback(event_type: str, data: dict[str, Any]) -> None:
            _event_counter[0] += 1
            n = _event_counter[0]
            if event_type != "agent_thinking":
                subs = self._event_bus.subscriber_count(run_id)
                logger.debug("Event #%d: %s (subs=%d, agent=%s)",
                             n, event_type, subs, data.get("agent", "?"))
            tracker.on_event(event_type, data)
            if event_type in ("hunt_complete", "hunt_error"):
                tracker.flush_graph_state()
            self._publish(run_id, event_type, {**data, "run_id": run_id})

        # Brief yield for SSE subscriber connection
        await asyncio.sleep(0)
        subs = self._event_bus.subscriber_count(run_id)
        logger.info("Starting hunt (subs=%d, buffering=%s)", subs, "on" if subs == 0 else "off")

        # Emit initial graph_state
        event_callback("graph_state", {
            "current_node": "orchestrator",
            "action": "start",
            "active_nodes": ["orchestrator"],
            "completed_nodes": [],
        })
        await asyncio.sleep(0)

        # Create event bridge
        bridge = CrewAIEventBridge(tree=tree, event_callback=event_callback)

        try:
            target = run.target or ""
            scope = run.scope or ""
            objective = run.objective or "comprehensive"

            # Extract SSH config from run metadata if present
            ssh_config = self._extract_ssh_config(run)

            # Build the Crew
            crew = crew_factory.create_crew(
                target=target,
                scope=scope,
                objective=objective,
                ssh_config=ssh_config,
                step_callback=bridge.step_callback,
                task_callback=bridge.task_callback,
                event_bridge=bridge,
            )

            logger.info(
                "Running CrewAI hunt for %s (agents=%d, tasks=%d, memory=%s, planning=%s)",
                target, len(crew.agents), len(crew.tasks),
                getattr(crew, 'memory', False),
                getattr(crew, 'planning', False),
            )

            # CrewAI kickoff() is synchronous — run in dedicated bounded executor
            loop = asyncio.get_running_loop()
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(_crew_executor(), crew.kickoff),
                    timeout=900,  # 15 minute timeout
                )
            except asyncio.TimeoutError:
                logger.error("TIMEOUT: crew.kickoff() exceeded 15 minutes")
                event_callback("hunt_error", {"error": "Hunt timed out after 15 minutes"})
                self._runs.update(run_id, {"status": "failed"})
                self._huntflows.persist()
                return

            logger.info("Run done, %d events emitted", _event_counter[0])

            # Persist findings + report_markdown to Redis BEFORE hunt_complete so clients that
            # refetch /api/runs/{id}/report on SSE completion see the final graph_state.
            findings_count, agents_completed = await self._finalize_run(
                run_id, result, bridge, tracker, target,
            )

            event_callback("hunt_complete", {
                "findings_count": findings_count,
                "agents_completed": agents_completed,
            })

        except Exception as e:
            logger.exception("Run %s FAILED: %s", run_id, e)
            self._runs.update(run_id, {"status": "failed"})
            self._huntflows.persist()
            event_callback("hunt_error", {"error": str(e)})

        finally:
            # Clean up SSH sessions
            self._cleanup_ssh()

    async def _finalize_run(
        self,
        run_id: str,
        result: Any,
        bridge: CrewAIEventBridge,
        tracker: _RunStateTracker,
        target: str,
    ) -> None:
        """Finalize a completed hunt: merge findings, update run."""
        # Collect findings from bridge (primary source)
        all_findings = list(bridge.findings)

        # Also merge any findings from the tracker (backup)
        seen_ids = {f.get("id") for f in all_findings if f.get("id")}
        for f in tracker.findings_cache:
            if f.get("id") not in seen_ids:
                all_findings.append(f)
                seen_ids.add(f.get("id"))

        # Extract report markdown (bridge + every task output — CrewOutput.pydantic is only
        # the *last* task, which may not be report_writer when fuzzer/vuln run in parallel).
        report_markdown = bridge.report_markdown
        if result is not None:
            tasks_out = getattr(result, "tasks_output", None) or []
            for t_out in tasks_out:
                md = _extract_report_markdown(t_out)
                if md and len(md) > len(report_markdown):
                    report_markdown = md

        # Fallback: crew-level object (mirrors last task — may help if tasks_output empty)
        if result is not None:
            md = _extract_report_markdown(result)
            if md and len(md) > len(report_markdown):
                report_markdown = md

        if not report_markdown:
            logger.warning(
                "run_id=%s: report_markdown still empty after hunt (tasks_output=%d)",
                run_id,
                len(getattr(result, "tasks_output", None) or []) if result is not None else 0,
            )

        # Build summary
        completed = bridge.completed_agents
        summary_parts = [f"Hunt completed for {target}."]
        if completed:
            summary_parts.append(f"{len(completed)} agents executed.")
        if all_findings:
            summary_parts.append(f"Found {len(all_findings)} potential findings.")
        if report_markdown:
            summary_parts.append("Report generated successfully.")
        summary = " ".join(summary_parts)

        # Update run — do not duplicate report_markdown as a chat message; it lives in
        # graph_state.report_markdown and is shown via the hunt report UI / report API.
        self._runs.update(run_id, {
            "messages": [
                {"role": "user", "content": f"Hunt target: {target}"},
                {"role": "assistant", "content": summary},
            ],
            "graph_state": {
                "current_node": "end",
                "active_nodes": [],
                "completed_nodes": completed + ["end"],
                "plan": list(tracker.plan_cache),
                "steps": tracker.export_reasoning_steps(),
                "findings": all_findings,
                "report_markdown": report_markdown,
            },
            "status": "completed",
        })

        # Persist huntflow tree
        self._huntflows.persist()

        logger.info("Run %s completed: %d findings, %d agents",
                    run_id, len(all_findings), len(completed))
        return len(all_findings), list(completed)

    @staticmethod
    def _extract_ssh_config(run: Any) -> dict[str, Any] | None:
        """Extract SSH configuration from run metadata."""
        # Check for ssh_config in run attributes (set by ChatView frontend)
        if hasattr(run, "ssh_config") and run.ssh_config:
            cfg = run.ssh_config
            if isinstance(cfg, dict) and cfg.get("host"):
                return cfg

        if not run.objective:
            return None

        try:
            # Check if objective contains JSON with SSH config
            if "ssh_" in run.objective.lower():
                import re
                host_match = re.search(r'ssh_host[=:]\s*(\S+)', run.objective)
                user_match = re.search(r'ssh_user[=:]\s*(\S+)', run.objective)
                pass_match = re.search(r'ssh_pass[=:]\s*(\S+)', run.objective)
                key_match = re.search(r'ssh_key[=:]\s*(\S+)', run.objective)

                if host_match:
                    return {
                        "host": host_match.group(1),
                        "username": user_match.group(1) if user_match else "root",
                        "password": pass_match.group(1) if pass_match else "",
                        "key_path": key_match.group(1) if key_match else "",
                        "port": 22,
                    }
        except Exception:
            pass

        return None

    @staticmethod
    def _cleanup_ssh() -> None:
        """Clean up SSH sessions after hunt completion."""
        try:
            from app.tools.ssh.session_manager import SSHSessionManager
            SSHSessionManager.reset()
        except Exception as e:
            logger.warning("SSH cleanup failed: %s", e)

    def _publish(self, run_id: str, event_type: str, data: dict[str, Any]) -> None:
        """Publish SSE event via EventBus (thread-safe for Crew worker threads)."""
        self._event_bus.publish_event(run_id, {"type": event_type, "data": data})


class _RunStateTracker:
    """Tracks run state from SSE events for repository updates."""

    def __init__(self, run_id: str, run_repository: RunRepositoryProtocol) -> None:
        self._run_id = run_id
        self._runs = run_repository
        self.active_nodes: set[str] = set()
        self.completed_nodes: list[str] = []
        self.plan_cache: list[str] = []
        self.findings_cache: list[dict] = []
        self._reasoning_steps: list[dict[str, Any]] = []
        try:
            self._max_reasoning_steps = int(os.environ.get("RUN_REASONING_STEPS_MAX", "800"))
        except ValueError:
            self._max_reasoning_steps = 800
        self._last_graph_flush = 0.0
        try:
            self._flush_interval_s = float(os.environ.get("RUN_STATE_FLUSH_INTERVAL_SEC", "0.5"))
        except ValueError:
            self._flush_interval_s = 0.5

    def on_event(self, event_type: str, data: dict[str, Any]) -> None:
        finding_added = True
        if event_type == "graph_state":
            self._merge_graph_state(data)
        elif event_type == "todo_update":
            self._update_plan(data)
        elif event_type == "finding":
            finding_added = self._add_finding(data)

        if event_type in _REASONING_PERSIST_EVENTS and (event_type != "finding" or finding_added):
            self._append_reasoning_step(event_type, data)

        if event_type == "graph_state":
            self._flush_graph_to_redis(force=False)
        elif event_type in ("todo_update", "finding"):
            self._flush_graph_to_redis(force=True)
        elif event_type in _REASONING_PERSIST_EVENTS:
            self._flush_graph_to_redis(force=False)

    def export_reasoning_steps(self) -> list[dict[str, Any]]:
        """Snapshot of persisted reasoning steps (for final run document)."""
        return list(self._reasoning_steps)

    def _add_finding(self, data: dict[str, Any]) -> bool:
        fid = data.get("id")
        if fid and any(f.get("id") == fid for f in self.findings_cache):
            return False
        self.findings_cache.append(data)
        return True

    def _append_reasoning_step(self, event_type: str, data: dict[str, Any]) -> None:
        raw_agent = data.get("agent") or "unknown"
        agent = raw_agent if isinstance(raw_agent, str) else str(raw_agent)
        content = ""
        tool = data.get("tool")
        tool_s = tool if isinstance(tool, str) else None

        if event_type == "agent_start":
            content = f"{agent} started"
        elif event_type == "agent_thinking":
            content = (str(data.get("content") or data.get("thinking") or ""))[:8000]
        elif event_type == "tool_call":
            inp = data.get("input")
            tname = data.get("tool")
            if inp not in (None, ""):
                content = str(inp)[:2000]
            elif tname:
                content = str(tname)
            else:
                content = "tool_call"
        elif event_type == "tool_result":
            content = str(data.get("summary") or data.get("output") or "")[:8000]
        elif event_type == "agent_complete":
            content = str(data.get("summary") or "")[:2000]
        elif event_type == "finding":
            sev = str(data.get("severity") or "info").upper()
            title = str(data.get("title") or "")
            content = f"[{sev}] {title}"
            agent = str(data.get("agent_source") or agent)
        elif event_type == "todo_update":
            todos = data.get("todos") or []
            content = f"Plan updated: {len(todos)} tasks"
            agent = "orchestrator"
        elif event_type == "agent_handoff":
            content = (
                f"Handoff: {data.get('from_display', '')} → {data.get('to_display', '')}"
            )[:500]
        else:
            return

        if not content and event_type not in ("agent_start", "tool_call"):
            return

        step: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "agent": agent,
            "type": event_type,
            "content": content,
            "timestamp": int(time.time() * 1000),
        }
        if tool_s:
            step["tool"] = tool_s
        self._reasoning_steps.append(step)
        if len(self._reasoning_steps) > self._max_reasoning_steps:
            self._reasoning_steps = self._reasoning_steps[-self._max_reasoning_steps :]

    def flush_graph_state(self) -> None:
        """Force-persist graph snapshot (e.g. hunt terminal events)."""
        self._flush_graph_to_redis(force=True)

    def _merge_graph_state(self, data: dict[str, Any]) -> None:
        action = data.get("action", "start")
        if action == "start":
            node = data.get("current_node", "")
            if node:
                self.active_nodes.add(node)
        elif action == "end":
            node = data.get("completed_node", "")
            if node:
                self.active_nodes.discard(node)
                if node not in self.completed_nodes:
                    self.completed_nodes.append(node)

        incoming_active = data.get("active_nodes")
        if incoming_active is not None:
            self.active_nodes.clear()
            self.active_nodes.update(incoming_active)
        incoming_completed = data.get("completed_nodes")
        if incoming_completed is not None:
            for n in incoming_completed:
                if n not in self.completed_nodes:
                    self.completed_nodes.append(n)

        incoming_plan = data.get("plan")
        if incoming_plan:
            self.plan_cache.clear()
            self.plan_cache.extend(incoming_plan)

    def _flush_graph_to_redis(self, force: bool) -> None:
        now = time.monotonic()
        if self._last_graph_flush == 0.0:
            force = True
        if not force and (now - self._last_graph_flush) < self._flush_interval_s:
            return
        self._last_graph_flush = now
        self._runs.update(self._run_id, {
            "graph_state": {
                "current_node": sorted(self.active_nodes)[0] if self.active_nodes else None,
                "active_nodes": sorted(self.active_nodes),
                "completed_nodes": list(self.completed_nodes),
                "plan": list(self.plan_cache),
                "steps": list(self._reasoning_steps),
                "findings": list(self.findings_cache),
            },
        })

    def _update_plan(self, data: dict[str, Any]) -> None:
        todos = data.get("todos", [])
        if todos:
            plan_items = []
            for t in todos:
                if isinstance(t, dict):
                    plan_items.append(t.get("task", t.get("content", str(t))))
                else:
                    plan_items.append(str(t))
            self.plan_cache.clear()
            self.plan_cache.extend(plan_items)
