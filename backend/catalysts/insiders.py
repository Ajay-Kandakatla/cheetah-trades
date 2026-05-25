"""Form 4 insider transaction cluster detector.

A SINGLE insider buy is moderately bullish; a CLUSTER (3+ insiders buying
the same stock in 7 days) is one of the highest-quality signals in the
market. It says "people inside the company who actually know what's
happening are putting their own money in, right now."

This module:
  - Pulls Form 4 filings via SEC EDGAR (free, no key)
  - Parses the ownership XML for buy vs sell, count, $ value
  - Aggregates by ticker + 7-day window to detect clusters
  - Exposes a score (0-100) and a list of insiders

We piggy-back on the existing CIK lookup map in `evidence.py` so we don't
re-implement that.

Endpoint surface:
  - get_insider_signal(ticker) → cluster_score + recent buys/sells
  - get_recent_clusters(min_buyers=3, days=7) → list of tickers with active
    insider buying clusters across all of EDGAR's recent filings
"""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from .evidence import _load_cik_map, _fetch_sec_filings

log = logging.getLogger("catalysts.insiders")

_HEADERS = {
    "User-Agent": "Cheetah catalyst scanner ajay@example.com",
    "Accept": "application/json",
}


# --- Form 4 XML parsing -------------------------------------------------

# Form 4 has structured XML with transactions. Key fields:
#   <transactionShares><value>5000</value></transactionShares>
#   <transactionPricePerShare><value>4.25</value></transactionPricePerShare>
#   <transactionAcquiredDisposedCode><value>A or D</value></...>
#   "A" = acquired (buy), "D" = disposed (sell)
# Filer name + relationship inside <reportingOwner>

_RE_SHARES = re.compile(r"<transactionShares>\s*<value>([\d.]+)</value>", re.S)
_RE_PRICE = re.compile(r"<transactionPricePerShare>\s*<value>([\d.]+)</value>", re.S)
_RE_AD = re.compile(r"<transactionAcquiredDisposedCode>\s*<value>([AD])</value>", re.S)
_RE_OWNER_NAME = re.compile(r"<reportingOwner>.*?<rptOwnerName>([^<]+)</rptOwnerName>", re.S)
_RE_IS_DIRECTOR = re.compile(r"<isDirector>([^<]+)</isDirector>", re.S)
_RE_IS_OFFICER = re.compile(r"<isOfficer>([^<]+)</isOfficer>", re.S)
_RE_OFFICER_TITLE = re.compile(r"<officerTitle>([^<]+)</officerTitle>", re.S)
_RE_TRANS_DATE = re.compile(r"<transactionDate>\s*<value>([^<]+)</value>", re.S)


def _parse_form4(xml_text: str) -> Optional[dict]:
    """Extract aggregate buy/sell info from a Form 4 XML body."""
    if not xml_text:
        return None
    # Owner identity
    owner = _RE_OWNER_NAME.search(xml_text)
    title = _RE_OFFICER_TITLE.search(xml_text)
    is_dir = _RE_IS_DIRECTOR.search(xml_text)
    is_off = _RE_IS_OFFICER.search(xml_text)

    # All transactions in this filing — a Form 4 can have multiple lines
    n_buys = 0
    n_sells = 0
    total_buy_shares = 0.0
    total_sell_shares = 0.0
    total_buy_value = 0.0
    total_sell_value = 0.0

    # Iterate parallel matches: AD code aligned with shares + price (best
    # effort — the SEC XML is consistent)
    ad_matches = _RE_AD.findall(xml_text)
    sh_matches = _RE_SHARES.findall(xml_text)
    px_matches = _RE_PRICE.findall(xml_text)

    for i, ad in enumerate(ad_matches):
        sh = float(sh_matches[i]) if i < len(sh_matches) else 0
        px = float(px_matches[i]) if i < len(px_matches) else 0
        val = sh * px
        if ad == "A":
            n_buys += 1
            total_buy_shares += sh
            total_buy_value += val
        elif ad == "D":
            n_sells += 1
            total_sell_shares += sh
            total_sell_value += val

    trans_date = _RE_TRANS_DATE.search(xml_text)

    role = []
    if is_off and "1" in is_off.group(1).lower(): role.append("officer")
    if is_dir and "1" in is_dir.group(1).lower(): role.append("director")
    role_str = "/".join(role) if role else "10%-owner"

    return {
        "owner_name": owner.group(1).strip() if owner else "Unknown",
        "officer_title": title.group(1).strip() if title else None,
        "role": role_str,
        "n_buys": n_buys,
        "n_sells": n_sells,
        "buy_shares": total_buy_shares,
        "sell_shares": total_sell_shares,
        "buy_value": total_buy_value,
        "sell_value": total_sell_value,
        "transaction_date": trans_date.group(1).strip() if trans_date else None,
        "net_value": total_buy_value - total_sell_value,
        "direction": "buy" if total_buy_value > total_sell_value else "sell" if total_sell_value > 0 else "neutral",
    }


