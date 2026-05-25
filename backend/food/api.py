"""HTTP routes for the family food planner.

Household-shared and stealth-gated to HOUSE_OWNER_EMAILS (returns 404 to
anyone else). Both Ajay and Vineetha see the same shared menu history,
preferences, pantry, and grocery list — same partition key in Mongo, like
the /house dashboard.

Recipes endpoint stays open since it's just static reference data.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse

from auth import require_household_member
from . import planner, store, grocery, recipes as recipes_mod

router = APIRouter()


@router.get("/food/today")
async def food_today(
    quick_only: bool = Query(False, description="Restrict to quick-cook recipes (≤30min, no heavy prep)"),
    user: str = Depends(require_household_member),
):
    """Today's two menu options + history summary.

    `quick_only=true` hard-filters to dishes flagged `quick: True` —
    skips multi-hour braises (paya, biryani) and labor-intensive prep
    (methi paratha). Useful on tired weeknights.
    """
    return JSONResponse(planner.suggest_today(user, quick_only=quick_only))


@router.get("/food/history")
async def food_history(
    days: int = Query(21, ge=1, le=90),
    user: str = Depends(require_household_member),
):
    """Last N days of cooked entries. Used for the calendar view."""
    return JSONResponse({"days": days, "rows": store.history(user, days=days)})


@router.post("/food/log")
async def food_log(
    payload: dict = Body(...),
    user: str = Depends(require_household_member),
):
    """Record what was cooked.
    Payload: {"slot": "dinner"|"adult_breakfast"|"kid_breakfast",
              "recipe_ids": ["palak_dal", "pappu_charu"],
              "date_et":   "2026-05-08"  (optional, defaults to today)}
    """
    slot = (payload.get("slot") or "").strip()
    rids = payload.get("recipe_ids") or []
    if slot not in {"adult_breakfast", "kid_breakfast", "dinner"}:
        return JSONResponse({"ok": False, "reason": "invalid slot"}, status_code=400)
    if not isinstance(rids, list):
        return JSONResponse({"ok": False, "reason": "recipe_ids must be a list"}, status_code=400)
    return JSONResponse(store.log_cooked(user, slot, rids, date_et=payload.get("date_et")))


@router.get("/food/preferences")
async def food_prefs_get(user: str = Depends(require_household_member)):
    return JSONResponse(store.get_preferences(user))


@router.post("/food/preferences")
async def food_prefs_set(
    payload: dict = Body(...),
    user: str = Depends(require_household_member),
):
    return JSONResponse(store.set_preferences(user, payload))


@router.get("/food/pantry")
async def food_pantry_get(user: str = Depends(require_household_member)):
    return JSONResponse(store.get_pantry(user))


@router.post("/food/pantry")
async def food_pantry_set(
    payload: dict = Body(...),
    user: str = Depends(require_household_member),
):
    return JSONResponse(store.set_pantry(user, payload))


@router.get("/food/grocery")
async def food_grocery(user: str = Depends(require_household_member)):
    """Weekly grocery list — projected from this week's planned + cooked menus."""
    return JSONResponse(grocery.weekly_grocery(user))


@router.get("/food/eat-out")
async def food_eat_out(
    buffet: bool | None = Query(None),
    out_of_box: bool = Query(False),
    n: int = Query(5, ge=1, le=20),
    user: str = Depends(require_household_member),
):
    """Weekend eat-out / buffet picks. Curated DFW Indian + non-Indian
    restaurants within 25 min of McKinney/Frisco. Each entry has Google
    Maps + Yelp links so hours/menu are always current."""
    from . import eat_out as _eo
    return JSONResponse({"picks": _eo.picks_for_today(want_buffet=buffet, out_of_box=out_of_box, n=n)})


@router.get("/food/recipes")
async def food_recipes_list():
    """Static recipe DB. Cached by the browser; not user-scoped."""
    return JSONResponse({"recipes": recipes_mod.RECIPES, "n": len(recipes_mod.RECIPES)})


@router.get("/food/recipes/{recipe_id}")
async def food_recipe_detail(recipe_id: str):
    r = recipes_mod.by_id(recipe_id)
    if not r:
        return JSONResponse({"ok": False, "reason": "not found"}, status_code=404)
    return JSONResponse(r)
