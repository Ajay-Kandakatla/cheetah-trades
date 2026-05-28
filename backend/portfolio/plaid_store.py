"""Mongo persistence for Plaid-linked portfolio data.

Three collections — each scoped to ``owner_email`` so multiple users
can link their own broker accounts without cross-contamination:

1. ``plaid_items``
   One doc per linked institution. Holds the encrypted access_token,
   the Plaid item_id, and a human-readable institution name. There's
   only one item per owner in v1 (most people link one broker — the
   typical case for the project owner is Fidelity).

2. ``portfolio_holdings_cache``
   Latest serialized response from /investments/holdings/get. The
   /portfolio/holdings route reads this first and only refetches from
   Plaid if older than 1h (or if the caller passes ?refresh=true). Cron
   refreshes this hourly during US market hours so the heatmap is
   already warm when the user opens the page.

3. ``portfolio_position_meta``
   User-typed entry / stop / target / notes per symbol — the bits Plaid
   doesn't know about. Needed for R-multiple math (`R = (price-entry) /
   (entry-stop)`). Unique key is (owner_email, symbol).

Access token encryption
-----------------------
The Plaid access token is read/write material for the user's broker
position data. We store it encrypted with Fernet (symmetric AES-128
in CBC + HMAC-SHA256). Key comes from ``PLAID_TOKEN_ENC_KEY``. If the
env var isn't set we log a warning and store the token plaintext —
acceptable during dev so the setup flow works, but operations must
generate a key for production:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

…and add the output to backend/.env as PLAID_TOKEN_ENC_KEY.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("portfolio.plaid_store")

# Shared Mongo handle — lazy, mirrors the pattern used by store.py.
_db = None
_disabled = False


def _get_db():
    """Cached Mongo handle. Returns None when Mongo isn't reachable so the
    rest of the app keeps functioning (status endpoint reports
    ``has_linked_account: False`` instead of 500ing)."""
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
        # owner_email uniquely identifies the linked item — only one
        # broker per owner in v1.
        _db.plaid_items.create_index(
            [("owner_email", ASCENDING)], unique=True
        )
        _db.portfolio_holdings_cache.create_index(
            [("owner_email", ASCENDING)], unique=True
        )
        _db.portfolio_position_meta.create_index(
            [("owner_email", ASCENDING), ("symbol", ASCENDING)], unique=True
        )
        return _db
    except Exception as exc:
        log.warning("portfolio.plaid_store: Mongo unavailable (%s) — disabling", exc)
        _disabled = True
        return None


def _now() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


# --------------------------------------------------------------------------
# Token encryption
# --------------------------------------------------------------------------
def _fernet():
    """Build a Fernet handle from PLAID_TOKEN_ENC_KEY. Returns None when
    the env var is unset — caller falls back to plaintext storage with
    a warning. Cached on the module so we don't re-derive the key on
    every save/load."""
    key = os.getenv("PLAID_TOKEN_ENC_KEY", "").strip()
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(key.encode())
    except Exception as exc:
        log.warning("portfolio.plaid_store: invalid PLAID_TOKEN_ENC_KEY (%s) — falling back to plaintext", exc)
        return None


def _encrypt(token: str) -> str:
    """Encrypt the Plaid access token. Prefixes the ciphertext with
    ``enc:`` so a future read can tell whether the stored value was
    written under encryption or not (lets us rotate the key without
    breaking previously-saved unencrypted tokens)."""
    f = _fernet()
    if f is None:
        log.warning("portfolio.plaid_store: PLAID_TOKEN_ENC_KEY not set — storing access_token UNENCRYPTED (dev only)")
        return token
    return "enc:" + f.encrypt(token.encode()).decode()


def _decrypt(stored: str) -> str:
    """Reverse of _encrypt. Tokens written before encryption was wired
    up are returned as-is so the user doesn't have to re-link."""
    if not stored:
        return ""
    if not stored.startswith("enc:"):
        return stored
    f = _fernet()
    if f is None:
        log.warning("portfolio.plaid_store: encrypted token in store but PLAID_TOKEN_ENC_KEY unset")
        return ""
    try:
        return f.decrypt(stored[4:].encode()).decode()
    except Exception as exc:
        log.error("portfolio.plaid_store: decrypt failed (%s) — key rotated?", exc)
        return ""


