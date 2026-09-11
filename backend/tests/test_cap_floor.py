"""The market-cap floor is ONE rule, copied into five modules.

Ajay set it at a billion on 2026-09-03 ("billion or at least bigger than a
billion") and moved it to $700M on 2026-09-10 ("make cap 700 m"). Five separate
S/D paths carry their own MIN_CAP_USD, and nothing made them agree — so a
future change to one of them silently leaves the others behind, and a name
would pass the alert gate while having no pre-built zone, or reach the paper
lane while the push that justifies it never fires.

These tests pin them equal. They are NOT a claim that the floor is correct:
lowering it WIDENS the eligible set (+80 names, +5.3%, measured 2026-09-10),
which is a loosening he asked for, not an edge anyone measured.
"""
from __future__ import annotations

import importlib

import pytest

MODULES = [
    "supply_demand.demand_alerts",
    "supply_demand.zone_bounce_alerts",
    "supply_demand.zone_edge",
    "supply_demand.zone_store",
    "trading.zone_edge_entry",
    "trading.options_lane",
]

EXPECTED = 700_000_000.0


@pytest.mark.parametrize("name", MODULES)
def test_every_path_uses_the_same_cap_floor(name):
    mod = importlib.import_module(name)
    assert hasattr(mod, "MIN_CAP_USD"), "%s lost its cap floor" % name
    assert float(mod.MIN_CAP_USD) == EXPECTED, (
        "%s has a cap floor of %s while the rest use %s — one rule, five copies, "
        "and they must not drift" % (name, mod.MIN_CAP_USD, EXPECTED))


def test_the_floor_is_the_gate_not_a_suggestion():
    """NEGATIVE. A name UNDER the floor must fail, and an unknown cap must fail
    too — an unpriced name is not a small name, but it is not a known-big one
    either, and this gate fails closed."""
    from supply_demand.demand_alerts import MIN_CAP_USD, passes_cap

    assert passes_cap(MIN_CAP_USD) is True
    assert passes_cap(MIN_CAP_USD + 1) is True
    assert passes_cap(MIN_CAP_USD - 1) is False
    assert passes_cap(None) is False
    assert passes_cap(float("nan")) is False


def test_lowering_the_floor_only_widens_never_narrows():
    """The change must be monotone: everything that passed at $1B still passes
    at $700M. A regression that inverted the comparison would be invisible in a
    count and obvious here."""
    from supply_demand.demand_alerts import passes_cap

    for cap in (7e8, 9e8, 1e9, 5e9, 3e12):
        if passes_cap(cap, 1_000_000_000.0):
            assert passes_cap(cap, 700_000_000.0), cap
