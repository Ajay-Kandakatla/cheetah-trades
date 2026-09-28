"""Fix round 2026-09-27 — the critic's confirmed findings on the Chart Maps
lane program, each pinned with its negatives. Hermetic: MiniDB + fake broker.

  1. GET /trading/strategies serves `enabled` = the row's own switch
     (program_caps.switch_on) and `buying_now` = program_caps.strategy_on, so
     with the program OFF the page shows the ON set that starts buying (not
     0DTE ON / deep_demand OFF);
  3. entries.enter refuses a not-a-lane tag (vcp, topping) in every mode, and an
     unknown tag takes the one-entry-per-minute slot (only manual is exempt);
  4. confirming a stale zone-rules card never loosens min_touches.
"""
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.chart_maps_lanes as CML  # noqa: E402
import trading.entries as EN  # noqa: E402
import trading.exit_engine as EE  # noqa: E402
import trading.lane_review as LR  # noqa: E402
import trading.program_caps as PC  # noqa: E402
import trading.strategy_tags as ST  # noqa: E402
from tests.test_entries_program import env  # noqa: E402,F401
from tests.test_lane_review import _seed, rv  # noqa: E402,F401
from tests.test_program_caps import et  # noqa: E402


# ── 1. switch vs buying now ─────────────────────────────────────────────────
def test_switch_on_is_the_program_on_rule_whatever_the_program_state():
    off, on = {"cm_program": False}, {"cm_program": True}
    for cfg in (off, on):
        assert {s for s in ST.lane_sids() if PC.switch_on(s, cfg)} == set(ST.DEFAULT_ON)
    assert PC.switch_on("amd", {"cm_lanes": {"amd": False}}) is False
    assert PC.switch_on("keltner", {"cm_lanes": {"keltner": True}}) is True
    assert PC.switch_on("breakout", {}) is ("breaking" in ST.DEFAULT_ON)   # legacy tag maps


def test_switch_on_negatives_not_a_lane_and_non_roster_are_off():
    """NEGATIVE: vcp / topping are never ON, even with a cm_lanes True; a
    non-roster tag (minervini, manual, junk) has no program switch."""
    for sid in ("vcp", "topping"):
        assert PC.switch_on(sid, {"cm_program": True, "cm_lanes": {sid: True}}) is False
    for tag in ("minervini", "manual", "options_zone", "nope", None, 5):
        assert PC.switch_on(tag, {"cm_program": True}) is False


def test_strategy_on_is_unchanged_by_the_split():
    """strategy_on still returns the program-OFF rules (existing lanes on their
    own switches) — the engine's behaviour did not move."""
    off = {"cm_program": False}
    assert {s for s in ST.lane_sids() if PC.strategy_on(s, off, "paper")} == set(ST.EXISTING_LANE_SIDS)
    on = {"cm_program": True}
    assert {s for s in ST.lane_sids() if PC.strategy_on(s, on, "paper")} == set(ST.DEFAULT_ON)
    assert PC.strategy_on("vcp", on, "paper") is False


@pytest.fixture
def payload(monkeypatch):
    cfg = {"cm_program": False}
    fake_ee = types.SimpleNamespace(get_config=lambda: cfg,
                                    broker=types.SimpleNamespace(mode=lambda: "paper"),
                                    _db=lambda: None)
    monkeypatch.setattr(CML, "_EE", lambda: fake_ee)
    monkeypatch.setattr(PC, "status_block", lambda c, m, b=None: {"enabled": PC.enabled(c, m)})
    monkeypatch.setattr(PC, "priority_order",
                        lambda now=None: {"day": "2026-09-28", "order": list(ST.lane_sids()),
                                          "counts": {}, "source": "test"})
    monkeypatch.setattr(LR, "scoreboard", lambda *a, **k: {})
    monkeypatch.setattr(CML, "_snapshot_block", lambda sid, n: None)

    def build(**c):
        cfg.clear()
        cfg.update(c)
        body = CML.strategies_payload(now=et(10, 0))
        return {r["sid"]: r for r in body["strategies"]}
    return build


def test_program_off_payload_shows_the_on_set_and_what_buys_now(payload):
    """The critic's probe: program OFF used to serve 6 ON (0DTE ON; deep_demand,
    amd, bonde, growth, patterns OFF). Now `enabled` is the 10 DEFAULT_ON and
    `buying_now` is the existing lanes."""
    rows = payload(cm_program=False)
    assert {s for s, r in rows.items() if r["enabled"]} == set(ST.DEFAULT_ON)
    assert {s for s, r in rows.items() if r["buying_now"]} == set(ST.EXISTING_LANE_SIDS)
    assert rows["signals"]["enabled"] is False and rows["signals"]["buying_now"] is True
    for sid in ("deep_demand", "amd", "bonde", "growth", "patterns"):
        assert rows[sid]["enabled"] is True and rows[sid]["buying_now"] is False


def test_program_on_payload_enabled_equals_buying_now(payload):
    rows = payload(cm_program=True, cm_lanes={"amd": False, "keltner": True})
    for r in rows.values():
        assert r["enabled"] is r["buying_now"]
    assert rows["amd"]["enabled"] is False and rows["keltner"]["enabled"] is True


