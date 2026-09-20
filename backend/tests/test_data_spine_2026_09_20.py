"""THE DATA SPINE — 📈 Bonde and 🚀 Explosive Growth off ONE quarterly series.

Ajay 2026-09-20: *"Especially this in Bondes. I think bondes and explosive
growth are hand in hand."*

THE DEFECT THESE TESTS PIN, measured on the live board 2026-09-20: 164 of 1,051
Bonde passers (15.6% — 13 explosive, 56 strong, 95 steady) carried a YoY pair
that is NOT four fiscal quarters apart, and the 🚀 growth board has REFUSED
exactly those rows since 2026-09-14. IOVA's keys are
[8105,8104,8102,8101,8100,8098]: FY Q4 is missing in both years, so slot 4 is
FY2025 Q1 standing in for the year-ago quarter of FY2026 Q2. Same filed quarter,
"explosive" on one board and "refused" on the other.

Every negative here fails on the OLD code. Nothing below moves a threshold: the
5 / 25 / 100 tiers, sales.py, canslim.py and buyable_verdict.py are untouched.
"""
from __future__ import annotations

import pytest

from sepa import qoq as Q
from sepa import bonde as BD
from growth import tracker as T
from rotation import hottest as H


# IOVA's real period keys off the live scan, 2026-09-20. 8103 (FY2025 Q4) and
# 8099 (FY2024 Q4) are simply absent from Massive's quarterly rows.
IOVA = [8105, 8104, 8102, 8101, 8100, 8098]
ADJACENT = [8106, 8105, 8104, 8103, 8102, 8101]


# ─────────────────────────────────────────────── the guard, in its one home
def test_a_pair_four_quarters_apart_passes_and_IOVAs_does_not():
    assert Q.yoy_pairs_ok(ADJACENT) is True
    assert Q.yoy_pairs_ok(IOVA) is False


def test_NEGATIVE_unverifiable_pairs_are_ACCEPTED_by_yoy_pairs_ok():
    """Inherited from `_adjacent` ON PURPOSE — refusing every legacy row would
    blank the board rather than improve it. This is exactly why `yoy_pairs_ok`
    must never be printed as a tick; `period_ok` is the tri-state."""
    assert Q.yoy_pairs_ok(None) is True
    assert Q.yoy_pairs_ok([]) is True
    assert Q.yoy_pairs_ok([8105, None, 8103, 8102, 8101, 8100]) is True
    assert Q.yoy_pairs_ok(["x", "y", "z", "a", "b", "c"]) is True
    assert Q.yoy_pairs_ok([8105, 8104]) is True          # too short to check


def test_yoy_pairs_verifiable_is_the_INVERSE_of_that_accept_branch():
    """PIN MOVED DELIBERATELY 2026-09-20 (the YoY repair): a hole in the PRIOR
    pair no longer makes a row unverifiable. The HEADLINE pair is what the
    growth claim rests on and it is checkable in both lists below — refusing
    them re-held-out the ~105 names the repair exists to release."""
    assert Q.yoy_pairs_verifiable(ADJACENT) is True
    assert Q.yoy_pairs_verifiable(IOVA) is True          # checkable AND wrong
    assert Q.yoy_pairs_verifiable(None) is False
    assert Q.yoy_pairs_verifiable([]) is False
    assert Q.yoy_pairs_verifiable([8105, None, 8103, 8102, 8101, 8100]) is True
    assert Q.yoy_pairs_verifiable([8105, 8104, 8103, 8102, 8101]) is True   # no slot 5
    assert Q.yoy_pairs_verifiable(["a", "b", "c", "d", "e", "f"]) is False
    assert Q.yoy_pairs_verifiable([8105, 8104, 8103, 8102]) is False  # too short


