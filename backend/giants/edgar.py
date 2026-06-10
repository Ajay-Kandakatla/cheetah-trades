"""SEC EDGAR 13F-HR fetcher — a giant fund's FULL quarterly portfolio.

This is the per-FUND inversion of supply_demand/whales.py (which is per-symbol
via yfinance and only sees the top ~15 holders). A 13F-HR information table
lists EVERY long US-equity position the manager held at quarter end, so
diffing two consecutive filings answers the question yfinance never can:
"the fund sold $14.5B of MU — where did that money GO?"

Honest scope:
  - 13F-HR is quarterly with up to a 45-day filing lag. This is a rotation/
    positioning view, NOT real-time flow.
  - Values are reported in FULL DOLLARS at period-end prices (verified live
    against Capital World Q1-2026: MU 42,054,392 sh / $14.2B ≈ $338 — the
    period-end price; yfinance shows the same share count priced at today).
  - Put/call option rows are EXCLUDED from flows (notional ≠ conviction);
    the excluded count is kept on the doc so nothing is silently dropped.
  - Short positions never appear in 13Fs at all.

Filings are immutable, so parsed holdings are cached in Mongo forever
(collection `giants_13f_filings`); a refresh only downloads accessions it
has never seen. Rate limit: SEC asks for <10 req/s + a real User-Agent.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Optional

log = logging.getLogger("giants.edgar")

_USER_AGENT = os.getenv(
    "SEC_USER_AGENT",
    "Cheetah Market App ajay@kandakatla.dev",
)
_BASE_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
_BASE_ARCHIVES = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}"
_SLEEP_BETWEEN_CALLS = 0.15  # ~6 req/s, under SEC's 10/s policy

_INFO_NS = "http://www.sec.gov/edgar/document/thirteenf/informationtable"


def _get(url: str, accept: str = "application/json"):
    import requests
    time.sleep(_SLEEP_BETWEEN_CALLS)
    r = requests.get(url, headers={"User-Agent": _USER_AGENT, "Accept": accept},
                     timeout=60)
    r.raise_for_status()
    return r


# --- Mongo cache (immutable filings) --------------------------------------

def _coll():
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        c = client[db]["giants_13f_filings"]
        c.create_index([("cik", ASCENDING), ("period", ASCENDING)])
        return c
    except Exception as exc:
        log.warning("giants filings mongo unavailable: %s", exc)
        return None


# --- Filing discovery ------------------------------------------------------

def recent_13f_filings(cik: int, max_n: int = 6) -> List[dict]:
    """The fund's most recent 13F-HR filings, one per period, newest first.

    Amendments (13F-HR/A) REPLACE the original for that period — we keep
    whichever was FILED last per report period.
    """
    d = _get(_BASE_SUBMISSIONS.format(cik=int(cik))).json()
    r = d.get("filings", {}).get("recent", {})
    rows = []
    for form, filed, acc, period in zip(
        r.get("form", []), r.get("filingDate", []),
        r.get("accessionNumber", []), r.get("reportDate", []),
    ):
        if form in ("13F-HR", "13F-HR/A") and period:
            rows.append({"form": form, "filed": filed,
                         "accession": acc, "period": period})
    best = {}
    for row in rows:
        cur = best.get(row["period"])
        if cur is None or row["filed"] > cur["filed"]:
            best[row["period"]] = row
    out = sorted(best.values(), key=lambda x: x["period"], reverse=True)
    return out[:max_n]


# --- Information-table parse ------------------------------------------------

def _find_info_table_file(cik: int, accession: str) -> Optional[str]:
    """Locate the information-table XML inside the filing directory."""
    acc_nodash = accession.replace("-", "")
    url = _BASE_ARCHIVES.format(cik=int(cik), acc_nodash=acc_nodash) + "/index.json"
    # EDGAR's index.json sometimes embeds raw control chars — strict=False.
    d = json.loads(_get(url).text, strict=False)
    items = [it.get("name", "") for it in d.get("directory", {}).get("item", [])]
    xmls = [n for n in items if n.lower().endswith(".xml")]
    for n in xmls:  # the conventional name first
        if "infotable" in n.lower() or "information" in n.lower():
            return n
    for n in xmls:  # fallback: any XML that isn't the cover page
        if "primary_doc" not in n.lower():
            return n
    return None


def _parse_info_table(raw_xml: str) -> dict:
    """Parse an info-table XML → holdings aggregated by CUSIP.

    Funds file multiple rows per security (different managers / voting
    discretion) — those are summed. putCall rows are counted and excluded.
    """
    root = ET.fromstring(raw_xml)
    ns = {"n": _INFO_NS}
    rows = root.findall("n:infoTable", ns)
    if not rows:  # some filers omit the default namespace
        ns = {"n": ""}
        rows = root.findall("infoTable")
    agg = {}
    n_options = 0
    for r in rows:
        put_call = (r.findtext("n:putCall", "", ns) or "").strip()
        if put_call:
            n_options += 1
            continue
        cusip = (r.findtext("n:cusip", "", ns) or "").strip().upper()
        name = (r.findtext("n:nameOfIssuer", "", ns) or "").strip()
        try:
            value = int(float(r.findtext("n:value", "0", ns) or 0))
        except (TypeError, ValueError):
            value = 0
        try:
            shares = int(float(
                r.findtext("n:shrsOrPrnAmt/n:sshPrnamt", "0", ns) or 0))
        except (TypeError, ValueError):
            shares = 0
        if not cusip:
            continue
        slot = agg.setdefault(cusip, {"cusip": cusip, "name": name,
                                      "value": 0, "shares": 0})
        slot["value"] += value
        slot["shares"] += shares
    holdings = sorted(agg.values(), key=lambda h: -h["value"])
    return {
        "holdings": holdings,
        "n_positions": len(holdings),
        "n_option_rows_excluded": n_options,
        "total_value": sum(h["value"] for h in holdings),
    }


def fetch_holdings(cik: int, filing: dict) -> Optional[dict]:
    """Parsed holdings for one filing — Mongo-cached forever (immutable).

    Returns {cik, period, filed, accession, holdings, n_positions,
    n_option_rows_excluded, total_value} or None on fetch/parse failure.
    """
    cik = int(cik)
    accession = filing["accession"]
    doc_id = "%d:%s" % (cik, accession)
    coll = _coll()
    if coll is not None:
        try:
            doc = coll.find_one({"_id": doc_id})
            if doc and doc.get("holdings"):
                doc.pop("fetched_at", None)
                return doc
        except Exception as exc:
            log.warning("filing cache read failed %s: %s", doc_id, exc)

    try:
        fname = _find_info_table_file(cik, accession)
        if not fname:
            log.warning("no info table file for %s", doc_id)
            return None
        acc_nodash = accession.replace("-", "")
        url = (_BASE_ARCHIVES.format(cik=cik, acc_nodash=acc_nodash)
               + "/" + fname)
        raw = _get(url, accept="application/xml").text
        parsed = _parse_info_table(raw)
    except Exception as exc:
        log.warning("13F fetch/parse failed %s: %s", doc_id, exc)
        return None

    doc = {
        "_id": doc_id,
        "cik": cik,
        "period": filing["period"],
        "filed": filing["filed"],
        "accession": accession,
        "form": filing.get("form", "13F-HR"),
        **parsed,
    }
    if coll is not None:
        try:
            coll.replace_one({"_id": doc_id},
                             {**doc, "fetched_at": datetime.now(timezone.utc)},
                             upsert=True)
        except Exception as exc:
            log.warning("filing cache write failed %s: %s", doc_id, exc)
    return doc


def cached_filings(cik: int) -> List[dict]:
    """All already-fetched filings for a fund, newest period first. No network."""
    coll = _coll()
    if coll is None:
        return []
    try:
        docs = list(coll.find({"cik": int(cik)}))
        return sorted(docs, key=lambda d: d.get("period", ""), reverse=True)
    except Exception as exc:
        log.warning("cached_filings failed for %s: %s", cik, exc)
        return []
