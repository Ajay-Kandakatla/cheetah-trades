"""Heavy research layer — slow-changing per-symbol blobs cached weekly.

Architecture: SEPA's analysis splits naturally into two cost tiers.

  ┌─────────────────────────────────────────────────────────────────┐
  │ RESEARCH (this module) — refreshed weekly on Sundays            │
  │   VCP base detection · power play · base count · CANSLIM        │
  │   fundamentals · liquidity baseline · ADR baseline · IPO age    │
  │   company name · stage classifier (snapshot)                    │
  │                                                                 │
  │ HOT (scanner.scan_universe_fast) — runs on demand, daily        │
  │   trend template · stage today · volume today · entry setup     │
  │   match against cached pivot · composite score                  │
  └─────────────────────────────────────────────────────────────────┘

Why split: VCP detection scans the full 2y price history for contractions
and tight bases — it costs ~1-2s per symbol. Across the Russell-1000 that's
20-30 minutes. But VCPs don't change day-to-day; once a base forms it stays.
Recomputing it daily is wasted work. Refreshing on Sundays gives Monday's
scan ~20-30s instead of 20+ minutes, and an on-demand button stays usable.

Mongo collection: `sepa_research_cache`
Cache TTL: 8 days (one cycle plus a grace day if Sunday cron skips)
"""
from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from . import (
    prices, vcp, power_play, base_count, canslim,
    adr, stage as stage_mod, company_names, moat as moat_mod,
)
from .ipo_age import age as ipo_age_for

log = logging.getLogger("sepa.research")

# 16 days, NOT 8: the refresh is weekly (Sunday 20:00 ET), so an 8-day TTL
# meant ONE missed Sunday put the entire cache over the cliff the following
# night — measured 2026-09-01: 3,642 fresh Monday evening, 21 by Tuesday
# 6am, and every Bonde-gated board (Deep Demand, Gabbar, Under Value) went
# empty. Fundamentals are quarterly; 16 days stale is a far smaller error
# than absent, and it leaves a full week of margin after a missed run.
CACHE_TTL_SEC = 16 * 24 * 3600


# ---------------------------------------------------------------------------
# Mongo cache
# ---------------------------------------------------------------------------
_mongo_coll = None
_mongo_disabled = False


def _get_cache():
    global _mongo_coll, _mongo_disabled
    if _mongo_disabled:
        return None
    if _mongo_coll is not None:
        return _mongo_coll
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        coll = client[db_name].sepa_research_cache
        coll.create_index([("symbol", ASCENDING)], unique=True)
        _mongo_coll = coll
        return _mongo_coll
    except Exception as exc:
        log.warning("research cache: Mongo unavailable (%s)", exc)
        _mongo_disabled = True
        return None


def get_research(symbol: str, max_age_sec: int = CACHE_TTL_SEC) -> Optional[dict]:
    """Return cached research blob or None if missing/stale."""
    coll = _get_cache()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"symbol": symbol.upper()})
        if not doc:
            return None
        age = time.time() - (doc.get("cached_at") or 0)
        if age >= max_age_sec:
            return None
        return doc
    except Exception:
        return None


def get_all_research(max_age_sec: int = CACHE_TTL_SEC) -> dict[str, dict]:
    """Bulk-load every fresh research blob — used by the fast scan."""
    coll = _get_cache()
    if coll is None:
        return {}
    cutoff = time.time() - max_age_sec
    try:
        return {
            doc["symbol"]: doc
            for doc in coll.find({"cached_at": {"$gte": cutoff}})
        }
    except Exception:
        return {}


