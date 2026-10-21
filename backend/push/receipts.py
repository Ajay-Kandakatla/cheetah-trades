"""Delivery receipts — did the device actually SHOW the push? (2026-10-21)

Ajay 2026-10-21, on the 15:36:15 ET 🚩 gajjala_setup push for NIXX: "Oh man I
did not get an A+ alert for it then today" — and, asked about the two 🧠
potentials around it: "Yes POLA reached and SAIQ too". push_history said
``sent 3 / failed 0`` for all three: every push service (two fcm.googleapis.com
subscriptions, one web.push.apple.com) accepted the message, and nothing
server-side could tell a notification the phone showed from one it dropped.
``sent`` is the push SERVICE's acceptance, never the device's screen.

The receipt closes that gap:
  1. push.sender stamps a ``push_id`` into every device payload and into the
     push_history row, with the ``targets`` it tried (endpoint HASHES only).
  2. frontend/public/sw.js, after ``showNotification`` resolves, POSTs
     ``{push_id, endpoint, shown_at}`` to ``POST /push/receipt`` — its own
     subscription endpoint, which only that device and this server know.
  3. This module validates the endpoint against push_subscriptions, scopes the
     row to that subscription's owner, and appends ONE receipt per device
     (idempotent) to the history row. ``sent`` / ``failed`` / ``total`` are
     never touched — a receipt is a second fact beside them, not a correction.
  4. push.recent serves ``shown_on`` ("shown on 2 of 3 devices (Mac Chrome ×2);
     no receipt from iPhone") and /alerts prints it verbatim.

Never stored, never served, never logged: an endpoint or a key. A receipt keeps
``sha1(endpoint)`` and the device WORD derived from the subscription's label
("iPhone", "Mac Chrome") — nothing that identifies the push-service URL.

The route is on main.py's public allowlist on purpose: a service worker runs
when the page is closed and its session cookie may be gone, and the receipt
must land exactly then. Its credential is the subscription endpoint — an
unguessable per-device URL that only a registered device can echo. An unknown
endpoint, an unknown push_id, or a row that belongs to another user all answer
the same 404; nothing about any row leaks to a stranger.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import uuid
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

log = logging.getLogger("push.receipts")

router = APIRouter(tags=["push"])

RECEIPT_PATH = "/push/receipt"       # main.py lists it in _PUBLIC_API_PATHS (see the docstring)
PUSH_ID_MAX = 64
ENDPOINT_MAX = 2048
MS_THRESHOLD = 10 ** 11              # a stamp above this is milliseconds (Date.now()), else seconds


def new_push_id() -> str:
    """The id the sender stamps on one send (one per send_to_all / send_to_user call)."""
    return uuid.uuid4().hex


def endpoint_hash(endpoint: Optional[str]) -> str:
    """sha1 of the subscription endpoint — the only form of it that is ever stored."""
    return hashlib.sha1((endpoint or "").encode("utf-8")).hexdigest()


# ── the device word ──────────────────────────────────────────────────────────
# push_subscriptions.label is "Pounce · <user agent[:100]>" (lib/pushSubscribe.ts),
# so the word is read off the UA. The OS is checked iPhone-first: an iPhone UA
# says "like Mac OS X". Edge before Chrome: an Edge UA carries "Chrome/" too.
_OS_WORDS = (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"),
             ("Macintosh", "Mac"), ("Mac OS", "Mac"), ("Windows", "Windows"), ("Linux", "Linux"))
_BROWSER_WORDS = (("Edg/", "Edge"), ("Firefox/", "Firefox"), ("FxiOS", "Firefox"),
                  ("Chrome/", "Chrome"), ("CriOS", "Chrome"), ("Safari/", "Safari"))
LABEL_WORD_MAX = 24
DEFAULT_DEVICE_WORD = "device"


def device_word(label: Optional[str]) -> str:
    """"Mac Chrome", "iPhone", "Android Chrome" … from a subscription label.
    A label with no UA marker is itself, trimmed; an empty one is "device"."""
    s = (label or "").strip()
    os_word = next((w for mark, w in _OS_WORDS if mark in s), "")
    br_word = next((w for mark, w in _BROWSER_WORDS if mark in s), "")
    words = " ".join(w for w in (os_word, br_word) if w)
    if words:
        return words
    if s.startswith("Pounce ·") or not s:
        return DEFAULT_DEVICE_WORD
    return s[:LABEL_WORD_MAX]


def targets_of(subs: list, oks: list) -> list:
    """The ``targets`` list the history row stores: one entry per subscription the
    sender tried — endpoint HASH, the device word, and whether the push service
    accepted it. Nothing else from the subscription."""
    out = []
    for sub, ok in zip(subs, oks):
        out.append({"sub": endpoint_hash((sub or {}).get("endpoint")),
                    "device": device_word((sub or {}).get("label")),
                    "ok": bool(ok)})
    return out


# ── the receipt ──────────────────────────────────────────────────────────────
def _subs_db():
    from push import subs
    return subs._get_db()


def _hist_coll():
    from push import history
    return history._get_coll()


def _shown_at(raw) -> Optional[int]:
    """The SW's stamp (Date.now(), ms) as epoch seconds; None when absent or not a number."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    v = float(raw)
    if v <= 0:
        return None
    if v > MS_THRESHOLD:
        v = v / 1000.0
    return int(v)


