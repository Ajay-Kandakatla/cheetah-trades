"""🎚️ tape_control — "buyers in control on the tape" for pinned names (2026-10-16).

Ajay 2026-10-16: "Can you add a watcher tape for IREN please." then "I wwant you to alert me
when the Buyers are winning in tape for IREN today."

One owner-only LIVE kind riding the EXISTING `sepa.cli trade-flash-watch` cron line: the cli
calls `run_pass` AFTER trade_flash.run_watch and its heartbeats, in its own try (AMENDMENTS7 A1 —
a fault here never touches the zone or burst passes).
THE RULE IS THE TAPE TAB'S CHECK 3, BY CALL: signals.delta_check over tape.analyze_tape's delta
(session cumulative delta > 0 AND the last tape.LATE_WINDOW_MIN minutes' delta >= 0, REGULAR prints,
pre-market included) — sides by the TICK RULE (no NBBO pull). One tape.fetch_trades per pinned
name per poll (429s capped at MAX_429). Rings on the flip, never while it holds, re-arms after a
poll that reads it lost; a poll that cannot read the tape never rings and never re-arms. A ring
that reached no device is retried on the next poll that still reads buyers in control, up to
MAX_PUSH_ATTEMPTS sends per flip (AMENDMENTS7 A3). UNMEASURED. Not advice.
"""
from __future__ import annotations

import logging
import time as _time
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from . import trade_flash as TF
from .tape_burst_kinds import KINDS_BUDGET_SEC

log = logging.getLogger("orderflow.tape_control")
ET = ZoneInfo("America/New_York")

# Ajay 2026-10-16 ("alert me when the Buyers are winning in tape for IREN today"): symbol -> the
# LAST session (ET ISO date, inclusive) the pin is read and rings; None = standing (DECISIONS7 K3).
WATCH = {"IREN": "2026-10-16"}   # Ajay 2026-10-16
KIND = "tape_control"            # MINE (DECISIONS7 D1)
EVENTS_COLL = "tape_control_events"   # MINE — its own collection (BUILD_SPEC7 §2: ids can collide with bursts)
STATE_COLL = "tape_control_state"     # MINE — one doc per (symbol, ET session day)
MARK = "\U0001F39A\uFE0F"        # MINE — 🎚️ (U+1F39A, not 🎛️ U+1F39B)
TITLE_FMT = MARK + " {lead} — buyers in control on the tape"   # MINE (D5)
URL_FMT = "/sepa/{sym}?tab=tape&from=alerts"                   # MINE — the Tape tab, "← Alerts" back link
RULE_WORD = "tick rule"          # Cheetah default — tape.tick_rule_sides (analyze_tape with no quotes)
RULE_TAIL = RULE_WORD + " (the Tape tab's quote-rule read can differ)"   # MINE (AMENDMENTS7 A7)
START_BY_SEC = KINDS_BUDGET_SEC  # MINE (reuse) — no tape read STARTS later than this into the poll
MAX_429 = 3                      # MINE (AMENDMENTS7 A4) — HTTP 429 retries per pull before it is a fault
MAX_PUSH_ATTEMPTS = 2            # MINE (AMENDMENTS7 A3) — sends per flip while none reaches a device
UNMEASURED_NOTE = ("UNMEASURED — the Tape verdict's forward ledger (GET /orderflow/ledger/accuracy) measures "
                   "the five-check verdict, not this check alone. Not advice.")
