"""FastAPI handlers for the catalysts module.

Endpoints:
  GET /catalysts/scan        — full scan (cached 5min during market, 30min after)
  GET /catalysts/{ticker}    — deep dive on a single ticker (no cache)

The scan endpoint is the workhorse:
  1. scanner.scan() — find tiny movers (~1-2s)
  2. parallel chatter + evidence enrichment for top N (~10-30s)
  3. parallel Gemma review for top M (~10-15s)
  4. score everything + return sorted by composite, with `quadrant` label

Total cold scan: ~30-45s. Cached after that.
"""
from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from . import scanner
from . import chatter as chatter_mod
from . import evidence as evidence_mod
from . import scorer
from . import gemma_review
from . import volume_alerts
from . import premarket as premarket_mod
from . import insiders
from . import calendar as cal_mod
from . import history as history_mod
from . import predictions as predictions_mod
from . import frenzy as frenzy_mod
from . import halts as halts_mod

log = logging.getLogger("catalysts.api")
router = APIRouter(tags=["catalysts"])

_CACHE_TTL_LIVE = 5 * 60        # 5min during market
_CACHE_TTL_AFTER = 30 * 60      # 30min after-hours
_CACHE_TTL_WEEKEND = 60 * 60    # 1h on weekends


# --- Mongo cache --------------------------------------------------------

def _cache_coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        return client[db]["catalysts_cache"]
    except Exception as exc:
        log.warning("catalysts cache mongo unavailable: %s", exc)
        return None


def _cache_get() -> Optional[dict]:
    coll = _cache_coll()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"_id": "scan_latest"})
        if not doc:
            return None
        ts = doc.get("cached_at")
        if not isinstance(ts, datetime):
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        from supply_demand.flow import market_status
        ms = market_status()
        ttl = (
            _CACHE_TTL_WEEKEND if ms["state"] == "weekend"
            else _CACHE_TTL_AFTER if not ms["is_live"]
            else _CACHE_TTL_LIVE
        )
        if age > ttl:
            return None
        payload = doc.get("payload")
        if isinstance(payload, dict):
            payload = dict(payload)
            payload["cached"] = True
            payload["cache_age_sec"] = round(age)
            return payload
    except Exception as exc:
        log.warning("catalysts cache get failed: %s", exc)
    return None


def _cache_put(payload: dict):
    coll = _cache_coll()
    if coll is None:
        return
    try:
        coll.update_one(
            {"_id": "scan_latest"},
            {"$set": {"cached_at": datetime.now(timezone.utc), "payload": payload}},
            upsert=True,
        )
    except Exception as exc:
        log.warning("catalysts cache put failed: %s", exc)


# --- Orchestration ------------------------------------------------------

def _enrich_one(c: dict) -> dict:
    """Pull chatter + evidence + score one candidate in parallel."""
    t = c["ticker"]
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_ch = ex.submit(chatter_mod.get_chatter, t)
        f_ev = ex.submit(evidence_mod.get_evidence, t)
        ch = f_ch.result() or {}
        ev = f_ev.result() or {}
    scores = scorer.score_candidate(c, ch, ev)
    return {**c, "chatter": ch, "evidence": ev, **scores}


