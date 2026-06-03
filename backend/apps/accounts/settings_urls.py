"""Settings routes (mounted at /api/settings/)."""
from django.urls import path

from .settings_views import (
    SettingsKeysView,
    ollama_health,
    ollama_models,
    provider_models,
)

urlpatterns = [
    path("keys", SettingsKeysView.as_view(), name="settings-keys"),
    path("models/<str:provider>", provider_models, name="settings-models"),
    path("ollama/health", ollama_health, name="settings-ollama-health"),
    path("ollama/models", ollama_models, name="settings-ollama-models"),
]
