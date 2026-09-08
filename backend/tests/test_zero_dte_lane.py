"""0DTE paper lane (2026-09-08) — owner rules on Signal Lab tags.

Ajay: "Can you also help me with doing options ODTE and Same day expire day
trading options please? I would like to see the accuracy and quick ness" and
"Did you start the ODTE options".

Every test runs against fakes: no Mongo, no Alpaca, no Massive. The signal
and the chain are stubbed at the two thin IO seams (_signal_for / _chain_row);
the broker is FakeOptBroker (records every order) plus mode() / cancel_order.
NEGATIVES throughout — a real-money trader reads this tab."""
from __future__ import annotations

from datetime import date, datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

import trading.exit_engine as EE
import trading.zero_dte_lane as ZD
from trading.broker_alpaca import BrokerError

from tests.test_trading_engine import FakeColl, FakeDB
from tests.test_options_lane import FakeOptBroker

ET = ZoneInfo("America/New_York")
TODAY = date.fromisoformat(EE._et_day())
NOW_ET = datetime.combine(TODAY, dtime(10, 30), tzinfo=ET)
NOW_UTC = NOW_ET.astimezone(timezone.utc)
EXP = TODAY.isoformat()
OCC_C = "SPY%sC00650000" % TODAY.strftime("%y%m%d")
OCC_P = "SPY%sP00646000" % TODAY.strftime("%y%m%d")

ROW = {"symbol": "SPY", "expiry": EXP, "spot": 648.2, "regime": "AMPLIFYING", "expected_move_pct": 0.9,
       "call": {"ticker": "O:" + OCC_C, "strike": 650.0, "bid": 1.20, "ask": 1.25, "delta": 0.36,
                "spread_pct": 4.1, "moves_needed": 0.4, "day_volume": 12000, "iv": 0.18},
       "put": {"ticker": "O:" + OCC_P, "strike": 646.0, "bid": 1.10, "ask": 1.15, "delta": -0.34,
               "spread_pct": 4.4, "moves_needed": 0.5, "day_volume": 9000, "iv": 0.19}}
SNAPS = {OCC_C: {"bid": 1.20, "ask": 1.25, "delta": 0.36}}
PUT_SNAPS = {OCC_P: {"bid": 1.10, "ask": 1.15, "delta": -0.34}}


def _frame_index(minutes: int = 60):
    start = datetime.combine(TODAY, dtime(9, 30), tzinfo=ET)
    return pd.DatetimeIndex([start + timedelta(minutes=i) for i in range(minutes)])


def _buy_events(i=59):
    return [{"i": 3, "kind": "sweep", "side": "sell_side"},
            {"i": i, "kind": "buy", "price": 648.2, "stop": 647.1, "target": 650.4}]


def _sell_events(i=59):
    return [{"i": i, "kind": "sell", "price": 648.2, "stop": 649.3, "target": 646.0}]


def _sig(events=None, now=NOW_UTC):
    return ZD.fresh_signal(events if events is not None else _buy_events(), _frame_index(), now)


class FakeZdBroker(FakeOptBroker):
    def __init__(self, *a, mode="paper", **kw):
        super().__init__(*a, **kw)
        self._mode = mode
        self.cancelled = []

    def mode(self):
        return self._mode

    def cancel_order(self, order_id):
        self.cancelled.append(order_id)

    def open_orders(self, symbol=None):
        return [dict(o) for o in self._orders]


