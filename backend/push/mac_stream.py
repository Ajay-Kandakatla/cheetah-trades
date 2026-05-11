"""Server-Sent Events channel for the native macOS Pounce.app.

Why this exists
---------------
Web Push on macOS Safari/WKWebView routes through APNs, which requires the
host app to carry the ``com.apple.developer.aps-environment`` entitlement.
That entitlement requires a paid Apple Developer Program account. Since we
don't have one, the native Mac app instead holds an SSE connection open to
``/push/mac-stream`` and fires local UNUserNotificationCenter notifications
when events arrive on the stream.

Architecture
------------
Producer side — ``notify._send_push`` (called from BOTH the api container
(async request handlers) and the cron container (sync supercronic jobs)) —
inserts payloads into the ``mac_outbox`` Mongo collection. We use Mongo as
the message bus because it already exists, both containers share it, and we
don't need to add another dependency or care about which container produced
the alert.

Consumer side — a background asyncio task started in main.py's lifespan
hook polls ``mac_outbox`` every 200ms, fans out matching docs to live SSE
clients (held in this module's in-memory dict), and deletes the processed
docs.

Trade-off: ~100-200ms of latency vs. an in-process call. Acceptable for
trading alerts. Buys us a much simpler, more robust design with no
cross-container IPC, no shared secrets, no service discovery.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Optional

log = logging.getLogger("push.mac_stream")

# In-memory registry of live SSE clients. Keyed by (user_email, device_id);
# each value is a list of asyncio.Queues so the same device with two open
# windows during a reload still gets every event.
_clients: dict[tuple[str, str], list[asyncio.Queue]] = {}
_lock: Optional[asyncio.Lock] = None  # lazy-init on first use (need running loop)


def _get_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


# ---------------------------------------------------------------------------
# Live-client registry
# ---------------------------------------------------------------------------
async def register(user_email: str, device_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    async with _get_lock():
        _clients.setdefault((user_email.lower(), device_id), []).append(q)
    log.info("mac_stream: connect %s/%s (now %d connection(s))",
             user_email, device_id, _count())
    return q


async def unregister(user_email: str, device_id: str, q: asyncio.Queue) -> None:
    async with _get_lock():
        key = (user_email.lower(), device_id)
        lst = _clients.get(key) or []
        if q in lst:
            lst.remove(q)
        if not lst:
            _clients.pop(key, None)
    log.info("mac_stream: disconnect %s/%s (now %d connection(s))",
             user_email, device_id, _count())


def _count() -> int:
    return sum(len(v) for v in _clients.values())


def connection_count() -> int:
    """Number of live SSE clients across all users. Used by /push/mac-status."""
    return _count()


async def _deliver_to_user(user_email: str, payload: dict,
                           target_device_ids: Optional[set[str]]) -> int:
    """Push ``payload`` onto every queue for ``user_email`` whose device_id
    is in ``target_device_ids`` (or all of them if None)."""
    delivered = 0
    user = (user_email or "").lower()
    for (uemail, device_id), queues in list(_clients.items()):
        if uemail != user:
            continue
        if target_device_ids is not None and device_id not in target_device_ids:
            continue
        for q in queues:
            try:
                q.put_nowait(payload)
                delivered += 1
            except asyncio.QueueFull:
                log.warning("mac_stream: queue full for %s/%s — drop", uemail, device_id)
    return delivered


# ---------------------------------------------------------------------------
# Outbox — producer-side (called by notify._send_push from api OR cron)
# ---------------------------------------------------------------------------
def enqueue_for_outbox(payload: dict, *, kind: Optional[str] = None) -> int:
    """Record one outbox doc per user that has at least one kind=mac
    subscription whose prefs allow this ``kind``.

    Returns the number of users enqueued (NOT the number of devices reached;
    that's resolved by the drain task at delivery time). Safe to call from
    sync OR async code, from any container that has a Mongo connection.

    Generic kind (kind=None) bypasses pref filtering — every user with at
    least one kind=mac sub gets it.
    """
    from push import subs
    db = subs._get_db()
    if db is None:
        return 0
    q: dict = {"kind": "mac"}
    if kind:
        q[f"prefs.{kind}"] = True
    users: set[str] = set()
    for r in db.push_subscriptions.find(q, {"user_email": 1}):
        u = (r.get("user_email") or "").lower()
        if u:
            users.add(u)
    if not users:
        return 0
    now = time.time()
    docs = [{
        "user_email": u,
        "payload": payload,
        "kind": kind,
        "created_at": now,
    } for u in users]
    try:
        db.mac_outbox.insert_many(docs)
    except Exception as exc:
        log.warning("mac_stream: outbox insert failed: %s", exc)
        return 0
    return len(docs)


# ---------------------------------------------------------------------------
# Drain task — consumer-side (api container only)
# ---------------------------------------------------------------------------
_drain_started = False


async def drain_task() -> None:
    """Poll the mac_outbox collection and fan out to live SSE clients.

    Runs forever; spawned from main.py's lifespan hook. Idempotent — calling
    start_drain_task() twice is a no-op.
    """
    from push import subs
    poll_ms = int(os.getenv("MAC_OUTBOX_POLL_MS", "200"))
    log.info("mac_stream: drain task started (poll=%dms)", poll_ms)
    while True:
        try:
            db = subs._get_db()
            if db is None:
                await asyncio.sleep(2.0)
                continue
            # Pull every pending doc and process. Atomic: find_one_and_delete
            # one at a time so two api replicas would never double-deliver.
            # In our single-replica setup this is just defensive.
            while True:
                doc = db.mac_outbox.find_one_and_delete({})
                if not doc:
                    break
                user_email = (doc.get("user_email") or "").lower()
                payload = doc.get("payload") or {}
                kind = doc.get("kind")
                # Snapshot the device_ids whose prefs allow this kind right
                # now (preferences may have changed since enqueue time).
                allowed = subs.list_mac_device_ids(
                    user_email=user_email,
                    filter_kind=kind,
                ) if kind else subs.list_mac_device_ids(user_email=user_email)
                await _deliver_to_user(user_email, payload, allowed if kind else None)
        except Exception as exc:
            log.exception("mac_stream: drain loop crashed, retrying: %s", exc)
            await asyncio.sleep(1.0)
        await asyncio.sleep(poll_ms / 1000.0)


def start_drain_task() -> None:
    """Start the outbox drain task. Safe to call multiple times — only the
    first call actually starts it. Call this from FastAPI's lifespan hook."""
    global _drain_started
    if _drain_started:
        return
    _drain_started = True
    asyncio.create_task(drain_task())


# ---------------------------------------------------------------------------
# SSE generator — used by GET /push/mac-stream
# ---------------------------------------------------------------------------
async def event_stream(user_email: str, device_id: str, request) -> Any:
    """Async generator that yields SSE-formatted events for one client.

    Heartbeats every 15s so intermediaries don't close the idle connection.
    """
    q = await register(user_email, device_id)
    try:
        # Initial hello so the client knows the stream is established.
        yield (f"event: hello\n"
               f"data: {json.dumps({'ok': True, 'ts': time.time(), 'device_id': device_id})}\n\n")
        last_heartbeat = time.time()
        while True:
            if await request.is_disconnected():
                break
            try:
                payload = await asyncio.wait_for(q.get(), timeout=5)
                yield f"event: alert\ndata: {json.dumps(payload)}\n\n"
            except asyncio.TimeoutError:
                pass
            now = time.time()
            if now - last_heartbeat >= 15:
                yield ": heartbeat\n\n"
                last_heartbeat = now
    finally:
        await unregister(user_email, device_id, q)
