"""SIM broker behavior — fake Mongo + controllable quotes, no network.

Locks trading/broker_sim.py (docs/sepa/auto_entry_methodology.md, "Built-in
SIM broker"): the matching rules of process_fills(), the Alpaca-shaped dicts
the engine reads, the account/position bookkeeping, and the house invariant
that a disarmed exit_engine tick creates NO sim orders.

Matching rules under test (evaluated once per tick against the live quote):
  market buy entry   -> fill at live
  limit buy entry    -> live <= limit -> fill (waits above the limit)
  bracket legs       -> held until the entry fills, then live
  sell stop          -> live <= stop_price -> fill at stop x (1 - slippage)
  sell limit target  -> live >= limit_price -> fill at limit
  OCO                -> one leg fills -> the sibling is canceled
  idempotency        -> an order fills ONCE across repeated process_fills

FakeColl mirrors tests/test_trading_engine.py (house pattern) plus
delete_one/drop, which the sim's position/reset paths need.

Host-runnable (py3.9, no pandas/numpy):
    cd backend && .venv/bin/python -m pytest tests/test_broker_sim.py -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.broker_sim as BS
import trading.exit_engine as EE
from trading.broker_alpaca import OPEN_STATUSES, BrokerError

SLIP = BS.SIM_SLIPPAGE_PCT / 100.0


# ── Fakes (pattern: tests/test_trading_engine.py + delete_one/drop) ──────────

class FakeCursor(list):
    def sort(self, *a, **k):
        return self

    def limit(self, n):
        return FakeCursor(self[:int(n)])


class FakeColl:
    def __init__(self, docs=None):
        self.rows = [dict(d) for d in (docs or [])]

    @staticmethod
    def _match(doc, q):
        for k, v in (q or {}).items():
            if isinstance(v, dict):
                if "$in" in v and doc.get(k) not in v["$in"]:
                    return False
                if "$ne" in v and doc.get(k) == v["$ne"]:
                    return False
            elif doc.get(k) != v:
                return False
        return True

    def find_one(self, q=None, *a, **k):
        for d in self.rows:
            if self._match(d, q):
                return dict(d)
        return None

    def find(self, q=None, *a, **k):
        return FakeCursor(dict(d) for d in self.rows if self._match(d, q))

    def insert_one(self, doc):
        self.rows.append(dict(doc))

    def update_one(self, q, update, upsert=False):
        for d in self.rows:
            if self._match(d, q):
                d.update(update.get("$set") or {})
                return
        if upsert:
            base = {k: v for k, v in (q or {}).items() if not isinstance(v, dict)}
            base.update(update.get("$set") or {})
            self.rows.append(base)

    def delete_one(self, q):
        for i, d in enumerate(self.rows):
            if self._match(d, q):
                del self.rows[i]
                return

    def drop(self):
        self.rows = []


class FakeDB:
    def __init__(self, armed=True):
        self.sim_account = FakeColl()
        self.sim_positions = FakeColl()
        self.sim_orders = FakeColl()
        self.trading_config = FakeColl([{
            "_id": "config", "armed": armed, "auto_entry": False,
            "consecutive_losses": 0, "processed_order_ids": [],
            "equity_cap": 5000.0,
        }])
        self.trade_ledger = FakeColl()
        self.auto_entry_state = FakeColl()


@pytest.fixture
def sim(monkeypatch):
    """Wire broker_sim to a FakeDB + a mutable quote dict; returns both."""

    def build(quotes=None, market_open=True, armed=True):
        db = FakeDB(armed=armed)
        quotes = dict(quotes or {})
        monkeypatch.setattr(BS, "_db", lambda: db)
        monkeypatch.setattr(
            BS, "_bulk_live",
            lambda syms: {s: {"price": quotes[s]} for s in syms if s in quotes})
        monkeypatch.setattr(
            BS, "clock", lambda: {"is_open": bool(market_open),
                                  "timestamp": "2026-06-11T10:00:00-04:00"})
        return db, quotes

    return build


def _orders(db, **match):
    return [o for o in db.sim_orders.rows
            if all(o.get(k) == v for k, v in match.items())]


def _cash(db):
    return float(db.sim_account.find_one({"_id": "account"})["cash"])


def _bracket(symbol="AAA", qty=10, target=115.0, stop=93.0, limit=None):
    return BS.submit_bracket(symbol, qty, take_profit_price=target,
                             stop_price=stop, limit_price=limit,
                             client_order_id=BS.make_client_order_id(symbol, "entry"))


# ── Bracket lifecycle ─────────────────────────────────────────────────────────

def test_market_entry_fills_at_quote_and_activates_held_legs(sim):
    """Market buy fills at the live Massive print; the two bracket legs sit
    `held` until then and go `new` on the parent fill (Alpaca semantics).
    Cash and position update exactly once."""
    db, _ = sim(quotes={"AAA": 100.0})
    order = _bracket()
    assert order["status"] == "new" and order["order_class"] == "bracket"
    assert {leg["status"] for leg in order["legs"]} == {"held"}
    assert {leg["leg_kind"] for leg in order["legs"]} == {"take_profit", "stop_loss"}

    out = BS.process_fills()
    assert [f["side"] for f in out["filled"]] == ["buy"]

    parent = db.sim_orders.find_one({"id": order["id"]})
    assert parent["status"] == "filled"
    assert float(parent["filled_avg_price"]) == 100.0
    assert parent["filled_at"]
    assert _cash(db) == 5000.0 - 10 * 100.0
    pos = db.sim_positions.find_one({"symbol": "AAA"})
    assert pos["qty"] == 10 and float(pos["avg_entry_price"]) == 100.0
    # Both legs now live and visible as TOP-LEVEL open orders (filled parent).
    top = BS.open_orders()
    assert sorted(o["type"] for o in top) == ["limit", "stop"]
    assert all(o["status"] in OPEN_STATUSES and o["side"] == "sell" for o in top)


def test_stop_triggers_at_or_below_and_fills_with_slippage_oco_cancels_target(sim):
    """Live <= stop_price -> the stop fills AT stop x (1 - SIM_SLIPPAGE_PCT)
    — pessimistic; real gaps fill worse. The OCO sibling (take-profit) is
    canceled, the position closes, cash is credited at the slipped price."""
    db, quotes = sim(quotes={"AAA": 100.0})
    _bracket(stop=93.0, target=115.0)
    BS.process_fills()

    quotes["AAA"] = 92.5                            # through the stop
    out = BS.process_fills()
    fill_px = round(93.0 * (1 - SLIP), 4)           # 92.907
    sells = [f for f in out["filled"] if f["side"] == "sell"]
    assert len(sells) == 1 and sells[0]["price"] == fill_px

    stop_row = _orders(db, type="stop", side="sell")[0]
    assert stop_row["status"] == "filled"
    assert float(stop_row["filled_avg_price"]) == fill_px
    target_row = _orders(db, type="limit", side="sell")[0]
    assert target_row["status"] == "canceled"       # OCO
    assert db.sim_positions.find_one({"symbol": "AAA"}) is None
    assert _cash(db) == round(4000.0 + 10 * fill_px, 2)
    # Streak bookkeeping sees both terminal legs via closed_orders_since.
    closed = BS.closed_orders_since("2000-01-01T00:00:00Z")
    assert {(o["type"], o["status"]) for o in closed} >= {
        ("stop", "filled"), ("limit", "canceled"), ("market", "filled")}
    assert all(o["order_class"] == "bracket" for o in closed)


def test_target_fills_at_limit_and_cancels_stop(sim):
    """Live >= target limit -> fill AT the limit; OCO cancels the stop."""
    db, quotes = sim(quotes={"AAA": 100.0})
    _bracket(stop=93.0, target=115.0)
    BS.process_fills()

    quotes["AAA"] = 116.2
    BS.process_fills()
    target_row = _orders(db, type="limit", side="sell")[0]
    assert target_row["status"] == "filled"
    assert float(target_row["filled_avg_price"]) == 115.0   # at the limit
    assert _orders(db, type="stop", side="sell")[0]["status"] == "canceled"
    assert _cash(db) == 4000.0 + 10 * 115.0
    assert db.sim_positions.find_one({"symbol": "AAA"}) is None


def test_limit_entry_waits_above_limit_then_fills(sim):
    """A GTC limit entry does NOT fill while live > limit; once live <= limit
    it fills (never above the limit) and only then do the legs activate."""
    db, quotes = sim(quotes={"AAA": 96.0})
    order = _bracket(limit=95.0)
    BS.process_fills()
    assert db.sim_orders.find_one({"id": order["id"]})["status"] == "new"
    assert all(o["status"] == "held" for o in _orders(db, side="sell"))
    assert _cash(db) == 5000.0

    quotes["AAA"] = 94.4
    BS.process_fills()
    parent = db.sim_orders.find_one({"id": order["id"]})
    assert parent["status"] == "filled"
    assert float(parent["filled_avg_price"]) == 94.4
    assert float(parent["filled_avg_price"]) <= 95.0
    assert all(o["status"] == "new" for o in _orders(db, side="sell"))


def test_replace_order_moves_the_stop_ratchet_path(sim):
    """exit_engine's breakeven ratchet calls replace_order(stop_price=entry);
    the moved stop must trigger at its NEW price."""
    db, quotes = sim(quotes={"AAA": 100.0})
    _bracket(stop=93.0, target=115.0)
    BS.process_fills()
    stop_id = _orders(db, type="stop", side="sell")[0]["id"]

    moved = BS.replace_order(stop_id, stop_price=100.0)
    assert moved["id"] == stop_id and moved["stop_price"] == 100.0

    quotes["AAA"] = 99.0                            # below NEW stop, above old
    BS.process_fills()
    stop_row = db.sim_orders.find_one({"id": stop_id})
    assert stop_row["status"] == "filled"
    assert float(stop_row["filled_avg_price"]) == round(100.0 * (1 - SLIP), 4)


def test_replace_terminal_order_raises(sim):
    db, quotes = sim(quotes={"AAA": 100.0})
    _bracket(stop=93.0, target=115.0)
    BS.process_fills()
    quotes["AAA"] = 90.0
    BS.process_fills()                              # stop filled
    stop_id = _orders(db, type="stop", side="sell")[0]["id"]
    with pytest.raises(BrokerError):
        BS.replace_order(stop_id, stop_price=95.0)


# ── Standalone stop (adopt-and-protect path) ─────────────────────────────────

def test_standalone_submit_stop_triggers_like_a_bracket_leg(sim):
    db, quotes = sim(quotes={"BBB": 50.0})
    db.sim_positions.insert_one({"symbol": "BBB", "qty": 20,
                                 "avg_entry_price": 48.0})
    BS.submit_stop("BBB", 20, 46.5,
                   client_order_id=BS.make_client_order_id("BBB", "protect"))
    BS.process_fills()
    assert _orders(db, side="sell")[0]["status"] == "new"   # 50 > 46.5

    quotes["BBB"] = 46.5                            # AT the stop -> trigger
    BS.process_fills()
    row = _orders(db, side="sell")[0]
    assert row["status"] == "filled"
    assert float(row["filled_avg_price"]) == round(46.5 * (1 - SLIP), 4)
    assert db.sim_positions.find_one({"symbol": "BBB"}) is None


# ── Account / close / idempotency ────────────────────────────────────────────

def test_account_equity_is_cash_plus_position_value_buying_power_is_cash(sim):
    db, _ = sim(quotes={"AAA": 110.0})
    db.sim_account.update_one({"_id": "account"},
                              {"$set": {"cash": 3000.0,
                                        "starting_cash": 5000.0}}, upsert=True)
    db.sim_positions.insert_one({"symbol": "AAA", "qty": 10,
                                 "avg_entry_price": 100.0})
    acct = BS.account()
    assert float(acct["equity"]) == 3000.0 + 10 * 110.0
    assert float(acct["cash"]) == 3000.0
    assert float(acct["buying_power"]) == 3000.0
    pos = BS.positions()[0]
    assert pos["symbol"] == "AAA" and pos["qty"] == "10"
    assert float(pos["avg_entry_price"]) == 100.0
    assert float(pos["current_price"]) == 110.0


def test_close_position_fills_at_live_immediately(sim):
    db, _ = sim(quotes={"BBB": 60.0})
    db.sim_positions.insert_one({"symbol": "BBB", "qty": 5,
                                 "avg_entry_price": 50.0})
    order = BS.close_position("BBB")
    assert order["status"] == "filled" and order["type"] == "market"
    assert float(order["filled_avg_price"]) == 60.0
    assert db.sim_positions.find_one({"symbol": "BBB"}) is None
    assert _cash(db) == 5000.0 + 5 * 60.0
    with pytest.raises(BrokerError):
        BS.close_position("BBB")                    # already gone


def test_fills_are_idempotent_across_repeated_process_fills(sim):
    """An order fills ONCE: repeated matching against the same quotes must
    not move cash or re-fill anything (status transitions are forward-only)."""
    db, quotes = sim(quotes={"AAA": 100.0})
    _bracket(stop=93.0, target=115.0)
    BS.process_fills()
    cash_after_entry = _cash(db)
    out = BS.process_fills()                        # same quotes again
    assert out["filled"] == [] and _cash(db) == cash_after_entry

    quotes["AAA"] = 92.0
    BS.process_fills()                              # stop fills once
    cash_after_stop = _cash(db)
    out = BS.process_fills()
    assert out["filled"] == [] and out["canceled"] == []
    assert _cash(db) == cash_after_stop
    assert len(_orders(db, status="filled")) == 2   # entry + stop, exactly


def test_duplicate_client_order_id_rejected_same_day_idempotency(sim):
    sim(quotes={"AAA": 100.0})
    BS.submit_stop("AAA", 10, 93.0,
                   client_order_id=BS.make_client_order_id("AAA", "protect"))
    with pytest.raises(BrokerError):
        BS.submit_stop("AAA", 10, 93.0,
                       client_order_id=BS.make_client_order_id("AAA", "protect"))


def test_insufficient_cash_rejected_at_submit(sim):
    sim(quotes={"AAA": 100.0})
    with pytest.raises(BrokerError):
        _bracket(qty=100)                           # 100 x $100 > $5k cash


def test_reset_restores_starting_cash_and_drops_state(sim):
    db, quotes = sim(quotes={"AAA": 100.0})
    _bracket()
    BS.process_fills()
    assert db.sim_orders.rows and db.sim_positions.rows
    out = BS.reset()
    assert out == {"ok": True, "cash": BS.SIM_STARTING_CASH}
    assert db.sim_orders.rows == [] and db.sim_positions.rows == []
    assert _cash(db) == BS.SIM_STARTING_CASH == 5000.0


# ── House invariant: disarmed tick places NOTHING (sim included) ─────────────

def test_disarmed_exit_engine_tick_with_sim_broker_creates_no_sim_orders(
        sim, monkeypatch):
    """exit_engine.tick() wired to the REAL sim broker module, disarmed, with
    an unprotected sim position: the tick must write its dry-run ledger row
    and create NO sim order — armed=false places nothing anywhere."""
    db, _ = sim(quotes={"AAA": 102.0})
    db.trading_config.rows[0]["armed"] = False
    db.sim_positions.insert_one({"symbol": "AAA", "qty": 10,
                                 "avg_entry_price": 100.0})
    monkeypatch.setattr(EE, "broker", BS)
    monkeypatch.setattr(EE, "_db", lambda: db)
    monkeypatch.setattr(EE, "regime", lambda: "normal")

    summary = EE.tick(force=True)

    assert db.sim_orders.rows == [], (
        "disarmed tick created sim orders: %r" % (db.sim_orders.rows,))
    dry = [r for r in db.trade_ledger.rows if r.get("dry_run") is True]
    assert any(r["kind"] == "adopt_protect" for r in dry)
    assert summary["dry_run_rows"] >= 1 and summary["adopted"] == 0
    assert summary.get("sim_fills", {}).get("ok") is True


def test_armed_exit_engine_tick_with_sim_broker_adopts_via_sim_stop(
        sim, monkeypatch):
    """Sanity for the wired pair: armed + unprotected sim position -> the
    engine's adopt-and-protect lands ONE working sell-stop in sim_orders at
    initial_stop(avg_entry) — the same flow it runs against Alpaca."""
    from trading.risk_rules import initial_stop
    db, _ = sim(quotes={"AAA": 102.0})
    db.sim_positions.insert_one({"symbol": "AAA", "qty": 10,
                                 "avg_entry_price": 100.0})
    monkeypatch.setattr(EE, "broker", BS)
    monkeypatch.setattr(EE, "_db", lambda: db)
    monkeypatch.setattr(EE, "regime", lambda: "normal")

    summary = EE.tick(force=True)

    stops = _orders(db, type="stop", side="sell")
    assert len(stops) == 1, db.sim_orders.rows
    assert stops[0]["status"] == "new"
    assert stops[0]["stop_price"] == initial_stop(100.0).stop_price == 93.0
    assert summary["adopted"] == 1
