"""Push delivery — calls pywebpush for each subscription."""
from __future__ import annotations

import json
import logging
from typing import Optional

from push import keys, subs
from push import receipts

log = logging.getLogger("push.sender")

CONTACT_EMAIL = "mailto:cheetah@example.com"  # required by VAPID — placeholder fine for personal use


_vapid_obj_cache = None


# Keys a composer adds for the LOG only (2026-09-29, Ajay: "I am unable to see
# the other that are hiddedn her … show them all"). `items` lists EVERY entry a
# consolidated push is about; push_history stores it for /alerts, but a device
# never receives it: 44 items x ~100 B would break the ~4 KB Web Push ceiling
# and pywebpush would fail the whole notification.
LOG_ONLY_KEYS = frozenset({"items"})   # logged to push_history, never sent to a device


def device_payload(payload: dict) -> dict:
    """The dict a DEVICE receives: `payload` minus LOG_ONLY_KEYS. A NEW dict when a
    key is stripped (the caller's dict, which history records, is never mutated);
    the same object when there is nothing to strip."""
    if not isinstance(payload, dict) or not any(k in payload for k in LOG_ONLY_KEYS):
        return payload
    return {k: v for k, v in payload.items() if k not in LOG_ONLY_KEYS}


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


def _fan_out(targets: list, payload: dict) -> tuple:
    """Send one payload to every target. Returns (result, push_id, targets_for_history).

    The DEVICE dict is a NEW dict every time: the caller's payload minus
    LOG_ONLY_KEYS, plus the ``push_id`` the service worker echoes in its delivery
    receipt (2026-10-21, Ajay: "Oh man I did not get an A+ alert for it then
    today" on a row that read sent 3 / failed 0 — see push/receipts.py). The
    caller's dict, which history records, is never mutated. ``targets`` carries
    the endpoint HASH + device word + acceptance per subscription, never an
    endpoint or a key.
    """
    push_id = receipts.new_push_id()
    device = dict(device_payload(payload))
    device["push_id"] = push_id
    oks = [_send_one(sub, device) for sub in targets]
    sent = sum(1 for ok in oks if ok)
    result = {"sent": sent, "failed": len(oks) - sent, "total_targets": len(targets)}
    return result, push_id, receipts.targets_of(targets, oks)


def send_to_all(payload: dict, kind: Optional[str] = None) -> dict:
    """Deliver a push payload to every subscribed device whose prefs allow ``kind``."""
    from market_hours import gate   # lazy: gate → reminder → notify → sender
    reason = gate.should_drop_kind(kind)
    if reason:
        # Ajay 2026-09-07 (Labor Day): "turn of alerts scans" — no device, no
        # push_history row; the row would only be noise on a closed market.
        log.info("push.sender: kind=%s dropped — market closed (%s)", kind, reason)
        return {"sent": 0, "failed": 0, "total_targets": 0, "skipped": reason}
    targets = subs.list_subscriptions(filter_kind=kind)
    result, push_id, target_rows = _fan_out(targets, payload)
    log.info("push.sender: kind=%s sent=%d failed=%d", kind, result["sent"], result["failed"])
    # Persist the full untruncated payload to history so the user can
    # re-read it from /notifications even after the phone has cleared
    # the lock-screen banner (which clips body to ~180 chars).
    # Best-effort — never block delivery on history failure.
    try:
        from push import history
        history.record(payload, user_email=None, result=result,
                       push_id=push_id, targets=target_rows)
    except Exception as exc:
        log.debug("push.sender: history record failed: %s", exc)
    return result


def send_to_user(user_email: str, payload: dict, kind: Optional[str] = None) -> dict:
    """Deliver a push to a SPECIFIC user's devices only. Used for admin-
    only notifications like "a new user signed in"."""
    from market_hours import gate   # lazy: gate → reminder → notify → sender
    reason = gate.should_drop_kind(kind)
    if reason:
        # Ajay 2026-09-07 (Labor Day): "turn of alerts scans" — no device, no
        # push_history row; the row would only be noise on a closed market.
        log.info("push.sender: kind=%s dropped — market closed (%s)", kind, reason)
        return {"sent": 0, "failed": 0, "total_targets": 0, "skipped": reason}
    targets = subs.list_subscriptions(filter_kind=kind, user_email=user_email)
    result, push_id, target_rows = _fan_out(targets, payload)
    log.info("push.sender: user=%s kind=%s sent=%d failed=%d",
             user_email, kind, result["sent"], result["failed"])
    # Same history-record path as send_to_all, but scoped to this user
    # so /push/history shows it under their email instead of as a
    # broadcast row.
    try:
        from push import history
        history.record(payload, user_email=user_email, result=result,
                       push_id=push_id, targets=target_rows)
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
