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

def _auto_entry_default() -> bool:
    """Auto-entry default: ON in paper/sim, OFF in live (Ajay 2026-06-26 —
    "default on, it's paper anyway"). Live stays opt-in so a real account never
    auto-buys by default; arming (the master switch) is still required in EVERY
    mode, so a default-on auto-entry still places no order until armed."""
    try:
        return _broker_mode() != "live"
    except Exception:                              # noqa: BLE001
        return False                               # fail safe → off


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
        "armed": bool(doc.get("armed", False)),          # default DISARMED (master switch)
        # Default ON in paper/sim, OFF in live. Respect an explicit stored value
        # (once toggled) either way; only fall back to the mode-aware default
        # when the key was never set. Arming still gates every actual order.
        "auto_entry": (bool(doc["auto_entry"]) if "auto_entry" in doc
                       else _auto_entry_default()),
        "equity_cap": equity_cap,       # "assume you have 5k" sizing ceiling
        "consecutive_losses": int(doc.get("consecutive_losses") or 0),
        "processed_order_ids": list(doc.get("processed_order_ids") or []),
        "last_tick_iso": doc.get("last_tick_iso"),
        "last_not_configured_day": doc.get("last_not_configured_day"),
        "last_auto_entry_disabled_day": doc.get("last_auto_entry_disabled_day"),
        "last_auto_entry_scan_warn_day": doc.get("last_auto_entry_scan_warn_day"),
        # Zone-edge (Supply & Demand) entries — trading/zone_edge_entry.py.
        # Default OFF in EVERY mode (owner opt-in per POST /trading/config);
        # arming is still required on top, like every other buy path.
        "zone_edge_entry": bool(doc.get("zone_edge_entry", False)),
        # Owner rule switches (zone_edge_entry.active_rules overlays these on
        # its STRICT defaults; anything malformed falls back to strict).
        "zone_edge_rules": (dict(doc["zone_edge_rules"])
                            if isinstance(doc.get("zone_edge_rules"), dict) else {}),
        "last_zone_entry_disabled_day": doc.get("last_zone_entry_disabled_day"),
        # Funnel floor overrides (data write, no deploy). This whitelist used
        # to STRIP them, which silently killed the documented auto_min_score
        # override — found in the 2026-07-12 low-RS audit.
        "auto_min_score": doc.get("auto_min_score"),
        "auto_min_rs": doc.get("auto_min_rs"),
        "progressive_exposure": doc.get("progressive_exposure"),
        "pyramiding": doc.get("pyramiding"),
        "last_errors": list(doc.get("last_errors") or []),  # last tick's failures, surfaced on the dashboard
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

    A NON-constructive tape runs the book's difficult-market playbook (p.311):
    BOTH 'risk_off' AND 'caution' -> 'difficult' (Ajay 2026-06-22). 'difficult'
    tightens the stop band (7-8% -> 5-6%) and takes smaller profits (15-20% ->
    10-12%) via risk_rules.regime_bands — Minervini downshifts in a tough market
    instead of trading it like a clean uptrend, and the 1-min tick means a later
    re-entry on a constructive turn is never missed. Only 'constructive' (or a
    missing doc / any error) -> 'normal'. Stops can only TIGHTEN under
    'difficult', never widen (p.308-309) — strictly more conservative.
    Lazy import — market_gauge pulls pandas; the engine must work without it.
    """
    try:
        from sepa.market_gauge import get_gauge
        state = str((get_gauge(prefer_persisted=True) or {}).get("state") or "").lower()
        if state in ("risk_off", "caution"):
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


# Statuses where a stop will ACTUALLY fire when its price is hit. This is
# STRICTER than broker.OPEN_STATUSES (which counts "held"): Alpaca can leave a
# bracket stop-loss leg stuck in "held" so it never triggers even when price
# reaches it (known Alpaca bug, confirmed 2026-06-24) — a "held" stop is NOT
# protection, so it must not count here.
_STOP_LIVE_STATUSES = {"new", "accepted", "partially_filled"}


def _find_working_stop(orders, symbol: str) -> Optional[dict]:
    """A protective sell-stop that will genuinely fire if hit (status in
    _STOP_LIVE_STATUSES). Returns None when the only stop is stuck/"held" —
    that's the case the watchdog must cover."""
    for o in orders:
        if ((o.get("symbol") or "").upper() == symbol
                and (o.get("side") or "").lower() == "sell"
                and _order_type(o) in ("stop", "stop_limit")
                and (o.get("status") or "").lower() in _STOP_LIVE_STATUSES):
            return o
    return None


