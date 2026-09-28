"""Auto-Pilot entries — the ONLY code path that ever buys (invariant 1).

enter() submits a bracket order at the active broker — Alpaca or the
built-in Massive-quote sim, picked by trading.broker.get_broker() — (entry
+ take-profit + stop legs resting at the broker, invariant 2) sized/
stopped/targeted exclusively by
trading/risk_rules.py (TLSW pp.291-315, page-cited). preview() is the same
evaluation with NO order — pure math plus a blocked[] list for the UI.

Check order (each cite = the printed TLSW page):
  configured -> armed -> in-flight open cap (positions + pending buys, option
  spreads included; MAX_POSITIONS p.312, or the paper program's
  program_caps.PROGRAM_MAX_OPEN while it is ON), one lane per name, one entry
  per minute (trading/program_caps.py, 2026-09-27) -> never average down
  (pp.304-305) -> earnings shield (<=7d) -> price -> market-hours (market
  orders only when open) -> size > 0 shares (p.312 + p.304 streak multiplier;
  min-composed with the program's 0.25% risk budget while it is ON).
"""
from __future__ import annotations

import json
import logging
import math
from typing import Optional

from trading import program_caps, risk_rules, safety_floor
from trading import strategy_tags
from trading.broker import BrokerError, get_broker
from trading.exit_engine import _db, get_config, ledger, regime

broker = get_broker()    # module-level so tests can monkeypatch EN.broker

log = logging.getLogger("trading.entries")

EARNINGS_SHIELD_DAYS = 7      # block entries into a report inside this window

# Journal LANE tag on every entry row (Ajay 2026-09-05: "Keep the minervini
# entries but also make sure you have demand zone and catalyst based entries
# time to time and journal it appropriately"). The caller names its lane;
# anything unknown is journaled as manual — a bad tag must never block a buy
# (2026-09-27: except a not-a-lane tab, which is refused, and an unknown tag
# still takes the one-entry-per-minute slot; only an explicit manual is exempt).
STRATEGIES = ("minervini", "demand_zone", "breakout", "catalyst", "manual")
# Chart Maps lane program (2026-09-27): every generic lane's sid plus the two
# existing lanes whose tags used to be coerced to manual (hot_pullback,
# quick_bounce), and the two options lanes' tags. The literal tuple above
# stays the historical five (pinned).
STRATEGIES_ALL = STRATEGIES + strategy_tags.PROGRAM_TAGS + ("zero_dte", "options_zone")
# entry_reason is a small JSON-safe dict; anything bigger is truncated so a
# runaway payload can never bloat the ledger row.
REASON_MAX_BYTES = 2048


def _strategy_tag(strategy) -> str:
    return strategy if isinstance(strategy, str) and strategy in STRATEGIES_ALL else "manual"


def _mode() -> str:
    """"sim" | "paper" | "live" of THIS module's broker (duck-called so test
    fakes without mode() read ALPACA_PAPER like exit_engine does)."""
    m = getattr(broker, "mode", None)
    if callable(m):
        try:
            return str(m())
        except Exception:                          # noqa: BLE001
            pass
    import os
    return "live" if (os.getenv("ALPACA_PAPER", "1") or "1").strip() == "0" else "paper"


def _json_clean(v):
    """Recursively JSON-safe: NaN/inf -> None, non-JSON leaves -> str."""
    if isinstance(v, dict):
        return {str(k): _json_clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_json_clean(x) for x in v]
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return v
    if isinstance(v, (int, float)):
        f = float(v)
        return None if (f != f or math.isinf(f)) else v
    return str(v)


