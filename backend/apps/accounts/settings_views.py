"""Settings endpoints: per-user API key vault status + update.

Mirrors the legacy /api/settings/keys contract (KeysStatus / KeysUpdate).
Secret values are never returned — only boolean "configured" flags.
"""
import os

import httpx
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ApiKeyVault

# Curated model lists per provider for the Settings dropdown.
PROVIDER_MODELS = {
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "o4-mini"],
    "anthropic": [
        "claude-sonnet-4-6-20260218", "claude-3-7-sonnet-latest",
        "claude-3-5-haiku-latest",
    ],
    "google": ["gemini-3-flash", "gemini-2.5-pro", "gemini-1.5-pro"],
    "ollama": ["llama3.2", "llama3.1", "qwen2.5", "mistral"],
}


def _ollama_url(request) -> str:
    return (
        request.query_params.get("url")
        or os.environ.get("OLLAMA_BASE_URL", "")
        or "http://host.docker.internal:11434"
    ).rstrip("/")

SECRET_FIELDS = [
    "openai_api_key", "anthropic_api_key", "google_api_key",
    "virustotal_api_key", "urlscan_api_key",
]
PLAIN_FIELDS = ["ollama_base_url", "model_provider", "selected_model"]


def _configured(vault, field: str, env_var: str) -> bool:
    if os.environ.get(env_var, "").strip():
        return True
    return bool(getattr(vault, field, "") if vault else "")


class SettingsKeysView(APIView):
    """GET status (no secrets); POST update/clear the caller's vault."""

    def get(self, request):
        vault = ApiKeyVault.objects.filter(user=request.user).first()
        return Response(
            {
                "openai_configured": _configured(vault, "openai_api_key", "OPENAI_API_KEY"),
                "anthropic_configured": _configured(vault, "anthropic_api_key", "ANTHROPIC_API_KEY"),
                "google_configured": _configured(vault, "google_api_key", "GOOGLE_API_KEY"),
                "ollama_configured": bool(
                    os.environ.get("OLLAMA_BASE_URL", "").strip()
                    or (vault.ollama_base_url if vault else "")
                ),
                "ollama_base_url": (vault.ollama_base_url if vault else "") or "",
                "model_provider": (vault.model_provider if vault else "") or "",
                "selected_model": (vault.selected_model if vault else "") or "",
            }
        )

    def post(self, request):
        vault, _ = ApiKeyVault.objects.get_or_create(user=request.user)
        data = request.data or {}
        if data.get("clear"):
            for field in SECRET_FIELDS + PLAIN_FIELDS:
                setattr(vault, field, "")
            vault.save()
            return self.get(request)
        for field in SECRET_FIELDS + PLAIN_FIELDS:
            if field in data and data[field] is not None:
                setattr(vault, field, str(data[field]).strip())
        vault.save()
        return self.get(request)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def provider_models(request, provider):
    models = PROVIDER_MODELS.get(provider.lower(), [])
    return Response({"models": [{"id": m, "name": m} for m in models]})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ollama_health(request):
    url = _ollama_url(request)
    try:
        r = httpx.get(f"{url}/api/tags", timeout=5)
        ok = r.status_code == 200
    except Exception:
        ok = False
    return Response({"status": "connected" if ok else "disconnected", "base_url": url})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ollama_models(request):
    url = _ollama_url(request)
    try:
        r = httpx.get(f"{url}/api/tags", timeout=5)
        data = r.json()
        models = [
            {"name": m.get("name", ""), "size": m.get("size", 0)}
            for m in data.get("models", [])
        ]
    except Exception:
        models = []
    return Response({"models": models, "base_url": url})
