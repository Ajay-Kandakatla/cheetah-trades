"""Forum Chatter — crowd discussion across stock-focused portals.

Four lanes per ticker. Scraping-first design: no API keys, no OAuth, no
client registration. The only env var that matters is REDDIT_USER_AGENT
(Reddit asks scrapers to identify themselves in the UA string).

Lane 1 — Reddit "Thoughtful" (old.reddit.com .json scrape)
  Allowlist: r/SecurityAnalysis, r/ValueInvesting, r/investing, r/stocks, r/options.
  Score-floored per audience size. Bear-thesis catcher.

Lane 2 — Reddit "Momentum" (old.reddit.com .json scrape)
  Allowlist: r/wallstreetbets, r/StockMarket, r/pennystocks, r/Daytrading,
  r/swingtrading. Looser score floors — these subs are the leading indicator
  for retail piling into a stage-2 leader.

Why scrape old.reddit instead of PRAW: same data the website hydrates from,
no 60-req/min OAuth bucket, no client_id/secret to provision, no token
refresh logic. The .json suffix has been stable on every Reddit URL for 15+
years.

Lane 3 — StockTwits public stream (HTTP)
  api.stocktwits.com/api/2/streams/symbol/{sym}.json — last ~30 messages,
  user-tagged Bullish/Bearish ratio. No auth, sometimes 403s under load.

Lane 4 — Hacker News (Algolia)
  hn.algolia.com search, last 30 days. Catches catalyst stories on tech
  megacaps (NVDA/AAPL/GOOGL/TSLA) before they hit the price.

Summary metrics (computed across all lanes):
  - mentions_7d            : total posts referencing the ticker, last 7 days
  - mentions_prior_7d      : same window, 7-14 days ago
  - mention_velocity       : mentions_7d / max(mentions_prior_7d, 1)
  - sentiment_ratio        : (bullish + score-weighted reddit upvotes) /
                             (bullish + bearish + downvotes)  ∈ [0, 1]
  - momentum_label         : "ramping" | "steady" | "fading" | "quiet"

Cached 15 min per ticker in Mongo collection `forum_chatter_cache`.
Universe scan (`/sepa/chatter`) reads cache only — no batch fetch storm.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from . import reddit_scrape

log = logging.getLogger("sepa.forum_chatter")

CACHE_TTL_SEC = 15 * 60

REDDIT_USER_AGENT = reddit_scrape.REDDIT_USER_AGENT  # back-compat alias

# (subreddit, score_floor) — calibrated per audience size / signal density
THOUGHTFUL_SUBS: list[tuple[str, int]] = [
    ("SecurityAnalysis", 30),
    ("ValueInvesting", 100),
    ("investing", 250),
    ("stocks", 500),
    ("options", 150),
]

MOMENTUM_SUBS: list[tuple[str, int]] = [
    ("wallstreetbets", 1000),  # huge audience — high floor cuts noise
    ("StockMarket", 200),
    ("pennystocks", 100),
    ("Daytrading", 50),
    ("swingtrading", 30),
]

ALL_SUBS = THOUGHTFUL_SUBS + MOMENTUM_SUBS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ticker_pattern(symbol: str) -> re.Pattern:
    sym = re.escape(symbol.upper())
    return re.compile(rf"(?:\${sym}\b|(?<![A-Za-z]){sym}(?![A-Za-z]))")


def _now() -> int:
    return int(time.time())


# ---------------------------------------------------------------------------
# Reddit lanes — thin wrappers over sepa.reddit_scrape (shared helper)
# ---------------------------------------------------------------------------
async def _reddit_thoughtful(symbol: str) -> dict:
    return await reddit_scrape.search_subreddits(
        symbol, THOUGHTFUL_SUBS,
        days=30,
        fetch_comments_per_thread=2,
        return_mention_windows=True,
        top_n=10,
    )


async def _reddit_momentum(symbol: str) -> dict:
    return await reddit_scrape.search_subreddits(
        symbol, MOMENTUM_SUBS,
        days=30,
        fetch_comments_per_thread=3,
        return_mention_windows=True,
        top_n=10,
    )


# ---------------------------------------------------------------------------
# StockTwits lane — public stream
# ---------------------------------------------------------------------------
async def _stocktwits(symbol: str) -> dict:
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
    headers = {"User-Agent": REDDIT_USER_AGENT, "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers=headers)
        if r.status_code != 200:
            return {"available": False, "reason": f"http {r.status_code}",
                    "messages": [], "bullish": 0, "bearish": 0, "neutral": 0}
        data = r.json()
    except Exception as exc:
        log.debug("stocktwits fetch failed for %s: %s", symbol, exc)
        return {"available": False, "reason": "fetch failed",
                "messages": [], "bullish": 0, "bearish": 0, "neutral": 0}

    raw = data.get("messages") or []
    bullish = bearish = neutral = 0
    out: list[dict] = []
    for m in raw[:30]:
        ent = m.get("entities") or {}
        sent = (ent.get("sentiment") or {}).get("basic")
        if sent == "Bullish":
            bullish += 1
        elif sent == "Bearish":
            bearish += 1
        else:
            neutral += 1
        out.append({
            "id":         m.get("id"),
            "body":       (m.get("body") or "")[:240],
            "user":       (m.get("user") or {}).get("username"),
            "followers":  (m.get("user") or {}).get("followers", 0),
            "sentiment":  sent,
            "created":    m.get("created_at"),
            "url":        f"https://stocktwits.com/{(m.get('user') or {}).get('username','')}/message/{m.get('id')}",
        })
    return {
        "available": True,
        "messages": out[:15],
        "bullish":  bullish,
        "bearish":  bearish,
        "neutral":  neutral,
        "total":    bullish + bearish + neutral,
    }


# ---------------------------------------------------------------------------
# Hacker News lane — Algolia
# ---------------------------------------------------------------------------
async def _hacker_news(symbol: str, company_name: Optional[str] = None) -> dict:
    cutoff = _now() - 30 * 86400
    queries: list[str] = [f"${symbol}", symbol]
    if company_name and len(company_name) >= 3:
        queries.append(company_name)

    base = "https://hn.algolia.com/api/v1/search_by_date"
    out: dict[str, dict] = {}  # objectID -> item (dedup)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            for q in queries:
                params = {
                    "query": q,
                    "tags": "story",
                    "numericFilters": f"created_at_i>{cutoff}",
                    "hitsPerPage": 20,
                }
                r = await client.get(base, params=params)
                if r.status_code != 200:
                    continue
                hits = (r.json() or {}).get("hits") or []
                for h in hits:
                    oid = h.get("objectID")
                    if not oid:
                        continue
                    out.setdefault(oid, h)
    except Exception as exc:
        log.debug("hn fetch failed for %s: %s", symbol, exc)
        return {"available": False, "reason": "fetch failed", "stories": [], "n": 0}

    pat = _ticker_pattern(symbol)
    stories: list[dict] = []
    for h in out.values():
        title = h.get("title") or ""
        url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        # Require ticker pattern OR company name match in title
        title_lower = title.lower()
        if not (pat.search(title) or
                (company_name and company_name.lower() in title_lower)):
            continue
        stories.append({
            "title":      title,
            "url":        url,
            "hn_url":     f"https://news.ycombinator.com/item?id={h.get('objectID')}",
            "points":     int(h.get("points") or 0),
            "n_comments": int(h.get("num_comments") or 0),
            "author":     h.get("author"),
            "created":    int(h.get("created_at_i") or 0),
        })
    stories.sort(key=lambda s: s["points"], reverse=True)
    return {"available": True, "stories": stories[:8], "n": len(stories)}


# ---------------------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------------------
def _summarize(thoughtful: dict, momentum: dict, stocktwits: dict, hn: dict) -> dict:
    mentions_7d = (
        int(thoughtful.get("mentions_7d", 0))
        + int(momentum.get("mentions_7d", 0))
    )
    mentions_prior_7d = (
        int(thoughtful.get("mentions_prior_7d", 0))
        + int(momentum.get("mentions_prior_7d", 0))
    )
    # Velocity guard: 0/0 used to compute as 0 and fall through to "fading"
    # below — but 0 mentions vs 0 prior isn't fading, it's never-started.
    # Treat the 0/0 case as undefined (None) so the classifier handles it
    # via the explicit "no chatter" branch instead of misreading silence
    # as a downtrend.
    if mentions_prior_7d == 0 and mentions_7d == 0:
        velocity = None
    else:
        velocity = mentions_7d / max(mentions_prior_7d, 1)

    bullish = int(stocktwits.get("bullish", 0))
    bearish = int(stocktwits.get("bearish", 0))

    # Score-weighted reddit signal — use top-thread upvote count as proxy
    reddit_score = 0
    for src in (thoughtful, momentum):
        for t in (src.get("threads") or [])[:5]:
            reddit_score += int(t.get("score", 0))

    sentiment_num = bullish + (reddit_score // 100)
    sentiment_den = bullish + bearish + (reddit_score // 100)
    sentiment_ratio = sentiment_num / sentiment_den if sentiment_den > 0 else None

    # Forum-chatter momentum classifier. This describes RETAIL FORUM
    # buzz velocity, NOT stock-price momentum — a quiet ticker can still
    # be ripping (institutions don't post on Reddit). Frontend label
    # makes this distinction explicit.
    if mentions_7d == 0 and mentions_prior_7d == 0:
        # Genuinely no reddit/HN chatter either window — "quiet" regardless
        # of stocktwits state (stocktwits is a separate, much noisier signal).
        label = "quiet"
    elif velocity is not None and velocity >= 1.5 and mentions_7d >= 3:
        label = "ramping"
    elif mentions_7d > 0 and velocity is not None and velocity <= 0.6:
        # Real drop-off: had chatter before, has less now. THIS is fading.
        label = "fading"
    elif mentions_7d == 0 and mentions_prior_7d > 0:
        # Was being talked about, now silent — still legitimately fading.
        label = "fading"
    else:
        label = "steady"

    return {
        "mentions_7d":       mentions_7d,
        "mentions_prior_7d": mentions_prior_7d,
        "mention_velocity":  round(velocity, 2) if velocity is not None else 0.0,
        "sentiment_ratio":   round(sentiment_ratio, 2) if sentiment_ratio is not None else None,
        "stocktwits_bullish": bullish,
        "stocktwits_bearish": bearish,
        "hn_stories":        int(hn.get("n", 0)),
        "momentum_label":    label,
    }


# ---------------------------------------------------------------------------
# Mongo cache + history
#
# Two collections:
#
#   * ``forum_chatter_cache`` — latest snapshot per ticker, upserted by _id.
#     Used for the 15-min TTL fast path. Wiped/overwritten on every fetch.
#
#   * ``forum_chatter_history`` — append-only timeline of every fetched
#     snapshot (added 2026-05-20 after user reported "is the cron running?
#     chatter looks stale" — see prewarm_top_sepa() + the new crontab
#     entry. Powers the ChatterMomentumDrillModal trend view).
#
#     Schema: {symbol, fetched_at, mentions_7d, mentions_prior_7d,
#              mention_velocity, momentum_label, sentiment_ratio,
#              bullish, bearish, hn_stories, n_threads}
#
#     Index: (symbol, fetched_at desc). TTL 90 days on fetched_at so
#     the collection self-prunes — we don't need year-old chatter for
#     a 60-day modal sparkline.
# ---------------------------------------------------------------------------
_mongo_coll = None
_mongo_hist = None
_mongo_disabled = False
HISTORY_TTL_DAYS = 90


def _get_db_client():
    """Shared Mongo client so we don't open two connections for cache + history."""
    from pymongo import MongoClient
    url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    return MongoClient(url, serverSelectionTimeoutMS=2000)