def _full_scan(*,
               max_results: int = 25,
               min_change_pct: float = 8.0,
               max_share_price: float = 20.0,
               max_market_cap: float = 500_000_000,
               with_gemma: bool = True,
               gemma_top_n: int = 12) -> dict:
    """Run the whole pipeline. Returns the full payload."""
    t0 = time.time()

    # 1) Scan
    candidates = scanner.scan(
        max_share_price=max_share_price,
        max_market_cap=max_market_cap,
        min_abs_change_pct=min_change_pct,
        max_results=max_results,
    )
    t_scan = time.time() - t0

    # 2) Enrich each candidate (chatter + evidence) — heavily parallel
    t1 = time.time()
    with ThreadPoolExecutor(max_workers=10) as ex:
        enriched = list(ex.map(_enrich_one, candidates))
    t_enrich = time.time() - t1

    # 3) Sort by composite (evidence-weighted) so top N are scan-worthy
    enriched.sort(key=lambda c: c.get("composite_score") or 0, reverse=True)

    # 4) Gemma review only for top N (LLM is slowest part)
    t2 = time.time()
    if with_gemma and enriched:
        top = enriched[:gemma_top_n]
        rest = enriched[gemma_top_n:]
        with ThreadPoolExecutor(max_workers=4) as ex:
            reviews = list(ex.map(
                lambda c: gemma_review.review(c, c.get("chatter") or {},
                                              c.get("evidence") or {},
                                              {"chatter_score": c.get("chatter_score"),
                                               "evidence_score": c.get("evidence_score"),
                                               "quadrant": c.get("quadrant")}),
                top,
            ))
        for c, r in zip(top, reviews):
            c["review"] = r
        # Heuristic for the rest (cheap)
        for c in rest:
            c["review"] = gemma_review._heuristic_review(
                c, c.get("chatter") or {}, c.get("evidence") or {},
                {"chatter_score": c.get("chatter_score"),
                 "evidence_score": c.get("evidence_score"),
                 "quadrant": c.get("quadrant")},
            )
        enriched = top + rest
    t_review = time.time() - t2

    # 5) Bucket by quadrant for the UI
    by_quadrant: dict[str, list[dict]] = {"REAL": [], "PUMP_RISK": [], "OVERLOOKED": [], "DEAD": []}
    for c in enriched:
        by_quadrant.setdefault(c.get("quadrant", "DEAD"), []).append(c["ticker"])

    from supply_demand.flow import market_status
    ms = market_status()

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "market": ms,
        "candidates": enriched,
        "by_quadrant": by_quadrant,
        "n_total": len(enriched),
        "n_real": len(by_quadrant["REAL"]),
        "n_pump_risk": len(by_quadrant["PUMP_RISK"]),
        "n_overlooked": len(by_quadrant["OVERLOOKED"]),
        "n_dead": len(by_quadrant["DEAD"]),
        "filters": {
            "max_share_price": max_share_price,
            "max_market_cap": max_market_cap,
            "min_abs_change_pct": min_change_pct,
        },
        "timing": {
            "scan_sec": round(t_scan, 1),
            "enrich_sec": round(t_enrich, 1),
            "review_sec": round(t_review, 1),
            "total_sec": round(time.time() - t0, 1),
        },
        "cached": False,
        "cache_age_sec": 0,
    }


# --- Endpoints ----------------------------------------------------------

@router.get("/catalysts/news-read/{symbol}")
async def get_news_read(symbol: str, force: bool = Query(False, description="bypass the 15-min cache")):
    """JIT news verdict — does recent news make this name MORE buyable, LESS
    buyable, or a SELL? On-demand only (never preloaded): pulls the last 72h of
    headlines, classifies the net read (LLM when available, else keyword tone).
    Educational — a news-sentiment read, NOT advice."""
    import asyncio
    from .news_read import news_read
    return await asyncio.to_thread(news_read, symbol, force)


@router.get("/catalysts/scan")
async def scan_catalysts(
    force: bool = Query(False, description="bypass cache"),
    max_results: int = Query(25, ge=5, le=60),
    min_change_pct: float = Query(8.0, ge=2.0, le=50.0),
    max_share_price: float = Query(20.0, ge=0.1, le=100.0),
    max_market_cap: float = Query(500_000_000, ge=10_000_000),
    with_gemma: bool = Query(True),
):
    """Find tiny stocks moving on a catalyst or chatter.

    Returns ranked candidates with separate `chatter_score` and
    `evidence_score`, plus a quadrant label so the UI can immediately
    distinguish real catalysts from pump-and-dump candidates.

    Cached 5min during market, 30min after-hours, 1h on weekends.
    """
    if not force:
        cached = _cache_get()
        if cached:
            return cached

    payload = _full_scan(
        max_results=max_results,
        min_change_pct=min_change_pct,
        max_share_price=max_share_price,
        max_market_cap=max_market_cap,
        with_gemma=with_gemma,
    )
    _cache_put(payload)
    # Record an hourly snapshot for the timeline / multi-day / stale views.
    # The history module debounces — back-to-back calls within 30 min are
    # collapsed so we don't double-count transitions.
    try:
        history_mod.record_snapshot(payload)
    except Exception as exc:
        log.warning("history snapshot failed (non-fatal): %s", exc)
    return payload


