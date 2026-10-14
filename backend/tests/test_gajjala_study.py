"""WP6 — the Gajjala study + his-example replay (scripts/gajjala_study.py, scripts/gajjala_examples.py), hermetic.

Synthetic 1-minute days only (no Massive, no Mongo). Pins: the qualification minute on his three numbers' edges; the
superset's instrument rule; the push-window rule; the entry classes; a known-edge sample reads positive and the
SAME values shuffled between event and placebo read ~0; the R math (stop wins every tie, a gap fills at the open,
breakeven after +1R, the 9-EMA close, the 60-minute exit); the clustered CI on a fixed seed and its 20-cluster floor;
NO LOOK-AHEAD (truncating or rewriting the 1-minute input after any minute leaves every earlier event unchanged); the
placebo never samples a bar before q; the RTH refusal; the replay's date check, rename retry and setting patch; and
the scripts' import scope (never the Mongo-writing loader).
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from chart_maps.gajjala import constants as GC
from daytrading.data import _classify_session
from scripts import gajjala_examples as EX
from scripts import gajjala_study as S

ET = ZoneInfo("America/New_York")
TODAY = "2026-10-13"
PRIOR = "2026-10-12"
PREV_CLOSE = 8.0                                   # 10.0 is exactly +25% (binary-exact)


# ── synthetic tape ────────────────────────────────────────────────────────────────────────────────────────────────
def path5(o, h, l, c, v):
    """A 5-minute bar as five minutes: down to the low, up to the high, back to the close, flat. The high prints in
    minute 1 — the break minute of an entry bar."""
    return [(o, o, l, l, v / 5), (l, h, l, h, v / 5), (h, h, c, c, v / 5), (c, c, c, c, v / 5), (c, c, c, c, v / 5)]


def day(dstr: str, start: str, bars5: list, custom: dict | None = None) -> pd.DataFrame:
    """bars5 = [(o,h,l,c,v) | None (empty bucket)] from `start` ET; custom = {bar offset: [five minute tuples]}."""
    t0 = datetime.strptime(f"{dstr} {start}", "%Y-%m-%d %H:%M").replace(tzinfo=ET)
    idx, rows = [], []
    for i, b in enumerate(bars5):
        if b is None:
            continue
        for k, m in enumerate((custom or {}).get(i) or path5(*b)):
            idx.append(pd.Timestamp(t0 + timedelta(minutes=5 * i + k)).tz_convert("UTC").tz_localize(None))
            rows.append(m)
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=pd.DatetimeIndex(idx))
    df["session"] = [_classify_session(t) for t in df.index]
    return df


def quiet(p, v=100_000):
    return (p, p + 0.125, p - 0.125, p, v)


D1 = (10.0, 10.5, 10.0, 10.5, 200_000)            # the detector fixtures' bull-flag leg (K1 exact at range 0.25)
D2 = (10.5, 11.0, 10.5, 11.0, 300_000)
P1 = (11.0, 11.0, 10.875, 10.9375, 100_000)
P2 = (10.9375, 10.96875, 10.8125, 10.875, 80_000)
E = (10.875, 11.25, 10.84375, 11.2, 250_000)       # breaks P2's high 10.96875 in its minute 1
TRIGGER, STOP = P2[1], P2[2]
RISK = TRIGGER - STOP                              # 0.15625


def prev_day():
    return day(PRIOR, "12:40", [quiet(PREV_CLOSE)] * 40)


def flag_day(*, rth_start="09:30", lead=4, after=None, custom=None, pm=True):
    """04:00 one premarket bucket (1M shares at +25% → q at 04:04), then `lead` quiet bars, the flag, the entry bar
    and `after` (default: a gentle rise then flat)."""
    after = after if after is not None else ([(11.2, 11.5, 11.15, 11.45, 90_000), (11.45, 11.8, 11.4, 11.75, 90_000)]
                                             + [quiet(11.75)] * 60)
    parts = [day(TODAY, "04:00", [quiet(10.0, 1_000_000)])] if pm else []
    parts.append(day(TODAY, rth_start, [quiet(10.0)] * lead + [D1, D2, P1, P2, E] + after, custom))
    return pd.concat(parts)


def run(today, *, prev=None, scope=S.DEFAULT_Q_SCOPE, prev_close=PREV_CLOSE):
    return S.study_symbol_day("TEST", TODAY, prev_day() if prev is None else prev, today, prev_close, scope=scope)


def ident(e):
    return {k: e[k] for k in ("setup", "frame", "entry_bar_t", "entry_class", "trigger", "stop", "fill_t", "window",
                               "pass_t")}


# ── his scanner, per minute ───────────────────────────────────────────────────────────────────────────────────────
def _qday(closes_vols, start="09:30"):
    t0 = datetime.strptime(f"{TODAY} {start}", "%Y-%m-%d %H:%M").replace(tzinfo=ET)
    idx = [pd.Timestamp(t0 + timedelta(minutes=i)).tz_convert("UTC").tz_localize(None) for i in range(len(closes_vols))]
    return pd.DataFrame({"open": [c for c, _ in closes_vols], "high": [c for c, _ in closes_vols],
                         "low": [c for c, _ in closes_vols], "close": [c for c, _ in closes_vols],
                         "volume": [v for _, v in closes_vols]}, index=pd.DatetimeIndex(idx))


def test_q_volume_edge_999_999_vs_1_000_000():
    assert S.qualification_minute(_qday([(10.0, 999_999)]), PREV_CLOSE) is None
    q = S.qualification_minute(_qday([(10.0, 999_999), (10.0, 1)]), PREV_CLOSE)
    assert q is not None and S.et_of(q).strftime("%H:%M") == "09:31"


def test_q_change_edge_24_99_vs_25_00():
    assert S.qualification_minute(_qday([(PREV_CLOSE * 1.2499, 2_000_000)]), PREV_CLOSE) is None
    exact = PREV_CLOSE * (1 + GC.SCAN_MIN_CHANGE_PCT / 100)           # the scanner's own expression
    assert S.qualification_minute(_qday([(exact, 2_000_000)]), PREV_CLOSE) is not None


def test_q_price_band_and_cumulative_volume_from_04_00():
    assert S.qualification_minute(_qday([(GC.SCAN_MAX_PRICE + 0.01, 2_000_000)]), 50.0) is None   # NEGATIVE above band
    assert S.qualification_minute(_qday([(GC.SCAN_MAX_PRICE, 2_000_000)]), 50.0) is not None
    assert S.qualification_minute(_qday([(0.09, 2_000_000)]), 0.05) is None                        # NEGATIVE under band
    pm = _qday([(10.0, 600_000)], start="04:00")
    rth = _qday([(10.0, 400_000)], start="09:30")
    q = S.qualification_minute(pd.concat([pm, rth]), PREV_CLOSE)
    assert S.et_of(q).strftime("%H:%M") == "09:30"                     # premarket shares count toward the 1M


def test_q_negative_no_prev_close_or_no_bars():
    assert S.qualification_minute(_qday([(10.0, 2_000_000)]), 0) is None
    assert S.qualification_minute(None, PREV_CLOSE) is None


def test_superset_instrument_rule_volume_and_band():
    prev = {s: {"c": 8.0} for s in ("ADR", "CSX", "ETFX", "NEWX", "THIN", "FLAT", "RICH")}
    today = {"ADR": {"h": 10.0, "l": 8.0, "v": 2e6}, "CSX": {"h": 11.0, "l": 8.0, "v": 2e6},
             "ETFX": {"h": 11.0, "l": 8.0, "v": 2e6}, "NEWX": {"h": 11.0, "l": 8.0, "v": 2e6},
             "THIN": {"h": 11.0, "l": 8.0, "v": 999_999}, "FLAT": {"h": 9.99, "l": 8.0, "v": 2e6},
             "RICH": {"h": 300.0, "l": 200.0, "v": 2e6}}
    prev["RICH"] = {"c": 100.0}
    types = {"ADR": "ADRC", "CSX": "CS", "ETFX": "ETF"}
    got = [s for s, _p in S.superset(today, prev, types)]
    assert got == ["ADR", "CSX", "NEWX"]           # NEGATIVE ETF out, thin out, +24.9% out, no price inside the band


def test_superset_unknown_type_dropped_under_drop_policy(monkeypatch):
    monkeypatch.setattr(GC, "SCAN_UNKNOWN_TYPE_POLICY", "drop")
    got = S.superset({"NEWX": {"h": 11.0, "l": 8.0, "v": 2e6}}, {"NEWX": {"c": 8.0}}, {})
    assert got == []


# ── windows + entry classes ───────────────────────────────────────────────────────────────────────────────────────
def _bt(hhmm, d=TODAY):
    return datetime.strptime(f"{d} {hhmm}", "%Y-%m-%d %H:%M").replace(tzinfo=ET)


@pytest.mark.parametrize("label,frame,want", [
    ("09:45", "5m", "suppressed_first15"), ("09:50", "5m", None), ("09:35", "5m", "suppressed_first15"),
    ("09:30", "5m", "suppressed_premarket"),
    ("16:00", "5m", None), ("16:05", "5m", None), ("20:00", "5m", None), ("20:05", "5m", "suppressed_window"),
    ("10:00", "15m", None), ("09:30", "15m", "suppressed_premarket"), ("09:45", "15m", "suppressed_first15"),
])
def test_spec_window_reason(label, frame, want):
    assert S.spec_window_reason(_bt(label), date.fromisoformat(TODAY), frame) == want


def test_half_day_after_hours_ends_17_00():
    hd = date.fromisoformat("2026-11-27")
    assert S.spec_window_reason(_bt("17:00", "2026-11-27"), hd, "5m") is None
    assert S.spec_window_reason(_bt("17:05", "2026-11-27"), hd, "5m") == "suppressed_window"
    assert S.window_class(_bt("13:05", "2026-11-27"), hd, "5m") == "ah"


def test_window_reason_matches_the_push_gate_once_wp4_ships():
    alerts = pytest.importorskip("chart_maps.gajjala.alerts")
    if not hasattr(alerts, "window_reason"):
        pytest.skip("WP4 window_reason not shipped")
    for hhmm in ("09:35", "09:45", "09:50", "15:55", "16:00", "16:05", "20:00", "20:05"):
        for fr in ("5m", "15m"):
            assert alerts.window_reason(_bt(hhmm), date.fromisoformat(TODAY), fr) == \
                S.spec_window_reason(_bt(hhmm), date.fromisoformat(TODAY), fr)


def test_break_class():
    base = {"broke": True, "entry_bar_t": "x", "as_of_bar_t": "x", "missed": [], "unjudged": []}
    assert S.break_class(dict(base, state="aplus")) == "aplus"
    assert S.break_class(dict(base, state="stopped")) == "stopped_in_bar"
    assert S.break_class(dict(base, state="partial", missed=["entry"])) == "ambiguous"
    assert S.break_class(dict(base, state="partial", missed=["k3_vol"])) is None          # NEGATIVE a missed rule
    assert S.break_class(dict(base, state="partial", missed=["entry", "k2"])) is None
    assert S.break_class(dict(base, state="triggered", as_of_bar_t="y")) is None           # NEGATIVE older bar
    assert S.break_class(dict(base, state="forming", broke=False)) is None


# ── end to end on one synthetic session ───────────────────────────────────────────────────────────────────────────
def test_flag_day_records_one_bull_flag_event_with_the_detector_levels():
    res = run(flag_day())
    assert res["q_t"] == f"{TODAY} 04:04"
    ev = [e for e in res["events"] if e["setup"] == "bull_flag"]
    assert len(ev) == 1
    e = ev[0]
    assert (e["trigger"], e["stop"], e["entry_class"], e["window"]) == (TRIGGER, STOP, "aplus", "rth")
    assert e["entry_bar_t"] == f"{TODAY} 10:15" and e["fill_t"] == f"{TODAY} 10:11"   # minute 1 of the entry bar
    assert e["r_session"] == pytest.approx((11.75 - TRIGGER) / RISK)
    assert e["exit_time60"] == "time" and e["exit_t_time60"] == f"{TODAY} 11:11"
    assert res["setup_free"] is False and res["pool"] == []


def test_negative_entry_inside_the_first_15_minutes_is_suppressed_not_recorded():
    res = run(flag_day(rth_start="09:00", lead=3))                    # entry bar 09:35–09:39
    assert not [e for e in res["events"] if e["setup"] == "bull_flag"]
    assert res["suppressed"]["suppressed_first15"] >= 1


def test_negative_never_listed_name_is_not_studied():
    res = run(flag_day(), prev_close=10.0)                            # +12.5% at best → his scanner never lists it
    assert res["q_t"] is None and res["events"] == [] and res["setup_free"] is None


def test_stop_inside_the_entry_bar_is_kept_as_a_loss_not_dropped():
    k = 4 + 4                                                         # the entry bar's offset in flag_day
    mins = [(10.875, 10.9, 10.85, 10.9, 50_000), (10.9, 11.25, 10.85, 11.2, 50_000),
            (11.2, 11.2, 10.8, 10.82, 50_000), (10.82, 10.85, 10.82, 10.85, 50_000), (10.85, 10.9, 10.85, 10.9, 50_000)]
    e = [x for x in run(flag_day(custom={k: mins}))["events"] if x["setup"] == "bull_flag"][0]
    assert e["entry_class"] == "stopped_in_bar"
    assert all(e[f"r_{r}"] == pytest.approx(-1.0) for r in GC.STUDY_EXIT_RULES)


def test_break_and_stop_in_one_minute_counts_as_a_stop():
    k = 4 + 4
    mins = [(10.875, 10.9, 10.85, 10.9, 50_000), (10.9, 11.25, 10.8, 11.2, 50_000)] + \
           [(11.2, 11.2, 11.2, 11.2, 50_000)] * 3
    e = [x for x in run(flag_day(custom={k: mins}))["events"] if x["setup"] == "bull_flag"][0]
    assert e["entry_class"] == "ambiguous"
    assert all(e[f"r_{r}"] == -1.0 and e[f"exit_{r}"] == "stop" for r in GC.STUDY_EXIT_RULES)


# ── NO LOOK-AHEAD ─────────────────────────────────────────────────────────────────────────────────────────────────
def _events_upto(res, cut_et):
    return sorted((ident(e) for e in res["events"] if S.parse_bar_t(e["entry_bar_t"]) <= cut_et),
                  key=lambda x: x["setup"])


@pytest.mark.parametrize("cut", ["09:45", "10:10", "10:15", "10:20", "10:30", "11:00", "13:00"])
def test_no_lookahead_truncating_after_any_minute_keeps_earlier_events(cut):
    full_day = flag_day()
    full = run(full_day)
    cut_et = _bt(cut)
    trunc = run(full_day[full_day.index < S.utc_naive(cut_et)])
    assert _events_upto(trunc, cut_et) == _events_upto(full, cut_et)


def test_no_lookahead_an_event_is_seen_only_once_its_entry_bar_has_closed():
    for today in (flag_day(), flag_day(rth_start="10:30")):
        for e in run(today)["events"]:
            assert S.parse_bar_t(e["pass_t"]) >= S.parse_bar_t(e["entry_bar_t"]), e
            assert S.parse_bar_t(e["fill_t"]) < S.parse_bar_t(e["entry_bar_t"])       # filled inside that bar


def test_no_lookahead_rewriting_the_future_never_moves_an_earlier_event():
    base = flag_day()
    crash = flag_day(after=[(11.2, 11.2, 6.0, 6.5, 5_000_000)] + [quiet(6.5)] * 60)   # a collapse after the entry
    a, b = run(base), run(crash)
    cut = _bt("10:15")
    assert _events_upto(a, cut) == _events_upto(b, cut) != []
    ea = [e for e in a["events"] if e["setup"] == "bull_flag"][0]
    eb = [e for e in b["events"] if e["setup"] == "bull_flag"][0]
    assert ea["r_session"] > 0 > eb["r_session"]                      # only the OUTCOME saw the future


def test_prefix_frame_is_the_frame_a_pass_would_build():
    from chart_maps.gajjala.bars import build_frames
    today = S.day_minutes(flag_day(), TODAY)
    everything = S.utc_naive(S.session_bounds(TODAY)["ah_close"]) + pd.Timedelta(days=1)
    full = build_frames("TEST", date.fromisoformat(TODAY), everything, prev_day(), today).f5
    L = S.utc_naive(_bt("10:15"))
    live = build_frames("TEST", date.fromisoformat(TODAY), L + pd.Timedelta(seconds=GC.BAR_SETTLE_SEC),
                        prev_day(), today[today.index < L]).f5
    cut = S.prefix_frame(full, int(full.df.index.searchsorted(L, side="right")))
    assert (cut.t, cut.c, cut.v, cut.ema9, cut.ema21, list(cut.today)) == \
        (live.t, live.c, live.v, live.ema9, live.ema21, list(live.today))


# ── placebo ───────────────────────────────────────────────────────────────────────────────────────────────────────
def zigzag_day(q_vol_per_bar=100_000):
    """No demand bar (every body < 3%), alternating higher highs → plenty of prior-bar breaks; 1M shares only at
    ~10:20, so q falls mid-morning."""
    bars, p = [], 10.0
    for i in range(70):
        step = 0.05 if i % 2 == 0 else -0.04
        o, c = p, p + step
        bars.append((o, max(o, c) + 0.03, min(o, c) - 0.03, c, q_vol_per_bar))
        p = c
    return day(TODAY, "09:30", bars)


def test_placebo_pool_only_from_a_no_setup_name_and_never_before_q():
    res = run(zigzag_day())
    assert res["setup_free"] is True and res["events"] == []
    q = datetime.strptime(res["q_t"], "%Y-%m-%d %H:%M").replace(tzinfo=ET)
    assert q > _bt("10:00")
    assert res["pool"], "a zigzag tape must offer prior-bar breaks"
    assert all(S.parse_bar_t(r["bar_t"]) > q for r in res["pool"])
    assert all(S.window_reason(S.parse_bar_t(r["entry_bar_t"]), TODAY, "5m") is None for r in res["pool"])


def test_negative_placebo_with_an_earlier_q_reaches_earlier_bars():
    late = run(zigzag_day())
    early = run(zigzag_day(q_vol_per_bar=1_000_000))                  # 1M in the first minute bucket
    assert min(S.parse_bar_t(r["bar_t"]) for r in early["pool"]) < \
        min(S.parse_bar_t(r["bar_t"]) for r in late["pool"])


def test_negative_a_name_with_a_setup_offers_no_placebo_bars():
    assert run(flag_day())["pool"] == []


def test_sample_placebo_same_session_and_window_fixed_seed():
    pools = {("2026-10-13", "rth"): [{"session": "2026-10-13", "symbol": f"P{i}", "window": "rth", "r_session": i}
                                     for i in range(80)],
             ("2026-10-13", "ah"): [{"session": "2026-10-13", "symbol": "AH", "window": "ah", "r_session": 9}]}
    evs = [{"session": "2026-10-13", "window": "rth", "setup": "bull_flag", "symbol": "E", "entry_bar_t": "t"},
           {"session": "2026-10-14", "window": "rth", "setup": "bull_flag", "symbol": "F", "entry_bar_t": "t"}]
    a, miss = S.sample_placebo(evs, pools)
    b, _ = S.sample_placebo(evs, pools)
    assert len(a) == S.PLACEBO_PER_EVENT and miss == 1                 # NEGATIVE no pool that session → missing
    assert a == b and all(r["window"] == "rth" for r in a)
    assert len({r["symbol"] for r in a}) == S.PLACEBO_PER_EVENT        # without replacement


# ── R math ────────────────────────────────────────────────────────────────────────────────────────────────────────
def mins_df(rows, start="10:11"):
    t0 = _bt(start)
    idx = [pd.Timestamp(t0 + timedelta(minutes=i)).tz_convert("UTC").tz_localize(None) for i in range(len(rows))]
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=pd.DatetimeIndex(idx))


END = S.utc_naive(_bt("16:00"))


def test_stop_exit_is_minus_one_r_and_a_gap_fills_at_the_open():
    out = S.walk_exit(mins_df([(10.9, 10.95, 10.8, 10.85)]), TRIGGER, STOP, "session", session_end=END)
    assert (out["reason"], out["r"]) == ("stop", pytest.approx(-1.0))
    gap = S.walk_exit(mins_df([(10.5, 10.6, 10.4, 10.5)]), TRIGGER, STOP, "session", session_end=END)
    assert gap["r"] == pytest.approx((10.5 - TRIGGER) / RISK) and gap["r"] < -1


T_EXIT = S.utc_naive(_bt("10:10")) + S.ONE_MIN + pd.Timedelta(minutes=GC.STUDY_TIME_EXIT_MIN)   # fill minute 10:10


def test_stop_wins_when_one_minute_touches_the_stop_and_the_time_exit():
    rows = [(11.0, 11.1, 11.0, 11.05)] * 59 + [(11.05, 11.5, 10.7, 11.4)]     # minute 11:10 ends AT the time exit
    t_exit = T_EXIT
    out = S.walk_exit(mins_df(rows, "10:11"), TRIGGER, STOP, "time60", session_end=END, time_exit=t_exit)
    assert out["reason"] == "stop" and out["r"] == pytest.approx(-1.0)


def test_time60_exits_at_the_close_of_the_sixtieth_minute():
    rows = [(11.0, 11.1, 11.0, 11.05)] * 90
    t_exit = T_EXIT
    out = S.walk_exit(mins_df(rows, "10:11"), TRIGGER, STOP, "time60", session_end=END, time_exit=t_exit)
    assert out["reason"] == "time" and out["exit_t"] == f"{TODAY} 11:10"
    assert out["r"] == pytest.approx((11.05 - TRIGGER) / RISK)


def test_trail9_breakeven_after_one_r_then_out_at_the_trigger():
    one_r = TRIGGER + GC.STUDY_BE_AFTER_R * RISK
    rows = [(11.0, one_r, 11.0, 11.1), (11.1, 11.15, TRIGGER - 0.01, 11.0)]
    out = S.walk_exit(mins_df(rows), TRIGGER, STOP, "trail9", session_end=END, ema_exit={})
    assert out["reason"] == "breakeven" and out["r"] == pytest.approx(0.0)
    no_be = S.walk_exit(mins_df([(11.0, one_r - 0.001, 11.0, 11.1), (11.1, 11.15, TRIGGER - 0.01, 11.0)]),
                        TRIGGER, STOP, "trail9", session_end=END, ema_exit={})
    assert no_be["reason"] == "session_end"                           # NEGATIVE under +1R the stop stays put


def test_trail9_exits_on_the_first_5_minute_close_under_the_9_ema_only_after_one_r():
    one_r = TRIGGER + GC.STUDY_BE_AFTER_R * RISK
    rows = [(11.0, one_r, 11.0, 11.2)] + [(11.2, 11.3, 11.15, 11.25)] * 8
    lab = S.utc_naive(_bt("10:15"))
    out = S.walk_exit(mins_df(rows, "10:11"), TRIGGER, STOP, "trail9", session_end=END,
                      ema_exit={lab: True, lab + pd.Timedelta(minutes=5): True})
    assert out["reason"] == "ema9" and out["exit_t"] == f"{TODAY} 10:14"   # BE armed after 10:11 → the 10:15 bar's close
    rows_low = [(11.0, 11.1, 11.0, 11.05)] * 9
    stay = S.walk_exit(mins_df(rows_low, "10:11"), TRIGGER, STOP, "trail9", session_end=END,
                       ema_exit={lab: True, lab + pd.Timedelta(minutes=5): True})
    assert stay["reason"] == "session_end"                            # NEGATIVE the 9 EMA exit waits for +1R


def test_session_end_stops_at_the_regular_close_and_mfe_in_r():
    rows = [(11.0, 11.5, 11.0, 11.4)] * 10
    out = S.walk_exit(mins_df(rows, "15:55"), TRIGGER, STOP, "session", session_end=END)
    assert out["exit_t"] == f"{TODAY} 15:59" and out["reason"] == "session_end"
    assert out["mfe_r"] == pytest.approx((11.5 - TRIGGER) / RISK)


# ── statistics ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_cluster_ci_fixed_seed_and_the_20_cluster_floor():
    rng = np.random.default_rng(1)
    vals = rng.normal(0.5, 1.0, 200).tolist()
    keys20 = [f"d{i % 20}" for i in range(200)]
    a, b = S.cluster_ci(vals, keys20, draws=300), S.cluster_ci(vals, keys20, draws=300)
    assert a == b and a[0] < np.mean(vals) < a[1]
    assert S.cluster_ci(vals, [f"d{i % 19}" for i in range(200)]) is None          # NEGATIVE 19 clusters
    assert S.cluster_delta_ci(vals, keys20, vals, [f"d{i % 19}" for i in range(200)]) is None


def _sample(mu_ev, mu_pl, *, seed=3, dates=40):
    rng = np.random.default_rng(seed)
    ev = [{"session": f"d{d}", "symbol": f"E{d}_{k}", "setup": "bull_flag", "r_session": float(rng.normal(mu_ev, 1)),
           "exit_session": "x", "mfe_session": 1.0} for d in range(dates) for k in range(3)]
    pl = [{"session": f"d{d}", "symbol": f"P{d}_{k}", "setup": "bull_flag", "r_session": float(rng.normal(mu_pl, 1)),
           "exit_session": "stop", "mfe_session": 0.0} for d in range(dates) for k in range(10)]
    return ev, pl


def test_a_known_edge_reads_positive():
    ev, pl = _sample(1.0, 0.0)
    c = S.compare(ev, pl, "session", draws=400)
    assert c["verdict"] == "measured_edge" and c["delta_ci_date"][0] > 0 and c["delta_ci_symbol"][0] > 0


def test_the_same_values_shuffled_read_about_zero():
    ev, pl = _sample(1.0, 0.0)
    vals = [x["r_session"] for x in ev + pl]
    rng = np.random.default_rng(11)
    rng.shuffle(vals)
    for x, v in zip(ev + pl, vals):
        x["r_session"] = v
    c = S.compare(ev, pl, "session", draws=400)
    assert c["verdict"] == "no_signal" and abs(c["delta_mean_r"]) < 0.3
    assert c["delta_ci_date"][0] < 0 < c["delta_ci_date"][1]


def test_an_inverted_sample_reads_inverted_and_too_few_clusters_reads_no_interval():
    ev, pl = _sample(-1.0, 0.0)
    assert S.compare(ev, pl, "session", draws=400)["verdict"] == "inverted"
    ev, pl = _sample(1.0, 0.0, dates=19)
    assert S.compare(ev, pl, "session", draws=400)["verdict"] == "no_interval"     # NEGATIVE 19 dates


def test_summary_reports_expectancy_and_stop_rate_beside_the_win_rate():
    ev, pl = _sample(1.0, 0.0)
    s = S.summarize(pl, "session", draws=200)
    assert s["stop_rate"] == 1.0 and set(s) >= {"mean_r", "median_r", "win_rate", "stop_rate", "median_mfe_r",
                                                "ci_date", "ci_symbol", "n", "dates", "symbols"}
    rep = S.build_report(ev, pl, ("session",), draws=200)
    assert set(rep["by_setup"]) == set(GC.SETUPS) | {"all"}
    assert rep["by_setup"]["kiss_fly"]["session"]["events"]["n"] == 0


# ── the run, the clock and the cache ──────────────────────────────────────────────────────────────────────────────
def test_refused_window():
    assert S.refused_window(_bt("10:00")) is True
    assert S.refused_window(_bt("09:29")) is False and S.refused_window(_bt("16:00")) is False
    assert S.refused_window(_bt("10:00", "2026-10-17")) is False                     # Saturday


def _freeze(monkeypatch, mod, hhmm):
    fixed = _bt(hhmm)

    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz) if tz else fixed

    monkeypatch.setattr(mod, "datetime", Frozen)


def test_main_refuses_during_rth_without_force(monkeypatch, tmp_path):
    _freeze(monkeypatch, S, "10:00")
    assert S.main(["--cache", str(tmp_path / "c"), "--out", str(tmp_path / "o"), "--offline"]) == 2
    assert not (tmp_path / "o").exists()
    assert S.main(["--cache", str(tmp_path / "c"), "--out", str(tmp_path / "o"), "--offline", "--force",
                   "--draws", "50", "--allow-short"]) == 0
    assert json.loads((tmp_path / "o" / "report.json").read_text())["meta"]["float_gate"].startswith("float gate")


def test_examples_main_refuses_during_rth(monkeypatch, tmp_path):
    _freeze(monkeypatch, EX, "11:00")
    assert EX.main(["--cache", str(tmp_path), "--out", str(tmp_path / "o"), "--offline"]) == 2


def _put_day(cache: S.Cache, sym: str, d: str, df: pd.DataFrame):
    cache._write(cache.root / "minutes" / d / f"{sym}.json", S.frame_to_json(df))


def _grouped(cache, d, rows):
    cache._write(cache.root / "grouped" / f"{d}.json", rows)


def test_run_end_to_end_from_the_file_cache_offline(tmp_path):
    cache = S.Cache(tmp_path, offline=True)
    _grouped(cache, PRIOR, {"TEST": {"o": 8, "h": 8, "l": 8, "c": PREV_CLOSE, "v": 1e6},
                            "ZIG": {"o": 8, "h": 8, "l": 8, "c": PREV_CLOSE, "v": 1e6}})
    _grouped(cache, TODAY, {"TEST": {"o": 10, "h": 11.9, "l": 9.9, "c": 11.75, "v": 3e6},
                            "ZIG": {"o": 10, "h": 11.0, "l": 9.9, "c": 10.3, "v": 7e6},
                            "DUD": {"o": 8, "h": 8.1, "l": 7.9, "c": 8.0, "v": 3e6}})
    for sym, df in (("TEST", flag_day()), ("ZIG", zigzag_day())):
        _put_day(cache, sym, TODAY, df)
        _put_day(cache, sym, PRIOR, prev_day())
    res = S.run(end=date.fromisoformat(TODAY), sessions=1, start=None, cache=cache, rules=GC.STUDY_EXIT_RULES,
                scope="warm", draws=50)
    assert res["counts"]["sessions"] == 1 and res["counts"]["listed"] == 2
    assert [e["setup"] for e in res["events"] if e["symbol"] == "TEST"].count("bull_flag") == 1
    assert res["placebo"] and all(p["symbol"] == "ZIG" for p in res["placebo"])
    assert all(p["session"] == TODAY for p in res["placebo"])
    assert cache.stats["minutes_offline_miss"] == 0


def test_cache_never_writes_a_failed_fetch(tmp_path):
    calls = []
    cache = S.Cache(tmp_path, fetch_minutes=lambda s, d: calls.append(s) or None,
                    fetch_grouped=lambda d: {})
    assert cache.minutes("X", date.fromisoformat(TODAY)) is None
    assert all("grouped" in str(p) or p.name == S.CACHE_MARKER for p in tmp_path.rglob("*.json"))
    cache.minutes("X", date.fromisoformat(TODAY))
    assert calls == ["X", "X"]                                        # retried, never cached as "no bars"
    assert cache.grouped(date.fromisoformat(TODAY)) == {}             # an empty answer IS cached (a holiday)
    assert (tmp_path / "grouped" / f"{TODAY}.json").exists()


def test_frame_json_round_trip_keeps_the_session_tag():
    df = flag_day()
    back = S.json_to_frame(S.frame_to_json(df))
    assert list(back.index) == list(df.index) and list(back["session"]) == list(df["session"])
    assert back["close"].tolist() == df["close"].tolist()


# ── his examples replay ───────────────────────────────────────────────────────────────────────────────────────────
def _daily(cache, sym, d, prev_d, prev_c):
    t = int(pd.Timestamp(f"{prev_d} 00:00", tz=ET).value // 1_000_000)
    cache._write(cache.root / "daily" / f"{sym}_{d}.json", [{"t": t, "o": prev_c, "h": prev_c, "l": prev_c,
                                                            "c": prev_c, "v": 1e6}])


def test_examples_replay_reads_a_flag_and_reports_unverified_and_missing(tmp_path):
    cache = S.Cache(tmp_path, offline=True)
    for sym in ("FLAG", "DULL"):
        _put_day(cache, sym, TODAY, flag_day())
        _put_day(cache, sym, PRIOR, prev_day())
    _daily(cache, "FLAG", TODAY, PRIOR, PREV_CLOSE)
    _daily(cache, "DULL", TODAY, PRIOR, 10.0)                         # +12.5% → his scanner never listed it
    exs = ({"ticker": "FLAG", "date": TODAY, "setup": "bull_flag", "label": "valid", "frame": "5m"},
           {"ticker": "DULL", "date": TODAY, "setup": "bull_flag", "label": "valid", "frame": "5m"},
           {"ticker": "GONE", "date": TODAY, "setup": "bull_flag", "label": "valid", "frame": "5m"})
    rows = EX.replay_examples(cache, exs)
    flag = {r["setting"]: r for r in rows if r["ticker"] == "FLAG"}
    assert flag["shipped"]["best_state"] == "aplus" and flag["shipped"]["trigger"] == TRIGGER
    assert set(flag) == {n for n, c in EX.SETTINGS.items() if "bull_flag" in c["setups"]}
    dull = [r for r in rows if r["ticker"] == "DULL"]
    assert len(dull) == 1 and dull[0]["status"].startswith("date unverified")         # NEGATIVE not replayed
    gone = [r for r in rows if r["ticker"] == "GONE"]
    assert len(gone) == 1 and gone[0]["status"].startswith("not in the cache")        # NEGATIVE reported, not skipped
    online = S.Cache(tmp_path, fetch_minutes=lambda s, d: None, fetch_daily=lambda s, a, b: [])
    gone = EX.replay_examples(online, exs[2:])
    assert gone[0]["status"].startswith("no bars (tried GONE")                         # a real miss says "no bars"
    md = EX.render_md(rows)
    assert "date unverified" in md and "not in the cache" in md


def test_examples_setting_patch_is_restored_and_refuses_unknown_names():
    before = GC.K4_KF_PULL_MAX
    with EX.patched({"K4_KF_PULL_MAX": 12}):
        assert GC.K4_KF_PULL_MAX == 12
    assert GC.K4_KF_PULL_MAX == before
    with pytest.raises(AttributeError):
        with EX.patched({"NOT_A_KNOB": 1}):
            pass
    for cfg in EX.SETTINGS.values():                                  # every override names a real constant
        assert all(hasattr(GC, k) for k in cfg["overrides"]) and set(cfg["setups"]) <= set(GC.SETUPS)


def test_examples_list_is_the_verified_set_dates():
    assert len(EX.EXAMPLES) == 27 and len({(e["ticker"], e["date"]) for e in EX.EXAMPLES}) == 27
    assert all(e["setup"] in GC.SETUPS or e["setup"] is None for e in EX.EXAMPLES)
    for e in EX.EXAMPLES:
        date.fromisoformat(e["date"])


def test_examples_best_state_ranking():
    assert EX.state_key({"state": "partial", "broke": True}) == "broke_not_aplus"
    assert EX.state_key({"state": "forming", "ready": True}) == "forming_ready"
    assert EX.STATE_RANK.index("aplus") < EX.STATE_RANK.index("stopped") < EX.STATE_RANK.index("partial")


# ── import scope / wording ────────────────────────────────────────────────────────────────────────────────────────
SCRIPTS = [Path(S.__file__), Path(EX.__file__)]


def test_scripts_never_reach_mongo_or_the_caching_loader():
    for p in SCRIPTS:
        src = p.read_text(encoding="utf-8")
        assert not re.search(r"\bload_intraday(_range)?\s*\(", src), p.name      # it writes intraday_cache
        for banned in ("_mongo_put_day", "MongoClient", "pymongo", "load_prices("):
            assert banned not in src, (p.name, banned)


def test_scripts_say_reversal_never_the_b_word():
    bword = re.compile("b" + "ounc", re.I)
    for p in SCRIPTS:
        assert not bword.search(p.read_text(encoding="utf-8")), p.name


# ── critic round 2026-10-13: as-printed bars, live scope, dated types, half days, short walks ─────────────────────
class _Resp:
    def __init__(self, status, body=None):
        self.status_code, self._body = status, body or {}

    def json(self):
        return self._body


class _FakeHttp:
    """Records every GET; answers from a queue (the last answer repeats)."""

    def __init__(self, *answers):
        self.calls, self.answers = [], list(answers)

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


def _wire(monkeypatch, http):
    import massive_keys
    from sepa import prices
    monkeypatch.setattr(massive_keys, "stocks_key", lambda: "k")
    monkeypatch.setattr(prices, "_http", lambda: http)
    monkeypatch.setattr(S.time, "sleep", lambda s: None)


def test_every_fetch_asks_for_as_printed_bars_never_split_adjusted(monkeypatch):
    t = int(pd.Timestamp(f"{TODAY} 14:00").value // 1_000_000)
    bar = {"t": t, "o": 1.0, "h": 1.0, "l": 1.0, "c": 1.0, "v": 5e6}
    http = _FakeHttp(_Resp(200, {"results": [dict(bar, T="AAA")]}))
    _wire(monkeypatch, http)
    d = date.fromisoformat(TODAY)
    assert S._fetch_grouped_http(d)["AAA"]["v"] == 5e6
    S._fetch_daily_http("AAA", d - timedelta(days=14), d)
    http.answers = [_Resp(200, {"results": [bar], "next_url": "https://api.massive.com/next"}),
                    _Resp(200, {"results": [dict(bar, t=t + 60_000)]})]
    df = S._fetch_minutes_http("AAA", d)
    assert len(df) == 2 and list(df.columns) == ["open", "high", "low", "close", "volume", "session"]
    first_pages = [c for c in http.calls if "next" not in c[0]]
    assert len(first_pages) == 3 and all(p["adjusted"] == "false" for _u, p in first_pages)
    assert http.calls[-1] == ("https://api.massive.com/next", {"apiKey": "k"})   # next_url carries its cursor
    src = Path(S.__file__).read_text(encoding="utf-8")
    assert '"adjusted": "true"' not in src and "_fetch_massive_minute(" not in src   # NEGATIVE the adjusted loader


def test_negative_minute_fetch_failure_429s_and_a_cut_page_are_not_answers(monkeypatch):
    d = date.fromisoformat(TODAY)
    _wire(monkeypatch, _FakeHttp(_Resp(500)))
    assert S._fetch_minutes_http("AAA", d) is None
    _wire(monkeypatch, _FakeHttp(_Resp(429)))
    assert S._fetch_minutes_http("AAA", d) is None                  # capped, never a hang
    _wire(monkeypatch, _FakeHttp(_Resp(200, {"results": [], "next_url": "https://x/n"})))
    assert S._fetch_minutes_http("AAA", d) is None                  # paging past the cap is cut → not cached
    _wire(monkeypatch, _FakeHttp(_Resp(200, {"results": []})))
    empty = S._fetch_minutes_http("AAA", d)
    assert empty is not None and len(empty) == 0                    # no prints IS an answer


def test_cache_refuses_a_directory_built_with_adjusted_bars(tmp_path, monkeypatch):
    old = tmp_path / "old"
    (old / "minutes" / TODAY).mkdir(parents=True)
    with pytest.raises(S.StaleCache):
        S.Cache(old, offline=True)                                  # NEGATIVE no marker + bars = layout 1
    other = tmp_path / "other"
    other.mkdir()
    (other / S.CACHE_MARKER).write_text(json.dumps({"layout": 1, "adjusted": True}))
    with pytest.raises(S.StaleCache):
        S.Cache(other, offline=True)
    fresh = S.Cache(tmp_path / "fresh", offline=True)
    assert json.loads((fresh.root / S.CACHE_MARKER).read_text()) == S.CACHE_LAYOUT
    S.Cache(tmp_path / "fresh", offline=True)                       # its own marker reads back fine
    assert S.main(["--cache", str(old), "--out", str(tmp_path / "o"), "--offline", "--force"]) == 2
    assert EX.main(["--cache", str(old), "--out", str(tmp_path / "o2"), "--offline", "--force"]) == 2


def test_live_scope_is_the_default_and_a_warm_hidden_aplus_never_becomes_a_placebo_name():
    """The critic's probe: q at 10:04 inside the flag (no premarket bucket). Live (the push's reading) records the
    10:15 bull flag; warm cuts the leg off — no event, but the name must NOT enter the placebo pool."""
    fd = flag_day(pm=False)
    assert S.DEFAULT_Q_SCOPE == "live"
    live = S.study_symbol_day("TEST", TODAY, prev_day(), fd, PREV_CLOSE)
    assert live["q_t"] == f"{TODAY} 10:04"
    assert [(e["setup"], e["entry_bar_t"]) for e in live["events"]] == [("bull_flag", f"{TODAY} 10:15")]
    warm = run(fd, scope="warm")
    assert warm["events"] == [] and warm["live_break"] is True
    assert warm["setup_free"] is False and warm["pool"] == []      # NEGATIVE never a placebo name
    zig = run(zigzag_day(), scope="warm")
    assert zig["setup_free"] is True and zig["pool"]                # a true no-setup name still is


def test_main_defaults_to_the_live_scope(tmp_path):
    assert S.main(["--cache", str(tmp_path / "c"), "--out", str(tmp_path / "o"), "--offline", "--force",
                   "--draws", "50", "--allow-short"]) == 0
    assert json.loads((tmp_path / "o" / "report.json").read_text())["meta"]["q_scope"] == "live"


def test_negative_a_break_on_an_earlier_bar_at_the_first_pass_is_not_an_event():
    """Live scope, q at 09:58: the first pass (10:00) already sees the 09:55 break AND the next bar trading under the
    stop. The read is "stopped" on an OLDER entry bar — the push never recorded it, so neither does the study."""
    after = [(11.2, 11.25, 10.7, 10.75, 90_000)] + [quiet(10.75)] * 60
    control = run(flag_day(lead=0, after=after))                    # premarket q → the pass AT 09:55 sees it
    assert [(e["setup"], e["entry_bar_t"], e["entry_class"]) for e in control["events"]] == \
        [("bull_flag", f"{TODAY} 09:55", "aplus")]
    late = run(flag_day(pm=False, lead=0, after=after))
    assert late["q_t"] == f"{TODAY} 09:58"
    assert late["events"] == []                                     # NEGATIVE entry_bar_t != as_of_bar_t


def test_superset_types_an_expired_warrant_by_the_dated_lookup():
    prev = {s: {"c": 8.0} for s in ("CSX", "OLDW", "NEWX")}
    today = {s: {"h": 11.0, "l": 8.0, "v": 2e6} for s in prev}
    asked = []

    def resolve(sym):
        asked.append(sym)
        return {"OLDW": "WARRANT"}.get(sym)

    unknown = set()
    got = [s for s, _p in S.superset(today, prev, {"CSX": "CS"}, resolve=resolve, unknown=unknown)]
    assert got == ["CSX", "NEWX"]                                   # NEGATIVE the expired warrant is out
    assert unknown == {"NEWX"} and "CSX" not in asked               # the active map wins, no call for it
    assert S.type_of("OLDW", {}, None) == GC.SCAN_UNKNOWN_TYPE      # without the lookup it would have leaked in


def test_dated_type_fetch_and_cache(monkeypatch, tmp_path):
    d = date.fromisoformat(TODAY)
    http = _FakeHttp(_Resp(200, {"results": {"ticker": "OLDW", "type": "WARRANT"}}))
    _wire(monkeypatch, http)
    assert S._fetch_type_dated_http("OLDW", d) == {"type": "WARRANT"}
    assert http.calls[0][0].endswith("/v3/reference/tickers/OLDW") and http.calls[0][1]["date"] == TODAY
    _wire(monkeypatch, _FakeHttp(_Resp(404)))
    assert S._fetch_type_dated_http("NOPE", d) == {"type": None}     # an answer: no entry that day
    _wire(monkeypatch, _FakeHttp(_Resp(500)))
    assert S._fetch_type_dated_http("NOPE", d) is None               # NEGATIVE a failure is not an answer
    calls = []
    cache = S.Cache(tmp_path, fetch_type=lambda s, dd: calls.append(s) or ({"type": "CS"} if s == "A" else None))
    assert cache.ticker_type("A", d) == "CS" and cache.ticker_type("A", d) == "CS" and calls == ["A"]
    assert cache.ticker_type("B", d) is None and cache.ticker_type("B", d) is None and calls == ["A", "B", "B"]


def test_run_tags_unknown_types_and_reports_them_dropped(tmp_path):
    cache = S.Cache(tmp_path, offline=True)
    _grouped(cache, PRIOR, {"TEST": {"c": PREV_CLOSE}, "NEWX": {"c": PREV_CLOSE}, "ZIG": {"c": PREV_CLOSE},
                            "OLDW": {"c": PREV_CLOSE}})
    _grouped(cache, TODAY, {"TEST": {"h": 11.9, "l": 9.9, "v": 3e6}, "NEWX": {"h": 11.9, "l": 9.9, "v": 3e6},
                            "ZIG": {"h": 11.0, "l": 9.9, "v": 7e6}, "OLDW": {"h": 11.9, "l": 9.9, "v": 3e6}})
    for sym, df in (("TEST", flag_day()), ("NEWX", flag_day()), ("ZIG", zigzag_day()), ("OLDW", flag_day())):
        _put_day(cache, sym, TODAY, df)
        _put_day(cache, sym, PRIOR, prev_day())
    cache._write(cache.root / "types" / TODAY / "OLDW.json", {"type": "WARRANT"})
    res = S.run(end=date.fromisoformat(TODAY), sessions=1, start=None, cache=cache, rules=("session",),
                types={"TEST": "CS", "ZIG": "CS"}, draws=50)
    assert {e["symbol"] for e in res["events"]} == {"TEST", "NEWX"}  # NEGATIVE the dated warrant never studied
    assert res["counts"]["type_unknown_kept"] == 1 and res["counts"]["listed_type_unknown"] == 1
    assert {e["symbol"]: e["type_known"] for e in res["events"]} == {"TEST": True, "NEWX": False}
    known = res["report_known_types"]["by_setup"]["bull_flag"]["session"]["events"]["n"]
    assert known == res["report"]["by_setup"]["bull_flag"]["session"]["events"]["n"] - 1
    assert "With 'type unknown' names dropped" in S.render_md(res, ("session",))


def _half_day_cache(tmp_path):
    cache = S.Cache(tmp_path, offline=True)
    _grouped(cache, "2025-11-26", {"TEST": {"c": PREV_CLOSE}})
    _grouped(cache, "2025-11-28", {"TEST": {"h": 11.9, "l": 9.9, "v": 3e6}})
    _grouped(cache, "2025-11-27", {})                                # Thanksgiving: an empty answer
    return cache


def _pre_fix_calendar(monkeypatch):
    """The house calendar as it was before the 2026-10-13 integration added 2025's three half days — the gap
    `half_day_unlisted` guards. (Pin updated at integration: the real calendar now lists them.)"""
    from catalysts.medical import reaction
    from supply_demand.timeframes import HALF_DAYS
    monkeypatch.setattr(reaction, "_half_days", lambda: {d for d in HALF_DAYS if not d.startswith("2025-")})


def test_the_house_calendar_now_lists_the_studys_half_days():
    from catalysts.medical.reaction import rth_close_time
    for d in S.HALF_DAYS_UNLISTED:
        assert rth_close_time(date.fromisoformat(d)).hour == 13, d
        assert S.half_day_unlisted(date.fromisoformat(d)) is False, d
    assert rth_close_time(date.fromisoformat("2025-11-26")) == S.ET_RTH_CLOSE       # NEGATIVE an ordinary day


def test_an_unlisted_half_day_is_skipped_and_named(tmp_path, monkeypatch):
    from catalysts.medical.reaction import rth_close_time
    _pre_fix_calendar(monkeypatch)
    hd = date.fromisoformat("2025-11-28")
    assert rth_close_time(hd) == S.ET_RTH_CLOSE                       # the calendar gap this guards
    res = S.run(end=hd, sessions=1, start=None, cache=_half_day_cache(tmp_path), rules=("session",), draws=50)
    assert res["skipped_half_days"] == ["2025-11-28"] and res["counts"].get("sessions", 0) == 0
    assert res["half_days_unchecked"] is False
    assert "2025-11-28" in S.render_md(res, ("session",))


def test_negative_a_listed_half_day_is_studied(tmp_path, monkeypatch):
    from catalysts.medical import reaction
    _pre_fix_calendar(monkeypatch)
    hd = date.fromisoformat("2025-11-28")
    assert S.half_day_unlisted(hd) is True
    assert S.half_day_unlisted(date.fromisoformat("2025-11-26")) is False          # NEGATIVE an ordinary day
    monkeypatch.setattr(reaction, "_half_days", lambda: {"2025-11-28"})           # the CROSS-WP calendar fix lands
    assert S.half_day_unlisted(hd) is False
    res = S.run(end=hd, sessions=1, start=None, cache=_half_day_cache(tmp_path), rules=("session",), draws=50)
    assert res["skipped_half_days"] == [] and res["counts"]["sessions"] == 1


def test_a_short_walk_is_flagged_and_exits_non_zero(tmp_path):
    cache = S.Cache(tmp_path / "c", offline=True)
    _grouped(cache, PRIOR, {"TEST": {"c": PREV_CLOSE}})
    _grouped(cache, TODAY, {"TEST": {"h": 11.9, "l": 9.9, "v": 3e6}})
    res = S.run(end=date.fromisoformat(TODAY), sessions=3, start=None, cache=cache, rules=("session",), draws=50)
    assert res["sessions"] == {"requested": 3, "got": 1, "studied": 1, "short": True}
    assert "SHORT WALK" in S.render_md(res, ("session",))
    argv = ["--cache", str(tmp_path / "c"), "--out", str(tmp_path / "o"), "--offline", "--force", "--draws", "50",
            "--end", TODAY, "--sessions", "3"]
    assert S.main(argv) == 3                                         # NEGATIVE short without --allow-short
    meta = json.loads((tmp_path / "o" / "report.json").read_text())["meta"]
    assert meta["sessions"]["short"] is True and meta["sessions"]["got"] == 1   # the outputs are still written
    assert S.main(argv + ["--allow-short"]) == 0
    full = S.run(end=date.fromisoformat(TODAY), sessions=1, start=None, cache=cache, rules=("session",), draws=50)
    assert full["sessions"]["short"] is False                        # NEGATIVE a complete walk is not short


# ── method v2 (2026-10-14, pre-registered before run 2): the run-1 critic's B1 / M1 / M2 / M3 / m1 / m2 ──────────────
def _ev(fill="10:20", risk_pct=4.52, trigger=10.0, window="rth", symbol="EV", setup="bull_flag", entry="10:25"):
    return {"session": TODAY, "window": window, "setup": setup, "symbol": symbol, "entry_bar_t": f"{TODAY} {entry}",
            "fill_t": f"{TODAY} {fill}", "risk_pct": risk_pct, "trigger": trigger,
            "stop": trigger * (1 - (risk_pct or 4.52) / 100)}


def test_v2_placebo_stop_is_risk_matched_never_the_bar_low():
    res = run(zigzag_day())
    assert res["setup_free"] is True and res["pool"] and res["pool_ctx"] is not None
    rows, cnt = S.sample_placebo_v2([_ev(fill="11:01")], res["pool"], {"TEST": res["pool_ctx"]})
    assert rows and cnt["placebo_match_hour"] == 1
    for r in rows:
        assert r["stop"] == pytest.approx(r["trigger"] * (1 - 4.52 / 100))      # trigger × (1 − event risk_pct)
        assert r["stop"] != r["bar_low"] and r["risk_pct"] == pytest.approx(4.52)   # NEGATIVE never the bar's low
        assert r["matched_risk_pct"] == pytest.approx(4.52)
    v1 = S.placebo_pool("TEST", TODAY, *_zig_frames())
    assert v1 and all(r["stop"] == r["bar_low"] for r in v1)                      # v1 (run 1) stays reproducible
    no_rp = dict(_ev(fill="11:01"), risk_pct=None, trigger=10.0, stop=9.0)        # NEGATIVE missing risk_pct → recomputed
    rows2, _ = S.sample_placebo_v2([no_rp], res["pool"], {"TEST": res["pool_ctx"]})
    assert all(r["stop"] == pytest.approx(r["trigger"] * 0.9) for r in rows2)


def _zig_frames():
    from chart_maps.gajjala.bars import build_frames
    today = S.day_minutes(zigzag_day(), TODAY)
    everything = S.utc_naive(S.session_bounds(TODAY)["ah_close"]) + pd.Timedelta(days=1)
    f5 = build_frames("TEST", date.fromisoformat(TODAY), everything, prev_day(), today).f5
    q = S.qualification_minute(today, PREV_CLOSE)
    return f5, today, q, S.ema_exit_map(f5)


def _path_day():
    """One tape for every name: the 10:00 minute breaks 10.00, a rise to 10.40, a slide to 9.70 by 10:40, flat to the
    close. At a 5% stop (9.50) it ends −0.6R / −3%; at a 2% stop (9.80, the bar's low) it is stopped: −1R / −2%."""
    rows = [(9.96, 10.05, 9.96, 10.02), (10.02, 10.1, 10.0, 10.08), (10.08, 10.15, 10.05, 10.12),
            (10.12, 10.2, 10.1, 10.15), (10.15, 10.2, 10.12, 10.18)]
    rows += [(10.18 + i * 0.01, 10.2 + i * 0.01, 10.17 + i * 0.01, 10.19 + i * 0.01) for i in range(20)]   # ≤ 10.40
    rows += [(10.39 - i * 0.035, 10.39 - i * 0.035, 10.355 - i * 0.035, 10.355 - i * 0.035) for i in range(20)]
    rows = [tuple(min(x, 10.4) for x in r) for r in rows]
    rows += [(9.7, 9.7, 9.7, 9.7)] * (6 * 60 - len(rows))
    return mins_df(rows, "10:00")


def _cands(today, n=5, low=9.8, hhmm="10:00"):
    t = S.utc_naive(_bt(hhmm))
    bucket = today[(today.index >= t) & (today.index < t + pd.Timedelta(minutes=5))]
    rows = [tuple(map(float, r)) + (1.0,) for r in bucket[["open", "high", "low", "close"]].itertuples(index=False)]
    lab = t + pd.Timedelta(minutes=5)
    return [{"symbol": f"P{i}", "session": TODAY, "bar_t": f"{TODAY} {hhmm}", "entry_bar_t": S.et_of(lab).strftime(
        "%Y-%m-%d %H:%M"), "trigger": 10.0, "bar_low": low, "window": "rth", "break_t": f"{TODAY} {hhmm}",
        "break_ts": t, "entry_label": lab, "entry_low": float(bucket["low"].min()), "rows": rows} for i in range(n)]


def _event_on(today, risk_pct=5.0):
    trigger = 10.0
    stop = trigger * (1 - risk_pct / 100)
    fill = S.utc_naive(_bt("10:00"))
    rec = {"session": TODAY, "window": "rth", "setup": "bull_flag", "symbol": "EV", "entry_bar_t": f"{TODAY} 10:05",
           "fill_t": f"{TODAY} 10:00", "risk_pct": risk_pct, "trigger": trigger, "stop": stop}
    rec = S._flat(rec, S.trade_outcomes(today, fill, trigger, stop, TODAY, "rth", {}, "aplus"), trigger)
    rec.update(S.push_outcomes(today, S.utc_naive(_bt("10:05")), stop, TODAY, "rth", {}))
    return rec


def test_v2_tighter_placebo_stops_read_zero_delta_where_v1_reads_an_edge():
    """The run-1 artefact in miniature: event and placebo trade the SAME tape; only the placebo's stop is tighter (its
    bar's low, 2% vs the event's 5%). v1 manufactures +0.4R of 'edge' (and −1% in return); v2 reads 0."""
    today = _path_day()
    ev = _event_on(today)
    assert ev["r_session"] == pytest.approx(-0.6) and ev["pct_session"] == pytest.approx(-3.0)
    cands = _cands(today)
    ctx = {c["symbol"]: {"today": today, "ema_exit": {}} for c in cands}
    pool_v1 = [S.placebo_trade(c, today, {}, c["bar_low"], push=False) for c in cands]
    pl_v1, _ = S.sample_placebo([ev], {(TODAY, "rth"): pool_v1})
    pl_v2, cnt = S.sample_placebo_v2([ev], cands, ctx)
    assert len(pl_v2) == 5 and cnt["placebo_match_hour"] == 1
    c1 = S.compare([ev], pl_v1, "session", method="v1", draws=50)
    c2 = S.compare([ev], pl_v2, "session", method="v2", draws=50)
    assert c1["delta_mean_r"] == pytest.approx(0.4) and c1["delta_mean_pct"] == pytest.approx(-1.0)   # NEGATIVE v1
    assert c2["delta_mean_r"] == pytest.approx(0.0, abs=1e-9) and c2["delta_trim_r"] == pytest.approx(0.0, abs=1e-9)
    assert c2["delta_mean_pct"] == pytest.approx(0.0, abs=1e-9)
    for rule in GC.STUDY_EXIT_RULES:
        assert S.compare([ev], pl_v2, rule, method="v2", draws=50)["delta_mean_r"] == pytest.approx(0.0, abs=1e-9)
        assert S.compare([ev], pl_v2, rule, fill="push", method="v2", draws=50)["delta_mean_r"] == \
            pytest.approx(0.0, abs=1e-9)


def test_push_fill_is_the_first_minute_open_at_or_after_pass_plus_settle():
    e = [x for x in run(flag_day())["events"] if x["setup"] == "bull_flag"][0]
    assert e["pass_t"] == f"{TODAY} 10:15" and e["push_status"] == "ok"
    assert e["push_fill_t"] == f"{TODAY} 10:16" and e["push_fill_px"] == 11.15       # 10:15:30 → the 10:16 open
    assert e["r_push_session"] == pytest.approx((11.75 - 11.15) / (11.15 - STOP))     # risk from the fill, same stop
    assert e["push_risk_pct"] == pytest.approx((11.15 - STOP) / 11.15 * 100)
    assert e["pct_session"] == pytest.approx((11.75 / TRIGGER - 1) * 100)
    L = S.utc_naive(_bt("10:00"))
    m = mins_df([(10.0, 10.1, 9.9, 10.0), (10.2, 10.3, 10.1, 10.2)], "10:00")
    assert S.push_fill(m, L, END) == ("ok", L + S.ONE_MIN, 10.2)                    # NEGATIVE the minute AT the pass
    assert S.push_fill(m, L + S.ONE_MIN * 5, END)[0] == "fill_minute_missing"        # NEGATIVE no minute left
    assert S.push_fill(m, L, L + S.ONE_MIN)[0] == "after_session_end"


def _v2_cache(tmp_path, test_day):
    cache = S.Cache(tmp_path, offline=True)
    _grouped(cache, PRIOR, {"TEST": {"c": PREV_CLOSE}, "ZIG": {"c": PREV_CLOSE}})
    _grouped(cache, TODAY, {"TEST": {"h": 11.9, "l": 9.9, "v": 3e6}, "ZIG": {"h": 11.0, "l": 9.9, "v": 7e6}})
    for sym, df in (("TEST", test_day), ("ZIG", zigzag_day())):
        _put_day(cache, sym, TODAY, df)
        _put_day(cache, sym, PRIOR, prev_day())
    return cache


def test_negative_a_push_fill_under_the_stop_is_dropped_and_counted(tmp_path):
    bad = flag_day(after=[(11.2, 11.25, 10.5, 10.6, 90_000)] + [quiet(10.6)] * 60)   # 10:16 opens 10.50 < 10.8125
    res = S.run(end=date.fromisoformat(TODAY), sessions=1, start=None, cache=_v2_cache(tmp_path, bad),
                rules=GC.STUDY_EXIT_RULES, draws=50)
    e = [x for x in res["events"] if x["setup"] == "bull_flag"][0]
    assert e["push_status"] == "under_stop" and e["r_push_session"] is None and e["r_session"] == -1.0
    assert res["counts"]["push_fill_under_stop"] == 1
    rep = res["report"]
    assert rep["by_setup"]["bull_flag"]["session"]["events"]["n"] == 1                  # the trigger fill keeps it
    assert rep["by_setup_push"]["bull_flag"]["session"]["events"]["n"] == 0             # the push fill drops it
    assert rep["push_status"]["bull_flag"] == {"under_stop": 1}
    md = S.render_md(res, GC.STUDY_EXIT_RULES)
    assert "under the stop (dropped) 1" in md and "| push |" in md and "(flip row)" in md


def test_v2_run_draws_hour_matched_risk_matched_placebo_and_v1_reproduces_run_1(tmp_path):
    cache = _v2_cache(tmp_path, flag_day())
    v2 = S.run(end=date.fromisoformat(TODAY), sessions=1, start=None, cache=cache, rules=("session",), draws=50)
    assert v2["method"] == "v2" and v2["placebo"] and all(p["symbol"] == "ZIG" for p in v2["placebo"])
    ev = {e["setup"]: e for e in v2["events"]}
    for p in v2["placebo"]:
        assert p["stop"] == pytest.approx(p["trigger"] * (1 - ev[p["setup"]]["risk_pct"] / 100))
        assert p["time_match"] in ("hour", "fallback") and "rows" not in p and "break_ts" not in p
    c = v2["counts"]
    assert c["placebo_match_hour"] >= 1
    assert sum(c.get(k, 0) for k in ("placebo_match_hour", "placebo_match_fallback", "placebo_missing")) == \
        len(v2["events"])
    v1 = S.run(end=date.fromisoformat(TODAY), sessions=1, start=None, cache=cache, rules=("session",), draws=50,
               method="v1")
    assert v1["placebo"] and all(p["stop"] == p["bar_low"] for p in v1["placebo"])     # NEGATIVE run 1's stop
    assert "by_setup_push" not in v1["report"] and v1["report"]["flip_fill"] == "trigger"
    assert "by_setup_push" in v2["report"] and v2["report"]["flip_fill"] == "push"
    with pytest.raises(ValueError):
        S.run(end=date.fromisoformat(TODAY), sessions=1, start=None, cache=cache, rules=("session",), method="v3")


def test_hour_bucket_matching_with_counted_fallbacks():
    today = mins_df([(10.02, 10.05, 10.0, 10.02)] * 390, "09:30")
    def cand(hhmm, window="rth", sym=None):
        c = _cands(today, n=1, hhmm=hhmm)[0]
        return dict(c, symbol=sym or f"C{hhmm}", window=window)
    c10, c11, c13, ah10 = cand("10:05"), cand("11:10"), cand("13:00"), cand("10:10", window="ah", sym="AH")
    ctx = {c["symbol"]: {"today": today, "ema_exit": {}} for c in (c10, c11, c13, ah10)}
    ev = _ev(fill="10:20")
    rows, cnt = S.sample_placebo_v2([ev], [c10, c11, c13, ah10], ctx)
    assert [r["symbol"] for r in rows] == ["C10:05"] and cnt == {"placebo_match_hour": 1, "placebo_push_ok": 1}
    rows, cnt = S.sample_placebo_v2([ev], [c11, c13, ah10], ctx)                    # hour 10 empty → ±60 min
    assert [(r["symbol"], r["time_match"]) for r in rows] == [("C11:10", "fallback")]
    assert cnt["placebo_match_fallback"] == 1
    rows, cnt = S.sample_placebo_v2([ev], [c13, ah10], ctx)                         # NEGATIVE 160 min away, other window
    assert rows == [] and cnt == {"placebo_missing": 1}


def test_trimmed_winsorized_median_columns_and_the_v2_verdict_reads_the_trimmed_delta():
    vals = list(range(1, 100)) + [1000]
    assert S.trim_mean(vals) == pytest.approx(50.5) and S.winsor_mean(vals) == pytest.approx(50.5)
    assert np.mean(vals) == pytest.approx(59.5)
    lop = list(range(1, 99)) + [1000]                                               # n = 99: g = 0.99 row per tail
    assert S.trim_mean(lop) == pytest.approx((0.01 * 1 + sum(range(2, 99)) + 0.01 * 1000) / (99 - 2 * 0.99))
    assert S.trim_mean(lop) < np.mean(lop) - 9                                      # NEGATIVE n < 100 still trims
    rng = np.random.default_rng(5)
    ev = [{"session": f"d{d}", "symbol": f"E{d}_{k}", "setup": "bull_flag", "r_session": float(rng.normal(1.0, 0.3)),
           "exit_session": "x", "mfe_session": 1.0, "pct_session": 1.0} for d in range(40) for k in range(10)]
    ev[7]["r_session"] = -1e4                                                       # one catastrophic tail row
    pl = [{"session": f"d{d}", "symbol": f"P{d}_{k}", "setup": "bull_flag", "r_session": float(rng.normal(0.0, 0.3)),
           "exit_session": "stop", "mfe_session": 0.0, "pct_session": 0.0} for d in range(40) for k in range(10)]
    for x in ev + pl:                                                               # the push fill: no edge at all
        x.update(r_push_session=float(rng.normal(0.0, 0.3)), exit_push_session="x", mfe_push_session=0.0,
                 pct_push_session=0.0)
    v2 = S.compare(ev, pl, "session", method="v2", draws=400)
    v1 = S.compare(ev, pl, "session", method="v1", draws=400)
    assert set(v2["events"]) >= {"trim_mean_r", "winsor_mean_r", "median_r", "mean_pct", "trim_mean_pct"}
    assert set(v2) >= {"delta_trim_r", "delta_trim_ci_date", "delta_trim_ci_symbol", "delta_winsor_r",
                       "delta_median_r", "delta_mean_pct", "delta_pct_ci_date", "delta_trim_pct"}
    assert v2["verdict_on"] == "trim_mean" and v2["verdict"] == v2["verdict_trim"] == "measured_edge"
    assert v2["delta_trim_ci_date"][0] > 0 and v2["delta_trim_ci_symbol"][0] > 0
    assert v1["verdict"] == v2["verdict_mean"] == "no_signal"                       # NEGATIVE the mean is tail-driven
    rep = S.build_report(ev, pl, ("session",), method="v2", draws=200)
    assert rep["by_setup"]["bull_flag"]["session"]["verdict"] == "measured_edge"    # trigger row, comparison only
    assert rep["flip"]["bull_flag"]["session"] == rep["by_setup_push"]["bull_flag"]["session"]["verdict"] \
        == "no_signal"                                                               # the flip reads the PUSH row
    assert "verdict rule" in S.render_md({"report": rep, "method": "v2"}, ("session",))


def test_main_writes_the_method_and_the_preregistered_rule_into_meta(tmp_path):
    base = ["--cache", str(tmp_path / "c"), "--offline", "--force", "--draws", "50", "--allow-short"]
    assert S.main(base + ["--out", str(tmp_path / "o")]) == 0
    meta = json.loads((tmp_path / "o" / "report.json").read_text())["meta"]
    assert meta["method"] == "v2" and meta["verdict_rule"] == S.VERDICT_RULE["v2"] and meta["flip_fill"] == "push"
    assert "TRIMMED" in meta["verdict_rule"] and meta["method_v2"]["trim_frac"] == S.STUDY_TRIM_FRAC
    assert "ungated structure" in meta["reversal_squeeze_rows"]
    assert S.main(base + ["--out", str(tmp_path / "o1"), "--method", "v1"]) == 0
    meta1 = json.loads((tmp_path / "o1" / "report.json").read_text())["meta"]
    assert meta1["method"] == "v1" and meta1["verdict_rule"] == S.VERDICT_RULE["v1"]
    md = (tmp_path / "o" / "report.md").read_text()
    assert S.RS_ROW_LABEL in md and "ungated structure" in md                       # m2 label on the 🎾 rows


def test_v2_method_numbers_stay_out_of_his_constants():
    assert (S.STUDY_TRIM_FRAC, S.STUDY_PLACEBO_FALLBACK_MIN, S.DEFAULT_METHOD) == (0.01, 60, "v2")
    assert not any(n.startswith(("STUDY_TRIM", "STUDY_PLACEBO")) for n in dir(GC))
    assert (GC.K3_VOL_FRAC, GC.K6_TIGHT_PCT, GC.K4_HF_BASE_MIN) == (0.50, 8.0, 6)    # his numbers untouched


def _hf_day(base_n=3, wide=True, tail=20):
    """A 2-bar demand leg, then a TIGHT base of `base_n` bars; `wide` then prints a bar that stretches the base past
    K6_TIGHT_PCT of price."""
    bars = [quiet(10.0)] * 4 + [D1, D2] + [quiet(10.95)] * base_n
    if wide:
        bars += [(10.95, 11.0, 9.9, 10.0, 100_000)] + [quiet(10.0)] * tail
    return day(TODAY, "09:30", bars)


def test_hf_replay_reports_the_longest_base_and_the_first_failing_rule():
    best, diag = EX.replay_day_full("HF", TODAY, prev_day(), _hf_day())
    assert best["horizontal_fade"]["reason"] == f"base 0 of {GC.K4_HF_BASE_MIN} bars"      # run 1's hidden symptom
    d = diag["horizontal_fade"]
    assert (d["longest"], d["longest_unit"], d["first_fail"]) == (3, "base bars", "k6_tight")
    assert d["longest_at"] == f"{TODAY} 10:15" and d["longest_state"] == "forming"
    assert EX.replay_day("HF", TODAY, prev_day(), _hf_day()).keys() == best.keys()       # old API unchanged
    _b, alive = EX.replay_day_full("HF", TODAY, prev_day(), _hf_day(base_n=5, wide=False))
    assert alive["horizontal_fade"]["longest"] == 5 and alive["horizontal_fade"]["first_fail"] == ""   # NEGATIVE


def test_examples_rows_and_table_carry_the_longest_structure_columns(tmp_path):
    cache = S.Cache(tmp_path, offline=True)
    _put_day(cache, "HFX", TODAY, _hf_day())
    _put_day(cache, "HFX", PRIOR, prev_day())
    _daily(cache, "HFX", TODAY, PRIOR, PREV_CLOSE)
    ex = ({"ticker": "HFX", "date": TODAY, "setup": "horizontal_fade", "label": "valid", "frame": "5m"},)
    rows = EX.replay_examples(cache, ex)
    shipped = [r for r in rows if r["setting"] == "shipped"][0]
    assert (shipped["longest"], shipped["first_fail"], shipped["best_state"]) == (3, "k6_tight", "forming")
    md = EX.render_md(rows)
    assert "longest reached" in md and "3 base bars (5m) @" in md and "| k6_tight |" in md
    unverified = EX.render_md([dict(shipped, status="date unverified", longest=None, first_fail=None)])
    assert "| — | — |" in unverified                                                  # NEGATIVE no replay → no claim


def test_first_failing_rule_names_an_invalid_reason():
    assert EX.first_failing_rule({"state": "invalid", "reason": "base wider than 8% of price"}) == "k6_tight"
    assert EX.first_failing_rule({"state": "partial", "missed": ["k2", "k3_vol"]}) == "k2"
    assert EX.first_failing_rule({"state": "forming", "missed": []}) is None
    assert EX.first_failing_rule({"state": "invalid", "reason": "something new"}) == "invalid: something new"


# ── critic round 2 (2026-10-14): an equal trim on both sides, the push row = what the push sends, mutant pins ──────
def _tail_rows(prefix, n_per_day, days, tail_every, rng):
    out = []
    for d in range(days):
        for k in range(n_per_day):
            r = -1.0 if rng.random() < 0.7 else float(rng.exponential(1.5))
            if (d * n_per_day + k) % tail_every == 0:
                r = 40.0
            out.append({"session": f"d{d}", "symbol": f"{prefix}{d}_{k}", "setup": "kiss_fly", "r_session": r,
                        "exit_session": "x", "mfe_session": 0.0, "pct_session": r, "r_push_session": r,
                        "exit_push_session": "x", "mfe_push_session": 0.0, "pct_push_session": r})
    return out


def _floor_trim(vals, frac=S.STUDY_TRIM_FRAC):
    a = np.sort(np.asarray(vals, dtype=float))
    k = int(np.floor(len(a) * frac + 1e-9))
    return float(a[k:len(a) - k].mean())


def test_the_trim_cuts_the_same_share_from_both_sides_whatever_their_n():
    """71 events against 50 placebo rows each, drawn from the SAME generator: the trimmed Δ must read the mean Δ, not
    +0.37R of edge from cutting 35 placebo rows a tail and none on the event side (critic round 2)."""
    rng = np.random.default_rng(1)
    ev, pl = _tail_rows("E", 1, 71, 24, rng), _tail_rows("P", 50, 71, 24, rng)
    c = S.compare(ev, pl, "session", fill="push", method="v2", draws=200)
    assert abs(c["delta_trim_r"]) < 0.1 and abs(c["delta_trim_r"] - c["delta_mean_r"]) < 0.05
    ev_r, pl_r = [x["r_session"] for x in ev], [x["r_session"] for x in pl]
    assert _floor_trim(ev_r) - _floor_trim(pl_r) > 0.3                              # NEGATIVE the whole-row floor
    rep = [dict(x, symbol=f"{x['symbol']}_{j}") for x in ev for j in range(50)]     # the events × 50: same shape
    c2 = S.compare(ev, rep, "session", fill="push", method="v2", draws=50)
    assert c2["delta_trim_r"] == pytest.approx(0.0, abs=1e-9) and c2["delta_winsor_r"] == pytest.approx(0.0, abs=1e-9)
    assert S.trim_mean(ev_r) == pytest.approx(S.trim_mean(ev_r * 50))
    assert S.winsor_mean(ev_r) == pytest.approx(S.winsor_mean(ev_r * 50))
    assert S.trim_mean([7.0]) == pytest.approx(7.0) and S.trim_mean([]) is None and S.winsor_mean([3.0, 5.0]) == pytest.approx(4.0)
    assert "FRACTIONAL" in S.VERDICT_RULE["v2"]


def test_a_non_aplus_event_is_off_the_push_row_and_kept_on_the_trigger_row():
    k = 4 + 4
    stopped = [(10.875, 10.9, 10.85, 10.9, 50_000), (10.9, 11.25, 10.85, 11.2, 50_000),
               (11.2, 11.2, 10.8, 10.82, 50_000), (10.82, 10.85, 10.82, 10.85, 50_000),
               (10.85, 10.9, 10.85, 10.9, 50_000)]
    ambiguous = [(10.875, 10.9, 10.85, 10.9, 50_000), (10.9, 11.25, 10.8, 11.2, 50_000)] + \
        [(11.2, 11.2, 11.2, 11.2, 50_000)] * 3
    for mins, cls in ((stopped, "stopped_in_bar"), (ambiguous, "ambiguous")):
        e = [x for x in run(flag_day(custom={k: mins}))["events"] if x["setup"] == "bull_flag"][0]
        assert e["entry_class"] == cls and e["push_status"] == S.NOT_APLUS
        assert e["r_session"] == pytest.approx(-1.0)                                # the trigger row keeps it
        assert all(e[f"r_push_{r}"] is None for r in GC.STUDY_EXIT_RULES) and e["push_fill_t"] is None
        rep = S.build_report([e], [], ("session",), method="v2", draws=20)
        assert rep["by_setup"]["bull_flag"]["session"]["events"]["n"] == 1
        assert rep["by_setup_push"]["bull_flag"]["session"]["events"]["n"] == 0
    ok = [x for x in run(flag_day())["events"] if x["setup"] == "bull_flag"][0]
    assert ok["entry_class"] == "aplus" and ok["push_status"] == "ok"               # NEGATIVE an A+ stays on it


def test_a_placebo_row_that_did_not_break_cleanly_is_off_the_push_row():
    flat = [(9.7, 9.7, 9.7, 9.7)] * 120
    after = [(10.0, 10.0, 9.4, 9.45)] + [(9.7, 9.7, 9.7, 9.7)] * 3                   # under 9.50 AFTER the break
    for first, rest, cls in (((9.96, 10.05, 9.96, 10.02), after, "break"),
                             ((9.96, 10.05, 9.4, 10.0), [(10.0, 10.0, 10.0, 10.0)] * 4, "ambiguous")):
        today = mins_df([first] + rest + flat, "10:00")
        c = _cands(today, n=1)[0]
        row = S.placebo_trade(c, today, {}, 9.5)
        assert row["entry_class"] == cls and row["push_status"] == S.NOT_APLUS
        assert row["r_session"] == pytest.approx(-1.0) and row["r_push_session"] is None
    today = _path_day()
    clean = S.placebo_trade(_cands(today, n=1)[0], today, {}, 9.5)
    assert clean["entry_class"] == "break" and clean["push_status"] == "ok"          # NEGATIVE a clean break stays
    assert clean["r_push_session"] is not None


def test_a_push_fill_opening_exactly_at_the_stop_is_under_the_stop():
    L = S.utc_naive(_bt("10:05"))
    today = mins_df([(9.5, 9.6, 9.5, 9.55)] + [(9.6, 9.6, 9.6, 9.6)] * 30, "10:06")
    rec = S.push_outcomes(today, L, 9.5, TODAY, "rth", {})
    assert rec["push_status"] == "under_stop" and rec["r_push_session"] is None
    above = mins_df([(9.51, 9.6, 9.51, 9.55)] + [(9.6, 9.6, 9.6, 9.6)] * 30, "10:06")
    assert S.push_outcomes(above, L, 9.5, TODAY, "rth", {})["push_status"] == "ok"   # NEGATIVE one tick above


def test_a_fill_minute_that_pierces_the_stop_is_minus_one_r_on_the_push_row():
    L = S.utc_naive(_bt("10:05"))
    today = mins_df([(10.0, 10.1, 9.4, 9.6)] + [(10.2, 10.2, 10.2, 10.2)] * 60, "10:06")
    rec = S.push_outcomes(today, L, 9.5, TODAY, "rth", {})
    assert rec["push_fill_px"] == 10.0 and rec["push_fill_t"] == f"{TODAY} 10:06"
    assert all(rec[f"r_push_{r}"] == pytest.approx(-1.0) and rec[f"exit_push_{r}"] == "stop"
               for r in GC.STUDY_EXIT_RULES)
    held = mins_df([(10.0, 10.1, 9.6, 9.8)] + [(10.2, 10.2, 10.2, 10.2)] * 60, "10:06")
    assert S.push_outcomes(held, L, 9.5, TODAY, "rth", {})["r_push_session"] > 0     # NEGATIVE the low held


def test_a_candidate_stopped_before_its_break_is_never_drawn_and_the_run_survives():
    today = mins_df([(9.96, 9.98, 9.4, 9.6), (9.6, 10.05, 9.6, 10.02)] + [(10.0, 10.0, 10.0, 10.0)] * 120, "10:00")
    c = _cands(today, n=1)[0]
    assert S.placebo_trade(c, today, {}, 9.5) is None                               # the stop printed first
    rows, cnt = S.sample_placebo_v2([_ev(fill="10:02", risk_pct=5.0)], [c], {c["symbol"]: {"today": today,
                                                                                           "ema_exit": {}}})
    assert rows == [] and cnt == {"placebo_missing": 1}
    rows, cnt = S.sample_placebo_v2([_ev(fill="10:02", risk_pct=8.0)], [c], {c["symbol"]: {"today": today,
                                                                                           "ema_exit": {}}})
    assert len(rows) == 1 and cnt["placebo_match_hour"] == 1                        # NEGATIVE a wider stop held


def _rd(s_t, bars, at, state="forming", missed=None, reason=""):
    return {"leg": {"s_t": s_t}, "base": {"bars": bars}, "frame": "5m", "as_of_bar_t": at, "state": state,
            "missed": missed or [], "reason": reason, "ready": False, "broke": state in ("aplus", "triggered")}


def _longest(passes):
    L = EX.Longest()
    for reads in passes:
        L.next_pass()
        for r in reads:
            L.see("horizontal_fade", r)
    return L.result()["horizontal_fade"]


def test_longest_says_superseded_never_alive_when_a_new_leg_replaced_the_structure():
    a, b = "2026-10-13 10:00", "2026-10-13 10:30"
    sup = _longest([[_rd(a, 3, "10:20")], [_rd(b, 2, "10:35")], [_rd(b, 2, "10:40")]])
    assert (sup["longest"], sup["longest_at"], sup["first_fail"], sup["longest_end"]) == (3, "10:20", "", "superseded")
    alive = _longest([[_rd(a, 3, "10:20")], [_rd(a, 3, "10:25")]])
    assert alive["longest_end"] == "alive_at_close"                                 # NEGATIVE read at the last pass
    tie_fail = _longest([[_rd(a, 3, "10:20")], [_rd(b, 3, "10:45")],
                         [_rd(b, 3, "10:50", state="invalid", reason="base wider than 8% of price")]])
    assert (tie_fail["longest_at"], tie_fail["first_fail"], tie_fail["longest_end"]) == ("10:45", "k6_tight", None)
    tie_late = _longest([[_rd(a, 3, "10:20")], [_rd(b, 3, "10:45")]])
    assert (tie_late["longest_at"], tie_late["longest_end"]) == ("10:45", "alive_at_close")   # the LATEST on a tie
    broke = _longest([[_rd(a, 3, "10:20")], [_rd(a, 3, "10:25", state="aplus")], [_rd(b, 1, "10:40")]])
    assert broke["longest_end"] == "broke"
    row = {"ticker": "X", "date": TODAY, "his_label": "valid", "setting": "shipped", "setup": "horizontal_fade",
           "best_state": "forming", "entry_bar_t": None, "trigger": None, "stop": None, "missed": "", "longest": 3,
           "longest_unit": "base bars", "longest_frame": "5m", "longest_at": "10:20", "status": "replayed",
           "reason": "", "float_gate": ""}
    md = EX.render_md([dict(row, first_fail="", longest_end="superseded"),
                       dict(row, first_fail="", longest_end="alive_at_close")])
    assert "none (superseded by a new leg)" in md and "none (alive at the close)" in md
    assert "alive at the close / broke" not in md


def test_hf_replay_end_of_the_longest_structure():
    _b, d = EX.replay_day_full("HF", TODAY, prev_day(), _hf_day())
    assert d["horizontal_fade"]["first_fail"] == "k6_tight" and d["horizontal_fade"]["longest_end"] is None
    _b, alive = EX.replay_day_full("HF", TODAY, prev_day(), _hf_day(base_n=5, wide=False))
    assert alive["horizontal_fade"]["longest_end"] == "alive_at_close"
