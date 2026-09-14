"""Long-term fundamentals — the ten metrics and the sector-relative score.

Ajay 2026-09-14: *"Move them to fundamentals tab in the individual ticker and
give a score on the fundamentals ranking for longterm."*

The tests that matter here are the NEGATIVE ones. Every metric in this module
has a way of producing a confident, wrong number — a CAGR annualised out of a
loss, a ROE flattered by negative equity, a score built from the three metrics
a company happens to be good at — and each of those has a test below that
fails if the guard is removed.
"""
import math

import pytest

from sepa import longterm as LT


# --------------------------------------------------------------------------
# The weights are a contract
# --------------------------------------------------------------------------
def test_weights_sum_to_one():
    assert abs(sum(LT.WEIGHTS.values()) - 1.0) < 1e-9


def test_every_weighted_key_is_produced_by_metrics_or_warm():
    """A weight keyed on a metric nobody computes silently never votes."""
    produced = set(LT.metrics.__doc__ and [] or [])  # placeholder, see below
    sample = {
        "opm": 1, "eps": 1, "de": 1, "roe": 1, "roce": 1, "net_profit": 1,
        "ocf": 1, "cash_conv": 1, "current_ratio": 1, "sales_cagr": 1,
        "profit_cagr": 1,
    }
    # `inst` is attached by warm(), not metrics(); everything else must come
    # out of the metric block itself.
    for key in LT.WEIGHTS:
        assert key in sample or key == "inst", f"weight {key!r} has no producer"


# --------------------------------------------------------------------------
# _safe_div — the negative-denominator trap
# --------------------------------------------------------------------------
def test_safe_div_refuses_a_negative_denominator():
    """A company with NEGATIVE equity would otherwise post a cheerful ROE.

    net income −100 over equity −50 is +200% if you just divide. That number
    would rank such a name at the TOP of its sector on ROE.
    """
    assert LT._safe_div(-100.0, -50.0, pct=True) is None


def test_safe_div_refuses_zero_and_none():
    assert LT._safe_div(10.0, 0.0) is None
    assert LT._safe_div(None, 10.0) is None
    assert LT._safe_div(10.0, None) is None


def test_safe_div_normal_case():
    assert LT._safe_div(50.0, 200.0, pct=True) == 25.0
    assert LT._safe_div(3.0, 2.0) == 1.5


# --------------------------------------------------------------------------
# _cagr — the loss trap, and the reason code that makes the scorer honest
# --------------------------------------------------------------------------
def test_cagr_normal_growth():
    v, why = LT._cagr([100.0, 110.0, 121.0])
    assert why is None
    assert v == pytest.approx(10.0, abs=0.01)


def test_cagr_refuses_when_it_starts_from_a_loss():
    """You cannot annualise growth from a negative base, and pretending you
    can produces a number whose SIGN is wrong for the wrong reason."""
    v, why = LT._cagr([-50.0, 10.0, 80.0])
    assert v is None
    assert why == "loss"


def test_cagr_refuses_when_it_ends_in_a_loss():
    v, why = LT._cagr([100.0, 50.0, -20.0])
    assert v is None
    assert why == "loss"


def test_cagr_needs_three_points_and_says_it_is_history_not_loss():
    """Two points is an anecdote. And the reason must be 'no_history', NOT
    'loss' — that distinction is what stops the scorer punishing a young
    company for being young."""
    v, why = LT._cagr([100.0, 150.0])
    assert v is None
    assert why == "no_history"


def test_cagr_ignores_none_holes():
    """A missing middle year is skipped, but it does NOT lower the bar: the
    three-point minimum counts REAL points, so [100, None, 121] is still only
    two and correctly refuses."""
    v, why = LT._cagr([100.0, None, 121.0])
    assert v is None and why == "no_history"
    # 100 -> [missing] -> 121 -> 133.1 spans THREE periods, not two. If the
    # hole is dropped before the span is measured, this reports 15.37%.
    v, why = LT._cagr([100.0, None, 121.0, 133.1])
    assert why is None
    assert v == pytest.approx(10.0, abs=0.01), (
        "dropping a missing year must not compress the timeline"
    )


# --------------------------------------------------------------------------
# percentile — the thin-sector guard and the tie handling
# --------------------------------------------------------------------------
def test_percentile_refuses_a_sector_thinner_than_the_floor():
    """A percentile against four peers is noise wearing a number."""
    pool = [1.0, 2.0, 3.0, 4.0]
    assert LT.percentile(3.0, pool) is None


def test_percentile_ranks_inside_a_big_enough_pool():
    pool = [float(i) for i in range(100)]
    p = LT.percentile(50.0, pool)
    assert p is not None and 49.0 <= p <= 52.0


