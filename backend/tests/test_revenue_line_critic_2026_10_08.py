"""Revenue line — critic round 2 (2026-10-08). Hermetic: real v1 rows, no network.

Ajay 2026-10-08, on the 141 held-out names: "update them please".

1. The financial-template rule is revenue − cost_of_revenue ONLY. Adding
   other_income_expense put SF ~10 % low at BOTH levels (1,306.9 vs the 10-Q's
   1,450.8 M); C, the one name whose 10-Q total carries other income, takes a
   CIK pick (`LINE_NET_PLUS_OTHER`).
2. The §5.3 census (99 non-held Financial-Services names, real v1 rows +
   SEC companyfacts): CACC (a lender whose 10-Q headlines gross) takes a plain
   pick; the BDCs ARCC FSK MAIN OBDC and CBSH (no line reproduces the 10-Q)
   are held.
3. `growth_read` reads the hole PER SLOT (`rev_line_series`): `rev_line` is the
   newest FILED slot's line and is never "undetermined" on a written doc.
4. The realign projection carries `rev_line_series` (FakeColl now honours the
   projection — see test_revenue_line_persist).
5. The audit selects the expected-net names from the ledger CSV, and an
   expected-net name matches on a NET tag only.
"""
from __future__ import annotations

import copy
import json
import pathlib

import pytest

from chart_maps import resiliency_tab as R
from scripts import revenue_line_audit as A
from sepa import canslim, qoq
from sepa import massive_fundamentals as MF
from tests.test_resiliency_growth_sanity_2026_10_07 import CACHED, TODAY, _chip

FIX = pathlib.Path(__file__).resolve().parent / "fixtures"
CEN = json.loads((FIX / "revenue_line_census_rows_2026_10_08.json").read_text())["names"]
HELD = json.loads((FIX / "revenue_line_rows_2026_10_08.json").read_text())["names"]
LEVEL_TOL = 0.002          # the 2026-10-07 measurement's representation tolerance (0.2 %), NOT a rule


def _near(a, b, tol=LEVEL_TOL):
    return a is not None and b is not None and abs(a - b) <= tol * abs(b)


def _cen(sym):
    cur, ya = CEN[sym]["rows"]
    return cur, ya


def _held(sym):
    by_end = {r["period_end"]: r for r in HELD[sym]["rows"]}
    return by_end[HELD[sym]["latest_end"]], by_end[HELD[sym]["year_ago_end"]]


# ═════════════════════════════════════ 1. the rule is revenue − cost only
def test_SF_net_line_lands_on_the_10Q_RevenuesNetOfInterestExpense_at_both_levels():
    cur, ya = _cen("SF")
    sec = CEN["SF"]["sec"]
    assert sec["tag"] == "RevenuesNetOfInterestExpense"
    v0, l0, n0 = MF.revenue_line(cur)
    v4, l4, n4 = MF.revenue_line(ya)
    assert (l0, l4, n0, n4) == (MF.LINE_NET_OF_INTEREST, MF.LINE_NET_OF_INTEREST, None, None)
    assert _near(v0, 1450.8e6) and _near(v4, 1284.3e6)
    assert _near(v0, sec["cur"]) and _near(v4, sec["year_ago"])


def test_NEGATIVE_SF_has_other_income_so_the_old_plus_oie_rule_is_10pct_low():
    """Fails if `+ other_income_expense` returns to the rule: SF's real rows
    carry −143.9 M of other income, which is NOT in the 10-Q's net total."""
    cur, ya = _cen("SF")
    assert cur["other_income_expense"] < -100e6
    old0 = cur["revenue"] - cur["cost_of_revenue"] + cur["other_income_expense"]
    assert not _near(old0, CEN["SF"]["sec"]["cur"], tol=0.05)
    assert MF.revenue_line(cur)[0] == pytest.approx(cur["revenue"] - cur["cost_of_revenue"])


def test_JEF_broker_stays_on_the_net_line():
    cur, ya = _cen("JEF")
    v0, v4 = MF.revenue_line(cur)[0], MF.revenue_line(ya)[0]
    assert _near(v0, CEN["JEF"]["sec"]["cur"]) and _near(v4, CEN["JEF"]["sec"]["year_ago"])


def test_C_takes_the_net_plus_other_pick_24766_and_21668():
    cur, ya = _held("C")
    assert MF.REVENUE_LINE_PICKS[cur["cik"]] == ("C", MF.TEMPLATE_FINANCIAL, MF.LINE_NET_PLUS_OTHER)
    v0, l0, n0 = MF.revenue_line(cur)
    v4, l4, _ = MF.revenue_line(ya)
    assert (l0, l4, n0) == (MF.LINE_NET_PLUS_OTHER, MF.LINE_NET_PLUS_OTHER, None)
    assert (v0, v4) == (24766e6, 21668e6)


