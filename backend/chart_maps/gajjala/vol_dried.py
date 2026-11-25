"""💧 "Armed, volume dried" — a push + forward tracker on 🚩 Gajjala (GG5), a pass step of the 5-minute pass (2026-11-24).

Ajay, verbatim (2026-11-24): "Can you track something for me how many times have the stocks bumped right after volume
dried up.. I noticed that the best entries so far have been after volume dried up.. after all the other rules. Can you
send me notification of volume dried please.." GG S9 1:57:33 (playbook.py): "volume completely dried out and the price
is not going down … then it makes a big move." Spec: scratchpad voldry/spec.md REV 2 §3.2.

WHAT RINGS (kind GC.VOL_DRIED_PUSH_KIND, LIVE at build — GC.VOL_DRIED_PUSH_MODE): ONCE per (session, symbol, setup),
on the GG5 cron pass where BOTH hold —
  * the card is "trigger armed" (potential.potential_kind == "armed": every rule met, only the break missing) WITH its
    own K3 volume-dried row met (tab.vol_dried_text — the 💧 chip's ONE engine);
  * entry_marks.ready_since(tracker) == potential._utc(now): the 🧠 tracker's armed entry was stamped BY THIS PASS, so
    it was not so at the previous cron sighting. A datetime compare, never strings; a joined doc's first entry is
    already None inside ready_since. run.py hands the SAME `now` to the 🧠 step and this one — that is what makes the
    equality hold.
On today's rules K3 is a hard row of all five setups, so every "trigger armed" card has met it: this usually rings on
the same pass as the 🧠 armed push (the twin — HIS CALL #1 of the spec).

GATE ORDER (every refusal COUNTED, never written, never consuming the claim): not armed (uncounted) · no vol row ·
no tracker doc / not turned this pass (`steady`) · no plan (`no_risk`) · closed day (alerts._closed_reason) · the 🧠
window (potential.window_reason → `outside_hours` / `muted`) · no print in the bar that just closed
(GC.POTENTIAL_FRESH_TAPE + potential.fresh_tape → `stale_tape`) · GG's K11 session floor (GC.K11_MIN_SESSION_VOLUME on
the pass's own volume read; unknown → held, `under_floor`) · dry · no alert collection (`no_store`) · the insert-only
claim (demand_alerts.claim_key, "GGD:" in gajjala_alerts, BEFORE the send) · mode "off" → recorded `dried_shadow`,
the sender is NEVER called (the A+ shadow precedent) · live: the owner-scoped send (push.hooks.notify_gajjala_vol_dried)
→ alerts._settle. A held transition never rings later (the A+ precedent — HIS CALL #2).

CLAIM FAULT (fail-open, bounded): demand_alerts.claim_key reads True on a WRITE error (the house helper shared by the
A+ / 🔀 / 🩳 pushes). That pass sends ONCE with no record (the settle likely fails too). Bounded to ONE send, because
the transition holds for one pass only. This module never claims "never a claim-less send".

THE TRACKER: the claim doc IS the forward record. States are `dried_*` words only (never a store.LEDGER_ALERT_STATES
word, so the 🏁 never reads them; the prefix "GGD:" is never "GG:", so the 🚩 lane and stream never read them).
The nightly at GC.LEDGER_GRADE_AT_ET (grade_night) grades every RECORDED doc with ledger.grade — the ONE trade-math engine — plus stop
first, the best high before the first stop touch (that minute excluded) and that high in R. A ring at/after the
regular close also loads its ring evening, so an evening stop-out counts. UNMEASURED — a description, not an entry.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Callable, Optional

from . import alerts as AL
from . import constants as GC
from . import ema_cross as EX
from . import entry_marks as EM
from . import potential as PT
from . import variant as V

log = logging.getLogger("chart_maps.gajjala.vol_dried")

KIND = GC.VOL_DRIED_PUSH_KIND
STATES = ("dried_claimed", "dried_pushed", "dried_no_target", "dried_failed", "dried_shadow")
RECORDED = STATES[1:]                       # every claimed state but the in-flight one — graded and counted
RANG = (STATES[1],)                         # reached a device
COUNT_KEYS = ("armed", "no_vol_row", "no_tracker", "steady", "no_risk", "closed_day", "outside_hours", "muted",
              "stale_tape", "under_floor", "dry", "no_store", "claimed_before", "shadow", "pushed", "no_target",
              "failed")
TITLE = "💧 Armed, volume dried · {sym} · {emoji} {label}"
TAG_PREFIX = "gg-dry"                       # never "gg-pot": the 🧠 notification is not replaced on the device
GRADE_VERSION = 1                           # TRANSPORT — bump to re-grade the lookback window
TEXTS = {
    "none": "💧 Volume dried: none in the last {n} sessions{off} · UNMEASURED",
    "count": ("💧 {rec}{rang} rang · {trig} triggered · {win} hit {r} · {stop} stop-first — last {n} sessions"
              "{pend}{off} · UNMEASURED"),
}
REC = "{rec} recorded · "
PEND = " · {k} not graded yet"
OFF_TAIL = " · pushes off now, recording only"
STEP_KEYS = ("rows", "graded", "already", "not_due", "deferred_cap", "load_failed", "no_bars", "split",
             "split_check_failed", "faulted", "written")
_ID_PREFIX = GC.VOL_DRIED_CLAIM_PREFIX + ":"


# ── small reads ───────────────────────────────────────────────────────────────────────────────────────────────────
def mode() -> str:
    """GC.VOL_DRIED_PUSH_MODE when it is one of GC.VOL_DRIED_PUSH_MODES, else "off" (junk fails closed). CALL time."""
    m = GC.VOL_DRIED_PUSH_MODE
    return m if isinstance(m, str) and m in GC.VOL_DRIED_PUSH_MODES else GC.VOL_DRIED_PUSH_MODES[0]


def _iso(session) -> str:
    return session.isoformat()[:10] if isinstance(session, (date, datetime)) else str(session or "")[:10]


def claim_key(session, sym, setup) -> str:
    """"GGD:{date}|{SYM}|{setup}" — one per (session, symbol, setup)."""
    return f"{GC.VOL_DRIED_CLAIM_PREFIX}:{_iso(session)}|{str(sym or '').upper()}|{setup}"


def vol_row(read) -> Optional[dict]:
    """The read's criteria row of key detectors.K3_VOL_KEY, ONLY when the 💧 chip's own test (tab.vol_dried_text)
    answers VOL_DRIED_TEXT; else None."""
    from . import detectors as D
    from . import tab as GT                                     # lazy: tab imports half the package
    if not isinstance(read, dict) or GT.vol_dried_text(read) != GT.VOL_DRIED_TEXT:
        return None
    return next((c for c in read.get("criteria") or []
                 if isinstance(c, dict) and c.get("key") == D.K3_VOL_KEY and c.get("ok") is True), None)


def in_state(read) -> bool:
    """"Trigger armed" (every rule but the break) AND its own K3 volume-dried row met."""
    return PT.potential_kind(read) == GC.POTENTIAL_KINDS[0] and vol_row(read) is not None


def turned_now(doc, now) -> bool:
    """The tracker's armed entry was stamped by THIS pass: EM.ready_since(doc) == PT._utc(now) (datetimes)."""
    at = EM.ready_since(doc)
    return at is not None and isinstance(now, datetime) and at == PT._utc(now)


