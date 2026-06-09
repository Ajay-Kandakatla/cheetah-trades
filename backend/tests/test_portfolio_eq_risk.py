"""Portfolio earnings-quality sell-RISK derivation (Minervini Ch.8, p.140-159).

These are HEADS-UP notes surfaced on a holding — NOT mechanical sell triggers
(Minervini sells on price, Ch.12-13). Locks which red flags become a heads-up.
Imports portfolio.diagnosis (needs fastapi) — runs in the container/CI.
"""
from __future__ import annotations

from portfolio.diagnosis import _earnings_quality_sell_risk as risk


def test_healthy_eq_has_no_sell_risk():
    eq = {"score": 80, "tier": "code33", "code_33": True, "red_flags": {},
          "components": {"npm_latest_pct": 20, "npm_prior_year_pct": 15, "npm_expanding": True}}
    assert risk(eq) == []


def test_double_trouble_flagged():
    eq = {"score": 30, "tier": "red_flag",
          "red_flags": {"double_trouble": True, "inventory_vs_sales": True}, "components": {}}
    assert any("double trouble" in x.lower() for x in risk(eq))


def test_inventory_build_flagged():
    eq = {"score": 40, "tier": "red_flag", "red_flags": {"inventory_vs_sales": True}, "components": {}}
    assert any("Inventory building" in x for x in risk(eq))


def test_low_quality_beat_flagged():
    eq = {"score": 20, "tier": "red_flag", "red_flags": {"low_quality_beat": True}, "components": {}}
    assert any("Low-quality beat" in x for x in risk(eq))


def test_margin_contraction_flagged():
    eq = {"score": 45, "tier": "steady", "red_flags": {},
          "components": {"npm_latest_pct": 10, "npm_prior_year_pct": 14, "npm_expanding": False}}
    assert any("margin contracting" in x.lower() for x in risk(eq))


def test_weak_tier_flagged():
    eq = {"score": 22, "tier": "weak", "red_flags": {}, "components": {}}
    assert any("Weak earnings quality" in x for x in risk(eq))


def test_none_or_unscored_is_empty():
    assert risk(None) == []
    assert risk({"score": None}) == []
