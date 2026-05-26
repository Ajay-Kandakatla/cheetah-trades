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
SYSTEM_PROMPT = """You are a senior macro/markets analyst writing a 30-SECOND macro brief for an active retail trader using Minervini's SEPA framework.

This is a QUICK READ. Tight bullets, not paragraphs. The trader is glancing at this before placing an order.

Output ONLY structured markdown — start directly with the first heading. Cover exactly these sections, in this order:

## 🎯 Why this is SEPA + catalyst
Why did this name pass Minervini's SEPA filter (Trend Template 8/8, RS ≥ 70, Stage 2, tight base) AND what is moving it RIGHT NOW. The page-context JSON below tells you which SEPA gates the stock currently passes — ground your answer in that, don't invent. Plus the active catalyst (earnings, FDA, contract win, sector tailwind, guidance raise). 2–3 short bullets MAX.

## 🌍 Geopolitical & macro risks
2–3 SHORT BULLETS. One sentence each. Be specific about the transmission mechanism (not "China tensions" — name the actual exposure and how it hits revenue/margin).

## 📈 Futures / commodities tied to this stock
2–3 bullets. Format: `**TICKER** — one-line why it matters`. Name the actual contract (e.g. **HG (copper)**, **USD/KRW**, **WTI**, **10Y yields**, **DRAM contract**).

## 🐻 Bear case right now
2–3 SHORT BULLETS. One sentence each. Specific to THIS company at TODAY's setup — not generic stock-market risk.

## Sector context
ONE SENTENCE. The single most-important sector dynamic framing this stock's near-term tape.

Constraints:
- TOTAL LENGTH ≤ 250 words. This is a 30-second scan, not an essay.
- No paragraphs longer than one sentence each in bullets.
- No price targets.
- Honest — if the bear case is weak, say so.
- Don't repeat the ticker every sentence.
- Don't preface with "Here is the analysis" — start with the first heading."""


def _build_user_prompt(symbol: str) -> str:
    """Build the user-side prompt. Pulls the SEPA snapshot for this ticker
    from the latest scan so the LLM can ground "why this is SEPA" in real
    data (which gates it passes, its score, base count, day move) rather
    than guessing.

    SEPA lookup is best-effort — if the scan cache is missing or the
    ticker isn't in it, we degrade to just the symbol and let the LLM
    speak in general terms about what makes a name SEPA-grade.
    """
    sepa_block = _format_sepa_snapshot(symbol)
    if sepa_block:
        return (
            f"Macro brief for ticker: {symbol}\n\n"
            f"## Live SEPA snapshot (use this in the 'Why SEPA' section)\n"
            f"```json\n{sepa_block}\n```"
        )
    return f"Macro brief for ticker: {symbol}\n\n(SEPA snapshot unavailable — speak in general SEPA terms.)"


def _format_sepa_snapshot(symbol: str) -> Optional[str]:
    """Pull the salient SEPA fields for `symbol` from the latest scan
    cache. Returns a compact JSON string or None if not found."""
    try:
        from sepa import scanner as sc
        import json as _json
        latest = sc.load_latest() or {}
        rows = (latest.get("all_results") or []) + (latest.get("candidates") or [])
        rec = next((r for r in rows if r.get("symbol", "").upper() == symbol), None)
        if not rec:
            return None
        # Pick only the fields the macro LLM needs — keep payload small.
        snap = {
            "score":         rec.get("score"),
            "rating":        rec.get("rating"),
            "rs_rank":       rec.get("rs_rank"),
            "stage":         (rec.get("stage") or {}).get("stage"),
            "trend_passed":  (rec.get("trend") or {}).get("passed"),
            "trend_pass_all": (rec.get("trend") or {}).get("pass_all"),
            "has_vcp_base":  (rec.get("vcp") or {}).get("has_base"),
            "is_power_play": (rec.get("power_play") or {}).get("is_power_play"),
            "base_count":    (rec.get("base_count") or {}).get("base_count"),
            "late_base":     (rec.get("base_count") or {}).get("is_late_stage"),
            "adr_pct":       rec.get("adr_pct"),
            "day_change_pct": rec.get("day_change_pct"),
            "last_close":    rec.get("last_close"),
            "is_etf":        rec.get("is_etf"),
            "pioneer_themes": rec.get("pioneer_themes"),
        }
        # Drop nulls so the LLM doesn't see noise.
        snap = {k: v for k, v in snap.items() if v not in (None, "", [])}
        return _json.dumps(snap, default=str)
    except Exception as exc:
        log.debug("macro: SEPA snapshot lookup failed for %s: %s", symbol, exc)
        return None


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
            max_tokens=600,              # 30-sec read — cap to ~400-500 tokens output
            temperature=0.3,
            timeout=90,
            provider="anthropic",
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
