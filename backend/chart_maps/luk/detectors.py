"""🥇 Luk's three setups as PURE functions over closed bars (Chart Maps `luk`, 2026-11-01 — spec §3.7).

WHAT. ↩️ Pullback reversal (his flush into the hourly 9/21 EMA, then the first breakout of the previous bar high —
VKNEJA5r8zw 1:56:39), 🔔 Opening range high (the take-out of the first 1-minute candle high, stop at the low of day —
lS9zbnLi1Gg 0:38:40) and 📦 Inside day → prior-day high (lS9zbnLi1Gg 0:36:11). Each detector returns one Read dict
(`_blank` lists its keys — served as-is by tab.py) whose `state` is one of STATES.

FRAMES. `F` is `chart_maps.luk.bars`' Frames (by = {"1m", "5m", "60m"}, closed bars only, ET close stamps
"%Y-%m-%d %H:%M"). The frame a break is read on is `bars.frame_for_close` of the bar's CLOSE (1-minute candles first,
then 5-minute — his E3 / E6 words); the window end is LUK_TRIGGER_WINDOW_END_MIN after the regular open.

A+ PER FRAME (C1). 5-minute frame: the break bar is the LATEST closed 5-minute bar (GG's rule, verbatim). 1-minute
frame: the break bar closed AFTER the previous Luk pass's bars-through (`prev_through_1m`; None on the first pass → any
bar today) AND no later closed 1-minute bar printed a low at or under the stop — one pass per 5-minute tick reads 1–5
one-minute bars at once, so GG's latest-bar rule would discard 4 of 5 of his 1-minute triggers.

LOOKBACKS THROUGH THE BREAK BAR (C7, C8). The low of day, the chase distance, the stop, the daily-9 pullback and the
flush are judged through the break bar's CLOSE (`forming`: through the latest closed bar) — a later low never moves a
served stop. The hourly reference is per judged 5-minute bar (`bars.hourly_ref(F, before_t = that bar's OPEN)`), never
"as of now".

PURE. Never fetches, never writes, never reads a clock. Every number is read from `chart_maps.luk.constants` at CALL
time. UNMEASURED — these are his rules as he described them; nothing here trades, sizes or enters a lane.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from datetime import time as dtime
from typing import Callable, Optional

from chart_maps.gajjala.ledger import _D, plan_of
from chart_maps.luk import bars as LB
from chart_maps.luk import constants as LC
from daytrading.data import ET_RTH_OPEN

log = logging.getLogger("chart_maps.luk.detectors")

STATES = ("aplus", "triggered", "stopped", "forming", "listed", "none")
SRC_LOD = "lod"
SRC_ENTRY_5M = "entry_candle_5m_low"
ONE, FIVE = "1m", "5m"
FRAME_TEXT = {ONE: "1-minute candle", FIVE: "5-minute candle"}
RTH = "rth"
STAMP_FMT = "%Y-%m-%d %H:%M"
CONFLUENCE_KEYS = ("ema9", "ema21", "ema50", "ema150")          # daily.FACT_KEYS' EMA names (E8: 9/21/50/150)
CONFLUENCE_TAIL = "prior high and gap not computed · anchored VWAP not computed (HIS CALL #7)"
NO_PLAN_REASON = "no plan — the stop sits at or above the trigger"
ADR_UNKNOWN_WHY = "ADR unknown — the half-ADR cap not judged"


# ── listing words (built from the constants at call time) ─────────────────────────────────────────────────────────
def chase_why() -> str:
    return f"more than {LC.LUK_NO_CHASE_PCT:g}% above the low of day — his no-chase rule"


def window_why() -> str:
    return f"broke after his candle window (first {LC.LUK_TRIGGER_WINDOW_END_MIN:g} minutes)"


def _wide_max_why(risk: float) -> str:
    return f"stop too wide by his rule — {risk:.1f}% > {LC.LUK_STOP_MAX_PCT:g}% of the trigger"


def _wide_adr_why(risk: float, adr: float) -> str:
    return (f"stop too wide by his rule — {risk:.1f}% > half the {LC.LUK_ADR_SESSIONS:g}-day ADR "
            f"({adr * LC.LUK_STOP_ADR_FRAC:.1f}%)")


# ── stamps and clocks (ET close stamps "%Y-%m-%d %H:%M"; compare as strings) ─────────────────────────────────────
def _stamp(x) -> Optional[str]:
    """Any bar-time spelling → the ET stamp "%Y-%m-%d %H:%M": a stamp string, an ISO string ("…T09:32:00-05:00"), an
    aware datetime (→ ET) or a naive one (read as ET). None / unparseable → None."""
    if isinstance(x, str):
        if len(x) < 16:
            return None
        try:
            x = datetime.fromisoformat(x)
        except ValueError:
            try:
                x = datetime.strptime(x[:16], STAMP_FMT)
            except ValueError:
                return None
    if isinstance(x, datetime):
        return LB._stamp(x)
    return None


def _dt(stamp: str) -> datetime:
    return datetime.strptime(stamp[:16], STAMP_FMT)


def _tod(stamp: str) -> dtime:
    return _dt(stamp).time()


def _shift(stamp: str, minutes: float) -> str:
    return (_dt(stamp) + timedelta(minutes=minutes)).strftime(STAMP_FMT)


def _open_plus(minutes: float) -> dtime:
    return (datetime.combine(date.min, ET_RTH_OPEN) + timedelta(minutes=minutes)).time()


def _hm(stamp: Optional[str]) -> str:
    return stamp[11:16] if stamp else ""


def _frame_minutes(tf: str) -> int:
    return int(tf[:-1])


def _bar_open(stamp: str, tf: str) -> str:
    return _shift(stamp, -_frame_minutes(tf))


def is_fresh_1m(break_close_t, prev_through_1m) -> bool:
    """C1: the 1-minute break bar closed AFTER the previous Luk pass's latest closed 1-minute bar (None → True)."""
    prev = _stamp(prev_through_1m)
    if prev is None:
        return True
    b = _stamp(break_close_t)
    return b is not None and b > prev


