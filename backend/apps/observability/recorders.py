"""Translate engine events + tool executions into normalized DB rows.

These run inside the Celery worker (sync). They are the bridge between the
unchanged CrewAIEventBridge event stream and the observability tables.
"""
import logging

from django.db.models import Max
from django.utils import timezone

from apps.findings.models import Finding

from .confidence import derive_confidence
from .models import (
    AgentStep,
    AgentTransition,
    GraphSnapshot,
    HuntflowNode,
    Screenshot,
    ToolExecution,
)

logger = logging.getLogger(__name__)

_STEP_TYPE = {
    "agent_start": "agent_start",
    "agent_thinking": "thinking",
    "tool_call": "tool_call",
    "tool_result": "tool_result",
    "agent_complete": "agent_complete",
    "agent_handoff": "handoff",
    "finding": "finding",
}

_TOOL_STATUS = {
    "success": "success", "completed": "success", "ok": "success",
    "error": "error", "failed": "error",
    "timeout": "timeout", "unavailable": "unavailable",
}


def record_event(run, event_type: str, data: dict, seq: int) -> None:
    """Write normalized rows for a single engine event (best-effort)."""
    try:
        if event_type in _STEP_TYPE:
            _agent_step(run, event_type, data, seq)
        if event_type == "graph_state":
            _graph_snapshot(run, data, seq)
        if event_type == "finding":
            _finding(run, data)
        if event_type == "huntflow_node_added":
            _huntflow_added(run, data, seq)
        elif event_type == "huntflow_node_completed":
            _huntflow_completed(run, data)
        if event_type == "screenshot":
            _screenshot(run, data)
    except Exception:
        logger.exception("record_event failed: %s", event_type)


def _agent_step(run, event_type, data, seq) -> None:
    agent = str(data.get("agent") or data.get("agent_source") or "")
    reasoning = ""
    summary = ""
    if event_type == "agent_thinking":
        reasoning = str(data.get("content") or data.get("thinking") or "")[:8000]
    elif event_type == "tool_call":
        summary = f"{data.get('tool', '')} {data.get('input', '')}".strip()[:2000]
    elif event_type == "tool_result":
        summary = str(data.get("summary") or data.get("output") or "")[:8000]
    elif event_type == "agent_complete":
        summary = str(data.get("summary") or "")[:2000]
    elif event_type == "agent_start":
        summary = f"{agent} started"
    elif event_type == "finding":
        summary = f"[{str(data.get('severity', 'info')).upper()}] {data.get('title', '')}"
    AgentStep.objects.create(
        run=run,
        agent_name=agent,
        sequence=seq,
        step_type=_STEP_TYPE[event_type],
        from_agent=str(data.get("from") or data.get("from_display") or ""),
        to_agent=str(data.get("to") or data.get("to_display") or ""),
        reasoning_text=reasoning,
        output_summary=summary,
        confidence=(derive_confidence(data) if event_type == "finding" else None),
    )
    if event_type == "agent_handoff":
        AgentTransition.objects.create(
            run=run,
            from_agent=str(data.get("from") or data.get("from_display") or ""),
            to_agent=str(data.get("to") or data.get("to_display") or ""),
            sequence=seq,
            edge_type="handoff",
        )


def _graph_snapshot(run, data, seq) -> None:
    GraphSnapshot.objects.create(
        run=run,
        sequence=seq,
        current_node=data.get("current_node"),
        active_nodes=data.get("active_nodes") or [],
        completed_nodes=data.get("completed_nodes") or [],
        plan=data.get("plan") or [],
        nodes=data.get("nodes") or [],
        edges=data.get("edges") or [],
    )


def _finding(run, data) -> None:
    title = data.get("title") or "Untitled"
    affected = data.get("affected_url") or data.get("url") or ""
    severity = (data.get("severity") or "info").lower()
    f = Finding(
        run=run,
        session=run.session,
        target=run.target_obj,
        title=title,
        severity=severity,
        description=data.get("description") or "",
        affected_url=affected,
        evidence=data.get("evidence") or "",
        remediation=data.get("remediation") or "",
        agent_source=data.get("agent_source") or data.get("agent") or "",
        tool_used=data.get("tool_used") or data.get("tool") or "",
        cvss_score=data.get("cvss_score"),
        cve_ids=data.get("cve_ids") or [],
        cisa_kev=bool(data.get("cisa_kev")),
        exploitability=(data.get("exploitability") or "unknown").lower(),
        confidence=derive_confidence(data),
    )
    f.dedup_key = f.compute_dedup_key()
    # Dedup within a run.
    if Finding.objects.filter(run=run, dedup_key=f.dedup_key).exists():
        return
    f.save()


def _huntflow_added(run, data, seq) -> None:
    parent = None
    if data.get("parent_id"):
        parent = HuntflowNode.objects.filter(
            run=run, node_id=data["parent_id"]
        ).first()
    HuntflowNode.objects.create(
        run=run,
        node_id=data.get("id"),
        parent=parent,
        node_type=data.get("node_type") or "reasoning",
        agent_name=data.get("agent_name") or "",
        content=str(data.get("content") or "")[:8000],
        metadata=data.get("metadata") or {},
        sequence=seq,
    )


def _huntflow_completed(run, data) -> None:
    HuntflowNode.objects.filter(run=run, node_id=data.get("id")).update(
        completed_at=timezone.now(), duration_ms=data.get("duration_ms")
    )


def _screenshot(run, data) -> None:
    Screenshot.objects.create(
        run=run,
        agent_name=data.get("agent") or "",
        tool_name=data.get("tool") or "screenshot_capture",
        url=data.get("url") or "",
        final_url=data.get("final_url") or "",
        image=data.get("path") or "",  # media-relative path; file already on disk
        width=data.get("width"),
        height=data.get("height"),
        bytes=data.get("bytes"),
        page_title=(data.get("page_title") or "")[:512],
        http_status=data.get("http_status"),
    )


# --------------------------------------------------------------------------- #
# Tool execution recorder (registered with the engine instrumentation seam)
# --------------------------------------------------------------------------- #
def tool_recorder(payload: dict):
    """Create a ToolExecution row from the adapter payload; return its id."""
    run_id = payload.get("run_id")
    if not run_id:
        return None
    try:
        seq = (
            ToolExecution.objects.filter(run_id=run_id)
            .aggregate(m=Max("sequence"))
            .get("m")
            or 0
        ) + 1
        te = ToolExecution.objects.create(
            run_id=run_id,
            agent_name=payload.get("agent") or "",
            tool_name=payload.get("tool_name") or "tool",
            sequence=seq,
            argv=payload.get("argv") or [],
            command_str=payload.get("command_str") or "",
            target=payload.get("target") or "",
            scope=payload.get("scope") or "",
            options=payload.get("options") or {},
            raw_stdout=payload.get("raw_stdout") or "",
            raw_stderr=payload.get("raw_stderr") or "",
            exit_code=payload.get("exit_code"),
            parsed_result=payload.get("parsed_result"),
            truncated_for_llm=payload.get("truncated_for_llm") or "",
            status=_TOOL_STATUS.get(payload.get("status"), "success"),
            error=payload.get("error") or "",
            duration_ms=payload.get("duration_ms"),
            started_at=timezone.now(),
            finished_at=timezone.now(),
        )
        return str(te.id)
    except Exception:
        logger.exception("tool_recorder failed")
        return None
