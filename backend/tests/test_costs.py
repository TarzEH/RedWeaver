"""Unit tests for LLM cost estimation: matching order, unknown models, overrides.

The bug these guard against is silent: an unpriced model used to be billed at
gpt-4o-mini rates with no signal, so every run on a newer model under-reported.
"""
import json

import pytest

from apps.hunts.costs import (
    estimate_cost_usd,
    is_priced,
    price_for,
    price_table,
)


@pytest.fixture(autouse=True)
def _clean_price_env(monkeypatch):
    """A price override in the ambient environment would skew every assertion."""
    monkeypatch.delenv("REDWEAVER_MODEL_PRICES", raising=False)


# ── matching ───────────────────────────────────────────────────────────────
def test_longest_key_wins_over_shorter_prefix():
    # "gpt-4o" is a substring of "gpt-4o-mini"; the specific entry must win
    # regardless of the order keys happen to sit in the dict.
    assert price_for("gpt-4o-mini") == (0.15, 0.60)
    assert price_for("gpt-4o") == (2.50, 10.00)
    assert price_for("gpt-4.1-nano") == (0.10, 0.40)
    assert price_for("gpt-4.1") == (2.00, 8.00)


def test_matches_dated_and_prefixed_model_ids():
    # Real ids carry revision/date suffixes and litellm provider prefixes.
    assert price_for("claude-sonnet-4-6-20260218") == (3.00, 15.00)
    assert price_for("anthropic/claude-opus-4-1") == (15.00, 75.00)
    assert price_for("gpt-5-mini-2025-08-07") == (0.25, 2.00)


def test_gpt5_family_is_priced_not_guessed():
    # The old table had no gpt-5 entries at all, so these silently fell back to
    # gpt-4o-mini rates.
    for model in ("gpt-5", "gpt-5-mini", "gpt-5-nano"):
        assert is_priced(model), f"{model} should have a price entry"
    assert price_for("gpt-5") != price_for("gpt-4o-mini")


def test_self_hosted_models_are_free():
    assert price_for("ollama/llama3.2") == (0.0, 0.0)
    assert estimate_cost_usd("ollama/llama3.2", 1_000_000, 1_000_000) == 0.0


# ── unknown models stay visible ────────────────────────────────────────────
def test_unknown_model_is_reported_as_unpriced():
    assert price_for("some-model-that-does-not-exist") is None
    assert is_priced("some-model-that-does-not-exist") is False
    assert is_priced("") is False


def test_unknown_model_still_produces_a_number():
    # Falls back rather than crashing a run — but is_priced() says it's a guess.
    assert estimate_cost_usd("some-model-that-does-not-exist", 1_000_000, 0) == 0.15


# ── arithmetic ─────────────────────────────────────────────────────────────
def test_cost_is_split_across_prompt_and_completion_rates():
    # gpt-4o: $2.50/1M prompt + $10.00/1M completion
    assert estimate_cost_usd("gpt-4o", 1_000_000, 0) == 2.50
    assert estimate_cost_usd("gpt-4o", 0, 1_000_000) == 10.00
    assert estimate_cost_usd("gpt-4o", 500_000, 100_000) == pytest.approx(2.25)


def test_zero_tokens_costs_nothing():
    assert estimate_cost_usd("gpt-4o", 0, 0) == 0.0


# ── env override ───────────────────────────────────────────────────────────
def test_env_override_adds_and_replaces_prices(monkeypatch):
    monkeypatch.setenv(
        "REDWEAVER_MODEL_PRICES",
        json.dumps({"brand-new-model": [1.0, 2.0], "gpt-4o": [99.0, 99.0]}),
    )
    assert price_for("brand-new-model") == (1.0, 2.0)
    assert price_for("gpt-4o") == (99.0, 99.0)  # override beats the built-in
    assert estimate_cost_usd("brand-new-model", 1_000_000, 0) == 1.0


def test_malformed_env_override_is_ignored(monkeypatch):
    monkeypatch.setenv("REDWEAVER_MODEL_PRICES", "not json at all")
    assert price_for("gpt-4o") == (2.50, 10.00)

    monkeypatch.setenv("REDWEAVER_MODEL_PRICES", json.dumps({"x": "cheap"}))
    assert "x" not in price_table()
    assert price_for("gpt-4o") == (2.50, 10.00)
