"""Align the pgvector embedding column to the configured provider dimension.

The embedding dimension depends on ``settings.KB_EMBED_DIM`` (1536 for OpenAI,
384 for the default local HuggingFace model, etc.). This migration alters the
``vector(N)`` column to match. It is idempotent: if the column already has the
target dimension it does nothing.

Because a dimension change invalidates any vectors already stored (and switching
embedding provider always requires a re-ingest), the column is truncated before
the type change. The HNSW index is dropped and recreated around the alter, since
the index is tied to the column type.
"""
import re

from django.conf import settings
from django.db import migrations
import pgvector.django.vector


def _current_dim(cursor) -> int | None:
    cursor.execute(
        """
        SELECT format_type(a.atttypid, a.atttypmod)
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        WHERE c.relname = 'knowledge_kbchunk' AND a.attname = 'embedding'
        """
    )
    row = cursor.fetchone()
    if not row or not row[0]:
        return None
    m = re.search(r"\((\d+)\)", row[0])  # e.g. 'vector(1536)'
    return int(m.group(1)) if m else None


def _align_dim(apps, schema_editor):
    target = int(getattr(settings, "KB_EMBED_DIM", 1536))
    with schema_editor.connection.cursor() as cur:
        if _current_dim(cur) == target:
            return
        # Drop the index (tied to the column type), clear stale-dim vectors,
        # retype the column, then rebuild the HNSW index to match Meta.
        cur.execute("DROP INDEX IF EXISTS kbchunk_emb_hnsw")
        cur.execute("TRUNCATE TABLE knowledge_kbchunk")
        cur.execute(
            f"ALTER TABLE knowledge_kbchunk "
            f"ALTER COLUMN embedding TYPE vector({target})"
        )
        cur.execute(
            "CREATE INDEX kbchunk_emb_hnsw ON knowledge_kbchunk "
            "USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("knowledge", "0002_kbchunk_hnsw_index"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(_align_dim, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="kbchunk",
                    name="embedding",
                    field=pgvector.django.vector.VectorField(
                        dimensions=int(getattr(settings, "KB_EMBED_DIM", 1536))
                    ),
                ),
            ],
        ),
    ]
