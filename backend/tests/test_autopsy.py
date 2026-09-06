"""Failed-trade autopsy behavior — fake Mongo, synthetic minute + daily
records injected through the module's seams, no network, no broker
(docs/supply_demand/trade_autopsy.md).

Locks trading/autopsy.py:

  Scope       only CLOSED journal trades with gain_pct < 0; winners,
              breakeven and open trades are never autopsied.
  Strategy    zone_edge (zone_edge_entry_state match, client_order_id
              preferred), minervini (trigger.path -> pivot band), manual.
  Classes     one test per OWNER class + the priority order (a shakeout
              that is also market_down is a shakeout; band_failed beats
              market_down; market_down beats chased; chased beats
              no_follow_through; demand vs breakout chase limits).
  Status      preliminary -> final once two CLOSED sessions after the exit
              day exist (a live overlay bar never counts); incomplete on a
              missing input with the retry count, capped at MAX_RETRIES;
              final is never recomputed or downgraded.
  Bounds      MAX_PER_RUN trades per run (one minute fetch each), SPY/RSP
              loaded once per run, recheck throttle, idempotent upsert,
              ONE 'autopsy' ledger row per trade.
  Report      summary shape, medians None at n=0, rows newest first, no
              _id, JSON-safe; API admin gate (403) + days clamp; tick step
              (i) fenced.

Host-runnable (py3.9; pandas only for the two frame-conversion tests):
    cd backend && .venv/bin/python -m pytest tests/test_autopsy.py -q
"""
import asyncio
import json
import math
import os
import sys
from datetime import date, datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.autopsy as AP
import trading.exit_engine as EE
import trading.journal as JN

ET = ZoneInfo("America/New_York")
D0 = date(2026, 8, 25)                         # Tuesday (EDT: ET = UTC-4)
FLOOR = 98.0                                   # demand band lo
BAND_HI = 99.5


# ── Fakes (pattern: tests/test_zone_edge_entry.py) ──────────────────────────

class FakeCursor(list):
    def sort(self, key=None, direction=1, *a, **k):
        if isinstance(key, str):
            return FakeCursor(sorted(self, key=lambda d: d.get(key) or 0,
                                     reverse=(direction == -1)))
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
                if "$regex" in v and not str(dv or "").startswith(v["$regex"].lstrip("^")):
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

    def delete_many(self, q):
        self.rows = [d for d in self.rows if not self._match(d, q)]


class FakeDB:
    def __init__(self):
        self.trading_config = FakeColl([{
            "_id": "config", "armed": True, "auto_entry": False,
            "zone_edge_entry": False, "consecutive_losses": 0,
            "processed_order_ids": [], "equity_cap": 100_000.0,
            "progressive_exposure": False}])
        self.trade_ledger = FakeColl()
        self.trade_journal = FakeColl()
        self.zone_edge_entry_state = FakeColl()
        self.trade_autopsies = FakeColl()
        self.auto_entry_state = FakeColl()


class FakeBroker:
    """Read-only broker for the tick-fence test (exit_engine.tick needs
    configured/clock/positions/open_orders/closed_orders_since)."""

    def configured(self):
        return True

    def clock(self):
        return {"is_open": True}

    def mode(self):
        return "paper"

    def positions(self):
        return []

    def open_orders(self, symbol=None):
        return []

    def closed_orders_since(self, iso_ts):
        return []

    OPEN_STATUSES = {"new", "accepted", "held", "partially_filled"}


# ── Synthetic data builders ────────────────────────────────────────────────

def et(day, hh, mm, ss=0):
    return datetime.combine(day, dtime(hh, mm, ss), tzinfo=ET)


def utc_iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def bdays(start, n, step=1):
    """n weekdays walking `step` (+1 forward / -1 back) from start, exclusive
    of start, in chronological order."""
    out, cur = [], start
    while len(out) < n:
        cur = cur + timedelta(days=step)
        if cur.weekday() < 5:
            out.append(cur)
    return sorted(out)


def trade(sym="AAA", entry=None, exit_=None, entry_px=100.0, exit_px=97.5,
          stop_pct=2.49, leg="stop", trigger=None, qty=10, status="closed"):
    entry = entry or et(D0, 10, 30)
    exit_ = exit_ or et(D0, 14, 0)
    stop_price = round(entry_px * (1 - stop_pct / 100.0), 4)
    gain = round((exit_px / entry_px - 1) * 100, 2)
    doc = {"trade_id": "%s-%d" % (sym, int(entry.timestamp())), "symbol": sym,
           "status": status,
           "entry": {"ts": utc_iso(entry), "epoch": entry.timestamp(),
                     "price": entry_px, "qty": qty, "stop_price": stop_price,
                     "stop_pct": stop_pct, "target_price": None,
                     "target_pct": None, "reward_risk": None,
                     "regime": "normal", "mode": "paper", "trigger": trigger},
           "protected_to_breakeven": False, "exit": None, "realized": None}
    if status == "closed":
        doc["exit"] = {"ts": utc_iso(exit_), "epoch": exit_.timestamp(),
                       "price": exit_px, "leg": leg}
        doc["realized"] = {"gain_pct": gain, "gain_dollars": round(qty * (exit_px - entry_px), 2),
                           "r_multiple": round(gain / stop_pct, 2),
                           "holding_days": 0.15, "exit_reason": "stopped out"}
    return doc


def state(sym="AAA", day=D0, lo=FLOOR, hi=BAND_HI, touches=3, side="demand",
          kind="demand", tier="near", stop_pct=2.49, first_seen="10:12",
          order_id="o-1", client_order_id="coid-AAA", entered=True):
    return {"key": "%s:%g-%g:%s" % (sym, lo, hi, day.isoformat()), "symbol": sym,
            "date": day.isoformat(),
            "band": {"kind": "demand" if side == "demand" else "supply",
                     "lo": lo, "hi": hi, "touches": touches, "strength": 1.5},
            "side": side, "kind": kind, "tier": tier, "attempted": True,
            "entered": entered, "stop_pct": stop_pct,
            "result": "entered" if entered else "blocked", "reason": None,
            "first_seen": first_seen, "last": 100.0, "order_id": order_id,
            "client_order_id": client_order_id,
            "order_ts": utc_iso(et(day, 10, 30))}


def mbars(day, px=100.0, spikes=(), session="rth"):
    """390 flat RTH 1-min bars for `day` at `px`; spikes = [(hh, mm, high,
    low)] overwrite that minute's high/low."""
    out = []
    for k in range(390):
        t = et(day, 9, 30) + timedelta(minutes=k)
        out.append({"ts": t.astimezone(timezone.utc), "open": px, "high": px,
                    "low": px, "close": px, "volume": 1000.0, "session": session})
    for hh, mm, hi, lo in spikes:
        idx = (hh * 60 + mm) - (9 * 60 + 30)
        out[idx]["high"], out[idx]["low"] = hi, lo
    return out


def dbar(day, o, h, l, c, live=False):
    return {"date": day, "open": o, "high": h, "low": l, "close": c,
            "volume": 1e6, "live": live}


def history(before=D0, n=20, px=100.0):
    """n closed bars before `before`: high px+1, low px-1, close px
    (ATR14 = 2.0 -> 2% of a 100 entry)."""
    return [dbar(d, px, px + 1.0, px - 1.0, px) for d in bdays(before, n, -1)]


def daily(exit_close, after=(), d0_open=100.0, d0_high=100.8, d0_low=97.4,
          live_last=False):
    """History + the D0 bar closing at exit_close + `after` closes on the
    following sessions (the last one flagged live when live_last)."""
    bars = history() + [dbar(D0, d0_open, d0_high, d0_low, exit_close)]
    days = bdays(D0, len(after), +1)
    for k, (d, c) in enumerate(zip(days, after)):
        bars.append(dbar(d, c, c + 0.5, c - 0.5, c,
                         live=(live_last and k == len(after) - 1)))
    return bars


