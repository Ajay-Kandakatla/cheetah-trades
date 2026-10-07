"""🛡️ 🚀 growth — the critic round on the 2026-10-07 b fix (2026-10-07 c).

Ajay 2026-10-07: "yes please also no #s for SNDK can you do a deep analysis of
data and make sure you do a sanity chcek fo missing data pieces over all."

The critic MEASURED, on real data, eight things the b round got wrong or left
untested. One test group per finding; every group has a NEGATIVE that fails if
the fix is reverted:

  1. labels four apart, quarters NOT a year apart (CRDO 455 days, KLIC 273,
     CAKE 728) — the stored period END dates now refuse the pair;
  2. a stored sales figure that disagrees with the v1 series is not "a
     disagreement with the company's own filings" (141 of 151 stored figures
     match the vX filing revenue);
  3. "no quarterly figures" split: a yfinance-fallback doc is not "neither
     provider";
  4. a year-ago revenue at or under $0 is not a "loss";
  5. `_etf_set` really reads the etf_info cache;
  6-8. docs: the QoQ-rank lag, PSKY = HIS CALL 12, SNDK's fiscal label.
Hermetic: no network, no Mongo.
"""
from __future__ import annotations

import copy
import inspect
import os

import pytest

from chart_maps import resiliency_tab as R
from sepa import canslim, capital_returns, etf_info, qoq, research, symbols as S
from tests.test_qoq_backfill_vintage_2026_10_07 import FakeColl, _doc, _m, wire  # noqa: F401
from tests.test_resiliency_growth_sanity_2026_10_07 import (BAC, PBF, SNDK_HEALED, TODAY, VST,
                                                            _chip, _fund, _mixed)
from tests.test_resiliency_tab import CAL, SESSION, _events, _frame, _spy_frame  # noqa: F401

DOCS = os.path.join(os.path.dirname(__file__), "..", "..", "docs")

# CRDO as cached (critic, MEASURED vs the raw vX rows): slot 0 ends 2026-08-01,
# slot 4 ends 2025-05-03 — labels four apart, 455 days.
PER = [8107, 8106, 8105, 8104, 8103, 8102]
CRDO_ENDS = ["2026-08-01", "2026-05-02", "2026-01-31", "2025-11-01", "2025-05-03", "2025-02-01"]
# KLIC: 2026-07-04 vs 2025-10-04 — 273 days
KLIC_ENDS = ["2026-07-04", "2026-04-04", "2026-01-03", "2025-12-27", "2025-10-04", "2025-06-28"]
GOOD_ENDS = ["2026-08-01", "2026-05-02", "2026-01-31", "2025-11-01", "2025-08-02", "2025-05-03"]


def _two_leg(ends=None):
    f = _fund(rev_pct=181.7, eps_pct=235.0, periods=PER,
              rev=[2.817e8, 1, 1, 1, 1.0e8, 1], eps=[0.67, 1, 1, 1, 0.20, 1])
    if ends is not None:
        f[qoq.END_SERIES_KEY] = list(ends)
    return f


def _read(path):
    with open(os.path.join(DOCS, path), encoding="utf-8") as fh:
        return fh.read()


# --------------------------------------------------------------------------
# 1 — the end dates refuse a mislabelled pair
# --------------------------------------------------------------------------
@pytest.mark.parametrize("a,b,ok", [
    ("2026-08-01", "2025-08-02", True),     # 364 — a 52-week year
    ("2026-06-30", "2025-06-30", True),     # 365
    ("2026-01-03", "2024-12-28", True),     # 371 — a 53-week year
    ("2026-08-01", "2025-05-03", False),    # CRDO 455
    ("2026-07-04", "2025-10-04", False),    # KLIC 273
    ("2026-06-27", "2024-06-29", False),    # CAKE-class 728
    ("2026-06-30", "2026-03-31", False),    # NRIX/XERS-class 91
])
def test_ends_year_apart(a, b, ok):
    assert qoq.ends_year_apart([a, None, None, None, b]) is ok


def test_NEG_ends_unverifiable_is_None_never_a_refusal():
    for ends in (None, [], ["2026-08-01"], ["2026-08-01", None, None, None, None],
                 [None, None, None, None, "2025-08-02"], ["bad", 1, 2, 3, "2025-08-02"]):
        assert qoq.ends_year_apart(ends) is None, ends


def test_period_ok_refuses_crdo_and_klic_on_their_end_dates():
    assert qoq.period_ok(PER) is True                         # the labels alone pass
    assert qoq.period_ok(PER, ends=CRDO_ENDS) is False
    assert qoq.period_ok(PER, ends=KLIC_ENDS) is False
    assert qoq.period_ok(PER, ends=GOOD_ENDS) is True


