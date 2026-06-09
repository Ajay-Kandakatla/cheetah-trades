"""Forward paper-trade — the HONEST real-time-data track record.

Unlike the historical backtest (which has to ASSUME the spread), this records
every live TRIGGERED signal with the REAL live spread captured at entry, then
resolves each to stop / target / time-stop / EOD on the real tape. The resulting
net-of-cost track record uses real spreads — the cleanest read on whether these
detectors actually make money. Accumulates over sessions.

Mongo `scalping_paper`, one doc per (symbol, strategy, et_date). Driven by the
`scalping-paper-record` (every ~5 min in market hours) + `scalping-paper-resolve`
crons. Educational, not advice.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, date, time as dtime, timedelta, timezone
from typing import Optional

from . import costs, engine, sim

log = logging.getLogger("scalping.paper")


def _now_et() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        # Container TZ is America/New_York — local time IS ET and stays
        # DST-correct (fixed UTC-5 was wrong half the year; review fix 2026-06-09).
        return datetime.now().astimezone()


def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        c = MongoClient(url, serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        coll = c[os.getenv("MONGO_DB", "cheetah")]["scalping_paper"]
        try:
            coll.create_index([("symbol", 1), ("strategy", 1), ("et_date", 1)],
                              unique=True, name="scalp_paper_uniq")
        except Exception:
            pass
        return coll
    except Exception as exc:
        log.warning("mongo unavailable for scalping_paper: %s", exc)
        return None


def record_live(profile: str = "aggressive") -> dict:
    """Open a paper position for each NEW triggered+tradeable signal, capturing
    the live spread. De-duped per (symbol, strategy, ET day)."""
    coll = _coll()
    if coll is None:
        return {"recorded": 0, "error": "no_mongo"}
    n = _now_et()
    if not engine._market_open(n):
        return {"recorded": 0, "market_open": False}
    et_date = n.strftime("%Y-%m-%d")
    data = engine.scan_now(profile=profile)
    recorded = 0
    for s in data.get("signals", []):
        if s.get("status") != "triggered" or not s.get("tradeable"):
            continue
        key = {"symbol": s["symbol"], "strategy": s["strategy"], "et_date": et_date}
        if coll.find_one(key):
            continue
        spread_pct = (s.get("spread") or {}).get("spread_pct")
        doc = {
            **key, "side": s["side"],
            "entry_price": s["entry_price"], "stop": s["stop"], "target": s.get("target"),
            "risk": abs(s["entry_price"] - s["stop"]),
            "time_stop_min": s.get("time_stop_min"),
            "live_spread_pct": spread_pct,          # the REAL spread, captured at entry
            "entry_ts": datetime.now(timezone.utc).isoformat(),
            "opened_at": datetime.now(timezone.utc),
            "status": "open", "regime_aligned": s.get("regime_aligned"),
        }
        try:
            coll.update_one(key, {"$setOnInsert": doc}, upsert=True)
            recorded += 1
        except Exception as exc:
            log.debug("paper insert failed %s: %s", s["symbol"], exc)
    log.info("scalping paper: recorded=%d", recorded)
    return {"recorded": recorded, "market_open": True}


def resolve_open() -> dict:
    """Resolve every open paper position against the real tape; close on stop /
    target / time-stop / EOD with net-of-cost using the CAPTURED spread."""
    coll = _coll()
    if coll is None:
        return {"closed": 0, "error": "no_mongo"}
    from daytrading.data import load_intraday
    n = _now_et()
    today = n.date()
    # 5-min buffer past the bell so a long resolve pass can't prematurely
    # finalize eod_flat while the close is still printing (review fix).
    after_close = n.time() >= dtime(16, 5)
    closed = 0
    for doc in coll.find({"status": "open"}):
        try:
            d = datetime.strptime(doc["et_date"], "%Y-%m-%d").date()
        except Exception:
            continue
        df = load_intraday(doc["symbol"], d, include_premarket=False)
        if df is None or df.empty:
            continue
        rth = df[df["session"] == "rth"]
        out = sim.simulate_outcome(rth, doc)
        if out["outcome"] in ("no_data", "invalid_risk"):
            continue
        # eod_flat only finalizes after the close (else still live)
        if out["outcome"] == "eod_flat" and d == today and not after_close:
            continue
        cost = costs.round_trip_cost_pct(doc["entry_price"], spread_pct=doc.get("live_spread_pct"),
                                         is_short=doc["side"] == "short").get("total_pct") or 0.0
        ep = doc.get("entry_price")
        risk_pct = (doc["risk"] / ep * 100.0) if ep and ep > 0 else None
        net_pnl = out["pnl_pct"] - cost
        coll.update_one({"_id": doc["_id"]}, {"$set": {
            "status": "closed", **out, "cost_pct": round(cost, 4),
            "net_pnl_pct": round(net_pnl, 3),
            "net_r_multiple": round(net_pnl / risk_pct, 3) if risk_pct else None,
            "closed_at": datetime.now(timezone.utc),
        }})
        closed += 1
    log.info("scalping paper: closed=%d", closed)
    return {"closed": closed}


def track_record(days: int = 30) -> dict:
    """Open positions + closed track record (net-of-cost, real spreads)."""
    coll = _coll()
    if coll is None:
        return {"error": "no_mongo", "open": [], "closed_stats": {}, "n_closed": 0}
    cutoff = (_now_et().date() - timedelta(days=days)).strftime("%Y-%m-%d")
    open_rows, closed = [], []
    for doc in coll.find({"et_date": {"$gte": cutoff}}):
        doc.pop("_id", None)
        for k in ("opened_at", "closed_at"):
            if isinstance(doc.get(k), datetime):
                doc[k] = doc[k].isoformat()
        (open_rows if doc.get("status") == "open" else closed).append(doc)

    stats = {"n": 0, "note": "no closed paper trades yet — give it some sessions"}
    if closed:
        nets = [c.get("net_pnl_pct") for c in closed if c.get("net_pnl_pct") is not None]
        net_rs = [c.get("net_r_multiple") for c in closed if c.get("net_r_multiple") is not None]
        wins = [x for x in nets if x > 0]
        stats = {
            "n": len(closed),
            "net_win_rate_pct": round(len(wins) / len(nets) * 100, 1) if nets else None,
            "net_expectancy_r": round(sum(net_rs) / len(net_rs), 3) if net_rs else None,
            "net_total_pnl_pct": round(sum(nets), 2) if nets else None,
            "by_strategy": {},
        }
        for strat in ("stocks_in_play_orb", "shock_fade"):
            sub = [c.get("net_pnl_pct") for c in closed
                   if c["strategy"] == strat and c.get("net_pnl_pct") is not None]
            if sub:
                w = [x for x in sub if x > 0]
                stats["by_strategy"][strat] = {
                    "n": len(sub), "net_win_rate_pct": round(len(w) / len(sub) * 100, 1),
                    "net_total_pnl_pct": round(sum(sub), 2)}
    return {
        "generated_at_iso": datetime.now(timezone.utc).isoformat(),
        "open": sorted(open_rows, key=lambda r: r.get("opened_at", ""), reverse=True),
        "closed": sorted(closed, key=lambda r: r.get("closed_at", ""), reverse=True)[:60],
        "n_open": len(open_rows), "n_closed": len(closed),
        "closed_stats": stats,
        "disclaimer": ("Forward paper-trade with REAL captured spreads — the honest "
                       "read. Educational, not advice; most retail day-trading nets a loss."),
    }
