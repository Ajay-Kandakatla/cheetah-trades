"""ICT board walk-forward backtest — every no-lookahead rule, on SYNTHETIC
1-minute and daily frames with the loaders injected. No network, no Mongo,
no scan on disk.

Ajay trades real money on the answer. A backtest with lookahead is worse
than no backtest, so the tests here are mostly about what the model was
ALLOWED to see at each 60m close: the daily frame ends on a partial bar
built from that session's minutes with stamps < t, never the session's
full bar or anything later; the micro frame never holds a bar after t;
the micro loop stays dormant until macro taps; a signal is stamped once,
on the first entry close; outcomes read minutes strictly after t; the
placebo sits at least a horizon earlier with the same R distances.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ict import backtest as BT  # noqa: E402
from ict import engine as E  # noqa: E402
from supply_demand.timeframes import frame_for  # noqa: E402

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# synthetic frames
# ---------------------------------------------------------------------------
def _accumulation(n):
    out = []
    for i in range(n):
        out.append((100.0, 100.5, 99.7, 100.1) if i % 2 == 0 else (100.1, 100.3, 99.5, 100.0))
    return out


def _entry_rows(accum=29):
    """The engine test's confirmed-then-entry 60m pattern, with a longer
    accumulation so the confirmed close (bar accum+2) already clears
    MICRO_MIN_BARS: manipulation under the range low, a 2-ATR push that
    leaves a gap, MSS on the gap's third bar, pullback into the gap."""
    rows = _accumulation(accum)
    rows += [(99.8, 100.2, 98.5, 99.6),      # manipulation: wick under 99.5, close back above
             (99.7, 101.8, 99.6, 101.7),     # displacement up, body 2.0
             (101.6, 102.4, 101.0, 102.2),   # low 101.0 > bar high 100.2 -> bullish FVG; MSS -> confirmed
             (102.2, 102.3, 101.5, 101.8),   # pullback (still confirmed)
             (101.8, 101.9, 101.2, 101.4),   # close inside the entry tolerance -> entry
             (101.4, 101.5, 100.9, 101.0)]   # still entry (dedupe)
    return rows


def _expand(o, h, l, c, n, t0):
    """`n` 1-minute bars realising one OHLC bar: open on the first minute,
    the high a third of the way in, the low two thirds in, close last."""
    closes = np.linspace(o, c, n + 1)[1:]
    opens = np.concatenate([[o], closes[:-1]])
    highs = np.maximum(opens, closes).copy()
    lows = np.minimum(opens, closes).copy()
    highs[n // 3] = h
    lows[(2 * n) // 3] = l
    idx = pd.DatetimeIndex([t0 + pd.Timedelta(minutes=k) for k in range(n)])
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes,
                         "volume": 1000.0, "session": "rth"}, index=idx)


def _minutes(rows, start="2026-08-03"):
    """Seven 60m bars a session (the first one 09:30-09:59 ET, then six full
    hours), August 2026 = EDT so 09:30 ET is 13:30 UTC. UTC-naive stamps the
    way daytrading.data leaves them."""
    days = pd.bdate_range(start, periods=len(rows) // 7 + 1)
    parts = []
    for i, (o, h, l, c) in enumerate(rows):
        d, k = days[i // 7], i % 7
        if k == 0:
            t0, n = pd.Timestamp(d) + pd.Timedelta(hours=13, minutes=30), 30
        else:
            t0, n = pd.Timestamp(d) + pd.Timedelta(hours=13 + k), 60
        parts.append(_expand(o, h, l, c, n, t0))
    return pd.concat(parts)


def _history(n=64, end="2026-07-31", dip_at=52, peak_at=60):
    """Closed daily sessions before the minutes: overlapping alternating bars
    (no gaps, no strict swings), one strict swing low at 99.0 (the tap
    level) and one fractal swing high at 105.0 (the target)."""
    idx = pd.bdate_range(end=end, periods=n)
    rows = []
    for i in range(n):
        r = (100.0, 102.0, 99.6, 101.0) if i % 2 == 0 else (101.0, 101.8, 99.8, 100.2)
        if i == dip_at:
            r = (100.0, 101.0, 99.0, 100.5)
        if i == peak_at:
            r = (100.5, 105.0, 99.9, 101.0)
        rows.append(r)
    return pd.DataFrame({"open": [r[0] for r in rows], "high": [r[1] for r in rows],
                         "low": [r[2] for r in rows], "close": [r[3] for r in rows],
                         "volume": 2e6}, index=idx)


def _daily_from_minutes(raw):
    days = BT._et_day_ints(raw.index)
    g = raw.groupby(days)
    df = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                       "close": g["close"].last(), "volume": g["volume"].sum()})
    df.index = pd.DatetimeIndex([pd.Timestamp(BT._date_from_day_int(int(d))) for d in df.index])
    return df


def _rising(start_level, sessions, step=0.1):
    rows, lvl = [], start_level
    for _s in range(sessions):
        for _k in range(7):
            o, c = lvl, lvl + step
            rows.append((o, c + 0.2, o - 0.2, c))
            lvl = c
    return rows


def _scenario(after_sessions=11):
    """Minutes: 5 sessions carrying the entry pattern, then `after_sessions`
    rising sessions (the 105 target gets hit). Daily: 64 closed history
    sessions + the minute sessions' own bars (what load_prices would hold)."""
    rows = _entry_rows() + [(101.0, 101.4, 100.8, 101.2)] * 1
    rows = rows[:35]
    rows += _rising(101.2, after_sessions)
    raw = _minutes(rows)
    daily = pd.concat([_history(), _daily_from_minutes(raw)])
    return rows, raw, daily


@pytest.fixture(scope="module")
def scenario():
    rows, raw, daily = _scenario()
    ctx = BT.prepare("AAA", raw, daily, min_sessions=5)
    return {"rows": rows, "raw": raw, "daily": daily, "ctx": ctx}


def _flat_minutes(sessions=30, start="2026-06-01", seed=3):
    rng = np.random.default_rng(seed)
    rows = []
    lvl = 100.0
    for _s in range(sessions):
        for _k in range(7):
            c = lvl + float(rng.normal(0, 0.15))
            rows.append((lvl, max(lvl, c) + 0.1, min(lvl, c) - 0.1, c))
            lvl = c
    return _minutes(rows, start)


