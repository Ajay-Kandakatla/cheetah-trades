"""Authentication helpers for multi-user mode.

oauth2-proxy sits in front of nginx and authenticates requests via Google
OAuth. After a successful auth check, the authenticated user's email is
injected into the request as the ``X-User-Email`` header. Backend routes
that should be user-scoped take a ``current_user_email`` dependency.

If the header is absent (e.g. local dev hitting localhost:8000 directly,
or the cron container running maintenance jobs), we fall back to the
``DEFAULT_USER_EMAIL`` env var. This keeps the cron-driven background jobs
working without auth, and existing data continues to be reachable via that
default identity.
"""
from __future__ import annotations

import os
from fastapi import Header, HTTPException, Request
from typing import Optional


def _default_user() -> str:
    """The fallback user when no X-User-Email header is set. Used by:
      - local dev hitting the API directly
      - cron-driven background jobs (no HTTP request, no headers)
      - existing pre-multiuser data (we backfill its user_email to this)
    """
    return os.getenv("DEFAULT_USER_EMAIL", "ajay@example.com")


async def current_user_email(
    request: Request = None,                     # injected by FastAPI when present
    x_user_email: Optional[str] = Header(None, alias="X-User-Email"),
) -> str:
    """FastAPI dependency — returns the authenticated user's email.

    Order of resolution:
      1. X-User-Email header — set by nginx after oauth2-proxy completes
         a Google session.
      2. ``pounce_local_session`` cookie — set by local password auth.
      3. DEFAULT_USER_EMAIL env — ONLY used when there is no Request
         object (i.e. the caller is a cron script importing functions
         directly, not an HTTP handler). HTTP requests without auth
         get 401 — they SHOULD have been blocked by
         require_auth_middleware in main.py, but this is the second
         line of defense in case someone wires a new endpoint that
         bypasses the middleware.

    The HTTP-context strict behavior was added 2026-05-18 after a
    DEFAULT_USER_EMAIL=ajaykandakatla@gmail.com env value in the
    container was silently treating every anonymous request as the
    admin user.
    """
    email = (x_user_email or "").strip().lower()

    # Path 2: local-auth session cookie. Only checked when the header is
    # absent, so existing Google-authed requests skip the cookie parse.
    if not email and request is not None:
        try:
            from local_auth import session as _sess
            raw = request.cookies.get(_sess.COOKIE_NAME)
            local_email = _sess.parse_cookie(raw)
            if local_email:
                email = local_email
        except Exception:
            # Defensive — if the local_auth module isn't importable for
            # any reason, don't 500 the request. Fall through and the
            # 401 below will fire.
            pass

    if email:
        return email

    # No auth signal at all. Behavior splits by context:
    #
    #   - HTTP context (request is not None): we're inside a real
    #     web request that somehow reached here without auth. The
    #     middleware in main.py should've blocked it; if we got
    #     here it's a programming bug elsewhere — raise 401 loudly.
    #
    #   - Script context (request is None): the caller is a cron
    #     job or test harness importing this function directly with
    #     no HTTP plumbing. Fall back to DEFAULT_USER_EMAIL so the
    #     nightly background jobs keep working.
    if request is not None:
        raise HTTPException(401, "not authenticated")
    return _default_user()


async def maybe_current_user(
    request: Request = None,
    x_user_email: Optional[str] = Header(None, alias="X-User-Email"),
) -> Optional[str]:
    """Like ``current_user_email`` but never raises — returns None if no
    user can be resolved. For endpoints that have BOTH user-scoped and
    public modes (e.g. /sepa/scan returns same data for everyone).

    HTTP context: returns None when unauthenticated. The caller decides
    whether to gate on that (most just personalize when present).
    Script context (no Request): returns DEFAULT_USER_EMAIL for cron jobs.
    """
    email = (x_user_email or "").strip().lower()
    if not email and request is not None:
        try:
            from local_auth import session as _sess
            raw = request.cookies.get(_sess.COOKIE_NAME)
            local_email = _sess.parse_cookie(raw)
            if local_email:
                email = local_email
        except Exception:
            pass
    if email:
        return email
    # See current_user_email for the rationale of this split.
    return None if request is not None else _default_user()


