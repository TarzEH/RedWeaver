"""Observability read routes (mounted at /api/), all scoped to a run."""
from django.urls import path

from .views import (
    AgentStepListView,
    AgentTransitionListView,
    EventLogListView,
    GraphSnapshotListView,
    ScreenshotListView,
    ToolExecutionListView,
)

urlpatterns = [
    path("runs/<uuid:run_id>/tool-executions", ToolExecutionListView.as_view(),
         name="run-tool-executions"),
    path("runs/<uuid:run_id>/agent-steps", AgentStepListView.as_view(),
         name="run-agent-steps"),
    path("runs/<uuid:run_id>/events", EventLogListView.as_view(),
         name="run-events"),
    path("runs/<uuid:run_id>/graph-snapshots", GraphSnapshotListView.as_view(),
         name="run-graph-snapshots"),
    path("runs/<uuid:run_id>/transitions", AgentTransitionListView.as_view(),
         name="run-transitions"),
    path("runs/<uuid:run_id>/screenshots", ScreenshotListView.as_view(),
         name="run-screenshots"),
]
