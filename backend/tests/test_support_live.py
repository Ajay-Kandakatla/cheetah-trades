"""Live extended-hours frame on the Support tab (Ajay 2026-09-02: "add live
chart please, for supply demand? I wanna see where things bounced over
night").

Guards: the 5m_live spec, the session tag surviving the resample, ext flags
reaching the minute loader, live_state's clock table, the overnight read's
decision table (held / broke / nothing printed / no tags), the bar
serializer's 'pre'/'ah' flag, and the structure-from-RTH split in for_symbol.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from supply_demand import timeframes as TF
from chart_maps import support as sup


# --- spec -------------------------------------------------------------------

def test_live_spec_registered_and_aliased():
    spec = TF.tf_spec("5m_live")
    assert spec["ext_hours"] is True
    assert spec["rule"] == "5min"
    assert TF.parse_tf("live") == "5m_live"
    assert TF.parse_tf("5m") == "5m_live"
    # HIDDEN from the generic dropdown — it is a chart frame, not a
    # structure frame; only the Support tab asks for it.
    assert not any(o["key"] == "5m_live" for o in TF.tf_options())
    assert any(o["key"] == "5m_live" for o in TF.tf_options(include_live=True))
    # every other intraday frame stays RTH-only
    for k in ("60m", "15m", "15m_open"):
        assert not TF.tf_spec(k).get("ext_hours")


# --- resample keeps the session tag ----------------------------------------

def _minute_frame():
    idx = pd.date_range("2026-09-01 13:25", periods=10, freq="1min", tz="UTC")  # 09:25-09:34 ET
    df = pd.DataFrame({"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05,
                       "volume": 100}, index=idx)
    df["session"] = ["premarket"] * 5 + ["rth"] * 5
    return df


def test_resample_keeps_session_tag_and_never_straddles():
    out = TF.resample_ohlcv(_minute_frame(), "5min")
    assert list(out["session"]) == ["premarket", "rth"]
    # right-labelled: the 09:25-09:29 bucket is stamped 09:30 ET (13:30Z)
    assert out.index[0] == pd.Timestamp("2026-09-01 13:30", tz="UTC")


def test_resample_without_session_column_unchanged():
    df = _minute_frame().drop(columns=["session"])
    out = TF.resample_ohlcv(df, "5min")
    assert "session" not in out.columns and len(out) == 2


# --- ext flags reach the loader --------------------------------------------

def test_intraday_raw_passes_ext_flags(monkeypatch):
    import daytrading.data as dd
    seen = {}

    def fake(symbol, start, end, include_premarket=False, include_afterhours=False):
        seen[symbol] = (include_premarket, include_afterhours)
        return None
    monkeypatch.setattr(dd, "load_intraday_range", fake)
    TF.intraday_raw("LIVE", "5m_live")
    TF.intraday_raw("RTH", "15m")
    assert seen["LIVE"] == (True, True)
    assert seen["RTH"] == (False, False)


# --- live_state clock table -------------------------------------------------

@pytest.mark.parametrize("et, state, refresh", [
    ("2026-09-01 08:00", "premarket", TF.LIVE_REFRESH_SEC),   # Tue
    ("2026-09-01 12:00", "rth", TF.LIVE_REFRESH_SEC),
    ("2026-09-01 17:00", "afterhours", TF.LIVE_REFRESH_SEC),
    ("2026-09-01 22:00", "closed", 0),
    ("2026-09-05 12:00", "closed", 0),                        # Saturday
])
def test_live_state_table(et, state, refresh):
    now = pd.Timestamp(et, tz="America/New_York")
    out = TF.live_state(now)
    assert out["state"] == state
    assert out["refresh_sec"] == refresh
    assert out["as_of"].endswith("ET")


# --- overnight read ---------------------------------------------------------

def _ext_frame(after_lows, after_closes, after_highs=None):
    """3 RTH bars then len(after_lows) extended-hours bars."""
    n_after = len(after_lows)
    idx = pd.date_range("2026-09-01 19:45", periods=3 + n_after, freq="5min", tz="UTC")
    after_highs = after_highs or [c + 0.5 for c in after_closes]
    df = pd.DataFrame({
        "open": [102, 102, 102] + list(after_closes),
        "high": [103, 103, 103] + list(after_highs),
        "low": [101.5, 101.5, 101.5] + list(after_lows),
        "close": [102, 102, 102] + list(after_closes),
        "session": ["rth"] * 3 + ["afterhours"] * n_after,
    }, index=idx)
    return df


SUPPORT = [{"lo": 100.0, "hi": 101.0}]
OVERHEAD = [{"lo": 104.0, "hi": 105.0}]


def test_overnight_touch_held():
    df = _ext_frame(after_lows=[101.8, 100.6, 101.2], after_closes=[102.0, 101.4, 101.9])
    o = sup.overnight_read(df, SUPPORT, OVERHEAD)
    assert o["bars"] == 3 and o["low"] == 100.6
    t = [x for x in o["touches"] if x["side"] == "support"]
    assert len(t) == 1 and t[0]["held"] is True and t[0]["broke"] is False
    assert not [x for x in o["touches"] if x["side"] == "overhead"]


def test_overnight_support_broke():
    df = _ext_frame(after_lows=[101.0, 99.0, 98.5], after_closes=[101.5, 99.5, 98.8])
    o = sup.overnight_read(df, SUPPORT, OVERHEAD)
    t = [x for x in o["touches"] if x["side"] == "support"][0]
    assert t["broke"] is True and t["held"] is False
    assert o["change_pct"] < 0


def test_overnight_overhead_rejected():
    df = _ext_frame(after_lows=[102, 103, 102.5], after_closes=[103, 103.8, 102.8],
                    after_highs=[103.5, 104.6, 103.2])
    o = sup.overnight_read(df, SUPPORT, OVERHEAD)
    t = [x for x in o["touches"] if x["side"] == "overhead"][0]
    assert t["held"] is True and t["broke"] is False


def test_overnight_all_rth_frame_has_no_overnight():
    df = _ext_frame(after_lows=[], after_closes=[])
    assert sup.overnight_read(df, SUPPORT, OVERHEAD) is None


def _overnight_then_session(after_lows, after_closes, n_rth_today=6):
    """prev-session RTH -> after-hours -> pre-market -> today's RTH run."""
    n = 3 + len(after_lows) + n_rth_today
    idx = pd.date_range("2026-09-01 19:45", periods=n, freq="5min", tz="UTC")
    closes = [102, 102, 102] + list(after_closes) + [103] * n_rth_today
    lows = [101.5, 101.5, 101.5] + list(after_lows) + [102.5] * n_rth_today
    return pd.DataFrame({
        "open": closes, "high": [c + 0.5 for c in closes], "low": lows,
        "close": closes,
        "session": (["rth"] * 3 + ["afterhours"] * len(after_lows)
                    + ["rth"] * n_rth_today),
    }, index=idx)


