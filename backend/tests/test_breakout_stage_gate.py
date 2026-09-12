"""The breakout board's stage gate (2026-09-12).

Ajay: *"From the breakout remove any S3. Only S2 stocks and if thy have
explosive growth its ok to have s1 and s3. If they are newly found explosive
growth"*.

Stage 2 is the only advancing stage and the only one Minervini calls buyable;
1 is basing, 3 is topping, 4 is decline. The board keeps S2 — plus an explosive
grower at 1 or 3, because a 100%-sales / 100%-EPS name basing is a different
proposition from a tired one. **Stage 4 is never excepted**: he named 1 and 3.

MEASURED on the live board. Before: 250 rows over stages {1:111, 2:78, 3:35,
4:26}. After: 250 rows drawn from 350 QUALIFYING names, {1:4, 2:240, 3:6, 4:0}.
Filtering the already-cut 250 would have left ~80 — which is why the gate runs
BEFORE the cut.
"""
from __future__ import annotations

import inspect

from sepa import breakout as B


def r(sym, stage, explosive=False, new=False):
    return {"symbol": sym, "stage": stage, "explosive": explosive,
            "explosive_new": new, "breakout_count": 3, "rs_rank": 50,
            "days_since_breakout": 0, "ai_sector_rank": None}


# ── the rule ───────────────────────────────────────────────────────────────
def test_stage_2_is_kept():
    assert B._stage_ok(r("AAA", 2)) is True


def test_NEGATIVE_stage_3_is_removed_which_is_what_he_asked_for():
    assert B._stage_ok(r("AAA", 3)) is False


def test_NEGATIVE_stage_1_is_removed_too():
    """"Only S2 stocks" — basing is not advancing."""
    assert B._stage_ok(r("AAA", 1)) is False


def test_an_EXPLOSIVE_grower_is_allowed_at_stage_1_and_3():
    assert B._stage_ok(r("IPI", 1, explosive=True)) is True
    assert B._stage_ok(r("NVDA", 3, explosive=True)) is True


def test_THE_LINE_HE_DID_NOT_DRAW_stage_4_is_never_excepted():
    """He named 1 and 3. A decline is a decline — an explosive grower in free
    fall is still in free fall, and the page has called S4 'avoid' since it
    shipped."""
    assert B._stage_ok(r("DEAD", 4)) is False
    assert B._stage_ok(r("DEAD", 4, explosive=True)) is False
    assert 4 in B.STAGE_NEVER


def test_NEGATIVE_an_UNREADABLE_stage_is_KEPT_not_dropped():
    """Dropping a name because the classifier could not answer would hide it
    for a reason that has nothing to do with the stock — the same discipline
    every other unknown in this app gets."""
    assert B._stage_ok(r("AAA", None)) is True
    assert B._stage_ok({"symbol": "AAA"}) is True


# ── where it runs ──────────────────────────────────────────────────────────
def test_THE_GATE_RUNS_BEFORE_THE_CUT():
    """The whole point. Gating after `rows[:top]` would filter 250 rows drawn
    from 2,840 candidates down to ~80; gating first means the 250 returned are
    250 QUALIFYING names."""
    src = inspect.getsource(B.board)
    i_gate = src.index("_stage_ok(x)")
    i_sort = src.index("rows.sort(key=_recency_key)")
    i_cut = src.index("rows = rows[:top]")
    assert i_gate < i_sort < i_cut


def test_the_explosive_tag_is_attached_BEFORE_the_gate_that_reads_it():
    """The exception is worthless if `explosive` is still unset when the gate
    runs — every S1/S3 row would be dropped and the board would silently lose
    exactly the names he asked to keep."""
    src = inspect.getsource(B.board)
    assert src.index('x["explosive"] = bool(g)') < src.index("_stage_ok(x)")


def test_what_the_gate_REMOVED_is_reported():
    """A filtered board must never read as the whole market breaking out."""
    src = inspect.getsource(B.board)
    for key in ('"stage_filter"', '"n_prestage"', '"n_stage_dropped"'):
        assert key in src


def test_the_gate_can_be_TURNED_OFF():
    sig = inspect.signature(B.board)
    assert sig.parameters["stages"].default is True, "his ask is the default"


def test_the_rule_lives_in_ONE_predicate_not_scattered_inline():
    assert B.STAGE_KEEP == (2,)
    assert set(B.STAGE_EXCEPTION) == {1, 3}
    assert B.STAGE_NEVER == (4,)


# ── "newly found" ──────────────────────────────────────────────────────────
def test_newly_found_returns_EMPTY_until_tracking_has_seen_an_arrival():
    """Nothing recorded when a name first appeared on the growth board — the
    doc is `_id: "latest"`, latest-only. On the first build EVERY name would
    look new, so a name present at the first build is NOT new; it is merely the
    first thing we ever saw."""
    from growth import tracker as GT

    class _Coll:
        def find_one(self, *a, **k):
            return None          # no __meta__ yet

        def find(self, *a, **k):
            return []

    class _DB:
        def __getitem__(self, name):
            return _Coll()

    assert GT.newly_found(db=_DB()) == set()


def test_the_new_growth_window_is_a_named_constant():
    from growth import tracker as GT
    assert isinstance(GT.NEW_GROWTH_DAYS, int) and GT.NEW_GROWTH_DAYS >= 7
