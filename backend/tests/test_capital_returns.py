"""Return on capital — ROCE / ROIC / ROE / turnover / capex intensity.

Ajay 2026-09-22: *"quality like very less capital and hi ROI."*

THE NEGATIVES CARRY THIS FILE. Every number here is one a reader will act on
with real money, and the ways each can be silently WRONG are far worse than the
ways it can be missing. A blank cell costs him nothing; a confident 4,000% ROE
sorted to the top of a "high return on capital" board costs him a position.

So the happy paths are a handful of arithmetic checks, and the bulk of the file
pins the refusals: negative equity, a vanishing denominator, a tax benefit, a
loss-making year, a mixed-quarter capex figure, a hole in the TTM window.
"""
from __future__ import annotations

import math

import pytest

from sepa import capital_returns as CR


# ───────────────────────────────────────────────────────── builders
def q(fy, fp, filed="2026-08-01", end="2026-06-30", *, ebit=None, ni=None,
      rev=None, ocf=None, pretax=None, tax=None, assets=None, cl=None,
      equity=None, liabilities=None):
    """One filing, shaped like the provider's."""
    def cell(v):
        return {"value": v} if v is not None else None
    ist = {k: cell(v) for k, v in (
        ("operating_income_loss", ebit),
        ("net_income_loss_attributable_to_parent", ni),
        ("revenues", rev),
        ("income_loss_from_continuing_operations_before_tax", pretax),
        ("income_tax_expense_benefit", tax)) if v is not None}
    bs = {k: cell(v) for k, v in (
        ("assets", assets), ("current_liabilities", cl),
        ("equity_attributable_to_parent", equity),
        ("liabilities", liabilities)) if v is not None}
    cf = {}
    if ocf is not None:
        cf["net_cash_flow_from_operating_activities"] = cell(ocf)
    return {"fiscal_year": fy, "fiscal_period": fp, "filing_date": filed,
            "end_date": end,
            "financials": {"income_statement": ist, "balance_sheet": bs,
                           "cash_flow_statement": cf}}


def four(**kw):
    """A clean 4-quarter window plus the quarter before it, newest first.

    Flows are per-quarter; the balance sheet rides on the endpoints only, which
    is where `compute` reads it.
    """
    ebit = kw.pop("ebit", 25.0)
    ni = kw.pop("ni", 10.0)
    rev = kw.pop("rev", 100.0)
    ocf = kw.pop("ocf", 30.0)
    pretax = kw.pop("pretax", 12.0)
    tax = kw.pop("tax", 3.0)
    a0 = kw.pop("assets", 1000.0)
    cl0 = kw.pop("cl", 200.0)
    e0 = kw.pop("equity", 500.0)
    a1 = kw.pop("prior_assets", 800.0)
    cl1 = kw.pop("prior_cl", 200.0)
    e1 = kw.pop("prior_equity", 300.0)
    flows = dict(ebit=ebit, ni=ni, rev=rev, ocf=ocf, pretax=pretax, tax=tax)
    rows = [
        q(2026, "Q2", assets=a0, cl=cl0, equity=e0, **flows),
        q(2026, "Q1", assets=900.0, cl=200.0, equity=450.0, **flows),
        q(2025, "Q4", filed=None, assets=850.0, cl=200.0, equity=400.0, **flows),
        q(2025, "Q3", assets=820.0, cl=200.0, equity=350.0, **flows),
        # the quarter BEFORE the window — the "beginning" balance sheet
        q(2025, "Q2", assets=a1, cl=cl1, equity=e1, **flows),
    ]
    return rows


# ═══════════════════════════════════════════ the derived-Q4 unlock
def test_the_ttm_window_KEEPS_a_derived_q4_because_a_flow_may_be_subtracted():
    """MEASURED LIVE 2026-09-22 — the finding this module turns on.

    `board_metrics` drops `filing_date is None` rows because a DERIVED Q4 is
    nonsense for an AVERAGE SHARE COUNT. For a FLOW it is ordinary arithmetic,
    and inheriting that guard would have been fatal: 4 consecutive REPORTED
    quarters exist for 1 of 21 live growth names; including derived Q4s it is
    21 of 21.
    """
    win = CR.ttm_window(four())
    assert win is not None
    assert len(win) == CR.TTM_QUARTERS
    assert [w["fiscal_period"] for w in win] == ["Q2", "Q1", "Q4", "Q3"]
    assert win[2]["filing_date"] is None          # the derived one, kept


