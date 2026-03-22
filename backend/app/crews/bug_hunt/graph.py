"""Workflow graph nodes/edges aligned with crew selection (same rules as builder)."""

from __future__ import annotations

from typing import Any

from app.crews.bug_hunt.config_loader import get_display_names
from app.crews.bug_hunt.selection import select_agent_names

_AGENT_NODE_TYPE: dict[str, str] = {
    "recon": "agent",
    "crawler": "agent",
    "vuln_scanner": "agent",
    "fuzzer": "agent",
    "web_search": "agent",
    "exploit_analyst": "analyst",
    "privesc": "agent",
    "tunnel_pivot": "agent",
    "post_exploit": "agent",
    "report_writer": "report",
}


def _edge(fr: str, to: str, kind: str = "context") -> dict[str, str]:
    return {"from": fr, "to": to, "type": kind}


def build_topology_for_hunt(
    target: str,
    objective: str = "comprehensive",
    ssh_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return nodes and edges for the given hunt parameters."""
    _, selected = select_agent_names(target, objective, ssh_config)
    agent_set = set(selected)
    display = get_display_names()

    nodes: list[dict[str, str]] = [
        {"id": "orchestrator", "label": "Orchestrator", "type": "orchestrator"},
    ]
    for aid in selected:
        nodes.append({
            "id": aid,
            "label": display.get(aid, aid.replace("_", " ").title()),
            "type": _AGENT_NODE_TYPE.get(aid, "agent"),
        })

    edges: list[dict[str, str]] = []

    if "recon" in agent_set:
        edges.append(_edge("orchestrator", "recon", "task"))
    if "fuzzer" in agent_set:
        edges.append(_edge("orchestrator", "fuzzer", "task"))

    if "crawler" in agent_set:
        edges.append(_edge("recon", "crawler", "context"))
        if "fuzzer" in agent_set:
            edges.append(_edge("fuzzer", "crawler", "context"))

    if "vuln_scanner" in agent_set:
        edges.append(_edge("recon", "vuln_scanner", "context"))

    if "web_search" in agent_set:
        edges.append(_edge("recon", "web_search", "context"))
        if "vuln_scanner" in agent_set:
            edges.append(_edge("vuln_scanner", "web_search", "context"))

    if "exploit_analyst" in agent_set:
        edges.append(_edge("recon", "exploit_analyst", "context"))
        if "fuzzer" in agent_set:
            edges.append(_edge("fuzzer", "exploit_analyst", "context"))
        if "crawler" in agent_set:
            edges.append(_edge("crawler", "exploit_analyst", "context"))
        if "vuln_scanner" in agent_set:
            edges.append(_edge("vuln_scanner", "exploit_analyst", "context"))
        if "web_search" in agent_set:
            edges.append(_edge("web_search", "exploit_analyst", "context"))

    if "privesc" in agent_set and "exploit_analyst" in agent_set:
        edges.append(_edge("exploit_analyst", "privesc", "context"))
    elif "privesc" in agent_set:
        edges.append(_edge("recon", "privesc", "context"))

    if "tunnel_pivot" in agent_set:
        if "privesc" in agent_set:
            edges.append(_edge("privesc", "tunnel_pivot", "context"))
        edges.append(_edge("recon", "tunnel_pivot", "context"))

    if "post_exploit" in agent_set:
        if "tunnel_pivot" in agent_set:
            edges.append(_edge("tunnel_pivot", "post_exploit", "context"))
        elif "privesc" in agent_set:
            edges.append(_edge("privesc", "post_exploit", "context"))

    if "report_writer" in agent_set:
        if "exploit_analyst" in agent_set:
            edges.append(_edge("exploit_analyst", "report_writer", "context"))
        if "post_exploit" in agent_set:
            edges.append(_edge("post_exploit", "report_writer", "context"))
        elif "exploit_analyst" not in agent_set and "recon" in agent_set:
            edges.append(_edge("recon", "report_writer", "context"))

    return {"nodes": nodes, "edges": edges}


def get_graph_topology(
    target: str | None = None,
    objective: str = "comprehensive",
    ssh_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Graph for API defaults or a specific hunt configuration.

    When ``target`` is None, uses a representative web target so the full web pipeline is shown.
    """
    t = target if target else "https://example.com"
    return build_topology_for_hunt(t, objective=objective, ssh_config=ssh_config)
