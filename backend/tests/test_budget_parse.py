"""Unit tests for the per-run spend ceiling accepted by the chat endpoint.

A malformed budget must never fail the request — the ceiling is a guard rail,
not the purpose of the call — and must never be mistaken for a ceiling of zero,
which would stop every hunt instantly.
"""
from decimal import Decimal

from apps.hunts.budget import parse_budget_usd


def test_valid_budgets_are_parsed():
    assert parse_budget_usd("2.50") == Decimal("2.50")
    assert parse_budget_usd(2.5) == Decimal("2.5")
    assert parse_budget_usd(1) == Decimal("1")


def test_absent_budget_means_no_limit():
    assert parse_budget_usd(None) is None
    assert parse_budget_usd("") is None


def test_zero_and_negative_mean_no_limit_not_an_instant_stop():
    # A ceiling of 0 would abort every run at the first task; treat it as unset.
    assert parse_budget_usd(0) is None
    assert parse_budget_usd("0") is None
    assert parse_budget_usd(-5) is None


def test_garbage_is_ignored_rather_than_raising():
    for value in ("abc", "$3.00", {}, [], object()):
        assert parse_budget_usd(value) is None
