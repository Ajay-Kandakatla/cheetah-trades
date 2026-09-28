"""Chart Maps lane program — the chokepoint caps (trading/program_caps.py).

Ajay 2026-09-27: "stop minerviews use all strategies from Most used from Chart
maps. All of them and journal the," — "Small: 0.25% risk, 15 open max",
"Top 10 most-used first".

What these pin, because getting any of it wrong costs real (paper) money and
the autopsy found the engine broke its own caps twice at the opening bell:
  * the in-flight open cap counts PENDING entry orders and option spread legs
    (a1 / C1), in every mode;
  * one entry per ET minute, claimed atomically — a slow tick can never claim
    backwards, two racers cannot both win, an unreadable clock refuses;
  * legacy lane tags (demand_zone, breakout, catalyst, quick_bounce,
    hot_pullback, zero_dte) hit the SAME per-strategy caps and 0.25% sizing
    as the new generic lanes (critic 1);
  * one lane per name; not-a-lane tabs (vcp, topping, ...) are refused in
    every mode; live is never a program.

The fakes here (MiniDB / MiniColl / CapsBroker) are imported by the other
program test modules — the house pattern (tests import each other's fakes).
Hermetic: no network, no Mongo, no broker.
"""
import os
import re
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pymongo.errors import DuplicateKeyError  # noqa: E402

import trading.exit_engine as EE  # noqa: E402
import trading.program_caps as PC  # noqa: E402
import trading.strategy_tags as ST  # noqa: E402
from trading import risk_rules  # noqa: E402
from trading.broker_alpaca import BrokerError  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

ET = ZoneInfo("America/New_York")


# ═════════════════════════════════════════════════════════════════════════════
# Fakes (shared)
# ═════════════════════════════════════════════════════════════════════════════
class MiniCursor(list):
    def sort(self, key=None, direction=1, *a, **k):
        if isinstance(key, list):
            key, direction = key[0]
        if key:
            list.sort(self, key=lambda d: (d.get(key) is None, d.get(key) if d.get(key) is not None else 0),
                      reverse=(direction == -1))
        return self

    def limit(self, n):
        return MiniCursor(self[:int(n)])


def _cmp_ok(dv, op, val):
    if op == "$in":
        return dv in val
    if op == "$nin":
        return dv not in val
    if op == "$ne":
        return dv != val
    if op == "$exists":
        return (dv is not None) == bool(val)
    if dv is None:
        return False
    if op == "$lt":
        return dv < val
    if op == "$lte":
        return dv <= val
    if op == "$gt":
        return dv > val
    if op == "$gte":
        return dv >= val
    if op == "$regex":
        return re.search(val, str(dv)) is not None
    raise AssertionError("MiniColl: unsupported operator %s" % op)


def match(doc, q):
    for k, v in (q or {}).items():
        if k == "$or":
            if not any(match(doc, sub) for sub in v):
                return False
            continue
        dv = doc.get(k)
        if isinstance(v, dict) and any(str(x).startswith("$") for x in v):
            for op, val in v.items():
                if not _cmp_ok(dv, op, val):
                    return False
        elif dv != v:
            return False
    return True