def compose(sym, setup, read, *, broker_text=None, trader_text=None, promo_text=None) -> dict:
    """The device payload. Every number is the read's own; prices through tab._px. NO `items` (push/recent untouched)."""
    from .tab import BROKER_FLAG_ICON, _px
    sym = str(sym or "").upper()
    read = read if isinstance(read, dict) else {}
    emoji, label = PT._setup_meta(setup)
    bt = broker_text if isinstance(broker_text, str) and broker_text.strip() else ""
    title = TITLE.format(sym=sym, emoji=emoji, label=label) + (f" · {BROKER_FLAG_ICON}" if bt else "")
    row = vol_row(read) or {}
    row_bit = (f"{row.get('label')} ({row.get('value')})"
               if isinstance(row.get("label"), str) and row.get("label") else "")
    bits = [f"trigger {_px(read.get('trigger'))}", f"stop {_px(read.get('stop'))}{PT._risk_bit(read)}", row_bit,
            trader_text, promo_text, bt, PT.TAIL]
    body = " · ".join(b for b in bits if isinstance(b, str) and b.strip())
    return {"title": title, "body": body, "tag": f"{TAG_PREFIX}-{setup}-{sym}", "url": PT.deep_link(sym, setup),
            "kind": KIND, "ticker": sym}


