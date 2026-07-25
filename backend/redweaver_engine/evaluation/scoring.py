"""Score a hunt's findings against a golden answer key.

``eval_kb`` already measures whether the knowledge base retrieves the right
document. Nothing measured whether the *hunt* found the right vulnerabilities —
so every prompt, model and tool change was a guess. This module is the missing
half: given the findings a run produced and a hand-written answer key for that
target, it reports recall (what we missed), precision (what we invented) and
noise (what we reported that the key says nothing about).

Everything here is pure — no Django, no network, no LLM. Scoring an existing run
is a replay: free, deterministic, and instant, so it can run on every change.

Three outcomes per reported finding, deliberately kept distinct:

* **true positive** — matches an ``expected`` entry.
* **false positive** — matches a ``forbidden`` entry (a known-bogus claim for
  this target).
* **unscored** — the key is silent about it. Counted and reported, never
  silently folded into precision, because "the answer key does not mention it"
  is not the same as "it is wrong".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


class GoldenSetError(ValueError):
    """Raised when a golden file is missing required structure."""


# ---------------------------------------------------------------------------
# Golden set loading
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Expectation:
    """One rule in an answer key: a vulnerability that should (or must not) appear."""

    id: str
    title_any: tuple[str, ...] = ()
    url_any: tuple[str, ...] = ()
    min_severity: str = ""
    note: str = ""

    def matches(self, finding: Mapping[str, Any]) -> bool:
        """True when a finding satisfies every constraint this rule declares."""
        haystack = " ".join(
            str(finding.get(key) or "") for key in ("title", "description")
        ).lower()
        if self.title_any and not any(t.lower() in haystack for t in self.title_any):
            return False

        if self.url_any:
            url = str(finding.get("affected_url") or "").lower()
            if not any(u.lower() in url for u in self.url_any):
                return False

        if self.min_severity:
            floor = SEVERITY_RANK.get(self.min_severity.lower(), 0)
            actual = SEVERITY_RANK.get(str(finding.get("severity") or "info").lower(), 0)
            if actual < floor:
                return False

        return True


@dataclass(frozen=True)
class GoldenSet:
    """An answer key for one target."""

    name: str
    target: str = ""
    notes: str = ""
    expected: tuple[Expectation, ...] = ()
    forbidden: tuple[Expectation, ...] = ()


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(v) for v in value if str(v).strip())


def _parse_expectations(items: Any, kind: str) -> tuple[Expectation, ...]:
    if items is None:
        return ()
    if not isinstance(items, list):
        raise GoldenSetError(f"'{kind}' must be a list")
    out = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise GoldenSetError(f"{kind}[{index}] must be a mapping")
        rule = Expectation(
            id=str(item.get("id") or f"{kind}-{index}"),
            title_any=_as_tuple(item.get("title_any")),
            url_any=_as_tuple(item.get("url_any")),
            min_severity=str(item.get("min_severity") or ""),
            note=str(item.get("note") or ""),
        )
        if not (rule.title_any or rule.url_any):
            raise GoldenSetError(
                f"{kind}[{index}] ({rule.id}) declares no title_any/url_any, so it would "
                "match every finding"
            )
        out.append(rule)
    return tuple(out)


def parse_golden(data: Mapping[str, Any], name: str = "") -> GoldenSet:
    """Build a :class:`GoldenSet` from a parsed YAML/JSON mapping."""
    if not isinstance(data, Mapping):
        raise GoldenSetError("golden set must be a mapping")
    expected = _parse_expectations(data.get("expected"), "expected")
    if not expected:
        raise GoldenSetError("golden set must declare at least one 'expected' entry")
    return GoldenSet(
        name=str(data.get("name") or name or "unnamed"),
        target=str(data.get("target") or ""),
        notes=str(data.get("notes") or ""),
        expected=expected,
        forbidden=_parse_expectations(data.get("forbidden"), "forbidden"),
    )


def load_golden(path: str | Path) -> GoldenSet:
    """Load a golden set from a ``.yaml`` / ``.json`` file."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - yaml is a hard dependency
            raise GoldenSetError("PyYAML is required to read .yaml golden sets") from exc
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    return parse_golden(data or {}, name=p.stem)


