"""deepagents / LangGraph implementation of HuntEngine.

Selected via ``HUNT_ENGINE=deepagents``. Inert by default (CrewAI is the
default), so this code never runs unless explicitly enabled.

STATUS (per docs/refactor-deepagents-ragas.md):
  * ``run_offsec`` — implemented (single deep agent). Marked VERIFY: the
    deepagents API is pre-1.0 and churns; confirm the create_deep_agent
    signature (``system_prompt`` vs legacy ``instructions``) and the output
    message shape against the *pinned* version before relying on it.
  * ``run_hunt`` — NOT YET IMPLEMENTED. This is Phase 3: an explicit LangGraph
    StateGraph of deepagents sub-agents (nodes) wired into the deterministic
    recon → {fuzzer ∥ vuln ∥ crawler} → exploit → [ssh] → report DAG, with the
    LangGraphEventBridge mapping stream events to the observability sinks. It
    must be built and validated against a running stack, not guessed offline.
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
        raise NotImplementedError(
            "deepagents bug-hunt engine (LangGraph DAG) is Phase 3 — not yet "
            "implemented. Set HUNT_ENGINE=crewai. See "
            "docs/refactor-deepagents-ragas.md."
        )

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
