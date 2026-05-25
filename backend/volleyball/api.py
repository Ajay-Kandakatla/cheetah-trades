"""FastAPI router for the /volleyball page.

OWNER-ONLY MODULE. All endpoints gate on ``require_house_owner`` which
returns 404 (stealth gate, same pattern as /house) for any user whose
email isn't in HOUSE_OWNER_EMAILS. This keeps the module invisible to
friends signed in via the local-auth path or via Google — they can't
even discover the endpoints exist by URL-guessing.

The content (rehab protocols, workout sessions, education cards) is
keyed to Ajay's specific injury history (right 2nd MTP plantar plate,
right shoulder overuse) and his specific supplement stack — would
mislead any other user.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from auth import require_house_owner

from . import plan as _plan
from . import education as _edu
from . import videos as _videos

router = APIRouter(tags=["volleyball"])


@router.get("/vb/today")
def vb_today(_: str = Depends(require_house_owner)):
    """Today's workout blueprint + supplement schedule + rehab protocols."""
    return JSONResponse(_plan.get_today_plan())


@router.get("/vb/weekly")
def vb_weekly(_: str = Depends(require_house_owner)):
    """Full 7-day rotation."""
    return JSONResponse(_plan.get_weekly_plan())


@router.get("/vb/education")
def vb_education_all(_: str = Depends(require_house_owner)):
    """Full education card bank organized by topic."""
    by_topic = {}
    for topic, pool in _edu.TOPIC_POOLS.items():
        by_topic[topic] = [
            {**c, "topic": topic, "id": f"{topic}-{i}"}
            for i, c in enumerate(pool)
        ]
    return JSONResponse({
        "by_topic":    by_topic,
        "total_count": sum(len(p) for p in _edu.TOPIC_POOLS.values()),
        "today_card":  _edu.pick_today(),
    })


@router.get("/vb/education/{topic}")
def vb_education_topic(topic: str, _: str = Depends(require_house_owner)):
    pool = _edu.TOPIC_POOLS.get(topic)
    if pool is None:
        raise HTTPException(404, f"unknown topic: {topic}")
    return JSONResponse({
        "topic": topic,
        "cards": [{**c, "topic": topic, "id": f"{topic}-{i}"}
                  for i, c in enumerate(pool)],
    })


@router.get("/vb/videos")
def vb_videos(_: str = Depends(require_house_owner)):
    """Curated YouTube videos for leg workouts.

    Grouped by category (plyometrics / strength / single_leg /
    home_no_equipment / knee_health) so the Workouts tab on
    /volleyball can render them as a tabbed playlist. Each video
    carries a verified YouTube ID + a relevance note explaining
    why it fits the user's profile.
    """
    return JSONResponse({
        "by_category":   _videos.get_videos_by_category(),
        "category_meta": _videos.CATEGORY_META,
        "total_count":   len(_videos.VIDEOS),
    })