@router.get("/catalysts/timeline")
async def get_timeline(session_date: Optional[str] = Query(None,
        description="ISO date in ET; defaults to today's session")):
    """Hour-by-hour intraday timeline of changes on the catalyst list.

    Returns each interval where any of these happened:
      - new tickers entered the list
      - tickers dropped off
      - chatter_score jumped ≥15 points
      - evidence_score jumped ≥10 points
      - quadrant transition (PUMP_RISK ↔ REAL etc.)
      - pump-phase transition (BREAKOUT → FRENZY → DISTRIBUTION etc.)

    Source: hourly snapshots recorded by /catalysts/scan + the cron job.
    """
    return history_mod.get_intraday_timeline(session_date)


@router.get("/catalysts/stale")
async def get_stale(
    min_age_hours: float = Query(3.0, ge=0.5, le=12.0,
        description="minimum hours on list before counting as stale"),
    max_score_drift: float = Query(8.0, ge=0.0, le=50.0,
        description="how much composite_score is allowed to drift while still 'stalled'"),
    session_date: Optional[str] = Query(None),
):
    """Tickers that have been on the catalyst list ≥N hours TODAY without
    composite_score moving meaningfully.

    Returns three buckets:
      - stable_winners  (REAL/OVERLOOKED) — sustained high-quality signal
      - stalled_chatter (PUMP_RISK) — chatter not converting to evidence
      - ambient_dead    (DEAD) — moves with no follow-through
    """
    return history_mod.get_stalled(
        min_age_hours=min_age_hours,
        max_score_drift=max_score_drift,
        session_date=session_date,
    )


@router.get("/catalysts/frenzy-radar")
async def get_frenzy_radar():
    """Pre-frenzy detector — surfaces tiny stocks BEFORE they go parabolic.

    Combines six leading-edge signals:
      1. quiet_volume_surge      Volume ≥3× avg AND price still calm <15%
      2. chatter_acceleration    This snapshot's velocity ≥1.5× prior's
      3. cross_platform_chatter  ST ≥10/24h AND Reddit ≥5/24h
      4. float_in_play           Volume / float ≥30%
      5. multi_day_accum_buildup CMF ≥40 over 10d, no >20% day in 5d
      6. fresh_appearance        First time on list in 5+ sessions

    Plus halt cross-reference (LUDP / T1 / T6 = parabolic phase).

    Tiers: IMMINENT ≥60 · SETUP 35-59 · EARLY 15-34 · QUIET <15
    """
    return frenzy_mod.build_frenzy_radar()


@router.get("/catalysts/halts")
async def get_halts(force: bool = Query(False)):
    """Today's NASDAQ trading halts (via free RSS feed).

    Halts — especially LUDP volatility halts — are highly correlated
    with frenzy moves. Cached 60s.
    """
    return halts_mod.get_today_halts(force=force)