def test_period_ok_is_a_TRI_STATE_and_None_is_never_a_tick():
    """352 of 2,078 live scan rows have no period keys. A surface that renders
    `!period_ok` as a warning would flag every one of them, and a surface that
    renders `period_ok` as a tick would claim a check nobody made.

    PIN MOVED DELIBERATELY 2026-09-20: the slot-1 hole below is a PRIOR hole —
    the headline pair 8105 vs 8101 is four apart, so the row reads True with
    `prior_hole` True, not None."""
    assert Q.period_ok(ADJACENT) is True
    assert Q.period_ok(IOVA) is False
    assert Q.period_ok(None) is None
    assert Q.period_ok([8105, None, 8103, 8102, 8101, 8100]) is True
    assert Q.prior_hole([8105, None, 8103, 8102, 8101, 8100]) is True
    assert Q.headline_hole([8105, None, 8103, 8102, 8101, 8100]) is False
    # NEW beside them — a HEADLINE hole is a refusal, and a short list is
    # still unverifiable rather than either answer.
    assert Q.period_ok([8105, 8104, 8103, 8102, None, 8100]) is False
    assert Q.headline_hole([8105, 8104, 8103, 8102, None, 8100]) is True
    assert Q.period_ok([8105, 8104, 8103, 8102]) is None


def test_period_label_prints_FISCAL_for_massive_and_CALENDAR_for_yfinance():
    assert Q.period_label(8105) == "FY2026 Q2"
    assert Q.period_label(8105, "yfinance") == "Q2 2026"
    assert Q.period_label(8104) == "FY2026 Q1"
    assert Q.period_label(None) is None
    assert Q.period_label("nope") is None


# ─────────────────────────────────────────── the growth board re-exports it
def test_the_growth_board_and_the_spine_share_ONE_set_of_pairs():
    """Not equal values — the SAME objects. A pair typed twice is a pair that
    drifts, and this one decides what both boards refuse."""
    assert T.HEADLINE_PAIR is Q.HEADLINE_PAIR
    assert T.PRIOR_PAIR is Q.PRIOR_PAIR
    assert T.YOY_GAP is Q.YOY_GAP
    assert T.period_label is Q.period_label


def test_the_E1_monkeypatch_still_BITES_through_yoy_pairs_ok(monkeypatch):
    """`growth/tracker` no longer calls `_adjacent` itself. The existing E1
    test patches `sepa.qoq._adjacent`, so `yoy_pairs_ok` must call the
    MODULE-GLOBAL name rather than a captured reference."""
    monkeypatch.setattr(Q, "_adjacent", lambda *a, **k: False)
    assert Q.yoy_pairs_ok(ADJACENT) is False
    assert T.qualifies({"q_period_series": ADJACENT})[1]["period_mismatch"] is True


def test_the_growth_board_refuses_IOVAs_pair_exactly_as_before():
    ok, legs = T.qualifies({
        "q_period_series": IOVA,
        "sales": {"growth_yoy_pct": 300.0, "prior_yoy_pct": 120.0},
        "q_eps_growth_pct": 300.0,
    })
    assert legs["period_mismatch"] is True
    assert ok is False
    ok2, legs2 = T.qualifies({
        "q_period_series": ADJACENT,
        "sales": {"growth_yoy_pct": 300.0, "prior_yoy_pct": 120.0},
        "q_eps_growth_pct": 300.0,
    })
    assert legs2["period_mismatch"] is False and ok2 is True


# ─────────────────────────────────────────────────────── the Bonde board
def _row(symbol, periods, *, tier="explosive", growth=131.2, score=90,
         accel=True, consec=4, source=None):
    f = {
        "rev_q_series": [213_475_000, 0, 0, 0, 5_546_000],
        "q_period_series": periods,
        "sales": {"tier": tier, "growth_yoy_pct": growth, "score": score,
                  "accelerating": accel, "consecutive_growth_q": consec,
                  "prior_yoy_pct": 60.0},
    }
    if source is not None:
        f["_source"] = source
    return {"symbol": symbol, "name": symbol, "last_close": 10.0,
            "fundamentals": f}


@pytest.fixture
def board(monkeypatch):
    """`board()` off an injected scan, with every side effect stubbed."""
    def _build(rows, pivots=None):
        from sepa import scanner, first_seen as FS
        monkeypatch.setattr(scanner, "load_latest",
                            lambda: {"all_results": rows, "finished_at": 1})
        monkeypatch.setattr(BD, "_pivots", lambda: dict(pivots or {}))
        monkeypatch.setattr(BD, "regime_state", lambda: {})
        monkeypatch.setattr(FS, "record", lambda *a, **k: None)
        monkeypatch.setattr(FS, "newly_found", lambda *a, **k: set())
        monkeypatch.setattr(FS, "first_seen_map", lambda *a, **k: {})
        return BD.board()
    return _build


