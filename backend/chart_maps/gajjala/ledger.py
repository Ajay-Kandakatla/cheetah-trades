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
survived its entry bar). ⏪ The REPLAYED line (2026-10-16 night, DECISIONS11 D5): `gajjala_replay` docs written by
scripts/gajjala_replay.py (today's detectors re-run on a session with no record, `_id` "REPLAY:{date}|{SYM}|{setup}",
state "replayed") are their own line — never rang, never in any count of sent alerts or any %. The grader is PURE: 1-minute bars in, a dict out; every price compare is in
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
LINES = ("live", "shadow", "replayed")   # live = it reached your phone · shadow = A+ recorded, never sent · replayed = today's detectors re-run on a session with no record (DECISIONS11 D5), never rang
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


# ⏪ the replayed line (2026-10-16 night, DECISIONS11 D4 / D5) — a replay doc's id is never a ledger_id (no collision)
REPLAY_ID_PREFIX = "REPLAY:"
REPLAY_STATE = "replayed"


def replay_id(date_iso: str, sym: str, setup: str) -> str:
    """`"REPLAY:{date}|{SYM}|{setup}"` — one gajjala_replay doc per (session, symbol, setup) (BUILD_SPEC11 §3.12)."""
    return f"{REPLAY_ID_PREFIX}{str(date_iso)[:10]}|{(sym or '').upper()}|{setup}"


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
    ⏪ (DECISIONS11 D5): a `gajjala_replay` doc — `_id` == replay_id(date, SYM, setup) (no `#`), state "replayed",
    kind "aplus", an `alert` block — is the REPLAYED line (`id` = its `_id`; at / trigger / stop read from `alert`); a
    `REPLAY:` id in any other state is never a row and never reads live (C6).
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
        a = doc.get("alert") if isinstance(doc.get("alert"), dict) else {}
        if state == "shadow" and _id.startswith(AL.SHADOW_CLAIM_PREFIX) and "#" not in _id:
            line = LINES[1]
        elif (state == "pushed" and "#" not in _id and not _id.startswith(AL.SHADOW_CLAIM_PREFIX)
              and not _id.startswith(REPLAY_ID_PREFIX)):                                     # C6
            line = LINES[0]
        elif (state == REPLAY_STATE and "#" not in _id and _id == replay_id(d.isoformat(), sym, setup)
              and doc.get("kind") == KINDS[1] and a):                                        # DECISIONS11 D5 · F15
            line = LINES[2]
        else:
            return None
        src_doc = a if line == LINES[2] else doc          # a replay doc keeps at / trigger / stop under "alert"
        at = _parse_at(src_doc.get("at")) or _parse_at(src_doc.get("claimed_at"))
        at_et = at.astimezone(ET).strftime("%H:%M") if at else None
        first_et = None
        trig, stop, px, src = (src_doc.get("trigger"), src_doc.get("stop"), src_doc.get("price"),
                               PLAN_SOURCES[3])
        url = PT.deep_link(sym, setup)
    plan, r = plan_of(trig, stop)
    t, s = _num(trig), _num(stop)
    r_pct = round(float(_D(r) / _D(t) * 100), 4) if plan == PLANS[0] else None
    rid = str(doc.get("_id")) if line == LINES[2] else ledger_id(d.isoformat(), sym, setup, kind)   # ⏪ D5
    return {"id": rid, "date": d.isoformat(), "symbol": sym, "setup": setup,
            "kind": kind, "line": line, "at_utc": at, "at_et": at_et, "rang": rang_of(d, at),
            "trigger": t, "stop": s, "r": r, "r_pct": r_pct,
            "thin": bool(r_pct is not None and r_pct < GC.LEDGER_MIN_R_PCT), "plan": plan,
            "price_at_alert": _num(px), "plan_source": src, "first_seen_et": first_et, "url": url,
            # 📌 2026-10-27: the flagged trader's key the claim / tracker doc carries (a ⏪ replay never has one)
            "trader": (doc.get("trader") if line != LINES[2] and isinstance(doc.get("trader"), str)
                       and doc.get("trader") else None)}


def _sort_key(row: dict) -> tuple:
    d = _as_date(row.get("date"))
    at = row.get("at_utc")
    setups = {s: i for i, s in enumerate(GC.SETUPS)}
    return (-(d.toordinal() if d else 0), 0 if at else 1, -(at.timestamp() if at else 0.0), row.get("symbol") or "",
            setups.get(row.get("setup"), len(setups)), KINDS.index(row["kind"]) if row.get("kind") in KINDS else 9)


def rows_for(sessions, store, *, with_replay: bool = False, faults: Optional[list] = None) -> list:
    """D1: every 🧠 push that rang + every A+ shadow / live A+ claim on these ET sessions, as alert_of dicts, ordered
    (date desc, at desc — no alert time last, symbol asc, SETUPS index, KINDS index). Raises LedgerReadError when
    either read is None. A doc that cannot be read as a row is skipped (logged) — the rest stand.
    ⏪ (DECISIONS11 D5): `with_replay` (served_block ONLY — the default False keeps grade_step and today_read off every
    replay doc) adds the store's replay_rows as the replayed line; each source keeps only its own lines (a REPLAY doc
    planted in gajjala_alerts is never a row); a replayed row carries `graded` = the doc's own pre-graded columns. A
    replay read that raises or answers None appends "replay" to `faults` and serves without the line (a store without
    the method: no line, no fault)."""
    sessions = list(sessions or [])
    pot = store.potential_pushes(sessions)
    al = store.alert_rows(sessions)
    if pot is None or al is None:
        raise LedgerReadError("the 🧠 tracker or the A+ ledger could not be read")
    rep: list = []
    if with_replay:
        rd = getattr(store, "replay_rows", None)
        if callable(rd):
            try:
                got = rd(sessions)
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala ledger: replay read failed: %s", type(exc).__name__)
                got = None
            if got is None:
                if faults is not None:
                    faults.append("replay")
            else:
                rep = list(got)
    out, seen = [], set()
    for docs, kind, lines in ((pot, KINDS[0], (LINES[0],)), (al, KINDS[1], (LINES[0], LINES[1])),
                              (rep, KINDS[1], (LINES[2],))):
        for doc in docs:
            try:
                row = alert_of(doc, kind)
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala ledger: unreadable %s doc %s: %s", kind, (doc or {}).get("_id"),
                            type(exc).__name__)
                continue
            if row is None or row["line"] not in lines or row["id"] in seen:
                continue
            if row["line"] == LINES[2]:
                row["graded"] = {h: (doc.get(h) if isinstance(doc.get(h), dict) else None)
                                 for h in GC.LEDGER_HORIZONS}
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
           "(docs/gajjala/study_2026_10_13.md); this record does not change that."
           # W3 — WIDENED 2026-10-16 (night): DECISIONS11 D11 — the chips count rows
           " The winners / losers chips count ROWS (a name that rang on two setups is two rows); the % lines are "
           "unchanged.")                                                                                    # W3
