"""Overnight gap tracker — what moved while you slept and *why*.

For each watchlist symbol:
  1. Yesterday's RTH close (4:00pm ET) → today's premarket-so-far reference price
  2. Compute gap %
  3. Pull premarket bars (4:00am–9:30am ET) for chart preview
  4. Pull recent news headlines from Massive (since yesterday's close)
  5. Pull earnings calendar — flag if reporting today/tonight
  6. Heuristic catalyst label from headline keywords (no LLM dependency)

The "catalyst attachment" is the secret sauce — most overnight gaps DO have
a single dominant cause, but it requires correlating the price move with
the right headline. We do this by:
  - filtering news to within the last 18h
  - keyword-scoring each headline against a curated catalyst dictionary
  - returning the highest-scored headline + its category
"""
from __future__ import annotations

import logging
import os
from massive_keys import stocks_key
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
import requests

log = logging.getLogger("overnight.movers")

BASE_URL = "https://api.massive.com"


# Catalyst categories — each maps to keywords that strongly imply that category.
# Order matters: we check most-specific first.
CATALYST_PATTERNS: list[tuple[str, str, list[str]]] = [
    ("Earnings", "earnings",   ["earnings", "quarter", "q1", "q2", "q3", "q4", "eps", "revenue beat",
                                 "revenue miss", "beats estimates", "misses estimates", "raises guidance",
                                 "lowers guidance", "fy2", "results", "reports"]),
    ("Analyst", "analyst",      ["upgrade", "downgrade", "raises price target", "lowers price target",
                                 "buy rating", "sell rating", "outperform", "underperform", "neutral",
                                 "morgan stanley", "goldman", "jpmorgan", "citi raises", "wells fargo",
                                 "bank of america", "wedbush", "needham", "barclays"]),
    ("M&A",      "ma",          ["acquir", "merger", "buyout", "to be acquired", "takeover", "tender offer",
                                 "stake", "private equity", "leveraged buyout", "lbo"]),
    ("Filing",   "filing",      ["8-k", "13f", "13d", "13g", "form 8-k", "files for", "files chapter"]),
    ("FDA",      "fda",         ["fda", "approval", "pdufa", "phase 1", "phase 2", "phase 3", "trial",
                                 "clinical", "drug"]),
    ("Litigation", "litigation",["lawsuit", "settles", "settlement", "court rules", "doj", "ftc",
                                 "antitrust", "ruling"]),
    ("Insider",  "insider",     ["insider buy", "insider sell", "ceo buys", "ceo sells", "form 4"]),
    ("Macro",    "macro",       ["fomc", "fed", "powell", "jobs report", "nonfarm", "payrolls", "cpi",
                                 "inflation", "tariff", "rate cut", "rate hike", "stimulus"]),
    ("Sector",   "sector",      ["sector", "peer", "rivals", "industry"]),
    ("Geopolitical", "geo",     ["war", "sanctions", "china", "russia", "iran", "north korea", "ukraine",
                                  "middle east", "israel", "gaza", "lebanon", "yemen", "geopolit",
                                  "tariff", "trade war", "embargo"]),
    ("Crypto",   "crypto",      ["bitcoin", "btc", "ethereum", "crypto", "stablecoin"]),
    ("Product",  "product",     ["launches", "unveils", "introduces", "new product", "next-gen"]),
    ("Partnership", "partnership", ["partnership", "deal", "agreement", "contract", "wins"]),
    ("Stock action", "stock_action", ["stock split", "buyback", "dividend", "spin-off", "ipo", "secondary"]),
]


def _hit(path: str, params: Optional[dict] = None) -> Optional[dict]:
    key = stocks_key()
    if not key:
        return None
    p = dict(params or {})
    p["apiKey"] = key
    try:
        r = requests.get(f"{BASE_URL}{path}", params=p, timeout=12)
        if r.status_code != 200:
            log.debug("massive %s -> HTTP %s", path, r.status_code)
            return None
        return r.json()
    except Exception as exc:
        log.debug("massive %s failed: %s", path, exc)
        return None


