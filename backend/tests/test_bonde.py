"""Bonde board — his screen as its own tab (Ajay 2026-09-13).

The negatives carry this file. Three of them pin real defects caught on the live
board before it shipped, and each produced a confident, plausible, wrong row.
"""
from __future__ import annotations

import pytest

from sepa import bonde as BD
from sepa import first_seen as FS


def scan_row(symbol, rev_series, **kw):
    return {"symbol": symbol, "name": kw.get("name"),
            "last_close": kw.get("last_close", 10.0),
            "fundamentals": {"rev_q_series": rev_series,
                             "sales": kw.get("sales") or {}}}


# ─────────────────────────────────────────── the revenue-base defect
def test_a_NEGATIVE_year_ago_base_is_refused_not_rendered_as_growth():
    """THE DBRG DEFECT, caught on the live board 2026-09-13.

    `sepa/sales.py::_yoy` divides by abs(base), so a NEGATIVE prior-year quarter
    comes back as large POSITIVE growth. DBRG read +15,961% off MINUS
    $3,207,000, and APLD +877% off MINUS $33,300,000. That is a sign flip, not a
    ramp, and it ranked above every real business on the board."""
    r = BD._rev_base(scan_row("DBRG", [508_679_000, None, None, None, -3_207_000]))
    assert r["base_state"] == "non_positive"
    assert r["rev_added"] is None          # no dollar figure off a negative base


def test_an_IMMATERIAL_base_is_flagged_because_the_percentage_is_a_ratio():
    """QUBT read +9,000% off $61,000 of quarterly revenue; FCUV +1,811% off
    $35,330. A company with $61k of quarterly revenue was pre-revenue."""
    assert BD._rev_base(scan_row("QUBT", [5_551_000, 0, 0, 0, 61_000]))["base_state"] == "too_small"
    assert BD._rev_base(scan_row("FCUV", [675_170, 0, 0, 0, 35_330]))["base_state"] == "too_small"


def test_a_REAL_base_passes_and_carries_its_dollars():
    r = BD._rev_base(scan_row("PTGX", [213_475_000, 0, 0, 0, 5_546_000]))
    assert r["base_state"] == "ok"
    assert r["rev_added"] == pytest.approx(207_929_000)


def test_NEGATIVE_the_materiality_floor_is_the_BOARDS_not_Bondes():
    """SOURCE GUARD. His 5/25/100 tiers are documented in his own writing; the
    $1M base floor is this app's, and the board must never imply otherwise."""
    assert BD.MIN_MATERIAL_BASE_REV == 1_000_000.0
    src = open(BD.__file__).read()
    assert "OWNER SETTING, NOT A BONDE NUMBER" in src
    assert "+15,961%" in src and "QUBT" in src


def test_the_order_inside_a_tier_does_NOT_rank_on_a_broken_base():
    """Every name in a tier already cleared the tier's threshold, so the order
    is this board's choice — and ranking on the raw percentage put a sign flip
    and a $61k base above a company going $5.5M -> $213M."""
    real = {"symbol": "PTGX", "base_state": "ok", "growth_yoy_pct": 3749.2,
            "sales_score": 100, "rev_added": 207_929_000}
    flip = {"symbol": "DBRG", "base_state": "non_positive", "growth_yoy_pct": 15961.5,
            "sales_score": 100, "rev_added": None}
    tiny = {"symbol": "QUBT", "base_state": "too_small", "growth_yoy_pct": 9000.0,
            "sales_score": 100, "rev_added": 5_490_000}
    assert sorted([flip, tiny, real], key=BD._sales_key)[0]["symbol"] == "PTGX"


def test_a_flagged_name_is_still_SHOWN_never_filtered_out():
    """Hiding it would make the board disagree with his screen. It must appear,
    with its numbers, simply not at the top."""
    rows = sorted([
        {"symbol": "DBRG", "base_state": "non_positive", "growth_yoy_pct": 15961.5,
         "sales_score": 100, "rev_added": None},
        {"symbol": "PTGX", "base_state": "ok", "growth_yoy_pct": 3749.2,
         "sales_score": 100, "rev_added": 207_929_000},
    ], key=BD._sales_key)
    assert {r["symbol"] for r in rows} == {"DBRG", "PTGX"}