def _send(owner: str, payload: dict) -> dict:
    from push import hooks
    return hooks.notify_gajjala_vol_dried(owner=owner, payload=payload)


def _broker_flags(st):
    try:
        from . import store as ST
        return frozenset(ST.broker_flags(st)[0])
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala 💧: broker list read failed: %s", type(exc).__name__)
        return None


def _broker_text(sym, flags) -> Optional[str]:
    try:
        from .tab import broker_text_for
        return broker_text_for(sym, flags) if flags is not None else None
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala 💧: broker clause failed: %s", type(exc).__name__)
        return None


def _str(x) -> Optional[str]:
    return x if isinstance(x, str) and x.strip() else None


# ── the pass step ─────────────────────────────────────────────────────────────────────────────────────────────────
def run_step(st, reads, frames, now, session, *, volume, ctx=None, owner=None, send: Optional[Callable] = None,
             dry=False) -> dict:
    """Judge every armed (sym, setup) of THIS pass → counts (COUNT_KEYS). See the module docstring for the order."""
    counts = {k: 0 for k in COUNT_KEYS}
    if st is None or not V.is_gg5(V.of(st)):
        return counts                                           # GG1 / GGA / 🥇 never run it
    from . import ledger as LG
    reads = reads if isinstance(reads, dict) else {}
    frames = frames if isinstance(frames, dict) else {}
    vol_up = {str(s).upper(): n for s, n in (volume or {}).items()} if isinstance(volume, dict) else {}
    ctx_up = {str(s).upper(): c for s, c in (ctx or {}).items()} if isinstance(ctx, dict) else {}
    fr_up = {str(s).upper(): f for s, f in frames.items()}
    order = {s: i for i, s in enumerate(GC.SETUPS)}
    cands = []
    for sym in sorted(reads, key=lambda s: str(s).upper()):
        by_setup = reads.get(sym) or {}
        if not isinstance(by_setup, dict):
            continue
        for setup in sorted(by_setup, key=lambda k: (order.get(k, len(order)), str(k))):
            r = by_setup.get(setup)
            if PT.potential_kind(r) == GC.POTENTIAL_KINDS[0]:
                cands.append((str(sym).upper(), setup, r))
    if not cands:
        return counts
    docs = st.potentials(session)
    if docs is None:                                            # a tracker read fault — never "no transition"
        counts["armed"] = counts["no_tracker"] = len(cands)
        return counts
    by_id = {d.get("_id"): d for d in docs if isinstance(d, dict) and d.get("_id")}
    send = send or _send
    closed = hours = coll = None
    coll_read = flags_read = False
    flags = None
    m = mode()
    for sym, setup, r in cands:
        counts["armed"] += 1
        row = vol_row(r)
        if row is None:
            counts["no_vol_row"] += 1
            continue
        doc = by_id.get(PT.doc_id(session, sym, setup))
        if doc is None:
            counts["no_tracker"] += 1
            continue
        if not turned_now(doc, now):
            counts["steady"] += 1
            continue
        if LG.plan_of(r.get("trigger"), r.get("stop"))[0] != LG.PLANS[0]:
            counts["no_risk"] += 1
            continue
        if closed is None:
            closed = AL._closed_reason(now) or ""
        if closed:
            counts["closed_day"] += 1
            continue
        if hours is None:
            hours = PT.window_reason(now, session) or ""
        if hours:
            counts[hours] += 1
            continue
        if GC.POTENTIAL_FRESH_TAPE and not PT.fresh_tape(fr_up.get(sym), now):
            counts["stale_tape"] += 1
            continue
        sv = EX.finite(vol_up.get(sym))                         # None / NaN / inf / bool / text → unknown → held
        if sv is None or sv < GC.K11_MIN_SESSION_VOLUME:
            counts["under_floor"] += 1
            continue
        if dry:
            counts["dry"] += 1
            continue
        if not coll_read:
            coll, coll_read = st.alerts_coll(), True
        if coll is None:
            counts["no_store"] += 1
            continue
        c = ctx_up.get(sym) if isinstance(ctx_up.get(sym), dict) else {}
        key = claim_key(session, sym, setup)
        state0 = STATES[4] if m == GC.VOL_DRIED_PUSH_MODES[0] else STATES[0]
        cdoc = {"date": _iso(session), "symbol": sym, "setup": setup, "frame": r.get("frame"),
                "bar_t": r.get("as_of_bar_t"), "trigger": LG._num(r.get("trigger")), "stop": LG._num(r.get("stop")),
                "risk_pct": LG._num(r.get("risk_pct")), "price": PT._frame_close(fr_up.get(sym)), "kind": KIND,
                "mode": m, "state": state0, "at": PT._utc(now).isoformat(), "at_et": PT._hhmm(now),
                "transition_at": EM.ready_since(doc).isoformat(),
                "vol_row": {k: row.get(k) for k in ("label", "value", "need")}}
        if _str(c.get("trader")):
            cdoc["trader"] = c["trader"]
        if c.get("promo") is True:
            cdoc["promo"] = True
            if _str(c.get("promo_text")):
                cdoc["promo_text"] = c["promo_text"]
        from supply_demand.demand_alerts import claim_key as _claim
        if not _claim(coll, key, cdoc):                         # BEFORE the send; a write fault reads True (fail-open)
            counts["claimed_before"] += 1
            continue
        if m == GC.VOL_DRIED_PUSH_MODES[0]:
            counts["shadow"] += 1                               # recorded, the sender is NEVER called
            continue
        try:
            if not flags_read:
                flags, flags_read = _broker_flags(st), True
            payload = compose(sym, setup, r, broker_text=_broker_text(sym, flags),
                              trader_text=_str(c.get("trader_text")), promo_text=_str(c.get("promo_text")))
            res = send(owner or AL._owner(), payload) or {}
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala 💧: send failed for %s %s: %s", sym, setup, type(exc).__name__)
            counts["failed"] += 1
            AL._settle(coll, key, {"state": STATES[3], "result": {"error": type(exc).__name__}})
            continue
        sent, targets = int(res.get("sent") or 0), int(res.get("total_targets") or 0)
        state = STATES[1] if sent > 0 else STATES[2] if targets == 0 else STATES[3]
        counts[{STATES[1]: "pushed", STATES[2]: "no_target"}.get(state, "failed")] += 1
        AL._settle(coll, key, {"state": state, "result": {k: res.get(k) for k in ("sent", "failed", "total_targets",
                                                                                  "skipped")}})
    return counts


