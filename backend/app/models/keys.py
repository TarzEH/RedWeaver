"""API keys request/response models."""
from pydantic import BaseModel


class KeysUpdate(BaseModel):
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    ollama_base_url: str | None = None
    model_provider: str | None = None
    selected_model: str | None = None
    clear: bool = False


class KeysStatus(BaseModel):
    openai_configured: bool
    anthropic_configured: bool
    google_configured: bool = False
    ollama_configured: bool = False
    ollama_base_url: str | None = None
    model_provider: str | None = None
    selected_model: str | None = None
