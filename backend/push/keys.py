"""VAPID keypair management — auto-generated on first run, persisted in Mongo."""
from __future__ import annotations

import base64
import logging
import os
from typing import Optional

log = logging.getLogger("push.keys")

_db = None


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient
        client = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"),
                              serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        _db = client[os.getenv("MONGO_DB", "cheetah")]
        return _db
    except Exception as exc:
        log.warning("push.keys: Mongo unavailable: %s", exc)
        return None


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _generate_keypair() -> dict:
    """Generate a fresh VAPID P-256 keypair, return base64url-encoded strings."""
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization

    priv = ec.generate_private_key(ec.SECP256R1())
    priv_bytes = priv.private_numbers().private_value.to_bytes(32, "big")
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    # PEM private key for pywebpush
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return {
        "private_b64": _b64url(priv_bytes),
        "public_b64": _b64url(pub_bytes),
        "private_pem": priv_pem,
    }


def vapid_keys() -> Optional[dict]:
    """Return the persisted VAPID keypair, generating it once if absent."""
    db = _get_db()
    if db is None:
        return None
    existing = db.app_config.find_one({"_id": "vapid"})
    if existing and existing.get("public_b64"):
        return existing
    new_keys = _generate_keypair()
    new_keys["_id"] = "vapid"
    db.app_config.update_one({"_id": "vapid"}, {"$set": new_keys}, upsert=True)
    log.info("push.keys: generated new VAPID keypair")
    return new_keys


def public_key() -> Optional[str]:
    """Public key as base64url-encoded string — frontend uses this in subscribe()."""
    keys = vapid_keys()
    return keys.get("public_b64") if keys else None
