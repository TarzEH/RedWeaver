"""Rough LLM cost estimation from token counts.

Prices are USD per 1M tokens (prompt, completion). They drift constantly, so
this is a ballpark for budgeting/visibility, not billing.

Two things this module is careful about, because the previous version got both
wrong and silently under-reported every run on a newer model:

1. **Longest match wins.** Matching is substring-based (model ids carry date
   and revision suffixes), so ``gpt-4o-mini`` must be tested before ``gpt-4o``
   regardless of dict order.
2. **Unknown models stay visible.** A model with no price entry is reported by
   :func:`is_priced`, so callers can label the number as a guess instead of
   presenting a gpt-4o-mini-class price as fact.

Extend or correct the table without a code change:

    REDWEAVER_MODEL_PRICES='{"gpt-5.3": [1.25, 10.0], "my-local-model": [0, 0]}'
"""
from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

# (prompt_per_1m, completion_per_1m). Approximate list prices — correct them via
# REDWEAVER_MODEL_PRICES rather than editing this table in a deployment.
_PRICES: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-5-nano": (0.05, 0.40),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5": (1.25, 10.00),
    "o3-mini": (1.10, 4.40),
    "o4-mini": (1.10, 4.40),
    "o3": (2.00, 8.00),
    # Anthropic
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-haiku-4": (1.00, 5.00),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-7-sonnet": (3.00, 15.00),
    "claude-sonnet-4": (3.00, 15.00),
    "claude-opus-4": (15.00, 75.00),
    # Google
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.00),
    # Self-hosted — no per-token charge.
    "ollama/": (0.0, 0.0),
}

_DEFAULT = (0.15, 0.60)  # gpt-4o-mini-class fallback for unpriced models

_ENV_OVERRIDE = "REDWEAVER_MODEL_PRICES"
_warned_unknown: set[str] = set()


def _env_prices() -> dict[str, tuple[float, float]]:
    """Parse REDWEAVER_MODEL_PRICES, skipping malformed entries."""
    raw = (os.environ.get(_ENV_OVERRIDE) or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        logger.warning("%s is not valid JSON; ignoring", _ENV_OVERRIDE)
        return {}
    if not isinstance(data, dict):
        logger.warning("%s must be a JSON object of model -> [prompt, completion]", _ENV_OVERRIDE)
        return {}
    out: dict[str, tuple[float, float]] = {}
    for key, value in data.items():
        try:
            prompt, completion = value
            out[str(key).lower()] = (float(prompt), float(completion))
        except (TypeError, ValueError):
            logger.warning("%s: bad price entry for %r; ignoring", _ENV_OVERRIDE, key)
    return out


def price_table() -> dict[str, tuple[float, float]]:
    """Built-in prices merged with the environment override (override wins)."""
    return {**_PRICES, **_env_prices()}


def price_for(model: str) -> tuple[float, float] | None:
    """Return the (prompt, completion) per-1M price, or None when unpriced.

    Model ids carry suffixes (``claude-sonnet-4-6-20260218``), so keys match as
    substrings — longest key first, so the most specific entry wins.
    """
    m = (model or "").lower()
    if not m:
        return None
    table = price_table()
    for key in sorted(table, key=len, reverse=True):
        if key in m:
            return table[key]
    return None


def is_priced(model: str) -> bool:
    """False when this model's cost is a fallback guess rather than a real price."""
    return price_for(model) is not None


def _rate(model: str) -> tuple[float, float]:
    price = price_for(model)
    if price is not None:
        return price
    key = (model or "").lower() or "<unset>"
    if key not in _warned_unknown:
        _warned_unknown.add(key)
        logger.warning(
            "No price entry for model %r; estimating at gpt-4o-mini rates. "
            "Set %s to price it properly.", key, _ENV_OVERRIDE,
        )
    return _DEFAULT


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    p_rate, c_rate = _rate(model)
    cost = (prompt_tokens / 1_000_000) * p_rate + (completion_tokens / 1_000_000) * c_rate
    return round(cost, 4)
