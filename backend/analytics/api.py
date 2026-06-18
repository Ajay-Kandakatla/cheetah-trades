"""HTTP routes for usage analytics.

Two endpoint groups:

  Ingestion (any authenticated user posts their own events):
    POST /analytics/event/start  → returns {id}
    POST /analytics/event/end    → mark a row complete

  Dashboard (admin-only — gated to ajaykandakatla@gmail.com, hardcoded):
    GET  /analytics/dashboard?days=14
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from auth import current_user_email
from analytics import store

router = APIRouter()

# Sole admin — never expected to change. Hardcoded rather than env-var
# because we don't want accidental privilege escalation via misconfig.
ADMIN_EMAIL = "ajaykandakatla@gmail.com"


def require_admin(email: str = Depends(current_user_email)) -> str:
    """Gate analytics dashboard to the sole admin. Returns the email on
    success; raises 404 (not 403) to keep the dashboard's existence
    opaque to non-admins."""
    if email.lower() != ADMIN_EMAIL:
        raise HTTPException(status_code=404)
    return email


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------
@router.post("/analytics/event/start")
async def analytics_event_start(
    payload: dict = Body(...),
    email: str = Depends(current_user_email),
):
    """Log the start of a page view. Returns the row id so the client
    can later send `/event/end` with the duration."""
    module = (payload.get("module") or "").strip()[:40]
    route  = (payload.get("route")  or "").strip()[:200]
    session_id = (payload.get("session_id") or "").strip()[:64]
    if not module or not route:
        raise HTTPException(400, "module + route required")
    # Sync pymongo insert → push to threadpool. Without this, every page
    # navigation parks the loop on a Mongo insert. Fires on every route
    # change, so it would compound with anything else mid-flight.
    rid = await asyncio.to_thread(
        store.start_event,
        user_email=email, module=module, route=route, session_id=session_id,
    )
    return JSONResponse({"id": rid})


@router.post("/analytics/event/end")
async def analytics_event_end(payload: dict = Body(...)):
    """Mark a page-view row as ended. Public-ish (no user check) because
    the client posts the row id directly — and beacons need to fire even
    when the auth cookie has expired (page-unload time)."""
    rid = (payload.get("id") or "").strip()
    dur = payload.get("duration_sec")
    if not rid:
        return JSONResponse({"ok": False, "reason": "id required"})
    # Sync pymongo update — threaded for the same reason as start_event.
    ok = await asyncio.to_thread(
        store.end_event,
        rid, duration_sec=int(dur) if dur is not None else None,
    )
    return JSONResponse({"ok": ok})


# ---------------------------------------------------------------------------
# Web-vitals / page-load RUM (Ajay 2026-06-17)
# ---------------------------------------------------------------------------
@router.post("/analytics/perf")
async def analytics_perf(payload: dict = Body(...)):
    """Ingest a batch of web-vitals / page-load samples (sent via sendBeacon).
    Public-ish like /event/end — beacons fire at page-hide when the auth cookie
    may already be gone, and the payload is non-sensitive timing data only.
    Batch is capped to keep a bad client from flooding."""
    events = payload.get("events")
    if not isinstance(events, list):
        return JSONResponse({"ok": False, "stored": 0})
    stored = await asyncio.to_thread(store.record_perf, events[:50])
    return JSONResponse({"ok": True, "stored": stored})


@router.get("/analytics/perf/summary")
async def analytics_perf_summary(
    days: int = Query(14, ge=1, le=180),
    _admin: str = Depends(require_admin),
):
    """p50/p75/p95 per page + metric, with a slow-vs-fast-connection split —
    the data that tells us which pages to optimize for low-bandwidth users."""
    out = await asyncio.to_thread(store.aggregate_perf, days)
    return JSONResponse(out)


# ---------------------------------------------------------------------------
# "What's new" feature highlights (Ajay 2026-06-18)
# ---------------------------------------------------------------------------
@router.get("/features/seen")
async def features_seen(email: str = Depends(current_user_email)):
    """Feature ids this user has already viewed (highlight cleared)."""
    seen = await asyncio.to_thread(store.feature_seen_set, email)
    return JSONResponse({"seen": seen})


@router.post("/features/seen")
async def features_mark_seen(
    payload: dict = Body(...),
    email: str = Depends(current_user_email),
):
    """Mark a feature viewed (clears its highlight) + log the first view."""
    feature = (payload.get("feature") or "").strip()
    if not feature:
        return JSONResponse({"ok": False, "reason": "feature required"})
    newly = await asyncio.to_thread(store.mark_feature_seen, email, feature)
    return JSONResponse({"ok": True, "newly": newly})


@router.post("/features/impression")
async def features_impression(
    payload: dict = Body(...),
    email: str = Depends(current_user_email),
):
    """Log new-feature highlights the user was shown but hasn't opened yet."""
    features = payload.get("features")
    if not isinstance(features, list):
        return JSONResponse({"ok": False, "logged": 0})
    n = await asyncio.to_thread(store.log_feature_impressions, email, features)
    return JSONResponse({"ok": True, "logged": n})


# ---------------------------------------------------------------------------
# Dashboard (admin)
# ---------------------------------------------------------------------------
@router.get("/analytics/dashboard")
async def analytics_dashboard(
    days: int = Query(14, ge=1, le=180),
    _admin: str = Depends(require_admin),
):
    # Aggregation can scan many docs depending on `days` — keep it off
    # the event loop.
    out = await asyncio.to_thread(store.aggregate_dashboard, days)
    return JSONResponse(out)
