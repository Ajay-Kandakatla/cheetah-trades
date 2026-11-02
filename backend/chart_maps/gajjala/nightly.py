"""Gajjala's tab — the 20:15 ET nightly (spec §3.10): float warm, the 30-session halt-history backfill, and the 🎾
squeeze-history warm for the NEXT session.

    python -m chart_maps.gajjala.nightly [--session YYYY-MM-DD] [--steps floats,halts,history,grade]

The pass (run.py) computes the bounded in-pass part; this job does the rest once the tape is shut, for tomorrow:
  floats   every name listed tomorrow (qualified today or the session before — scanner.listed_symbols) + tonight's
           after-hours carry set: the float chain of context.floats_for, Yahoo paced at FLOAT_FETCH_INTERVAL_SEC and
           stopped by the first 429 (the back-off state is the pass's own).
  halts    every session of the chip's window (the K8_HISTORY_SESSIONS market days up to and including today) not yet
           read in full from Nasdaq Trader's dated list (`halts.get_halts_for_date`, one GET each, measured
           2026-10-13 — scripts/gajjala_halts_history_probe.py): 30 on the first night, then 1. A session the live
           passes recorded is read once more in full (a host-sleep gap in the live rows would otherwise stay).
           A failed read is retried the next night; nothing is marked read on a failure — and a read with ZERO
           halts that day counts as failed (probed sessions: 28 to 95; an empty list is a feed miss, not a calm day).
  history  the 🎾 chip for every name above, stored under TOMORROW's date (the session it is shown in).
  grade    🏁 the Track record (2026-10-16, ledger.grade_step) — LAST, in its own try: every 🧠 push that rang and every
           A+ shadow / live claim of the last LEDGER_GRADE_LOOKBACK_SESSIONS market days whose column has ended is
           graded by GG's trade math into gajjala_ledger (same session on the night it ends, next session the night
           after). The existing 20:15 crontab line runs it — it passes no --steps, so every STEPS entry runs.
Writes only the gajjala_* collections + the house `intraday_cache` (the loader caches a completed day it fetched);
one Massive splits call per walked next-session row. Read-only on every other provider. Idempotent: a second run the same night reads
nothing new (halts) and serves the stored chips (history).

🚩 The 1-minute page (2026-10-27, BUILD_SPEC27 §3.6 — Ajay "do everything and also add the track record for it from
today.."): `main` then grades the GG1 record (`ledger.grade_step(store.for_variant(GG1), now)` → gajjala_1m_ledger),
AFTER GG5's run and only when "grade" is a step, in its OWN try: its summary lands under `gajjala_1m`, a failure there
is logged and named under `gajjala_1m.error` — never in GG5's `errors`, never in the exit code. floats / halts / history
are shared data GG5's run already warmed.

🧪 Gajjala · Audited (2026-11-01 — Ajay "create a new tab for Gajjals when you modifiy with audit of End of day..
Gajjals-Audited"): `main` then grades the GGA record (gajjala_audited_ledger) AFTER GG1, in its OWN try, under
`gajjala_audited` — COPY FIRST: a GGA row with the same id · alert stamp · trigger · stop · plan as its 🚩 original is
the same read at the same stamp through the ONE trade-math engine, so the original's current columns are COPIED
(provenance `copied_from` / `copied_at` INSIDE each column — LEDGER_KEYS is closed), never re-fetched. Only the
RESIDUAL — a GGA row with no matching 🚩 row (the original's send failed / no target), or whose original carries no
current column (its grade deferred or failed that night) — is graded by `ledger.grade_step`, which skips every copied
column without a load. The summary serves `copy.residual` (expected 0 most nights). A failure is named under
`gajjala_audited.error`, never in GG5's `errors` or the exit code.
🧪 EXIT GRADES (2026-11-01, Ajay "But keep a track record too to see the winners and loster"): after the copy and the
grade, `audited_exits.grade_exits` grades T3 (fixed 2R / 3R on the 🌀 Intraday VCP) and T5 (the 21 EMA trail) into
gajjala_audited_exits, in its OWN inner try (`gajjala_audited.exits.error` — never hides copy / grade). ONE night late
by design: `load_intraday` never caches today and fetches a cold past day (daytrading/data.py:241-253), so a row of
tonight's session is `deferred_today`, and a row is loaded only when BOTH its symbol-days (the session + the market
day before, the EMA warm-up) are already in `intraday_cache` (a cache READ first, `audited_exits.is_warm`) — a cold
row is `deferred_cold`, never fetched (HIS CALL #21). Zero provider calls on that step.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import date, datetime, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from . import constants as GC
from . import context as CX

log = logging.getLogger("chart_maps.gajjala.nightly")

ET = ZoneInfo("America/New_York")
STEPS = ("floats", "halts", "history", "grade")           # 🏁 grade LAST (2026-10-16): its failure never stops a step


def default_session(now: Optional[datetime] = None) -> date:
    """Today (ET) when it trades, else the last market day before it."""
    from catalysts.medical.reaction import is_market_day, prev_market_day
    et = (now or datetime.now(timezone.utc)).astimezone(ET).date()
    return et if is_market_day(et) else prev_market_day(et)


def halt_window(session: date) -> list:
    """The chip's halt window for the session after `session`: K8_HISTORY_SESSIONS market days ending AT `session`."""
    from catalysts.medical.reaction import next_market_day
    return CX.history_window(next_market_day(session), GC.K8_HISTORY_SESSIONS)


