"""JIT news-read — does recent news make this name more or less buyable?

On-demand ONLY (never preloaded). Pulls recent Massive headlines for the ticker,
classifies the net read into a simple swing-trader verdict
(more_buyable / neutral / less_buyable / sell) with a one-line reason. Uses the
local LLM when configured; falls back to a keyword-tone heuristic. Cached 15 min
per symbol so re-clicks don't re-hit the model.

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


def _heuristic(tones: list[str]) -> tuple[str, str]:
    """Verdict from keyword-tone counts when the LLM isn't available."""
    bull = tones.count("bullish")
    bear = tones.count("bearish")
    net = bull - bear
    if net >= 2:
        return "more_buyable", f"{bull} bullish vs {bear} bearish headlines — news leans constructive."
    if net == 1:
        return "more_buyable", f"Slightly more bullish ({bull}) than bearish ({bear}) headlines."
    if net <= -2:
        return ("sell" if bear >= 3 else "less_buyable"), f"{bear} bearish vs {bull} bullish headlines — news leans negative."
    if net == -1:
        return "less_buyable", f"Slightly more bearish ({bear}) than bullish ({bull}) headlines."
    return "neutral", f"Mixed tape — {bull} bullish, {bear} bearish."


def news_read(symbol: str, force: bool = False) -> dict:
    sym = (symbol or "").upper().strip()
    if not sym:
        return {"available": False, "reason": "no symbol"}
    if not force:
        hit = _cache.get(sym)
        if hit and (time.time() - hit["ts"]) < _TTL:
            return hit["data"]

    from .evidence import _fetch_massive_news, _tag_news_tone
    raw = _fetch_massive_news(sym, hours=72) or []
    items = []
    for n in raw[:12]:
        title = n.get("title") or ""
        tone = _tag_news_tone(title, n.get("description") or "")
        items.append({
            "title": title,
            "url": n.get("url"),
            "publisher": n.get("publisher"),
            "when": n.get("published_utc"),
            "tone": tone,
        })

    now = datetime.now(timezone.utc).isoformat()
    if not items:
        data = {"available": False, "reason": "No recent news (last 72h).",
                "verdict": "neutral", "label": "No recent news", "color": "slate",
                "n": 0, "headlines": [], "as_of": now, "disclaimer": DISCLAIMER}
        _cache[sym] = {"ts": time.time(), "data": data}
        return data

    tones = [i["tone"] for i in items]
    verdict, reason = _heuristic(tones)
    source = "heuristic"

    # Prefer an LLM read when configured — a real one-line summary verdict.
    try:
        from llm import chat, is_enabled
        if is_enabled():
            lines = "\n".join(f"- ({i['tone']}) {i['title']}" for i in items if i["title"])
            system = (
                "You classify equity NEWS for a swing trader who only buys constructive setups. "
                "From the headlines decide if the news makes the stock MORE buyable, LESS buyable, "
                "a SELL, or NEUTRAL. Reply ONLY JSON: "
                '{"verdict":"more_buyable|less_buyable|sell|neutral","reason":"<=18 words"}. '
                "Reason states WHAT in the news drives it. No advice — just the news read."
            )
            prompt = f"Ticker {sym}. Recent headlines (last 72h):\n{lines}\n\nClassify."
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
        "headlines": items[:8],
        "source": source,
        "as_of": now,
        "disclaimer": DISCLAIMER,
    }
    _cache[sym] = {"ts": time.time(), "data": data}
    log.info("news_read[%s]: %s (%s, n=%d)", sym, verdict, source, len(items))
    return data
