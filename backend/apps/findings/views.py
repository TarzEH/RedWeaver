"""Finding endpoints: global list/triage + per-run list + triage workflow."""
from rest_framework import mixins, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.access import ScopedQuerysetMixin, finding_scope_q
from apps.common.permissions import RoleWritePermission

from .models import Finding, FindingActivity, FindingComment
from .serializers import (
    AttackChainSerializer,
    FindingActivitySerializer,
    FindingCommentSerializer,
    FindingSerializer,
    FindingTriageSerializer,
)


class FindingViewSet(
    ScopedQuerysetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """List/retrieve findings with filters; PATCH to triage status."""

    queryset = Finding.objects.all().select_related("run")
    serializer_class = FindingSerializer
    search_fields = ("title", "affected_url", "description")
    scope_q = staticmethod(finding_scope_q)
    permission_classes = [IsAuthenticated, RoleWritePermission]

    def get_serializer_class(self):
        if self.action in ("update", "partial_update"):
            return FindingTriageSerializer
        return FindingSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("session_id"):
            qs = qs.filter(session_id=p["session_id"])
        if p.get("hunt_id") or p.get("run_id"):
            qs = qs.filter(run_id=p.get("hunt_id") or p.get("run_id"))
        if p.get("severity"):
            qs = qs.filter(severity=p["severity"])
        if p.get("status"):
            qs = qs.filter(status=p["status"])
        if p.get("agent_source"):
            qs = qs.filter(agent_source=p["agent_source"])
        return qs

    def perform_update(self, serializer):
        before = {"status": serializer.instance.status, "assignee": serializer.instance.assignee_id}
        f = serializer.save()
        u = self.request.user
        if before["status"] != f.status:
            FindingActivity.objects.create(finding=f, actor=u, action="status_change",
                                           detail=f"{before['status']} -> {f.status}")
        if before["assignee"] != f.assignee_id:
            FindingActivity.objects.create(finding=f, actor=u, action="assigned",
                                           detail=(f.assignee.email if f.assignee_id else "unassigned"))

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        finding = self.get_object()
        if request.method == "POST":
            body = (request.data.get("body") or "").strip()
            if not body:
                return Response({"error": "body required"}, status=400)
            c = FindingComment.objects.create(finding=finding, author=request.user, body=body)
            FindingActivity.objects.create(finding=finding, actor=request.user, action="comment",
                                           detail=body[:120])
            return Response(FindingCommentSerializer(c).data, status=201)
        qs = finding.comments.all()
        return Response(FindingCommentSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"])
    def activity(self, request, pk=None):
        finding = self.get_object()
        return Response(FindingActivitySerializer(finding.activity.all(), many=True).data)

    @action(detail=True, methods=["post"])
    def retest(self, request, pk=None):
        """Re-scan the finding's affected target as a fresh focused run."""
        finding = self.get_object()
        target = finding.affected_url or (finding.run.target if finding.run_id else "")
        if not target:
            return Response({"error": "no target to retest"}, status=400)
        from apps.hunts.models import Run
        from apps.hunts.views import _enqueue_run
        run = Run.objects.create(
            target=target, scope=target, objective="comprehensive",
            created_by=request.user, session=finding.session, workspace=finding.run.workspace,
        )
        _enqueue_run(run)
        FindingActivity.objects.create(finding=finding, actor=request.user, action="retest",
                                       detail=f"retest run {run.id}")
        return Response({"status": "retest started", "run_id": str(run.id)}, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def run_findings(request, run_id):
    """GET /api/runs/{run_id}/findings -> {findings: [...]} (scoped to the user)."""
    qs = Finding.objects.filter(run_id=run_id).order_by("-created_at")
    if not getattr(request.user, "is_superuser", False):
        qs = qs.filter(finding_scope_q(request.user))
    return Response({"findings": FindingSerializer(qs, many=True).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def run_attack_navigator(request, run_id):
    """Export a MITRE ATT&CK Navigator layer (.json) for a run's findings —
    a real engagement artifact that opens in the ATT&CK Navigator."""
    from django.http import HttpResponse
    import json
    from apps.common.access import run_scope_q, scoped_get_or_404
    from apps.hunts.models import Run
    from .attack_map import navigator_layer

    run = scoped_get_or_404(Run, request.user, run_scope_q, id=run_id)
    layer = navigator_layer(run, list(run.findings.all()))
    resp = HttpResponse(json.dumps(layer, indent=2), content_type="application/json")
    resp["Content-Disposition"] = f'attachment; filename="redweaver-{str(run.id)[:8]}-attack-layer.json"'
    return resp


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def run_compare(request, run_id):
    """Delta between a run and a ?baseline=<run_id>: new / fixed / recurring
    findings keyed by dedup_key — the core 'are we getting better?' loop."""
    from apps.common.access import run_scope_q, scoped_get_or_404
    from apps.hunts.models import Run

    baseline_id = request.query_params.get("baseline")
    if not baseline_id:
        return Response({"error": "baseline query param required"}, status=400)
    cur = scoped_get_or_404(Run, request.user, run_scope_q, id=run_id)
    base = scoped_get_or_404(Run, request.user, run_scope_q, id=baseline_id)

    def fmap(run):
        m = {}
        for f in run.findings.all():
            m[f.dedup_key or f.compute_dedup_key()] = f
        return m

    cur_m, base_m = fmap(cur), fmap(base)
    new_k = [k for k in cur_m if k not in base_m]
    fixed_k = [k for k in base_m if k not in cur_m]
    recur_k = [k for k in cur_m if k in base_m]
    ser = lambda fs: FindingSerializer(fs, many=True).data  # noqa: E731
    return Response({
        "run_id": str(cur.id),
        "baseline_id": str(base.id),
        "new": ser([cur_m[k] for k in new_k]),
        "fixed": ser([base_m[k] for k in fixed_k]),
        "recurring": ser([cur_m[k] for k in recur_k]),
        "summary": {"new": len(new_k), "fixed": len(fixed_k), "recurring": len(recur_k)},
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def run_attack_chains(request, run_id):
    """Persisted multi-step attack chains correlated by the exploit_analyst."""
    from apps.common.access import run_scope_q, scoped_get_or_404
    from apps.hunts.models import Run
    run = scoped_get_or_404(Run, request.user, run_scope_q, id=run_id)
    return Response(AttackChainSerializer(run.attack_chains.all(), many=True).data)
