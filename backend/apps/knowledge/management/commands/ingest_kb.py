"""Ingest the knowledge base into Postgres pgvector (chunk + embed + store).

Chunking is markdown-structure-aware: it splits on headers and paragraph
boundaries and never cuts inside a fenced code block or table, so retrieved
chunks keep whole commands/payloads intact (critical for the OffSec playbook).
"""
import os
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.knowledge.embeddings import embed_texts
from apps.knowledge.models import KbChunk

# Map the on-disk numbered dir to the semantic category vocab the agents pass to
# knowledge_search(category=...) (see KnowledgeQueryInput). Without this the
# stored category ("01-reconnaissance") never matched the agent's ("reconnaissance").
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


def _atomic_blocks(text: str) -> list[str]:
    """Split markdown into atomic blocks (paragraphs, headers, whole code fences)
    that must never be cut internally."""
    blocks: list[str] = []
    cur: list[str] = []
    in_fence = False

    def flush():
        nonlocal cur
        if cur:
            blocks.append("\n".join(cur))
            cur = []

    for line in text.split("\n"):
        stripped = line.lstrip()
        if stripped.startswith("```"):
            if not in_fence:
                flush()
                in_fence = True
                cur = [line]
            else:
                cur.append(line)
                in_fence = False
                flush()
            continue
        if in_fence:
            cur.append(line)
            continue
        if line.startswith("#"):  # header is its own boundary
            flush()
            blocks.append(line)
            continue
        if stripped == "":
            flush()
            continue
        cur.append(line)
    flush()
    return [b for b in blocks if b.strip()]


def chunk_markdown(text: str, size: int = 1200, overlap: int = 150) -> list[str]:
    """Pack atomic markdown blocks into ~size-char chunks without splitting code."""
    chunks: list[str] = []
    buf = ""
    for b in _atomic_blocks(text):
        # A single oversized block (huge code dump) gets hard-split as a fallback.
        if len(b) > size * 1.6:
            if buf.strip():
                chunks.append(buf.strip())
                buf = ""
            for i in range(0, len(b), size):
                chunks.append(b[i:i + size])
            continue
        if buf and len(buf) + len(b) + 1 > size:
            chunks.append(buf.strip())
            buf = buf[-overlap:] if overlap else ""  # carry a little context
        buf = (buf + "\n" + b) if buf else b
    if buf.strip():
        chunks.append(buf.strip())
    return [c for c in chunks if c.strip()]


class Command(BaseCommand):
    help = "Read knowledge-base markdown, chunk, embed (OpenAI), store in pgvector."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default=os.environ.get("KB_SOURCE_DIR", "/app/knowledge-base"),
            help="Directory of knowledge-base markdown files.",
        )

    def handle(self, *args, **opts):
        source = Path(opts["source"])
        md_files = sorted(source.rglob("*.md"))
        if not md_files:
            self.stderr.write(f"No .md files under {source}")
            return

        # (re)build the index
        KbChunk.objects.all().delete()
        total = 0
        for f in md_files:
            rel = str(f.relative_to(source))
            top = rel.split("/")[0]
            category = CATEGORY_MAP.get(top, top.split("-", 1)[-1].replace("-", "_"))
            text = f.read_text(encoding="utf-8", errors="replace")
            # larger chunks for dense cheatsheets/templates/references
            big = any(k in rel for k in ("cheatsheet", "template", "reference"))
            chunks = chunk_markdown(text, size=1800 if big else 1200, overlap=150)
            if not chunks:
                continue
            try:
                vectors = embed_texts(chunks)
            except Exception as exc:
                self.stderr.write(f"embed failed for {rel}: {exc}")
                return
            KbChunk.objects.bulk_create([
                KbChunk(file=rel, category=category, chunk_index=i,
                        content=c, embedding=v)
                for i, (c, v) in enumerate(zip(chunks, vectors))
            ])
            total += len(chunks)
            self.stdout.write(f"  {rel} [{category}]: {len(chunks)} chunks")

        self.stdout.write(self.style.SUCCESS(
            f"Ingested {total} chunks from {len(md_files)} files into pgvector."
        ))