# ─────────────────────────────────────────── the duplicate-pivot defect
def test_NEGATIVE_pivots_are_DEDUPED_to_one_row_per_symbol(monkeypatch):
    """Measured live: the stored setups returned MRNA five times, PAYS three
    and ANF twice, because each scanner pass upserts a new row. Raw, one name
    would occupy five rows and a 12-name board would look like 30.

    Patched through `setups.store` itself rather than by swapping sys.modules —
    the module is imported by other tests in the suite, so a sys.modules swap
    passes alone and fails in a full run depending on import order.
    """
    import time
    from setups import store
    now = time.time()
    rows = [{"symbol": "MRNA", "generated_at": now - 100, "meta": {"gap_pct": 9.0}},
            {"symbol": "MRNA", "generated_at": now - 10, "meta": {"gap_pct": 11.0}},
            {"symbol": "ANF", "generated_at": now - 50, "meta": {"gap_pct": 8.5}}]
    monkeypatch.setattr(store, "get_setups", lambda **kw: rows)

    out = BD._pivots()
    assert set(out) == {"MRNA", "ANF"}
    # ...and the FRESHEST row wins, not whichever came back first.
    assert out["MRNA"]["meta"]["gap_pct"] == 11.0


def test_NEGATIVE_a_STALE_pivot_is_dropped(monkeypatch):
    """Every setup kind in the app is currently stale (see regime_state) —
    newest episodic_pivot 413h old. A board that rendered those would present
    a 17-day-old gap as a live entry."""
    import time
    from setups import store
    now = time.time()
    rows = [{"symbol": "OLD", "generated_at": now - (BD.MAX_PIVOT_AGE_H + 10) * 3600,
             "meta": {"gap_pct": 12.0}}]
    monkeypatch.setattr(store, "get_setups", lambda **kw: rows)
    assert BD._pivots() == {}


# ─────────────────────────────────────────── arrivals
def test_the_FIRST_cohort_is_never_badged_as_new():
    """'We have only just started looking' must never render as 'these are
    fresh finds'. Without the __meta__ guard the first build badges everything."""
    class _Coll:
        """A Mongo stand-in that honours $setOnInsert properly.

        The first version of this fake applied $setOnInsert on EVERY call, so
        `tracking_since` advanced with each build and the strict `>` excluded
        the very arrival it was meant to catch. The fake was wrong, not the
        module — but it is exactly the mistake the real guard exists to prevent,
        so it is worth the accurate double.
        """
        def __init__(self):
            self.docs = {}

        def update_one(self, q, upd, upsert=False):
            _id = q["_id"]
            is_new = _id not in self.docs
            d = self.docs.setdefault(_id, {"_id": _id})
            if is_new:
                d.update(upd.get("$setOnInsert") or {})
            d.update(upd.get("$set") or {})

        def find_one(self, q, *a, **k):
            return self.docs.get(q.get("_id"))

        def find(self, q, *a, **k):
            gt = (q.get("first_seen") or {}).get("$gt")
            for _id, d in self.docs.items():
                if _id == FS.META_ID:
                    continue
                if gt is None or str(d.get("first_seen", "")) > str(gt):
                    yield d

    class _DB:
        def __init__(self):
            self.c = _Coll()

        def __getitem__(self, name):
            return self.c

    db = _DB()
    FS.record("t", ["AAA", "BBB"], db=db)
    assert FS.newly_found("t", days=30, db=db) == set()     # the first cohort
    import time as _t
    _t.sleep(0.01)
    FS.record("t", ["AAA", "BBB", "CCC"], db=db)
    assert FS.newly_found("t", days=30, db=db) == {"CCC"}   # only the arrival


def test_NEGATIVE_no_tracking_history_means_NO_arrivals_not_all_of_them():
    class _Empty:
        def find_one(self, *a, **k): return None
        def find(self, *a, **k): return iter(())

    class _DB:
        def __getitem__(self, name): return _Empty()
    assert FS.newly_found("t", days=30, db=_DB()) == set()


# ─────────────────────────────────────────── the regime finding
def test_the_board_EXPLAINS_an_empty_pivot_section():
    """FOUND WHILE BUILDING THIS, 2026-09-13: every setup kind in the app is
    stale because `is_bull_regime()` reads False and Ajay chose to sit out bear
    markets. An empty headline section with no explanation reads as broken."""
    note = BD.pivot_pause_note({"scanners_paused": True, "label": "market_in_correction"})
    assert "PIVOTS ARE PAUSED" in note
    assert "market in correction" in note
    assert "your own rule" in note
    # ...and nothing is said when they are running.
    assert BD.pivot_pause_note({"scanners_paused": False}) == ""
    assert BD.pivot_pause_note(None) == ""


