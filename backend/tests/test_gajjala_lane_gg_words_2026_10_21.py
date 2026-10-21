"""🚩 Gajjala lane — the four placeholders become GG's own sentences (2026-10-21, BUILD_SPEC22 Part A, A1–A5).

Ajay 2026-10-21, verbatim, on "The four lane numbers GG never gave: partial size trigger (R), 9 or 21 EMA on Kiss & Fly,
halt calm-down minutes, cushion for double size": "keep what ever Gajjala says for these".

Locks (every positive with its NEGATIVE):
  A1 Kiss & Fly trails the 21 EMA (VR 11.4) — a close under the 9 but over the 21 stays; a bull flag still trails the 9;
     an intrabar low under the 21 never exits; the LIVE bar never exits (mutation guard: bars.closed_only).
  A2 the partial into strength (VR 11.4) after the add (VR 11.3): the first closed bar after the breakeven+add bar
     closing ABOVE the highest high since the entry bar sells half through the two-tick part-sell, once (HIS CALL #24 /
     #25); NEG a close equal to that high, a LIVE bar (mutation guard), no add fill, the second strength bar.
  A3 halts (VR 10.1): one clean CLOSED bar after the bar holding the resume (HIS CALL #26); the doc WAITS, never a
     terminal skip; NEG no halt row, yesterday's halt; the stop printing meanwhile = never_triggered; the cut-off.
  A4 the cushion (VR 11.7): the lane's REALIZED P&L this ET month ≥ 2 x this trade's planned risk at the single rate →
     double; 1.99x → single; a loss streak / drawdown → single; the month boundary; NEG the broker's unrealized P&L.
  A5 nothing awaits; the served words; the rules_info line; every new constant carries its GG cite and his line.

UNMEASURED — GG's rules as he gave them, on paper; no edge, no win rate. Hermetic: fake broker + fake Mongo, the bars
and halts seams patched, no network.
"""
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.exit_engine as EE
import trading.gajjala_entry as GL
from chart_maps.gajjala import constants as GC
from tests.test_gajjala_lane import alert, seed, _at, _rows, _brackets, DAY, PLAN, SAIQ_ID
from tests.test_gajjala_lane_gg_rules import gg, v2_open, stop_leg, calls, FILL_T  # noqa: F401 — `gg` is a fixture
from tests.test_trading_engine import _position

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
SRC = os.path.join(os.path.dirname(__file__), "..", "trading", "gajjala_entry.py")
HIS = "keep what ever Gajjala says for these"
KF_ID = f"GG:{DAY}|SAIQ|kiss_fly"
SETTLE = timedelta(seconds=GC.BAR_SETTLE_SEC)


def frame(bars, live=None, day=DAY):
    """bars = [(HH, MM close label ET, close, ema9, ema21, high)]; the `low` column dips under both EMAs on purpose (an
    intrabar low is never a rule input). `live` = one more bar the clock has NOT settled yet."""
    rows = list(bars) + ([live] if live else [])
    idx = [pd.Timestamp(_at(day, r[0], r[1])).tz_convert("UTC").tz_localize(None) for r in rows]
    df = pd.DataFrame({"open": [r[2] for r in rows], "high": [r[5] for r in rows],
                       "low": [min(r[2], r[3] or r[2], r[4] or r[2]) - 0.05 for r in rows],
                       "close": [r[2] for r in rows], "volume": [1000.0] * len(rows),
                       "ema9": [r[3] for r in rows], "ema21": [r[4] for r in rows]}, index=pd.DatetimeIndex(idx))
    return SimpleNamespace(df=df)


# entry bar 10:55 (fill 10:53) + two bars at / under the fill, then the 11:10 breakeven+add bar (high 4.62)
BASE = [(10, 55, 4.47, 4.40, 4.35, 4.47), (11, 0, 4.48, 4.42, 4.36, 4.48), (11, 5, 4.47, 4.43, 4.37, 4.47),
        (11, 10, 4.60, 4.45, 4.38, 4.62)]


def after_be(**kw):
    base = dict(be_state="done", be_bar_t=_at(DAY, 11, 10).astimezone(UTC).isoformat(), be_et="11:11", stop_px=4.49,
                add_qty=735, add_order_id="brk-9", add_fill_qty=735, add_fill_px=4.60)
    base.update(kw)
    return v2_open(**base)


def be_orders():
    return [stop_leg(4.49, 735, "stop-1"), stop_leg(4.49, 735, "stop-2")]


# ── A1 the 21 EMA on Kiss & Fly ──────────────────────────────────────────────────────────────────────────────────────
def test_A1_constant_is_the_pass_21_and_its_column():
    assert GL.GG_TRAIL_EMA_KF == 21 and GL.GG_TRAIL_EMA_KF is GC.EMA_SLOW
    assert GL._EMA_COL[GL.GG_TRAIL_EMA_KF] == "ema21" and GL._EMA_COL[GL.GG_TRAIL_EMA] == "ema9"
    assert GL.trail_ema_period("kiss_fly") == 21
    for s in GC.SETUPS:
        if s != "kiss_fly":
            assert GL.trail_ema_period(s) == 9, s                            # NEG: every other setup trails the 9


