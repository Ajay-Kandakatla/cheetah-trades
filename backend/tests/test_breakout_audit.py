"""Breakout integrity tripwire (Ajay 2026-06-18 — real money). Re-derives "broke
out today" from raw bars (book p.203) and compares to the persisted scan flag.

Locks: the reference definition (close > prior-21-bar high AND vol > 1.5× the
50-day avg), that a light-volume new high (BNY's case) is NOT a breakout, and
that the audit catches BOTH a false positive (flagged but not real) and a false
negative (real but missed).

  cd backend && .venv/bin/python -m pytest tests/test_breakout_audit.py -q
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa import breakout_audit


def _df(closes, vols):
    n = len(closes)
    return pd.DataFrame({"close": closes, "volume": vols},
                        index=pd.date_range("2026-01-01", periods=n, freq="D"))


# ── the reference definition (book p.203) ────────────────────────────────────

def test_real_volume_breakout_is_true():
    # last close clears the prior-21 high (100) on 2× the ~1M average volume
    assert breakout_audit.is_breakout_today(_df([100.0] * 59 + [110.0],
                                                [1_000_000] * 59 + [2_000_000])) is True


def test_new_high_on_light_volume_is_false():
    # BNY's case: new high, but volume is only 0.7× avg → NOT a breakout
    assert breakout_audit.is_breakout_today(_df([100.0] * 59 + [110.0],
                                                [1_000_000] * 59 + [700_000])) is False


def test_no_new_high_is_false():
    # huge volume but the close didn't clear the prior high → NOT a breakout
    assert breakout_audit.is_breakout_today(_df([100.0] * 59 + [99.0],
                                                [1_000_000] * 59 + [3_000_000])) is False


def test_insufficient_history_is_none():
    assert breakout_audit.is_breakout_today(_df([100.0] * 10, [1e6] * 10)) is None


# ── the audit catches discrepancies ──────────────────────────────────────────

def _patch(monkeypatch, scan_rows, dfs):
    from sepa import scanner, prices
    monkeypatch.setattr(scanner, "load_latest",
                        lambda: {"all_results": scan_rows, "generated_at": 1})
    monkeypatch.setattr(prices, "load_prices", lambda s, *a, **k: dfs.get(s))


def test_audit_clean_when_flags_match(monkeypatch):
    _patch(monkeypatch,
           [{"symbol": "AAA", "volume": {"days_since_breakout": 0}},    # flagged today
            {"symbol": "BBB", "volume": {"days_since_breakout": 2}}],   # not today
           {"AAA": _df([100.0] * 59 + [110.0], [1e6] * 59 + [2e6]),     # real breakout ✓
            "BBB": _df([100.0] * 59 + [110.0], [1e6] * 59 + [7e5])})    # light-vol new high ✓
    rep = breakout_audit.audit_latest(max_workers=2)
    assert rep["clean"] is True
    assert rep["false_positives"] == [] and rep["false_negatives"] == []
    assert rep["flagged_today"] == 1 and rep["confirmed_today"] == 1


def test_audit_catches_false_positive(monkeypatch):
    # scanner flagged AAA as today's breakout, but raw bars say light volume
    _patch(monkeypatch,
           [{"symbol": "AAA", "volume": {"days_since_breakout": 0}}],
           {"AAA": _df([100.0] * 59 + [110.0], [1e6] * 59 + [7e5])})
    rep = breakout_audit.audit_latest(max_workers=2)
    assert rep["clean"] is False
    assert rep["false_positives"] == ["AAA"]


def test_audit_catches_false_negative(monkeypatch):
    # raw bars say AAA is a real breakout, but the scanner didn't flag it
    _patch(monkeypatch,
           [{"symbol": "AAA", "volume": {"days_since_breakout": 3}}],
           {"AAA": _df([100.0] * 59 + [110.0], [1e6] * 59 + [2e6])})
    rep = breakout_audit.audit_latest(max_workers=2)
    assert rep["clean"] is False
    assert rep["false_negatives"] == ["AAA"]
