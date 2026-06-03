"""Run/hunt/session/target routes (mounted at /api/)."""
from rest_framework.routers import SimpleRouter

from .views import HuntViewSet, RunViewSet, SessionViewSet, TargetViewSet

router = SimpleRouter(trailing_slash=False)
router.register("runs", RunViewSet, basename="run")
router.register("hunts", HuntViewSet, basename="hunt")
router.register("sessions", SessionViewSet, basename="session")
router.register("targets", TargetViewSet, basename="target")

urlpatterns = router.urls
