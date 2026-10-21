"""🚩 Gajjala lane v2 — GG's playbook rules, exactly (2026-10-21, BUILD_SPEC19 D1–D17).

Ajay 2026-10-21: "Is the 700 M floor by Gajjala?" / "Follow full Gajjala and he doesnt care exactly about this.. Go
through his rules from play book and implement them exactly"

Locks (every positive with its NEGATIVE): the market OTO entry at first sight / after a wait / never_triggered when the
stop prints first (VR 11.0 / 11.1 / 11.2); half size first and the add at breakeven with the combined stop at the
first fill (VR 11.3, S8 56:27); breakeven only on a CLOSED bar ≥ GG_BE_AFTER_BARS after the entry bar that closes
above the fill (NEG: 2 bars, a close at the fill, a LIVE bar — the mutation guard); the 9 EMA trail after breakeven
only on a closed bar's CLOSE (NEG: before breakeven, an intrabar low); the partial into strength after the add (2026-10-21,
BUILD_SPEC22 A2 — its own file tests/test_gajjala_lane_gg_words_2026_10_21.py; here the part-sell mechanics); GG's 0.25%
risk, halved after a loss, back after a win, the drawdown window budget and the half-off (VR 11.7); the 2-bar cooldown
(VR 10.6); the halt wait (VR 10.1, 2026-10-21 A3); the earnings / p.312 exemptions for
the lane ONLY (NEG: zone_edge / other strategies still blocked); the SEPA distribution step and the p.308 ratchet skip
lane names (NEG: a house name still exits / ratchets); floors default OFF; the served `rules` + an EMPTY `awaiting`; the F5
broker changes in BOTH brokers; the 🏁 grader's +1R untouched.

UNMEASURED — GG's rules as he gave them, on paper; no edge, no win rate. Hermetic: fake broker + fake Mongo, the bars
and halts seams patched, no network.
"""
import json
import os
import sys
import types
from datetime import date, datetime, time as dtime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.broker_alpaca as BA
import trading.broker_sim as BS
import trading.entries as EN
import trading.exit_engine as EE
import trading.gajjala_entry as GL
import trading.safety_floor as SF
from chart_maps.gajjala import constants as GC
from tests.test_gajjala_lane import GBroker, LaneColl, alert, seed, _at, _rows, _brackets, DAY, PLAN, SAIQ_ID
from tests.test_trading_engine import FakeDB, _position, _stop_order, env  # noqa: F401 — `env` is a fixture
from tests.test_broker_sim import FakeDB as SimDB

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
FILL_T = _at(DAY, 10, 53)                                       # the entry bar = 10:50–10:55 (label 10:55 ET)


# ── fakes ────────────────────────────────────────────────────────────────────────────────────────────────────────
class MBroker(GBroker):
    """GBroker + close_position(symbol, qty) (BUILD_SPEC19 F5) and a mutable stop book."""

    def close_position(self, symbol, qty=None):
        self.calls.append(("close_position", {"symbol": symbol, "qty": qty}))
        return {}

    def cancel_order(self, order_id):
        # 2026-10-21 (critic fix): a cancelled stop leaves the book at once (the sim's semantics); the pending-cancel
        # broker lives in tests/test_gajjala_lane_critic_2026_10_21.py
        self.calls.append(("cancel_order", {"order_id": order_id}))
        self._orders = [o for o in self._orders if o.get("id") != order_id]


@pytest.fixture
def gg(monkeypatch):
    def build(docs=(), positions=(), orders=(), closed=(), lasts=None, alerts=(), armed=True, equity=100_000.0,
              cash=None, cfg=None, now=None, frame=None, state=None, halts=None, earnings_days=None):
        db = FakeDB(armed=armed)
        db.gajjala_lane = LaneColl(docs)
        db.gajjala_lane_state = LaneColl([dict(state, _id="state")] if state else [])
        if cfg:
            db.trading_config.rows[0].update(cfg)
        brk = MBroker(positions, orders, closed, equity, cash, True, "paper")
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
        monkeypatch.setattr(SF, "market_cap", lambda sym: 2_000_000_000.0)
        monkeypatch.setattr(EN, "_live_price", lambda sym: (None, None))
        s = SimpleNamespace(db=db, brk=brk, lasts=dict(lasts or {}), alerts=list(alerts), now=now or _at(DAY, 11, 11),
                            frame=frame, halts=halts)
        monkeypatch.setattr(GL, "_alert_docs", lambda day: list(s.alerts))
        monkeypatch.setattr(GL, "_live_last", lambda b, sym: (s.lasts.get(sym), "test"))
        monkeypatch.setattr(GL, "_now_et", lambda: s.now)
        monkeypatch.setattr(GL, "_et_day", lambda: s.now.date().isoformat())
        monkeypatch.setattr(GL, "_bars5", lambda sym, day, now: s.frame)
        monkeypatch.setattr(GL, "_halts_of", lambda day, sym: s.halts)
        s.run = lambda at=None: GL.run(broker=brk, cfg=EE.get_config(), now=at or s.now)
        s.coll = db.gajjala_lane
        s.state = db.gajjala_lane_state
        return s
    return build


def frame(bars, live=None):
    """A 5-minute frame: bars = [(HH, MM close label ET, close, ema9)], the `low` column under the EMA on purpose
    (an intrabar dip is never a rule input). `live` = one more bar the clock has NOT settled yet."""
    rows = list(bars) + ([live] if live else [])
    idx = [pd.Timestamp(_at(DAY, hh, mm)).tz_convert("UTC").tz_localize(None) for hh, mm, _c, _e in rows]
    df = pd.DataFrame({"open": [c for _h, _m, c, _e in rows], "high": [c for _h, _m, c, _e in rows],
                       "low": [min(c, e or c) - 0.05 for _h, _m, c, e in rows], "close": [c for _h, _m, c, _e in rows],
                       "volume": [1000.0] * len(rows),
                       "ema9": [e for _h, _m, _c, e in rows], "ema21": [None] * len(rows)}, index=pd.DatetimeIndex(idx))
    return SimpleNamespace(df=df)


def v2_open(**kw):
    base = dict(state="open", order_id="o-1", qty=735, fill_qty=735, full_qty=1470, half_qty=735, fill_px=4.49,
                fill_et="10:53", fill_t=FILL_T.astimezone(UTC).isoformat(), entry=4.48, target=None, stop_px=4.31,
                be_state=None, partial_state=None, dd_half_state=None, version=2, floors="gg")
    base.update(kw)
    return seed(**base)


