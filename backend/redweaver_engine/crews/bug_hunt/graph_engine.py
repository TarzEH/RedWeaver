"""LangGraph DAG hunt engine — deepagents sub-agents wired into the deterministic
recon → {fuzzer ∥ vuln_scanner ∥ crawler ∥ web_search} → exploit_analyst →
[privesc → tunnel_pivot → post_exploit] → report_writer pipeline.

Each selected agent becomes a node running a `deepagents` sub-agent (its YAML
role/goal/backstory as the system prompt, its registry tools wrapped as LangChain
tools, its Pydantic schema as `response_format`). Edges encode the dependency DAG
so ordering is guaranteed (LangGraph supersteps fan-out/fan-in); the
LangGraphHuntBridge maps node lifecycle + structured output to the same events
and findings the CrewAI path produced.

VERIFY (deepagents is pre-1.0, API churns): confirm against the pinned version —
  * create_deep_agent kwarg names (`system_prompt`/`response_format`),
  * the structured-output location in the invoke result,
  * AIMessage.usage_metadata shape (token accounting),
  * sync .invoke superstep concurrency (true wall-clock parallelism of the
    discovery batch likely needs the async path — ordering holds either way).
KNOWN GAP: SSH + file-IO tools are CrewAI-specific; LangChain equivalents are a
follow-up, so SSH-target hunts are not yet at full parity on this engine.
"""
from __future__ import annotations

import logging
import operator
import threading
from typing import Annotated, Any, Callable, TypedDict

from redweaver_engine.crews.bug_hunt.config_loader import (
    get_agent_prompt_dicts,
    get_task_description_templates,
)
from redweaver_engine.crews.bug_hunt.graph_bridge import LangGraphHuntBridge
from redweaver_engine.crews.bug_hunt.schemas import (
    CrawlerResult,
    ExploitAnalysisResult,
    FuzzerResult,
    HuntReport,
    PostExploitResult,
    PrivEscResult,
    ReconResult,
    TunnelPivotResult,
    VulnScanResult,
    WebSearchResult,
)
from redweaver_engine.crews.bug_hunt.selection import SSH_AGENTS, select_agent_names
from redweaver_engine.crews.bug_hunt.template import fetch_report_template
from redweaver_engine.tools.langchain_adapter import to_langchain_tools

logger = logging.getLogger(__name__)

AGENT_SCHEMAS = {
    "recon": ReconResult,
    "fuzzer": FuzzerResult,
    "vuln_scanner": VulnScanResult,
    "crawler": CrawlerResult,
    "web_search": WebSearchResult,
    "exploit_analyst": ExploitAnalysisResult,
    "privesc": PrivEscResult,
    "tunnel_pivot": TunnelPivotResult,
    "post_exploit": PostExploitResult,
    "report_writer": HuntReport,
}

DISCOVERY_AGENTS = ["fuzzer", "vuln_scanner", "crawler", "web_search"]
# Which upstream agents' outputs each agent should see as context.
CONTEXT_MAP = {
    "fuzzer": ["recon"],
    "vuln_scanner": ["recon"],
    "crawler": ["recon"],
    "web_search": ["recon"],
    "exploit_analyst": ["recon", "fuzzer", "vuln_scanner", "crawler", "web_search"],
    "privesc": ["recon", "exploit_analyst"],
    "tunnel_pivot": ["recon", "privesc"],
    "post_exploit": ["privesc", "tunnel_pivot"],
    "report_writer": list(AGENT_SCHEMAS.keys()),
}


START_SENTINEL = "__start__"
END_SENTINEL = "__end__"