def index_bars(pct_by_day=None, base=500.0):
    """Daily bars for an index: flat 0% except pct_by_day {date: pct}."""
    pct_by_day = pct_by_day or {}
    days = bdays(D0, 20, -1) + [D0] + bdays(D0, 5, +1)
    out, px = [], base
    for d in days:
        prev = px
        px = round(prev * (1 + pct_by_day.get(d, 0.0) / 100.0), 4)
        out.append(dbar(d, prev, max(prev, px), min(prev, px), px))
    return out


BASE_MINUTE = mbars(D0, 100.0, spikes=[(11, 0, 100.8, 100.0), (14, 0, 100.0, 97.4)])


@pytest.fixture
def env(monkeypatch):
    """Wire autopsy's seams; returns (db, calls) where calls records every
    minute-bar fetch, daily load and gauge read."""

    def build(trades=(), states=(), minute=None, dailies=None, spy=None,
              rsp=None, gauge="constructive", autopsies=(), ledger_rows=()):
        db = FakeDB()
        for t in trades:
            db.trade_journal.insert_one(t)
        for s in states:
            db.zone_edge_entry_state.insert_one(s)
        for a in autopsies:
            db.trade_autopsies.insert_one(a)
        for r in ledger_rows:
            db.trade_ledger.insert_one(r)
        calls = {"minute": [], "daily": [], "gauge": 0}
        minute_map = minute if isinstance(minute, dict) else None
        # The caller's dict is used AS IS so a test can swap a frame between
        # runs (preliminary -> final) by mutating it.
        dailies = dailies if dailies is not None else {}
        dailies.setdefault("SPY", spy if spy is not None else index_bars())
        dailies.setdefault("RSP", rsp if rsp is not None else index_bars())

        def fake_minute(symbol, d0, d1):
            calls["minute"].append((symbol, d0, d1))
            if minute_map is not None:
                return minute_map.get(symbol)
            if callable(minute):
                return minute(symbol, d0, d1)
            return minute

        def fake_daily(symbol):
            calls["daily"].append(symbol)
            return dailies.get(symbol)

        def fake_gauge():
            calls["gauge"] += 1
            return gauge

        monkeypatch.setattr(EE, "_db", lambda: db)
        monkeypatch.setattr(JN, "_db", lambda: db)
        monkeypatch.setattr(AP, "_db", lambda: db)
        monkeypatch.setattr(AP, "_minute_bars", fake_minute)
        monkeypatch.setattr(AP, "_daily_bars", fake_daily)
        monkeypatch.setattr(AP, "_gauge_now", fake_gauge)
        return db, calls

    return build


def _docs(db):
    return db.trade_autopsies.rows


def _doc(db, sym="AAA"):
    rows = [d for d in _docs(db) if d.get("symbol") == sym]
    assert len(rows) == 1, rows
    return rows[0]


def _autopsy_rows(db):
    return [r for r in db.trade_ledger.rows if r.get("kind") == "autopsy"]


# ── Scope: only closed losers ───────────────────────────────────────────────

def test_winners_breakeven_and_open_trades_are_never_autopsied(env):
    db, calls = env(trades=[
        trade("WIN", exit_px=103.0),                 # +3%
        trade("FLAT", exit_px=100.0),                # 0.0% -> not a loss
        trade("OPEN", status="open"),
    ], states=[state("WIN"), state("FLAT"), state("OPEN")],
        minute=BASE_MINUTE, dailies={"WIN": daily(99.0), "FLAT": daily(99.0),
                                     "OPEN": daily(99.0)})
    out = AP.run(now=et(D0, 16, 30))
    assert out["ok"] is True and out["losers"] == 0 and out["checked"] == 0
    assert _docs(db) == [] and calls["minute"] == [] and calls["daily"] == []
    assert _autopsy_rows(db) == []


def test_no_work_means_no_price_or_gauge_reads(env):
    db, calls = env(trades=[], minute=BASE_MINUTE)
    AP.run()
    assert calls == {"minute": [], "daily": [], "gauge": 0}


# ── Strategy detection ──────────────────────────────────────────────────────

def test_strategy_zone_edge_minervini_manual(env):
    trig = {"path": "intraday", "pivot": 99.0, "relvol": 2.1, "score": 90,
            "cleared_at_frac": 0.2}
    db, _ = env(trades=[trade("AAA"), trade("BBB", trigger=trig),
                        trade("CCC")],
                states=[state("AAA")],
                minute={"AAA": BASE_MINUTE, "BBB": BASE_MINUTE, "CCC": BASE_MINUTE},
                dailies={"AAA": daily(99.0, after=(97.0, 97.0)),
                         "BBB": daily(99.5, after=(97.0, 97.0)),
                         "CCC": daily(99.0, after=(97.0, 97.0))})
    out = AP.run(now=et(D0, 16, 30))
    assert out["checked"] == 3 and out["errors"] == []
    a, b, c = _doc(db, "AAA"), _doc(db, "BBB"), _doc(db, "CCC")
    assert (a["strategy"], a["side"], a["kind"]) == ("zone_edge", "demand", "demand")
    assert a["entry"]["band"] == {"kind": "demand", "lo": 98.0, "hi": 99.5, "touches": 3}
    assert a["entry"]["tier"] == "near" and a["entry"]["first_seen"] == "10:12"
    assert a["entry"]["entry_lag_sec"] == 18 * 60.0
    assert a["structure"]["floor"] == 98.0
    # minervini: pivot is the floor, band lo = hi = pivot, breakout chase limit
    assert (b["strategy"], b["side"], b["kind"]) == ("minervini", "pivot", "breakout")
    assert b["entry"]["band"] == {"kind": "pivot", "lo": 99.0, "hi": 99.0, "touches": None}
    assert b["structure"]["floor"] == 99.0 and b["structure"]["band_close_held"] is True
    assert b["entry"]["stop_requested_pct"] is None and b["entry"]["clamped"] is None
    # manual: no band, no floor -> band reads are None, never False
    assert (c["strategy"], c["side"], c["kind"]) == ("manual", None, None)
    assert c["entry"]["band"] is None and c["entry"]["chase_pct"] is None
    assert c["structure"]["band_close_held"] is None
    assert c["structure"]["reclaimed_within_2"] is None
    assert c["classification"] == "no_follow_through"


def test_zone_state_matched_by_client_order_id_via_entry_ledger_row(env):
    """Two entered state rows for the same symbol/day (different bands): the
    'entry' ledger row at the journal epoch carries the client_order_id, and
    that decides which band the autopsy reads."""
    t = trade("AAA")
    db, _ = env(trades=[t],
                states=[state("AAA", lo=90.0, hi=91.0, order_id="o-9",
                              client_order_id="coid-other"),
                        state("AAA", lo=98.0, hi=99.5, order_id="o-1",
                              client_order_id="coid-AAA")],
                minute=BASE_MINUTE, dailies={"AAA": daily(99.0, after=(97.0, 97.0))},
                ledger_rows=[{"ts": t["entry"]["ts"], "epoch": t["entry"]["epoch"],
                              "kind": "entry", "symbol": "AAA", "dry_run": False,
                              "detail": {"order_id": "o-1",
                                         "client_order_id": "coid-AAA",
                                         "price": 100.0}}])
    AP.run(now=et(D0, 16, 30))
    d = _doc(db)
    assert d["entry"]["band"]["lo"] == 98.0
    assert d["ids"] == {"order_id": "o-1", "client_order_id": "coid-AAA"}


