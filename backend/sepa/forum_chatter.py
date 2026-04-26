"""Forum Chatter — crowd discussion across stock-focused portals.

Three lanes per ticker:

Lane 1 — Reddit "Thoughtful" (PRAW)
  Allowlist: r/SecurityAnalysis, r/ValueInvesting, r/investing, r/stocks, r/options.
  Score-floored per audience size. Bear-thesis catcher.

Lane 2 — Reddit "Momentum" (PRAW)
  Allowlist: r/wallstreetbets, r/StockMarket, r/pennystocks, r/Daytrading,
  r/swingtrading. Looser score floors — these subs are the leading indicator
  for retail piling into a stage-2 leader.

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

log = logging.getLogger("sepa.forum_chatter")

CACHE_TTL_SEC = 15 * 60

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv(
    "REDDIT_USER_AGENT", "cheetah-market-app/0.1 (forum_chatter)"
)

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
# Reddit lane — PRAW (sync, wrapped in to_thread)
# ---------------------------------------------------------------------------
def _reddit_search_sync(
    symbol: str,
    subs: list[tuple[str, int]],
    *,
    include_top_comments: int = 0,
) -> dict:
    """Search a list of subreddits for a ticker. Returns threads + mention windows."""
    if not (REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET):
        return {
            "available": False,
            "reason": "no REDDIT_CLIENT_ID",
            "threads": [],
            "mentions_7d": 0,
            "mentions_prior_7d": 0,
        }
    try:
        import praw
    except ImportError:
        return {
            "available": False,
            "reason": "praw not installed",
            "threads": [],
            "mentions_7d": 0,
            "mentions_prior_7d": 0,
        }

    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
        )
        reddit.read_only = True
    except Exception as exc:
        return {
            "available": False,
            "reason": f"praw init failed: {exc}",
            "threads": [],
            "mentions_7d": 0,
            "mentions_prior_7d": 0,
        }

    pat = _ticker_pattern(symbol)
    threads: list[dict] = []
    now = time.time()
    cutoff_30d = now - 30 * 86400
    cutoff_7d = now - 7 * 86400
    cutoff_14d = now - 14 * 86400

    mentions_7d = 0
    mentions_prior_7d = 0

    for sub_name, score_floor in subs:
        try:
            sub = reddit.subreddit(sub_name)
            for post in sub.search(symbol, sort="top", time_filter="month", limit=20):
                if post.created_utc < cutoff_30d:
                    continue
                title = post.title or ""
                selftext = (post.selftext or "")[:500]
                if not pat.search(title) and not pat.search(selftext):
                    continue

                # Mention-velocity windows (any score, any thread that mentions ticker)
                if post.created_utc >= cutoff_7d:
                    mentions_7d += 1
                elif post.created_utc >= cutoff_14d:
                    mentions_prior_7d += 1

                # Threads list — gated by score floor
                if post.score < score_floor:
                    continue

                comments_out: list[dict] = []
                if include_top_comments > 0:
                    try:
                        post.comment_sort = "top"
                        post.comments.replace_more(limit=0)
                        for c in post.comments.list()[:include_top_comments]:
                            body = (getattr(c, "body", "") or "")[:280]
                            if not body:
                                continue
                            comments_out.append({
                                "score": int(getattr(c, "score", 0) or 0),
                                "body":  body,
                            })
                    except Exception as exc:
                        log.debug("comments fetch failed for %s: %s", post.id, exc)

                threads.append({
                    "subreddit":  sub_name,
                    "title":      title,
                    "url":        f"https://reddit.com{post.permalink}",
                    "score":      int(post.score),
                    "n_comments": int(post.num_comments),
                    "created":    int(post.created_utc),
                    "snippet":    selftext[:240],
                    "comments":   comments_out,
                })
        except Exception as exc:
            log.debug("reddit search failed for %s in r/%s: %s", symbol, sub_name, exc)

    threads.sort(key=lambda t: t["score"], reverse=True)
    return {
        "available": True,
        "threads": threads[:10],
        "mentions_7d": mentions_7d,
        "mentions_prior_7d": mentions_prior_7d,
    }


async def _reddit_thoughtful(symbol: str) -> dict:
    return await asyncio.to_thread(
        _reddit_search_sync, symbol, THOUGHTFUL_SUBS, include_top_comments=2
    )


async def _reddit_momentum(symbol: str) -> dict:
    return await asyncio.to_thread(
        _reddit_search_sync, symbol, MOMENTUM_SUBS, include_top_comments=3
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

    if mentions_7d == 0 and not (stocktwits.get("messages") or []):
        label = "quiet"
    elif velocity >= 1.5 and mentions_7d >= 3:
        label = "ramping"
    elif velocity <= 0.6:
        label = "fading"
    else:
        label = "steady"

    return {
        "mentions_7d":       mentions_7d,
        "mentions_prior_7d": mentions_prior_7d,
        "mention_velocity":  round(velocity, 2),
        "sentiment_ratio":   round(sentiment_ratio, 2) if sentiment_ratio is not None else None,
        "stocktwits_bullish": bullish,
        "stocktwits_bearish": bearish,
        "hn_stories":        int(hn.get("n", 0)),
        "momentum_label":    label,
    }


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
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        _mongo_coll = client[db_name].forum_chatter_cache
        return _mongo_coll
    except Exception as exc:
        log.warning("forum_chatter: mongo unavailable (%s)", exc)
        _mongo_disabled = True
        return None


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

    return payload


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
