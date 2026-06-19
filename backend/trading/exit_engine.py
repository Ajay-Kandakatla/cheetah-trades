"""Auto-Pilot exit engine — the reconciler that keeps every Alpaca position
protected per Minervini TLSW pp.291-315. All math comes from
trading/risk_rules.py (page-cited, hand-verified); nothing is re-derived here.

Each tick:
  adopt-and-protect  any position with no working sell-stop gets one at
                     risk_rules.initial_stop (pp.301-302: absolute max stop,
                     sell the moment it's hit — so a stop must always rest
                     at the broker).
  ratchet            price >= breakeven_trigger (3x initial risk, p.308)
                     and the stop still sits below entry -> move the stop
                     to breakeven at Alpaca.
  streak bookkeeping filled sell-stops below entry bump consecutive_losses;
                     a filled take-profit leg steps it back down (p.304).

Safety invariants:
  * NEVER initiates a buy. Entries happen only via POST /trading/enter.
  * Stops/targets rest AT ALPACA (GTC), never only in this process.
  * armed=false -> NO order is placed anywhere; every intended action is
    written to the trade_ledger as a dry_run row instead.

Import-light on purpose: no pandas/numpy anywhere in this module's import
chain (the broker layer pulls only `requests`); sepa.market_gauge (pandas)
is imported lazily inside regime() and failure there degrades to "normal".

The broker is OBTAINED FROM trading.broker.get_broker() (Alpaca when keys
are set or TRADING_BROKER=alpaca; the built-in Massive-quote sim otherwise
or when TRADING_BROKER=sim). Both expose the same duck-typed surface; the
sim also exposes process_fills(), duck-called at the top of every tick.

CLI:  python -m trading.exit_engine tick [--force]
"""
from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from trading import risk_rules
from trading.broker import BrokerError, get_broker

broker = get_broker()    # module-level so tests can monkeypatch EE.broker

log = logging.getLogger("trading.exit_engine")

CONFIG_ID = "config"
PROCESSED_IDS_KEEP = 1000      # cap on the never-double-count order-id list
STREAK_LOOKBACK_DAYS = 14      # closed-order scan window (see tick step e)


# ── Mongo (same lazy pattern as giants/flows.py) ───────────────────────────
_DB = None


def _db():
    global _DB
    if _DB is not None:
        return _DB
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        name = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        _DB = client[name]
        return _DB
    except Exception as exc:                       # noqa: BLE001
        log.warning("trading: mongo unavailable: %s", exc)
        return None