class MiniColl:
    """A small Mongo stand-in: the operators the program code uses, and
    find_one_and_update with upsert that raises DuplicateKeyError on an _id
    collision exactly like Mongo does."""

    def __init__(self, docs=None):
        self.rows = [dict(d) for d in (docs or [])]
        self.raise_on = {}

    def _maybe_raise(self, name):
        exc = self.raise_on.get(name)
        if exc is not None:
            raise exc

    def find_one(self, q=None, *a, **k):
        self._maybe_raise("find_one")
        for d in self.rows:
            if match(d, q):
                return dict(d)
        return None

    def find(self, q=None, *a, **k):
        self._maybe_raise("find")
        return MiniCursor(dict(d) for d in self.rows if match(d, q))

    def count_documents(self, q=None):
        return len(self.find(q))

    def insert_one(self, doc):
        self._maybe_raise("insert_one")
        if "_id" in doc and any(r.get("_id") == doc["_id"] for r in self.rows):
            raise DuplicateKeyError("dup _id %r" % doc["_id"])
        self.rows.append(dict(doc))

    @staticmethod
    def _apply(d, update):
        for k, v in (update.get("$set") or {}).items():
            d[k] = v
        for k, v in (update.get("$inc") or {}).items():
            d[k] = (d.get(k) or 0) + v
        for k in (update.get("$unset") or {}):
            d.pop(k, None)

    def update_one(self, q, update, upsert=False):
        self._maybe_raise("update_one")
        for d in self.rows:
            if match(d, q):
                self._apply(d, update)
                return
        if upsert:
            base = {k: v for k, v in (q or {}).items() if not isinstance(v, dict) and k != "$or"}
            base.update(update.get("$setOnInsert") or {})
            self._apply(base, update)
            self.rows.append(base)

    def replace_one(self, q, doc, upsert=False):
        for i, d in enumerate(self.rows):
            if match(d, q):
                self.rows[i] = dict(doc)
                return
        if upsert:
            self.rows.append(dict(doc))

    def find_one_and_update(self, q, update, upsert=False, **k):
        self._maybe_raise("find_one_and_update")
        for d in self.rows:
            if match(d, q):
                before = dict(d)
                self._apply(d, update)
                return before
        if upsert:
            base = {kk: v for kk, v in (q or {}).items() if not isinstance(v, dict)}
            if "_id" in base and any(r.get("_id") == base["_id"] for r in self.rows):
                raise DuplicateKeyError("E11000 duplicate key _id %r" % base["_id"])
            self._apply(base, update)
            self.rows.append(base)
        return None

    def delete_one(self, q):
        for i, d in enumerate(self.rows):
            if match(d, q):
                del self.rows[i]
                return

    def delete_many(self, q):
        self.rows = [d for d in self.rows if not match(d, q)]


class MiniDB:
    """Attribute-style DB; any collection name springs into existence (like
    pymongo). `missing` names raise AttributeError (a fake with no such coll)."""

    def __init__(self, cfg=None, missing=()):
        object.__setattr__(self, "_colls", {})
        object.__setattr__(self, "_missing", set(missing))
        self.trading_config.rows.append(dict({"_id": "config"}, **(cfg or {})))

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name in self._missing:
            raise AttributeError(name)
        colls = object.__getattribute__(self, "_colls")
        if name not in colls:
            colls[name] = MiniColl()
        return colls[name]

    def __setattr__(self, name, value):
        self._colls[name] = value

    def __getitem__(self, name):
        return getattr(self, name)


def add_program_colls(db):
    """Give an existing lane-test FakeDB the three program collections."""
    for name in (PC.PROGRAM_STATE_COLL, PC.PROGRAM_ENTRIES_COLL, PC.LOG_COLL):
        setattr(db, name, MiniColl())
    return db


def pos(sym, qty=10, avg=100.0, last=100.0, asset_class=None, mv=None):
    p = {"symbol": sym, "qty": str(qty), "avg_entry_price": str(avg),
         "current_price": str(last), "market_value": str(mv if mv is not None else qty * last)}
    if asset_class:
        p["asset_class"] = asset_class
    return p


def order(sym, side="buy", status="new", qty=10, limit=None, intent=None, legs=None,
          order_class=None, oid=None):
    o = {"id": oid or "o-%s-%s" % (sym, side), "symbol": sym, "side": side, "status": status,
         "qty": str(qty), "limit_price": (str(limit) if limit is not None else None)}
    if intent:
        o["position_intent"] = intent
    if legs is not None:
        o["legs"] = legs
    if order_class:
        o["order_class"] = order_class
    return o


def spread(occ1="AAPL261120C00200000", occ2="AAPL261120C00210000", status="new",
           intents=("buy_to_open", "sell_to_open")):
    return {"id": "mleg-1", "symbol": "", "order_class": "mleg", "status": status,
            "qty": "1", "limit_price": "2.10",
            "legs": [{"symbol": occ1, "side": "buy", "position_intent": intents[0]},
                     {"symbol": occ2, "side": "sell", "position_intent": intents[1]}]}