def backfill_halts(store, session: date, *, fetch: Optional[Callable] = None) -> dict:
    """Read every session of the window not yet marked read; mark each one read only when its GET answered with at
    least one halt dated that session (an empty or other-date answer = failed, retried next night)."""
    if fetch is None:
        from catalysts.halts import get_halts_for_date as fetch
    window = halt_window(session)
    keep = {d.isoformat() for d in window}
    st = store.get_state(CX.HALT_BACKFILL_STATE_ID) or {}
    done = {d for d in (st.get("done") or []) if d in keep}
    out = {"window": len(window), "read": 0, "failed": 0, "rows": 0, "already": 0}
    for d in window:
        iso = d.isoformat()
        if iso in done:
            out["already"] += 1
            continue
        try:
            payload = fetch(d)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala nightly: halts for %s failed: %s", iso, type(exc).__name__)
            payload = {}
        n_halts = sum(int((v or {}).get("n_halts") or 0) for v in ((payload or {}).get("by_ticker") or {}).values())
        if not payload or n_halts == 0:
            # a zero-halt session is not plausible in this tape (probed sessions: 28 to 95 halts — docs/gajjala/context_reads_2026_10_13.md §4) — an empty answer is a
            # read that did not land (2026-10-13 review); retried next night, never marked read
            out["failed"] += 1
            continue
        out["rows"] += CX.record_halts(store, d, payload, source="history")
        out["read"] += 1
        done.add(iso)
    store.set_state(CX.HALT_BACKFILL_STATE_ID, {"done": sorted(done)})
    return out


def names_for_tomorrow(store, session: date) -> tuple:
    """(symbols, priority) — tomorrow's listed set + tonight's after-hours carry names; priority = their best change."""
    from catalysts.medical.reaction import next_market_day

    from . import scanner
    target = next_market_day(session)
    listed = scanner.listed_symbols(store, target)
    carry = ((store.ah_carry(session) or {}).get("names") or {})
    best: dict = {}
    for doc in store.scan_docs(scanner._window(target)):
        s = doc.get("symbol")
        if s:
            best[s] = max(best.get(s, float("-inf")), float(doc.get("max_change_pct") or 0.0))
    for s, c in carry.items():
        best.setdefault(s.upper(), float((c or {}).get("ah_move_pct") or 0.0))
    syms = sorted(set(listed) | {s.upper() for s in carry})
    return syms, {s: {"change_pct": best.get(s, 0.0)} for s in syms}


