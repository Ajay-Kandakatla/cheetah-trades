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


# ── engine fixes 2026-09-05 (Ajay: "yes please fix the bugs") ─────────────────
def test_a_snapshot_that_echoes_the_prior_session_is_not_appended():
    """Pre-session, Massive's day object can carry YESTERDAY's o/h/l/c/v under
    today's date (the phantom `_drop_phantom_tail` documents). Same close AND
    same volume as the last closed bar = placeholder, not a session."""
    df = _frame()
    last = df.iloc[-1]
    echo = {**SNAP, "open": float(last["open"]), "high": float(last["high"]),
            "low": float(last["low"]), "close": float(last["close"]),
            "volume": float(last["volume"])}
    out, info = P.with_today_bar(df, "CHPT", snap=echo)
    assert out is df and len(out) == len(df)
    assert info["appended"] is False and info["source"] == "frame"
    assert "phantom" in (info.get("reason") or "")


def test_a_weekend_dated_snapshot_is_not_appended():
    """bulk_snapshot falls back to today-ET when day.t is absent, so a Saturday
    read stamps Friday's aggregate with a Saturday date. Real daily bars only
    fall Mon–Fri — the same guard patch_latest_closes already applies."""
    df = _frame(last="2026-09-04")                                # Friday
    sat = {**SNAP, "close": 9.5, "volume": 1234.0, "date": "2026-09-05 00:00:00"}
    out, info = P.with_today_bar(df, "CHPT", snap=sat)
    assert out is df and info["appended"] is False
    assert "weekend" in (info.get("reason") or "")
    sun = {**sat, "date": "2026-09-06 00:00:00"}
    assert P.with_today_bar(df, "CHPT", snap=sun)[1]["appended"] is False


def test_a_genuine_live_bar_still_appends_after_the_guards():
    """Same date, different close/volume from the prior session = a real
    session in progress; the guards must not eat it."""
    df = _frame()                                                 # ends Wed 09-02
    out, info = P.with_today_bar(df, "CHPT", snap=SNAP)           # Thu 09-03
    assert info["appended"] is True and len(out) == len(df) + 1
    assert info.get("reason") is None
    # a bar that shares ONLY the close (volume differs) is a real session too
    same_close = {**SNAP, "close": float(df["close"].iloc[-1]), "volume": 777.0}
    assert P.with_today_bar(df, "CHPT", snap=same_close)[1]["appended"] is True


# ── extended hours (Ajay 2026-09-08: "enable pre market pricing and let me scan
# premarket hours … Also after hours") ──────────────────────────────────────────
import datetime as _dt  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

_ET = ZoneInfo("America/New_York")


def _stamp(y, m, d, hh, mm):
    """A Massive-style ns stamp for an ET wall-clock time."""
    return int(_dt.datetime(y, m, d, hh, mm, tzinfo=_ET).timestamp() * 1e9)


PRE = {"open": 0, "high": 0, "low": 0, "close": 0, "volume": 0, "date": "2026-09-03 00:00:00",
       "prev_day_close": 5.19, "last_trade_price": 5.61,
       "last_trade_ts_ms": _stamp(2026, 9, 3, 8, 13)}


def test_premarket_print_becomes_a_flat_synthetic_bar():
    df = _frame()
    out, info = P.with_today_bar(df, "CHPT", snap=PRE)
    assert len(out) == len(df) + 1
    last = out.iloc[-1]
    assert (last["open"], last["high"], last["low"], last["close"], last["volume"]) == (5.61, 5.61, 5.61, 5.61, 0.0)
    assert out.index[-1] == pd.Timestamp("2026-09-03 04:00:00")
    assert info["appended"] is True and info["adjusted"] is False
    assert info["source"] == "premarket" and info["session"] == "premarket"
    assert info["last_price"] == 5.61 and info["date"] == "2026-09-03"
    assert abs(info["as_of_epoch"] - PRE["last_trade_ts_ms"] / 1e9) < 1e-3
    assert len(df) == 80, "the cached frame itself is never mutated"


def test_afterhours_print_extends_the_appended_day_bar():
    snap = {**SNAP, "last_trade_price": 9.40, "last_trade_ts_ms": _stamp(2026, 9, 3, 17, 5)}
    out, info = P.with_today_bar(_frame(), "CHPT", snap=snap)
    last = out.iloc[-1]
    assert (last["open"], last["high"], last["low"], last["close"]) == (6.9, 9.40, 6.71, 9.40)
    assert last["volume"] == 30903227.0, "the session's volume stands"
    assert info["appended"] is True and info["source"] == "afterhours"
    assert info["session"] == "afterhours" and info["last_price"] == 9.40
    # a LOWER after-hours print pulls the low, never the high
    out2, _ = P.with_today_bar(_frame(), "CHPT", snap={**snap, "last_trade_price": 6.50})
    l2 = out2.iloc[-1]
    assert (l2["high"], l2["low"], l2["close"]) == (9.2, 6.50, 6.50)


