"""🚩 Gajjala lane v2 — the critic's defects, each with the test that would have caught it (2026-10-21).

MED: the breakeven add refilled the drawdown half-off (add = full − held); the part-sell cancelled and sold in the same
tick, which Alpaca refuses while the cancel is pending (the stop flickered on and off, the half-off never ran); a
halved risk_mult can lock the lane and the size skip did not say so (the rule itself is HIS CALL #18).
LOW: four unpinned guards (_protect's shortfall stop, the armed-only management, the per-bucket bar cache, the trail's
strict `<`); the three MINE numbers without a HIS CALL number; POST {"gajjala_floors": null} stored True; a disarmed
tick wrote a real drawdown_on row; the breakeven wording.

UNMEASURED — no edge, no win rate. Hermetic: fake broker + fake Mongo, no network.
"""
import asyncio
import json
import os
import sys
from datetime import timedelta, timezone
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.exit_engine as EE
import trading.gajjala_entry as GL
from trading.broker_alpaca import OPEN_STATUSES
from tests.test_gajjala_lane import _at, _brackets, _rows, DAY, PLAN, SAIQ_ID
from tests.test_gajjala_lane_gg_rules import BELOW, MBroker, calls, frame, gg, stop_leg, v2_open  # noqa: F401
from tests.test_trading_engine import _position

UTC = timezone.utc
SRC = os.path.join(os.path.dirname(__file__), "..", "trading", "gajjala_entry.py")
DOC = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "trading_gajjala_lane.md")


# ── MED: the part-sell over two ticks on a broker with Alpaca's pending-cancel semantics ────────────────────────────
class PendingCancelBroker(MBroker):
    """Alpaca's semantics: a cancel leaves the stop `pending_cancel` (its shares still held) until settle(); a sell or a
    new stop for more than the free shares is refused 'insufficient qty available'; a sell reduces the position."""

    def _free(self, symbol):
        pos = next((p for p in self._positions if p["symbol"] == symbol), None)
        held = int(float(pos["qty"])) if pos else 0
        busy = sum(int(float(o.get("qty") or 0)) for o in self._orders
                   if o.get("symbol") == symbol and o.get("side") == "sell"
                   and (o.get("status") in OPEN_STATUSES or o.get("status") == "pending_cancel"))
        return pos, held - busy

    def cancel_order(self, order_id):
        self.calls.append(("cancel_order", {"order_id": order_id}))
        for o in self._orders:
            if o.get("id") == order_id:
                o["status"] = "pending_cancel"

    def settle(self):
        self._orders = [o for o in self._orders if o.get("status") != "pending_cancel"]

    def close_position(self, symbol, qty=None):
        self.calls.append(("close_position", {"symbol": symbol, "qty": qty}))
        pos, free = self._free(symbol)
        if qty is None or qty > free:
            raise EE.BrokerError("HTTP 403 insufficient qty available for order (requested: %s, available: %s)"
                                 % (qty, free))
        pos["qty"] = str(int(float(pos["qty"])) - int(qty))
        return {}

    def submit_stop(self, symbol, qty, stop_price, client_order_id=None):
        self.calls.append(("submit_stop", {"symbol": symbol, "qty": qty, "stop_price": stop_price}))
        _pos, free = self._free(symbol)
        if qty > free:
            raise EE.BrokerError("HTTP 403 insufficient qty available")
        oid = "stop-new-%d" % len(self.calls)
        self._orders.append(dict(stop_leg(stop_price, qty, oid)))
        return {"id": oid}

    def working_stop_qty(self, symbol="SAIQ"):
        return sum(int(float(o["qty"])) for o in self._orders if o.get("symbol") == symbol and o.get("status") == "new")


def _pending_gg(gg, **kw):
    s = gg(**kw)
    brk = PendingCancelBroker(kw.get("positions", ()), kw.get("orders", ()), (), kw.get("equity", 100_000.0), None,
                              True, "paper")
    for mod in (EE, GL, sys.modules["trading.entries"]):
        setattr(mod, "broker", brk)                         # the gg fixture's monkeypatch restores them at teardown
    s.brk = brk
    s.run = lambda at=None: GL.run(broker=brk, cfg=EE.get_config(), now=at or s.now)
    return s


