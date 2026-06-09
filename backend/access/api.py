"""HTTP routes for the per-user feature access system.

Two surfaces:

  Self (any authenticated user):
    GET  /me/features                  -> { features: [...], catalog: [...] }

  Admin (only ADMIN_EMAIL):
    GET  /admin/access/users           -> { users: [{email, features, ...}] }
    GET  /admin/access/catalog         -> { catalog: [...], default_ids: [...] }
    PUT  /admin/access/users/{email}   -> body: { features: [...] }
    DELETE /admin/access/users/{email} -> resets to defaults

All Mongo work is run on the threadpool — `access.store` is sync pymongo
and the admin matrix call hits Mongo + reads a file, so we don't want
to park the event loop on the request path.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Body, Depends, HTTPException

from auth import current_user_email
from . import store

log = logging.getLogger("access.api")

router = APIRouter()

# Mirrors the constant in analytics/api.py. Kept local rather than
# imported across modules so a refactor of one doesn't quietly relax
# the other's gate.
ADMIN_EMAIL = "ajaykandakatla@gmail.com"


def _require_admin(email: str) -> None:
    """404 stealth-gate. Keeps the admin endpoints opaque to other
    signed-in users."""
    if (email or "").lower() != ADMIN_EMAIL:
        raise HTTPException(status_code=404, detail="Not Found")


# ---------------------------------------------------------------------------
# Self
# ---------------------------------------------------------------------------
@router.get("/me/features")
async def me_features(email: str = Depends(current_user_email)):
    """Features the *current* user can see. Still served because some
    callers (FeatureRoute on the frontend, future per-feature checks)
    use the raw feature set rather than the menu projection.

    Returns the catalog too so the UI has labels + grouping without a
    second round-trip.
    """
    features = await asyncio.to_thread(store.get_user_features, email)
    return {
        "email":    email,
        "features": sorted(features),
        "catalog":  store.FEATURE_CATALOG,
    }


@router.get("/me/menu")
async def me_menu(email: str = Depends(current_user_email)):
    """Pre-built sectioned menu structure for the NavBar.

    Cleaner than the old "render every possible link and hide the ones
    the user can't reach" approach — the frontend can't accidentally
    surface a 404'ing link because the backend never sends it in the
    first place. ``build_menu`` is the single source of truth for which
    page goes in which section, derived from the FEATURE_CATALOG.

    Empty sections are still returned (as []) so the frontend can rely
    on the schema and just skip rendering whichever sections are empty.
    """
    menu = await asyncio.to_thread(store.build_menu, email)
    return menu


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
@router.get("/admin/access/catalog")
async def admin_access_catalog(email: str = Depends(current_user_email)):
    """Static feature catalog + default ID list. Lets the admin UI
    render the matrix without hardcoding labels client-side."""
    _require_admin(email)
    return {
        "catalog":     store.FEATURE_CATALOG,
        "default_ids": sorted(store.DEFAULT_FEATURES),
        "restricted_ids": sorted(store.RESTRICTED_FEATURES),
    }


@router.get("/admin/access/users")
async def admin_access_users(email: str = Depends(current_user_email)):
    """Full access matrix — one row per user with their effective
    feature set. Used by the /admin/access page on the frontend.

    Each row is enriched with a server-resolved ``display_name`` (via
    users.store.resolve_display_name → DISPLAY_NAME_OVERRIDES_JSON env
    map → cached Google profile → title-cased handle) so the frontend
    doesn't need to hardcode any personal-name overrides in its bundle.
    """
    _require_admin(email)
    users = await asyncio.to_thread(store.list_users)
    # Enrich each row with display_name. Done in the API layer (not the
    # store) because list_users is also used by jobs that don't need
    # the user-facing name and shouldn't pay the lookup cost.
    from users import store as user_store
    for u in users:
        ue = u.get("email") or ""
        # Best-effort: pull the cached profile (no Google call — passing
        # access_token=None ensures we never make a network request here).
        try:
            prof = user_store.get_or_fetch(ue, access_token=None)
        except Exception:
            prof = {}
        u["display_name"] = user_store.resolve_display_name(ue, (prof or {}).get("display_name"))
    return {"users": users}


@router.put("/admin/access/users/{user_email}")
async def admin_access_set(
    user_email: str,
    payload: dict = Body(...),
    email: str = Depends(current_user_email),
):
    """Overwrite the saved feature set for one user.

    Body: ``{"features": ["morning", "sepa", ...]}``

    Owners (HOUSE_OWNER_EMAILS) can still be edited cosmetically here —
    the admin matrix shows their toggles — but their effective set is
    always "everything" at resolution time (see store.get_user_features).
    Saving against an owner row is therefore a no-op visually.
    """
    _require_admin(email)
    features = payload.get("features")
    if not isinstance(features, list):
        raise HTTPException(status_code=400, detail="features must be a list of strings")
    result = await asyncio.to_thread(
        store.set_user_features,
        user_email,
        features,
        updated_by=email,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=503, detail=result.get("reason") or "store unavailable")
    return result


@router.delete("/admin/access/users/{user_email}")
async def admin_access_reset(
    user_email: str,
    email: str = Depends(current_user_email),
):
    """Drop the saved override for one user — they revert to defaults
    on the next /me/features read."""
    _require_admin(email)

    def _drop() -> bool:
        db = store._get_db()
        if db is None:
            return False
        db.user_features.delete_one({"user_email": (user_email or "").lower()})
        return True

    ok = await asyncio.to_thread(_drop)
    if not ok:
        raise HTTPException(status_code=503, detail="store unavailable")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Admin · sign-in allowlist (who can log in at all)
# ---------------------------------------------------------------------------
# Separate surface from the feature matrix above. The matrix grants PAGES to
# people already allowed in; these endpoints control the oauth2-proxy door
# itself (backend/oauth2-emails.txt). After a change, oauth2-proxy must be
# restarted to re-read the file — we surface that command in every response so
# the owner (who runs deploys) knows the change isn't live until they run it.
_OAUTH_RESTART_CMD = "docker compose --profile oauth restart oauth2-proxy"


@router.get("/admin/access/allowlist")
async def admin_allowlist_get(email: str = Depends(current_user_email)):
    """Current sign-in allowlist — one row per approved email, flagged with
    whether it's a protected (owner) address and whether the user already has
    a saved per-user feature override."""
    _require_admin(email)
    emails = await asyncio.to_thread(store.read_allowlist)
    return {
        "emails": emails,
        "restart_cmd": _OAUTH_RESTART_CMD,
        "needs_restart_note": (
            "New / removed emails take effect after oauth2-proxy re-reads the "
            "file — it does not hot-reload."
        ),
    }


@router.post("/admin/access/allowlist")
async def admin_allowlist_add(
    payload: dict = Body(...),
    email: str = Depends(current_user_email),
):
    """Add an email to the sign-in allowlist. Body: ``{"email": "x@y.com"}``."""
    _require_admin(email)
    target = (payload.get("email") or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="email required")
    result = await asyncio.to_thread(store.add_allowlist_email, target, added_by=email)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("reason") or "could not add")
    result["restart_cmd"] = _OAUTH_RESTART_CMD
    # Only a genuine new line needs a restart; a no-op re-add does not.
    result["needs_restart"] = bool(result.get("added"))
    return result


@router.delete("/admin/access/allowlist/{target_email}")
async def admin_allowlist_remove(
    target_email: str,
    email: str = Depends(current_user_email),
):
    """Remove an email from the sign-in allowlist. Owner emails are refused
    (would risk locking the owner out)."""
    _require_admin(email)
    result = await asyncio.to_thread(store.remove_allowlist_email, target_email, removed_by=email)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("reason") or "could not remove")
    result["restart_cmd"] = _OAUTH_RESTART_CMD
    result["needs_restart"] = bool(result.get("removed"))
    return result
