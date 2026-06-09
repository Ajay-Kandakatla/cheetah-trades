"""Catalyst detection — what could move a SEPA candidate today.

Three inputs:
  1. Earnings: upcoming (Finnhub earnings calendar) + last surprise (yfinance).
  2. News sentiment: Google News RSS headlines — rule-based keyword scoring
     (upgrade/partnership/contract/FDA/beats/raises vs downgrade/miss/probe).
  3. Analyst revisions: yfinance recommendations — count up- vs down-revisions
     in last 30 days.

Polygon upgrade (when POLYGON_API_KEY set): swap news to Polygon's news API
(already sentiment-scored) and earnings to Polygon financials. Until then,
the free stack below works on every ticker.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, List
from urllib.parse import quote

import httpx
import yfinance as yf

from .providers import FINNHUB_API_KEY, has_polygon, POLYGON_API_KEY

log = logging.getLogger("sepa.catalyst")

BULLISH = {
    "beats", "beat", "raises", "raised", "upgrade", "upgraded", "outperform",
    "partnership", "contract", "approved", "approval", "acquires", "acquisition",
    "launch", "breakthrough", "record", "surges", "soars", "tops", "strong",
    "guidance raised",
}
BEARISH = {
    "miss", "missed", "downgrade", "downgraded", "underperform", "probe",
    "investigation", "lawsuit", "recall", "halt", "plunge", "tumbles", "cuts",
    "guidance cut", "delisted", "bankruptcy", "fraud",
}


def _score_headline(text: str) -> int:
    t = text.lower()
    score = 0
    for w in BULLISH:
        if w in t:
            score += 1
    for w in BEARISH:
        if w in t:
            score -= 1
    return score


async def _fetch_google_news(symbol: str, company_hint: str = "") -> List[dict]:
    """Fetch ticker-relevant news headlines.

    Two-step strategy to avoid the USD-as-currency / ETH-as-Ethereum /
    AI-as-buzzword false-positive trap:

      1. Resolve the company's full name (via the company_names cache).
         Search Google News by the *company name*, not the bare ticker.
         "Nvidia Corporation" returns Nvidia-relevant articles;
         "NVDA stock" returns articles about every other ticker too because
         NVDA prices are quoted in dollars, the dollar is "USD", etc.

      2. Post-filter the returned items: require the title to contain either
         the company name (or its first word) OR a ticker cashtag ($NVDA).
         Drops macro/currency/cross-ticker pollution.

    No API key required.
    """
    import re
    import xml.etree.ElementTree as ET
    from . import company_names

    sym = symbol.upper()
    name = company_hint or company_names.name_for(sym) or ""
    # First word of the company name (drops "Inc", "Corporation", "Holdings"
    # etc. for laxer matching). E.g. "NVIDIA Corporation" → "NVIDIA".
    name_first = name.split()[0] if name else ""

    # Search query: prefer the company name. Fall back to `$TICKER stock` only
    # when we have no name. Quoted phrase + the word "stock" anchors the news
    # away from unrelated mentions of the same string.
    if name:
        q = f'"{name}" stock'
    else:
        q = f'${sym} stock'

    url = f"https://news.google.com/rss/search?q={quote(q)}&hl=en-US&gl=US&ceid=US:en"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.text)
    except Exception as exc:
        log.warning("google news fetch failed for %s: %s", symbol, exc)
        return []

    # Build a relevance regex: company name OR first-word OR cashtag.
    relevance_terms: List[str] = []
    if name:
        relevance_terms.append(re.escape(name))
    if name_first and name_first.lower() != name.lower():
        relevance_terms.append(re.escape(name_first))
    relevance_terms.append(re.escape(f"${sym}"))
    # Cashtag-less ticker — only for tickers that aren't common English/acronym
    # collisions (4+ chars typically safe; 2-3 char tickers too risky).
    if len(sym) >= 4:
        relevance_terms.append(rf"\b{re.escape(sym)}\b")
    relevance_re = re.compile("|".join(relevance_terms), re.IGNORECASE)

    items: List[dict] = []
    for it in root.findall(".//item")[:30]:  # fetch more, filter down
        title = (it.findtext("title") or "").strip()
        if not title:
            continue
        if not relevance_re.search(title):
            continue  # dropped: title doesn't mention this company
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        items.append({"title": title, "link": link, "pub": pub,
                      "score": _score_headline(title)})
        if len(items) >= 15:
            break
    return items


async def _fetch_finnhub_earnings(symbol: str) -> Optional[dict]:
    if not FINNHUB_API_KEY:
        return None
    from_d = datetime.utcnow().date().isoformat()
    to_d = (datetime.utcnow().date() + timedelta(days=30)).isoformat()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://finnhub.io/api/v1/calendar/earnings",
                params={"from": from_d, "to": to_d, "symbol": symbol,
                        "token": FINNHUB_API_KEY},
            )
        if resp.status_code != 200:
            return None
        data = resp.json().get("earningsCalendar") or []
        if not data:
            return None
        ev = data[0]
        return {
            "date": ev.get("date"),
            "hour": ev.get("hour"),  # bmo/amc
            "eps_estimate": ev.get("epsEstimate"),
            "revenue_estimate": ev.get("revenueEstimate"),
        }
    except Exception as exc:
        log.warning("finnhub earnings fetch failed for %s: %s", symbol, exc)
        return None


def _fetch_yfinance_extras(symbol: str) -> dict:
    """Synchronous — run in a thread via asyncio."""
    out: dict = {"last_surprise_pct": None, "up_revisions_30d": 0,
                 "down_revisions_30d": 0}
    try:
        t = yf.Ticker(symbol)
        try:
            earns = t.earnings_history  # new yfinance
        except Exception:
            earns = None
        if earns is not None and hasattr(earns, "empty") and not earns.empty:
            row = earns.iloc[-1]
            if "surprisePercent" in earns.columns and row["surprisePercent"] is not None:
                out["last_surprise_pct"] = float(row["surprisePercent"])

        recs = None
        try:
            recs = t.recommendations
        except Exception:
            pass
        if recs is not None and hasattr(recs, "empty") and not recs.empty:
            cutoff = datetime.utcnow() - timedelta(days=30)
            recent = recs[recs.index >= cutoff] if hasattr(recs, "index") else recs
            if "To Grade" in getattr(recent, "columns", []):
                ups = bears = 0
                for _, r in recent.iterrows():
                    tg = str(r.get("To Grade", "")).lower()
                    if any(k in tg for k in ["buy", "outperform", "overweight", "strong"]):
                        ups += 1
                    elif any(k in tg for k in ["sell", "underperform", "underweight"]):
                        bears += 1
                out["up_revisions_30d"] = ups
                out["down_revisions_30d"] = bears
    except Exception as exc:
        log.debug("yfinance extras failed for %s: %s", symbol, exc)
    return out


async def catalyst_for(symbol: str) -> dict:
    news_task = asyncio.create_task(_fetch_google_news(symbol))
    earnings_task = asyncio.create_task(_fetch_finnhub_earnings(symbol))
    extras = await asyncio.to_thread(_fetch_yfinance_extras, symbol)
    news = await news_task
    earnings = await earnings_task

    top_news = sorted(news, key=lambda x: abs(x["score"]), reverse=True)[:5]
    sentiment_score = sum(x["score"] for x in news)

    return {
        "symbol": symbol,
        "earnings_upcoming": earnings,
        "last_earnings_surprise_pct": extras.get("last_surprise_pct"),
        "analyst_up_revisions_30d": extras.get("up_revisions_30d"),
        "analyst_down_revisions_30d": extras.get("down_revisions_30d"),
        "news_sentiment_score": sentiment_score,
        "news_count": len(news),
        "top_news": top_news,
        "provider": "polygon" if has_polygon() else "free_stack",
    }


# ════════════════════════════════════════════════════════════════════════════
# Catalyst SUMMARY — a grounded, plain-English digest of the headlines/signals
# for the detail page (Ajay asked: "summarize the catalyst info", 2026-06-09).
#
# Real-money safety: the LLM is told to use ONLY the provided headlines/signals,
# never invent a fact/number/price, downweight generic "outperforms/underperforms
# on <day>" filler, and never give buy/sell/hold advice. When the local LLM is
# off we fall back to a deterministic heuristic line so the section is never
# empty and never fabricated. Cached per symbol per UTC day in Mongo. Uses the
# LOCAL model by default (free) — it is ONLY called on the single-symbol detail
# path, never in the multi-ticker scan, so cost/latency stay bounded.
# ════════════════════════════════════════════════════════════════════════════
import os  # noqa: E402

_SUMMARY_DB = None


def _summary_db():
    global _SUMMARY_DB
    if _SUMMARY_DB is not None:
        return _SUMMARY_DB
    try:
        from pymongo import MongoClient
        client = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"),
                             serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        _SUMMARY_DB = client[os.getenv("MONGO_DB", "cheetah")]
        _SUMMARY_DB.catalyst_summaries.create_index("symbol", unique=True)
        return _SUMMARY_DB
    except Exception as exc:
        log.warning("catalyst summary: Mongo unavailable: %s", exc)
        return None


def _heuristic_summary(cat: dict) -> str:
    """Deterministic, data-grounded one-liner — used when the LLM is disabled.
    Says only what the counts/signals actually show; invents nothing."""
    news = cat.get("top_news") or []
    n = cat.get("news_count") or len(news)
    sent = cat.get("news_sentiment_score") or 0
    up = cat.get("analyst_up_revisions_30d") or 0
    dn = cat.get("analyst_down_revisions_30d") or 0
    earn = cat.get("earnings_upcoming")
    if not news and not earn and not (up or dn):
        return "No recent news catalyst found."
    tone = "net-bullish" if sent > 0 else "net-bearish" if sent < 0 else "neutral"
    bits = [f"{n} recent headline{'s' if n != 1 else ''} ({tone} tone)"]
    if up or dn:
        bits.append(f"{up} up / {dn} down analyst revisions (30d)")
    if earn:
        bits.append("earnings upcoming")
    return "; ".join(bits) + "."


def _generate_summary(cat: dict, *, provider: str) -> Optional[str]:
    try:
        import llm
    except Exception:
        return _heuristic_summary(cat)
    if not llm.is_enabled():
        return _heuristic_summary(cat)

    headlines = cat.get("top_news") or []
    if not headlines and not cat.get("earnings_upcoming"):
        return _heuristic_summary(cat)

    lines = []
    for nws in headlines[:6]:
        sc = nws.get("score", 0) or 0
        tag = "+" if sc > 0 else "-" if sc < 0 else "."
        title = (nws.get("title") or "").strip()
        if title:
            lines.append(f"  [{tag}] {title}")

    facts = []
    earn = cat.get("earnings_upcoming")
    if earn:
        facts.append(f"earnings upcoming ({earn.get('date') if isinstance(earn, dict) else earn})")
    sup = cat.get("last_earnings_surprise_pct")
    if sup is not None:
        try:
            facts.append(f"last EPS surprise {float(sup):+.1f}%")
        except Exception:
            pass
    up = cat.get("analyst_up_revisions_30d") or 0
    dn = cat.get("analyst_down_revisions_30d") or 0
    facts.append(f"analyst revisions 30d: {up} up / {dn} down")

    prompt = (
        f"Ticker {cat.get('symbol')}. Recent news headlines "
        f"(+ bullish, - bearish, . neutral):\n"
        + ("\n".join(lines) if lines else "  (no headlines)")
        + "\n\nOther signals: " + "; ".join(facts)
        + "\n\nWrite a 1-2 sentence (<=40 words) plain-English summary of the CATALYST "
          "picture: what, if anything, is actually driving this stock right now. "
          "Use ONLY the headlines and signals above — do NOT invent any fact, number, "
          "or price that is not shown. Explicitly downweight generic "
          "'outperforms/underperforms competitors on <day>' filler headlines. "
          "If there is no real catalyst, say so plainly. Do NOT give buy/sell/hold "
          "advice or a price target."
    )
    system = (
        "You summarize stock-news catalysts for an experienced trader. Be terse, "
        "factual, and grounded strictly in the provided text. Never fabricate a fact "
        "or number. Never give investment advice."
    )
    try:
        resp = llm.chat(prompt, system=system, max_tokens=120,
                        temperature=0.1, timeout=20, provider=provider)
    except Exception as exc:
        log.warning("catalyst summary llm error %s: %s", cat.get("symbol"), exc)
        return _heuristic_summary(cat)
    if not resp.get("ok"):
        return _heuristic_summary(cat)
    text = (resp.get("text") or "").strip().strip('"').strip()
    return text or _heuristic_summary(cat)


def summarize_catalyst(cat: dict, *, provider: str = "local", force: bool = False) -> Optional[str]:
    """Grounded plain-English catalyst summary for the detail page.

    Cached per symbol per UTC day in Mongo (regenerated at most once/day per
    name). Local LLM by default (free); deterministic heuristic fallback when the
    LLM is off. Never invents facts and never gives advice (prompt-enforced).
    Returns None only if there is no symbol.
    """
    sym = (cat or {}).get("symbol")
    if not sym:
        return None
    import datetime as _dt
    ymd = _dt.datetime.utcnow().strftime("%Y-%m-%d")
    db = _summary_db()
    if db is not None and not force:
        try:
            doc = db.catalyst_summaries.find_one({"symbol": sym})
            if doc and doc.get("ymd") == ymd and doc.get("summary"):
                return doc["summary"]
        except Exception:
            pass
    summary = _generate_summary(cat, provider=provider)
    if summary and db is not None:
        try:
            db.catalyst_summaries.update_one(
                {"symbol": sym},
                {"$set": {"symbol": sym, "ymd": ymd, "summary": summary,
                          "is_llm": llm_used(cat)}},
                upsert=True,
            )
        except Exception:
            pass
    return summary


def llm_used(cat: dict) -> bool:
    """Best-effort flag: was the LLM available for this summary? (For the UI to
    label heuristic vs AI.)"""
    try:
        import llm
        return bool(llm.is_enabled())
    except Exception:
        return False
