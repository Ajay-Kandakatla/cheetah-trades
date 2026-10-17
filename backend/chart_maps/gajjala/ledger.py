"""🏁 Track record — every Gajjala alert that rang, graded by GG's trade math (2026-10-16, BUILD_SPEC9 + AMENDMENTS9).

THE ASK (Ajay 2026-10-16, verbatim):
  "also can you track all Gajjals stocks and keep a new tab to show wins vs losses. To see a percentage and the ticker.

  We are not looking for winners just in time but when they got in to our alerts if they made it or not. Like XLAB today
  was a winner I made good money on it"
His knob answers (DECISIONS9): WIN RULE = "GG's trade math" — the trigger the alert gave is the entry, a WIN reaches
+1R (trigger − stop) before the stop is touched, never triggered = "no entry" (shown, never counted); HORIZON = "Both
columns" — the same session and through the next session, side by side. Q0 (13:00 ET): "Keep GG's math" — the stop is a
touch (low ≤ stop), the win +1R before the stop, the % the best move from the fill. FILL WINDOW (13:10 ET, AMENDMENTS9
E1): "From 09:45 ET only" — fills count 09:45–16:00 ET (constants.LEDGER_FILL_FROM_ET / LEDGER_FILL_TO_ET); an alert
that rang after the regular close fills in its next regular session, which is then its "same session".

OPERATIONAL ACCOUNTING, NOT A STUDY. This is a ledger of the alerts as sent — no CI, no placebo, no measured edge; the
2026-10-14 study of the five setups read NULL and nothing here contradicts it. NOT SEPA: no other method's engine is
imported (tests/test_gajjala_source_guard.py). Every number comes from constants.py; every served string is composed
here (the frontend prints them).

Rows (D1): every 🧠 potential push that RANG (`push.state` "pushed"; joined / muted / never-pushed potentials are not
rows) — the live line, the headline % — and every A+ `gajjala_alerts` SHADOW claim (never sent: its own line, never in
the %) + every live A+ entry (a `GG:` claim in state pushed, since 2026-10-16) on the live line, counted on its own 🎯
line (counts["entry"], `entries_text`), never pooled into the 🧠 % (AMENDMENTS10 F3: an A+ exists only once the trade
survived its entry bar). The grader is PURE: 1-minute bars in, a dict out; every price compare is in
`Decimal(repr(x))` (1.85 + 0.10 is 1.9500000000000002 in binary floats — a float compare misses an equal high).

Writes: ONLY `grade_step` (the 20:15 ET nightly's LAST step) writes, into gajjala_ledger. `today_read` (the 🏁 GET's
"today so far") reads today's 1-minute bars and NEVER writes. `served_block` reads Mongo only.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from . import constants as GC

log = logging.getLogger("chart_maps.gajjala.ledger")

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
ONE_MIN = timedelta(minutes=1)
SETTLE = timedelta(seconds=GC.BAR_SETTLE_SEC)

KINDS = ("potential", "aplus")        # 🧠 gajjala_potential push · 🚩 A+ gajjala_setup
LINES = ("live", "shadow")            # live = it reached your phone · shadow = A+ recorded, never sent
PLAN_SOURCES = ("push", "first_sighting", "first_sighting_deferred", "aplus")
PLANS = ("ok", "no_plan", "no_risk")  # no_risk = trigger == stop on the alert (AMENDMENTS9 E4)
ENTRIES = ("filled", "no_entry", "no_plan", "no_risk", "no_time")
RANGS = ("pre", "rth", "ah")          # AMENDMENTS9 E1: the alert's own stamp vs 09:30 / the regular close
RANG_TEXT = {"pre": "rang pre", "rth": "rang RTH", "ah": "rang AH"}
CELL_STATES = ("win", "loss", "open", "flat", "no_entry", "no_plan", "no_risk", "no_time", "pending", "split")
DECIDED = ("win", "loss")
_DECIDED_COPY = ("entry", "fill_px", "fill_t", "outcome", "target_px", "exit_t", "reason", "best_to_exit_pct")
STEP_KEYS = ("rows", "same", "next", "next_copied", "not_due", "deferred_cap", "load_failed", "no_bars", "split",
             "split_check_failed", "loads", "written", "faulted")


class LedgerReadError(RuntimeError):
    """A row source (the 🧠 tracker or the A+ ledger) could not be read — never "no alert rang"."""


# ── small helpers ─────────────────────────────────────────────────────────────────────────────────────────────────
def _num(x) -> Optional[float]:
    if isinstance(x, bool) or x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def _D(x) -> Decimal:
    """Every price compare: the decimal the float prints as (repr), never its binary expansion."""
    return Decimal(repr(float(x)))


def _aware(t: Optional[datetime]) -> datetime:
    if t is None:
        return datetime.now(UTC)
    return t.replace(tzinfo=UTC) if t.tzinfo is None else t.astimezone(UTC)


def _as_date(d) -> Optional[date]:
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    try:
        return date.fromisoformat(str(d)[:10])
    except (TypeError, ValueError):
        return None


def _iso_t(t: Optional[datetime]) -> Optional[str]:
    return _aware(t).isoformat() if isinstance(t, datetime) else None


def _parse_at(v) -> Optional[datetime]:
    """An alert stamp (aware ISO string, or a datetime read back naive = UTC) → aware UTC; anything else → None."""
    if isinstance(v, datetime):
        return _aware(v)
    if isinstance(v, str) and v.strip():
        try:
            t = datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        return _aware(t)
    return None


def _hhmm(v) -> Optional[str]:
    return v if isinstance(v, str) and len(v) == 5 and v[2] == ":" and (v[:2] + v[3:]).isdigit() else None


def _close_et(d: date):
    from . import alerts as AL
    return AL._closes(d)[0]


def _close_utc(d: date) -> datetime:
    return datetime.combine(d, _close_et(d), tzinfo=ET).astimezone(UTC)


def _next_market_day(d: date) -> date:
    from catalysts.medical.reaction import next_market_day
    return next_market_day(d)


def _prev_market_day(d: date) -> date:
    from catalysts.medical.reaction import prev_market_day
    return prev_market_day(d)


def _px(x) -> str:
    from . import tab as GT
    return GT._px(x)


def _pct(x) -> str:
    return f"{float(x):+.1f}%"


def _dow_md(d: date) -> str:
    return f"{d:%a} {d:%m-%d}"


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def ledger_id(date_iso: str, sym: str, setup: str, kind: str) -> str:
    """`"{date}|{SYM}|{setup}|{kind}"` — one ledger doc per rung alert."""
    return f"{str(date_iso)[:10]}|{(sym or '').upper()}|{setup}|{kind}"


# ── the plan and the clock ────────────────────────────────────────────────────────────────────────────────────────
def plan_of(trigger, stop) -> tuple:
    """(plan, r) — "ok" with r = trigger − stop when trigger > stop; "no_risk" when trigger == stop (E4); "no_plan"
    for a missing / non-finite trigger or stop, or a stop above the trigger."""
    t, s = _num(trigger), _num(stop)
    if t is None or s is None or t <= 0 or s < 0:
        return "no_plan", None
    dt, ds = _D(t), _D(s)
    if dt == ds:
        return "no_risk", None
    if dt < ds:
        return "no_plan", None
    return "ok", float(dt - ds)


def rang_of(session, at_utc: Optional[datetime]) -> Optional[str]:
    """E1 chip: "pre" before 09:30 ET, "rth" to the regular close, "ah" at or after it (on the alert's date)."""
    from daytrading.data import ET_RTH_OPEN
    d = _as_date(session)
    if d is None or not isinstance(at_utc, datetime):
        return None
    et = _aware(at_utc).astimezone(ET)
    if et < datetime.combine(d, ET_RTH_OPEN, tzinfo=ET):
        return RANGS[0]
    if et < datetime.combine(d, _close_et(d), tzinfo=ET):
        return RANGS[1]
    return RANGS[2]


def session_bounds(session, at_utc: datetime) -> dict:
    """{"date", "rang", "fill_from", "same_date", "same_end", "next_date", "next_end"} — aware UTC datetimes.
    fill_from = the alert + BAR_SETTLE_SEC (the alert minute and anything before alert + settle never fills). AMENDMENTS9
    E1: an alert before the regular close of `session` (alerts._closes[0]: 16:00, 13:00 on a half day) has its same
    session on `session`; an alert at or after it has its same session on the NEXT market day (its first regular
    session). The next-session column ends at the regular close of the market day after the same session."""
    d = _as_date(session)
    at = _aware(at_utc)
    same_date = d if at < _close_utc(d) else _next_market_day(d)
    next_date = _next_market_day(same_date)
    return {"date": d, "rang": rang_of(d, at), "fill_from": at + SETTLE, "same_date": same_date,
            "same_end": _close_utc(same_date), "next_date": next_date, "next_end": _close_utc(next_date)}


def fill_window(day: date) -> tuple:
    """(from, to) ET times a fill may start in on `day`: LEDGER_FILL_FROM_ET (09:45, Ajay "From 09:45 ET only") to
    LEDGER_FILL_TO_ET (16:00), never past that day's regular close (13:00 on a half day — the regular session)."""
    return GC.LEDGER_FILL_FROM_ET, min(GC.LEDGER_FILL_TO_ET, _close_et(day))


def bars_from_frame(df) -> list:
    """A load_intraday DataFrame (naive-UTC minute STARTS) → [(t_utc aware, o, h, l, c)] ascending, NaN rows dropped,
    one bar per minute."""
    if df is None or getattr(df, "empty", True):
        return []
    out = {}
    try:
        cols = [df[k] for k in ("open", "high", "low", "close")]
    except Exception:                                           # noqa: BLE001
        return []
    for ts, o, h, lo, c in zip(df.index, *cols):
        vals = [_num(v) for v in (o, h, lo, c)]
        if any(v is None for v in vals):
            continue
        t = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
        if isinstance(t, str):
            t = _parse_at(t)
        if not isinstance(t, datetime):
            continue
        t = _aware(t)
        out[t] = (t, *vals)
    return [out[k] for k in sorted(out)]


def _merge(*parts) -> list:
    out = {}
    for p in parts:
        for b in p or []:
            out[b[0]] = b
    return [out[k] for k in sorted(out)]


# ── rows (D1) ─────────────────────────────────────────────────────────────────────────────────────────────────────
def alert_of(doc: dict, kind: str) -> Optional[dict]:
    """-> {id, date, symbol, setup, kind, line, at_utc (aware | None), at_et "HH:MM" | None, rang, trigger, stop, r,
    r_pct, thin, plan, price_at_alert, plan_source, first_seen_et, url} | None when the doc is not a row (D1).

    🧠 "potential": a push that RANG (`push.state` "pushed") on a doc not first seen by a join pass. 🚩 "aplus": a
    `SHADOW:` claim in state "shadow" (line shadow, never sent …) + every live A+ entry (a `GG:` claim in state pushed,
    no `#`, since 2026-10-16) on the live line — served_block counts it on its own 🎯 line, never in the 🧠 % (F3).
    Alert time (E3) = `push.at` / `at` → else `claimed_at` → else None (the row is "no alert time", never counted)."""
    from . import alerts as AL
    from . import potential as PT
    from . import store as ST
    if not isinstance(doc, dict) or kind not in KINDS:
        return None
    sym = str(doc.get("symbol") or "").upper()
    setup = doc.get("setup")
    d = _as_date(doc.get("date")) if isinstance(doc.get("date"), str) else None
    if not sym or not isinstance(setup, str) or not setup or d is None:
        return None
    if kind == KINDS[0]:
        push = doc.get("push")
        if not isinstance(push, dict) or push.get("state") != "pushed":
            return None
        if doc.get("first_seen_mode") == ST.JOINED_MODE:
            return None
        at = _parse_at(push.get("at")) or _parse_at(push.get("claimed_at")) or _parse_at(doc.get("claimed_at"))
        at_et = _hhmm(push.get("at_et")) or (at.astimezone(ET).strftime("%H:%M") if at else None)
        first_et = _hhmm(doc.get("first_seen_et"))
        if _num(push.get("trigger")) is not None and _num(push.get("stop")) is not None:
            trig, stop, px, src = push.get("trigger"), push.get("stop"), push.get("px"), PLAN_SOURCES[0]
        else:
            trig, stop, px = doc.get("first_trigger"), doc.get("first_stop"), doc.get("first_px")
            # deferred only when BOTH times are on file and differ (the W9b note names both); a missing one is a
            # first sighting — a served note never prints a missing time
            src = PLAN_SOURCES[2] if (at_et is not None and first_et is not None and at_et != first_et) \
                else PLAN_SOURCES[1]
        line = LINES[0]
        url = doc.get("url") if isinstance(doc.get("url"), str) and doc.get("url").startswith("/") else \
            PT.deep_link(sym, setup)
    else:
        _id = str(doc.get("_id") or "")
        state = doc.get("state")
        if state == "shadow" and _id.startswith(AL.SHADOW_CLAIM_PREFIX) and "#" not in _id:
            line = LINES[1]
        elif state == "pushed" and "#" not in _id and not _id.startswith(AL.SHADOW_CLAIM_PREFIX):
            line = LINES[0]
        else:
            return None
        at = _parse_at(doc.get("at")) or _parse_at(doc.get("claimed_at"))
        at_et = at.astimezone(ET).strftime("%H:%M") if at else None
        first_et = None
        trig, stop, px, src = doc.get("trigger"), doc.get("stop"), doc.get("price"), PLAN_SOURCES[3]
        url = PT.deep_link(sym, setup)
    plan, r = plan_of(trig, stop)
    t, s = _num(trig), _num(stop)
    r_pct = round(float(_D(r) / _D(t) * 100), 4) if plan == PLANS[0] else None
    return {"id": ledger_id(d.isoformat(), sym, setup, kind), "date": d.isoformat(), "symbol": sym, "setup": setup,
            "kind": kind, "line": line, "at_utc": at, "at_et": at_et, "rang": rang_of(d, at),
            "trigger": t, "stop": s, "r": r, "r_pct": r_pct,
            "thin": bool(r_pct is not None and r_pct < GC.LEDGER_MIN_R_PCT), "plan": plan,
            "price_at_alert": _num(px), "plan_source": src, "first_seen_et": first_et, "url": url}


def _sort_key(row: dict) -> tuple:
    d = _as_date(row.get("date"))
    at = row.get("at_utc")
    setups = {s: i for i, s in enumerate(GC.SETUPS)}
    return (-(d.toordinal() if d else 0), 0 if at else 1, -(at.timestamp() if at else 0.0), row.get("symbol") or "",
            setups.get(row.get("setup"), len(setups)), KINDS.index(row["kind"]) if row.get("kind") in KINDS else 9)


def rows_for(sessions, store) -> list:
    """D1: every 🧠 push that rang + every A+ shadow / live A+ claim on these ET sessions, as alert_of dicts, ordered
    (date desc, at desc — no alert time last, symbol asc, SETUPS index, KINDS index). Raises LedgerReadError when
    either read is None. A doc that cannot be read as a row is skipped (logged) — the rest stand."""
    sessions = list(sessions or [])
    pot = store.potential_pushes(sessions)
    al = store.alert_rows(sessions)
    if pot is None or al is None:
        raise LedgerReadError("the 🧠 tracker or the A+ ledger could not be read")
    out, seen = [], set()
    for docs, kind in ((pot, KINDS[0]), (al, KINDS[1])):
        for doc in docs:
            try:
                row = alert_of(doc, kind)
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala ledger: unreadable %s doc %s: %s", kind, (doc or {}).get("_id"),
                            type(exc).__name__)
                continue
            if row is not None and row["id"] not in seen:
                seen.add(row["id"])
                out.append(row)
    out.sort(key=_sort_key)
    return out


