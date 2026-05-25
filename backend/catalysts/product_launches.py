"""Product launch scanner — surfaces new hardware/software/feature
announcements per ticker as a catalyst signal.

Why: Dell rallying because of new server hardware. NVDA rallying because
of a new GPU. AMD rallying because of a new CPU. Stock-price moves often
trace back to a specific product announcement — surfacing those keeps
the user from saying "why is this up?" and reaching for an analyst
report.

Pipeline (run nightly + on-demand):

  1. Fetch last 30d of news from Massive for each tracked symbol.
  2. Pre-filter by keyword (`launches`, `unveils`, `announces`, etc.)
     to cut LLM cost — most ticker news isn't a launch.
  3. Survivors go through Gemma with a structured-output prompt:
     "Is this a product LAUNCH announcement? Extract product name,
     category, status, expected impact." Gemma returns JSON.
  4. Cache verified launches in Mongo (`product_launches` collection)
     keyed by (symbol, url).
  5. Surface via /catalysts/launches/{symbol} — used by the SEPA card
     chip and the morning brief.

Cache lifetime: 7 days. Older launches still served from cache (so a
hot product stays visible) but considered "stale" — re-classified on
next nightly run if it appears in a fresh news fetch.
"""
from __future__ import annotations

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

log = logging.getLogger("catalysts.product_launches")

# Cheap pre-filter — words that strongly suggest a real launch announcement.
# News matching ANY of these goes to the LLM; rest is skipped to save tokens.
_LAUNCH_KEYWORDS = (
    "launches", "launching", "launched",
    "unveils", "unveiled",
    "announces", "announced", "announcement",
    "introduces", "introducing",
    "reveals", "revealed", "reveal",
    "debuts", "debut",
    "ships", "shipping", "begins shipping",
    "release", "released",
    "new chip", "new gpu", "new cpu",
    "new server", "new processor",
    "new model", "new product",
    "preorder", "pre-order",
    "available now", "now available",
)


# Categories the LLM is allowed to assign. Keeps output tidy.
_VALID_CATEGORIES = {
    "cpu", "gpu", "ai_chip", "server", "storage", "networking",
    "smartphone", "laptop", "tablet", "wearable",
    "software", "saas", "ai_model", "api", "platform",
    "vehicle", "battery", "robotics", "medical_device",
    "drug", "therapy",
    "other",
}


# Status values — the LLM must pick from this list.
_VALID_STATUS = {
    "announced",   # press release, no ship date yet
    "preorder",    # ordering open, ships future
    "shipping",    # available now
    "rumored",     # unconfirmed leak / supply-chain leak
}


# ---------------------------------------------------------------------------
# Mongo cache
# ---------------------------------------------------------------------------
_CACHE_TTL_DAYS = 7