@pytest.fixture
def zenv(monkeypatch):
    def build(armed=True, enabled=True, open_docs=(), attempts=(), signal="buy", row=ROW,
              now_et=NOW_ET, **broker_kw):
        broker_kw.setdefault("snaps", SNAPS)
        broker_kw.setdefault("put_snaps", PUT_SNAPS)
        broker_kw.setdefault("last", {"SPY": 648.5})
        fake = FakeZdBroker((), **broker_kw)
        db = FakeDB(armed=armed)
        db.trading_config.rows[0]["zero_dte_entry"] = enabled
        db.zero_dte_positions = FakeColl([dict(d) for d in open_docs])
        db.zero_dte_lane_state = FakeColl([dict(a) for a in attempts])
        for mod in (EE, ZD):
            monkeypatch.setattr(mod, "_db", lambda: db)
            monkeypatch.setattr(mod, "broker", fake)
        sig = (None if signal is None else _sig(_buy_events() if signal == "buy" else _sell_events()))
        monkeypatch.setattr(ZD, "_signal_for", lambda sym, now: sig if sym == "SPY" else None)
        monkeypatch.setattr(ZD, "_chain_row", lambda sym: row if sym == "SPY" else None)
        monkeypatch.setattr(ZD, "_now_et", lambda: now_et)
        return fake, db
    return build


def _pos(db, sym="SPY"):
    return next((d for d in db.zero_dte_positions.rows if d.get("symbol") == sym), None)


def _ledger(db, kind):
    return [r for r in db.trade_ledger.rows if r.get("kind") == kind]


# ── owner numbers ─────────────────────────────────────────────────────────────
def test_owner_numbers():
    assert ZD.STRATEGY == "zero_dte"
    assert (ZD.ENTRY_OPEN_ET, ZD.LAST_ENTRY_ET, ZD.FLATTEN_ET) == (dtime(9, 45), dtime(14, 30), dtime(15, 45))
    assert ZD.SIGNAL_MAX_AGE_SEC == 180 and ZD.ENTRY_FILL_WAIT_SEC == 180
    assert (ZD.RISK_PCT_OF_EQUITY, ZD.MAX_PREMIUM_PER_TRADE) == (0.5, 500.0)
    assert (ZD.MAX_ENTRIES_PER_DAY, ZD.MAX_OPEN) == (3, 3)
    assert (ZD.PREMIUM_TAKE_PCT, ZD.PREMIUM_STOP_PCT) == (100.0, 50.0)
    assert ZD.SKIP_REGIMES == ("PINNED",)


# ── pure pieces ───────────────────────────────────────────────────────────────
def test_fresh_signal_takes_the_last_tag_within_three_minutes():
    s = _sig()
    assert s and s["kind"] == "buy" and s["age_sec"] == 0.0
    assert s["bar_close_ts"] == NOW_UTC.isoformat()
    # 2 min old: still fresh; 4 min old: stale; a tag from the future: no
    assert _sig(now=NOW_UTC + timedelta(seconds=120)) is not None
    assert _sig(now=NOW_UTC + timedelta(seconds=181)) is None
    assert _sig(now=NOW_UTC - timedelta(seconds=30)) is None
    # NEGATIVE: sweeps/BOS alone are not entries; empty frames never crash
    assert ZD.fresh_signal([{"i": 3, "kind": "sweep"}], _frame_index(), NOW_UTC) is None
    assert ZD.fresh_signal([], _frame_index(), NOW_UTC) is None
    assert ZD.fresh_signal(_buy_events(i=999), _frame_index(), NOW_UTC) is None
    # naive-UTC index (daytrading.data shape) works too
    naive = pd.DatetimeIndex([t.astimezone(timezone.utc).replace(tzinfo=None) for t in _frame_index()])
    assert ZD.fresh_signal(_buy_events(), naive, NOW_UTC)["kind"] == "buy"


def test_size_is_whole_contracts_inside_the_smaller_budget():
    assert ZD.size_contracts(1.25, 100_000) == (4, 500.0, None)          # $500 cap beats 0.5% ($500)
    assert ZD.size_contracts(1.25, 40_000) == (1, 200.0, None)           # 0.5% of 40k = $200
    q, b, why = ZD.size_contracts(6.0, 100_000)
    assert q == 0 and b == 500.0 and "over the $500 budget" in why
    assert ZD.size_contracts(0, 100_000)[0] == 0 and ZD.size_contracts(1.0, 0)[0] == 0


