"""Knowledge base stored as pgvector embeddings in Postgres (RAG)."""
import uuid

from django.db import models
from django.utils import timezone
from pgvector.django import HnswIndex, VectorField

# OpenAI text-embedding-3-small dimensionality.
EMBED_DIM = 1536


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
