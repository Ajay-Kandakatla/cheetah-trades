"""Smart Money & Sentiment — three lanes per ticker.

Lane 1 — Analyst consensus (Finnhub free tier).
  /stock/recommendation: monthly buckets (strongBuy/buy/hold/sell/strongSell)
  /stock/price-target:   targetMean, targetHigh, targetLow, numberOfAnalysts
  Pure ratings/targets only — Finnhub free does not expose per-analyst hit rates.

Lane 2 — Curated blog mentions (RSS).
  Damodaran "Musings on Markets" (Blogger Atom feed)
  Bespoke "Think B.I.G." blog
  Morningstar stock-analysis RSS
  Body-regex match on $TICKER and bare TICKER. Last 90 days.

Lane 3 — Reddit (old.reddit.com .json scrape — see sepa.reddit_scrape).
  Allowlist: r/SecurityAnalysis, r/ValueInvesting, r/investing, r/stocks, r/options.
  Score threshold scaled per sub. Last 30 days. No auth required.

13F is intentionally NOT included — see GRAPH_REPORT decision: 45-day lag + ETF
clone graveyard means it's net-negative for a 1-12wk swing-trading workflow.

Cached 15 min per ticker in Mongo collection `smart_money_cache`.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional

import httpx

from .providers import FINNHUB_API_KEY
from . import reddit_scrape

log = logging.getLogger("sepa.smart_money")

CACHE_TTL_SEC = 15 * 60

# Back-compat alias — UA + base URL now live in reddit_scrape
REDDIT_USER_AGENT = reddit_scrape.REDDIT_USER_AGENT

# (subreddit, score_floor) — calibrated per audience size / signal density
SUB_ALLOWLIST: list[tuple[str, int]] = [
    ("SecurityAnalysis", 30),
    ("ValueInvesting", 100),
    ("investing", 250),
    ("stocks", 500),
    ("options", 150),
]

BLOG_FEEDS = [
    {
        "name": "Damodaran",
        "url": "https://aswathdamodaran.blogspot.com/feeds/posts/default",
        "kind": "atom",
    },
    {
        "name": "Bespoke",
        "url": "https://www.bespokepremium.com/think-big-blog/feed/",
        "kind": "rss",
    },
    {
        "name": "Morningstar",
        "url": "https://www.morningstar.com/feeds/articles?category=stocks",
        "kind": "rss",
    },
]


# ---------------------------------------------------------------------------
# Lane 1 — Analyst consensus (Finnhub)
# ---------------------------------------------------------------------------
async def _analyst_consensus(symbol: str) -> dict:
    if not FINNHUB_API_KEY:
        return {"available": False, "reason": "no FINNHUB_API_KEY"}
    base = "https://finnhub.io/api/v1"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            recs_r, tgt_r = await asyncio.gather(
                client.get(f"{base}/stock/recommendation",
                           params={"symbol": symbol, "token": FINNHUB_API_KEY}),
                client.get(f"{base}/stock/price-target",
                           params={"symbol": symbol, "token": FINNHUB_API_KEY}),
            )
        recs = recs_r.json() if recs_r.status_code == 200 else []
        tgt = tgt_r.json() if tgt_r.status_code == 200 else {}
    except Exception as exc:
        log.warning("analyst consensus fetch failed for %s: %s", symbol, exc)
        return {"available": False, "reason": "fetch failed"}

    latest = recs[0] if recs else {}
    prev = recs[1] if len(recs) > 1 else {}

    def total(b: dict) -> int:
        return sum(int(b.get(k, 0) or 0) for k in
                   ("strongBuy", "buy", "hold", "sell", "strongSell"))

    def bullish(b: dict) -> int:
        return int(b.get("strongBuy", 0) or 0) + int(b.get("buy", 0) or 0)

    n = total(latest)
    n_prev = total(prev)
    return {
        "available": True,
        "period": latest.get("period"),
        "buckets": {
            "strong_buy": int(latest.get("strongBuy", 0) or 0),
            "buy":        int(latest.get("buy", 0) or 0),
            "hold":       int(latest.get("hold", 0) or 0),
            "sell":       int(latest.get("sell", 0) or 0),
            "strong_sell": int(latest.get("strongSell", 0) or 0),
        },
        "total_analysts": n,
        "bullish_pct": round(100 * bullish(latest) / n, 1) if n else None,
        "delta_bullish_mom": (bullish(latest) - bullish(prev)) if n_prev else 0,
        "target_mean":   tgt.get("targetMean"),
        "target_median": tgt.get("targetMedian"),
        "target_high":   tgt.get("targetHigh"),
        "target_low":    tgt.get("targetLow"),
        "target_n":      tgt.get("numberOfAnalysts"),
        "target_updated": tgt.get("lastUpdated"),
    }


# ---------------------------------------------------------------------------
# Lane 2 — Blog mentions (RSS)
# ---------------------------------------------------------------------------
def _ticker_pattern(symbol: str) -> re.Pattern:
    sym = re.escape(symbol.upper())
    # \$TICKER  or  bare TICKER bordered by non-letters (avoid matching inside words).
    return re.compile(rf"(?:\${sym}\b|(?<![A-Za-z]){sym}(?![A-Za-z]))")


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s or "")


async def _fetch_blog(client: httpx.AsyncClient, feed: dict) -> list[dict]:
    try:
        r = await client.get(feed["url"], headers={"User-Agent": REDDIT_USER_AGENT})
        if r.status_code != 200:
            return []
    except Exception as exc:
        log.debug("blog fetch failed for %s: %s", feed["name"], exc)
        return []
    try:
        root = ET.fromstring(r.text)
    except ET.ParseError:
        return []

    out: list[dict] = []
    if feed["kind"] == "atom":
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("a:entry", ns):
            title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
            link_el = entry.find("a:link[@rel='alternate']", ns)
            link = link_el.get("href") if link_el is not None else ""
            content = (entry.findtext("a:content", default="", namespaces=ns)
                       or entry.findtext("a:summary", default="", namespaces=ns)
                       or "")
            published = entry.findtext("a:published", default="", namespaces=ns) or ""
            out.append({"title": title, "link": link,
                        "body": _strip_html(content), "published": published,
                        "source": feed["name"]})
    else:  # rss 2.0
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = item.findtext("description") or ""
            published = item.findtext("pubDate") or ""
            out.append({"title": title, "link": link,
                        "body": _strip_html(desc), "published": published,
                        "source": feed["name"]})
    return out


async def _blog_mentions(symbol: str) -> list[dict]:
    pat = _ticker_pattern(symbol)
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        feeds = await asyncio.gather(*(_fetch_blog(client, f) for f in BLOG_FEEDS))
    hits: list[dict] = []
    for feed_items in feeds:
        for item in feed_items:
            haystack = f"{item['title']} {item['body']}"
            if pat.search(haystack):
                hits.append({
                    "source":    item["source"],
                    "title":     item["title"],
                    "link":      item["link"],
                    "published": item["published"],
                    "snippet":   _snippet_around(haystack, pat, 180),
                })
    hits.sort(key=lambda h: h.get("published", ""), reverse=True)
    return hits[:8]


def _snippet_around(text: str, pat: re.Pattern, width: int) -> str:
    m = pat.search(text)
    if not m:
        return text[:width]
    start = max(0, m.start() - width // 2)
    end = min(len(text), m.end() + width // 2)
    s = text[start:end].strip()
    return ("…" + s + "…") if start > 0 or end < len(text) else s


# ---------------------------------------------------------------------------
# Lane 3 — Reddit (old.reddit.com .json scrape via sepa.reddit_scrape)
# ---------------------------------------------------------------------------
async def _reddit_threads(symbol: str) -> dict:
    """Scrape the thoughtful-sub allowlist for ticker mentions.

    Returns the same shape the previous PRAW implementation did:
      {"available": bool, "threads": [...], "reason"?: str}
    Smart-money UI doesn't use mention windows, so we skip those for speed.
    """
    result = await reddit_scrape.search_subreddits(
        symbol, SUB_ALLOWLIST,
        days=30,
        fetch_comments_per_thread=0,        # smart_money doesn't render comments
        return_mention_windows=False,
        top_n=10,
    )
    # Trim mention-window keys callers don't expect to see here.
    return {
        "available": result.get("available", False),
        "reason":    result.get("reason"),
        "threads":   result.get("threads", []),
    }


# ---------------------------------------------------------------------------
# Main entry — combined, cached
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
        _mongo_coll = client[db_name].smart_money_cache
        return _mongo_coll
    except Exception as exc:
        log.warning("smart_money: mongo unavailable (%s)", exc)
        _mongo_disabled = True
        return None


async def smart_money_for(symbol: str) -> dict:
    sym = symbol.upper().strip()
    now = int(time.time())

    coll = _get_cache()
    if coll is not None:
        try:
            doc = coll.find_one({"_id": sym})
            if doc and now - int(doc.get("fetched_at", 0)) < CACHE_TTL_SEC:
                payload = doc.get("payload") or {}
                payload["cached"] = True
                return payload
        except Exception as exc:
            log.debug("smart_money cache read failed: %s", exc)

    analyst, blogs, reddit = await asyncio.gather(
        _analyst_consensus(sym),
        _blog_mentions(sym),
        _reddit_threads(sym),
    )
    payload = {
        "symbol":   sym,
        "fetched_at": now,
        "fetched_at_iso": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
        "analyst":  analyst,
        "blogs":    blogs,
        "reddit":   reddit,
        "cached":   False,
    }

    if coll is not None:
        try:
            coll.update_one(
                {"_id": sym},
                {"$set": {"fetched_at": now, "payload": payload}},
                upsert=True,
            )
        except Exception as exc:
            log.debug("smart_money cache write failed: %s", exc)

    return payload