RULE_NOTE = "Sides by the " + RULE_TAIL + "."
FAULT_WORDS = {                   # MINE — why a poll did not read the tape (never a False read)
    "no_prints": "no prints from the provider",
    "no_regular": "no regular prints yet",
    "truncated": "the pull hit the page cap — the newest prints were missing",
    "rate_limited": "the provider kept answering HTTP 429 (rate limited)",
    "error": "the tape read failed",
    "budget": "the poll ran out of time",
    "no_mongo": "the state store was unreachable",
}
NOT_PUSHED_WORDS = {              # MINE (AMENDMENTS7 A3) — why a ring reached no device
    "no_device": "reached no device",
    "not_sent": "reached no device",
    "no_mongo": "not sent: the push store was unreachable",
    "insert_failed": "not sent: the ring was not recorded",
    "error": "not sent: the send failed",
}
TIMES_WORDS = {1: "once", 2: "twice"}   # MINE — "rang twice to no device"
REASON_NO_PIN = "no pin active — every pin has ended"
REASON_NO_MONGO = "state store unreachable — no read, no ring"
REASON_OUTSIDE = "outside the watch window — not read"
COUNT_KEYS = ("pins", "active", "expired", "read", "faults", "in_control", "rang", "pushed",
              "lost_race", "skipped_budget")

__all__ = [
    "WATCH", "KIND", "EVENTS_COLL", "STATE_COLL", "MARK", "TITLE_FMT", "URL_FMT", "RULE_WORD",
    "RULE_TAIL", "START_BY_SEC", "MAX_429", "MAX_PUSH_ATTEMPTS", "UNMEASURED_NOTE", "RULE_NOTE",
    "FAULT_WORDS", "NOT_PUSHED_WORDS", "REASON_NO_PIN", "REASON_NO_MONGO", "REASON_OUTSIDE",
    "COUNT_KEYS", "RateLimited", "et_hhmm", "tape_url", "et_today", "selected", "pins_for",
    "state_id", "initial_state", "prev_core", "decide", "apply_outcome", "read_tape",
    "headline", "pin_text", "status_block", "run_pass",
]


class RateLimited(Exception):
    """The capped pull gave up on HTTP 429s (tape.last_fetch_fault() == "rate_limited")."""


