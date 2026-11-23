"""👀 Gajjala's Watch — the REST side of the minute read (2026-11-23, spec ggconn rev 2 §3.4, WP-3).

Ajay, verbatim (2026-11-23 ~12:00 ET): "Can you clean up some connection I am seeing delays price update for AKAN on the
watch chart.." · "I would like us to focus on connections of Gajjala more for the rest of the tabs."

Three parts, two switches (C.REST_OWN_BREAKER_ON, C.REST_REREAD_ON):
  (a) ON — the Watch loader's OWN breaker (`breaker()` / `load_day`), rebuilt CLOSED before every read (`open_read()`,
      called on the loop's own thread before `frames_for` builds its pool). A trip costs the rest of THAT read, never
      the next minute. No cooldown number of mine: the module breaker's trip rule and cooldown (daytrading.data) apply
      inside a read; every other caller keeps the module breaker `_CB`.
  (b) ALWAYS — a per-session counter doc `rest:{session}` in C.COLL_STATE (`count`): iterations, names, failed
      name-minutes. Read it with `scripts/gajjala_watch_rest_count.py` (read-only).
  (c) BUILT, OFF (C.REST_REREAD_ON False = HIS CALL) — the plan / merge / summary of one re-read of a minute's `failed`
      names; the loop runs it AFTER the cross push and every tile write, inside the same budget and the same `now`.

Never imports the live feed, the live hub, the socket, the paper lane or the cross engine. `daytrading.data` is
imported lazily (`_dt()`). Transport only — no rule, gate, threshold or ring condition here. UNMEASURED.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Optional

from . import constants as C

log = logging.getLogger("chart_maps.gajjala_watch.rest")

_LOCK = threading.Lock()
_BREAKER: Optional[dict] = None


def _dt():
    from daytrading import data as dt_data
    return dt_data


# ── (a) the Watch's own breaker ───────────────────────────────────────────────────────────────────────────────────
def breaker() -> dict:
    """The Watch's OWN breaker. Built under _LOCK when there is none — the build child's first call comes from
    BAR_WORKERS threads at once, and they must all feed ONE breaker [C6]."""
    global _BREAKER
    b = _BREAKER
    if b is not None:
        return b
    with _LOCK:
        if _BREAKER is None:
            _BREAKER = _dt().new_breaker()
        return _BREAKER


def open_read() -> None:
    """A NEW closed breaker (dt_data.new_breaker()) for the read about to start, swapped in under _LOCK. Called on the
    loop's own thread only — before frames_for builds its pool and after the previous pool ended (bars.frames_for's pool
    is a `with` block), so no fetch ever sees the swap. No-op when C.REST_OWN_BREAKER_ON is off. NEVER raises: a fault
    logs the type name and the old breaker stays [C7, C8]."""
    global _BREAKER
    if not C.REST_OWN_BREAKER_ON:
        return
    try:
        fresh = _dt().new_breaker()
        with _LOCK:
            _BREAKER = fresh
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch: own breaker not renewed: %s", type(exc).__name__)


def load_day(sym, day, force=False, include_premarket=True, include_afterhours=False):
    """RUN._load_day's call with the Watch's own breaker: dt_data.load_intraday(..., cb=breaker())."""
    return _dt().load_intraday(sym, day, force=force, include_premarket=include_premarket,
                               include_afterhours=include_afterhours, cb=breaker())


# ── (b)/(c) a minute's failed names ───────────────────────────────────────────────────────────────────────────────
def failed_names(per_name, syms) -> tuple:
    """The names frames_for reported `failed`, in list order — never over_budget / no_bars / a name it did not report.
    A pure read of per_name (the counter needs it in both modes — NOT gated by either switch)."""
    pn = per_name if isinstance(per_name, dict) else {}
    out = []
    for s in syms or []:
        e = pn.get(s)
        if isinstance(e, dict) and e.get("status") == "failed" and s not in out:
            out.append(s)
    return tuple(out)


@dataclass(frozen=True)
class Plan:
    names: tuple
    wait: float
    left: float
    skip: Optional[str]


def retry_plan(failed, *, budget_sec, elapsed_sec) -> Plan:
    """C.REST_REREAD_ON off → nothing (skip "off"). Else wait = C.REST_RETRY_PAUSE_SEC and left = budget − elapsed −
    wait; a re-read is not started with less than one fetch timeout (dt_data._FETCH_TIMEOUT_SEC, read at CALL time) of
    the budget left (skip "no_time"). Else every failed name, once."""
    if not C.REST_REREAD_ON:
        return Plan((), 0.0, 0.0, C.REST_SKIPS[0])
    wait = float(C.REST_RETRY_PAUSE_SEC)
    left = float(budget_sec) - float(elapsed_sec) - wait
    if left < float(_dt()._FETCH_TIMEOUT_SEC):
        return Plan((), 0.0, max(0.0, left), C.REST_SKIPS[1])
    return Plan(tuple(failed), wait, left, None)


_REPLACES = ("loaded", "no_bars")


def merge(per_name, stats, per_name2, stats2, names) -> tuple:
    """Per name: the re-read's entry replaces the first one ONLY when it says loaded / no_bars; failed again,
    over_budget or nothing → the first verdict "failed" stands. stats (in place): failed −1 and the new status +1 per
    replaced name (stats2, the re-read's own counts, is not added). Returns the replaced names, list order."""
    pn2 = per_name2 if isinstance(per_name2, dict) else {}
    changed = []
    for s in names or ():
        e = pn2.get(s)
        if not (isinstance(e, dict) and e.get("status") in _REPLACES):
            continue
        per_name[s] = dict(e)
        stats["failed"] = stats.get("failed", 0) - 1
        stats[e["status"]] = stats.get(e["status"], 0) + 1
        changed.append(s)
    return tuple(changed)


def summary(n_failed, plan: Plan) -> dict:
    """The iteration's `rest` block: counts of the failed names and the plan (recovered / pushed filled by the loop)."""
    return {"failed": int(n_failed), "retried": len(plan.names), "recovered": 0, "pushed": 0, "wait_s": plan.wait,
            "skip": plan.skip}


# ── (b) the per-session counter doc [C2] ──────────────────────────────────────────────────────────────────────────
def _iso(session) -> str:
    return session.isoformat() if hasattr(session, "isoformat") else str(session or "")[:10]


def count(state_coll, session, now, *, n_names, rest=None) -> None:
    """ONE update_one on `rest:{session}` (upsert): $inc iterations 1 + names n_names every iteration that ran; when
    `rest` (a failed minute) also failed_minutes 1 and its failed / retried / recovered / pushed / no_time / errors,
    and $set `last`. None collection → nothing. NEVER raises (one warning, the type name only)."""
    if state_coll is None:
        return
    try:
        iso = _iso(session)
        inc = {"iterations": 1, "names": int(n_names)}
        sets = {"session": iso, "at": now}
        if rest:
            r = rest
            inc.update({"failed_minutes": 1, "failed": int(r.get("failed") or 0),
                        "retried": int(r.get("retried") or 0), "recovered": int(r.get("recovered") or 0),
                        "pushed": int(r.get("pushed") or 0),
                        "no_time": 1 if r.get("skip") == C.REST_SKIPS[1] else 0,
                        "errors": 1 if r.get("error") else 0})
            sets["last"] = {"at": now, "failed": r.get("failed"), "retried": r.get("retried"),
                            "recovered": r.get("recovered"), "pushed": r.get("pushed"), "wait_s": r.get("wait_s"),
                            "skip": r.get("skip"), "error": r.get("error")}
        state_coll.update_one({"_id": C.REST_COUNT_ID_PREFIX + iso}, {"$inc": inc, "$set": sets}, upsert=True)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch: REST counter write failed: %s", type(exc).__name__)


def _reset() -> None:
    """Tests: forget the breaker."""
    global _BREAKER
    with _LOCK:
        _BREAKER = None


__all__ = ["breaker", "open_read", "load_day", "failed_names", "Plan", "retry_plan", "merge", "summary", "count"]
