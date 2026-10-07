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
    NOT every filer complies: T. Rowe Price Associates still files VALUE in
    THOUSANDS (Q2-2026: 3,241 positions totalling 999,124,702). Holdings are
    stored as filed; flows.normalize_value_units detects the unit per filing.
  - One period can carry an original + amendments: canonical_filings picks
    ONE portfolio per (cik, period) — RESTATEMENT replaces, NEW HOLDINGS
    merges (see canonical_period).
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

_HOLDINGS_FORMS = ("13F-HR", "13F-HR/A")
_NOTICE_FORMS = ("13F-NT", "13F-NT/A")   # "holdings reported by another manager"


def filing_index(cik: int, max_n: int = 6) -> dict:
    """EVERY 13F-HR and 13F-HR/A filing for the fund's newest `max_n` report
    periods (newest period first; oldest-filed first within a period), plus
    the periods covered only by a 13F-NT notice.

    2026-10-06: this used to keep only the LAST-FILED doc per period, so a
    NEW HOLDINGS amendment (JANA's Q1-2026 /A: one position, $61.5M) became
    the fund's whole Q1 portfolio. Picking the canonical filing per period
    needs each amendment's TYPE, which lives on the cover page — that is
    `canonical_filings`' job, not this list's.
    """
    d = _get(_BASE_SUBMISSIONS.format(cik=int(cik))).json()
    r = d.get("filings", {}).get("recent", {})
    rows, notice = [], set()
    for form, filed, acc, period in zip(
        r.get("form", []), r.get("filingDate", []),
        r.get("accessionNumber", []), r.get("reportDate", []),
    ):
        if not period:
            continue
        if form in _HOLDINGS_FORMS:
            rows.append({"form": form, "filed": filed,
                         "accession": acc, "period": period})
        elif form in _NOTICE_FORMS:
            notice.add(period)
    periods = sorted({row["period"] for row in rows}, reverse=True)[:max_n]
    keep = set(periods)
    out = sorted((row for row in rows if row["period"] in keep),
                 key=lambda x: x["filed"])
    out.sort(key=lambda x: x["period"], reverse=True)  # stable: filed order kept
    newest = periods[0] if periods else ""
    # Only a notice NEWER than the last holdings filing explains a gap.
    return {"filings": out,
            "notice_periods": sorted((p for p in notice if p > newest),
                                     reverse=True)}


def recent_13f_filings(cik: int, max_n: int = 6) -> List[dict]:
    """All 13F-HR / 13F-HR/A filings for the newest `max_n` periods — see
    `filing_index`. Resolve them to ONE portfolio per period with
    `canonical_filings` after fetching their holdings."""
    return filing_index(cik, max_n)["filings"]


# --- Cover page: which KIND of amendment ------------------------------------

AMEND_RESTATEMENT = "RESTATEMENT"
AMEND_NEW_HOLDINGS = "NEW HOLDINGS"
# Stored when the cover page WAS read and carries neither tag (or the filing
# has no primary_doc): without it the daily refresh re-fetched index.json +
# primary_doc for that /A forever. Treated as unknown by canonical_period.
AMEND_UNKNOWN = "UNKNOWN"


def _parse_cover(raw_xml: str) -> Optional[str]:
    """The cover page's amendmentType ('RESTATEMENT' / 'NEW HOLDINGS'), or
    None when the page carries neither (an original, or an unreadable page).
    Namespace-agnostic: filers differ on prefixes."""
    m = re.search(r"<(?:\w+:)?amendmentType>\s*([^<]*?)\s*</", raw_xml or "")
    if not m:
        return None
    t = m.group(1).strip().upper()
    return t if t in (AMEND_RESTATEMENT, AMEND_NEW_HOLDINGS) else None


def _fetch_amendment_type(cik: int, accession: str) -> str:
    """The amendment's type after a SUCCESSFUL read: RESTATEMENT, NEW
    HOLDINGS, or AMEND_UNKNOWN when nothing on file says which. A failed
    fetch raises (the caller stores nothing, so the next refresh retries)."""
    acc_nodash = accession.replace("-", "")
    base = _BASE_ARCHIVES.format(cik=int(cik), acc_nodash=acc_nodash)
    d = json.loads(_get(base + "/index.json").text, strict=False)
    items = [it.get("name", "") for it in d.get("directory", {}).get("item", [])]
    for n in items:
        if n.lower().endswith(".xml") and "primary_doc" in n.lower():
            return (_parse_cover(_get(base + "/" + n,
                                      accept="application/xml").text)
                    or AMEND_UNKNOWN)
    return AMEND_UNKNOWN


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


def _is_amendment(doc: dict) -> bool:
    return (doc.get("form") or "").upper().endswith("/A")


