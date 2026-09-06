"""Zone-edge entry behavior — fake broker + fake Mongo, no network, no zones
computed (docs/supply_demand/zone_edge_autopilot.md).

Locks trading/zone_edge_entry.py:

  Gates     flag off / disarmed / not configured / market closed -> no-op
            with ONE zone_entry_disabled ledger row per ET day; stale or
            wrong-day board doc -> nothing; at/after 15:45 ET -> nothing.
  Funnel    demand ARRIVALS (tier near/in, arrival=true) and BREAKOUTS
            (tier broke + new_highs) only; touches >= 2, cap >= $1B; a
            'near' resistance row or a resident demand row is never bought.
  Stops     band.lo x (1 - 0.5%) as the REQUESTED stop, handed to entries
            as the ABSOLUTE level (placed there whatever the order-time
            print; refused when drift makes it too wide); wider than the
            10% line -> blocked + recorded; room < 2R to the first band
            overhead (supply at/above, or broken demand above) -> blocked;
            inside a supply band -> blocked; unknown zone doc -> blocked
            (fails closed).
  Attempts  one per (symbol, band, ET day), recorded BEFORE entries.enter;
            blocked/error attempts recorded too; 'market closed' is not.
  Race      one execution_race doc per attempt (blocked included);
            reconcile_race stamps engine fill / owner view / owner fill and
            race_report computes the lags + medians (JSON-safe).
  Buys      ONLY via entries.enter (recorder here; the no-direct-submit
            invariant is in tests/test_trading_contracts.py).

Host-runnable (py3.9, no pandas/numpy):
    cd backend && .venv/bin/python -m pytest tests/test_zone_edge_entry.py -q
"""
import asyncio
import json
import math
import os
import sys
import types
from datetime import date, datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.entries as EN
import trading.exit_engine as EE
import trading.zone_edge_entry as ZE
from trading.risk_rules import ABS_MAX_STOP_PCT, MAX_POSITIONS, MIN_REWARD_RISK

ET = ZoneInfo("America/New_York")
DAY = EE._et_day()
NOW = datetime.combine(date.fromisoformat(DAY), dtime(10, 30), tzinfo=ET)
OWNER = "owner@example.com"


# ── Fakes (pattern: tests/test_auto_entry.py, + $gt/$in + delete_many) ──────

class FakeCursor(list):
    def sort(self, key=None, direction=1, *a, **k):
        if isinstance(key, str):
            rows = sorted(self, key=lambda d: d.get(key) or 0,
                          reverse=(direction == -1))
            return FakeCursor(rows)
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
                dv = doc.get(k)
                if "$in" in v and dv not in v["$in"]:
                    return False
                if "$ne" in v and dv == v["$ne"]:
                    return False
                if "$gt" in v and not (dv is not None and dv > v["$gt"]):
                    return False
                if "$gte" in v and not (dv is not None and dv >= v["$gte"]):
                    return False
                if "$lt" in v and not (dv is not None and dv < v["$lt"]):
                    return False
                if "$lte" in v and not (dv is not None and dv <= v["$lte"]):
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

    def insert_many(self, docs):
        for d in docs:
            self.rows.append(dict(d))

    def update_one(self, q, update, upsert=False):
        for d in self.rows:
            if self._match(d, q):
                d.update(update.get("$set") or {})
                return
        if upsert:
            base = {k: v for k, v in (q or {}).items() if not isinstance(v, dict)}
            base.update(update.get("$set") or {})
            self.rows.append(base)

    def replace_one(self, q, doc, upsert=False):
        for i, d in enumerate(self.rows):
            if self._match(d, q):
                self.rows[i] = dict(doc)
                return
        if upsert:
            self.rows.append(dict(doc))

    def delete_many(self, q):
        self.rows = [d for d in self.rows if not self._match(d, q)]


class FakeDB:
    def __init__(self, armed=True, flag=True, equity_cap=100_000.0):
        self.trading_config = FakeColl([{
            "_id": "config", "armed": armed, "zone_edge_entry": flag,
            "auto_entry": False, "consecutive_losses": 0,
            "processed_order_ids": [], "equity_cap": equity_cap,
            "progressive_exposure": False,
        }])
        self.trade_ledger = FakeColl()
        self.auto_entry_state = FakeColl()
        self.zone_edge_entry_state = FakeColl()
        self.execution_race = FakeColl()
        self.zone_edge_latest = FakeColl()
        self.zone_edge_track = FakeColl()
        self.usage_events = FakeColl()
        self.portfolio_holdings = FakeColl()


class FakeBroker:
    """Reads only — zone_edge_entry must never need a mutation method; any
    submit_*/replace/cancel attempt raises AttributeError and surfaces as a
    run() error."""

    def __init__(self, positions=(), market_open=True, configured=True,
                 closed_orders=(), mode="paper"):
        self._positions = list(positions)
        self._market_open = bool(market_open)
        self._configured = bool(configured)
        self._closed = list(closed_orders)
        self._mode = mode
        self.closed_calls = 0

    def configured(self):
        return self._configured

    def clock(self):
        return {"is_open": self._market_open}

    def mode(self):
        return self._mode

    def account(self):
        return {"equity": "100000", "cash": "100000", "buying_power": "100000"}

    def positions(self):
        return [dict(p) for p in self._positions]

    def open_orders(self, symbol=None):
        return []

    def closed_orders_since(self, iso_ts):
        self.closed_calls += 1
        return [dict(o) for o in self._closed]

    def latest_trade(self, symbol):
        return None

    def make_client_order_id(self, symbol, intent):
        return "cheetah-%s-%s-%s" % (symbol, DAY.replace("-", ""), intent)


def _position(symbol, qty=10, avg_entry=100.0, last=110.0):
    return {"symbol": symbol, "qty": str(qty),
            "avg_entry_price": str(avg_entry), "current_price": str(last)}


# ── Board row / doc builders ────────────────────────────────────────────────

def demand_row(sym="AAA", last=100.0, lo=98.0, hi=99.5, touches=3, cap=5e9,
               tier="near", arrival=True, dist_pct=0.5, first_seen="10:12",
               side="demand", role="demand", **extra):
    row = {"symbol": sym, "name": sym + " Inc", "last": last, "dist_pct": dist_pct,
           "tier": tier, "side": side, "role": role,
           "band": {"kind": "demand", "lo": lo, "hi": hi, "touches": touches,
                    "strength": 1.5},
           "cap": cap, "new_highs": None, "high_252": None, "pct_to_52w": None,
           "overhead_bands": None, "arrival": arrival, "first_seen": first_seen,
           "url": "/sepa/%s?tab=supply" % sym}
    row.update(extra)
    return row


def break_row(sym="BBB", last=105.0, lo=100.0, hi=103.0, touches=3, cap=5e9,
              tier="broke", new_highs=True, overhead=0, dist_pct=-1.9,
              first_seen="10:05", side="supply", role="resistance", **extra):
    row = {"symbol": sym, "name": sym + " Corp", "last": last, "dist_pct": dist_pct,
           "tier": tier, "side": side, "role": role,
           "band": {"kind": "supply", "lo": lo, "hi": hi, "touches": touches,
                    "strength": 2.0},
           "cap": cap, "new_highs": new_highs, "high_252": 104.0, "pct_to_52w": 1.0,
           "overhead_bands": overhead, "arrival": None, "first_seen": first_seen,
           "url": "/sepa/%s?tab=supply" % sym}
    row.update(extra)
    return row


def latest_doc(breaking=(), near_demand=(), as_of=None, day=None):
    return {"_id": "latest",
            "as_of": (as_of if as_of is not None else NOW.isoformat()),
            "date": day or DAY, "in_session": True,
            "counts": {"breaking": len(breaking), "near_demand": len(near_demand)},
            "breaking": list(breaking), "near_demand": list(near_demand)}


def zone_doc(sym, supply_los=(), demand_bands=()):
    bands = [{"kind": "supply", "lo": lo, "hi": lo + 2.0, "touches": 2,
              "strength": 50.0} for lo in supply_los]          # proven lids (2026-09-06 rule)
    bands += [{"kind": "demand", "lo": lo, "hi": hi, "touches": 2,
               "strength": 50.0} for lo, hi in demand_bands]
    return {"_id": "%s:%s" % (sym, DAY), "symbol": sym, "date": DAY,
            "bands": bands, "prev_close": 99.0, "high_252": 104.0}


@pytest.fixture
def env(monkeypatch):
    """Wire zone_edge_entry's seams; returns (broker, db, enter_calls, pushes,
    zone_reads)."""

    def build(latest=None, positions=(), armed=True, flag=True,
              market_open=True, configured=True, now=NOW, zones=None,
              enter_result=None, enter_raises=None, closed_orders=(),
              mode="paper", real_enter=False, live_price=None):
        """real_enter=True leaves entries.enter UNPATCHED and wires its own
        seams instead (live print = `live_price`, no earnings, normal regime,
        no closed-trade history) so a test can watch the REAL stop math run
        on a print that drifted away from the board's signal print. The
        broker then records submit_bracket calls in `fake.brackets`."""
        fake = (BracketBroker if real_enter else FakeBroker)(
            positions, market_open, configured, closed_orders, mode)
        db = FakeDB(armed=armed, flag=flag)
        if latest is not None:
            db.zone_edge_latest.insert_one(latest)
        enter_calls, pushes, zone_reads = [], [], []
        zones = zones or {}

        def fake_enter(symbol, limit_price=None, stop_pct=None,
                       allow_earnings=False, top_up=False, stop_price=None,
                       strategy="manual", reason=None):
            enter_calls.append({"symbol": symbol, "limit_price": limit_price,
                                "stop_pct": stop_pct, "stop_price": stop_price,
                                "allow_earnings": allow_earnings,
                                "top_up": top_up, "strategy": strategy,
                                "reason": reason})
            if enter_raises:
                raise enter_raises
            res = enter_result or {"order_id": "o-%d" % len(enter_calls),
                                   "shares": 12,
                                   "stop": {"stop_pct": stop_pct,
                                            "stop_price": 97.51,
                                            "basis": "requested"}}
            # entries.enter ledgers an 'entry' row carrying the ids.
            EE.ledger("entry", symbol=symbol,
                      detail={"order_id": res["order_id"],
                              "client_order_id": "coid-%s" % symbol,
                              "price": 100.0})
            return res

        def fake_zone_doc(sym, day):
            zone_reads.append(sym)
            return zones.get(sym)

        monkeypatch.setattr(EE, "_db", lambda: db)
        monkeypatch.setattr(EN, "_db", lambda: db)
        monkeypatch.setattr(ZE, "_db", lambda: db)
        monkeypatch.setattr(ZE, "broker", fake)
        monkeypatch.setattr(EE, "broker", fake)
        monkeypatch.setattr(EN, "broker", fake)
        monkeypatch.setattr(ZE, "_now_et", lambda: now)
        monkeypatch.setattr(ZE, "_zone_doc", fake_zone_doc)
        monkeypatch.setattr(ZE, "_owner_email", lambda: OWNER)
        monkeypatch.setattr(ZE, "_notify",
                            lambda sym, side, mode_word, body:
                            pushes.append((sym, side, mode_word, body)))
        if real_enter:
            monkeypatch.setattr(EN, "_live_price",
                                lambda sym: (live_price, "test-tape"))
            monkeypatch.setattr(EN, "_closed_trade_stats", lambda: (None, 0))
            monkeypatch.setattr(EN, "regime", lambda: "normal")
            stub = types.ModuleType("sepa.earnings_watch")
            stub.next_event = lambda s: None
            monkeypatch.setitem(sys.modules, "sepa.earnings_watch", stub)
        else:
            monkeypatch.setattr(ZE.entries, "enter", fake_enter)
        return fake, db, enter_calls, pushes, zone_reads

    return build


