"""Build a CrewFactory from a KeysProvider (port of legacy crew_factory_provider)."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_embedder_config(llm_factory, keys: dict) -> dict | None:
    provider = llm_factory._resolve_provider(keys)
    if provider == "openai":
        api_key = llm_factory._resolve_openai_key(keys)
        if api_key:
            return {"provider": "openai",
                    "config": {"model": "text-embedding-3-small", "api_key": api_key}}
    elif provider == "google":
        api_key = llm_factory._resolve_google_key(keys)
        if api_key:
            return {"provider": "google",
                    "config": {"model": "models/text-embedding-004", "api_key": api_key}}
    elif provider == "ollama":
        url = llm_factory._resolve_ollama_url(keys) or llm_factory.DEFAULT_OLLAMA_URL
        return {"provider": "ollama",
                "config": {"model": "nomic-embed-text", "url": url}}
    return None


def _build_crewai_llm(llm_factory, keys: dict):
    """Build a crewai.LLM (litellm) — crewai 1.x rejects LangChain chat models.

    Uses litellm provider-prefixed model strings and the resolved API key.
    """
    from crewai import LLM

    provider = llm_factory._resolve_provider(keys)
    model = llm_factory.resolve_model_name()
    if provider == "anthropic":
        return LLM(model=f"anthropic/{model}",
                   api_key=llm_factory._resolve_anthropic_key(keys), temperature=0.1)
    if provider == "google":
        return LLM(model=f"gemini/{model}",
                   api_key=llm_factory._resolve_google_key(keys), temperature=0.1)
    if provider == "ollama":
        url = llm_factory._resolve_ollama_url(keys) or llm_factory.DEFAULT_OLLAMA_URL
        return LLM(model=f"ollama/{model}", base_url=url, temperature=0.1)
    return LLM(model=model, api_key=llm_factory._resolve_openai_key(keys), temperature=0.1)


def build_crew_factory(keys_provider) -> Any | None:
    """Return a CrewFactory, or None if no LLM key is configured."""
    from redweaver_engine.crews.bug_hunt.builder import CrewFactory
    from redweaver_engine.llm_factory import LLMFactory
    from redweaver_engine.tools.registry import ToolRegistry

    llm_factory = LLMFactory(keys_provider)
    if not llm_factory.has_api_key():
        return None

    keys = keys_provider.get_all()
    llm = _build_crewai_llm(llm_factory, keys)
    registry = ToolRegistry(
        virustotal_api_key=keys.get("virustotal_api_key"),
        urlscan_api_key=keys.get("urlscan_api_key"),
    )
    embedder = build_embedder_config(llm_factory, keys)
    return CrewFactory(tool_registry=registry, llm=llm, embedder_config=embedder)
