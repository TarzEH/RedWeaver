"""Instrumentation seam: run-context + raw tool capture + pluggable sinks.

This module lives in the engine on purpose — it has NO Django imports — so that
``BaseCLITool`` and ``CrewAIToolAdapter`` can record raw output and emit events
without coupling to the web framework. At startup the Django side registers the
real recorder/publisher via :func:`set_tool_recorder` / :func:`set_event_publisher`.
Until then (and in standalone/engine tests) every hook is a safe no-op.
"""
from __future__ import annotations

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# ---------------------------------------------------------------------------
# Run context — which run / agent is currently driving a tool call.
# contextvars propagate within the same thread/coroutine, which is exactly the
# CrewAI step_callback -> tool-call path.
# ---------------------------------------------------------------------------
_run_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "rw_run_id", default=None
)
_agent: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "rw_agent", default=None
)


def set_run_context(run_id: Optional[str], agent: Optional[str] = None):
    """Set the active run/agent; returns reset tokens."""
    return _run_id.set(run_id), _agent.set(agent)


def set_active_agent(agent: Optional[str]):
    """Update only the active agent (called as agents hand off)."""
    return _agent.set(agent)


def get_run_context() -> tuple[Optional[str], Optional[str]]:
    return _run_id.get(), _agent.get()


@contextmanager
def run_context(run_id: Optional[str], agent: Optional[str] = None):
    t1 = _run_id.set(run_id)
    t2 = _agent.set(agent)
    try:
        yield
    finally:
        _run_id.reset(t1)
        _agent.reset(t2)


# ---------------------------------------------------------------------------
# Raw CLI capture stash — BaseCLITool computes argv/stdout/stderr/exit_code
# (otherwise discarded) and stashes them here; the adapter pops them and writes
# the persisted ToolExecution row.
# ---------------------------------------------------------------------------
@dataclass
class CLIRaw:
    command: str = ""
    argv: list = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    cwd: str = "/tmp"


_cli_raw: contextvars.ContextVar[Optional[CLIRaw]] = contextvars.ContextVar(
    "rw_cli_raw", default=None
)


def stash_cli_raw(raw: CLIRaw) -> None:
    _cli_raw.set(raw)


def pop_cli_raw() -> Optional[CLIRaw]:
    """Return and clear the last stashed CLI raw artifacts (None if absent)."""
    raw = _cli_raw.get()
    _cli_raw.set(None)
    return raw


# ---------------------------------------------------------------------------
# Pluggable sinks. Django registers real implementations; defaults are no-ops
# so the engine stays importable and testable without a database.
# ---------------------------------------------------------------------------
ToolRecorder = Callable[[dict], Any]  # receives a tool-execution payload dict
EventPublisher = Callable[..., Any]   # publish(run_id, event_type, data, agent=)

_tool_recorder: Optional[ToolRecorder] = None
_event_publisher: Optional[EventPublisher] = None


def set_tool_recorder(fn: Optional[ToolRecorder]) -> None:
    global _tool_recorder
    _tool_recorder = fn


def set_event_publisher(fn: Optional[EventPublisher]) -> None:
    global _event_publisher
    _event_publisher = fn


def record_tool_execution(payload: dict) -> Any:
    """Persist a tool execution (no-op until Django registers a recorder)."""
    if _tool_recorder is None:
        return None
    try:
        return _tool_recorder(payload)
    except Exception:  # never let instrumentation crash a hunt
        return None


def publish_event(
    run_id: Optional[str], event_type: str, data: Optional[dict] = None, agent: Optional[str] = None
) -> Any:
    """Emit a live event (no-op until Django registers a publisher)."""
    if _event_publisher is None:
        return None
    try:
        return _event_publisher(run_id, event_type, data or {}, agent=agent)
    except Exception:
        return None
