"""Sequential quarter-over-quarter income and growth (2026-09-12).

Ajay: *"May show any stage but prioritize income and growth only quarter over
quarter"*.

The board already printed quarterly YEAR-over-year. This is the other
comparison — Q0 against Q1 — and the tests that matter are the ones about what
it REFUSES to answer, because the failure mode here is not a wrong number, it is
a meaningless number winning the top of a board he trades.
"""
from __future__ import annotations

from sepa import qoq


# ── the arithmetic ─────────────────────────────────────────────────────────
def test_it_compares_the_latest_quarter_to_the_ONE_BEFORE_IT():
    """Not to the same quarter a year ago — that number already exists on the
    board and is a different fact."""
    out = qoq.compute(rev_series=[1.2e9, 1.0e9, 5.0e8, 4.0e8, 9.9e9],
                      eps_series=[0.50, 0.40, 0.10, 0.05, 9.99])
    assert out["growth_qoq_pct"] == 20.0          # 1.2 vs 1.0, NOT vs 9.9
    assert out["income_qoq_pct"] == 25.0


def test_a_sequential_DECLINE_is_reported_as_a_decline():
    out = qoq.compute(rev_series=[8.0e8, 1.0e9])
    assert out["growth_qoq_pct"] == -20.0


def test_two_quarters_is_ALL_it_needs():
    """The reason it covers names quarterly-YoY cannot: YoY needs five
    quarters. MEASURED on his board: revenue 59/80 vs 57/80, net income 66/80
    vs 56/80, and GOLD has a sequential number with no YoY at all."""
    out = qoq.compute(rev_series=[1.2e9, 1.0e9])
    assert out["growth_qoq_pct"] == 20.0
    assert qoq.QUARTERS_NEEDED == 2


# ── what it refuses ────────────────────────────────────────────────────────
def test_THE_BIG_ONE_a_negative_prior_quarter_yields_NO_PERCENTAGE():
    """21 of 80 sampled names had a negative prior-quarter EPS. -0.02 -> +0.30
    is "+1,600%" under (cur-prev)/|prev| and would own rank 1 on a board of
    250. It is not comparable to a profitable grower's +12%, so there is no
    percentage at all."""
    out = qoq.compute(eps_series=[0.30, -0.02])
    assert out["income_qoq_pct"] is None
    assert out["income_base"] == qoq.BASE_NON_POSITIVE


def test_the_turn_is_still_RECORDED_just_not_as_growth():
    """He should see a first profitable quarter. He should not see it ranked as
    if it were 1,600% growth."""
    assert qoq.compute(eps_series=[0.30, -0.02])["income_turn"] == "to_profit"
    assert qoq.compute(eps_series=[-0.05, -0.50])["income_turn"] == "narrowing"
    assert qoq.compute(eps_series=[-0.10, 0.40])["income_turn"] == "to_loss"
    assert qoq.compute(eps_series=[0.50, 0.40])["income_turn"] is None


def test_NEGATIVE_a_zero_base_is_refused_not_treated_as_infinite_growth():
    out = qoq.compute(eps_series=[0.30, 0.0])
    assert out["income_qoq_pct"] is None
    assert out["income_base"] == qoq.BASE_NON_POSITIVE


def test_THE_MEASURED_FLOOR_a_tiny_POSITIVE_base_is_refused_at_TEN_CENTS():
    """THE DEFECT THAT SHIPPED FIRST. A "require a positive base" rule catches
    none of these — measured on his live board, ELEVEN of the top twenty on the
    raw percentage were bought by a non-material base and NINE were tiny
    POSITIVE, not negative:

        CDNA +4,040%  $0.05 -> $2.07     SNPS +3,056%  $0.09 -> $2.84
        DBRG +3,733%  $0.03 -> $1.15     TXNM +2,033%  $0.03 -> $0.64
        MRVL   +725%  $0.04 -> $0.33     CNH  +1,000%  $0.01 -> $0.11

    None is a grower. CNH's eight quarters fall $0.34 -> $0.11 — a two-thirds
    DECLINE ranked fifth-best on the board. SNPS's $0.09 was one amortisation
    quarter. A $0.01 floor lets every one of them through."""
    assert qoq.MIN_EPS_BASE == 0.10
    for prior, latest in ((0.05, 2.07), (0.09, 2.84), (0.03, 1.15), (0.04, 0.33)):
        out = qoq.compute(eps_series=[latest, prior])
        assert out["income_qoq_pct"] is None, f"${prior} base must be refused"
        assert out["income_base"] == qoq.BASE_TOO_SMALL
    # and the real ones keep their number
    for prior, latest in ((0.19, 2.03), (1.73, 17.73), (0.27, 1.59)):
        assert qoq.compute(eps_series=[latest, prior])["income_qoq_pct"] is not None


