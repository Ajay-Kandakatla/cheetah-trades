"""🛡️ Resiliency tab on Chart Maps (2026-09-30) — WP-BE of the resiliency spec.

Ajay 2026-09-30: "Can you build me a new tab- Resileincy. This is to help me
with #1 - Stocks that are not going to by more than 0.5% during a T1 event like
FOMC or any others like todays Inflation and GDP track T2s as well. #3 - Tape
is positive and bullish EOD or Pre market. but volume has to be accounted for.
We have all of this data already."

Pins `chart_maps/resiliency_tab.py` (the pure functions, build, rank, words,
memo) and the board / api wiring. Positive AND negative cases. Hermetic: the
conftest refuses Mongo; FRED, the calendar, the frames and the snapshot are
all injected; no thread is started (`_spawn` is patched).
"""
from __future__ import annotations

import asyncio
import copy
import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

import macro_calendar as mc
from chart_maps import board as B
from chart_maps import resiliency_tab as R
from sepa import prices
from supply_demand import key_levels as KL

ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]

NOW = datetime(2026, 9, 30, 11, 0, tzinfo=ET)          # Wednesday, rth — Core PCE (T1) + GDP (T2)
PRE = datetime(2026, 9, 30, 8, 52, tzinfo=ET)
SESSION = date(2026, 9, 30)
LAST = "2026-09-29"


# --------------------------------------------------------------------------
# builders
# --------------------------------------------------------------------------
def _market_days(end: str, n: int) -> list:
    from market_hours.reminder import ALL_HOLIDAYS
    out, d = [], pd.Timestamp(end)
    while len(out) < n:
        if d.weekday() < 5 and d.strftime("%Y-%m-%d") not in ALL_HOLIDAYS:
            out.append(d)
        d -= pd.Timedelta(days=1)
    return sorted(out)


DAYS = [d.date().isoformat() for d in _market_days(LAST, 400)]
T1_DAYS = [DAYS[-10], DAYS[-40], DAYS[-70], DAYS[-100], DAYS[-130], DAYS[-160],
           DAYS[-190], DAYS[-220]]
T2_DAYS = [DAYS[-5], DAYS[-35], DAYS[-65], DAYS[-10]]      # the last one is also T1
OLD_T1 = DAYS[-300]                                          # outside the 365-day window


def _frame(closes: dict = None, *, n=400, end=LAST, base=50.0, volume=1_000_000.0,
           drop=(), bars: dict = None):
    idx = pd.DatetimeIndex(_market_days(end, n))
    df = pd.DataFrame({"open": base, "high": base + 1.0, "low": base - 1.0, "close": base,
                       "volume": volume}, index=idx)
    for d, c in (closes or {}).items():
        df.loc[pd.Timestamp(d), "close"] = c
        df.loc[pd.Timestamp(d), "high"] = max(c + 1.0, df.loc[pd.Timestamp(d), "high"])
        df.loc[pd.Timestamp(d), "low"] = min(c - 1.0, df.loc[pd.Timestamp(d), "low"])
    for d, vals in (bars or {}).items():
        for k, v in vals.items():
            df.loc[pd.Timestamp(d), k] = v
    if drop:
        df = df.drop([pd.Timestamp(d) for d in drop])
    return df


def _spy_frame(end=LAST, n=400):
    idx = pd.DatetimeIndex(_market_days(end, n))
    c = np.array([400.0 + i * 0.1 for i in range(len(idx))])
    df = pd.DataFrame({"open": c, "high": c + 2, "low": c - 2, "close": c,
                       "volume": 5e7}, index=idx)
    for d in T1_DAYS[:4]:                         # SPY falls on four T1 days
        i = idx.get_loc(pd.Timestamp(d))
        df.iloc[i, df.columns.get_loc("close")] = float(df["close"].iloc[i - 1]) * 0.99
    return df


def _events(t1=T1_DAYS + [OLD_T1], t2=T2_DAYS):
    ev = [{"date": d, "kind": "cpi", "tier": 1, "label": "CPI", "source": "x", "release_id": 10}
          for d in t1]
    ev += [{"date": d, "kind": "claims", "tier": 2, "label": "Jobless claims", "source": "x",
            "release_id": 180} for d in t2]
    return {"events": ev, "errors": [], "unsourced": list(mc.HISTORY_UNSOURCED),
            "start": "x", "end": "y", "available": True}


CAL = {"macro": [{"date": "2026-09-30", "kind": "pce", "tier": 1, "label": "Core PCE"},
                 {"date": "2026-09-30", "kind": "gdp", "tier": 2, "label": "GDP"},
                 {"date": "2026-09-30", "kind": "adp", "tier": 2, "label": "ADP payrolls"},
                 {"date": "2026-10-02", "kind": "jobs", "tier": 1, "label": "Jobs report (NFP)"}]}


def FRAMES():
    return {
        "SPY": _spy_frame(),
        "QUIET": _frame(),
        "DROPR": _frame({d: 49.5 for d in T1_DAYS[:3]}),
        "HOLEY": _frame(drop=[T1_DAYS[1]]),
        "ACCUM": _frame(bars={LAST: {"close": 51.0, "high": 51.2, "low": 50.0,
                                     "volume": 3_000_000.0}}),
        "THIN": _frame(volume=1000.0),
    }


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _rth(px, *, ref, at=NOW, age_sec=30, close=None):
    return {"open": ref, "high": max(ref, px), "low": min(ref, px),
            "close": close if close is not None else px, "volume": 1_000_000,
            "date": pd.Timestamp(at.date()),
            "last_trade_price": px, "last_trade_ts_ms": _ms(at) - age_sec * 1000,
            "prev_day_close": ref}


def _pre(px, *, ref, at=PRE, age_sec=30, av=None, t_at=None):
    t = t_at or (at - timedelta(minutes=1))
    return {"open": 0, "high": 0, "low": 0, "close": 0, "volume": 0,
            "last_trade_price": px, "last_trade_ts_ms": _ms(at) - age_sec * 1000,
            "prev_day_close": ref, "min_av": av, "min_t_ms": _ms(t) if av is not None else None}


SPY_REF = round(400.0 + 399 * 0.1, 4)                    # the SPY frame's last close
SNAPS = {"SPY": _rth(440.43, ref=SPY_REF), "QUIET": _rth(50.1, ref=50.0),
         "DROPR": _rth(49.5, ref=50.0), "ACCUM": _rth(51.3, ref=51.0),
         "THIN": _rth(50.0, ref=50.0)}


def _entry(frames=None, *, session=SESSION, events=None, cal=CAL):
    fr = frames if frames is not None else FRAMES()
    return R.build("full", session, universe_fn=lambda u: [s for s in fr if s != "SPY"],
                   frames_fn=lambda syms: {s: fr[s] for s in syms if s in fr},
                   events_fn=lambda a, b: (events if events is not None else _events()),
                   calendar_fn=lambda: cal)


@pytest.fixture
def _clean(monkeypatch):
    R._memo.clear(); R._warming.clear(); R._failed.clear()
    R._pm_memo.clear(); R._pm_warming.clear(); R._pm_failed.clear()
    spawned = []
    monkeypatch.setattr(R, "_spawn", lambda target, name: spawned.append((target, name)))
    yield spawned
    R._memo.clear(); R._warming.clear(); R._failed.clear()
    R._pm_memo.clear(); R._pm_warming.clear(); R._pm_failed.clear()


# --------------------------------------------------------------------------
# 1 — pure functions
# --------------------------------------------------------------------------
def test_pct_ret_and_held_boundary():
    assert R.pct_ret(99.5, 100) == -0.5
    assert R.held(-0.50) is True and R.held(-0.51) is False and R.held(0.0) is True
    assert R.held(None) is None and R.pct_ret(0, 100) is None and R.pct_ret(1, float("nan")) is None


def test_constants_are_imported_never_retyped():
    from sepa import breakout_audit, universe
    from supply_demand import momentum_burst as MB
    assert R.BENCH == universe.BENCHMARK and R.PM_RVOL_MIN == MB.BURST_RVOL_MIN
    assert R.PCT_DP == MB.PCT_DP and R.VOL_AVG_BARS == breakout_audit.VOL_AVG_BARS
    assert R.BETA_BARS == KL.YEAR_BARS
    assert (R.PM_OPEN_MIN, R.PM_CLOSE_MIN, R.PM_SLOTS) == (240, 570, 33)
    assert R.DEFAULT_SORT_KEY == B.DEFAULT_SORT
    src = (BACKEND / "chart_maps" / "resiliency_tab.py").read_text(encoding="utf-8")
    assert "BURST_RVOL_MIN" in src and not re.search(r"=\s*1\.5\b", src)
    assert "KL.anchor_read" in src and "KL.verify_last" in src
    assert "bulk_cached_frames" in src and "past_events" in src
    assert "UNMEASURED" in src


