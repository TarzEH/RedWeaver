"""Ragas evaluation of the pgvector RAG (context recall/precision, faithfulness,
answer relevancy) over a golden Q/A set.

    python manage.py eval_kb_ragas [--k 5] [--no-generation] [--json out.json]
                                   [--fail-under]   # exit 1 if a threshold fails (CI)

Reuses RedWeaver's multi-provider LLM + embeddings as the judge, so it runs with
OpenAI/Anthropic/Google or fully offline (Ollama + local HF embeddings).
"""
import json

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Evaluate KB RAG quality with Ragas (context recall/precision, faithfulness)."

    def add_arguments(self, parser):
        parser.add_argument("--k", type=int, default=5, help="retriever top_k")
        parser.add_argument("--no-generation", action="store_true",
                            help="retrieval-only metrics (skip LLM answer generation)")
        parser.add_argument("--json", dest="json_out", default="",
                            help="write the full result (incl. per-sample) to this path")
        parser.add_argument("--fail-under", action="store_true",
                            help="exit non-zero if any metric is below its threshold (CI)")
        parser.add_argument("--timeout", type=int, default=300)

    def handle(self, *args, **opts):
        try:
            from apps.knowledge.eval.ragas_eval import run_ragas_eval
        except ImportError as exc:
            self.stderr.write(f"ragas not installed: {exc}\n  pip install ragas")
            return

        try:
            result = run_ragas_eval(
                top_k=opts["k"],
                with_generation=not opts["no_generation"],
                timeout=opts["timeout"],
            )
        except Exception as exc:  # noqa: BLE001
            self.stderr.write(f"eval failed: {exc}")
            return

        self.stdout.write(
            f"\nRagas eval — {result['n_samples']} samples, top_k={result['top_k']}, "
            f"generation={'on' if result['with_generation'] else 'off'}\n"
        )
        for metric, score in result["scores"].items():
            thr = result["thresholds"].get(metric)
            shown = "n/a" if score is None else f"{score:.3f}"
            flag = ""
            if thr is not None and score is not None:
                flag = "  ✓" if score >= thr else f"  ✗ (< {thr})"
            self.stdout.write(f"  {metric:42} {shown}{flag}")

        if opts["json_out"]:
            with open(opts["json_out"], "w", encoding="utf-8") as fh:
                json.dump(result, fh, indent=2, default=str)
            self.stdout.write(f"\nWrote {opts['json_out']}")

        if result["passed"]:
            self.stdout.write(self.style.SUCCESS("\nPASS — all metrics meet thresholds."))
        else:
            failed = ", ".join(result["failures"])
            self.stdout.write(self.style.ERROR(f"\nFAIL — below threshold: {failed}"))
            if opts["fail_under"]:
                raise SystemExit(1)