class CapsBroker:
    """Reads + one recorded mutation (submit_bracket)."""

    def __init__(self, positions=(), orders=(), equity=100_000.0, market_open=True,
                 mode="paper", orders_raise=False):
        self._positions = list(positions)
        self._orders = list(orders)
        self._equity = float(equity)
        self._open = bool(market_open)
        self._mode = mode
        self.orders_raise = orders_raise
        self.reads = []
        self.brackets = []

    def configured(self):
        return True

    def mode(self):
        return self._mode

    def clock(self):
        self.reads.append("clock")
        return {"is_open": self._open}

    def account(self):
        self.reads.append("account")
        return {"equity": str(self._equity), "cash": str(self._equity),
                "buying_power": str(self._equity)}

    def positions(self):
        self.reads.append("positions")
        return [dict(p) for p in self._positions]

    def open_orders(self, symbol=None):
        self.reads.append("open_orders")
        if self.orders_raise:
            raise BrokerError("alpaca GET /v2/orders -> HTTP 500")
        return [dict(o) for o in self._orders]

    def closed_orders_since(self, iso):
        return []

    def latest_trade(self, symbol):
        self.reads.append("latest_trade")
        return None

    def make_client_order_id(self, symbol, intent):
        return "cheetah-%s-20260928-%s" % (symbol, intent)

    def submit_bracket(self, symbol, qty, take_profit_price, stop_price, limit_price=None,
                       client_order_id=None, tif="gtc", order_class="bracket"):
        self.brackets.append({"symbol": symbol, "qty": qty, "stop_price": stop_price,
                              "take_profit_price": take_profit_price})
        return {"id": "bracket-%d" % len(self.brackets)}


def et(h, m, s=0, day=28):
    return datetime(2026, 9, day, h, m, s, tzinfo=ET)


@pytest.fixture
def mdb(monkeypatch):
    db = MiniDB()
    monkeypatch.setattr(EE, "_db", lambda: db)
    PC.set_tick_minute(None)
    yield db
    PC.set_tick_minute(None)


ON = {"cm_program": True}
OFF = {"cm_program": False}


def _check(tag, sym, brk, cfg=None, mode="paper", held=False, now=None, **kw):
    return PC.check(tag, sym, brk=brk, cfg=cfg if cfg is not None else OFF, mode=mode,
                    held=held, now=now or et(10, 0), **kw)


# ═════════════════════════════════════════════════════════════════════════════
# Constants
# ═════════════════════════════════════════════════════════════════════════════
def test_constants_are_his_numbers():
    assert PC.PROGRAM_RISK_PCT == 0.25
    assert PC.PER_STRATEGY_MAX_ENTRIES_PER_DAY == 1
    assert PC.PER_STRATEGY_MAX_OPEN == 2
    assert PC.PROGRAM_MAX_OPEN == 15
    assert PC.PROGRAM_MAX_GROSS_PCT == 100.0
    assert "held" not in PC.PENDING_BUY_STATUSES and "partially_filled" in PC.PENDING_BUY_STATUSES
    assert PC.OPEN_INTENTS == ("buy_to_open", "sell_to_open")
    assert not hasattr(PC, "PROGRAM_MIN_ENTRY_GAP_SEC")       # rev 1's 60-s gap is gone
    # live keeps the frozen risk_rules cap (never edited)
    assert risk_rules.MAX_POSITIONS == 5


# ═════════════════════════════════════════════════════════════════════════════
# a1 — the in-flight open cap
# ═════════════════════════════════════════════════════════════════════════════
def test_a_pending_unfilled_buy_counts_program_off(mdb):
    """NEGATIVE: 4 positions + 1 pending entry -> the 5th buy is refused with
    the program OFF (the old cap read positions only and let it through)."""
    brk = CapsBroker([pos(s) for s in ("A", "B", "C", "D")], [order("E", limit=50)])
    reasons = _check("manual", "F", brk)
    assert any(r.startswith("program-wait: portfolio full: 4 positions + 1 pending entries / 5")
               for r in reasons), reasons
    assert any("(p.312)" in r for r in reasons)            # the live cap keeps its cite
    # without the pending order it clears
    brk2 = CapsBroker([pos(s) for s in ("A", "B", "C", "D")])
    assert _check("manual", "F", brk2) == []


def test_the_16th_is_refused_with_the_program_on(mdb):
    """NEGATIVE: 14 positions (one of them an option row) + 1 pending = 15 ->
    the next is refused; 13 + 1 pending leaves the slot."""
    rows = [pos("S%d" % i) for i in range(13)] + [pos("AAPL261120C00200000", asset_class="us_option")]
    brk = CapsBroker(rows, [order("P1", limit=10)])
    r = _check("manual", "NEW", brk, cfg=ON)
    assert any("portfolio full: 14 positions + 1 pending entries / 15" in x for x in r), r
    assert not any("(p.312)" in x for x in r)              # 15 is not the book's cap
    brk2 = CapsBroker(rows[:-1], [order("P1", limit=10)])
    assert _check("manual", "NEW", brk2, cfg=ON) == []


