"""Authentication DTOs."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.user import UserRole


class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    role: UserRole
    is_active: bool
    workspace_ids: list[str] = Field(default_factory=list)
