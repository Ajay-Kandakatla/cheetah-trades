"""ℹ️ Rules panel (2026-09-06): every line is built from the enforcing
module's constants, so the numbers on the page can never drift from the
code. These tests pin that: each key exists, every section carries the
three categories, and the live constants appear in the text."""
from __future__ import annotations

import pytest

from supply_demand import rules_info as RI
from supply_demand import alert_gates as AG
from supply_demand import demand_alerts as DA
from supply_demand import demand_reentry as DR
from supply_demand import zone_bounce_alerts as ZB
from supply_demand import zone_edge as ZE
from trading import risk_rules as RR
from trading import auto_entry as AE
from trading import zone_edge_entry as ZEE
from trading import catalyst_entry as CE


def _text(sec: dict) -> str:
    return " ".join(sec["picks"] + sec["stops"] + sec["alerts"] + [sec["note"]])


def test_every_section_has_the_three_categories_and_a_title():
    secs = RI.sections()
    assert tuple(secs) == RI.SECTION_KEYS
    for key, sec in secs.items():
        assert sec["title"] and sec["emoji"], key
        for cat in ("picks", "stops", "alerts"):
            assert isinstance(sec[cat], list), (key, cat)
            assert all(isinstance(x, str) and x for x in sec[cat]), (key, cat)
        assert sec["picks"] and sec["stops"], key      # never an empty panel
        assert len(sec["picks"]) <= 8 and len(sec["stops"]) <= 6, key   # few lines


def test_numbers_come_from_the_enforcing_modules():
    secs = RI.sections()
    d = _text(secs["in_demand"])
    assert RI._pct(DR.STOP_BUFFER_PCT) in d and RI._pct(RR.ABS_MAX_STOP_PCT) in d
    assert ("%d times" % DR.MIN_TOUCHES) in d and ("%d bars" % DR.REENTRY_LOOKBACK_BARS) in d
    assert RI._pct(DR.MIN_ROOM_DEFAULT) in d and RI._pct(DR.ENTRY_ABOVE_TOL_PCT) in d
    a = _text(secs["alerts"])
    assert RI._pct(AG.ALERT_MIN_ROOM_PCT) in a and RI._pct(AG.ALERT_MAX_ABOVE_DEMAND_PCT) in a
    assert RI._pct(DA.AT_PCT) in a and RI._pct(DA.NEAR_PCT) in a
    assert RI._pct(ZB.BOUNCE_MIN_PCT) in a and RI._pct(ZB.STRONG_PCT) in a
    assert RI._pct(ZE.BROKE_MAX_PCT) in a and ("%d%%" % int(ZE.NEW_HIGH_TOL * 100)) in a
    assert RI._t(DA.SESSION_OPEN) in a and RI._t(ZE.SESSION_OPEN) in a
    p = _text(secs["autopilot"])
    assert ("score ≥ %d" % int(AE.AUTO_MIN_SCORE)) in p and ("RS ≥ %d" % int(AE.AUTO_MIN_RS)) in p
    assert RI._pct(RR.NORMAL_STOP_BAND[0]) in p and RI._pct(RR.DIFFICULT_STOP_BAND[1]) in p
    assert RI._pct(ZEE.STOP_BUFFER_PCT) in p and ("%d+%d per day" % (ZEE.MAX_ZONE_ENTRIES_PER_SIDE_PER_DAY, ZEE.MAX_ZONE_ENTRIES_PER_SIDE_PER_DAY)) in p
    assert "/".join(CE.QUADRANTS_OK) in p and ("$%dM" % int(CE.CATALYST_MIN_DOLLAR_VOL / 1e6)) in p
    assert ("%d positions" % RR.MAX_POSITIONS) in p


def test_the_deep_demand_prose_is_built_from_the_enforcing_constants():
    """🕳️ Deep Demand, widened 2026-09-16 (Ajay: "the stocks that crosses the
    first level of support and lying in second or third level of support").

    The panel line must state the DEPTH CAP and the band bar, and every figure
    in it has to come from the module that enforces it — `deep_demand`'s own
    cap and ordinal, `demand_reentry`'s band bar, `price_zones`' near scale.
    A retyped "2nd or 3rd" is exactly how this panel went stale before."""
    from supply_demand import deep_demand as DD
    from supply_demand import price_zones as PZ

    t = _text(RI.sections()["deep_demand"])
    assert DD.ordinal(DD.MAX_LEVELS_BROKEN + 1) in t              # "3rd"
    assert ("(%d crossed)" % DD.MAX_LEVELS_BROKEN) in t
    assert RI._pct(PZ.NEAR_PCT) in t
    assert ("≥ %d touches" % DR.MIN_TOUCHES) in t
    assert ("strength ≥ %d" % int(DR.MIN_ZONE_STRENGTH)) in t
    assert "crossed one or more demand bands" in t and "next level down" in t
    assert "band being ENTERED" in t
    # the old fixed-pair wording must be gone
    assert "SECOND band from the top" not in t
    # house rule: the word on any surface he reads is "reversal", never "bounce"
    assert "bounce" not in t.lower()


