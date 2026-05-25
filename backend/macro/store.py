"""Storage + LLM call for the macro-context module.

Cache shape (Mongo ``macro_context`` collection)::

    {
      _id: ObjectId,
      symbol:       "MU",
      analysis:     "## Geopolitical risks\n…",   # raw markdown from Claude
      headlines:    [{title, url, source, published_at}, ...],
      provider:     "anthropic" | "local",
      model:        "claude-sonnet-4-5",
      generated_at: 1779200556,
      ttl_at:       1779222156,                    # 6h after generated_at
    }

A read with a fresh cache hit returns the stored doc unchanged.
A miss (or ``force=True``) triggers a fresh Claude call + Finnhub
news pull, upserts the row, and returns the new payload.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("macro.store")

# 6h cache — see module docstring rationale.
TTL_SEC = 6 * 60 * 60

_db = None
_disabled = False


def _get_db():
    global _db, _disabled
    if _disabled:
        return None
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        _db = client[os.getenv("MONGO_DB", "cheetah")]
        # Unique per symbol — one cached doc, last write wins.
        _db.macro_context.create_index([("symbol", ASCENDING)], unique=True)
        return _db
    except Exception as exc:
        log.warning("macro.store: Mongo unavailable (%s) — disabling persistence", exc)
        _disabled = True
        return None


# ----------------------------------------------------------------------
# Claude prompt
# ----------------------------------------------------------------------
SYSTEM_PROMPT = """You are a senior macro/markets analyst writing a short ticker-specific brief for an active retail trader.

Output ONLY structured markdown — no preamble like "Here is the analysis." Start directly with the first heading. Cover exactly these sections, in this order:

## 🌍 Geopolitical & macro risks
The 2–4 specific macro forces that could move THIS company's stock right now. Tariffs, sanctions, election cycles, central-bank moves, FX, labor disputes at suppliers, regulation, etc. One short paragraph each. Be specific about transmission mechanism — don't just list "China tensions"; say *how* China tensions would hit this stock (e.g. "20% of revenue from China; CHIPS Act sanctions could cut access to BoE-supplied tools").

## 📈 Futures / commodities tied to this stock
The 2–3 most-correlated futures contracts, commodities, or rate instruments. Memory chip companies: DRAM contract pricing, NAND spot, USD/KRW. Oil majors: WTI, Brent. Banks: 10Y yields, 2s10s. Be specific — name the actual ticker / contract.

## 🐻 Bear case right now
The most credible reasons this stock could underperform in the next 1–3 months. Cyclical risk, valuation, customer concentration, technology pivots. Not generic "stocks can go down"; specific to THIS company at TODAY's valuation. 2–4 bullets.

## Sector context
The 2–3 sector dynamics that frame this stock's near-term tape. Industry capex cycle, competitive landscape moves, regulatory backdrop. Brief — half a paragraph.

