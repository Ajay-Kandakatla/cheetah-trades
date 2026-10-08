"""🛡️ 🚀 the revenue line on the growth read (2026-10-08).

Ajay 2026-10-08, on the 141 held-out names: "update them please". Banks rank on
the 10-Q's net revenue (the template rule in `massive_fundamentals`); a name
whose provider line is not the 10-Q's keeps * and the fold says why. Every
string is served — the FE composes none. Hermetic.
"""
from __future__ import annotations

import pytest

from chart_maps import resiliency_tab as R
from sepa import massive_fundamentals as MF
from tests.test_resiliency_growth_sanity_2026_10_07 import (BAC, CACHED, SNDK, TODAY, VST,
                                                            _chip, _fund)


def _bac_healed():
    f = _fund(rev_pct=14.99, eps_pct=10.0, rev=[31558e6, 1, 1, 1, 27443e6, 1],
              eps=[1.1, 1, 1, 1, 1.0, 1])
    f.update(rev_line=MF.LINE_NET_OF_INTEREST, rev_line_series=[MF.LINE_NET_OF_INTEREST] * 6,
             rev_line_note=None, rev_line_mixed=0)
    return f


def _sofi(*, eps=True, stored=27.35):
    f = _fund(rev_pct=stored, eps_pct=10.0 if eps else None,
              rev=[429298000.0, 1, 1, 1, 337107000.0, 1],
              eps=[1.1, 1, 1, 1, 1.0, 1] if eps else None)
    f.update(rev_line=MF.LINE_REVENUE, rev_line_note=MF.NOTE_NO_NII, rev_line_mixed=0)
    return f


def _cvx():
    f = _fund(rev_pct=51.43, rev=[67199e6, 1, 1, 1, 44375e6, 1])
    f.update(rev_line=MF.LINE_REVENUE, rev_line_note=MF.NOTE_SUBLINE_CALL, rev_line_mixed=0)
    return f


def _undetermined():
    """The doc production WRITES for a bank quarter with no cost line (critic round 2):
    real rows through canslim, the hole in `rev_line_series[0]`, `rev_line` net."""
    from tests.test_revenue_line_critic_2026_10_08 import stt_shaped_undetermined
    return stt_shaped_undetermined(0, eps=False)


def _stat(g):
    return R._growth_stat(g)


# ─────────────────────────────────────────── ranked on the net line
def test_bank_after_the_heal_ranks_on_the_net_line_and_the_fold_says_so():
    g, chip = _chip(_bac_healed(), today=TODAY)
    assert g["sales_ranked"] is True and g["sales_reason"] is None
    assert chip.startswith("Sales +15.0% · ") and "*" not in chip.split(" · ")[0]
    assert g["sales_line"] == MF.LINE_NET_OF_INTEREST
    assert g["sales_line_words"] == "total revenue net of interest expense"
    assert "sales +14.99% (total revenue net of interest expense)" in _stat(g)


def test_held_line_shows_star_and_the_ledger_note():
    g, chip = _chip(_sofi(), today=TODAY)
    assert g["sales_reason"] == "line_unverified" and g["sales_ranked"] is False
    assert chip.startswith("Sales +27.4%* · ")
    assert (f"sales +27.35% on the provider's revenue — not ranked: {MF.NOTE_NO_NII}"
            in _stat(g))
    assert g["legs"] == 1                                    # EPS still ranks
    assert R.coverage_class(g, bars=400, min_bars=100) == "one_leg"


def test_his_call_subline_says_pending_a_decision():
    g, chip = _chip(_cvx(), today=TODAY)
    assert chip.startswith("Sales +51.4%* · ")
    assert "pending a decision" in _stat(g)
    assert R.coverage_class(g, bars=400, min_bars=100) == R.REVENUE_LINE_CLASS


def test_undetermined_quarter_token_is_line_na_with_the_hole_words():
    f = _undetermined()
    assert f["rev_line"] != MF.LINE_UNDETERMINED          # production never writes it there
    g, chip = _chip(f, today=TODAY)
    assert g["sales_reason"] == "line_unverified" and g["sales_yoy_pct"] is None
    assert chip.startswith("Sales line n/a · ")
    assert ("sales: not ranked — " + MF.LINE_WORDS[MF.LINE_UNDETERMINED]) in _stat(g)


