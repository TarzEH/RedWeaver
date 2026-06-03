"""pgvector similarity search over the KB (fast, accurate RAG retrieval)."""
import logging

from pgvector.django import CosineDistance

from .embeddings import embed_query
from .models import KbChunk

logger = logging.getLogger(__name__)


def kb_search(query: str, top_k: int = 5, min_score: float = 0.0) -> list[dict]:
    """Return the top_k most similar KB chunks as
    [{file, category, content, relevance_score}], ordered by cosine similarity."""
    try:
        qv = embed_query(query)
    except Exception:
        logger.warning("kb_search: embedding failed", exc_info=True)
        return []
    rows = (
        KbChunk.objects.annotate(dist=CosineDistance("embedding", qv))
        .order_by("dist")[:top_k]
    )
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