# ── the grade (pure) ──────────────────────────────────────────────────────────────────────────────────────────────
def _pct(hi, x) -> Optional[float]:
    from . import ledger as LG
    h, b = LG._num(hi), LG._num(x)
    if h is None or b is None or b <= 0:
        return None
    return round((h / b - 1) * 100, 2)


def grade_row(doc: dict, bars_1m: list, bounds: Optional[dict]) -> dict:
    """One recorded ring → ledger.grade's same column (GG's trade math) + stop first, the best high before the first
    stop touch (that minute excluded — its order inside the minute is unknown), that high vs the ring price and the
    trigger, and in R (ledger.r_past). `won` = outcome "win" (+LEDGER_R_MULT R before the stop)."""
    from . import ledger as LG
    doc = doc if isinstance(doc, dict) else {}
    trig, stop = LG._num(doc.get("trigger")), LG._num(doc.get("stop"))
    plan = LG.plan_of(trig, stop)[0]
    alert = {"at_utc": LG._parse_at(doc.get("at")), "trigger": trig, "stop": stop, "plan": plan}
    g = LG.grade(alert, bars_1m, bounds, GC.LEDGER_HORIZONS[0])
    elig = ([b for b in bars_1m or [] if bounds["fill_from"] <= b[0] < bounds["same_end"]]
            if isinstance(bounds, dict) and bounds else [])
    stop_t = None
    if stop is not None and stop >= 0:
        ds = LG._D(stop)
        stop_t = next((b[0] for b in elig if LG._D(b[3]) <= ds), None)
    fill_t = LG._parse_at(g.get("fill_t"))
    stop_first = stop_t is not None and (g.get("entry") != "filled" or (fill_t is not None and stop_t < fill_t))
    pre = [b for b in elig if stop_t is None or b[0] < stop_t]
    max_high = max((float(b[2]) for b in pre), default=None)
    out = {k: g.get(k) for k in ("entry", "fill_px", "fill_t", "outcome", "reason", "best_pct", "bars_n", "end_t")}
    out.update(triggered=g.get("entry") == "filled", won=g.get("outcome") == "win", stop_first=bool(stop_first),
               stop_t=LG._iso_t(stop_t), max_high=max_high,
               max_vs_ring_pct=_pct(max_high, doc.get("price")), max_vs_trigger_pct=_pct(max_high, trig),
               r_max=LG.r_past(trig, stop, max_high) if max_high is not None else None, version=GRADE_VERSION)
    return out


