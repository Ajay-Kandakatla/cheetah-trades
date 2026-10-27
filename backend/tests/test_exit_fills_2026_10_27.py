"""Engine-sell fills (2026-10-27, BUILD_SPEC28 WP-B) — trading/exit_fills.py + the broker reader + the exit
engine's accounting hooks, no network.

Ajay: "Anyway you can can show me which tab made money or not?"

Locks:
  * book() books ONE `exit_fill` ledger row at the broker's own fill (price, SOLD qty, filled_at) for every
    engine market sell journal.unbooked_exits() lists; idempotent; never an estimate (no fill -> nothing);
  * it never trades, never pushes, never writes `trade_closed` (the p.299 stop rule + progressive sizing read
    that kind — their inputs stay byte-identical);
  * the tick step (e2) books after a force exit and leaves the streak / processed ids alone;
  * broker_alpaca.closed_orders_for = one symbol, every page, deduped, <= 10 pages; the sim mirrors it;
  * status() serves lane_pnl (fenced) and pnl_summary nets the option positions' cost basis;
  * account_baseline_ts reads, never seeds.
"""
import json
import os
import sys
import time
import types
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.broker_alpaca as BA
import trading.broker_sim as BS
import trading.entries as EN
import trading.exit_engine as EE
import trading.exit_fills as XF
import trading.journal as JN
import trading.options_lane as OL
import trading.progressive as PG
import trading.zero_dte_lane as ZD
from tests.test_journal import FakeColl as _JournalColl
from tests.test_journal import _row, _ts
from tests.test_trading_engine import FakeBrokerModule

E0 = 1_792_000_000.0            # 2026-10-15-ish UTC
HOUR = 3600.0
DAY = 86400.0


# ── Fakes ─────────────────────────────────────────────────────────────────────

def _get(doc, key):
    cur = doc
    for part in key.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


class FakeColl(_JournalColl):
    """test_journal's FakeColl + dotted keys + delete_many (the rollback filter)."""

    @staticmethod
    def _match(doc, q):
        for k, v in (q or {}).items():
            got = _get(doc, k)
            if isinstance(v, dict):
                if "$in" in v and got not in v["$in"]:
                    return False
                if "$ne" in v and got == v["$ne"]:
                    return False
            elif got != v:
                return False
        return True

    def delete_many(self, q):
        before = len(self.rows)
        self.rows = [d for d in self.rows if not self._match(d, q)]
        return types.SimpleNamespace(deleted_count=before - len(self.rows))


class FakeDB:
    def __init__(self, cfg=None):
        self.trade_ledger = FakeColl()
        self.trade_journal = FakeColl()
        self.gajjala_lane = FakeColl()
        self.options_positions = FakeColl()
        self.zero_dte_positions = FakeColl()
        self.auto_entry_state = FakeColl()
        self.trading_account_baseline = FakeColl()
        self.trading_config = FakeColl([dict({"_id": "config", "armed": True, "consecutive_losses": 2,
                                              "processed_order_ids": ["seen-1"], "equity_cap": 100_000.0,
                                              "progressive_exposure": False, "auto_entry": False},
                                             **(cfg or {}))])


@pytest.fixture
def db(monkeypatch):
    fdb = FakeDB()
    for mod in (EE, JN, OL, ZD, EN):
        monkeypatch.setattr(mod, "_db", lambda: fdb)
    return fdb


class FakeBroker:
    """Read-only broker double: canned orders + positions; every order-side call RAISES."""

    def __init__(self, orders=(), positions=(), positions_error=None):
        self.orders = [dict(o) for o in orders]
        self._positions = [dict(p) for p in positions]
        self.positions_error = positions_error
        self.reads = []

    def closed_orders_for(self, symbol, after_iso, until_iso=None):
        self.reads.append((symbol, after_iso, until_iso))
        return [dict(o) for o in self.orders
                if o.get("symbol") == symbol and (o.get("submitted_at") or "") > (after_iso or "")
                and (until_iso is None or (o.get("submitted_at") or "") < until_iso)]

    def positions(self):
        if self.positions_error:
            raise BA.BrokerError(self.positions_error)
        return [dict(p) for p in self._positions]

    def _never(self, *a, **k):
        raise AssertionError("exit_fills must never trade")

    submit_bracket = submit_stop = submit_market = cancel_order = replace_order = close_position = _never


def _iso(epoch, frac=""):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + frac + "Z"


def _sell(oid, sym, epoch, qty, px, side="sell"):
    return {"id": oid, "symbol": sym, "side": side, "status": "filled", "type": "market",
            "submitted_at": _iso(epoch - 1), "filled_at": _iso(epoch), "filled_qty": str(qty),
            "filled_avg_price": str(px)}


