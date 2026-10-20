"""Shareholders' equity on the company headline = the FILED balance sheet first (2026-10-20).

Ajay 2026-10-20, the SXTC card: "Share holders queirty is werong". The card showed $25.69B on a $1.2M company —
Yahoo's `bookValue` per share ($2,480.58, stale after serial reverse splits) × today's 10,357,498 shares. The 20-F
filed 2026-07-01 says $29,707,422 (SEC XBRL, identical through the house helper). The same product gave BRK-B
$735T (the A-share book value per share × the B-share count), CDT $4.59B, NIVF $2.39B, TWG $1.13B.

Hermetic: yfinance and the Massive helper are monkeypatched; nothing touches the network.
"""
from __future__ import annotations

import pytest

from sepa import card_enrichment as CE
from sepa import massive_fundamentals as MF
from sepa import stock_analysis as SA


# ── fixtures ────────────────────────────────────────────────────────────────
SXTC_INFO = {"marketCap": 1151754, "totalRevenue": 1138052, "bookValue": 2480.58,
             "sharesOutstanding": 10357498, "enterpriseValue": -27155066, "totalDebt": 1120986,
             "totalCash": 28320836, "financialCurrency": "USD"}
BRKB_INFO = {"marketCap": 1_094_908_840_000, "bookValue": 522225.9, "sharesOutstanding": 1_408_035_161}
PLAIN_INFO = {"marketCap": 20_000_000, "bookValue": 10.0, "sharesOutstanding": 1_000_000}


def _row(end, equity=None, parent=None, *, fp="FY", fy=2026, filed="2026-07-01"):
    bal = {}
    if equity is not None:
        bal["equity"] = {"value": equity}
    if parent is not None:
        bal["equity_attributable_to_parent"] = {"value": parent}
    return {"fiscal_year": fy, "fiscal_period": fp, "end_date": end, "filing_date": filed,
            "financials": {"balance_sheet": bal, "income_statement": {}}, "source": "massive_v1"}


class _Tk:
    def __init__(self, info):
        self.info = info


@pytest.fixture
def yf(monkeypatch):
    """Point the panel's yfinance read at a canned `.info`."""
    def _set(info):
        monkeypatch.setattr(SA.symbols, "yf_ticker", lambda sym: _Tk(dict(info)))
    return _set


@pytest.fixture
def helper(monkeypatch):
    """Point the ONE financials helper at canned reports per (symbol, timeframe); records the calls."""
    calls = []

    def _set(table):
        def fake(symbol, *, timeframe, limit, statements=MF.ALL_STATEMENTS, timeout=12.0, key=None):
            calls.append((symbol, timeframe, limit, tuple(statements), timeout))
            ans = table.get((symbol, timeframe), [])
            if isinstance(ans, Exception):
                raise ans
            return list(ans)
        monkeypatch.setattr(MF, "fetch_reports", fake)
        return calls
    return _set


def _headline(sym="SXTC", **kw):
    panel = SA.fundamental_panel(sym, **kw)
    assert panel["available"] in (True, False)
    return panel["headline"]


# ── the SXTC case ───────────────────────────────────────────────────────────
def test_sxtc_the_filed_balance_sheet_beats_yahoos_product(yf, helper):
    yf(SXTC_INFO)
    calls = helper({("SXTC", "quarterly"): [], ("SXTC", "annual"): [_row("2026-03-31", 29707422.0, 29707422.0),
                                                                     _row("2025-03-31", 15439762.0, 15439762.0, fy=2025)]})
    h = _headline("SXTC")
    assert h["shareholder_equity"] == 29707422.0
    assert h["equity_source"] == "filing" and h["equity_status"] == "filing"
    assert h["equity_as_of"] == "2026-03-31"
    assert h["equity_filed"] == "2026-07-01"
    assert h["equity_period"] == "FY 2026"
    assert h["equity_note"] == ("Filed balance sheet (FY 2026), period ended 2026-03-31, filed 2026-07-01 — "
                                "total equity attributable to shareholders.")
    # Yahoo's inputs are still served (nothing hidden), only the product is no longer the figure.
    assert h["book_value_per_share"] == 2480.58 and h["shares_outstanding"] == 10357498
    assert h["market_cap"] == 1151754 and h["enterprise_value"] == -27155066
    # income spine + balance sheet only, never the cash flow — one period per series, the short timeout.
    assert all(c[3] == (MF.INCOME, MF.BALANCE) and c[2] == 1 and c[4] == SA.HELPER_TIMEOUT_SEC for c in calls)
    assert [c[1] for c in calls] == ["quarterly", "annual"]


