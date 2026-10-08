"""The revenue line persists beside the revenue series (2026-10-08).

Ajay 2026-10-08, on the 141 held-out names: "update them please". The helper
(`massive_fundamentals.revenue_line`) picks each quarter's line by v1's
statement template; this file pins that the choice SURVIVES into the research
doc (`canslim` → `research.decision_snapshot`) and that the nightly `qoq`
backfill / realign move it with the series and never splice a different line.

NEGATIVES carry the file: a legacy vX-shaped report (no `revenue_line`) must be
byte-identical to before; a series that would mix two lines holes the odd slot
instead of printing a % across lines.
"""
from __future__ import annotations

import copy
import json
import pathlib

import pytest

from sepa import canslim, qoq, research
from sepa import massive_fundamentals as MF

FX = json.loads((pathlib.Path(__file__).resolve().parent / "fixtures"
                 / "revenue_line_rows_2026_10_08.json").read_text())["names"]


def _wire(monkeypatch, quarterly, annual=()):
    monkeypatch.setattr(MF, "fetch_reports",
                        lambda s, *, timeframe, limit, statements=(), timeout=None, key=None:
                        copy.deepcopy(list(quarterly) if timeframe == "quarterly" else list(annual)))
    monkeypatch.setattr(canslim, "stocks_key", lambda: "test-key")
    monkeypatch.setattr(canslim, "_massive_financials_disabled", False)


def _legacy(fy, q, end, rev, eps=1.0):
    """A vX-shaped report as before 2026-10-08 — NO `revenue_line` key."""
    return {"fiscal_year": fy, "fiscal_period": f"Q{q}", "end_date": end,
            "financials": {"income_statement": {"revenues": {"value": rev},
                                                "diluted_earnings_per_share": {"value": eps}},
                           "balance_sheet": {}}}


def _with_line(rep, line, note=None):
    r = copy.deepcopy(rep)
    r["revenue_line"], r["revenue_line_note"] = line, note
    return r


FIVE = [(2026, 2, "2026-06-30", 125.0), (2026, 1, "2026-03-31", 120.0),
        (2025, 4, "2025-12-31", 115.0), (2025, 3, "2025-09-30", 110.0),
        (2025, 2, "2025-06-30", 100.0)]


def _bac_reports():
    """BAC's real latest + year-ago rows through the helper, three synthetic
    standard-shaped quarters between (so slot 4 is the year-ago quarter)."""
    rows = {r["period_end"]: r for r in FX["BAC"]["rows"]}
    cur = MF.to_vx_report((2026, 2), {MF.INCOME: rows["2026-06-30"]}, "quarterly", (MF.INCOME,))
    ya = MF.to_vx_report((2025, 2), {MF.INCOME: rows["2025-06-30"]}, "quarterly", (MF.INCOME,))
    mid = []
    for fy, q, end in ((2026, 1, "2026-03-31"), (2025, 4, "2025-12-31"), (2025, 3, "2025-09-30")):
        r = _legacy(fy, q, end, 30e9)
        r["revenue_line"], r["revenue_line_note"] = MF.LINE_NET_OF_INTEREST, None
        mid.append(r)
    return [cur] + mid + [ya]


# ═════════════════════════════════════════════ canslim
def test_bank_series_and_pct_are_the_net_line_and_say_so(monkeypatch):
    _wire(monkeypatch, _bac_reports())
    m = canslim._fetch_massive_financials("BAC")
    assert m["rev_q_series"][0] == 31558000000.0 and m["rev_q_series"][4] == 27443000000.0
    assert m["rev_growth_q_pct"] == 14.99 == qoq.yoy_pct(m["rev_q_series"])
    assert m["rev_line"] == MF.LINE_NET_OF_INTEREST
    assert m["rev_line_series"] == [MF.LINE_NET_OF_INTEREST] * 5
    assert m["rev_line_note"] is None and m["rev_line_mixed"] == 0


