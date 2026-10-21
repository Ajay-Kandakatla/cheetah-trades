"""🚩 Gajjala paper lane (2026-10-20, BUILD_SPEC17) — trading/gajjala_entry.py.

Ajay 2026-10-20: "in the autopilot can you stop rest of the strategies and only use the Gajjalas strategies please."

Locks: the owner numbers and the constants it imports (never retyped), the gate (switch / live broker / closed), the
read (today's pushed live A+ only — NEG every other claim shape), the claim (once per alert id, stale at first sight),
GG's trade math (entry = last x (1 + chase) on the grid once the tape trades the trigger, target = entry + 1R, stop =
the served stop, size by risk / notional / cash), every refusal (NEG each), the cut-off / flatten clock, the fill wait,
the exits (kind, P&L, R), the caps, the disarmed dry run (no order, no ledger row), the floors switch, the served text
(every number a constant, no b-word, no book), the tab payload contract and the API switches / routes.

v2 2026-10-21 (BUILD_SPEC19, Ajay "Follow full Gajjala … implement them exactly"): the pins v2 moved are updated in
place — a market OTO entry (no limit, no target), half of GG's 0.25% first, no stale / thin-R / dead / day cap, floors
default OFF, the earnings shield waived, the served `rules` object. GG's management rules (breakeven + add, the 9 EMA
trail, the partial, cooldown, drawdown) are in tests/test_gajjala_lane_gg_rules.py.

Hermetic: fake broker + fake Mongo (tests/test_trading_engine fakes + LaneColl), `_alert_docs`, `_live_last`,
`_now_et`, `_et_day`, `EN._live_price`, `SF.market_cap` and `sepa.earnings_watch` patched — no network.
"""
import asyncio
import json
import os
import re
import sys
import types
from datetime import date, datetime, time as dtime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from pymongo.errors import DuplicateKeyError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.entries as EN
import trading.exit_engine as EE
import trading.gajjala_entry as GL
import trading.safety_floor as SF
from chart_maps.gajjala import constants as GC
from tests.test_trading_engine import FakeBrokerModule, FakeCursor, FakeDB, _position

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
DAY = "2026-10-20"                                     # a Tuesday, a full session
NOW = datetime(2026, 10, 20, 10, 55, tzinfo=ET)
HALF_DAY = "2026-11-27"                                # supply_demand.timeframes.HALF_DAYS


# ── fakes ────────────────────────────────────────────────────────────────────────────────────────────────────────
class _Res:
    def __init__(self, n):
        self.matched_count = n
        self.modified_count = n


class LaneColl:
    """gajjala_lane: DuplicateKeyError on a repeat `_id`, update_one -> matched/modified counts, count_documents,
    $setOnInsert on upsert (BUILD_SPEC17 T5)."""

    def __init__(self, docs=()):
        self.rows = [dict(d) for d in docs]

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

    def find(self, q=None, *a, **k):
        return FakeCursor(dict(d) for d in self.rows if self._match(d, q))

    def find_one(self, q=None, *a, **k):
        for d in self.rows:
            if self._match(d, q):
                return dict(d)
        return None

    def insert_one(self, doc):
        if any(r.get("_id") == doc.get("_id") for r in self.rows):
            raise DuplicateKeyError("E11000 duplicate key %s" % doc.get("_id"))
        self.rows.append(dict(doc))

    def update_one(self, q, update, upsert=False):
        for d in self.rows:
            if self._match(d, q):
                d.update(update.get("$set") or {})
                return _Res(1)
        if upsert:
            base = {k: v for k, v in (q or {}).items() if not isinstance(v, dict)}
            base.update(update.get("$setOnInsert") or {})
            base.update(update.get("$set") or {})
            self.rows.append(base)
        return _Res(0)

    def count_documents(self, q):
        return sum(1 for d in self.rows if self._match(d, q))

    def get(self, _id):
        return next((d for d in self.rows if d.get("_id") == _id), None)


class GBroker(FakeBrokerModule):
    def __init__(self, positions=(), orders=(), closed=(), equity=100_000.0, cash=None, market_open=True,
                 mode="paper"):
        super().__init__(positions, orders, equity, market_open)
        self._closed = list(closed)
        self._cash = float(equity if cash is None else cash)
        self._mode = mode

    def mode(self):
        return self._mode

    def account(self):
        return {"equity": str(self._equity), "cash": str(self._cash), "buying_power": str(self._cash)}

    def closed_orders_since(self, iso_ts):
        return [dict(o) for o in self._closed]

    def submit_bracket(self, symbol, qty, take_profit_price, stop_price, **kw):
        self.calls.append(("submit_bracket", dict(symbol=symbol, qty=qty, take_profit_price=take_profit_price,
                                                  stop_price=stop_price, **kw)))
        return {"id": "brk-%d" % len(self.calls)}


def _at(day, hh, mm):
    return datetime.combine(date.fromisoformat(day), dtime(hh, mm), tzinfo=ET)


def alert(sym="SAIQ", setup="bull_flag", trig=4.46, stop=4.31, hm=(10, 52), day=DAY, state="pushed",
          prefix="GG:", suffix=""):
    at = _at(day, *hm).astimezone(UTC).isoformat()
    return {"_id": f"{prefix}{day}|{sym}|{setup}{suffix}", "date": day, "symbol": sym, "setup": setup,
            "state": state, "at": at, "trigger": trig, "stop": stop, "frame": "5m",
            "entry_bar_t": f"{day} {hm[0]:02d}:{hm[1] - 2:02d}", "kind": GC.PUSH_KIND, "mode": "live"}


@pytest.fixture
def lane(monkeypatch):
    def build(alerts=(), lasts=None, armed=True, positions=(), orders=(), closed=(), equity=100_000.0, cash=None,
              mode="paper", market_open=True, cfg=None, earnings_days=None, cap=2_000_000_000.0, now=NOW,
              docs=()):
        db = FakeDB(armed=armed)
        db.gajjala_lane = LaneColl(docs)
        db.gajjala_lane_state = LaneColl()                  # v2 2026-10-21 (D4/D5): risk_mult + the equity peak
        if cfg:
            db.trading_config.rows[0].update(cfg)
        brk = GBroker(positions, orders, closed, equity, cash, market_open, mode)
        for mod in (EE, EN, GL):
            monkeypatch.setattr(mod, "broker", brk)
        monkeypatch.setattr(EE, "_db", lambda: db)
        monkeypatch.setattr(EN, "_db", lambda: db)
        monkeypatch.setattr(EE, "regime", lambda: "normal")
        monkeypatch.setattr(EN, "regime", lambda: "normal")
        monkeypatch.setattr(EE, "_distribution_read", lambda sym: None)
        stub = types.ModuleType("sepa.earnings_watch")
        stub.next_event = (lambda s: None) if earnings_days is None else \
            (lambda s, _d=earnings_days: {"date": "2026-10-23", "days_to": _d})
        monkeypatch.setitem(sys.modules, "sepa.earnings_watch", stub)
        monkeypatch.setattr(SF, "market_cap", lambda sym: cap)
        monkeypatch.setattr(EN, "_live_price", lambda sym: (None, None))
        import chart_maps.gajjala.store as GST
        monkeypatch.setattr(GST, "broker_flags", lambda store: ((), False))
        state = SimpleNamespace(db=db, brk=brk, lasts=dict(lasts or {}), alerts=list(alerts), now=now)
        monkeypatch.setattr(GL, "_alert_docs", lambda day: list(state.alerts))
        monkeypatch.setattr(GL, "_live_last", lambda b, sym: (state.lasts.get(sym), "test"))
        monkeypatch.setattr(GL, "_now_et", lambda: state.now)
        monkeypatch.setattr(GL, "_et_day", lambda: state.now.date().isoformat())
        # v2 2026-10-21: the closed 5-minute bars and the halt ledger are seams (no Massive, no Mongo here); the
        # management rules have their own file (tests/test_gajjala_lane_gg_rules.py)
        monkeypatch.setattr(GL, "_bars5", lambda sym, day, now: None)
        monkeypatch.setattr(GL, "_halts_of", lambda day, sym: None)
        state.run = lambda at=None, **kw: GL.run(broker=brk, cfg=EE.get_config(), now=at or state.now, **kw)
        state.coll = db.gajjala_lane
        return state
    return build


def _rows(db, kind):
    return [r for r in db.trade_ledger.rows if r.get("kind") == kind]


def _lane_rows(db):
    return [r for r in db.trade_ledger.rows if str(r.get("kind") or "").startswith("gajjala")]


def _brackets(brk):
    return [kw for name, kw in brk.calls if name == "submit_bracket"]


def seed(**kw):
    base = {"_id": f"GG:{DAY}|SAIQ|bull_flag", "date": DAY, "symbol": "SAIQ", "setup": "bull_flag",
            "setup_label": "🚩 Bull Flag", "alert_at": _at(DAY, 10, 52).astimezone(UTC).isoformat(),
            "alert_et": "10:52", "trigger": 4.46, "stop": 4.31, "r": 0.15, "r_pct": 3.3632, "thin": False,
            "plan": "ok", "state": "waiting", "floors": "house", "floor_warnings": []}
    base.update(kw)
    return base