def stop_leg(px=4.31, qty=735, oid="stop-1"):
    return dict(_stop_order("SAIQ", px, qty, oid))


def calls(brk, name):
    return [kw for n, kw in brk.calls if n == name]


# ── D7 entry ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_market_entry_at_first_sight_when_last_is_at_or_over_the_trigger(gg):
    s = gg(alerts=[alert()], lasts={"SAIQ": 4.46}, now=_at(DAY, 10, 55))
    out = s.run()
    (br,) = _brackets(s.brk)
    assert out["ordered"] == 1 and br["limit_price"] is None and br["take_profit_price"] is None
    assert br["order_class"] == "oto" and br["stop_price"] == 4.31 and br["tif"] == "day"
    d = s.coll.get(SAIQ_ID)
    assert d["state"] == "ordered" and d["entry"] == 4.46 and d["target"] is None
    assert _rows(s.db, "gajjala_entry")[0]["detail"]["order_type"] == "market"


def test_waits_under_the_trigger_then_buys_market_when_it_trades(gg):
    s = gg(alerts=[alert()], lasts={"SAIQ": 4.45}, now=_at(DAY, 10, 55))
    assert s.run()["waiting"] == 1 and _brackets(s.brk) == []
    assert s.coll.get(SAIQ_ID)["state"] == "waiting"                    # NEG: under the trigger = no order, not dead
    s.lasts["SAIQ"] = 4.47
    out = s.run(at=_at(DAY, 11, 5))
    assert out["ordered"] == 1 and len(_brackets(s.brk)) == 1


def test_never_triggered_when_the_stop_prints_first(gg):
    s = gg(alerts=[alert()], lasts={"SAIQ": 4.40}, now=_at(DAY, 10, 55))
    s.run()
    s.lasts["SAIQ"] = 4.31
    s.run(at=_at(DAY, 10, 58))
    d = s.coll.get(SAIQ_ID)
    assert d["state"] == "unfilled" and d["skip_kind"] == "never_triggered" and _brackets(s.brk) == []
    assert GL.fate_text(d).startswith("not filled — last 4.31 is at or under the stop 4.31")
    s.lasts["SAIQ"] = 4.50
    s.run(at=_at(DAY, 11, 0))
    assert _brackets(s.brk) == []                                       # NEG: terminal — one doc per alert id


def test_entry_is_half_of_the_full_size():
    p = GL.entry_plan(PLAN, 4.48, 100_000, 100_000)
    assert (p["full_qty"], p["half_qty"], p["qty"], p["add_qty"]) == (1470, 735, 735, 735)
    one = GL.entry_plan(PLAN, 4.48, 100_000, 4.48 * 1.5)                # cash for one share
    assert (one["full_qty"], one["qty"], one["add_qty"]) == (1, 1, 0)   # min 1, nothing left to add


# ── D8a breakeven + add ──────────────────────────────────────────────────────────────────────────────────────────
BELOW = [(10, 55, 4.47, 4.40), (11, 0, 4.48, 4.42), (11, 5, 4.47, 4.43)]          # entry bar + 2 bars at / under the fill


def test_breakeven_on_the_third_closed_bar_moves_the_stop_and_adds_the_second_half(gg):
    f = frame(BELOW + [(11, 10, 4.60, 4.45)])
    s = gg(docs=[v2_open()], positions=[_position("SAIQ", 735, 4.49, 4.60)], orders=[stop_leg()], frame=f)
    out = s.run()
    assert out["breakeven"] == 1 and out["added"] == 1
    assert calls(s.brk, "replace_order") == [{"order_id": "stop-1", "stop_price": 4.49, "limit_price": None}]
    (add,) = _brackets(s.brk)
    assert add["qty"] == 735 and add["stop_price"] == 4.49 and add["take_profit_price"] is None   # combined stop = fill
    assert add["order_class"] == "oto" and add["limit_price"] is None
    assert add["client_order_id"] == "test-SAIQ-gg-add-bull_flag"
    d = s.coll.get(SAIQ_ID)
    assert d["be_state"] == "done" and d["stop_px"] == 4.49 and d["add_qty"] == 735 and d["add_order_id"]
    assert d["be_bar_t"] == _at(DAY, 11, 10).astimezone(UTC).isoformat()
    assert d["fill_qty"] + d["add_qty"] == d["full_qty"]                # never past full_qty
    assert len(_rows(s.db, "gajjala_breakeven")) == 1 and len(_rows(s.db, "gajjala_add")) == 1
    s.run(at=_at(DAY, 11, 12))
    assert len(_brackets(s.brk)) == 1                                   # once


def test_breakeven_NEG_two_bars_only(gg):
    f = frame([(10, 55, 4.47, 4.40), (11, 0, 4.60, 4.42), (11, 5, 4.62, 4.43)])   # 2 bars after the entry bar
    s = gg(docs=[v2_open()], positions=[_position("SAIQ", 735, 4.49, 4.62)], orders=[stop_leg()], frame=f,
           now=_at(DAY, 11, 6))
    out = s.run()
    assert out["breakeven"] == 0 and calls(s.brk, "replace_order") == [] and _brackets(s.brk) == []


def test_breakeven_NEG_a_close_at_the_fill(gg):
    f = frame(BELOW + [(11, 10, 4.49, 4.45)])
    s = gg(docs=[v2_open()], positions=[_position("SAIQ", 735, 4.49, 4.49)], orders=[stop_leg()], frame=f)
    assert s.run()["breakeven"] == 0 and calls(s.brk, "replace_order") == []


def test_breakeven_NEG_the_live_bar_never_counts(gg):
    """THE LIVE-BAR GUARD (memory cheetah_live_bar_overlay): the 11:10 bar is still printing at 11:10:10 (it counts
    BAR_SETTLE_SEC after its label) — a lane that read it would move the stop. Mutation-proved: drop
    `GB.closed_only` in closed_rows and this test fails."""
    f = frame(BELOW, live=(11, 10, 4.70, 4.45))
    s = gg(docs=[v2_open()], positions=[_position("SAIQ", 735, 4.49, 4.70)], orders=[stop_leg()], frame=f,
           now=_at(DAY, 11, 10) + timedelta(seconds=10))
    out = s.run()
    assert out["breakeven"] == 0 and calls(s.brk, "replace_order") == [] and _brackets(s.brk) == []
    assert s.coll.get(SAIQ_ID)["be_state"] is None
    out = s.run(at=_at(DAY, 11, 10) + timedelta(seconds=GC.BAR_SETTLE_SEC))     # settled → now it counts
    assert out["breakeven"] == 1


