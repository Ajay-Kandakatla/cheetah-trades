"""Auto-Pilot engine behavior — fake broker + fake Mongo, no network, no Alpaca.

Locks the SAFETY behavior of the trading engine (docs/sepa/
risk_management_methodology.md, "How the engine maps the rules to Alpaca"):

  trading.exit_engine.tick() — the reconciler:
    * unprotected position + armed -> exactly ONE submit_stop at
      initial_stop(avg_entry).stop_price (7% below entry, normal regime);
    * disarmed -> NO broker mutation at all; one trade_ledger row with
      dry_run=True (the engine narrates, places nothing);
    * ratchet (p.308): last >= breakeven_trigger(entry, stop) and the stop
      still below entry -> one replace_order moving the stop to breakeven;
      below the trigger, or stop already at/above entry -> no call.

    * every share reserved for a resting sell order (EMR 2026-10-21: a
      bracket take-profit limit held all 36) -> NO submit_stop, ONE
      adopt_held ledger row per position per day, the served sentence on
      status(); free shares -> the stop goes out as before; the hold clears
      the moment the holder is gone; the watchdog still exits a breach.

  trading.entries.enter()/preview() — the ONLY buy path. Refuses:
    * when MAX_POSITIONS (5) are already held (p.312);
    * adding to a held name below average cost (pp.304-305, never average
      down);
    * earnings inside the shield window unless allow_earnings=True;
    * when disarmed;
    * when position_size() floors to 0 shares.
    preview() is pure math: full payload, blocked[] reasons, NO order.

Wiring (each module holds its own `broker` reference; the Mongo accessor
`_db` lives in exit_engine and every helper resolves it there at call time):
  EE.broker / EN.broker            -> FakeBrokerModule (records mutations)
  EE._db / EN._db                  -> FakeDB (trading_config + trade_ledger)
  EE.regime / EN.regime            -> "normal" (gauge not consulted)
  sys.modules["sepa.earnings_watch"] -> stub next_event (earnings shield)

Host-runnable (py3.9, no pandas/numpy):
    cd backend && python3 -m pytest tests/test_trading_engine.py -q
"""
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.entries as EN
import trading.exit_engine as EE
from trading.broker_alpaca import OPEN_STATUSES, BrokerError
from trading.risk_rules import MAX_POSITIONS, breakeven_trigger, initial_stop


# ── Fakes ───────────────────────────────────────────────────────────────────

class FakeCursor(list):
    def sort(self, *a, **k):
        return self

    def limit(self, n):
        return FakeCursor(self[:int(n)])


class FakeColl:
    """Minimal Mongo stand-in (house pattern: tests/test_earnings_watch.py
    FakeColl), extended with insert_one/update_one + cursor chaining for the
    trading_config single-doc and trade_ledger append-only shapes."""

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


class FakeDB:
    """Attribute-style Mongo DB exposing the two trading collections."""

    def __init__(self, armed, losses=0):
        self.trading_config = FakeColl([{
            "_id": "config", "armed": armed,
            "consecutive_losses": losses, "processed_order_ids": [],
            # equity_cap defaults to auto_entry.DEFAULT_EQUITY_CAP (5000) in
            # production; these legacy tests pin cap == fake equity so the
            # p.312 sizing math (25% of 100k = 500 sh at $50) stays visible.
            # The cap's own behavior is locked in tests/test_auto_entry.py.
            "equity_cap": 100_000.0,
            # progressive_exposure pinned OFF: legacy sizing expectations
            # (500 sh full size) predate the pilot governor, which is owned
            # by tests/test_progressive.py.
            "progressive_exposure": False,
        }])
        self.trade_ledger = FakeColl()
        self.auto_entry_state = FakeColl()
        self.trading_account_baseline = FakeColl()   # status() P&L baseline


def _position(symbol, qty, avg_entry, last):
    """Alpaca /v2/positions row shape (string numerics, like the real API)."""
    return {"symbol": symbol, "qty": str(qty),
            "avg_entry_price": str(avg_entry), "current_price": str(last)}


def _stop_order(symbol, stop_price, qty, oid="stop-existing-1"):
    """Alpaca /v2/orders working sell-stop (status must be in OPEN_STATUSES)."""
    return {"id": oid, "symbol": symbol, "qty": str(qty), "side": "sell",
            "type": "stop", "status": "new", "stop_price": str(stop_price),
            "limit_price": None, "legs": None}


