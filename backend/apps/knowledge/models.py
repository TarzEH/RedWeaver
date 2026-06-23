"""Knowledge base stored as pgvector embeddings in Postgres (RAG)."""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from pgvector.django import HnswIndex, VectorField

# Embedding dimensionality, driven by the configured provider (settings.KB_EMBED_DIM):
# OpenAI text-embedding-3-small = 1536, local all-MiniLM-L6-v2 = 384, etc.
# Migration 0003 aligns the actual pgvector column to this value.
EMBED_DIM = int(getattr(settings, "KB_EMBED_DIM", 1536))


class KbChunk(models.Model):
    """A chunk of a knowledge-base document with its embedding vector."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.CharField(max_length=512, db_index=True)
    category = models.CharField(max_length=128, blank=True, default="")
    chunk_index = models.IntegerField(default=0)
    content = models.TextField()
    embedding = VectorField(dimensions=EMBED_DIM)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["file"]),
            HnswIndex(
                name="kbchunk_emb_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]

    def __str__(self) -> str:
        return f"{self.file}#{self.chunk_index}"


class KbEmbeddingConfig(models.Model):
    """Global (singleton) embedding configuration for the pgvector KB.

    Editable from the Settings UI so the embedding provider/model can be changed
    without pre-setting env vars. It is global by design: there is a single
    KbChunk index with a single vector dimension, so the choice must be
    system-wide. ``dimension`` is auto-detected from the model on re-index.
    """

    SINGLETON_ID = 1

    PROVIDER_OPENAI = "openai"
    PROVIDER_HUGGINGFACE = "huggingface"
    PROVIDER_CHOICES = [
        (PROVIDER_OPENAI, "OpenAI"),
        (PROVIDER_HUGGINGFACE, "HuggingFace (offline)"),
    ]

    STATUS_IDLE = "idle"
    STATUS_RUNNING = "running"
    STATUS_DONE = "done"
    STATUS_ERROR = "error"

    id = models.PositiveSmallIntegerField(
        primary_key=True, default=SINGLETON_ID, editable=False
    )
    provider = models.CharField(
        max_length=32, choices=PROVIDER_CHOICES, default=PROVIDER_OPENAI
    )
    model = models.CharField(max_length=128, blank=True, default="")  # blank = provider default
    # Literal default keeps migration state stable; the real value is seeded from
    # settings (migration 0004) and auto-detected from the model on each re-index.
    dimension = models.PositiveIntegerField(default=1536)
    device = models.CharField(max_length=16, default="cpu")  # cpu | cuda (HF only)

    # Re-index status (drives the Settings UI progress/feedback).
    status = models.CharField(max_length=16, default=STATUS_IDLE)
    last_error = models.TextField(blank=True, default="")
    last_indexed_at = models.DateTimeField(null=True, blank=True)
    chunk_count = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "KB embedding config"
        verbose_name_plural = "KB embedding config"

    def __str__(self) -> str:
        return f"KbEmbeddingConfig<{self.provider}:{self.model or 'default'}>"

    @classmethod
    def get_solo(cls) -> "KbEmbeddingConfig":
        obj, _ = cls.objects.get_or_create(id=cls.SINGLETON_ID)
        return obj
