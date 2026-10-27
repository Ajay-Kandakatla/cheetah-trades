"""`1min` — "Today, to the minute", the 1-minute Support-tab chart frame.

Ajay 2026-10-26, verbatim:

    "Can you build me 1 min bar chart and also 1 week bar chart in the supply
     and demand"

The 1-minute frame is the `5m_today` path at rule "1min": raw Massive minutes,
extended hours, clipped to the latest ET date from 04:00, at most 960 bars,
`ext_hours` (Support tab only — every structure caller refuses it). The forming
minute is flagged `partial` while the tape is open, so it is drawn and never
read as structure. Neither the frame nor its BUY/SELL is measured or recorded.

The negatives carry the weight: `1m` is the one-month WINDOW and never this
frame; the five older frames are byte-identical; the 5-minute frames' partial
rule and unrecorded sentence did not move; structure callers still refuse.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from chart_maps import support as S
from supply_demand import key_levels as KL
from supply_demand import patterns as pat_mod
from supply_demand import price_zones as pz
from supply_demand import timeframes as TF


# --- fixtures ---------------------------------------------------------------

def _minutes(day: str, start: str, end: str, session: str,
             base: float = 100.0, offset: int = 0) -> pd.DataFrame:
    """One block of 1-minute bars stamped in ET, served UTC-naive with the
    minute START as the index (as `daytrading.data` serves them). DISTINCT
    OHLCV per minute so exactness is checkable, on a sawtooth so the zone
    engine finds swings."""
    idx = (pd.date_range(f"{day} {start}", f"{day} {end}", freq="1min",
                         tz="America/New_York").tz_convert("UTC").tz_localize(None))
    i = np.arange(len(idx)) + offset
    saw = np.abs(((i % 40) - 20)) / 10.0              # 0..2..0 every 40 minutes
    o = base + saw + i * 1e-4
    c = o + 0.01
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) + 0.02,
                         "low": np.minimum(o, c) - 0.02, "close": c,
                         "volume": 100.0 + i, "session": session}, index=idx)


def _full_day(day: str, base: float = 100.0) -> pd.DataFrame:
    """04:00-09:29 premarket, 09:30-15:59 rth, 16:00-19:59 afterhours —
    exactly (20 - 4) * 60 = 960 minutes."""
    out = pd.concat([
        _minutes(day, "04:00", "09:29", "premarket", base, 0),
        _minutes(day, "09:30", "15:59", "rth", base, 330),
        _minutes(day, "16:00", "19:59", "afterhours", base, 720),
    ])
    assert len(out) == 960
    return out


def _raw() -> pd.DataFrame:
    return pd.concat([_full_day("2026-10-23", 90.0),
                      _full_day("2026-10-26", 100.0)]).sort_index()


def _two_day_fixture() -> pd.DataFrame:
    """The `_two_days` shape of test_5m_today_frame_2026_09_17.py."""
    blocks = []
    for day in ("2026-09-16", "2026-09-17"):
        blocks.append(_minutes(day, "04:00", "04:29", "premarket"))
        blocks.append(_minutes(day, "09:30", "09:59", "rth"))
        blocks.append(_minutes(day, "16:00", "16:29", "afterhours"))
    return pd.concat(blocks).sort_index()


def _daily(start: str, end: str, drop=()) -> pd.DataFrame:
    idx = pd.bdate_range(start, end)
    idx = idx[~idx.strftime("%Y-%m-%d").isin(list(drop))]
    i = np.arange(len(idx))
    c = 80.0 + 6.0 * np.abs(((i % 20) - 10)) / 10.0 + i * 1e-3
    o = c - 0.1
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) + 0.3,
                         "low": np.minimum(o, c) - 0.3, "close": c,
                         "volume": 1e6 + i}, index=idx)


def _et(idx) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(idx)
    return (idx.tz_localize("UTC") if idx.tz is None else idx).tz_convert("America/New_York")


def _rth_state(*a, **k):
    return {"state": "rth", "refresh_sec": TF.LIVE_REFRESH_SEC,
            "as_of": "2026-10-26 10:00:00 ET"}


def _closed_state(*a, **k):
    return {"state": "closed", "refresh_sec": 0, "as_of": "2026-10-26 21:00:00 ET"}


@pytest.fixture
def tab(monkeypatch):
    """The Support tab on the 1-minute frame, nothing on the network."""
    from sepa import prices
    raw = _raw()
    daily = _daily("2025-08-01", "2026-10-23")[-300:]
    monkeypatch.setattr(TF, "intraday_raw", lambda sym, key=None: raw.copy())
    monkeypatch.setattr(prices, "load_prices", lambda sym, *a, **k: daily.copy())
    monkeypatch.setattr(prices, "bulk_snapshot", lambda *a, **k: {})
    monkeypatch.setattr(S, "_shared_frame_as_of", lambda sym: None)
    monkeypatch.setattr(TF, "live_state", _rth_state)
    monkeypatch.setattr(pat_mod, "opening_range", lambda sym, minutes: None)
    recorded: list = []
    monkeypatch.setattr(S, "_record_signal", lambda *a, **k: recorded.append(a))
    S._deep_cache.clear()
    return {"raw": raw, "daily": daily, "recorded": recorded}


# --- the spec ---------------------------------------------------------------

def test_the_1min_spec_is_registered():
    spec = TF.tf_spec(TF.M1_TODAY)
    assert spec["key"] == "1min" == TF.M1_TODAY
    assert spec["label"] == "Today, to the minute"
    assert spec["bar_label"] == "1-minute"
    assert spec["window_label"] == "today only, from 04:00 ET"
    assert spec["bars"] == (20 - 4) * 60 == 960
    assert spec["days"] == 1
    assert spec["rule"] == "1min"
    assert spec["swing_window"] == 2
    assert spec["ext_hours"] is True
    assert spec["orb_minutes"] == TF.tf_spec(TF.M5_TODAY)["orb_minutes"]
    assert "support_only" not in spec


def test_1min_sits_FIRST_and_weekly_LAST_in_the_served_list():
    assert [o["key"] for o in TF.tf_options(include_live=True)] == [
        "1min", "5m_today", "24h", "15m", "60m", "daily", "weekly"]


def test_NEGATIVE_neither_new_frame_reaches_the_structure_list():
    assert [o["key"] for o in TF.tf_options()] == ["15m", "60m", "daily"]


def test_the_aliases_a_url_might_carry_resolve_to_1min():
    for raw in ("1min", "1-MIN", " 1minute ", "m1"):
        assert TF.parse_tf(raw) == TF.M1_TODAY, raw


def test_NEGATIVE_1m_is_a_window_not_a_frame():
    assert TF.parse_tf("1m") == TF.DAILY
    assert "1m" not in TF._ALIAS
    assert S.parse_window("1m") == "1m"


# --- the frame --------------------------------------------------------------

def test_the_frame_is_today_only_from_0400_and_at_most_960_bars():
    df, meta = TF.frame_for("X", TF.M1_TODAY, raw=_raw(), allow_ext=True)
    assert df is not None, meta
    et = _et(df.index)
    assert {str(d) for d in et.date} == {"2026-10-26"}
    assert len(df) == 960 <= TF.tf_spec(TF.M1_TODAY)["bars"]
    # right-labelled: the 04:00 minute is stamped 04:01, the 19:59 one 20:00
    assert et[0].strftime("%H:%M") == "04:01"
    assert et[-1].strftime("%H:%M") == "20:00"
    assert meta["session"] == "2026-10-26"


def test_each_1min_bar_is_its_own_minute_relabelled_at_its_close():
    raw = _raw()
    df, _meta = TF.frame_for("X", TF.M1_TODAY, raw=raw, allow_ext=True)
    assert "session" in df.columns
    for label, row in df.iterrows():
        src = raw.loc[label - pd.Timedelta(minutes=1)]
        for col in ("open", "high", "low", "close", "volume"):
            assert row[col] == src[col], (label, col)
        assert row["session"] == src["session"], label


def test_the_forming_minute_is_partial_while_the_tape_is_open(monkeypatch):
    monkeypatch.setattr(TF, "live_state", _rth_state)
    _df, meta = TF.frame_for("X", TF.M1_TODAY, raw=_raw(), allow_ext=True)
    assert meta["partial"] is True


def test_NEGATIVE_a_closed_tape_has_no_forming_minute(monkeypatch):
    monkeypatch.setattr(TF, "live_state", _closed_state)
    _df, meta = TF.frame_for("X", TF.M1_TODAY, raw=_raw(), allow_ext=True)
    assert meta["partial"] is False


def test_NEGATIVE_the_5m_today_partial_rule_is_unchanged(monkeypatch):
    monkeypatch.setattr(TF, "live_state", _rth_state)
    _a, open_meta = TF.frame_for("X", TF.M5_TODAY, raw=_two_day_fixture(),
                                 allow_ext=True)
    monkeypatch.setattr(TF, "live_state", _closed_state)
    _b, closed_meta = TF.frame_for("X", TF.M5_TODAY, raw=_two_day_fixture(),
                                   allow_ext=True)
    assert open_meta["partial"] is closed_meta["partial"] is False


def test_NEGATIVE_structure_callers_refuse_1min(monkeypatch):
    df, meta = TF.frame_for("X", TF.M1_TODAY, raw=_raw())
    assert df is None
    assert "chart frame" in (meta["reason"] or "")

    def _boom(*a, **k):
        raise AssertionError("a structure caller fetched 1-minute bars")
    monkeypatch.setattr(TF, "intraday_raw", _boom)
    out = pz.for_symbol("X", tf="1min")
    assert "chart frame" in (out.get("error") or ""), out


# --- the Support tab ----------------------------------------------------------

def test_the_support_tab_reads_closed_minutes_only(tab, monkeypatch):
    seen: list = []
    real = pz.compute

    def spy(df, *a, **k):
        seen.append(df)
        return real(df, *a, **k)
    monkeypatch.setattr(pz, "compute", spy)
    out = S.for_symbol("ACME", "6m", tf="1min")
    assert not out.get("error"), out.get("error")
    bars = out["tile"]["bars"]
    assert seen, "the zone engine never ran"
    assert len(seen[0]) == len(bars) - 1          # the forming minute is not structure
    assert len(bars) <= 960
    assert {b["t"][:10] for b in bars} == {"2026-10-26"}
    assert out["live"]["refresh_sec"] == TF.LIVE_REFRESH_SEC
    assert out["levels_bar_label"] == "1-minute"
    assert out["timeframe"] == "1min"


def test_extended_hours_bars_carry_the_shading_flag(tab):
    out = S.for_symbol("ACME", "6m", tf="1min")
    bars = out["tile"]["bars"]
    assert bars
    for b in bars:
        hm = b["t"][11:]
        if "04:01" <= hm <= "09:30":
            assert b.get("s") == "pre", b
        elif hm > "16:00":
            assert b.get("s") == "ah", b
        else:
            assert "s" not in b, b


def test_NEGATIVE_a_1min_signal_is_never_recorded_and_says_why(tab):
    out = S.for_symbol("ACME", "6m", tf="1min")
    assert tab["recorded"] == []
    sig = out["signal"]
    assert sig is not None
    assert sig["recorded"] is False
    assert "the 1-minute frame has none" in sig["recorded_note"]
    assert "5-minute frames" not in sig["recorded_note"]


def test_NEGATIVE_the_5_minute_unrecorded_sentence_is_byte_identical():
    # the literal from support.py at origin/main a218264a
    origin = ("This chart's BUY/SELL is NOT written to the forward ledger: "
              "the ledger scores an outcome over a per-timeframe horizon and "
              "the 5-minute frames have none, so no hit rate is claimed for "
              "it. The daily, 15-minute and 1-hour charts are recorded.")
    assert S._not_recorded_note(TF.M5_TODAY, "5-minute") == S.NOT_RECORDED_5M == origin
    assert S._not_recorded_note(TF.H24, "5-minute") == origin


def test_recency_on_1min_is_counted_in_its_own_bars(tab):
    out = S.for_symbol("ACME", "6m", tf="1min")
    keys = [s["k"] for s in out["tile"]["stats"]]
    assert "touched in the last 21 × 1-minute bars" in keys, keys
    text = json.dumps(out["tile"]["stats"], ensure_ascii=False) + out["tile"]["why"]
    assert "last month" not in text


def test_NEGATIVE_the_older_frames_still_say_last_month(tab):
    out = S.for_symbol("ACME", "6m", tf="daily")
    assert not out.get("error"), out.get("error")
    touched = [s["k"] for s in out["tile"]["stats"] if s["k"].startswith("touched")]
    assert touched == ["touched in last month"]


def test_key_levels_on_1min_mirror_5m_today():
    assert KL.FRAME_PERIODS["1min"] == KL.FRAME_PERIODS["5m_today"]
    assert "1min" in KL.EXT_FRAMES


def test_NEGATIVE_the_five_existing_frames_are_byte_identical():
    # Captured from TF.TIMEFRAMES at origin/main a218264a (step A0), span included.
    snapshot = [
        {'key': '5m_today', 'label': 'Today, for an entry', 'bar_label': '5-minute',
         'window_label': 'today only, from 04:00 ET', 'bars': 192, 'days': 1,
         'swing_window': 2, 'rule': '5min', 'ext_hours': True, 'orb_minutes': 5,
         'span': '5-minute bars · today only, from 04:00 ET'},
        {'key': '24h', 'label': 'Last 24 hours', 'bar_label': '5-minute',
         'window_label': 'the 24 hours up to the last print, pre-market through after-hours',
         'bars': 288, 'days': 3, 'swing_window': 2, 'rule': '5min', 'ext_hours': True,
         'orb_minutes': 5,
         'span': '5-minute bars · the 24 hours up to the last print, pre-market through after-hours'},
        {'key': '15m', 'label': 'The last two weeks', 'bar_label': '15-minute',
         'window_label': 'the last ~10 sessions', 'bars': 260, 'days': 15,
         'swing_window': 2, 'orb_minutes': 15,
         'span': '15-minute bars · the last ~10 sessions'},
        {'key': '60m', 'label': 'The last two months', 'bar_label': '1-hour',
         'window_label': 'the last ~47 sessions', 'bars': 330, 'days': 70,
         'swing_window': 3, 'orb_minutes': 60,
         'span': '1-hour bars · the last ~47 sessions'},
        {'key': 'daily', 'label': 'The big picture', 'bar_label': 'daily',
         'window_label': '1 year by default — the Zoom dropdown sets how far back',
         'bars': 252, 'days': 0, 'swing_window': 4, 'orb_minutes': 30,
         'span': 'daily bars · 1 year by default — the Zoom dropdown sets how far back'},
    ]
    five = [t for t in TF.TIMEFRAMES if t["key"] not in (TF.M1_TODAY, TF.WEEKLY)]
    assert five == snapshot


def test_NEGATIVE_no_nan_and_no_bounce_in_a_1min_payload(tab):
    out = S.for_symbol("ACME", "6m", tf="1min")
    assert not out.get("error"), out.get("error")
    dump = json.dumps(out, allow_nan=False, ensure_ascii=False)
    assert "bounce" not in dump.lower()
