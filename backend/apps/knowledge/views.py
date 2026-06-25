"""Knowledge endpoints — backed by the Postgres pgvector RAG."""
import os

from django.db.models import Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import KbChunk, KbEmbeddingConfig
from .search import kb_search

# Curated suggestions for the Settings embedding dropdowns (dimension is still
# auto-detected from the model on re-index; these are only UI hints).
OPENAI_EMBED_MODELS = [
    {"id": "text-embedding-3-small", "dim": 1536, "label": "text-embedding-3-small (1536)"},
    {"id": "text-embedding-3-large", "dim": 3072, "label": "text-embedding-3-large (3072)"},
]
HF_EMBED_MODELS = [
    {"id": "sentence-transformers/all-MiniLM-L6-v2", "dim": 384, "label": "all-MiniLM-L6-v2 (384, fast)"},
    {"id": "BAAI/bge-small-en-v1.5", "dim": 384, "label": "bge-small-en-v1.5 (384)"},
    {"id": "BAAI/bge-base-en-v1.5", "dim": 768, "label": "bge-base-en-v1.5 (768)"},
    {"id": "BAAI/bge-large-en-v1.5", "dim": 1024, "label": "bge-large-en-v1.5 (1024)"},
    {"id": "intfloat/e5-base-v2", "dim": 768, "label": "e5-base-v2 (768)"},
]


def _serialize_embed_config(cfg: KbEmbeddingConfig) -> dict:
    return {
        "provider": cfg.provider,
        "model": cfg.model,
        "dimension": cfg.dimension,
        "device": cfg.device,
        "status": cfg.status,
        "last_error": cfg.last_error,
        "last_indexed_at": cfg.last_indexed_at.isoformat() if cfg.last_indexed_at else None,
        "chunk_count": cfg.chunk_count,
        "openai_key_configured": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
        "providers": [
            {"id": "openai", "label": "OpenAI", "needs_key": True, "models": OPENAI_EMBED_MODELS},
            {"id": "huggingface", "label": "HuggingFace (offline)", "needs_key": False, "models": HF_EMBED_MODELS},
        ],
    }


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
        llm = lf.build_langchain_chat_model()
        answer = llm.invoke(prompt).content
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


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def embedding_config(request):
    """GET the global embedding config (+ provider/model options & re-index status);
    POST to update provider/model/device. Changing these does NOT re-embed — the
    caller must trigger /api/knowledge/reindex afterwards."""
    cfg = KbEmbeddingConfig.get_solo()
    if request.method == "POST":
        data = request.data or {}
        provider = str(data.get("provider", cfg.provider)).lower()
        valid = {c[0] for c in KbEmbeddingConfig.PROVIDER_CHOICES}
        if provider not in valid:
            return Response({"error": f"invalid provider (use {sorted(valid)})"}, status=400)
        cfg.provider = provider
        if "model" in data:
            cfg.model = str(data.get("model") or "").strip()
        if "device" in data:
            cfg.device = (str(data.get("device") or "cpu").strip() or "cpu")
        cfg.save(update_fields=["provider", "model", "device", "updated_at"])
    return Response(_serialize_embed_config(cfg))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reindex_knowledge(request):
    """Kick off a background re-index with the active embedding config.
    Auto-detects the model dimension, retypes the pgvector column, re-embeds."""
    cfg = KbEmbeddingConfig.get_solo()
    if cfg.status == KbEmbeddingConfig.STATUS_RUNNING:
        return Response(
            {"error": "re-index already running", **_serialize_embed_config(cfg)},
            status=409,
        )
    cfg.status = KbEmbeddingConfig.STATUS_RUNNING
    cfg.last_error = ""
    cfg.save(update_fields=["status", "last_error", "updated_at"])

    from .tasks import reindex_kb_task

    reindex_kb_task.delay()
    return Response(_serialize_embed_config(cfg), status=202)
