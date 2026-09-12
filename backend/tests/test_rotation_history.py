"""Daily rotation history and the change detector (2026-09-12).

Ajay, on the six-row ~35-chip Hot-sectors strip: "this is what I mean when I
said messy" and "I am trying to see what changed if there is no change
continously same sectors continue to show the top for example energy has been
continous."

The single most important behaviour here is `quiet`: when nothing moved, that
is an ANSWER — "no change today" — not an empty render. A strip that cannot
say it is a strip he has to diff by eye every session.
"""
from __future__ import annotations

import pytest

from rotation import history as H


def payload(as_of, order, key="rel_5d"):
    """`order` is best-first; values descend so the rank IS the list order."""
    return {"as_of": as_of,
            "themes": [{"group": g, key: 10.0 - i, "n": 10}
                       for i, g in enumerate(order)]}


def snap(as_of, order):
    return H.snapshot(payload(as_of, order))


# --------------------------------------------------------------- snapshot
def test_the_snapshot_ranks_by_the_leg_the_strip_ranks_by():
    s = snap("2026-09-11", ["optical", "ai_semis", "energy"])
    assert [(r["group"], r["rank"]) for r in s["grains"]["themes"]] == \
        [("optical", 1), ("ai_semis", 2), ("energy", 3)]


def test_NEGATIVE_a_payload_with_no_as_of_is_REFUSED_not_stamped_with_today():
    """A document keyed by the wrong day corrupts every delta computed after
    it — far worse than a missing day."""
    assert H.snapshot({"themes": [{"group": "x", "rel_5d": 1}]}) is None
    assert H.store({"themes": []}) is None


def test_NEGATIVE_a_missing_leg_sorts_LAST_and_never_wins_rank_one():
    """The values must be NEGATIVE for this test to mean anything.

    With a positive leg, treating a missing value as 0.0 still ranks it last,
    so the test passes under a broken sort. On a DOWN week — every theme
    negative — a missing leg read as 0.0 is the BEST score on the board and the
    blank takes rank 1. Mutation-tested 2026-09-12: the positive-value version
    of this test sailed through exactly that bug."""
    s = H.snapshot({"as_of": "2026-09-11", "themes": [
        {"group": "blank"},
        {"group": "worst", "rel_5d": -8.0},
        {"group": "best", "rel_5d": -1.0}]})
    assert [r["group"] for r in s["grains"]["themes"]] == ["best", "worst", "blank"]


# ---------------------------------------------------------------- changes
def test_it_reports_what_entered_left_and_moved():
    today = payload("2026-09-11", ["optical", "ai_semis", "energy"])
    prior = snap("2026-09-10", ["energy", "optical", "ai_semis"])
    c = H.changes(today, history=[prior], top_n=2)
    assert [e["group"] for e in c["entered"]] == ["ai_semis"]
    assert [e["group"] for e in c["left"]] == ["energy"]
    assert c["moved"][0] == {"group": "energy", "rank": 3, "prev_rank": 1, "delta": -2}
    assert c["quiet"] is False


def test_QUIET_is_the_answer_when_the_ranking_did_not_move():
    """THE POINT. Energy #1 for eight days is one fact, not eight."""
    order = ["energy", "optical", "ai_semis", "nuclear"]
    c = H.changes(payload("2026-09-11", order), history=[snap("2026-09-10", order)])
    assert c["quiet"] is True
    assert c["entered"] == [] and c["left"] == [] and c["moved"] == []
    assert c["baseline"] == "2026-09-10"


def test_a_one_place_shuffle_is_NOT_a_change_worth_a_line():
    """MIN_MOVE exists so a strip read in two seconds is not full of noise."""
    c = H.changes(payload("2026-09-11", ["optical", "energy", "ai_semis"]),
                  history=[snap("2026-09-10", ["energy", "optical", "ai_semis"])],
                  top_n=6, min_move=2)
    assert c["moved"] == [] and c["quiet"] is True


def test_the_streak_counts_consecutive_sessions_at_the_SAME_rank():
    """"energy has been continous" — the number that lets the strip say it."""
    order = ["energy", "optical", "ai_semis"]
    hist = [snap("2026-09-%02d" % d, order) for d in (10, 9, 8, 7)]
    c = H.changes(payload("2026-09-11", order), history=hist)
    assert c["streaks"]["energy"] == 5           # today + four stored sessions


def test_a_streak_BREAKS_when_the_rank_changed_and_does_not_count_past_it():
    hist = [snap("2026-09-10", ["energy", "optical"]),
            snap("2026-09-09", ["optical", "energy"]),   # <- different
            snap("2026-09-08", ["energy", "optical"])]
    c = H.changes(payload("2026-09-11", ["energy", "optical"]), history=hist)
    assert c["streaks"]["energy"] == 2           # today + 09-10 only


