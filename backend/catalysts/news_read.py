"""JIT news-read — does recent news make this name more or less buyable?

On-demand ONLY (never preloaded). Pulls the ticker's recent headlines from the
SAME source the catalyst tab uses (sepa.catalyst._fetch_google_news — company-
name-resolved Google News with a per-headline sentiment score; Massive news as a
fallback), and classifies the net read into a simple swing-trader verdict
(more_buyable / neutral / less_buyable / sell) with a one-line reason. Uses the
local LLM when configured for the summary; falls back to the score heuristic.
Cached 15 min per symbol so re-clicks don't re-hit the model.

Educational — a read of recent news SENTIMENT for buyability, NOT a forecast and
NOT advice.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

log = logging.getLogger("catalysts.news_read")

_TTL = 15 * 60
_cache: dict = {}

VERDICT_META = {
    "more_buyable": {"label": "More buyable",          "color": "green"},
    "neutral":      {"label": "Mixed — no clear edge",  "color": "slate"},
    "less_buyable": {"label": "Less buyable",           "color": "amber"},
    "sell":         {"label": "Sell-side risk",         "color": "red"},
}

DISCLAIMER = ("A read of recent news sentiment for swing-buyability — not a "
              "forecast and not advice.")


def _tone_from_score(score: float) -> str:
    if score > 0.05:
        return "bullish"
    if score < -0.05:
        return "bearish"
    return "neutral"


def _fetch_news(sym: str) -> list[dict]:
    """Headlines + per-item tone. Google News (same as the catalyst tab) first,
    Massive (7d) as fallback. Each item: {title, url, tone, score}."""
    items: list[dict] = []
    try:
        import asyncio
        from sepa.catalyst import _fetch_google_news
        news = asyncio.run(_fetch_google_news(sym)) or []
        for n in news[:12]:
            sc = float(n.get("score") or 0.0)
            items.append({
                "title": n.get("title"),
                "url": n.get("link") or n.get("url"),
                "tone": _tone_from_score(sc),
                "score": round(sc, 3),
            })
    except Exception as exc:
        log.debug("news_read: google news failed for %s: %s", sym, exc)

    if not items:
        try:
            from .evidence import _fetch_massive_news, _tag_news_tone
            raw = _fetch_massive_news(sym, hours=168) or []
            for n in raw[:12]:
                tone = _tag_news_tone(n.get("title") or "", n.get("description") or "")
                sc = 1.0 if tone == "bullish" else -1.0 if tone == "bearish" else 0.0
                items.append({
                    "title": n.get("title"),
                    "url": n.get("url"),
                    "tone": tone,
                    "score": sc,
                })
        except Exception as exc:
            log.debug("news_read: massive fallback failed for %s: %s", sym, exc)
    return items


def _heuristic(items: list[dict]) -> tuple[str, str]:
    net = sum(i.get("score") or 0.0 for i in items)
    bull = sum(1 for i in items if i["tone"] == "bullish")
    bear = sum(1 for i in items if i["tone"] == "bearish")
    if net >= 0.6:
        return "more_buyable", f"Net-positive headlines ({bull} bullish vs {bear} bearish)."
    if net <= -0.6:
        return ("sell" if bear >= 3 else "less_buyable"), f"Net-negative headlines ({bear} bearish vs {bull} bullish)."
    if bull and not bear:
        return "more_buyable", f"{bull} bullish headlines, none bearish."
    if bear and not bull:
        return "less_buyable", f"{bear} bearish headlines, none bullish."
    return "neutral", f"Mixed — {bull} bullish, {bear} bearish."


def news_read(symbol: str, force: bool = False) -> dict:
    sym = (symbol or "").upper().strip()
    if not sym:
        return {"available": False, "reason": "no symbol"}
    if not force:
        hit = _cache.get(sym)
        if hit and (time.time() - hit["ts"]) < _TTL:
            return hit["data"]

    items = _fetch_news(sym)
    now = datetime.now(timezone.utc).isoformat()
    if not items:
        data = {"available": False, "reason": "No recent news found.",
                "verdict": "neutral", "label": "No recent news", "color": "slate",
                "n": 0, "headlines": [], "as_of": now, "disclaimer": DISCLAIMER}
        _cache[sym] = {"ts": time.time(), "data": data}
        return data

    verdict, reason = _heuristic(items)
    source = "headlines"

    # Prefer an LLM read when configured — a real one-line summary verdict.
    try:
        from llm import chat, is_enabled
        if is_enabled():
            lines = "\n".join(f"- ({i['tone']}) {i['title']}" for i in items if i.get("title"))
            system = (
                "You classify equity NEWS for a swing trader who only buys constructive setups. "
                "From the headlines decide if the news makes the stock MORE buyable, LESS buyable, "
                "a SELL, or NEUTRAL. Reply ONLY JSON: "
                '{"verdict":"more_buyable|less_buyable|sell|neutral","reason":"<=18 words"}. '
                "Reason states WHAT in the news drives it. No advice — just the news read."
            )
            prompt = f"Ticker {sym}. Recent headlines:\n{lines}\n\nClassify."
            res = chat(prompt, system=system, json_only=True, max_tokens=160, timeout=30)
            parsed = (res or {}).get("parsed") or {}
            v = (parsed.get("verdict") or "").strip().lower()
            if v in VERDICT_META:
                verdict = v
                reason = (parsed.get("reason") or reason).strip()
                source = "llm"
    except Exception as exc:
        log.debug("news_read LLM failed for %s: %s", sym, exc)

    meta = VERDICT_META[verdict]
    tones = [i["tone"] for i in items]
    data = {
        "available": True,
        "verdict": verdict,
        "label": meta["label"],
        "color": meta["color"],
        "reason": reason,
        "n": len(items),
        "tone_counts": {
            "bullish": tones.count("bullish"),
            "bearish": tones.count("bearish"),
            "neutral": tones.count("neutral"),
        },
        "headlines": [{"title": i["title"], "url": i["url"], "tone": i["tone"]} for i in items[:8]],
        "source": source,
        "as_of": now,
        "disclaimer": DISCLAIMER,
    }
    _cache[sym] = {"ts": time.time(), "data": data}
    log.info("news_read[%s]: %s (%s, n=%d)", sym, verdict, source, len(items))
    return data
