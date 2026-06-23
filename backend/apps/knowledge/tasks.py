"""Celery task: rebuild the pgvector KB with the active embedding config.

Re-index is heavy and destructive (it truncates and re-embeds the whole KB), so
it runs out-of-process and reports progress via KbEmbeddingConfig.status.
"""
import logging

from celery import shared_task
from django.utils import timezone

from .embeddings import probe_dimension
from .ingest import run_ingest, set_embedding_dimension
from .models import KbEmbeddingConfig

logger = logging.getLogger(__name__)


@shared_task(name="knowledge.reindex_kb")
def reindex_kb_task() -> dict:
    """Auto-detect the active model's dimension, retype the vector column if
    needed, then re-embed the entire knowledge base."""
    cfg = KbEmbeddingConfig.get_solo()
    cfg.status = KbEmbeddingConfig.STATUS_RUNNING
    cfg.last_error = ""
    cfg.save(update_fields=["status", "last_error", "updated_at"])

    try:
        # The model is the source of truth for dimension — detect it so the user
        # never has to supply the right number from the UI.
        dim = probe_dimension()
        set_embedding_dimension(dim)
        result = run_ingest()

        cfg.refresh_from_db()
        cfg.dimension = dim
        cfg.chunk_count = result["chunks"]
        cfg.status = KbEmbeddingConfig.STATUS_DONE
        cfg.last_error = ""
        cfg.last_indexed_at = timezone.now()
        cfg.save(update_fields=[
            "dimension", "chunk_count", "status", "last_error",
            "last_indexed_at", "updated_at",
        ])
        return {"ok": True, **result, "dimension": dim}
    except Exception as exc:  # noqa: BLE001
        logger.exception("reindex_kb failed")
        cfg.refresh_from_db()
        cfg.status = KbEmbeddingConfig.STATUS_ERROR
        cfg.last_error = str(exc)[:2000]
        cfg.save(update_fields=["status", "last_error", "updated_at"])
        return {"ok": False, "error": str(exc)}
