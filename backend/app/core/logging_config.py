"""Structured logging configuration with correlation ID support.

Sets up JSON-formatted logging with contextual fields (correlation_id, user_id, hunt_id).
Uses contextvars for async-safe context propagation.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

# Context variables for request-scoped data
correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="")
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id", default="")
hunt_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("hunt_id", default="")


def new_correlation_id() -> str:
    return str(uuid.uuid4())[:8]


class _ThirdPartyNoiseFilter(logging.Filter):
    """Drop high-churn CrewAI / OpenAI adapter lines that use the root logger."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "Successfully validated tool" in msg:
            return False
        return True


class StructuredFormatter(logging.Formatter):
    """JSON log formatter with contextual fields."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add context vars if set
        cid = correlation_id_var.get("")
        if cid:
            log_entry["correlation_id"] = cid
        uid = user_id_var.get("")
        if uid:
            log_entry["user_id"] = uid
        hid = hunt_id_var.get("")
        if hid:
            log_entry["hunt_id"] = hid

        # Add exception info
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }

        # Add extra fields
        for key in ("status_code", "method", "path", "duration_ms"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        return json.dumps(log_entry, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configure structured logging for the application."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # Add structured handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    handler.addFilter(_ThirdPartyNoiseFilter())
    root.addHandler(handler)

    # Reduce noise from third-party libraries
    for name in (
        "uvicorn.access",
        "httpx",
        "httpcore",
        "chromadb",
        "openai",
        "anthropic",
        "crewai",
        "litellm",
        "langchain",
        "langchain_core",
        "langchain_community",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)