def test_A1_kiss_fly_exits_under_the_21_not_under_the_9(gg):
    under9 = (11, 15, 4.55, 4.58, 4.50, 4.57)                              # under the 9, over the 21
    s = gg(docs=[after_be(_id=KF_ID, setup="kiss_fly")], positions=[_position("SAIQ", 1470, 4.545, 4.55)],
           orders=be_orders(), frame=frame(BASE + [under9]), now=_at(DAY, 11, 16))
    out = s.run()
    assert out["trailed"] == 0 and s.coll.get(KF_ID)["state"] == "open" and calls(s.brk, "close_position") == []
    s.frame = frame(BASE + [under9, (11, 20, 4.48, 4.56, 4.50, 4.56)])     # the close under the 21
    out = s.run(at=_at(DAY, 11, 21))
    d = s.coll.get(KF_ID)
    assert out["trailed"] == 1 and d["state"] == "closing" and d["exit_kind"] == "trail"
    assert "under the 21 EMA 4.50" in d["why"] and calls(s.brk, "close_position") == [{"symbol": "SAIQ", "qty": None}]
    assert "trailing the 21 EMA" in GL.fate_text(dict(d, state="open"))


def test_A1_bull_flag_still_exits_on_the_9(gg):
    s = gg(docs=[after_be()], positions=[_position("SAIQ", 1470, 4.545, 4.55)], orders=be_orders(),
           frame=frame(BASE + [(11, 15, 4.55, 4.58, 4.50, 4.57)]), now=_at(DAY, 11, 16))
    out = s.run()
    d = s.coll.get(SAIQ_ID)
    assert out["trailed"] == 1 and d["exit_kind"] == "trail" and "under the 9 EMA" in d["why"]


def test_A1_NEG_an_intrabar_low_under_the_21_never_exits(gg):
    f = frame(BASE + [(11, 15, 4.56, 4.55, 4.50, 4.58)])
    assert f.df["low"].iloc[-1] < 4.50                                      # the low dips under the 21
    s = gg(docs=[after_be(_id=KF_ID, setup="kiss_fly")], positions=[_position("SAIQ", 1470, 4.545, 4.56)],
           orders=be_orders(), frame=f, now=_at(DAY, 11, 16))
    out = s.run()
    assert out["trailed"] == 0 and s.coll.get(KF_ID)["state"] == "open" and calls(s.brk, "close_position") == []


def test_A1_NEG_the_live_bar_under_the_21_never_exits(gg):
    """Mutation guard: drop `GB.closed_only` in closed_rows and this test fails."""
    s = gg(docs=[after_be(_id=KF_ID, setup="kiss_fly")], positions=[_position("SAIQ", 1470, 4.545, 4.40)],
           orders=be_orders(), frame=frame(BASE, live=(11, 15, 4.40, 4.55, 4.50, 4.58)),
           now=_at(DAY, 11, 15) + timedelta(seconds=10))
    out = s.run()
    assert out["trailed"] == 0 and calls(s.brk, "close_position") == []
    out = s.run(at=_at(DAY, 11, 15) + SETTLE)                               # settled → now it counts
    assert out["trailed"] == 1


# ── A2 the partial into strength after the add ──────────────────────────────────────────────────────────────────────
def _rows_of(bars, now):
    return GL.closed_rows(frame(bars), now)


def test_A2_strength_bar_pure():
    mins = 5
    after = _at(DAY, 11, 10).astimezone(UTC)
    rows = _rows_of(BASE + [(11, 15, 4.63, 4.50, 4.40, 4.64)], _at(DAY, 11, 16))
    b = GL.strength_bar(rows, FILL_T, after, mins)
    assert b["t"] == _at(DAY, 11, 15).astimezone(UTC) and b["prior_high"] == 4.62     # 4.63 > every high since entry
    assert GL.strength_bar(_rows_of(BASE, _at(DAY, 11, 16)), FILL_T, after, mins) is None   # NEG: the BE bar itself
    eq = _rows_of(BASE + [(11, 15, 4.62, 4.50, 4.40, 4.62)], _at(DAY, 11, 16))
    assert GL.strength_bar(eq, FILL_T, after, mins) is None                 # NEG: equal to the high is not strength
    pre = [(10, 50, 4.40, 4.30, 4.30, 9.99)] + BASE + [(11, 15, 4.63, 4.50, 4.40, 4.64)]
    assert GL.strength_bar(_rows_of(pre, _at(DAY, 11, 16)), FILL_T, after, mins)["prior_high"] == 4.62   # pre-entry out
    late = BASE + [(11, 15, 4.61, 4.50, 4.40, 4.70), (11, 20, 4.69, 4.55, 4.42, 4.69), (11, 25, 4.71, 4.6, 4.45, 4.72)]
    b = GL.strength_bar(_rows_of(late, _at(DAY, 11, 26)), FILL_T, after, mins)
    assert b["t"] == _at(DAY, 11, 25).astimezone(UTC) and b["prior_high"] == 4.70    # the 11:15 wick raised the bar
    assert GL.strength_bar(rows, FILL_T, None, mins) is None                # NEG: no breakeven bar → never


