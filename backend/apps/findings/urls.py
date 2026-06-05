"""Finding routes (mounted at /api/)."""
from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    FindingViewSet,
    run_attack_chains,
    run_attack_navigator,
    run_compare,
    run_findings,
)

router = SimpleRouter(trailing_slash=False)
router.register("findings", FindingViewSet, basename="finding")

urlpatterns = [
    path("runs/<uuid:run_id>/findings", run_findings, name="run-findings"),
    path("runs/<uuid:run_id>/attack-navigator", run_attack_navigator, name="run-attack-navigator"),
    path("runs/<uuid:run_id>/attack-chains", run_attack_chains, name="run-attack-chains"),
    path("runs/<uuid:run_id>/compare", run_compare, name="run-compare"),
    *router.urls,
]
