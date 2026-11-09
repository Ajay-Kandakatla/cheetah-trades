"""📡 Massive socket canary (GG LIVE spec §3.1 / §7 #10–#11, 2026-11-09) — RE-RUNNABLE, but run ONLY on HIS CALL #10.

It opens deliberate SECOND sockets on the prod stocks key, so it kicks the api's live feed (≤ 2 kicks, each shorter
than the api's KICK_COOLDOWN_SEC). It refuses on a market day between GC.PASS_OPEN_ET and GC.PASS_CLOSE_ET unless
--force.

  step (a) — open B, auth; measure when the api's socket (A) logs `max_connections` after B's auth_success (read
             from the api's own kick timeline, `/live/feed-status?events=1`, admin header); close B cleanly.
  step (b) — open B, auth, then a HARD TCP drop (no close frame); open C at once; measure C's auth_success and first
             frame, and whether C is refused while B's ghost is still counted; close C.

Every step finishes inside `live_feed.KICK_COOLDOWN_SEC − CANARY_MARGIN_SEC`, so the api's own reconnect lands after
it; steps are ≥ CANARY_STEP_GAP_SEC apart. Output: one JSON object on stdout. Results go to
docs/realtime/socket_kick_2026_11_09.md.

  python scripts/live_feed_canary.py --email <admin email> [--api http://127.0.0.1:8000] [--force]

Never prints the key. Writes nothing (no Mongo, no file).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ET = ZoneInfo("America/New_York")
CANARY_STEP_GAP_SEC = 60.0           # MINE — the api's reconnect (30 s) never lands inside the next step
CANARY_MARGIN_SEC = 5.0              # MINE — each step ends this long before the api's kick cooldown
CANARY_AUTH_TIMEOUT_SEC = 8.0        # = live_feed._await_auth's default timeout
CANARY_POLL_SEC = 0.5                # MINE — how often step (a) reads the api's timeline


def refuse_reason(now_et: datetime, force: bool) -> Optional[str]:
    """None = may run. A market day inside the pass window refuses unless --force."""
    if force:
        return None
    from market_hours.gate import closed_reason
    from chart_maps.gajjala import constants as GC
    if closed_reason(now_et):
        return None
    lo = datetime.strptime(GC.PASS_OPEN_ET, "%H:%M").time()
    hi = datetime.strptime(GC.PASS_CLOSE_ET, "%H:%M").time()
    if lo <= now_et.time() < hi:
        return (f"market day {now_et:%Y-%m-%d} inside {GC.PASS_OPEN_ET}–{GC.PASS_CLOSE_ET} ET — "
                "the canary kicks the live feed; run it on a closed window (HIS CALL #10) or pass --force")
    return None


def step_budget() -> float:
    import live_feed
    return max(1.0, float(live_feed.KICK_COOLDOWN_SEC) - CANARY_MARGIN_SEC)


async def _auth(ws, key: str, deadline: float) -> dict:
    """Send auth, wait for a status that settles it. Returns {ok, status, t_auth, first_frame_t}."""
    out = {"ok": False, "status": None, "t_auth": None, "first_frame_t": None}
    await ws.send(json.dumps({"action": "auth", "params": key}))
    while time.time() < deadline:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=max(0.1, deadline - time.time()))
        except asyncio.TimeoutError:
            break
        if out["first_frame_t"] is None:
            out["first_frame_t"] = time.time()
        try:
            evs = json.loads(raw)
        except Exception:                                       # noqa: BLE001
            continue
        for e in evs if isinstance(evs, list) else [evs]:
            st = e.get("status") if isinstance(e, dict) else None
            if st in ("auth_success", "auth_failed", "max_connections", "error"):
                out.update(status=st, ok=(st == "auth_success"), t_auth=time.time())
                return out
    return out


def _api_kick_after(api: str, email: str, since: float) -> Optional[float]:
    """The epoch of the api socket's first `max_connections` timeline row at/after `since`, or None."""
    import requests
    try:
        r = requests.get(f"{api}/live/feed-status", params={"events": 1}, headers={"X-User-Email": email}, timeout=3)
        rows = (r.json() or {}).get("events") or []
    except Exception:                                           # noqa: BLE001
        return None
    for row in rows:
        if row.get("status") == "max_connections" and float(row.get("ts") or 0) >= since:
            return float(row["ts"])
    return None


async def step_a(url: str, key: str, api: str, email: str) -> dict:
    import websockets
    t0 = time.time()
    end = t0 + step_budget()
    res = {"step": "a", "b_status": None, "b_auth_s": None, "a_kicked_after_b_auth_s": None}
    async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
        a = await _auth(ws, key, min(end, time.time() + CANARY_AUTH_TIMEOUT_SEC))
        res["b_status"] = a["status"]
        if a["t_auth"]:
            res["b_auth_s"] = round(a["t_auth"] - t0, 3)
        if a["ok"]:
            while time.time() < end - CANARY_POLL_SEC:
                k = await asyncio.to_thread(_api_kick_after, api, email, a["t_auth"] - 1.0)
                if k is not None:
                    res["a_kicked_after_b_auth_s"] = round(k - a["t_auth"], 3)
                    break
                await asyncio.sleep(CANARY_POLL_SEC)
        await ws.close()
    res["wall_s"] = round(time.time() - t0, 3)
    return res


async def step_b(url: str, key: str) -> dict:
    import websockets
    t0 = time.time()
    end = t0 + step_budget()
    res = {"step": "b", "b_status": None, "c_status": None, "c_auth_s": None, "c_first_frame_s": None}
    b = await websockets.connect(url, ping_interval=None)
    a = await _auth(b, key, min(end, time.time() + CANARY_AUTH_TIMEOUT_SEC))
    res["b_status"] = a["status"]
    tr = getattr(b, "transport", None)
    if tr is not None:
        tr.abort()                                              # the hard TCP drop: no close frame
    t_drop = time.time()
    async with websockets.connect(url, ping_interval=20, ping_timeout=20) as c:
        ca = await _auth(c, key, min(end, time.time() + CANARY_AUTH_TIMEOUT_SEC))
        res["c_status"] = ca["status"]
        if ca["t_auth"]:
            res["c_auth_s"] = round(ca["t_auth"] - t_drop, 3)
        if ca["first_frame_t"]:
            res["c_first_frame_s"] = round(ca["first_frame_t"] - t_drop, 3)
        await c.close()
    res["wall_s"] = round(time.time() - t0, 3)
    return res


async def main_async(args) -> dict:
    import live_feed
    from massive_keys import stocks_key
    key = stocks_key()
    if not key:
        return {"ok": False, "why": "no stocks key"}
    out = {"ok": True, "url": live_feed.MASSIVE_WS_URL, "kick_cooldown_s": live_feed.KICK_COOLDOWN_SEC,
           "step_budget_s": step_budget(), "started_et": datetime.now(tz=ET).isoformat(timespec="seconds"),
           "steps": []}
    out["steps"].append(await step_a(live_feed.MASSIVE_WS_URL, key, args.api, args.email))
    await asyncio.sleep(CANARY_STEP_GAP_SEC)
    out["steps"].append(await step_b(live_feed.MASSIVE_WS_URL, key))
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--api", default="http://127.0.0.1:8000")
    p.add_argument("--email", required=True, help="an admin email (the timeline is admin-only)")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)
    why = refuse_reason(datetime.now(tz=ET), args.force)
    if why:
        print(json.dumps({"ok": False, "refused": why}))
        return 2
    print(json.dumps(asyncio.run(main_async(args)), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