def test_A2_partial_due_needs_the_add_fill():
    assert GL.GG_PARTIAL_AFTER == "add" and GL.GG_PARTIAL_STRENGTH == "new_high" and GL.GG_PARTIAL_FRAC == 0.5
    assert GL.partial_due(after_be())
    assert not GL.partial_due(after_be(add_fill_qty=None))                  # NEG: the add has not filled
    assert not GL.partial_due(after_be(add_fill_qty=0, add_refused="lane switched off — no new buys"))   # NEG: refused
    assert not GL.partial_due(v2_open())                                    # NEG: before breakeven
    assert not GL.partial_due(after_be(partial_state="done"))               # NEG: once per trade


def test_A2_partial_sells_half_after_the_add_into_a_new_high(gg):
    s = gg(docs=[after_be()], positions=[_position("SAIQ", 1470, 4.545, 4.63)], orders=be_orders(),
           frame=frame(BASE + [(11, 15, 4.63, 4.50, 4.40, 4.64)]), now=_at(DAY, 11, 16))
    out = s.run()                                                           # tick N cancels the stops only
    assert out["partials"] == 0 and calls(s.brk, "close_position") == []
    assert sorted(c["order_id"] for c in calls(s.brk, "cancel_order")) == ["stop-1", "stop-2"]
    d = s.coll.get(SAIQ_ID)
    assert d["partial_state"] == "cancelling"
    assert d["partial_why"] == ("🚩 Gajjala lane: half into strength — the 11:15 ET 5-minute bar closed 4.63 over the "
                                "move's high 4.62 (GG: 'peel off 1/3 or half into strength')")
    out = s.run(at=_at(DAY, 11, 17))                                        # tick N+1 sells half, re-stops the rest
    assert out["partials"] == 1 and calls(s.brk, "close_position") == [{"symbol": "SAIQ", "qty": 735}]
    assert calls(s.brk, "submit_stop") == [{"symbol": "SAIQ", "qty": 735, "stop_price": 4.49}]
    d = s.coll.get(SAIQ_ID)
    assert d["partial_state"] == "done" and d["partial_qty"] == 735 and len(_rows(s.db, "gajjala_partial")) == 1
    assert "735 sold into strength" in GL.fate_text(d)


def test_A2_NEG_the_second_strength_bar_sells_nothing_more(gg):
    f = frame(BASE + [(11, 15, 4.63, 4.50, 4.40, 4.64), (11, 20, 4.80, 4.55, 4.42, 4.81)])
    s = gg(docs=[after_be(partial_state="done", partial_qty=735)], positions=[_position("SAIQ", 735, 4.545, 4.80)],
           orders=[stop_leg(4.49, 735, "stop-3")], frame=f, now=_at(DAY, 11, 21))
    out = s.run()
    assert out["partials"] == 0 and calls(s.brk, "close_position") == [] and calls(s.brk, "cancel_order") == []


def test_A2_NEG_a_close_equal_to_the_moves_high(gg):
    s = gg(docs=[after_be()], positions=[_position("SAIQ", 1470, 4.545, 4.62)], orders=be_orders(),
           frame=frame(BASE + [(11, 15, 4.62, 4.50, 4.40, 4.62)]), now=_at(DAY, 11, 16))
    out = s.run()
    assert out["partials"] == 0 and calls(s.brk, "cancel_order") == [] and s.coll.get(SAIQ_ID)["partial_state"] is None


def test_A2_NEG_the_live_bar_never_counts(gg):
    """Mutation guard (memory cheetah_live_bar_overlay): the 11:15 bar is still printing at 11:15:10 — drop
    `GB.closed_only` in closed_rows and this test fails."""
    s = gg(docs=[after_be()], positions=[_position("SAIQ", 1470, 4.545, 5.00)], orders=be_orders(),
           frame=frame(BASE, live=(11, 15, 5.00, 4.60, 4.45, 5.01)), now=_at(DAY, 11, 15) + timedelta(seconds=10))
    out = s.run()
    assert out["partials"] == 0 and calls(s.brk, "cancel_order") == [] and s.coll.get(SAIQ_ID)["partial_state"] is None
    s.run(at=_at(DAY, 11, 15) + SETTLE)                                     # settled → the peel starts
    assert s.coll.get(SAIQ_ID)["partial_state"] == "cancelling"


def test_A2_NEG_before_the_add_no_partial(gg):
    """The breakeven came but the add's fill is not recorded yet (its order is still working): no peel."""
    doc = after_be(add_fill_qty=None, add_fill_px=None)
    s = gg(docs=[doc], positions=[_position("SAIQ", 735, 4.49, 4.80)],
           orders=[stop_leg(4.49, 735, "stop-1"), {"id": "brk-9", "symbol": "SAIQ", "side": "buy", "type": "market",
                                                   "status": "new", "qty": "735", "filled_qty": "0"}],
           frame=frame(BASE + [(11, 15, 4.80, 4.50, 4.40, 4.81)]), now=_at(DAY, 11, 16))
    out = s.run()
    assert out["partials"] == 0 and calls(s.brk, "cancel_order") == [] and s.coll.get(SAIQ_ID)["partial_state"] is None


def test_A2_NEG_before_breakeven_no_partial(gg):
    s = gg(docs=[v2_open()], positions=[_position("SAIQ", 735, 4.49, 4.80)], orders=[stop_leg()],
           frame=frame([(10, 55, 4.47, 4.40, 4.35, 4.47), (11, 0, 4.80, 4.42, 4.36, 4.81)]), now=_at(DAY, 11, 1))
    out = s.run()
    assert out["partials"] == 0 and out["breakeven"] == 0 and calls(s.brk, "cancel_order") == []