class FakeBrokerModule:
    """Drop-in for trading.broker_alpaca: canned reads, every mutation
    recorded in .calls as (method, {named args})."""

    OPEN_STATUSES = OPEN_STATUSES
    BrokerError = BrokerError

    def __init__(self, positions=(), orders=(), equity=100_000.0,
                 market_open=True):
        self._positions = list(positions)
        self._orders = list(orders)
        self._equity = float(equity)
        self._market_open = bool(market_open)
        self.calls = []

    # -- reads ----------------------------------------------------------------
    def configured(self):
        return True

    def clock(self):
        return {"is_open": self._market_open}

    def account(self):
        return {"equity": str(self._equity), "cash": str(self._equity),
                "buying_power": str(self._equity)}

    def positions(self):
        return [dict(p) for p in self._positions]

    def open_orders(self, symbol=None):
        return [dict(o) for o in self._orders
                if symbol is None or o.get("symbol") == symbol]

    def closed_orders_since(self, iso_ts):
        return []

    def latest_trade(self, symbol):
        return None

    def make_client_order_id(self, symbol, intent):
        return "test-%s-%s" % (symbol, intent)

    # -- mutations (recorded) ---------------------------------------------------
    def submit_stop(self, symbol, qty, stop_price, client_order_id=None):
        self.calls.append(("submit_stop", {
            "symbol": symbol, "qty": qty, "stop_price": stop_price}))
        return {"id": "submitted-stop-%d" % len(self.calls)}

    def submit_bracket(self, symbol, qty, take_profit_price, stop_price,
                       limit_price=None, client_order_id=None, tif="gtc",
                       order_class="bracket"):
        self.calls.append(("submit_bracket", {
            "symbol": symbol, "qty": qty,
            "take_profit_price": take_profit_price, "stop_price": stop_price,
            "limit_price": limit_price}))
        return {"id": "submitted-bracket-%d" % len(self.calls)}

    def replace_order(self, order_id, stop_price=None, limit_price=None):
        self.calls.append(("replace_order", {
            "order_id": order_id, "stop_price": stop_price,
            "limit_price": limit_price}))
        return {"id": order_id}

    def cancel_order(self, order_id):
        self.calls.append(("cancel_order", {"order_id": order_id}))

    def close_position(self, symbol):
        self.calls.append(("close_position", {"symbol": symbol}))
        return {}


@pytest.fixture
def env(monkeypatch):
    """Build a wired engine environment; returns (fake_broker, fake_db)."""

    def build(positions=(), orders=(), armed=True, losses=0,
              equity=100_000.0, earnings_days=None, market_open=True):
        fake = FakeBrokerModule(positions, orders, equity, market_open)
        db = FakeDB(armed=armed, losses=losses)
        monkeypatch.setattr(EE, "broker", fake)
        monkeypatch.setattr(EN, "broker", fake)
        monkeypatch.setattr(EE, "_db", lambda: db)
        monkeypatch.setattr(EN, "_db", lambda: db)   # entries' own binding
        monkeypatch.setattr(EE, "regime", lambda: "normal")
        monkeypatch.setattr(EN, "regime", lambda: "normal")
        # Default: no distribution signal (don't touch the real SEPA scanner).
        # Sell-discipline tests override this with a canned scan row.
        monkeypatch.setattr(EE, "_distribution_read", lambda sym: None)
        stub = types.ModuleType("sepa.earnings_watch")
        if earnings_days is None:
            stub.next_event = lambda s: None
        else:
            stub.next_event = lambda s, _d=earnings_days: {
                "date": "2026-06-14", "days_to": _d}
        monkeypatch.setitem(sys.modules, "sepa.earnings_watch", stub)
        return fake, db

    return build


def _calls(broker, method):
    return [kw for name, kw in broker.calls if name == method]


def _dry_rows(db):
    return [r for r in db.trade_ledger.rows if r.get("dry_run") is True]


# ── Exit engine: adopt-and-protect ───────────────────────────────────────────

def test_unprotected_position_armed_places_exactly_one_7pct_stop(env):
    """pp.301-302: a stop must always rest at the broker. Armed + an
    unprotected long -> exactly ONE submit_stop at initial_stop(avg_entry)
    = 7% below entry in a normal regime."""
    broker, db = env(positions=[_position("AAA", 100, 100.0, 102.0)])
    summary = EE.tick()

    stops = _calls(broker, "submit_stop")
    assert len(stops) == 1, broker.calls
    assert stops[0]["symbol"] == "AAA"
    assert stops[0]["qty"] == 100
    assert stops[0]["stop_price"] == initial_stop(100.0).stop_price == 93.0
    assert summary["adopted"] == 1
    assert not _calls(broker, "replace_order")
    # The ledger row is real (not dry) and carries the page cite.
    rows = [r for r in db.trade_ledger.rows if r["kind"] == "adopt_protect"]
    assert len(rows) == 1 and rows[0]["dry_run"] is False
    assert rows[0]["cite"] == "p.301-302"