def _last_rth_close(df: pd.DataFrame) -> Optional[tuple[pd.Timestamp, float]]:
    """Return (ts_utc, price) of the most recent RTH close (last bar with session=='rth').

    df is expected from the daytrading.data loader (already session-tagged).
    """
    if df is None or df.empty or "session" not in df.columns:
        return None
    rth = df[df["session"] == "rth"]
    if rth.empty:
        return None
    et_idx = rth.index.tz_localize("UTC").tz_convert("America/New_York")
    et_dates = pd.Series(et_idx.date, index=rth.index)
    today = et_dates.max()
    # We want YESTERDAY's close — last bar of the most recent prior trading date
    prior_dates = sorted([d for d in et_dates.unique() if d < today])
    if not prior_dates:
        # If no prior date in window, use today's last bar (fallback)
        last = rth.index[-1]
        return last, float(rth.loc[last, "close"])
    prior_close_day = prior_dates[-1]
    bars = rth[et_dates == prior_close_day]
    if bars.empty:
        return None
    last = bars.index[-1]
    return last, float(bars.loc[last, "close"])


def _premarket_today_reference(df: pd.DataFrame) -> Optional[tuple[pd.Timestamp, float, int, float, float]]:
    """For the most-recent ET trading session, return:
    (last_pre_ts, last_pre_price, n_bars, premarket_high, premarket_low)
    or None if no premarket bars exist for today."""
    if df is None or df.empty:
        return None
    pre = df[df["session"] == "premarket"]
    if pre.empty:
        return None
    et_idx = pre.index.tz_localize("UTC").tz_convert("America/New_York")
    et_dates = pd.Series(et_idx.date, index=pre.index)
    today = et_dates.max()
    today_pre = pre[et_dates == today]
    if today_pre.empty:
        return None
    last_ts = today_pre.index[-1]
    last_price = float(today_pre.loc[last_ts, "close"])
    pre_high = float(today_pre["high"].max())
    pre_low = float(today_pre["low"].min())
    return last_ts, last_price, len(today_pre), pre_high, pre_low


def _classify_catalyst(headline: str) -> Optional[tuple[str, str, int]]:
    """Score a headline against the catalyst dictionary. Returns (label, key, score)."""
    if not headline:
        return None
    lower = headline.lower()
    best = None
    for label, key, kws in CATALYST_PATTERNS:
        score = sum(1 for kw in kws if kw in lower)
        if score == 0:
            continue
        # Length-bonus: longer keyword matches > shorter ones
        kw_bonus = max(len(kw) for kw in kws if kw in lower) // 4
        total = score * 10 + kw_bonus
        if best is None or total > best[2]:
            best = (label, key, total)
    return best


def _fetch_news(symbol: str, since_iso: str, limit: int = 10) -> list[dict]:
    """Fetch news for a single symbol since `since_iso` (UTC ISO date string)."""
    body = _hit("/v2/reference/news",
                params={"ticker": symbol, "limit": limit, "order": "desc",
                        "published_utc.gte": since_iso})
    if not body:
        return []
    return body.get("results") or []


def _is_earnings_calendar_today(symbol: str, prefetched_news: Optional[list[dict]] = None) -> Optional[dict]:
    """Best-effort earnings flag — scans recent news for earnings-related items.

    If `prefetched_news` is supplied, reuse those items instead of making a
    new Massive API call (saves ~200ms per symbol on the overnight scan).
    """
    if prefetched_news is None:
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        prefetched_news = _fetch_news(symbol, since, limit=10)
    for item in prefetched_news or []:
        title = (item.get("title") or "").lower()
        if any(kw in title for kw in ("earnings", "reports q", "results")):
            return {"flagged": True, "title": item.get("title"), "url": item.get("article_url"),
                    "published": item.get("published_utc")}
    return None


_VALID_CATEGORIES = {
    "Earnings", "Analyst", "M&A", "FDA", "Filing", "Litigation", "Insider",
    "Macro", "Sector", "Geopolitical", "Crypto", "Product", "Partnership",
    "Stock action", "Other",
}


