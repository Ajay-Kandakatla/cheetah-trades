"""The infosec roster (Ajay 2026-09-14: "Where is information security? Like
NTSK and other companies").

He asked while watching AI names dump, and the app could not answer at ANY
grain: there was no cyber roster, and the Technology sector averaged collapsing
semis against ripping software into a flat +1.15.

Measured that morning on live pre-market prints: the 15 names below ran a
median +7.80% while ai_semis ran -6.95% on the same tape — +8.00pp vs RSP, all
15 green. That rotation is the reason the roster exists.
"""
from __future__ import annotations

import pytest

from sepa import universe as U


def test_NTSK_resolves_and_the_roster_exists():
    """The name he actually asked about."""
    assert "infosec" in U.THEME_UNIVERSE
    assert U.theme_for("NTSK") == "infosec"
    assert len(U.THEME_UNIVERSE["infosec"]) == 15


def test_NEGATIVE_the_dead_tickers_are_not_in_it():
    """VALIDATED BY LAST BAR DATE, NOT BAR COUNT — the SDIG trap: a dead ticker
    keeps its whole history, so `len(bars)` says nothing about liveness.

    CYBR's last bar is 2026-02-10, JAMF's 2026-01-29, and MIME has no data at
    all. All three would have looked healthy on a bar count.
    """
    roster = set(U.THEME_UNIVERSE["infosec"])
    for dead in ("CYBR", "JAMF", "MIME"):
        assert dead not in roster, f"{dead} failed liveness validation"


def test_NEGATIVE_the_CDN_and_observability_names_are_excluded():
    """A roster that admits every company with a security line stops measuring
    the thesis. NET and AKAM are CDNs, DDOG is observability."""
    roster = set(U.THEME_UNIVERSE["infosec"])
    for adjacent in ("NET", "AKAM", "DDOG"):
        assert adjacent not in roster


def test_every_theme_has_a_priority_and_none_is_orphaned():
    """A theme missing from THEME_PRIORITY sorts last silently. Adding a roster
    without a rank is the easy half of this change to forget."""
    assert set(U.THEME_PRIORITY) == set(U.THEME_UNIVERSE)
    assert U.THEME_PRIORITY["infosec"] < U.THEME_PRIORITY["crypto"]


def test_the_rosters_stay_disjoint():
    """`_assert_themes_disjoint` is the existing invariant — one ticker, one
    theme — and 15 new names is the most likely way to break it."""
    U._assert_themes_disjoint()
    seen, dupes = set(), []
    for names in U.THEME_UNIVERSE.values():
        for n in names:
            if n in seen:
                dupes.append(n)
            seen.add(n)
    assert not dupes, f"a ticker is in two rosters: {dupes}"


def test_the_measurement_that_justified_it_rides_with_it():
    """SOURCE GUARD. A roster added on the strength of one morning's rotation
    must carry that number, and the three names it rejected."""
    import inspect
    src = inspect.getsource(U)
    assert "+7.80%" in src and "-6.95%" in src
    assert "CYBR" in src and "JAMF" in src