# ── A3 halts ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _h(resume=None, n=1, day=DAY, first="10:41:07"):
    return {"n": n, "text": f"⏸ halted ×{n} (LUDP)", "date": day, "first_halt_time": first,
            "last_resume_et": resume.isoformat() if isinstance(resume, datetime) else resume}


def test_A3_halt_wait_pure():
    assert GL.GG_HALT_CALM_BARS == 1 and not hasattr(GL, "GG_HALT_CALM_MIN")
    h = _h(_at(DAY, 10, 52))                                                 # inside the 10:50–10:55 bar
    w = GL.halt_wait(h, _at(DAY, 10, 56), DAY, 5)
    assert w["until"] == _at(DAY, 11, 0).astimezone(UTC)
    assert w["why"] == "halted, resumed 10:52 ET — waiting for one clean closed bar (closes 11:00 ET)"
    assert GL.halt_wait(h, _at(DAY, 11, 0) + timedelta(seconds=GC.BAR_SETTLE_SEC - 1), DAY, 5) is not None
    assert GL.halt_wait(h, _at(DAY, 11, 0) + SETTLE, DAY, 5) is None         # the clean bar closed
    still = GL.halt_wait(_h(None), _at(DAY, 14, 0), DAY, 5)
    assert still["why"] == "halted at 10:41 ET, not resumed — waiting for one clean closed bar after the resume"
    assert GL.halt_wait(None, _at(DAY, 10, 56), DAY, 5) is None             # NEG: no halt row
    assert GL.halt_wait(_h(_at(DAY, 10, 52), n=0), _at(DAY, 10, 56), DAY, 5) is None    # NEG: no halt counted
    assert GL.halt_wait(_h(None, day="2026-10-19"), _at(DAY, 10, 56), DAY, 5) is None   # NEG: yesterday's row
    y = _h(_at("2026-10-19", 15, 58))
    assert GL.halt_wait(y, _at(DAY, 9, 46), DAY, 5) is None                 # NEG: a resume yesterday


def test_A3_waits_with_the_resume_inside_the_live_bar_then_enters(gg):
    s = gg(alerts=[alert()], lasts={"SAIQ": 4.48}, halts=_h(_at(DAY, 10, 57)), now=_at(DAY, 10, 58))
    out = s.run()
    d = s.coll.get(SAIQ_ID)
    assert out["halt_waiting"] == 1 and d["state"] == "waiting" and d["wait_reason"] == "halt_calm"
    assert d["skip_kind"] is None and _brackets(s.brk) == [] and not _rows(s.db, "gajjala_skip")   # never terminal
    assert GL.fate_text(d) == ("halted, resumed 10:57 ET — waiting for one clean closed bar (closes 11:05 ET) · "
                               "trigger 4.46 (stop 4.31) — until 15:30 ET · ⏸ halted ×1 (LUDP) today")
    assert s.run(at=_at(DAY, 11, 3))["halt_waiting"] == 1 and _brackets(s.brk) == []   # resume bar closed, not clean
    out = s.run(at=_at(DAY, 11, 5) + SETTLE)
    d = s.coll.get(SAIQ_ID)
    assert out["ordered"] == 1 and d["state"] == "ordered" and d["wait_reason"] is None and len(_brackets(s.brk)) == 1


def test_A3_never_enters_while_still_halted_and_the_cutoff_is_unfilled(gg):
    s = gg(alerts=[alert()], lasts={"SAIQ": 4.48}, halts=_h(None), now=_at(DAY, 10, 55))
    for hm in ((10, 55), (11, 30), (15, 29)):
        s.run(at=_at(DAY, *hm))
    assert _brackets(s.brk) == [] and s.coll.get(SAIQ_ID)["state"] == "waiting"
    s.run(at=_at(DAY, 15, 30))
    d = s.coll.get(SAIQ_ID)
    assert d["state"] == "unfilled" and d["skip_kind"] == "halt" and _brackets(s.brk) == []
    assert d["why"] == "still waiting for one clean closed bar after the halt at the 15:30 ET cut-off"


def test_A3_the_stop_printing_while_halted_is_never_triggered(gg):
    s = gg(alerts=[alert()], lasts={"SAIQ": 4.48}, halts=_h(None), now=_at(DAY, 10, 55))
    s.run()
    s.lasts["SAIQ"] = 4.30
    s.run(at=_at(DAY, 11, 0))
    d = s.coll.get(SAIQ_ID)
    assert d["state"] == "unfilled" and d["skip_kind"] == "never_triggered" and _brackets(s.brk) == []


def test_A3_back_under_the_trigger_the_plain_wait_again(gg):
    s = gg(alerts=[alert()], lasts={"SAIQ": 4.48}, halts=_h(None), now=_at(DAY, 10, 55))
    s.run()
    s.lasts["SAIQ"] = 4.40
    s.run(at=_at(DAY, 11, 0))
    d = s.coll.get(SAIQ_ID)
    assert d["state"] == "waiting" and d["wait_reason"] is None
    assert GL.fate_text(d).startswith("waiting for the tape to trade 4.46")


