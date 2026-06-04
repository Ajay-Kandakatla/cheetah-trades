"""Per-card SEPA enrichment — JIT signals shown as chips on SEPA cards.

The SEPA scan stores trend/RS/stage/volume on each candidate. Two
additional signals the user wants chip-visibility on don't fit in the
scan (too expensive to compute for every ticker every night) but are
cheap to compute per-card on demand:

  1. Cluster insider buy — SEC Form 4 cluster: ≥3 unique insiders filing
     in the last 30 days. Bullish tell per Minervini's playbook.
  2. Valuation signal — undervalued / fair / overvalued based on the
     existing stock_analysis.valuation_score (P/E + P/B + P/S composite).

Strategy
--------
Each (symbol → enrichment) tuple is cached in Mongo for 24h. The card
in the SEPA list calls this endpoint when it enters the viewport
(IntersectionObserver in React). If a fresh row exists, it's returned
immediately; otherwise both signals are computed in parallel and cached.

Cheap to recompute: the insider call hits EDGAR's FTS (free); the
valuation read is a slim view of an analysis cache that may already be
warm from a prior visit to the candidate detail page.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional

log = logging.getLogger("sepa.card_enrichment")

# Per-symbol cache TTL. Insider data on EDGAR turns over slowly (Form 4
# filings are daily but the cluster signal only flips when 3+ insiders
# file fresh — that's a multi-day event). Valuation numbers move on
# earnings, also slow. 24h is plenty.
_CACHE_TTL_SEC = 24 * 3600

_coll = None
_disabled = False


def _get_coll():
    """Lazy Mongo handle for the ``card_enrichment_cache`` collection.
    Returns None on connection failure so callers can degrade
    gracefully (compute live each call rather than crashing)."""
    global _coll, _disabled
    if _disabled:
        return None
    if _coll is not None:
        return _coll
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DB", "cheetah")
        cli = MongoClient(url, serverSelectionTimeoutMS=2000)
        cli.admin.command("ping")
        coll = cli[db_name].card_enrichment_cache
        coll.create_index([("symbol", ASCENDING)], unique=True)
        coll.create_index([("cached_at", ASCENDING)])
        _coll = coll
        return _coll
    except Exception as exc:
        log.warning("card_enrichment: Mongo unavailable (%s)", exc)
        _disabled = True
        return None


# --------------------------------------------------------------------------
# Valuation signal — map stock_analysis.valuation_score to a 3-bucket label.
# --------------------------------------------------------------------------
def _valuation_signal_from_score(score: Optional[int]) -> Optional[str]:
    """Map the 0–100 composite valuation score (higher = cheaper, lower =
    pricier) to a human chip label.

    Bands chosen so "undervalued" requires meaningful margin of safety
    (P/E < ~15, P/B < ~3, P/S < ~5 ballpark), "overvalued" flags
    genuinely pricey names (P/E > ~35 typical), and "fair" sits between
    so the most common case doesn't decorate the card with a chip.
    """
    if score is None:
        return None
    if score >= 70:
        return "undervalued"
    if score >= 40:
        return "fair"
    return "overvalued"


def _extract_valuation(analysis_blob: dict) -> dict:
    """Pull just the valuation panel from an analysis_for() response.
    Shape (from sepa.stock_analysis.analysis_for):
        {fundamental: {available, headline, valuation: {score, label,
                       metrics: {pe, forward_pe, price_to_book,
                       price_to_sales, peg}, formula}, ...}, ...}
    Note: 2026-05-27 — confirmed via direct probe that the valuation
    panel sits under .fundamental.valuation, not top-level .valuation.
    Pre-this-fix the chip never rendered because the extractor was
    looking one nesting level too shallow.
    We slim to the 4 numbers the chip + hover tooltip need."""
    fundamental = (analysis_blob or {}).get("fundamental") or {}
    val = fundamental.get("valuation") or {}
    metrics = val.get("metrics") or {}
    score = val.get("score")
    return {
        "score":       score,
        "signal":      _valuation_signal_from_score(score),
        "label":       val.get("label"),  # human label from stock_analysis
        "pe":          metrics.get("pe"),
        "forward_pe":  metrics.get("forward_pe"),
        "pbv":         metrics.get("price_to_book"),
        "psales":      metrics.get("price_to_sales"),
        "peg":         metrics.get("peg"),
    }


def _extract_headline(analysis_blob: dict) -> dict:
    """Pull the company net-worth / shareholders'-equity figures (from
    ``.fundamental.headline``) so the card can show them next to the valuation
    chip — the same numbers the detail-page CompanyHeadline strip shows."""
    fundamental = (analysis_blob or {}).get("fundamental") or {}
    head = fundamental.get("headline") or {}
    return {
        "market_cap":          head.get("market_cap"),          # "current net worth"
        "shareholder_equity":  head.get("shareholder_equity"),  # book equity
    }


# --------------------------------------------------------------------------
# Public entry — compute or fetch from cache
# --------------------------------------------------------------------------
async def enrich(symbol: str, *, force_refresh: bool = False) -> dict:
    """Return both signals for ``symbol``. Cached 24h in Mongo.

    Shape returned:

    .. code-block:: python

        {
          "symbol": "MU",
          "cached_at": 1779999999,
          "fresh": True,
          "insider": {
              "cluster_buy": True,
              "unique_insiders_30d": 4,
              "form4_count_30d": 6,
          },
          "valuation": {
              "signal": "fair",   # "undervalued" | "fair" | "overvalued" | None
              "score":  62,
              "pe":     22.4,
              "pbv":    3.1,
              "psales": 5.2,
              "peg":    1.4,
          },
        }
    """
    sym = (symbol or "").upper().strip()
    if not sym:
        return {"symbol": symbol, "error": "invalid symbol"}

    # Cache hit (if not forcing refresh) — return immediately
    coll = _get_coll()
    now = int(time.time())
    if coll is not None and not force_refresh:
        try:
            doc = coll.find_one({"symbol": sym})
            # The `doc.get("headline") is not None` guard forces a recompute for
            # cards cached BEFORE the net-worth/equity headline was added, so it
            # shows up immediately instead of waiting out the 24h TTL.
            if (doc and (now - (doc.get("cached_at") or 0)) < _CACHE_TTL_SEC
                    and doc.get("headline") is not None):
                return {
                    "symbol":     sym,
                    "cached_at":  doc.get("cached_at"),
                    "fresh":      False,
                    "insider":    doc.get("insider") or {},
                    "valuation":  doc.get("valuation") or {},
                    "headline":   doc.get("headline") or {},
                    # Macro risk is overlaid FRESH (hourly market read), never
                    # frozen in the 24h card cache.
                    "macro_risk": _macro_for(sym),
                }
        except Exception as exc:
            log.warning("card_enrichment cache read failed for %s: %s", sym, exc)

    # Compute both signals in parallel.
    insider_task = asyncio.create_task(_compute_insider(sym))
    fundamentals_task = asyncio.create_task(_compute_fundamentals(sym))
    insider, fundamentals = await asyncio.gather(insider_task, fundamentals_task)
    valuation = (fundamentals or {}).get("valuation") or {}
    headline = (fundamentals or {}).get("headline") or {}

    payload = {
        "symbol":     sym,
        "cached_at":  now,
        "fresh":      True,
        "insider":    insider,
        "valuation":  valuation,
        "headline":   headline,
        "macro_risk": _macro_for(sym),
    }

    # Best-effort cache write. A failure here doesn't break the response —
    # next call recomputes (which is fine, just costs the EDGAR/analysis
    # round trip again).
    if coll is not None:
        try:
            coll.update_one(
                {"symbol": sym},
                {"$set": {
                    "symbol":     sym,
                    "insider":    insider,
                    "valuation":  valuation,
                    "headline":   headline,
                    "cached_at":  now,
                }},
                upsert=True,
            )
        except Exception as exc:
            log.warning("card_enrichment cache write failed for %s: %s", sym, exc)

    return payload


def _macro_for(sym: str) -> dict:
    """Per-stock macro-risk overlay from the hourly-cached market read. Cheap +
    pure; returns {} if the market read isn't available yet."""
    try:
        from sepa import macro_risk as mrisk
        market = mrisk.get_market()
        return mrisk.score_stock(sym, market) if market else {}
    except Exception as exc:
        log.warning("card_enrichment macro_risk for %s failed: %s", sym, exc)
        return {}