PLAN = {"trigger": 4.46, "stop": 4.31, "plan": "ok", "thin": False}


# ── owner numbers + the clock ────────────────────────────────────────────────────────────────────────────────────
def test_owner_numbers_and_imported_constants():
    from trading import zone_edge_entry as ZEE, zero_dte_lane as ZDL
    assert GL.WINDOW_OPEN_ET is GC.LEDGER_FILL_FROM_ET and GL.WINDOW_OPEN_ET == dtime(9, 45)
    assert GL.R_MULT is GC.LEDGER_R_MULT and GL.MIN_R_PCT is GC.LEDGER_MIN_R_PCT
    assert GL.flatten_et(date(2026, 10, 20)) == ZEE.QB_EOD_FLATTEN_ET == GL.flatten_et()
    assert GL.cutoff_et(date(2026, 10, 20)) == dtime(15, 30) == GL.cutoff_et()
    assert GL.GAJJALA_FILL_WAIT_SEC == ZDL.ENTRY_FILL_WAIT_SEC
    assert GL.STRATEGY == "gajjala" and GL.LANE_COLL == "gajjala_lane" and GL.DEFAULT_ON is True
    # v2 2026-10-21 (BUILD_SPEC19 D3 / D4 / D7): GG's 0.25%, no day cap, no stale line, no chase limit
    assert (GL.GAJJALA_RISK_PCT, GL.GAJJALA_MAX_NOTIONAL_PCT, GL.GAJJALA_MAX_ENTRIES_PER_DAY, GL.GAJJALA_MAX_OPEN) \
        == (0.25, 10.0, None, 3)
    assert (GL.GAJJALA_SIGNAL_MAX_AGE_MIN, GL.GAJJALA_CHASE_PCT, GL.GAJJALA_MAX_ROUND_R_PCT) == (None, None, 10.0)
    assert GL.GAJJALA_MISSED_R == 1.0
    from trading import broker as BF
    assert GL.round_price is BF.round_price and GL.MIN_STOP_GAP_USD == BF.MIN_STOP_GAP_USD == 0.01
    assert set(GL.SKIP_KINDS) >= {"floor", "never_triggered", "disarmed", "broker_gap", "rounding", "cooldown", "halt"}
    assert not set(GL.SKIP_KINDS) & {"stale", "thin_r", "dead", "cap_day"}           # v2: removed (D3 / D7)


def test_half_day_cutoff_1230_flatten_1255():
    d = date.fromisoformat(HALF_DAY)
    assert GL.cutoff_et(d) == dtime(12, 30) and GL.flatten_et(d) == dtime(12, 55)
    assert GL.cutoff_et(HALF_DAY) == dtime(12, 30)
    assert GL.in_entry_window(_at(HALF_DAY, 12, 29)) and not GL.in_entry_window(_at(HALF_DAY, 12, 30))
    assert GL.in_entry_window(_at(DAY, 12, 30))                 # NEG: a full day is still open at 12:30


def test_gate_flag_off_live_closed_each_refuse():
    ok = GL.gate({"gajjala_entry": True}, "paper", True)
    assert ok["ok"] and ok["why"] is None
    assert GL.gate({}, "paper", True)["ok"]                     # default ON
    assert GL.gate({"gajjala_entry": None}, "sim", True)["ok"]
    off = GL.gate({"gajjala_entry": False}, "paper", True)
    assert not off["ok"] and off["why"] == "lane switched off"
    live = GL.gate({"gajjala_entry": True}, "live", True)
    assert not live["ok"] and live["why"] == "live broker — this lane is paper only" and not live["paper"]
    closed = GL.gate({"gajjala_entry": True}, "paper", False)
    assert not closed["ok"] and closed["why"] == "market closed"


def test_live_broker_one_disabled_row_a_day(lane):
    s = lane(alerts=[alert()], lasts={"SAIQ": 4.48}, mode="live")
    out1 = s.run()
    out2 = s.run()
    assert not out1["ran"] and not out2["ran"]
    rows = _rows(s.db, "gajjala_disabled")
    assert len(rows) == 1 and rows[0]["dry_run"] is True and rows[0]["cite"] == GL.CITE
    assert EE.get_config()["last_gajjala_disabled_day"] == DAY
    assert _brackets(s.brk) == [] and s.coll.rows == []
    s2 = lane(alerts=[alert()], cfg={"gajjala_entry": False}, mode="live")
    s2.run()
    assert _rows(s2.db, "gajjala_disabled") == []               # NEG: switched off is not "disabled by live"


def test_window_edges_0944_0945_1529_1530():
    assert not GL.in_entry_window(_at(DAY, 9, 44))
    assert GL.in_entry_window(_at(DAY, 9, 45))
    assert GL.in_entry_window(_at(DAY, 15, 29))
    assert not GL.in_entry_window(_at(DAY, 15, 30))
    assert not GL.in_entry_window(_at(DAY, 16, 30))             # after-hours A+ do push; the lane never trades them


# ── the read + the claim ─────────────────────────────────────────────────────────────────────────────────────────
def test_only_pushed_live_claims_are_read(lane):
    yday = "2026-10-19"
    alerts = [alert("SAIQ"),
              alert("SHA", prefix="SHADOW:GG:", state="shadow"),
              alert("SUP", suffix="#suppressed_first15", state="suppressed_first15"),
              alert("CLM", state="claimed"), alert("FAI", state="failed"), alert("NOT", state="no_target"),
              alert("RPL", prefix="REPLAY:"),
              alert("YDY", day=yday, hm=(10, 50))]
    s = lane(alerts=alerts, lasts={})
    out = s.run()
    assert out["claimed"] == 1
    assert [d["_id"] for d in s.coll.rows] == [f"GG:{DAY}|SAIQ|bull_flag"]


def test_claim_once_per_alert_id(lane, monkeypatch):
    s = lane(alerts=[alert()], lasts={})
    assert s.run()["claimed"] == 1
    assert s.run()["claimed"] == 0
    assert len(s.coll.rows) == 1
    # a racing tick that did not see the doc: the insert raises DuplicateKeyError and is a no-op
    monkeypatch.setattr(GL, "_find", lambda coll, q: [] if q.get("date") == DAY and "state" not in q
                        else [dict(d) for d in coll.find(q)])
    out = s.run()
    assert out["claimed"] == 0 and len(s.coll.rows) == 1 and out["ok"]


def test_stale_21_min_refused_19_min_claimed(lane):
    """v2 2026-10-21 (D7): the stale line was mine — an alert first seen 21 min after it rang still waits."""
    s = lane(alerts=[alert("OLD", hm=(10, 34)), alert("NEW", hm=(10, 36))], lasts={})
    out = s.run()                                                # now 10:55 → 21 and 19 minutes
    assert out["claimed"] == 2
    old = s.coll.get(f"GG:{DAY}|OLD|bull_flag")
    new = s.coll.get(f"GG:{DAY}|NEW|bull_flag")
    assert old["state"] == "waiting" and old["skip_kind"] is None
    assert new["state"] == "waiting" and new["skip_kind"] is None
    assert _rows(s.db, "gajjala_skip") == []


# ── GG's trade math ──────────────────────────────────────────────────────────────────────────────────────────────
def test_plan_risk_qty():
    p = GL.entry_plan({"trigger": 10.0, "stop": 9.0, "plan": "ok"}, 10.0, 100_000, 100_000)
    assert p["ok"] and p["entry"] == 10.0 and p["stop"] == 9.0 and p["target"] is None
    assert p["full_qty"] == int(100_000 * 0.0025 / 1.0) == 250                  # the risk binds
    assert p["qty"] == p["half_qty"] == 125 and p["add_qty"] == 125
    assert p["risk_usd"] == 125.0 and p["full_risk_usd"] == 250.0 and p["risk_pct"] == 0.25


def test_plan_notional_cap_saiq_2217():
    p = GL.entry_plan(PLAN, 4.48, 100_000, 100_000)
    assert (p["entry"], p["target"], p["stop"]) == (4.48, None, 4.31)
    assert p["full_qty"] == int(250 / 0.17) == 1470 and p["qty"] == 735
    assert p["risk_usd"] == round(735 * 0.17, 2) and p["notional"] == round(735 * 4.48, 2)
    tight = GL.entry_plan({"trigger": 4.46, "stop": 4.45, "plan": "ok"}, 4.46, 100_000, 100_000)
    assert tight["full_qty"] == int(10_000 / 4.46) == 2242 and tight["qty"] == 1121    # the 10% notional cap binds
    assert tight["full_qty"] < int(250 / 0.01)                                         # NEG: the risk alone would buy 25000


