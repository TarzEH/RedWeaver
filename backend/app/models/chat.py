"""Chat request/result models."""
from typing import Any

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    run_id: str | None = None
    ssh_config: dict[str, Any] | None = None


class ChatResult(BaseModel):
    reply: str
    run_id: str | None
    created_run: bool
    deferred: bool = False  # True when agent runs in background; frontend should poll run