def test_breakeven_failed_replace_keeps_the_hard_stop_and_never_adds(gg, monkeypatch):
    f = frame(BELOW + [(11, 10, 4.60, 4.45)])
    s = gg(docs=[v2_open()], positions=[_position("SAIQ", 735, 4.49, 4.60)], orders=[stop_leg()], frame=f)

    def boom(order_id, stop_price=None, limit_price=None):
        s.brk.calls.append(("replace_order", {"order_id": order_id}))
        raise EE.BrokerError("HTTP 422 replace refused")
    monkeypatch.setattr(s.brk, "replace_order", boom, raising=False)
    out = s.run()
    d = s.coll.get(SAIQ_ID)
    assert d["be_state"] is None and d["be_failed_n"] == 1 and d["stop_px"] == 4.31
    assert _brackets(s.brk) == [] and calls(s.brk, "cancel_order") == []       # no add, the stop never cancelled
    assert any("breakeven SAIQ" in e for e in out["errors"]) and len(_rows(s.db, "gajjala_be_failed")) == 1
    monkeypatch.setattr(s.brk, "replace_order", lambda order_id, stop_price=None, limit_price=None:
                        {"id": "stop-2"}, raising=False)
    out = s.run(at=_at(DAY, 11, 12))                                     # retried next tick
    assert out["breakeven"] == 1 and s.coll.get(SAIQ_ID)["stop_order_ids"] == ["stop-2"]   # Alpaca's NEW id kept


def test_the_add_never_averages_down(gg):
    """The bar closed above the fill but the tape is back under it now: the stop still moves, the add is refused
    by entries' never-average-down (NEG: no buy under the average)."""
    f = frame(BELOW + [(11, 10, 4.60, 4.45)])
    s = gg(docs=[v2_open()], positions=[_position("SAIQ", 735, 4.49, 4.40)], orders=[stop_leg()], frame=f)
    out = s.run()
    d = s.coll.get(SAIQ_ID)
    assert out["breakeven"] == 1 and out["added"] == 0 and _brackets(s.brk) == []
    assert "never average down" in d["add_refused"] or "stop < the entry price" in d["add_refused"]


def test_lane_off_moves_the_stop_but_never_adds(gg):
    f = frame(BELOW + [(11, 10, 4.60, 4.45)])
    s = gg(docs=[v2_open()], positions=[_position("SAIQ", 735, 4.49, 4.60)], orders=[stop_leg()], frame=f,
           cfg={"gajjala_entry": False})
    out = s.run()
    assert out["manage_only"] and out["breakeven"] == 1 and _brackets(s.brk) == []
    assert s.coll.get(SAIQ_ID)["add_refused"] == "lane switched off — no new buys"


# ── D8c the 9 EMA trail ──────────────────────────────────────────────────────────────────────────────────────────
def _after_be(**kw):
    return v2_open(be_state="done", be_bar_t=_at(DAY, 11, 10).astimezone(UTC).isoformat(), be_et="11:11",
                   stop_px=4.49, add_qty=735, add_order_id="brk-9", add_fill_qty=735, add_fill_px=4.60, **kw)


def _be_orders():
    return [stop_leg(4.49, 735, "stop-1"), stop_leg(4.49, 735, "stop-2")]


def test_trail_exit_on_a_closed_bar_under_the_9_ema_after_breakeven(gg):
    f = frame(BELOW + [(11, 10, 4.60, 4.45), (11, 15, 4.55, 4.58)])
    s = gg(docs=[_after_be()], positions=[_position("SAIQ", 1470, 4.545, 4.55)], orders=_be_orders(), frame=f,
           now=_at(DAY, 11, 16))
    out = s.run()
    d = s.coll.get(SAIQ_ID)
    assert out["trailed"] == 1 and d["state"] == "closing" and d["exit_kind"] == "trail"
    assert "under the 9 EMA" in d["why"]
    assert calls(s.brk, "close_position") == [{"symbol": "SAIQ", "qty": None}]          # the whole remainder
    assert sorted(c["order_id"] for c in calls(s.brk, "cancel_order")) == ["stop-1", "stop-2"]   # house flatten


def test_trail_NEG_an_intrabar_low_under_the_ema_never_exits(gg):
    f = frame(BELOW + [(11, 10, 4.60, 4.45), (11, 15, 4.62, 4.58)])     # the low column dips under 4.58
    assert f.df["low"].iloc[-1] < 4.58
    s = gg(docs=[_after_be()], positions=[_position("SAIQ", 1470, 4.545, 4.62)], orders=_be_orders(), frame=f,
           now=_at(DAY, 11, 16))
    out = s.run()
    assert out["trailed"] == 0 and s.coll.get(SAIQ_ID)["state"] == "open" and calls(s.brk, "close_position") == []


def test_trail_NEG_before_breakeven_the_hard_stop_stands(gg):
    f = frame([(10, 55, 4.47, 4.48), (11, 0, 4.40, 4.46), (11, 5, 4.41, 4.45), (11, 10, 4.42, 4.44)])
    s = gg(docs=[v2_open()], positions=[_position("SAIQ", 735, 4.49, 4.42)], orders=[stop_leg()], frame=f)
    out = s.run()
    assert out["trailed"] == 0 and out["breakeven"] == 0 and calls(s.brk, "close_position") == []
    assert s.coll.get(SAIQ_ID)["state"] == "open"


def test_trail_NEG_the_breakeven_bar_itself_is_not_a_trail_bar(gg):
    f = frame(BELOW + [(11, 10, 4.60, 4.65)])                            # the BE bar closed under its EMA
    s = gg(docs=[_after_be()], positions=[_position("SAIQ", 1470, 4.545, 4.60)], orders=_be_orders(), frame=f)
    assert s.run()["trailed"] == 0


def test_trail_uses_a_real_bars_frame_and_its_9_ema():
    """The lane reads the pass's own Frame shape (bars.build_frame: ema9 = _masked_ema over closed bars)."""
    from chart_maps.gajjala import bars as GB
    closes = [4.40 + 0.02 * i for i in range(12)] + [4.50]
    idx = [pd.Timestamp(_at(DAY, 10, 0) + timedelta(minutes=5 * (i + 1))).tz_convert("UTC").tz_localize(None)
           for i in range(len(closes))]
    df = pd.DataFrame({"open": closes, "high": closes, "low": closes, "close": closes, "volume": [1.0] * len(closes)},
                      index=pd.DatetimeIndex(idx))
    fr = GB.build_frame(df, DAY, GB.RULES["5m"])
    rows = GL.closed_rows(fr, _at(DAY, 11, 10))
    assert rows[-1]["ema9"] == fr.ema9[-1] and rows[-1]["close"] == 4.50 and rows[-1]["close"] < rows[-1]["ema9"]
    assert GL.trail_bar(rows, rows[-2]["t"], "ema9") is rows[-1]
    assert GL.trail_bar(rows, rows[-1]["t"], "ema9") is None             # NEG: nothing after the last bar
    assert rows[0]["ema9"] is None                                       # warm-up is a gap, never a guess