def _classify_with_llm(symbol: str, headlines: list[dict]) -> Optional[dict]:
    """Use the local LLM to classify the strongest catalyst from a list of headlines.

    Returns {category, headline, confidence, rationale, ...} or None if LLM
    is unavailable or returned junk. Caller falls back to keyword matching.
    """
    try:
        import llm
    except ImportError:
        return None
    if not llm.is_enabled() or not headlines:
        return None

    # Compose a compact list for the LLM
    items = []
    for i, h in enumerate(headlines[:8]):
        title = (h.get("title") or "").replace("\n", " ").strip()
        pub = (h.get("publisher") or {}).get("name") or ""
        when = (h.get("published_utc") or "")[:16]
        items.append(f"{i+1}. [{when}] {title}  ({pub})")

    categories = sorted(_VALID_CATEGORIES)
    prompt = (
        f"You are analyzing why {symbol} stock moved overnight. Below are recent news "
        f"headlines about {symbol} since yesterday's market close.\n\n"
        f"Available categories: {', '.join(categories)}.\n\n"
        f"Headlines:\n" + "\n".join(items) + "\n\n"
        f"Pick the SINGLE headline that most likely caused the overnight stock move. "
        f"Generic market commentary not specific to {symbol} should be category 'Other'. "
        f"Output ONLY a JSON object (no preamble, no markdown fences) with keys:\n"
        f'  "category": one of the categories above (exact spelling)\n'
        f'  "headline_index": integer 1-{len(items)} matching the picked headline\n'
        f'  "confidence": integer 0-100 (your certainty this drives the price)\n'
        f'  "rationale": 1-2 sentences explaining why\n'
    )

    res = llm.chat(prompt, max_tokens=300, temperature=0.1, json_only=True, timeout=45)
    if not res.get("ok") or not res.get("parsed"):
        return None
    parsed = res["parsed"]
    cat = parsed.get("category")
    idx = parsed.get("headline_index")
    if cat not in _VALID_CATEGORIES:
        return None
    if not isinstance(idx, int) or idx < 1 or idx > len(headlines):
        return None
    chosen = headlines[idx - 1]
    return {
        "category": cat,
        "category_key": cat.lower().replace(" ", "_").replace("&", "and"),
        "headline": (chosen.get("title") or "")[:200],
        "publisher": (chosen.get("publisher") or {}).get("name"),
        "url": chosen.get("article_url"),
        "published_utc": chosen.get("published_utc"),
        "confidence": parsed.get("confidence"),
        "rationale": parsed.get("rationale"),
        "method": "llm",
        "model": res.get("model"),
        "latency_sec": res.get("latency_sec"),
    }


def _attach_catalyst(symbol: str, last_close_ts: pd.Timestamp,
                      prefetched_news: Optional[list[dict]] = None) -> tuple[dict, list[dict]]:
    """Pick the strongest news catalyst since yesterday's close.

    Returns (catalyst_dict, news_items) so callers can reuse the news list
    for additional checks (earnings flag) without re-hitting the API.
    """
    # Ensure UTC-aware ISO timestamp — Massive's published_utc.gte expects this.
    if last_close_ts.tzinfo is None:
        ts = last_close_ts.tz_localize("UTC")
    else:
        ts = last_close_ts.tz_convert("UTC")
    since = ts.isoformat()
    items = prefetched_news if prefetched_news is not None else _fetch_news(symbol, since, limit=10)

    # Try LLM first — it's much smarter than keyword matching, especially
    # for vague headlines or sector-flow attribution. Falls back to keywords
    # if LLM isn't running or returns junk.
    llm_result = _classify_with_llm(symbol, items)
    if llm_result is not None:
        return llm_result, items

    candidates = []
    for it in items:
        title = it.get("title") or ""
        cls = _classify_catalyst(title)
        if not cls:
            continue
        label, key, score = cls
        candidates.append({
            "headline": title[:200],
            "category": label,
            "category_key": key,
            "score": score,
            "publisher": (it.get("publisher") or {}).get("name"),
            "url": it.get("article_url"),
            "published_utc": it.get("published_utc"),
        })
    candidates.sort(key=lambda x: -x["score"])
    if not candidates:
        # No matched catalyst — but we may still have news; return top headline as raw
        if items:
            top = items[0]
            return {
                "category": "Other",
                "category_key": "other",
                "headline": (top.get("title") or "")[:200],
                "publisher": (top.get("publisher") or {}).get("name"),
                "url": top.get("article_url"),
                "published_utc": top.get("published_utc"),
                "score": 0,
            }, items
        return {"category": None, "headline": None}, items
    top = dict(candidates[0])  # copy to avoid circular reference
    top["all_candidates"] = [{k: v for k, v in c.items() if k != "all_candidates"} for c in candidates[1:5]]
    top["method"] = "keyword"
    return top, items


