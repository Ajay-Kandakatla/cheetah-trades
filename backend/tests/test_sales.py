"""Behavioral contracts for the Sales Confidence score (backend/sepa/sales.py).

Anchored to Pradeep Bonde's ("Stockbee") DOCUMENTED sales thresholds — 5% floor,
25% preferred, 100% "explosive" — not the third-party 30/39% figures that failed
source verification (see docs/sepa/sales_confidence_methodology.md). Synthetic
revenue series; no network.
"""
from __future__ import annotations

from sepa import sales


def _series(yoy_recent):
    """Newest-first quarterly revenue series whose YoY[i] == yoy_recent[i] %.
    Older 4 quarters are a flat base of 100; the recent 4 are base*(1+yoy)."""
    base = [100.0, 100.0, 100.0, 100.0]
    recent = [100.0 * (1 + p / 100.0) for p in yoy_recent]
    return recent + base   # Q0..Q3 (newest) then Q4..Q7 (a year ago)


def test_explosive_sales_scores_high():
    info = sales.compute(_series([120, 110, 100, 90]))   # ~120% YoY, accelerating
    assert info["tier"] == "explosive"
    assert info["growth_yoy_pct"] >= 100
    assert info["accelerating"] is True
    assert info["score"] >= 90


def test_strong_sales_25_to_100():
    info = sales.compute(_series([40, 38, 35, 30]))
    assert info["tier"] == "strong"
    assert 55 <= info["score"] <= 100


def test_below_floor_scores_weak():
    # Below Bonde's 5% floor — the accel/consistency bonuses must NOT lift it.
    info = sales.compute(_series([3, 2, 1, 1]))
    assert info["tier"] == "weak"
    assert info["score"] < 40


def test_declining_sales():
    info = sales.compute(_series([-10, -5, 0, 5]))
    assert info["tier"] == "declining"
    assert info["growth_yoy_pct"] < 0
    assert info["score"] < 25


def test_acceleration_flag():
    accel = sales.compute(_series([40, 20, 15, 10]))   # 40 now vs 20 prior
    decel = sales.compute(_series([20, 40, 35, 30]))   # 20 now vs 40 prior
    assert accel["accelerating"] is True
    assert decel["accelerating"] is False


def test_consistency_counts_consecutive_growth():
    assert sales.compute(_series([30, 25, 20, 15]))["consecutive_growth_q"] == 4
    assert sales.compute(_series([30, -5, 20, 15]))["consecutive_growth_q"] == 1


def test_sales_led_flag():
    led = sales.compute(_series([50, 40, 30, 20]), eps_growth_q=10)     # sales 50 > eps 10
    not_led = sales.compute(_series([50, 40, 30, 20]), eps_growth_q=80)
    assert led["sales_led"] is True
    assert not_led["sales_led"] is False


def test_insufficient_history_is_none():
    assert sales.compute([100, 101, 102])["score"] is None    # < 5 quarters
    assert sales.compute([])["score"] is None


def test_thresholds_locked():
    assert sales.SALES_FLOOR_PCT == 5.0
    assert sales.SALES_PREFERRED_PCT == 25.0
    assert sales.SALES_EXPLOSIVE_PCT == 100.0
