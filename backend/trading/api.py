"""Trading Auto-Pilot API — Minervini-risk-managed exits + manual entries.

GET  /trading/status                engine + account + per-position protection
                                    (+ auto_entry block: enabled, cap,
                                    entries_today, per-candidate last_eval)
POST /trading/arm?armed=true|false  master switch (admin)
POST /trading/auto-entry?enabled=true|false  auto-entry flag (admin)
POST /trading/config                JSON {equity_cap?, auto_min_score?,
                                    auto_min_rs?, progressive_exposure?,
                                    pyramiding?, zone_edge_entry?,
                                    zone_edge_rules?, catalyst_entry?} —
                                    sizing ceiling + funnel floors + pilot
                                    governor + the Supply & Demand zone-edge
                                    and catalyst-lane entry switches (admin;
                                    null resets to default = OFF)
GET  /trading/race?days=5           execution race: engine vs owner per
                                    zone-edge signal (lags + price gaps)
GET  /trading/autopsies?days=30     failed-trade autopsies: every losing
                                    round-trip classified (owner rules) +
                                    numbers + feedback line + rule table
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
    """Owner-tunable engine knobs. Accepts any subset of: equity_cap,
    auto_min_score (funnel score floor), auto_min_rs (funnel RS floor,
    TLSW p.79 'preferably in the 80s or 90s'). An explicit null resets a
    floor to its code default."""
    _require_admin(email)
    updates = {}
    if "equity_cap" in payload:
        try:
            cap = float(payload.get("equity_cap"))
        except (TypeError, ValueError):
            raise HTTPException(400, "equity_cap must be a number")
        if not (EQUITY_CAP_MIN <= cap <= EQUITY_CAP_MAX):
            raise HTTPException(400, "equity_cap must be between %d and %d"
                                % (EQUITY_CAP_MIN, EQUITY_CAP_MAX))
        updates["equity_cap"] = cap
    for floor_key, lo, hi in (("auto_min_score", 0.0, 100.0),
                              ("auto_min_rs", 1.0, 99.0)):
        if floor_key not in payload:
            continue
        raw = payload.get(floor_key)
        if raw is None:
            updates[floor_key] = None      # reset to the code default
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            raise HTTPException(400, "%s must be a number or null" % floor_key)
        if not (lo <= val <= hi):
            raise HTTPException(400, "%s must be between %g and %g"
                                % (floor_key, lo, hi))
        updates[floor_key] = val
    for bool_key in ("progressive_exposure", "pyramiding"):
        if bool_key not in payload:
            continue
        raw = payload.get(bool_key)
        if raw is None:
            updates[bool_key] = None                 # reset -> default ON
        elif isinstance(raw, bool):
            updates[bool_key] = raw
        else:
            raise HTTPException(400, "%s must be a boolean or null" % bool_key)
    if "zone_edge_entry" in payload:
        # Supply & Demand zone-edge entries (trading/zone_edge_entry.py).
        # Strict boolean like the auto_entry flag; null resets to the
        # default, which is OFF in every mode. Arming still gates orders.
        raw = payload.get("zone_edge_entry")
        if raw is None:
            updates["zone_edge_entry"] = False       # reset -> default OFF
        elif isinstance(raw, bool):
            updates["zone_edge_entry"] = raw
        else:
            raise HTTPException(400, "zone_edge_entry must be a boolean or null")
    if "catalyst_entry" in payload:
        # Catalyst-lane entries (trading/catalyst_entry.py; Ajay 2026-09-05
        # "catalyst based entries time to time"). Strict boolean like the
        # zone_edge_entry flag; null resets to the default, which is OFF in
        # every mode. Arming still gates orders; paper account.
        raw = payload.get("catalyst_entry")
        if raw is None:
            updates["catalyst_entry"] = False        # reset -> default OFF
        elif isinstance(raw, bool):
            updates["catalyst_entry"] = raw
        else:
            raise HTTPException(400, "catalyst_entry must be a boolean or null")
    if "options_entry" in payload:
        # Options lane (trading/options_lane.py; Ajay 2026-09-06). Strict
        # boolean; null resets to the default OFF. Arming still gates orders;
        # paper account only.
        raw = payload.get("options_entry")
        if raw is None:
            updates["options_entry"] = False
        elif isinstance(raw, bool):
            updates["options_entry"] = raw
        else:
            raise HTTPException(400, "options_entry must be a boolean or null")
    if "zone_edge_rules" in payload:
        # Owner rule switches for the zone-edge entries (Ajay 2026-09-03:
        # "Enter anything that is in demand zone ... any stocks crossing the
        # resistance or supply zone buy them too"). A dict of
        # {demand_residents: bool, breakout_any_band: bool, min_touches: 1..10};
        # null resets to STRICT (the module defaults). Unknown keys rejected so
        # a typo cannot silently leave the engine strict.
        raw = payload.get("zone_edge_rules")
        if raw is None:
            updates["zone_edge_rules"] = {}
        elif isinstance(raw, dict):
            clean = {}
            for k, v in raw.items():
                if k in ("demand_residents", "breakout_any_band"):
                    if not isinstance(v, bool):
                        raise HTTPException(400, "zone_edge_rules.%s must be a boolean" % k)
                    clean[k] = v
                elif k == "min_touches":
                    if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 10:
                        raise HTTPException(400, "zone_edge_rules.min_touches must be an integer 1..10")
                    clean[k] = v
                else:
                    raise HTTPException(400, "zone_edge_rules: unknown key %r" % k)
            updates["zone_edge_rules"] = clean
        else:
            raise HTTPException(400, "zone_edge_rules must be an object or null")
    if not updates:
        raise HTTPException(400, "nothing to update — send equity_cap, "
                                 "auto_min_score, auto_min_rs, "
                                 "progressive_exposure, pyramiding, "
                                 "zone_edge_entry, zone_edge_rules and/or "
                                 "catalyst_entry")
    from trading import exit_engine

    def work():
        exit_engine.update_config(**updates)
        exit_engine.ledger("config_update",
                           detail=dict(updates, by=email))
        return updates

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


def _flatten_reason(payload) -> Optional[str]:
    """Optional owner reason from the flatten body ({"reason": str}); 400 on
    a non-string; capped by exit_engine.FLATTEN_REASON_MAX; None when
    absent/blank. The body itself is optional (the Exit button sends none)."""
    if payload is None or not isinstance(payload, dict) or "reason" not in payload:
        return None
    raw = payload.get("reason")
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise HTTPException(400, "reason must be a string")
    from trading import exit_engine
    return exit_engine._clean_reason(raw)


@router.get("/options")
async def trading_options(email: str = Depends(current_user_email)):
    """Options lane tab: status block, open / recent contracts, journal."""
    from trading import options_lane
    return JSONResponse(await asyncio.to_thread(options_lane.tab_payload))


@router.post("/options/close/{underlying}")
async def trading_options_close(underlying: str,
                                email: str = Depends(current_user_email)):
    """Owner closes the lane's position on one underlying now (armed only)."""
    _require_admin(email)
    from trading import options_lane
    try:
        result = await asyncio.to_thread(options_lane.close_now, underlying, "owner close")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return JSONResponse(result)