def test_afterhours_print_adjusts_the_frame_that_already_holds_today():
    df = _frame(last="2026-09-03")
    before = float(df.iloc[-1]["close"])
    snap = {**SNAP, "last_trade_price": 9.40, "last_trade_ts_ms": _stamp(2026, 9, 3, 18, 0)}
    out, info = P.with_today_bar(df, "CHPT", snap=snap)
    assert out is not df and len(out) == len(df)
    assert out.iloc[-1]["close"] == 9.40 and out.iloc[-1]["high"] == 9.40
    assert float(df.iloc[-1]["close"]) == before, "the cached frame is never mutated"
    assert info["appended"] is False and info["adjusted"] is True
    assert info["source"] == "afterhours" and info["session"] == "afterhours"
    assert info["date"] == "2026-09-03" and info["last_price"] == 9.40


def test_negative_stale_or_off_session_prints_change_nothing():
    df = _frame()
    # yesterday's after-hours print under a zero pre-market bar → no bar
    out, info = P.with_today_bar(df, "CHPT", snap={**PRE, "last_trade_ts_ms": _stamp(2026, 9, 2, 19, 0)})
    assert out is df and info["appended"] is False
    # a print stamped before the pre-market opens (03:00) → no bar
    assert P.with_today_bar(df, "CHPT", snap={**PRE, "last_trade_ts_ms": _stamp(2026, 9, 3, 3, 0)})[1]["appended"] is False
    # a Saturday stamp → no bar
    assert P.with_today_bar(df, "CHPT", snap={**PRE, "last_trade_ts_ms": _stamp(2026, 9, 5, 8, 0)})[1]["appended"] is False
    # unpriced / unstamped / garbage
    for bad in ({**PRE, "last_trade_price": 0}, {**PRE, "last_trade_ts_ms": None},
                {**PRE, "last_trade_price": "x"}, {**PRE, "last_trade_ts_ms": "soon"}):
        out, info = P.with_today_bar(df, "CHPT", snap=bad)
        assert out is df and info["appended"] is False, bad
    # an RTH print on a real day bar: the bar is the bar (source stays "snapshot")
    rth = {**SNAP, "last_trade_price": 9.1069, "last_trade_ts_ms": _stamp(2026, 9, 3, 14, 0)}
    out, info = P.with_today_bar(df, "CHPT", snap=rth)
    assert info["source"] == "snapshot" and info["session"] == "rth" and out.iloc[-1]["close"] == 9.1069
    # an after-hours print of a DIFFERENT day than the day bar → bar unchanged
    other = {**SNAP, "last_trade_price": 9.40, "last_trade_ts_ms": _stamp(2026, 9, 2, 17, 0)}
    out, info = P.with_today_bar(df, "CHPT", snap=other)
    assert out.iloc[-1]["close"] == 9.1069 and info["source"] == "snapshot"
    # the frame already holds today and the print is RTH → plain no-op
    held = _frame(last="2026-09-03")
    out, info = P.with_today_bar(held, "CHPT", snap=rth)
    assert out is held and info["appended"] is False and info["adjusted"] is False


def test_trade_session_clock_and_extended_print():
    d = lambda hh, mm, day=3: _dt.datetime(2026, 9, day, hh, mm, tzinfo=_ET)
    assert P.trade_session(d(3, 59)) == "closed" and P.trade_session(d(4, 0)) == "premarket"
    assert P.trade_session(d(9, 29)) == "premarket" and P.trade_session(d(9, 30)) == "rth"
    assert P.trade_session(d(15, 59)) == "rth" and P.trade_session(d(16, 0)) == "afterhours"
    assert P.trade_session(d(19, 59)) == "afterhours" and P.trade_session(d(20, 0)) == "closed"
    assert P.trade_session(d(10, 0, day=5)) == "closed"      # Saturday
    ep = P.extended_print(PRE)
    assert ep["price"] == 5.61 and ep["date"] == "2026-09-03" and ep["session"] == "premarket"
    assert P.extended_print({}) is None and P.extended_print(None) is None
    assert P.extended_print({"last_trade_price": 5.0}) is None, "a price without a stamp is not a print"
    ms = {**PRE, "last_trade_ts_ms": PRE["last_trade_ts_ms"] // 1_000_000}   # ms stamp
    assert P.extended_print(ms)["session"] == "premarket"


def test_support_overlay_treats_an_adjusted_afterhours_frame_as_live():
    """chart_maps.support._overlay_today: the frame that already holds today,
    close carried to the after-hours print, is LIVE (as_of = the print's
    stamp) and the closed frame the caller keeps stays the original."""
    from chart_maps import support as S
    df = _frame(last="2026-09-03")
    snap = {**SNAP, "last_trade_price": 9.40, "last_trade_ts_ms": _stamp(2026, 9, 3, 18, 0)}

    class _P:
        @staticmethod
        def with_today_bar(frame, sym):
            return P.with_today_bar(frame, sym, snap=snap)

    out, as_of, live = S._overlay_today(_P, df, "CHPT")
    assert live is True and abs(as_of - snap["last_trade_ts_ms"] / 1e9) < 1e-3
    assert out.iloc[-1]["close"] == 9.40 and df.iloc[-1]["close"] != 9.40
    # zones read: the adjusted print prices the verdict
    from supply_demand import price_zones as PZ
    _df, info = PZ._overlay_today(_P, df, "CHPT")
    assert info["adjusted"] and info["last_price"] == 9.40