def run(session: Optional[date] = None, *, store=None, now: Optional[datetime] = None, steps=STEPS,
        fetch_halts: Optional[Callable] = None, daily_loader: Optional[Callable] = None,
        status_lookup: Optional[Callable] = None, massive_lookup: Optional[Callable] = None,
        sleep: Callable = time.sleep, ledger_load_day: Optional[Callable] = None,
        ledger_split_lookup: Optional[Callable] = None) -> dict:
    """The four steps for `session` (default: today ET / the last market day). -> a summary dict (+ `errors`).
    `ledger_load_day` / `ledger_split_lookup` are the 🏁 grade step's injectable loaders (ledger.grade_step)."""
    from catalysts.medical.reaction import next_market_day

    from . import store as ST
    store = store or ST.default()
    now = now or datetime.now(timezone.utc)
    session = session or default_session(now)
    target = next_market_day(session)
    out: dict = {"session": session.isoformat(), "target": target.isoformat(), "errors": []}
    syms, priority = names_for_tomorrow(store, session)
    out["names"] = len(syms)
    if "floats" in steps:
        try:
            state: dict = {}
            loaded = store.get_state(CX.FLOAT_STATE_ID) or {}
            state.update({k: loaded.get(k) for k in ("until", "n") if k in loaded})
            reads = CX.floats_for(syms, priority=priority, state=state, now=now, status_lookup=status_lookup,
                                  massive_lookup=massive_lookup, sleep=sleep, store=store, session=target,
                                  max_new=len(syms))
            out["floats"] = dict(state.get("yahoo") or {},
                                 known=sum(1 for r in reads.values() if r.get("shares") is not None))
        except Exception as exc:                                # noqa: BLE001
            log.exception("gajjala nightly: floats step failed")
            out["errors"].append(f"floats: {type(exc).__name__}")
    if "halts" in steps:
        try:
            out["halts"] = backfill_halts(store, session, fetch=fetch_halts)
        except Exception as exc:                                # noqa: BLE001
            log.exception("gajjala nightly: halts step failed")
            out["errors"].append(f"halts: {type(exc).__name__}")
    if "history" in steps:
        try:
            res = CX.warm_squeeze_history(syms, target, store, loader=daily_loader)
            out["history"] = {k: res[k] for k in ("computed", "cached", "deferred")}
        except Exception as exc:                                # noqa: BLE001
            log.exception("gajjala nightly: history step failed")
            out["errors"].append(f"history: {type(exc).__name__}")
    if "grade" in steps:                                         # LAST (the B8 pattern): its failure never stops a step
        try:
            from . import ledger as LG
            out["grade"] = LG.grade_step(store, now, load_day=ledger_load_day, split_lookup=ledger_split_lookup)
        except Exception as exc:                                # noqa: BLE001
            log.exception("gajjala nightly: grade step failed")
            out["errors"].append(f"grade: {type(exc).__name__}")
    return out


def grade_1m(now: datetime, *, store=None) -> dict:
    """🏁 The 1-minute page's grade (2026-10-27): {"grade": ledger.grade_step(<GG1 store>, now)}; a raise →
    {"error": "grade: <Type>"} (logged). Never raises."""
    try:
        from . import ledger as LG
        from . import store as ST
        from . import variant as V
        return {"grade": LG.grade_step(store if store is not None else ST.for_variant(V.GG1), now)}
    except Exception as exc:                                    # noqa: BLE001
        log.exception("gajjala nightly: the 1-minute page's grade failed")
        return {"error": f"grade: {type(exc).__name__}"}


def copy_original_grades(gga, now: datetime, *, shared=None) -> dict:
    """🧪 COPY FIRST (2026-11-01): for every GGA A+ row of the grade window (grade_step's sessions, clipped to the GGA
    record) whose 🚩 original has the SAME id, alert stamp (`at_utc` — the pass clock on both claims), trigger, stop
    and plan, every horizon column the original holds at LEDGER_GRADE_VERSION and the GGA doc does not is copied —
    `dict(col, copied_from=store.LEDGER, copied_at=now)` — in the body grade_step writes. Never a provider call.
    -> {rows, matched, copied_cols, written, residual, faulted, read_fault}; `residual` = GGA rows with no match, or a
    match whose original holds no current column — each only while its GGA doc still lacks a current column (the rows
    grade_step may load for). A read fault copies nothing."""
    from . import ledger as LG
    from . import store as ST
    from . import variant as V
    out = {"rows": 0, "matched": 0, "copied_cols": 0, "written": 0, "residual": 0, "faulted": 0, "read_fault": False}
    shared = shared if shared is not None else getattr(gga, "shared", None)
    sessions = LG._clip(CX.history_window(LG._next_market_day(default_session(now)),
                                          GC.LEDGER_GRADE_LOOKBACK_SESSIONS), V.GGA)
    try:
        if shared is None:
            raise LG.LedgerReadError("no 🚩 store to copy from")
        mine = LG.rows_for(sessions, gga, variant=V.GGA)
        orig = {r["id"]: r for r in LG.rows_for(sessions, shared)}
        o_docs = shared.ledger_docs(sessions)
        g_docs = gga.ledger_docs(sessions)
        if o_docs is None or g_docs is None:
            raise LG.LedgerReadError("a ledger could not be read")
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala nightly: the audited copy could not read: %s", type(exc).__name__)
        out["read_fault"] = True
        return out
    odocs = {d.get("_id"): d for d in o_docs if isinstance(d, dict)}
    gdocs = {d.get("_id"): d for d in g_docs if isinstance(d, dict)}
    out["rows"] = len(mine)
    stamp = now.isoformat()
    for row in mine:
        try:
            rid = row["id"]
            o = orig.get(rid)
            odoc, gdoc = odocs.get(rid) or {}, gdocs.get(rid) or {}
            open_cols = any(LG._current(gdoc, h) is None for h in GC.LEDGER_HORIZONS)
            if not (o is not None and o.get("at_utc") is not None and o.get("at_utc") == row.get("at_utc")
                    and o.get("trigger") is not None and row.get("trigger") is not None
                    and o.get("stop") is not None and row.get("stop") is not None
                    and LG._D(o["trigger"]) == LG._D(row["trigger"]) and LG._D(o["stop"]) == LG._D(row["stop"])
                    and o.get("plan") == row.get("plan")):
                out["residual"] += int(open_cols)
                continue
            out["matched"] += 1
            if not any(LG._current(odoc, h) is not None for h in GC.LEDGER_HORIZONS):
                out["residual"] += int(open_cols)               # the 🚩 grade deferred / failed that night
                continue
            cols = {}
            for h in GC.LEDGER_HORIZONS:
                col = LG._current(odoc, h)
                if col is not None and LG._current(gdoc, h) is None:
                    cols[h] = dict(col, copied_from=ST.LEDGER, copied_at=stamp)
            if not cols:
                continue
            body = {"date": row["date"], "symbol": row["symbol"], "setup": row["setup"], "kind": row["kind"],
                    "line": row["line"], "alert": LG._alert_block(row), "graded_at": stamp,
                    "version": GC.LEDGER_GRADE_VERSION}
            body.update(cols)
            if gga.upsert_ledger(rid, body):
                out["copied_cols"] += len(cols)
                out["written"] += 1
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala nightly: copying %s failed: %s", row.get("id"), type(exc).__name__)
            out["faulted"] += 1
    return out