def test_trail_ema_kiss_fly_is_the_21(monkeypatch):
    # 2026-10-21 (BUILD_SPEC22 A1, Ajay "keep what ever Gajjala says for these"): GG VR 11.4 "the 21 on Kiss & Fly"
    assert GL.trail_ema_period("kiss_fly") == 21 and GL.trail_ema_period("bull_flag") == 9   # NEG: other setups
    monkeypatch.setattr(GL, "GG_TRAIL_EMA_KF", None)
    assert GL.trail_ema_period("kiss_fly") == 9                                          # None would fall back to 9


# ── D8b partial — 2026-10-21 (BUILD_SPEC22 A2): after the add, the first closed bar closing over the move's high ─────
def test_partial_NEG_no_add_fill_no_partial(gg):
    """The placeholder GG_PARTIAL_R is gone (2026-10-21); the peel needs the add's FILL (GG_PARTIAL_AFTER "add")."""
    assert not hasattr(GL, "GG_PARTIAL_R")
    f = frame(BELOW + [(11, 10, 4.60, 4.45), (11, 15, 5.40, 4.70)])     # far into strength
    doc = _after_be()
    doc.update(add_fill_qty=None, add_fill_px=None, add_order_id=None)
    s = gg(docs=[doc], positions=[_position("SAIQ", 735, 4.49, 5.40)], orders=[stop_leg(4.49, 735)], frame=f,
           now=_at(DAY, 11, 16))
    out = s.run()
    assert out["partials"] == 0 and calls(s.brk, "close_position") == [] and calls(s.brk, "cancel_order") == []


def test_partial_into_strength_cancel_sell_restop(gg, monkeypatch):
    f = frame(BELOW + [(11, 10, 4.60, 4.45), (11, 15, 4.80, 4.62)])     # 4.80 > the move's high 4.60
    s = gg(docs=[_after_be()], positions=[_position("SAIQ", 1470, 4.545, 4.80)], orders=_be_orders(), frame=f,
           now=_at(DAY, 11, 16))
    out = s.run()
    # 2026-10-21 (critic fix): two ticks — the cancel first (Alpaca cancels asynchronously), the sell the next tick
    assert out["partials"] == 0 and calls(s.brk, "close_position") == [] and calls(s.brk, "submit_stop") == []
    assert sorted(c["order_id"] for c in calls(s.brk, "cancel_order")) == ["stop-1", "stop-2"]
    assert s.coll.get(SAIQ_ID)["partial_state"] == "cancelling"
    out = s.run(at=_at(DAY, 11, 17))
    assert out["partials"] == 1
    assert calls(s.brk, "close_position") == [{"symbol": "SAIQ", "qty": 735}]
    assert calls(s.brk, "submit_stop") == [{"symbol": "SAIQ", "qty": 735, "stop_price": 4.49}]
    d = s.coll.get(SAIQ_ID)
    assert d["partial_state"] == "done" and d["partial_qty"] == 735 and d["partial_naked_ms"] == 60_000   # one tick
    assert "rules" in GL.status_block(EE.get_config()) and "the first closed bar closing at a new high of the move " \
        "peels half" in GL.rules_block()["manage_text"]
    s.run(at=_at(DAY, 11, 18))
    assert len(calls(s.brk, "close_position")) == 1                     # once


def test_partial_NEG_a_close_at_the_moves_high(gg, monkeypatch):
    f = frame(BELOW + [(11, 10, 4.60, 4.45), (11, 15, 4.60, 4.55)])     # equal to the high = not strength
    s = gg(docs=[_after_be()], positions=[_position("SAIQ", 1470, 4.545, 4.60)], orders=_be_orders(), frame=f,
           now=_at(DAY, 11, 16))
    assert s.run()["partials"] == 0 and calls(s.brk, "close_position") == [] and calls(s.brk, "cancel_order") == []


def test_partial_sell_refused_restores_the_stop(gg, monkeypatch):
    f = frame(BELOW + [(11, 10, 4.60, 4.45), (11, 15, 4.80, 4.62)])
    s = gg(docs=[_after_be()], positions=[_position("SAIQ", 1470, 4.545, 4.80)], orders=_be_orders(), frame=f,
           now=_at(DAY, 11, 16))

    def refuse(symbol, qty=None):
        raise EE.BrokerError("HTTP 403 insufficient qty available")
    monkeypatch.setattr(s.brk, "close_position", refuse, raising=False)
    s.run()                                                             # 2026-10-21: tick N cancels only
    out = s.run(at=_at(DAY, 11, 17))                                    # tick N+1 sells — refused
    assert calls(s.brk, "submit_stop") == [{"symbol": "SAIQ", "qty": 1470, "stop_price": 4.49}]   # never naked
    d = s.coll.get(SAIQ_ID)
    assert d["partial_state"] is None and "insufficient qty" in d["partial_error"]
    assert any(e.startswith("partial SAIQ") for e in out["errors"])


# ── D4 / D5 risk ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_risk_halves_after_a_loss_and_resets_on_a_win():
    assert GL.GAJJALA_RISK_PCT == 0.25 and GL.GG_LOSS_RISK_CUT == 0.5
    assert GL.risk_after(1.0, -10) == 0.5 and GL.risk_after(0.5, -1) == 0.25
    assert GL.risk_after(0.25, 5) == 1.0
    assert GL.risk_after(0.5, 0) == 0.5 and GL.risk_after(0.5, None) == 0.5           # NEG: flat / unknown
    half = GL.entry_plan(PLAN, 4.48, 100_000, 100_000, risk_mult=0.5)
    assert half["risk_pct"] == 0.125 and half["full_qty"] == int(125 / 0.17) == 735 and half["qty"] == 367
    assert GL.entry_plan(PLAN, 4.48, 100_000, 100_000, risk_mult=1e-6)["skip_kind"] == "size"   # < 1 share


