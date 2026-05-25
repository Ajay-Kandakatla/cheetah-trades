"""Forward catalyst calendar — earnings + FDA + biotech readouts + lockup
expirations for the next 30 days.

The whole "Catalysts NOW" tab is reactive — it tells you what's already
moving. This module is PROACTIVE — it tells you what's about to move so
you can pre-position.

Sources (free):
  - yfinance Ticker.calendar  → next earnings date per ticker
  - FDA: ClinicalTrials.gov  → upcoming Phase 3 readouts
  - SEC: 13G/D + S-1 lockup dates (not v1 — would need parser)
  - Macro: Fed dates, CPI release calendar (hardcoded — they don't change)

Output: a unified timeline of {date, ticker, type, description, source}.

We cache 6h since these dates don't change quickly. Endpoint:
  GET /catalysts/calendar?days=30
"""
from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

log = logging.getLogger("catalysts.calendar")


# --- Mongo cache --------------------------------------------------------

_CACHE_TTL_SEC = 6 * 60 * 60


def _cache_coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        return client[db]["catalyst_calendar_cache"]
    except Exception as exc:
        log.warning("calendar cache mongo unavailable: %s", exc)
        return None


def _cache_get() -> Optional[dict]:
    coll = _cache_coll()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"_id": "calendar_latest"})
        if not doc:
            return None
        ts = doc.get("cached_at")
        if not isinstance(ts, datetime):
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        if age > _CACHE_TTL_SEC:
            return None
        payload = doc.get("payload")
        if isinstance(payload, dict):
            payload["cached"] = True
            payload["cache_age_sec"] = round(age)
            return payload
    except Exception as exc:
        log.warning("calendar cache get failed: %s", exc)
    return None


def _cache_put(payload: dict):
    coll = _cache_coll()
    if coll is None:
        return
    try:
        coll.update_one(
            {"_id": "calendar_latest"},
            {"$set": {"cached_at": datetime.now(timezone.utc), "payload": payload}},
            upsert=True,
        )
    except Exception as exc:
        log.warning("calendar cache put failed: %s", exc)


# --- Earnings via yfinance ---------------------------------------------

def _next_earnings(ticker: str) -> Optional[dict]:
    """Pull next earnings date from yfinance Ticker.calendar."""
    try:
        import yfinance as yf
        tk = yf.Ticker(ticker)
        cal = tk.calendar
        if not cal:
            return None
        # cal returns dict-like object; key varies by yfinance version
        edate = None
        for key in ("Earnings Date", "earningsDate", "earnings_date"):
            if isinstance(cal, dict) and key in cal:
                v = cal[key]
                if isinstance(v, list) and v: edate = v[0]
                else: edate = v
                break
        if not edate:
            return None
        if hasattr(edate, "isoformat"):
            edate_str = edate.isoformat()[:10]
        else:
            edate_str = str(edate)[:10]
        return {"ticker": ticker.upper(), "date": edate_str}
    except Exception as exc:
        log.debug("earnings fetch failed for %s: %s", ticker, exc)
        return None


# --- ClinicalTrials.gov: phase 3 readouts coming up ---------------------

def _fetch_clinical_trials_readouts(days: int = 30) -> list[dict]:
    """Pull Phase 3 trials with primary completion in next `days`.

    The v2 API: https://clinicaltrials.gov/api/v2/studies?...
    We filter by:
      - Phase 3 or 4
      - Primary completion within window
      - Industry sponsor (not gov / academic) — public-company readouts
    """
    cutoff = (datetime.now(timezone.utc) + timedelta(days=days)).date().isoformat()
    today = datetime.now(timezone.utc).date().isoformat()
    url = "https://clinicaltrials.gov/api/v2/studies"
    try:
        r = requests.get(url, params={
            "query.cond": "",
            "filter.advanced": (
                f"AREA[PrimaryCompletionDate]RANGE[{today},{cutoff}] "
                f"AND AREA[Phase](PHASE3 OR PHASE4) "
                f"AND AREA[StudySponsorOrganizationType]INDUSTRY"
            ),
            "fields": "NCTId,BriefTitle,LeadSponsorName,Phase,PrimaryCompletionDate,Condition",
            "pageSize": 100,
        }, timeout=15)
        if r.status_code != 200:
            log.warning("clinicaltrials HTTP %s: %s", r.status_code, r.text[:200])
            return []
        body = r.json() or {}
        out = []
        for s in body.get("studies", []):
            proto = (s.get("protocolSection") or {})
            id_mod = proto.get("identificationModule") or {}
            sponsor_mod = proto.get("sponsorCollaboratorsModule") or {}
            status_mod = proto.get("statusModule") or {}
            cond_mod = proto.get("conditionsModule") or {}
            design_mod = proto.get("designModule") or {}

            sponsor = ((sponsor_mod.get("leadSponsor") or {}).get("name") or "").strip()
            phase_list = (design_mod.get("phases") or [])
            phase = "/".join(phase_list) if phase_list else "?"
            pri_date = ((status_mod.get("primaryCompletionDateStruct") or {}).get("date") or "")

            out.append({
                "type": "fda_readout",
                "date": pri_date[:10] if pri_date else None,
                "title": id_mod.get("briefTitle"),
                "sponsor": sponsor,
                "phase": phase,
                "conditions": cond_mod.get("conditions") or [],
                "nct_id": id_mod.get("nctId"),
                "url": f"https://clinicaltrials.gov/study/{id_mod.get('nctId')}" if id_mod.get("nctId") else None,
            })
        return out
    except Exception as exc:
        log.warning("clinicaltrials fetch failed: %s", exc)
        return []


