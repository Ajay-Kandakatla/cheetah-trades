"""vX -> v1 financials migration (2026-09-30).

Massive's vX financials endpoint answers `Sunset: 2026-10-09` and was already
in 410 brownouts. Four live modules moved to the v1 fundamentals family behind
ONE helper, `sepa.massive_fundamentals`. These tests are hermetic: every HTTP
call is a stub, and every v1 row below is copied from a live v1 response
(2026-09-30) or trimmed from one.

The NEGATIVES carry this file. The migration's real risks are all silent:
v1 ZERO-FILLS absent lines (a REIT's missing tax line becomes 0.0 and ROIC
quietly equals ROCE), v1 stamps a derived Q4 with a real filing date (the
dilution guard stops firing), and an outage that reads as "no filings".
"""
from __future__ import annotations

import pathlib
import re

import pytest

from sepa import massive_fundamentals as MF

KEY = "sk-test-DO-NOT-LEAK-123"


# ───────────────────────────────────────────── fixtures: live-shaped v1 rows
def inc(fy, fq, end, filed, *, timeframe="quarterly", cik="0001045810", **kw):
    row = {"cik": cik, "tickers": ["NVDA"], "timeframe": timeframe,
           "fiscal_year": fy, "fiscal_quarter": fq, "period_end": end,
           "filing_date": filed,
           # v1 zero-fills EVERY field — reproduce that, then overwrite.
           "revenue": 0.0, "diluted_earnings_per_share": 0.0,
           "basic_earnings_per_share": 0.0, "consolidated_net_income_loss": 0.0,
           "net_income_loss_attributable_common_shareholders": 0.0,
           "preferred_stock_dividends_declared": 0.0, "noncontrolling_interest": 0.0,
           "operating_income": 0.0, "gross_profit": 0.0,
           "income_before_income_taxes": 0.0, "income_taxes": 0.0,
           "diluted_shares_outstanding": 0.0, "basic_shares_outstanding": 0.0,
           # 2026-10-08 — the STANDARD template's keys, zero-filled as on live
           # MCD/NEE rows. Without them every row here would read as v1's
           # FINANCIAL template (both keys missing) and lose its revenue line.
           "interest_expense": 0.0, "research_development": 0.0,
           "cost_of_revenue": 0.0, "interest_income": 0.0,
           "depreciation_depletion_amortization": 0.0, "other_income_expense": 0.0}
    row.update(kw)
    return row


def fin_inc(fy, fq, end, filed, *, timeframe="quarterly", cik="0000070858", **kw):
    """A FINANCIAL-template v1 income row (banks/brokers/lenders): no
    `interest_expense`, no `research_development` key at all."""
    row = inc(fy, fq, end, filed, timeframe=timeframe, cik=cik)
    for k in ("interest_expense", "research_development", "interest_income",
              "depreciation_depletion_amortization"):
        row.pop(k, None)
    row.update(kw)
    return row


def bal(fy, fq, end, filed, *, timeframe="quarterly", cik="0001045810", **kw):
    row = {"cik": cik, "tickers": ["NVDA"], "timeframe": timeframe,
           "fiscal_year": fy, "fiscal_quarter": fq, "period_end": end,
           "filing_date": filed, "inventories": 0.0, "total_assets": 0.0,
           "total_liabilities": 0.0, "total_equity": 0.0,
           "total_equity_attributable_to_parent": 0.0,
           "total_current_assets": 0.0, "total_current_liabilities": 0.0,
           "long_term_debt_and_capital_lease_obligations": 0.0}
    row.update(kw)
    return row


def cfs(fy, fq, end, filed, *, timeframe="quarterly", cik="0001045810", **kw):
    row = {"cik": cik, "tickers": ["NVDA"], "timeframe": timeframe,
           "fiscal_year": fy, "fiscal_quarter": fq, "period_end": end,
           "filing_date": filed, "net_cash_from_operating_activities": 0.0,
           "change_in_cash_and_equivalents": 0.0,
           "purchase_of_property_plant_and_equipment": 0.0}
    row.update(kw)
    return row


# Live NVDA 2026-09-30, v1 quarterly (numbers verbatim).
NVDA_Q2_27 = inc(2027, 2, "2026-07-26", "2026-08-26", revenue=96221000000.0,
                 diluted_earnings_per_share=2.46, basic_earnings_per_share=2.47,
                 consolidated_net_income_loss=59688000000.0,
                 net_income_loss_attributable_common_shareholders=59688000000.0,
                 operating_income=63734000000.0, gross_profit=72142000000.0,
                 income_before_income_taxes=71507000000.0,
                 income_taxes=11819000000.0,
                 diluted_shares_outstanding=24285000000.0,
                 basic_shares_outstanding=24190000000.0)
NVDA_Q2_27_BAL = bal(2027, 2, "2026-07-26", "2026-08-26",
                     inventories=31575000000.0, total_assets=320272000000.0,
                     total_liabilities=91288000000.0, total_equity=228984000000.0,
                     total_equity_attributable_to_parent=228984000000.0,
                     total_current_assets=197412000000.0,
                     total_current_liabilities=43019000000.0,
                     long_term_debt_and_capital_lease_obligations=32366000000.0)
NVDA_Q2_27_CFS = cfs(2027, 2, "2026-07-26", "2026-08-26",
                     net_cash_from_operating_activities=24077000000.0,
                     change_in_cash_and_equivalents=9206000000.0)


class _Resp:
    def __init__(self, status, body=None, headers=None, raise_json=False):
        self.status_code = status
        self._body = body if body is not None else {"status": "OK", "results": []}
        self.headers = headers or {}
        self._raise = raise_json

    def json(self):
        if self._raise:
            raise ValueError("not json")
        return self._body


class _FakeRequests:
    """Routes by endpoint + timeframe; records every call; can script a
    sequence of responses per endpoint."""

    def __init__(self, tables=None, script=None):
        self.tables = tables or {}          # (endpoint, timeframe) -> rows
        self.by_ticker = {}                 # (endpoint, timeframe, ticker) -> rows
        self.script = script or {}          # endpoint -> [resp or exc, ...]
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        ep = url.rsplit("/", 1)[-1]
        self.calls.append({"url": url, "params": dict(params or {}),
                           "headers": dict(headers or {}), "ep": ep})
        seq = self.script.get(ep)
        if seq:
            nxt = seq.pop(0)
            if isinstance(nxt, Exception):
                raise nxt
            return nxt
        params = params or {}
        rows = self.tables.get((ep, params.get("timeframe")), [])
        tk = (ep, params.get("timeframe"), params.get("tickers"))
        if params.get("tickers") and tk in self.by_ticker:
            rows = self.by_ticker[tk]
        if params.get("cik"):
            rows = [r for r in rows if r.get("cik") == params["cik"]]
        if params.get("period_end.gte"):
            rows = [r for r in rows if r["period_end"] >= params["period_end.gte"]]
        rows = sorted(rows, key=lambda r: r["period_end"], reverse=True)
        return _Resp(200, {"status": "OK", "results": rows[: int(params.get("limit", 100))]})


@pytest.fixture
def fake(monkeypatch):
    import sys
    import massive_keys
    monkeypatch.setattr(massive_keys, "stocks_key", lambda: KEY)
    f = _FakeRequests()
    monkeypatch.setitem(sys.modules, "requests", f)
    sleeps = []
    monkeypatch.setattr(MF, "_sleep", lambda s: sleeps.append(s))
    f.sleeps = sleeps
    return f


# ═════════════════════════════════════════════ the helper: mapping
def test_a_v1_row_comes_back_in_the_vX_shape_every_module_reads(fake):
    fake.tables[("income-statements", "quarterly")] = [NVDA_Q2_27]
    fake.tables[("balance-sheets", "quarterly")] = [NVDA_Q2_27_BAL]
    fake.tables[("cash-flow-statements", "quarterly")] = [NVDA_Q2_27_CFS]
    [r] = MF.fetch_reports("nvda", timeframe="quarterly", limit=12, key=KEY)
    assert (r["fiscal_year"], r["fiscal_period"], r["end_date"], r["filing_date"]) == \
        (2027, "Q2", "2026-07-26", "2026-08-26")
    inc_ = r["financials"]["income_statement"]
    assert inc_["revenues"] == {"value": 96221000000.0}
    assert inc_["diluted_earnings_per_share"] == {"value": 2.46}
    assert inc_["net_income_loss"] == {"value": 59688000000.0}
    assert inc_["operating_income_loss"] == {"value": 63734000000.0}
    assert inc_["income_loss_from_continuing_operations_before_tax"] == {"value": 71507000000.0}
    assert inc_["income_tax_expense_benefit"] == {"value": 11819000000.0}
    assert inc_["diluted_average_shares"] == {"value": 24285000000.0}
    b = r["financials"]["balance_sheet"]
    assert b["inventory"] == {"value": 31575000000.0}
    assert b["assets"] == {"value": 320272000000.0}
    assert b["current_liabilities"] == {"value": 43019000000.0}
    assert b["long_term_debt"] == {"value": 32366000000.0}
    c = r["financials"]["cash_flow_statement"]
    assert c["net_cash_flow_from_operating_activities"] == {"value": 24077000000.0}
    assert c["net_cash_flow"] == {"value": 9206000000.0}
    assert r["source"] == "massive_v1"


