"""🌀 Raid-low entry STUDY — pure-function tests (2026-09-24).

Ajay 2026-09-17: "I am rely on manipulation.. I wanna use that as an entry the
bottom of manipulation"; 2026-09-24: "yes please build raid low".

The script (`scripts/amd_raid_low_study.py`) measures HIS rule: a buy limit at
the raid low after the raid bar closes. These tests pin the order mechanics
(strict fill, no cancel, fill-bar conservatism, stop-first ties, terminal
rows), the point-in-time walk (future invariance, history independence), the
placebo draw, the statistics and the mechanical verdict. NEGATIVE cases are
marked (N). No test touches Mongo: every data read is monkeypatched.
"""
from __future__ import annotations

import ast
import json
import math
import os
import pathlib
import re
from concurrent.futures.process import BrokenProcessPool

import numpy as np
import pandas as pd
import pytest

from scripts import amd_raid_low_study as S
from scripts import turning_bullish_amd_study as AS
from supply_demand import alert_gates as AG
from supply_demand import amd as A
from supply_demand import turning_bullish as TB
from rotation import tracker as RT

BACKEND = pathlib.Path(__file__).resolve().parents[1]
SRC = (BACKEND / "scripts" / "amd_raid_low_study.py").read_text()
FIX = BACKEND / "tests" / "fixtures" / "amd_orcl_daily_2026_09_23.json"

L, E, T = 95.0, 96.0, 110.0
S0 = L * (1 - S.STOP_PCT / 100.0)
W, H = S.ORDER_WINDOW, S.HOLD


# ─────────────────────────────────────────── builders
def flat(n, px=100.0):
    """n flat bars o=c=px, h=px+1, l=px-1 (never near L, S0 or T)."""
    return ([px] * n, [px + 1.0] * n, [px - 1.0] * n, [px] * n)


def setbar(arrs, i, o=None, h=None, l=None, c=None):
    for arr, v in zip(arrs, (o, h, l, c)):
        if v is not None:
            arr[i] = v


def raid_frame(n):
    """Bar 0 is the raid bar: low == L, close back above E."""
    arrs = flat(n)
    setbar(arrs, 0, o=100.0, h=101.0, l=L, c=100.0)
    return arrs


def np_(arrs):
    return tuple(np.asarray(a, dtype=float) for a in arrs)


def lim(arrs, t=0, level=L, stop=S0, target=T, **kw):
    o, h, l, c = np_(arrs)
    kw.setdefault("window", W)
    kw.setdefault("hold", H)
    kw.setdefault("ended", False)
    return S.simulate_limit(o, h, l, c, t, level, stop, target, **kw)


def orcl(scale=1.0):
    bars = json.loads(FIX.read_text())["bars"]
    return pd.DataFrame({"open": [b["o"] * scale for b in bars],
                         "high": [b["h"] * scale for b in bars],
                         "low": [b["l"] * scale for b in bars],
                         "close": [b["c"] * scale for b in bars],
                         "volume": [b["v"] for b in bars]},
                        index=pd.DatetimeIndex([b["t"] for b in bars]))


def dated(c, h, l, start="2024-01-02"):
    n = len(c)
    return pd.DataFrame({"open": c, "high": h, "low": l, "close": c, "volume": [1e6] * n},
                        index=pd.bdate_range(start, periods=n))


def chain_frame(seg=35, nseg=6, step=0.1, wick=0.2):
    """A staircase of bases, each raided a little deeper than the last, so every
    base spans the previous raid: one long re-sweep chain (> 120 bars)."""
    c, h, l = [], [], []
    for k in range(nseg):
        base = 100.0 - k * step
        for i in range(seg - 1):
            x = base + (i % 3) * 0.4
            c.append(x); h.append(x + 0.5); l.append(x - 0.5)
        w = min(min(l[-seg * 3:]), base - 0.5) - wick
        x = base + 0.1
        c.append(x); h.append(x + 0.5); l.append(w)
    for i in range(10):
        x = 100.0 - nseg * step + (i % 3) * 0.4
        c.append(x); h.append(x + 0.5); l.append(x - 0.5)
    return dated(c, h, l)


def base60_frame():
    """A 60-bar base raided on bar 60."""
    c = [100.0 + (i % 3) * 0.4 for i in range(60)]
    h = [x + 0.5 for x in c]
    l = [x - 0.5 for x in c]
    c.append(100.1); h.append(100.6); l.append(98.8)
    for i in range(5):
        c.append(100.2); h.append(100.7); l.append(99.8)
    return dated(c, h, l)


# ═════════════════════════════════════════ 1-13 order mechanics
def test_01_strict_fill_exact_touch_is_not_a_fill_but_a_trade_through_is():
    a = raid_frame(40)
    setbar(a, 1, l=L)
    r = lim(a)
    assert not r["filled"] and r["why"] == "unfilled"                    # (N)
    assert lim(a, strict=False)["filled"]                                # FT: touch fills
    b = raid_frame(40)
    setbar(b, 1, l=L - 0.1)
    r = lim(b)
    assert r["filled"] and r["fill_px"] == L and r["fill_idx"] == 1


def test_02_gap_below_the_level_fills_at_the_open():
    a = raid_frame(40)
    setbar(a, 1, o=94.8, l=94.7)
    r = lim(a)
    assert r["filled"] and r["fill_px"] == 94.8


def test_03_gap_below_the_stop_is_gap_stop_with_zero_return():
    a = raid_frame(40)
    setbar(a, 1, o=94.0, h=94.2, l=93.5, c=94.1)
    r = lim(a)
    assert r["filled"] and r["why"] == "gap_stop" and r["ret"] == 0.0
    rates = S._why_rates(np.array([S.WHY.index(r["why"])]), np.array([True]))
    assert rates["gap_stop"] == 1.0                                       # in the stop-out rate


def test_04_window_off_by_one():
    a = raid_frame(40)
    setbar(a, W, l=L - 0.1)
    assert lim(a)["filled"] and lim(a)["delay"] == W
    b = raid_frame(40)
    setbar(b, W + 1, l=L - 0.1)
    assert not lim(b)["filled"]                                           # (N)


def test_05_never_fills_on_the_raid_bar_itself():
    a = raid_frame(40)
    setbar(a, 0, l=L - 5.0)                    # even a deeper print ON bar t is not a fill
    r = lim(a)
    assert not r["filled"] and r["fill_idx"] is None and r["why"] == "unfilled"


def test_06_no_cancel_in_the_primary_cancels_only_in_CX():
    a = raid_frame(40)
    setbar(a, 1, c=E - 0.5, l=E - 0.8)          # close under the edge, above L
    setbar(a, 2, l=L - 0.1)
    assert lim(a)["filled"]
    assert lim(a, cancel_above=T, cancel_below=E)["why"] == "cancelled"   # (N for CX)
    b = raid_frame(40)
    setbar(b, 1, c=T + 1, h=T + 1.5)            # close above the base top
    setbar(b, 2, o=100, l=L - 0.1)
    assert lim(b)["filled"]
    assert lim(b, cancel_above=T, cancel_below=E)["why"] == "cancelled"
    c_ = raid_frame(40)
    setbar(c_, 1, l=L - 0.1, c=E - 0.5)         # fill and a close < E on the same bar
    assert lim(c_)["filled"] and lim(c_, cancel_above=T, cancel_below=E)["filled"]


