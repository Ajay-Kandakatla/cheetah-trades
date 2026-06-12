"""Auto-Pilot entries — the ONLY code path that ever buys (invariant 1).

enter() submits a bracket order at Alpaca (entry + take-profit + stop legs
resting at the broker, invariant 2) sized/stopped/targeted exclusively by
trading/risk_rules.py (TLSW pp.291-315, page-cited). preview() is the same
evaluation with NO order — pure math plus a blocked[] list for the UI.

Check order (each cite = the printed TLSW page):
  configured -> armed -> position count < MAX_POSITIONS (p.312) ->
  never average down (pp.304-305) -> earnings shield (<=7d) ->
  price -> market-hours (market orders only when open) ->
  size > 0 shares (p.312 + p.304 streak multiplier).
"""
from __future__ import annotations

import logging
from typing import Optional

from trading import broker_alpaca as broker
from trading import risk_rules
from trading.broker_alpaca import BrokerError
from trading.exit_engine import _db, get_config, ledger, regime

log = logging.getLogger("trading.entries")

EARNINGS_SHIELD_DAYS = 7      # block entries into a report inside this window


def _closed_trade_stats():
    """(avg winning gain pct, total closed trades) from the ledger's
    trade_closed rows — feeds initial_stop's half-average-gain rule (p.299:
    "if your winning trades produce a gain of 15 percent on average, you
    should sell any declining stock at no more than 7.5 percent")."""
    db = _db()
    if db is None:
        return None, 0
    try:
        rows = list(db.trade_ledger.find({"kind": "trade_closed",
                                          "dry_run": {"$ne": True}},
                                         {"detail.gain_pct": 1}))
    except Exception as exc:                       # noqa: BLE001
        log.debug("closed-trade stats unavailable: %s", exc)
        return None, 0
    gains = []
    for r in rows:
        g = (r.get("detail") or {}).get("gain_pct")
        if g is not None:
            try:
                gains.append(float(g))
            except (TypeError, ValueError):
                pass
    winners = [g for g in gains if g > 0]
    avg = round(sum(winners) / len(winners), 2) if winners else None
    return avg, len(gains)


def _live_price(symbol: str):
    """(price, source). sepa.prices first (lazy — pulls pandas), Alpaca
    latest trade as the fallback."""
    try:
        from sepa.prices import bulk_live_prices
        row = (bulk_live_prices([symbol]) or {}).get(symbol) or {}
        px = row.get("price") or row.get("last_trade_price") or row.get("prev_day_close")
        if px:
            return float(px), "sepa.prices"
    except Exception as exc:                       # noqa: BLE001
        log.debug("live price via sepa.prices failed for %s: %s", symbol, exc)
    try:
        px = broker.latest_trade(symbol)
        if px:
            return float(px), "alpaca_latest_trade"
    except Exception as exc:                       # noqa: BLE001
        log.debug("live price via alpaca failed for %s: %s", symbol, exc)
    return None, None