def test_NEG_period_ok_without_ends_is_the_label_answer_for_every_other_caller():
    for p in (PER, [8105, 8104, 8102, 8101, 8100, 8098], None, [None, None]):
        assert qoq.period_ok(p) == qoq.period_ok(p, ends=None)


def test_window_is_same_quarter_days_by_name(monkeypatch):
    assert qoq.YEAR_DAYS == 365
    monkeypatch.setattr(capital_returns, "SAME_QUARTER_DAYS", 100)
    assert qoq.ends_year_apart(CRDO_ENDS) is True              # 455 within 365±100


def test_growth_read_crdo_is_period_mismatch_and_never_ranks():
    g, chip = _chip(_two_leg(CRDO_ENDS), today=TODAY)
    assert g["state"] == "period_mismatch" and g["score"] is None and g["legs"] == 0
    assert not g["sales_ranked"] and not g["eps_ranked"]
    assert chip == "Sales · EPS: " + R.GROWTH_MISMATCH
    assert R.coverage_class(g, bars=400, min_bars=research.MIN_RESEARCH_BARS) == "period_gap"
    g2, _ = _chip(_two_leg(KLIC_ENDS), today=TODAY)
    assert g2["state"] == "period_mismatch" and g2["score"] is None


def test_NEG_the_same_doc_with_year_apart_ends_or_no_ends_still_ranks_two_legs():
    for ends in (GOOD_ENDS, None):
        g, _ = _chip(_two_leg(ends), today=TODAY)
        assert g["state"] == "read" and g["legs"] == 2 and g["sales_ranked"] and g["eps_ranked"]


def _report(fy, q, end, rev):
    return {"fiscal_year": fy, "fiscal_period": f"Q{q}", "end_date": end,
            "financials": {"income_statement": {"revenues": {"value": rev, "unit": "USD"},
                                                "diluted_earnings_per_share": {"value": 1.0}},
                           "balance_sheet": {}}}


def test_canslim_stores_end_dates_parallel_to_the_aligned_keys(monkeypatch):
    from sepa import massive_fundamentals as MF
    q = [_report(2026, 2, "2026-07-26", 250), _report(2026, 1, "2026-04-26", 200),
         _report(2025, 3, "2025-10-26", 180),                 # FY2025 Q4 absent → hole
         _report(2025, 2, "2025-07-27", 150), _report(2025, 1, "2025-04-27", 100)]
    monkeypatch.setattr(MF, "fetch_reports",
                        lambda s, *, timeframe, limit, statements=(), timeout=None, key=None:
                        list(q) if timeframe == "quarterly" else [])
    monkeypatch.setattr(canslim, "stocks_key", lambda: "test-key")
    monkeypatch.setattr(canslim, "_massive_financials_disabled", False)
    m = canslim._fetch_massive_financials("TEST")
    assert m["q_period_series"] == [8105, 8104, None, 8102, 8101, 8100]
    assert m["q_end_series"] == ["2026-07-26", "2026-04-26", None, "2025-10-26",
                                 "2025-07-27", "2025-04-27"]
    assert qoq.ends_year_apart(m["q_end_series"]) is True
    assert canslim._end_day(None) is None and canslim._end_day({"end_date": ""}) is None


def test_research_snapshot_projects_and_serves_the_end_dates(monkeypatch):
    assert "fundamentals.q_end_series" in research.DECISION_FIELDS
    import time as _t
    doc = {"symbol": "CRDO", "cached_at": _t.time(),
           "fundamentals": {"q_period_series": PER, "q_end_series": CRDO_ENDS}}

    class C:
        def find(self, q, proj):
            assert proj.get("fundamentals.q_end_series") == 1
            return [copy.deepcopy(doc)]
    monkeypatch.setattr(research, "_get_cache", lambda: C())
    assert research.decision_snapshot(["CRDO"])["CRDO"]["q_end_series"] == CRDO_ENDS


def test_backfill_writes_the_end_dates_with_the_keys(wire):
    rev, eps = [1.1e9, 1, 1, 1, 1.0e9, 1], [1.1, 1, 1, 1, 1.0, 1]
    m = _m(rev=rev, eps=eps)
    m["q_end_series"] = list(GOOD_ENDS)
    coll = wire([_doc("OK", rev=rev, eps=eps, rev_pct=10.0, eps_pct=10.0)], {"OK": m})
    assert qoq.backfill(["OK"], only_missing=False, now=0.0)["filled"] == 1
    (_flt, upd), = coll.updates
    assert upd["$set"]["fundamentals.q_end_series"] == GOOD_ENDS


