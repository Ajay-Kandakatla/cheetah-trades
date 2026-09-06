"""Flatten queue (2026-09-05) — owner exits Alpaca refused outside the
session because the shares were held for pending-cancel orders.

Saturday 2026-09-05: Ajay chose to exit AEIS/APLD/LUNR at Monday open.
exit_engine.flatten() cancelled each bracket (its take-profit limit carries
the stop leg), then Alpaca refused DELETE /v2/positions/{sym} with HTTP 403
code 40310000 "insufficient qty available for order (requested: 44,
available: 0)" — the cancels sit in pending_cancel until the next session.
So the exit is queued in trading_config and the tick drains it.

Every test runs against the FakeBrokerModule / FakeDB fakes from
test_trading_engine.py — no Mongo, no Docker, no Alpaca, no network."""
from __future__ import annotations

import sys
import types

import pytest

import trading.exit_engine as EE
import trading.entries as EN
from trading.broker_alpaca import BrokerError

from tests.test_trading_engine import FakeBrokerModule, FakeColl, FakeDB, _position

HELD = ('alpaca DELETE /v2/positions/AEIS -> HTTP 403: {"available":"0",'
        '"code":40310000,"existing_qty":"44","held_for_orders":"44",'
        '"message":"insufficient qty available for order (requested: 44, '
        'available: 0)","symbol":"AEIS"}')


def _tp_leg(symbol, oid="tp-1", status="new"):
    """The bracket take-profit sell LIMIT that carries the stop leg."""
    return {"id": oid, "symbol": symbol, "qty": "44", "side": "sell",
            "type": "limit", "status": status, "limit_price": "305.84",
            "stop_price": None, "legs": None}


def _mkt_sell(symbol, oid="sell-mkt-1", status="accepted", fill=None):
    o = {"id": oid, "symbol": symbol, "qty": "44", "side": "sell",
         "type": "market", "status": status, "legs": None}
    if fill is not None:
        o["filled_avg_price"] = str(fill)
        o["filled_at"] = "2026-09-08T13:30:05Z"
    return o


class CasColl(FakeColl):
    """FakeColl whose update_one reports matched_count like pymongo, so the
    compare-and-set queue write is exercised for real."""

    def update_one(self, q, update, upsert=False):
        matched = sum(1 for d in self.rows if self._match(d, q))
        super().update_one(q, update, upsert=upsert)
        return types.SimpleNamespace(matched_count=matched)


class QueueBroker(FakeBrokerModule):
    """FakeBrokerModule + Alpaca's held-shares refusal and closed orders."""

    def __init__(self, positions=(), orders=(), held=(), closed=(),
                 close_error=None, close_id="sell-mkt-1", market_open=True):
        super().__init__(positions, orders, 100_000.0, market_open)
        self.held = set(held)
        self.closed = list(closed)
        self.close_error = close_error
        self.close_id = close_id

    def close_position(self, symbol):
        self.calls.append(("close_position", {"symbol": symbol}))
        if symbol in self.held:
            raise BrokerError(HELD.replace("AEIS", symbol))
        if self.close_error:
            raise BrokerError(self.close_error)
        return {"id": self.close_id, "symbol": symbol, "side": "sell",
                "type": "market", "status": "accepted"}

    def closed_orders_since(self, iso_ts):
        return [dict(o) for o in self.closed]


