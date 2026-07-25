"""Fit :mod:`apps.observability.confidence` weights against triaged findings.

The default weights are one person's intuition about how much a CISA KEV hit or
a bare CVE id should count. Once analysts have triaged findings as confirmed or
false-positive, that intuition can be replaced with a measurement.

The optimiser is deliberately plain: coordinate descent on the *same* clamped
linear model that ships in production, minimising Brier score (mean squared
error against the 0/1 label). No numpy, no sklearn, no new dependency, and the
fitted weights drop straight into ``CONFIDENCE_WEIGHTS``.

Calibration on a handful of labels is worse than not calibrating at all, so
:func:`fit_weights` refuses to run below :data:`MIN_SAMPLES` per class and says
so rather than returning confident nonsense.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Sequence

from .confidence import DEFAULT_WEIGHTS, score_features

logger = logging.getLogger(__name__)

#: Minimum labelled findings *per class* before a fit is allowed.
MIN_SAMPLES = 15

#: Weights are bounded so one over-represented signal cannot dominate the score.
WEIGHT_BOUNDS = (-0.5, 0.6)


class NotEnoughData(RuntimeError):
    """Raised when the labelled set is too small to calibrate on."""


@dataclass
class FitResult:
    """Outcome of a calibration run."""

    weights: dict[str, float]
    baseline_brier: float
    fitted_brier: float
    samples: int
    positives: int
    negatives: int
    feature_support: dict[str, int] = field(default_factory=dict)

    @property
    def improvement(self) -> float:
        """Reduction in Brier score; positive means the fit is better."""
        return round(self.baseline_brier - self.fitted_brier, 5)

    def to_dict(self) -> dict:
        return {
            "weights": self.weights,
            "baseline_brier": self.baseline_brier,
            "fitted_brier": self.fitted_brier,
            "improvement": self.improvement,
            "samples": self.samples,
            "positives": self.positives,
            "negatives": self.negatives,
            "feature_support": self.feature_support,
        }


def brier_score(
    samples: Sequence[tuple[dict[str, float], int]],
    weights: dict[str, float],
) -> float:
    """Mean squared error of the clamped linear score against the labels."""
    if not samples:
        return 0.0
    total = sum((score_features(f, weights) - label) ** 2 for f, label in samples)
    return round(total / len(samples), 5)


def feature_support(samples: Sequence[tuple[dict[str, float], int]]) -> dict[str, int]:
    """How many labelled samples actually exercise each feature.

    A weight fitted on two samples is noise; the caller shows this table so a
    low-support weight is visibly untrustworthy rather than quietly wrong.
    """
    support = {name: 0 for name in DEFAULT_WEIGHTS}
    for features, _ in samples:
        for name, value in features.items():
            if value and name != "bias":
                support[name] = support.get(name, 0) + 1
    support["bias"] = len(samples)
    return support


def fit_weights(
    samples: Sequence[tuple[dict[str, float], int]],
    initial: dict[str, float] | None = None,
    rounds: int = 40,
    min_samples: int = MIN_SAMPLES,
) -> FitResult:
    """Coordinate-descent fit of the confidence weights.

    ``samples`` is a sequence of ``(feature_vector, label)`` where label is 1 for
    a confirmed finding and 0 for a false positive.
    """
    positives = sum(1 for _, label in samples if label == 1)
    negatives = len(samples) - positives
    if positives < min_samples or negatives < min_samples:
        raise NotEnoughData(
            f"Need at least {min_samples} confirmed and {min_samples} false-positive "
            f"findings to calibrate; have {positives} confirmed / {negatives} false-positive. "
            "Triage more findings first — a fit on this little data is worse than the default."
        )

    base = dict(initial or DEFAULT_WEIGHTS)
    baseline = brier_score(samples, base)

    weights = dict(base)
    low, high = WEIGHT_BOUNDS
    step = 0.1
    best = baseline

    for _ in range(rounds):
        improved = False
        for name in DEFAULT_WEIGHTS:
            for delta in (step, -step):
                candidate = dict(weights)
                candidate[name] = max(low, min(high, round(candidate[name] + delta, 4)))
                if candidate[name] == weights[name]:
                    continue
                score = brier_score(samples, candidate)
                if score < best:
                    best, weights, improved = score, candidate, True
        if not improved:
            step /= 2
            if step < 0.005:
                break

    return FitResult(
        weights={k: round(v, 4) for k, v in weights.items()},
        baseline_brier=baseline,
        fitted_brier=best,
        samples=len(samples),
        positives=positives,
        negatives=negatives,
        feature_support=feature_support(samples),
    )


def samples_from_findings(findings) -> list[tuple[dict[str, float], int]]:
    """Build a labelled training set from triaged Finding rows.

    Only human-meaningful labels are used: ``confirmed``/``remediated`` are
    positives, ``false_positive`` is a negative. Everything else is unlabelled
    and excluded.
    """
    from .confidence import extract_features

    positive_states = {"confirmed", "remediated"}
    samples = []
    for finding in findings:
        status = str(getattr(finding, "status", "") or "").lower()
        if status in positive_states:
            label = 1
        elif status == "false_positive":
            label = 0
        else:
            continue
        payload = {
            "cisa_kev": getattr(finding, "cisa_kev", False),
            "exploitability": getattr(finding, "exploitability", "unknown"),
            "cvss_score": getattr(finding, "cvss_score", None),
            "cve_ids": getattr(finding, "cve_ids", None) or [],
            "evidence": getattr(finding, "evidence", "") or "",
            "epss_score": getattr(finding, "epss_score", None),
        }
        samples.append((extract_features(payload), label))
    return samples