def test_every_mapped_vX_key_has_a_v1_source_and_nothing_else_is_invented():
    """The map IS the migration's record. A vX key a live module reads that is
    missing from it would come back None forever, silently."""
    read_by_live_modules = {
        "income_statement": {"revenues", "diluted_earnings_per_share",
                             "basic_earnings_per_share", "net_income_loss",
                             "net_income_loss_attributable_to_parent",
                             "operating_income_loss", "gross_profit",
                             "income_loss_from_continuing_operations_before_tax",
                             "income_tax_expense_benefit", "diluted_average_shares",
                             "basic_average_shares"},
        "balance_sheet": {"inventory", "assets", "liabilities", "equity",
                          "equity_attributable_to_parent", "current_assets",
                          "current_liabilities", "long_term_debt"},
        "cash_flow_statement": {"net_cash_flow_from_operating_activities",
                                "net_cash_flow"},
    }
    for st, keys in read_by_live_modules.items():
        served = set(MF.FIELD_MAP[st]) | set(MF.DERIVED.get(st, {}))
        assert keys <= served, (st, keys - served)


def test_parent_net_income_is_common_plus_preferred_the_BX_identity(fake):
    """Live BX 2026-06-30: consolidated 2,356,066,000 with a −1,126,877,000
    minority adjustment; common 1,229,189,000 + preferred 0 = the parent line.
    Using the CONSOLIDATED line as 'parent' would put the minority's earnings
    over the parent's equity — the 2.5x ROE overstatement capital_returns
    already guards against."""
    fake.tables[("income-statements", "quarterly")] = [inc(
        2026, 2, "2026-06-30", "2026-08-01", cik="0001393818",
        consolidated_net_income_loss=2356066000.0,
        noncontrolling_interest=-1126877000.0,
        net_income_loss_attributable_common_shareholders=1229189000.0)]
    [r] = MF.fetch_reports("BX", timeframe="quarterly", limit=4,
                           statements=(MF.INCOME,), key=KEY)
    i = r["financials"]["income_statement"]
    assert i["net_income_loss_attributable_to_parent"] == {"value": 1229189000.0}
    assert i["net_income_loss"] == {"value": 2356066000.0}


def test_parent_net_income_adds_back_preferred_dividends_GOOGL(fake):
    fake.tables[("income-statements", "quarterly")] = [inc(
        2026, 2, "2026-06-30", "2026-07-25", cik="0001652044",
        consolidated_net_income_loss=112193000000.0,
        net_income_loss_attributable_common_shareholders=112107000000.0,
        preferred_stock_dividends_declared=86000000.0)]
    [r] = MF.fetch_reports("GOOGL", timeframe="quarterly", limit=4,
                           statements=(MF.INCOME,), key=KEY)
    assert r["financials"]["income_statement"][
        "net_income_loss_attributable_to_parent"] == {"value": 112193000000.0}


# ═════════════════════════════════════════════ NEGATIVE: v1 zero-fill
def test_NEGATIVE_a_v1_ZERO_is_ABSENT_never_a_zero_ARR_tax_and_inventory(fake):
    """MEASURED 2026-09-30: ARR (mortgage REIT) reports `income_taxes: 0.0` and
    `inventories: 0.0` on v1 where vX carried NO line. Passed through, the tax
    zero turns capital_returns' `no_tax_expense` refusal into a 0% rate and
    ROIC silently equals ROCE."""
    fake.tables[("income-statements", "quarterly")] = [inc(
        2026, 2, "2026-06-30", "2026-07-30", cik="0001428205",
        income_before_income_taxes=114816000.0, income_taxes=0.0,
        consolidated_net_income_loss=114816000.0)]
    fake.tables[("balance-sheets", "quarterly")] = [bal(
        2026, 2, "2026-06-30", "2026-07-30", cik="0001428205",
        inventories=0.0, total_assets=20e9)]
    [r] = MF.fetch_reports("ARR", timeframe="quarterly", limit=4,
                           statements=(MF.INCOME, MF.BALANCE), key=KEY)
    assert "income_tax_expense_benefit" not in r["financials"]["income_statement"]
    assert "inventory" not in r["financials"]["balance_sheet"]
    # Every other zero-filled line is omitted too — none reaches a consumer.
    for blob in r["financials"].values():
        for cell in blob.values():
            assert cell["value"] != 0.0


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "abc", None, True])
def test_NEGATIVE_non_numbers_are_absent(fake, bad):
    fake.tables[("income-statements", "quarterly")] = [inc(
        2026, 1, "2026-03-31", "2026-05-01", revenue=bad, diluted_earnings_per_share=1.5)]
    [r] = MF.fetch_reports("X", timeframe="quarterly", limit=4,
                           statements=(MF.INCOME,), key=KEY)
    assert "revenues" not in r["financials"]["income_statement"]
    assert r["financials"]["income_statement"]["diluted_earnings_per_share"] == {"value": 1.5}


def test_NEGATIVE_a_period_missing_one_statement_carries_no_zeros(fake):
    """Income filed, balance sheet absent for that period: the balance block
    is empty, never zero-filled."""
    fake.tables[("income-statements", "quarterly")] = [NVDA_Q2_27]
    fake.tables[("balance-sheets", "quarterly")] = []
    [r] = MF.fetch_reports("NVDA", timeframe="quarterly", limit=4,
                           statements=(MF.INCOME, MF.BALANCE), key=KEY)
    assert r["financials"]["balance_sheet"] == {}


# ═════════════════════════════════════════════ derived Q4 + restated dates
def test_a_QUARTERLY_Q4_is_marked_derived_exactly_as_vX_did(fake):
    """v1 stamps Q4 with the 10-K date, but no 10-Q exists for a fourth
    quarter. Live v1 NVDA FY2024 Q4 reads 47,336,000,000 diluted shares against
    ~24.9 B either side — the derived value still breaks."""
    fake.tables[("income-statements", "quarterly")] = [
        inc(2026, 4, "2026-01-25", "2026-02-25", diluted_shares_outstanding=24430000000.0),
        inc(2026, 3, "2025-10-26", "2025-11-19", diluted_shares_outstanding=24483000000.0)]
    q4, q3 = MF.fetch_reports("NVDA", timeframe="quarterly", limit=4,
                              statements=(MF.INCOME,), key=KEY)
    assert q4["fiscal_period"] == "Q4" and q4["filing_date"] is None
    assert q4["v1_filing_date"] == "2026-02-25"          # kept, never thrown away
    assert q3["filing_date"] == "2025-11-19"


def test_NEGATIVE_an_ANNUAL_row_keeps_its_filing_date(fake):
    """Only QUARTERLY Q4s are derived; the annual row IS the 10-K."""
    fake.tables[("income-statements", "annual")] = [inc(
        2025, 4, "2025-09-27", "2025-10-31", timeframe="annual",
        diluted_earnings_per_share=7.46)]
    [a] = MF.fetch_reports("AAPL", timeframe="annual", limit=4,
                           statements=(MF.INCOME,), key=KEY)
    assert a["fiscal_period"] == "FY"
    assert a["filing_date"] == "2025-10-31"


def test_RESTATED_filing_dates_never_reorder_periods(fake):
    """Live v1 NVDA: FY2026 Q2 carries 2026-08-26 (the NEXT year's 10-Q
    comparative) while the NEWER FY2026 Q3 carries 2025-11-19. Order is by the
    fiscal period, never by filing date."""
    fake.tables[("income-statements", "quarterly")] = [
        inc(2026, 2, "2025-07-27", "2026-08-26", revenue=46743000000.0),
        inc(2026, 3, "2025-10-26", "2025-11-19", revenue=57006000000.0),
        inc(2027, 1, "2026-04-26", "2026-05-20", revenue=81615000000.0)]
    rs = MF.fetch_reports("NVDA", timeframe="quarterly", limit=12,
                          statements=(MF.INCOME,), key=KEY)
    assert [(r["fiscal_year"], r["fiscal_period"]) for r in rs] == \
        [(2027, "Q1"), (2026, "Q3"), (2026, "Q2")]


def test_a_DUPLICATE_period_keeps_the_later_filing(fake):
    fake.tables[("income-statements", "quarterly")] = [
        inc(2026, 1, "2026-03-31", "2026-05-01", revenue=100.0),
        inc(2026, 1, "2026-03-31", "2026-08-01", revenue=105.0)]
    [r] = MF.fetch_reports("X", timeframe="quarterly", limit=4,
                           statements=(MF.INCOME,), key=KEY)
    assert r["financials"]["income_statement"]["revenues"] == {"value": 105.0}


