"""Moat-only backfill — sequential Yahoo reads, 429 backoff, resumable.

Why (2026-10-11): the weekly research refresh read yfinance `.info` from six
threads, Yahoo answered ~1,300 of them with 429, and every 429 was written as
`moat: null` — 87.7% of served blobs had no moat. The refresh now carries the
stored moat forward (`research.compute_research(with_moat=False)`) and this
module does every moat read, ONE at a time:

  * paced: at least `interval_sec` between two reads;
  * a 429 sleeps BACKOFF_START_SEC, doubling to BACKOFF_MAX_SEC, and retries
    the SAME name; after MAX_RATE_LIMIT_RETRIES the run stops (resumable);
  * a non-429 read failure marks that name `fetch_failed` for this pass and
    moves on; MAX_CONSECUTIVE_FAILURES in a row stops the run (network down);
  * writes ONLY moat / moat_as_of / moat_status / moat_failed_at — never
    `cached_at`, never an upsert, so a stale blob never looks fresh and no
    blob is created here.

Resumable cursor: a pass has a start time (`pass_started_at`, stored in
`sepa_moat_backfill_state`). A name read in this pass carries
`moat_as_of >= pass_started_at` (or `moat_failed_at >=` it), so a resumed run
skips it; an interrupted run (budget, 429 stop, crash, container kill) picks
up exactly the names still owed.

Modes:
  null     names with no moat at all (the 2026-10-11 gap) — `moat-backfill`
  refresh  also every moat read before the pass began, oldest first — the
           weekly pass `research-refresh` chains after its threaded part
Order: no-moat first, then oldest moat_as_of, then symbol — so a pass cut
short fills the worst gaps first and the same tail is not starved weekly.

Pacing numbers are transport knobs, not trading thresholds.
"""
from __future__ import annotations

import logging
import time
from typing import Callable, Iterable, Optional

from . import moat as moat_mod

log = logging.getLogger("sepa.moat_backfill")

STATE_COLLECTION = "sepa_moat_backfill_state"
MODES = ("null", "refresh")

DEFAULT_INTERVAL_SEC = 1.0
BACKOFF_START_SEC = 60.0
BACKOFF_MAX_SEC = 900.0
MAX_RATE_LIMIT_RETRIES = 6         # 60+120+240+480+900+900 s ≈ 45 min, then stop
MAX_CONSECUTIVE_FAILURES = 20
PROGRESS_EVERY = 50

_PICK_PROJECTION = {"symbol": 1, "moat.label": 1, "moat_as_of": 1,
                    "moat_failed_at": 1}


