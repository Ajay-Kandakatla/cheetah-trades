"""AI Servers / Systems — the layer that had no home (2026-09-12).

Ajay, after the breakout board started ranking by recency and surfaced HPQ /
HPE / DELL / SWKS breaking out on the same day with no AI tag between them:
*"Add them please"*.

WHY A NEW SECTOR RATHER THAN A LINE IN AN EXISTING ONE: `ai_chips` is silicon,
`memory_hbm` is DRAM, `cloud_infra` is the HYPERSCALERS who buy the racks, and
`optical_interconnect` is the networking. Nothing covered the integration layer,
so DELL / HPE / SMCI resolved to None and sank below every tagged name on the
AI-first lists he asked for in June 2026.

THE TER TRAP (2026-09-11) IS THE REASON FOR THE COLLISION TESTS: putting a
ticker in a second sector moved Teradyne out of `semis_ai` and into `broad` in
the one-bucket-per-ticker map, silently dropping its chip-export-control risk.
"""
from __future__ import annotations

import pytest

from sepa import macro_risk as MR
from supply_demand import sectors as S

MEMBERS = ("DELL", "HPE", "SMCI")


def _sector(sid):
    return next(s for s in S.SECTORS if s["id"] == sid)


def test_the_sector_exists_and_carries_the_three_server_OEMs():
    sec = _sector("ai_servers")
    assert sec["label"] == "AI Servers / Systems"
    assert set(sec["sp_tickers"]) == set(MEMBERS)


def test_every_member_now_resolves_to_an_AI_SECTOR():
    """The whole point: before this they returned None and sorted last on a
    board explicitly ranked AI-first."""
    for t in MEMBERS:
        got = S.ai_sector_for_ticker(t)
        assert got is not None, f"{t} must carry an AI-ecosystem tag"
        assert got["id"] == "ai_servers"


def test_it_ranks_BEHIND_the_silicon_it_integrates_but_AHEAD_of_the_building():
    """chips → memory → servers → energy/cooling/grid → software → REITs."""
    order = S.AI_SECTOR_PRIORITY
    assert order.index("ai_chips") < order.index("ai_servers")
    assert order.index("memory_hbm") < order.index("ai_servers")
    assert order.index("ai_servers") < order.index("ai_software")
    assert order.index("ai_servers") < order.index("datacenter_reits")
    assert S.ai_sector_for_ticker("NVDA")["rank"] < S.ai_sector_for_ticker("DELL")["rank"]


def test_members_inherit_CHIP_EXPORT_CONTROL_risk():
    """They ship mostly-NVIDIA value, so a chip export control hits them
    directly — SMCI most of all. Without the bucket mapping they fall through
    to 'broad' and stop inheriting the one macro risk that moves them."""
    for t in MEMBERS:
        assert MR.sector_of(t) == "semis_ai", t


def test_NEGATIVE_no_member_was_already_in_another_sector_the_TER_TRAP():
    """`_build_ticker_buckets` uses setdefault — FIRST sector wins. A member
    that already sat in some other sector could be silently re-bucketed, which
    is exactly what happened to Teradyne on 2026-09-11."""
    for t in MEMBERS:
        owners = [s["id"] for s in S.SECTORS if t in (s.get("sp_tickers") or [])]
        assert owners == ["ai_servers"], f"{t} is in {owners} — re-bucketing risk"


def test_NEGATIVE_TER_still_carries_its_chip_export_risk():
    """The regression this class of change caused once already."""
    assert MR.sector_of("TER") == "semis_ai"


def test_NEGATIVE_it_invents_no_supply_gap():
    """Same honesty rule as cybersecurity/biotech: `gap_economics` renders a $
    demand-vs-supply bar with a sources line. Assembly capacity is not the
    bottleneck — GPU allocation upstream is — so the field stays OFF and the
    thesis says so in words."""
    sec = _sector("ai_servers")
    assert not sec.get("gap_economics")
    assert "not a supply gap" in sec["thesis"].lower()


def test_NEGATIVE_the_RF_HANDSET_semis_were_deliberately_NOT_added():
    """He named SWKS with DELL and HPE. Skyworks and Qorvo are RF front-end
    suppliers whose revenue is overwhelmingly handsets — they broke out the
    same day as the server names, which is co-movement, not membership.
    Tagging them AI would pollute the exact ranking this sector exists to fix.
    Flagged to him rather than added; this test records the decision so it does
    not quietly reverse."""
    for t in ("SWKS", "QRVO"):
        assert S.ai_sector_for_ticker(t) is None, (
            f"{t} is an RF/handset semi — adding it dilutes the AI-first rank")


def test_NEGATIVE_HPQ_is_not_HPE():
    """HPQ is PCs and printers; HPE is the enterprise/AI server business. They
    broke out on the same day and are one letter apart."""
    assert S.ai_sector_for_ticker("HPQ") is None
    assert S.ai_sector_for_ticker("HPE") is not None