@pytest.fixture
def qenv(monkeypatch):
    """Wired engine env with a QueueBroker; returns (broker, db, pushes)."""

    def build(positions=(), orders=(), armed=True, held=(), closed=(),
              close_error=None, close_id="sell-mkt-1", market_open=True,
              queue=None):
        fake = QueueBroker(positions, orders, held, closed, close_error,
                           close_id, market_open)
        db = FakeDB(armed=armed)
        db.trading_config = CasColl(db.trading_config.rows)
        db.trading_account_baseline = FakeColl()   # status() P&L baseline
        db.trade_journal = FakeColl()              # tick step (g) journal reconcile
        if queue:
            db.trading_config.rows[0]["flatten_queue"] = [dict(e) for e in queue]
        pushes = []
        monkeypatch.setattr(EE, "broker", fake)
        monkeypatch.setattr(EN, "broker", fake)
        monkeypatch.setattr(EE, "_db", lambda: db)
        monkeypatch.setattr(EN, "_db", lambda: db)
        monkeypatch.setattr(EE, "regime", lambda: "normal")
        monkeypatch.setattr(EN, "regime", lambda: "normal")
        monkeypatch.setattr(EE, "_distribution_read", lambda sym: None)
        monkeypatch.setattr(EE, "_notify_autopilot",
                            lambda kind, sym, text: pushes.append((kind, sym, text)))
        stub = types.ModuleType("sepa.earnings_watch")
        stub.next_event = lambda s: None
        monkeypatch.setitem(sys.modules, "sepa.earnings_watch", stub)
        return fake, db, pushes

    return build


def _calls(broker, method):
    return [kw for name, kw in broker.calls if name == method]


def _rows(db, kind):
    return [r for r in db.trade_ledger.rows if r.get("kind") == kind]


def _queue(db):
    return EE.get_config()["flatten_queue"]


PENDING = {"symbol": "AEIS", "reason": "pre-gate cohort", "state": "pending",
           "queued_at": "2026-09-06T04:17:07Z", "order_id": None, "sent_at": None}
SENT = dict(PENDING, state="sent", order_id="sell-mkt-1", sent_at="2026-09-08T13:00:00Z")


# ── flatten(): the owner's Exit button ───────────────────────────────────────

def test_flatten_queues_on_alpaca_held_refusal(qenv):
    broker, db, _ = qenv(positions=[_position("AEIS", 44, 278.035, 280.9)],
                         orders=[_tp_leg("AEIS")], held={"AEIS"})
    res = EE.flatten("AEIS", reason="  pre-gate cohort  ")

    assert res["queued"] is True and res["closed"] is False and res["canceled"] == 1
    assert _calls(broker, "cancel_order") == [{"order_id": "tp-1"}]
    q = _queue(db)
    assert len(q) == 1 and q[0]["symbol"] == "AEIS" and q[0]["state"] == "pending"
    assert q[0]["reason"] == "pre-gate cohort" and q[0]["queued_at"]
    assert res["queue"]["symbol"] == "AEIS" and "order_id" not in res["queue"]
    # The queued row is the record; NO plain "flatten" row (the journal would
    # read it as an exit).
    assert len(_rows(db, "flatten_queued")) == 1 and not _rows(db, "flatten")
    assert _rows(db, "flatten_queued")[0]["detail"]["reason"] == "pre-gate cohort"


def test_flatten_does_not_recancel_pending_cancel_orders(qenv):
    """Second Exit click while the first cancel is still pending: Alpaca
    answers HTTP 422 'order pending cancel' to a repeat — do not send it."""
    broker, db, _ = qenv(positions=[_position("AEIS", 44, 278.0, 280.0)],
                         orders=[_tp_leg("AEIS", oid="tp-1", status="pending_cancel"),
                                 _tp_leg("AEIS", oid="stop-2", status="held")],
                         held={"AEIS"})
    res = EE.flatten("AEIS", reason="again")
    assert res["queued"] is True and res["already_cancelling"] == 1
    assert _calls(broker, "cancel_order") == [{"order_id": "stop-2"}]
    assert len(res["errors"]) == 1 and "40310000" in res["errors"][0]


def test_flatten_other_broker_error_is_not_queued(qenv):
    broker, db, _ = qenv(positions=[_position("AEIS", 44, 278.0, 280.0)],
                         close_error="alpaca DELETE /v2/positions/AEIS -> HTTP 500: boom")
    res = EE.flatten("AEIS")
    assert res["queued"] is False and res["closed"] is False
    assert _queue(db) == [] and not _rows(db, "flatten_queued")
    row = _rows(db, "flatten")[0]
    assert row["detail"]["closed"] is False and row["detail"]["errors"]