@router.get("/catalysts/predictions")
async def get_predictions(force: bool = Query(False, description="bypass 10min cache")):
    """High-conviction tiny-stock predictions — synthesizes every signal we
    track into a single ranked list:
      - Real-catalyst quadrant (today)
      - Multi-day accumulation (Chaikin Money Flow)
      - Insider buy clusters (Form 4)
      - Stable-winner status (sustained REAL/OVERLOOKED)
      - Volume surge
      - Forward catalyst calendar (next 7d)
      - Multi-day appearance count
      - News tone (bullish vs bearish)
      - Pump-phase classification

    Penalties for: dilutive offering filed (HARD VETO),
    insider sell cluster, distribution-phase, already-extended,
    bearish-news, pure-chatter (PUMP_RISK with no evidence).

    Returns predictions ranked by conviction_score with HIGH/MEDIUM/WATCH/AVOID
    tier labels. Cached 10min during market, 30min after.
    """
    return predictions_mod.build_predictions(force=force)


@router.get("/catalysts/multi-day-accumulators")
async def get_multi_day_accum(
    min_session_appearances: int = Query(3, ge=2, le=10,
        description="minimum distinct session-dates seen"),
    lookback_days: int = Query(10, ge=3, le=30),
    min_accumulation_score: float = Query(30.0, ge=0.0, le=100.0,
        description="minimum Chaikin Money Flow score (-100..+100)"),
):
    """Tiny stocks accumulating across multiple days.

    Logic: tickers that have appeared in catalyst snapshots on ≥N distinct
    session-dates AND show positive Chaikin Money Flow (≥min score) over
    recent sessions. The intersection of "this keeps coming up" + "smart
    money is positioning" = the sustained accumulation signal.
    """
    return history_mod.get_multi_day_accumulators(
        min_session_appearances=min_session_appearances,
        lookback_days=lookback_days,
        min_accumulation_score=min_accumulation_score,
    )


@router.get("/catalysts/alerts/history")
async def get_alert_history(session_date: Optional[str] = Query(None,
        description="ISO date in ET; defaults to today")):
    """Recent volume-spike alerts fired this session.

    Frontend polls this every 30-60s and pops a browser Notification when
    a NEW ticker appears. Twilio is best-effort; the Mongo log is the
    source of truth.
    """
    return {
        "session_date": session_date,
        "alerts": volume_alerts.get_history(session_date),
    }


@router.post("/catalysts/alerts/run")
async def trigger_alert_sweep(threshold: float = Query(volume_alerts.DEFAULT_SURGE_THRESHOLD,
                                                        ge=2.0, le=20.0)):
    """Manually trigger a volume-spike sweep. Normally cron does this every
    5 min, but this is useful for testing / on-demand.
    """
    return volume_alerts.run(threshold=threshold)


@router.get("/catalysts/premarket")
async def get_premarket(
    min_change_pct: float = Query(5.0, ge=1.0, le=50.0),
    max_share_price: float = Query(20.0, ge=0.1, le=100.0),
    max_market_cap: float = Query(500_000_000, ge=10_000_000),
    max_results: int = Query(25, ge=5, le=60),
):
    """Pre-market scan — gappers in the 4:00-9:30 ET window.

    Different criteria than regular-session scan: no volume surge filter
    (no avg pre-market volume baseline available for free), but tighter
    on absolute price move.
    """
    return premarket_mod.scan_premarket(
        min_abs_change_pct=min_change_pct,
        max_price=max_share_price,
        max_cap=max_market_cap,
        max_results=max_results,
    )


@router.get("/catalysts/insiders/{ticker}")
async def get_insiders(ticker: str, days: int = Query(14, ge=3, le=60)):
    """Form 4 insider transactions for `ticker` over the last `days` days.

    Returns cluster_score + recent transactions. A cluster (3+ distinct
    insiders buying in last 7 days) is one of the highest-quality bullish
    signals available.
    """
    return insiders.get_insider_signal(ticker, days=days)


@router.get("/catalysts/calendar")
async def get_calendar(
    days: int = Query(30, ge=1, le=90),
    force: bool = Query(False, description="bypass 6h cache"),
):
    """Forward catalyst calendar — earnings, FDA readouts, macro events
    in the next `days` days. Cached 6h since these dates rarely change."""
    return cal_mod.get_calendar(days=days, force=force)