def _entry(sym, epoch, qty=10, price=100.0, stop=95.0, strategy="breakout"):
    return _row("entry", sym, epoch, detail={"order_id": "buy-%s" % sym, "qty": qty, "price": price,
                                             "stop_price": stop, "strategy": strategy,
                                             "stop_pct": round((price - stop) / price * 100, 2)})


def _force(kind, sym, epoch, qty, last, closed=True, reason="sell rule"):
    return _row(kind, sym, epoch, detail={"qty": qty, "avg_entry": last, "last": last, "reason": reason,
                                          "canceled": 1, "cancel_errors": [], "closed": closed})


def _seed_cnq(fdb, epoch=E0):
    fdb.trade_ledger.insert_one(_entry("CNQ", epoch, qty=479, price=51.58, stop=48.0))
    fdb.trade_ledger.insert_one(_force("distribution_exit", "CNQ", epoch + DAY, 479, 51.245))


def _fills(fdb):
    return [r for r in fdb.trade_ledger.rows if r.get("kind") == "exit_fill"]


# ── 1-12: book() / rollback() / the CLI ───────────────────────────────────────

def test_book_writes_one_exit_fill_at_the_fill_time(db):
    _seed_cnq(db)
    fill_epoch = E0 + DAY + 30
    order = _sell("s-1", "CNQ", fill_epoch, 479, 51.2)
    order["filled_at"] = _iso(fill_epoch, ".123456789")          # Alpaca's nanosecond stamp
    brk = FakeBroker([order])
    res = XF.book(brk, held_symbols=set())
    assert res["candidates"] == 1 and len(res["written"]) == 1 and res["would_write"] == []
    rows = _fills(db)
    assert len(rows) == 1
    row = rows[0]
    assert row["epoch"] == pytest.approx(fill_epoch + 0.123456, abs=1e-3)
    assert row["ts"] == _ts(fill_epoch)
    assert row["cite"] == XF.CITE and row["dry_run"] is False and row["symbol"] == "CNQ"
    det = row["detail"]
    assert set(det) == {"leg", "source_kind", "source", "trade_id", "strategy", "order_id", "order_ids", "fill",
                        "qty", "entry", "gain_pct", "decision_ts", "decision_last", "held_qty", "reason",
                        "filled_at", "partial", "overfill_qty", "est"}
    assert det["leg"] == "force_exit" and det["source_kind"] == "distribution_exit"
    assert det["source"] == XF.SOURCE_LIVE and det["strategy"] == "breakout"
    assert det["order_id"] == "s-1" and det["order_ids"] == ["s-1"]
    assert det["fill"] == 51.2 and det["qty"] == 479 and det["entry"] == 51.58
    assert det["gain_pct"] == round((51.2 / 51.58 - 1) * 100, 2)
    assert det["decision_last"] == 51.245 and det["held_qty"] == 479 and det["reason"] == "sell rule"
    assert det["partial"] is False and det["overfill_qty"] == 0 and det["est"] is False
    assert res["written"][0] == {"symbol": "CNQ", "lane": "breakout", "trade_id": det["trade_id"], "qty": 479,
                                 "fill": 51.2, "entry": 51.58, "realized": round(479 * (51.2 - 51.58), 2),
                                 "orders": 1}
    # The journal now closes the round trip at the fill.
    JN.reconcile()
    doc = JN.load()[0]
    assert doc["status"] == "closed" and doc["fill_wanted"] is None
    assert doc["realized"]["gain_dollars"] == round(479 * (51.2 - 51.58), 2)
    # NEG: a second run writes nothing (idempotent).
    res2 = XF.book(brk, held_symbols=set())
    assert res2["candidates"] == 0 and res2["written"] == []
    assert len(_fills(db)) == 1


def test_book_still_held_writes_nothing(db):
    _seed_cnq(db)
    brk = FakeBroker([_sell("s-1", "CNQ", E0 + DAY + 30, 479, 51.2)],
                     positions=[{"symbol": "CNQ", "qty": "479"}])
    res = XF.book(brk, held_symbols={"cnq"})
    assert res["still_held"] == ["CNQ"] and res["written"] == [] and brk.reads == []
    # The back-fill path reads the broker's positions itself.
    res = XF.book(brk)
    assert res["still_held"] == ["CNQ"] and res["written"] == []
    # NEG: positions unreadable -> an error, nothing booked, no order read.
    bad = FakeBroker([_sell("s-1", "CNQ", E0 + DAY + 30, 479, 51.2)], positions_error="HTTP 500")
    res = XF.book(bad)
    assert res["errors"] and res["errors"][0].startswith("positions unavailable") and bad.reads == []
    assert _fills(db) == []


