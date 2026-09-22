"""The 📈 Bonde steady tier, LABELLED — 2026-09-21 (Ajay: *"Yes"*).

He was offered "leave it, label it, or drop it". Labelling is additive and
reversible; dropping 666 names is not. So this package adds a served sentence
and nothing else — and this file is what stops that sentence from becoming a
stronger claim than the replay supports.

Three kinds of test here, in order:

1. **Field-for-field pins.** Every number in `bonde.STEADY_MEASURED` is read
   back out of `backend/scripts/board_growth_measured.json`. A re-run that
   moves a number fails the suite instead of quietly rewriting the label.
2. **Honesty pins.** Each *claim* the sentence makes is checked against the
   artifact's own interval signs: "wholly below zero" only where the interval
   is, "spans zero" where it does, "the ONE cohort" only over the axis and
   horizon where it is true (pinned across all 19 cells), and never a MEAN
   without its MEDIAN beside it — the house rule `test_bonde.py` already
   applies to the tier paragraph.
3. **Negatives.** The label must not have become an ACTION: `SECTION_CAP`,
   `SECTIONS`, `note()` and `MEASURED` are unchanged, and `board()` still
   places steady rows.

Rule #10: nothing here gates, sorts, filters or alerts.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from sepa import bonde as BD
from sepa import first_seen as FS

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "backend" / "scripts" / "board_growth_measured.json"

HORIZONS = ("h21", "h63", "h126")
MINUS = "−"  # U+2212 — the board prints a real minus, never a hyphen


@pytest.fixture(scope="module")
def art() -> dict:
    return json.loads(ARTIFACT.read_text())


@pytest.fixture(scope="module")
def steady_cell(art) -> dict:
    return art["cells"]["B_STEADY"]


@pytest.fixture(scope="module")
def arrive_cell(art) -> dict:
    return art["cells"]["B_EXPL_ARRIVE"]


@pytest.fixture(scope="module")
def verdict() -> str:
    return BD.steady_verdict()


def r2(pair) -> tuple:
    """The artifact's interval, rounded the way the constant stores it."""
    return tuple(round(float(x), 2) for x in pair)


# ──────────────────────────────────────────── 1. field-for-field pins
@pytest.mark.parametrize("h", HORIZONS)
def test_the_lift_constants_equal_the_artifact_at_every_horizon(h, steady_cell):
    """Both clusterings, every horizon — not just the one that reads worst.

    The 2026-09-13 audit's lesson on this board was that DATE clustering is
    the binding axis (symbol clustering alone left intervals ~3x too tight).
    A constant that carried only `ci_symbol` would let the label state a
    finding the replay does not have at 21 days.
    """
    got = BD.STEADY_MEASURED["lift"][h]
    cell = steady_cell[h]
    assert got["n"] == cell["n"]
    assert got["n_symbols"] == cell["n_symbols"]
    assert got["n_dates"] == cell["n_dates"]
    assert got["median_lift_pp"] == cell["median_lift_vs_all_scored_pp"]
    assert tuple(got["ci_symbol"]) == r2(cell["lift_ci_symbol"])
    assert tuple(got["ci_date"]) == r2(cell["lift_ci_date"])


@pytest.mark.parametrize("h", HORIZONS)
def test_the_momentum_control_constants_equal_the_artifact(h, steady_cell):
    got = BD.STEADY_MEASURED["momentum_control"][h]
    cell = steady_cell[h]["momentum_control"]
    assert got["n"] == cell["n"]
    assert got["mean_excess_pp"] == round(cell["mean_excess_pp"], 2)
    assert got["median_excess_pp"] == round(cell["median_excess_pp"], 2)
    assert tuple(got["ci_symbol"]) == r2(cell["ci_symbol"])
    assert "ci_date" not in cell, "an unread date CI would silence the caveat"
    assert "ci_date" not in got