@router.get("/catalysts/{ticker}")
async def deep_dive(ticker: str, with_gemma: bool = Query(True)):
    """Deep dive on a single ticker — chatter + evidence + Gemma review.

    Useful when the user wants to check a specific name (e.g. RYOJ) that
    may not be in the top-mover list (e.g. moved before market open).
    No cache — always fresh.
    """
    t = ticker.upper()
    # Build a minimal candidate from yfinance/Massive
    try:
        import yfinance as yf
        tk = yf.Ticker(t)
        fi = tk.fast_info
        last = float(getattr(fi, "last_price", 0) or 0)
        prev = float(getattr(fi, "previous_close", 0) or 0)
        change_pct = round((last - prev) / prev * 100, 2) if prev else 0
        info = {}
        try: info = tk.info or {}
        except Exception: pass
        c = {
            "ticker": t,
            "company_name": info.get("shortName") or info.get("longName"),
            "sector": info.get("sector"),
            "price": last,
            "prev_close": prev,
            "change_pct": change_pct,
            "volume": int(getattr(fi, "last_volume", 0) or 0),
            "avg_volume_10d": float(getattr(fi, "ten_day_average_volume", 0) or 0) or None,
            "market_cap": float(getattr(fi, "market_cap", 0) or 0) or None,
            "float": info.get("floatShares") or info.get("sharesOutstanding"),
        }
        if c["avg_volume_10d"] and c["volume"]:
            c["volume_surge_ratio"] = round(c["volume"] / c["avg_volume_10d"], 1)
    except Exception as exc:
        return {"error": f"could not fetch quote for {t}: {exc}"}

    enriched = _enrich_one(c)
    scores = {
        "chatter_score": enriched.get("chatter_score"),
        "evidence_score": enriched.get("evidence_score"),
        "quadrant": enriched.get("quadrant"),
    }
    if with_gemma:
        enriched["review"] = gemma_review.review(
            enriched, enriched.get("chatter") or {}, enriched.get("evidence") or {}, scores,
        )
    else:
        enriched["review"] = gemma_review._heuristic_review(
            enriched, enriched.get("chatter") or {}, enriched.get("evidence") or {}, scores,
        )
    return enriched


# ============================================================================
# Product launches — new hardware / software / drug / vehicle announcements
# Surfaces "Dell launching new GPUs" type catalysts that often drive moves
# the market reflects before analysts catch up. Scanned by nightly cron in
# catalysts.product_launches; this endpoint reads from cache.
# ============================================================================
from catalysts import product_launches as _pl  # noqa: E402


@router.get("/catalysts/launches/{symbol}")
async def get_launches(symbol: str, days: int = Query(60, ge=1, le=180),
                       limit: int = Query(10, ge=1, le=30)):
    """Return cached product launches for a symbol. Read-only — the
    classification is done by the nightly cron, not the request path."""
    rows = _pl.list_launches(symbol, days=days, limit=limit)
    return {
        "symbol":   symbol.upper(),
        "count":    len(rows),
        "launches": rows,
    }


@router.post("/catalysts/launches/{symbol}/refresh")
async def refresh_launches(symbol: str, days: int = Query(30, ge=1, le=90)):
    """Force a fresh scan for one symbol — useful when investigating a
    sudden price move. Costs ~5-15s depending on news count.

    After the scan, publish a `launch.refreshed` SSE event with the new
    count so every open tab can update its chip without re-polling.
    """
    result = _pl.scan_symbol(symbol, days=days)

    # Re-count from cache against the same window the chip uses (45d) so
    # the pushed number matches what /catalysts/launches/batch would
    # return on a cold load. Cheap — single Mongo aggregate.
    try:
        from events import publish as bus_publish
        new_count = len(_pl.list_launches(symbol, days=45, limit=200))
        bus_publish("launch.refreshed", {
            "symbol": symbol.upper(),
            "count":  new_count,
        })
    except Exception as e:
        # Bus failures must never break the refresh response — log and
        # keep going. Worst case the chip stays stale until next mount.
        log.warning("events: failed to publish launch.refreshed for %s: %s", symbol, e)

    return result


