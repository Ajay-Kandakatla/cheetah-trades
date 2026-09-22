"""Pins for the 🎪 promo-circuit first-tag forward study (2026-09-21).

"Ship the backtest with the claim": the verdict that reaches the chip, the
board and the doc is read back out of ``backend/scripts/promo_tag_measured.json``,
which ``backend/scripts/promo_tag_study.py`` produced.  This file pins that
artifact, pins that ``promo_curate.MEASURED`` agrees with it field for field,
and pins the study's own honesty rules — a cell the doc quotes must clear the
cluster minimum, and a cell that does not must print no interval at all.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "backend" / "scripts" / "promo_tag_measured.json"
SCRIPT = ROOT / "backend" / "scripts" / "promo_tag_study.py"
DOC = ROOT / "docs" / "catalysts" / "promo_tag_study_2026_09_21.md"
LANE_DOC = ROOT / "docs" / "catalysts" / "promo_curation.md"

PRIMARY = "pooled|5|open|shotgun_kept|all"
MINUS = "−"


@pytest.fixture(scope="module")
def art() -> dict:
    return json.loads(ARTIFACT.read_text())


@pytest.fixture(scope="module")
def doc() -> str:
    return DOC.read_text()


@pytest.fixture(scope="module")
def doc_flat(doc: str) -> str:
    """The doc with markdown emphasis stripped and whitespace collapsed, so a
    phrase check is not defeated by where the paragraph happened to wrap."""
    return " ".join(doc.replace("**", "").split())


@pytest.fixture(scope="module")
def measured() -> dict:
    from catalysts import promo_curate as PCU

    return PCU.MEASURED


# --------------------------------------------------------------------------
# the package exists and says what it is
# --------------------------------------------------------------------------


def test_the_script_the_artifact_and_the_doc_all_ship():
    for path in (SCRIPT, ARTIFACT, DOC, LANE_DOC):
        assert path.exists(), f"{path.name} must ship with the claim"


def test_both_surfaces_carry_the_rule_10_banner(art, doc):
    assert art["header"].startswith("NOT A SIGNAL, NOT A GATE")
    assert "NOT A SIGNAL, NOT A GATE" in doc


def test_the_question_is_stored_verbatim(art):
    assert "pull data from social media and chatter" in art["asked"]
    assert art["asked_on"] == "2026-09-21"


# --------------------------------------------------------------------------
# the primary cell
# --------------------------------------------------------------------------


def test_the_primary_cell_is_the_pooled_five_session_open_entry(art):
    assert art["primary_key"] == PRIMARY
    reason = art["primary_reason"].lower()
    assert "open" in reason and "cluster" in reason


def test_the_primary_numbers_are_pinned(art):
    cell = art["lines"][PRIMARY]
    assert cell["n"] == 1231
    assert cell["n_date_clusters"] == 31
    assert cell["n_symbol_clusters"] == 614
    assert cell["median"] == pytest.approx(-0.0730107526881721)
    assert cell["placebo_median"] == pytest.approx(-0.0252365930599369)
    assert cell["delta"] == pytest.approx(-0.0477741596282352)
    assert cell["ci_date"] == pytest.approx([-0.07194734256908117, -0.034083210376948773])
    assert cell["ci_symbol"] == pytest.approx([-0.06496903727591287, -0.03431338961847651])
    assert cell["win_pct"] == pytest.approx(29.244516653127537)
    assert cell["median_dd"] == pytest.approx(-0.1418439716312056)


def test_the_primary_interval_excludes_zero_on_BOTH_clusterings(art):
    cell = art["lines"][PRIMARY]
    assert cell["date_excl0"] is True and cell["symbol_excl0"] is True
    assert cell["ci_date"][1] < 0, "the doc calls this significant"
    assert cell["ci_symbol"][1] < 0


def test_the_tagged_name_loses_to_its_OWN_matched_peers_not_to_the_market(art):
    cell = art["lines"][PRIMARY]
    assert cell["median"] < cell["placebo_median"] < 0
    assert cell["delta"] == pytest.approx(cell["median"] - cell["placebo_median"])
    context = art["benchmark_context"]
    assert context["symbol"] == "RSP", "equal-weight, never SPY"
    assert cell["placebo_median"] < context["median_ret_5"], (
        "the placebo carries the cohort's small-cap tilt — that is why it is the comparison"
    )


def test_the_doc_prints_the_primary_numbers(art, doc):
    cell = art["lines"][PRIMARY]
    plain = doc.replace("**", "")
    assert f"{MINUS}{abs(cell['delta']) * 100:.2f}pp" in plain
    assert f"{MINUS}{abs(cell['median']) * 100:.2f}%" in plain
    assert f"{MINUS}{abs(cell['placebo_median']) * 100:.2f}%" in plain
    assert "1,231 events" in plain


# --------------------------------------------------------------------------
# day one is a coin flip — the doc's one NON-significant claim
# --------------------------------------------------------------------------


def test_the_one_session_cell_spans_zero(art):
    cell = art["lines"]["pooled|1|open|shotgun_kept|all"]
    assert cell["ci_date"][0] < 0 < cell["ci_date"][1], "the doc calls day one a coin flip"
    assert cell["date_excl0"] is False


def test_the_close_entry_variant_is_milder_than_the_open_entry(art):
    close = art["lines"]["pooled|5|close|shotgun_kept|all"]["delta"]
    open_ = art["lines"][PRIMARY]["delta"]
    assert close > open_, "the tag-day close already carries part of the move"
    assert close < 0


# --------------------------------------------------------------------------
# the honesty rule: no interval below the cluster minimum
# --------------------------------------------------------------------------


def test_the_cluster_minimum_is_recorded(art):
    assert art["min_clusters"] == 20
    assert art["draws"] == 2000
    assert art["k_placebo"] == 5


@pytest.mark.parametrize(
    "key", ["pooled|21|open|shotgun_kept|all", "pooled|5|open|shotgun_kept|tier:S",
            "OOS|5|open|shotgun_kept|all"]
)
def test_NEGATIVE_a_thin_cell_carries_NO_interval(art, key):
    """A cell under the cluster minimum must print n/a, never a number that
    looks like a measurement."""
    cell = art["lines"][key]
    assert cell["n_date_clusters"] < art["min_clusters"]
    assert cell["ci_date"] in (None, [None, None]) or cell["ci_date"][0] is None


@pytest.mark.parametrize("key", [PRIMARY, "pooled|5|close|shotgun_kept|all",
                                 "pooled|1|open|shotgun_kept|all",
                                 "pooled|5|open|shotgun_kept|tier:A",
                                 "pooled|5|open|shotgun_kept|tier:B"])
def test_every_cell_the_doc_quotes_an_interval_for_clears_the_minimum(art, key):
    cell = art["lines"][key]
    assert cell["n_date_clusters"] >= art["min_clusters"], key
    assert cell["ci_date"] and cell["ci_date"][0] is not None


def test_the_doc_never_quotes_the_21_session_cell_as_a_result(doc_flat):
    assert "not quotable" in doc_flat
    assert "65 events" in doc_flat


# --------------------------------------------------------------------------
# out of sample: the sign agrees, the evidence does not
# --------------------------------------------------------------------------


def test_the_out_of_sample_leg_is_a_SIGN_CHECK_not_a_measurement(art, doc_flat):
    oos = art["lines"]["OOS|5|open|shotgun_kept|all"]
    is_ = art["lines"]["IS|5|open|shotgun_kept|all"]
    assert oos["n_date_clusters"] == 8
    assert oos["delta"] < 0 and is_["delta"] < 0, "the sign agrees"
    assert abs(oos["delta"]) < abs(is_["delta"]), "and the magnitude does not"
    assert art["measured_literal"]["oos_clean"] is False
    assert "sign check, not a measurement" in doc_flat


def test_the_rerun_date_is_carried_everywhere(art, doc, measured):
    assert art["rerun_after"] == "2026-10-12"
    assert measured["rerun_after"] == "2026-10-12"
    assert "2026-10-12" in doc


# --------------------------------------------------------------------------
# tiers and accounts
# --------------------------------------------------------------------------


def test_tier_A_is_less_bad_than_tier_B_and_both_intervals_sit_below_zero(art):
    a = art["lines"]["pooled|5|open|shotgun_kept|tier:A"]
    b = art["lines"]["pooled|5|open|shotgun_kept|tier:B"]
    assert a["delta"] > b["delta"]
    assert a["ci_date"][1] < 0 and b["ci_date"][1] < 0


def test_NEGATIVE_no_per_account_cut_earns_an_interval(art, doc_flat):
    accounts = art["accounts_pooled_5_open"]
    assert len(accounts) == 13, "13 accounts clear 20 events"
    for name, row in accounts.items():
        assert row["delta"] < 0, f"{name} points positive — the doc says all 13 are negative"
        assert row["n_date_clusters"] < art["min_clusters"], name
        assert row["ci_date"] is None or row["ci_date"][0] is None, name
    assert "not one clears the cluster minimum" in doc_flat


# --------------------------------------------------------------------------
# what the cohort is
# --------------------------------------------------------------------------


def test_the_cohort_is_a_microcap_tape(art, doc):
    rates = art["base_rates"]
    assert rates["n_events"] == 3452
    assert rates["under_2_pct"] == pytest.approx(39.59316037735849)
    assert rates["under_5m_pct"] == pytest.approx(69.36910377358491)
    assert rates["dumped_21_pct"] == pytest.approx(31.84983348471087)
    assert rates["median_dd_21"] == pytest.approx(-0.35274403016338496)
    for literal in ("39.6%", "69.4%", "31.8%"):
        assert literal in doc


# --------------------------------------------------------------------------
# the served verdict agrees with the artifact
# --------------------------------------------------------------------------


def test_the_served_MEASURED_agrees_with_the_artifact_field_for_field(art, measured):
    lit = art["measured_literal"]
    assert measured is not None, "the study has run; the chip must stop saying 'pending'"
    for key in ("as_of", "primary", "n_5", "n_date_clusters_5", "rerun_after", "verdict"):
        assert measured[key] == lit[key], key
    assert measured["delta_5"] == pytest.approx(lit["delta_5"])
    assert measured["ci_date_5"] == pytest.approx(lit["ci_date_5"])
    assert measured["ci_symbol_5"] == pytest.approx(lit["ci_symbol_5"])
    assert measured["oos_5"]["clusters"] == lit["oos_5"]["clusters"]


def test_the_served_MEASURED_matches_the_primary_cell(art, measured):
    cell = art["lines"][PRIMARY]
    assert measured["n_5"] == cell["n"]
    assert measured["delta_5"] == pytest.approx(cell["delta"])
    assert measured["ci_date_5"] == pytest.approx(cell["ci_date"])


def test_the_verdict_says_inverted_and_names_what_it_is_NOT(measured):
    verdict = measured["verdict"]
    assert "inverted" in verdict
    assert "not a source of entries" in verdict


def test_the_served_verdict_points_back_at_its_own_provenance(measured):
    assert measured["script"] == "backend/scripts/promo_tag_study.py"
    assert measured["doc"] == "docs/catalysts/promo_tag_study_2026_09_21.md"
    assert measured["artifact"] == "backend/scripts/promo_tag_measured.json"


# --------------------------------------------------------------------------
# negatives — the boundary between research and the app
# --------------------------------------------------------------------------


def test_NEGATIVE_an_inverted_read_never_becomes_a_short_or_a_gate(art, doc_flat):
    assert "not a short signal" in doc_flat.lower()
    assert "not_an_edge" in art["limits"]
    hits = subprocess.run(
        ["git", "grep", "-l", "promo_tag_measured", "--", "backend", "frontend"],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout.split()
    allowed = {"backend/tests/test_promo_tag_measured.py",
               "backend/catalysts/promo_curate.py"}
    assert set(hits) <= allowed, f"a served module reads the research artifact: {hits}"


def test_the_artifact_lists_its_own_limits(art, doc_flat):
    for key in ("oos_clusters", "in_sample_bias", "h21", "match_fallback",
                "per_account", "not_an_edge"):
        assert art["limits"][key], key
    assert "1,516 events" in doc_flat, "the fallback count is stated, not buried"


def test_the_doc_puts_open_questions_to_him(doc):  # noqa: D103
    assert "## 8. His call" in doc
    tail = doc.split("## 8. His call", 1)[1]
    assert tail.count("?") >= 4


def test_NEGATIVE_the_study_never_says_bounce(doc):
    assert "bounce" not in doc.lower(), 'every surface he reads says "reversal"'


def test_an_independent_rerun_reproduced_every_field(art):
    """The strongest claim in the package: a separate run the same evening,
    re-fetching from the provider instead of reading the price cache, produced
    the identical measured literal. If that ever stops being true the doc's
    section 6 is wrong."""
    repro = art["reproductions"]["independent_rerun"]
    lit = art["measured_literal"]
    for key in sorted(lit):
        assert repro[key] == lit[key], key
    assert set(art["reproductions"]["independent_rerun_identical_fields"]) == set(lit)


def test_the_seed_11_run_moves_only_the_interval(art):
    seed11 = art["reproductions"]["seed_11"]
    lit = art["measured_literal"]
    assert seed11["delta_5"] == pytest.approx(lit["delta_5"]), "the point estimate is seed-free"
    assert seed11["n_5"] == lit["n_5"]
    for a, b in zip(seed11["ci_date_5"], lit["ci_date_5"]):
        assert abs(a - b) < 0.0006, "the bootstrap interval moves under 0.06pp between seeds"
