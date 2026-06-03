"""Settings routes (mounted at /api/settings/)."""
from django.urls import path

from .settings_views import SettingsKeysView

urlpatterns = [
    path("keys", SettingsKeysView.as_view(), name="settings-keys"),
]
