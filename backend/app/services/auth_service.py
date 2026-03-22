"""Authentication service — register, login, token management."""

from __future__ import annotations

import logging

from app.core.errors import AuthError, ConflictError, ValidationError
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, verify_token,
)
from app.domain.user import User, UserRole
from app.dto.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.repositories.redis_user_repository import RedisUserRepository

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, user_repo: RedisUserRepository) -> None:
        self._repo = user_repo

    def register(self, dto: RegisterRequest) -> tuple[UserResponse, TokenResponse]:
        """Register a new user. Returns (user, tokens)."""
        # Check uniqueness
        if self._repo.get_by_email(dto.email):
            raise ConflictError("Email already registered")
        if self._repo.get_by_username(dto.username):
            raise ConflictError("Username already taken")

        if len(dto.password) < 6:
            raise ValidationError("Password must be at least 6 characters")

        user = User(
            email=dto.email.lower().strip(),
            username=dto.username.strip(),
            hashed_password=hash_password(dto.password),
            role=UserRole.OPERATOR,
        )
        self._repo.create(user)
        logger.info("User registered: %s (%s)", user.username, user.id[:8])

        tokens = self._create_tokens(user)
        return self._to_response(user), tokens

    def login(self, dto: LoginRequest) -> tuple[UserResponse, TokenResponse]:
        """Authenticate user. Returns (user, tokens)."""
        user = self._repo.get_by_email(dto.email.lower().strip())
        if not user:
            raise AuthError("Invalid email or password")
        if not user.is_active:
            raise AuthError("Account is disabled")
        if not verify_password(dto.password, user.hashed_password):
            raise AuthError("Invalid email or password")

        logger.info("User logged in: %s", user.username)
        tokens = self._create_tokens(user)
        return self._to_response(user), tokens

    def refresh_token(self, refresh_token: str) -> TokenResponse:
        """Refresh an access token."""
        payload = verify_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise AuthError("Invalid refresh token")

        user_id = payload.get("sub")
        if not user_id:
            raise AuthError("Invalid token payload")

        user = self._repo.get(user_id)
        if not user or not user.is_active:
            raise AuthError("User not found or disabled")

        return self._create_tokens(user)

    def get_current_user(self, token: str) -> User:
        """Validate token and return the user."""
        payload = verify_token(token)
        if not payload:
            raise AuthError("Invalid or expired token")

        user_id = payload.get("sub")
        if not user_id:
            raise AuthError("Invalid token payload")

        user = self._repo.get(user_id)
        if not user:
            raise AuthError("User not found")
        if not user.is_active:
            raise AuthError("Account is disabled")

        return user

    def _create_tokens(self, user: User) -> TokenResponse:
        data = {"sub": user.id, "email": user.email, "role": user.role.value}
        return TokenResponse(
            access_token=create_access_token(data),
            refresh_token=create_refresh_token(data),
        )

    @staticmethod
    def _to_response(user: User) -> UserResponse:
        return UserResponse(
            id=user.id, email=user.email, username=user.username,
            role=user.role, is_active=user.is_active,
            workspace_ids=user.workspace_ids,
        )
