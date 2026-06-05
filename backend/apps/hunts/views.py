"""DRF viewsets for runs, hunts, sessions, targets.

Run and Hunt are the same model exposed two ways for frontend compatibility.
Execution (start/stop/chat -> Celery) is wired in Phase F; the start/stop
actions here update status and enqueue when the task is available.
"""
import json

from django.utils import timezone
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
from apps.common.permissions import RoleWritePermission

from .models import NotificationChannel, Run, Schedule, Session, Target
from .serializers import (
    HuntCreateSerializer,
    HuntDetailSerializer,
    HuntSerializer,
    NotificationChannelSerializer,
    RunDetailSerializer,
    RunSummarySerializer,
    ScheduleSerializer,
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
    permission_classes = [IsAuthenticated, RoleWritePermission]

    def get_serializer_class(self):
        return RunDetailSerializer if self.action == "retrieve" else RunSummarySerializer


def _enqueue_run(run: Run) -> None:
    """Enqueue execution with a per-run soft timeout, recording the task id so
    the run can be cancelled later."""
    try:
        from .tasks import execute_run
    except Exception:
        return
    soft = run.timeout_seconds or None
    task = execute_run.apply_async(
        (str(run.id),),
        soft_time_limit=soft,
        time_limit=(soft + 60) if soft else None,
    )
    if task and getattr(task, "id", None):
        run.celery_task_id = task.id
        run.save(update_fields=["celery_task_id", "updated_at"])


class HuntViewSet(ScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Run.objects.all().select_related("session", "workspace", "target_obj")
    scope_q = staticmethod(run_scope_q)
    permission_classes = [IsAuthenticated, RoleWritePermission]

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
        if run.celery_task_id:
            try:
                from celery.result import AsyncResult
                AsyncResult(run.celery_task_id).revoke(terminate=True, signal="SIGTERM")
            except Exception:
                pass
        run.status = "cancelled"
        run.completed_at = run.completed_at or timezone.now()
        run.save(update_fields=["status", "completed_at", "updated_at"])
        return Response(HuntSerializer(run, context={"request": request}).data)


class SessionViewSet(ScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Session.objects.all().select_related("workspace")
    scope_q = staticmethod(session_scope_q)
    permission_classes = [IsAuthenticated, RoleWritePermission]

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
    permission_classes = [IsAuthenticated, RoleWritePermission]

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


class NotificationChannelViewSet(viewsets.ModelViewSet):
    """Outbound webhook/Slack channels, scoped to the owner."""
    serializer_class = NotificationChannelSerializer
    permission_classes = [IsAuthenticated, RoleWritePermission]

    def get_queryset(self):
        u = self.request.user
        qs = NotificationChannel.objects.all()
        if getattr(u, "is_superuser", False):
            return qs
        return qs.filter(created_by=u)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ScheduleViewSet(viewsets.ModelViewSet):
    """Recurring scans (continuous monitoring), scoped to the owner."""
    serializer_class = ScheduleSerializer
    permission_classes = [IsAuthenticated, RoleWritePermission]

    def get_queryset(self):
        u = self.request.user
        qs = Schedule.objects.all()
        if getattr(u, "is_superuser", False):
            return qs
        return qs.filter(created_by=u)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def session_assets(request, session_id):
    """Asset inventory: aggregate findings across a session's runs into hosts
    with open ports, detected tech, finding counts and max severity."""
    import re
    from urllib.parse import urlparse

    from apps.common.access import scoped_get_or_404, session_scope_q
    from apps.findings.models import Finding

    sess = scoped_get_or_404(Session, request.user, session_scope_q, id=session_id)
    rank = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}
    assets: dict = {}
    for f in Finding.objects.filter(session=sess).select_related("run"):
        host = (
            (urlparse(f.affected_url).hostname if "://" in (f.affected_url or "") else "")
            or (f.affected_url or "").split("/")[0].split(":")[0]
            or (f.run.target if f.run_id else "")
            or "unknown"
        )
        a = assets.setdefault(host, {"host": host, "findings": 0, "max_severity": "info",
                                     "ports": set(), "technologies": set()})
        a["findings"] += 1
        if rank.get(f.severity, 0) > rank.get(a["max_severity"], 0):
            a["max_severity"] = f.severity
        m = re.search(r"port\s*(\d{1,5})", (f.title or "").lower())
        if m:
            a["ports"].add(int(m.group(1)))
        tm = re.search(r"detected\s+(.+?)(?:\s+version|\s+stack|$)", (f.title or "").lower())
        if tm:
            a["technologies"].add(tm.group(1).strip()[:40])
    out = [
        {**a, "ports": sorted(a["ports"]), "technologies": sorted(a["technologies"])}
        for a in assets.values()
    ]
    out.sort(key=lambda x: (-rank.get(x["max_severity"], 0), -x["findings"]))
    return Response({"session_id": str(sess.id), "asset_count": len(out), "assets": out})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def run_ask(request, run_id):
    """Ask-your-pentest: a grounded Q&A over THIS run's findings + report."""
    run = scoped_get_or_404(Run, request.user, run_scope_q, id=run_id)
    question = (request.data.get("question") or "").strip()
    if not question:
        return Response({"error": "question required"}, status=400)

    from apps.accounts.keys import keys_provider_for_user
    from apps.findings.serializers import FindingSerializer
    from redweaver_engine.llm_factory import LLMFactory

    from .crew_factory import _build_crewai_llm

    kp = keys_provider_for_user(run.created_by or request.user)
    lf = LLMFactory(kp)
    if not lf.has_api_key():
        return Response({"error": "No LLM API key configured"}, status=400)

    findings = FindingSerializer(run.findings.all(), many=True).data
    context = json.dumps(findings, default=str)[:9000]
    report = (run.report_markdown or "")[:6000]
    prompt = (
        f"You are a security analyst. Answer the question about THIS authorized "
        f"penetration test of {run.target} using ONLY the findings and report "
        f"below. Be concise, cite specific findings/CVEs, and say if the data is "
        f"insufficient.\n\nFINDINGS (JSON):\n{context}\n\nREPORT:\n{report}\n\n"
        f"QUESTION: {question}"
    )
    try:
        llm = _build_crewai_llm(lf, kp.get_all())
        answer = llm.call([{"role": "user", "content": prompt}])
    except Exception as exc:  # noqa: BLE001
        return Response({"error": str(exc)}, status=500)
    return Response({"answer": str(answer), "question": question})


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
