"""Built-in SIMULATED broker — paper trading with NO external account.

Same duck-typed surface as the Alpaca client (configured/account/clock/
positions/open_orders/closed_orders_since/submit_bracket/submit_stop/
replace_order/cancel_order/close_position/latest_trade/make_client_order_id)
returning Alpaca-SHAPED dicts (id, client_order_id, symbol, side, type,
order_class, status, qty, filled_avg_price, filled_at, submitted_at,
stop_price, limit_price, legs[]), so exit_engine / entries / auto_entry run
unchanged. Selection happens in trading/broker.py (env TRADING_BROKER).

Fills come from the app's OWN real-time Massive quotes
(sepa.prices.bulk_live_prices — lazy import, this module stays pandas-free
at import time). State lives in three Mongo collections:

  sim_account    single doc {_id: "account", cash, starting_cash}
  sim_positions  one doc per symbol {symbol, qty, avg_entry_price}
  sim_orders     flat order docs; bracket legs carry parent_id + leg_kind

process_fills() is the matching engine — called at the top of every
exit_engine tick (hasattr-guarded duck call; the Alpaca module has no such
method because a real broker matches at the exchange).

Safety: the engine's armed=false invariant is upstream of this module —
disarmed, exit_engine/entries/auto_entry never call submit_* on ANY broker,
sim included. CLI: python -m trading.broker_sim reset
"""
from __future__ import annotations

import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Optional

# The shared error type + open-status set — engine code catches/reads these
# through trading.broker; importing them here keeps the two brokers in sync.
from trading.broker_alpaca import OPEN_STATUSES, BrokerError

log = logging.getLogger("trading.broker_sim")

# ── Honesty constants ───────────────────────────────────────────────────────
# SIM fills are evaluated ONCE PER ENGINE TICK (~1/minute via cron) against
# the latest Massive trade print — a between-tick move resolves at the NEXT
# tick. The sim is therefore COARSER than a real broker's matching: a stop
# touched and recovered inside a minute may not fill here, and a gap through
# the stop fills at stop x (1 - SIM_SLIPPAGE_PCT/100) where a real fill
# could be far worse. Paper results read through this sim are optimistic on
# timing and only mildly pessimistic on price.
SIM_STARTING_CASH = 5000.0   # mirrors auto_entry.DEFAULT_EQUITY_CAP ("assume you have 5k")
SIM_SLIPPAGE_PCT = 0.1       # stop fills price = stop x (1 - 0.1%) — pessimistic

TERMINAL_STATUSES = {"filled", "canceled"}


# ── Mongo + quote seams ─────────────────────────────────────────────────────

def _db():
    """exit_engine's lazy Mongo accessor, resolved at CALL time (lazy import
    breaks the trading.broker -> broker_sim -> exit_engine import cycle;
    exit_engine is pandas-free). Tests monkeypatch THIS function."""
    from trading.exit_engine import _db as engine_db
    return engine_db()


def _bulk_live(symbols: list) -> dict:
    """ONE batched Massive quote call (sepa.prices.bulk_live_prices). Lazy
    import — sepa.prices pulls pandas-adjacent deps; never at import time.
    Tests monkeypatch THIS seam with a controllable quote dict."""
    if not symbols:
        return {}
    try:
        from sepa.prices import bulk_live_prices
        return bulk_live_prices(list(symbols)) or {}
    except Exception as exc:                       # noqa: BLE001
        log.warning("broker_sim: bulk live prices failed: %s", exc)
        return {}


def _live_price_map(symbols: list) -> dict:
    """{SYM: float} from one _bulk_live call — same price preference order
    as entries._live_price (price -> last_trade_price -> prev_day_close)."""
    out = {}
    for sym, row in (_bulk_live(sorted(set(symbols))) or {}).items():
        row = row or {}
        px = (row.get("price") or row.get("last_trade_price")
              or row.get("prev_day_close"))
        try:
            px = float(px) if px else None
        except (TypeError, ValueError):
            px = None
        if px and px > 0:
            out[(sym or "").upper()] = px
    return out


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_et() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York"))
    except Exception:                              # noqa: BLE001
        return datetime.now().astimezone()


