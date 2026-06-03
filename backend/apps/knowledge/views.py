"""Knowledge endpoints — proxy to the knowledge microservice."""
import httpx
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

BASE = settings.KNOWLEDGE_SERVICE_URL.rstrip("/")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def knowledge_health(request):
    try:
        r = httpx.get(f"{BASE}/health", timeout=10)
        return Response(r.json(), status=r.status_code)
    except Exception as exc:
        return Response(
            {"status": "unreachable", "documents_indexed": 0,
             "files_indexed": 0, "error": str(exc)},
            status=503,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def knowledge_query(request):
    try:
        r = httpx.post(
            f"{BASE}/api/knowledge/query", json=request.data or {}, timeout=30
        )
        return Response(r.json(), status=r.status_code)
    except Exception as exc:
        return Response({"results": [], "error": str(exc)}, status=503)