def test_a_gap_in_the_window_refuses_rather_than_reaching_further_back():
    """A window with a hole would compare a 5-quarter span against a 4-quarter
    one and report it as a year."""
    rows = [r for r in four() if r["fiscal_period"] != "Q1"]
    assert CR.ttm_window(rows) is None


def test_a_ttm_sum_is_None_when_any_quarter_lacks_the_line_never_a_partial():
    """NVDA's derived Q4 2025 carries `revenues: None` on the live provider.

    Three quarters summed and presented as four understates a denominator by
    ~25% and overstates every ratio built on it.
    """
    rows = four()
    del rows[2]["financials"]["income_statement"]["revenues"]
    win = CR.ttm_window(rows)
    assert CR.ttm_sum(win, "income_statement", "revenues") is None
    # the lines that ARE complete still sum
    assert CR.ttm_sum(win, "income_statement", "operating_income_loss") == 100.0


# ═══════════════════════════════════════════ the arithmetic
def test_roce_is_ttm_ebit_over_AVERAGE_capital_employed():
    """capital employed = assets - current liabilities; averaged end-to-end.

    ending 1000-200 = 800, beginning 800-200 = 600, average 700.
    TTM EBIT = 4 x 25 = 100 -> 100/700 = 14.29%.
    """
    out = CR.compute(four())
    assert out["capital_employed"] == 800.0
    assert out["denominator_basis"]["capital_employed"] == "average"
    assert out["roce_pct"] == pytest.approx(14.29, abs=0.01)
    assert out["reasons"].get("roce_pct") is None


def test_roe_uses_parent_equity_and_asset_turnover_uses_average_assets():
    out = CR.compute(four())
    # TTM NI = 40, average equity = (500+300)/2 = 400 -> 10.0%
    assert out["roe_pct"] == pytest.approx(10.0, abs=0.01)
    # TTM revenue = 400, average assets = (1000+800)/2 = 900 -> 0.444
    assert out["asset_turnover"] == pytest.approx(0.444, abs=0.001)


def test_roic_applies_the_filings_own_effective_tax_rate_never_a_statutory_one():
    """tax 3 / pretax 12 = 25%; NOPAT = 100 x 0.75 = 75; 75/700 = 10.71%."""
    out = CR.compute(four())
    assert out["effective_tax_rate"] == pytest.approx(0.25, abs=0.0001)
    assert out["nopat"] == pytest.approx(75.0, abs=0.01)
    assert out["roic_pct"] == pytest.approx(10.71, abs=0.01)


def test_the_denominator_basis_says_ending_when_there_is_no_earlier_quarter():
    """The reader is never told an average was used when it was not."""
    rows = [r for r in four() if not (r["fiscal_year"] == 2025
                                      and r["fiscal_period"] == "Q2")]
    out = CR.compute(rows)
    assert out["denominator_basis"] == {"capital_employed": "ending",
                                        "equity": "ending",
                                        "assets": "ending"}
    assert out["roce_pct"] == pytest.approx(12.5, abs=0.01)     # 100/800


# ═══════════════════════════════════════════ NEGATIVES — the denominator
def test_NEGATIVE_equity_yields_None_not_a_positive_roe_from_two_negatives():
    """THE WORST FAILURE IN THE PACKAGE, and it is silent.

    A company with negative book equity and a negative profit divides one by
    the other and prints a POSITIVE ROE — it would read as the best name on a
    quality board while being the most damaged one on it.
    """
    out = CR.compute(four(equity=-500.0, prior_equity=-300.0, ni=-10.0))
    assert out["roe_pct"] is None
    assert out["reasons"]["roe_pct"] == "negative_equity"


