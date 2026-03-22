"""Workspace DTOs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    name: str
    description: str = ""


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    description: str
    owner_id: str
    member_ids: list[str] = Field(default_factory=list)
    created_at: str
