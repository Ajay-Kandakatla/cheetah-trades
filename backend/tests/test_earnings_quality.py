"""Behavioral + regression contracts for the Minervini Ch.8 earnings-quality
score (backend/sepa/earnings_quality.py), book pp.140-159.

Synthetic newest-first quarterly series; no network. Helpers build series whose
YoY[i] (series[i] vs series[i+4]) equals a chosen percent, and net income from a
chosen per-quarter margin, so we can exercise:
  * the Code 33 (EPS + sales + margins accelerating 3 quarters, p.158-159)
  * margin expansion (p.145-147)
  * the low-quality "cost-cutting beat" penalty (p.141-144)  <- regression guard
  * the inventory / double-trouble red flags (p.153-157)
"""
from __future__ import annotations

from sepa import earnings_quality as eq

BASE = 100.0


def rev_from_yoy(yoy4):
    """Newest-first 8-q revenue series with YoY[i]==yoy4[i] for i in 0..3."""
    recent = [BASE * (1 + p / 100.0) for p in yoy4]
    older = [BASE, BASE, BASE, BASE]
    return recent + older


def eps_from_yoy(yoy4, base=2.0):
    recent = [base * (1 + p / 100.0) for p in yoy4]
    older = [base, base, base, base]
    return recent + older


def ni_from_margins(rev_series, margins8):
    """Net income series = revenue[i] * margin[i] (margin as a fraction)."""
    return [rev_series[i] * margins8[i] for i in range(len(rev_series))]


def test_clean_code_33_scores_high():
    rev = rev_from_yoy([50, 35, 20, 10])          # sales accelerating
    eps = eps_from_yoy([60, 40, 20, 10])          # EPS accelerating
    margins = [0.20, 0.18, 0.16, 0.15, 0.12, 0.12, 0.12, 0.12]  # NPM rising (newest-first)
    ni = ni_from_margins(rev, margins)
    out = eq.compute(eps, rev, ni)
    assert out["code_33"] is True
    assert out["tier"] == "code33"
    assert out["score"] >= 70
    assert out["components"]["npm_expanding"] is True
    assert out["components"]["eps_accelerating_3q"] is True
    assert out["components"]["rev_accelerating_3q"] is True


def test_cost_cutting_beat_scores_low():
    # REGRESSION (p.141-144): EPS jumps on ~flat sales with NO margin expansion ->
    # earnings not revenue-driven -> must score LOW and flag low_quality_beat.
    rev = rev_from_yoy([2, 2, 2, 2])              # sales flat (<5%)
    eps = eps_from_yoy([40, 40, 40, 40])          # EPS +40% YoY
    margins = [0.10] * 8                          # margins flat -> not expanding
    ni = ni_from_margins(rev, margins)
    out = eq.compute(eps, rev, ni)
    assert out["red_flags"]["low_quality_beat"] is True
    assert out["tier"] == "red_flag"
    assert out["score"] < 40
    assert out["code_33"] is False


def test_margin_expansion_detected():
    rev = rev_from_yoy([12, 11, 10, 9])
    eps = eps_from_yoy([30, 28, 26, 24])
    margins = [0.18, 0.16, 0.15, 0.14, 0.10, 0.10, 0.10, 0.10]  # NPM 18% now vs 10% yr-ago
    ni = ni_from_margins(rev, margins)
    out = eq.compute(eps, rev, ni)
    assert out["components"]["npm_expanding"] is True
    assert out["components"]["npm_latest_pct"] > out["components"]["npm_prior_year_pct"]


def test_inventory_red_flag():
    rev = rev_from_yoy([8, 7, 6, 5])             # modest sales growth
    eps = eps_from_yoy([30, 25, 20, 15])
    margins = [0.12] * 8                          # flat -> not Code 33
    ni = ni_from_margins(rev, margins)
    inv = rev_from_yoy([45, 30, 20, 10])         # inventory +45% vs sales +8%
    out = eq.compute(eps, rev, ni, inv_q_series=inv)
    assert out["red_flags"]["inventory_vs_sales"] is True
    assert out["code_33"] is False
    assert "nventory" in out["reason"]


def test_inventory_build_with_strong_sales_is_not_flagged():
    # p.156: inventory building AHEAD of accelerating demand (sales strong) is the
    # GOOD kind, not "piling up" — the red flag must be suppressed (the NVDA case).
    rev = rev_from_yoy([50, 40, 30, 20])         # sales +50% YoY (strong)
    eps = eps_from_yoy([60, 45, 30, 20])
    ni = ni_from_margins(rev, [0.30, 0.26, 0.22, 0.20, 0.15, 0.15, 0.15, 0.15])
    inv = rev_from_yoy([90, 60, 40, 20])         # inventory +90% (> sales) but sales strong
    out = eq.compute(eps, rev, ni, inv_q_series=inv)
    assert out["red_flags"]["inventory_vs_sales"] is False
    assert out["red_flags"]["inv_growth_yoy_pct"] > out["components"]["rev_growth_yoy_pct"]


def test_double_trouble_when_inventory_and_receivables_outrun_sales():
    rev = rev_from_yoy([6, 6, 6, 6])
    eps = eps_from_yoy([20, 18, 16, 14])
    ni = ni_from_margins(rev, [0.11] * 8)
    inv = rev_from_yoy([40, 30, 20, 10])
    recv = rev_from_yoy([35, 25, 18, 9])
    out = eq.compute(eps, rev, ni, inv_q_series=inv, recv_q_series=recv)
    assert out["red_flags"]["inventory_vs_sales"] is True
    assert out["red_flags"]["receivables_vs_sales"] is True
    assert out["red_flags"]["double_trouble"] is True
    assert "double trouble" in out["reason"].lower()


def test_receivables_flag_is_none_without_supplement():
    rev = rev_from_yoy([10, 9, 8, 7])
    eps = eps_from_yoy([20, 18, 16, 14])
    ni = ni_from_margins(rev, [0.12] * 8)
    out = eq.compute(eps, rev, ni, inv_q_series=rev_from_yoy([5, 5, 5, 5]))
    assert out["red_flags"]["receivables_vs_sales"] is None
    assert out["red_flags"]["double_trouble"] is False


def test_insufficient_history_is_none():
    out = eq.compute([2.0, 2.1, 2.2], [100.0, 101.0], [10.0, 10.0])
    assert out["score"] is None
    assert out["_insufficient"] is True


def test_thresholds_locked():
    # Mirrors the source-guard in test_sepa_contracts.py. Changing any of these
    # is a methodology change (Rule #4) and must update the page-cited doc.
    assert eq.STRONG_EPS_YOY_PCT == 25.0
    assert eq.SALES_FLOOR_PCT == 5.0
    assert eq.INV_OVER_SALES_GAP_PCT == 15.0
    assert eq.INV_REDFLAG_SALES_STRONG_PCT == 25.0
    assert eq.LOWQ_EPS_MIN_PCT == 25.0
    assert eq.LOWQ_SALES_MAX_PCT == 5.0
