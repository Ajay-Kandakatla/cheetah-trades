"""Accumulating ledger of daily retail order imbalance, so the predictive
question can be answered on a sample worth trusting.

Ajay 2026-08-14: "Add a cron job please" — after the first measurement came
back promising but resting on only **8 distinct days** (positive spread on 6/8
at 1d, 5/8 at 5d; the 5-day mean fell from +2.15% to +0.70% with the two best
sessions removed).

WHY A LEDGER AND NOT A LONG BACKTEST RUN
----------------------------------------
Settling it needs 60+ trading days. At ~11 s per symbol-day (a tape fetch plus
an NBBO fetch) a one-shot 60-day × 60-symbol run is ~11 HOURS — a job that ties
up the API container, competes with the trading-hours crons, and has to start
over if anything trips.

Recording instead costs ONE day per night (~11 min) and the sample grows by
itself. A bounded backfill chunk runs alongside it, so history fills in from
both ends and the wait is days, not months.

The ledger stores only the IMBALANCE. Forward returns are joined at read time
from the price cache — a day recorded today cannot know its own +5-day return,
and storing a placeholder that later gets filled is exactly how lookahead bugs
get in. `study()` simply ignores observations too recent to have an outcome.

Not advice. A measured relationship is a hint until the sample is large enough
to be one.
"""
from __future__ import annotations

import logging
import os
from datetime import date as _date, timedelta
from typing import Optional

log = logging.getLogger("orderflow.retail_history")

# Universe recorded nightly. Deliberately modest: every symbol costs ~11s, and
# a focused liquid set gives cleaner retail identification than a broad one
# (thin tape yields too few sub-penny prints to sign).
UNIVERSE_SIZE = 60

# Backfill chunk per night, on top of the current day.
BACKFILL_DAYS_PER_RUN = 6
BACKFILL_MAX_LOOKBACK = 120        # never reach further back than this

MIN_RETAIL_TRADES = 50             # matches retail.MIN_TRADES_FOR_READ