# --- Macro events (hardcoded — Fed + key prints) ------------------------

def _macro_events(days: int = 30) -> list[dict]:
    """Hardcoded macro calendar for the rolling window.

    Real production this would scrape FRED or BEA, but for v1 a static
    list keeps things simple. Update once a quarter.
    """
    today = datetime.now(timezone.utc).date()
    cutoff = today + timedelta(days=days)

    # Known dates (update as needed). Treat any past date as filtered out.
    raw = [
        # FOMC meetings 2025/2026 (publicly announced)
        ("2026-05-13", "fomc", "Fed Funds Decision (FOMC)", "huge — affects whole market"),
        ("2026-06-17", "fomc", "Fed Funds Decision (FOMC)", "huge — affects whole market"),
        # CPI prints (typical 2nd Tues of month)
        ("2026-05-13", "cpi", "April CPI release", "macro print — risk on/off"),
        ("2026-06-12", "cpi", "May CPI release", "macro print — risk on/off"),
        # Jobs reports (1st Friday)
        ("2026-05-01", "nfp", "April Non-Farm Payrolls", "labor market"),
        ("2026-06-05", "nfp", "May Non-Farm Payrolls", "labor market"),
    ]

    out = []
    for date_str, kind, title, why in raw:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            continue
        if today <= d <= cutoff:
            out.append({
                "type": "macro",
                "subtype": kind,
                "date": date_str,
                "title": title,
                "description": why,
            })
    return out


# --- Public combined fetch ----------------------------------------------

def get_calendar(days: int = 30, *, force: bool = False, tickers: Optional[list[str]] = None) -> dict:
    """Return forward calendar for next `days`.

    Buckets:
      - earnings: per-ticker earnings dates (from supply_demand graph or
                  passed-in tickers)
      - fda: phase 3/4 readouts coming up
      - macro: FOMC, CPI, NFP
    """
    if not force:
        cached = _cache_get()
        if cached and cached.get("days_window") == days:
            return cached

    # Tickers to look up earnings for: graph names + tracked watchlist tickers
    if not tickers:
        try:
            from supply_demand.dependencies import NODES
            tickers = [n["ticker"] for n in NODES]
        except Exception:
            tickers = []

    # 1) Earnings (parallel)
    earnings: list[dict] = []
    if tickers:
        with ThreadPoolExecutor(max_workers=10) as ex:
            for r in ex.map(_next_earnings, tickers):
                if r and r.get("date"):
                    today = datetime.now(timezone.utc).date()
                    cutoff = today + timedelta(days=days)
                    try:
                        d = datetime.strptime(r["date"], "%Y-%m-%d").date()
                        if today <= d <= cutoff:
                            earnings.append({
                                "type": "earnings",
                                "date": r["date"],
                                "ticker": r["ticker"],
                                "title": f"{r['ticker']} earnings",
                            })
                    except Exception:
                        continue
    earnings.sort(key=lambda e: e["date"])

    # 2) FDA / clinical readouts
    fda = _fetch_clinical_trials_readouts(days=days)
    fda.sort(key=lambda e: e.get("date") or "")

    # 3) Macro
    macro = _macro_events(days=days)
    macro.sort(key=lambda e: e["date"])

    # Combined timeline
    timeline = earnings + fda + macro
    timeline.sort(key=lambda e: e.get("date") or "")

    payload = {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "days_window": days,
        "n_earnings": len(earnings),
        "n_fda": len(fda),
        "n_macro": len(macro),
        "n_total": len(timeline),
        "by_type": {
            "earnings": earnings,
            "fda": fda,
            "macro": macro,
        },
        "timeline": timeline,
        "cached": False,
        "cache_age_sec": 0,
    }

    _cache_put(payload)
    return payload


__all__ = ["get_calendar"]