# ---------------------------------------------------------------------------
# the time axis: frame_for's 60m bars, in order
# ---------------------------------------------------------------------------
def test_time_axis_is_frame_for_60m_and_hpos_counts_minutes_before_the_close(scenario):
    ctx, raw, rows = scenario["ctx"], scenario["raw"], scenario["rows"]
    h1, _meta = frame_for("AAA", "60m", raw=raw, bars=len(raw) + 1)
    assert list(ctx.ht) == list(h1.index.asi8)
    assert np.allclose(ctx.h1[["open", "high", "low", "close"]].to_numpy(), np.array(rows))
    assert ctx.n_sessions == 16 and len(ctx.ht) == 16 * 7
    for j in (0, 1, 6, 7, 33, len(ctx.ht) - 1):
        t = ctx.ht[j]
        assert int(ctx.hpos[j]) == int((raw.index.asi8 < t).sum())
        assert ctx.hsess[j] == j // 7
    # a close label belongs to the bar before it: the 16:00 ET close is still
    # that session, not the next day
    assert BT._iso_et(ctx.ht[6]).endswith("16:00:00-04:00")
    assert ctx.session_date(int(ctx.hsess[6])) == date(2026, 8, 3)


# ---------------------------------------------------------------------------
# rule 1 — what the daily read is allowed to see
# ---------------------------------------------------------------------------
def test_as_of_daily_never_holds_the_current_full_bar_or_anything_later(scenario):
    ctx, raw, daily = scenario["ctx"], scenario["raw"], scenario["daily"]
    seen = []

    def spy(sym, df):
        seen.append((df.index[-1], len(df), df.iloc[-1].to_dict(), df.index.max()))
        return E.macro(sym, df=df)

    BT.walk(ctx, macro_fn=spy, seed=1)
    assert len(seen) == len(ctx.ht)
    days = BT._et_day_ints(raw.index)
    for j, (last_idx, n, last_row, max_idx) in enumerate(seen):
        s = int(ctx.hsess[j])
        sd = pd.Timestamp(ctx.session_date(s))
        assert last_idx == sd and max_idx == sd            # ends ON the session, nothing later
        closed = daily[daily.index < sd]
        assert n == len(closed) + 1                        # closed sessions + one partial bar
        t = ctx.ht[j]
        m = raw[(days == int(ctx.sessions[s])) & (raw.index.asi8 < t)]
        assert last_row["open"] == m["open"].iloc[0]
        assert last_row["high"] == m["high"].max()         # running extremes at t
        assert last_row["low"] == m["low"].min()
        assert last_row["close"] == m["close"].iloc[-1]
        assert last_row["volume"] == m["volume"].sum()
        if j % 7 < 6:
            full = daily.loc[sd]
            assert not (last_row["high"] == full["high"] and last_row["low"] == full["low"]
                        and last_row["close"] == full["close"] and last_row["volume"] == full["volume"]), \
                "an intra-session close saw the session's full daily bar"


def test_closed_part_of_the_as_of_frame_is_the_daily_cache_not_minutes(scenario):
    ctx, daily = scenario["ctx"], scenario["daily"]
    df = BT.as_of_daily(ctx, 4, 33)
    sd = pd.Timestamp(ctx.session_date(4))
    pd.testing.assert_frame_equal(df.iloc[:-1], daily[daily.index < sd].astype(float))
    assert df.index[-1] == sd


def test_incremental_session_frame_equals_a_plain_macro_call(scenario):
    """Rule 2: the walk overwrites one placeholder row per close; the read
    must equal macro() on a freshly built as-of frame."""
    ctx = scenario["ctx"]
    live = {}

    def spy(sym, df):
        m = E.macro(sym, df=df)
        live[len(live)] = (df.copy(), m)
        return m

    BT.walk(ctx, macro_fn=spy, seed=1)
    for j in (0, 3, 6, 7, 29, 31, 33, 34, 70):
        df_live, m_live = live[j]
        fresh = BT.as_of_daily(ctx, int(ctx.hsess[j]), j)
        pd.testing.assert_frame_equal(df_live, fresh)
        assert E.macro("AAA", df=fresh) == m_live


def test_partial_bar_is_none_before_the_first_minute_and_grows_within_the_session(scenario):
    ctx = scenario["ctx"]
    o, h, lo, c, v = BT.partial_bar(ctx, 4, 28)             # 09:30-09:59 of session 4
    assert v == 30 * 1000.0 and o == 100.0 and h == 100.5 and lo == 99.7 and c == 100.1
    o2, h2, lo2, c2, v2 = BT.partial_bar(ctx, 4, 33)         # through 15:00 ET
    assert v2 == (30 + 5 * 60) * 1000.0 and h2 >= h and lo2 <= lo


# ---------------------------------------------------------------------------
# rule 1 (micro) + rule 3 (dormant)
# ---------------------------------------------------------------------------
def test_micro_frame_never_holds_a_bar_after_t_and_respects_the_production_window(scenario):
    ctx = scenario["ctx"]
    calls = []

    def mspy(sym, df, mctx):
        calls.append((df.index.max().value, df.index.min().value, len(df)))
        return E.micro(sym, "60m", df=df, macro_ctx=mctx)

    seen_t = []

    def maspy(sym, df):
        m = E.macro(sym, df=df)
        seen_t.append(m)
        return m

    BT.walk(ctx, macro_fn=maspy, micro_fn=mspy, seed=1)
    assert calls, "the scenario must wake the micro loop"
    tapped_js = [j for j, m in enumerate(seen_t) if m and m.get("tapped")]
    assert len(tapped_js) == len(calls)
    start, end = E.micro_raw_window(today=date(2026, 8, 7))
    for j, (mx, mn, n) in zip(tapped_js, calls):
        assert mx <= ctx.ht[j]                              # never a bar after t
        assert mx == ctx.ht[j]                              # the bar closing at t is included
        assert n <= j + 1
        sd = ctx.session_date(int(ctx.hsess[j]))
        assert pd.Timestamp(mn).tz_localize("UTC").tz_convert(ET).date() >= sd - (end - start)
        # ...and not SHORTER than production either: every bar whose session
        # lies inside the window is there (consolidations() segments from the
        # frame start, so a shorter frame is a different state machine)
        day0 = int(ctx.sessions[int(ctx.hsess[j])]) - (end - start).days
        lo_expected = int(np.searchsorted(ctx.hday, day0, side="left"))
        assert mn == ctx.ht[max(lo_expected, j + 1 - 330)] and n == j + 1 - max(lo_expected, j + 1 - 330)