def test_a_cm_lanes_override_shows_even_with_the_program_off(payload):
    """NEGATIVE: an OFF override on a default-ON lane reads OFF before the
    program starts (the page used to show every generic lane OFF regardless)."""
    rows = payload(cm_program=False, cm_lanes={"deep_demand": False})
    assert rows["deep_demand"]["enabled"] is False
    assert rows["deep_demand"]["switch"]["value"] is False


# ── 3. the buy path: not-a-lane tags and unknown tags ───────────────────────
@pytest.mark.parametrize("program", [False, True])
@pytest.mark.parametrize("tag", ["vcp", "topping"])
def test_a_not_a_lane_tag_is_refused_in_every_mode(env, tag, program):
    """NEGATIVE: the critic's probe placed VVV (vcp) and TTT (topping)."""
    brk, db, _ = env(program=program)
    PC.set_tick_minute(et(10, 0))
    with pytest.raises(ValueError) as exc:
        EN.enter("VVV", stop_price=48.5, strategy=tag)
    assert str(exc.value) == "program-cap: %s is not a lane (never buys)" % tag
    assert brk.brackets == [] and brk.reads == []
    assert PC.minute_taken(et(10, 0)) is None                # the minute was not burned


def test_the_critic_probe_now_places_one_buy_a_minute(env):
    """NEGATIVE: vcp, topping, deep_demand in one minute -> only deep_demand."""
    brk, db, _ = env(program=True)
    PC.set_tick_minute(et(10, 0))
    for sym, tag in (("VVV", "vcp"), ("TTT", "topping")):
        with pytest.raises(ValueError, match="is not a lane"):
            EN.enter(sym, stop_price=48.5, strategy=tag)
    EN.enter("AAA", stop_price=48.5, strategy="deep_demand")
    assert [b["symbol"] for b in brk.brackets] == ["AAA"]


def test_an_unknown_tag_takes_the_minute_but_is_journaled_manual(env):
    brk, db, _ = env()
    PC.set_tick_minute(et(10, 1))
    EN.enter("TYP", stop_price=48.5, strategy="deep_demnd")   # a typo
    row = [r for r in db.trade_ledger.rows if r.get("kind") == "entry"][-1]
    assert row["detail"]["strategy"] == "manual"
    assert PC.minute_taken(et(10, 1))["sid"] == "deep_demnd"
    with pytest.raises(ValueError, match="one entry per minute"):
        EN.enter("BBB", stop_price=48.5, strategy="demand_zone")
    with pytest.raises(ValueError, match="one entry per minute"):
        EN.enter("CCC", stop_price=48.5, strategy="another_typo")
    assert [b["symbol"] for b in brk.brackets] == ["TYP"]


@pytest.mark.parametrize("strategy", ["manual", None])
def test_explicit_manual_and_no_tag_stay_exempt(env, strategy):
    """NEGATIVE: the fix must not throttle his own manual buys."""
    brk, db, _ = env()
    PC.set_tick_minute(et(10, 2))
    PC.claim("amd", "ZZZ")
    EN.enter("MMM", stop_price=48.5, strategy=strategy)
    assert [b["symbol"] for b in brk.brackets] == ["MMM"]
    assert PC.minute_taken(et(10, 2))["symbol"] == "ZZZ"      # manual claimed nothing


# ── 4. a stale card never loosens a zone rule ───────────────────────────────
def test_a_stale_min_touches_card_cannot_lower_a_stricter_config(rv):
    """NEGATIVE: the critic's probe — config 3, card 2 -> stays 3."""
    db, _ = rv
    db.trading_config.rows[0]["zone_edge_rules"] = {"min_touches": 3}
    _seed(db, "p1", kind="class:band_failed", level="config",
          change={"key": "zone_edge_rules", "value": {"min_touches": 2}})
    out = LR.confirm("p1", "o")
    assert out["status"] == "confirmed"
    assert EE.get_config()["zone_edge_rules"] == {"min_touches": 3}


def test_a_min_touches_card_still_tightens(rv):
    db, _ = rv
    db.trading_config.rows[0]["zone_edge_rules"] = {"min_touches": 1, "demand_residents": True}
    _seed(db, "p2", kind="class:band_failed", level="config",
          change={"key": "zone_edge_rules", "value": {"min_touches": 2}})
    LR.confirm("p2", "o")
    assert EE.get_config()["zone_edge_rules"] == {"min_touches": 2, "demand_residents": True}
    db.trading_config.rows[0]["zone_edge_rules"] = None
    _seed(db, "p3", kind="class:band_failed", level="config",
          change={"key": "zone_edge_rules", "value": {"min_touches": 2}})
    LR.confirm("p3", "o")
    assert EE.get_config()["zone_edge_rules"] == {"min_touches": 2}


def test_a_bad_min_touches_card_is_still_refused(rv):
    """NEGATIVE: the max() does not launder an invalid value past validate_rules."""
    db, _ = rv
    db.trading_config.rows[0]["zone_edge_rules"] = {}
    _seed(db, "p4", level="config", change={"key": "zone_edge_rules", "value": {"min_touches": 11}})
    with pytest.raises(ValueError, match="min_touches"):
        LR.confirm("p4", "o")
