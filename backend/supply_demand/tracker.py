"""Sector supply/demand classifier.

For each curated sector:
  1. Pull ETF + commodity prices (1d/30d/90d change) — yfinance
  2. Pull recent news headlines mentioning sector keywords — Massive
  3. Send to Gemma for classification: state ∈ {constrained, balanced, oversupplied}
     + confidence + 2-sentence narrative

Output: gap_index 0-100 where:
   ≥70 = supply-constrained (bullish for the sector's producers)
   40-69 = balanced
   ≤39 = oversupplied (bearish)

Cached 6 hours in Mongo. Cron refreshes at 6am ET daily.
"""
from __future__ import annotations

import logging
import os
from massive_keys import stocks_key
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

from .sectors import SECTORS, SECTOR_BY_ID

log = logging.getLogger("supply_demand.tracker")

_CACHE_TTL_SEC = 24 * 60 * 60         # 24 hours — fresh-enough threshold
_CACHE_STALE_SEC = 7 * 24 * 60 * 60   # 7 days — serve-stale-and-refresh threshold


def _cache_coll():
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        c = client[db]["supply_demand_cache"]
        c.create_index([("sector_id", ASCENDING)], unique=True)
        return c
    except Exception as exc:
        log.warning("supply_demand cache mongo unavailable: %s", exc)
        return None


def _cache_get(sector_id: str, *, allow_stale: bool = True) -> Optional[dict]:
    """Get cached classification. By default returns even STALE rows
    (older than _CACHE_TTL_SEC) up to _CACHE_STALE_SEC — the request
    path serves stale data instantly and a background refresh is
    triggered separately. Pass allow_stale=False to require fresh."""
    coll = _cache_coll()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"sector_id": sector_id})
        if not doc:
            return None
        ts = doc.get("cached_at")
        if not isinstance(ts, datetime):
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        # Strict mode (allow_stale=False) — only return if within TTL.
        # Stale mode (default) — return up to _CACHE_STALE_SEC old.
        max_age = _CACHE_TTL_SEC if not allow_stale else _CACHE_STALE_SEC
        if age > max_age:
            return None
        payload = doc.get("payload")
        if isinstance(payload, dict):
            payload = dict(payload)
            payload["_cached"] = True
            payload["_cache_age_sec"] = round(age)
            payload["_is_stale"] = age > _CACHE_TTL_SEC
            return payload
    except Exception as exc:
        log.warning("supply_demand cache get failed: %s", exc)
    return None


def _cache_put(sector_id: str, payload: dict) -> None:
    coll = _cache_coll()
    if coll is None:
        return
    try:
        coll.update_one(
            {"sector_id": sector_id},
            {"$set": {"sector_id": sector_id, "cached_at": datetime.now(timezone.utc),
                      "payload": payload}},
            upsert=True,
        )
    except Exception as exc:
        log.warning("supply_demand cache put failed: %s", exc)


def _fetch_etf_metrics(ticker: str) -> Optional[dict]:
    """1d/30d/90d return + last close from yfinance."""
    if not ticker:
        return None
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        hist = t.history(period="6mo", interval="1d")
        if hist is None or hist.empty:
            return None
        closes = hist["Close"]
        last = float(closes.iloc[-1])
        prev = float(closes.iloc[-2]) if len(closes) >= 2 else last
        d30 = float(closes.iloc[-22]) if len(closes) >= 22 else last
        d90 = float(closes.iloc[-66]) if len(closes) >= 66 else last
        return {
            "ticker": ticker,
            "last": round(last, 2),
            "change_1d_pct": round((last / prev - 1) * 100, 2) if prev else None,
            "change_30d_pct": round((last / d30 - 1) * 100, 2) if d30 else None,
            "change_90d_pct": round((last / d90 - 1) * 100, 2) if d90 else None,
        }
    except Exception as exc:
        log.warning("etf metrics failed for %s: %s", ticker, exc)
        return None