def overnight_for_symbol(symbol: str, df: Optional[pd.DataFrame] = None) -> Optional[dict]:
    """Compute the full overnight picture for one symbol.

    `df` should be the intraday DataFrame from daytrading.data with
    premarket+RTH bars covering today + yesterday.
    """
    if df is None:
        # Lazy import to avoid circular
        from daytrading.data import load_intraday_range
        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=4)
        df = load_intraday_range(symbol, start, today, include_premarket=True, include_afterhours=True)
    if df is None or df.empty:
        return None

    yclose = _last_rth_close(df)
    if yclose is None:
        return None
    yclose_ts, yclose_px = yclose

    pre = _premarket_today_reference(df)
    if pre is None:
        # No premarket yet today — overnight tracker requires premarket data
        return {"symbol": symbol, "yesterday_close": yclose_px,
                "yesterday_close_ts": yclose_ts.isoformat(),
                "premarket_last": None, "gap_pct": None,
                "catalyst": None, "premarket_bars": 0,
                "premarket_sparkline": []}

    pre_ts, pre_px, n_bars, pre_high, pre_low = pre
    gap_pct = (pre_px / yclose_px - 1) * 100 if yclose_px else None

    # Premarket sparkline — sample down to ~30 points
    today_pre_mask = (df["session"] == "premarket")
    today_pre = df[today_pre_mask]
    et_idx = today_pre.index.tz_localize("UTC").tz_convert("America/New_York")
    today_date = pd.Series(et_idx.date, index=today_pre.index).max()
    today_pre = today_pre[pd.Series(et_idx.date, index=today_pre.index) == today_date]
    sparkline = []
    if len(today_pre) > 0:
        step = max(1, len(today_pre) // 30)
        for ts, row in today_pre.iloc[::step].iterrows():
            sparkline.append({"ts": ts.isoformat(),
                              "px": round(float(row["close"]), 4)})

    catalyst, news_items = _attach_catalyst(symbol, yclose_ts)
    earnings = _is_earnings_calendar_today(symbol, prefetched_news=news_items)

    # Slim list of clickable news items for the UI — top 5, only essential fields
    news_links = []
    for it in (news_items or [])[:5]:
        news_links.append({
            "title": (it.get("title") or "")[:200],
            "url": it.get("article_url"),
            "publisher": (it.get("publisher") or {}).get("name"),
            "published_utc": it.get("published_utc"),
        })

    return {
        "symbol": symbol,
        "yesterday_close": round(yclose_px, 4),
        "yesterday_close_ts": yclose_ts.isoformat(),
        "premarket_last": round(pre_px, 4),
        "premarket_last_ts": pre_ts.isoformat(),
        "premarket_high": round(pre_high, 4),
        "premarket_low": round(pre_low, 4),
        "premarket_bars": n_bars,
        "gap_pct": round(gap_pct, 3) if gap_pct is not None else None,
        "catalyst": catalyst if catalyst.get("category") else None,
        "earnings_flag": earnings,
        "premarket_sparkline": sparkline,
        "news_links": news_links,
    }


_CACHE_TTL_SEC = 30 * 60  # legacy default — overridden by _cache_ttl_sec() below


def _et_now() -> datetime:
    """Current time in America/New_York. Falls back to UTC if zoneinfo isn't
    available (shouldn't happen in our Python 3.11 image, but defensive)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.now(timezone.utc)


def _cache_ttl_sec() -> int:
    """Market-state-aware cache TTL. Premarket movers can swing 5%+ in
    minutes during active hours, so a 30-min stale window is way too long
    when it matters most.

    Hours (America/New_York):
      • 04:00 – 09:30  Mon-Fri  → 120s   (active premarket — gappers move fast)
      • 09:30 – 16:00  Mon-Fri  → 600s   (regular session — overnight tape less critical)
      • everything else                  → 1800s  (closed / weekends — futures barely move)

    Same data, just doesn't go stale during the windows where freshness matters.
    """
    now = _et_now()
    weekday = now.weekday()  # 0=Mon .. 6=Sun
    if weekday >= 5:
        return 1800
    minutes_in_day = now.hour * 60 + now.minute
    premkt_start = 4 * 60          # 04:00
    rth_open    = 9 * 60 + 30      # 09:30
    rth_close   = 16 * 60          # 16:00
    if premkt_start <= minutes_in_day < rth_open:
        return 120
    if rth_open <= minutes_in_day < rth_close:
        return 600
    return 1800


def _cache_coll():
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.environ.get("MONGO_URL", "mongodb://mongo:27017")
        db = os.environ.get("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        c = client[db]["overnight_cache"]
        c.create_index([("symbol", ASCENDING)], unique=True)
        return c
    except Exception as exc:
        log.warning("overnight cache mongo unavailable: %s", exc)
        return None


def _cache_get(symbol: str) -> Optional[dict]:
    coll = _cache_coll()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"symbol": symbol.upper()})
        if not doc:
            return None
        ts = doc.get("cached_at")
        if not isinstance(ts, datetime):
            return None
        # Mongo strips tzinfo on read — treat as UTC so the math works.
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_sec = (datetime.now(timezone.utc) - ts).total_seconds()
        # Market-aware TTL — short during active premarket, long during dead hours
        if age_sec > _cache_ttl_sec():
            return None
        payload = doc.get("payload")
        if isinstance(payload, dict):
            payload = dict(payload)
            payload["_cached"] = True
            payload["_cache_age_sec"] = round(age_sec)
            return payload
    except Exception as exc:
        log.warning("overnight cache get failed for %s: %s", symbol, exc)
    return None


def _cache_put(symbol: str, payload: dict) -> None:
    coll = _cache_coll()
    if coll is None:
        return
    try:
        coll.update_one(
            {"symbol": symbol.upper()},
            {"$set": {"symbol": symbol.upper(), "cached_at": datetime.now(timezone.utc),
                      "payload": payload}},
            upsert=True,
        )
    except Exception as exc:
        log.warning("overnight cache put failed for %s: %s", symbol, exc)


def overnight_for_symbol_cached(symbol: str, force: bool = False) -> Optional[dict]:
    """Cache-aware version of overnight_for_symbol. 30min TTL by default.

    `force=True` bypasses the cache and re-scrapes."""
    sym = symbol.upper()
    if not force:
        cached = _cache_get(sym)
        if cached is not None:
            return cached
    fresh = overnight_for_symbol(sym)
    if fresh:
        _cache_put(sym, fresh)
        fresh["_cached"] = False
    return fresh


def overnight_movers(symbols: list[str], min_gap_pct: float = 0.5,
                      force: bool = False) -> list[dict]:
    """Compute overnight movers in PARALLEL with Mongo-backed per-symbol cache.

    Cache TTL is 30 minutes. Pass force=True from the UI to bypass cache.
    """
    import concurrent.futures
    out = []
    # Parallelize per-symbol scans (each does 1-3 Massive API calls when not cached)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        future_to_sym = {ex.submit(overnight_for_symbol_cached, s, force): s for s in symbols}
        for fut in concurrent.futures.as_completed(future_to_sym):
            sym = future_to_sym[fut]
            try:
                r = fut.result()
            except Exception as exc:
                log.warning("overnight failed for %s: %s", sym, exc)
                continue
            if r is None or r.get("gap_pct") is None:
                continue
            if abs(r["gap_pct"]) < min_gap_pct:
                continue
            out.append(r)
    out.sort(key=lambda x: -abs(x.get("gap_pct") or 0))
    return out