def test_NEGATIVE_a_base_too_near_zero_is_refused_and_named_separately():
    """POSITIVE but a rounding error: 0.001 -> 0.02 is "+1,900%" and says
    nothing. Distinct from a loss on purpose — the page must not imply the
    company lost money when it merely earned almost nothing."""
    out = qoq.compute(eps_series=[0.02, 0.001])
    assert out["income_qoq_pct"] is None
    assert out["income_base"] == qoq.BASE_TOO_SMALL
    assert qoq.BASE_TOO_SMALL != qoq.BASE_NON_POSITIVE


def test_NEGATIVE_one_quarter_of_history_is_UNKNOWN_not_zero_growth():
    out = qoq.compute(rev_series=[1.0e9], eps_series=[0.4])
    assert out["growth_qoq_pct"] is None
    assert out["growth_base"] == qoq.BASE_UNKNOWN
    assert out["income_base"] == qoq.BASE_UNKNOWN


def test_NEGATIVE_a_HOLE_in_the_series_never_silently_becomes_Q0_vs_Q2():
    """The trap that would be invisible: if a missing Q1 were skipped, the
    board would print a two-quarter change and CALL it quarter-over-quarter.
    A hole is unknown."""
    out = qoq.compute(rev_series=[1.2e9, None, 1.0e9])
    assert out["growth_qoq_pct"] is None
    assert out["growth_base"] == qoq.BASE_UNKNOWN


def test_NEGATIVE_empty_and_missing_series_never_raise():
    for args in ({}, {"rev_series": []}, {"rev_series": None},
                 {"eps_series": [None, None]}):
        out = qoq.compute(**args)
        assert out["growth_qoq_pct"] is None and out["income_qoq_pct"] is None


def test_NEGATIVE_a_NaN_is_treated_as_missing_not_as_a_number():
    out = qoq.compute(rev_series=[float("nan"), 1.0e9])
    assert out["growth_qoq_pct"] is None


# ── the blend ──────────────────────────────────────────────────────────────
def rows(*pairs):
    return [{"income_qoq_pct": i, "growth_qoq_pct": g} for i, g in pairs]


def test_THE_OUTLIER_GUARD_one_giant_print_does_not_own_the_board():
    """Blended raw, a +5,000% EPS print decides the whole order by itself.
    Blended by PERCENTILE it is worth exactly one rank more than +40%."""
    r = rows((5000.0, 3.0), (40.0, 90.0), (20.0, 50.0))
    qoq.score_board(r)
    assert r[0]["qoq_score"] < r[1]["qoq_score"], \
        "the 5,000% name has the WORST growth leg and must not lead"


def test_it_ranks_on_BOTH_legs_not_whichever_is_larger():
    r = rows((10.0, 10.0), (90.0, 90.0), (90.0, 10.0))
    qoq.score_board(r)
    assert r[1]["qoq_score"] > r[2]["qoq_score"] > r[0]["qoq_score"]


def test_a_name_with_ONE_leg_is_scored_on_that_leg_and_SAYS_SO():
    """Neither invented (handing it the other leg's median) nor hidden
    (dropping a real breakout over a filing gap)."""
    r = rows((50.0, None), (50.0, 50.0))
    qoq.score_board(r)
    assert r[0]["qoq_score"] is not None
    assert r[0]["qoq_legs"] == 1 and r[1]["qoq_legs"] == 2


def test_NEGATIVE_a_name_with_NO_legs_scores_None_and_never_a_zero():
    """A zero would sort above every genuine decliner — an unknown reading as
    the favourable state, which is the failure this whole app guards."""
    r = rows((None, None), (-80.0, -80.0))
    qoq.score_board(r)
    assert r[0]["qoq_score"] is None
    assert r[0]["qoq_legs"] == 0
    assert r[1]["qoq_score"] is not None