def _effective_stop(symbol: str, avg_entry: float, reg: str,
                    stop_order: Optional[dict] = None) -> Optional[float]:
    """The protective stop price the engine is COMMITTED to, for the watchdog +
    the dashboard. Prefers a visible resting stop's price, else the original
    stop from the entry ledger row, else the regime initial stop recomputed
    from entry (pp.301-302/311). None only when nothing is computable."""
    if stop_order is not None:
        try:
            sp = float(stop_order.get("stop_price") or 0)
            if sp > 0:
                return sp
        except (TypeError, ValueError):
            pass
    led = _initial_stop_from_ledger(symbol)
    if led:
        try:
            return float(led)
        except (TypeError, ValueError):
            pass
    try:
        return float(risk_rules.initial_stop(float(avg_entry), reg).stop_price)
    except Exception:                                  # noqa: BLE001
        return None


def _distribution_read(symbol: str) -> Optional[dict]:
    """Latest SEPA scan row (stage + sell-signals + volume + climax + mvp) for a
    held symbol, or None. Lazy + fenced: sepa.scanner pulls pandas and the engine
    must work without it, so any failure degrades to "no sell signal" rather than
    breaking the reconciler."""
    try:
        from sepa import scanner as _sc
        latest = _sc.load_latest() or {}
        rows = (latest.get("results") or latest.get("candidates")
                or latest.get("rows") or [])
        for r in rows:
            if (r.get("symbol") or "").upper() == symbol.upper():
                return r
    except Exception as exc:                           # noqa: BLE001
        log.debug("distribution read failed for %s: %s", symbol, exc)
    return None


def _fired_today(kind: str, symbol: str) -> bool:
    """True if a ledger row of ``kind`` for ``symbol`` already exists today (ET).
    Fires each distribution alert/exit at most once per name per day instead of
    every minute. ts is stamped UTC but equals the ET calendar day during US
    market hours (the only window the tick runs), so the ^YYYY-MM-DD prefix holds."""
    db = _db()
    if db is None:
        return False
    try:
        return db.trade_ledger.find_one(
            {"kind": kind, "symbol": (symbol or "").upper(),
             "ts": {"$regex": "^" + _et_day()}}) is not None
    except Exception:                                  # noqa: BLE001
        return False


