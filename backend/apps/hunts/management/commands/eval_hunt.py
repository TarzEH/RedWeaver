"""Score a completed hunt against a golden answer key.

This is a **replay**: it reads findings already in the database and scores them
offline. No scan, no LLM call, no cost — so it can run on every change.

    # score one run against one key
    python manage.py eval_hunt --run <run-id> --golden evals/golden/juice-shop.yaml

    # score the latest run for every key that matches a run's target
    python manage.py eval_hunt --all

    # save a baseline, then compare a later run against it
    python manage.py eval_hunt --run <id> --golden <key> --json evals/baseline.json
    python manage.py eval_hunt --run <id> --golden <key> --compare evals/baseline.json

By default the pipeline's *delivered* output is scored: findings triaged or
verified as false positives are excluded, because that is what a user sees.
Pass --raw to score the hunt's unfiltered output instead — the difference
between the two runs is the value the verification pass is adding.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from redweaver_engine.evaluation.scoring import (
    GoldenSetError,
    compare,
    discover_golden,
    load_golden,
    score_findings,
)

DEFAULT_GOLDEN_DIR = "evals/golden"


class Command(BaseCommand):
    help = "Score a hunt's findings against a golden answer key (offline replay)."

    def add_arguments(self, parser):
        parser.add_argument("--run", help="Run id to score (default: latest matching run)")
        parser.add_argument("--golden", help="Path to a golden .yaml/.json file")
        parser.add_argument(
            "--all", action="store_true",
            help=f"Score the latest matching run for every key in {DEFAULT_GOLDEN_DIR}",
        )
        parser.add_argument(
            "--raw", action="store_true",
            help="Include findings marked false-positive (scores the pre-verification output)",
        )
        parser.add_argument("--json", dest="json_out", help="Write results to this JSON file")
        parser.add_argument("--compare", help="Baseline JSON to diff the result against")

    # ------------------------------------------------------------------
    def handle(self, *args, **opts):
        base_dir = Path(getattr(settings, "BASE_DIR", "."))

        if opts["all"]:
            golden_dir = base_dir / DEFAULT_GOLDEN_DIR
            goldens = discover_golden(golden_dir)
            if not goldens:
                raise CommandError(f"No golden sets found in {golden_dir}")
        elif opts["golden"]:
            path = Path(opts["golden"])
            if not path.is_absolute():
                path = base_dir / path
            try:
                goldens = [load_golden(path)]
            except FileNotFoundError as exc:
                raise CommandError(f"Golden set not found: {path}") from exc
            except GoldenSetError as exc:
                raise CommandError(f"Invalid golden set {path}: {exc}") from exc
        else:
            raise CommandError("Pass --golden <file> or --all")

        results = []
        for golden in goldens:
            run = self._resolve_run(opts.get("run"), golden.target)
            if run is None:
                self.stdout.write(self.style.WARNING(
                    f"  skip {golden.name}: no completed run found for target "
                    f"{golden.target or '(unspecified)'}"
                ))
                continue
            results.append(self._score_run(run, golden, raw=opts["raw"]))

        if not results:
            raise CommandError("Nothing scored — no matching runs.")

        payload = [r.to_dict() for r in results]

        if opts["compare"]:
            self._print_comparison(Path(opts["compare"]), payload)

        if opts["json_out"]:
            out = Path(opts["json_out"])
            if not out.is_absolute():
                out = base_dir / out
            out.parent.mkdir(parents=True, exist_ok=True)
            body = payload[0] if len(payload) == 1 else payload
            out.write_text(json.dumps(body, indent=2), encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"\nWrote {out}"))

    # ------------------------------------------------------------------
    def _resolve_run(self, run_id: str | None, target: str):
        from apps.hunts.models import Run, RunStatus

        if run_id:
            run = Run.objects.filter(id=run_id).first()
            if not run:
                raise CommandError(f"Run {run_id} not found")
            return run

        qs = Run.objects.filter(status__in=[RunStatus.COMPLETED, RunStatus.CANCELLED])
        if target:
            # Match on host, so http:// vs https:// and a trailing path do not miss.
            host = target.split("://")[-1].strip("/")
            qs = qs.filter(target__icontains=host)
        return qs.order_by("-created_at").first()

    def _score_run(self, run, golden, raw: bool = False):
        from apps.findings.models import FindingStatus
        from apps.findings.serializers import FindingSerializer

        qs = run.findings.all()
        if not raw:
            qs = qs.exclude(status=FindingStatus.FALSE_POSITIVE)

        findings = FindingSerializer(qs, many=True).data
        duration = None
        if run.started_at and run.completed_at:
            duration = round((run.completed_at - run.started_at).total_seconds(), 1)

        result = score_findings(
            findings,
            golden,
            run_id=str(run.id),
            cost_usd=float(run.cost_usd or 0),
            duration_seconds=duration,
        )
        self._print_result(result, raw=raw)
        return result

    # ------------------------------------------------------------------
    def _print_result(self, result, raw: bool) -> None:
        mode = "raw (pre-verification)" if raw else "delivered (false positives excluded)"
        self.stdout.write(
            f"\n{self.style.MIGRATE_HEADING(result.golden)}  "
            f"run={result.run_id[:8]}  target={result.target or '—'}  [{mode}]"
        )

        for rule_id in result.matched_expectations:
            self.stdout.write(f"  ✓ found   {rule_id}")
        for rule_id in result.missed_expectations:
            self.stdout.write(self.style.WARNING(f"  ✗ MISSED  {rule_id}"))
        for title in result.false_positive_titles[:10]:
            self.stdout.write(self.style.ERROR(f"  ! FP      {title[:70]}"))

        precision = "n/a" if result.precision is None else f"{result.precision:.0%}"
        f1 = "n/a" if result.f1 is None else f"{result.f1:.3f}"
        summary = (
            f"  recall {result.recall:.0%} ({len(result.matched_expectations)}/"
            f"{result.expected_total})   precision {precision}   F1 {f1}   "
            f"noise {result.noise_ratio:.0%} ({result.unscored}/{result.total_findings})"
        )
        self.stdout.write(self.style.SUCCESS(summary))

        cost = "n/a" if result.cost_usd is None else f"${result.cost_usd:.4f}"
        duration = "n/a" if result.duration_seconds is None else f"{result.duration_seconds:.0f}s"
        self.stdout.write(f"  cost {cost}   duration {duration}")

        if result.precision is None:
            self.stdout.write(self.style.WARNING(
                "  precision is n/a: no finding matched an expected or forbidden rule. "
                "Add rules for the recurring titles above to make the run scorable."
            ))

    def _print_comparison(self, baseline_path: Path, payload: list[dict]) -> None:
        if not baseline_path.is_absolute():
            baseline_path = Path(getattr(settings, "BASE_DIR", ".")) / baseline_path
        if not baseline_path.is_file():
            raise CommandError(f"Baseline not found: {baseline_path}")

        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        baselines = baseline if isinstance(baseline, list) else [baseline]
        by_name = {b.get("golden"): b for b in baselines if isinstance(b, dict)}

        self.stdout.write(self.style.MIGRATE_HEADING(f"\nvs baseline {baseline_path.name}"))
        for current in payload:
            before = by_name.get(current["golden"])
            if not before:
                self.stdout.write(self.style.WARNING(
                    f"  {current['golden']}: not in baseline, skipping"
                ))
                continue
            diff = compare(before, current)
            for metric in ("recall", "precision", "f1", "noise_ratio", "cost_usd"):
                entry = diff[metric]
                delta = entry["delta"]
                if delta is None:
                    self.stdout.write(f"  {metric:<12} {entry['before']} -> {entry['after']}")
                    continue
                # Lower is better for these two.
                improved = delta < 0 if metric in ("noise_ratio", "cost_usd") else delta > 0
                style = self.style.SUCCESS if improved else (
                    self.style.ERROR if delta else self.style.NOTICE
                )
                self.stdout.write(style(
                    f"  {metric:<12} {entry['before']} -> {entry['after']}  ({delta:+})"
                ))
            if diff["newly_missed"]:
                self.stdout.write(self.style.ERROR(
                    f"  REGRESSION — no longer found: {', '.join(diff['newly_missed'])}"
                ))
            if diff["newly_found"]:
                self.stdout.write(self.style.SUCCESS(
                    f"  newly found: {', '.join(diff['newly_found'])}"
                ))