def test_plan_cash_cap():
    p = GL.entry_plan(PLAN, 4.48, 100_000, 500)
    assert p["ok"] and p["full_qty"] == int(500 / 4.48) == 111 and p["qty"] == 55


def test_plan_zero_shares_refused():
    p = GL.entry_plan(PLAN, 4.48, 100_000, 1.0)
    assert not p["ok"] and p["skip_kind"] == "size" and p["why"] == "0 shares fit the risk, the notional cap and the cash"
    assert GL.entry_plan(PLAN, 4.48, None, None)["skip_kind"] == "size"


def test_bracket_target_is_entry_plus_1R_stop_is_served(lane):
    """v2 (D7 / D8d): a MARKET entry, OTO — the served stop as its only leg, no take-profit."""
    p = GL.entry_plan(PLAN, 4.50, 100_000, 100_000)
    assert p["entry"] == 4.50 and p["target"] is None and p["stop"] == 4.31
    s = lane(alerts=[alert()], lasts={"SAIQ": 4.50})
    s.run()
    (br,) = _brackets(s.brk)
    assert (br["limit_price"], br["take_profit_price"], br["stop_price"]) == (None, None, 4.31)
    assert br["order_class"] == "oto" and br["tif"] == "day" and br["qty"] == p["qty"]


def test_drma_sub_dollar_four_decimals():
    p = GL.entry_plan({"trigger": 0.8744, "stop": 0.861, "plan": "ok"}, 0.879, 100_000, 100_000)
    assert p["ok"] and (p["entry"], p["target"], p["stop"]) == (0.879, None, 0.861)
    assert p["full_qty"] == int(10_000 / 0.879) == 11376 and p["qty"] == 5688
    assert p["risk_usd"] == round(5688 * 0.018, 2) and p["stop_shift_pct_r"] == 0.0
    # NEG: the old 2-decimal grid would have put the stop at 0.86, a cent under the served 0.861
    assert round(0.861, 2) == 0.86 and GL.round_price(0.861, "down") == 0.861


def test_rounding_shift_refused():
    p = GL.entry_plan({"trigger": 2.00, "stop": 1.9849, "plan": "ok"}, 2.00, 100_000, 100_000)
    assert not p["ok"] and p["skip_kind"] == "rounding"
    assert p["why"] == "the broker's price grid moves the stop by 32% of R — over the 10% line"
    ok = GL.entry_plan({"trigger": 2.00, "stop": 1.90, "plan": "ok"}, 2.00, 100_000, 100_000)
    assert ok["ok"]                                                   # NEG: an on-grid stop passes


def test_hodo_broker_gap_refused():
    p = GL.entry_plan({"trigger": 0.0753, "stop": 0.0709, "plan": "ok"}, 0.0755, 100_000, 100_000)
    assert not p["ok"] and p["skip_kind"] == "broker_gap"
    assert p["why"] == "the stop 0.0709 is under $0.01 below the last 0.0755 — Alpaca refuses a stop that tight"


def test_missed_dead_thin_no_plan_no_risk_each_refused():
    m = GL.entry_plan(PLAN, 4.62, 100_000, 100_000)                    # past 4.61 = trigger + 1R
    assert m["skip_kind"] == "missed"
    assert m["why"] == "last 4.62 is past +1R (4.61) — the move went without us"
    assert GL.entry_plan(PLAN, 4.61, 100_000, 100_000)["ok"]          # NEG: AT +1R still trades
    d = GL.entry_plan(PLAN, 4.31, 100_000, 100_000)
    assert d["skip_kind"] == "never_triggered"
    assert d["why"] == "last 4.31 is at or under the stop 4.31 — the break failed back into its range (GG: out)"
    t = GL.entry_plan({"trigger": 10.0, "stop": 9.96, "plan": "ok", "thin": True}, 10.0, 100_000, 100_000)
    assert t["ok"] and t["skip_kind"] is None                         # v2 (D7): no thin-R refusal (GG: tight R always)
    n = GL.entry_plan({"trigger": None, "stop": 4.31, "plan": "no_plan"}, 4.5, 100_000, 100_000)
    assert n["skip_kind"] == "no_plan" and n["why"] == "the alert carries no usable trigger and stop"
    z = GL.entry_plan({"trigger": 4.31, "stop": 4.31, "plan": "no_risk"}, 4.5, 100_000, 100_000)
    assert z["skip_kind"] == "no_risk" and z["why"] == "trigger equals the stop — no risk to size"
    w = GL.entry_plan(PLAN, 4.45, 100_000, 100_000)
    assert w["waiting"] and not w["ok"] and w["skip_kind"] is None
    assert GL.entry_plan(PLAN, None, 100_000, 100_000)["waiting"]


def test_waiting_then_orders_when_the_tape_trades_the_trigger(lane):
    s = lane(alerts=[alert()], lasts={"SAIQ": 4.40})
    out = s.run()
    assert out["waiting"] == 1 and _brackets(s.brk) == []
    assert s.coll.rows[0]["state"] == "waiting"
    s.lasts["SAIQ"] = 4.48
    s.now = NOW + timedelta(minutes=1)
    out = s.run()
    assert out["ordered"] == 1
    (br,) = _brackets(s.brk)
    assert (br["limit_price"], br["qty"], br["order_class"]) == (None, 735, "oto")
    d = s.coll.rows[0]
    assert d["state"] == "ordered" and d["order_id"] == "brk-1" and d["client_order_id"] == "test-SAIQ-gg-bull_flag"
    assert d["ordered_et"] == "10:56" and d["full_qty"] == 1470 and d["half_qty"] == 735
    assert len(_rows(s.db, "gajjala_entry")) == 1 and len(_rows(s.db, "entry")) == 1


def test_waiting_at_cutoff_never_triggered(lane):
    s = lane(docs=[seed()], lasts={"SAIQ": 4.40}, now=_at(DAY, 15, 29))
    s.run()
    assert s.coll.rows[0]["state"] == "waiting"                       # NEG: 15:29 still waits
    s.now = _at(DAY, 15, 30)
    s.run()
    d = s.coll.rows[0]
    assert d["state"] == "unfilled" and d["skip_kind"] == "never_triggered"
    assert d["why"] == "the tape never traded 4.46 by 15:30 ET"
    assert GL.fate_text(d) == "not filled — the tape never traded 4.46 by 15:30 ET"
    assert _brackets(s.brk) == []


# ── the floors switch ────────────────────────────────────────────────────────────────────────────────────────────
def test_floors_on_skip_and_count_a_087_name(lane):
    a = alert("DRMA", "intraday_vcp", 0.8744, 0.861, hm=(10, 50))
    s = lane(alerts=[a], lasts={"DRMA": 0.879}, cap=None, cfg={"gajjala_floors": True})   # v2: ON is his switch
    s.run()
    d = s.coll.rows[0]
    assert d["state"] == "skipped" and d["skip_kind"] == "floor"
    assert d["why"].startswith("house safety floors: share price $0.88 is under the $2.00 penny floor")
    assert d["floor_warnings"] == ["market cap unknown — the size floor could not be checked"]
    assert _brackets(s.brk) == []                                      # NEG: no order
    st = GL.status_block(EE.get_config())
    assert st["skipped_floor_today"] == 1 and st["skipped_floor_text"] == "1 skipped by the floors today"
    assert st["skipped_today"] == {"floor": 1}


def test_floors_off_passes_gg_and_the_entry_row_records_the_waiver(lane):
    a = alert("DRMA", "intraday_vcp", 0.8744, 0.861, hm=(10, 50))
    s = lane(alerts=[a], lasts={"DRMA": 0.879}, cap=5_000_000.0)       # v2 (D1): the default is OFF
    s.run()
    d = s.coll.rows[0]
    assert d["state"] == "ordered" and d["floors"] == "gg"
    assert any(w.startswith("waived by gajjala_floors=false: share price $0.88") for w in d["floor_warnings"])
    (br,) = _brackets(s.brk)
    assert (br["limit_price"], br["take_profit_price"], br["stop_price"], br["qty"]) == (None, None, 0.861, 5688)
    entry = _rows(s.db, "entry")[0]["detail"]
    assert entry["overrides"]["floors"] == "gg" and len(entry["overrides"]["floor_blocks_waived"]) == 2
    assert entry["strategy"] == "gajjala" and entry["order_class"] == "oto" and entry["target_price"] is None
    st = GL.status_block(EE.get_config())
    assert st["floors"] == "gg" and st["floors_flip"] == 'POST /trading/config {"gajjala_floors": true}'


# ── fill wait, cut-off, partial fills ────────────────────────────────────────────────────────────────────────────
def _ordered(sent_at, **kw):
    return seed(state="ordered", order_id="o-1", qty=2217, entry=4.51, target=4.66, stop_px=4.31,
                ordered_at=sent_at.astimezone(UTC).isoformat(), ordered_et=sent_at.strftime("%H:%M"), **kw)