def test_a_partially_filled_buy_of_a_held_symbol_counts_once(mdb):
    brk = CapsBroker([pos("A"), pos("B"), pos("C"), pos("D")],
                     [order("D", status="partially_filled", limit=20)])
    inf = PC.inflight(brk)
    assert inf["positions"] | inf["pending_buys"] == {"A", "B", "C", "D"}
    assert _check("manual", "E", brk) == []                # 4 names, 1 slot left


def test_sell_legs_and_held_legs_are_not_counted(mdb):
    brk = CapsBroker([pos("A")], [order("A", side="sell", status="new", intent="sell_to_close"),
                                  order("B", side="buy", status="held"),
                                  order("C", side="sell", status="held")])
    inf = PC.inflight(brk)
    assert inf["pending_buys"] == set()


def test_open_orders_unreadable_raises_and_the_caller_fails_closed(mdb):
    """NEGATIVE: the broker cannot list open orders -> inflight raises."""
    brk = CapsBroker([pos("A")], orders_raise=True)
    with pytest.raises(BrokerError):
        PC.inflight(brk)
    with pytest.raises(BrokerError):
        _check("manual", "B", brk)


def test_a_pending_buy_of_the_same_symbol_refuses_a_second(mdb):
    brk = CapsBroker([], [order("AAA", limit=10)])
    r = _check("manual", "AAA", brk)
    assert "program-wait: entry already pending for AAA" in r


def test_a_pending_spread_counts_both_legs(mdb):
    """critic 7: an open mleg spread with 2 *_to_open legs = 2 pending; 13
    positions + that spread -> the next buy is refused. A single-leg
    buy_to_open counts 1; a buy_to_close leg is NOT counted."""
    rows = [pos("S%d" % i) for i in range(13)]
    brk = CapsBroker(rows, [spread()])
    inf = PC.inflight(brk)
    assert inf["pending_buys"] == {"AAPL261120C00200000", "AAPL261120C00210000"}
    r = _check("manual", "NEW", brk, cfg=ON)
    assert any("13 positions + 2 pending entries / 15" in x for x in r), r
    single = order("MSFT261120C00400000", intent="buy_to_open", limit=3.2)
    assert PC.inflight(CapsBroker([], [single]))["pending_buys"] == {"MSFT261120C00400000"}
    closing = order("MSFT261120P00400000", intent="buy_to_close", limit=1.0)
    assert PC.inflight(CapsBroker([], [closing]))["pending_buys"] == set()
    close_spread = spread(intents=("sell_to_close", "buy_to_close"))
    assert PC.inflight(CapsBroker([], [close_spread]))["pending_buys"] == set()


def test_pending_notional_prices_stocks_and_options(mdb):
    brk = CapsBroker([pos("A", last=20.0)],
                     [order("B", qty=10, limit=5.0),
                      order("MSFT261120C00400000", qty=2, limit=3.0, intent="buy_to_open"),
                      order("A", qty=3, limit=None)])
    assert PC.inflight(brk)["pending_notional"] == pytest.approx(10 * 5.0 + 2 * 100 * 3.0 + 3 * 20.0)


def test_a_spread_takes_two_slots(mdb):
    rows = [pos("S%d" % i) for i in range(14)]
    brk = CapsBroker(rows)
    assert _check("options_zone", "X", brk, cfg=ON) == []
    assert any("portfolio full" in r for r in _check("options_zone", "X", brk, cfg=ON, adds=2))


def test_a_held_name_is_exempt_from_the_open_cap_but_not_from_one_lane_per_name(mdb):
    brk = CapsBroker([pos(s) for s in ("A", "B", "C", "D", "E")])
    assert _check("manual", "A", brk, held=True) == []     # a manual add (never average down stays in entries)
    r = _check("demand_zone", "A", brk, held=True)
    assert "program-cap: A already held (one lane per name)" in r


# ═════════════════════════════════════════════════════════════════════════════
# one lane per name (critic 5)
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("tag", ["hot_pullback", "deep_demand", "demand_zone", "breakout",
                                 "catalyst", "quick_bounce"])