@pytest.mark.parametrize("h", HORIZONS)
def test_the_arrivals_contrast_equals_the_artifact(h, arrive_cell):
    got = BD.STEADY_MEASURED["explosive_arrivals"][h]
    cell = arrive_cell[h]
    assert got["median_lift_pp"] == cell["median_lift_vs_all_scored_pp"]
    assert tuple(got["ci_symbol"]) == r2(cell["lift_ci_symbol"])
    assert tuple(got["ci_date"]) == r2(cell["lift_ci_date"])


def test_the_panel_size_and_provenance_come_from_the_artifact(art):
    s = BD.STEADY_MEASURED
    assert s["panel_dates"] == art["repro"]["n_dates_panel"]
    assert s["run_date"] == "2026-09-21"
    assert s["doc"] == "docs/research/board_growth_2026_09_21.md"
    assert (ROOT / s["doc"]).is_file()
    assert s["script"] == "backend/scripts/board_growth_replay.py"
    assert (ROOT / s["script"]).is_file()
    assert s["prior_read"] == BD.MEASURED["run_date"]


# ──────────────────────────────────────────── 2. honesty of the claim
def test_the_21_day_claim_is_true_on_the_symbol_axis_and_not_on_the_date_axis(
        steady_cell):
    """"wholly below zero" is a SYMBOL-axis statement here, and the label says
    so in its first clause. Date-clustered the same interval spans zero."""
    sym = r2(steady_cell["h21"]["lift_ci_symbol"])
    dat = r2(steady_cell["h21"]["lift_ci_date"])
    assert sym[1] < 0, "the whole-interval-below-zero claim"
    assert dat[0] < 0 < dat[1], "the spans-zero caveat"


@pytest.mark.parametrize("h", ("h63", "h126"))
def test_every_interval_spans_zero_at_63_and_126_on_BOTH_clusterings(
        h, steady_cell):
    sym = r2(steady_cell[h]["lift_ci_symbol"])
    dat = r2(steady_cell[h]["lift_ci_date"])
    assert sym[0] < 0 < sym[1], h
    assert dat[0] < 0 < dat[1], h


@pytest.mark.parametrize("h", HORIZONS)
def test_the_momentum_controlled_MEAN_is_below_zero_at_every_horizon(
        h, steady_cell):
    """The only leg of this study that is negative everywhere — and it is a
    claim about the MEAN under symbol clustering alone."""
    assert r2(steady_cell[h]["momentum_control"]["ci_symbol"])[1] < 0


def test_the_arrivals_lift_is_clear_of_zero_on_the_symbol_axis_only(
        arrive_cell):
    """"every CI clear of zero" would be false. 21 and 126 days span zero
    date-clustered; only 63 days is clear on both axes."""
    for h in HORIZONS:
        assert r2(arrive_cell[h]["lift_ci_symbol"])[0] > 0, h
    assert r2(arrive_cell["h21"]["lift_ci_date"])[0] < 0
    assert r2(arrive_cell["h126"]["lift_ci_date"])[0] < 0
    assert r2(arrive_cell["h63"]["lift_ci_date"])[0] > 0


def test_THE_ONE_COHORT_claim_holds_over_every_cell_at_21d_symbol_clustered(
        art):
    """The sentence says "AT 21 DAYS, SYMBOL-CLUSTERED … THE ONE COHORT".

    Pinned over all 19 cells so a re-run that produces a second below-zero
    cohort fails here rather than leaving an overstated word on the board.
    `ALL_SCORED` is the degenerate self-reference (upper bound exactly 0.0);
    `B_STEADY` is the subject. Today the nearest other cell is `B_STRONG` at
    +0.56.
    """
    others = []
    for key, cell in art["cells"].items():
        if key in ("ALL_SCORED", "B_STEADY"):
            continue
        ci = (cell.get("h21") or {}).get("lift_ci_symbol")
        if ci:
            others.append((key, round(float(ci[1]), 5)))
    assert others, "no comparison cells — the claim would be vacuous"
    assert all(hi >= 0 for _, hi in others), \
        "a second cohort measures below the field: %r" % (
            [o for o in others if o[1] < 0],)
    assert round(float(art["cells"]["ALL_SCORED"]["h21"]["lift_ci_symbol"][1]),
                 5) == 0.0
    assert round(float(
        art["cells"]["B_STEADY"]["h21"]["lift_ci_symbol"][1]), 5) < 0


