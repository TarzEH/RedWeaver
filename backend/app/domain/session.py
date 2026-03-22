"""Session entity — a red team engagement containing multiple hunts against multiple targets."""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from app.domain.base import BaseEntity


class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Session(BaseEntity):
    name: str
    description: str = ""
    workspace_id: str = ""
    created_by: str = ""
    status: SessionStatus = SessionStatus.ACTIVE
    target_ids: list[str] = Field(default_factory=list)
    hunt_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
