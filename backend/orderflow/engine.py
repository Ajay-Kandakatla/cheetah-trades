"""Orchestrator — one call turns a symbol into the full Tape snapshot.

Flow: newest session with prints (today ET, walking back over weekends /
holidays up to 5 days) → fetch tape → delta / big prints / bursts → 1-min
bars → volume profile + intraday EMAs → daily-trend gate + zones + GEX →
deterministic verdict → persist to Mongo `orderflow_snapshots` (_id
"SYM:YYYY-MM-DD") → append the verdict to the accuracy ledger.

On-demand cost: dominated by the trades fetch — ~1-6 pages (50k prints each)
for typical SEPA names, worst-case ~20-30s on megacap tape (page cap flags
`truncated`). The GET endpoint serves the cached snapshot instantly; the
POST /scan recomputes.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger("orderflow.engine")

MAX_LOOKBACK_DAYS = 5
STALE_AFTER_MIN_RTH = 20        # during the session a snapshot goes stale fast
SESSION_MEANINGFUL_AFTER = (9, 45)   # before open+15m, read the PRIOR session
MIN_TRADES_FOR_VERDICT = 500    # thinner tape -> verdict forced to WAIT


def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        c = MongoClient(url, serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        return c[os.getenv("MONGO_DB", "cheetah")].orderflow_snapshots
    except Exception:
        return None


def _now_et():
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/New_York"))


def apply_thin_gate(verdict: dict, n_trades: int) -> dict:
    """Halted / illiquid tape can't earn a green light: a BUY off fewer than
    MIN_TRADES_FOR_VERDICT prints is downgraded to WAIT. Pure — unit-tested."""
    if n_trades >= MIN_TRADES_FOR_VERDICT or verdict.get("verdict") != "BUY":
        return verdict
    return {**verdict, "verdict": "WAIT",
            "reason": (f"tape too thin ({n_trades} prints < {MIN_TRADES_FOR_VERDICT}) "
                       "— checks look good but there isn't enough tape to trust a BUY")}


def compute(symbol: str) -> Optional[dict]:
    """Fresh Tape snapshot for the most recent session with prints."""
    from . import tape, signals

    sym = (symbol or "").upper().strip()
    if not sym:
        return None

    trades = None
    now = _now_et()
    day = now.date()
    # Before open+15m today's tape is premarket-thin — a verdict off 200
    # prints is noise. Start from the prior session instead.
    if (now.hour, now.minute) < SESSION_MEANINGFUL_AFTER:
        day = day - timedelta(days=1)
    for _ in range(MAX_LOOKBACK_DAYS + 1):
        if day.weekday() < 5:
            trades = tape.fetch_trades(sym, day)
            if trades is not None and len(trades):
                break
        day = day - timedelta(days=1)
    if trades is None or not len(trades):
        return None

    # NBBO for the same session upgrades side-classification from the tick rule
    # to the quote rule (Lee-Ready). Best-effort: a failed or partial pull
    # degrades to the tick rule and is reported in `classification`, never
    # silently. See orderflow/quotes.py.
    nbbo = None
    try:
        from . import quotes as quotes_mod
        nbbo = quotes_mod.fetch_quotes(sym, day)
    except Exception as exc:
        log.debug("nbbo fetch failed for %s: %s", sym, exc)

    tape_read = tape.analyze_tape(trades, quotes=nbbo)
    last_price = tape_read["last_price"]

    bars = None
    try:
        from daytrading import data as dt_data
        bars = dt_data.load_intraday(sym, day, include_premarket=True,
                                     include_afterhours=True)
    except Exception as exc:
        log.debug("intraday bars failed for %s: %s", sym, exc)

    profile = tape.volume_profile(bars) if bars is not None else None
    ema_read = signals.intraday_ema_read(bars)
    trend_read = signals.daily_trend_read(sym)
    delta_read = signals.delta_check(tape_read["delta"])
    big_read = signals.big_buyers_check(tape_read["big_prints"])
    zone = signals.zone_read(sym, last_price)
    gex = signals.gex_context(sym)

    verdict = signals.composite_verdict(trend_read, ema_read, delta_read, big_read, zone)
    n_trades = tape_read["delta"]["n_trades"]
    thin = n_trades < MIN_TRADES_FOR_VERDICT
    verdict = apply_thin_gate(verdict, n_trades)

    snap = {
        "symbol": sym,
        "et_date": str(day),
        "as_of_utc": datetime.utcnow().isoformat() + "Z",
        "last_price": last_price,
        "tape": tape_read,
        "profile": profile,
        "emas": {"intraday": ema_read,
                 "daily": {"pass": trend_read["pass"], "detail": trend_read["detail"],
                           "source": trend_read["source"]}},
        "zone": zone,
        "gex": gex,
        "thin_tape": thin,
        **verdict,
        "method_note": ("Industry-standard order-flow read (tick-rule sides, ~75-80% "
                        "accuracy vs the full quote rule) — configured house thresholds, "
                        "not a book method. Decision-support, not advice."),
    }

    _save(snap)
    try:
        from . import history
        history.record(snap)
    except Exception as exc:
        log.warning("orderflow ledger record failed for %s: %s", sym, exc)
    return snap


def _save(snap: dict) -> None:
    coll = _coll()
    if coll is None:
        return
    try:
        doc = dict(snap)
        doc["_id"] = f"{snap['symbol']}:{snap['et_date']}"
        coll.update_one({"_id": doc["_id"]}, {"$set": doc}, upsert=True)
    except Exception as exc:
        log.warning("orderflow snapshot save failed: %s", exc)


def get_cached(symbol: str) -> Optional[dict]:
    """Most recent stored snapshot for the symbol (any date), with staleness."""
    coll = _coll()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"symbol": symbol.upper()}, sort=[("et_date", -1)])
        if not doc:
            return None
        doc.pop("_id", None)
        doc["stale"] = _is_stale(doc)
        return doc
    except Exception as exc:
        log.warning("orderflow snapshot read failed: %s", exc)
        return None


def _is_stale(doc: dict) -> bool:
    """Stale = not from the latest session, or >20 min old during RTH."""
    now = _now_et()
    try:
        as_of = datetime.fromisoformat((doc.get("as_of_utc") or "").rstrip("Z"))
        age_min = (datetime.utcnow() - as_of).total_seconds() / 60.0
    except Exception:
        return True
    in_rth = now.weekday() < 5 and (9, 30) <= (now.hour, now.minute) < (16, 0)
    if in_rth:
        return age_min > STALE_AFTER_MIN_RTH
    return doc.get("et_date") != _last_session_date()


def _last_session_date() -> str:
    now = _now_et()
    d = now.date()
    if (now.hour, now.minute) < SESSION_MEANINGFUL_AFTER:
        d = d - timedelta(days=1)      # same rule as compute(): today isn't a session yet
    while d.weekday() >= 5:
        d = d - timedelta(days=1)
    return str(d)