def plan_dag(present: list[str]) -> list[tuple[str, str]]:
    """Pure DAG planner: given the selected agents, return the directed edges
    (using START/END sentinels). Kept dependency-free so the deterministic
    ordering can be unit-tested without langgraph/deepagents installed.

    Shape: START → recon → {discovery…} → exploit_analyst → [privesc →
    tunnel_pivot → post_exploit] → report_writer → END, with every step elided
    gracefully when its agent is absent.
    """
    present_set = set(present)
    edges: list[tuple[str, str]] = []
    discovery = [a for a in DISCOVERY_AGENTS if a in present_set]
    has_recon = "recon" in present_set

    if has_recon:
        edges.append((START_SENTINEL, "recon"))
        for d in discovery:
            edges.append(("recon", d))
    else:
        for d in (discovery or present[:1]):
            edges.append((START_SENTINEL, d))

    joiners = discovery or (["recon"] if has_recon else [])
    if "exploit_analyst" in present_set:
        for j in (joiners or (["recon"] if has_recon else [])):
            if j in present_set:
                edges.append((j, "exploit_analyst"))
        tail: str | None = "exploit_analyst"
    else:
        tail = None

    ssh_chain = [a for a in ("privesc", "tunnel_pivot", "post_exploit") if a in present_set]
    prev = tail
    if ssh_chain:
        head = ssh_chain[0]
        if prev:
            edges.append((prev, head))
        elif has_recon:
            edges.append(("recon", head))
        for a, b in zip(ssh_chain, ssh_chain[1:]):
            edges.append((a, b))
        prev = ssh_chain[-1]

    terminal = "report_writer" if "report_writer" in present_set else None
    if terminal:
        if prev:
            sources = [prev]
        elif "exploit_analyst" in present_set:
            sources = ["exploit_analyst"]
        elif discovery:
            sources = list(discovery)
        elif has_recon:
            sources = ["recon"]
        else:
            sources = []
        for s in sources:
            edges.append((s, terminal))
        edges.append((terminal, END_SENTINEL))
    else:
        last = prev or ("exploit_analyst" if "exploit_analyst" in present_set else None) \
            or (discovery[-1] if discovery else ("recon" if has_recon else None))
        if last:
            edges.append((last, END_SENTINEL))

    return edges


def _merge_tokens(a: dict, b: dict) -> dict:
    out = dict(a or {})
    for k, v in (b or {}).items():
        out[k] = out.get(k, 0) + (v or 0)
    return out


class HuntState(TypedDict, total=False):
    outputs: Annotated[dict, lambda a, b: {**(a or {}), **(b or {})}]
    tokens: Annotated[dict, _merge_tokens]
    report_markdown: str


def _knowledge_search_tool():
    """A LangChain knowledge_search tool backed by the registered pgvector RAG."""
    from langchain_core.tools import tool

    from redweaver_engine.tools import instrumentation as instr

    @tool
    def knowledge_search(query: str, category: str = "", top_k: int = 5) -> str:
        """Search the security methodology knowledge base (pgvector RAG). Use this
        to ground steps in concrete commands/payloads. `category` optionally filters
        by topic (e.g. reconnaissance, web_attacks, privilege_escalation)."""
        import json as _json

        hits = instr.kb_search(query, top_k, 0.0, category or None)
        return _json.dumps({"results": hits}, default=str)[:8000]

    return knowledge_search


def _coerce_output(result: Any, schema: Any) -> Any:
    """Best-effort extraction of a sub-agent's structured output. VERIFY shape."""
    if isinstance(result, dict):
        for key in ("structured_response", "response", "structured_output"):
            if result.get(key) is not None:
                return result[key]
        msgs = result.get("messages")
        if msgs:
            last = msgs[-1]
            return getattr(last, "content", None) or (
                last.get("content") if isinstance(last, dict) else str(last)
            )
    return result


def _sum_tokens(result: Any) -> tuple[int, int]:
    pt = ct = 0
    msgs = result.get("messages") if isinstance(result, dict) else None
    for m in (msgs or []):
        um = getattr(m, "usage_metadata", None)
        if isinstance(um, dict):
            pt += int(um.get("input_tokens", 0) or 0)
            ct += int(um.get("output_tokens", 0) or 0)
    return pt, ct


def _format_upstream(agent_name: str, outputs: dict) -> str:
    keys = CONTEXT_MAP.get(agent_name, [])
    parts = []
    for k in keys:
        if k in outputs and outputs[k]:
            import json as _json

            parts.append(f"### Context from {k}\n{_json.dumps(outputs[k], default=str)[:4000]}")
    return "\n\n".join(parts)