def test_warmup_covers_the_production_micro_window():
    """The first evaluated close must see the same micro window the cron
    would have: WARMUP_DAYS >= engine.micro_raw_window's span."""
    start, end = E.micro_raw_window(today=date(2026, 8, 7))
    assert BT.WARMUP_DAYS >= (end - start).days == E.MICRO_DAYS + 4


def test_micro_loop_is_dormant_until_macro_taps(scenario):
    ctx = scenario["ctx"]
    called = []
    res = BT.walk(ctx, macro_fn=lambda s, df: {"symbol": s, "tapped": None, "date": "x", "swings": []},
                  micro_fn=lambda s, df, m: called.append(1) or None, seed=1)
    assert called == [] and res["tapped_bars"] == 0 and res["micro_calls"] == 0
    assert res["signals"] == [] and res["evaluated"] == len(ctx.ht)


def test_micro_runs_only_on_tapped_closes(scenario):
    ctx = scenario["ctx"]
    calls = []
    tap_on = {33, 34}

    def macro_fn(s, df):
        j = len(calls_seen)
        calls_seen.append(1)
        return {"symbol": s, "tapped": ({"kind": "swing_low", "bias": "bullish", "price": 99.0,
                                          "bar_i": len(df) - 2, "date": "2026-08-06"} if j in tap_on else None),
                "date": "x", "swings": []}
    calls_seen = []
    res = BT.walk(ctx, macro_fn=macro_fn, micro_fn=lambda s, df, m: calls.append(len(df)) or None, seed=1)
    assert res["tapped_bars"] == 2 and len(calls) == 2


# ---------------------------------------------------------------------------
# rule 4 — the signal: first entry close, deduped, with the plan
# ---------------------------------------------------------------------------
def test_end_to_end_signal_is_the_first_entry_close_with_the_board_plan(scenario):
    ctx = scenario["ctx"]
    res = BT.walk(ctx, seed=7)
    assert res["skipped_no_plan"] == 0 and res["macro_none"] == 0
    sigs = res["signals"]
    assert len(sigs) == 1, [s["signal_ts"] for s in sigs]
    s = sigs[0]
    assert s["bar_i"] == 33 and s["signal_ts"] == "2026-08-07T15:00:00-04:00"
    assert s["session"] == "2026-08-07" and s["month"] == "2026-08"
    assert s["bias"] == "bullish" and s["state"] == "entry" and s["grade"] == 100
    assert s["grade_bucket"] == "100" and s["source"] == "power_of_three"
    assert s["tap_kind"] == "swing_low" and s["tap_price"] == 99.0 and s["tap_age_sessions"] == 0
    assert s["tap_bias"] == "bullish" and s["bias_matches_tap"] is True
    assert s["zone"] == "fvg" and s["entry"] == 101.0 and s["target"] == 105.0
    assert s["stop"] < 98.5 and s["rr"] > 1.0                # stop under the manipulation low, buffered
    assert s["fill"] == s["close_at_t"] == 101.4               # the 60m close, not the zone edge
    assert s["macro_date"] == "2026-08-07"                     # the as-of frame ended on the session
    assert s["manipulation_at"] == "2026-08-07T11:00:00-04:00"
    assert s["key"] == "AAA|bullish|2026-08-07T11:00:00-04:00"
    # the next close (bar 34, close 101.0) is ALSO an entry for the same key
    # — the engine says so — and it is not a second signal
    mi = E.micro("AAA", "60m", df=BT.micro_window(ctx, 4, 34), macro_ctx=E.macro("AAA", df=BT.as_of_daily(ctx, 4, 34)))
    assert mi["state"] == "entry" and mi["manipulation"]["at"] == s["manipulation_at"]


def test_end_to_end_confirmed_table_and_entered_later(scenario):
    ctx = scenario["ctx"]
    res = BT.walk(ctx, seed=7)
    conf = res["confirmed"]
    assert len(conf) == 1
    c = conf[0]
    assert c["state"] == "confirmed" and c["bar_i"] == 31 and c["entered_later"] is True
    assert c["kind"] == "confirmed" and c["fill"] == 102.2 and c["outcome"] in ("target", "stop", "horizon")
    assert c["key"] == res["signals"][0]["key"]


def test_signal_is_stamped_once_per_key_and_new_keys_get_new_signals(scenario):
    ctx = scenario["ctx"]
    plan = {"entry": 101.0, "entry_lo": 100.2, "entry_hi": 101.0, "stop": 98.3, "target": 105.0,
            "rr": 1.5, "zone": "fvg", "risk_pct": 2.7}
    seq = {33: "A", 34: "A", 35: "A", 40: "B", 41: "B"}

    def micro_fn(s, df, m):
        j = len(df) - 1 + 0                       # not reliable; use the last stamp instead
        t = df.index.max().value
        j = int(np.searchsorted(ctx.ht, t))
        if j not in seq:
            return None
        return {"bias": "bullish", "state": "entry", "grade": 100, "plan": plan, "atr": 0.8,
                "manipulation": {"at": f"manip-{seq[j]}"}, "mss": None, "fvg": None, "ifvg": None,
                "source": "power_of_three", "why": "x", "last": 101.0}

    tap = lambda s, df: {"symbol": s, "tapped": {"kind": "swing_low", "bias": "bullish", "price": 99.0,
                                                  "bar_i": len(df) - 1, "date": "d"}, "date": "x", "swings": []}
    res = BT.walk(ctx, macro_fn=tap, micro_fn=micro_fn, seed=1)
    assert [s["bar_i"] for s in res["signals"]] == [33, 40]
    assert [s["key"] for s in res["signals"]] == ["AAA|bullish|manip-A", "AAA|bullish|manip-B"]


