"""Shared KB ingestion core: discover -> chunk -> embed -> store in pgvector.

Used by both the ``ingest_kb`` management command and the ``reindex_kb_task``
Celery task. Also exposes ``set_embedding_dimension`` to retype the pgvector
column when the embedding model's dimension changes.
"""
import glob
import os
import re
from pathlib import Path

from django.db import connection

from .chunking import chunk_markdown
from .embeddings import embed_texts
from .models import KbChunk

# Map the on-disk numbered dir to the semantic category vocab the agents pass to
# knowledge_search(category=...). Without this the stored category
# ("01-reconnaissance") never matched the agent's ("reconnaissance").
CATEGORY_MAP = {
    "01-reconnaissance": "reconnaissance",
    "02-web-attacks": "web_attacks",
    "03-vulnerability-scanning": "vulnerability_scanning",
    "04-exploitation": "exploitation",
    "05-privilege-escalation": "privilege_escalation",
    "06-tunneling-and-pivoting": "tunneling",
    "07-password-attacks": "password_attacks",
    "08-active-directory": "active_directory",
    "09-post-exploitation": "post_exploitation",
    "10-evasion-techniques": "av_evasion",
    "11-cloud-security": "cloud_security",
    "12-command-and-control": "c2_frameworks",
    "13-reporting-templates": "reporting",
}


def default_source() -> Path:
    return Path(os.environ.get("KB_SOURCE_DIR", "/app/knowledge-base"))


def discover_files(source: Path) -> list[Path]:
    """List every markdown file under ``source`` with glob."""
    return sorted(Path(p) for p in glob.glob(str(source / "**" / "*.md"), recursive=True))


def current_column_dim() -> int | None:
    """Read the current pgvector dimension of knowledge_kbchunk.embedding."""
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT format_type(a.atttypid, a.atttypmod)
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            WHERE c.relname = 'knowledge_kbchunk' AND a.attname = 'embedding'
            """
        )
        row = cur.fetchone()
    if not row or not row[0]:
        return None
    m = re.search(r"\((\d+)\)", row[0])  # 'vector(1536)'
    return int(m.group(1)) if m else None


def set_embedding_dimension(dim: int) -> bool:
    """Retype the embedding column to ``vector(dim)`` if it differs.

    Returns True if the column was altered. A dimension change invalidates stored
    vectors, so the table is truncated and the HNSW index rebuilt around the alter.
    """
    dim = int(dim)
    if current_column_dim() == dim:
        return False
    with connection.cursor() as cur:
        cur.execute("DROP INDEX IF EXISTS kbchunk_emb_hnsw")
        cur.execute("TRUNCATE TABLE knowledge_kbchunk")
        cur.execute(
            f"ALTER TABLE knowledge_kbchunk ALTER COLUMN embedding TYPE vector({dim})"
        )
        # pgvector's HNSW index supports at most 2000 dimensions. For larger
        # models (e.g. text-embedding-3-large = 3072) skip the ANN index; cosine
        # search still works via a sequential scan, just slower.
        if dim <= 2000:
            cur.execute(
                "CREATE INDEX kbchunk_emb_hnsw ON knowledge_kbchunk "
                "USING hnsw (embedding vector_cosine_ops) "
                "WITH (m = 16, ef_construction = 64)"
            )
    return True


def run_ingest(source: Path | None = None, on_progress=None) -> dict:
    """Chunk, embed, and store every KB markdown file. Rebuilds the index.

    ``on_progress(rel, category, n_chunks)`` is called per file if supplied.
    Returns ``{"files": int, "chunks": int}``.
    """
    source = Path(source) if source else default_source()
    md_files = discover_files(source)
    if not md_files:
        raise FileNotFoundError(f"No .md files under {source}")

    KbChunk.objects.all().delete()
    total = 0
    for f in md_files:
        rel = str(f.relative_to(source)).replace(os.sep, "/")
        top = rel.split("/")[0]
        category = CATEGORY_MAP.get(top, top.split("-", 1)[-1].replace("-", "_"))
        text = f.read_text(encoding="utf-8", errors="replace")
        # larger chunks for dense cheatsheets/templates/references
        big = any(k in rel for k in ("cheatsheet", "template", "reference"))
        chunks = chunk_markdown(text, size=1800 if big else 1200, overlap=150)
        if not chunks:
            continue
        vectors = embed_texts(chunks)
        KbChunk.objects.bulk_create([
            KbChunk(file=rel, category=category, chunk_index=i, content=c, embedding=v)
            for i, (c, v) in enumerate(zip(chunks, vectors))
        ])
        total += len(chunks)
        if on_progress:
            on_progress(rel, category, len(chunks))

    return {"files": len(md_files), "chunks": total}