def test_half_off_waits_for_the_pending_cancel_then_sells_and_restops(gg):
    """The critic's probe: ticks 11:11–11:16 used to read half_off 0 every tick with the stop 0 / 735 / 0 / 735 and
    'insufficient qty available'. Now: cancel → wait (no stop resubmitted while pending) → sell 367 + stop 368."""
    s = _pending_gg(gg, docs=[v2_open()], positions=[_position("SAIQ", 735, 4.49, 4.50)], orders=[stop_leg()],
                    equity=89_000.0, state={"equity_peak": 100_000.0, "in_drawdown": False, "risk_mult": 1.0})
    out = s.run(at=_at(DAY, 11, 11))
    assert out["half_off"] == 0 and calls(s.brk, "cancel_order") == [{"order_id": "stop-1"}]
    assert calls(s.brk, "close_position") == [] and calls(s.brk, "submit_stop") == []
    assert s.coll.get(SAIQ_ID)["dd_half_state"] == "cancelling" and s.coll.get(SAIQ_ID)["dd_half_want"] == 367
    out = s.run(at=_at(DAY, 11, 12))                                    # the cancel is still pending at the broker
    assert out["half_off"] == 0 and calls(s.brk, "close_position") == []
    assert calls(s.brk, "submit_stop") == []                            # NEG: never resubmit while a cancel is pending
    assert len(calls(s.brk, "cancel_order")) == 1                       # NEG: no repeat cancel of a pending order
    s.brk.settle()
    out = s.run(at=_at(DAY, 11, 13))
    assert out["half_off"] == 1
    assert calls(s.brk, "close_position") == [{"symbol": "SAIQ", "qty": 367}]
    assert calls(s.brk, "submit_stop") == [{"symbol": "SAIQ", "qty": 368, "stop_price": 4.31}]
    d = s.coll.get(SAIQ_ID)
    assert d["dd_half_state"] == "done" and d["dd_half_qty"] == 367 and d["dd_half_naked_ms"] == 120_000
    assert s.brk.working_stop_qty() == 368 == int(float(s.brk._positions[0]["qty"]))
    out = s.run(at=_at(DAY, 11, 14))
    assert out["half_off"] == 0 and len(calls(s.brk, "close_position")) == 1 and len(calls(s.brk, "submit_stop")) == 1
    assert s.brk.working_stop_qty() == 368                              # covered, no duplicate stop
    assert not [e for e in out["errors"] if "insufficient" in e]


def test_partial_cancel_failure_frees_the_claim_and_keeps_the_stop(gg, monkeypatch):
    """NEG: a cancel the broker refuses leaves every share under its stop — no sell, the claim is freed."""
    s = _pending_gg(gg, docs=[v2_open()], positions=[_position("SAIQ", 735, 4.49, 4.50)], orders=[stop_leg()],
                    equity=89_000.0, state={"equity_peak": 100_000.0, "in_drawdown": False, "risk_mult": 1.0})

    def refuse(order_id):
        raise EE.BrokerError("HTTP 422 order not cancelable")
    monkeypatch.setattr(s.brk, "cancel_order", refuse)
    out = s.run(at=_at(DAY, 11, 11))
    d = s.coll.get(SAIQ_ID)
    assert d["dd_half_state"] is None and "not cancelable" in d["dd_half_error"]
    assert calls(s.brk, "close_position") == [] and s.brk.working_stop_qty() == 735
    assert any(e.startswith("dd_half SAIQ") for e in out["errors"])


# ── MED: the breakeven add is the planned half, never a refill ──────────────────────────────────────────────────────
def test_breakeven_add_never_refills_the_drawdown_half_off(gg):
    """The critic's probe: fill 735, full 1470, dd_half done, 367 held → the old add bought 1103 (back to FULL)."""
    f = frame(BELOW + [(11, 10, 4.60, 4.45)])
    s = gg(docs=[v2_open(dd_half_state="done", dd_half_qty=368)], positions=[_position("SAIQ", 367, 4.49, 4.60)],
           orders=[stop_leg(qty=367)], frame=f)
    out = s.run()
    d = s.coll.get(SAIQ_ID)
    assert out["breakeven"] == 1 and out["added"] == 0 and _brackets(s.brk) == []
    assert d["add_refused"].startswith("drawdown — half came off") and d["add_qty"] == 735 != 1103


