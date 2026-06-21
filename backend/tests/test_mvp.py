"""MVP indicator (David Ryan's "ants") + the base-stage-aware buy gate.

Methodology: Minervini, *Think & Trade Like a Champion* (TTLAC) §1 ebook p.33
(the 12/15 · +25% vol · +20% price footprint) + §9 p.199 (reverse/sell use) +
§9 ~p.200 (bases 3-4 tradeable, 5-6 sell). See docs/sepa/mvp_methodology.md.

Two layers:
  1. sepa.mvp.compute — the pure footprint + near-base-bottom origin fact.
  2. scanner gate — base 3-4 now tradeable (avoid only ≥5); MVP exhaustion
     blocks; near-base-bottom MVP overrides the 3% extension cap.

  cd backend && .venv/bin/python -m pytest tests/test_mvp.py -q
"""
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd

from sepa import mvp


def _df(closes, vols, lows=None):
    lows = lows if lows is not None else [c * 0.99 for c in closes]
    return pd.DataFrame({"open": closes, "high": [c * 1.01 for c in closes],
                         "low": lows, "close": closes, "volume": vols})


# 15 daily deltas summing to +25 with `n_up` of them positive (ends at 125 from 100).
def _window_path(start, n_up=13):
    n_down = 15 - n_up
    up = (25 + n_down * 0.5) / n_up            # each up step
    deltas = [up] * n_up + [-0.5] * n_down     # n_up ups, rest small downs
    px = [start]
    for d in deltas:
        px.append(round(px[-1] + d * (start / 100.0), 4))
    return px                                   # length 16 (start + 15 steps)


def _series(base_level, base_n, window_start, n_up=13, base_vol=1_000_000, win_vol=2_000_000):
    base = [float(base_level)] * base_n
    win = _window_path(window_start, n_up=n_up)
    closes = base + win
    vols = [base_vol] * (base_n + 1) + [win_vol] * 15   # window = last 15 bars
    return closes, vols


# ── compute() ────────────────────────────────────────────────────────────────

def test_clean_mvp_continuation_off_base():
    closes, vols = _series(100, 50, 100, n_up=13)       # window starts at the base
    out = mvp.compute(_df(closes, vols))
    assert out["has_mvp"] is True
    assert out["up_days"] >= mvp.MVP_UP_DAYS_MIN
    assert out["price_pct"] >= mvp.MVP_PRICE_PCT_MIN
    assert out["volume_pct"] >= mvp.MVP_VOLUME_PCT_MIN
    assert out["near_base_bottom"] is True              # window began at the base low


def test_extended_mvp_not_near_base_bottom():
    # Same footprint but the 15-day window starts well ABOVE the base low.
    closes, vols = _series(100, 50, 150, n_up=13)
    out = mvp.compute(_df(closes, vols))
    assert out["has_mvp"] is True
    assert out["near_base_bottom"] is False             # started extended, not off the bottom


def test_no_mvp_when_flat():
    closes = [100.0] * 70
    vols = [1_000_000] * 70
    out = mvp.compute(_df(closes, vols))
    assert out["has_mvp"] is False
    assert out["up_days"] == 0


def test_momentum_gate_blocks_below_12_up_days():
    closes, vols = _series(100, 50, 100, n_up=11)        # only 11 of 15 up
    out = mvp.compute(_df(closes, vols))
    assert out["up_days"] == 11
    assert out["has_mvp"] is False                       # fails the 12/15 gate


def test_volume_gate_blocks_when_volume_flat():
    # Price + momentum qualify, but volume did NOT step up (no +25%).
    closes, vols = _series(100, 50, 100, n_up=13, base_vol=1_000_000, win_vol=1_000_000)
    out = mvp.compute(_df(closes, vols))
    assert out["price_pct"] >= mvp.MVP_PRICE_PCT_MIN
    assert out["volume_pct"] < mvp.MVP_VOLUME_PCT_MIN
    assert out["has_mvp"] is False


def test_insufficient_data_returns_none():
    assert mvp.compute(_df([100.0] * 10, [1_000_000] * 10)) is None
    assert mvp.compute(None) is None


# ── scanner gate (base-stage-aware + MVP exceptions) ─────────────────────────

def _tr(pass_all=True):
    return types.SimpleNamespace(pass_all=pass_all)


_STG2 = {"stage": 2}
_LIQ = {"liquid": True}
_VOL_BREAKOUT = {"high_vol_breakout": True}
_SETUP = {"type": "VCP", "pivot": 100.0, "stop": 93.0}


def test_base_4_now_passes_setup_ready():
    from sepa import scanner as S
    # base 4 = is_late_stage True but is_avoid_stage False -> still tradeable.
    bc = {"base_count": 4, "is_late_stage": True, "is_avoid_stage": False}
    assert S._is_setup_ready(_tr(), _STG2, bc, _LIQ, _SETUP) is True


def test_base_5_blocked_by_avoid_stage():
    from sepa import scanner as S
    bc = {"base_count": 5, "is_late_stage": True, "is_avoid_stage": True}
    assert S._is_setup_ready(_tr(), _STG2, bc, _LIQ, _SETUP) is False


def test_exhaustion_blocks_setup_ready_and_buyable():
    from sepa import scanner as S
    bc = {"base_count": 2, "is_late_stage": False, "is_avoid_stage": False}
    assert S._is_setup_ready(_tr(), _STG2, bc, _LIQ, _SETUP, exhaustion=True) is False
    assert S._is_buyable(_tr(), _STG2, bc, _LIQ, _VOL_BREAKOUT, _SETUP, 100.0,
                         mvp={"has_mvp": True, "near_base_bottom": True},
                         exhaustion=True) is False       # exhaustion overrides everything


def test_near_base_bottom_overrides_extension_cap():
    from sepa import scanner as S
    bc = {"base_count": 2, "is_late_stage": False, "is_avoid_stage": False}
    # last 105 vs pivot 100 = +5% extended (> BUYABLE_MAX_EXT_PCT 3%).
    ext_mvp = {"has_mvp": True, "near_base_bottom": True}
    no_mvp = {"has_mvp": False, "near_base_bottom": False}
    assert S._is_buyable(_tr(), _STG2, bc, _LIQ, _VOL_BREAKOUT, _SETUP, 105.0,
                         mvp=ext_mvp) is True            # near-base-bottom exception (TTLAC §1 p.34)
    assert S._is_buyable(_tr(), _STG2, bc, _LIQ, _VOL_BREAKOUT, _SETUP, 105.0,
                         mvp=no_mvp) is False            # no exception -> 3% cap blocks it


def test_in_zone_breakout_still_buyable_without_mvp():
    from sepa import scanner as S
    bc = {"base_count": 3, "is_late_stage": False, "is_avoid_stage": False}
    # base 3, breakout 2% past pivot (in zone), no MVP -> buyable (base 3 tradeable).
    assert S._is_buyable(_tr(), _STG2, bc, _LIQ, _VOL_BREAKOUT, _SETUP, 102.0) is True