def test_NEGATIVE_capital_employed_yields_None_with_its_own_named_reason():
    out = CR.compute(four(assets=100.0, cl=900.0,
                          prior_assets=100.0, prior_cl=900.0))
    assert out["roce_pct"] is None
    assert out["roic_pct"] is None
    assert out["reasons"]["roce_pct"] == "negative_capital_employed"
    assert out["reasons"]["roic_pct"] == "negative_capital_employed"


def test_a_ZERO_denominator_yields_None_and_never_infinity_or_a_crash():
    out = CR.compute(four(assets=200.0, cl=200.0,
                          prior_assets=200.0, prior_cl=200.0))
    assert out["roce_pct"] is None
    assert out["reasons"]["roce_pct"] == "negative_capital_employed"
    for v in out.values():
        assert not (isinstance(v, float) and math.isinf(v))


def _tiny_equity():
    """$2 M of equity against $4 B of assets and $80 M of profit: ROE 4,000%."""
    return four(assets=4_000_000_000.0, cl=0.0, equity=2_000_000.0,
                prior_assets=4_000_000_000.0, prior_cl=0.0,
                prior_equity=2_000_000.0, ni=20_000_000.0)


def test_the_sanity_bound_SHIPS_OFF_so_the_module_invents_no_number():
    """RULE #1. `MIN_DENOMINATOR_ASSET_SHARE` is the only constant in this file
    that could have been a picked number, and it ships at 0.0 — off.

    With it off the module is purely definitional: a denominator has to be
    positive, and nothing else. The 4,000% ROE is then PRINTED rather than
    blanked, which is the honest trade and is stated on the constant.
    """
    assert CR.MIN_DENOMINATOR_ASSET_SHARE == 0.0
    out = CR.compute(_tiny_equity())
    assert out["roe_pct"] == pytest.approx(4000.0, abs=1.0)
    assert out["reasons"].get("roe_pct") is None


def test_the_sanity_bound_still_WORKS_when_he_sets_one(monkeypatch):
    """The guard, the reason code and the constant all stay, so setting a value
    is HIS call and one edit. This pins the mechanism, not a default."""
    monkeypatch.setattr(CR, "MIN_DENOMINATOR_ASSET_SHARE", 0.01)
    out = CR.compute(_tiny_equity())
    assert out["roe_pct"] is None
    assert out["reasons"]["roe_pct"] == "denominator_too_small"


def test_REGRESSION_a_blanked_ratio_can_UPGRADE_a_capital_destroyers_grade():
    """WHY the bound ships off, measured rather than argued.

    `growth/capital_quality.py` excludes an UNKNOWN component from `answered`.
    So blanking a ratio is NOT a neutral act: a company earning -167% on a
    capital base of 0.75% of its assets reads WORSE with the bound off (FAIL,
    "most", 3 of 4) than with it on (UNKNOWN, "all", 3 of 3). A screen that
    improves a name's grade by suppressing its worst figure is worse than no
    screen, and no live name was ever cited as reaching the bound.
    """
    from growth import capital_quality as CQ

    rows = four(ebit=-12.5, ni=1.0,
                assets=4_000.0, cl=3_970.0, equity=30.0,
                prior_assets=4_000.0, prior_cl=3_970.0, prior_equity=30.0)
    for r in rows:                      # every quarter carries the same base
        bs = r["financials"]["balance_sheet"]
        bs["assets"] = {"value": 4_000.0}
        bs["current_liabilities"] = {"value": 3_970.0}

    def graded(out):
        row = {"symbol": "ZZZ", "cash": 100.0, "debt": 10.0, "fcf_yield": 3.0,
               "shares_yoy_pct": -1.0, "sector": "Technology",
               "roce_pct": out["roce_pct"], "capex_intensity_pct": None,
               "capital_reasons": out["reasons"], "capital_measured": False}
        return CQ.for_row(row, {"sectors": {}, "n_docs": 0, "available": False})

    shipped = graded(CR.compute(rows))
    assert shipped["components"]["positive_roce"]["verdict"] == CQ.FAIL
    assert (shipped["grade"], shipped["passed"], shipped["answered"]) == ("most", 3, 4)

    CR_bound = CR.MIN_DENOMINATOR_ASSET_SHARE
    try:
        CR.MIN_DENOMINATOR_ASSET_SHARE = 0.01
        bounded = graded(CR.compute(rows))
    finally:
        CR.MIN_DENOMINATOR_ASSET_SHARE = CR_bound
    # the SAME company, reading better because a figure was suppressed
    assert bounded["components"]["positive_roce"]["verdict"] == CQ.UNKNOWN
    assert (bounded["grade"], bounded["passed"], bounded["answered"]) == ("all", 3, 3)


