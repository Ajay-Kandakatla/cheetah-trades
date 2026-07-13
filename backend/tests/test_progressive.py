"""Progressive-exposure governor — trading/progressive.py.

Locks the pilot-buy mechanization (TLSW pp.307-308 "pilot buys ... require
that at least a few trades work out before getting more aggressive" +
Minervini's standing X rule "are your last 4 or 5 stocks profitable on
balance"): pilot size (0.5x) until the last 5 closed trades are net
positive, min()-composition with the p.304 streak multiplier, config
kill-switch, and fail-conservative behavior on missing data.

Host-runnable (py3.9, no pandas/numpy):
    cd backend && .venv/bin/python -m pytest tests/test_progressive.py -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.progressive as P
from trading.risk_rules import (
    MAX_POSITION_FRACTION, STREAK_HALVE_AFTER, position_size)


# ── on_balance_multiplier (pure) ─────────────────────────────────────────────

def test_unproven_account_gets_pilot_size():
    for gains in (None, [], [5.0], [5.0, 3.0]):
        mult, det = P.on_balance_multiplier(gains)
        assert mult == P.PILOT_MULTIPLIER == 0.5
        assert det["basis"] == "unproven"


def test_positive_on_balance_gets_full_size():
    mult, det = P.on_balance_multiplier([8.0, -6.0, 12.0, -7.0, 4.0])
    assert mult == 1.0
    assert det["net_pct"] == 11.0
    assert det["basis"].endswith("positive_on_balance")


def test_negative_on_balance_gets_pilot_size():
    mult, det = P.on_balance_multiplier([-7.0, -6.5, 15.0, -8.0, 2.0])
    assert mult == P.PILOT_MULTIPLIER
    assert det["net_pct"] == -4.5


def test_exactly_flat_is_not_on_balance_profitable():
    mult, _ = P.on_balance_multiplier([5.0, -5.0, 3.0, -3.0, 0.0])
    assert mult == P.PILOT_MULTIPLIER


def test_only_the_window_counts_and_garbage_is_ignored():
    # 6th value (old big winner) must NOT rescue a negative last-5.
    gains = [-2.0, -2.0, -2.0, 1.0, 1.0, 50.0]
    mult, det = P.on_balance_multiplier(gains)
    assert mult == P.PILOT_MULTIPLIER and det["n"] == 5

    mult, det = P.on_balance_multiplier([4.0, "junk", None, 3.0, 2.0])
    assert det["n"] == 3          # 3 valid -> proven threshold met
    assert mult == 1.0


# ── ledger read ──────────────────────────────────────────────────────────────

class _Cursor(list):
    def sort(self, *a, **k):
        return self

    def limit(self, n):
        return _Cursor(self[:int(n)])


class _Coll:
    def __init__(self, rows):
        self.rows = rows

    def find(self, q=None, *a, **k):
        out = []
        for r in self.rows:
            if r.get("kind") != (q or {}).get("kind"):
                continue
            if r.get("dry_run") is True:
                continue
            out.append(dict(r))
        return _Cursor(out)


class _DB:
    def __init__(self, rows):
        self.trade_ledger = _Coll(rows)


def _closed(epoch, gain, dry=False):
    return {"kind": "trade_closed", "epoch": epoch, "dry_run": dry,
            "detail": {"gain_pct": gain}}


def test_last_gains_newest_first_window_and_dry_run_excluded():
    rows = [_closed(1, -9.0), _closed(2, 1.0), _closed(3, 2.0),
            _closed(4, 3.0), _closed(5, 4.0), _closed(6, 5.0),
            _closed(7, 99.0, dry=True)]
    gains = P.last_gains(_DB(rows))
    assert gains == [5.0, 4.0, 3.0, 2.0, 1.0]   # -9 aged out, dry excluded


def test_last_gains_unreadable_ledger_is_empty():
    assert P.last_gains(None) == []

    class Boom:
        def find(self, *a, **k):
            raise RuntimeError("mongo down")

    class BoomDB:
        trade_ledger = Boom()

    assert P.last_gains(BoomDB()) == []          # -> unproven -> pilot


# ── multiplier() + config kill-switch ────────────────────────────────────────

def test_config_kill_switch_and_default_on():
    db = _DB([])
    assert P.multiplier(db, {"progressive_exposure": False}) == (
        1.0, {"enabled": False})
    mult, det = P.multiplier(db, {})             # absent -> ON
    assert mult == P.PILOT_MULTIPLIER and det["enabled"] is True
    mult, _ = P.multiplier(db, {"progressive_exposure": None})
    assert mult == P.PILOT_MULTIPLIER            # null = default = ON


# ── composition with p.304 inside position_size ──────────────────────────────

def test_position_size_min_composition_never_multiplies():
    base = position_size(10_000.0, 100.0, 0)
    assert base["multiplier"] == 1.0
    assert base["shares"] == int(10_000 * MAX_POSITION_FRACTION / 100.0)

    pilot = position_size(10_000.0, 100.0, 0, extra_multiplier=0.5)
    assert pilot["multiplier"] == 0.5
    assert pilot["shares"] == base["shares"] // 2

    # streak already at 0.5 + pilot 0.5 -> min = 0.5, NOT 0.25
    both = position_size(10_000.0, 100.0, STREAK_HALVE_AFTER,
                         extra_multiplier=0.5)
    assert both["multiplier"] == 0.5

    # streak 0.25 is stricter than the pilot -> streak wins
    deep = position_size(10_000.0, 100.0, STREAK_HALVE_AFTER * 2,
                         extra_multiplier=0.5)
    assert deep["multiplier"] == 0.25


def test_position_size_ignores_out_of_range_extra():
    base = position_size(10_000.0, 100.0, 0)
    for junk in (0.0, -1.0, 2.0, None, "x"):
        assert position_size(10_000.0, 100.0, 0,
                             extra_multiplier=junk) == base