def _fetch_sector_news(keywords: list[str], limit: int = 8) -> list[dict]:
    """Fetch recent news matching any sector keyword via Massive news API."""
    import requests
    key = stocks_key()
    if not key:
        return []
    # Use the first 1-2 keywords as the search query (Massive doesn't AND multiple)
    if not keywords:
        return []
    headlines: list[dict] = []
    seen = set()
    # Try first 3 keywords; merge results
    for kw in keywords[:3]:
        try:
            r = requests.get(
                "https://api.massive.com/v2/reference/news",
                params={"q": kw, "limit": 6, "order": "desc", "apiKey": key},
                timeout=10,
            )
            if r.status_code != 200:
                continue
            for item in (r.json() or {}).get("results") or []:
                t = item.get("title")
                if not t or t in seen:
                    continue
                seen.add(t)
                headlines.append({
                    "title": t[:200],
                    "url": item.get("article_url"),
                    "publisher": (item.get("publisher") or {}).get("name"),
                    "published_utc": item.get("published_utc"),
                })
                if len(headlines) >= limit:
                    return headlines
        except Exception as exc:
            log.warning("sector news fetch failed for %s: %s", kw, exc)
    return headlines


def _classify_with_gemma(sector: dict, etf: Optional[dict], commodity: Optional[dict],
                          headlines: list[dict]) -> Optional[dict]:
    """Use local LLM to classify sector state. Returns None if LLM unavailable."""
    try:
        import llm
    except ImportError:
        return None
    if not llm.is_enabled():
        return None

    headline_summary = "\n".join(f"- {h['title']}" for h in headlines[:8]) if headlines else "(no recent news)"
    etf_summary = (
        f"ETF {etf['ticker']}: 1d {etf.get('change_1d_pct')}% / 30d {etf.get('change_30d_pct')}% / 90d {etf.get('change_90d_pct')}%"
        if etf else "(no ETF tracked)"
    )
    commodity_summary = (
        f"Commodity {commodity['ticker']}: 1d {commodity.get('change_1d_pct')}% / 30d {commodity.get('change_30d_pct')}% / 90d {commodity.get('change_90d_pct')}%"
        if commodity else ""
    )

    prompt = f"""Sector: {sector['label']}
Existing thesis: {sector.get('thesis', '')}

Market signals:
{etf_summary}
{commodity_summary}

Recent headlines:
{headline_summary}

Classify the current global supply/demand state for this sector.

Output ONLY a JSON object (no markdown fence, no preamble) with these fields:
  "state": one of "constrained" / "balanced" / "oversupplied"
  "gap_index": integer 0-100 (0=heavy oversupply, 50=balanced, 100=severe shortage)
  "confidence": integer 0-100
  "narrative": 2 sentences explaining the current state, citing the strongest signal
  "trend_direction": one of "tightening" / "stable" / "loosening"
"""

    res = llm.chat(prompt, max_tokens=400, temperature=0.2, json_only=True, timeout=60)
    if not res.get("ok"):
        return None
    parsed = res.get("parsed")
    if not isinstance(parsed, dict):
        return None
    if parsed.get("state") not in ("constrained", "balanced", "oversupplied"):
        return None
    try:
        gi = int(parsed.get("gap_index", 50))
        gi = max(0, min(100, gi))
    except (ValueError, TypeError):
        gi = 50
    return {
        "state": parsed["state"],
        "gap_index": gi,
        "confidence": int(parsed.get("confidence", 50)),
        "narrative": parsed.get("narrative", ""),
        "trend_direction": parsed.get("trend_direction", "stable"),
        "_method": "llm",
        "_model": res.get("model"),
        "_latency_sec": res.get("latency_sec"),
    }