def test_zone_state_with_foreign_ids_only_is_not_matched(env):
    """Both sides carry ids and none match -> not that band (manual), never a
    foreign order's band."""
    t = trade("AAA")
    db, _ = env(trades=[t],
                states=[state("AAA", order_id="o-9", client_order_id="coid-other")],
                minute=BASE_MINUTE, dailies={"AAA": daily(99.0, after=(97.0, 97.0))},
                ledger_rows=[{"ts": t["entry"]["ts"], "epoch": t["entry"]["epoch"],
                              "kind": "entry", "symbol": "AAA", "dry_run": False,
                              "detail": {"order_id": "o-1",
                                         "client_order_id": "coid-AAA"}}])
    AP.run(now=et(D0, 16, 30))
    assert _doc(db)["strategy"] == "manual"


def test_state_read_failure_is_soft(env, monkeypatch):
    db, _ = env(trades=[trade("AAA")], states=[state("AAA")],
                minute=BASE_MINUTE, dailies={"AAA": daily(99.0, after=(97.0, 97.0))})

    def boom(*a, **k):
        raise RuntimeError("state down")

    monkeypatch.setattr(db.zone_edge_entry_state, "find", boom)
    out = AP.run(now=et(D0, 16, 30))
    assert out["errors"] == [] and _doc(db)["strategy"] == "manual"


# ── Classes (one per class) + priority order ────────────────────────────────

def test_class_shakeout_and_priority_over_market_down_and_band_failed(env):
    """Exit-day close UNDER the floor (band_failed would fire) and SPY -1.5%
    on the exit day (market_down would fire) — but the close came back above
    the floor within 2 sessions after a stop exit: shakeout wins."""
    db, _ = env(trades=[trade("AAA")], states=[state("AAA")], minute=BASE_MINUTE,
                dailies={"AAA": daily(97.8, after=(99.0, 100.0))},
                spy=index_bars({D0: -1.5}))
    out = AP.run(now=et(D0, 16, 30))
    d = _doc(db)
    assert d["classification"] == "shakeout" and d["status"] == "final"
    assert d["structure"]["band_close_held"] is False
    assert d["structure"]["reclaimed_within_2"] is True
    assert d["market"]["spy_pct_exit_day"] == -1.5
    assert d["excursion"]["mfe_pct"] == pytest.approx(0.8, abs=1e-6)
    assert d["excursion"]["mfe_r"] == pytest.approx(0.8 / 2.49, abs=1e-3)
    assert d["excursion"]["mae_pct"] == pytest.approx(-2.6, abs=1e-6)
    assert d["excursion"]["reached_1r"] is False
    assert d["structure"]["atr_pct_14"] == pytest.approx(2.0, abs=1e-6)
    # feedback carries the numbers, not advice
    fb = d["feedback"]
    assert "MAE -2.6%" in fb and "ATR 2%" in fb and "floor 98" in fb
    assert "owner decision" in fb
    assert out["classified"] == [{"trade_id": d["trade_id"], "symbol": "AAA",
                                  "classification": "shakeout"}]


def test_shakeout_needs_a_stop_leg(env):
    """Same reclaim, but a manual flatten is not a shakeout."""
    db, _ = env(trades=[trade("AAA", leg="flatten")], states=[state("AAA")],
                minute=BASE_MINUTE, dailies={"AAA": daily(97.8, after=(99.0, 100.0))})
    AP.run(now=et(D0, 16, 30))
    assert _doc(db)["classification"] == "band_failed"


def test_class_band_failed_and_priority_over_market_down(env):
    db, _ = env(trades=[trade("AAA")], states=[state("AAA")], minute=BASE_MINUTE,
                dailies={"AAA": daily(97.8, after=(97.0, 96.5))},
                spy=index_bars({D0: -1.5}))
    AP.run(now=et(D0, 16, 30))
    d = _doc(db)
    assert d["classification"] == "band_failed"
    assert d["structure"]["reclaimed_within_2"] is False
    assert "floor 98 did not hold" in d["feedback"]
    assert "97.8" in d["feedback"] and "touches 3" in d["feedback"]


def test_class_market_down_via_rsp_and_priority_over_chased(env):
    """Band held on the exit day, RSP -1.2% (SPY flat), MFE < 0.5R, AND the
    entry chased 1.51% above the ceiling: market_down wins over chased."""
    db, _ = env(trades=[trade("AAA", entry_px=101.0, exit_px=98.5,
                              stop_pct=3.46)],
                states=[state("AAA")],
                minute=mbars(D0, 101.0, spikes=[(11, 0, 101.5, 101.0), (14, 0, 101.0, 98.4)]),
                dailies={"AAA": daily(98.5, after=(97.0, 97.0))},
                rsp=index_bars({D0: -1.2}))
    AP.run(now=et(D0, 16, 30))
    d = _doc(db)
    assert d["classification"] == "market_down"
    assert d["entry"]["chase_pct"] == pytest.approx(1.5075, abs=1e-3)
    assert d["market"]["rsp_pct_exit_day"] == -1.2 and d["market"]["spy_pct_exit_day"] == 0.0
    assert "RSP -1.2%" in d["feedback"] and "SPY 0%" in d["feedback"]


def test_market_down_needs_low_mfe(env):
    """SPY -1.5% but the trade ran 1.2R first: not the tape's fault."""
    db, _ = env(trades=[trade("AAA")], states=[state("AAA")],
                minute=mbars(D0, 100.0, spikes=[(11, 0, 103.0, 100.0), (14, 0, 100.0, 97.4)]),
                dailies={"AAA": daily(98.5, after=(97.0, 97.0))},
                spy=index_bars({D0: -1.5}))
    AP.run(now=et(D0, 16, 30))
    d = _doc(db)
    assert d["classification"] == "unclassified"
    assert d["excursion"]["reached_1r"] is True


def test_class_chased_demand_and_priority_over_no_follow_through(env):
    db, _ = env(trades=[trade("AAA", entry_px=101.0, exit_px=98.5, stop_pct=3.46)],
                states=[state("AAA")],
                minute=mbars(D0, 101.0, spikes=[(11, 0, 101.5, 101.0), (14, 0, 101.0, 98.4)]),
                dailies={"AAA": daily(98.5, after=(97.0, 97.0))})
    AP.run(now=et(D0, 16, 30))
    d = _doc(db)
    assert d["classification"] == "chased"
    assert d["excursion"]["mfe_r"] < AP.FOLLOW_THROUGH_R     # would be no_follow_through
    assert "1.51% above the band ceiling 99.5" in d["feedback"]
    assert "limit 1%" in d["feedback"]


def test_breakout_chase_limit_is_wider(env):
    """A breakout 1.46% past the cleared band is NOT chased (limit 2%); the
    same distance on a demand arrival is."""
    st = state("AAA", lo=100.0, hi=103.0, side="supply", kind="breakout",
               tier="broke", stop_pct=4.8)
    db, _ = env(trades=[trade("AAA", entry_px=104.5, exit_px=101.0, stop_pct=4.8)],
                states=[st],
                minute=mbars(D0, 104.5, spikes=[(11, 0, 105.0, 104.5), (14, 0, 104.5, 100.9)]),
                dailies={"AAA": daily(103.5, after=(102.0, 102.0))})
    AP.run(now=et(D0, 16, 30))
    d = _doc(db)
    assert d["kind"] == "breakout" and d["side"] == "supply"
    assert d["structure"]["floor"] == 103.0           # breakouts: the cleared ceiling
    assert d["structure"]["band_close_held"] is True
    assert d["entry"]["chase_pct"] == pytest.approx(1.456, abs=1e-3)
    assert d["classification"] == "no_follow_through"
    assert d["feedback"].startswith("MFE ") and "before the stop" in d["feedback"]


def test_class_no_follow_through(env):
    db, _ = env(trades=[trade("AAA")], states=[state("AAA")], minute=BASE_MINUTE,
                dailies={"AAA": daily(98.5, after=(97.0, 97.0))})
    AP.run(now=et(D0, 16, 30))
    d = _doc(db)
    assert d["classification"] == "no_follow_through"
    assert d["exit"]["time_to_exit_min"] == 210.0
    assert "210 min" in d["feedback"] and "0.32R" in d["feedback"]


