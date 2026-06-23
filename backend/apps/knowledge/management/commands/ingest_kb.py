"""Ingest the knowledge base into Postgres pgvector (chunk + embed + store).

Files are discovered with ``glob`` and chunked with a markdown-aware LangChain
splitter (see ``apps.knowledge.chunking``): it splits on headers and prefers
fenced-code-block / heading boundaries, so retrieved chunks keep whole
commands/payloads intact (critical for the OffSec playbook).
"""
import glob
import os
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.knowledge.chunking import chunk_markdown
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
        # Discover every markdown file under the source tree with glob.
        md_files = sorted(
            Path(p) for p in glob.glob(str(source / "**" / "*.md"), recursive=True)
        )
        if not md_files:
            self.stderr.write(f"No .md files under {source}")
            return

        # (re)build the index
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