def test_a_lane_never_buys_a_name_already_held(mdb, tag):
    brk = CapsBroker([pos("EMR")])
    assert "program-cap: EMR already held (one lane per name)" in _check(tag, "EMR", brk, held=True)


@pytest.mark.parametrize("tag", ["minervini", "manual"])
def test_minervini_and_manual_keep_the_add_rule(mdb, tag):
    brk = CapsBroker([pos("EMR")])
    assert not any("one lane per name" in r for r in _check(tag, "EMR", brk, held=True))


# ═════════════════════════════════════════════════════════════════════════════
# strategy_on / enabled / not-a-lane (critic 8)
# ═════════════════════════════════════════════════════════════════════════════
def test_program_off_existing_lanes_on_generic_off():
    for tag in ("zero_dte", "demand_zone", "catalyst", "breakout", "quick_bounce", "hot_pullback"):
        assert PC.strategy_on(tag, OFF, "paper") is True, tag
    assert PC.strategy_on("amd", OFF, "paper") is False            # NEGATIVE
    assert PC.strategy_on("deep_demand", {}, "paper") is False


def test_program_on_defaults_and_overrides():
    assert PC.strategy_on("amd", ON, "paper") is True
    assert PC.strategy_on("keltner", ON, "paper") is False
    assert PC.strategy_on("zero_dte", ON, "paper") is False         # signals OFF while ON
    cfg = dict(ON, cm_lanes={"amd": False, "keltner": True})
    assert PC.strategy_on("amd", cfg, "paper") is False
    assert PC.strategy_on("keltner", cfg, "paper") is True
    for tag in ("minervini", "options_zone", "manual"):
        assert PC.strategy_on(tag, cfg, "paper") is True


@pytest.mark.parametrize("tag", ["vcp", "topping", "support", "winners", "news"])
@pytest.mark.parametrize("cfg,mode", [(ON, "paper"), (OFF, "paper"), (ON, "live")])
def test_not_a_lane_is_refused_in_every_mode(mdb, tag, cfg, mode):
    assert PC.strategy_on(tag, cfg, mode) is False
    r = _check(tag, "ABC", CapsBroker(), cfg=cfg, mode=mode)
    assert r and r[0].startswith("program-cap: %s is not a lane" % tag)


def test_live_is_never_a_program(mdb):
    """NEGATIVE: live + cm_program true -> cap 5, no risk budget; the minute
    claim still applies."""
    assert PC.enabled(ON, "live") is False
    assert PC.open_cap(ON, "live") == 5 and PC.open_cap(ON, "paper") == 15
    assert PC.open_cap(ON, "sim") == 15
    assert PC.risk_budget("demand_zone", ON, "live") is None
    ok, _ = PC.claim("demand_zone", "AAA", now=et(10, 0))
    ok2, why = PC.claim("minervini", "BBB", now=et(10, 0, 30))
    assert ok is True and ok2 is False and "one entry per minute" in why


def test_a_sid_switched_off_is_a_day_cap(mdb):
    cfg = dict(ON, cm_lanes={"deep_demand": False})
    r = _check("deep_demand", "AAA", CapsBroker(), cfg=cfg)
    assert "program-cap: deep_demand is OFF" in r


def test_a_generic_tag_is_refused_while_the_program_is_off(mdb):
    """A generic lane can never buy while the switch is OFF, even called
    directly (belt and braces on top of the dispatcher never running it)."""
    assert "program-cap: amd is OFF" in _check("amd", "AAA", CapsBroker(), cfg=OFF)


# ═════════════════════════════════════════════════════════════════════════════
# normalisation (critic 1)
# ═════════════════════════════════════════════════════════════════════════════
def test_a_legacy_tag_hits_the_sid_daily_cap(mdb):
    """NEGATIVE: a recorded demand_zone entry, then a 2nd demand_zone entry
    the same day -> refused under the zones sid."""
    PC.record_entry("demand_zone", "AAA", now=et(9, 45))
    r = _check("demand_zone", "BBB", CapsBroker(), cfg=ON, now=et(11, 0))
    assert "program-cap: zones daily cap 1 reached" in r
    # tomorrow it clears
    assert not any("daily cap" in x for x in _check("demand_zone", "BBB", CapsBroker(), cfg=ON,
                                                     now=et(11, 0, day=29)))


