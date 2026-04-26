"""Reddit scraping helper — shared across forum_chatter + smart_money.

Hits old.reddit.com/.json directly. No PRAW, no OAuth, no client_id. Same
data the website hydrates from. Stable for 15+ years on every Reddit URL.

Public API:
    await search_subreddits(symbol, subs, ...) -> dict

Returns the same shape both lanes have always used:
    {
      "available":         bool,
      "reason":            str,           # only when available=False
      "threads":           [{...}, ...],  # top-N by score, descending
      "mentions_7d":       int,           # 0 if return_mention_windows=False
      "mentions_prior_7d": int,           # 0 if return_mention_windows=False
    }

Each thread:
    {
      "subreddit":  str,
      "title":      str,
      "url":        "https://reddit.com/r/.../comments/.../...",
      "score":      int,
      "n_comments": int,
      "created":    int,    # unix-utc seconds
      "snippet":    str,    # first 240 chars of selftext
      "comments":   [{"score": int, "body": str}, ...],  # empty unless requested
    }
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time

import httpx

log = logging.getLogger("sepa.reddit_scrape")

REDDIT_USER_AGENT = os.getenv(
    "REDDIT_USER_AGENT",
    "cheetah-market-app/0.1 (+https://github.com/Ajay-Kandakatla/cheetah-trades)",
)
REDDIT_BASE = "https://old.reddit.com"
REDDIT_TIMEOUT = 12


def _ticker_pattern(symbol: str) -> re.Pattern:
    sym = re.escape(symbol.upper())
    return re.compile(rf"(?:\${sym}\b|(?<![A-Za-z]){sym}(?![A-Za-z]))")


def _headers() -> dict:
    return {
        "User-Agent": REDDIT_USER_AGENT,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }


async def _fetch_top_comments(
    client: httpx.AsyncClient, permalink: str, n: int
) -> list[dict]:
    if not permalink or n <= 0:
        return []
    url = f"{REDDIT_BASE}{permalink.rstrip('/')}.json"
    try:
        r = await client.get(
            url,
            params={"limit": str(n + 5), "sort": "top"},
            headers=_headers(),
        )
        if r.status_code != 200:
            return []
        data = r.json()
    except Exception as exc:
        log.debug("reddit comments fetch failed for %s: %s", permalink, exc)
        return []

    if not isinstance(data, list) or len(data) < 2:
        return []
    children = (data[1].get("data") or {}).get("children") or []

    out: list[dict] = []
    for c in children:
        if c.get("kind") != "t1":
            continue
        cd = c.get("data") or {}
        body = (cd.get("body") or "").strip()
        if not body or body in ("[deleted]", "[removed]"):
            continue
        out.append({
            "score": int(cd.get("score", 0) or 0),
            "body":  body[:280],
        })
        if len(out) >= n:
            break
    return out


async def _search_one_sub(
    client: httpx.AsyncClient,
    symbol: str,
    sub_name: str,
    score_floor: int,
    pat: re.Pattern,
    cutoffs: tuple[float, float, float],  # (window_start, 7d_ago, 14d_ago)
    fetch_comments_per_thread: int,
    return_mention_windows: bool,
) -> tuple[list[dict], int, int]:
    """Search one subreddit. Returns (qualifying_threads, m_7d, m_prior_7d)."""
    cutoff_window, cutoff_7d, cutoff_14d = cutoffs
    url = f"{REDDIT_BASE}/r/{sub_name}/search.json"
    params = {
        "q":           symbol,
        "restrict_sr": "1",
        "sort":        "top",
        "t":           "month",
        "limit":       "25",
    }
    try:
        r = await client.get(url, params=params, headers=_headers())
        if r.status_code != 200:
            log.debug("reddit r/%s returned %d for %s", sub_name, r.status_code, symbol)
            return [], 0, 0
        data = r.json()
    except Exception as exc:
        log.debug("reddit search failed for %s in r/%s: %s", symbol, sub_name, exc)
        return [], 0, 0

    children = (data.get("data") or {}).get("children") or []
    candidates: list[dict] = []
    m_7d = m_prior_7d = 0

    for c in children:
        post = c.get("data") or {}
        created = float(post.get("created_utc") or 0)
        if created < cutoff_window:
            continue
        title = post.get("title") or ""
        selftext = (post.get("selftext") or "")[:500]
        if not pat.search(title) and not pat.search(selftext):
            continue

        if return_mention_windows:
            if created >= cutoff_7d:
                m_7d += 1
            elif created >= cutoff_14d:
                m_prior_7d += 1

        score = int(post.get("score") or 0)
        if score < score_floor:
            continue

        candidates.append({
            "subreddit":  sub_name,
            "title":      title,
            "url":        f"https://reddit.com{post.get('permalink', '')}",
            "permalink":  post.get("permalink", ""),
            "score":      score,
            "n_comments": int(post.get("num_comments") or 0),
            "created":    int(created),
            "snippet":    selftext[:240],
        })

    candidates.sort(key=lambda t: t["score"], reverse=True)
    top = candidates[:5]  # cap comment fetches per sub
    if fetch_comments_per_thread > 0 and top:
        comment_results = await asyncio.gather(
            *(_fetch_top_comments(client, t["permalink"], fetch_comments_per_thread)
              for t in top),
            return_exceptions=True,
        )
        for t, cr in zip(top, comment_results):
            t["comments"] = cr if isinstance(cr, list) else []
    for t in candidates:
        t.setdefault("comments", [])
        t.pop("permalink", None)

    return candidates, m_7d, m_prior_7d


async def search_subreddits(
    symbol: str,
    subs: list[tuple[str, int]],
    *,
    days: int = 30,
    fetch_comments_per_thread: int = 0,
    return_mention_windows: bool = False,
    top_n: int = 10,
) -> dict:
    """Search a list of (sub_name, score_floor) tuples for posts mentioning symbol.

    Args:
        symbol: ticker, e.g. 'NVDA'
        subs: list of (sub_name, min_score) tuples
        days: window cutoff (drops posts older than this)
        fetch_comments_per_thread: 0 = skip comments; N = fetch top-N for the
            top-5 threads per sub (caps request volume)
        return_mention_windows: when True, populate mentions_7d /
            mentions_prior_7d counters (counts every ticker-mentioning post,
            not just score-floor passers)
        top_n: max threads to keep in the final list (overall, after merging
            all subs)
    """
    pat = _ticker_pattern(symbol)
    now = time.time()
    cutoffs = (
        now - days * 86400,
        now - 7 * 86400,
        now - 14 * 86400,
    )

    try:
        async with httpx.AsyncClient(
            timeout=REDDIT_TIMEOUT, follow_redirects=True,
            headers=_headers(),
        ) as client:
            results = await asyncio.gather(*(
                _search_one_sub(
                    client, symbol, sub_name, score_floor, pat, cutoffs,
                    fetch_comments_per_thread, return_mention_windows,
                )
                for sub_name, score_floor in subs
            ), return_exceptions=True)
    except Exception as exc:
        return {
            "available": False, "reason": f"http error: {exc}",
            "threads": [], "mentions_7d": 0, "mentions_prior_7d": 0,
        }

    threads: list[dict] = []
    m_7d = m_prior_7d = 0
    for res in results:
        if isinstance(res, Exception):
            log.debug("reddit sub failed: %s", res)
            continue
        sub_threads, m7, mp = res
        threads.extend(sub_threads)
        m_7d += m7
        m_prior_7d += mp

    threads.sort(key=lambda t: t["score"], reverse=True)
    return {
        "available":         True,
        "threads":           threads[:top_n],
        "mentions_7d":       m_7d,
        "mentions_prior_7d": m_prior_7d,
    }
