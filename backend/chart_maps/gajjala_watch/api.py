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
    handler). `store.add`; on `added` / `replaced` (🔁 2026-11-18) ONLY, only when the watch is on, and only when the minute loop will NOT read the
    name within about a minute (`colls.loop_reads_soon` False), one `--build` child is requested — single-flight (C2.5): at most ONE alive in this
    container; an alive child re-reads the list before it exits, so a second add while it runs spawns nothing.
    C2.5 SUPERSEDED 2026-11-19 (Ajay, relayed verbatim: "When I add a new ticket they are gettinf added in to que but not
    active / charts are not loading I amhaving to click on the chips again"): IN the window (`loop_reads_soon` True) the
    add now spawns the same single-flight child with `--new-only` (C.ARGV_BUILD_NEW) — only names with no tile doc, or
    added after their tile doc's last write — instead of waiting for the minute loop. Cost: 1–2 Massive minute calls per
    added name: today (forced, bars.py:287) + the prior day when the 1-minute cache misses (bars.py:283 — a brand-new
    name always misses); single-flight. Out of the window: the plain `--build` child, unchanged.
  * `DELETE /chart-maps/gajjala-watch/symbols/{symbol}` — the same gate; `store.remove`, then ALWAYS `auto.dismiss`
    (🤖 2026-11-17, spec ggwauto §3.5): the × on an auto name removes it until tomorrow, and a × on his own name also
    blocks an auto re-add today (HIS CALL #6). His list answered `absent` and the auto list `dismissed` → the auto
    answer; otherwise the store's own answer. A raising / missing auto engine is logged and the store's answer stands.
    The answer shape stays `{state, symbols, symbol, text}` (`symbols` = his list).
  * `GET    /chart-maps/gajjala-watch/symbols` — the ➕/➖ card button (2026-11-15): the owner's names only
    (`payload.list_payload`), read off the event loop; anyone else gets exactly `owner_only` and nothing is read; a
    failing read answers `error`, never an empty list (an empty list would offer ➕ on a name already watched).

  * `POST   /chart-maps/gajjala-watch/live` (👀 LIVE 2026-11-16, Ajay: "Can you make the watch list charts live
    please" · "I need it to be live live.. per sec change") — `require_primary_admin` (404 for anyone else, resolved
    BEFORE the body — the body is read inside the handler, so even malformed JSON from a non-owner is a 404; nothing
    registered). Body `{"symbols": [...]}` (not a list → 422 `live_card.BAD_BODY_TEXT`) →
    `live_card.normalize` → `live_hub.register_interest(C.TAB, syms, None)` on the event loop (sync, no I/O); a body
    `variant` is IGNORED (always the watch tab). Answer `{state, stream: {on, word, state}, tab, symbols}` with the
    SAME fallbacks as `chart_maps.api._stream_interest` (the feed's own word when the hub gives none; hub missing /
    raising → `on: false`). No Mongo read, no snapshot, nothing written — the prices arrive as `gajjala.update`.

  * `GET    /chart-maps/gajjala-watch/runners` (📅 2026-11-22, spec watch_org §3.4 — Ajay: "use that space between the
    parent tab of Gajjala and watch tab to be for previous day runners but remove them if they don’t run the current
    day") — PRIMARY OWNER ONLY through `_is_owner` (anyone else, or a direct call with the Depends OBJECT, gets exactly
    `owner_only_payload()` and nothing is read). `runners.strip(now)` built, scrubbed and JSON-encoded inside ONE
    `asyncio.to_thread`; never raises (state `error` + the served sentence). Display only.

  * `GET    /chart-maps/gajjala-watch/runners/chart/{symbol}[?tf=1m|5m|15m]` (📅 2026-11-26, spec runcharts §3.5 — Ajay:
    "I want you to have continous charts for previous day runners … I wanna able to horizontal scroll tp check
    continuity like he does") — PRIMARY OWNER ONLY through `_is_owner` (anyone else, or a direct call with the Depends
    OBJECT, gets exactly `owner_only_payload()` and nothing is read). `runchart.build(symbol, now, tf=tf)` (imported
    LAZILY), scrubbed and JSON-encoded inside ONE `asyncio.to_thread`; never raises (state `error` +
    C.RUNCHART_FAULT_TEXT). No session-count parameter: an unknown query key changes nothing. Display only.

  * `POST   /chart-maps/gajjala-watch/run/{symbol}` (▶ 2026-11-24, spec ggrun §3.4 — Ajay: "On the Watch list I need a
    run button to run against Gajjalas rules of a stock") — `require_primary_admin` (404 for anyone else, before the
    handler). `run_rules.run(symbol, now)` (imported LAZILY through C.RUN_MODULE), scrubbed and JSON-encoded inside ONE
    `asyncio.to_thread`; HTTP 200 for every served state. An import / unexpected fault → state `error` with the string
    title and note (C.RUN_TITLE_TEXT, C.RUN_ERROR_TEXT, C.RUN_NOTE_TEXT). Rings nothing, records nothing.

The admin email never appears in an answer. UNMEASURED — a cross is information, not an entry.
"""
from __future__ import annotations

import asyncio
import gzip
import importlib
import json
import logging
import threading
from datetime import datetime
from typing import Any, Optional
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


def _runners_body(now: datetime) -> bytes:
    """📅 2026-11-22 — the owner's strip as JSON bytes, called ONLY inside asyncio.to_thread. Never raises: a fault
    anywhere → {state: "error", text: C.RUNNERS_ERROR_TEXT}."""
    from growth.api import _scrub
    try:
        from . import runners as RN
        out = RN.strip(now)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch: runners strip failed: %s", type(exc).__name__)
        out = {"state": "error", "text": C.RUNNERS_ERROR_TEXT}
    return JSONResponse(_scrub(out)).body


def _runchart_body(symbol, now: datetime, tf) -> bytes:
    """📅 2026-11-26 — the owner's continuous chart as JSON bytes, called ONLY inside asyncio.to_thread. Never raises: a
    fault anywhere → {state: "error", text: C.RUNCHART_FAULT_TEXT}."""
    from growth.api import _scrub
    try:
        from . import runchart as RC
        out = RC.build(symbol, now, tf=tf)
        if not isinstance(out, dict):
            raise TypeError("not an answer")
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch: runner chart failed: %s", type(exc).__name__)
        out = {"state": "error", "text": C.RUNCHART_FAULT_TEXT.format(sym=ST.normalize(symbol) or str(symbol))}
    try:
        return JSONResponse(_scrub(out)).body
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch: runner chart not encoded: %s", type(exc).__name__)
        return JSONResponse({"state": "error",
                             "text": C.RUNCHART_FAULT_TEXT.format(sym=ST.normalize(symbol) or str(symbol))}).body


def _run_fallback() -> dict:
    out = {k: None for k in C.RUN_ANSWER_KEYS}
    out.update(state="error", title=C.RUN_TITLE_TEXT, text=C.RUN_ERROR_TEXT, note=C.RUN_NOTE_TEXT, setups=[])
    return out


def _run_body(symbol: str, now: datetime) -> bytes:
    """▶ 2026-11-24 — the run's answer as JSON bytes, called ONLY inside asyncio.to_thread. Never raises: an import /
    unexpected fault → the fallback answer (state `error`, title and note always strings)."""
    from growth.api import _scrub
    try:
        out = importlib.import_module(C.RUN_MODULE).run(symbol, now)
        if not isinstance(out, dict):
            raise TypeError("not an answer")
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch: run rules failed: %s", type(exc).__name__)
        out = _run_fallback()
    try:
        return JSONResponse(_scrub(out)).body
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch: run answer not encoded: %s", type(exc).__name__)
        return JSONResponse(_scrub(_run_fallback())).body


def _request_build(new_only: bool = False) -> str:
    """[C2.5] Single-flight `--build` child (the on_demand._STATE shape): alive → "running"; else spawn → "spawned";
    a raising spawn logs one line → "error". Never raises. `new_only` (2026-11-19, in window) → C.ARGV_BUILD_NEW:
    1–2 Massive minute calls per added name: today (forced, bars.py:287) + the prior day when the 1-minute cache misses
    (bars.py:283 — a brand-new name always misses); single-flight."""
    from chart_maps.gajjala import on_demand as OD
    with _LOCK:
        if OD._alive(_BUILD["proc"]):
            return "running"
        try:
            _BUILD["proc"] = OD._spawn(list(C.ARGV_BUILD_NEW if new_only else C.ARGV_BUILD), C.PROC_NAME_BUILD)
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


@router.get(C.API_RUNNERS_PATH)
async def gajjala_watch_runners(email: Optional[str] = Depends(maybe_current_user)):
    """📅 the owner's previous-day runners strip. A direct call (container smoke test) receives the Depends OBJECT and is
    served as a non-owner — nothing read."""
    if not _is_owner(email):
        return PL.owner_only_payload()
    body = await asyncio.to_thread(_runners_body, datetime.now(ET))
    return Response(content=body, media_type="application/json")


@router.get(C.API_RUNCHART_PATH)
async def gajjala_watch_runner_chart(symbol: str, email: Optional[str] = Depends(maybe_current_user),
                                     tf: Optional[str] = Query(None)):
    """📅 the owner's continuous chart of one runner. A direct call (container smoke test) receives the Depends OBJECT
    and is served as a non-owner — nothing read."""
    if not _is_owner(email):
        return PL.owner_only_payload()
    body = await asyncio.to_thread(_runchart_body, symbol, datetime.now(ET), tf)
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
    out = await asyncio.to_thread(_broker_note, out)                  # 🚫 2026-11-19 — the word, never a block
    if out.get("state") in ("added", "replaced"):            # 🔁 2026-11-18: a replace adds a name too
        try:
            if CO.enabled():                                    # off → no build child
                _request_build(new_only=bool(CO.loop_reads_soon(datetime.now(ET))))   # 2026-11-19: in window too
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala_watch: build request failed: %s", exc)
    return out


@router.post(C.API_RUN_PATH)
async def gajjala_watch_run(symbol: str, email: str = Depends(require_primary_admin)):
    """▶ the owner's run of Gajjala's rules on ONE Watch name (body built off the event loop)."""
    body = await asyncio.to_thread(_run_body, symbol, datetime.now(ET))
    return Response(content=body, media_type="application/json")


def _broker_note(out) -> Any:
    """🚫 2026-11-19 (spec watchfid): `broker.add_note` (imported lazily through sys.modules) — his add of a listed name
    still lands; its answer carries the word. Any failure → the store's answer unchanged."""
    try:
        return importlib.import_module(PL.BROKER_MODULE).add_note(out)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch: broker add note failed: %s", type(exc).__name__)
        return out


def _dismiss(symbol, by) -> Any:
    """🤖 `auto.dismiss`, the engine imported LAZILY through sys.modules (tests inject a stub there)."""
    return importlib.import_module(PL.AUTO_MODULE).dismiss(symbol, by=by)


def _rules_dismiss(symbol, by) -> Any:
    """✅ `allrules.dismiss` (2026-11-24, spec watchall §3.4), imported LAZILY through sys.modules (PL.RULES_MODULE)."""
    return importlib.import_module(PL.RULES_MODULE).dismiss(symbol, by=by)


def _rules_error(symbol) -> Optional[dict]:
    """✅ [C1] the `error` answer when the name is STILL served in the ✅ list (allrules.current_symbols of today's
    session), else None — never "absent" / "dismissed" for a name he still sees. A fault → None. Never raises."""
    try:
        from . import build as BLD                              # lazy: the session clock (tab.session_for)
        sym = ST.normalize(symbol)
        if sym is None:
            return None
        served = importlib.import_module(PL.RULES_MODULE).current_symbols(CO.colls(None),
                                                                           BLD.session_of(datetime.now(ET))[0])
        if CO.fold(sym) not in {CO.fold(s) for s in served or [] if isinstance(s, str)}:
            return None
        return {"state": "error", "symbols": CO.owner_symbols(None), "symbol": sym, "text": PL.store_text("error", sym)}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch: all-rules served check failed: %s", type(exc).__name__)
        return None


@router.delete(C.API_SYMBOL_PATH)
async def gajjala_watch_remove(symbol: str, email: str = Depends(require_primary_admin)):
    """His ×: store.remove, then ALWAYS 🤖 auto.dismiss, then (C.RULES_ON) ✅ allrules.dismiss. The answer: the store's
    `removed` → the store's; ✅ `error` while the name is still served in ✅ → that error [C1]; else (store `absent`) the
    🤖 `dismissed`, else the ✅ `dismissed`; else the store's."""
    out = await asyncio.to_thread(ST.remove, symbol, by=email)
    try:
        a = await asyncio.to_thread(_dismiss, symbol, email)
    except Exception as exc:                                    # noqa: BLE001 — the store's answer stands
        log.warning("gajjala_watch: auto dismiss failed: %s", exc)
        a = None
    r = None
    if C.RULES_ON:
        try:
            r = await asyncio.to_thread(_rules_dismiss, symbol, email)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala_watch: all-rules dismiss failed: %s", type(exc).__name__)
            r = {"state": "error"}
    st = out.get("state") if isinstance(out, dict) else None
    if st == "removed":
        return out
    if isinstance(r, dict) and r.get("state") == "error":
        err = await asyncio.to_thread(_rules_error, symbol)
        if err is not None:
            return err
    if st == "absent" and isinstance(a, dict) and a.get("state") == "dismissed":
        return a
    if st == "absent" and isinstance(r, dict) and r.get("state") == "dismissed":
        return r
    return out


def _feed_pair() -> tuple:
    """(word, state) of the ONE socket through `live_feed.state_word()` — (None, None) when absent or raising
    (the `chart_maps.api._feed_view` shape, re-read here so this router never imports the card routes)."""
    try:
        import live_feed                                        # lazy: the api process owns the socket
        state, word = live_feed.state_word()
    except Exception as exc:                                    # noqa: BLE001
        log.debug("gajjala_watch: feed state unavailable: %s", exc)
        return None, None
    return (word if isinstance(word, str) and word.strip() else None,
            state if isinstance(state, str) and state.strip() else None)


def _live_interest(syms: list) -> dict:
    """Register the watch's live interest with the hub → {"on", "word", "state"} — the `_stream_interest` fallbacks:
    the hub's served pair, else the feed's own; hub missing / raising → on False with the feed's word. Never raises."""
    word, state = _feed_pair()
    try:
        import live_hub                                         # lazy: the hub lives in the api process
        res = live_hub.register_interest(C.TAB, syms, None)
    except Exception as exc:                                    # noqa: BLE001 — the route answers either way
        log.debug("gajjala_watch: live interest failed: %s", exc)
        return {"on": False, "word": word, "state": state}
    res = res if isinstance(res, dict) else {}
    w, st = res.get("word"), res.get("state")
    return {"on": res.get("on") is True, "word": w if isinstance(w, str) and w.strip() else word,
            "state": st if isinstance(st, str) and st.strip() else state}


def _parse_body(raw: bytes) -> Any:
    """The live POST body → a parsed value; empty / malformed / not UTF-8 → None (the route then answers 422
    `BAD_BODY_TEXT`). Parsed INSIDE the handler, after `require_primary_admin`, so a non-owner's malformed JSON never
    reaches FastAPI's body parser — it gets the gate's 404 like every other body (REFIX 2026-11-16)."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None


@router.post(C.API_LIVE_PATH)
async def gajjala_watch_live(request: Request, email: str = Depends(require_primary_admin)):
    """👀 LIVE: the owner's board registers its names with the hub every renewal; the variant is ALWAYS the watch tab.
    The body is read HERE (no declared body parameter): FastAPI parses a declared body before the dependency runs."""
    from chart_maps import live_card as LC
    payload = _parse_body(await request.body())
    syms_in = payload.get("symbols") if isinstance(payload, dict) else None
    if not isinstance(syms_in, list):
        return JSONResponse({"detail": LC.BAD_BODY_TEXT}, status_code=422)
    syms = LC.normalize(syms_in)
    return {"state": "ok", "stream": _live_interest(syms), "tab": C.TAB, "symbols": syms}