def test_line_mixed_is_not_compared():
    f = _fund(rev=[5e9, 1, 1, 1, None, 1])
    f.update(rev_line=MF.LINE_NET_OF_INTEREST, rev_line_note=None, rev_line_mixed=1)
    g, chip = _chip(f, today=TODAY)
    assert g["sales_reason"] == "line_mixed" and chip.startswith("Sales line n/a · ")
    assert R.SALES_LINE_MIXED_TEXT in _stat(g)
    assert R.coverage_class(g, bars=400, min_bars=100) == R.REVENUE_LINE_CLASS


def _reads():
    docs = {"BAC": _bac_healed(), "SOFI": _sofi(eps=False), "CVX": _cvx(), "VST": VST,
            "SNDK": SNDK, "UND": _undetermined()}
    adv = {"BAC": 9e9, "SOFI": 5e9, "CVX": 7e9, "VST": 3e9, "SNDK": 2e9, "UND": 1e9}
    reads = {}
    for s, f in docs.items():
        g = R.growth_read(f, today=TODAY)
        reads[s] = {"growth": g, "adv50": adv[s], "bars": 400}
    R.score_growth([r["growth"] for r in reads.values()])
    return reads


def test_coverage_identity_line_segment_and_gaps_line():
    cov = R.growth_coverage(_reads(), min_bars=100, ttl_days=16)
    c = cov["classes"]
    assert sum(c.values()) == cov["n"] == 6
    assert c[R.REVENUE_LINE_CLASS] == 3 and c["two_legs"] == 2
    line = R.growth_line(cov)
    assert f" blank by rule · 3 {R.REVENUE_LINE_LABEL} · no figure " in line
    lines = R.growth_gaps_block(cov)["lines"]
    rl = [ln for ln in lines if ln.startswith(R.REVENUE_LINE_LABEL + " (")]
    assert rl == [f"revenue line not the 10-Q's (3): {R.REVENUE_LINE_WHY} — CVX, SOFI, UND"]


# ─────────────────────────────────────────── NEGATIVES
def test_NEGATIVE_a_held_line_never_ranks_even_when_stored_equals_series():
    f = _sofi(stored=27.35)
    assert R.qoq.yoy_pct(f["rev_q_series"]) == 27.35
    g, _ = _chip(f, today=TODAY)
    assert g["sales_ranked"] is False and g["sales_reason"] == "line_unverified"


def test_NEGATIVE_rule_reasons_keep_priority_over_a_note():
    f = _fund(rev_pct=900.0, rev=[5e6, 1, 1, 1, -3e6, 1])
    f.update(rev_line=MF.LINE_REVENUE, rev_line_note=MF.NOTE_NO_NII)
    g, _ = _chip(f, today=TODAY)
    assert g["sales_reason"] == "year_ago_loss"
    assert R.coverage_class(g, bars=400, min_bars=100) == "by_rule"


@pytest.mark.parametrize("f", [BAC, VST, SNDK])
def test_NEGATIVE_legacy_docs_are_unchanged(f):
    g, chip = _chip(dict(f), today=TODAY)
    assert g["sales_line"] is None and g["sales_line_words"] is None and g["sales_line_note"] is None
    assert g["sales_reason"] not in R.LINE_REASONS
    stat = _stat(g)
    assert "provider's" not in stat and "revenue line" not in stat


def test_NEGATIVE_the_zero_count_growth_line_has_no_line_segment():
    reads = {s: rd for s, rd in _reads().items() if s in ("BAC", "VST", "SNDK")}
    line = R.growth_line(R.growth_coverage(reads, min_bars=100, ttl_days=16))
    assert R.REVENUE_LINE_LABEL not in line
    assert R.GAP_ORDER == ("etf", "new_listing", "not_researched", "massive_unused", "no_filings",
                           "stale_filings", "period_gap", "year_ago_missing")


def test_NEGATIVE_the_ranked_bank_chip_carries_no_line_words():
    _g, chip = _chip(_bac_healed(), today=TODAY)
    assert "interest" not in chip and "*" not in chip
    assert R.GROWTH_CHIP_FMT == "Sales {sales} · EPS {eps} YoY ({period})"


def test_blank_carries_the_three_keys():
    b = R._growth_blank()
    assert b["sales_line"] is None and b["sales_line_words"] is None and b["sales_line_note"] is None
    assert CACHED
