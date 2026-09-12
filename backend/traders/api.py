"""📌 The GnT tab's endpoints.

Ajay 2026-09-12: "create a tab for me. I wanna track his stocks for investing"
+ "do this daily twice".

Both endpoints READ STORED POSTS. Neither fetches X on a page load — a board
that depends on a third party answering is a board that spins. The twice-daily
cron (`python -m traders.gnt refresh`) owns the fetching.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from traders import feed as G
from traders import registry as R

log = logging.getLogger("traders.api")
router = APIRouter(tags=["traders"])


def _scrub(o):
    """NaN / inf -> None, recursively. FastAPI serialises NaN as a bare `NaN`
    token, which is not JSON and breaks the frontend's JSON.parse."""
    if isinstance(o, float):
        return None if (o != o or o in (float("inf"), float("-inf"))) else o
    if isinstance(o, dict):
        return {k: _scrub(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_scrub(v) for v in o]
    return o


@router.get("/traders")
async def traders_list():
    """Who is tracked, with each one's cited championship claim."""
    return JSONResponse(_scrub({
        "traders": R.TRADERS, "default": R.DEFAULT_KEY,
        "disclaimer": R.DISCLAIMER,
    }))


@router.get("/traders/curated")
async def traders_curated(limit: int = Query(200, ge=1, le=1000)):
    """What the curator ADDED to the scan universe, and what it REJECTED.

    The rejections are the useful half: on the first real run, three of the
    eight uncovered names these accounts mention were CRYPTO (BNB, ETH, XRP).
    A job that added what it was told would have put them in the universe every
    scan, zone store and paper lane runs on."""
    from traders import curate as C
    db = C._db()
    rows = []
    if db is not None:
        try:
            rows = list(db[C.COLL].find({}).sort("checked_at", -1).limit(int(limit)))
        except Exception as exc:                               # noqa: BLE001
            log.warning("traders/curated read failed: %s", exc)
    return JSONResponse(_scrub({
        "rows": rows,
        "added": sum(1 for r in rows if r.get("status") == "added"),
        "rejected": sum(1 for r in rows if r.get("status") == "rejected"),
        "note": ("A name is added because it RESOLVES — a real company record "
                 "and real price history — never because a champion said it. "
                 "Added means the app can SEE it, not that it likes it."),
    }))


@router.get("/traders/{key}")
async def trader_board(key: str, limit: int = Query(400, ge=1, le=2000)):
    """Tito Adhikary's (@GnT_Trades) tickers, each with the post behind it and
    this app's own read beside it.

    READ THE SENTENCE, NOT THE TICKER. He posts forward ideas ("$SPCX ...
    definitely on watch next week") AND past-tense recaps of closed trades,
    several of them PUTS ("Great day on $QQQ puts, +$12K"). A bare ticker list
    off this account inverts him. Every row therefore carries its most recent
    post verbatim, its age in days, and the words found in it — never a
    direction this app inferred.

    His 2,115.1% USIC 2025 win is a CITED claim from @USICOfficial, not a
    number this app measured, and a contest return is not a transferable track
    record: those divisions permit concentration and leverage this app's own
    risk rules forbid.

    Nothing here gates a scan, an alert or a lane.
    """
    if R.get(key) is None:
        return JSONResponse({"error": f"unknown trader '{key}'",
                             "known": R.keys()}, status_code=404)
    return JSONResponse(_scrub(G.board(limit=limit, trader=key)))


@router.post("/traders/refresh")
async def traders_refresh():
    """Fetch X now and store. The cron calls the same function twice a day.

    `ok: false` means the RECENT source returned nothing — X changed its page
    shape and the board is no longer tracking his latest posts. That is
    reported, never hidden: a tracker that silently stops updating is worse
    than one that is visibly broken."""
    return JSONResponse(_scrub(G.refresh_all()))