def _sessions_lookback(now) -> list:
    from . import context as CX
    from . import ledger as LG
    from . import nightly as NG
    return CX.history_window(LG._next_market_day(NG.default_session(now)), GC.LEDGER_GRADE_LOOKBACK_SESSIONS)


def _recorded(coll, days: list) -> list:
    """Every GGD doc of these dates in a RECORDED state (one find; the prefix and state re-checked here)."""
    rows = coll.find({"_id": {"$regex": "^" + _ID_PREFIX}, "date": {"$in": list(days)},
                      "state": {"$in": list(RECORDED)}})
    return [d for d in rows or [] if isinstance(d, dict) and str(d.get("_id") or "").startswith(_ID_PREFIX)
            and d.get("state") in RECORDED]


def _current(doc) -> bool:
    g = (doc or {}).get("grade")
    return isinstance(g, dict) and g.get("version") == GRADE_VERSION


def grade_step(store, now: datetime, *, load_day: Optional[Callable] = None, split_lookup: Optional[Callable] = None,
               max_loads: Optional[int] = None, dry: bool = False) -> dict:
    """The nightly grade of every recorded 💧 ring of the ledger's lookback whose same session has ended
    (now ≥ same_end + ledger.SETTLE) and is not graded at GRADE_VERSION. A ring at/after the regular close loads its
    ring date AND its same session (merged): the evening's prints count for stop first and the best high; fills stay
    on GG's fill window of the same session (ledger.fill_window). Loads through one memo, capped at
    GC.LEDGER_BACKFILL_MAX_SYMBOL_DAYS (the rest `deferred_cap`). A failed load is retried, never written."""
    from . import ledger as LG
    now = LG._aware(now)
    sessions = _sessions_lookback(now)
    out: dict = {"sessions": [d.isoformat() for d in sessions], "read_fault": False, "dry": bool(dry)}
    out.update({k: 0 for k in STEP_KEYS})
    coll = store.alerts_coll() if store is not None else None
    if coll is None:
        out["read_fault"] = True
        return out
    try:
        rows = _recorded(coll, [d.isoformat() for d in sessions])
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala 💧 grade: read failed: %s", type(exc).__name__)
        out["read_fault"] = True
        return out
    out["rows"] = len(rows)
    cap = int(max_loads) if max_loads is not None else int(GC.LEDGER_BACKFILL_MAX_SYMBOL_DAYS)
    load = load_day or LG._default_load_day
    split = split_lookup or LG._default_split_lookup(store)
    memo: dict = {}
    loads = [0]
    now_iso = now.isoformat()

    def days_for(sym: str, days: list) -> tuple:
        miss = [d for d in days if (sym, d) not in memo]
        if loads[0] + len(miss) > cap:
            return "deferred_cap", {}
        for d in miss:
            loads[0] += 1
            try:
                res = load(sym, d)
                bars, failed = (res if isinstance(res, tuple) else (res, False))
                bars = bars if isinstance(bars, list) else LG.bars_from_frame(bars)
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala 💧 grade: load raised for %s %s: %s", sym, d, type(exc).__name__)
                bars, failed = None, True
            memo[(sym, d)] = (bars or [], bool(failed))
        if any(memo[(sym, d)][1] for d in days):
            return "load_failed", {}
        return "ok", {d: memo[(sym, d)][0] for d in days}

    def write(doc, g):
        out["graded"] += 1
        if dry:
            return
        AL._settle(coll, doc["_id"], {"grade": g, "graded_at": now_iso})
        out["written"] += 1

    for doc in sorted(rows, key=lambda d: str(d.get("_id"))):
        try:
            if _current(doc):
                out["already"] += 1
                continue
            at = LG._parse_at(doc.get("at"))
            d0 = LG._as_date(doc.get("date"))
            if at is None or d0 is None:
                write(doc, grade_row(doc, [], None))
                continue
            b = LG.session_bounds(d0, at)
            if now < b["same_end"] + LG.SETTLE:
                out["not_due"] += 1
                continue
            if LG.plan_of(doc.get("trigger"), doc.get("stop"))[0] != LG.PLANS[0]:
                write(doc, grade_row(doc, [], b))
                continue
            sym = str(doc.get("symbol") or "").upper()
            after_close = b["same_date"] != d0
            if after_close:
                sp = split(sym, d0, b["same_date"])
                if sp is None:
                    out["split_check_failed"] += 1
                    continue
                if sp:
                    out["split"] += 1
                    write(doc, {"reason": "split", "split_on": sp if isinstance(sp, str)
                                else b["same_date"].isoformat(), "version": GRADE_VERSION})
                    continue
            days = [d0, b["same_date"]] if after_close else [b["same_date"]]
            status, by_day = days_for(sym, days)
            if status != "ok":
                out[status] += 1
                continue
            if not by_day[b["same_date"]]:
                out["no_bars"] += 1                             # a feed gap — retried
                continue
            write(doc, grade_row(doc, LG._merge(*by_day.values()), b))
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala 💧 grade: row %s faulted: %s", doc.get("_id"), type(exc).__name__)
            out["faulted"] += 1
    return out