def _public(doc: Optional[dict]) -> Optional[dict]:
    if doc is None:
        return None
    out = dict(doc)
    out.pop("_id", None)
    return out


# ── Account / position state ────────────────────────────────────────────────

def _account_doc(db) -> dict:
    doc = db.sim_account.find_one({"_id": "account"})
    if doc is None:
        doc = {"_id": "account", "cash": SIM_STARTING_CASH,
               "starting_cash": SIM_STARTING_CASH, "created_at": _utc_iso()}
        db.sim_account.update_one({"_id": "account"}, {"$set": dict(doc)},
                                  upsert=True)
    return doc


def _set_cash(db, cash: float) -> None:
    db.sim_account.update_one({"_id": "account"},
                              {"$set": {"cash": round(float(cash), 2),
                                        "updated_at": _utc_iso()}},
                              upsert=True)


def _apply_fill_to_state(db, order: dict, price: float) -> None:
    """Cash + position bookkeeping for ONE fill (called exactly once per
    order — the caller guards the new->filled transition)."""
    sym = order["symbol"]
    qty = int(order["qty"])
    cash = float(_account_doc(db).get("cash") or 0.0)
    pos = db.sim_positions.find_one({"symbol": sym})
    if order["side"] == "buy":
        _set_cash(db, cash - qty * price)
        old_qty = int(float((pos or {}).get("qty") or 0))
        old_avg = float((pos or {}).get("avg_entry_price") or 0.0)
        new_qty = old_qty + qty
        new_avg = ((old_qty * old_avg + qty * price) / new_qty) if new_qty else price
        db.sim_positions.update_one(
            {"symbol": sym},
            {"$set": {"symbol": sym, "qty": new_qty,
                      "avg_entry_price": round(new_avg, 4),
                      "updated_at": _utc_iso()}},
            upsert=True)
    else:
        _set_cash(db, cash + qty * price)
        old_qty = int(float((pos or {}).get("qty") or 0))
        new_qty = old_qty - qty
        if new_qty > 0:
            db.sim_positions.update_one({"symbol": sym},
                                        {"$set": {"qty": new_qty,
                                                  "updated_at": _utc_iso()}})
        else:
            db.sim_positions.delete_one({"symbol": sym})


# ── Order state machine (forward-only transitions) ──────────────────────────

def _order(db, order_id: str) -> Optional[dict]:
    return db.sim_orders.find_one({"id": order_id})


def _is_working(doc: Optional[dict]) -> bool:
    return bool(doc) and (doc.get("status") or "").lower() in OPEN_STATUSES


def _set_status(db, order_id: str, status: str, **extra) -> bool:
    """new/held -> filled/canceled (or held -> new). Returns False when the
    order is already terminal — fills/cancels are idempotent, never repeated."""
    doc = _order(db, order_id)
    if doc is None or (doc.get("status") or "").lower() in TERMINAL_STATUSES:
        return False
    fields = {"status": status, "updated_at": _utc_iso()}
    fields.update(extra)
    db.sim_orders.update_one({"id": order_id}, {"$set": fields})
    return True


def _fill(db, doc: dict, price: float) -> bool:
    price = round(float(price), 4)
    if not _set_status(db, doc["id"], "filled",
                       filled_avg_price=price, filled_at=_utc_iso()):
        return False
    order = _order(db, doc["id"])
    _apply_fill_to_state(db, order, price)
    return True


def _activate_children(db, parent_id: str) -> None:
    """Parent entry filled -> held bracket legs go live (Alpaca: legs of a
    filled parent surface as top-level open orders)."""
    for child in list(db.sim_orders.find({"parent_id": parent_id,
                                          "status": "held"})):
        _set_status(db, child["id"], "new")