def _safe_reason(reason) -> Optional[dict]:
    """The entry_reason the ledger/journal carry: a JSON-safe dict capped at
    REASON_MAX_BYTES (a truncated marker + preview past that). None for
    anything that is not a dict."""
    if not isinstance(reason, dict):
        return None
    clean = _json_clean(reason)
    try:
        text = json.dumps(clean, allow_nan=False, default=str)
    except (TypeError, ValueError):
        return {"truncated": True, "preview": str(clean)[:REASON_MAX_BYTES]}
    if len(text) > REASON_MAX_BYTES:
        return {"truncated": True, "preview": text[:REASON_MAX_BYTES]}
    return clean


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
              allow_earnings: bool = False,
              top_up: bool = False,
              stop_price: Optional[float] = None,
              strategy: str = "manual"):
    """Run every entry check WITHOUT raising. Returns (blocked, ctx).

    strategy (2026-09-27) is the journal lane tag; trading/program_caps.check
    applies the in-flight open cap, the pending-entry and one-lane-per-name
    rules and the minute peek for it, and — while the paper program is ON —
    the per-strategy caps and the 0.25% risk budget. preview() passes none
    (= manual).

    top_up=True is the PYRAMID path (TTLAC §3 Add and Reduce / §5 scale-up,
    TLSW pp.307-308): size = full-position shares MINUS shares already held,
    so an add can only ever complete the position toward the same p.312
    25%-of-equity ceiling — never past it. Requires an existing position;
    never-average-down (pp.304-305) still applies on top.

    stop_price is an ABSOLUTE stop level (2026-09-05, zone-edge entries):
    the caller decided a price — a band floor — not a percent of whatever
    the tape prints at order time. It is converted to the requested percent
    AT THE PLANNING PRICE (so the placed stop is that level, on the cent
    grid) and takes precedence over stop_pct. It is refused, never clamped,
    when the level is not below the entry or sits past ABS_MAX_STOP_PCT —
    a clamp would move the stop back up into the structure the strategy is
    buying. risk_rules' own floor still applies (a level tighter than its
    minimum is widened, i.e. placed lower — safer, never higher)."""
    symbol = (symbol or "").strip().upper()
    blocked = []
    ctx = {"symbol": symbol, "price": None, "price_source": None,
           "market_open": False, "equity": 0.0, "equity_used": 0.0,
           "equity_cap": None, "earnings": None,
           "sizing": None, "stop_plan": None, "target": None,
           "breakeven_trigger": None, "equity_risk_pct": None,
           "regime": "normal", "market_cap": None, "warnings": []}
    if not symbol:
        blocked.append("symbol required")

    if not broker.configured():
        blocked.append("Alpaca not configured (set ALPACA_KEY_ID / ALPACA_SECRET_KEY)")

    cfg = get_config()
    ctx["cfg"] = cfg
    if not cfg["armed"]:
        blocked.append("engine disarmed — entries require armed=true "
                       "(POST /trading/arm?armed=true)")

    tag = _strategy_tag(strategy)
    mode = _mode()
    ctx["strategy"], ctx["mode"] = tag, mode
    ctx["program"] = program_caps.enabled(cfg, mode)
    held = None
    positions = []
    inf = None
    if broker.configured() and symbol:
        try:
            positions = broker.positions()
            for p in positions:
                if (p.get("symbol") or "").upper() == symbol:
                    held = p
            try:
                inf = program_caps.inflight(broker)
            except BrokerError:
                inf = None
                blocked.append("broker error: open orders unreadable — entry refused "
                               "(in-flight cap fails closed)")
            if inf is not None:
                blocked += program_caps.check(tag, symbol, brk=broker, cfg=cfg, mode=mode,
                                              held=held is not None, inf=inf)
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

    # Manipulation-safety floors (trading/safety_floor.py). THIS is the
    # chokepoint: every stock lane — minervini auto-entry, demand-zone,
    # zone-edge, hot-pullback, catalyst, manual — reaches the broker through
    # _evaluate, so the floors belong here and nowhere else. Ajay 2026-09-11:
    # "make sure to give me not penny stocks and other safety gates or warn
    # me.. I dont want 10 Million Market Cap stocks too". A known-small cap
    # and a sub-$2 quote BLOCK; an unknown cap and a thin tape WARN.
    floors = safety_floor.check(symbol, price)
    blocked.extend(floors["blocked"])
    ctx["market_cap"] = floors["market_cap"]
    ctx["warnings"] = list(floors["warnings"])

    # Absolute stop level -> requested percent at the planning price (see
    # the docstring). Refuse rather than clamp: the level is the plan.
    ctx["stop_level"] = None
    if stop_price is not None and price:
        try:
            level = float(stop_price)
        except (TypeError, ValueError):
            level = 0.0
        dist = ((price - level) / price * 100.0) if level > 0 else None
        if dist is None or dist <= 0:
            blocked.append("requested stop %.2f is not below the entry price "
                           "%.2f" % (level, price))
        elif dist > risk_rules.ABS_MAX_STOP_PCT:
            blocked.append("requested stop %.2f is %.2f%% under the entry price "
                           "%.2f — past the %g%% line (the print moved away "
                           "from the level; not clamping the stop up into it)"
                           % (level, dist, price, risk_rules.ABS_MAX_STOP_PCT))
        else:
            stop_pct = dist
            ctx["stop_level"] = level

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
    # Progressive-exposure governor (TLSW pp.307-308 pilot buys; see
    # trading/progressive.py) — pilot-size until the last few closed trades
    # are profitable on balance. min()-composes with the p.304 streak
    # multiplier inside position_size.
    from trading import progressive
    prog_mult, prog_detail = progressive.multiplier(_db(), cfg)
    ctx["progressive"] = prog_detail
    if price:
        sizing = risk_rules.position_size(ctx["equity_used"], price,
                                          cfg["consecutive_losses"],
                                          extra_multiplier=prog_mult)
    else:
        sizing = {"shares": 0, "allocation": 0.0,
                  "multiplier": min(
                      risk_rules.size_multiplier(cfg["consecutive_losses"]),
                      prog_mult)}
    # Pyramid top-up (TTLAC §3/§5): the add completes the position to the
    # SAME full-size allocation — full shares minus what's already held.
    # A position already at (or past) full size adds 0 -> blocked. Note the
    # progressive governor composes here for free: while the account is
    # unproven, "full" IS the pilot size, so a pilot can only top up AFTER
    # the last-5 read turns positive — exactly §5's "on the heels of wins".
    if top_up:
        if held is None:
            blocked.append("top-up requested but no %s position is held"
                           % (symbol or "?"))
        else:
            try:
                held_qty = int(float(held.get("qty") or 0))
            except (TypeError, ValueError):
                held_qty = 0
            full_shares = int(sizing["shares"])
            add_shares = max(0, full_shares - held_qty)
            if price:
                sizing = {"shares": add_shares,
                          "allocation": round(add_shares * price, 2),
                          "multiplier": sizing["multiplier"]}
            if add_shares <= 0:
                blocked.append("already at full size — %d held vs %d full "
                               "(p.312 ceiling; adds only complete the "
                               "position, never exceed it)"
                               % (held_qty, full_shares))
    ctx["sizing"] = sizing
    if sizing["shares"] <= 0 and not top_up:
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

    # Paper program risk budget (2026-09-27, "Small: 0.25% risk"): shares at
    # risk = PROGRAM_RISK_PCT of equity used over the PLACED stop distance,
    # min-composed with position_size — never larger, so the streak and
    # pilot multipliers still bind.
    rb = program_caps.risk_budget(tag, cfg, mode)
    ctx["risk_budget"] = None
    plan = ctx.get("stop_plan")
    if rb is not None and price and plan is not None and not top_up:
        per_share = round(price - plan.stop_price, 4)
        eq_used = ctx["equity_used"]
        if per_share > 0 and eq_used > 0:
            risk_shares = int(math.floor(eq_used * rb / 100.0 / per_share))
            shares = min(int(ctx["sizing"]["shares"]), risk_shares)
            ctx["sizing"] = {"shares": shares, "allocation": round(shares * price, 2),
                             "multiplier": ctx["sizing"]["multiplier"]}
            ctx["risk_budget"] = {"pct": rb, "usd": round(eq_used * rb / 100.0, 2),
                                  "per_share": per_share, "shares_by_risk": risk_shares}
            ctx["equity_risk_pct"] = round(shares * per_share / eq_used * 100.0, 4)
            if shares <= 0:
                blocked.append("position size 0 at %.2f%% risk ($%.2f) with a %.2f/share stop"
                               % (rb, eq_used * rb / 100.0, per_share))
        else:
            blocked.append("position size 0 at %.2f%% risk: no stop distance" % rb)
    if ctx["program"] and price and ctx["sizing"] and inf is not None:
        ok, why = program_caps.gross_ok(positions=positions,
                                        pending_notional=inf["pending_notional"],
                                        add_usd=ctx["sizing"]["shares"] * price,
                                        equity_used=ctx["equity_used"], cfg=cfg, mode=mode)
        if not ok:
            blocked.append(why)

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
        "progressive": ctx.get("progressive"),
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
        "market_cap": ctx["market_cap"],
        "blocked": blocked,
        "warnings": ctx["warnings"],
    }