def test_breakeven_add_is_capped_at_the_planned_half(gg):
    """Shares sold since the fill (held 600 < fill 735): the add is full − the first fill (735), not full − held (870)."""
    f = frame(BELOW + [(11, 10, 4.60, 4.45)])
    s = gg(docs=[v2_open()], positions=[_position("SAIQ", 600, 4.49, 4.60)], orders=[stop_leg(qty=600)], frame=f)
    s.run()
    (add,) = _brackets(s.brk)
    assert add["qty"] == 735 and s.coll.get(SAIQ_ID)["add_qty"] == 735
    s2 = gg(docs=[v2_open()], positions=[_position("SAIQ", 735, 4.49, 4.60)], orders=[stop_leg()], frame=f)
    s2.run()
    assert [b["qty"] for b in _brackets(s2.brk)] == [735]               # NEG: the normal case unchanged
    s3 = gg(docs=[v2_open(dd_half_due=True)], positions=[_position("SAIQ", 1, 4.49, 4.60)], orders=[stop_leg(qty=1)],
            frame=f)
    s3.run()
    assert _brackets(s3.brk) == [] and s3.coll.get(SAIQ_ID)["add_refused"].startswith("drawdown")   # due = no add


# ── MED: the risk_mult lock is named in the size skip (the rule is HIS CALL #18) ───────────────────────────────────
def test_size_skip_names_risk_mult_once_it_has_locked_the_lane():
    m = 1.0
    for _ in range(11):
        m = GL.risk_after(m, -0.01)                                     # a breakeven stop a cent under the fill
    p = GL.entry_plan(PLAN, 4.48, 100_000, 100_000, risk_mult=m)
    assert p["skip_kind"] == "size"
    assert p["why"].startswith("0 shares fit the risk, the notional cap and the cash — risk_mult is ")
    assert ("risk_mult is %g after losing lane trades" % m) in p["why"] and "only a win resets it (HIS CALL #18)" in p["why"]
    cashless = GL.entry_plan(PLAN, 4.48, 100_000, 1.0)                 # NEG: risk_mult 1 — the cash binds, not risk_mult
    assert cashless["why"] == "0 shares fit the risk, the notional cap and the cash"


# ── LOW: four guards that no test pinned ───────────────────────────────────────────────────────────────────────────
def test_protect_restops_a_shortfall_and_leaves_a_covered_position(gg):
    s = gg(docs=[v2_open()], positions=[_position("SAIQ", 735, 4.49, 4.50)], orders=[stop_leg(qty=400)], frame=None)
    out = s.run()
    assert out["protected"] == 1 and calls(s.brk, "submit_stop") == [{"symbol": "SAIQ", "qty": 335, "stop_price": 4.31}]
    s2 = gg(docs=[v2_open()], positions=[_position("SAIQ", 735, 4.49, 4.50)], orders=[stop_leg()], frame=None)
    assert s2.run()["protected"] == 0 and calls(s2.brk, "submit_stop") == []     # NEG: covered


def test_disarmed_management_makes_zero_broker_calls(gg):
    """A breakeven-ready bar, a stop shortfall and the drawdown turn — disarmed, the lane sends NOTHING."""
    f = frame(BELOW + [(11, 10, 4.60, 4.45)])
    kw = dict(docs=[v2_open()], positions=[_position("SAIQ", 735, 4.49, 4.60)], orders=[stop_leg(qty=400)], frame=f,
              equity=89_000.0, state={"equity_peak": 100_000.0, "in_drawdown": False, "risk_mult": 1.0})
    s = gg(armed=False, **kw)
    s.run()
    assert s.brk.calls == [] and s.coll.get(SAIQ_ID)["be_state"] is None
    (row,) = _rows(s.db, "gajjala_partial")
    assert row["detail"]["kind"] == "drawdown_on" and row["dry_run"] is True      # no REAL ledger row disarmed
    s2 = gg(armed=True, **kw)
    s2.run()
    assert s2.brk.calls != []                                           # NEG: armed, the same tick acts
    assert _rows(s2.db, "gajjala_partial")[0]["dry_run"] is False