def test_disarmed_tick_places_nothing_and_logs_one_dry_run_row(env):
    """The armed gate is the master safety: disarmed, the engine must not
    touch the broker — it writes exactly one dry_run ledger row describing
    the stop it WOULD have placed."""
    broker, db = env(positions=[_position("AAA", 100, 100.0, 102.0)],
                     armed=False)
    summary = EE.tick()

    assert broker.calls == [], (
        "disarmed engine touched the broker: %r" % (broker.calls,))
    dry = _dry_rows(db)
    assert len(dry) == 1, db.trade_ledger.rows
    assert dry[0]["kind"] == "adopt_protect"
    assert dry[0]["detail"]["stop_price"] == 93.0
    assert summary["dry_run_rows"] == 1 and summary["adopted"] == 0


# ── Exit engine: breakeven ratchet (p.308) ───────────────────────────────────

def test_ratchet_replaces_stop_at_breakeven_at_3R(env):
    """p.308 worked example as a live ratchet: entry 50, stop 47.50 (risk
    2.50) -> trigger 57.50. Last 57.60 >= trigger and the stop is below
    entry -> exactly one replace_order to breakeven 50.0."""
    assert breakeven_trigger(50.0, 47.50) == 57.50
    broker, db = env(positions=[_position("BBB", 40, 50.0, 57.60)],
                     orders=[_stop_order("BBB", 47.50, 40)])
    summary = EE.tick()

    replaces = _calls(broker, "replace_order")
    assert len(replaces) == 1, broker.calls
    assert replaces[0]["order_id"] == "stop-existing-1"
    assert replaces[0]["stop_price"] == 50.0
    assert summary["ratcheted"] == 1
    assert not _calls(broker, "submit_stop")       # already protected
    rows = [r for r in db.trade_ledger.rows if r["kind"] == "ratchet_breakeven"]
    assert len(rows) == 1 and rows[0]["cite"] == "p.308"


def test_ratchet_does_not_fire_below_trigger(env):
    """Last 57.40 < 57.50 trigger -> no replace, no new stop, no mutation."""
    broker, _ = env(positions=[_position("BBB", 40, 50.0, 57.40)],
                    orders=[_stop_order("BBB", 47.50, 40)])
    EE.tick()
    assert broker.calls == [], (
        "ratchet fired below the 3R trigger: %r" % (broker.calls,))


def test_ratchet_idempotent_once_stop_at_or_above_entry(env):
    """Stop already at breakeven (>= entry) -> no replace churn every tick
    (p.308 says 'at least breakeven', once)."""
    broker, _ = env(positions=[_position("BBB", 40, 50.0, 60.0)],
                    orders=[_stop_order("BBB", 50.0, 40)])
    EE.tick()
    assert broker.calls == [], (
        "stop already at breakeven; replace churn: %r" % (broker.calls,))


def test_ratchet_no_loop_when_avg_entry_has_subcent_precision(env):
    """Regression (verify-gate 2026-06-11): Alpaca's avg_entry_price can
    carry >2 decimals (e.g. 100.564). After ratcheting to the cent grid
    (round(avg_entry, 2) == 100.56) the raw float still sits above the stop,
    so a `cur_stop < avg_entry` guard re-fires every tick — an infinite
    replace_order loop with the SAME price. The guard must compare against
    the rounded breakeven, not the raw float."""
    broker, db = env(positions=[_position("CCC", 10, 100.564, 130.0)],
                     orders=[_stop_order("CCC", 100.56, 10)])
    # Original adopt row: 7%-style initial stop, so the 3R trigger (p.308)
    # is long since met at last=130 — the loop bug would fire here.
    db.trade_ledger.insert_one({"kind": "adopt_protect", "symbol": "CCC",
                                "epoch": 1.0, "dry_run": False,
                                "detail": {"stop_price": 93.52}})
    EE.tick()
    assert broker.calls == [], (
        "ratchet loop: re-replaced an at-breakeven stop: %r" % (broker.calls,))


# ── Watchdog: the engine's own backstop when the broker stop won't fire ──────
# Alpaca can leave a bracket stop-loss leg stuck in "held" so it never triggers
# even when price reaches it (confirmed 2026-06-24). The watchdog force-exits
# at market when price breaches the committed stop and NO genuinely-working
# broker stop rests — so protection never depends on the broker alone (p.301-302).

def _held_stop_order(symbol, stop_price, qty, oid="held-stop-1"):
    """A bracket stop-loss leg stuck in Alpaca's "held" state — present, priced,
    but NOT working (won't fire). The watchdog must treat it as no protection."""
    return {"id": oid, "symbol": symbol, "qty": str(qty), "side": "sell",
            "type": "stop", "status": "held", "order_class": "bracket",
            "stop_price": str(stop_price), "limit_price": None, "legs": None}