def test_line_series_is_parallel_to_the_aligned_keys_a_hole_is_None(monkeypatch):
    reps = [_with_line(_legacy(*t), MF.LINE_REVENUE) for t in FIVE]
    del reps[2]                                          # FY2025 Q4 absent → hole
    _wire(monkeypatch, reps)
    m = canslim._fetch_massive_financials("X")
    assert m["q_period_series"][:5] == [8105, 8104, None, 8102, 8101]
    assert m["rev_line_series"][:5] == ["revenue", "revenue", None, "revenue", "revenue"]
    assert len(m["rev_line_series"]) == len(m["rev_q_series"]) == len(m["q_period_series"])


def test_hold_note_rides_to_the_doc(monkeypatch):
    reps = [_with_line(_legacy(*t), MF.LINE_REVENUE, MF.NOTE_NO_NII) for t in FIVE]
    _wire(monkeypatch, reps)
    m = canslim._fetch_massive_financials("SOFI")
    assert m["rev_line_note"] == MF.NOTE_NO_NII and m["rev_line"] == MF.LINE_REVENUE


@pytest.mark.parametrize("builder", ["hybrid", "massive"])
def test_both_payload_builders_carry_the_four_keys(monkeypatch, builder):
    reps = [_with_line(_legacy(*t), MF.LINE_NET_OF_INTEREST) for t in FIVE]
    _wire(monkeypatch, reps)
    monkeypatch.setattr(canslim, "_inst_ownership_yfinance", lambda s: None)
    monkeypatch.setattr(canslim, "_receivables_yfinance", lambda s: None)
    out = canslim._from_hybrid("X") if builder == "hybrid" else canslim._from_massive("X")
    for k in qoq.LINE_KEYS:
        assert k in out, k
    assert out["rev_line"] == MF.LINE_NET_OF_INTEREST and out["rev_line_mixed"] == 0
    assert tuple(canslim.REV_LINE_KEYS) == qoq.LINE_KEYS


def test_NEGATIVE_legacy_reports_are_byte_identical_and_carry_no_line(monkeypatch):
    reps = [_legacy(*t) for t in FIVE]
    _wire(monkeypatch, reps)
    m = canslim._fetch_massive_financials("OLD")
    assert m["rev_q_series"][:5] == [125.0, 120.0, 115.0, 110.0, 100.0]
    assert m["rev_growth_q_pct"] == canslim._compute_q_rev_growth(
        qoq.align_reports(reps, canslim._period_index)[0]) == 25.0
    assert m["rev_line"] is None and m["rev_line_mixed"] == 0
    assert m["rev_line_series"][:5] == [None] * 5


def test_NEGATIVE_mixed_lines_hole_the_odd_slot_and_print_no_pct(monkeypatch):
    reps = [_with_line(_legacy(*t), MF.LINE_NET_OF_INTEREST) for t in FIVE]
    reps[4]["revenue_line"] = MF.LINE_REVENUE           # year-ago on another line
    _wire(monkeypatch, reps)
    m = canslim._fetch_massive_financials("MIX")
    assert m["rev_q_series"][4] is None and m["rev_line_mixed"] == 1
    assert m["rev_growth_q_pct"] is None == qoq.yoy_pct(m["rev_q_series"])
    assert m["rev_line"] == MF.LINE_NET_OF_INTEREST     # the newest line wins


def test_NEGATIVE_newest_figure_sets_the_line_an_undetermined_hole_does_not():
    rev = [None, 5.0, 4.0, 3.0, 2.0]
    lines = [MF.LINE_UNDETERMINED, "net_of_interest", "net_of_interest", "revenue", "net_of_interest"]
    out, n, ref = canslim._one_revenue_line(rev, lines)
    assert ref == "net_of_interest" and n == 1 and out == [None, 5.0, 4.0, None, 2.0]
    assert canslim._one_revenue_line([1.0, 2.0], [None, None]) == ([1.0, 2.0], 0, None)


def test_NEGATIVE_the_yfinance_fallback_carries_no_line_keys(monkeypatch):
    monkeypatch.setattr(canslim, "_fetch_massive_financials", lambda s: None)
    monkeypatch.setattr(canslim, "_from_yfinance", lambda s: {"_source": "yfinance"})
    out = canslim._from_hybrid("YF")
    assert not any(k in out for k in qoq.LINE_KEYS)