def test_NEGATIVE_the_FIRST_snapshot_says_so_instead_of_inventing_a_shift():
    c = H.changes(payload("2026-09-11", ["energy", "optical"]), history=[])
    assert c["baseline"] is None and c["quiet"] is True
    assert "first snapshot" in c["reason"]
    assert c["entered"] == [] and c["left"] == []


def test_NEGATIVE_it_never_compares_a_session_against_itself():
    """Re-running the same day must not become a zero-change 'comparison' with
    a baseline that is today."""
    today = payload("2026-09-11", ["energy", "optical"])
    c = H.changes(today, history=[snap("2026-09-11", ["optical", "energy"])])
    assert c["baseline"] is None      # the only stored row IS today
    assert "first snapshot" in c["reason"]


def test_every_grain_is_snapshotted_not_just_themes():
    p = {"as_of": "2026-09-11",
         "themes": [{"group": "optical", "rel_5d": 9}],
         "sectors": [{"group": "Energy", "rel_5d": 3}],
         "industries": [{"group": "Uranium", "rel_5d": 1}],
         "cohorts": [{"group": "Energy · small caps", "rel_5d": 4}]}
    g = H.snapshot(p)["grains"]
    assert set(g) == set(H.GRAINS)
    assert g["sectors"][0]["group"] == "Energy"


def test_the_module_makes_no_forward_claim():
    """Whitespace-normalised: the sentence wraps, and a test that breaks when
    a docstring is reflowed teaches people to delete the test."""
    doc = " ".join((H.__doc__ or "").split())
    assert "not a reason to trade it" in doc
    assert "does NOT predict" in doc


# ------------------------------------------------------- the all-grain answer
def multi(as_of, themes, sectors, key="rel_5d"):
    """A payload where themes and sectors can disagree about whether anything
    moved — the exact case a single-grain answer gets wrong."""
    return {"as_of": as_of,
            "themes": [{"group": g, key: 10.0 - i} for i, g in enumerate(themes)],
            "sectors": [{"group": g, key: 10.0 - i} for i, g in enumerate(sectors)]}


def test_changes_all_answers_every_grain_in_one_read():
    hist = [H.snapshot(multi("2026-09-11", ["a", "b", "c"], ["Energy", "Tech"]))]
    out = H.changes_all(multi("2026-09-12", ["c", "b", "a"], ["Energy", "Tech"]),
                        history=hist, min_move=1)
    assert set(out["grains"]) == set(H.GRAINS)
    assert out["baseline"] == "2026-09-11"


def test_NEGATIVE_quiet_is_FALSE_when_ANY_grain_moved_even_if_the_headline_did_not():
    """The bug this exists to stop: the strip renders cohorts, industries AND
    themes, so reporting the sector grain's "no change" while themes reshuffled
    underneath is a confident false sentence — worse than the chip wall."""
    hist = [H.snapshot(multi("2026-09-11", ["a", "b", "c", "d"], ["Energy", "Tech"]))]
    cur = multi("2026-09-12", ["d", "c", "b", "a"], ["Energy", "Tech"])
    # sectors alone: untouched, so the single-grain answer is quiet
    assert H.changes(cur, history=hist, grain="sectors", min_move=2)["quiet"] is True
    # themes alone: a 3-place move
    assert H.changes(cur, history=hist, grain="themes", min_move=2)["quiet"] is False
    # the combined answer must follow the grain that MOVED
    assert H.changes_all(cur, history=hist, min_move=2)["quiet"] is False


def test_changes_all_is_quiet_only_when_NOTHING_moved_anywhere():
    same = ["a", "b", "c"]
    hist = [H.snapshot(multi("2026-09-11", same, ["Energy", "Tech"]))]
    out = H.changes_all(multi("2026-09-12", same, ["Energy", "Tech"]),
                        history=hist, min_move=2)
    assert out["quiet"] is True
    assert out["baseline"] == "2026-09-11"


def test_NEGATIVE_changes_all_refuses_a_payload_with_no_as_of():
    out = H.changes_all({"themes": [{"group": "a", "rel_5d": 1.0}]}, history=[])
    assert out["quiet"] is True and out["grains"] == {}
    assert "as_of" in (out.get("reason") or "")


def test_the_first_session_says_so_across_every_grain():
    out = H.changes_all(multi("2026-09-12", ["a", "b"], ["Energy"]), history=[])
    assert out["baseline"] is None
    assert "first snapshot" in (out.get("reason") or "")
    assert out["grains"]["themes"]["streaks"] == {"a": 1, "b": 1}
