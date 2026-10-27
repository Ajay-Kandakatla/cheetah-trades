"""`weekly` — "The long view", the weekly Support-tab chart frame.

Ajay 2026-10-26, verbatim:

    "Can you build me 1 min bar chart and also 1 week bar chart in the supply
     and demand"

The weekly frame is ONE composition of two existing engines: the Support DAILY
frame (`support._frame_for`, today's live bar overlaid exactly as on the daily
chart) resampled by `chart_maps.ema_frames.resample_ohlcv(…, "weekly")` — W-FRI,
closed=right, label=right: Mon–Fri, labelled by that week's Friday. The forming
week is drawn (`s: "forming"`) and never read as structure. The Zoom sets how
far back (`support.weekly_bars_for`: 6m 26 · 1y 52 · 2y 104 · 3y 156 · 5y 260).
Support tab only (`support_only`) — every structure caller refuses it. The board
block stays daily. UNMEASURED; its BUY/SELL is never recorded.

The negatives carry the weight: `1w` is the one-week WINDOW and never this
frame; the minute resampler is still left-closed; there is no second weekly
resampler; a zoom weekly bars cannot fill lands on 1 year, never on the daily
overlay.
"""
from __future__ import annotations

import inspect
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from chart_maps import ema_frames as EF
from chart_maps import support as S
from supply_demand import key_levels as KL
from supply_demand import patterns as pat_mod
from supply_demand import price_zones as pz
from supply_demand import timeframes as TF


# --- fixtures ---------------------------------------------------------------

def _daily(start: str, end: str, drop=()) -> pd.DataFrame:
    """Business-day frame with DISTINCT OHLCV per day, on a ~12-week sawtooth
    so weekly bars hold swings; `drop` removes dates (holidays / gaps)."""
    idx = pd.bdate_range(start, end)
    idx = idx[~idx.strftime("%Y-%m-%d").isin(list(drop))]
    i = np.arange(len(idx))
    c = 50.0 + 10.0 * np.abs(((i % 60) - 30)) / 30.0 + i * 1e-3
    o = c - 0.1 - (i % 3) * 0.01
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) + 0.3 + (i % 7) * 0.01,
                         "low": np.minimum(o, c) - 0.3 - (i % 5) * 0.01,
                         "close": c, "volume": 1e6 + i}, index=idx)


def _agg():
    return {"open": "first", "high": "max", "low": "min", "close": "last",
            "volume": "sum"}


WED = date(2026, 10, 28)


def _stub_frame(monkeypatch, daily: pd.DataFrame, today: date = WED) -> None:
    monkeypatch.setattr(S, "_frame_for",
                        lambda sym, need, **k: (daily.copy(), len(daily), 1.7e9,
                                                daily.copy()))
    monkeypatch.setattr(EF, "_today_et", lambda: today)


@pytest.fixture
def tab(monkeypatch):
    """The Support tab on the weekly frame: a 2y daily frame ending Wed
    2026-10-28, nothing on the network."""
    from sepa import prices
    daily = _daily("2024-10-28", "2026-10-28")
    _stub_frame(monkeypatch, daily)
    monkeypatch.setattr(prices, "bulk_snapshot", lambda *a, **k: {})
    monkeypatch.setattr(pat_mod, "opening_range", lambda sym, minutes: None)
    recorded: list = []
    monkeypatch.setattr(S, "_record_signal", lambda *a, **k: recorded.append(a))
    return {"daily": daily, "recorded": recorded}


# --- the spec ---------------------------------------------------------------

def test_the_weekly_spec_is_registered():
    spec = TF.tf_spec(TF.WEEKLY)
    assert spec["key"] == "weekly" == TF.WEEKLY
    assert spec["label"] == "The long view"
    assert spec["bar_label"] == "weekly"
    assert spec["window_label"] == ("1 year by default — the Zoom dropdown sets "
                                    "how far back, up to 5 years")
    assert spec["bars"] == 260 == S.weekly_bars_for("5y")
    assert spec["days"] == 0
    assert spec["swing_window"] == 4
    assert spec["support_only"] is True
    assert "ext_hours" not in spec
    assert spec["orb_minutes"] is None


def test_the_aliases_resolve_to_weekly():
    for raw in ("weekly", "W", " week ", "wk", "1WK"):
        assert TF.parse_tf(raw) == TF.WEEKLY, raw