def test_A3_NEG_no_halt_row_is_untouched(gg):
    s = gg(alerts=[alert()], lasts={"SAIQ": 4.48}, halts=None, now=_at(DAY, 10, 55))
    out = s.run()
    d = s.coll.get(SAIQ_ID)
    assert out["halt_waiting"] == 0 and d["state"] == "ordered" and d.get("wait_reason") is None


def test_A3_NEG_a_halt_yesterday_is_ignored(gg):
    s = gg(alerts=[alert()], lasts={"SAIQ": 4.48}, halts=_h(None, day="2026-10-19"), now=_at(DAY, 10, 55))
    out = s.run()
    assert out["halt_waiting"] == 0 and s.coll.get(SAIQ_ID)["state"] == "ordered"


def test_A3_halts_of_carries_the_date_and_first_halt(monkeypatch):
    import chart_maps.gajjala.store as GST

    class Store:
        def halts(self, day):
            return [{"date": day, "symbol": "SAIQ", "n_halts": 2, "reasons": ["LUDP"], "first_halt_time": "10:41:07",
                     "last_resume_et": "2026-10-20T10:57:00-04:00", "source": "live"}]
    monkeypatch.setattr(GST, "GajjalaStore", Store)
    h = GL._halts_of(DAY, "saiq")
    assert h == {"n": 2, "text": "⏸ halted ×2 (LUDP)", "last_resume_et": "2026-10-20T10:57:00-04:00",
                 "first_halt_time": "10:41:07", "last_halt_time": None, "open_halt": False, "date": DAY}
    assert GL._halts_of(DAY, "OTHR") is None                                # NEG: another name


# ── A4 the cushion → double ──────────────────────────────────────────────────────────────────────────────────────────
def test_A4_cushion_read_pure():
    assert (GL.GG_CUSHION_LOSERS, GL.GG_DOUBLE_MULT, GL.GG_CUSHION_PERIOD) == (2, 2.0, "month")
    assert not hasattr(GL, "GG_CUSHION_DOUBLE_PCT")
    c = GL.cushion_read(500.0, 250.0)
    assert c["double"] and c["need"] == 500.0
    assert c["text"] == "cushion +$500.00 this month vs 2 losers $500.00 → double"
    assert not GL.cushion_read(497.5, 250.0)["double"]                      # NEG: 1.99x
    lo = GL.cushion_read(900.0, 250.0, risk_mult=0.5)
    assert not lo["double"] and lo["text"].endswith("→ single (risk halved after a loss)")   # NEG: a loss streak
    dd = GL.cushion_read(900.0, 250.0, state={"in_drawdown": True})
    assert not dd["double"] and dd["text"].endswith("→ single (drawdown mode)")             # NEG: drawdown on
    assert not GL.cushion_read(900.0, 250.0, state={"dd_window": {"trades": 1}})["double"]  # NEG: a window open
    assert not GL.cushion_read(900.0, None)["double"] and not GL.cushion_read(-10.0, 250.0)["double"]


def _closed(sym, pnl, exit_t, **kw):
    return seed(_id=f"GG:x|{sym}|bull_flag|{exit_t.isoformat()}", symbol=sym, state="closed", exit_kind="trail",
                exit_t=exit_t.astimezone(UTC).isoformat(), pnl_usd=pnl, date=exit_t.date().isoformat(), **kw)


def test_A4_month_realized_pnl_and_the_month_boundary():
    docs = [_closed("AAA", 300.0, _at("2026-10-31", 11, 0)), _closed("BBB", 200.0, _at("2026-10-01", 10, 0)),
            _closed("CCC", -50.0, _at("2026-09-30", 15, 0)),
            seed(_id="o", symbol="DDD", state="open", pnl_usd=99_999.0),          # NEG: unrealized never counts
            seed(_id="u", symbol="EEE", state="unfilled", pnl_usd=12_345.0)]
    assert GL.month_realized_pnl(docs, "2026-10-31") == 500.0
    assert GL.month_realized_pnl(docs, date(2026, 11, 1)) == 0.0            # the boundary resets
    assert GL.month_realized_pnl(docs, "2026-09-30") == -50.0
    late = _closed("FFF", 80.0, datetime(2026, 11, 1, 0, 30, tzinfo=UTC))   # 20:30 ET on 10-31 → October
    assert GL.month_realized_pnl([late], "2026-10-31") == 80.0 and GL.month_realized_pnl([late], "2026-11-01") == 0.0


# the single plan at 4.48: full 1470 x 0.17 = $249.90 at risk → the cushion needs 2 x 249.90 = $499.80
NEED = 499.80


def test_A4_exactly_two_losers_doubles_the_A_plus(gg):
    s = gg(docs=[_closed("OTHR", NEED, _at(DAY, 10, 30))], alerts=[alert()], lasts={"SAIQ": 4.48}, now=_at(DAY, 10, 55))
    s.run()
    d = s.coll.get(SAIQ_ID)
    (br,) = _brackets(s.brk)
    dbl = GL.entry_plan(PLAN, 4.48, 100_000, 100_000, risk_mult=GL.GG_DOUBLE_MULT)
    assert d["risk_basis"] == "double" and br["qty"] == dbl["qty"] == d["qty"] and d["qty"] > 735   # up to double
    assert d["risk_pct"] == 0.5 and d["full_qty"] == dbl["full_qty"]
    assert d["cushion_text"] == "cushion +$499.80 this month vs 2 losers $499.80 → double"
    assert _rows(s.db, "gajjala_entry")[0]["detail"]["risk_basis"] == "double"


