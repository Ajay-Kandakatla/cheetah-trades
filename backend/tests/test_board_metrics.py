"""Board fundamentals — dilution, cash vs debt, EV/Sales, FCF yield.

Ajay 2026-09-13. The NEGATIVES carry this file: every one of these columns is a
number a reader will act on, and the ways each can be silently WRONG are worse
than the ways it can be missing. Two real defects are pinned here because both
produced confident, plausible, catastrophically wrong values on the live board
before they were caught.
"""
from __future__ import annotations

import pytest

from sepa import board_metrics as BM


def q(fy, fp, shares, filed="2026-01-01"):
    return {"fiscal_year": fy, "fiscal_period": fp, "filing_date": filed,
            "end_date": "2026-01-01",
            "financials": {"income_statement": {
                "diluted_average_shares": {"value": shares}}}}


# ───────────────────────────────────────────── the derived-Q4 trap
def test_a_DERIVED_quarter_is_dropped_because_it_has_no_filing_date():
    """MEASURED LIVE 2026-09-13. 23.8% of the provider's quarterly rows are
    derived Q4s — annual minus the three reported quarters — and for an AVERAGE
    share count that subtraction is nonsense: NVDA's reads -28,000,000."""
    rows = [q(2026, "Q4", -28_000_000, filed=None), q(2026, "Q3", 24_483_000_000)]
    kept = BM._reported_quarters(rows)
    assert [k["shares"] for k in kept] == [24_483_000_000]


def test_NEGATIVE_the_guard_is_the_filing_date_NOT_a_magnitude_floor():
    """THE TRAP INSIDE THE TRAP, and why this test exists.

    MU's corrupt derived value is 2,000,000 — a perfectly ordinary share count
    for a real microcap. A "drop anything implausibly small" guard would pass
    MU's garbage AND reject genuine small names. `filing_date is None` separates
    derived from reported exactly, with no invented number."""
    corrupt_but_plausible = q(2025, "Q4", 2_000_000, filed=None)
    genuine_microcap = q(2026, "Q1", 2_000_000, filed="2026-02-01")
    assert BM._reported_quarters([corrupt_but_plausible]) == []
    assert len(BM._reported_quarters([genuine_microcap])) == 1
    # ...and the module must not have grown a magnitude floor behind our backs.
    src = open(BM.__file__).read()
    assert "MIN_SANE_SHARES" not in src and "MIN_SHARES" not in src


def test_NEGATIVE_a_non_positive_share_count_is_dropped():
    assert BM._reported_quarters([q(2025, "Q4", -168_000, filed="2025-03-01")]) == []
    assert BM._reported_quarters([q(2025, "Q4", 0, filed="2025-03-01")]) == []


# ───────────────────────────────────────────── the RKT basis flip
def test_NEGATIVE_an_OSCILLATING_share_basis_blanks_instead_of_reporting_1559pct():
    """THE RKT DEFECT, caught on the live board before it shipped.

    Rocket Companies measured +1,559% dilution and is not diluting: its up-C
    units drop out of the EPS denominator in the quarters where they are
    anti-dilutive, so a Q2-vs-Q2 read compares a near-basic denominator against
    a fully-diluted one. Arithmetic perfect, number meaningless."""
    rows = [q(2026, "Q2", 2_843_538_118), q(2026, "Q1", 2_846_974_742),
            q(2025, "Q3", 2_106_227_188), q(2025, "Q2", 171_438_105),
            q(2025, "Q1", 2_001_936_379)]
    out = BM.shares_yoy(rows)
    assert out["pct"] is None
    assert out["reason"] == "unstable_share_basis"
    assert out["flip"] == ["Q3 2025", "Q2 2025"]


def test_a_REAL_heavy_diluter_still_reports_its_number():
    """The mirror, so the basis guard cannot be over-tightened into hiding the
    exact names the column exists for. PROP's real series is smooth and
    monotonic — 16.7M to 185.6M — and must survive."""
    rows = [q(2026, "Q2", 185_590_890), q(2026, "Q1", 80_585_148),
            q(2025, "Q3", 50_624_457), q(2025, "Q2", 44_063_281),
            q(2025, "Q1", 26_796_704)]
    out = BM.shares_yoy(rows)
    assert out["reason"] is None
    assert out["pct"] == pytest.approx(321.2, abs=0.5)


# ───────────────────────────────────────────── period adjacency
def test_the_comparison_is_the_SAME_fiscal_quarter_a_year_earlier():
    rows = [q(2026, "Q2", 110), q(2026, "Q1", 105), q(2025, "Q2", 100)]
    out = BM.shares_yoy(rows)
    assert out["pct"] == pytest.approx(10.0)
    assert out["period"] == "Q2 2026" and out["prior_period"] == "Q2 2025"


def test_NEGATIVE_no_year_ago_quarter_REFUSES_rather_than_using_the_oldest():
    """Falling back to "the oldest quarter we have" silently compares across a
    different number of quarters and reports it as a year of dilution."""
    rows = [q(2026, "Q2", 200), q(2026, "Q1", 100)]
    out = BM.shares_yoy(rows)
    assert out["pct"] is None and out["reason"] == "no_year_ago_quarter"


def test_NEGATIVE_a_suspected_split_blanks_the_cell():
    rows = [q(2026, "Q2", 1_000_000_000), q(2025, "Q2", 900_000_000)]
    out = BM.shares_yoy(rows, live_shares=50_000_000)   # 20x away — a consolidation
    assert out["pct"] is None and out["reason"] == "split_suspected"