def _evaluate(symbol: str, limit_price: Optional[float] = None,
              stop_pct: Optional[float] = None,
              allow_earnings: bool = False):
    """Run every entry check WITHOUT raising. Returns (blocked, ctx)."""
    symbol = (symbol or "").strip().upper()
    blocked = []
    ctx = {"symbol": symbol, "price": None, "price_source": None,
           "market_open": False, "equity": 0.0, "equity_used": 0.0,
           "equity_cap": None, "earnings": None,
           "sizing": None, "stop_plan": None, "target": None,
           "breakeven_trigger": None, "equity_risk_pct": None,
           "regime": "normal"}
    if not symbol:
        blocked.append("symbol required")

    if not broker.configured():
        blocked.append("Alpaca not configured (set ALPACA_KEY_ID / ALPACA_SECRET_KEY)")

    cfg = get_config()
    ctx["cfg"] = cfg
    if not cfg["armed"]:
        blocked.append("engine disarmed — entries require armed=true "
                       "(POST /trading/arm?armed=true)")

    held = None
    if broker.configured() and symbol:
        try:
            positions = broker.positions()
            for p in positions:
                if (p.get("symbol") or "").upper() == symbol:
                    held = p
            if held is None and len(positions) >= risk_rules.MAX_POSITIONS:
                blocked.append("portfolio full: %d/%d positions (p.312)"
                               % (len(positions), risk_rules.MAX_POSITIONS))
            acct = broker.account()
            ctx["equity"] = float(acct.get("equity") or 0)
            ctx["market_open"] = bool(broker.clock().get("is_open"))
        except BrokerError as exc:
            blocked.append("broker error: %s" % exc)

    # price — an explicit limit_price doubles as the planning price
    price, source = (float(limit_price), "requested") if limit_price else (None, None)
    if price is None and symbol:
        price, source = _live_price(symbol)
    if not price or price <= 0:
        blocked.append("no price available for %s" % (symbol or "?"))
        price = None
    ctx["price"], ctx["price_source"] = price, source

    # never average down (pp.304-305); add only when in profit (p.307/308)
    if held is not None and price:
        try:
            avg_cost = float(held.get("avg_entry_price") or 0)
        except (TypeError, ValueError):
            avg_cost = 0.0
        if avg_cost and not risk_rules.may_add_to_position(avg_cost, price):
            blocked.append("never average down — %s at %.2f is not above avg "
                           "cost %.2f (pp.304-305)" % (symbol, price, avg_cost))

    # earnings shield
    try:
        from sepa.earnings_watch import next_event
        ev = next_event(symbol) if symbol else None
        if ev:
            ctx["earnings"] = {"next_date": ev.get("date"),
                               "days_to": ev.get("days_to")}
    except Exception as exc:                       # noqa: BLE001
        log.debug("earnings shield unavailable for %s: %s", symbol, exc)
    ew = ctx["earnings"]
    if (ew and ew.get("days_to") is not None
            and ew["days_to"] <= EARNINGS_SHIELD_DAYS and not allow_earnings):
        blocked.append("earnings in %dd (%s) — pass allow_earnings=true to "
                       "override" % (ew["days_to"], ew.get("next_date")))

    # market orders only while the clock says open; limits are GTC anytime
    if limit_price is None and not ctx["market_open"]:
        blocked.append("market closed — market entries blocked; provide "
                       "limit_price for a GTC limit")

    # math (all of it from risk_rules — never re-derived).
    # Sizing equity = min(Alpaca equity, trading_config.equity_cap) for ALL
    # entries (manual + auto): the cap is what makes "assume you have 5k"
    # true on a $100k Alpaca paper account (auto_entry.DEFAULT_EQUITY_CAP).
    reg = regime()
    ctx["regime"] = reg
    try:
        cap = float(cfg.get("equity_cap") or 0)
    except (TypeError, ValueError):
        cap = 0.0
    ctx["equity_cap"] = cap or None
    ctx["equity_used"] = min(ctx["equity"], cap) if cap > 0 else ctx["equity"]
    if price:
        sizing = risk_rules.position_size(ctx["equity_used"], price,
                                          cfg["consecutive_losses"])
    else:
        sizing = {"shares": 0, "allocation": 0.0,
                  "multiplier": risk_rules.size_multiplier(cfg["consecutive_losses"])}
    ctx["sizing"] = sizing
    if sizing["shares"] <= 0:
        blocked.append("position size is 0 shares (equity used %.2f of %.2f, "
                       "cap %s, multiplier %.2f after %d consecutive losses "
                       "— p.304/p.312)"
                       % (ctx["equity_used"], ctx["equity"],
                          ctx["equity_cap"], sizing["multiplier"],
                          cfg["consecutive_losses"]))

    if price:
        try:
            avg_gain, n_closed = _closed_trade_stats()
            plan = risk_rules.initial_stop(price, reg, avg_gain_pct=avg_gain,
                                           closed_trades=n_closed,
                                           requested_pct=stop_pct)
            ctx["stop_plan"] = plan
            ctx["target"] = risk_rules.profit_target(price, plan.stop_pct, reg)
            ctx["breakeven_trigger"] = risk_rules.breakeven_trigger(
                price, plan.stop_price)
            ctx["equity_risk_pct"] = risk_rules.equity_risk_pct(
                plan.stop_pct,
                position_fraction=risk_rules.MAX_POSITION_FRACTION * sizing["multiplier"])
        except ValueError as exc:
            blocked.append("risk math: %s" % exc)

    return blocked, ctx


