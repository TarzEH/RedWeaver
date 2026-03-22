"""Global error handler middleware.

Catches AppError subclasses and returns structured JSON responses.
Unhandled exceptions get a generic 500 with correlation ID for debugging.
"""

from __future__ import annotations

import logging
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.errors import AppError
from app.core.logging_config import correlation_id_var

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except AppError as e:
            logger.warning(
                "AppError: %s %s -> %d %s",
                request.method, request.url.path,
                e.status_code, e.message,
            )
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": e.error_type,
                    "message": e.message,
                    "details": e.details,
                    "correlation_id": correlation_id_var.get(""),
                },
            )
        except Exception as e:
            cid = correlation_id_var.get("")
            logger.error(
                "Unhandled exception: %s %s -> %s",
                request.method, request.url.path, str(e),
                exc_info=True,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_error",
                    "message": "An unexpected error occurred.",
                    "correlation_id": cid,
                },
            )
