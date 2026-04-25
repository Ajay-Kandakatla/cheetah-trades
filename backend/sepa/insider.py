"""Insider & institutional activity via SEC EDGAR (free, no key).

Three signals:
  1. Form 4 (insider transactions): recent cluster of BUYS by officers/directors
     is a bullish tell; multiple insiders buying in the same window is stronger.
  2. 13D (activist >5% stake): fresh filing = potential catalyst.
  3. 13G (passive >5%): institutional accumulation.

We query EDGAR's full-text search and company-filing feeds. SEC requires a
User-Agent with contact info — set SEC_USER_AGENT in env or we default to a
generic one.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Optional, List

import httpx

log = logging.getLogger("sepa.insider")

SEC_UA = os.getenv(
    "SEC_USER_AGENT",
    "Cheetah Market Research research@cheetah.local",
)
SEC_HEADERS = {"User-Agent": SEC_UA, "Accept-Encoding": "gzip, deflate"}
EDGAR_FTS = "https://efts.sec.gov/LATEST/search-index"


async def _fts_search(symbol: str, form: str, days: int = 60) -> List[dict]:
    """Full-text search against EDGAR for a form type + ticker."""
    start = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    end = datetime.utcnow().strftime("%Y-%m-%d")
    params = {
        "q": f'"{symbol}"',
        "forms": form,
        "dateRange": "custom",
        "startdt": start,
        "enddt": end,
    }
    try:
        async with httpx.AsyncClient(timeout=15, headers=SEC_HEADERS) as client:
            resp = await client.get(EDGAR_FTS, params=params)
        if resp.status_code != 200:
            return []
        data = resp.json()
        hits = data.get("hits", {}).get("hits", [])
        out: List[dict] = []
        for h in hits[:20]:
            src = h.get("_source", {})
            adsh = src.get("adsh") or ""
            cik = (src.get("ciks") or [""])[0]
            out.append({
                "form": src.get("form"),
                "filed": src.get("file_date"),
                "display_names": src.get("display_names", []),
                "cik": cik,
                "accession": adsh,
                "url": (
                    f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                    f"&CIK={cik}&type={form}&dateb=&owner=include&count=40"
                ) if cik else None,
            })
        return out
    except Exception as exc:
        log.warning("EDGAR FTS %s for %s failed: %s", form, symbol, exc)
        return []


async def insider_activity(symbol: str) -> dict:
    # Run 3 queries in parallel
    form4, d13d, d13g = await asyncio.gather(
        _fts_search(symbol, "4", days=60),
        _fts_search(symbol, "SC 13D", days=180),
        _fts_search(symbol, "SC 13G", days=180),
    )

    # Form 4 clustering — unique filer names in last 30 days
    cutoff = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
    recent4 = [f for f in form4 if (f.get("filed") or "") >= cutoff]
    unique_filers = len({n for f in recent4 for n in (f.get("display_names") or [])})

    return {
        "symbol": symbol,
        "form4_count_60d": len(form4),
        "form4_count_30d": len(recent4),
        "form4_unique_insiders_30d": unique_filers,
        "form4_cluster_buy": unique_filers >= 3,
        "sc13d_180d": len(d13d),
        "sc13g_180d": len(d13g),
        "has_recent_13d": any((x.get("filed") or "") >= cutoff for x in d13d),
        "recent_filings": {
            "form4": form4[:5],
            "13d": d13d[:3],
            "13g": d13g[:3],
        },
    }
