"""Ingest the knowledge base into Postgres pgvector (chunk + embed + store)."""
import os
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.knowledge.embeddings import embed_texts
from apps.knowledge.models import KbChunk


def chunk_text(text: str, size: int = 1000, overlap: int = 200) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        piece = text[start:start + size]
        if piece.strip():
            chunks.append(piece)
        start += size - overlap
    return chunks


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
            category = rel.split("/")[0]
            text = f.read_text(encoding="utf-8", errors="replace")
            # larger chunks for cheatsheets/templates
            big = any(k in rel for k in ("cheatsheet", "template", "reference"))
            chunks = chunk_text(text, size=1600 if big else 1000, overlap=200)
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
            self.stdout.write(f"  {rel}: {len(chunks)} chunks")

        self.stdout.write(self.style.SUCCESS(
            f"Ingested {total} chunks from {len(md_files)} files into pgvector."
        ))