def test_contract_for_maps_buy_to_call_sell_to_put_and_refuses_pins():
    c, why = ZD.contract_for(ROW, "buy")
    assert why is None and c["occ"] == OCC_C and c["otype"] == "call" and c["ask"] == 1.25
    c, why = ZD.contract_for(ROW, "sell")
    assert why is None and c["occ"] == OCC_P and c["otype"] == "put"
    assert ZD.contract_for(None, "buy") == (None, "no same-day chain")
    assert ZD.contract_for(dict(ROW, regime="PINNED"), "buy")[1] == "dealers PINNED — no 0DTE entry"
    assert ZD.contract_for(dict(ROW, put=None), "sell")[1] == "no tradeable put on the chain"
    assert ZD.contract_for(dict(ROW, call=dict(ROW["call"], ask=None)), "buy")[1] == "contract has no ask"
    assert ZD.occ_from_ticker("O:SPY260909C00650000") == "SPY260909C00650000"
    assert ZD.occ_from_ticker("SPY260909C00650000") == "SPY260909C00650000"
    assert ZD.occ_from_ticker(None) is None


def test_exit_reason_order_clock_stock_premium():
    call = {"side": "call", "signal": {"stop": 647.1, "target": 650.4}, "fill_price": 1.25}
    put = {"side": "put", "signal": {"stop": 649.3, "target": 646.0}, "fill_price": 1.15}
    t = datetime.combine(TODAY, dtime(11, 0), tzinfo=ET)
    assert ZD.exit_reason(call, 648.5, 1.30, t) is None                       # hold
    assert "signal stop" in ZD.exit_reason(call, 647.0, 1.30, t)
    assert "2R target" in ZD.exit_reason(call, 650.5, 1.30, t)
    assert "signal stop" in ZD.exit_reason(put, 649.4, 1.30, t)
    assert "2R target" in ZD.exit_reason(put, 645.9, 1.30, t)
    assert ZD.exit_reason(call, 648.5, 0.62, t).startswith("premium -50%")
    assert ZD.exit_reason(call, 648.5, 2.50, t).startswith("premium +100%")
    assert ZD.exit_reason(call, 648.5, 0.63, t) is None                       # -49.6%: hold
    # the clock beats everything, even a stock sitting on its target
    late = datetime.combine(TODAY, dtime(15, 45), tzinfo=ET)
    assert ZD.exit_reason(call, 650.5, 2.50, late).startswith("flatten 15:45")
    # NEGATIVE: no stock print and no mark -> hold, never a crash
    assert ZD.exit_reason(call, None, None, t) is None


def test_windows_and_latency_and_narrative():
    assert ZD.in_entry_window(dtime(9, 45)) and not ZD.in_entry_window(dtime(9, 44))
    assert ZD.in_entry_window(dtime(14, 29)) and not ZD.in_entry_window(dtime(14, 30))
    assert ZD.past_flatten(dtime(15, 45)) and not ZD.past_flatten(dtime(15, 44))
    t0 = NOW_UTC
    doc = {"pos_id": "SPY-x", "symbol": "SPY", "side": "call", "qty": 4, "expiry": EXP,
           "limit_price": 1.25, "status": "closed",
           "signal": {"kind": "buy", "price": 648.2, "stop": 647.1, "target": 650.4},
           "signal_bar_close_ts": t0.isoformat(), "seen_ts": (t0 + timedelta(seconds=12)).isoformat(),
           "order_ts": (t0 + timedelta(seconds=13)).isoformat(), "fill_ts": (t0 + timedelta(seconds=15)).isoformat(),
           "fill_price": 1.25, "contract": {"strike": 650.0, "delta": 0.36, "spread_pct": 4.1, "moves_needed": 0.4},
           "expected_move_pct": 0.9, "regime": "AMPLIFYING", "close_reason": "stock 650.5 hit the 2R target 650.4",
           "exit_price": 2.1, "realized_pnl": 340.0, "stock_move_pct": 0.35, "closed_ts": (t0 + timedelta(minutes=20)).isoformat()}
    lat = ZD.latency(doc)
    assert lat == {"signal_to_seen_sec": 12.0, "seen_to_order_sec": 1.0, "order_to_fill_sec": 2.0, "signal_to_fill_sec": 15.0}
    n = ZD.narrative(doc)
    assert n.startswith("Bought 4 × SPY %s $650.0 call @ $1.25 ask" % EXP)
    assert "Signal Lab BUY tag" in n and "stop 647.1, target 650.4 = 2R" in n
    assert "delta 0.36" in n and "dealers AMPLIFYING" in n
    assert "signal→fill 15.0s" in n and "hit the 2R target" in n and "P&L +340" in n and "stock 0.35%" in n
    # NEGATIVE: an empty doc still reads
    assert ZD.narrative({}).startswith("Bought ? × None")
    assert ZD.latency({}) == {"signal_to_seen_sec": None, "seen_to_order_sec": None,
                              "order_to_fill_sec": None, "signal_to_fill_sec": None}


