"""Hunt engine selection (CrewAI default; deepagents behind a flag)."""
from __future__ import annotations

from django.conf import settings

from .base import EventCallback, HuntEngine, HuntResult, NoLLMKeyError


def get_hunt_engine(name: str | None = None) -> HuntEngine:
    """Return the configured hunt engine.

    Resolution: explicit ``name`` arg → ``settings.HUNT_ENGINE`` → "crewai".
    """
    name = (name or getattr(settings, "HUNT_ENGINE", "crewai") or "crewai").lower()
    if name == "deepagents":
        from .deepagents_engine import DeepAgentsEngine

        return DeepAgentsEngine()
    from .crewai_engine import CrewAIEngine

    return CrewAIEngine()


__all__ = [
    "get_hunt_engine",
    "HuntEngine",
    "HuntResult",
    "NoLLMKeyError",
    "EventCallback",
]