def test_class_unclassified_when_no_rule_matches(env):
    db, _ = env(trades=[trade("AAA")], states=[state("AAA")],
                minute=mbars(D0, 100.0, spikes=[(11, 0, 103.0, 100.0), (14, 0, 100.0, 97.4)]),
                dailies={"AAA": daily(98.5, after=(97.0, 97.0))})
    AP.run(now=et(D0, 16, 30))
    d = _doc(db)
    assert d["classification"] == "unclassified"
    assert d["excursion"]["mfe_r"] == pytest.approx(3.0 / 2.49, abs=1e-3)
    assert "no rule matched" in d["feedback"] and "band held True" in d["feedback"]


def test_class_stop_clamped_and_its_negative(env):
    """Requested 9.5% under entry, the risk contract placed 7%: exit 92.8
    sits ABOVE the requested level 90.5 -> the clamp fired. Exit 90.0 (below
    the requested level) is the band failing, not the clamp."""
    st = state("AAA", lo=90.5, hi=92.0, stop_pct=9.5)
    db, _ = env(trades=[trade("AAA", exit_px=92.8, stop_pct=7.0)], states=[st],
                minute=mbars(D0, 100.0, spikes=[(14, 0, 100.0, 92.7)]),
                dailies={"AAA": daily(89.0, after=(88.0, 88.0))})
    AP.run(now=et(D0, 16, 30))
    d = _doc(db)
    assert d["entry"]["stop_requested_pct"] == 9.5
    assert d["entry"]["stop_placed_pct"] == 7.0 and d["entry"]["clamped"] is True
    assert d["classification"] == "stop_clamped"
    assert "9.5%" in d["feedback"] and "7%" in d["feedback"] and "90.5" in d["feedback"]

    db2, _ = env(trades=[trade("AAA", exit_px=90.0, stop_pct=7.0)], states=[st],
                 minute=mbars(D0, 100.0, spikes=[(14, 0, 100.0, 89.9)]),
                 dailies={"AAA": daily(89.0, after=(88.0, 88.0))})
    AP.run(now=et(D0, 16, 30))
    d2 = _doc(db2)
    assert d2["entry"]["clamped"] is True
    assert d2["classification"] == "band_failed"


def test_clamp_tolerance_is_a_tenth_of_a_point(env):
    """Requested 2.55, placed 2.49: within CLAMP_TOLERANCE_PT -> not clamped."""
    db, _ = env(trades=[trade("AAA")], states=[state("AAA", stop_pct=2.55)],
                minute=BASE_MINUTE, dailies={"AAA": daily(98.5, after=(97.0, 97.0))})
    AP.run(now=et(D0, 16, 30))
    assert _doc(db)["entry"]["clamped"] is False


def test_classify_is_first_match_and_never_fires_on_none():
    assert AP.classify({}) == "unclassified"
    base = {"exit_price": 92.8, "stop_requested_level": 90.5, "clamped": True,
            "leg": "stop", "reclaimed_within_2": True, "band_close_held": False,
            "spy_pct_exit_day": -2.0, "mfe_r": 0.1, "chase_pct": 5.0,
            "kind": "demand"}
    assert AP.classify(base) == "stop_clamped"
    base["clamped"] = False
    assert AP.classify(base) == "shakeout"
    base["reclaimed_within_2"] = None
    assert AP.classify(base) == "band_failed"
    base["band_close_held"] = None
    assert AP.classify(base) == "market_down"
    base["spy_pct_exit_day"] = None
    assert AP.classify(base) == "chased"
    base["kind"] = None                                  # manual: no chase limit
    assert AP.classify(base) == "no_follow_through"
    base["mfe_r"] = None
    assert AP.classify(base) == "unclassified"
    assert AP.classify({"leg": "stop", "reclaimed_within_2": False}) == "unclassified"
    assert AP.classify({"spy_pct_exit_day": -1.0, "mfe_r": 0.5}) == "unclassified"
    assert AP.classify({"spy_pct_exit_day": -1.0, "mfe_r": 0.49}) == "market_down"
    assert AP.classify({"chase_pct": 2.0, "kind": "breakout"}) == "unclassified"
    assert AP.classify({"chase_pct": 2.01, "kind": "breakout"}) == "chased"


# ── Tags ────────────────────────────────────────────────────────────────────

def test_tags_positive_and_negative(env):
    early = trade("EARLY", entry=et(D0, 9, 45), exit_=et(D0, 14, 0), stop_pct=8.0)
    late = trade("LATE", entry=et(D0, 15, 50), exit_=et(D0, 15, 58))
    db, _ = env(trades=[early, late],
                states=[state("EARLY", touches=2, stop_pct=8.0), state("LATE")],
                minute={"EARLY": BASE_MINUTE, "LATE": BASE_MINUTE},
                dailies={"EARLY": daily(98.5, after=(97.0, 97.0), d0_open=98.5),
                         "LATE": daily(98.5, after=(97.0, 97.0), d0_open=99.5)})
    AP.run(now=et(D0, 16, 30))
    e, l = _doc(db, "EARLY"), _doc(db, "LATE")
    assert set(e["tags"]) == {"first_30_min_entry", "gap_down_open", "thin_band", "wide_stop"}
    assert e["entry"]["session_frac"] == pytest.approx(15 / 390.0, abs=1e-4)
    assert e["structure"]["gap_open_pct"] == -1.5
    assert l["tags"] == ["late_day_entry"]
    assert l["entry"]["session_frac"] == pytest.approx(380 / 390.0, abs=1e-4)
    assert l["structure"]["gap_open_pct"] == -0.5
    assert "partial_data" not in e["tags"] + l["tags"]


# ── Status: preliminary -> final, incomplete + retries, never downgraded ──

def test_preliminary_then_final_after_two_closed_sessions(env, monkeypatch):
    dailies = {"AAA": daily(97.8)}
    db, calls = env(trades=[trade("AAA")], states=[state("AAA")],
                    minute=BASE_MINUTE, dailies=dailies)
    AP.run(now=et(D0, 16, 30))
    d = _doc(db)
    assert d["status"] == "preliminary" and d["classification"] == "band_failed"
    assert d["structure"]["reclaimed_within_2"] is None
    assert d["structure"]["sessions_after_exit"] == 0 and d["missing"] == []
    assert len(_autopsy_rows(db)) == 1 and d["ledgered"] is True

    # one closed session back above the floor -> reclaimed True already, but
    # still preliminary until the second session exists
    dailies["AAA"] = daily(97.8, after=(99.0,))
    AP.run(now=et(bdays(D0, 1)[0], 16, 30), recheck_sec=0)
    d = _doc(db)
    assert d["status"] == "preliminary" and d["classification"] == "shakeout"
    assert d["structure"]["reclaimed_within_2"] is True

    # a LIVE overlay bar never counts as the second session
    dailies["AAA"] = daily(97.8, after=(99.0, 100.0), live_last=True)
    AP.run(now=et(bdays(D0, 2)[1], 12, 0), recheck_sec=0)
    d = _doc(db)
    assert d["status"] == "preliminary" and d["structure"]["sessions_after_exit"] == 1

    dailies["AAA"] = daily(97.8, after=(99.0, 100.0))
    AP.run(now=et(bdays(D0, 2)[1], 16, 30), recheck_sec=0)
    d = _doc(db)
    assert d["status"] == "final" and d["structure"]["sessions_after_exit"] == 2
    assert len(_autopsy_rows(db)) == 1                 # ledgered ONCE
    assert len(_docs(db)) == 1
    computed = d["computed_at"]

    # final is never recomputed or downgraded, even when inputs vanish
    n_minute = len(calls["minute"])
    dailies["AAA"] = None
    out = AP.run(now=et(bdays(D0, 3)[2], 16, 30), recheck_sec=0)
    assert out["checked"] == 0 and out["pending"] == 0
    d = _doc(db)
    assert d["status"] == "final" and d["computed_at"] == computed
    assert len(calls["minute"]) == n_minute


