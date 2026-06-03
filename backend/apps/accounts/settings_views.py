"""Settings endpoints: per-user API key vault status + update.

Mirrors the legacy /api/settings/keys contract (KeysStatus / KeysUpdate).
Secret values are never returned — only boolean "configured" flags.
"""
import os

from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ApiKeyVault

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