def test_intraday_coll_name_pinned_to_daytrading_owner():
    src = (BACKEND / "daytrading" / "data.py").read_text(encoding="utf-8")
    assert f'["{R.INTRADAY_COLL}"]' in src


def test_day_iso_normalizes_04_00_and_tz_aware():
    assert R.day_iso(pd.Timestamp("2026-09-29 04:00")) == "2026-09-29"
    assert R.day_iso(pd.Timestamp("2026-09-30 01:00", tz="UTC")) == "2026-09-29"


def test_closes_by_day_drops_nonfinite():
    df = _frame(n=5)
    df.iloc[1, df.columns.get_loc("close")] = float("nan")
    df.iloc[2, df.columns.get_loc("close")] = 0.0
    assert len(R.closes_by_day(df)) == 3
    assert R.closes_by_day(None) == {}


def test_event_sessions_good_friday_maps_to_monday_and_t2_excludes_t1():
    days = ["2026-04-01", "2026-04-02", "2026-04-06", "2026-04-07"]     # 04-03 Good Friday
    ev = [{"date": "2026-04-03", "kind": "jobs", "tier": 1, "label": "Jobs report (NFP)"},
          {"date": "2026-04-06", "kind": "claims", "tier": 2, "label": "Jobless claims"},
          {"date": "2026-04-07", "kind": "adp", "tier": 2, "label": "ADP payrolls"},
          {"date": "2026-04-07", "kind": "gdp", "tier": 2, "label": "GDP"},
          {"date": "2026-04-01", "kind": "ism", "tier": 3, "label": "ISM"}]
    s = R.event_sessions(ev, days, start=date(2026, 4, 1), end=date(2026, 4, 8))
    assert list(s["t1"]) == ["2026-04-06"]
    assert s["t1"]["2026-04-06"]["release_dates"] == ["2026-04-03"]
    assert list(s["t2"]) == ["2026-04-07"]                            # 04-06 is T1 only
    assert s["t2"]["2026-04-07"]["labels"] == ["ADP payrolls", "GDP"]
    both = R.event_sessions(ev, days, start=date(2026, 4, 1), end=date(2026, 4, 8),
                            t2_excludes_t1=False)
    assert "2026-04-06" in both["t2"]
    # NEGATIVE: end is exclusive (today's session never rates itself); tier 3 ignored
    s2 = R.event_sessions(ev, days, start=date(2026, 4, 1), end=date(2026, 4, 7))
    assert s2["t2"] == {} and "2026-04-01" not in s2["t1"]
    # NEGATIVE: an event after the last trading day maps nowhere
    assert R.event_sessions([{"date": "2026-05-01", "tier": 1, "kind": "cpi"}], days,
                            start=date(2026, 1, 1), end=date(2027, 1, 1)) == {"t1": {}, "t2": {}}


def test_event_returns_prev_is_the_prior_bench_day_no_bridging():
    days = ["2026-09-24", "2026-09-25", "2026-09-28"]
    closes = {"2026-09-24": 100.0, "2026-09-25": 99.5, "2026-09-28": 101.0}
    assert R.event_returns(closes, days, {"2026-09-25": {}, "2026-09-28": {}}) == \
        {"2026-09-25": -0.5, "2026-09-28": 1.51}
    # NEGATIVE: a hole on the prior day is None, never bridged to 09-24
    holey = {"2026-09-24": 100.0, "2026-09-28": 101.0}
    assert R.event_returns(holey, days, {"2026-09-28": {}}) == {"2026-09-28": None}
    assert R.event_returns(closes, days, {"2026-09-24": {}}) == {"2026-09-24": None}


def test_tier_stats_rates_down_subset_worst_last_median():
    ses = {d: {"labels": [f"L{i}"]} for i, d in enumerate(["a1", "a2", "a3", "a4"])}
    rets = {"a1": 0.1, "a2": -0.6, "a3": -0.5, "a4": None}
    bench = {"a1": -1.0, "a2": -0.2, "a3": 0.3, "a4": -0.1}
    st = R.tier_stats(rets, ses, bench, tier=1)
    assert (st["events"], st["n"], st["held"], st["rate_pct"], st["rated"]) == (4, 3, 2, 66.67, False)
    assert (st["down_events"], st["down_n"], st["down_held"], st["down_rate_pct"]) == (3, 2, 1, 50.0)
    assert st["median_ret_pct"] == -0.5
    assert st["worst"] == {"date": "a2", "labels": ["L1"], "ret_pct": -0.6, "spy_ret_pct": -0.2}
    assert st["last"] == {"date": "a4", "labels": ["L3"], "ret_pct": None, "held": None,
                          "spy_ret_pct": -0.1}
    assert R.tier_stats({}, {}, {}, tier=1) is None
    zero = R.tier_stats({}, {"a": {}}, {}, tier=2)
    assert zero["n"] == 0 and zero["rate_pct"] is None and zero["rated"] is False


def test_box_pass_at_exactly_75():
    assert R.box_pass({"rated": True, "n": 4, "held": 3}) is True
    assert R.box_pass({"rated": True, "n": 3, "held": 2}) is False
    assert R.box_pass({"rated": False, "n": 3, "held": 3}) is None
    assert R.box_pass(None) is None and R.box_pass({"rated": True, "n": 0, "held": 0}) is None


def test_sigma_and_beta():
    days = [f"d{i:03d}" for i in range(60)]
    c = {d: 100.0 * (1.01 if i % 2 else 1.0) for i, d in enumerate(days)}
    assert R.sigma_pct(c, days, bars=50) is not None and R.sigma_pct(c, days, bars=50) > 0.9
    b = {d: 200.0 * (1.005 if i % 2 else 1.0) for i, d in enumerate(days)}
    assert R.beta(c, b, days, bars=50) == pytest.approx(2.0, abs=0.02)
    # NEGATIVE: a hole, a flat benchmark, too few days
    h = dict(c); h.pop(days[-3])
    assert R.sigma_pct(h, days, bars=50) is None and R.beta(h, b, days, bars=50) is None
    assert R.beta(c, {d: 5.0 for d in days}, days, bars=50) is None
    assert R.sigma_pct(c, days[:10], bars=50) is None


def test_eod_read_accumulation_bar_is_bullish():
    e = R.eod_read({"close": 51.0, "high": 51.2, "low": 50.0, "volume": 3e6}, 50.0, 1e6,
                   date_iso=LAST, source="closed")
    assert e["state"] == "read" and e["bullish"] is True and e["up"] and e["upper_half"]
    assert e["rvol"] == 3.0 and e["close_loc_pct"] == 83.33 and e["chg_pct"] == 2.0


@pytest.mark.parametrize("bar,prev,avg,state,bullish", [
    ({"close": 51.0, "high": 51.2, "low": 50.0, "volume": float("nan")}, 50.0, 1e6, "no_volume", None),
    ({"close": 51.0, "high": 51.2, "low": 50.0, "volume": None}, 50.0, 1e6, "no_volume", None),
    ({"close": 51.0, "high": 51.0, "low": 51.0, "volume": 3e6}, 50.0, 1e6, "flat_bar", False),
    ({"close": 51.0, "high": 51.2, "low": 50.0, "volume": 3e6}, 50.0, None, "no_avg", None),
    ({"close": 51.0, "high": 51.2, "low": 50.0, "volume": 3e6}, None, 1e6, "no_bars", None),
    (None, 50.0, 1e6, "no_bars", None),
    ({"close": 49.0, "high": 51.2, "low": 48.9, "volume": 3e6}, 50.0, 1e6, "read", False),
    ({"close": 51.0, "high": 51.2, "low": 50.0, "volume": 1e6}, 50.0, 1e6, "read", False),
])
def test_NEG_eod_read_states(bar, prev, avg, state, bullish):
    e = R.eod_read(bar, prev, avg, date_iso=LAST, source="closed")
    assert e["state"] == state and e["bullish"] is bullish


