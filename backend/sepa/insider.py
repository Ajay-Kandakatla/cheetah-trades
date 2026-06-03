"""Insider & institutional activity via SEC EDGAR (free, no key).

Three signals:
  1. Form 4 (insider transactions): recent cluster of BUYS by officers/directors
     is a bullish tell; multiple insiders buying in the same window is stronger.
  2. 13D (activist >5% stake): fresh filing = potential catalyst.
  3. 13G (passive >5%): institutional accumulation.

CIK-SCOPED (fixed 2026-06-03). We resolve the ticker to the issuer's SEC CIK
first, then query EDGAR's full-text search filtered to THAT CIK. The previous
implementation did a free-text phrase search for the ticker string itself
(`q="ST"`), which cross-matched the letters anywhere in any filing — for the
2-letter ticker ST (Sensata, CIK 0001477294) that returned 1,767 unrelated
Form 4s (Apax, TotalEnergies, PennyMac…) instead of Sensata's real 15, and
falsely tripped "cluster insider buying". Scoping to the issuer CIK and
stripping the issuer's own name from each filing's party list fixes both the
counts and the displayed filer names.

SEC requires a User-Agent with contact info — set SEC_USER_AGENT in env or we
default to a generic one.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
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
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

# ── Ticker → issuer CIK map (cached module-level; the file is ~220 KB) ───────
_TICKER_MAP: Optional[dict] = None
_TICKER_MAP_TS: float = 0.0
_TICKER_TTL_SEC = 24 * 3600
_ticker_lock = asyncio.Lock()


async def _ticker_to_cik(symbol: str) -> Optional[str]:
    """Resolve a ticker to its 10-digit zero-padded SEC CIK, or None if the
    ticker isn't in SEC's official map. Cached for a day."""
    global _TICKER_MAP, _TICKER_MAP_TS
    sym = (symbol or "").upper().strip()
    if not sym:
        return None
    now = time.time()
    if _TICKER_MAP is None or (now - _TICKER_MAP_TS) > _TICKER_TTL_SEC:
        async with _ticker_lock:
            # Re-check after acquiring the lock — another coroutine may have
            # just populated it.
            if _TICKER_MAP is None or (time.time() - _TICKER_MAP_TS) > _TICKER_TTL_SEC:
                try:
                    async with httpx.AsyncClient(timeout=15, headers=SEC_HEADERS) as client:
                        resp = await client.get(SEC_TICKERS_URL)
                    resp.raise_for_status()
                    data = resp.json()
                    m: dict[str, str] = {}
                    # company_tickers.json is ranked roughly by size; first
                    # occurrence of a ticker wins (handles rare dupes).
                    for v in data.values():
                        t = str(v.get("ticker", "")).upper().strip()
                        cik = str(v.get("cik_str", "")).strip()
                        if t and cik and t not in m:
                            m[t] = cik.zfill(10)
                    _TICKER_MAP = m
                    _TICKER_MAP_TS = time.time()
                except Exception as exc:
                    log.warning("EDGAR ticker map fetch failed: %s", exc)
                    if _TICKER_MAP is None:
                        return None  # no cached map to fall back on
    return (_TICKER_MAP or {}).get(sym)


def _owner_names(all_names: List[str], issuer_cik: str) -> List[str]:
    """Reporting owners only — drop the issuer's own name. EDGAR embeds the CIK
    in each display string, e.g. "SIEDEL RICHARD W. JR.  (CIK 0001661082)" and
    "Sensata Technologies Holding plc  (CIK 0001477294)"; the issuer is the one
    carrying `issuer_cik`."""
    return [n for n in (all_names or []) if issuer_cik not in n]


async def _fts_search(cik: str, form: str, days: int = 60) -> List[dict]:
    """Full-text search against EDGAR for a form type, scoped to one issuer CIK.

    `display_names` from EDGAR lists every party on the filing — the reporting
    owner(s) AND the issuer. We strip the issuer (the entry whose embedded CIK
    matches `cik`) so callers see only the actual filers.
    """
    start = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    end = datetime.utcnow().strftime("%Y-%m-%d")
    params = {
        "forms": form,
        "ciks": cik,                # scope to the issuer — no free-text match
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
        for h in hits[:40]:
            src = h.get("_source", {})
            adsh = src.get("adsh") or (h.get("_id", "").split(":", 1)[0]) or ""
            all_names = src.get("display_names", []) or []
            # Keep only reporting owners — drop the issuer's own name.
            owners = _owner_names(all_names, cik)
            owner_ciks = [c for c in (src.get("ciks") or []) if c != cik]
            out.append({
                "form": src.get("form") or form,
                "filed": src.get("file_date"),
                "display_names": owners,
                "cik": owner_ciks[0] if owner_ciks else "",
                "accession": adsh,
                # Link to the issuer's filings of this type on SEC.gov.
                "url": (
                    f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                    f"&CIK={cik}&type={form}&dateb=&owner=include&count=40"
                ),
            })
        return out
    except Exception as exc:
        log.warning("EDGAR FTS %s for CIK %s failed: %s", form, cik, exc)
        return []


def _empty_result(symbol: str, cik: Optional[str], note: str) -> dict:
    return {
        "symbol": symbol,
        "resolved_cik": cik,
        "note": note,
        "form4_count_60d": 0,
        "form4_count_30d": 0,
        "form4_unique_insiders_30d": 0,
        "form4_cluster_buy": False,
        "sc13d_180d": 0,
        "sc13g_180d": 0,
        "has_recent_13d": False,
        "recent_filings": {"form4": [], "13d": [], "13g": []},
    }


async def insider_activity(symbol: str) -> dict:
    sym = (symbol or "").upper().strip()
    cik = await _ticker_to_cik(sym)
    if not cik:
        # Unknown ticker (ADR, recent listing not yet in SEC's map, etc.) —
        # return zeros rather than the old free-text garbage.
        return _empty_result(sym, None, "ticker not found in SEC CIK map")

    # Run the 3 form-type queries in parallel, all scoped to the issuer CIK.
    form4, d13d, d13g = await asyncio.gather(
        _fts_search(cik, "4", days=60),
        _fts_search(cik, "SC 13D", days=180),
        _fts_search(cik, "SC 13G", days=180),
    )

    # Form 4 clustering — unique reporting-owner names in last 30 days. With the
    # issuer stripped, these are now real insiders only.
    cutoff = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
    recent4 = [f for f in form4 if (f.get("filed") or "") >= cutoff]
    unique_filers = len({n for f in recent4 for n in (f.get("display_names") or [])})

    return {
        "symbol": sym,
        "resolved_cik": cik,
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