def test_NEG_backfill_never_leaves_stale_end_dates_beside_new_keys(wire):
    rev, eps = [1.1e9, 1, 1, 1, 1.0e9, 1], [1.1, 1, 1, 1, 1.0, 1]
    d = _doc("OK", rev=rev, eps=eps, rev_pct=10.0, eps_pct=10.0)
    d["fundamentals"]["q_end_series"] = list(CRDO_ENDS)
    coll = wire([d], {"OK": _m(rev=rev, eps=eps)})           # the fetch carries no dates
    qoq.backfill(["OK"], only_missing=False, now=0.0)
    (_flt, upd), = coll.updates
    assert "fundamentals.q_end_series" in upd["$set"]
    assert upd["$set"]["fundamentals.q_end_series"] is None


def test_realign_moves_the_end_dates_with_the_keys(monkeypatch):
    d = {"symbol": "X", "fundamentals": {
        "q_period_series": [8105, 8104, 8102, 8101],
        "rev_q_series": [4.0, 3.0, 2.0, 1.0],
        "q_end_series": ["2026-06-30", "2026-03-31", "2025-09-30", "2025-06-30"]}}
    nodates = {"symbol": "Y", "fundamentals": {
        "q_period_series": [8105, 8104, 8102, 8101], "rev_q_series": [4.0, 3.0, 2.0, 1.0]}}
    coll = FakeColl([d, nodates])
    monkeypatch.setattr(research, "_get_cache", lambda: coll)
    out = qoq.realign()
    assert out["realigned"] == 2
    sets = {flt["symbol"]: upd["$set"] for flt, upd in coll.updates}
    assert sets["X"]["fundamentals.q_period_series"] == [8105, 8104, None, 8102, 8101]
    assert sets["X"]["fundamentals.q_end_series"] == ["2026-06-30", "2026-03-31", None,
                                                      "2025-09-30", "2025-06-30"]
    assert sets["Y"]["fundamentals.q_end_series"] is None     # NEG: never invented


# --------------------------------------------------------------------------
# 2 — a stored figure vs the series is not "vs the filings"
# --------------------------------------------------------------------------
def test_stored_disagrees_text_names_the_series_not_the_filings():
    g, chip = _chip(BAC, today=TODAY)
    assert g["sales_reason"] == "stored_disagrees" and not g["sales_ranked"]
    st = R._growth_stat(g)
    assert "sales +19.25% stored vs +3.67% from the quarterly series on file" in st
    assert "the stored figure and the quarterly series disagree" in st
    assert "filings" not in st and "realigns" not in st
    why = R._gap_why("pending", {})
    assert "filings" not in why and "quarterly series on file" in why


def test_NEG_no_growth_text_calls_the_series_the_filings():
    src = inspect.getsource(R)
    assert "own quarterly filings" not in src and "quarterly filings on file" not in src
    assert "a research refresh realigns them" not in src


# --------------------------------------------------------------------------
# 3 — "no quarterly figures" split
# --------------------------------------------------------------------------
YF_EMPTY = _fund(periods=[], src="yfinance")
MASSIVE_EMPTY = _fund()                                       # Massive/hybrid doc, nothing


def test_a_yfinance_fallback_doc_with_nothing_is_massive_unused():
    g, chip = _chip(YF_EMPTY, today=TODAY)
    assert g["state"] == "no_figures" and g["massive_unused"] is True
    assert R.coverage_class(g, bars=400, min_bars=220) == "massive_unused"
    assert chip == "Sales · EPS: " + R.GROWTH_MASSIVE_UNUSED
    assert "fell back to yfinance" in R._growth_stat(g)
    assert "neither provider" not in R._gap_why("massive_unused", {})


def test_NEG_a_massive_doc_with_nothing_stays_no_filings_and_never_says_neither_provider():
    g, chip = _chip(MASSIVE_EMPTY, today=TODAY)
    assert g["state"] == "no_figures" and g["massive_unused"] is False
    assert R.coverage_class(g, bars=400, min_bars=220) == "no_filings"
    assert chip == "Sales · EPS: " + R.GROWTH_NO_FIGURES
    for k in R.GAP_ORDER:
        assert "neither provider" not in R._gap_why(k, {"min_bars": 220, "ttl_days": 16})
    # a yfinance doc WITH figures is a read, never massive_unused
    assert R.growth_read(SNDK_HEALED, today=TODAY)["massive_unused"] is False


def test_build_counts_the_massive_unused_bucket_on_the_line():
    frames, fund = _mixed()
    frames["YFE"] = _frame(n=400, volume=1.1e6)
    fund["YFE"] = YF_EMPTY
    e = R.build("full", SESSION, universe_fn=lambda u: [s for s in frames if s != "SPY"],
                frames_fn=lambda syms: {s: frames[s] for s in syms if s in frames},
                events_fn=lambda a, b: _events(), calendar_fn=lambda: CAL,
                fund_fn=lambda syms: dict(fund), etf_fn=lambda syms: {"SMH"} & set(syms))
    assert e["reads"]["YFE"]["growth"]["gap"] == "massive_unused"
    assert e["reads"]["NOFIL"]["growth"]["gap"] == "no_filings"
    cov = e["growth_coverage"]
    assert cov["classes"]["massive_unused"] == 1 and sum(cov["classes"].values()) == cov["n"]
    line = R.growth_line(cov)
    assert "1 Massive not used at research time, 1 no quarterly figures" in line
    lines = R.growth_gaps_block(cov)["lines"]
    assert any(ln.startswith("Massive not used at research time (1): ") and ln.endswith("— YFE")
               for ln in lines)