# --------------------------------------------------------------------------
# plaid_items — one doc per linked institution per owner
# --------------------------------------------------------------------------
def save_item(owner_email: str, access_token: str, item_id: str,
              institution_name: str) -> dict:
    """Upsert the linked broker for ``owner_email``. Encrypts the access
    token at rest. Returns ``{ok, institution_name}`` so the caller can
    confirm the link without re-reading from Mongo."""
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db unavailable"}

    owner_email = owner_email.lower().strip()
    db.plaid_items.update_one(
        {"owner_email": owner_email},
        {
            "$set": {
                "owner_email":      owner_email,
                "access_token":     _encrypt(access_token),
                "item_id":          item_id,
                "institution_name": institution_name or "",
                "last_sync":        None,
                "updated_at":       _now(),
            },
            "$setOnInsert": {"linked_at": _now()},
        },
        upsert=True,
    )
    return {"ok": True, "institution_name": institution_name}


def get_item(owner_email: str) -> Optional[dict]:
    """Return ``{access_token, item_id, institution_name, linked_at,
    last_sync}`` for the owner's linked broker, or None if none exists.

    The returned ``access_token`` is plaintext — decryption happens
    inline. Caller should NEVER serialize this back to a client; only
    the backend uses it to call Plaid.
    """
    db = _get_db()
    if db is None:
        return None
    doc = db.plaid_items.find_one({"owner_email": owner_email.lower().strip()})
    if not doc:
        return None
    return {
        "access_token":     _decrypt(doc.get("access_token", "")),
        "item_id":          doc.get("item_id", ""),
        "institution_name": doc.get("institution_name", ""),
        "linked_at":        doc.get("linked_at"),
        "last_sync":        doc.get("last_sync"),
    }


def mark_synced(owner_email: str) -> None:
    """Stamp ``last_sync`` on the item doc — bumped each time we
    successfully refresh holdings. The UI shows "synced 12 min ago"
    based on this."""
    db = _get_db()
    if db is None:
        return
    db.plaid_items.update_one(
        {"owner_email": owner_email.lower().strip()},
        {"$set": {"last_sync": _now()}},
    )


def delete_item(owner_email: str) -> dict:
    """Unlink the user's broker — wipes the item doc + the cached
    holdings. Local-only; does NOT call Plaid's /item/remove. Use
    ``disconnect`` for the end-to-end flow."""
    db = _get_db()
    if db is None:
        return {"ok": False}
    owner_email = owner_email.lower().strip()
    db.plaid_items.delete_many({"owner_email": owner_email})
    db.portfolio_holdings_cache.delete_many({"owner_email": owner_email})
    return {"ok": True}


def disconnect(email: str) -> dict:
    """End-to-end unlink: revoke the access_token at Plaid, then wipe the
    local doc + holdings cache.

    Why both halves: just deleting our row leaks the slot on Plaid's side
    (the free trial caps linked Items at 10 and every orphan eats one).
    Just calling Plaid leaves a stale row that the /portfolio/status
    endpoint still treats as "linked". Do both, in that order — if Plaid
    refuses (network blip, key rotation), we keep the local row so the
    user can retry rather than ending up half-detached.

    Returns ``{"removed": True}`` on success, ``{"removed": False,
    "error": "..."}`` if there's nothing to disconnect or Plaid refused.
    """
    db = _get_db()
    if db is None:
        return {"removed": False, "error": "db unavailable"}

    item = get_item(email)
    if not item:
        return {"removed": False, "error": "no linked account"}
    access_token = item.get("access_token") or ""
    if not access_token:
        # Doc exists but token didn't decrypt — likely a key rotation
        # mishap. Drop the doc anyway so the user isn't stuck with a
        # phantom link they can't replace.
        delete_item(email)
        return {"removed": True, "error": "token undecryptable; local row dropped"}

    from portfolio import plaid_client
    try:
        ok = plaid_client.remove_item(access_token)
    except plaid_client.PlaidNotConfigured as exc:
        return {"removed": False, "error": str(exc)}
    except Exception as exc:
        log.exception("portfolio.plaid_store: disconnect failed for %s", email)
        return {"removed": False, "error": str(exc)}

    if not ok:
        return {"removed": False, "error": "plaid /item/remove refused"}

    delete_item(email)
    return {"removed": True}