def test_07_stop_and_target_on_the_same_later_bar_is_a_stop():
    a = raid_frame(40)
    setbar(a, 1, l=L - 0.1)
    setbar(a, 3, h=T + 1, l=S0 - 0.1)
    r = lim(a)
    assert r["why"] == "stop" and r["exit_px"] == S0


def test_08_fill_bar_through_the_stop_stops_at_the_stop():
    a = raid_frame(40)
    setbar(a, 1, o=100.0, l=S0 - 0.2)
    r = lim(a)
    assert r["why"] == "stop" and r["exit_idx"] == 1
    assert r["ret"] == pytest.approx(S0 / L - 1.0)


def test_09_target_never_credited_on_the_fill_bar():
    a = raid_frame(40)
    setbar(a, 1, o=100.0, h=T + 2, l=L - 0.1)
    r = lim(a)
    assert r["why"] != "target" and r["why"] == "clock"                   # (N)


def test_10_later_gaps_exit_at_the_open():
    a = raid_frame(40)
    setbar(a, 1, l=L - 0.1)
    setbar(a, 4, o=93.0, h=93.5, l=92.0, c=93.2)
    r = lim(a)
    assert r["why"] == "stop" and r["exit_px"] == 93.0
    b = raid_frame(40)
    setbar(b, 1, l=L - 0.1)
    setbar(b, 4, o=112.0, h=113.0, l=111.0, c=112.5)
    r = lim(b)
    assert r["why"] == "target" and r["exit_px"] == 112.0


def test_11_clock_exit_and_complete_flag():
    n = 1 + W + H + 5
    a = raid_frame(n)
    setbar(a, 2, l=L - 0.1)
    setbar(a, 2 + H, c=101.5)
    r = lim(a)
    assert r["why"] == "clock" and r["exit_idx"] == 2 + H
    assert r["ret"] == pytest.approx(101.5 / L - 1.0)
    assert r["complete"] and r["evaluable"]
    short = raid_frame(W + H)                    # t + W + HOLD > n - 1
    assert not lim(short)["complete"]                                     # (N)


def test_12_terminal_rows_on_ended_frames():
    a = raid_frame(4)                            # fill on bar 1, frame ends 2 bars later
    setbar(a, 1, l=L - 0.1)
    setbar(a, 3, c=99.0)
    r = lim(a, ended=True)
    assert r["why"] == "terminal" and r["exit_idx"] == 3 and r["evaluable"]
    assert r["ret"] == pytest.approx(99.0 / L - 1.0)
    r2 = lim(a, ended=False)
    assert not r2["evaluable"] and r2["why"] is None                       # (N) open
    b = raid_frame(3)                            # ends inside the window, no print
    r3 = lim(b, ended=True)
    assert r3["why"] == "unfilled" and r3["evaluable"]                     # (N)


def test_12b_walk_symbol_flags_terminal_rows_only_on_ended_names(monkeypatch):
    df = _synthetic_names()["SYM0"]
    n = len(df)
    last = df.index[-1]
    monkeypatch.setattr(S, "load_closed", lambda s, a: (df, None))
    later = (last + pd.Timedelta(days=S.ENDED_GRACE_DAYS + 30)).strftime("%Y-%m-%d")
    _, err, p = S.walk_symbol("SYM0", later, True)
    assert err is None and p["meta"]["ended"]
    for side in ("ev", "pl"):
        c = p[side]
        near = c["t"].astype(np.int64) + W + H > n - 1
        assert near.any(), side
        assert c["terminal"][near].all() and c["evaluable"][near].all(), side
        assert not c["complete"][near].any(), side
        assert not c["terminal"][~near].any() and c["evaluable"][~near].all(), side
    _, err, q = S.walk_symbol("SYM0", last.strftime("%Y-%m-%d"), True)
    assert err is None and not q["meta"]["ended"]
    for side in ("ev", "pl"):
        c = q[side]
        near = c["t"].astype(np.int64) + W + H > n - 1
        assert not c["terminal"].any() and not c["evaluable"][near].any(), side          # (N) open