def count_today(pot_docs, ledger_docs=None) -> int:
    """The 🏁 chip count (AMENDMENTS9 E5 "rows graded today"): today's 🧠 rows (alert_of(d, "potential") is not None)
    that carry a stored same-session grade in `ledger_docs` (the session's gajjala_ledger docs). No extra read; no
    ledger docs given → 0 (the board's GET reads Mongo only — the nightly grades at LEDGER_GRADE_AT_ET)."""
    graded = {d.get("_id") for d in ledger_docs or [] if isinstance(d, dict) and isinstance(d.get("same"), dict)}
    n = 0
    for d in pot_docs or []:
        try:
            row = alert_of(d, KINDS[0])
        except Exception:                                       # noqa: BLE001
            row = None
        n += 1 if row is not None and row["id"] in graded else 0
    return n


# ── the grader (pure) ─────────────────────────────────────────────────────────────────────────────────────────────
def _blank(horizon: str) -> dict:
    return {"horizon": horizon, "entry": None, "fill_px": None, "fill_t": None, "outcome": None, "target_px": None,
            "exit_t": None, "reason": None, "best_pct": None, "best_to_exit_pct": None, "close_pct": None,
            "end_t": None, "end_date": None, "through_t": None, "bars_n": 0}


def grade(alert: dict, bars_1m: list, bounds: Optional[dict], horizon: str) -> dict:
    """GG's trade math (D2–D4 + Q0 + E1) for one column. `bars_1m` = [(t_utc START, o, h, l, c)] ascending; `bounds`
    = session_bounds(…) (today_read may cut same_end). -> the grade dict (every time an aware-UTC ISO string)."""
    if horizon not in GC.LEDGER_HORIZONS:
        raise ValueError(f"horizon {horizon!r} not in {GC.LEDGER_HORIZONS}")
    out = _blank(horizon)
    if not isinstance((alert or {}).get("at_utc"), datetime) or not bounds:
        return dict(out, entry="no_time", reason="no_time")
    plan = alert.get("plan") or plan_of(alert.get("trigger"), alert.get("stop"))[0]
    if plan != PLANS[0]:
        return dict(out, entry=plan, reason=plan)
    same = horizon == GC.LEDGER_HORIZONS[0]
    end = bounds["same_end"] if same else bounds["next_end"]
    out["end_t"] = _iso_t(end)
    out["end_date"] = (bounds["same_date"] if same else bounds["next_date"]).isoformat()
    elig = [b for b in bars_1m or [] if bounds["fill_from"] <= b[0] < end]
    out["bars_n"] = len(elig)
    out["through_t"] = _iso_t(elig[-1][0] + ONE_MIN) if elig else None
    trig, stop = _D(alert["trigger"]), _D(alert["stop"])
    windows: dict = {}

    def fill_ok(t: datetime) -> bool:
        et = t.astimezone(ET)
        day = et.date()
        if day not in windows:
            windows[day] = fill_window(day)
        lo, hi = windows[day]
        return lo <= et.time() < hi

    i0 = next((i for i, b in enumerate(elig) if _D(b[2]) >= trig and fill_ok(b[0])), None)
    if i0 is None:
        return dict(out, entry="no_entry", reason="no_entry")
    fill = max(trig, _D(elig[i0][1]))
    target = fill + _D(GC.LEDGER_R_MULT) * (trig - stop)
    exit_i, outcome, reason = None, None, None
    for i in range(i0, len(elig)):
        _t, _o, h, lo, _c = elig[i]
        if _D(lo) <= stop:                                     # a touch (Q0); a bar with both = LOSS; the fill minute counts
            exit_i, outcome, reason = i, "loss", ("stop_fill_minute" if i == i0 else "stop")
            break
        if i > i0 and _D(h) >= target:                         # the fill minute's high never counts toward the win
            exit_i, outcome, reason = i, "win", "target"
            break
    if outcome is None:
        outcome, reason = ("open" if same else "flat"), "horizon_end"

    def pct(x: Decimal) -> float:
        return round(float((x - fill) / fill * 100), 2)

    best = max(_D(b[2]) for b in elig[i0:])
    best_x = max(_D(b[2]) for b in elig[i0:(exit_i if exit_i is not None else len(elig) - 1) + 1])
    return dict(out, entry="filled", fill_px=float(fill), fill_t=_iso_t(elig[i0][0]), outcome=outcome,
                target_px=float(target), exit_t=_iso_t(elig[exit_i][0]) if exit_i is not None else None,
                reason=reason, best_pct=pct(best), best_to_exit_pct=pct(best_x), close_pct=pct(_D(elig[-1][4])))