def test_NEGATIVE_a_recycled_ticker_never_interleaves_two_companies(fake):
    """MEASURED 2026-09-30: `tickers=MU` answers annual rows from CIK 798287
    (a ~$500 M-revenue company) between Micron's. vX had the mirror defect —
    RKT's "10 years" included Rock-Tenn's 2010-2014 filings. Only the company
    that filed the NEWEST period is kept, and it keeps its FULL history."""
    fake.tables[("income-statements", "annual")] = [
        inc(2025, 4, "2025-08-28", "2025-10-03", timeframe="annual", cik="MICRON", revenue=37e9),
        inc(2018, 4, "2018-12-31", "2019-03-01", timeframe="annual", cik="OTHER", revenue=5e8),
        inc(2017, 4, "2017-12-31", "2018-03-01", timeframe="annual", cik="OTHER", revenue=4e8),
        inc(2018, 4, "2018-08-30", "2018-10-01", timeframe="annual", cik="MICRON", revenue=30e9),
        inc(2017, 4, "2017-08-31", "2017-10-01", timeframe="annual", cik="MICRON", revenue=20e9)]
    fake.tables[("balance-sheets", "annual")] = [
        bal(2025, 4, "2025-08-28", "2025-10-03", timeframe="annual", cik="MICRON", total_assets=1e11)]
    rs = MF.fetch_reports("MU", timeframe="annual", limit=3,
                          statements=(MF.INCOME, MF.BALANCE), key=KEY)
    assert [r["cik"] for r in rs] == ["MICRON"] * 3            # full limit, not 1
    assert [r["end_date"] for r in rs] == ["2025-08-28", "2018-08-30", "2017-08-31"]
    # The re-ask and every later statement go by CIK, not by ticker.
    assert fake.calls[1]["params"].get("cik") == "MICRON"
    assert fake.calls[2]["ep"] == "balance-sheets"
    assert fake.calls[2]["params"].get("cik") == "MICRON" and "tickers" not in fake.calls[2]["params"]


NVDA_Q1_27 = inc(2027, 1, "2026-04-26", "2026-05-20", revenue=81615000000.0,
                 diluted_earnings_per_share=2.39)


def test_a_single_company_with_a_FULL_answer_is_asked_ONCE_per_statement(fake):
    fake.tables[("income-statements", "quarterly")] = [NVDA_Q2_27, NVDA_Q1_27]
    fake.tables[("balance-sheets", "quarterly")] = [NVDA_Q2_27_BAL]
    MF.fetch_reports("NVDA", timeframe="quarterly", limit=1,
                     statements=(MF.INCOME, MF.BALANCE), key=KEY)
    assert [c["ep"] for c in fake.calls] == ["income-statements", "balance-sheets"]
    assert fake.calls[0]["params"]["tickers"] == "NVDA"
    assert fake.calls[1]["params"]["cik"] == "0001045810"
    # The balance sheet is asked from the spine's oldest period on, with 2x the
    # limit, so stray comparative rows cannot crowd a real period out.
    assert fake.calls[0]["params"]["limit"] == 2
    assert fake.calls[1]["params"]["limit"] == 2
    assert fake.calls[1]["params"]["period_end.gte"] == "2026-06-11"   # 07-26 − 45 d


def test_a_RENAMED_ticker_is_re_asked_by_CIK_for_its_full_history(fake):
    """Critic 2026-09-30: `tickers=SGI` answers ONE annual income row while its
    CIK holds twelve; the balance sheet (asked by CIK) came back full, so the
    reports were income-less and A was None although v1 has the years."""
    full = [inc(2025 - i, 4, f"{2025 - i}-06-30", f"{2025 - i}-08-20", timeframe="annual",
                cik="SOMNIGROUP", diluted_earnings_per_share=1.0 + i) for i in range(6)]
    fake.tables[("income-statements", "annual")] = full
    fake.by_ticker[("income-statements", "annual", "SGI")] = full[:1]
    rs = MF.fetch_reports("SGI", timeframe="annual", limit=4,
                          statements=(MF.INCOME,), key=KEY)
    assert [r["fiscal_year"] for r in rs] == [2025, 2024, 2023, 2022]
    assert fake.calls[1]["params"].get("cik") == "SOMNIGROUP"


def test_NEGATIVE_a_short_history_that_IS_the_full_history_keeps_it(fake):
    """A recent IPO answers short by ticker AND by CIK — nothing is invented."""
    fake.tables[("income-statements", "quarterly")] = [NVDA_Q2_27]
    rs = MF.fetch_reports("NTSK", timeframe="quarterly", limit=12,
                          statements=(MF.INCOME,), key=KEY)
    assert len(rs) == 1 and len(fake.calls) == 2


def test_newest_first_and_truncated_to_limit(fake):
    fake.tables[("income-statements", "quarterly")] = [
        inc(2025, q, f"2025-0{q * 2}-28", "2025-09-01", revenue=float(q)) for q in (1, 2, 3)]
    rs = MF.fetch_reports("X", timeframe="quarterly", limit=2,
                          statements=(MF.INCOME,), key=KEY)
    assert [r["fiscal_period"] for r in rs] == ["Q3", "Q2"]
    assert fake.calls[0]["params"]["sort"] == "period_end.desc"


# ═════════════════════════════════════════════ fail loudly
def test_NEGATIVE_EMPTY_is_no_filings_not_an_error(fake):
    """A delisted name (v1 carries listed names only), an ETF, a trust."""
    assert MF.fetch_reports("ZZZZQ", timeframe="quarterly", limit=12, key=KEY) == []


def test_NEGATIVE_410_is_raised_at_ONCE_never_retried(fake):
    fake.script["income-statements"] = [_Resp(410, {"status": "ERROR"})]
    with pytest.raises(MF.FinancialsUnavailable) as ei:
        MF.fetch_reports("NVDA", timeframe="quarterly", limit=12, key=KEY)
    assert ei.value.reason == "endpoint_gone" and ei.value.status == 410
    assert len(fake.calls) == 1 and fake.sleeps == []


def test_429_is_RETRIED_honouring_Retry_After_then_succeeds(fake):
    fake.tables[("income-statements", "quarterly")] = [NVDA_Q2_27, NVDA_Q1_27]
    fake.script["income-statements"] = [_Resp(429, headers={"Retry-After": "3"})]
    rs = MF.fetch_reports("NVDA", timeframe="quarterly", limit=1,
                          statements=(MF.INCOME,), key=KEY)
    assert len(rs) == 1
    assert len(fake.calls) == 2 and fake.sleeps == [3.0]


def test_NEGATIVE_a_huge_Retry_After_is_capped(fake):
    fake.tables[("income-statements", "quarterly")] = [NVDA_Q2_27]
    fake.script["income-statements"] = [_Resp(429, headers={"Retry-After": "3600"})]
    MF.fetch_reports("NVDA", timeframe="quarterly", limit=12,
                     statements=(MF.INCOME,), key=KEY)
    assert fake.sleeps == [MF.MAX_RETRY_AFTER_SEC]


def test_NEGATIVE_429_that_never_clears_RAISES_rate_limited_after_MAX_ATTEMPTS(fake):
    fake.script["income-statements"] = [_Resp(429) for _ in range(10)]
    with pytest.raises(MF.FinancialsUnavailable) as ei:
        MF.fetch_reports("NVDA", timeframe="quarterly", limit=12, key=KEY)
    assert ei.value.reason == "rate_limited"
    assert len(fake.calls) == MF.MAX_ATTEMPTS
    assert fake.sleeps == [1.0, 2.0]                  # backoff doubled


def test_NEGATIVE_5xx_retries_then_raises_server_error(fake):
    fake.script["income-statements"] = [_Resp(503), _Resp(502), _Resp(500)]
    with pytest.raises(MF.FinancialsUnavailable) as ei:
        MF.fetch_reports("NVDA", timeframe="quarterly", limit=12, key=KEY)
    assert ei.value.reason == "server_error"
    assert len(fake.calls) == MF.MAX_ATTEMPTS


@pytest.mark.parametrize("status", [401, 403])
def test_NEGATIVE_auth_failure_is_not_retried(fake, status):
    fake.script["income-statements"] = [_Resp(status)]
    with pytest.raises(MF.FinancialsUnavailable) as ei:
        MF.fetch_reports("NVDA", timeframe="quarterly", limit=12, key=KEY)
    assert ei.value.reason == "not_authorized" and len(fake.calls) == 1


def test_NEGATIVE_other_4xx_is_named(fake):
    fake.script["income-statements"] = [_Resp(404)]
    with pytest.raises(MF.FinancialsUnavailable) as ei:
        MF.fetch_reports("NVDA", timeframe="quarterly", limit=12, key=KEY)
    assert ei.value.reason == "http_404"


def test_NEGATIVE_transport_error_retries_then_raises_WITHOUT_the_key(fake):
    """This repo has leaked the Massive key five times through URL-bearing
    exception text. The key rides in a header now, never a query param."""
    boom = ConnectionError(f"https://api.massive.com/x?apiKey={KEY}")
    fake.script["income-statements"] = [boom, boom, boom]
    with pytest.raises(MF.FinancialsUnavailable) as ei:
        MF.fetch_reports("NVDA", timeframe="quarterly", limit=12, key=KEY)
    assert ei.value.reason == "transport_error"
    assert KEY not in str(ei.value) and ei.value.__cause__ is None
    assert len(fake.calls) == MF.MAX_ATTEMPTS


