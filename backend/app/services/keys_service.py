"""API keys status and update."""
import os

from app.models.keys import KeysUpdate, KeysStatus
from app.repositories.api_keys_repository import ApiKeysRepositoryProtocol


class KeysService:
    """Get key status and update keys; never returns key values."""

    def __init__(self, api_keys_repository: ApiKeysRepositoryProtocol) -> None:
        self._repo = api_keys_repository

    # ------------------------------------------------------------------ #
    # Key resolution (env vars take precedence, then UI/Redis)
    # ------------------------------------------------------------------ #

    def resolve_openai_key(self) -> str:
        """Return the effective OpenAI key (env > Redis). Never expose to API."""
        keys = self._repo.get_all()
        return (
            os.environ.get("OPENAI_API_KEY", "").strip()
            or (keys.get("openai_api_key") or "").strip()
        )

    def resolve_anthropic_key(self) -> str:
        """Return the effective Anthropic key (env > Redis). Never expose to API."""
        keys = self._repo.get_all()
        return (
            os.environ.get("ANTHROPIC_API_KEY", "").strip()
            or (keys.get("anthropic_api_key") or "").strip()
        )

    def resolve_google_key(self) -> str:
        """Return the effective Google API key (env > Redis). Never expose to API."""
        keys = self._repo.get_all()
        return (
            os.environ.get("GOOGLE_API_KEY", "").strip()
            or (keys.get("google_api_key") or "").strip()
        )

    def resolve_ollama_url(self) -> str:
        """Return the effective Ollama URL (env > Redis > default)."""
        keys = self._repo.get_all()
        return (
            os.environ.get("OLLAMA_BASE_URL", "").strip()
            or (keys.get("ollama_base_url") or "").strip()
        )

    def get_status(self) -> KeysStatus:
        keys = self._repo.get_all()
        ollama_url = self.resolve_ollama_url()
        return KeysStatus(
            openai_configured=bool(self.resolve_openai_key()),
            anthropic_configured=bool(self.resolve_anthropic_key()),
            google_configured=bool(self.resolve_google_key()),
            ollama_configured=bool(ollama_url),
            ollama_base_url=ollama_url or None,
            model_provider=keys.get("model_provider") or os.environ.get("MODEL_PROVIDER") or None,
            selected_model=keys.get("selected_model") or None,
        )

    def update_keys(self, body: KeysUpdate) -> KeysStatus:
        if body.clear:
            self._repo.clear()
            return KeysStatus(
                openai_configured=False,
                anthropic_configured=False,
                google_configured=False,
                ollama_configured=False,
            )
        if body.openai_api_key is not None:
            self._repo.set_key("openai_api_key", body.openai_api_key or "")
        if body.anthropic_api_key is not None:
            self._repo.set_key("anthropic_api_key", body.anthropic_api_key or "")
        if body.google_api_key is not None:
            self._repo.set_key("google_api_key", body.google_api_key or "")
        if body.ollama_base_url is not None:
            self._repo.set_key("ollama_base_url", body.ollama_base_url or "")
        if body.model_provider is not None:
            self._repo.set_key("model_provider", body.model_provider or "")
        if body.selected_model is not None:
            self._repo.set_key("selected_model", body.selected_model or "")
        return self.get_status()