def _cache_coll():
    try:
        from pymongo import MongoClient, ASCENDING, DESCENDING
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        c = client[db]["product_launches"]
        c.create_index([("symbol", ASCENDING), ("url", ASCENDING)], unique=True)
        c.create_index([("symbol", ASCENDING), ("published_at", DESCENDING)])
        c.create_index([("classified_at", DESCENDING)])
        return c
    except Exception as exc:
        log.warning("product_launches: mongo unavailable: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Massive news fetch (same source as catalysts/evidence.py)
# ---------------------------------------------------------------------------
def _fetch_news(symbol: str, days: int = 30) -> list[dict]:
    key = os.getenv("MASSIVE_API_KEY")
    if not key:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    try:
        r = requests.get(
            "https://api.massive.com/v2/reference/news",
            params={
                "ticker": symbol,
                "limit": 50,
                "order": "desc",
                "apiKey": key,
            },
            timeout=8,
        )
        if r.status_code != 200:
            return []
        items = (r.json() or {}).get("results", [])
        out = []
        for it in items:
            published = it.get("published_utc")
            try:
                pub_dt = datetime.fromisoformat((published or "").replace("Z", "+00:00"))
                if pub_dt < cutoff:
                    continue
            except Exception:
                continue
            out.append({
                "title":         (it.get("title") or "").strip(),
                "description":   (it.get("description") or "").strip()[:400],
                "url":           it.get("article_url") or it.get("amp_url"),
                "publisher":     (it.get("publisher") or {}).get("name"),
                "published_utc": published,
            })
        return out
    except Exception as exc:
        log.debug("news fetch failed for %s: %s", symbol, exc)
        return []


def _is_likely_launch(item: dict) -> bool:
    """Cheap keyword pre-filter. Returns True if any launch word appears
    in title or description — LLM classifies the survivors."""
    blob = ((item.get("title") or "") + " " + (item.get("description") or "")).lower()
    return any(kw in blob for kw in _LAUNCH_KEYWORDS)


# ---------------------------------------------------------------------------
# LLM classification (Gemma)
# ---------------------------------------------------------------------------
_PROMPT_SYSTEM = (
    "You are a financial news classifier. Your only job is to determine "
    "whether a news headline + description describes a NEW PRODUCT LAUNCH "
    "by the named company, and if so, extract structured details. "
    "Reject: analyst opinions, partnership rumors without a product, "
    "earnings reports, financial commentary, executive moves, M&A. "
    "Accept: actual new products, hardware, software, services, models, "
    "drugs, vehicles being announced/launched/shipped by the company."
)


def _build_prompt(symbol: str, item: dict) -> str:
    return (
        f"Company ticker: {symbol}\n"
        f"News title: {item.get('title') or ''}\n"
        f"News description: {item.get('description') or ''}\n"
        f"Publisher: {item.get('publisher') or 'unknown'}\n\n"
        "Question: Does this article describe a NEW PRODUCT LAUNCH or "
        "ANNOUNCEMENT by this company? If yes, extract details.\n\n"
        "Return strictly this JSON shape, no markdown, no commentary:\n"
        "{\n"
        '  "is_launch": true | false,\n'
        '  "confidence": 0.0 to 1.0,\n'
        '  "product_name": "short product name or null",\n'
        f'  "category": "one of: {", ".join(sorted(_VALID_CATEGORIES))}",\n'
        f'  "status": "one of: {", ".join(sorted(_VALID_STATUS))}",\n'
        '  "expected_impact": "one short sentence on likely stock impact",\n'
        '  "reason": "one short sentence justifying the classification"\n'
        "}\n"
        "If is_launch is false, set the other fields to null/0."
    )


def _classify(symbol: str, item: dict) -> Optional[dict]:
    from llm import chat as llm_chat, is_enabled as llm_is_enabled
    if not llm_is_enabled():
        return None
    res = llm_chat(
        _build_prompt(symbol, item),
        system=_PROMPT_SYSTEM,
        max_tokens=300,
        temperature=0.1,
        json_only=True,
        timeout=30,
    )
    if not res.get("ok"):
        return None
    parsed = res.get("parsed") or {}
    if not isinstance(parsed, dict):
        return None
    is_launch = bool(parsed.get("is_launch"))
    if not is_launch:
        return None
    # Validate enums; coerce category/status to fallback when out of range
    cat = (parsed.get("category") or "other").lower()
    if cat not in _VALID_CATEGORIES:
        cat = "other"
    stat = (parsed.get("status") or "announced").lower()
    if stat not in _VALID_STATUS:
        stat = "announced"
    try:
        conf = float(parsed.get("confidence") or 0)
    except Exception:
        conf = 0.0
    return {
        "is_launch":       True,
        "confidence":      max(0.0, min(1.0, conf)),
        "product_name":    (parsed.get("product_name") or "").strip()[:120] or None,
        "category":        cat,
        "status":          stat,
        "expected_impact": (parsed.get("expected_impact") or "").strip()[:240] or None,
        "reason":          (parsed.get("reason") or "").strip()[:240] or None,
    }


# ---------------------------------------------------------------------------
# Per-symbol scan (the unit of work for the cron)
# ---------------------------------------------------------------------------
def scan_symbol(symbol: str, *, days: int = 30, min_confidence: float = 0.55) -> dict:
    """Fetch news → pre-filter → LLM classify → cache. Returns summary."""
    symbol = symbol.upper().strip()
    coll = _cache_coll()
    news = _fetch_news(symbol, days=days)
    candidates = [n for n in news if _is_likely_launch(n)]
    classified: list[dict] = []
    skipped = 0

    for item in candidates:
        url = item.get("url")
        if not url:
            skipped += 1
            continue
        # Skip if already classified within TTL — avoids re-LLM'ing same
        # article every cron run.
        if coll is not None:
            existing = coll.find_one({"symbol": symbol, "url": url})
            if existing:
                age = (datetime.now(timezone.utc).timestamp() - (existing.get("classified_at") or 0))
                if age < _CACHE_TTL_DAYS * 86400:
                    if existing.get("is_launch"):
                        classified.append({**existing, "_id": str(existing["_id"]), "_from_cache": True})
                    continue

        result = _classify(symbol, item)
        if not result:
            # Not a launch; persist a tombstone so we don't re-classify same URL
            if coll is not None:
                coll.update_one(
                    {"symbol": symbol, "url": url},
                    {"$set": {
                        "symbol": symbol,
                        "url": url,
                        "title": item.get("title"),
                        "published_at": item.get("published_utc"),
                        "is_launch": False,
                        "classified_at": int(datetime.now(timezone.utc).timestamp()),
                    }},
                    upsert=True,
                )
            continue
        if result["confidence"] < min_confidence:
            continue
        doc = {
            "symbol":         symbol,
            "url":            url,
            "title":          item.get("title"),
            "description":    item.get("description"),
            "publisher":      item.get("publisher"),
            "published_at":   item.get("published_utc"),
            "classified_at":  int(datetime.now(timezone.utc).timestamp()),
            **result,
        }
        if coll is not None:
            coll.update_one(
                {"symbol": symbol, "url": url},
                {"$set": doc},
                upsert=True,
            )
        classified.append(doc)

    return {
        "symbol":       symbol,
        "news_fetched": len(news),
        "pre_filtered": len(candidates),
        "launches":     len(classified),
        "skipped":      skipped,
    }


# ---------------------------------------------------------------------------
# Read-side helpers (used by API + frontend)
# ---------------------------------------------------------------------------
def list_launches(symbol: str, *, days: int = 60, limit: int = 10) -> list[dict]:
    """Return cached launches for a symbol, newest first."""
    coll = _cache_coll()
    if coll is None:
        return []
    cutoff_ts = (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()
    cur = coll.find({
        "symbol":    symbol.upper(),
        "is_launch": True,
    }).sort("published_at", -1).limit(limit)
    out = []
    for r in cur:
        try:
            pub = datetime.fromisoformat((r.get("published_at") or "").replace("Z", "+00:00"))
            if pub.timestamp() < cutoff_ts:
                continue
        except Exception:
            pass
        r["_id"] = str(r["_id"])
        out.append(r)
    return out


def summary_for_card(symbol: str) -> Optional[dict]:
    """Compact summary used by SEPA card chip: count + top-1 product."""
    rows = list_launches(symbol, days=45, limit=5)
    if not rows:
        return None
    top = rows[0]
    return {
        "count":         len(rows),
        "latest_product":      top.get("product_name"),
        "latest_category":     top.get("category"),
        "latest_status":       top.get("status"),
        "latest_url":          top.get("url"),
        "latest_published_at": top.get("published_at"),
        "rows":          rows,
    }


# ---------------------------------------------------------------------------
# Batch runner (used by the cron)
# ---------------------------------------------------------------------------
def scan_many(symbols: list[str], *, max_workers: int = 3) -> dict:
    """Run scan_symbol across many symbols in parallel. Conservative
    concurrency to avoid Gemma queue overload."""
    if not symbols:
        return {"scanned": 0, "summary": []}
    symbols = [s.upper().strip() for s in symbols if s]
    summary: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for r in ex.map(scan_symbol, symbols):
            summary.append(r)
    total_launches = sum(s["launches"] for s in summary)
    return {
        "scanned":         len(symbols),
        "total_launches":  total_launches,
        "summary":         summary,
    }


# ---------------------------------------------------------------------------
# CLI entrypoint — used by crontab
# ---------------------------------------------------------------------------
def _default_universe() -> list[str]:
    """Symbols to scan on the cron: watchlist + portfolio holdings + scan top-50."""
    out: set[str] = set()
    try:
        from watchlist import store as watch
        out.update((r.get("ticker") or "").upper() for r in watch.list_entries() if r.get("ticker"))
    except Exception:
        pass
    try:
        from portfolio import store as port
        # Pull all users' holdings — small set, cheap.
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        db = client[os.getenv("MONGO_DB", "cheetah")]
        for h in db.portfolio_holdings.find({}, {"ticker": 1}):
            t = (h.get("ticker") or "").upper()
            if t:
                out.add(t)
    except Exception:
        pass
    try:
        from sepa import scanner as sepa
        rows = (sepa.load_latest() or {}).get("all_results") or []
        rows.sort(key=lambda r: -(r.get("score") or 0))
        for r in rows[:50]:
            t = (r.get("symbol") or "").upper()
            if t and not r.get("is_etf"):
                out.add(t)
    except Exception:
        pass
    return sorted(out)


def main() -> int:
    """`python -m catalysts.product_launches` — cron entrypoint."""
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", help="Scan a single symbol (default: watchlist + portfolio + scan top-50)")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--workers", type=int, default=3)
    args = p.parse_args()

    if args.symbol:
        res = scan_symbol(args.symbol, days=args.days)
        print(json.dumps(res, indent=2, default=str))
        return 0

    syms = _default_universe()
    print(f"scanning {len(syms)} symbols for product launches…")
    res = scan_many(syms, max_workers=args.workers)
    print(f"\n=== Results ===")
    print(f"Symbols scanned:    {res['scanned']}")
    print(f"Total launches:     {res['total_launches']}")
    # Show top movers — symbols with most launches
    top = sorted(res["summary"], key=lambda s: -s["launches"])[:10]
    print(f"\nTop launch activity:")
    for s in top:
        if s["launches"] > 0:
            print(f"  {s['symbol']:6} → {s['launches']} launch(es) from {s['pre_filtered']} candidates")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