def _working(**kw):
    o = {"id": "o-1", "symbol": "SAIQ", "side": "buy", "type": "limit", "status": "new", "filled_qty": "0"}
    o.update(kw)
    return o


def test_unfilled_after_180s_cancelled_no_retry(lane):
    sent = NOW - timedelta(seconds=179)
    s = lane(docs=[_ordered(sent)], orders=[_working()], lasts={"SAIQ": 4.55})
    s.run()
    assert s.coll.rows[0]["state"] == "ordered" and not [c for c in s.brk.calls if c[0] == "cancel_order"]   # NEG
    s.now = sent + timedelta(seconds=181)
    s.run()
    d = s.coll.rows[0]
    assert d["state"] == "unfilled" and d["why"] == "not filled in 180 s — cancelled, no retry"
    assert [c[1]["order_id"] for c in s.brk.calls if c[0] == "cancel_order"] == ["o-1"]
    assert len(_rows(s.db, "gajjala_cancel")) == 1
    s.alerts = [alert()]
    s.now += timedelta(minutes=1)
    s.run()
    assert _brackets(s.brk) == [] and s.coll.rows[0]["state"] == "unfilled"   # no retry


def test_ordered_at_cutoff_cancelled(lane):
    sent = _at(DAY, 15, 29, ) + timedelta(seconds=30)
    s = lane(docs=[_ordered(sent)], orders=[_working()], now=_at(DAY, 15, 30))
    s.run()
    d = s.coll.rows[0]
    assert d["state"] == "unfilled" and d["why"] == "still unfilled at the 15:30 ET cut-off — cancelled"


def test_partial_fill_on_cancel_is_open_with_filled_qty(lane):
    sent = NOW - timedelta(seconds=200)
    s = lane(docs=[_ordered(sent)], orders=[_working(status="partially_filled", filled_qty="500",
                                                     filled_avg_price="4.50", filled_at=NOW.isoformat())])
    s.run()
    d = s.coll.rows[0]
    assert d["state"] == "open" and d["fill_qty"] == 500 and d["qty"] == 500 and d["fill_px"] == 4.5
    assert GL.fate_text(d).startswith("filled 500 @ 4.50 at 10:55 ET")


def test_fill_moves_ordered_to_open(lane):
    s = lane(docs=[_ordered(NOW - timedelta(seconds=30))],
             closed=[_working(status="filled", filled_qty="2217", filled_avg_price="4.49",
                              filled_at=_at(DAY, 10, 53).astimezone(UTC).isoformat())])
    out = s.run()
    d = s.coll.rows[0]
    assert out["filled"] == 1 and d["state"] == "open" and d["fill_px"] == 4.49 and d["fill_et"] == "10:53"
    assert GL.fate_text(d) == "filled 2,217 @ 4.49 at 10:53 ET · target 4.66 · stop 4.31"


# ── the close-of-day clock + exits ───────────────────────────────────────────────────────────────────────────────
def _open(**kw):
    base = dict(state="open", order_id="o-1", qty=2217, fill_qty=2217, fill_px=4.49, fill_et="10:53",
                fill_t=_at(DAY, 10, 53).astimezone(UTC).isoformat(), entry=4.51, target=4.66, stop_px=4.31)
    base.update(kw)
    return seed(**base)


def test_flatten_1555_not_1554(lane):
    s = lane(docs=[_open()], positions=[_position("SAIQ", 2217, 4.49, 4.55)], now=_at(DAY, 15, 54))
    s.run()
    assert s.coll.rows[0]["state"] == "open"
    assert not [c for c in s.brk.calls if c[0] == "close_position"]   # NEG
    s.now = _at(DAY, 15, 55)
    s.run()
    d = s.coll.rows[0]
    assert d["state"] == "closing" and d["exit_kind"] == "flatten"
    assert [c[1]["symbol"] for c in s.brk.calls if c[0] == "close_position"] == ["SAIQ"]
    fl = _rows(s.db, "flatten")[0]
    assert fl["detail"]["reason"] == "🚩 Gajjala lane: same-session close at 15:55 ET"


def test_carried_doc_flattened_next_tick(lane):
    yday = "2026-10-19"
    s = lane(docs=[_open(_id=f"GG:{yday}|SAIQ|bull_flag", date=yday)],
             positions=[_position("SAIQ", 2217, 4.49, 4.40)], now=_at(DAY, 9, 31))
    s.run()
    d = s.coll.rows[0]
    assert d["state"] == "closing" and d["exit_kind"] == "carried"
    assert _rows(s.db, "flatten")[0]["detail"]["reason"] == "🚩 Gajjala lane: carried past its session"


def _sell(typ, px, hm):
    return {"id": "s-" + typ, "symbol": "SAIQ", "side": "sell", "type": typ, "status": "filled",
            "filled_avg_price": str(px), "filled_qty": "2217", "filled_at": _at(DAY, *hm).astimezone(UTC).isoformat()}


def test_exit_kinds_target_stop_flatten_pnl_and_r(lane):
    s = lane(docs=[_open()], closed=[_sell("limit", 4.66, (11, 31))])
    s.run()
    d = s.coll.rows[0]
    assert d["state"] == "closed" and d["exit_kind"] == "target" and d["exit_px"] == 4.66 and d["exit_et"] == "11:31"
    assert d["pnl_usd"] == round((4.66 - 4.49) * 2217, 2) and d["r_mult"] == 1.13
    assert GL.fate_text(d) == "target 4.66 at 11:31 ET · +$376.89 · +1.13R"
    assert len(_rows(s.db, "gajjala_exit")) == 1
    s = lane(docs=[_open()], closed=[_sell("stop", 4.31, (11, 2))])
    s.run()
    d = s.coll.rows[0]
    assert d["exit_kind"] == "stop" and d["pnl_usd"] == round((4.31 - 4.49) * 2217, 2) and d["r_mult"] == -1.2
    assert GL.fate_text(d) == "stop 4.31 at 11:02 ET · −$399.06 · -1.20R"
    s = lane(docs=[_open(state="closing", exit_kind="flatten")], closed=[_sell("market", 4.55, (15, 55))],
             now=_at(DAY, 15, 56))
    s.run()
    d = s.coll.rows[0]
    assert d["state"] == "closed" and d["exit_kind"] == "flatten" and d["r_mult"] == 0.4
    assert GL.fate_text(d).startswith("flattened 4.55 at 15:55 ET · +$133.02")
    # JBDI (§2): +1.25R
    assert GL.r_multiple(2.59, 2.49, 2.48, 2.40) == 1.25 and GL.pnl_of(2.59, 2.49, 3984) == 398.4
    # NEG: an older sell (before the fill) is never this trade's exit
    s = lane(docs=[_open()], closed=[_sell("limit", 4.66, (10, 40))])
    s.run()
    assert s.coll.rows[0]["exit_kind"] == "flatten" and s.coll.rows[0]["exit_px"] is None


# ── caps, disarmed, refusals from the chokepoint ─────────────────────────────────────────────────────────────────
def test_caps_day_open_held_terminal(lane):
    """v2 (D3): no day cap — four alerts, three open (GAJJALA_MAX_OPEN), the fourth `cap_open`."""
    a = [alert("AAA", hm=(10, 50)), alert("BBB", hm=(10, 51)), alert("CCC", hm=(10, 52)),
         alert("DDD", hm=(10, 53))]
    s = lane(alerts=a, lasts={k: 4.48 for k in ("AAA", "BBB", "CCC", "DDD")})
    s.run()
    st = {d["symbol"]: d for d in s.coll.rows}
    assert [st[k]["state"] for k in ("AAA", "BBB", "CCC")] == ["ordered"] * 3
    assert st["DDD"]["state"] == "skipped" and st["DDD"]["skip_kind"] == "cap_open"
    assert st["DDD"]["why"] == "3 lane positions open already"
    # cap_open: 3 lane positions open from yesterday, a fresh alert today
    yday = "2026-10-19"
    docs = [_open(_id=f"GG:{yday}|O{i}|bull_flag", date=yday, symbol=f"O{i}") for i in range(3)]
    s = lane(alerts=[alert("EEE", hm=(9, 48))], lasts={"EEE": 4.48}, docs=docs,
             positions=[_position(f"O{i}", 10, 4.49, 4.5) for i in range(3)], now=_at(DAY, 9, 50))
    monkey_flatten = []
    EE_flatten = EE.flatten
    try:
        EE.flatten = lambda sym, reason=None: monkey_flatten.append(sym) or {"dry_run": True}
        s.run()
    finally:
        EE.flatten = EE_flatten
    e = s.coll.get(f"GG:{DAY}|EEE|bull_flag")
    assert e["skip_kind"] == "cap_open" and e["why"] == "3 lane positions open already"
    # held: already in the account
    s = lane(alerts=[alert("FFF")], lasts={"FFF": 4.48}, positions=[_position("FFF", 10, 4.0, 4.5)])
    s.run()
    f = s.coll.rows[0]
    assert f["skip_kind"] == "held" and f["why"] == "already holding FFF" and _brackets(s.brk) == []
    s.lasts["FFF"] = 4.50
    s.now += timedelta(minutes=1)
    s.run()
    assert s.coll.rows[0]["skip_kind"] == "held" and _brackets(s.brk) == []        # terminal


