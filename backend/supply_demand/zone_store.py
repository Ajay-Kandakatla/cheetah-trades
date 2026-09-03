"""Zone store — the morning's daily supply/demand bands for every $1B+ name.

Ajay 2026-09-03: "NTAP did hit the demand zone in the morning and bounced
back immediately 20 point I am looking for those."

Why a store and not the demand board
------------------------------------
The demand board (supply_demand/demand_reentry) keeps demand bands with
MIN_TOUCHES=2 and MIN_ZONE_STRENGTH=40, and it reads the CLOSE. What NTAP's
09:30 low hit on 2026-09-03 was a BROKEN-SUPPLY shelf (161.78-167.54, one
touch, strength 18): old resistance acting as support. Every band involved
that morning had touches=1 and strength 15-24, so the board — and the
board-fed demand_alerts pass — are structurally blind to it. The bounce
watcher (supply_demand/zone_bounce_alerts.py) therefore needs EVERY band,
both kinds, per name, drawn once before the open. That is this module.

What is stored (one doc per symbol per ET session date)
-------------------------------------------------------
    {_id: "NTAP:2026-09-03", symbol, date, geom: "board",
     bands: [{kind: "supply"|"demand", lo, hi, touches, strength}, ...],
     atr14, prev_close, computed_at}

* Bands come from price_zones.compute(df, max_zones=None, **zone_geom()) —
  the demand board's geometry (swing 5 / merge 4% / half-width 1.75%), so a
  band here is the same band the Supply/Demand tab draws. max_zones=None
  keeps every cluster: the watcher wants the shelf price meets FIRST, not
  the four strongest.
* TODAY's rows are DROPPED before computing. The cached frame may already
  carry a partial today bar (patch_latest_closes / with_today_bar), and a
  band drawn from today's own low would be instantly "touched" — a
  tautology, not a level. prev_close and atr14 are read from the truncated
  frame for the same reason.
* NEVER price_zones.for_symbol (it overlays today's live bar via
  prices.with_today_bar — one snapshot HTTP call per symbol) and never
  promo_live._zones_compute. Bars come from sepa.prices.load_prices, i.e.
  the shared Mongo price cache; the provider is not called per symbol here.
* Universe = sepa.universe.load_universe("full") filtered to market cap
  >= $1B using the WEEKLY shares cache (sepa.volume_movers._shares_coll
  docs carry market_cap). Measured 2026-09-03: 1,751 names -> 1,124 with a
  known cap >= $1B. Unknown cap is excluded here — the watcher's own cap
  gate skips unknowns anyway.

Cron: 9:20 ET weekdays (backend/crontab), five minutes before the demand
board warms. python -m supply_demand.zone_store warms and reports.

Configured price-structure method, NOT a book method, no Minervini cites.
Decision support, not a buy signal, not advice.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from typing import Callable, Iterable, Optional
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
COLL = "zone_store"
GEOM_TAG = "board"                 # demand_reentry.zone_geom() — the board's resolution
MIN_CAP_USD = 1_000_000_000.0      # Ajay 2026-09-03: "billion or at least bigger than a billion"
MIN_BARS = 120                     # ~6 months: fewer bars is not enough structure to draw from
ATR_PERIOD = 14
DEFAULT_WORKERS = 6                # Mongo reads + pure compute; more just contends
DEFAULT_BUDGET_SEC = 240           # the 9:20 warm must be done before the 9:33 first pass


def _today_et(now: Optional[datetime] = None) -> date:
    return (now or datetime.now(ET)).astimezone(ET).date()


def _coll(coll=None):
    if coll is not None:
        return coll
    try:
        from portfolio.store import _get_db
        db = _get_db()
        return db[COLL] if db is not None else None
    except Exception as exc:
        log.warning("zone_store: no mongo: %s", exc)
        return None


# --------------------------------------------------------------------------
# Universe
# --------------------------------------------------------------------------
def big_cap_universe(universe: Optional[Iterable[str]] = None, caps: Optional[dict] = None,
                     floor: float = MIN_CAP_USD) -> list[str]:
    """load_universe('full') filtered to a KNOWN market cap >= floor, read
    from the weekly shares cache in one query — never the provider."""
    if universe is None:
        from sepa.universe import load_universe
        universe = load_universe("full")
    syms = [str(s).upper() for s in universe if s]
    if caps is None:
        caps = {}
        try:
            from sepa import volume_movers as vm
            coll = vm._shares_coll()
            if coll is not None:
                for d in coll.find({"_id": {"$in": syms}}, {"market_cap": 1}):
                    caps[d["_id"]] = d.get("market_cap")
        except Exception as exc:
            log.warning("zone_store: shares cache read failed: %s", exc)
    out = []
    for s in syms:
        try:
            if caps.get(s) is not None and float(caps[s]) >= floor:
                out.append(s)
        except (TypeError, ValueError):
            continue
    return out


# --------------------------------------------------------------------------
# One symbol
# --------------------------------------------------------------------------
def drop_today(df, today: date):
    """The frame without any row dated `today` (or later) — see the module
    docstring. Index is the DatetimeIndex load_prices returns."""
    if df is None or len(df) == 0:
        return df
    try:
        import pandas as pd
        cutoff = pd.Timestamp(today)
        idx = pd.to_datetime(df.index)
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_convert("America/New_York").tz_localize(None)
        return df[idx.normalize() < cutoff]
    except Exception as exc:                                    # pragma: no cover
        log.warning("zone_store: drop_today failed: %s", exc)
        return df


def _slim(z: dict, kind: str) -> Optional[dict]:
    try:
        return {"kind": kind, "lo": float(z["lo"]), "hi": float(z["hi"]),
                "touches": int(z.get("touches") or 0),
                "strength": float(z.get("strength") or 0.0)}
    except (KeyError, TypeError, ValueError):
        return None


def build_doc(symbol: str, df, today: date, *, compute: Optional[Callable] = None,
              atr: Optional[Callable] = None, now: Optional[datetime] = None) -> Optional[dict]:
    """The store document for one symbol, or None when the frame cannot
    support one (missing, too short after dropping today)."""
    frame = drop_today(df, today)
    if frame is None or len(frame) < MIN_BARS:
        return None
    if compute is None:
        from supply_demand import price_zones
        from supply_demand.demand_reentry import zone_geom
        geom = zone_geom()

        def compute(f):
            return price_zones.compute(f, max_zones=None, **geom)
    if atr is None:
        from supply_demand.patterns import atr as _atr

        def atr(f):
            return _atr(f, ATR_PERIOD)
    try:
        zones = compute(frame) or {}
    except Exception as exc:
        log.warning("zone_store: compute failed for %s: %s", symbol, exc)
        return None
    bands = []
    for kind, key in (("demand", "demand_zones"), ("supply", "supply_zones")):
        for z in zones.get(key) or []:
            b = _slim(z, kind)
            if b and b["hi"] >= b["lo"] > 0:
                bands.append(b)
    try:
        a14 = atr(frame)
        a14 = float(a14) if a14 else None
    except Exception:
        a14 = None
    try:
        prev_close = float(frame["close"].iloc[-1])
    except Exception:
        prev_close = None
    return {"_id": f"{symbol}:{today.isoformat()}", "symbol": symbol,
            "date": today.isoformat(), "geom": GEOM_TAG, "bands": bands,
            "atr14": a14, "prev_close": prev_close,
            "computed_at": (now or datetime.now(ET)).isoformat()}


# --------------------------------------------------------------------------
# Warm + load
# --------------------------------------------------------------------------
def warm(universe: Optional[Iterable[str]] = None, max_workers: int = DEFAULT_WORKERS,
         budget_sec: float = DEFAULT_BUDGET_SEC, *, loader: Optional[Callable] = None,
         coll=None, caps: Optional[dict] = None, today: Optional[date] = None,
         compute: Optional[Callable] = None, atr: Optional[Callable] = None) -> dict:
    """Compute and persist today's doc for every $1B+ name. Every input is
    injectable for tests; the cron passes none. A symbol whose frame is None
    (delisted, never cached) is counted and skipped, never raised."""
    t0 = time.time()
    today = today or _today_et()
    syms = big_cap_universe(universe, caps)
    coll = _coll(coll)
    if loader is None:
        from sepa import prices

        def loader(sym):
            return prices.load_prices(sym, period="2y")

    def one(sym):
        try:
            df = loader(sym)
        except Exception as exc:
            log.debug("zone_store: load failed for %s: %s", sym, exc)
            df = None
        return sym, build_doc(sym, df, today, compute=compute, atr=atr)

    stored = skipped = failed = 0
    timed_out = False
    with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as pool:
        futs = {pool.submit(one, s): s for s in syms}
        for fut in as_completed(futs):
            if time.time() - t0 > budget_sec:
                timed_out = True
                break
            try:
                sym, doc = fut.result()
            except Exception as exc:                             # pragma: no cover
                log.warning("zone_store: worker failed: %s", exc)
                failed += 1
                continue
            if doc is None:
                skipped += 1
                continue
            if coll is not None:
                try:
                    coll.replace_one({"_id": doc["_id"]}, doc, upsert=True)
                except Exception as exc:
                    log.warning("zone_store: write failed for %s: %s", sym, exc)
                    failed += 1
                    continue
            stored += 1
        if timed_out:
            for f in futs:
                f.cancel()
    out = {"date": today.isoformat(), "universe": len(syms), "stored": stored,
           "skipped": skipped, "failed": failed, "timed_out": timed_out,
           "seconds": round(time.time() - t0, 1)}
    purge(coll=coll)
    log.info("zone_store: warm %s", out)
    return out


KEEP_DAYS = 7   # ~1,124 docs × ~15 bands a day; a week is plenty for replays


def purge(keep_days: int = KEEP_DAYS, coll=None, today: Optional[date] = None) -> int:
    """Drop store docs older than `keep_days` sessions; returns the count."""
    coll = _coll(coll)
    if coll is None:
        return 0
    cutoff = (today or _today_et()) - timedelta(days=keep_days)
    try:
        res = coll.delete_many({"date": {"$lt": cutoff.isoformat()}})
        n = int(getattr(res, "deleted_count", 0) or 0)
    except Exception as exc:
        log.warning("zone_store: purge failed: %s", exc)
        return 0
    if n:
        log.info("zone_store: purged %d docs older than %s", n, cutoff.isoformat())
    return n


def load(symbols: Optional[Iterable[str]] = None, day: Optional[date] = None,
         coll=None) -> dict:
    """{SYMBOL: doc} for `day` (default today ET). `symbols` None = every
    stored name for that date. Empty dict when the store is cold."""
    coll = _coll(coll)
    if coll is None:
        return {}
    day = day or _today_et()
    q: dict = {"date": day.isoformat() if hasattr(day, "isoformat") else str(day)}
    if symbols is not None:
        q["symbol"] = {"$in": [str(s).upper() for s in symbols]}
    try:
        return {d["symbol"]: d for d in coll.find(q)}
    except Exception as exc:
        log.warning("zone_store: load failed: %s", exc)
        return {}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    res = warm()
    log.info("ZONE-STORE: date=%s universe=%s stored=%s skipped=%s failed=%s "
             "timed_out=%s seconds=%s", res["date"], res["universe"], res["stored"],
             res["skipped"], res["failed"], res["timed_out"], res["seconds"])
