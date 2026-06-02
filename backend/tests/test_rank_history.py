"""Rank-history event derivation — behavioral (2026-06-02).

The 'Ranking' tab marks breakout / became-buyable / stage-change on the rank line.
'became_buyable' must be an EDGE (False->True), not fire on every buyable bar.
"""
from sepa.rank_history import derive_events


def _snap(stage=2, breakout=True, setup=True):
    return {
        "stage": stage,
        "entry_setup": {"pivot": 10} if setup else None,
        "volume": {"high_vol_breakout": breakout},
    }


def test_breakout_event_and_buyable():
    ev, buyable, stage = derive_events(_snap(), is_qual=True, prev_buyable=False, prev_stage=2)
    assert "breakout" in ev
    assert "became_buyable" in ev      # False -> True edge
    assert buyable is True and stage == 2


def test_became_buyable_is_an_edge_not_a_level():
    # Already buyable last point → no 'became_buyable' again, but still a breakout.
    ev, buyable, _ = derive_events(_snap(), is_qual=True, prev_buyable=True, prev_stage=2)
    assert "breakout" in ev
    assert "became_buyable" not in ev
    assert buyable is True


def test_not_buyable_without_breakout():
    ev, buyable, _ = derive_events(_snap(breakout=False), is_qual=True, prev_buyable=False, prev_stage=2)
    assert buyable is False
    assert "breakout" not in ev and "became_buyable" not in ev


def test_not_buyable_when_not_stage2():
    _, buyable, _ = derive_events(_snap(stage=1), is_qual=True, prev_buyable=False, prev_stage=1)
    assert buyable is False


def test_stage_change_event():
    ev, _, stage = derive_events(_snap(stage=3), is_qual=True, prev_buyable=False, prev_stage=2)
    assert "stage_3" in ev and stage == 3
    # No spurious stage event when stage is unchanged.
    ev2, _, _ = derive_events(_snap(stage=2), is_qual=True, prev_buyable=False, prev_stage=2)
    assert not any(e.startswith("stage_") for e in ev2)