def test_incomplete_on_missing_minute_bars_with_retry_cap(env):
    db, calls = env(trades=[trade("AAA")], states=[state("AAA")], minute=None,
                    dailies={"AAA": daily(97.8, after=(97.0, 97.0))})
    AP.run(now=et(D0, 16, 30))
    d = _doc(db)
    assert d["status"] == "incomplete" and d["retries"] == 1
    assert "minute_bars" in d["missing"] and "partial_data" in d["tags"]
    assert d["excursion"] == {"mfe_pct": None, "mfe_r": None, "mae_pct": None,
                              "reached_1r": None, "n_bars": 0}
    # the rules that CAN read still classify (band_failed needs no minute bars)
    assert d["classification"] == "band_failed"
    assert _autopsy_rows(db) == []                    # not ledgered while incomplete
    assert d["ledgered"] is False

    for k in range(2, AP.MAX_RETRIES + 1):
        AP.run(now=et(D0, 16, 30), recheck_sec=0)
        assert _doc(db)["retries"] == k
    assert len(calls["minute"]) == AP.MAX_RETRIES
    out = AP.run(now=et(D0, 16, 30), recheck_sec=0)   # capped: no more fetches
    assert out["pending"] == 0 and len(calls["minute"]) == AP.MAX_RETRIES
    assert _doc(db)["retries"] == AP.MAX_RETRIES and _doc(db)["status"] == "incomplete"


def test_incomplete_recovers_when_the_input_arrives(env, monkeypatch):
    holder = {"bars": None}
    db, calls = env(trades=[trade("AAA")], states=[state("AAA")],
                    minute=lambda s, a, b: holder["bars"],
                    dailies={"AAA": daily(97.8, after=(97.0, 97.0))})
    AP.run(now=et(D0, 16, 30))
    assert _doc(db)["status"] == "incomplete"
    holder["bars"] = BASE_MINUTE
    AP.run(now=et(D0, 16, 30), recheck_sec=0)
    d = _doc(db)
    assert d["status"] == "final" and d["retries"] == 1
    assert d["missing"] == [] and "partial_data" not in d["tags"]
    assert len(_autopsy_rows(db)) == 1 and d["ledgered"] is True


def test_incomplete_on_missing_daily_and_index_frames(env):
    db, _ = env(trades=[trade("AAA")], states=[state("AAA")], minute=BASE_MINUTE,
                dailies={"AAA": None, "SPY": None, "RSP": index_bars()})
    AP.run(now=et(D0, 16, 30))
    d = _doc(db)
    assert d["status"] == "incomplete"
    assert set(d["missing"]) >= {"daily_bars", "exit_day_bar", "entry_day_bar", "spy_daily"}
    assert "rsp_daily" not in d["missing"]
    assert d["structure"]["band_close_held"] is None
    assert d["market"]["spy_pct_exit_day"] is None
    assert d["market"]["rsp_pct_exit_day"] == 0.0
    assert d["excursion"]["mfe_r"] == pytest.approx(0.8 / 2.49, abs=1e-3)


def test_recheck_throttle_and_idempotent_upsert(env):
    db, calls = env(trades=[trade("AAA")], states=[state("AAA")], minute=BASE_MINUTE,
                    dailies={"AAA": daily(97.8)})
    AP.run(now=et(D0, 16, 30))
    out = AP.run(now=et(D0, 16, 31))                  # 60 s later: throttled
    assert out["pending"] == 0 and len(calls["minute"]) == 1
    out = AP.run(now=et(D0, 17, 31))                  # > RECHECK_SEC: re-checked
    assert out["checked"] == 1 and len(calls["minute"]) == 2
    docs = _docs(db)
    assert len(docs) == 1 and docs[0]["_id"] == docs[0]["trade_id"] == trade("AAA")["trade_id"]
    assert len(_autopsy_rows(db)) == 1


def test_max_per_run_bounds_fetches_and_processes_newest_first(env):
    trades = [trade("S%d" % k, entry=et(D0, 10, k), exit_=et(D0, 14, k)) for k in range(5)]
    db, calls = env(trades=trades, minute=BASE_MINUTE,
                    dailies={t["symbol"]: daily(98.5, after=(97.0, 97.0)) for t in trades})
    assert AP.MAX_PER_RUN == 3
    out = AP.run(now=et(D0, 16, 30))
    assert out["pending"] == 5 and out["checked"] == 3 and out["stored"] == 3
    assert len(calls["minute"]) == 3
    assert [c[0] for c in calls["minute"]] == ["S4", "S3", "S2"]   # newest entry first
    assert calls["daily"].count("SPY") == 1 and calls["daily"].count("RSP") == 1
    assert calls["gauge"] == 1
    out = AP.run(now=et(D0, 16, 31))
    assert out["pending"] == 2 and out["checked"] == 2
    assert len(_docs(db)) == 5
    out = AP.run(now=et(D0, 16, 32), max_per_run=0)
    assert out["checked"] == 0


def test_new_trades_go_before_rechecks(env):
    dailies = {"OLD": daily(97.8), "NEW": daily(97.8)}
    db, calls = env(trades=[trade("OLD", entry=et(D0, 10, 0), exit_=et(D0, 14, 0))],
                    minute=BASE_MINUTE, dailies=dailies)
    AP.run(now=et(D0, 16, 30))
    db.trade_journal.insert_one(trade("NEW", entry=et(D0, 9, 45), exit_=et(D0, 13, 0)))
    out = AP.run(now=et(D0, 17, 31), max_per_run=1)
    assert out["checked"] == 1 and calls["minute"][-1][0] == "NEW"


# ── Soft failure everywhere ────────────────────────────────────────────────

def test_journal_failure_never_raises(env, monkeypatch):
    env(trades=[trade("AAA")])

    def boom(*a, **k):
        raise RuntimeError("journal down")

    monkeypatch.setattr(JN, "load", boom)
    out = AP.run()
    assert out["ok"] is False and out["errors"] == ["journal: journal down"]


def test_per_trade_failure_is_isolated(env, monkeypatch):
    trades = [trade("AAA"), trade("BBB", entry=et(D0, 10, 0), exit_=et(D0, 14, 0))]
    db, _ = env(trades=trades, minute=BASE_MINUTE,
                dailies={"AAA": daily(98.5, after=(97.0, 97.0)),
                         "BBB": daily(98.5, after=(97.0, 97.0))})
    real = AP._daily_bars

    def flaky(symbol):
        if symbol == "AAA":
            raise RuntimeError("prices down")
        return real(symbol)

    monkeypatch.setattr(AP, "_daily_bars", flaky)
    out = AP.run(now=et(D0, 16, 30))
    assert out["ok"] is False and len(out["errors"]) == 1 and "AAA" in out["errors"][0]
    assert [d["symbol"] for d in _docs(db)] == ["BBB"]


def test_missing_autopsies_collection_is_reported_not_raised(env, monkeypatch):
    db, _ = env(trades=[trade("AAA")], minute=BASE_MINUTE,
                dailies={"AAA": daily(98.5, after=(97.0, 97.0))})
    delattr(db, "trade_autopsies")
    out = AP.run(now=et(D0, 16, 30))
    assert out["checked"] == 1 and out["stored"] == 0
    assert any("trade_autopsies unavailable" in e for e in out["errors"])
    assert _autopsy_rows(db) == []                    # nothing stored -> nothing ledgered


