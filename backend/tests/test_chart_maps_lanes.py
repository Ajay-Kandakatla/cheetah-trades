"""The generic Chart Maps lane + the tick dispatcher (trading/chart_maps_lanes.py).

Ajay 2026-09-27: "stop minerviews use all strategies from Most used from Chart
maps. All of them and journal the," — "Top 10 most-used first".

Pins, all hermetic (MiniDB / CapsBroker / a faked live read / a faked
entries.enter that claims the minute like the real one):
  * no stop is ever invented: a LIST tile with no live band, a PLAN stop at or
    above the print, a short / bearish setup are never bought;
  * the live 🎯 READY read decides — a BLOCKED read (room 3.2%) is a logged
    skip, never an order;
  * snapshot freshness: > 600 s, another day, a board built before the last
    close, an unknown build time all fail closed; a Friday-evening build is
    fine on Monday; the Tuesday after a Monday holiday reads Friday's close;
  * ONE entry per tick across all generic sids — the second sid's live read
    is never even made — while the existing lanes still run (their exits);
  * a transient veto clears the attempt (retried next tick); any other veto
    keeps it (the band is spent for the day); a moved band is skipped;
  * program OFF = the pre-program fixed order, byte for byte; a slot that
    raises never stops the others; the slots follow the usage order.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.chart_maps_lanes as CML  # noqa: E402
import trading.exit_engine as EE  # noqa: E402
import trading.program_caps as PC  # noqa: E402
from supply_demand import enterable  # noqa: E402
from tests.test_program_caps import ET, CapsBroker, MiniDB, et  # noqa: E402

NOW = et(10, 30)                    # Monday 2026-09-28
DAY = "2026-09-28"
ON = {"cm_program": True, "armed": True}


def snap(sid, cands, *, day=DAY, age=60, source_as_of="2026-09-28T13:00:00Z", now=NOW):
    return {"_id": sid, "sid": sid, "day": day, "as_of": now.timestamp() - age,
            "source_as_of": source_as_of, "candidates": cands}


def cand(sym, rank=1, stop=None, buy=None, band=(9.37, 9.59), **extra):
    c = {"symbol": sym, "board_rank": rank}
    if stop is not None or buy is not None:
        c["plan"] = {"stop": stop, "buy": buy, "target": 14.0}
    if band is not None:
        c["enterable"] = {"band": {"lo": band[0], "hi": band[1]}}
    c.update(extra)
    return c


def live_row(px=10.0, band=(9.37, 9.59), verdict=None, short=(), coverage="store"):
    return {"coverage": coverage,
            "enterable": {"verdict": verdict or enterable.READY, "print": {"px": px},
                          "band": ({"lo": band[0], "hi": band[1]} if band else None),
                          "room": 8.4, "gates": {"room_ok": True, "prox_ok": True},
                          "reason_short": list(short), "reasons": []}}


@pytest.fixture
def lane(monkeypatch):
    """(db, brk, enters, reads, set_live) — enter claims the minute like
    entries.enter does and raises the program-wait veto when it is gone."""
    db = MiniDB()
    monkeypatch.setattr(EE, "_db", lambda: db)
    from market_hours import gate
    monkeypatch.setattr(gate, "closed_reason",
                        lambda now=None: None if now is None or now.weekday() < 5 else "weekend")
    live = {}
    reads = []

    def payload(syms, background=True):
        reads.extend(syms)
        return {"rows": {s: live[s] for s in syms if s in live}}

    from supply_demand import bounce_room
    monkeypatch.setattr(bounce_room, "api_payload", payload)
    enters = []
    veto = {"raise": None}

    def fake_enter(sym, **k):
        if veto["raise"] is not None:
            raise veto["raise"]
        ok, why = PC.claim(k.get("strategy"), sym)
        if not ok:
            raise ValueError(why)
        enters.append((sym, k))
        return {"order_id": "o-%s" % sym}

    from trading import entries
    monkeypatch.setattr(entries, "enter", fake_enter)
    PC.set_tick_minute(NOW)
    brk = CapsBroker()
    yield db, brk, enters, reads, live, veto
    PC.set_tick_minute(None)


def _logs(db, sid=None):
    return [r for r in db.cm_lane_log.rows if sid is None or r["sid"] == sid]


# ═════════════════════════════════════════════════════════════════════════════
# The entry rule
# ═════════════════════════════════════════════════════════════════════════════
def test_a_ready_list_candidate_is_bought_with_the_band_floor_stop(lane):
    db, brk, enters, reads, live, _ = lane
    db.cm_lane_snapshot.rows.append(snap("amd", [cand("AAA")]))
    live["AAA"] = live_row()
    out = CML.run_generic(brk, ON, ["amd"], now=NOW)
    assert out["entered"]["symbol"] == "AAA" and out["entered"]["stop_src"] == "band_floor"
    sym, k = enters[0]
    assert k["strategy"] == "amd" and k["limit_price"] is None and k["allow_earnings"] is False
    assert k["stop_price"] == round(9.37 * (1 - CML.STOP_BUFFER_PCT / 100.0), 4)
    r = k["reason"]
    assert (r["sid"], r["adapter"], r["adapter_version"], r["kind"]) == \
        ("amd", "LIST", "cm-lanes-v1", "demand")
    assert r["snapshot_ref"] == "cheetah-AAA-20260928-entry"
    e = db.cm_lane_entries.rows[0]
    assert e["_id"] == r["snapshot_ref"] and e["candidate"]["symbol"] == "AAA"
    assert e["live"]["verdict"] == enterable.READY
    assert db.cm_lane_state.rows[0]["result"] == "entered"


def test_a_list_tile_with_no_live_band_is_never_bought(lane):
    """NEGATIVE: no served stop and no band -> no stop is invented."""
    db, brk, enters, reads, live, _ = lane
    db.cm_lane_snapshot.rows.append(snap("amd", [cand("AAA", band=None), cand("BBB", rank=2)]))
    live["BBB"] = live_row(band=None)
    out = CML.run_generic(brk, ON, ["amd"], now=NOW)
    assert enters == [] and out["entered"] is None
    assert reads == ["BBB"]                              # AAA was never even read
    assert [(r["symbol"], r["reason"]) for r in _logs(db)] == [("BBB", CML.NO_STOP_TEXT)]
    assert db.cm_lane_state.rows == []


def test_a_plan_stop_at_or_above_the_print_is_never_bought(lane):
    db, brk, enters, reads, live, _ = lane
    db.cm_lane_snapshot.rows.append(snap("deep_demand", [cand("AAA", stop=10.0, buy=10.6)]))
    live["AAA"] = live_row(px=10.0)
    CML.run_generic(brk, ON, ["deep_demand"], now=NOW)
    assert enters == [] and _logs(db)[0]["reason"] == CML.NO_STOP_TEXT


def test_a_plan_candidate_uses_the_served_stop(lane):
    db, brk, enters, reads, live, _ = lane
    db.cm_lane_snapshot.rows.append(snap("deep_demand", [cand("AAA", stop=9.23, buy=9.45)]))
    live["AAA"] = live_row(px=9.5)
    out = CML.run_generic(brk, ON, ["deep_demand"], now=NOW)
    assert out["entered"]["stop"] == 9.23 and out["entered"]["stop_src"] == "served"
    assert enters[0][1]["reason"]["served_target"] == 14.0


def test_short_geometry_and_a_bearish_ict_are_never_bought(lane):
    db, brk, enters, reads, live, _ = lane
    cfg = dict(ON, cm_lanes={"ict": True})
    db.cm_lane_snapshot.rows.append(snap("deep_demand", [cand("SHRT", stop=10.5, buy=10.0)]))
    db.cm_lane_snapshot.rows.append(snap("ict", [
        cand("BEAR", stop=9.0, buy=9.5, served={"bias": "bearish", "state": "entry"}),
        cand("WAIT", rank=2, stop=9.0, buy=9.5, served={"bias": "bullish", "state": "armed"})]))
    for s in ("SHRT", "BEAR", "WAIT"):
        live[s] = live_row()
    assert CML._is_long("ict", cand("X", stop=9, buy=9.5, served={"bias": "bearish",
                                                                  "state": "entry"})) \
        == "not a bullish ICT entry"
    out = CML.run_generic(brk, cfg, ["deep_demand", "ict"], now=NOW)
    assert enters == [] and reads == [] and out["entered"] is None


def test_a_blocked_live_read_is_a_logged_skip(lane):
    """NEGATIVE: the list said yes, the live print says room 3.2% -> no order."""
    db, brk, enters, reads, live, _ = lane
    db.cm_lane_snapshot.rows.append(snap("amd", [cand("AAA")]))
    live["AAA"] = live_row(verdict=enterable.BLOCKED, short=["room 3.2% (< 5%)"])
    out = CML.run_generic(brk, ON, ["amd"], now=NOW)
    assert enters == [] and out["entered"] is None
    assert _logs(db)[0]["reason"] == "live read blocked: room 3.2% (< 5%)"
    assert db.cm_lane_state.rows == []                 # a skip never spends the day


@pytest.mark.parametrize("row,why", [
    (None, "no live read (coverage none)"),
    ({"coverage": "pending"}, "no live read (coverage pending)"),
])
def test_an_unreadable_live_read_fails_closed(lane, row, why):
    db, brk, enters, reads, live, _ = lane
    db.cm_lane_snapshot.rows.append(snap("amd", [cand("AAA")]))
    if row is not None:
        live["AAA"] = row
    CML.run_generic(brk, ON, ["amd"], now=NOW)
    assert enters == [] and _logs(db)[0]["reason"] == why


def test_a_moved_band_is_skipped_for_plan_adapters(lane):
    db, brk, enters, reads, live, _ = lane
    db.cm_lane_snapshot.rows.append(snap("deep_demand", [cand("AAA", stop=8.5, buy=9.45)]))
    live["AAA"] = live_row(band=(9.00, 9.30))
    CML.run_generic(brk, ON, ["deep_demand"], now=NOW)
    assert enters == []
    assert _logs(db)[0]["reason"].startswith("band moved since the snapshot (9.37-9.59 -> 9.00-9.30)")
    # inside the tolerance it is the same band
    live["AAA"] = live_row(band=(9.37 + CML.BAND_MATCH_TOL / 2, 9.59))
    assert CML.confirm_live("deep_demand", cand("AAA"))["ok"] is True


def test_a_held_or_pending_name_is_not_bought_again(lane):
    db, brk, enters, reads, live, _ = lane
    brk._positions = [{"symbol": "AAA", "qty": "10", "avg_entry_price": "10",
                       "current_price": "10", "market_value": "100"}]
    db.cm_lane_snapshot.rows.append(snap("amd", [cand("AAA")]))
    live["AAA"] = live_row()
    CML.run_generic(brk, ON, ["amd"], now=NOW)
    assert enters == [] and reads == []


# ═════════════════════════════════════════════════════════════════════════════
# Snapshot freshness
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("kw,why", [
    ({"age": 601}, "stale snapshot (601s old)"),
    ({"day": "2026-09-25"}, "stale snapshot (built another day)"),
    ({"source_as_of": "2026-09-25T19:59:00Z"},
     "stale board (built 2026-09-25 15:59 ET, before the last close)"),
    ({"source_as_of": None}, "stale board (build time unknown)"),
])
def test_stale_snapshots_fail_closed(lane, kw, why):
    db, brk, enters, reads, live, _ = lane
    db.cm_lane_snapshot.rows.append(snap("amd", [cand("AAA")], **kw))
    live["AAA"] = live_row()
    out = CML.run_generic(brk, ON, ["amd"], now=NOW)
    assert enters == [] and reads == []
    assert out["sids"]["amd"]["reason"] == why
    assert _logs(db)[0]["reason"] == why and _logs(db)[0]["symbol"] == "*"


def test_no_snapshot_and_no_write_time(lane):
    assert CML.snapshot_stale(None, NOW) == "no snapshot"
    d = snap("amd", [])
    d["as_of"] = None
    assert CML.snapshot_stale(d, NOW) == "stale snapshot (write time unknown)"
    d["as_of"] = "2026-09-28T14:29:30"                  # naive ISO = UTC (Mongo)
    assert CML.snapshot_stale(d, NOW) is None


def test_a_friday_evening_build_trades_on_monday_morning(lane):
    mon = et(9, 35)
    doc = snap("amd", [], now=mon, source_as_of=et(21, 20, day=25).isoformat())
    assert CML.snapshot_stale(doc, mon) is None
    assert CML.prev_session_close(mon) == et(16, 0, day=25)
    # NEGATIVE: Friday 15:59 is before Friday's close -> stale on Monday
    doc["source_as_of"] = et(15, 59, day=25).isoformat()
    assert CML.snapshot_stale(doc, mon).startswith("stale board")


def test_the_tuesday_after_a_monday_holiday_reads_fridays_close(monkeypatch):
    """Real closed-day engine: 2026-09-07 is Labor Day."""
    tue = datetime(2026, 9, 8, 9, 35, tzinfo=ET)
    assert CML.prev_session_close(tue) == datetime(2026, 9, 4, 16, 0, tzinfo=ET)
    assert CML.prev_session_close(datetime(2026, 9, 8, 16, 5, tzinfo=ET)) == \
        datetime(2026, 9, 8, 16, 0, tzinfo=ET)


def test_epoch_of_reads_every_stamp_shape():
    assert CML._epoch_of(1790000000) == 1790000000.0
    assert CML._epoch_of(1790000000000) == 1790000000.0
    assert CML._epoch_of("2026-09-28T13:00:00Z") == \
        datetime(2026, 9, 28, 13, tzinfo=timezone.utc).timestamp()
    for bad in (None, "", "garbage", True, float("nan")):
        assert CML._epoch_of(bad) is None


# ═════════════════════════════════════════════════════════════════════════════
# One entry per tick, vetoes
# ═════════════════════════════════════════════════════════════════════════════
def test_two_generic_sids_enter_exactly_once_and_the_second_is_never_read(lane):
    db, brk, enters, reads, live, _ = lane
    db.cm_lane_snapshot.rows.append(snap("deep_demand", [cand("AAA", stop=9.2, buy=9.45)]))
    db.cm_lane_snapshot.rows.append(snap("amd", [cand("BBB")]))
    live["AAA"], live["BBB"] = live_row(px=9.5), live_row()
    out = CML.run_generic(brk, ON, ["deep_demand", "amd"], now=NOW)
    assert [e[0] for e in enters] == ["AAA"] and reads == ["AAA"]
    assert "amd" not in out["sids"]
    # the next call in the same minute stops at the clock, before any read
    out2 = CML.run_generic(brk, ON, ["amd"], now=NOW)
    assert reads == ["AAA"] and out2["sids"]["amd"]["reason"].startswith(
        "program-wait: one entry per minute (taken by deep_demand AAA")


def test_a_transient_veto_clears_the_attempt_and_stops(lane):
    db, brk, enters, reads, live, veto = lane
    db.cm_lane_snapshot.rows.append(snap("amd", [cand("AAA"), cand("BBB", rank=2)]))
    live["AAA"], live["BBB"] = live_row(), live_row()
    veto["raise"] = ValueError("program-wait: portfolio full: 15 positions + 0 pending entries / 15")
    out = CML.run_generic(brk, ON, ["amd"], now=NOW)
    assert db.cm_lane_state.rows == [] and reads == ["AAA"]
    assert out["sids"]["amd"]["reason"].startswith("program-wait: portfolio full")
    veto["raise"] = None
    assert CML.run_generic(brk, ON, ["amd"], now=NOW)["entered"]["symbol"] == "AAA"


def test_any_other_veto_keeps_the_attempt_and_tries_the_next(lane):
    db, brk, enters, reads, live, veto = lane
    db.cm_lane_snapshot.rows.append(snap("amd", [cand("AAA"), cand("BBB", rank=2)]))
    live["AAA"], live["BBB"] = live_row(), live_row()
    veto["raise"] = ValueError("earnings in 3d (2026-10-01)")
    CML.run_generic(brk, ON, ["amd"], now=NOW)
    st = {d["symbol"]: d for d in db.cm_lane_state.rows}
    assert st["AAA"]["result"] == "blocked" and st["BBB"]["result"] == "blocked"
    assert reads == ["AAA", "BBB"]
    veto["raise"] = None
    reads.clear()
    assert CML.run_generic(brk, ON, ["amd"], now=NOW)["entered"] is None and reads == []


def test_the_gate_off_disarmed_closed_late(lane):
    db, brk, enters, reads, live, _ = lane
    db.cm_lane_snapshot.rows.append(snap("amd", [cand("AAA")]))
    live["AAA"] = live_row()
    assert CML.run_generic(brk, {"cm_program": False, "armed": True}, ["amd"],
                           now=NOW)["sids"]["amd"]["reason"] == "off"
    assert CML.run_generic(brk, dict(ON, cm_lanes={"amd": False}), ["amd"],
                           now=NOW)["sids"]["amd"]["reason"] == "off"
    assert CML.run_generic(brk, {"cm_program": True}, ["amd"],
                           now=NOW)["sids"]["amd"]["reason"] == "disarmed"
    assert CML.run_generic(brk, ON, ["vcp"], now=NOW)["sids"]["vcp"]["reason"] == "off"
    brk._open = False
    assert CML.run_generic(brk, ON, ["amd"], now=NOW)["sids"]["amd"]["reason"] == "market closed"
    brk._open = True
    late = datetime.combine(NOW.date(), CML.LAST_ENTRY_ET, tzinfo=ET)
    assert CML.run_generic(brk, ON, ["amd"], now=late)["sids"]["amd"]["reason"] == \
        "after_last_entry_time"
    assert enters == [] and reads == []


def test_an_unreadable_state_or_broker_never_attempts(lane):
    db, brk, enters, reads, live, _ = lane
    db.cm_lane_snapshot.rows.append(snap("amd", [cand("AAA")]))
    live["AAA"] = live_row()
    brk.orders_raise = True
    out = CML.run_generic(brk, ON, ["amd"], now=NOW)
    assert out["sids"]["amd"]["reason"] == "broker unreadable" and enters == []
    brk.orders_raise = False
    db.cm_lane_state.raise_on["find_one"] = RuntimeError("mongo down")
    out = CML.run_generic(brk, ON, ["amd"], now=NOW)
    assert out["sids"]["amd"]["reason"] == "state unreadable" and enters == [] and reads == []


def test_max_confirms_per_sid(lane):
    db, brk, enters, reads, live, _ = lane
    cands = [cand("S%d" % i, rank=i) for i in range(6)]
    db.cm_lane_snapshot.rows.append(snap("amd", cands))
    for c in cands:
        live[c["symbol"]] = live_row(verdict=enterable.WATCH, short=["reclaim"])
    CML.run_generic(brk, ON, ["amd"], now=NOW)
    assert reads == ["S0", "S1", "S2"] and len(reads) == CML.MAX_CONFIRMS_PER_SID


# ═════════════════════════════════════════════════════════════════════════════
# The dispatcher
# ═════════════════════════════════════════════════════════════════════════════
def test_program_off_runs_the_fixed_order(lane, monkeypatch):
    db, brk, *_ = lane
    monkeypatch.setattr(EE, "_run_lanes_fixed_order", lambda: {"fixed": True})
    monkeypatch.setattr(CML, "_run_program_on", lambda *a: pytest.fail("program ran while OFF"))
    assert CML.run_program(brk, {"cm_program": False}) == {"fixed": True}
    assert CML.run_program(CapsBroker(mode="live"), {"cm_program": True}) == {"fixed": True}


@pytest.fixture
def slots(lane, monkeypatch):
    calls = []
    monkeypatch.setattr(CML, "_run_existing",
                        lambda l, b, c: calls.append(l) or {"lane": l})
    monkeypatch.setattr(PC, "priority_order",
                        lambda now=None: {"order": ["zones", "deep_demand", "hot_sectors",
                                                    "catalysts", "amd", "hot_pullback"]})
    return lane, calls


def test_the_dispatcher_follows_the_usage_order_and_one_generic_entry(slots, monkeypatch):
    (db, brk, enters, reads, live, _), calls = slots
    db.cm_lane_snapshot.rows.append(snap("deep_demand", [cand("AAA", stop=9.2, buy=9.45)]))
    db.cm_lane_snapshot.rows.append(snap("amd", [cand("BBB")]))
    live["AAA"], live["BBB"] = live_row(px=9.5), live_row()
    real = CML.run_generic
    gen = []
    monkeypatch.setattr(CML, "run_generic",
                        lambda b, c, s, now=None: gen.append(s[0]) or real(b, c, s, now=NOW))
    out = CML.run_program(brk, ON)
    assert calls == ["zone_edge_demand", "catalyst_entry", "hot_pullback_entry",
                     "zone_edge_supply", "zero_dte_lane", "options_lane"]
    assert gen == ["deep_demand"]                      # hot_sectors + amd: minute gone
    assert [e[0] for e in enters] == ["AAA"] and reads == ["AAA"]
    assert out["chart_maps_lanes"]["amd"]["reason"] == CML.MINUTE_GONE_TEXT
    assert [r["reason"] for r in _logs(db, "amd")] == [CML.MINUTE_GONE_TEXT]
    assert out["zone_edge_entry"] == {"lane": "zone_edge_demand"}
    assert out["hot_pullback"] == {"lane": "hot_pullback_entry"}
    assert out["program"]["order"][0] == "zones"


def test_a_slot_that_raises_never_stops_the_others(slots, monkeypatch):
    (db, brk, *_), calls = slots

    def boom(l, b, c):
        calls.append(l)
        if l == "zone_edge_demand":
            raise RuntimeError("zone read failed")
        return {}

    monkeypatch.setattr(CML, "_run_existing", boom)
    monkeypatch.setattr(CML, "run_generic",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("gen boom")))
    out = CML.run_program(brk, ON)
    assert calls[-1] == "options_lane" and "hot_pullback_entry" in calls
    assert "zone_edge_entry: zone read failed" in out["errors"]
    assert "deep_demand: gen boom" in out["errors"]


def test_slots_never_drop_an_existing_lane_and_options_run_last():
    s = CML._slots(["amd", "vcp", "nonsense", "breaking", "zones", "quick_bounce"])
    lanes = [x[0] for x in s]
    assert lanes[0] == "generic" and ("generic", "vcp") not in s
    assert lanes.count("zone_edge_demand") == 1 and lanes.count("zone_edge_supply") == 1
    assert lanes[-1] == "options_lane"
    for l in ("catalyst_entry", "hot_pullback_entry", "zero_dte_lane"):
        assert l in lanes


def test_run_program_never_raises(monkeypatch):
    monkeypatch.setattr(CML, "_mode", lambda b: (_ for _ in ()).throw(RuntimeError("x")))
    assert CML.run_program(CapsBroker(), ON) == {"errors": ["chart_maps_lanes: x"]}