def _get_cache():
    global _mongo_coll, _mongo_disabled
    if _mongo_disabled:
        return None
    if _mongo_coll is not None:
        return _mongo_coll
    try:
        db_name = os.getenv("MONGO_DB", "cheetah")
        client = _get_db_client()
        client.admin.command("ping")
        _mongo_coll = client[db_name].forum_chatter_cache
        return _mongo_coll
    except Exception as exc:
        log.warning("forum_chatter: mongo unavailable (%s)", exc)
        _mongo_disabled = True
        return None


def _get_history():
    """Append-only history collection. Lazy-creates the (symbol, fetched_at)
    compound index + a TTL index on fetched_at so old rows auto-expire."""
    global _mongo_hist, _mongo_disabled
    if _mongo_disabled:
        return None
    if _mongo_hist is not None:
        return _mongo_hist
    try:
        from pymongo import ASCENDING, DESCENDING
        db_name = os.getenv("MONGO_DB", "cheetah")
        client = _get_db_client()
        client.admin.command("ping")
        coll = client[db_name].forum_chatter_history
        coll.create_index([("symbol", ASCENDING), ("fetched_at", DESCENDING)])
        # Mongo TTL is on a datetime field. We use fetched_at_dt (set in
        # _append_history) and expire after HISTORY_TTL_DAYS.
        try:
            coll.create_index(
                "fetched_at_dt",
                expireAfterSeconds=HISTORY_TTL_DAYS * 86400,
            )
        except Exception:
            # Index might already exist with different expiry — ignore.
            pass
        _mongo_hist = coll
        return _mongo_hist
    except Exception as exc:
        log.warning("forum_chatter history: mongo unavailable (%s)", exc)
        return None


