"""Kids activity routes — household-gated like /food and /house."""
from __future__ import annotations

import random
from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse

from auth import require_household_member
from . import activities as act_mod, store, video_resolver as vr

router = APIRouter()


@router.get("/kids/today")
async def kids_today(
    age: float = Query(3.5, description="Child's age in years"),
    mess_max: int = Query(5, ge=1, le=5),
    duration_max: int = Query(60, ge=5, le=180),
    framework: str | None = Query(None),
    user: str = Depends(require_household_member),
):
    """Suggest 3 activities for today.

    Filters for child's age + max mess level (low when daughter is sick or
    you're tired) + max duration. Excludes anything done in the last 7 days
    so you're not doing 'lentil scoop' five days running.
    """
    recent = store.recent_ids(user, days=7)
    pool = act_mod.filter_activities(
        framework=framework,
        mess_max=mess_max,
        duration_max=duration_max,
        age=age,
        exclude_ids=list(recent),
    )
    if not pool:
        # Cooldown wiped the pool — relax the recent-id filter
        pool = act_mod.filter_activities(
            framework=framework,
            mess_max=mess_max,
            duration_max=duration_max,
            age=age,
        )
    random.shuffle(pool)
    picks = pool[:3]
    # Attach validated videos when cached — frontend uses these for direct
    # links instead of YouTube-search fallback.
    for p in picks:
        cached = vr.get_cached(p["id"])
        if cached:
            p["validated_video"] = {
                "video_id":    cached.get("video_id"),
                "video_url":   cached.get("video_url"),
                "title":       cached.get("title"),
                "author_name": cached.get("author_name"),
                "thumbnail":   cached.get("thumbnail"),
            }
    return JSONResponse({
        "date_et": store._today_et(),
        "picks": picks,
        "filter": {"age": age, "mess_max": mess_max, "duration_max": duration_max,
                   "framework": framework},
        "recent_count": len(recent),
        "frameworks": act_mod.FRAMEWORKS,
    })


@router.get("/kids/all")
async def kids_all(
    framework: str | None = Query(None),
    user: str = Depends(require_household_member),
):
    """Full activity DB — for browsing on rainy days."""
    out = act_mod.filter_activities(framework=framework) if framework else list(act_mod.ACTIVITIES)
    return JSONResponse({"activities": out, "n": len(out)})


@router.get("/kids/influencers")
async def kids_influencers(user: str = Depends(require_household_member)):
    """The research-backed parenting voices behind the activities."""
    return JSONResponse({"influencers": act_mod.INFLUENCERS})


@router.post("/kids/log")
async def kids_log_done(
    payload: dict = Body(...),
    user: str = Depends(require_household_member),
):
    aid = (payload.get("activity_id") or "").strip()
    if not aid:
        return JSONResponse({"ok": False, "reason": "activity_id required"}, status_code=400)
    return JSONResponse(store.log_done(
        user, aid,
        rating=payload.get("rating"),
        notes=payload.get("notes", ""),
        date_et=payload.get("date_et"),
    ))


@router.get("/kids/history")
async def kids_history(
    days: int = Query(21, ge=1, le=90),
    user: str = Depends(require_household_member),
):
    return JSONResponse({"days": days, "rows": store.history(user, days=days)})