# ═══════════════════════════════════ NEGATIVES — ROE's own inputs
def _no_assets(equity=0.01, ni=1000.0, assets=None):
    """Four quarters whose balance sheet carries EQUITY but no usable `assets`.

    ROE is the one ratio whose denominator does not come from the assets line,
    so it is the one that can reach the divide with nothing to bound it.
    """
    rows = four(equity=equity, prior_equity=equity, ni=ni, cl=10.0,
                prior_cl=10.0)
    for r in rows:
        bs = r["financials"]["balance_sheet"]
        if assets is None:
            bs.pop("assets", None)
        else:
            bs["assets"] = {"value": assets}
        bs["equity_attributable_to_parent"] = {"value": equity}
    return rows


def test_REGRESSION_roe_refuses_when_there_is_no_assets_line_to_bound_it():
    """40,000,000%. Not a typo — measured on the branch before this fix.

    ROCE and ROIC cannot reach an unguarded divide (capital employed IS assets
    minus current liabilities, so they are None without it) and asset turnover
    divides by assets itself. ROE was the one leg that ran on whatever the
    equity line said. It now refuses the missing input the same way.
    """
    out = CR.compute(_no_assets())
    assert out["roe_pct"] is None
    assert out["reasons"]["roe_pct"] == "missing_input"
    assert out["total_assets"] is None


def test_REGRESSION_roe_refuses_on_a_filed_zero_assets_line_too():
    """`assets: 0.0` is present but unusable — a guard cannot be applied to it
    any more than to an absent line."""
    out = CR.compute(_no_assets(assets=0.0))
    assert out["roe_pct"] is None
    assert out["reasons"]["roe_pct"] == "missing_input"


def test_roe_is_still_computed_the_moment_the_assets_line_is_there():
    """The refusal above must not blank ROE for ordinary filings — 21 of 21
    live board names carry the assets line today."""
    out = CR.compute(_no_assets(equity=500.0, ni=10.0, assets=1000.0))
    assert out["roe_pct"] is not None


# ═══════════════════════════════════ NEGATIVES — restatements
def _restated(order):
    """The window's latest quarter filed TWICE: an original and a restatement.

    `_fetch_quarters` sends no `sort` parameter, so the provider's list order is
    its default, not a guarantee.
    """
    base = dict(ni=10.0, rev=100.0, ocf=30.0, pretax=12.0, tax=3.0,
                assets=8000.0, cl=1000.0, equity=500.0)
    original = q(2026, "Q2", filed="2027-01-15", ebit=200.0, **base)
    restated = q(2026, "Q2", filed="2027-04-01", ebit=20.0, **base)
    rest = [q(2026, "Q1", ebit=200.0, **base),
            q(2025, "Q4", filed=None, ebit=200.0, **base),
            q(2025, "Q3", ebit=200.0, **base),
            q(2025, "Q2", ebit=200.0, **dict(base, assets=5000.0, equity=400.0))]
    pair = [original, restated] if order == "original_first" else [restated, original]
    return pair + rest