def sales_snapshot(symbols: list[str],
                   max_age_sec: int = CACHE_TTL_SEC) -> dict[str, dict]:
    """Bonde sales block + revenue YoY for a set of symbols, one Mongo query.

    Feeds the Deep Demand and Gabbar Levels boards' falling-knife gate (Ajay
    2026-08-25: "both need pradeep bonde's sales and revenus quarter logic").
    Projection keeps the read tiny — the full research blob is ~everything.
    Returns {} on any failure; the boards treat a missing symbol as "sales
    unknown", never as a pass.
    """
    coll = _get_cache()
    if coll is None or not symbols:
        return {}
    cutoff = time.time() - max_age_sec
    try:
        out: dict[str, dict] = {}
        for doc in coll.find(
                {"symbol": {"$in": [s.upper() for s in symbols]},
                 "cached_at": {"$gte": cutoff}},
                {"symbol": 1, "cached_at": 1,
                 "fundamentals.sales": 1,
                 "fundamentals.rev_growth_q_pct": 1}):
            f = doc.get("fundamentals") or {}
            out[doc["symbol"]] = {
                "sales": f.get("sales"),
                "rev_growth_q_pct": f.get("rev_growth_q_pct"),
                "cached_at": doc.get("cached_at"),
            }
        return out
    except Exception as exc:
        log.warning("research sales_snapshot failed: %s", exc)
        return {}


def _put_research(symbol: str, payload: dict) -> None:
    coll = _get_cache()
    if coll is None:
        return
    try:
        payload["symbol"] = symbol.upper()
        payload["cached_at"] = int(time.time())
        coll.update_one({"symbol": symbol.upper()}, {"$set": payload}, upsert=True)
    except Exception as exc:
        log.warning("research cache write failed for %s: %s", symbol, exc)


# ---------------------------------------------------------------------------
# Per-symbol research compute
# ---------------------------------------------------------------------------
def compute_research(symbol: str, *, with_canslim: bool = True) -> Optional[dict]:
    """Run all the slow analyses for one symbol and persist to cache.

    Returns the full research blob, or None when the symbol has no usable
    price history. Skipped fields stay None so the hot scan can fill them.
    """
    df = prices.load_prices(symbol)
    if df is None or len(df) < 220:
        return None

    liq = adr.liquidity_check(df)
    adr_value = adr.adr_pct(df, period=20)

    vcp_info = vcp.detect(df)
    pp_info = power_play.detect(df)
    bc = base_count.count_bases(df)
    stg = stage_mod.classify(df)

    fundamentals = None
    moat = None
    if with_canslim:
        try:
            fundamentals = canslim.fundamentals_for(symbol)
        except Exception as exc:
            log.warning("canslim failed for %s: %s", symbol, exc)
        # Buffett-style economic moat — uses yfinance .info same as canslim,
        # so we already paid the network cost. Cheap to add.
        try:
            moat = moat_mod.compute_moat(symbol)
        except Exception as exc:
            log.warning("moat failed for %s: %s", symbol, exc)

    try:
        ipo_info = ipo_age_for(symbol)
    except Exception:
        ipo_info = None

    payload = {
        "name": company_names.name_for(symbol),
        "vcp": vcp_info,
        "power_play": pp_info,
        "base_count": bc,
        "stage_snapshot": stg,
        "fundamentals": fundamentals,
        "moat": moat,
        "liquidity": liq,
        "adr_baseline": adr_value,
        "ipo_age": ipo_info,
        "bars_seen": int(len(df)),
        "last_bar_date": df.index[-1].isoformat() if hasattr(df.index[-1], "isoformat") else str(df.index[-1]),
    }
    _put_research(symbol, payload)
    return payload


