"""Short volume debug + drill API.

Endpoints:

  GET /short/{symbol}
      Latest cached snapshot for `symbol`. ~5ms on cache hit, ~300ms on miss.
      Used by the frontend chip + drill modal.

  GET /short/{symbol}/history?days=30
      Last `days` records (default 30). Used by sparkline trend rendering.

  GET /short-interest/reg-sho?check=A,B   (2026-11-22)
      🔒 Hard to borrow — the exchanges' Reg SHO threshold lists, ONE whole
      read via `short_interest.reg_sho.payload` (Mongo only; never a 500).

  GET /short-interest/borrow?symbols=A,B,C   (2026-11-22)
      💸 Borrow — Interactive Brokers' public shortable-shares file, served
      for up to `borrow.MAP_MAX_SYMBOLS` names via `short_interest.borrow.payload`
      (Mongo only; a due file is fetched by the engine's single background
      worker, never inline; never a 500 — a raising read serves
      `borrow.fault_payload(symbols)`, the same shape as "Mongo down").

  GET /short-interest/ssr?symbols=A,B,C   (2026-11-23)
      ⛔ SSR — the SEC Rule 201 short-sale restriction for up to
      `ssr.MAP_MAX_SYMBOLS` names via `short_interest.ssr.payload` (Mongo
      only: the official Nasdaq / NYSE Group lists + the house's computed
      read; a due list is fetched by the `ssr_lists` single background
      worker, never inline; never a 500 — a raising read serves
      `ssr.fault_payload(symbols)`, the same shape as "Mongo down").

  GET /short-interest/map?symbols=A,B,C   (2026-10-03)
      🩳 Short INTEREST (bi-monthly FINRA settlement) for up to
      `read.MAP_MAX_SYMBOLS` names — the ONE bulk read behind the chip on
      every Chart Maps tab and the ticker page. ONE `$in` read of the
      `short_interest_latest` cache via `short_interest.read.si_map`, off the
      event loop; never a provider call. A name with no cached doc is absent.
      2026-11-24: each ok / stale name is handed to `share_basis.kick` (the
      single background worker; dilution, splits, filings) and a queued or
      in-flight name carries `basis.pending` + `basis.retry_after_sec`. The
      answer keeps exactly `{items, n, max_symbols}`.

The short-VOLUME paths go through `short_interest.client`, which manages the
1-day Mongo cache. `/short/{symbol}/interest` is the older live per-name read
(two provider calls per hit); the chip and the ticker page never use it.
"""
from __future__ import annotations

import asyncio
import logging
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from short_interest import client as si_client

log = logging.getLogger("short_interest.api")

router = APIRouter(tags=["short_interest"])


@router.get("/short/{symbol}")
async def get_short_volume(symbol: str, refresh: bool = Query(False)):
    """Latest single-day short-volume snapshot for `symbol`."""
    sym = symbol.upper()
    snap = si_client.short_volume_for(sym, force_refresh=refresh)
    if not snap:
        return JSONResponse(
            {"symbol": sym, "found": False,
             "message": "No short-volume data — FINRA doesn't publish "
                        "for this ticker, or it's an ADR/foreign listing."},
        )
    return {"symbol": sym, "found": True, "snapshot": snap}


@router.get("/short/{symbol}/interest")
async def get_short_interest(symbol: str):
    """Bi-monthly FINRA short interest + squeeze gauges (short % of shares
    outstanding, days-to-cover, settlement-over-settlement trend).

    Complements ``/short/{symbol}`` (daily short-sale VOLUME). Returns
    ``{available: False}`` when Massive has no short-interest record (ADRs,
    foreign listings, very thin names).
    """
    sym = symbol.upper()
    data = await asyncio.to_thread(si_client.short_interest_for, sym)
    if not data:
        return JSONResponse({"symbol": sym, "available": False})
    return {**data, "available": True}