HEADS = (("symbol", "Ticker"), ("setup", "Setup"), ("at", "Alert"), ("kind", "Kind"),
         ("plan", "Trigger → fill · stop"), ("same", "Same session"), ("next", "Through next session"))  # W11
KIND_TEXT = {("potential", "live"): "🧠 live", ("aplus", "shadow"): "A+ shadow — never sent",
             ("aplus", "live"): "🎯 A+ entry",
             ("aplus", "replayed"): "⏪ A+ replayed"}                                   # W7 · E7 · DECISIONS11 D5
# MINE (AMENDMENTS10 F3): the count buckets — the headline % (🧠 pushes only) · the A+ shadow line · the 🎯 live A+ entries
# · (DECISIONS11 D5) the ⏪ replayed rows — never rang, their own bucket, never a % (WIDENED 2026-10-16 night)
COUNT_LINES = ("live", "shadow", "entry", "replayed")
ENTRIES_HEAD = "🎯 A+ entries sent (their own line, not pooled with the 🧠 %)"            # AMENDMENTS10 F3
NO_PLAN_TEXT = "no trigger or stop on the alert"                                                         # W9
NO_RISK_TEXT = "trigger = stop on the alert — no risk to size"                                           # E4
NO_TIME_TEXT = "no alert time"                                                                           # E3
THIN_TEXT = "thin R"                                                                                     # E4
# ⏪ the replayed line (DECISIONS11 D4 / D5 / D10, BUILD_SPEC11 §3.11, AMENDMENTS11 F10) — served words, frozen
REPLAYED_HEAD = "⏪ Replayed with today's detectors (never rang, not in any %)"            # DECISIONS11 D5
REPLAY_NOTE = ("Replayed on the study's same-day universe (a subset of what the live scanner lists), no float gate, "
               "as-printed bars; these never rang. Not a measurement — the 2026-10-14 study read NULL.")   # D5 verbatim
REPLAY_FAULT_TEXT = "⏪ replay not read"                                                   # D5
REPLAY_NOT_GRADED_TEXT = "not graded (bars not cached)"                                    # D4
REPLAY_CHIP = "⏪ replayed"
REPLAY_CHIP_UNGATED = "⏪ replayed · 🎾 ungated"                                           # D10 DEFAULT — HIS CALL Q4
FLOAT_GATED_SETUPS = ("reversal_squeeze",)   # MINE: the one detector that reads the float (detectors.reversal_squeeze → _float_gate, K8_MAX_FLOAT)
REPLAY_CAVEATS = (
    "Universe: the study's same-day list (grouped daily, his three scanner numbers, the first qualifying minute) — a subset of what the live scanner lists (no stay-listed carry, no split hold-outs).",
    "No float gate: 🎾 Reversal Squeeze rows are ungated structure (no point-in-time float on file).",
    "As-printed bars (not split-adjusted), graded only on the study cache's own minute bars.",
    f"The alert time is the {GC.PASS_CADENCE_SEC // 60}-minute pass label (the live pass rang about a minute later); its freshness, halts and after-hours context are not replayed.",
    "A later reverse split unknown to the dated type lookup is not seen.",
    "One break per setup per day: the study keeps the first break of any class — a later A+ behind an earlier stopped or variant break on the same setup is not replayed.",   # AMENDMENTS11 F10
    "These never rang. Not a measurement — the 2026-10-14 study read NULL.",
)

# ✅ / ❌ categories (Ajay 2026-10-16: "I want winners and losers category in his track record and would like us to study
# the losers" — DECISIONS11 D11, BUILD_SPEC11 §3.14 C8, AMENDMENTS11 F7 / F13). ROW counts, never a %.
BUCKETS = ("win", "loss", "open", "flat", "out")                                           # DECISIONS11 D11
BUCKET_TEXT = {"win": "✅ winner", "loss": "❌ loser", "open": "⏳ open", "flat": "➖ flat",
               "out": "— no fill / not graded"}                                           # D11 · AMENDMENTS11 F7
CATEGORY_KEYS = ("all",) + BUCKETS
CATEGORY_LABELS = {"all": "📋 all", "win": "✅ winners", "loss": "❌ losers", "open": "⏳ open", "flat": "➖ flat",
                   "out": "— no fill / not graded"}                                       # D11 · AMENDMENTS11 F7
CATEGORY_PARAM = "cat"
CATEGORY_EMPTY_TEXT = "No row in this category on this span."