def test_bar_cache_rereads_on_a_new_bucket(monkeypatch):
    from chart_maps.gajjala import bars as GB
    loads = []

    def frames_for(symbols, session, now, **kw):
        loads.append((tuple(symbols), now))
        return {symbols[0]: SimpleNamespace(f5="f5-%d" % len(loads))}
    monkeypatch.setattr(GB, "frames_for", frames_for)
    GL._BAR_CACHE.clear()
    try:
        a = GL._bars5("SAIQ", DAY, _at(DAY, 11, 12))
        b = GL._bars5("SAIQ", DAY, _at(DAY, 11, 13))                     # same 5-minute bucket
        assert a == b == "f5-1" and len(loads) == 1                     # NEG: no re-read inside a bucket
        c = GL._bars5("SAIQ", DAY, _at(DAY, 11, 17))                     # the 11:15 bar has closed — a new bucket
        assert c == "f5-2" and len(loads) == 2
        GL._bars5("MMA", DAY, _at(DAY, 11, 17))
        assert len(loads) == 3                                          # per symbol
    finally:
        GL._BAR_CACHE.clear()


def test_trail_NEG_a_close_equal_to_the_ema_does_not_exit(gg):
    from tests.test_gajjala_lane_gg_rules import _after_be, _be_orders
    f = frame(BELOW + [(11, 10, 4.60, 4.45), (11, 15, 4.58, 4.58)])
    s = gg(docs=[_after_be()], positions=[_position("SAIQ", 1470, 4.545, 4.58)], orders=_be_orders(), frame=f,
           now=_at(DAY, 11, 16))
    assert s.run()["trailed"] == 0 and calls(s.brk, "close_position") == []
    f2 = frame(BELOW + [(11, 10, 4.60, 4.45), (11, 15, 4.57, 4.58)])
    s2 = gg(docs=[_after_be()], positions=[_position("SAIQ", 1470, 4.545, 4.57)], orders=_be_orders(), frame=f2,
            now=_at(DAY, 11, 16))
    assert s2.run()["trailed"] == 1                                     # a cent under = out


# ── LOW: numbering, the null config, the wording ───────────────────────────────────────────────────────────────────
def test_the_three_mine_numbers_carry_his_call_numbers():
    with open(SRC, encoding="utf-8") as fh:
        src = fh.read().splitlines()
    with open(DOC, encoding="utf-8") as fh:
        doc = fh.read()
    for name, n in (("GAJJALA_FILL_WAIT_SEC", 20), ("GAJJALA_MAX_ROUND_R_PCT", 21),
                    ("GAJJALA_ENTRY_CUTOFF_BEFORE_CLOSE_MIN", 22)):
        line = next(x for x in src if x.startswith(name + " = "))
        assert ("MINE — HIS CALL #%d" % n) in line, line
        assert ("- **#%d** `%s`" % (n, name)) in doc
    assert "never add a lane without his call" in doc                   # the contracts anchor is back


def test_api_null_floors_is_the_code_default_off(monkeypatch):
    pytest.importorskip("fastapi")
    from trading import api as TA
    from tests.test_trading_engine import FakeDB
    import auth
    db = FakeDB(armed=True)
    monkeypatch.setattr(EE, "_db", lambda: db)
    admin = auth.HOUSE_OWNER_EMAIL
    asyncio.run(TA.trading_config({"gajjala_floors": True}, email=admin))
    assert EE.get_config()["gajjala_floors"] is True
    resp = asyncio.run(TA.trading_config({"gajjala_floors": None}, email=admin))
    assert json.loads(resp.body) == {"gajjala_floors": None} and EE.get_config()["gajjala_floors"] is False
    asyncio.run(TA.trading_config({"gajjala_entry": False}, email=admin))
    asyncio.run(TA.trading_config({"gajjala_entry": None}, email=admin))
    assert EE.get_config()["gajjala_entry"] is True                     # NEG: the lane's null is still ON