def test_a_MISMATCHED_passer_is_held_out_of_every_tier_and_LISTED(board):
    """The shipped default. On the old code IOVA sat in `explosive` while the
    🚀 board refused it off the same filed quarter."""
    b = board([_row("IOVA", IOVA)])
    assert b["counts"]["explosive"] == 0
    assert all(not v for k, v in b["sections"].items())
    assert b["n_period_mismatch"] == 1
    assert b["period_mismatch_symbols"] == [
        {"symbol": "IOVA", "tier": "explosive",
         "latest": "FY2026 Q2", "year_ago": "FY2025 Q1",
         "cohort": BD.COHORT_PASSER}]
    assert b["n_period_mismatch_pass"] == 1
    assert b["n_period_mismatch_rejected"] == 0
    assert "held OUT of the tiers" in b["note"]
    assert b["n_pass"] == 1          # his screen's fire rate is UNCHANGED
    assert b["n_tiered"] == 0        # what is actually shown is not


def test_the_SAME_row_on_adjacent_periods_is_tiered_normally(board):
    b = board([_row("IOVA", ADJACENT)])
    assert [r["symbol"] for r in b["sections"]["explosive"]] == ["IOVA"]
    assert b["n_period_mismatch"] == 0
    assert b["n_tiered"] == 1
    assert "held OUT of the tiers" not in b["note"]


def test_a_row_with_NO_period_keys_is_still_tiered_and_says_unverified(board):
    """352 of 2,078 live scan rows. Blanking them would delete the board."""
    b = board([_row("LEGACY", None)])
    row = b["sections"]["explosive"][0]
    assert row["period_ok"] is None and row["period"] is None
    assert b["n_period_mismatch"] == 0


def test_every_row_carries_the_period_and_the_tri_state(board):
    b = board([_row("GOOD", ADJACENT)])
    row = b["sections"]["explosive"][0]
    assert row["period"] == "FY2026 Q3"
    assert row["period_ok"] is True


def test_a_yfinance_row_prints_a_CALENDAR_quarter(board):
    b = board([_row("YF", ADJACENT, source="yfinance")])
    assert b["sections"]["explosive"][0]["period"] == "Q3 2026"


def test_a_mismatched_EPISODIC_PIVOT_stays_in_pivot_with_the_CLAIM_blanked(board):
    """The EP is a gap on volume — true whatever the quarterly series says. The
    growth CLAIM is what is withheld (spec §7.13: holding it out entirely is
    the alternative, his call)."""
    piv = {"IOVA": {"generated_at": None, "trigger": 5.0, "stop": 4.0,
                    "meta": {"gap_pct": 12.0, "vol_mult": 6.0}}}
    b = board([_row("IOVA", IOVA)], pivots=piv)
    pv = b["sections"]["pivot"]
    assert [r["symbol"] for r in pv] == ["IOVA"]
    assert pv[0]["tier"] is None
    assert pv[0]["growth_yoy_pct"] is None
    assert pv[0]["prior_yoy_pct"] is None
    assert pv[0]["accelerating"] is None
    assert pv[0]["period_ok"] is False
    assert pv[0]["pivot"]["gap_pct"] == 12.0      # the EVENT survives intact
    assert b["counts"]["explosive"] == 0
    assert b["n_period_mismatch"] == 1


def test_NEGATIVE_a_mismatched_FLOOR_CLEARER_is_not_in_the_rejected_section(board):
    """A name cannot be 'rejected for character' off a pair that is not a year
    apart either — the rejected section is guarded the same way."""
    r = _row("MISM", IOVA, tier="steady", growth=8.0, accel=False, consec=1)
    b = board([r])
    assert b["sections"]["rejected"] == []
    assert b["n_rejected"] == 0
    assert b["n_period_mismatch"] == 1
    ok = _row("FINE", ADJACENT, tier="steady", growth=8.0, accel=False, consec=1)
    b2 = board([ok])
    assert [x["symbol"] for x in b2["sections"]["rejected"]] == ["FINE"]


def test_the_note_keeps_its_opening_sentence_and_only_APPENDS(board):
    assert BD.note(1051, 2076, {"pivot": 12}).startswith("MEASURED")
    assert BD.pair_guard_note(0) == ""
    assert "164 passers are held OUT" in BD.pair_guard_note(164)
    assert "growth board refuses the same rows" in BD.pair_guard_note(164)


