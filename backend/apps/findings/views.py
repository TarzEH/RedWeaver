"""Finding endpoints: global list/triage + per-run list."""
from rest_framework import mixins, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.access import ScopedQuerysetMixin, finding_scope_q

from .models import Finding
from .serializers import FindingSerializer, FindingTriageSerializer


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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def run_findings(request, run_id):
    """GET /api/runs/{run_id}/findings -> {findings: [...]} (scoped to the user)."""
    qs = Finding.objects.filter(run_id=run_id).order_by("-created_at")
    if not getattr(request.user, "is_superuser", False):
        qs = qs.filter(finding_scope_q(request.user))
    return Response({"findings": FindingSerializer(qs, many=True).data})