def test_NEGATIVE_C_on_another_CIK_is_the_bare_rule_without_other_income():
    cur = dict(_held("C")[0], cik="0000123456")
    v, line, note = MF.revenue_line(cur)
    assert line == MF.LINE_NET_OF_INTEREST and note is None
    assert v == 24262e6                      # 44,799 − 20,537; the 504 M of other income is not added


def test_NEGATIVE_the_net_plus_other_pick_with_no_cost_line_is_a_hole():
    cur = dict(_held("C")[0], cost_of_revenue=0.0)
    assert MF.revenue_line(cur) == (None, MF.LINE_UNDETERMINED, None)


def test_net_lines_and_words():
    assert MF.NET_LINES == (MF.LINE_NET_OF_INTEREST, MF.LINE_NET_PLUS_OTHER)
    assert MF.LINE_NET_PLUS_OTHER in MF.LINE_CODES and MF.LINE_NET_PLUS_OTHER in MF.LINE_WORDS
    assert "other income" in MF.LINE_WORDS[MF.LINE_NET_PLUS_OTHER]
    assert "other income" not in MF.LINE_WORDS[MF.LINE_NET_OF_INTEREST]


# ═════════════════════════════════════ 2. the census: CACC pick, BDC + CBSH holds
def test_CACC_lender_takes_plain_revenue_587_and_584():
    cur, ya = _cen("CACC")
    assert MF.row_template(cur) == MF.TEMPLATE_FINANCIAL
    assert MF.REVENUE_LINE_PICKS[CEN["CACC"]["cik"]] == ("CACC", MF.TEMPLATE_FINANCIAL, MF.LINE_REVENUE)
    v0, l0, n0 = MF.revenue_line(cur)
    v4, l4, _ = MF.revenue_line(ya)
    assert (l0, l4, n0) == (MF.LINE_REVENUE, MF.LINE_REVENUE, None)
    assert _near(v0, 587.4e6) and _near(v4, 583.8e6)
    assert _near(v0, CEN["CACC"]["sec"]["cur"]) and _near(v4, CEN["CACC"]["sec"]["year_ago"])


def test_NEGATIVE_CACC_without_its_pick_reads_480_net_a_line_the_10Q_does_not_print():
    cur = dict(_cen("CACC")[0], cik="0000123456")
    v, line, _ = MF.revenue_line(cur)
    assert line == MF.LINE_NET_OF_INTEREST and not _near(v, 587.4e6, tol=0.05)


@pytest.mark.parametrize("sym", ["ARCC", "FSK", "MAIN", "OBDC", "CBSH"])
def test_census_names_no_line_reproduces_are_held_with_the_note(sym):
    cur, ya = _cen(sym)
    cik = CEN[sym]["cik"]
    assert MF.REVENUE_LINE_HOLD[cik][:2] == (sym, MF.HOLD_UNVERIFIED)
    v, line, note = MF.revenue_line(cur)
    assert note == MF.NOTE_NO_MATCHING_LINE
    sec = CEN[sym]["sec"]
    # neither v1 line reproduces the 10-Q's headline at the latest quarter
    assert not _near(v, sec["cur"]) and not _near(MF._value(cur["revenue"]), sec["cur"])


def test_NEGATIVE_a_held_census_name_never_ranks_on_the_board():
    f = _doc_from_rows("CBSH", *_cen("CBSH"))
    g, chip = _chip(f, today=TODAY)
    assert g["sales_reason"] == "line_unverified" and g["sales_ranked"] is False
    assert "*" in chip.split(" · ")[0]


# ═════════════════════════════════════ 3. growth_read reads the hole per slot
def _report(fy, q, row):
    return MF.to_vx_report((fy, q), {MF.INCOME: row}, "quarterly", (MF.INCOME,))


def _with_period(row, fy, q, end):
    r = copy.deepcopy(row)
    r.update(period_end=end, fiscal_year=fy, fiscal_quarter=q)
    return r