def test_book_no_fill_leaves_open(db):
    _seed_cnq(db)
    unfilled = _sell("s-2", "CNQ", E0 + DAY + 30, 0, 51.2)
    unfilled["filled_avg_price"] = None
    brk = FakeBroker([_sell("b-1", "CNQ", E0 + DAY + 30, 479, 51.2, side="buy"), unfilled,
                      _sell("s-3", "XYZ", E0 + DAY + 30, 479, 51.2)])
    res = XF.book(brk, held_symbols=set())
    assert res["no_fill"] == ["CNQ"] and res["written"] == []
    assert _fills(db) == []
    JN.reconcile()
    doc = JN.load()[0]
    assert doc["status"] == "open" and doc["fill_wanted"]["kind"] == "distribution_exit"
    # NEG: never an estimate at the decision `last`.
    assert doc["realized"] is None


def test_book_partials_summed_and_capped(db, monkeypatch):
    db.trade_ledger.insert_one(_entry("ASX", E0, qty=608, price=40.66, stop=38.0))
    for k in range(4):
        db.trade_ledger.insert_one(_force("watchdog_exit", "ASX", E0 + DAY + k * 60, 608, 37.04))
    brk = FakeBroker([_sell("a-1", "ASX", E0 + DAY + 10, 300, 37.10),
                      _sell("a-2", "ASX", E0 + DAY + 20, 400, 37.00)])
    res = XF.book(brk, held_symbols=set())
    assert res["candidates"] == 1
    det = _fills(db)[0]["detail"]
    assert det["qty"] == 608 and det["overfill_qty"] == 92
    assert det["fill"] == round((300 * 37.10 + 308 * 37.00) / 608, 4)
    assert det["order_ids"] == ["a-1", "a-2"] and det["partial"] is False
    assert det["held_qty"] == 608 and det["source_kind"] == "watchdog_exit"
    assert res["overfill"] == ["ASX"] and res["partial"] == []
    # NEG: one sell short of the cap is a partial, never an overfill.
    db2 = FakeDB()
    for mod in (EE, JN):
        monkeypatch.setattr(mod, "_db", lambda: db2)
    db2.trade_ledger.insert_one(_entry("PR", E0, qty=243, price=23.075, stop=22.0))
    db2.trade_ledger.insert_one(_force("distribution_exit", "PR", E0 + DAY, 243, 22.465))
    res = XF.book(FakeBroker([_sell("p-1", "PR", E0 + DAY + 10, 200, 22.4)]), held_symbols=set())
    assert res["partial"] == ["PR"] and res["overfill"] == []
    assert _fills(db2)[0]["detail"]["partial"] is True and _fills(db2)[0]["detail"]["qty"] == 200


def test_book_skips_booked_order_ids(db):
    db.trade_ledger.insert_one(_row("trade_closed", "ZZZ", E0 - DAY, detail={"order_id": "s-1", "leg": "stop",
                                                                            "fill": 9.0, "gain_pct": -3.0}))
    db.trade_ledger.insert_one(_row("exit_fill", "YYY", E0 - DAY, detail={"order_ids": ["s-2"], "leg": "flatten",
                                                                         "fill": 9.0, "source": "broker_fill"}))
    _seed_cnq(db)
    brk = FakeBroker([_sell("s-1", "CNQ", E0 + DAY + 10, 479, 50.0), _sell("s-2", "CNQ", E0 + DAY + 15, 479, 50.5),
                      _sell("s-3", "CNQ", E0 + DAY + 20, 479, 51.2)])
    XF.book(brk, held_symbols=set())
    det = _fills(db)[-1]["detail"]
    assert det["order_ids"] == ["s-3"] and det["fill"] == 51.2
    # NEG: with every sell already booked elsewhere there is no fill.
    db.trade_ledger.rows = [r for r in db.trade_ledger.rows if r.get("symbol") != "CNQ"]
    _seed_cnq(db)
    db.trade_ledger.insert_one(_row("trade_closed", "QQQ", E0 - DAY, detail={"order_id": "s-3"}))
    res = XF.book(brk, held_symbols=set())
    assert res["no_fill"] == ["CNQ"] and res["written"] == []


