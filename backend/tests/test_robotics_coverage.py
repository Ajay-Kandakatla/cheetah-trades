"""Robotics coverage — the 3-vs-19 mismatch and the ETFs (2026-09-12).

Ajay: "Do we have a robotic category? Can you find robotics stocks and ETFs
please". It had a theme with 19 names and a sector with THREE — two lists for
one idea, silently disagreeing — and not one robotics ETF was scannable.

The most important test in this file is the NEGATIVE one at the bottom: it
pins that an ETF can never fire an alert. That is a REAL limitation of the
shipped feature, and a test that quietly assumed otherwise would be worse than
no test at all.
"""
from __future__ import annotations

import pytest

from sepa import universe as U
from sepa.universe import THEME_UNIVERSE
from supply_demand import sectors as S
from supply_demand import rules_info as RI
from supply_demand import zone_store as Z
from trading import safety_floor as SF

ETFS = ["KOID", "BOTZ", "ROBO", "ARKQ", "ROBT"]


def _sector(sid):
    return [d for d in S.SECTORS if d.get("id") == sid][0]


# TER is in the robotics THEME but deliberately NOT in the robotics SECTOR.
# sectors.py tolerates a ticker in several sectors; macro_risk builds a
# one-bucket-per-ticker map from the same file, so adding TER to robotics moved
# it from `semis_ai` to `broad` and it stopped inheriting chip-export-control
# risk. Named here rather than hidden in a >= comparison.
SECTOR_EXCLUDES = {"TER": "keeps its semis_ai macro-risk bucket"}


def test_the_sector_and_the_theme_agree_except_where_it_is_documented():
    """Two lists for one idea is how they drift."""
    theme = set(THEME_UNIVERSE["robotics"])
    sec = set(_sector("robotics")["sp_tickers"])
    missing = sorted(theme - sec - set(SECTOR_EXCLUDES))
    assert not missing, "in the robotics THEME but not the sector: %s" % missing


def test_the_documented_exclusion_is_REAL_and_still_needed():
    """A named exception must keep earning its place, or it becomes folklore."""
    from sepa import macro_risk as MR
    for sym in SECTOR_EXCLUDES:
        assert sym in THEME_UNIVERSE["robotics"]
        assert sym not in _sector("robotics")["sp_tickers"]
        assert MR.sector_of(sym) == "semis_ai", (
            "%s no longer needs the exclusion — remove it" % sym)


def test_the_sector_is_no_longer_three_names():
    """REGRESSION. It carried ISRG/AMZN/TSLA against a 19-name theme."""
    assert len(_sector("robotics")["sp_tickers"]) > 10


@pytest.mark.parametrize("sym", ETFS)
def test_every_robotics_etf_is_scannable(sym):
    """`full` is the only universe that reaches a scan, a board or a chart."""
    assert sym in {s.upper() for s in U.load_universe("full")}


def test_the_etfs_are_listed_on_the_sector_they_belong_to():
    assert set(_sector("robotics")["etfs"]) == set(ETFS)
    # the benchmark ETF must be one of them, not a name nothing scans
    assert _sector("robotics")["etf"] in ETFS


# ------------------------------------------------------- the honest limit
def test_NEGATIVE_an_etf_can_NEVER_fire_an_alert_and_that_is_expected():
    """THE POINT OF THIS FILE.

    The provider reports no market cap for a fund, only AUM.
    `big_cap_universe` keeps only a KNOWN cap >= MIN_CAP_USD, so every ETF is
    dropped from the zone store — no bands, therefore no demand, reversal or
    supply-break push, ever.

    Ajay was offered an AUM fallback (option 2) and declined it, because
    MIN_CAP_USD is shared with trading.safety_floor where it blocks REAL buys
    as a manipulation-safety floor. AUM is not market cap.

    If someone later makes ETFs alert, this test SHOULD fail — and they should
    then check that they have not also loosened the entry gate."""
    out = Z.big_cap_universe(universe=ETFS + ["REAL"],
                             caps={**{s: None for s in ETFS}, "REAL": 2e9})
    assert out == ["REAL"]
    assert Z.MIN_CAP_USD == SF.MIN_CAP_USD


def test_the_rules_panel_SAYS_the_etfs_never_alert():
    """His call was "charts and scans only, and say so". An ETF that silently
    never alerts is indistinguishable from a broken alert, so the limitation
    has to reach the screen."""
    import json
    txt = json.dumps(RI.sections())
    assert "ETFs chart and scan but NEVER alert" in txt
    for sym in ETFS:
        assert sym in txt, "%s must be named where the limit is stated" % sym


def test_NEGATIVE_no_robotics_etf_was_added_to_a_THEME_roster():
    """Themes are a strict partition used for rotation medians. An ETF inside
    one would blend a fund's return into the median of its own holdings."""
    for roster in THEME_UNIVERSE.values():
        for sym in ETFS:
            assert sym not in roster
