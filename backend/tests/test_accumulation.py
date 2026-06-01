"""Contracts for the real-time accumulation/distribution tracker.

Pure logic — no network. Locks the quote-test classification and the dark-pool
split that the card's "who's accumulating" read depends on.
"""
from __future__ import annotations

import asyncio

from accumulation import AccumulationTracker


def _run(coro):
    return asyncio.run(coro)


def _mk(focus=("AAPL",), window=900.0, maxf=40):
    t = AccumulationTracker(window_sec=window, max_focus=maxf)
    t.set_focus(list(focus))
    return t


# ── focus management ─────────────────────────────────────────────────────

def test_set_focus_caps_and_reports_added():
    t = AccumulationTracker(max_focus=2)
    added = t.set_focus(["AAPL", "MSFT", "NVDA"])
    assert t.focus == {"AAPL", "MSFT"}          # capped at 2 (order preserved)
    assert added == {"AAPL", "MSFT"}
    added2 = t.set_focus(["AAPL", "TSLA"])
    assert t.focus == {"AAPL", "TSLA"}
    assert added2 == {"TSLA"}


def test_add_focus_idempotent():
    t = _mk(("AAPL",))
    assert t.add_focus("MSFT") is True
    assert t.in_focus("MSFT")
    assert t.add_focus("MSFT") is False


# ── quote-test classification ────────────────────────────────────────────

def test_trade_at_ask_is_buy():
    t = _mk(("AAPL",))
    t.on_quote("AAPL", 100.0, 100.10)
    _run(t.on_trade("AAPL", 100.10, 50, is_dark=False))   # at ask → buy
    s = t.snapshot("AAPL")["session"]
    assert s["buy_volume"] == 50 and s["sell_volume"] == 0
    assert s["net_dollars"] == round(100.10 * 50, 2)


def test_trade_at_bid_is_sell():
    t = _mk(("AAPL",))
    t.on_quote("AAPL", 100.0, 100.10)
    _run(t.on_trade("AAPL", 100.0, 30, is_dark=False))    # at bid → sell
    s = t.snapshot("AAPL")["session"]
    assert s["sell_volume"] == 30 and s["buy_volume"] == 0
    assert s["net_dollars"] == round(-100.0 * 30, 2)


def test_no_nbbo_is_unclassified_but_counts_volume():
    t = _mk(("AAPL",))
    _run(t.on_trade("AAPL", 100.0, 10, is_dark=False))    # no quote yet → side 0
    s = t.snapshot("AAPL")["session"]
    assert s["buy_volume"] == 0 and s["sell_volume"] == 0
    assert s["volume"] == 10


# ── dark-pool split ──────────────────────────────────────────────────────

def test_dark_pool_buy_ratio_and_pct():
    t = _mk(("AAPL",))
    t.on_quote("AAPL", 100.0, 100.10)
    _run(t.on_trade("AAPL", 100.10, 100, is_dark=True))   # dark buy
    _run(t.on_trade("AAPL", 100.00, 40, is_dark=False))   # lit sell
    s = t.snapshot("AAPL")["session"]
    assert s["dark_volume"] == 100
    assert s["dark_buy_ratio"] == 1.0
    assert round(s["dark_pct"], 4) == round(100 / 140, 4)


# ── focus gating ─────────────────────────────────────────────────────────

def test_off_focus_trade_ignored():
    t = _mk(("AAPL",))
    t.on_quote("MSFT", 1.0, 2.0)
    _run(t.on_trade("MSFT", 2.0, 10, is_dark=False))
    assert t.snapshot("MSFT") is None


# ── signal label ─────────────────────────────────────────────────────────

def test_signal_accumulation_when_buy_heavy():
    t = _mk(("AAPL",))
    t.on_quote("AAPL", 100.0, 100.10)
    for _ in range(7):
        _run(t.on_trade("AAPL", 100.10, 10, is_dark=False))   # buys
    for _ in range(3):
        _run(t.on_trade("AAPL", 100.00, 10, is_dark=False))   # sells → 70% buy
    assert t.snapshot("AAPL")["signal"] == "accumulation"


def test_signal_distribution_when_sell_heavy():
    t = _mk(("AAPL",))
    t.on_quote("AAPL", 100.0, 100.10)
    for _ in range(7):
        _run(t.on_trade("AAPL", 100.00, 10, is_dark=False))   # sells → 70% sell
    for _ in range(3):
        _run(t.on_trade("AAPL", 100.10, 10, is_dark=False))
    assert t.snapshot("AAPL")["signal"] == "distribution"


# ── rolling window ───────────────────────────────────────────────────────

def test_window_trims_old_trades_but_session_keeps_all():
    t = AccumulationTracker(window_sec=10.0)
    t.set_focus(["AAPL"])
    t.on_quote("AAPL", 100.0, 100.10)
    _run(t.on_trade("AAPL", 100.10, 10, is_dark=False, ts=1000.0))  # old
    _run(t.on_trade("AAPL", 100.10, 5, is_dark=False, ts=1100.0))   # 100s later
    snap = t.snapshot("AAPL")
    assert snap["session"]["volume"] == 15     # session keeps both
    assert snap["window"]["volume"] == 5       # window only the recent
