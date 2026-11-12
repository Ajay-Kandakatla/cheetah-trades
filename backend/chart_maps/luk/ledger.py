"""🏁 Luk's Track record — every 🥇 A+ that rang (live) or was recorded (shadow), graded by LUK's trade math (BUILD_SPEC
§3.9, WP-B, 2026-11-01; both states since the go-live 2026-11-01).

Ajay 2026-11-01: "look at other winners of US stocks champion ship and pic the next best one like Gajjala. Implement
their strategy please if they have online resources."

ROWS. Every `luk_alerts` claim in ROW_STATES (= gajjala.store.LEDGER_ALERT_STATES) dated on or after LC.LUK_RECORD_FROM:
a SHADOW claim (`SHADOW:LUK:{date}|SYM|setup`, state "shadow" — recorded, never sent) or, since the go-live (Ajay
2026-11-01: "Lets make it live. also alerts too."), a LIVE claim (`LUK:{date}|SYM|setup`, state "pushed" — it reached his
phone). Each row carries its own `line` (gajjala.ledger.LINES words: "live" / "shadow") and its own `push_state`. Never a
`#state` refusal, a claim in flight ("claimed"), a "failed" / "no_target" settle, or a doc dated before the record.

THE TRADE MATH (his words where he gave them; the rest is a Cheetah choice, listed as a HIS CALL):
- FILL — the house convention of 🚩's 🏁 (gajjala/ledger.py `grade`, re-implemented here and pinned equal on a shared
  fixture by tests/test_luk_ledger.py): the first 1-minute bar starting at least BAR_SETTLE_SEC after the alert, ET
  start time in [LUK_FILL_FROM_ET, min(LUK_FILL_TO_ET, that day's regular close)), whose high ≥ the trigger → fill =
  max(trigger, that bar's open). Same session only (HIS CALL #16); none → "no entry".
- STOP — the alert's stop, a TOUCH (low ≤ stop) → exit at the stop, r = (stop − fill) / R, measured from the actual
  fill (2026-11-11; −1.0 only when the fill is the trigger, lower when the fill bar opened above it); the fill minute
  counts; a bar that touches the stop and a target high → the stop wins (GG's Q0).
- EXIT — the first daily CLOSE below the daily 9 EMA (VKNEJA5r8zw 2:29:17 "I closed this trade on the first close um
  below the 9 EMA") → exit at that close, r = (close − fill) / R. No maximum hold (HIS CALL #11).
- 3R / 5R — his partials (VKNEJA5r8zw 2:27:37, LC.LUK_PARTIAL_R) are FLAGS when a high AFTER the fill minute reaches
  fill + mR; never applied (HIS CALL #5).
R = trigger − stop (the alert's own plan, gajjala.ledger.plan_of).

CLOSED DAYS — ONLY through `daily.closed_through` ([fixed: C2, C9]): Luk's OWN post-close fetch, ONE counted load
inside `max_loads` (minute + daily) per call; the house cache is never read. A day that has not closed + settled
(`daily.trusted_through(now, d)` false — pure, no read, no fetch) → `not_settled`; a fetch refused by the cap →
`deferred_cap`; a fetch that brings no frame / no bar dated that day → `deferred_daily`. Each is deferred ("not graded
yet") and retried on the next call with a fresh fetch — never frozen, never a half-session close.
REFIX 2026-11-01 (WP-A2 follow-up): the grader no longer reads the house daily cache anywhere (its `cached_at` is
re-stamped by `patch_latest_closes`, so it proves nothing about the bar dated `d`); the old `untrusted` step counter
(the house-cache stamp rule) is replaced by `not_settled`; `graded_from.daily_cached_at` = the fetch time.

Writes: ONLY `grade_step` writes, into luk_ledger. `served_block` reads Mongo only. Operational accounting of alerts as
recorded (live and shadow), never a backtest; UNMEASURED.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from typing import Callable, Optional

from catalysts.medical.reaction import is_market_day, next_market_day, prev_market_day, rth_close_time
from chart_maps.gajjala import alerts as GA
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as GS
from chart_maps.gajjala import variant as V
from chart_maps.gajjala.ledger import (ET, LINES, SETTLE, UTC, _D, _aware, _default_load_day, _iso_t, _num, _px,
                                       bars_from_frame, plan_of, rang_of)
# 🏁 like 🚩's + 🔁 one count per stock per day (Ajay 2026-11-02, spec luk-track §3.3.2): the 🚩 served-block words and
# helpers and THE one dedupe engine, imported never retyped (GG's RANG_TEXT / NO_TIME_TEXT are aliased: this module's
# own names keep their meaning — the long rang sentence on the tape read line, the "not graded" fill word)
from chart_maps.gajjala.ledger import (APLUS_CHART_KEYS, APLUS_CHART_TITLES, BUCKET_TEXT, BUCKETS, CATEGORY_EMPTY_TEXT,
                                       CATEGORY_PARAM, DUP_RULE_TEXT, DUP_TEXT, FLAG_BUCKETS, KIND_TEXT,
                                       SORT_KEYS, SORT_PARAM, _aplus_cell, _categories, _counts_blank, _counts_text,
                                       _dow_md, _plural, _sorts, _win_pct, dedupe_trades, dup_count_text)
from chart_maps.gajjala.ledger import NO_TIME_TEXT as GG_NO_TIME_TEXT
from chart_maps.gajjala.ledger import RANG_TEXT as GG_RANG_TEXT
from daytrading.data import ET_RTH_OPEN

from . import constants as LC
from . import daily as DL
from . import variant as VL
from .variant import LUK

log = logging.getLogger("chart_maps.luk.ledger")

ROW_ID = "{date}|{SYM}|{setup}|aplus"
KIND = "aplus"
EXITS = ("stop", "ema9_close")
OPEN = "open"
STATE_SHADOW = "shadow"
STATE_PUSHED = "pushed"                                          # 2026-11-01 go-live: a live claim that rang
ROW_STATES = (STATE_SHADOW, STATE_PUSHED)                        # = gajjala.store.LEDGER_ALERT_STATES (pinned equal)
LINE_OF = {STATE_SHADOW: LINES[1], STATE_PUSHED: LINES[0]}       # GG's 🏁 line words ("shadow" / "live"), never retyped
PLAN_OK, NO_PLAN, NO_RISK = "ok", "no_plan", "no_risk"            # gajjala.ledger.plan_of's answers
FILLED, NO_ENTRY = "filled", "no_entry"
FINAL_ENTRIES = (NO_ENTRY, NO_PLAN, NO_RISK)
# the only top-level keys a luk_ledger doc carries (the GG store's upsert_ledger guards GG's own keys — Luk writes its
# own shape through `_write`, which refuses any other key)
LEDGER_KEYS = frozenset({"date", "symbol", "setup", "kind", "alert", "fill", "walk", "graded_at", "graded_from",
                         "version"})
GRADE_VERSION = LC.LUK_GRADE_VERSION   # the luk_ledger schema version (bump in constants.py to re-grade)
STEP_KEYS = ("rows", "final", "extended", "written", "not_due", "no_time", "no_entry", "deferred", "deferred_cap",
             "deferred_budget", "deferred_daily", "not_settled", "load_failed", "no_bars", "faulted")
DEFERRED_TEXT = "not graded yet — Luk's own post-close fetch brought no daily bar"   # the house cache is never read
PENDING_TEXT = "not graded yet"


class LedgerReadError(RuntimeError):
    """luk_alerts or luk_ledger could not be read — never "no A+ recorded"."""


# ── small helpers ─────────────────────────────────────────────────────────────────────────────────────────────────
def _as_date(d) -> Optional[date]:
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    try:
        return date.fromisoformat(str(d)[:10])
    except (TypeError, ValueError):
        return None


def _parse_at(v) -> Optional[datetime]:
    if isinstance(v, datetime):
        return _aware(v)
    if isinstance(v, str) and v.strip():
        try:
            return _aware(datetime.fromisoformat(v.strip().replace("Z", "+00:00")))
        except ValueError:
            return None
    return None


def record_from() -> date:
    """The first session the record reads (LC.LUK_RECORD_FROM — Ajay design #7, the deploy date)."""
    return _as_date(LC.LUK_RECORD_FROM)


def clip(sessions) -> list:
    """`sessions` (dates or ISO strings) without any session before LUK_RECORD_FROM, as dates."""
    start = record_from()
    out = []
    for s in sessions or []:
        d = _as_date(s)
        if d is not None and d >= start:
            out.append(d)
    return out


def record_sessions(today: date) -> list:
    """Every market day from LUK_RECORD_FROM through `today` (ascending)."""
    d, out = record_from(), []
    while d <= today:
        if is_market_day(d):
            out.append(d)
        d += timedelta(days=1)
    return out


def close_utc(d: date) -> datetime:
    """The regular close of `d` (16:00 ET; 13:00 on a half day — the house calendar) as aware UTC."""
    return datetime.combine(d, rth_close_time(d), tzinfo=ET).astimezone(UTC)


def row_id(date_iso: str, sym: str, setup: str) -> str:
    return ROW_ID.format(date=str(date_iso)[:10], SYM=(sym or "").upper(), setup=setup)


def _r_text(r) -> str:
    """+2.3R / −1.0R (a true minus sign)."""
    v = float(r)
    return f"{'+' if v >= 0 else '−'}{abs(v):.1f}R"


def _hhmm(iso_t) -> Optional[str]:
    t = _parse_at(iso_t)
    return t.astimezone(ET).strftime("%H:%M") if t else None


def _md(d) -> str:
    dd = _as_date(d)
    return f"{dd:%m-%d}" if dd else "—"


def _flag_key(m) -> str:
    return f"reached_{int(m)}r"


# ── rows ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def row_of(doc: dict) -> Optional[dict]:
    """A luk_alerts shadow or pushed claim → the row dict | None when the doc is not a row (a state outside ROW_STATES,
    a `#state` refusal, an id that is not the house key of its own state — the shadow key for "shadow", the claim key
    for "pushed" — of its own date / symbol / setup, a setup not his, a date before the record)."""
    state = doc.get("state") if isinstance(doc, dict) else None
    if state not in ROW_STATES:
        return None
    sym = str(doc.get("symbol") or "").upper()
    setup = doc.get("setup")
    d = _as_date(doc.get("date")) if isinstance(doc.get("date"), str) else None
    if not sym or setup not in LC.SETUPS or d is None or d < record_from():
        return None
    want = GA.shadow_key(d, sym, setup, LUK) if state == STATE_SHADOW else GA.claim_key(d, sym, setup, LUK)
    if str(doc.get("_id") or "") != want:
        return None
    at = _parse_at(doc.get("at")) or _parse_at(doc.get("claimed_at"))
    plan, r = plan_of(doc.get("trigger"), doc.get("stop"))
    t, s = _num(doc.get("trigger")), _num(doc.get("stop"))
    r_pct = round(float(_D(r) / _D(t) * 100), 4) if plan == PLAN_OK else None
    return {"id": row_id(d.isoformat(), sym, setup), "date": d.isoformat(), "symbol": sym, "setup": setup,
            "at_utc": at, "at_et": at.astimezone(ET).strftime("%H:%M") if at else None, "rang": rang_of(d, at),
            "trigger": t, "stop": s, "r_usd": r, "r_pct": r_pct, "plan": plan,
            "price_at_alert": _num(doc.get("price")), "frame": doc.get("frame"),
            "url": f"/chart-maps?tab={LUK.tab}&sub={setup}&focus={sym}", "line": LINE_OF[state],
            "push_state": state}


def _sort_key(row: dict) -> tuple:
    d = _as_date(row.get("date"))
    at = row.get("at_utc")
    order = {s: i for i, s in enumerate(LC.SETUPS)}
    return (-(d.toordinal() if d else 0), 0 if at else 1, -(at.timestamp() if at else 0.0), row.get("symbol") or "",
            order.get(row.get("setup"), len(order)))


def rows_for(sessions, store) -> list:
    """Every shadow or pushed A+ claim on these ET sessions (clipped to ≥ LUK_RECORD_FROM) as row dicts, ordered
    (date desc, at desc, symbol, SETUPS order). Raises LedgerReadError when luk_alerts cannot be read."""
    days = clip(sessions)
    if not days:
        return []
    docs = store.alert_rows(days)
    if docs is None:
        raise LedgerReadError("luk_alerts could not be read")
    out, seen = [], set()
    for doc in docs:
        try:
            row = row_of(doc)
        except Exception as exc:                                # noqa: BLE001
            log.warning("luk ledger: unreadable alert doc %s: %s", (doc or {}).get("_id"), type(exc).__name__)
            continue
        if row is None or row["id"] in seen:
            continue
        seen.add(row["id"])
        out.append(row)
    out.sort(key=_sort_key)
    return out


# ── the grader (pure) ─────────────────────────────────────────────────────────────────────────────────────────────
def fill_window(day: date) -> tuple:
    """(from, to) ET times a fill may START in on `day`: LUK_FILL_FROM_ET (09:30) to LUK_FILL_TO_ET (16:00), never past
    that day's regular close (13:00 on a half day)."""
    return LC.LUK_FILL_FROM_ET, min(LC.LUK_FILL_TO_ET, rth_close_time(day))


def fill(alert: dict, bars_1m: list) -> Optional[dict]:
    """The house fill convention (gajjala/ledger.py `grade` — pinned equal by a test): the first bar (START t) with
    t ≥ alert + BAR_SETTLE_SEC, on the alert's own session, ET start in fill_window(day), high ≥ trigger → {"entry":
    "filled", "fill_px": max(trigger, open), "fill_t", "fill_date"}. None = no entry (or no alert time / no ok plan)."""
    at = (alert or {}).get("at_utc")
    d = _as_date((alert or {}).get("date"))
    if not isinstance(at, datetime) or d is None:
        return None
    if plan_of(alert.get("trigger"), alert.get("stop"))[0] != PLAN_OK:
        return None
    start = _aware(at) + SETTLE
    lo, hi = fill_window(d)
    trig = _D(alert["trigger"])
    for b in bars_1m or []:
        t = _aware(b[0])
        if t < start:
            continue
        et = t.astimezone(ET)
        if et.date() != d or not (lo <= et.time() < hi):
            continue
        if _D(b[2]) >= trig:
            return {"entry": FILLED, "fill_px": float(max(trig, _D(b[1]))), "fill_t": _iso_t(t),
                    "fill_date": d.isoformat()}
    return None


def _blank_walk() -> dict:
    w = {"exit": None, "state": OPEN, "exit_t": None, "exit_date": None, "exit_px": None, "r": None, "r_now": None,
         "best_r": None, "sessions": 0, "through_date": None, "last_close": None}
    for m in LC.LUK_PARTIAL_R:
        w[_flag_key(m)] = False
        w[_flag_key(m) + "_t"] = None
    return w


def stop_r(trigger, stop, fill_px) -> Optional[float]:
    """The R of a stop exit, measured from the ACTUAL fill: (stop − fill) / (trigger − stop) — the same arithmetic as
    walk()'s r_of at the stop (Ajay 2026-11-11, relayed: "Do your receommendations"). None (never −1.0 by default,
    never NaN) when the plan is not ok, the fill is not a finite number, or the fill is at or under the stop
    (impossible on a graded row: fill ≥ trigger > stop)."""
    plan, r = plan_of(trigger, stop)
    f, s = _num(fill_px), _num(stop)
    if plan != PLAN_OK or f is None or s is None or f <= s:
        return None
    return round(float((_D(s) - _D(f)) / _D(r)), 4)


def walk(alert: dict, fill_: dict, days: list, prior: Optional[dict] = None) -> dict:
    """LUK's exits over `days` = [{"date", "bars" [(t_utc START, o, h, l, c)] regular-session, "close", "ema9_close"}]
    from the fill session on (or from the session after `prior`'s through_date). Per bar from the fill minute on: low ≤
    stop → exit "stop" at the stop, r = stop_r (from the fill) (the fill minute counts; a stop and a target in one bar →
    the stop). A high
    ≥ fill + mR on a bar AFTER the fill minute sets the reached_{m}r flag (first touch time kept). At each session end
    (close and ema9_close both numbers): close < ema9_close → exit "ema9_close" at that close, r = (close − fill) / R.
    A day without both daily numbers is walked intraday only (stop / flags) and never counted as a held session.
    No exit → state "open" with r_now at the last close. sessions = sessions from the fill session inclusive."""
    w = dict(prior) if isinstance(prior, dict) else _blank_walk()
    for m in LC.LUK_PARTIAL_R:
        w.setdefault(_flag_key(m), False)
        w.setdefault(_flag_key(m) + "_t", None)
    if w.get("exit") in EXITS:
        return w
    plan, r = plan_of(alert.get("trigger"), alert.get("stop"))
    if plan != PLAN_OK or not isinstance(fill_, dict) or _num(fill_.get("fill_px")) is None:
        return w
    R = _D(r)
    fpx = _D(fill_["fill_px"])
    stop = _D(alert["stop"])
    fill_t = _parse_at(fill_.get("fill_t"))
    targets = [(m, fpx + _D(m) * R) for m in LC.LUK_PARTIAL_R]

    def r_of(px) -> float:
        return round(float((_D(px) - fpx) / R), 4)

    for day in days or []:
        d = _as_date(day.get("date"))
        for b in day.get("bars") or []:
            t = _aware(b[0])
            if fill_t is not None and t < fill_t:
                continue
            if _D(b[3]) <= stop:                                # a touch; the fill minute counts; the stop wins
                w.update(exit=EXITS[0], state="stopped", exit_t=_iso_t(t), exit_date=d.isoformat() if d else None,
                         exit_px=float(stop), r=stop_r(alert.get("trigger"), alert.get("stop"), fill_.get("fill_px")),
                         r_now=None, through_date=d.isoformat() if d else None)
                w["sessions"] = int(w.get("sessions") or 0) + 1
                return w
            if fill_t is not None and t > fill_t:               # the fill minute's high never sets a flag
                for m, px in targets:
                    if not w.get(_flag_key(m)) and _D(b[2]) >= px:
                        w[_flag_key(m)] = True
                        w[_flag_key(m) + "_t"] = _iso_t(t)
                br = r_of(b[2])
                w["best_r"] = br if w.get("best_r") is None else max(float(w["best_r"]), br)
        close, ema = _num(day.get("close")), _num(day.get("ema9_close"))
        if close is None or ema is None:
            continue
        w["sessions"] = int(w.get("sessions") or 0) + 1
        w["through_date"] = d.isoformat() if d else None
        w["last_close"] = close
        w["r_now"] = r_of(close)
        if _D(close) < _D(ema):
            w.update(exit=EXITS[1], state=EXITS[1], exit_date=d.isoformat() if d else None, exit_px=close,
                     r=r_of(close), r_now=None)
            return w
    return w


# ── the grade step (inside the Luk pass) ──────────────────────────────────────────────────────────────────────────
def _rth_bars(bars: list, d: date) -> list:
    """The bars of `d` whose ET START is in [09:30, that day's regular close)."""
    hi = rth_close_time(d)
    out = []
    for b in bars or []:
        et = _aware(b[0]).astimezone(ET)
        if et.date() == d and ET_RTH_OPEN <= et.time() < hi:
            out.append(b)
    return out


def _alert_block(row: dict) -> dict:
    return {"at": _iso_t(row.get("at_utc")), "at_et": row.get("at_et"), "rang": row.get("rang"),
            "trigger": row.get("trigger"), "stop": row.get("stop"), "r_usd": row.get("r_usd"),
            "r_pct": row.get("r_pct"), "plan": row.get("plan"), "price_at_alert": row.get("price_at_alert"),
            "frame": row.get("frame"), "url": row.get("url")}


def _write(store, _id: str, body: dict) -> bool:
    """THE luk_ledger write: one `update_one({_id}, {$set}, upsert=True)` on the store's ledger handle; refused (False)
    when a key falls outside LEDGER_KEYS."""
    bad = set(body or {}) - LEDGER_KEYS
    if not body or bad or not _id:
        log.warning("luk ledger: refused write %s (keys outside LEDGER_KEYS: %s)", _id, sorted(bad))
        return False
    try:
        c = store.coll(GS.LEDGER)
        if c is None:
            return False
        c.update_one({"_id": _id}, {"$set": dict(body)}, upsert=True)
        return True
    except Exception as exc:                                    # noqa: BLE001
        log.warning("luk ledger: write failed for %s: %s", _id, exc)
        return False


def _default_fetch(sym: str):
    from sepa import prices
    return prices.load_prices(sym, "1y", force=True)


def grade_step(store, now: datetime, *, load_day: Optional[Callable] = None, fetch_daily: Optional[Callable] = None,
               max_loads: Optional[int] = None, budget_sec: Optional[float] = None,
               clock: Optional[Callable] = None, dry: bool = False) -> dict:
    """Extend every open row's walk through each session that has CLOSED (now ≥ close + BAR_SETTLE_SEC), oldest first.
    A session needs its 1-minute bars (`load_day(sym, d)` → (bars, provider_failed); memo; counted loads["minute"])
    and, unless the stop printed that day, its daily close / 9 EMA through `daily.closed_through` (Luk's own post-close
    fetch, ONE counted load; the house cache is never read). loads["minute"] + loads["daily"] never pass `max_loads`; the loop never runs past
    `budget_sec`. A row that cannot be extended is DEFERRED (counted by cause) and retried on the next call. `dry` →
    nothing written. -> the step summary (STEP_KEYS + loads, open, sessions, read_fault, dry)."""
    now = _aware(now)
    clock = clock or time.monotonic
    cap = int(LC.LUK_GRADE_MAX_LOADS if max_loads is None else max_loads)
    budget = float(LC.LUK_GRADE_BUDGET_SEC if budget_sec is None else budget_sec)
    load = load_day or _default_load_day
    fetch = fetch_daily or _default_fetch
    t0 = clock()
    today = now.astimezone(ET).date()
    sessions = record_sessions(today)
    out: dict = {k: 0 for k in STEP_KEYS}
    loads = {"daily": 0, "minute": 0}
    out.update(loads=loads, open=0, sessions=len(sessions), read_fault=False, dry=bool(dry),
               deferred_text=DEFERRED_TEXT)
    if not sessions:
        return out
    try:
        rows = rows_for(sessions, store)
    except LedgerReadError:
        out["read_fault"] = True
        return out
    stored = store.ledger_docs(sessions)
    if stored is None:
        out["read_fault"] = True
        return out
    docs = {d.get("_id"): d for d in stored if isinstance(d, dict) and d.get("_id")}
    out["rows"] = len(rows)
    memo: dict = {}

    def spent() -> int:
        return int(loads["minute"]) + int(loads["daily"])

    def minutes(sym: str, d: date) -> tuple:
        """-> (status, bars) — ok | deferred_cap | load_failed | no_bars."""
        if (sym, d) not in memo:
            if spent() >= cap:
                return "deferred_cap", None
            loads["minute"] += 1
            try:
                res = load(sym, d)
                bars, failed = res if isinstance(res, tuple) else (res, False)
                bars = bars if isinstance(bars, list) else bars_from_frame(bars)
            except Exception as exc:                            # noqa: BLE001
                log.warning("luk ledger: minute load raised for %s %s: %s", sym, d, type(exc).__name__)
                bars, failed = None, True
            memo[(sym, d)] = (bars or [], bool(failed))
        bars, failed = memo[(sym, d)]
        if failed:
            return "load_failed", None
        if not bars:
            return "no_bars", None
        return "ok", bars

    def daily_close(sym: str, d: date) -> tuple:
        """-> (facts | None, why) through daily.closed_through — Luk's OWN post-close fetch, ONE counted load, refused
        past `max_loads` (deferred_cap); the house cache is never read. `d` not closed + settled
        (`DL.trusted_through(now, d)` false — pure, no fetch attempted) → not_settled. Every other None → deferred_daily."""
        refused = {"cap": False}

        def capped_fetch(s: str):
            if spent() > cap:                                   # the load closed_through just counted would pass the cap
                loads["daily"] -= 1
                refused["cap"] = True
                return None
            return fetch(s)
        before = int(loads["daily"])
        facts = DL.closed_through(sym, d, now=now, fetch=capped_fetch, loads=loads)
        if isinstance(facts, dict) and _num(facts.get("close")) is not None \
                and _num(facts.get("ema9_close")) is not None:
            return facts, None
        if not DL.trusted_through(DL._epoch(now), d):
            return None, "not_settled"
        if refused["cap"] or (int(loads["daily"]) == before and spent() >= int(LC.LUK_GRADE_MAX_LOADS)):
            return None, "deferred_cap"
        return None, "deferred_daily"

    def defer(why: str) -> None:
        out[why] += 1
        out["deferred"] += 1

    stop_all = False
    for row in sorted(rows, key=lambda x: (x["date"], x.get("symbol") or "", x.get("setup") or "")):
        if stop_all:
            defer("deferred_budget")
            continue
        rid = row["id"]
        try:
            doc = docs.get(rid) or {}
            if doc.get("version") != GRADE_VERSION:
                doc = {}
            f = doc.get("fill") if isinstance(doc.get("fill"), dict) else None
            w = doc.get("walk") if isinstance(doc.get("walk"), dict) else None
            if (f and f.get("entry") in FINAL_ENTRIES) or (w and w.get("exit") in EXITS):
                out["final"] += 1
                continue
            body = {"date": row["date"], "symbol": row["symbol"], "setup": row["setup"], "kind": KIND,
                    "alert": _alert_block(row), "version": GRADE_VERSION}
            if row.get("plan") != PLAN_OK:
                body.update(fill={"entry": row["plan"]}, walk=None, graded_at=now.isoformat())
                out["final"] += 1
                if not dry and _write(store, rid, body):
                    out["written"] += 1
                continue
            if not isinstance(row.get("at_utc"), datetime):
                out["no_time"] += 1
                continue
            d = _as_date(row["date"]) if w is None or not w.get("through_date") else \
                next_market_day(_as_date(w["through_date"]))
            if not (d <= today and now >= close_utc(d) + SETTLE):
                out["not_due"] += 1
                if f is not None:
                    out["open"] += 1
                continue
            changed = False
            graded_from = dict(doc.get("graded_from") or {}) if isinstance(doc.get("graded_from"), dict) else {}
            while d <= today and now >= close_utc(d) + SETTLE:
                if clock() - t0 > budget:
                    stop_all = True
                    defer("deferred_budget")
                    break
                status, bars = minutes(row["symbol"], d)
                if status != "ok":
                    defer(status)
                    break
                if f is None:
                    f = fill(row, bars)
                    if f is None:
                        f = {"entry": NO_ENTRY}
                        out["no_entry"] += 1
                        changed = True
                        break
                    changed = True
                rth = _rth_bars(bars, d)
                intraday = walk(row, f, [{"date": d.isoformat(), "bars": rth, "close": None, "ema9_close": None}],
                                prior=w)
                if intraday.get("exit") == EXITS[0]:
                    w = intraday
                    out["extended"] += 1
                    changed = True
                    break
                facts, why = daily_close(row["symbol"], d)
                if facts is None:
                    defer(why)
                    break
                w = walk(row, f, [{"date": d.isoformat(), "bars": rth, "close": facts["close"],
                                   "ema9_close": facts["ema9_close"]}], prior=w)
                graded_from = {"daily_cached_at": facts.get("daily_cached_at"), "date": d.isoformat()}
                out["extended"] += 1
                changed = True
                if w.get("exit") in EXITS:
                    break
                d = next_market_day(d)
            if f is not None and f.get("entry") == FILLED and not (w and w.get("exit") in EXITS):
                out["open"] += 1
            if changed:
                body.update(fill=f, walk=w, graded_at=now.isoformat(), graded_from=graded_from or None)
                if not dry and _write(store, rid, body):
                    out["written"] += 1
        except Exception as exc:                                # noqa: BLE001
            log.warning("luk ledger: grading %s failed: %s", rid, type(exc).__name__)
            out["faulted"] += 1
    return out


# ── served words (constants-built; no dates typed here) ───────────────────────────────────────────────────────────
TITLE = "🏁 Track record — every 🥇 A+ recorded here since {from_}, graded by Luk's trade math · UNMEASURED"
RULE_TEXT = (
    "Fill = the first 1-minute bar at least {settle} s after the alert trading at or above the trigger, from the "
    "regular open — the same fill convention as 🚩's 🏁 (a Cheetah choice, for comparability). Stop = the alert's "
    "stop, a touch; the R of a stop is measured from the actual fill, so a fill above the trigger loses more than "
    "one R. Exit = the stop or the first daily close below the {ema} EMA, whichever prints first — his "
    "stated exit (VKNEJA5r8zw 2:29:17). His partials at {partials} are shown as flags, not applied (HIS CALL #5); no "
    "maximum hold — a row stays open until the exit prints (HIS CALL #11). The alert itself can print up to {lag} "
    "minutes after his bar closed (one Luk pass per {lag} minutes), so a 🏁 fill is later than his would have been — "
    "a fact (HIS CALL #29).")
HONESTY_LIVE = ("Rows are alerts that rang your phone (live) or were recorded in shadow (never sent) — each row's own "
                "line says which; since {since} every 🥇 A+ rings by your call (\"{words}\"). Operational accounting of "
                "alerts as recorded, not a backtest. UNMEASURED until the strategy lab's {floor}-entry-week floor ({n} "
                "entry weeks so far).")
HONESTY_SHADOW = ("Every row is a shadow record — none reached your phone. Operational accounting of alerts as recorded, "
                  "not a backtest. UNMEASURED until the strategy lab's {floor}-entry-week floor ({n} entry weeks so far).")
COUNTS_TEXT = ("{n} A+ recorded · {filled} filled · {stopped} stopped · {ema9} closed below the {ema} EMA · {open} open "
               "· {mean} · {entry_weeks} of {floor} entry weeks")
MEAN_TEXT = "mean {mean_r:+.2f}R over {closed} closed"
MEAN_NONE_TEXT = "no closed row yet"
EMPTY_TEXT_LIVE = "No 🥇 A+ in this span — none rang, none was recorded."
EMPTY_TEXT_SHADOW = "No 🥇 A+ recorded in this span — every A+ is recorded in shadow, never sent."
FAULT_TEXT = "The 🏁 record could not be read this time — the next re-read tries again."
FILL_TEXT = "filled {px} at {hhmm}"
NO_ENTRY_TEXT = "no entry — the trigger never traded from the regular open to the close"
NO_PLAN_TEXT = {NO_PLAN: "no plan — the alert carried no usable trigger / stop",
                NO_RISK: "no risk — trigger equals the stop"}
NO_TIME_TEXT = "no alert time on file — not graded"
EXIT_STOP_TEXT = "stopped {hhmm} · {r}"
EXIT_STOP_NO_R_TEXT = "stopped {hhmm} · R not known — the fill is missing"   # MINE (2026-11-11) — unreachable, kept visible
EXIT_EMA9_TEXT = "closed below the {ema} EMA on {md} · {r} · {sessions}"
EXIT_OPEN_TEXT = "open · {r} after {sessions}"
PLAN_TEXT = "trigger {trigger} · stop {stop} (−{pct:.1f}%) · R ${r}"
RANG_TEXT_LIVE = "rang {hhmm} ET ({when}) — sent to your phone"
RANG_TEXT_SHADOW = "recorded {hhmm} ET ({when}) — shadow, never sent"
RANG_TEXT = {LINES[0]: RANG_TEXT_LIVE, LINES[1]: RANG_TEXT_SHADOW}        # by the row's own line
RANG_WHEN = {"pre": "pre-market", "rth": "regular session", "ah": "after hours"}
RANG_NONE_TEXT = {LINES[0]: "rang — no alert time on file", LINES[1]: "recorded — no alert time on file"}

# 🏁 like 🚩's (Ajay 2026-11-02, verbatim: "Can you make Luk's track record similar to Gajjal's and also can you make sure
# you are not accounting for duplicates of the same stock as winner unless it did the same pattern again and met all the
# criteria on the same day") — spec luk-track §3.3.3: the 🚩-shaped block's Luk words (MINE unless named). Win / loss on
# 🥇 = the sign of R at Luk's own exit (HIS CALL #9); a close exactly at the fill = ➖ flat, out of the % (HIS CALL #8).
LUK_HK = "exit"                                   # MINE — the one horizon key the charts block serves (Luk has no same / next)
HEADS = (("symbol", "Ticker"), ("setup", "Setup"), ("at", "Alert"), ("kind", "Kind"),
         ("plan", "Trigger · stop · R"), ("fill", "Fill"), ("exit", "Exit · R · sessions"))
KIND_TEXT_LIVE = "🥇 A+ — sent to your phone"        # the shadow word = gajjala.ledger.KIND_TEXT[("aplus", "shadow")]
KIND_TEXT_SHADOW = KIND_TEXT[(KIND, LINES[1])]     # imported, never retyped ("A+ shadow — never sent")
OUTCOME_LABEL = "Through Luk's exit (the stop or the first daily close below the {ema} EMA)"
CHARTS_TITLE = "🥇 A+ wins vs losses — every 🥇 A+ on the span, graded by Luk's exit · UNMEASURED"
CHART_TITLES = dict(APLUS_CHART_TITLES, **{APLUS_CHART_KEYS[0]: "🥇 A+ wins vs losses"})   # 🚩's keys; the 🥇 emoji
CHARTS_LEAD = "A+ through Luk's exit"
CHARTS_SPLIT = "{sent} sent to your phone"
CHARTS_SPLIT_SHADOW = "{n} recorded in shadow (never sent)"          # joined " · " only when n > 0
CHARTS_EMPTY_TEXT = "No 🥇 A+ on this span."
CHARTS_HONESTY = ("Every 🥇 A+ on the span — sent or recorded in shadow — in one %, graded by Luk's exit: a win is a "
                  "closed row above its fill, a loss a closed row below it (a stop is one R down or more, measured "
                  "from the actual fill); open rows and a close exactly at the fill stay out of the %. Operational accounting of alerts as recorded, not a "
                  "backtest; small n. UNMEASURED.") + " " + DUP_RULE_TEXT
MORE_TEXT = "+{n} more rows — the counts above cover all {total}"
TAPE_TOGGLE_TITLE = "the full tape — the alert, the fill, the trigger / stop, the exit and the {partials} marks"


def _ema_n() -> int:
    return int(LC.LUK_PULLBACK_DAILY_EMA)


def _lag_min() -> int:
    """The Luk pass cadence in minutes (the variant's cadence constant — one pass per 5-minute tick)."""
    return int(V.cadence_sec(LUK)) // 60


def partials_text() -> str:
    """"3R and 5R" — from LC.LUK_PARTIAL_R."""
    parts = [f"{int(m)}R" for m in LC.LUK_PARTIAL_R]
    return " and ".join(parts) if len(parts) <= 2 else ", ".join(parts[:-1]) + " and " + parts[-1]


def title_text() -> str:
    return TITLE.format(from_=record_from().isoformat())


def rule_text() -> str:
    """The ⓘ text + (2026-11-02) the one-count-per-stock-per-day rule (gajjala.ledger.DUP_RULE_TEXT, imported)."""
    return (RULE_TEXT.format(settle=int(GC.BAR_SETTLE_SEC), ema=_ema_n(), partials=partials_text(), lag=_lag_min())
            + " " + DUP_RULE_TEXT)


def honesty() -> str:
    """The honesty template of the mode (luk.variant.push_mode(), read at call time)."""
    return HONESTY_LIVE if VL.push_mode() == "live" else HONESTY_SHADOW


def empty_text() -> str:
    """The empty-span sentence of the mode (read at call time)."""
    return EMPTY_TEXT_LIVE if VL.push_mode() == "live" else EMPTY_TEXT_SHADOW


def honesty_text(n_weeks: int) -> str:
    """The mode's honesty + (2026-11-02) DUP_RULE_TEXT, appended AFTER .format (his words carry no brace)."""
    return honesty().format(floor=int(LC.MEASURE_FLOOR_WEEKS), n=int(n_weeks), since=LC.LUK_LIVE_SINCE,
                            words=LC.LUK_LIVE_WORDS) + " " + DUP_RULE_TEXT


def flags_text(w: Optional[dict]) -> str:
    """"+3R reached" / "+3R and +5R reached" / ""."""
    hit = [f"+{int(m)}R" for m in LC.LUK_PARTIAL_R if isinstance(w, dict) and w.get(_flag_key(m))]
    return (" and ".join(hit) + " reached") if hit else ""


def plan_text(row: dict) -> Optional[str]:
    if row.get("plan") != PLAN_OK:
        return NO_PLAN_TEXT.get(row.get("plan"))
    return PLAN_TEXT.format(trigger=_px(row["trigger"]), stop=_px(row["stop"]), pct=float(row["r_pct"]),
                            r=f"{float(row['r_usd']):.2f}")


def rang_text(row: dict) -> str:
    """By the row's OWN line ("live" = it rang; anything else = the shadow words)."""
    line = row.get("line") if row.get("line") in RANG_TEXT else LINES[1]
    if not row.get("at_et"):
        return RANG_NONE_TEXT[line]
    return RANG_TEXT[line].format(hhmm=row["at_et"], when=RANG_WHEN.get(row.get("rang"), RANG_WHEN["rth"]))


def state_of(row: dict, doc: Optional[dict]) -> str:
    """pending | no_time | no_plan | no_risk | no_entry | stopped | ema9_close | open."""
    if row.get("plan") != PLAN_OK:
        return row.get("plan")
    if not isinstance(row.get("at_utc"), datetime):
        return "no_time"
    doc = doc if isinstance(doc, dict) and doc.get("version") == GRADE_VERSION else {}
    f = doc.get("fill") if isinstance(doc.get("fill"), dict) else None
    w = doc.get("walk") if isinstance(doc.get("walk"), dict) else None
    if f is None:
        return "pending"
    if f.get("entry") != FILLED:
        return f.get("entry") or "pending"
    if w and w.get("exit") == EXITS[0]:
        return "stopped"
    if w and w.get("exit") == EXITS[1]:
        return EXITS[1]
    return OPEN


def cells(row: dict, doc: Optional[dict]) -> dict:
    """The served row: ids, the plan / rang / fill / exit / flags texts, the state and the numbers."""
    st = state_of(row, doc)
    doc = doc if isinstance(doc, dict) and doc.get("version") == GRADE_VERSION else {}
    f = doc.get("fill") if isinstance(doc.get("fill"), dict) else {}
    w = doc.get("walk") if isinstance(doc.get("walk"), dict) else None
    if f.get("entry") == FILLED:
        fill_text = FILL_TEXT.format(px=_px(f.get("fill_px")), hhmm=_hhmm(f.get("fill_t")) or "—")
    elif st == NO_ENTRY:
        fill_text = NO_ENTRY_TEXT
    elif st in (NO_PLAN, NO_RISK):
        fill_text = NO_PLAN_TEXT[st]
    elif st == "no_time":
        fill_text = NO_TIME_TEXT
    else:
        fill_text = PENDING_TEXT
    exit_text, r = "", None
    if st == "stopped":                                       # 2026-11-11: ALWAYS from the fill, never the stored R
        r = stop_r(row.get("trigger"), row.get("stop"), f.get("fill_px"))
        hhmm = _hhmm(w.get("exit_t")) or "—"
        exit_text = (EXIT_STOP_TEXT.format(hhmm=hhmm, r=_r_text(r)) if r is not None
                     else EXIT_STOP_NO_R_TEXT.format(hhmm=hhmm))
    elif st == EXITS[1]:
        r = float(w["r"])
        exit_text = EXIT_EMA9_TEXT.format(ema=_ema_n(), md=_md(w.get("exit_date")), r=_r_text(r),
                                          sessions=_plural(int(w.get("sessions") or 0), "session", "sessions"))
    elif st == OPEN:
        if w and _num(w.get("r_now")) is not None:
            exit_text = EXIT_OPEN_TEXT.format(r=_r_text(w["r_now"]),
                                              sessions=_plural(int(w.get("sessions") or 0), "session", "sessions"))
        else:
            exit_text = PENDING_TEXT
    bucket = bucket_of(st, r)
    ft = flags_text(w)
    filled = st in ("stopped", EXITS[1], OPEN)
    at_et = row.get("at_et")
    line = row.get("line")
    return {"id": row["id"], "date": row["date"], "symbol": row["symbol"], "setup": row["setup"],
            "href": row.get("url"), "state": st, "r": r,
            "r_now": (_num(w.get("r_now")) if st == OPEN and w else None),
            "best_r": (_num(w.get("best_r")) if w else None),
            "sessions": (int(w.get("sessions") or 0) if w else 0),
            **{_flag_key(m): bool(w and w.get(_flag_key(m))) for m in LC.LUK_PARTIAL_R},
            "rang_text": rang_text(row), "plan_text": plan_text(row), "fill_text": fill_text,
            "exit_text": exit_text, "flags_text": ft, "tape_id": row["id"],
            # 🏁 like 🚩's (2026-11-02, spec luk-track §3.3.4) — additive: the 🚩 row keys the shared table reads
            "key": row["id"].replace("|", "-"), "setup_label": setup_label(row["setup"]), "kind": KIND, "line": line,
            "kind_text": KIND_TEXT_LIVE if line == LINES[0] else KIND_TEXT_SHADOW,
            "at_et": at_et,
            "at_text": f"{at_et} ET" if at_et and isinstance(row.get("at_utc"), datetime) else GG_NO_TIME_TEXT,
            "rang": row.get("rang"), "thin_text": None,
            "trigger": row.get("trigger"), "stop": row.get("stop"),
            "fill_px": _num(f.get("fill_px")) if filled else None, "note": None,
            "fill": {"state": FILLED if filled else st, "text": fill_text, "sub_text": None, "provisional": False},
            "exit": ({"state": bucket, "text": exit_text, "sub_text": ft or None, "provisional": False} if filled
                     else None),
            "bucket": bucket, "bucket_text": BUCKET_TEXT[bucket],
            "flag_text": BUCKET_TEXT[bucket] if bucket in FLAG_BUCKETS else None,
            "loss_text": None, "broker_text": None, "trader_text": None, "dup_of": None, "dup_text": None}


def setup_label(setup: str) -> str:
    """"↩️ Pullback reversal" — the setup's emoji + label from LC.SUBS (never retyped)."""
    for key, emoji, label in LC.SUBS:
        if key == setup:
            return f"{emoji} {label}".strip()
    return str(setup)


def bucket_of(state: str, r) -> str:
    """The row's ✅ / ❌ bucket (gajjala.ledger.BUCKETS words) by the sign of R at Luk's exit (HIS CALL #9): a closed row
    (stopped / ema9_close) with r > 0 → win, r < 0 (every stop is −1.0 or lower, from the fill) → loss, r == 0 → flat (HIS CALL #8); an open
    row → open; anything else (no entry / no plan / no risk / no time / pending) → out."""
    if state in ("stopped", EXITS[1]) and _num(r) is not None:
        v = float(r)
        return BUCKETS[0] if v > 0 else BUCKETS[1] if v < 0 else BUCKETS[3]
    if state == "stopped":
        return BUCKETS[1]
    if state == OPEN:
        return BUCKETS[2]
    return BUCKETS[4]


def track_row(row: dict, doc: Optional[dict]) -> dict:
    """The 🏁 table row = cells() with the SHORT E1 rang chip (gajjala.ledger.RANG_TEXT — HIS CALL #13); cells() keeps
    the long "rang HH:MM ET — sent to your phone" sentence for the tape's read line (luk/tape.py)."""
    return dict(cells(row, doc), rang_text=GG_RANG_TEXT.get(row.get("rang")))


def _trade_facts(row: dict, doc: Optional[dict]) -> Optional[dict]:
    """🔁 THE adapter (spec luk-track §3.3.5): a Luk row + its luk_ledger doc → the neutral trade facts
    gajjala.ledger.dedupe_trades reads, or None when the row is never counted (no aware ring time, plan not ok). The
    clause lives in dedupe_trades only — this never judges. group = (date, symbol, line): live and shadow are two
    ledgers, as on 🚩 (HIS CALL #18). filled: None = not graded yet, False = no entry, True = filled (fill_t);
    decided_t = the stop minute (exit "stop") or that day's regular close (exit "ema9_close"), else None (open)."""
    at = row.get("at_utc")
    if not isinstance(at, datetime) or row.get("plan") != PLAN_OK:
        return None
    doc = doc if isinstance(doc, dict) and doc.get("version") == GRADE_VERSION else {}
    f = doc.get("fill") if isinstance(doc.get("fill"), dict) else None
    w = doc.get("walk") if isinstance(doc.get("walk"), dict) else {}
    filled, fill_t, decided_t = None, None, None
    if f is not None:
        filled = f.get("entry") == FILLED
        if filled:
            fill_t = _parse_at(f.get("fill_t"))
            if w.get("exit") == EXITS[0]:
                decided_t = _parse_at(w.get("exit_t"))
            elif w.get("exit") == EXITS[1]:
                xd = _as_date(w.get("exit_date"))
                decided_t = close_utc(xd) if xd is not None else None
    order = {s: i for i, s in enumerate(LC.SETUPS)}
    return {"id": row["id"], "group": (row["date"], row["symbol"], row.get("line")), "at": _aware(at),
            "filled": filled, "fill_t": fill_t, "decided_t": decided_t, "trigger": row.get("trigger"),
            "stop": row.get("stop"), "rank": order.get(row.get("setup"), len(order))}


def counts_of(served: list, entry_weeks: int) -> tuple:
    """(counts, counts_text) over the served rows. mean_r_closed is an operational count, never a measurement.
    🔁 2026-11-02: `n` = every row given (listed); every other tally counts only the COUNTED rows (no `dup_of`);
    `dup` = the duplicates left out, named on the counts line's tail (gajjala.ledger.dup_count_text)."""
    n_all = len(served)
    served = [c for c in served if not c.get("dup_of")]
    n_dup = n_all - len(served)
    by = {k: sum(1 for c in served if c["state"] == k) for k in ("stopped", EXITS[1], OPEN, NO_ENTRY)}
    filled = by["stopped"] + by[EXITS[1]] + by[OPEN]
    closed = [c["r"] for c in served if c["state"] in ("stopped", EXITS[1]) and c.get("r") is not None]
    mean_r = round(sum(closed) / len(closed), 4) if closed else None
    out = {"n": n_all, "filled": filled, "no_entry": by[NO_ENTRY], "stopped": by["stopped"],
           "ema9_exits": by[EXITS[1]], "open": by[OPEN],
           "closed_positive": sum(1 for r in closed if r > 0), "closed_negative": sum(1 for r in closed if r < 0),
           "mean_r_closed": mean_r, "entry_weeks": int(entry_weeks), "dup": n_dup}
    for m in LC.LUK_PARTIAL_R:
        out[_flag_key(m)] = sum(1 for c in served if c.get(_flag_key(m)))
    mean = MEAN_TEXT.format(mean_r=mean_r, closed=len(closed)) if mean_r is not None else MEAN_NONE_TEXT
    out_text = COUNTS_TEXT.format(n=out["n"], filled=filled, stopped=out["stopped"], ema9=out["ema9_exits"],
                                  ema=_ema_n(), open=out["open"], mean=mean, entry_weeks=int(entry_weeks),
                                  floor=int(LC.MEASURE_FLOOR_WEEKS))
    tail = dup_count_text(n_dup)
    return out, out_text + (" · " + tail if tail else "")


def entry_weeks(served_all: list) -> int:
    """Distinct ISO weeks with a FILLED row over the whole record (the strategy lab's floor counts weeks)."""
    weeks = set()
    for c in served_all:
        if c["state"] in ("stopped", EXITS[1], OPEN):
            d = _as_date(c.get("date"))
            if d is not None:
                weeks.add(tuple(d.isocalendar()[:2]))
    return len(weeks)


def span_sessions(span: str, session: date, record: list) -> list:
    """The span's sessions (LUK_LEDGER_SPANS): today / yesterday / 5d / 10d (GC.LEDGER_SPAN_SESSIONS /
    _LONG market days through `session`) / all (every record session), clipped to the record start."""
    if span == "today":
        days = [session]
    elif span == "yesterday":
        days = [prev_market_day(session)]
    elif span in ("5d", "10d"):
        n = int(GC.LEDGER_SPAN_SESSIONS if span == "5d" else GC.LEDGER_SPAN_SESSIONS_LONG)
        days, d = [session], session
        while len(days) < n:
            d = prev_market_day(d)
            days.append(d)
    else:
        days = list(record)
    return sorted(clip(days))


def _chart_counts(rows: list) -> dict:
    """🥇 one counts dict over the COUNTED rows given (gajjala.ledger._counts_blank("same") + "flat"), tallied by the
    served bucket (win / loss / flat / open) else the fill state (no_entry / no_plan / no_risk / no_time / pending);
    thin stays 0 (no thin rule on 🥇 — HIS CALL #7). pct = gajjala.ledger._win_pct."""
    c = dict(_counts_blank("same"), flat=0)
    for r in rows:
        b = r.get("bucket")
        k = b if b in (BUCKETS[0], BUCKETS[1], BUCKETS[2], BUCKETS[3]) else r.get("state")
        if k in c and k not in ("pct", "thin"):
            c[k] += 1
    c["pct"] = _win_pct(c)
    return c


def _chart_cell(rows: list, detail: bool) -> dict:
    return _aplus_cell(_chart_counts(rows), LUK_HK, detail, mid_k="open")


def charts_block(shown: list) -> dict:
    """🥇 the GajjalaAplusCharts-shaped block (spec luk-track §3.3.7) over EVERY row on the span (never the capped
    list): every 🥇 row is an A+ (sent or shadow) in one %, by Luk's exit, under the ONE horizon key LUK_HK (no toggle:
    `horizons` empty). Duplicates (🔁) are out of every count, % and chart; `total` / `n_sent` / `n_shadow` stay row
    counts. Charts: outcomes (one bar) · by_setup (LC.SETUPS order — never by %; only setups with a counted row) ·
    by_day (dates ascending)."""
    counted = [r for r in shown if not r.get("dup_of")]
    n_dup = len(shown) - len(counted)
    n_sent = sum(1 for r in shown if r.get("line") == LINES[0])
    n_shadow = sum(1 for r in shown if r.get("line") == LINES[1])
    c = _chart_counts(counted)
    charts: list = []
    if shown:
        outcomes = {"key": APLUS_CHART_KEYS[0], "title": CHART_TITLES[APLUS_CHART_KEYS[0]],
                    "bars": [dict(_aplus_cell(c, LUK_HK, True, mid_k="open"), key=LUK_HK,
                                  label=OUTCOME_LABEL.format(ema=_ema_n()))]}
        by_s: dict = {}
        for r in counted:
            by_s.setdefault(r["setup"], []).append(r)
        by_setup = {"key": APLUS_CHART_KEYS[1], "title": CHART_TITLES[APLUS_CHART_KEYS[1]],
                    "rows": [{"key": k, "label": setup_label(k), LUK_HK: _chart_cell(by_s[k], False)}
                             for k in LC.SETUPS if k in by_s]}
        by_d: dict = {}
        for r in counted:
            by_d.setdefault(r["date"], []).append(r)
        by_day = {"key": APLUS_CHART_KEYS[2], "title": CHART_TITLES[APLUS_CHART_KEYS[2]],
                  "cols": [{"key": d_iso, "label": _dow_md(_as_date(d_iso)), LUK_HK: _chart_cell(by_d[d_iso], False)}
                           for d_iso in sorted(by_d)]}
        charts = [outcomes, by_setup, by_day]
        counts_text = {LUK_HK: _counts_text(c, "same", False, lead=CHARTS_LEAD, dup=n_dup)}
        split_text = CHARTS_SPLIT.format(sent=n_sent) + (
            " · " + CHARTS_SPLIT_SHADOW.format(n=n_shadow) if n_shadow > 0 else "")
        empty = None
    else:
        counts_text = split_text = None
        empty = CHARTS_EMPTY_TEXT
    return {"title": CHARTS_TITLE, "total": len(shown), "n_sent": n_sent, "n_shadow": n_shadow, "n_dup": n_dup,
            "counts": {LUK_HK: c}, "counts_text": counts_text, "split_text": split_text, "replayed_note": None,
            "more_text": None, "empty_text": empty, "honesty": CHARTS_HONESTY, "horizons": [],
            "horizon_default": LUK_HK, "charts": charts, "days": []}


def views_block() -> dict:
    """The served view block (gajjala.tape's words, imported lazily — tape imports the gajjala ledger): NO view toggle
    on 🥇 (`items` empty — no 🕰️ timeline), only the Tape column's head / toggle / title."""
    from chart_maps.gajjala.tape import TAPE_HEAD, TAPE_TOGGLE, VIEW_DEFAULT, VIEW_PARAM
    return {"param": VIEW_PARAM, "default": VIEW_DEFAULT, "items": [], "kinds": [KIND], "empty_text": None,
            "tape_head": TAPE_HEAD, "tape_toggle": TAPE_TOGGLE,
            "tape_toggle_title": TAPE_TOGGLE_TITLE.format(partials=partials_text())}


def mark_dups(shown: list, docs: dict, rows_by_id: dict) -> dict:
    """🔁 (spec luk-track §3.3.6 step 2) — gajjala.ledger.dedupe_trades over the rows' facts (the ONE engine); marks each
    served row in place: `dup_of` (the counted row's id), `dup_text` (its at_et / setup_label), no ✅ / ❌ flag on a
    duplicate. -> {duplicate id: counted id}."""
    facts = [_trade_facts(rows_by_id[c["id"]], docs.get(c["id"])) for c in shown if c["id"] in rows_by_id]
    dups = dedupe_trades([f for f in facts if f])
    by_id = {c["id"]: c for c in shown}
    for c in shown:
        first = by_id.get(dups.get(c["id"])) if c["id"] in dups else None
        if first is None:
            continue
        c["dup_of"] = first["id"]
        c["dup_text"] = DUP_TEXT.format(at=first.get("at_et") or GG_NO_TIME_TEXT, setup=first.get("setup_label"))
        c["flag_text"] = None
    return dups


def _days_capped(shown: list) -> tuple:
    """(days, listed) — the rows by alert date (served order: newest first), capped at LC.LUK_LEDGER_ROWS_MAX rows in
    all, the OLDEST cut first. Only the list is cut — the counts, the chips and the charts cover every row."""
    days: list = []
    listed = 0
    for c in shown:
        if listed >= int(LC.LUK_LEDGER_ROWS_MAX):
            break
        if not days or days[-1]["date"] != c["date"]:
            days.append({"date": c["date"], "label": _dow_md(_as_date(c["date"])), "rows": []})
        days[-1]["rows"].append(c)
        listed += 1
    return days, listed


def _static_keys() -> dict:
    return {"heads": [{"key": k, "label": lab} for k, lab in HEADS], "views": views_block(),
            "category_param": CATEGORY_PARAM, "category_empty_text": CATEGORY_EMPTY_TEXT, "sorts": _sorts(),
            "sort_param": SORT_PARAM, "sort_default": SORT_KEYS[0], "bucket_order": list(BUCKETS)}


def served_block(store, session, now, *, span: str = "") -> dict:
    """The 🏁 block the tab serves (Mongo only): title, rule_text, honesty, span / spans, counts + counts_text,
    days [{date, label, rows}], n_rows, empty_text, fault (+ fault_text) — and (2026-11-02, 🏁 like 🚩's) heads, views,
    categories, sorts, bucket order, more_text and the `charts` block, every row 🚩-shaped. ORDER (spec §3.3.6): every
    row on the span → 🔁 dedupe marks → counts / categories / charts over EVERY row on the span → only THEN the list is
    capped (LUK_LEDGER_ROWS_MAX, oldest cut first, more_text). n_rows = rows on the span (== counts.n; == rows listed
    under the cap)."""
    now = _aware(now)
    session = _as_date(session) or now.astimezone(ET).date()
    spans = list(LC.LUK_LEDGER_SPANS)
    span_k = span if span in spans else LC.LUK_LEDGER_SPAN_DEFAULT
    base = {"title": title_text(), "rule_text": rule_text(), "span": span_k, "spans": spans,
            "empty_text": empty_text(), "fault": False, "fault_text": None, "record_from": record_from().isoformat()}
    record = record_sessions(max(session, now.astimezone(ET).date()))
    try:
        rows = rows_for(record, store)
        docs_l = store.ledger_docs(record) if record else []
        if docs_l is None:
            raise LedgerReadError("luk_ledger could not be read")
    except LedgerReadError:
        out, text = counts_of([], 0)
        return dict(base, honesty=honesty_text(0), counts=out, counts_text=text, days=[], n_rows=0, fault=True,
                    fault_text=FAULT_TEXT, categories=_categories([]), more_text=None, charts=charts_block([]),
                    **_static_keys())
    docs = {d.get("_id"): d for d in docs_l if isinstance(d, dict)}
    served_all = [track_row(r, docs.get(r["id"])) for r in rows]
    weeks = entry_weeks(served_all)
    want = {d.isoformat() for d in span_sessions(span_k, session, record)}
    shown = [c for c in served_all if c["date"] in want]                       # (1) every row on the span
    mark_dups(shown, docs, {r["id"]: r for r in rows})                          # (2) 🔁 the one engine
    counts, text = counts_of(shown, weeks)                                      # (3) every row on the span
    categories = _categories(shown)                                             # (4) every row on the span
    charts = charts_block(shown)
    days, listed = _days_capped(shown)                                          # (5) only now the list is cut
    cut = len(shown) - listed
    more_text = MORE_TEXT.format(n=cut, total=len(shown)) if cut > 0 else None
    return dict(base, honesty=honesty_text(weeks), counts=counts, counts_text=text, days=days, n_rows=len(shown),
                categories=categories, more_text=more_text, charts=charts, **_static_keys())


__all__ = ["ROW_ID", "EXITS", "OPEN", "LEDGER_KEYS", "STATE_SHADOW", "STATE_PUSHED", "ROW_STATES", "LINE_OF", "GRADE_VERSION", "LedgerReadError", "row_id", "row_of",
           "rows_for", "fill", "fill_window", "stop_r", "walk", "grade_step", "served_block", "title_text", "rule_text",
           "honesty", "empty_text", "honesty_text", "flags_text", "cells", "counts_of", "state_of", "record_from", "record_sessions", "clip",
           "bucket_of", "setup_label", "track_row", "charts_block", "views_block", "mark_dups", "LUK_HK", "HEADS"]