def test_REGRESSION_a_restated_quarter_is_resolved_by_FILING_DATE_not_list_order():
    """Same company, same filings, two different ROCEs decided by list position.

    The comment on `ttm_window` claimed "newest filing wins"; nothing consulted
    `filing_date` at all. A stable sort on the period index alone means the row
    the provider happened to list first won a tie.
    """
    a = CR.compute(_restated("original_first"))
    b = CR.compute(_restated("restated_first"))
    assert a["ttm_ebit"] == b["ttm_ebit"] == 620.0       # 20 + 200 + 200 + 200
    assert a["roce_pct"] == b["roce_pct"]
    assert a["filing_date"] == b["filing_date"] == "2027-04-01"


def test_REGRESSION_a_restatement_reaches_the_GRADED_leg_in_either_order():
    """`positive_roce` is a graded chip and a pushed alert. It must not flip on
    which copy of a quarter the provider listed first."""
    for order in ("original_first", "restated_first"):
        rows = _restated(order)
        for r in rows:
            if r["filing_date"] == "2027-04-01":
                r["financials"]["income_statement"]["operating_income_loss"] = {
                    "value": -900.0}
        out = CR.compute(rows)
        assert out["ttm_ebit"] == -300.0
        assert out["roce_pct"] < 0, order


def test_the_prior_balance_sheet_is_picked_by_filing_date_as_well():
    """Lines 400-403 took the first index match and broke. Same defect, same
    rule — and the prior quarter is the whole `average` denominator."""
    base = dict(ni=10.0, rev=100.0, ocf=30.0, pretax=12.0, tax=3.0, ebit=25.0,
                cl=0.0, equity=500.0)
    rows = [r for r in four()
            if not (r["fiscal_year"] == 2025 and r["fiscal_period"] == "Q2")]
    rows.append(q(2025, "Q2", filed="2025-08-01", assets=800.0, **base))
    rows.append(q(2025, "Q2", filed="2026-02-01", assets=200.0, **base))
    out = CR.compute(rows)
    # ending CE = 1000 - 200 = 800. The RESTATED prior quarter (assets 200,
    # cl 0 -> CE 200) is the one used: average 500, TTM EBIT 100 -> 20.00%.
    # The superseded one (CE 800) would average to 800 and print 12.50%.
    assert out["roce_pct"] == pytest.approx(20.0, abs=0.01)
    assert out["denominator_basis"]["capital_employed"] == "average"


# ═══════════════════════════════════ NEGATIVES — ROE's basis
def _minority(parent_equity=None, parent_ni=None, total_equity=None,
              total_ni=None):
    """A filer with minority interests: the parent lines and the consolidated
    lines are DIFFERENT figures, and either can be absent."""
    rows = four(assets=10_000.0, cl=1_000.0, prior_assets=10_000.0,
                prior_cl=1_000.0)
    for r in rows:
        bs, ist = (r["financials"]["balance_sheet"],
                   r["financials"]["income_statement"])
        bs.pop("equity_attributable_to_parent", None)
        ist.pop("net_income_loss_attributable_to_parent", None)
        if parent_equity is not None:
            bs["equity_attributable_to_parent"] = {"value": parent_equity}
        if total_equity is not None:
            bs["equity"] = {"value": total_equity}
        if parent_ni is not None:
            ist["net_income_loss_attributable_to_parent"] = {"value": parent_ni}
        if total_ni is not None:
            ist["net_income_loss"] = {"value": total_ni}
    return rows


def test_REGRESSION_roe_never_divides_CONSOLIDATED_earnings_by_PARENT_equity():
    """The minority's earnings over only the parent's book: a 2.5x overstatement.

    The numerator fell back parent -> consolidated and the denominator fell back
    parent -> consolidated INDEPENDENTLY. One basis is now chosen for both, and
    it is served.
    """
    out = CR.compute(_minority(parent_equity=1000.0, total_equity=5000.0,
                               total_ni=250.0))
    assert out["roe_basis"] == "consolidated"
    assert out["ttm_net_income"] == 1000.0      # 4 x 250, consolidated
    assert out["total_equity"] == 5000.0        # consolidated, to match
    assert out["roe_pct"] == pytest.approx(20.0, abs=0.01)   # NOT 100.0


