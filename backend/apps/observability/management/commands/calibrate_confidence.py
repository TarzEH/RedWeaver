"""Fit confidence weights against findings analysts have triaged.

    python manage.py calibrate_confidence
    python manage.py calibrate_confidence --run <run-id> --min-samples 25

Reads every finding marked confirmed/remediated (positive) or false_positive
(negative), fits the weights used by :mod:`apps.observability.confidence`, and
prints the ``CONFIDENCE_WEIGHTS`` value to apply. It never writes the weights
itself — applying them is an env change the operator makes deliberately, and the
before/after Brier score is there so it is an informed decision.
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from apps.observability.calibration import (
    NotEnoughData,
    brier_score,
    fit_weights,
    samples_from_findings,
)
from apps.observability.confidence import DEFAULT_WEIGHTS, active_weights

#: A weight fitted on fewer samples than this is flagged as untrustworthy.
LOW_SUPPORT = 10


class Command(BaseCommand):
    help = "Fit confidence weights from human-triaged findings (Brier-optimised)."

    def add_arguments(self, parser):
        parser.add_argument("--run", help="Restrict to one run id")
        parser.add_argument(
            "--min-samples", type=int, default=None,
            help="Minimum labelled findings required per class (default 15)",
        )
        parser.add_argument("--json", dest="json_out", help="Write the full result to this file")

    def handle(self, *args, **opts):
        from apps.findings.models import Finding

        qs = Finding.objects.all()
        if opts["run"]:
            qs = qs.filter(run_id=opts["run"])

        samples = samples_from_findings(qs)
        if not samples:
            raise CommandError(
                "No triaged findings found. Mark findings confirmed or false-positive "
                "in the UI first — calibration needs labels, not scans."
            )

        kwargs = {}
        if opts["min_samples"] is not None:
            kwargs["min_samples"] = opts["min_samples"]

        try:
            result = fit_weights(samples, initial=active_weights(), **kwargs)
        except NotEnoughData as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n{result.samples} labelled findings "
            f"({result.positives} confirmed / {result.negatives} false-positive)"
        ))

        current_brier = brier_score(samples, active_weights())
        self.stdout.write(
            f"  Brier  default={brier_score(samples, DEFAULT_WEIGHTS):.5f}  "
            f"active={current_brier:.5f}  fitted={result.fitted_brier:.5f}"
        )

        if result.improvement <= 0:
            self.stdout.write(self.style.WARNING(
                "  The fit is no better than the weights already in use — keep them."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"  Brier improves by {result.improvement:.5f} (lower is better)"
            ))

        self.stdout.write("\n  feature          weight   (was)   support")
        for name in DEFAULT_WEIGHTS:
            fitted = result.weights[name]
            before = active_weights()[name]
            support = result.feature_support.get(name, 0)
            flag = "  ⚠ low support" if support < LOW_SUPPORT and name != "bias" else ""
            line = f"  {name:<16} {fitted:>6.3f}  {before:>6.3f}   {support:>5}{flag}"
            self.stdout.write(self.style.WARNING(line) if flag else line)

        self.stdout.write(self.style.MIGRATE_HEADING("\nTo apply, set:"))
        self.stdout.write(f"  CONFIDENCE_WEIGHTS='{json.dumps(result.weights)}'")

        if any(
            support < LOW_SUPPORT
            for name, support in result.feature_support.items()
            if name != "bias"
        ):
            self.stdout.write(self.style.WARNING(
                "\n  Some features were exercised by very few labelled findings. Their "
                "weights are fitted to noise — triage more findings before trusting them."
            ))

        if opts["json_out"]:
            with open(opts["json_out"], "w", encoding="utf-8") as fh:
                json.dump(result.to_dict(), fh, indent=2)
            self.stdout.write(self.style.SUCCESS(f"\nWrote {opts['json_out']}"))
