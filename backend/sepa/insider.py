"""Insider & institutional activity via SEC EDGAR (free, no key).

Three signals:
  1. Form 4 (insider transactions): the bullish tell is OFFICERS/DIRECTORS
     making OPEN-MARKET PURCHASES (transaction code P) with their own money —
     a cluster of those is stronger. Grants (A), option exercises (M), gifts
     (G) and tax-withholding (F) are NOT conviction buys and must be excluded.
  2. 13D (activist >5% stake): fresh filing = potential catalyst.
  3. 13G (passive >5%): institutional accumulation.

CIK-SCOPED (fixed 2026-06-03). We resolve the ticker to the issuer's SEC CIK,
query EDGAR full-text filtered to that CIK, and strip the issuer's own name
from each filing's party list. The previous free-text search (`q="ST"`) matched
the ticker letters anywhere and returned 1,767 unrelated Form 4s for ST.

TRANSACTION-AWARE (2026-06-03 phase 2). For each recent Form 4 we fetch the
filing XML and parse:
  - the reporting owner's relationship (officer / director / 10% owner) + title
  - the transaction codes, to tell a real open-market BUY from a sell/grant/tax
So "cluster insider buying" now means ≥2 distinct officers/directors who bought
on the open market in the last 30 days — not just "≥3 filings of any kind".
(That 2-name threshold is a house heuristic, not a Minervini book formula.)

SEC requires a User-Agent with contact info — set SEC_USER_AGENT in env.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import xml.etree.ElementTree as ET
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

# Cluster-buy heuristic: ≥ this many distinct officer/director open-market
# buyers in the 30-day window. Not a book formula — a house threshold.
CLUSTER_BUY_MIN_INSIDERS = 2
# Deep-parse at most this many of the most-recent Form 4s per symbol (caps SEC
# traffic; buys are rare so this comfortably covers the cluster window).
_MAX_FORM4_DEEP = 20

# ── Ticker → issuer CIK map (cached module-level; the file is ~220 KB) ───────
_TICKER_MAP: Optional[dict] = None
_TICKER_MAP_TS: float = 0.0
_TICKER_TTL_SEC = 24 * 3600
_ticker_lock = asyncio.Lock()

# ── Parsed Form 4 cache (accession is immutable → cache aggressively) ────────
_FORM4_CACHE: dict = {}
_FORM4_CACHE_MAX = 5000
# Concurrency limit for SEC XML fetches. Created per-call (in insider_activity)
# so it binds to the running event loop — a module-level Semaphore binds to the
# import-time loop and raises "attached to a different loop" under asyncio.run.
_FORM4_CONCURRENCY = 3

# ── Global EDGAR rate limiter (root-cause fix for the 429 storm, 2026-06-17) ──
# SEC EDGAR allows ~10 requests/second per client; exceed it and it returns
# "429 Too Many Requests". The old code had NESTED unbounded concurrency — the
# scanner's insider_sweep (Semaphore 4 symbols) × each symbol's 3 FTS searches +
# 3 Form-4 XML fetches = 20+ EDGAR GETs landing in the same millisecond, with no
# per-request pacing and no 429 backoff (the retry just re-fired the burst). This
# single chokepoint paces EVERY EDGAR GET — across the scan sweep AND the per-card
# enrichment path — so concurrent callers queue instead of bursting.
EDGAR_MAX_RPS = float(os.getenv("SEC_MAX_RPS", "7") or 7)        # headroom under 10
_EDGAR_MIN_INTERVAL = 1.0 / max(1.0, EDGAR_MAX_RPS)
_EDGAR_MAX_RETRIES = int(os.getenv("SEC_MAX_RETRIES", "4") or 4)
_EDGAR_MAX_BACKOFF = 8.0
# The pacing lock binds to the RUNNING loop — a module-level Lock binds to the
# import-time loop and breaks under asyncio.run / a fresh loop (same reason the
# Form-4 Semaphore is created per-call).
_edgar_lock: Optional[asyncio.Lock] = None
_edgar_lock_loop = None
_edgar_next_ts = 0.0          # monotonic clock of the earliest next-allowed GET


def _get_edgar_lock() -> asyncio.Lock:
    global _edgar_lock, _edgar_lock_loop
    loop = asyncio.get_event_loop()
    if _edgar_lock is None or _edgar_lock_loop is not loop:
        _edgar_lock = asyncio.Lock()
        _edgar_lock_loop = loop
    return _edgar_lock


async def _edgar_pace() -> None:
    """Serialize the 'reserve the next slot' step so concurrent coroutines start
    their EDGAR GETs at least _EDGAR_MIN_INTERVAL apart (a token bucket of 1)."""
    global _edgar_next_ts
    async with _get_edgar_lock():
        now = time.monotonic()
        wait = _edgar_next_ts - now
        if wait > 0:
            await asyncio.sleep(wait)
            now = time.monotonic()
        _edgar_next_ts = max(now, _edgar_next_ts) + _EDGAR_MIN_INTERVAL


async def _edgar_get(url: str, *, params: Optional[dict] = None, timeout: float = 15):
    """Single chokepoint for ALL EDGAR GETs: global rate-pacing + 429/5xx-aware
    backoff (honours Retry-After). Returns the httpx.Response (the 2xx, or the
    last response received), or None if every attempt raised. Concurrent callers
    queue behind _edgar_pace() — they can never burst past EDGAR_MAX_RPS."""
    last = None
    for attempt in range(_EDGAR_MAX_RETRIES + 1):
        await _edgar_pace()
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=SEC_HEADERS) as client:
                resp = await client.get(url, params=params)
        except Exception as exc:
            log.warning("EDGAR GET %s attempt %d errored: %s", url, attempt + 1, exc)
            await asyncio.sleep(min(_EDGAR_MAX_BACKOFF, 0.5 * (2 ** attempt)))
            continue
        last = resp
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            ra = resp.headers.get("Retry-After")
            try:
                backoff = float(ra) if ra else 0.0
            except (TypeError, ValueError):
                backoff = 0.0
            if backoff <= 0:
                backoff = min(_EDGAR_MAX_BACKOFF, 1.0 * (2 ** attempt))
            log.info("EDGAR %d on %s — backing off %.1fs (attempt %d)",
                     resp.status_code, url, backoff, attempt + 1)
            await asyncio.sleep(backoff)
            continue
        return resp
    return last


# Section-16 transaction codes → human label. P/S are open-market; the rest are
# comp/mechanical and not conviction signals.
_TXN_LABEL = {
    "P": "Buy", "S": "Sell", "A": "Grant", "M": "Option exercise",
    "F": "Tax withholding", "G": "Gift", "C": "Conversion", "X": "Option exercise",
    "D": "Disposition to issuer", "W": "Will/inheritance", "J": "Other",
}


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
            if _TICKER_MAP is None or (time.time() - _TICKER_MAP_TS) > _TICKER_TTL_SEC:
                try:
                    resp = await _edgar_get(SEC_TICKERS_URL, timeout=15)
                    if resp is None or resp.status_code != 200:
                        raise RuntimeError(f"ticker map HTTP {getattr(resp, 'status_code', 'none')}")
                    data = resp.json()
                    m: dict[str, str] = {}
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
                        return None
    return (_TICKER_MAP or {}).get(sym)


def _owner_names(all_names: List[str], issuer_cik: str) -> List[str]:
    """Reporting owners only — drop the issuer's own name. EDGAR embeds the CIK
    in each display string, e.g. "SIEDEL RICHARD W. JR.  (CIK 0001661082)" and
    "Sensata Technologies Holding plc  (CIK 0001477294)"; the issuer is the one
    carrying `issuer_cik`."""
    return [n for n in (all_names or []) if issuer_cik not in n]


async def _fts_search(cik: str, form: str, days: int = 60, retries: int = 2) -> List[dict]:
    """EDGAR full-text search for a form type, scoped to one issuer CIK.
    Retries a couple of times — EDGAR FTS occasionally returns a throttled body
    without a `hits` block."""
    start = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    end = datetime.utcnow().strftime("%Y-%m-%d")
    params = {
        "forms": form, "ciks": cik, "dateRange": "custom",
        "startdt": start, "enddt": end,
    }
    for attempt in range(retries + 1):
        try:
            # Global rate-paced + 429-backed-off GET (see _edgar_get). This loop
            # now only re-tries the rare "200 but no hits block" throttle body —
            # actual 429/5xx backoff is handled inside _edgar_get.
            resp = await _edgar_get(EDGAR_FTS, params=params)
            if resp is not None and resp.status_code == 200:
                data = resp.json()
                if "hits" in data:
                    hits = data.get("hits", {}).get("hits", [])
                    out: List[dict] = []
                    for h in hits[:40]:
                        src = h.get("_source", {})
                        _id = h.get("_id", "")
                        adsh = src.get("adsh") or _id.split(":", 1)[0] or ""
                        doc = _id.split(":", 1)[1] if ":" in _id else ""
                        owners = _owner_names(src.get("display_names", []) or [], cik)
                        owner_ciks = [c for c in (src.get("ciks") or []) if c != cik]
                        out.append({
                            "form": src.get("form") or form,
                            "filed": src.get("file_date"),
                            "display_names": owners,
                            "owner": owners[0] if owners else None,
                            "cik": owner_ciks[0] if owner_ciks else "",
                            "accession": adsh,
                            "doc": doc,
                            "url": (
                                f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                                f"&CIK={cik}&type={form}&dateb=&owner=include&count=40"
                            ),
                        })
                    return out
        except Exception as exc:
            log.warning("EDGAR FTS %s for CIK %s (attempt %d) failed: %s",
                        form, cik, attempt + 1, exc)
        await asyncio.sleep(0.4 * (attempt + 1))
    return []


def _b(el: Optional[ET.Element], tag: str) -> bool:
    if el is None:
        return False
    v = (el.findtext(tag) or "").strip()
    return v in ("1", "true", "True")


def _parse_form4_xml(content) -> dict:
    """Pure parse of one Form 4 ownership document → relationship + transaction
    summary. Returns owner name, relationship label, whether the filer is an
    officer/director (vs an outside 10% owner), and whether the filing contains
    a real open-market purchase (code P, acquired)."""
    root = ET.fromstring(content)
    owner = (root.findtext(".//reportingOwner/reportingOwnerId/rptOwnerName")
             or root.findtext(".//rptOwnerName") or "").strip() or None
    rel = root.find(".//reportingOwnerRelationship")
    is_officer = _b(rel, "isOfficer")
    is_director = _b(rel, "isDirector")
    is_ten = _b(rel, "isTenPercentOwner")
    is_other = _b(rel, "isOther")
    title = (rel.findtext("officerTitle") if rel is not None else None) or None

    if is_officer:
        relationship = "Officer"
    elif is_director:
        relationship = "Director"
    elif is_ten:
        relationship = "10% owner"
    elif is_other:
        relationship = "Other"
    else:
        relationship = "—"
    # Officers/directors have fiduciary insight — the signal we care about.
    # A pure 10% holder (PE/VC fund) is an "insider" by SEC rule but a weaker
    # tell, so we tag it separately.
    is_insider = bool(is_officer or is_director)
    is_entity_holder = bool(is_ten and not (is_officer or is_director))

    buy_sh = sell_sh = grant_sh = 0.0
    buy_val = 0.0
    codes: list[str] = []
    for tr in root.findall(".//nonDerivativeTransaction"):
        code = (tr.findtext(".//transactionCode") or "").strip().upper()
        ad = (tr.findtext(".//transactionAcquiredDisposedCode/value") or "").strip().upper()
        try:
            sh = float(tr.findtext(".//transactionShares/value") or 0)
        except ValueError:
            sh = 0.0
        try:
            px = float(tr.findtext(".//transactionPricePerShare/value") or 0)
        except ValueError:
            px = 0.0
        if code:
            codes.append(code)
        if code == "P" and ad == "A":
            buy_sh += sh
            buy_val += sh * px
        elif code == "S" and ad == "D":
            sell_sh += sh
        elif code == "A" and ad == "A":
            grant_sh += sh

    is_buy = buy_sh > 0
    is_sell = sell_sh > 0
    if is_buy:
        txn = f"Buy {int(buy_sh):,} sh" + (f" @ ${buy_val / buy_sh:,.2f}" if buy_sh else "")
    elif is_sell:
        txn = f"Sell {int(sell_sh):,} sh"
    elif "A" in codes:
        txn = "Grant"
    elif "M" in codes or "X" in codes:
        txn = "Option exercise"
    elif "F" in codes:
        txn = "Tax withholding"
    elif "G" in codes:
        txn = "Gift"
    elif codes:
        txn = _TXN_LABEL.get(codes[0], codes[0])
    else:
        txn = "—"

    return {
        "owner": owner,
        "relationship": relationship,
        "title": title,
        "is_insider": is_insider,
        "is_entity_holder": is_entity_holder,
        "is_buy": is_buy,
        "is_sell": is_sell,
        "buy_shares": round(buy_sh, 2),
        "buy_value": round(buy_val, 2),
        "codes": codes,
        "txn": txn,
    }


async def _fetch_form4_detail(issuer_cik: str, accession: str, doc: str,
                              sem: asyncio.Semaphore) -> Optional[dict]:
    """Fetch + parse one Form 4 XML; cached by accession (immutable)."""
    if not accession or not doc or not doc.lower().endswith(".xml"):
        return None
    if accession in _FORM4_CACHE:
        return _FORM4_CACHE[accession]
    try:
        cik_int = str(int(issuer_cik))            # archive path has no zero-pad
        adsh_nodash = accession.replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{adsh_nodash}/{doc}"
        async with sem:
            resp = await _edgar_get(url)
        if resp is None or resp.status_code != 200:
            return None
        parsed = _parse_form4_xml(resp.content)
    except Exception as exc:
        log.warning("form4 parse %s failed: %s", accession, exc)
        return None
    if len(_FORM4_CACHE) < _FORM4_CACHE_MAX:
        _FORM4_CACHE[accession] = parsed
    return parsed


def _owner_of(f: dict) -> str:
    return (f.get("owner")
            or (f.get("display_names") or [None])[0]
            or "").strip()


def _empty_result(symbol: str, cik: Optional[str], note: str) -> dict:
    return {
        "symbol": symbol, "resolved_cik": cik, "note": note,
        "form4_count_60d": 0, "form4_count_30d": 0,
        "form4_unique_insiders_30d": 0,
        "form4_buy_count_30d": 0, "form4_sell_count_30d": 0,
        "form4_insider_buyers_30d": 0, "form4_cluster_buy": False,
        "sc13d_180d": 0, "sc13g_180d": 0, "has_recent_13d": False,
        "recent_filings": {"form4": [], "13d": [], "13g": []},
    }


async def insider_activity(symbol: str) -> dict:
    sym = (symbol or "").upper().strip()
    cik = await _ticker_to_cik(sym)
    if not cik:
        return _empty_result(sym, None, "ticker not found in SEC CIK map")

    form4, d13d, d13g = await asyncio.gather(
        _fts_search(cik, "4", days=60),
        _fts_search(cik, "SC 13D", days=180),
        _fts_search(cik, "SC 13G", days=180),
    )

    # Deep-enrich the most recent Form 4s with relationship + transaction detail.
    deep = form4[:_MAX_FORM4_DEEP]
    sem = asyncio.Semaphore(_FORM4_CONCURRENCY)   # bound to the running loop
    details = await asyncio.gather(
        *[_fetch_form4_detail(cik, f.get("accession", ""), f.get("doc", ""), sem) for f in deep]
    )
    for f, det in zip(deep, details):
        if det:
            if det.get("owner"):
                f["owner"] = det["owner"]
            f.update({
                "relationship": det["relationship"],
                "title": det["title"],
                "is_insider": det["is_insider"],
                "is_entity_holder": det["is_entity_holder"],
                "is_buy": det["is_buy"],
                "is_sell": det["is_sell"],
                "txn": det["txn"],
                "shares": det["buy_shares"],
                "value": det["buy_value"],
            })

    cutoff = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
    recent4 = [f for f in form4 if (f.get("filed") or "") >= cutoff]
    unique_filers = len({_owner_of(f) for f in recent4 if _owner_of(f)})
    insider_buyers = {
        _owner_of(f) for f in recent4
        if f.get("is_buy") and f.get("is_insider") and _owner_of(f)
    }
    buy_count = sum(1 for f in recent4 if f.get("is_buy"))
    sell_count = sum(1 for f in recent4 if f.get("is_sell"))

    return {
        "symbol": sym,
        "resolved_cik": cik,
        "form4_count_60d": len(form4),
        "form4_count_30d": len(recent4),
        "form4_unique_insiders_30d": unique_filers,
        "form4_buy_count_30d": buy_count,
        "form4_sell_count_30d": sell_count,
        "form4_insider_buyers_30d": len(insider_buyers),
        # Real cluster buying: ≥N distinct officers/directors bought open-market.
        "form4_cluster_buy": len(insider_buyers) >= CLUSTER_BUY_MIN_INSIDERS,
        "sc13d_180d": len(d13d),
        "sc13g_180d": len(d13g),
        "has_recent_13d": any((x.get("filed") or "") >= cutoff for x in d13d),
        "recent_filings": {
            "form4": form4[:8],
            "13d": d13d[:3],
            "13g": d13g[:3],
        },
    }


# ── Result cache (Mongo) — so broad coverage doesn't re-hit EDGAR every scan ──
# Ajay 2026-06-05: the cluster-buy chip needs insider data on far more than the
# top-20 candidates. Form 4 filings are daily, so a result cache (default 12h)
# lets a scan sweep hundreds of names while only fetching the STALE ones.
_INSIDER_TTL_SEC = int(os.getenv("INSIDER_CACHE_TTL_SEC", str(12 * 3600)))
_INSIDER_COLL = None


def _insider_coll():
    """The app's Mongo `insider_cache` collection (reuses history's connection).
    Memoized once it succeeds; retries on a later call if Mongo was unavailable."""
    global _INSIDER_COLL
    if _INSIDER_COLL is not None:
        return _INSIDER_COLL
    try:
        from . import history
        db = history._get_db()
        if db is not None:
            _INSIDER_COLL = db.insider_cache
            return _INSIDER_COLL
    except Exception:
        pass
    return None


async def insider_activity_cached(symbol: str) -> dict:
    """`insider_activity` with a Mongo result cache (TTL `_INSIDER_TTL_SEC`).
    Cache hit → instant (no EDGAR call); miss → fetch + store. Same return shape
    as the uncached call, so callers are interchangeable."""
    sym = (symbol or "").upper().strip()
    coll = _insider_coll()
    now = int(time.time())
    if coll is not None:
        try:
            doc = coll.find_one({"_id": sym})
            if doc and (now - int(doc.get("computed_at") or 0)) < _INSIDER_TTL_SEC:
                doc.pop("_id", None)
                doc.pop("computed_at", None)
                return doc
        except Exception:
            pass
    data = await insider_activity(sym)
    if coll is not None and data:
        try:
            coll.update_one({"_id": sym}, {"$set": {**data, "_id": sym, "computed_at": now}}, upsert=True)
        except Exception:
            pass
    return data