def test_NEGATIVE_1w_is_a_window_not_a_frame():
    assert TF.parse_tf("1w") == TF.DAILY
    assert "1w" not in TF._ALIAS
    assert S.parse_window("1w") == "1w"


def test_window_to_weeks_mapping():
    assert S.WEEKLY_WINDOWS == ("6m", "1y", "2y", "3y", "5y")
    assert {k: S.weekly_bars_for(k) for k in S.WEEKLY_WINDOWS} == {
        "6m": 26, "1y": 52, "2y": 104, "3y": 156, "5y": 260}


def test_NEGATIVE_a_window_weekly_bars_cannot_fill_lands_on_1y(tab):
    for k in ("1w", "2w", "1m", "3m", "all", "junk"):
        out = S.for_symbol("TEST", k, tf="weekly")
        assert out["window"] == "1y", (k, out["window"])
        assert "per_window" not in out, k          # never the daily overlay
        assert out["timeframe"] == "weekly", k


# --- the weekly convention ---------------------------------------------------

# The REAL daily cache is stamped UTC-naive at 04:00 (EDT) / 05:00 (EST), and
# today's overlaid row at 00:00 (container probe of NVDA/AAPL, 2026-10-26).
# pandas widens a right-closed weekly bin by one day so a Friday 04:00 bar stays
# in ITS week — pinned here over every stamp the cache carries, plus the mixed
# tail, so a refactor cannot push every Friday into the next week unnoticed.
STAMPS = ("00:00", "04:00", "05:00", "mixed")


def _stamped(d: pd.DataFrame, stamp: str) -> pd.DataFrame:
    if stamp == "mixed":
        hours = [4 if i % 2 else 5 for i in range(len(d))]
        hours[-1] = 0
        off = pd.to_timedelta(hours, unit="h")
    else:
        off = pd.Timedelta(stamp + ":00")
    out = d.copy()
    out.index = d.index.normalize() + off
    return out


def _day(d: pd.DataFrame, ymd: str) -> pd.DataFrame:
    return d[d.index.normalize() == pd.Timestamp(ymd)]


@pytest.mark.parametrize("stamp", STAMPS)
def test_friday_belongs_to_its_own_week(stamp):
    d = _stamped(_daily("2026-10-12", "2026-10-23"), stamp)
    wk = EF.resample_ohlcv(d, "weekly")
    assert [t.strftime("%Y-%m-%d") for t in wk.index] == ["2026-10-16", "2026-10-23"]
    week1 = d[(d.index.normalize() >= pd.Timestamp("2026-10-12"))
              & (d.index.normalize() <= pd.Timestamp("2026-10-16"))]
    assert len(week1) == 5
    row = wk.iloc[0]
    assert row["open"] == week1["open"].iloc[0]          # Monday's open
    assert row["close"] == week1["close"].iloc[-1]       # Friday's close
    assert row["high"] == week1["high"].max()
    assert row["low"] == week1["low"].min()
    assert row["volume"] == week1["volume"].sum()


@pytest.mark.parametrize("stamp", STAMPS)
def test_holiday_week_ends_on_its_friday_label_with_mon_thu(stamp):
    d = _stamped(_daily("2026-03-30", "2026-04-10", drop=("2026-04-03",)),  # Good Friday
                 stamp)
    wk = EF.resample_ohlcv(d, "weekly")
    labels = [t.strftime("%Y-%m-%d") for t in wk.index]
    assert labels == ["2026-04-03", "2026-04-10"]
    row = wk.loc[pd.Timestamp("2026-04-03")]
    mon_thu = d[(d.index.normalize() >= pd.Timestamp("2026-03-30"))
                & (d.index.normalize() <= pd.Timestamp("2026-04-02"))]
    assert len(mon_thu) == 4
    assert row["close"] == _day(d, "2026-04-02")["close"].iloc[0]
    assert row["volume"] == mon_thu["volume"].sum()


