"""HTTP routes for the personal house dashboard.

Every route is gated by ``require_house_owner`` — even other authenticated
users in the email allowlist get 403.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from auth import require_house_owner
from house import store, playbook as playbook_mod, scraper as scraper_mod

router = APIRouter()


@router.get("/house/config")
async def house_get_config(owner: str = Depends(require_house_owner)):
    cfg = store.get_config(owner)
    return JSONResponse({"config": cfg})


@router.post("/house/config")
async def house_set_config(
    payload: dict = Body(...),
    owner: str = Depends(require_house_owner),
):
    res = store.upsert_config(owner, payload)
    return JSONResponse(res)


@router.get("/house/dashboard")
async def house_dashboard(owner: str = Depends(require_house_owner)):
    """The whole rolled-up view the frontend needs in one round trip."""
    cfg     = store.get_config(owner) or {}
    latest  = store.latest_snapshot(owner)
    history = store.list_snapshots(owner, days=60)
    comps   = store.list_comps(owner)
    events  = store.list_events(owner, limit=50)
    pb = playbook_mod.build_playbook(
        config=cfg, latest=latest, history=history, comps=comps, events=events,
    )
    return JSONResponse({
        "config":   cfg,
        "latest":   latest,
        "history":  history,
        "comps":    comps,
        "events":   events,
        "playbook": pb,
    })


@router.post("/house/snapshot")
async def house_snapshot_post(
    payload: dict = Body(...),
    owner: str = Depends(require_house_owner),
):
    """Save (or merge into) today's snapshot. Manual numbers override scraper."""
    if not isinstance(payload, dict):
        raise HTTPException(400, "expected JSON object")
    metrics = {**payload, "source": payload.get("source") or "manual"}
    return JSONResponse(store.upsert_snapshot(owner, metrics))


@router.post("/house/scrape")
async def house_scrape_now(owner: str = Depends(require_house_owner)):
    """Run the Redfin/Zillow/Realtor scrapers using the saved config URLs
    and merge the result into today's snapshot. Best-effort; failures don't
    raise — the user can always enter numbers manually."""
    cfg = store.get_config(owner) or {}
    metrics = scraper_mod.scrape_all(
        redfin_url=cfg.get("redfin_url"),
        zillow_url=cfg.get("zillow_url"),
        realtor_url=cfg.get("realtor_url"),
    )
    # Pop block markers — they're status, not data we want to persist.
    blocked = [metrics.pop(k) for k in list(metrics) if k.startswith("_blocked")]

    real_keys = [k for k in metrics if k != "source"]
    if not real_keys:
        reason = "scraper found nothing — enter numbers manually below."
        if blocked:
            reason = f"blocked by: {', '.join(blocked)}. Enter manually below."
        return JSONResponse({
            "ok": False,
            "reason": reason,
            "blocked": blocked,
            "metrics": metrics,
        })
    res = store.upsert_snapshot(owner, metrics)
    return JSONResponse({
        "ok": True,
        "metrics": metrics,
        "blocked": blocked,
        "stored": res,
    })


@router.get("/house/comps")
async def house_comps_list(owner: str = Depends(require_house_owner)):
    return JSONResponse({"comps": store.list_comps(owner)})


@router.post("/house/comps")
async def house_comp_add(
    payload: dict = Body(...),
    owner: str = Depends(require_house_owner),
):
    if not payload.get("address"):
        raise HTTPException(400, "address required")
    return JSONResponse(store.add_comp(owner, payload))


@router.delete("/house/comps")
async def house_comp_remove(
    address: str = Query(...),
    owner: str = Depends(require_house_owner),
):
    return JSONResponse(store.remove_comp(owner, address))


@router.get("/house/events")
async def house_events_list(owner: str = Depends(require_house_owner)):
    return JSONResponse({"events": store.list_events(owner)})


@router.post("/house/events")
async def house_event_add(
    payload: dict = Body(...),
    owner: str = Depends(require_house_owner),
):
    return JSONResponse(store.add_event(owner, payload))


@router.delete("/house/events/{event_id}")
async def house_event_remove(
    event_id: str,
    owner: str = Depends(require_house_owner),
):
    return JSONResponse(store.remove_event(owner, event_id))