def test_disarmed_dry_run_no_order_no_ledger_row(lane):
    s = lane(alerts=[alert()], lasts={"SAIQ": 4.48}, armed=False)
    out = s.run()
    d = s.coll.rows[0]
    assert d["state"] == "dry_run" and d["skip_kind"] == "disarmed" and out["dry_run"] == 1
    assert d["why"] == "disarmed — would have bought 735 at market (last 4.48); nothing sent"
    assert GL.fate_text(d) == d["why"]
    assert s.brk.calls == [] and _lane_rows(s.db) == [] and _rows(s.db, "entry") == []


def test_earnings_refusal_classified(lane):
    """v2 (D2, VR 0.7): GG has no earnings gate — the lane passes allow_earnings=True and still buys."""
    s = lane(alerts=[alert()], lasts={"SAIQ": 4.48}, earnings_days=3)
    s.run()
    d = s.coll.rows[0]
    assert d["state"] == "ordered" and d["skip_kind"] is None
    assert _rows(s.db, "entry")[0]["detail"]["allow_earnings"] is True
    assert GL._classify_refusal("earnings in 3d (2026-10-23)") == "earnings"
    assert GL._classify_refusal("share price $1.00 is under the $2.00 penny floor") == "floor"
    assert GL._classify_refusal("market cap $5M is under the $700M floor") == "floor"
    assert GL._classify_refusal("portfolio full: 5/5 positions (p.312)") == "blocked"
    assert len(_brackets(s.brk)) == 1


def test_enter_called_with_the_lane_plan(lane, monkeypatch):
    calls = []
    monkeypatch.setattr(GL.TE, "enter", lambda sym, **kw: calls.append((sym, kw)) or
                        {"order_id": "x-1", "client_order_id": "cid"})
    s = lane(alerts=[alert(setup="kiss_fly", trig=2.48, stop=2.40, sym="JBDI")], lasts={"JBDI": 2.49})
    s.run()
    (sym, kw), = calls
    assert sym == "JBDI"
    assert kw["tif"] == "day" and kw["order_intent"] == "gg-kiss_fly" and kw["strategy"] == "gajjala"
    assert (kw["limit_price"], kw["stop_price"]) == (None, 2.40) and "target_price" not in kw
    assert kw["order_class"] == "oto" and kw["ceiling"] == "gg" and kw["allow_earnings"] is True
    assert kw["sizing"]["qty"] == 1388 and kw["sizing"]["full_qty"] == 2777 and kw["sizing"]["price"] == 2.49
    assert kw["sizing"]["basis"] == "gg_risk_pct" and kw["sizing"]["risk_usd"] == 124.92
    assert kw["floors"] == "gg"
    r = kw["reason"]
    assert r["lane"] == "gajjala" and r["alert_id"] == f"GG:{DAY}|JBDI|kiss_fly" and r["alert_at"] == "10:52"
    assert r["cite"] == GL.CITE and (r["trigger"], r["stop"]) == (2.48, 2.40)


def test_close_now_needs_armed_and_a_position(lane):
    s = lane(docs=[_open()], positions=[_position("SAIQ", 2217, 4.49, 4.55)], armed=False)
    with pytest.raises(ValueError, match="engine not armed"):
        GL.close_now("SAIQ")
    s = lane(docs=[_open()], positions=[_position("SAIQ", 2217, 4.49, 4.55)])
    with pytest.raises(ValueError, match="no open 🚩 Gajjala position on XYZ"):
        GL.close_now("xyz")
    out = GL.close_now("saiq")
    assert out == {"ok": True, "state": "closing", "symbol": "SAIQ", "errors": []}
    assert s.coll.rows[0]["state"] == "closing" and s.coll.rows[0]["exit_kind"] == "owner"
    s = lane(docs=[_ordered(NOW - timedelta(seconds=30))], orders=[_working()])
    out = GL.close_now("SAIQ")
    assert out["state"] == "unfilled" and s.coll.rows[0]["why"] == "owner cancelled"
    assert [c[1]["order_id"] for c in s.brk.calls if c[0] == "cancel_order"] == ["o-1"]


def test_a_crash_inside_the_lane_never_raises(lane, monkeypatch):
    s = lane(alerts=[alert()], lasts={"SAIQ": 4.48})
    monkeypatch.setattr(GL, "_alert_docs", lambda day: (_ for _ in ()).throw(RuntimeError("boom")))
    out = s.run()
    assert out["ok"] is False and any("boom" in e for e in out["errors"])
    monkeypatch.setattr(GL, "_alert_docs", lambda day: None)
    out = s.run()
    assert out["ok"] and "the 🚩 A+ alerts could not be read" in out["errors"]
    monkeypatch.setattr(GL, "run", lambda **kw: (_ for _ in ()).throw(RuntimeError("lane down")))
    summary = EE.tick()
    assert "gajjala_lane: lane down" in summary["errors"]
    assert "gajjala_lane" in EE.status()


def test_tick_runs_the_lane_after_the_other_lanes(lane):
    s = lane(alerts=[alert()], lasts={"SAIQ": 4.48})
    summary = EE.tick()
    assert summary["gajjala_lane"]["ordered"] == 1 and summary["gajjala_lane"]["ran"]


# ── served text ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_status_block_shape_and_flip_line(lane):
    lane()
    st = GL.status_block(EE.get_config())
    assert set(st) == {"strategy", "enabled", "paper", "floors", "floors_text", "floors_flip",
                       "floors_off_confirm_text", "skipped_floor_today", "skipped_floor_text", "skipped_today",
                       "entries_today", "max_per_day", "open_n", "max_open", "caps_text", "window", "flatten_at",
                       "settings", "rules", "unmeasured_text", "streak_text", "track_record_text",
                       "track_record_url", "empty_today_text", "disabled_text", "live_text"}
    assert st["floors"] == "gg" and st["floors_flip"] == 'POST /trading/config {"gajjala_floors": true}'
    assert st["floors_text"] == ("OFF by default (your call 2026-10-21): the house $2 / $700M floors do not apply "
                                 "to GG's lane")
    house = GL.status_block({"gajjala_entry": True, "gajjala_floors": True})
    assert house["floors"] == "house" and house["floors_flip"] == 'POST /trading/config {"gajjala_floors": false}'
    assert house["floors_text"].startswith("House safety floors ON for this lane (your switch): share price ≥ $2.00")
    assert st["floors_off_confirm_text"] == ("Turn the house floors off for the 🚩 lane? Names under $2 and small caps "
                                             "will trade on paper.")
    assert st["window"] == "09:45–15:30 ET" and st["flatten_at"] == "15:55 ET"
    assert st["caps_text"] == "0 entries today (GG has no day cap) · 0 of 3 open" and st["max_per_day"] is None
    assert st["track_record_url"] == "/chart-maps?tab=gajjala&sub=track_record"
    assert set(st["rules"]) == {"entry_text", "stop_text", "size_text", "manage_text", "risk_text", "exempt_text",
                                "not_built", "awaiting"}
    assert st["disabled_text"] is None and st["live_text"] is None
    assert st["settings"]["risk_pct"] == 0.25 and st["settings"]["max_entries_per_day"] is None
    assert st["settings"]["be_after_bars"] == 3 and st["settings"]["reentry_wait_bars"] == 2
    off = GL.status_block({"gajjala_entry": False})
    assert off["enabled"] is False and off["disabled_text"] == \
        ('Lane switched off — no new entries; open lane positions are still flattened at 15:55 ET. '
         'POST /trading/config {"gajjala_entry": true} turns it on.')               # HIS CALL #13 (2026-10-20 fix)


def _texts():
    st = GL.status_block({"gajjala_entry": True, "gajjala_floors": True})
    gg = GL.status_block({"gajjala_entry": False, "gajjala_floors": False})
    rules = st["rules"]
    return ([rules[k] for k in ("entry_text", "stop_text", "size_text", "manage_text", "risk_text", "exempt_text")]
            + [st["floors_text"], st["floors_off_confirm_text"], st["unmeasured_text"],
               st["streak_text"], st["track_record_text"], st["empty_today_text"], gg["disabled_text"],
               GL.LIVE_TEXT, st["window"], st["flatten_at"], st["caps_text"]])