def test_manage_text_says_one_close_above_the_entry():
    t = GL.rules_block()["manage_text"]
    assert t.startswith("no target — after the first closed bar, %d or more bars after the entry bar, that closes "
                        "above the entry, the stop moves to breakeven" % GL.GG_BE_AFTER_BARS)
    with open(SRC, encoding="utf-8") as fh:
        head = fh.read().split('"""', 2)[1]
    assert "zero risk on the whole" not in head                         # NEG: the add risks its own fill − the first
    rows = [{"t": _at(DAY, 11, 10).astimezone(UTC), "close": 4.50}]
    assert GL.be_bar(rows, _at(DAY, 10, 53), 4.49, 5) is rows[0]        # one close above, 3 bars on = breakeven
    rows = [{"t": _at(DAY, 11, 5).astimezone(UTC) + timedelta(0), "close": 4.50}]
    assert GL.be_bar(rows, _at(DAY, 10, 53), 4.49, 5) is None           # NEG: 2 bars on


# ── the verifier's defects (2026-10-21, round 2) ───────────────────────────────────────────────────────────────────
def _dd_pending(gg):
    return _pending_gg(gg, docs=[v2_open()], positions=[_position("SAIQ", 735, 4.49, 4.50)], orders=[stop_leg()],
                       equity=89_000.0, state={"equity_peak": 100_000.0, "in_drawdown": False, "risk_mult": 1.0})


def _tick(s, hh, mm):
    s.now = _at(DAY, hh, mm)
    return EE.tick(force=True)


def test_ee_tick_never_adopts_a_lane_name_mid_part_sell(gg):
    """HIGH: the lane runs as step (n) INSIDE EE.tick, after adopt-and-protect. Tick N cancels the stop; at tick N+1
    adopt-and-protect used to place a house stop (735 @ risk_rules.initial_stop) before the lane sold — the lane then
    cancelled it, every tick, and the half-off never ran. Now the name is skipped while the doc is 'cancelling'."""
    s = _dd_pending(gg)
    out = _tick(s, 11, 11)
    assert out["adopted"] == 0 and s.coll.get(SAIQ_ID)["dd_half_state"] == "cancelling"
    assert GL.part_sell_symbols() == {"SAIQ"} and EE._gajjala_part_sell_symbols() == {"SAIQ"}
    s.brk.settle()
    out = _tick(s, 11, 12)
    assert out["adopted"] == 0 and out["gajjala_part_sell_skipped"] == 1          # NEG: no house stop first
    assert out["gajjala_lane"]["half_off"] == 1
    assert calls(s.brk, "close_position") == [{"symbol": "SAIQ", "qty": 367}]
    assert calls(s.brk, "submit_stop") == [{"symbol": "SAIQ", "qty": 368, "stop_price": 4.31}]   # the lane's stop only
    assert not _rows(s.db, "adopt_protect")
    assert s.coll.get(SAIQ_ID)["dd_half_state"] == "done" and GL.part_sell_symbols() == set()
    out = _tick(s, 11, 13)
    assert out["adopted"] == 0 and "gajjala_part_sell_skipped" not in out           # covered: nothing to skip
    assert s.brk.working_stop_qty() == 368 == int(float(s.brk._positions[0]["qty"]))


def test_ee_tick_NEG_still_adopts_a_lane_name_that_is_not_mid_part_sell(gg):
    """NEG: a lane name with no stop and no part-sell in flight is still adopted (a stop must always be resting)."""
    s = _pending_gg(gg, docs=[v2_open()], positions=[_position("SAIQ", 735, 4.49, 4.50)], orders=[])
    out = _tick(s, 11, 11)
    assert out["adopted"] == 1 and "gajjala_part_sell_skipped" not in out
    assert GL.part_sell_symbols() == set()
    s2 = _pending_gg(gg, docs=[v2_open(dd_half_state="done"), dict(v2_open(), _id="x", dd_half_state="cancelling",
                                                                    state="closed")],
                     positions=[_position("SAIQ", 735, 4.49, 4.50)], orders=[])
    assert GL.part_sell_symbols() == set()                              # NEG: done / not open = not mid part-sell


