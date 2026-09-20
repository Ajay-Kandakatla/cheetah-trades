"""THE YoY PAIR REPAIR — densify Massive's filings by FISCAL PERIOD.

Ajay 2026-09-20, answering the his-call list: *"#2"* — repair the 164
mismatched pairs to the true year-ago quarter rather than keep holding those
rows out of the 📈 Bonde board.

THE DEFECT THESE TESTS PIN. Massive OMITS a quarter it does not have rather
than leaving a placeholder, so every consumer that reads "slot 4" gets whatever
filing happens to sit fourth. IOVA's keys are [8105,8104,8102,8101,8100,8098] —
FY Q4 is absent in BOTH years, so slot 4 was FY2025 Q1 standing in for the
year-ago quarter of FY2026 Q2, and the board printed the result as growth.

Every negative here fails on the pre-repair code. NOTHING below moves a
threshold: `sepa/sales.py` is source-guarded byte-for-byte at the bottom of
this file, and its 5 / 25 / 100 tiers are pinned beside it.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from sepa import qoq as Q
from sepa import canslim as CS
from sepa import sales as SL
from sepa import buyable_verdict as BV
from scripts import data_spine_audit as DSA


IOVA = [8105, 8104, 8102, 8101, 8100, 8098]
ADJACENT = [8106, 8105, 8104, 8103, 8102, 8101]

# NU's real key list off the live cache: three restated quarters, each filed
# twice, newest FILING first.
NU_KEYS = [8059, 8058, 8057, 8056, 8055, 8054, 8054, 8053, 8053, 8052, 8052, 8052]


def _report(fy, q, rev=None, eps=None, ni=None, inv=None):
    """A Massive /vX/reference/financials report, shaped as the live one."""
    inc, bal = {}, {}
    if rev is not None:
        inc["revenues"] = {"value": rev, "unit": "USD"}
    if eps is not None:
        inc["diluted_earnings_per_share"] = {"value": eps, "unit": "USD"}
    if ni is not None:
        inc["net_income_loss"] = {"value": ni, "unit": "USD"}
    if inv is not None:
        bal["inventory"] = {"value": inv, "unit": "USD"}
    return {"fiscal_year": fy, "fiscal_period": f"Q{q}",
            "financials": {"income_statement": inc, "balance_sheet": bal}}


# ───────────────────────────────────────────────────────── _densify
def test_densify_keeps_the_FIRST_row_for_a_restated_quarter():
    """Massive lists filings newest-FILING-first, so the first row for a
    restated quarter is the RESTATEMENT. NU files FY2024 Q2 twice — revenue
    1,892,600,000 then 1,892,590,000 — and the board must read the first."""
    slots, index_of, stats = Q._densify(NU_KEYS)
    assert slots == [8059, 8058, 8057, 8056, 8055, 8054, 8053, 8052]
    assert stats["duplicate_periods"] == 4          # 1 + 1 + 2 ignored rows
    assert stats["reordered"] is False
    assert index_of[8054] == 5 and index_of[8053] == 7 and index_of[8052] == 9

    rev = [0, 0, 0, 0, 0, 1_892_600_000, 1_892_590_000, 0, 0, 0, 0, 0]
    a = Q.align_series(NU_KEYS, rev_q_series=rev)
    assert a["rev_q_series"][5] == 1_892_600_000
    assert a["duplicate_periods"] == 4


def test_densify_puts_the_MAX_key_at_slot_0_when_the_source_is_out_of_order():
    """8 live documents come back out of filing order. Slot 0 is the latest
    reported quarter or the whole read is wrong."""
    ddog = [8104, 8105, 8103, 8102, 8101, 8100]
    slots, _, stats = Q._densify(ddog)
    assert slots[0] == 8105
    assert slots == [8105, 8104, 8103, 8102, 8101, 8100]
    assert stats["reordered"] is True


def test_densify_on_an_already_dense_list_changes_NOTHING():
    slots, _, stats = Q._densify(ADJACENT)
    assert slots == ADJACENT
    assert stats == {"duplicate_periods": 0, "reordered": False}


# ───────────────────────────────────────────────── align_reports / align_series
def test_align_reports_leaves_a_HOLE_where_the_quarter_is_missing():
    """A synthetic Massive `q_results` with FY2025 Q4 absent: the FY2025 Q2
    report must land at slot 4 under a FY2026 Q2 head, not at slot 3."""
    reports = [_report(2026, 2, rev=250), _report(2026, 1, rev=200),
               _report(2025, 3, rev=180), _report(2025, 2, rev=150),
               _report(2025, 1, rev=100)]
    aligned, dropped, stats = Q.align_reports(reports, CS._period_index)
    assert [CS._period_index(r) if r else None for r in aligned] == [
        8105, 8104, None, 8102, 8101, 8100]
    assert aligned[2] is None                       # FY2025 Q4 = 8103, absent
    assert CS._income_value(aligned[4], "revenues") == 150.0   # FY2025 Q2
    assert dropped == 0 and stats == {"duplicate_periods": 0, "reordered": False}


def test_align_series_gives_IOVA_its_real_shape_and_the_right_slot_4():
    rev = [250.0, 200.0, 180.0, 100.0, 90.0, 80.0]   # parallel to IOVA's keys
    a = Q.align_series(IOVA, rev_q_series=rev)
    assert a["q_period_series"] == [8105, 8104, None, 8102, 8101, 8100, None, 8098]
    assert a["rev_q_series"][4] == 100.0             # the 8101 value, not 90/180
    assert a["rev_q_series"][2] is None and a["rev_q_series"][6] is None
    assert a["dropped_unlabelled"] == 0


def test_the_repaired_IOVA_pair_is_ACCEPTED_and_RE_TIERED_on_the_labelled_pair():
    rev = [250.0, 200.0, 180.0, 100.0, 90.0, 80.0]
    a = Q.align_series(IOVA, rev_q_series=rev)
    assert Q.period_ok(IOVA) is False                # the raw list is still wrong
    assert Q.period_ok(a["q_period_series"]) is True
    assert Q.headline_hole(a["q_period_series"]) is False
    assert Q.prior_hole(a["q_period_series"]) is False

    raw_tier = SL.compute(CS._head8(rev))            # 250 vs 90 — the wrong base
    new_tier = SL.compute(CS._head8(a["rev_q_series"]))   # 250 vs 100 — FY2025 Q2
    assert raw_tier["growth_yoy_pct"] == 177.8
    assert new_tier["growth_yoy_pct"] == 150.0
    assert new_tier["tier"] == "explosive"


def test_NEGATIVE_an_ABSENT_year_ago_quarter_yields_NOTHING_not_a_neighbour():
    """The whole point. 8101 is missing; slot 4 must be None and the growth
    number must be absent — NEVER the 8100 or the 8102 value."""
    keys = [8105, 8104, 8103, 8102, 8100, 8099]
    rev = [250.0, 200.0, 180.0, 150.0, 90.0, 80.0]
    a = Q.align_series(keys, rev_q_series=rev)
    assert a["q_period_series"] == [8105, 8104, 8103, 8102, None, 8100, 8099]
    assert a["rev_q_series"][4] is None
    assert a["rev_q_series"][4] not in (90.0, 150.0)

    s = SL.compute(CS._head8(a["rev_q_series"]))
    assert s["growth_yoy_pct"] is None
    assert s["tier"] == "unknown" and s["score"] is None
    assert Q.period_ok(a["q_period_series"]) is False
    assert Q.headline_hole(a["q_period_series"]) is True


@pytest.mark.parametrize("keys,hole_slot,growth", [
    ([8105, 8104, 8103, 8102, 8101, 8099], 5, 150.0),   # only the prior year-ago
    ([8105, 8103, 8102, 8101, 8100, 8099], 1, 66.7),    # only the prior quarter
])
def test_a_PRIOR_hole_alone_is_NOT_held_out_and_lands_in_the_rejected_list(
        keys, hole_slot, growth):
    """REGRESSION the first draft of this repair would have caused: refusing
    every YoY-slot hole re-held-out the ~105 names whose HEADLINE pair is
    correct — the exact rows the repair exists to release."""
    rev = [250.0, 200.0, 180.0, 150.0, 100.0, 80.0]
    a = Q.align_series(keys, rev_q_series=rev)
    p = a["q_period_series"]
    assert p[hole_slot] is None
    assert Q.period_ok(p) is True
    assert Q.prior_hole(p) is True
    assert Q.headline_hole(p) is False

    s = SL.compute(CS._head8(a["rev_q_series"]))
    assert s["growth_yoy_pct"] == growth            # computed on 0 vs 4
    assert s["prior_yoy_pct"] is None
    assert s["accelerating"] is False               # never None — sales.py:69
    assert s["consecutive_growth_q"] == 1

    # Today's character clause, unchanged: a floor-clearer with no character
    # is REJECTED and visible under 🔎, not promoted and not vanished.
    pillar = BV._bonde_pillar({"fundamentals": {"sales": s}})
    assert pillar["pending"] is False
    assert pillar["passed"] is False
    assert f"< {BV.BONDE_MIN_CONSEC_Q} consecutive growth quarters" in pillar["reason"]
    assert s["growth_yoy_pct"] >= SL.SALES_FLOOR_PCT


def test_NEGATIVE_a_list_with_NO_int_key_comes_back_UNCHANGED():
    """The legacy / yfinance path stores calendar quarters positionally and
    must never be rearranged on a guess."""
    reports = [{"a": 1}, {"b": 2}]
    aligned, dropped, stats = Q.align_reports(reports, CS._period_index)
    assert aligned is reports or aligned == reports
    assert dropped == 0 and stats == {"duplicate_periods": 0, "reordered": False}

    a = Q.align_series([None, None], rev_q_series=[5.0, 4.0])
    assert a["q_period_series"] == [None, None]
    assert a["rev_q_series"] == [5.0, 4.0]
    assert a["dropped_unlabelled"] == 0
    assert Q.period_ok([None, None]) is None


def test_NEGATIVE_an_UNLABELLED_report_is_DROPPED_and_COUNTED_never_placed():
    reports = [_report(2026, 2, rev=250), {"fiscal_year": 2026, "rev": 1},
               _report(2026, 1, rev=200)]
    aligned, dropped, _ = Q.align_reports(reports, CS._period_index)
    assert dropped == 1
    assert [CS._income_value(r, "revenues") for r in aligned] == [250.0, 200.0]
    a = Q.align_series([8105, None, 8104], rev_q_series=[250.0, 999.0, 200.0])
    assert a["dropped_unlabelled"] == 1
    assert 999.0 not in a["rev_q_series"]


# ────────────────────────────────────── the five series ride the SAME alignment
def _fake_massive(monkeypatch, q_results, a_results=()):
    """`_fetch_massive_financials` against a stubbed HTTP layer — the real
    function, so the five comprehensions under test are the shipped ones."""
    class _Resp:
        def __init__(self, payload):
            self.status_code = 200
            self._p = payload

        def json(self):
            return {"results": list(self._p)}

    class _Sess:
        def get(self, url, params=None, timeout=None):
            return _Resp(q_results if params.get("timeframe") == "quarterly"
                         else a_results)

    class _Requests:
        Session = _Sess

    monkeypatch.setitem(sys.modules, "requests", _Requests)
    monkeypatch.setattr(CS, "stocks_key", lambda: "test-key")
    monkeypatch.setattr(CS, "_massive_financials_disabled", False)
    return CS._fetch_massive_financials("TEST")


def test_EVERY_series_including_inv_reads_the_ALIGNED_reports(monkeypatch):
    """`inv_q_series` is read POSITIONALLY by `earnings_quality.compute`, so a
    hole that lands in the other four and not in it would silently pair a
    quarter's inventory with a different quarter's revenue."""
    q = [_report(2026, 2, rev=250, eps=2.5, ni=25, inv=50),
         _report(2026, 1, rev=200, eps=2.0, ni=20, inv=40),
         _report(2025, 3, rev=180, eps=1.8, ni=18, inv=30),   # FY2025 Q4 absent
         _report(2025, 2, rev=150, eps=1.5, ni=15, inv=25),
         _report(2025, 1, rev=100, eps=1.0, ni=10, inv=20)]
    m = _fake_massive(monkeypatch, q)
    assert m["q_period_series"] == [8105, 8104, None, 8102, 8101, 8100]
    for key in ("rev_q_series", "eps_q_series", "ni_q_series", "inv_q_series"):
        assert m[key][2] is None, key
    assert m["inv_q_series"] == [50.0, 40.0, None, 30.0, 25.0, 20.0]
    assert m["rev_q_series"][4] == 150.0            # FY2025 Q2, the year-ago Q
    # THE REPAIR, visible as a number: raw slot 4 was the FY2025 Q1 report
    # (rev 100) and the board printed +150.0%. The year-ago quarter is FY2025
    # Q2 (rev 150), so the true figure is +66.67%.
    assert m["rev_growth_q_pct"] == 66.67
    assert m["q_eps_growth_pct"] == round((2.5 - 1.5) / 1.5 * 100, 2)
    assert m["unlabelled_dropped"] == 0
    assert m["duplicate_periods"] == 0 and m["reordered"] is False


def test_the_massive_path_reports_what_the_alignment_had_to_do(monkeypatch):
    q = [_report(2026, 1, rev=200), _report(2026, 2, rev=250),
         _report(2026, 2, rev=249), {"fiscal_year": 2026}]
    m = _fake_massive(monkeypatch, q)
    assert m["q_period_series"] == [8105, 8104]
    assert m["rev_q_series"] == [250.0, 200.0]      # the FIRST 8105 row wins
    assert m["reordered"] is True
    assert m["duplicate_periods"] == 1
    assert m["unlabelled_dropped"] == 1


# ────────────────────────────────────────────────────────────── yoy_pct
def _former_canslim_arithmetic(series):
    """canslim._compute_q_eps_growth as it read before 2026-09-20."""
    if len(series) < 5:
        return None
    a, b = series[0], series[4]
    if a is None or b is None or b == 0:
        return None
    return round((a - b) / abs(b) * 100, 2)


@pytest.mark.parametrize("series", [
    [2.5, 0, 0, 0, 1.5],
    [-0.05, 0, 0, 0, -0.50],        # NEGATIVE base — |b|, never a sign flip
    [1.0, 0, 0, 0, 0.0],            # zero base → None, never a division
])
def test_yoy_pct_matches_canslims_former_arithmetic_exactly(series):
    assert Q.yoy_pct(series) == _former_canslim_arithmetic(series)


def test_yoy_pct_refuses_a_short_list_and_a_hole():
    assert Q.yoy_pct([1.0, 2.0, 3.0, 4.0]) is None
    assert Q.yoy_pct([1.0, 0, 0, 0, None]) is None
    assert Q.yoy_pct([None, 0, 0, 0, 1.0]) is None


def test_NEGATIVE_a_densified_HOLE_never_crashes_the_value_readers():
    assert CS._income_value(None, "revenues") is None
    assert CS._income_value(None, "diluted_earnings_per_share") is None
    assert CS._balance_value(None, "inventory") is None
    assert CS._period_index(None) is None


# ─────────────────────────────────────────────────────────────── realign
class _FakeColl:
    def __init__(self, docs):
        self._docs = docs
        self.writes = []

    def find(self, q, proj=None):
        return [dict(d) for d in self._docs]

    def update_one(self, flt, update):
        self.writes.append((flt, update))


@pytest.fixture
def cache(monkeypatch):
    def _install(docs):
        from sepa import research
        coll = _FakeColl(docs)
        monkeypatch.setattr(research, "_get_cache", lambda: coll)
        return coll
    return _install


def _doc(symbol, periods, rev, *, tier="unknown"):
    return {"symbol": symbol, "cached_at": 111.0,
            "fundamentals": {"q_period_series": periods, "rev_q_series": rev,
                             "eps_q_series": [None] * len(rev),
                             "ni_q_series": [None] * len(rev),
                             "sales": {"tier": tier}}}


def test_realign_DRY_RUN_writes_nothing_and_returns_the_retier_table(cache):
    coll = cache([_doc("IOVA", IOVA, [250.0, 200.0, 180.0, 100.0, 90.0, 80.0])])
    out = Q.realign(dry_run=True)
    assert coll.writes == []
    assert out["dry_run"] is True
    assert out["keyed"] == 1 and out["realigned"] == 1
    assert out["retier"] == {"unknown→explosive": 1}
    assert out["headline_hole"] == 0 and out["prior_hole"] == 0


def test_realign_NEVER_touches_cached_at_and_NEVER_recomputes_earnings_quality(cache):
    coll = cache([_doc("IOVA", IOVA, [250.0, 200.0, 180.0, 100.0, 90.0, 80.0])])
    out = Q.realign()
    assert out["realigned"] == 1 and len(coll.writes) == 1
    sets = coll.writes[0][1]["$set"]
    assert "cached_at" not in sets and "fundamentals.cached_at" not in sets
    assert not any("earnings_quality" in k for k in sets)
    assert sets["fundamentals.q_period_series"] == [
        8105, 8104, None, 8102, 8101, 8100, None, 8098]
    assert sets["fundamentals.sales"]["growth_yoy_pct"] == 150.0
    assert sets["fundamentals.headline_hole"] is False
    assert sets["fundamentals.prior_hole"] is False
    assert "fundamentals.realigned_at" in sets


def test_realign_counts_a_HEADLINE_hole_and_a_PRIOR_hole_SEPARATELY(cache):
    """Never one `year_ago_hole` number: the first is pending and off the
    board, the second is released and judged by the character clause."""
    cache([
        _doc("HEAD", [8105, 8104, 8103, 8102, 8100, 8099],
             [250.0, 200.0, 180.0, 150.0, 90.0, 80.0]),
        _doc("PRIOR", [8105, 8104, 8103, 8102, 8101, 8099],
             [250.0, 200.0, 180.0, 150.0, 100.0, 80.0]),
    ])
    out = Q.realign(dry_run=True)
    assert out["headline_hole"] == 1
    assert out["prior_hole"] == 1


def test_NEGATIVE_realign_skips_an_UNKEYED_document_entirely(cache):
    coll = cache([_doc("LEGACY", None, [1.0, 2.0]),
                  _doc("ALSO", [None, None], [1.0, 2.0])])
    out = Q.realign()
    assert out["keyed"] == 0 and out["realigned"] == 0 and coll.writes == []


# ───────────────────────────────────────────────────────── repair_outcome
def _rdoc(symbol, periods, rev, tier="unknown"):
    return {"symbol": symbol,
            "fundamentals": {"q_period_series": periods, "rev_q_series": rev,
                             "eps_q_series": [None] * len(rev or []),
                             "sales": {"tier": tier}}}


SIX_DOCS = [
    _rdoc("IOVA", IOVA, [250.0, 200.0, 180.0, 100.0, 90.0, 80.0]),
    _rdoc("ADJ", ADJACENT, [200.0, 190.0, 180.0, 170.0, 100.0, 95.0]),
    _rdoc("HEAD", [8105, 8104, 8103, 8102, 8100, 8099],
          [250.0, 200.0, 180.0, 150.0, 90.0, 80.0]),
    _rdoc("PRIOR", [8105, 8104, 8103, 8102, 8101, 8099],
          [250.0, 200.0, 180.0, 150.0, 100.0, 80.0]),
    _rdoc("NU", NU_KEYS,
          [120.0, 118.0, 116.0, 114.0, 100.0, 90.0, 89.0, 88.0, 87.0, 86.0,
           85.0, 84.0]),
    _rdoc("UNKEYED", None, [1.0, 2.0]),
]


def test_repair_outcome_says_where_every_row_LANDS_after_the_heal():
    r = DSA.repair_outcome(SIX_DOCS)
    assert r["mismatched_before"] == 3           # IOVA + HEAD + PRIOR
    assert r["headline_hole"] == 1 and r["symbols_headline_hole"] == ["HEAD"]
    assert r["prior_hole"] == 1 and r["symbols_prior_hole"] == ["PRIOR"]
    assert r["duplicate_periods"] == 1           # NU, counted once per DOC
    assert r["reordered"] == 0
    assert r["unverifiable"] == 1                # UNKEYED
    assert r["still_held_out"] == 0              # a headline hole is PENDING
    assert sum(r["placement_after"].values()) == 5
    assert r["placement_after"]["out_pending"] == 1        # HEAD
    assert r["placement_after"]["rejected_character"] == 1  # PRIOR
    assert r["placement_after"]["tiered"] == 3
    assert sum(r["retier_after"].values()) == 5


def test_repair_outcome_places_the_PRIOR_hole_row_through_the_REAL_clause():
    """It clears Bonde's 5% floor — 150% YoY — and fails only on character,
    which is exactly the visible 🔎 cohort, not a silent drop."""
    r = DSA.repair_outcome([SIX_DOCS[3]])
    assert r["placement_after"] == {"tiered": 0, "rejected_character": 1,
                                    "out_pending": 0, "out_floor": 0}
    assert r["retier_after"] == {"explosive": 1}


def test_NEGATIVE_repair_outcome_counts_an_unkeyed_doc_and_places_it_NOWHERE():
    r = DSA.repair_outcome([SIX_DOCS[5]])
    assert r["unverifiable"] == 1
    assert sum(r["placement_after"].values()) == 0
    assert r["retier_after"] == {}


# ───────────────────────────────────────────────────────── source guards
def test_the_E1_monkeypatch_of__adjacent_STILL_bites_through_yoy_pairs_ok(monkeypatch):
    """`period_ok` must call the MODULE-GLOBAL `_adjacent`, not a captured
    reference — the 🚀 growth board's E1 test depends on it."""
    monkeypatch.setattr(Q, "_adjacent", lambda *a, **k: False)
    assert Q.yoy_pairs_ok(ADJACENT) is False
    assert Q.period_ok(ADJACENT) is False


