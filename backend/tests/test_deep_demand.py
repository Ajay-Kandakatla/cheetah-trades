"""Deep Demand — the second-level-arrival read (supply_demand/deep_demand.py).

Why this exists (Ajay 2026-08-25): "stocks entering second level of demand
zone from the top but sales are intact ... penalized stocks that actually
have good revenue but market does not realize it." The price half must be
computed INSIDE the demand scan because these names usually fail trend_ok
and never reach the cached rows a board could read.

The sales half (Bonde gate) is board-side and tested in test_chart_maps.py.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import deep_demand as DD
from supply_demand.price_zones import NEAR_PCT
from supply_demand.demand_reentry import MIN_TOUCHES, MIN_ZONE_STRENGTH


def _band(lo, hi, touches=3, strength=60.0):
    return {"kind": "demand", "lo": lo, "hi": hi, "mid": (lo + hi) / 2,
            "touches": touches, "strength": strength}


def _rec(last, bands, top_band_read=None):
    return {"symbol": "T", "last_price": last, "demand_zones": bands,
            "top_band_read": top_band_read}


# ── geometry ────────────────────────────────────────────────────────────────
def test_inside_second_band_qualifies():
    r = DD.read(_rec(82.0, [_band(90, 95), _band(80, 85)]))
    assert r is not None
    assert r["state"] == "in"
    assert r["dist_pct"] == 0.0
    assert r["second_band"]["lo"] == 80


def test_approaching_second_band_from_above_within_near_pct_qualifies():
    # last 86.0 vs second hi 85 → ~1.16% above, inside NEAR_PCT
    r = DD.read(_rec(86.0, [_band(90, 95), _band(80, 85)]))
    assert r is not None and r["state"] == "near"
    assert 0 < r["dist_pct"] <= NEAR_PCT


def test_too_far_above_the_second_band_does_not_qualify():
    # 89.0 is below the first band's floor (90) but ~4.5% above the second's
    # top — not "entering" yet, and NEAR_PCT is the one scale for "at".
    assert DD.read(_rec(89.0, [_band(90, 95), _band(80, 85)])) is None


def test_first_band_still_holding_does_not_qualify():
    # Price inside the FIRST band — that is the ordinary zones board's case.
    assert DD.read(_rec(92.0, [_band(90, 95), _band(80, 85)])) is None


def test_broken_through_both_bands_does_not_qualify():
    # Below the second band's floor: that is a breakdown, not an entry.
    assert DD.read(_rec(78.0, [_band(90, 95), _band(80, 85)])) is None


def test_single_band_charts_never_qualify():
    assert DD.read(_rec(82.0, [_band(90, 95)])) is None
    assert DD.read(_rec(82.0, [])) is None


# ── band quality: imported thresholds, one scale ────────────────────────────
def test_flimsy_second_band_is_refused_by_the_scan_own_bar():
    weak_touch = [_band(90, 95), _band(80, 85, touches=MIN_TOUCHES - 1)]
    weak_str = [_band(90, 95), _band(80, 85, strength=MIN_ZONE_STRENGTH - 1)]
    assert DD.read(_rec(82.0, weak_touch)) is None
    assert DD.read(_rec(82.0, weak_str)) is None


def test_break_evidence_rides_along_when_present():
    tb = {"bars_since_break": 4, "fell_from_pct": 12.5, "broke_below": True}
    r = DD.read(_rec(82.0, [_band(90, 95), _band(80, 85)], top_band_read=tb))
    assert r["bars_since_top_break"] == 4
    assert r["fell_from_pct"] == 12.5


def test_below_top_pct_measures_the_penalty():
    r = DD.read(_rec(82.0, [_band(90, 95), _band(80, 85)]))
    # (90 - 82) / 90 = 8.89%
    assert r["below_top_pct"] == pytest.approx(8.89, abs=0.01)


# ── ordering ────────────────────────────────────────────────────────────────
def test_sort_key_puts_in_band_before_near_and_closer_before_farther():
    in_row = {"deep_demand": {"state": "in", "dist_pct": 0.0,
                              "second_band": {"strength": 50}}}
    near_close = {"deep_demand": {"state": "near", "dist_pct": 0.5,
                                  "second_band": {"strength": 50}}}
    near_far = {"deep_demand": {"state": "near", "dist_pct": 2.5,
                                "second_band": {"strength": 90}}}
    rows = [near_far, near_close, in_row]
    rows.sort(key=DD.sort_key)
    assert [r["deep_demand"]["state"] for r in rows] == ["in", "near", "near"]
    assert rows[1]["deep_demand"]["dist_pct"] == 0.5


# ── malformed input never crashes a scan ────────────────────────────────────
def test_garbage_records_return_none_not_raise():
    assert DD.read({}) is None
    assert DD.read({"last_price": None, "demand_zones": [_band(1, 2), _band(0, 1)]}) is None
    assert DD.read(_rec(82.0, [{"lo": None, "hi": None}, _band(80, 85)])) is None
