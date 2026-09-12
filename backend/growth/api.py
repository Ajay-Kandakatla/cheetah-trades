"""🚀 Explosive Growth API — read-only.

Nothing here runs the screen inline: GET /growth/board reads the stored doc
that the weekly cron built. POST /growth/refresh rebuilds it on demand (his
"make sure we are going to update this list as new one come to the market").
"""
from __future__ import annotations

import logging
import math

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from . import alerts as A
from . import tracker as T

log = logging.getLogger("growth.api")

router = APIRouter(tags=["growth"])


def _scrub(o):
    """NaN / inf -> None, recursively. A NaN survives json.dumps in Python and
    breaks the frontend's JSON.parse — the same bug that once stuck the SEPA
    scan button on 'Scanning…'."""
    if isinstance(o, dict):
        return {k: _scrub(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_scrub(v) for v in o]
    if isinstance(o, float):
        return None if (o != o or math.isinf(o)) else o
    return o


def _payload(doc: dict) -> dict:
    rows = doc.get("rows") or []
    return _scrub({
        "rows": rows,
        "n": len(rows),
        "built_at": (doc.get("built_at").isoformat()
                     if hasattr(doc.get("built_at"), "isoformat")
                     else doc.get("built_at")),
        "screen": doc.get("screen") or {
            "min_sales_growth_pct": T.MIN_SALES_GROWTH_PCT,
            "min_eps_growth_pct": T.MIN_EPS_GROWTH_PCT,
            "min_prior_sales_pct": T.MIN_PRIOR_SALES_PCT,
            "cap_floor": T.MIN_CAP_USD,
            "universe_mode": T.UNIVERSE_MODE,
        },
        # Said on the board itself, not only in a doc nobody opens.
        "disclaimer": (
            "Discovery list, NOT a signal. The 100%/100% screen has never been "
            "measured forward. No market-cap floor here (your call) — rows the "
            "trading engine will refuse to buy say so in their own warnings."
        ),
    })


@router.get("/growth/board")
async def growth_board():
    return JSONResponse(_payload(T.board() or {}))


@router.post("/growth/refresh")
async def growth_refresh(limit: int = Query(T.MAX_ROWS, ge=1, le=1000)):
    """Rebuild the board now. The weekly cron calls the same function."""
    return JSONResponse(_payload(T.build(limit=limit)))


@router.get("/growth/tags")
async def growth_tags():
    """The board as a SYMBOL -> tag map, for the 🚀 chip on every other board.

    Ajay 2026-09-11: "I am hoping this new list will be considerd in all chart
    maps. Like in Deep demand scan." Every Chart Maps tile board renders through
    one component, so one small map lights them all up — a name already on his
    demand / VCP / breaking board shows that it is ALSO a 100/100 grower.

    Deliberately tiny: symbol -> {sales, eps, refused}. The chip is a POINTER to
    the growth board, not a second copy of it, so the boards can never drift
    into disagreeing about what qualifies."""
    rows = (T.board() or {}).get("rows") or []
    tags = {}
    for r in rows:
        sym = r.get("symbol")
        if not sym:
            continue
        tags[sym] = {
            "sales": r.get("sales_growth_pct"),
            "eps": r.get("q_eps_growth_pct"),
            # True when the trading engine will refuse it (sub-$2 or a known
            # sub-$700M cap) — the chip must not make such a name look clean
            # just because its sales are good.
            "refused": any(str(w).startswith("⛔") for w in (r.get("warnings") or [])),
        }
    return JSONResponse(_scrub({"n": len(tags), "tags": tags}))


@router.get("/growth/at-demand")
async def growth_at_demand():
    """Which board names are at demand with an intact floor RIGHT NOW — the
    same list the 🚀 growth_demand_alert kind pushes from. Read-only: this
    sends nothing and writes no dedupe state."""
    items = A.candidates()
    return JSONResponse(_scrub({
        "n": len(items),
        "kind": A.KIND,
        "items": [{"symbol": i["row"]["symbol"],
                   "sales_growth_pct": i["row"].get("sales_growth_pct"),
                   "q_eps_growth_pct": i["row"].get("q_eps_growth_pct"),
                   "price": i["row"].get("price"),
                   "band": i["band"],
                   "room": i["room"],
                   "warnings": i["row"].get("warnings") or []}
                  for i in items],
    }))
