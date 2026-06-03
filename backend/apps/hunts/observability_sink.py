"""The event_callback that persists normalized rows + broadcasts live events.

Replaces the legacy _RunStateTracker + EventBus wiring. One callback per run,
passed into CrewAIEventBridge; for every engine event it (1) persists an
EventLog row + broadcasts via Channels (publisher.publish) and (2) writes the
normalized observability rows (recorders.record_event).
"""
import logging
from typing import Callable

from apps.observability import recorders
from apps.observability.publisher import publish

logger = logging.getLogger(__name__)


def make_event_callback(run) -> Callable[[str, dict], None]:
    def callback(event_type: str, data: dict) -> None:
        seq = publish(str(run.id), event_type, data, agent=data.get("agent"))
        try:
            recorders.record_event(run, event_type, data, seq or 0)
        except Exception:
            logger.exception("recorder failed for %s", event_type)

    return callback