def test_the_key_rides_in_the_header_never_the_url(fake):
    MF.fetch_reports("NVDA", timeframe="quarterly", limit=12, key=KEY)
    for c in fake.calls:
        assert c["headers"]["Authorization"] == f"Bearer {KEY}"
        assert "apiKey" not in c["params"] and KEY not in c["url"]


@pytest.mark.parametrize("resp", [_Resp(200, raise_json=True),
                                  _Resp(200, {"status": "OK", "results": "nope"}),
                                  _Resp(200, ["not", "a", "dict"])])
def test_NEGATIVE_a_malformed_body_is_bad_payload(fake, resp):
    fake.script["income-statements"] = [resp]
    with pytest.raises(MF.FinancialsUnavailable) as ei:
        MF.fetch_reports("NVDA", timeframe="quarterly", limit=12, key=KEY)
    assert ei.value.reason == "bad_payload"


def test_NEGATIVE_no_key_is_an_error_not_an_empty_list(fake, monkeypatch):
    import massive_keys
    monkeypatch.setattr(massive_keys, "stocks_key", lambda: "")
    with pytest.raises(MF.FinancialsUnavailable) as ei:
        MF.fetch_reports("NVDA", timeframe="quarterly", limit=12)
    assert ei.value.reason == "no_key" and fake.calls == []


def test_NEGATIVE_bad_arguments_raise_before_any_call(fake):
    with pytest.raises(ValueError):
        MF.fetch_reports("NVDA", timeframe="ttm", limit=4, key=KEY)
    with pytest.raises(ValueError):
        MF.fetch_reports("NVDA", timeframe="annual", limit=4,
                         statements=("ratios",), key=KEY)
    assert fake.calls == []


# ═════════════════════════════════════════════ canslim (C/A EPS)
def _nvda_like_quarters():
    """Five quarters so slot 0 vs slot 4 is the year-ago quarter."""
    return [inc(2027, 2, "2026-07-26", "2026-08-26", diluted_earnings_per_share=2.46,
                revenue=96221000000.0, consolidated_net_income_loss=59.0),
            inc(2027, 1, "2026-04-26", "2026-05-20", diluted_earnings_per_share=2.39,
                revenue=81615000000.0, consolidated_net_income_loss=58.0),
            inc(2026, 4, "2026-01-25", "2026-02-25", diluted_earnings_per_share=1.76,
                revenue=68127000000.0, consolidated_net_income_loss=43.0),
            inc(2026, 3, "2025-10-26", "2025-11-19", diluted_earnings_per_share=1.30,
                revenue=57006000000.0, consolidated_net_income_loss=31.0),
            inc(2026, 2, "2025-07-27", "2026-08-26", diluted_earnings_per_share=1.08,
                revenue=46743000000.0, consolidated_net_income_loss=26.0)]


@pytest.fixture
def cs(monkeypatch, fake):
    from sepa import canslim as CS
    monkeypatch.setattr(CS, "stocks_key", lambda: KEY)
    monkeypatch.setattr(CS, "_massive_financials_disabled", False)
    monkeypatch.setattr(CS, "_massive_last_error", {})
    return CS


def test_canslim_reads_C_from_v1_end_to_end(cs, fake):
    fake.tables[("income-statements", "quarterly")] = _nvda_like_quarters()
    fake.tables[("balance-sheets", "quarterly")] = [
        bal(2027, 2, "2026-07-26", "2026-08-26", inventories=31575000000.0)]
    m = cs._fetch_massive_financials("NVDA")
    assert m["q_eps_growth_pct"] == round((2.46 - 1.08) / 1.08 * 100, 2)
    assert m["rev_growth_q_pct"] == round((96221 - 46743) / 46743 * 100, 2)
    assert m["q_period_series"] == [8109, 8108, 8107, 8106, 8105]   # FY*4 + (Q-1)
    assert m["inv_q_series"][0] == 31575000000.0
    # Only the statements it needs — and nothing on vX. (The quarterly income
    # answer is short of 12, so it is re-asked once by CIK.)
    eps = {(c["ep"], c["params"]["timeframe"]) for c in fake.calls}
    assert eps == {("balance-sheets", "quarterly"), ("income-statements", "annual"),
                   ("income-statements", "quarterly")}
    assert not any("vX" in c["url"] for c in fake.calls)


def test_canslim_A_uses_SPLIT_ADJUSTED_annual_EPS(cs, fake):
    """v1 restates history onto today's share basis: NVDA FY2024 EPS reads
    ~1.19 on v1 where vX served the pre-10:1-split 11.93. A mixed basis made
    the 3-year average compare 1.19 against 11.93 — a fake −90%."""
    fake.tables[("income-statements", "annual")] = [
        inc(2026, 4, "2026-01-25", "2026-02-25", timeframe="annual", diluted_earnings_per_share=4.90),
        inc(2025, 4, "2025-01-26", "2026-02-25", timeframe="annual", diluted_earnings_per_share=2.94),
        inc(2024, 4, "2024-01-28", "2026-02-25", timeframe="annual", diluted_earnings_per_share=1.19),
        inc(2023, 4, "2023-01-29", "2025-02-26", timeframe="annual", diluted_earnings_per_share=0.17)]
    m = cs._fetch_massive_financials("NVDA")
    g = [(4.90 - 2.94) / 2.94, (2.94 - 1.19) / 1.19, (1.19 - 0.17) / 0.17]
    assert m["y_eps_growth_pct"] == round(sum(x * 100 for x in g) / 3, 2)


def test_NEGATIVE_canslim_zero_inventory_is_unknown_not_zero(cs, fake):
    fake.tables[("income-statements", "quarterly")] = _nvda_like_quarters()
    fake.tables[("balance-sheets", "quarterly")] = [
        bal(2027, 2, "2026-07-26", "2026-08-26", inventories=0.0)]
    m = cs._fetch_massive_financials("CRWD")
    assert m["inv_q_series"][0] is None


def test_NEGATIVE_canslim_provider_error_is_None_AND_says_why(cs, fake, monkeypatch):
    fake.script["income-statements"] = [_Resp(429) for _ in range(10)]
    assert cs._fetch_massive_financials("NVDA") is None
    assert cs._massive_last_error["NVDA"] == "rate_limited"
    assert cs._massive_financials_disabled is False   # 429 is "not now"

    # The hybrid fallback carries the reason onto the payload.
    monkeypatch.setattr(cs, "_from_yfinance", lambda s: {"_source": "yfinance"})
    fake.script["income-statements"] = [_Resp(503) for _ in range(10)]
    out = cs._from_hybrid("NVDA")
    assert out["_source"] == "yfinance" and out["_massive_error"] == "server_error"


def test_NEGATIVE_canslim_success_clears_the_error_and_adds_no_key(cs, fake, monkeypatch):
    cs._massive_last_error["NVDA"] = "rate_limited"
    fake.tables[("income-statements", "quarterly")] = _nvda_like_quarters()
    assert cs._fetch_massive_financials("NVDA") is not None
    assert "NVDA" not in cs._massive_last_error
    monkeypatch.setattr(cs, "_from_yfinance", lambda s: {"_source": "yfinance"})
    fake.tables[("income-statements", "quarterly")] = []
    out = cs._from_hybrid("EMPTY")          # no filings: a fallback, NOT an outage
    assert "_massive_error" not in out


def test_NEGATIVE_canslim_401_disables_the_run(cs, fake):
    fake.script["income-statements"] = [_Resp(401)]
    assert cs._fetch_massive_financials("NVDA") is None
    assert cs._massive_financials_disabled is True
    n = len(fake.calls)
    assert cs._fetch_massive_financials("AAPL") is None
    assert len(fake.calls) == n                        # not hammered again


# ═════════════════════════════════════════════ longterm (Fundamentals tab)
def test_longterm_annual_rows_map_every_statement(fake):
    from sepa import longterm as LT
    fake.tables[("income-statements", "annual")] = [inc(
        2025, 4, "2025-09-27", "2025-10-31", timeframe="annual", revenue=416e9,
        operating_income=133e9, consolidated_net_income_loss=112e9,
        net_income_loss_attributable_common_shareholders=112e9,
        diluted_earnings_per_share=7.46)]
    fake.tables[("balance-sheets", "annual")] = [bal(
        2025, 4, "2025-09-27", "2025-10-31", timeframe="annual",
        total_assets=359e9, total_liabilities=285e9,
        total_equity_attributable_to_parent=74e9, total_current_liabilities=165e9,
        long_term_debt_and_capital_lease_obligations=78e9)]
    fake.tables[("cash-flow-statements", "annual")] = [cfs(
        2025, 4, "2025-09-27", "2025-10-31", timeframe="annual",
        net_cash_from_operating_activities=111e9, change_in_cash_and_equivalents=-2e9)]
    [r] = LT.annual_financials("AAPL")
    assert (r["fiscal_year"], r["revenues"], r["operating_income"], r["net_income"],
            r["eps_diluted"], r["assets"], r["equity"], r["current_liabilities"],
            r["long_term_debt"], r["ocf"], r["net_cash_flow"], r["filing_date"]) == \
        (2025, 416e9, 133e9, 112e9, 7.46, 359e9, 74e9, 165e9, 78e9, 111e9, -2e9, "2025-10-31")


