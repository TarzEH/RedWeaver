"""Read-only observability endpoints (the behind-the-scenes debug API)."""
from django.http import Http404
from rest_framework import generics

from apps.common.access import run_scope_q
from apps.common.pagination import DefaultPagination
from apps.hunts.models import Run

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

    def _check_run_access(self):
        run_id = self.kwargs["run_id"]
        user = self.request.user
        run_qs = Run.objects.filter(id=run_id)
        if not getattr(user, "is_superuser", False):
            run_qs = run_qs.filter(run_scope_q(user))
        if not run_qs.exists():
            raise Http404("Run not found")
        return run_id

    def get_queryset(self):
        run_id = self._check_run_access()
        return self.model.objects.filter(run_id=run_id).order_by(*self.ordering)


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