def _bounds_of(row: dict) -> Optional[dict]:
    at = row.get("at_utc")
    return session_bounds(row["date"], at) if isinstance(at, datetime) else None


def _nominal_bounds(row: dict) -> dict:
    """The due clock of a row with no alert time: its date's regular close (same) and the next one (next)."""
    d = _as_date(row["date"])
    n = _next_market_day(d)
    return {"same_date": d, "same_end": _close_utc(d), "next_date": n, "next_end": _close_utc(n)}


# ── the nightly grade step (§3.5) ─────────────────────────────────────────────────────────────────────────────────
def _default_load_day(sym: str, day: date) -> tuple:
    """(bars, provider_failed) — completed days from `intraday_cache` (NO force), 04:00–20:00 ET prints."""
    from daytrading import data as dt_data
    from sepa.symbols import for_massive
    try:
        dt_data.clear_fetch_failed()
        df = dt_data.load_intraday(for_massive(sym), day, include_premarket=True, include_afterhours=True)
        return bars_from_frame(df), bool(df is None and dt_data.last_fetch_failed())
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala ledger: 1-minute load failed for %s %s: %s", sym, day, type(exc).__name__)
        return None, True


def _default_split_lookup(store) -> Callable:
    """-> look(sym, alert_date, end_date) → True | iso date (a split in (alert_date, end_date]) | False | None (the
    check could not be read). The scanner's per-session record answers only a ONE-session window (end_date = the
    market day after alert_date): it covers that one session, so a two-session window (an after-close alert's next
    column) always asks fetch_splits_strict."""
    def look(sym: str, alert_date: date, next_date: date):
        rec = None
        if _next_market_day(alert_date) == next_date:
            try:
                rec = (store.split_checks(next_date) or {}).get(sym.upper())
            except Exception:                                   # noqa: BLE001
                rec = None
        if rec == "held":
            return True
        if rec == "ok":
            return False
        try:
            from chart_maps import drop10_tab as DT
            splits = DT.fetch_splits_strict(sym, (alert_date + timedelta(days=1)).isoformat())
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala ledger: split check failed for %s: %s", sym, type(exc).__name__)
            return None
        lo, hi = alert_date.isoformat(), next_date.isoformat()
        hit = [str((s or {}).get("execution_date") or "")[:10] for s in splits or []]
        hit = [h for h in hit if lo < h <= hi]
        return hit[0] if hit else False
    return look


def _current(doc: dict, h: str) -> Optional[dict]:
    """The stored column when it was graded by this LEDGER_GRADE_VERSION, else None (a version bump regrades)."""
    col = (doc or {}).get(h)
    if not isinstance(col, dict):
        return None
    v = col.get("version", (doc or {}).get("version"))
    return col if v == GC.LEDGER_GRADE_VERSION else None


def _alert_block(row: dict) -> dict:
    return {"at": _iso_t(row.get("at_utc")), "at_et": row.get("at_et"), "rang": row.get("rang"),
            "trigger": row.get("trigger"), "stop": row.get("stop"), "r": row.get("r"), "r_pct": row.get("r_pct"),
            "thin": row.get("thin"), "plan": row.get("plan"), "price_at_alert": row.get("price_at_alert"),
            "plan_source": row.get("plan_source"), "first_seen_et": row.get("first_seen_et"), "url": row.get("url")}