@router.post("/flatten/{symbol}")
async def trading_flatten(symbol: str,
                          payload: Optional[dict] = Body(default=None),
                          email: str = Depends(current_user_email)):
    """Cancel orders + close one position. Outside the session Alpaca can
    refuse the close (shares held for the pending-cancel orders): then the
    exit is QUEUED and the engine drains it every minute (flatten queue,
    2026-09-05) — the response says queued=true."""
    _require_admin(email)
    reason = _flatten_reason(payload)
    from trading import exit_engine
    try:
        result = await asyncio.to_thread(exit_engine.flatten, symbol, reason)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return JSONResponse(result)


@router.post("/flatten-queue/{symbol}/cancel")
async def trading_flatten_unqueue(symbol: str,
                                  email: str = Depends(current_user_email)):
    """Take a queued exit back: the engine will NOT sell it at the open. A
    sell Alpaca already accepted (state sent) is not cancelled here."""
    _require_admin(email)
    from trading import exit_engine
    try:
        ok = await asyncio.to_thread(exit_engine.unqueue_flatten, symbol)
        queue = await asyncio.to_thread(exit_engine.public_flatten_queue)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return JSONResponse({"unqueued": bool(ok), "flatten_queue": queue})


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


@router.get("/race")
async def trading_race(days: int = 5,
                       email: str = Depends(current_user_email)):
    """Execution race — engine vs owner, one row per zone-edge signal the
    engine attempted (blocked attempts included): signal time, engine order
    / fill, the owner's first view of the ticker page, his manual Portfolio
    fill, and the lags + price gaps between them. Reconciles first (read-only
    over every collection but execution_race)."""
    _require_admin(email)
    from trading import zone_edge_entry
    return JSONResponse(await asyncio.to_thread(
        zone_edge_entry.race_report, max(1, min(int(days or 5), 30))))


@router.get("/autopsies")
async def trading_autopsies(days: int = 30,
                            email: str = Depends(current_user_email)):
    """Failed-trade autopsies — every closed LOSING round-trip (zone-edge,
    Minervini or manual) classified by the OWNER rules in trading/autopsy.py
    with its numbers (lag, chase, stop requested vs placed, MFE/MAE, band
    held, reclaimed, SPY/RSP) and one feedback line, plus the summary and
    the rule table. Read-only: the docs are written by the engine tick."""
    _require_admin(email)
    from trading import autopsy
    return JSONResponse(await asyncio.to_thread(
        autopsy.report, max(1, min(int(days if days is not None else 30), 365))))


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
