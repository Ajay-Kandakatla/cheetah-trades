"""The revenue-line audit (durability tripwire, 2026-10-08) — hermetic.

SEC companyfacts is a TRIMMED copy of the 2026-10-07 pulls (BAC, C:
`tests/fixtures/sec_companyfacts_trim_2026_10_08.json`); the fetch is stubbed,
so no request leaves the process. The NEGATIVE that carries the file: a
companyfacts feed that lags the quarter (C) is "unchecked", never "mismatch".
"""
from __future__ import annotations

import json
import pathlib

import pytest

from scripts import revenue_line_audit as A

CF = json.loads((pathlib.Path(__file__).resolve().parent / "fixtures"
                 / "sec_companyfacts_trim_2026_10_08.json").read_text())
END, YA = "2026-06-30", "2025-06-30"


def test_bac_pair_comes_from_the_SAME_accession():
    p = A.sec_quarter_pair(CF["BAC"], END, YA)
    cur, ya, accn = p["Revenues"]
    assert (cur, ya) == (31558000000.0, 27443000000.0)
    assert accn == "0000070858-26-000394"
    # NOT the year-ago as originally filed (26,463 M in 0000070858-25-000268)
    assert ya != 26463000000.0


def test_bac_net_line_matches():
    p = A.sec_quarter_pair(CF["BAC"], END, YA)
    v = A.verdict(31558e6, 27443e6, 14.99, p)
    assert v == {"verdict": "match", "tag": "Revenues", "sec_pct": 14.99}


def test_the_NII_plus_NonII_sum_path():
    p = A.sec_quarter_pair(CF["BAC"], END, YA)
    assert p[A.SUM_TAG][:2] == (15997e6 + 15561e6, 14670e6 + 12773e6)
    only_sum = {A.SUM_TAG: p[A.SUM_TAG]}
    assert A.verdict(31558e6, 27443e6, 14.99, only_sum)["tag"] == A.SUM_TAG


def test_a_CB_like_gap_with_both_levels_in_matches_on_levels():
    pairs = {"Revenues": (15816e6, 14836e6, "x")}               # SEC 6.61 %
    v = A.verdict(15811e6, 14853e6, 6.45, pairs)                 # 0.16 pp off, levels within 0.2 %
    assert v["verdict"] == "match"


def test_NEGATIVE_gross_bank_revenue_is_a_mismatch():
    p = A.sec_quarter_pair(CF["BAC"], END, YA)
    v = A.verdict(49393e6, 42624e6, 15.88 + 3.0, p)
    assert v["verdict"] == "mismatch"


def test_NEGATIVE_a_lagging_companyfacts_is_unchecked_never_mismatch_C():
    assert A.sec_quarter_pair(CF["C"], END, YA) == {}
    for pct in (14.30, 99.0, None):
        assert A.verdict(24766e6, 21668e6, pct, {})["verdict"] == "unchecked"


def test_NEGATIVE_no_stored_figure_is_unchecked():
    p = A.sec_quarter_pair(CF["BAC"], END, YA)
    assert A.verdict(None, None, None, p)["verdict"] == "unchecked"


def test_NEGATIVE_a_six_month_fact_is_not_a_quarter():
    assert A._three_month({"start": "2026-01-01", "end": "2026-06-30"}) is False
    assert A._three_month({"start": "2026-04-01", "end": "2026-06-30"}) is True
    assert A._three_month({"start": "2026-04-27", "end": "2026-07-26"}) is True   # 52/53-week


class _Coll:
    def __init__(self, docs):
        self.docs = docs

    def find(self, q, proj=None):
        if "symbol" in q:
            return [d for d in self.docs if d["symbol"] in q["symbol"]["$in"]]
        return [d for d in self.docs if (d.get("fundamentals") or {}).get("rev_line")
                == q["fundamentals.rev_line"]]


def test_audit_end_to_end_with_stubbed_sec_and_zero_massive():
    docs = [{"symbol": "BAC", "fundamentals": {
                "rev_q_series": [31558e6, 1, 1, 1, 27443e6], "q_end_series": [END, 0, 0, 0, YA],
                "rev_growth_q_pct": 14.99, "rev_line": "net_of_interest", "rev_line_note": None}},
            {"symbol": "C", "fundamentals": {
                "rev_q_series": [24766e6, 1, 1, 1, 21668e6], "q_end_series": [END, 0, 0, 0, YA],
                "rev_growth_q_pct": 14.30, "rev_line": "net_of_interest", "rev_line_note": None}}]
    coll = _Coll(docs)
    syms = A._select(coll, symbols=[], held=False, financial=True)
    assert syms == ["BAC", "C"]
    fetched = []
    rows = A.audit(syms, coll=coll, cik_of=lambda s: {"BAC": "0000070858", "C": "0000831001"}[s],
                   fetch=lambda cik: fetched.append(cik) or CF["BAC" if cik == "0000070858" else "C"])
    got = {r["symbol"]: r["verdict"] for r in rows}
    assert got == {"BAC": "match", "C": "unchecked"}
    assert fetched == ["0000070858", "0000831001"]
    assert A.suggestions(rows) == []


def test_held_selects_every_ledger_ticker():
    from sepa import massive_fundamentals as MF
    syms = A._select(_Coll([]), symbols=["bac"], held=True, financial=False)
    assert "BAC" in syms and "SOFI" in syms and "RKT" in syms
    assert len(syms) == 1 + len(MF.REVENUE_LINE_PICKS) + len(MF.REVENUE_LINE_HOLD)


def test_main_blocks_writes_first(monkeypatch):
    import scripts.resiliency_study as RS
    from sepa import research
    calls = []
    monkeypatch.setattr(RS, "block_writes", lambda: calls.append("blocked"))
    monkeypatch.setattr(research, "_get_cache", lambda: calls.append("cache") or None)
    assert A.main(["--held"]) == 1
    assert calls == ["blocked", "cache"]


def test_tolerances_are_the_measurements_not_rules():
    assert (A.AUDIT_PCT_TOL, A.AUDIT_LEVEL_TOL) == (0.10, 0.002)
    assert A.AUDIT_EXTRA_SLEEP == 0.06