def test_store_failure_never_ledgers_and_the_next_run_ledgers_once(env, monkeypatch):
    """Reviewer regression (2026-09-03): the feed row is written only AFTER
    the doc is stored. A failed upsert must not leave an 'autopsy' row whose
    `ledgered` flag never persisted (that re-ledgered the trade on every
    re-check)."""
    db, _ = env(trades=[trade("AAA")], states=[state("AAA")], minute=BASE_MINUTE,
                dailies={"AAA": daily(98.5, after=(97.0, 97.0))})
    real = db.trade_autopsies.update_one

    def boom(*a, **k):
        raise RuntimeError("mongo write down")

    monkeypatch.setattr(db.trade_autopsies, "update_one", boom)
    out = AP.run(now=et(D0, 16, 30))
    assert out["checked"] == 1 and out["stored"] == 0
    assert any("store failed" in e for e in out["errors"])
    assert _autopsy_rows(db) == [] and out["classified"] == [] and _docs(db) == []
    monkeypatch.setattr(db.trade_autopsies, "update_one", real)
    out = AP.run(now=et(D0, 16, 31))                  # no doc yet -> due, no throttle
    assert out["stored"] == 1 and out["errors"] == []
    assert len(_autopsy_rows(db)) == 1 and _doc(db)["ledgered"] is True
    assert out["classified"][0]["classification"] == "no_follow_through"
    AP.run(now=et(D0, 17, 32), recheck_sec=0)
    assert len(_autopsy_rows(db)) == 1


def test_recheck_that_loses_an_input_keeps_the_preliminary_doc(env):
    """Reviewer regression (2026-09-03): a provider hiccup on an hourly
    re-check must never replace computed numbers with None (and, after
    MAX_RETRIES, freeze the trade as 'incomplete' forever). The previous
    preliminary doc is kept, the miss is stamped, retries counted, and the
    trade still finalizes once the input is back."""
    holder = {"bars": BASE_MINUTE}
    dailies = {"AAA": daily(97.8)}
    db, calls = env(trades=[trade("AAA")], states=[state("AAA")],
                    minute=lambda s, a, b: holder["bars"], dailies=dailies)
    AP.run(now=et(D0, 16, 30))
    d = _doc(db)
    assert d["status"] == "preliminary" and d["classification"] == "band_failed"
    assert d["excursion"]["mfe_pct"] == pytest.approx(0.8, abs=1e-6)

    holder["bars"] = None                              # minute fetch fails on the re-check
    out = AP.run(now=et(D0, 17, 31), recheck_sec=0)
    d = _doc(db)
    assert out["checked"] == 1 and out["stored"] == 1
    assert out["preliminary"] == 1 and out["incomplete"] == 0
    assert d["status"] == "preliminary" and d["retries"] == 1
    assert d["excursion"]["mfe_pct"] == pytest.approx(0.8, abs=1e-6)
    assert d["excursion"]["mae_pct"] == pytest.approx(-2.6, abs=1e-6)
    assert d["classification"] == "band_failed" and "partial_data" not in d["tags"]
    assert d["missing"] == [] and d["last_miss"]["missing"] == ["minute_bars"]
    assert d["computed_at"] == AP._utc_iso(et(D0, 17, 31).astimezone(timezone.utc))
    assert len(_autopsy_rows(db)) == 1
    json.dumps(d, allow_nan=False)

    # an outage longer than MAX_RETRIES re-checks never freezes it
    for k in range(AP.MAX_RETRIES + 1):
        AP.run(now=et(D0, 17, 32 + k), recheck_sec=0)
    d = _doc(db)
    assert d["status"] == "preliminary" and d["retries"] == AP.MAX_RETRIES + 2

    # the input is back + the two sessions exist -> final, numbers intact
    holder["bars"] = BASE_MINUTE
    dailies["AAA"] = daily(97.8, after=(97.0, 96.5))
    out = AP.run(now=et(bdays(D0, 2)[1], 16, 30), recheck_sec=0)
    d = _doc(db)
    assert out["checked"] == 1 and d["status"] == "final"
    assert d["classification"] == "band_failed" and d["structure"]["reclaimed_within_2"] is False
    assert d["excursion"]["mfe_pct"] == pytest.approx(0.8, abs=1e-6)
    assert len(_autopsy_rows(db)) == 1 and len(_docs(db)) == 1


def test_malformed_journal_docs_never_break_the_run(env):
    """Reviewer regression (2026-09-03): a journal doc whose `realized` /
    `exit` is not a dict is skipped (gain unreadable) or lands as an
    'incomplete' doc — never an exception, never a run-wide abort."""
    bad_realized = dict(trade("BAD1"), realized="junk",
                        exit={"price": 97.5, "epoch": et(D0, 14, 0).timestamp(), "leg": "stop"})
    bad_exit = dict(trade("BAD2", entry=et(D0, 10, 0)), exit=["junk"])
    db, _ = env(trades=[bad_realized, bad_exit, trade("AAA")], states=[state("AAA")],
                minute=BASE_MINUTE,
                dailies={"AAA": daily(98.5, after=(97.0, 97.0)),
                         "BAD2": daily(98.5, after=(97.0, 97.0))})
    out = AP.run(now=et(D0, 16, 30))
    assert out["ok"] is True and out["errors"] == []
    assert {d["symbol"] for d in _docs(db)} == {"AAA", "BAD2"}     # BAD1: gain unreadable
    b2 = _doc(db, "BAD2")
    assert b2["status"] == "incomplete" and b2["retries"] == 1
    assert {"exit_ts", "exit_price", "exit_day_bar"} <= set(b2["missing"])
    assert b2["exit"]["price"] is None and b2["classification"] == "unclassified"
    assert _autopsy_rows(db) == [] or all(r["symbol"] == "AAA" for r in _autopsy_rows(db))
    assert _doc(db, "AAA")["classification"] == "no_follow_through"
    assert AP.compute({"trade_id": "X-1", "symbol": "x", "entry": "junk",
                       "exit": 3, "realized": None}, None, None, None, None, None
                      )["status"] == "incomplete"


# ── Numbers helpers ────────────────────────────────────────────────────────

def test_excursion_uses_rth_bars_from_entry_minute_through_exit_bar():
    bars = mbars(D0, 100.0, spikes=[(10, 29, 120.0, 80.0),   # before entry
                                    (10, 30, 100.4, 99.8),   # entry minute
                                    (12, 0, 101.0, 99.0),
                                    (14, 0, 100.2, 97.4),    # exit minute
                                    (14, 1, 130.0, 50.0)])   # after exit
    bars += mbars(D0, 100.0, spikes=[(12, 30, 150.0, 10.0)], session="premarket")
    e = AP.excursion(bars, et(D0, 10, 30, 20), et(D0, 14, 0, 5), 100.0)
    assert e["n_bars"] == 211
    assert e["mfe_pct"] == pytest.approx(1.0) and e["mae_pct"] == pytest.approx(-2.6)
    assert AP.excursion([], et(D0, 10, 30), et(D0, 14, 0), 100.0) == {
        "mfe_pct": None, "mae_pct": None, "n_bars": 0}
    assert AP.excursion(bars, None, et(D0, 14, 0), 100.0)["n_bars"] == 0
    assert AP.excursion(bars, et(D0, 10, 30), et(D0, 14, 0), 0)["n_bars"] == 0
    nan_bars = [dict(b, high=float("nan")) for b in bars[:5]]
    assert AP.excursion(nan_bars, et(D0, 9, 30), et(D0, 9, 35), 100.0)["n_bars"] == 0