def test_A4_NEG_one_point_nine_nine_losers_stays_single(gg):
    s = gg(docs=[_closed("OTHR", round(NEED * 1.99 / 2, 2), _at(DAY, 10, 30))], alerts=[alert()],
           lasts={"SAIQ": 4.48}, now=_at(DAY, 10, 55))
    s.run()
    d = s.coll.get(SAIQ_ID)
    assert d["risk_basis"] == "single" and d["qty"] == 735 and _brackets(s.brk)[0]["qty"] == 735


def test_A4_NEG_a_loss_streak_stays_single(gg):
    s = gg(docs=[_closed("OTHR", 5_000.0, _at(DAY, 10, 30))], alerts=[alert()], lasts={"SAIQ": 4.48},
           now=_at(DAY, 10, 55), state={"risk_mult": 0.5})
    s.run()
    d = s.coll.get(SAIQ_ID)
    assert d["risk_basis"] == "single" and d["risk_pct"] == 0.125 and d["qty"] == 367


def test_A4_NEG_drawdown_on_stays_single(gg):
    s = gg(docs=[_closed("OTHR", 5_000.0, _at(DAY, 10, 30))], alerts=[alert()], lasts={"SAIQ": 4.48},
           now=_at(DAY, 10, 55), equity=89_000.0,
           state={"equity_peak": 100_000.0, "in_drawdown": True, "risk_mult": 1.0,
                  "dd_window": {"opened_at": "x", "trades": 0, "risk_used_pct": 0.0}})
    s.run()
    d = s.coll.get(SAIQ_ID)
    assert d["risk_basis"] == "single" and d["risk_pct"] == 0.25


def test_A4_the_month_boundary_resets_the_cushion(gg):
    """10-30 (Fri) with an October cushion → double; the same docs on 11-02 (Mon) → single (a new month)."""
    oct_win = _closed("OTHR", 5_000.0, _at("2026-10-30", 10, 0))
    s = gg(docs=[oct_win], alerts=[alert(day="2026-10-30")], lasts={"SAIQ": 4.48}, now=_at("2026-10-30", 10, 55))
    s.run()
    assert s.coll.get(f"GG:2026-10-30|SAIQ|bull_flag")["risk_basis"] == "double"
    s = gg(docs=[oct_win], alerts=[alert(day="2026-11-02")], lasts={"SAIQ": 4.48}, now=_at("2026-11-02", 10, 55))
    s.run()
    d = s.coll.get(f"GG:2026-11-02|SAIQ|bull_flag")
    assert d["risk_basis"] == "single" and d["cushion_text"].startswith("cushion +$0.00 this month")


def test_A4_NEG_the_brokers_unrealized_pnl_never_counts(gg, monkeypatch):
    s = gg(docs=[seed(_id=f"GG:{DAY}|OPEN|bull_flag", symbol="OPEN", state="open", pnl_usd=50_000.0, fill_px=1.0,
                      fill_qty=100, target=None, version=2)],
           positions=[_position("OPEN", 100, 1.0, 501.0)], alerts=[alert()], lasts={"SAIQ": 4.48},
           now=_at(DAY, 10, 55), equity=200_000.0)
    acct = s.brk.account

    def rich():
        return dict(acct(), unrealized_pl="50000", unrealized_intraday_pl="50000", last_equity="100000")
    monkeypatch.setattr(s.brk, "account", rich, raising=False)
    s.run()
    d = s.coll.get(SAIQ_ID)
    assert s.coll.get(f"GG:{DAY}|OPEN|bull_flag")["state"] == "open"         # still open: its P&L is unrealized
    assert d["risk_basis"] == "single" and d["cushion_text"].startswith("cushion +$0.00 this month")


def test_A4_served_risk_text_names_the_cushion(gg):
    s = gg(docs=[_closed("OTHR", 600.0, _at(DAY, 10, 30))], state={"equity": 100_000.0, "risk_mult": 1.0})
    st = GL.status_block(EE.get_config())
    assert st["rules"]["risk_text"].endswith(
        "an A+ risks 2× once this month's realized lane P&L covers 2 losers at the single rate, with no loss streak "
        "and drawdown mode off (GG: 'raise only on a cushion that survives 2 losers; A+ up to double') — cushion "
        "+$600.00 this month vs 2 losers $500.00 → double (estimated on 0.25% of the last equity read; each entry "
        "decides on its own planned risk and size caps)")
    s.coll.rows[0]["pnl_usd"] = 499.0
    assert GL.status_block(EE.get_config())["rules"]["risk_text"].endswith(
        "vs 2 losers $500.00 → single (estimated on 0.25% of the last equity read; each entry decides on its own "
        "planned risk and size caps)")
    assert st["settings"]["cushion_losers"] == 2 and st["settings"]["double_mult"] == 2.0
    assert st["settings"]["cushion_period"] == "month" and st["settings"]["halt_calm_bars"] == 1