class GraphHuntEngine:
    """Builds and runs the LangGraph DAG of deepagents sub-agents for a hunt."""

    def __init__(self, llm: Any, registry: Any, run_id: str) -> None:
        self._llm = llm
        self._registry = registry
        self._run_id = run_id
        self._prompts = get_agent_prompt_dicts()
        self._tasks = get_task_description_templates()
        self._knowledge_tool = _knowledge_search_tool()
        self._agent_cache: dict[str, Any] = {}
        self._lock = threading.Lock()

    def _system_prompt(self, agent_name: str) -> str:
        cfg = self._prompts[agent_name]
        return f"ROLE: {cfg['role']}\n\nGOAL: {cfg['goal']}\n\n{cfg['backstory']}"

    def _build_sub_agent(self, agent_name: str):
        with self._lock:
            if agent_name in self._agent_cache:
                return self._agent_cache[agent_name]
            from deepagents import create_deep_agent  # VERIFY pinned API

            tools = to_langchain_tools(
                self._registry.get_tools_for_agent(agent_name), self._run_id, agent_name
            )
            tools.append(self._knowledge_tool)
            agent = create_deep_agent(
                model=self._llm,
                tools=tools,
                system_prompt=self._system_prompt(agent_name),
                response_format=AGENT_SCHEMAS.get(agent_name),
            )
            self._agent_cache[agent_name] = agent
            return agent

    def _task_text(self, agent_name: str, target: str, scope: str,
                   attack_focus: str, outputs: dict) -> str:
        scope_str = scope or "only the exact target given"
        template = self._tasks.get(agent_name, "Perform your role for {target}.")
        desc = template.format(target=target, scope=scope_str)
        if agent_name == "report_writer":
            tmpl = fetch_report_template()
            if tmpl:
                desc += "\n\n## REPORT TEMPLATE REFERENCE\n" + tmpl
        if attack_focus:
            desc += f"\n\n{attack_focus}"
        upstream = _format_upstream(agent_name, outputs)
        if upstream:
            desc += f"\n\n## UPSTREAM CONTEXT\n{upstream}"
        desc += (
            "\n\nReturn your findings as the structured schema (findings array). "
            "Consult knowledge_search for methodology before concluding."
        )
        return desc

    def _make_node(self, agent_name: str, target: str, scope: str,
                   attack_focus: str, bridge: LangGraphHuntBridge) -> Callable:
        schema = AGENT_SCHEMAS.get(agent_name)

        def node(state: HuntState) -> dict:
            bridge.on_agent_start(agent_name)
            task = self._task_text(agent_name, target, scope, attack_focus,
                                   state.get("outputs", {}))
            try:
                agent = self._build_sub_agent(agent_name)
                result = agent.invoke({"messages": [{"role": "user", "content": task}]})
            except Exception as exc:  # noqa: BLE001
                bridge.on_agent_error(agent_name, exc)
                return {"outputs": {agent_name: {}}}

            output = _coerce_output(result, schema)
            bridge.on_agent_output(agent_name, output)
            pt, ct = _sum_tokens(result)

            # Normalize the structured output to a dict for downstream context.
            dump: Any = output
            if hasattr(output, "model_dump"):
                dump = output.model_dump()
            update: dict = {"outputs": {agent_name: dump}, "tokens": {"prompt": pt, "completion": ct}}
            if agent_name == "report_writer":
                update["report_markdown"] = bridge.report_markdown

            n = len([f for f in bridge.findings if f.get("agent_source") == agent_name])
            bridge.on_agent_complete(agent_name, n)
            return update

        return node

    def build_graph(self, target: str, scope: str, objective: str,
                    ssh_config: dict | None, attack_techniques: list | None,
                    attack_focus: str, bridge: LangGraphHuntBridge):
        from langgraph.graph import END, START, StateGraph

        has_ssh = bool(ssh_config and ssh_config.get("host"))
        _type, selected = select_agent_names(
            target, objective, ssh_config, attack_techniques=attack_techniques
        )
        present = [a for a in selected if a in AGENT_SCHEMAS]
        if has_ssh:
            present += [a for a in SSH_AGENTS if a not in present]
        present_set = set(present)

        g = StateGraph(HuntState)
        for name in present:
            g.add_node(name, self._make_node(name, target, scope, attack_focus, bridge))

        for a, b in plan_dag(present):
            src = START if a == START_SENTINEL else a
            dst = END if b == END_SENTINEL else b
            g.add_edge(src, dst)

        return g.compile()

    def run(self, target: str, scope: str, objective: str,
            ssh_config: dict | None, attack_techniques: list | None,
            attack_focus: str, bridge: LangGraphHuntBridge) -> dict:
        graph = self.build_graph(target, scope, objective, ssh_config,
                                 attack_techniques, attack_focus, bridge)
        final = graph.invoke({"outputs": {}, "tokens": {}})
        tokens = final.get("tokens", {}) if isinstance(final, dict) else {}
        return {
            "report_markdown": bridge.report_markdown
            or (final.get("report_markdown", "") if isinstance(final, dict) else ""),
            "prompt_tokens": int(tokens.get("prompt", 0) or 0),
            "completion_tokens": int(tokens.get("completion", 0) or 0),
            "completed_agents": bridge.completed_agents,
        }
