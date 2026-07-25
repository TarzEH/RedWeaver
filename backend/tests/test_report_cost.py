"""Unit tests for the report's ``cost`` block (``apps.reports.views.cost_payload``).

The bug these guard against was silent and total: the backend emitted
``{prompt_tokens, completion_tokens, total_tokens, usd}`` while the frontend
renders the cost badge only when ``cost.total_usd != null``, so *every* report
dropped its cost with no error anywhere.

``apps.reports.views`` is a Django module and Django is not installed in this
unit-test environment, so the pure helper is lifted out of the source with
``ast`` and executed on its own. That keeps the payload contract under test
without a Django install or a database — and fails loudly if the helper is
renamed or stops being pure.
"""
from __future__ import annotations

import ast
import json
from decimal import Decimal
from pathlib import Path

import pytest

from apps.hunts.costs import is_priced

_VIEWS = Path(__file__).resolve().parents[1] / "apps" / "reports" / "views.py"

# Every key the frontend `ReportCost` interface reads (frontend/src/types/api.ts).
_FRONTEND_KEYS = {
    "total_usd", "input_tokens", "output_tokens", "total_tokens",
    "model", "is_estimate", "budget_usd", "budget_used_fraction",
}
# Keys other consumers (HTML export footer, scripted clients) still read.
_LEGACY_KEYS = {"prompt_tokens", "completion_tokens", "total_tokens", "usd"}


def _load_cost_payload():
    """Compile just ``cost_payload`` out of views.py, without importing Django."""
    tree = ast.parse(_VIEWS.read_text(), filename=str(_VIEWS))
    fn = next(
        (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "cost_payload"),
        None,
    )
    assert fn is not None, "cost_payload() was renamed or moved out of apps/reports/views.py"
    namespace = {"is_priced": is_priced}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(_VIEWS), "exec"), namespace)
    return namespace["cost_payload"]


cost_payload = _load_cost_payload()


def _payload(**overrides):
    kwargs = {
        "prompt_tokens": 1000,
        "completion_tokens": 500,
        "total_tokens": 1500,
        "cost_usd": Decimal("0.1234"),
        "budget_usd": None,
        "model": "gpt-4o-mini",
    }
    kwargs.update(overrides)
    return cost_payload(**kwargs)


@pytest.fixture(autouse=True)
def _clean_price_env(monkeypatch):
    """A price override in the ambient environment would skew `is_estimate`."""
    monkeypatch.delenv("REDWEAVER_MODEL_PRICES", raising=False)


# ── shape contract ─────────────────────────────────────────────────────────
def test_emits_every_key_the_frontend_reads():
    assert _FRONTEND_KEYS <= set(_payload())


def test_keeps_the_legacy_keys_so_other_consumers_do_not_break():
    p = _payload()
    assert _LEGACY_KEYS <= set(p)
    assert (p["prompt_tokens"], p["completion_tokens"], p["usd"]) == (1000, 500, 0.1234)


def test_new_and_legacy_token_keys_agree():
    p = _payload()
    assert p["input_tokens"] == p["prompt_tokens"]
    assert p["output_tokens"] == p["completion_tokens"]
    assert p["total_usd"] == p["usd"]


def test_payload_is_json_serialisable():
    # Decimal leaking through would 500 the endpoint on serialisation.
    assert json.loads(json.dumps(_payload(budget_usd=Decimal("5.00"))))["total_usd"] == 0.1234


# ── total_usd: the field that gates the badge ──────────────────────────────
def test_total_usd_is_present_even_for_a_free_run():
    # `cost?.total_usd != null` gates the badge — 0.0 must still render.
    p = _payload(cost_usd=Decimal("0"), model="ollama/llama3")
    assert p["total_usd"] == 0.0
    assert p["total_usd"] is not None


def test_total_usd_is_a_float_not_a_decimal():
    assert isinstance(_payload(cost_usd=Decimal("2.5000"))["total_usd"], float)


def test_none_cost_is_treated_as_zero():
    assert _payload(cost_usd=None)["total_usd"] == 0.0


# ── tokens ─────────────────────────────────────────────────────────────────
def test_total_tokens_falls_back_to_the_sum_when_unset():
    # Interrupted runs sometimes persist the halves but never the total.
    assert _payload(total_tokens=0)["total_tokens"] == 1500


def test_stored_total_wins_when_present():
    # Usage metrics can include tokens neither half accounts for; don't override.
    assert _payload(total_tokens=1700)["total_tokens"] == 1700


def test_none_tokens_are_treated_as_zero():
    p = _payload(prompt_tokens=None, completion_tokens=None, total_tokens=None)
    assert (p["input_tokens"], p["output_tokens"], p["total_tokens"]) == (0, 0, 0)


# ── is_estimate ────────────────────────────────────────────────────────────
def test_priced_model_is_not_an_estimate():
    assert _payload(model="claude-sonnet-4-6-20260218")["is_estimate"] is False
    assert is_priced("claude-sonnet-4-6-20260218")


def test_unpriced_model_is_flagged_as_an_estimate():
    # Billed at the gpt-4o-mini-class fallback rate, so the figure is a guess.
    assert _payload(model="some-brand-new-model-2027")["is_estimate"] is True


def test_unknown_model_is_flagged_as_an_estimate():
    assert _payload(model="")["is_estimate"] is True
    assert _payload(model=None)["is_estimate"] is True


def test_model_is_normalised_to_a_string():
    assert _payload(model=None)["model"] == ""
    assert _payload(model="  gpt-4o  ")["model"] == "gpt-4o"


# ── budget ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("budget", [None, 0, Decimal("0"), Decimal("0.00"), 0.0])
def test_no_budget_reports_null_not_zero(budget):
    # A 0 here would read as "budget of $0, already blown" in the UI.
    p = _payload(budget_usd=budget)
    assert p["budget_usd"] is None
    assert p["budget_used_fraction"] is None


def test_budget_fraction_is_spend_over_ceiling():
    p = _payload(cost_usd=Decimal("2.5"), budget_usd=Decimal("10.00"))
    assert p["budget_usd"] == 10.0
    assert p["budget_used_fraction"] == 0.25


def test_budget_fraction_can_exceed_one():
    # The guard checks at task boundaries, so a run can overshoot its ceiling.
    p = _payload(cost_usd=Decimal("12.00"), budget_usd=Decimal("10.00"))
    assert p["budget_used_fraction"] == 1.2


def test_zero_spend_against_a_budget_is_zero_not_null():
    p = _payload(cost_usd=Decimal("0"), budget_usd=Decimal("5.00"))
    assert p["budget_used_fraction"] == 0.0
    assert p["budget_usd"] == 5.0
