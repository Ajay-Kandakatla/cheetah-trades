"""Gemma review — short narrative summary of WHY a stock is moving.

Hand the candidate's prices, news, filings, and chatter samples to the
local Gemma instance via the existing `llm` client. Ask for:
  - one-sentence catalyst description
  - bull pull (max 1 sentence)
  - bear pull (max 1 sentence)
  - evidence_grade A/B/C/D
  - is_pump_warning bool — true if chatter is loud but evidence is thin

If LLM is disabled (no LM Studio running) we return a minimal heuristic
review derived from the same inputs so the UI still has something to show.
"""
from __future__ import annotations

import logging
from typing import Optional

from llm import chat as llm_chat, is_enabled as llm_is_enabled

log = logging.getLogger("catalysts.gemma_review")


def _heuristic_review(candidate: dict, chatter: dict, evidence: dict, scores: dict) -> dict:
    """Fallback when Gemma isn't running."""
    quad = scores.get("quadrant")
    parts = []
    news = (evidence or {}).get("news") or {}
    sec = (evidence or {}).get("sec_filings") or {}

    if news.get("n_bullish"):
        first = (news.get("bullish") or [{}])[0]
        parts.append(first.get("title") or "Bullish news")
    elif news.get("n_bearish"):
        first = (news.get("bearish") or [{}])[0]
        parts.append(first.get("title") or "Bearish news")
    elif sec.get("has_8k"):
        parts.append("Recent 8-K filing")
    elif sec.get("has_offering"):
        parts.append("Recent offering filing (dilutive)")
    elif chatter.get("velocity_per_hour", 0) > 1:
        parts.append("Heavy social chatter, no clear catalyst yet")
    else:
        parts.append("Price moved on light catalyst")

    catalyst = parts[0]

    return {
        "catalyst_summary": catalyst,
        "bull_pull": None,
        "bear_pull": None,
        "evidence_grade": _grade_from_score(scores.get("evidence_score") or 0),
        "is_pump_warning": quad == "PUMP_RISK",
        "_method": "heuristic",
    }


def _grade_from_score(score: float) -> str:
    if score >= 70: return "A"
    if score >= 50: return "B"
    if score >= 30: return "C"
    return "D"


def _build_prompt(c: dict, ch: dict, ev: dict, scores: dict) -> str:
    """Compact prompt that fits in Gemma's context easily for ~30 candidates."""
    name = c.get("company_name") or c.get("ticker")
    chg = c.get("change_pct")
    surge = c.get("volume_surge_ratio")
    cap = c.get("market_cap")
    cap_str = f"${cap/1e6:.0f}M" if cap else "unknown"

    news_titles = []
    for n in (ev.get("news") or {}).get("bullish", [])[:3]:
        news_titles.append(f"  + [BULL] {n.get('title')}")
    for n in (ev.get("news") or {}).get("bearish", [])[:2]:
        news_titles.append(f"  − [BEAR] {n.get('title')}")
    for n in (ev.get("news") or {}).get("neutral", [])[:1]:
        news_titles.append(f"  · [NEUT] {n.get('title')}")
    news_block = "\n".join(news_titles) or "  (no news in last 48h)"

    filings = []
    for f in (ev.get("sec_filings") or {}).get("items", [])[:5]:
        filings.append(f"  · {f.get('form')} on {f.get('filing_date')} ({f.get('tone')})")
    filings_block = "\n".join(filings) or "  (no recent SEC filings)"

    blurbs = (ch.get("sample_blurbs") or [])[:3]
    blurb_block = "\n".join(f"  > {b}" for b in blurbs) or "  (no recent chatter)"

    return f"""You're a sharp swing-trader analyst reviewing a small-cap stock that
moved unusually today. Give me a TIGHT, honest read.

TICKER: {c.get('ticker')} ({name})
PRICE: ${c.get('price'):.2f}  ·  CHANGE: {chg:+.2f}%  ·  CAP: {cap_str}
VOLUME SURGE: {surge or '?'}× avg
QUADRANT (system-assigned): {scores.get('quadrant')}  (chatter {scores.get('chatter_score')}/100, evidence {scores.get('evidence_score')}/100)

RECENT NEWS (48h):
{news_block}

RECENT SEC FILINGS (7 days):
{filings_block}

SAMPLE CHATTER (Stocktwits / Reddit):
{blurb_block}

Return ONLY a JSON object with these exact keys:
  "catalyst_summary": one sentence, ≤25 words, plain English, what's actually moving the stock
  "bull_pull": one sentence, the strongest reason to be long here, or null if there isn't one
  "bear_pull": one sentence, the biggest risk or hidden gotcha, or null if there isn't one
  "evidence_grade": "A" | "B" | "C" | "D" — A means real catalyst with hard evidence; D means pure speculation
  "is_pump_warning": true/false — true if chatter is loud but evidence is thin or there's a recent dilutive offering
"""


def review(candidate: dict, chatter: dict, evidence: dict, scores: dict, *,
           timeout_sec: int = 25) -> dict:
    """Run a Gemma review on one candidate.

    On error / timeout / disabled LLM, falls back to heuristic.
    """
    if not llm_is_enabled():
        return _heuristic_review(candidate, chatter, evidence, scores)

    prompt = _build_prompt(candidate, chatter, evidence, scores)
    try:
        result = llm_chat(
            prompt,
            json_only=True,
            max_tokens=300,
            temperature=0.3,
            timeout=timeout_sec,
        )
        if not isinstance(result, dict) or not result.get("catalyst_summary"):
            # Empty / malformed response → blend in heuristic so the user
            # always gets a useful catalyst_summary (the most-shown field).
            heur = _heuristic_review(candidate, chatter, evidence, scores)
            if not isinstance(result, dict):
                return heur
            return {
                "catalyst_summary": result.get("catalyst_summary") or heur["catalyst_summary"],
                "bull_pull": result.get("bull_pull"),
                "bear_pull": result.get("bear_pull"),
                "evidence_grade": (result.get("evidence_grade") or "").upper()[:1] or heur["evidence_grade"],
                "is_pump_warning": bool(result.get("is_pump_warning")) if "is_pump_warning" in result else heur["is_pump_warning"],
                "_method": "gemma+heuristic",
            }
        return {
            "catalyst_summary": result.get("catalyst_summary"),
            "bull_pull": result.get("bull_pull"),
            "bear_pull": result.get("bear_pull"),
            "evidence_grade": (result.get("evidence_grade") or "").upper()[:1] or _grade_from_score(scores.get("evidence_score", 0)),
            # Default is_pump_warning to TRUE when quadrant is PUMP_RISK and
            # the LLM didn't explicitly contradict (saves us from missing the
            # most important UX signal).
            "is_pump_warning": bool(result.get("is_pump_warning",
                scores.get("quadrant") == "PUMP_RISK")),
            "_method": "gemma",
        }
    except Exception as exc:
        log.warning("gemma review failed for %s: %s", candidate.get("ticker"), exc)
        return _heuristic_review(candidate, chatter, evidence, scores)


__all__ = ["review"]