def test_flatten_exit_fill_uses_the_sold_qty(db):
    """Fix round (2026-10-27): a fill-less flatten after a partial entry fill books the SOLD qty end to end."""
    db.trade_ledger.insert_one(_entry("SLAB", E0, qty=56, price=221.0, stop=210.0))
    db.trade_ledger.insert_one(_row("flatten", "SLAB", E0 + DAY, detail={"canceled": 1, "closed": True,
                                                                         "errors": []}))
    res = XF.book(FakeBroker([_sell("f-6", "SLAB", E0 + DAY + 30, 6, 220.0)]), held_symbols=set())
    assert [(r["qty"], r["fill"], r["realized"]) for r in res["written"]] == [(6, 220.0, -6.0)]
    JN.reconcile()
    doc = JN.load()[0]
    assert doc["status"] == "closed" and doc["exit"]["leg"] == "flatten"
    assert doc["realized"]["gain_dollars"] == -6.0
    assert JN.summary()["by_strategy"]["breakout"]["realized_pnl"] == -6.0
    # NEG: the served block equals the dry-run line, never the planned 56 shares.
    assert doc["realized"]["gain_dollars"] != -56.0


def test_shared_exit_fill_never_double_counts(db):
    """Fix round (2026-10-27): the later MRK trade's fill never closes the earlier MRK trade."""
    L = db.trade_ledger
    L.insert_one(_entry("MRK", E0, qty=91, price=134.0, stop=128.0, strategy="manual"))
    L.insert_one(_force("distribution_exit", "MRK", E0 + DAY, 91, 133.0))
    L.insert_one(_entry("MRK", E0 + 5 * DAY, qty=50, price=140.0, stop=133.0, strategy="breakout"))
    L.insert_one(_force("distribution_exit", "MRK", E0 + 6 * DAY, 50, 131.0))
    res = XF.book(FakeBroker([_sell("m-50", "MRK", E0 + 6 * DAY + 10, 50, 130.0)]), held_symbols=set())
    later = "MRK-%d" % int(E0 + 5 * DAY)
    assert [(r["trade_id"], r["realized"]) for r in res["written"]] == [(later, -500.0)]
    assert res["no_fill"] == ["MRK"]
    JN.reconcile()
    docs = {d["trade_id"]: d for d in JN.load()}
    first = docs["MRK-%d" % int(E0)]
    assert docs[later]["status"] == "closed" and docs[later]["realized"]["gain_dollars"] == -500.0
    # NEG: the earlier trade stays open + flagged; manual realized stays 0.0; the candidate never vanishes.
    assert first["status"] == "open" and first["fill_wanted"] is not None
    bs = JN.summary()["by_strategy"]
    assert bs["manual"]["realized_pnl"] == 0.0 and bs["manual"]["closed"] == 0
    assert bs["breakout"]["realized_pnl"] == -500.0
    assert [c["trade_id"] for c in JN.unbooked_exits()] == ["MRK-%d" % int(E0)]


def test_book_never_trades_or_pushes(db, monkeypatch):
    pushes = []
    monkeypatch.setattr(EE, "_notify_autopilot", lambda *a, **k: pushes.append(a))
    _seed_cnq(db)
    db.trade_ledger.insert_one(_entry("FRSH", E0 + 2 * DAY, qty=381, price=13.98, stop=13.0))
    db.trade_ledger.insert_one(_row("flatten", "FRSH", E0 + 3 * DAY, detail={"canceled": 1, "closed": True,
                                                                            "errors": []}))
    brk = FakeBroker([_sell("s-1", "CNQ", E0 + DAY + 10, 479, 51.2), _sell("f-1", "FRSH", E0 + 3 * DAY + 5, 381, 13.94)])
    res = XF.book(brk, held_symbols=set())
    assert len(res["written"]) == 2
    assert pushes == []
    kinds = {r["kind"] for r in db.trade_ledger.rows}
    assert "trade_closed" not in kinds
    assert {r["detail"]["leg"] for r in _fills(db)} == {"force_exit", "flatten"}
    # NEG: the source never names an order-side call.
    src = open(XF.__file__).read()
    for word in ("submit_", "cancel_order", "replace_order", "close_position", "_notify_autopilot"):
        assert word not in src


def test_book_engine_inputs_untouched(db):
    db.trade_ledger.insert_one(_row("trade_closed", "AAA", E0 - 5 * DAY,
                                    detail={"order_id": "tp-1", "leg": "take_profit", "fill": 110.0,
                                            "gain_pct": 10.0}))
    _seed_cnq(db)
    before = (EN._closed_trade_stats(), PG.last_gains(db))
    XF.book(FakeBroker([_sell("s-1", "CNQ", E0 + DAY + 10, 479, 51.2)]), held_symbols=set())
    assert len(_fills(db)) == 1
    after = (EN._closed_trade_stats(), PG.last_gains(db))
    assert before == after == ((10.0, 1), [10.0])
    # NEG pin: an exit_fill is never a trade_closed.
    assert all(r["kind"] != "trade_closed" for r in _fills(db))
    assert sum(1 for r in db.trade_ledger.rows if r["kind"] == "trade_closed") == 1