# ───────────────────────────────── the held-out sentence counts two cohorts
def test_NEGATIVE_a_mismatched_FLOOR_CLEARER_is_never_called_a_passer(board):
    """It FAILED his screen (character clause) — it is held out of 🔎, not of a
    tier. Counting it in the sentence's "N passers" would quote his screen's
    fire rate as larger than it is. Fails on the pre-refix code, which passed
    `len(held_out)` straight into the passer slot."""
    r = _row("MISM", IOVA, tier="steady", growth=8.0, accel=False, consec=1)
    b = board([r])
    assert b["n_period_mismatch"] == 1          # the LIST is still 1 long
    assert b["n_period_mismatch_pass"] == 0     # but no passer was held out
    assert b["n_period_mismatch_rejected"] == 1
    assert b["period_mismatch_symbols"][0]["cohort"] == BD.COHORT_FLOOR_CLEARER
    assert "1 passers are held OUT" not in b["note"]
    assert "failed the character clause" in b["note"]


def test_a_MIXED_hold_out_names_both_cohorts_and_the_totals_add_up(board):
    piv = _row("IOVA", IOVA)                              # passer, mismatched
    clr = _row("MISM", IOVA, tier="steady", growth=8.0, accel=False, consec=1)
    b = board([piv, clr])
    assert b["n_period_mismatch"] == 2
    assert b["n_period_mismatch_pass"] == 1
    assert b["n_period_mismatch_rejected"] == 1
    assert (b["n_period_mismatch_pass"] + b["n_period_mismatch_rejected"]
            == len(b["period_mismatch_symbols"]))
    assert "2 rows are held OUT" in b["note"]
    assert "1 that PASS his sales screen" in b["note"]
    assert "1 that cleared his 5% floor" in b["note"]
    assert b["n_pass"] == 1          # his screen's fire rate, unchanged


def test_pair_guard_note_is_BYTE_IDENTICAL_when_every_held_out_row_passed():
    """The one-cohort sentence must not move — it is what the board served
    before the split, and 164/164 is the live shape."""
    assert BD.pair_guard_note(164, 164) == BD.pair_guard_note(164)
    assert BD.pair_guard_note(164, None) == BD.pair_guard_note(164)
    assert BD.pair_guard_note(0, 0) == ""


def test_NEGATIVE_pair_guard_note_splits_the_count_when_they_differ():
    t = BD.pair_guard_note(164, 100)
    assert "164 rows are held OUT" in t
    assert "100 that PASS his sales screen" in t
    assert "64 that cleared his 5% floor" in t
    assert "passers are held OUT" not in t
    assert "growth board refuses the same rows" in t


def test_NEGATIVE_the_pivot_sort_never_reads_a_blanked_tier():
    """The pivot section now carries rows with `tier: None`, so `_pivot_key`
    must not touch tier or growth_yoy_pct."""
    r = {"symbol": "IOVA", "tier": None, "growth_yoy_pct": None,
         "pivot": {"hours_ago": 3.0, "gap_pct": 12.0}}
    assert BD._pivot_key(r) == (3.0, -12.0, "IOVA")


# ────────────────────────────────────────────────── the 🔥 Hottest row
def test_hottest_blanks_every_yoy_leg_on_a_mismatched_pair():
    """Those legs are handed to the sector day-tag model as FACTS
    (rotation/sector_news_tags.py:145). A None key is dropped there, so
    blanking here removes them from the prompt automatically."""
    f = {"q_period_series": IOVA, "_source": "massive",
         "rev_growth_q_pct": 131.2, "q_eps_growth_pct": 210.0,
         "sales": {"tier": "explosive", "growth_yoy_pct": 131.2,
                   "prior_yoy_pct": 60.0, "accelerating": True}}
    row = H._fundamentals_row("IOVA", f, {})
    assert row["period_mismatch"] is True
    assert row["period_ok"] is False
    assert row["sales_yoy"] is None
    assert row["sales_prior_yoy"] is None
    assert row["q_eps_yoy"] is None
    assert row["sales_accelerating"] is None
    assert row["sales_tier"] == "explosive"     # the tier is not a YoY leg