def _cancel_children(db, parent_id: str) -> None:
    for child in list(db.sim_orders.find({"parent_id": parent_id})):
        if _is_working(child):
            _set_status(db, child["id"], "canceled", canceled_at=_utc_iso())


def _cancel_siblings(db, doc: dict) -> list:
    """OCO: one bracket leg fills -> the other leg is canceled. Returns the
    canceled sibling ids."""
    parent_id = doc.get("parent_id")
    canceled = []
    if not parent_id:
        return canceled
    for sib in list(db.sim_orders.find({"parent_id": parent_id})):
        if sib.get("id") != doc.get("id") and _is_working(sib):
            if _set_status(db, sib["id"], "canceled", canceled_at=_utc_iso()):
                canceled.append(sib["id"])
    return canceled


def _new_order(db, *, symbol, side, otype, qty, order_class="",
               limit_price=None, stop_price=None, parent_id=None,
               leg_kind=None, client_order_id=None, tif="gtc",
               status="new") -> dict:
    if client_order_id and db.sim_orders.find_one(
            {"client_order_id": client_order_id}) is not None:
        raise BrokerError("sim: duplicate client_order_id %r (same-day "
                          "idempotency, mirrors Alpaca)" % client_order_id)
    doc = {
        "id": uuid.uuid4().hex,
        "client_order_id": client_order_id or ("sim-%s" % uuid.uuid4().hex[:12]),
        "symbol": (symbol or "").upper(),
        "side": side,
        "type": otype,
        "order_class": order_class,
        "status": status,
        "qty": str(int(qty)),
        "filled_avg_price": None,
        "filled_at": None,
        "submitted_at": _utc_iso(),
        "stop_price": (round(float(stop_price), 2)
                       if stop_price is not None else None),
        "limit_price": (round(float(limit_price), 2)
                        if limit_price is not None else None),
        "time_in_force": tif,
        "parent_id": parent_id,
        "leg_kind": leg_kind,
        "legs": None,
    }
    db.sim_orders.insert_one(dict(doc))
    return doc


def _require_db():
    db = _db()
    if db is None:
        raise BrokerError("sim broker: mongo unavailable")
    return db


def _whole_qty(qty) -> int:
    q = int(qty)
    if q <= 0 or q != float(qty):
        raise BrokerError("qty must be a positive whole number (got %r)" % (qty,))
    return q


# ── Duck-typed read surface ─────────────────────────────────────────────────

def configured() -> bool:
    """The sim broker needs no keys — always ready."""
    return True


def mode() -> str:
    return "sim"


def clock() -> dict:
    """Local ET market clock: weekday 9:30-16:00. NO holiday calendar — on a
    market holiday the sim believes the market is open but quotes barely
    move, so fills just don't happen (documented coarseness)."""
    now = _now_et()
    mins = now.hour * 60 + now.minute
    is_open = (now.weekday() < 5
               and (9 * 60 + 30) <= mins < (16 * 60))
    return {"is_open": is_open, "timestamp": now.isoformat()}


def account() -> dict:
    """equity = cash + sum(qty x live); buying_power = cash (no margin)."""
    db = _require_db()
    acct = _account_doc(db)
    cash = float(acct.get("cash") or 0.0)
    positions_rows = list(db.sim_positions.find())
    quotes = _live_price_map([p["symbol"] for p in positions_rows])
    market_value = 0.0
    for p in positions_rows:
        live = quotes.get(p["symbol"]) or float(p.get("avg_entry_price") or 0)
        market_value += int(float(p.get("qty") or 0)) * live
    equity = round(cash + market_value, 2)
    return {"equity": str(equity), "cash": str(round(cash, 2)),
            "buying_power": str(round(cash, 2)),
            "currency": "USD", "status": "ACTIVE", "sim": True,
            "starting_cash": acct.get("starting_cash", SIM_STARTING_CASH)}


