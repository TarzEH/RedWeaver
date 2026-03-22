"""Correlation ID middleware.

Injects a unique correlation ID into every request for log tracing.
If the client sends X-Correlation-ID, it's reused; otherwise a new one is generated.
"""

from __future__ import annotations

import time
import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.logging_config import correlation_id_var, new_correlation_id

logger = logging.getLogger(__name__)


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Extract or generate correlation ID
        cid = request.headers.get("X-Correlation-ID") or new_correlation_id()
        correlation_id_var.set(cid)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 1)

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = cid

        # Log request (skip health checks and SSE streams)
        path = request.url.path
        if path != "/health" and not path.endswith("/stream"):
            logger.info(
                "%s %s -> %d (%.1fms)",
                request.method, path, response.status_code, duration_ms,
                extra={"status_code": response.status_code, "method": request.method, "path": path, "duration_ms": duration_ms},
            )

        return response