# ── pure helpers ─────────────────────────────────────────────────────────────
def et_hhmm(dt: datetime) -> str:
    """"HH:MM" in ET; a naive input is read as UTC. PURE."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ET).strftime("%H:%M")


def tape_url(sym: str) -> str:
    """The Tape tab of one name, back-linked to /alerts. PURE."""
    return URL_FMT.format(sym=str(sym).upper())


def et_today() -> str:
    """The ET session day as an ISO date (never the container clock's date)."""
    return datetime.now(ET).date().isoformat()


def selected(kinds) -> bool:
    """True when `kinds` (the cli's --kinds) asks for this kind: None / "" / "all", or a comma
    list / iterable naming KIND or "all". PURE."""
    if kinds is None:
        return True
    if isinstance(kinds, str):
        names = [k.strip() for k in kinds.split(",") if k.strip()]
        if not names:
            return True
    else:
        names = [str(k).strip() for k in kinds]
    return KIND in names or "all" in names


def pins_for(day: str, watch: Optional[dict] = None) -> list:
    """[{"symbol", "until", "active"}] sorted by symbol; active iff until is None or
    day <= until (ISO compare). PURE."""
    w = WATCH if watch is None else watch
    out = []
    for sym in sorted(w):
        until = w[sym]
        out.append({"symbol": str(sym).upper(), "until": until,
                    "active": until is None or str(day) <= str(until)})
    return out


def state_id(symbol: str, day: str) -> str:
    return f"{symbol.upper()}:{day}"


def initial_state() -> dict:
    """The keys `decide` owns. `rang` / `push_attempts` / `not_pushed_reason` / `exhausted`
    describe the CURRENT flip's delivery (AMENDMENTS7 A3); `first_read` says the current
    read state began at the day's first read (A6). PURE."""
    return {"in_control": None, "since": None, "since_hhmm": None, "last_read": None,
            "last_read_at": None, "faults": 0, "rings": [], "rang": False,
            "push_attempts": 0, "not_pushed_reason": None, "exhausted": False,
            "first_read": False}


def prev_core(doc: Optional[dict]) -> Optional[dict]:
    """Only the `initial_state()` keys of a stored doc reach `decide`. PURE."""
    if not doc:
        return None
    keys = initial_state().keys()
    return {k: doc[k] for k in keys if k in doc}


def _reset_delivery(s: dict) -> None:
    s.update(rang=False, push_attempts=0, not_pushed_reason=None, exhausted=False)


def decide(prev_state: Optional[dict], read: Optional[dict]) -> tuple:
    """(new_state, ring). PURE — inputs never mutated.

    A None read (a fault) changes nothing but `faults`: never a ring, never a re-arm. A read
    rings when it turns to in control (the day's first read included) and never while it
    holds — except a retry: the last ring of this flip reached no device (`pushed is False`)
    and fewer than MAX_PUSH_ATTEMPTS sends were made. A False read re-arms and resets the
    delivery bookkeeping."""
    s = {**initial_state(), **(prev_state or {})}
    s["rings"] = [dict(r) for r in (s.get("rings") or [])]
    if read is None:
        s["faults"] = int(s.get("faults") or 0) + 1
        return s, False
    was = s.get("in_control")
    now_in = bool(read["in_control"])
    s.update(last_read=dict(read), last_read_at=read["at"], in_control=now_in)
    if was is None or now_in != was:
        s["since"], s["since_hhmm"] = read["at"], read["hhmm"]
        s["first_read"] = was is None
        _reset_delivery(s)
    if not now_in:
        _reset_delivery(s)
    flip = now_in and was is not True
    last = s["rings"][-1] if s["rings"] else {}
    retry = (now_in and was is True and not s.get("exhausted")
             and int(s.get("push_attempts") or 0) < MAX_PUSH_ATTEMPTS
             and last.get("pushed") is False)
    ring = bool(flip or retry)
    if ring:
        s["rings"].append({"at": read["at"], "hhmm": read["hhmm"],
                           "first_read": bool(flip and was is None), "retry": bool(retry)})
    return s, ring


def apply_outcome(state: dict, pushed: bool, reason: Optional[str] = None) -> dict:
    """The state after the send of its last ring. PURE. Reached a device → `rang`; else one
    more attempt, `not_pushed_reason`, and `exhausted` at MAX_PUSH_ATTEMPTS."""
    s = dict(state)
    s["rings"] = [dict(r) for r in (state.get("rings") or [])]
    if s["rings"]:
        s["rings"][-1]["pushed"] = bool(pushed)
        if not pushed:
            s["rings"][-1]["not_pushed_reason"] = reason
    if pushed:
        s.update(rang=True, not_pushed_reason=None)
    else:
        n = int(s.get("push_attempts") or 0) + 1
        s.update(rang=False, push_attempts=n, not_pushed_reason=reason,
                 exhausted=n >= MAX_PUSH_ATTEMPTS)
    return s


# ── the read (one fetch_trades, tick rule, check 3 by call) ──────────────────
def _fetch_capped(symbol, day):
    from . import tape as TP
    df = TP.fetch_trades(symbol, day, max_429=MAX_429)
    if df is None and TP.last_fetch_fault() == "rate_limited":
        raise RateLimited(symbol)
    return df


def read_tape(symbol: str, day, *, at: datetime, fetch_fn=None, analyze_fn=None,
              check_fn=None) -> tuple:
    """(read, None) | (None, fault_key). Never raises."""
    from . import signals as SG
    from . import tape as TP
    fetch_fn = fetch_fn or _fetch_capped
    analyze_fn = analyze_fn or TP.analyze_tape
    check_fn = check_fn or SG.delta_check
    try:
        trades = fetch_fn(symbol, day)
    except RateLimited:
        return None, "rate_limited"
    except Exception:
        return None, "error"
    if trades is None or not len(trades):
        return None, "no_prints"
    if bool(getattr(trades, "attrs", {}).get("truncated", False)):
        return None, "truncated"
    try:
        flow = TP.split_by_kind(trades)["flow"]
        if not len(flow):
            return None, "no_regular"
        t = analyze_fn(trades)                 # quotes OMITTED -> classification.method "tick"
        d = t["delta"]
        if int(d.get("n_trades") or 0) <= 0:
            return None, "no_regular"
        ok = bool(check_fn(d)["pass"])         # signals.delta_check — check 3 BY CALL
        et = at.astimezone(ET)
        return {"at": et.isoformat(), "hhmm": et.strftime("%H:%M"), "hms": et.strftime("%H:%M:%S"),
                "in_control": ok, "delta": int(d["delta"]), "late_delta": int(d["late_delta"]),
                "pct": float(d["delta_pct_of_volume"]), "late_window_min": int(d["late_window_min"]),
                "n_trades": int(d["n_trades"]), "price": float(t["last_price"]),
                "last_print_et": TP.stamp_et(flow.index.max())["time_et"],
                "method": str((t.get("classification") or {}).get("method") or "tick")}, None
    except Exception:
        return None, "error"


# ── served words ─────────────────────────────────────────────────────────────
def _delta_words(r: dict) -> str:
    return ("session delta {pct:+.1f}% of volume ({delta:+,} shares), last {n} min {late:+,} shares"
            .format(pct=float(r["pct"]), delta=int(r["delta"]), n=int(r["late_window_min"]),
                    late=int(r["late_delta"])))


def headline(ev: dict) -> str:
    """W2 — the push body line and the /alerts item line. PURE."""
    first = " · first read today" if ev.get("first_read") else ""
    return "{sym} · {dw} · ${price:.2f} · {hhmm} ET{first} · {tail}".format(
        sym=str(ev["symbol"]).upper(), dw=_delta_words(ev), price=float(ev["price"]),
        hhmm=ev["hhmm"], first=first, tail=RULE_TAIL)


def _num_words(r: dict) -> str:
    return "{dw} · ${price:.2f} · last print {lp} ET".format(
        dw=_delta_words(r), price=float(r["price"]), lp=r.get("last_print_et") or "—")


def _who(r: dict) -> str:
    d, late = int(r["delta"]), int(r["late_delta"])
    if d < 0:
        return "sellers in control for the session"
    if d == 0:
        return "session delta flat"
    if late < 0:
        return "sellers took the last %d min" % int(r["late_window_min"])
    return "buyers in control"


def _rang_words(rings: list) -> str:
    if not rings:
        return ""
    parts = []
    for r in rings:
        h = str(r.get("hhmm") or "")
        if r.get("pushed") is False:
            h += " (%s)" % NOT_PUSHED_WORDS.get(r.get("not_pushed_reason") or "not_sent",
                                                NOT_PUSHED_WORDS["not_sent"])
        parts.append(h)
    return " · rang " + ", ".join(parts) + " ET"


def _fault_tail(doc: dict) -> str:
    lf = doc.get("last_fault") or None
    if not isinstance(lf, dict) or not lf.get("at"):
        return ""
    if doc.get("last_read_at") and str(lf["at"]) <= str(doc["last_read_at"]):
        return ""
    return " · %s ET poll not read: %s" % (lf.get("hhmm") or "—",
                                          FAULT_WORDS.get(lf.get("why"), FAULT_WORDS["error"]))


def _waiting_words() -> str:
    return "watched %s–%s ET on trading days · no read yet today" % (
        TF.WATCH_OPEN_ET.strftime("%H:%M"), TF.WATCH_CLOSE_ET.strftime("%H:%M"))


def pin_text(pin: dict, doc: Optional[dict], now: datetime) -> tuple:
    """(state, text) — W4–W8, no symbol prefix. PURE."""
    if not pin.get("active"):
        return "expired", "pin ended at the close of %s · not read" % pin.get("until")
    day = now.astimezone(ET).date().isoformat() if now.tzinfo else now.date().isoformat()
    if not isinstance(doc, dict) or (doc.get("date") not in (None, day)):
        return "waiting", _waiting_words()
    r = doc.get("last_read")
    if doc.get("in_control") is None or not isinstance(r, dict):
        lf = doc.get("last_fault")
        if isinstance(lf, dict) and lf.get("why"):
            return "no_read", "no read yet today · %s ET poll not read: %s" % (
                lf.get("hhmm") or "—", FAULT_WORDS.get(lf.get("why"), FAULT_WORDS["error"]))
        return "waiting", _waiting_words()
    rang = _rang_words(doc.get("rings") or [])
    ftail = _fault_tail(doc)
    since = doc.get("since_hhmm") or "—"
    if doc.get("in_control") is True:
        lead = ("buyers led at the first read today %s ET" % since if doc.get("first_read")
                else "buyers in control since %s ET" % since)
        exh = ""
        if doc.get("exhausted"):
            n = int(doc.get("push_attempts") or MAX_PUSH_ATTEMPTS)
            exh = " · rang %s to no device — check Notifications" % TIMES_WORDS.get(n, "%d times" % n)
        return "in_control", "%s · %s · read %s ET%s%s%s · %s" % (
            lead, _num_words(r), r.get("hhmm") or "—", rang, exh, ftail, RULE_WORD)
    return "not_in_control", "%s since %s ET · %s · read %s ET · rings when buyers take control%s%s · %s" % (
        _who(r), since, _num_words(r), r.get("hhmm") or "—", rang, ftail, RULE_WORD)


def status_block(now: datetime, *, coll=None) -> dict:
    """{"pins": [...], "note": W9} for GET /alerts/status. WATCH is the truth; a dead / None
    coll leaves every active pin `waiting`. Never raises."""
    note = UNMEASURED_NOTE + " " + RULE_NOTE
    try:
        et = now.astimezone(ET) if now.tzinfo else now.replace(tzinfo=ET)
        day_s = et.date().isoformat()
        docs = {}
        if coll is not None:
            try:
                for d in coll.find({"date": day_s, "kind": KIND}) or []:
                    if isinstance(d, dict) and d.get("symbol"):
                        docs[str(d["symbol"]).upper()] = d
            except Exception as exc:
                log.warning("tape_control: state read failed: %s", exc)
                docs = {}
        pins = []
        for p in pins_for(day_s):
            doc = docs.get(p["symbol"]) if p["active"] else None
            state, text = pin_text(p, doc, et)
            rings = (doc or {}).get("rings") or [] if state in ("in_control", "not_in_control") else []
            pins.append({"symbol": p["symbol"], "date": day_s, "until": p["until"],
                         "active": p["active"], "state": state, "text": text,
                         "url": tape_url(p["symbol"]),
                         "rang": [str(r.get("hhmm")) for r in rings if r.get("hhmm")]})
        return {"pins": pins, "note": note}
    except Exception as exc:
        log.warning("tape_control: status_block failed: %s", exc)
        return {"pins": [], "note": note}


# ── the impure pass ──────────────────────────────────────────────────────────
def _is_dup_key(exc: Exception) -> bool:
    try:
        from pymongo.errors import DuplicateKeyError
        if isinstance(exc, DuplicateKeyError):
            return True
    except Exception:
        pass
    return type(exc).__name__ == "DuplicateKeyError"


def _claim(coll, sid: str, prev: Optional[dict], new: dict) -> tuple:
    """(claimed, rev, why). why ∈ None | "lost_race" | "no_mongo"."""
    body = {k: v for k, v in new.items() if k != "_id"}
    try:
        if prev is None:
            res = coll.update_one({"_id": sid}, {"$setOnInsert": {**body, "rev": 1}}, upsert=True)
            return (getattr(res, "upserted_id", None) is not None), 1, None
        rev = (prev.get("rev") or 0) + 1
        res = coll.update_one({"_id": sid, "rev": prev.get("rev")}, {"$set": {**body, "rev": rev}})
        return int(getattr(res, "modified_count", 0) or 0) == 1, rev, None
    except Exception as exc:
        if _is_dup_key(exc):
            return False, None, "lost_race"
        log.warning("tape_control: claim %s failed: %s", sid, exc)
        return False, None, "no_mongo"


def _outcomes(events: list, rec: Optional[dict], raised: bool) -> dict:
    """{event_id: (pushed, reason)} from record_and_push's result. PURE."""
    out = {}
    if raised or not isinstance(rec, dict):
        return {ev["_id"]: (False, "error") for ev in events}
    if not rec.get("ok", True):
        why = "no_mongo" if "mongo" in str(rec.get("reason") or "") else "error"
        return {ev["_id"]: (False, why) for ev in events}
    if "fresh_ids" in rec:
        fresh = set(rec.get("fresh_ids") or [])
    else:
        fresh = {ev["_id"] for ev in events} if int(rec.get("new") or 0) > 0 else set()
    for ev in events:
        if ev["_id"] not in fresh:
            out[ev["_id"]] = (False, "insert_failed")
        elif rec.get("pushed"):
            out[ev["_id"]] = (True, None)
        else:
            out[ev["_id"]] = (False, "not_sent")
    return out


def _event(sym: str, day_s: str, read: dict, state: dict) -> dict:
    last = state["rings"][-1]
    return {"_id": TF.event_id(sym, day_s, read["hms"]), "kind": KIND, "symbol": sym.upper(),
            "et_date": day_s, "time_et": read["hms"], "hhmm": read["hhmm"],
            "delta": read["delta"], "late_delta": read["late_delta"], "pct": read["pct"],
            "late_window_min": read["late_window_min"], "n_trades": read["n_trades"],
            "price": read["price"], "last_print_et": read["last_print_et"],
            "method": read["method"], "ring_n": len(state["rings"]),
            "first_read": bool(last.get("first_read")), "retry": bool(last.get("retry")),
            "recorded_at": int(_time.time())}


def run_pass(*, now: datetime, poll_ts: Optional[int] = None, started: Optional[float] = None,
             dry_run: bool = False, fetch_fn=None, db=None, record_fn=None, status_fn=None,
             clock=_time.monotonic) -> dict:
    """One poll over the active pins (BUILD_SPEC7 §3.5 as amended by AMENDMENTS7 A3/A5/A9).
    `ran` = no active pin, or at least one good read. Never raises (best-effort writes)."""
    et_now = now.astimezone(ET) if now.tzinfo else now.replace(tzinfo=ET)
    day = et_now.date()
    day_s = day.isoformat()
    now_iso = et_now.isoformat()
    counts = {k: 0 for k in COUNT_KEYS}
    pins = pins_for(day_s)
    active = [p for p in pins if p["active"]]
    counts.update(pins=len(pins), active=len(active), expired=len(pins) - len(active))

    def _status(reason):
        if dry_run:
            return
        try:
            fn = status_fn
            if fn is None:
                from supply_demand import alert_status as AS
                fn = AS.record_pass
            fn(KIND, dict(counts), now, reason=reason)
        except Exception as exc:                     # best-effort, never fatal
            log.warning("%s: record_pass failed: %s", KIND, exc)

    def _done(reason, extra=None):
        ran = counts["active"] == 0 or counts["read"] >= 1
        _status(reason)
        log.info("TAPE-CONTROL: %s", {**counts, "reason": reason})
        out = {"ran": ran, **counts}
        if reason:
            out["reason"] = reason
        if extra:
            out.update(extra)
        return out

    if not active:
        return _done(REASON_NO_PIN, {"dry_run": True, "would_push": 0, "reads": []} if dry_run else None)
    if not dry_run and not TF.in_window(et_now):
        log.info("TAPE-CONTROL: outside the window, not read")
        return {"ran": False, **counts, "reason": REASON_OUTSIDE}

    d = db if db is not None else TF._db()
    if d is None:
        counts["faults"] += len(active)
        return _done(REASON_NO_MONGO, {"dry_run": True, "would_push": 0, "reads": []} if dry_run else None)
    try:
        coll = d[STATE_COLL]
    except Exception:
        counts["faults"] += len(active)
        return _done(REASON_NO_MONGO, {"dry_run": True, "would_push": 0, "reads": []} if dry_run else None)

    events, ring_meta, reads, fault_words = [], [], [], []
    for p in active:
        sym = p["symbol"]
        sid = state_id(sym, day_s)
        try:
            prev = coll.find_one({"_id": sid})
        except Exception as exc:
            log.warning("tape_control: state read %s failed: %s", sid, exc)
            counts["faults"] += 1
            fault_words.append(FAULT_WORDS["no_mongo"])
            reads.append({"symbol": sym, "read": None, "fault": "no_mongo", "would_ring": False,
                          "text": FAULT_WORDS["no_mongo"]})
            continue
        if started is not None and clock() - started >= START_BY_SEC:
            read, fault = None, "budget"
            counts["skipped_budget"] += 1
        else:
            read, fault = read_tape(sym, day, at=et_now, fetch_fn=fetch_fn)
        new, ring = decide(prev_core(prev), read)
        if read is None:
            counts["faults"] += 1
            fault_words.append(FAULT_WORDS.get(fault, FAULT_WORDS["error"]))
        else:
            counts["read"] += 1
            if read["in_control"]:
                counts["in_control"] += 1
        new.update(_id=sid, symbol=sym, date=day_s, kind=KIND, until=p["until"], last_pass=now_iso,
                   last_fault=({"at": now_iso, "hhmm": et_now.strftime("%H:%M"), "why": fault}
                               if fault else (prev or {}).get("last_fault")),
                   created_at=(prev or {}).get("created_at") or now_iso)
        if ring:
            new["rings"][-1]["event_id"] = TF.event_id(sym, day_s, read["hms"])
            new["rings"][-1]["pushed"] = None
        if dry_run:
            reads.append({"symbol": sym, "read": read, "fault": fault, "would_ring": ring,
                          "text": pin_text(p, new, et_now)[1]})
            if ring:
                events.append(_event(sym, day_s, read, new))
            continue
        claimed, rev, why = _claim(coll, sid, prev, new)
        if not claimed:
            if why == "no_mongo":
                counts["faults"] += 1
                fault_words.append(FAULT_WORDS["no_mongo"])
                if read is not None:
                    counts["read"] -= 1
                    if read["in_control"]:
                        counts["in_control"] -= 1
            else:
                counts["lost_race"] += 1
            continue
        if ring:
            ev = _event(sym, day_s, read, new)
            events.append(ev)
            ring_meta.append((sid, rev, new, ev["_id"]))

    rec = {}
    if events:
        counts["rang"] = len(events)
        raised = False
        try:
            rec = (record_fn or TF.record_and_push)(
                events, kind=KIND, coll_name=EVENTS_COLL, title_fmt=TITLE_FMT,
                headline_fn=headline, url_fn=tape_url, precheck_colls=(),
                fresh_since=poll_ts, dry_run=dry_run) or {}
        except Exception as exc:
            log.warning("%s push failed: %s", KIND, exc)
            raised, rec = True, {}
        if not dry_run:
            counts["pushed"] = int(bool(rec.get("pushed")))
            outcomes = _outcomes(events, rec, raised)
            for sid, rev, state, eid in ring_meta:
                pushed, why = outcomes.get(eid, (False, "error"))
                done = apply_outcome(state, pushed, why)
                patch = {k: done[k] for k in ("rings", "rang", "push_attempts",
                                              "not_pushed_reason", "exhausted")}
                try:
                    coll.update_one({"_id": sid, "rev": rev}, {"$set": patch})
                except Exception as exc:              # best-effort: a pending ring is never retried
                    log.warning("tape_control: outcome patch %s failed: %s", sid, exc)

    reason = None
    if counts["read"] == 0 and fault_words:
        reason = "; ".join(dict.fromkeys(fault_words))
    extra = None
    if dry_run:
        extra = {"dry_run": True, "would_push": int(rec.get("would_push", 0) or 0) if events else 0,
                 "reads": reads}
    return _done(reason, extra)