Constraints:
- Total length ≤ 700 words.
- No price targets (you don't see live data).
- Honest. If the bear case is weak, say so. If geopolitical risk is overblown, say so.
- Cite specific company names, supplier names, product names where useful.
- Don't repeat the ticker symbol every sentence — assume the reader knows."""


def _build_user_prompt(symbol: str) -> str:
    return f"Macro brief for ticker: {symbol}"


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------
def get_macro_context(symbol: str, *, force: bool = False) -> dict:
    """Return cached macro brief (and refresh if stale or ``force=True``).

    Returns shape::

        {
          ok:            True,
          symbol:        "MU",
          analysis:      "## Geopolitical…",     # markdown
          headlines:     [{title, url, source, published_at}, ...],
          provider:      "anthropic" | "local",
          model:         "claude-sonnet-4-5",
          generated_at:  epoch,
          ttl_at:        epoch,
          from_cache:    bool,
        }

    On LLM failure the function still returns ``ok: True`` with empty
    ``analysis`` so the modal renders the news headlines portion —
    Finnhub-only is still useful to the user.
    """
    symbol = (symbol or "").upper().strip()
    if not symbol:
        return {"ok": False, "error": "symbol required"}

    db = _get_db()
    now = int(time.time())

    # Cache lookup unless force-bypass.
    if not force and db is not None:
        doc = db.macro_context.find_one({"symbol": symbol})
        if doc and doc.get("ttl_at", 0) > now:
            doc.pop("_id", None)
            doc["from_cache"] = True
            doc["ok"] = True
            return doc

    # Cache miss / forced: do the work.
    analysis, provider, model = _call_llm(symbol)
    headlines = _recent_headlines(symbol)

    payload = {
        "symbol":       symbol,
        "analysis":     analysis,
        "headlines":    headlines,
        "provider":     provider,
        "model":        model,
        "generated_at": now,
        "ttl_at":       now + TTL_SEC,
    }

    if db is not None:
        try:
            db.macro_context.update_one(
                {"symbol": symbol},
                {"$set": payload},
                upsert=True,
            )
        except Exception as exc:
            log.warning("macro.store: upsert failed for %s: %s", symbol, exc)

    payload["from_cache"] = False
    payload["ok"] = True
    return payload


def _call_llm(symbol: str) -> tuple[str, str, Optional[str]]:
    """Run the macro prompt through Claude (or local fallback). Returns
    ``(analysis_markdown, provider_label, model_id)``. On failure
    returns empty analysis + 'unavailable' label — the modal handles
    the empty case by showing only the news headlines."""
    try:
        import llm
        resp = llm.chat(
            prompt=_build_user_prompt(symbol),
            system=SYSTEM_PROMPT,
            max_tokens=1400,
            temperature=0.3,
            timeout=90,
            provider="anthropic",        # auto-falls back to local if not configured
        )
        if not resp.get("ok"):
            log.warning("macro: LLM error for %s: %s", symbol, resp.get("error"))
            return ("", "unavailable", None)
        text = (resp.get("text") or "").strip()
        # Strip any leading preamble before the first markdown heading.
        head = text.find("## ")
        if head > 0:
            text = text[head:]
        return (text, resp.get("provider") or "anthropic", resp.get("model"))
    except Exception as exc:
        log.exception("macro: LLM call exploded for %s: %s", symbol, exc)
        return ("", "error", None)


def _recent_headlines(symbol: str, limit: int = 6) -> list[dict]:
    """Pull a handful of recent headlines via the existing news module.
    Best-effort — empty list on failure since the analysis text is the
    primary value of the modal."""
    try:
        import asyncio
        import news as news_mod
        # fetch_news is an async function in news.py. Run it in a fresh
        # loop because this helper might be called from a sync context
        # (the api endpoint already wraps us in to_thread).
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If somehow called from within a running loop, defer
                # to creating a new one in a thread.
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as ex:
                    rows = ex.submit(asyncio.run, news_mod.fetch_news(symbol)).result(timeout=15)
            else:
                rows = loop.run_until_complete(news_mod.fetch_news(symbol))
        except RuntimeError:
            rows = asyncio.run(news_mod.fetch_news(symbol))

        out: list[dict] = []
        for r in (rows or [])[:limit]:
            out.append({
                "title":        (r.get("headline") or r.get("title") or "")[:200],
                "url":          r.get("url") or r.get("link"),
                "source":       r.get("source") or r.get("provider") or "",
                "published_at": r.get("datetime") or r.get("published_at"),
            })
        return out
    except Exception as exc:
        log.warning("macro: headlines fetch failed for %s: %s", symbol, exc)
        return []


def _iso_from_epoch(ep) -> Optional[str]:
    """Helper for consumers that want an ISO string. Returns None on bad input."""
    if not ep:
        return None
    try:
        return datetime.fromtimestamp(int(ep), tz=timezone.utc).isoformat()
    except Exception:
        return None