# ── frames ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _frame(F, tf):
    by = getattr(F, "by", None) or {}
    return by.get(tf)


def _today_rth(fr) -> list:
    if fr is None:
        return []
    return [i for i in fr.today if fr.session[i] == RTH] if fr.session else list(fr.today)


def _last_idx_at_or_before(fr, stamp: str) -> int:
    """The index of the last bar of `fr` closing at or before `stamp` (−1 when none)."""
    k = -1
    for i, t in enumerate(fr.t):
        if t <= stamp:
            k = i
        else:
            break
    return k


def _latest_stamp(F) -> Optional[str]:
    f1 = _frame(F, ONE)
    if f1 is not None and len(f1.t):
        return f1.t[-1]
    f5 = _frame(F, FIVE)
    return f5.t[-1] if f5 is not None and len(f5.t) else None


def _low(F, through_t) -> Optional[float]:
    return LB.rth_low(F, through_t)


def _high(F, through_t) -> Optional[float]:
    return LB.rth_high(F, through_t)


def _entry_low_5m(F, break_t: str, tf: str) -> Optional[float]:
    """S4's "5 minute entry candle low" judged THROUGH the break bar (C7): a 5-minute break bar → its own low; a
    1-minute break bar → the low of its 5-minute bucket's 1-minute bars that closed at or before the break bar."""
    if tf == FIVE:
        f5 = _frame(F, FIVE)
        k = f5.t.index(break_t) if f5 is not None and break_t in f5.t else -1
        return f5.l[k] if k >= 0 else None
    f1 = _frame(F, ONE)
    if f1 is None:
        return None
    step = _frame_minutes(FIVE)
    d = _dt(break_t)
    mins = (d.hour * 60 + d.minute - 1) // step * step                 # the 5-minute bucket the break minute opened in
    b_open = d.replace(hour=mins // 60, minute=mins % 60).strftime(STAMP_FMT)
    lows = [f1.l[i] for i in f1.today if b_open < f1.t[i] <= break_t]
    return min(lows) if lows else None


def _stop_touched_after(F, break_t: str, stop) -> bool:
    """A later CLOSED regular-session 1-minute bar (after the break bar's close) printed a low at or under the stop."""
    f1 = _frame(F, ONE)
    if f1 is None or stop is None:
        return False
    return any(f1.t[i] > break_t and _D(f1.l[i]) <= _D(stop) for i in _today_rth(f1))


# ── the engines named by the spec ──────────────────────────────────────────────────────────────────────────────────
def stop_plan(trigger, lod, entry_low_5m, adr20_pct) -> dict:
    """S3: stop = the low of day; S4: entry-to-LOD > LUK_LOD_SWITCH_PCT % → the 5-minute entry candle low; then S2:
    too wide when risk > LUK_STOP_MAX_PCT % of the trigger or > LUK_STOP_ADR_FRAC × the 20-day ADR (exactly at a cap
    is NOT too wide; ADR unknown → only the % cap is judged). `too_wide` None when no stop exists yet."""
    out = {"stop": None, "stop_src": None, "risk_pct": None, "r_usd": None, "too_wide": None, "why": None}
    if trigger is None or lod is None or trigger <= 0:
        return out
    t = _D(trigger)
    stop, src = lod, SRC_LOD
    if (t - _D(lod)) / t * 100 > _D(LC.LUK_LOD_SWITCH_PCT):
        stop, src = entry_low_5m, SRC_ENTRY_5M
    out["stop_src"] = src
    if stop is None:
        return out
    out["stop"] = float(stop)
    plan, r = plan_of(trigger, stop)
    if plan != "ok":
        return out
    risk_d = (t - _D(stop)) / t * 100
    out["r_usd"] = r
    out["risk_pct"] = float(risk_d)
    if risk_d > _D(LC.LUK_STOP_MAX_PCT):
        out["too_wide"], out["why"] = True, _wide_max_why(float(risk_d))
    elif adr20_pct is not None and risk_d > _D(adr20_pct) * _D(LC.LUK_STOP_ADR_FRAC):
        out["too_wide"], out["why"] = True, _wide_adr_why(float(risk_d), float(adr20_pct))
    else:
        out["too_wide"] = False
        out["why"] = ADR_UNKNOWN_WHY if adr20_pct is None else None
    return out


def chase(trigger, lod) -> bool:
    """E4: the trigger sits more than LUK_NO_CHASE_PCT % above the low of day (exactly at it → False)."""
    if trigger is None or lod is None or lod <= 0:
        return False
    return (_D(trigger) / _D(lod) - 1) * 100 > _D(LC.LUK_NO_CHASE_PCT)


def flush(F, through_t) -> dict:
    """E2 / C8: for each of today's regular-session 5-minute bars closed at or before `through_t` (None = every closed
    bar), its OWN hourly reference = `bars.hourly_ref(F, before_t = that bar's OPEN)`; touched = a bar's low at or under
    its reference 9 EMA; touch_bar_t = the first such bar; depth_pct = (the touch bar's ref 9 EMA − the low of day through
    `through_t`) / that 9 EMA × 100; below_21 = that low under the touch bar's ref 21 EMA — a FACT, never a gate."""
    out = {"touched": False, "touch_bar_t": None, "touch_idx": None, "depth_pct": None, "below_21": None,
           "ref": None}
    f5 = _frame(F, FIVE)
    if f5 is None:
        return out
    through = _stamp(through_t)
    for i in _today_rth(f5):
        if through is not None and f5.t[i] > through:
            break
        ref = LB.hourly_ref(F, _bar_open(f5.t[i], FIVE))
        e9 = (ref or {}).get("ema9")
        if e9 is None:
            continue
        if _D(f5.l[i]) <= _D(e9):
            out.update(touched=True, touch_bar_t=f5.t[i], touch_idx=i, ref=ref)
            break
    if not out["touched"]:
        return out
    lod = _low(F, through)
    e9, e21 = out["ref"].get("ema9"), out["ref"].get("ema21")
    if lod is not None and e9:
        out["depth_pct"] = float((_D(e9) - _D(lod)) / _D(e9) * 100)
    if lod is not None and e21 is not None:
        out["below_21"] = lod < e21
    return out


def confluence(facts, lod, day_high) -> dict:
    """E8: how many of his daily EMAs (9 / 21 / 50 / 150) today's range touched (lod ≤ EMA ≤ day high). Prior highs, the
    gap and the anchored VWAP are not computed (HIS CALL #7)."""
    touched = []
    facts = facts or {}
    if lod is not None and day_high is not None:
        for key in CONFLUENCE_KEYS:
            v = facts.get(key)
            if v is not None and lod <= v <= day_high:
                touched.append(f"{key[3:]} EMA")
    n = len(touched)
    head = f"{n} of his levels touched today" + (f": {', '.join(touched)}" if touched else "")
    return {"n": n, "touched": touched, "text": f"{head} · {CONFLUENCE_TAIL}"}


def first_break_after(frame, start_idx: int, level_fn: Callable, *, window_end_et: Optional[dtime] = None
                      ) -> Optional[int]:
    """The first bar j > start_idx of TODAY's regular session with high > level_fn(j) (level_fn → None skips bar j) and
    a close time ≤ `window_end_et` (None = no window end). The frame holds closed bars only."""
    if frame is None:
        return None
    for j in _today_rth(frame):
        if j <= start_idx:
            continue
        if window_end_et is not None and _tod(frame.t[j]) > window_end_et:
            break
        lvl = level_fn(j)
        if lvl is not None and _D(frame.h[j]) > _D(lvl):
            return j
    return None


# ── Read builders ──────────────────────────────────────────────────────────────────────────────────────────────────
def _blank(setup: str, F) -> dict:
    return {"setup": setup, "state": "none", "reason": "", "frame": None, "trigger": None, "stop": None,
            "stop_src": None, "risk_pct": None, "r_usd": None, "entry_bar_t": None,
            "as_of_bar_t": _latest_stamp(F), "lod": None, "criteria": [],
            "facts": {"flush_depth_pct": None, "touch_bar_t": None, "below_21": None, "confluence_n": None,
                      "confluence_text": None, "window_text": None, "frame_text": None},
            "listed_why": None}


def crit(key: str, label: str, ok, value: str, need: str) -> dict:
    return {"key": key, "label": label, "ok": ok, "value": value, "need": need}


def _px(x) -> str:
    return "—" if x is None else f"{x:.2f}"


def _window_text(switch_min, window_min) -> str:
    one_end = _open_plus(switch_min).strftime("%H:%M")
    if window_min is None:
        return (f"any regular-session time — 1-minute candles to {one_end} ET, then 5-minute; no window end "
                f"({LC.LUK_PDH_WINDOW})")
    end = _open_plus(window_min).strftime("%H:%M")
    return (f"his candle window: 1-minute candles to {one_end} ET, then 5-minute to {end} ET "
            f"(first {window_min:g} minutes)")


def _find_break(F, *, start1: int, start5: int, level1: Callable, level5: Callable, switch_min) -> tuple:
    """(tf, j) — the first break on the 1-minute frame among bars `frame_for_close` gives "1m", else on the 5-minute
    frame among the bars it does not (a 5-minute break after the window is still FOUND — listed, never hidden)."""
    f1, f5 = _frame(F, ONE), _frame(F, FIVE)

    def on1(j):
        return level1(j) if LB.frame_for_close(_tod(f1.t[j]), switch_min=switch_min) == ONE else None

    def on5(j):
        return level5(j) if LB.frame_for_close(_tod(f5.t[j]), switch_min=switch_min) != ONE else None

    j = first_break_after(f1, start1, on1) if f1 is not None else None
    if j is not None:
        return ONE, j
    j = first_break_after(f5, start5, on5) if f5 is not None else None
    return (FIVE, j) if j is not None else (None, None)


def _armed(F, switch_min) -> tuple:
    """(tf, idx) of the bar whose high a NEXT bar must take out: the latest closed 1-minute bar while the next 1-minute
    close is still on the 1-minute frame, else the latest closed 5-minute bar."""
    f1, f5 = _frame(F, ONE), _frame(F, FIVE)
    if f1 is not None and len(f1.t):
        nxt = _shift(f1.t[-1], _frame_minutes(ONE))
        if LB.frame_for_close(_tod(nxt), switch_min=switch_min) == ONE:
            return ONE, len(f1.t) - 1
    if f5 is not None and len(f5.t):
        return FIVE, len(f5.t) - 1
    return None, None


def _judge_break(r: dict, F, facts, *, tf: str, j: int, trigger: float, prev_through_1m, switch_min,
                 window_min, crit_head: list, break_label: str) -> dict:
    """A break on frame `tf` at bar j over `trigger`: every lookback through the break bar's close (C7), the stop plan
    (S3 → S4 → S2), the listing rules (E4, S2, the window), then the frame's freshness rule (C1)."""
    fr = _frame(F, tf)
    bt = fr.t[j]
    lod = _low(F, bt)
    day_high = _high(F, bt)
    adr = (facts or {}).get("adr20_pct")
    plan = stop_plan(trigger, lod, _entry_low_5m(F, bt, tf), adr)
    r.update(frame=tf, trigger=float(trigger), entry_bar_t=bt, lod=lod, stop=plan["stop"], stop_src=plan["stop_src"],
             risk_pct=plan["risk_pct"], r_usd=plan["r_usd"], as_of_bar_t=fr.t[-1])
    r["facts"]["frame_text"] = FRAME_TEXT[tf]
    cf = confluence(facts, lod, day_high)
    r["facts"]["confluence_n"], r["facts"]["confluence_text"] = cf["n"], cf["text"]
    in_window = (True if window_min is None
                 else LB.frame_for_close(_tod(bt), switch_min=switch_min) is not None)
    chased = chase(trigger, lod)
    dist = float((_D(trigger) / _D(lod) - 1) * 100) if lod else None
    crits = list(crit_head)
    crits.append(crit("trigger_break", break_label, True,
                      f"broke {_px(trigger)} on the {FRAME_TEXT[tf]} closing {_hm(bt)} ET", break_label))
    if window_min is not None:
        crits.append(crit("in_window", f"inside his candle window (first {window_min:g} minutes)", in_window,
                          f"closed {_hm(bt)} ET", f"a break closing by {_open_plus(window_min).strftime('%H:%M')} ET"))
    crits.append(crit("no_chase", f"within {LC.LUK_NO_CHASE_PCT:g}% of the low of day", not chased,
                      "—" if dist is None else f"{dist:.1f}% above the low of day {_px(lod)}",
                      f"a trigger at most {LC.LUK_NO_CHASE_PCT:g}% above the low of day"))
    wide = plan["too_wide"]
    crits.append(crit("stop_width",
                      f"stop within {LC.LUK_STOP_MAX_PCT:g}% and half the {LC.LUK_ADR_SESSIONS:g}-day ADR",
                      None if wide is None else not wide,
                      "—" if plan["risk_pct"] is None else (f"{plan['risk_pct']:.1f}% risk"
                                                            + (f" · {plan['why']}" if plan["why"] else "")),
                      f"a stop at most {LC.LUK_STOP_MAX_PCT:g}% under the trigger and inside half the ADR"))
    r["criteria"] = crits
    if plan["stop"] is not None and plan["r_usd"] is None:
        r["state"], r["reason"] = "none", NO_PLAN_REASON
        return r
    if chased:
        r["state"], r["listed_why"] = "listed", chase_why()
    elif wide is True:
        r["state"], r["listed_why"] = "listed", plan["why"]
    elif not in_window:
        r["state"], r["listed_why"] = "listed", window_why()
    if r["state"] == "listed":
        return r
    if wide is None or any(c["ok"] is not True for c in crits):
        r["state"], r["reason"] = "none", "not judgeable — " + ", ".join(c["key"] for c in crits if c["ok"] is not True)
        return r
    if _stop_touched_after(F, bt, plan["stop"]):
        r["state"] = "stopped"
    elif tf == ONE:
        r["state"] = "aplus" if is_fresh_1m(bt, prev_through_1m) else "triggered"
    else:
        r["state"] = "aplus" if j == len(fr.t) - 1 else "triggered"
    return r


def _forming(r: dict, F, facts, *, level: float, tf: str, crit_head: list, break_label: str, need: str) -> dict:
    """Context met, no break yet: the armed level is served with the stop it would carry today (through the latest
    closed bar — `rth_low(F)` with no through_t)."""
    lod = _low(F, None)
    plan = stop_plan(level, lod, None, (facts or {}).get("adr20_pct"))
    r.update(state="forming", frame=tf, trigger=float(level), lod=lod, stop=plan["stop"], stop_src=plan["stop_src"],
             risk_pct=plan["risk_pct"], r_usd=plan["r_usd"])
    r["facts"]["frame_text"] = FRAME_TEXT.get(tf)
    cf = confluence(facts, lod, _high(F, None))
    r["facts"]["confluence_n"], r["facts"]["confluence_text"] = cf["n"], cf["text"]
    r["criteria"] = list(crit_head) + [crit("trigger_break", break_label, False, f"{_px(level)} armed", need)]
    return r


# ── the three setups ───────────────────────────────────────────────────────────────────────────────────────────────
def pullback_reversal(F, facts, session_iso, *, prev_through_1m=None) -> dict:
    """↩️ E1 + E2 + E5: the low of day at or under the PRIOR close's daily 9 EMA, a flush of a 5-minute low into the
    hourly 9 EMA, then the first bar after the touch whose high takes out the previous bar's high — never a bar before
    the low ("I generally won't buy the dip on the way down")."""
    setup = "pullback_reversal"
    r = _blank(setup, F)
    switch, window = LC.LUK_ONE_MIN_UNTIL_MIN, LC.LUK_TRIGGER_WINDOW_END_MIN
    r["facts"]["window_text"] = _window_text(switch, window)
    facts = facts or {}
    ema_key = f"ema{LC.LUK_PULLBACK_DAILY_EMA}"
    e9d = facts.get(ema_key)
    if e9d is None:
        r["reason"] = f"no daily {LC.LUK_PULLBACK_DAILY_EMA} EMA — daily facts not ready"
        return r
    fl = flush(F, None)
    if not fl["touched"]:
        r["reason"] = "no flush into the hourly 9 EMA today"
        return r
    f1, f5 = _frame(F, ONE), _frame(F, FIVE)
    touch_t = fl["touch_bar_t"]
    touch_open = _bar_open(touch_t, FIVE)
    start1 = _last_idx_at_or_before(f1, touch_t) if f1 is not None else -1
    start5 = fl["touch_idx"]

    def level1(j):
        prior = [f1.l[k] for k in range(j) if f1.t[k] > touch_open and f1.session[k] == RTH and k >= f1.today.start]
        if j - 1 < 0 or not prior or _D(f1.l[j]) < _D(min(prior)):
            return None                                         # the bar making the low — never on the way down
        return f1.h[j - 1]

    def level5(j):
        prior = [f5.l[k] for k in range(start5, j)]
        if not prior or _D(f5.l[j]) < _D(min(prior)):
            return None
        return f5.h[j - 1]

    tf, j = _find_break(F, start1=start1, start5=start5, level1=level1, level5=level5, switch_min=switch)
    label = "broke the previous bar's high after the low"
    through_t = _frame(F, tf).t[j] if tf else _latest_stamp(F)
    fl_b = flush(F, through_t)
    r["facts"].update(flush_depth_pct=fl_b["depth_pct"], touch_bar_t=fl_b["touch_bar_t"], below_21=fl_b["below_21"])
    lod_b = _low(F, through_t if tf else None)
    pulled = None if lod_b is None else _D(lod_b) <= _D(e9d)
    head = [crit("daily_pullback_9", f"pulled back to the daily {LC.LUK_PULLBACK_DAILY_EMA} EMA", pulled,
                 f"low {_px(lod_b)} vs daily {LC.LUK_PULLBACK_DAILY_EMA} EMA {_px(e9d)}",
                 f"a low at or under the daily {LC.LUK_PULLBACK_DAILY_EMA} EMA ({_px(e9d)})"),
            crit("hourly_touch", "flushed into the hourly 9 EMA", True,
                 f"touched at {_hm(fl_b['touch_bar_t'])} ET"
                 + ("" if fl_b["depth_pct"] is None else f" · {fl_b['depth_pct']:.1f}% below it")
                 + (" · under the hourly 21 EMA too" if fl_b["below_21"] else ""),
                 "a 5-minute low at or under the hourly 9 EMA")]
    if pulled is not True:
        r["criteria"] = head
        r["reason"] = f"the low of day has not reached the daily {LC.LUK_PULLBACK_DAILY_EMA} EMA"
        r["lod"] = lod_b
        return r
    if tf is None:
        atf, k = _armed(F, switch)
        if atf is None:
            r["reason"] = "no closed bar to arm"
            return r
        return _forming(r, F, facts, level=_frame(F, atf).h[k], tf=atf, crit_head=head, break_label=label,
                        need="a bar taking out the previous bar's high")
    return _judge_break(r, F, facts, tf=tf, j=j, trigger=_frame(F, tf).h[j - 1], prev_through_1m=prev_through_1m,
                        switch_min=switch, window_min=window, crit_head=head, break_label=label)


def opening_range_high(F, facts, session_iso, *, prev_through_1m=None) -> dict:
    """🔔 E6: the first 1-minute candle after the open sets the opening range high (its low = the low of day then);
    the first take-out of that high — 1-minute bars until the LUK_ORH_SWITCH_MIN close, then 5-minute — inside the
    window; stop at the low of day through the break bar (S4 switch to the 5-minute entry candle low)."""
    setup = "opening_range_high"
    r = _blank(setup, F)
    switch, window = LC.LUK_ORH_SWITCH_MIN, LC.LUK_TRIGGER_WINDOW_END_MIN
    r["facts"]["window_text"] = _window_text(switch, window)
    f1, f5 = _frame(F, ONE), _frame(F, FIVE)
    first_t = f"{session_iso} {_open_plus(LC.LUK_ORH_CANDLE_MIN).strftime('%H:%M')}"
    k0 = f1.t.index(first_t) if f1 is not None and first_t in f1.t else -1
    if k0 < 0:
        r["reason"] = "no first 1-minute candle yet"
        return r
    orh = f1.h[k0]
    head = [crit("first_candle", "the first 1-minute candle after the open", True,
                 f"high {_px(orh)} · low {_px(f1.l[k0])}", "the 09:30 candle")]
    start5 = _last_idx_at_or_before(f5, first_t) if f5 is not None else -1
    tf, j = _find_break(F, start1=k0, start5=start5, level1=lambda _j: orh, level5=lambda _j: orh,
                        switch_min=switch)
    label = "took out the opening range high"
    if tf is None:
        atf = ONE if _armed(F, switch)[0] == ONE else FIVE
        return _forming(r, F, facts, level=orh, tf=atf, crit_head=head, break_label=label,
                        need=f"a bar taking out {_px(orh)}")
    return _judge_break(r, F, facts, tf=tf, j=j, trigger=orh, prev_through_1m=prev_through_1m, switch_min=switch,
                        window_min=window, crit_head=head, break_label=label)


def inside_day_pdh(F, facts, session_iso, *, prev_through_1m=None) -> dict:
    """📦 E7: yesterday an inside day (facts, strict), today the first regular-session take-out of yesterday's high —
    1-minute candles until LUK_ONE_MIN_UNTIL_MIN, then 5-minute; no window end (LUK_PDH_WINDOW)."""
    setup = "inside_day_pdh"
    r = _blank(setup, F)
    switch = LC.LUK_ONE_MIN_UNTIL_MIN
    r["facts"]["window_text"] = _window_text(switch, None)
    facts = facts or {}
    inside, pdh = facts.get("inside_day"), facts.get("prev_high")
    if inside is not True or pdh is None:
        r["reason"] = ("daily facts not ready" if inside is None or pdh is None
                       else "yesterday was not an inside day")
        return r
    head = [crit("inside_day", "yesterday an inside day", True,
                 f"high {_px(pdh)} · low {_px(facts.get('prev_low'))} inside the day before",
                 "a high under and a low over the day before")]
    tf, j = _find_break(F, start1=-1, start5=-1, level1=lambda _j: pdh, level5=lambda _j: pdh, switch_min=switch)
    label = "took out the prior-day high"
    if tf is None:
        atf = ONE if _armed(F, switch)[0] == ONE else FIVE
        return _forming(r, F, facts, level=pdh, tf=atf, crit_head=head, break_label=label,
                        need=f"a bar taking out {_px(pdh)}")
    return _judge_break(r, F, facts, tf=tf, j=j, trigger=pdh, prev_through_1m=prev_through_1m, switch_min=switch,
                        window_min=None, crit_head=head, break_label=label)


DETECTORS = {"pullback_reversal": pullback_reversal, "opening_range_high": opening_range_high,
             "inside_day_pdh": inside_day_pdh}


def read_all(F, facts, session_iso, *, prev_through_1m=None) -> dict:
    """{setup: Read} in LC.SETUPS order; a detector that raises reads `none` with its reason (never a crash)."""
    out = {}
    for setup in LC.SETUPS:
        try:
            out[setup] = DETECTORS[setup](F, facts, session_iso, prev_through_1m=prev_through_1m)
        except Exception as exc:                                # noqa: BLE001
            log.warning("luk detector %s failed: %s", setup, exc)
            r = _blank(setup, F)
            r["reason"] = f"read failed: {type(exc).__name__}"
            out[setup] = r
    return out


__all__ = ["STATES", "SRC_LOD", "SRC_ENTRY_5M", "FRAME_TEXT", "stop_plan", "chase", "flush", "confluence",
           "first_break_after", "pullback_reversal", "opening_range_high", "inside_day_pdh", "read_all",
           "is_fresh_1m", "chase_why", "window_why", "crit"]