def test_roe_uses_the_PARENT_basis_when_the_filings_carry_both_parent_lines():
    out = CR.compute(_minority(parent_equity=1000.0, parent_ni=100.0,
                               total_equity=5000.0, total_ni=250.0))
    assert out["roe_basis"] == "parent"
    assert out["total_equity"] == 1000.0
    assert out["roe_pct"] == pytest.approx(40.0, abs=0.01)   # 400 / 1000


def test_REGRESSION_a_filed_ZERO_parent_equity_is_a_zero_not_an_absent_line():
    """`or` is a truthiness test. A parent whose book value the minority owns
    all of would fall through to the consolidated figure and print a
    comfortable ROE against a denominator belonging to another entity. The
    honest answer is the refusal that negative/zero equity already gets."""
    out = CR.compute(_minority(parent_equity=0.0, parent_ni=100.0,
                               total_equity=5000.0, total_ni=250.0))
    assert out["roe_basis"] == "parent"
    assert out["roe_pct"] is None
    assert out["reasons"]["roe_pct"] == "negative_equity"


def test_a_missing_consolidated_equity_line_refuses_rather_than_mixing_bases():
    out = CR.compute(_minority(total_ni=250.0))
    assert out["roe_basis"] == "consolidated"
    assert out["roe_pct"] is None
    assert out["reasons"]["roe_pct"] == "missing_input"


# ═══════════════════════════════════ NEGATIVES — what the basis flag says
def test_REGRESSION_denominator_basis_is_reported_PER_denominator():
    """One flag for three denominators told the reader an average was used on a
    ROE computed off the ending balance.

    `ce_avg`, `eq_avg` and `assets_avg` each fall back to their own ending
    balance independently, and this is the field a reader uses to decide
    whether two names' figures are comparable.
    """
    rows = four()
    prior = rows[-1]                       # the quarter BEFORE the window
    prior["financials"]["balance_sheet"].pop("equity_attributable_to_parent")
    out = CR.compute(rows)
    assert out["denominator_basis"] == {"capital_employed": "average",
                                        "equity": "ending",
                                        "assets": "average"}
    # ROCE really was averaged; ROE really was not, and the flag now says so
    assert out["roce_pct"] == pytest.approx(14.29, abs=0.01)
    assert out["roe_pct"] == pytest.approx(8.0, abs=0.01)      # 40 / 500


# ═══════════════════════════════════════════ NEGATIVES — the tax rate
def test_a_TAX_BENEFIT_refuses_roic_rather_than_making_nopat_exceed_ebit():
    """MEASURED 2026-09-22: NLY -0.8% and ALAB -14.7% on the live board.

    A negative rate makes NOPAT LARGER than EBIT, ranking a company higher for
    having lost money somewhere else.
    """
    out = CR.compute(four(tax=-5.0))
    assert out["roic_pct"] is None
    assert out["reasons"]["roic_pct"] == "effective_tax_rate_out_of_range"
    assert out["roce_pct"] is not None      # pre-tax ROCE is unaffected


def test_a_LOSS_MAKING_year_refuses_roic_because_the_rate_would_flip_the_sign():
    """FF on the live board: TTM pre-tax -30 M."""
    out = CR.compute(four(pretax=-12.0))
    assert out["roic_pct"] is None
    assert out["reasons"]["roic_pct"] == "nonpositive_pretax_income"


def test_a_MISSING_tax_line_is_named_structurally_not_called_a_missing_input():
    """MEASURED 2026-09-22: 5 of 21 (LQDA, DX, INSW, ARR, LPG) — shipping
    tonnage regimes and REITs are structurally untaxed, not unfetched."""
    rows = four()
    for r in rows:
        r["financials"]["income_statement"].pop("income_tax_expense_benefit")
    out = CR.compute(rows)
    assert out["roic_pct"] is None
    assert out["reasons"]["roic_pct"] == "no_tax_expense"


def test_a_tax_rate_above_100_pct_is_refused_as_out_of_range():
    out = CR.compute(four(pretax=10.0, tax=15.0))
    assert out["roic_pct"] is None
    assert out["reasons"]["roic_pct"] == "effective_tax_rate_out_of_range"


