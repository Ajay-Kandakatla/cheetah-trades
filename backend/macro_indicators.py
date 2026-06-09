"""Macro indicators panel — the Market Gauge page's live economic dashboard.

Surfaces the macro series we ALREADY pull from FRED for the gauge's Economic
pillar (backend/sepa/fred.py), but with the TREND and the next scheduled release
date attached so the page can show "how it's changing" and "what's coming":

    CPIAUCSL  — CPI, All Urban Consumers  → YoY inflation %        (good: down)
    CPILFESL  — Core CPI (ex food/energy) → YoY %                  (good: down)
    UNRATE    — Civilian Unemployment Rate (%)                     (good: down)
    FEDFUNDS  — Federal Funds Effective Rate (%)                   (good: neutral)
    T10Y3M    — 10-Year minus 3-Month Treasury spread (%)         (good: up)

Each indicator carries: the latest value, the prior print, the change, a
~24-point trend for a sparkline, the reference date of the latest print, and the
next scheduled release date (reused from macro_calendar's real FRED release
calendar). Educational context for the regime read — NOT advice, NOT a forecast.

Same cache shape as sepa/market_gauge: a Mongo `macro_indicators/latest` doc
warmed by a daily cron, an in-process TTL, and a graceful degrade to whatever was
last persisted when FRED is unreachable. With no FRED_API_KEY the panel returns
an empty indicator list (honest — never fabricated numbers).
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("macro_indicators")

# id, FRED series, label, transform, unit, which direction is "healthy",
# the macro_calendar release `kind` to read the next date from, and a blurb.
INDICATORS = [
    {"id": "cpi", "series": "CPIAUCSL", "label": "CPI (headline)",
     "transform": "yoy", "unit": "%", "good": "down", "release": "cpi",
     "freq": "monthly", "blurb": "All-items inflation, year-over-year"},
    {"id": "core_cpi", "series": "CPILFESL", "label": "Core CPI",
     "transform": "yoy", "unit": "%", "good": "down", "release": "cpi",
     "freq": "monthly", "blurb": "Ex food & energy — the Fed's underlying trend"},
    {"id": "unrate", "series": "UNRATE", "label": "Unemployment",
     "transform": "level", "unit": "%", "good": "down", "release": "jobs",
     "freq": "monthly", "blurb": "Civilian unemployment rate"},
    {"id": "fedfunds", "series": "FEDFUNDS", "label": "Fed Funds Rate",
     "transform": "level", "unit": "%", "good": "neutral", "release": "fomc",
     "freq": "monthly", "blurb": "Effective policy rate (next move set at FOMC)"},
    {"id": "yield_curve", "series": "T10Y3M", "label": "10y–3m Spread",
     "transform": "level", "unit": "%", "good": "up", "release": None,
     "freq": "daily", "blurb": "Recession curve — negative = inverted"},
]

_TTL_SEC = 6 * 3600            # FRED updates daily at most; 6h in-proc is plenty
_PERSIST_FRESH_SEC = 36 * 3600  # a daily-cron doc stands as "current" for ~1.5d
_TREND_POINTS = 24


# ── pure assembly (unit-testable; no network) ────────────────────────────────
def _assemble(cfg: dict, hist: list, next_release: Optional[str] = None) -> Optional[dict]:
    """PURE: (config, [(date,value)] newest-first, next-release date) → one
    indicator dict, or None when there's not even a latest value. `hist` is
    already transformed (YoY for CPI, raw level for rates)."""
    if not hist:
        return None
    as_of, value = hist[0]
    prev = hist[1][1] if len(hist) > 1 else None
    change = round(value - prev, 2) if prev is not None else None
    direction = "flat"
    if change is not None:
        direction = "up" if change > 0.0001 else "down" if change < -0.0001 else "flat"
    # Sparkline wants oldest→newest.
    trend = [v for (_d, v) in reversed(hist)]
    return {
        "id": cfg["id"],
        "label": cfg["label"],
        "blurb": cfg["blurb"],
        "series": cfg["series"],
        "unit": cfg["unit"],
        "good": cfg["good"],            # which direction is healthy (FE colors)
        "transform": cfg["transform"],  # "yoy" | "level"
        "value": round(value, 2),
        "prev": round(prev, 2) if prev is not None else None,
        "change": change,
        "direction": direction,
        "as_of": as_of,                 # reference date of the latest print
        "as_of_label": _month_label(as_of) if cfg.get("freq") == "monthly" else as_of,
        "trend": trend,
        "next_release": next_release,
        "next_release_label": _short_date(next_release) if next_release else None,
    }


def _month_label(ymd: str) -> str:
    """'2026-04-01' → 'Apr 2026' (monthly series reference month)."""
    try:
        return datetime.strptime(ymd, "%Y-%m-%d").strftime("%b %Y")
    except Exception:
        return ymd


def _short_date(ymd: str) -> str:
    """'2026-06-11' → 'Jun 11'."""
    try:
        return datetime.strptime(ymd, "%Y-%m-%d").strftime("%b %-d")
    except Exception:
        return ymd


def _history_for(cfg: dict) -> list:
    """Fetch + transform a series into [(date, value)] newest-first."""
    from sepa import fred
    if cfg["transform"] == "yoy":
        return fred.yoy_history(cfg["series"], _TREND_POINTS)
    return fred.level_history(cfg["series"], _TREND_POINTS)


def _next_releases() -> dict:
    """kind -> earliest upcoming release date (YYYY-MM-DD), from the real FRED
    release calendar macro_calendar already reads. Empty on any failure."""
    out: dict = {}
    try:
        import macro_calendar
        for e in macro_calendar._fred_releases(45):
            k, d = e.get("kind"), e.get("date")
            if k and d and (k not in out or d < out[k]):
                out[k] = d
    except Exception as exc:
        log.debug("macro_indicators: next-release lookup failed: %s", exc)
    return out


# ── compute / persist / serve (mirrors sepa/market_gauge) ────────────────────
def compute() -> dict:
    releases = _next_releases()
    indicators = []
    for cfg in INDICATORS:
        try:
            hist = _history_for(cfg)
            nr = releases.get(cfg["release"]) if cfg.get("release") else None
            ind = _assemble(cfg, hist, nr)
            if ind:
                indicators.append(ind)
        except Exception as exc:
            log.warning("macro_indicators: %s failed: %s", cfg["id"], exc)
    try:
        from sepa import fred
        fred_available = fred.available()
    except Exception:
        fred_available = False
    now = int(time.time())
    return {
        "generated_at": now,
        "generated_at_iso": datetime.now(timezone.utc).isoformat(),
        "indicators": indicators,
        "fred_available": fred_available,
        "disclaimer": (
            "Live macro context from the St. Louis Fed (FRED). CPI/Core CPI are "
            "year-over-year; unemployment, Fed funds and the 10y–3m spread are "
            "shown as levels. Educational — not a forecast, not advice."),
    }


def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        return client[os.getenv("MONGO_DB", "cheetah")].macro_indicators
    except Exception:
        return None


def run_and_persist() -> dict:
    """Compute + upsert the `latest` doc. Called by the daily
    `sepa.cli macro-indicators-refresh` cron (after the 8:30 ET CPI print)."""
    payload = compute()
    coll = _coll()
    if coll is not None:
        try:
            doc = dict(payload)
            doc["_id"] = "latest"
            doc["computed_at"] = int(time.time())
            coll.update_one({"_id": "latest"}, {"$set": doc}, upsert=True)
            log.info("macro_indicators persisted: %d series", len(payload.get("indicators", [])))
        except Exception as exc:
            log.warning("macro_indicators persist failed: %s", exc)
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
    """Serve the panel: in-proc cache → fresh persisted doc → live compute."""
    now = time.time()
    if not force and _CACHE["data"] is not None and (now - _CACHE["at"]) < _TTL_SEC:
        return _CACHE["data"]
    if not force:
        doc = load_persisted()
        if doc is not None and doc.get("age_sec", 1e12) < _PERSIST_FRESH_SEC:
            _CACHE.update(at=now, data=doc)
            return doc
    data = compute()
    _CACHE.update(at=now, data=data)
    return data
