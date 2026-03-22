"""Configurable LLM factory for CrewAI and the OpenAI Agents SDK.

Provides model name resolution, model provider creation for
OpenAI (default), Anthropic (via AnthropicModelProvider extension),
Google Gemini (via OpenAI-compatible endpoint), and Ollama (via
OpenAI-compatible API), plus CrewAI LangChain ChatModel creation.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from app.repositories.api_keys_repository import ApiKeysRepositoryProtocol

logger = logging.getLogger(__name__)


class LLMFactory:
    """Creates model configuration for the OpenAI Agents SDK.

    Model selection priority:
    1. model_override parameter (per-call)
    2. User-selected model (stored in keys repo)
    3. Environment variables (MODEL_OPENAI, MODEL_ANTHROPIC, MODEL_GOOGLE, MODEL_OLLAMA)
    4. Default models

    Provider resolution:
    1. MODEL_PROVIDER env or UI setting
    2. Auto-detect from available keys/URLs (OpenAI > Anthropic > Google > Ollama)
    """

    DEFAULT_MODELS: dict[str, str] = {
        "openai": os.environ.get("MODEL_OPENAI", "gpt-4o-mini"),
        "anthropic": os.environ.get("MODEL_ANTHROPIC", "claude-sonnet-4-6-20260218"),
        "google": os.environ.get("MODEL_GOOGLE", "gemini-3-flash"),
        "ollama": os.environ.get("MODEL_OLLAMA", "llama3.2"),
    }

    DEFAULT_OLLAMA_URL = "http://host.docker.internal:11434"
    GOOGLE_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

    def __init__(self, api_keys_repository: ApiKeysRepositoryProtocol) -> None:
        self._keys_repo = api_keys_repository

    def resolve_model_name(self, model_override: str | None = None) -> str:
        """Return the model name string for the SDK."""
        if model_override:
            logger.debug("resolve_model_name: using override=%r", model_override)
            return model_override

        keys = self._keys_repo.get_all()

        # Check for user-selected model first
        selected = (keys.get("selected_model") or "").strip()
        if selected:
            logger.debug("resolve_model_name: using user-selected model=%r", selected)
            return selected

        provider = self._resolve_provider(keys)
        model = self.DEFAULT_MODELS.get(provider, self.DEFAULT_MODELS["openai"])
        logger.debug("resolve_model_name: provider=%r, model=%r", provider, model)
        return model

    def create_model_provider(self) -> Any | None:
        """Return a model provider for non-OpenAI models.

        For Anthropic, returns an AnthropicModelProvider instance.
        For OpenAI, Ollama, and Google, returns None (all use OpenAI client).
        """
        keys = self._keys_repo.get_all()
        provider = self._resolve_provider(keys)

        if provider == "anthropic":
            api_key = self._resolve_anthropic_key(keys)
            if api_key:
                try:
                    from agents.extensions.models.anthropic_model import AnthropicModelProvider

                    logger.debug("Using Anthropic provider (%s)", self.DEFAULT_MODELS["anthropic"])
                    return AnthropicModelProvider()
                except ImportError:
                    logger.warning("agents anthropic extension not installed, falling back to OpenAI")
                    return None

        if provider == "google":
            logger.debug("Using Google Gemini provider (OpenAI-compatible API)")
            return None

        if provider == "ollama":
            logger.debug("Using Ollama provider (OpenAI-compatible API)")
            return None

        logger.debug("Using OpenAI provider (%s)", self.DEFAULT_MODELS["openai"])
        return None

    def get_openai_client_kwargs(self) -> dict[str, Any] | None:
        """Return kwargs to construct AsyncOpenAI for non-standard endpoints.

        For Ollama: returns {base_url, api_key="ollama"}.
        For Google: returns {base_url, api_key=google_key}.
        For OpenAI/Anthropic: returns None (use default client).
        """
        keys = self._keys_repo.get_all()
        provider = self._resolve_provider(keys)
        if provider == "ollama":
            url = self._resolve_ollama_url(keys) or self.DEFAULT_OLLAMA_URL
            logger.debug("Ollama client kwargs: base_url=%s/v1", url)
            return {
                "base_url": f"{url}/v1",
                "api_key": "ollama",
            }
        if provider == "google":
            api_key = self._resolve_google_key(keys)
            if api_key:
                logger.debug("Google client kwargs: base_url=%s", self.GOOGLE_OPENAI_BASE_URL)
                return {
                    "base_url": self.GOOGLE_OPENAI_BASE_URL,
                    "api_key": api_key,
                }
        return None

    def has_api_key(self) -> bool:
        """Check if at least one LLM API key/endpoint is available."""
        keys = self._keys_repo.get_all()
        provider = self._resolve_provider(keys)
        if provider == "ollama":
            return True  # Ollama doesn't need an API key
        return bool(
            self._resolve_openai_key(keys)
            or self._resolve_anthropic_key(keys)
            or self._resolve_google_key(keys)
        )

    def _resolve_provider(self, keys: dict) -> str:
        """Determine which LLM provider to use."""
        provider = (
            keys.get("model_provider")
            or os.environ.get("MODEL_PROVIDER", "")
        ).strip().lower()
        logger.debug(
            "_resolve_provider: explicit=%r, has_openai=%s, has_anthropic=%s, has_google=%s, has_ollama=%s",
            provider,
            bool(self._resolve_openai_key(keys)),
            bool(self._resolve_anthropic_key(keys)),
            bool(self._resolve_google_key(keys)),
            bool(self._resolve_ollama_url(keys)),
        )
        if provider in ("openai", "anthropic", "google", "ollama"):
            return provider
        if self._resolve_openai_key(keys):
            return "openai"
        if self._resolve_anthropic_key(keys):
            return "anthropic"
        if self._resolve_google_key(keys):
            return "google"
        if self._resolve_ollama_url(keys):
            return "ollama"
        return "openai"

    @staticmethod
    def _resolve_openai_key(keys: dict) -> str | None:
        from_env = os.environ.get("OPENAI_API_KEY", "").strip()
        from_ui = (keys.get("openai_api_key") or "").strip()
        return from_env or from_ui or None

    @staticmethod
    def _resolve_anthropic_key(keys: dict) -> str | None:
        from_env = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        from_ui = (keys.get("anthropic_api_key") or "").strip()
        return from_env or from_ui or None

    @staticmethod
    def _resolve_google_key(keys: dict) -> str | None:
        from_env = os.environ.get("GOOGLE_API_KEY", "").strip()
        from_ui = (keys.get("google_api_key") or "").strip()
        return from_env or from_ui or None

    @staticmethod
    def _resolve_ollama_url(keys: dict) -> str | None:
        from_env = os.environ.get("OLLAMA_BASE_URL", "").strip()
        from_ui = (keys.get("ollama_base_url") or "").strip()
        return from_env or from_ui or None

    # ------------------------------------------------------------------
    # CrewAI LLM support
    # ------------------------------------------------------------------

    def create_crewai_llm(self, model_override: str | None = None) -> Any:
        """Return a LangChain ChatModel instance for CrewAI.

        Supports OpenAI, Anthropic, Google Gemini, and Ollama providers.
        Falls back to a simple model string if LangChain provider packages
        are not installed.
        """
        keys = self._keys_repo.get_all()
        provider = self._resolve_provider(keys)
        model_name = self.resolve_model_name(model_override)

        if provider == "openai":
            api_key = self._resolve_openai_key(keys)
            try:
                from langchain_openai import ChatOpenAI

                logger.debug("CrewAI LLM: OpenAI %s", model_name)
                return ChatOpenAI(
                    model=model_name,
                    api_key=api_key,
                    temperature=0.1,
                    timeout=300,
                )
            except ImportError:
                logger.warning("langchain-openai not installed, using model string")
                return model_name

        elif provider == "anthropic":
            api_key = self._resolve_anthropic_key(keys)
            try:
                from langchain_anthropic import ChatAnthropic

                logger.debug("CrewAI LLM: Anthropic %s", model_name)
                return ChatAnthropic(
                    model=model_name,
                    api_key=api_key,
                    temperature=0.1,
                    timeout=300,
                )
            except ImportError:
                logger.warning("langchain-anthropic not installed, using model string")
                return model_name

        elif provider == "google":
            api_key = self._resolve_google_key(keys)
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI

                logger.debug("CrewAI LLM: Google %s", model_name)
                return ChatGoogleGenerativeAI(
                    model=model_name,
                    google_api_key=api_key,
                    temperature=0.1,
                )
            except ImportError:
                logger.warning("langchain-google-genai not installed, using model string")
                return model_name

        elif provider == "ollama":
            url = self._resolve_ollama_url(keys) or self.DEFAULT_OLLAMA_URL
            try:
                from langchain_ollama import ChatOllama

                logger.debug("CrewAI LLM: Ollama %s at %s", model_name, url)
                return ChatOllama(
                    model=model_name,
                    base_url=url,
                    temperature=0.1,
                )
            except ImportError:
                logger.warning("langchain-ollama not installed, using model string")
                return model_name

        # Fallback
        logger.warning("Unknown provider %s, using model string", provider)
        return model_name