def test_flatten_success_carries_the_reason(qenv):
    broker, db, _ = qenv(positions=[_position("AEIS", 44, 278.0, 280.0)])
    res = EE.flatten("AEIS", reason="x" * 400)
    assert res["closed"] is True and res["queued"] is False
    assert len(_rows(db, "flatten")[0]["detail"]["reason"]) == EE.FLATTEN_REASON_MAX


def test_disarmed_flatten_never_queues_or_sends(qenv):
    broker, db, _ = qenv(positions=[_position("AEIS", 44, 278.0, 280.0)],
                         orders=[_tp_leg("AEIS")], held={"AEIS"}, armed=False)
    res = EE.flatten("AEIS", reason="why")
    assert res["dry_run"] is True and res["queued"] is False
    assert not _calls(broker, "cancel_order") and not _calls(broker, "close_position")
    assert _queue(db) == []
    assert _rows(db, "flatten")[0]["dry_run"] is True


# ── tick step (a2): the drain ────────────────────────────────────────────────

def test_drain_skipped_when_disarmed_no_broker_mutations(qenv):
    broker, db, _ = qenv(positions=[_position("AEIS", 44, 278.0, 280.0)],
                         orders=[_tp_leg("AEIS", status="pending_cancel")],
                         armed=False, queue=[PENDING])
    summary = EE.tick()
    assert summary["flatten_queue"]["skipped_disarmed"] == 1
    assert summary["flatten_queue"]["drained"] == 0
    assert not _calls(broker, "cancel_order") and not _calls(broker, "close_position")
    assert _queue(db)[0]["state"] == "pending"


def test_drain_runs_before_the_market_closed_return(qenv):
    """Alpaca accepts a market sell outside hours (it queues for the open),
    so the drain must not wait for the 9:30 tick."""
    broker, db, pushes = qenv(positions=[_position("AEIS", 44, 278.035, 280.9)],
                              orders=[_tp_leg("AEIS", status="pending_cancel")],
                              market_open=False, queue=[PENDING])
    summary = EE.tick()
    assert summary["reason"] == "market_closed"
    assert summary["flatten_queue"]["drained"] == 1
    # The only open order is already pending_cancel: a second cancel is what
    # Alpaca rejects, so none is sent; the close goes out.
    assert not _calls(broker, "cancel_order")
    assert _calls(broker, "close_position") == [{"symbol": "AEIS"}]
    q = _queue(db)
    assert q[0]["state"] == "sent" and q[0]["order_id"] == "sell-mkt-1" and q[0]["sent_at"]
    row = _rows(db, "flatten")[0]
    assert row["dry_run"] is False and row["detail"]["closed"] is True
    assert row["detail"]["reason"] == "pre-gate cohort"
    assert row["detail"]["note"] == "drained from flatten_queue"
    assert row["detail"]["order_id"] == "sell-mkt-1"
    assert len(pushes) == 1 and pushes[0][0] == "position_alert" and pushes[0][1] == "AEIS"
    assert "pre-gate cohort" in pushes[0][2]


def test_pending_drain_cancels_live_orders_but_not_pending_cancel_ones(qenv):
    broker, db, _ = qenv(positions=[_position("AEIS", 44, 278.0, 280.0)],
                         orders=[_tp_leg("AEIS", oid="tp-old", status="pending_cancel"),
                                 _tp_leg("AEIS", oid="stop-new", status="new"),
                                 _tp_leg("BBB", oid="tp-bbb", status="new")],
                         queue=[PENDING])
    EE.tick()
    assert _calls(broker, "cancel_order") == [{"order_id": "stop-new"}]
    assert _rows(db, "flatten")[0]["detail"]["canceled"] == 1


def test_still_held_stays_pending_and_protect_loop_skips_it(qenv):
    broker, db, _ = qenv(positions=[_position("AEIS", 44, 278.0, 280.0),
                                    _position("BBB", 100, 100.0, 102.0)],
                         held={"AEIS"}, queue=[PENDING])
    s1 = EE.tick()
    assert s1["flatten_queue"]["still_held"] == 1
    assert s1["flatten_queue"]["protect_skipped"] == 1
    # BBB (not queued) still gets its protective stop; AEIS must NOT — a new
    # stop would re-hold the shares and block the close forever.
    stops = _calls(broker, "submit_stop")
    assert [c["symbol"] for c in stops] == ["BBB"]
    assert _queue(db)[0]["state"] == "pending"
    assert not _rows(db, "flatten")           # nothing to journal yet
    s2 = EE.tick()                            # next minute: same, no spam
    assert s2["flatten_queue"]["still_held"] == 1
    assert not _rows(db, "flatten") and not _rows(db, "flatten_queued")
    assert not [e for e in s1["errors"] + s2["errors"] if "flatten" in e]