def discover_golden(directory: str | Path) -> list[GoldenSet]:
    """Load every golden set in a directory, sorted by file name."""
    d = Path(directory)
    if not d.is_dir():
        return []
    out = []
    for path in sorted(d.iterdir()):
        if path.suffix in (".yaml", ".yml", ".json"):
            out.append(load_golden(path))
    return out


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

@dataclass
class EvalResult:
    """Scores for one run against one golden set."""

    golden: str
    target: str = ""
    run_id: str = ""
    total_findings: int = 0
    expected_total: int = 0
    matched_expectations: list[str] = field(default_factory=list)
    missed_expectations: list[str] = field(default_factory=list)
    true_positives: int = 0
    false_positives: int = 0
    unscored: int = 0
    false_positive_titles: list[str] = field(default_factory=list)
    cost_usd: float | None = None
    duration_seconds: float | None = None

    @property
    def recall(self) -> float:
        if not self.expected_total:
            return 0.0
        return round(len(self.matched_expectations) / self.expected_total, 4)

    @property
    def precision(self) -> float | None:
        """None when nothing was scorable — an honest 'unknown', not 1.0."""
        scored = self.true_positives + self.false_positives
        if not scored:
            return None
        return round(self.true_positives / scored, 4)

    @property
    def f1(self) -> float | None:
        precision = self.precision
        if precision is None:
            return None
        if precision + self.recall == 0:
            return 0.0
        return round(2 * precision * self.recall / (precision + self.recall), 4)

    @property
    def noise_ratio(self) -> float:
        """Share of reported findings the answer key says nothing about."""
        if not self.total_findings:
            return 0.0
        return round(self.unscored / self.total_findings, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "golden": self.golden,
            "target": self.target,
            "run_id": self.run_id,
            "total_findings": self.total_findings,
            "expected_total": self.expected_total,
            "matched": len(self.matched_expectations),
            "matched_expectations": self.matched_expectations,
            "missed_expectations": self.missed_expectations,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_positive_titles": self.false_positive_titles,
            "unscored": self.unscored,
            "recall": self.recall,
            "precision": self.precision,
            "f1": self.f1,
            "noise_ratio": self.noise_ratio,
            "cost_usd": self.cost_usd,
            "duration_seconds": self.duration_seconds,
        }


def score_findings(
    findings: Iterable[Mapping[str, Any]],
    golden: GoldenSet,
    run_id: str = "",
    cost_usd: float | None = None,
    duration_seconds: float | None = None,
) -> EvalResult:
    """Score a list of finding dicts against an answer key."""
    findings = [f for f in findings if isinstance(f, Mapping)]

    result = EvalResult(
        golden=golden.name,
        target=golden.target,
        run_id=run_id,
        total_findings=len(findings),
        expected_total=len(golden.expected),
        cost_usd=cost_usd,
        duration_seconds=duration_seconds,
    )

    matched_ids: set[str] = set()
    for finding in findings:
        hits = [rule.id for rule in golden.expected if rule.matches(finding)]
        if hits:
            matched_ids.update(hits)
            result.true_positives += 1
            continue
        if any(rule.matches(finding) for rule in golden.forbidden):
            result.false_positives += 1
            title = str(finding.get("title") or "").strip()
            if title:
                result.false_positive_titles.append(title)
            continue
        result.unscored += 1

    result.matched_expectations = sorted(matched_ids)
    result.missed_expectations = sorted(
        rule.id for rule in golden.expected if rule.id not in matched_ids
    )
    return result


def compare(baseline: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    """Delta between two :meth:`EvalResult.to_dict` payloads.

    ``None`` for a metric means it was unavailable on one side, so no delta is
    computed rather than treating a missing value as zero.
    """
    metrics = (
        "recall", "precision", "f1", "noise_ratio",
        "true_positives", "false_positives", "unscored",
        "total_findings", "cost_usd", "duration_seconds",
    )
    out: dict[str, Any] = {}
    for metric in metrics:
        before, after = baseline.get(metric), current.get(metric)
        if isinstance(before, (int, float)) and isinstance(after, (int, float)):
            out[metric] = {
                "before": before,
                "after": after,
                "delta": round(after - before, 4),
            }
        else:
            out[metric] = {"before": before, "after": after, "delta": None}

    before_missed = set(baseline.get("missed_expectations") or [])
    after_missed = set(current.get("missed_expectations") or [])
    out["newly_missed"] = sorted(after_missed - before_missed)
    out["newly_found"] = sorted(before_missed - after_missed)
    return out
