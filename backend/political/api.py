"""🏛️ Political disclosures — the curated list and the headline candidates.

Two reads, both cheap and both read-only:

  GET /political/disclosures  → the curated rows (the chip's source of truth)
  GET /political/board        → the rows grouped by category + the watch
                                candidates + what the watch last did

Neither endpoint runs the watch. The watch is a daily cron
(``python -m political.watch``); the board renders what it stored.
"""
from __future__ import annotations

import asyncio
import logging
import math
from datetime import date

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from . import disclosures as D
from . import watch as W

log = logging.getLogger("political.api")
router = APIRouter(tags=["political"])


def _scrub(obj):
    """NaN/Inf → None. The same scrub every board in this app runs: a NaN
    serialises as the bare token `NaN`, which is not legal JSON, and the
    frontend's JSON.parse throws — a failure that looks like a hung page."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _scrub(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    return obj


def _board(limit: int, today=None) -> dict:
    today = today or date.today()
    rows = D.entries()
    entries = []
    groups: dict[str, list[str]] = {c: [] for c in D.CATEGORIES}
    for row in rows:
        out = dict(row)
        out["is_new"] = D.is_new(row, today)
        entries.append(out)
        for cat in (row.get("categories") or []):
            if cat in groups:
                groups[cat].append(row["ticker"])
    return {
        "as_of": today.isoformat(),
        "new_days": D.NEW_DISCLOSURE_DAYS,
        "entries": entries,
        # A ticker with two categories counts in BOTH groups on purpose — INTC
        # is family-disclosed AND a government investment, and hiding one of
        # those to make the counts add to 44 would be the wrong trade.
        "groups": groups,
        "candidates": W.candidates(limit=limit),
        "watch": {
            "last_run": W.last_run(),
            "queries": list(W.WATCH_QUERIES),
            "window_hours": W.WINDOW_HOURS,
            "heuristic": True,
            "note": W.NOTE,
        },
    }


@router.get("/political/disclosures")
async def political_disclosures():
    """The curated list — the rows behind the 🏛️/🇺🇸 chips."""
    rows = D.entries()
    return JSONResponse(_scrub({"n": len(rows), "entries": rows,
                                "new_days": D.NEW_DISCLOSURE_DAYS}))


@router.get("/political/board")
async def political_board(
    limit: int = Query(200, ge=1, le=1000,
                       description="max watch candidates to return, newest first"),
):
    """The 🏛️ POTUS tab's payload: the curated rows grouped, plus every
    heuristic candidate the watch has stored.

    `limit` is coerced inside the handler for the reason every board in this
    repo coerces: these functions get called directly in the container for
    smoke tests, and FastAPI resolves `Query(...)` defaults at REQUEST time, so
    a direct call receives the Query OBJECT, which is not an int.
    """
    n = limit if isinstance(limit, int) else 200
    return JSONResponse(_scrub(await asyncio.to_thread(_board, n)))
