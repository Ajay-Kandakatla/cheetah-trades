"""Study-side tests for scripts/entry_trigger_study.py (ENTERABLE spec §3A, the
22 pins). Everything runs WITHOUT Mongo on synthetic frames: the script must be
importable with no database, every trigger must be computable from closed bars
alone, and no future bar may ever change a fire decision.

The NEGATIVE cases are the point of half of them: a trigger that fires one bar
too late, a floor that broke before the confirmation, a higher low that bar k
itself undercut, a lift a hair under the imported threshold, a cell under the
120-row floor, a PC bucket that separates on all three splits and still must not
ship, and a benchmark that is not cached.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
import pytest

from scripts import entry_trigger_study as ETS
from scripts import explosive_study as ES
from studies import bounce_quality_study as BQ
from supply_demand import alert_gates as AG
from supply_demand import demand_reentry as DR
from supply_demand import premarket_entry as PE
from supply_demand import price_zones as PZ

CLOCKS = (5, 10, 20)
HOLD = 20


# ── fixtures ──────────────────────────────────────────────────────────────────
def _arrays(n: int = 60, base: float = 100.0):
    """A flat, benign frame: every bar closes at `base`, range base-1 .. base+1."""
    o = np.full(n, base, dtype=float)
    h = np.full(n, base + 1.0, dtype=float)
    l = np.full(n, base - 1.0, dtype=float)
    c = np.full(n, base, dtype=float)
    v = np.full(n, 500_000.0, dtype=float)
    return o, h, l, c, v


def _frame(n: int = 400, seed: int = 5, base: float = 100.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    step = rng.normal(0, 1.0, n)
    close = np.maximum(base + np.cumsum(step), 5.0)
    wick = np.abs(rng.normal(0, 0.8, n)) + 0.05
    op = close - step * 0.5
    dates = pd.bdate_range("2025-01-02", periods=n)
    return pd.DataFrame({"open": op, "high": close + wick, "low": close - wick,
                         "close": close, "volume": rng.integers(1e5, 1e6, n).astype(float),
                         "d": dates.strftime("%Y-%m-%d")})


def _cols(o, h, l, c, j, stop, band_hi=None, target=None, n=None):
    return ETS.convention_cols(o, h, l, c, j, n if n is not None else len(c), stop, target,
                               band_hi, CLOCKS, HOLD)


class _A:
    """The argparse namespace the stats helpers read."""
    boot_draws = 120
    perm_draws = 100
    placebo_draws = 100


# ═════════════════════════════════════════════════════════════════════════════
# 1 — constants imported, sets frozen
# ═════════════════════════════════════════════════════════════════════════════
def test_constants_are_imported_and_prereg_sets_are_frozen():
    assert ETS.FIVE_PCT is AG.ALERT_MIN_ROOM_PCT
    assert ETS.STOP_BUFFER_PCT is AG.STOP_BUFFER_PCT
    assert ETS.LIFT_PCT is PE.CONFIRM_MAX_LIFT_PCT
    assert ETS.WEAK_LO is PE.WEAK_DAY_LO_PCT and ETS.WEAK_HI is PE.WEAK_DAY_HI_PCT
    assert ETS.SMA_SHORT is AG.KNIFE_MA_LEN
    assert ETS.TOUCH_TOL is AG.APPROACH_TOUCH_TOL_PCT
    assert ETS.intact_replica is ES.intact_replica
    assert ETS.served_band is ES.served_band
    assert len(ETS.PREREG_P_TRIG) == 4 and len(set(ETS.PREREG_P_TRIG)) == 4
    assert len(ETS.PREREG_N_TRIG) == 15 and len(set(ETS.PREREG_N_TRIG)) == 15
    assert len(ETS.PREREG_PC_TRIG) == 14 and len(set(ETS.PREREG_PC_TRIG)) == 14
    assert "gap_up_next" not in ETS.PREREG_P_TRIG
    assert "gap_up_next" not in ETS.PREREG_PC_TRIG
    assert "gap_up_next" in ETS.PREREG_N_TRIG
    assert ETS.MIN_CELL_N == 120
    assert ETS.SHIP_ELIGIBLE_CONVENTIONS == ("P", "N")
    assert ETS.ship_eligible("PC") is False and ETS.ship_eligible("N") is True
    # the windows that are NOT his words carry their provenance in the source
    src = open(ETS.__file__).read()
    assert "brief 2026-09-15 — unconfirmed" in src
    # pin updated by the 2026-09-15 paste: the RESULTS block is filled from the
    # committed JSON, so it names that run's date and its status instead of
    # "pending" — and it still carries the survivor line, which is none.
    import os.path as _op
    _js = json.load(open(_op.join(_op.dirname(ETS.__file__),
                                  "entry_trigger_measured.json")))
    assert "RESULTS — %s" % _js["run_date"] in ETS.__doc__
    assert "STATUS: %s" % _js["status"] in ETS.__doc__
    assert "RESULTS — pending" not in ETS.__doc__


# ═════════════════════════════════════════════════════════════════════════════
# 2 — NEGATIVE: no future bar may change a fire decision
# ═════════════════════════════════════════════════════════════════════════════
def test_LOOKAHEAD_GUARD_future_bars_never_change_a_trigger():
    o, h, l, c, v = _arrays(60)
    j, stop, band_hi = 25, 97.0, 100.5
    c[26], h[26] = 100.4, 100.9                      # no C1 yet (c <= h[j] = 101)
    c[27], h[27] = 101.6, 102.0                      # C1 + L1 fire here
    l[28], h[28], c[28] = 99.4, 101.9, 101.5         # a higher low for HL
    c[31], h[31] = 102.5, 103.0                      # HL confirms here
    before = _cols(o, h, l, c, j, stop, band_hi, target=110.0)
    for key in ETS.ALL_CONV_KEYS:
        k = before.get("entry_bar_" + key)
        last = int(k) if k == k and k is not None and not np.isnan(k) else \
            j + (ETS.TRIGGER_WINDOW.get(key) or int(key[1:]) if key.startswith("D") else 1)
        if key in ETS.TRIGGER_KEYS and (k != k or k is None or np.isnan(k)):
            last = j + ETS.TRIGGER_WINDOW[key]
        o2, h2, l2, c2 = o.copy(), h.copy(), l.copy(), c.copy()
        for t in range(int(last) + 1, len(c2)):
            o2[t], h2[t], l2[t], c2[t] = 5.0, 500.0, 0.5, 400.0     # violent future
        after = _cols(o2, h2, l2, c2, j, stop, band_hi, target=110.0)
        for f in ("fired_", "entry_", "entry_bar_", "skip_reason_"):
            a, b = before[f + key], after[f + key]
            same = (a == b) or (isinstance(a, float) and isinstance(b, float)
                                and np.isnan(a) and np.isnan(b))
            assert same, (key, f, a, b)


# ═════════════════════════════════════════════════════════════════════════════
# 3 — NEGATIVE: a `_pre` feature may never read bar j
# ═════════════════════════════════════════════════════════════════════════════
def test_LOOKAHEAD_GUARD_pre_features_ignore_bar_j():
    f = _frame(300, seed=11)
    o = f["open"].to_numpy(float); h = f["high"].to_numpy(float)
    l = f["low"].to_numpy(float); c = f["close"].to_numpy(float)
    v = f["volume"].to_numpy(float)
    j = 250
    pre_before = {**ETS.volume_cols(v, c, j), "above_sma50_pre": ETS._sma_above(c, j, ETS.SMA_SHORT),
                  "above_sma200_pre": ETS._sma_above(c, j, ETS.SMA_LONG)}
    at_before = ETS.candle_cols(o, h, l, c, j)
    o2, h2, l2, c2, v2 = o.copy(), h.copy(), l.copy(), c.copy(), v.copy()
    o2[j], h2[j], l2[j], c2[j], v2[j] = c[j] * 0.9, c[j] * 1.3, c[j] * 0.8, c[j] * 1.25, v[j] * 9
    pre_after = {**ETS.volume_cols(v2, c2, j), "above_sma50_pre": ETS._sma_above(c2, j, ETS.SMA_SHORT),
                 "above_sma200_pre": ETS._sma_above(c2, j, ETS.SMA_LONG)}
    for k in ("rvol20_pre", "rvol50_pre", "updn_vol10_pre", "above_sma50_pre", "above_sma200_pre"):
        a, b = pre_before[k], pre_after[k]
        assert a == b or (a != a and b != b), k
    at_after = ETS.candle_cols(o2, h2, l2, c2, j)
    assert at_before["close_pos_at"] != at_after["close_pos_at"]      # the _at half DID move
    assert pre_before["rvol20_at"] != pre_after["rvol20_at"]


# ═════════════════════════════════════════════════════════════════════════════
# 4 — the entry is never before the trigger bar
# ═════════════════════════════════════════════════════════════════════════════
def test_entry_is_never_before_the_trigger_bar():
    o, h, l, c, v = _arrays(60)
    j, stop = 25, 97.0
    c[27], h[27] = 101.6, 102.0
    l[28], h[28], c[28] = 99.4, 101.9, 101.5
    c[31], h[31] = 102.5, 103.0
    o[26] = 100.9
    cols = _cols(o, h, l, c, j, stop, band_hi=100.5, target=115.0)
    assert cols["fired_N"] and cols["entry_N"] == o[j + 1]
    assert cols["entry_bar_N"] == j + 1
    for key in ETS.ALL_CONV_KEYS:
        if key in ("N", "PC") or not cols["fired_" + key]:
            continue
        kb = int(cols["entry_bar_" + key])
        assert kb >= j + 1, key
        assert cols["entry_" + key] == c[kb], key
    # PC is the MOC twin of P: the same close[j] entry, never a later bar
    assert cols["fired_PC"] and cols["entry_PC"] == c[j] and cols["entry_bar_PC"] == j


# ═════════════════════════════════════════════════════════════════════════════
# 5 — C1 + NEGATIVE (a close above one bar too late)
# ═════════════════════════════════════════════════════════════════════════════
def test_c1_fires_on_the_first_close_above_the_touch_high_within_3_bars():
    o, h, l, c, v = _arrays(60)
    j, stop = 25, 97.0
    c[26] = 100.9                                   # below h[j] = 101 -> no fire
    c[27] = 101.4                                   # first close above -> fire
    c[28] = 105.0
    k, why = ETS.trigger_c1(o, h, l, c, j, stop, None, ETS.C_WINDOW_BARS)
    assert (k, why) == (27, None)
    o2, h2, l2, c2, _ = _arrays(60)
    c2[29] = 101.4                                  # k = j+4 -> outside the window
    k2, why2 = ETS.trigger_c1(o2, h2, l2, c2, j, stop, None, ETS.C_WINDOW_BARS)
    assert k2 is None and why2 == "no_trigger"


# ═════════════════════════════════════════════════════════════════════════════
# 6 — NEGATIVE: the floor broke before (or on) the trigger bar
# ═════════════════════════════════════════════════════════════════════════════
def test_c1_does_not_fire_when_the_floor_broke_first_or_on_the_trigger_bar():
    o, h, l, c, v = _arrays(60)
    j, stop = 25, 97.0
    l[26] = 96.5                                    # the floor broke at j+1
    c[27] = 101.4
    k, why = ETS.trigger_c1(o, h, l, c, j, stop, None, ETS.C_WINDOW_BARS)
    assert k is None and why == "floor_broke_before_trigger"
    o2, h2, l2, c2, _ = _arrays(60)
    l2[27], c2[27] = 96.9, 101.4                    # the trigger bar itself broke it
    k2, why2 = ETS.trigger_c1(o2, h2, l2, c2, j, stop, None, ETS.C_WINDOW_BARS)
    assert k2 is None and why2 == "floor_broke_before_trigger"


# ═════════════════════════════════════════════════════════════════════════════
# 7 — C2 + NEGATIVE (no in-band close at j -> c2_na, every _C2 outcome NaN)
# ═════════════════════════════════════════════════════════════════════════════
def test_c2_needs_an_in_band_close_at_j_and_the_first_close_above_the_band_top():
    o, h, l, c, v = _arrays(60)
    j, stop, band_hi = 25, 97.0, 100.5
    c[26] = 100.2                                   # still under the band top
    c[27] = 100.8                                   # first close above -> fire
    assert ETS.trigger_c2(o, h, l, c, j, stop, band_hi, ETS.C_WINDOW_BARS) == (27, None)
    o2, h2, l2, c2, _ = _arrays(60)
    c2[j] = 101.0                                   # the touch bar closed ABOVE the band
    k, why = ETS.trigger_c2(o2, h2, l2, c2, j, stop, band_hi, ETS.C_WINDOW_BARS)
    assert k is None and why == "c2_na"
    cols = _cols(o2, h2, l2, c2, j, stop, band_hi, target=115.0)
    assert cols["c2_na"] is True and cols["fired_C2"] is False
    assert np.isnan(cols["hit5_20_C2"]) and np.isnan(cols["R20_C2"])
    assert np.isnan(cols["entry_C2"]) and cols["skip_reason_C2"] == "c2_na"


# ═════════════════════════════════════════════════════════════════════════════
# 8 — HL + NEGATIVES (a lower low; bar k itself undercuts l[j])
# ═════════════════════════════════════════════════════════════════════════════
def test_hl_requires_a_confirmed_higher_low_within_10_bars_including_the_trigger_bar():
    o, h, l, c, v = _arrays(60)
    j, stop = 25, 97.0                              # l[j] = 99.0
    l[26], h[26], c[26] = 99.5, 100.3, 100.0        # the higher low, m = 26
    l[27], c[27] = 99.8, 100.5                      # closes above h[26] -> fire at 27
    assert ETS.trigger_hl(o, h, l, c, j, stop, None, ETS.HL_WINDOW_BARS) == (27, None)
    o2, h2, l2, c2, _ = _arrays(60)
    l2[26], h2[26] = 98.5, 100.3                    # the post-touch low is LOWER than l[j]
    l2[27], c2[27] = 99.8, 100.5
    k2, why2 = ETS.trigger_hl(o2, h2, l2, c2, j, stop, None, ETS.HL_WINDOW_BARS)
    assert k2 is None and why2 == "no_trigger"
    o3, h3, l3, c3, _ = _arrays(60)
    l3[26], h3[26] = 99.5, 100.3
    l3[27], c3[27] = 98.4, 100.5                    # bar k undercuts l[j] while closing above h[m]
    l3[28], c3[28] = 99.8, 100.5                    # ... and the next bar cannot rescue it
    k3, why3 = ETS.trigger_hl(o3, h3, l3, c3, j, stop, None, ETS.HL_WINDOW_BARS)
    assert k3 is None and why3 == "no_trigger"


# ═════════════════════════════════════════════════════════════════════════════
# 9 — L1 fires at the IMPORTED lift and not a hair under
# ═════════════════════════════════════════════════════════════════════════════
def test_l1_fires_at_the_imported_lift_and_not_a_hair_under():
    o, h, l, c, v = _arrays(60)
    j, stop = 25, 97.0
    c[26] = c[j] * (1.0 + PE.CONFIRM_MAX_LIFT_PCT / 100.0)
    assert ETS.trigger_l1(o, h, l, c, j, stop, None, ETS.C_WINDOW_BARS) == (26, None)
    o2, h2, l2, c2, _ = _arrays(60)
    c2[26] = c2[j] * 1.00999
    c2[27] = c2[j] * 1.00999
    c2[28] = c2[j] * 1.00999
    k, why = ETS.trigger_l1(o2, h2, l2, c2, j, stop, None, ETS.C_WINDOW_BARS)
    assert k is None and why == "no_trigger"


# ═════════════════════════════════════════════════════════════════════════════
# 10 — NEGATIVE: a delay entry is skipped when the stop was hit first
# ═════════════════════════════════════════════════════════════════════════════
def test_delay_conventions_skip_when_the_stop_is_hit_before_the_entry():
    o, h, l, c, v = _arrays(60)
    j, stop = 25, 97.0
    l[26] = 96.0                                    # the floor broke at j+1
    cols = _cols(o, h, l, c, j, stop, band_hi=100.5, target=115.0)
    assert cols["fired_D2"] is False and cols["skip_reason_D2"] == "stopped_before_entry"
    assert cols["fired_D1"] is False
    for k in ETS.DELAYS_PLACEBO:
        assert ("fired_D%d" % k) in cols and ("hit5_20_D%d" % k) in cols
    o2, h2, l2, c2, _ = _arrays(60)
    l2[30] = 96.0                                   # the floor broke at j+5
    cols2 = _cols(o2, h2, l2, c2, j, stop, band_hi=100.5, target=115.0)
    assert cols2["fired_D4"] is True
    assert cols2["fired_D7"] is False and cols2["skip_reason_D7"] == "stopped_before_entry"


# ═════════════════════════════════════════════════════════════════════════════
# 11 — the outcome walk starts at the ENTRY bar, not the touch bar
# ═════════════════════════════════════════════════════════════════════════════
def test_outcomes_walk_from_the_entry_bar_not_the_touch_bar():
    o, h, l, c, v = _arrays(60)
    j, stop, band_hi, target = 25, 97.0, 100.5, 130.0
    h[26], c[26] = 107.0, 100.4                     # a +7% PRINT before the entry, no C1
    c[27] = 101.4                                   # C1 fires at j+2
    cols = _cols(o, h, l, c, j, stop, band_hi, target)
    k = int(cols["entry_bar_C1"])
    assert k == 27
    want = ES.outcome_block(h[k + 1:k + 21], l[k + 1:k + 21], c[k + 1:k + 21],
                            float(c[k]), stop, target, band_hi, CLOCKS, HOLD, suffix="_C1")
    assert cols["hit5_20_C1"] == want["hit5_20_C1"]
    assert cols["R20_C1"] == want["R20_C1"]
    assert cols["hit5_20_C1"] == 0.0                # the j+1 spike does NOT count
    p_blk = ES.outcome_block(h[j + 1:j + 21], l[j + 1:j + 21], c[j + 1:j + 21],
                             float(c[j]), stop, target, band_hi, CLOCKS, HOLD)
    assert p_blk["hit5_20"] == 1.0                  # ... but it does for the print entry P


# ═════════════════════════════════════════════════════════════════════════════
# 12 — the policy view prices the miss
# ═════════════════════════════════════════════════════════════════════════════
def test_policy_R_is_zero_for_unfired_and_R20_for_fired():
    D = pd.DataFrame({
        "fired_C1": [True, False, True], "R20_C1": [1.5, np.nan, -1.0],
        "hit5_20_C1": [1.0, np.nan, 0.0], "stop_20_C1": [0.0, np.nan, 1.0],
        "fired_D2": [True, True, False], "R20_D2": [1.5, 0.3, np.nan],
        "hit5_20_D2": [1.0, 0.0, np.nan], "stop_20_D2": [0.0, 0.0, np.nan]})
    out = ETS.add_policy(D, ["C1", "D2"], 20)
    assert out["R20_policy_C1"].tolist() == [1.5, 0.0, -1.0]
    assert out["hit5_20_policy_C1"].tolist() == [1.0, 0.0, 0.0]
    assert out["stop_20_policy_C1"].tolist() == [0.0, 0.0, 1.0]
    assert out["R20_policy_D2"].tolist() == [1.5, 0.3, 0.0]


# ═════════════════════════════════════════════════════════════════════════════
# 13 — NEGATIVE: a zero-price bar never reaches price_zones
# ═════════════════════════════════════════════════════════════════════════════
def test_zero_price_bars_are_dropped_before_any_band_is_drawn():
    f = _frame(60, seed=3)
    f.loc[10, "low"] = 0.0
    f.loc[20, "close"] = -1.0
    log = {"nonpos_names": 0, "nonpos_rows": 0}
    g = ES.drop_nonpositive(f, log)
    assert len(g) == len(f) - 2 and log["nonpos_rows"] == 2
    assert (g[["open", "high", "low", "close"]].to_numpy(dtype=float) > 0).all()
    src = open(ETS.__file__).read()
    assert "ES.frame_with_tail_rule" in src          # the replay uses the guarded loader
    assert "def drop_nonpositive" not in src         # and never re-implements it


# ═════════════════════════════════════════════════════════════════════════════
# 14 — NEGATIVE: cells under the 120 floor are hidden, not shown small
# ═════════════════════════════════════════════════════════════════════════════
def _cell_frame(n_fired_k1: int, n_fired_k2: int, n_unfired: int, key: str = "C1") -> pd.DataFrame:
    rows = []
    for i in range(n_fired_k1 + n_fired_k2 + n_unfired):
        k = 1 if i < n_fired_k1 else (2 if i < n_fired_k1 + n_fired_k2 else None)
        rows.append({"symbol": "S%03d" % (i % 40), "date": "2025-03-%02d" % (i % 28 + 1),
                     "bar_idx": 200, "fired_" + key: k is not None,
                     "entry_bar_" + key: 200 + k if k else np.nan,
                     "skip_reason_" + key: None if k else "no_trigger",
                     "fired_D1": True, "fired_D2": True,
                     "hit5_20_D1": float(i % 3 == 0), "hit5_20_D2": float(i % 3 == 0),
                     "stop_20_D1": float(i % 4 == 0), "stop_20_D2": float(i % 4 == 0),
                     "c2_na": False})
    return pd.DataFrame(rows)


def test_under_floor_cells_are_hidden():
    D = _cell_frame(0, 119, 400, key="C2")
    r = ETS.convention_block(D, "C2", HOLD, CLOCKS, _A(), "hit5", with_splits=False)
    assert r["verdict"] == "n<120 — not shown"
    assert "d_cond" not in r and "hit5_20" not in r
    # a k with fewer than 120 kept rows is dropped from the pool and listed
    D2 = _cell_frame(119, 200, 400, key="C1")
    cl = ETS.cond_cells(D2, "C1", ETS.C_WINDOW_BARS, HOLD)
    assert cl["ks"] == [2] and cl["dropped_k"] == [1]
    assert cl["weights"] == {2: 1.0} and cl["n_fired"] == 319


# ═════════════════════════════════════════════════════════════════════════════
# 15 — the stats stage runs with no Mongo and writes every MEASURED key
# ═════════════════════════════════════════════════════════════════════════════
def _synthetic_events(n_sym: int = 110, n_ev: int = 14, seed: int = 3) -> pd.DataFrame:
    """One row per (symbol, date) with every column the stats stage reads. The
    trigger rows obey the identity (a C1 that fires at k carries D_k's outcome)."""
    rng = np.random.default_rng(seed)
    dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2025-01-02", periods=420)]
    rows = []
    for s in range(n_sym):
        sym = "S%03d" % s
        off = int(rng.integers(0, 60))
        for i in range(n_ev):
            j = 130 + 25 * i + off
            entry = 50.0 + rng.uniform(0, 50)
            stop = entry * (1 - rng.uniform(0.01, 0.05))
            clear = rng.uniform() < 0.15
            target = None if clear else entry * (1 + rng.uniform(0.06, 0.2))
            surv = int(rng.integers(0, 11))                    # bars survived unstopped
            hit = float(rng.uniform() < 0.34)
            stp = float(rng.uniform() < 0.74) if hit == 0 else 0.0
            why = "stop" if stp else ("target" if (hit and not clear) else "clock")
            R = -1.0 if why == "stop" else rng.uniform(-0.5, 3.0)
            row = {"symbol": sym, "date": dates[j - 130], "bar_idx": j,
                   "dir": rng.choice(["bouncing", "falling"], p=[0.75, 0.25]),
                   "entry": entry, "stop": stop, "target": target, "clear": clear,
                   "room_pct": None if clear else (target / entry - 1) * 100,
                   "risk_pct": (entry - stop) / entry * 100, "trade_pct": R,
                   "R": R, "why": why, "knife": rng.uniform() < 0.3, "mood": rng.uniform(-50, 50),
                   "band_lo": stop / 0.995, "band_hi": stop / 0.995 * 1.02,
                   "served_lo": stop / 0.995, "served_hi": stop / 0.995 * 1.02,
                   "dvol50_pre": rng.lognormal(16, 1.5),
                   "close_pos_at": rng.uniform(), "lower_wick_at": rng.uniform(),
                   "body_at": rng.uniform(), "up_close_at": rng.uniform() < 0.5,
                   "close_gt_prev_high_at": rng.uniform() < 0.3, "engulf_at": rng.uniform() < 0.2,
                   "inside_at": rng.uniform() < 0.2, "gap_up_next": rng.uniform() < 0.3,
                   "weak_day_at": rng.uniform() < 0.2, "day_ret_at": rng.normal(0, 2),
                   "rvol20_at": rng.lognormal(0, 0.5), "rvol20_pre": rng.lognormal(0, 0.5),
                   "rvol50_pre": rng.lognormal(0, 0.5), "updn_vol10_pre": rng.lognormal(0, 0.5),
                   "vol_slope3_at": rng.normal(0, 1), "rvol_conf_C1": rng.lognormal(0, 0.5),
                   "above_sma50_pre": rng.uniform() < 0.5, "above_sma200_pre": rng.uniform() < 0.5,
                   "rs20_pre": rng.normal(1, 0.1),
                   "intact_state_at": rng.choice(["intact", "swept", "broken"]),
                   "k_5pct": np.nan, "k_stop": np.nan, "k_target": np.nan,
                   "max_gain_pct_20": rng.uniform(0, 12), "hit5c_20": hit,
                   "entry_N": entry, "gap_N": rng.uniform() < 0.05,
                   "risk_pct_N": (entry - stop) / entry * 100, "c2_na": rng.uniform() < 0.2}
            row["intact_at"] = row["intact_state_at"] == "intact"
            for cl in CLOCKS:
                row["hit5_%d" % cl] = hit
                row["hit5b_%d" % cl] = hit
                row["hit_lid_%d" % cl] = np.nan if clear else float(why == "target")
                row["stop_%d" % cl] = stp
                row["R%d" % cl] = R
                row["why%d" % cl] = why
                row["pct%d" % cl] = R
            # every convention
            fires = {}
            for key in ETS.TRIGGER_KEYS:
                w = ETS.TRIGGER_WINDOW[key]
                k = int(rng.integers(1, w + 1)) if rng.uniform() < 0.55 else None
                if k is not None and k > surv:
                    k = None
                fires[key] = k
            for key in ETS.ALL_CONV_KEYS:
                sfx = "_" + key
                if key == "N":
                    fired, kb = (not row["gap_N"]), j + 1
                elif key == "PC":
                    fired, kb = True, j
                elif key.startswith("D"):
                    kk = int(key[1:])
                    fired, kb = (kk <= surv), j + kk
                else:
                    fired, kb = (fires[key] is not None), (j + (fires[key] or 0))
                khit = float(rng.uniform() < 0.34)
                kstp = float(rng.uniform() < 0.7) if khit == 0 else 0.0
                kR = -1.0 if kstp else rng.uniform(-0.5, 3.0)
                if key in ETS.TRIGGER_KEYS and fired:
                    dk = "D%d" % fires[key]                 # THE IDENTITY
                    khit = row["hit5_20_" + dk]
                    kstp = row["stop_20_" + dk]
                    kR = row["R20_" + dk]
                row["fired" + sfx] = fired
                row["entry" + sfx] = entry if fired else np.nan
                row["entry_bar" + sfx] = float(kb) if fired else np.nan
                row["skip_reason" + sfx] = None if fired else "no_trigger"
                row["risk_pct" + sfx] = (entry - stop) / entry * 100 if fired else np.nan
                row["room_pct" + sfx] = (None if clear else (target / entry - 1) * 100) if fired else np.nan
                row["target_passed" + sfx] = False if fired else np.nan
                kind = ETS.conv_kind(key)
                clks = CLOCKS if kind == "full" else (HOLD,)
                for cl in sorted(set(clks) | {HOLD}):
                    row["hit5_%d%s" % (cl, sfx)] = khit if fired else np.nan
                    row["stop_%d%s" % (cl, sfx)] = kstp if fired else np.nan
                    row["R%d%s" % (cl, sfx)] = kR if fired else np.nan
                    if kind != "delay":
                        row["hit5b_%d%s" % (cl, sfx)] = khit if fired else np.nan
                        row["hit_lid_%d%s" % (cl, sfx)] = (np.nan if clear else float(kR > 0)) if fired else np.nan
                        row["why%d%s" % (cl, sfx)] = ("stop" if kstp else "clock") if fired else None
                if kind == "full":
                    row["hit5c_%d%s" % (HOLD, sfx)] = khit if fired else np.nan
                    row["max_gain_pct_%d%s" % (HOLD, sfx)] = rng.uniform(0, 12)
                    row["k_5pct" + sfx] = row["k_stop" + sfx] = row["k_target" + sfx] = np.nan
            # faithful to convention_cols: N's ONLY skip reason is the gap rule
            row["skip_reason_N"] = None if row["fired_N"] else "gap_N"
            row["entry_bar_c1_sweep"] = row["entry_bar_C1"]
            rows.append(row)
    X = pd.DataFrame(rows).drop_duplicates(["symbol", "date"]).reset_index(drop=True)
    X["episode"] = ES.flag_episodes(X, HOLD)
    X["episode_dir"] = ES.flag_episodes(X, HOLD, within="dir")
    return X


def _write(tmp_path, X, stride: int = 1, names: int = 0):
    csv = tmp_path / "ev.csv"
    X.to_csv(csv, index=False)
    with open(str(csv) + ".meta.json", "w") as fh:
        json.dump({"universe_mode": "broad", "n_universe": 200,
                   "symbols": sorted(X.symbol.unique().tolist()), "n_frames": 200,
                   "tail": {"today": 0, "phantom": 0}, "counters": {}, "floor": 120,
                   "stride": stride, "names": names}, fh)
    return csv



def test_stats_stage_runs_without_mongo_and_writes_every_measured_key(tmp_path):
    X = _synthetic_events()
    csv = _write(tmp_path, X)
    out = tmp_path / "m.json"
    ETS.main(["--stage", "stats", "--from-csv", str(csv), "--json", str(out),
              "--boot-draws", "120", "--perm-draws", "80", "--placebo-draws", "80"])
    m = json.load(open(out))
    for k in ("run_date", "universe_mode", "n_names", "n_events_all", "n_events_bouncing",
              "n_episodes", "n_episodes_N", "n_dates", "window", "floor", "clocks", "hold",
              "primary_outcome", "min_cell_n", "windows", "base", "delays", "conventions",
              "c1_window_sweep", "per_feature", "stratifiers", "interactions",
              "splits_features", "selected", "survivor", "status", "fallback",
              "survivorship", "liquidity_control", "script", "cohort_note",
              "intact_reconcile", "quotable", "quotable_reasons", "min_dvol_filter", "counters",
              "n_feature_nan", "feature_notes", "walltime_stats_s"):
        assert k in m, k
    assert m["script"] == "backend/scripts/entry_trigger_study.py"
    # UPDATED PIN (m1 2026-09-15): no --cache-csv and no --survivorship means the
    # survivorship replay is missing, and the flag now says so instead of True
    assert m["min_cell_n"] == 120 and m["quotable"] is False
    assert m["quotable_reasons"] == [ETS.SURVIVORSHIP_MISSING]
    assert m["windows"]["source"] == ETS.WINDOW_SOURCE
    assert m["status"] in ("separates", "no_signal", "pending")
    assert set(m["base"]) <= {"P", "N", "PC"} and "P" in m["base"]
    for key in ("N", "PC", "D1", "C1", "C2", "HL", "L1"):
        assert key in m["conventions"], key
    c1 = m["conventions"]["C1"]
    for k in ("n_fired", "fire_rate", "fire_bar_dist", "n_skipped", "n_base_k", "dropped_k",
              "hit5_20", "stop_20", "R20", "room_pct", "risk_pct", "d_cond", "ci_cond",
              "mdl_cond", "d_paired", "ci_paired", "d_raw", "ci_raw", "d_delay_only",
              "d_stop_cond", "ci_stop_cond", "d_cond_reweighted", "ci_rw", "policy_R20",
              "policy_R20_P", "d_policy_R", "ci_policy_R", "d_policy_R_vs_delay",
              "one_per_date", "one_per_symbol", "splits", "conditions", "verdict"):
        assert k in c1, k
    assert set(c1["splits"]) == {"s1", "s2", "s3"}
    assert all(p.get("ship_eligible") is False for p in m["per_feature"] if p["convention"] == "PC")
    # the decomposition the spec verifies: d_raw - Σ w_k·d_delay_only_k == d_cond
    assert abs(c1["decomp_gap"]) < 1e-6


# ═════════════════════════════════════════════════════════════════════════════
# 16a — THE IDENTITY: a fired trigger IS the matching delay entry on its own row
# ═════════════════════════════════════════════════════════════════════════════
def test_a_fired_trigger_IS_the_matching_delay_entry_on_its_own_row():
    o, h, l, c, v = _arrays(60)
    j, stop, band_hi, target = 25, 97.0, 100.5, 130.0
    c[26] = 100.4
    c[27] = 101.4                                    # C1 at k=2
    c[28] = 103.0
    for t in range(29, 60):
        c[t], h[t] = 104.0, 105.0
    l[30], h[30], c[30] = 99.6, 104.0, 103.5
    cols = _cols(o, h, l, c, j, stop, band_hi, target)
    assert cols["entry_bar_C1"] == 27
    assert cols["entry_C1"] == cols["entry_D2"]
    assert cols["hit5_20_C1"] == cols["hit5_20_D2"]
    assert cols["R20_C1"] == cols["R20_D2"]
    assert cols["stop_20_C1"] == cols["stop_20_D2"]
    # L1 and C2 land on their own delay too
    for key in ("L1", "C2"):
        if not cols["fired_" + key]:
            continue
        k = int(cols["entry_bar_" + key]) - j
        assert cols["entry_" + key] == cols["entry_D%d" % k]
        assert cols["hit5_20_" + key] == cols["hit5_20_D%d" % k]
    # and a HL that fires late lands on ITS delay
    o2, h2, l2, c2, _ = _arrays(80)
    for t in range(26, 80):
        c2[t], h2[t], l2[t] = 100.0, 101.0, 99.6
    l2[29], h2[29], c2[29] = 99.4, 100.2, 100.0
    c2[31], h2[31] = 100.5, 100.9
    cols2 = ETS.convention_cols(o2, h2, l2, c2, j, 80, stop, target, band_hi, CLOCKS, HOLD)
    if cols2["fired_HL"]:
        k = int(cols2["entry_bar_HL"]) - j
        assert cols2["entry_HL"] == cols2["entry_D%d" % k]
        assert cols2["hit5_20_HL"] == cols2["hit5_20_D%d" % k]


# ═════════════════════════════════════════════════════════════════════════════
# 16b — NEGATIVE: the contrast is fired vs UNFIRED survivors, never self-paired
# ═════════════════════════════════════════════════════════════════════════════
def test_conditional_contrast_compares_fired_rows_against_unfired_survivors(monkeypatch):
    monkeypatch.setattr(ETS, "MIN_CELL_N", 1)
    rows = []
    for i, (fired, y) in enumerate([(True, 1.0), (True, 1.0), (True, 0.0),
                                    (False, 0.0), (False, 0.0), (False, 1.0)]):
        rows.append({"symbol": "S%d" % i, "date": "2025-03-03", "bar_idx": 100,
                     "fired_C1": fired, "entry_bar_C1": 102.0 if fired else np.nan,
                     "fired_D1": True, "fired_D2": True, "fired_D3": True,
                     "hit5_20_D1": y, "hit5_20_D2": y, "hit5_20_D3": y})
    D = pd.DataFrame(rows)
    cl = ETS.cond_cells(D, "C1", ETS.C_WINDOW_BARS, HOLD)
    assert cl["ks"] == [2] and cl["weights"] == {2: 1.0}
    d = ETS.pooled_delta(D, cl, "hit5_20_D%d")
    assert d == pytest.approx(2.0 / 3.0 - 3.0 / 6.0, abs=1e-9)        # +0.1667
    # NEGATIVE: every survivor fired -> the contrast is 0 and undefined as evidence
    D2 = D.copy()
    D2["fired_C1"] = True
    D2["entry_bar_C1"] = 102.0
    cl2 = ETS.cond_cells(D2, "C1", ETS.C_WINDOW_BARS, HOLD)
    assert ETS.pooled_delta(D2, cl2, "hit5_20_D%d") == pytest.approx(0.0, abs=1e-12)


# ═════════════════════════════════════════════════════════════════════════════
# 16c — one date resample is SHARED across the fire bars
# ═════════════════════════════════════════════════════════════════════════════
def test_cond_boot_shares_one_date_resample_across_fire_bars(monkeypatch):
    rng = np.random.default_rng(1)
    rows = []
    for i in range(60):
        rows.append({"symbol": "S%d" % i, "date": "2025-03-%02d" % (i % 6 + 1),
                     "hit5_20_D1": float(i % 2), "hit5_20_D2": float(i % 3 == 0)})
    D = pd.DataFrame(rows)
    base = {1: pd.Series(True, index=D.index), 2: pd.Series(True, index=D.index)}
    kept = {1: pd.Series(np.arange(len(D)) % 2 == 0, index=D.index),
            2: pd.Series(np.arange(len(D)) % 3 == 0, index=D.index)}
    w = {1: 0.4, 2: 0.6}
    ycols = {1: "hit5_20_D1", 2: "hit5_20_D2"}
    calls = {"n": 0, "idx": None}
    keys = np.array(sorted(D["date"].unique()))

    class _Rng:
        def integers(self, lo, hi, size=None):
            calls["n"] += 1
            m, n = size
            idx = np.tile(np.arange(n), (m, 1))
            idx[:, 0] = 1                                   # a real, non-identity resample
            calls["idx"] = idx[0]
            return idx

    monkeypatch.setattr(np.random, "default_rng", lambda *a, **k: _Rng())
    d = ETS.cond_boot(D, ycols, base, kept, w, draws=5)
    assert calls["n"] == 1, "every fire bar must share ONE date resample per draw"
    # the hand computation under that same resample
    idx = calls["idx"]
    tot = 0.0
    for k, col in ycols.items():
        bs, bc = ES._by_key(D[base[k]], keys, col, "date")
        ks_, kc = ES._by_key(D[kept[k]], keys, col, "date")
        tot += w[k] * (ks_[idx].sum() / kc[idx].sum() - bs[idx].sum() / bc[idx].sum())
    assert d.size == 5 and d[0] == pytest.approx(tot, abs=1e-12)


# ═════════════════════════════════════════════════════════════════════════════
# 17 — NEGATIVE: the selection rule needs every condition, all three splits,
#      and can never pick a PC feature bucket
# ═════════════════════════════════════════════════════════════════════════════
def _conv(all_true: bool = True, split_bad: bool = False, a_false: bool = False) -> dict:
    cond = {"a_cond_beats_mdl": not a_false, "b_stop_not_raised": True,
            "c_reweighted_sign": True, "d_policy_not_worse": True,
            "e_one_per_date_symbol": True, "f_all_three_splits": not split_bad}
    if not all_true:
        cond["c_reweighted_sign"] = False
    return {"conditions": cond, "d_cond": 3.0, "ci_cond": [1.0, 5.0], "mdl_cond": 2.0,
            "d_policy_R": 0.11, "fire_rate": 0.4, "window_bars": 3,
            "splits": {"s1": {"verdict": "separates" if not split_bad else "no_signal"},
                       "s2": {"verdict": "separates"}, "s3": {"verdict": "separates"}}}


def test_selection_rule_needs_every_condition_and_all_three_splits_and_never_picks_PC():
    sel, surv = ETS.select_survivor({"C1": _conv()}, [], {})
    assert sel == ["C1"] and surv["key"] == "C1" and surv["type"] == "convention"
    sel, surv = ETS.select_survivor({"C1": _conv(a_false=True)}, [], {})
    assert sel == [] and surv is None
    sel, surv = ETS.select_survivor({"C1": _conv(split_bad=True)}, [], {})
    assert sel == [] and surv is None
    sel, surv = ETS.select_survivor({"C1": _conv(all_true=False)}, [], {})
    assert sel == [] and surv is None
    # a PC bucket that separates on all three splits must NOT ship
    pf = [{"name": "close_pos_at", "convention": "PC"}]
    spl = {"PC": {"s1": {"verdict": "separates", "selected": ["close_pos_at"]},
                  "s2": {"verdict": "separates"}, "s3": {"verdict": "separates"}}}
    sel, surv = ETS.select_survivor({}, pf, spl)
    assert sel == [] and surv is None
    assert pf[0]["ship_eligible"] is False
    # the same table under N DOES ship
    spl_n = {"N": {"s1": {"verdict": "separates", "selected": ["close_pos_at"], "mdl": 2.0},
                   "s2": {"verdict": "separates"}, "s3": {"verdict": "separates"}}}
    sel, surv = ETS.select_survivor({}, [{"name": "close_pos_at", "convention": "N"}], spl_n)
    assert sel == ["N:close_pos_at"] and surv["type"] == "feature"


# ═════════════════════════════════════════════════════════════════════════════
# 18 — the candle features are their formulas
# ═════════════════════════════════════════════════════════════════════════════
def test_candle_features_match_their_formulas_on_a_hand_built_bar():
    o = np.array([9.0, 10.0]); h = np.array([11.5, 12.0])
    l = np.array([8.5, 9.0]); c = np.array([9.5, 11.5])
    r = ETS.candle_cols(o, h, l, c, 1)
    assert r["close_pos_at"] == pytest.approx((11.5 - 9.0) / 3.0)        # 0.8333
    assert r["lower_wick_at"] == pytest.approx((10.0 - 9.0) / 3.0)       # 0.3333
    assert r["body_at"] == pytest.approx(1.5 / 3.0)                      # 0.5
    assert r["up_close_at"] is True
    assert r["close_gt_prev_high_at"] is False                           # 11.5 < 11.5 is False
    assert r["engulf_at"] is False                                       # the prior bar closed UP
    assert r["inside_at"] is False
    o2 = np.array([10.0, 9.1]); h2 = np.array([10.2, 11.0])
    l2 = np.array([9.0, 9.2]); c2 = np.array([9.2, 10.4])
    r2 = ETS.candle_cols(o2, h2, l2, c2, 1)
    assert r2["engulf_at"] is True                                       # down bar fully engulfed
    # a zero-range bar has no shape
    r3 = ETS.candle_cols(np.array([5.0, 5.0]), np.array([5.0, 5.0]),
                         np.array([5.0, 5.0]), np.array([5.0, 5.0]), 1)
    assert np.isnan(r3["close_pos_at"]) and np.isnan(r3["body_at"])
    # the weak-day band is the IMPORTED one
    o4 = np.array([100.0, 95.0]); h4 = np.array([101.0, 96.0])
    l4 = np.array([99.0, 94.0]); c4 = np.array([100.0, 95.0])
    assert ETS.candle_cols(o4, h4, l4, c4, 1)["weak_day_at"] is True     # -5% is in [-8, -3]
    c5 = np.array([100.0, 99.0])
    assert ETS.candle_cols(o4, h4, l4, c5, 1)["weak_day_at"] is False    # -1% is not


# ═════════════════════════════════════════════════════════════════════════════
# 19 — the RESULTS block is pending until the run fills it
# ═════════════════════════════════════════════════════════════════════════════
def test_docstring_results_block_is_pending_or_equals_the_json():
    doc = ETS.__doc__
    assert "RESULTS" in doc
    tail = doc[doc.index("RESULTS"):]
    assert tail.startswith("RESULTS — pending") or "cohort:" in tail
    assert "DEVIATIONS" in doc and "bucket_stats" in doc
    assert "backend/scripts/entry_trigger_study.py" in ETS.SCRIPT


# ═════════════════════════════════════════════════════════════════════════════
# 20 — a strided run is never quotable and says so
# ═════════════════════════════════════════════════════════════════════════════
def test_smoke_banner_and_quotable_flag(tmp_path, capsys):
    X = _synthetic_events(n_sym=8, n_ev=4, seed=9)
    csv = _write(tmp_path, X, stride=2)
    out = tmp_path / "m.json"
    ETS.main(["--stage", "stats", "--from-csv", str(csv), "--json", str(out),
              "--stride", "2", "--boot-draws", "60", "--perm-draws", "40",
              "--placebo-draws", "40"])
    printed = capsys.readouterr().out
    assert "NOT QUOTABLE" in printed
    m = json.load(open(out))
    assert m["quotable"] is False


# ═════════════════════════════════════════════════════════════════════════════
# 21 — event_at IS the engine's event (the mirror the live reader depends on)
# ═════════════════════════════════════════════════════════════════════════════
def test_event_at_reproduces_BQ_events_band_stop_and_target_on_a_synthetic_frame():
    f = _frame(320, seed=17)
    o = f["open"].to_numpy(float); h = f["high"].to_numpy(float)
    l = f["low"].to_numpy(float); c = f["close"].to_numpy(float)
    geom = DR.zone_geom()
    checked = 0
    for j in range(260, 300):
        z = PZ.compute(f.iloc[max(0, j - 252):j], last_price=float(c[j]), max_zones=None, **geom)
        if not z:
            continue
        bands = (z.get("supply_zones") or []) + (z.get("demand_zones") or [])
        # ── the DIRECT replay of bounce_quality_study.py:467-489 ──
        px, prev, day_low = float(c[j]), float(c[j - 1]), float(l[j])
        hits = []
        for b in (z.get("demand_zones") or []):
            if not AG.demand_proximity_gate(px, b):
                continue
            if not isinstance(AG.approach_read(px, b, prev, day_low), dict):
                continue
            hits.append((float(b["lo"]), b))
        want = None
        if hits:
            band_lo, band = max(hits, key=lambda t: t[0])
            ok_room, room = AG.room_gate(px, bands, prev)
            if ok_room:
                stop = float(band["lo"]) * (1.0 - AG.STOP_BUFFER_PCT / 100.0)
                if px > stop:
                    want = (float(band["lo"]), float(band["hi"]), stop,
                            float(room["target"]) if room else None)
        got = ETS.event_at(o, h, l, c, j, bands)
        if want is None:
            assert got is None, j
        else:
            assert got is not None, j
            assert (float(got["band"]["lo"]), float(got["band"]["hi"]), got["stop"],
                    got["target"]) == want
            checked += 1
    assert checked >= 1, "the synthetic frame produced no event to mirror"


# ═════════════════════════════════════════════════════════════════════════════
# 22 — NEGATIVE: no RSP in the cache -> rs20_pre is all-NaN and counted
# ═════════════════════════════════════════════════════════════════════════════
def test_rs20_pre_is_all_nan_and_counted_when_rsp_is_absent():
    f = _frame(300, seed=23)
    c = f["close"].to_numpy(float)
    ev = pd.DataFrame([{"date": f["d"].iloc[j], "entry": float(c[j]),
                        "stop": float(c[j]) * 0.95, "target": float(c[j]) * 1.15}
                       for j in (200, 210, 220)])
    counters = {"no_bar": 0, "no_band": 0, "band_mismatch": 0, "no_frame": 0}
    rows = ETS.features_for_symbol("AAA", f, ev, HOLD, CLOCKS, DR.zone_geom(), counters, rsp=None)
    assert rows, "the synthetic frame produced no feature rows"
    assert all(r["rs20_pre"] != r["rs20_pre"] for r in rows)        # every one NaN
    X = pd.DataFrame(rows)
    assert int(X["rs20_pre"].isna().sum()) == len(X)
    # with a benchmark present it IS measured
    rsp = {str(d): 50.0 + i * 0.05 for i, d in enumerate(f["d"].tolist())}
    rows2 = ETS.features_for_symbol("AAA", f, ev, HOLD, CLOCKS, DR.zone_geom(), counters, rsp=rsp)
    assert any(r["rs20_pre"] == r["rs20_pre"] for r in rows2)


# ═════════════════════════════════════════════════════════════════════════════
# 23 — m1: `quotable` is the SAMPLE test AND the survivorship replay, never one
#      of them. A True beside an all-None survivorship block contradicted the
#      report's own "NO NUMBER ABOVE IS QUOTABLE WITHOUT THE CACHE LINE" banner.
# ═════════════════════════════════════════════════════════════════════════════
def _cache_csv(tmp_path, X, hit=0.40, stop=0.70, n_names=40, name="cache.csv"):
    """A cache-universe events CSV in the shape `survivorship_read` reads."""
    rows = []
    for i in range(n_names * 4):
        rows.append({"symbol": "C%03d" % (i % n_names), "date": X["date"].iloc[i % len(X)],
                     "dir": "bouncing", "episode_dir": True,
                     "hit5_20": float(i % 100 < hit * 100), "stop_20": float(i % 100 < stop * 100),
                     "R20": 0.1})
    p = tmp_path / name
    pd.DataFrame(rows).to_csv(p, index=False)
    return p


def test_quotable_is_false_without_the_survivorship_replay_and_says_why(tmp_path, capsys):
    """NEGATIVE: a full-universe stats run with NO cache line is NOT quotable."""
    X = _synthetic_events(n_sym=40, n_ev=6, seed=11)
    csv = _write(tmp_path, X)
    out = tmp_path / "m.json"
    ETS.main(["--stage", "stats", "--from-csv", str(csv), "--json", str(out),
              "--boot-draws", "60", "--perm-draws", "40", "--placebo-draws", "40"])
    printed = capsys.readouterr().out
    m = json.load(open(out))
    assert m["quotable"] is False
    assert m["quotable_reasons"] == [ETS.SURVIVORSHIP_MISSING]
    assert m["survivorship"]["cache_hit5_20"] is None
    assert "NO NUMBER ABOVE IS QUOTABLE WITHOUT THE CACHE LINE" in printed
    assert "NOT QUOTABLE — " + ETS.SURVIVORSHIP_MISSING in printed   # the verdict line agrees


def test_quotable_is_true_only_when_both_halves_hold(tmp_path):
    """POSITIVE: the same run WITH the cache line is quotable; a strided run with
    the cache line is still not (both reasons are listed, never one)."""
    X = _synthetic_events(n_sym=40, n_ev=6, seed=11)
    csv = _write(tmp_path, X)
    cache = _cache_csv(tmp_path, X)
    out = tmp_path / "m.json"
    ETS.main(["--stage", "stats", "--from-csv", str(csv), "--json", str(out),
              "--cache-csv", str(cache), "--boot-draws", "60", "--perm-draws", "40",
              "--placebo-draws", "40"])
    m = json.load(open(out))
    assert m["quotable"] is True and m["quotable_reasons"] == []
    assert m["survivorship"]["cache_hit5_20"] is not None
    assert m["survivorship"]["cache_n_names"] == 40

    strided = _write(tmp_path, X, stride=3)
    out2 = tmp_path / "m2.json"
    ETS.main(["--stage", "stats", "--from-csv", str(strided), "--json", str(out2),
              "--cache-csv", str(cache), "--stride", "3", "--boot-draws", "60",
              "--perm-draws", "40", "--placebo-draws", "40"])
    m2 = json.load(open(out2))
    assert m2["quotable"] is False
    assert m2["quotable_reasons"] == [ETS.SUBSAMPLE_NOT_QUOTABLE]


# ═════════════════════════════════════════════════════════════════════════════
# 24 — the survivorship replay is a SEPARATE run, so stats MERGES its result
# ═════════════════════════════════════════════════════════════════════════════
def test_survivorship_is_parked_beside_the_cache_and_merged_by_a_later_run(tmp_path):
    X = _synthetic_events(n_sym=40, n_ev=6, seed=13)
    csv = _write(tmp_path, X)
    cache = _cache_csv(tmp_path, X)
    out = tmp_path / "m.json"
    ETS.main(["--stage", "stats", "--from-csv", str(csv), "--json", str(out),
              "--cache-csv", str(cache), "--boot-draws", "60", "--perm-draws", "40",
              "--placebo-draws", "40"])
    park = str(cache) + ETS.SURVIVORSHIP_SUFFIX
    assert os.path.exists(park), "the computed block was not parked beside the cache"
    first = json.load(open(out))["survivorship"]
    assert first["source"].startswith("cache-csv:")

    # (a) an explicit --survivorship merges it, with NO cache CSV in sight
    out2 = tmp_path / "m2.json"
    ETS.main(["--stage", "stats", "--from-csv", str(csv), "--json", str(out2),
              "--survivorship", park, "--boot-draws", "60", "--perm-draws", "40",
              "--placebo-draws", "40"])
    m2 = json.load(open(out2))
    assert m2["quotable"] is True and m2["quotable_reasons"] == []
    assert m2["survivorship"]["source"] == "merged:" + park
    assert m2["survivorship"]["cache_hit5_20"] == first["cache_hit5_20"]
    assert m2["survivorship"]["cache_n_names"] == first["cache_n_names"]
    # d_hit5_vs_broad is RECOMPUTED against this run's own broad base, never carried
    assert abs(m2["survivorship"]["d_hit5_vs_broad"]
               - (m2["survivorship"]["cache_hit5_20"] - m2["base"]["P"]["hit5_20"])) < 1e-9

    # (b) --cache-csv pointing at a CSV that is gone falls back to the sidecar
    os.remove(str(cache))
    out3 = tmp_path / "m3.json"
    ETS.main(["--stage", "stats", "--from-csv", str(csv), "--json", str(out3),
              "--cache-csv", str(cache), "--boot-draws", "60", "--perm-draws", "40",
              "--placebo-draws", "40"])
    assert json.load(open(out3))["survivorship"]["source"] == "merged:" + park


def test_survivorship_merge_refuses_a_block_with_no_cache_line(tmp_path, capsys):
    """NEGATIVE: an empty / half-written sidecar is NOT a survivorship replay."""
    X = _synthetic_events(n_sym=40, n_ev=6, seed=17)
    csv = _write(tmp_path, X)
    bad = tmp_path / "empty.survivorship.json"
    with open(bad, "w") as fh:
        json.dump({"cache_n_names": 1200, "cache_hit5_20": None}, fh)
    out = tmp_path / "m.json"
    ETS.main(["--stage", "stats", "--from-csv", str(csv), "--json", str(out),
              "--survivorship", str(bad), "--boot-draws", "60", "--perm-draws", "40",
              "--placebo-draws", "40"])
    printed = capsys.readouterr().out
    m = json.load(open(out))
    assert m["quotable"] is False and m["quotable_reasons"] == [ETS.SURVIVORSHIP_MISSING]
    assert m["survivorship"]["cache_n_names"] is None      # the bad block is not half-merged
    assert "carries no cache_hit5_20" in printed
    assert ETS.survivorship_present({"cache_hit5_20": None}) is False
    assert ETS.survivorship_present({"cache_hit5_20": 31.4}) is True
    assert ETS.survivorship_present(None) is False


# ═════════════════════════════════════════════════════════════════════════════
# 25 — study_verdict deviation (2): N is SCORED on the gapless rows but REPORTED
#      over the whole episode cohort; the gap_N episodes are skips, not a vanish
# ═════════════════════════════════════════════════════════════════════════════
def test_N_fire_rate_and_n_skipped_count_the_episodes_dropped_by_gap_N(tmp_path):
    X = _synthetic_events(n_sym=60, n_ev=8, seed=19)
    csv = _write(tmp_path, X)
    out = tmp_path / "m.json"
    ETS.main(["--stage", "stats", "--from-csv", str(csv), "--json", str(out),
              "--boot-draws", "60", "--perm-draws", "40", "--placebo-draws", "40"])
    m = json.load(open(out))
    n_ep, n_epN = m["n_episodes"], m["n_episodes_N"]
    assert n_epN < n_ep, "the fixture produced no gap_N episodes — nothing to pin"
    N = m["conventions"]["N"]
    assert N["n_base"] == n_ep                       # the FULL cohort, not the gapless frame
    assert N["n_fired"] == n_epN
    assert sum(N["n_skipped"].values()) == n_ep - n_epN
    assert N["n_skipped"]["gap_N"] == n_ep - n_epN
    # the fire rate reflects them: strictly under 1.0, and exactly n_fired / n_base
    assert N["fire_rate"] < 1.0
    assert abs(N["fire_rate"] - n_epN / n_ep) < 1e-12
    # NEGATIVE: the un-based read (over the gapless frame) is the bug — 1.000
    assert abs(N["n_fired"] / n_epN - 1.0) < 1e-12
    # every other convention is untouched: its base IS the frame it is scored on
    assert m["conventions"]["C1"]["n_base"] == n_ep


def test_excluded_skips_counts_by_the_rows_own_reason_and_is_empty_when_nothing_dropped():
    D = pd.DataFrame({"gap_N": [True, True, False, False],
                      "skip_reason_N": ["gap_N", None, None, None]})
    kept = D["gap_N"] == False                                          # noqa: E712
    assert ETS.excluded_skips(D, kept, "skip_reason_N", "gap_N") == {"gap_N": 2}
    # NEGATIVE: nothing excluded -> no phantom skip line
    assert ETS.excluded_skips(D, pd.Series([True] * 4), "skip_reason_N", "gap_N") == {}
    # NEGATIVE: no reason column -> the fallback label, never a KeyError
    assert ETS.excluded_skips(D[["gap_N"]], kept, "skip_reason_N", "gap_N") == {"gap_N": 2}


# ═════════════════════════════════════════════════════════════════════════════
# 26 — study_verdict deviation (3): the C1 window sweep drops the same no_bars
#      rows conventions.C1 drops, so the two n_fired agree at the C1 window
# ═════════════════════════════════════════════════════════════════════════════
def test_c1_window_sweep_excludes_the_same_no_bars_rows_as_convention_C1(tmp_path):
    X = _synthetic_events(n_sym=60, n_ev=8, seed=23)
    # make some C1 fires unusable the way a short frame tail does: the delay-k
    # entry has no forward bars, so close_entry_cols marked fired_D<k> False
    k = pd.to_numeric(X["entry_bar_c1_sweep"], errors="coerce") - pd.to_numeric(X["bar_idx"], errors="coerce")
    victims = X.index[(k == 1) & X["fired_C1"].fillna(False).astype(bool)][:25]
    assert len(victims) >= 5, "the fixture produced no k=1 C1 fires to blind"
    for col, val in (("fired_C1", False), ("fired_D1", False)):
        X.loc[victims, col] = val
    for col in ("skip_reason_C1", "skip_reason_D1"):
        X.loc[victims, col] = "no_bars"
    for c in [c for c in X.columns if c.endswith("_C1") or c.endswith("_D1")]:
        if c.startswith(("hit5", "stop", "R", "hit_lid")):
            X.loc[victims, c] = np.nan
    csv = _write(tmp_path, X)
    out = tmp_path / "m.json"
    ETS.main(["--stage", "stats", "--from-csv", str(csv), "--json", str(out),
              "--boot-draws", "60", "--perm-draws", "40", "--placebo-draws", "40"])
    m = json.load(open(out))
    sweep = m["c1_window_sweep"][str(ETS.C_WINDOW_BARS)]
    assert sweep["n_fired"] == m["conventions"]["C1"]["n_fired"]
    # NEGATIVE: the blinded rows ARE in the raw sweep column — they are excluded on
    # purpose, and the count of what was excluded is reported rather than hidden
    assert sweep["n_no_bars"] > 0
    assert sweep["note"].endswith("no_bars rows excluded as conventions.C1 does")


# ═════════════════════════════════════════════════════════════════════════════
# 27 — study_verdict deviation (4): family 5 never prints "separates"
# ═════════════════════════════════════════════════════════════════════════════
def test_interaction_cells_read_cushion_or_not_selected_never_separates():
    # NEGATIVE first: no CI, a NaN CI and a CI that straddles zero are all "not selected"
    assert ETS.inter_verdict(None) == ETS.INTER_NOT_SELECTED
    assert ETS.inter_verdict(float("nan")) == ETS.INTER_NOT_SELECTED
    assert ETS.inter_verdict(-0.4) == ETS.INTER_NOT_SELECTED
    assert ETS.inter_verdict(0.0) == ETS.INTER_NOT_SELECTED
    # (a) alone is a cushion, never a selection
    assert ETS.inter_verdict(2.5) == ETS.INTER_CUSHION
    # (c) the reweight, when the cell has one, must keep the sign
    assert ETS.inter_verdict(2.5, d_rw=1.2, ci_rw=[0.4, 2.0]) == ETS.INTER_CUSHION
    assert ETS.inter_verdict(2.5, d_rw=-1.2, ci_rw=[-3.0, 0.4]) == ETS.INTER_NOT_SELECTED
    assert ETS.inter_verdict(2.5, d_rw=1.2, ci_rw=[-0.4, 2.0]) == ETS.INTER_NOT_SELECTED
    assert ETS.inter_verdict(2.5, d_rw=None, ci_rw=[None, None]) == ETS.INTER_NOT_SELECTED
    # (d) policy not worse
    assert ETS.inter_verdict(2.5, d_policy=-0.31) == ETS.INTER_NOT_SELECTED
    assert ETS.inter_verdict(2.5, d_policy=0.0) == ETS.INTER_CUSHION
    # the word the conventions own is never produced here
    for args in ((5.0,), (5.0, 2.0, [1.0, 3.0]), (None,), (-1.0,)):
        assert ETS.inter_verdict(*args) != "separates"


def test_interactions_table_never_serves_separates_on_a_real_run(tmp_path):
    X = _synthetic_events(n_sym=60, n_ev=8, seed=29)
    csv = _write(tmp_path, X)
    out = tmp_path / "m.json"
    ETS.main(["--stage", "stats", "--from-csv", str(csv), "--json", str(out),
              "--boot-draws", "60", "--perm-draws", "40", "--placebo-draws", "40"])
    inter = json.load(open(out))["interactions"]
    assert inter, "the fixture produced no interaction cells"
    allowed = {ETS.INTER_CUSHION, ETS.INTER_NOT_SELECTED, "n<%d — not shown" % ETS.MIN_CELL_N}
    for cell in inter:
        assert cell["verdict"] in allowed, cell
    # and a cushion never reaches the selection: survivor comes from the conventions
    assert json.load(open(out))["status"] in ("separates", "no_signal")