@router.get("/short-interest/map")
async def short_interest_read_map(
    symbols: str = Query("", description="comma-separated tickers; first 200 read"),
):
    """🩳 Served short-interest blocks for a batch of names (display only).

    Every word and number is built by `short_interest.read`; the front end
    prints `chip` / `title` / `rows` verbatim. Never fetches from the provider.
    """
    from short_interest import read as SR
    syms = [s.strip().upper() for s in (symbols or "").split(",") if s.strip()]
    items = await asyncio.to_thread(SR.si_map, syms)
    # 🩳 2026-11-24 [C5] — kick the share-basis worker for the read names (ok / stale only; a no_record block is
    # never kicked, no kick on an empty list) and mark each queued / in-flight name `basis.pending` so the page re-asks.
    kick = [s for s, b in items.items() if isinstance(b, dict) and b.get("status") in ("ok", "stale")]
    if kick:
        try:
            pend = await asyncio.to_thread(_kick_basis, kick)
        except Exception as exc:                               # noqa: BLE001
            log.warning("share_basis: the kick failed: %s", type(exc).__name__)
            pend = []
        if pend:
            retry = _retry_after_sec()
            for sym in pend:
                if sym in items:
                    items[sym] = {**items[sym], "basis": {**(items[sym].get("basis") or {"status": "pending"}),
                                                          "pending": True, "retry_after_sec": retry}}
    return {"items": items, "n": len(items), "max_symbols": SR.MAP_MAX_SYMBOLS}


def _kick_basis(symbols) -> list:
    """The seam to short_interest.share_basis.kick (lazy): the asked names that are queued or in flight. Never raises."""
    if not symbols:
        return []
    try:
        from short_interest import share_basis as SB
        res = SB.kick(list(symbols))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("share_basis: kick unavailable: %s", type(exc).__name__)
        return []
    pend = res.get("pending") if isinstance(res, dict) else None
    return [str(s).upper() for s in (pend if isinstance(pend, list) else []) if isinstance(s, str) and s]


def _retry_after_sec():
    """share_basis.SB_RETRY_AFTER_SEC by name (lazy); None when the module cannot load."""
    try:
        from short_interest import share_basis as SB
        return SB.SB_RETRY_AFTER_SEC
    except Exception:                                          # noqa: BLE001
        return None


@router.get("/short-interest/reg-sho")
async def reg_sho_threshold(check: str = Query("", description="comma-separated tickers: on / off / unknown")):
    """🔒 Hard to borrow (2026-11-22): the whole Reg SHO threshold read, built by
    `short_interest.reg_sho.payload` from Mongo only (a due list is refreshed by
    the engine's single background worker, never inline). Never answers 500: a
    read that raises serves `reg_sho.fault_payload()` — a served line that says
    the tags could not be read."""
    from short_interest import reg_sho as RS
    syms = [s.strip() for s in (check or "").split(",") if s.strip()]
    try:
        return await asyncio.to_thread(RS.payload, check=syms or None)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("reg_sho: the read failed: %s", type(exc).__name__)
        return RS.fault_payload()


@router.get("/short-interest/borrow")
async def ibkr_borrow(symbols: str = Query("", description="comma-separated tickers; first 200 read")):
    """💸 Borrow (2026-11-22): IBKR's borrow fee + shares available for a batch of names, built by
    `short_interest.borrow.payload` from Mongo only. Never answers 500: a read that raises serves
    `borrow.fault_payload(syms)` — the unread block for each asked name, the same shape as "Mongo down"."""
    from short_interest import borrow as BR
    syms = [s.strip() for s in (symbols or "").split(",") if s.strip()]
    try:
        return await asyncio.to_thread(BR.payload, syms)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("borrow: the read failed: %s", type(exc).__name__)
        return BR.fault_payload(syms)


@router.get("/short-interest/ssr")
async def ssr_rule_201(symbols: str = Query("", description="comma-separated tickers; first 200 read")):
    """⛔ SSR (2026-11-23): the SEC Rule 201 short-sale restriction for a batch of names, built by
    `short_interest.ssr.payload` from Mongo only. Never answers 500: a read that raises serves
    `ssr.fault_payload(syms)` — every asked name unknown / unread, the same shape as "Mongo down"."""
    from short_interest import ssr as SSR
    syms = [s.strip() for s in (symbols or "").split(",") if s.strip()]
    try:
        return await asyncio.to_thread(SSR.payload, syms)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ssr: the read failed: %s", type(exc).__name__)
        return SSR.fault_payload(syms)


@router.get("/short/{symbol}/history")
async def get_short_volume_history(
    symbol: str,
    days: int = Query(30, ge=5, le=180),
):
    """Last `days` daily short-volume records for trend analysis."""
    sym = symbol.upper()
    records = si_client.short_volume_history(sym, days=days)
    return {
        "symbol":  sym,
        "n":       len(records),
        "records": records,
    }