@pytest.mark.parametrize("stamp", ("04:00", "05:00"))
def test_NEGATIVE_a_left_closed_weekly_bin_would_push_friday_into_next_week(stamp):
    """The failure the stamp tests guard against, made visible: the same 04:00 /
    05:00 bars through a LEFT-closed W-FRI resample put Fri 10-16 into the week
    labelled 10-23 — so the explicit right-closed call is load-bearing."""
    d = _stamped(_daily("2026-10-12", "2026-10-23"), stamp)
    wrong = d.resample("W-FRI", closed="left", label="right").agg(_agg()).dropna()
    good = EF.resample_ohlcv(d, "weekly")
    fri = _day(d, "2026-10-16")["close"].iloc[0]
    assert good.loc[pd.Timestamp("2026-10-16"), "close"] == fri
    assert wrong.iloc[0]["close"] != fri


def test_NEGATIVE_an_empty_week_is_dropped_not_painted():
    gap = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2026-10-05", "2026-10-09")]
    d = _daily("2026-09-28", "2026-10-16", drop=gap)
    wk = EF.resample_ohlcv(d, "weekly")
    labels = [t.strftime("%Y-%m-%d") for t in wk.index]
    assert "2026-10-09" not in labels
    assert labels == ["2026-10-02", "2026-10-16"]
    assert not wk.isna().any().any()


def test_first_and_last_bar_ohlc_exact():
    idx = pd.bdate_range("2026-10-05", "2026-10-23")              # 3 weeks
    o = [10, 11, 12, 13, 14, 20, 21, 22, 23, 24, 30, 31, 32, 33, 34]
    h = [15, 16, 19, 14, 15, 25, 26, 29, 24, 25, 35, 39, 33, 34, 35]
    lo = [9, 8, 11, 12, 13, 19, 18, 21, 22, 23, 29, 28, 31, 32, 33]
    c = [11, 12, 13, 14, 15, 21, 22, 23, 24, 25, 31, 32, 33, 34, 36]
    v = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    d = pd.DataFrame({"open": o, "high": h, "low": lo, "close": c, "volume": v},
                     index=idx, dtype=float)
    wk = EF.resample_ohlcv(d, "weekly")
    assert len(wk) == 3
    assert wk.iloc[0].to_dict() == {"open": 10.0, "high": 19.0, "low": 8.0,
                                    "close": 15.0, "volume": 15.0}
    assert wk.iloc[-1].to_dict() == {"open": 30.0, "high": 39.0, "low": 28.0,
                                     "close": 36.0, "volume": 65.0}


def test_the_week_still_forming_is_flagged_and_kept_out_of_structure(monkeypatch):
    d = _daily("2026-10-05", "2026-10-28")
    monkeypatch.setattr(S, "_frame_for",
                        lambda sym, need, **k: (d, len(d), 1.7e9, d))
    wk = S._weekly_frames("X", 52, today=date(2026, 10, 28))
    assert wk["forming"] == "2026-10-30"
    assert len(wk["closed"]) == len(wk["full"]) - 1
    assert wk["closed"].index[-1] < wk["full"].index[-1]
    assert wk["daily"] is d
    assert "W-FRI" in wk["source"]


def test_NEGATIVE_a_finished_week_is_not_forming(monkeypatch):
    d = _daily("2026-10-05", "2026-10-30")
    monkeypatch.setattr(S, "_frame_for",
                        lambda sym, need, **k: (d, len(d), 1.7e9, d))
    wk = S._weekly_frames("X", 52, today=date(2026, 10, 31))
    assert wk["forming"] is None
    assert wk["closed"].equals(wk["full"])


def test_the_weekly_resample_is_explicitly_right_closed_and_unchanged():
    src = inspect.getsource(EF.resample_ohlcv)
    assert 'closed="right", label="right"' in src
    d = _daily("2025-01-01", "2026-10-28", drop=("2025-07-04", "2026-04-03"))
    for frame, rule in (("weekly", "W-FRI"), ("monthly", "ME")):
        want = d.resample(rule).agg(_agg()).dropna(how="any")    # pandas defaults
        got = EF.resample_ohlcv(d, frame)
        pd.testing.assert_frame_equal(got, want)


def test_NEGATIVE_the_minute_resampler_is_still_left_closed():
    assert 'label="right", closed="left"' in inspect.getsource(TF.resample_ohlcv)


def test_NEGATIVE_no_parallel_weekly_resample():
    assert ".resample(" not in inspect.getsource(S)
    assert inspect.getsource(TF).count(".resample(") == 1


# --- the Support tab ----------------------------------------------------------

