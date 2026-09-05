"""supply_demand/alert_status — what each Supply & Demand push pass did last,
so the /alerts page can say WHY the phone was quiet.

Ajay 2026-09-05 (verbatim): "Do we have the same logic in back end demand for
the ones that I get alerts. Would it be the same list of stocks.. Also can I go
to a dedicated page to see the list of alerts? May be add it to recent alerts
or something?"

The honest answer to the first question is NO: the Demand board is a
closed-bar scan over the full universe with an R:R floor; the phone gets a live,
$1B+, gated subset (alert_gates: >= 5% room to the first band overhead, print
<= 1% above the demand band). A quiet phone is therefore normal, and a page
that only lists what pushed cannot tell "nothing qualified" from "the pass
never ran". This module keeps the last pass's counters per kind:

  zone_edge          read from the existing ``zone_edge_latest`` doc (_id
                     'latest'), whose counts now carry skipped_room /
                     skipped_cap / unknown_cap / pushed (zone_edge.check_once).
  zone_bounce_alert  written here by zone_bounce_alerts.check_once
  demand_alert       written here by demand_alerts.check_once

``alert_pass_latest`` collection: {_id: kind, as_of: ET iso, date: YYYY-MM-DD,
counts: {...ints}, reason?: str}. One doc per kind, replaced every pass.
``record_pass`` is best-effort and never raises — it sits after the sends in a
cron pass, and delivery is what matters. A missing doc reads as as_of null and
counts {} (the page shows "no pass recorded", never zeros it did not measure).

GET /alerts/status (supply_demand/api.py) -> ``status_payload``:
  {in_session, now_et, gate: {min_room_pct, max_above_demand_pct},
   passes: {zone_edge, zone_bounce_alert, demand_alert}, disclaimer}
  each pass: {as_of, date, counts, cadence_sec[, reason]}
Times are ET ISO strings; ``in_session`` is zone_edge's clock (RTH 9:31-16:00
on NYSE trading days), evaluated at request time. ``in_session`` is the CLOCK,
not proof the crons are alive — the page compares each ``as_of`` with
``now_et`` against ``cadence_sec`` and says "stale" when a pass is overdue.

S/D scope: configured house heuristic, not a book method, no cites. Decision
support, not a buy signal, not advice.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from . import alert_gates as AG

log = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
PASS_COLL = "alert_pass_latest"
ZONE_EDGE_KIND = "zone_edge"
PASS_KINDS = (ZONE_EDGE_KIND, "zone_bounce_alert", "demand_alert")

# How often each cron is scheduled to run in RTH (backend/crontab: zone_edge
# `* 9-16 * * 1-5`, demand_alerts `3-58/5`, zone_bounce_alerts `4-59/5`).
# Reported per pass as `cadence_sec` so the page can call a same-day stamp
# STALE against the real schedule instead of a hard-coded "every minute"
# (review 2026-09-05: a cron dead since 10:02 read as "passes running" at
# 14:30 because the header was inferred from the clock alone). Change the
# crontab -> change this; the source guard in test_alert_status pins both.
CADENCE_SEC = {ZONE_EDGE_KIND: 60, "zone_bounce_alert": 300, "demand_alert": 300}

DISCLAIMER = ("Phone pushes are a gated, live, $1B+ subset of the boards (alert_gates: >= 5% "
              "room to the first band overhead, print <= 1% above the demand band); the "
              "Demand board is a closed-bar scan with an R:R floor. Counts are the last pass "
              "of each cron, not a full-universe truth. Configured heuristic, not a book "
              "method. Decision support, not a buy signal, not advice.")


def _coll():
    try:
        from portfolio.store import _get_db
        db = _get_db()
        return db[PASS_COLL] if db is not None else None
    except Exception as exc:
        log.warning("alert_status: no mongo for %s: %s", PASS_COLL, exc)
        return None


def _int(x) -> Optional[int]:
    """Counts are ints; numpy / floats / bools coerce, garbage drops (None)."""
    if isinstance(x, bool):
        return int(x)
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v or math.isinf(v):
        return None
    return int(v)


def clean_counts(counts) -> dict:
    """{str: int} only — a dict / list value (e.g. a stray `hits` list) becomes
    its length, anything non-numeric is dropped."""
    out: dict = {}
    for k, v in (counts or {}).items():
        if isinstance(v, (list, tuple, set, dict)):
            out[str(k)] = len(v)
            continue
        n = _int(v)
        if n is not None:
            out[str(k)] = n
    return out


_NOT_COUNTS = ("ran", "date", "as_of", "reason", "payload", "seconds", "latest_written",
               "breaking", "near_demand")


def counts_from_result(result: dict) -> dict:
    """A check_once result -> its counters: numeric keys kept, list-valued keys
    (`hits`) become their length, bookkeeping keys dropped."""
    return clean_counts({k: v for k, v in (result or {}).items() if k not in _NOT_COUNTS})


def record_result(kind: str, result: dict, now: Optional[datetime] = None, coll=None) -> bool:
    """record_pass for a whole check_once result — the one line each pass adds
    before returning. Skips a pass that never ran the read (outside RTH)."""
    result = result or {}
    if not result.get("ran") and not result.get("reason"):
        return False
    return record_pass(kind, counts_from_result(result), now, coll=coll,
                       reason=result.get("reason"))


def record_pass(kind: str, counts: dict, now: Optional[datetime] = None, coll=None,
                reason: Optional[str] = None) -> bool:
    """Replace the `kind` doc with this pass's counters. Best-effort: returns
    True on a write, False on no coll / any error; never raises."""
    try:
        if coll is None:
            coll = _coll()
        if coll is None:
            return False
        now = now or datetime.now(ET)
        et = now.astimezone(ET) if now.tzinfo is not None else now.replace(tzinfo=ET)
        doc = {"_id": str(kind), "as_of": et.isoformat(), "date": et.date().isoformat(),
               "counts": clean_counts(counts)}
        if reason:
            doc["reason"] = str(reason)
        coll.replace_one({"_id": str(kind)}, doc, upsert=True)
        return True
    except Exception as exc:
        log.warning("alert_status: record_pass(%s) failed: %s", kind, exc)
        return False


def _empty_pass() -> dict:
    return {"as_of": None, "date": None, "counts": {}}


def read_pass(kind: str, coll=None) -> dict:
    """{as_of, date, counts[, reason]} for one recorded kind; a missing or
    unreadable doc is the empty shape (as_of None, counts {})."""
    try:
        if coll is None:
            coll = _coll()
        if coll is None:
            return _empty_pass()
        doc = coll.find_one({"_id": str(kind)})
    except Exception as exc:
        log.warning("alert_status: read_pass(%s) failed: %s", kind, exc)
        return _empty_pass()
    if not doc:
        return _empty_pass()
    out = {"as_of": doc.get("as_of") or None, "date": doc.get("date") or None,
           "counts": clean_counts(doc.get("counts") or {})}
    if doc.get("reason"):
        out["reason"] = str(doc["reason"])
    return out


def read_zone_edge(latest_coll=None) -> dict:
    """The zone_edge pass from its own `zone_edge_latest` 'latest' doc — the
    same counts the board payload carries (a pre-2026-09-05 doc lacks the
    skip buckets; they are passed through as absent, never invented)."""
    try:
        if latest_coll is None:
            from . import zone_edge as ZE
            latest_coll = ZE._coll(ZE.LATEST_COLL)
        if latest_coll is None:
            return _empty_pass()
        doc = latest_coll.find_one({"_id": "latest"})
    except Exception as exc:
        log.warning("alert_status: zone_edge latest read failed: %s", exc)
        return _empty_pass()
    if not doc:
        return _empty_pass()
    # The empty-store self-heal write leaves `as_of` None on purpose (that key
    # means "a real pass with rows" to the board and the paper engine) and
    # stamps `ran_at` instead (zone_edge.check_once, 2026-09-05). For THIS
    # payload `as_of` means "when the cron last ran", the same as the two
    # recorded passes, so the stamp falls through; `reason` says what it found.
    out = {"as_of": doc.get("as_of") or doc.get("ran_at") or None, "date": doc.get("date") or None,
           "counts": clean_counts(doc.get("counts") or {})}
    if doc.get("reason"):
        out["reason"] = str(doc["reason"])
    return out


def _with_cadence(kind: str, pass_doc: dict) -> dict:
    """The pass shape plus its scheduled cadence (contract B allows extra keys)."""
    return dict(pass_doc, cadence_sec=int(CADENCE_SEC[kind]))


def status_payload(*, pass_coll=None, latest_coll=None, now: Optional[datetime] = None) -> dict:
    """GET /alerts/status. Every input is injectable for tests; the route passes
    none. Never raises — a dead Mongo is three empty passes, not a 500."""
    from . import zone_edge as ZE                 # lazy: zone_edge's siblings import this module
    now = now or datetime.now(ET)
    et = now.astimezone(ET) if now.tzinfo is not None else now.replace(tzinfo=ET)
    try:
        live = bool(ZE.in_session(et))
    except Exception:
        live = False
    if pass_coll is None:
        pass_coll = _coll()
    return {
        "in_session": live,
        "now_et": et.isoformat(),
        "gate": {"min_room_pct": float(AG.ALERT_MIN_ROOM_PCT),
                 "max_above_demand_pct": float(AG.ALERT_MAX_ABOVE_DEMAND_PCT)},
        "passes": {
            ZONE_EDGE_KIND:      _with_cadence(ZONE_EDGE_KIND, read_zone_edge(latest_coll)),
            "zone_bounce_alert": _with_cadence("zone_bounce_alert", read_pass("zone_bounce_alert", pass_coll)),
            "demand_alert":      _with_cadence("demand_alert", read_pass("demand_alert", pass_coll)),
        },
        "disclaimer": DISCLAIMER,
    }


__all__ = ["PASS_COLL", "PASS_KINDS", "CADENCE_SEC", "record_pass", "record_result", "counts_from_result",
           "read_pass", "read_zone_edge",
           "status_payload", "clean_counts", "DISCLAIMER"]