def grade_step(store, now: datetime, *, load_day: Optional[Callable] = None, split_lookup: Optional[Callable] = None,
               dry: bool = False, max_loads: Optional[int] = None) -> dict:
    """🏁 The nightly grade (the 20:15 ET job's LAST step). Every row of the last LEDGER_GRADE_LOOKBACK_SESSIONS market
    days up to today gets each column whose horizon has ENDED (now ≥ end + BAR_SETTLE_SEC) and is not stored at this
    LEDGER_GRADE_VERSION; a horizon not ended is never written. A same column already decided (win / loss) is walked
    again for the next column (same fill / outcome / exit — the best % runs to the next close, D3); `next_copied`
    counts those. Loads go through a per-run memo, at most `max_loads` (LEDGER_BACKFILL_MAX_SYMBOL_DAYS)
    symbol-days a run (the rest `deferred_cap`, next night). A provider failure / an empty alert day leaves the column
    absent (retried), never "no entry". Each row in its own try. -> the step summary (STEP_KEYS + sessions,
    read_fault, dry)."""
    from . import context as CX
    from . import nightly as NG
    now = _aware(now)
    end_session = NG.default_session(now)
    sessions = CX.history_window(_next_market_day(end_session), GC.LEDGER_GRADE_LOOKBACK_SESSIONS)
    out: dict = {"sessions": [d.isoformat() for d in sessions], "read_fault": False, "dry": bool(dry)}
    out.update({k: 0 for k in STEP_KEYS})
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
    cap = int(max_loads) if max_loads is not None else int(GC.LEDGER_BACKFILL_MAX_SYMBOL_DAYS)
    load = load_day or _default_load_day
    split = split_lookup or _default_split_lookup(store)
    memo: dict = {}

    def days_for(sym: str, days: list) -> tuple:
        """-> (status, {day: bars}) — status ok | deferred_cap | load_failed."""
        miss = [d for d in days if (sym, d) not in memo]
        if out["loads"] + len(miss) > cap:
            return "deferred_cap", {}
        for d in miss:
            out["loads"] += 1
            try:
                res = load(sym, d)
                bars, failed = (res if isinstance(res, tuple) else (res, False))
                bars = bars if isinstance(bars, list) else bars_from_frame(bars)
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala ledger: load raised for %s %s: %s", sym, d, type(exc).__name__)
                bars, failed = None, True
            memo[(sym, d)] = (bars or [], bool(failed))
        if any(memo[(sym, d)][1] for d in days):
            return "load_failed", {}
        return "ok", {d: memo[(sym, d)][0] for d in days}

    def walk(row: dict, b: dict, h: str) -> tuple:
        """-> (grade | None, why)."""
        if row.get("plan") != PLANS[0] or b is None:
            return grade(row, [], b, h), None
        days = [b["same_date"]] if h == GC.LEDGER_HORIZONS[0] else [b["same_date"], b["next_date"]]
        status, by_day = days_for(row["symbol"], days)
        if status != "ok":
            return None, status
        if not by_day[b["same_date"]]:
            return None, "no_bars"                              # the name qualified that day — a feed gap, retried
        g = grade(row, _merge(*by_day.values()), b, h)
        if h != GC.LEDGER_HORIZONS[0] and not by_day[b["next_date"]]:
            g["next_no_prints"] = True                          # a halt all day / a delisting: graded on what printed
        return g, None

    pending: dict = {}
    same_now: dict = {}
    plan_rows = []
    for row in rows:
        try:
            plan_rows.append((row, _bounds_of(row)))
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala ledger: bounds failed for %s: %s", row.get("id"), type(exc).__name__)
            out["faulted"] += 1
    for h in GC.LEDGER_HORIZONS:                                # every same job first, then every next job
        is_same = h == GC.LEDGER_HORIZONS[0]
        for row, b in plan_rows:
            rid = row["id"]
            try:
                doc = docs.get(rid) or {}
                have = _current(doc, h)
                if have is not None:
                    if is_same:
                        same_now[rid] = have
                    continue
                due_b = b or _nominal_bounds(row)
                if now < (due_b["same_end"] if is_same else due_b["next_end"]) + SETTLE:
                    out["not_due"] += 1
                    continue
                if (is_same and row.get("plan") == PLANS[0] and b is not None
                        and b["same_date"] != _as_date(row["date"])):
                    # E1: an alert at or after the close is graded on the NEXT session's bars — a split between the
                    # alert day and that session rescales them, so the same column is guarded over (alert, same]:
                    # a split → reason "split" (never graded), an unread check → absent (retried)
                    sp0 = split(row["symbol"], _as_date(row["date"]), b["same_date"])
                    if sp0 is None:
                        out["split_check_failed"] += 1
                        continue
                    if sp0:
                        g = dict(_blank(h), reason="split",
                                 split_on=sp0 if isinstance(sp0, str) else b["same_date"].isoformat(),
                                 end_t=_iso_t(b["same_end"]), end_date=b["same_date"].isoformat(),
                                 version=GC.LEDGER_GRADE_VERSION)
                        pending.setdefault(rid, {})[h] = g
                        same_now[rid] = g
                        out["split"] += 1
                        out[h] += 1
                        continue
                s = same_now.get(rid)
                s_dec = (not is_same and isinstance(s, dict) and s.get("entry") == "filled"
                         and s.get("outcome") in DECIDED)
                sp = False
                if not is_same and row.get("plan") == PLANS[0] and b is not None:
                    sp = split(row["symbol"], _as_date(row["date"]), b["next_date"])
                    if sp is None:
                        out["split_check_failed"] += 1
                        if not s_dec:
                            continue
                    if sp and not s_dec:
                        g = dict(_blank(h), entry=(s or {}).get("entry"), outcome=None, reason="split",
                                 split_on=sp if isinstance(sp, str) else None,
                                 end_t=_iso_t(b["next_end"]), end_date=b["next_date"].isoformat(),
                                 version=GC.LEDGER_GRADE_VERSION)
                        pending.setdefault(rid, {})[h] = g
                        out["split"] += 1
                        out[h] += 1
                        continue
                if s_dec and (sp or sp is None):
                    # a trade the same session already ended is never overwritten by a split on (or an unread split
                    # check of) the next session: the outcome is COPIED and its best % stays the same session's —
                    # prices across a split are not comparable, so no walk crosses it
                    g = dict(s, horizon=h, end_t=_iso_t(b["next_end"]), end_date=b["next_date"].isoformat(),
                             best_through="same")
                    if isinstance(sp, str):
                        g["split_on"] = sp
                    if sp is None:
                        g["split_unchecked"] = True
                    out["next_copied"] += 1
                else:
                    # a decided same column with no split is WALKED again for D3's "best %" to the column's own end
                    # (AMENDMENTS9 E1's replay: XLAB 10-15's next-session best ≈ +215%); the trade itself — entry,
                    # fill, outcome, exit, reason — is COPIED from the same column, never re-derived
                    g, why = walk(row, b, h)
                    if g is None:
                        out[why] += 1
                        continue
                    if s_dec:
                        g.update({k: s.get(k) for k in _DECIDED_COPY})
                        out["next_copied"] += 1
                g["version"] = GC.LEDGER_GRADE_VERSION
                pending.setdefault(rid, {})[h] = g
                if is_same:
                    same_now[rid] = g
                out[h] += 1
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala ledger: grading %s %s failed: %s", rid, h, type(exc).__name__)
                out["faulted"] += 1
    for row, _b in plan_rows:
        cols = pending.get(row["id"])
        if not cols or dry:
            continue
        body = {"date": row["date"], "symbol": row["symbol"], "setup": row["setup"], "kind": row["kind"],
                "line": row["line"], "alert": _alert_block(row), "graded_at": now.isoformat(),
                "version": GC.LEDGER_GRADE_VERSION}
        body.update(cols)
        if store.upsert_ledger(row["id"], body):
            out["written"] += 1
    return out