# ═════════════════════════════════════════════ research
def test_decision_fields_and_snapshot_project_the_line(monkeypatch):
    for k in qoq.LINE_KEYS:
        assert f"fundamentals.{k}" in research.DECISION_FIELDS
    doc = {"symbol": "BAC", "cached_at": 9e9,
           "fundamentals": {"rev_line": "net_of_interest", "rev_line_series": ["net_of_interest"],
                            "rev_line_note": None, "rev_line_mixed": 0}}

    class C:
        def find(self, q, proj):
            assert all(proj.get(f"fundamentals.{k}") == 1 for k in qoq.LINE_KEYS)
            return [doc]
    monkeypatch.setattr(research, "_get_cache", lambda: C())
    snap = research.decision_snapshot(["BAC"])["BAC"]
    assert snap["rev_line"] == "net_of_interest" and snap["rev_line_series"] == ["net_of_interest"]
    assert "rev_line_note" in snap and snap["rev_line_mixed"] == 0


def test_NEGATIVE_a_legacy_doc_snapshots_None_lines(monkeypatch):
    class C:
        def find(self, q, proj):
            return [{"symbol": "OLD", "cached_at": 9e9, "fundamentals": {"rev_q_series": [1.0]}}]
    monkeypatch.setattr(research, "_get_cache", lambda: C())
    snap = research.decision_snapshot(["OLD"])["OLD"]
    assert all(snap[k] is None for k in qoq.LINE_KEYS)


# ═════════════════════════════════════════════ qoq backfill / realign
def _project(doc: dict, proj) -> dict:
    if not proj:
        return doc
    out = {"_id": doc["_id"]} if "_id" in doc else {}
    for path, on in proj.items():
        if not on:
            continue
        head, _, tail = path.partition(".")
        if head not in doc:
            continue
        if not tail:
            out[head] = doc[head]
        elif isinstance(doc[head], dict) and tail in doc[head]:
            out.setdefault(head, {})[tail] = doc[head][tail]
    return out


class FakeColl:
    def __init__(self, docs):
        self.docs = {d["symbol"]: copy.deepcopy(d) for d in docs}
        self.updates: list = []

    def find(self, q=None, proj=None):
        """Honours an inclusion projection like Mongo (critic round 2): a key the
        caller's projection leaves out is NOT read back, so a dropped
        `fundamentals.rev_line_series` in qoq.realign fails a test."""
        return [_project(copy.deepcopy(d), proj) for d in self.docs.values()]

    def update_one(self, flt, upd):
        self.updates.append((flt, upd))


REV = [1.1e9, 1, 1, 1, 1.0e9, 1]
EPS = [1.1, 1, 1, 1, 1.0, 1]
PER = [8105, 8104, 8103, 8102, 8101, 8100]


def _doc(sym, **extra):
    f = {"_source": "hybrid", "q_period_series": list(PER), "rev_q_series": list(REV),
         "eps_q_series": list(EPS), "ni_q_series": [1.0] * 6,
         "rev_growth_q_pct": 10.0, "q_eps_growth_pct": 10.0}
    f.update(extra)
    return {"symbol": sym, "cached_at": 1.0, "fundamentals": f}


def _m(**extra):
    m = {"q_period_series": list(PER), "rev_q_series": list(REV), "eps_q_series": list(EPS),
         "ni_q_series": [1.0] * 6}
    m.update(extra)
    return m


@pytest.fixture
def wire(monkeypatch):
    def _w(docs, fetched):
        coll = FakeColl(docs)
        monkeypatch.setattr(research, "_get_cache", lambda: coll)
        monkeypatch.setattr(canslim, "_fetch_massive_financials",
                            lambda s: copy.deepcopy(fetched.get(s)))
        return coll
    return _w


LINES = {"rev_line": "net_of_interest", "rev_line_series": ["net_of_interest"] * 6,
         "rev_line_note": None, "rev_line_mixed": 0}