@pytest.mark.parametrize("tag", ["demand_zone", "breakout", "catalyst", "quick_bounce",
                                 "hot_pullback", "amd", "deep_demand"])
def test_every_roster_stock_tag_is_sized_at_quarter_percent(tag):
    assert PC.risk_budget(tag, ON, "paper") == 0.25
    assert PC.risk_budget(tag, OFF, "paper") is None


def test_non_roster_and_options_tags_have_no_stock_risk_budget():
    for tag in ("minervini", "manual", "options_zone", "zero_dte"):
        assert PC.risk_budget(tag, ON, "paper") is None


def test_record_entry_normalises_the_sid_and_keeps_the_tag(mdb):
    PC.record_entry("breakout", "LNG", order_id="o1", client_order_id="c1", now=et(9, 31))
    doc = mdb.program_entries.rows[0]
    assert doc["sid"] == "breaking" and doc["tag"] == "breakout"
    assert doc["day"] == "2026-09-28" and doc["symbol"] == "LNG"
    PC.record_entry("catalyst", "EOSE", now=et(9, 40))
    assert mdb.program_entries.rows[1]["sid"] == "catalysts"


def test_a_third_open_breakout_waits(mdb):
    """NEGATIVE: two breaking entries still open -> the 3rd waits."""
    PC.record_entry("breakout", "AAA", now=et(9, 31, day=24))
    PC.record_entry("breakout", "BBB", now=et(9, 31, day=25))
    brk = CapsBroker([pos("AAA"), pos("BBB")])
    r = _check("breakout", "CCC", brk, cfg=ON)
    assert "program-wait: breaking 2 open (max 2)" in r
    # a closed one no longer counts
    brk2 = CapsBroker([pos("AAA")])
    assert not any("open (max" in x for x in _check("breakout", "CCC", brk2, cfg=ON))


def test_an_open_name_belongs_to_its_latest_program_entry(mdb):
    PC.record_entry("breakout", "AAA", now=et(9, 31, day=21))       # old, closed since
    PC.record_entry("amd", "AAA", now=et(9, 31, day=25))            # current holder
    assert PC.open_by_sid({"AAA"}) == {"amd": 1}


def test_tighten_only_caps_bind(mdb):
    cfg = dict(ON, cm_lane_caps={"amd": {"per_day": 0}})
    assert "program-cap: amd daily cap 0 reached" in _check("amd", "X", CapsBroker(), cfg=cfg)


# ═════════════════════════════════════════════════════════════════════════════
# the minute clock (critics 3 + 4)
# ═════════════════════════════════════════════════════════════════════════════
def test_critic_4_the_minute_bucket(mdb):
    ok1, _ = PC.claim("amd", "AAA", now=et(9, 31, 45))
    ok2, _ = PC.claim("deep_demand", "BBB", now=et(9, 32, 2))       # a new minute
    ok3, why = PC.claim("growth", "CCC", now=et(9, 32, 50))         # same minute: refused
    assert (ok1, ok2, ok3) == (True, True, False)
    assert why == "program-wait: one entry per minute (taken by deep_demand BBB at 09:32:02 ET)"
    assert PC.is_transient(why)


def test_an_older_minute_can_never_claim_after_a_newer_one(mdb):
    assert PC.claim("amd", "AAA", now=et(9, 33, 1))[0] is True
    ok, why = PC.claim("zones", "BBB", now=et(9, 32, 59))
    assert ok is False and "one entry per minute" in why


def test_manual_is_exempt_from_the_claim(mdb):
    assert PC.claim("amd", "AAA", now=et(9, 33, 1))[0] is True
    assert PC.claim("manual", "BBB", now=et(9, 33, 5)) == (True, None)


def test_a_duplicate_key_or_any_mongo_error_refuses(mdb):
    """NEGATIVE: DuplicateKeyError -> refused with who took it; any other
    Mongo error -> refused, clock unreadable (fails closed)."""
    mdb.program_state.raise_on["find_one_and_update"] = DuplicateKeyError("E11000")
    ok, why = PC.claim("amd", "AAA", now=et(10, 0))
    assert ok is False and why.startswith("program-wait: one entry per minute")
    mdb.program_state.raise_on["find_one_and_update"] = RuntimeError("socket closed")
    ok, why = PC.claim("amd", "AAA", now=et(10, 1))
    assert (ok, why) == (False, "program-wait: entry clock unreadable")