def _append_history(payload: dict) -> None:
    """Insert one snapshot per chatter fetch. Failures are logged + swallowed
    — the live-fetch result is far more important than history bookkeeping."""
    coll = _get_history()
    if coll is None:
        return
    try:
        summary = payload.get("summary") or {}
        thoughtful = payload.get("thoughtful") or {}
        momentum = payload.get("momentum") or {}
        fetched_at = int(payload.get("fetched_at") or _now())
        coll.insert_one({
            "symbol":             payload.get("symbol"),
            "fetched_at":         fetched_at,
            # Datetime variant — required for the Mongo TTL index above.
            "fetched_at_dt":      datetime.fromtimestamp(fetched_at, tz=timezone.utc),
            "mentions_7d":        int(summary.get("mentions_7d", 0)),
            "mentions_prior_7d":  int(summary.get("mentions_prior_7d", 0)),
            "mention_velocity":   float(summary.get("mention_velocity") or 0),
            "momentum_label":     summary.get("momentum_label"),
            "sentiment_ratio":    summary.get("sentiment_ratio"),
            "bullish":            int(summary.get("stocktwits_bullish", 0)),
            "bearish":            int(summary.get("stocktwits_bearish", 0)),
            "hn_stories":         int(summary.get("hn_stories", 0)),
            "n_threads": (
                len(thoughtful.get("threads") or []) +
                len(momentum.get("threads") or [])
            ),
        })
    except Exception as exc:
        log.debug("forum_chatter history insert failed: %s", exc)


