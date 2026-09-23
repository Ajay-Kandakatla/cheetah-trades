"""💎 Capital quality — the graded "low capital, high return" read.

Ajay 2026-09-22: *"quality like very less capital and hi ROI."*

THE NEGATIVES CARRY THIS FILE, and there is one specific lie it exists to make
impossible: **an UNKNOWN rendering as a FAIL.** A name whose balance sheet could
not be read must never be shown as a name that was read and found wanting. Every
component, every count, every grade and the ranking itself is pinned against
that confusion here.

The other half is the pair of numbers nobody is allowed to invent: the peer
floor (which is the house's, and is pinned equal to it) and the MEASURED flag
(which cannot become True while no study exists).
"""
from __future__ import annotations

import json
import math
import os

import pytest

from growth import capital_quality as CQ


# ───────────────────────────────────────────────────────────────── builders
def row(**kw) -> dict:
    """A board row with every field the read touches, all answerable."""
    base = {
        "symbol": "TEST",
        "sector": "Technology",
        "balance_meaningful": True,
        "cash": 10_000.0,
        "debt": 5_000.0,
        "fcf_yield": 3.5,
        "shares_yoy_pct": -1.2,
        "roce_pct": 30.0,
        "capex_intensity_pct": 3.0,
        "capital_period": "Q2 2026",
        "capital_period_end": "2026-06-30",
        "capital_reasons": {},
    }
    base.update(kw)
    return base


def peers(n_roce=99, n_capex=99, med_roce=10.0, med_capex=8.0,
          sector="Technology", available=True) -> dict:
    return {
        "available": available,
        "n_docs": 485,
        "sectors": {sector: {
            "roce_pct": {"median": med_roce, "n": n_roce},
            "capex_intensity_pct": {"median": med_capex, "n": n_capex},
        }},
    }


def verdicts(read: dict) -> dict:
    return {k: v["verdict"] for k, v in read["components"].items()}


# ═══════════════════════════════════════════════ the happy path, stated once
def test_a_name_passing_everything_grades_all():
    r = CQ.for_row(row(), peers())
    assert r["grade"] == "all"
    assert (r["passed"], r["failed"], r["unknown"]) == (6, 0, 0)
    assert r["answered"] == 6
    assert set(verdicts(r).values()) == {CQ.PASS}


def test_every_declared_component_is_answered_for_every_row():
    """No component may silently go missing — a chip reading a key that is not
    there renders `undefined`, which looks like a pass."""
    for r in (CQ.for_row(row(), peers()), CQ.for_row({}, {})):
        assert set(r["components"]) == set(CQ.COMPONENT_KEYS)
        for key in CQ.COMPONENT_KEYS:
            assert r["components"][key]["verdict"] in (CQ.PASS, CQ.FAIL, CQ.UNKNOWN)


# ═══════════════════════════════════════════ NEGATIVE: unknown is not failed
def test_a_name_with_no_fundamentals_grades_unknown_and_is_never_ranked():
    """The headline negative. Nothing known => not ranked LAST, not ranked."""
    r = CQ.for_row({"symbol": "EMPTY"}, {})
    assert r["grade"] == "unknown"
    assert r["rank_key"] is None, "an unreadable name must not be ranked at all"
    assert r["answered"] == 0
    assert r["failed"] == 0, "missing data is never a failure"
    assert r["unknown"] == len(CQ.COMPONENT_KEYS)


@pytest.mark.parametrize("field,component,reason", [
    ("cash", "net_cash", "missing_cash_or_debt"),
    ("debt", "net_cash", "missing_cash_or_debt"),
    ("fcf_yield", "positive_fcf", "missing_fcf_yield"),
    ("shares_yoy_pct", "no_dilution", "missing_shares_yoy"),
    ("roce_pct", "positive_roce", "missing_roce"),
])
def test_a_component_with_a_missing_input_is_unknown_not_failed(
        field, component, reason):
    r = CQ.for_row(row(**{field: None}), peers())
    c = r["components"][component]
    assert c["verdict"] == CQ.UNKNOWN
    assert c["reason"] == reason
    assert r["failed"] == 0


def test_a_missing_input_does_not_drag_the_grade_down():
    """5 of 5 answered is still "all" — the sixth was never asked."""
    r = CQ.for_row(row(fcf_yield=None), peers())
    assert r["grade"] == "all"
    assert r["answered"] == 5 and r["unknown"] == 1


