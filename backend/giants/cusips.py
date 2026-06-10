"""CUSIP → ticker resolution for 13F information tables.

13Fs identify securities by CUSIP + a free-text issuer name (often abbreviated
beyond recognition: "INTERNATIONAL BUSINESS MACHS", "BANK AMERICA CORP").
Name-matching alone mapped only ~77% of Capital World's portfolio by value in
live testing, so the PRIMARY source is the SEC's own Fails-to-Deliver data
files, which carry an authoritative CUSIP|SYMBOL pair for essentially every
traded US equity (~12.5k CUSIPs per half-month file). Combining the three most
recent files + a normalized-name fallback against SEC company_tickers.json
mapped 98.4%+ by value in the same test.

Whatever still misses stays UNMAPPED and is surfaced by issuer name — never
silently dropped.

The combined map is cached in Mongo (`giants_cusip_map`, single doc) and
rebuilt when older than 30 days.
"""
from __future__ import annotations

import io
import logging
import os
import re
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

log = logging.getLogger("giants.cusips")

_FTD_URL = "https://www.sec.gov/files/data/fails-deliver-data/cnsfails{ym}{half}.zip"
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_REBUILD_AFTER = timedelta(days=30)

# Suffix tokens stripped (repeatedly) from the END of issuer names before
# matching. Conservative: only legal-form / share-class noise.
_SUFFIX_RE = re.compile(
    r"\b(INCORPORATED|INC|CORPORATION|CORP|COMPANY|CO|LIMITED|LTD|PLC|NEW|DEL"
    r"|COM|CL|CLASS|SER|SERIES|ADR|ADS|SPONSORED|SHS|THE|A|B|C)\s*$"
)


def normalize_issuer(s: str) -> str:
    """Uppercase, strip punctuation, then peel suffix tokens off the end."""
    s = re.sub(r"[^A-Z0-9 ]", " ", (s or "").upper())
    prev = None
    while prev != s:
        prev = s
        s = _SUFFIX_RE.sub("", s).strip()
    return re.sub(r"\s+", " ", s).strip()


def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        return client[db]["giants_cusip_map"]
    except Exception as exc:
        log.warning("cusip map mongo unavailable: %s", exc)
        return None


def _recent_ftd_names(today: Optional[datetime] = None):
    """The 6 most recent half-month FTD file stems (newest first). FTD files
    publish ~30 days after the half-month closes, so start one month back."""
    now = today or datetime.now(timezone.utc)
    out = []
    y, m = now.year, now.month
    for _ in range(4):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        out.append(("%04d%02d" % (y, m), "b"))
        out.append(("%04d%02d" % (y, m), "a"))
    return out[:6]


def _fetch_ftd_pairs(ym: str, half: str) -> Dict[str, str]:
    from giants.edgar import _get
    url = _FTD_URL.format(ym=ym, half=half)
    raw = _get(url, accept="application/zip").content
    zf = zipfile.ZipFile(io.BytesIO(raw))
    name = zf.namelist()[0]
    pairs: Dict[str, str] = {}
    for line in zf.read(name).decode("utf-8", "ignore").splitlines():
        p = line.split("|")
        if len(p) >= 3 and len(p[1]) == 9 and p[2].strip():
            pairs[p[1].upper()] = p[2].strip().upper()
    return pairs


def _build_map() -> Tuple[Dict[str, str], Dict[str, str], list]:
    """(cusip→ticker, normalized-name→ticker, sources_used)."""
    cus: Dict[str, str] = {}
    sources = []
    got = 0
    for ym, half in _recent_ftd_names():
        if got >= 3:
            break
        try:
            pairs = _fetch_ftd_pairs(ym, half)
            # older files first into the dict so NEWER files win on conflict
            merged = dict(pairs)
            merged.update(cus)
            cus = merged
            sources.append("ftd:%s%s" % (ym, half))
            got += 1
        except Exception as exc:
            log.info("FTD file %s%s unavailable: %s", ym, half, exc)

    names: Dict[str, str] = {}
    try:
        from giants.edgar import _get
        tk = _get(_TICKERS_URL).json()
        for v in tk.values():
            n = normalize_issuer(v.get("title", ""))
            if n and n not in names:
                names[n] = (v.get("ticker") or "").upper()
        sources.append("company_tickers.json")
    except Exception as exc:
        log.warning("company_tickers fetch failed: %s", exc)
    return cus, names, sources


def get_maps(force: bool = False) -> Tuple[Dict[str, str], Dict[str, str]]:
    """The cached (cusip→ticker, name→ticker) maps, rebuilding if stale."""
    coll = _coll()
    if coll is not None and not force:
        try:
            doc = coll.find_one({"_id": "latest"})
            if doc:
                ts = doc.get("built_at")
                if isinstance(ts, datetime):
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) - ts < _REBUILD_AFTER:
                        return doc.get("cusips", {}), doc.get("names", {})
        except Exception as exc:
            log.warning("cusip map read failed: %s", exc)

    cus, names, sources = _build_map()
    if coll is not None and (cus or names):
        try:
            coll.replace_one(
                {"_id": "latest"},
                {"_id": "latest", "cusips": cus, "names": names,
                 "sources": sources,
                 "built_at": datetime.now(timezone.utc)},
                upsert=True)
        except Exception as exc:
            log.warning("cusip map write failed: %s", exc)
    return cus, names


def resolve(cusip: str, issuer_name: str,
            cus_map: Dict[str, str], name_map: Dict[str, str]) -> Optional[str]:
    """Ticker for a 13F row, or None (caller shows the raw issuer name)."""
    t = cus_map.get((cusip or "").upper())
    if t:
        return t
    return name_map.get(normalize_issuer(issuer_name)) or None