# ──────────────────────────────────────────── the served sentence
def test_the_steady_line_is_SERVED_as_a_string_from_the_dict(verdict):
    v = BD.measured_verdict()
    assert isinstance(v["steady"], str), \
        "test_bonde.py joins measured_verdict().values()"
    assert v["steady"] == verdict
    assert len(verdict) > 400
    # every other value stayed a str too — the join in test_bonde.py:279
    assert all(isinstance(x, str) for x in v.values())


@pytest.mark.parametrize("needle", [
    "MEASURED 2026-09-21",
    "AT 21 DAYS, SYMBOL-CLUSTERED",
    "THE ONE COHORT",
    MINUS + "0.21pp",
    MINUS + "0.40 to " + MINUS + "0.04",
    MINUS + "0.56 to +0.10",
    "spans zero",
    "14,353",
    "1,611",
    "24 monthly cross-sections",
    "20 of them carry a full 21-session forward",
    MINUS + "0.52pp",
    MINUS + "0.51pp",
    MINUS + "0.89 to +0.02",
    MINUS + "1.18 to +0.25",
    "every interval spans zero on both clusterings",
    "MEAN " + MINUS + "0.60 / " + MINUS + "1.79 / " + MINUS + "3.40pp",
    "MEDIAN " + MINUS + "1.27 / " + MINUS + "3.80 / " + MINUS + "6.98pp",
    "symbol-clustered only",
    "MEDIAN +3.33 / +7.49 / +12.83pp",
    "+1.24 to +5.42",
    "21 and 126 days span zero",
    MINUS + "0.91 to +8.37",
    MINUS + "8.05 to +19.07",
    "only 63 days is clear",
    "+0.52 to +16.06",
    "MEASUREMENT",
    "not a rule",
    "docs/research/board_growth_2026_09_21.md",
    "backend/scripts/board_growth_replay.py",
])
def test_the_served_line_says_it(verdict, needle):
    assert needle in verdict


def test_every_number_in_the_line_comes_from_the_dict(verdict):
    """Not a proof, a tripwire: bend a constant and the sentence must bend.

    A sentence assembled from the dict cannot carry a retyped literal past
    this test, which is the whole reason the constants exist.
    """
    original = BD.STEADY_MEASURED["lift"]["h21"]["median_lift_pp"]
    try:
        BD.STEADY_MEASURED["lift"]["h21"]["median_lift_pp"] = -9.99
        bent = BD.steady_verdict()
    finally:
        BD.STEADY_MEASURED["lift"]["h21"]["median_lift_pp"] = original
    assert MINUS + "9.99pp" in bent
    assert MINUS + "0.21pp" not in bent
    assert BD.steady_verdict() == verdict


@pytest.mark.parametrize("h,mean,median", [
    ("h21", MINUS + "0.60", MINUS + "1.27"),
    ("h63", MINUS + "1.79", MINUS + "3.80"),
    ("h126", MINUS + "3.40", MINUS + "6.98"),
])
def test_a_MEAN_never_appears_without_its_MEDIAN(verdict, h, mean, median):
    """The house rule from `test_bonde.py::test_the_TIERS_never_print_a_mean…`.

    The momentum-controlled mean is the strongest number in this study and the
    medians are three to five times larger in magnitude — printing the mean
    alone would understate the spread AND flatter the precision.
    """
    assert mean in verdict
    assert median in verdict


def test_NEGATIVE_the_line_never_makes_the_unqualified_first_draft_claim(
        verdict):
    """The first draft said the steady tier "is the one cohort that measures
    WORSE than the field" with no axis and no horizon. That is false at 63 and
    126 days and false on the date axis at 21."""
    assert "ON THIS BOARD THE STEADY TIER IS THE ONE COHORT THAT MEASURES " \
           "WORSE THAN THE FIELD" not in verdict
    one = verdict.index("THE ONE COHORT")
    assert "AT 21 DAYS, SYMBOL-CLUSTERED" in verdict[:one], \
        "the qualifier must precede the claim, not trail it"