def test_unknown_components_are_excluded_from_answered_not_counted_as_fail():
    r = CQ.for_row(row(cash=None, fcf_yield=None, roce_pct=None), peers())
    assert r["unknown"] >= 3
    assert r["passed"] + r["failed"] == r["answered"]
    assert r["passed"] + r["failed"] + r["unknown"] == len(CQ.COMPONENT_KEYS)


def test_a_nan_input_is_unknown_never_a_silent_fail():
    """`nan > 0` is False in Python — a NaN that reached the comparison would
    render as a FAIL. It must be stopped before it gets there."""
    r = CQ.for_row(row(fcf_yield=float("nan"), roce_pct=float("nan")), peers())
    assert r["components"]["positive_fcf"]["verdict"] == CQ.UNKNOWN
    assert r["components"]["positive_roce"]["verdict"] == CQ.UNKNOWN
    assert r["failed"] == 0


def test_an_infinite_input_is_unknown_too():
    r = CQ.for_row(row(roce_pct=float("inf")), peers())
    assert r["components"]["positive_roce"]["verdict"] == CQ.UNKNOWN


def test_a_string_input_is_unknown_not_a_crash():
    r = CQ.for_row(row(cash="lots", fcf_yield="3.5%"), peers())
    assert r["components"]["net_cash"]["verdict"] == CQ.UNKNOWN
    assert r["components"]["positive_fcf"]["verdict"] == CQ.UNKNOWN


# ═════════════════════════════════════════ the definitional cuts themselves
@pytest.mark.parametrize("cash,debt,expect", [
    (10.0, 5.0, CQ.PASS),
    (5.0, 10.0, CQ.FAIL),
    (5.0, 5.0, CQ.FAIL),        # equal is NOT net cash
    (0.0, 0.0, CQ.FAIL),
])
def test_net_cash_is_a_strict_inequality(cash, debt, expect):
    r = CQ.for_row(row(cash=cash, debt=debt), peers())
    assert r["components"]["net_cash"]["verdict"] == expect


@pytest.mark.parametrize("v,expect", [(1.0, CQ.PASS), (-1.0, CQ.FAIL),
                                      (0.0, CQ.FAIL)])
def test_positive_fcf_is_a_sign_test(v, expect):
    assert CQ.for_row(row(fcf_yield=v), peers()
                      )["components"]["positive_fcf"]["verdict"] == expect


@pytest.mark.parametrize("v,expect", [(-5.0, CQ.PASS), (0.0, CQ.PASS),
                                      (0.1, CQ.FAIL), (40.0, CQ.FAIL)])
def test_no_dilution_treats_flat_as_not_rising(v, expect):
    """"not rising" is <= 0. A company that issued no stock has not diluted
    him, and calling that a failure would be a fitted cut, not a definitional
    one."""
    assert CQ.for_row(row(shares_yoy_pct=v), peers()
                      )["components"]["no_dilution"]["verdict"] == expect


@pytest.mark.parametrize("v,expect", [(30.0, CQ.PASS), (0.01, CQ.PASS),
                                      (0.0, CQ.FAIL), (-17.03, CQ.FAIL)])
def test_positive_roce_is_a_sign_test_not_a_threshold(v, expect):
    """Measured on the live board 2026-09-22 this is not a no-op: it separates
    SITM (-1.03%) and FF (-17.03%) from the 14 other operating names."""
    assert CQ.for_row(row(roce_pct=v), peers()
                      )["components"]["positive_roce"]["verdict"] == expect


def test_no_component_compares_against_a_chosen_constant():
    """The safety property of the whole package: shifting every input by a big
    constant may flip a RELATIVE cut, but a definitional one only ever answers
    to a sign or to the other side of its own inequality. This pins that there
    is no hidden `roce > 20` anywhere: a name far below any plausible invented
    bar still PASSES every definitional cut as long as the facts hold."""
    r = CQ.for_row(row(cash=1.01, debt=1.0, fcf_yield=0.0001,
                       shares_yoy_pct=0.0, roce_pct=0.0001), peers())
    for key in ("net_cash", "positive_fcf", "no_dilution", "positive_roce"):
        assert r["components"][key]["verdict"] == CQ.PASS


