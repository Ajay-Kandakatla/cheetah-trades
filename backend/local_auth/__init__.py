"""Local password authentication — alternative to Google OAuth.

Why this exists: oauth2-proxy gates the app behind Google sign-in. Users
without a Google account (Yahoo, Outlook, etc.) couldn't get in. Local
auth lets allowlisted emails set their own password and sign in directly.

Architecture:
  - oauth2-proxy still handles the Google OAuth handshake (unchanged).
  - oauth2-proxy's SKIP_AUTH_ROUTES is set to wildcard so it stops
    redirecting unauthenticated requests to Google. Backend becomes
    the sole auth enforcer.
  - Two auth paths coexist:
      a) Google users: oauth2-proxy completes the dance, sets cookies,
         requests carry X-User-Email header (existing behavior).
      b) Local users: hit /auth/local/login, get a signed session cookie
         (pounce_local_session), requests carry that cookie.
  - auth.current_user_email checks the header FIRST, falls back to the
    cookie. Both paths feed the same per-user data partitions.

Security:
  - Passwords hashed with PBKDF2-SHA256, 200k iterations, per-user salt.
  - Session cookies HMAC-signed with a server-side secret derived from
    OAUTH2_PROXY_COOKIE_SECRET (already required for oauth2-proxy).
  - HttpOnly + Secure + SameSite=Lax (cookie won't leak to JS, won't
    transmit over HTTP).
  - 30-day session expiry, matched to oauth2-proxy's 720h policy.
  - Per-IP rate limit on /auth/local/login to slow brute force.
  - Signup gated by oauth2-emails.txt allowlist — random strangers
    can't create accounts.
"""
from .api import router  # noqa: F401