# ---------------------------------------------------------------------------
# Batch refresh — Sunday cron entry point
# ---------------------------------------------------------------------------
def refresh_universe(symbols: list[str], *, max_workers: int = 6,
                     with_canslim: bool = True) -> dict:
    """Refresh research for every symbol in the universe.

    Heavy operation — designed for the weekend cron slot. Uses a thread pool
    since each symbol is I/O-bound (provider fetch + Mongo write) plus a small
    CPU slice for VCP detection.
    """
    t0 = time.time()
    refreshed: list[str] = []
    failed: list[str] = []

    # Warm the company-name cache once up front
    try:
        company_names.bulk_warm(symbols)
    except Exception as exc:
        log.warning("company_names bulk_warm failed: %s", exc)

    def _one(sym: str) -> tuple[str, bool]:
        try:
            res = compute_research(sym, with_canslim=with_canslim)
            return sym, res is not None
        except Exception as exc:
            log.warning("research compute failed for %s: %s", sym, exc)
            return sym, False

    log.info("research: refreshing %d symbols (workers=%d)", len(symbols), max_workers)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for sym, ok in ex.map(_one, symbols):
            (refreshed if ok else failed).append(sym)
            if (len(refreshed) + len(failed)) % 50 == 0:
                log.info("research: %d/%d done (%.1fs elapsed)",
                         len(refreshed) + len(failed), len(symbols), time.time() - t0)

    duration = round(time.time() - t0, 2)
    log.info("research: DONE — refreshed=%d failed=%d in %ss",
             len(refreshed), len(failed), duration)
    return {
        "refreshed": refreshed,
        "failed": failed,
        "total": len(symbols),
        "duration_sec": duration,
    }


# ---------------------------------------------------------------------------
# Status — for the UI banner
# ---------------------------------------------------------------------------
def needs_refresh(min_surviving_frac: float = 0.6,
                  horizon_sec: int = 48 * 3600) -> tuple[bool, str]:
    """Whether a catch-up refresh should run. PURE decision over status().

    True when the fraction of blobs that will STILL be fresh `horizon_sec`
    from now falls under `min_surviving_frac` — i.e. the cache is already
    thin, or a single old batch is about to cross the TTL (the 2026-09-01
    cliff: one missed Sunday run emptied every Bonde-gated board
    overnight). An empty/unavailable cache always wants a refresh.
    """
    st = status()
    if not st.get("available"):
        return True, "research cache unavailable"
    total = st.get("total") or 0
    if total == 0:
        return True, "research cache empty"
    fresh = st.get("fresh") or 0
    expiring = st.get("expiring_48h") or 0
    surviving = max(0, fresh - expiring)
    frac = surviving / total
    if frac < min_surviving_frac:
        return True, (f"only {surviving}/{total} blobs survive the next "
                      f"{horizon_sec // 3600}h ({frac:.0%})")
    return False, f"{surviving}/{total} blobs survive ({frac:.0%}) — healthy"


def status() -> dict:
    """Return cache freshness summary for the UI."""
    coll = _get_cache()
    if coll is None:
        return {"available": False, "reason": "Mongo unavailable"}
    try:
        total = coll.count_documents({})
        if total == 0:
            return {"available": True, "total": 0, "fresh": 0,
                    "oldest_age_sec": None, "newest_age_sec": None}
        cutoff = time.time() - CACHE_TTL_SEC
        fresh = coll.count_documents({"cached_at": {"$gte": cutoff}})
        # blobs that are fresh NOW but cross the TTL within 48h — the
        # predictive read that catches a missed Sunday on Monday morning,
        # before the boards go dark rather than after
        expiring = coll.count_documents(
            {"cached_at": {"$gte": cutoff, "$lt": cutoff + 48 * 3600}})
        oldest = coll.find_one({}, sort=[("cached_at", 1)])
        newest = coll.find_one({}, sort=[("cached_at", -1)])
        now = time.time()
        return {
            "available": True,
            "total": total,
            "fresh": fresh,
            "expiring_48h": expiring,
            "stale": total - fresh,
            "oldest_age_sec": int(now - (oldest.get("cached_at") or 0)) if oldest else None,
            "newest_age_sec": int(now - (newest.get("cached_at") or 0)) if newest else None,
            "ttl_sec": CACHE_TTL_SEC,
        }
    except Exception as exc:
        return {"available": False, "reason": str(exc)}
