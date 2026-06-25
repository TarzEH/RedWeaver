"""deepagents / LangGraph implementation of HuntEngine.

Selected via ``HUNT_ENGINE=deepagents``. Inert by default (CrewAI is the
default), so this code never runs unless explicitly enabled.

STATUS (per docs/refactor-deepagents-ragas.md):
  * ``run_offsec`` — implemented (single deep agent). The create_deep_agent
    signature (incl. ``system_prompt``) is CONFIRMED against deepagents 0.6.12;
    the final output-message shape is still verified at runtime (live model call).
  * ``run_hunt`` — implemented via the LangGraph StateGraph of deepagents
    sub-agents (graph_engine.py): the deterministic recon → {fuzzer ∥ vuln ∥
    crawler} → exploit → [ssh] → report DAG, with LangGraphHuntBridge mapping
    node lifecycle to the observability sinks. Needs a live-stack run to validate
    end-to-end (findings/report/token accounting).
"""
from __future__ import annotations

import logging
from typing import Any

from .base import EventCallback, HuntEngine, HuntResult, NoLLMKeyError

logger = logging.getLogger(__name__)


# Concise offsec operator prompt for the deepagents path. Reconcile with the
# CrewAI backstory in redweaver_engine/crews/offsec.py during Phase 2 hardening.
_OFFSEC_SYSTEM_PROMPT = (
    "You are an offensive-security operator. Turn the provided findings into a "
    "concrete, per-finding attack playbook: exact commands, payloads, and the "
    "relevant MITRE ATT&CK techniques. ALWAYS ground steps in the knowledge base "
    "(use the knowledge_search tool) and corroborate exploits with web_search / "
    "cvedetails_lookup. Prioritize by real risk (KEV/EPSS/exploit availability), "
    "not CVSS alone. Output a single well-structured Markdown playbook."
)


class DeepAgentsEngine(HuntEngine):
    name = "deepagents"

    def _chat_model(self, keys_provider: Any):
        from redweaver_engine.llm_factory import LLMFactory

        lf = LLMFactory(keys_provider)
        if not lf.has_api_key():
            raise NoLLMKeyError("No LLM API key configured")
        return lf.build_langchain_chat_model()

    def run_hunt(self, *, run: Any, keys_provider: Any, callback: EventCallback) -> HuntResult:
        from redweaver_engine.crews.bug_hunt.graph_bridge import LangGraphHuntBridge
        from redweaver_engine.crews.bug_hunt.graph_engine import GraphHuntEngine
        from redweaver_engine.huntflow_types import HuntflowTree
        from redweaver_engine.tools.instrumentation import run_context
        from redweaver_engine.tools.registry import ToolRegistry

        keys = keys_provider.get_all()
        llm = self._chat_model(keys_provider)
        registry = ToolRegistry(
            virustotal_api_key=keys.get("virustotal_api_key"),
            urlscan_api_key=keys.get("urlscan_api_key"),
        )

        ssh_config = run.ssh_config if isinstance(run.ssh_config, dict) else None
        attack_techniques = run.attack_focus or None

        # Pre-hunt ATT&CK focus directive (same derivation as the CrewAI factory).
        attack_focus = ""
        if attack_techniques:
            from redweaver_engine.crews.bug_hunt.attack_planning import plan_from_techniques
            from redweaver_engine.crews.bug_hunt.selection import (
                TARGET_AGENT_MAP,
                select_agent_names,
            )

            ttype, _sel = select_agent_names(
                run.target or "", run.objective or "comprehensive",
                ssh_config, attack_techniques=attack_techniques,
            )
            attack_focus = plan_from_techniques(
                attack_techniques,
                list(TARGET_AGENT_MAP.get(ttype, TARGET_AGENT_MAP["web"])),
                ssh_config,
            )["focus"]

        tree = HuntflowTree(str(run.id), run.target or "")
        bridge = LangGraphHuntBridge(tree=tree, event_callback=callback, run_id=str(run.id))
        callback("graph_state", {
            "current_node": "orchestrator", "action": "start",
            "active_nodes": ["orchestrator"], "completed_nodes": [],
        })

        engine = GraphHuntEngine(llm=llm, registry=registry, run_id=str(run.id))
        with run_context(str(run.id), None):
            logger.info("LangGraph hunt for run %s (target=%s)", run.id, run.target)
            out = engine.run(
                target=run.target or "",
                scope=run.scope or "",
                objective=run.objective or "comprehensive",
                ssh_config=ssh_config,
                attack_techniques=attack_techniques,
                attack_focus=attack_focus,
                bridge=bridge,
            )

        result = HuntResult(
            report_markdown=out["report_markdown"],
            prompt_tokens=out["prompt_tokens"],
            completion_tokens=out["completion_tokens"],
            total_tokens=out["prompt_tokens"] + out["completion_tokens"],
            completed_agents=out["completed_agents"],
        )
        try:
            result.model = (keys or {}).get("selected_model") or ""
        except Exception:
            result.model = ""
        return result

    def run_offsec(
        self,
        *,
        run: Any,
        keys_provider: Any,
        findings: list[dict],
        research_md: str,
        callback: EventCallback | None = None,
    ) -> str:
        # VERIFY against pinned deepagents version (API churns pre-1.0).
        from deepagents import create_deep_agent  # type: ignore

        from redweaver_engine.tools.langchain_adapter import to_langchain_tools
        from redweaver_engine.tools.registry import ToolRegistry

        keys = keys_provider.get_all()
        registry = ToolRegistry(
            virustotal_api_key=keys.get("virustotal_api_key"),
            urlscan_api_key=keys.get("urlscan_api_key"),
        )
        # offsec uses research/grounding tools, not scanners.
        tool_names = ("knowledge_search", "web_search", "cvedetails_lookup")
        bug_tools = [registry.get_tool(n) for n in tool_names]
        bug_tools = [t for t in bug_tools if t is not None]
        lc_tools = to_langchain_tools(bug_tools, run_id=str(run.id), agent="offsec")

        agent = create_deep_agent(
            model=self._chat_model(keys_provider),
            tools=lc_tools,
            system_prompt=_OFFSEC_SYSTEM_PROMPT,
        )
        task = (
            f"Target: {run.target or ''}\n\n"
            f"Findings (JSON-ish): {findings}\n\n"
            f"Pre-gathered research:\n{research_md}\n\n"
            "Produce the full per-finding attack playbook in Markdown."
        )
        result = agent.invoke({"messages": [{"role": "user", "content": task}]})
        # VERIFY: output message shape under the default in-memory backend.
        try:
            return (result["messages"][-1].content or "").strip()
        except Exception:  # noqa: BLE001
            return str(result).strip()
