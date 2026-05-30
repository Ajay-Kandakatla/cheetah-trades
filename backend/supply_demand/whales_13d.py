"""SEC 13D / 13G filings — "whale crossed 5% ownership" tracker.

Why this exists (2026-05-29): the existing whales.py is 13F-based and lags
45 days. 13D/G is the closest free "real-time" institutional signal —
filed within 10 days of crossing 5% ownership of a class of shares.

Data source: SEC EDGAR submissions JSON
(`https://data.sec.gov/submissions/CIK{cik}.json`). Free, no API key, but
rate-limited to ~10 req/sec and requires a real User-Agent (company name +
contact email) per SEC policy.

Scope of v1:
  - Per-ticker list of recent SC 13D / SC 13D/A / SC 13G / SC 13G/A filings
  - Returns filer name, filing date, form type, accession number, and
    a deep link to the primary document on SEC.gov.
  - Does NOT parse % owned from cover page — that's deferred to v2.
    Users can click the deep link for the full cover page on SEC.gov.

Cache: 24h in Mongo (`whales13d_cache` collection). 13D/G filings can
arrive any time so refresh daily via cron.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

log = logging.getLogger("supply_demand.whales_13d")

_CACHE_TTL_SEC = 24 * 60 * 60  # 24 hours
_USER_AGENT = os.getenv(
    "SEC_USER_AGENT",
    "Cheetah Market App ajay@kandakatla.dev",
)

# Forms tracked, in order of "weight" for the SEPA decision lens:
#   - Form 4   — insider trades (officers/directors/10%+ owners), 2-day lag.
#                Most common; fires constantly on liquid names.
#   - Form 144 — insider pre-sale notice (planned restricted-stock sales).
#                Useful "watch for upcoming insider supply" signal.
#   - SC 13D/G + amendments — 5% ownership threshold crossings.
#                Rare but high-signal (activist plays, post-IPO anchors).
#
# Widened 2026-05-29: was 13D/G-only, but SEPA's liquid-name universe
# almost never triggers 13D — ARM had 25 Form 4s + 9 Form 144s but
# zero 13D/G in 6 months. Form 4/144 is the actual real-time-ish
# institutional signal for established names.
_FORMS_TRACKED = (
    "4", "4/A",
    "144",
    "SC 13D", "SC 13D/A",
    "SC 13G", "SC 13G/A",
)

# Buckets used for per-form-type counts in the payload.
def _form_bucket(form: str) -> str | None:
    if form in ("4", "4/A"):
        return "form4"
    if form == "144":
        return "form144"
    if form.startswith("SC 13"):
        return "form13"
    return None


# --- Mongo cache ---------------------------------------------------------

def _cache_coll():
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        c = client[db]["whales13d_cache"]
        c.create_index([("ticker", ASCENDING)], unique=True)
        return c
    except Exception as exc:
        log.warning("whales13d cache mongo unavailable: %s", exc)
        return None


def _cache_get(ticker: str) -> Optional[dict]:
    coll = _cache_coll()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"ticker": ticker.upper()})
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
            payload = dict(payload)
            payload["_cached"] = True
            payload["_cache_age_sec"] = round(age)
            return payload
    except Exception as exc:
        log.warning("whales13d cache get failed for %s: %s", ticker, exc)
    return None


def _cache_put(ticker: str, payload: dict) -> None:
    coll = _cache_coll()
    if coll is None:
        return
    try:
        coll.update_one(
            {"ticker": ticker.upper()},
            {"$set": {"ticker": ticker.upper(),
                      "cached_at": datetime.now(timezone.utc),
                      "payload": payload}},
            upsert=True,
        )
    except Exception as exc:
        log.warning("whales13d cache put failed for %s: %s", ticker, exc)


# --- ticker -> CIK lookup ------------------------------------------------

# In-process cache of the full company_tickers.json. SEC refreshes this
# weekly. Fetched once per process; we never re-fetch unless reload_cik_map()
# is explicitly called. Memory footprint is ~1 MB.
_CIK_MAP: dict[str, str] | None = None


def _fetch_cik_map() -> dict[str, str]:
    """Return {TICKER: CIK_padded_to_10_digits}. Fetches once per process."""
    import requests
    r = requests.get(
        "https://www.sec.gov/files/company_tickers.json",
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
        timeout=15,
    )
    r.raise_for_status()
    raw = r.json()
    out: dict[str, str] = {}
    for _, row in raw.items():
        try:
            ticker = str(row["ticker"]).upper()
            cik = str(row["cik_str"]).zfill(10)
            out[ticker] = cik
        except Exception:
            continue
    return out


def _ticker_to_cik(ticker: str) -> Optional[str]:
    global _CIK_MAP
    if _CIK_MAP is None:
        try:
            _CIK_MAP = _fetch_cik_map()
            log.info("whales13d: cached CIK map with %d tickers", len(_CIK_MAP))
        except Exception as exc:
            log.warning("whales13d: CIK map fetch failed: %s", exc)
            _CIK_MAP = {}
    return _CIK_MAP.get(ticker.upper())


def reload_cik_map() -> int:
    """Force a refresh of the ticker→CIK map. Returns new size."""
    global _CIK_MAP
    _CIK_MAP = _fetch_cik_map()
    return len(_CIK_MAP)


# --- Core fetch ----------------------------------------------------------

def _fetch_recent_filings(cik: str) -> list[dict]:
    """Pull all recent filings for a CIK, return raw row dicts.

    SEC's submissions JSON `filings.recent` is column-oriented — each field
    is a parallel array. Zip them back into row dicts for downstream use.
    """
    import requests
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    r = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=15)
    r.raise_for_status()
    js = r.json()
    recent = (js.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    dates = recent.get("filingDate") or []
    accs = recent.get("accessionNumber") or []
    primary = recent.get("primaryDocument") or []
    primary_desc = recent.get("primaryDocDescription") or []
    rows = []
    n = min(len(forms), len(dates), len(accs))
    for i in range(n):
        rows.append({
            "form": forms[i],
            "filing_date": dates[i],
            "accession_number": accs[i],
            "primary_doc": primary[i] if i < len(primary) else None,
            "primary_doc_desc": primary_desc[i] if i < len(primary_desc) else None,
        })
    return rows


def _accession_to_url(cik: str, accession: str, primary_doc: str | None) -> str:
    """Build a deep link to the filing's primary document on SEC.gov.

    Accession numbers have hyphens (e.g., 0001193125-24-034827) but the
    archive URL strips them. The filing-index URL is what humans want.
    """
    acc_no_dashes = accession.replace("-", "")
    cik_no_pad = cik.lstrip("0") or "0"
    if primary_doc:
        return (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{cik_no_pad}/{acc_no_dashes}/{primary_doc}"
        )
    return (
        f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
        f"&CIK={cik}&type=SC+13&dateb=&owner=include&count=40"
    )


def get_13d(ticker: str, days: int = 120, force: bool = False) -> dict:
    """Return recent SEC filings of interest for SEPA-tier flow signal.

    Tracks Form 4 (insider trades), Form 144 (insider pre-sale notice),
    and SC 13D/G + amendments (5% ownership threshold). Function name
    kept as get_13d() for backwards-compat with the cache + endpoint
    plumbing — the widened form set is the 2026-05-29 pivot.

    Output:
      {
        ticker, cik,
        as_of, window_days,
        filings: [
          {form, filing_date, accession_number, primary_doc_url, ...},
          ...
        ],
        n_filings,           # total across all tracked forms
        n_form4,             # insider Form 4 (+ 4/A)
        n_form144,           # insider Form 144
        n_form13,            # SC 13D/G (+ amendments)
        latest, error?
      }
    """
    t = ticker.upper()
    if not force:
        cached = _cache_get(t)
        if cached:
            return cached

    cik = _ticker_to_cik(t)
    if not cik:
        payload = {
            "ticker": t,
            "cik": None,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "window_days": days,
            "filings": [],
            "n_filings": 0,
            "latest": None,
            "error": f"ticker {t} not found in SEC company_tickers.json",
        }
        _cache_put(t, payload)
        return payload

    try:
        all_rows = _fetch_recent_filings(cik)
    except Exception as exc:
        log.warning("whales13d: filings fetch failed for %s (CIK %s): %s",
                    t, cik, exc)
        payload = {
            "ticker": t,
            "cik": cik,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "window_days": days,
            "filings": [],
            "n_filings": 0,
            "latest": None,
            "error": f"SEC fetch failed: {exc}",
        }
        _cache_put(t, payload)
        return payload

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    keep = []
    n_by_bucket = {"form4": 0, "form144": 0, "form13": 0}
    for row in all_rows:
        if row["form"] not in _FORMS_TRACKED:
            continue
        if row["filing_date"] < cutoff:
            continue
        bucket = _form_bucket(row["form"])
        if bucket:
            n_by_bucket[bucket] += 1
        url = _accession_to_url(cik, row["accession_number"], row.get("primary_doc"))
        keep.append({
            "form": row["form"],
            "filing_date": row["filing_date"],
            "accession_number": row["accession_number"],
            "primary_doc_url": url,
            "primary_doc_desc": row.get("primary_doc_desc"),
            "bucket": bucket,
            # Filer name lives in the cover page — left None for v1.
            # Cover-page parse is the v2 work item.
            "filer_name": None,
            "pct_owned": None,
        })

    # Sort newest-first (also serves as "latest" pointer)
    keep.sort(key=lambda r: r["filing_date"], reverse=True)

    payload = {
        "ticker": t,
        "cik": cik,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "window_days": days,
        "filings": keep,
        "n_filings": len(keep),
        "n_form4":   n_by_bucket["form4"],
        "n_form144": n_by_bucket["form144"],
        "n_form13":  n_by_bucket["form13"],
        "latest": keep[0] if keep else None,
        "source": "SEC EDGAR submissions API",
        "disclaimer": (
            "Form 4 = insider trades (2-day lag). Form 144 = insider "
            "pre-sale notice. SC 13D/G = 5% ownership threshold crossings. "
            "Filer names and trade details are on the cover page of each "
            "linked filing — open the link to verify."
        ),
    }

    _cache_put(t, payload)
    return payload


__all__ = ["get_13d", "reload_cik_map"]