def test_watchdog_exits_at_market_when_stop_breached_and_no_working_stop(env):
    """Armed, no working stop, last (92) at/below the committed stop (93 = 7%
    initial in normal regime) -> the engine SELLS AT MARKET this tick and does
    NOT instead try to adopt a stop."""
    broker, db = env(positions=[_position("AAA", 100, 100.0, 92.0)])
    summary = EE.tick()

    closes = _calls(broker, "close_position")
    assert closes == [{"symbol": "AAA"}], broker.calls
    assert not _calls(broker, "submit_stop"), "adopted instead of exiting"
    assert summary["watchdog_exits"] == 1
    rows = [r for r in db.trade_ledger.rows if r["kind"] == "watchdog_exit"]
    assert len(rows) == 1 and rows[0]["dry_run"] is False
    assert rows[0]["cite"] == "p.301-302"
    assert rows[0]["detail"]["stop"] == 93.0


def test_watchdog_treats_a_held_bracket_stop_as_no_protection(env):
    """The core Alpaca-bug regression: a "held" stop leg exists at the broker but
    won't fire. With price below it, the watchdog must STILL exit (held != working)."""
    broker, _ = env(positions=[_position("AAA", 100, 100.0, 92.0)],
                    orders=[_held_stop_order("AAA", 93.0, 100)])
    summary = EE.tick()
    assert _calls(broker, "close_position") == [{"symbol": "AAA"}], broker.calls
    assert summary["watchdog_exits"] == 1


def test_watchdog_does_not_fire_when_a_working_stop_rests(env):
    """A genuinely-working broker stop is trusted (avoids double-selling /
    slippage): price below it -> the engine does NOT market-close."""
    broker, _ = env(positions=[_position("AAA", 100, 100.0, 92.0)],
                    orders=[_stop_order("AAA", 93.0, 100)])
    EE.tick()
    assert not _calls(broker, "close_position"), broker.calls


def test_watchdog_does_not_fire_above_the_stop(env):
    """Price (95) above the stop (93) -> no exit; adopt-and-protect runs as usual."""
    broker, _ = env(positions=[_position("AAA", 100, 100.0, 95.0)])
    EE.tick()
    assert not _calls(broker, "close_position"), broker.calls
    assert len(_calls(broker, "submit_stop")) == 1   # normal adopt path


def test_watchdog_disarmed_places_nothing_and_logs_one_dry_run(env):
    """Disarmed master gate holds for the watchdog too: a breach writes a single
    dry_run watchdog_exit row and touches the broker zero times."""
    broker, db = env(positions=[_position("AAA", 100, 100.0, 92.0)], armed=False)
    summary = EE.tick()
    assert broker.calls == [], broker.calls
    dry = [r for r in db.trade_ledger.rows
           if r.get("dry_run") and r["kind"] == "watchdog_exit"]
    assert len(dry) == 1
    assert summary["dry_run_rows"] >= 1 and summary["watchdog_exits"] == 0


def test_watchdog_close_failure_is_surfaced_not_swallowed(monkeypatch, env):
    """If the market-close itself fails, the error must be LOUD: in the tick
    summary AND persisted to config.last_errors for the dashboard — never a
    silent swallow like the old adopt path."""
    broker, db = env(positions=[_position("AAA", 100, 100.0, 92.0)])

    def boom(symbol):
        raise BrokerError("alpaca close rejected")
    monkeypatch.setattr(broker, "close_position", boom)

    summary = EE.tick()
    assert any("watchdog AAA" in e for e in summary["errors"]), summary["errors"]
    assert summary["watchdog_exits"] == 0
    assert any("watchdog AAA" in e for e in (EE.get_config().get("last_errors") or []))


# ── Sell discipline: distribution / stage-breakdown auto-exit (2026-06-25) ────
# Ajay chose AGGRESSIVE: any topping/distribution/exhaustion signal on a held
# name → auto-sell at market (sell_discipline.evaluate). Runs in the tick after
# the watchdog, before adopt. Dedup once per symbol/day/kind.
from trading import sell_discipline as SD

_STAGE3_DIST = {"stage": {"stage": 3}, "volume": {"accumulation_strength": "distributing"}}


def test_evaluate_decisive_breaks_are_auto_sell():
    assert SD.evaluate({"sell_signals": {"signals": {"close_below_200ma": True}}}, 50)["action"] == "auto_sell"
    assert SD.evaluate({"stage": {"stage": 4}, "trend": {"ma50": 100}}, 95)["action"] == "auto_sell"  # >=3% below
    assert SD.evaluate({"stage": {"stage": 4}, "trend": {"ma50": 100}}, 98) is None                   # only 2% below


def test_evaluate_topping_signals_are_auto_sell_in_aggressive_mode():
    assert SD.evaluate(_STAGE3_DIST, 100)["action"] == "auto_sell"
    assert SD.evaluate({"climax_distribution": {"is_distribution": True}}, 100)["action"] == "auto_sell"
    assert SD.evaluate({"mvp_exhaustion": True}, 100)["action"] == "auto_sell"