def test_the_note_leads_with_the_FIRE_RATE_not_the_mechanics():
    """His sales gate alone describes half the market. A reader who does not
    know that reads the tier sections as a selection."""
    note = BD.note(1051, 2076, {"pivot": 12})
    assert "1,051 of 2,076" in note and "50.6%" in note
    assert "sales_confidence_methodology" in note
    # whose numbers are whose
    assert "owner settings, not numbers he published" in note


def test_the_board_RE_DERIVES_nothing():
    """SOURCE GUARD, and the point of the whole module: every rule is called
    from the module that already implements and cites it."""
    src = open(BD.__file__).read()
    assert "_bonde_pillar" in src          # the pass rule
    assert "sepa/sales.py" in src          # the tiers
    assert "episodic_pivot" in src         # the entry
    assert "NOTHING HERE RE-DERIVES BONDE" in src


# ═══════════════════════════════════════════ MEASURED 2026-09-13 — INVERTED
# This board shipped in the morning on the thesis that his sales screen is the
# universe and the Episodic Pivot is the entry, so the intersection is the
# selection. It was measured twice the same day and the intersection is the
# WORST cell either pass found. These tests exist so nobody — me included —
# can quietly walk that back to a rules-first board.
# Source: backend/scripts/bonde_audit/ (README.md carries the run recipe).

def test_the_note_LEADS_with_the_inverted_measurement():
    """The first words a reader meets must be the verdict, not the rules.

    Same treatment the Keltner and AMD tabs got the same day, and for the same
    reason: a board that explains its mechanics first has already been read as
    a buy list by the time it admits what it measured.
    """
    note = BD.note(1051, 2076, {"pivot": 12})
    assert note.startswith("MEASURED 2026-09-13 AND THE THESIS IS INVERTED")
    # the number, its placebo and its interval — never a bare point estimate
    assert "−3.22%" in note and "39.8%" in note
    assert "−0.11%" in note and "49.6%" in note        # the placebo
    assert "−3.11pp" in note and "−5.28 to −1.16" in note
    assert "STUDY BOARD" in note
    assert "backend/scripts/bonde_audit/" in note      # the re-runnable source
    # ...and the fire rate is still there, just no longer the headline
    assert "1,051 of 2,076" in note and "50.6%" in note


def test_the_note_says_his_SALES_GATE_ALONE_separated_nothing():
    """The gate passes 48.2% of Pivot events and 46.0% of matched non-Pivot
    draws — it carries no information about the pivot. A board that prints the
    intersection's number without this one implies the gate did some work."""
    note = BD.note(1051, 2076, {"pivot": 12})
    assert "−0.40pp" in note and "−1.40 to +0.61" in note


def test_the_verdict_banner_is_SERVED_not_typed_into_the_component():
    """One home for the numbers (`MEASURED`), so a re-run moves every surface.

    The alternative — the figures living in TSX — is how a board ends up
    quoting a stale lift months after the script that produced it changed.
    """
    v = BD.measured_verdict()
    assert "INVERTED" in v["headline"] and BD.MEASURED["run_date"] in v["headline"]
    assert "−3.22%" in v["body"] and "−0.11%" in v["body"]
    assert "STUDY BOARD, NOT A BUY LIST" in v["body"]
    # every claimed section is present and non-empty
    for k in ("body", "not_a_short", "tiers", "rejected", "struck", "limits"):
        assert v[k] and len(v[k]) > 80, k
    assert v["scripts"] == "backend/scripts/bonde_audit/"


def test_NEGATIVE_the_verdict_refuses_to_read_as_a_SHORT_signal():
    """Cell A's 21-day MEAN is −2.18% with a CI that includes zero. 'These
    bleed at the median and win less than half the time' is the finding;
    'these reliably fall' is a different claim the data does not support."""
    v = BD.measured_verdict()
    assert "−2.18%" in v["not_a_short"]
    assert "includes zero" in v["not_a_short"]


def test_NEGATIVE_the_STRUCK_claims_appear_nowhere():
    """Three first-pass claims did not reproduce under an independent audit on
    ~2x the panel. The most tempting one is the most wrong: 'EP + sales-PASS
    even loses to EP + sales-FAIL' is a punchy sentence and it spans zero in
    all four fundamentals variants."""
    v = BD.measured_verdict()
    blob = " ".join(v.values()) + BD.note(1051, 2076, {"pivot": 12})
    # the struck A-vs-B claim may appear ONLY inside the 'struck' paragraph
    assert "−2.42pp" in v["struck"]
    assert blob.count("−2.42pp") == 1
    assert "only the consistency one is" in v["struck"]
    assert "no-retry fetcher" in v["struck"]