# 🎯 Ajay 2026-10-26 (BUILD_SPEC25): "Once done can you give me a  A+ filter in the track record I wanna see how many of
# the A+ were successful draw some charts to show the winning vs losing percentages of A+ trades please" — FROZEN words
# (§3.1). The A+ rows pool the sent (live) and the shadow line in ONE % of their own; the 🧠 headline % is unchanged; the
# ⏪ replayed rows never rang and stay out. ROW counts tallied by the headline's own thin rule (_tally_into). UNMEASURED.
KIND_PARAM = "kind"
KIND_KEYS = ("all", "aplus")                                                               # first = off
KIND_LABELS = {"all": "📋 every alert", "aplus": "🎯 A+ only"}
KIND_EMPTY_TEXT = "No 🎯 A+ alert on this span."
APLUS_LINES = (LINES[0], LINES[1])
APLUS_TITLE = "🎯 A+ only — every A+ alert, sent or shadow, graded by GG's trade math · UNMEASURED"
APLUS_LEADS = {"same": "A+ same session", "next": "A+ through next session"}
APLUS_SENT_TEXT = "{n} sent to your phone"
APLUS_SHADOW_TEXT = "{n} from the shadow period (never sent)"
APLUS_REPLAYED_NOTE = "⏪ Replayed rows are not in the 🎯 A+ filter, its counts or its charts — they never rang."
APLUS_HONESTY = ("Pooled: the A+ alerts sent to your phone and the shadow-period A+ (never sent) in one %, on its own "
                 "line — the 🧠 headline % is unchanged. An A+ exists only once the trade survived its entry bar. Small "
                 "n, a ledger graded by GG's own trade math — not a backtest of a strategy. The 2026-10-14 study of the "
                 "five setups read NULL — no edge over a matched placebo (docs/gajjala/study_2026_10_13.md); this "
                 "record does not change that.")
APLUS_CHART_KEYS = ("outcomes", "by_setup", "by_day")
APLUS_CHART_TITLES = {"outcomes": "🎯 A+ wins vs losses", "by_setup": "By setup", "by_day": "By alert day"}
APLUS_ITEM_LABELS = {"win": "wins", "loss": "losses", "open": "open", "flat": "flat", "no_entry": "no entry",
                     "other": "other"}
NO_DECIDED_TEXT = "no graded entry yet"


def bucket_of(same_state: Optional[str], next_state: Optional[str], next_due: bool = True) -> str:
    """D11 + BUILD_SPEC11 C8 as modified by AMENDMENTS11 F7 — the row's category from its two SERVED cell states, total:
    next win/loss → it; else same win/loss → it (next pending / split / copied); else next "flat" → "flat"; else same
    "open" while the next column is still due (next "pending" and `next_due`) → "open"; else "out" (no_entry / no_plan /
    no_risk / no_time / pending / split, a replayed row whose next session was never cached, same open + next split,
    any unknown string). A thin-R row keeps its real bucket (and its thin chip — it stays out of the %)."""
    if next_state in DECIDED:
        return next_state
    if same_state in DECIDED:
        return same_state
    if next_state == BUCKETS[3]:
        return BUCKETS[3]
    if same_state == BUCKETS[2] and next_state == "pending" and next_due:
        return BUCKETS[2]
    return BUCKETS[4]


def _category_text(key: str, n: int, n_replayed: int = 0) -> str:
    """The chip's served text, the ROW count inside it (C10): f"{label} {n}" (+ f" +{r} ⏪" when `n_replayed` replayed
    rows share the bucket — AMENDMENTS11 F13, counted apart, never in a sent count)."""
    return f"{CATEGORY_LABELS[key]} {int(n)}" + (f" +{int(n_replayed)} ⏪" if n_replayed else "")


def _categories(rows: list) -> list:
    """D11 / C10 / AMENDMENTS11 F6 + F13 — one chip per CATEGORY_KEYS key over the SERVED rows given: `n` = the rows
    on the lines live / shadow / entry (every non-replayed row; "all" = all of them), `n_replayed` = the ⏪ replayed
    rows of that bucket, counted APART (they filter in with their bucket, never in a sent count); `text` =
    _category_text. Row counts only — never a %."""
    out = []
    for k in CATEGORY_KEYS:
        mine = [r for r in rows if k == CATEGORY_KEYS[0] or r.get("bucket") == k]
        r_n = sum(1 for r in mine if r.get("line") == LINES[2])
        n = len(mine) - r_n
        out.append({"key": k, "text": _category_text(k, n, r_n), "n": n, "n_replayed": r_n})
    return out


# loss facts (DECISIONS11 D12, BUILD_SPEC11 §3.15, AMENDMENTS11 F2 / F14 / F17) — FROZEN words: facts from the STORED
# grade fields only (never a regrade, never a bar), no causal word; the thresholds live in constants.py (MINE)
LOSS_FACT_THIN = "thin R (not in the %)"
LOSS_FACT_STOPPED = "stopped {n} min after the fill"
LOSS_FACT_BEST = "high +{x}R through the stop minute"         # AMENDMENTS11 F17 (best_to_exit includes the stop minute)
LOSS_FACT_FILLED = "filled {m} min after it rang"
LOSS_FACT_FILL_MINUTE = "stop in the fill minute"
LOSS_FACT_LATE_RTH = "last {n} min of RTH"                    # n = GC.LEDGER_LOSS_LATE_RTH_MIN
LOSS_FACT_NEXT_MORNING = "filled next morning (rang AH)"
LOSS_FACT_STALE = "filled ≥{n} min after the ring"            # n = GC.LEDGER_LOSS_STALE_FILL_MIN