def test_NEGATIVE_longterm_outage_is_NOT_no_filings(fake):
    from sepa import longterm as LT
    fake.script["income-statements"] = [_Resp(429) for _ in range(10)]
    m = LT.metrics("AAPL")
    assert m["ok"] is False and m["error"] == "rate_limited"
    assert "outage" in m["reason"] and "no filed annual financials" not in m["reason"]


def test_NEGATIVE_longterm_empty_still_says_no_filings(fake):
    from sepa import longterm as LT
    m = LT.metrics("SPY")
    assert m["ok"] is False and m["reason"] == "no filed annual financials"
    assert "error" not in m


# ═════════════════════════════════════════════ board_metrics + capital_returns
@pytest.fixture
def bm(monkeypatch, fake):
    from sepa import board_metrics as BM
    import massive_keys
    monkeypatch.setattr(massive_keys, "stocks_key", lambda: KEY)
    monkeypatch.setattr(BM, "balance_metrics", lambda s: {"balance_meaningful": True})
    monkeypatch.setattr(BM, "_live_shares", lambda s, db=None: None)
    monkeypatch.setattr(BM, "_capex_ttm", lambda s: (None, None))
    return BM


def _eight_nvda_quarters():
    """Live v1 NVDA share counts, incl. the derived FY2024-style Q4 garbage."""
    spec = [(2027, 2, "2026-07-26", "2026-08-26", 24285e6),
            (2027, 1, "2026-04-26", "2026-05-20", 24391e6),
            (2026, 4, "2026-01-25", "2026-02-25", 47336e6),   # derived — garbage
            (2026, 3, "2025-10-26", "2025-11-19", 24483e6),
            (2026, 2, "2025-07-27", "2026-08-26", 24532e6),
            (2026, 1, "2025-04-27", "2026-05-20", 24611e6)]
    return [inc(fy, fq, end, filed, diluted_shares_outstanding=sh, revenue=1e9,
                operating_income=5e8, consolidated_net_income_loss=4e8,
                net_income_loss_attributable_common_shareholders=4e8,
                income_before_income_taxes=5e8, income_taxes=1e8)
            for fy, fq, end, filed, sh in spec]


def test_board_dilution_on_v1_drops_the_DERIVED_Q4(bm, fake):
    fake.tables[("income-statements", "quarterly")] = _eight_nvda_quarters()
    row = bm.for_symbol("NVDA")
    d = row["shares_yoy"]
    assert d["pct"] == round(100 * (24285e6 - 24532e6) / 24532e6, 1)
    assert d["period"] == "Q2 2027" and d["prior_period"] == "Q2 2026"
    assert "financials_error" not in row
    # The garbage Q4 (1.9x its neighbours) never reached the basis check.
    assert 47336e6 not in [q["shares"] for q in bm._reported_quarters(
        MF.fetch_reports("NVDA", timeframe="quarterly", limit=12, key=KEY))]


def test_NEGATIVE_board_outage_is_named_on_BOTH_readers(bm, fake):
    fake.script["income-statements"] = [_Resp(503) for _ in range(10)]
    row = bm.for_symbol("NVDA")
    assert row["financials_error"] == "server_error"
    assert row["shares_yoy"]["pct"] is None
    assert row["shares_yoy"]["reason"] == bm.FINANCIALS_UNAVAILABLE
    reasons = row["capital_returns"]["reasons"]
    assert set(reasons.values()) == {"financials_unavailable"}
    assert row["capital_returns"]["roce_pct"] is None


def test_NEGATIVE_board_empty_is_still_no_quarters_not_an_outage(bm, fake):
    row = bm.for_symbol("SPY")
    assert "financials_error" not in row
    assert set(row["capital_returns"]["reasons"].values()) == {"no_quarters"}


def test_NEGATIVE_REIT_zero_tax_keeps_the_no_tax_expense_refusal(bm, fake):
    """THE silent failure v1 would have shipped: ARR's `income_taxes: 0.0`
    passed through makes the rate 0% and ROIC == ROCE."""
    qs = _eight_nvda_quarters()
    for q in qs:
        q["income_taxes"] = 0.0
    fake.tables[("income-statements", "quarterly")] = qs
    fake.tables[("balance-sheets", "quarterly")] = [
        bal(q["fiscal_year"], q["fiscal_quarter"], q["period_end"], q["filing_date"],
            total_assets=10e9, total_current_liabilities=2e9, total_equity=5e9,
            total_equity_attributable_to_parent=5e9, total_liabilities=5e9)
        for q in qs]
    cr = bm.for_symbol("ARR")["capital_returns"]
    assert cr["roic_pct"] is None
    assert cr["reasons"]["roic_pct"] == "no_tax_expense"
    assert cr["roce_pct"] is not None          # the rest still computes


class _Coll:
    def __init__(self, docs=None):
        self.docs = dict(docs or {})
        self.queries = []

    def find(self, q, proj=None):
        self.queries.append(q)
        return []                                 # nothing fresh

    def find_one(self, q, proj=None):
        d = self.docs.get(q["_id"])
        if d is None:
            return None
        if "financials_error" in q and "financials_error" in d:
            return None
        return d

    def replace_one(self, q, doc, upsert=False):
        self.docs[q["_id"]] = doc


def test_NEGATIVE_an_outage_row_never_overwrites_a_good_row(bm, fake):
    good = {"_id": "NVDA", "shares_yoy": {"pct": -1.0}, "capital_returns": {}}
    coll = _Coll({"NVDA": good})
    fake.script["income-statements"] = [_Resp(410)] * 2
    out = bm.warm(["NVDA", "NEWCO"], db={bm.COLL: coll}, max_workers=1)
    assert coll.docs["NVDA"] is good                       # kept
    assert coll.docs["NEWCO"]["financials_error"] == "endpoint_gone"  # says why
    assert out["provider_errors"] == 2 and out["kept_prior"] == 1
    # ...and a doc written during an outage is never "fresh".
    assert coll.queries[0]["financials_error"] == {"$exists": False}


def test_capital_returns_provider_error_refuses_with_a_KNOWN_reason():
    from sepa import capital_returns as CR
    out = CR.compute([], provider_error="rate_limited")
    assert "financials_unavailable" in CR.REASONS
    assert set(out["reasons"].values()) == {"financials_unavailable"}
    assert out["roce_pct"] is None and out["period"] is None


# ═════════════════════════════════════════════ source guard
BACKEND = pathlib.Path(__file__).resolve().parents[1]


def _live_modules():
    for p in BACKEND.rglob("*.py"):
        rel = p.relative_to(BACKEND).as_posix()
        if rel.startswith(("scripts/", "tests/", ".venv/")) or "/.venv/" in rel:
            continue
        yield rel, p.read_text(errors="replace")


def test_SOURCE_GUARD_no_live_module_references_the_vX_financials_endpoint():
    """vX financials sunset 2026-10-09. Study scripts under scripts/ may keep
    it (a snapshot of the whole feed was saved 2026-09-30); nothing live may."""
    offenders = [rel for rel, src in _live_modules()
                 if re.search(r"vX/reference/financials|reference/financials", src)]
    assert offenders == [], offenders


def test_SOURCE_GUARD_one_engine_only_the_helper_builds_v1_financials_urls():
    offenders = [rel for rel, src in _live_modules()
                 if "financials/v1" in src and rel != "sepa/massive_fundamentals.py"]
    assert offenders == [], offenders


def test_NEGATIVE_longterm_score_for_carries_the_outage_code_to_the_tab(fake, monkeypatch):
    """The tab headlines `error` as an outage; without it an outage would be
    headlined "No filed annual financials" (frontend LongTermFundamentals)."""
    from sepa import longterm as LT
    monkeypatch.setattr(LT, "stored", lambda db=None: {})
    monkeypatch.setattr(LT, "institutional", lambda s: {})
    fake.script["income-statements"] = [_Resp(410)]
    out = LT.score_for("AAPL")
    assert out["ok"] is False and out["error"] == "endpoint_gone"
    fake.script["income-statements"] = []
    assert LT.score_for("SPY")["error"] is None          # empty: not an outage