def test_period_index_handles_a_NON_CALENDAR_fiscal_year():
    """MU, NVDA and HNI all run off-calendar fiscal years. The index makes
    "one year earlier" a subtraction instead of a date guess."""
    assert BM._period_index({"fiscal_year": 2026, "fiscal_period": "Q2"}) \
        - BM._period_index({"fiscal_year": 2025, "fiscal_period": "Q2"}) == BM.YOY_GAP
    assert BM._period_index({"fiscal_year": 2026, "fiscal_period": "FY"}) is None
    assert BM._period_index({"fiscal_year": None, "fiscal_period": "Q1"}) is None


# ───────────────────────────────────────────── sector honesty
def test_non_operating_sectors_are_FLAGGED_not_silently_rendered():
    """A bank's deposits are liabilities and a mortgage REIT is levered by
    design — ARR and NLY measure EV/Sales at 41x and 44x. Rendering those as
    ordinary numbers invites exactly the wrong read."""
    assert "Financial Services" in BM.NON_OPERATING_SECTORS
    assert "Real Estate" in BM.NON_OPERATING_SECTORS
    assert "Technology" not in BM.NON_OPERATING_SECTORS


def test_attach_puts_FLAT_keys_on_a_row_and_leaves_an_unknown_row_alone():
    rows = [{"symbol": "AAA"}, {"symbol": "ZZZ"}]
    snap = {"AAA": {"shares_yoy": {"pct": 12.5, "reason": None, "period": "Q2 2026"},
                    "cash": 10.0, "debt": 4.0, "cash_minus_debt": 6.0,
                    "ev_sales": 3.0, "fcf_yield": 1.5, "sector": "Technology",
                    "balance_meaningful": True}}
    BM.snapshot = lambda syms, db=None, max_age_sec=None: snap      # type: ignore
    out = BM.attach(rows)
    assert out[0]["shares_yoy_pct"] == 12.5 and out[0]["ev_sales"] == 3.0
    # A row the cache cannot answer for keeps NO metric keys at all, so the
    # frontend renders an em-dash rather than a zero.
    assert "shares_yoy_pct" not in out[1] and "ev_sales" not in out[1]


def test_the_module_says_WHY_it_is_board_scoped_not_universe_scoped():
    """SOURCE GUARD. The whole design rests on a measurement — the weekly
    universe cron fills 40%, a board-sized list fills 98-100% — and an edit
    that moves this into the universe cache has to delete that first."""
    src = open(BM.__file__).read()
    assert "39.6%" in src and "98.8%" in src
    assert "a column blank for a third of the board is worse than no column" in src


# ───────────────────────────────────────────── float / cap (2026-09-20)
class _Info:
    """A yfinance ticker double — `.info` only, which is all this path reads."""

    def __init__(self, info):
        self.info = info


def _patch_info(monkeypatch, info):
    from sepa import symbols as S
    monkeypatch.setattr(S, "yf_ticker", lambda sym: _Info(info))


def test_balance_metrics_stores_float_and_cap_as_PLAIN_floats(monkeypatch):
    """The Bonde float leg reads these, and `bonde_api._scrub` has to hand the
    frontend JSON — a numpy scalar out of yfinance serialises as garbage."""
    _patch_info(monkeypatch, {"floatShares": 1.8e7, "sharesOutstanding": 2.1e7,
                              "marketCap": 4e9, "sector": "Technology"})
    out = BM.balance_metrics("FOO")
    assert out["float_shares"] == 1.8e7 and type(out["float_shares"]) is float
    assert out["shares_outstanding"] == 2.1e7
    assert out["market_cap"] == 4e9 and type(out["market_cap"]) is float


def test_NEGATIVE_a_missing_floatShares_is_None_not_a_small_float(monkeypatch):
    """ADRs and thin names omit `floatShares`. Reading the absence as 0 — or
    falling back to shares outstanding — would mint a false "tiny float ✓"."""
    _patch_info(monkeypatch, {"sharesOutstanding": 2.1e7, "marketCap": 4e9})
    out = BM.balance_metrics("ADR")
    assert out["float_shares"] is None
    assert out["shares_outstanding"] == 2.1e7


def test_NEGATIVE_a_NaN_float_share_count_is_None(monkeypatch):
    _patch_info(monkeypatch, {"floatShares": float("nan"), "marketCap": float("inf")})
    out = BM.balance_metrics("NAN")
    assert out["float_shares"] is None and out["market_cap"] is None


def test_attach_flattens_market_cap_and_float(monkeypatch):
    rows = [{"symbol": "AAA"}]
    monkeypatch.setattr(BM, "snapshot", lambda syms, db=None, max_age_sec=None: {
        "AAA": {"market_cap": 4e9, "float_shares": 1.8e7,
                "shares_outstanding": 2.1e7, "sector": "Technology"}})
    out = BM.attach(rows)
    assert out[0]["market_cap"] == 4e9
    assert out[0]["float_shares"] == 1.8e7
    assert out[0]["shares_outstanding"] == 2.1e7


def test_NEGATIVE_a_PRE_2026_09_20_doc_shape_flattens_to_None_not_a_KeyError(monkeypatch):
    """419 docs were written before `float_shares` existed and stay that way
    until `warm --all` or the 36h TTL rolls. The board must render an unknown,
    not throw on a missing key."""
    rows = [{"symbol": "AAA"}]
    monkeypatch.setattr(BM, "snapshot", lambda syms, db=None, max_age_sec=None: {
        "AAA": {"cash": 10.0, "debt": 4.0, "sector": "Technology",
                "balance_meaningful": True}})
    out = BM.attach(rows)
    assert out[0]["float_shares"] is None
    assert out[0]["market_cap"] is None
    assert out[0]["cash"] == 10.0