class BracketBroker(FakeBroker):
    """FakeBroker + the ONE mutation entries.enter needs (submit_bracket),
    recorded — used only by the real_enter tests."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.brackets = []

    def submit_bracket(self, symbol, qty, take_profit_price, stop_price,
                       limit_price=None, client_order_id=None):
        self.brackets.append({"symbol": symbol, "qty": qty,
                              "take_profit_price": take_profit_price,
                              "stop_price": stop_price, "limit_price": limit_price,
                              "client_order_id": client_order_id})
        return {"id": "brk-%d" % len(self.brackets)}


def _kind_rows(db, kind):
    return [r for r in db.trade_ledger.rows if r.get("kind") == kind]


def _state_rows(db):
    return db.zone_edge_entry_state.rows


def _race_rows(db):
    return db.execution_race.rows


def _expected_stop_pct(last, lo):
    stop = round(lo * (1 - ZE.STOP_BUFFER_PCT / 100.0), 4)
    return round((last - stop) / last * 100.0, 2)


# ── Gates ────────────────────────────────────────────────────────────────────

def test_flag_off_noops_with_single_daily_disabled_ledger(env):
    """zone_edge_entry=false -> no-op; exactly ONE zone_entry_disabled ledger
    row per ET day no matter how many ticks; nothing evaluated, no state,
    no race doc."""
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()]), flag=False,
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    out1 = ZE.run()
    out2 = ZE.run()
    assert out1["ran"] is False and out1["reason"] == "gated"
    assert out2["ran"] is False
    assert out1["gate"]["zone_edge_entry"] is False
    assert enter_calls == []
    assert len(_kind_rows(db, "zone_entry_disabled")) == 1
    assert _kind_rows(db, "zone_entry_disabled")[0]["dry_run"] is False
    assert _state_rows(db) == [] and _race_rows(db) == []


def test_disarmed_places_no_orders(env):
    """armed=false NEVER places orders (house invariant) — refused before any
    candidate is evaluated, even with the zone flag on."""
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()]), armed=False,
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    out = ZE.run()
    assert out["ran"] is False and out["gate"]["armed"] is False
    assert enter_calls == []
    assert _kind_rows(db, "zone_entry") == []
    assert _state_rows(db) == [] and _race_rows(db) == []


def test_not_configured_and_market_closed_are_gated(env):
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()]), configured=False)
    assert ZE.run()["ran"] is False
    _, db2, enter_calls2, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()]), market_open=False)
    out = ZE.run()
    assert out["ran"] is False and out["gate"]["market_open"] is False
    assert enter_calls == [] and enter_calls2 == []


def test_stale_signal_places_nothing(env):
    """A latest doc older than SIGNAL_MAX_AGE_SEC, without as_of, or from
    another day places NOTHING (fails closed) — a dead board cron must never
    turn into trades off old prints."""
    old = (NOW - timedelta(seconds=ZE.SIGNAL_MAX_AGE_SEC + 30)).isoformat()
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()], as_of=old),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    out = ZE.run()
    assert out["ran"] is True and out["reason"] == "stale_signal"
    assert out["signal"]["fresh"] is False and "stale" in out["signal"]["reason"]
    assert enter_calls == [] and _state_rows(db) == [] and _race_rows(db) == []

    _, _, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()], as_of=""))
    assert ZE.run()["reason"] == "stale_signal" and enter_calls == []

    yesterday = (date.fromisoformat(DAY) - timedelta(days=1)).isoformat()
    _, _, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()], day=yesterday))
    out = ZE.run()
    assert out["reason"] == "stale_signal" and enter_calls == []

    _, _, enter_calls, _, _ = env(latest=None)
    out = ZE.run()
    assert out["reason"] == "stale_signal" and enter_calls == []


def test_fresh_signal_inside_max_age_is_accepted(env):
    recent = (NOW - timedelta(seconds=ZE.SIGNAL_MAX_AGE_SEC - 10)).isoformat()
    _, _, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()], as_of=recent),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    out = ZE.run()
    assert out["signal"]["fresh"] is True
    assert [c["symbol"] for c in enter_calls] == ["AAA"]


def test_after_last_entry_time_places_nothing(env):
    """No NEW entries at/after 15:45 ET; the 15:44 tick still can."""
    late = datetime.combine(date.fromisoformat(DAY), ZE.LAST_ENTRY_ET, tzinfo=ET)
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()], as_of=late.isoformat()),
        now=late, zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    out = ZE.run()
    assert out["reason"] == "after_last_entry_time" and enter_calls == []
    assert _state_rows(db) == [] and _race_rows(db) == []

    early = late - timedelta(minutes=1)
    _, _, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()], as_of=early.isoformat()),
        now=early, zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    ZE.run()
    assert [c["symbol"] for c in enter_calls] == ["AAA"]


# ── Funnel negatives ─────────────────────────────────────────────────────────

def _assert_never(db, enter_calls):
    assert enter_calls == []
    assert _state_rows(db) == [] and _race_rows(db) == []
    assert _kind_rows(db, "zone_entry") == []
    assert _kind_rows(db, "zone_entry_blocked") == []


def test_near_resistance_row_never_bought(env):
    """A 'near' supply row is NOT through the ceiling — never a buy."""
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(breaking=[break_row(tier="near", dist_pct=0.4)]),
        zones={"BBB": zone_doc("BBB")})
    out = ZE.run()
    assert out["reason"] == "no_candidates" and out["rejected"] == 1
    _assert_never(db, enter_calls)


def test_broke_without_new_highs_never_bought(env):
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(breaking=[break_row(new_highs=False, overhead=2)]),
        zones={"BBB": zone_doc("BBB")})
    ZE.run()
    _assert_never(db, enter_calls)
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(breaking=[break_row(new_highs=None)]))
    ZE.run()
    _assert_never(db, enter_calls)


def test_touches_below_min_never_bought(env):
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(breaking=[break_row(touches=1)],
                          near_demand=[demand_row(touches=1)]),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,)), "BBB": zone_doc("BBB")})
    out = ZE.run()
    assert out["rejected"] == 2
    _assert_never(db, enter_calls)
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row(touches=None)]))
    ZE.run()
    _assert_never(db, enter_calls)


def test_cap_below_floor_or_unknown_never_bought(env):
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(breaking=[break_row(cap=9.9e8)],
                          near_demand=[demand_row(cap=None)]),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,)), "BBB": zone_doc("BBB")})
    out = ZE.run()
    assert out["rejected"] == 2
    _assert_never(db, enter_calls)


def test_resident_demand_row_never_bought(env):
    """arrival=False (a name that has SAT in the band) and arrival missing
    both fail closed."""
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row(arrival=False),
                                       demand_row(sym="CCC", arrival=None)]),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,)),
               "CCC": zone_doc("CCC", supply_los=(120.0,))})
    out = ZE.run()
    assert out["rejected"] == 2
    _assert_never(db, enter_calls)


def test_wrong_tier_and_missing_print_or_band_never_bought(env):
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row(tier="broke"),
                                       demand_row(sym="CCC", last=None),
                                       demand_row(sym="DDD", lo=None)]))
    out = ZE.run()
    assert out["rejected"] == 3
    _assert_never(db, enter_calls)


# ── Stop + room gates (blocked attempts: recorded, never retried) ───────────

def test_stop_wider_than_book_max_blocked_and_recorded(env):
    """band floor 15% under the print -> requested stop > 10% -> blocked,
    attempt recorded (state + race outcome 'blocked' + one ledger row),
    and the second tick does NOT retry."""
    row = demand_row(last=100.0, lo=85.0, hi=86.0, tier="near", dist_pct=14.0)
    _, db, enter_calls, _, zone_reads = env(
        latest=latest_doc(near_demand=[row]),
        zones={"AAA": zone_doc("AAA", supply_los=(150.0,))})
    out = ZE.run()
    assert enter_calls == []
    assert out["blocked"] == ["AAA"]
    assert zone_reads == []                        # stop gate fires first
    st = _state_rows(db)
    assert len(st) == 1 and st[0]["attempted"] is True and st[0]["entered"] is False
    assert st[0]["result"] == "blocked" and "stop wider" in st[0]["reason"]
    assert st[0]["stop_pct"] > ABS_MAX_STOP_PCT
    race = _race_rows(db)
    assert len(race) == 1 and race[0]["outcome"] == "blocked"
    assert "stop wider" in race[0]["reason"]
    assert race[0]["engine_order_ts"] is None
    blocked = _kind_rows(db, "zone_entry_blocked")
    assert len(blocked) == 1 and blocked[0]["dry_run"] is True
    out2 = ZE.run()
    assert enter_calls == [] and len(_kind_rows(db, "zone_entry_blocked")) == 1
    assert out2["skipped"] == [{"symbol": "AAA", "reason": "attempted today (same band)"}]


def test_room_below_2r_blocked(env):
    """AAA: last 100, band lo 95 -> stop 94.525 (5.48%) -> needs 10.95% room;
    nearest supply floor at 106 (6%, past the 5% alert gate) -> blocked
    'room < 2R'. (Geometry widened 2026-09-05: the alert gate's 5% floor now
    runs first, so the 2R block needs a wider requested stop to show.)"""
    _, db, enter_calls, _, zone_reads = env(
        latest=latest_doc(near_demand=[demand_row(lo=95.0)]),
        zones={"AAA": zone_doc("AAA", supply_los=(106.0, 130.0))})
    out = ZE.run()
    assert enter_calls == [] and out["blocked"] == ["AAA"]
    assert zone_reads == ["AAA"]                   # ONE read, this candidate
    st = _state_rows(db)[0]
    assert st["result"] == "blocked" and st["reason"].startswith("room < %gR" % MIN_REWARD_RISK)
    race = _race_rows(db)[0]
    assert race["outcome"] == "blocked" and "room <" in race["reason"]
    blk = _kind_rows(db, "zone_entry_blocked")[0]["detail"]
    assert blk["room"]["next_band"] == {"kind": "supply", "lo": 106.0, "hi": 108.0}
    assert blk["room"]["room_pct"] == pytest.approx(6.0)
    assert blk["room"]["need_pct"] == pytest.approx(MIN_REWARD_RISK * _expected_stop_pct(100.0, 95.0))


def test_room_unknown_without_zone_doc_blocked(env):
    """No zone_store doc for the symbol -> room unknown -> fails CLOSED."""
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()]), zones={})
    out = ZE.run()
    assert enter_calls == [] and out["blocked"] == ["AAA"]
    assert "room unknown" in _state_rows(db)[0]["reason"]
    assert _race_rows(db)[0]["outcome"] == "blocked"


def test_room_with_no_supply_overhead_passes(env):
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()]),
        zones={"AAA": zone_doc("AAA", supply_los=(), demand_bands=((90.0, 92.0),))})
    ZE.run()
    assert [c["symbol"] for c in enter_calls] == ["AAA"]
    assert _kind_rows(db, "zone_entry")[0]["detail"]["room"]["reason"] == "no band overhead"


def test_breakout_to_new_highs_without_overhead_skips_room_check(env):
    """new_highs + overhead_bands 0 -> no zone_store read at all."""
    _, db, enter_calls, _, zone_reads = env(
        latest=latest_doc(breaking=[break_row(overhead=0)]), zones={})
    ZE.run()
    assert [c["symbol"] for c in enter_calls] == ["BBB"]
    assert zone_reads == []
    assert "skipped" in _kind_rows(db, "zone_entry")[0]["detail"]["room"]["reason"]


def test_breakout_with_overhead_still_needs_room(env):
    """new_highs via the 52w tolerance but a supply band still overhead ->
    the room check applies (and fails closed without a zone doc)."""
    row = break_row(overhead=1)
    _, db, enter_calls, _, zone_reads = env(
        latest=latest_doc(breaking=[row]),
        zones={"BBB": zone_doc("BBB", supply_los=(110.5,))})   # 5.2% room: past the 5% alert gate, under 2R
    out = ZE.run()
    assert enter_calls == [] and out["blocked"] == ["BBB"]
    assert zone_reads == ["BBB"]
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(breaking=[break_row(overhead=1)]),
        zones={"BBB": zone_doc("BBB", supply_los=(130.0,))})
    ZE.run()
    assert [c["symbol"] for c in enter_calls] == ["BBB"]
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(breaking=[break_row(overhead=None)]), zones={})
    out = ZE.run()
    assert enter_calls == [] and out["blocked"] == ["BBB"]


# ── Skips (not attempts) ─────────────────────────────────────────────────────

def test_already_held_skipped_without_attempt(env):
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()]),
        positions=[_position("AAA")],
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    out = ZE.run()
    assert enter_calls == []
    assert out["skipped"] == [{"symbol": "AAA", "reason": "already held"}]
    assert _state_rows(db) == [] and _race_rows(db) == []


def test_position_slots_full_skipped_without_attempt(env):
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()]),
        positions=[_position("P%d" % i) for i in range(MAX_POSITIONS)],
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    out = ZE.run()
    assert enter_calls == []
    assert out["skipped"][0]["reason"].startswith("no position slot")
    assert _state_rows(db) == [] and _race_rows(db) == []


def test_per_day_cap_four(env):
    """Five valid demand arrivals -> exactly MAX_ZONE_ENTRIES_PER_DAY buys;
    a pre-seeded day at the cap -> zero."""
    syms = ["A%d" % i for i in range(5)]
    rows = [demand_row(sym=s, dist_pct=0.1 * i) for i, s in enumerate(syms)]
    zones = {s: zone_doc(s, supply_los=(120.0,)) for s in syms}
    _, db, enter_calls, _, _ = env(latest=latest_doc(near_demand=rows), zones=zones)
    out = ZE.run()
    assert len(enter_calls) == ZE.MAX_ZONE_ENTRIES_PER_DAY == 4
    assert out["entries_today"] == 4
    assert sum(1 for r in _state_rows(db) if r.get("entered")) == 4
    assert out["skipped"] == [{"symbol": "A4", "reason": "daily cap 4 reached"}]

    _, db, enter_calls, _, _ = env(latest=latest_doc(near_demand=rows[:1]), zones=zones)
    for i in range(4):
        db.zone_edge_entry_state.insert_one(
            {"key": "X%d:1-2:%s" % (i, DAY), "symbol": "X%d" % i, "date": DAY,
             "attempted": True, "entered": True})
    out = ZE.run()
    assert enter_calls == [] and out["skipped"][0]["reason"] == "daily cap 4 reached"


def test_second_tick_same_band_no_second_attempt(env):
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()]),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    ZE.run()
    # the name is now held at the broker in reality; even if positions()
    # lags, the state record alone must stop a second attempt
    out2 = ZE.run()
    assert len(enter_calls) == 1
    assert len(_state_rows(db)) == 1 and len(_race_rows(db)) == 1
    assert out2["skipped"] == [{"symbol": "AAA", "reason": "attempted today (same band)"}]


def test_same_symbol_twice_in_one_tick_handled_once(env):
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(breaking=[break_row(sym="AAA", overhead=0)],
                          near_demand=[demand_row(sym="AAA")]),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    out = ZE.run()
    assert len(enter_calls) == 1
    assert out["skipped"] == [{"symbol": "AAA", "reason": "already handled this tick"}]


# ── Success / veto / error paths ────────────────────────────────────────────

def test_success_path_enters_with_owner_stop_and_records_everything(env):
    row = demand_row(last=100.0, lo=98.0, hi=99.5, tier="near", dist_pct=0.5,
                     first_seen="10:12")
    fake, db, enter_calls, pushes, _ = env(
        latest=latest_doc(near_demand=[row]),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    out = ZE.run()
    assert out["ran"] is True and out["entered"] == ["AAA"]
    assert out["entries_today"] == 1
    # entries.enter is the ONLY buy path — called with the computed stop
    assert len(enter_calls) == 1
    call = enter_calls[0]
    assert call["symbol"] == "AAA" and call["limit_price"] is None
    assert call["allow_earnings"] is False and call["top_up"] is False
    assert call["stop_pct"] == pytest.approx(_expected_stop_pct(100.0, 98.0))
    assert call["stop_pct"] == pytest.approx(2.49, abs=0.01)
    # state
    st = _state_rows(db)[0]
    assert st["key"] == "AAA:98-99.5:%s" % DAY
    assert st["attempted"] is True and st["entered"] is True
    assert st["result"] == "entered" and st["order_id"] == "o-1"
    assert st["client_order_id"] == "coid-AAA"     # from the 'entry' ledger row
    # race doc
    race = _race_rows(db)[0]
    assert race["_id"] == "AAA:demand:98-99.5:%s" % DAY
    assert race["outcome"] == "ordered" and race["reason"] is None
    assert race["signal_first_seen"] == "10:12"
    assert race["signal_ts"] == datetime.combine(
        date.fromisoformat(DAY), dtime(10, 12), tzinfo=ET).isoformat()
    assert race["signal_ts_basis"] == "first_seen"
    assert race["signal_px"] == 100.0
    assert race["engine_order_ts"] and race["engine_order_ts"].endswith("Z")
    assert race["engine_client_order_id"] == "coid-AAA"
    assert race["engine_order_id"] == "o-1"
    for k in ("engine_fill_ts", "engine_fill_px", "user_view_ts",
              "user_view_px", "user_fill_ts", "user_fill_px"):
        assert race[k] is None
    # ledger
    rows = _kind_rows(db, "zone_entry")
    assert len(rows) == 1 and rows[0]["dry_run"] is False
    det = rows[0]["detail"]
    assert det["side"] == "demand" and det["band"]["lo"] == 98.0
    assert det["stop_pct"] == pytest.approx(2.49, abs=0.01)
    assert det["dist_pct"] == 0.5 and det["first_seen"] == "10:12"
    assert det["order_id"] == "o-1"
    assert "OWNER RULES" in rows[0]["cite"] and "risk_rules" in rows[0]["cite"]
    assert "p." not in rows[0]["cite"]           # no book page for the entry
    # push
    assert pushes == [("AAA", "demand", "paper", pushes[0][3])]
    assert "AAA demand near" in pushes[0][3] and "12 sh" in pushes[0][3]


def test_breakout_success_stop_sits_under_cleared_band_floor(env):
    row = break_row(last=105.0, lo=100.0, hi=103.0, overhead=0)
    _, db, enter_calls, pushes, _ = env(latest=latest_doc(breaking=[row]))
    ZE.run()
    assert enter_calls[0]["stop_pct"] == pytest.approx(_expected_stop_pct(105.0, 100.0))
    race = _race_rows(db)[0]
    assert race["side"] == "supply" and race["kind"] == "breakout"
    assert race["_id"] == "BBB:supply:100-103:%s" % DAY
    assert pushes[0][1] == "supply"


def test_push_title_word_follows_broker_mode(env):
    for mode, word in (("paper", "paper"), ("sim", "sim"), ("live", "LIVE")):
        _, _, _, pushes, _ = env(latest=latest_doc(breaking=[break_row()]), mode=mode)
        ZE.run()
        assert pushes[0][2] == word


def test_notify_builds_target_title(monkeypatch):
    sent = []
    stub_sender = types.ModuleType("push.sender")
    stub_sender.send_to_user = lambda email, payload, kind=None: sent.append(
        (email, payload, kind)) or {"sent": 1}
    stub_hooks = types.ModuleType("push.hooks")
    stub_hooks.ADMIN_EMAIL = "admin@example.com"
    monkeypatch.setitem(sys.modules, "push.sender", stub_sender)
    monkeypatch.setitem(sys.modules, "push.hooks", stub_hooks)
    # `from push import sender` resolves the PACKAGE attribute first when the
    # real modules were imported earlier in the session — stub those too.
    import push as push_pkg
    monkeypatch.setattr(push_pkg, "sender", stub_sender, raising=False)
    monkeypatch.setattr(push_pkg, "hooks", stub_hooks, raising=False)
    ZE._notify("AAA", "demand", "paper", "body text")
    assert len(sent) == 1
    email, payload, kind = sent[0]
    assert email == "admin@example.com" and kind is None
    assert payload["title"] == "🎯 Zone-edge paper buy AAA demand"
    assert payload["body"] == "body text" and payload["ticker"] == "AAA"


def test_enter_veto_writes_blocked_race_and_never_retries(env):
    _, db, enter_calls, pushes, _ = env(
        latest=latest_doc(near_demand=[demand_row()]),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))},
        enter_raises=ValueError("earnings in 3d (2026-09-06) — pass allow_earnings=true"))
    out = ZE.run()
    assert len(enter_calls) == 1 and out["blocked"] == ["AAA"]
    assert out["entered"] == [] and pushes == []
    race = _race_rows(db)[0]
    assert race["outcome"] == "blocked" and "earnings" in race["reason"]
    st = _state_rows(db)[0]
    assert st["attempted"] is True and st["entered"] is False and st["result"] == "blocked"
    blocked = _kind_rows(db, "zone_entry_blocked")
    assert len(blocked) == 1 and blocked[0]["dry_run"] is True
    assert _kind_rows(db, "zone_entry") == []
    ZE.run()
    assert len(enter_calls) == 1                   # no per-minute retry


def test_enter_unexpected_error_ledgered_once_and_visible(env):
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()]),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))},
        enter_raises=RuntimeError("alpaca 500"))
    out = ZE.run()
    assert out["errors"] == ["AAA: alpaca 500"]
    assert _race_rows(db)[0]["outcome"] == "error"
    assert _state_rows(db)[0]["result"] == "error"
    err = _kind_rows(db, "zone_entry_error")
    assert len(err) == 1 and err[0]["dry_run"] is False
    assert "verify at the broker" in err[0]["detail"]["hint"]
    ZE.run()
    assert len(enter_calls) == 1 and len(_kind_rows(db, "zone_entry_error")) == 1


def test_market_closed_veto_is_not_recorded_and_retries(env):
    """A 'market closed' veto from entries (clock flipped mid-tick) is NOT an
    attempt: no state, no race doc, and the next open tick tries again."""
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()]),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))},
        enter_raises=ValueError("market closed — market entries blocked; provide limit_price"))
    out = ZE.run()
    assert len(enter_calls) == 1
    assert out["skipped"] == [{"symbol": "AAA", "reason": "market closed"}]
    assert out["blocked"] == []
    assert _state_rows(db) == [] and _race_rows(db) == []
    assert _kind_rows(db, "zone_entry_blocked") == []
    ZE.run()
    assert len(enter_calls) == 2


def test_ordering_breakouts_first_then_demand_by_dist(env):
    rows_d = [demand_row(sym="CCC", dist_pct=1.2, first_seen="10:01"),
              demand_row(sym="AAA", dist_pct=0.3, first_seen="10:20")]
    rows_b = [break_row(sym="BBB", dist_pct=-2.5, overhead=0),
              break_row(sym="DDD", dist_pct=-0.4, overhead=0)]
    zones = {s: zone_doc(s, supply_los=(120.0,)) for s in ("AAA", "CCC")}
    _, _, enter_calls, _, _ = env(
        latest=latest_doc(breaking=rows_b, near_demand=rows_d), zones=zones)
    ZE.run()
    assert [c["symbol"] for c in enter_calls] == ["DDD", "BBB", "AAA", "CCC"]


def test_read_candidates_pure_order_and_rejections():
    latest = latest_doc(
        breaking=[break_row(sym="N1", tier="near", dist_pct=0.2),
                  break_row(sym="B1", dist_pct=-1.0),
                  break_row(sym="B2", dist_pct=-0.2)],
        near_demand=[demand_row(sym="D1", dist_pct=0.9),
                     demand_row(sym="D2", dist_pct=0.1),
                     demand_row(sym="R1", arrival=False)])
    cands, rejected = ZE.read_candidates(latest)
    assert [c["symbol"] for c in cands] == ["B2", "B1", "D2", "D1"]
    assert {(r["symbol"], r["reason"]) for r in rejected} == {
        ("N1", "near resistance (not through)"), ("R1", "resident (no arrival)")}
    assert ZE.read_candidates(None) == ([], [])
    assert ZE.read_candidates({"breaking": [None, "x"], "near_demand": []}) == ([], [])


def test_stop_request_and_room_ok_pure():
    stop, pct = ZE.stop_request(100.0, 98.0)
    assert stop == pytest.approx(97.51) and pct == pytest.approx(2.49)
    assert ZE.stop_request(None, 98.0) == (None, None)
    assert ZE.stop_request(100.0, 0) == (None, None)
    assert ZE.stop_request(100.0, "nan") == (None, None)
    ok, det = ZE.room_ok(100.0, 2.49, None)
    assert ok is False and "unknown" in det["reason"]
    ok, det = ZE.room_ok(100.0, 2.49, {"bands": []})
    assert ok is True and det["reason"] == "no band overhead"
    ok, det = ZE.room_ok(100.0, 2.49, zone_doc("X", supply_los=(104.97, 130.0)))
    assert ok is False and det["room_pct"] == pytest.approx(4.97)
    ok, det = ZE.room_ok(100.0, 2.49, zone_doc("X", supply_los=(104.98,)))
    assert ok is True and det["reason"] == "ok"
    # a supply band BELOW the print (a cleared/broken one) is not overhead
    ok, det = ZE.room_ok(100.0, 2.49, zone_doc("X", supply_los=(90.0,)))
    assert ok is True and det["next_band"] is None


def test_signal_state_pure():
    good = ZE.signal_state(latest_doc(), NOW, DAY)
    assert good["fresh"] is True and good["age_sec"] == 0.0
    assert ZE.signal_state(None, NOW, DAY)["fresh"] is False
    assert ZE.signal_state({"date": DAY, "as_of": "garbage"}, NOW, DAY)["fresh"] is False
    assert ZE.signal_state(latest_doc(day="2020-01-01"), NOW, DAY)["fresh"] is False
    edge = (NOW - timedelta(seconds=ZE.SIGNAL_MAX_AGE_SEC)).isoformat()
    assert ZE.signal_state(latest_doc(as_of=edge), NOW, DAY)["fresh"] is True
    past = (NOW - timedelta(seconds=ZE.SIGNAL_MAX_AGE_SEC + 1)).isoformat()
    assert ZE.signal_state(latest_doc(as_of=past), NOW, DAY)["fresh"] is False


# ── Execution race: reconcile + report ──────────────────────────────────────

def _sig(hh=10, mm=12):
    return datetime.combine(date.fromisoformat(DAY), dtime(hh, mm), tzinfo=ET)


def _race_doc(sym="AAA", outcome="ordered", day=DAY, sig=None, order_lag=5,
              coid="coid-AAA", side="demand"):
    sig = sig or _sig()
    doc = {"_id": "%s:%s:98-99.5:%s" % (sym, side, day), "symbol": sym,
           "side": side, "kind": "demand", "tier": "near",
           "band": {"lo": 98.0, "hi": 99.5}, "day": day,
           "signal_first_seen": sig.strftime("%H:%M"),
           "signal_ts": sig.isoformat(), "signal_ts_basis": "first_seen",
           "signal_px": 100.0, "dist_pct": 0.5, "stop_pct": 2.49,
           "engine_order_ts": None, "engine_order_id": None,
           "engine_client_order_id": None,
           "engine_fill_ts": None, "engine_fill_px": None,
           "user_view_ts": None, "user_view_px": None,
           "user_fill_ts": None, "user_fill_px": None,
           "outcome": outcome, "reason": None, "created_at": EE._utc_iso()}
    if outcome == "ordered":
        doc["engine_order_ts"] = EE._utc_iso((sig + timedelta(seconds=order_lag))
                                             .astimezone(timezone.utc))
        doc["engine_order_id"] = "o-1"
        doc["engine_client_order_id"] = coid
    return doc


def _utc(dt):
    return EE._utc_iso(dt.astimezone(timezone.utc))


def test_reconcile_race_stamps_engine_fill_user_view_and_user_fill(env):
    sig = _sig()
    filled_at = sig + timedelta(seconds=7)
    fake, db, _, _, _ = env(
        latest=latest_doc(),
        closed_orders=[
            {"id": "o-1", "client_order_id": "coid-AAA", "symbol": "AAA",
             "side": "buy", "status": "filled", "filled_at": _utc(filled_at),
             "filled_avg_price": "100.4"},
            {"id": "o-9", "client_order_id": "coid-ZZZ", "symbol": "ZZZ",
             "side": "buy", "status": "filled", "filled_at": _utc(filled_at),
             "filled_avg_price": "50"}])
    db.execution_race.insert_one(_race_doc())
    view_ts = int((sig + timedelta(seconds=90)).timestamp())
    db.usage_events.insert_many([
        {"user_email": OWNER, "module": "sepa", "route": "/sepa/AAA?tab=supply",
         "started_at": view_ts},
        {"user_email": OWNER, "module": "sepa", "route": "/sepa/AAA",
         "started_at": view_ts + 600},                        # later view
        {"user_email": OWNER, "module": "sepa", "route": "/sepa/AAA",
         "started_at": int((sig - timedelta(seconds=60)).timestamp())},  # BEFORE
        {"user_email": OWNER, "module": "sepa", "route": "/sepa/AAAB",
         "started_at": view_ts - 30},                         # other symbol
        {"user_email": "other@example.com", "module": "sepa", "route": "/sepa/AAA",
         "started_at": view_ts - 30},                         # other user
    ])
    db.zone_edge_track.insert_many([
        {"symbol": "AAA", "date": DAY, "ts": (sig + timedelta(seconds=60)).isoformat(),
         "side": "demand", "tier": "near", "px": 100.6, "dist_pct": 0.6,
         "band": {"lo": 98.0, "hi": 99.5}},
        {"symbol": "AAA", "date": DAY, "ts": (sig + timedelta(seconds=600)).isoformat(),
         "side": "demand", "tier": "near", "px": 102.0, "dist_pct": 2.0,
         "band": {"lo": 98.0, "hi": 99.5}},
    ])
    fill_ts = int((sig + timedelta(seconds=300)).timestamp())
    db.portfolio_holdings.insert_many([
        {"user_email": OWNER, "ticker": "AAA", "account": "Fidelity",
         "shares": 10.0, "cost_basis": 1010.0, "added_at": fill_ts,
         "updated_at": fill_ts},
        {"user_email": OWNER, "ticker": "AAA", "account": "Old",
         "shares": 5.0, "cost_basis": 400.0,
         "added_at": fill_ts - 86400 * 30, "updated_at": fill_ts - 86400 * 30},
        {"user_email": OWNER, "ticker": "BBB", "account": "Fidelity",
         "shares": 1.0, "cost_basis": 1.0, "added_at": fill_ts, "updated_at": fill_ts},
    ])
    out = ZE.reconcile_race(now=NOW, broker=fake)
    assert out["checked"] == 1 and out["errors"] == []
    assert out["engine_filled"] == 1 and out["user_viewed"] == 1 and out["user_filled"] == 1
    assert fake.closed_calls == 1
    d = db.execution_race.rows[0]
    assert d["engine_fill_ts"] == _utc(filled_at) and d["engine_fill_px"] == 100.4
    assert d["user_view_ts"] == _utc(sig + timedelta(seconds=90))
    assert d["user_view_px"] == 100.6                     # nearest track print
    assert d["user_fill_ts"] == _utc(sig + timedelta(seconds=300))
    assert d["user_fill_px"] == pytest.approx(101.0)      # cost basis per share
    assert d["reconciled_at"]
    # read-only over every other collection
    assert len(db.usage_events.rows) == 5 and len(db.portfolio_holdings.rows) == 3
    assert len(db.zone_edge_track.rows) == 2 and db.trade_ledger.rows == []
    # idempotent: a second pass finds nothing new and asks the broker nothing
    out2 = ZE.reconcile_race(now=NOW, broker=fake)
    assert out2["engine_filled"] == 0 and out2["user_viewed"] == 0
    assert fake.closed_calls == 1

    rep = ZE.race_report(days=5, now=NOW, reconcile=False)
    assert rep["days"] == 5 and rep["owner"] == OWNER
    row = rep["rows"][0]
    assert "_id" not in row
    assert row["engine_lag_sec"] == 5.0 and row["engine_fill_lag_sec"] == 7.0
    assert row["user_view_lag_sec"] == 90.0 and row["user_fill_lag_sec"] == 300.0
    assert row["px_base"] == 100.4
    assert row["px_gap_view"] == pytest.approx(0.2)
    assert row["px_gap_fill"] == pytest.approx(0.6)
    assert row["px_gap_fill_pct"] == pytest.approx(0.6 / 100.4 * 100.0, abs=1e-3)
    s = rep["summary"]
    assert s["n"] == 1 and s["n_ordered"] == 1 and s["n_engine_filled"] == 1
    assert s["n_user_viewed"] == 1 and s["n_user_filled"] == 1
    assert s["median_engine_lag_sec"] == 5.0
    assert s["median_user_view_lag_sec"] == 90.0
    assert s["median_user_fill_lag_sec"] == 300.0
    assert s["median_px_gap_fill_pct"] == pytest.approx(0.6 / 100.4 * 100.0, abs=1e-3)
    json.dumps(rep, allow_nan=False)


def test_reconcile_negatives_no_view_no_fill_no_order_match(env):
    """View before the signal only, holding older than the signal, and a
    closed order with a different client id -> nothing stamped; a blocked
    doc never asks the broker for fills; a view with no track print within
    the window gets user_view_px None."""
    sig = _sig()
    fake, db, _, _, _ = env(
        latest=latest_doc(),
        closed_orders=[{"id": "o-other", "client_order_id": "coid-OTHER",
                        "symbol": "AAA", "side": "buy", "status": "filled",
                        "filled_at": _utc(sig), "filled_avg_price": "1"}])
    db.execution_race.insert_one(_race_doc())
    db.execution_race.insert_one(_race_doc(sym="BBB", outcome="blocked", coid=None))
    db.usage_events.insert_one({"user_email": OWNER, "route": "/sepa/AAA",
                                "started_at": int((sig - timedelta(seconds=5)).timestamp())})
    db.usage_events.insert_one({"user_email": OWNER, "route": "/sepa/BBB",
                                "started_at": int((sig + timedelta(seconds=40)).timestamp())})
    old = int((sig - timedelta(days=3)).timestamp())
    db.portfolio_holdings.insert_one({"user_email": OWNER, "ticker": "AAA",
                                      "shares": 3.0, "cost_basis": 300.0,
                                      "added_at": old, "updated_at": old})
    out = ZE.reconcile_race(now=NOW, broker=fake)
    assert out["checked"] == 2 and out["engine_filled"] == 0
    assert out["user_filled"] == 0 and out["user_viewed"] == 1
    a = db.execution_race.find_one({"symbol": "AAA"})
    assert a["engine_fill_ts"] is None and a["user_view_ts"] is None
    assert a["user_fill_ts"] is None
    b = db.execution_race.find_one({"symbol": "BBB"})
    assert b["user_view_ts"] == _utc(sig + timedelta(seconds=40))
    assert b["user_view_px"] is None                      # no track print near
    assert b["engine_fill_ts"] is None
    rep = ZE.race_report(days=5, now=NOW, reconcile=False)
    r = {x["symbol"]: x for x in rep["rows"]}
    assert r["AAA"]["engine_lag_sec"] == 5.0 and r["AAA"]["engine_fill_lag_sec"] is None
    assert r["BBB"]["engine_lag_sec"] is None and r["BBB"]["user_view_lag_sec"] == 40.0
    assert r["BBB"]["px_base"] == 100.0                   # falls back to signal_px
    assert rep["summary"]["median_engine_lag_sec"] == 5.0
    assert rep["summary"]["median_user_fill_lag_sec"] is None


def test_reconcile_only_today_and_yesterday(env):
    fake, db, _, _, _ = env(latest=latest_doc())
    old_day = (date.fromisoformat(DAY) - timedelta(days=3)).isoformat()
    old_sig = datetime.combine(date.fromisoformat(old_day), dtime(10, 12), tzinfo=ET)
    db.execution_race.insert_one(_race_doc(day=old_day, sig=old_sig))
    db.usage_events.insert_one({"user_email": OWNER, "route": "/sepa/AAA",
                                "started_at": int((old_sig + timedelta(seconds=30)).timestamp())})
    out = ZE.reconcile_race(now=NOW, broker=fake)
    assert out["checked"] == 0 and fake.closed_calls == 0
    assert db.execution_race.rows[0]["user_view_ts"] is None
    yday = (date.fromisoformat(DAY) - timedelta(days=1)).isoformat()
    y_sig = datetime.combine(date.fromisoformat(yday), dtime(10, 12), tzinfo=ET)
    db.execution_race.insert_one(_race_doc(sym="YYY", day=yday, sig=y_sig, coid="coid-YYY"))
    db.usage_events.insert_one({"user_email": OWNER, "route": "/sepa/YYY",
                                "started_at": int((y_sig + timedelta(seconds=30)).timestamp())})
    out = ZE.reconcile_race(now=NOW, broker=fake)
    assert out["checked"] == 1 and out["user_viewed"] == 1


def test_race_report_days_window_medians_and_nan_safety(env):
    fake, db, _, _, _ = env(latest=latest_doc())
    for i, (sym, lag) in enumerate((("A1", 3), ("A2", 9), ("A3", 4))):
        d = _race_doc(sym=sym, order_lag=lag, coid="c%d" % i)
        d["user_view_ts"] = _utc(_sig() + timedelta(seconds=100 + i * 50))
        d["user_fill_px"] = 101.0 + i
        d["user_fill_ts"] = _utc(_sig() + timedelta(seconds=500 + i))
        db.execution_race.insert_one(d)
    bad = _race_doc(sym="NAN", coid="cn")
    bad["signal_px"] = float("nan")
    bad["signal_ts"] = "not-a-time"
    db.execution_race.insert_one(bad)
    six_days = (date.fromisoformat(DAY) - timedelta(days=6)).isoformat()
    db.execution_race.insert_one(_race_doc(sym="OLD", day=six_days, coid="co"))
    rep = ZE.race_report(days=5, now=NOW, reconcile=False)
    syms = {r["symbol"] for r in rep["rows"]}
    assert syms == {"A1", "A2", "A3", "NAN"}
    s = rep["summary"]
    assert s["n"] == 4 and s["median_engine_lag_sec"] == 4.0
    assert s["median_user_view_lag_sec"] == 150.0
    assert s["median_user_fill_lag_sec"] == 501.0
    assert s["median_px_gap_fill_pct"] == pytest.approx(2.0)   # (102-100)/100
    nan_row = [r for r in rep["rows"] if r["symbol"] == "NAN"][0]
    assert nan_row["signal_px"] is None and nan_row["engine_lag_sec"] is None
    assert nan_row["px_base"] is None and nan_row["px_gap_fill"] is None
    json.dumps(rep, allow_nan=False)
    rep7 = ZE.race_report(days=7, now=NOW, reconcile=False)
    assert "OLD" in {r["symbol"] for r in rep7["rows"]}
    assert ZE.race_report(days=0, now=NOW, reconcile=False)["days"] == 1
    assert ZE.race_report(days=999, now=NOW, reconcile=False)["days"] == 30


def test_run_reconciles_at_the_end(env, monkeypatch):
    calls = []
    fake, db, _, _, _ = env(latest=latest_doc(breaking=[break_row()]))
    real = ZE.reconcile_race
    monkeypatch.setattr(ZE, "reconcile_race",
                        lambda now=None, broker=None: calls.append(now) or real(now=now, broker=broker))
    out = ZE.run()
    assert calls == [NOW] and out["race"]["checked"] == 1
    # gated runs never touch the race ledger
    calls.clear()
    _, _, _, _, _ = env(latest=latest_doc(), flag=False)
    assert "race" not in ZE.run() and calls == []


# ── Status block + config + engine wiring ────────────────────────────────────

def test_status_block_shape(env):
    _, db, _, _, _ = env(latest=latest_doc(near_demand=[demand_row()]),
                         zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    ZE.run()
    blk = ZE.status_block()
    assert blk["enabled"] is True and blk["entries_today"] == 1
    assert blk["max_per_day"] == 4 and blk["last_entry_et"] == "15:45"
    assert blk["signal"]["fresh"] is True
    assert blk["attempts"][0]["symbol"] == "AAA" and "_id" not in blk["attempts"][0]
    assert any("arrival" in r["rule"] for r in blk["rules"])
    assert all("source" in r and "value" in r for r in blk["rules"])
    assert not any("TLSW" in r["source"] or "p." in r["source"] for r in blk["rules"])
    json.dumps(blk, allow_nan=False)


def test_get_config_carries_flag_default_off(env):
    _, db, _, _, _ = env(latest=None, flag=True)
    assert EE.get_config()["zone_edge_entry"] is True
    db.trading_config.rows[0].pop("zone_edge_entry")
    assert EE.get_config()["zone_edge_entry"] is False
    assert "last_zone_entry_disabled_day" in EE.get_config()


class _TickBroker(FakeBroker):
    def open_orders(self, symbol=None):
        return []


def test_tick_step_h_calls_run_and_is_fenced(env, monkeypatch):
    """exit_engine.tick() runs zone_edge_entry.run(broker, cfg) AFTER the
    exits and inside its own try/except: a crash lands in summary.errors,
    never propagates, and the journal step still runs."""
    fake, db, _, _, _ = env(latest=latest_doc())
    monkeypatch.setattr(EE, "regime", lambda: "normal")
    monkeypatch.setattr(EE, "_distribution_read", lambda sym: None)
    import trading.auto_entry as AE
    import trading.journal as JN
    monkeypatch.setattr(AE, "run", lambda broker=None, cfg=None: {"ran": False})
    journal_calls = []
    monkeypatch.setattr(JN, "reconcile", lambda: journal_calls.append(1) or {})
    seen = []

    def fake_run(broker=None, cfg=None):
        seen.append((broker, cfg.get("zone_edge_entry")))
        return {"ran": True, "entered": []}

    monkeypatch.setattr(ZE, "run", fake_run)
    summary = EE.tick()
    assert summary["ok"] is True
    assert summary["zone_edge_entry"] == {"ran": True, "entered": []}
    assert seen == [(fake, True)] and journal_calls == [1]

    def boom(broker=None, cfg=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(ZE, "run", boom)
    summary = EE.tick()
    assert summary["ok"] is True
    assert any(e == "zone_edge_entry: boom" for e in summary["errors"])
    assert len(journal_calls) == 2


def test_status_carries_zone_edge_block_and_survives_its_failure(env, monkeypatch):
    fake, db, _, _, _ = env(latest=latest_doc())
    monkeypatch.setattr(EE, "regime", lambda: "normal")
    out = EE.status()
    assert out["zone_edge_entry"]["enabled"] is True
    assert out["zone_edge_entry"]["max_per_day"] == 4

    def boom(cfg=None):
        raise RuntimeError("status boom")

    monkeypatch.setattr(ZE, "status_block", boom)
    out = EE.status()
    assert out["zone_edge_entry"] == {"enabled": True, "error": "status boom"}


def test_api_config_accepts_zone_edge_entry_and_race_route(env, monkeypatch):
    fastapi = pytest.importorskip("fastapi")
    from trading import api as TA
    import auth
    admin = auth.HOUSE_OWNER_EMAIL
    _, db, _, _, _ = env(latest=latest_doc(), flag=False)

    resp = asyncio.run(TA.trading_config({"zone_edge_entry": True}, email=admin))
    assert json.loads(resp.body) == {"zone_edge_entry": True}
    assert EE.get_config()["zone_edge_entry"] is True
    assert _kind_rows(db, "config_update")[-1]["detail"]["zone_edge_entry"] is True
    resp = asyncio.run(TA.trading_config({"zone_edge_entry": None}, email=admin))
    assert json.loads(resp.body) == {"zone_edge_entry": False}
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_config({"zone_edge_entry": "yes"}, email=admin))
    assert exc.value.status_code == 400
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_config({"zone_edge_entry": True}, email="nobody@example.com"))
    assert exc.value.status_code == 403

    monkeypatch.setattr(ZE, "race_report",
                        lambda days=5: {"rows": [], "summary": {"n": 0}, "days": days})
    resp = asyncio.run(TA.trading_race(days=3, email=admin))
    assert json.loads(resp.body) == {"rows": [], "summary": {"n": 0}, "days": 3}
    resp = asyncio.run(TA.trading_race(days=500, email=admin))
    assert json.loads(resp.body)["days"] == 30
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_race(days=3, email="nobody@example.com"))
    assert exc.value.status_code == 403


def test_helpers_to_dt_and_secs():
    assert ZE._to_dt(None) is None and ZE._to_dt("") is None
    assert ZE._to_dt("garbage") is None
    z = ZE._to_dt("2026-09-03T14:30:00Z")
    assert z.tzinfo is not None and z.hour == 14
    e = ZE._to_dt(1_700_000_000)
    assert e.tzinfo == timezone.utc
    assert ZE._secs("2026-09-03T14:30:10Z", "2026-09-03T10:30:00-04:00") == 10.0
    assert ZE._secs(None, "2026-09-03T10:30:00-04:00") is None
    assert ZE._num(float("nan")) is None and ZE._num(math.inf) is None
    assert ZE._num("1.23456") == 1.2346
    assert ZE._route_matches("/sepa/MU?tab=supply", "MU") is True
    assert ZE._route_matches("/sepa/MU/", "mu") is True
    assert ZE._route_matches("/sepa/MUX", "MU") is False
    assert ZE._route_matches("/sepa", "MU") is False
    assert ZE._route_matches(None, "MU") is False
    ts, basis = ZE.signal_ts_for(DAY, "10:12", None)
    assert basis == "first_seen"
    assert ts.endswith("10:12:00-04:00") or ts.endswith("10:12:00-05:00")
    ts, basis = ZE.signal_ts_for(DAY, None, NOW.isoformat())
    assert basis == "as_of" and ts == NOW.isoformat()
    assert ZE.signal_ts_for(DAY, "bad", "bad") == (None, None)


# ── Review regressions (2026-09-03): fail-closed attempt store, narrow order
#    try, malformed rows, future-dated signal, same-symbol-other-band ────────

class BoomColl(FakeColl):
    """FakeColl whose named methods raise — a Mongo outage mid-tick."""

    def __init__(self, docs=None, fail=()):
        super().__init__(docs)
        self.fail = set(fail)

    def _maybe(self, name):
        if name in self.fail:
            raise RuntimeError("mongo down (%s)" % name)

    def find_one(self, *a, **k):
        self._maybe("find_one")
        return super().find_one(*a, **k)

    def find(self, *a, **k):
        self._maybe("find")
        return super().find(*a, **k)

    def update_one(self, *a, **k):
        self._maybe("update_one")
        return super().update_one(*a, **k)


def test_state_write_failure_places_no_order(env):
    """The attempt record must be durable BEFORE entries.enter: a failed
    state write means NO order (not an unrecorded order that a crash would
    retry every minute). Once the store is back the band is attempted."""
    _, db, enter_calls, pushes, _ = env(
        latest=latest_doc(near_demand=[demand_row()]),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    db.zone_edge_entry_state = BoomColl(fail=("update_one",))
    out = ZE.run()
    assert enter_calls == [] and pushes == []
    assert out["ok"] is False
    assert any("state write failed" in e for e in out["errors"])
    assert out["skipped"] == [{"symbol": "AAA", "reason": "state write failed (not attempted)"}]
    assert out["blocked"] == [] and out["entered"] == []
    assert _race_rows(db) == []
    assert _kind_rows(db, "zone_entry") == [] and _kind_rows(db, "zone_entry_blocked") == []
    db.zone_edge_entry_state = FakeColl()
    ZE.run()
    assert [c["symbol"] for c in enter_calls] == ["AAA"]


def test_state_read_failure_places_no_order(env, monkeypatch):
    """Unknown attempt state fails CLOSED: a per-key read failure skips that
    candidate; a day-level read failure (or no collection at all) sits the
    whole tick out. Nothing is recorded either way."""
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()]),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    db.zone_edge_entry_state = BoomColl(fail=("find_one",))
    out = ZE.run()
    assert enter_calls == [] and out["ok"] is False
    assert out["skipped"] == [{"symbol": "AAA", "reason": "state unknown (read failed)"}]
    assert _race_rows(db) == [] and _kind_rows(db, "zone_entry_blocked") == []

    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()]),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    db.zone_edge_entry_state = BoomColl(fail=("find",))
    out = ZE.run()
    assert enter_calls == [] and out["ok"] is False
    assert out["reason"] == "state_unavailable" and out["evaluated"] == 0
    assert _race_rows(db) == []

    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()]),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    real_coll = ZE._coll
    monkeypatch.setattr(ZE, "_coll",
                        lambda name: None if name == ZE.STATE_COLL else real_coll(name))
    out = ZE.run()
    assert enter_calls == [] and out["reason"] == "state_unavailable"
    assert ZE._get_state("x") is None and ZE._set_state("x", a=1) is False
    assert ZE._entries_today(DAY) is None


def test_symbol_entered_today_under_other_band_skipped(env):
    """Bought today under band A, then listed again under band B -> skipped
    without an attempt (the broker's same-day client_order_id would reject
    it; no blocked ledger / race noise). A symbol merely BLOCKED under
    another band is still a fresh attempt on the new band."""
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()]),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    db.zone_edge_entry_state.insert_one(
        {"key": "AAA:90-91:%s" % DAY, "symbol": "AAA", "date": DAY,
         "attempted": True, "entered": True})
    out = ZE.run()
    assert enter_calls == []
    assert out["skipped"] == [{"symbol": "AAA", "reason": "already entered today (other band)"}]
    assert len(_state_rows(db)) == 1 and _race_rows(db) == []
    assert _kind_rows(db, "zone_entry_blocked") == []

    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()]),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    db.zone_edge_entry_state.insert_one(
        {"key": "AAA:90-91:%s" % DAY, "symbol": "AAA", "date": DAY,
         "attempted": True, "entered": False, "result": "blocked"})
    ZE.run()
    assert [c["symbol"] for c in enter_calls] == ["AAA"]


def test_post_order_bookkeeping_failure_never_relabels_a_placed_order(env):
    """Once entries.enter has RETURNED an order exists. A result whose
    fields do not format (shares 'twelve', stop 'bogus') must still be
    recorded as entered/ordered — one zone_entry ledger row, no
    zone_entry_error, race outcome 'ordered', push still sent."""
    weird = {"order_id": "o-1", "shares": "twelve", "stop": "bogus"}
    _, db, enter_calls, pushes, _ = env(
        latest=latest_doc(near_demand=[demand_row()]),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))},
        enter_result=weird)
    out = ZE.run()
    assert len(enter_calls) == 1
    assert out["entered"] == ["AAA"] and out["blocked"] == [] and out["errors"] == []
    st = _state_rows(db)[0]
    assert st["entered"] is True and st["result"] == "entered" and st["order_id"] == "o-1"
    race = _race_rows(db)[0]
    assert race["outcome"] == "ordered" and race["engine_order_id"] == "o-1"
    assert race["engine_order_ts"]
    assert len(_kind_rows(db, "zone_entry")) == 1
    assert _kind_rows(db, "zone_entry_error") == [] and _kind_rows(db, "zone_entry_blocked") == []
    assert len(pushes) == 1 and pushes[0][0] == "AAA" and "AAA" in pushes[0][3]
    ZE.run()
    assert len(enter_calls) == 1                   # no retry of a placed order


def test_malformed_board_rows_never_raise_and_never_buy(env):
    """Bad types on the board doc (non-str symbol, band as a list / string,
    non-list sections, a list where the doc should be) must be rejected,
    never raise out of run(), and place nothing."""
    bad = [
        dict(demand_row(sym="AAA"), symbol=123),
        dict(demand_row(sym="BBB"), band=[98.0, 99.5]),
        dict(demand_row(sym="CCC"), band="98-99.5"),
        dict(demand_row(sym="DDD"), symbol=None),
        "not-a-row", None, 7,
    ]
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=bad, breaking=()),
        zones={s: zone_doc(s, supply_los=(120.0,)) for s in ("AAA", "BBB", "CCC", "DDD")})
    out = ZE.run()
    assert out["ok"] is True and out["reason"] == "no_candidates"
    assert out["rejected"] == 4
    _assert_never(db, enter_calls)

    latest = latest_doc(near_demand=[demand_row()])
    latest["breaking"] = {"not": "a list"}
    latest["near_demand"] = "AAA"
    _, db, enter_calls, _, _ = env(latest=latest)
    out = ZE.run()
    assert out["reason"] == "no_candidates"
    _assert_never(db, enter_calls)

    assert ZE.read_candidates([1, 2]) == ([], [])
    assert ZE.read_candidates({"breaking": None, "near_demand": {"x": 1}}) == ([], [])
    assert ZE.signal_state([1, 2], NOW, DAY)["fresh"] is False
    assert ZE.signal_state("latest", NOW, DAY)["fresh"] is False


def test_malformed_zone_doc_blocks_room_check(env):
    """A zone_store doc whose bands are not a list of dicts is UNKNOWN room
    (fails closed -> blocked), never a crash and never 'no overhead'."""
    for bands in ([None], ["x", {"kind": "supply", "lo": 130.0}], "bands", None, 5):
        _, db, enter_calls, _, _ = env(
            latest=latest_doc(near_demand=[demand_row()]),
            zones={"AAA": {"symbol": "AAA", "date": DAY, "bands": bands}})
        out = ZE.run()
        assert enter_calls == [] and out["blocked"] == ["AAA"], bands
        assert "room unknown" in _state_rows(db)[0]["reason"]
    ok, det = ZE.room_ok(100.0, 2.49, {"bands": [None]})
    assert ok is False and "malformed" in det["reason"]
    ok, det = ZE.room_ok(100.0, 2.49, {"bands": [{"kind": "supply", "lo": "nan"}]})
    assert ok is True and det["reason"] == "no band overhead"
    ok, det = ZE.room_ok(100.0, 2.49, "not-a-doc")
    assert ok is False and "unknown" in det["reason"]


def test_future_dated_signal_is_not_trusted(env):
    """as_of more than SIGNAL_MAX_AGE_SEC in the future (clock skew / bad
    data) is not fresh; a few seconds of skew is tolerated."""
    future = (NOW + timedelta(seconds=ZE.SIGNAL_MAX_AGE_SEC + 1)).isoformat()
    s = ZE.signal_state(latest_doc(as_of=future), NOW, DAY)
    assert s["fresh"] is False and "future" in s["reason"]
    slight = (NOW + timedelta(seconds=30)).isoformat()
    assert ZE.signal_state(latest_doc(as_of=slight), NOW, DAY)["fresh"] is True
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()], as_of=future),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    out = ZE.run()
    assert out["reason"] == "stale_signal"
    _assert_never(db, enter_calls)


def test_run_survives_broker_configured_raising(env):
    """brk.configured() raising is a gate failure, not an exception out of
    run(): gated, nothing attempted."""
    fake, db, enter_calls, _, _ = env(latest=latest_doc(near_demand=[demand_row()]))

    def boom():
        raise RuntimeError("keyring")

    fake.configured = boom
    out = ZE.run()
    assert out["ran"] is False and out["reason"] == "gated"
    assert out["gate"]["configured"] is False
    assert any("configured" in e for e in out["errors"])
    _assert_never(db, enter_calls)


# ── Owner rule switches (Ajay 2026-09-03 evening: "Enter anything that is in
# demand zone ... Any time any stocks crossing the resistance or supply zone
# buy them too") — wide rules via cfg["zone_edge_rules"]; strict stays default.

def _wide_cfg(**over):
    rules = {"demand_residents": True, "breakout_any_band": True, "min_touches": 1}
    rules.update(over)
    return dict(EE.get_config(), zone_edge_rules=rules)


def test_active_rules_defaults_are_strict_and_junk_falls_back():
    assert ZE.active_rules(None) == ZE.RULES_DEFAULT
    assert ZE.active_rules({"zone_edge_rules": "wide"}) == ZE.RULES_DEFAULT
    junk = ZE.active_rules({"zone_edge_rules": {"demand_residents": "yes",
                                                "breakout_any_band": 1,
                                                "min_touches": 0, "extra": True}})
    assert junk == ZE.RULES_DEFAULT
    assert ZE.active_rules({"zone_edge_rules": {"min_touches": True}})["min_touches"] == 2
    wide = ZE.active_rules({"zone_edge_rules": {"demand_residents": True,
                                                "breakout_any_band": True,
                                                "min_touches": 1}})
    assert wide == {"demand_residents": True, "breakout_any_band": True, "min_touches": 1}


def test_wide_rules_buy_a_resident_and_any_band_breakout(env):
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row(arrival=False)],
                          breaking=[break_row(sym="BBB", new_highs=False)]),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,)),
               "BBB": zone_doc("BBB", supply_los=(150.0,))})
    out = ZE.run(cfg=_wide_cfg())
    assert out["rules"]["demand_residents"] is True
    assert out["rejected"] == 0
    assert sorted(c["symbol"] for c in enter_calls) == ["AAA", "BBB"]
    assert out["entered"][0] == "BBB", "breakouts still go first"


def test_strict_defaults_unchanged_when_rules_key_missing(env):
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row(arrival=False)],
                          breaking=[break_row(sym="BBB", new_highs=False)]),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,)),
               "BBB": zone_doc("BBB", supply_los=(150.0,))})
    out = ZE.run()
    assert out["rejected"] == 2
    _assert_never(db, enter_calls)


def test_min_touches_1_buys_a_single_touch_band_only_when_widened(env):
    row = demand_row(arrival=True)
    row["band"]["touches"] = 1
    _, db, enter_calls, _, _ = env(latest=latest_doc(near_demand=[row]),
                                   zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    out = ZE.run()
    assert out["rejected"] == 1 and not enter_calls
    out = ZE.run(cfg=_wide_cfg(demand_residents=False, breakout_any_band=False))
    assert out["rejected"] == 0 and [c["symbol"] for c in enter_calls] == ["AAA"]


def test_wide_ordering_arrivals_before_residents_by_band_quality():
    r_weak = demand_row(sym="WEAK", arrival=False); r_weak["band"]["touches"] = 2; r_weak["band"]["strength"] = 20.0
    r_strong = demand_row(sym="STRG", arrival=False); r_strong["band"]["touches"] = 6; r_strong["band"]["strength"] = 90.0
    r_arr = demand_row(sym="ARRV", arrival=True); r_arr["dist_pct"] = 0.9
    latest = latest_doc(near_demand=[r_weak, r_strong, r_arr],
                        breaking=[break_row(sym="BRK", new_highs=False)])
    cands, rejected = ZE.read_candidates(latest, ZE.active_rules(_wide_cfg()))
    assert rejected == []
    assert [c["symbol"] for c in cands] == ["BRK", "ARRV", "STRG", "WEAK"]
    strict, rej = ZE.read_candidates(latest)
    assert [c["symbol"] for c in strict] == ["ARRV"] and len(rej) == 3


def test_status_block_reports_active_rules(env):
    env(latest=latest_doc())
    blk = ZE.status_block(_wide_cfg())
    assert blk["active_rules"] == {"demand_residents": True, "breakout_any_band": True, "min_touches": 1}
    assert ZE.status_block(EE.get_config())["active_rules"] == ZE.RULES_DEFAULT


def test_api_config_accepts_zone_edge_rules_and_status_shows_them(env):
    fastapi = pytest.importorskip("fastapi")
    from trading import api as TA
    import auth
    admin = auth.HOUSE_OWNER_EMAIL
    env(latest=latest_doc(), flag=True)
    wide = {"demand_residents": True, "breakout_any_band": True, "min_touches": 1}
    resp = asyncio.run(TA.trading_config({"zone_edge_rules": wide}, email=admin))
    assert json.loads(resp.body) == {"zone_edge_rules": wide}
    assert EE.get_config()["zone_edge_rules"] == wide
    assert ZE.status_block(EE.get_config())["active_rules"] == wide
    # partial object keeps the strict default for the rest
    resp = asyncio.run(TA.trading_config({"zone_edge_rules": {"min_touches": 3}}, email=admin))
    assert json.loads(resp.body) == {"zone_edge_rules": {"min_touches": 3}}
    assert ZE.active_rules(EE.get_config()) == {"demand_residents": False,
                                                "breakout_any_band": False, "min_touches": 3}
    # null resets to STRICT
    resp = asyncio.run(TA.trading_config({"zone_edge_rules": None}, email=admin))
    assert json.loads(resp.body) == {"zone_edge_rules": {}}
    assert ZE.active_rules(EE.get_config()) == ZE.RULES_DEFAULT
    # NEGATIVES: wrong types, out-of-range, unknown keys, non-admin
    for bad in ({"demand_residents": "yes"}, {"min_touches": 0}, {"min_touches": True},
                {"min_touches": 11}, {"typo_key": True}, "wide", 7):
        with pytest.raises(fastapi.HTTPException) as exc:
            asyncio.run(TA.trading_config({"zone_edge_rules": bad}, email=admin))
        assert exc.value.status_code == 400, bad
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_config({"zone_edge_rules": wide}, email="nobody@example.com"))
    assert exc.value.status_code == 403



# ── 2026-09-05 review fixes (Ajay: "yes please fix the bugs") ───────────────
# Stop anchoring: the engine decided a LEVEL (band floor x 0.995); the placed
# stop must be that level whatever the tape printed by order time.

def test_stop_is_anchored_under_the_band_floor_when_the_live_print_drifts_up(env):
    """Signal print 100.00, band 98-99.5 -> owner stop 97.51. The order goes
    out ~1.5% higher (101.50). A percent-of-price hand-off would put the
    broker stop at 98.97 — INSIDE the band being bought. The placed stop
    must sit at the owner level, under band.lo."""
    fake, db, _, pushes, _ = env(
        latest=latest_doc(near_demand=[demand_row(last=100.0, lo=98.0, hi=99.5)]),
        zones={"AAA": zone_doc("AAA", supply_los=(130.0,))},
        real_enter=True, live_price=101.5)
    out = ZE.run()
    assert out["entered"] == ["AAA"], out
    assert len(fake.brackets) == 1
    placed = fake.brackets[0]["stop_price"]
    assert placed == pytest.approx(97.51, abs=0.005), placed
    assert placed < 98.0, "stop must be under the band floor, not inside the band"
    det = _kind_rows(db, "zone_entry")[0]["detail"]
    assert det["order"]["stop"]["stop_price"] == pytest.approx(97.51, abs=0.005)
    assert "stop 97.51" in pushes[0][3]


def test_stop_anchor_refused_when_drift_pushes_risk_past_the_ceiling(env):
    """Signal print 100.00, band floor 91 -> stop 90.545 = 9.46% (passes the
    local gate). By order time the print is 101.00 -> 10.35% to the level:
    past ABS_MAX_STOP_PCT. Refuse with a reason; never clamp the stop back
    up into the band and never place the order."""
    fake, db, _, pushes, _ = env(
        latest=latest_doc(near_demand=[demand_row(last=100.0, lo=91.0, hi=99.5,
                                                  dist_pct=0.5)]),
        zones={"AAA": zone_doc("AAA", supply_los=(150.0,))},
        real_enter=True, live_price=101.0)
    out = ZE.run()
    assert fake.brackets == [] and out["entered"] == [] and pushes == []
    assert out["blocked"] == ["AAA"]
    st = _state_rows(db)[0]
    assert st["result"] == "blocked"
    assert "90.5" in st["reason"] and "%g%%" % ABS_MAX_STOP_PCT in st["reason"], st["reason"]


def test_stop_anchor_refused_when_the_print_is_already_through_the_level(env):
    """The tape printed 97.00 by order time — under the 97.51 level. A stop
    above the entry is not a plan: refuse, no order."""
    fake, db, _, _, _ = env(
        latest=latest_doc(near_demand=[demand_row(last=100.0, lo=98.0, hi=99.5)]),
        zones={"AAA": zone_doc("AAA", supply_los=(130.0,))},
        real_enter=True, live_price=97.0)
    out = ZE.run()
    assert fake.brackets == [] and out["blocked"] == ["AAA"]
    assert "not below" in _state_rows(db)[0]["reason"]


def test_run_hands_entries_the_absolute_stop_level(env):
    _, _, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row()]),
        zones={"AAA": zone_doc("AAA", supply_los=(130.0,))})
    ZE.run()
    assert enter_calls[0]["stop_price"] == pytest.approx(97.51)
    assert enter_calls[0]["stop_pct"] == pytest.approx(2.49, abs=0.01)


# Room gate: the FIRST band overhead is kind-agnostic (broken demand above the
# print is resistance — the rule supply_watch.overhead_bands and
# bounce_room.first_overhead already apply), a print inside a supply band has
# zero room, and `need` is 2R of the stop the engine will actually PLACE.

def test_room_gate_counts_a_broken_demand_band_overhead(env):
    """last 100, band lo 95 -> stop 5.48%, need 10.95%. A DEMAND band 106-108
    sits 6% up (1.1R; past the 5% alert gate): broken support = resistance
    -> blocked 'room < 2R'."""
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row(lo=95.0)]),
        zones={"AAA": zone_doc("AAA", supply_los=(), demand_bands=((106.0, 108.0),))})
    out = ZE.run()
    assert enter_calls == [] and out["blocked"] == ["AAA"]
    blk = _kind_rows(db, "zone_entry_blocked")[0]["detail"]["room"]
    assert blk["reason"].startswith("room < %gR" % MIN_REWARD_RISK), blk
    assert blk["next_band"] == {"kind": "demand", "lo": 106.0, "hi": 108.0}
    assert blk["room_pct"] == pytest.approx(6.0)
    # a demand band BELOW or CONTAINING the print is support, never overhead
    ok, det = ZE.room_ok(100.0, 2.49, zone_doc("X", demand_bands=((90.0, 92.0), (99.0, 101.0))))
    assert ok is True and det["reason"] == "no band overhead"


def test_room_gate_blocks_a_print_inside_a_supply_band(env):
    ok, det = ZE.room_ok(100.0, 3.0, {"bands": [
        {"kind": "supply", "lo": 99.0, "hi": 104.0},
        {"kind": "supply", "lo": 90.0, "hi": 93.0}]})
    assert ok is False and det["room_pct"] == 0.0
    assert det["reason"].startswith("inside supply band"), det
    assert det["next_band"] == {"kind": "supply", "lo": 99.0, "hi": 104.0}
    # a supply band whose TOP is exactly at the print still contains it
    ok, det = ZE.room_ok(100.0, 3.0, {"bands": [{"kind": "supply", "lo": 96.0, "hi": 100.0}]})
    assert ok is False and "inside supply band" in det["reason"]
    # through the funnel: the demand row prints inside an overlapping lid
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row(last=99.5, lo=98.0, hi=100.0)]),
        zones={"AAA": {"symbol": "AAA", "date": DAY, "bands": [
            {"kind": "demand", "lo": 98.0, "hi": 100.0, "touches": 3},
            {"kind": "supply", "lo": 99.0, "hi": 104.0, "touches": 2}]}})
    out = ZE.run()
    # 2026-09-05: the alert gate sees the lid first -> a SKIP (re-read next
    # tick), the TRU class; never an order either way.
    assert enter_calls == [] and out["blocked"] == []
    assert out["skipped"][0]["reason"].startswith("alert gate: inside supply band 99-104")
    assert _state_rows(db) == []


def test_room_need_floors_at_the_engine_minimum_stop():
    """tier 'in': last 100, lo 99.6 -> requested 0.90%. risk_rules places
    1.0% (its floor), so 2R is 2.00% — a lid 1.9% up is NOT enough room."""
    stop, pct = ZE.stop_request(100.0, 99.6)
    assert pct == pytest.approx(0.9)
    ok, det = ZE.room_ok(100.0, pct, {"bands": [{"kind": "supply", "lo": 101.9, "hi": 103.0}]})
    assert ok is False and det["need_pct"] == pytest.approx(2.0), det
    ok, det = ZE.room_ok(100.0, pct, {"bands": [{"kind": "supply", "lo": 102.0, "hi": 103.0}]})
    assert ok is True and det["need_pct"] == pytest.approx(2.0)
    # a request wider than the floor is used as-is
    ok, det = ZE.room_ok(100.0, 2.49, {"bands": [{"kind": "supply", "lo": 104.98, "hi": 106.0}]})
    assert ok is True and det["need_pct"] == pytest.approx(4.98)


def test_rules_list_room_rule_names_broken_support_not_only_supply():
    room = [r for r in ZE.rules_list() if r["rule"].startswith("Room sanity")][0]
    assert "nearest supply floor above" not in room["rule"]
    assert "broken support" in room["rule"] and "inside a supply band" in room["rule"]


# ── integrator fixes 2026-09-05 (review of the 22-bug sweep) ─────────────────
def test_a_breakout_into_an_overlapping_supply_lid_never_skips_the_room_check():
    """Review 2026-09-05: zone_edge counted overhead as bands with lo > band.hi,
    so a supply band OVERLAPPING the broken one (99-104 over 96-99.5, print
    100) was invisible: new_highs True, overhead 0 -> _needs_room_check False
    -> the paper buy proceeded with the print INSIDE a supply band. The board
    payload now carries overhead 1 / new_highs False for that geometry, so
    room_ok runs and blocks it."""
    from supply_demand import zone_edge as SDZE
    bands = [{"kind": "supply", "lo": 96.0, "hi": 99.5, "touches": 3, "strength": 50.0},
             {"kind": "supply", "lo": 99.0, "hi": 104.0, "touches": 2, "strength": 50.0}]
    rb = SDZE.read_breaking(100.0, bands, 99.0)
    assert rb["tier"] == "broke" and rb["band"]["hi"] == 99.5
    assert rb["overhead_bands"] == 1 and rb["new_highs"] is False
    c = {"kind": "breakout", "new_highs": rb["new_highs"], "overhead_bands": rb["overhead_bands"]}
    assert ZE._needs_room_check(c) is True
    ok, room = ZE.room_ok(100.0, 1.0, {"bands": bands})
    assert ok is False and room["reason"].startswith("inside supply band (99-104)")
    # the skip itself is unchanged for a genuine breakout to new highs
    assert ZE._needs_room_check({"kind": "breakout", "new_highs": True, "overhead_bands": 0}) is False


# ── Phone gate = entry gate (Ajay 2026-09-05) ────────────────────────────────
# "What ever rules I created for the alerts are the ideal conditions for a
# stock to be bough in Autopilot." The alert_gates rules (>= 5% room to the
# first unbroken band overhead; demand print within 1% above the band top)
# are an AND on top of every existing gate. Rejections are SKIPS (re-read next
# tick — room can open), counted in skipped_alert_gate, with a race row.

def _tru_row():
    """TRU 2026-09-05: print 79.88 inside demand band 78.34-81.08 which
    CONTAINS a supply band 80.12-82.10 -> 0.3% room, R:R 0.09."""
    return demand_row(sym="TRU", last=79.88, lo=78.34, hi=81.08, tier="in",
                      arrival=True, dist_pct=0.0, touches=3)


def _tru_zone():
    return {"_id": "TRU:%s" % DAY, "symbol": "TRU", "date": DAY,
            "bands": [{"kind": "demand", "lo": 78.34, "hi": 81.08, "touches": 3},
                      {"kind": "supply", "lo": 80.12, "hi": 82.10, "touches": 2},
                      {"kind": "supply", "lo": 83.87, "hi": 85.00, "touches": 2}],
            "prev_close": 79.50, "high_252": 90.0}


def test_alert_gate_tru_shape_blocked_on_room(env):
    _, db, enter_calls, _, zone_reads = env(
        latest=latest_doc(near_demand=[_tru_row()]), zones={"TRU": _tru_zone()})
    out = ZE.run()
    assert enter_calls == []
    assert out["skipped"] == [{"symbol": "TRU",
                               "reason": "alert gate: room 0.30% < 5% (supply 80.12-82.1)"}]
    assert out["skipped_alert_gate"] == 1 and out["blocked"] == []
    assert zone_reads == ["TRU"]
    assert _state_rows(db) == []                       # a skip, not an attempt
    race = _race_rows(db)
    assert len(race) == 1 and race[0]["outcome"] == "skipped"
    assert race[0]["reason"].startswith("alert gate: room 0.30%")
    assert race[0]["gate"]["room"]["room_pct"] == 0.3
    out2 = ZE.run()                                    # re-evaluated, still skipped
    assert out2["skipped_alert_gate"] == 1 and enter_calls == []
    assert len(_race_rows(db)) == 1


def test_alert_gate_resident_in_band_with_8pct_room_passes(env):
    """demand_residents rule ON: a name sitting IN its band with the first
    supply 8% up passes both alert rules and enters as strategy demand_zone."""
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row(last=99.0, lo=98.0, hi=99.5,
                                                  tier="in", arrival=False, dist_pct=0.0)]),
        zones={"AAA": zone_doc("AAA", supply_los=(106.92,))})
    EE.update_config(zone_edge_rules={"demand_residents": True})
    out = ZE.run()
    assert out["entered"] == ["AAA"] and out["skipped_alert_gate"] == 0
    call = enter_calls[0]
    assert call["strategy"] == "demand_zone"
    r = call["reason"]
    assert r["side"] == "demand" and r["tier"] == "in"
    assert r["band"] == {"kind": "demand", "lo": 98.0, "hi": 99.5, "touches": 3, "strength": 1.5}
    assert r["gate"]["room"]["room_pct"] == 8.0 and r["gate"]["proximity"] is True
    assert r["room"]["reason"] == "ok"
    json.dumps(r, allow_nan=False)
    assert _kind_rows(db, "zone_entry")[0]["detail"]["gate"]["ok"] is True


def test_alert_gate_print_1_5pct_above_band_top_fails_proximity(env):
    """last 101.0 vs band top 99.5 = 1.5% above -> 'I am late' -> skipped."""
    _, db, enter_calls, _, _ = env(
        latest=latest_doc(near_demand=[demand_row(last=101.0, lo=98.0, hi=99.5, dist_pct=1.5)]),
        zones={"AAA": zone_doc("AAA", supply_los=(120.0,))})
    out = ZE.run()
    assert enter_calls == []
    assert out["skipped"] == [{"symbol": "AAA",
                               "reason": "alert gate: print 1.5% above demand band top "
                                         "99.5 (max 1%)"}]
    assert out["skipped_alert_gate"] == 1 and _state_rows(db) == []


def test_alert_gate_breakout_measures_to_the_next_band_above_the_broken_one(env):
    """Breakout through 102-103 at 103.5 (stop 101.49 = 1.94%, 2R needs 3.9%):
    next supply 3% up -> alert gate skip; 6% up -> passes (strategy breakout);
    nothing above -> passes. The cleared band is never its own lid."""
    row = break_row(last=103.5, lo=102.0, hi=103.0, overhead=1, dist_pct=-0.5)
    zone = {"_id": "BBB:%s" % DAY, "symbol": "BBB", "date": DAY, "prev_close": 102.5,
            "bands": [{"kind": "supply", "lo": 102.0, "hi": 103.0, "touches": 3},
                      {"kind": "supply", "lo": 106.605, "hi": 108.0, "touches": 2}]}
    _, db, enter_calls, _, _ = env(latest=latest_doc(breaking=[row]), zones={"BBB": zone})
    out = ZE.run()
    assert enter_calls == []
    assert out["skipped"][0]["reason"] == "alert gate: room 3.00% < 5% (supply 106.605-108)"
    zone["bands"][1] = {"kind": "supply", "lo": 109.71, "hi": 111.0, "touches": 2}
    _, db, enter_calls, _, _ = env(latest=latest_doc(breaking=[row]), zones={"BBB": zone})
    out = ZE.run()
    assert out["entered"] == ["BBB"]
    assert enter_calls[0]["strategy"] == "breakout"
    assert enter_calls[0]["reason"]["gate"]["room"]["room_pct"] == 6.0
    assert enter_calls[0]["reason"]["gate"]["proximity"] is None     # supply side: n/a
    zone["bands"] = zone["bands"][:1]
    _, db, enter_calls, _, _ = env(latest=latest_doc(breaking=[row]), zones={"BBB": zone})
    out = ZE.run()
    assert out["entered"] == ["BBB"]
    assert enter_calls[0]["reason"]["gate"]["room"] is None            # CLEAR


def test_alert_gate_pure_function_edges():
    """No doc -> the gate is UNKNOWN (falls through to the 2R gate's
    'room unknown' block); malformed bands fail closed; supply broken under
    prev_close is not overhead; demand row proximity under the floor fails."""
    c = ZE._candidate("demand", demand_row(last=100.0, lo=98.0, hi=99.5))
    assert ZE.alert_gate(c, None) is None
    assert ZE.alert_gate(c, {"bands": "nope"}) is None        # unknown -> 2R gate blocks
    assert ZE.alert_gate(c, {"bands": [None]}) is None
    doc = {"bands": [{"kind": "supply", "lo": 101.0, "hi": 102.0, "touches": 2}],
           "prev_close": 102.5}
    ok, d = ZE.alert_gate(c, doc)
    assert ok is True and d["room"] is None                # broken lid = support
    doc["prev_close"] = 100.5
    ok, d = ZE.alert_gate(c, doc)
    assert ok is False and d["reason"].startswith("alert gate: room 1.00% < 5%")
    c_low = ZE._candidate("demand", demand_row(last=97.0, lo=98.0, hi=99.5))
    ok, d = ZE.alert_gate(c_low, {"bands": [], "prev_close": 99.0})
    assert ok is False and "under" in d["reason"] and d["proximity"] is False


def test_status_block_counts_alert_gate_skips_today(env):
    _, db, _, _, _ = env(latest=latest_doc(near_demand=[_tru_row()]), zones={"TRU": _tru_zone()})
    ZE.run()
    blk = ZE.status_block(EE.get_config())
    assert blk["skipped_alert_gate_today"] == 1
    rules = " ".join(r["rule"] + r["value"] for r in blk["rules"])
    assert "5%" in rules and "1%" in rules and "alert" in rules.lower()


# ── proven lids (Ajay 2026-09-06, the KLAC lesson) ───────────────────────────
def test_room_ok_skips_an_unproven_lid_and_measures_to_the_next_proven_one():
    """KLAC 2026-09-02: print 169.50 inside a 1-touch / strength-32 supply band
    166.37-172.30 sitting on the demand band. room_ok read 'inside supply
    band' and the lane never bought; the next PROVEN lid is 191.11 (12.7%)."""
    bands = [{"kind": "demand", "lo": 164.60, "hi": 169.81, "touches": 3, "strength": 100.0},
             {"kind": "supply", "lo": 166.37, "hi": 172.30, "touches": 1, "strength": 32.0},
             {"kind": "supply", "lo": 191.11, "hi": 193.94, "touches": 2, "strength": 53.0}]
    ok, det = ZE.room_ok(169.50, 3.37, {"bands": bands})
    assert ok is True and det["reason"] == "ok" and det["room_pct"] == 12.75
    assert det["next_band"] == {"kind": "supply", "lo": 191.11, "hi": 193.94}
    proven = [dict(b, touches=2, strength=53.0) if b["lo"] == 166.37 else b for b in bands]
    ok2, det2 = ZE.room_ok(169.50, 3.37, {"bands": proven})
    assert ok2 is False and det2["reason"].startswith("inside supply band (166.37-172.3)")
    # a weak DEMAND band above the print is not resistance either
    weak_dem = {"kind": "demand", "lo": 175.0, "hi": 176.0, "touches": 1, "strength": 5.0}
    assert ZE.room_ok(169.50, 3.37, {"bands": bands + [weak_dem]})[1]["next_band"]["lo"] == 191.11
    # unknown touches keep the lid (conservative): a bare level still blocks
    assert ZE.room_ok(169.50, 3.37, {"bands": bands + [{"kind": "supply", "lo": 171.0}]})[0] is False