# Owner-only modules (e.g. /house — Ajay's personal real-estate dashboard)
# get a tighter dep that 403s anyone else even if they're in the broader
# email allowlist.
#
# HOUSE_OWNER_EMAILS env is a comma-separated list (or single email). ORDER
# MATTERS — the FIRST email is the canonical partition key for shared data
# in Mongo, so co-owners all read/write the same config. Don't reorder
# this list once data exists or you'll orphan existing rows.
def _parse_owner_emails() -> list[str]:
    raw = os.getenv("HOUSE_OWNER_EMAILS")
    if not raw:
        raw = os.getenv("HOUSE_OWNER_EMAIL", "ajaykandakatla@gmail.com")
    seen: set[str] = set()
    out: list[str] = []
    for e in raw.split(","):
        e = e.strip().lower()
        if e and e not in seen:
            seen.add(e)
            out.append(e)
    return out


HOUSE_OWNER_EMAILS: list[str] = _parse_owner_emails()
# Primary owner — first email wins. All shared-house data lives under this key.
HOUSE_OWNER_EMAIL: str = HOUSE_OWNER_EMAILS[0] if HOUSE_OWNER_EMAILS else "ajaykandakatla@gmail.com"


def is_admin_email(email: Optional[str]) -> bool:
    """Single source of truth for "is this user an admin?"

    Replaces the frontend's hardcoded ``ADMIN_EMAIL = 'ajaykandakatla@gmail.com'``
    constants that previously appeared in 6 different .tsx files (and
    leaked the personal email into the JS bundle). The /auth/me endpoint
    now returns ``is_admin`` based on this function so the frontend
    just reads the flag instead of comparing strings.

    Admin = anyone in HOUSE_OWNER_EMAILS. Co-owners are admins too —
    intentional: a household sale or budget should be jointly managed
    rather than gated to one user.
    """
    if not email:
        return False
    return email.strip().lower() in {e.lower() for e in HOUSE_OWNER_EMAILS}


async def require_house_owner(
    x_user_email: Optional[str] = Header(None, alias="X-User-Email"),
) -> str:
    """403s the request unless the caller is one of the configured house owners.

    /house is a SHARED dashboard between co-owners (e.g. spouses
    co-selling). Returns the *primary* owner email regardless of which
    co-owner is signed in, so all data ends up under one shared partition
    key in Mongo — both users see/edit the same config, snapshots, comps
    and events.
    """
    email = (x_user_email or "").strip().lower() or _default_user()
    if email not in HOUSE_OWNER_EMAILS:
        # Stealth gate — present as 404 so non-owners don't even discover
        # the /house module exists. The real reason is owner-only.
        raise HTTPException(404, "Not Found")
    return HOUSE_OWNER_EMAIL   # primary — shared partition for all co-owners


# Household-shared modules (e.g. /food meal planner) reuse the same
# co-owner list as /house. Both spouses see the same shared menu history,
# preferences, and grocery list. Different from current_user_email which
# is "any authenticated user gets their own scoped data".
async def require_household_member(
    x_user_email: Optional[str] = Header(None, alias="X-User-Email"),
) -> str:
    """Allow either:

      1. A configured household member (HOUSE_OWNER_EMAILS), OR
      2. A friend who's been granted explicit access to /food or /kids
         via the admin panel (see backend/access).

    Returns the *primary* owner email so household data stays under
    one shared Mongo partition. v1 limitation: friends granted access
    see the owners' shared content — per-user data scoping for friends
    is a follow-up. This keeps the gate simple while letting the admin
    open up the household pages to guests.

    Stealth-gated as 404 — non-household, non-granted users don't even
    learn the module exists.
    """
    email = (x_user_email or "").strip().lower() or _default_user()
    if email in HOUSE_OWNER_EMAILS:
        return HOUSE_OWNER_EMAIL
    # Check the per-user feature access list. Inline import keeps
    # access -> auth from importing auth at module load (which would
    # create a circular dep on FastAPI startup).
    try:
        from access.store import user_has_feature
    except Exception:
        # access module unavailable — fall back to owner-only behavior
        raise HTTPException(404, "Not Found")
    # Allow if the user has been granted either /food or /kids — both
    # routes pass through this same gate today. If granular per-feature
    # gating becomes needed, swap to require_feature(feature_id) where
    # the route declares which feature it's protecting.
    if user_has_feature(email, "food") or user_has_feature(email, "kids") or user_has_feature(email, "house"):
        return HOUSE_OWNER_EMAIL
    raise HTTPException(404, "Not Found")
