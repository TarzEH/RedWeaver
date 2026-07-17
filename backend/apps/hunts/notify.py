"""Fire outbound notifications (webhook / Slack) on run events. Best-effort."""
from __future__ import annotations

import logging

from django.db.models import Q

logger = logging.getLogger(__name__)


def _channels_for(run):
    from .models import NotificationChannel

    qs = NotificationChannel.objects.filter(enabled=True)
    cond = Q()
    if run.created_by_id:
        cond |= Q(created_by_id=run.created_by_id)
    if run.workspace_id:
        cond |= Q(workspace_id=run.workspace_id)
    return qs.filter(cond) if cond else qs.none()


def notify_run_complete(run, findings_count: int, severity_counts: dict | None = None) -> None:
    """POST a run-complete summary to each subscribed channel (never raises)."""
    try:
        import httpx
    except Exception:
        return
    target = run.target or ""
    text = (
        f"✅ RedWeaver hunt complete — {target}\n"
        f"{findings_count} findings"
        + (f" · {severity_counts}" if severity_counts else "")
    )
    payload = {
        "event": "hunt_complete",
        "run_id": str(run.id),
        "target": target,
        "status": run.status,
        "findings_count": findings_count,
        "severity_counts": severity_counts or {},
        "cost_usd": float(run.cost_usd or 0),
    }
    for ch in _channels_for(run):
        if ch.events and "hunt_complete" not in ch.events:
            continue
        body = {"text": text} if ch.kind == "slack" else payload
        try:
            httpx.post(ch.url, json=body, timeout=8.0)
        except Exception as exc:  # noqa: BLE001
            logger.debug("notification to %s failed: %s", ch.id, exc)
