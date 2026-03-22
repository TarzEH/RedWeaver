"""Workspace entity — groups sessions and targets for a team or project."""

from __future__ import annotations

from pydantic import Field

from app.domain.base import BaseEntity


class Workspace(BaseEntity):
    name: str
    description: str = ""
    owner_id: str = ""
    member_ids: list[str] = Field(default_factory=list)
