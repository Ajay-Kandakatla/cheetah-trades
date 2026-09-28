"""The existing lanes join the Chart Maps lane program (2026-09-27, §3.6).

zone-edge (zones / quick_bounce / breaking), catalysts, hot pullback, 0DTE and
the options lane keep their own rules and state, and now also:
  * run the shared cheap-skip (program_caps.check) before any state write — a
    capped / OFF / minute-taken lane writes no state, no race row, no ledger
    row, only a cm_lane_log reason the Trading page shows (critic 12);
  * treat a TRANSIENT program veto as "not an attempt" — the band is never
    burned for the day on a lost minute;
  * hot pullback passes the STANDING alert gate (room + proximity) on the
    live read, fail closed, and never buys a name another lane holds
    (critics 5 + 6);
  * 0DTE is NOT stopped at deploy (program OFF): only the program's `signals`
    switch stops its entries, and its open contracts are still managed
    (critic 8); both options lanes claim the minute before they submit;
  * options_zone risks min(1%, 0.25%) premium while the program is ON (critic 9).
Hermetic: every broker / Mongo / price read is a fake.
"""
import os
import sys
from datetime import date, datetime, time as dtime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.catalyst_entry as CE  # noqa: E402
import trading.exit_engine as EE  # noqa: E402
import trading.hot_pullback_entry as HPE  # noqa: E402
import trading.options_lane as OL  # noqa: E402
import trading.program_caps as PC  # noqa: E402
import trading.zero_dte_lane as ZD  # noqa: E402
import trading.zone_edge_entry as ZE  # noqa: E402
from tests.test_program_caps import CapsBroker, MiniDB, pos  # noqa: E402
from tests.test_zone_edge_entry import (  # noqa: E402
    NOW, break_row, demand_row, latest_doc, zone_doc)
from tests.test_zone_edge_entry import env as zone_env  # noqa: E402,F401  (fixture)
from tests.test_catalyst_entry import env as cat_env  # noqa: E402,F401  (fixture)
from tests.test_catalyst_entry import cand, happy, scan  # noqa: E402
from tests.test_zero_dte_lane import zenv  # noqa: E402,F401  (fixture)
from tests.test_options_lane import oenv  # noqa: E402,F401  (fixture)


@pytest.fixture(autouse=True)
def _frozen_usage(monkeypatch):
    import usage
    monkeypatch.setattr(usage, "feature_counts", lambda top=50: [])
    PC.set_tick_minute(None)
    yield
    PC.set_tick_minute(None)


def _log(db):
    return db.cm_lane_log.rows


def _prog(**extra):
    return dict(EE.get_config(), cm_program=True, **extra)


# ═════════════════════════════════════════════════════════════════════════════
# zone-edge
# ═════════════════════════════════════════════════════════════════════════════
def test_a_transient_veto_never_burns_the_band(zone_env):
    """NEGATIVE: the minute was lost inside entries.enter -> the attempt is
    cleared (retried next tick), no blocked race row, one log row."""
    veto = ValueError("program-wait: one entry per minute (taken by amd ZZZ at 10:30:00 ET)")
    _, db, enter_calls, _, _ = zone_env(latest=latest_doc(near_demand=[demand_row()]),
                                        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))},
                                        enter_raises=veto)
    out = ZE.run()
    assert len(enter_calls) == 1 and out["entered"] == []
    assert db.zone_edge_entry_state.rows == []
    assert [r for r in db.execution_race.rows if r.get("outcome") == "blocked"] == []
    assert [r for r in db.trade_ledger.rows if r.get("kind") == "zone_entry_blocked"] == []
    assert any("one entry per minute" in r["reason"] for r in _log(db))
    # a non-transient veto still burns it (unchanged behaviour)
    _, db2, _, _, _ = zone_env(latest=latest_doc(near_demand=[demand_row()]),
                               zones={"AAA": zone_doc("AAA", supply_los=(120.0,))},
                               enter_raises=ValueError("earnings in 3d (2026-10-01)"))
    ZE.run()
    assert db2.zone_edge_entry_state.rows[0]["result"] == "blocked"