def test_12c_is_ended_grace_boundary():
    as_of = "2026-09-24"
    edge = (pd.Timestamp(as_of) - pd.Timedelta(days=S.ENDED_GRACE_DAYS)).strftime("%Y-%m-%d")
    before = (pd.Timestamp(edge) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    assert not S.is_ended(edge, as_of)                                    # (N) exactly the grace
    assert S.is_ended(before, as_of)
    assert not S.is_ended(as_of, as_of)                                   # (N)


def test_13_simulate_market_entries():
    n = H + 5
    a = raid_frame(n)
    o, h, l, c = np_(a)
    r = S.simulate_market(o, h, l, c, 0, entry="close", stop=S0, target=T, hold=H, ended=False)
    assert r["fill_px"] == 100.0 and r["exit_idx"] == H and r["why"] == "clock"
    b = raid_frame(n)
    setbar(b, 1, o=94.0)
    o, h, l, c = np_(b)
    r = S.simulate_market(o, h, l, c, 0, entry="next_open", stop=S0, target=T, hold=H, ended=False)
    assert r["why"] == "gap_skip" and not r["filled"]
    o, h, l, c = np_(a)
    r = S.simulate_market(o, h, l, c, 0, entry="next_open", stop=S0, target=T, hold=H, ended=False)
    assert r["fill_px"] == 100.0 and r["fill_idx"] == 1
    r = S.simulate_market(o, h, l, c, 0, entry="hindsight_low", stop=S0, target=T, hold=H, ended=False)
    assert r["fill_px"] == L and r["fill_idx"] == 0


# ═════════════════════════════════════════ 14-16 point in time
def _key(rows, fields):
    return [tuple((k, (round(r[k], 9) if isinstance(r[k], float) else r[k])) for k in fields)
            for r in rows]


def test_14_pit_walk_is_future_invariant():
    df = orcl()
    cut = 200
    ev0, pl0 = S.pit_walk(df)
    for f in (0.5, 1.5):
        alt = df.copy()
        alt.iloc[cut + 1:, :4] = alt.iloc[cut + 1:, :4] * f
        ev1, pl1 = S.pit_walk(alt)
        fe = ("t",) + S.RAID_FIELDS + ("atr", "delta", "rho", "nu")
        fp = ("t", "level", "close", "ob_lo", "ob_hi", "pos")
        assert _key([e for e in ev1 if e["t"] <= cut], fe) == _key([e for e in ev0 if e["t"] <= cut], fe)
        assert _key([p for p in pl1 if p["t"] <= cut], fp) == _key([p for p in pl0 if p["t"] <= cut], fp)
    assert any(e["t"] <= cut for e in ev0) and any(p["t"] <= cut for p in pl0)


def test_15_pit_walk_equals_the_detector_and_never_mislabels(monkeypatch):
    df = orcl()
    ev, _ = S.pit_walk(df)
    full = {r["idx"]: r for r in A.find_raids(df)["raids"] if r["idx"] >= S.WARMUP_PIT}
    assert sorted(full) == [e["t"] for e in ev] and ev
    for e in ev:
        assert S.raid_fields_equal(e, full[e["t"]])
    real = A.find_raids

    def lagged(frame, **kw):
        R = real(frame, **kw)
        for r in R["raids"]:
            r["idx"] = r["idx"] - 1                # the last row is never bar t
        return R
    monkeypatch.setattr(S.A, "find_raids", lagged)
    ev2, _ = S.pit_walk(df)
    assert ev2 == []                                                      # (N)


def test_16_history_independence_and_its_bounds():
    df = orcl()
    ev, _ = S.pit_walk(df)
    for t in range(S.WARMUP_PIT, len(df)):
        hc = S.history_check(df, t)
        assert hc["match"] and hc["open_base_match"], t
    assert ev
    b = base60_frame()
    t = 60
    assert A.find_raids(b)["raids"][-1]["idx"] == t
    assert not S.history_check(b, t, warmup=30)["match"]                  # (N) bound not vacuous
    cf = chain_frame()
    chained = [r for r in A.find_raids(cf)["raids"] if r["idx"] >= S.WARMUP_PIT]
    diffs = [S.history_check(cf, r["idx"]) for r in chained]
    assert all(d["match"] for d in diffs)                                 # (N) chain excluded
    assert any(d["chain_diff"] for d in diffs)                            # ...but counted


# ═════════════════════════════════════════ 17 source guard
def test_17_constants_are_imported_by_name():
    assert S.WARMUP_PIT == A.MAX_BASE_BARS + A.MAX_RAID_AGE
    assert S.ORDER_WINDOW is TB.MAX_RAID_BARS_AGO
    assert S.HOLD == AS.REACH_H
    assert S.STOP_PCT == AG.STOP_BUFFER_PCT
    assert S.BENCH is RT.BENCHMARK
    for name in ("WARMUP_PIT", "ORDER_WINDOW", "HOLD", "STOP_PCT", "BENCH", "STOP_ATR",
                 "STOP_ATR_FLOOR_PCT", "WINDOWS_SECONDARY", "PRICE_FLOOR"):
        assert not re.search(r"^%s\s*=\s*\(?\s*[-\d.\"']" % name, SRC, re.M), name
    assert S.WINDOWS_SECONDARY == (AS.BARS_AGO_MAX, A.MAX_MARKUP_BARS)


# ═════════════════════════════════════════ 18 pool rule
def _fake_R(t, *, raid=False, brk=False, ob=(90.0, 110.0)):
    rows = [{"idx": t, "date": "2025-01-01", "raid_level": 96.0, "raid_price": 95.0,
             "raid_close": 97.0, "depth_pct": 1.0, "vol_ratio": 1.0, "base_lo": 96.0,
             "base_hi": 110.0, "base_bars": 10, "base_date": "2024-12-01",
             "base_end_date": "2024-12-20", "sweep_seq": 1}] if raid else []
    return {"raids": rows, "last_break_base": {"lo": 1} if brk else None,
            "open_base": {"lo": ob[0], "hi": ob[1]} if ob else None, "n": t + 1}


def _pool_frame(n=130, low=92.0, close=95.0):
    c = [close] * n
    h = [close + 1] * n
    l = [low] * n
    return dated(c, h, l)


@pytest.mark.parametrize("kw,expect", [
    ({"raid": True}, 0), ({"brk": True}, 0), ({"ob": None}, 0), ({}, 1)])
def test_18_pool_rule(monkeypatch, kw, expect):
    df = _pool_frame()
    monkeypatch.setattr(S.A, "find_raids", lambda f, **k: _fake_R(len(f) - 1, **kw))
    ev, pool = S.pit_walk(df, warmup=len(df) - 1)
    assert len(pool) == expect
    if expect:
        assert pool[0]["level"] == 92.0 and pool[0]["ob_hi"] == 110.0
    if kw.get("raid"):
        assert len(ev) == 1                                               # (N) raid bar = event only


def test_18b_pool_rule_close_outside_and_upper_low_excluded(monkeypatch):
    monkeypatch.setattr(S.A, "find_raids", lambda f, **k: _fake_R(len(f) - 1))
    ev, pool = S.pit_walk(_pool_frame(close=111.0, low=92.0), warmup=129)
    assert pool == []                                                     # (N) close outside
    ev, pool = S.pit_walk(_pool_frame(close=105.0, low=97.0), warmup=129)
    assert pool == []                                                     # (N) pos 0.35 > 1/3
    ev, pool = S.pit_walk(_pool_frame(close=105.0, low=96.0), warmup=129)
    assert len(pool) == 1 and pool[0]["pos"] <= S.PLACEBO_LOWER_FRACTION


def test_18c_pool_order_is_strict_with_no_cancel():
    a = flat(40)
    setbar(a, 0, l=92.0, c=95.0)
    setbar(a, 1, l=92.0)                         # exact touch
    setbar(a, 2, o=100.0, h=112.0, l=100.0, c=111.0)   # a close over the base top, no print
    setbar(a, 3, l=91.9)
    o, h, l, c = np_(a)
    out = S.pool_arms(o, h, l, c, 1.0, {"t": 0, "level": 92.0, "ob_hi": 110.0}, 40, False)
    assert out["P_f"] == 1 and out["P_fd"] == 3                            # strict, no cancel
    assert out["P_FT_f"] == 1 and out["P_FT_fd"] == 1


# ═════════════════════════════════════════ 19-22 matching and stats helpers
def _ev_pl():
    ev = pd.DataFrame({"eid": [0, 1, 2], "sym": [0, 1, 2], "date": [1, 1, 5],
                       "dpos": [0, 0, 4], "cell": [3, 3, 7], "t": [200, 200, 300]})
    pl = pd.DataFrame({"pid": np.arange(8), "sym": [0, 1, 1, 3, 3, 0, 2, 2],
                       "date": [1, 1, 1, 1, 2, 1, 3, 9], "dpos": [0, 0, 0, 0, 1, 0, 2, 8],
                       "cell": [3, 3, 3, 3, 3, 9, 7, 7], "t": [200, 200, 150, 200, 100, 200, 250, 150]})
    return ev, pl


def test_19_draw_matched():
    ev, pl = _ev_pl()
    P1 = S.draw_matched(ev, pl, k=5, seed=1, same_symbol=False, widen=2, gap=24)
    psym = pl.set_index("pid")["sym"]
    esym = ev.set_index("eid")["sym"]
    for eid, pid in zip(P1["eid"], P1["pid"]):
        assert psym[pid] != esym[eid]                                     # (N) never own symbol
    d0 = P1[P1["eid"] == 0]
    assert len(d0) == 5 and set(d0["pid"]) <= {1, 2, 3} and (d0["kind"] == "exact").all()
    d1 = P1[P1["eid"] == 1]
    assert set(d1["pid"]) <= {0, 3}                                       # exact date AND cell
    assert P1.attrs["unmatched"] == [2]                                   # (N) only own-symbol rows
    again = S.draw_matched(ev, pl, k=5, seed=1, same_symbol=False, widen=2, gap=24)
    assert again["pid"].tolist() == P1["pid"].tolist()                    # same seed, same draws
    ps = S.draw_matched(ev, pl, k=5, seed=1, same_symbol=True, widen=0, gap=24)
    ppl = pl.set_index("pid")
    pev = ev.set_index("eid")
    for eid, pid in zip(ps["eid"], ps["pid"]):
        assert ppl.loc[pid, "sym"] == pev.loc[eid, "sym"]
        assert abs(ppl.loc[pid, "t"] - pev.loc[eid, "t"]) > 24            # (N) gap excluded
    assert set(ps[ps["eid"] == 1]["pid"]) == {2}
    assert ps.attrs["unmatched"] == [0]                                   # (N) pid 0 sits inside the gap


def test_19c_same_symbol_gap_boundary_is_exclusive():
    gap = W + H
    ev = pd.DataFrame({"eid": [0], "sym": [0], "date": [1], "dpos": [0], "cell": [3], "t": [500]})
    pl = pd.DataFrame({"pid": [0, 1, 2], "sym": [0, 0, 0], "date": [2, 3, 4], "dpos": [1, 2, 3],
                       "cell": [3, 3, 3], "t": [500 + gap, 500 - gap, 500 + gap + 1]})
    ps = S.draw_matched(ev, pl, k=5, seed=1, same_symbol=True, widen=0, gap=gap)
    assert set(ps["pid"]) == {2}                                          # (N) |t'-t| == gap excluded
    only = S.draw_matched(ev, pl.iloc[:2], k=5, seed=1, same_symbol=True, widen=0, gap=gap)
    assert only.attrs["unmatched"] == [0] and len(only) == 0              # (N)


def test_19b_widening_and_unmatched():
    ev = pd.DataFrame({"eid": [0, 1], "sym": [0, 0], "date": [1, 1], "dpos": [10, 40],
                       "cell": [4, 4], "t": [10, 10]})
    pl = pd.DataFrame({"pid": [0, 1], "sym": [1, 0], "date": [1, 1], "dpos": [12, 40],
                       "cell": [4, 4], "t": [0, 0]})
    P1 = S.draw_matched(ev, pl, k=5, seed=3, same_symbol=False, widen=2, gap=24)
    assert (P1[P1["eid"] == 0]["kind"] == "widened").all()
    assert set(P1[P1["eid"] == 0]["pid"]) == {0}                          # with replacement
    assert P1.attrs["unmatched"] == [1]                                   # (N) only own symbol
    none = S.draw_matched(ev, pl, k=5, seed=3, same_symbol=False, widen=0, gap=24)
    assert 0 in none.attrs["unmatched"]                                   # (N) no widening -> none


def test_20_bin_edges_and_cells():
    rng = np.random.default_rng(0)
    evd = pd.DataFrame({"delta": rng.random(300), "rho": rng.random(300), "nu": rng.random(300)})
    e = S.bin_edges(evd)
    assert len(e["delta"]) == 2 and len(e["rho"]) == 4 and len(e["nu"]) == 2
    cells = S.cell_of(evd["delta"], evd["rho"], evd["nu"], e)
    assert cells.min() >= 0 and cells.max() <= 44 and len(np.unique(cells)) > 30
    before = json.dumps(e)
    ext = S.cell_of([-9, 9], [-9, 9], [-9, 9], e)
    assert ext.tolist() == [0, 44] and json.dumps(e) == before           # (N) edges unchanged
    assert S.cell_of([np.nan], [0.5], [0.5], e).tolist() == [-1]


def test_21_smd():
    a = np.random.default_rng(1).normal(0, 1, 5000)
    assert S.smd(a, a) == 0.0
    assert abs(S.smd(a + 0.2, a)) > 0.1


def test_22_bench_returns():
    b = pd.DataFrame({"open": [100.0, 102.0, 104.0], "close": [101.0, 103.0, 106.0]},
                     index=pd.DatetimeIndex(["2026-01-05 04:00", "2026-01-06 00:00", "2026-01-07"]))
    r = S.bench_returns([20260105, 20260105, 0], [20260107, 20260108, 20260107], b)
    assert r[0] == pytest.approx(106.0 / 100.0 - 1.0)
    assert math.isnan(r[1]) and math.isnan(r[2])                          # (N) missing -> NaN


# ═════════════════════════════════════════ 23-25
def test_23_cap_as_of_and_digest():
    df = pd.DataFrame({"open": [1.0, 2.0, 3.0], "high": [1.0, 2.0, 3.0], "low": [1.0, 2.0, 3.0],
                       "close": [1.0, 2.0, 3.0], "volume": [1.0, 1.0, 1.0]},
                      index=pd.DatetimeIndex(["2026-09-23 00:00", "2026-09-24 04:00", "2026-09-25 00:00"]))
    cap = S.cap_as_of(df, "2026-09-24")
    assert len(cap) == 2 and cap.index[-1] == pd.Timestamp("2026-09-24 04:00")
    more = pd.concat([df, pd.DataFrame({"open": [9.0], "high": [9.0], "low": [9.0], "close": [9.0],
                                        "volume": [1.0]}, index=pd.DatetimeIndex(["2026-09-28"]))])
    assert S.bars_digest(S.cap_as_of(more, "2026-09-24")) == S.bars_digest(cap)   # (N)
    moved = df.copy()
    moved.iloc[1, 3] = 2.5
    assert S.bars_digest(S.cap_as_of(moved, "2026-09-24")) != S.bars_digest(cap)


def test_24_drop_one_block_exposes_a_single_block_lift():
    vals = np.r_[np.full(10, 5.0), np.zeros(30), np.zeros(40)]
    is_ev = np.r_[np.ones(40, bool), np.zeros(40, bool)]
    blk = np.r_[np.zeros(10), np.ones(30), np.zeros(10), np.ones(30)].astype(int)
    r = S.drop_one_block(vals, is_ev, ~is_ev, np.ones(80, bool), blk)
    assert r["per_block"][0] <= 0 and r["min"] <= 0 and r["argmin"] == 0
    assert r["per_block"][1] > 0


def test_25_bootstrap_intervals():
    rng = np.random.default_rng(2)
    n = 2000
    g = np.repeat(np.arange(200), 10)
    base = rng.normal(0, 1, n)
    other = rng.normal(0, 1, n)
    base, other = base - base.mean(), other - other.mean()     # a known difference, exactly
    groups = np.r_[g, g]
    ma = np.r_[np.ones(n, bool), np.zeros(n, bool)]
    r = S.boot_delta(np.r_[base + 1.0, other], ma, ~ma, groups, B=300)
    assert r["diff_ci"][0] < 1.0 < r["diff_ci"][1] and r["diff_ci"][0] > 0
    same = S.boot_delta(np.r_[base, other], ma, ~ma, groups, B=300)
    assert same["diff_ci"][0] < 0 < same["diff_ci"][1]                    # (N)
    m = S.boot_mean(base + 1.0, np.ones(n, bool), g, B=300)
    assert m["ci"][0] < 1.0 < m["ci"][1]


def test_25b_bootstrap_is_clustered_not_per_row():
    g = np.repeat(np.arange(4), 50)
    v = g.astype(float)                       # every row of a symbol identical
    m = np.ones(len(v), bool)
    cl = S.boot_mean(v, m, g, B=400)
    iid = S.boot_mean(v, m, np.arange(len(v)), B=400)
    w_cl = cl["ci"][1] - cl["ci"][0]
    w_iid = iid["ci"][1] - iid["ci"][0]
    assert w_iid > 0 and w_cl / w_iid > 3                                 # (N) per-row CI too tight
    ma = np.r_[m, np.zeros(len(v), bool)]
    vals = np.r_[v, np.zeros(len(v))]
    grp = np.r_[g, g]
    dc = S.boot_delta(vals, ma, ~ma, grp, B=400)["diff_ci"]
    di = S.boot_delta(vals, ma, ~ma, np.r_[np.arange(len(v)), np.arange(len(v)) + len(v)], B=400)["diff_ci"]
    assert (dc[1] - dc[0]) / (di[1] - di[0]) > 3                          # (N)


# ═════════════════════════════════════════ 26 verdict
def _res(**over):
    res = {"snapshot": {"ok": True}, "balance": {"balanced": True},
           "primary": {"diff_ci": [0.01, 0.03], "xs_ci": [0.005, 0.02], "matched_share": 0.95},
           "stability": {"date_h1": 0.01, "date_h2": 0.01, "sym_p0": 0.01, "sym_p1": 0.01,
                         "one_per_date": 0.01, "one_per_symbol": 0.01, "same_symbol": 0.01,
                         "drop_one_block": {"per_block": {0: 0.01, 1: 0.02}}},
           "survivorship": {"cache_all": {"diff": 0.01}}}
    for k, v in over.items():
        sect, key = k.split("__")
        res[sect][key] = v
    return res


def test_26_verdict_every_branch():
    assert S.verdict(_res())["status"] == "edge"
    assert S.verdict(_res(snapshot__ok=False))["status"] == "invalid_snapshot"           # (N)
    v = S.verdict(_res(balance__balanced=False))
    assert v["status"] == "no_signal" and "imbalanced" in v["tags"]                    # (N)
    v = S.verdict(_res(balance__balanced=False, primary__diff_ci=[-0.05, -0.01]))
    assert v["status"] != "inverted"                                                    # (N)
    assert S.verdict(_res(primary__diff_ci=[-0.05, -0.01]))["status"] == "inverted"
    v = S.verdict(_res(stability__date_h2=-0.001))
    assert v["status"] == "no_signal" and "fragile" in v["tags"]                       # (N)
    v = S.verdict(_res(stability__drop_one_block={"per_block": {0: 0.01, 1: 0.0}}))
    assert "fragile" in v["tags"]                                                       # (N)
    v = S.verdict(_res(primary__xs_ci=[-0.001, 0.02]))
    assert v["status"] == "no_signal" and v["tags"] == ["relative_only"]              # (N)
    v = S.verdict(_res(primary__diff_ci=[-0.001, 0.02]))
    assert "absolute_only" in v["tags"]
    v = S.verdict(_res(primary__matched_share=0.89))
    assert v["status"] == "no_signal" and v["tags"] == ["undermatched"]               # (N)
    v = S.verdict(_res(primary__diff_ci=[float("nan"), float("nan")]))
    assert v["status"] == "no_signal"                                                   # NaN never passes


def test_26b_verdict_same_symbol_cache_all_and_share_boundary():
    v = S.verdict(_res(stability__same_symbol=0.0))
    assert v["status"] == "no_signal" and "fragile" in v["tags"] and "e" in v["failed"]   # (N)
    v = S.verdict(_res(stability__same_symbol=-0.01))
    assert v["status"] == "no_signal" and "fragile" in v["tags"]                        # (N)
    v = S.verdict(_res(survivorship__cache_all={"diff": 0.0}))
    assert v["status"] == "no_signal" and "fragile" in v["tags"] and "f" in v["failed"]   # (N)
    v = S.verdict(_res(survivorship__cache_all={"diff": -0.01}))
    assert v["status"] == "no_signal" and "fragile" in v["tags"]                        # (N)
    v = S.verdict(_res(primary__matched_share=S.MIN_MATCHED_SHARE))
    assert v["status"] == "edge" and "undermatched" not in v["tags"]                     # boundary passes
    v = S.verdict(_res(primary__matched_share=S.MIN_MATCHED_SHARE - 1e-9))
    assert "undermatched" in v["tags"]                                                   # (N)


# ═════════════════════════════════════════ 27-30
class _DeadPool:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def map(self, fn, items):
        yield fn(items[0])
        raise BrokenProcessPool("worker killed")


def test_27_run_pool_exits_3_on_a_dead_worker():
    it = S.run_pool(lambda x: x * 2, [1, 2, 3], 2, executor_cls=_DeadPool)
    assert next(it) == 2
    with pytest.raises(SystemExit) as e:
        list(it)
    assert e.value.code == 3                                              # (N) no silent partial
    assert S.peak_rss_mb() > 0


def test_28_wording_and_headline_from_constants():
    assert "bounce" not in SRC.lower()                                    # (N)
    h = S.headline({})
    assert f"{S.ORDER_WINDOW} sessions" in h and f"{S.STOP_PCT}%" in h
    assert "NOT_RUN" in h
    assert "all raid fills" in h                                          # Amendment 1, A1.4


def test_29_read_only_guard():
    for word in ("load_prices", "_fetch", "_mongo_put", "insert", "update_", "replace_one",
                 "delete", "bulk_write", "create_index", "turning_bullish_keltner_study"):
        assert word not in SRC, word
    tree = ast.parse(SRC)
    names = {a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
             for a in n.names} | {n.module or "" for n in ast.walk(tree)
                                  if isinstance(n, ast.ImportFrom)}
    assert not any("keltner" in x for x in names)
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not attrs & {"insert_one", "insert_many", "update_one", "update_many",
                        "delete_one", "delete_many", "find_one_and_update"}


def test_30_json_nan_becomes_null(tmp_path):
    p = tmp_path / "x.json"
    S._json_dump(str(p), {"a": float("nan"), "b": [float("inf"), 1.0], "c": np.float32(2.0)})
    d = json.loads(p.read_text())
    assert d == {"a": None, "b": [None, 1.0], "c": 2.0}


# ═════════════════════════════════════════ 31 + an end-to-end synthetic run
def _synthetic_names(k=8, n=320):
    frames = {}
    rng = np.random.default_rng(11)
    for i in range(k):
        steps = rng.normal(0, 1.2, n)
        c = 50 + np.cumsum(steps) * 0.6
        c = np.maximum(c, 5.0)
        wick = np.abs(rng.normal(0, 0.6, n)) + 0.05
        o = c + rng.normal(0, 0.3, n)
        h = np.maximum(c, o) + wick
        lo = np.minimum(c, o) - wick
        frames["SYM%d" % i] = pd.DataFrame(
            {"open": o, "high": h, "low": lo, "close": c, "volume": rng.integers(1e5, 1e6, n).astype(float)},
            index=pd.bdate_range("2025-01-02", periods=n))
    return frames


def _write_walk(tmp, monkeypatch, features_only):
    frames = _synthetic_names()
    as_of = max(f.index[-1] for f in frames.values()).strftime("%Y-%m-%d")
    monkeypatch.setattr(S, "load_closed", lambda s, a: (frames[s], None))
    res = [S.walk_symbol(s, as_of, features_only) for s in sorted(frames)]
    res.append(("DEAD", "short", None))
    S._write_chunk(str(tmp), 0, res, set(frames), features_only)
    S._json_dump(str(tmp / "snapshot_t0.json"), {"as_of": as_of, "stride": 1, "universe": "cache",
                                                 "stamps": {}, "symbols": sorted(frames)})
    S._json_dump(str(tmp / "snapshot_verify.json"), {"ok": True, "docs_moved": 0,
                                                     "walked_moved": 0, "bars_differ": 0})
    (tmp / "in_study.txt").write_text("\n".join(sorted(frames)) + "\n")
    return frames, as_of


class _A:
    def __init__(self, out):
        self.out = str(out)
        self.git_head = "test"


def _force_balanced(tmp):
    """The 8-name synthetic walk is too small to balance, so stats would stop.
    Force the gate open here; the stop itself has its own test, A1-9."""
    p = tmp / "match.json"
    mt = json.loads(p.read_text())
    mt["balance"]["balanced"] = True
    p.write_text(json.dumps(mt))


def test_31_sanity_and_match_open_no_arms_file(tmp_path, monkeypatch):
    _write_walk(tmp_path, monkeypatch, features_only=True)
    assert not list((tmp_path / "walk").glob("*_arms.npz"))
    opened = []
    real = np.load

    def spy(p, *a, **k):
        opened.append(str(p))
        return real(p, *a, **k)
    monkeypatch.setattr(S.np, "load", spy)
    monkeypatch.setattr(S, "load_closed", lambda s, a: (None, "no_doc"))
    S.stage_sanity(_A(tmp_path))
    S.stage_match(_A(tmp_path))
    assert opened and not any("_arms" in p for p in opened)                # (N)
    assert (tmp_path / "match.json").exists()
    mt = json.loads((tmp_path / "match.json").read_text())
    assert mt["balance"]["gate_vars"] == ["rho", "delta", "nu"]            # Amendment 1
    assert "SUPERSEDED" in mt["balance"]["balance_v1"]["label"]
    assert mt["amendment"] == S.AMENDMENT_1


def test_32_stats_end_to_end_on_synthetic_frames(tmp_path, monkeypatch):
    frames, as_of = _write_walk(tmp_path, monkeypatch, features_only=False)
    bench = next(iter(frames.values()))
    monkeypatch.setattr(S, "bench_frame", lambda as_of=None: bench)
    monkeypatch.setattr(S, "BOOT_B", 60)
    S.stage_match(_A(tmp_path))
    _force_balanced(tmp_path)
    res = S.stage_stats(_A(tmp_path))
    d = json.loads((tmp_path / "amd_raid_low_measured.json").read_text())
    for key in ("study", "prereg", "snapshot", "sample", "fills", "primary", "balance",
                "stability", "survivorship", "secondary", "diagnostics_not_tradable", "verdict"):
        assert key in d, key
    assert d["verdict"]["status"] in ("edge", "inverted", "no_signal")
    assert d["sample"]["skipped"] == {"short": 1}
    assert "HINDSIGHT" in d["diagnostics_not_tradable"]["hindsight"]["label"]
    Z = np.load(tmp_path / "matched.npz")                                 # A1-3: without replacement
    for k in ("p1", "p1s", "ca"):
        assert pd.Series(Z[k + "_pid"]).is_unique, k
    pr = d["primary"]                                                     # A1-10: e1 - p1 == lift
    trio = [pr["e1_mean_matched"], pr["p1_mean"], pr["diff"]]
    if all(x is not None for x in trio):
        assert abs(pr["e1_mean_matched"] - pr["p1_mean"] - pr["diff"]) < 1e-12
    else:
        assert all(x is None for x in trio)                               # < 5 fills in an arm
    assert d["prereg"]["amendment_1"] == S.AMENDMENT_1                    # A1-13
    for k in ("MATCH_VARS", "CALIPER_SD", "K_NN"):
        assert k in d["prereg"], k


def test_32b_stats_refuses_a_matched_npz_from_another_walk(tmp_path, monkeypatch):
    frames, as_of = _write_walk(tmp_path, monkeypatch, features_only=False)
    bench = next(iter(frames.values()))
    monkeypatch.setattr(S, "bench_frame", lambda as_of=None: bench)
    monkeypatch.setattr(S, "BOOT_B", 30)
    S.stage_match(_A(tmp_path))
    _force_balanced(tmp_path)
    mt = json.loads((tmp_path / "match.json").read_text())
    assert mt["feat_fingerprint"] == S.feat_fingerprint(S.load_chunks(str(tmp_path), "feat"))
    keep = {k: v for k, v in frames.items() if k != "SYM0"}               # a re-walk without SYM0
    monkeypatch.setattr(S, "load_closed", lambda s, a: (keep[s], None))
    res = [S.walk_symbol(s, as_of, False) for s in sorted(keep)]
    S._write_chunk(str(tmp_path), 0, res, set(keep), False)
    with pytest.raises(SystemExit) as e:
        S.stage_stats(_A(tmp_path))                                       # (N) stale eids / pids
    assert "different walk" in str(e.value)
    assert not (tmp_path / "amd_raid_low_measured.json").exists()
    (tmp_path / "match.json").unlink()
    with pytest.raises(SystemExit):
        S.stage_stats(_A(tmp_path))                                       # (N) no match.json
    S.stage_match(_A(tmp_path))
    _force_balanced(tmp_path)
    S.stage_stats(_A(tmp_path))
    assert (tmp_path / "amd_raid_low_measured.json").exists()


def test_33_stats_refuses_without_a_passed_snapshot(tmp_path):
    S._json_dump(str(tmp_path / "snapshot_verify.json"), {"ok": False})
    res = S.stage_stats(_A(tmp_path))
    assert res["verdict"]["status"] == "invalid_snapshot"                  # (N)
    assert not (tmp_path / "amd_raid_low_measured.json").exists()


def test_34_explain_prints_the_event_and_a_pool_row(tmp_path, monkeypatch, capsys):
    frames = _synthetic_names(k=3)
    sym, df = next((s, f) for s, f in frames.items() if S.pit_walk(f)[0] and S.pit_walk(f)[1])
    ev, pool = S.pit_walk(df)
    monkeypatch.setattr(S, "load_closed", lambda s, a: (df, None))
    S._json_dump(str(tmp_path / "snapshot_t0.json"), {"as_of": df.index[-1].strftime("%Y-%m-%d")})
    S.explain(_A(tmp_path), sym, ev[0]["date"])
    out = capsys.readouterr().out
    assert "EVENT:" in out and "raid_price=%s" % ev[0]["raid_price"] in out
    S.explain(_A(tmp_path), sym, pool[0]["date"])
    assert "POOL ROW:" in capsys.readouterr().out
    S.explain(_A(tmp_path), sym, "1999-01-01")
    assert "no bar" in capsys.readouterr().out                            # (N)


# ═════════════════════════════════════════ Amendment 1 (2026-09-25, before any outcome)
def _nn_ev(rows):
    """rows: (eid, sym, dpos, rho, delta, nu[, t])."""
    return pd.DataFrame([{"eid": r[0], "sym": r[1], "dpos": r[2], "rho": r[3], "delta": r[4],
                          "nu": r[5], "t": r[6] if len(r) > 6 else 500} for r in rows])


def _nn_pl(rows):
    """rows: (pid, sym, dpos, rho, delta, nu[, t])."""
    return pd.DataFrame([{"pid": r[0], "sym": r[1], "dpos": r[2], "rho": r[3], "delta": r[4],
                          "nu": r[5], "t": r[6] if len(r) > 6 else 500} for r in rows])


ONES = np.ones(3)


def _a1_smds(ev, pl, M):
    em = np.unique(M["eid"].to_numpy(dtype=np.int64))
    pid = M["pid"].to_numpy(dtype=np.int64)
    return {"smd_" + v: S.smd(ev[v].to_numpy()[em], pl[v].to_numpy()[pid]) for v in S.MATCH_VARS}


def test_a1_01_cells_stay_imbalanced_nn_with_caliper_balances():
    rng = np.random.default_rng(20260925)
    D, NE, NP = 20, 6, 3000
    ev = pd.DataFrame({"eid": np.arange(D * NE), "sym": np.tile(np.arange(NE), D),
                       "dpos": np.repeat(np.arange(D), NE), "t": 500,
                       "rho": 0.02 + 0.28 * rng.random(D * NE) ** 0.2,
                       "delta": 0.005 + 0.045 * rng.random(D * NE),
                       "nu": 0.01 + 0.07 * rng.random(D * NE)})
    pl = pd.DataFrame({"pid": np.arange(D * NP), "sym": 100 + np.tile(np.arange(NP), D),
                       "dpos": np.repeat(np.arange(D), NP), "t": 500,
                       "rho": 0.02 + 0.28 * rng.random(D * NP),
                       "delta": 0.005 + 0.045 * rng.random(D * NP),
                       "nu": 0.01 + 0.07 * rng.random(D * NP)})
    e = S.bin_edges(ev)
    ev1 = ev.assign(date=ev["dpos"], cell=S.cell_of(ev["delta"], ev["rho"], ev["nu"], e))
    pl1 = pl.assign(date=pl["dpos"], cell=S.cell_of(pl["delta"], pl["rho"], pl["nu"], e))
    V1 = S.draw_matched(ev1, pl1, k=5, seed=1, same_symbol=False, widen=2, gap=24)
    assert _a1_smds(ev, pl, V1)["smd_rho"] >= S.BALANCE_SMD_MAX            # (N) skew inside every cell
    M = S.match_nn(ev, pl, S.match_sd(ev, pl))
    assert M["eid"].nunique() == D * NE and M.attrs["unmatched"] == []
    assert M["pid"].is_unique
    bal = _a1_smds(ev, pl, M)
    assert all(abs(bal["smd_" + v]) < S.BALANCE_SMD_MAX for v in S.MATCH_VARS), bal
    assert S.balance_gate(bal)


def test_a1_02_caliper_is_a_per_covariate_box():
    c = S.CALIPER_SD
    ev = _nn_ev([(0, 0, 5, 0.0, 0.0, 0.0)])
    far = (0, 1, 5, c + 0.1, 0.0, 0.0)
    near = (1, 2, 5, c / 4, c / 4, c / 4)
    M = S.match_nn(ev, _nn_pl([far, near]), ONES)
    assert M["pid"].tolist() == [1]                                       # (N) far row never drawn
    M = S.match_nn(ev, _nn_pl([far]), ONES)
    assert len(M) == 0 and M.attrs["unmatched"] == [0]                    # (N)
    M = S.match_nn(ev, _nn_pl([(0, 1, 5, 0.0, 0.0, c + 0.01)]), ONES)
    assert len(M) == 0 and M.attrs["unmatched"] == [0]                    # (N) nu alone excludes
    box = (0, 1, 5, c - 0.01, c - 0.01, c - 0.01)
    M = S.match_nn(ev, _nn_pl([box]), ONES)
    assert M["pid"].tolist() == [0] and M["dist"].iloc[0] > c             # a box, not a radius


def test_a1_03_without_replacement_never_reuses_a_draw():
    ev = _nn_ev([(0, 0, 5, 0.00, 0, 0), (1, 1, 5, 0.01, 0, 0), (2, 2, 5, 0.02, 0, 0)])
    rows = [(0, 10, 5, 0.00, 0, 0), (1, 11, 5, 0.05, 0, 0)]
    M = S.match_nn(ev, _nn_pl(rows), ONES)
    assert M["pid"].is_unique and M["eid"].nunique() == 2                 # (N)
    assert len(M.attrs["unmatched"]) == 1
    left = M.attrs["unmatched"][0]
    M2 = S.match_nn(ev, _nn_pl(rows + [(2, 12, 6, 0.01, 0, 0)]), ONES)
    assert M2["pid"].is_unique and M2.attrs["unmatched"] == []
    assert M2.set_index("eid").loc[left, "kind"] == "widened"
    assert (M2[M2["eid"] != left]["kind"] == "exact").all()


def test_a1_04_closest_pair_wins_not_eid_order():
    ev = _nn_ev([(0, 0, 5, 0.00, 0, 0), (1, 1, 5, 0.20, 0, 0)])
    M = S.match_nn(ev, _nn_pl([(0, 9, 5, 0.15, 0, 0)]), ONES)
    assert M["eid"].tolist() == [1] and M["pid"].tolist() == [0]
    assert M["dist"].iloc[0] == pytest.approx(0.05)
    assert M.attrs["unmatched"] == [0]                                    # (N) eid 0 loses


def test_a1_05_deterministic_ties_and_no_rng():
    import inspect
    ev = _nn_ev([(0, 0, 5, 0.0, 0, 0)])
    pl = _nn_pl([(7, 1, 5, 0.1, 0, 0), (3, 2, 5, -0.1, 0, 0)])           # identical distance
    M = S.match_nn(ev, pl, ONES)
    assert M["pid"].tolist() == [3]                                       # (N) lower pid, not row order
    assert S.match_nn(ev, pl, ONES).equals(M)
    params = inspect.signature(S.match_nn).parameters
    assert "seed" not in params and "rng" not in params
    src = inspect.getsource(S.match_nn)
    assert "random" not in src and "rng" not in src


def test_a1_06_widening_only_if_needed():
    ev = _nn_ev([(0, 0, 10, 0.0, 0, 0)])
    M = S.match_nn(ev, _nn_pl([(0, 1, 10, 0.2, 0, 0), (1, 2, 11, 0.0, 0, 0)]), ONES)
    assert M["pid"].tolist() == [0] and M["kind"].tolist() == ["exact"]   # (N) closer +1 row ignored
    M = S.match_nn(ev, _nn_pl([(0, 1, 10, 0.2, 0, 0), (1, 2, 11, 0.0, 0, 0)]), ONES, k=2)
    assert M["kind"].tolist() == ["exact"]                                # (N) exact-matched: no widened extra
    M = S.match_nn(ev, _nn_pl([(0, 1, 12, 0.0, 0, 0)]), ONES)
    assert M["pid"].tolist() == [0] and M["kind"].tolist() == ["widened"]
    M = S.match_nn(ev, _nn_pl([(0, 1, 13, 0.0, 0, 0)]), ONES)
    assert len(M) == 0 and M.attrs["unmatched"] == [0]                    # (N) +3 is out
    M = S.match_nn(ev, _nn_pl([(0, 1, 12, 0.0, 0, 0)]), ONES, widen=0)
    assert len(M) == 0 and M.attrs["unmatched"] == [0]                    # (N) no widening


def test_a1_07_symbols_and_the_p1s_gap():
    ev = _nn_ev([(0, 0, 5, 0.0, 0, 0, 500)])
    M = S.match_nn(ev, _nn_pl([(0, 0, 5, 0.0, 0, 0), (1, 1, 5, 0.1, 0, 0)]), ONES)
    assert M["pid"].tolist() == [1]                                       # (N) never own symbol
    M = S.match_nn(ev, _nn_pl([(0, 0, 5, 0.0, 0, 0)]), ONES)
    assert M.attrs["unmatched"] == [0]                                    # (N)
    gap = W + H
    pl = _nn_pl([(0, 0, 9, 0.0, 0, 0, 500 + gap), (1, 0, 1, 0.0, 0, 0, 500 - gap),
                 (2, 0, 30, 0.1, 0, 0, 500 + gap + 1), (3, 1, 40, 0.0, 0, 0, 500 + gap + 5)])
    ps = S.match_nn(ev, pl, ONES, same_symbol=True, widen=0, gap=gap)
    assert ps["pid"].tolist() == [2]                                      # (N) == gap and other sym out
    only = S.match_nn(ev, pl.iloc[:2], ONES, same_symbol=True, widen=0, gap=gap)
    assert len(only) == 0 and only.attrs["unmatched"] == [0]              # (N)


def test_a1_08_the_gate_reads_rho_delta_and_nu():
    ok = {"smd_rho": 0.05, "smd_delta": 0.05}
    assert not S.balance_gate({**ok, "smd_nu": 0.1})                      # (N) boundary fails
    assert not S.balance_gate({**ok, "smd_nu": -0.12})                    # (N) nu is gated
    assert S.balance_gate({**ok, "smd_nu": 0.099})
    assert not S.balance_gate({**ok, "smd_nu": float("nan")})             # (N) NaN fails
    assert not S.balance_gate(ok)                                         # (N) missing key fails
    assert not S.balance_gate({"smd_rho": -0.1, "smd_delta": 0.0, "smd_nu": 0.0})   # (N)
    assert "rho, delta and nu" in S.VERDICT_RULE_TEXT


def test_a1_09_stats_stops_before_any_outcome_when_imbalanced(tmp_path, monkeypatch):
    _write_walk(tmp_path, monkeypatch, features_only=False)
    assert list((tmp_path / "walk").glob("*_arms.npz"))
    S.stage_match(_A(tmp_path))
    p = tmp_path / "match.json"
    mt = json.loads(p.read_text())
    mt["balance"]["balanced"] = False
    p.write_text(json.dumps(mt))
    opened = []
    real = np.load

    def spy(f, *a, **k):
        opened.append(str(f))
        return real(f, *a, **k)
    monkeypatch.setattr(S.np, "load", spy)
    res = S.stage_stats(_A(tmp_path))
    assert res["verdict"]["status"] == "no_signal" and "imbalanced" in res["verdict"]["tags"]
    assert opened and not any("_arms" in f for f in opened)                # (N) no outcome opened
    assert not any("matched.npz" in f for f in opened)
    assert not (tmp_path / "amd_raid_low_measured.json").exists()          # (N)


def test_a1_10_headline_pairs_the_matched_e1_with_p1():
    res = {"verdict": {"status": "no_signal", "tags": []},
           "primary": {"e1_mean_matched": 0.0123, "p1_mean": 0.0045, "diff": 0.0078,
                       "e1_mean_all": 0.05, "diff_ci": [0.001, 0.015], "xs_mean": 0.01,
                       "xs_ci": [0.0, 0.02], "stop_rate": 0.4},
           "fills": {"E1": {"rate": 0.5}, "P1": {"rate": 0.6}}}
    h = S.headline(res)
    assert "+1.23% per fill vs +0.45%" in h and "lift +0.78pp" in h
    assert "all raid fills +5.00%" in h
    assert "+5.00% per fill" not in h                                     # (N) all-fills never beside P1


def test_a1_11_date_halves_are_unique_dates():
    d = [1] * 10 + [2, 3, 4, 5]
    assert S.date_split(d) == 3
    assert S.date_split(d) != int(np.median(d)) and int(np.median(d)) == 1   # (N) not the median event
    assert S.date_split([]) == 0


def test_a1_12_match_sd():
    ev = pd.DataFrame({"rho": [0.0, 2.0], "delta": [0.0, 1.0], "nu": [0.0, 1.0]})
    pl = pd.DataFrame({"rho": [0.0, 4.0], "delta": [0.0, 1.0], "nu": [0.0, 1.0]})
    s = S.match_sd(ev, pl)
    assert s[0] == pytest.approx(math.sqrt((2.0 + 8.0) / 2.0))
    assert s[1] == pytest.approx(math.sqrt(0.5)) and s[2] == pytest.approx(math.sqrt(0.5))
    evn = pd.concat([ev, pd.DataFrame({"rho": [np.nan], "delta": [np.nan], "nu": [np.inf]})])
    assert np.allclose(S.match_sd(evn, pl), s)                            # (N) non-finite ignored
    assert math.isnan(S.match_sd(ev.iloc[:1], pl)[0])                     # (N) one row -> NaN


def test_a1_13_amendment_source_guard():
    assert S.MATCH_VARS == ("rho", "delta", "nu")
    assert S.CALIPER_SD == 0.4 and S.K_NN == 1
    body = SRC[SRC.index("def balance_gate"):SRC.index("def date_split")]
    assert "for v in MATCH_VARS" in body
    assert "2026-09-25, before any outcome" in S.AMENDMENT_1
