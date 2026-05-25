"""Push delivery — calls pywebpush for each subscription."""
from __future__ import annotations

import json
import logging
from typing import Optional

from push import keys, subs

log = logging.getLogger("push.sender")

CONTACT_EMAIL = "mailto:cheetah@example.com"  # required by VAPID — placeholder fine for personal use


_vapid_obj_cache = None


def _vapid_obj():
    """Build a Vapid object from the PEM. pywebpush 2.0 changed vapid_private_key
    to expect DER-base64 (not PEM) when passed as a string, so we instantiate
    Vapid ourselves from PEM and pass it via vapid_object=."""
    global _vapid_obj_cache
    if _vapid_obj_cache is not None:
        return _vapid_obj_cache
    vapid = keys.vapid_keys()
    if not vapid:
        return None
    try:
        from py_vapid import Vapid
        v = Vapid.from_pem(vapid["private_pem"].encode())
        _vapid_obj_cache = v
        return v
    except Exception as exc:
        log.error("push.sender: could not build Vapid object: %s", exc)
        return None


def _send_one(subscription: dict, payload: dict) -> bool:
    try:
        from pywebpush import webpush
        v = _vapid_obj()
        if v is None:
            log.warning("push.sender: no VAPID object available")
            return False
        webpush(
            subscription_info={
                "endpoint": subscription["endpoint"],
                "keys": subscription["keys"],
            },
            data=json.dumps(payload),
            # Pass the Vapid instance directly — pywebpush 2.0 accepts a
            # Vapid object via this same parameter (not vapid_object).
            vapid_private_key=v,
            vapid_claims={"sub": CONTACT_EMAIL},
            ttl=3600,
        )
        return True
    except Exception as exc:
        log.warning("push.sender: send failed for %s: %s",
                    subscription.get("endpoint", "?")[:60], exc)
        # If the subscription has expired (410 Gone), drop it.
        if "410" in str(exc) or "expired" in str(exc).lower():
            try:
                subs.remove_subscription(subscription["endpoint"])
            except Exception:
                pass
        return False


def send_to_all(payload: dict, kind: Optional[str] = None) -> dict:
    """Deliver a push payload to every subscribed device whose prefs allow ``kind``."""
    targets = subs.list_subscriptions(filter_kind=kind)
    sent = 0
    failed = 0
    for sub in targets:
        ok = _send_one(sub, payload)
        if ok:
            sent += 1
        else:
            failed += 1
    log.info("push.sender: kind=%s sent=%d failed=%d", kind, sent, failed)
    result = {"sent": sent, "failed": failed, "total_targets": len(targets)}
    # Persist the full untruncated payload to history so the user can
    # re-read it from /notifications even after the phone has cleared
    # the lock-screen banner (which clips body to ~180 chars).
    # Best-effort — never block delivery on history failure.
    try:
        from push import history
        history.record(payload, user_email=None, result=result)
    except Exception as exc:
        log.debug("push.sender: history record failed: %s", exc)
    return result


def send_to_user(user_email: str, payload: dict, kind: Optional[str] = None) -> dict:
    """Deliver a push to a SPECIFIC user's devices only. Used for admin-
    only notifications like "a new user signed in"."""
    targets = subs.list_subscriptions(filter_kind=kind, user_email=user_email)
    sent = 0
    failed = 0
    for sub in targets:
        ok = _send_one(sub, payload)
        if ok:
            sent += 1
        else:
            failed += 1
    log.info("push.sender: user=%s kind=%s sent=%d failed=%d",
             user_email, kind, sent, failed)
    result = {"sent": sent, "failed": failed, "total_targets": len(targets)}
    # Same history-record path as send_to_all, but scoped to this user
    # so /push/history shows it under their email instead of as a
    # broadcast row.
    try:
        from push import history
        history.record(payload, user_email=user_email, result=result)
    except Exception as exc:
        log.debug("push.sender: history record failed: %s", exc)
    return result


def test_send(endpoint: str) -> dict:
    """Send a test notification to one endpoint — used by the Settings page."""
    db = subs._get_db()
    if db is None:
        return {"ok": False}
    sub = db.push_subscriptions.find_one({"endpoint": endpoint})
    if not sub:
        return {"ok": False, "reason": "subscription not found"}
    payload = {
        "title": "Pounce test ✓",
        "body": "Push notifications are working — you'll get alerts when SEPA fires.",
        "tag": "test",
        "url": "/notifications",
    }
    return {"ok": _send_one(sub, payload)}
