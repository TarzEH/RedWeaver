"""In-memory event bus for SSE streaming.

Hunt execution runs ``crew.kickoff()`` in a thread pool; CrewAI callbacks run on
that worker thread. All delivery to ``asyncio.Queue`` must happen on the main
event loop via ``call_soon_threadsafe``. Use :meth:`publish_event` as the single
entry point — it detects the caller thread and schedules correctly while
preserving the no-subscriber buffer for late SSE clients.
"""
from __future__ import annotations

import asyncio
import functools
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


class EventBus:
    """Async in-memory pub/sub for streaming hunt events to SSE clients."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._event_count: dict[str, int] = defaultdict(int)
        self._buffer: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._buffer_max = 2000
        self._buffer_max_thinking = 400

    # ------------------------------------------------------------------
    # Loop binding
    # ------------------------------------------------------------------

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Store reference to the main event loop (call once on startup)."""
        self._loop = loop
        logger.info("Main event loop bound")

    # ------------------------------------------------------------------
    # Subscribe / unsubscribe
    # ------------------------------------------------------------------

    async def subscribe(self, run_id: str) -> asyncio.Queue:
        """Create and register a new queue for a run.

        If events were buffered before this subscriber connected,
        they are replayed into the queue immediately.
        """
        queue: asyncio.Queue = asyncio.Queue()

        buffered = self._buffer.pop(run_id, [])
        if buffered:
            logger.debug(
                "Replaying %d buffered events for run %s...",
                len(buffered),
                run_id[:8],
            )
            for event in buffered:
                queue.put_nowait(event)

        self._subscribers[run_id].append(queue)
        self._event_count[run_id] = len(buffered)
        logger.debug(
            "Subscriber added for run %s... (total: %d, buffered: %d)",
            run_id[:8],
            len(self._subscribers[run_id]),
            len(buffered),
        )
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        """Remove a queue from subscribers."""
        if run_id in self._subscribers:
            self._subscribers[run_id] = [
                q for q in self._subscribers[run_id] if q is not queue
            ]
            total_events = self._event_count.get(run_id, 0)
            if not self._subscribers[run_id]:
                del self._subscribers[run_id]
                self._event_count.pop(run_id, None)
                self._buffer.pop(run_id, None)
            logger.debug(
                "Subscriber removed for run %s... (delivered %d events)",
                run_id[:8],
                total_events,
            )

    # ------------------------------------------------------------------
    # Publish (single code path)
    # ------------------------------------------------------------------

    def _publish_to_run(self, run_id: str, event: dict[str, Any]) -> None:
        """Must run on the event loop thread only."""
        subscribers = self._subscribers.get(run_id, [])

        if not subscribers:
            self._buffer_event(run_id, event)
            return

        for queue in subscribers:
            try:
                queue.put_nowait(event)
                self._event_count[run_id] = self._event_count.get(run_id, 0) + 1
            except asyncio.QueueFull:
                logger.warning("Queue full for %s... — dropping event", run_id[:8])
            except Exception as e:
                logger.error("put_nowait error: %s", e)

    def _buffer_event(self, run_id: str, event: dict[str, Any]) -> None:
        buf = self._buffer[run_id]
        event_type = event.get("type", "")
        if event_type == "agent_thinking":
            thinking_count = sum(1 for e in buf if e.get("type") == "agent_thinking")
            if thinking_count >= self._buffer_max_thinking:
                return
        if len(buf) < self._buffer_max:
            buf.append(event)
        if event_type not in ("agent_thinking",):
            logger.debug(
                "Buffering %s for %s... (buf=%d, no subscribers)",
                event_type,
                run_id[:8],
                len(buf),
            )

    def publish_event(self, run_id: str, event: dict[str, Any]) -> None:
        """Publish to subscribers or buffer. Safe from any thread (Crew worker or loop)."""
        if self._loop is None or not self._loop.is_running():
            self._publish_to_run(run_id, event)
            return

        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None

        if running is self._loop:
            self._publish_to_run(run_id, event)
        else:
            self._loop.call_soon_threadsafe(
                functools.partial(self._publish_to_run, run_id, event)
            )

    def publish_nowait(self, run_id: str, event: dict[str, Any]) -> None:
        """Backward-compatible alias for :meth:`publish_event`."""
        self.publish_event(run_id, event)

    def publish_sync(self, run_id: str, event: dict[str, Any]) -> None:
        """Backward-compatible alias for :meth:`publish_event`."""
        self.publish_event(run_id, event)

    async def publish(self, run_id: str, event: dict[str, Any]) -> None:
        """Async publish — same semantics as :meth:`publish_event` (buffers if needed)."""
        self.publish_event(run_id, event)

    def has_subscribers(self, run_id: str) -> bool:
        return bool(self._subscribers.get(run_id))

    def subscriber_count(self, run_id: str) -> int:
        return len(self._subscribers.get(run_id, []))


# Global singleton
event_bus = EventBus()
