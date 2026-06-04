"""DRF viewsets for runs, hunts, sessions, targets.

Run and Hunt are the same model exposed two ways for frontend compatibility.
Execution (start/stop/chat -> Celery) is wired in Phase F; the start/stop
actions here update status and enqueue when the task is available.
"""
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.access import (
    ScopedQuerysetMixin,
    run_scope_q,
    scoped_get_or_404,
    session_scope_q,
    target_scope_q,
)

from .models import Run, Session, Target
from .serializers import (
    HuntCreateSerializer,
    HuntDetailSerializer,
    HuntSerializer,
    RunDetailSerializer,
    RunSummarySerializer,
    SessionSerializer,
    SessionWriteSerializer,
    TargetSerializer,
    TargetWriteSerializer,
)


class RunViewSet(
    ScopedQuerysetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Run.objects.all().select_related("session", "workspace")
    scope_q = staticmethod(run_scope_q)

    def get_serializer_class(self):
        return RunDetailSerializer if self.action == "retrieve" else RunSummarySerializer


def _enqueue_run(run: Run) -> None:
    """Enqueue execution if the Celery task exists (wired in Phase F)."""
    try:
        from .tasks import execute_run
    except Exception:
        return
    execute_run.delay(str(run.id))


class HuntViewSet(ScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Run.objects.all().select_related("session", "workspace", "target_obj")
    scope_q = staticmethod(run_scope_q)

    def get_serializer_class(self):
        if self.action == "create":
            return HuntCreateSerializer
        if self.action == "retrieve":
            return HuntDetailSerializer
        return HuntSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        sid = self.request.query_params.get("session_id")
        return qs.filter(session_id=sid) if sid else qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        run = self.get_object()
        run.status = Run._meta.get_field("status").default  # queued
        run.save(update_fields=["status", "updated_at"])
        _enqueue_run(run)
        return Response(HuntSerializer(run, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def stop(self, request, pk=None):
        run = self.get_object()
        run.status = "cancelled"
        run.save(update_fields=["status", "updated_at"])
        return Response(HuntSerializer(run, context={"request": request}).data)


class SessionViewSet(ScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Session.objects.all().select_related("workspace")
    scope_q = staticmethod(session_scope_q)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return SessionWriteSerializer
        return SessionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        wid = self.request.query_params.get("workspace_id")
        return qs.filter(workspace_id=wid) if wid else qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], url_path=r"targets/(?P<target_id>[^/.]+)")
    def link_target(self, request, pk=None, target_id=None):
        session = self.get_object()
        updated = Target.objects.filter(id=target_id).update(session=session)
        if not updated:
            return Response({"detail": "target not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"status": "linked"})


class TargetViewSet(ScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Target.objects.all()
    scope_q = staticmethod(target_scope_q)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return TargetWriteSerializer
        return TargetSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        sid = self.request.query_params.get("session_id")
        return qs.filter(session_id=sid) if sid else qs

    def update(self, request, *args, **kwargs):
        kwargs["partial"] = True  # treat PUT as partial (frontend sends sparse bodies)
        return super().update(request, *args, **kwargs)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def run_offsec(request, run_id):
    """GET -> {status, markdown}; POST -> enqueue the OffSec playbook agent."""
    run = scoped_get_or_404(Run, request.user, run_scope_q, id=run_id)
    if request.method == "POST":
        if run.offsec_status not in ("running", "queued"):
            run.offsec_status = "queued"
            run.save(update_fields=["offsec_status", "updated_at"])
            try:
                from .offsec_tasks import generate_offsec_playbook
                generate_offsec_playbook.delay(str(run.id))
            except Exception:
                pass
        return Response({"status": run.offsec_status})
    return Response({"status": run.offsec_status, "markdown": run.offsec_markdown})