def test_NEGATIVE_the_old_product_is_what_the_card_showed():
    """The pre-fix figure, reproduced from the same inputs — the number he screenshotted."""
    assert round(SXTC_INFO["bookValue"] * SXTC_INFO["sharesOutstanding"], 2) == 25692602388.84


# ── which filed row ─────────────────────────────────────────────────────────
def test_equity_attributable_to_parent_is_preferred_over_total_equity(yf, helper):
    yf(PLAIN_INFO)
    helper({("BRK.B", "annual"): [_row("2025-12-31", 719703000000.0, 717419000000.0, fy=2025, filed="2026-08-10")]})
    h = _headline("BRK-B")
    assert h["shareholder_equity"] == 717419000000.0
    assert h["equity_source"] == "filing"
    assert "total equity attributable to shareholders" in h["equity_note"]


def test_total_equity_is_used_when_the_parent_line_is_absent_and_the_note_says_so(yf, helper):
    yf(PLAIN_INFO)
    helper({("CDT", "quarterly"): [_row("2026-06-30", 103093000.0, None, fp="Q2", filed="2026-08-12")]})
    h = _headline("CDT")
    assert h["shareholder_equity"] == 103093000.0 and h["equity_period"] == "Q2 2026"
    assert "including any minority interest" in h["equity_note"]
    assert "attributable to shareholders" not in h["equity_note"]


def test_the_newest_period_end_wins_across_the_two_series(yf, helper):
    yf(PLAIN_INFO)
    helper({("CDT", "quarterly"): [_row("2026-06-30", 103093000.0, fp="Q2", filed="2026-08-12")],
            ("CDT", "annual"): [_row("2025-12-31", -7170000.0, fy=2025, filed="2026-08-12")]})
    h = _headline("CDT")
    assert h["shareholder_equity"] == 103093000.0 and h["equity_as_of"] == "2026-06-30"


def test_an_older_quarterly_row_loses_to_a_newer_annual_row(yf, helper):
    yf(PLAIN_INFO)
    helper({("X", "quarterly"): [_row("2025-09-30", 20233535.0, fp="Q2", filed="2025-12-31")],
            ("X", "annual"): [_row("2026-03-31", 29707422.0)]})
    assert _headline("X")["equity_as_of"] == "2026-03-31"


def test_on_a_tie_the_row_that_names_its_filing_date_wins(yf, helper):
    """A derived Q4 row ends on the FY date but carries no filing date (the helper's design) — the FY row wins."""
    yf(PLAIN_INFO)
    helper({("X", "quarterly"): [_row("2025-12-31", 5_000_000.0, fp="Q4", fy=2025, filed=None)],
            ("X", "annual"): [_row("2025-12-31", 5_000_000.0, fp="FY", fy=2025, filed="2026-02-20")]})
    h = _headline("X")
    assert h["equity_period"] == "FY 2025" and h["equity_filed"] == "2026-02-20"
    assert "filed 2026-02-20" in h["equity_note"]


def test_negative_filed_equity_is_a_real_figure_and_is_served(yf, helper):
    yf(PLAIN_INFO)
    helper({("CDT", "annual"): [_row("2025-12-31", -7170000.0, fy=2025)]})
    h = _headline("CDT")
    assert h["shareholder_equity"] == -7170000.0 and h["equity_source"] == "filing"


def test_class_shares_are_asked_with_massives_dotted_spelling(yf, helper):
    yf(PLAIN_INFO)
    calls = helper({})
    _headline("BRK-B")
    assert calls and all(c[0] == "BRK.B" for c in calls)


def test_a_company_reporting_in_another_currency_gets_the_hint_in_its_note(yf, helper):
    yf({**PLAIN_INFO, "financialCurrency": "JPY"})
    helper({("SONY", "annual"): [_row("2026-03-31", 53686692234.0, 51198483366.0, filed="2026-06-18")]})
    h = _headline("SONY")
    assert h["shareholder_equity"] == 51198483366.0
    assert h["equity_note"].endswith("The company reports in JPY; the figure is as the filings provider serves it, not converted here.")