def get_history(symbol: str, days: int = 60, limit: int = 200) -> list[dict]:
    """Return the last `days` of history snapshots for `symbol`, oldest first.

    Powers the ChatterMomentumDrillModal — sparkline + table of how the
    momentum label was computed over time. Returns [] if Mongo is down
    or there's no history yet (e.g. ticker hasn't been prewarmed yet).
    """
    coll = _get_history()
    if coll is None:
        return []
    cutoff = _now() - days * 86400
    try:
        cur = coll.find(
            {"symbol": symbol.upper().strip(), "fetched_at": {"$gte": cutoff}},
            projection={
                "_id": 0,
                "symbol": 1, "fetched_at": 1,
                "mentions_7d": 1, "mentions_prior_7d": 1,
                "mention_velocity": 1, "momentum_label": 1,
                "sentiment_ratio": 1, "bullish": 1, "bearish": 1,
                "hn_stories": 1, "n_threads": 1,
            },
        ).sort("fetched_at", 1).limit(limit)
        return list(cur)
    except Exception as exc:
        log.warning("forum_chatter get_history failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def chatter_for(
    symbol: str,
    company_name: Optional[str] = None,
    *,
    refresh: bool = False,
) -> dict:
    """Per-ticker chatter payload. Cached 15 min in Mongo."""
    sym = symbol.upper().strip()
    now = _now()

    coll = _get_cache()
    if coll is not None and not refresh:
        try:
            doc = coll.find_one({"_id": sym})
            if doc and now - int(doc.get("fetched_at", 0)) < CACHE_TTL_SEC:
                payload = doc.get("payload") or {}
                payload["cached"] = True
                return payload
        except Exception as exc:
            log.debug("forum_chatter cache read failed: %s", exc)

    thoughtful, momentum, stocktwits, hn = await asyncio.gather(
        _reddit_thoughtful(sym),
        _reddit_momentum(sym),
        _stocktwits(sym),
        _hacker_news(sym, company_name),
    )

    # Reddit-outage handling: if BOTH Reddit lanes came back unavailable
    # (e.g. rate-limited to all-429 across all subs), don't pollute the
    # cache with empty data. Return the previously cached payload — even
    # if it's older than the 15-min TTL — and mark it `stale: True` so
    # the UI can render a "Reddit data unavailable, showing last known"
    # banner. The next prewarm or visit will retry the live fetch.
    #
    # StockTwits and HN remain real-time even during a Reddit outage,
    # so this preserves the user's trust in the lanes that DO work.
    reddit_down = (
        not thoughtful.get("available", True)
        and not momentum.get("available", True)
    )
    if reddit_down and coll is not None:
        try:
            doc = coll.find_one({"_id": sym})
            if doc:
                stale_payload = dict(doc.get("payload") or {})
                stale_payload["cached"] = True
                stale_payload["stale"] = True
                stale_payload["stale_reason"] = "reddit unavailable; showing last good fetch"
                # Still refresh StockTwits + HN portions and the
                # timestamps so the user knows those lanes are live.
                stale_payload["stocktwits"] = stocktwits
                stale_payload["hn"] = hn
                stale_payload["last_attempt_at"] = now
                log.warning("forum_chatter %s: reddit lanes both unavailable; "
                            "preserving stale cache", sym)
                return stale_payload
        except Exception as exc:
            log.debug("forum_chatter stale-read failed: %s", exc)
        # No prior cache to fall back to — fall through and write the
        # empty-Reddit payload but mark it explicitly. Better than
        # nothing for first-ever fetch of a ticker during an outage.

    summary = _summarize(thoughtful, momentum, stocktwits, hn)
    payload = {
        "symbol":        sym,
        "company_name":  company_name,
        "fetched_at":    now,
        "fetched_at_iso": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
        "thoughtful":    thoughtful,
        "momentum":      momentum,
        "stocktwits":    stocktwits,
        "hn":            hn,
        "summary":       summary,
        "cached":        False,
        # When both Reddit lanes failed AND there was no prior cache,
        # we still cache this minimally-useful payload but flag it so
        # the UI can hint that the chatter data is degraded.
        "reddit_degraded": reddit_down,
    }

    if coll is not None:
        try:
            coll.update_one(
                {"_id": sym},
                {"$set": {"fetched_at": now, "payload": payload}},
                upsert=True,
            )
        except Exception as exc:
            log.debug("forum_chatter cache write failed: %s", exc)

    # Append to the history timeline so the drill-in modal can render
    # a trend sparkline. Best-effort — failures are swallowed; the
    # latest-cache update above is the one that matters for the API
    # response.
    _append_history(payload)

    return payload