def test_journal_block_counts_wins_losses_and_latency_medians():
    t0 = NOW_UTC.isoformat()
    def d(pnl, ret, move, s2f, status="closed"):
        return {"status": status, "realized_pnl": pnl, "premium_return_pct": ret, "stock_move_pct": move,
                "signal_bar_close_ts": t0, "fill_ts": (NOW_UTC + timedelta(seconds=s2f)).isoformat(),
                "order_ts": (NOW_UTC + timedelta(seconds=s2f - 2)).isoformat()}
    j = ZD.journal_block([d(120, 40, 0.3, 10), d(-60, -50, -0.2, 20), d(0, 0, 0, 30), d(None, None, None, 5, "open"),
                          {"status": "missed"}])
    assert (j["n"], j["open"], j["closed"], j["missed"], j["wins"], j["losses"]) == (5, 1, 3, 1, 1, 1)
    assert j["win_rate_pct"] == 50.0 and j["realized_pnl"] == 60.0
    assert j["avg_premium_return_pct"] == -3.3 and j["avg_stock_move_pct"] == 0.03
    assert j["median_signal_to_fill_sec"] == 15.0 and j["median_order_to_fill_sec"] == 2.0
    assert ZD.journal_block([])["win_rate_pct"] is None


# ── the tick: gates ───────────────────────────────────────────────────────────
def test_switch_off_or_live_broker_or_closed_market_gates_everything(zenv):
    fake, db = zenv(enabled=False)
    out = ZD.run()
    assert out["reason"] == "gated" and fake.orders == [] and not out["ran"]
    fake, db = zenv(mode="live")
    out = ZD.run()
    assert out["reason"] == "gated" and fake.orders == []
    assert any("paper-only" in e for e in out["errors"])
    fake, db = zenv(market_open=False)
    out = ZD.run()
    assert out["reason"] == "gated" and fake.orders == [] and _ledger(db, "zero_dte_disabled") == []
    # a LIVE options broker with the switch on says so once a day; a broker
    # without options helpers (the sim) never writes the row (disarmed-tick invariant)
    fake, db = zenv(mode="live")
    ZD.run(); ZD.run()
    assert len(_ledger(db, "zero_dte_disabled")) == 1
    fake, db = zenv()
    from tests.test_trading_engine import FakeBrokerModule

    class PlainBroker(FakeBrokerModule):          # the sim: no options helpers
        def mode(self):
            return "paper"
    out = ZD.run(broker=PlainBroker())
    assert out["reason"] == "gated" and out["gate"]["broker_has_options"] is False
    assert _ledger(db, "zero_dte_disabled") == []


def test_not_armed_is_a_dry_run_with_no_order(zenv):
    fake, db = zenv(armed=False)
    out = ZD.run()
    assert out["ran"] and out["dry_run"] == ["SPY"] and fake.orders == []
    assert db.zero_dte_lane_state.rows[0]["result"] == "dry_run"
    assert _pos(db) is None