def test_hottest_reads_the_SPINES_number_not_canslims_parallel_one():
    f = {"q_period_series": ADJACENT, "_source": "massive",
         "rev_growth_q_pct": 131.24, "q_eps_growth_pct": 210.0,
         "sales": {"tier": "explosive", "growth_yoy_pct": 131.2}}
    row = H._fundamentals_row("X", f, {})
    assert row["sales_yoy"] == 131.2
    assert row["sales_yoy_source"] == "sales"
    assert row["fund_source"] == "massive"
    assert row["period"] == "FY2026 Q3" and row["period_ok"] is True


def test_a_YFINANCE_row_keeps_its_number_and_says_where_it_came_from():
    """`sales.compute([], eps)` returns tier 'unknown' with no growth_yoy_pct,
    but `rev_growth_q_pct` IS filled from Yahoo — blanking it would delete the
    number from every yfinance-sourced row."""
    f = {"q_period_series": ADJACENT, "_source": "yfinance",
         "rev_growth_q_pct": 42.5, "sales": {"tier": "unknown"}}
    row = H._fundamentals_row("YF", f, {})
    assert row["sales_yoy"] == 42.5
    assert row["sales_yoy_source"] == "yfinance"
    assert row["period"] == "Q3 2026"        # CALENDAR, never FY2026 Q3


def test_a_LEGACY_row_without_a_source_is_labelled_legacy_not_guessed():
    f = {"q_period_series": ADJACENT, "rev_growth_q_pct": 12.0, "sales": {}}
    row = H._fundamentals_row("OLD", f, {})
    assert row["sales_yoy"] == 12.0
    assert row["sales_yoy_source"] == "legacy"
    assert row["fund_source"] is None


def test_NEGATIVE_hottest_on_an_unverifiable_row_flags_nothing():
    f = {"rev_growth_q_pct": 12.0, "sales": {"growth_yoy_pct": 12.0}}
    row = H._fundamentals_row("NOKEYS", f, {})
    assert row["period_ok"] is None
    assert row["period_mismatch"] is False
    assert row["sales_yoy"] == 12.0


# ────────────────────────────────────── research snapshot carries _source
def test_decision_snapshot_projects_the_SOURCE(monkeypatch):
    """Without it the served path cannot tell Massive from yfinance, so
    `period_label` printed 'FY2026 Q2' for a CALENDAR Q2 — a year off on an
    NVDA-class fiscal year."""
    from sepa import research as R

    class Coll:
        def find(self, q, proj):
            assert "fundamentals._source" in proj
            return [{"symbol": "YF", "cached_at": 1.0,
                     "fundamentals": {"_source": "yfinance",
                                      "sales": {"tier": "unknown"},
                                      "q_period_series": ADJACENT}}]
    monkeypatch.setattr(R, "_get_cache", lambda: Coll())
    snap = R.decision_snapshot(["YF"], max_age_sec=10 ** 9)
    assert snap["YF"]["_source"] == "yfinance"
    assert "fundamentals._source" in R.DECISION_FIELDS


# ───────────────────────────────────────── the earnings-surprise 100x bug
def _fake_history(value):
    class DF:
        empty = False
        columns = ["surprisePercent"]

        class _ILoc:
            def __getitem__(self, i):
                return {"surprisePercent": value}
        iloc = _ILoc()
    return DF()


def _surprise(monkeypatch, value):
    from sepa import catalyst as C

    class T2:
        earnings_history = _fake_history(value)
        recommendations = None
    monkeypatch.setattr(C.symbols, "yf_ticker", lambda s: T2())
    return C._fetch_yfinance_extras("NVDA")["last_surprise_pct"]


def test_the_surprise_FRACTION_is_converted_to_the_apps_percent_unit(monkeypatch):
    """Measured on the live container 2026-09-20: yfinance
    `earnings_history.surprisePercent` is a FRACTION (NVDA 0.0616) while the
    sibling path already in this app, `earnings_watch._fetch_next` off
    `get_earnings_dates` "Surprise(%)", is a PERCENT (6.16). The ticker page
    printed "+0.1%" for a 6.2% beat."""
    assert _surprise(monkeypatch, 0.0616) == 6.16
    assert _surprise(monkeypatch, 0.1843) == 18.43


def test_NEGATIVE_a_NaN_surprise_is_None_not_a_float(monkeypatch):
    """NaN passed the old `is not None` test and sailed through as a float."""
    assert _surprise(monkeypatch, float("nan")) is None
    assert _surprise(monkeypatch, None) is None


