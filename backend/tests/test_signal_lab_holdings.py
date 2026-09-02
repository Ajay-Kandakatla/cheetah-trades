"""Signals board carries the portfolio by default (Ajay 2026-09-02)."""
from daytrading import signal_lab as sl


def test_merge_keeps_watchlist_order_then_adds_held_names_once():
    out = sl.merge_holdings(["nvda", "VST"], [{"ticker": "vst"}, {"ticker": "UBER"}, {"ticker": ""}, {}])
    assert out["symbols"] == ["NVDA", "VST", "UBER"]
    assert out["held"] == ["UBER", "VST"]


def test_merge_negatives():
    assert sl.merge_holdings([], []) == {"symbols": [], "held": []}
    assert sl.merge_holdings(None, None) == {"symbols": [], "held": []}
    assert sl.merge_holdings([" ", "aaoi "], [{"ticker": None}]) == {"symbols": ["AAOI"], "held": []}