# ── A5 nothing awaits; the served words; rules_info; the cites ─────────────────────────────────────────────────────
def test_A5_nothing_awaits_and_the_served_words(gg):
    s = gg()
    st = GL.status_block(EE.get_config())
    r = st["rules"]
    assert r["awaiting"] == [] and GL.AWAITING == ()
    assert "the remainder trails the 5-minute 9 EMA, the 21 on Kiss & Fly" in r["manage_text"]
    assert "after the add, the first closed bar closing at a new high of the move peels half" in r["manage_text"]
    assert r["entry_text"].endswith("never during a halt — one clean closed bar after the resume (GG: 'when it's "
                                    "clean, when it's calmer, then I enter')")
    assert "all-in on an obvious A+ (GG's word “obvious” has no rule)" in r["not_built"]
    for gone in ("partial_r", "halt_calm_min", "cushion_double_pct"):
        assert gone not in st["settings"], gone
    assert (st["settings"]["partial_after"], st["settings"]["partial_strength"]) == ("add", "new_high")
    text = json.dumps(st, ensure_ascii=False).lower()
    assert ("b" + "ounc") not in text and "win rate" not in text and "awaiting your number" not in text


def test_A5_the_words_move_with_the_constants(monkeypatch):
    monkeypatch.setattr(GL, "GG_HALT_CALM_BARS", 2)
    monkeypatch.setattr(GL, "GG_PARTIAL_FRAC", 1 / 3)
    r = GL.rules_block()
    assert "never during a halt — 2 clean closed bars after the resume" in r["entry_text"]
    assert "peels 33.3333%" in r["manage_text"] and "peels half" not in r["manage_text"]


def test_A5_rules_info_lane_line_is_built_from_the_constants():
    from supply_demand import rules_info as RI
    line = next(x for x in RI.sections()["autopilot"]["picks"] if x.startswith("🚩 Gajjala lane (paper)"))
    assert ("the rest trails the %d EMA (the %d on Kiss & Fly; out on a closed bar under it)"
            % (GL.GG_TRAIL_EMA, GL.GG_TRAIL_EMA_KF)) in line
    assert "after the add, the first closed bar closing above every high since the entry sells half" in line
    assert "never enters during a halt — one clean closed bar after the resume" in line
    assert ("an A+ risks %g× once the month's realized lane P&L covers %d losers at the single rate"
            % (GL.GG_DOUBLE_MULT, GL.GG_CUSHION_LOSERS)) in line
    assert "UNMEASURED" in line and ("b" + "ounc") not in line.lower()


def test_A5_rules_info_line_MOVES_with_the_constants(monkeypatch):
    from supply_demand import rules_info as RI
    monkeypatch.setattr(GL, "GG_CUSHION_LOSERS", 3)
    line = next(x for x in RI.sections()["autopilot"]["picks"] if x.startswith("🚩 Gajjala lane (paper)"))
    assert "covers 3 losers" in line and "covers 2 losers" not in line


NEW = {"GG_PARTIAL_AFTER": ("VR 11.4", None), "GG_PARTIAL_STRENGTH": ("VR 11.4", "HIS CALL #24"),
       "GG_TRAIL_EMA_KF": ("VR 11.4", None), "GG_HALT_CALM_BARS": ("VR 10.1", "HIS CALL #26"),
       "GG_CUSHION_LOSERS": ("VR 11.7", None), "GG_DOUBLE_MULT": ("VR 11.7", None),
       "GG_CUSHION_PERIOD": ("VR 11.7", None), "GG_PARTIAL_FRAC": ("VR 11.4", "HIS CALL #25")}


def test_A5_every_new_constant_carries_its_GG_cite_and_his_line():
    with open(SRC, encoding="utf-8") as fh:
        src = fh.read()
    lines = src.splitlines()
    for name, (cite, call) in NEW.items():
        line = next(x for x in lines if x.startswith(name + " = "))
        tail = line.split("#", 1)[1]
        assert ("GG " + cite) in tail, line
        if name != "GG_PARTIAL_FRAC":                                        # the 2026-10-21 lines carry his sentence
            assert f'Ajay 2026-10-21 "{HIS}"' in tail, line
        if call:
            assert call in tail, line
        assert "MINE" not in tail, line
    for gone in ("GG_PARTIAL_R", "GG_HALT_CALM_MIN", "GG_CUSHION_DOUBLE_PCT"):
        assert not any(x.startswith(gone + " = ") for x in lines), gone
        assert not hasattr(GL, gone), gone
    assert "awaiting your number" not in src
    assert HIS in GL.__doc__


def test_A5_NEG_a_placeholder_back_at_None_would_be_caught():
    """The served words never print None (a stand-in for a placeholder sneaking back)."""
    for k in ("GG_TRAIL_EMA_KF", "GG_HALT_CALM_BARS", "GG_CUSHION_LOSERS", "GG_DOUBLE_MULT"):
        assert getattr(GL, k) is not None, k
    assert "None" not in json.dumps(GL.rules_block(), ensure_ascii=False)


# ── critic fixes 2026-10-21 ─────────────────────────────────────────────────────────────────────────────────────────
from chart_maps.gajjala import context as CX                                    # noqa: E402

REHALT = {"ticker": "SAIQ", "n_halts": 2, "reasons": ["LUDP"], "halts": [
    {"halt_time": "10:15:00", "reason_code": "LUDP", "resume_date": "10/20/2026", "resume_time": "10:20:00"},
    {"halt_time": "10:45:00", "reason_code": "LUDP", "resume_date": None, "resume_time": None}]}


