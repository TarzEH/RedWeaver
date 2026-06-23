"""Ingest the knowledge base into Postgres pgvector (chunk + embed + store).

Thin CLI wrapper over apps.knowledge.ingest.run_ingest. Files are discovered
with glob and chunked with a markdown-aware LangChain splitter (see
apps.knowledge.chunking) that keeps fenced code blocks intact.
"""
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.knowledge.ingest import default_source, run_ingest


class Command(BaseCommand):
    help = "Read knowledge-base markdown, chunk, embed, store in pgvector."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default=str(default_source()),
            help="Directory of knowledge-base markdown files.",
        )

    def handle(self, *args, **opts):
        def _log(rel, category, n):
            self.stdout.write(f"  {rel} [{category}]: {n} chunks")

        try:
            result = run_ingest(Path(opts["source"]), on_progress=_log)
        except FileNotFoundError as exc:
            self.stderr.write(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            self.stderr.write(f"ingest failed: {exc}")
            return

        self.stdout.write(self.style.SUCCESS(
            f"Ingested {result['chunks']} chunks from {result['files']} files into pgvector."
        ))
