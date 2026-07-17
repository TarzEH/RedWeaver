"""Workspace routes (mounted at /api/)."""
from rest_framework.routers import SimpleRouter

from .views import WorkspaceViewSet

router = SimpleRouter(trailing_slash=False)
router.register("workspaces", WorkspaceViewSet, basename="workspace")

urlpatterns = router.urls