def test_disarmed_mid_part_sell_restops_every_share_and_nothing_else(gg):
    """MED (HIS CALL #23): disarmed between the cancel (tick N) and the sell (tick N+1) → ONE protective SELL stop at the
    doc's stop for every unprotected share, a `gajjala_restop_disarmed` row; no buy, no sell at market. Armed again →
    the part-sell completes (the restop is cancelled, then the sell + the stop for the rest)."""
    s = _dd_pending(gg)
    _tick(s, 11, 11)
    assert s.coll.get(SAIQ_ID)["dd_half_state"] == "cancelling"
    s.brk.settle()
    s.db.trading_config.rows[0]["armed"] = False
    n0 = len(s.brk.calls)
    out = _tick(s, 11, 12)
    assert out["armed"] is False and out["gajjala_lane"]["restopped"] == 1
    assert s.brk.calls[n0:] == [("submit_stop", {"symbol": "SAIQ", "qty": 735, "stop_price": 4.31})]
    (row,) = _rows(s.db, "gajjala_restop_disarmed")
    assert row["dry_run"] is False and row["detail"]["qty"] == 735 and row["detail"]["kind"] == "dd_half"
    assert row["detail"]["stop_px"] == 4.31 and row["detail"]["strategy"] == "gajjala"
    assert s.brk.working_stop_qty() == 735 and s.coll.get(SAIQ_ID)["dd_half_state"] == "cancelling"
    for hh, mm in ((11, 13), (13, 0), (15, 56)):
        out = _tick(s, hh, mm)
        assert out["gajjala_lane"]["restopped"] == 0                     # covered: ONE stop, never a second
    # NEG: a disarmed tick never buys or sells at market — the one protective sell stop is the only broker call
    assert s.brk.calls[n0:] == [("submit_stop", {"symbol": "SAIQ", "qty": 735, "stop_price": 4.31})]
    assert calls(s.brk, "close_position") == [] and _brackets(s.brk) == []
    assert int(float(s.brk._positions[0]["qty"])) == 735 and s.coll.get(SAIQ_ID)["dd_half_state"] == "cancelling"
    # armed again: the part-sell completes over the next ticks
    s.db.trading_config.rows[0]["armed"] = True
    out = s.run(at=_at(DAY, 11, 20))
    assert out["half_off"] == 0 and calls(s.brk, "close_position") == []      # the restop's cancel is sent first
    s.brk.settle()
    out = s.run(at=_at(DAY, 11, 21))
    assert out["half_off"] == 1 and calls(s.brk, "close_position") == [{"symbol": "SAIQ", "qty": 367}]
    assert s.brk.working_stop_qty() == 368 == int(float(s.brk._positions[0]["qty"]))
    assert s.coll.get(SAIQ_ID)["dd_half_state"] == "done"


def test_disarmed_restop_NEG_waits_while_the_cancel_is_pending_and_never_without_a_part_sell(gg):
    """NEG: the cancel still pending at the broker (its shares held) → no restop; a disarmed doc that is NOT mid
    part-sell with a stop shortfall → no restop (the disarmed invariant stands outside HIS CALL #23)."""
    s = _dd_pending(gg)
    s.run(at=_at(DAY, 11, 11))
    s.db.trading_config.rows[0]["armed"] = False
    n0 = len(s.brk.calls)
    out = s.run(at=_at(DAY, 11, 12))                                    # not settled: stop-1 still pending_cancel
    assert out["restopped"] == 0 and s.brk.calls[n0:] == [] and not _rows(s.db, "gajjala_restop_disarmed")
    s2 = _pending_gg(gg, docs=[v2_open()], positions=[_position("SAIQ", 735, 4.49, 4.50)], orders=[stop_leg(qty=400)],
                     armed=False)
    out = s2.run()
    assert out["restopped"] == 0 and s2.brk.calls == []
    with pytest.raises(ValueError, match="engine not armed"):
        EE.lane_stop("SAIQ", 1, 4.31)                                   # NEG: only the protective flag passes disarmed