def _fetch_form4_xml(filing_url: str) -> Optional[str]:
    """Fetch the XML body of a Form 4 filing.

    EDGAR layout: a filing lives at /Archives/edgar/data/{cik}/{acc}/, and
    inside that directory you'll find:
      - Index page (filename ends with `-index.htm`)
      - The raw ownership XML (filename varies, but always contains
        `<ownershipDocument>` as the root element)
      - An XSLT-rendered version under `xslF345X06/` (this is what the
        primary-document field often points at — wrong file for parsing)

    Strategy:
      1. Try the URL as-is (works if it's already the raw XML).
      2. Strip any /xslF345X06/ subpath.
      3. List the directory index and grab any `.xml` file that contains
         `<ownershipDocument>`.
    """
    if not filing_url:
        return None

    headers = {"User-Agent": _HEADERS["User-Agent"]}
    candidates = [filing_url]

    # If URL has /xslF345X06/ stylesheet path, also try the raw file
    if "/xslF345X06/" in filing_url:
        candidates.append(filing_url.replace("/xslF345X06/", "/"))
    if "/xslF345X05/" in filing_url:
        candidates.append(filing_url.replace("/xslF345X05/", "/"))
    if "/xslF345X02/" in filing_url:
        candidates.append(filing_url.replace("/xslF345X02/", "/"))

    if filing_url.endswith(".htm"):
        candidates.insert(0, filing_url[:-4] + ".xml")

    for url in candidates:
        try:
            r = requests.get(url, headers=headers, timeout=6)
            if r.status_code == 200 and "<ownershipDocument" in r.text:
                return r.text
        except Exception:
            continue

    # Last resort: scrape the directory listing for any .xml file
    if "/Archives/edgar/data/" in filing_url:
        try:
            base = filing_url.rsplit("/", 1)[0]
            # Strip /xslF345X06 if present
            base = re.sub(r"/xslF345X0\d/?$", "", base)
            r = requests.get(base + "/", headers=headers, timeout=6)
            if r.status_code == 200:
                # Find any .xml link in the listing
                for m in re.finditer(r'href="([^"]+\.xml)"', r.text):
                    fname = m.group(1)
                    # Skip XSL files; we want the data XML
                    if "xslF" in fname or fname.startswith("xsl"):
                        continue
                    full = fname if fname.startswith("http") else base + "/" + fname.lstrip("/")
                    try:
                        rr = requests.get(full, headers=headers, timeout=6)
                        if rr.status_code == 200 and "<ownershipDocument" in rr.text:
                            return rr.text
                    except Exception:
                        continue
        except Exception:
            pass

    return None


# --- Per-ticker insider signal ------------------------------------------

def get_insider_signal(ticker: str, days: int = 14) -> dict:
    """Fetch + parse all Form 4 filings for `ticker` in the last `days` days.

    Returns:
      {
        ticker,
        n_buyers, n_sellers,
        net_buy_value_usd,
        cluster_detected,    # ≥3 distinct buyers in last 7 days
        cluster_score,       # 0-100
        recent: [{owner, role, direction, date, shares, value}, ...]
      }
    """
    filings = _fetch_sec_filings(ticker, days=days)
    form4s = [f for f in filings if (f.get("form") or "").strip() == "4"]
    if not form4s:
        return {
            "ticker": ticker.upper(),
            "n_buyers_7d": 0,
            "n_sellers_7d": 0,
            "net_buy_value_usd_7d": 0,
            "cluster_detected": False,
            "cluster_score": 0,
            "recent": [],
        }

    # Cap how many we fetch per ticker (rate-limit gentle)
    form4s = form4s[:15]

    parsed: list[dict] = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        xmls = list(ex.map(lambda f: _fetch_form4_xml(f.get("url")), form4s))
    for f, xml in zip(form4s, xmls):
        p = _parse_form4(xml or "") if xml else None
        if p:
            p["filing_date"] = f.get("filing_date")
            p["filing_url"] = f.get("url")
            parsed.append(p)

    # Cluster window: last 7 days
    now = datetime.now(timezone.utc).date()
    cutoff = now - timedelta(days=7)

    distinct_buyers_7d = set()
    distinct_sellers_7d = set()
    net_value = 0.0
    for p in parsed:
        try:
            fdate = datetime.strptime(p.get("filing_date") or "", "%Y-%m-%d").date()
        except Exception:
            continue
        if fdate >= cutoff:
            if p["direction"] == "buy" and p["buy_value"] > 0:
                distinct_buyers_7d.add(p["owner_name"])
            if p["direction"] == "sell" and p["sell_value"] > 0:
                distinct_sellers_7d.add(p["owner_name"])
            net_value += p["net_value"]

    n_buyers = len(distinct_buyers_7d)
    n_sellers = len(distinct_sellers_7d)
    cluster_detected = n_buyers >= 3

    # Score: weight # of buyers heavily (the cluster signal), then $ size
    score = 0.0
    score += min(50, n_buyers * 18)        # 3 buyers = 54 → cap 50
    if net_value > 100_000: score += 10
    if net_value > 500_000: score += 15
    if net_value > 2_000_000: score += 20
    score -= min(25, n_sellers * 8)        # punish if insiders selling more
    score = max(0.0, min(100.0, score))

    parsed.sort(key=lambda p: p.get("filing_date") or "", reverse=True)
    return {
        "ticker": ticker.upper(),
        "n_buyers_7d": n_buyers,
        "n_sellers_7d": n_sellers,
        "net_buy_value_usd_7d": int(net_value),
        "cluster_detected": cluster_detected,
        "cluster_score": round(score, 1),
        "recent": parsed[:10],
    }


# --- Cross-ticker scan: who has cluster RIGHT NOW -----------------------

# This requires us to walk EDGAR's recent Form 4 filings index, which is
# at https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4
# and parse out tickers. That's expensive and brittle. For v1 we instead
# pre-filter via the existing scanner output (already-moving stocks) and
# add insider signal as enrichment. Cross-EDGAR scanning is a Tier 2
# upgrade later.

__all__ = ["get_insider_signal"]
