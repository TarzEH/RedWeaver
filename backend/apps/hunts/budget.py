"""Per-run LLM spend ceiling, enforced at task boundaries.

A hunt is a long agentic loop: without a ceiling, a target that keeps producing
tool output can quietly burn far more than intended. This module reads CrewAI's
cumulative usage metrics after each completed task, keeps ``Run.cost_usd`` live
(instead of only writing it once at the end), and raises :class:`BudgetExceeded`
once the ceiling is crossed.

Off by default: a run has no ceiling unless ``Run.budget_usd`` is set or the
``RUN_BUDGET_USD`` environment variable is non-zero.

Enforcement is at *task* granularity, not per token — a single task can overshoot
the ceiling before the next check. Treat it as a circuit breaker, not a hard cap.
"""
from __future__ import annotations

import logging
import os
from decimal import Decimal, InvalidOperation

from .costs import estimate_cost_usd

logger = logging.getLogger(__name__)


class BudgetExceeded(RuntimeError):
    """Raised when a run's cumulative estimated spend passes its ceiling."""


def parse_budget_usd(value) -> Decimal | None:
    """Read an optional spend ceiling supplied by an API caller.

    Returns None for anything absent, non-numeric, zero or negative, which a run
    treats as "no per-run limit" (falling back to the RUN_BUDGET_USD default).

    Zero deliberately maps to None rather than to a real ceiling of $0 — that
    would abort every hunt at the first task boundary. And a malformed value
    must never fail the request: the ceiling is a guard rail, not the point of
    the call.
    """
    if value is None or value == "":
        return None
    try:
        budget = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return budget if budget > 0 else None


def default_budget_usd() -> float:
    """Installation-wide default ceiling; 0 (the default) means unlimited."""
    raw = (os.environ.get("RUN_BUDGET_USD") or "").strip()
    if not raw:
        return 0.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        logger.warning("RUN_BUDGET_USD=%r is not a number; ignoring", raw)
        return 0.0


def usage_from_crew(crew) -> tuple[int, int]:
    """Return (prompt_tokens, completion_tokens) for a crew, or (0, 0).

    CrewAI exposes this as the **method** ``calculate_usage_metrics()``, which
    aggregates each agent's token process and only then caches the result onto
    ``crew.usage_metrics``. The attribute therefore does not exist until the
    method has been called at least once.

    Reading only the attribute — which this did — silently returned (0, 0) on
    every call, so the live cost never updated during a run and the budget
    ceiling could never trip. Prefer the method; fall back to the attribute so a
    crew that only caches a value (or a test double) still works.
    """
    metrics = None
    calculate = getattr(crew, "calculate_usage_metrics", None)
    if callable(calculate):
        try:
            metrics = calculate()
        except Exception:
            logger.debug("calculate_usage_metrics() failed", exc_info=True)
    if metrics is None:
        metrics = getattr(crew, "usage_metrics", None)
    if metrics is None:
        return 0, 0
    prompt = int(getattr(metrics, "prompt_tokens", 0) or 0)
    completion = int(getattr(metrics, "completion_tokens", 0) or 0)
    return prompt, completion


class BudgetGuard:
    """Tracks spend across a run and trips once the ceiling is crossed."""

    def __init__(self, run, model: str, event_callback=None) -> None:
        self._run = run
        self._model = model or ""
        self._callback = event_callback
        self._limit = float(run.budget_usd or 0.0) or default_budget_usd()
        self._tripped = False

    @property
    def limit_usd(self) -> float:
        """The active ceiling; 0.0 means unlimited."""
        return self._limit

    @property
    def enabled(self) -> bool:
        return self._limit > 0

    def check(self, crew) -> None:
        """Refresh the run's live cost and raise if over budget.

        Never raises for reasons other than the budget: a crew that does not
        expose usage metrics simply yields no update.
        """
        try:
            prompt, completion = usage_from_crew(crew)
        except Exception:
            logger.debug("Could not read crew usage metrics", exc_info=True)
            return
        if not (prompt or completion):
            return

        cost = estimate_cost_usd(self._model, prompt, completion)
        self._persist(prompt, completion, cost)

        if not self.enabled or self._tripped or cost < self._limit:
            return

        self._tripped = True
        message = (
            f"Budget ceiling reached: estimated ${cost:.4f} of ${self._limit:.2f} "
            f"({prompt + completion:,} tokens on {self._model or 'unknown model'}). "
            "Hunt stopped early; findings collected so far are kept."
        )
        logger.warning("run %s: %s", self._run.id, message)
        if self._callback:
            try:
                self._callback("hunt_budget_exceeded", {
                    "cost_usd": cost, "limit_usd": self._limit,
                    "prompt_tokens": prompt, "completion_tokens": completion,
                })
            except Exception:
                logger.debug("budget event callback failed", exc_info=True)
        raise BudgetExceeded(message)

    def _persist(self, prompt: int, completion: int, cost: float) -> None:
        """Write live token/cost figures so the UI is not blind until the end."""
        run = self._run
        run.prompt_tokens = prompt
        run.completion_tokens = completion
        run.total_tokens = prompt + completion
        run.cost_usd = cost
        try:
            run.save(update_fields=[
                "prompt_tokens", "completion_tokens", "total_tokens", "cost_usd", "updated_at",
            ])
        except Exception:
            logger.debug("Could not persist interim cost for run %s", run.id, exc_info=True)
