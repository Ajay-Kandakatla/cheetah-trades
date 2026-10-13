"""Gajjala's tab — the 20:15 ET nightly (spec §3.10): float warm, the 30-session halt-history backfill, and the 🎾
squeeze-history warm for the NEXT session.

    python -m chart_maps.gajjala.nightly [--session YYYY-MM-DD] [--steps floats,halts,history]

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
Writes only the gajjala_* collections. Read-only on every provider. Idempotent: a second run the same night reads
nothing new (halts) and serves the stored chips (history).
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
STEPS = ("floats", "halts", "history")


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
        sleep: Callable = time.sleep) -> dict:
    """The three steps for `session` (default: today ET / the last market day). -> a summary dict (+ `errors`)."""
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
    return out


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
    print(json.dumps(out, default=str))
    return 1 if out.get("errors") else 0


if __name__ == "__main__":
    sys.exit(main())
