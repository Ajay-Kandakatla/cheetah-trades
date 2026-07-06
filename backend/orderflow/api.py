"""FastAPI handlers for the order-flow ("Tape") module."""
from __future__ import annotations

import logging

from fastapi import APIRouter

log = logging.getLogger("orderflow.api")
router = APIRouter(tags=["orderflow"])


@router.get("/orderflow/{symbol}")
async def get_orderflow(symbol: str):
    """Cached Tape snapshot for one ticker (instant). `stale: true` means the
    FE should offer the Scan button — snapshots age out in 20 min during RTH,
    or when they're from a previous session."""
    from . import engine
    doc = engine.get_cached(symbol.upper())
    if not doc:
        return {"symbol": symbol.upper(), "found": False,
                "message": "No tape snapshot yet — run a scan."}
    return {"found": True, **doc}


@router.post("/orderflow/{symbol}/scan")
async def scan_orderflow(symbol: str):
    """Compute a fresh Tape snapshot — pulls the session's raw prints from
    Massive and re-derives delta / big prints / bursts / profile / verdict.
    Typical SEPA names return in a few seconds; megacap tape (NVDA-class,
    >1M prints) can take ~20-30s and flags `tape.truncated` past 1.2M."""
    import asyncio
    from . import engine
    snap = await asyncio.to_thread(engine.compute, symbol.upper())
    if not snap:
        return {"symbol": symbol.upper(), "found": False,
                "message": "No prints from Massive for this ticker in the last "
                           "few sessions — illiquid or invalid symbol."}
    return {"found": True, **snap}


@router.get("/orderflow/ledger/accuracy")
async def get_accuracy():
    """OUR measured forward record for the Tape verdict (per-verdict hit
    rates at T+1/T+5). This is the honest counterweight to any claimed
    win rate — small n early, wide error bars, says so in the payload."""
    from . import history
    return history.accuracy()


__all__ = ["router"]