def test_NEGATIVE_ties_share_a_percentile_and_are_not_ordered_by_accident():
    r = rows((10.0, 10.0), (10.0, 10.0), (90.0, 90.0))
    qoq.score_board(r)
    assert r[0]["qoq_score"] == r[1]["qoq_score"] < r[2]["qoq_score"]


def test_NEGATIVE_a_board_of_one_does_not_divide_by_zero():
    r = rows((10.0, 10.0))
    qoq.score_board(r)
    assert r[0]["qoq_score"] == 100.0


def test_NEGATIVE_an_all_unknown_board_scores_every_row_None():
    r = rows((None, None), (None, None))
    qoq.score_board(r)
    assert [x["qoq_score"] for x in r] == [None, None]


def test_the_module_makes_no_forward_claim():
    doc = " ".join((qoq.__doc__ or "").split())
    assert "nothing here is a claim" in doc.lower()
    assert "no study in this app measures" in doc.lower()


# ── seasonality ────────────────────────────────────────────────────────────
# THE ONE REAL OBJECTION to a sequential read, and it is Minervini's: a
# retailer's January quarter is smaller than its December quarter EVERY year,
# and raw sequential calls that a collapse. Quarter-vs-same-quarter-prior-year
# exists to cancel exactly this.
#
# MEASURED on his board 2026-09-12: median sequential revenue by fiscal
# transition is +5.3% for Q1->Q2 (31% negative) against -4.0% for Q4->Q1 (63%
# negative) — a fiscal-Q1 reporter is docked ~9 points for no business reason.
# Sequential revenue correlates 0.376 with the SAME transition a year earlier
# and 0.023 with the adjacent one: the seasonal component is real and repeats.
def seasonal_series(this_year, last_year):
    """Newest-first revenue where slots 0/1 are this year's transition and
    slots 4/5 are the same transition a year ago."""
    return [this_year[0], this_year[1], 1.0, 1.0, last_year[0], last_year[1]]


def test_it_reads_the_SAME_transition_one_year_earlier_not_the_adjacent_one():
    out = qoq.compute(rev_series=seasonal_series([1.0e9, 6.0e8], [9.0e8, 5.5e8]))
    assert out["growth_qoq_pct"] == 66.67
    assert out["growth_qoq_ly_pct"] == 63.64


def test_a_move_the_name_makes_EVERY_year_is_FLAGGED_not_celebrated():
    """+66% sequentially looks explosive until you see it did +64% at the same
    point last year. Genuine improvement: 3 points."""
    out = qoq.compute(rev_series=seasonal_series([1.0e9, 6.0e8], [9.0e8, 5.5e8]))
    assert out["seasonal_echo"] is True
    assert out["growth_vs_seasonal_pp"] == 3.03


def test_a_GENUINE_acceleration_is_not_flagged_as_seasonal():
    """Same transition, +4% last year and +66% now — that is not the calendar."""
    out = qoq.compute(rev_series=seasonal_series([1.0e9, 6.0e8], [5.2e8, 5.0e8]))
    assert out["seasonal_echo"] is False
    assert out["growth_vs_seasonal_pp"] == 62.67


def test_the_flag_needs_the_SAME_SIGN_not_just_a_big_prior_move():
    """A name that fell 30% at this transition last year and rose 40% now has
    broken its pattern — the opposite of a seasonal echo."""
    out = qoq.compute(rev_series=seasonal_series([1.4e9, 1.0e9], [7.0e8, 1.0e9]))
    assert out["seasonal_echo"] is False


def test_NEGATIVE_no_prior_year_transition_means_no_flag_and_no_adjustment():
    """Four quarters of history cannot answer the seasonal question, and a
    missing answer must not read as 'not seasonal, verified'."""
    out = qoq.compute(rev_series=[1.0e9, 6.0e8, 5.0e8, 4.0e8])
    assert out["growth_qoq_pct"] == 66.67
    assert out["growth_qoq_ly_pct"] is None
    assert out["growth_vs_seasonal_pp"] is None
    assert out["seasonal_echo"] is False