def grade_audited(now: datetime, *, store=None, load_day: Optional[Callable] = None,
                  split_lookup: Optional[Callable] = None, exits_load: Optional[Callable] = None,
                  exits_warm: Optional[Callable] = None) -> dict:
    """🧪 The audited record's grade (2026-11-01): {"copy": copy_original_grades(...), "grade": ledger.grade_step(<GGA
    store>, now), "exits": audited_exits.grade_exits(<GGA store>, now)} — the copy FIRST, the grade for the residual
    only, then the exit grades (one night late, warm cache only — the module docstring). A store that is not the audited
    variant's is refused (fail closed — this step never grades 🚩's own ledger). A raise in the copy or the grade →
    {"error": "grade: <Type>"} (logged); a raise in the exits step → "exits": {"error": "exits: <Type>"} beside the
    copy and the grade (its OWN try). Never raises."""
    try:
        from . import ledger as LG
        from . import store as ST
        from . import variant as V
        gga = store if store is not None else ST.for_variant(V.GGA)
        if not V.is_audited(gga):                               # fail closed: this grade writes the GGA ledger ONLY
            raise ValueError("not the audited store")
        copied = copy_original_grades(gga, now)
        graded = LG.grade_step(gga, now, load_day=load_day, split_lookup=split_lookup)
        try:
            from . import audited_exits as AX
            exits = AX.grade_exits(gga, now, load_df=exits_load, warm=exits_warm)
        except Exception as exc:                                # noqa: BLE001
            log.exception("gajjala nightly: the audited exit grades failed")
            exits = {"error": f"exits: {type(exc).__name__}"}
        return {"copy": copied, "grade": graded, "exits": exits}
    except Exception as exc:                                    # noqa: BLE001
        log.exception("gajjala nightly: the audited record's grade failed")
        return {"error": f"grade: {type(exc).__name__}"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="chart_maps.gajjala.nightly", description=__doc__.split("\n")[0])
    ap.add_argument("--session", help="YYYY-MM-DD (default: today ET, or the last market day)")
    ap.add_argument("--steps", default=",".join(STEPS), help="comma list of " + "/".join(STEPS))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    steps = tuple(s.strip() for s in args.steps.split(",") if s.strip() in STEPS)
    session = date.fromisoformat(args.session) if args.session else None
    from . import store as ST
    st = ST.default()
    st.ensure_indexes()
    out = run(session, store=st, steps=steps)
    if "grade" in steps:                                         # 🚩 1-minute page (2026-10-27): after GG5, fenced
        out["gajjala_1m"] = grade_1m(datetime.now(timezone.utc))
        out["gajjala_audited"] = grade_audited(datetime.now(timezone.utc))   # 🧪 2026-11-01: after GG5 + GG1, fenced
    print(json.dumps(out, default=str))
    return 1 if out.get("errors") else 0


if __name__ == "__main__":
    sys.exit(main())