# ── the on-open "today so far" read (§3.6, AMENDMENTS9 E6 / E8) ───────────────────────────────────────────────────
_TODAY_MEMO: dict = {}                    # {(session_iso, SYM): (clock(), fetched_at aware UTC, bars)}
_TODAY_SPLIT: dict = {}                   # {(session_iso, SYM, alert_iso): True | iso | False} — answered checks only
_TODAY_LOCK = threading.Lock()


def _today_load(sym: str, day: date) -> tuple:
    """(bars, provider_failed) — today's 1-minute bars, force=True (E8: the loader directly, not frames_for)."""
    from daytrading import data as dt_data
    from sepa.symbols import for_massive
    dt_data.clear_fetch_failed()
    df = dt_data.load_intraday(for_massive(sym), day, force=True, include_premarket=True, include_afterhours=True)
    return bars_from_frame(df), bool(df is None and dt_data.last_fetch_failed())


def _floor_minute(t: datetime) -> datetime:
    return t.replace(second=0, microsecond=0)


def today_bars(sym: str, day: date, *, clock: Optional[Callable] = None, load: Optional[Callable] = None,
               now: Optional[datetime] = None) -> tuple:
    """DECISIONS11 D2 — today's 1-minute bars of `sym` through the ONE memo today_read fills (_TODAY_MEMO, key
    (day_iso, SYM), LEDGER_TODAY_MEMO_SEC): a hit loads nothing; a miss loads ONCE through `load` (the caller passes
    _today_load for the 📈 full tape) and stores it for today_read too (the same value shape). AMENDMENTS11 F8: `load`
    None = MEMO-ONLY — a miss never loads and answers (None, None) (the row's mini tape never fetches). -> (bars
    [(t_utc, o, h, l, c)] of that ET day, fetched_at aware UTC) | (None, None) on a miss without a loader, a provider
    failure or no bars (never memoised). NEVER WRITES Mongo."""
    clock = clock or time.monotonic
    d_iso, sym_u = day.isoformat(), str(sym or "").upper()
    with _TODAY_LOCK:
        for m in (_TODAY_MEMO, _TODAY_SPLIT):                   # the today_read prune rule: one session at a time
            for k in [k for k in m if k[0] != d_iso]:
                m.pop(k, None)
        hit = _TODAY_MEMO.get((d_iso, sym_u))
    if hit is not None and clock() - hit[0] < GC.LEDGER_TODAY_MEMO_SEC:
        return hit[2], hit[1]
    if load is None:
        return None, None
    try:
        res = load(sym_u, day)
        bars, failed = (res if isinstance(res, tuple) else (res, False))
        bars = bars if isinstance(bars, list) else bars_from_frame(bars)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala ledger: today bars failed for %s: %s", sym_u, type(exc).__name__)
        return None, None
    if failed:
        return None, None
    bars = [b for b in bars or [] if b[0].astimezone(ET).date() == day]
    if not bars:
        return None, None
    at = _aware(now)
    with _TODAY_LOCK:
        _TODAY_MEMO[(d_iso, sym_u)] = (clock(), at, bars)
    return bars, at


def today_read(now: Optional[datetime] = None, *, span: str = "", store=None, load_frames: Optional[Callable] = None,
               clock: Optional[Callable] = None, split_lookup: Optional[Callable] = None) -> Optional[dict]:
    """D5c. None when the span excludes today ("yesterday"), or tab.session_for(now) is not today, or no today row
    still lacks a stored `same` (whose same session is today). Else -> {"session", "at", "through_et", "grades":
    {row_id: grade(…, "same")}, "not_read": [SYM…], "stats": {"loaded", "memo", "no_bars", "failed", "over_budget",
    "capped", "split_held"}}. `load_frames(sym, day)` -> (bars | DataFrame | None, provider_failed) — default the 1-minute loader
    with force=True. Memo LEDGER_TODAY_MEMO_SEC per (session, symbol); at most LEDGER_TODAY_MAX symbols per open;
    LEDGER_TODAY_BUDGET_SEC from the start. Closed minutes only; "through" never claims more than was read (E6: a
    memoised frame ends at its fetch time − BAR_SETTLE_SEC). An after-close row of yesterday (E1) is read only when
    `split_lookup(sym, alert_date, today)` (default ledger's own split lookup) answers no split: a split or an unread
    check puts the name in "not_read" (graded tonight), never a provisional grade on rescaled bars; an answered check
    is memoised for the session. NEVER WRITES."""
    from . import store as ST
    from . import tab as GT
    span_k = span if span in GC.LEDGER_SPANS else GC.LEDGER_SPAN_DEFAULT
    if span_k == GC.LEDGER_SPANS[1]:                            # "yesterday" — nothing of today is shown
        return None
    now = _aware(now)
    session, is_today, _in = GT.session_for(now)
    if not is_today:
        return None
    store = store or ST.default()
    clock = clock or time.monotonic
    load = load_frames or _today_load
    # E1: an alert at or after the close has its same session on the NEXT market day, so yesterday's after-hours
    # rows are read too (their same session is today); a span that shows only today reads only today's rows
    days = [session] if span_k == GC.LEDGER_SPANS[0] else [_prev_market_day(session), session]
    try:
        rows = rows_for(days, store)
    except LedgerReadError:
        return None
    stored = {d.get("_id"): d for d in (store.ledger_docs(days) or []) if isinstance(d, dict)}
    todo = []
    for row in rows:
        b = _bounds_of(row)
        if b is None or row.get("plan") != PLANS[0] or b["same_date"] != session:
            continue
        if isinstance((stored.get(row["id"]) or {}).get("same"), dict):
            continue
        todo.append((row, b))
    if not todo:
        return None
    s_iso = session.isoformat()
    t0 = clock()
    with _TODAY_LOCK:
        for m in (_TODAY_MEMO, _TODAY_SPLIT):
            for k in [k for k in m if k[0] != s_iso]:
                m.pop(k, None)
        memo = {k[1]: v for k, v in _TODAY_MEMO.items()}
        split_memo = dict(_TODAY_SPLIT)
    split = split_lookup or _default_split_lookup(store)
    held_out, kept, split_over = [], [], 0
    for row, b in todo:
        a_d = _as_date(row["date"])
        if a_d == session:
            kept.append((row, b))
            continue
        # E1: yesterday's after-close row is graded on today's bars — a split in (alert day, today] rescales them
        key = (s_iso, row["symbol"], a_d.isoformat())
        sp = split_memo.get(key)
        if key not in split_memo and clock() - t0 > GC.LEDGER_TODAY_BUDGET_SEC:
            split_over += 1                                     # out of time: not read, never memoised
        elif key not in split_memo:
            try:
                sp = split(row["symbol"], a_d, session)
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala ledger: today split check failed for %s: %s", row["symbol"], type(exc).__name__)
                sp = None
            if sp is not None:
                split_memo[key] = sp
                with _TODAY_LOCK:
                    _TODAY_SPLIT[key] = sp
        if sp is False:
            kept.append((row, b))
        elif row["symbol"] not in held_out:
            held_out.append(row["symbol"])
    todo = kept
    syms = []
    for row, _b in todo:
        if row["symbol"] not in syms:
            syms.append(row["symbol"])
    read, capped = syms[:int(GC.LEDGER_TODAY_MAX)], syms[int(GC.LEDGER_TODAY_MAX):]
    stats = {"loaded": 0, "memo": 0, "no_bars": 0, "failed": 0, "over_budget": split_over, "capped": len(capped),
             "split_held": len(held_out)}
    got: dict = {}
    for sym in read:
        hit = memo.get(sym)
        if hit is not None and clock() - hit[0] < GC.LEDGER_TODAY_MEMO_SEC:
            stats["memo"] += 1
            got[sym] = (hit[1], hit[2])
            continue
        if clock() - t0 > GC.LEDGER_TODAY_BUDGET_SEC:
            stats["over_budget"] += 1
            continue
        try:
            res = load(sym, session)
            bars, failed = (res if isinstance(res, tuple) else (res, False))
            bars = bars if isinstance(bars, list) else bars_from_frame(bars)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala ledger: today read failed for %s: %s", sym, type(exc).__name__)
            bars, failed = None, True
        if failed:
            stats["failed"] += 1
            continue
        bars = [b for b in bars or [] if b[0].astimezone(ET).date() == session]
        if not bars:
            stats["no_bars"] += 1
            continue
        stats["loaded"] += 1
        got[sym] = (now, bars)
        with _TODAY_LOCK:
            _TODAY_MEMO[(s_iso, sym)] = (clock(), now, bars)
    grades: dict = {}
    through = None
    for row, b in todo:
        if row["symbol"] not in got:
            continue
        fetched_at, bars = got[row["symbol"]]
        boundary = _floor_minute(min(now, fetched_at) - SETTLE)
        closed = [x for x in bars if x[0] + ONE_MIN <= boundary]
        try:
            grades[row["id"]] = grade(row, closed, dict(b, same_end=min(b["same_end"], boundary)), "same")
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala ledger: today grade failed for %s: %s", row["id"], type(exc).__name__)
            continue
        cut = min(b["same_end"], boundary)                      # E6: never past the session close nor the read
        through = cut if through is None else min(through, cut)
    not_read = [s for s in syms if s not in got]
    not_read += [s for s in held_out if s not in not_read]     # a name whose after-close row was held is not read
    return {"session": s_iso, "at": now.isoformat(),
            "through_et": through.astimezone(ET).strftime("%H:%M") if through else None,
            "grades": grades, "not_read": not_read, "stats": stats}


