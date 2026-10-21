"""Auto-Pilot entries — the ONLY code path that ever buys (invariant 1).

enter() submits a bracket order at the active broker — Alpaca or the
built-in Massive-quote sim, picked by trading.broker.get_broker() — (entry
+ take-profit + stop legs resting at the broker, invariant 2) sized/
stopped/targeted exclusively by
trading/risk_rules.py (TLSW pp.291-315, page-cited). preview() is the same
evaluation with NO order — pure math plus a blocked[] list for the UI.

Check order (each cite = the printed TLSW page):
  configured -> armed -> position count < MAX_POSITIONS (p.312) ->
  never average down (pp.304-305) -> earnings shield (<=7d) ->
  price -> market-hours (market orders only when open) ->
  size > 0 shares (p.312 + p.304 streak multiplier).
"""
from __future__ import annotations

import json
import logging
import math
from typing import Optional

from trading import risk_rules, safety_floor
from trading.broker import BrokerError, get_broker
from trading.exit_engine import _db, get_config, ledger, regime

broker = get_broker()    # module-level so tests can monkeypatch EN.broker

log = logging.getLogger("trading.entries")

EARNINGS_SHIELD_DAYS = 7      # block entries into a report inside this window

# Journal LANE tag on every entry row (Ajay 2026-09-05: "Keep the minervini
# entries but also make sure you have demand zone and catalyst based entries
# time to time and journal it appropriately"). The caller names its lane;
# anything unknown is journaled as manual — a bad tag must never block a buy.
STRATEGIES = ("minervini", "demand_zone", "breakout", "catalyst", "gajjala", "manual")
# The ONE lane that may waive the two safety-floor BLOCKS (Ajay 2026-10-20, the
# 🚩 Gajjala paper lane — its switch `gajjala_floors`, default ON = the house
# floors apply). floors="gg" from any other strategy is refused, never honoured.
FLOOR_WAIVER_STRATEGIES = ("gajjala",)
FLOORS = ("house", "gg")
# The p.312 five-position account ceiling (2026-10-21, BUILD_SPEC19 D3 — a
# Minervini rule, not GG's): ceiling="gg" turns that block into a warning, and is
# accepted only from a strategy in FLOOR_WAIVER_STRATEGIES (the same one lane).
CEILINGS = ("house", "gg")
# Order classes a lane plan may ask for (2026-10-21, BUILD_SPEC19 D7/D8d — GG "no
# fixed targets"): "oto" = the entry + its stop leg only, no take-profit; it
# needs a lane plan, carries no target_price and may be a market entry (the
# plan's `price` is then the planning price).
ORDER_CLASSES = ("bracket", "oto")
# entry_reason is a small JSON-safe dict; anything bigger is truncated so a
# runaway payload can never bloat the ledger row.
REASON_MAX_BYTES = 2048


