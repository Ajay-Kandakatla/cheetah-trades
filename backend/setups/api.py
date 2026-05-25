"""FastAPI router for the three setups (PEG / ORB / Inside-Day).

Endpoints
---------
GET  /setups                     — combined feed (latest across all kinds)
GET  /setups/{kind}              — kind ∈ {peg, orb, inside_day}
POST /setups/{kind}/scan         — admin-only force re-run of a scanner
                                    (useful for testing without waiting on cron)
POST /setups/expire-stale        — admin-only sweep; cron also calls this

The list endpoints are open to any authenticated user (the SEPA universe
is already shared — see access/store.py). The scan + expire endpoints
are admin-only because they can be expensive (PEG scan = ~50 Massive
calls) and they shouldn't be invokable by a friend account.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from auth import current_user_email

from . import store

log = logging.getLogger("setups.api")

router = APIRouter(prefix="/setups", tags=["setups"])


_KIND_DISPATCH = {
    "peg":                  ("setups.peg",                  "scan"),
    "inside_day":           ("setups.inside_day",           "scan"),
    "orb_capture":          ("setups.orb",                  "capture_range"),
    "orb_watch":            ("setups.orb",                  "check_triggers"),
    "low_cheat":            ("setups.cheat",                "scan_low"),
    "mid_cheat":            ("setups.cheat",                "scan_mid"),
    "high_cheat":           ("setups.cheat",                "scan_high"),
    "bull_flag":            ("setups.bull_flag",            "scan"),
    "episodic_pivot":       ("setups.episodic_pivot",       "scan"),
    "high_tight_flag":      ("setups.high_tight_flag",      "scan"),
    "post_earnings_drift":  ("setups.post_earnings_drift",  "scan"),
    # Kell — Cycle of Price Action scanners (Oliver Kell, 2021). All
    # write into the same `setups` Mongo collection with their own
    # `kind` discriminator. UI: /kell page. Cycle order:
    # reversal_extension → wedge_pop → ema_crossback → base_n_break →
    # exhaustion_extension → wedge_drop → (cycle repeats).
    "reversal_extension":     ("kell.reversal_extension",     "scan"),
    "wedge_pop":              ("kell.wedge_pop",              "scan"),
    "ema_crossback":          ("kell.ema_crossback",          "scan"),
    "base_n_break":           ("kell.base_n_break",           "scan"),
    "exhaustion_extension":   ("kell.exhaustion_extension",   "scan"),
    "wedge_drop":             ("kell.wedge_drop",             "scan"),
}
_VALID_KINDS = {
    "peg", "orb", "inside_day",
    "low_cheat", "mid_cheat", "high_cheat",
    "bull_flag", "episodic_pivot",
    "high_tight_flag", "post_earnings_drift",
    # Kell additions — 6 canonical Cycle of Price Action patterns.
    "reversal_extension", "wedge_pop", "ema_crossback",
    "base_n_break", "exhaustion_extension", "wedge_drop",
}


def _is_admin(email: str) -> bool:
    """Tight admin check — only the configured HOUSE_OWNER can re-run
    scanners or sweep state. Mirrors the pattern used in access/api.py
    so adding a new admin only touches one place (env var)."""
    try:
        from auth import HOUSE_OWNER_EMAILS
        return email.lower() in {e.lower() for e in HOUSE_OWNER_EMAILS}
    except Exception:
        return False


@router.get("")
def list_all(
    limit: int = Query(50, ge=1, le=200),
    only_pending: bool = Query(True),
    email: str = Depends(current_user_email),
):
    """Combined feed across all kinds — for the dashboard's mixed view."""
    rows = store.get_setups(limit=limit, only_pending=only_pending)
    return JSONResponse({
        "count": len(rows),
        "setups": rows,
    })


@router.get("/{kind}")
def list_one_kind(
    kind: str,
    limit: int = Query(50, ge=1, le=200),
    only_pending: bool = Query(True),
    email: str = Depends(current_user_email),
):
    if kind not in _VALID_KINDS:
        raise HTTPException(404, f"unknown kind: {kind}")
    rows = store.get_setups(kind=kind, limit=limit, only_pending=only_pending)
    return JSONResponse({
        "kind": kind,
        "count": len(rows),
        "setups": rows,
    })


@router.post("/{kind}/scan")
def force_scan(
    kind: str,
    email: str = Depends(current_user_email),
):
    """Admin: re-run a specific scanner ad hoc."""
    if not _is_admin(email):
        raise HTTPException(403, "admin only")
    # Map UI-friendly kind → internal callable
    target_map = {
        "peg":                 _KIND_DISPATCH["peg"],
        "inside_day":          _KIND_DISPATCH["inside_day"],
        # ORB has two phases — default to capture; pass kind="orb_watch"
        # explicitly to invoke the watcher.
        "orb":                 _KIND_DISPATCH["orb_capture"],
        "orb_watch":           _KIND_DISPATCH["orb_watch"],
        "low_cheat":           _KIND_DISPATCH["low_cheat"],
        "mid_cheat":           _KIND_DISPATCH["mid_cheat"],
        "high_cheat":          _KIND_DISPATCH["high_cheat"],
        "bull_flag":           _KIND_DISPATCH["bull_flag"],
        "episodic_pivot":      _KIND_DISPATCH["episodic_pivot"],
        "high_tight_flag":     _KIND_DISPATCH["high_tight_flag"],
        "post_earnings_drift": _KIND_DISPATCH["post_earnings_drift"],
        # Kell scanners — Cycle of Price Action.
        "reversal_extension":     _KIND_DISPATCH["reversal_extension"],
        "wedge_pop":              _KIND_DISPATCH["wedge_pop"],
        "ema_crossback":          _KIND_DISPATCH["ema_crossback"],
        "base_n_break":           _KIND_DISPATCH["base_n_break"],
        "exhaustion_extension":   _KIND_DISPATCH["exhaustion_extension"],
        "wedge_drop":             _KIND_DISPATCH["wedge_drop"],
    }
    if kind not in target_map:
        raise HTTPException(404, f"unknown scan target: {kind}")
    mod_name, func_name = target_map[kind]
    try:
        import importlib
        mod = importlib.import_module(mod_name)
        fn = getattr(mod, func_name)
        result = fn()
    except Exception as exc:
        log.exception("force_scan(%s) failed", kind)
        raise HTTPException(500, f"scan failed: {exc}")
    n = len(result) if isinstance(result, list) else int(result or 0)
    return JSONResponse({"kind": kind, "ran": True, "count": n})


@router.post("/expire-stale")
def expire_stale(email: str = Depends(current_user_email)):
    if not _is_admin(email):
        raise HTTPException(403, "admin only")
    n = store.expire_stale()
    return JSONResponse({"expired": n})