def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        c = MongoClient(url, serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        return c[os.getenv("MONGO_DB", "cheetah")].retail_flow_observations
    except Exception as exc:
        log.warning("retail-history: mongo unavailable: %s", exc)
        return None


def universe() -> list:
    from sepa import universe as U
    return list(U.fetch_sp500()[:UNIVERSE_SIZE])


def record_day(day: _date, symbols: Optional[list] = None) -> dict:
    """Measure and store retail imbalance for every symbol on `day`.

    Idempotent per (symbol, day) — safe to re-run, so a partial night can be
    resumed without double-counting.
    """
    from . import quotes as quotes_mod, retail as retail_mod, tape as tape_mod

    coll = _coll()
    if coll is None:
        return {"ok": False, "reason": "mongo unavailable"}
    syms = symbols or universe()

    stored, skipped, errors = 0, 0, 0
    for sym in syms:
        if coll.find_one({"symbol": sym, "day": str(day)}, {"_id": 1}):
            skipped += 1
            continue
        try:
            tr = tape_mod.fetch_trades(sym, day)
            qt = quotes_mod.fetch_quotes(sym, day)
            r = retail_mod.identify(tr, qt)
        except Exception as exc:
            log.debug("retail-history: %s %s failed: %s", sym, day, exc)
            errors += 1
            continue
        if not (r and r.get("signed") and r.get("imbalance_pct") is not None
                and r.get("retail_trades", 0) >= MIN_RETAIL_TRADES):
            skipped += 1
            continue
        coll.update_one(
            {"symbol": sym, "day": str(day)},
            {"$set": {"symbol": sym, "day": str(day),
                      "imbalance_pct": r["imbalance_pct"],
                      "retail_pct_of_volume": r.get("retail_pct_of_volume"),
                      "retail_trades": r.get("retail_trades")}},
            upsert=True)
        stored += 1

    log.info("retail-history: %s stored=%d skipped=%d errors=%d",
             day, stored, skipped, errors)
    return {"ok": True, "day": str(day), "stored": stored,
            "skipped": skipped, "errors": errors}


def _recorded_days(coll) -> set:
    return {d for d in coll.distinct("day")}


def backfill(chunk: int = BACKFILL_DAYS_PER_RUN,
             max_lookback: int = BACKFILL_MAX_LOOKBACK) -> dict:
    """Fill in the most recent UNrecorded weekdays, oldest-first within the
    chunk. Bounded so a nightly run always finishes."""
    coll = _coll()
    if coll is None:
        return {"ok": False, "reason": "mongo unavailable"}
    have = _recorded_days(coll)

    missing = []
    day = _date.today() - timedelta(days=1)
    while len(missing) < chunk and (_date.today() - day).days <= max_lookback:
        if day.weekday() < 5 and str(day) not in have:
            missing.append(day)
        day -= timedelta(days=1)

    out = [record_day(d) for d in reversed(missing)]
    return {"ok": True, "days": [o.get("day") for o in out],
            "stored": sum(o.get("stored", 0) for o in out)}


def study(horizons=(1, 3, 5), min_days: int = 20) -> dict:
    """Score the accumulated ledger. Forward returns joined at read time.

    Reports the DAY-LEVEL breakdown, not just the pooled spread — pooling 60
    symbols on the same day looks like 60 observations but is closer to one,
    which is the trap the first measurement fell into.
    """
    import statistics
    from collections import defaultdict
    from sepa import prices

    coll = _coll()
    if coll is None:
        return {"ok": False, "reason": "mongo unavailable"}
    rows = list(coll.find({}, {"_id": 0}))
    if not rows:
        return {"ok": True, "n": 0, "verdict": "ledger empty — cron has not run yet"}

    frames, per_day = {}, defaultdict(list)
    for r in rows:
        sym = r["symbol"]
        if sym not in frames:
            try:
                df = prices.load_prices(sym, period="2y")
                df = df.rename(columns={c: str(c).lower() for c in df.columns}) if df is not None else None
                frames[sym] = df
            except Exception:
                frames[sym] = None
        df = frames[sym]
        if df is None:
            continue
        dates = [d.date().isoformat() if hasattr(d, "date") else str(d)[:10] for d in df.index]
        closes = [float(c) for c in df["close"]]
        try:
            i = dates.index(r["day"])
        except ValueError:
            continue
        base = closes[i]
        rec = {"imbalance": r["imbalance_pct"]}
        usable = False
        for h in horizons:
            j = i + h
            if j < len(closes) and base > 0:
                rec[f"fwd_{h}d"] = (closes[j] / base - 1) * 100
                usable = True
        if usable:
            per_day[r["day"]].append(rec)

    day_spreads = {h: [] for h in horizons}
    for day, obs in per_day.items():
        if len(obs) < 10:
            continue
        for h in horizons:
            k = f"fwd_{h}d"
            v = [o for o in obs if o.get(k) is not None]
            if len(v) < 10:
                continue
            v.sort(key=lambda o: o["imbalance"])
            q = max(1, len(v) // 5)
            spread = (statistics.mean(o[k] for o in v[-q:])
                      - statistics.mean(o[k] for o in v[:q]))
            day_spreads[h].append(spread)

    n_days = len([d for d, o in per_day.items() if len(o) >= 10])
    out = {"ok": True, "n_observations": sum(len(o) for o in per_day.values()),
           "n_days": n_days, "horizons": {}}
    for h in horizons:
        s = day_spreads[h]
        if not s:
            continue
        pos = sum(1 for x in s if x > 0)
        out["horizons"][f"{h}d"] = {
            "days": len(s),
            "median_spread_pct": round(statistics.median(s), 3),
            "mean_spread_pct": round(statistics.mean(s), 3),
            "positive_days": pos,
            "positive_pct": round(100.0 * pos / len(s), 1),
            # Drop the two best days — the first measurement's 5d mean fell
            # from +2.15% to +0.70% under exactly this test.
            "mean_ex_top2_pct": (round(statistics.mean(sorted(s)[:-2]), 3)
                                 if len(s) > 3 else None),
        }

    if n_days < min_days:
        out["verdict"] = (f"accumulating — {n_days}/{min_days} days recorded. "
                          f"Too few to conclude anything.")
    else:
        ok = [v for v in out["horizons"].values()
              if v["positive_pct"] >= 60 and (v["mean_ex_top2_pct"] or 0) > 0]
        out["verdict"] = ("holds up — positive on a majority of days and survives "
                          "dropping the two best" if len(ok) == len(out["horizons"])
                          else "does NOT hold up once day-level consistency is required")
    return out


if __name__ == "__main__":                                   # pragma: no cover
    import json
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "nightly"
    if cmd == "study":
        print(json.dumps(study(), indent=2))
    else:
        y = _date.today() - timedelta(days=1)
        print(json.dumps({"today": record_day(y), "backfill": backfill()}, indent=2))
