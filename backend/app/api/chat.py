"""Chat endpoint."""
import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_chat_service, get_hunt_execution_service
from app.models.chat import ChatRequest, ChatResult
from app.services.chat_service import ChatService
from app.services.hunt_execution_service import HuntExecutionService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/chat", response_model=ChatResult)
async def chat(
    body: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
    hunt_service: HuntExecutionService = Depends(get_hunt_execution_service),
):
    """Unified chat: creates/uses run and returns immediately; hunt runs as async task.

    Uses asyncio.create_task() on the main event loop instead of BackgroundTasks
    with execute_run_sync, eliminating the asyncio.run() blocking issue.
    """
    logger.info("POST /api/chat: message=%r, run_id=%s", (body.message or "")[:80], body.run_id)
    try:
        result = chat_service.chat(body)
        if getattr(result, "deferred", False) and result.run_id:
            logger.info("Deferred run: run_id=%s -> creating async task", result.run_id)
            asyncio.create_task(hunt_service.execute(result.run_id))
        else:
            logger.debug("Immediate result: run_id=%s, reply_len=%d", result.run_id, len(result.reply or ""))
        return result
    except ValueError as e:
        logger.warning("ValueError: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