def enter(symbol: str, limit_price: Optional[float] = None,
          stop_pct: Optional[float] = None,
          allow_earnings: bool = False,
          top_up: bool = False,
          stop_price: Optional[float] = None,
          strategy: str = "manual",
          reason: Optional[dict] = None) -> dict:
    """Place the bracket entry. Raises ValueError(reason) on any failed
    check; the API maps that to 400 {detail}. top_up=True is the pyramid
    add (see _evaluate) — the bracket covers ONLY the added shares; its own
    stop/target legs protect the tranche, and the p.308 breakeven ratchet
    keeps operating on the whole position via the exit engine. stop_price
    is an absolute stop LEVEL that wins over stop_pct (see _evaluate).
    strategy / reason (2026-09-05) are the journal LANE tag and the small
    why-dict the caller hands over; they change nothing about the checks or
    the order — they ride on the 'entry' ledger row for the journal's
    by_strategy split and the autopsy's strategy read."""
    # A not-a-lane tab (vcp, topping, support, ...) never buys, in any mode —
    # refused here, before the tag is coerced to manual below.
    if strategy_tags.is_not_a_lane(strategy):
        raise ValueError("program-cap: %s is not a lane (never buys)"
                         % strategy_tags.norm(strategy))
    tag = _strategy_tag(strategy)
    # The minute tag: only an explicit manual (or no tag) is exempt. An
    # unknown tag is still JOURNALED as manual, but it claims the minute like
    # any lane, so a typo can never skip the one-entry-per-minute rule.
    minute_tag = ("manual" if strategy is None or strategy == "manual"
                  else tag if tag != "manual" else str(strategy))
    # One entry per ET minute (program_caps, every mode, manual exempt): a
    # lane that cannot win the minute makes no broker, quote or earnings read.
    if minute_tag != "manual":
        why = program_caps.minute_taken_reason(program_caps.minute_taken())
        if why:
            raise ValueError(why)
    blocked, ctx = _evaluate(symbol, limit_price=limit_price,
                             stop_pct=stop_pct, allow_earnings=allow_earnings,
                             top_up=top_up, stop_price=stop_price, strategy=tag)
    if blocked:
        raise ValueError("; ".join(blocked))

    sym = ctx["symbol"]
    # The atomic claim, AFTER every check passed and BEFORE the order. A
    # claimed minute whose submit then fails stays claimed (fails closed).
    ok, why = program_caps.claim(minute_tag, sym)
    if not ok:
        raise ValueError(why)
    price = ctx["price"]
    plan = ctx["stop_plan"]
    target = ctx["target"]
    qty = ctx["sizing"]["shares"]
    client_order_id = broker.make_client_order_id(sym, "entry")

    # Stamp the venue (sim | paper | live) so the journal/analytics can label
    # and segment this fill by source (SIM track record vs live paper). Never
    # block a buy on a mode read — degrade to None (journal treats None as sim,
    # since every pre-Alpaca fill was the sim).
    try:
        broker_mode = broker.mode()
    except Exception:                              # noqa: BLE001
        broker_mode = None

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
        "mode": broker_mode,
        "qty": qty, "price": price, "price_source": ctx["price_source"],
        "limit_price": limit_price, "allocation": ctx["sizing"]["allocation"],
        "equity_used": ctx["equity_used"], "equity_cap": ctx["equity_cap"],
        "size_multiplier": ctx["sizing"]["multiplier"],
        "consecutive_losses": ctx["cfg"]["consecutive_losses"],
        "stop_price": plan.stop_price, "stop_pct": plan.stop_pct,
        "stop_basis": plan.basis, "stop_level_requested": ctx["stop_level"],
        "target_price": target["target_price"], "target_pct": target["target_pct"],
        "reward_risk": target["reward_risk"],
        "breakeven_trigger": ctx["breakeven_trigger"],
        "equity_risk_pct": ctx["equity_risk_pct"],
        "regime": ctx["regime"], "earnings": ctx["earnings"],
        "allow_earnings": bool(allow_earnings),
        "top_up": bool(top_up),
        "strategy": tag,
        "entry_reason": _safe_reason(reason),
        "risk_budget": ctx.get("risk_budget"),
        "program": bool(ctx.get("program")),
        "sid": strategy_tags.norm(tag),
    }
    ledger("entry", symbol=sym, detail=detail, dry_run=False,
           cite="stop p.299/301/311; target p.301/311; size p.312; "
                "streak p.304; breakeven trigger p.308")
    program_caps.record_entry(tag, sym, asset="stock", order_id=order.get("id"),
                              client_order_id=client_order_id,
                              snapshot_ref=(reason or {}).get("snapshot_ref")
                              if isinstance(reason, dict) else None)
    return {
        "order_id": order.get("id"),
        "shares": qty,
        "stop": {"stop_pct": plan.stop_pct, "stop_price": plan.stop_price,
                 "basis": plan.basis},
        "target": target,
    }