def _utc_iso(dt: Optional[datetime] = None) -> str:
    return (dt or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _et_day() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:                              # noqa: BLE001
        return datetime.now(timezone.utc).date().isoformat()


# ── trading_config (single doc) + trade_ledger ─────────────────────────────

def get_config() -> dict:
    doc = None
    db = _db()
    if db is not None:
        try:
            doc = db.trading_config.find_one({"_id": CONFIG_ID})
        except Exception as exc:                   # noqa: BLE001
            log.warning("trading_config read failed: %s", exc)
    doc = doc or {}
    try:                                # canonical default lives in auto_entry
        from trading.auto_entry import DEFAULT_EQUITY_CAP as _cap_default
    except Exception:                              # noqa: BLE001
        _cap_default = 5000.0
    try:
        equity_cap = float(doc.get("equity_cap") or 0) or _cap_default
    except (TypeError, ValueError):
        equity_cap = _cap_default
    return {
        "armed": bool(doc.get("armed", False)),          # default DISARMED
        "auto_entry": bool(doc.get("auto_entry", False)),  # default OFF
        "equity_cap": equity_cap,       # "assume you have 5k" sizing ceiling
        "consecutive_losses": int(doc.get("consecutive_losses") or 0),
        "processed_order_ids": list(doc.get("processed_order_ids") or []),
        "last_tick_iso": doc.get("last_tick_iso"),
        "last_not_configured_day": doc.get("last_not_configured_day"),
        "last_auto_entry_disabled_day": doc.get("last_auto_entry_disabled_day"),
        "updated_at": doc.get("updated_at"),
    }


def update_config(**fields) -> None:
    db = _db()
    if db is None:
        return
    fields["updated_at"] = _utc_iso()
    try:
        db.trading_config.update_one({"_id": CONFIG_ID},
                                     {"$set": fields}, upsert=True)
    except Exception as exc:                       # noqa: BLE001
        log.warning("trading_config write failed: %s", exc)


def ledger(kind: str, symbol: Optional[str] = None, detail: Optional[dict] = None,
           dry_run: bool = False, cite: Optional[str] = None) -> dict:
    row = {"ts": _utc_iso(), "epoch": time.time(), "kind": kind,
           "symbol": symbol, "detail": detail or {},
           "dry_run": bool(dry_run), "cite": cite}
    db = _db()
    if db is not None:
        try:
            db.trade_ledger.insert_one(dict(row))
        except Exception as exc:                   # noqa: BLE001
            log.warning("trade_ledger write failed: %s", exc)
    log.info("ledger %s%s %s%s", kind, " " + symbol if symbol else "",
             "DRY-RUN " if dry_run else "", detail or {})
    return row


def _detail_text(detail) -> str:
    """Flatten a ledger row's detail into a readable one-liner for the feed.

    Rows store `detail` as a dict; the frontend renders it as plain text, so an
    object reaching JSX crashes React (#31). Coerce here at the API boundary —
    the raw dicts stay in Mongo for journal.reconcile()."""
    if detail is None:
        return ""
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        parts = []
        for k, v in detail.items():
            if isinstance(v, dict):
                v = ", ".join("%s=%s" % (kk, vv) for kk, vv in v.items())
            elif isinstance(v, (list, tuple)):
                v = ", ".join(str(x) for x in v)
            parts.append("%s: %s" % (k, v))
        return " · ".join(parts)
    return str(detail)


def ledger_tail(limit: int = 20) -> list:
    db = _db()
    rows = []
    if db is None:
        return rows
    try:
        for d in db.trade_ledger.find().sort("epoch", -1).limit(int(limit)):
            d.pop("_id", None)
            d["detail"] = _detail_text(d.get("detail"))
            rows.append(d)
    except Exception as exc:                       # noqa: BLE001
        log.warning("trade_ledger read failed: %s", exc)
    return rows


def _notify_autopilot(kind: str, ticker: str, detail: str) -> None:
    """Owner push for Auto-Pilot events (push.hooks.notify_autopilot —
    owner-scoped, his own trades). Failures are logged + swallowed: push can
    never break the reconciler."""
    try:
        from push.hooks import notify_autopilot
        notify_autopilot(kind, ticker, detail)
    except Exception as exc:                       # noqa: BLE001
        log.warning("autopilot push failed (%s %s): %s", kind, ticker, exc)


# ── Account starting baseline (P&L denominator) ────────────────────────────

def _baseline_coll():
    db = _db()
    return None if db is None else db.trading_account_baseline


def account_starting_cash(acct: dict) -> float:
    """The "what we started this account with" baseline for the P&L header.

    The SIM reports `starting_cash` on its account directly. A live/paper
    brokerage account has no such field — its API only knows the equity right
    now — so the FIRST time we ever see the account we snapshot its equity and
    persist it (keyed by the account id), then read that snapshot forever after.
    "started $X -> equity now" then reads as the gain since the engine was
    connected to this account, which is what the dashboard wants.

    Degrades safely: with no Mongo it returns current equity (P&L shows $0,
    never a crash). Deleting the persisted doc re-baselines on the next read."""
    acct = acct or {}
    sc = acct.get("starting_cash")
    if sc is not None:
        try:
            return float(sc)
        except (TypeError, ValueError):
            pass
    try:
        equity = float(acct.get("equity") or 0)
    except (TypeError, ValueError):
        equity = 0.0
    key = str(acct.get("account_number") or acct.get("id") or _broker_mode())
    coll = _baseline_coll()
    if coll is None:
        return equity
    try:
        doc = coll.find_one({"account_key": key})
        if doc is not None and doc.get("starting_equity") is not None:
            return float(doc["starting_equity"])
        coll.update_one(
            {"account_key": key},
            {"$set": {"account_key": key, "starting_equity": equity,
                      "mode": _broker_mode(), "snapshot_ts": _utc_iso()}},
            upsert=True)
        return equity
    except Exception as exc:                       # noqa: BLE001
        log.warning("account baseline read/seed failed (%s): %s", key, exc)
        return equity


# ── Account P&L summary (Auto-Pilot dashboard) ─────────────────────────────

def pnl_summary(account, positions) -> dict:
    """Account-level P&L roll-up for the Auto-Pilot dashboard (portfolio-style):
    what we STARTED with vs equity now, plus invested / unrealized / realized.
    Ajay 2026-06-18 ("I can't tell if we made money … how much did we enter
    with"). Pure — derived from the broker account + open positions.

    Identity for the SIM (no deposits/withdrawals):
        equity = starting_cash + realized + unrealized
    so realized = total_pnl − unrealized."""
    acct = account or {}
    starting = float(acct.get("starting_cash") or 0)
    equity = float(acct.get("equity") or 0)
    cash = float(acct.get("cash") or 0)
    cost_basis = 0.0
    for p in positions or []:
        cost_basis += float(p.get("qty") or 0) * float(p.get("avg_entry") or 0)
    market_value = round(equity - cash, 2)               # authoritative (account equity)
    unreal = round(market_value - cost_basis, 2)
    total = round(equity - starting, 2) if starting else None
    realized = round(total - unreal, 2) if total is not None else None
    return {
        "starting_cash": round(starting, 2),
        "equity": round(equity, 2),
        "cash": round(cash, 2),
        "invested": round(cost_basis, 2),
        "market_value": market_value,
        "unrealized_dollars": unreal,
        "unrealized_pct": round(unreal / cost_basis * 100, 2) if cost_basis else None,
        "realized_dollars": realized,
        "total_pnl_dollars": total,
        "total_pnl_pct": round(total / starting * 100, 2) if (starting and total is not None) else None,
        "position_count": len(positions or []),
    }


# ── Regime (p.311 normal vs difficult) ─────────────────────────────────────

def regime() -> str:
    """Map the persisted Market Gauge onto the book's two regimes (p.311).

    sepa.market_gauge.get_gauge() returns a dict whose `state` is one of
    'constructive' | 'caution' | 'risk_off' (score 0-100, cutoffs 67/34).
    Conservative mapping: ONLY an explicit 'risk_off' verdict -> 'difficult';
    'caution', 'constructive', a missing doc, or any error -> 'normal'.
    Lazy import — market_gauge pulls pandas; the engine must work without it.
    """
    try:
        from sepa.market_gauge import get_gauge
        state = str((get_gauge(prefer_persisted=True) or {}).get("state") or "").lower()
        if state == "risk_off":
            return "difficult"
    except Exception as exc:                       # noqa: BLE001
        log.debug("regime: gauge unavailable (%s) -> normal", exc)
    return "normal"


# ── Order helpers ──────────────────────────────────────────────────────────

def _flatten_orders(orders) -> list:
    """Top-level open orders + their nested bracket legs as one flat list."""
    out = []
    for o in orders or []:
        out.append(o)
        for leg in o.get("legs") or []:
            out.append(leg)
    return out


def _order_type(o: dict) -> str:
    return (o.get("type") or o.get("order_type") or "").lower()


def _is_working(o: dict) -> bool:
    return (o.get("status") or "").lower() in broker.OPEN_STATUSES


def _find_stop(orders, symbol: str) -> Optional[dict]:
    """The working protective sell-stop for symbol (bracket legs included)."""
    for o in orders:
        if ((o.get("symbol") or "").upper() == symbol
                and (o.get("side") or "").lower() == "sell"
                and _order_type(o) in ("stop", "stop_limit")
                and _is_working(o)):
            return o
    return None


def _find_target(orders, symbol: str) -> Optional[dict]:
    """The working take-profit sell-limit for symbol."""
    for o in orders:
        if ((o.get("symbol") or "").upper() == symbol
                and (o.get("side") or "").lower() == "sell"
                and _order_type(o) == "limit"
                and _is_working(o)):
            return o
    return None


def _initial_stop_from_ledger(symbol: str) -> Optional[float]:
    """The ORIGINAL initial stop price for symbol, from the ledger row written
    at entry/adopt time (p.308: the breakeven trigger uses the INITIAL risk,
    not the current stop after any ratchet). None when no row exists."""
    db = _db()
    if db is None:
        return None
    try:
        cur = (db.trade_ledger
               .find({"symbol": symbol, "kind": {"$in": ["entry", "adopt_protect"]}})
               .sort("epoch", -1).limit(5))
        for d in cur:
            det = d.get("detail") or {}
            sp = det.get("stop_price") or (det.get("stop") or {}).get("stop_price")
            if sp:
                return float(sp)
    except Exception as exc:                       # noqa: BLE001
        log.debug("initial stop lookup failed for %s: %s", symbol, exc)
    return None


def _entry_price_from_ledger(symbol: str) -> Optional[float]:
    db = _db()
    if db is None:
        return None
    try:
        cur = (db.trade_ledger
               .find({"symbol": symbol, "kind": {"$in": ["entry", "adopt_protect"]}})
               .sort("epoch", -1).limit(5))
        for d in cur:
            det = d.get("detail") or {}
            px = det.get("price") or det.get("avg_entry")
            if px:
                return float(px)
    except Exception as exc:                       # noqa: BLE001
        log.debug("entry price lookup failed for %s: %s", symbol, exc)
    return None


# ── The reconciler ─────────────────────────────────────────────────────────

def tick(force: bool = False) -> dict:
    summary = {"ok": True, "forced": bool(force), "market_open": None,
               "armed": False, "regime": None, "positions": 0,
               "adopted": 0, "ratcheted": 0, "dry_run_rows": 0,
               "streak_events": 0, "errors": []}

    # (0) sim matching engine — duck-called when the active broker has one
    # (the sim broker fills pending orders against Massive quotes here; a
    # real broker matches at the exchange). MUST run before adopt/ratchet/
    # streak so a just-filled stop is seen this same tick.
    if hasattr(broker, "process_fills"):
        try:
            summary["sim_fills"] = broker.process_fills()
        except Exception as exc:                   # noqa: BLE001
            summary["errors"].append("process_fills: %s" % exc)

    # (a) configured?
    if not broker.configured():
        today = _et_day()
        if get_config().get("last_not_configured_day") != today:
            ledger("not_configured",
                   detail={"hint": "set ALPACA_KEY_ID / ALPACA_SECRET_KEY"})
            update_config(last_not_configured_day=today)
        summary.update(ok=False, reason="not_configured")
        return summary

    # (b) market clock — authoritative; cron's hour band only bounds calls.
    try:
        market_open = bool(broker.clock().get("is_open"))
    except BrokerError as exc:
        summary["errors"].append(str(exc))
        market_open = False
        if not force:
            summary.update(ok=False, reason="clock_unavailable")
            return summary
    summary["market_open"] = market_open
    if not market_open and not force:
        summary["reason"] = "market_closed"
        return summary

    # (c) config + regime
    cfg = get_config()
    armed = cfg["armed"]
    reg = regime()
    summary.update(armed=armed, regime=reg)
    tick_started_iso = _utc_iso()

    # (d) protect + ratchet every position
    try:
        positions = broker.positions()
        open_orders = _flatten_orders(broker.open_orders())
    except BrokerError as exc:
        summary["ok"] = False
        summary["errors"].append(str(exc))
        return summary
    summary["positions"] = len(positions)

    for pos in positions:
        sym = (pos.get("symbol") or "").upper()
        try:
            qty = int(float(pos.get("qty") or 0))
            avg_entry = float(pos.get("avg_entry_price") or 0)
            last = float(pos.get("current_price") or 0)
        except (TypeError, ValueError):
            continue
        if qty <= 0 or avg_entry <= 0:
            continue                       # engine manages whole-share longs only

        stop_order = _find_stop(open_orders, sym)

        if stop_order is None:
            # adopt-and-protect (pp.301-302: a stop must always be resting)
            plan = risk_rules.initial_stop(avg_entry, reg)
            detail = {"qty": qty, "avg_entry": avg_entry,
                      "stop_price": plan.stop_price, "stop_pct": plan.stop_pct,
                      "basis": plan.basis, "regime": reg}
            if armed:
                try:
                    order = broker.submit_stop(
                        sym, qty, plan.stop_price,
                        client_order_id=broker.make_client_order_id(sym, "protect"))
                    detail["order_id"] = order.get("id")
                    ledger("adopt_protect", symbol=sym, detail=detail,
                           dry_run=False, cite="p.301-302")
                    summary["adopted"] += 1
                except BrokerError as exc:
                    summary["errors"].append("adopt %s: %s" % (sym, exc))
            else:
                ledger("adopt_protect", symbol=sym, detail=detail,
                       dry_run=True, cite="p.301-302")
                summary["dry_run_rows"] += 1
            continue

        # ratchet to breakeven (p.308) — trigger uses the ORIGINAL risk
        try:
            cur_stop = float(stop_order.get("stop_price") or 0)
        except (TypeError, ValueError):
            continue
        if cur_stop <= 0 or last <= 0:
            continue
        initial_sp = _initial_stop_from_ledger(sym) or cur_stop
        if initial_sp >= avg_entry:        # bad ledger data — fall back
            initial_sp = cur_stop
        if initial_sp >= avg_entry:        # stop already at/above entry
            continue
        trigger = risk_rules.breakeven_trigger(avg_entry, initial_sp)
        # Breakeven on the cent grid. Guard against new_stop (NOT the raw
        # avg_entry float): Alpaca's avg_entry_price can carry >2 decimals,
        # and `cur_stop < avg_entry` would stay true after replacing to
        # round(avg_entry, 2) — an infinite replace-every-tick loop.
        new_stop = round(avg_entry, 2)
        if last >= trigger and cur_stop < new_stop:
            detail = {"qty": qty, "avg_entry": avg_entry, "last": last,
                      "trigger": trigger, "initial_stop": initial_sp,
                      "old_stop": cur_stop, "new_stop": new_stop,
                      "order_id": stop_order.get("id")}
            if armed:
                try:
                    broker.replace_order(stop_order.get("id"), stop_price=new_stop)
                    ledger("ratchet_breakeven", symbol=sym, detail=detail,
                           dry_run=False, cite="p.308")
                    summary["ratcheted"] += 1
                except BrokerError as exc:
                    summary["errors"].append("ratchet %s: %s" % (sym, exc))
            else:
                ledger("ratchet_breakeven", symbol=sym, detail=detail,
                       dry_run=True, cite="p.308")
                summary["dry_run_rows"] += 1

    # (e) streak bookkeeping (p.304) — never double-count an order id.
    # Alpaca's closed-orders `after` filters by SUBMITTED time, so a GTC stop
    # submitted days ago that fills today is invisible to a since=last-tick
    # query. Always scan a fixed lookback window instead; processed_order_ids
    # dedupes the re-scans (sell fills only, so the 1000-id cap is years of
    # headroom at MAX_POSITIONS=5).
    since = _utc_iso(datetime.now(timezone.utc)
                     - timedelta(days=STREAK_LOOKBACK_DAYS))
    processed_ids = list(cfg["processed_order_ids"])
    seen = set(processed_ids)
    losses = cfg["consecutive_losses"]
    try:
        closed = broker.closed_orders_since(since)
    except BrokerError as exc:
        closed = []
        summary["errors"].append(str(exc))

    for o in closed:
        oid = o.get("id")
        if not oid or oid in seen:
            continue
        if (o.get("side") or "").lower() != "sell":
            continue
        if (o.get("status") or "").lower() != "filled":
            continue
        otype = _order_type(o)
        sym = (o.get("symbol") or "").upper()
        try:
            fill = float(o.get("filled_avg_price") or 0)
        except (TypeError, ValueError):
            fill = 0.0
        entry_px = _entry_price_from_ledger(sym)

        if otype in ("stop", "stop_limit"):
            # A stop fill below entry is a loss. Unknown entry -> treat as a
            # loss (a stop sits below entry unless ratcheted to breakeven).
            is_loss = (fill < entry_px) if (entry_px and fill) else True
            processed_ids.append(oid)
            seen.add(oid)
            if is_loss:
                losses += 1
                ledger("streak_loss", symbol=sym,
                       detail={"order_id": oid, "fill": fill, "entry": entry_px,
                               "consecutive_losses": losses,
                               "size_multiplier": risk_rules.size_multiplier(losses)},
                       cite="p.304")
            else:
                ledger("streak_neutral", symbol=sym,
                       detail={"order_id": oid, "fill": fill, "entry": entry_px,
                               "note": "stop filled at/above entry (breakeven)"},
                       cite="p.308")
            summary["streak_events"] += 1
        elif otype == "limit" and (o.get("order_class") or "") in ("bracket", "oco", "oto"):
            # take-profit leg filled — the plan worked: step back down (p.304)
            processed_ids.append(oid)
            seen.add(oid)
            losses = max(0, losses - risk_rules.STREAK_HALVE_AFTER)
            ledger("streak_win", symbol=sym,
                   detail={"order_id": oid, "fill": fill, "entry": entry_px,
                           "consecutive_losses": losses,
                           "size_multiplier": risk_rules.size_multiplier(losses)},
                   cite="p.304")
            summary["streak_events"] += 1
        else:
            continue

        # closed-trade stats feed initial_stop's half-avg-gain rule (p.299)
        if entry_px and fill:
            gain_pct = round((fill / entry_px - 1) * 100, 2)
            is_stop_leg = otype in ("stop", "stop_limit")
            ledger("trade_closed", symbol=sym,
                   detail={"order_id": oid,
                           "leg": "stop" if is_stop_leg else "take_profit",
                           "fill": fill, "entry": entry_px,
                           "gain_pct": gain_pct},
                   cite="p.299")
            _notify_autopilot(
                "stop_filled" if is_stop_leg else "target_filled", sym,
                "%s closed via %s: filled %.2f vs entry %.2f (%+.2f%%)"
                % (sym, "stop" if is_stop_leg else "take-profit",
                   fill, entry_px, gain_pct))

    update_config(consecutive_losses=losses,
                  processed_order_ids=processed_ids[-PROCESSED_IDS_KEEP:],
                  last_tick_iso=tick_started_iso)
    summary["streak"] = {"consecutive_losses": losses,
                         "size_multiplier": risk_rules.size_multiplier(losses)}

    # (f) auto-entry — AFTER exit reconciliation, fully fenced: a buy-side
    # crash can never break stop protection above.
    try:
        from trading import auto_entry
        summary["auto_entry"] = auto_entry.run(broker=broker, cfg=get_config())
    except Exception as exc:                       # noqa: BLE001
        log.warning("auto_entry run failed: %s", exc)
        summary["errors"].append("auto_entry: %s" % exc)

    # (g) journal reconcile — derive/update the perpetual trade_journal from
    # the ledger so it is current between ticks. Read-only over the ledger, no
    # trading side effects; fully fenced + lazy-imported so it can NEVER break
    # stop protection or entries above (import-light: journal pulls no pandas).
    try:
        from trading import journal
        summary["journal"] = journal.reconcile()
    except Exception as exc:                       # noqa: BLE001
        log.warning("journal reconcile failed: %s", exc)
        summary["errors"].append("journal: %s" % exc)
    return summary


# ── Status (GET /trading/status payload) ───────────────────────────────────

def _broker_mode() -> str:
    """"sim" | "paper" | "live" from the ACTIVE broker's mode() (duck-called
    so test fakes without mode() fall back to the ALPACA_PAPER reading)."""
    m = getattr(broker, "mode", None)
    if callable(m):
        try:
            return str(m())
        except Exception as exc:                   # noqa: BLE001
            log.debug("broker mode() failed: %s", exc)
    return "live" if (os.getenv("ALPACA_PAPER", "1") or "1").strip() == "0" else "paper"


# Three missed 1-min ticks = the order-managing engine is behind/asleep.
ENGINE_STALE_SEC = 180


def _engine_liveness(last_tick_iso, *, market_open: bool, armed: bool) -> dict:
    """Liveness of the REAL trading engine — its 1-min tick() heartbeat written
    to trading_config.last_tick_iso, NOT the alert cron. ``stale`` is only True
    when the engine SHOULD be running (market open AND armed) but its last pass
    is older than ENGINE_STALE_SEC (or never recorded). This is the one signal
    that means "order management may be uncovered right now"."""
    age = None
    epoch = None
    if last_tick_iso:
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(str(last_tick_iso).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            epoch = dt.timestamp()
            age = max(0.0, time.time() - epoch)
        except Exception:                              # noqa: BLE001
            age = None
    stale = bool(market_open and armed and (age is None or age > ENGINE_STALE_SEC))
    return {
        "last_tick_iso": last_tick_iso,
        "last_tick_epoch": epoch,
        "tick_age_sec": round(age) if age is not None else None,
        "stale_after_sec": ENGINE_STALE_SEC,
        "stale": stale,
    }


def status() -> dict:
    cfg = get_config()
    out = {
        "mode": _broker_mode(),
        "configured": broker.configured(),
        "armed": cfg["armed"],
        "market_open": False,
        "account": None,
        "regime": "normal",
        "streak": {"consecutive_losses": cfg["consecutive_losses"],
                   "size_multiplier": risk_rules.size_multiplier(cfg["consecutive_losses"])},
        "positions": [],
        "ledger_tail": ledger_tail(20),
        "error": None,
    }
    try:
        from trading import auto_entry
        out["auto_entry"] = auto_entry.status_block(cfg)
    except Exception as exc:                       # noqa: BLE001
        out["auto_entry"] = {"enabled": bool(cfg.get("auto_entry")),
                             "error": str(exc)}
    if not out["configured"]:
        return out
    try:
        acct = broker.account()
        out["account"] = {"equity": float(acct.get("equity") or 0),
                          "cash": float(acct.get("cash") or 0),
                          "buying_power": float(acct.get("buying_power") or 0),
                          "starting_cash": account_starting_cash(acct)}
        out["market_open"] = bool(broker.clock().get("is_open"))
        out["regime"] = regime()
        orders = _flatten_orders(broker.open_orders())
        for pos in broker.positions():
            sym = (pos.get("symbol") or "").upper()
            qty = int(float(pos.get("qty") or 0))
            avg_entry = float(pos.get("avg_entry_price") or 0)
            last = float(pos.get("current_price") or 0)
            upl_pct = round((last / avg_entry - 1) * 100, 2) if (avg_entry and last) else None

            so = _find_stop(orders, sym)
            stop = None
            if so is not None:
                try:
                    sp = float(so.get("stop_price") or 0)
                except (TypeError, ValueError):
                    sp = 0.0
                stop = {"price": sp,
                        "pct_below_entry": round((1 - sp / avg_entry) * 100, 2) if avg_entry else None,
                        "order_id": so.get("id"),
                        "at_breakeven": bool(avg_entry and sp >= avg_entry)}

            to = _find_target(orders, sym)
            target = None
            if to is not None:
                try:
                    target = {"price": float(to.get("limit_price") or 0),
                              "order_id": to.get("id")}
                except (TypeError, ValueError):
                    target = {"price": None, "order_id": to.get("id")}

            init_sp = _initial_stop_from_ledger(sym) or (stop or {}).get("price")
            bt = None
            if init_sp and avg_entry and float(init_sp) < avg_entry:
                bt = risk_rules.breakeven_trigger(avg_entry, float(init_sp))

            out["positions"].append({
                "symbol": sym, "qty": qty, "avg_entry": avg_entry,
                "last": last, "upl_pct": upl_pct, "stop": stop,
                "target": target, "breakeven_trigger": bt,
                "protected": stop is not None,
            })
    except Exception as exc:                       # noqa: BLE001 — BrokerError is pre-scrubbed
        out["error"] = str(exc)
    # Real engine heartbeat (its 1-min tick), so the page can warn when order
    # management may be asleep while armed + market open. Computed last so it
    # sees the resolved market_open above.
    out["engine"] = _engine_liveness(cfg.get("last_tick_iso"),
                                     market_open=bool(out.get("market_open")),
                                     armed=bool(out.get("armed")))
    # Count of OPEN positions with NO resting stop — "real risk uncovered now".
    out["unprotected"] = [p["symbol"] for p in out["positions"] if not p.get("protected")]
    # Portfolio-style account P&L (started-with vs now) for the dashboard header.
    out["pnl_summary"] = pnl_summary(out.get("account"), out.get("positions"))
    return out


# ── Flatten (manual risk-off actions; still gated by armed) ────────────────

def flatten(symbol: str) -> dict:
    """Cancel symbol's open orders + close the position. Disarmed -> a
    dry_run ledger row only (invariant: armed=false places NO orders)."""
    sym = (symbol or "").strip().upper()
    if not sym:
        raise ValueError("symbol required")
    if not broker.configured():
        raise ValueError("Alpaca not configured (ALPACA_KEY_ID / ALPACA_SECRET_KEY)")
    cfg = get_config()
    try:
        orders = [o for o in broker.open_orders(symbol=sym)
                  if (o.get("symbol") or "").upper() == sym]
    except BrokerError as exc:
        raise ValueError(str(exc))

    if not cfg["armed"]:
        ledger("flatten", symbol=sym,
               detail={"orders_to_cancel": [o.get("id") for o in orders],
                       "note": "disarmed — dry run, nothing sent"},
               dry_run=True, cite="p.302")
        return {"dry_run": True, "canceled": 0, "closed": False,
                "detail": "disarmed — no orders placed; dry-run ledger row recorded"}

    canceled, errors = 0, []
    for o in orders:
        oid = o.get("id")
        if not oid:
            continue
        try:
            broker.cancel_order(oid)
            canceled += 1
        except BrokerError as exc:
            errors.append(str(exc))
    closed = False
    try:
        broker.close_position(sym)
        closed = True
    except BrokerError as exc:
        errors.append(str(exc))
    ledger("flatten", symbol=sym,
           detail={"canceled": canceled, "closed": closed, "errors": errors},
           dry_run=False, cite="p.302")
    return {"dry_run": False, "canceled": canceled, "closed": closed,
            "errors": errors}


def flatten_all() -> dict:
    """Disaster plan: cancel every open order, close every position."""
    if not broker.configured():
        raise ValueError("Alpaca not configured (ALPACA_KEY_ID / ALPACA_SECRET_KEY)")
    cfg = get_config()
    try:
        positions = broker.positions()
        orders = broker.open_orders()
    except BrokerError as exc:
        raise ValueError(str(exc))
    syms = [(p.get("symbol") or "").upper() for p in positions]

    if not cfg["armed"]:
        ledger("flatten_all",
               detail={"positions": syms,
                       "orders_to_cancel": [o.get("id") for o in orders],
                       "note": "disarmed — dry run, nothing sent"},
               dry_run=True, cite="p.302")
        return {"dry_run": True, "canceled": 0, "closed": [],
                "detail": "disarmed — no orders placed; dry-run ledger row recorded"}

    canceled, errors, closed = 0, [], []
    for o in orders:                       # cancel parents; legs die with them
        oid = o.get("id")
        if not oid:
            continue
        try:
            broker.cancel_order(oid)
            canceled += 1
        except BrokerError as exc:
            errors.append(str(exc))
    for sym in syms:
        try:
            broker.close_position(sym)
            closed.append(sym)
        except BrokerError as exc:
            errors.append(str(exc))
    ledger("flatten_all",
           detail={"canceled": canceled, "closed": closed, "errors": errors},
           dry_run=False, cite="p.302")
    return {"dry_run": False, "canceled": canceled, "closed": closed,
            "errors": errors}


# ── CLI ────────────────────────────────────────────────────────────────────

def _main(argv) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if not argv or argv[0] != "tick":
        print("usage: python -m trading.exit_engine tick [--force]")
        return 2
    summary = tick(force="--force" in argv[1:])
    log.info("EXIT-ENGINE tick: %s", summary)
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