def test_daily_helpers():
    bars = daily(97.8, after=(99.0, 100.0), d0_open=98.5)
    assert AP.daily_change_pct(bars, D0) == pytest.approx(-2.2)
    assert AP.gap_open_pct(bars, D0) == pytest.approx(-1.5)
    assert [b["close"] for b in AP.sessions_after(bars, D0)] == [99.0, 100.0]
    assert AP.sessions_after(bars, bdays(D0, 5)[-1]) == []
    assert AP.daily_change_pct(bars, date(2020, 1, 1)) is None
    assert AP.gap_open_pct(None, D0) is None
    assert AP.atr_pct(bars, D0, 100.0) == pytest.approx(2.0)
    assert AP.atr_pct(bars[-5:], D0, 100.0) is None          # too few bars
    assert AP.atr_pct(bars, D0, 0) is None
    assert AP.session_frac(et(D0, 9, 30)) == 0.0
    assert AP.session_frac(et(D0, 9, 0)) == 0.0
    assert AP.session_frac(et(D0, 16, 30)) == 1.0
    assert AP.session_frac(et(D0, 12, 45)) == pytest.approx(195 / 390.0)
    assert AP.session_frac(None) is None
    assert AP.entry_lag_sec("10:12", D0, et(D0, 10, 30)) == 1080.0
    assert AP.entry_lag_sec("junk", D0, et(D0, 10, 30)) is None
    assert AP.entry_lag_sec(None, D0, et(D0, 10, 30)) is None
    assert AP.floor_of("demand", {"lo": 1.0, "hi": 2.0}) == 1.0
    assert AP.floor_of("breakout", {"lo": 1.0, "hi": 2.0}) == 2.0
    assert AP.floor_of(None, {"lo": 1.0, "hi": 2.0}) is None
    assert AP.floor_of("demand", None) is None


def test_compute_is_pure_and_json_safe_on_garbage():
    doc = AP.compute({"trade_id": "X-1", "symbol": "x",
                      "entry": {"price": float("nan"), "epoch": "junk"},
                      "exit": {"price": None}}, None, None, None, None, None)
    assert doc["status"] == "incomplete" and doc["strategy"] == "manual"
    assert doc["symbol"] == "X" and doc["classification"] == "unclassified"
    assert {"entry_ts", "exit_ts", "entry_price", "exit_price", "minute_bars",
            "daily_bars"} <= set(doc["missing"])
    json.dumps(doc, allow_nan=False)
    assert AP._json_safe({"a": float("nan"), "b": [float("inf"), 1, True, None],
                          "c": D0, "d": {"e": "s"}}) == {
        "a": None, "b": [None, 1, True, None], "c": "2026-08-25", "d": {"e": "s"}}
    assert AP._s(None) == "n/a" and AP._s(2.0) == "2" and AP._s(2.4900) == "2.49"
    assert AP._s(-2.6) == "-2.6" and AP._s(0.3212, 2) == "0.32"


def test_records_from_pandas_frames_and_price_seams(monkeypatch):
    pd = pytest.importorskip("pandas")
    import daytrading.data as DD
    import sepa.prices as SP
    ts = pd.to_datetime([et(D0, 9, 30).astimezone(timezone.utc).replace(tzinfo=None),
                         et(D0, 9, 31).astimezone(timezone.utc).replace(tzinfo=None)])
    mdf = pd.DataFrame({"open": [1.0, 2.0], "high": [1.5, float("nan")],
                        "low": [0.5, 1.5], "close": [1.2, 1.9],
                        "volume": [10, 20], "session": ["rth", "rth"]},
                       index=pd.Index(ts, name="ts_utc"))
    monkeypatch.setattr(DD, "_fetch_massive_minute", lambda s, a, b: mdf)
    rows = AP._minute_bars("AAA", D0, D0)
    assert len(rows) == 2 and rows[0]["ts"] == et(D0, 9, 30).astimezone(timezone.utc)
    assert rows[0]["ts"].tzinfo is not None
    assert rows[1]["high"] is None and rows[1]["close"] == 1.9 and rows[1]["session"] == "rth"
    monkeypatch.setattr(DD, "_fetch_massive_minute", lambda s, a, b: None)
    assert AP._minute_bars("AAA", D0, D0) is None

    ddf = pd.DataFrame({"open": [100.0, 101.0], "high": [101.0, 102.0],
                        "low": [99.0, 100.0], "close": [100.5, 101.5],
                        "volume": [1e6, 2e6]},
                       index=pd.to_datetime([D0 - timedelta(days=1), D0]))
    periods = []

    def fake_load(s, period="2y", force=False):
        periods.append(period)
        return ddf

    monkeypatch.setattr(SP, "load_prices", fake_load)
    monkeypatch.setattr(SP, "with_today_bar", lambda df, s, snap=None: (df, {"appended": True}))
    rows = AP._daily_bars("AAA")
    # Reviewer regression (2026-09-03): the seam must request the cache-wide
    # default period — a miss is written back into the shared price_cache
    # that the SEPA scanner reads without a period.
    assert periods == ["2y"] and AP.DAILY_PERIOD == "2y"
    assert [r["date"] for r in rows] == [D0 - timedelta(days=1), D0]
    assert rows[0]["live"] is False and rows[1]["live"] is True
    assert rows[1]["close"] == 101.5
    monkeypatch.setattr(SP, "load_prices", lambda s, p="2y", force=False: None)
    assert AP._daily_bars("AAA") is None
    assert AP._records(None, "x") == [] and AP._records("junk", "x") == []


# ── Report + API + tick fence ──────────────────────────────────────────────

def test_report_empty_summary_shape_and_rules(env):
    env()
    rep = AP.report(days=30)
    assert rep["rows"] == [] and rep["days"] == 30
    assert rep["summary"] == {"n": 0, "by_class": {}, "by_strategy": {},
                              "n_final": 0, "n_preliminary": 0, "n_incomplete": 0,
                              "median_mfe_r": None, "median_time_to_exit_min": None}
    assert [r["class"] for r in rep["rules"]] == list(AP.CLASSES)
    for r in rep["rules"]:
        assert set(r) == {"class", "rule", "threshold"}
    assert AP.report(days=0)["days"] == 1 and AP.report(days=999)["days"] == 365
    assert AP.report(days="junk")["days"] == 30
    json.dumps(rep, allow_nan=False)


def test_report_rows_newest_first_no_id_window_and_medians(env):
    old = trade("OLD", entry=et(D0 - timedelta(days=40), 10, 0),
                exit_=et(D0 - timedelta(days=40), 14, 0))
    trades = [old, trade("AAA"), trade("BBB", entry=et(D0, 10, 0), exit_=et(D0, 15, 0))]
    db, _ = env(trades=trades, states=[state("AAA")], minute=BASE_MINUTE,
                dailies={"OLD": daily(98.5, after=(97.0, 97.0)),
                         "AAA": daily(97.8, after=(99.0, 100.0)),
                         "BBB": daily(98.5)})
    AP.run(now=et(D0, 16, 30))
    db.trade_autopsies.rows[0]["excursion"]["mfe_r"] = float("nan")   # legacy NaN
    rep = AP.report(days=30, now=et(D0, 16, 30))
    assert [r["symbol"] for r in rep["rows"]] == ["BBB", "AAA"]
    assert all("_id" not in r for r in rep["rows"])
    s = rep["summary"]
    assert s["n"] == 2 and s["by_class"] == {"shakeout": 1, "no_follow_through": 1}
    assert s["by_strategy"] == {"zone_edge": 1, "manual": 1}
    assert s["n_final"] == 1 and s["n_preliminary"] == 1 and s["n_incomplete"] == 0
    assert s["median_mfe_r"] == pytest.approx(0.8 / 2.49, abs=1e-3)
    assert s["median_time_to_exit_min"] == 255.0
    json.dumps(rep, allow_nan=False)
    assert AP.report(days=60, now=et(D0, 16, 30))["summary"]["n"] == 3


def test_api_autopsies_admin_gated_and_clamped(env, monkeypatch):
    fastapi = pytest.importorskip("fastapi")
    from trading import api as TA
    import auth
    admin = auth.HOUSE_OWNER_EMAIL
    env()
    seen = []

    def fake_report(days=30, now=None):
        seen.append(days)
        return {"rows": [], "summary": {"n": 0}, "rules": [], "days": days}

    monkeypatch.setattr(AP, "report", fake_report)
    resp = asyncio.run(TA.trading_autopsies(days=30, email=admin))
    assert json.loads(resp.body) == {"rows": [], "summary": {"n": 0}, "rules": [], "days": 30}
    resp = asyncio.run(TA.trading_autopsies(days=500, email=admin))
    assert json.loads(resp.body)["days"] == 365
    resp = asyncio.run(TA.trading_autopsies(days=0, email=admin))
    assert json.loads(resp.body)["days"] == 1
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_autopsies(days=30, email="nobody@example.com"))
    assert exc.value.status_code == 403
    with pytest.raises(fastapi.HTTPException) as exc:
        asyncio.run(TA.trading_autopsies(days=30, email=None))
    assert exc.value.status_code == 403
    assert seen == [30, 365, 1]