# ── the served block (§3.7, §3.10 W1–W15) ─────────────────────────────────────────────────────────────────────────
TITLE = "🏁 Track record — every Gajjala alert that rang, graded by GG's trade math · UNMEASURED"        # W1
RULE_LABEL = "ⓘ how each alert is graded"                                                               # W2a
# W3 — WIDENED 2026-10-16: Ajay flipped the A+ kind live ("you alert me when that happens"); AMENDMENTS10 F3: the live
# A+ entries sit on their own 🎯 line, never pooled with the 🧠 % (an A+ exists only once its trade survived the entry bar)
HONESTY = ("A ledger of the alerts as sent, graded by GG's own trade math — not a backtest of a strategy, and small n "
           "early. A+ rows from the shadow period (never sent) stay out of the %; A+ entries sent live are counted on "
           "their own 🎯 line, not pooled with the 🧠 pushes — an A+ exists only once the trade survived its entry bar. "
           "The 2026-10-14 study of the five setups read NULL — no edge over a matched placebo "
           "(docs/gajjala/study_2026_10_13.md); this record does not change that.")                       # W3
HEADS = (("symbol", "Ticker"), ("setup", "Setup"), ("at", "Alert"), ("kind", "Kind"),
         ("plan", "Trigger → fill · stop"), ("same", "Same session"), ("next", "Through next session"))  # W11
KIND_TEXT = {("potential", "live"): "🧠 live", ("aplus", "shadow"): "A+ shadow — never sent",
             ("aplus", "live"): "🎯 A+ entry"}                                         # W7 · E7 (DECISIONS10 D3)
# MINE (AMENDMENTS10 F3): the count buckets — the headline % (🧠 pushes only) · the A+ shadow line · the 🎯 live A+ entries
COUNT_LINES = ("live", "shadow", "entry")
ENTRIES_HEAD = "🎯 A+ entries sent (their own line, not pooled with the 🧠 %)"            # AMENDMENTS10 F3
NO_PLAN_TEXT = "no trigger or stop on the alert"                                                         # W9
NO_RISK_TEXT = "trigger = stop on the alert — no risk to size"                                           # E4
NO_TIME_TEXT = "no alert time"                                                                           # E3
THIN_TEXT = "thin R"                                                                                     # E4


def _t(x) -> str:
    return x.strftime("%H:%M")


def _m() -> str:
    return f"{GC.LEDGER_R_MULT:g}"


def rule_text() -> str:
    """W2 as amended by AMENDMENTS9 E1 (the 09:45 fill window, the after-close alert's same session)."""
    from daytrading.data import ET_RTH_CLOSE
    rth = _t(ET_RTH_CLOSE)
    lo, hi = _t(GC.LEDGER_FILL_FROM_ET), _t(GC.LEDGER_FILL_TO_ET)
    return (f"GG's trade math (your answer, 2026-10-16). Entry = the trigger the alert gave: the first 1-minute bar "
            f"from {lo} ET to {hi} ET (your answer: from {lo} ET only) that starts {GC.BAR_SETTLE_SEC} s or more after "
            f"the alert and trades at or above the trigger fills — at the trigger, or at that bar's open when it opened "
            f"above it (a gap fills at the open). WIN = a later 1-minute high reaches the fill +{_m()}R (R = trigger − "
            f"stop, as the alert gave them) before any low touches the stop. LOSS = the stop is touched first; a bar "
            f"that touches both counts as a loss, and so does a stop touched in the fill minute. Same session = through "
            f"{rth} ET on the alert's day (an alert at or after {rth} ET: through {rth} ET of the next market day, its "
            f"first regular session); through next session = the same walk to {rth} ET of the market day after that, "
            f"after-hours and pre-market prints included. The % is the best high after the fill against the fill; the "
            f"small % is the column's last close against the fill. No entry and no plan are listed, never counted; a "
            f"thin R (under {GC.LEDGER_MIN_R_PCT:g}% of the trigger) is graded and kept out of the %.")


def _span_label(k: str) -> str:
    return {"today": "Today", "yesterday": "Yesterday", "5d": f"Last {GC.LEDGER_SPAN_SESSIONS} sessions",
            "10d": f"Last {GC.LEDGER_SPAN_SESSIONS_LONG} sessions",                                     # DECISIONS11 D3
            "all": "All"}.get(k, k)                                                                      # W12


def _sessions_for(span_k: str, session: date, store) -> list:
    from . import context as CX
    if span_k == "today":
        return [session]
    if span_k == "yesterday":
        return [_prev_market_day(session)]
    if span_k == "5d":
        return CX.history_window(_next_market_day(session), GC.LEDGER_SPAN_SESSIONS)
    if span_k == "10d":                                         # DECISIONS11 D3 — the whole past week + fits
        return CX.history_window(_next_market_day(session), GC.LEDGER_SPAN_SESSIONS_LONG)
    dates = store.alert_dates()                                 # E7: the rows' own dates, never the ledger's alone
    if dates is None:
        raise LedgerReadError("the alert dates could not be read")
    more = set(dates) | set(store.ledger_dates() or []) | {session.isoformat()}
    return sorted({d for d in (_as_date(x) for x in more) if d is not None})


def _when(t_iso: Optional[str], alert_date: date) -> str:
    t = _parse_at(t_iso)
    if t is None:
        return "—"
    et = t.astimezone(ET)
    return et.strftime("%H:%M") if et.date() == alert_date else et.strftime("%a %H:%M")


def _pending(row: dict, h: str, now: datetime, session: date, is_today: bool) -> tuple:
    at = GC.LEDGER_GRADE_AT_ET
    b = _bounds_of(row) or _nominal_bounds(row)
    end, end_date = (b["same_end"], b["same_date"]) if h == "same" else (b["next_end"], b["next_date"])
    if now >= end + SETTLE:
        return "not graded yet", f"graded nightly at {at} ET"
    today_et = now.astimezone(ET).date()
    if h == "same" and is_today and row["date"] == session.isoformat() and end_date == session:
        return "not read yet", f"graded tonight {at} ET"
    if end_date == today_et:
        return "after today's close", f"graded tonight {at} ET"
    return f"after {_dow_md(end_date)}'s close", f"graded {_dow_md(end_date)} {at} ET"