def test_book_lookback_and_precheck(db):
    now = E0 + 10 * DAY
    _seed_cnq(db)                                   # decision at E0 + 1 day = 9 days before now
    brk = FakeBroker([_sell("s-1", "CNQ", E0 + DAY + 10, 479, 51.2)])
    res = XF.book(brk, held_symbols=set(), lookback_days=EE.FLATTEN_SENT_LOOKBACK_DAYS, now=now)
    assert res["candidates"] == 0 and res["written"] == []
    assert brk.reads == []                          # pre-check: no force / fill-less row in the window
    # A recent decision of another symbol passes the pre-check; the old one is still outside the window.
    db.trade_ledger.insert_one(_entry("LNG", now - 2 * DAY, qty=20, price=276.88, stop=260.0))
    db.trade_ledger.insert_one(_force("distribution_exit", "LNG", now - DAY, 20, 277.15))
    brk.orders.append(_sell("l-1", "LNG", now - DAY + 10, 20, 277.0))
    res = XF.book(brk, held_symbols=set(), lookback_days=EE.FLATTEN_SENT_LOOKBACK_DAYS, now=now)
    assert res["candidates"] == 1 and [r["symbol"] for r in res["written"]] == ["LNG"]
    assert [s for s, _a, _u in brk.reads] == ["LNG"]
    # The back-fill (no lookback) books the old one.
    res = XF.book(brk, held_symbols=set(), lookback_days=None, now=now)
    assert [r["symbol"] for r in res["written"]] == ["CNQ"]


def test_book_broker_without_reader_skips(db, monkeypatch):
    _seed_cnq(db)
    brk = types.SimpleNamespace(positions=lambda: [])
    res = XF.book(brk, held_symbols=set())
    assert res["skipped"] == "broker has no closed_orders_for"
    assert res["written"] == [] and _fills(db) == []
    # NEG: no ledger at all -> skipped, nothing read.
    for mod in (EE, JN):
        monkeypatch.setattr(mod, "_db", lambda: None)
    assert XF.book(FakeBroker())["skipped"] == "no ledger"


def test_book_skip_queue_symbols(db):
    _seed_cnq(db)
    brk = FakeBroker([_sell("s-1", "CNQ", E0 + DAY + 10, 479, 51.2)])
    res = XF.book(brk, held_symbols=set(), skip_symbols={"CNQ"})
    assert res["skipped_queue"] == ["CNQ"] and res["written"] == [] and brk.reads == []
    # NEG: another queued symbol does not block this one.
    res = XF.book(brk, held_symbols=set(), skip_symbols={"AEIS"})
    assert [r["symbol"] for r in res["written"]] == ["CNQ"]


