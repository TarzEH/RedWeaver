"""Knowledge endpoints — backed by the Postgres pgvector RAG."""
from django.db.models import Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import KbChunk
from .search import kb_search


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def knowledge_categories(request):
    """Distinct KB categories with document/file counts (drives the nav tree)."""
    rows = (
        KbChunk.objects.values("category")
        .annotate(chunks=Count("id"), files=Count("file", distinct=True))
        .order_by("category")
    )
    return Response({"categories": list(rows)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def knowledge_files(request):
    """List KB files (optionally ?category=), with title + chunk count."""
    qs = KbChunk.objects.all()
    cat = request.query_params.get("category")
    if cat:
        qs = qs.filter(category=cat)
    rows = (
        qs.values("file", "category")
        .annotate(chunks=Count("id"))
        .order_by("file")
    )
    out = [{
        "file": r["file"],
        "category": r["category"],
        "chunks": r["chunks"],
        "title": r["file"].rsplit("/", 1)[-1].replace(".md", "").replace("-", " ").title(),
    } for r in rows]
    return Response({"files": out})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def knowledge_document(request):
    """Reassemble a full KB document from its chunks (ordered by chunk_index)."""
    file = request.query_params.get("file")
    if not file:
        return Response({"error": "file required"}, status=400)
    chunks = list(
        KbChunk.objects.filter(file=file).order_by("chunk_index").values("content", "category")
    )
    if not chunks:
        return Response({"error": "not found"}, status=404)
    return Response({
        "file": file,
        "category": chunks[0]["category"],
        "title": file.rsplit("/", 1)[-1].replace(".md", "").replace("-", " ").title(),
        "content": "\n\n".join(c["content"] for c in chunks),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def knowledge_ask(request):
    """RAG Q&A over the KB corpus — grounded answer with KB-file citations."""
    question = (request.data.get("question") or "").strip()
    if not question:
        return Response({"error": "question required"}, status=400)
    hits = kb_search(question, top_k=6, min_score=0.15)
    if not hits:
        return Response({"answer": "No relevant knowledge-base content found.", "sources": []})

    from apps.accounts.keys import keys_provider_for_user
    from apps.hunts.crew_factory import _build_crewai_llm
    from redweaver_engine.llm_factory import LLMFactory

    kp = keys_provider_for_user(request.user)
    lf = LLMFactory(kp)
    if not lf.has_api_key():
        return Response({"error": "No LLM API key configured"}, status=400)

    context = "\n\n".join(f"[{h['file']}]\n{h['content'][:1500]}" for h in hits)
    prompt = (
        "You are a security knowledge assistant. Answer the question using ONLY the "
        "knowledge-base excerpts below. Be concise and practical; include exact "
        "commands when relevant and cite the KB filename in brackets.\n\n"
        f"KNOWLEDGE BASE:\n{context}\n\nQUESTION: {question}"
    )
    try:
        llm = _build_crewai_llm(lf, kp.get_all())
        answer = llm.call([{"role": "user", "content": prompt}])
    except Exception as exc:  # noqa: BLE001
        return Response({"error": str(exc)}, status=500)
    sources = sorted({h["file"] for h in hits})
    return Response({"answer": str(answer), "sources": sources, "question": question})


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