def test_other_close_error_is_surfaced_and_entry_kept(qenv):
    broker, db, _ = qenv(positions=[_position("AEIS", 44, 278.0, 280.0)],
                         close_error="alpaca DELETE -> HTTP 500: boom", queue=[PENDING])
    s = EE.tick()
    assert s["flatten_queue"]["still_held"] == 0
    assert any("flatten_queue AEIS" in e for e in s["flatten_queue"]["errors"])
    assert _queue(db)[0]["state"] == "pending"


def test_sent_entry_waits_while_its_order_is_open(qenv):
    broker, db, _ = qenv(positions=[_position("AEIS", 44, 278.0, 280.0)],
                         orders=[_mkt_sell("AEIS", "sell-mkt-1", "accepted")],
                         queue=[SENT])
    s = EE.tick()
    assert s["flatten_queue"]["sent_waiting"] == 1
    # Never cancel our own sell, never send a second one, never re-protect.
    assert not _calls(broker, "cancel_order") and not _calls(broker, "close_position")
    assert not _calls(broker, "submit_stop")
    assert _queue(db)[0] == SENT


def test_sent_order_vanished_position_remains_retries_from_pending(qenv):
    broker, db, _ = qenv(positions=[_position("AEIS", 44, 278.0, 280.0)],
                         orders=[], close_id="sell-mkt-2", queue=[SENT])
    s = EE.tick()
    assert s["flatten_queue"]["drained"] == 1
    assert _calls(broker, "close_position") == [{"symbol": "AEIS"}]
    q = _queue(db)[0]
    assert q["state"] == "sent" and q["order_id"] == "sell-mkt-2"


def test_position_gone_journals_the_fill_and_drops_the_entry(qenv):
    broker, db, pushes = qenv(
        positions=[], closed=[_mkt_sell("AEIS", "sell-mkt-1", "filled", fill=281.10)],
        queue=[SENT])
    EE.ledger("entry", symbol="AEIS", detail={"price": 278.035, "qty": 44})
    s = EE.tick()
    assert s["flatten_queue"]["done"] == 1
    assert _queue(db) == []
    tc = _rows(db, "trade_closed")
    assert len(tc) == 1
    d = tc[0]["detail"]
    assert d["leg"] == "flatten" and d["fill"] == 281.10 and d["entry"] == 278.035
    assert d["gain_pct"] == pytest.approx(1.1, abs=0.01)
    assert d["reason"] == "pre-gate cohort" and d["order_id"] == "sell-mkt-1"
    done = _rows(db, "flatten_done")[0]["detail"]
    assert done["filled"] is True and done["state"] == "sent"
    assert len(pushes) == 1 and "281.10" in pushes[0][2]


def test_position_gone_without_a_fill_still_drops_the_entry(qenv):
    broker, db, pushes = qenv(positions=[], closed=[], queue=[SENT])
    EE.tick()
    assert _queue(db) == [] and not _rows(db, "trade_closed")
    assert _rows(db, "flatten_done")[0]["detail"]["filled"] is False
    assert pushes == []


def test_position_gone_pending_entry_is_dropped_without_a_fill_row(qenv):
    """Stopped out by another path before the drain ever sent a sell: the
    stop fill already journals itself (tick step e); no trade_closed here."""
    broker, db, _ = qenv(positions=[], closed=[_mkt_sell("AEIS", "x", "filled", fill=1)],
                         queue=[PENDING])
    EE.tick()
    assert _queue(db) == [] and not _rows(db, "trade_closed")
    assert _rows(db, "flatten_done")[0]["detail"]["state"] == "pending"