def _heuristic_classify(sector: dict, etf: Optional[dict]) -> dict:
    """Cheap fallback when LLM isn't running. Uses ETF momentum as the signal."""
    if etf and etf.get("change_30d_pct") is not None:
        ch30 = etf["change_30d_pct"]
        if ch30 > 8:
            return {"state": "constrained", "gap_index": 70, "confidence": 35,
                    "narrative": f"ETF {etf['ticker']} up {ch30}% over 30 days suggests demand outpacing supply.",
                    "trend_direction": "tightening", "_method": "heuristic"}
        if ch30 < -8:
            return {"state": "oversupplied", "gap_index": 25, "confidence": 35,
                    "narrative": f"ETF {etf['ticker']} down {abs(ch30)}% over 30 days suggests demand softening or supply overhang.",
                    "trend_direction": "loosening", "_method": "heuristic"}
    return {"state": "balanced", "gap_index": 50, "confidence": 25,
            "narrative": "No strong signals; defaulting to balanced state. Enable LLM for better classification.",
            "trend_direction": "stable", "_method": "heuristic"}


def classify_sector(sector_id: str, force: bool = False) -> Optional[dict]:
    """Compute (or load cached) classification for a single sector.

    Cache strategy:
      - Fresh (<24h): serve directly, no LLM call
      - Stale (24h-7d): serve cached (with _is_stale flag), let the
        DAILY cron's resolve_all() refresh in the background
      - Missing/expired: full recompute via LLM (the only path that
        actually hits Gemma on the request hot-path)
    """
    sector = SECTOR_BY_ID.get(sector_id)
    if not sector:
        return None
    if not force:
        # Default: accept stale data — the daily cron keeps the cache
        # warm so this almost always hits.
        cached = _cache_get(sector_id, allow_stale=True)
        if cached is not None:
            return cached

    etf = _fetch_etf_metrics(sector.get("etf", "")) if sector.get("etf") else None
    commodity = _fetch_etf_metrics(sector.get("commodity", "")) if sector.get("commodity") else None
    headlines = _fetch_sector_news(sector.get("keywords") or [])

    classification = _classify_with_gemma(sector, etf, commodity, headlines)
    if classification is None:
        classification = _heuristic_classify(sector, etf)

    payload = {
        "sector_id": sector_id,
        "label": sector["label"],
        "narrative_static": sector.get("narrative"),
        "thesis_static": sector.get("thesis"),
        "etf": etf,
        "commodity": commodity,
        "headlines": headlines,
        "classification": classification,
        "sp_tickers": sector.get("sp_tickers") or [],
        "gap_economics": sector.get("gap_economics"),
        "as_of": datetime.now(timezone.utc).isoformat(),
    }
    _cache_put(sector_id, payload)
    payload["_cached"] = False
    return payload


def classify_all_sectors(force: bool = False) -> dict:
    """Classify all 15 sectors in parallel."""
    import concurrent.futures
    out: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        future_to_id = {ex.submit(classify_sector, s["id"], force): s["id"] for s in SECTORS}
        for fut in concurrent.futures.as_completed(future_to_id):
            try:
                r = fut.result()
                if r:
                    out.append(r)
            except Exception as exc:
                log.warning("sector classify failed for %s: %s", future_to_id[fut], exc)
    # Sort: most constrained first
    out.sort(key=lambda x: -(x.get("classification", {}).get("gap_index") or 50))
    cached_count = sum(1 for s in out if s.get("_cached"))
    return {
        "sectors": out,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "n_sectors": len(out),
        "n_cached": cached_count,
        "cache_ttl_hours": _CACHE_TTL_SEC // 3600,
    }


if __name__ == "__main__":
    import argparse
    import json as _json
    ap = argparse.ArgumentParser()
    ap.add_argument("--sector", default=None, help="single sector id (default: all)")
    ap.add_argument("--force", action="store_true", help="bypass cache")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
    if args.sector:
        print(_json.dumps(classify_sector(args.sector, force=args.force), indent=2, default=str))
    else:
        result = classify_all_sectors(force=args.force)
        for s in result["sectors"]:
            c = s.get("classification", {})
            print(f"  {s['label']:<28}  gap={c.get('gap_index'):>3}/100  state={c.get('state'):<14}  conf={c.get('confidence')}%  {c.get('narrative', '')[:80]}")
