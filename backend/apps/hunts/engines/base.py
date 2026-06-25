"""Engine abstraction: the seam that lets RedWeaver swap orchestrators.

`execute_run` / `generate_offsec_playbook` (Celery) call a `HuntEngine` instead
of CrewAI directly, so the orchestrator (CrewAI today, deepagents/LangGraph next)
is selectable via `settings.HUNT_ENGINE` with zero change to the task bodies.

Keeping this in the Django app (not redweaver_engine) is deliberate: it
coordinates Django `Run` state + key resolution with the framework-agnostic
engine, so the engine package stays Django-free.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


class NoLLMKeyError(RuntimeError):
    """Raised by an engine when no LLM provider key/endpoint is configured."""


@dataclass
class HuntResult:
    """Normalized result of a hunt, independent of the orchestrator.

    Findings are persisted to Postgres via the observability sinks *during* the
    run (unchanged), so the caller counts them from the DB afterwards; this
    object only carries what the task body needs to finalize the Run row.
    """

    report_markdown: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    completed_agents: list[str] = field(default_factory=list)
    model: str = ""


# Event callback shape used by the Celery tasks (event_type, data) -> None.
EventCallback = Callable[[str, dict], None]


class HuntEngine(Protocol):
    """Pluggable multi-agent orchestrator for hunts + offsec playbooks."""

    name: str

    def run_hunt(
        self,
        *,
        run: Any,
        keys_provider: Any,
        callback: EventCallback,
    ) -> HuntResult:
        """Execute the full bug-hunt pipeline for ``run``.

        Persists findings/tool-executions/events via the sinks as it goes and
        returns a HuntResult. Raises ``NoLLMKeyError`` if unconfigured.
        """
        ...

    def run_offsec(
        self,
        *,
        run: Any,
        keys_provider: Any,
        findings: list[dict],
        research_md: str,
        callback: EventCallback | None = None,
    ) -> str:
        """Generate the OffSec playbook markdown from a run's findings."""
        ...