def positions() -> list:
    """Alpaca /v2/positions shape (string numerics, avg_entry_price +
    current_price — exactly what exit_engine reads)."""
    db = _require_db()
    rows = list(db.sim_positions.find())
    quotes = _live_price_map([p["symbol"] for p in rows])
    out = []
    for p in rows:
        qty = int(float(p.get("qty") or 0))
        if qty <= 0:
            continue
        avg = float(p.get("avg_entry_price") or 0.0)
        live = quotes.get(p["symbol"]) or avg
        mv = round(qty * live, 2)
        upl = round((live - avg) * qty, 2)
        out.append({
            "symbol": p["symbol"], "qty": str(qty), "side": "long",
            "avg_entry_price": str(avg), "current_price": str(live),
            "market_value": str(mv), "unrealized_pl": str(upl),
            "unrealized_plpc": str(round((live / avg - 1), 6) if avg else 0),
        })
    return out


def _with_legs(db, doc: dict) -> dict:
    out = _public(doc)
    legs = [_public(c) for c in db.sim_orders.find({"parent_id": doc["id"]})]
    out["legs"] = legs or None
    return out


def open_orders(symbol: Optional[str] = None) -> list:
    """Mirrors Alpaca nested=true: working parents carry their legs[] nested;
    working legs of FILLED parents appear as top-level rows on their own."""
    db = _require_db()
    sym = (symbol or "").upper() or None
    out = []
    for o in db.sim_orders.find():
        if not _is_working(o):
            continue
        if sym and o.get("symbol") != sym:
            continue
        parent_id = o.get("parent_id")
        if not parent_id:
            out.append(_with_legs(db, o))
        else:
            parent = _order(db, parent_id)
            if parent is None or not _is_working(parent):
                out.append(_public(o))     # leg rides alone once parent filled
    return out


def closed_orders_since(iso_ts: str) -> list:
    """Terminal orders submitted after iso_ts, oldest first (Alpaca filters
    by SUBMITTED time — the exit engine compensates with its 14d lookback).
    Bracket legs appear as individual rows, order_class preserved, so the
    streak bookkeeping sees stop/take-profit fills directly."""
    db = _require_db()
    rows = [o for o in db.sim_orders.find()
            if (o.get("status") or "").lower() in TERMINAL_STATUSES
            and (o.get("submitted_at") or "") > (iso_ts or "")]
    rows.sort(key=lambda o: o.get("submitted_at") or "")
    return [_public(o) for o in rows[:500]]


def latest_trade(symbol: str) -> Optional[float]:
    return _live_price_map([(symbol or "").upper()]).get((symbol or "").upper())


def make_client_order_id(symbol: str, intent: str) -> str:
    """Same deterministic id as the Alpaca client: cheetah-{SYM}-{yyyymmdd
    ET}-{intent}; duplicates are rejected in _new_order (same-day
    idempotency)."""
    day = _now_et().strftime("%Y%m%d")
    return "cheetah-%s-%s-%s" % (symbol.upper(), day, intent)


# ── Duck-typed order surface ────────────────────────────────────────────────