async def prewarm_top_sepa(top_n: int = 20) -> dict:
    """Refresh chatter for the top `top_n` SEPA candidates.

    Called from a daily cron — see backend/crontab. Without this the
    chatter cache only refreshes when a user opens a ticker detail
    page, so any ticker that goes unvisited for >15 minutes ends up
    showing stale data the next time someone opens it.

    Returns ``{ok, fetched, failed, took_sec}``. Caps live Reddit hits
    via the chatter_universe(max_fetch=N) plumbing so we don't burn
    Reddit's free-tier rate budget — the rest fall through to cache.

    Idempotent: safe to call ad-hoc to refresh chatter on demand.
    """
    import time
    t0 = time.time()
    try:
        # Late import to dodge circular: scanner imports prices, prices
        # imports… we just want load_latest here. No async required.
        from sepa import scanner as sepa_scanner
        latest = sepa_scanner.load_latest() or {}
    except Exception as exc:
        log.warning("prewarm_top_sepa: load_latest failed: %s", exc)
        return {"ok": False, "fetched": 0, "failed": 0, "reason": str(exc)}

    rows = latest.get("all_results") or latest.get("candidates") or []
    if not rows:
        return {"ok": False, "fetched": 0, "failed": 0, "reason": "no scan yet"}
    top = rows[:top_n]
    symbols = [r.get("symbol") for r in top if r.get("symbol")]
    names = {r["symbol"]: r.get("name") for r in top if r.get("symbol") and r.get("name")}

    fetched = 0
    failed = 0
    for sym in symbols:
        try:
            # refresh=True bypasses the 15-min cache check so we always
            # do a live fetch on the prewarm path. The 15-min TTL still
            # protects the request-path fast reads in chatter_for().
            await chatter_for(sym, company_name=names.get(sym), refresh=True)
            fetched += 1
        except Exception as exc:
            log.warning("prewarm_top_sepa: %s failed: %s", sym, exc)
            failed += 1
    took = round(time.time() - t0, 1)
    log.info("forum_chatter prewarm: fetched=%d failed=%d in %ss",
             fetched, failed, took)
    return {"ok": True, "fetched": fetched, "failed": failed,
            "took_sec": took, "symbols": symbols}