def test_the_TIERS_never_print_a_mean_without_its_median_and_placebo():
    """The first pass's '+3.8pp / +1.6pp' were MEAN lifts printed as if they
    were typical outcomes. Median lifts are +0.45pp and +0.37pp with CIs that
    include zero, and the mean is the right tail: it falls to +0.26pp once the
    top 5% of returns are dropped."""
    t = BD.measured_verdict()["tiers"]
    assert "MEDIAN" in t
    assert "+0.45pp" in t and "+0.37pp" in t
    assert "include zero" in t
    assert "+0.26pp" in t and "top 5%" in t
    assert "scored universe" in t          # the placebo, named


def test_the_LIMITS_are_printed_with_the_numbers_not_buried_in_a_doc():
    lim = BD.measured_verdict()["limits"]
    for phrase in ("survivorship", "ONE bull regime", "filing date",
                   "unclassifiable", "gross of commissions"):
        assert phrase in lim, phrase


# ─────────────────────────────────────────── the 🔎 rejected cohort
def _pillar(passed, growth, **kw):
    d = {"passed": passed, "growth_yoy_pct": growth, "tier": kw.get("tier"),
         "score": kw.get("score"), "accelerating": kw.get("accelerating", False),
         "consecutive_growth_q": kw.get("consec", 0), "sales_led": None,
         "reason": ""}
    return d


def test_the_cohort_his_gate_REJECTS_is_shown_because_it_MEASURED_BETTER():
    """THE ONE FINDING THAT SURVIVED EVERY ATTACK.

    Among names clearing his 5% floor, requiring THIS APP'S 'character' clause
    (accelerating OR >=2 consecutive growth quarters — the app's own, 2026-06-16,
    mis-attributed to him until 2026-09-20) measures NEGATIVE: the rejected
    cohort won 56.8% of the next 21 sessions against 51.2% for the cohort the
    gate accepts (+5.64pp, CI +3.91 to +7.52). The gate is not edited — a rule
    change is Ajay's call (Rule #10) — so the discarded names get their own
    labelled section instead.
    """
    assert BD.SECTION_REJECTED in BD.SECTIONS
    assert BD.SECTIONS[-1] == BD.SECTION_REJECTED      # last, never leading
    rej = BD.measured_verdict()["rejected"]
    assert "56.8%" in rej and "51.2%" in rej
    assert "+5.64pp" in rej and "+3.91 to +7.52" in rej
    assert "not edited" in rej


def test_only_the_CONSISTENCY_clause_is_inverted_accelerating_is_a_NULL():
    """The first pass said both clauses measure backwards. `accelerating` is
    +1.63pp mean with a CI of −0.85 to +7.54 — a null, and calling a null an
    inversion is the same error in the other direction."""
    rej = BD.measured_verdict()["rejected"]
    assert "CONSISTENCY" in rej
    assert "accelerating` is a null, not a negative" in rej


def test_the_rejected_cohorts_own_CAVEAT_travels_with_it():
    """It does not survive date clustering at 21 days (it does at 63), and the
    variant matching production's raw list position shrinks it to 1,030 bars
    with CIs spanning zero. Shipping the finding without that is the Hot
    Pullback mistake again."""
    rej = BD.measured_verdict()["rejected"]
    assert "date clustering at 21 days" in rej
    assert "1,030 bars" in rej


def test_the_floor_check_matches_the_pillars_own_ROUNDING_seam():
    """`_bonde_pillar` tests the ROUNDED growth against the 5% floor while
    `sales.compute` tiers off the unrounded value. The audit found exactly one
    row in that seam out of 780. The board must sit on the same side of it as
    the rule it is describing, or a name renders as 'rejected for character'
    when the gate actually rejected it for the floor."""
    assert BD._cleared_floor(_pillar(False, 4.6)) is True      # rounds to 5
    assert BD._cleared_floor(_pillar(False, 4.4)) is False
    assert BD._cleared_floor(_pillar(False, None)) is False


def test_NEGATIVE_the_board_does_NOT_sort_on_the_0_to_100_sales_score():
    """The audit could not separate whatever ranking value that score has from
    the right tail of the return distribution, so it decides no order a reader
    might mistake for a ranking."""
    low_score_big_grower = {"symbol": "AAA", "base_state": "ok",
                            "growth_yoy_pct": 300.0, "rev_added": 2e8,
                            "sales_score": 40}
    high_score_small = {"symbol": "BBB", "base_state": "ok",
                        "growth_yoy_pct": 30.0, "rev_added": 1e6,
                        "sales_score": 100}
    assert sorted([high_score_small, low_score_big_grower],
                  key=BD._sales_key)[0]["symbol"] == "AAA"
    src = open(BD.__file__).read()
    assert "NOT `sales.compute`'s 0-100 score, deliberately" in src