# ── what the RANK is computed on ───────────────────────────────────────────
def test_the_rank_uses_the_SEASONALLY_REFERENCED_move_by_default():
    """It is still quarter over quarter — measured against the company's own
    calendar instead of against zero."""
    inc, gro, basis = qoq.rank_values(
        qoq.compute(rev_series=seasonal_series([1.0e9, 6.0e8], [9.0e8, 5.5e8])))
    assert gro == 3.03 and basis == "seasonal"


def test_it_FALLS_BACK_to_the_raw_sequential_move_and_says_so():
    """A name without a prior-year transition stays in the ranking rather than
    dropping out of it — and the basis is recorded so the page can say which
    reading a row was ranked on."""
    inc, gro, basis = qoq.rank_values(qoq.compute(rev_series=[1.0e9, 6.0e8]))
    assert gro == 66.67 and basis == "raw"


def test_the_raw_reading_is_still_available_on_demand():
    q = qoq.compute(rev_series=seasonal_series([1.0e9, 6.0e8], [9.0e8, 5.5e8]))
    inc, gro, basis = qoq.rank_values(q, seasonal=False)
    assert gro == 66.67 and basis == "raw"


def test_THE_MEASUREMENT_THAT_DROVE_THIS_IS_RECORDED_IN_THE_SOURCE():
    """A default that departs from his literal words must carry its reason
    where the next reader will find it, with the placebo beside it."""
    doc = " ".join((qoq.rank_values.__doc__ or "").split())
    assert "PLACEBO" in doc
    assert "+24.0%" in doc and "+0.4%" in doc


def test_NEGATIVE_a_seasonal_echo_is_never_SILENTLY_dropped_from_the_board():
    """He asked for quarter over quarter and gets it. The flag is information,
    not a filter — there is no code path that removes a row for being
    seasonal."""
    import inspect
    src = inspect.getsource(qoq)
    assert "seasonal_echo" in src
    for filt in ("if seasonal_echo", "not row[\"seasonal_echo\"]", "seasonal_echo is False and"):
        assert filt not in src


def test_the_seasonal_norm_AVERAGES_two_prior_years_not_one():
    """One prior year is a bet that year was not strange. The quarterly fetch
    widened to 12 quarters on 2026-09-12 so this can average two observations
    of the same transition."""
    # slots:        0     1     2  3  4(=+50%)  5     6  7  8(=+10%) 9
    rev = [1.5e9, 1.0e9, 1, 1, 1.5e9, 1.0e9, 1, 1, 1.1e9, 1.0e9]
    out = qoq.compute(rev_series=rev)
    assert out["growth_qoq_pct"] == 50.0
    assert out["growth_qoq_ly_pct"] == 30.0          # mean of +50 and +10
    assert out["growth_vs_seasonal_pp"] == 20.0
    assert qoq.SEASONAL_SLOTS == ((4, 5), (8, 9))


def test_ONE_prior_year_is_still_used_when_that_is_all_there_is():
    rev = [1.5e9, 1.0e9, 1, 1, 1.5e9, 1.0e9]
    assert qoq.compute(rev_series=rev)["growth_qoq_ly_pct"] == 50.0


def test_the_seasonality_MEASUREMENT_and_its_PLACEBO_live_in_the_source():
    """A default that departs from his literal words carries its evidence where
    the next reader will find it — spread AND placebo AND p, per his standing
    rule that no measured number ships as a bare point estimate."""
    doc = " ".join((qoq._seasonal_norm.__doc__ or "").split())
    assert "placebo" in doc.lower()
    assert "p=0.0005" in doc
    assert "ZYME" in doc


def test_the_SCORED_screens_still_see_exactly_eight_quarters():
    """Widening the fetch must not move `sales.score` or `earnings_quality` —
    both are book-cited and thresholded. A methodology that drifts as a side
    effect of an unrelated feature is a methodology nobody decided to change."""
    from sepa import canslim
    import inspect
    assert canslim._head8(list(range(12))) == list(range(8))
    assert canslim._head8(None) is None
    src = inspect.getsource(canslim)
    for call in ("sales.compute(_head8(", "_head8(m.get(\"eps_q_series\"))"):
        assert call in src
    assert 'sales.compute(m.get("rev_q_series")' not in src


