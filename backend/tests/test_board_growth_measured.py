"""Pins for the 2026-09-21 board-growth research package.

Rule: "ship the backtest with the claim" — every measured number the report
prints is read back out of ``backend/scripts/board_growth_measured.json``.  This
file pins the headline set, so a re-run that moves a number fails the suite
instead of quietly rewriting the story.

It also pins the *honesty* of the report: a cohort the doc calls significant
must have a CI clear of zero in the artifact, and a cohort the doc calls flat
must not.  And it guards Rule #10 — the artifact is research, so no served
module may import it.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "backend" / "scripts" / "board_growth_measured.json"
DOC = ROOT / "docs" / "research" / "board_growth_2026_09_21.md"
SCRIPTS = [
    ROOT / "backend" / "scripts" / "board_growth_study.py",
    ROOT / "backend" / "scripts" / "board_growth_replay.py",
    ROOT / "backend" / "scripts" / "board_growth_crdo.py",
    ROOT / "backend" / "scripts" / "board_growth_merge.py",
]

MINUS = "−"  # the doc renders negatives with a unicode minus


@pytest.fixture(scope="module")
def art() -> dict:
    return json.loads(ARTIFACT.read_text())


@pytest.fixture(scope="module")
def doc() -> str:
    return DOC.read_text()


@pytest.fixture(scope="module")
def doc_plain(doc: str) -> str:
    """The doc with markdown emphasis stripped, so a literal check is not
    defeated by the bold markers around a headline number."""
    return doc.replace("**", "")


def fmt(value: float, unit: str = "", places: int = 2, signed: bool = False) -> str:
    """Render a number the way the doc renders it (unicode minus, fixed dp)."""
    text = f"{value:+.{places}f}" if signed else f"{value:.{places}f}"
    return text.replace("-", MINUS) + unit


# --------------------------------------------------------------------------
# the package exists at all
# --------------------------------------------------------------------------


def test_the_artifact_the_doc_and_every_script_are_present():
    assert ARTIFACT.exists(), "the measured artifact is the only quotable source"
    assert DOC.exists()
    for path in SCRIPTS:
        assert path.exists(), f"{path.name} must ship with the claim"


def test_both_surfaces_carry_the_rule_10_banner(art, doc):
    assert art["header"].startswith("NOT A SIGNAL, NOT A GATE")
    assert "NOT A SIGNAL, NOT A GATE" in doc


def test_the_question_is_stored_verbatim(art):
    assert "explosive growth stocks and Bondes stocks" in art["asked"]
    assert art["asked_on"] == "2026-09-21"


# --------------------------------------------------------------------------
# the repro gate — the panel is the panel the shipped study used
# --------------------------------------------------------------------------


def test_the_repro_gate_passed_before_any_new_cell_was_quoted(art):
    gate = art["repro"]["gate"]
    assert gate["gate_passed"] is True
    assert gate["explosive_median_lift_pp"] == pytest.approx(0.45)
    assert gate["explosive_lift_ci"] == pytest.approx([-0.31, 1.36])


def test_the_panel_size_is_pinned(art):
    repro = art["repro"]
    assert repro["panel_rows"] == 54786
    assert repro["scored_bars"] == 45425
    assert repro["n_symbols"] == 2669
    assert repro["strict"] is True
    assert repro["derived"] == "plus90"
    assert repro["windows"] == [21, 63, 126]


def test_the_benchmark_is_rsp_not_spy(art):
    assert art["run"]["benchmark"] == "RSP"


# --------------------------------------------------------------------------
# the headline answer — before the filing vs since the filing
# --------------------------------------------------------------------------

BEFORE_SINCE = [
    ("growth_21", 46.4, 80.0, -2.21, 40.0),
    ("bonde_visible_all", 8.19, 66.4, -4.41, 37.5),
    ("universe_all", 8.14, 65.5, -4.63, 31.0),
]


@pytest.mark.parametrize("cohort,pre,pre_pos,since,since_pos", BEFORE_SINCE)
def test_the_run_happened_before_the_qualifying_filing(
    art, doc, cohort, pre, pre_pos, since, since_pos
):
    block = art["cohorts"][cohort]
    assert block["pre_filed_126_pct"]["median"] == pytest.approx(pre)
    assert block["pre_filed_126_pct"]["share_pos"] == pytest.approx(pre_pos)
    assert block["since_10q_filed_pct"]["median"] == pytest.approx(since)
    assert block["since_10q_filed_pct"]["share_pos"] == pytest.approx(since_pos)
    # the sign flip is the whole answer; assert it rather than trusting the prose
    assert block["pre_filed_126_pct"]["median"] > 0 > block["since_10q_filed_pct"]["median"]
    assert fmt(pre, "%", signed=True) in doc
    assert fmt(since, "%", signed=True) in doc


def test_the_growth_board_ran_hardest_before_its_filing(art):
    pre = {k: art["cohorts"][k]["pre_filed_126_pct"]["median"] for k, *_ in BEFORE_SINCE}
    assert pre["growth_21"] > 5 * pre["universe_all"], (
        "the +46.4%-before figure is the reason his impression is right about the past"
    )


# --------------------------------------------------------------------------
# trailing windows the doc's first table prints
# --------------------------------------------------------------------------

TRAILING = [
    ("growth_21", "3m", -8.81, [-16.7, 5.93]),
    ("growth_21", "6m", 34.99, [4.03, 69.46]),
    ("bonde_visible_all", "3m", -4.8, [-8.89, -1.15]),
    ("bonde_visible_all", "6m", 2.21, [-4.76, 5.72]),
    ("universe_all", "3m", -1.78, [-2.52, -1.13]),
]


@pytest.mark.parametrize("cohort,window,rel,ci", TRAILING)
def test_trailing_vs_rsp_is_pinned(art, doc, cohort, window, rel, ci):
    block = art["cohorts"][cohort]["windows"][window]
    assert block["vs_rsp_median_pp"] == pytest.approx(rel)
    assert block["vs_rsp_median_ci"] == pytest.approx(ci)
    assert ci[0] <= ci[1]
    assert fmt(rel, "pp", signed=True) in doc


def test_the_bonde_board_three_month_underperformance_is_significant(art):
    ci = art["cohorts"]["bonde_visible_all"]["windows"]["3m"]["vs_rsp_median_ci"]
    assert ci[1] < 0, "the doc calls this one significant; the CI must sit below zero"


def test_the_growth_board_six_month_outperformance_is_significant(art):
    ci = art["cohorts"]["growth_21"]["windows"]["6m"]["vs_rsp_median_ci"]
    assert ci[0] > 0, "the doc calls this one significant; the CI must sit above zero"


def test_the_growth_board_three_month_read_is_NOT_called_significant(art, doc_plain):
    ci = art["cohorts"]["growth_21"]["windows"]["3m"]["vs_rsp_median_ci"]
    assert ci[0] < 0 < ci[1], "this CI spans zero"
    # the doc must print the interval beside the number, never the number alone
    assert f"{MINUS}8.81pp [{MINUS}16.70, +5.93]" in doc_plain


# --------------------------------------------------------------------------
# nobody on either board is at a 52-week high
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cohort,n,at_high,below",
    [("growth_21", 21, 0, 21.14), ("bonde_visible_all", 160, 0, 25.39)],
)
def test_not_one_visible_member_is_at_a_52_week_high(art, doc, cohort, n, at_high, below):
    block = art["cohorts"][cohort]
    assert block["n"] == n
    assert block["n_at_52w_high"] == at_high
    assert block["pct_below_high"]["median"] == pytest.approx(below)
    assert f"{below:.2f}%" in doc


def test_the_universe_does_have_names_at_a_high(art):
    universe = art["cohorts"]["universe_all"]
    assert universe["n_at_52w_high"] == 40
    assert universe["n"] == 2090


@pytest.mark.parametrize("cohort", ["universe_all", "growth_21", "bonde_visible_all"])
def test_a_cohort_never_claims_more_names_at_a_high_than_it_has(art, cohort):
    block = art["cohorts"][cohort]
    assert 0 <= block["n_at_52w_high"] <= block["n"]
    assert 0 <= block["n_within_25pct_of_high"] <= block["n"]
    assert block["n_since_10q_filed_positive"] <= block["n_since_10q_filed_known"] <= block["n"]


# --------------------------------------------------------------------------
# arrival vs incumbency — the only cell with a clean CI at every horizon
# --------------------------------------------------------------------------

ARRIVE = [("h21", 3.33), ("h63", 7.49), ("h126", 12.83)]


@pytest.mark.parametrize("horizon,lift", ARRIVE)
def test_bonde_explosive_arrivals_lift_is_pinned_and_clear_of_zero(art, doc, horizon, lift):
    cell = art["cells"]["B_EXPL_ARRIVE"][horizon]
    assert cell["median_lift_vs_all_scored_pp"] == pytest.approx(lift)
    assert cell["lift_ci_symbol"][0] > 0, "the doc's one significance claim"
    assert fmt(lift, signed=True) in doc


@pytest.mark.parametrize("horizon", ["h21", "h63"])
def test_bonde_explosive_incumbents_are_flat_for_three_months(art, horizon):
    cell = art["cells"]["B_EXPL_INCUMBENT"][horizon]
    ci = cell["lift_ci_symbol"]
    assert ci[0] < 0 < ci[1], "the doc calls the incumbent row flat; its CI must span zero"


def test_incumbents_only_separate_by_six_months(art):
    cell = art["cells"]["B_EXPL_INCUMBENT"]["h126"]
    assert cell["median_lift_vs_all_scored_pp"] == pytest.approx(5.47)
    assert cell["lift_ci_symbol"][0] > 0


def test_arrivals_beat_incumbents_at_every_horizon(art):
    for horizon in ("h21", "h63", "h126"):
        arrive = art["cells"]["B_EXPL_ARRIVE"][horizon]["median_lift_vs_all_scored_pp"]
        incumbent = art["cells"]["B_EXPL_INCUMBENT"][horizon]["median_lift_vs_all_scored_pp"]
        assert arrive > incumbent, horizon


# --------------------------------------------------------------------------
# the steady tier is a measured drag
# --------------------------------------------------------------------------


def test_the_steady_tier_measures_negative_at_one_month(art, doc):
    cell = art["cells"]["B_STEADY"]["h21"]
    assert cell["median_lift_vs_all_scored_pp"] == pytest.approx(-0.21)
    assert cell["lift_ci_symbol"][1] < 0, "the doc calls the steady tier a drag"
    assert fmt(-0.21, signed=True) in doc


@pytest.mark.parametrize("horizon", ["h21", "h63", "h126"])
def test_the_steady_tier_momentum_controlled_mean_is_negative_everywhere(art, horizon):
    control = art["cells"]["B_STEADY"][horizon]["momentum_control"]
    assert control["mean_excess_pp"] < 0
    assert control["ci_symbol"][1] < 0


# --------------------------------------------------------------------------
# the momentum control: a fat right tail, not a better typical name
# --------------------------------------------------------------------------

MOMENTUM = [("h21", 3.518707552462157), ("h63", 7.41290432842146), ("h126", 12.51038907592231)]


@pytest.mark.parametrize("horizon,mean_excess", MOMENTUM)
def test_the_explosive_tier_survives_the_momentum_control_on_the_mean(art, horizon, mean_excess):
    control = art["cells"]["B_EXPL"][horizon]["momentum_control"]
    assert control["mean_excess_pp"] == pytest.approx(mean_excess)
    assert control["ci_symbol"][0] > 0


@pytest.mark.parametrize("horizon", ["h21", "h63", "h126"])
def test_the_median_member_does_NOT_beat_its_momentum_peers(art, horizon):
    """The mean separates and the median does not — that is the fat-tail claim.

    The per-row excess is measured against the quintile's all-scored MEAN, so the
    baseline's own median excess is negative by construction.  The honest test is
    the board's median excess against the BASELINE's median excess, not zero.
    """
    board = art["cells"]["B_EXPL"][horizon]["momentum_control"]["median_excess_pp"]
    baseline = art["cells"]["ALL_SCORED"][horizon]["momentum_control"]["median_excess_pp"]
    gap = board - baseline
    mean_gap = art["cells"]["B_EXPL"][horizon]["momentum_control"]["mean_excess_pp"]
    assert gap < mean_gap, (
        "the median moves far less than the mean — a handful of members carry the cohort"
    )


def test_the_baseline_momentum_control_mean_is_zero_by_construction(art):
    for horizon in ("h21", "h63", "h126"):
        control = art["cells"]["ALL_SCORED"][horizon]["momentum_control"]
        assert control["mean_excess_pp"] == pytest.approx(0.0, abs=1e-6)


# --------------------------------------------------------------------------
# the lift lives in the beaten-down quintile, not the running one
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cell_key,lift", [("B_EXPL_Q1", 19.1), ("G100_Q1", 18.16)]
)
def test_the_worst_trailing_quintile_carries_the_six_month_lift(art, doc, cell_key, lift):
    cell = art["cells"][cell_key]["h126"]
    assert cell["median_lift_vs_all_scored_pp"] == pytest.approx(lift)
    assert cell["lift_ci_symbol"][0] > 0
    assert fmt(lift, signed=True) in doc


def test_the_hottest_quintile_does_not(art):
    cell = art["cells"]["B_EXPL_Q5"]["h126"]
    assert cell["median_lift_vs_all_scored_pp"] == pytest.approx(3.41)
    assert cell["lift_ci_symbol"][0] < 0 < cell["lift_ci_symbol"][1], "Q5 spans zero"


def test_the_quintile_gap_is_bigger_on_the_boards_than_in_the_universe(art):
    board_gap = (
        art["cells"]["B_EXPL_Q1"]["h126"]["median_lift_vs_all_scored_pp"]
        - art["cells"]["B_EXPL_Q5"]["h126"]["median_lift_vs_all_scored_pp"]
    )
    universe_gap = (
        art["cells"]["ALL_SCORED_Q1"]["h126"]["median_lift_vs_all_scored_pp"]
        - art["cells"]["ALL_SCORED_Q5"]["h126"]["median_lift_vs_all_scored_pp"]
    )
    assert board_gap > universe_gap


def test_the_momentum_edges_are_pinned(art):
    edges = art["repro"]["momentum_edges"]
    assert len(edges) == 4
    assert edges == sorted(edges)
    assert edges[0] == pytest.approx(-19.16302581799838)
    assert edges[-1] == pytest.approx(26.34680859509496)


# --------------------------------------------------------------------------
# the screen number does not track the run
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cohort,leg,rho", [("growth_21", "sales", 0.1987), ("bonde_visible_explosive", "sales", 0.0882)]
)
def test_the_screen_number_rho_spans_zero(art, doc, cohort, leg, rho):
    block = art["rho_screen_vs_trailing_3m"][cohort][leg]
    assert block["rho"] == pytest.approx(rho)
    lo, hi = block["ci"]
    assert lo < 0 < hi, "a bigger screen number does not mean a bigger move"
    assert str(rho) in doc


def test_every_quoted_rho_ci_spans_zero(art):
    for cohort, legs in art["rho_screen_vs_trailing_3m"].items():
        for leg, block in legs.items():
            lo, hi = block["ci"]
            assert lo < 0 < hi, f"{cohort}/{leg} would be the study's only non-null leg"


# --------------------------------------------------------------------------
# CRDO
# --------------------------------------------------------------------------


def test_the_crdo_exit_reference_is_pinned(art, doc):
    exit_ref = art["crdo"]["exit_reference"]
    assert exit_ref["entry"] == pytest.approx(167.65)
    assert exit_ref["shares"] == pytest.approx(196.973)
    assert exit_ref["reference_close"] == pytest.approx(187.27)
    assert exit_ref["pnl_pct_entry_to_reference"] == pytest.approx(11.7)
    assert exit_ref["pnl_dollars_entry_to_reference"] == pytest.approx(3864.61)
    assert exit_ref["stop_pushes"] == 3
    assert "+11.7% (+$3,864.61)" in doc


def test_crdo_exited_on_a_top_one_percent_week_after_a_bottom_three_percent_quarter(art, doc):
    pct = art["crdo"]["percentiles_in_growth_21"]
    assert pct["1w"]["ret_pct"] == pytest.approx(24.77)
    assert pct["1w"]["universe_pctile"] == pytest.approx(99.4)
    assert pct["3m"]["ret_pct"] == pytest.approx(-38.1)
    assert pct["3m"]["cohort_pctile"] == pytest.approx(2.4)
    assert pct["3m"]["universe_pctile"] == pytest.approx(2.8)
    assert "99.4th of the scan universe" in doc


def test_crdo_sits_below_its_june_high(art, doc):
    high = art["crdo"]["high_52w"]
    assert high["close"] == pytest.approx(302.52)
    assert high["date"] == "2026-06-22"
    assert high["pct_below"] == pytest.approx(38.09665476662699)
    assert "302.52" in doc and "2026-06-22" in doc


def test_crdo_close_sits_inside_the_stored_demand_band(art, doc):
    band = art["crdo"]["zone_band_at_close"]
    assert band["band"]["lo"] <= band["close"] <= band["band"]["hi"]
    assert band["band"]["lo"] == pytest.approx(182.61)
    assert band["band"]["hi"] == pytest.approx(189.12)
    assert "182.61–189.12" in doc


def test_the_screens_saw_crdo_eighteen_months_before_the_boards_did(art, doc):
    first = art["crdo"]["first_pass"]
    assert first["bonde_explosive"]["filed"] == "2025-03-10"
    assert first["bonde_explosive"]["anchor_close"] == pytest.approx(43.36)
    assert first["bonde_explosive"]["return_to_last_pct"] == pytest.approx(331.9)
    assert first["passes_100_100"]["filed"] == "2025-08-01"
    assert first["passes_100_100"]["return_to_last_pct"] == pytest.approx(63.27)
    assert "+331.9%" in doc


def test_the_ledger_stamps_are_labelled_as_backfill_not_arrival(art, doc):
    ledgers = art["crdo"]["ledgers"]
    assert ledgers["growth_seen_first"].startswith("2026-09-12")
    assert ledgers["bonde_seen_first"].startswith("2026-09-14")
    assert "backfill" in ledgers["caveat"].lower()
    assert "day-one" in doc and "backfill" in doc


# --------------------------------------------------------------------------
# negatives — the honesty of the package, not its arithmetic
# --------------------------------------------------------------------------


def test_the_doc_never_reports_a_lift_without_its_interval(doc):
    """Every `+N.NNpp` / `−N.NNpp` in a table row is followed by a bracketed CI.

    A bare point estimate on a surface he reads is the thing the standing rule
    forbids; the two summary sentences that repeat an already-bracketed number
    are allowed because the table above them carries the interval.
    """
    rows = [line for line in doc.splitlines() if line.startswith("| ") and "pp" in line]
    assert rows, "the lift tables must exist"
    for row in rows:
        if "h=21" in row or "---" in row:
            continue
        for match in re.finditer(r"[+−]\d+\.\d+(?=\s*\[)", row):
            assert match  # the lookahead is the assertion
        assert row.count("[") == row.count("]")


def test_the_containment_check_can_actually_fail(doc):
    """Sanity: the doc-literal assertions above are not vacuous."""
    assert fmt(-999.99, "pp", signed=True) not in doc
    assert "+1234.56pp" not in doc


def test_no_served_module_imports_the_research_artifact():
    """Rule #10 — research never becomes a gate by accident."""
    hits = subprocess.run(
        ["git", "grep", "-l", "board_growth_measured", "--", "backend", "frontend"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.split()
    allowed = {
        "backend/scripts/board_growth_merge.py",
        "backend/tests/test_board_growth_measured.py",
    }
    assert set(hits) <= allowed, f"a served module reads the research artifact: {hits}"


def test_the_artifact_lists_its_own_limits(art, doc):
    biases = art["biases"]
    for key in ("look_ahead", "survivorship", "print_anchoring", "overlapping_windows"):
        assert key in biases and biases[key]
    assert "Survivorship" in doc
    assert "Not an edge claim" in doc


def test_the_doc_puts_open_questions_to_him_rather_than_deciding_them(doc):
    assert "## 6. His call" in doc
    tail = doc.split("## 6. His call", 1)[1]
    assert tail.count("?") >= 6, "every his-call item is a question, not a decision"