def grade_night(now) -> dict:
    """{"grade": grade_step(ST.default(), now)} or {"error": "grade: <Type>"}. Never raises."""
    try:
        from . import store as ST
        return {"grade": grade_step(ST.default(), now)}
    except Exception as exc:                                    # noqa: BLE001
        log.exception("gajjala nightly: the 💧 vol dried grade failed")
        return {"error": f"grade: {type(exc).__name__}"}


# ── the served line + the ℹ️ clause ───────────────────────────────────────────────────────────────────────────────
def count_block(store, session) -> dict:
    """{"mode", "text"} — the ONE count line over the last GC.LEDGER_SPAN_SESSIONS_LONG sessions. Ints only. A read
    fault RAISES (tab's _soft serves None)."""
    from . import context as CX
    from . import ledger as LG
    sessions = CX.history_window(LG._next_market_day(LG._as_date(session)), GC.LEDGER_SPAN_SESSIONS_LONG)
    coll = store.alerts_coll() if store is not None else None
    if coll is None:
        raise RuntimeError("no gajjala_alerts handle")
    rows = _recorded(coll, [d.isoformat() for d in sessions])
    m = mode()
    off = OFF_TAIL if m == GC.VOL_DRIED_PUSH_MODES[0] else ""
    n = GC.LEDGER_SPAN_SESSIONS_LONG
    if not rows:
        return {"mode": m, "text": TEXTS["none"].format(n=n, off=off)}

    def g(d) -> dict:
        x = d.get("grade")
        return x if isinstance(x, dict) else {}
    rec = len(rows)
    rang = sum(1 for d in rows if d.get("state") in RANG)
    trig = sum(1 for d in rows if g(d).get("triggered") is True)
    win = sum(1 for d in rows if g(d).get("won") is True)
    stop = sum(1 for d in rows if g(d).get("stop_first") is True)
    k = sum(1 for d in rows if not _current(d))
    text = TEXTS["count"].format(rec=REC.format(rec=rec) if rec != rang else "", rang=rang, trig=trig, win=win,
                                 r=f"+{GC.LEDGER_R_MULT:g}R", stop=stop, n=n,
                                 pend=PEND.format(k=k) if k > 0 else "", off=off)
    return {"mode": m, "text": text}


