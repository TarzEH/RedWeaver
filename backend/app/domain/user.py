"""User entity with role-based access."""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from app.domain.base import BaseEntity


class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class User(BaseEntity):
    email: str
    username: str
    hashed_password: str = ""
    role: UserRole = UserRole.OPERATOR
    is_active: bool = True
    workspace_ids: list[str] = Field(default_factory=list)