def test_entry_without_a_plan_or_stop_is_skipped_and_counted(scenario):
    ctx = scenario["ctx"]

    def micro_fn(s, df, m):
        j = int(np.searchsorted(ctx.ht, df.index.max().value))
        if j == 33:
            return {"bias": "bullish", "state": "entry", "grade": 80, "plan": None,
                    "manipulation": {"at": "m1"}, "atr": 0.8}
        if j == 40:
            return {"bias": "bearish", "state": "entry", "grade": 80,
                    "plan": {"entry": 1, "stop": None, "target": None, "zone": "fvg"},
                    "manipulation": {"at": "m2"}, "atr": 0.8}
        return None

    tap = lambda s, df: {"symbol": s, "tapped": {"kind": "fvg", "bias": "bullish", "price": 99.0,
                                                  "bar_i": len(df) - 1, "date": "d"}, "date": "x", "swings": []}
    res = BT.walk(ctx, macro_fn=tap, micro_fn=micro_fn, seed=1)
    assert res["signals"] == [] and res["skipped_no_plan"] == 2


def test_bars_before_eval_from_are_context_only(scenario):
    ctx = scenario["ctx"]
    seen = []
    day = int(ctx.sessions[4])
    BT.walk(ctx, macro_fn=lambda s, df: seen.append(df.index[-1]) or None, eval_from_day=day, seed=1)
    assert min(seen) == pd.Timestamp(ctx.session_date(4)) and len(seen) == (16 - 4) * 7


# ---------------------------------------------------------------------------
# rule 5 — outcomes on minutes strictly after t
# ---------------------------------------------------------------------------
def _arrs(bars):
    hi = np.array([b[0] for b in bars], dtype=float)
    lo = np.array([b[1] for b in bars], dtype=float)
    cl = np.array([b[2] for b in bars], dtype=float)
    return hi, lo, cl


def test_outcome_target_before_stop_with_mfe_mae_in_r():
    hi, lo, cl = _arrs([(101, 99.5, 100.5), (102, 100, 101), (104, 101, 103.5), (103, 102, 102.5)])
    o = BT.outcome("bullish", 100.0, 98.0, 104.0, hi, lo, cl)
    assert o["outcome"] == "target" and o["bars_to_outcome"] == 3
    assert o["r_abs"] == 2.0
    assert o["mfe_r"] == 2.0 and o["mae_r"] == 0.25          # (104-100)/2, (100-99.5)/2 through the exit bar
    assert o["ret_at_horizon_r"] == 1.25                     # (102.5-100)/2, marked at the LAST close
    assert o["ret_at_horizon_pct"] == 2.5 and o["mfe_pct"] == 4.0


def test_outcome_stop_first_even_when_target_hits_later():
    hi, lo, cl = _arrs([(100.5, 97.9, 98.5), (105, 98, 104), (106, 104, 105)])
    o = BT.outcome("bullish", 100.0, 98.0, 104.0, hi, lo, cl)
    assert o["outcome"] == "stop" and o["bars_to_outcome"] == 1
    assert o["mae_r"] == 1.05 and o["mfe_r"] == 0.25
    assert o["ret_at_horizon_r"] == 2.5                      # holding through would have paid; reported, not credited


def test_same_minute_tie_counts_as_stop():
    hi, lo, cl = _arrs([(100.2, 99.8, 100), (104.5, 97.5, 101), (102, 101, 101.5)])
    o = BT.outcome("bullish", 100.0, 98.0, 104.0, hi, lo, cl)
    assert o["outcome"] == "stop" and o["bars_to_outcome"] == 2


def test_horizon_when_neither_touches_and_no_target_resolves_only_by_stop_or_horizon():
    hi, lo, cl = _arrs([(101, 99, 100.5), (102, 99.5, 101.5), (101.8, 100, 101)])
    o = BT.outcome("bullish", 100.0, 98.0, 104.0, hi, lo, cl)
    assert o["outcome"] == "horizon" and o["bars_to_outcome"] == 3 and o["ret_at_horizon_r"] == 0.5
    o2 = BT.outcome("bullish", 100.0, 98.0, None, hi, lo, cl)
    assert o2["outcome"] == "horizon"
    hi3, lo3, cl3 = _arrs([(101, 99, 100.5), (110, 97, 108)])
    assert BT.outcome("bullish", 100.0, 98.0, None, hi3, lo3, cl3)["outcome"] == "stop"


def test_bearish_mirror():
    hi, lo, cl = _arrs([(100.5, 99, 99.5), (100, 96.5, 97), (98, 96.2, 97.5)])
    o = BT.outcome("bearish", 100.0, 102.0, 96.0, hi, lo, cl)
    assert o["outcome"] == "horizon" and o["ret_at_horizon_r"] == 1.25   # (100-97.5)/2
    assert o["mfe_r"] == 1.9 and o["mae_r"] == 0.25                      # (100-96.2)/2, (100.5-100)/2
    hi2, lo2, cl2 = _arrs([(100.5, 99, 99.5), (102.5, 98, 101)])
    assert BT.outcome("bearish", 100.0, 102.0, 96.0, hi2, lo2, cl2)["outcome"] == "stop"
    hi3, lo3, cl3 = _arrs([(100.5, 99, 99.5), (100, 95.9, 96.5)])
    assert BT.outcome("bearish", 100.0, 102.0, 96.0, hi3, lo3, cl3)["outcome"] == "target"
    hi4, lo4, cl4 = _arrs([(102.5, 95.5, 99)])                             # tie -> stop, mirrored
    assert BT.outcome("bearish", 100.0, 102.0, 96.0, hi4, lo4, cl4)["outcome"] == "stop"


def test_unresolved_window_keeps_only_the_partial_first_touch_and_bad_geometry_is_flagged():
    hi, lo, cl = _arrs([(101, 97, 98), (103, 98, 102)])
    o = BT.outcome("bullish", 100.0, 98.0, 104.0, hi, lo, cl, resolved_window=False)
    assert o["outcome"] == "unresolved" and o["partial_first_touch"] == "stop"
    assert o["mfe_r"] is None and o["ret_at_horizon_r"] is None and o["bars_available"] == 2
    assert BT.outcome("bullish", 100.0, 101.0, 104.0, hi, lo, cl)["outcome"] == "bad_geometry"
    assert BT.outcome("bullish", 100.0, 98.0, 104.0, [], [], [])["outcome"] == "unresolved"


