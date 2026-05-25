"""Signed session cookies for the local-auth path.

Cookie format::

    <email>.<expires_epoch>.<hmac_sha256_hex>

The HMAC is computed over ``email|expires`` using a server-side secret
derived from OAUTH2_PROXY_COOKIE_SECRET (already required by
oauth2-proxy, so we don't introduce a new env var). The shared secret
means cookies survive container restarts as long as the secret stays
constant — and ``oauth2-proxy`` already documents that rotating the
secret invalidates all sessions, so users understand that contract.

Verification rejects:
  - malformed cookies
  - cookies past their expiry
  - cookies whose HMAC doesn't match the secret

All comparisons use ``hmac.compare_digest`` for timing-safe equality.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import time
from typing import Optional

log = logging.getLogger("local_auth.session")

COOKIE_NAME = "pounce_local_session"
# 30 days — matches OAUTH2_PROXY_COOKIE_EXPIRE=720h so the two auth
# paths feel equivalent. User has to sign in once a month either way.
SESSION_TTL_SEC = 30 * 24 * 60 * 60


def _secret() -> bytes:
    """Server-side HMAC key. Derived from OAUTH2_PROXY_COOKIE_SECRET
    (already required in production) so we don't add another env var
    the user has to remember. We hash it once with a constant tag to
    domain-separate from oauth2-proxy's own cookie usage — same input,
    distinct keying material.

    Falls back to a dev-only string when running outside the docker
    stack so unit tests / local dev don't have to set the env.
    """
    raw = os.getenv("OAUTH2_PROXY_COOKIE_SECRET") or "dev-only-not-for-prod-do-not-deploy"
    # Domain separation — local_auth cookies use a derived key, not the
    # same one oauth2-proxy uses for its own cookie.
    return hashlib.sha256(b"pounce.local_auth.session." + raw.encode("utf-8")).digest()


def _sign(payload: str) -> str:
    sig = hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")


def issue_cookie(email: str, *, ttl_sec: int = SESSION_TTL_SEC) -> tuple[str, int]:
    """Return ``(cookie_value, expires_epoch)`` for the given email.
    Caller sets the cookie on the response with HttpOnly + Secure +
    SameSite=Lax."""
    expires = int(time.time()) + ttl_sec
    payload = f"{email.lower().strip()}|{expires}"
    sig = _sign(payload)
    return f"{email.lower().strip()}.{expires}.{sig}", expires


def parse_cookie(raw: Optional[str]) -> Optional[str]:
    """Validate a cookie value and return the email it encodes (or
    ``None`` if invalid/expired). Logs nothing on failure — a bad
    cookie is the normal "not signed in" path."""
    if not raw:
        return None
    try:
        email, expires_str, sig = raw.rsplit(".", 2)
    except ValueError:
        return None
    try:
        expires = int(expires_str)
    except ValueError:
        return None
    if expires < int(time.time()):
        return None
    expected = _sign(f"{email}|{expires}")
    if not hmac.compare_digest(expected, sig):
        return None
    return email.lower().strip()
