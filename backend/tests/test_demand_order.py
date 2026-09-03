"""demand_order — closest to the level first, money flow breaks ties.

Ajay 2026-09-03: "make sure in our other demand and deep demand keep the
closest one to demand zones on the top. Of course CMF inflow too considered."

Pure-function tests. The board/scan wiring is asserted in test_chart_maps.py,
test_deep_demand.py and test_supply_demand_contracts.py; this file owns the
KEY itself — including every way a None can reach it.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import demand_order as O  # noqa: E402

LO, HI = 95.0, 100.0


def _flow(state, cmf):
    return None if state is None else {"state": state, "cmf_20": cmf}


def _px_above(pct):
    """A price exactly `pct`% above HI by the module's own formula
    ((px - hi) / px * 100)."""
    return HI / (1 - pct / 100.0)


def _key(px, state="neutral", cmf=0.0, tail=()):
    return O.proximity_key(px, LO, HI, _flow(state, cmf), tail)


def _order(items):
    """items: (label, px, state, cmf) → labels sorted by the key."""
    return [lbl for lbl, px, st, cmf in
            sorted(items, key=lambda it: _key(it[1], it[2], it[3]))]


# ── proximity leads ──────────────────────────────────────────────────────────
def test_inside_then_nearest_above_across_in_near_and_approaching():
    """In-band first, then the 0.5% buckets outward — regardless of flow."""
    assert _order([("FAR", _px_above(2.53), "inflow", 0.364),
                   ("NEAR", _px_above(0.81), "inflow", 0.282),
                   ("IN", 97.0, "inflow", 0.248)]) == ["IN", "NEAR", "FAR"]


def test_the_worked_example_from_the_docstring():
    """The five live approaching rows of 2026-09-03, all inside bucket 0:
    MP, HIMS, ITRI, VLTO, EXR. Raw distance put the accumulated name LAST."""
    rows = [("ITRI", _px_above(0.03), "neutral", -0.044),
            ("EXR", _px_above(0.08), "distribution", -0.275),
            ("VLTO", _px_above(0.11), "distribution", -0.144),
            ("HIMS", _px_above(0.18), "neutral", -0.031),
            ("MP", _px_above(0.26), "inflow", 0.159)]
    assert _order(rows) == ["MP", "HIMS", "ITRI", "VLTO", "EXR"]


def test_equal_bucket_the_higher_cmf_leads():
    assert _order([("MILD", _px_above(0.10), "inflow", 0.05),
                   ("HOT", _px_above(0.40), "inflow", 0.30)]) == ["HOT", "MILD"]


def test_inflow_beats_neutral_beats_distribution_inside_a_bucket():
    assert _order([("SOLD", _px_above(0.05), "distribution", -0.3),
                   ("NEUT", _px_above(0.10), "neutral", 0.0),
                   ("IN", _px_above(0.30), "inflow", 0.1)]) == ["IN", "NEUT", "SOLD"]


def test_bucket_boundary_0_49_vs_0_51_is_documented_behaviour():
    """0.49% and 0.51% straddle the 0.5% edge: they are DIFFERENT buckets, so
    distance decides there even against a hotter flow read. Inside a bucket
    (0.45 vs 0.49) the flow read decides. Both are the intended trade-off —
    a step function has an edge somewhere, and 0.5% is inside one session's
    noise on a $96 stock (see PROXIMITY_BUCKET_PCT)."""
    assert O.PROXIMITY_BUCKET_PCT == 0.5
    assert _order([("B1_INFLOW", _px_above(0.51), "inflow", 0.30),
                   ("B0_SOLD", _px_above(0.49), "distribution", -0.30)]) == ["B0_SOLD", "B1_INFLOW"]
    assert _order([("CLOSER_SOLD", _px_above(0.45), "distribution", -0.30),
                   ("INFLOW", _px_above(0.49), "inflow", 0.30)]) == ["INFLOW", "CLOSER_SOLD"]


def test_below_band_sorts_after_above_band():
    """Fell through the level is not the same event as arriving at it."""
    assert _order([("BELOW", 94.0, "inflow", 0.4),
                   ("ABOVE_FAR", _px_above(4.0), "distribution", -0.4),
                   ("IN", 99.0, None, None)]) == ["IN", "ABOVE_FAR", "BELOW"]
    st, prox = O.geometry(94.0, LO, HI)
    assert st == O.STATE_BELOW and prox == (LO - 94.0) / 94.0 * 100.0


# ── None-safety ──────────────────────────────────────────────────────────────
def test_missing_inflow_and_none_cmf_sort_LAST_in_their_bucket_never_first():
    assert _order([("NOREAD", _px_above(0.10), None, None),
                   ("SOLD", _px_above(0.20), "distribution", -0.5),
                   ("INFLOW_NOCMF", _px_above(0.30), "inflow", None),
                   ("INFLOW", _px_above(0.40), "inflow", 0.01)]) == [
        "INFLOW", "INFLOW_NOCMF", "SOLD", "NOREAD"]
    assert O.cmf_rank({"cmf_20": None}) == math.inf
    assert O.cmf_rank(None) == math.inf
    assert O.flow_rank(None) == O.FLOW_RANK_MISSING
    assert O.flow_rank({"state": "weird"}) == O.FLOW_RANK_MISSING


def test_a_true_zero_distance_sorts_FIRST():
    """The old `dist_pct or 99.0` guard sent a true 0.0 to the BACK of the
    list. Price exactly on the band top is inside it and leads."""
    assert _order([("ON_TOP", HI, "neutral", 0.0),
                   ("JUST_OUT", _px_above(0.01), "inflow", 0.5)]) == ["ON_TOP", "JUST_OUT"]
    k0 = O.proximity_key_from(O.STATE_ABOVE, 0.0, None)
    k1 = O.proximity_key_from(O.STATE_ABOVE, 0.3, None)
    assert k0 < k1


def test_missing_price_or_band_ranks_last_not_first_and_never_raises():
    real = _key(_px_above(1.0))
    for junk in ((None, LO, HI), (99.0, None, HI), (99.0, LO, None),
                 ("abc", LO, HI), (float("nan"), LO, HI), (0.0, LO, HI),
                 (-5.0, LO, HI)):
        k = O.proximity_key(*junk, inflow=None)
        assert k[0] == O.STATE_UNKNOWN and k > real
    # a reversed band is still a band
    assert O.geometry(97.0, HI, LO) == (O.STATE_IN, 0.0)


def test_none_plan_entry_zone_deep_demand_or_block_never_crash_the_row_keys():
    for row in ({}, {"approaching": None}, {"approaching": {"band": None}},
                {"entry_zone": None, "plan": None, "last_price": None},
                {"symbol": "X", "last_price": 10.0, "approaching": {"dist_pct": None}}):
        O.approaching_key(row)
    for row in ({}, {"approaching_ob": None}, {"approaching_ob": {"block": None}}):
        O.approaching_ob_key(row)
    for row in ({}, {"in_ob": None}, {"in_ob": {"block": None}},
                {"in_ob": {"block": {"bars_ago": None}}}):
        O.in_ob_key(row)
    for row in ({}, {"deep_demand": None}, {"deep_demand": {"second_band": None}},
                {"deep_demand": {"state": "in"}, "last_price": None}):
        O.deep_key(row)
    # a None in a caller tail is pushed last, not a TypeError
    with_drift = _key(_px_above(0.1), tail=(-3.1, "A"))
    no_drift = _key(_px_above(0.1), tail=(None, "A"))
    assert with_drift < no_drift
    sorted([with_drift, no_drift, _key(_px_above(0.1), tail=(None, None))])


# ── inflow_of ────────────────────────────────────────────────────────────────
def test_inflow_of_reads_top_level_then_the_nested_deep_read():
    top = {"inflow": {"state": "inflow", "cmf_20": 0.2}}
    nested = {"deep_demand": {"inflow": {"state": "neutral", "cmf_20": 0.0}}}
    both = {"inflow": {"state": "inflow"}, "deep_demand": {"inflow": {"state": "distribution"}}}
    assert O.inflow_of(top)["state"] == "inflow"
    assert O.inflow_of(nested)["state"] == "neutral"
    assert O.inflow_of(both)["state"] == "inflow"          # top-level wins
    assert O.inflow_of({}) is None and O.inflow_of(None) is None
    assert O.inflow_of({"inflow": None, "deep_demand": None}) is None


# ── per-board keys ───────────────────────────────────────────────────────────
def _ob(sym, px, bars_ago, state=None, cmf=None):
    return {"symbol": sym, "last_price": px,
            "inflow": _flow(state, cmf),
            "in_ob": {"block": {"lo": 98.0, "hi": 100.0, "bars_ago": bars_ago}}}


def test_in_ob_age_leads_then_flow_and_cmf_inside_an_age_tie():
    rows = [_ob("OLD_INFLOW", 99.0, 20, "inflow", 0.3),
            _ob("Y_NOREAD", 99.0, 2),
            _ob("Y_SOLD", 99.0, 2, "distribution", -0.2),
            _ob("Y_INFLOW", 99.0, 2, "inflow", 0.1),
            _ob("NO_AGE", 99.0, None, "inflow", 0.9)]
    assert [r["symbol"] for r in sorted(rows, key=O.in_ob_key)] == [
        "Y_INFLOW", "Y_SOLD", "Y_NOREAD", "OLD_INFLOW", "NO_AGE"]


def test_approaching_key_uses_the_band_and_the_live_price_override():
    def row(sym, px, drift=-2.0, state="neutral", cmf=0.0):
        return {"symbol": sym, "last_price": px, "inflow": _flow(state, cmf),
                "approaching": {"dist_pct": 1.0, "drift_pct": drift,
                                "band": {"lo": LO, "hi": HI}}}
    a, b = row("A", _px_above(0.3)), row("B", _px_above(2.9))
    assert [r["symbol"] for r in sorted([b, a], key=O.approaching_key)] == ["A", "B"]
    live = {"A": _px_above(2.0), "B": _px_above(0.2)}
    assert [r["symbol"] for r in sorted(
        [a, b], key=lambda r: O.approaching_key(r, px=live[r["symbol"]]))] == ["B", "A"]
    # same bucket, same flow → the EXACT distance still decides before the
    # caller's tail (0.10% beats 0.20% even against a harder fall) ...
    c, d = row("C", _px_above(0.10), drift=-1.0), row("D", _px_above(0.20), drift=-4.0)
    assert [r["symbol"] for r in sorted([c, d], key=O.approaching_key)] == ["C", "D"]
    # ... and only an identical distance falls through to drift, then symbol
    e, f = row("E", _px_above(0.10), drift=-1.0), row("F", _px_above(0.10), drift=-4.0)
    assert [r["symbol"] for r in sorted([e, f], key=O.approaching_key)] == ["F", "E"]
    g = row("G", _px_above(0.10), drift=-1.0)
    assert [r["symbol"] for r in sorted([g, e], key=O.approaching_key)] == ["E", "G"]


def test_deep_key_falls_back_to_the_read_when_the_row_has_no_price():
    with_px = {"symbol": "P", "last_price": 99.0,
               "deep_demand": {"state": "in", "dist_pct": 0.0,
                               "second_band": {"lo": LO, "hi": HI, "strength": 50}}}
    read_only_near = {"symbol": "R", "deep_demand": {"state": "near", "dist_pct": 1.2,
                                                     "second_band": {"strength": 50}}}
    read_only_in = {"symbol": "Q", "deep_demand": {"state": "in", "dist_pct": 0.0,
                                                   "second_band": {"strength": 50}}}
    out = [r["symbol"] for r in sorted([read_only_near, with_px, read_only_in], key=O.deep_key)]
    assert out[:2] in (["P", "Q"], ["Q", "P"]) and out[2] == "R"
    # stronger second band breaks an otherwise identical tie
    weak = dict(with_px, symbol="W", deep_demand={**with_px["deep_demand"],
                                                  "second_band": {"lo": LO, "hi": HI, "strength": 10}})
    assert [r["symbol"] for r in sorted([weak, with_px], key=O.deep_key)] == ["P", "W"]