# ═════════════════════════════════════════════ critic 2026-09-30: the period join
def _pep_rows():
    """PEP-shaped: the balance sheet carries a prior-year-end comparative
    LABELLED Q1 at the year-end date."""
    income = [inc(2025, 4, "2025-12-27", "2026-02-03", revenue=29e9, diluted_earnings_per_share=1.85),
              inc(2025, 3, "2025-09-06", "2025-10-09", revenue=23e9, diluted_earnings_per_share=1.90),
              inc(2025, 2, "2025-06-14", "2025-07-17", revenue=22e9, diluted_earnings_per_share=0.92),
              inc(2025, 1, "2025-03-22", "2025-04-24", revenue=17e9, diluted_earnings_per_share=1.33)]
    balance = [bal(2025, 4, "2025-12-27", "2026-02-03", inventories=444.0),
               bal(2025, 1, "2025-12-27", "2026-04-30", inventories=999.0),   # THE STRAY
               bal(2025, 3, "2025-09-06", "2025-10-09", inventories=333.0),
               bal(2025, 2, "2025-06-14", "2025-07-17", inventories=222.0),
               bal(2025, 1, "2025-03-22", "2025-04-24", inventories=111.0)]
    return income, balance


def test_NEGATIVE_a_STRAY_balance_row_never_becomes_a_period_PEP(fake):
    income, balance = _pep_rows()
    fake.tables[("income-statements", "quarterly")] = income
    fake.tables[("balance-sheets", "quarterly")] = balance
    rs = MF.fetch_reports("PEP", timeframe="quarterly", limit=4,
                          statements=(MF.INCOME, MF.BALANCE), key=KEY)
    got = [(r["fiscal_period"], r["end_date"],
            r["financials"]["balance_sheet"]["inventory"]["value"],
            r["financials"]["income_statement"]["diluted_earnings_per_share"]["value"]) for r in rs]
    assert got == [("Q4", "2025-12-27", 444.0, 1.85), ("Q3", "2025-09-06", 333.0, 1.90),
                   ("Q2", "2025-06-14", 222.0, 0.92), ("Q1", "2025-03-22", 111.0, 1.33)]


def test_NEGATIVE_PEP_through_canslim_alignment_keeps_EPS_in_the_Q1_slot(cs, fake):
    """The blocker, end to end: before the fix the stray sorted ahead of the
    real Q1, `qoq._densify` kept it, and Q1's EPS read None — C refused."""
    income, balance = _pep_rows()
    fake.tables[("income-statements", "quarterly")] = income
    fake.tables[("balance-sheets", "quarterly")] = balance
    fake.tables[("income-statements", "annual")] = [inc(
        2025, 4, "2025-12-27", "2026-02-03", timeframe="annual",
        diluted_earnings_per_share=6.00)]
    m = cs._fetch_massive_financials("PEP")
    assert m["eps_q_series"] == pytest.approx([1.85, 1.90, 0.92, 1.33])
    assert m["inv_q_series"] == [444.0, 333.0, 222.0, 111.0]


def test_NEGATIVE_a_stray_in_the_SPINE_keeps_the_row_whose_date_is_its_own(fake):
    income, _ = _pep_rows()
    stray = inc(2025, 1, "2025-12-27", "2026-04-30", revenue=1.0, diluted_earnings_per_share=9.99)
    fake.tables[("income-statements", "quarterly")] = income + [stray]
    rs = MF.fetch_reports("PEP", timeframe="quarterly", limit=4,
                          statements=(MF.INCOME,), key=KEY)
    q1 = [r for r in rs if r["fiscal_period"] == "Q1"]
    assert len(rs) == 4 and len(q1) == 1 and q1[0]["end_date"] == "2025-03-22"


def test_NEGATIVE_an_UNRESOLVABLE_shared_date_is_a_hole_not_a_guess(fake):
    """Two labels on one date, each with no other row, and BOTH in order with
    their neighbours cannot be told apart — neither is kept."""
    fake.tables[("income-statements", "quarterly")] = [
        inc(2025, 2, "2025-06-30", "2025-08-01", revenue=2.0),
        inc(2025, 3, "2025-06-30", "2025-08-01", revenue=3.0),
        inc(2025, 1, "2025-03-31", "2025-05-01", revenue=1.0)]
    rs = MF.fetch_reports("X", timeframe="quarterly", limit=4,
                          statements=(MF.INCOME,), key=KEY)
    assert [r["fiscal_period"] for r in rs] == ["Q1"]


def test_an_out_of_order_label_on_a_shared_date_is_dropped(fake):
    """PEP's stray at the year-end with only its own date: Q1 at 12-27 is out
    of order against Q2 (06-14) and Q3 (09-06), so the Q4 keeps the date."""
    income, _ = _pep_rows()
    rows = [r for r in income if r["fiscal_quarter"] != 1]
    rows.append(inc(2025, 1, "2025-12-27", "2026-04-30", revenue=1.0))
    fake.tables[("income-statements", "quarterly")] = rows
    rs = MF.fetch_reports("PEP", timeframe="quarterly", limit=4,
                          statements=(MF.INCOME,), key=KEY)
    assert [(r["fiscal_period"], r["end_date"]) for r in rs] == \
        [("Q4", "2025-12-27"), ("Q3", "2025-09-06"), ("Q2", "2025-06-14")]


def test_an_ANNUAL_balance_sheet_a_few_days_off_still_joins_CARR(fake):
    """CARR FY2021: balance 2022-01-04 vs income 2021-12-31 — one year, not two."""
    fake.tables[("income-statements", "annual")] = [
        inc(2021, 4, "2021-12-31", "2022-02-08", timeframe="annual", revenue=20.6e9)]
    fake.tables[("balance-sheets", "annual")] = [
        bal(2021, 4, "2022-01-04", "2022-02-08", timeframe="annual", total_assets=26e9)]
    rs = MF.fetch_reports("CARR", timeframe="annual", limit=4,
                          statements=(MF.INCOME, MF.BALANCE), key=KEY)
    assert len(rs) == 1
    assert rs[0]["end_date"] == "2021-12-31"
    assert rs[0]["financials"]["balance_sheet"]["assets"] == {"value": 26e9}


def test_NEGATIVE_a_balance_row_near_NO_period_attaches_to_nothing(fake):
    fake.tables[("income-statements", "quarterly")] = [NVDA_Q2_27]
    fake.tables[("balance-sheets", "quarterly")] = [
        bal(2027, 2, "2026-10-26", "2026-11-20", inventories=5.0)]      # 92 days off
    [r] = MF.fetch_reports("NVDA", timeframe="quarterly", limit=1,
                           statements=(MF.INCOME, MF.BALANCE), key=KEY)
    assert r["financials"]["balance_sheet"] == {}


# ═════════════════════════════════════════════ critic 2026-09-30: parent NI
@pytest.mark.parametrize("cons,nci,common,pref,parent", [
    (445e6, 0.0, 300e6, 86e6, 445e6),     # TDG-shaped: common+pref would say 386
    (50e6, -3e6, -38e6, 126e6, 47e6),     # TSN-shaped: common+pref would say 88
    (2356066000.0, -1126877000.0, 1229189000.0, 0.0, 1229189000.0),   # BX
])
def test_parent_net_income_is_consolidated_plus_the_minority_adjustment(fake, cons, nci, common, pref, parent):
    fake.tables[("income-statements", "quarterly")] = [inc(
        2026, 2, "2026-06-30", "2026-08-01", consolidated_net_income_loss=cons,
        noncontrolling_interest=nci,
        net_income_loss_attributable_common_shareholders=common,
        preferred_stock_dividends_declared=pref)]
    [r] = MF.fetch_reports("X", timeframe="quarterly", limit=1,
                           statements=(MF.INCOME,), key=KEY)
    assert r["financials"]["income_statement"]["net_income_loss_attributable_to_parent"] \
        == {"value": parent}


# ═════════════════════════════════════════════ critic 2026-09-30: Q4 EPS
def _q(fy, fp, end, eps):
    return {"fiscal_year": fy, "fiscal_period": fp, "end_date": end, "timeframe": "quarterly",
            "financials": {"income_statement": {} if eps is None else
                           {"diluted_earnings_per_share": {"value": eps},
                            "basic_earnings_per_share": {"value": eps}}}}


def _a(fy, end, eps):
    return {"fiscal_year": fy, "fiscal_period": "FY", "end_date": end,
            "financials": {"income_statement": {"diluted_earnings_per_share": {"value": eps},
                                                "basic_earnings_per_share": {"value": eps}}}}


def test_Q4_EPS_is_annual_minus_three_quarters_NFLX(fake):
    """v1 serves NFLX FY2024 Q4 at 0.11 (derived NI over the broken derived
    share count); vX served annual − Q1..Q3 ≈ 0.43, and C was built on that."""
    q = [_q(2024, "Q4", "2024-12-31", 0.11), _q(2024, "Q3", "2024-09-30", 0.54),
         _q(2024, "Q2", "2024-06-30", 0.49), _q(2024, "Q1", "2024-03-31", 0.53)]
    MF.derive_q4_eps(q, [_a(2024, "2024-12-31", 1.99)])
    v = q[0]["financials"]["income_statement"]["diluted_earnings_per_share"]["value"]
    assert v == pytest.approx(1.99 - 0.54 - 0.49 - 0.53)
    assert q[0]["q4_eps_derived"] is True
    assert q[1]["financials"]["income_statement"]["diluted_earnings_per_share"]["value"] == 0.54


