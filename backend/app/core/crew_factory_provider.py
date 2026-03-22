"""Single source of truth for building CrewFactory (LLM, tools, embedder)."""

from __future__ import annotations

import logging
from typing import Any

from app.core.llm_factory import LLMFactory

logger = logging.getLogger(__name__)
from app.crews.bug_hunt.builder import CrewFactory
from app.repositories.api_keys_repository import ApiKeysRepositoryProtocol
from app.tools.registry import ToolRegistry


def build_embedder_config(
    llm_factory: LLMFactory,
    keys: dict[str, Any],
) -> dict[str, Any] | None:
    """Embedder config for CrewAI memory based on active LLM provider."""
    provider = llm_factory._resolve_provider(keys)

    if provider == "openai":
        api_key = llm_factory._resolve_openai_key(keys)
        if api_key:
            return {
                "provider": "openai",
                "config": {"model": "text-embedding-3-small", "api_key": api_key},
            }
    elif provider == "google":
        api_key = llm_factory._resolve_google_key(keys)
        if api_key:
            return {
                "provider": "google",
                "config": {"model": "models/text-embedding-004", "api_key": api_key},
            }
    elif provider == "ollama":
        url = llm_factory._resolve_ollama_url(keys) or llm_factory.DEFAULT_OLLAMA_URL
        return {
            "provider": "ollama",
            "config": {"model": "nomic-embed-text", "url": url},
        }
    return None


def build_crew_factory(
    api_keys_repository: ApiKeysRepositoryProtocol,
) -> CrewFactory | None:
    """Build CrewFactory from API key repository, or None if no LLM key."""
    llm_factory = LLMFactory(api_keys_repository)

    if not llm_factory.has_api_key():
        return None

    llm = llm_factory.create_crewai_llm()
    logger.debug("CrewAI LLM: %r", llm)
    keys = api_keys_repository.get_all()
    registry = ToolRegistry(
        virustotal_api_key=keys.get("virustotal_api_key"),
        urlscan_api_key=keys.get("urlscan_api_key"),
    )
    embedder_config = build_embedder_config(llm_factory, keys)

    return CrewFactory(
        tool_registry=registry,
        llm=llm,
        embedder_config=embedder_config,
    )