def test_backfill_dry_run_writes_nothing_then_live_then_rerun_noop(db, monkeypatch, capsys):
    _seed_cnq(db)
    db.trade_ledger.insert_one(_entry("PNTG", E0 + 2 * DAY, qty=324, price=38.23, stop=36.0))
    db.trade_ledger.insert_one(_force("distribution_exit", "PNTG", E0 + 3 * DAY, 324, 39.525))
    brk = FakeBroker([_sell("s-1", "CNQ", E0 + DAY + 10, 479, 51.2)])
    monkeypatch.setattr(EE, "broker", brk)
    n_rows = len(db.trade_ledger.rows)
    assert XF._main(["backfill", "--dry-run"]) == 0
    out = capsys.readouterr().out
    lines = out.strip().splitlines()
    assert lines[0] == "exit_fills backfill — DRY RUN (nothing written)"
    assert len(db.trade_ledger.rows) == n_rows
    cnq = next(ln for ln in lines if ln.startswith("CNQ"))
    assert cnq.endswith("WOULD WRITE") and "479 sold @ 51.2 (1 order) · realized -$182.02" in cnq
    assert cnq.startswith("CNQ    breakout      entry ")
    assert next(ln for ln in lines if ln.startswith("PNTG")).endswith("NO FILL FOUND — left open")
    tail = json.loads(lines[-1])
    assert tail["candidates"] == 2 and tail["would_write"] == 1 and tail["written"] == 0
    assert tail["no_fill"] == ["PNTG"] and tail["still_held"] == [] and tail["overfill"] == []
    # NEG: no broker key or URL is ever printed.
    for bad in ("alpaca.markets", "http", "APCA", "SECRET"):
        assert bad not in out
    assert XF._main(["backfill", "--live"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "exit_fills backfill — LIVE"
    assert next(ln for ln in out.splitlines() if ln.startswith("CNQ")).endswith("WRITTEN")
    rows = _fills(db)
    assert len(rows) == 1 and rows[0]["detail"]["source"] == XF.SOURCE_BACKFILL
    assert rows[0]["detail"].get("backfilled_at")
    assert json.loads(out.strip().splitlines()[-1])["written"] == 1
    assert XF._main(["backfill", "--dry-run"]) == 0
    tail = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert tail["would_write"] == 0 and tail["candidates"] == 1
    # NEG: an unknown verb does nothing.
    assert XF._main(["backfill"]) == 2 and len(_fills(db)) == 1


def test_rollback_scoped(db):
    L = db.trade_ledger
    L.insert_one(_entry("CNQ", E0))
    L.insert_one(_row("exit_fill", "CNQ", E0 + DAY, detail={"source": XF.SOURCE_BACKFILL, "leg": "force_exit"}))
    L.insert_one(_row("exit_fill", "PR", E0 + DAY, detail={"source": XF.SOURCE_BACKFILL, "leg": "force_exit"}))
    L.insert_one(_row("exit_fill", "EMR", E0 + DAY, detail={"source": XF.SOURCE_LIVE, "leg": "force_exit"}))
    L.insert_one(_row("trade_closed", "AAA", E0 + DAY, detail={"source": XF.SOURCE_BACKFILL}))
    assert XF.rollback(dry_run=True) == {"rows": 2, "deleted": 0}
    assert len(L.rows) == 5
    assert XF.rollback(dry_run=False) == {"rows": 2, "deleted": 2}
    left = sorted((r["kind"], r["symbol"]) for r in L.rows)
    assert left == [("entry", "CNQ"), ("exit_fill", "EMR"), ("trade_closed", "AAA")]
    # NEG: a second rollback deletes nothing more.
    assert XF.rollback(dry_run=False) == {"rows": 0, "deleted": 0}


# ── 13: the tick hook (e2) ────────────────────────────────────────────────────

class _TickBroker(FakeBrokerModule):
    def __init__(self, orders_for=(), **kw):
        super().__init__(**kw)
        self._closed_for = [dict(o) for o in orders_for]

    def closed_orders_for(self, symbol, after_iso, until_iso=None):
        return [dict(o) for o in self._closed_for if o.get("symbol") == symbol
                and (o.get("submitted_at") or "") > (after_iso or "")]


def _tick_env(monkeypatch, fake):
    fdb = FakeDB()
    for mod in (EE, JN, OL, ZD, EN):
        monkeypatch.setattr(mod, "_db", lambda: fdb)
    monkeypatch.setattr(EE, "broker", fake)
    monkeypatch.setattr(EN, "broker", fake)
    monkeypatch.setattr(EE, "regime", lambda: "normal")
    monkeypatch.setattr(EN, "regime", lambda: "normal")
    monkeypatch.setattr(EE, "_distribution_read", lambda sym: None)
    stub = types.ModuleType("sepa.earnings_watch")
    stub.next_event = lambda s: None
    monkeypatch.setitem(sys.modules, "sepa.earnings_watch", stub)
    now = time.time()
    fdb.trade_ledger.insert_one(_entry("EMR", now - 3 * DAY, qty=36, price=152.895, stop=145.0))
    fdb.trade_ledger.insert_one(_force("distribution_exit", "EMR", now - 2 * HOUR, 36, 161.475))
    return fdb, now


def test_tick_e2_books_after_force_exit_and_leaves_streak(monkeypatch):
    now = time.time()
    fake = _TickBroker(orders_for=[_sell("e-1", "EMR", now - 2 * HOUR + 5, 36, 161.4)], positions=())
    fdb, _ = _tick_env(monkeypatch, fake)
    summary = EE.tick()
    assert [r["symbol"] for r in summary["exit_fills"]["written"]] == ["EMR"]
    rows = _fills(fdb)
    assert len(rows) == 1 and rows[0]["detail"]["source"] == XF.SOURCE_LIVE and rows[0]["detail"]["qty"] == 36
    cfg = EE.get_config()
    assert cfg["consecutive_losses"] == 2 and cfg["processed_order_ids"] == ["seen-1"]
    assert fake.calls == []                          # no order of any kind
    assert not any(str(e).startswith("exit_fills") for e in summary["errors"])


def test_tick_e2_broker_without_reader_is_skipped_not_an_error(monkeypatch):
    fake = FakeBrokerModule(positions=())
    fdb, _ = _tick_env(monkeypatch, fake)
    summary = EE.tick()
    assert summary["exit_fills"]["skipped"] == "broker has no closed_orders_for"
    assert not any(str(e).startswith("exit_fills") for e in summary["errors"])
    assert _fills(fdb) == []


# ── 14-15: the broker readers ─────────────────────────────────────────────────

def test_closed_orders_for_params_and_pagination(monkeypatch):
    calls = []

    def page(start, n):
        return [{"id": "o%d" % i, "symbol": "ASX", "submitted_at": "2026-09-14T14:%02d:%02d.%06dZ"
                 % (i // 3600 % 60, i // 60 % 60, i)} for i in range(start, start + n)]

    pages = [page(0, 500), page(499, 21)]           # o499 repeats on page 2

    def fake_request(method, path, params=None, json_body=None, base=None):
        calls.append((method, path, dict(params or {})))
        return pages[len(calls) - 1]

    monkeypatch.setattr(BA, "_request", fake_request)
    out = BA.closed_orders_for("asx", "2026-09-10T13:30:00Z", "2026-09-20T20:00:00Z")
    assert len(calls) == 2
    m, p, params = calls[0]
    assert (m, p) == ("GET", "/v2/orders")
    assert params == {"status": "closed", "symbols": "ASX", "after": "2026-09-10T13:30:00Z",
                      "until": "2026-09-20T20:00:00Z", "direction": "asc", "limit": 500}
    assert calls[1][2]["after"] == pages[0][-1]["submitted_at"]
    assert len(out) == 520 and len({o["id"] for o in out}) == 520
    # NEG: no `until` key when none is given; a short first page is the only call.
    calls.clear()
    pages[:] = [page(0, 3)]
    BA.closed_orders_for("ASX", "2026-09-10T13:30:00Z")
    assert len(calls) == 1 and "until" not in calls[0][2]
    # NEG: an endless 500-row stream stops at the 10-page guard.
    calls.clear()
    counter = {"n": 0}

    def endless(method, path, params=None, json_body=None, base=None):
        counter["n"] += 1
        calls.append(params)
        return page(counter["n"] * 1000, 500)

    monkeypatch.setattr(BA, "_request", endless)
    BA.closed_orders_for("ASX", "2026-09-10T13:30:00Z")
    assert len(calls) == 10


def test_sim_closed_orders_for_filters_symbol_and_window(monkeypatch):
    sim = types.SimpleNamespace(sim_orders=FakeColl([
        {"id": "a1", "symbol": "AAA", "status": "filled", "submitted_at": "2026-10-01T15:00:00Z"},
        {"id": "a2", "symbol": "AAA", "status": "canceled", "submitted_at": "2026-10-01T14:00:00Z"},
        {"id": "a3", "symbol": "AAA", "status": "new", "submitted_at": "2026-10-01T14:30:00Z"},
        {"id": "a4", "symbol": "AAA", "status": "filled", "submitted_at": "2026-09-30T15:00:00Z"},
        {"id": "a5", "symbol": "AAA", "status": "filled", "submitted_at": "2026-10-03T15:00:00Z"},
        {"id": "b1", "symbol": "BBB", "status": "filled", "submitted_at": "2026-10-01T15:00:00Z"},
    ]))
    monkeypatch.setattr(BS, "_require_db", lambda: sim)
    out = BS.closed_orders_for("aaa", "2026-10-01T00:00:00Z", "2026-10-02T00:00:00Z")
    assert [o["id"] for o in out] == ["a2", "a1"]                 # terminal, symbol, window, oldest first
    # NEG: no until -> the later fill is included; never another symbol, never a working order.
    out = BS.closed_orders_for("AAA", "2026-10-01T00:00:00Z")
    assert [o["id"] for o in out] == ["a2", "a1", "a5"]
    assert all(o["symbol"] == "AAA" and o["status"] != "new" for o in out)


# ── 16-17: status() + the baseline date ───────────────────────────────────────

OCC_KSS = "KSS261120C00015000"
OCC_BABA = "BABA261120C00120000"


class _StatusBroker(FakeBrokerModule):
    def account(self):
        return {"equity": "101615", "cash": "100000", "buying_power": "100000", "account_number": "PA1"}


def _status_env(monkeypatch):
    fdb = FakeDB()
    fdb.trading_account_baseline.insert_one({"account_key": "PA1", "starting_equity": 100000.0,
                                             "snapshot_ts": "2026-07-13T15:17:27Z"})
    for mod in (EE, JN, OL, ZD, EN):
        monkeypatch.setattr(mod, "_db", lambda: fdb)
    fake = _StatusBroker(positions=[
        {"symbol": OCC_KSS, "asset_class": "us_option", "qty": "5", "cost_basis": "775", "market_value": "875",
         "unrealized_pl": "100"},
        {"symbol": OCC_BABA, "asset_class": "us_option", "qty": "1", "cost_basis": "840", "market_value": "740",
         "unrealized_pl": "-100"}])
    monkeypatch.setattr(EE, "broker", fake)
    monkeypatch.setattr(EE, "regime", lambda: "normal")
    from trading import auto_entry, catalyst_entry, gajjala_entry, zone_edge_entry
    for mod in (auto_entry, zone_edge_entry, catalyst_entry, gajjala_entry):
        monkeypatch.setattr(mod, "status_block", lambda *a, **k: {"enabled": False})
    blk = {"n": 2, "open": 2, "closed": 0, "wins": 0, "losses": 0, "win_rate_pct": None, "avg_r": None,
           "expectancy_pct": None, "realized_pnl": 0.0, "first_ts": "2026-10-09T14:00:00Z",
           "last_ts": "2026-10-19T14:00:00Z"}
    monkeypatch.setattr(OL, "status_block", lambda *a, **k: {
        "enabled": True, "journal": blk,
        "open": [{"pos_id": "KSS-1", "legs": [{"symbol": OCC_KSS}]}, {"pos_id": "BABA-1", "legs": [{"symbol": OCC_BABA}]}]})
    monkeypatch.setattr(ZD, "status_block", lambda *a, **k: {"enabled": False, "journal": {"n": 0}, "open": []})
    return fdb, fake


def test_status_serves_lane_pnl_and_option_cost_basis(monkeypatch):
    _status_env(monkeypatch)
    out = EE.status()
    assert out["error"] is None
    pnl = out["pnl_summary"]
    assert pnl["unrealized_dollars"] == 0.0                     # +100 - 100: the options' gain, not their value
    assert pnl["invested"] == 1615.0 and pnl["market_value"] == 1615.0
    lp = out["lane_pnl"]
    assert isinstance(lp["rows"], list)
    row = next(r for r in lp["rows"] if r["key"] == "options_zone")
    assert row["held"] == 2 and row["unrealized_pnl"] == 0.0
    assert lp["since"] == "2026-07-13"
    json.dumps(lp, allow_nan=False)
    # NEG: before the fix the full market value read as gain.
    assert pnl["unrealized_dollars"] != 1615.0
    # NEG: lane_pnl_block raising never breaks status().
    monkeypatch.setattr(JN, "lane_pnl_block", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    out = EE.status()
    assert out["lane_pnl"] == {"error": "P&L by lane unavailable (RuntimeError)"}
    assert out["pnl_summary"]["unrealized_dollars"] == 0.0


def test_status_broker_down_serves_lane_pnl_without_positions(monkeypatch):
    _, fake = _status_env(monkeypatch)

    def down():
        raise BA.BrokerError("alpaca GET /v2/account -> HTTP 503: down")

    monkeypatch.setattr(fake, "account", down)
    out = EE.status()
    assert out["error"]
    assert out["pnl_summary"]["invested"] == 0.0                 # opt_cost stays 0.0
    assert out["lane_pnl"].get("positions_text")                  # broker unknown, said once


def test_account_baseline_ts(monkeypatch):
    fdb = FakeDB()
    fdb.trading_account_baseline.insert_one({"account_key": "PA1", "starting_equity": 98203.6,
                                             "snapshot_ts": "2026-07-13T15:17:27Z"})
    monkeypatch.setattr(EE, "_db", lambda: fdb)
    assert EE.account_baseline_ts({"account_number": "PA1", "equity": "87183.56"}) == "2026-07-13T15:17:27Z"
    # NEG: never seeds — an unknown account reads None and the collection is unchanged.
    assert EE.account_baseline_ts({"account_number": "PA9", "equity": "5"}) is None
    assert len(fdb.trading_account_baseline.rows) == 1

    def boom():
        raise AssertionError("the DB must not be touched for a sim account")

    monkeypatch.setattr(EE, "_db", boom)
    # NEG: the SIM reports starting_cash itself -> None, DB untouched.
    assert EE.account_baseline_ts({"starting_cash": 5000.0, "equity": 5100.0}) is None
    monkeypatch.setattr(EE, "_db", lambda: None)
    assert EE.account_baseline_ts({"account_number": "PA1"}) is None
