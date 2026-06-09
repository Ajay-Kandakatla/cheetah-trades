"""Fear & Greed index — mirrors CNN Business's published index for the Market
Gauge page.

The user asked for "a fear greed index like CNN biz does" and showed CNN's dial.
Rather than reverse-engineer a real-money sentiment signal (we explicitly DON'T
fake undisclosed third-party formulas — see the Market Gauge page copy), this
reads CNN's OWN published value from their public dataviz feed and reshapes it:

    https://production.dataviz.cnn.io/index/fearandgreed/graphdata/<date>

We surface exactly what CNN shows on the dial — the 0-100 score, the rating
(Extreme Fear … Extreme Greed), the previous-close / 1-week / 1-month / 1-year
readings, the seven component sub-indices (momentum, strength, breadth, put/call,
volatility, safe-haven, junk-bond), and a recent historical trend.

ATTRIBUTION: every payload carries `source` = "CNN Business" + the source URL.
This is CNN's index, surfaced in-app — not our own computation.

The feed bot-blocks bare requests (HTTP 418), so we send a browser User-Agent
plus the cnn.com Referer/Origin it expects. Same cache shape as market_gauge: a
Mongo `fear_greed/latest` doc warmed by a market-hours cron, a short in-process
TTL, and a graceful degrade to the last persisted value if the feed is down.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger("sepa.fear_greed")

FEED_BASE = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
SOURCE_NAME = "CNN Business"
SOURCE_URL = "https://www.cnn.com/markets/fear-and-greed"

# The feed returns 418 without a browser-like header set + cnn.com origin.
_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.cnn.com/",
    "Origin": "https://www.cnn.com",
}

# CNN's seven sub-indices, in the order CNN lists them, with a plain-English
# blurb describing what each one measures (so the card explains itself).
COMPONENTS = [
    ("market_momentum_sp500", "Market Momentum", "S&P 500 vs its 125-day average"),
    ("stock_price_strength", "Stock Price Strength", "Net 52-week highs vs lows (NYSE)"),
    ("stock_price_breadth", "Stock Price Breadth", "McClellan Volume Summation (advancing vs declining volume)"),
    ("put_call_options", "Put / Call Options", "5-day put/call ratio — hedging demand"),
    ("market_volatility_vix", "Market Volatility", "VIX vs its 50-day average"),
    ("safe_haven_demand", "Safe-Haven Demand", "Stocks vs Treasuries, 20-day relative return"),
    ("junk_bond_demand", "Junk Bond Demand", "Junk vs investment-grade yield spread"),
]

_TTL_SEC = 10 * 60              # CNN updates intraday; 10-min in-proc cache
_PERSIST_FRESH_SEC = 26 * 3600  # a cron-warmed doc stands as "current" for ~1 day
_HIST_CAP = 90                 # cap the trend to the last ~90 points


def _band(score: Optional[float]) -> tuple:
    """(key, label) sentiment band for a 0-100 score, using CNN's cut points.
    Used to label the previous-close/week/month/year readings (the feed gives
    only their numbers, not their ratings)."""
    if score is None:
        return ("unknown", "—")
    s = float(score)
    if s < 25:
        return ("extreme_fear", "Extreme Fear")
    if s < 45:
        return ("fear", "Fear")
    if s < 55:
        return ("neutral", "Neutral")
    if s < 75:
        return ("greed", "Greed")
    return ("extreme_greed", "Extreme Greed")


def _rating_key(rating: Optional[str]) -> str:
    """Normalize CNN's rating string ('extreme fear') → key ('extreme_fear')."""
    return (rating or "").strip().lower().replace(" ", "_") or "unknown"


def _rating_label(rating: Optional[str]) -> str:
    return (rating or "").strip().title() or "—"


def _prev(score: Optional[float]) -> Optional[dict]:
    if score is None:
        return None
    key, label = _band(score)
    return {"value": round(float(score), 1), "rating": key, "rating_label": label}