# --------------------------------------------------------------------------
# 4 — a year-ago revenue at or under $0 is not a loss
# --------------------------------------------------------------------------
def test_sales_leg_on_a_non_positive_base_says_no_revenue_not_loss():
    zero = _fund(rev_pct=None, eps_pct=None, rev=[5e6, 1, 1, 1, 0.0, 1])
    g, chip = _chip(zero, today=TODAY)
    assert g["sales_base"] == "non_positive" and g["sales_reason"] == "year_ago_loss"
    assert chip.startswith("Sales yr-ago rev ≤$0 · ")
    assert R.SALES_NO_REV_TOKEN == "yr-ago rev ≤$0"


def test_NEG_the_eps_leg_keeps_yr_ago_loss_and_the_sales_leg_never_says_loss():
    g, chip = _chip(PBF, today=TODAY)                          # EPS year-ago -0.05
    assert chip == "Sales +56.3% · EPS yr-ago loss YoY (FY2026 Q2)"
    neg = R.growth_read(_fund(rev_pct=900.0, rev=[5e6, 1, 1, 1, -3e6, 1]))
    assert "loss" not in R._leg_token(neg, "sales")
    assert "no revenue" in R._gap_why("by_rule", {})


# --------------------------------------------------------------------------
# 5 — `_etf_set` really reads the etf_info cache
# --------------------------------------------------------------------------
def test_etf_set_includes_the_etf_info_cache(monkeypatch):
    seen = []
    monkeypatch.setattr(etf_info, "cached_etf_set", lambda syms: seen.append(list(syms)) or {"ZZETF"})
    assert "ZZETF" in R._etf_set(["ZZETF", "NVDA"])
    assert seen == [["ZZETF", "NVDA"]]


def test_NEG_build_without_etf_fn_reads_the_cache_and_the_card_is_an_etf(monkeypatch):
    from sepa import universe as U
    monkeypatch.setattr(U, "fetch_etf_universe", lambda: [])
    monkeypatch.setattr(etf_info, "cached_etf_set", lambda syms: {"ZZETF"} & set(syms))
    frames = {"SPY": _spy_frame(), "ZZETF": _frame(n=400, volume=5e6),
              "VST": _frame(n=400, volume=4e6)}
    fund = {"ZZETF": VST, "VST": VST}
    e = R.build("full", SESSION, universe_fn=lambda u: ["ZZETF", "VST"],
                frames_fn=lambda syms: {s: frames[s] for s in syms if s in frames},
                events_fn=lambda a, b: _events(), calendar_fn=lambda: CAL,
                fund_fn=lambda syms: dict(fund))
    assert e["reads"]["ZZETF"]["growth"]["state"] == "etf"
    assert e["reads"]["ZZETF"]["growth"]["score"] is None
    assert e["reads"]["VST"]["growth"]["state"] == "read"


# --------------------------------------------------------------------------
# 6-8 — docs + fates
# --------------------------------------------------------------------------
def test_breakout_qoq_doc_names_the_sunday_lag():
    txt = _read("sepa/breakout_qoq_rank.md")
    assert "reaches the QoQ rank only after the Sunday" in txt and "HIS CALL" in txt


def test_psky_fate_is_marked_his_call_12():
    ev = S.DELISTED["PSKY"]
    assert "HIS CALL 12" in ev and "PZG" in ev
    assert "HIS CALL 12" not in S.DELISTED["DBRG"]               # NEG: only the ambiguous one


def test_sndk_afterwards_line_uses_its_fiscal_label():
    txt = _read("sepa/keeping_data_current.md")
    assert "`Sales +371.6% · EPS yr-ago loss YoY (FY2026 Q4)`" in txt
    assert "should read `Sales +371.6% · EPS yr-ago loss YoY (Q2 2026)`" not in txt


def test_NEG_docs_drop_the_clean_top_15_and_the_filings_claim():
    res = _read("chart_maps/resiliency_tab_2026_09_30.md")
    assert "— every one\n  two-leg." not in res and "every one two-leg" not in res
    assert "CRDO" in res and "KLIC" in res
    audit = _read("sepa/missing_data_audit_2026_10_07.md")
    assert "was RANKED on the stale number" not in audit
    assert "141" in audit