def test_a_losing_v2_trade_halves_risk_mult_and_a_win_resets(gg):
    stop_fill = {"id": "stop-1", "symbol": "SAIQ", "side": "sell", "type": "stop", "status": "filled",
                 "filled_qty": "735", "filled_avg_price": "4.31", "filled_at": _at(DAY, 11, 2).astimezone(UTC).isoformat()}
    s = gg(docs=[v2_open()], positions=[], closed=[stop_fill], now=_at(DAY, 11, 3))
    s.run()
    d = s.coll.get(SAIQ_ID)
    assert d["state"] == "closed" and d["exit_kind"] == "stop" and d["pnl_usd"] == round(-0.18 * 735, 2)
    assert d["r_mult"] == -1.2
    assert s.state.get("state")["risk_mult"] == 0.5
    assert "now 0.125%" in GL.status_block(EE.get_config())["rules"]["risk_text"]
    win = dict(stop_fill, id="mkt-1", type="market", filled_avg_price="4.80")
    s2 = gg(docs=[v2_open(exit_kind="trail", state="closing")], positions=[], closed=[win], now=_at(DAY, 12, 0),
            state={"risk_mult": 0.25})
    s2.run()
    assert s2.coll.get(SAIQ_ID)["exit_kind"] == "trail" and s2.state.get("state")["risk_mult"] == 1.0


def test_scaled_trade_pnl_counts_the_add_and_every_sell():
    pnl, px = GL.trade_pnl([(735, 4.80), (1470, 4.55)], [(735, 4.49), (735, 4.60)])
    assert pnl == round(735 * 4.80 + 735 * 4.55 - 1470 * 4.545, 2) and px == round((4.80 + 4.55) / 2, 4)
    assert GL.trade_r(pnl, 735, 4.46, 4.31) == round(pnl / (735 * 0.15), 2)
    assert GL.trade_pnl([], [(735, 4.49)]) == (None, None)                                 # NEG: nothing sold


def test_drawdown_step_window_and_budget():
    f, on = GL.drawdown_step({}, 100_000.0, "t0")
    assert f["equity_peak"] == 100_000.0 and not f["in_drawdown"] and not on and "dd_window" not in f
    st = {"equity_peak": 100_000.0, "in_drawdown": False}
    f, on = GL.drawdown_step(st, 90_001.0, "t1")
    assert not f["in_drawdown"] and not on                               # NEG: under 10% down
    f, on = GL.drawdown_step(st, 90_000.0, "t2")
    assert f["in_drawdown"] and on and f["dd_window"] == {"opened_at": "t2", "trades": 0, "risk_used_pct": 0.0}
    st.update(f)
    f2, on2 = GL.drawdown_step(st, 89_000.0, "t3")
    assert f2["in_drawdown"] and not on2                                 # NEG: already in drawdown — no second turn
    assert GL.budget_left_pct(st) == 5.0 and GL.budget_left_pct({}) is None
    for i in range(GL.GG_DRAWDOWN_TRADES - 1):
        st.update(GL.window_after_trade(st, 0.25))
    assert st["dd_window"]["trades"] == 4 and GL.budget_left_pct(st) == 4.0
    st.update(GL.window_after_trade(st, 0.25))
    assert st["dd_window"] is None and st["dd_last_window"]["trades"] == 5        # the five trades are spent
    tight = GL.entry_plan(PLAN, 4.48, 90_000, 90_000, budget_left_pct=0.1)
    assert tight["full_qty"] == int(90 / 0.17) == 529 and tight["qty"] == 264      # the budget binds
    assert GL.entry_plan(PLAN, 4.48, 90_000, 90_000, budget_left_pct=0.0)["skip_kind"] == "size"


def test_drawdown_turning_on_takes_half_off_every_open_lane_position(gg):
    s = gg(docs=[v2_open()], positions=[_position("SAIQ", 735, 4.49, 4.50)], orders=[stop_leg()], equity=89_000.0,
           state={"equity_peak": 100_000.0, "in_drawdown": False, "risk_mult": 1.0}, frame=None)
    out = s.run()
    # 2026-10-21 (critic fix): tick N cancels the stop, tick N+1 sells half and re-stops the rest
    assert out["drawdown"] is True and out["half_off"] == 0 and calls(s.brk, "close_position") == []
    assert calls(s.brk, "cancel_order") == [{"order_id": "stop-1"}]
    out = s.run(at=_at(DAY, 11, 12))
    assert out["half_off"] == 1
    assert calls(s.brk, "close_position") == [{"symbol": "SAIQ", "qty": 367}]
    assert calls(s.brk, "submit_stop") == [{"symbol": "SAIQ", "qty": 368, "stop_price": 4.31}]
    d = s.coll.get(SAIQ_ID)
    assert d["dd_half_state"] == "done" and d["dd_half_qty"] == 367 and d["dd_half_naked_ms"] == 60_000
    assert "drawdown mode on: 0 of 5 trades, budget left 5%" in GL.status_block(EE.get_config())["rules"]["risk_text"]
    s.run(at=_at(DAY, 11, 13))
    assert len(calls(s.brk, "close_position")) == 1                     # once
    s2 = gg(docs=[v2_open()], positions=[_position("SAIQ", 735, 4.49, 4.50)], orders=[stop_leg()], equity=89_000.0,
            state={"equity_peak": 100_000.0, "in_drawdown": True, "risk_mult": 1.0})
    assert s2.run()["half_off"] == 0 and calls(s2.brk, "close_position") == []      # NEG: no turn, no half-off


def test_a_drawdown_entry_counts_in_the_window(gg):
    s = gg(alerts=[alert()], lasts={"SAIQ": 4.48}, equity=89_000.0, now=_at(DAY, 10, 55),
           state={"equity_peak": 100_000.0, "in_drawdown": True, "risk_mult": 1.0,
                  "dd_window": {"opened_at": "x", "trades": 1, "risk_used_pct": 0.25}})
    s.run()
    w = s.state.get("state")["dd_window"]
    assert w["trades"] == 2 and w["risk_used_pct"] > 0.25


# ── D10 cooldown / D11 halts ─────────────────────────────────────────────────────────────────────────────────────
def _stopped(exit_hm=(11, 2)):
    return seed(state="closed", exit_kind="stop", exit_t=_at(DAY, *exit_hm).astimezone(UTC).isoformat(),
                exit_et="%02d:%02d" % exit_hm, fill_px=4.49, pnl_usd=-132.3)