def _allowed_numbers():
    vals = [GL.GAJJALA_RISK_PCT, GL.GAJJALA_MAX_NOTIONAL_PCT, GL.GAJJALA_MAX_OPEN, GL.GAJJALA_FILL_WAIT_SEC,
            GL.GAJJALA_MAX_ROUND_R_PCT, GL.GAJJALA_MISSED_R, GL.GG_BE_AFTER_BARS, GL.GG_TRAIL_EMA,
            GL.GG_REENTRY_WAIT_BARS, GL.GG_DRAWDOWN_PCT, GL.GG_DRAWDOWN_TRADES, GL.GG_DRAWDOWN_RISK_SUM_PCT,
            SF.MIN_SHARE_PRICE, SF.MIN_CAP_USD / 1e6, 0]
    out = set()
    for v in vals:
        out |= {f"{v:g}", f"{v:.2f}", str(v)}
    return out


def test_every_number_in_the_text_is_a_constant_value(monkeypatch):
    times = {GL._hhmm(GL.WINDOW_OPEN_ET), GL._hhmm(GL.cutoff_et()), GL._hhmm(GL.flatten_et())}
    assert times == {"09:45", "15:30", "15:55"}
    allowed = _allowed_numbers()
    his_call_date = "2026-10-21"                                            # D14: the served floors_text names his call
    for text in _texts():
        rest = text.replace(his_call_date, " ")
        assert not re.search(r"\d{4}-\d{2}-\d{2}", rest), text             # NO other dates (T10)
        for t in times:
            rest = rest.replace(t, " ")
        rest = rest.replace("5-minute", " ")                                # the frame's name (bars.RULES)
        for n in re.findall(r"\d+(?:\.\d+)?", rest):
            assert n in allowed, (n, text)
    # the text MOVES with the constant (never typed)
    monkeypatch.setattr(GL, "GAJJALA_FLATTEN_BEFORE_CLOSE_MIN", 6)
    assert "flat at 15:54 ET" in GL.rules_block()["manage_text"] and "15:55" not in GL.rules_block()["manage_text"]
    monkeypatch.setattr(GL, "GG_BE_AFTER_BARS", 4)
    assert "the first closed bar, 4 or more bars after the entry bar, that closes above the entry" in \
        GL.rules_block()["manage_text"]                                  # wording 2026-10-21 (critic)
    monkeypatch.setattr(GL, "GAJJALA_RISK_PCT", 0.5)
    assert GL.rules_block()["size_text"].startswith("half of 0.5% of equity at risk first")


def test_no_bword_no_book_names_in_served_text(lane):
    s = lane(alerts=[alert()], lasts={"SAIQ": 4.48})
    s.run()
    payload = json.dumps(GL.tab_payload(), ensure_ascii=False)
    for text in _texts() + [payload]:
        low = text.lower()
        assert "bounce" not in low, text
        for book in ("TLSW", "TTLAC", "Minervini", "p.29", "p.30", "p.31"):
            assert book not in text, (book, text)
    path = os.path.join(os.path.dirname(__file__), "..", "trading", "gajjala_entry.py")
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    assert not re.search(r"bounc", src, flags=re.I), "the b-word is in the lane source"
    assert "UNMEASURED" in src and "Paper only" in src and "Not advice." in src
    assert "in the autopilot can you stop rest of the strategies and only use the Gajjalas strategies please." in src


SECTION2_ROW_KEYS = {"id", "symbol", "setup", "setup_label", "alert_et", "trigger", "stop", "r", "r_pct", "state",
                     "skip_kind", "why", "entry", "target", "qty", "risk_usd", "notional", "fill_px", "fill_et",
                     "exit_px", "exit_et", "exit_kind", "pnl_usd", "r_mult", "last", "fate_text", "pnl_text",
                     "floors", "floor_warnings", "broker_text", "url", "closable"}


def test_tab_payload_every_pushed_alert_has_a_fate(lane):
    alerts = [alert("SAIQ", hm=(10, 52)), alert("DRMA", "intraday_vcp", 0.8744, 0.861, hm=(10, 50))]
    s = lane(alerts=alerts, lasts={"SAIQ": 4.48, "DRMA": 0.879}, cap=None, cfg={"gajjala_floors": True})
    s.run()
    s.alerts.append(alert("NEWX", hm=(10, 56)))                       # rang after the last tick: not seen yet
    s.alerts.append(alert("LATE", hm=(15, 40)))                       # rang after the cut-off: never traded
    s.now = _at(DAY, 15, 45)
    p = GL.tab_payload()
    assert set(p) == {"date", "armed", "mode", "as_of", "status", "today", "recent", "journal"}
    assert p["date"] == DAY and p["armed"] is True and p["mode"] == "paper"
    assert set(p["journal"]) == {"n", "closed", "wins", "losses", "flat", "unfilled", "win_rate_pct", "pnl_usd",
                                 "avg_r", "text"}
    rows = {r["symbol"]: r for r in p["today"]}
    assert set(rows) == {"SAIQ", "DRMA", "LATE", "NEWX"}
    for r in p["today"]:
        assert set(r) == SECTION2_ROW_KEYS, set(r) ^ SECTION2_ROW_KEYS
        assert isinstance(r["fate_text"], str) and r["fate_text"]
    assert [r["symbol"] for r in p["today"]] == ["DRMA", "SAIQ", "NEWX", "LATE"]   # ascending alert time
    assert rows["SAIQ"]["state"] == "ordered" and rows["SAIQ"]["closable"] is True
    assert rows["SAIQ"]["fate_text"] == "market order 735 sent 10:55 ET (last 4.48) · stop 4.31"
    assert rows["SAIQ"]["setup_label"] == "🚩 Bull Flag" and rows["SAIQ"]["url"] == \
        "/chart-maps?tab=gajjala&sub=bull_flag&focus=SAIQ"
    assert rows["DRMA"]["state"] == "skipped" and rows["DRMA"]["closable"] is False
    assert rows["DRMA"]["fate_text"].startswith("skipped — house safety floors: share price $0.88")
    assert rows["DRMA"]["setup_label"] == "🌀 Intraday VCP" and rows["DRMA"]["last"] == 0.879
    assert rows["LATE"]["state"] == "not_seen" and rows["LATE"]["fate_text"] == "not traded — rang after the 15:30 ET cut-off"
    assert rows["NEWX"]["fate_text"] == "not seen by the lane yet"
    assert p["status"]["skipped_floor_today"] == 1 and p["status"]["entries_today"] == 1
    assert p["journal"]["n"] == 1 and p["journal"]["text"] == \
        "0 closed · 0 stop · 0 trail · 0 flat · P&L +$0.00 · avg — · 0 not filled"
    json.dumps(p, allow_nan=False)


def test_tab_payload_open_and_closed_rows_and_journal(lane):
    closed = seed(_id=f"GG:{DAY}|JBDI|kiss_fly", symbol="JBDI", setup="kiss_fly", alert_et="11:20",
                  trigger=2.48, stop=2.40, r=0.08, state="closed", entry=2.51, target=2.59, stop_px=2.40,
                  qty=3984, fill_px=2.49, fill_qty=3984, fill_et="11:21", exit_px=2.59, exit_et="11:31",
                  exit_kind="target", pnl_usd=398.4, r_mult=1.25, order_id="o-2")
    s = lane(docs=[_open(), closed], positions=[_position("SAIQ", 2217, 4.49, 4.55)], now=_at(DAY, 11, 40))
    p = GL.tab_payload()
    rows = {r["symbol"]: r for r in p["today"]}
    assert rows["SAIQ"]["last"] == 4.55 and rows["SAIQ"]["pnl_usd"] == 133.02
    assert rows["SAIQ"]["pnl_text"] == "+$133.02 open (last 4.55)" and rows["SAIQ"]["closable"]
    assert rows["JBDI"]["fate_text"] == "target 2.59 at 11:31 ET · +$398.40 · +1.25R"
    assert rows["JBDI"]["pnl_text"] == "+$398.40 · +1.25R" and rows["JBDI"]["last"] is None
    j = p["journal"]
    assert (j["n"], j["closed"], j["wins"], j["losses"], j["win_rate_pct"], j["pnl_usd"], j["avg_r"]) == \
        (2, 1, 1, 0, 100.0, 398.4, 1.25)
    assert j["text"] == "1 closed · 1 target · 0 stop · 0 trail · 0 flat · P&L +$398.40 · avg +1.25R · 0 not filled"
    assert p["status"]["caps_text"] == "2 entries today (GG has no day cap) · 1 of 3 open"