def test_retried_next_tick_after_a_transient_veto(zone_env, monkeypatch):
    _, db, enter_calls, _, _ = zone_env(latest=latest_doc(near_demand=[demand_row()]),
                                        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    real = ZE.entries.enter
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("program-wait: portfolio full: 5 positions + 0 pending entries / 5 (p.312)")
        return real(*a, **k)

    monkeypatch.setattr(ZE.entries, "enter", flaky)
    assert ZE.run()["entered"] == []
    assert ZE.run()["entered"] == ["AAA"]


def test_critic_12_a_sid_switched_off_is_a_logged_cheap_skip(zone_env):
    """NEGATIVE: program ON with zones OFF -> no enter, no state, no race doc,
    but a cm_lane_log row saying why."""
    _, db, enter_calls, _, _ = zone_env(latest=latest_doc(near_demand=[demand_row()]),
                                        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    out = ZE.run(cfg=_prog(cm_lanes={"zones": False}))
    assert enter_calls == [] and db.zone_edge_entry_state.rows == []
    assert db.execution_race.rows == []
    rows = _log(db)
    assert len(rows) == 1 and rows[0]["reason"] == "program-cap: zones is OFF"
    assert rows[0]["sid"] == "zones" and rows[0]["symbol"] == "*"
    assert out["skipped"][0]["reason"] == "program-cap: zones is OFF"


def test_the_minute_taken_means_no_enter_and_no_state(zone_env):
    """NEGATIVE: someone already entered this minute -> zone_edge never calls
    entries.enter and writes no state."""
    _, db, enter_calls, _, _ = zone_env(latest=latest_doc(near_demand=[demand_row()],
                                                          breaking=[break_row()]),
                                        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    PC.set_tick_minute(NOW)
    assert PC.claim("amd", "ZZZ")[0] is True
    out = ZE.run()
    assert enter_calls == [] and db.zone_edge_entry_state.rows == []
    assert out["skipped"][0]["reason"].startswith("program-wait: one entry per minute")
    assert len(out["skipped"]) == 1                      # the loop stopped at the first


def test_sides_filter_and_reconcile_switch(zone_env, monkeypatch):
    _, db, enter_calls, _, _ = zone_env(latest=latest_doc(near_demand=[demand_row()],
                                                          breaking=[break_row()]),
                                        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    races = []
    monkeypatch.setattr(ZE, "reconcile_race", lambda now=None, broker=None: races.append(1) or {})
    out = ZE.run(sides=("supply",), reconcile=False)
    assert out["evaluated"] == 1 and [c["symbol"] for c in enter_calls] == ["BBB"]
    assert races == []
    ZE.run(sides=("demand",), reconcile=True)
    assert [c["symbol"] for c in enter_calls] == ["BBB", "AAA"] and races == [1]


def test_demand_before_breakout_by_usage_rank_only_while_on(zone_env):
    zones = {"AAA": zone_doc("AAA", supply_los=(120.0,))}
    _, _, enter_calls, _, _ = zone_env(latest=latest_doc(near_demand=[demand_row()],
                                                         breaking=[break_row()]), zones=zones)
    ZE.run(cfg=_prog())
    assert [c["symbol"] for c in enter_calls] == ["AAA", "BBB"]   # zones (#1) before breaking (#11)
    assert enter_calls[0]["reason"]["sid"] == "zones" and enter_calls[0]["reason"]["tab"] == "zones"
    assert enter_calls[1]["reason"]["sid"] == "breaking"
    assert enter_calls[0]["reason"]["kind"] == "demand"
    _, _, enter_calls2, _, _ = zone_env(latest=latest_doc(near_demand=[demand_row()],
                                                          breaking=[break_row()]), zones=zones)
    ZE.run()                                                        # program OFF: board order
    assert [c["symbol"] for c in enter_calls2] == ["BBB", "AAA"]


def test_the_open_cap_counts_pending_entries_in_the_lane_too(zone_env, monkeypatch):
    """NEGATIVE (a1): 4 positions + 1 pending buy -> no 5th entry, program OFF."""
    fake, db, enter_calls, _, _ = zone_env(latest=latest_doc(near_demand=[demand_row()]),
                                           positions=[pos("P%d" % i) for i in range(4)],
                                           zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    monkeypatch.setattr(fake, "open_orders",
                        lambda symbol=None: [{"id": "x", "symbol": "PEND", "side": "buy",
                                              "status": "new", "qty": "5", "limit_price": "10"}])
    out = ZE.run()
    assert enter_calls == [] and out["skipped"][0]["reason"].startswith(
        "program-wait: portfolio full: 4 positions + 1 pending entries / 5")


# ═════════════════════════════════════════════════════════════════════════════
# catalysts
# ═════════════════════════════════════════════════════════════════════════════
def test_catalyst_daily_cap_is_a_logged_cheap_skip(cat_env):
    br, docs = happy()
    _, db, enter_calls, _, _ = cat_env(payload=scan([cand()]), bounce=br, docs=docs)
    PC.record_entry("catalyst", "XYZ")                      # the catalysts sid bought today
    out = CE.run(cfg=_prog())
    assert enter_calls == [] and db.catalyst_entry_state.rows == []
    assert out["skipped"][-1]["reason"] == "program-cap: catalysts daily cap 1 reached"
    assert [(r["sid"], r["symbol"]) for r in _log(db)] == [("catalysts", "*")]


def test_catalyst_reason_carries_the_sid_and_a_transient_veto_is_cleared(cat_env):
    br, docs = happy()
    _, db, enter_calls, _, _ = cat_env(payload=scan([cand()]), bounce=br, docs=docs)
    assert CE.run()["entered"] == ["EOSE"]
    r = enter_calls[0]["reason"]
    assert (r["sid"], r["tab"], r["kind"]) == ("catalysts", "catalysts", "demand")
    br, docs = happy()
    _, db2, _, _, _ = cat_env(payload=scan([cand()]), bounce=br, docs=docs,
                              enter_raises=ValueError("program-wait: one entry per minute (x)"))
    out = CE.run()
    assert db2.catalyst_entry_state.rows == [] and out["entered"] == []
    assert [r for r in db2.trade_ledger.rows if r.get("kind") == "catalyst_entry_blocked"] == []


# ═════════════════════════════════════════════════════════════════════════════
# 0DTE (critic 8)
# ═════════════════════════════════════════════════════════════════════════════
def test_program_off_a_fresh_0dte_signal_still_submits(zenv):
    """critic 8: the deploy state (program OFF) does NOT stop 0DTE."""
    fake, db = zenv()
    out = ZD.run()
    assert len(fake.orders) == 1 and out["entered"] == ["SPY"]
    assert db.program_entries.rows[0]["sid"] == "signals"
    assert db.program_entries.rows[0]["occ"] == fake.orders[0]["symbol"]


def test_program_on_signals_off_manages_but_never_enters(zenv, monkeypatch):
    """NEGATIVE: program ON + signals OFF (the default) -> _manage still runs
    (its contracts keep their exits), no entry."""
    fake, db = zenv()
    managed = []
    real = ZD._manage
    monkeypatch.setattr(ZD, "_manage", lambda *a, **k: managed.append(1) or real(*a, **k))
    out = ZD.run(cfg=_prog())
    assert managed == [1] and fake.orders == []
    assert out["entry_reason"] == "program: signals OFF"
    assert _log(db)[0]["reason"] == "program-cap: signals is OFF"


def test_a_refused_0dte_claim_never_submits(zenv):
    """NEGATIVE: the minute is gone -> no submit, no attempt recorded (retried)."""
    fake, db = zenv()
    PC.set_tick_minute(datetime.now().astimezone())
    PC.claim("amd", "ZZZ")
    out = ZD.run()
    assert fake.orders == [] and db.zero_dte_lane_state.rows == []
    assert out["skipped"][0]["reason"].startswith("program-wait: one entry per minute")


def test_a_day_capped_0dte_records_a_skipped_attempt(zenv):
    fake, db = zenv()
    PC.record_entry("zero_dte", "QQQ", asset="option", occ="QQQX")
    ZD.run(cfg=_prog(cm_lanes={"signals": True}))
    assert fake.orders == []
    att = db.zero_dte_lane_state.rows
    assert len(att) == 1 and att[0]["result"] == "skipped"
    assert att[0]["reason"] == "program-cap: signals daily cap 1 reached"


# ═════════════════════════════════════════════════════════════════════════════
# options lane (critic 9)
# ═════════════════════════════════════════════════════════════════════════════
def test_a_refused_options_claim_never_submits(oenv):
    fake, db, _ = oenv()
    PC.set_tick_minute(datetime.now().astimezone())
    assert PC.claim("amd", "ZZZ")[0] is True
    out = OL.run()
    assert fake.orders == []
    assert out["skipped"][-1]["reason"].startswith("program-wait: one entry per minute")
    assert db.options_lane_state.rows == []


def test_options_sizing_is_quarter_percent_only_while_on(oenv):
    oenv()
    assert OL.run(cfg=_prog())["risk_pct"] == 0.25
    oenv()
    assert OL.run()["risk_pct"] == 1.0
    assert OL.size_contracts(2.0, 88_935.0, 0.25)[1] == pytest.approx(222.34, abs=0.01)
    assert OL.size_contracts(2.0, 88_935.0)[1] == pytest.approx(889.35, abs=0.01)
    assert OL.RISK_PCT_OF_EQUITY == 1.0                       # the constant is untouched


def test_options_zone_counts_in_the_open_cap_but_has_no_strategy_caps():
    db = MiniDB()
    import trading.exit_engine as E
    orig = E._db
    E._db = lambda: db
    try:
        PC.record_entry("options_zone", "AAA", asset="option", occ="AAA261120C00100000")
        brk = CapsBroker([pos("S%d" % i) for i in range(15)])
        r = PC.check("options_zone", "BBB261120C00100000", brk=brk, cfg={"cm_program": True},
                     mode="paper", asset="option")
        assert any("portfolio full" in x for x in r)
        assert not any("daily cap" in x or "open (max" in x for x in r)
    finally:
        E._db = orig


# ═════════════════════════════════════════════════════════════════════════════
# hot pullback (critics 5 + 6)
# ═════════════════════════════════════════════════════════════════════════════
class HPBroker(CapsBroker):
    def __init__(self, *a, last=None, **k):
        super().__init__(*a, **k)
        self.closed = []
        self._last = last or {}

    def last_price(self, sym):
        return self._last.get(sym)

    def close_position(self, sym):
        self.closed.append(sym)
        return {}


@pytest.fixture
def hp(monkeypatch):
    def build(gates=None, coverage="store", positions=(), open_docs=(), cfg_extra=None,
              reason_short=None, last=None):
        db = MiniDB(cfg={"armed": True, "consecutive_losses": 0, "equity_cap": 100_000.0,
                         "progressive_exposure": False})
        for d in open_docs:
            db.hot_pullback_positions.rows.append(dict(d))
        monkeypatch.setattr(EE, "_db", lambda: db)
        monkeypatch.setattr(HPE, "_coll", lambda name: getattr(db, name))
        monkeypatch.setattr(HPE, "_sessions_between_factory", lambda: (lambda a, b: 1))
        from market_hours import gate
        monkeypatch.setattr(gate, "closed_reason", lambda now=None: None)
        from supply_demand import hot_pullback as HP
        today = date(2026, 9, 28)
        row = {"symbol": "DYN", "date": "2026-09-25", "close": 20.31, "low": 17.0,
               "plan": {"target": 25.58}, "band": {"lo": 16.56, "hi": 17.02},
               "flush_pct": -35.8, "under_ma21_pct": -20.6,
               "reversal": {"off_low_pct": 19.5}}
        monkeypatch.setattr(HP, "last_closed_signals", lambda before=None: ("2026-09-25", [row]))
        from sepa import prices
        monkeypatch.setattr(prices, "bulk_snapshot",
                            lambda syms: {s: {"open": 20.0, "close": (last or {}).get(s, 20.0)}
                                          for s in syms})
        from supply_demand import bounce_room
        g = {"room_ok": True, "prox_ok": True} if gates is None else gates
        monkeypatch.setattr(bounce_room, "api_payload",
                            lambda syms, background=True: {"rows": {s: {
                                "coverage": coverage,
                                "enterable": {"gates": g, "reason_short": reason_short or []}}
                                for s in syms}})
        enters = []
        from trading import entries as TE
        monkeypatch.setattr(TE, "enter", lambda sym, **k: enters.append((sym, k)) or
                            {"order_id": "o-%s" % sym})
        brk = HPBroker(positions, last=last)
        cfg = dict(EE.get_config(), **(cfg_extra or {}))
        now = datetime.combine(today, dtime(9, 35)).replace(tzinfo=HPE.ET)
        return brk, db, enters, cfg, now

    return build


def _skips(db):
    return [r for r in db.trade_ledger.rows if r.get("kind") == "hot_pullback_skip"]


def test_hot_pullback_passes_the_standing_alert_gate(hp):
    brk, db, enters, cfg, now = hp()
    out = HPE.run(broker=brk, cfg=cfg, now=now)
    assert [e[0] for e in enters] == ["DYN"]
    reason = enters[0][1]["reason"]
    assert reason["gate"] == {"room_ok": True, "prox_ok": True}
    assert (reason["sid"], reason["tab"], reason["kind"]) == ("hot_pullback", "hot_pullback", "demand")
    assert out["entered"][0]["symbol"] == "DYN"


@pytest.mark.parametrize("gates,coverage,short", [
    ({"room_ok": False, "prox_ok": True}, "store", ["room 3.2% (< 5%)"]),
    ({"room_ok": True, "prox_ok": False}, "store", ["4.1% above demand"]),
    ({"room_ok": True, "prox_ok": True}, "pending", []),       # unreadable -> fail closed
    ({"room_ok": None, "prox_ok": True}, "ondemand", []),
])
def test_hot_pullback_alert_gate_refusals(hp, gates, coverage, short):
    """NEGATIVES (critic 6): room fails / proximity fails / no coverage ->
    no enter, no hot_pullback_skip ledger row, one cm_lane_log row."""
    brk, db, enters, cfg, now = hp(gates=gates, coverage=coverage, reason_short=short)
    out = HPE.run(broker=brk, cfg=cfg, now=now)
    assert enters == [] and _skips(db) == []
    rows = _log(db)
    assert len(rows) == 1 and rows[0]["reason"].startswith("alert gate:")
    assert rows[0]["sid"] == "hot_pullback" and rows[0]["symbol"] == "DYN"
    assert out["skipped"][0]["why"].startswith("alert gate:")
    # a second tick in the window adds no ledger row either (it would repeat every minute)
    HPE.run(broker=brk, cfg=cfg, now=now + timedelta(minutes=1))
    assert _skips(db) == [] and _log(db)[0]["count"] == 2


def test_hot_pullback_never_buys_a_name_another_lane_holds(hp):
    """critic 5: EMR held by another lane (broker position, not in
    hot_pullback_positions) -> no order; its exit loop never touches EMR."""
    brk, db, enters, cfg, now = hp(positions=[pos("DYN"), pos("EMR")])
    out = HPE.run(broker=brk, cfg=cfg, now=now)
    assert enters == []
    assert out["skipped"][0]["why"] == "program-cap: DYN already held (one lane per name)"
    assert brk.closed == []


def test_hot_pullback_off_via_the_program_still_closes_its_positions(hp):
    """NEGATIVE: program ON + hot_pullback OFF stops ENTRIES only — an open
    position whose stop is hit is still closed."""
    open_doc = {"_id": "p1", "symbol": "OLD", "status": "open", "entry_date": "2026-09-24",
                "stop": 10.0, "target": 15.0}
    brk, db, enters, cfg, now = hp(open_docs=[open_doc], last={"OLD": 9.5},
                                   cfg_extra={"cm_program": True,
                                              "cm_lanes": {"hot_pullback": False}})
    out = HPE.run(broker=brk, cfg=cfg, now=now)
    assert brk.closed == ["OLD"] and out["closed"][0]["symbol"] == "OLD"
    assert enters == []
    assert _log(db)[0]["reason"] == "program-cap: hot_pullback is OFF"


def test_hot_pullback_transient_veto_writes_no_skip_row(hp, monkeypatch):
    brk, db, enters, cfg, now = hp()
    from trading import entries as TE

    def veto(sym, **k):
        raise ValueError("program-wait: one entry per minute (taken by amd X at 09:35:01 ET)")

    monkeypatch.setattr(TE, "enter", veto)
    HPE.run(broker=brk, cfg=cfg, now=now)
    assert _skips(db) == [] and "one entry per minute" in _log(db)[0]["reason"]