def _doc_from_rows(sym, cur_row, ya_row, monkeypatch=None):
    """The production path: real v1 rows → to_vx_report → canslim._fetch_massive_financials
    → the research doc's fundamentals → growth_read. Q2-26 / three middle quarters
    (copies of the latest row) / Q2-25."""
    reps = [_report(2026, 2, cur_row)]
    for fy, q, end in ((2026, 1, "2026-03-31"), (2025, 4, "2025-12-31"), (2025, 3, "2025-09-30")):
        reps.append(_report(fy, q, _with_period(cur_row, fy, q, end)))
    reps.append(_report(2025, 2, ya_row))
    saved = (canslim.stocks_key, canslim._massive_financials_disabled, MF.fetch_reports)
    try:
        canslim.stocks_key = lambda: "k"
        canslim._massive_financials_disabled = False
        MF.fetch_reports = (lambda s, *, timeframe, limit, statements=(), timeout=None, key=None:
                            copy.deepcopy(reps if timeframe == "quarterly" else []))
        m = canslim._fetch_massive_financials(sym)
    finally:
        canslim.stocks_key, canslim._massive_financials_disabled, MF.fetch_reports = saved
    f = {"sales": {}, "_source": "massive", "cached_at": CACHED,
         **{k: m.get(k) for k in ("rev_growth_q_pct", "q_eps_growth_pct", "q_period_series",
                                  "q_end_series", "rev_q_series", "eps_q_series", "ni_q_series")},
         **{k: m.get(k) for k in qoq.LINE_KEYS}}
    return f


def stt_shaped_undetermined(slot: int, *, eps: bool = True) -> dict:
    """BAC's real Q2-26 / Q2-25 rows with the STT 2024-06-30 shape (cost_of_revenue 0.0)
    on the latest (slot 0) or the year-ago (slot 4) quarter — the doc the heal writes.
    `eps=False` drops the EPS leg (a sales-only card, the coverage tests' shape)."""
    cur, ya = (copy.deepcopy(r) for r in _held("BAC"))
    (cur if slot == 0 else ya)["cost_of_revenue"] = 0.0
    f = _doc_from_rows("BAC", cur, ya)
    if not eps:
        f.update(q_eps_growth_pct=None, eps_q_series=None)
    return f


@pytest.mark.parametrize("slot", [0, qoq.YOY_GAP])
def test_an_undetermined_latest_or_year_ago_slot_is_line_unverified_end_to_end(slot):
    f = stt_shaped_undetermined(slot)
    # what production writes: the newest FILED line, the hole only in the series
    assert f["rev_line"] == MF.LINE_NET_OF_INTEREST
    assert f["rev_line_series"][slot] == MF.LINE_UNDETERMINED
    assert f["rev_q_series"][slot] is None and f["rev_line_mixed"] == 0
    g, chip = _chip(f, today=TODAY)
    assert g["sales_reason"] == "line_unverified" and g["sales_ranked"] is False
    assert g["sales_line_note"] == MF.LINE_WORDS[MF.LINE_UNDETERMINED]
    assert chip.startswith("Sales line n/a · ")
    stat = R._growth_stat(g)
    assert ("sales: not ranked — " + MF.LINE_WORDS[MF.LINE_UNDETERMINED]) in stat
    assert g["legs"] == 1                                    # EPS still ranks
    assert R.coverage_class(g, bars=400, min_bars=100) == "one_leg"
    g2, _ = _chip(stt_shaped_undetermined(slot, eps=False), today=TODAY)
    assert R.coverage_class(g2, bars=400, min_bars=100) == R.REVENUE_LINE_CLASS


@pytest.mark.parametrize("slot", [0, qoq.YOY_GAP])
def test_NEGATIVE_the_hole_never_reads_as_not_filed_or_a_missing_year_ago(slot):
    g, chip = _chip(stt_shaped_undetermined(slot), today=TODAY)
    stat = R._growth_stat(g)
    assert g["sales_reason"] not in ("not_filed", "year_ago_missing")
    assert "no figure on file" not in stat and "spin-off" not in stat
    assert "not filed" not in chip and "yr-ago" not in chip


def test_NEGATIVE_an_undetermined_MIDDLE_slot_does_not_hold_the_leg():
    f = _doc_from_rows("BAC", *_held("BAC"))
    f["rev_line_series"] = list(f["rev_line_series"])
    f["rev_line_series"][2] = MF.LINE_UNDETERMINED
    g, _ = _chip(f, today=TODAY)
    assert g["sales_ranked"] is True and g["sales_reason"] is None


def test_the_undetermined_words_fit_either_slot():
    w = MF.LINE_WORDS[MF.LINE_UNDETERMINED]
    assert "this quarter" not in w and "a quarter compared" in w


