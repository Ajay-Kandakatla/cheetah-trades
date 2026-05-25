"""HTTP routes for personal portfolio holdings."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from auth import current_user_email
from portfolio import quotes, store

router = APIRouter()


def _rollup(holdings: list[dict], quote_map: dict[str, dict]) -> dict:
    """Compute per-row + total $ values from holdings + live quotes.

    Returned shape feeds both the dedicated /portfolio page and the
    morning-brief Holdings card.
    """
    rows = []
    total_value = 0.0
    total_cost = 0.0
    for h in holdings:
        t = h["ticker"]
        q = quote_map.get(t) or {}
        shares = float(h.get("shares") or 0)
        cost = float(h.get("cost_basis") or 0)
        last = q.get("last")
        cur_value = (shares * last) if (last is not None) else None
        pl_dollars = (cur_value - cost) if (cur_value is not None) else None
        pl_pct = ((cur_value / cost - 1) * 100) if (cur_value is not None and cost > 0) else None
        day_dollars = (shares * (q.get("day_change") or 0)) if last is not None else None
        rows.append({
            "ticker":         t,
            "shares":         shares,
            "cost_basis":     cost,
            "avg_cost":       (cost / shares) if shares > 0 else None,
            "last":           last,
            "prev_close":     q.get("prev_close"),
            "current_value":  None if cur_value is None else round(cur_value, 2),
            "pl_dollars":     None if pl_dollars is None else round(pl_dollars, 2),
            "pl_pct":         None if pl_pct is None else round(pl_pct, 2),
            "day_change_pct": q.get("day_change_pct"),
            "day_dollars":    None if day_dollars is None else round(day_dollars, 2),
            "account":        h.get("account"),
            "tags":           h.get("tags") or [],
        })
        if cur_value is not None:
            total_value += cur_value
        total_cost += cost

    # Sort by current value desc when known, else by cost_basis.
    rows.sort(key=lambda r: -((r.get("current_value") or r.get("cost_basis") or 0)))

    # Position weights (% of total value).
    if total_value > 0:
        for r in rows:
            cv = r.get("current_value") or 0
            r["weight_pct"] = round((cv / total_value) * 100, 1)

    return {
        "rows":         rows,
        "total_value":  round(total_value, 2),
        "total_cost":   round(total_cost, 2),
        "pl_dollars":   round(total_value - total_cost, 2),
        "pl_pct":       round((total_value / total_cost - 1) * 100, 2) if total_cost > 0 else None,
        "day_dollars":  round(sum((r.get("day_dollars") or 0) for r in rows), 2),
        "count":        len(rows),
    }


def build_summary(user_email: str) -> dict:
    """Headless helper — used by morning.brief to inline holdings into
    the brief response without an HTTP round trip."""
    holdings = store.list_holdings(user_email)
    if not holdings:
        return {"available": False, "count": 0, "rows": []}
    quote_map = quotes.fetch_quotes([h["ticker"] for h in holdings])
    summary = _rollup(holdings, quote_map)
    summary["available"] = True
    return summary


@router.get("/portfolio")
async def portfolio_get(user_email: str = Depends(current_user_email)):
    return JSONResponse(build_summary(user_email))


@router.post("/portfolio")
async def portfolio_upsert(
    payload: dict = Body(...),
    user_email: str = Depends(current_user_email),
):
    """Upsert a single holding.

    Body: { ticker, shares, cost_basis, account?, tags?, notes? }
    """
    if not payload.get("ticker"):
        raise HTTPException(400, "ticker required")
    if payload.get("shares") is None:
        raise HTTPException(400, "shares required (0 = closed position; will be removed)")
    if float(payload["shares"]) == 0:
        return JSONResponse(store.remove_holding(
            user_email, payload["ticker"], payload.get("account"),
        ))
    return JSONResponse(store.upsert_holding(
        user_email,
        payload["ticker"],
        float(payload["shares"]),
        float(payload.get("cost_basis") or 0),
        account=payload.get("account"),
        tags=payload.get("tags"),
        notes=payload.get("notes"),
    ))


@router.delete("/portfolio")
async def portfolio_delete(
    ticker: str = Query(...),
    account: str | None = Query(None),
    user_email: str = Depends(current_user_email),
):
    return JSONResponse(store.remove_holding(user_email, ticker, account))