# ═══════════════════════════════════════════ NEGATIVES — periods
def test_periods_agree_tolerates_a_stamp_difference_but_not_a_whole_quarter():
    """MEASURED 2026-09-22. MU stamps 2026-05-28 against 2026-05-31 for the
    SAME quarter; NLY sits a full quarter apart at 2026-03-31 vs 2026-06-30."""
    assert CR.periods_agree("2026-05-28", "2026-05-31") is True
    assert CR.periods_agree("2026-03-31", "2026-06-30") is False
    assert CR.periods_agree("2026-06-30", None) is None
    assert CR.periods_agree("not-a-date", "2026-06-30") is None


def test_capex_from_a_DIFFERENT_quarter_is_refused_not_quietly_divided():
    """capex is the one figure from a second source. A ratio pairing this
    quarter's revenue with last quarter's capex is a real defect."""
    out = CR.compute(four(), capex_ttm=-40.0, capex_period_end="2026-03-31")
    assert out["capex_intensity_pct"] is None
    assert out["fcf_conversion_pct"] is None
    assert out["reasons"]["capex_intensity_pct"] == "capex_period_mismatch"
    assert out["ttm_capex"] is None      # not even stored on a mismatch


def test_capex_from_the_SAME_quarter_computes_intensity_and_conversion():
    """TTM revenue 400, capex 40 -> 10%. OCF 120 - 40 = 80 FCF over NI 40 =
    200%."""
    out = CR.compute(four(), capex_ttm=-40.0, capex_period_end="2026-06-30")
    assert out["ttm_capex"] == 40.0
    assert out["ttm_fcf"] == pytest.approx(80.0, abs=0.01)
    assert out["capex_intensity_pct"] == pytest.approx(10.0, abs=0.01)
    assert out["fcf_conversion_pct"] == pytest.approx(200.0, abs=0.01)


def test_a_missing_capex_line_blanks_only_the_capex_ratios():
    """MEASURED: Massive carries NO capex line at all (0/21), and yfinance
    misses the 2 mortgage REITs. Everything else must survive that."""
    out = CR.compute(four())
    assert out["capex_intensity_pct"] is None
    assert out["reasons"]["capex_intensity_pct"] == "no_capex"
    assert out["roce_pct"] is not None
    assert out["roe_pct"] is not None


def test_fcf_conversion_is_refused_against_a_negative_net_income():
    """Dividing good cash generation by a loss flips the sign and prints a
    healthy cash-converting company as a bad one."""
    out = CR.compute(four(ni=-10.0), capex_ttm=-40.0,
                     capex_period_end="2026-06-30")
    assert out["fcf_conversion_pct"] is None
    assert out["capex_intensity_pct"] is not None   # unaffected


def test_the_period_is_reported_and_a_derived_latest_quarter_is_declared():
    """RULE #7 — the as-of PERIOD, never the cache age."""
    out = CR.compute(four())
    assert out["period"] == "Q2 2026"
    assert out["period_end"] == "2026-06-30"
    assert out["period_is_derived"] is False
    rows = four()
    rows[0]["filing_date"] = None
    assert CR.compute(rows)["period_is_derived"] is True


# ═══════════════════════════════════════════ NEGATIVES — sectors, NaN, contract
def test_a_NON_OPERATING_sector_refuses_every_ratio_but_keeps_the_raw_figures():
    """A bank's deposits are liabilities and a mortgage REIT is levered by
    design. Same cohort `board_metrics.NON_OPERATING_SECTORS` already flags —
    measured there at 20.7% of this board."""
    out = CR.compute(four(), balance_meaningful=False)
    for f in ("roce_pct", "roic_pct", "roe_pct", "asset_turnover"):
        assert out[f] is None
        assert out["reasons"][f] == "non_operating_sector"
    assert out["total_assets"] == 1000.0        # drill-in can still show them
    assert out["ttm_ebit"] == 100.0


