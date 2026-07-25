"""Translate engine events + tool executions into normalized DB rows.

These run inside the Celery worker (sync). They are the bridge between the
unchanged CrewAIEventBridge event stream and the observability tables.

The two decision helpers at the top of this module — :func:`tool_status` and
:func:`chain_step_matches` — are pure and carry logic that is security-relevant
(an audit status; what evidence gets attached to an attack chain). They are unit
tested without a database, so this module must import without Django: every
Django/ORM import below is made lazily inside the function that needs it.
"""
import logging

from .confidence import derive_confidence

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

# Adapter status vocabulary -> ToolStatus. "blocked" is the scope/SSRF guard
# refusing a target before the tool ran; it must survive as its own value.
_TOOL_STATUS = {
    "success": "success", "completed": "success", "ok": "success",
    "error": "error", "failed": "error",
    "timeout": "timeout", "unavailable": "unavailable",
    "blocked": "blocked",
    "running": "running",
}


def tool_status(raw) -> str:
    """Map an adapter status onto a :class:`ToolStatus` value.

    Anything unrecognised becomes ``error``, never ``success``: this row is an
    audit record, and a status we cannot interpret is not evidence that the tool
    succeeded. The old ``success`` default is what recorded every guard-blocked
    call — the one proof the SSRF guard fired — as a clean success.
    """
    # Anything non-str (a missing key, or a payload defect) is unrecognisable by
    # construction — and must not reach dict.get(), which raises on unhashables.
    key = raw.strip().lower() if isinstance(raw, str) else None
    mapped = _TOOL_STATUS.get(key)
    if mapped is None:
        logger.warning(
            "unrecognised tool status %r; recording as 'error'", raw
        )
        return "error"
    return mapped


# A chain step shorter than this is a bare category noun ("ssh", "xss", "port")
# once normalization has stripped its digits — matching on it attaches every
# finding in that category to the chain. ~12 chars is about three real words,
# enough for a step to name one specific finding rather than a class of them.
_MIN_CHAIN_STEP_CHARS = 12


def chain_step_matches(step: str, title: str, normalize=None) -> bool:
    """True when an attack-chain step and a finding title denote the same thing.

    Both sides are normalized the same way the finding dedup keys are, then
    compared by containment in either direction — the analyst may write a step
    that quotes the title, or a title that quotes the step. Either side falling
    under the length floor is treated as too generic to link on.
    """
    norm = normalize or _norm_title
    s, t = norm(step or ""), norm(title or "")
    if len(s) < _MIN_CHAIN_STEP_CHARS or len(t) < _MIN_CHAIN_STEP_CHARS:
        return False
    return s in t or t in s


def _norm_title(value: str) -> str:
    """Reuse the Finding normalizer so chain links and dedup agree on wording."""
    from apps.findings.models import Finding

    return Finding._norm_title(value)


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
        if event_type == "attack_chain":
            _attack_chain(run, data)
        if event_type == "false_positives":
            _false_positives(run, data)
    except Exception:
        logger.exception("record_event failed: %s", event_type)


def _attack_chain(run, data) -> None:
    from apps.findings.models import AttackChain, Finding

    name = (data.get("name") or "").strip()
    if not name:
        return
    ch = AttackChain.objects.create(
        run=run,
        name=name[:256],
        description=(data.get("description") or "")[:4000],
        severity=(data.get("severity") or "high").lower(),
        steps=data.get("steps") or [],
    )
    # Link findings a chain step actually names (best-effort). Normalized on
    # both sides and floored in length, so a step like "ssh" no longer drags in
    # every finding whose title happens to mention it.
    steps = [
        s
        for s in (data.get("steps") or [])
        # Normalization only ever shortens, so the raw length is a sound (and
        # free) pre-filter for the floor enforced inside chain_step_matches.
        if isinstance(s, str) and len(s) >= _MIN_CHAIN_STEP_CHARS
    ]
    if steps:
        matched = [
            f
            for f in Finding.objects.filter(run=run).only("id", "title")
            if any(chain_step_matches(s, f.title) for s in steps)
        ]
        if matched:
            ch.findings.add(*matched)


def _false_positives(run, data) -> None:
    from apps.findings.models import Finding, FindingStatus

    for title in data.get("titles") or []:
        if not isinstance(title, str) or not title.strip():
            continue
        Finding.objects.filter(run=run, title__iexact=title.strip()).update(
            status=FindingStatus.FALSE_POSITIVE
        )


def _agent_step(run, event_type, data, seq) -> None:
    from .models import AgentStep, AgentTransition

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
    from .models import GraphSnapshot

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
    from apps.findings.models import Finding
    from apps.findings.noise import downgrade_expected_noise

    # Truthfully rank bare expected-port observations as informational before persist.
    data = downgrade_expected_noise(data)
    title = data.get("title") or "Untitled"
    affected = data.get("affected_url") or data.get("url") or ""
    severity = (data.get("severity") or "info").lower()
    # Best-effort EPSS enrichment (feeds confidence + real-world prioritization).
    if data.get("cve_ids") and data.get("epss_score") is None:
        try:
            from apps.findings.enrichment import max_epss
            epss = max_epss(data.get("cve_ids") or [])
            if epss is not None:
                data["epss_score"] = epss
        except Exception:
            pass
    # Reuse the id the engine already stamped on the published event. The UI
    # merges the live event stream with this table keyed on id; minting a fresh
    # uuid here put the two in different id spaces, so every finding rendered
    # twice and a refuted one came back through its stream twin.
    # Passed as **kwargs, not id=None — an explicit None would override the
    # model's uuid4 default instead of falling back to it.
    incoming_id = _incoming_uuid(data.get("id"))
    id_kwarg = {"id": incoming_id} if incoming_id else {}

    f = Finding(
        **id_kwarg,
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
        epss_score=data.get("epss_score"),
        exploitability=(data.get("exploitability") or "unknown").lower(),
        confidence=derive_confidence(data),
    )
    f.dedup_key = f.compute_dedup_key()
    # Dedup within a run.
    if Finding.objects.filter(run=run, dedup_key=f.dedup_key).exists():
        return
    f.save()


def _incoming_uuid(value):
    """Return the event's id as a UUID, or None to let the model mint one.

    The engine supplies a uuid4 string; anything unparseable falls back to the
    model default rather than failing the write — losing a finding is far worse
    than losing the id correlation for one row.
    """
    import uuid

    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        logger.debug("finding event carried a non-UUID id %r; generating one", value)
        return None


def _huntflow_added(run, data, seq) -> None:
    from .models import HuntflowNode

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
    from django.utils import timezone

    from .models import HuntflowNode

    HuntflowNode.objects.filter(run=run, node_id=data.get("id")).update(
        completed_at=timezone.now(), duration_ms=data.get("duration_ms")
    )


def _screenshot(run, data) -> None:
    from .models import Screenshot

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
        from django.db import transaction
        from django.db.models import Max
        from django.utils import timezone

        from apps.hunts.models import Run

        from .models import ToolExecution
        # Allocate the per-run sequence under a row lock so concurrent (async)
        # tool calls can't collide on the same ToolExecution.sequence.
        with transaction.atomic():
            Run.objects.select_for_update().filter(id=run_id).first()
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
            status=tool_status(payload.get("status")),
            error=payload.get("error") or "",
            duration_ms=payload.get("duration_ms"),
            started_at=timezone.now(),
            finished_at=timezone.now(),
        )
        return str(te.id)
    except Exception:
        logger.exception("tool_recorder failed")
        return None
