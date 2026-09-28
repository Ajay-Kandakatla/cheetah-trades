"""Chart Maps lanes — the two scheduled jobs, driven by the per-minute engine
tick instead of new crontab lines (2026-09-27 follow-up).

WHY. The lane snapshot (every 5 min in RTH) and the daily loss review were
designed as three NEW crontab lines. The crontab is host-mounted from the main
tree and a deploy does not ship it, so no line was ever added and neither job
would ever run. The one line that already runs every minute on market-day
hours is `* 9-16 * * 1-5 python -m trading.exit_engine tick` (cron
container). `exit_engine._main` calls `run_after_tick(summary)` AFTER `tick()`
has returned, so both jobs run after every exit the tick manages and can never
block or fail it.

1. SNAPSHOT (`maybe_trigger_snapshot`). At most once per `SNAPSHOT_EVERY_MIN`
   bucket, from `bounce_room.SESSION_OPEN` (09:30) to before
   `zone_edge_entry.LAST_ENTRY_ET` (15:45, the last minute a lane may buy),
   on an open market day (broker clock open + `market_hours.gate`), and only
   while the program is ON (`program_caps.enabled`: `cm_program` true on
   paper / sim) — no api CPU while OFF. It asks the API service to rebuild:
   HTTP GET `INTERNAL_API_BASE` + `/chart-maps/lane-snapshot?record=true` with
   the `X-User-Email: cron@internal` header every cron → api call uses. The
   boards build in the api process, never here. Fire-and-forget: a short
   timeout; a read timeout means the api received the call and keeps
   building in its own thread (the route runs `lane_snapshot.run` via
   `asyncio.to_thread`, which a client disconnect cannot stop). A refused
   connection or an HTTP error is logged and ledgered once per ET day.
   A Mongo claim on `program_state` (`SNAPSHOT_CLAIM_ID`, the same `$lt`
   upsert pattern as `program_caps.claim`) means two overlapping ticks never
   both fire one bucket.

2. REVIEW (`maybe_run_review`). Once per trading day, on the first tick at or
   after `REVIEW_AT_ET` (16:50 — after the 16:45 autopsy pass; the cron
   tick's last hour is 16), `lane_review.build(day=today)` runs in-process.
   It is broker-light (it only READS the broker's closed orders, paged) and
   never places or cancels an order. Claimed atomically first (one
   `find_one_and_update` upsert of `lane_review:<day>` on `program_state`), so
   two ticks never both run it; a closed day never runs. It runs in a DAEMON
   worker thread joined for at most `REVIEW_BUDGET_SEC`. On an overrun the
   tick returns, the process exits and the daemon thread dies with it — the
   cron container's supercronic never starts a tick while the previous one
   is still running, so a lingering non-daemon thread would have skipped
   every tick until the review finished. An overrun is logged, ledgered and
   marked `over_budget`, and a LATER tick re-claims the day (the build is
   idempotent: `replace_one` upserts, `journal.reconcile` upserts by
   trade_id). A claim whose owner died (a `cron` redeploy, an OOM) stays
   `running`; it is re-claimable once it is older than `REVIEW_BUDGET_SEC`,
   because no live owner can hold it longer than that. A `done` or `failed`
   day is never re-run by the tick (`python -m trading.lane_review --day D`
   stays the manual re-run).

Both are fenced: nothing here raises into the caller.
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

log = logging.getLogger("trading.tick_jobs")

ET = ZoneInfo("America/New_York")

# HIS CALL #7 (docs/trading_chart_maps_lanes.md): a snapshot every 5 min.
SNAPSHOT_EVERY_MIN = 5
SNAPSHOT_PATH = "/chart-maps/lane-snapshot"
SNAPSHOT_PARAMS = {"record": "true"}
# The header every cron -> api call in this repo sends (crontab, demand_alerts).
CRON_USER_EMAIL = "cron@internal"
INTERNAL_API_DEFAULT = "http://api:8000"
# Fire-and-forget: (connect, read) seconds. A read timeout is NOT a failure.
SNAPSHOT_TIMEOUT_SEC = (3.0, 5.0)
SNAPSHOT_CLAIM_ID = "lane_snapshot_trigger"
SNAPSHOT_FAIL_ID = "lane_snapshot_trigger_fail"
SNAPSHOT_FAIL_KIND = "cm_snapshot_trigger_failed"

REVIEW_HOUR, REVIEW_MINUTE = 16, 50
REVIEW_CLAIM_PREFIX = "lane_review:"
# The worker thread is joined for at most this long (under one tick cadence).
# It also bounds how long a live owner can hold a `running` claim, so an older
# claim is a dead owner's and a later tick may take the day over.
REVIEW_BUDGET_SEC = 45.0
# Terminal statuses: the tick never re-runs a day that reached one of these.
REVIEW_FINAL_STATUSES = ("done", "failed")
REVIEW_FAIL_KIND = "cm_lane_review_failed"
REVIEW_OVER_BUDGET_KIND = "cm_lane_review_over_budget"


# ── shared names, imported at call time (tests' fakes apply) ─────────────────
def _EE():
    from trading import exit_engine as EE          # noqa: PLC0415
    return EE


def _PC():
    from trading import program_caps as PC         # noqa: PLC0415
    return PC


def _now_et(now: Optional[datetime] = None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc).astimezone(ET)
    if now.tzinfo is None:
        return now.replace(tzinfo=ET)
    return now.astimezone(ET)


def _closed_reason(n: datetime) -> Optional[str]:
    from market_hours import gate                   # noqa: PLC0415
    return gate.closed_reason(n)


def _state_coll():
    PC = _PC()
    return PC._coll(PC.PROGRAM_STATE_COLL)


def _session_open():
    from supply_demand.bounce_room import SESSION_OPEN  # noqa: PLC0415
    return SESSION_OPEN


def _last_entry():
    from trading.zone_edge_entry import LAST_ENTRY_ET   # noqa: PLC0415
    return LAST_ENTRY_ET


def review_at():
    from datetime import time as dtime               # noqa: PLC0415
    return dtime(REVIEW_HOUR, REVIEW_MINUTE)


# ═════════════════════════════════════════════════════════════════════════════
# 1. SNAPSHOT
# ═════════════════════════════════════════════════════════════════════════════
def bucket_key(now: Optional[datetime] = None) -> str:
    """'YYYY-MM-DDTHH:MM' floored to the SNAPSHOT_EVERY_MIN bucket (ET).
    ISO strings sort in time order, so the `$lt` claim never goes backwards."""
    n = _now_et(now)
    m = n.minute - (n.minute % SNAPSHOT_EVERY_MIN)
    return "%sT%02d:%02d" % (n.date().isoformat(), n.hour, m)


def snapshot_window_reason(now: Optional[datetime] = None) -> Optional[str]:
    """None inside [SESSION_OPEN, LAST_ENTRY_ET), else why not."""
    t = _now_et(now).time()
    start, end = _session_open(), _last_entry()
    if t < start:
        return "before %s ET" % start.strftime("%H:%M")
    if t >= end:
        return "at/after %s ET (last entry minute)" % end.strftime("%H:%M")
    return None


def _claim_bucket(coll, key: str, n: datetime) -> tuple:
    """(True, None) when this tick owns the bucket, else (False, reason)."""
    PC = _PC()
    try:
        coll.find_one_and_update({"_id": SNAPSHOT_CLAIM_ID, "bucket": {"$lt": key}},
                                 {"$set": {"bucket": key,
                                           "at": n.isoformat(timespec="seconds")}},
                                 upsert=True)
        return True, None
    except Exception as exc:                        # noqa: BLE001
        if PC._is_dup(exc):
            return False, "bucket %s already fired" % key[11:]
        log.warning("lane snapshot trigger: claim failed: %s", exc)
        return False, "claim failed: %s" % type(exc).__name__


def _ledger_failure_once(coll, day: str, detail: dict) -> bool:
    """One ledger row per ET day for a failed trigger. True when written."""
    try:
        coll.find_one_and_update({"_id": SNAPSHOT_FAIL_ID, "day": {"$ne": day}},
                                 {"$set": {"day": day, "detail": detail}}, upsert=True)
    except Exception as exc:                        # noqa: BLE001
        if not _PC()._is_dup(exc):
            log.warning("lane snapshot trigger: failure dedupe unreadable: %s", exc)
        return False
    try:
        _EE().ledger(SNAPSHOT_FAIL_KIND, detail=detail)
    except Exception as exc:                        # noqa: BLE001
        log.warning("lane snapshot trigger: ledger failed: %s", exc)
        return False
    return True


def _default_get(url, params=None, headers=None, timeout=None):
    import requests                                 # noqa: PLC0415
    return requests.get(url, params=params, headers=headers, timeout=timeout)


def _is_read_timeout(exc) -> bool:
    try:
        import requests                             # noqa: PLC0415
        if isinstance(exc, requests.exceptions.ReadTimeout):
            return True
    except Exception:                               # noqa: BLE001
        pass
    return type(exc).__name__ == "ReadTimeout"


def maybe_trigger_snapshot(*, market_open, now: Optional[datetime] = None,
                           cfg: Optional[dict] = None, mode: Optional[str] = None,
                           http_get: Optional[Callable] = None) -> dict:
    """Ask the api to rebuild the lane snapshot, at most once per bucket.
    Returns {"fired": bool, ...}. Never raises."""
    try:
        n = _now_et(now)
        if market_open is not True:
            return {"fired": False, "skipped": "market closed"}
        closed = _closed_reason(n)
        if closed:
            return {"fired": False, "skipped": closed}
        why = snapshot_window_reason(n)
        if why:
            return {"fired": False, "skipped": why}
        EE = _EE()
        cfg = cfg if cfg is not None else EE.get_config()
        mode = mode if mode is not None else EE._broker_mode()
        if not _PC().enabled(cfg, mode):
            return {"fired": False, "skipped": "program OFF"}
        coll = _state_coll()
        if coll is None:
            return {"fired": False, "skipped": "no mongo (cannot claim the bucket)"}
        key = bucket_key(n)
        ok, reason = _claim_bucket(coll, key, n)
        if not ok:
            return {"fired": False, "skipped": reason}
        base = (os.getenv("INTERNAL_API_BASE") or INTERNAL_API_DEFAULT).rstrip("/")
        url = base + SNAPSHOT_PATH
        get = http_get or _default_get
        out = {"fired": True, "bucket": key}
        err = None
        try:
            r = get(url, params=dict(SNAPSHOT_PARAMS),
                    headers={"X-User-Email": CRON_USER_EMAIL}, timeout=SNAPSHOT_TIMEOUT_SEC)
            code = getattr(r, "status_code", None)
            out["http"] = code
            if not isinstance(code, int) or code >= 400:
                err = "HTTP %s" % code
        except Exception as exc:                    # noqa: BLE001
            if _is_read_timeout(exc):
                out["http"] = "sent (read timeout; the api keeps building)"
            else:
                err = "%s: %s" % (type(exc).__name__, str(exc)[:200])
        if err:
            out["error"] = err
            log.warning("lane snapshot trigger %s failed: %s", key, err)
            out["ledgered"] = _ledger_failure_once(
                coll, n.date().isoformat(), {"bucket": key, "url": url, "error": err})
        return out
    except Exception as exc:                        # noqa: BLE001
        log.warning("lane snapshot trigger crashed: %s", exc)
        return {"fired": False, "error": "%s: %s" % (type(exc).__name__, str(exc)[:200])}


# ═════════════════════════════════════════════════════════════════════════════
# 2. REVIEW
# ═════════════════════════════════════════════════════════════════════════════
def _default_build(day: str, now: datetime) -> dict:
    from trading import lane_review                 # noqa: PLC0415
    return lane_review.build(day=day, now=now, record=True)


def _claim_review(coll, day: str, n: datetime,
                  budget_sec: float = REVIEW_BUDGET_SEC) -> tuple:
    """(True, None) when this tick owns the day, else (False, reason).

    One find_one_and_update with upsert (the `program_caps.claim` pattern): a
    missing doc is inserted; an existing doc is taken over only when it is
    not final AND its `claimed_at` is at least `budget_sec` old (an
    `over_budget` run whose daemon thread died with its process, or a
    `running` claim whose process was killed). Anything else fails the
    filter, the upsert collides on _id and Mongo raises DuplicateKeyError."""
    cid = REVIEW_CLAIM_PREFIX + day
    cutoff = (n - timedelta(seconds=max(0.0, float(budget_sec)))).isoformat(timespec="seconds")
    try:
        coll.find_one_and_update(
            {"_id": cid, "status": {"$nin": list(REVIEW_FINAL_STATUSES)},
             "claimed_at": {"$lte": cutoff}},
            {"$set": {"day": day, "claimed_at": n.isoformat(timespec="seconds"),
                      "status": "running"},
             "$inc": {"attempts": 1}},
            upsert=True)
        return True, None
    except Exception as exc:                        # noqa: BLE001
        if not _PC()._is_dup(exc):
            log.warning("lane review: claim failed: %s", exc)
            return False, "claim failed: %s" % type(exc).__name__
    try:
        cur = coll.find_one({"_id": cid}) or {}
    except Exception:                               # noqa: BLE001
        cur = {}
    if cur.get("status") in REVIEW_FINAL_STATUSES:
        return False, "already ran today"
    return False, "claimed at %s (%s); another tick owns it" % (
        str(cur.get("claimed_at") or "?")[11:19], cur.get("status") or "running")


def _mark(coll, day: str, fields: dict) -> None:
    try:
        coll.update_one({"_id": REVIEW_CLAIM_PREFIX + day}, {"$set": fields})
    except Exception as exc:                        # noqa: BLE001
        log.debug("lane review: status write failed: %s", exc)


def _ledger(kind: str, detail: dict) -> None:
    try:
        _EE().ledger(kind, detail=detail)
    except Exception as exc:                        # noqa: BLE001
        log.warning("lane review: ledger failed: %s", exc)


def maybe_run_review(*, now: Optional[datetime] = None, build: Optional[Callable] = None,
                     budget_sec: float = REVIEW_BUDGET_SEC) -> dict:
    """Run today's lane review once, on the first tick at/after REVIEW_AT_ET.
    Returns {"ran": bool, ...}. Never raises."""
    try:
        n = _now_et(now)
        if n.time() < review_at():
            return {"ran": False, "skipped": "before %s ET" % review_at().strftime("%H:%M")}
        closed = _closed_reason(n)
        if closed:
            return {"ran": False, "skipped": closed}
        coll = _state_coll()
        if coll is None:
            return {"ran": False, "skipped": "no mongo (cannot claim the day)"}
        day = n.date().isoformat()
        ok, reason = _claim_review(coll, day, n, budget_sec)
        if not ok:
            return {"ran": False, "skipped": reason}
        fn = build or _default_build
        box: dict = {}

        def _work():
            try:
                box["doc"] = fn(day, n)
            except BaseException as exc:            # noqa: BLE001
                box["exc"] = exc

        # daemon=True: an overrun must NOT keep the cron process alive (the
        # next exit_engine tick waits for this one to exit).
        th = threading.Thread(target=_work, name="lane-review-%s" % day, daemon=True)
        th.start()
        th.join(max(0.0, float(budget_sec)))
        if th.is_alive():
            detail = {"day": day, "budget_sec": budget_sec}
            log.warning("lane review %s still running after %ss; abandoned with this "
                        "process, a later tick re-claims the day", day, budget_sec)
            _mark(coll, day, {"status": "over_budget"})
            _ledger(REVIEW_OVER_BUDGET_KIND, detail)
            return {"ran": True, "day": day, "status": "over_budget"}
        if "exc" in box:
            exc = box["exc"]
            err = "%s: %s" % (type(exc).__name__, str(exc)[:200])
            log.warning("lane review %s failed: %s", day, err)
            _mark(coll, day, {"status": "failed", "error": err})
            _ledger(REVIEW_FAIL_KIND, {"day": day, "error": err})
            return {"ran": True, "day": day, "status": "failed", "error": err}
        doc = box.get("doc") or {}
        _mark(coll, day, {"status": "done", "skipped": doc.get("skipped"),
                          "headline": doc.get("headline"),
                          "finished_at": _now_et().isoformat(timespec="seconds")})
        return {"ran": True, "day": day, "status": "done",
                "headline": doc.get("headline"), "skipped": doc.get("skipped")}
    except Exception as exc:                        # noqa: BLE001
        log.warning("lane review hook crashed: %s", exc)
        return {"ran": False, "error": "%s: %s" % (type(exc).__name__, str(exc)[:200])}


# ═════════════════════════════════════════════════════════════════════════════
def run_after_tick(summary: Optional[dict], now: Optional[datetime] = None) -> dict:
    """Both jobs, after the tick. `summary` is the tick's own; only its
    `market_open` (the broker clock) is read. Never raises."""
    out: dict = {}
    mo = (summary or {}).get("market_open") if isinstance(summary, dict) else None
    try:
        out["lane_snapshot"] = maybe_trigger_snapshot(market_open=mo, now=now)
    except Exception as exc:                        # noqa: BLE001
        out["lane_snapshot"] = {"fired": False, "error": str(exc)[:200]}
    try:
        out["lane_review"] = maybe_run_review(now=now)
    except Exception as exc:                        # noqa: BLE001
        out["lane_review"] = {"ran": False, "error": str(exc)[:200]}
    return out