def test_size_skip_NEG_no_risk_mult_note_when_the_cash_or_the_notional_cap_binds():
    """LOW: the risk_mult note only when the risk cap itself is 0 shares — not when the cash or the notional cap bound."""
    cash = GL.entry_plan(PLAN, 4.48, 100_000, 1.0, risk_mult=0.5)       # risk cap 735 shares, cash cap 0
    assert cash["skip_kind"] == "size" and cash["why"] == "0 shares fit the risk, the notional cap and the cash"
    tight = dict(PLAN, trigger=4.46, stop=4.45)
    notional = GL.entry_plan(tight, 4.46, 40, 40, risk_mult=0.5)        # risk cap 5 shares, notional cap 0
    assert notional["skip_kind"] == "size" and "risk_mult" not in notional["why"]
    m = 1.0
    for _ in range(11):
        m = GL.risk_after(m, -0.01)
    locked = GL.entry_plan(PLAN, 4.48, 100_000, 100_000, risk_mult=m)   # the risk cap itself is 0 → named
    assert ("risk_mult is %g" % m) in locked["why"]


# ── the verifier's defects (2026-10-21, round 2 LOW): the disarmed re-stop in the flatten window ─────────────────────
def test_disarmed_after_flatten_time_restops_once_and_never_sells(gg):
    """LOW (HIS CALL #23 in the flatten window): an armed 15:54 tick cancels the stop for the half-off → settle → disarm.
    The 15:55 / 15:56 / 15:59 ticks reach the flatten branch, whose disarmed flatten is a dry run; it used to `continue`
    past the re-stop and the shares sat without a stop through the close. Now: exactly ONE protective SELL stop for every
    unprotected share — no sell at market, no buy, the doc stays open and 'cancelling'."""
    s = _dd_pending(gg)
    _tick(s, 15, 54)
    assert s.coll.get(SAIQ_ID)["dd_half_state"] == "cancelling" and calls(s.brk, "cancel_order") == [{"order_id": "stop-1"}]
    s.brk.settle()
    assert s.brk.working_stop_qty() == 0                                # the shares have no stop now
    s.db.trading_config.rows[0]["armed"] = False
    n0 = len(s.brk.calls)
    restopped = []
    for hh, mm in ((15, 55), (15, 56), (15, 59)):
        out = _tick(s, hh, mm)
        restopped.append(out["gajjala_lane"]["restopped"])
    assert restopped == [1, 0, 0]                                       # ONE stop, never a second
    assert s.brk.calls[n0:] == [("submit_stop", {"symbol": "SAIQ", "qty": 735, "stop_price": 4.31})]
    assert calls(s.brk, "close_position") == [] and _brackets(s.brk) == []      # NEG: no market sell, no buy
    assert s.brk.working_stop_qty() == 735 == int(float(s.brk._positions[0]["qty"]))
    (row,) = _rows(s.db, "gajjala_restop_disarmed")
    assert row["dry_run"] is False and row["detail"]["qty"] == 735 and row["detail"]["kind"] == "dd_half"
    d = s.coll.get(SAIQ_ID)
    assert d["state"] == "open" and d["dd_half_state"] == "cancelling"


def test_flatten_window_NEG_armed_flattens_and_never_restops(gg, monkeypatch):
    """NEG: the same 15:54 cancel, still armed at 15:55 → the normal flatten sells the whole position (the doc moves to
    'closing'); no re-stop, no `gajjala_restop_disarmed` row."""
    s = _dd_pending(gg)
    _tick(s, 15, 54)
    s.brk.settle()
    sells = []

    def close_all(symbol, qty=None):
        s.brk.calls.append(("close_position", {"symbol": symbol, "qty": qty}))
        pos, free = s.brk._free(symbol)
        sells.append(free)
        pos["qty"] = str(int(float(pos["qty"])) - free)
        return {}
    monkeypatch.setattr(s.brk, "close_position", close_all)
    n0 = len(s.brk.calls)
    out = _tick(s, 15, 55)
    assert out["gajjala_lane"]["restopped"] == 0 and not _rows(s.db, "gajjala_restop_disarmed")
    assert calls(s.brk, "submit_stop") == [] and sells == [735]
    assert ("close_position", {"symbol": "SAIQ", "qty": None}) in s.brk.calls[n0:]
    assert s.coll.get(SAIQ_ID)["state"] == "closing" and s.coll.get(SAIQ_ID)["exit_kind"] == "flatten"