def test_NEGATIVE_the_arrivals_contrast_is_not_overstated(verdict):
    assert "every CI clear of zero" not in verdict
    assert "symbol-clustered CIs clear of zero" in verdict


def test_NEGATIVE_negative_at_every_horizon_carries_its_median(verdict):
    sentences = re.split(r"(?<=\.)\s+", verdict)
    hits = [s for s in sentences if "negative at every horizon" in s]
    assert len(hits) == 1
    assert "MEDIAN" in hits[0]
    assert "MEAN" in hits[0]


def test_NEGATIVE_the_line_never_borrows_the_other_studys_struck_number():
    """`test_bonde.py::test_NEGATIVE_the_STRUCK_claims_appear_nowhere` counts
    `−2.42pp` exactly once across every served value. The steady line must not
    be the second occurrence."""
    v = BD.measured_verdict()
    blob = " ".join(v.values()) + BD.note(1051, 2076, {"pivot": 12})
    assert blob.count(MINUS + "2.42pp") == 1
    assert MINUS + "2.42pp" not in v["steady"]


def test_NEGATIVE_the_unsourced_prior_read_is_described_in_words_only(verdict):
    """`docs/sepa/bonde_board.md:85` carries "−0.01pp" for this tier from the
    2026-09-13 audit with NO interval and no machine-readable artifact. A
    number with no interval may not ride on a served honesty line."""
    assert "0.01pp" not in verdict
    assert "read this tier flat with no interval" in verdict
    assert BD.MEASURED["run_date"] in verdict


def test_NEGATIVE_the_line_says_reversal_wording_and_claims_no_action(verdict):
    assert "bounce" not in verdict.lower()
    assert "nothing here is hidden, dropped, re-sorted or gated on it" in verdict
    for word in ("buy", "sell", "should", "avoid", "skip"):
        assert word not in verdict.lower().split(), word


# ──────────────────────────────────────────── 3. the label is not an action
def test_NEGATIVE_the_section_cap_and_the_section_list_are_unchanged():
    assert BD.SECTION_CAP[BD.SECTION_STEADY] == 40
    assert BD.SECTION_STEADY in BD.SECTIONS
    assert BD.SECTIONS == (BD.SECTION_PIVOT, BD.SECTION_EXPLOSIVE,
                           BD.SECTION_STRONG, BD.SECTION_STEADY,
                           BD.SECTION_REJECTED)
    assert BD.SECTION_CAP == {BD.SECTION_PIVOT: 60, BD.SECTION_EXPLOSIVE: 60,
                              BD.SECTION_STRONG: 60, BD.SECTION_STEADY: 40,
                              BD.SECTION_REJECTED: 40}


def test_NEGATIVE_the_2026_09_13_MEASURED_dict_is_untouched():
    """A sibling dict, not an edit: `measured_verdict()`, `note()` and
    `supply_demand/rules_info.py` all read `MEASURED` by key."""
    m = BD.MEASURED
    assert m["run_date"] == "2026-09-13"
    assert m["scripts"] == "backend/scripts/bonde_audit/"
    assert m["lift_21d"] == -3.11 and m["lift_ci"] == (-5.28, -1.16)
    assert m["tier_strong_med"] == 0.37 and m["tier_explosive_med"] == 0.45
    assert m["panel_bars"] == 45425 and m["panel_dates"] == 24
    assert "steady" not in m and "lift" not in m


def test_NEGATIVE_the_note_under_the_board_did_not_move():
    """Snapshot of the pre-change sentence. `note()` is the board's own
    paragraph and belongs to the 2026-09-13 study; the steady label is served
    separately, under the Steady header, and must not have leaked into it."""
    plain = BD.note(1051, 2076, {"pivot": 12})
    assert len(plain) == 1620
    assert hashlib.sha256(plain.encode()).hexdigest() == \
        "08a979a221c76c4e0b0ae4c69c141bc21201a7abd440e66829e8f4f571592409"
    full = BD.note(1051, 2076, {"pivot": 12},
                   reg={"scanners_paused": False},
                   n_mismatch=164, n_mismatch_pass=147)
    assert len(full) == 2082
    assert hashlib.sha256(full.encode()).hexdigest() == \
        "7dc554958b3407549523bfc70ca7871ec45543a92dfad67f966fb12ced74396f"
    assert "STEADY TIER" not in plain and MINUS + "0.21pp" not in plain