@pytest.mark.parametrize("case", ["no_annual", "missing_q2", "annual_ends_elsewhere"])
def test_NEGATIVE_an_underivable_Q4_EPS_is_ABSENT_never_v1s_value(fake, case):
    q = [_q(2024, "Q4", "2024-12-31", 0.11), _q(2024, "Q3", "2024-09-30", 0.54),
         _q(2024, "Q2", "2024-06-30", None if case == "missing_q2" else 0.49),
         _q(2024, "Q1", "2024-03-31", 0.53)]
    annual = {"no_annual": [],
              "missing_q2": [_a(2024, "2024-12-31", 1.99)],
              "annual_ends_elsewhere": [_a(2024, "2024-06-30", 1.99)]}[case]
    MF.derive_q4_eps(q, annual)
    assert "diluted_earnings_per_share" not in q[0]["financials"]["income_statement"]
    assert "basic_earnings_per_share" not in q[0]["financials"]["income_statement"]


def test_canslim_C_on_a_Q4_print_uses_the_DERIVED_Q4(cs, fake):
    fake.tables[("income-statements", "quarterly")] = [
        inc(2025, 4, "2025-12-31", "2026-01-28", diluted_earnings_per_share=0.11),  # v1: broken
        inc(2025, 3, "2025-09-30", "2025-10-20", diluted_earnings_per_share=0.60),
        inc(2025, 2, "2025-06-30", "2025-07-20", diluted_earnings_per_share=0.70),
        inc(2025, 1, "2025-03-31", "2025-04-20", diluted_earnings_per_share=0.65),
        inc(2024, 4, "2024-12-31", "2025-01-28", diluted_earnings_per_share=0.05),  # v1: broken
        inc(2024, 3, "2024-09-30", "2024-10-20", diluted_earnings_per_share=0.54),
        inc(2024, 2, "2024-06-30", "2024-07-20", diluted_earnings_per_share=0.49),
        inc(2024, 1, "2024-03-31", "2024-04-20", diluted_earnings_per_share=0.53)]
    fake.tables[("income-statements", "annual")] = [
        inc(2025, 4, "2025-12-31", "2026-01-28", timeframe="annual", diluted_earnings_per_share=2.50),
        inc(2024, 4, "2024-12-31", "2025-01-28", timeframe="annual", diluted_earnings_per_share=1.99)]
    m = cs._fetch_massive_financials("NFLX")
    q4_25, q4_24 = 2.50 - 0.60 - 0.70 - 0.65, 1.99 - 0.54 - 0.49 - 0.53
    assert m["eps_q_series"][0] == pytest.approx(q4_25)
    assert m["q_eps_growth_pct"] == round((q4_25 - q4_24) / abs(q4_24) * 100, 2)


def test_NEGATIVE_longterm_warm_during_an_OUTAGE_keeps_last_weeks_row(monkeypatch):
    """Critic 2026-09-30 (#5): the Sunday warm replaced the stored cross-section
    with the survivors, so an outage dropped names for a week. An outage now
    carries the prior row forward; a company with no filings still drops."""
    from sepa import longterm as LT

    prior = {"rows": {"OUT": {"m": {"roce": 30.0}, "coverage": {"years_available": 12},
                              "absent_because": {}, "sector": "Technology"},
                      "GONE": {"m": {"roce": 5.0}, "coverage": {}, "sector": "Technology"}}}
    res = {"OK": {"symbol": "OK", "ok": True, "metrics": {"roce": 20.0},
                  "coverage": {"years_available": 12}, "absent_because": {}},
           "OUT": {"symbol": "OUT", "ok": False, "error": "rate_limited", "reason": "outage"},
           "NEW": {"symbol": "NEW", "ok": False, "error": "server_error", "reason": "outage"},
           "GONE": {"symbol": "GONE", "ok": False, "reason": "no filed annual financials"}}
    written = {}

    class _Coll:
        def replace_one(self, q, doc, upsert=False):
            written["doc"] = doc

    monkeypatch.setattr(LT, "metrics", lambda s: res[s])
    monkeypatch.setattr(LT, "stored", lambda db=None: prior)
    monkeypatch.setattr(LT, "_sector_map", lambda db=None: {"OK": "Technology", "OUT": "Technology"})
    from sepa import canslim
    monkeypatch.setattr(canslim, "fundamentals_for", lambda s: {"inst_ownership_pct": 60.0})
    out = LT.warm(universe=list(res), max_workers=1, db={LT.COLL: _Coll()})
    rows = written["doc"]["rows"]
    assert set(rows) == {"OK", "OUT"}
    assert rows["OUT"]["carried_forward"] is True and rows["OUT"]["m"]["roce"] == 30.0
    assert out["carried_forward"] == 1 and out["failed"] == 3
    assert written["doc"]["n_carried_forward"] == 1


def test_the_OLDEST_Q4_in_canslims_window_still_gets_its_EPS(cs, fake):
    """Critic 2026-09-30 (low): with exactly 12 quarters asked, the oldest Q4's
    Q1..Q3 fell outside the window and its derived EPS read None."""
    rows = []
    for fy in (2026, 2025, 2024, 2023):
        for q in (4, 3, 2, 1):
            rows.append(inc(fy, q, f"{fy}-{q * 3:02d}-28", f"{fy}-{q * 3:02d}-28" if q < 4 else f"{fy + 1}-01-28",
                            diluted_earnings_per_share=0.99 if q == 4 else float(q)))
    fake.tables[("income-statements", "quarterly")] = rows
    fake.tables[("income-statements", "annual")] = [
        inc(fy, 4, f"{fy}-12-28", f"{fy + 1}-01-28", timeframe="annual", diluted_earnings_per_share=10.0)
        for fy in (2026, 2025, 2024, 2023)]
    m = cs._fetch_massive_financials("X")
    assert len(m["q_period_series"]) == 12
    q4s = [e for p, e in zip(m["q_period_series"], m["eps_q_series"]) if p % 4 == 3]
    assert q4s == [4.0, 4.0, 4.0]                      # 10 − (1+2+3), none None


def test_NEGATIVE_a_padded_ask_is_short_only_against_what_the_caller_wants(fake):
    """Critic 2026-09-30 (low): a 12-year ask padded to 24 re-asked by CIK for
    nearly every company. 12 of 12 is a full answer."""
    fake.tables[("income-statements", "annual")] = [
        inc(2025 - i, 4, f"{2025 - i}-12-31", f"{2026 - i}-02-01", timeframe="annual",
            revenue=1e9) for i in range(12)]
    MF.fetch_reports("AAPL", timeframe="annual", limit=12,
                     statements=(MF.INCOME,), key=KEY)
    assert len(fake.calls) == 1 and fake.calls[0]["params"]["limit"] == 24


# ═════════════════════════════════════════════ 2026-10-08: the revenue line per template
import json as _json

FIXTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "revenue_line_rows_2026_10_08.json"
FX = _json.loads(FIXTURE.read_text())["names"]
LEVEL_TOL = 0.002          # the 2026-10-07 measurement's representation tolerance (0.2 %)
PCT_TOL = 0.10             # pp — same measurement; NOT a rule
RANKED = ("BAC JPM C GS SCHW STT OMF LPLA RKT CVS BRO O HPE NEE MCD EQIX CB AIG "
          "MS CFG HWC AMT TRV").split()


def _pair(sym):
    rows = FX[sym]["rows"]
    by_end = {r["period_end"]: r for r in rows}
    return by_end[FX[sym]["latest_end"]], by_end[FX[sym]["year_ago_end"]]


def _near(a, b, tol=LEVEL_TOL):
    return a is not None and b is not None and abs(a - b) <= tol * abs(b)


@pytest.mark.parametrize("sym", RANKED)
def test_the_mapped_revenue_line_reproduces_the_10Q_on_real_rows(sym):
    """Real v1 rows (2026-10-07 pull) vs the 10-Q face (R-file) / SEC
    companyfacts (non-held): both quarter levels within 0.2 %, and the YoY
    within 0.10 pp OR on levels (CB 0.16 pp, $1 M rounding — §1.4)."""
    cur, ya = _pair(sym)
    sec = FX[sym]["sec"]
    v0, l0, n0 = MF.revenue_line(cur)
    v4, l4, n4 = MF.revenue_line(ya)
    assert n0 is None and n4 is None and l0 == l4 and l0 != MF.LINE_UNDETERMINED
    assert _near(v0, sec["cur"]) and _near(v4, sec["year_ago"]), (sym, v0, v4, sec)
    pct = round((v0 - v4) / abs(v4) * 100, 2)
    assert abs(pct - sec["pct"]) <= PCT_TOL or (_near(v0, sec["cur"]) and _near(v4, sec["year_ago"]))


@pytest.mark.parametrize("sym,cur,ya,pct", [
    ("BAC", 31558e6, 27443e6, 14.99), ("C", 24766e6, 21668e6, 14.30),
    ("LPLA", 5186623e3, 3835025e3, 35.24), ("RKT", 2784e6, 1451e6, 91.87),
    ("CVS", 106096e6, 98915e6, 7.26), ("MS", 21348e6, 16792e6, 27.13),
    ("CFG", 2283e6, 2037e6, 12.08), ("HWC", 401362e3, 375483e3, 6.89)])