def submit_bracket(symbol: str, qty: int, take_profit_price: float,
                   stop_price: float, limit_price: Optional[float] = None,
                   client_order_id: Optional[str] = None, tif: str = "gtc",
                   order_class: str = "bracket") -> dict:
    """Buy bracket: entry + take-profit limit + stop-loss legs. Legs start
    `held` and activate when the entry fills (Alpaca semantics)."""
    db = _require_db()
    q = _whole_qty(qty)
    if limit_price is None and not clock().get("is_open"):
        raise BrokerError("market order rejected: market is closed — "
                          "use a limit_price (GTC) instead")
    est_px = float(limit_price) if limit_price is not None else (
        latest_trade(symbol) or 0.0)
    cash = float(_account_doc(db).get("cash") or 0.0)
    if est_px and est_px * q > cash + 1e-9:
        raise BrokerError("sim: insufficient cash %.2f for %d x %.2f"
                          % (cash, q, est_px))
    parent = _new_order(db, symbol=symbol, side="buy",
                        otype="limit" if limit_price is not None else "market",
                        qty=q, order_class=order_class,
                        limit_price=limit_price,
                        client_order_id=client_order_id, tif=tif)
    _new_order(db, symbol=symbol, side="sell", otype="limit", qty=q,
               order_class=order_class, limit_price=take_profit_price,
               parent_id=parent["id"], leg_kind="take_profit", tif=tif,
               status="held")
    _new_order(db, symbol=symbol, side="sell", otype="stop", qty=q,
               order_class=order_class, stop_price=stop_price,
               parent_id=parent["id"], leg_kind="stop_loss", tif=tif,
               status="held")
    return _with_legs(db, _order(db, parent["id"]))


def submit_stop(symbol: str, qty: int, stop_price: float,
                client_order_id: Optional[str] = None) -> dict:
    """Standalone GTC sell-stop (adopt-and-protect)."""
    db = _require_db()
    doc = _new_order(db, symbol=symbol, side="sell", otype="stop",
                     qty=_whole_qty(qty), stop_price=stop_price,
                     client_order_id=client_order_id)
    return _public(doc)


def replace_order(order_id: str, stop_price: Optional[float] = None,
                  limit_price: Optional[float] = None) -> dict:
    """Move a working order's stop/limit (the breakeven-ratchet path). Same
    id is kept — simpler than Alpaca's replacement-id chain and invisible to
    the engine, which re-reads open_orders every tick."""
    db = _require_db()
    doc = _order(db, order_id)
    if doc is None:
        raise BrokerError("sim: order %s not found" % order_id)
    if not _is_working(doc):
        raise BrokerError("sim: order %s is %s — cannot replace"
                          % (order_id, doc.get("status")))
    fields = {}
    if stop_price is not None:
        fields["stop_price"] = round(float(stop_price), 2)
    if limit_price is not None:
        fields["limit_price"] = round(float(limit_price), 2)
    if not fields:
        raise BrokerError("replace_order: nothing to change")
    fields["updated_at"] = _utc_iso()
    db.sim_orders.update_one({"id": order_id}, {"$set": fields})
    return _public(_order(db, order_id))


def cancel_order(order_id: str) -> None:
    db = _require_db()
    doc = _order(db, order_id)
    if doc is None:
        raise BrokerError("sim: order %s not found" % order_id)
    _set_status(db, order_id, "canceled", canceled_at=_utc_iso())
    _cancel_children(db, order_id)     # canceling a parent kills its legs


def close_position(symbol: str) -> dict:
    """Market-sell the whole position NOW at the live Massive quote."""
    db = _require_db()
    sym = (symbol or "").upper()
    pos = db.sim_positions.find_one({"symbol": sym})
    qty = int(float((pos or {}).get("qty") or 0))
    if qty <= 0:
        raise BrokerError("sim: position does not exist: %s" % sym)
    live = latest_trade(sym)
    if not live:
        raise BrokerError("sim: no live quote for %s — cannot close" % sym)
    doc = _new_order(db, symbol=sym, side="sell", otype="market", qty=qty)
    _fill(db, doc, live)
    return _public(_order(db, doc["id"]))


# ── The matching engine ─────────────────────────────────────────────────────

