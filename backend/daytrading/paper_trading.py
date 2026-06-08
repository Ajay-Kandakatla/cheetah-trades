"""Live paper trading — runs all strategies against today's bars + tracks P&L.

State lives in Mongo collection `paper_trades`. One document per (symbol,
strategy, side, entry_ts) — naturally idempotent against re-runs of the
same scan.

Workflow on each /day/paper/today call:
  1. For each watchlist symbol, load today's intraday bars.
  2. Run every registered strategy's detect().
  3. For each detected signal: upsert into Mongo (no-op if it already exists).
  4. For each open position: simulate_outcome on today's bars, update if
     stop/target/EOD-flat reached, record exit.
  5. Aggregate stats: open positions, closed positions, today's hypothetical
     P&L (uniform 1% risk per trade → equity curve).

All P&L is hypothetical — no orders are placed anywhere. The point is to
validate the strategy in real time without risking capital.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, date
from typing import Optional

from .data import load_intraday
from .backtest import SIGNAL_REGISTRY

log = logging.getLogger("daytrading.paper")

# 1% risk per hypothetical trade — standard sizing for compounding equity curve
RISK_PER_TRADE_PCT = 1.0


def _coll():
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        c = client[db]["paper_trades"]
        c.create_index([("et_date", ASCENDING), ("symbol", ASCENDING),
                        ("strategy", ASCENDING), ("side", ASCENDING),
                        ("entry_ts", ASCENDING)],
                       unique=True, name="paper_uniq")
        c.create_index([("status", ASCENDING), ("et_date", ASCENDING)])
        return c
    except Exception as exc:
        log.warning("mongo unavailable for paper_trades: %s", exc)
        return None


def _scan_symbol(symbol: str, today: date, strategies: Optional[list[str]] = None) -> dict:
    """Detect signals on today's bars + open paper positions for new ones."""
    df = load_intraday(symbol, today, include_premarket=True)
    if df is None or df.empty:
        return {"symbol": symbol, "new": 0, "df": None}

    coll = _coll()
    new_count = 0
    selected = strategies or list(SIGNAL_REGISTRY.keys())
    for strat_name in selected:
        mod = SIGNAL_REGISTRY.get(strat_name)
        if mod is None:
            continue
        try:
            signals = [s for s in mod.detect(df) if s.get("side") == "long"]   # long-only (bull swing)
        except Exception as exc:
            log.warning("detect() failed %s/%s: %s", symbol, strat_name, exc)
            continue
        for sig in signals:
            doc = {
                "et_date": str(today),
                "symbol": symbol,
                "strategy": sig["strategy"],
                "side": sig["side"],
                "entry_ts": sig["entry_ts"],
                "entry_price": sig["entry_price"],
                "stop": sig["stop"],
                "target": sig["target"],
                "risk_pct": sig.get("risk_pct"),
                "reward_pct": sig.get("reward_pct"),
                "r_multiple_potential": sig.get("r_multiple_potential"),
                "reasons": sig.get("reasons", []),
                "status": "open",
                "opened_at": datetime.now(timezone.utc),
            }
            if coll is not None:
                try:
                    res = coll.update_one(
                        {"et_date": doc["et_date"], "symbol": doc["symbol"],
                         "strategy": doc["strategy"], "side": doc["side"],
                         "entry_ts": doc["entry_ts"]},
                        {"$setOnInsert": doc}, upsert=True,
                    )
                    if res.upserted_id is not None:
                        new_count += 1
                except Exception as exc:
                    log.warning("paper upsert failed: %s", exc)
    return {"symbol": symbol, "new": new_count, "df": df}


def _close_open_positions(today: date, dfs_by_symbol: dict) -> int:
    """For each open position today, run simulate_outcome and close if exited."""
    coll = _coll()
    if coll is None:
        return 0
    closed = 0
    for doc in coll.find({"et_date": str(today), "status": "open"}):
        df = dfs_by_symbol.get(doc["symbol"])
        if df is None:
            df = load_intraday(doc["symbol"], today, include_premarket=True)
            dfs_by_symbol[doc["symbol"]] = df
        if df is None or df.empty:
            continue
        mod = SIGNAL_REGISTRY.get(doc["strategy"])
        if mod is None:
            continue
        try:
            outcome = mod.simulate_outcome(df, doc)
        except Exception as exc:
            log.warning("simulate failed for %s: %s", doc.get("_id"), exc)
            continue
        if not outcome or outcome.get("outcome") in (None, "no_data", "no_exit"):
            continue
        # eod_flat only counts as closed AFTER end of RTH (16:00 ET)
        # Otherwise it's still open until the day finishes
        is_terminal = outcome.get("outcome") in ("stop", "target") or (
            outcome.get("outcome") == "eod_flat" and _is_after_rth_close(today)
        )
        if not is_terminal:
            continue
        update = {
            "status": "closed",
            "outcome": outcome.get("outcome"),
            "exit_ts": outcome.get("exit_ts"),
            "exit_price": outcome.get("exit_price"),
            "pnl_pct": outcome.get("pnl_pct"),
            "r_multiple": outcome.get("r_multiple"),
            "closed_at": datetime.now(timezone.utc),
        }
        coll.update_one({"_id": doc["_id"]}, {"$set": update})
        closed += 1
    return closed