def test_named_names_land_on_the_10Q_figure(sym, cur, ya, pct):
    a, b = (MF.revenue_line(r)[0] for r in _pair(sym))
    assert _near(a, cur) and _near(b, ya)
    assert round((a - b) / abs(b) * 100, 2) == pytest.approx(pct, abs=PCT_TOL)


def test_BAC_through_fetch_reports_is_the_net_line_with_provenance(fake):
    cur, ya = _pair("BAC")
    fake.tables[("income-statements", "quarterly")] = [cur, ya]
    r0, r4 = MF.fetch_reports("BAC", timeframe="quarterly", limit=2,
                              statements=(MF.INCOME,), key=KEY)
    assert r0["financials"]["income_statement"]["revenues"] == {"value": 31558000000.0}
    assert r4["financials"]["income_statement"]["revenues"] == {"value": 27443000000.0}
    assert r0["revenue_line"] == MF.LINE_NET_OF_INTEREST and r0["revenue_line_note"] is None


def test_report_level_keys_only_when_the_income_statement_is_read():
    row = _pair("MCD")[0]
    r = MF.to_vx_report((2026, 2), {MF.INCOME: row}, "quarterly", (MF.INCOME,))
    assert r["revenue_line"] == MF.LINE_REVENUE and "revenue_line_note" in r
    assert r["financials"]["income_statement"]["revenues"] == {"value": row["revenue"]}
    b = MF.to_vx_report((2026, 2), {MF.BALANCE: bal(2026, 2, "2026-06-30", "2026-08-01")},
                        "quarterly", (MF.BALANCE,))
    assert "revenue_line" not in b and "revenue_line_note" not in b


def test_line_words_and_ledgers_are_well_formed():
    assert set(MF.LINE_WORDS) == set(MF.LINE_CODES)
    assert not set(MF.REVENUE_LINE_PICKS) & set(MF.REVENUE_LINE_HOLD)
    for cik, (tk, tmpl, line) in MF.REVENUE_LINE_PICKS.items():
        assert re.fullmatch(r"\d{10}", cik) and tk
        assert tmpl in (MF.TEMPLATE_FINANCIAL, MF.TEMPLATE_INSURANCE, MF.TEMPLATE_STANDARD)
        assert line in MF.LINE_CODES and line != MF.LINE_UNDETERMINED
    for cik, (tk, kind, note) in MF.REVENUE_LINE_HOLD.items():
        assert re.fullmatch(r"\d{10}", cik) and tk
        assert kind in (MF.HOLD_UNVERIFIED, MF.HOLD_HIS_CALL) and isinstance(note, str) and note
    assert len(MF.REVENUE_LINE_PICKS) == 8 and len(MF.REVENUE_LINE_HOLD) == 39   # + C CACC; + 4 BDCs, CBSH (critic round 2)
    # every fixture name's CIK is the ledger's CIK for that ticker
    tick = {v[0]: k for k, v in {**MF.REVENUE_LINE_PICKS, **MF.REVENUE_LINE_HOLD}.items()}
    for sym, d in FX.items():
        if sym in tick:
            assert tick[sym] == d["cik"], sym


def test_template_is_read_from_KEY_PRESENCE():
    assert MF.FIN_TEMPLATE_ABSENT_KEYS == ("interest_expense", "research_development")
    assert MF.row_template(_pair("BAC")[0]) == MF.TEMPLATE_FINANCIAL
    assert MF.row_template(_pair("TRV")[0]) == MF.TEMPLATE_INSURANCE
    assert MF.row_template(_pair("MCD")[0]) == MF.TEMPLATE_STANDARD
    # zero-filled is PRESENT
    assert MF.row_template({"interest_expense": 0.0, "research_development": 0.0}) == MF.TEMPLATE_STANDARD


# ───────────────────────────── NEGATIVES
@pytest.mark.parametrize("sym", ["MCD", "NEE"])
def test_NEGATIVE_a_standard_row_keeps_v1_revenue(sym):
    for row in _pair(sym):
        v, line, note = MF.revenue_line(row)
        assert (v, line, note) == (row["revenue"], MF.LINE_REVENUE, None)


def test_NEGATIVE_an_insurer_is_plain_revenue_never_revenue_minus_cost_TRV():
    cur = _pair("TRV")[0]
    assert cur["cost_of_revenue"] == 7708000000.0
    v, line, _ = MF.revenue_line(cur)
    assert v == 12153000000.0 and line == MF.LINE_REVENUE
    assert v != cur["revenue"] - cur["cost_of_revenue"]


def test_NEGATIVE_STT_2024_bank_row_without_a_cost_line_is_a_HOLE_never_gross(fake):
    stt = [r for r in FX["STT"]["rows"] if r["period_end"] == "2024-06-30"][0]
    assert stt["cost_of_revenue"] == 0.0 and stt["revenue"] > 0
    assert MF.revenue_line(stt) == (None, MF.LINE_UNDETERMINED, None)
    fake.tables[("income-statements", "quarterly")] = [stt]
    [r] = MF.fetch_reports("STT", timeframe="quarterly", limit=1,
                           statements=(MF.INCOME,), key=KEY)
    assert "revenues" not in r["financials"]["income_statement"]
    assert r["revenue_line"] == MF.LINE_UNDETERMINED


def test_NEGATIVE_a_bank_row_with_revenue_zero_is_undetermined():
    row = fin_inc(2026, 2, "2026-06-30", "2026-08-01", revenue=0.0, cost_of_revenue=5e9)
    assert MF.revenue_line(row) == (None, MF.LINE_UNDETERMINED, None)


@pytest.mark.parametrize("sym", ["AMT", "EQIX"])
def test_NEGATIVE_the_refuted_REIT_rule_never_appears(sym):
    """revenue + interest income breaks AMT (4.65→5.12) and EQIX (16.36→15.29)."""
    for row in _pair(sym):
        v, line, note = MF.revenue_line(row)
        assert (v, line, note) == (row["revenue"], MF.LINE_REVENUE, None)


def test_NEGATIVE_a_pick_ticker_on_ANOTHER_CIK_takes_the_default_rule():
    """Recycled tickers (RKT carried Rock-Tenn): the pick is keyed by CIK."""
    row = dict(_pair("RKT")[0], cik="0000123456")
    v, line, note = MF.revenue_line(row)
    assert line == MF.LINE_NET_OF_INTEREST and note is None
    assert v == pytest.approx(row["revenue"] - row["cost_of_revenue"])   # the rule adds no other income


def test_NEGATIVE_the_CVS_pick_on_a_financial_shaped_row_is_default_plus_a_note():
    cvs = _pair("CVS")[0]
    row = {k: v for k, v in cvs.items() if k not in MF.FIN_TEMPLATE_ABSENT_KEYS}
    v, line, note = MF.revenue_line(row)
    assert line == MF.LINE_NET_OF_INTEREST and note == MF.NOTE_PICK_SHAPE_CHANGED
    assert v != 106096000000.0


def test_NEGATIVE_hold_names_keep_their_value_and_carry_the_note():
    v, line, note = MF.revenue_line(_pair("SOFI")[0])
    assert (v, line, note) == (_pair("SOFI")[0]["revenue"], MF.LINE_REVENUE, MF.NOTE_NO_NII)
    nu = _pair("NU")[0]
    v, line, note = MF.revenue_line(nu)
    assert line == MF.LINE_NET_OF_INTEREST and note == MF.NOTE_FOREIGN_FILER
    assert v == pytest.approx(nu["revenue"] - nu["cost_of_revenue"])     # the rule adds no other income
    cvx = _pair("CVX")[0]
    v, line, note = MF.revenue_line(cvx)
    assert (v, line, note) == (cvx["revenue"], MF.LINE_REVENUE, MF.NOTE_SUBLINE_CALL)
    assert MF.REVENUE_LINE_HOLD[cvx["cik"]][1] == MF.HOLD_HIS_CALL


def test_NEGATIVE_the_inc_fixture_is_the_standard_template_the_trap_cannot_return():
    assert MF.row_template(inc(2026, 2, "2026-06-30", "2026-08-01")) == MF.TEMPLATE_STANDARD
    assert MF.row_template(NVDA_Q2_27) == MF.TEMPLATE_STANDARD
    assert MF.row_template(fin_inc(2026, 2, "2026-06-30", "2026-08-01")) == MF.TEMPLATE_FINANCIAL


def test_SOURCE_GUARD_only_the_helper_reads_the_revenue_line_inputs():
    """One engine: no live module but the helper names the lines the
    template rule combines (0 offenders 2026-10-08)."""
    pat = re.compile(r"""["'](cost_of_revenue|other_income_expense|interest_income)["']""")
    offenders = [rel for rel, src in _live_modules()
                 if pat.search(src) and rel != "sepa/massive_fundamentals.py"]
    assert offenders == [], offenders