def _force_exit(symbol: str, orders) -> dict:
    """Cancel symbol's working orders + market-close the position NOW. The
    watchdog's hands — caller must already be armed. ``broker.close_position``
    errors propagate so the caller can alert; cancel errors are collected."""
    sym = (symbol or "").upper()
    canceled, cancel_errors = 0, []
    for o in orders or []:
        if (o.get("symbol") or "").upper() != sym:
            continue
        oid = o.get("id")
        if not oid:
            continue
        try:
            broker.cancel_order(oid)
            canceled += 1
        except BrokerError as exc:
            cancel_errors.append(str(exc))
    broker.close_position(sym)
    return {"canceled": canceled, "cancel_errors": cancel_errors, "closed": True}


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
               "adopted": 0, "ratcheted": 0, "watchdog_exits": 0,
               "distribution_exits": 0, "distribution_alerts": 0,
               "dry_run_rows": 0, "streak_events": 0, "errors": []}

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
        working_stop = _find_working_stop(open_orders, sym)

        # (d0) WATCHDOG — the engine's own backstop. A broker stop can silently
        # fail to fire (Alpaca leaves bracket stop-loss legs stuck in "held";
        # confirmed 2026-06-24), so we never trust the broker alone. If NO
        # genuinely-working stop rests AND price has reached/breached the
        # committed stop, the engine SELLS AT MARKET this tick (pp.301-302: sell
        # the moment the stop is hit, no exceptions). When a real working stop
        # rests, we leave it to the broker (avoids double-selling / slippage).
        eff_stop = _effective_stop(sym, avg_entry, reg, working_stop)
        if working_stop is None and eff_stop and last > 0 and last <= eff_stop:
            detail = {"qty": qty, "avg_entry": avg_entry, "last": last,
                      "stop": round(eff_stop, 2), "regime": reg,
                      "reason": "price hit stop with no working broker stop"}
            if armed:
                try:
                    detail.update(_force_exit(sym, open_orders))
                    ledger("watchdog_exit", symbol=sym, detail=detail,
                           dry_run=False, cite="p.301-302")
                    summary["watchdog_exits"] += 1
                    _notify_autopilot(
                        "position_alert", sym,
                        "%s sold at market ~%.2f — stop %.2f hit and no working broker "
                        "stop fired (engine backstop)" % (sym, last, eff_stop))
                except BrokerError as exc:
                    summary["errors"].append("watchdog %s: %s" % (sym, exc))
                    _notify_autopilot(
                        "position_alert", sym,
                        "%s hit its stop %.2f but the engine could NOT exit (%s) — "
                        "act manually" % (sym, eff_stop, exc))
            else:
                ledger("watchdog_exit", symbol=sym,
                       detail={**detail, "note": "disarmed — dry run, nothing sent"},
                       dry_run=True, cite="p.301-302")
                summary["dry_run_rows"] += 1
            continue                       # exiting this position; skip adopt/ratchet

        # (d1) DISTRIBUTION / STAGE-BREAKDOWN sell discipline (Ajay 2026-06-25).
        # Read the latest SEPA stage + sell-signals for this held name and act on
        # the Minervini sell rules (trading.sell_discipline). Runs AFTER the
        # watchdog (a hit stop is unconditional) and BEFORE adopt/ratchet (don't
        # protect a name we're exiting). Aggressive mode: any topping/distribution
        # /exhaustion signal -> auto-sell at market. Dedup once per symbol/day/kind.
        from trading import sell_discipline as _sd
        verdict = _sd.evaluate(_distribution_read(sym), last)
        if verdict and not _fired_today(verdict["kind"], sym):
            ddetail = {"qty": qty, "avg_entry": avg_entry, "last": last,
                       "reason": verdict["reason"]}
            if verdict["action"] == "auto_sell":
                if armed:
                    try:
                        ddetail.update(_force_exit(sym, open_orders))
                        ledger(verdict["kind"], symbol=sym, detail=ddetail,
                               dry_run=False, cite=verdict["cite"])
                        summary["distribution_exits"] += 1
                        _notify_autopilot("position_alert", sym,
                            "%s SOLD at market ~%.2f — %s" % (sym, last, verdict["reason"]))
                    except BrokerError as exc:
                        summary["errors"].append("distribution_exit %s: %s" % (sym, exc))
                        _notify_autopilot("position_alert", sym,
                            "%s flashed a SELL (%s) but the engine could NOT exit "
                            "(%s) — act manually" % (sym, verdict["reason"], exc))
                else:
                    ledger(verdict["kind"], symbol=sym,
                           detail={**ddetail, "note": "disarmed — dry run, nothing sent"},
                           dry_run=True, cite=verdict["cite"])
                    summary["dry_run_rows"] += 1
                continue                   # exiting this name; skip adopt/ratchet
            else:                          # 'alert' — warn only, keep protecting it
                ledger(verdict["kind"], symbol=sym, detail=ddetail,
                       dry_run=False, cite=verdict["cite"])
                summary["distribution_alerts"] += 1
                _notify_autopilot("position_alert", sym, "%s — %s." % (sym, verdict["reason"]))

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
                  last_tick_iso=tick_started_iso,
                  last_errors=list(summary["errors"])[-20:])  # surfaced on the dashboard
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

    # (h) zone-edge entries (Supply & Demand strategy, owner rules; flag
    # `zone_edge_entry`, default OFF) — same fence as (f): a buy-side crash
    # can never break stop protection above. Buys still flow ONLY through
    # entries.enter().
    try:
        from trading import zone_edge_entry
        summary["zone_edge_entry"] = zone_edge_entry.run(broker=broker,
                                                         cfg=get_config())
    except Exception as exc:                       # noqa: BLE001
        log.warning("zone_edge_entry run failed: %s", exc)
        summary["errors"].append("zone_edge_entry: %s" % exc)

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

    # (i) failed-trade autopsies (trading/autopsy.py, owner rules) — AFTER
    # (g) so the journal it reads is current. Read-only over the journal /
    # zone state / prices / gauge (never the broker); writes trade_autopsies
    # only. Same fence as (f)/(h): a crash here can NEVER break stop
    # protection above. Bounded to autopsy.MAX_PER_RUN trades per tick.
    try:
        from trading import autopsy
        summary["autopsy"] = autopsy.run()
    except Exception as exc:                       # noqa: BLE001
        log.warning("autopsy run failed: %s", exc)
        summary["errors"].append("autopsy: %s" % exc)
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
    try:
        from trading import zone_edge_entry
        out["zone_edge_entry"] = zone_edge_entry.status_block(cfg)
    except Exception as exc:                       # noqa: BLE001
        out["zone_edge_entry"] = {"enabled": bool(cfg.get("zone_edge_entry")),
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

            # A genuinely-working broker stop (fires if hit) vs any visible
            # stop (may be a stuck "held" leg). Only the former is real broker
            # protection; the rest is covered by the watchdog.
            working = _find_working_stop(orders, sym)
            so = working if working is not None else _find_stop(orders, sym)
            stop = None
            if so is not None:
                try:
                    sp = float(so.get("stop_price") or 0)
                except (TypeError, ValueError):
                    sp = 0.0
                stop = {"price": sp,
                        "pct_below_entry": round((1 - sp / avg_entry) * 100, 2) if avg_entry else None,
                        "order_id": so.get("id"),
                        "working": working is not None,
                        "at_breakeven": bool(avg_entry and sp >= avg_entry)}

            # The stop the engine ENFORCES via the watchdog even when no working
            # broker stop rests (the Alpaca "held"-leg backstop). Always shown so
            # the dashboard reads "Stop 157.25 · engine-enforced" instead of a
            # bare "UNPROTECTED" scare when the broker leg is stuck.
            eff = _effective_stop(sym, avg_entry, out["regime"], working)
            watchdog_stop = round(eff, 2) if eff else None
            if working is not None:
                stop_status = "working"          # live broker stop resting
            elif watchdog_stop and cfg["armed"]:
                stop_status = "watchdog"         # engine-enforced backstop
            else:
                stop_status = "none"             # truly uncovered

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
                "watchdog_stop": watchdog_stop, "stop_status": stop_status,
                "target": target, "breakeven_trigger": bt,
                # Covered = a working broker stop OR the engine watchdog enforces
                # one. Only "none" (no working stop and nothing to enforce) is
                # truly uncovered.
                "protected": stop_status != "none",
            })
    except Exception as exc:                       # noqa: BLE001 — BrokerError is pre-scrubbed
        out["error"] = str(exc)
    # Real engine heartbeat (its 1-min tick), so the page can warn when order
    # management may be asleep while armed + market open. Computed last so it
    # sees the resolved market_open above.
    out["engine"] = _engine_liveness(cfg.get("last_tick_iso"),
                                     market_open=bool(out.get("market_open")),
                                     armed=bool(out.get("armed")))
    # Last tick's failures, surfaced so a swallowed adopt/watchdog error is
    # LOUD on the dashboard instead of dying in an in-memory summary.
    out["engine"]["last_errors"] = cfg.get("last_errors") or []
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