# ═════════════════════════════════════ 5. audit: expected-net names, net tags only
class _Coll:
    def __init__(self, docs):
        self.docs = docs

    def find(self, q, proj=None):
        if "symbol" in q:
            return [d for d in self.docs if d["symbol"] in q["symbol"]["$in"]]
        want = q["fundamentals.rev_line"]["$in"]
        return [d for d in self.docs if (d.get("fundamentals") or {}).get("rev_line") in want]


END, YA = "2026-06-30", "2025-06-30"
TRIM = json.loads((FIX / "sec_companyfacts_trim_2026_10_08.json").read_text())


def test_expected_net_reads_the_ledger_csv():
    e = A.expected_net()
    assert e["BAC"] == (MF.LINE_NET_OF_INTEREST, "Revenues")
    assert e["JPM"] == (MF.LINE_NET_OF_INTEREST, "RevenuesNetOfInterestExpense")
    assert e["COF"] == (MF.LINE_NET_OF_INTEREST, A.SUM_TAG)
    assert e["C"] == (MF.LINE_NET_PLUS_OTHER, "Revenues")
    assert len(e) == 34
    for held in ("NU", "ALLY", "SOFI", "CVX", "MCD"):
        assert held not in e


def test_NEGATIVE_a_BAC_gross_regression_is_SELECTED_and_is_a_mismatch_with_line_drift():
    """v1 starts serving `interest_expense` on bank rows → BAC back on gross 49,393 M,
    rev_line 'revenue'. Selecting by current rev_line would never audit it."""
    docs = [{"symbol": "BAC", "fundamentals": {
        "rev_q_series": [49393e6, 1, 1, 1, 42624e6], "q_end_series": [END, 0, 0, 0, YA],
        "rev_growth_q_pct": 15.88, "rev_line": MF.LINE_REVENUE, "rev_line_note": None}}]
    coll = _Coll(docs)
    exp = A.expected_net()
    syms = A._select(coll, symbols=[], held=False, financial=True, expected=exp)
    assert "BAC" in syms
    assert A._select(coll, symbols=[], held=False, financial=True, expected={}) == []
    [row] = A.audit(["BAC"], coll=coll, cik_of=lambda s: "0000070858",
                    fetch=lambda cik: TRIM["BAC"], expected=exp)
    assert row["verdict"] == "mismatch" and row["line_drift"] is True
    assert any("not the expected net_of_interest" in s for s in A.suggestions([row]))


def test_NEGATIVE_a_brokers_gross_Revenues_tag_cannot_pass_an_expected_net_name():
    """SF: SEC `Revenues` 1,638.8 / 1,491.1 M is the GROSS v1 figure (MEASURED)."""
    gross = CEN["SF"]["sec"]["revenues_tag"]
    net = CEN["SF"]["sec"]
    pairs = {"Revenues": (gross[0], gross[1], "a"),
             "RevenuesNetOfInterestExpense": (net["cur"], net["year_ago"], "a")}
    acc = A.accept_tags("SF", MF.LINE_NET_OF_INTEREST, {})
    assert acc == A.NET_TAGS
    assert A.verdict(gross[0], gross[1], 9.91, pairs)["verdict"] == "match"        # any-tag: the trap
    assert A.verdict(gross[0], gross[1], 9.91, pairs, accept=acc)["verdict"] == "mismatch"
    v = A.verdict(net["cur"], net["year_ago"], 12.97, pairs, accept=acc)
    assert v == {"verdict": "match", "tag": "RevenuesNetOfInterestExpense", "sec_pct": 12.97}


def test_NEGATIVE_an_expected_net_name_with_only_a_non_net_tag_is_unchecked():
    pairs = {"Revenues": (1638.8e6, 1491.1e6, "a")}
    assert A.verdict(1638.8e6, 1491.1e6, 9.91, pairs, accept=A.NET_TAGS)["verdict"] == "unchecked"


def test_BAC_C_SCHW_face_tag_Revenues_still_counts_for_them():
    exp = A.expected_net()
    assert "Revenues" in A.accept_tags("BAC", MF.LINE_NET_OF_INTEREST, exp)
    assert A.accept_tags("MCD", MF.LINE_REVENUE, exp) is None
    p = A.sec_quarter_pair(TRIM["BAC"], END, YA)
    v = A.verdict(31558e6, 27443e6, 14.99, p, accept=A.accept_tags("BAC", MF.LINE_NET_OF_INTEREST, exp))
    assert v["verdict"] == "match"


def test_NEGATIVE_financial_without_the_csv_refuses_to_run(monkeypatch, tmp_path):
    import scripts.resiliency_study as RS
    monkeypatch.setattr(RS, "block_writes", lambda: None)
    assert A.main(["--financial", "--expected", str(tmp_path / "missing.csv")]) == 2