def test_drain_is_fenced_from_the_rest_of_the_tick(qenv, monkeypatch):
    broker, db, _ = qenv(positions=[_position("BBB", 100, 100.0, 102.0)], queue=[PENDING])

    def boom():
        raise RuntimeError("drain bug")

    monkeypatch.setattr(EE, "_drain_flatten_queue", boom)
    s = EE.tick()
    assert any("flatten_queue: drain bug" in e for e in s["errors"])
    assert [c["symbol"] for c in _calls(broker, "submit_stop")] == ["BBB"]


# ── status(), queue helpers, API reason cleaning ─────────────────────────────

def test_status_reports_queue_and_marks_the_row(qenv):
    broker, db, _ = qenv(positions=[_position("AEIS", 44, 278.0, 280.0),
                                    _position("BBB", 100, 100.0, 102.0)],
                         queue=[PENDING])
    out = EE.status()
    assert out["flatten_queue"] == [{"symbol": "AEIS", "reason": "pre-gate cohort",
                                     "queued_at": "2026-09-06T04:17:07Z",
                                     "state": "pending", "sent_at": None}]
    rows = {p["symbol"]: p for p in out["positions"]}
    assert rows["AEIS"]["exit_queued"] is True
    assert rows["AEIS"]["exit_queue_state"] == "pending"
    assert rows["AEIS"]["stop_status"] == "queued" and rows["AEIS"]["protected"] is True
    assert rows["BBB"]["exit_queued"] is False and rows["BBB"]["exit_queue_state"] is None
    assert "AEIS" not in out["unprotected"]


def test_unqueue_removes_the_entry_and_records_it(qenv):
    broker, db, _ = qenv(queue=[SENT])
    assert EE.unqueue_flatten("aeis") is True
    assert _queue(db) == []
    row = _rows(db, "flatten_unqueued")[0]
    assert row["detail"]["state"] == "sent" and "untouched" in row["detail"]["note"]
    assert EE.unqueue_flatten("AEIS") is False
    assert not _calls(broker, "cancel_order")   # the accepted sell is left alone


def test_queue_flatten_is_idempotent_and_keeps_sent_state(qenv):
    broker, db, _ = qenv(queue=[SENT])
    e = EE.queue_flatten("AEIS", "newer reason")
    q = _queue(db)
    assert len(q) == 1 and e["state"] == "sent" and e["order_id"] == "sell-mkt-1"
    assert q[0]["reason"] == "newer reason"
    e2 = EE.queue_flatten("aeis")
    assert e2["reason"] == "newer reason"
    with pytest.raises(ValueError):
        EE.queue_flatten("  ")


def test_norm_queue_drops_garbage_and_dedupes():
    q = EE._norm_queue([None, "AEIS", {"symbol": ""}, {"symbol": " aeis ", "state": "weird",
                                                        "order_id": "x", "sent_at": "t"},
                        {"symbol": "AEIS", "state": "sent"}, {"symbol": "b", "state": "sent",
                                                               "order_id": "o", "sent_at": "s"}])
    assert q == [{"symbol": "AEIS", "reason": None, "queued_at": None, "state": "pending",
                  "order_id": None, "sent_at": None},
                 {"symbol": "B", "reason": None, "queued_at": None, "state": "sent",
                  "order_id": "o", "sent_at": "s"}]
    assert EE._norm_queue("nope") == [] and EE._norm_queue(None) == []


def test_held_for_orders_matches_alpaca_refusal_only():
    assert EE._held_for_orders(BrokerError(HELD)) is True
    assert EE._held_for_orders("code 40310000") is True
    assert EE._held_for_orders("HTTP 500: boom") is False
    assert EE._held_for_orders(None) is False


def test_api_flatten_reason_cleaning():
    from fastapi import HTTPException
    from trading import api as TA
    assert TA._flatten_reason(None) is None and TA._flatten_reason({}) is None
    assert TA._flatten_reason({"reason": None}) is None
    assert TA._flatten_reason({"reason": "   "}) is None
    assert TA._flatten_reason({"reason": " why "}) == "why"
    assert len(TA._flatten_reason({"reason": "x" * 999})) == EE.FLATTEN_REASON_MAX
    with pytest.raises(HTTPException):
        TA._flatten_reason({"reason": 5})