def test_cooldown_two_bars_after_a_stop_out(gg):
    kf = alert(setup="kiss_fly", hm=(11, 11))
    s = gg(docs=[_stopped()], alerts=[kf], lasts={"SAIQ": 4.48}, now=_at(DAY, 11, 12))
    s.run()
    d = s.coll.get(f"GG:{DAY}|SAIQ|kiss_fly")
    assert d["skip_kind"] == "cooldown" and _brackets(s.brk) == []
    assert d["why"] == "stopped out on SAIQ at 11:02 ET — GG waits 2 bars before a re-entry (until 11:15 ET)"
    assert GL.cooldown_until(_at(DAY, 11, 2), 5) == _at(DAY, 11, 15).astimezone(UTC)


def test_cooldown_NEG_three_bars_later_a_new_alert_trades(gg):
    kf = alert(setup="kiss_fly", hm=(11, 16))
    s = gg(docs=[_stopped()], alerts=[kf], lasts={"SAIQ": 4.48}, now=_at(DAY, 11, 17))
    s.run()
    assert s.coll.get(f"GG:{DAY}|SAIQ|kiss_fly")["state"] == "ordered" and len(_brackets(s.brk)) == 1
    s = gg(docs=[_stopped(), ], alerts=[alert(setup="kiss_fly", hm=(11, 11))], lasts={"SAIQ": 4.48},
           now=_at(DAY, 11, 12))
    s.coll.rows[0]["exit_kind"] = "trail"                               # NEG: a trail exit is not a stop-out
    s.run()
    assert s.coll.get(f"GG:{DAY}|SAIQ|kiss_fly")["state"] == "ordered"


def test_halt_wait_one_clean_closed_bar_after_the_resume(gg, monkeypatch):
    """2026-10-21 (BUILD_SPEC22 A3): GG_HALT_CALM_MIN is gone; a resume at 10:50 sits in the 10:50–10:55 bar, so the
    first clean bar is 10:55–11:00 — the lane WAITS (never a terminal skip) until it has closed."""
    assert not hasattr(GL, "GG_HALT_CALM_MIN") and GL.GG_HALT_CALM_BARS == 1
    h = {"n": 2, "text": "⏸ halted ×2 (LUDP)", "last_resume_et": _at(DAY, 10, 50).isoformat()}
    s = gg(alerts=[alert()], lasts={"SAIQ": 4.48}, halts=h, now=_at(DAY, 10, 55))
    out = s.run()
    d = s.coll.get(SAIQ_ID)
    assert d["state"] == "waiting" and d["wait_reason"] == "halt_calm" and d["skip_kind"] is None
    assert out["halt_waiting"] == 1 and _brackets(s.brk) == []
    assert GL.fate_text(d).startswith("halted, resumed 10:50 ET — waiting for one clean closed bar (closes 11:00 ET)")
    out = s.run(at=_at(DAY, 11, 0) + timedelta(seconds=GC.BAR_SETTLE_SEC))
    d = s.coll.get(SAIQ_ID)
    assert d["state"] == "ordered" and d["halts"]["n"] == 2 and len(_brackets(s.brk)) == 1   # calm again
    assert GL.fate_text(d).endswith(" · ⏸ halted ×2 (LUDP) today")


# ── D2 / D3 exemptions — strategy-gated (entries) ────────────────────────────────────────────────────────────────
OTO = dict(limit_price=None, stop_price=4.31, strategy="gajjala", order_class="oto",
           sizing={"qty": 735, "basis": "gg_risk_pct", "price": 4.48})


def test_p312_ceiling_waived_for_gajjala_only(env):
    fake, db = env(positions=[_position("P%d" % i, 1, 10.0, 10.0) for i in range(5)])
    from trading.risk_rules import MAX_POSITIONS
    assert len(fake.positions()) == MAX_POSITIONS
    blocked, ctx = EN._evaluate("SAIQ", ceiling="gg", allow_earnings=True, **OTO)
    assert blocked == [] and any("GG has no position ceiling" in w for w in ctx["warnings"])
    blocked, _ = EN._evaluate("SAIQ", **OTO)                              # NEG: the default ceiling still blocks
    assert any("portfolio full: 5/5 positions (p.312)" in b for b in blocked)
    for strat in ("demand_zone", "breakout", "minervini", "catalyst", "manual"):
        blocked, _ = EN._evaluate("SAIQ", ceiling="gg", **dict(OTO, strategy=strat))
        assert any("ceiling='gg' is the 🚩 Gajjala lane's rule only" in b for b in blocked), strat
    blocked, _ = EN._evaluate("SAIQ", ceiling="none", **OTO)
    assert any("ceiling must be one of house, gg" in b for b in blocked)