def test_no_mongo_refuses_the_claim_and_the_peek_reads_taken(monkeypatch):
    monkeypatch.setattr(EE, "_db", lambda: None)
    assert PC.claim("amd", "AAA") == (False, "program-wait: entry clock unreadable")
    assert PC.minute_taken().get("error")
    assert PC.minute_taken_reason(PC.minute_taken()) == "program-wait: entry clock unreadable"


def test_two_racers_on_one_atomic_collection_exactly_one_wins(mdb):
    results = [PC.claim("amd", "AAA", now=et(10, 5, 1)), PC.claim("zones", "BBB", now=et(10, 5, 1))]
    assert sorted(r[0] for r in results) == [False, True]


def test_set_tick_minute_pins_the_key(mdb):
    PC.set_tick_minute(et(9, 45, 58))
    assert PC.minute_key() == "2026-09-28T09:45"
    assert PC.minute_key(et(9, 50)) == "2026-09-28T09:50"      # an explicit now still wins
    PC.set_tick_minute(None)
    assert PC.minute_key(et(9, 51, 10)) == "2026-09-28T09:51"


def test_the_peek_sees_the_minute_and_a_newer_one(mdb):
    assert PC.minute_taken(et(10, 0)) is None
    PC.claim("amd", "AAA", now=et(10, 0, 20))
    t = PC.minute_taken(et(10, 0, 40))
    assert t["sid"] == "amd" and t["symbol"] == "AAA"
    assert PC.minute_taken(et(9, 59)) is not None                  # a newer minute is taken too
    assert PC.minute_taken(et(10, 1)) is None
    assert any("one entry per minute" in r
               for r in _check("zones", "BBB", CapsBroker(), now=et(10, 0, 50)))
    assert not any("one entry per minute" in r
                   for r in _check("manual", "BBB", CapsBroker(), now=et(10, 0, 50)))


# ═════════════════════════════════════════════════════════════════════════════
# gross, option risk, log, priority, validation, status
# ═════════════════════════════════════════════════════════════════════════════
def test_gross_cap_only_while_on():
    positions = [pos("A", qty=100, last=500.0)]                  # $50k
    ok, why = PC.gross_ok(positions=positions, pending_notional=30_000, add_usd=25_000,
                          equity_used=100_000, cfg=ON, mode="paper")
    assert ok is False and "program-wait: program gross" in why
    assert PC.gross_ok(positions=positions, pending_notional=0, add_usd=25_000,
                       equity_used=100_000, cfg=ON, mode="paper") == (True, None)
    assert PC.gross_ok(positions=positions, pending_notional=90_000, add_usd=90_000,
                       equity_used=100_000, cfg=OFF, mode="paper") == (True, None)


def test_option_risk_pct_is_min_composed_only_while_on():
    assert PC.option_risk_pct("options_zone", 1.0, ON, "paper") == 0.25
    assert PC.option_risk_pct("options_zone", 1.0, OFF, "paper") == 1.0
    assert PC.option_risk_pct("options_zone", 0.1, ON, "paper") == 0.1


def test_log_skip_dedupes_per_day_and_counts(mdb):
    for _ in range(3):
        PC.log_skip("demand_zone", "*", "program-cap: zones daily cap 1 reached", now=et(10, 0))
    PC.log_skip("amd", "ABC", "live read blocked: room", now=et(10, 1))
    rows = {r["_id"]: r for r in mdb.cm_lane_log.rows}
    k = "2026-09-28:zones:*:program-cap: zones daily cap 1 reached"
    assert rows[k]["count"] == 3 and rows[k]["sid"] == "zones"
    assert len(rows) == 2


def test_usage_rank_tie_and_uncounted_order():
    counts, seen = ST.frozen_counts()
    order = ST.usage_rank(counts, seen)
    assert order.index("bonde") < order.index("hot_pullback")          # 69/69, same last_seen
    assert order.index("potus") < order.index("gabbar")                # 17/17, potus newer
    assert order[:3] == ["zones", "deep_demand", "hot_sectors"]
    only = ST.usage_rank({"amd": 3}, {})
    assert only[0] == "amd" and only[1:] == [s for s in ST.lane_sids() if s != "amd"]


