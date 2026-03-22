"""Hunt DTOs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.hunt import HuntStatus


class HuntCreate(BaseModel):
    session_id: str
    target_ids: list[str] = Field(default_factory=list)
    objective: str = "comprehensive"
    agent_selection: list[str] = Field(default_factory=list)
    timeout_seconds: int = 900
    ssh_config: dict[str, Any] | None = None


class HuntResponse(BaseModel):
    id: str
    session_id: str
    target_ids: list[str]
    status: HuntStatus
    target: str  # Primary target string for display
    objective: str
    finding_count: int = 0
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None


class HuntDetail(HuntResponse):
    messages: list[dict[str, Any]] = Field(default_factory=list)
    graph_state: dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""