def test_the_two_surprise_paths_now_AGREE_on_the_same_quarter(monkeypatch):
    """Parity, not a new number: `AnalystPulseModal` falls back from one path
    to the other, so the units had to match."""
    from sepa import earnings_watch as EW
    monkeypatch.setattr(EW, "_fetch_next",
                        lambda s: {"last_report": {"surprise_pct": 6.16}},
                        raising=False)
    assert (EW._fetch_next("NVDA")["last_report"]["surprise_pct"]
            == _surprise(monkeypatch, 0.0616))


def test_NEGATIVE_no_threshold_reads_the_surprise_on_the_ticker_page():
    """SOURCE GUARD for the unit change: `cheetahVerdict.ts` uses
    `catalystSurprisePct` as a NULL CHECK only, so ×100 moves the printed
    number and no verdict. If a threshold ever appears here, this fails and the
    unit change must be re-argued."""
    import pathlib
    p = (pathlib.Path(__file__).resolve().parents[2]
         / "frontend" / "src" / "lib" / "cheetahVerdict.ts")
    src = p.read_text()
    assert "catalystSurprisePct != null" in src
    import re
    for m in re.finditer(r"catalystSurprisePct\s*([<>]=?)", src):
        raise AssertionError("a THRESHOLD now reads the surprise: %s" % m.group(0))


# ──────────────────────────────────────────────────── the audit counters
def test_the_audit_counters_are_PURE_over_injected_documents():
    from scripts import data_spine_audit as A
    docs = [_row("IOVA", IOVA), _row("SNDK", IOVA, tier="strong"),
            _row("HPQ", IOVA, tier="steady"), _row("FINE", ADJACENT),
            _row("NOKEYS", None)]
    m = A.mismatch_by_tier(docs)
    assert m["total"] == 3
    assert m["by_tier"] == {"explosive": 1, "strong": 1, "steady": 1}
    assert m["symbols"]["explosive"] == ["IOVA"]
    assert A.unverifiable_count(docs) == 1                 # NOKEYS only
    q4 = A.q4_shaped_share(docs)
    assert q4["mismatched"] == 3 and q4["q4_shaped"] == 3   # 8103 and 8099 gone
    assert q4["pct"] == 100.0


def test_the_CROSS_SOURCE_asymmetry_is_counted_both_ways():
    """The residual disagreement: both boards apply the same guard, to
    DIFFERENT COPIES of the series. A symbol keyed in research and unkeyed in
    the scan is checked on one board and accept-by-defaulted on the other."""
    from scripts import data_spine_audit as A
    scan = [_row("A", None), _row("B", ADJACENT), _row("C", ADJACENT)]
    research = [_row("A", ADJACENT), _row("B", None), _row("C", ADJACENT)]
    a = A.cross_source_asymmetry(scan, research)
    assert a["overlap"] == 3
    assert a["research_only_keyed"]["total"] == 1
    assert a["research_only_keyed"]["symbols"] == ["A"]
    assert a["scan_only_keyed"]["symbols"] == ["B"]
    assert a["research_only_keyed"]["by_tier"] == {"explosive": 1}


def test_the_character_clause_pairs_are_REPORTED_not_applied():
    """Spec §7.2 — the shipped guard checks exactly the two pairs the 🚀 board
    checks, so the boards agree by construction. The extra count is his call."""
    from scripts import data_spine_audit as A
    # (0,4) and (1,5) are fine; (2,6) is not — 8100 is missing.
    keys = [8106, 8105, 8104, 8103, 8102, 8101, 8099, 8098]
    assert Q.yoy_pairs_ok(keys) is True
    assert A.character_pairs_mismatch([_row("X", keys)]) == 1
    assert A.character_pairs_mismatch([_row("X", ADJACENT)]) == 0


def test_the_overlap_diff_counter_finds_a_TIER_disagreement():
    from scripts import data_spine_audit as A
    scan = [_row("BLMN", ADJACENT, tier=None)]
    research = [_row("BLMN", ADJACENT, tier="weak")]
    d = A.overlap_diffs(scan, research)
    assert d["overlap"] == 1 and d["tier_differs"] == 1
    assert d["period_differs"] == 0 and d["growth_differs"] == 0


