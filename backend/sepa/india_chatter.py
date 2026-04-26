"""Indian Stock Chatter — crowd discussion across India-native portals.

Three lanes per ticker. Same scraping-first design as forum_chatter — no
API keys, no OAuth. Universe is Nifty 50 (see india_universe.py).

Lane 1 — Reddit "Indian Markets" (old.reddit.com .json scrape)
  Allowlist: r/IndianStockMarket, r/IndiaInvestments, r/NSEbets,
  r/StockMarketIndia, r/DalalStreetTalks. Score floors calibrated per
  audience size. Scraping helper is the same one US forum_chatter uses.

Lane 2 — ValuePickr (Discourse JSON)
  Indian value-investor forum (forum.valuepickr.com) — high signal density,
  long-form research. Discourse natively serves /search.json for any query.
  No auth, no rate limit on read endpoints.

Lane 3 — MoneyControl News (HTML scrape)
  https://www.moneycontrol.com/news/tags/{slug}.html — most-iconic Indian
  retail news source, server-rendered HTML. Catches catalyst stories
  (results, M&A, regulatory) that move Indian stocks.

Summary metrics (computed across lanes):
  - mentions_7d / mentions_prior_7d / mention_velocity (Reddit only)
  - sentiment_ratio                : score-weighted upvote signal proxy
  - momentum_label                 : ramping | steady | fading | quiet

Cached 15 min in Mongo `india_chatter_cache`.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

import httpx

from . import reddit_scrape, india_universe

log = logging.getLogger("sepa.india_chatter")

CACHE_TTL_SEC = 15 * 60

# (subreddit, score_floor) — calibrated per audience
INDIAN_SUBS: list[tuple[str, int]] = [
    ("IndianStockMarket", 100),
    ("IndiaInvestments", 60),
    ("NSEbets", 30),
    ("StockMarketIndia", 20),
    ("DalalStreetTalks", 10),
]

VALUEPICKR_BASE = "https://forum.valuepickr.com"
MONEYCONTROL_NEWS = "https://www.moneycontrol.com/news/tags/{slug}.html"

DEFAULT_USER_AGENT = (
    "cheetah-market-app/0.1 (+https://github.com/Ajay-Kandakatla/cheetah-trades)"
)


def _now() -> int:
    return int(time.time())


# ---------------------------------------------------------------------------
# Lane 1 — Reddit · India
# ---------------------------------------------------------------------------
async def _reddit_india(symbol: str, search_terms: list[str]) -> dict:
    """Reddit lane — search the primary symbol *and* the company name.

    Indian retail uses bare ticker AND the marketing name interchangeably
    (e.g. "RELIANCE" and "Reliance"). The reddit_scrape helper takes one
    query, so we run it twice and merge — unique by post URL.
    """
    pat = reddit_scrape._ticker_pattern(symbol)  # type: ignore[attr-defined]

    # Run search for primary ticker (gets mention windows from this pass).
    primary = await reddit_scrape.search_subreddits(
        symbol, INDIAN_SUBS,
        days=30,
        fetch_comments_per_thread=2,
        return_mention_windows=True,
        top_n=15,
    )

    # If a company name is meaningfully different from the ticker, also
    # search by name and merge unique threads. Skip mention-window double-
    # counting — the ticker pass already covers it.
    threads: list[dict] = list(primary.get("threads") or [])
    seen_urls: set[str] = {t["url"] for t in threads}

    name_terms = [t for t in search_terms if t.lower() != symbol.lower()][:2]
    for term in name_terms:
        try:
            extra = await reddit_scrape.search_subreddits(
                term, INDIAN_SUBS,
                days=30,
                fetch_comments_per_thread=2,
                return_mention_windows=False,
                top_n=10,
            )
        except Exception as exc:
            log.debug("reddit india secondary search failed for %s: %s", term, exc)
            continue
        for t in (extra.get("threads") or []):
            if t["url"] in seen_urls:
                continue
            # Title or selftext should still mention the company in some form;
            # very short tickers like "ITC" can match too aggressively otherwise.
            title = t.get("title") or ""
            snippet = t.get("snippet") or ""
            if not (term.lower() in title.lower() or term.lower() in snippet.lower()
                    or pat.search(title) or pat.search(snippet)):
                continue
            seen_urls.add(t["url"])
            threads.append(t)

    threads.sort(key=lambda t: int(t.get("score", 0) or 0), reverse=True)
    return {
        "available":         primary.get("available", False),
        "reason":            primary.get("reason"),
        "threads":           threads[:12],
        "mentions_7d":       int(primary.get("mentions_7d", 0) or 0),
        "mentions_prior_7d": int(primary.get("mentions_prior_7d", 0) or 0),
    }


# ---------------------------------------------------------------------------
# Lane 2 — ValuePickr (Discourse)
# ---------------------------------------------------------------------------
async def _valuepickr(symbol: str, search_terms: list[str]) -> dict:
    """ValuePickr is a Discourse forum — every search has a .json variant.

    Discourse search returns matching topics + posts. We collect topics,
    de-dupe, sort by like_count + posts_count.
    """
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "application/json",
    }
    topics_by_id: dict[int, dict] = {}

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            for term in search_terms[:3]:
                try:
                    r = await client.get(
                        f"{VALUEPICKR_BASE}/search.json",
                        params={"q": term, "order": "latest"},
                    )
                except Exception as exc:
                    log.debug("valuepickr fetch failed for %s: %s", term, exc)
                    continue
                if r.status_code != 200:
                    continue
                try:
                    data = r.json()
                except Exception:
                    continue
                for t in (data.get("topics") or []):
                    tid = t.get("id")
                    if not tid or tid in topics_by_id:
                        continue
                    topics_by_id[tid] = t
    except Exception as exc:
        return {
            "available": False, "reason": f"http error: {exc}",
            "topics": [], "n": 0,
        }

    # Filter to last ~180 days, then sort by engagement
    cutoff = _now() - 180 * 86400
    out: list[dict] = []
    for t in topics_by_id.values():
        bumped_iso = t.get("bumped_at") or t.get("last_posted_at") or ""
        try:
            bumped = int(datetime.fromisoformat(bumped_iso.replace("Z", "+00:00")).timestamp())
        except Exception:
            bumped = 0
        if bumped and bumped < cutoff:
            continue
        out.append({
            "id":           t.get("id"),
            "title":        t.get("title") or t.get("fancy_title") or "",
            "slug":         t.get("slug") or "",
            "url":          f"{VALUEPICKR_BASE}/t/{t.get('slug')}/{t.get('id')}",
            "posts_count":  int(t.get("posts_count") or 0),
            "reply_count":  int(t.get("reply_count") or 0),
            "like_count":   int(t.get("like_count") or 0),
            "views":        int(t.get("views") or 0),
            "category_id":  t.get("category_id"),
            "bumped_at":    bumped,
        })

    # Rank by (likes + posts) — engagement-weighted
    out.sort(key=lambda r: r["like_count"] + r["posts_count"], reverse=True)

    return {
        "available": True,
        "topics":    out[:8],
        "n":         len(out),
    }


# ---------------------------------------------------------------------------
# Lane 3 — MoneyControl news
# ---------------------------------------------------------------------------
def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s or "").strip()


async def _moneycontrol(symbol: str, slug: Optional[str]) -> dict:
    """MoneyControl news-tag scrape.

    Page format: an unordered list of <li class="clearfix"> with the article
    title in <h2><a>, a short description in <p>, a publish-date <span class
    ="article_schedule">, and an image. We extract title + url + date.
    """
    if not slug:
        return {"available": False, "reason": "no slug for ticker", "articles": [], "n": 0}

    url = MONEYCONTROL_NEWS.format(slug=quote(slug))
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36"
        ),
        "Accept-Language": "en-IN,en;q=0.9",
    }
    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=True, headers=headers) as client:
            r = await client.get(url)
        if r.status_code != 200:
            return {
                "available": False, "reason": f"http {r.status_code}",
                "articles": [], "n": 0,
            }
        html = r.text
    except Exception as exc:
        log.debug("moneycontrol fetch failed for %s: %s", slug, exc)
        return {"available": False, "reason": "fetch failed", "articles": [], "n": 0}

    # Cheap regex-based extraction — avoids pulling in bs4 here.
    # Each news card: <li class="clearfix"> ... <h2><a href="..." title="...">title</a></h2>
    #                 ... <span class="article_schedule">date</span>
    # We capture href + visible title + date.
    article_pat = re.compile(
        r'<li[^>]*class="clearfix"[^>]*>.*?'
        r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>\s*</h2>'
        r'(?:.*?<p[^>]*>(.*?)</p>)?'
        r'(?:.*?<span[^>]*class="article_schedule"[^>]*>(.*?)</span>)?',
        re.DOTALL | re.IGNORECASE,
    )

    articles: list[dict] = []
    for m in article_pat.finditer(html):
        href, title, desc, date = m.groups()
        title_clean = _strip_html(title)
        if not title_clean:
            continue
        articles.append({
            "title":    title_clean[:240],
            "url":      href.strip(),
            "snippet":  _strip_html(desc or "")[:240],
            "date":     _strip_html(date or "")[:60],
        })
        if len(articles) >= 12:
            break

    return {
        "available": True,
        "articles":  articles,
        "n":         len(articles),
    }


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
def _summarize(reddit: dict, valuepickr: dict, moneycontrol: dict) -> dict:
    mentions_7d = int(reddit.get("mentions_7d") or 0)
    mentions_prior_7d = int(reddit.get("mentions_prior_7d") or 0)
    velocity = mentions_7d / max(mentions_prior_7d, 1)

    # Sentiment proxy: ValuePickr engagement + Reddit upvotes vs nothing
    # explicitly negative. Indian forums don't expose Bullish/Bearish tags
    # like StockTwits — so this is a "buzz-positive" signal, not a signed
    # sentiment ratio. UI labels it "Engagement" instead of Sentiment.
    reddit_score = sum(int((t.get("score") or 0)) for t in (reddit.get("threads") or [])[:5])
    vp_engagement = sum(int(t.get("like_count") or 0) + int(t.get("posts_count") or 0)
                        for t in (valuepickr.get("topics") or [])[:5])
    engagement_total = reddit_score + vp_engagement * 5  # weight VP higher (smaller userbase)

    if mentions_7d == 0 and not (valuepickr.get("topics") or []):
        label = "quiet"
    elif velocity >= 1.5 and mentions_7d >= 2:
        label = "ramping"
    elif velocity <= 0.6:
        label = "fading"
    else:
        label = "steady"

    return {
        "mentions_7d":       mentions_7d,
        "mentions_prior_7d": mentions_prior_7d,
        "mention_velocity":  round(velocity, 2),
        "engagement":        engagement_total,
        "vp_topics":         int(valuepickr.get("n") or 0),
        "mc_articles":       int(moneycontrol.get("n") or 0),
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
        _mongo_coll = client[db_name].india_chatter_cache
        return _mongo_coll
    except Exception as exc:
        log.warning("india_chatter: mongo unavailable (%s)", exc)
        _mongo_disabled = True
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def chatter_for(symbol: str, *, refresh: bool = False) -> dict:
    """Per-ticker Indian chatter payload. Cached 15 min in Mongo."""
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
            log.debug("india_chatter cache read failed: %s", exc)

    entry = india_universe.get(sym)
    company_name = entry["name"] if entry else None
    slug = entry["slug"] if entry else None
    search_terms = india_universe.search_terms_for(sym)

    reddit, vp, mc = await asyncio.gather(
        _reddit_india(sym, search_terms),
        _valuepickr(sym, search_terms),
        _moneycontrol(sym, slug),
    )

    summary = _summarize(reddit, vp, mc)
    payload = {
        "symbol":        sym,
        "company_name":  company_name,
        "fetched_at":    now,
        "fetched_at_iso": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
        "reddit":        reddit,
        "valuepickr":    vp,
        "moneycontrol":  mc,
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
            log.debug("india_chatter cache write failed: %s", exc)

    return payload


async def chatter_universe(*, max_fetch: int = 12) -> dict:
    """Universe-wide ranking against the Nifty 50 hardcoded list.

    Same staleness pattern as the US universe scan: cache hits return instantly,
    misses are fetched live up to `max_fetch` per call.
    """
    coll = _get_cache()
    rows: list[dict] = []
    to_fetch: list[str] = []

    for sym in india_universe.all_symbols():
        doc = None
        if coll is not None:
            try:
                doc = coll.find_one({"_id": sym})
            except Exception:
                doc = None
        if doc and _now() - int(doc.get("fetched_at", 0)) < CACHE_TTL_SEC:
            rows.append(_summarize_row(sym, doc.get("payload") or {}))
        else:
            to_fetch.append(sym)

    fetch_now = to_fetch[:max_fetch]
    stale = to_fetch[max_fetch:]

    if fetch_now:
        fresh = await asyncio.gather(*(chatter_for(s) for s in fetch_now))
        for sym, payload in zip(fetch_now, fresh):
            rows.append(_summarize_row(sym, payload))

    for sym in stale:
        entry = india_universe.get(sym) or {}
        rows.append({
            "symbol":         sym,
            "company_name":   entry.get("name"),
            "stale":          True,
            "mentions_7d":    None,
            "momentum_label": None,
            "engagement":     None,
            "vp_topics":      None,
            "mc_articles":    None,
        })

    rows.sort(
        key=lambda r: (r.get("engagement") or 0)
                      + (r.get("mentions_7d") or 0) * (r.get("mention_velocity") or 1),
        reverse=True,
    )
    return {
        "generated_at":     _now(),
        "generated_at_iso": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
        "n_total":          len(india_universe.all_symbols()),
        "n_cached":         len(rows) - len(stale),
        "n_fetched":        len(fetch_now),
        "n_stale":          len(stale),
        "rows":             rows,
    }


def _summarize_row(symbol: str, payload: dict) -> dict:
    s = payload.get("summary") or {}
    return {
        "symbol":            symbol,
        "company_name":      payload.get("company_name"),
        "mentions_7d":       s.get("mentions_7d"),
        "mentions_prior_7d": s.get("mentions_prior_7d"),
        "mention_velocity":  s.get("mention_velocity"),
        "engagement":        s.get("engagement"),
        "vp_topics":         s.get("vp_topics"),
        "mc_articles":       s.get("mc_articles"),
        "momentum_label":    s.get("momentum_label"),
        "fetched_at":        payload.get("fetched_at"),
        "stale":             False,
    }