def process_fills() -> dict:
    """Match every pending sim order against ONE batched Massive quote call.
    Called at the top of every exit_engine tick, BEFORE adopt/ratchet/streak,
    so a just-filled stop is seen the same tick. Idempotent: an order fills
    once; status transitions move only forward (new/held -> filled/canceled).

    Rules (evaluated against the latest trade print, once per tick):
      buy market           fill at live
      buy limit            live <= limit        -> fill at live
      bracket legs         held -> new when the parent entry fills
      sell stop            live <= stop_price   -> fill at stop x (1 - slip)
      sell limit (target)  live >= limit_price  -> fill at limit
      OCO                  one leg fills        -> sibling canceled
    """
    db = _db()
    if db is None:
        return {"ok": False, "reason": "mongo_unavailable",
                "checked": 0, "filled": [], "canceled": []}
    working = [o for o in db.sim_orders.find() if _is_working(o)]
    pos_syms = [p["symbol"] for p in db.sim_positions.find()]
    syms = sorted({o["symbol"] for o in working} | set(pos_syms))
    summary = {"ok": True, "checked": len(working), "filled": [],
               "canceled": [], "ts": _utc_iso()}
    if not working:
        return summary
    quotes = _live_price_map(syms)                 # the ONE bulk call

    # Pass 1 — pending BUY entries (market + limit); fills activate legs.
    for o in working:
        if o.get("side") != "buy" or o.get("status") == "held":
            continue
        live = quotes.get(o["symbol"])
        if not live:
            continue
        filled = False
        if o.get("type") == "market":
            filled = _fill(db, o, live)
        elif o.get("type") == "limit":
            lim = float(o.get("limit_price") or 0)
            if lim and live <= lim:
                filled = _fill(db, o, min(live, lim))
        if filled:
            summary["filled"].append({"id": o["id"], "symbol": o["symbol"],
                                      "side": "buy", "price":
                                      _order(db, o["id"]).get("filled_avg_price")})
            _activate_children(db, o["id"])

    # Pass 2 — ACTIVE sell stops/targets (re-read: legs may just have gone
    # live; a stop sitting below a just-filled entry won't trigger at the
    # same print unless the price is already at/below it).
    for o in list(db.sim_orders.find()):
        if (not _is_working(o) or o.get("side") != "sell"
                or o.get("status") == "held"):
            continue
        live = quotes.get(o["symbol"])
        if not live:
            continue
        filled = False
        price = None
        if o.get("type") == "stop":
            sp = float(o.get("stop_price") or 0)
            if sp and live <= sp:
                price = round(sp * (1 - SIM_SLIPPAGE_PCT / 100.0), 4)
                filled = _fill(db, o, price)
        elif o.get("type") == "limit":
            lim = float(o.get("limit_price") or 0)
            if lim and live >= lim:
                price = lim
                filled = _fill(db, o, price)
        if filled:
            summary["filled"].append({"id": o["id"], "symbol": o["symbol"],
                                      "side": "sell", "price": price})
            summary["canceled"].extend(_cancel_siblings(db, o))
    return summary


# ── Reset (drop state, restore starting cash) ───────────────────────────────

def reset() -> dict:
    """Drop sim_orders/sim_positions/sim_account and restore the starting
    cash. Exposed via POST /trading/sim-reset (admin, confirm=yes, sim-only)
    and `python -m trading.broker_sim reset`."""
    db = _require_db()
    for name in ("sim_orders", "sim_positions", "sim_account"):
        try:
            getattr(db, name).drop()
        except Exception as exc:                   # noqa: BLE001
            raise BrokerError("sim reset: drop %s failed: %s" % (name, exc))
    _account_doc(db)                               # re-seed starting cash
    try:                                           # lazy — avoids import cycle
        from trading.exit_engine import ledger
        ledger("sim_reset", detail={"starting_cash": SIM_STARTING_CASH})
    except Exception as exc:                       # noqa: BLE001
        log.warning("sim reset: ledger row failed: %s", exc)
    return {"ok": True, "cash": SIM_STARTING_CASH}


# ── CLI ─────────────────────────────────────────────────────────────────────

def _main(argv) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if not argv or argv[0] != "reset":
        print("usage: python -m trading.broker_sim reset")
        return 2
    out = reset()
    log.info("SIM broker reset: %s", out)
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
