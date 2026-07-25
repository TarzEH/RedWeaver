"""Derive a data-reliability/confidence score (0..1) for a finding.

Signals (all already present in the finding payload / FindingItem schema):
CISA KEV membership, exploitability, CVSS, CVE refs, EPSS, and evidence presence.

The score is a clamped linear sum: ``clamp(sum(weight[f] * feature[f]))``. Those
weights used to be inline magic numbers picked by hand; they are now named and
overridable, so :mod:`apps.observability.calibration` can fit them against
findings humans have actually triaged instead of leaving them a guess.

The defaults reproduce the original hand-tuned behaviour exactly — nothing moves
until someone calibrates. Override without a code change:

    CONFIDENCE_WEIGHTS='{"cisa_kev": 0.30, "has_evidence": 0.15}'

(partial overrides are merged over the defaults).
"""
from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

#: Feature name -> weight. `bias` is the neutral prior applied to every finding.
DEFAULT_WEIGHTS: dict[str, float] = {
    "bias": 0.4,
    # Externally corroborated as exploited in the wild.
    "cisa_kev": 0.25,
    # Exploitability buckets (mutually exclusive).
    "expl_proven": 0.25,
    "expl_likely": 0.15,
    "expl_possible": 0.05,
    "expl_unlikely": -0.1,
    # CVSS buckets (mutually exclusive).
    "cvss_critical": 0.15,   # >= 9.0
    "cvss_high": 0.1,        # >= 7.0
    "cvss_any": 0.05,        # > 0
    # Corroboration.
    "has_cve": 0.05,
    "has_evidence": 0.1,
    # EPSS buckets (mutually exclusive).
    "epss_high": 0.1,        # >= 0.5
    "epss_medium": 0.05,     # >= 0.1
}

_ENV_OVERRIDE = "CONFIDENCE_WEIGHTS"


def _env_weights() -> dict[str, float]:
    raw = (os.environ.get(_ENV_OVERRIDE) or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        logger.warning("%s is not valid JSON; using default weights", _ENV_OVERRIDE)
        return {}
    if not isinstance(data, dict):
        logger.warning("%s must be a JSON object; using default weights", _ENV_OVERRIDE)
        return {}
    out: dict[str, float] = {}
    for key, value in data.items():
        if key not in DEFAULT_WEIGHTS:
            logger.warning("%s: unknown feature %r; ignoring", _ENV_OVERRIDE, key)
            continue
        try:
            out[key] = float(value)
        except (TypeError, ValueError):
            logger.warning("%s: non-numeric weight for %r; ignoring", _ENV_OVERRIDE, key)
    return out


def active_weights() -> dict[str, float]:
    """Defaults merged with the environment override."""
    return {**DEFAULT_WEIGHTS, **_env_weights()}


def extract_features(data: dict) -> dict[str, float]:
    """Turn a finding payload into the 0/1 feature vector the score is built on."""
    features = {name: 0.0 for name in DEFAULT_WEIGHTS}
    features["bias"] = 1.0

    if data.get("cisa_kev"):
        features["cisa_kev"] = 1.0

    expl = (data.get("exploitability") or "unknown").lower()
    if expl in ("proven", "likely", "possible", "unlikely"):
        features[f"expl_{expl}"] = 1.0

    cvss = data.get("cvss_score")
    if isinstance(cvss, (int, float)) and not isinstance(cvss, bool):
        if cvss >= 9.0:
            features["cvss_critical"] = 1.0
        elif cvss >= 7.0:
            features["cvss_high"] = 1.0
        elif cvss > 0:
            features["cvss_any"] = 1.0

    if data.get("cve_ids"):
        features["has_cve"] = 1.0
    if (data.get("evidence") or "").strip():
        features["has_evidence"] = 1.0

    epss = data.get("epss_score")
    if isinstance(epss, (int, float)) and not isinstance(epss, bool):
        if epss >= 0.5:
            features["epss_high"] = 1.0
        elif epss >= 0.1:
            features["epss_medium"] = 1.0

    return features


def score_features(features: dict[str, float], weights: dict[str, float] | None = None) -> float:
    """Clamped linear score for an already-extracted feature vector."""
    w = active_weights() if weights is None else weights
    total = sum(w.get(name, 0.0) * value for name, value in features.items())
    return max(0.0, min(1.0, round(total, 3)))


def derive_confidence(data: dict, weights: dict[str, float] | None = None) -> float:
    """Confidence (0..1) that a finding is real, from its corroborating signals."""
    return score_features(extract_features(data), weights)
