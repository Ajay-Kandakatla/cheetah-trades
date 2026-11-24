"""🧾 My trades vs GG — the ONE writer of `owner_trade_log` (spec accountability §3.1, WP-BE1, 2026-11-23).

Ajay 2026-11-23, verbatim: "Please create a rule to warn me to not over trade and hold me accountable if I am missing out
any gajjalas rules".

One doc per 🧾 tap: {_id, owner, date (ET), sym, alert_id, entry, stop, stop_src, shares, grade, why_b, patience,
discipline, tap_ts (UTC, the server's clock), quiet_at_tap, add_to, warned_at_tap, exit_px, exit_ts, exit_note, void,
void_ts}. Index (owner, date). Every write goes through this module and nothing else; code never rewrites a tapped fact
(checks are graded at read time in accountability.py). A NEW collection, outside the gajjala store's own set (the 🚩 /
🏁 / 👀 builds never read it). Reads answer None on a fault (no handle, or the driver raised) — never "nothing logged".
Writes answer False / "error" on a fault. Never raises.
"""
from __future__ import annotations

import logging
import threading
import uuid
from typing import Optional

log = logging.getLogger("chart_maps.gajjala.accountability_store")

COLL = "owner_trade_log"
INDEX = (("owner", 1), ("date", 1))
_INDEXED = {"done": False}
_LOCK = threading.Lock()
EXIT_STATES = ("ok", "absent", "already", "void", "error")
VOID_STATES = ("ok", "absent", "already", "error")


def _coll():
    """The Mongo handle (the house `_get_db`), or None. Tests monkeypatch this."""
    try:
        from portfolio.store import _get_db
        db = _get_db()
        return db[COLL] if db is not None else None
    except Exception as exc:                                    # noqa: BLE001
        log.debug("owner_trade_log: no mongo: %s", exc)
        return None


def ensure_index(c=None) -> None:
    """Idempotent (owner, date) index — once per process, on the first write."""
    c = c if c is not None else _coll()
    if c is None:
        return
    with _LOCK:
        if _INDEXED["done"]:
            return
        try:
            c.create_index(list(INDEX))
            _INDEXED["done"] = True
        except Exception as exc:                                # noqa: BLE001
            log.warning("owner_trade_log: index failed: %s", type(exc).__name__)


def new_id() -> str:
    return uuid.uuid4().hex


def _find(q: dict) -> Optional[list]:
    c = _coll()
    if c is None:
        return None
    try:
        return [d for d in c.find(q) if isinstance(d, dict)]
    except Exception as exc:                                    # noqa: BLE001
        log.warning("owner_trade_log: read failed: %s", type(exc).__name__)
        return None


def all_for(owner: str) -> Optional[list]:
    """Every tap of this owner (his log is one doc per tap — small). None on a read fault."""
    return _find({"owner": owner})


def day(owner: str, date_iso: str) -> Optional[list]:
    return _find({"owner": owner, "date": date_iso})


def get(owner: str, trade_id: str) -> Optional[dict]:
    """One doc of this owner by id; None when absent or on a fault (the route answers 404 either way)."""
    c = _coll()
    if c is None or not isinstance(trade_id, str) or not trade_id:
        return None
    try:
        d = c.find_one({"_id": trade_id, "owner": owner})
    except Exception as exc:                                    # noqa: BLE001
        log.warning("owner_trade_log: get failed: %s", type(exc).__name__)
        return None
    return d if isinstance(d, dict) else None


def insert(doc: dict) -> bool:
    """THE tap write — one insert_one. False on a fault (nothing half-written)."""
    c = _coll()
    if c is None or not isinstance(doc, dict) or not doc.get("_id") or not doc.get("owner"):
        return False
    ensure_index(c)
    try:
        c.insert_one(dict(doc))
        return True
    except Exception as exc:                                    # noqa: BLE001
        log.warning("owner_trade_log: insert failed: %s", type(exc).__name__)
        return False


def set_exit(owner: str, trade_id: str, exit_px: float, exit_ts, exit_note: Optional[str]) -> str:
    """The exit tap — a compare-and-set that lands ONLY on a doc with no exit yet and not void:
    "ok" | "absent" (no such doc for this owner) | "already" (an exit is on file) | "void" | "error"."""
    c = _coll()
    if c is None:
        return EXIT_STATES[4]
    cur = get(owner, trade_id)
    if cur is None:
        return EXIT_STATES[1]
    if cur.get("void"):
        return EXIT_STATES[3]
    if cur.get("exit_px") is not None:
        return EXIT_STATES[2]
    try:
        res = c.update_one({"_id": trade_id, "owner": owner, "exit_px": None, "void": {"$ne": True}},
                           {"$set": {"exit_px": exit_px, "exit_ts": exit_ts, "exit_note": exit_note}})
    except Exception as exc:                                    # noqa: BLE001
        log.warning("owner_trade_log: exit failed: %s", type(exc).__name__)
        return EXIT_STATES[4]
    return EXIT_STATES[0] if int(getattr(res, "matched_count", 0) or 0) > 0 else EXIT_STATES[2]


def set_void(owner: str, trade_id: str, void_ts) -> str:
    """The void tap — the doc is KEPT, `void` True: "ok" | "absent" | "already" | "error"."""
    c = _coll()
    if c is None:
        return VOID_STATES[3]
    cur = get(owner, trade_id)
    if cur is None:
        return VOID_STATES[1]
    if cur.get("void"):
        return VOID_STATES[2]
    try:
        res = c.update_one({"_id": trade_id, "owner": owner, "void": {"$ne": True}},
                           {"$set": {"void": True, "void_ts": void_ts}})
    except Exception as exc:                                    # noqa: BLE001
        log.warning("owner_trade_log: void failed: %s", type(exc).__name__)
        return VOID_STATES[3]
    return VOID_STATES[0] if int(getattr(res, "matched_count", 0) or 0) > 0 else VOID_STATES[2]