# ════════════════════════════ NEGATIVE: the peer floor refuses to compare
def test_the_peer_floor_is_the_house_floor_not_a_new_one():
    """`MIN_PEERS` is `sepa/longterm.py:MIN_SECTOR_N`, whose own comment reads
    "Below this, a within-sector percentile is noise." Pinned equal so the two
    cannot drift, and so nobody can quietly lower this one to make the relative
    cut fire on a thin cohort."""
    from sepa import longterm as LT
    assert CQ.MIN_PEERS == LT.MIN_SECTOR_N == 20


@pytest.mark.parametrize("n", [0, 1, 2, 3, 19])
def test_the_sector_cut_refuses_rather_than_comparing_against_a_handful(n):
    """THE negative this read exists for. A median over 2 names is not a
    sector median, and serving one would be an invented number wearing a
    statistic's clothes."""
    r = CQ.for_row(row(), peers(n_roce=n, n_capex=n))
    for key in ("roce_above_sector", "capex_below_sector"):
        c = r["components"][key]
        assert c["verdict"] == CQ.UNKNOWN
        assert c["reason"] == "insufficient_peers"
    assert r["failed"] == 0


def test_the_floor_is_inclusive_at_exactly_min_peers():
    r = CQ.for_row(row(), peers(n_roce=CQ.MIN_PEERS, n_capex=CQ.MIN_PEERS))
    assert r["components"]["roce_above_sector"]["verdict"] == CQ.PASS
    assert r["components"]["roce_above_sector"]["peer_n"] == CQ.MIN_PEERS


def test_the_floor_is_counted_per_field_not_per_document():
    """A sector with 99 documents but 3 usable ROCE figures has THREE peers for
    ROCE. Counting documents is how a median over three names gets served
    looking like a median over ninety-nine."""
    r = CQ.for_row(row(), peers(n_roce=3, n_capex=99))
    assert r["components"]["roce_above_sector"]["reason"] == "insufficient_peers"
    assert r["components"]["capex_below_sector"]["verdict"] in (CQ.PASS, CQ.FAIL)


def test_relative_cuts_are_unknown_when_the_peer_pool_could_not_be_read():
    r = CQ.for_row(row(), {"available": False, "sectors": {}, "n_docs": 0})
    for key in ("roce_above_sector", "capex_below_sector"):
        c = r["components"][key]
        assert c["verdict"] == CQ.UNKNOWN and c["reason"] == "peers_unavailable"
    assert r["failed"] == 0


def test_a_name_with_no_sector_cannot_be_compared_to_one():
    r = CQ.for_row(row(sector=None), peers())
    for key in ("roce_above_sector", "capex_below_sector"):
        assert r["components"][key]["reason"] == "no_sector"


def test_a_sector_absent_from_the_cohort_refuses_on_peers():
    r = CQ.for_row(row(sector="Utilities"), peers(sector="Technology"))
    assert r["components"]["roce_above_sector"]["reason"] == "insufficient_peers"


def test_a_non_operating_balance_sheet_is_refused_by_name_not_compared():
    """A bank's deposits are liabilities and a mortgage REIT is levered by
    design. `board_metrics` already flags the cohort; comparing it on "capital
    employed" would be a category error, and it is UNKNOWN, not FAIL."""
    r = CQ.for_row(row(balance_meaningful=False, roce_pct=None,
                       capex_intensity_pct=None,
                       capital_reasons={"roce_pct": "non_operating_sector"}),
                   peers())
    assert r["components"]["roce_above_sector"]["reason"] == "non_operating_sector"
    assert r["components"]["capex_below_sector"]["reason"] == "non_operating_sector"
    assert r["components"]["positive_roce"]["reason"] == "non_operating_sector"
    assert r["failed"] == 0


# ═══════════════════════════════════════ the relative cuts' DIRECTION
def test_roce_above_sector_is_higher_is_better():
    assert CQ.for_row(row(roce_pct=30.0), peers(med_roce=10.0)
                      )["components"]["roce_above_sector"]["verdict"] == CQ.PASS
    assert CQ.for_row(row(roce_pct=5.0), peers(med_roce=10.0)
                      )["components"]["roce_above_sector"]["verdict"] == CQ.FAIL


