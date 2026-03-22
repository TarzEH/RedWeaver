"""Authentication API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.deps import get_auth_service
from app.core.errors import AuthError
from app.dto.auth import LoginRequest, RegisterRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
def register(body: RegisterRequest, service: AuthService = Depends(get_auth_service)):
    user, tokens = service.register(body)
    return {"user": user.model_dump(), "tokens": tokens.model_dump()}


@router.post("/login")
def login(body: LoginRequest, service: AuthService = Depends(get_auth_service)):
    user, tokens = service.login(body)
    return {"user": user.model_dump(), "tokens": tokens.model_dump()}


@router.post("/refresh")
def refresh(body: dict, service: AuthService = Depends(get_auth_service)):
    refresh_token = body.get("refresh_token", "")
    if not refresh_token:
        raise AuthError("refresh_token is required")
    tokens = service.refresh_token(refresh_token)
    return tokens.model_dump()


@router.get("/me")
def me(request: Request, service: AuthService = Depends(get_auth_service)):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise AuthError("Authorization header required")
    token = auth_header[7:]
    user = service.get_current_user(token)
    return {
        "id": user.id, "email": user.email, "username": user.username,
        "role": user.role.value, "is_active": user.is_active,
        "workspace_ids": user.workspace_ids,
    }