def test_target_already_passed_at_the_fill_is_bad_geometry_not_a_target_hit():
    """A bullish target at or under the fill (bearish at or over) would be
    'hit' on the first forward minute for ~0 R; it is geometry, skipped."""
    hi, lo, cl = _arrs([(101, 99.5, 100.5), (102, 100, 101)])
    assert BT.outcome("bullish", 100.0, 98.0, 99.0, hi, lo, cl)["outcome"] == "bad_geometry"
    assert BT.outcome("bullish", 100.0, 98.0, 100.0, hi, lo, cl)["outcome"] == "bad_geometry"
    assert BT.outcome("bearish", 100.0, 102.0, 101.0, hi, lo, cl)["outcome"] == "bad_geometry"
    assert BT.outcome("bearish", 100.0, 102.0, 100.0, hi, lo, cl)["outcome"] == "bad_geometry"
    assert BT.outcome("bullish", 100.0, 98.0, 100.01, hi, lo, cl)["outcome"] == "target"
    assert BT.outcome("bearish", 100.0, 102.0, 99.99, hi, lo, cl)["outcome"] == "target"   # low 99.5 reaches it
    # through the walk: such an entry is skipped and counted, never a signal
    rows, raw, daily = _scenario()
    ctx = BT.prepare("DDD", raw, daily, min_sessions=5)

    def micro_fn(s, df, m):
        j = int(np.searchsorted(ctx.ht, df.index.max().value))
        if j != 33:
            return None
        return {"bias": "bullish", "state": "entry", "grade": 80,
                "plan": {"entry": 101.0, "stop": 98.3, "target": float(ctx.hc[33]) - 0.5, "zone": "fvg", "rr": 1.0},
                "manipulation": {"at": "m"}, "atr": 0.8}

    tap = lambda s, df: {"symbol": s, "tapped": {"kind": "swing_low", "bias": "bullish", "price": 99.0,
                                                  "bar_i": len(df) - 1, "date": "d"}, "date": "x", "swings": []}
    res = BT.walk(ctx, macro_fn=tap, micro_fn=micro_fn, seed=1)
    assert res["signals"] == [] and res["skipped_bad_geometry"] == 1


def test_evaluate_reads_minutes_strictly_after_t_and_unresolved_past_the_data_end(scenario):
    ctx = scenario["ctx"]
    j = 33
    start, end, ok, last = BT._window(ctx, j, BT.HORIZON_SESSIONS)
    assert start == int(ctx.hpos[j]) and ctx.mt[start] >= ctx.ht[j] and ctx.mt[start - 1] < ctx.ht[j]
    assert ok and last == 4 + BT.HORIZON_SESSIONS and end == int(ctx.sess_end[last])
    r = BT.evaluate(ctx, j, "bullish", 101.4, 98.3, 105.0)
    assert r["outcome"] == "target" and r["horizon_end_session"] == ctx.session_date(14).isoformat()
    assert r["sessions_to_outcome"] >= 1
    # a signal in the last sessions cannot resolve: 10 sessions do not fit
    j_late = len(ctx.ht) - 3
    r2 = BT.evaluate(ctx, j_late, "bullish", float(ctx.hc[j_late]), float(ctx.hc[j_late]) - 1.0, None)
    assert r2["outcome"] == "unresolved" and r2["horizon_end_session"] is None
    # a horizon of 1 session from the second-to-last session does fit
    r3 = BT.evaluate(ctx, len(ctx.ht) - 8, "bullish", float(ctx.hc[-8]), float(ctx.hc[-8]) - 50.0, None, horizon=1)
    assert r3["outcome"] == "horizon"


def test_evaluate_never_reads_the_signal_bars_own_minutes(scenario):
    """Regression: a stop printed by the LAST minute of the signal bar (a
    minute with stamp < t, already inside the fill) is not a forward touch.
    An off-by-one at the window start (hpos - 1) would flip this to 'stop'."""
    import copy
    ctx = copy.copy(scenario["ctx"])
    ctx.ml = ctx.ml.copy()
    ctx.mh = ctx.mh.copy()
    j = 33
    b = int(ctx.hpos[j])
    fill = float(ctx.hc[j])
    stop = fill - 1.0
    ctx.ml[b - 1] = stop - 5.0                    # the signal bar's last minute, stamp < t
    assert ctx.ml[b:].min() > stop                # no forward minute reaches the stop
    r = BT.evaluate(ctx, j, "bullish", fill, stop, None)
    assert r["outcome"] == "horizon", r["outcome"]
    # the mirror for a bearish read: a high on that minute above the stop
    ctx.mh[b - 1] = fill + 30.0
    assert ctx.mh[b:].max() < fill + 20.0
    rb = BT.evaluate(ctx, j, "bearish", fill, fill + 20.0, None)
    assert rb["outcome"] == "horizon", rb["outcome"]
    # and the very first forward minute (stamp == t) DOES count
    ctx.ml[b] = stop - 0.01
    assert BT.evaluate(ctx, j, "bullish", fill, stop, None)["outcome"] == "stop"


# ---------------------------------------------------------------------------
# rule 6 — placebo
# ---------------------------------------------------------------------------
def test_placebo_sits_at_least_a_horizon_earlier_with_the_same_r_distances():
    import random
    raw = _flat_minutes(sessions=30)
    daily = pd.concat([_history(end="2026-05-29"), _daily_from_minutes(raw)])
    ctx = BT.prepare("BBB", raw, daily, min_sessions=5)
    j = 7 * 25 + 3                                            # session 25
    fill, stop, tgt = float(ctx.hc[j]), float(ctx.hc[j]) * 0.97, float(ctx.hc[j]) * 1.06
    for seed in range(60):
        p = BT.placebo(ctx, j, "bullish", fill, stop, tgt, random.Random(seed))
        assert p is not None
        assert int(ctx.hsess[p["bar_i"]]) <= 25 - BT.HORIZON_SESSIONS - 1
        # the placebo's own window ends strictly before the signal's session:
        # no minute is read by both windows
        p_start, p_end, p_ok, p_last = BT._window(ctx, p["bar_i"], BT.HORIZON_SESSIONS)
        assert p_ok and p_last <= 25 - 1 and p_end <= int(ctx.sess_start[25])
        assert p_end <= int(ctx.hpos[j])
        assert p["fill"] == round(float(ctx.hc[p["bar_i"]]), 4)
        assert abs((p["fill"] - p["stop"]) / p["fill"] - 0.03) < 1e-6
        assert abs((p["target"] - p["fill"]) / p["fill"] - 0.06) < 1e-6
        assert p["outcome"] in ("target", "stop", "horizon")   # its own horizon always fits
    pb = BT.placebo(ctx, j, "bearish", fill, fill * 1.03, fill * 0.94, random.Random(1))
    assert pb["stop"] > pb["fill"] > pb["target"]
    assert BT.placebo(ctx, 7 * 5, "bullish", fill, stop, tgt, random.Random(1)) is None   # nothing 11 sessions back
    assert BT.placebo(ctx, 7 * 10, "bullish", fill, stop, tgt, random.Random(1)) is None  # session 10: only <= -1
    assert BT.placebo(ctx, 7 * 11, "bullish", fill, stop, tgt, random.Random(1))["bar_i"] < 7   # session 11 -> session 0
    assert BT.placebo(ctx, j, "bullish", fill, stop, None, random.Random(1))["target"] is None


