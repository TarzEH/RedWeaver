"""pgvector similarity search over the KB (fast, accurate RAG retrieval)."""
import logging
import re

from pgvector.django import CosineDistance

from .embeddings import embed_query
from .models import KbChunk

logger = logging.getLogger(__name__)

_STOP = {"the", "a", "an", "of", "to", "for", "and", "or", "in", "on", "is", "how", "with"}


def _keywords(query: str) -> list[str]:
    toks = re.findall(r"[a-z0-9.\-]{3,}", (query or "").lower())
    return [t for t in toks if t not in _STOP]


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

    # Hybrid-lite: pull a wider candidate set via ANN, then re-rank by combining
    # cosine similarity with keyword overlap (catches exact CVE ids / tool flags /
    # payloads that dense embeddings alone miss). No extra index needed.
    rows = _run_query(qv, top_k * 3, category)
    if category and not rows:
        rows = _run_query(qv, top_k * 3, None)  # graceful fallback

    kws = _keywords(query)
    scored = []
    for c in rows:
        cosine = 1.0 - float(c.dist)
        if cosine < min_score:
            continue
        content_l = (c.content or "").lower()
        hits = sum(1 for k in kws if k in content_l)
        boost = min(0.15, 0.03 * hits)  # cap the keyword contribution
        scored.append((cosine + boost, round(cosine, 4), c))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"file": c.file, "category": c.category, "content": c.content, "relevance_score": cos}
        for _combined, cos, c in scored[:top_k]
    ]