# ──────────────────────────────── the arrival ledger and the held-out cohort
@pytest.fixture
def recorded(monkeypatch):
    """`board()` off an injected scan, returning (board, symbols recorded).

    The arrival ledger (`bonde_seen`) is the ✨ NEW clock. What goes INTO it is
    the thing under test here, so `FS.record` is captured rather than stubbed.
    """
    def _build(rows, pivots=None, new=()):
        from sepa import scanner, first_seen as FS
        seen: list = []
        monkeypatch.setattr(scanner, "load_latest",
                            lambda: {"all_results": rows, "finished_at": 1})
        monkeypatch.setattr(BD, "_pivots", lambda: dict(pivots or {}))
        monkeypatch.setattr(BD, "regime_state", lambda: {})
        monkeypatch.setattr(FS, "record",
                            lambda coll, syms, db=None: seen.append(
                                (coll, set(syms))))
        monkeypatch.setattr(FS, "newly_found", lambda *a, **k: set(new))
        monkeypatch.setattr(FS, "first_seen_map", lambda *a, **k: {})
        b = BD.board()
        assert len(seen) == 1 and seen[0][0] == BD.SEEN_COLL
        return b, seen[0][1]
    return _build


def test_NEGATIVE_a_held_out_passer_is_NOT_stamped_into_the_arrival_ledger(recorded):
    """FAILS ON THE OLD CODE, which recorded every passer.

    A passer the fiscal-pair guard holds out renders NOWHERE. Stamping it would
    run its ✨ NEW clock out while it is hidden, so on the day the guard lets it
    through — the day it actually arrives on his screen — it would arrive silent.
    """
    b, seen = recorded([_row("IOVA", IOVA), _row("GOOD", ADJACENT)])
    assert b["n_period_mismatch"] == 1
    assert seen == {"GOOD"}
    assert "IOVA" not in seen


def test_a_held_out_row_that_KEEPS_its_pivot_IS_recorded(recorded):
    """It is drawn in ⚡ Pivots with the growth claim blanked, so it arrived."""
    piv = {"IOVA": {"generated_at": None, "trigger": 5.0, "stop": 4.0,
                    "meta": {"gap_pct": 12.0, "vol_mult": 6.0}}}
    b, seen = recorded([_row("IOVA", IOVA)], pivots=piv)
    assert [r["symbol"] for r in b["sections"]["pivot"]] == ["IOVA"]
    assert seen == {"IOVA"}


def test_NEGATIVE_n_new_no_longer_counts_a_row_the_board_never_drew(recorded):
    """`n_new` is read off the ledger. With the held-out cohort out of it, a
    hidden name cannot inflate the count his screen prints."""
    b, seen = recorded([_row("IOVA", IOVA), _row("GOOD", ADJACENT)],
                       new={"GOOD"})
    assert seen == {"GOOD"}          # what the ledger would have grown by
    assert b["n_new"] == 1
    assert [r["symbol"] for r in b["sections"]["explosive"]] == ["GOOD"]
    assert b["sections"]["explosive"][0]["is_new"] is True


def test_a_passer_pushed_off_by_the_SECTION_CAP_is_STILL_recorded(recorded, monkeypatch):
    """The older guarantee must not regress: the cap decides what is SHOWN, it
    does not decide what has arrived — otherwise a name's ✨ NEW clock resets
    every time the cap pushes it off and back on."""
    monkeypatch.setitem(BD.SECTION_CAP, BD.SECTION_EXPLOSIVE, 1)
    rows = [_row("AAA", ADJACENT, growth=300.0),
            _row("BBB", ADJACENT, growth=200.0)]
    b, seen = recorded(rows)
    assert [r["symbol"] for r in b["sections"]["explosive"]] == ["AAA"]
    assert seen == {"AAA", "BBB"}


def test_NEGATIVE_a_row_that_FAILS_the_screen_is_never_stamped(recorded):
    """A 🔎 rejected row is not on his screen, and the board already refuses to
    badge it ✨ NEW — the ledger must not carry it either."""
    rej = _row("REJ", ADJACENT, tier="steady", growth=8.0, accel=False,
               consec=1)
    b, seen = recorded([rej])
    assert [r["symbol"] for r in b["sections"]["rejected"]] == ["REJ"]
    assert seen == set()
