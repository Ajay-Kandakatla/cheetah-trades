"""📅 Long Term — the three Mongo collections (spec §3.9, WP-RUN).

Ajay 2026-11-12, verbatim: "Save this entire list for me. In a New tab - Long Term - Remember this analays criteria I
am asking you to for this tab and keep updating it from all the other tabs info.. Weekly and if something gets dropped
let me know when to like is Sales drop or Stage 2 to Stage 3 or stage 4 changes."

  * `long_term_list_runs`    — INSERT ONLY, `_id` = the ISO week ("2026-W46"). A run doc is never updated, replaced
                               or deleted: a week that ran is history.
  * `long_term_list_forward` — INSERT ONLY: `_id: "base"` (frozen ONCE) + one point doc per ISO week.
  * `long_term_list_claims`  — `run:<week>`, `digest:<week>`; the insert IS the claim; state updates allowed here only.

Every call is fenced: Mongo down → None / [] / False plus a log line, never a raise into the caller. Collections are
passed in (tests hand fakes that record every method called) or resolved from `_db()` — the `longterm._db` pattern.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from . import constants as C

log = logging.getLogger("long_term_list.store")

BASE_ID = "base"
RUN_CLAIM = "run:"
DIGEST_CLAIM = "digest:"


def _db():
    """The app database (prices._get_mongo().database), or None when Mongo is unreachable."""
    try:
        from sepa import prices
        coll = prices._get_mongo()
        return coll.database if coll is not None else None
    except Exception as exc:                                   # noqa: BLE001
        log.warning("long_term_list: mongo unavailable: %s", exc)
        return None


def colls(db=None) -> Optional[dict]:
    """{"runs", "forward", "claims"} collections, or None when there is no database."""
    d = db if db is not None else _db()
    if d is None:
        return None
    try:
        return {"runs": d[C.RUNS_COLL], "forward": d[C.FORWARD_COLL], "claims": d[C.CLAIMS_COLL]}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("long_term_list: collections unavailable: %s", exc)
        return None


def iso_week_id(d) -> str:
    """'2026-W46' for any date / datetime / 'YYYY-MM-DD' string."""
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    if isinstance(d, datetime):
        d = d.date()
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _dup_error():
    try:
        from pymongo.errors import DuplicateKeyError
        return DuplicateKeyError
    except Exception:                                          # pragma: no cover — pymongo is in the image
        return KeyError


def _is_dup(exc: Exception) -> bool:
    return isinstance(exc, _dup_error()) or type(exc).__name__ == "DuplicateKeyError"


# ── claims ──────────────────────────────────────────────────────────────────────────────────────────────────────
def claim(claims, claim_id: str, now_iso: str, **extra) -> Optional[bool]:
    """Insert `claim_id` (the insert IS the claim). True claimed · False already held · None store unreachable.

    A claim left in state "failed" (the run raised) is taken back ONCE through a conditional update on that state, so
    the recovery recipe (`--run-now`) can redo a week whose run crashed; a "claimed" / "done" claim is never retaken."""
    if claims is None:
        return None
    doc = {"_id": claim_id, "state": "claimed", "claimed_at": now_iso, **extra}
    try:
        claims.insert_one(doc)
        return True
    except Exception as exc:                                   # noqa: BLE001
        if not _is_dup(exc):
            log.warning("long_term_list: claim %s failed: %s", claim_id, exc)
            return None
    try:
        res = claims.update_one({"_id": claim_id, "state": "failed"},
                                {"$set": {"state": "claimed", "claimed_at": now_iso, "retaken": True, **extra}})
        return bool(getattr(res, "modified_count", 0))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("long_term_list: claim retake %s failed: %s", claim_id, exc)
        return False


def set_claim(claims, claim_id: str, state: str, **fields) -> bool:
    if claims is None:
        return False
    try:
        claims.update_one({"_id": claim_id}, {"$set": {"state": state, **fields}})
        return True
    except Exception as exc:                                   # noqa: BLE001
        log.warning("long_term_list: claim %s → %s not written: %s", claim_id, state, exc)
        return False


# ── runs (INSERT ONLY) ──────────────────────────────────────────────────────────────────────────────────────────
def runs_desc(runs, limit: Optional[int] = None) -> list:
    """Every stored run, newest ISO week first ([] when unreachable)."""
    if runs is None:
        return []
    try:
        docs = list(runs.find({}))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("long_term_list: runs read failed: %s", exc)
        return []
    docs = [d for d in docs if isinstance(d, dict) and isinstance(d.get("_id"), str)]
    docs.sort(key=lambda d: d["_id"], reverse=True)
    return docs[:limit] if limit else docs


def insert_run(runs, doc: dict) -> Optional[bool]:
    """True inserted · False that week already has a run (never overwritten) · None unreachable."""
    if runs is None:
        return None
    try:
        runs.insert_one(doc)
        return True
    except Exception as exc:                                   # noqa: BLE001
        if _is_dup(exc):
            return False
        log.warning("long_term_list: run %s not stored: %s", doc.get("_id"), exc)
        return None


# ── forward record (INSERT ONLY) ────────────────────────────────────────────────────────────────────────────────
def forward_docs(fwd) -> list:
    if fwd is None:
        return []
    try:
        return [d for d in fwd.find({}) if isinstance(d, dict)]
    except Exception as exc:                                   # noqa: BLE001
        log.warning("long_term_list: forward read failed: %s", exc)
        return []


def insert_forward(fwd, doc: dict) -> Optional[bool]:
    """True inserted · False that `_id` exists already (the base is frozen once; a week's point is never rewritten)."""
    if fwd is None:
        return None
    try:
        fwd.insert_one(doc)
        return True
    except Exception as exc:                                   # noqa: BLE001
        if _is_dup(exc):
            return False
        log.warning("long_term_list: forward %s not stored: %s", doc.get("_id"), exc)
        return None


# ── 🔔 zone reaches (2026-11-12, scratchpad pkzone/spec.md §3.2 — critique C1 / C2) ─────────────────────────────
# Ajay 2026-11-12, verbatim: "add an alert list when stocks reach Pankaj's zones and also tell me if you finish the
# long term tabs in general".
#   * `long_term_zone_latch` — INSERT ONLY, `_id` "<session>|<SYM>|<zone>": the push gate. The insert IS the latch; a
#     duplicate means "already rang this session" and nothing is written. Never updated, replaced, deleted or retaken.
#   * `long_term_zone_state` — one doc per ET session: the latest pass read (`$set`), every reach of the session
#     (`reaches.<SYM|zone>`, first write wins — the tab's log) and the push result written ONCE by the pass whose
#     latch insert succeeded (`results.<SYM|zone>`). This module never uses an array-append operator.
def zone_colls(db=None) -> Optional[dict]:
    """{"latch", "state"} collections, or None when there is no database."""
    d = db if db is not None else _db()
    if d is None:
        return None
    try:
        return {"latch": d[C.ZONE_LATCH_COLL], "state": d[C.ZONE_STATE_COLL]}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("long_term_list: zone collections unavailable: %s", exc)
        return None


def latch(coll, doc: dict) -> Optional[bool]:
    """Insert the latch doc. True inserted · False that `_id` is held (DuplicateKey) · None any other error / no coll.
    Only `insert_one` is ever called on this collection — no retake (a retake would allow a second send)."""
    if coll is None:
        return None
    try:
        coll.insert_one(doc)
        return True
    except Exception as exc:                                   # noqa: BLE001
        if _is_dup(exc):
            return False
        log.warning("long_term_list: zone latch %s not written: %s", doc.get("_id"), exc)
        return None


def zone_state_write(coll, session: str, fields: dict) -> bool:
    """`$set` the latest pass read on the session doc (upsert). Fenced."""
    if coll is None:
        return False
    try:
        coll.update_one({"_id": session}, {"$set": dict(fields)}, upsert=True)
        return True
    except Exception as exc:                                   # noqa: BLE001
        log.warning("long_term_list: zone state %s not written: %s", session, exc)
        return False


def zone_reach_add(coll, session: str, rkey: str, rec: dict) -> Optional[bool]:
    """Log one reach, FIRST WRITE WINS: a conditional `$set` on `reaches.<rkey>` not existing yet (no upsert — the
    session doc was written by `zone_state_write` earlier in the same pass). True first record · False already
    logged (the first time and price are kept) · None error / no coll."""
    if coll is None:
        return None
    field = f"reaches.{rkey}"
    try:
        res = coll.update_one({"_id": session, field: {"$exists": False}}, {"$set": {field: dict(rec)}})
        return bool(getattr(res, "modified_count", 0))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("long_term_list: zone reach %s/%s not logged: %s", session, rkey, exc)
        return None


def zone_result_set(coll, session: str, rkey: str, result: dict) -> bool:
    """`$set` `results.<rkey>` — called ONLY by the pass whose latch insert returned True (or None = no store);
    never for a duplicate insert (critique C1)."""
    if coll is None:
        return False
    try:
        coll.update_one({"_id": session}, {"$set": {f"results.{rkey}": dict(result)}})
        return True
    except Exception as exc:                                   # noqa: BLE001
        log.warning("long_term_list: zone result %s/%s not written: %s", session, rkey, exc)
        return False


def zone_state(coll, session: str) -> Optional[dict]:
    """The session's state doc, or None (missing / unreachable)."""
    if coll is None or not session:
        return None
    try:
        doc = coll.find_one({"_id": session})
        return doc if isinstance(doc, dict) else None
    except Exception as exc:                                   # noqa: BLE001
        log.warning("long_term_list: zone state %s unreadable: %s", session, exc)
        return None
