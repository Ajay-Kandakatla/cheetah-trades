"""👀 Gajjala's Watch — the routes (spec §3.4, WP-A, 2026-11-15).

Ajay 2026-11-15, verbatim: "I need dashboard to add tickers to Gajjalas watch dashboard. I wanna be able to remove and
add remove tickers from the dashboard."

  * `GET  /chart-maps/gajjala-watch[?symbols=A,B]` — PRIMARY OWNER ONLY through `maybe_current_user` + `_is_owner`
    (the `long_term_list/api.py` pattern). Anyone else — another email, no email, or a direct call that receives the
    `Depends` OBJECT — gets exactly `{state: "owner_only", reason, title}`, HTTP 200, and nothing is read for them.
    The owner's body is built, scrubbed (NaN → null), JSON-encoded AND gzipped inside ONE `asyncio.to_thread` — never
    on the event loop (C2.4; the `/sepa/scan` pattern, main.py). `symbols` = the pending poll's names: normalized,
    and only LISTED names are served (an unlisted one is dropped, never read).
  * `POST   /chart-maps/gajjala-watch/symbols/{symbol}` — `require_primary_admin` (404 for anyone else, before the
    handler). `store.add`; on `added` ONLY, only when the watch is on, and only when the minute loop will NOT read the
    name within about a minute (`colls.loop_reads_soon` False), one `--build` child is requested — single-flight (C2.5): at most ONE alive in this
    container; an alive child re-reads the list before it exits, so a second add while it runs spawns nothing.
  * `DELETE /chart-maps/gajjala-watch/symbols/{symbol}` — the same gate; `store.remove`.
  * `GET    /chart-maps/gajjala-watch/symbols` — the ➕/➖ card button (2026-11-15): the owner's names only
    (`payload.list_payload`), read off the event loop; anyone else gets exactly `owner_only` and nothing is read; a
    failing read answers `error`, never an empty list (an empty list would offer ➕ on a name already watched).

The admin email never appears in an answer. UNMEASURED — a cross is information, not an entry.
"""
from __future__ import annotations

import asyncio
import gzip
import logging
import threading
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response

from auth import maybe_current_user
from ollama_chat.api import require_primary_admin

from . import colls as CO
from . import constants as C
from . import payload as PL
from . import store as ST

log = logging.getLogger("chart_maps.gajjala_watch.api")
ET = ZoneInfo("America/New_York")

router = APIRouter(tags=["chart-maps"])

_LOCK = threading.Lock()
_BUILD: dict = {"proc": None}
BUILD_STATES = ("spawned", "running", "error")


def _is_owner(email) -> bool:
    if not isinstance(email, str) or not email.strip():
        return False
    from ollama_chat.api import is_primary_admin                 # lazy: tests monkeypatch it
    try:
        return bool(is_primary_admin(email))
    except Exception:                                           # noqa: BLE001
        return False


def parse_only(raw) -> Optional[list]:
    """`?symbols=A,B` → normalized names, de-duplicated in order; absent / not a string → None (= every listed name)."""
    if not isinstance(raw, str):
        return None
    out: list = []
    for part in raw.split(","):
        s = ST.normalize(part)
        if s and s not in out:
            out.append(s)
    return out


def _body(now: datetime, only: Optional[list]) -> tuple:
    """(json bytes, gzip bytes) of the owner's board — called ONLY inside asyncio.to_thread (C2.4)."""
    from growth.api import _scrub
    body = JSONResponse(_scrub(PL.build(now, only=only))).body
    return body, gzip.compress(body, compresslevel=6)


def _request_build() -> str:
    """[C2.5] Single-flight `--build` child (the on_demand._STATE shape): alive → "running"; else spawn → "spawned";
    a raising spawn logs one line → "error". Never raises."""
    from chart_maps.gajjala import on_demand as OD
    with _LOCK:
        if OD._alive(_BUILD["proc"]):
            return "running"
        try:
            _BUILD["proc"] = OD._spawn(list(C.ARGV_BUILD), C.PROC_NAME_BUILD)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala_watch: build child not spawned: %s", exc)
            return "error"
        return "spawned"


@router.get(C.API_PATH)
async def gajjala_watch(request: Request = None, email: Optional[str] = Depends(maybe_current_user),
                        symbols: Optional[str] = Query(None)):
    """👀 the owner's board — stored tile docs only (never a bar fetch). A direct call (container smoke test) receives
    the Depends OBJECT and is served as a non-owner."""
    if not _is_owner(email):
        return PL.owner_only_payload()
    only = parse_only(symbols)
    body, gz = await asyncio.to_thread(_body, datetime.now(ET), only)
    accept = (request.headers.get("accept-encoding") or "") if request is not None else ""
    if "gzip" in accept.lower():
        return Response(content=gz, media_type="application/json",
                        headers={"Content-Encoding": "gzip", "Vary": "Accept-Encoding"})
    return Response(content=body, media_type="application/json")


@router.get(C.API_LIST_PATH)
async def gajjala_watch_symbols(email: Optional[str] = Depends(maybe_current_user)):
    """➕/➖ the owner's watch names for the card buttons. A direct call gets the Depends OBJECT → owner_only."""
    if not _is_owner(email):
        return PL.owner_only_payload()
    try:
        syms = await asyncio.to_thread(CO.owner_symbols, None, True)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch: list read failed: %s", exc)
        return PL.error_payload("the list could not be read")
    return PL.list_payload(syms)


@router.post(C.API_SYMBOL_PATH)
async def gajjala_watch_add(symbol: str, email: str = Depends(require_primary_admin)):
    out = await asyncio.to_thread(ST.add, symbol, by=email)
    if out.get("state") == "added":
        try:
            if CO.enabled() and not CO.loop_reads_soon(datetime.now(ET)):     # off → no build child
                _request_build()
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala_watch: build request failed: %s", exc)
    return out


@router.delete(C.API_SYMBOL_PATH)
async def gajjala_watch_remove(symbol: str, email: str = Depends(require_primary_admin)):
    return await asyncio.to_thread(ST.remove, symbol, by=email)
