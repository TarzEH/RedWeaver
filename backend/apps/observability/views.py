"""Read-only observability endpoints (the behind-the-scenes debug API)."""
from rest_framework import generics

from apps.common.pagination import DefaultPagination

from .models import (
    AgentStep,
    AgentTransition,
    EventLog,
    GraphSnapshot,
    Screenshot,
    ToolExecution,
)
from .serializers import (
    AgentStepSerializer,
    AgentTransitionSerializer,
    EventLogSerializer,
    GraphSnapshotSerializer,
    ScreenshotSerializer,
    ToolExecutionSerializer,
)


class _RunScopedList(generics.ListAPIView):
    model = None
    ordering = ("sequence",)
    pagination_class = DefaultPagination

    def get_queryset(self):
        return self.model.objects.filter(
            run_id=self.kwargs["run_id"]
        ).order_by(*self.ordering)


class ToolExecutionListView(_RunScopedList):
    model = ToolExecution
    serializer_class = ToolExecutionSerializer


class AgentStepListView(_RunScopedList):
    model = AgentStep
    serializer_class = AgentStepSerializer


class GraphSnapshotListView(_RunScopedList):
    model = GraphSnapshot
    serializer_class = GraphSnapshotSerializer


class AgentTransitionListView(_RunScopedList):
    model = AgentTransition
    serializer_class = AgentTransitionSerializer


class ScreenshotListView(_RunScopedList):
    model = Screenshot
    serializer_class = ScreenshotSerializer
    ordering = ("-taken_at",)


class EventLogListView(_RunScopedList):
    model = EventLog
    serializer_class = EventLogSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        after = self.request.query_params.get("after")
        if after:
            try:
                qs = qs.filter(sequence__gt=int(after))
            except (TypeError, ValueError):
                pass
        return qs
