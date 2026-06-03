"""Event publisher: persist EventLog (ordered) + broadcast over Channels.

Replaces the legacy in-memory EventBus. Safe to call from Celery/CrewAI worker
threads (sync). The engine calls this via instrumentation.publish_event after
``register_engine_sinks()`` wires it up at app start.
"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.hunts.models import Run

from .models import EventLog

logger = logging.getLogger(__name__)


def _persist(run_id, event_type, data, agent) -> int:
    """Allocate a gap-free per-run sequence and persist the EventLog row."""
    with transaction.atomic():
        Run.objects.select_for_update().filter(id=run_id).first()
        last = (
            EventLog.objects.filter(run_id=run_id)
            .aggregate(m=Max("sequence"))
            .get("m")
            or 0
        )
        seq = last + 1
        EventLog.objects.create(
            run_id=run_id,
            sequence=seq,
            event_type=event_type,
            agent_name=(agent or data.get("agent") or ""),
            timestamp=timezone.now(),
            payload=data,
        )
    return seq


def publish(run_id, event_type, data=None, agent=None) -> int | None:
    """Persist + broadcast one event. Returns its sequence (or None on failure)."""
    data = data or {}
    seq = None
    try:
        seq = _persist(run_id, event_type, data, agent)
    except Exception:
        logger.exception("EventLog persist failed for run=%s type=%s", run_id, event_type)

    try:
        layer = get_channel_layer()
        if layer is not None:
            envelope = {
                "type": event_type,
                "run_id": str(run_id),
                "seq": seq,
                "ts": timezone.now().isoformat(),
                "agent": agent or data.get("agent"),
                "replay": False,
                "data": data,
            }
            async_to_sync(layer.group_send)(
                f"run_{run_id}", {"type": "run.event", "envelope": envelope}
            )
    except Exception:
        logger.exception("Channels group_send failed for run=%s", run_id)

    return seq


def record_and_publish(run_id, event_type, data=None, agent=None) -> int | None:
    """Persist EventLog + broadcast AND write normalized rows.

    Registered as the engine event publisher so adapter/screenshot events
    (which bypass the CrewAIEventBridge callback) still produce AgentStep /
    Screenshot / etc. rows — not just EventLog entries.
    """
    seq = publish(run_id, event_type, data, agent)
    try:
        from apps.hunts.models import Run

        from . import recorders

        run = Run.objects.filter(id=run_id).first()
        if run is not None:
            recorders.record_event(run, event_type, data or {}, seq or 0)
    except Exception:
        logger.exception("record_and_publish recorder failed for %s", event_type)
    return seq


# --- legacy compatibility shims -------------------------------------------- #
def publish_event(run_id, event: dict) -> int | None:
    return publish(run_id, event.get("type"), event.get("data") or {})


def publish_sync(run_id, event: dict) -> int | None:
    return publish_event(run_id, event)
