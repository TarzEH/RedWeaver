"""CrewAI implementation of HuntEngine — wraps the existing crew flow verbatim.

This is the default engine. Its logic is the inner block that previously lived
in `tasks.execute_run` / `offsec_tasks.generate_offsec_playbook`, moved behind
the engine interface with no behavioral change.
"""
from __future__ import annotations

import logging
from typing import Any

from ..crew_factory import _build_crewai_llm, build_crew_factory
from .base import EventCallback, HuntEngine, HuntResult, NoLLMKeyError

logger = logging.getLogger(__name__)


class CrewAIEngine(HuntEngine):
    name = "crewai"

    def run_hunt(self, *, run: Any, keys_provider: Any, callback: EventCallback) -> HuntResult:
        from redweaver_engine.crews.bug_hunt.callbacks import (
            CrewAIEventBridge,
            _extract_report_markdown,
        )
        from redweaver_engine.huntflow_types import HuntflowTree
        from redweaver_engine.tools.instrumentation import run_context

        factory = build_crew_factory(keys_provider)
        if factory is None:
            raise NoLLMKeyError("No LLM API key configured")

        tree = HuntflowTree(str(run.id), run.target or "")
        bridge = CrewAIEventBridge(tree=tree, event_callback=callback, run_id=str(run.id))

        callback("graph_state", {
            "current_node": "orchestrator", "action": "start",
            "active_nodes": ["orchestrator"], "completed_nodes": [],
        })

        with run_context(str(run.id), None):
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

        out = HuntResult(report_markdown=report_md, completed_agents=bridge.completed_agents)
        usage = getattr(result, "token_usage", None)
        if usage is not None:
            out.prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            out.completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
            out.total_tokens = int(
                getattr(usage, "total_tokens", 0) or (out.prompt_tokens + out.completion_tokens)
            )
        try:
            out.model = (keys_provider.get_all() or {}).get("selected_model") or ""
        except Exception:
            out.model = ""
        return out

    def run_offsec(
        self,
        *,
        run: Any,
        keys_provider: Any,
        findings: list[dict],
        research_md: str,
        callback: EventCallback | None = None,
    ) -> str:
        from redweaver_engine.crews.offsec import build_offsec_crew
        from redweaver_engine.llm_factory import LLMFactory
        from redweaver_engine.tools.registry import ToolRegistry

        lf = LLMFactory(keys_provider)
        if not lf.has_api_key():
            raise NoLLMKeyError("No LLM API key configured")
        keys = keys_provider.get_all()
        llm = _build_crewai_llm(lf, keys)
        registry = ToolRegistry(
            virustotal_api_key=keys.get("virustotal_api_key"),
            urlscan_api_key=keys.get("urlscan_api_key"),
        )
        crew = build_offsec_crew(
            llm=llm,
            registry=registry,
            target=run.target or "",
            findings=findings,
            run_id=str(run.id),
            research_context=research_md,
        )
        result = crew.kickoff()
        return (getattr(result, "raw", None) or str(result) or "").strip()