# ── concurrency: API flatten (api container) vs cron drain ───────────────────

def test_queue_writes_are_compare_and_set(qenv):
    broker, db, _ = qenv()
    doc = db.trading_config.rows[0]
    assert doc.get("flatten_queue_rev") in (None, 0)
    EE.queue_flatten("AEIS", "a")
    assert doc["flatten_queue_rev"] == 1
    EE.queue_flatten("BBB", "b")
    assert doc["flatten_queue_rev"] == 2 and [e["symbol"] for e in _queue(db)] == ["AEIS", "BBB"]
    assert EE.unqueue_flatten("AEIS") is True
    assert doc["flatten_queue_rev"] == 3 and [e["symbol"] for e in _queue(db)] == ["BBB"]
    # A stale revision never lands.
    assert EE._queue_write([], rev=99) is False
    assert [e["symbol"] for e in _queue(db)] == ["BBB"]


def test_commit_retries_after_a_conflicting_writer(qenv, monkeypatch):
    broker, db, _ = qenv()
    calls = {"n": 0}
    real = EE._queue_write

    def flaky(queue, rev):
        calls["n"] += 1
        if calls["n"] < 3:
            return False
        return real(queue, rev)

    monkeypatch.setattr(EE, "_queue_write", flaky)
    EE.queue_flatten("AEIS", "why")
    assert calls["n"] == 3 and _queue(db)[0]["symbol"] == "AEIS"


def test_drain_keeps_an_exit_queued_by_the_api_mid_drain(qenv):
    """The owner clicks Exit on NEWX (api container) while the cron drain is
    mid-flight on AEIS: the drain's write must not drop NEWX."""
    broker, db, _ = qenv(positions=[_position("AEIS", 44, 278.0, 280.0),
                                    _position("NEWX", 10, 50.0, 51.0)],
                         queue=[PENDING])
    doc = db.trading_config.rows[0]
    real_close = broker.close_position

    def close_and_race(symbol):
        # simulate the API path landing between the drain's read and write
        doc["flatten_queue"] = doc["flatten_queue"] + [
            {"symbol": "NEWX", "reason": "owner", "state": "pending",
             "queued_at": "2026-09-08T13:31:00Z", "order_id": None, "sent_at": None}]
        doc["flatten_queue_rev"] = int(doc.get("flatten_queue_rev") or 0) + 1
        return real_close(symbol)

    broker.close_position = close_and_race
    s = EE.tick()
    assert s["flatten_queue"]["drained"] == 1
    q = {e["symbol"]: e for e in _queue(db)}
    assert set(q) == {"AEIS", "NEWX"}
    assert q["AEIS"]["state"] == "sent" and q["NEWX"]["state"] == "pending"


def test_drain_respects_an_unqueue_that_landed_mid_drain(qenv):
    broker, db, _ = qenv(positions=[_position("AEIS", 44, 278.0, 280.0)], queue=[PENDING])
    doc = db.trading_config.rows[0]
    real_close = broker.close_position

    def close_and_unqueue(symbol):
        doc["flatten_queue"] = []
        doc["flatten_queue_rev"] = int(doc.get("flatten_queue_rev") or 0) + 1
        return real_close(symbol)

    broker.close_position = close_and_unqueue
    EE.tick()
    assert _queue(db) == []          # the owner's unqueue wins; the sent sell is out


def test_sent_order_filled_but_position_read_lags_waits_instead_of_reselling(qenv):
    broker, db, _ = qenv(positions=[_position("AEIS", 44, 278.0, 280.0)], orders=[],
                         closed=[_mkt_sell("AEIS", "sell-mkt-1", "filled", fill=281.0)],
                         queue=[SENT])
    s = EE.tick()
    assert s["flatten_queue"]["sent_waiting"] == 1
    assert not _calls(broker, "close_position") and not _calls(broker, "cancel_order")
    assert _queue(db)[0] == SENT