def fetch_holdings(cik: int, filing: dict) -> Optional[dict]:
    """Parsed holdings for one filing — Mongo-cached forever (immutable).

    Returns {cik, period, filed, accession, form, amendment_type, holdings,
    n_positions, n_option_rows_excluded, total_value} or None on fetch/parse
    failure. `amendment_type` is read off the cover page for 13F-HR/A
    filings (None for originals; AMEND_UNKNOWN when the page was read but
    names no type — stored, never re-fetched; when the read FAILED the key
    is left OFF the cache so the next refresh retries). Cached /A docs from
    before 2026-10-06 lack it and are backfilled here.
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
                if _is_amendment(doc) and doc.get("amendment_type") is None:
                    _backfill_amendment_type(coll, cik, doc)
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
    if _is_amendment(doc):
        try:
            atype = _fetch_amendment_type(cik, accession)
        except Exception as exc:
            log.warning("13F cover read failed %s: %s", doc_id, exc)
            atype = None
        if atype:
            doc["amendment_type"] = atype
    else:
        doc["amendment_type"] = None
    if coll is not None:
        try:
            coll.replace_one({"_id": doc_id},
                             {**doc, "fetched_at": datetime.now(timezone.utc)},
                             upsert=True)
        except Exception as exc:
            log.warning("filing cache write failed %s: %s", doc_id, exc)
    return doc


def _backfill_amendment_type(coll, cik: int, doc: dict) -> None:
    try:
        atype = _fetch_amendment_type(cik, doc["accession"])
    except Exception as exc:
        log.warning("13F cover read failed %s: %s", doc.get("_id"), exc)
        return
    if not atype:
        return
    doc["amendment_type"] = atype
    try:
        coll.update_one({"_id": doc["_id"]}, {"$set": {"amendment_type": atype}})
    except Exception as exc:
        log.warning("amendment_type backfill write failed %s: %s",
                    doc.get("_id"), exc)


# --- One canonical portfolio per (cik, period) ------------------------------

def _merge_holdings(base: List[dict], extra: List[dict]) -> List[dict]:
    """NEW HOLDINGS amendment rows added onto the original's, summed per
    CUSIP (the amendment reports positions the original left out)."""
    by = {h["cusip"]: dict(h) for h in base}
    for h in extra:
        slot = by.get(h["cusip"])
        if slot is None:
            by[h["cusip"]] = dict(h)
        else:
            slot["value"] = (slot.get("value") or 0) + (h.get("value") or 0)
            slot["shares"] = (slot.get("shares") or 0) + (h.get("shares") or 0)
    return sorted(by.values(), key=lambda h: -(h.get("value") or 0))


def canonical_period(docs: List[dict]) -> Optional[dict]:
    """ONE portfolio for one (cik, period) out of the original + amendments.

      - RESTATEMENT  → replaces everything filed before it for the period.
      - NEW HOLDINGS → MERGED into the portfolio it amends; never the whole
                       portfolio (JANA Q1-2026 /A = 1 position).
      - amendment of UNKNOWN type (cover page not read yet, or read and
        untagged = AMEND_UNKNOWN) → ignored while
        a complete portfolio exists (recorded in `amendments_unresolved`);
        with nothing to stand on, the period has NO canonical filing — a
        partial book diffed as a whole one invents exits.
      - a NEW HOLDINGS amendment with no original cached → None, same reason.
    """
    if not docs:
        return None
    ordered = sorted(docs, key=lambda d: (d.get("filed") or "",
                                          1 if _is_amendment(d) else 0))
    cur: Optional[dict] = None
    applied, unresolved = [], []
    for d in ordered:
        if not _is_amendment(d):
            cur = dict(d)
            applied, unresolved = [], []
            continue
        atype = d.get("amendment_type")
        if atype == AMEND_RESTATEMENT:
            cur = dict(d)
            applied, unresolved = [d.get("accession")], []
        elif atype == AMEND_NEW_HOLDINGS and cur is not None:
            merged = _merge_holdings(cur.get("holdings") or [],
                                     d.get("holdings") or [])
            cur = dict(cur, holdings=merged, n_positions=len(merged),
                       total_value=sum(h.get("value") or 0 for h in merged),
                       n_option_rows_excluded=(
                           (cur.get("n_option_rows_excluded") or 0)
                           + (d.get("n_option_rows_excluded") or 0)))
            applied.append(d.get("accession"))
        else:
            unresolved.append(d.get("accession"))
    if cur is None:
        log.info("no canonical 13F for cik=%s period=%s (unresolved "
                 "amendments %s)", docs[0].get("cik"),
                 docs[0].get("period"), unresolved)
        return None
    cur["amendments_applied"] = applied
    cur["amendments_unresolved"] = unresolved
    return cur


def canonical_filings(docs: List[dict]) -> List[dict]:
    """Group raw filing docs by period → one canonical doc each, newest
    period first. Periods without a canonical portfolio are dropped."""
    by_period: dict = {}
    for d in docs:
        by_period.setdefault(d.get("period", ""), []).append(d)
    out = []
    for period in sorted(by_period, reverse=True):
        c = canonical_period(by_period[period])
        if c is not None:
            out.append(c)
    return out


def cached_filings(cik: int, raw: bool = False) -> List[dict]:
    """Already-fetched filings for a fund, newest period first. No network.

    Default: ONE canonical portfolio per period (`canonical_filings`). Until
    2026-10-06 this returned every cached doc, so Citadel's Q2-2026 original
    and its Q2-2026 RESTATEMENT sat side by side and `[:2]` diffed Q2 vs Q2.
    `raw=True` returns the docs as stored.
    """
    coll = _coll()
    if coll is None:
        return []
    try:
        docs = list(coll.find({"cik": int(cik)}))
    except Exception as exc:
        log.warning("cached_filings failed for %s: %s", cik, exc)
        return []
    if raw:
        return sorted(docs, key=lambda d: d.get("period", ""), reverse=True)
    return canonical_filings(docs)
