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
    assert RI._pct(ZEE.STOP_BUFFER_PCT) in p and ("%d per day" % ZEE.MAX_ZONE_ENTRIES_PER_DAY) in p
    assert "/".join(CE.QUADRANTS_OK) in p and ("$%dM" % int(CE.CATALYST_MIN_DOLLAR_VOL / 1e6)) in p
    assert ("%d positions" % RR.MAX_POSITIONS) in p


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