def test_NEGATIVE_a_usd_filer_gets_no_currency_hint(yf, helper):
    yf({**PLAIN_INFO, "financialCurrency": "USD"})
    helper({("X", "annual"): [_row("2026-03-31", 1_000_000.0)]})
    assert "reports in" not in _headline("X")["equity_note"]


def test_an_etf_never_asks_the_filings_helper(yf, helper):
    yf(PLAIN_INFO)
    calls = helper({("SPY", "annual"): [_row("2026-03-31", 1.0)]})
    h = _headline("SPY", is_etf=True)
    assert calls == []
    assert h["equity_status"] == "skipped" and h["equity_source"] == "derived"
    assert h["equity_note"].startswith("Filings are not read for a fund")


# ── NEGATIVES: no filing ────────────────────────────────────────────────────
def test_NEGATIVE_provider_trouble_falls_back_to_a_plausible_product_and_says_the_provider_did_not_answer(yf, helper):
    yf(PLAIN_INFO)
    calls = helper({("X", "quarterly"): MF.FinancialsUnavailable("rate_limited", symbol="X", status=429),
                    ("X", "annual"): MF.FinancialsUnavailable("rate_limited", symbol="X", status=429)})
    h = _headline("X")
    assert h["shareholder_equity"] == 10_000_000.0
    assert h["equity_source"] == "derived" and h["equity_status"] == "unavailable" and h["equity_as_of"] is None
    assert h["equity_note"].startswith("The filings provider did not answer (rate_limited)")
    assert "book value per share" in h["equity_note"] and h["equity_note"].endswith("Estimated.")
    assert "No filed balance sheet" not in h["equity_note"]
    # the second series is not asked once the provider fails.
    assert [c[1] for c in calls] == ["quarterly"]


def test_NEGATIVE_an_outage_after_a_good_quarterly_row_still_serves_the_filing(yf, helper):
    yf(PLAIN_INFO)
    helper({("X", "quarterly"): [_row("2026-06-30", 7_000_000.0, fp="Q2", filed="2026-08-12")],
            ("X", "annual"): MF.FinancialsUnavailable("server_error", symbol="X", status=503)})
    h = _headline("X")
    assert h["shareholder_equity"] == 7_000_000.0 and h["equity_status"] == "filing"


def test_NEGATIVE_an_empty_answer_with_an_implausible_product_is_refused(yf, helper):
    """BRK-B before the dotted spelling: Yahoo's A-share book value per share × the B-share count = $735T."""
    yf(BRKB_INFO)
    helper({})
    h = _headline("BRK-B")
    assert h["shareholder_equity"] is None and h["equity_source"] is None and h["equity_status"] == "none"
    assert h["equity_note"].startswith("Refused") and "735" in h["equity_note"]
    assert h["equity_note"].endswith("No filed balance sheet was found under this ticker.")


def test_NEGATIVE_a_micro_cap_product_far_above_its_cap_is_refused_even_under_a_billion(yf, helper):
    """SXTC-sized cap with a $932M product (810×) — the two-condition guard would have served this."""
    yf({"marketCap": 1_150_000, "bookValue": 90.0, "sharesOutstanding": 10_357_498})
    helper({})
    h = _headline("X")
    assert h["shareholder_equity"] is None and h["equity_note"].startswith("Refused")


def test_NEGATIVE_a_product_with_no_market_cap_to_judge_it_against_is_refused(yf, helper):
    yf({"bookValue": 10.0, "sharesOutstanding": 1_000_000})
    helper({})
    h = _headline("X")
    assert h["shareholder_equity"] is None
    assert "with no market capitalization to judge it against" in h["equity_note"]


def test_NEGATIVE_a_helper_crash_never_breaks_the_panel(yf, helper):
    yf(PLAIN_INFO)
    helper({("X", "quarterly"): RuntimeError("boom"), ("X", "annual"): RuntimeError("boom")})
    h = _headline("X")
    assert h["shareholder_equity"] == 10_000_000.0 and h["equity_source"] == "derived"
    assert h["equity_status"] == "unavailable" and "(error)" in h["equity_note"]


def test_NEGATIVE_no_inputs_at_all_serves_nothing(yf, helper):
    yf({"marketCap": 5_000_000})
    helper({})
    h = _headline("X")
    assert h["shareholder_equity"] is None and h["equity_source"] is None and h["equity_note"] is None
    assert h["equity_status"] == "none"


