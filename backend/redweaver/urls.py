"""Root URL configuration.

App URL modules are included incrementally as they are implemented in the
auth (D) and read-API (E) phases. Each include is guarded so the project
keeps booting while later phases are still in progress.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def health(_request):
    """Liveness probe (Docker healthcheck hits /health)."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health", health),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]

# --- App API routes (added per phase). Guarded so partial trees still boot. ---
_API_INCLUDES = [
    ("api/auth/", "apps.accounts.urls"),
    ("api/", "apps.workspaces.urls"),
    ("api/", "apps.hunts.urls"),
    ("api/", "apps.findings.urls"),
    ("api/", "apps.observability.urls"),
    ("api/", "apps.reports.urls"),
    ("api/", "apps.agents.urls"),
    ("api/", "apps.knowledge.urls"),
]

for _prefix, _module in _API_INCLUDES:
    try:
        urlpatterns.append(path(_prefix, include(_module)))
    except Exception:  # pragma: no cover - module not implemented yet
        pass

# Serve screenshot media through Django in DEBUG; nginx/whitenoise in prod.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