# --------------------------------------------------------------------------
# portfolio_holdings_cache — last Plaid /holdings/get response
# --------------------------------------------------------------------------
def cache_holdings(owner_email: str, holdings_response: dict) -> None:
    """Persist a fresh Plaid response. Replaces (does not merge) the
    previous snapshot — Plaid's holdings endpoint is point-in-time so
    we always overwrite."""
    db = _get_db()
    if db is None:
        return
    db.portfolio_holdings_cache.update_one(
        {"owner_email": owner_email.lower().strip()},
        {"$set": {
            "owner_email": owner_email.lower().strip(),
            "accounts":    holdings_response.get("accounts") or [],
            "holdings":    holdings_response.get("holdings") or [],
            "securities":  holdings_response.get("securities") or [],
            "cached_at":   _now(),
        }},
        upsert=True,
    )


def get_cached_holdings(owner_email: str, max_age_sec: int = 3600) -> Optional[dict]:
    """Return the cached response if it's still fresh, else None.

    ``max_age_sec`` defaults to 1h — Plaid recommends a similar cadence
    for the Investments product and cron refreshes hourly during market
    hours anyway. Pass ``max_age_sec=0`` to bypass the freshness check
    and always return the stored doc (useful for "show whatever we
    have" reads when Plaid is degraded).
    """
    db = _get_db()
    if db is None:
        return None
    doc = db.portfolio_holdings_cache.find_one({"owner_email": owner_email.lower().strip()})
    if not doc:
        return None
    cached_at = doc.get("cached_at", 0)
    if max_age_sec > 0 and (_now() - cached_at) > max_age_sec:
        return None
    return {
        "accounts":   doc.get("accounts") or [],
        "holdings":   doc.get("holdings") or [],
        "securities": doc.get("securities") or [],
        "cached_at":  cached_at,
    }


# --------------------------------------------------------------------------
# portfolio_position_meta — user-typed entry / stop / target / notes
# --------------------------------------------------------------------------
def set_position_meta(owner_email: str, symbol: str, *,
                       entry: Optional[float] = None,
                       stop: Optional[float] = None,
                       target: Optional[float] = None,
                       notes: Optional[str] = None) -> dict:
    """Upsert the user-typed risk levels for one symbol. Any field left
    as None is preserved from the existing doc (partial updates work)."""
    db = _get_db()
    if db is None:
        return {"ok": False}
    symbol = symbol.upper().strip()
    if not symbol:
        return {"ok": False, "reason": "symbol required"}

    update: dict = {"updated_at": _now()}
    if entry is not None:
        update["entry"] = float(entry)
    if stop is not None:
        update["stop"] = float(stop)
    if target is not None:
        update["target"] = float(target)
    if notes is not None:
        update["notes"] = str(notes)

    db.portfolio_position_meta.update_one(
        {"owner_email": owner_email.lower().strip(), "symbol": symbol},
        {
            "$set": {
                "owner_email": owner_email.lower().strip(),
                "symbol":      symbol,
                **update,
            },
        },
        upsert=True,
    )
    return {"ok": True, "symbol": symbol}


def get_position_meta(owner_email: str) -> list[dict]:
    """List of every meta the user has typed in. Used by the heatmap +
    R-multiple table to overlay entry/stop/target onto Plaid positions."""
    db = _get_db()
    if db is None:
        return []
    rows = list(db.portfolio_position_meta.find(
        {"owner_email": owner_email.lower().strip()}, {"_id": 0}
    ))
    rows.sort(key=lambda r: r.get("symbol") or "")
    return rows


# --------------------------------------------------------------------------
# Cron-friendly bulk refresh
# --------------------------------------------------------------------------
def refresh_all_holdings() -> int:
    """Loop every linked broker and refresh its holdings cache from Plaid.

    Cron entry point — see backend/crontab. Returns the number of
    accounts successfully refreshed. Errors per-item are logged and
    skipped (a degraded Plaid response for one user shouldn't block
    the whole sweep).
    """
    db = _get_db()
    if db is None:
        return 0

    # Local imports to avoid pulling plaid_client at module-load time
    # (so unit tests can stub it without installing the SDK).
    from portfolio import plaid_client

    refreshed = 0
    for doc in db.plaid_items.find({}):
        owner = (doc.get("owner_email") or "").lower().strip()
        if not owner:
            continue
        access_token = _decrypt(doc.get("access_token", ""))
        if not access_token:
            continue
        try:
            resp = plaid_client.get_holdings(access_token)
        except plaid_client.PlaidNotConfigured:
            log.info("portfolio.plaid_store: Plaid not configured — skipping refresh sweep")
            return refreshed
        except Exception as exc:
            log.warning("portfolio.plaid_store: refresh failed for %s: %s", owner, exc)
            continue
        cache_holdings(owner, resp)
        mark_synced(owner)
        refreshed += 1
    return refreshed