def _strategy_tag(strategy) -> str:
    return strategy if isinstance(strategy, str) and strategy in STRATEGIES else "manual"


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
              stop_price: Optional[float] = None, *,
              sizing: Optional[dict] = None,
              target_price: Optional[float] = None,
              floors: str = "house",
              strategy: str = "manual",
              ceiling: str = "house",
              order_class: str = "bracket"):
    """Run every entry check WITHOUT raising. Returns (blocked, ctx).

    LANE PLAN (2026-10-20, the 🚩 Gajjala paper lane): `sizing` = {qty, basis,
    ...} with an explicit limit_price, stop_price and target_price is a lane
    that brings its OWN stop / target / size (GG's trade math). It bypasses
    only the book's stop, target and size math below — armed, the p.312
    position count, never-average-down, earnings, price and the safety floors
    all still apply. `floors="gg"` waives the two floor BLOCKS (kept as
    warnings + ctx["floor_blocks_waived"]) and is accepted only from a
    strategy in FLOOR_WAIVER_STRATEGIES. target_price without sizing is
    refused (the book lanes keep the book's target).

    2026-10-21 (BUILD_SPEC19 D3 / D7): `ceiling="gg"` (FLOOR_WAIVER_STRATEGIES
    only) turns the p.312 position-count block into a warning; a lane plan with
    `order_class="oto"` carries NO target (GG has no fixed target) and may omit
    limit_price (a market entry; `sizing["price"]` is the planning price, else the
    live price). The default bracket lane plan is unchanged.

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
           "regime": "normal", "market_cap": None, "warnings": [],
           "floor_blocks_waived": []}
    if not symbol:
        blocked.append("symbol required")

    lane = sizing is not None
    lane_ok = False
    if target_price is not None and not lane:
        blocked.append("target_price is only accepted with a lane sizing plan")
    if floors not in FLOORS:
        blocked.append("floors must be one of %s (got %r)" % (", ".join(FLOORS), floors))
    elif floors == "gg" and strategy not in FLOOR_WAIVER_STRATEGIES:
        blocked.append("floors='gg' is the 🚩 Gajjala lane's switch only")
    if ceiling not in CEILINGS:
        blocked.append("ceiling must be one of %s (got %r)" % (", ".join(CEILINGS), ceiling))
    elif ceiling == "gg" and strategy not in FLOOR_WAIVER_STRATEGIES:
        blocked.append("ceiling='gg' is the 🚩 Gajjala lane's rule only")
    oto = order_class == "oto"
    if order_class not in ORDER_CLASSES:
        blocked.append("order_class must be one of %s (got %r)" % (", ".join(ORDER_CLASSES), order_class))
    elif oto and not lane:
        blocked.append("order_class='oto' is only accepted with a lane sizing plan")
    if lane:
        lane_ok = True
        try:
            lane_qty = int(sizing.get("qty")) if isinstance(sizing, dict) else 0
        except (TypeError, ValueError):
            lane_qty = 0
        try:
            lim = float(limit_price) if limit_price is not None else None
            stp = float(stop_price) if stop_price is not None else None
            tgt = float(target_price) if target_price is not None else None
        except (TypeError, ValueError):
            lim = stp = tgt = None
        if lim is None and not oto:
            blocked.append("a lane plan needs a limit_price")
            lane_ok = False
        if stp is None:
            blocked.append("a lane plan needs a stop_price")
            lane_ok = False
        if tgt is None and not oto:
            blocked.append("a lane plan needs a target_price")
            lane_ok = False
        if oto and tgt is not None:
            blocked.append("an OTO lane plan carries no target_price")
            lane_ok = False
        if lane_ok and not oto and not (0 < stp < lim < tgt):
            blocked.append("a lane plan needs stop < limit < target (got %s / %s / %s)"
                           % (stp, lim, tgt))
            lane_ok = False
        if lane_qty < 1:
            blocked.append("a lane plan needs a whole qty >= 1")
            lane_ok = False
        if top_up:
            blocked.append("a lane plan never tops up a position")
            lane_ok = False

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
                full = ("portfolio full: %d/%d positions (p.312)"
                        % (len(positions), risk_rules.MAX_POSITIONS))
                if ceiling == "gg" and strategy in FLOOR_WAIVER_STRATEGIES:
                    ctx["warnings"].append("waived by the 🚩 lane (GG has no position ceiling): " + full)
                else:
                    blocked.append(full)
            acct = broker.account()
            ctx["equity"] = float(acct.get("equity") or 0)
            ctx["market_open"] = bool(broker.clock().get("is_open"))
        except BrokerError as exc:
            blocked.append("broker error: %s" % exc)

    # price — an explicit limit_price doubles as the planning price; an OTO lane
    # plan's market entry brings its own (the last trade the lane read)
    price, source = (float(limit_price), "requested") if limit_price else (None, None)
    if price is None and lane and oto and isinstance(sizing, dict):
        try:
            plan_px = float(sizing.get("price")) if sizing.get("price") is not None else None
        except (TypeError, ValueError):
            plan_px = None
        if plan_px and plan_px > 0:
            price, source = plan_px, "lane"
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
    #
    # 2026-10-20: the 🚩 Gajjala lane alone may pass floors="gg" (its owner
    # switch gajjala_floors=false) — the two blocks then ride as warnings and
    # on ctx["floor_blocks_waived"]; every other caller blocks exactly as before.
    fl = safety_floor.check(symbol, price)
    ctx["market_cap"] = fl["market_cap"]
    ctx["warnings"] = list(ctx["warnings"]) + list(fl["warnings"])
    if floors == "gg" and strategy in FLOOR_WAIVER_STRATEGIES:
        ctx["floor_blocks_waived"] = list(fl["blocked"])
        ctx["warnings"] += ["waived by gajjala_floors=false: " + b for b in fl["blocked"]]
    else:
        blocked.extend(fl["blocked"])

    # Absolute stop level -> requested percent at the planning price (see
    # the docstring). Refuse rather than clamp: the level is the plan.
    ctx["stop_level"] = None
    if stop_price is not None and price and not lane:
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

    if lane:
        # The lane's own plan, verbatim (GG's trade math): no book stop, no
        # 2:1 target, no streak / progressive multiplier, no equity_cap.
        lim_px = lim
        if lane_ok and oto:
            # OTO (BUILD_SPEC19 D7): the planning price is the limit or the lane's
            # last trade; the stop must sit under it; no target at all
            lim_px = lim if lim is not None else price
            if not lim_px or not (0 < stp < lim_px):
                blocked.append("an OTO lane plan needs 0 < stop < the entry price (got %s / %s)"
                               % (stp, lim_px))
                lane_ok = False
        if lane_ok:
            basis = str(sizing.get("basis") or "lane")
            ctx["equity_used"] = ctx["equity"]
            ctx["sizing"] = {"shares": lane_qty, "allocation": round(lane_qty * lim_px, 2),
                             "multiplier": 1.0, "basis": basis}
            ctx["stop_level"] = stp
            ctx["stop_plan"] = risk_rules.StopPlan(
                stop_pct=round((lim_px - stp) / lim_px * 100.0, 2), stop_price=stp,
                basis="lane:" + basis)
            ctx["target"] = (None if oto else
                             {"target_price": tgt,
                              "target_pct": round((tgt - lim_px) / lim_px * 100.0, 2),
                              "reward_risk": round((tgt - lim_px) / (lim_px - stp), 2)})
            ctx["breakeven_trigger"] = risk_rules.breakeven_trigger(lim_px, stp)
            ctx["equity_risk_pct"] = (round(lane_qty * (lim_px - stp) / ctx["equity"] * 100.0, 4)
                                      if ctx["equity"] else None)
        return blocked, ctx

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
          reason: Optional[dict] = None, *,
          target_price: Optional[float] = None,
          sizing: Optional[dict] = None,
          floors: str = "house",
          tif: str = "gtc",
          order_intent: str = "entry",
          ceiling: str = "house",
          order_class: str = "bracket") -> dict:
    """Place the bracket entry. Raises ValueError(reason) on any failed
    check; the API maps that to 400 {detail}. top_up=True is the pyramid
    add (see _evaluate) — the bracket covers ONLY the added shares; its own
    stop/target legs protect the tranche, and the p.308 breakeven ratchet
    keeps operating on the whole position via the exit engine. stop_price
    is an absolute stop LEVEL that wins over stop_pct (see _evaluate).
    strategy / reason (2026-09-05) are the journal LANE tag and the small
    why-dict the caller hands over; they change nothing about the checks or
    the order — they ride on the 'entry' ledger row for the journal's
    by_strategy split and the autopsy's strategy read.
    target_price / sizing / floors (2026-10-20) are the lane-plan seam (see
    _evaluate); tif / order_intent reach the broker (time in force, and the
    client_order_id intent so two lanes or two setups on one name never
    collide). The defaults leave the book path's order byte-for-byte.
    ceiling / order_class (2026-10-21, BUILD_SPEC19 D3 / D7): the 🚩 lane's
    p.312 waiver and its no-target OTO entry (see _evaluate); defaults unchanged."""
    blocked, ctx = _evaluate(symbol, limit_price=limit_price,
                             stop_pct=stop_pct, allow_earnings=allow_earnings,
                             top_up=top_up, stop_price=stop_price,
                             sizing=sizing, target_price=target_price,
                             floors=floors, strategy=strategy,
                             ceiling=ceiling, order_class=order_class)
    if blocked:
        raise ValueError("; ".join(blocked))

    sym = ctx["symbol"]
    price = ctx["price"]
    plan = ctx["stop_plan"]
    target = ctx["target"]
    qty = ctx["sizing"]["shares"]
    client_order_id = broker.make_client_order_id(sym, order_intent)

    # Stamp the venue (sim | paper | live) so the journal/analytics can label
    # and segment this fill by source (SIM track record vs live paper). Never
    # block a buy on a mode read — degrade to None (journal treats None as sim,
    # since every pre-Alpaca fill was the sim).
    try:
        broker_mode = broker.mode()
    except Exception:                              # noqa: BLE001
        broker_mode = None

    # tif is passed only when it is not the broker default ("gtc"), so the
    # book lanes' call stays exactly what it was.
    tif_kw = {} if tif == "gtc" else {"tif": tif}
    # OTO (BUILD_SPEC19 D7): no take-profit leg; order_class is passed only then
    if order_class == "oto":
        tif_kw["order_class"] = "oto"
    try:
        order = broker.submit_bracket(
            sym, qty,
            take_profit_price=(target or {}).get("target_price"),
            stop_price=plan.stop_price,
            limit_price=limit_price,
            client_order_id=client_order_id, **tif_kw)
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
        "target_price": (target or {}).get("target_price"),
        "target_pct": (target or {}).get("target_pct"),
        "reward_risk": (target or {}).get("reward_risk"),
        "breakeven_trigger": ctx["breakeven_trigger"],
        "equity_risk_pct": ctx["equity_risk_pct"],
        "regime": ctx["regime"], "earnings": ctx["earnings"],
        "allow_earnings": bool(allow_earnings),
        "top_up": bool(top_up),
        "strategy": _strategy_tag(strategy),
        "entry_reason": _safe_reason(reason),
        "tif": tif,
        "order_class": order_class,
        "ceiling": ceiling,
        "warnings": list(ctx.get("warnings") or []),
        "overrides": {"sizing": (str(sizing.get("basis") or "lane")
                                 if isinstance(sizing, dict) else None),
                      "target": ("none" if order_class == "oto" else
                                 "lane" if sizing is not None else None),
                      "floors": floors,
                      "floor_blocks_waived": list(ctx.get("floor_blocks_waived") or [])},
    }
    cite = "stop p.299/301/311; target p.301/311; size p.312; streak p.304; breakeven trigger p.308"
    if sizing is not None and isinstance(reason, dict) and isinstance(reason.get("cite"), str):
        cite = reason["cite"]
    ledger("entry", symbol=sym, detail=detail, dry_run=False, cite=cite)
    return {
        "order_id": order.get("id"),
        "client_order_id": client_order_id,
        "shares": qty,
        "stop": {"stop_pct": plan.stop_pct, "stop_price": plan.stop_price,
                 "basis": plan.basis},
        "target": target,
    }