def _is_after_rth_close(today: date) -> bool:
    """True if it's currently after 16:00 ET on `today`."""
    import pandas as pd
    now_et = pd.Timestamp.utcnow().tz_convert("America/New_York")
    if now_et.date() != today:
        return now_et.date() > today
    return now_et.hour >= 16


def scan_and_update(symbols: list[str], strategies: Optional[list[str]] = None) -> dict:
    """One call: scan + open new + close exited. Returns counts.

    Idempotent — running twice with no new bars produces zero new positions.
    """
    today = datetime.utcnow().date()
    dfs_by_symbol: dict = {}
    new_total = 0
    for s in symbols:
        r = _scan_symbol(s, today, strategies=strategies)
        new_total += r.get("new", 0)
        if r.get("df") is not None:
            dfs_by_symbol[s] = r["df"]
    closed = _close_open_positions(today, dfs_by_symbol)
    return {"new_signals": new_total, "closed_positions": closed,
            "scanned_symbols": len(symbols), "et_date": str(today)}


def list_today(symbols: Optional[list[str]] = None) -> dict:
    """Return all of today's paper positions + aggregate stats."""
    coll = _coll()
    if coll is None:
        return {"open": [], "closed": [], "stats": {"error": "mongo unavailable"}}
    today = datetime.utcnow().date()
    q = {"et_date": str(today)}
    if symbols:
        q["symbol"] = {"$in": [s.upper() for s in symbols]}

    open_pos = []
    closed_pos = []
    for doc in coll.find(q).sort("entry_ts", 1):
        doc["_id"] = str(doc["_id"])
        # Strip the datetime objects for JSON
        for f in ("opened_at", "closed_at"):
            if f in doc and hasattr(doc[f], "isoformat"):
                doc[f] = doc[f].isoformat()
        if doc.get("status") == "open":
            open_pos.append(doc)
        else:
            closed_pos.append(doc)

    stats = _aggregate_stats(closed_pos)
    return {
        "et_date": str(today),
        "open": open_pos,
        "closed": closed_pos,
        "open_count": len(open_pos),
        "closed_count": len(closed_pos),
        "stats": stats,
    }


def _aggregate_stats(closed: list[dict]) -> dict:
    if not closed:
        return {"n": 0, "note": "no closed positions yet today"}
    wins = [c for c in closed if (c.get("r_multiple") or 0) > 0]
    losses = [c for c in closed if (c.get("r_multiple") or 0) < 0]
    n = len(closed)
    win_rate = len(wins) / n * 100 if n else 0
    pnl_total_pct = sum((c.get("pnl_pct") or 0) for c in closed)
    avg_pnl = pnl_total_pct / n if n else 0
    avg_r = sum((c.get("r_multiple") or 0) for c in closed) / n if n else 0
    # Equity curve assuming RISK_PER_TRADE_PCT% risked per trade compounded
    equity_curve = [0.0]
    eq = 100.0
    for c in closed:
        r = c.get("r_multiple") or 0
        # Each R = RISK_PER_TRADE_PCT% of equity
        eq *= (1 + r * RISK_PER_TRADE_PCT / 100)
        equity_curve.append(round(eq - 100, 3))

    by_strategy: dict = {}
    for c in closed:
        s = c.get("strategy", "?")
        by_strategy.setdefault(s, []).append(c)
    strat_stats = {}
    for s, items in by_strategy.items():
        strat_wins = [x for x in items if (x.get("r_multiple") or 0) > 0]
        strat_stats[s] = {
            "n": len(items),
            "win_rate_pct": round(len(strat_wins) / len(items) * 100, 1) if items else 0,
            "avg_r": round(sum((x.get("r_multiple") or 0) for x in items) / len(items), 3) if items else 0,
            "total_pnl_pct": round(sum((x.get("pnl_pct") or 0) for x in items), 3),
        }

    return {
        "n": n,
        "n_wins": len(wins),
        "n_losses": len(losses),
        "win_rate_pct": round(win_rate, 1),
        "total_pnl_pct": round(pnl_total_pct, 3),
        "avg_pnl_pct": round(avg_pnl, 3),
        "avg_r_multiple": round(avg_r, 3),
        "equity_curve_pct": equity_curve,
        "by_strategy": strat_stats,
        "risk_per_trade_pct": RISK_PER_TRADE_PCT,
    }


def reset_today(symbols: Optional[list[str]] = None) -> dict:
    """Delete all paper trades for today. Used for manual cleanup / re-run."""
    coll = _coll()
    if coll is None:
        return {"deleted": 0, "error": "mongo unavailable"}
    today = datetime.utcnow().date()
    q = {"et_date": str(today)}
    if symbols:
        q["symbol"] = {"$in": [s.upper() for s in symbols]}
    res = coll.delete_many(q)
    return {"deleted": res.deleted_count, "et_date": str(today)}
