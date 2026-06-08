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
from supply_demand import demand_zones as Z


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


# ════════════════════════════════════════════════════════════════════════════
# Demand zones (demand_zones.py) — Minervini basing, Ch.10 pp.197-213.
# Spec + page cites: docs/supply_demand/demand_zones_methodology.md
# ════════════════════════════════════════════════════════════════════════════

# ── Depth class — book validity gate (p.210-211) ─────────────────────────────
def test_depth_class_bands():
    assert Z._depth_class(None) is None
    assert Z._depth_class(5.0) == "shallow"          # < 8 → barely a base
    assert Z._depth_class(7.99) == "shallow"
    assert Z._depth_class(8.0) == "constructive"     # 8-35 constructive (p.211)
    assert Z._depth_class(25.0) == "constructive"
    assert Z._depth_class(35.0) == "constructive"
    assert Z._depth_class(35.1) == "deep"            # beyond ideal
    assert Z._depth_class(59.9) == "deep"
    assert Z._depth_class(60.0) == "failure_prone"   # >= 60 (p.210-211)
    assert Z._depth_class(85.0) == "failure_prone"


def test_demand_zone_thresholds_locked():
    # Book p.210-211: 10-35% constructive, >=60% failure-prone. Lock so a
    # refactor can't silently loosen the validity gate.
    assert Z.DEPTH_SHALLOW_MAX == 8.0
    assert Z.DEPTH_CONSTRUCTIVE_MAX == 35.0
    assert Z.DEPTH_FAILURE_PRONE == 60.0


# ── Zone geometry — where price sits vs the band (pure) ───────────────────────
def test_zone_geometry_in_zone():
    g = Z._zone_geometry(45.0, 40.0, 50.0)
    assert g["in_zone"] is True and g["zone_status"] == "in"
    assert g["distance_to_zone_pct"] == 0.0
    assert g["zone_position_pct"] == 50.0            # halfway floor→pivot


def test_zone_geometry_above_pivot_is_support_below():
    g = Z._zone_geometry(60.0, 40.0, 50.0)
    assert g["in_zone"] is False and g["zone_status"] == "above"
    assert g["distance_to_zone_pct"] == 20.0         # 60/50 - 1
    assert g["zone_position_pct"] is None


def test_zone_geometry_below_floor():
    g = Z._zone_geometry(36.0, 40.0, 50.0)
    assert g["zone_status"] == "below"
    assert g["distance_to_zone_pct"] == -10.0        # 36/40 - 1 (signed)
    assert g["in_zone"] is False


def test_zone_geometry_guards():
    assert Z._zone_geometry(None, 40.0, 50.0)["zone_status"] is None
    assert Z._zone_geometry(45.0, 50.0, 40.0)["zone_status"] is None   # inverted band


# ── Behavioral — zone_for_symbol maps the locked VCP base → the band ─────────
def _patch(monkeypatch, df, base, ctx):
    monkeypatch.setattr(Z.prices, "load_prices", lambda s: df)
    monkeypatch.setattr(Z.vcp_mod, "detect", lambda d: base)
    monkeypatch.setattr(Z.sd, "analyze_symbol", lambda s: ctx)


def test_zone_for_symbol_maps_base_and_pullback(monkeypatch):
    df = _df([50.0] * 60)
    df.loc[59, "close"] = 45.0                        # current price inside [40,50]
    base = {
        "base_low": 40.0, "base_high": 52.0, "pivot_buy_price": 50.0,
        "base_depth_pct": 23.0, "n_contractions": 3, "final_contraction_pct": 6.0,
        "tightness": 72, "tightness_band": "tight", "volume_drying": True,
        "has_base": True, "suggested_stop": 41.0,
    }
    _patch(monkeypatch, df, base,
           {"state": "demand", "demand_score": 80.0, "dollar_vol": 1_000_000, "name": "Acme"})
    rec = Z.zone_for_symbol("ACME", "leaderboard")
    assert rec["has_zone"] is True
    assert rec["zone_low"] == 40.0 and rec["zone_high"] == 50.0   # floor / pivot
    assert rec["depth_class"] == "constructive"
    assert rec["in_zone"] is True and rec["zone_status"] == "in"
    assert rec["pulled_back"] is True                # in a constructive base → cross-link
    assert rec["state"] == "demand" and rec["source"] == "leaderboard"


def test_zone_for_symbol_breakout_is_above_not_pullback(monkeypatch):
    df = _df([50.0] * 60)
    df.loc[59, "close"] = 66.0                        # broke out above the pivot
    base = {"base_low": 40.0, "base_high": 52.0, "pivot_buy_price": 50.0, "base_depth_pct": 23.0}
    _patch(monkeypatch, df, base, {})
    rec = Z.zone_for_symbol("X", "day")
    assert rec["zone_status"] == "above" and rec["in_zone"] is False
    assert rec["distance_to_zone_pct"] == 32.0        # 66/50 - 1; zone is support below
    assert rec["pulled_back"] is False


def test_zone_for_symbol_no_base(monkeypatch):
    df = _df([50.0] * 60)
    _patch(monkeypatch, df, {"reason": "no contractions"}, {})
    rec = Z.zone_for_symbol("X", "leaderboard")
    assert rec["has_zone"] is False
    assert rec["zone_low"] is None and rec["depth_class"] is None
    assert rec["zone_status"] is None


# ── Source guard — zones MUST derive from the contract-locked VCP detector ────
def test_zone_source_is_the_locked_vcp_detector():
    import sepa.vcp as vcp
    assert Z.vcp_mod is vcp                           # not a reimplementation
    assert callable(vcp.detect)