def test_evaluate_clean_or_missing_is_none():
    assert SD.evaluate({"stage": {"stage": 2}, "volume": {"accumulation_strength": "accumulating"}}, 100) is None
    assert SD.evaluate(None, 100) is None


def test_evaluate_decisive_break_trumps_a_topping_warning():
    # Stage 3 AND a 200DMA break → the decisive 200DMA verdict wins (checked first).
    v = SD.evaluate({**_STAGE3_DIST, "sell_signals": {"signals": {"close_below_200ma": True}}}, 50)
    assert "200-day" in v["reason"]


def test_distribution_auto_sells_a_held_topper_when_armed(env, monkeypatch):
    broker, db = env(positions=[_position("AAA", 10, 100.0, 100.0)])   # last 100 > 93 stop → watchdog quiet
    monkeypatch.setattr(EE, "_distribution_read", lambda sym: _STAGE3_DIST)
    summary = EE.tick()
    assert _calls(broker, "close_position") == [{"symbol": "AAA"}], broker.calls
    assert not _calls(broker, "submit_stop"), "adopted a stop on a name it should exit"
    assert summary["distribution_exits"] == 1
    rows = [r for r in db.trade_ledger.rows if r["kind"] == "distribution_exit"]
    assert len(rows) == 1 and rows[0]["dry_run"] is False and "p.72" in (rows[0]["cite"] or "")


def test_distribution_disarmed_is_dry_run_only(env, monkeypatch):
    broker, db = env(positions=[_position("AAA", 10, 100.0, 100.0)], armed=False)
    monkeypatch.setattr(EE, "_distribution_read", lambda sym: _STAGE3_DIST)
    summary = EE.tick()
    assert broker.calls == [], broker.calls
    dry = [r for r in db.trade_ledger.rows if r.get("dry_run") and r["kind"] == "distribution_exit"]
    assert len(dry) == 1 and summary["distribution_exits"] == 0


def test_distribution_fires_at_most_once_per_day(env, monkeypatch):
    broker, _ = env(positions=[_position("AAA", 10, 100.0, 100.0)])
    monkeypatch.setattr(EE, "_distribution_read", lambda sym: _STAGE3_DIST)
    monkeypatch.setattr(EE, "_fired_today", lambda kind, sym: True)   # already sold/alerted today
    EE.tick()
    assert not _calls(broker, "close_position"), broker.calls


def test_clean_name_is_not_sold_and_still_gets_its_stop(env, monkeypatch):
    broker, _ = env(positions=[_position("AAA", 10, 100.0, 100.0)])
    monkeypatch.setattr(EE, "_distribution_read",
                        lambda sym: {"stage": {"stage": 2}, "volume": {"accumulation_strength": "accumulating"}})
    EE.tick()
    assert not _calls(broker, "close_position")
    assert len(_calls(broker, "submit_stop")) == 1   # normal adopt-and-protect still runs


# ── Entries: refusal checks (every reason cited) ─────────────────────────────

def _enter_blocked(symbol, price, **kw):
    """enter() raises ValueError('; '.join(blocked)) — capture the reasons."""
    with pytest.raises(ValueError) as exc_info:
        EN.enter(symbol, limit_price=price, **kw)
    return str(exc_info.value)


def test_entry_rejected_at_max_positions(env):
    """p.312 position-count cap: 5 names held -> a 6th entry is refused and
    no order reaches the broker."""
    held = [_position(s, 10, 100.0, 110.0)
            for s in ("AAA", "BBB", "CCC", "DDD", "EEE")]
    assert len(held) == MAX_POSITIONS
    broker, _ = env(positions=held)
    msg = _enter_blocked("NEW", 50.0)
    assert "portfolio full" in msg and "p.312" in msg, msg
    assert broker.calls == []


def test_entry_rejects_averaging_down(env):
    """pp.304-305: 'only losers average losers' — held at 100, trading 90:
    adding is refused, the reason says so, no order is placed."""
    broker, _ = env(positions=[_position("NVDA", 10, 100.0, 90.0)])
    msg = _enter_blocked("NVDA", 90.0)
    assert "average down" in msg, msg
    assert broker.calls == []


def test_earnings_shield_blocks_unless_overridden(env):
    """Earnings in 3 days -> refused (a stop cannot protect an overnight
    gap; pp.296-297 disaster-plan logic). allow_earnings=True lifts the
    shield and the entry goes out as a bracket with book-correct legs."""
    broker, _ = env(earnings_days=3)
    msg = _enter_blocked("GAP", 50.0)
    assert "earnings in 3d" in msg, msg
    assert broker.calls == []

    res = EN.enter("GAP", limit_price=50.0, allow_earnings=True)
    brackets = _calls(broker, "submit_bracket")
    assert len(brackets) == 1, broker.calls
    # 25% of 100k at $50 = 500 shares; 7% stop = 46.50; 15% target = 57.50.
    assert res["shares"] == 500
    assert res["stop"]["stop_price"] == 46.5
    assert res["target"]["target_price"] == 57.5
    assert brackets[0]["stop_price"] == 46.5
    assert brackets[0]["take_profit_price"] == 57.5


