"""Evidence signal — hard data backing (or refuting) the chatter.

For a ticker we look for:
  1. Recent news from Massive (last 48h) — categorized by tag
  2. SEC filings (last 7 days) via EDGAR — 8-K (material event), 13D/G
     (activist), 10-Q/K (financials), S-1 (offering = often dilutive)
  3. Earnings event proximity (within ±2 days)
  4. Insider trading flags (Form 4 filings — buys are bullish)

Every evidence item is tagged with a `weight` (how convincing it is) and
a `tone` (bullish / bearish / neutral / dilutive). The scorer uses these
to compute the evidence_score.

All sources are FREE — Massive is already paid for, SEC EDGAR is free.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import requests

log = logging.getLogger("catalysts.evidence")

# Massive news categories that we treat as strong evidence
_BULLISH_NEWS_KEYWORDS = (
    "fda approval", "approves", "approved by", "phase 3", "topline", "phase 2 met",
    "merger", "acquisition", "buyout", "acquire", "to be acquired",
    "earnings beat", "raises guidance", "raised guidance", "exceeds",
    "contract", "awarded", "deal with", "partnership with",
    "insider buys", "10b5-1", "buyback",
    "reverse split", "uplisting", "listed on",
)
_BEARISH_NEWS_KEYWORDS = (
    "fda rejects", "complete response letter", "crl", "phase 3 misses", "fails",
    "earnings miss", "lowered guidance", "cut guidance", "warning",
    "lawsuit", "fraud", "investigation", "delisted", "going concern",
    "offering", "dilution", "secondary offering", "at-the-market",
    "downgrade",
)


# --- Massive news -------------------------------------------------------

def _fetch_massive_news(ticker: str, hours: int = 48) -> list[dict]:
    """Pull recent news from Massive. Same source we already use elsewhere."""
    import os
    key = os.getenv("MASSIVE_API_KEY")
    if not key:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    url = "https://api.massive.com/v2/reference/news"
    try:
        r = requests.get(url, params={
            "ticker": ticker,
            "limit": 25,
            "order": "desc",
            "apiKey": key,
        }, timeout=8)
        if r.status_code != 200:
            return []
        body = r.json() or {}
        out = []
        for it in body.get("results", []):
            published = it.get("published_utc")
            if published:
                try:
                    pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                    if pub_dt < cutoff:
                        continue
                except Exception:
                    pass
            title = (it.get("title") or "").strip()
            desc = (it.get("description") or "").strip()
            out.append({
                "title": title,
                "url": it.get("article_url") or it.get("amp_url"),
                "publisher": (it.get("publisher") or {}).get("name"),
                "published_utc": published,
                "description": desc[:240],
                "tickers": it.get("tickers") or [],
            })
        return out
    except Exception as exc:
        log.debug("massive news failed for %s: %s", ticker, exc)
        return []


def _tag_news_tone(title: str, desc: str) -> str:
    """Classify a headline as bullish / bearish / neutral via keyword match."""
    text = (title + " " + desc).lower()
    bull_hits = sum(1 for kw in _BULLISH_NEWS_KEYWORDS if kw in text)
    bear_hits = sum(1 for kw in _BEARISH_NEWS_KEYWORDS if kw in text)
    if bull_hits > bear_hits:
        return "bullish"
    if bear_hits > bull_hits:
        return "bearish"
    return "neutral"


# --- SEC EDGAR ----------------------------------------------------------

# EDGAR ticker → CIK mapping is a single JSON file at
# https://www.sec.gov/files/company_tickers.json — cache once per process.
_CIK_CACHE: dict[str, str] = {}
_CIK_LOADED = False


def _load_cik_map() -> dict[str, str]:
    global _CIK_LOADED
    if _CIK_LOADED and _CIK_CACHE:
        return _CIK_CACHE
    try:
        r = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers={"User-Agent": "Cheetah catalyst scanner ajay@example.com"},
            timeout=10,
        )
        if r.status_code != 200:
            return {}
        body = r.json() or {}
        for v in body.values():
            t = (v.get("ticker") or "").upper()
            cik = str(v.get("cik_str") or "").zfill(10)
            if t and cik:
                _CIK_CACHE[t] = cik
        _CIK_LOADED = True
    except Exception as exc:
        log.warning("failed to load CIK map: %s", exc)
    return _CIK_CACHE


def _fetch_sec_filings(ticker: str, days: int = 7) -> list[dict]:
    """Pull recent SEC filings for a ticker via EDGAR submissions API.

    Returns up to N most-recent filings of types we care about (8-K, 13D/G,
    Form 4, S-1, S-3, etc) within `days`.
    """
    cik = _load_cik_map().get(ticker.upper())
    if not cik:
        return []

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date()

    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    try:
        r = requests.get(
            url,
            headers={"User-Agent": "Cheetah catalyst scanner ajay@example.com"},
            timeout=8,
        )
        if r.status_code != 200:
            return []
        body = r.json() or {}
        recent = (body.get("filings") or {}).get("recent") or {}
        # recent has parallel arrays: form, filingDate, accessionNumber, primaryDocument
        forms = recent.get("form") or []
        dates = recent.get("filingDate") or []
        accs = recent.get("accessionNumber") or []
        docs = recent.get("primaryDocument") or []

        out = []
        for i, form in enumerate(forms):
            if i >= len(dates):
                break
            try:
                fdate = datetime.strptime(dates[i], "%Y-%m-%d").date()
            except Exception:
                continue
            if fdate < cutoff:
                continue
            acc_clean = (accs[i] if i < len(accs) else "").replace("-", "")
            doc = docs[i] if i < len(docs) else ""
            url_doc = (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_clean}/{doc}"
                if acc_clean and doc else None
            )
            out.append({
                "form": form,
                "filing_date": dates[i],
                "url": url_doc,
            })
        return out
    except Exception as exc:
        log.debug("EDGAR fetch failed for %s: %s", ticker, exc)
        return []


def _classify_filing(form: str) -> tuple[str, int]:
    """Map a form type → (tone, weight). Higher weight = stronger signal."""
    f = form.upper()
    if f.startswith("8-K"):
        return ("neutral", 5)        # material event — could be either
    if f in ("13D", "SC 13D"):
        return ("bullish", 7)        # activist or significant shareholder
    if f in ("13G", "SC 13G"):
        return ("bullish", 4)
    if f == "4":
        return ("neutral", 3)        # insider trade — direction needs body parse
    if f in ("S-1", "S-3", "424B5"):
        return ("bearish", 5)        # dilutive offering
    if f.startswith("10-Q") or f.startswith("10-K"):
        return ("neutral", 2)
    if f == "FWP":  # free writing prospectus — often offering
        return ("bearish", 3)
    return ("neutral", 1)


# --- Public combined fetch ----------------------------------------------

def get_evidence(ticker: str) -> dict:
    """Combined evidence snapshot: news + SEC filings, each tagged."""
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_news = ex.submit(_fetch_massive_news, ticker, 48)
        f_sec = ex.submit(_fetch_sec_filings, ticker, 7)
        news = f_news.result() or []
        sec = f_sec.result() or []

    # Tag each news headline
    bullish_news = []
    bearish_news = []
    neutral_news = []
    for n in news:
        tone = _tag_news_tone(n.get("title") or "", n.get("description") or "")
        n = {**n, "tone": tone}
        if tone == "bullish":
            bullish_news.append(n)
        elif tone == "bearish":
            bearish_news.append(n)
        else:
            neutral_news.append(n)

    # Tag each filing
    tagged_filings = []
    for f in sec:
        tone, weight = _classify_filing(f.get("form") or "")
        tagged_filings.append({**f, "tone": tone, "weight": weight})

    return {
        "ticker": ticker.upper(),
        "news": {
            "n_total": len(news),
            "n_bullish": len(bullish_news),
            "n_bearish": len(bearish_news),
            "n_neutral": len(neutral_news),
            "bullish": bullish_news[:5],
            "bearish": bearish_news[:5],
            "neutral": neutral_news[:3],
        },
        "sec_filings": {
            "n_total": len(tagged_filings),
            "items": tagged_filings,
            "has_8k": any(f["form"].startswith("8-K") for f in tagged_filings),
            "has_offering": any(f["form"] in ("S-1", "S-3", "424B5", "FWP") for f in tagged_filings),
            "has_13d": any(f["form"] in ("13D", "SC 13D", "13G", "SC 13G") for f in tagged_filings),
            "has_insider_trade": any(f["form"] == "4" for f in tagged_filings),
        },
    }


def get_evidence_batch(tickers: list[str], max_workers: int = 6) -> dict[str, dict]:
    """Parallel evidence fetch for many tickers."""
    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for r in ex.map(get_evidence, tickers):
            if r:
                out[r["ticker"]] = r
    return out


__all__ = ["get_evidence", "get_evidence_batch"]