# ── array position is NOT quarter adjacency ────────────────────────────────
# Massive OMITS a quarter it does not have rather than leaving a placeholder,
# so slot 0 and slot 1 are not necessarily consecutive. ORCL is missing Q2
# FY2025 and Q2 FY2026; NVDA is missing Q1 FY2025. Measured over 200 of his
# board names: 3.2% of "sequential" pairs span two quarters, and 12.6% of the
# YEAR-over-year pairs the board has printed for months are not four quarters
# apart — ASO's compares 2027Q2 against 2025Q4.
Q = lambda fy, q: fy * 4 + (q - 1)                                  # noqa: E731


def test_a_verified_adjacent_pair_is_computed_normally():
    out = qoq.compute(rev_series=[1.5e9, 1.0e9],
                      periods=[Q(2026, 2), Q(2026, 1)])
    assert out["growth_qoq_pct"] == 50.0
    assert out["periods_checked"] is True


def test_NEGATIVE_a_GAP_between_the_two_newest_filings_is_REFUSED():
    """Printing a two-quarter change and calling it quarter-over-quarter is a
    confident false label — worse than an em-dash."""
    out = qoq.compute(rev_series=[1.5e9, 1.0e9], eps_series=[0.5, 0.4],
                      periods=[Q(2026, 3), Q(2026, 1)])
    assert out["growth_qoq_pct"] is None
    assert out["income_qoq_pct"] is None
    assert out["growth_base"] == qoq.BASE_NOT_ADJACENT
    assert qoq.BASE_NOT_ADJACENT not in (qoq.BASE_UNKNOWN, qoq.BASE_NON_POSITIVE)


def test_NEGATIVE_a_seasonal_slot_that_is_not_a_WHOLE_YEAR_back_is_skipped():
    """Slot 4 is only "the same transition a year ago" when it really is four
    quarters back. With a hole in the history it can be five — a different
    season, silently used as this one's norm."""
    good = qoq.compute(rev_series=[1.5e9, 1.0e9, 1, 1, 1.5e9, 1.0e9],
                       periods=[Q(2026, 2), Q(2026, 1), Q(2025, 4), Q(2025, 3),
                                Q(2025, 2), Q(2025, 1)])
    assert good["growth_qoq_ly_pct"] == 50.0
    bad = qoq.compute(rev_series=[1.5e9, 1.0e9, 1, 1, 1.5e9, 1.0e9],
                      periods=[Q(2026, 2), Q(2026, 1), Q(2025, 4), Q(2025, 3),
                               Q(2024, 3), Q(2024, 2)])     # five back, not four
    assert bad["growth_qoq_ly_pct"] is None


def test_NEGATIVE_an_UNVERIFIABLE_pair_is_ACCEPTED_not_dropped():
    """Legacy cached documents carry no period keys. Refusing every one of them
    would blank the ranking rather than improve it — so they compute, and
    `periods_checked` says they were not verified."""
    out = qoq.compute(rev_series=[1.5e9, 1.0e9], periods=None)
    assert out["growth_qoq_pct"] == 50.0
    assert out["periods_checked"] is False
    out2 = qoq.compute(rev_series=[1.5e9, 1.0e9], periods=[None, None])
    assert out2["growth_qoq_pct"] == 50.0


def test_the_backfill_treats_a_document_with_NO_period_keys_as_missing():
    """Otherwise every row cached before today keeps an unverifiable pair
    forever and the nightly fill would skip it as already done."""
    assert qoq._series_missing({"fundamentals": {"rev_q_series": [1, 2]}}) is True
    assert qoq._series_missing({"fundamentals": {
        "rev_q_series": [1, 2], "q_period_series": [8105, 8104]}}) is False


def test_the_seasonal_norm_is_a_MEDIAN_not_a_mean():
    """Measured 2026-09-12: one near-zero-revenue quarter gave ATRC a "typical
    Q2" of +4,825% and destroyed the adjustment outright. The base floors
    already refuse that case; the median does not depend on them staying
    right."""
    import inspect
    src = inspect.getsource(qoq._seasonal_norm)
    assert "MEDIAN, not mean" in src
    assert "ATRC" in src
    # three prior observations: +10, +12, +4825 -> median 12, mean 1615
    rev = [2.0e9, 1.0e9, 1, 1,
           1.10e9, 1.0e9, 1, 1,
           1.12e9, 1.0e9]
    out = qoq.compute(rev_series=rev)
    assert out["growth_qoq_ly_pct"] == 11.0        # mean of the two = median