def _whole_min(a: datetime, b: datetime) -> int:
    """Whole minutes from a to b (floor)."""
    return int((b - a).total_seconds() // 60)


def _fill_clock(grade: Optional[dict]) -> Optional[tuple]:
    """(fill_t, exit_t) aware UTC of a FILLED, decided (win / loss) grade that is not a split cell, else None."""
    if not isinstance(grade, dict) or grade.get("entry") != "filled" or grade.get("reason") == "split":
        return None
    if grade.get("outcome") not in DECIDED:
        return None
    f, x = _parse_at(grade.get("fill_t")), _parse_at(grade.get("exit_t"))
    return (f, x) if f is not None and x is not None else None


def fill_facts(row: dict, grade: Optional[dict]) -> Optional[dict]:
    """AMENDMENTS11 F14 — PURE, the fill-clock facts of ANY decided trade (win or loss) from the stored grade fields only
    (never a regrade, never a bar): None unless `grade` FILLED, decided, with fill_t and exit_t. -> {"fill_after_min":
    int | None (fill_t − the alert's at_utc, floor), "late_rth": the fill minute starts within LEDGER_LOSS_LATE_RTH_MIN
    of its day's regular close, "next_morning": the row rang "ah" and the fill's ET date ≠ the alert date, "stale":
    fill_after_min ≥ LEDGER_LOSS_STALE_FILL_MIN and not next_morning (F2), "fast": exit_t − fill_t ≤
    LEDGER_LOSS_FAST_MIN (the stop for a loss, the +1R for a win)}. loss_facts calls it — one engine."""
    clk = _fill_clock(grade)
    if clk is None:
        return None
    fill_t, exit_t = clk
    row = row or {}
    at = row.get("at_utc") if isinstance(row.get("at_utc"), datetime) else _parse_at(row.get("at_utc"))
    fill_after = _whole_min(_aware(at), fill_t) if at is not None else None
    f_et = fill_t.astimezone(ET)
    close = datetime.combine(f_et.date(), _close_et(f_et.date()), tzinfo=ET)
    late = timedelta(0) < close - f_et <= timedelta(minutes=GC.LEDGER_LOSS_LATE_RTH_MIN)
    a_d = _as_date(row.get("date"))
    next_morning = row.get("rang") == RANGS[2] and a_d is not None and f_et.date() != a_d
    stale = fill_after is not None and fill_after >= GC.LEDGER_LOSS_STALE_FILL_MIN and not next_morning
    return {"fill_after_min": fill_after, "late_rth": bool(late), "next_morning": bool(next_morning),
            "stale": bool(stale), "fast": _whole_min(fill_t, exit_t) <= GC.LEDGER_LOSS_FAST_MIN}


def loss_facts(row: dict, grade: Optional[dict]) -> Optional[dict]:
    """D12 — PURE, from the stored grade fields only (never a regrade, never a bar). None unless `grade` is a FILLED
    loss with fill_t and exit_t. -> {"stopped_min": int (exit_t − fill_t, floor), "fill_after_min", "best_r": float |
    None (best_to_exit_pct / 100 × fill_px / row["r"]; None without r), "fill_minute": reason == "stop_fill_minute",
    "late_rth", "next_morning", "stale" (fill_facts — F2: never a next-morning fill), "fast": stopped_min ≤
    LEDGER_LOSS_FAST_MIN, "no_progress": best_r < LEDGER_LOSS_NO_PROGRESS_R, "gave_back": best_r ≥
    LEDGER_LOSS_GAVE_BACK_R, "thin": bool(row["thin"])}."""
    if not isinstance(grade, dict) or grade.get("outcome") != "loss":
        return None
    ff = fill_facts(row, grade)
    if ff is None:
        return None
    fill_t, exit_t = _fill_clock(grade)
    row = row or {}
    best, fill, r = _num(grade.get("best_to_exit_pct")), _num(grade.get("fill_px")), _num(row.get("r"))
    best_r = (float(_D(best) / 100 * _D(fill) / _D(r)) if best is not None and fill is not None and r
              else None)
    return {"stopped_min": _whole_min(fill_t, exit_t), "fill_after_min": ff["fill_after_min"], "best_r": best_r,
            "fill_minute": grade.get("reason") == "stop_fill_minute", "late_rth": ff["late_rth"],
            "next_morning": ff["next_morning"], "stale": ff["stale"], "fast": ff["fast"],
            "no_progress": bool(best_r is not None and best_r < GC.LEDGER_LOSS_NO_PROGRESS_R),
            "gave_back": bool(best_r is not None and best_r >= GC.LEDGER_LOSS_GAVE_BACK_R),
            "thin": bool(row.get("thin"))}


def loss_text(row: dict, grade: Optional[dict]) -> Optional[str]:
    """" · ".join of: LOSS_FACT_THIN (thin rows, FIRST) · LOSS_FACT_STOPPED · LOSS_FACT_BEST (when best_r) ·
    LOSS_FACT_FILLED (when fill_after_min) · ONE part, the first true in D12's order: fill_minute →
    LOSS_FACT_FILL_MINUTE, late_rth → LOSS_FACT_LATE_RTH, next_morning → LOSS_FACT_NEXT_MORNING, stale →
    LOSS_FACT_STALE. `{x}` = f"{best_r:.1f}". None when loss_facts is None."""
    f = loss_facts(row, grade)
    if f is None:
        return None
    parts = [LOSS_FACT_THIN] if f["thin"] else []
    parts.append(LOSS_FACT_STOPPED.format(n=f["stopped_min"]))
    if f["best_r"] is not None:
        parts.append(LOSS_FACT_BEST.format(x=f"{f['best_r']:.1f}"))
    if f["fill_after_min"] is not None:
        parts.append(LOSS_FACT_FILLED.format(m=f["fill_after_min"]))
    part = next((p for ok, p in ((f["fill_minute"], LOSS_FACT_FILL_MINUTE),
                                 (f["late_rth"], LOSS_FACT_LATE_RTH.format(n=GC.LEDGER_LOSS_LATE_RTH_MIN)),
                                 (f["next_morning"], LOSS_FACT_NEXT_MORNING),
                                 (f["stale"], LOSS_FACT_STALE.format(n=GC.LEDGER_LOSS_STALE_FILL_MIN))) if ok), None)
    if part:
        parts.append(part)
    return " · ".join(parts)


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


def _sessions_for(span_k: str, session: date, store, faults: Optional[list] = None) -> list:
    """The span's sessions. On "all" a replay_dates read that answers None or raises appends "replay" to `faults`
    (served_block then serves REPLAY_FAULT_TEXT) — never folded silently into "no replayed sessions"."""
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
    rd = getattr(store, "replay_dates", None)                   # ⏪ DECISIONS11 D5: the replayed sessions too
    if callable(rd):
        try:
            rdates = rd()
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala ledger: replay dates read failed: %s", type(exc).__name__)
            rdates = None
        if rdates is None:
            if faults is not None:
                faults.append("replay")
        else:
            more |= set(rdates)
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


def replay_cell(row: dict, h: str, g: Optional[dict], now: datetime, session: date, is_today: bool) -> dict:
    """⏪ DECISIONS11 D4 / D5 — a replayed row's cell from its OWN pre-graded column (never provisional): the ledger's
    _cell on a grade; a column the script could not grade (None) → "pending" with REPLAY_NOT_GRADED_TEXT (never the
    nightly's "graded tonight" — the nightly never grades a replay doc). A row with no plan / no risk / no alert time
    reads the live _cell's word (never "bars not cached" — no bars would have graded it). The 🏁 block and the tape both
    call it."""
    if isinstance(g, dict) or row.get("plan") != PLANS[0] or row.get("at_utc") is None:
        return _cell(row, h, g, False, now, session, is_today)
    return {"state": "pending", "text": REPLAY_NOT_GRADED_TEXT, "sub_text": None, "provisional": False}


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


def _extras(c: dict, h: str, pending_text: str = "not graded yet") -> str:
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
        bits.append(f"{c['pending']} {pending_text}")
    return "".join(f" · {b}" for b in bits)


def _wl(c: dict, pct: bool = True) -> str:
    """"N wins · M losses · P% won" — `pct=False` (the ⏪ replayed line, DECISIONS11 D5) drops the "· P% won" /
    "· no graded entry yet" tail: a replayed line never reads a %."""
    s = f"{_plural(c['win'], 'win', 'wins')} · {_plural(c['loss'], 'loss', 'losses')}"
    if not pct:
        return s
    p = _win_pct(c)
    return s + " · " + (f"{p}% won" if p is not None else NO_DECIDED_TEXT)


def _counts_text(c: dict, h: str, provisional: bool, lead: Optional[str] = None) -> str:
    """W4 / W4n — `lead` (🎯 BUILD_SPEC25: APLUS_LEADS[h]) replaces "Same session" / "Through next session"; the default
    (None) is the headline's own line, byte for byte."""
    if h == "same":
        head = "Same session" if lead is None else lead
        s = f"{head}: {_wl(c)} · {c['no_entry']} no entry · {c['open']} open" + _extras(c, h)
        return s + (" · today not final" if provisional else "")
    head = "Through next session" if lead is None else lead
    return f"{head}: {_wl(c)} · {c['no_entry']} no entry · {c['flat']} flat" + _extras(c, h)  # W4n


def _line_text(head: str, cs: dict, cn: dict, pct: bool = True, pending_text: str = "not graded yet") -> str:
    return (f"{head}: same session {_wl(cs, pct)} · {cs['no_entry']} no entry · "
            f"{cs['open']} open{_extras(cs, 'same', pending_text)}; through next session {_wl(cn, pct)} · "
            f"{cn['flat']} flat{_extras(cn, 'next', pending_text)}")


def _shadow_text(cs: dict, cn: dict) -> str:
    return _line_text("A+ shadow (never sent, not in the %)", cs, cn)                                 # W5


def _entries_text(cs: dict, cn: dict) -> str:
    """AMENDMENTS10 F3 — the live A+ entries' own line (the shadow line's template, its own head)."""
    return _line_text(ENTRIES_HEAD, cs, cn)


def _replayed_text(cs: dict, cn: dict) -> str:
    """DECISIONS11 D5 — the ⏪ replayed line (the shadow line's template, its own head), NEVER a %. Its pending word is
    REPLAY_NOT_GRADED_TEXT (the nightly never grades a replay doc, so "not graded yet" would be false)."""
    return _line_text(REPLAYED_HEAD, cs, cn, pct=False, pending_text=REPLAY_NOT_GRADED_TEXT)


def _count_line(row: dict) -> str:
    """AMENDMENTS10 F3 — which counts a row feeds: a live A+ entry → "entry" (its own 🎯 line), a shadow A+ → "shadow",
    a 🧠 push → "live" (the headline %). `row["line"]` itself is unchanged (a pushed `GG:` claim is still line live).
    ⏪ a replayed row → "replayed" FIRST (DECISIONS11 D5: never in live / shadow / entry, never a %)."""
    if row.get("line") == LINES[2]:
        return COUNT_LINES[3]
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


def _tally_into(c: dict, state: str, thin: bool) -> None:
    """THE thin rule (E4), ONE place: a thin-R row's win / loss / open / flat / no entry counts under `thin` (out of
    the %); any other state counts under its own key when the column has one (a same-session split has none)."""
    if thin and state in ("win", "loss", "open", "flat", "no_entry"):
        c["thin"] += 1
    elif state in c:
        c[state] += 1


def _group_days(rows: list, s_iso: str, is_today: bool) -> tuple:
    """(days, served_n) — the rows by alert date, newest first (W13 label, `more_n`), capped at LEDGER_ROWS_MAX rows
    in all (the oldest cut first). served_block's `days` AND the 🎯 `aplus.days` (BUILD_SPEC25)."""
    days, served_n = [], 0
    by_day: dict = {}
    for r in rows:
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
    return days, served_n


# ── 🎯 A+ filter + the win / loss charts (Ajay 2026-10-26, BUILD_SPEC25 §3.2) ───────────────────────────────────────
def is_aplus_row(r: dict) -> bool:
    """A BUILT row of the 🎯 filter: an A+ on the live (sent) or the shadow line — never a ⏪ replayed one."""
    return r.get("kind") == KINDS[1] and r.get("line") in APLUS_LINES


def _aplus_counts(rows: list) -> dict:
    """{h: counts} over the BUILT A+ rows, tallied from their served cell states by the headline's own thin rule."""
    c = {h: _counts_blank(h) for h in GC.LEDGER_HORIZONS}
    for r in rows:
        for h in GC.LEDGER_HORIZONS:
            _tally_into(c[h], r[h]["state"], bool(r.get("thin_text")))
    for h in GC.LEDGER_HORIZONS:
        c[h]["pct"] = _win_pct(c[h])
    return c


def _kind_text(key: str, n: int, n_replayed: int = 0) -> str:
    """The kind chip's served text, the ROW count inside it — never a %."""
    return f"{KIND_LABELS[key]} {int(n)}" + (f" +{int(n_replayed)} ⏪" if n_replayed else "")


def _kinds(shown: list, ap_shown: list) -> list:
    """The two kind chips over the SERVED rows: "all" (the ⏪ replayed rows counted apart) · "aplus" (aplus.days)."""
    r_n = sum(1 for r in shown if r.get("line") == LINES[2])
    n = len(shown) - r_n
    return [{"key": KIND_KEYS[0], "text": _kind_text(KIND_KEYS[0], n, r_n), "n": n, "n_replayed": r_n},
            {"key": KIND_KEYS[1], "text": _kind_text(KIND_KEYS[1], len(ap_shown)), "n": len(ap_shown),
             "n_replayed": 0}]


def _aplus_cell(c: dict, h: str, detail: bool) -> dict:
    """One horizon's served chart cell from a counts dict: {total, decided, pct, loss_pct, pct_text, text, short_text,
    items}. `total` = Σ the counts (pct excluded); the % is of the decided rows only; loss_pct = 100 − pct (one
    rounding). items: win + loss ALWAYS, the rest only when n > 0; Σ items.n == total."""
    total = sum(int(v) for k, v in c.items() if k != "pct")
    w, lo = int(c["win"]), int(c["loss"])
    decided = w + lo
    pct = _win_pct(c)
    loss_pct = None if pct is None else 100 - pct
    pct_text = f"{pct}% won · {decided} decided" if pct is not None else NO_DECIDED_TEXT
    k = total - w - lo
    text = _wl(c) + (f" · {k} other" if k > 0 else "")

    def item(key, n, txt):
        return {"key": key, "label": APLUS_ITEM_LABELS[key], "n": int(n), "text": txt}

    items = [item("win", w, _plural(w, "win", "wins")
                  + (f" ({pct}% of the {decided} decided)" if detail and pct is not None else "")),
             item("loss", lo, _plural(lo, "loss", "losses")
                  + (f" ({loss_pct}% of the {decided} decided)" if detail and loss_pct is not None else ""))]
    if detail:
        mid_k = "open" if h == GC.LEDGER_HORIZONS[0] else "flat"
        mid, ne = int(c[mid_k]), int(c["no_entry"])
        other = total - w - lo - mid - ne
        if mid > 0:
            items.append(item(mid_k, mid, f"{mid} {APLUS_ITEM_LABELS[mid_k]}"))
        if ne > 0:
            items.append(item("no_entry", ne, f"{ne} {APLUS_ITEM_LABELS['no_entry']}"))
        if other > 0:
            items.append(item("other", other, f"{other} {APLUS_ITEM_LABELS['other']}" + _extras(c, h)))
    elif k > 0:
        items.append(item("other", k, f"{k} {APLUS_ITEM_LABELS['other']}"))
    return {"total": total, "decided": decided, "pct": pct, "loss_pct": loss_pct, "pct_text": pct_text,
            "text": text, "short_text": f"{w}W {lo}L", "items": items}


def _aplus_group_cells(rows: list) -> dict:
    c = _aplus_counts(rows)
    return {h: _aplus_cell(c[h], h, False) for h in GC.LEDGER_HORIZONS}


def _aplus_charts(ap: list) -> list:
    """The three charts over the BUILT A+ rows ([] when none): outcomes (one bar per horizon, every row) · by_setup
    (GC.SETUPS order — never by %, unknown setups after, sorted; only setups with a row) · by_day (dates ASCENDING)."""
    if not ap:
        return []
    heads = dict(HEADS)
    c = _aplus_counts(ap)
    outcomes = {"key": APLUS_CHART_KEYS[0], "title": APLUS_CHART_TITLES[APLUS_CHART_KEYS[0]],
                "bars": [dict(_aplus_cell(c[h], h, True), key=h, label=heads[h]) for h in GC.LEDGER_HORIZONS]}
    by_s: dict = {}
    for r in ap:
        by_s.setdefault(r["setup"], []).append(r)
    order = [s for s in GC.SETUPS if s in by_s] + sorted(s for s in by_s if s not in GC.SETUPS)
    by_setup = {"key": APLUS_CHART_KEYS[1], "title": APLUS_CHART_TITLES[APLUS_CHART_KEYS[1]],
                "rows": [dict({"key": s, "label": by_s[s][0].get("setup_label")}, **_aplus_group_cells(by_s[s]))
                         for s in order]}
    by_d: dict = {}
    for r in ap:
        by_d.setdefault(r["date"], []).append(r)
    by_day = {"key": APLUS_CHART_KEYS[2], "title": APLUS_CHART_TITLES[APLUS_CHART_KEYS[2]],
              "cols": [dict({"key": d_iso, "label": _dow_md(_as_date(d_iso))}, **_aplus_group_cells(by_d[d_iso]))
                       for d_iso in sorted(by_d)]}
    return [outcomes, by_setup, by_day]


def aplus_block(ap: list, ap_days: list, has_replay: bool, prov: bool) -> dict:
    """🎯 the always-served A+ block (BUILD_SPEC25 §3.2): pooled live + shadow counts of EVERY A+ row on the span (never
    cut by LEDGER_ROWS_MAX), the house sentences, the three charts and its own capped rows (`days`)."""
    heads = dict(HEADS)
    counts = _aplus_counts(ap)
    n_sent = sum(1 for r in ap if r.get("line") == LINES[0])
    n_shadow = sum(1 for r in ap if r.get("line") == LINES[1])
    shown_n = sum(len(d["rows"]) for d in ap_days)
    cut = len(ap) - shown_n
    if ap:
        counts_text = {h: _counts_text(counts[h], h, prov if h == GC.LEDGER_HORIZONS[0] else False,
                                       lead=APLUS_LEADS[h]) for h in GC.LEDGER_HORIZONS}
        split_text = APLUS_SENT_TEXT.format(n=n_sent) + (
            " · " + APLUS_SHADOW_TEXT.format(n=n_shadow) if n_shadow > 0 else "")
        more_text = f"+{cut} more A+ rows — the counts above cover all {len(ap)}" if cut > 0 else None
        empty_text = None
    else:
        counts_text = split_text = more_text = None
        empty_text = KIND_EMPTY_TEXT
    return {"title": APLUS_TITLE, "total": len(ap), "n_sent": n_sent, "n_shadow": n_shadow, "counts": counts,
            "counts_text": counts_text, "split_text": split_text,
            "replayed_note": APLUS_REPLAYED_NOTE if has_replay else None, "more_text": more_text,
            "empty_text": empty_text, "honesty": APLUS_HONESTY,
            "horizons": [{"key": h, "label": heads[h]} for h in GC.LEDGER_HORIZONS],
            "horizon_default": GC.LEDGER_HORIZONS[0], "charts": _aplus_charts(ap), "days": ap_days if ap else []}


def served_block(store, session: date, now: datetime, *, span: str = "", is_today: bool = False,
                 today: Optional[dict] = None, broker_text_of: Optional[Callable] = None) -> dict:
    """The 🏁 sub's served block (§3.8 shape; W1–W15). Mongo reads only; `today` = today_read's dict (provisional same
    cells for today's rows). Counts are per column: the headline (`counts["live"]`, `counts_text`) = the 🧠 pushes only;
    the shadow A+ line (`counts["shadow"]`, `shadow_text`) and the live A+ entries (`counts["entry"]`, `entries_text`,
    AMENDMENTS10 F3 — never pooled into the 🧠 %) separately; no entry / no plan / no risk / no alert time / thin R /
    pending / split are listed, never in the %. ⏪ (DECISIONS11 D5) the replayed rows read their own pre-graded
    columns, count under counts["replayed"] (pct always None, `replayed_text` without a %), never enter `needs`; a
    replay read fault serves the block without them and `replayed_note` = REPLAY_FAULT_TEXT. ✅ / ❌ (D11 / D12) every
    row serves `bucket` / `bucket_text` / `loss_text`; `categories` / `categories_timeline` count the SERVED rows
    (F6), the replayed ones apart (F13) — they never feed a count line or a %. Raises LedgerReadError on a read
    fault (the tab softens it into TRACK_RECORD_FAULT).
    🚫 DECISIONS12 D2 — the row's broker tag from the tab's callable (owner only); rows_for untouched."""
    from . import alerts as AL
    from . import tape as TP                                    # lazy: tape imports this module (DECISIONS11 D3)
    from . import trader_names as TN                            # 📌 2026-10-27 — the served tag words

    def _broker(sym):
        if broker_text_of is None:
            return None
        try:
            return broker_text_of(sym)
        except Exception as exc:                                # noqa: BLE001 — a tag never takes the block down
            log.warning("gajjala ledger: broker tag failed: %s", type(exc).__name__)
            return None
    now = _aware(now)
    session = _as_date(session)
    span_k = span if span in GC.LEDGER_SPANS else GC.LEDGER_SPAN_DEFAULT
    faults: list = []
    sessions = _sessions_for(span_k, session, store, faults)
    rows = rows_for(sessions, store, with_replay=True, faults=faults)          # ⏪ DECISIONS11 D5
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
        replayed = row.get("line") == LINES[2]
        doc = stored.get(row["id"]) or {}
        cells, gs = {}, {}
        for h in GC.LEDGER_HORIZONS:
            prov = False
            if replayed:
                # ⏪ a replayed row reads ONLY its own pre-graded columns (never gajjala_ledger, never today's grades)
                g = (row.get("graded") or {}).get(h)
                g = g if isinstance(g, dict) else None
                cells[h] = replay_cell(row, h, g, now, session, is_today)
            else:
                g = doc.get(h) if isinstance(doc.get(h), dict) else None
                if (g is None and h == "same" and is_today and row["id"] in grades_today
                        and (_bounds_of(row) or {}).get("same_date") == session):       # E1: same session = today
                    g, prov = grades_today[row["id"]], True
                cells[h] = _cell(row, h, g, prov, now, session, is_today)
            gs[h] = g
            _tally_into(counts[_count_line(row)][h], cells[h]["state"], bool(row.get("thin")))   # THE thin rule
            if prov and _count_line(row) == COUNT_LINES[0]:
                any_prov = True
        plan_text, fill_px = _plan_text(row, gs.get("same"), gs.get("next"))
        e, label = AL.SETUP_META.get(row["setup"], ("", row["setup"]))
        note = (f"trigger as first seen {row.get('first_seen_et')} ET (the ring was {row.get('at_et')} ET)"
                if row.get("plan_source") == PLAN_SOURCES[2] and row.get("first_seen_et") and row.get("at_et")
                else None)                                                                                 # W9b
        # ✅ / ❌ (DECISIONS11 D11, AMENDMENTS11 F7): the bucket from the two SERVED cell states; a replayed row whose
        # next column was never graded (bars not cached) is not "due" — never "⏳ open" forever
        next_due = not (replayed and gs.get("next") is None)
        bucket = bucket_of(cells["same"]["state"], cells["next"]["state"], next_due)
        # D12: the loss facts of the column that made the bucket "loss" (next when it reads loss, else same)
        lt = None
        if bucket == BUCKETS[1]:
            lt = loss_text(row, gs.get("next") if cells["next"]["state"] == BUCKETS[1] else gs.get("same"))
        replay_text = ((REPLAY_CHIP_UNGATED if row["setup"] in FLOAT_GATED_SETUPS else REPLAY_CHIP) if replayed
                       else None)                                                        # D5 · D10 (HIS CALL Q4)
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
                      "same": cells["same"], "next": cells["next"],
                      "replay_text": replay_text, "bucket": bucket, "bucket_text": BUCKET_TEXT[bucket],
                      "loss_text": lt, "broker_text": _broker(row["symbol"]),             # 🚫 DECISIONS12 D2
                      "trader_text": TN.text_for(row.get("trader"))})                   # 📌 2026-10-27
    for ln in COUNT_LINES:
        for h in GC.LEDGER_HORIZONS:
            # ⏪ the replayed line never reads a % (DECISIONS11 D5 / D7)
            counts[ln][h]["pct"] = None if ln == COUNT_LINES[3] else _win_pct(counts[ln][h])
    has_shadow = any(r["line"] == LINES[1] for r in rows)
    has_entry = any(_count_line(r) == COUNT_LINES[2] for r in rows)
    has_replay = any(r["line"] == LINES[2] for r in rows)
    # E1: a row needs today's read when its same session is today (yesterday's after-close alert too) — on a span that
    # reads today at all ("yesterday" never does: today_read answers None there); a replayed row never needs it
    reads_today = is_today and span_k != GC.LEDGER_SPANS[1]
    needs = [r for r in rows if reads_today and r.get("line") != LINES[2]
             and not isinstance((stored.get(r["id"]) or {}).get("same"), dict)
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
    days, served_n = _group_days(built, s_iso, is_today)
    extra = len(built) - served_n
    shown = [r for d in days for r in d["rows"]]                # AMENDMENTS11 F6: the chips count the SERVED rows
    # 🎯 BUILD_SPEC25: the A+ rows (sent + shadow, never ⏪) — their OWN capped list, counted over every one of them
    ap = [r for r in built if is_aplus_row(r)]
    ap_days, _ap_n = _group_days(ap, s_iso, is_today)
    ap_shown = [r for d in ap_days for r in d["rows"]]
    ap_prov = any((r["same"] or {}).get("provisional") for r in ap)      # the 🧠 any_prov is untouched
    tl_kinds = TP.views_block()["kinds"]
    rep_text = _replayed_text(counts["replayed"]["same"], counts["replayed"]["next"]) if has_replay else None
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
            "views": TP.views_block(),                                                  # DECISIONS11 D3 (served)
            # ⏪ DECISIONS11 D5: the replayed line's own words — never in counts_text / shadow_text / entries_text
            "replayed_text": rep_text,
            "replayed_note": REPLAY_NOTE if has_replay else (REPLAY_FAULT_TEXT if faults else None),
            # ✅ / ❌ DECISIONS11 D11 (C10, F6, F13): ROW counts of the rows served, never a %, never a count line
            "categories": _categories(shown),
            "categories_timeline": _categories([r for r in shown if r["kind"] in tl_kinds]),
            "category_param": CATEGORY_PARAM, "category_empty_text": CATEGORY_EMPTY_TEXT,
            # 🎯 BUILD_SPEC25 (Ajay 2026-10-26): the kind chips (ROW counts), the A+ rows' categories, the A+ block
            "kinds": _kinds(shown, ap_shown), "kind_param": KIND_PARAM, "kind_empty_text": KIND_EMPTY_TEXT,
            "categories_aplus": _categories(ap_shown),
            "aplus": aplus_block(ap, ap_days, has_replay, ap_prov)}


