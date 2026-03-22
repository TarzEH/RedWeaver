"""Hunt entity — a single execution against one or more targets within a session."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.domain.base import BaseEntity
from app.domain.target import SSHConfig


class HuntStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class HuntConfig(BaseModel):
    """Configuration for a hunt execution."""

    objective: str = "comprehensive"
    agent_selection: list[str] = Field(default_factory=list)  # Empty = auto-select
    timeout_seconds: int = 900
    ssh_config: SSHConfig | None = None


class Hunt(BaseEntity):
    session_id: str = ""
    target_ids: list[str] = Field(default_factory=list)
    created_by: str = ""
    config: HuntConfig = Field(default_factory=HuntConfig)
    status: HuntStatus = HuntStatus.QUEUED
    started_at: str | None = None
    completed_at: str | None = None
    error_message: str = ""
    finding_ids: list[str] = Field(default_factory=list)
    graph_state: dict[str, Any] = Field(default_factory=dict)
    messages: list[dict[str, Any]] = Field(default_factory=list)

    # Backward compatibility fields (mapped from existing Run model)
    target: str = ""
    scope: str = ""
    objective: str = "comprehensive"