def test_capex_below_sector_is_LOWER_is_better():
    """The "less capital" half of the ask. Getting this direction backwards
    would rank the most capital-hungry names as the highest quality — the exact
    inversion the ask is about. Measured 2026-09-22: NVDA 2.43% capex intensity
    against SM 35.61%."""
    assert CQ.for_row(row(capex_intensity_pct=2.43), peers(med_capex=8.0)
                      )["components"]["capex_below_sector"]["verdict"] == CQ.PASS
    assert CQ.for_row(row(capex_intensity_pct=35.61), peers(med_capex=8.0)
                      )["components"]["capex_below_sector"]["verdict"] == CQ.FAIL


def test_equal_to_the_median_is_not_above_it():
    r = CQ.for_row(row(roce_pct=10.0, capex_intensity_pct=8.0),
                   peers(med_roce=10.0, med_capex=8.0))
    assert r["components"]["roce_above_sector"]["verdict"] == CQ.FAIL
    assert r["components"]["capex_below_sector"]["verdict"] == CQ.FAIL


def test_a_served_relative_component_says_what_it_was_compared_against():
    """The reader is never shown a median without being told what it is a
    median OF."""
    c = CQ.for_row(row(), peers(n_roce=99, med_roce=10.0)
                   )["components"]["roce_above_sector"]
    assert c["peer_n"] == 99 and c["sector_median"] == 10.0
    assert "n=99" in c["detail"]


# ═════════════════════════════════════════════════════ the grade is a count
@pytest.mark.parametrize("passed,answered,expect", [
    (0, 0, "unknown"),
    (6, 6, "all"), (1, 1, "all"),
    (0, 6, "none"), (0, 1, "none"),
    (4, 6, "most"), (2, 3, "most"),
    (3, 6, "some"), (1, 3, "some"), (1, 2, "some"),
])
def test_the_grade_is_a_pure_count(passed, answered, expect):
    assert CQ.grade_for(passed, answered) == expect


def test_every_grade_is_declared():
    for p in range(0, 7):
        for a in range(p, 7):
            assert CQ.grade_for(p, a) in CQ.GRADES


def test_a_half_split_is_some_not_most():
    """The majority line is strict: 3 of 6 is not a majority."""
    assert CQ.grade_for(3, 6) == "some"
    assert CQ.grade_for(4, 6) == "most"


def test_answered_is_served_because_all_of_one_is_not_all_of_six():
    """A name with one answerable question it passed grades "all", and so does a
    name that passed all six. Same word, different facts — `answered` is what
    keeps the board honest about which it is looking at."""
    thin = CQ.for_row(row(fcf_yield=None, shares_yoy_pct=None, roce_pct=None,
                          capex_intensity_pct=None), peers())
    full = CQ.for_row(row(), peers())
    assert thin["grade"] == full["grade"] == "all"
    assert thin["answered"] == 1 and full["answered"] == 6, (
        "the grade alone cannot distinguish them — `answered` must")


def test_rank_key_is_none_only_when_nothing_was_answered():
    assert CQ.for_row({}, {})["rank_key"] is None
    r = CQ.for_row(row(cash=5.0, debt=10.0, fcf_yield=None,
                       shares_yoy_pct=None, roce_pct=None), {})
    assert r["answered"] == 1 and r["rank_key"] == 0, (
        "a name judged and found wanting IS ranked — at zero, not at None")


# ═══════════════════════════════════════════════════ NEGATIVE: the NaN sweep
def _walk(o, path="payload"):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _walk(v, "%s.%s" % (path, k))
    elif isinstance(o, (list, tuple)):
        for i, v in enumerate(o):
            yield from _walk(v, "%s[%d]" % (path, i))
    else:
        yield path, o


def test_no_nan_or_inf_reaches_the_payload_even_from_poisoned_inputs():
    """A NaN survives `json.dumps` in Python and breaks the frontend's
    `JSON.parse` — the bug that once stuck the SEPA scan button on
    'Scanning...'. Poison every numeric input and sweep the whole payload."""
    bad = float("nan")
    rows = [row(cash=bad, debt=bad, fcf_yield=bad, shares_yoy_pct=bad,
                roce_pct=bad, capex_intensity_pct=bad),
            row(cash=float("inf"), roce_pct=float("-inf")),
            row()]
    summary = CQ.attach(rows, db=object())
    # Sweep what THIS module produced. The poisoned inputs are the board's own
    # fields and are not this module's to clean; `growth/api.py:_scrub` takes
    # the whole payload at the edge. What must be provably clean is everything
    # written here.
    payload = {"reads": [r["capital_quality"] for r in rows],
               "summary": summary}
    for path, v in _walk(payload):
        if isinstance(v, float):
            assert not math.isnan(v), "NaN at %s" % path
            assert not math.isinf(v), "inf at %s" % path
    json.loads(json.dumps(payload))      # and it must survive a round trip


