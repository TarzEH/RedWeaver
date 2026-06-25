"""Hunt engine selection (CrewAI default; deepagents behind a flag)."""
from __future__ import annotations

from django.conf import settings

from .base import EventCallback, HuntEngine, HuntResult, NoLLMKeyError


def get_hunt_engine(name: str | None = None) -> HuntEngine:
    """Return the configured hunt engine.

    CrewAI was removed (it required langchain <0.4, incompatible with deepagents'
    langchain 1.x — see docs/refactor-deepagents-ragas.md), so deepagents is the
    only engine. ``HUNT_ENGINE`` is honored for forward-compat but only
    ``deepagents`` is implemented.
    """
    name = (name or getattr(settings, "HUNT_ENGINE", "deepagents") or "deepagents").lower()
    if name not in ("deepagents", ""):
        import logging
        logging.getLogger(__name__).warning(
            "HUNT_ENGINE=%s is not available; using deepagents", name
        )
    from .deepagents_engine import DeepAgentsEngine

    return DeepAgentsEngine()


__all__ = [
    "get_hunt_engine",
    "HuntEngine",
    "HuntResult",
    "NoLLMKeyError",
    "EventCallback",
]