def record_receipt(body, *, subs_db=None, hist_coll=None, now: Optional[int] = None) -> tuple:
    """(status, payload) for one POST body. Pure apart from the two injectable stores.

    200 {ok: true, dup: bool} — appended (dup=false) or already there (dup=true);
    400 {ok: false, reason}  — a malformed body;
    404 {ok: false, reason: "unknown"} — endpoint not registered, push_id not in
        history, or the row is another user's (one answer for all three);
    503 — a store is unavailable (the SW retries nothing; the row stays honest).
    """
    if not isinstance(body, dict):
        return 400, {"ok": False, "reason": "body must be an object"}
    push_id = body.get("push_id")
    endpoint = body.get("endpoint")
    if not isinstance(push_id, str) or not push_id or len(push_id) > PUSH_ID_MAX:
        return 400, {"ok": False, "reason": "push_id required"}
    if not isinstance(endpoint, str) or not endpoint.startswith("https://") or len(endpoint) > ENDPOINT_MAX:
        return 400, {"ok": False, "reason": "endpoint required"}

    db = subs_db() if subs_db is not None else _subs_db()
    coll = hist_coll() if hist_coll is not None else _hist_coll()
    if db is None or coll is None:
        return 503, {"ok": False, "reason": "store unavailable"}

    sub = db.push_subscriptions.find_one({"endpoint": endpoint},
                                         {"user_email": 1, "label": 1, "kind": 1})
    if not sub or sub.get("kind") == "mac":
        return 404, {"ok": False, "reason": "unknown"}
    row = coll.find_one({"push_id": push_id}, {"user_email": 1})
    if not row:
        return 404, {"ok": False, "reason": "unknown"}
    owner = row.get("user_email")
    if owner is not None and (owner or "").lower() != (sub.get("user_email") or "").lower():
        return 404, {"ok": False, "reason": "unknown"}

    h = endpoint_hash(endpoint)
    receipt = {"sub": h, "device": device_word(sub.get("label")),
               "shown_at": _shown_at(body.get("shown_at")),
               "at": int(now if now is not None else time.time())}
    # One receipt per device: the filter refuses a row that already holds this
    # hash, so a re-delivered push (or a retried POST) never counts twice.
    res = coll.update_one({"push_id": push_id, "receipts.sub": {"$ne": h}},
                          {"$push": {"receipts": receipt}})
    dup = int(getattr(res, "matched_count", 0) or 0) == 0
    return 200, {"ok": True, "dup": dup}


@router.post(RECEIPT_PATH)
async def push_receipt(payload: dict):
    """The service worker's "I showed it" — see the module docstring. No auth
    dependency: the subscription endpoint in the body is the credential."""
    try:
        status, out = await asyncio.to_thread(record_receipt, payload)
    except Exception as exc:          # never 500 the worker; the row just stays receipt-less
        log.debug("push.receipts: receipt failed: %s", exc)
        status, out = 503, {"ok": False, "reason": "store unavailable"}
    return JSONResponse(out, status_code=status)


# ── what /alerts prints ──────────────────────────────────────────────────────
def _dedupe_words(words: list) -> str:
    """["Mac Chrome", "Mac Chrome", "iPhone"] -> "Mac Chrome ×2, iPhone" (first-seen order)."""
    counts: dict = {}
    for w in words:
        counts[w] = counts.get(w, 0) + 1
    return ", ".join(f"{w} ×{n}" if n > 1 else w for w, n in counts.items())


def shown_on(row: dict) -> Optional[dict]:
    """The served block for one push_history row, or None when the row predates
    receipts (no ``push_id``) or targeted nobody (the delivery line already says
    "not delivered"). ``text`` is the whole sentence; the page prints it verbatim.

    ``shown`` counts receipts; ``total`` is the row's ``total`` (devices targeted,
    the same denominator as the delivery line); ``devices`` are the words of the
    devices that reported; ``missing`` the accepted targets with no receipt yet.
    """
    if not isinstance(row, dict) or not row.get("push_id"):
        return None
    total = int(row.get("total") or 0)
    if total <= 0:
        return None
    receipts = [r for r in (row.get("receipts") or []) if isinstance(r, dict)]
    seen = {r.get("sub") for r in receipts}
    devices = [str(r.get("device") or DEFAULT_DEVICE_WORD) for r in receipts]
    targets = [t for t in (row.get("targets") or []) if isinstance(t, dict)]
    missing = [str(t.get("device") or DEFAULT_DEVICE_WORD)
               for t in targets if t.get("ok") and t.get("sub") not in seen]
    shown = len(receipts)
    text = f"shown on {shown} of {total} device{'' if total == 1 else 's'}"
    if devices:
        text += f" ({_dedupe_words(devices)})"
    if missing:
        text += f"; no receipt from {_dedupe_words(missing)}"
    return {"shown": shown, "total": total, "devices": devices, "missing": missing, "text": text}


__all__ = ["router", "RECEIPT_PATH", "new_push_id", "endpoint_hash", "device_word",
           "targets_of", "record_receipt", "shown_on", "DEFAULT_DEVICE_WORD"]