def test_placebo_is_seeded_per_symbol(scenario):
    raw = _flat_minutes(sessions=30)
    daily = pd.concat([_history(end="2026-05-29"), _daily_from_minutes(raw)])
    ctx = BT.prepare("CCC", raw, daily, min_sessions=5)
    plan = {"entry": 100.0, "stop": 97.0, "target": 106.0, "rr": 2.0, "zone": "ifvg"}
    tap = lambda s, df: {"symbol": s, "tapped": {"kind": "swing_low", "bias": "bullish", "price": 99.0,
                                                  "bar_i": len(df) - 1, "date": "d"}, "date": "x", "swings": []}

    def micro_fn(s, df, m):
        j = int(np.searchsorted(ctx.ht, df.index.max().value))
        if j != 7 * 20:
            return None
        return {"bias": "bullish", "state": "entry", "grade": 80, "plan": dict(plan, stop=float(ctx.hc[j]) - 2.0),
                "manipulation": {"at": "m"}, "atr": 0.5}

    a = BT.walk(ctx, macro_fn=tap, micro_fn=micro_fn, seed=7)["signals"][0]["placebo"]
    b = BT.walk(ctx, macro_fn=tap, micro_fn=micro_fn, seed=7)["signals"][0]["placebo"]
    c = BT.walk(ctx, macro_fn=tap, micro_fn=micro_fn, seed=8)["signals"][0]["placebo"]
    assert a == b and a["ts"] != c["ts"]


# ---------------------------------------------------------------------------
# prepare: skips and the mismatch guard
# ---------------------------------------------------------------------------
def test_prepare_skips_short_histories_missing_daily_and_split_drift():
    raw = _flat_minutes(sessions=8)
    daily = pd.concat([_history(end="2026-05-29"), _daily_from_minutes(raw)])
    with pytest.raises(BT.SkipSymbol) as ex:
        BT.prepare("X", raw, daily)
    assert ex.value.reason == "short_minute_history"
    with pytest.raises(BT.SkipSymbol) as ex:
        BT.prepare("X", None, daily, min_sessions=1)
    assert ex.value.reason == "no_minutes"
    with pytest.raises(BT.SkipSymbol) as ex:
        BT.prepare("X", raw, daily.iloc[:10], min_sessions=1)
    assert ex.value.reason == "no_daily"
    drift = daily.copy()
    drift.loc[drift.index >= "2026-06-01", ["open", "high", "low", "close"]] *= 2.0   # daily cache pre-split
    with pytest.raises(BT.SkipSymbol) as ex:
        BT.prepare("X", raw, drift, min_sessions=1)
    assert ex.value.reason == "daily_minute_mismatch"
    assert BT.prepare("X", raw, daily, min_sessions=1).n_sessions == 8


def test_prepare_drops_todays_open_session_and_extended_hours():
    raw = _flat_minutes(sessions=6, start="2026-08-17")
    ext = raw.iloc[:5].copy()
    ext.index = ext.index - pd.Timedelta(hours=2)
    ext["session"] = "premarket"
    raw2 = pd.concat([ext, raw]).sort_index()
    daily = pd.concat([_history(end="2026-08-14"), _daily_from_minutes(raw)])
    during = datetime(2026, 8, 24, 11, 0, tzinfo=ET)          # last synthetic session = Mon 08-24
    ctx = BT.prepare("X", raw2, daily, min_sessions=1, now=during)
    assert ctx.n_sessions == 5 and ctx.session_date(4) == date(2026, 8, 21)
    after = datetime(2026, 8, 24, 16, 5, tzinfo=ET)
    assert BT.prepare("X", raw2, daily, min_sessions=1, now=after).n_sessions == 6
    assert len(ctx.mt) == 5 * 390                              # premarket minutes gone


# ---------------------------------------------------------------------------
# report: medians, n=0 buckets, benchmarks, markdown
# ---------------------------------------------------------------------------
def test_stats_and_summary_survive_empty_and_small_buckets():
    s = BT.stats([])
    assert s["n"] == 0 and s["resolved"] == 0 and s["median_ret_at_horizon_r"] is None
    assert s["target_before_stop_pct"] is None and s["small_n"] is True
    sm = BT.summarize([], [], [])
    assert sm["overall"]["n"] == 0 and sm["placebo"]["n"] == 0 and sm["by_bias"] == {}
    md = BT.render_markdown({"summary": sm, "context": {}, "args": {}, "caveats": BT.CAVEATS,
                             "params": [], "as_of": "x", "span_start": "a", "span_end": "b",
                             "universe_size": 0, "horizon": 10})
    assert "n/a" in md and "## Verdict" in md and "(none)" in md


def test_placebo_line_is_over_the_resolved_signals_placebos_only():
    pl_ok = {"outcome": "target", "target": 1, "ret_at_horizon_r": 2.0, "mfe_r": 2, "mae_r": 0.1}
    pl_bad = {"outcome": "stop", "target": 1, "ret_at_horizon_r": -1.0, "mfe_r": 0.1, "mae_r": 1}
    sigs = [{"symbol": "A", "bias": "bullish", "outcome": "stop", "target": 1, "placebo": pl_ok},
            {"symbol": "A", "bias": "bullish", "outcome": "unresolved", "target": 1, "placebo": pl_bad},
            {"symbol": "A", "bias": "bearish", "outcome": "unresolved", "target": 1, "placebo": pl_bad}]
    sm = BT.summarize(sigs, [], [{"status": "ok"}])
    assert sm["overall"]["n"] == 3 and sm["overall"]["resolved"] == 1
    assert sm["placebo"]["n"] == 1 and sm["placebo"]["median_ret_at_horizon_r"] == 2.0
    assert list(sm["placebo_by_bias"]) == ["bullish"] and sm["placebo_by_bias"]["bullish"]["n"] == 1


