"""Observability bridge for the LangGraph/deepagents hunt engine.

The LangGraph twin of CrewAIEventBridge: instead of CrewAI step/task callbacks,
nodes call ``on_agent_start`` / ``on_agent_output`` / ``on_agent_complete``
explicitly. It emits the *same* SSE events and HuntflowTree nodes as the CrewAI
bridge — and reuses the same finding/attack-chain/report extraction helpers — so
the "behind the scenes" UI and persisted findings are identical across engines.

Tool-level events (tool_call/tool_result + ToolExecution rows) are emitted
authoritatively by the LangChain tool adapter, exactly like the CrewAI path, so
this bridge only handles agent- and finding-level events.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable

from redweaver_engine.crews.bug_hunt.callbacks import (
    _extract_findings_from_output,
    _extract_list_field,
    _extract_report_markdown,
)
from redweaver_engine.crews.bug_hunt.config_loader import get_display_names
from redweaver_engine.huntflow_types import HuntflowNodeType, HuntflowTree
from redweaver_engine.tools.instrumentation import set_active_agent

logger = logging.getLogger(__name__)


class LangGraphHuntBridge:
    """Maps deepagents/LangGraph node lifecycle to RedWeaver events + HuntflowTree."""

    def __init__(
        self,
        tree: HuntflowTree,
        event_callback: Callable[[str, dict[str, Any]], None],
        run_id: str | None = None,
    ) -> None:
        self._tree = tree
        self._callback = event_callback
        self._run_id = run_id
        self._lock = threading.Lock()
        self._agent_node_ids: dict[str, str] = {}
        self._active_agents: set[str] = set()
        self._completed_agents: list[str] = []
        self._all_findings: list[dict[str, Any]] = []
        self._report_markdown: str = ""

    # ------------------------------------------------------------------ start
    def on_agent_start(self, agent_name: str) -> None:
        display = get_display_names().get(agent_name, agent_name.replace("_", " ").title())
        with self._lock:
            set_active_agent(agent_name)
            if agent_name in self._active_agents:
                return
            self._active_agents.add(agent_name)
            node = self._tree.add_node(
                parent_id=self._tree.root_id,
                node_type=HuntflowNodeType.AGENT_TASK,
                agent_name=agent_name,
                content=f"{display} started",
            )
            self._agent_node_ids[agent_name] = node.id
            self._emit_node_added(node)
            self._callback("agent_start", {"agent": agent_name, "agent_name": display})
            self._callback("graph_state", {
                "current_node": agent_name, "action": "start",
                "active_nodes": sorted(self._active_agents),
                "completed_nodes": list(self._completed_agents),
            })

    # ------------------------------------------------------------------ output
    def on_agent_output(self, agent_name: str, output: Any) -> None:
        """Extract + emit findings, attack chains, false positives, report md."""
        findings = _extract_findings_from_output(output, agent_name)
        with self._lock:
            if findings:
                self._all_findings.extend(findings)
                parent_id = self._agent_node_ids.get(agent_name, self._tree.root_id)
                for finding in findings:
                    f_node = self._tree.add_node(
                        parent_id=parent_id,
                        node_type=HuntflowNodeType.FINDING,
                        agent_name=agent_name,
                        content=f"[{finding.get('severity', 'info').upper()}] {finding.get('title', '')}",
                        metadata=finding,
                    )
                    self._tree.complete_node(f_node.id)
                    self._emit_node_added(f_node)
                    self._callback("finding", finding)

            for ch in _extract_list_field(output, "attack_chains"):
                if hasattr(ch, "model_dump"):
                    ch = ch.model_dump()
                if isinstance(ch, dict) and ch.get("name"):
                    self._callback("attack_chain", {
                        "name": ch.get("name"),
                        "steps": ch.get("steps") or [],
                        "severity": ch.get("severity") or "high",
                        "description": ch.get("description") or "",
                    })
            fps = [f for f in _extract_list_field(output, "false_positives") if isinstance(f, str)]
            if fps:
                self._callback("false_positives", {"titles": fps})

            md = _extract_report_markdown(output)
            if md and len(md) > len(self._report_markdown):
                self._report_markdown = md

    # ------------------------------------------------------------------ complete
    def on_agent_complete(self, agent_name: str, findings_count: int | None = None) -> None:
        display = get_display_names().get(agent_name, agent_name.replace("_", " ").title())
        with self._lock:
            self._active_agents.discard(agent_name)
            if agent_name not in self._completed_agents:
                self._completed_agents.append(agent_name)
            node_id = self._agent_node_ids.get(agent_name)
            if node_id:
                self._tree.complete_node(node_id)
                node = self._tree.get_node(node_id)
                if node:
                    self._emit_node_completed(node)
            n = findings_count if findings_count is not None else 0
            self._callback("agent_complete", {
                "agent": agent_name, "agent_name": display,
                "summary": f"{display} completed ({n} findings)",
            })
            self._callback("graph_state", {
                "completed_node": agent_name, "action": "end",
                "active_nodes": sorted(self._active_agents),
                "completed_nodes": list(self._completed_agents),
            })

    def on_agent_error(self, agent_name: str, exc: Exception) -> None:
        logger.warning("graph node %s failed: %s", agent_name, exc)
        self.on_agent_complete(agent_name, 0)

    # ------------------------------------------------------------------ emit
    def _emit_node_added(self, node: Any) -> None:
        self._callback("huntflow_node_added", {
            "id": node.id, "parent_id": node.parent_id,
            "node_type": node.node_type.value if hasattr(node.node_type, "value") else node.node_type,
            "agent_name": node.agent_name, "content": node.content,
            "timestamp": node.timestamp, "metadata": node.metadata,
        })

    def _emit_node_completed(self, node: Any) -> None:
        self._callback("huntflow_node_completed", {
            "id": node.id, "completed_at": node.completed_at, "duration_ms": node.duration_ms,
        })

    @property
    def completed_agents(self) -> list[str]:
        return list(self._completed_agents)

    @property
    def report_markdown(self) -> str:
        return self._report_markdown

    @property
    def findings(self) -> list[dict[str, Any]]:
        return list(self._all_findings)