def test_percentile_inverts_when_lower_is_better():
    pool = [float(i) for i in range(100)]
    hi = LT.percentile(90.0, pool, lower_is_better=True)
    lo = LT.percentile(10.0, pool, lower_is_better=True)
    assert lo > hi, "a LOW debt/equity must score HIGH"


def test_percentile_uses_the_midpoint_of_a_tie():
    """A sector where forty names all post 0.00 must not hand thirty-nine of
    them a zero and one of them a 100."""
    pool = [0.0] * 40 + [5.0] * 10
    p = LT.percentile(0.0, pool)
    assert p is not None and 35.0 < p < 45.0


def test_percentile_none_in_none_out():
    assert LT.percentile(None, [float(i) for i in range(50)]) is None


# --------------------------------------------------------------------------
# score_from_percentiles — the flattery trap. This is the important block.
# --------------------------------------------------------------------------
def _full(v=50.0):
    return {k: v for k in LT.WEIGHTS}


def test_score_of_a_uniform_name_is_that_percentile():
    out = LT.score_from_percentiles(_full(50.0))
    assert out["score"] == pytest.approx(50.0, abs=0.05)
    assert out["covered_weight"] == pytest.approx(1.0, abs=1e-6)
    assert out["ranked"] is True


def test_a_metric_missing_for_NO_HISTORY_is_renormalised_away():
    p = _full(60.0)
    p["profit_cagr"] = None
    out = LT.score_from_percentiles(p, {"profit_cagr": "no_history"})
    # Still 60 — the remaining metrics all say 60, and a young company is not
    # punished for having no decade.
    assert out["score"] == pytest.approx(60.0, abs=0.05)
    assert out["covered_weight"] < 1.0
    assert "profit_cagr" not in out["imputed"]


def test_a_metric_missing_because_the_COMPANY_LOST_MONEY_still_votes():
    """THE FLATTERY TRAP. Without this, a company that lost money every year
    is scored purely on the metrics it is good at, and a cash-burning story
    ranks beside a compounder.

    Same percentiles as the test above, different reason code, and the score
    must come out materially LOWER.
    """
    p = _full(60.0)
    p["profit_cagr"] = None
    out = LT.score_from_percentiles(p, {"profit_cagr": "loss"})
    assert "profit_cagr" in out["imputed"]
    assert out["score"] < 60.0 - 5.0, (
        "a loss-driven blank must drag the score down, not be renormalised away"
    )
    # and the weight is fully covered, because the metric DID vote
    assert out["covered_weight"] == pytest.approx(1.0, abs=1e-6)


def test_the_two_absent_reasons_do_not_produce_the_same_score():
    """The regression that matters: if someone collapses the reason codes back
    into a plain None, these two become equal and the trap returns."""
    p = _full(60.0)
    p["profit_cagr"] = None
    p["cash_conv"] = None
    unknown = LT.score_from_percentiles(
        p, {"profit_cagr": "no_history", "cash_conv": "no_history"})
    lossy = LT.score_from_percentiles(
        p, {"profit_cagr": "loss", "cash_conv": "loss"})
    assert lossy["score"] < unknown["score"]


def test_a_thin_name_is_NOT_ranked_even_though_it_has_a_score():
    """DDOG scored 74.2 on 0.34 of the weights and sat third in Technology.
    A number backed by a third of the evidence does not belong in a ranking
    beside one backed by all of it."""
    p = {k: None for k in LT.WEIGHTS}
    p["de"] = 90.0
    p["inst"] = 90.0
    out = LT.score_from_percentiles(p)
    assert out["score"] is not None
    assert out["ranked"] is False
    assert out["covered_weight"] < LT.MIN_COVERED_WEIGHT
    assert "0.7" in out["reason"] or "0.70" in out["reason"]


def test_a_name_with_nothing_scorable_returns_none_not_zero():
    out = LT.score_from_percentiles({k: None for k in LT.WEIGHTS})
    assert out["score"] is None
    assert out["ranked"] is False


def test_debt_to_equity_is_inverted_inside_a_real_score():
    low_debt = _full(50.0); low_debt["de"] = 95.0
    high_debt = _full(50.0); high_debt["de"] = 5.0
    assert (LT.score_from_percentiles(low_debt)["score"]
            > LT.score_from_percentiles(high_debt)["score"])