@router.post("/catalysts/launches/batch")
async def get_launches_batch(payload: dict):
    """Batched launch counts for many symbols in one request.

    Used by SEPA card chips on the list view — without this each visible
    card fires its own GET, exceeding the browser's 6-concurrent-per-
    origin cap and stacking up "pending" requests in the network tab.
    One round-trip replaces N round-trips.

    Request:  {"symbols": ["AMD","MU",...], "days": 45}
    Response: {"counts": {"AMD": 3, "MU": 0, ...}}
    """
    symbols = payload.get("symbols") or []
    if not isinstance(symbols, list) or not symbols:
        return {"counts": {}}
    days = int(payload.get("days") or 45)
    days = max(1, min(180, days))

    # Cap to a reasonable batch — even on huge scans the list view shows
    # ~50 cards at a time. 200 is a generous ceiling.
    symbols = [str(s).upper().strip() for s in symbols if s][:200]

    # Single Mongo aggregation: group by symbol, count is_launch=True
    # docs whose published_at falls in the window.
    from datetime import datetime, timedelta, timezone
    coll = _pl._cache_coll()
    if coll is None:
        return {"counts": {s: 0 for s in symbols}}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    pipe = [
        {"$match": {
            "symbol":       {"$in": symbols},
            "is_launch":    True,
            "published_at": {"$gte": cutoff},
        }},
        {"$group": {"_id": "$symbol", "count": {"$sum": 1}}},
    ]
    counts: dict[str, int] = {s: 0 for s in symbols}
    for r in coll.aggregate(pipe):
        counts[r["_id"]] = int(r.get("count") or 0)
    return {"counts": counts}


@router.get("/catalysts/launches")
async def list_recent_launches(days: int = Query(14, ge=1, le=90),
                                limit: int = Query(50, ge=1, le=200)):
    """Aggregate recent launches across all tracked symbols. Used by the
    morning brief 'fresh catalysts' panel."""
    from datetime import datetime, timedelta, timezone
    coll = _pl._cache_coll()
    if coll is None:
        return {"launches": [], "count": 0}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = list(coll.find({
        "is_launch": True,
        "published_at": {"$gte": cutoff},
    }).sort("published_at", -1).limit(limit))
    for r in rows:
        r["_id"] = str(r["_id"])
    return {"count": len(rows), "launches": rows}


# ----------------------------------------------------------------------------
# Gabbar's Price Levels — hardcoded buy-zone bands ported from the
# eponymous TradingView script. Pure lookup; no compute / no upstream call.
# Returns 404 (not 200 + empty) for uncovered tickers so the frontend
# can branch on the response status alone without parsing a payload.
# ----------------------------------------------------------------------------
@router.get("/catalysts/gabbar-levels/{symbol}")
async def gabbar_levels(symbol: str):
    """Buy-zone bands for one ticker per Gabbar's curated Pine Script.
    See backend/catalysts/gabbar_levels.py for the source + attribution."""
    from . import gabbar_levels as gl
    payload = gl.get_bands(symbol)
    if not payload:
        # Frontend treats 404 as "not covered" and hides the section
        # entirely — avoids rendering an empty band card on tickers
        # the source table doesn't include.
        raise HTTPException(status_code=404, detail="symbol not in Gabbar's table")
    return payload


@router.get("/catalysts/gabbar-levels")
async def gabbar_levels_list():
    """Sorted list of tickers covered by the source table. Lets the
    frontend pre-decide whether to fetch (avoids 404 round-trips)."""
    from . import gabbar_levels as gl
    return {"symbols": gl.list_covered_symbols(), "attribution": gl.BAND_ATTRIBUTION}
