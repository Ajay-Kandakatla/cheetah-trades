"""The semi_materials THEME — the Chart Maps half of the 2026-09-11 sector work.

Ajay, correcting me after I shipped it to the wrong surface:
  "i dont use supply deman page at all.. I only been using chart maps not sure
   why you are upating it"

supply_demand/sectors.py renders on /supply-demand ONLY. The Chart Maps 🔥
Hot-sectors strip ranks THEMES, which come from sepa/universe.THEME_UNIVERSE.
Same roster, two files, because the two surfaces read different lists.
"""
import pytest

from sepa import universe as U

KEY = "semi_materials"


def test_the_theme_exists_and_carries_the_two_that_ran():
    assert KEY in U.THEME_UNIVERSE
    t = set(U.THEME_UNIVERSE[KEY])
    assert len(t) >= 10
    assert {"AEHR", "COHU"} <= t, "the two names that actually ran must be in it"
    assert {"ENTG", "MTRN", "CBT", "ROG"} <= t, "the consumables leg"
    assert {"AMKR", "KLIC", "ACLS", "PLAB"} <= t, "the test / packaging leg"


def test_themes_stay_a_strict_partition():
    """THE INVARIANT I GOT WRONG FIRST TIME. _assert_themes_disjoint raises at
    import on any ticker in two themes. I wrote this roster with all 17 names
    and a comment claiming overlap was fine; the assert caught five of them
    (FORM/ICHR/ONTO/UCTT in ai_semis, TER in robotics). They stayed where they
    were and this theme is the 12 that had no theme at all."""
    seen = {}
    for name, syms in U.THEME_UNIVERSE.items():
        for s in syms:
            assert s not in seen, "%s in both %s and %s" % (s, name, seen[s])
            seen[s] = name
    U._assert_themes_disjoint()          # the real guard, called directly


def test_NEGATIVE_it_does_not_steal_from_ai_semis_or_robotics():
    """Those rosters are ones he already watches; moving a name out of them
    would silently change a board he reads."""
    mine = set(U.THEME_UNIVERSE[KEY])
    assert {"FORM", "ICHR", "ONTO", "UCTT"} <= set(U.THEME_UNIVERSE["ai_semis"])
    assert "TER" in U.THEME_UNIVERSE["robotics"]
    assert not (mine & {"FORM", "ICHR", "ONTO", "UCTT", "TER"})


@pytest.mark.parametrize("ticker", sorted(U.THEME_UNIVERSE[KEY]))
def test_every_theme_ticker_is_in_the_scan_universe(ticker):
    """A theme name outside load_universe('full') charts nowhere — the NTSK
    lesson, which applies to themes exactly as it does to sectors."""
    assert ticker in {s.upper() for s in U.load_universe("full")}, (
        "%s is in the theme but outside the scan universe" % ticker)


def test_the_sector_file_keeps_the_fuller_roster():
    """sectors.py has no disjoint constraint, so it carries all 17 — including
    the 5 the theme had to give up. The two must not silently diverge in the
    OTHER direction: every theme name must also be in the sector."""
    from supply_demand.sectors import SECTOR_BY_ID
    sec = set(SECTOR_BY_ID[KEY]["sp_tickers"])
    assert set(U.THEME_UNIVERSE[KEY]) <= sec, \
        "a theme name missing from the sector roster means the two have drifted"
    assert len(sec) == 17
