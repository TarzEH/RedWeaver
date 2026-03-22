"""Session DTOs."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.session import SessionStatus


class SessionCreate(BaseModel):
    name: str
    description: str = ""
    workspace_id: str
    tags: list[str] = Field(default_factory=list)


class SessionResponse(BaseModel):
    id: str
    name: str
    description: str
    workspace_id: str
    status: SessionStatus
    target_count: int = 0
    hunt_count: int = 0
    finding_count: int = 0
    tags: list[str] = Field(default_factory=list)
    created_at: str


class SessionDetail(SessionResponse):
    target_ids: list[str] = Field(default_factory=list)
    hunt_ids: list[str] = Field(default_factory=list)