def pick(docs: Iterable[dict], *, mode: str, pass_started_at: float,
         symbols: Optional[Iterable[str]] = None) -> list[str]:
    """Symbols still owed a moat read in this pass, in read order. PURE."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    want = {s.upper() for s in symbols} if symbols is not None else None
    rows: list[tuple[int, float, str]] = []
    for d in docs:
        sym = d.get("symbol")
        if not sym or (want is not None and sym not in want):
            continue
        as_of = d.get("moat_as_of") or 0
        if as_of >= pass_started_at or (d.get("moat_failed_at") or 0) >= pass_started_at:
            continue                     # already read / tried in this pass
        has = isinstance(d.get("moat"), dict)
        if has and mode == "null":
            continue
        rows.append((1 if has else 0, as_of, sym))
    rows.sort()
    return [sym for _, _, sym in rows]


def _write(coll, sym: str, moat: Optional[dict], now: int) -> str:
    """Store one read. Returns "ok" | "no_data" | "kept"."""
    if moat is not None and not moat.get("data_completeness"):
        prev = (coll.find_one({"symbol": sym}, {"moat": 1}) or {}).get("moat")
        if moat_mod.lost_inputs(moat, prev):
            coll.update_one({"symbol": sym}, {"$set": {
                "moat_status": "fetch_failed", "moat_failed_at": now}})
            return "kept"
    if moat is None:
        fields = {"moat": None, "moat_as_of": now, "moat_status": "no_data"}
    else:
        fields = {"moat": {**moat, "as_of": now}, "moat_as_of": now,
                  "moat_status": "ok"}
    coll.update_one({"symbol": sym}, {"$set": fields})
    return "no_data" if moat is None else "ok"


def run(coll, state_coll, *, mode: str = "null",
        symbols: Optional[Iterable[str]] = None,
        restart: bool = False, resume_only: bool = False,
        interval_sec: float = DEFAULT_INTERVAL_SEC,
        max_minutes: Optional[float] = None, limit: Optional[int] = None,
        fetch: Optional[Callable[[str], Optional[dict]]] = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time) -> dict:
    """One backfill run. `restart` begins a new pass; `resume_only` does
    nothing unless an unfinished pass exists (the nightly catch-up)."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    fetch = fetch or (lambda s: moat_mod.compute_moat(s, breaker=False))
    state_id = f"moat_backfill:{mode}"
    t0 = clock()
    st = state_coll.find_one({"_id": state_id}) or {}
    unfinished = bool(st.get("pass_started_at")) and not st.get("done")

    if resume_only and not unfinished:
        return {"mode": mode, "status": "nothing_to_resume", "done": True,
                "todo": 0, "processed": 0, "counts": {}}
    if restart or not unfinished:
        pass_started_at = int(t0)
        state_coll.update_one({"_id": state_id}, {"$set": {
            "pass_started_at": pass_started_at, "done": False,
            "symbols_filter": sorted({s.upper() for s in symbols}) if symbols is not None else None,
        }}, upsert=True)
        resumed = False
    else:
        pass_started_at = st["pass_started_at"]
        resumed = True
        if symbols is None and st.get("symbols_filter") is not None:
            symbols = st["symbols_filter"]

    owed = pick(coll.find({}, _PICK_PROJECTION), mode=mode,
                pass_started_at=pass_started_at, symbols=symbols)
    todo = owed[:limit] if limit is not None else owed
    deadline = t0 + max_minutes * 60 if max_minutes else None
    log.info("moat-backfill %s: %d names owed (%s pass from %d), reading %d",
             mode, len(owed), "resumed" if resumed else "new",
             pass_started_at, len(todo))

    counts = {"ok": 0, "no_data": 0, "kept": 0, "failed": 0,
              "rate_limit_waits": 0}
    status = "done"
    processed = 0
    consecutive_failures = 0
    last_read = None
    for sym in todo:
        if deadline is not None and clock() >= deadline:
            status = "budget"
            break
        retries, delay = 0, BACKOFF_START_SEC
        outcome = None
        while outcome is None:
            if last_read is not None:
                gap = interval_sec - (clock() - last_read)
                if gap > 0:
                    sleep(gap)
            last_read = clock()
            try:
                moat = fetch(sym)
            except moat_mod.MoatFetchError as exc:
                if not exc.rate_limited:
                    log.warning("moat-backfill: %s read failed: %s", sym, exc)
                    outcome = "failed"
                    break
                if retries >= MAX_RATE_LIMIT_RETRIES:
                    status = "rate_limited"
                    break
                if deadline is not None and clock() + delay >= deadline:
                    status = "budget"
                    break
                retries += 1
                counts["rate_limit_waits"] += 1
                log.warning("moat-backfill: 429 on %s — sleeping %.0fs (retry %d/%d)",
                            sym, delay, retries, MAX_RATE_LIMIT_RETRIES)
                sleep(delay)
                delay = min(delay * 2, BACKOFF_MAX_SEC)
            except Exception as exc:       # a scoring bug: per-name failure
                log.warning("moat-backfill: %s failed: %s", sym, exc)
                outcome = "failed"
            else:
                outcome = _write(coll, sym, moat, int(clock()))
        if outcome is None:                # stopped mid-name: it stays owed
            break
        if outcome == "failed":
            coll.update_one({"symbol": sym}, {"$set": {
                "moat_status": "fetch_failed", "moat_failed_at": int(clock())}})
            consecutive_failures += 1
        else:
            consecutive_failures = 0
        counts[outcome] += 1
        processed += 1
        if processed % PROGRESS_EVERY == 0:
            log.info("moat-backfill %s: %d/%d %s", mode, processed, len(todo), counts)
            state_coll.update_one({"_id": state_id}, {"$set": {"last_symbol": sym}})
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            status = "unreachable"
            break

    done = status == "done" and len(todo) == len(owed)
    duration = round(clock() - t0, 1)
    state_coll.update_one({"_id": state_id}, {"$set": {
        "done": done, "last_status": status, "last_run_at": int(t0),
        "last_counts": counts, "last_duration_sec": duration,
    }})
    log.info("moat-backfill %s: %s — %d/%d read in %.0fs %s",
             mode, status, processed, len(todo), duration, counts)
    return {"mode": mode, "pass_started_at": pass_started_at,
            "resumed": resumed, "status": status, "done": done,
            "owed": len(owed), "todo": len(todo), "processed": processed,
            "counts": counts, "duration_sec": duration}


def run_default(**kw) -> dict:
    """`run` against the live research cache + state collection."""
    from . import research
    coll = research._get_cache()
    if coll is None:
        log.warning("moat-backfill: Mongo unavailable — nothing done")
        return {"status": "no_mongo", "done": False, "processed": 0, "counts": {}}
    state_coll = coll.database[STATE_COLLECTION]
    moat_mod.reset_breaker()
    return run(coll, state_coll, **kw)
