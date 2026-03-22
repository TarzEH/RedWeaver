"""CrewAI event bridge: translates CrewAI callbacks to SSE events."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from app.crews.bug_hunt.config_loader import get_display_names
from app.models.huntflow import HuntflowNodeType, HuntflowTree

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _thinking_emit_interval() -> float:
    try:
        return max(0.05, float(os.environ.get("THINKING_EMIT_INTERVAL_SEC", "0.35")))
    except ValueError:
        return 0.35


def _safe_str(obj: Any, max_len: int = 500) -> str:
    """Safely stringify an object with truncation."""
    if isinstance(obj, str):
        s = obj
    else:
        try:
            s = json.dumps(obj, default=str)
        except (TypeError, ValueError):
            s = str(obj)
    return s[:max_len] + "..." if len(s) > max_len else s


def _extract_findings_from_output(output: Any, agent_name: str) -> list[dict[str, Any]]:
    """Extract findings from a CrewAI task output."""
    findings = []
    raw = None

    if hasattr(output, "pydantic"):
        pydantic_obj = output.pydantic
        if pydantic_obj and hasattr(pydantic_obj, "findings"):
            raw = pydantic_obj.findings
    elif hasattr(output, "json_dict"):
        json_dict = output.json_dict
        if isinstance(json_dict, dict):
            raw = json_dict.get("findings", [])
    elif hasattr(output, "raw"):
        raw_str = output.raw
        if isinstance(raw_str, str):
            try:
                parsed = json.loads(raw_str)
                raw = parsed.get("findings", []) if isinstance(parsed, dict) else []
            except (json.JSONDecodeError, TypeError):
                pass
    elif hasattr(output, "findings"):
        raw = output.findings
    elif isinstance(output, dict):
        raw = output.get("findings", [])
    elif isinstance(output, str):
        try:
            parsed = json.loads(output)
            raw = parsed.get("findings", []) if isinstance(parsed, dict) else []
        except (json.JSONDecodeError, TypeError):
            pass

    if not raw:
        return []

    now = datetime.now(timezone.utc).isoformat()
    for f in raw:
        if hasattr(f, "model_dump"):
            f = f.model_dump()
        elif not isinstance(f, dict):
            continue
        findings.append({
            "id": f.get("id") or str(uuid.uuid4()),
            "title": f.get("title") or f.get("name") or "Untitled",
            "severity": (f.get("severity") or "info").lower(),
            "description": f.get("description") or "",
            "affected_url": f.get("affected_url") or f.get("url") or "",
            "evidence": f.get("evidence") or "",
            "remediation": f.get("remediation") or "",
            "agent_source": agent_name,
            "tool_used": f.get("tool_used") or f.get("tool") or "",
            "cvss_score": f.get("cvss_score"),
            "cve_ids": f.get("cve_ids") or [],
            "timestamp": f.get("timestamp") or now,
        })
    return findings


def _extract_report_markdown(output: Any) -> str:
    """Extract report_markdown from a CrewAI TaskOutput or similar."""
    if output is None:
        return ""

    if hasattr(output, "pydantic") and output.pydantic:
        p = output.pydantic
        if hasattr(p, "report_markdown"):
            s = (getattr(p, "report_markdown", None) or "").strip()
            if s:
                return s
        try:
            dumped = p.model_dump()
            if isinstance(dumped, dict):
                s = (dumped.get("report_markdown") or "").strip()
                if s:
                    return s
        except Exception:
            pass

    if hasattr(output, "json_dict") and isinstance(output.json_dict, dict):
        s = (output.json_dict.get("report_markdown") or "").strip()
        if s:
            return s

    if hasattr(output, "raw") and isinstance(output.raw, str):
        raw = output.raw.strip()
        if not raw:
            return ""
        if raw.startswith("{") or raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    s = (parsed.get("report_markdown") or "").strip()
                    if s:
                        return s
            except (json.JSONDecodeError, TypeError):
                pass
        # Model sometimes returns Markdown directly when JSON parsing fails (avoid fuzzer noise).
        if raw.startswith("#") and len(raw) > 200:
            return raw
        low = raw.lower()
        if len(raw) > 500 and any(
            phrase in low
            for phrase in (
                "penetration testing report",
                "executive summary",
                "remediation roadmap",
                "detailed findings",
                "scope and methodology",
            )
        ):
            return raw

    return ""


class CrewAIEventBridge:
    """Bridges CrewAI callbacks to the EventBus SSE system."""

    def __init__(
        self,
        tree: HuntflowTree,
        event_callback: Callable[[str, dict[str, Any]], None],
    ) -> None:
        self._tree = tree
        self._callback = event_callback
        self._agent_node_ids: dict[str, str] = {}
        self._active_agents: set[str] = set()
        self._completed_agents: list[str] = []
        self._all_findings: list[dict[str, Any]] = []
        self._report_markdown: str = ""
        self._task_agent_map: dict[str, str] = {}
        self._last_thinking_emit: dict[str, float] = {}
        self._thinking_emit_interval = _thinking_emit_interval()
        self._include_thinking_stream = _env_bool("INCLUDE_THINKING_STREAM", True)

    def step_callback(self, step_output: Any) -> None:
        try:
            agent_name = self._extract_agent_name_from_step(step_output)
            if not agent_name:
                return

            display_names = get_display_names()
            display = display_names.get(agent_name, agent_name.replace("_", " ").title())

            if agent_name not in self._active_agents:
                self._active_agents.add(agent_name)

                node = self._tree.add_node(
                    parent_id=self._tree.root_id,
                    node_type=HuntflowNodeType.AGENT_TASK,
                    agent_name=agent_name,
                    content=f"{display} started",
                )
                self._agent_node_ids[agent_name] = node.id
                self._emit_node_added(node)

                self._callback("agent_start", {
                    "agent": agent_name,
                    "agent_name": display,
                })
                self._callback("graph_state", {
                    "current_node": agent_name,
                    "action": "start",
                    "active_nodes": sorted(self._active_agents),
                    "completed_nodes": list(self._completed_agents),
                })

            self._process_tool_events(step_output, agent_name, display)

            thought = self._extract_thought(step_output)
            if thought and self._include_thinking_stream:
                now = time.monotonic()
                last = self._last_thinking_emit.get(agent_name, 0.0)
                if now - last >= self._thinking_emit_interval:
                    self._last_thinking_emit[agent_name] = now
                    self._callback("agent_thinking", {
                        "agent": agent_name,
                        "content": thought,
                        "thinking": thought,
                    })

        except Exception as e:
            logger.warning("step_callback error: %s", e)

    def task_callback(self, task_output: Any) -> None:
        try:
            agent_name = self._extract_agent_name_from_task(task_output)
            if not agent_name:
                agent_name = "unknown"

            display_names = get_display_names()
            display = display_names.get(agent_name, agent_name.replace("_", " ").title())

            findings = _extract_findings_from_output(task_output, agent_name)
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

            # Report markdown: take the longest extracted block (report_writer task;
            # parallel/async ordering can make crew-level pydantic point at a non-report task).
            md = _extract_report_markdown(task_output)
            if md and len(md) > len(self._report_markdown):
                self._report_markdown = md

            self._active_agents.discard(agent_name)
            if agent_name not in self._completed_agents:
                self._completed_agents.append(agent_name)

            node_id = self._agent_node_ids.get(agent_name)
            if node_id:
                self._tree.complete_node(node_id)
                node = self._tree.get_node(node_id)
                if node:
                    self._emit_node_completed(node)

            self._callback("agent_complete", {
                "agent": agent_name,
                "agent_name": display,
                "summary": f"{display} completed ({len(findings)} findings)",
            })
            self._callback("graph_state", {
                "completed_node": agent_name,
                "action": "end",
                "active_nodes": sorted(self._active_agents),
                "completed_nodes": list(self._completed_agents),
            })

        except Exception as e:
            logger.warning("task_callback error: %s", e)

    def register_task_agent(self, task_description: str, agent_name: str) -> None:
        self._task_agent_map[task_description[:100]] = agent_name

    def _extract_agent_name_from_step(self, step_output: Any) -> str | None:
        if hasattr(step_output, "agent") and step_output.agent:
            agent_obj = step_output.agent
            if hasattr(agent_obj, "role"):
                return self._role_to_name(agent_obj.role)
        if isinstance(step_output, dict):
            agent = step_output.get("agent", "")
            if agent:
                return self._role_to_name(str(agent))
        return None

    def _extract_agent_name_from_task(self, task_output: Any) -> str | None:
        if hasattr(task_output, "agent"):
            if hasattr(task_output.agent, "role"):
                return self._role_to_name(task_output.agent.role)
            return self._role_to_name(str(task_output.agent))
        desc = ""
        if hasattr(task_output, "description"):
            desc = str(task_output.description)[:100]
        elif hasattr(task_output, "task") and hasattr(task_output.task, "description"):
            desc = str(task_output.task.description)[:100]
        if desc and desc in self._task_agent_map:
            return self._task_agent_map[desc]
        return None

    @staticmethod
    def _role_to_name(role: str) -> str:
        role_map = {
            "Network Reconnaissance Specialist": "recon",
            "Web Application Spider": "crawler",
            "Vulnerability Scanner": "vuln_scanner",
            "Directory & Parameter Discovery Specialist": "fuzzer",
            "Security Intelligence Researcher": "web_search",
            "Vulnerability Correlation & Analysis Expert": "exploit_analyst",
            "Professional Pentest Report Writer": "report_writer",
            "Privilege Escalation Specialist": "privesc",
            "Network Pivoting & Tunneling Specialist": "tunnel_pivot",
            "Post-Exploitation & Flag Collection Specialist": "post_exploit",
        }
        if role in role_map:
            return role_map[role]
        lower = role.lower()
        for key, val in role_map.items():
            if key.lower() in lower or val in lower:
                return val
        return role.lower().replace(" ", "_")

    def _process_tool_events(self, step_output: Any, agent_name: str, display: str) -> None:
        tool_name = None
        tool_result = None

        if hasattr(step_output, "tool"):
            tool_name = step_output.tool
        elif isinstance(step_output, dict):
            tool_name = step_output.get("tool")

        if hasattr(step_output, "tool_output"):
            tool_result = step_output.tool_output
        elif isinstance(step_output, dict):
            tool_result = step_output.get("result") or step_output.get("output")

        if tool_name:
            parent_id = self._agent_node_ids.get(agent_name, self._tree.root_id)

            tool_node = self._tree.add_node(
                parent_id=parent_id,
                node_type=HuntflowNodeType.TOOL_CALL,
                agent_name=agent_name,
                content=str(tool_name),
                metadata={"tool": str(tool_name)},
            )
            self._emit_node_added(tool_node)

            self._callback("tool_call", {
                "agent": agent_name,
                "agent_name": display,
                "tool": str(tool_name),
                "input": "",
            })

            if tool_result is not None:
                result_str = _safe_str(tool_result)
                self._tree.complete_node(tool_node.id)

                result_node = self._tree.add_node(
                    parent_id=tool_node.id,
                    node_type=HuntflowNodeType.TOOL_RESULT,
                    agent_name=agent_name,
                    content=result_str[:500],
                    metadata={"tool": str(tool_name)},
                )
                self._tree.complete_node(result_node.id)
                self._emit_node_added(result_node)

                self._callback("tool_result", {
                    "agent": agent_name,
                    "agent_name": display,
                    "tool": str(tool_name),
                    "summary": result_str,
                })

    @staticmethod
    def _extract_thought(step_output: Any) -> str:
        if hasattr(step_output, "thought"):
            return str(step_output.thought)[:500]
        if hasattr(step_output, "text"):
            return str(step_output.text)[:500]
        if isinstance(step_output, dict):
            return str(step_output.get("thought", ""))[:500]
        return ""

    def _emit_node_added(self, node: Any) -> None:
        self._callback("huntflow_node_added", {
            "id": node.id,
            "parent_id": node.parent_id,
            "node_type": node.node_type.value if hasattr(node.node_type, "value") else node.node_type,
            "agent_name": node.agent_name,
            "content": node.content,
            "timestamp": node.timestamp,
            "metadata": node.metadata,
        })

    def _emit_node_completed(self, node: Any) -> None:
        self._callback("huntflow_node_completed", {
            "id": node.id,
            "completed_at": node.completed_at,
            "duration_ms": node.duration_ms,
        })

    @property
    def completed_agents(self) -> list[str]:
        return list(self._completed_agents)

    @property
    def findings(self) -> list[dict[str, Any]]:
        return list(self._all_findings)

    @property
    def report_markdown(self) -> str:
        return self._report_markdown

    @property
    def active_agents(self) -> set[str]:
        return set(self._active_agents)

    @property
    def agent_node_ids(self) -> dict[str, str]:
        return dict(self._agent_node_ids)
