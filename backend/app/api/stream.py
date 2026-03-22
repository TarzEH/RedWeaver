"""SSE streaming endpoint for real-time hunt updates."""
import asyncio
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.event_bus import event_bus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/runs/{run_id}/stream")
async def stream_run(run_id: str):
    """Server-Sent Events stream for real-time hunt updates.

    Events:
        agent_start, agent_thinking, tool_call, tool_result,
        agent_complete, finding, graph_state, hunt_complete, hunt_error,
        agent_handoff, huntflow_node_added, huntflow_node_completed,
        subagent_spawn, todo_update, pt_report_ready
    """

    async def event_generator():
        queue = await event_bus.subscribe(run_id)
        event_count = 0
        logger.debug("Stream connected for run %s...", run_id[:8])
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    event_count += 1
                    event_type = event.get("type", "")

                    # Log non-noisy events
                    if event_type != "agent_thinking" and event_count <= 200:
                        logger.debug("Sending #%d: %s (run=%s...)", event_count, event_type, run_id[:8])

                    # Send as default "message" event with {type, data} payload
                    payload = json.dumps(event, default=str)
                    yield f"data: {payload}\n\n"

                    if event_type in ("hunt_complete", "hunt_error"):
                        logger.debug("Terminal event: %s (total=%d, run=%s...)", event_type, event_count, run_id[:8])
                        break
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield f": heartbeat\n\n"
        finally:
            logger.debug("Stream disconnected for run %s... (sent %d events)", run_id[:8], event_count)
            event_bus.unsubscribe(run_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