def test_priority_order_falls_back_to_frozen_on_an_empty_read(mdb, monkeypatch):
    """NEGATIVE: usage_stats empty/unreadable -> the frozen 2026-09-27 order."""
    import usage
    monkeypatch.setattr(usage, "feature_counts", lambda top=50: [])
    out = PC.priority_order(et(9, 0))
    assert out["source"] == "frozen"
    assert out["order"] == ST.usage_rank(*ST.frozen_counts())
    assert mdb.program_state.find_one({"_id": PC.USAGE_ORDER_ID}) is None   # frozen is not cached


def test_priority_order_reads_usage_once_per_day(mdb, monkeypatch):
    import usage
    calls = []

    def fc(top=50):
        calls.append(top)
        return [{"key": "chart-maps:tab:amd", "count": 900, "last_seen": 1},
                {"key": "chart-maps:tab:zero_dte", "count": 5, "last_seen": 1},
                {"key": "page:/trading", "count": 99999}]

    monkeypatch.setattr(usage, "feature_counts", fc)
    a = PC.priority_order(et(9, 0))
    b = PC.priority_order(et(15, 0))
    assert a["order"][0] == "amd" and a["source"] == "usage_stats" and b == a
    assert calls == [100]
    assert a["counts"]["signals"] == 5
    c = PC.priority_order(et(9, 0, day=29))                        # a new ET day re-reads
    assert len(calls) == 2 and c["day"] == "2026-09-29"


def test_validate_updates():
    cur = {"cm_lanes": {"amd": True}, "cm_lane_caps": {}}
    out = PC.validate_updates({"cm_program": True}, {})
    assert out["cm_program"] is True and out["cm_program_started"]
    assert "cm_program_started" not in PC.validate_updates({"cm_program": True},
                                                           {"cm_program_started": "2026-09-28"})
    assert PC.validate_updates({"cm_program": None}, {}) == {"cm_program": False}
    assert PC.validate_updates({"cm_lanes": {"demand_zone": False}}, cur)["cm_lanes"] == \
        {"amd": True, "zones": False}                                # legacy tag normalised
    assert PC.validate_updates({"cm_lanes": {"amd": None}}, cur)["cm_lanes"] == {}   # null resets
    assert PC.validate_updates({"cm_lane_caps": {"amd": {"per_day": 0, "max_open": 1}}},
                               cur)["cm_lane_caps"] == {"amd": {"per_day": 0, "max_open": 1}}
    # NEGATIVES
    for bad in ({"cm_lanes": {"nope": True}}, {"cm_lanes": {"vcp": True}},
                {"cm_lanes": {"minervini": True}}, {"cm_lanes": {"amd": "yes"}},
                {"cm_lanes": "all"}, {"cm_program": "on"},
                {"cm_lane_caps": {"amd": {"per_day": 2}}},             # above the default
                {"cm_lane_caps": {"amd": {"max_open": 3}}},
                {"cm_lane_caps": {"amd": {"per_day": True}}},
                {"cm_lane_caps": {"amd": {"typo": 1}}},
                {"cm_lane_caps": {"topping": {"per_day": 0}}}):
        with pytest.raises(ValueError):
            PC.validate_updates(bad, cur)


def test_rules_list_is_built_from_the_constants():
    text = " ".join(PC.rules_list())
    for token in ("0.25%", "1 new buy a day and 2 open", "At most 15 open",
                  "Live stays at 5", "One new entry per minute", "One lane per name",
                  "UNMEASURED"):
        assert token in text, token
    assert "bounce" not in text.lower()


def test_status_block_shapes(mdb):
    PC.claim("amd", "AAA", now=et(10, 0, 20))
    PC.record_entry("amd", "AAA", now=et(10, 0, 20))
    brk = CapsBroker([pos("AAA")], [order("BBB", limit=5)])
    blk = PC.status_block(ON, "paper", brk)
    assert blk["enabled"] is True and blk["caps"]["max_open"] == 15
    assert blk["minute"]["sid"] == "amd" and blk["last_entry"]["symbol"] == "AAA"
    assert blk["open"] == {"n": 2, "positions": 1, "pending": 1, "by_sid": {"amd": 1}}
    live = PC.status_block(ON, "live", None)
    assert live["enabled"] is False and live["caps"]["max_open"] == 5 and live["open"] is None


def test_no_order_tokens_in_the_chokepoint():
    src = open(PC.__file__, encoding="utf-8").read()
    assert "submit_" not in src and "close_position" not in src and "cancel_order" not in src
