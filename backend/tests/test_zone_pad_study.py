"""Hermetic tests for scripts/zone_pad_study_2026_09_30.py (WP-STUDY, spec 2026-09-30).

Pure functions on synthetic frames — no Mongo (conftest refuses a client), no provider.
Every threshold the study uses is pinned to the constant it is imported from.
"""
from __future__ import annotations

import ast
import math
import re

import numpy as np
import pandas as pd
import pytest

from scripts import entry_trigger_study as ETS
from scripts import explosive_study as ES
from scripts import zone_pad_study_2026_09_30 as ZP
from studies import bounce_quality_study as BQ
from supply_demand import alert_gates as AG
from supply_demand import key_levels as KL
from supply_demand import sd_liquidity as SL
from supply_demand import zone_pad_measured as ZPM


@pytest.fixture
def pad_off_arm_a(monkeypatch):
    """Arm A = today's engine: on the branch the gates read level_pad; turn it off."""
    try:
        from supply_demand import level_pad as LP
    except ImportError:                                  # pragma: no cover
        return None
    monkeypatch.setattr(LP, "DEMAND_PAD_PCT", 0.0)
    return LP


def _frame(n: int = 420, seed: int = 11, base: float = 100.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    step = rng.normal(0, 1.2, n)
    close = np.maximum(base + np.cumsum(step), 5.0)
    wick = np.abs(rng.normal(0, 1.0, n)) + 0.05
    high, low = close + wick, close - wick
    op = close - step * 0.5
    vol = rng.integers(100_000, 1_000_000, n).astype(float)
    dates = pd.bdate_range("2024-01-02", periods=n)
    return pd.DataFrame({"date": dates, "open": op, "high": high, "low": low, "close": close,
                         "volume": vol, "d": dates.strftime("%Y-%m-%d")})


# ── constants: imported, never typed ─────────────────────────────────────────
def test_every_threshold_is_the_house_constant():
    assert ZP.PAD_PCT is SL.STOP_SHELF_PCT
    assert ZP.PIERCE_PCT is SL.SWEEP_MIN_PIERCE_PCT
    assert ZP.PIERCE_PCT == KL.PIERCE_PCT
    assert ZP.RECLAIM_BARS is SL.RECLAIM_MAX_BARS
    assert ZP.HOLD is BQ.HOLD_SESSIONS and ZP.CLOCKS is BQ.CLOCKS and ZP.HOLD in ZP.CLOCKS
    assert ZP.FLOOR is BQ.MIN_HISTORY_BARS
    assert ZP.REVERSAL_PCT is AG.ALERT_MIN_ROOM_PCT
    assert ZP.TOUCH_TOL_PCT is AG.APPROACH_TOUCH_TOL_PCT
    assert ZP.STOP_BUFFER_PCT is AG.STOP_BUFFER_PCT
    assert ZP.MAX_ABOVE_PCT is AG.ALERT_MAX_ABOVE_DEMAND_PCT
    assert ZP.MIN_CELL_N is ETS.MIN_CELL_N
    assert ZP.SWEEP_WINDOW is AG.SWEEP_WINDOW_BARS
    # the three numbers the spec itself fixes
    assert (ZP.FALL_PADS, ZP.PLACEBO_MAX_TRIES, ZP.QUOTABLE_MIN_DATES) == (3, 50, 100)


def test_geometry_strips_any_pad_key(monkeypatch):
    from supply_demand import demand_reentry as DR
    real = DR.zone_geom()
    monkeypatch.setattr(DR, "zone_geom", lambda: {**real, "demand_pad_pct": 1.0})
    assert ZP.geom() == real
    assert "demand_pad_pct" not in ZP.geom()


def test_arm_a_pad_off_turns_the_branch_pad_off(monkeypatch):
    from supply_demand import level_pad as LP
    monkeypatch.setattr(LP, "DEMAND_PAD_PCT", LP.DEMAND_PAD_PCT)
    prev = ZP.arm_a_pad_off()
    assert prev == SL.STOP_SHELF_PCT
    assert LP.DEMAND_PAD_PCT == 0.0


# ── arm B emulation ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("lo", [1.23, 133.0, 5000.5, 0.87])
def test_floor_b_is_the_stop_shelf_bottom(lo):
    assert ZP._floor_b({"lo": lo, "hi": lo * 1.02}) == SL.stop_shelf(lo)["bottom"]


def test_floor_b_his_case_and_garbage():
    assert ZP._floor_b({"lo": 133.0, "hi": 135.0}) == 131.67
    assert ZP._floor_b({"lo": 133.0, "hi": 135.0}, pad=0) == 133.0
    for bad in (None, {}, {"lo": 0, "hi": 1}, {"lo": -1, "hi": 1}, {"lo": "x", "hi": 2},
                {"lo": float("nan"), "hi": 2}, {"lo": 3, "hi": 2}):
        assert ZP._floor_b(bad) is None


def test_prox_b_boundaries():
    b = {"kind": "demand", "lo": 133.0, "hi": 135.0}
    assert ZP.prox_b(132.0, b) and ZP.prox_b(131.67, b) and ZP.prox_b(136.35, b)
    assert not ZP.prox_b(131.66, b)
    assert not ZP.prox_b(136.36, b)
    assert not ZP.prox_b(float("nan"), b) and not ZP.prox_b(None, b) and not ZP.prox_b(-1, b)


def test_prox_b_at_pad_zero_is_todays_gate(pad_off_arm_a):
    b = {"kind": "demand", "lo": 133.0, "hi": 135.0}
    for px in (131.0, 132.0, 132.99, 133.0, 134.0, 136.35, 136.36):
        assert ZP.prox_b(px, b, pad=0) == AG.demand_proximity_gate(px, b)


def _his_case():
    B = {"kind": "demand", "lo": 133.0, "hi": 135.0, "touches": 3}
    S = {"kind": "supply", "lo": 150.0, "hi": 152.0, "touches": 3}
    return B, S


def test_his_133_132_case_only_the_pad_chain_admits(pad_off_arm_a):
    B, S = _his_case()
    # low 131.30 touched, the print 132.00 is 0.5% off it, yesterday closed above the band
    ea = ZP.pick_event([S, B], [B], 132.0, 136.0, 131.30, "A")
    eb = ZP.pick_event([S, B], [B], 132.0, 136.0, 131.30, "B")
    assert ea is None
    assert eb is not None and eb["band"] is B and eb["dir"] == "bouncing"
    assert eb["room"]["target"] == 150.0
    # NEGATIVE: under the pad floor nothing admits it
    assert ZP.pick_event([S, B], [B], 131.5, 136.0, 130.8, "B") is None


def test_room_b_excludes_only_the_entry_band():
    B, S = _his_case()
    ok, room = ZP.room_b(132.0, [B, S], 136.0, B)
    assert ok and room["target"] == 150.0
    # without the exclusion the same band is its own ceiling at 133 -> fails
    ok2, room2 = AG.room_gate(132.0, [B, S], 136.0)
    assert not ok2 and room2["target"] == 133.0
    # an EQUAL but different dict is not removed (identity, not equality)
    ok3, _ = ZP.room_b(132.0, [dict(B), S], 136.0, B)
    assert not ok3


def test_stops_his_case():
    B, _ = _his_case()
    sa, sb = ZP.stops(B)
    assert sa == pytest.approx(133.0 * 0.995)
    assert sb == pytest.approx(131.67 * 0.995)
    assert round(sb, 2) == 131.01
    sa0, sb0 = ZP.stops(B, pad=0)
    assert sa0 == sb0


# ── forward mechanics ────────────────────────────────────────────────────────
def _arr(n, v):
    return np.full(n, float(v))


def test_forward_stop_and_target_in_the_same_bar_books_the_stop():
    n = 80
    h, l, c = _arr(n, 101), _arr(n, 99), _arr(n, 100)
    h[3], l[3] = 120.0, 90.0
    fw = ZP.forward(h, l, c, 0, 100.0, 95.0, 110.0)
    assert fw["why5"] == "stop" and fw["pct5"] == pytest.approx(-5.0) and fw["R5"] == pytest.approx(-1.0)


def test_forward_gap_through_the_stop_books_at_the_stop():
    n = 80
    h, l, c = _arr(n, 101), _arr(n, 99), _arr(n, 100)
    h[2], l[2], c[2] = 80.0, 70.0, 75.0            # opened far under the stop
    fw = ZP.forward(h, l, c, 0, 100.0, 95.0, None)
    assert fw["why20"] == "stop" and fw["pct20"] == pytest.approx(-5.0)   # documented limitation


def test_forward_target_clock_and_negatives():
    n = 80
    h, l, c = _arr(n, 101), _arr(n, 99), _arr(n, 100)
    h[7] = 111.0
    fw = ZP.forward(h, l, c, 0, 100.0, 95.0, 110.0)
    assert fw["why5"] == "clock" and fw["why10"] == "target" and fw["R10"] == pytest.approx(2.0)
    assert ZP.forward(h, l, c, 0, 100.0, 100.0, None) is None          # entry <= stop
    assert ZP.forward(h, l, c, 0, 100.0, -1.0, None) is None
    assert ZP.forward(h, l, c, n - 10, 100.0, 95.0, None) is None      # no full clock


def test_forward_nan_bars_never_trigger():
    n = 80
    h, l, c = _arr(n, 101), _arr(n, 99), _arr(n, 100)
    l[2] = np.nan                                   # a hole is skipped, never a 0 low
    fw = ZP.forward(h, l, c, 0, 100.0, 95.0, None)
    assert fw["why60"] == "clock"


# ── buckets, resolution ──────────────────────────────────────────────────────
@pytest.mark.parametrize("depth,want", [
    (-3.0, "held"), (0.0, "held"), (0.1499, "held"), (0.15, "pierce_to_pad"),
    (0.99, "pierce_to_pad"), (1.0, "pad_to_2pad"), (1.99, "pad_to_2pad"), (2.0, "2pad_to_3pad"),
    (3.0, "3pad_plus"), (40.0, "3pad_plus"), (float("nan"), "held"), (None, "held")])
def test_bucket_edges_are_exact(depth, want):
    assert ZP.bucket(depth) == want


def test_bucket_scales_with_the_pad():
    assert ZP.bucket(1.5, pad=2.0) == "pierce_to_pad"
    assert ZP.bucket(0.5, pad=0) == "3pad_plus"      # pad 0 -> every pierce is beyond 3 pads


def test_depth_window_is_the_reclaim_window():
    assert ZP.DEPTH_BARS is SL.RECLAIM_MAX_BARS


def test_resolve_reversal_fall_clock_and_depth():
    n = 40
    e = ZP.DEPTH_BARS                                # the depth window closes at bar e
    h, l, c = _arr(n, 101), _arr(n, 99.5), _arr(n, 100)
    l[1] = 98.9                                      # 1.1% under a 100 level, inside the window
    h[e + 3] = 105.1                                 # the reversal, AFTER the window
    r = ZP.resolve(h, l, c, 0, 100.0)
    assert r["outcome"] == "reversed" and r["res_k"] == e + 3
    assert r["depth_pct"] == pytest.approx(1.1) and r["bucket"] == "pad_to_2pad"
    h2, l2, c2 = _arr(n, 101), _arr(n, 99.5), _arr(n, 100)
    c2[e + 2], h2[e + 2] = 96.9, 106.0                # fell AND reversal high same bar -> fell
    assert ZP.resolve(h2, l2, c2, 0, 100.0)["outcome"] == "fell"
    h3, l3, c3 = _arr(n, 101), _arr(n, 100.5), _arr(n, 101)
    r3 = ZP.resolve(h3, l3, c3, 0, 100.0)
    assert r3["outcome"] == "clock" and r3["bucket"] == "held" and r3["res_k"] == e + ZP.HOLD
    l3[1] = np.nan
    assert ZP.resolve(h3, l3, c3, 0, 100.0)["bucket"] == "held"     # NaN skipped, not a 0 low
    assert ZP.resolve(h3, l3, c3, n - 5, 100.0) is None
    assert ZP.resolve(h3, l3, c3, n - e - ZP.HOLD, 100.0) is None   # outcome window runs off
    assert ZP.resolve(h3, l3, c3, 0, 0.0) is None


def test_resolve_outcomes_inside_the_depth_window_are_not_scored():
    n = 40
    e = ZP.DEPTH_BARS
    h, l, c = _arr(n, 101), _arr(n, 99.5), _arr(n, 100)
    h[3] = 110.0                                     # a reversal high INSIDE the depth window
    assert ZP.resolve(h, l, c, 0, 100.0)["outcome"] == "clock"
    h2, l2, c2 = _arr(n, 101), _arr(n, 99.5), _arr(n, 100)
    c2[3], l2[3] = 96.0, 95.5                        # a 'fell' close inside the window: depth only
    r2 = ZP.resolve(h2, l2, c2, 0, 100.0)
    assert r2["outcome"] == "clock" and r2["bucket"] == "3pad_plus"
    h3, l3, c3 = _arr(n, 101), _arr(n, 99.5), _arr(n, 100)
    l3[e + 1] = 90.0                                 # a deep low AFTER the window: not depth
    assert ZP.resolve(h3, l3, c3, 0, 100.0)["bucket"] == "pierce_to_pad"


def test_shallow_bucket_can_fall_and_deep_bucket_can_reverse():
    """The pre-amendment construction made these two impossible: depth ran to the resolution
    bar, so a fall always booked 3pad_plus and a pierce-to-pad event could never 'fall'."""
    n = 40
    e = ZP.DEPTH_BARS
    h, l, c = _arr(n, 101), _arr(n, 100.2), _arr(n, 100.5)
    l[2] = 99.5                                      # 0.5% pierce: inside the pad
    c[e + 4] = l[e + 4] = 96.5                       # then it kept falling, after the window
    r = ZP.resolve(h, l, c, 0, 100.0)
    assert (r["bucket"], r["outcome"]) == ("pierce_to_pad", "fell")
    h2, l2, c2 = _arr(n, 101), _arr(n, 99.5), _arr(n, 100.5)
    l2[2] = 96.0                                     # 4% pierce: beyond 3 pads
    h2[e + 4] = 106.0                                # then it reversed
    r2 = ZP.resolve(h2, l2, c2, 0, 100.0)
    assert (r2["bucket"], r2["outcome"]) == ("3pad_plus", "reversed")


def _pad_pierce_rows(p_rev: float, seed: int, n_dates: int = 150, per: int = 4) -> pd.DataFrame:
    """Synthetic touch events, every one pierced INSIDE the pad (0.5% under a 100 level) in the
    depth window; after it, each reverses with probability p_rev, else keeps falling."""
    rng = np.random.default_rng(seed)
    e = ZP.DEPTH_BARS
    n = e + ZP.HOLD + 2
    dates = pd.bdate_range("2025-01-02", periods=n_dates).strftime("%Y-%m-%d")
    rows = []
    for d in dates:
        for _ in range(per):
            h, l, c = _arr(n, 101), _arr(n, 100.2), _arr(n, 100.5)
            l[1 + int(rng.integers(0, e))] = 99.5
            k = e + 1 + int(rng.integers(0, ZP.HOLD))
            if rng.random() < p_rev:
                h[k] = 106.0
            else:
                c[k] = l[k] = 96.5
            rows.append({"date": d, **ZP.resolve(h, l, c, 0, 100.0)})
    return pd.DataFrame(rows)


def test_his_observation_true_separates_from_placebo():
    real = _pad_pierce_rows(0.70, seed=21)
    placebo = _pad_pierce_rows(0.40, seed=22)
    assert set(real["bucket"]) == {ZP.PAD_BUCKET}
    t = ZP.touch_tables(real, placebo, draws=1000)
    rb = t["real"]["by_bucket"][ZP.PAD_BUCKET]
    assert 0.0 < rb["rev"] < 100.0 and 0.0 < rb["fell"] < 100.0     # not degenerate
    d = t["d_rev_given_pad"]
    assert d["lo"] > 0 and ZP.verdict(d["lo"], d["hi"]) == "supports"


def test_his_observation_false_does_not_separate():
    real = _pad_pierce_rows(0.50, seed=23)
    placebo = _pad_pierce_rows(0.50, seed=24)
    t = ZP.touch_tables(real, placebo, draws=1000)
    d = t["d_rev_given_pad"]
    assert d["lo"] < 0 < d["hi"] and ZP.verdict(d["lo"], d["hi"]) == "no_signal"
    worse = ZP.touch_tables(_pad_pierce_rows(0.30, seed=25), placebo, draws=1000)["d_rev_given_pad"]
    assert worse["hi"] < 0


def test_touch_tests():
    assert ZP.touch_band(136.0, 135.0, 135.0) and ZP.touch_band(136.0, 136.35, 135.0)
    assert not ZP.touch_band(136.0, 136.36, 135.0)
    assert not ZP.touch_band(135.0, 134.0, 135.0)     # yesterday not ABOVE the band
    assert not ZP.touch_band(None, 1, 1) and not ZP.touch_band(float("nan"), 1, 1)
    tol = KL.AT_LEVEL_PCT
    assert ZP.touch_level(140.0, 133.0 * (1 + tol / 100.0), 133.0)
    assert not ZP.touch_level(140.0, 133.0 * (1 + tol / 100.0) + 0.01, 133.0)
    assert not ZP.touch_level(132.0, 131.0, 133.0)


# ── key levels: vectorized == KL.period_levels ───────────────────────────────
def test_period_lows_equal_key_levels_period_levels():
    f = _frame(n=330, seed=3)
    lows = ZP.period_lows(f)
    fd = f.set_index(pd.DatetimeIndex(f["date"]))[["open", "high", "low", "close", "volume"]]
    for j in (5, 40, 251, 252, 253, 300, 329):
        session = fd.index[j].date()
        got = {m["period"]: m["price"] for m in KL.period_levels(fd.iloc[:j], session, KL.BOARD_PERIODS)
               if m["kind"] == "low"}
        for per in KL.BOARD_PERIODS:
            mine = lows[per][j]
            if per in got:
                assert mine == pytest.approx(got[per], abs=1e-9), (per, j)
            else:
                assert not np.isfinite(mine), (per, j)


def test_period_lows_skip_nan_lows():
    f = _frame(n=300, seed=4)
    f.loc[100, "low"] = np.nan
    lows = ZP.period_lows(f)
    assert np.nanmin(lows["year"]) > 0               # a NaN hole is never a 0 level


def test_suppressed_sell_and_reclaim_reads():
    n = 60
    c = _arr(n, 134.0)
    L = 133.0
    edge = ZP.key_pad_edge(L)
    assert edge == 131.67
    c[3] = 132.0                                     # raw rule fires (0.75% under), pad quiet
    c[6] = 133.5                                     # closed back above L
    r = ZP.suppressed_sell(c, 0, L)
    assert r["raw_fired"] and r["suppressed"] and r["supp_reclaimed"] == 1.0
    assert r["supp_pad_broke"] == 0.0 and math.isnan(r["extra_pct"])
    c2 = _arr(n, 134.0)
    c2[3], c2[8] = 132.0, 130.0                      # later breaks the pad edge
    r2 = ZP.suppressed_sell(c2, 0, L)
    assert r2["supp_pad_broke"] == 1.0 and r2["extra_pct"] == pytest.approx((130.0 / 132.0 - 1) * 100)
    c3 = _arr(n, 134.0)
    c3[3] = 131.0                                    # through BOTH: not suppressed
    r3 = ZP.suppressed_sell(c3, 0, L)
    assert r3["raw_fired"] and not r3["suppressed"]
    c4 = _arr(n, 134.0)
    c4[3] = 132.81                                   # 0.143% under: not a raw break
    assert not ZP.suppressed_sell(c4, 0, L)["raw_fired"]
    assert not ZP.suppressed_sell(c4, 0, L, pad=0)["suppressed"]
    lo_ = _arr(n, 133.5)
    lo_[2] = 132.0
    cc = _arr(n, 133.5)
    assert ZP.reclaim_read(lo_, cc, 0, L) == {"pierced": True, "reclaimed": True}
    assert ZP.reclaim_read(_arr(n, 133.5), cc, 0, L) == {"pierced": False, "reclaimed": False}


# ── placebo ──────────────────────────────────────────────────────────────────
def test_placebo_band_and_level_reject_non_positive_gaps():
    assert ZP.placebo_band(100.0, 0.0, 0.02) is None
    assert ZP.placebo_band(100.0, -0.01, 0.02) is None
    assert ZP.placebo_band(float("nan"), 0.01, 0.02) is None
    assert ZP.placebo_band(100.0, 0.01, -0.1) is None
    b = ZP.placebo_band(100.0, 0.02, 0.015)
    assert b == {"kind": "demand", "hi": 98.0, "lo": round(98.0 / 1.015, 2)}
    assert ZP.placebo_level(100.0, 0.0) is None and ZP.placebo_level(100.0, 0.03) == 97.0


def test_placebo_accepts_rejects_no_touch_and_nan(pad_off_arm_a):
    n = 80
    h, l, c = _arr(n, 101), _arr(n, 99.5), _arr(n, 100)
    ev = {"q": "q1", "g": 0.05, "h": 0.02, "symbol": "X", "date": "2025-01-02"}
    assert ZP.placebo_accepts(ev, h, l, c, 5) is None           # low never reached 95.x
    l2 = l.copy()
    l2[5] = 94.0
    row = ZP.placebo_accepts(ev, h, l2, c, 5)
    assert row is not None and row["hi"] == 95.0
    c3 = c.copy()
    c3[5] = np.nan
    assert ZP.placebo_accepts(ev, h, l2, c3, 5) is None          # a NaN bar is skipped
    assert ZP.placebo_accepts({**ev, "g": -0.01}, h, l2, c, 5) is None
    assert ZP.placebo_accepts(ev, h, l2, c, n - 3) is None       # no forward clock


def test_placebo_q2_uses_the_real_events_entry_test(pad_off_arm_a):
    n = 80
    h, l, c = _arr(n, 101), _arr(n, 99.5), _arr(n, 100)
    # prev close 100, band hi 98, the day dips to 97.4 and closes 98.2 (0.8% off the low)
    l[5], c[5], h[5] = 97.4, 98.2, 100.0
    ev = {"q": "q2", "g": 0.02, "h": 0.01, "touches": 3, "room_pct": 6.0,
          "symbol": "X", "date": "2025-01-02"}
    row = ZP.placebo_accepts(ev, h, l, c, 5)
    assert row is not None and "a_R20" in row and "b_R20" in row
    c2 = c.copy()
    c2[5] = 97.45                                   # at the low: not a reversal read -> rejected
    assert ZP.placebo_accepts(ev, h, l, c2, 5) is None


def test_draw_placebo_is_seeded_and_never_the_same_name(pad_off_arm_a):
    n = 80
    h, l, c = _arr(n, 101), _arr(n, 99.5), _arr(n, 100)
    l[5] = 94.0
    frames = {"X": (h, l, c), "Y": (h, l, c)}
    pool = {"2025-01-02": [("X", 5), ("Y", 5)]}
    ev = {"q": "q1", "g": 0.05, "h": 0.02, "symbol": "X", "date": "2025-01-02", "lo": 93.0}
    r1, t1 = ZP.draw_placebo(ev, pool, frames)
    r2, t2 = ZP.draw_placebo(ev, pool, frames)
    assert r1 is not None and r1["p_symbol"] == "Y" and (r1, t1) == (r2, t2)
    assert ZP.draw_placebo(ev, {"2025-01-02": [("X", 5)]}, frames) == (None, ZP.PLACEBO_MAX_TRIES)
    assert ZP.draw_placebo(ev, {}, frames) == (None, 0)


# ── pad 0 -> arm B == arm A row for row ──────────────────────────────────────
def _replay_rows(pad):
    rows = []
    for seed in (11, 23, 37, 41):
        rows += ZP.replay_symbol("S%d" % seed, _frame(seed=seed), pad=pad)
    return rows


def test_pad_zero_arm_b_equals_arm_a_row_for_row(pad_off_arm_a):
    rows = [r for r in _replay_rows(0) if r["q"] == "q2"]
    assert rows, "the fixture must produce events"
    assert all(r["cohort"] == "A" for r in rows)
    for r in rows:
        assert r["stop_a"] == r["stop_b"] and r["floor_b"] == r["lo"]
        for cl in ZP.CLOCKS:
            for k in ("R", "pct", "why"):
                assert r["a_%s%d" % (k, cl)] == r["b_%s%d" % (k, cl)]
        assert r["sweep_drawn"] == r["sweep_pad"]


def test_pad_changes_only_the_stop_on_cohort_a(pad_off_arm_a):
    zero = {(r["symbol"], r["j"]): r for r in _replay_rows(0) if r["q"] == "q2" and r["cohort"] == "A"}
    one = {(r["symbol"], r["j"]): r for r in _replay_rows(None) if r["q"] == "q2" and r["cohort"] == "A"}
    assert set(zero) == set(one)                    # cohort A never depends on arm B
    for k, r in one.items():
        assert r["a_R20"] == zero[k]["a_R20"] and r["stop_b"] < r["stop_a"]
        assert r["floor_b"] == ZP._floor_b({"lo": r["lo"], "hi": r["hi"]})


def test_replay_skips_short_frames():
    assert ZP.replay_symbol("X", _frame(n=200)) == []
    assert ZP.replay_symbol("X", None) == []
    assert ZP.kl_symbol("X", _frame(n=200)) == []


def test_kl_replay_rows_are_support_tests():
    rows = ZP.kl_symbol("K", _frame(n=420, seed=7))
    assert rows
    for r in rows:
        assert r["q"] == "q3" and r["g"] > 0 and r["bucket"] in ZP.BUCKETS
        assert set(r["periods"].split("+")) <= set(KL.BOARD_PERIODS)
    assert len({(r["symbol"], r["date"]) for r in rows}) == len(rows)   # one per symbol-date


# ── statistics ───────────────────────────────────────────────────────────────
def _cohort(effect: float, seed: int, n_dates: int = 150, per: int = 6) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    day = np.random.default_rng(99).normal(0, 0.5, n_dates)   # a market-wide day effect,
    dates = pd.bdate_range("2025-01-02", periods=n_dates).strftime("%Y-%m-%d")   # shared by
    rows = []                                                  # real and placebo (same dates)
    for i, d in enumerate(dates):
        shock = day[i]
        for _ in range(per):
            rows.append({"date": d, "d_pct20": effect + shock + rng.normal(0, 2.0)})
    return pd.DataFrame(rows)


def test_did_bootstrap_recovers_a_planted_effect_and_not_a_null():
    placebo = _cohort(0.0, 1)
    real = _cohort(1.0, 2)
    r = ZP.two_sample(placebo, real, "d_pct20", draws=2000)
    assert r["lo"] > 0 and r["hi"] > r["lo"] and ZP.verdict(r["lo"], r["hi"]) == "supports"
    null = ZP.two_sample(placebo, _cohort(0.0, 3), "d_pct20", draws=2000)
    assert null["lo"] < 0 < null["hi"] and ZP.verdict(null["lo"], null["hi"]) == "no_signal"
    inv = ZP.two_sample(placebo, _cohort(-1.0, 4), "d_pct20", draws=2000)
    assert ZP.verdict(inv["lo"], inv["hi"]) == "inverted"


def test_two_sample_is_cluster_boot_when_the_dates_match():
    X, Y = _cohort(0.0, 5, n_dates=40), _cohort(0.5, 6, n_dates=40)
    r = ZP.two_sample(X, Y, "d_pct20", draws=1000, seed=7)
    d = ES.cluster_boot(X, Y, "d_pct20", "date", 1000, 7)
    assert r["lo"] == pytest.approx(np.percentile(d, 2.5))
    assert r["hi"] == pytest.approx(np.percentile(d, 97.5))


def test_two_sample_keeps_y_only_dates_and_handles_empty():
    X = _cohort(0.0, 5, n_dates=40)
    Y = pd.concat([_cohort(0.5, 6, n_dates=40),
                   pd.DataFrame({"date": ["2030-01-01"] * 3, "d_pct20": [9.0, 9.0, 9.0]})])
    r = ZP.two_sample(X, Y, "d_pct20", draws=500)
    assert r["dates"] == 41 and np.isfinite(r["lo"])
    e = ZP.two_sample(X.iloc[:0], Y, "d_pct20")
    assert math.isnan(e["d"]) and math.isnan(e["lo"])


def test_mean_ci_and_verdict_negatives():
    D = _cohort(1.0, 8)
    m = ZP.mean_ci(D, "d_pct20", draws=1000)
    assert m["lo"] < m["mean"] < m["hi"] and m["n"] == len(D)
    assert math.isnan(ZP.mean_ci(D.iloc[:0], "d_pct20")["lo"])
    assert ZP.verdict(float("nan"), float("nan")) == "no_signal"
    assert ZP.verdict(None, None) == "no_signal"
    assert ZP.verdict(-0.1, 0.2) == "no_signal"


def test_quotable_rule():
    ok, why = ZP.quotable({"a": ZP.MIN_CELL_N, "b": 500}, ZP.QUOTABLE_MIN_DATES)
    assert ok and not why
    ok, why = ZP.quotable({"a": ZP.MIN_CELL_N - 1}, 200)
    assert not ok and "a n=119" in why[0]
    ok, why = ZP.quotable({"a": 500}, ZP.QUOTABLE_MIN_DATES - 1)
    assert not ok


def _q2_result(lo, hi, n=400, dates=150):
    arm = {"win": 24.0, "stop": 75.0, "mean_R": 0.2}
    return {"did": {"d": (lo + hi) / 2, "lo": lo, "hi": hi, "n_pairs": n, "n_x": n, "dates": dates},
            "arm_A": arm, "arm_B": {**arm, "stop": 70.0}}


@pytest.mark.parametrize("lo,hi,want", [(0.1, 0.9, "supports"), (-0.5, 0.4, "no_signal"),
                                        (-0.9, -0.2, "inverted")])
def test_emit_measured_literal_round_trips_through_zone_pad_measured(monkeypatch, lo, hi, want):
    m, why = ZP.measured_block(_q2_result(lo, hi), {"run_date": "2026-09-30", "universe": "store"})
    assert m is not None and not why
    lit = ZP.measured_literal(m)
    assert lit.startswith("MEASURED = ")
    parsed = ast.literal_eval(lit.split("=", 1)[1].strip())
    for k in ZP.MEASURED_KEYS:
        assert k in parsed
    monkeypatch.setattr(ZPM, "MEASURED", parsed)
    assert ZPM.status() == want
    line = ZPM.verdict_line()
    assert line.startswith("MEASURED 2026-09-30: %s" % want) and "[%+.2f, %+.2f]" % (lo, hi) in line
    assert "bounce" not in line.lower()


def test_emit_refuses_an_unquotable_or_undefined_run():
    m, why = ZP.measured_block(_q2_result(0.1, 0.9, n=50), {"run_date": "2026-09-30"})
    assert m is None and why
    m, why = ZP.measured_block(_q2_result(0.1, 0.9, dates=40), {"run_date": "2026-09-30"})
    assert m is None and any("dates" in w for w in why)
    m, why = ZP.measured_block(_q2_result(float("nan"), float("nan")), {"run_date": "2026-09-30"})
    assert m is None
    m, why = ZP.measured_block({"did": {}}, {"run_date": "2026-09-30"})
    assert m is None


def test_csv_bools_read_back_as_bools():
    s = pd.Series([True, False, "True", "False", np.nan, 1.0, 0.0])
    assert ZP._bool(s).tolist() == [True, False, True, False, False, True, False]


# ── source guards ────────────────────────────────────────────────────────────
def _src() -> str:
    return open(ZP.__file__).read()


def test_study_never_writes_mongo_or_calls_a_provider():
    src = _src()
    for bad in (".insert", ".update_one", ".update_many", ".replace_one", ".delete_", "bulk_write",
                "drop_collection", "fetch_bars", "requests.", "httpx", "massive"):
        assert bad not in src, bad


def test_study_types_no_pad_or_threshold():
    code = "\n".join(line.split("#", 1)[0] for line in _src().splitlines())
    assert not re.search(r"\*\s*0\.99\b", code)
    assert not re.search(r"1(\.0)?\s*-\s*0\.01\b", code)
    for typed in ("= 0.15", "= 12\n", "= 5.0", "= 0.5\n", "= 1.0\n", "= 120\n"):
        assert typed not in code, typed


def test_study_reuses_the_engines_it_names():
    src = _src()
    for use in ("ES.cluster_boot", "ES.placebo_dates", "ES.perm_p", "BQ._frame", "PZ.compute",
                "DR.zone_geom", "AG.demand_proximity_gate", "AG.approach_read", "AG.room_gate",
                "AG.sweep_read", "ETS.MIN_CELL_N", "SL.STOP_SHELF_PCT", "KL.YEAR_BARS"):
        assert use in src, use
    assert "level_pad" in src and "DEMAND_PAD_PCT = 0.0" in src   # arm A = pad off


def test_report_wording_never_says_bounce():
    strings = [n.value for n in ast.walk(ast.parse(_src()))
               if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    printed = [s for s in strings if "%" in s or s.startswith("\n")]
    assert printed
    for s in printed:
        assert "bounce" not in s.lower() and "fake" not in s.lower(), s