def test_the_support_tab_reads_weekly_levels_off_closed_weeks_only(tab, monkeypatch):
    calls: list = []
    real = pz.compute

    def spy(df, *a, **k):
        calls.append((df, k))
        return real(df, *a, **k)
    monkeypatch.setattr(pz, "compute", spy)
    out = S.for_symbol("TEST", "1y", tf="weekly")
    assert not out.get("error"), out.get("error")
    df, kw = calls[0]
    assert kw["lookback_bars"] == 52
    assert kw["swing_window"] == 4
    assert df.index[-1].strftime("%Y-%m-%d") == "2026-10-23"    # last COMPLETED Friday
    bars = out["tile"]["bars"]
    assert len(bars) <= 52
    assert bars[-1]["s"] == "forming" and bars[-1]["t"] == "2026-10-30"
    assert all("s" not in b for b in bars[:-1])
    assert out["data_through"] == "2026-10-28"
    assert out["levels_bar_label"] == "weekly"
    assert out["zoom_applies"] is True
    assert out["live"] is None
    assert out["forming"]["date"] == "2026-10-30"
    assert out["note"].count(S.WEEKLY_UNMEASURED) == 1
    assert "still forming" in out["note"]
    assert out["chart_span"].startswith("52 x weekly bars · 1 year")
    assert out["timeframe_meta"]["forming"] == "2026-10-30"
    assert out["tile"]["badges"] and "still forming" in out["tile"]["badges"][0]["text"]


def test_NEGATIVE_an_after_hours_print_in_the_forming_week_moves_the_bar_not_a_level(
        tab, monkeypatch):
    base = S.for_symbol("TEST", "1y", tf="weekly")
    moved = tab["daily"].copy()
    last = moved.index[-1]
    moved.loc[last, "close"] = moved.loc[last, "close"] + 0.37    # AH overwrite
    moved.loc[last, "high"] = max(moved.loc[last, "high"], moved.loc[last, "close"])
    _stub_frame(monkeypatch, moved)
    after = S.for_symbol("TEST", "1y", tf="weekly")
    assert not base.get("error") and not after.get("error")
    assert base["tile"]["bars"][-1]["c"] != after["tile"]["bars"][-1]["c"]

    def bands(out):
        return [(b["lo"], b["hi"], b["touches"]) for side in ("supports", "overhead")
                for b in (out.get(side) or [])]
    assert bands(base) == bands(after)
    assert bands(base), "the fixture must hold a level"


def test_the_board_block_stays_daily(tab, monkeypatch):
    seen: list = []
    real = S.board_read

    def spy(closed, sym, px):
        seen.append(closed)
        return real(closed, sym, px)
    monkeypatch.setattr(S, "board_read", spy)
    S.for_symbol("TEST", "1y", tf="weekly")
    assert seen
    idx = seen[0].index
    assert len(idx) == len(tab["daily"])
    assert any(t.weekday() != 4 for t in idx)          # sessions, not Friday labels


def test_the_weekly_pattern_scan_reads_the_windows_daily_sessions(tab, monkeypatch):
    from patterns import timeframe as pat_tf
    seen: list = []

    def spy(sym, key, *, df=None):
        seen.append((key, df))
        return {"symbol": sym, "timeframe": key, "patterns": []}
    monkeypatch.setattr(pat_tf, "scan", spy)
    S.for_symbol("TEST", "1y", tf="weekly")
    assert len(seen) == 1
    key, df = seen[0]
    assert key == "daily"
    assert len(df) == 252
    assert any(t.weekday() != 4 for t in df.index)