def test_overnight_survives_the_open_and_still_reports_last_night():
    # REGRESSION (review 2026-09-02): anchoring on the LAST rth bar made the
    # read say "nothing printed" from 09:35 ET until the close, every day.
    df = _overnight_then_session(after_lows=[100.6, 101.2], after_closes=[101.4, 101.9])
    o = sup.overnight_read(df, SUPPORT, OVERHEAD)
    assert o["bars"] == 2
    assert o["low"] == 100.6
    assert [t["side"] for t in o["touches"]] == ["support"]
    assert o["since"].endswith("ET")


def test_overnight_gap_straight_through_a_band_is_a_break_not_silence():
    # REGRESSION (review 2026-09-02): an extreme-only test reported "No level
    # touched" while price sat 7% under the support band.
    df = _ext_frame(after_lows=[93.5, 93.0, 93.4], after_closes=[93.9, 93.9, 93.9])
    o = sup.overnight_read(df, SUPPORT, OVERHEAD)
    t = [x for x in o["touches"] if x["side"] == "support"]
    assert len(t) == 1 and t[0]["broke"] is True and t[0]["gapped"] is True
    assert o["change_pct"] < -7


def test_overnight_gap_up_through_overhead_is_a_clear():
    df = _ext_frame(after_lows=[106.0], after_closes=[107.0], after_highs=[107.5])
    t = [x for x in sup.overnight_read(df, SUPPORT, OVERHEAD)["touches"]
         if x["side"] == "overhead"]
    assert len(t) == 1 and t[0]["broke"] is True and t[0]["gapped"] is True


