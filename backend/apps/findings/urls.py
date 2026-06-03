"""Finding routes (mounted at /api/)."""
from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import FindingViewSet, run_findings

router = SimpleRouter(trailing_slash=False)
router.register("findings", FindingViewSet, basename="finding")

urlpatterns = [
    path("runs/<uuid:run_id>/findings", run_findings, name="run-findings"),
    *router.urls,
]