def test_NEGATIVE_weekly_draws_no_opening_range_and_fetches_no_minutes(tab, monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("the weekly frame reached for minute bars")
    monkeypatch.setattr(pat_mod, "opening_range", _boom)
    monkeypatch.setattr(TF, "intraday_raw", _boom)
    out = S.for_symbol("TEST", "1y", tf="weekly")
    assert not out.get("error"), out.get("error")
    assert out["opening_range"] is None


def test_NEGATIVE_a_weekly_signal_is_never_recorded_and_says_why(tab):
    out = S.for_symbol("TEST", "1y", tf="weekly")
    assert tab["recorded"] == []
    sig = out["signal"]
    assert sig is not None
    assert sig["recorded"] is False
    assert "the weekly frame has none" in sig["recorded_note"]


def test_NEGATIVE_structure_callers_refuse_weekly(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("a structure caller built the weekly frame")
    monkeypatch.setattr(S, "_frame_for", _boom)
    df, meta = TF.frame_for("X", "weekly")
    assert df is None
    assert "chart frame" in (meta["reason"] or "")
    assert meta["reason"] == TF.WEEKLY_REFUSED
    assert "chart frame" in (pz.for_symbol("X", tf="weekly").get("error") or "")
    from patterns import timeframe as pat_tf
    assert pat_tf.scan("X", "weekly")["patterns"] == []


def test_frame_for_weekly_on_the_support_path_flags_the_forming_week(monkeypatch):
    _stub_frame(monkeypatch, _daily("2020-01-01", "2026-10-28"))
    df, meta = TF.frame_for("X", "weekly", allow_ext=True)
    assert df is not None, meta
    assert meta["partial"] is True
    assert meta["forming"] == "2026-10-30"
    assert len(df) <= 260
    assert meta["ext_hours"] is False


def test_weekly_short_history_is_counted_in_weeks(tab, monkeypatch):
    _stub_frame(monkeypatch, _daily("2026-04-06", "2026-10-28"))
    out = S.for_symbol("TEST", "1y", tf="weekly")
    assert not out.get("error"), out.get("error")
    assert out["short_history"] == {"have": 30, "asked": 52, "unit": "weekly bars"}


def test_NEGATIVE_daily_short_history_has_no_unit(monkeypatch):
    from sepa import prices
    short = _daily("2026-06-01", "2026-10-23")
    monkeypatch.setattr(prices, "load_prices", lambda sym, *a, **k: short.copy())
    monkeypatch.setattr(prices, "bulk_snapshot", lambda *a, **k: {})
    monkeypatch.setattr(S, "_shared_frame_as_of", lambda sym: None)
    monkeypatch.setattr(prices, "_fetch_massive", lambda *a, **k: None)
    monkeypatch.setattr(pat_mod, "opening_range", lambda sym, minutes: None)
    monkeypatch.setattr(S, "_record_signal", lambda *a, **k: None)
    S._deep_cache.clear()
    out = S.for_symbol("TEST", "1y", tf="daily")
    assert not out.get("error"), out.get("error")
    assert out["short_history"] and "unit" not in out["short_history"]
    assert "forming" not in out                 # the key exists only on weekly


def test_recency_on_weekly_is_counted_in_weeks(tab):
    out = S.for_symbol("TEST", "1y", tf="weekly")
    keys = [s["k"] for s in out["tile"]["stats"]]
    assert "touched in the last 21 × weekly bars" in keys, keys
    text = json.dumps(out["tile"]["stats"], ensure_ascii=False) + out["tile"]["why"]
    assert "last month" not in text


def test_weekly_moving_averages_are_in_weekly_bars(tab):
    out = S.for_symbol("TEST", "1y", tf="weekly")
    tile = out["tile"]
    curves = tile.get("curves") or []
    assert curves, "no moving average reached the weekly tile"
    for c in curves:
        assert len(c["values"]) == len(tile["bars"]), c["tone"]
    ema9 = next(c for c in curves if c["tone"] == "ema9")
    daily_ema9 = float(tab["daily"]["close"].ewm(span=9, adjust=False).mean().iloc[-1])
    assert ema9["values"][-1] is not None
    assert abs(ema9["values"][-1] - daily_ema9) > 1e-6


def test_key_levels_on_weekly_mirror_daily():
    assert KL.FRAME_PERIODS["weekly"] == KL.FRAME_PERIODS["daily"]
    assert "weekly" not in KL.EXT_FRAMES


def test_the_fe_fixture_is_the_served_list():
    path = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "components"
            / "__fixtures__" / "support_timeframes_2026_10_26.json")
    assert json.loads(path.read_text(encoding="utf-8")) == TF.tf_options(include_live=True)


def test_NEGATIVE_no_nan_and_no_bounce_in_a_weekly_payload(tab):
    for window in ("1y", "5y"):
        out = S.for_symbol("TEST", window, tf="weekly")
        assert not out.get("error"), out.get("error")
        dump = json.dumps(out, allow_nan=False, ensure_ascii=False)
        assert "bounce" not in dump.lower()