def test_NaN_in_the_provider_payload_never_reaches_a_served_value():
    """The house `_scrub` rule stops NaN at the payload edge; this stops it at
    the source, so it cannot poison a sum on the way there."""
    rows = four()
    rows[0]["financials"]["balance_sheet"]["assets"] = {"value": float("nan")}
    out = CR.compute(rows)
    for k, v in out.items():
        if isinstance(v, float):
            assert not math.isnan(v), k
            assert not math.isinf(v), k
    assert out["total_assets"] is None


def test_every_reason_this_module_can_emit_is_declared_in_REASONS():
    """A reason a surface cannot recognise renders as a mystery blank."""
    cases = [CR.compute([]), CR.compute(four(), balance_meaningful=False),
             CR.compute(four(equity=-1.0, prior_equity=-1.0)),
             CR.compute(four(tax=-5.0)), CR.compute(four(pretax=-1.0)),
             CR.compute(four(), capex_ttm=-1.0,
                        capex_period_end="2020-01-01")]
    seen = set()
    for c in cases:
        seen |= set((c.get("reasons") or {}).values())
    assert seen, "no refusals exercised"
    assert seen <= set(CR.REASONS), seen - set(CR.REASONS)


def test_an_empty_or_junk_payload_returns_the_full_shape_and_never_raises():
    """A board must not go down because a provider returned nothing."""
    for bad in ([], None, [{}], [{"fiscal_year": "x"}], ["not-a-dict"]):
        out = CR.compute(bad)
        assert out["roce_pct"] is None
        assert out["measured"] is False
        assert "reasons" in out


def test_the_module_declares_itself_UNMEASURED():
    """It is a screen built from accounting identities, not an edge. It must
    not borrow the credibility of anything that has been measured."""
    assert CR.MEASURED is False
    assert CR.compute(four())["measured"] is False


# ═══════════════════════════════════════════ the attach layer
def test_attach_flags_a_board_period_that_disagrees_with_the_balance_sheet():
    """ITEM #3. The growth board carries its own `period_end` from the income
    screen. A balance sheet drawn from a DIFFERENT quarter than the growth
    figures beside it pairs a numerator and a denominator from different points
    in time — a real defect, so it is detected and marked.

    MEASURED 2026-09-22 on the live board: 0 of 21 disagree today, which is
    exactly why the check has to be automatic rather than eyeballed once.
    """
    from sepa import board_metrics as BM
    row = {"symbol": "X", "period_end": "2026-06-30"}
    BM._attach_capital_returns(row, {"period_end": "2026-03-31",
                                     "measured": False, "reasons": {}})
    assert row["capital_period_mismatch"] is True
    row2 = {"symbol": "X", "period_end": "2026-06-30"}
    BM._attach_capital_returns(row2, {"period_end": "2026-06-28",
                                      "measured": False, "reasons": {}})
    assert row2["capital_period_mismatch"] is False


def test_attach_reports_unknown_not_agreement_when_a_period_is_missing():
    from sepa import board_metrics as BM
    row = {"symbol": "X"}
    BM._attach_capital_returns(row, {"period_end": "2026-06-30",
                                     "measured": False, "reasons": {}})
    assert row["capital_period_mismatch"] is None


def test_attach_marks_the_read_unmeasured_even_when_there_is_no_data():
    """A surface must never render these as if they were a measured edge, and
    an absent block must not silently drop the flag that says so."""
    from sepa import board_metrics as BM
    row = {"symbol": "X"}
    BM._attach_capital_returns(row, {})
    assert row["capital_measured"] is False
    assert row.get("roce_pct") is None


def test_attach_copies_every_declared_field_and_invents_none():
    from sepa import board_metrics as BM
    cr = CR.compute(four())
    row = {"symbol": "X", "period_end": "2026-06-30"}
    BM._attach_capital_returns(row, cr)
    for k in BM.CAPITAL_RETURN_FIELDS:
        assert k in row
    assert row["roce_pct"] == cr["roce_pct"]
    assert row["capital_period"] == "Q2 2026"
    assert row["capital_measured"] is False
