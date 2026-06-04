"""pgvector similarity search over the KB (fast, accurate RAG retrieval)."""
import logging

from pgvector.django import CosineDistance

from .embeddings import embed_query
from .models import KbChunk

logger = logging.getLogger(__name__)


def _run_query(qv, top_k: int, category: str | None):
    qs = KbChunk.objects.all()
    if category:
        qs = qs.filter(category=category)
    return list(
        qs.annotate(dist=CosineDistance("embedding", qv)).order_by("dist")[:top_k]
    )


def kb_search(
    query: str,
    top_k: int = 5,
    min_score: float = 0.0,
    category: str | None = None,
) -> list[dict]:
    """Return the top_k most similar KB chunks as
    [{file, category, content, relevance_score}], ordered by cosine similarity.

    ``category`` restricts to a normalized topic (e.g. ``web_attacks``); if the
    filter yields nothing it transparently falls back to a corpus-wide search so
    a mismatched category never starves the caller. ``min_score`` drops chunks
    whose cosine similarity is below the threshold (noise control)."""
    try:
        qv = embed_query(query)
    except Exception:
        logger.warning("kb_search: embedding failed", exc_info=True)
        return []

    rows = _run_query(qv, top_k, category)
    if category and not rows:
        rows = _run_query(qv, top_k, None)  # graceful fallback

    out = []
    for c in rows:
        score = round(1.0 - float(c.dist), 4)  # cosine similarity
        if score < min_score:
            continue
        out.append({
            "file": c.file,
            "category": c.category,
            "content": c.content,
            "relevance_score": score,
        })
    return out
