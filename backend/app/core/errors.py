"""Typed error hierarchy for structured error handling.

All service/domain errors should raise these instead of generic exceptions.
The error_handler middleware catches them and returns structured JSON responses.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application error with HTTP status code and structured details."""

    status_code: int = 500
    error_type: str = "internal_error"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = 404
    error_type = "not_found"


class AuthError(AppError):
    status_code = 401
    error_type = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    error_type = "forbidden"


class ValidationError(AppError):
    status_code = 422
    error_type = "validation_error"


class ConflictError(AppError):
    status_code = 409
    error_type = "conflict"


class RateLimitError(AppError):
    status_code = 429
    error_type = "rate_limit"


class ServiceUnavailableError(AppError):
    status_code = 503
    error_type = "service_unavailable"