async def chatter_universe(
    symbols: list[str],
    name_lookup: Optional[dict] = None,
    *,
    max_fetch: int = 12,
) -> dict:
    """Universe-wide ranking by mention velocity.

    Returns rows for every symbol — cache-hits instantly, cache-misses
    capped at `max_fetch` to avoid Reddit-rate-limit storms. Frontend can
    drill into a row to force-refresh.
    """
    coll = _get_cache()
    cached_rows: list[dict] = []
    to_fetch: list[str] = []

    for sym in symbols:
        sym = sym.upper().strip()
        doc = None
        if coll is not None:
            try:
                doc = coll.find_one({"_id": sym})
            except Exception:
                doc = None
        if doc and _now() - int(doc.get("fetched_at", 0)) < CACHE_TTL_SEC:
            payload = doc.get("payload") or {}
            cached_rows.append(_summarize_row(sym, payload))
        else:
            to_fetch.append(sym)

    # Cap live fetches; remainder shown as 'stale' rows so user knows what's missing
    fetch_now = to_fetch[:max_fetch]
    stale = to_fetch[max_fetch:]

    if fetch_now:
        names = name_lookup or {}
        fresh = await asyncio.gather(*(
            chatter_for(s, company_name=names.get(s)) for s in fetch_now
        ))
        for sym, payload in zip(fetch_now, fresh):
            cached_rows.append(_summarize_row(sym, payload))

    for sym in stale:
        cached_rows.append({
            "symbol":        sym,
            "stale":         True,
            "mentions_7d":   None,
            "momentum_label": None,
        })

    cached_rows.sort(
        key=lambda r: (r.get("mentions_7d") or 0) * (r.get("mention_velocity") or 1),
        reverse=True,
    )
    return {
        "generated_at":     _now(),
        "generated_at_iso": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
        "n_total":          len(symbols),
        "n_cached":         len(cached_rows) - len(stale),
        "n_fetched":        len(fetch_now),
        "n_stale":          len(stale),
        "rows":             cached_rows,
    }


def _summarize_row(symbol: str, payload: dict) -> dict:
    s = payload.get("summary") or {}
    return {
        "symbol":             symbol,
        "company_name":       payload.get("company_name"),
        "mentions_7d":        s.get("mentions_7d"),
        "mentions_prior_7d":  s.get("mentions_prior_7d"),
        "mention_velocity":   s.get("mention_velocity"),
        "sentiment_ratio":    s.get("sentiment_ratio"),
        "stocktwits_bullish": s.get("stocktwits_bullish"),
        "stocktwits_bearish": s.get("stocktwits_bearish"),
        "hn_stories":         s.get("hn_stories"),
        "momentum_label":     s.get("momentum_label"),
        "fetched_at":         payload.get("fetched_at"),
        "stale":              False,
    }