def test_a_poisoned_median_is_refused_rather_than_compared_against():
    bad = {"available": True, "n_docs": 9, "sectors": {"Technology": {
        "roce_pct": {"median": float("nan"), "n": 99},
        "capex_intensity_pct": {"median": None, "n": 99}}}}
    r = CQ.for_row(row(), bad)
    for key in ("roce_above_sector", "capex_below_sector"):
        assert r["components"][key]["verdict"] == CQ.UNKNOWN
        assert r["components"][key]["reason"] == "insufficient_peers"


# ══════════════════════════════════════ NEGATIVE: the MEASURED flag is pinned
def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))


def test_measured_true_requires_the_study_script_to_exist():
    """THE guard. This read orders names by balance-sheet quality and nobody has
    measured whether that predicts anything. `MEASURED` may only become True
    once a study exists at the path the module names — "ship the backtest with
    the claim", the standing rule."""
    if CQ.MEASURED:
        path = os.path.join(_repo_root(), CQ.STUDY_SCRIPT)
        assert os.path.exists(path), (
            "MEASURED is True but %s does not exist — a measured flag with no "
            "study behind it is exactly the fabrication this package forbids"
            % CQ.STUDY_SCRIPT)


def test_measured_is_false_today_because_no_study_has_been_run():
    assert not os.path.exists(os.path.join(_repo_root(), CQ.STUDY_SCRIPT))
    assert CQ.MEASURED is False


def test_the_measured_note_says_in_plain_words_that_it_is_not_an_edge():
    note = CQ.MEASURED_NOTE.lower()
    assert "screen" in note and "not an edge" in note
    assert "measured" in note


def test_the_flag_rides_on_every_row_and_on_the_summary():
    """So no surface can render a grade without the sentence beside it."""
    rows = [row()]
    summary = CQ.attach(rows, db=object())
    assert rows[0]["capital_quality"]["measured"] is False
    assert summary["measured"] is False
    assert summary["measured_note"] == CQ.MEASURED_NOTE


def test_it_does_not_borrow_the_longterm_quality_scores_credibility():
    """Two unmeasured reads; neither lends the other any weight."""
    from sepa import longterm as LT
    assert LT.SCORE_IS_MEASURED is False and CQ.MEASURED is False


def test_the_read_is_not_conflated_with_eq_score():
    """`eq_score` is the Ch.8 EARNINGS-quality read and it FEEDS the SEPA score.
    This is a BALANCE-SHEET read and it feeds nothing. A row carrying both must
    keep them in separate keys."""
    rows = [row(eq_score=88)]
    CQ.attach(rows, db=object())
    assert rows[0]["eq_score"] == 88
    assert "eq_score" not in rows[0]["capital_quality"]
    assert rows[0]["capital_quality"]["grade"] in CQ.GRADES


# ═══════════════════════════════════════════════════════ Rule #7: the period
def test_the_read_carries_the_fiscal_period_not_the_cache_age():
    r = CQ.for_row(row(capital_period="Q2 2026",
                       capital_period_end="2026-06-30"), peers())
    assert r["period"] == "Q2 2026" and r["period_end"] == "2026-06-30"
    assert "fetched_at" not in r and "age" not in r


# ═══════════════════════════════════════════════════ the board-level attach
def test_attach_serves_the_counts_a_chip_needs_before_he_toggles_it():
    """The `ExplosiveGrowth.tsx:285` lesson: a `debt === 0` filter silently
    returned ZERO of 29 rows. A chip must be able to say how many it hides."""
    rows = [row(), row(cash=1.0, debt=99.0), row(cash=None, debt=None)]
    s = CQ.attach(rows, db=object())
    net = [c for c in s["components"] if c["key"] == "net_cash"][0]
    assert (net["pass_n"], net["fail_n"], net["unknown_n"]) == (1, 1, 1)
    assert net["hides_n"] == 1, "an UNKNOWN row is not hidden — it was not judged"


