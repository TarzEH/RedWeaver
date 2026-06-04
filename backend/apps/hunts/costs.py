"""Rough LLM cost estimation from token counts.

Prices are USD per 1M tokens (prompt, completion). They drift over time, so this
is a ballpark for budgeting/visibility, not billing. Unknown models fall back to
a cheap default so the estimate never crashes a run.
"""
from __future__ import annotations

# (prompt_per_1m, completion_per_1m)
_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "o4-mini": (1.10, 4.40),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-sonnet-4": (3.00, 15.00),
    "claude-opus-4": (15.00, 75.00),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-2.0-flash": (0.10, 0.40),
}
_DEFAULT = (0.15, 0.60)  # gpt-4o-mini-class fallback


def _rate(model: str) -> tuple[float, float]:
    m = (model or "").lower()
    for key, price in _PRICES.items():
        if key in m:
            return price
    return _DEFAULT


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    p_rate, c_rate = _rate(model)
    cost = (prompt_tokens / 1_000_000) * p_rate + (completion_tokens / 1_000_000) * c_rate
    return round(cost, 4)