def preview(symbol: str, price: Optional[float] = None,
            stop_pct: Optional[float] = None) -> dict:
    """GET /trading/preview payload — pure math, NO order, blocked[] lists
    every failed check instead of raising."""
    blocked, ctx = _evaluate(symbol, limit_price=price, stop_pct=stop_pct,
                             allow_earnings=False)
    plan = ctx["stop_plan"]
    sizing = ctx["sizing"] or {"shares": 0, "allocation": 0.0, "multiplier": 1.0}
    return {
        "symbol": ctx["symbol"],
        "price": ctx["price"],
        "price_source": ctx["price_source"],
        "shares": sizing["shares"],
        "allocation": sizing["allocation"],
        "size_multiplier": sizing["multiplier"],
        "equity_used": ctx["equity_used"],
        "equity_cap": ctx["equity_cap"],
        "stop": ({"stop_pct": plan.stop_pct, "stop_price": plan.stop_price,
                  "basis": plan.basis} if plan else None),
        "target": ctx["target"],
        "breakeven_trigger": ctx["breakeven_trigger"],
        "equity_risk_pct": ctx["equity_risk_pct"],
        "regime": ctx["regime"],
        "market_open": ctx["market_open"],
        "earnings": ctx["earnings"],
        "blocked": blocked,
    }


def enter(symbol: str, limit_price: Optional[float] = None,
          stop_pct: Optional[float] = None,
          allow_earnings: bool = False) -> dict:
    """Place the bracket entry. Raises ValueError(reason) on any failed
    check; the API maps that to 400 {detail}."""
    blocked, ctx = _evaluate(symbol, limit_price=limit_price,
                             stop_pct=stop_pct, allow_earnings=allow_earnings)
    if blocked:
        raise ValueError("; ".join(blocked))

    sym = ctx["symbol"]
    price = ctx["price"]
    plan = ctx["stop_plan"]
    target = ctx["target"]
    qty = ctx["sizing"]["shares"]
    client_order_id = broker.make_client_order_id(sym, "entry")

    try:
        order = broker.submit_bracket(
            sym, qty,
            take_profit_price=target["target_price"],
            stop_price=plan.stop_price,
            limit_price=limit_price,
            client_order_id=client_order_id)
    except BrokerError as exc:
        raise ValueError(str(exc))

    detail = {
        "order_id": order.get("id"), "client_order_id": client_order_id,
        "qty": qty, "price": price, "price_source": ctx["price_source"],
        "limit_price": limit_price, "allocation": ctx["sizing"]["allocation"],
        "equity_used": ctx["equity_used"], "equity_cap": ctx["equity_cap"],
        "size_multiplier": ctx["sizing"]["multiplier"],
        "consecutive_losses": ctx["cfg"]["consecutive_losses"],
        "stop_price": plan.stop_price, "stop_pct": plan.stop_pct,
        "stop_basis": plan.basis,
        "target_price": target["target_price"], "target_pct": target["target_pct"],
        "reward_risk": target["reward_risk"],
        "breakeven_trigger": ctx["breakeven_trigger"],
        "equity_risk_pct": ctx["equity_risk_pct"],
        "regime": ctx["regime"], "earnings": ctx["earnings"],
        "allow_earnings": bool(allow_earnings),
    }
    ledger("entry", symbol=sym, detail=detail, dry_run=False,
           cite="stop p.299/301/311; target p.301/311; size p.312; "
                "streak p.304; breakeven trigger p.308")
    return {
        "order_id": order.get("id"),
        "shares": qty,
        "stop": {"stop_pct": plan.stop_pct, "stop_price": plan.stop_price,
                 "basis": plan.basis},
        "target": target,
    }