def test_entry_rejected_when_disarmed(env):
    """Disarmed is the master safety on the buy side too."""
    broker, _ = env(armed=False)
    msg = _enter_blocked("NEW", 50.0)
    assert "disarmed" in msg, msg
    assert broker.calls == []


def test_entry_rejected_when_size_floors_to_zero_shares(env):
    """position_size() floors to whole shares (p.312); $100 equity at a
    $5000 name is 0 shares -> refuse rather than send a zero-qty order."""
    broker, _ = env(equity=100.0)
    msg = _enter_blocked("PRCY", 5000.0)
    assert "0 shares" in msg, msg
    assert broker.calls == []


def test_preview_is_pure_math_and_carries_contract_keys(env):
    """GET /trading/preview contract: full plan + blocked[] reasons, and NO
    order ever leaves preview — the FE builds against these keys."""
    broker, _ = env(armed=False, earnings_days=3)
    out = EN.preview("GAP", price=50.0)
    assert broker.calls == [], "preview placed an order: %r" % (broker.calls,)
    for key in ("symbol", "price", "shares", "allocation", "stop", "target",
                "breakeven_trigger", "equity_risk_pct", "earnings", "blocked"):
        assert key in out, "preview payload missing `%s`" % key
    blob = " ".join(out["blocked"])
    assert "disarmed" in blob and "earnings" in blob, out["blocked"]
    # The math is still computed for the UI even while blocked.
    assert out["stop"]["stop_price"] == 46.5
    assert out["target"]["target_price"] == 57.5
    assert out["breakeven_trigger"] == 60.5       # 50 + 3 x 3.50 (p.308)


def test_detail_text_flattens_objects_for_the_feed():
    """Regression — the ledger feed renders detail as plain text, so an object
    reaching the frontend crashes React (#31). _detail_text must flatten the
    exact auto_entry_disabled {gate, hint} shape that white-screened the page."""
    from trading.exit_engine import _detail_text
    out = _detail_text({"gate": {"configured": True, "armed": False,
                                 "auto_entry": False, "market_open": True},
                        "hint": "needs armed + auto_entry"})
    assert isinstance(out, str)
    assert "armed=False" in out and "hint: needs armed" in out
    assert _detail_text("already a string") == "already a string"
    assert _detail_text(None) == ""
    assert _detail_text({"flags": ["a", "b"], "n": 3}) == "flags: a, b · n: 3"


# ── Adopt-and-protect when the shares are held by a resting sell order (2026-10-21)
# EMR: a bracket take-profit sell LIMIT from 2026-09-22 held all 36 shares;
# Alpaca refused the protective stop every minute (HTTP 403 40310000,
# available 0 / held_for_orders 36) and nothing was ledgered — the line only
# lived in last_errors. The engine must see the hold BEFORE posting, write ONE
# adopt_held row per position per ET day, serve the sentence on status() and
# leave the holding order alone (cancel vs OCO is the owner's call).

EMR_SENTENCE = ("36 sh held by a sell limit from 2026-09-22 — no stop can rest; "
                "cancel it or replace it with an OCO (your call)")


def _sell_limit(symbol, limit_price, qty, oid="limit-1",
                submitted_at="2026-09-22T13:34:08.28669Z", status="new"):
    """Alpaca /v2/orders working sell LIMIT (a bracket's take-profit leg)."""
    return {"id": oid, "client_order_id": "5cf7cce7-a60d-4a63-b8d5-e3d658065ea4",
            "symbol": symbol, "qty": str(qty), "side": "sell", "type": "limit",
            "order_type": "limit", "status": status, "order_class": "bracket",
            "limit_price": str(limit_price), "stop_price": None,
            "submitted_at": submitted_at, "legs": None}


def _emr(**patch):
    """The live EMR row on 2026-10-21 (qty_available 0 = every share held)."""
    pos = _position("EMR", 36, 153.49, 163.37)
    pos["qty_available"] = "0"
    pos.update(patch)
    return pos


def _held_rows(db):
    return [r for r in db.trade_ledger.rows if r["kind"] == "adopt_held"]