def test_pm_slots_across_a_dst_boundary_and_zero_sessions():
    agg = [{"_id": {"s": "AAA", "d": "2026-10-30", "h": "08:0"}, "v": 100.0},   # EDT 04:00
           {"_id": {"s": "AAA", "d": "2026-11-02", "h": "09:0"}, "v": 200.0},   # EST 04:00
           {"_id": {"s": "AAA", "d": "2026-11-02", "h": "08:0"}, "v": 999.0},   # EST 03:00 — out
           {"_id": {"s": "AAA", "d": "2026-11-02", "h": "13:3"}, "v": 7.0},     # EST 08:30
           {"_id": {"s": "AAA", "d": "2026-11-04", "h": "09:0"}, "v": 5e9},     # the session itself
           {"_id": {"s": "ZZZ", "d": "2026-11-02", "h": "09:0"}, "v": 1.0}]     # no doc listed
    # fix round 2026-09-30: a day with no pre-market rows is a zero session only
    # when its first cached bar is before the 09:30 ET open (11-03: 04:00 EST)
    docs = [("AAA", "2026-10-30"), ("AAA", "2026-11-02"),
            ("AAA", "2026-11-03", "2026-11-03T09:00:00"), ("AAA", "2026-11-04")]
    out = R.pm_slots(agg, docs, session=date(2026, 11, 4),
                     dates=["2026-10-30", "2026-11-02", "2026-11-03", "2026-11-04"])
    assert set(out) == {"AAA"}
    a = out["AAA"]
    assert a["sessions"] == 3                                   # 11-03 = a zero session
    assert a["slot_mean"][0] == pytest.approx(100.0)            # (100 + 200 + 0) / 3
    assert a["slot_mean"][(8 * 60 + 30 - 240) // 10] == pytest.approx(7.0 / 3)
    assert len(a["slot_mean"]) == 33 and sum(a["slot_mean"]) == pytest.approx(307.0 / 3)


def test_NEG_pm_slots_skip_regular_session_only_days():
    """Critic 2026-09-30: BNY 2026-07-28 = 390 bars from 09:30 ET, no pre-market
    rows. Such a day is NOT a zero pre-market session — counting it shrank the
    usual volume and inflated pm_rvol. Only a day cached from before the open
    (or holding pre-market rows) counts."""
    agg = [{"_id": {"s": "BNY", "d": "2026-07-27", "h": "08:0"}, "v": 300.0},   # EDT 04:00
           {"_id": {"s": "BNY", "d": "2026-07-29", "h": "08:0"}, "v": 100.0}]
    dates = ["2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30", "2026-07-31"]
    docs = [("BNY", "2026-07-27", "2026-07-27T08:00:00"),
            ("BNY", "2026-07-28", "2026-07-28T13:30:00"),          # 09:30 EDT — regular only
            ("BNY", "2026-07-29", "2026-07-29T08:00:00"),
            ("BNY", "2026-07-30", "2026-07-30T13:31:00"),          # after the open
            ("BNY", "2026-07-31", None)]                           # no stamp — unknown
    b = R.pm_slots(agg, docs, session=date(2026, 8, 3), dates=dates)["BNY"]
    assert b["sessions"] == 2 and b["slot_mean"][0] == pytest.approx(200.0)
    # the pre-fix count (every doc a session) would have been 5 -> 80.0
    assert b["slot_mean"][0] != pytest.approx(400.0 / 5)
    # a real zero: cached from 04:00 ET with no pre-market volume -> counted
    z = R.pm_slots(agg, docs + [("BNY", "2026-07-24", "2026-07-24T08:00:00")],
                   session=date(2026, 8, 3), dates=dates + ["2026-07-24"])["BNY"]
    assert z["sessions"] == 3 and z["slot_mean"][0] == pytest.approx(400.0 / 3)
    # a 09:29 ET first bar is before the open; 09:30 exactly is not
    assert R._starts_before_open("2026-07-28", "2026-07-28T13:29:00") is True
    assert R._starts_before_open("2026-07-28", "2026-07-28T13:30:00") is False
    assert R._starts_before_open("2026-11-03", "2026-11-03T14:29:00") is True    # EST
    assert R._starts_before_open("2026-11-03", "2026-11-03T14:30:00") is False
    for junk in (None, "", "not a time", 12345):
        assert R._starts_before_open("2026-07-28", junk) is False
    # a regular-only name never reaches a baseline at all
    only_rth = R.pm_slots([], [("XYZ", d, f"{d}T13:30:00") for d in dates],
                          session=date(2026, 8, 3), dates=dates)
    assert only_rth == {}


def test_pm_baseline_at_linear_and_NEG_zero():
    s = [60.0] * 33
    assert R.pm_baseline_at(s, 245) == pytest.approx(30.0)
    assert R.pm_baseline_at(s, 250) == pytest.approx(60.0)
    assert R.pm_baseline_at(s, 255) == pytest.approx(90.0)
    assert R.pm_baseline_at(s, 9999) == pytest.approx(60.0 * 33)
    assert R.pm_baseline_at(s, 240) is None
    assert R.pm_baseline_at([0.0] * 33, 500) is None             # no division by zero downstream
    assert R.pm_baseline_at([1.0] * 5, 500) is None


def _pre_kw(**kw):
    base = {"ref_close": 100.0, "ref_date": LAST, "now": PRE, "session": SESSION,
            "phase": "pre", "baseline": {"sessions": 12, "slot_mean": [10.0] * 33},
            "baseline_state": "ready", "volume_verified": True}   # the math behind the gate
    base.update(kw)
    return base


def test_pre_read_bullish_at_exactly_1_5():
    p = R.pre_read(_pre(100.65, ref=100.0, av=438), **_pre_kw())
    assert p["state"] == "read" and p["as_of_et"] == "08:52"
    assert p["baseline_vol"] == 292.0 and p["pm_rvol"] == 1.5 and p["bullish"] is True
    assert p["move_pct"] == 0.65 and p["pm_volume"] == 438 and p["pm_dollar_vol"] == 44085.0
    q = R.pre_read(_pre(100.65, ref=100.0, av=436), **_pre_kw())
    assert q["pm_rvol"] == 1.49 and q["bullish"] is False and q["vol_ok"] is False
    down = R.pre_read(_pre(99.9, ref=100.0, av=900), **_pre_kw())
    assert down["vol_ok"] is True and down["up"] is False and down["bullish"] is False


def test_NEG_pre_read_unread_legs():
    assert R.pre_read(_pre(100.65, ref=100.0, av=438), **_pre_kw(phase="rth"))["state"] == "not_open"
    assert R.pre_read(_pre(100.65, ref=100.0, av=438), **_pre_kw(phase=None))["state"] == "not_open"
    # 04:01, the only trade is last evening's -> no fresh print
    at = datetime(2026, 9, 30, 4, 1, tzinfo=ET)
    old = _pre(100.65, ref=100.0, av=438, at=at, age_sec=9 * 3600)
    assert R.pre_read(old, **_pre_kw(now=at))["state"] == "no_print"
    assert R.pre_read(None, **_pre_kw())["state"] == "no_print"
    for av in (None, 0):
        r = R.pre_read(_pre(100.65, ref=100.0, av=av), **_pre_kw())
        assert r["state"] == "no_volume" and r["bullish"] is None
    yday = _pre(100.65, ref=100.0, av=438, t_at=PRE - timedelta(days=1))
    assert R.pre_read(yday, **_pre_kw())["state"] == "no_volume"
    four = R.pre_read(_pre(100.65, ref=100.0, av=438),
                      **_pre_kw(baseline={"sessions": 4, "slot_mean": [10.0] * 33}))
    assert four["state"] == "no_baseline" and four["bullish"] is None and "needs 5" in four["text"]
    zero = R.pre_read(_pre(100.65, ref=100.0, av=438),
                      **_pre_kw(baseline={"sessions": 9, "slot_mean": [0.0] * 33}))
    assert zero["state"] == "no_baseline" and zero["pm_rvol"] is None
    assert R.pre_read(_pre(100.65, ref=100.0, av=438),
                      **_pre_kw(baseline=None, baseline_state="warming"))["state"] == "baseline_warming"
    stale = R.pre_read(_pre(100.65, ref=97.0, av=438), **_pre_kw())
    assert stale["state"] == "stale" and stale["bullish"] is None


EV = {"tier": 1, "labels": ["Core PCE"]}


def test_today_read_holding_on_an_event_session():
    t = R.today_read(_rth(100.42, ref=100.0), ref_close=100.0, ref_date=LAST, now=NOW,
                     session=SESSION, phase="rth", event=EV)
    assert t["state"] == "read" and t["move_pct"] == 0.42 and t["holding"] is True
    assert t["basis"] == "live" and t["tape"] == "rth" and t["as_of_et"] == "10:59"
    d = R.today_read(_rth(98.8, ref=100.0), ref_close=100.0, ref_date=LAST, now=NOW,
                     session=SESSION, phase="rth", event=EV)
    assert d["holding"] is False and d["move_pct"] == -1.2


def test_NEG_today_read_never_says_holding_without_a_print():
    kw = dict(ref_close=100.0, ref_date=LAST, session=SESSION)
    assert R.today_read(_rth(100.4, ref=100.0), now=NOW, phase="rth", event=None, **kw)["state"] == "no_event"
    # pre phase, only yesterday's close in the row -> anchor basis last_close -> no_print
    row = {"prev_day_close": 100.0}
    t = R.today_read(row, now=PRE, phase="pre", event=EV, **kw)
    assert t["state"] == "no_print" and t["move_pct"] is None and t["holding"] is None
    assert R.today_read(None, now=NOW, phase="rth", event=EV, **kw)["state"] == "no_print"
    # stale cache: the snapshot's prior close disagrees with ours
    s = R.today_read(_rth(100.4, ref=96.0), now=NOW, phase="rth", event=EV, **kw)
    assert s["state"] == "stale" and s["holding"] is None
    assert R.today_read(_rth(100.4, ref=100.0), now=NOW, phase=None, event=EV, **kw)["state"] == "not_open"


def test_tile_filter_and_parse_filters():
    res = {"t1": {"rated": True, "n": 4, "held": 3}, "t2": {"rated": False, "n": 3, "held": 3},
           "eod": {"bullish": True}, "pre": {"bullish": None}}
    assert R.tile_filter(res) == {"t1": True, "t2": None, "eod": True, "pre": None}
    assert R.parse_filters("EOD, t1,foo") == ("t1", "eod")
    assert R.parse_filters("pre+t2") == ("t2", "pre")
    # NEGATIVE: junk / None / non-str -> ()
    for junk in (None, "", "  ", "foo,bar", 7, ["t1"]):
        assert R.parse_filters(junk) == ()
    assert R.tile_filter({"eod": {"bullish": "yes"}})["eod"] is None


def _row(sym, *, rate=None, rated=True, down=None, down_n=1, worst=None, t2rate=None,
         today=None):
    t1 = {"rated": rated, "rate_pct": rate, "down_rate_pct": down, "down_n": down_n,
          "worst": None if worst is None else {"ret_pct": worst}}
    t2 = {"rated": True, "rate_pct": t2rate, "down_rate_pct": None, "down_n": 0, "worst": None}
    return {"symbol": sym, "resiliency": {"t1": t1, "t2": t2, "today": today or {}}}


def test_order_key_all_four_sorts():
    rows = [_row("A", rate=80, down=50, worst=-2.0, t2rate=90),
            _row("B", rate=90, down=40, worst=-1.0, t2rate=70,
                 today={"state": "read", "move_pct": -0.3}),
            _row("C", rate=100, rated=False, down=100, worst=-0.1, t2rate=100,
                 today={"state": "read", "move_pct": 1.2}),
            _row("D", rate=80, down=60, worst=-3.0, t2rate=80,
                 today={"state": "no_print", "move_pct": None})]

    def order(s):
        return [r["symbol"] for r in sorted(rows, key=lambda r: R.order_key(r, s))]
    assert order("default") == ["B", "D", "A", "C"]                 # rated first, rate, down rate
    assert order("res_t2") == ["C", "A", "D", "B"]
    assert order("res_down") == ["D", "A", "B", "C"]                # C unrated goes last
    assert order("res_today") == ["C", "B", "A", "D"]               # reads first, A/D unread by symbol
    assert order("bogus") == order("default")


# --------------------------------------------------------------------------
# 2 — build + rank
# --------------------------------------------------------------------------
def test_build_rates_the_window_and_the_session_events():
    e = _entry()
    assert e["events_error"] is None
    ev = e["events_summary"]
    assert ev["t1_sessions"] == 8 and ev["t2_sessions"] == 3              # OLD_T1 out; dup T2 out
    assert ev["t1_spy_down"] == 4 and ev["t1_by_kind"]["cpi"] == 8
    assert ev["t2_by_kind"]["claims"] == 3 and ev["t2_by_kind"]["ism"] == 0
    assert e["session_events"] == {"t1": ["Core PCE"], "t2": ["GDP", "ADP payrolls"], "tier": 1}
    assert e["next_t1"] == {"date": "2026-10-02", "label": "Jobs report (NFP)"}
    q = e["reads"]["QUIET"]["t1"]
    assert (q["events"], q["n"], q["held"], q["rated"], q["rate_pct"]) == (8, 8, 8, True, 100.0)
    assert q["down_n"] == 4 and q["down_held"] == 4
    d = e["reads"]["DROPR"]["t1"]
    assert (d["held"], d["rate_pct"]) == (5, 62.5) and d["worst"]["ret_pct"] == -1.0
    h = e["reads"]["HOLEY"]["t1"]
    assert h["rated"] is False and h["n"] == 7
    a = e["reads"]["ACCUM"]["eod"]
    assert a["state"] == "read" and a["bullish"] is True and a["date"] == LAST
    assert e["reads"]["QUIET"]["eod"]["bullish"] is False
    assert e["reads"]["QUIET"]["ref_close"] == 50.0 and e["reads"]["QUIET"]["ref_date"] == LAST
    assert e["reads"]["QUIET"]["sigma_pct"] == 0.0 and e["reads"]["QUIET"]["beta"] == 0.0
    assert "SPY" not in e["syms"]


def test_rank_counts_filters_today_and_order():
    e = _entry()
    rows, counts, filters, today, su = R.rank(e, SNAPS, None, now=NOW, sort="default")
    assert su is None
    assert counts["scanned"] == 5 and counts["no_bars"] == 0
    assert counts["rated_t1"] + counts["partial_t1"] + counts["no_bars"] == counts["scanned"]
    assert counts["partial_t1"] == 1 and counts["t1_pass"] == 3            # QUIET ACCUM THIN
    assert counts["eod_pass"] == 1 and counts["pre_read"] == 0
    assert today["event_day"] is True and today["t1"] == ["Core PCE"] and today["tier"] == 1
    assert today["spy_move_pct"] == 0.12 and today["spy_tape"] == "rth"
    assert (today["read"], today["holding"], today["down"], today["no_print"]) == (4, 3, 1, 1)
    syms = [r["symbol"] for r in rows]
    assert syms[:3] == ["ACCUM", "QUIET", "THIN"] and syms[-1] == "HOLEY"
    q = next(r for r in rows if r["symbol"] == "QUIET")
    assert q["resiliency"]["today"]["holding"] is True and q["res_filter"]["t1"] is True
    assert filters["keys"] == list(R.FILTER_KEYS) and filters["active"] == []
    # ticked boxes
    rows2, _c, f2, _t, _s = R.rank(e, SNAPS, None, now=NOW, sort="default", active=("t1", "eod"))
    assert {r["symbol"] for r in rows2} == {"QUIET", "ACCUM", "THIN"}
    assert f2["passed_any"] == 3 and f2["passed_all"] == 1 and f2["mode"] == "any"
    rows3, _c, f3, _t, _s = R.rank(e, SNAPS, None, now=NOW, sort="default",
                                   active=("t1", "eod"), mode="all")
    assert [r["symbol"] for r in rows3] == ["ACCUM"] and f3["mode"] == "all"
    assert "must match all" in f3["line"]
    rows4, *_ = R.rank(e, SNAPS, None, now=NOW, sort="res_today")
    assert [r["symbol"] for r in rows4][:2] == ["ACCUM", "QUIET"]            # +0.59, +0.20


def test_NEG_rank_never_mutates_the_memo_and_never_reads_the_calendar(monkeypatch):
    e = _entry()
    before = copy.deepcopy(e)

    def boom(*a, **k):
        raise AssertionError("the calendar must never be read on a request")
    monkeypatch.setattr(mc, "get_macro_calendar", boom)
    monkeypatch.setattr(mc, "past_events", boom)
    rows, *_ = R.rank(e, SNAPS, None, now=NOW, sort="default", active=("t1",))
    rows[0]["resiliency"]["t1"]["held"] = -99
    rows[0]["resiliency"]["today"]["state"] = "mutated"
    R.rank(e, SNAPS, None, now=NOW, sort="res_today")
    assert e == before


def test_NEG_non_event_day_no_today_badge_and_res_today_unavailable():
    e = _entry(cal={"macro": [{"date": "2026-10-02", "kind": "jobs", "tier": 1,
                               "label": "Jobs report (NFP)"}]})
    rows, counts, filters, today, su = R.rank(e, SNAPS, None, now=NOW, sort="res_today")
    assert today == {"event_day": False, "session": "2026-09-30",
                     "next_t1": {"date": "2026-10-02", "label": "Jobs report (NFP)"}}
    assert su == R.TODAY_SORT_UNAVAILABLE
    assert all(r["resiliency"]["today"]["state"] == "no_event" for r in rows)
    for r in rows:
        assert not any(b["text"].startswith(R.TODAY_MARK) for b in R.tile_badges(r))
        assert not any(s["k"] == "Today" for s in R.tile_stats(r))
    assert R.today_line(today) == ("\U0001F4C5 2026-09-30 has no T1 or T2 print. "
                                   "Next T1: Jobs report (NFP) 2026-10-02.")


def test_NEG_fred_all_fail_rates_nobody_and_says_so():
    bad = {"events": [], "errors": [{"release_id": i, "reason": "HTTP 503"}
                                    for i in mc.HISTORY_RELEASE_IDS],
           "unsourced": [], "available": False}
    e = _entry(events=bad)
    assert e["events_error"] == "HTTP 503"
    assert all(rd["t1"] is None and rd["t2"] is None for rd in e["reads"].values())
    rows, counts, filters, today, su = R.rank(e, SNAPS, None, now=NOW, sort="default",
                                              active=("t1", "t2"))
    assert rows == [] and counts["t1_pass"] == 0 and counts["rated_t1"] == 0
    assert filters["items"][0]["no_read"] == 5
    h = R.header_text(counts, entry=e, ph="rth", pm_state=None)
    assert "could not be read (HTTP 503)" in h and "no name is rated" in h
    assert R.events_line(e).count("HTTP 503") == len(mc.HISTORY_RELEASE_IDS)
    # the tape reads still show
    rows2, c2, *_ = R.rank(e, SNAPS, None, now=NOW, sort="default", active=("eod",))
    assert [r["symbol"] for r in rows2] == ["ACCUM"]


def test_NEG_a_raising_events_fn_is_an_error_class_not_a_crash():
    fr = FRAMES()

    def boom(a, b):
        raise ConnectionError("https://api.stlouisfed.org/fred/x?api_key=SECRET")
    e = R.build("full", SESSION, universe_fn=lambda u: ["QUIET"],
                frames_fn=lambda syms: {s: fr[s] for s in syms if s in fr},
                events_fn=boom, calendar_fn=lambda: CAL)
    assert e["events_error"] == "ConnectionError" and "SECRET" not in json.dumps(e, default=str)


def test_NEG_calendar_failure_leaves_no_event_and_never_raises():
    fr = FRAMES()

    def boom():
        raise TimeoutError("slow")
    e = R.build("full", SESSION, universe_fn=lambda u: ["QUIET"],
                frames_fn=lambda syms: {s: fr[s] for s in syms if s in fr},
                events_fn=lambda a, b: _events(), calendar_fn=boom)
    assert e["session_events"]["tier"] is None and e["next_t1"] is None


def test_NEG_partial_history_is_hidden_when_ticked_and_counted():
    e = _entry()
    rows, counts, filters, *_ = R.rank(e, SNAPS, None, now=NOW, sort="default", active=("t1",))
    assert "HOLEY" not in {r["symbol"] for r in rows}
    it = filters["items"][0]
    assert it["key"] == "t1" and it["no_read"] == 1 and it["hidden"] == 2   # HOLEY + DROPR


def test_NEG_unknown_res_tokens_and_junk_mode():
    e = _entry()
    rows, _c, f, *_ = R.rank(e, SNAPS, None, now=NOW, sort="default",
                             active=R.parse_filters("foo,bar"), mode="junk")
    assert f["active"] == [] and f["mode"] == "any" and len(rows) == 5


def test_NEG_stale_cache_today_and_pre_are_stale_never_holding():
    snaps = dict(SNAPS)
    snaps["QUIET"] = _rth(50.1, ref=48.0)                        # the snapshot disagrees
    rows, counts, *_ = R.rank(_entry(), snaps, None, now=NOW, sort="default")
    q = next(r for r in rows if r["symbol"] == "QUIET")
    assert q["resiliency"]["today"]["state"] == "stale"
    assert q["resiliency"]["today"]["holding"] is None and counts["stale"] == 1
    pre_snaps = {"QUIET": _pre(50.3, ref=48.0, av=500)}
    rows2, *_ = R.rank(_entry(), pre_snaps, {"state": "ready", "by_sym": {}}, now=PRE,
                       sort="default")
    assert next(r for r in rows2 if r["symbol"] == "QUIET")["resiliency"]["pre"]["state"] == "stale"


def test_NEG_bars_behind_are_stale_even_when_the_snapshot_verifies():
    fr = FRAMES()
    fr["LAGGY"] = _frame(end="2026-09-25")
    e = _entry(fr)
    assert e["reads"]["LAGGY"]["eod"]["state"] == "stale"
    snaps = dict(SNAPS, LAGGY=_rth(50.1, ref=50.0))
    rows, counts, *_ = R.rank(e, snaps, None, now=NOW, sort="default")
    lag = next(r for r in rows if r["symbol"] == "LAGGY")
    assert lag["resiliency"]["today"]["state"] == "stale" and lag["res_filter"]["eod"] is None


def test_NEG_pre_volume_leg_off_until_his_call():
    """Critic 2026-09-30: min.av read +11-13% above the 1-minute bars the
    baseline is built from (the spec's 2% STOP check failed). Until Ajay
    decides, the volume leg is not compared: no rvol, bullish None, the box
    passes none — even where the ratio would clear 1.5x by a mile."""
    assert R.PM_VOLUME_VERIFIED is False
    kw = {k: v for k, v in _pre_kw().items() if k != "volume_verified"}
    p = R.pre_read(_pre(100.65, ref=100.0, av=5000), **kw)
    assert p["state"] == "volume_unverified" and p["bullish"] is None
    assert p["pm_rvol"] is None and p["vol_ok"] is None and p["baseline_vol"] is None
    assert p["move_pct"] == 0.65 and p["pm_volume"] == 5000
    assert R.PRE_UNVERIFIED_TEXT in p["text"] and "your call" in p["text"]
    assert R.pre_read(_pre(100.65, ref=100.0, av=5000), **dict(kw, volume_verified=False))[
        "state"] == "volume_unverified"
    # unread legs keep their own state (no print / no volume are not "unverified")
    assert R.pre_read(None, **kw)["state"] == "no_print"
    assert R.pre_read(_pre(100.65, ref=100.0, av=None), **kw)["state"] == "no_volume"
    # through rank: the box passes none, the header and the box note say why
    base = {"sessions": 12, "slot_mean": [10.0] * 33}
    snaps = {"QUIET": _pre(50.3, ref=50.0, av=9000), "ACCUM": _pre(51.2, ref=51.0, av=9000)}
    pm = {"state": "ready", "by_sym": {"QUIET": base, "ACCUM": base}}
    rows, counts, filters, *_ = R.rank(_entry(), snaps, pm, now=PRE, sort="default",
                                       active=("pre",))
    assert rows == [] and counts["pre_pass"] == 0 and counts["pre_read"] == 0
    head = R.header_text(counts, entry=_entry(), ph="pre", pm_state="ready")
    assert "not compared yet" in head and "passes none until you decide" in head
    assert R.PRE_OFF_REASON in R.box_notes()["pre"]          # follow-up 2026-09-30 wording
    assert "box is OFF" in R.rules_block()["lines"][-1]


def test_NEG_board_skips_the_baseline_while_the_volume_leg_is_off(res_board, monkeypatch):
    res_board["seed"]()
    calls = []
    monkeypatch.setattr(R, "pm_cached_or_warm",
                        lambda syms, session, **k: calls.append(session) or
                        {"state": "ready", "by_sym": {}})
    B.resiliency_tiles(24, 130, "full", False, "default", now=PRE)
    assert calls == []                               # no aggregation on intraday_cache
    monkeypatch.setattr(R, "PM_VOLUME_VERIFIED", True)
    B.resiliency_tiles(24, 130, "full", False, "default", now=PRE)
    assert len(calls) == 1
    B.resiliency_tiles(24, 130, "full", False, "default", now=NOW)   # rth: never
    assert len(calls) == 1


def test_pre_market_rank_reads_the_baseline(monkeypatch):
    monkeypatch.setattr(R, "PM_VOLUME_VERIFIED", True)   # the math behind the gate
    base = {"sessions": 12, "slot_mean": [10.0] * 33}
    snaps = {"QUIET": _pre(50.3, ref=50.0, av=900), "ACCUM": _pre(51.2, ref=51.0, av=300),
             "DROPR": _pre(49.9, ref=50.0, av=900), "THIN": _pre(50.2, ref=50.0, av=900)}
    pm = {"state": "ready", "by_sym": {"QUIET": base, "ACCUM": base, "DROPR": base,
                                       "THIN": {"sessions": 4, "slot_mean": [10.0] * 33}}}
    rows, counts, *_ = R.rank(_entry(), snaps, pm, now=PRE, sort="default", active=("pre",))
    assert [r["symbol"] for r in rows] == ["QUIET"]
    assert counts["pre_read"] == 3 and counts["pre_pass"] == 1 and counts["pre_no_baseline"] == 1
    # NEGATIVE: a warming baseline reads nobody as bullish
    rows_w, cw, *_ = R.rank(_entry(), snaps, {"state": "warming", "by_sym": {}}, now=PRE,
                            sort="default", active=("pre",))
    assert rows_w == [] and cw["pre_pass"] == 0
    assert "loading" in R.header_text(cw, entry=_entry(), ph="pre", pm_state="warming")


def test_close_phase_eod_reads_the_session_bar():
    at = datetime(2026, 9, 30, 16, 30, tzinfo=ET)
    snaps = {"QUIET": dict(_rth(50.6, ref=50.0, at=at), open=50.0, high=50.7, low=49.9,
                           close=50.6, volume=2_500_000),
             "DROPR": dict(_rth(50.6, ref=50.0, at=at), open=50.0, high=50.7, low=49.9,
                           close=50.6, volume=0)}
    rows, counts, *_ = R.rank(_entry(), snaps, None, now=at, sort="default")
    q = next(r for r in rows if r["symbol"] == "QUIET")["resiliency"]["eod"]
    assert q["source"] == "session" and q["date"] == "2026-09-30" and q["bullish"] is True
    assert counts["eod_session"] == 1
    d = next(r for r in rows if r["symbol"] == "DROPR")["resiliency"]["eod"]
    assert d["source"] == "closed" and d["date"] == LAST            # zero volume -> the closed read


def test_NEG_closed_saturday_and_holiday():
    sat = datetime(2026, 10, 3, 10, 0, tzinfo=ET)
    fr = {s: (_spy_frame(end="2026-10-02") if s == "SPY" else _frame(end="2026-10-02"))
          for s in ("SPY", "QUIET")}
    sess = R.session_for(sat)
    assert sess == date(2026, 10, 5)
    e = _entry(fr, session=sess, cal={"macro": []})
    snaps = {"QUIET": _rth(50.0, ref=50.0, at=datetime(2026, 10, 2, 19, 0, tzinfo=ET))}
    rows, counts, *_ = R.rank(e, snaps, None, now=sat, sort="default")
    q = rows[0]["resiliency"]
    assert q["pre"]["state"] == "not_open" and q["eod"]["date"] == "2026-10-02"
    blk = R.ready_block(counts, entry=e, now=sat, sort="default", filters={}, today={})
    assert blk["phase"] is None and blk["market_closed"] == "weekend"
    hol = datetime(2026, 11, 26, 9, 0, tzinfo=ET)
    wb = R.warming_block(now=hol)
    assert wb["phase"] is None and wb["market_closed"] == "holiday 2026-11-26"


def test_NEG_nan_inf_in_frames_serialize_clean():
    fr = FRAMES()
    q = fr["QUIET"]
    q.iloc[-5, q.columns.get_loc("close")] = float("nan")
    q.iloc[-6, q.columns.get_loc("volume")] = float("inf")
    q.iloc[-1, q.columns.get_loc("volume")] = float("nan")
    e = _entry(fr)
    rows, counts, filters, today, su = R.rank(e, SNAPS, None, now=NOW, sort="default")
    blk = R.ready_block(counts, entry=e, now=NOW, sort="default", filters=filters, today=today)
    payload = {"rows": rows, "block": blk,
               "tiles": [{"badges": R.tile_badges(r), "stats": R.tile_stats(r, event_day=True),
                          "why": R.why_text(r)} for r in rows]}
    json.dumps(payload, allow_nan=False)
    _no_numpy(payload)
    assert next(r for r in rows if r["symbol"] == "QUIET")["resiliency"]["eod"]["state"] == "no_volume"


def _no_numpy(x):
    if isinstance(x, dict):
        for v in x.values():
            _no_numpy(v)
    elif isinstance(x, list):
        for v in x:
            _no_numpy(v)
    else:
        assert type(x) in (int, float, str, bool, type(None)), (type(x), x)
        if isinstance(x, float):
            assert math.isfinite(x)


# --------------------------------------------------------------------------
# 3 — words
# --------------------------------------------------------------------------
def test_tile_words_badges_stats_why():
    e = _entry()
    rows, *_ = R.rank(e, SNAPS, None, now=NOW, sort="default", active=("t1",))
    q = next(r for r in rows if r["symbol"] == "QUIET")
    b = R.tile_badges(q, ("t1",), event_day=True)
    assert b[0] == {"text": "\U0001F6E1️ T1 held 8/8 (100%)", "tone": "good"}
    assert b[1] == {"text": "\U0001F4C5 T1 today · holding +0.20%", "tone": "good"}
    assert b[2] == {"text": "\U0001F6E1️ Held on T1", "tone": "good", "res_filter": "t1"}
    ks = [s["k"] for s in R.tile_stats(q, event_day=True)]
    assert ks == ["T1 held", "T2 held", "EOD tape", "Pre-market", "Today", "T1 worst",
                  "Last T1", "σ · β"]
    assert R.why_text(q).startswith("Held 8 of 8 T1 days (100%), 4 of 4 when SPY fell")
    rows_all, *_ = R.rank(e, SNAPS, None, now=NOW, sort="default")
    d = next(r for r in rows_all if r["symbol"] == "DROPR")
    bd = R.tile_badges(d, (), event_day=True)
    assert bd[0]["tone"] == "muted" and bd[1] == {"text": "\U0001F4C5 T1 today · down -1.00%",
                                                  "tone": "warn"}


def test_served_words_are_built_from_the_constants():
    rb = R.rules_block()
    assert rb["hold_max_drop_pct"] == R.HOLD_MAX_DROP_PCT and rb["benchmark"] == "SPY"
    assert any(f"{R.HOLD_RATE_MIN_PCT:g}%" in ln for ln in rb["lines"])
    assert "UNMEASURED" in R.NOTE     # the 1.5× bar is named only while the leg is on
    assert R.study_block()["status"] in ("pending", "measured")
    notes = R.box_notes()
    assert set(notes) == set(R.FILTER_KEYS) and "UNMEASURED" in notes["pre"]


def test_study_block_measured_replaces_the_first_note_sentence():
    # the T1 verdict reads the EVENT-SPECIFIC contrast (fix round 2026-09-30): the
    # bracket printed is specific_ci, never the stratified lift's ci
    m = {"status": "measured", "run_date": "2026-10-01",
         "t1": {"verdict": "no_signal", "lift_pp": 5.8, "ci": [4.3, 7.8], "n_events": 52,
                "placebo_lift_pp": 5.8, "placebo_ci": [4.2, 7.5], "specific_pp": -0.1,
                "specific_ci": [-2.5, 2.6], "specific": "general"},
         "t2": {"verdict": "too_small"}, "eod": {"verdict": "no_signal", "lift_pp": 0.05,
                                                 "ci": [-0.1, 0.2]},
         "pre": {"verdict": "unmeasured", "reason": "too short"}}
    s = R.study_block(m)
    assert s["status"] == "measured" and s["t1"]["verdict"] == "no_signal"
    assert s["t1"]["text"].startswith("MEASURED 2026-10-01: names that held on at least 75%")
    assert "beyond ordinary days is -0.1pp [-2.5, +2.6], 52 data days" in s["t1"]["text"]
    assert "NO_SIGNAL" in s["t1"]["text"] and "+5.8pp more often on the next ordinary day" in s["t1"]["text"]
    # NEGATIVE: the stratified bracket never reads as the verdict's CI, and the
    # words never claim the strata matched volatility
    assert "[+4.3, +7.8]" not in s["t1"]["text"]
    assert "same-volatility" not in s["t1"]["text"] and "same volatility" not in s["t1"]["text"]
    # NEGATIVE: a literal without the event-specific fields prints the verdict word only
    bare = R.study_block({"status": "measured", "run_date": "2026-10-01",
                          "t1": {"verdict": "separates", "lift_pp": 5.8, "ci": [4.3, 7.8]}})
    assert bare["t1"]["text"] == "MEASURED 2026-10-01: SEPARATES."
    assert s["pre"]["text"] == "UNMEASURED — too short"
    assert R.note_text(s).startswith(R.MARK + " MEASURED 2026-10-01")
    # NEGATIVE: a junk verdict never reaches the page
    assert R.study_block({"status": "measured", "t1": {"verdict": "wow"}})["t1"]["verdict"] == "unmeasured"
    assert R.study_block({"status": "pending"})["t1"]["verdict"] == "unmeasured"


def test_NEG_measured_module_absent_falls_back(monkeypatch):
    import builtins
    real = builtins.__import__

    def fake(name, *a, **k):
        if name.endswith("resiliency_measured") or (a and a[2] and "resiliency_measured" in a[2]):
            raise ImportError("absent")
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", fake)
    assert R._measured() == R.MEASURED_DEFAULT


def test_NEG_guard_no_bounce_fake_or_forecast_words():
    """Every string literal in the module (served words + docstrings); the
    `quick_bounce` import is an identifier, not a word he reads."""
    import ast
    tree = ast.parse((BACKEND / "chart_maps" / "resiliency_tab.py").read_text(encoding="utf-8"))
    words = " ".join(n.value for n in ast.walk(tree)
                     if isinstance(n, ast.Constant) and isinstance(n.value, str)).lower()
    assert "unmeasured" in words
    for w in ("bounce", "fake", "won't drop", "won’t drop", "market-resilient"):
        assert w not in words, w


def test_NEG_guard_trading_and_push_never_import_the_tab():
    for sub in ("trading", "push"):
        for p in (BACKEND / sub).rglob("*.py"):
            assert "resiliency_tab" not in p.read_text(errors="ignore"), p


def test_NEG_guard_enterable_has_no_resiliency_kind():
    from supply_demand import enterable as EN
    assert "resiliency" not in EN.KIND_BY_TAB


def test_NEG_guard_the_tab_never_imports_board():
    src = (BACKEND / "chart_maps" / "resiliency_tab.py").read_text(encoding="utf-8")
    assert "import board" not in src and "chart_maps.board" not in src


# --------------------------------------------------------------------------
# 4 — memo
# --------------------------------------------------------------------------
def test_memo_warming_then_ready(monkeypatch, _clean):
    built = _entry()
    monkeypatch.setattr(R, "build", lambda u, s, **k: built)
    got = R.cached_or_warm("full", now=NOW)
    assert got["state"] == "warming" and len(_clean) == 1
    _clean[0][0]()                                          # run the spawned build
    got2 = R.cached_or_warm("full", now=NOW)
    assert got2["state"] == "ready" and got2["entry"]["session"] == "2026-09-30"


def test_NEG_a_raising_build_is_error_then_retried_after_back_off(monkeypatch, _clean):
    calls = []

    def boom(u, s, **k):
        calls.append(1)
        raise RuntimeError("the price-cache read returned no frames")
    monkeypatch.setattr(R, "build", boom)
    monkeypatch.setattr(R, "_spawn", lambda target, name: target())
    assert R.cached_or_warm("full", now=NOW)["state"] == "warming"
    got = R.cached_or_warm("full", now=NOW)
    assert got["state"] == "error" and "no frames" in got["reason"] and len(calls) == 1
    assert R.cached_or_warm("full", now=NOW)["state"] == "error" and len(calls) == 1
    t0 = R.time.time()
    monkeypatch.setattr(R.time, "time", lambda: t0 + R.FAIL_RETRY_SEC + 1)
    R.cached_or_warm("full", now=NOW)
    assert len(calls) == 2


def test_NEG_error_reason_never_carries_a_key():
    assert R._safe_reason(RuntimeError("GET https://x?api_key=SECRET failed")) == "RuntimeError"
    assert R._safe_reason(RuntimeError("boom")) == "boom"


def test_NEG_build_raises_on_an_empty_frame_read():
    with pytest.raises(RuntimeError):
        R.build("full", SESSION, universe_fn=lambda u: ["AAA"], frames_fn=lambda s: {},
                events_fn=lambda a, b: _events(), calendar_fn=lambda: CAL)


class _Coll:
    def __init__(self, agg, docs):
        self.agg, self.docs, self.pipes = agg, docs, []

    def aggregate(self, pipe, **k):
        self.pipes.append(pipe)
        return iter(self.agg)

    def find(self, q, proj):
        self.proj = proj
        return iter(self.docs)


def test_pm_cached_or_warm_sync_and_the_pipeline(_clean):
    dates = R.pm_dates(SESSION)
    assert len(dates) == R.VOL_AVG_BARS and dates[-1] == LAST and SESSION.isoformat() not in dates
    c = _Coll([{"_id": {"s": "AAA", "d": LAST, "h": "12:0"}, "v": 50.0}],
              [{"symbol": "AAA", "date": LAST}])
    got = R.pm_cached_or_warm(["AAA"], SESSION, sync=True, coll=c)
    assert got["state"] == "ready" and got["by_sym"]["AAA"]["sessions"] == 1
    assert c.pipes[0][0] == {"$match": {"symbol": {"$in": ["AAA"]}, "date": {"$in": dates}}}
    assert c.pipes[0][-1]["$group"]["_id"]["h"] == {"$substrBytes": ["$pm.ts_utc", 11, 4]}
    # the doc list carries each day's first bar stamp (regular-only days are skipped)
    assert c.proj["first"] == {"$min": "$bars.ts_utc"}
    c2 = _Coll([], [{"symbol": "AAA", "date": LAST, "first": f"{LAST}T13:30:00"}])
    R._pm_memo.clear()
    assert R.pm_build(["AAA"], SESSION, coll=c2) == {}
    src = (BACKEND / "chart_maps" / "resiliency_tab.py").read_text(encoding="utf-8")
    body = src[src.index("def pm_build("):src.index("def pm_cached_or_warm(")]
    for w in ("insert", "update", "delete", "create_index", "replace", "_get_mongo_coll"):
        assert w not in body, w


def test_NEG_pm_unavailable_is_error_not_a_crash(monkeypatch, _clean):
    monkeypatch.setattr(R, "_pm_coll", lambda: None)
    assert R.pm_cached_or_warm(["AAA"], SESSION, sync=True)["state"] == "error"


# --------------------------------------------------------------------------
# 5 — board + api
# --------------------------------------------------------------------------
class _Fixed(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)


@pytest.fixture
def res_board(monkeypatch, _clean):
    from sepa import scanner
    state = {"frames": FRAMES(), "snaps": dict(SNAPS), "snap_calls": [], "finish_tiles": [],
             "events": None, "cal": CAL}

    def _snaps(syms):
        state["snap_calls"].append(sorted(syms))
        return {s: state["snaps"][s] for s in syms if s in state["snaps"]}

    def _bars(tiles, days, **k):
        for t in tiles:
            t["bars"] = [{"t": LAST, "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}]

    real_finish = B._finish

    def _finish_spy(tiles, *a, **k):
        state["finish_tiles"].append([dict(t) for t in tiles])
        return real_finish(tiles, *a, **k)

    real_build = R.build

    def fake_build(universe, session, **k):
        fr = state["frames"]
        return real_build(universe, session,
                          universe_fn=lambda u: [s for s in fr if s != "SPY"],
                          frames_fn=lambda syms: {s: fr[s] for s in syms if s in fr},
                          events_fn=lambda a, b: state["events"] or _events(),
                          calendar_fn=lambda: state["cal"])

    monkeypatch.setattr(R, "build", fake_build)
    monkeypatch.setattr(B, "datetime", _Fixed)
    monkeypatch.setattr(B, "_bulk_snaps", _snaps)
    monkeypatch.setattr(B, "_finish", _finish_spy)
    monkeypatch.setattr(scanner, "load_latest", lambda *a, **k: {"all_results": []})
    monkeypatch.setattr(B, "_attach_bars", _bars)
    monkeypatch.setattr(B, "attach_explosive", lambda tiles: 0)
    monkeypatch.setattr(B, "attach_velocity", lambda tiles, **k: 0)
    monkeypatch.setattr(B, "_velocity_decor", lambda tiles: None)
    monkeypatch.setattr(B, "_name_for", lambda s: f"{s} Inc")
    monkeypatch.setattr(B, "attach_live_now", lambda tiles, out=None, **k: {})
    monkeypatch.setattr(B, "attach_enterable", lambda tiles, kind="demand", **k: 0)
    monkeypatch.setattr(B, "attach_band_structure", lambda tiles, kind="demand", **k: 0)
    monkeypatch.setattr(B, "band_structure_coverage", lambda tiles, kind="demand": {})
    monkeypatch.setattr(B, "attach_burst", lambda tiles, out=None, **k: {})
    monkeypatch.setattr(B, "_burst_frames", lambda syms: {})
    monkeypatch.setattr(B, "attach_key_levels", lambda tiles, out=None, **k: None)

    def seed():
        R._memo.clear()
        R.cached_or_warm("full", now=NOW, sync=True)
    state["seed"] = seed
    return state


BOARD_KEYS = {"state", "session", "phase", "market_closed", "sort", "header", "today_line",
              "events_line", "rules", "events", "today", "counts", "filters", "study", "note",
              "measured", "built_at"}
COUNT_KEYS_SPEC = {"scanned", "no_bars", "stale", "rated_t1", "partial_t1", "t1_pass",
                   "rated_t2", "partial_t2", "t2_pass", "eod_read", "eod_pass", "pre_read",
                   "pre_pass", "no_turnover", "dropped_thin", "shown"}


def test_board_payload_shape_and_sorts(res_board):
    res_board["seed"]()
    a = B.board(tab="resiliency", limit=24)
    assert a["tab"] == "resiliency" and a["sort"] == "default"
    assert a["sorts"] == R.served_sorts()
    assert [s["key"] for s in a["sorts"]] == ["default", "res_t2", "res_down", "res_today"]
    assert [t["symbol"] for t in a["tiles"]] == ["ACCUM", "QUIET", "DROPR", "HOLEY"]  # THIN floored
    rb = a["resiliency_board"]
    assert set(rb) == BOARD_KEYS and rb["state"] == "ready"
    assert COUNT_KEYS_SPEC <= set(rb["counts"])
    assert rb["counts"]["dropped_thin"] == 1 and rb["counts"]["shown"] == 4
    assert rb["today"]["event_day"] is True and rb["today_line"].startswith(
        "\U0001F4C5 2026-09-30 is a T1 data day — Core PCE (T1); GDP + ADP payrolls (T2).")
    assert rb["events"]["t1_sessions"] == 8 and rb["events"]["sources"] == list(R.EVENT_SOURCES)
    assert rb["filters"]["mode_param"] == "res_mode" and rb["filters"]["keys"] == list(R.FILTER_KEYS)
    assert rb["measured"] is False and rb["note"] == a["note"]
    t = a["tiles"][1]
    assert t["symbol"] == "QUIET" and set(t["resiliency"]) == {
        "t1", "t2", "today", "eod", "pre", "sigma_pct", "beta", "adv50"}
    assert set(t["res_filter"]) == set(R.FILTER_KEYS) and "enterable" not in t
    assert t["badges"][0]["text"].startswith("\U0001F6E1️ T1 held")
    assert len(res_board["snap_calls"]) == 1 and "SPY" in res_board["snap_calls"][0]
    json.dumps(a, allow_nan=False)
    b = B.board(tab="resiliency", sort="res_t2", limit=24)
    assert b["sort"] == "res_t2" and b["resiliency_board"]["sort"] == "res_t2"


def test_probe_fixture_is_flat_and_carries_forced_warming_and_error(res_board, tmp_path):
    """Critic 2026-09-30: the probe wrote {_about, captured_at, variants, args},
    and the FE payload test reads TOP-LEVEL `tab == "resiliency"` values — the
    real capture found no payloads. Now every payload is top level, the capture
    keys start with "_", and the real handler also serves a forced warming and
    a forced error payload (a ready capture has neither). The memo is restored."""
    from scripts import resiliency_tab_cost_probe as P
    res_board["seed"]()
    memo_before = dict(R._memo)
    build_before = R.build
    out = tmp_path / "fixture.json"
    P.dump_fixture(str(out), NOW)
    doc = json.loads(out.read_text(encoding="utf-8"))
    payloads = {k: v for k, v in doc.items()
                if isinstance(v, dict) and v.get("tab") == "resiliency"}
    assert set(payloads) == {name for name, _kw in P.VARIANTS} | set(P.FORCED)
    assert all(k.startswith("_") for k in set(doc) - set(payloads))
    assert "variants" not in doc and "args" not in doc
    state = {k: v["resiliency_board"]["state"] for k, v in payloads.items()}
    assert state.pop("warming_forced") == "warming" and state.pop("error_forced") == "error"
    assert set(state.values()) == {"ready"}
    assert payloads["warming_forced"]["tiles"] == [] and payloads["warming_forced"]["warming"]
    assert payloads["error_forced"]["tiles"] == []
    # NEGATIVE: the forcing never leaks out of the probe
    assert R._memo == memo_before and R.build is build_before and not R._failed
    assert R.cached_or_warm("full", now=NOW)["state"] == "ready"


def test_board_res_filters_any_and_all(res_board):
    res_board["seed"]()
    a = B.board(tab="resiliency", res="t1,eod", limit=24)
    assert {t["symbol"] for t in a["tiles"]} == {"QUIET", "ACCUM"}
    acc = next(t for t in a["tiles"] if t["symbol"] == "ACCUM")
    assert [b["res_filter"] for b in acc["badges"] if "res_filter" in b] == ["t1", "eod"]
    b = B.board(tab="resiliency", res="t1,eod", res_mode="all", limit=24)
    assert [t["symbol"] for t in b["tiles"]] == ["ACCUM"]
    assert b["resiliency_board"]["filters"]["mode"] == "all"
    c = B.board(tab="resiliency", res="pre", limit=24)
    assert c["tiles"] == [] and c["note"] == R.filter_empty_note(("pre",))


def test_NEG_tab_scoped_sorts_and_other_tabs_ignore_res(res_board, monkeypatch):
    res_board["seed"]()
    bogus = B.board(tab="resiliency", sort="volume", limit=24)
    assert bogus["sort"] == "default"
    seen = []
    monkeypatch.setattr(B, "ath_tiles", lambda *a, **k: seen.append(a[4]) or {"tiles": []})
    out = B.board(tab="ath", sort="res_t2", res="t1")
    assert seen == ["default"] and "resiliency_board" not in out
    src = (BACKEND / "chart_maps" / "board.py").read_text(encoding="utf-8")
    assert '(t == "resiliency" and sort in _RES.TAB_SORTS)' in src
    assert 'elif t == "resiliency":' in src


def test_NEG_board_never_reads_the_calendar_on_a_request(res_board, monkeypatch):
    res_board["seed"]()

    def boom(*a, **k):
        raise AssertionError("request path read the calendar")
    monkeypatch.setattr(mc, "get_macro_calendar", boom)
    monkeypatch.setattr(mc, "past_events", boom)
    out = B.board(tab="resiliency", limit=24)
    assert out["resiliency_board"]["state"] == "ready"


def test_board_warming_and_error(monkeypatch, _clean):
    built = _entry()
    monkeypatch.setattr(R, "build", lambda u, s, **k: built)
    out = B.resiliency_tiles(24, 130, "full", now=NOW, sort="res_t2")
    assert out["tiles"] == [] and out["warming"] is True and out["note"] == R.WARMING_NOTE
    wb = out["resiliency_board"]
    assert wb["state"] == "warming" and wb["counts"] is None and set(wb) == BOARD_KEYS
    R._memo.clear(); R._warming.clear()
    R._failed[("2026-09-30", "full")] = {"ts": R.time.time(), "reason": "boom"}
    err = B.resiliency_tiles(24, 130, "full", now=NOW)
    assert err["resiliency_board"]["state"] == "error"
    assert err["note"] == R.error_note("boom") and "retried every 5 minutes" in err["note"]


def test_pool_is_cut_before_finish(res_board, monkeypatch):
    res_board["seed"]()
    monkeypatch.setattr(B, "LIMIT_MAX", 1)
    monkeypatch.setattr(B, "TAPE_POOL_MULT", 2)
    out = B.resiliency_tiles(1, 130, "full", now=NOW)
    assert len(res_board["finish_tiles"][-1]) == 2 and len(out["tiles"]) == 1
    for t in res_board["finish_tiles"][-1]:
        for k in B.ATTACH_OWNED_KEYS:
            assert k not in t


def test_api_coercion_with_query_objects(monkeypatch):
    from chart_maps import api
    seen = {}

    def fake_board(**kw):
        seen.update(kw)
        return {"tiles": []}
    monkeypatch.setattr(api.board_mod, "board", fake_board)
    asyncio.run(api.chart_maps(tab="resiliency"))                  # every other arg a Query object
    assert seen["tab"] == "resiliency" and seen["res"] is None and seen["res_mode"] is None
    asyncio.run(api.chart_maps(tab="resiliency", res="t1,eod", res_mode="all"))
    assert seen["res"] == "t1,eod" and seen["res_mode"] == "all"
    asyncio.run(api.chart_maps(tab="resiliency", res="  ", res_mode=""))
    assert seen["res"] is None and seen["res_mode"] is None


# --------------------------------------------------------------------------
# 6 — the snapshot's pre-market volume
# --------------------------------------------------------------------------
def test_min_av_parsed_from_a_snapshot_json(monkeypatch):
    body = {"tickers": [{"ticker": "NVDA", "day": {"o": 0, "h": 0, "l": 0, "c": 0, "v": 0},
                         "min": {"av": 1536210, "t": 1790774340000, "v": 25535},
                         "lastTrade": {"p": 228.68, "t": 1790774351000000000},
                         "prevDay": {"c": 227.21}, "todaysChangePerc": 0.647},
                        {"ticker": "AAPL", "day": {}, "lastTrade": {}, "prevDay": {}}]}

    class Resp:
        status_code = 200

        def json(self):
            return body

    class Http:
        def get(self, *a, **k):
            return Resp()
    monkeypatch.setattr(prices, "stocks_key", lambda: "x")
    monkeypatch.setattr(prices, "_http", lambda: Http())
    out = prices.bulk_snapshot(["NVDA", "AAPL"])
    assert out["NVDA"]["min_av"] == 1536210 and out["NVDA"]["min_t_ms"] == 1790774340000
    t = R._et_of_ms(out["NVDA"]["min_t_ms"])
    assert (t.date().isoformat(), t.strftime("%H:%M")) == ("2026-09-30", "09:19")
    # NEGATIVE: no `min` object -> None, never 0
    assert out["AAPL"]["min_av"] is None and out["AAPL"]["min_t_ms"] is None