def test_NEGATIVE_the_board_still_PLACES_steady_rows(monkeypatch):
    """LABEL IT, not drop it. A name in the 5-25% band still lands in the
    steady section with the label served beside it — same end-to-end
    monkeypatch shape as `test_bonde.py`."""
    from sepa import scanner, board_metrics as BM

    def scan_row(symbol, rev_series, sales):
        return {"symbol": symbol, "name": None, "last_close": 10.0,
                "fundamentals": {"rev_q_series": rev_series, "sales": sales}}

    rows = [
        scan_row("STDY", [112_000_000, 0, 0, 0, 100_000_000],
                 {"score": 60, "tier": "steady", "growth_yoy_pct": 12.0,
                  "accelerating": True, "consecutive_growth_q": 3}),
        scan_row("BIGG", [200_000_000, 0, 0, 0, 100_000_000],
                 {"score": 90, "tier": "strong", "growth_yoy_pct": 100.0,
                  "accelerating": True, "consecutive_growth_q": 4}),
    ]
    monkeypatch.setattr(scanner, "load_latest", lambda *a, **k: {"all_results": rows})
    monkeypatch.setattr(BD, "_pivots", lambda *a, **k: {})
    monkeypatch.setattr(BD, "regime_state", lambda *a, **k: {"scanners_paused": False})
    monkeypatch.setattr(BM, "attach", lambda *a, **k: None)
    monkeypatch.setattr(FS, "record", lambda *a, **k: 0)
    monkeypatch.setattr(FS, "newly_found", lambda *a, **k: set())
    monkeypatch.setattr(FS, "first_seen_map", lambda *a, **k: {})

    b = BD.board()
    got = {k: [r["symbol"] for r in v] for k, v in b["sections"].items()}
    assert got[BD.SECTION_STEADY] == ["STDY"], "the tier was dropped or hidden"
    assert b["counts"][BD.SECTION_STEADY] == 1
    assert b["measured"]["steady"] == BD.steady_verdict()
    # the label changed no ordering and no other section
    assert got[BD.SECTION_STRONG] == ["BIGG"]


# ──────────────────────────────────────────── source guards
def test_SOURCE_GUARD_the_constants_are_a_literal_in_bonde_and_the_artifact_stays_research():
    """Rule #10 — research never becomes a gate by accident. The served module
    carries a frozen dict and cites the DOC; it never reads the JSON."""
    src = Path(BD.__file__).read_text(encoding="utf-8")
    assert "STEADY_MEASURED = {" in src
    assert "board_growth_measured" not in src
    assert "docs/research/board_growth_2026_09_21.md" in src
    assert "backend/scripts/board_growth_replay.py" in src
    assert str(ARTIFACT.name) not in src


def test_SOURCE_GUARD_the_doc_carries_the_labelled_tier_section():
    doc = (ROOT / "docs" / "sepa" / "bonde_board.md").read_text(
        encoding="utf-8")
    assert "## 10. The steady tier, labelled — 2026-09-21" in doc
    assert MINUS + "0.21pp" in doc
    assert MINUS + "0.40, " + MINUS + "0.04" in doc
    assert "spans zero" in doc
    assert "leave it, label it, or" in doc.lower()
    assert "Read as **LABEL IT**" in doc
    assert "dropping 666 names is not" in doc
    assert "Nothing is hidden, dropped, filtered,\nre-sorted or de-prioritised" in doc
    assert "docs/research/board_growth_2026_09_21.md" in doc
    # the §1 tier table's un-intervalled steady row now carries its footnote
    assert "steady 5–25%" in doc
    assert "See §10." in doc