def test_held_position_writes_one_adopt_held_row_and_never_posts_the_stop(env):
    broker, db = env(positions=[_emr()], orders=[_sell_limit("EMR", 168.18, 36)])
    summary = EE.tick()

    assert not _calls(broker, "submit_stop"), broker.calls
    assert not _calls(broker, "cancel_order") and not _calls(broker, "replace_order")
    assert summary["adopt_held"] == 1 and summary["adopted"] == 0
    assert not any("adopt EMR" in e for e in summary["errors"]), summary["errors"]
    assert not any("EMR" in e for e in (EE.get_config().get("last_errors") or []))
    rows = _held_rows(db)
    assert len(rows) == 1
    assert rows[0]["dry_run"] is False and rows[0]["cite"] == "p.301-302"
    d = rows[0]["detail"]
    assert d["sentence"] == EMR_SENTENCE
    assert d["held_qty"] == 36 and d["available"] == 0 and d["qty"] == 36
    assert d["stop_price"] == initial_stop(153.49).stop_price
    assert d["orders"] == [{"id": "limit-1",
                            "client_order_id": "5cf7cce7-a60d-4a63-b8d5-e3d658065ea4",
                            "type": "limit", "qty": 36, "status": "new",
                            "submitted_at": "2026-09-22T13:34:08.28669Z",
                            "limit_price": "168.18", "stop_price": None,
                            "order_class": "bracket"}]


def test_held_position_status_serves_the_sentence_under_the_position(env):
    broker, db = env(positions=[_emr()], orders=[_sell_limit("EMR", 168.18, 36)])
    out = EE.status()
    assert out["error"] is None, out["error"]
    row = {p["symbol"]: p for p in out["positions"]}["EMR"]
    assert row["adopt_held"]["sentence"] == EMR_SENTENCE
    assert row["adopt_held"]["held_qty"] == 36 and row["adopt_held"]["available"] == 0
    assert row["adopt_held"]["orders"][0]["id"] == "limit-1"
    assert row["stop"] is None
    # The watchdog still covers a breach, so the badge is not "none".
    assert row["stop_status"] == "watchdog" and row["protected"] is True
    assert "EMR" not in out["unprotected"]
    # The holder IS the take-profit leg: it still prints as the target.
    assert row["target"] == {"price": 168.18, "order_id": "limit-1"}
    assert not broker.calls


def test_second_tick_writes_no_second_adopt_held_row(env):
    """NEGATIVE: once per position per day — three ticks, one row, zero POSTs."""
    broker, db = env(positions=[_emr()], orders=[_sell_limit("EMR", 168.18, 36)])
    EE.tick()
    EE.tick()
    s3 = EE.tick()
    assert len(_held_rows(db)) == 1
    assert not _calls(broker, "submit_stop"), broker.calls
    assert s3["adopt_held"] == 1          # still counted each tick, written once


def test_the_hold_clears_the_moment_the_limit_is_gone(env):
    """NEGATIVE: the gate is the LIVE state, not the day's row — with the limit
    cancelled the very next tick posts the stop (the day's adopt_held row must
    not block adopt-and-protect) and status() serves no sentence."""
    broker, db = env(positions=[_emr()], orders=[_sell_limit("EMR", 168.18, 36)])
    EE.tick()
    assert not _calls(broker, "submit_stop")

    broker._orders = []                           # the owner cancelled it at Alpaca
    broker._positions[0]["qty_available"] = "36"
    s = EE.tick()
    stops = _calls(broker, "submit_stop")
    assert len(stops) == 1 and stops[0]["symbol"] == "EMR" and stops[0]["qty"] == 36
    assert stops[0]["stop_price"] == initial_stop(153.49).stop_price
    assert s["adopted"] == 1 and s["adopt_held"] == 0
    assert [r["kind"] for r in db.trade_ledger.rows if r["symbol"] == "EMR"] == ["adopt_held", "adopt_protect"]
    row = {p["symbol"]: p for p in EE.status()["positions"]}["EMR"]
    assert row["adopt_held"] is None


def test_free_shares_still_get_their_stop_even_with_a_partial_sell_limit(env):
    """NEGATIVE: a sell limit on 40 of 100 shares is NOT a hold — the full-size
    stop goes out exactly as before and no adopt_held row is written."""
    pos = _position("AAA", 100, 100.0, 102.0)
    pos["qty_available"] = "60"
    broker, db = env(positions=[pos], orders=[_sell_limit("AAA", 120.0, 40, oid="limit-part")])
    s = EE.tick()
    stops = _calls(broker, "submit_stop")
    assert len(stops) == 1 and stops[0]["qty"] == 100
    assert s["adopted"] == 1 and s["adopt_held"] == 0
    assert not _held_rows(db)
    row = {p["symbol"]: p for p in EE.status()["positions"]}["AAA"]
    assert row["adopt_held"] is None


def test_a_position_without_qty_available_and_no_orders_is_not_a_hold(env):
    """NEGATIVE: the sim broker's positions carry no qty_available — unchanged."""
    broker, db = env(positions=[_position("AAA", 100, 100.0, 102.0)])
    s = EE.tick()
    assert len(_calls(broker, "submit_stop")) == 1 and s["adopt_held"] == 0
    assert not _held_rows(db)
    assert {p["symbol"]: p for p in EE.status()["positions"]}["AAA"]["adopt_held"] is None