def test_attach_serves_both_survivor_counts_and_they_mean_different_things():
    """Measured 2026-09-22: stacking every definitional cut leaves 2 of 21. The
    counts are served so a surface can WARN instead of emptying itself.

    `no_fail_n` is what survives every chip ON — a chip hides FAILURES, so the
    all-unknown row is still on screen. `all_pass_n` is the strictest read and
    needs the peer cohort, which is why it is 0 here."""
    rows = [row(), row(shares_yoy_pct=40.0), row(cash=None, debt=None,
                       fcf_yield=None, shares_yoy_pct=None, roce_pct=None)]
    s = CQ.attach(rows, db=object())          # no peers: relative cuts unknown
    assert s["n"] == 3
    assert s["no_fail_n"] == 2, "the unjudged row is not hidden by a chip"
    assert s["all_pass_n"] == 0, "nothing can pass all six without a peer cohort"


def test_all_pass_n_counts_only_a_clean_sweep_of_every_component():
    # Peers supplied directly so the relative components can actually pass.
    rows = [row(), row(fcf_yield=None), row(shares_yoy_pct=40.0)]
    p = peers()
    reads = [CQ.for_row(r, p) for r in rows]
    assert [r["passed"] for r in reads] == [6, 5, 5]
    assert sum(1 for r in reads if r["passed"] == len(CQ.COMPONENT_KEYS)) == 1
    assert sum(1 for r in reads if r["failed"] == 0) == 2


def test_attach_reports_the_peer_cohort_it_actually_used():
    s = CQ.attach([row()], db=object())
    assert s["peers"]["min_peers"] == CQ.MIN_PEERS
    assert "available" in s["peers"] and "n_docs" in s["peers"]


def test_attach_grade_counts_sum_to_the_rows_graded():
    rows = [row(), row(shares_yoy_pct=40.0), {}, row(cash=None, debt=None)]
    s = CQ.attach(rows, db=object())
    assert sum(s["grades"].values()) == s["n"] == len(rows)


def test_attach_declares_every_component_with_its_kind_and_label():
    s = CQ.attach([row()], db=object())
    assert [c["key"] for c in s["components"]] == list(CQ.COMPONENT_KEYS)
    for c in s["components"]:
        assert c["kind"] in (CQ.DEFINITIONAL, CQ.RELATIVE)
        assert c["label"] and isinstance(c["label"], str)


# ══════════════════════════════════════════ NEGATIVE: nothing may take a tab down
def test_attach_never_raises_on_junk_rows():
    for junk in ([None, "x", 42, [], row()], [], None, "not a list"):
        s = CQ.attach(junk, db=object())
        assert isinstance(s, dict) and "grades" in s


def test_attach_survives_a_dead_peer_read_and_still_grades_the_definitional_cuts():
    class Boom:
        def __getitem__(self, _k):
            raise RuntimeError("mongo is down")
    rows = [row()]
    s = CQ.attach(rows, db=Boom())
    read = rows[0]["capital_quality"]
    assert s["peers"]["available"] is False
    assert read["grade"] == "all" and read["answered"] == 4, (
        "the four definitional cuts do not need a peer cohort")
    for key in ("roce_above_sector", "capex_below_sector"):
        assert read["components"][key]["reason"] == "peers_unavailable"


def test_for_row_is_pure_and_does_not_mutate_the_row():
    r = row()
    before = dict(r)
    CQ.for_row(r, peers())
    assert r == before, "for_row must not write to the row; attach does that"


def test_peer_medians_returns_the_unavailable_shape_on_a_dead_db():
    class Boom:
        def __getitem__(self, _k):
            raise RuntimeError("nope")
    out = CQ.peer_medians(db=Boom())
    assert out["available"] is False and out["sectors"] == {}


# ═══════════════════════════════════════════ Rule #10: it changes no rule
def test_the_read_adds_one_key_and_touches_nothing_else_on_the_row():
    r = row()
    before = set(r)
    CQ.attach([r], db=object())
    assert set(r) - before == {"capital_quality"}


def test_the_module_declares_no_threshold_constant():
    """A float or int module constant that is not a count, a floor cited from
    the house, or a declared flag would be an invented number. Pinned so one
    cannot be added quietly."""
    allowed = {"MIN_PEERS"}
    numeric = {k for k, v in vars(CQ).items()
               if not k.startswith("_") and isinstance(v, (int, float))
               and not isinstance(v, bool)}
    assert numeric <= allowed, "undeclared numeric constant(s): %s" % (
        numeric - allowed)