def test_backfill_writes_the_line_keys_with_the_series(wire):
    coll = wire([_doc("BAC", rev_line="net_of_interest")], {"BAC": _m(**LINES)})
    out = qoq.backfill(["BAC"], only_missing=False, now=0.0)
    assert out["filled"] == 1
    (_, upd), = coll.updates
    s = upd["$set"]
    for k in qoq.LINE_KEYS:
        assert f"fundamentals.{k}" in s
    assert s["fundamentals.rev_line_note"] is None           # present, value None
    assert "rev_line_series" not in qoq.SERIES_KEYS


def test_NEGATIVE_backfill_refuses_a_line_change(wire):
    coll = wire([_doc("BAC", rev_line="revenue")], {"BAC": _m(**LINES)})
    out = qoq.backfill(["BAC"], only_missing=False, now=0.0)
    assert coll.updates == [] and out["skipped"] == {"rev_line_changed": 1}
    assert "fundamentals.rev_line" in qoq.BACKFILL_PROJ


def test_NEGATIVE_a_legacy_doc_without_a_line_is_not_a_line_change():
    assert qoq.backfill_skip_reason(_doc("X")["fundamentals"], _m(**LINES)) is None
    assert qoq.backfill_skip_reason(_doc("X", rev_line="revenue")["fundamentals"], _m()) is None


def test_NEGATIVE_a_stub_m_without_line_keys_writes_series_keys_only(wire):
    coll = wire([_doc("OK")], {"OK": _m()})
    qoq.backfill(["OK"], only_missing=False, now=0.0)
    (_, upd), = coll.updates
    assert set(upd["$set"]) <= ({f"fundamentals.{k}" for k in qoq.SERIES_KEYS}
                                | {f"fundamentals.{qoq.END_SERIES_KEY}"})


def test_realign_moves_the_line_series_with_the_keys(wire):
    per = [8105, 8104, 8102, 8101, 8100]                  # 8103 missing → densify
    lines = ["a", "b", "c", "d", "e"]
    d = _doc("R", q_period_series=per, rev_q_series=[5.0, 4.0, 3.0, 2.0, 1.0],
             eps_q_series=[5.0, 4.0, 3.0, 2.0, 1.0], ni_q_series=[1.0] * 5,
             rev_line_series=lines)
    coll = wire([d], {})
    out = qoq.realign(["R"])
    assert out["realigned"] == 1
    (_, upd), = coll.updates
    s = upd["$set"]
    assert s["fundamentals.q_period_series"] == [8105, 8104, None, 8102, 8101, 8100]
    assert s["fundamentals.rev_line_series"] == ["a", "b", None, "c", "d", "e"]


def test_NEGATIVE_realign_never_adds_a_line_series_to_a_doc_without_one(wire):
    per = [8105, 8104, 8102, 8101, 8100]
    d = _doc("R", q_period_series=per, rev_q_series=[5.0, 4.0, 3.0, 2.0, 1.0],
             eps_q_series=[5.0, 4.0, 3.0, 2.0, 1.0], ni_q_series=[1.0] * 5)
    coll = wire([d], {})
    qoq.realign(["R"])
    (_, upd), = coll.updates
    assert "fundamentals.rev_line_series" not in upd["$set"]


def test_NEGATIVE_realign_reads_the_line_series_through_its_projection(wire):
    """Fails if `fundamentals.rev_line_series` leaves qoq.realign's projection:
    the series would then silently stop moving with the keys."""
    per = [8105, 8104, 8102, 8101, 8100]
    d = _doc("R", q_period_series=per, rev_q_series=[5.0, 4.0, 3.0, 2.0, 1.0],
             eps_q_series=[5.0, 4.0, 3.0, 2.0, 1.0], ni_q_series=[1.0] * 5,
             rev_line_series=["a", "b", "c", "d", "e"], rev_line_note="never projected")
    coll = wire([d], {})
    assert _project(copy.deepcopy(d), {"fundamentals.q_period_series": 1}) == {
        "fundamentals": {"q_period_series": per}}
    qoq.realign(["R"])
    (_, upd), = coll.updates
    assert upd["$set"]["fundamentals.rev_line_series"] == ["a", "b", None, "c", "d", "e"]