# ── pick_equity, pure ───────────────────────────────────────────────────────
def test_pick_equity_boundaries():
    NONE = {"status": "none"}
    # exactly 20× the cap is still served; above it is refused whatever the size.
    assert SA.pick_equity(NONE, 20 * 2e7, 2e7)["source"] == "derived"
    assert SA.pick_equity(NONE, 21 * 1e6, 1e6)["source"] is None
    assert SA.pick_equity(NONE, 21 * 2e7, 2e7)["source"] is None
    # no / zero / junk market cap → refused, never served.
    assert SA.pick_equity(NONE, 5e6, None)["source"] is None
    assert SA.pick_equity(NONE, 5e6, 0)["source"] is None
    assert SA.pick_equity(NONE, 5e6, "x")["source"] is None
    # a filed figure wins even when a derived one exists, and is never guarded.
    f = {"status": "filing", "value": 29.7e6, "as_of": "2026-03-31", "filed": "2026-07-01", "period": "FY 2026", "line": "parent"}
    assert SA.pick_equity(f, 9e9, 1.15e6)["value"] == 29.7e6
    # junk derived values are nothing.
    assert SA.pick_equity(NONE, float("nan"), 1e6)["value"] is None
    assert SA.pick_equity(NONE, "x", 1e6)["value"] is None
    assert SA.pick_equity(None, None, 1e6)["status"] is None


def test_pick_equity_unavailable_reason_words():
    u = {"status": "unavailable", "reason": "server_error"}
    note = SA.pick_equity(u, 5e6, 2e7)["note"]
    assert note.startswith("The filings provider did not answer (server_error) — this is Yahoo's")
    refused = SA.pick_equity(u, 5e9, 2e7)["note"]
    assert refused.startswith("Refused") and refused.endswith("The filings provider did not answer (server_error).")


# ── the caches and the chip ─────────────────────────────────────────────────
def test_schema_version_bumped_so_cached_v4_products_recompute():
    assert SA.SCHEMA_VERSION >= 5


def test_an_analysis_built_during_an_outage_is_kept_only_five_minutes():
    assert SA.cache_ttl_for({"fundamental": {"headline": {"equity_status": "unavailable"}}}) == SA.UNAVAILABLE_TTL_SEC == 300
    assert SA.cache_ttl_for({"fundamental": {"headline": {"equity_status": "filing"}}}) is None
    assert SA.cache_ttl_for({"fundamental": {"headline": {"equity_status": "none"}}}) is None
    assert SA.cache_ttl_for({}) is None


def test_card_enrichment_passes_the_source_through():
    blob = {"fundamental": {"headline": {"market_cap": 1, "shareholder_equity": 2, "equity_source": "filing",
                                         "equity_status": "filing", "equity_as_of": "2026-03-31", "equity_note": "n"}}}
    h = CE._extract_headline(blob)
    assert h == {"market_cap": 1, "shareholder_equity": 2, "equity_source": "filing", "equity_status": "filing",
                 "equity_as_of": "2026-03-31", "equity_note": "n"}


def test_NEGATIVE_a_chip_row_cached_before_the_filed_equity_keys_is_not_current():
    assert CE._headline_current({"headline": {"market_cap": 1, "shareholder_equity": 25692602388.84}}) is False
    assert CE._headline_current({"headline": {"market_cap": 1, "shareholder_equity": 2, "equity_source": "filing"}}) is True
    assert CE._headline_current({"headline": {"shareholder_equity": None, "equity_source": None}}) is True
    assert CE._headline_current(None) is False


def test_NEGATIVE_a_chip_built_during_an_outage_is_never_cached_for_a_day():
    assert CE._cacheable({"equity_status": "unavailable"}) is False
    assert CE._cacheable({"equity_status": "filing"}) is True
    assert CE._cacheable({"equity_status": "none"}) is True
    assert CE._cacheable({}) is True and CE._cacheable(None) is True


def test_cell_value_reads_both_shapes():
    assert SA._cell_value({"value": 3}) == 3.0 and SA._cell_value(4) == 4.0
    assert SA._cell_value(None) is None and SA._cell_value({"value": None}) is None
    assert SA._cell_value(True) is None and SA._cell_value("x") is None