# ── pure parse (unit-testable; no network) ───────────────────────────────────
def _parse(raw: dict) -> dict:
    """PURE: CNN graphdata JSON → our payload shape."""
    fng = (raw or {}).get("fear_and_greed") or {}
    score = fng.get("score")
    rating = fng.get("rating")

    components = []
    for key, label, blurb in COMPONENTS:
        c = (raw or {}).get(key) or {}
        cs = c.get("score")
        if cs is None:
            continue
        components.append({
            "key": key,
            "label": label,
            "blurb": blurb,
            "score": round(float(cs), 1),
            "rating": _rating_key(c.get("rating")),
            "rating_label": _rating_label(c.get("rating")),
        })

    # Historical trend (oldest→newest) for a sparkline.
    hist_raw = (raw or {}).get("fear_and_greed_historical") or {}
    hist_pts = hist_raw.get("data") if isinstance(hist_raw, dict) else hist_raw
    history = []
    for p in (hist_pts or []):
        try:
            history.append({"t": int(p["x"]), "v": round(float(p["y"]), 1),
                            "rating": _rating_key(p.get("rating"))})
        except (KeyError, TypeError, ValueError):
            continue
    history = history[-_HIST_CAP:]

    return {
        "score": round(float(score), 1) if score is not None else None,
        "score_int": int(round(float(score))) if score is not None else None,
        "rating": _rating_key(rating),
        "rating_label": _rating_label(rating),
        "as_of_iso": fng.get("timestamp"),
        "previous": {
            "close": _prev(fng.get("previous_close")),
            "week": _prev(fng.get("previous_1_week")),
            "month": _prev(fng.get("previous_1_month")),
            "year": _prev(fng.get("previous_1_year")),
        },
        "components": components,
        "history": history,
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "disclaimer": (
            "CNN Business's published Fear & Greed Index, surfaced in-app — not "
            "our own computation. Sentiment context, not a forecast or advice."),
    }


def _fetch_raw() -> Optional[dict]:
    """Hit CNN's feed (with a recent-history window) → raw JSON, or None."""
    try:
        import requests
    except ImportError:
        log.warning("fear_greed: requests not installed")
        return None
    # Ask from ~120 days back so the historical array is a few months deep.
    start = (datetime.now(timezone.utc).date() - timedelta(days=120)).isoformat()
    try:
        r = requests.get(f"{FEED_BASE}/{start}", headers=_HEADERS, timeout=10)
        if r.status_code != 200:
            log.warning("fear_greed: CNN feed HTTP %s", r.status_code)
            return None
        return r.json()
    except Exception as exc:
        log.warning("fear_greed: fetch failed: %s", exc)
        return None


def compute() -> dict:
    raw = _fetch_raw()
    if not raw:
        return {"error": "feed_unavailable", "source": SOURCE_NAME,
                "source_url": SOURCE_URL}
    payload = _parse(raw)
    payload["generated_at"] = int(time.time())
    payload["generated_at_iso"] = datetime.now(timezone.utc).isoformat()
    return payload


# ── persist / serve (mirrors sepa/market_gauge) ──────────────────────────────
def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        return client[os.getenv("MONGO_DB", "cheetah")].fear_greed
    except Exception:
        return None


def run_and_persist() -> dict:
    """Compute + upsert `latest`. Called by the market-hours
    `sepa.cli fear-greed-refresh` cron. On a feed miss, leaves the prior doc."""
    payload = compute()
    if payload.get("error"):
        log.warning("fear_greed: feed unavailable, keeping last persisted")
        return load_persisted() or payload
    coll = _coll()
    if coll is not None:
        try:
            doc = dict(payload)
            doc["_id"] = "latest"
            doc["computed_at"] = int(time.time())
            coll.update_one({"_id": "latest"}, {"$set": doc}, upsert=True)
            log.info("fear_greed persisted: score=%s rating=%s",
                     payload.get("score"), payload.get("rating"))
        except Exception as exc:
            log.warning("fear_greed persist failed: %s", exc)
    _CACHE.update(at=time.time(), data=payload)
    return payload


def load_persisted() -> Optional[dict]:
    coll = _coll()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"_id": "latest"})
        if not doc:
            return None
        doc.pop("_id", None)
        doc["age_sec"] = int(time.time()) - int(doc.get("computed_at") or 0)
        return doc
    except Exception:
        return None


_CACHE: dict = {"at": 0.0, "data": None}


def get(force: bool = False) -> dict:
    """Serve: in-proc cache → fresh persisted doc → live fetch. On a live-feed
    miss, fall back to the last persisted doc so the dial never blanks out."""
    now = time.time()
    if not force and _CACHE["data"] is not None and (now - _CACHE["at"]) < _TTL_SEC:
        return _CACHE["data"]
    if not force:
        doc = load_persisted()
        if doc is not None and doc.get("age_sec", 1e12) < _PERSIST_FRESH_SEC:
            _CACHE.update(at=now, data=doc)
            return doc
    data = compute()
    if data.get("error"):
        fallback = load_persisted()
        if fallback is not None:
            return fallback
    else:
        _CACHE.update(at=now, data=data)
    return data