# ── API ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_api_config_three_flags_strict(lane):
    fastapi = pytest.importorskip("fastapi")
    from trading import api as TA
    import auth
    admin = auth.HOUSE_OWNER_EMAIL
    s = lane()
    # v2 2026-10-21 (D1): gajjala_floors defaults OFF; gajjala_entry stays ON
    assert EE.get_config()["gajjala_entry"] is True and EE.get_config()["gajjala_floors"] is False
    resp = asyncio.run(TA.trading_config({"gajjala_entry": False}, email=admin))
    assert json.loads(resp.body) == {"gajjala_entry": False} and EE.get_config()["gajjala_entry"] is False
    resp = asyncio.run(TA.trading_config({"gajjala_entry": None, "gajjala_floors": None,
                                          "hot_pullback_entry": None}, email=admin))
    # 2026-10-21 (critic): null = the code default — gajjala_floors stores None (get_config → OFF), the lanes ON
    assert json.loads(resp.body) == {"gajjala_entry": True, "gajjala_floors": None, "hot_pullback_entry": True}
    assert EE.get_config()["gajjala_floors"] is False
    resp = asyncio.run(TA.trading_config({"hot_pullback_entry": False}, email=admin))
    assert EE.get_config()["hot_pullback_entry"] is False
    for key in ("gajjala_entry", "gajjala_floors", "hot_pullback_entry"):
        with pytest.raises(fastapi.HTTPException) as exc:
            asyncio.run(TA.trading_config({key: "yes"}, email=admin))
        assert exc.value.status_code == 400 and exc.value.detail == "%s must be a boolean or null" % key
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_config({"gajjala_floors": 1}, email=admin))
    assert exc.value.status_code == 400
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_config({"gajjala_entry": True}, email="nobody@example.com"))
    assert exc.value.status_code == 403
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_config({}, email=admin))
    assert "gajjala_entry" in exc.value.detail and "hot_pullback_entry" in exc.value.detail


def test_api_gajjala_routes_admin_gated(lane):
    fastapi = pytest.importorskip("fastapi")
    from trading import api as TA
    import auth
    admin = auth.HOUSE_OWNER_EMAIL
    s = lane(alerts=[alert()], lasts={"SAIQ": 4.40})
    s.run()
    for call in (lambda e: TA.trading_gajjala(email=e), lambda e: TA.trading_gajjala_close("SAIQ", email=e)):
        for who in ("nobody@example.com", None):
            with pytest.raises(fastapi.HTTPException) as exc:
                asyncio.run(call(who))
            assert exc.value.status_code == 403
    body = json.loads(asyncio.run(TA.trading_gajjala(email=admin)).body)
    assert body["today"][0]["state"] == "waiting" and body["status"]["strategy"] == "gajjala"
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_gajjala_close("XYZ", email=admin))
    assert exc.value.status_code == 400 and exc.value.detail == "no open 🚩 Gajjala position on XYZ"
    lane(armed=False)
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_gajjala_close("SAIQ", email=admin))
    assert exc.value.status_code == 400 and exc.value.detail == "engine not armed"


def test_api_gajjala_close_failure_is_not_200(lane, monkeypatch):
    """A close the broker refused must not answer 200 (critic 2026-10-20): the tab only reads the HTTP status, so a
    silent ok:false left the row open with no error line. 502 + the served broker errors as the detail; NEGATIVE: a
    close that closed / queued stays 200 with the result body."""
    fastapi = pytest.importorskip("fastapi")
    from trading import api as TA
    from trading import gajjala_entry as GE
    import auth
    admin = auth.HOUSE_OWNER_EMAIL
    lane(alerts=[alert()], lasts={"SAIQ": 4.40}).run()
    monkeypatch.setattr(GE, "close_now", lambda sym, reason="owner close": {"ok": False, "state": "open", "symbol": sym,
                                                                            "errors": ["HTTP 500 internal error"]})
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_gajjala_close("SAIQ", email=admin))
    assert exc.value.status_code == 502 and exc.value.detail == "HTTP 500 internal error"
    monkeypatch.setattr(GE, "close_now", lambda sym, reason="owner close": {"ok": False, "state": "open", "symbol": sym,
                                                                            "errors": []})
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_gajjala_close("SAIQ", email=admin))
    assert exc.value.status_code == 502 and exc.value.detail == "the broker did not close SAIQ"
    monkeypatch.setattr(GE, "close_now", lambda sym, reason="owner close": {"ok": True, "state": "closing", "symbol": sym,
                                                                            "errors": []})
    resp = asyncio.run(TA.trading_gajjala_close("SAIQ", email=admin))
    assert resp.status_code == 200 and json.loads(resp.body)["state"] == "closing"


# ── critic fixes 2026-10-20 (BUILD_SPEC17 review): flatten failures, OFF manages, tick gates, ledger, gaps, fills ───
def _boom_close(s, monkeypatch, calls):
    def boom(sym):
        calls.append(sym)
        raise EE.BrokerError("HTTP 500 internal error")
    monkeypatch.setattr(s.brk, "close_position", boom, raising=False)


SAIQ_ID = f"GG:{DAY}|SAIQ|bull_flag"


def test_failed_flatten_stays_open_and_retries_every_tick(lane, monkeypatch):
    """Critic P1: a non-403 BrokerError on the 15:55 close is NOT 'closing' — retried every tick, then carried."""
    s = lane(docs=[_open()], positions=[_position("SAIQ", 2217, 4.49, 4.55)], now=_at(DAY, 15, 55))
    calls = []
    _boom_close(s, monkeypatch, calls)
    errs = []
    for hm in ((15, 55), (15, 56), (15, 57)):
        out = s.run(at=_at(DAY, *hm))
        errs.append(out["errors"])
        assert s.coll.get(SAIQ_ID)["state"] == "open"
    assert calls == ["SAIQ"] * 3                                          # every tick tries again
    assert all(e and "flatten SAIQ: HTTP 500 internal error" in e[0] for e in errs)
    nxt = datetime(2026, 10, 21, 10, 0, tzinfo=ET)
    s.now = nxt
    out = s.run(at=nxt)
    assert calls == ["SAIQ"] * 4 and s.coll.get(SAIQ_ID)["state"] == "open" and out["errors"]
    monkeypatch.setattr(s.brk, "close_position", lambda sym: calls.append(sym) or {}, raising=False)
    out = s.run(at=nxt + timedelta(minutes=1))
    d = s.coll.get(SAIQ_ID)
    assert d["state"] == "closing" and d["exit_kind"] == "carried" and out["closing"] == 1 and not out["errors"]


def test_queued_flatten_is_closing_and_the_queue_owns_it(lane, monkeypatch):
    s = lane(docs=[_open()], positions=[_position("SAIQ", 2217, 4.49, 4.55)], now=_at(DAY, 15, 55))
    seen = []
    monkeypatch.setattr(EE, "flatten", lambda sym, reason=None: seen.append(sym) or
                        {"dry_run": False, "closed": False, "queued": True, "errors": ["held for orders"]})
    s.run()
    assert s.coll.get(SAIQ_ID)["state"] == "closing" and seen == ["SAIQ"]
    s.db.trading_config.rows[0]["flatten_queue"] = [{"symbol": "SAIQ", "state": "pending"}]
    s.run(at=_at(DAY, 15, 56))
    assert seen == ["SAIQ"]                                                # NEG: queued → not re-flattened by the lane


def test_closing_doc_still_held_is_reflattened_at_flatten_time(lane, monkeypatch):
    seen = []
    monkeypatch.setattr(EE, "flatten", lambda sym, reason=None: seen.append((sym, reason)) or
                        {"dry_run": False, "closed": True, "queued": False, "errors": []})
    s = lane(docs=[_open(state="closing", exit_kind="owner", why="owner close")],
             positions=[_position("SAIQ", 2217, 4.49, 4.55)], now=_at(DAY, 14, 0))
    s.run()
    assert seen == []                                                      # NEG: before 15:55 the owner close stands
    s.run(at=_at(DAY, 15, 55))
    assert [x[0] for x in seen] == ["SAIQ"]
    d = s.coll.get(SAIQ_ID)
    assert d["state"] == "closing" and d["exit_kind"] == "owner"
    s = lane(docs=[_open(state="closing", exit_kind="flatten")], positions=[], now=_at(DAY, 15, 56),
             closed=[_sell("market", 4.55, (15, 55))])
    seen.clear()
    s.run()
    assert seen == [] and s.coll.get(SAIQ_ID)["state"] == "closed"         # NEG: gone from the positions → closed


def test_close_now_failed_flatten_is_not_ok(lane, monkeypatch):
    """Critic P5: the owner's Close on a broker 500 says ok False and the doc stays open."""
    s = lane(docs=[_open()], positions=[_position("SAIQ", 2217, 4.49, 4.55)])
    _boom_close(s, monkeypatch, [])
    res = GL.close_now("SAIQ")
    assert res["ok"] is False and res["state"] == "open" and res["errors"] == ["HTTP 500 internal error"]
    assert s.coll.get(SAIQ_ID)["state"] == "open"
    monkeypatch.setattr(s.brk, "close_position", lambda sym: {}, raising=False)
    assert GL.close_now("SAIQ")["ok"] is True and s.coll.get(SAIQ_ID)["state"] == "closing"   # NEG: success