def test_earnings_shield_waived_by_the_lane_only(env):
    _fake, _db = env(earnings_days=2)
    blocked, _ = EN._evaluate("SAIQ", allow_earnings=True, **OTO)
    assert not any("earnings in" in b for b in blocked)
    blocked, _ = EN._evaluate("AAA", limit_price=50.0, strategy="breakout")   # NEG: a zone-edge breakout entry
    assert any("earnings in 2d" in b for b in blocked)
    with open(os.path.join(os.path.dirname(__file__), "..", "trading", "zone_edge_entry.py"), encoding="utf-8") as fh:
        assert "stop_price=stop_price, allow_earnings=False)" in fh.read()   # zone_edge never waives it
    with open(os.path.join(os.path.dirname(__file__), "..", "trading", "gajjala_entry.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert src.count("allow_earnings=True") == src.count('ceiling="gg"') == src.count('order_class="oto"') == 2
    # (the entry and the add — both through entries.enter, both strategy="gajjala")


def test_oto_lane_plan_shape(env):
    fake, db = env()
    blocked, ctx = EN._evaluate("SAIQ", **OTO)
    assert blocked == [] and ctx["target"] is None and ctx["price"] == 4.48 and ctx["price_source"] == "lane"
    assert ctx["stop_plan"].stop_price == 4.31
    blocked, _ = EN._evaluate("SAIQ", target_price=4.66, **OTO)
    assert any("an OTO lane plan carries no target_price" in b for b in blocked)
    blocked, _ = EN._evaluate("SAIQ", **dict(OTO, stop_price=4.50))
    assert any("needs 0 < stop < the entry price" in b for b in blocked)
    blocked, _ = EN._evaluate("AAA", order_class="oto", strategy="gajjala")     # NEG: no lane plan
    assert any("order_class='oto' is only accepted with a lane sizing plan" in b for b in blocked)
    blocked, _ = EN._evaluate("SAIQ", **dict(OTO, order_class="trailing"))
    assert any("order_class must be one of bracket, oto" in b for b in blocked)
    res = EN.enter("SAIQ", tif="day", order_intent="gg-bull_flag", **OTO)
    (br,) = [kw for n, kw in fake.calls if n == "submit_bracket"]
    assert br["take_profit_price"] is None and br["limit_price"] is None and res["target"] is None
    det = [r for r in db.trade_ledger.rows if r["kind"] == "entry"][0]["detail"]
    assert det["order_class"] == "oto" and det["target_price"] is None and det["overrides"]["target"] == "none"


# ── D9 house exit-engine exemptions (exit_engine) ───────────────────────────────────────────────────────────────
DIST = {"sell_signals": {"signals": {"close_below_200ma": True}}}


def _engine(env, monkeypatch, positions, orders, lane_docs):
    fake, db = env(positions=positions, orders=orders)
    db.gajjala_lane = LaneColl(lane_docs)
    monkeypatch.setattr(GL, "run", lambda **kw: {"stubbed": True})
    return fake, db


def test_distribution_exit_skips_lane_names_house_names_still_exit(env, monkeypatch):
    fake, db = _engine(env, monkeypatch,
                       [_position("AAA", 100, 10.0, 10.5), _position("BBB", 100, 10.0, 10.5)],
                       [_stop_order("AAA", 9.0, 100, "s-a"), _stop_order("BBB", 9.0, 100, "s-b")],
                       [seed(_id="GG:x|AAA|bull_flag", symbol="AAA", state="open")])
    monkeypatch.setattr(EE, "_distribution_read", lambda sym: DIST)
    summary = EE.tick()
    closes = [kw["symbol"] for n, kw in fake.calls if n == "close_position"]
    assert closes == ["BBB"] and summary["distribution_exits"] == 1        # NEG: the house name still exits


def test_p308_ratchet_skips_lane_names_house_names_still_ratchet(env, monkeypatch):
    fake, db = _engine(env, monkeypatch,
                       [_position("AAA", 100, 10.0, 14.0), _position("BBB", 100, 10.0, 14.0)],
                       [_stop_order("AAA", 9.0, 100, "s-a"), _stop_order("BBB", 9.0, 100, "s-b")],
                       [seed(_id="GG:x|AAA|bull_flag", symbol="AAA", state="closing")])
    summary = EE.tick()
    replaced = [kw["order_id"] for n, kw in fake.calls if n == "replace_order"]
    assert replaced == ["s-b"] and summary["ratcheted"] == 1 and summary["gajjala_exempt"] == 1


def test_lane_exemption_needs_a_live_lane_doc(env, monkeypatch):
    """NEG: a CLOSED / skipped lane doc on the name exempts nothing (the house rules are back)."""
    fake, db = _engine(env, monkeypatch, [_position("AAA", 100, 10.0, 10.5)], [_stop_order("AAA", 9.0, 100, "s-a")],
                       [seed(_id="GG:x|AAA|bull_flag", symbol="AAA", state="closed"),
                        seed(_id="GG:y|AAA|kiss_fly", symbol="AAA", state="skipped")])
    monkeypatch.setattr(EE, "_distribution_read", lambda sym: DIST)
    EE.tick()
    assert [kw["symbol"] for n, kw in fake.calls if n == "close_position"] == ["AAA"]
    assert EE.GAJJALA_LANE_LIVE_STATES == ("ordered", "open", "closing")


def test_watchdog_still_protects_lane_names(env, monkeypatch):
    """D9: the watchdog is NOT exempt — a lane name at its stop with no working broker stop is sold."""
    fake, db = _engine(env, monkeypatch, [_position("AAA", 100, 10.0, 8.5)], [],
                       [seed(_id="GG:x|AAA|bull_flag", symbol="AAA", state="open")])
    db.trade_ledger.rows.append({"kind": "entry", "symbol": "AAA", "epoch": 1, "detail": {"stop_price": 9.0}})
    summary = EE.tick()
    assert summary["watchdog_exits"] == 1


def test_lane_stop_armed_only(env):
    fake, db = env()
    o = EE.lane_stop("saiq", 368, 4.31, "test")
    assert fake.calls[-1] == ("submit_stop", {"symbol": "SAIQ", "qty": 368, "stop_price": 4.31})
    assert [r for r in db.trade_ledger.rows if r["kind"] == "lane_stop"][0]["detail"]["order_id"] == o["id"]
    fake, db = env(armed=False)
    with pytest.raises(ValueError, match="engine not armed"):
        EE.lane_stop("SAIQ", 1, 4.31)
    assert fake.calls == []                                               # NEG: disarmed places nothing


# ── D1 floors default + served words ─────────────────────────────────────────────────────────────────────────────
def test_floors_default_off(gg):
    gg()
    assert EE.get_config()["gajjala_floors"] is False and GL._floors_of(EE.get_config()) == "gg"
    assert GL._floors_of({"gajjala_floors": True}) == "house"           # NEG: his switch still works
    with open(os.path.join(os.path.dirname(__file__), "..", "trading", "exit_engine.py"), encoding="utf-8") as fh:
        assert '"gajjala_floors": bool(doc.get("gajjala_floors", False)),' in fh.read()


def test_rules_object_and_awaiting_list(gg, monkeypatch):
    gg()
    r = GL.status_block(EE.get_config())["rules"]
    assert r["entry_text"] == ("market at the break, after the entry bar closes (GG: 'right at the break … sometimes "
                               "I wait for the bar close'); never during a halt — one clean closed bar after the resume "
                               "(GG: 'when it's clean, when it's calmer, then I enter')")      # 2026-10-21 A5
    assert r["stop_text"] == "the alert's stop, a market stop at the broker from the fill (GG: 'low of the prior bar as the stop loss')"
    assert r["size_text"] == "half of 0.25% of equity at risk first; the other half is added at breakeven (GG: 'half size, then add')"
    # 2026-10-21 (critic): the wording says what be_bar() does — ONE close above the entry, ≥ 3 bars after the entry bar
    assert r["manage_text"] == ("no target — after the first closed bar, 3 or more bars after the entry bar, that "
                                "closes above the entry, the stop moves to breakeven and the second half is added; the "
                                "remainder trails the 5-minute 9 EMA, the 21 on Kiss & Fly (out on a close below it); "
                                "after the add, the first closed bar closing at a new high of the move peels half; "
                                "flat at 15:55 ET")                                    # 2026-10-21 A5
    assert "after 3 closed bars above the entry" not in r["manage_text"]       # NEG: the old wording is gone
    assert r["risk_text"].startswith("0.25% of equity per trade, halved after a loss, back to 0.25% after a win — now "
                                     "0.25%; drawdown mode off: ")
    assert r["exempt_text"] == ("no earnings shield, no five-position ceiling, no SEPA distribution exit on lane names "
                                "— GG's rules only")
    assert r["not_built"][0] == "base counting (3rd base climax, 4th out)" and len(r["not_built"]) == 6
    assert r["not_built"][-1].startswith("all-in on an obvious A+")             # 2026-10-21 A4: still not built
    assert r["awaiting"] == [] and GL.AWAITING == ()                            # 2026-10-21 A5: nothing awaits
    text = json.dumps(GL.status_block(EE.get_config()), ensure_ascii=False).lower()
    assert ("b" + "ounc") not in text and "win rate" not in text and "edge" not in text.replace("no edge", "")


def test_no_placeholder_left_and_every_gg_number_is_cited():
    # 2026-10-21 (BUILD_SPEC22): the four placeholders are gone — GG's sentences replace them (cited in the new file)
    assert GL.AWAITING == ()
    with open(os.path.join(os.path.dirname(__file__), "..", "trading", "gajjala_entry.py"), encoding="utf-8") as fh:
        src = fh.read()
    for name in ("GG_PARTIAL_R", "GG_HALT_CALM_MIN", "GG_CUSHION_DOUBLE_PCT"):
        assert not any(x.startswith(name + " = ") for x in src.splitlines()), name
    assert "awaiting your number" not in src
    for name in ("GAJJALA_RISK_PCT", "GG_BE_AFTER_BARS", "GG_PARTIAL_FRAC", "GG_REENTRY_WAIT_BARS", "GG_DRAWDOWN_PCT",
                 "GG_DRAWDOWN_TRADES", "GG_DRAWDOWN_RISK_SUM_PCT", "GG_LOSS_RISK_CUT", "GG_TRAIL_EMA"):
        line = next(x for x in src.splitlines() if x.startswith(name + " = "))
        assert "GG" in line.split("#", 1)[1], line
    for name in ("GAJJALA_MAX_OPEN", "GAJJALA_MAX_NOTIONAL_PCT", "GAJJALA_MISSED_R", "GAJJALA_FLATTEN_BEFORE_CLOSE_MIN"):
        line = next(x for x in src.splitlines() if x.startswith(name + " = "))
        assert "MINE — HIS CALL #" in line, line
    assert GL.GG_TRAIL_EMA is GC.EMA_FAST


def test_the_grader_keeps_its_plus_1R():
    from chart_maps.gajjala import ledger as GLG
    assert GC.LEDGER_R_MULT == 1.0 and GL.R_MULT is GC.LEDGER_R_MULT
    with open(GLG.__file__, encoding="utf-8") as fh:
        assert "gajjala_entry" not in fh.read()                          # the grader never reads the lane


# ── F5 the broker changes, both brokers ──────────────────────────────────────────────────────────────────────────
def _capture(monkeypatch):
    sent = []
    monkeypatch.setattr(BA, "_request", lambda method, path, params=None, json_body=None, base=None:
                        sent.append({"method": method, "path": path, "params": params, "body": json_body}) or {"id": "x"})
    monkeypatch.setattr(BA, "clock", lambda: {"is_open": True})
    return sent


def test_alpaca_oto_without_a_take_profit(monkeypatch):
    sent = _capture(monkeypatch)
    BA.submit_bracket("saiq", 735, None, 4.31, client_order_id="c1", tif="day", order_class="oto")
    b = sent[-1]["body"]
    assert b["order_class"] == "oto" and "take_profit" not in b and b["stop_loss"] == {"stop_price": "4.31"}
    assert b["type"] == "market" and "limit_price" not in b and b["time_in_force"] == "day"
    BA.submit_bracket("saiq", 735, None, 4.31)                            # None alone → oto
    assert sent[-1]["body"]["order_class"] == "oto"
    BA.submit_bracket("saiq", 10, 4.66, 4.31, limit_price=4.51)          # NEG: existing callers unchanged
    b = sent[-1]["body"]
    assert b["order_class"] == "bracket" and b["take_profit"] == {"limit_price": "4.66"}


def test_alpaca_close_position_qty(monkeypatch):
    sent = _capture(monkeypatch)
    BA.close_position("saiq", qty=367)
    assert sent[-1] == {"method": "DELETE", "path": "/v2/positions/SAIQ", "params": {"qty": "367"}, "body": None}
    BA.close_position("saiq")
    assert sent[-1]["params"] is None                                    # NEG: the whole position as before
    with pytest.raises(BA.BrokerError):
        BA.close_position("saiq", qty=0)


def _sim(monkeypatch, quotes):
    db = SimDB()
    monkeypatch.setattr(BS, "_db", lambda: db)
    monkeypatch.setattr(BS, "_bulk_live", lambda syms: {s: {"price": quotes[s]} for s in syms if s in quotes})
    monkeypatch.setattr(BS, "clock", lambda: {"is_open": True, "timestamp": "2026-10-21T10:00:00-04:00"})
    return db


def test_sim_oto_has_only_the_stop_leg_and_partial_close(monkeypatch):
    quotes = {"SAIQ": 4.48}
    db = _sim(monkeypatch, quotes)
    o = BS.submit_bracket("SAIQ", 100, None, 4.31, client_order_id="sim-1", tif="day")
    legs = [x for x in db.sim_orders.rows if x.get("parent_id") == o["id"]]
    assert [x["leg_kind"] for x in legs] == ["stop_loss"] and o["order_class"] == "oto"
    BS.process_fills()
    assert db.sim_positions.find_one({"symbol": "SAIQ"})["qty"] == 100
    assert [x["status"] for x in db.sim_orders.rows if x.get("parent_id") == o["id"]] == ["new"]
    BS.close_position("SAIQ", qty=40)
    assert db.sim_positions.find_one({"symbol": "SAIQ"})["qty"] == 60
    with pytest.raises(BS.BrokerError, match="insufficient qty"):
        BS.close_position("SAIQ", qty=61)                                 # NEG: never more than held
    BS.close_position("SAIQ")
    assert db.sim_positions.find_one({"symbol": "SAIQ"}) is None
    o2 = BS.submit_bracket("SAIQ", 1, 4.66, 4.31, client_order_id="sim-2")      # NEG: a bracket keeps both legs
    assert sorted(x["leg_kind"] for x in db.sim_orders.rows if x.get("parent_id") == o2["id"]) == \
        ["stop_loss", "take_profit"]