def test_NEGATIVE_the_rejected_section_is_never_badged_as_a_NEW_ARRIVAL():
    """✨ NEW means 'arrived on HIS screen'. A 🔎 row is by definition not on
    it, so a name that passed last week and fails the character clause today
    would otherwise render as a fresh find on a board it just fell off."""
    src = open(BD.__file__).read()
    assert '(k != SECTION_REJECTED) and (r["symbol"] in new)' in src


def test_SOURCE_GUARD_the_measurement_ships_its_own_script():
    """STANDING RULE: any measured number on a board he trades ships its
    re-runnable script and a CI, never a bare point estimate."""
    import os
    d = os.path.join(os.path.dirname(os.path.dirname(BD.__file__)),
                     "scripts", "bonde_audit")
    assert os.path.isdir(d)
    for f in ("README.md", "core.py", "lane1.py", "lane1b.py", "lane2.py",
              "attack.py", "sens.py", "oracle.py", "fetch.py"):
        assert os.path.isfile(os.path.join(d, f)), f
    readme = open(os.path.join(d, "README.md")).read()
    assert "−3.11pp" in readme and "−5.28 to −1.16" in readme
    # the superseded first pass is kept so the struck claims stay visible
    assert os.path.isfile(os.path.join(d, "parent_ep.py"))
    assert "SUPERSEDED" in open(os.path.join(d, "parent_ep.py")).read()


def test_board_routes_a_floor_clearer_WITHOUT_character_into_the_rejected_section(monkeypatch):
    """END TO END. Three names, three fates:

      PASS   clears the floor AND has character   -> his screen (a tier)
      REJ    clears the floor, no character       -> 🔎, and NOT in any tier
      LOW    below the floor                      -> nowhere at all

    The third row is the one worth the test: a name that failed the FLOOR must
    never land in a section labelled 'rejected for character', because that
    label is a claim about which half of his rule threw it out.
    """
    from sepa import scanner, board_metrics as BM
    rows = [
        scan_row("PASS", [200_000_000, 0, 0, 0, 100_000_000],
                 sales={"score": 90, "tier": "strong", "growth_yoy_pct": 100.0,
                        "accelerating": True, "consecutive_growth_q": 4}),
        scan_row("REJ", [120_000_000, 0, 0, 0, 100_000_000],
                 sales={"score": 55, "tier": "steady", "growth_yoy_pct": 20.0,
                        "accelerating": False, "consecutive_growth_q": 1}),
        scan_row("LOW", [101_000_000, 0, 0, 0, 100_000_000],
                 sales={"score": 20, "tier": "weak", "growth_yoy_pct": 1.0,
                        "accelerating": False, "consecutive_growth_q": 0}),
    ]
    monkeypatch.setattr(scanner, "load_latest", lambda *a, **k: {"all_results": rows})
    monkeypatch.setattr(BD, "_pivots", lambda *a, **k: {})
    monkeypatch.setattr(BD, "regime_state", lambda *a, **k: {"scanners_paused": False})
    monkeypatch.setattr(BM, "attach", lambda *a, **k: None)
    monkeypatch.setattr(FS, "record", lambda *a, **k: 0)
    monkeypatch.setattr(FS, "newly_found", lambda *a, **k: {"PASS", "REJ"})
    monkeypatch.setattr(FS, "first_seen_map", lambda *a, **k: {})

    b = BD.board()
    got = {k: [r["symbol"] for r in v] for k, v in b["sections"].items()}
    assert got[BD.SECTION_REJECTED] == ["REJ"]
    assert "REJ" not in got["steady"] and "REJ" not in got["strong"]
    assert got["strong"] == ["PASS"]
    assert "LOW" not in [s for v in got.values() for s in v]

    assert b["n_pass"] == 1                      # his screen, unchanged
    assert b["n_rejected"] == 1                  # the cohort beside it
    assert b["measured"]["headline"].endswith("INVERTED")

    # ✨ NEW is a claim about HIS screen: it may light on PASS, never on REJ.
    new_by_sym = {r["symbol"]: r["is_new"]
                  for v in b["sections"].values() for r in v}
    assert new_by_sym["PASS"] is True
    assert new_by_sym["REJ"] is False