def test_tick_step_i_runs_after_journal_and_is_fenced(env, monkeypatch):
    """exit_engine.tick() calls autopsy.run() AFTER (g) journal.reconcile
    inside its own try/except: a crash lands in summary.errors, the tick
    still returns ok, and stop protection above is untouched."""
    env()
    fake = FakeBroker()
    monkeypatch.setattr(EE, "broker", fake)
    monkeypatch.setattr(EE, "regime", lambda: "normal")
    monkeypatch.setattr(EE, "_distribution_read", lambda sym: None)
    import trading.auto_entry as AE
    import trading.zone_edge_entry as ZE
    monkeypatch.setattr(AE, "run", lambda broker=None, cfg=None: {"ran": False})
    monkeypatch.setattr(ZE, "run", lambda broker=None, cfg=None: {"ran": False})
    order = []
    monkeypatch.setattr(JN, "reconcile", lambda: order.append("journal") or {})

    def fake_run(now=None, max_per_run=AP.MAX_PER_RUN, recheck_sec=AP.RECHECK_SEC):
        order.append("autopsy")
        return {"ok": True, "checked": 0}

    monkeypatch.setattr(AP, "run", fake_run)
    summary = EE.tick()
    assert summary["ok"] is True and summary["errors"] == []
    assert summary["autopsy"] == {"ok": True, "checked": 0}
    assert order == ["journal", "autopsy"]

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(AP, "run", boom)
    summary = EE.tick()
    assert summary["ok"] is True
    assert "autopsy: boom" in summary["errors"]
    assert "autopsy" not in summary


def test_cli_main_logs_one_line_and_returns_zero(env, caplog):
    env()
    import logging
    with caplog.at_level(logging.INFO, logger="trading.autopsy"):
        rc = AP._main([])
    assert rc == 0
    assert sum(1 for r in caplog.records if r.name == "trading.autopsy"
               and "AUTOPSY run" in r.getMessage()) == 1


def test_losers_skip_exits_older_than_the_backlog_window(monkeypatch):
    """First deploy must not walk every historical paper loser (owner bound)."""
    import time as _time
    from trading import journal as J
    from trading import autopsy as AU
    now = _time.time()
    fresh = {"trade_id": "AAA:1", "symbol": "AAA", "status": "closed",
             "realized": {"gain_pct": -3.0}, "exit": {"epoch": now - 2 * 86400}}
    stale = {"trade_id": "BBB:1", "symbol": "BBB", "status": "closed",
             "realized": {"gain_pct": -3.0}, "exit": {"epoch": now - (AU.BACKLOG_DAYS + 1) * 86400}}
    no_epoch = {"trade_id": "CCC:1", "symbol": "CCC", "status": "closed",
                "realized": {"gain_pct": -3.0}, "exit": {}}
    winner = {"trade_id": "DDD:1", "symbol": "DDD", "status": "closed",
              "realized": {"gain_pct": 2.0}, "exit": {"epoch": now - 86400}}
    monkeypatch.setattr(J, "load", lambda status=None, limit=None: [fresh, stale, no_epoch, winner])
    ids = [d["trade_id"] for d in AU._losers()]
    assert ids == ["AAA:1", "CCC:1"], ids



# ── Explicit strategy tag (2026-09-05 lanes) ─────────────────────────────────

def test_detect_prefers_the_explicit_tag_and_falls_back_to_inference():
    assert AP.STRATEGIES == ("zone_edge", "minervini", "catalyst", "manual")
    band = {"kind": "demand", "lo": 98.0, "hi": 99.5, "touches": 3, "strength": 1.5}
    # demand_zone tag, no state doc matched -> zone_edge/demand from the reason.
    d = AP.detect({"strategy": "demand_zone",
                   "entry_reason": {"side": "demand", "tier": "near", "band": band,
                                    "stop_pct": 2.49}}, None)
    assert (d["strategy"], d["side"], d["kind"], d["tier"]) == ("zone_edge", "demand", "demand", "near")
    assert d["band"] == {"kind": "demand", "lo": 98.0, "hi": 99.5, "touches": 3}
    assert d["stop_requested_pct"] == 2.49
    # breakout tag -> zone_edge/breakout; a matching state doc still wins the band + first_seen.
    st = state("AAA", side="supply", kind="breakout", tier="broke", lo=100.0, hi=103.0)
    d = AP.detect({"strategy": "breakout", "entry_reason": {"side": "supply", "band": band}}, st)
    assert (d["strategy"], d["side"], d["kind"]) == ("zone_edge", "supply", "breakout")
    assert d["band"]["lo"] == 100.0 and d["first_seen"] == "10:12"
    # catalyst -> its own strategy label; floor = the anchoring band's lo.
    d = AP.detect({"strategy": "catalyst",
                   "entry_reason": {"side": "demand", "quadrant": "REAL",
                                    "proximity": {"band": band}, "stop_pct": 4.5}}, None)
    assert (d["strategy"], d["side"], d["kind"]) == ("catalyst", "demand", "demand")
    assert d["band"]["lo"] == 98.0 and AP.floor_of(d["kind"], d["band"]) == 98.0
    assert d["stop_requested_pct"] == 4.5
    d = AP.detect({"strategy": "catalyst",
                   "entry_reason": {"side": "broken_supply",
                                    "bounce": {"band": {"kind": "supply", "lo": 90.0, "hi": 92.0,
                                                        "touches": 2}}}}, None)
    assert d["strategy"] == "catalyst" and d["band"]["lo"] == 90.0 and d["side"] == "broken_supply"
    # minervini tag with the trigger still present.
    d = AP.detect({"strategy": "minervini", "trigger": {"path": "intraday", "pivot": 99.0}}, None)
    assert (d["strategy"], d["kind"]) == ("minervini", "breakout") and d["band"]["lo"] == 99.0
    # manual / missing tag -> the OLD inference (state -> zone_edge; trigger -> minervini).
    assert AP.detect({"strategy": "manual"}, state("AAA"))["strategy"] == "zone_edge"
    assert AP.detect({"trigger": {"path": "intraday", "pivot": 99.0}}, None)["strategy"] == "minervini"
    assert AP.detect({"strategy": "manual"}, None)["strategy"] == "manual"
    assert AP.detect({"strategy": "alpha_wolf"}, None)["strategy"] == "manual"


def test_catalyst_trade_autopsied_under_its_own_strategy(env):
    t = trade("CAT")
    t["entry"]["strategy"] = "catalyst"
    t["entry"]["entry_reason"] = {"side": "demand", "quadrant": "OVERLOOKED", "grade": "B",
                                  "proximity": {"band": {"kind": "demand", "lo": FLOOR,
                                                         "hi": BAND_HI, "touches": 3}},
                                  "stop_pct": 2.49}
    db, _ = env(trades=[t], minute={"CAT": BASE_MINUTE},
                dailies={"CAT": daily(99.0, after=(97.0, 97.0))})
    out = AP.run(now=et(D0, 16, 30))
    assert out["checked"] == 1 and out["errors"] == []
    d = _doc(db, "CAT")
    assert (d["strategy"], d["side"], d["kind"]) == ("catalyst", "demand", "demand")
    assert d["structure"]["floor"] == FLOOR and d["entry"]["stop_requested_pct"] == 2.49
    rep = AP.report(days=60, now=et(D0, 16, 30))
    assert rep["summary"]["by_strategy"] == {"catalyst": 1}