def test_the_deep_demand_prose_types_no_number_of_its_own():
    """NEGATIVE, the mutation guard: not one numeric literal may appear inside
    a quoted string of the Deep Demand block — every number must arrive
    through a %s/%d fed by a constant. If MAX_LEVELS_BROKEN, MIN_TOUCHES,
    MIN_ZONE_STRENGTH or NEAR_PCT moves, the panel moves with it."""
    import inspect
    import re

    src = inspect.getsource(RI.sections)
    start = src.index('out["deep_demand"]')
    end = src.index('out["alerts"]', start)
    block = src[start:end]
    literals = re.findall(r'"([^"\\]*)"', block)
    joined = " ".join(literals)
    assert "Deep Demand" in joined, "the block was not located"
    offenders = [s for s in literals if any(ch.isdigit() for ch in s)]
    assert offenders == [], f"Deep Demand prose types its own numbers: {offenders}"
    for typed in ("40", "3%", "2nd", "3rd", "second or third"):
        assert typed not in joined, typed


def test_sd_sections_never_cite_the_book():
    """feedback_sepa_book_scope: S/D rules carry no Minervini cites; only the
    Auto-Pilot section names the book for its Minervini lane."""
    secs = RI.sections()
    for key in ("in_demand", "deep_demand", "alerts", "sepa_bounce", "catalysts"):
        t = _text(secs[key]).lower()
        assert "minervini" not in t and "tlsw" not in t and "p." not in t.replace("p.m", ""), key
    assert "TLSW" in secs["autopilot"]["note"]


def test_payload_narrows_to_one_section_and_lists_keys():
    full = RI.payload()
    assert set(full["sections"]) == set(RI.SECTION_KEYS) and full["keys"] == list(RI.SECTION_KEYS)
    one = RI.payload("alerts")
    assert list(one["sections"]) == ["alerts"]
    assert RI.payload("nope")["sections"] == {}


def test_helpers_format_like_the_page_reads():
    assert RI._pct(5.0) == "5%" and RI._pct(1.5) == "1.5%" and RI._pct(0.5) == "0.5%"
    assert RI._b(1_000_000_000.0) == "$1B"
    # REGRESSION (2026-09-10): integer-billions printed "$0B" for the $700M
    # floor he set — the ℹ️ panel would have told him there is no floor.
    assert RI._b(700_000_000.0) == "$700M"
    assert RI._b(250_000_000.0) == "$250M"
    assert RI._b(1_500_000_000.0) == "$1.5B"
    from datetime import time as dtime
    assert RI._t(dtime(9, 32)) == "9:32" and RI._t(dtime(16, 0)) == "16:00"


@pytest.mark.anyio
async def test_route_serves_the_payload_and_404s_an_unknown_section():
    import json
    from fastapi import HTTPException
    from supply_demand import api as SA
    res = await SA.supply_demand_rules(section=None)
    body = json.loads(res.body)
    assert set(body["sections"]) == set(RI.SECTION_KEYS)
    res = await SA.supply_demand_rules(section="alerts")
    assert list(json.loads(res.body)["sections"]) == ["alerts"]
    with pytest.raises(HTTPException):
        await SA.supply_demand_rules(section="nope")


def test_the_BONDE_section_leads_with_the_measurement_and_never_retypes_it():
    """ℹ️ Rules panel — 📈 Bonde.

    Two things at once. First, the panel must carry the verdict, because the
    tab's own thesis measured inverted and the panel is where a reader goes to
    find out what a board actually does. Second, every figure is read from
    `sepa.bonde.MEASURED` rather than typed here — the panel's whole design
    rule is that a line is built from the constant that enforces it, and a
    measured number is the case where drift is most expensive.
    """
    from supply_demand import rules_info as RI
    from sepa import bonde as BD

    sec = RI.sections()["bonde"]
    assert "bonde" in RI.payload()["keys"]
    blob = " ".join(sec["picks"] + sec["stops"] + sec["alerts"])

    assert "INVERTED" in blob
    assert "%.2f" % abs(BD.MEASURED["cell_a_med_21d"]) in blob     # −3.22
    assert "%.1f" % BD.MEASURED["cell_a_win_21d"] in blob          # 39.8
    assert "%.1f" % BD.MEASURED["placebo_win_21d"] in blob         # the placebo
    assert BD.MEASURED["scripts"] in blob
    assert "NOTHING HERE PUSHES, GATES OR BUYS" in blob

    # whose numbers are whose — his tiers, this app's pivot thresholds
    assert "not figures Bonde published" in blob
    # and the 8%/5x line must read as a percentage, not as a format artifact
    assert "8%%" not in blob