def test_overnight_ignores_an_inverted_band():
    df = _ext_frame(after_lows=[100.6], after_closes=[101.5])
    assert sup.overnight_read(df, [{"lo": 101.0, "hi": 100.0}], []) ["touches"] == []


def test_overnight_none_without_session_tags():
    df = _ext_frame(after_lows=[101], after_closes=[101.5]).drop(columns=["session"])
    assert sup.overnight_read(df, SUPPORT, OVERHEAD) is None
    assert sup.overnight_read(None, SUPPORT, OVERHEAD) is None


# --- bar serializer ---------------------------------------------------------

def test_frame_bars_flags_extended_hours_only():
    df = _ext_frame(after_lows=[101.8], after_closes=[102.0])
    df.loc[df.index[0], "session"] = "premarket"
    bars = sup._frame_bars(df)
    assert bars[0]["s"] == "pre"
    assert "s" not in bars[1]            # rth
    assert bars[-1]["s"] == "ah"
    assert len(bars[0]["t"]) == 16       # HH:MM stamps
    # ET on the axis: the frame is indexed 19:45 UTC -> 15:45 ET
    assert bars[0]["t"].endswith("15:45")


def test_overnight_times_are_et():
    df = _ext_frame(after_lows=[100.6], after_closes=[101.5])
    o = sup.overnight_read(df, SUPPORT, OVERHEAD)
    assert o["low_at"].endswith("ET") and " 16:00 ET" in o["low_at"]   # 20:00 UTC bar
    assert o["touches"][0]["at"].endswith("ET")


# --- source guards ----------------------------------------------------------

@pytest.mark.parametrize("et, state", [
    ("2026-09-07 10:00", "closed"),      # Labor Day — a weekday
    ("2026-11-26 10:00", "closed"),      # Thanksgiving
    ("2026-11-27 11:00", "rth"),         # half day, still open at 11:00
    ("2026-11-27 18:00", "closed"),      # half day, ext session over by 17:00
])
def test_live_state_respects_holidays_and_half_days(et, state):
    # REGRESSION (review 2026-09-02): a weekday-only check polled Massive
    # every 30s all Labor Day (~1,900 calls per open tab).
    assert TF.live_state(pd.Timestamp(et, tz="America/New_York"))["state"] == state


def test_ext_frame_refuses_to_feed_the_zone_engine():
    # REGRESSION (review 2026-09-02): the live frame was reachable from the
    # zone-map dropdown, which would build zones out of 07:12 prints.
    df, meta = TF.frame_for("AAPL", "5m_live")
    assert df is None and "chart frame" in meta["reason"]


def test_data_through_is_et_so_an_evening_bar_is_not_tomorrow():
    # REGRESSION: the right-labelled 19:55-20:00 ET bar is 00:00 UTC the
    # next day, so the footer read "bars through <tomorrow>" every evening.
    idx = pd.date_range("2026-09-03 00:00", periods=1, freq="5min", tz="UTC")
    df = pd.DataFrame({"open": 1, "high": 1, "low": 1, "close": 1}, index=idx)
    assert sup._last_bar_date(df, intraday=True) == "2026-09-02"
    # ...and a DAILY frame (dates at midnight) is never shifted back a day
    assert sup._last_bar_date(df) == "2026-09-03"


def test_for_symbol_reads_levels_from_the_daily_window_on_the_live_frame():
    src = (Path(__file__).resolve().parents[1] / "chart_maps" / "support.py").read_text()
    assert 'daily_df, _have_d, levels_as_of = _frame_for(sym, spec["bars"])' in src
    assert 'and not ext_frame:\n            _record_signal' in src   # no double ledger
    assert 'opening_range_from_bars' in src        # one minute fetch per poll
    assert 'allow_ext=True' in src
    assert '"live": tf_mod.live_state() if ext_frame else None' in src
    assert 'overnight_read(chart_df' in src
