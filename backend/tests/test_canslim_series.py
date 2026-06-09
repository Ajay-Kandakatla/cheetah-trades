"""Data-layer test for canslim's Massive financials extraction.

Locks that we read income-statement (revenues, diluted EPS, net_income_loss) and
balance-sheet (inventory) values from the Massive /vX/reference/financials report
shape — the inputs the Minervini Ch.8 earnings-quality score (margins, Code 33,
inventory red flag) is built on. Synthetic report dicts; no network.
"""
from __future__ import annotations

from sepa import canslim


def _v(x):
    return {"value": x, "unit": "USD"}


def _report(inc=None, bal=None):
    return {"financials": {"income_statement": inc or {}, "balance_sheet": bal or {}}}


def test_income_value_extracts_eps_revenue_netincome():
    r = _report(inc={
        "revenues": _v(1000.0),
        "diluted_earnings_per_share": _v(2.5),
        "net_income_loss": _v(300.0),
    })
    assert canslim._income_value(r, "revenues") == 1000.0
    assert canslim._income_value(r, "diluted_earnings_per_share") == 2.5
    assert canslim._income_value(r, "net_income_loss") == 300.0
    assert canslim._income_value(r, "not_a_field") is None


def test_balance_value_extracts_inventory():
    r = _report(bal={"inventory": _v(750.0)})
    assert canslim._balance_value(r, "inventory") == 750.0
    # Massive does NOT expose receivables — must read as absent, never invented.
    assert canslim._balance_value(r, "accounts_receivable") is None
    assert canslim._balance_value(_report(), "inventory") is None


def test_values_handle_garbage_safely():
    assert canslim._income_value({"financials": None}, "revenues") is None
    assert canslim._income_value({}, "revenues") is None
    assert canslim._balance_value({}, "inventory") is None
    # Non-numeric value -> None (not a crash).
    bad = {"financials": {"balance_sheet": {"inventory": {"value": "n/a"}}}}
    assert canslim._balance_value(bad, "inventory") is None
    # Explicit null value -> None.
    nul = {"financials": {"income_statement": {"revenues": {"value": None}}}}
    assert canslim._income_value(nul, "revenues") is None


def test_series_are_newest_first_and_aligned():
    # Two quarters, newest first; confirm the list-comprehension series in
    # _fetch_massive_financials would pull the right column per quarter.
    q = [
        _report(inc={"revenues": _v(1200.0), "diluted_earnings_per_share": _v(3.0),
                     "net_income_loss": _v(360.0)}, bal={"inventory": _v(800.0)}),
        _report(inc={"revenues": _v(1000.0), "diluted_earnings_per_share": _v(2.5),
                     "net_income_loss": _v(300.0)}, bal={"inventory": _v(700.0)}),
    ]
    rev = [canslim._income_value(r, "revenues") for r in q]
    eps = [canslim._income_value(r, "diluted_earnings_per_share") for r in q]
    ni = [canslim._income_value(r, "net_income_loss") for r in q]
    inv = [canslim._balance_value(r, "inventory") for r in q]
    assert rev == [1200.0, 1000.0]
    assert eps == [3.0, 2.5]
    assert ni == [360.0, 300.0]
    assert inv == [800.0, 700.0]