async def _compute_insider(sym: str) -> dict:
    """Compute the cluster-insider signal from EDGAR. Slim view: just
    the fields the chip + tooltip need."""
    try:
        from sepa.insider import insider_activity
        full = await insider_activity(sym)
        return {
            # cluster_buy now means real open-market buying by officers/directors
            "cluster_buy":          bool(full.get("form4_cluster_buy")),
            "unique_insiders_30d":  int(full.get("form4_unique_insiders_30d") or 0),
            "form4_count_30d":      int(full.get("form4_count_30d") or 0),
            "buy_count_30d":        int(full.get("form4_buy_count_30d") or 0),
            "insider_buyers_30d":   int(full.get("form4_insider_buyers_30d") or 0),
            "has_recent_13d":       bool(full.get("has_recent_13d")),
        }
    except Exception as exc:
        log.warning("card_enrichment._compute_insider(%s) failed: %s", sym, exc)
        return {"cluster_buy": False, "unique_insiders_30d": 0, "form4_count_30d": 0,
                "buy_count_30d": 0, "insider_buyers_30d": 0}


async def _compute_fundamentals(sym: str) -> dict:
    """Compute the valuation signal + the net-worth/equity headline from a
    SINGLE stock-analysis fetch. Returns {"valuation": {...}, "headline": {...}}."""
    try:
        # ``analysis_for`` is sync — wrap with to_thread so the
        # enrichment endpoint stays cooperative. Caching of the full
        # analysis blob is handled in stock_analysis.py (Mongo, schema-
        # versioned, 60-min TTL).
        from sepa.stock_analysis import analysis_for
        analysis = await asyncio.to_thread(analysis_for, sym, False)
        return {
            "valuation": _extract_valuation(analysis or {}),
            "headline":  _extract_headline(analysis or {}),
        }
    except Exception as exc:
        log.warning("card_enrichment._compute_fundamentals(%s) failed: %s", sym, exc)
        return {"valuation": {"score": None, "signal": None}, "headline": {}}
