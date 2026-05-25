"""Local-auth user storage.

Schema (Mongo ``local_users`` collection)::

    {
      _id:               ObjectId,
      email:             "aby1@yahoo.com",   # canonical: lowercased
      password_salt:     "<32-char hex>",
      password_hash:     "<64-char hex>",     # PBKDF2-SHA256
      iterations:        200000,              # baked in so we can rotate later
      created_at:        epoch,
      last_login_at:     epoch | None,
      failed_attempts:   int,                  # rate-limit counter
      locked_until:      epoch | None,         # in-band lockout window
    }

Hashing is plain ``hashlib.pbkdf2_hmac`` — no third-party dependency.
200k iterations matches what NIST recommended through 2024 and bcrypt's
default work factor; takes ~100ms per verification on a modern Mac which
is plenty slow to make brute-force impractical without slowing real
users.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from typing import Optional

log = logging.getLogger("local_auth.store")

# PBKDF2 parameters. Iterations baked into the user row so we can
# rotate to a higher value later without breaking existing logins.
PBKDF2_ITERATIONS = 200_000
SALT_BYTES = 16

# Lockout policy — after this many consecutive failures, the account is
# locked for LOCKOUT_SECONDS. Counter resets on a successful login.
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 5 * 60                    # 5 minutes

_db = None
_disabled = False


def _get_db():
    global _db, _disabled
    if _disabled:
        return None
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        _db = client[os.getenv("MONGO_DB", "cheetah")]
        # One row per email — unique constraint catches double-signup.
        _db.local_users.create_index([("email", ASCENDING)], unique=True)
        return _db
    except Exception as exc:
        log.warning("local_auth: Mongo unavailable (%s) — disabling persistence", exc)
        _disabled = True
        return None


# ----------------------------------------------------------------------
# Allowlist gate
# ----------------------------------------------------------------------
def email_in_allowlist(email: str) -> bool:
    """The signup flow only accepts emails already in oauth2-emails.txt.
    This prevents random strangers from creating accounts even though
    the signup endpoint is publicly reachable (it has to be — no auth
    yet at sign-up time).

    The file is mounted into the api container at the same relative
    path as the source tree (it's part of the build context)."""
    target = (email or "").lower().strip()
    if not target:
        return False
    try:
        with open("oauth2-emails.txt") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and line.lower() == target:
                    return True
    except FileNotFoundError:
        # Conservative — if we can't read the allowlist, deny all
        # signups rather than silently letting anyone in.
        log.warning("local_auth: oauth2-emails.txt not found; rejecting signup")
        return False
    return False


# ----------------------------------------------------------------------
# Hashing
# ----------------------------------------------------------------------
def _hash_password(password: str, salt: bytes) -> str:
    """PBKDF2-SHA256 → hex string. Per-user salt + iterations."""
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return dk.hex()


def _generate_salt() -> bytes:
    return secrets.token_bytes(SALT_BYTES)


def _now() -> int:
    return int(time.time())


# ----------------------------------------------------------------------
# CRUD
# ----------------------------------------------------------------------
def get_user(email: str) -> Optional[dict]:
    """Read the user row for ``email`` (or None). Lowercased lookup."""
    db = _get_db()
    if db is None:
        return None
    return db.local_users.find_one({"email": (email or "").lower().strip()})


def create_user(email: str, password: str) -> dict:
    """Create a new local user. Returns ``{ok, reason?}``.

    Validation:
      - email must be in oauth2-emails.txt
      - password must be at least 8 chars (basic floor)
      - email must not already have a local_users row

    Note: this does NOT verify the email is real (no email-out flow).
    The oauth2-emails.txt allowlist is the trust boundary — admin has
    already vouched for who can sign up.
    """
    email = (email or "").lower().strip()
    if not email:
        return {"ok": False, "reason": "email required"}
    if not email_in_allowlist(email):
        # Stealth wording — don't reveal whether the email is on the
        # list or not (avoids enumeration). Same error for both cases.
        return {"ok": False, "reason": "not_allowed"}
    if not password or len(password) < 8:
        return {"ok": False, "reason": "password must be at least 8 characters"}
    if len(password) > 256:
        # Cap on password length too — PBKDF2 itself doesn't care, but
        # gigantic inputs are a small DoS vector (CPU on hashing).
        return {"ok": False, "reason": "password too long"}

    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "store unavailable"}

    if db.local_users.find_one({"email": email}):
        return {"ok": False, "reason": "already_exists"}

    salt = _generate_salt()
    doc = {
        "email":           email,
        "password_salt":   salt.hex(),
        "password_hash":   _hash_password(password, salt),
        "iterations":      PBKDF2_ITERATIONS,
        "created_at":      _now(),
        "last_login_at":   None,
        "failed_attempts": 0,
        "locked_until":    None,
    }
    db.local_users.insert_one(doc)
    return {"ok": True, "email": email}


def verify_password(email: str, password: str) -> dict:
    """Check the password against the stored hash. Returns
    ``{ok, reason?, locked_until?}``.

    Side effects:
      - Increments failed_attempts on bad password.
      - Locks the account for LOCKOUT_SECONDS after MAX_FAILED_ATTEMPTS.
      - On success: resets failed_attempts and updates last_login_at.

    All comparisons use ``hmac.compare_digest`` so the API can't be
    used for a timing oracle.
    """
    email = (email or "").lower().strip()
    if not email or not password:
        return {"ok": False, "reason": "invalid_credentials"}

    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "store unavailable"}

    user = db.local_users.find_one({"email": email})
    if not user:
        # Deliberate same error wording as "wrong password" so an
        # attacker can't enumerate which emails have accounts.
        return {"ok": False, "reason": "invalid_credentials"}

    now = _now()
    if user.get("locked_until") and user["locked_until"] > now:
        return {
            "ok": False,
            "reason": "locked",
            "locked_until": user["locked_until"],
            "seconds_left": user["locked_until"] - now,
        }

    salt = bytes.fromhex(user["password_salt"])
    iterations = int(user.get("iterations") or PBKDF2_ITERATIONS)
    # Recompute with the iterations stored on the row in case we ever
    # rotate the global default — old users keep working until they
    # re-set their password.
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()

    if not hmac.compare_digest(derived, user["password_hash"]):
        attempts = int(user.get("failed_attempts") or 0) + 1
        update: dict = {"failed_attempts": attempts}
        if attempts >= MAX_FAILED_ATTEMPTS:
            update["locked_until"] = now + LOCKOUT_SECONDS
            update["failed_attempts"] = 0       # counter resets at lockout
        db.local_users.update_one({"_id": user["_id"]}, {"$set": update})
        return {"ok": False, "reason": "invalid_credentials"}

    # Success — reset counters, stamp last login.
    db.local_users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "failed_attempts": 0,
            "locked_until":    None,
            "last_login_at":   now,
        }},
    )
    return {"ok": True, "email": email}


def set_password(email: str, new_password: str) -> dict:
    """Reset the password for an existing local user. Useful for the
    admin to wipe a forgotten password (no email-recovery flow yet)."""
    email = (email or "").lower().strip()
    if not new_password or len(new_password) < 8:
        return {"ok": False, "reason": "password too short"}
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "store unavailable"}
    user = db.local_users.find_one({"email": email})
    if not user:
        return {"ok": False, "reason": "not_found"}
    salt = _generate_salt()
    db.local_users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "password_salt":   salt.hex(),
            "password_hash":   _hash_password(new_password, salt),
            "iterations":      PBKDF2_ITERATIONS,
            "failed_attempts": 0,
            "locked_until":    None,
        }},
    )
    return {"ok": True}