# ── the tick: entries ─────────────────────────────────────────────────────────
def test_fresh_buy_tag_buys_the_tabs_call_at_the_ask_and_journals_the_latency(zenv):
    fake, db = zenv()
    out = ZD.run()
    assert out["ran"] and out["entered"] == ["SPY"] and out["errors"] == []
    assert fake.orders == [{"kind": "single", "symbol": OCC_C, "qty": 4, "side": "buy",
                            "limit_price": 1.25, "position_intent": "buy_to_open"}]
    pos = _pos(db)
    assert pos["status"] == "open" and pos["side"] == "call" and pos["qty"] == 4 and pos["budget"] == 500.0
    assert pos["signal"] == {"kind": "buy", "price": 648.2, "stop": 647.1, "target": 650.4, "i": 59}
    assert pos["signal_bar_close_ts"] == NOW_UTC.isoformat() and pos["seen_ts"] and pos["order_ts"]
    assert pos["fill_price"] is None and pos["order_id"] == "opt-1" and pos["expiry"] == EXP
    assert pos["regime"] == "AMPLIFYING" and pos["expected_move_pct"] == 0.9 and pos["contract"]["strike"] == 650.0
    st = db.zero_dte_lane_state.rows[0]
    assert st["result"] == "entered" and st["key"].startswith("SPY:%s:" % EE._et_day())
    led = _ledger(db, "zero_dte_entry")
    assert len(led) == 1 and led[0]["detail"]["occ"] == OCC_C and led[0]["detail"]["latency"]["signal_to_seen_sec"] is not None
    # the same tag on the next tick is one attempt, never a second order
    out2 = ZD.run()
    assert len(fake.orders) == 1 and out2["entered"] == []


def test_sell_tag_buys_the_put(zenv):
    fake, db = zenv(signal="sell")
    ZD.run()
    assert fake.orders[0]["symbol"] == OCC_P and fake.orders[0]["limit_price"] == 1.15
    assert _pos(db)["side"] == "put" and _pos(db)["qty"] == 4          # 500 // 115


def test_no_same_day_chain_pin_or_budget_are_journaled_skips(zenv):
    fake, db = zenv(row=None)
    out = ZD.run()
    assert fake.orders == [] and out["skipped"] == [{"symbol": "SPY", "reason": "no same-day chain"}]
    assert db.zero_dte_lane_state.rows[0]["result"] == "skipped"
    fake, db = zenv(row=dict(ROW, regime="PINNED"))
    assert ZD.run()["skipped"][0]["reason"] == "dealers PINNED — no 0DTE entry"
    fake, db = zenv(row=dict(ROW, call=dict(ROW["call"], ask=6.0)))
    assert "over the $500 budget" in ZD.run()["skipped"][0]["reason"] and fake.orders == []


def test_entry_window_and_daily_cap_and_open_cap(zenv):
    fake, db = zenv(now_et=datetime.combine(TODAY, dtime(9, 44), tzinfo=ET))
    assert ZD.run()["entry_reason"] == "outside 09:45–14:30 ET" and fake.orders == []
    fake, db = zenv(now_et=datetime.combine(TODAY, dtime(14, 30), tzinfo=ET))
    assert ZD.run()["entry_reason"] == "outside 09:45–14:30 ET" and fake.orders == []
    day = EE._et_day()
    att = [{"key": "%s:%s:k%d" % (s, day, i), "date": day, "symbol": s, "result": "entered"}
           for i, s in enumerate(("QQQ", "IWM", "NVDA"))]
    fake, db = zenv(attempts=att)
    assert ZD.run()["entry_reason"] == "daily cap 3 reached" and fake.orders == []
    opens = [{"pos_id": "%s-x" % s, "symbol": s, "status": "open", "side": "call", "occ": "X", "expiry": EXP,
              "qty": 1, "fill_price": 1.0, "signal": {}} for s in ("QQQ", "IWM", "NVDA")]
    fake, db = zenv(open_docs=opens, snaps={}, last={})
    assert ZD.run()["entry_reason"] == "3 open (max 3)" and fake.orders == []


def test_broker_rejection_is_blocked_not_retried(zenv):
    fake, db = zenv(reject="insufficient options buying power")
    out = ZD.run()
    assert out["blocked"] == [{"symbol": "SPY", "reason": "insufficient options buying power"}]
    assert db.zero_dte_lane_state.rows[0]["result"] == "blocked" and _pos(db) is None
    assert ZD.run()["blocked"] == [] and fake.orders == []