def test_stats_use_medians_and_count_target_only_among_rows_with_a_target():
    recs = [
        {"outcome": "target", "target": 1, "mfe_r": 2.0, "mae_r": 0.2, "ret_at_horizon_r": 1.0, "rr": 2, "bars_to_outcome": 10},
        {"outcome": "stop", "target": 1, "mfe_r": 0.3, "mae_r": 1.1, "ret_at_horizon_r": -1.2, "rr": 2, "bars_to_outcome": 5},
        {"outcome": "horizon", "target": None, "mfe_r": 0.8, "mae_r": 0.5, "ret_at_horizon_r": 0.4, "rr": None, "bars_to_outcome": 100},
        {"outcome": "unresolved", "target": 1, "mfe_r": None, "mae_r": None, "ret_at_horizon_r": None, "rr": 3, "bars_to_outcome": None},
    ]
    s = BT.stats(recs)
    assert s["n"] == 4 and s["resolved"] == 3 and s["unresolved"] == 1 and s["with_target"] == 2
    assert s["target_before_stop_pct"] == 50.0 and s["stop_pct"] == 33.3 and s["horizon_pct"] == 33.3
    assert s["median_mfe_r"] == 0.8 and s["median_mae_r"] == 0.5
    assert s["median_ret_at_horizon_r"] == 0.4 and s["mean_ret_at_horizon_r"] == round(0.2 / 3, 4)
    assert s["small_n"] is True


def test_bench_forward_is_close_to_close_over_the_horizon():
    idx = pd.bdate_range("2026-06-01", periods=20)
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": np.arange(100, 120, dtype=float),
                       "volume": 1.0}, index=idx)
    assert BT.bench_forward(df, "2026-06-01", 10) == 10.0
    assert BT.bench_forward(df, "2026-06-06", 10) == round((114 / 104 - 1) * 100, 3)   # Saturday -> Friday 06-05's close
    assert BT.bench_forward(df, "2026-06-20", 10) is None
    assert BT.bench_forward(None, "2026-06-01", 10) is None
    ctx = BT.context_lines([{"outcome": "target", "session": "2026-06-01", "month": "2026-06"},
                            {"outcome": "unresolved", "session": "2026-06-02", "month": "2026-06"}],
                           bench_loader=lambda b: df if b == "SPY" else None)
    assert ctx["SPY"]["n"] == 1 and ctx["SPY"]["median_fwd_pct"] == 10.0
    assert ctx["RSP"]["n"] == 0 and ctx["RSP"]["median_fwd_pct"] is None


# ---------------------------------------------------------------------------
# run / resume / CLI end to end (loaders injected)
# ---------------------------------------------------------------------------
def _loaders(scenario):
    raw, daily = scenario["raw"], scenario["daily"]
    flat = _flat_minutes(sessions=16, start="2026-08-03")
    frames = {"AAA": (raw, daily), "BBB": (flat, pd.concat([_history(), _daily_from_minutes(flat)]))}
    calls = []

    def ml(sym, start, end):
        calls.append(sym)
        return frames.get(sym, (None, None))[0]

    def dl(sym):
        if sym in ("SPY", "RSP"):
            return frames["BBB"][1]
        return frames.get(sym, (None, None))[1]

    return ml, dl, calls


def test_run_writes_partial_lines_and_resume_skips_finished_symbols(scenario, tmp_path):
    ml, dl, calls = _loaders(scenario)
    out = str(tmp_path / "bt.json")
    common = dict(symbols=["AAA", "BBB", "ZZZ"], months=1, seed=7, workers=2, minute_loader=ml,
                  daily_loader=dl, bench_loader=dl, out=out, today=date(2026, 8, 24),
                  now=datetime(2026, 8, 24, 17, 0, tzinfo=ET), log_every=1, min_sessions=5)
    doc = BT.run(**common)
    lines = [json.loads(l) for l in (tmp_path / "bt.json.partial.jsonl").read_text().splitlines()]
    assert sorted(l["symbol"] for l in lines) == ["AAA", "BBB", "ZZZ"]
    assert {l["symbol"]: l["status"] for l in lines}["ZZZ"] == "skipped"
    assert doc["summary"]["counts"]["skip_reasons"] == {"no_minutes": 1}
    assert doc["summary"]["overall"]["n"] == 1 and doc["sample"] == ["AAA", "BBB", "ZZZ"]
    assert doc["span_start"] == "2026-07-24"
    assert doc["fetch_start"] == (date(2026, 7, 24) - pd.Timedelta(days=BT.WARMUP_DAYS)).isoformat() == "2026-06-29"
    calls.clear()
    doc2 = BT.run(resume=True, **common)
    # the ok symbols are not re-read; ZZZ's 'no_minutes' skip (the breaker
    # may have been open) is re-tried and re-skipped
    assert calls == ["ZZZ"]
    assert doc2["summary"]["overall"]["n"] == 1 and len(doc2["per_symbol"]) == 3
    assert doc2["signals"][0]["key"] == doc["signals"][0]["key"]
    # a data-reason skip is final: rewrite ZZZ's line and nothing is re-read
    last = {}
    for l in (tmp_path / "bt.json.partial.jsonl").read_text().splitlines():
        rec = json.loads(l)
        last[rec["symbol"]] = rec                              # the newer line wins, as in _read_partial
    assert sorted(last) == ["AAA", "BBB", "ZZZ"]
    last["ZZZ"] = dict(last["ZZZ"], status="skipped", reason="short_minute_history")
    final = [json.dumps(last[k]) for k in sorted(last)]
    (tmp_path / "bt.json.partial.jsonl").write_text("\n".join(final) + "\n")
    calls.clear()
    BT.run(resume=True, **common)
    assert calls == []
    lines = [json.loads(l) for l in final]
    # a partial file with one symbol missing: only that one is computed
    kept = [json.dumps(l) for l in lines if l["symbol"] != "BBB"]
    (tmp_path / "bt.json.partial.jsonl").write_text("\n".join(kept) + "\n")
    calls.clear()
    BT.run(resume=True, **common)
    assert calls == ["BBB"]
    # an errored symbol is not done: --resume re-runs it and the newer line wins
    err = [json.dumps(dict(l, status="error", reason="ReadTimeout") if l["symbol"] == "AAA" else l) for l in lines]
    (tmp_path / "bt.json.partial.jsonl").write_text("\n".join(err) + "\n")
    calls.clear()
    doc3 = BT.run(resume=True, **common)
    assert calls == ["AAA"] and doc3["summary"]["overall"]["n"] == 1
    assert {p["symbol"]: p["status"] for p in doc3["per_symbol"]}["AAA"] == "ok"
    assert len([json.loads(l) for l in (tmp_path / "bt.json.partial.jsonl").read_text().splitlines()]) == 4
    # a fresh (non-resume) run truncates the partial file: no stale lines survive
    calls.clear()
    BT.run(**common)
    fresh = [json.loads(l) for l in (tmp_path / "bt.json.partial.jsonl").read_text().splitlines()]
    assert sorted(calls) == ["AAA", "BBB", "ZZZ"] and len(fresh) == 3