def _state_of(g: dict) -> str:
    if g.get("reason") == "split":
        return "split"
    e = g.get("entry")
    if e == "filled":
        return g.get("outcome") or "open"
    return e if e in ("no_entry", "no_plan", "no_risk", "no_time") else "pending"


def _cell(row: dict, h: str, g: Optional[dict], provisional: bool, now: datetime, session: date,
          is_today: bool) -> dict:
    """W10 — {state, text, sub_text, provisional}."""
    alert_d = _as_date(row["date"])
    if g is None:
        if row.get("at_utc") is None:
            return {"state": "no_time", "text": NO_TIME_TEXT, "sub_text": None, "provisional": False}
        if row.get("plan") != PLANS[0]:
            g = {"entry": row.get("plan")}
        else:
            text, sub = _pending(row, h, now, session, is_today)
            return {"state": "pending", "text": text, "sub_text": sub, "provisional": False}
    st = _state_of(g)
    B = _pct(g["best_pct"]) if g.get("best_pct") is not None else "—"
    C = _pct(g["close_pct"]) if g.get("close_pct") is not None else "—"
    when = _when(g.get("exit_t"), alert_d)
    m = _m()
    lo, hi = _t(GC.LEDGER_FILL_FROM_ET), _t(GC.LEDGER_FILL_TO_ET)
    if provisional:
        text, sub = {"win": (f"WIN · best {B} so far", f"+{m}R at {when} · not final"),
                     "loss": (f"LOSS · best {B} so far", f"stop at {when} · not final"),
                     "open": (f"open · best {B} so far", f"close {C} so far"),
                     "no_entry": ("no entry yet", "not final")}.get(st, (st.replace("_", " "), "not final"))
    elif st == "win":
        text, sub = f"WIN · best {B}", f"+{m}R at {when} · close {C}"
    elif st == "loss":
        text = f"LOSS · best {B}"
        sub = (f"stop in the fill minute {when} · close {C}" if g.get("reason") == "stop_fill_minute"
               else f"stop at {when} · close {C}")
    elif st == "open":
        text, sub = f"open · best {B}", f"close {C}"
    elif st == "flat":
        nd = _as_date(g.get("end_date"))
        text, sub = f"flat · best {B}", f"close {C} at the {_dow_md(nd) if nd else '—'} close"
    elif st == "no_entry":
        text, sub = "no entry", f"the trigger never traded {lo}–{hi} ET after the alert"
    elif st == "no_plan":
        text, sub = "no plan", None
    elif st == "no_risk":
        text, sub = "no risk", NO_RISK_TEXT
    elif st == "no_time":
        text, sub = NO_TIME_TEXT, None
    elif st == "split":
        text, sub = "split", f"split on {g.get('split_on') or 'the next session'} — not graded"
    else:
        text, sub = _pending(row, h, now, session, is_today)
    if st in DECIDED and not provisional and g.get("best_through") == "same":       # a decided trade kept across a split
        sub += (f" · split on {g['split_on']} — best and close through the same session" if g.get("split_on")
                else " · best and close through the same session")
    return {"state": st, "text": text, "sub_text": sub, "provisional": bool(provisional)}


def filled_grade(same: Optional[dict], nxt: Optional[dict]) -> Optional[dict]:
    """The first of (same, next) that FILLED with a numeric fill_px and is not a split cell — the pick _plan_text makes,
    now one function (DECISIONS11 D2: the tape draws the same fill the plan text prints); _plan_text calls it."""
    return next((x for x in (same, nxt) if isinstance(x, dict) and x.get("entry") == "filled"
                 and _num(x.get("fill_px")) is not None and x.get("reason") != "split"), None)


def _plan_text(row: dict, same: Optional[dict], nxt: Optional[dict]) -> tuple:
    """W9 -> (plan_text, fill_px)."""
    if row.get("plan") == PLANS[1]:
        if row.get("trigger") is None or row.get("stop") is None:
            return NO_PLAN_TEXT, None
        return f"trigger {_px(row['trigger'])} · stop {_px(row['stop'])}", None
    if row.get("plan") == PLANS[2]:
        return NO_RISK_TEXT, None
    T, S = _px(row["trigger"]), _px(row["stop"])
    g = filled_grade(same, nxt)
    if g is None:
        return f"trigger {T} · stop {S}", None
    when = _when(g.get("fill_t"), _as_date(row["date"]))
    return (f"trigger {T} → fill {_px(g['fill_px'])} at {when} · stop {S} · +{_m()}R {_px(g.get('target_px'))}",
            g.get("fill_px"))


def _counts_blank(h: str) -> dict:
    keys = ("win", "loss", "no_entry", "open" if h == "same" else "flat", "no_plan", "no_risk", "no_time", "pending",
            "thin") + (("split",) if h == "next" else ())
    return dict({k: 0 for k in keys}, pct=None)


def _win_pct(c: dict) -> Optional[int]:
    w, lo = c["win"], c["loss"]
    return int(100 * w / (w + lo) + 0.5) if w + lo > 0 else None


def _extras(c: dict, h: str) -> str:
    bits = []
    if c.get("split"):
        bits.append(f"{c['split']} split")
    if c["no_plan"]:
        bits.append(f"{c['no_plan']} no plan")
    if c["no_risk"]:
        bits.append(f"{c['no_risk']} no risk")
    if c["no_time"]:
        bits.append(f"{c['no_time']} {NO_TIME_TEXT}")
    if c["thin"]:
        bits.append(f"{c['thin']} {THIN_TEXT} (not in the %)")
    if c["pending"]:
        bits.append(f"{c['pending']} not graded yet")
    return "".join(f" · {b}" for b in bits)


def _wl(c: dict) -> str:
    p = _win_pct(c)
    pct = f"{p}% won" if p is not None else "no graded entry yet"
    return f"{_plural(c['win'], 'win', 'wins')} · {_plural(c['loss'], 'loss', 'losses')} · {pct}"


def _counts_text(c: dict, h: str, provisional: bool) -> str:
    if h == "same":
        s = f"Same session: {_wl(c)} · {c['no_entry']} no entry · {c['open']} open" + _extras(c, h)
        return s + (" · today not final" if provisional else "")
    return f"Through next session: {_wl(c)} · {c['no_entry']} no entry · {c['flat']} flat" + _extras(c, h)  # W4n


def _line_text(head: str, cs: dict, cn: dict) -> str:
    return (f"{head}: same session {_wl(cs)} · {cs['no_entry']} no entry · "
            f"{cs['open']} open{_extras(cs, 'same')}; through next session {_wl(cn)} · {cn['flat']} flat"
            f"{_extras(cn, 'next')}")


def _shadow_text(cs: dict, cn: dict) -> str:
    return _line_text("A+ shadow (never sent, not in the %)", cs, cn)                                 # W5


def _entries_text(cs: dict, cn: dict) -> str:
    """AMENDMENTS10 F3 — the live A+ entries' own line (the shadow line's template, its own head)."""
    return _line_text(ENTRIES_HEAD, cs, cn)


def _count_line(row: dict) -> str:
    """AMENDMENTS10 F3 — which counts a row feeds: a live A+ entry → "entry" (its own 🎯 line), a shadow A+ → "shadow",
    a 🧠 push → "live" (the headline %). `row["line"]` itself is unchanged (a pushed `GG:` claim is still line live)."""
    if row.get("line") == LINES[1]:
        return COUNT_LINES[1]
    if row.get("kind") == KINDS[1]:
        return COUNT_LINES[2]
    return COUNT_LINES[0]