# ── the tick: manage ──────────────────────────────────────────────────────────
def _open_doc(fill=1.25, side="call", occ=OCC_C, order_id="opt-1", order_ts=None, fill_ts=None):
    return {"pos_id": "SPY-%s-1029" % EE._et_day(), "symbol": "SPY", "side": side, "occ": occ, "expiry": EXP,
            "qty": 4, "limit_price": 1.25, "order_id": order_id, "status": "open",
            "signal": {"kind": "buy" if side == "call" else "sell", "price": 648.2,
                       "stop": 647.1 if side == "call" else 649.3, "target": 650.4 if side == "call" else 646.0},
            "signal_bar_close_ts": NOW_UTC.isoformat(),
            "seen_ts": (NOW_UTC + timedelta(seconds=10)).isoformat(),
            "order_ts": order_ts or (NOW_UTC + timedelta(seconds=11)).isoformat(),
            "fill_price": fill, "fill_ts": fill_ts or ((NOW_UTC + timedelta(seconds=13)).isoformat() if fill else None),
            "fill_qty": 4 if fill else None, "day": EE._et_day()}


def test_stock_stop_closes_with_a_limit_at_the_bid(zenv):
    fake, db = zenv(open_docs=[_open_doc()], signal=None, last={"SPY": 647.0})
    out = ZD.run()
    assert out["closing"] == ["SPY"] and out["entered"] == []
    assert fake.orders == [{"kind": "single", "symbol": OCC_C, "qty": 4, "side": "sell",
                            "limit_price": 1.20, "position_intent": "sell_to_close"}]
    pos = _pos(db)
    assert pos["status"] == "closing" and "signal stop" in pos["close_reason"] and pos["close_order_id"] == "opt-1"
    assert _ledger(db, "zero_dte_close_sent")[0]["detail"]["price"] == 1.20


def test_close_fill_realizes_pnl_and_the_stock_move(zenv):
    doc = dict(_open_doc(), status="closing", close_order_id="x-9", close_price=1.20,
               close_reason="stock 647.0 hit the signal stop 647.1")
    closed = [{"id": "x-9", "status": "filled", "filled_avg_price": "1.30",
               "filled_at": (NOW_UTC + timedelta(minutes=5)).isoformat()}]
    fake, db = zenv(open_docs=[doc], signal=None, closed=closed, last={"SPY": 647.0})
    out = ZD.run()
    assert out["closed"] == ["SPY"]
    pos = _pos(db)
    assert pos["status"] == "closed" and pos["exit_price"] == 1.30 and pos["realized_pnl"] == 20.0
    assert pos["premium_return_pct"] == 4.0 and pos["stock_move_pct"] == round((647.0 / 648.2 - 1) * 100, 2)
    led = _ledger(db, "zero_dte_exit")[0]["detail"]
    assert led["realized_pnl"] == 20.0 and led["strategy"] == "zero_dte" and led["latency"]["signal_to_fill_sec"] == 13.0


def test_flatten_time_closes_a_winner_too(zenv):
    late = datetime.combine(TODAY, dtime(15, 46), tzinfo=ET)
    fake, db = zenv(open_docs=[_open_doc()], signal=None, now_et=late, last={"SPY": 649.0})
    out = ZD.run()
    assert out["closing"] == ["SPY"] and _pos(db)["close_reason"].startswith("flatten 15:45")
    assert out["entry_reason"] == "outside 09:45–14:30 ET"


def test_premium_take_and_stop_close_on_the_bid(zenv):
    fake, db = zenv(open_docs=[_open_doc()], signal=None, snaps={OCC_C: {"bid": 2.60, "ask": 2.70}}, last={"SPY": 648.9})
    assert ZD.run()["closing"] == ["SPY"] and _pos(db)["close_reason"].startswith("premium +108%")
    fake, db = zenv(open_docs=[_open_doc()], signal=None, snaps={OCC_C: {"bid": 0.60, "ask": 0.65}}, last={"SPY": 648.0})
    ZD.run()
    assert _pos(db)["close_reason"].startswith("premium -52%")
    # NEGATIVE: a healthy position with the stock between stop and target is held
    fake, db = zenv(open_docs=[_open_doc()], signal=None, last={"SPY": 648.9})
    out = ZD.run()
    assert out["held"] == ["SPY"] and fake.orders == [] and _pos(db)["status"] == "open"