def test_lane_off_still_flattens_but_never_claims(lane):
    """Critic P2 / HIS CALL #13: OFF stops NEW entries only — an open lane position is still closed at 15:55."""
    s = lane(docs=[_open()], positions=[_position("SAIQ", 2217, 4.49, 4.55)], cfg={"gajjala_entry": False},
             now=_at(DAY, 15, 55))
    out = s.run()
    assert out["manage_only"] is True and out["ran"] is True and out["gate"]["ok"] is False
    assert [c[1]["symbol"] for c in s.brk.calls if c[0] == "close_position"] == ["SAIQ"]
    assert s.coll.get(SAIQ_ID)["state"] == "closing"
    # NEG: a waiting alert with the lane off at 10:00 — no claim, no bracket
    s = lane(alerts=[alert(hm=(9, 58))], lasts={"SAIQ": 4.48}, cfg={"gajjala_entry": False}, now=_at(DAY, 10, 0))
    out = s.run()
    assert out["claimed"] == 0 and s.coll.rows == [] and _brackets(s.brk) == []
    # NEG: a pre-claimed waiting doc is not bought either, and is still expired at the cut-off
    s = lane(docs=[seed()], lasts={"SAIQ": 4.48}, cfg={"gajjala_entry": False}, now=_at(DAY, 10, 0))
    s.run()
    assert s.coll.get(SAIQ_ID)["state"] == "waiting" and _brackets(s.brk) == []
    s.run(at=_at(DAY, 15, 30))
    assert s.coll.get(SAIQ_ID)["skip_kind"] == "never_triggered"
    # NEG: off AND disarmed → nothing runs
    s = lane(docs=[_open()], positions=[_position("SAIQ", 2217, 4.49, 4.55)], cfg={"gajjala_entry": False},
             armed=False, now=_at(DAY, 15, 55))
    out = s.run()
    assert out["ran"] is False and s.brk.calls == []
    st = GL.status_block({"gajjala_entry": False})
    assert "no new entries; open lane positions are still flattened at 15:55 ET" in st["disabled_text"]


@pytest.mark.parametrize("hm,rang,brackets", [((15, 29), (15, 28), 1), ((15, 30), (15, 28), 0),
                                               ((15, 45), (15, 40), 0)])
def test_run_window_gate_no_order_at_or_after_the_cutoff(lane, hm, rang, brackets):
    """run()'s in_entry_window gate: the tape trades the trigger at 15:30 / 15:45 → no bracket; 15:29 → one."""
    s = lane(alerts=[alert(hm=rang)], lasts={"SAIQ": 4.48}, now=_at(DAY, *hm))
    out = s.run()
    assert len(_brackets(s.brk)) == brackets
    assert out["claimed"] == brackets and len(s.coll.rows) == brackets


def test_overlapping_ticks_same_waiting_doc_one_bracket(lane, monkeypatch):
    """D10: two ticks that both read the doc as 'waiting' — the conditional state change lets one order out."""
    s = lane(docs=[seed()], lasts={"SAIQ": 4.48})
    snap = [dict(d) for d in s.coll.rows]                                  # what both ticks read before either wrote
    monkeypatch.setattr(GL, "_find", lambda coll, q: [dict(d) for d in snap if LaneColl._match(d, q)])
    cfg = EE.get_config()
    outs = []
    for _ in range(2):
        out = {"claimed": 0, "waiting": 0, "ordered": 0, "skipped": 0, "dry_run": 0, "errors": []}
        GL._try_waiting(s.coll, cfg, s.brk, NOW, DAY, GL._Reads(s.brk, "2026-10-16T00:00:00+00:00"), out)
        outs.append(out)
    assert len(_brackets(s.brk)) == 1 and [o["ordered"] for o in outs] == [1, 0]
    assert s.coll.get(SAIQ_ID)["state"] == "ordered"


def test_disarmed_skip_rows_are_dry_run(lane):
    s = lane(docs=[seed()], lasts={"SAIQ": 4.30}, armed=False)             # the stop printed first, disarmed
    s.run()
    (row,) = _rows(s.db, "gajjala_skip")
    assert row["detail"]["skip_kind"] == "never_triggered" and row["dry_run"] is True
    s = lane(docs=[seed()], lasts={"SAIQ": 4.30})                          # NEG: armed → a real row
    s.run()
    assert [r["dry_run"] for r in _rows(s.db, "gajjala_skip")] == [False]
    assert s.coll.get(SAIQ_ID)["state"] == "unfilled"


def test_target_under_a_cent_over_the_entry_is_broker_gap():
    """v2: no target leg — only the stop's distance from the last can be too tight for Alpaca."""
    p = GL.entry_plan({"trigger": 0.50, "stop": 0.492, "plan": "ok"}, 0.50, 100_000, 100_000)
    assert not p["ok"] and p["skip_kind"] == "broker_gap"                   # 0.50 − 0.492 < $0.01
    ok = GL.entry_plan({"trigger": 0.50, "stop": 0.492, "plan": "ok"}, 0.502, 100_000, 100_000)
    assert ok["ok"] and ok["skip_kind"] is None and ok["target"] is None    # NEG: R under a cent, no target to refuse


def _cancel_lands_fill(s, monkeypatch, filled_qty):
    def cancel(order_id):
        s.brk.calls.append(("cancel_order", {"order_id": order_id}))
        o = s.brk._orders.pop(0)
        s.brk._closed.append(dict(o, status="canceled", filled_qty=str(filled_qty), filled_avg_price="4.50",
                                  filled_at=NOW.astimezone(UTC).isoformat()))
    monkeypatch.setattr(s.brk, "cancel_order", cancel, raising=False)


def test_fill_landing_between_the_read_and_the_cancel_is_open(lane, monkeypatch):
    s = lane(docs=[_ordered(NOW - timedelta(seconds=200))], orders=[_working()])
    _cancel_lands_fill(s, monkeypatch, 300)
    out = s.run()
    d = s.coll.get(SAIQ_ID)
    assert out["cancelled"] == 1 and d["state"] == "open" and d["fill_qty"] == 300 and d["fill_px"] == 4.5
    assert _rows(s.db, "gajjala_cancel")[0]["detail"]["filled_qty"] == 300
    # the order unreadable after the cancel, but the shares are in the account → open with the position
    s = lane(docs=[_ordered(NOW - timedelta(seconds=200))], orders=[_working()])

    def cancel_and_hold(order_id):
        s.brk._orders.clear()
        s.brk._positions.append(_position("SAIQ", 120, 4.50, 4.52))
    monkeypatch.setattr(s.brk, "cancel_order", cancel_and_hold, raising=False)
    s.run()
    d = s.coll.get(SAIQ_ID)
    assert d["state"] == "open" and d["fill_qty"] == 120 and d["fill_px"] == 4.5
    # NEG: nothing filled after the cancel → unfilled, the slot released
    s = lane(docs=[_ordered(NOW - timedelta(seconds=200))], orders=[_working()])
    _cancel_lands_fill(s, monkeypatch, 0)
    s.run()
    d = s.coll.get(SAIQ_ID)
    assert d["state"] == "unfilled" and GL.status_block(EE.get_config())["open_n"] == 0


def _ordering(age_s, **kw):
    return seed(state="ordering", qty=2217, entry=4.51, target=4.66, stop_px=4.31,
                ordering_at=(NOW - timedelta(seconds=age_s)).astimezone(UTC).isoformat(),
                client_order_id="test-SAIQ-gg-bull_flag", **kw)


def test_stuck_ordering_reconciled_by_client_order_id(lane):
    s = lane(docs=[_ordering(200)], orders=[_working(id="o-9", client_order_id="test-SAIQ-gg-bull_flag")])
    s.run()
    d = s.coll.get(SAIQ_ID)
    assert d["state"] == "ordered" and d["order_id"] == "o-9"
    s = lane(docs=[_ordering(200)], positions=[_position("SAIQ", 2217, 4.49, 4.5)])
    s.run()
    d = s.coll.get(SAIQ_ID)
    assert d["state"] == "open" and d["fill_qty"] == 2217 and d["fill_px"] == 4.49
    s = lane(docs=[_ordering(200)], orders=[_working(id="o-7", client_order_id="test-OTHER-gg-bull_flag")])
    s.run()
    d = s.coll.get(SAIQ_ID)
    assert d["state"] == "unfilled" and d["why"] == "the order never reached the broker — slot released"
    assert GL.status_block(EE.get_config())["open_n"] == 0 and _brackets(s.brk) == []
    # NEG: younger than the fill wait — an overlapping tick may still be inside entries.enter → untouched
    s = lane(docs=[_ordering(30)])
    s.run()
    assert s.coll.get(SAIQ_ID)["state"] == "ordering"


def test_ordering_records_the_client_order_id_before_the_broker_call(lane, monkeypatch):
    seen = []
    s = lane(alerts=[alert()], lasts={"SAIQ": 4.48})
    monkeypatch.setattr(GL.TE, "enter", lambda sym, **kw: seen.append(dict(s.coll.get(SAIQ_ID))) or
                        {"order_id": "x-1", "client_order_id": "test-SAIQ-gg-bull_flag"})
    s.run()
    (mid,) = seen
    assert mid["state"] == "ordering" and mid["client_order_id"] == "test-SAIQ-gg-bull_flag" and mid["ordering_at"]
