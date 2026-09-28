"""Journal lane tags for the Chart Maps lane program (2026-09-27).

Pins: a generic lane's tag (deep_demand) survives entry -> exit and gets its
own by_strategy row; hot_pullback / quick_bounce are no longer journaled as
manual (the entries coercion bug); legacy demand_zone maps onto the zones
sid; untagged-era hot pullback / quick bounce entries are recovered from the
lane's own same-day record; narratives say "reversal", never the other word.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.autopsy as AP  # noqa: E402
import trading.exit_engine as EE  # noqa: E402
import trading.journal as JN  # noqa: E402
from tests.test_journal_exits import R  # noqa: E402
from tests.test_program_caps import MiniDB  # noqa: E402


@pytest.fixture
def db(monkeypatch):
    d = MiniDB()
    monkeypatch.setattr(JN, "_db", lambda: d)
    monkeypatch.setattr(EE, "_db", lambda: d)
    return d


def _docs(db):
    return JN._build_docs(JN._ledger_rows(), JN._zone_lanes(), JN._exit_fills())


def test_deep_demand_is_kept_from_entry_through_exit(db):
    reason = {"sid": "deep_demand", "tab": "deep_demand", "adapter": "PLAN",
              "adapter_version": "cm-lanes-v1", "kind": "demand",
              "band": {"lo": 9.37, "hi": 9.59}, "snapshot_ref": "cheetah-CTOS-20260928-entry"}
    db.trade_ledger.rows[:] = [
        R("2026-09-28T13:40:00Z", 1790516400.0, "entry", "CTOS", qty=100, price=9.45,
          stop_price=9.23, stop_pct=2.33, strategy="deep_demand", entry_reason=reason),
        R("2026-09-29T14:00:00Z", 1790604000.0, "trade_closed", "CTOS", leg="stop", fill=9.22,
          gain_pct=-2.43)]
    d = _docs(db)[0]
    assert d["entry"]["strategy"] == "deep_demand"
    assert d["entry"]["program"] == {"sid": "deep_demand", "tab": "deep_demand",
                                     "adapter_version": "cm-lanes-v1",
                                     "snapshot_ref": "cheetah-CTOS-20260928-entry"}
    assert d["status"] == "closed"
    assert "Chart Maps deep_demand lane entry" in d["narrative"] and "9.37-9.59" in d["narrative"]
    assert "bounce" not in d["narrative"].lower()
    bs = JN.by_strategy(_docs(db))
    assert "deep_demand" in bs and bs["deep_demand"]["closed"] == 1 and "manual" not in bs


@pytest.mark.parametrize("tag", ["hot_pullback", "quick_bounce"])
def test_hot_pullback_and_quick_bounce_are_no_longer_manual(db, tag):
    db.trade_ledger.rows[:] = [R("2026-09-28T13:40:00Z", 1790516400.0, "entry", "AAA", qty=10,
                                 price=10.0, stop_price=9.5, stop_pct=5, strategy=tag)]
    d = _docs(db)[0]
    assert d["entry"]["strategy"] == tag
    assert list(JN.by_strategy([d])) == [tag]


def test_legacy_demand_zone_maps_onto_the_zones_sid(db):
    db.trade_ledger.rows[:] = [R("2026-09-28T13:40:00Z", 1790516400.0, "entry", "AAA", qty=10,
                                 price=10.0, stop_price=9.5, stop_pct=5, strategy="demand_zone")]
    d = _docs(db)[0]
    assert d["entry"]["strategy"] == "demand_zone" and d["entry"]["program"]["sid"] == "zones"


def test_non_roster_entries_carry_no_program_block(db):
    db.trade_ledger.rows[:] = [R("2026-09-28T13:40:00Z", 1790516400.0, "entry", "AAA", qty=10,
                                 price=10.0, stop_price=9.5, stop_pct=5, strategy="minervini"),
                               R("2026-09-28T13:41:00Z", 1790516460.0, "entry", "BBB", qty=10,
                                 price=10.0, stop_price=9.5, stop_pct=5)]
    docs = {d["symbol"]: d for d in _docs(db)}
    assert docs["AAA"]["entry"]["program"] is None and docs["BBB"]["entry"]["strategy"] == "manual"
    assert docs["BBB"]["entry"]["program"] is None


def test_an_unknown_tag_is_still_manual(db):
    db.trade_ledger.rows[:] = [R("2026-09-28T13:40:00Z", 1790516400.0, "entry", "AAA", qty=10,
                                 price=10.0, stop_price=9.5, stop_pct=5, strategy="ALPHA")]
    assert _docs(db)[0]["entry"]["strategy"] == "manual"


def test_quick_bounce_recovered_from_the_zone_state(db):
    """Before the fix quick_bounce was ledgered as manual; the zone-edge
    state doc that ordered it names the lane (journal only)."""
    db.trade_ledger.rows[:] = [R("2026-09-15T13:40:00Z", 1789479600.0, "entry", "QBX", qty=10,
                                 price=10.0, stop_price=9.5, stop_pct=5, strategy="manual")]
    db.zone_edge_entry_state.rows.append({"symbol": "QBX", "date": "2026-09-15", "side": "demand",
                                          "order_ts": "x", "strategy": "quick_bounce"})
    assert _docs(db)[0]["entry"]["strategy"] == "quick_bounce"


def test_autopsy_reads_a_program_demand_entry_as_chart_maps():
    e = {"strategy": "deep_demand",
         "entry_reason": {"kind": "demand", "band": {"lo": 9.37, "hi": 9.59, "touches": 3},
                          "stop_pct": 2.3}}
    d = AP.detect(e, None)
    assert (d["strategy"], d["kind"], d["band"]["lo"]) == ("chart_maps", "demand", 9.37)
    qb = AP.detect({"strategy": "quick_bounce", "entry_reason": {"band": {"lo": 1, "hi": 2}}}, None)
    assert qb["strategy"] == "zone_edge" and qb["kind"] == "demand"
    # NEGATIVE: a manual entry with a stray demand reason is not claimed
    man = AP.detect({"strategy": "manual", "entry_reason": {"kind": "demand",
                                                            "band": {"lo": 1, "hi": 2}}}, None)
    assert man["strategy"] == "manual"