def test_entry_fill_is_read_off_the_broker_and_a_stale_limit_is_cancelled(zenv):
    filled = [{"id": "opt-1", "status": "filled", "filled_avg_price": "1.24", "filled_qty": "4",
               "filled_at": (NOW_UTC + timedelta(seconds=14)).isoformat()}]
    fake, db = zenv(open_docs=[_open_doc(fill=None)], signal=None, closed=filled, last={"SPY": 648.9})
    out = ZD.run()
    pos = _pos(db)
    assert pos["fill_price"] == 1.24 and pos["fill_qty"] == 4 and pos["status"] == "open"
    assert _ledger(db, "zero_dte_filled")[0]["detail"]["latency"]["order_to_fill_sec"] == 3.0
    assert out["held"] == ["SPY"]
    # unfilled for longer than ENTRY_FILL_WAIT_SEC -> cancelled, journaled as missed
    old = (datetime.now(timezone.utc) - timedelta(seconds=ZD.ENTRY_FILL_WAIT_SEC + 5)).isoformat()
    fake, db = zenv(open_docs=[_open_doc(fill=None, order_ts=old)], signal=None, last={"SPY": 648.9})
    out = ZD.run()
    assert fake.cancelled == ["opt-1"] and out["missed"] == ["SPY"]
    assert _pos(db)["status"] == "missed" and "not filled in 180s" in _pos(db)["close_reason"]
    assert ZD.narrative(_pos(db)).startswith("Tried 4 ×")
    # NEGATIVE: a young unfilled limit is left working
    young = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    fake, db = zenv(open_docs=[_open_doc(fill=None, order_ts=young)], signal=None, last={"SPY": 648.9})
    out = ZD.run()
    assert fake.cancelled == [] and out["held"] == ["SPY"] and _pos(db)["status"] == "open"


def test_put_side_exits_mirror(zenv):
    fake, db = zenv(open_docs=[_open_doc(side="put", occ=OCC_P, fill=1.15)], signal=None, last={"SPY": 649.4})
    ZD.run()
    assert fake.orders[0]["symbol"] == OCC_P and fake.orders[0]["limit_price"] == 1.10
    assert "signal stop 649.3" in _pos(db)["close_reason"]


# ── read side ─────────────────────────────────────────────────────────────────
def test_status_and_tab_payload_shape(zenv):
    fake, db = zenv(open_docs=[_open_doc()], signal=None)
    s = ZD.status_block()
    assert s["enabled"] is True and s["paper"] is True and s["strategy"] == "zero_dte"
    assert s["max_per_day"] == 3 and s["max_open"] == 3 and s["entry_window"] == "09:45–14:30" and s["flatten_et"] == "15:45"
    assert len(s["rules"]) == 7 and s["settings"]["premium_stop_pct"] == 50.0
    assert s["open"][0]["symbol"] == "SPY" and s["open"][0]["narrative"].startswith("Bought 4 × SPY")
    assert s["open"][0]["latency"]["signal_to_fill_sec"] == 13.0
    p = ZD.tab_payload()
    assert p["armed"] is True and p["mode"] == "paper" and p["status"]["journal"]["open"] == 1 and p["recent"] == []


def test_close_now_requires_an_open_position_and_the_armed_switch(zenv):
    fake, db = zenv(open_docs=[_open_doc()], signal=None)
    r = ZD.close_now("spy", "owner close")
    assert r["ok"] and r["closing"] == ["SPY"] and fake.orders[0]["position_intent"] == "sell_to_close"
    with pytest.raises(ValueError):
        ZD.close_now("QQQ")
    fake, db = zenv(open_docs=[_open_doc()], signal=None, armed=False)
    with pytest.raises(ValueError):
        ZD.close_now("SPY")