__all__ = ["KINDS", "LINES", "PLAN_SOURCES", "RANGS", "RANG_TEXT", "CELL_STATES", "LedgerReadError", "ledger_id",
           "plan_of", "rang_of", "alert_of", "rows_for", "count_today", "session_bounds", "fill_window",
           "bars_from_frame", "grade", "grade_step", "today_read", "today_bars", "filled_grade", "served_block",
           "rule_text", "TITLE", "RULE_LABEL", "HONESTY", "HEADS", "KIND_TEXT", "COUNT_LINES", "ENTRIES_HEAD",
           "REPLAY_ID_PREFIX", "REPLAY_STATE", "replay_id", "REPLAYED_HEAD", "REPLAY_NOTE", "REPLAY_FAULT_TEXT",
           "REPLAY_NOT_GRADED_TEXT", "REPLAY_CHIP", "REPLAY_CHIP_UNGATED", "FLOAT_GATED_SETUPS", "REPLAY_CAVEATS",
           "BUCKETS", "BUCKET_TEXT", "CATEGORY_KEYS", "CATEGORY_LABELS", "CATEGORY_PARAM", "CATEGORY_EMPTY_TEXT",
           "bucket_of", "LOSS_FACT_THIN", "LOSS_FACT_STOPPED", "LOSS_FACT_BEST", "LOSS_FACT_FILLED",
           "LOSS_FACT_FILL_MINUTE", "LOSS_FACT_LATE_RTH", "LOSS_FACT_NEXT_MORNING", "LOSS_FACT_STALE",
           "fill_facts", "loss_facts", "loss_text", "replay_cell",
           "KIND_PARAM", "KIND_KEYS", "KIND_LABELS", "KIND_EMPTY_TEXT", "APLUS_LINES", "APLUS_TITLE", "APLUS_LEADS",
           "APLUS_SENT_TEXT", "APLUS_SHADOW_TEXT", "APLUS_REPLAYED_NOTE", "APLUS_HONESTY", "APLUS_CHART_KEYS",
           "APLUS_CHART_TITLES", "APLUS_ITEM_LABELS", "NO_DECIDED_TEXT", "is_aplus_row", "aplus_block"]