def _empty_text(span_k: str, sessions: list) -> str:
    if span_k == "today":
        return "No Gajjala alert has rung yet this session."
    if span_k == "yesterday":
        return f"No Gajjala alert rang on {sessions[0].isoformat() if sessions else '—'}."
    if span_k == "5d":
        return f"No Gajjala alert rang in the last {GC.LEDGER_SPAN_SESSIONS} sessions."
    if span_k == "10d":
        return f"No Gajjala alert rang in the last {GC.LEDGER_SPAN_SESSIONS_LONG} sessions."
    return "No Gajjala alert on file yet."                                                              # W15


def served_block(store, session: date, now: datetime, *, span: str = "", is_today: bool = False,
                 today: Optional[dict] = None) -> dict:
    """The 🏁 sub's served block (§3.8 shape; W1–W15). Mongo reads only; `today` = today_read's dict (provisional same
    cells for today's rows). Counts are per column: the headline (`counts["live"]`, `counts_text`) = the 🧠 pushes only;
    the shadow A+ line (`counts["shadow"]`, `shadow_text`) and the live A+ entries (`counts["entry"]`, `entries_text`,
    AMENDMENTS10 F3 — never pooled into the 🧠 %) separately; no entry / no plan / no risk / no alert time / thin R /
    pending / split are listed, never in the %. Raises LedgerReadError on a read
    fault (the tab softens it into TRACK_RECORD_FAULT)."""
    from . import alerts as AL
    from . import tape as TP                                    # lazy: tape imports this module (DECISIONS11 D3)
    now = _aware(now)
    session = _as_date(session)
    span_k = span if span in GC.LEDGER_SPANS else GC.LEDGER_SPAN_DEFAULT
    sessions = _sessions_for(span_k, session, store)
    rows = rows_for(sessions, store)
    stored_l = store.ledger_docs(sessions)
    if stored_l is None:
        raise LedgerReadError("the ledger could not be read")
    stored = {d.get("_id"): d for d in stored_l if isinstance(d, dict)}
    grades_today = (today or {}).get("grades") or {} if isinstance(today, dict) else {}
    s_iso = session.isoformat()
    counts = {ln: {h: _counts_blank(h) for h in GC.LEDGER_HORIZONS} for ln in COUNT_LINES}
    any_prov = False
    built = []
    for row in rows:
        doc = stored.get(row["id"]) or {}
        cells, gs = {}, {}
        for h in GC.LEDGER_HORIZONS:
            g = doc.get(h) if isinstance(doc.get(h), dict) else None
            prov = False
            if (g is None and h == "same" and is_today and row["id"] in grades_today
                    and (_bounds_of(row) or {}).get("same_date") == session):           # E1: same session = today
                g, prov = grades_today[row["id"]], True
            gs[h] = g
            cells[h] = _cell(row, h, g, prov, now, session, is_today)
            c = counts[_count_line(row)][h]
            st = cells[h]["state"]
            if row.get("thin") and st in ("win", "loss", "open", "flat", "no_entry"):
                c["thin"] += 1
            elif st in c:
                c[st] += 1
            if prov and _count_line(row) == COUNT_LINES[0]:
                any_prov = True
        plan_text, fill_px = _plan_text(row, gs.get("same"), gs.get("next"))
        e, label = AL.SETUP_META.get(row["setup"], ("", row["setup"]))
        note = (f"trigger as first seen {row.get('first_seen_et')} ET (the ring was {row.get('at_et')} ET)"
                if row.get("plan_source") == PLAN_SOURCES[2] and row.get("first_seen_et") and row.get("at_et")
                else None)                                                                                 # W9b
        built.append({"key": row["id"].replace("|", "-"), "id": row["id"], "date": row["date"],
                      "symbol": row["symbol"], "setup": row["setup"], "setup_label": f"{e} {label}".strip(),
                      "kind": row["kind"], "line": row["line"],
                      "kind_text": KIND_TEXT.get((row["kind"], row["line"]), row["kind"]),
                      "at_et": row.get("at_et"),
                      "at_text": (f"{row['at_et']} ET" if row.get("at_et") and row.get("at_utc") else
                                  NO_TIME_TEXT),                                                         # W8 / E3
                      "rang": row.get("rang"), "rang_text": RANG_TEXT.get(row.get("rang")),             # E1 chip
                      "thin_text": THIN_TEXT if row.get("thin") else None,                              # E4 chip
                      "trigger": row.get("trigger"), "stop": row.get("stop"), "fill_px": fill_px,
                      "plan_text": plan_text, "note": note, "href": row.get("url"),
                      "same": cells["same"], "next": cells["next"]})
    for ln in COUNT_LINES:
        for h in GC.LEDGER_HORIZONS:
            counts[ln][h]["pct"] = _win_pct(counts[ln][h])
    has_shadow = any(r["line"] == LINES[1] for r in rows)
    has_entry = any(_count_line(r) == COUNT_LINES[2] for r in rows)
    # E1: a row needs today's read when its same session is today (yesterday's after-close alert too) — on a span that
    # reads today at all ("yesterday" never does: today_read answers None there)
    reads_today = is_today and span_k != GC.LEDGER_SPANS[1]
    needs = [r for r in rows if reads_today and not isinstance((stored.get(r["id"]) or {}).get("same"), dict)
             and r.get("plan") == PLANS[0] and (_bounds_of(r) or {}).get("same_date") == session]
    at = GC.LEDGER_GRADE_AT_ET
    today_text = None
    if needs:
        if isinstance(today, dict) and today.get("through_et"):
            k = len(today.get("not_read") or [])
            today_text = f"Today · through {today['through_et']} ET · not final" + (
                f" · {_plural(k, 'name', 'names')} not read on this open — graded tonight {at} ET" if k else "")
        else:
            today_text = f"Today · not read on this open — graded tonight {at} ET"                     # W6
    days, served_n = [], 0
    by_day: dict = {}
    for r in built:
        by_day.setdefault(r["date"], []).append(r)
    for d_iso in sorted(by_day, reverse=True):
        room = max(0, int(GC.LEDGER_ROWS_MAX) - served_n)
        part = by_day[d_iso][:room]
        if not part:
            continue
        served_n += len(part)
        d = _as_date(d_iso)
        label = f"{d:%a} {d_iso}" + (" · today" if d_iso == s_iso and is_today else "")                # W13
        more = len(by_day[d_iso]) - len(part)
        days.append({"date": d_iso, "label": label, "more_n": more or None, "rows": part})
    extra = len(built) - served_n
    return {"title": TITLE, "rule_label": RULE_LABEL, "rule_text": rule_text(), "honesty": HONESTY, "span": span_k,
            "spans": [{"key": k, "label": _span_label(k)} for k in GC.LEDGER_SPANS],
            "heads": [{"key": k, "label": lab} for k, lab in HEADS],
            "counts": counts,
            "counts_text": {"same": _counts_text(counts["live"]["same"], "same", any_prov),
                            "next": _counts_text(counts["live"]["next"], "next", False)},
            "shadow_text": _shadow_text(counts["shadow"]["same"], counts["shadow"]["next"]) if has_shadow else None,
            "entries_text": (_entries_text(counts["entry"]["same"], counts["entry"]["next"]) if has_entry
                             else None),                                                       # AMENDMENTS10 F3
            "today_text": today_text, "days": days,
            "more_text": f"+{extra} more rows — the counts above cover all {len(built)}" if extra > 0 else None,  # W14
            "empty_text": None if built else _empty_text(span_k, sessions), "grade_at_et": at,
            "views": TP.views_block()}                                                  # DECISIONS11 D3 (served)


__all__ = ["KINDS", "LINES", "PLAN_SOURCES", "RANGS", "RANG_TEXT", "CELL_STATES", "LedgerReadError", "ledger_id",
           "plan_of", "rang_of", "alert_of", "rows_for", "count_today", "session_bounds", "fill_window",
           "bars_from_frame", "grade", "grade_step", "today_read", "today_bars", "filled_grade", "served_block",
           "rule_text", "TITLE", "RULE_LABEL", "HONESTY", "HEADS", "KIND_TEXT", "COUNT_LINES", "ENTRIES_HEAD"]
