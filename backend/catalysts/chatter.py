"""Chatter signal — Stocktwits + Reddit.

For each candidate ticker we measure social activity across two free
public sources:

  1. Stocktwits — public message stream API for the symbol, via the shared
     stocktwits_client (Cloudflare TLS-impersonation + pagination). Pages
     are 30 messages each; we walk up to ST_MAX_PAGES pages so n_24h — and
     therefore velocity_per_hour — doesn't saturate at 30 msgs (1.25/hr)
     on frenzy names. Quiet tickers still cost a single request because
     pagination stops at the 24h cutoff.

  2. Reddit — search across high-velocity ticker-discussion subs:
     r/pennystocks, r/wallstreetbets, r/smallstreetbets, r/Biotechplays,
     r/Shortsqueeze, r/StockMarket. We hit the public .json endpoints
     (no PRAW needed, no rate-limit issues for low query counts).

Output for a ticker:
  {
    stocktwits: {n_messages, n_24h, sentiment_pct_bullish, last_message},
    reddit: {n_posts_24h, top_sub, top_thread_url, top_thread_title},
    velocity: messages-per-hour over last 24h,
    sample_blurbs: [up to 3 short text snippets],
  }
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from urllib.parse import quote

import requests

import stocktwits_client

log = logging.getLogger("catalysts.chatter")

# Subs known for catalyst/penny chatter
DEFAULT_SUBS = [
    "pennystocks", "wallstreetbets", "smallstreetbets",
    "Biotechplays", "Shortsqueeze", "StockMarket",
    "Daytrading", "tradetheoptions",
]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Cheetah catalyst scanner; ajay@example.com)",
    "Accept": "application/json",
}


# --- Stocktwits ---------------------------------------------------------

# Pages of 30 walked per ticker. 4 pages → n_24h can reach 120, lifting the
# velocity ceiling from 1.25/hr to 5/hr and letting chatter_score's
# "50 msgs/24h ≈ very loud" calibration actually be reachable (it never was
# with the single-page cap). Pagination stops at the 24h cutoff, so only
# frenzy names spend more than 1 of the ~200 req/hr unauthenticated budget.
ST_MAX_PAGES = 4


def _fetch_stocktwits(ticker: str, max_pages: int = ST_MAX_PAGES) -> dict:
    """Public Stocktwits stream via the shared impersonation client."""
    now = time.time()
    cutoff_24h = now - 24 * 3600

    res = stocktwits_client.fetch_stream(
        ticker, max_pages=max_pages, stop_before_epoch=cutoff_24h, timeout=6)
    if not res.get("ok"):
        # The client already logged the reason; keep it machine-readable so
        # an outage reads as "unavailable", never as "0 chatter".
        return {"n_messages": 0, "n_24h": 0, "sentiment_pct_bullish": None,
                "last_message": None, "blurbs": [],
                "unavailable_reason": res.get("reason")}

    msgs = res.get("messages") or []

    n_24h = 0
    n_bullish = 0
    n_bearish = 0
    blurbs = []
    last_msg_ts = None

    for m in msgs:
        ts = m.get("_epoch")
        if ts and ts >= cutoff_24h:
            n_24h += 1
        sent = (m.get("entities") or {}).get("sentiment") or {}
        basic = sent.get("basic") if isinstance(sent, dict) else None
        if basic == "Bullish":
            n_bullish += 1
        elif basic == "Bearish":
            n_bearish += 1
        body_text = (m.get("body") or "").strip()
        if len(blurbs) < 3 and body_text:
            blurbs.append(body_text[:160])
        if last_msg_ts is None and ts:
            last_msg_ts = ts

    n_total_with_sent = n_bullish + n_bearish
    sent_pct = round(n_bullish / n_total_with_sent * 100) if n_total_with_sent else None

    return {
        "n_messages": len(msgs),
        "n_24h": n_24h,
        "sentiment_pct_bullish": sent_pct,
        "n_bullish": n_bullish,
        "n_bearish": n_bearish,
        "last_message_ts": last_msg_ts,
        "blurbs": blurbs,
    }


# --- Reddit -------------------------------------------------------------

def _fetch_reddit(ticker: str, subs: Optional[list[str]] = None) -> dict:
    """Search Reddit for the ticker across high-velocity catalyst subs.

    We use Reddit's public search.json endpoint with a 7-day window, then
    count posts in the last 24h vs prior to gauge acceleration.
    """
    subs = subs or DEFAULT_SUBS

    # Use OR-search across subs in one query. Reddit accepts subreddit:foo OR subreddit:bar
    sub_q = " OR ".join(f"subreddit:{s}" for s in subs)
    # Hard-search the literal ticker. Use quotation marks so we don't match
    # incidental words. Add $TICKER variant since wsb users often use it.
    q = f'("{ticker}" OR "${ticker}") ({sub_q})'
    url = f"https://www.reddit.com/search.json?q={quote(q)}&sort=new&t=week&limit=50"

    try:
        r = requests.get(url, headers=_HEADERS, timeout=8)
        if r.status_code != 200:
            return {"n_posts_24h": 0, "n_posts_7d": 0, "top": None, "subreddits": []}
        body = r.json() or {}
        children = (body.get("data") or {}).get("children") or []

        now = time.time()
        cutoff_24h = now - 24 * 3600

        posts = []
        sub_counts: dict[str, int] = {}
        for ch in children:
            d = ch.get("data") or {}
            if d.get("kind") and d["kind"] != "t3":
                continue
            posts.append({
                "title": d.get("title") or "",
                "url": "https://reddit.com" + (d.get("permalink") or ""),
                "subreddit": d.get("subreddit"),
                "score": d.get("score") or 0,
                "n_comments": d.get("num_comments") or 0,
                "created": d.get("created_utc") or 0,
            })
            s = d.get("subreddit")
            if s:
                sub_counts[s] = sub_counts.get(s, 0) + 1

        n_24h = sum(1 for p in posts if p["created"] >= cutoff_24h)
        # Top post by score (recent week)
        posts.sort(key=lambda p: p["score"], reverse=True)
        top = posts[0] if posts else None
        # Sub leaders
        sub_leaders = sorted(sub_counts.items(), key=lambda x: -x[1])

        return {
            "n_posts_7d": len(posts),
            "n_posts_24h": n_24h,
            "top": top,
            "subreddits": [s for s, _ in sub_leaders[:5]],
            "subreddit_counts": dict(sub_leaders[:5]),
        }
    except Exception as exc:
        log.debug("reddit fetch failed for %s: %s", ticker, exc)
        return {"n_posts_24h": 0, "n_posts_7d": 0, "top": None, "subreddits": []}


# --- Public combined fetch ----------------------------------------------

def get_chatter(ticker: str) -> dict:
    """Combined chatter snapshot: Stocktwits + Reddit + velocity."""
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_st = ex.submit(_fetch_stocktwits, ticker)
        f_rd = ex.submit(_fetch_reddit, ticker)
        st = f_st.result()
        rd = f_rd.result()

    # Velocity: messages-per-hour from both sources, last 24h
    velocity = ((st.get("n_24h") or 0) + (rd.get("n_posts_24h") or 0)) / 24

    # Sample blurbs (mix of stocktwits + reddit titles, bias toward signal)
    blurbs = []
    blurbs.extend(st.get("blurbs", []) or [])
    if rd.get("top"):
        blurbs.append(rd["top"]["title"])
    blurbs = [b for b in blurbs if b][:5]

    return {
        "ticker": ticker.upper(),
        "stocktwits": st,
        "reddit": rd,
        "velocity_per_hour": round(velocity, 2),
        "sample_blurbs": blurbs,
    }


def get_chatter_batch(tickers: list[str], max_workers: int = 8) -> dict[str, dict]:
    """Fetch chatter for many tickers in parallel. Stocktwits allows about
    200 unauthenticated req/hr/IP and pagination multiplies spend on loud
    names (up to ST_MAX_PAGES each), so cap workers and accept some misses.
    """
    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for r in ex.map(get_chatter, tickers):
            if r:
                out[r["ticker"]] = r
    return out


__all__ = ["get_chatter", "get_chatter_batch"]
