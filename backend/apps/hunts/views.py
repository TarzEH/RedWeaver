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

    def host_of(url, fallback):
        return (
            (urlparse(url).hostname if "://" in (url or "") else "")
            or (url or "").split("/")[0].split(":")[0]
            or fallback or "unknown"
        )

    # one screenshot per host (latest), for the asset-grid thumbnail
    from apps.observability.models import Screenshot
    shots: dict = {}
    for s in Screenshot.objects.filter(run__session=sess).order_by("-taken_at"):
        h = host_of(s.url, "")
        if h and h not in shots:
            shots[h] = s.image.url if s.image else ""

    assets: dict = {}
    for f in Finding.objects.filter(session=sess).select_related("run"):
        host = host_of(f.affected_url, f.run.target if f.run_id else "")
        a = assets.setdefault(host, {"host": host, "findings": 0, "max_severity": "info",
                                     "ports": set(), "technologies": set(), "cves": set(),
                                     "exploit_available": False})
        a["findings"] += 1
        if rank.get(f.severity, 0) > rank.get(a["max_severity"], 0):
            a["max_severity"] = f.severity
        m = re.search(r"port\s*(\d{1,5})", (f.title or "").lower())
        if m:
            a["ports"].add(int(m.group(1)))
        tm = re.search(r"detected\s+(.+?)(?:\s+version|\s+stack|$)", (f.title or "").lower())
        if tm:
            a["technologies"].add(tm.group(1).strip()[:40])
        for c in (f.cve_ids or []):
            a["cves"].add(c)
        if f.cisa_kev or (f.exploitability or "").lower() in ("proven", "likely"):
            a["exploit_available"] = True
    out = [
        {**a, "ports": sorted(a["ports"]), "technologies": sorted(a["technologies"]),
         "cves": sorted(a["cves"]), "screenshot": shots.get(a["host"], "")}
        for a in assets.values()
    ]
    out.sort(key=lambda x: (-rank.get(x["max_severity"], 0), -x["findings"]))
    return Response({"session_id": str(sess.id), "asset_count": len(out), "assets": out})


def _exposure_score(findings) -> float:
    w = {"critical": 10, "high": 7, "medium": 4, "low": 2, "info": 0.5}
    raw = sum(w.get((f.severity or "info").lower(), 0) for f in findings)
    return round(min(100.0, 100.0 * (1 - 2.718 ** (-raw / 25.0))), 1)  # saturating


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def session_posture(request, session_id):
    """Posture-over-time: exposure score + severity counts per finished run."""
    from collections import Counter

    from apps.common.access import scoped_get_or_404, session_scope_q
    sess = scoped_get_or_404(Session, request.user, session_scope_q, id=session_id)
    points = []
    for run in sess.runs.filter(status="completed").order_by("created_at"):
        fs = list(run.findings.all())
        points.append({
            "run_id": str(run.id),
            "date": (run.completed_at or run.created_at).isoformat(),
            "target": run.target,
            "exposure": _exposure_score(fs),
            "findings": len(fs),
            "by_severity": dict(Counter(f.severity for f in fs)),
        })
    return Response({"session_id": str(sess.id), "points": points})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def run_attack_graph(request, run_id):
    """Unified attack graph: target -> host -> service/port -> CVE -> exploit,
    built from the run's findings (answers 'what runs tech with an exploit')."""
    import re as _re
    from urllib.parse import urlparse as _up

    run = scoped_get_or_404(Run, request.user, run_scope_q, id=run_id)
    nodes: dict = {}
    edges: list = []

    def node(nid, label, ntype, sev="info"):
        nodes.setdefault(nid, {"id": nid, "label": label[:48], "type": ntype, "severity": sev})

    def edge(a, b):
        if a != b and {"source": a, "target": b} not in edges:
            edges.append({"source": a, "target": b})

    target = run.target or "target"
    node(f"t:{target}", target, "target")
    for f in run.findings.all():
        host = (_up(f.affected_url).hostname if "://" in (f.affected_url or "") else "") \
            or (f.affected_url or "").split("/")[0].split(":")[0] or target
        hid = f"h:{host}"
        node(hid, host, "host")
        edge(f"t:{target}", hid)
        pm = _re.search(r"port\s*(\d{1,5})", (f.title or "").lower())
        anchor = hid
        if pm:
            sid = f"s:{host}:{pm.group(1)}"
            node(sid, f"port {pm.group(1)}", "service")
            edge(hid, sid)
            anchor = sid
        for c in (f.cve_ids or []):
            cid = f"c:{c}"
            node(cid, c, "cve", f.severity)
            edge(anchor, cid)
            if f.cisa_kev or (f.exploitability or "").lower() in ("proven", "likely"):
                eid = f"e:{c}"
                node(eid, "exploit", "exploit", f.severity)
                edge(cid, eid)
    return Response({"run_id": str(run.id), "nodes": list(nodes.values()), "edges": edges})


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
def run_attack(request, run_id):
    """GET -> {status, markdown}; POST -> enqueue the Attack playbook agent."""
    run = scoped_get_or_404(Run, request.user, run_scope_q, id=run_id)
    if request.method == "POST":
        if run.attack_status not in ("running", "queued"):
            run.attack_status = "queued"
            run.save(update_fields=["attack_status", "updated_at"])
            try:
                from .attack_tasks import generate_attack_playbook
                generate_attack_playbook.delay(str(run.id))
            except Exception:
                pass
        return Response({"status": run.attack_status})
    return Response({"status": run.attack_status, "markdown": run.attack_markdown})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def attack_plan(request):
    """Preview a pre-hunt ATT&CK plan WITHOUT starting a hunt.

    Body: {target?, attack_techniques?: [ids], navigator_layer?: {layer JSON}, ssh_config?}.
    Returns the derived {techniques, unknown, tactics, agent_selection, focus} so the
    UI can show what a hunt scoped to those ATT&CK techniques would run.
    """
    from redweaver_engine.crews.bug_hunt.attack_planning import (
        normalize_technique_id,
        parse_navigator_layer,
        plan_from_techniques,
        plan_navigator_layer,
    )
    from redweaver_engine.crews.bug_hunt.selection import (
        TARGET_AGENT_MAP,
        classify_target,
    )

    data = request.data if isinstance(request.data, dict) else {}
    target = (data.get("target") or "").strip()
    ssh_config = data.get("ssh_config") if isinstance(data.get("ssh_config"), dict) else None

    techniques = [
        normalize_technique_id(t)
        for t in (data.get("attack_techniques") or [])
        if normalize_technique_id(t)
    ]
    if not techniques and isinstance(data.get("navigator_layer"), dict):
        techniques = parse_navigator_layer(data["navigator_layer"])

    target_type = classify_target(target) if target else "web"
    target_agents = list(TARGET_AGENT_MAP.get(target_type, TARGET_AGENT_MAP["web"]))

    if not techniques:
        return Response({
            "target_type": target_type,
            "techniques": [], "unknown": [], "tactics": [],
            "agent_selection": [], "focus": "",
        })

    plan = plan_from_techniques(techniques, target_agents, ssh_config)
    plan["target_type"] = target_type
    # Attach a ready-to-open ATT&CK Navigator layer for the planned techniques.
    plan["layer"] = plan_navigator_layer(plan["techniques"], plan["tactics"], target)
    return Response(plan)