def test_FIX_a_second_halt_still_in_progress_is_halted_not_clean():
    """Critic 2026-10-21: halted, resumed, halted again — last_resume_et is the EARLIER resume; the lane must still wait."""
    h = dict(CX.halts_chip("SAIQ", {"by_ticker": {"SAIQ": REHALT}}), date=DAY)
    assert h["last_resume_et"] == "2026-10-20T10:20:00-04:00" and h["open_halt"] is True
    assert h["last_halt_time"] == "10:45:00" and h["first_halt_time"] == "10:15:00"
    w = GL.halt_wait(h, _at(DAY, 10, 50), DAY, 5)
    assert w == {"why": "halted at 10:45 ET, not resumed — waiting for one clean closed bar after the resume",
                 "until": None}
    assert GL.halt_wait(h, _at(DAY, 15, 0), DAY, 5) is not None              # still open hours later


def test_FIX_NEG_both_halts_resumed_is_judged_on_the_last_resume():
    rec = {**REHALT, "halts": [REHALT["halts"][0], dict(REHALT["halts"][1], resume_date="10/20/2026",
                                                         resume_time="10:50:00")]}
    h = dict(CX.halts_chip("SAIQ", {"by_ticker": {"SAIQ": rec}}), date=DAY)
    assert h["open_halt"] is False and h["last_resume_et"] == "2026-10-20T10:50:00-04:00"
    assert GL.halt_wait(h, _at(DAY, 10, 56), DAY, 5)["until"] == _at(DAY, 11, 0).astimezone(UTC)
    assert GL.halt_wait(h, _at(DAY, 11, 0) + SETTLE, DAY, 5) is None        # one clean closed bar after 10:50


def test_FIX_NEG_an_unparseable_resume_is_still_halted():
    rec = {**REHALT, "halts": [REHALT["halts"][0], dict(REHALT["halts"][1], resume_date="10/20/2026",
                                                         resume_time="garbage")]}
    assert CX.open_halt(rec) is True and CX.open_halt({"halts": [REHALT["halts"][0]]}) is False
    assert CX.open_halt(None) is False


def test_FIX_the_ledger_row_carries_the_open_halt_and_the_lane_reads_it(monkeypatch):
    from tests.test_gajjala_store import fake_store
    st = fake_store()
    assert CX.record_halts(st, DAY, {"by_ticker": {"SAIQ": REHALT}}, source="live") == 1
    row = st.halts(DAY)[0]
    assert row["open_halt"] is True and row["last_halt_time"] == "10:45:00"
    import chart_maps.gajjala.store as GST
    monkeypatch.setattr(GST, "GajjalaStore", lambda: st)
    h = GL._halts_of(DAY, "SAIQ")
    assert h["open_halt"] is True and GL.halt_wait(h, _at(DAY, 10, 50), DAY, 5)["until"] is None


def test_FIX_the_lane_never_enters_into_a_second_halt(gg):
    h = {"n": 2, "text": "⏸ halted ×2 (LUDP)", "date": DAY, "first_halt_time": "10:15:00",
         "last_halt_time": "10:45:00", "last_resume_et": _at(DAY, 10, 20).isoformat(), "open_halt": True}
    s = gg(alerts=[alert()], lasts={"SAIQ": 4.48}, halts=h, now=_at(DAY, 10, 55))
    out = s.run()
    d = s.coll.get(SAIQ_ID)
    assert out["halt_waiting"] == 1 and d["state"] == "waiting" and d["wait_reason"] == "halt_calm"
    assert _brackets(s.brk) == []
    s2 = gg(alerts=[alert()], lasts={"SAIQ": 4.48}, halts=dict(h, open_halt=False), now=_at(DAY, 10, 55))
    assert s2.run()["ordered"] == 1                                         # NEG: the same row, resumed → enters


def test_FIX_a_size_cap_that_holds_the_size_is_never_stamped_double(gg):
    """Critic 2026-10-21: trigger 4.46 / stop 4.36 at last 4.46 — the 10% notional cap binds at single AND double
    (full 2242 both), so the doc says single (size cap), risk_pct the single 0.25."""
    single = GL.entry_plan({"trigger": 4.46, "stop": 4.36, "plan": "ok"}, 4.46, 100_000, 100_000)
    dbl = GL.entry_plan({"trigger": 4.46, "stop": 4.36, "plan": "ok"}, 4.46, 100_000, 100_000,
                        risk_mult=GL.GG_DOUBLE_MULT)
    assert single["full_qty"] == dbl["full_qty"] == 2242 and dbl["ok"]
    s = gg(docs=[_closed("OTHR", 5_000.0, _at(DAY, 10, 30))], alerts=[alert(stop=4.36)], lasts={"SAIQ": 4.46},
           now=_at(DAY, 10, 55))
    s.run()
    d = s.coll.get(SAIQ_ID)
    assert d["risk_basis"] == "single (size cap)" and d["risk_pct"] == 0.25 and d["full_qty"] == 2242
    assert _rows(s.db, "gajjala_entry")[0]["detail"]["risk_basis"] == "single (size cap)"


def test_FIX_NEG_v1_limit_bracket_trades_never_count_toward_the_cushion():
    docs = [_closed("AAA", 300.0, _at(DAY, 11, 0)), _closed("V1", 9_000.0, _at(DAY, 11, 0), target=5.10)]
    assert GL.month_realized_pnl(docs, DAY) == 300.0
