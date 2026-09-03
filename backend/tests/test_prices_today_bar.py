"""prices.with_today_bar — today's live bar overlaid on the closed daily frame.

Ajay 2026-09-03 (CHPT): the Supply/Demand tab read "nearest support 1.4%
below" off the 09-02 close while the tape printed +76%. Behavioural tests on
synthetic frames + the three wiring points (price_zones, support tab, tiles).
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sepa import prices as P  # noqa: E402


def _frame(n=80, start=5.0, last="2026-09-02", wavy=False):
    idx = pd.bdate_range(end=pd.Timestamp(last), periods=n) + pd.Timedelta(hours=4)
    close = [start + i * 0.01 for i in range(n)]
    if wavy:   # repeated swing lows/highs so the zone engine finds structure
        import math
        close = [start + 1.0 + math.sin(i / 4.0) * 0.6 + (i % 17 == 0) * 0.3 for i in range(n)]
    return pd.DataFrame({"open": close, "high": [c + 0.05 for c in close],
                         "low": [c - 0.05 for c in close], "close": close,
                         "volume": [1e6] * n}, index=idx)


SNAP = {"open": 6.9, "high": 9.2, "low": 6.71, "close": 9.1069, "volume": 30903227.0,
        "date": "2026-09-03 00:00:00", "change_pct": 75.5, "prev_day_close": 5.19,
        "last_trade_ts_ms": 1788455521222922425}


def test_appends_todays_bar_when_the_frame_ends_yesterday():
    df = _frame()
    out, info = P.with_today_bar(df, "CHPT", snap=SNAP)
    assert len(out) == len(df) + 1
    last = out.iloc[-1]
    assert (last["open"], last["high"], last["low"], last["close"]) == (6.9, 9.2, 6.71, 9.1069)
    assert last["volume"] == 30903227.0
    assert out.index[-1] == pd.Timestamp("2026-09-03 04:00:00"), "same 04:00 convention as the frame"
    assert info["appended"] is True and info["date"] == "2026-09-03"
    assert info["last_price"] == 9.1069 and info["source"] == "snapshot"
    assert abs(info["as_of_epoch"] - 1788455521.222922) < 1e-3, "ns stamp → epoch seconds"
    assert len(df) == 80, "the cached frame itself is never mutated"


def test_no_op_when_the_frame_already_holds_the_snapshot_date():
    df = _frame(last="2026-09-03")
    out, info = P.with_today_bar(df, "CHPT", snap=SNAP)
    assert out is df and info["appended"] is False and info["date"] == "2026-09-03"


def test_no_op_on_missing_or_premarket_zero_snapshots_and_empty_frames():
    df = _frame()
    for snap in (None, {}, {**SNAP, "open": 0, "high": 0, "low": 0, "close": 0},
                 {**SNAP, "close": None}, {**SNAP, "date": ""}, {**SNAP, "low": "x"}):
        out, info = P.with_today_bar(df, "CHPT", snap=snap)
        assert out is df and info["appended"] is False, snap
    out, info = P.with_today_bar(None, "CHPT", snap=SNAP)
    assert out is None and info["appended"] is False
    out, info = P.with_today_bar(df.iloc[0:0], "CHPT", snap=SNAP)
    assert len(out) == 0 and info["appended"] is False


def test_ms_stamps_and_tz_aware_indexes_are_handled():
    df = _frame()
    df.index = df.index.tz_localize("UTC")
    out, info = P.with_today_bar(df, "CHPT", snap={**SNAP, "last_trade_ts_ms": 1788455521222})
    assert out.index[-1] == pd.Timestamp("2026-09-03 04:00:00", tz="UTC")
    assert abs(info["as_of_epoch"] - 1788455521.222) < 1e-3


def test_snapshot_is_fetched_for_the_symbol_when_not_given(monkeypatch):
    calls = []
    monkeypatch.setattr(P, "bulk_snapshot", lambda syms: (calls.append(list(syms)), {"CHPT": SNAP})[1])
    out, info = P.with_today_bar(_frame(), "chpt")
    assert calls == [["CHPT"]] and info["appended"] is True and len(out) == 81


def test_a_snapshot_failure_leaves_the_frame_alone(monkeypatch):
    def boom(syms):
        raise RuntimeError("massive down")
    monkeypatch.setattr(P, "bulk_snapshot", boom)
    df = _frame()
    out, info = P.with_today_bar(df, "CHPT")
    assert out is df and info["appended"] is False


# ── wiring: the three readers see the live bar ───────────────────────────────
def test_price_zones_for_symbol_reads_last_price_from_the_live_bar(monkeypatch):
    from supply_demand import price_zones as pz
    monkeypatch.setattr(P, "load_prices", lambda sym, *a, **k: _frame(300, wavy=True))
    monkeypatch.setattr(P, "bulk_snapshot", lambda syms: {"CHPT": SNAP})
    out = pz.for_symbol("CHPT")
    assert out.get("error") is None, out
    assert out["last_price"] == 9.11
    assert out["live_bar"]["appended"] is True and out["live_bar"]["date"] == "2026-09-03"


def test_price_zones_without_a_snapshot_is_byte_for_byte_the_closed_read(monkeypatch):
    from supply_demand import price_zones as pz
    monkeypatch.setattr(P, "load_prices", lambda sym, *a, **k: _frame(300, wavy=True))
    monkeypatch.setattr(P, "bulk_snapshot", lambda syms: {})
    out = pz.for_symbol("CHPT")
    assert out.get("error") is None, out
    assert out["last_price"] == round(float(_frame(300, wavy=True)["close"].iloc[-1]), 2)
    assert out["live_bar"]["appended"] is False


def test_support_tab_frame_carries_today_and_stamps_the_snapshot_time(monkeypatch):
    from chart_maps import support as S
    monkeypatch.setattr(P, "load_prices", lambda sym, *a, **k: _frame(300))
    monkeypatch.setattr(P, "bulk_snapshot", lambda syms: {"CHPT": SNAP})
    df, have, as_of = S._frame_for("CHPT", 120)
    assert have == 301 and str(df.index[-1])[:10] == "2026-09-03"
    assert abs(as_of - 1788455521.222922) < 1e-3
    monkeypatch.setattr(P, "bulk_snapshot", lambda syms: {})
    df2, have2, as_of2 = S._frame_for("CHPT", 120)
    assert have2 == 300 and as_of2 != as_of


def test_tile_bars_include_todays_candle(monkeypatch):
    from chart_maps import board as B
    monkeypatch.setattr(P, "load_prices", lambda sym, *a, **k: _frame(300))
    monkeypatch.setattr(P, "bulk_snapshot", lambda syms: {"CHPT": SNAP})
    bars = B.bars_for("CHPT", days=60)
    assert bars and bars[-1]["t"] == "2026-09-03" and bars[-1]["c"] == 9.1069