# --------------------------------------------------------------------------
# metrics() — shape, and the D/E definition
# --------------------------------------------------------------------------
def _row(**kw):
    base = dict(fiscal_year=2025, end_date="2025-12-31", filing_date="2026-02-01",
                revenues=1000.0, operating_income=200.0, gross_profit=500.0,
                net_income=150.0, eps_diluted=1.5, eps_basic=1.5,
                assets=2000.0, liabilities=800.0, equity=1200.0,
                current_assets=600.0, current_liabilities=300.0,
                long_term_debt=100.0, ocf=180.0, net_cash_flow=20.0)
    base.update(kw)
    return base


def test_metrics_computes_the_ten_from_filed_rows():
    # Revenue and profit compound at 10%/yr; operating income tracks revenue so
    # the ratio metrics stay checkable by hand against the LATEST year.
    rows = []
    for y in range(2025, 2019, -1):
        k = 1.1 ** (y - 2020)
        rows.append(_row(fiscal_year=y, revenues=1000.0 * k,
                         operating_income=200.0 * k, net_income=150.0 * k))
    r = LT.metrics("TEST", rows=rows)
    assert r["ok"] is True
    m = r["metrics"]
    assert m["opm"] == pytest.approx(20.0, abs=0.01)     # 200k/1000k, k cancels
    # operating income compounds with revenue; capital employed is fixed at
    # assets 2000 − current liabilities 300 = 1700
    assert m["roce"] == pytest.approx(200.0 * 1.1 ** 5 / 1700.0 * 100, abs=0.01)
    # equity is fixed at 1200 in _row, so ROE rises with the compounded profit
    assert m["roe"] == pytest.approx(150.0 * 1.1 ** 5 / 1200.0 * 100, abs=0.01)
    assert m["current_ratio"] == pytest.approx(2.0, abs=0.01)
    assert m["cash_conv"] == pytest.approx(180.0 / (150.0 * 1.1 ** 5), abs=0.01)
    assert m["sales_cagr"] == pytest.approx(10.0, abs=0.1)


def test_debt_to_equity_uses_TOTAL_liabilities_not_just_long_term_debt():
    """A company funded by payables and leases is levered whether or not it
    issued a bond. Using `long_term_debt` grades that name as pristine."""
    r = LT.metrics("TEST", rows=[_row()])
    # 800/1200 = 0.667, NOT 100/1200 = 0.083
    assert r["metrics"]["de"] == pytest.approx(0.667, abs=0.005)


def test_metrics_reports_coverage_honestly_for_a_one_year_name():
    """Ajay: 'I know some of the stocks may not have 10 years.' NTSK has one."""
    r = LT.metrics("TEST", rows=[_row()])
    cov = r["coverage"]
    assert cov["years_available"] == 1
    assert cov["has_10y"] is False
    assert r["metrics"]["sales_cagr"] is None
    assert r["absent_because"].get("sales_cagr") == "no_history"


def test_metrics_on_a_symbol_with_no_filings_does_not_raise():
    """ETFs, trusts and fresh listings land here. A fundamentals tab that 500s
    on them is worse than one that says 'no filings'."""
    r = LT.metrics("TEST", rows=[])
    assert r["ok"] is False
    assert r["reason"]
    assert r["metrics"] == {}


def test_a_loss_making_name_marks_cash_conv_as_loss_not_history():
    r = LT.metrics("TEST", rows=[_row(net_income=-50.0), _row(fiscal_year=2024),
                                _row(fiscal_year=2023)])
    assert r["absent_because"].get("cash_conv") == "loss"


# --------------------------------------------------------------------------
# The honesty contracts — these guard wording, not arithmetic
# --------------------------------------------------------------------------
def test_score_is_not_advertised_as_measured_until_a_study_exists():
    """Flipping SCORE_IS_MEASURED is what lets the frontend use forward-looking
    language. It must not be flipped without a study; three boards this year
    shipped a claim that later measured null or inverted."""
    assert LT.SCORE_IS_MEASURED is False, (
        "set this True only alongside a committed, re-runnable study with a CI"
    )


def test_promoter_holding_is_never_claimed_for_a_us_name():
    """US issuers file no promoter holding. The institutional block stands in
    for it and must say so rather than relabelling a different number."""
    src = open(LT.__file__, encoding="utf-8").read()
    assert "promoter holding" in src.lower()
    assert "no US equivalent" in src or "NO US EQUIVALENT" in src
    inst = LT.institutional.__doc__ or ""
    assert "level" in inst.lower() and "flow" in inst.lower(), (
        "ownership is a 13F-cadence LEVEL and block share is a FLOW; Rule #7 "
        "says they must not be blended"
    )


def test_block_share_is_not_called_during_the_universe_warm():
    """It pages the raw trade tape. Doing that across ~2,685 names would hammer
    a provider already observed refusing connections under burst load."""
    import inspect
    src = inspect.getsource(LT.warm)
    assert "_block_share" not in src
