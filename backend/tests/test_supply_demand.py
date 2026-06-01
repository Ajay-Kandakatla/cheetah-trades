"""Contract tests for the per-stock supply/demand screen.

Spec + page cites: docs/supply_demand/per_stock_methodology.md
Locks the new overhead-supply metric + the state precedence so a refactor
can't silently change the Minervini Ch.10 (pp.204-210) semantics.

Pure-function tests (no Mongo / no network) — run via:
  docker run --rm -v "$PWD/backend:/app" -w /app cheetah-api:latest \
      python -m pytest tests/test_supply_demand.py -q
"""
from __future__ import annotations

import pandas as pd

from supply_demand import stock_supply_demand as S


def _df(closes, vols=None):
    n = len(closes)
    vols = vols if vols is not None else [1.0] * n
    return pd.DataFrame({"close": [float(c) for c in closes], "volume": [float(v) for v in vols]})


# ── Overhead supply metric (the new computation) ─────────────────────────────
def test_overhead_zero_at_new_high():
    # Strictly ascending → the last close IS the max → nothing traded higher.
    assert S._overhead_supply_pct(_df(range(1, 121))) == 0.0


def test_overhead_is_volume_fraction_traded_above_current():
    # 100 bars at price 100, then current bar at 50 → 100/101 traded above.
    oh = S._overhead_supply_pct(_df([100] * 100 + [50]))
    assert oh is not None and 98.0 <= oh <= 100.0


def test_overhead_increases_as_current_price_falls():
    base = list(range(50, 150))  # 100 bars spanning 50..149
    near_high = S._overhead_supply_pct(_df(base + [140]))   # few bars above 140
    deep      = S._overhead_supply_pct(_df(base + [60]))    # most bars above 60
    assert deep > near_high


def test_overhead_none_for_short_history():
    assert S._overhead_supply_pct(_df([1.0] * 10)) is None


# ── State precedence (book-faithful) ─────────────────────────────────────────
def test_distribution_is_supply():
    assert S._classify(5.0, 5.0, {"accumulation_strength": "distributing"}) == "supply"


def test_deep_overhead_is_supply_even_with_buying():
    # HOOD-class: heavy overhead / deep correction wins over recent accumulation
    # (book p.210 — rallied back into overhead supply).
    assert S._classify(57.0, 38.0,
                       {"accumulation_strength": "accumulating", "high_vol_breakout": True}) == "supply"


def test_clear_runway_with_accumulation_is_demand():
    # Accumulation alone qualifies (drying/breakout not required).
    assert S._classify(2.0, 1.0, {"accumulation_strength": "strong"}) == "demand"


def test_near_high_but_neutral_is_churning():
    assert S._classify(6.0, 10.0, {"accumulation_strength": "neutral"}) == "churning"


# ── Demand score (spreads, doesn't saturate, orders correctly) ───────────────
def test_score_orders_demand_above_supply():
    strong_clean = S._demand_score(0.0, 0.0,
        {"accumulation_strength": "strong", "cmf_signal": "inflow", "is_drying_up": True})
    deep_supply = S._demand_score(57.0, 38.0,
        {"accumulation_strength": "distributing", "cmf_signal": "outflow"})
    assert strong_clean > 80
    assert deep_supply < 40
    assert strong_clean > deep_supply


def test_score_within_bounds():
    for oh, pb, vol in [(0, 0, {"accumulation_strength": "strong", "cmf_signal": "inflow"}),
                        (100, 90, {"accumulation_strength": "distributing", "cmf_signal": "outflow"}),
                        (None, None, {})]:
        s = S._demand_score(oh, pb, vol)
        assert 0.0 <= s <= 100.0


# ── Locked thresholds ────────────────────────────────────────────────────────
def test_thresholds_locked():
    assert S.LOOKBACK_DAYS == 252
    assert S.OVERHEAD_LOW_PCT == 15.0
    assert S.OVERHEAD_HEAVY_PCT == 40.0
    assert S.DEEP_CORRECTION_PCT == 50.0
    assert S.NEAR_HIGH_PCT == 15.0
