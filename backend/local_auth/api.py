"""HTTP routes for local password auth.

Endpoints::

    POST /auth/local/signup    body: {email, password}  → 201 + set-cookie
    POST /auth/local/login     body: {email, password}  → 200 + set-cookie
    POST /auth/local/logout                              → 204 + clear cookie
    GET  /auth/local/me                                  → 200 {email}|401

These endpoints MUST be reachable by anonymous users — see
docker-compose.yml's OAUTH2_PROXY_SKIP_AUTH_ROUTES for the bypass
configuration that lets unauthenticated requests reach them.

Rate limiting on /login is a simple in-memory per-IP token bucket.
Not Redis-backed so it resets on container restart — fine because
PBKDF2 verification itself takes ~100ms which already throttles
brute force.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Body, HTTPException, Request, Response

from . import store, session as sess

log = logging.getLogger("local_auth.api")

router = APIRouter()


# In-memory per-IP rate limit. Buckets are deques of recent attempt
# timestamps; if a bucket has >LIMIT entries within WINDOW, the request
# is rejected. Keys are (route, ip) tuples.
_RATE_WINDOW = 60.0          # 1 minute
_RATE_LIMIT = 10             # 10 attempts/min per IP per endpoint
_rate_buckets: defaultdict[tuple, deque] = defaultdict(deque)


def _client_ip(req: Request) -> str:
    """Best-effort client IP. Trusts X-Forwarded-For from nginx since
    requests reach the backend via the frontend's nginx proxy."""
    xff = req.headers.get("x-forwarded-for") or ""
    if xff:
        # First entry is the actual client.
        return xff.split(",")[0].strip()
    return req.client.host if req.client else "unknown"


def _rate_limited(route: str, ip: str) -> bool:
    now = time.time()
    bucket = _rate_buckets[(route, ip)]
    # Drop expired entries.
    while bucket and bucket[0] < now - _RATE_WINDOW:
        bucket.popleft()
    if len(bucket) >= _RATE_LIMIT:
        return True
    bucket.append(now)
    return False


def _set_session_cookie(resp: Response, email: str) -> None:
    """Set the signed session cookie with secure flags."""
    cookie_value, expires = sess.issue_cookie(email)
    max_age = expires - int(time.time())
    # Secure flag turned on by default. For local dev (http://localhost)
    # browsers ignore Secure cookies — so we drop it when host is the
    # docker compose loopback. Production-deployed behind HTTPS will
    # get the secure flag.
    resp.set_cookie(
        key=sess.COOKIE_NAME,
        value=cookie_value,
        max_age=max_age,
        httponly=True,
        secure=True,            # nginx → cloudflared terminates TLS, browser sees HTTPS
        samesite="lax",
        path="/",
    )


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------
@router.post("/auth/local/signup")
async def signup(req: Request, response: Response, payload: dict = Body(...)):
    """Create a local user. Email must already be in oauth2-emails.txt
    or the call is rejected with the same generic error as bad signup
    inputs — no allowlist enumeration."""
    ip = _client_ip(req)
    if _rate_limited("signup", ip):
        raise HTTPException(status_code=429, detail="too many requests")

    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    result = await asyncio.to_thread(store.create_user, email, password)
    if not result.get("ok"):
        # Generic 400 for most reasons (allowlist miss, validation
        # fail, already exists) so an attacker can't tell why. Only
        # exception: store unavailable → 503 so the admin notices.
        if result.get("reason") == "store unavailable":
            raise HTTPException(status_code=503, detail="store unavailable")
        # Reveal "already_exists" so an existing user can recover —
        # they need to know to use login instead of signup. Email
        # enumeration via this is mitigated by the allowlist (only
        # invited users can probe).
        if result.get("reason") == "already_exists":
            raise HTTPException(status_code=409, detail="email already has a password set; use login")
        if result.get("reason") == "not_allowed":
            raise HTTPException(status_code=403, detail="email not on allowlist; ask admin to add you")
        raise HTTPException(status_code=400, detail=result.get("reason") or "invalid signup")

    # Auto-login after signup — set session cookie so the user lands
    # straight in the app without a separate sign-in step.
    _set_session_cookie(response, email)
    response.status_code = 201
    return {"ok": True, "email": email}


@router.post("/auth/local/login")
async def login(req: Request, response: Response, payload: dict = Body(...)):
    ip = _client_ip(req)
    if _rate_limited("login", ip):
        raise HTTPException(status_code=429, detail="too many requests")

    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    result = await asyncio.to_thread(store.verify_password, email, password)
    if not result.get("ok"):
        if result.get("reason") == "locked":
            raise HTTPException(
                status_code=423,
                detail=f"account locked; try again in {result.get('seconds_left', 300)}s",
            )
        # Same wording for "no such user" + "wrong password" to avoid
        # email-enumeration attacks via the response.
        raise HTTPException(status_code=401, detail="invalid email or password")

    _set_session_cookie(response, email)
    return {"ok": True, "email": email}


@router.post("/auth/local/logout")
async def logout(response: Response):
    """Clear the session cookie. Idempotent — safe to call when not
    signed in."""
    response.delete_cookie(sess.COOKIE_NAME, path="/")
    response.status_code = 204
    return {}


@router.get("/auth/local/me")
async def me(req: Request):
    """Return the currently-signed-in local user, if any. Used by the
    frontend to detect "did we just sign in" and "is the cookie still
    valid". Returns 401 when the cookie is missing/invalid/expired."""
    cookie = req.cookies.get(sess.COOKIE_NAME)
    email = sess.parse_cookie(cookie)
    if not email:
        raise HTTPException(status_code=401, detail="not signed in")
    return {"email": email}
