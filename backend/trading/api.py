"""Trading Auto-Pilot API — Minervini-risk-managed exits + manual entries.

GET  /trading/status                engine + account + per-position protection
                                    (+ auto_entry block: enabled, cap,
                                    entries_today, per-candidate last_eval)
POST /trading/arm?armed=true|false  master switch (admin)
POST /trading/auto-entry?enabled=true|false  auto-entry flag (admin)
POST /trading/config                JSON {equity_cap} — sizing ceiling (admin)
GET  /trading/preview               pure entry math, NO order
POST /trading/enter                 bracket entry (admin; the ONLY buy path)
POST /trading/flatten/{symbol}      cancel orders + close position (admin)
POST /trading/flatten-all?confirm=yes  disaster plan (admin)
POST /trading/sim-reset?confirm=yes wipe SIM broker state (admin, sim-only)
GET  /trading/ledger?limit=100      trade_ledger tail
GET  /trading/journal?limit&decisions  round-trip journal (+ open MTM, decisions)
GET  /trading/analytics             Minervini batting/expectancy/win-loss stats

Style mirrors giants/api.py (asyncio.to_thread, lazy imports) but EVERY
route — GETs included — is admin-gated: status/preview/ledger expose account
equity, positions and order history, which is owner-only data.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse

from auth import current_user_email, is_admin_email

router = APIRouter(prefix="/trading", tags=["trading"])


def _require_admin(email: Optional[str]) -> None:
    if not is_admin_email(email):
        raise HTTPException(403, "admin only")


@router.get("/status")
async def trading_status(email: str = Depends(current_user_email)):
    _require_admin(email)
    from trading import exit_engine
    return JSONResponse(await asyncio.to_thread(exit_engine.status))


@router.post("/arm")
async def trading_arm(armed: bool, email: str = Depends(current_user_email)):
    _require_admin(email)
    from trading import exit_engine

    def work():
        exit_engine.update_config(armed=bool(armed))
        exit_engine.ledger("arm" if armed else "disarm",
                           detail={"armed": bool(armed), "by": email})
        return {"armed": bool(armed)}

    return JSONResponse(await asyncio.to_thread(work))


@router.post("/auto-entry")
async def trading_auto_entry(enabled: bool,
                             email: str = Depends(current_user_email)):
    _require_admin(email)
    from trading import exit_engine

    def work():
        exit_engine.update_config(auto_entry=bool(enabled))
        exit_engine.ledger("auto_entry_toggle",
                           detail={"enabled": bool(enabled), "by": email})
        return {"auto_entry": bool(enabled)}

    return JSONResponse(await asyncio.to_thread(work))


EQUITY_CAP_MIN, EQUITY_CAP_MAX = 100.0, 100_000.0


@router.post("/config")
async def trading_config(payload: dict = Body(...),
                         email: str = Depends(current_user_email)):
    _require_admin(email)
    if "equity_cap" not in payload:
        raise HTTPException(400, "equity_cap required")
    try:
        cap = float(payload.get("equity_cap"))
    except (TypeError, ValueError):
        raise HTTPException(400, "equity_cap must be a number")
    if not (EQUITY_CAP_MIN <= cap <= EQUITY_CAP_MAX):
        raise HTTPException(400, "equity_cap must be between %d and %d"
                            % (EQUITY_CAP_MIN, EQUITY_CAP_MAX))
    from trading import exit_engine

    def work():
        exit_engine.update_config(equity_cap=cap)
        exit_engine.ledger("config_update",
                           detail={"equity_cap": cap, "by": email})
        return {"equity_cap": cap}

    return JSONResponse(await asyncio.to_thread(work))


@router.get("/preview")
async def trading_preview(symbol: str, price: Optional[float] = None,
                          stop_pct: Optional[float] = None,
                          email: str = Depends(current_user_email)):
    _require_admin(email)
    from trading import entries
    return JSONResponse(
        await asyncio.to_thread(entries.preview, symbol, price, stop_pct))


@router.post("/enter")
async def trading_enter(payload: dict = Body(...),
                        email: str = Depends(current_user_email)):
    _require_admin(email)
    from trading import entries
    symbol = (payload.get("symbol") or "").strip().upper()
    if not symbol:
        raise HTTPException(400, "symbol required")
    try:
        result = await asyncio.to_thread(
            entries.enter, symbol,
            payload.get("limit_price"),
            payload.get("stop_pct"),
            bool(payload.get("allow_earnings")))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return JSONResponse(result)


@router.post("/flatten/{symbol}")
async def trading_flatten(symbol: str,
                          email: str = Depends(current_user_email)):
    _require_admin(email)
    from trading import exit_engine
    try:
        result = await asyncio.to_thread(exit_engine.flatten, symbol)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return JSONResponse(result)


@router.post("/flatten-all")
async def trading_flatten_all(confirm: str = "",
                              email: str = Depends(current_user_email)):
    _require_admin(email)
    if confirm != "yes":
        raise HTTPException(400, "flatten-all requires ?confirm=yes")
    from trading import exit_engine
    try:
        result = await asyncio.to_thread(exit_engine.flatten_all)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return JSONResponse(result)


@router.post("/sim-reset")
async def trading_sim_reset(confirm: str = "",
                            email: str = Depends(current_user_email)):
    """Wipe the SIM broker (orders/positions/cash back to SIM_STARTING_CASH).
    Refused with 400 unless the ACTIVE broker is the sim — this can never
    touch an Alpaca account."""
    _require_admin(email)
    if confirm != "yes":
        raise HTTPException(400, "sim-reset requires ?confirm=yes")
    from trading import broker as broker_factory
    from trading import broker_sim
    if broker_factory.get_broker() is not broker_sim:
        raise HTTPException(400, "active broker is not the sim "
                                 "(TRADING_BROKER/keys select Alpaca) — "
                                 "sim-reset refused")

    def work():
        out = broker_sim.reset()
        from trading import exit_engine
        exit_engine.ledger("sim_reset_api", detail={"by": email})
        return out

    try:
        return JSONResponse(await asyncio.to_thread(work))
    except Exception as exc:                       # noqa: BLE001
        raise HTTPException(400, str(exc))


@router.get("/ledger")
async def trading_ledger(limit: int = 100,
                         email: str = Depends(current_user_email)):
    _require_admin(email)
    from trading import exit_engine
    rows = await asyncio.to_thread(exit_engine.ledger_tail,
                                   max(1, min(int(limit), 1000)))
    return JSONResponse({"rows": rows})


def _live_prices_for(symbols):
    """Batched live quotes for open-position mark-to-market (lazy — pulls
    pandas via sepa.prices). Failures degrade to {} (no marks, no crash)."""
    if not symbols:
        return {}
    try:
        from sepa.prices import bulk_live_prices
        return bulk_live_prices(list(symbols)) or {}
    except Exception:                              # noqa: BLE001
        return {}


def _mark_open(open_docs):
    """Mark-to-market the OPEN journal docs with a live quote, and build the
    open_marks list analytics.compute consumes for open_risk_dollars. The
    journal stays pure/historical; the live overlay lives only in the API
    response."""
    syms = [d.get("symbol") for d in open_docs if d.get("symbol")]
    quotes = _live_prices_for(syms)
    marked, marks = [], []
    for d in open_docs:
        sym = d.get("symbol")
        entry = d.get("entry") or {}
        q = quotes.get(sym) or {}
        last = q.get("price") or q.get("last_trade_price") or q.get("prev_day_close")
        try:
            last = float(last) if last is not None else None
        except (TypeError, ValueError):
            last = None
        ep = entry.get("price")
        qty = entry.get("qty")
        sp = entry.get("stop_price")
        unreal_pct = unreal_dollars = None
        if last is not None and ep:
            unreal_pct = round((last / ep - 1) * 100, 2)
            if qty is not None:
                unreal_dollars = round(qty * (last - ep), 2)
        out = dict(d)
        out["mark"] = {"last": last, "unrealized_pct": unreal_pct,
                       "unrealized_dollars": unreal_dollars}
        marked.append(out)
        if last is not None and qty is not None and sp is not None:
            marks.append({"qty": qty, "last": last, "stop": sp,
                          "entry_price": ep})
    return marked, marks


@router.get("/journal")
async def trading_journal(limit: int = 100, decisions: int = 0,
                          email: str = Depends(current_user_email)):
    _require_admin(email)
    from trading import journal

    def work():
        journal.reconcile()                        # cheap + idempotent
        closed = journal.load(limit=max(1, min(int(limit), 1000)),
                              status="closed")
        open_docs = journal.load(status="open")
        marked, _ = _mark_open(open_docs)
        out = {"trades": closed, "open": marked,
               "summary": journal.summary()}
        if int(decisions or 0):
            out["decisions"] = journal.decisions(days=14)
        return out

    return JSONResponse(await asyncio.to_thread(work))


@router.get("/analytics")
async def trading_analytics(email: str = Depends(current_user_email)):
    _require_admin(email)
    from trading import analytics, journal

    def work():
        journal.reconcile()                        # journal always current
        closed = journal.load(status="closed")
        open_docs = journal.load(status="open")
        _, marks = _mark_open(open_docs)
        return analytics.compute(closed, open_marks=marks)

    return JSONResponse(await asyncio.to_thread(work))