def test_missing_minute_sessions_are_counted_not_skipped():
    raw = _flat_minutes(sessions=12, start="2026-06-01")
    daily = pd.concat([_history(end="2026-05-29"), _daily_from_minutes(raw)])
    full = BT.prepare("EEE", raw, daily, min_sessions=5)
    assert full.missing_sessions == 0
    days = BT._et_day_ints(raw.index)
    hole = raw[days != int(np.unique(days)[5])]                 # the 6th session's minutes never arrived
    ctx = BT.prepare("EEE", hole, daily, min_sessions=5)
    assert ctx.n_sessions == 11 and ctx.missing_sessions == 1
    res = BT.walk(ctx, macro_fn=lambda s, df: None, seed=1)
    assert res["missing_sessions"] == 1
    sm = BT.summarize([], [], [dict(res, symbol="EEE", status="ok")])
    assert sm["counts"]["missing_sessions"] == 1 and sm["counts"]["symbols_with_missing_sessions"] == 1


def test_cli_end_to_end_writes_json_and_markdown(scenario, tmp_path):
    ml, dl, _calls = _loaders(scenario)
    out, md = str(tmp_path / "ict_bt.json"), str(tmp_path / "ict_bt.md")
    doc = BT.main(["--names", "2", "--months", "1", "--out", out, "--md", md, "--seed", "7", "--workers", "2"],
                  universe=["BBB", "AAA", "QQQ"], minute_loader=ml, daily_loader=dl, bench_loader=dl,
                  today=date(2026, 8, 24), now=datetime(2026, 8, 24, 17, 0, tzinfo=ET), min_sessions=5)
    assert doc["universe_size"] == 3 and len(doc["sample"]) == 2
    assert doc["sample"] == BT.sample_universe(["BBB", "AAA", "QQQ"], 2, 7)
    saved = json.loads(Path(out).read_text())
    for k in ("as_of", "span_start", "span_end", "horizon", "args", "universe_size", "sample", "per_symbol",
              "summary", "context", "signals", "confirmed", "caveats", "params", "source", "seconds"):
        assert k in saved, k
    assert saved["horizon"] == BT.HORIZON_SESSIONS and saved["args"]["seed"] == 7
    assert {p["key"] for p in saved["params"]} >= set(BT.BACKTEST_PARAMS) | set(E._ENGINE_PARAMS)
    assert any("Survivorship" in c for c in saved["caveats"]) and any("same-minute" in c.lower() for c in saved["caveats"])
    assert saved["context"]["SPY"]["n"] == saved["summary"]["overall"]["resolved"]
    text = Path(md).read_text()
    for section in ("## Counts", "## Signal vs placebo", "## By bias", "## By grade", "## By tap kind",
                    "## By zone kind", "## By tap agreement", "## By manipulation source", "## By month",
                    "## Confirmed but never entered", "## Caveats", "## Owner constants in force", "## Verdict"):
        assert section in text, section
    assert "bias agrees with tap" in text and saved["summary"]["by_tap_agreement"]["bias agrees with tap"]["n"] == 1
    assert saved["summary"]["counts"]["placebo_skipped"] == 1        # the entry only, not its confirmed twin
    assert "n/a%" not in text and "| ⚠ small n |" in text
    assert "ORCHESTRATOR" in text and "TODAY's big caps" in text
    assert "minute-data holes" in text and "bad geometry" in text.lower()
    assert "HORIZON_SESSIONS" in text and "MIN_TARGET_R" in text
    if saved["summary"]["overall"]["n"]:
        assert "small n" in text                                 # 1 signal is flagged, never ranked


def test_sample_is_seeded_and_sorted():
    pool = [f"S{i}" for i in range(50)]
    a, b = BT.sample_universe(pool, 10, 7), BT.sample_universe(pool, 10, 7)
    assert a == b == sorted(a) and len(a) == 10
    assert BT.sample_universe(pool, 10, 8) != a
    assert BT.sample_universe(pool, 500, 1) == sorted(pool)


# ---------------------------------------------------------------------------
# source discipline
# ---------------------------------------------------------------------------
def test_backtest_source_discipline():
    src = (ROOT / "backend/ict/backtest.py").read_text()
    assert re.search(r"with_today_bar\s*\(", src) is None, "the live today-bar overlay is not a historical fact"
    assert re.search(r"bulk_snapshot\s*\(", src) is None
    for m in re.finditer(r"load_prices\(([^)]*)\)", src):
        assert "period" not in m.group(1) and "," not in m.group(1), m.group(0)
    assert re.search(r"\b(ema|sma|vwap)\b", src, re.IGNORECASE) is None
    assert "frame_for(" in src and ".resample(" not in src, "the 60m axis is the house resample, never by hand"
    assert "HORIZON_SESSIONS = 10" in src and "owner rule" in src
    assert E.MICRO_TF_DEFAULT == "60m" and BT.MICRO_TF == "60m"
    doc = (ROOT / "docs/ict/backtest_method.md").read_text()
    for k in list(BT.BACKTEST_PARAMS) + ["TAP_LOOKBACK", "ENTRY_TOL_PCT", "STOP_BUFFER_ATR", "MIN_TARGET_R", "MICRO_DAYS"]:
        assert k in doc, f"docs/ict/backtest_method.md does not list {k}"
    for phrase in ("placebo", "survivorship", "same-minute", "60m close", "--resume", "python -m ict.backtest"):
        assert phrase.lower() in doc.lower(), phrase