def test_qty_available_zero_with_no_visible_holder_is_a_hold(env):
    """Alpaca says nothing is free but the open-order list shows no holder
    (lagging list): no POST either, and the sentence says so."""
    broker, db = env(positions=[_emr()])
    s = EE.tick()
    assert not _calls(broker, "submit_stop") and s["adopt_held"] == 1
    rows = _held_rows(db)
    assert len(rows) == 1 and rows[0]["detail"]["orders"] == []
    assert rows[0]["detail"]["sentence"] == (
        "36 sh held by orders the engine cannot see (0 available) — no stop can rest; "
        "cancel them or replace them with an OCO (your call)")


def test_watchdog_still_exits_a_held_position_on_a_breach(env):
    """The price check is untouched: last (140) under the committed stop
    (142.75 = 7% under 153.49) with the limit holding the shares -> the existing
    _force_exit path cancels the holder and closes at market; no stop POST, no
    adopt_held row (the name is leaving)."""
    broker, db = env(positions=[_emr(current_price="140.0")],
                     orders=[_sell_limit("EMR", 168.18, 36)])
    s = EE.tick()
    assert _calls(broker, "cancel_order") == [{"order_id": "limit-1"}], broker.calls
    assert _calls(broker, "close_position") == [{"symbol": "EMR"}]
    assert not _calls(broker, "submit_stop")
    assert s["watchdog_exits"] == 1 and s["adopt_held"] == 0
    assert not _held_rows(db)


def test_disarmed_held_position_touches_nothing_and_writes_one_row(env):
    broker, db = env(positions=[_emr()], orders=[_sell_limit("EMR", 168.18, 36)],
                     armed=False)
    EE.tick()
    EE.tick()
    assert broker.calls == [], broker.calls
    assert len(_held_rows(db)) == 1
    assert not _dry_rows(db)              # no adopt_protect dry-run spam either
    row = {p["symbol"]: p for p in EE.status()["positions"]}["EMR"]
    assert row["adopt_held"]["sentence"] == EMR_SENTENCE


def test_a_held_refusal_with_no_visible_holder_is_ledgered_once_and_stays_loud(env, monkeypatch):
    """Fallback: no holder visible AND no qty_available (the pre-check cannot
    see the hold) and Alpaca still refuses as held -> the error line stays in
    the summary + last_errors AND one adopt_held row per day is written."""
    broker, db = env(positions=[_position("EMR", 36, 153.49, 163.37)])

    def refuse(symbol, qty, stop_price, client_order_id=None):
        raise BrokerError('alpaca POST /v2/orders -> HTTP 403: {"available":"0",'
                          '"code":40310000,"existing_qty":"36","held_for_orders":"36",'
                          '"message":"insufficient qty available for order (requested: 36, available: 0)"}')
    monkeypatch.setattr(broker, "submit_stop", refuse)
    s = EE.tick()
    EE.tick()
    assert any("adopt EMR" in e for e in s["errors"]), s["errors"]
    assert any("adopt EMR" in e for e in (EE.get_config().get("last_errors") or []))
    rows = _held_rows(db)
    assert len(rows) == 1
    assert "cannot see" in rows[0]["detail"]["sentence"]
    assert "40310000" in rows[0]["detail"]["error"]


def test_a_non_held_refusal_writes_no_adopt_held_row(env, monkeypatch):
    """NEGATIVE: any other broker refusal is NOT a hold — error only, as before."""
    broker, db = env(positions=[_position("AAA", 100, 100.0, 102.0)])

    def refuse(*a, **k):
        raise BrokerError("alpaca POST /v2/orders -> HTTP 422: stop price too close")
    monkeypatch.setattr(broker, "submit_stop", refuse)
    s = EE.tick()
    assert any("adopt AAA" in e for e in s["errors"])
    assert not _held_rows(db) and s["adopt_held"] == 0


def test_adopt_held_sentence_shapes():
    one = EE.adopt_held_sentence(36, {"orders": [{"type": "limit", "submitted_at": "2026-09-22T13:34:08Z"}]})
    assert one == EMR_SENTENCE
    two = EE.adopt_held_sentence(100, {"orders": [
        {"type": "limit", "submitted_at": "2026-09-22T13:34:08Z"},
        {"type": "stop", "submitted_at": None}]})
    assert two == ("100 sh held by 2 sell orders (limit from 2026-09-22, stop from an unknown date)"
                   " — no stop can rest; cancel them or replace them with an OCO (your call)")
    blind = EE.adopt_held_sentence(36, {"orders": [], "available": 0})
    assert blind == ("36 sh held by orders the engine cannot see (0 available) — no stop can rest; "
                     "cancel them or replace them with an OCO (your call)")