def test_SOURCE_GUARD_sepa_sales_py_is_BYTE_IDENTICAL_to_HEAD():
    """The repair relabels quarters. It does not touch Bonde's numbers, and
    this is the guard that says so out loud (Rule #4)."""
    root = Path(__file__).resolve().parents[2]
    head = subprocess.run(["git", "show", "HEAD:backend/sepa/sales.py"],
                          cwd=str(root), capture_output=True)
    assert head.returncode == 0, head.stderr.decode()[:400]
    assert (root / "backend" / "sepa" / "sales.py").read_bytes() == head.stdout


def test_SOURCE_GUARD_the_bonde_thresholds_are_unmoved():
    assert (SL.SALES_FLOOR_PCT, SL.SALES_PREFERRED_PCT,
            SL.SALES_EXPLOSIVE_PCT) == (5.0, 25.0, 100.0)


# ── trailing blanks vs a KNOWN hole (the one red test the workflow left) ─────
def test_a_TRAILING_run_of_Nones_is_UNVERIFIABLE_not_a_known_hole():
    """The 2026-09-14 growth-board pin (E1: "a legacy row with no period keys
    is accepted, not blanked") and the 2026-09-20 repair must both hold. A
    slot-4 None is a KNOWN hole only when a filed quarter exists beyond it —
    the shape `align_reports` produces. Nothing filed beyond → the row cannot
    be checked → None, never False."""
    import sepa.qoq as Q
    legacy = [8105, None, None, None, None, None]
    assert Q.period_ok(legacy) is None
    assert Q.headline_hole(legacy) is False
    assert Q.prior_hole(legacy) is False
    assert Q.yoy_pairs_ok(legacy) is True          # accept-by-default kept
    assert Q.yoy_pairs_verifiable(legacy) is False


def test_NEGATIVE_a_slot_4_None_WITH_a_filed_quarter_beyond_it_is_STILL_a_hole():
    """The densified IOVA-class shape: 8101 is filed past the hole, so the
    year-ago quarter is genuinely absent and the row is refused."""
    import sepa.qoq as Q
    assert Q.period_ok([8106, 8105, 8104, 8103, None, 8101]) is False
    assert Q.headline_hole([8106, 8105, 8104, 8103, None, 8101]) is True
    # …and the same list densified never changes the answer.
    dense, _, _ = Q._densify([8106, 8105, 8104, 8103, 8101])
    assert dense[4] is None and Q.period_ok(dense) is False


def test_NEGATIVE_densify_can_never_emit_the_trailing_None_shape():
    """The reason the narrow reading is behaviour-identical on aligned data:
    the last slot of a densified list is always the oldest KEY."""
    import sepa.qoq as Q
    for keys in ([8105], [8105, 8104, 8103, 8102, 8100, 8099], [8106, 8101]):
        dense, _, _ = Q._densify(keys)
        assert dense[-1] is not None