def rules_line() -> str:
    """The ℹ️ panel clause — every number from the constants at CALL time, never typed."""
    from . import detectors as D
    w = PT._clock_words()
    return (f"💧 Armed, volume dried ({KIND}, mode {mode()}): rings once per name, setup and session on the first "
            f"{w['cadence']}-minute pass where a card's every rule but the break is met (\"trigger armed\") and its own "
            f"K3 volume-dried row is met — every pullback / base bar at most {D.part_words(GC.K3_VOL_FRAC)} the "
            f"run-up's average bar — when it was not so at the pass before; {w['open']}–{w['close']} ET, never "
            f"{w['rth_open']}–{w['mute_end']} (his first {w['n']} minutes), never on a closed day, held under GG's "
            f"{GC.K11_MIN_SESSION_VOLUME:,}-share session floor or without a print in the bar that just closed; a held "
            f"one does not ring later. With the mode off each would-be ring is recorded, never sent. Each one is "
            f"graded at the {GC.LEDGER_GRADE_AT_ET} ET nightly: triggered (GG's fill rule, from "
            f"{GC.LEDGER_FILL_FROM_ET:%H:%M} ET), hit +{GC.LEDGER_R_MULT:g}R before the stop, stop touched first, best "
            f"high before any stop touch vs the ring price and the trigger, in R off the card's stop; an after-close "
            f"ring counts its evening too. On today's rules every \"trigger armed\" card has already met K3, so it "
            f"usually rings on the same pass as the 🧠 armed push. UNMEASURED — a description, not an entry.")


__all__ = ["KIND", "STATES", "RECORDED", "RANG", "COUNT_KEYS", "TITLE", "TAG_PREFIX", "GRADE_VERSION", "TEXTS", "REC",
           "PEND", "OFF_TAIL", "STEP_KEYS", "mode", "claim_key", "vol_row", "in_state", "turned_now", "compose",
           "run_step", "grade_row", "grade_step", "grade_night", "count_block", "rules_line"]
