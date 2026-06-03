"""Knowledge endpoints — backed by the Postgres pgvector RAG."""
from django.db.models import Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import KbChunk
from .search import kb_search


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def knowledge_health(request):
    chunks = KbChunk.objects.count()
    files = KbChunk.objects.values("file").distinct().count()
    return Response({
        "status": "ok" if chunks else "empty",
        "backend": "postgres+pgvector",
        "documents_indexed": chunks,
        "files_indexed": files,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def knowledge_query(request):
    data = request.data or {}
    query = data.get("query", "")
    top_k = int(data.get("top_k", 5) or 5)
    if not query:
        return Response({"results": [], "error": "query required"}, status=400)
    results = kb_search(query, top_k=top_k)
    return Response({
        "status": "success",
        "query": query,
        "results_count": len(results),
        "results": results,
    })
