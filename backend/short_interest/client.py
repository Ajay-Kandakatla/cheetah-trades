"""Short volume Massive client + Mongo cache.

Public API:
    short_volume_for(symbol)        → latest single-day snapshot dict | None
    short_volume_history(symbol, n) → list of last `n` daily records
    latest_short_pct(symbol)        → float | None  (just the % for quick chip lookup)

Cache strategy:
    * Mongo collection `short_volume_cache` keyed on (symbol, date).
    * Each upsert keeps the full FINRA record (all 15 fields per the
      Massive /stocks/v1/short-volume schema). We never delete rows so
      we accumulate a time-series usable for trend analysis.
    * A summary record per symbol caches the latest snapshot for fast
      "single chip lookup" reads (collection `short_volume_latest`).

The fetch loop pulls the last 30 days of data per request — enough for
the 20-day moving average we use to spot short-spike vs steady-state
short positioning. If a symbol is queried on a market day and we already
have today's record cached, we skip the HTTP call.

TWO SERIES, TWO CACHES — DO NOT CROSS THEM
──────────────────────────────────────────
This module owns two *different* short measurements, and reading one as
the other is a silent, plausible, wrong number:

  * SHORT VOLUME (daily) — what fraction of a single session's tape printed
    on the short side. Massive `/stocks/v1/short-volume`. Caches:
    `short_volume_cache` (time-series, one row per symbol+date) and
    `short_volume_latest` (newest snapshot per symbol).
  * SHORT INTEREST (bi-monthly) — total shares sold short and still open at
    a FINRA settlement, plus days-to-cover and % of shares outstanding.
    Massive `/stocks/v1/short-interest`, via `short_interest_for()`.
    Cache: `short_interest_latest` (SI_COLL), warmed by
    `python -m short_interest.client warm-si`, read in bulk by
    `short_interest_map()`.

`short_interest_map()` reads SI_COLL and nothing else — never the short
VOLUME caches. A days-to-cover leg on a board that read the volume ratio
would render a confident number of the wrong series.
"""
from __future__ import annotations

import logging
import math
import os
import time
from massive_keys import stocks_key
from datetime import date, datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger("short_interest.client")


# ---------- Mongo cache helpers ------------------------------------------------

# Module-level connection handle. Mirrors the pattern used by options/soir.py
# and other backend modules — each owns its own MongoClient + creates the
# indexes it cares about on first call.
_db = None


def _get_db():
    """Lazy Mongo handle. Returns None if Mongo is unreachable (dev mode)."""
    global _db
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient, ASCENDING, DESCENDING
        client = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"),
                              serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        _db = client[os.getenv("MONGO_DB", "cheetah")]
        # Time-series of daily short volume — one row per (symbol, date).
        _db.short_volume_cache.create_index(
            [("symbol", ASCENDING), ("date", DESCENDING)], unique=True,
        )
        # Latest snapshot per symbol — fast read path for chip rendering.
        _db.short_volume_latest.create_index("symbol", unique=True)
        return _db
    except Exception as exc:
        log.warning("short_interest: Mongo unavailable: %s", exc)
        return None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _today_iso() -> str:
    return _now_utc().date().isoformat()


def _cached_latest(symbol: str) -> Optional[dict]:
    """Read the latest cached snapshot for `symbol`. Returns None if the
    cache is empty OR the cached value is older than 24h."""
    db = _get_db()
    if db is None:
        return None
    try:
        rec = db.short_volume_latest.find_one({"symbol": symbol.upper()}, {"_id": 0})
        if not rec:
            return None
        cached_at = rec.get("cached_at")
        if not cached_at:
            return None
        # The FINRA feed updates daily. A cached snapshot is fresh enough
        # if it was fetched within the last 24h.
        if isinstance(cached_at, str):
            cached_at = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
        if (_now_utc() - cached_at).total_seconds() > 86_400:
            return None
        return rec.get("snapshot")
    except Exception as exc:
        log.warning("short_interest: cache read failed for %s: %s", symbol, exc)
        return None


def _persist_records(symbol: str, records: list[dict]) -> None:
    """Upsert each record into short_volume_cache. Update short_volume_latest
    with the newest record so single-chip lookups are O(1)."""
    db = _get_db()
    if db is None or not records:
        return
    try:
        # Upsert per (symbol, date) so we accumulate a time-series.
        for r in records:
            db.short_volume_cache.update_one(
                {"symbol": symbol.upper(), "date": r["date"]},
                {"$set": {**r, "symbol": symbol.upper()}},
                upsert=True,
            )
        # Latest pointer for fast reads
        newest = max(records, key=lambda x: x["date"])
        db.short_volume_latest.update_one(
            {"symbol": symbol.upper()},
            {"$set": {
                "symbol": symbol.upper(),
                "snapshot": newest,
                "cached_at": _now_utc().isoformat(),
            }},
            upsert=True,
        )
    except Exception as exc:
        log.warning("short_interest: persist failed for %s: %s", symbol, exc)


# ---------- Massive fetcher ----------------------------------------------------

# Process-level lazy-disable. If the endpoint returns 401/403 (plan
# downgrade, key rotation), skip subsequent calls in this run.
_short_volume_disabled = False


def _fetch_from_massive(symbol: str, days_back: int = 30) -> list[dict]:
    """Hit /stocks/v1/short-volume for the last N days.

    Returns list of records (may be empty if no FINRA data for this symbol
    or if the plan doesn't include short-volume). Each record matches the
    Massive schema exactly — caller pulls the fields it needs.
    """
    global _short_volume_disabled
    if _short_volume_disabled:
        return []
    api_key = stocks_key()
    if not api_key:
        return []

    try:
        import requests
    except ImportError:
        log.warning("short_interest: requests not installed")
        return []

    since = (_now_utc().date() - timedelta(days=days_back)).isoformat()
    url = "https://api.massive.com/stocks/v1/short-volume"
    params = {
        "ticker":  symbol.upper(),
        "date.gte": since,
        "limit":   max(days_back, 30),
        "order":   "desc",
        "sort":    "date",
        "apiKey":  api_key,
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code in (401, 403):
            if not _short_volume_disabled:
                log.warning(
                    "short_interest: Massive returned %s for %s — plan doesn't "
                    "include short-volume. Disabling for this run.",
                    r.status_code, symbol,
                )
                _short_volume_disabled = True
            return []
        if r.status_code == 429:
            log.warning("short_interest: rate-limited on %s", symbol)
            return []
        if r.status_code != 200:
            log.debug("short_interest: %s returned HTTP %s", symbol, r.status_code)
            return []
        body = r.json() or {}
        return body.get("results") or []
    except Exception as exc:
        log.warning("short_interest: fetch failed for %s: %s", symbol, exc)
        return []


# ---------- Public API ---------------------------------------------------------

def short_volume_for(symbol: str, *, force_refresh: bool = False) -> Optional[dict]:
    """Latest single-day short volume snapshot for `symbol`.

    Returns dict with keys:
        date              (str ISO)
        ticker            (str)
        short_volume      (float)
        total_volume      (float)
        short_volume_ratio (float, 0-100)
        exempt_volume     (float)  — market-maker hedge shorts
        non_exempt_volume (float)  — directional short bets
        ... plus venue-level breakdown

    Returns None when:
        - Massive plan doesn't include short volume (silently disabled)
        - No FINRA data for this symbol (ADRs, foreign listings)
        - Network failure (caller should treat None as "no signal")
    """
    if not force_refresh:
        cached = _cached_latest(symbol)
        if cached:
            return cached

    records = _fetch_from_massive(symbol)
    if not records:
        return None

    _persist_records(symbol, records)
    return max(records, key=lambda x: x["date"])


def short_volume_history(symbol: str, days: int = 30) -> list[dict]:
    """Last `days` days of short volume records, newest first.

    Hits Mongo cache first; only fetches from Massive if the cache is
    older than 24h. Useful for trend analysis (rising short% on
    advancing stock = squeeze setup).
    """
    db = _get_db()
    if db is not None:
        try:
            cursor = (db.short_volume_cache
                        .find({"symbol": symbol.upper()}, {"_id": 0})
                        .sort("date", -1)
                        .limit(days))
            cached = list(cursor)
            # If we have at least `days * 0.5` records AND the newest is
            # less than 24h old, return cache without a fresh fetch.
            if cached and len(cached) >= max(days // 2, 5):
                newest_date = max(c["date"] for c in cached)
                age_days = (date.today() - date.fromisoformat(newest_date)).days
                if age_days <= 2:  # weekend tolerance
                    return cached
        except Exception as exc:
            log.warning("short_interest: history cache read failed: %s", exc)

    records = _fetch_from_massive(symbol, days_back=days)
    if records:
        _persist_records(symbol, records)
    return sorted(records, key=lambda x: x["date"], reverse=True)[:days]


def latest_short_pct(symbol: str) -> Optional[float]:
    """Just the latest short_volume_ratio (0-100). Fast path for chip rendering."""
    snap = short_volume_for(symbol)
    if not snap:
        return None
    return snap.get("short_volume_ratio")


# ---------- Short INTEREST (bi-monthly FINRA settlement) -----------------------
# Distinct from short VOLUME above: short interest is the FINRA bi-monthly
# settlement of total shares sold short — the classic squeeze gauge. Massive:
# GET /stocks/v1/short-interest (note the .desc dot-sort; order=desc is ignored).

_float_cache: dict[str, Optional[int]] = {}

# Squeeze-fuel thresholds. STANDARD market heuristics (NOT from a SEPA book) —
# % of shares short and days-to-cover are the two classic gauges of how hard a
# short position would be to unwind. Conservative bands; env-tunable. The raw
# numbers are always returned so the user can judge for themselves.
SI_HIGH_PCT = float(os.getenv("SI_HIGH_PCT_FLOAT", "20"))
SI_ELEV_PCT = float(os.getenv("SI_ELEV_PCT_FLOAT", "10"))
SI_HIGH_DTC = float(os.getenv("SI_HIGH_DAYS_TO_COVER", "5"))
SI_ELEV_DTC = float(os.getenv("SI_ELEV_DAYS_TO_COVER", "2.5"))


def _fetch_short_interest_rows(symbol: str, limit: int = 4) -> list[dict]:
    """Latest `limit` bi-monthly short-interest settlements, newest first."""
    api_key = stocks_key()
    if not api_key:
        return []
    try:
        import requests
    except ImportError:
        return []
    try:
        r = requests.get(
            "https://api.massive.com/stocks/v1/short-interest",
            params={"ticker": symbol.upper(), "sort": "settlement_date.desc",
                    "limit": limit, "apiKey": api_key},
            timeout=10,
        )
        if r.status_code != 200:
            log.debug("short_interest(SI): %s HTTP %s", symbol, r.status_code)
            return []
        return (r.json() or {}).get("results") or []
    except Exception as exc:
        # type name only: an exception's text can carry the request URL and,
        # with it, the apiKey (the 5th-leak lesson, 2026-09-12).
        log.warning("short_interest(SI): fetch failed for %s: %s", symbol,
                    type(exc).__name__)
        return []


def _shares_outstanding(symbol: str) -> Optional[int]:
    """Share count from Massive ticker reference (cached per process). A true
    free float isn't in the feed, so this is shares OUTSTANDING — the metric is
    labelled accordingly (short % of shares outstanding)."""
    sym = symbol.upper()
    if sym in _float_cache:
        return _float_cache[sym]
    api_key = stocks_key()
    val = None
    if api_key:
        try:
            import requests
            r = requests.get(f"https://api.massive.com/v3/reference/tickers/{sym}",
                             params={"apiKey": api_key}, timeout=10)
            if r.status_code == 200:
                res = (r.json() or {}).get("results") or {}
                val = res.get("share_class_shares_outstanding") or res.get("weighted_shares_outstanding")
        except Exception as exc:
            log.debug("short_interest(shares): %s failed: %s", sym, type(exc).__name__)
    _float_cache[sym] = val
    return val


def _squeeze_signal(pct, dtc) -> str:
    """Squeeze-fuel label. PCT-PRIMARY: short % of shares is the fuel; days-to-
    cover only amplifies it. A low short % can't squeeze no matter how high the
    days-to-cover (avoids flagging mega-caps like AAPL at <1% short)."""
    d = dtc or 0
    if pct is None:                          # no share count → coarse dtc-only
        return "elevated" if d >= SI_HIGH_DTC else "low"
    if pct >= SI_HIGH_PCT or (pct >= SI_ELEV_PCT and d >= SI_HIGH_DTC):
        return "high"
    if pct >= SI_ELEV_PCT or (pct >= SI_ELEV_PCT / 2 and d >= SI_HIGH_DTC):
        return "elevated"
    return "low"


def short_interest_for(symbol: str) -> Optional[dict]:
    """Latest bi-monthly short interest + squeeze gauges, or None if Massive has
    no short-interest record (ADRs / thin names).

    Keys: settlement_date, short_interest (shares), avg_daily_volume,
    days_to_cover, shares_outstanding, pct_of_shares, prev_settlement_date,
    si_change_pct (vs prior settlement), squeeze (low|elevated|high).
    """
    rows = _fetch_short_interest_rows(symbol, limit=4)
    if not rows:
        return None
    latest = rows[0]
    prev = rows[1] if len(rows) > 1 else None
    si = latest.get("short_interest")
    shares = _shares_outstanding(symbol)
    pct = (si / shares * 100) if (si and shares) else None
    dtc = latest.get("days_to_cover")
    prev_si = prev.get("short_interest") if prev else None
    chg = ((si - prev_si) / prev_si * 100) if (si and prev_si) else None
    return {
        "symbol": symbol.upper(),
        "settlement_date": latest.get("settlement_date"),
        "short_interest": si,
        "avg_daily_volume": latest.get("avg_daily_volume"),
        "days_to_cover": dtc,
        "shares_outstanding": shares,
        "pct_of_shares": round(pct, 2) if pct is not None else None,
        "prev_settlement_date": prev.get("settlement_date") if prev else None,
        "si_change_pct": round(chg, 1) if chg is not None else None,
        "squeeze": _squeeze_signal(pct, dtc),
    }


# ---------- Short-INTEREST bulk cache (bi-monthly FINRA settlements) -----------
#
# The board path (sepa/bonde_picks.attach) needs a days-to-cover number for up
# to ~260 names in one page render. `short_interest_for()` is TWO Massive calls
# per symbol, so it can never run on a request path: a cron warms this cache and
# the board does ONE `$in` read against it.

SI_COLL = "short_interest_latest"

# APP freshness LABEL, not one of his numbers and never a gate (§7.15, Rule #7:
# check the reported PERIOD against the source's cadence, not the cache age).
# FINRA settles mid-month and end-of-month and publishes ~9 business days later,
# so a settlement older than 45 days means two missed settlements plus the
# publication lag — i.e. the cache, not the market, is behind. A stale label is
# rendered beside the value; it never flips a pass/fail.
SI_STALE_DAYS = 45

# How long a warm result is considered fresh enough to skip a re-fetch. The
# underlying series only moves twice a month; a day keeps the warm cheap and
# still picks up a new settlement the day after it publishes.
SI_WARM_TTL_SEC = 24 * 3600


def _si_coll(db=None):
    """The short-INTEREST collection (never the short-VOLUME ones)."""
    d = db if db is not None else _get_db()
    if d is None:
        return None
    try:
        return d[SI_COLL]
    except Exception as exc:                                   # noqa: BLE001
        log.warning("short_interest: %s unavailable: %s", SI_COLL, exc)
        return None


def _age_days(settlement_date) -> Optional[int]:
    """Calendar days between a settlement date and today, or None.

    ONE CLOCK ON THE PICK LINE: `today` here is the LOCAL date, the same
    `date.today()` the surprise and IPO legs read through
    `sepa.bonde_picks._today()`. A UTC `today` runs a calendar day ahead of
    the local one every evening after 19:00 CT, which would move this stale
    label — and only this one — a day out of step with the surprise leg's on
    the same row. The label is an app freshness bound, never a gate (§7.15),
    so the cheap fix is to read the same clock everywhere.
    """
    if not settlement_date:
        return None
    try:
        d = datetime.strptime(str(settlement_date)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return (date.today() - d).days


def short_interest_map(symbols, db=None) -> dict:
    """{SYM: doc + stale + age_days} for a list of names — ONE Mongo read.

    Reads `SI_COLL` only. `stale` and `age_days` are both None when the stored
    doc carries no `settlement_date` (a remembered miss, or a provider with no
    record for the name); otherwise `age_days` is calendar days since the
    settlement and `stale` is `age_days > SI_STALE_DAYS`.

    Never fetches: a symbol with no doc is simply absent from the map, and the
    caller renders it as unknown rather than as a zero.
    """
    syms = []
    for s in symbols or []:
        s = str(s or "").strip().upper()
        if s and s not in syms:
            syms.append(s)
    coll = _si_coll(db)
    if coll is None or not syms:
        return {}
    out: dict = {}
    try:
        for doc in coll.find({"_id": {"$in": syms}}):
            sym = doc.get("_id")
            if not sym:
                continue
            rec = dict(doc)
            rec.pop("_id", None)
            age = _age_days(rec.get("settlement_date"))
            rec["age_days"] = age
            rec["stale"] = None if age is None else bool(age > SI_STALE_DAYS)
            out[str(sym).upper()] = rec
    except Exception as exc:                                   # noqa: BLE001
        log.warning("short_interest: map read failed: %s", exc)
        return {}
    return out


class _WarmResult(dict):
    """The per-symbol warm's result. `kept` (2026-10-03) reads 0 until a None
    answer keeps a held doc; it is only materialised when non-zero so the
    long-standing exact-shape result (n/fetched/written/skipped/failed) is
    unchanged for every caller that compares it whole."""

    def __missing__(self, key):
        if key == "kept":
            return 0
        raise KeyError(key)


def warm_short_interest(symbols, db=None, sleep_sec: float = 0.25,
                        force: bool = False) -> dict:
    """Fetch + store short interest for `symbols`. Network, cron-only.

    TWO Massive calls per name, so it sleeps between names and skips anything
    fetched within `SI_WARM_TTL_SEC` unless `force`. A `None` answer is WRITTEN
    as a remembered miss (`settlement_date: None`) so the next warm does not
    re-pay for a name the provider has no record for, and the board can tell
    "never warmed" from "warmed, no record". Never raises.

    FIX 2026-10-03: `_fetch_short_interest_rows` answers `[]` on ANY HTTP
    error, so a `None` here is also what a provider outage looks like. A
    `None` therefore never REPLACES a doc that holds a settlement — the good
    older number is kept (`kept`) rather than overwritten with "no record".
    When the existence read itself fails the answer is unknowable, so a `None`
    is not written at all (counted `failed`).
    """
    syms = []
    for s in symbols or []:
        s = str(s or "").strip().upper()
        if s and s not in syms:
            syms.append(s)
    res = _WarmResult(n=len(syms), fetched=0, written=0, skipped=0, failed=0)
    coll = _si_coll(db)
    if coll is None or not syms:
        return res

    fresh = set()
    held: Optional[set] = set()     # names whose doc holds a settlement; None = unknown
    cutoff = time.time() - SI_WARM_TTL_SEC
    try:
        for d in coll.find({"_id": {"$in": syms}},
                           {"_id": 1, "fetched_at": 1, "settlement_date": 1}):
            if d.get("settlement_date"):
                held.add(d["_id"])
            if not force and (d.get("fetched_at") or 0) >= cutoff:
                fresh.add(d["_id"])
    except Exception as exc:                                   # noqa: BLE001
        log.warning("short_interest: warm freshness read failed: %s", type(exc).__name__)
        fresh = set()
        held = None

    todo = [s for s in syms if s not in fresh]
    res["skipped"] = len(syms) - len(todo)

    for i, sym in enumerate(todo):
        try:
            d = short_interest_for(sym)
            res["fetched"] += 1
        except Exception as exc:                               # noqa: BLE001
            log.warning("short_interest: warm %s failed: %s", sym, exc)
            res["failed"] += 1
            d = None
            if i < len(todo) - 1 and sleep_sec:
                time.sleep(sleep_sec)
            continue

        if d:
            doc = {
                "_id": sym,
                "symbol": sym,
                "settlement_date": d.get("settlement_date"),
                "short_interest": d.get("short_interest"),
                "avg_daily_volume": d.get("avg_daily_volume"),
                "days_to_cover": d.get("days_to_cover"),
                "shares_outstanding": d.get("shares_outstanding"),
                "pct_of_shares": d.get("pct_of_shares"),
                "prev_settlement_date": d.get("prev_settlement_date"),
                "si_change_pct": d.get("si_change_pct"),
                "squeeze": d.get("squeeze"),
                "fetched_at": time.time(),
            }
        elif held is None:
            # Could not tell whether a good doc exists: never risk replacing it.
            res["failed"] += 1
            if i < len(todo) - 1 and sleep_sec:
                time.sleep(sleep_sec)
            continue
        elif sym in held:
            # A None over a held settlement is as likely an outage as a real
            # "no record" — keep the good older number.
            res["kept"] += 1
            if i < len(todo) - 1 and sleep_sec:
                time.sleep(sleep_sec)
            continue
        else:
            # A remembered miss — reads as `no_si_record`, not as "not warmed".
            doc = {"_id": sym, "symbol": sym, "settlement_date": None,
                   "fetched_at": time.time()}
        try:
            coll.replace_one({"_id": sym}, doc, upsert=True)
            res["written"] += 1
        except Exception as exc:                               # noqa: BLE001
            log.warning("short_interest: warm upsert %s failed: %s", sym, exc)
            res["failed"] += 1
        if i < len(todo) - 1 and sleep_sec:
            time.sleep(sleep_sec)
    return res


# ---------- Short-INTEREST bulk warm, by settlement date (2026-10-03) ---------
#
# Ajay 2026-10-03: "can you add this field to all our chart maps scan. also the
# individual tickers please". The per-name warm above is TWO Massive calls per
# symbol (~79 min for the 2,744-name universe). Massive answers a whole FINRA
# settlement in ONE call (`settlement_date=X&limit=50000`, ~1.8 s, 22.6k
# tickers, measured 2026-10-03), so the universe warm is at most THREE calls:
#   1. which settlements are newest (one per-ticker call on SETTLEMENT_REF_TICKER)
#   2. the latest settlement, whole market
#   3. the prior settlement, whole market (for the change and the partial guard)
# and ZERO calls when FINRA's calendar says no newer settlement can be out yet
# (`read.newer_settlement_can_exist`). Denominators come from ONE `shares_cache`
# read at warm time (yfinance float / shares outstanding, with their date), so
# the served read stays ONE `$in` query. A good older doc is never replaced by a
# miss, never moved backwards, and nothing is written when a call fails.

SI_BULK_LIMIT = 50000
SI_BULK_MAX_PAGES = 5
SI_BULK_SLEEP_SEC = 0.25
# HIS CALL #11 — a data-completeness constant, not a market threshold: a
# latest settlement with fewer rows than this share of the prior one is taken
# as a partial provider load and written NOT AT ALL (retried next run).
SI_BULK_MIN_ROWS_RATIO = 0.9
SI_BULK_WRITE_CHUNK = 1000
# The newest-settlement probe ticker (probe 2026-10-03: 210 settlements back to
# 2017-12-29, never gapped).
SETTLEMENT_REF_TICKER = "AAPL"

_SI_URL = "https://api.massive.com/stocks/v1/short-interest"


def _finite(v) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _pos_int(v) -> Optional[int]:
    f = _finite(v)
    return int(round(f)) if (f is not None and f > 0) else None


def _nonneg_int(v) -> Optional[int]:
    f = _finite(v)
    return int(round(f)) if (f is not None and f >= 0) else None


def _fetch_settlement_rows(settlement_date: str, calls: Optional[list] = None
                           ) -> Optional[dict]:
    """{TICKER: row} for ONE FINRA settlement, whole market. None on no key, a
    non-200, an exception or zero rows. Logs a status code or an exception TYPE
    only — never `str(exc)` or a URL (either can carry the apiKey)."""
    api_key = stocks_key()
    if not api_key:
        log.warning("short_interest(bulk): no Massive key")
        return None
    try:
        import requests
    except ImportError:
        return None
    d = str(settlement_date)[:10]
    out: dict = {}
    url: Optional[str] = _SI_URL
    params: Optional[dict] = {"settlement_date": d, "limit": SI_BULK_LIMIT, "apiKey": api_key}
    pages = 0
    while url and pages < SI_BULK_MAX_PAGES:
        if pages and SI_BULK_SLEEP_SEC:
            time.sleep(SI_BULK_SLEEP_SEC)
        pages += 1
        if calls is not None:
            calls.append(d)
        try:
            r = requests.get(url, params=params, timeout=60)
        except Exception as exc:                               # noqa: BLE001
            log.warning("short_interest(bulk): %s fetch failed: %s", d, type(exc).__name__)
            return None
        if r.status_code != 200:
            log.warning("short_interest(bulk): %s HTTP %s", d, r.status_code)
            return None
        try:
            body = r.json() or {}
        except Exception as exc:                               # noqa: BLE001
            log.warning("short_interest(bulk): %s bad body: %s", d, type(exc).__name__)
            return None
        for row in body.get("results") or []:
            if not isinstance(row, dict):
                continue
            t = str(row.get("ticker") or "").strip().upper()
            if t and str(row.get("settlement_date") or "")[:10] == d:
                out[t] = row
        nxt = body.get("next_url")
        if nxt:
            url, params = str(nxt), {"apiKey": api_key}
        else:
            url = None
    return out or None


def _settlement_dates_from_provider(calls: Optional[list] = None
                                    ) -> Optional[tuple]:
    """(latest, prior) settlement dates the provider holds, via ONE per-ticker
    call on SETTLEMENT_REF_TICKER. None when it answers nothing."""
    if calls is not None and stocks_key():
        calls.append("discover")           # no key → no HTTP call is made
    rows = _fetch_short_interest_rows(SETTLEMENT_REF_TICKER, limit=2)
    dates = [str(r.get("settlement_date"))[:10] for r in rows or []
             if isinstance(r, dict) and r.get("settlement_date")]
    if not dates:
        return None
    return (dates[0], dates[1] if len(dates) > 1 else None)


def _denominators(db) -> dict:
    """{SYM: {float_shares, shares_outstanding, as_of_iso}} — ONE `shares_cache`
    read (yfinance floatShares / sharesOutstanding, written by
    sepa.volume_movers). Non-finite or <= 0 → None. Any failure → {}."""
    out: dict = {}
    try:
        d = db if db is not None else _get_db()
        if d is None:
            return {}
        for doc in d["shares_cache"].find(
                {}, {"float_shares": 1, "shares_outstanding": 1, "as_of": 1}):
            sym = str(doc.get("_id") or "").strip().upper()
            if not sym:
                continue
            asof = None
            a = _finite(doc.get("as_of"))
            if a is not None and a > 0:
                try:
                    asof = datetime.fromtimestamp(a, tz=timezone.utc).date().isoformat()
                except (OverflowError, OSError, ValueError):
                    asof = None
            out[sym] = {"float_shares": _pos_int(doc.get("float_shares")),
                        "shares_outstanding": _pos_int(doc.get("shares_outstanding")),
                        "as_of_iso": asof}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("short_interest(bulk): shares_cache read failed: %s", type(exc).__name__)
        return {}
    return out


def _build_doc(sym, row, prev_row, denom, *, latest, prior, fetched_at) -> Optional[dict]:
    """The v2 `short_interest_latest` doc for one ticker, or None when the row
    carries no usable short-interest count (a reported 0 is real and kept)."""
    from short_interest import read as SR       # lazy: read imports this module

    if not isinstance(row, dict):
        return None
    si = _nonneg_int(row.get("short_interest"))
    if si is None:
        return None
    dtc = _finite(row.get("days_to_cover"))
    dtc = dtc if (dtc is not None and dtc >= 0) else None
    adv = _nonneg_int(row.get("avg_daily_volume"))
    has_prev = isinstance(prev_row, dict)
    prev_si = _nonneg_int(prev_row.get("short_interest")) if has_prev else None
    chg = round((si - prev_si) / prev_si * 100.0, 1) if (prev_si is not None and prev_si > 0) else None
    den = denom if isinstance(denom, dict) else {}
    fl = _pos_int(den.get("float_shares"))
    so = _pos_int(den.get("shares_outstanding"))
    asof = den.get("as_of_iso")
    pf = round(si / fl * 100.0, 2) if fl else None
    ps = round(si / so * 100.0, 2) if so else None
    sym = str(sym).upper()
    return {
        "_id": sym, "symbol": sym, "v": 2,
        "settlement_date": str(latest)[:10],
        "short_interest": si,
        "avg_daily_volume": adv,
        "days_to_cover": dtc,
        "prev_settlement_date": (str(prior)[:10] if (has_prev and prior) else None),
        "prev_short_interest": prev_si,
        "si_change_pct": chg,
        "float_shares": fl,
        "float_asof": asof if fl else None,
        "float_source": SR.FLOAT_SOURCE if fl else None,
        "shares_outstanding": so,
        "shares_asof": asof if so else None,
        "shares_source": SR.SHARES_SOURCE if so else None,
        "pct_of_float": pf,
        # LEGACY KEY NAME kept: the 📈 Bonde DTC leg displays `pct_of_shares`.
        "pct_of_shares": ps,
        # Legacy compatibility only — read.py never serves it.
        "squeeze": _squeeze_signal(ps, dtc),
        "source": SR.SOURCE_SI,
        "checked_settlement": str(latest)[:10],
        "fetched_at": fetched_at,
    }


def _canonical_rows(rows: dict) -> dict:
    """Re-key provider rows to the app's spelling (2026-10-03): Massive spells
    class shares with a dot (BRK.B); the universe, tiles and `shares_cache`
    use the dash (BRK-B). Without this a class share is written under BRK.B
    with no float, and BRK-B gets a remembered miss. A row the provider
    already spells the app's way wins a collision."""
    from sepa.symbols import for_yahoo       # lazy, like read.py: no import cycle
    out: dict = {}
    for t, row in (rows or {}).items():
        c = for_yahoo(t)
        if c in out and c != t:
            continue
        out[c] = row
    return out


def warm_short_interest_bulk(scope=None, db=None, *, force: bool = False,
                             dry_run: bool = False, today=None,
                             sleep_sec: float = SI_BULK_SLEEP_SEC) -> dict:
    """Warm `short_interest_latest` from whole-market FINRA settlements.

    0 provider calls when no newer settlement can be out (FINRA calendar), 1
    when one can but the provider still answers the held one, 3 on a new
    settlement. Writes every FINRA ticker as a v2 doc, a remembered miss for a
    `scope` name FINRA has no row for, and only `checked_settlement` on a held
    doc the new settlement lacks -- both only once `due_date(latest)` has
    passed; before that such a name is `deferred` (left pending, fetched again
    next run), since the provider may still be loading the settlement. ATOMIC on failure: any failed call, or a
    partial settlement, writes nothing. Never raises.
    """
    res = {"mode": "bulk", "provider_calls": 0, "latest": None, "prior": None,
           "rows_latest": 0, "rows_prior": 0, "written": 0, "misses": 0, "kept": 0,
           "deferred": 0, "skipped_reason": None, "error": None}
    if dry_run:
        res["docs"] = []
    try:
        _warm_bulk(res, scope, db, force=force, dry_run=dry_run, today=today,
                   sleep_sec=sleep_sec)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("short_interest(bulk): warm failed: %s", type(exc).__name__)
        res["error"] = "warm failed: %s" % type(exc).__name__
    return res


def _warm_bulk(res, scope, db, *, force, dry_run, today, sleep_sec) -> None:
    from short_interest import read as SR       # lazy: read imports this module

    coll = _si_coll(db)
    if coll is None:
        res["error"] = "no_db"
        return
    names: list = []
    for s in scope or []:
        s = str(s or "").strip().upper()
        if s and s not in names:
            names.append(s)

    existing: dict = {}
    for d in coll.find({}, {"settlement_date": 1, "checked_settlement": 1, "v": 1}):
        if d.get("_id"):
            existing[str(d["_id"]).upper()] = d
    marks = []
    for d in existing.values():
        if d.get("checked_settlement"):
            marks.append(str(d["checked_settlement"])[:10])
        elif d.get("v") == 2 and d.get("settlement_date"):
            marks.append(str(d["settlement_date"])[:10])
    held = max(marks) if marks else None
    # Pending = a scope name the bulk warm has not answered at `held` yet. A
    # legacy (per-name) doc never carries `checked_settlement`, so it is pending
    # until a bulk warm reaches it.
    pending = [s for s in names
               if s not in existing
               or str(existing[s].get("checked_settlement") or "")[:10] != held]

    if not force and held and not pending and not SR.newer_settlement_can_exist(held, today):
        nxt = SR.next_settlement_after(SR._as_date(held))
        res["skipped_reason"] = ("no newer FINRA settlement can be out before %s"
                                 % SR.publication_date(nxt).isoformat())
        return

    calls: list = []
    try:
        disc = _settlement_dates_from_provider(calls)
    finally:
        res["provider_calls"] = len(calls)
    if not disc:
        res["error"] = "settlement discovery failed (no rows for %s)" % SETTLEMENT_REF_TICKER
        return
    latest, prior = disc
    res["latest"], res["prior"] = latest, prior
    if held and latest < held:
        res["skipped_reason"] = "provider at %s, behind the held %s" % (latest, held)
        return
    if not force and latest == held and not pending:
        res["skipped_reason"] = "provider still at %s" % latest
        return
    if not prior:
        res["error"] = "no prior settlement from the provider"
        return

    if sleep_sec:
        time.sleep(sleep_sec)
    rows_latest = _fetch_settlement_rows(latest, calls)
    res["provider_calls"] = len(calls)
    if rows_latest is None:
        res["error"] = "latest settlement %s fetch failed" % latest
        return
    if sleep_sec:
        time.sleep(sleep_sec)
    rows_prior = _fetch_settlement_rows(prior, calls)
    res["provider_calls"] = len(calls)
    if rows_prior is None:
        res["error"] = "prior settlement %s fetch failed" % prior
        return
    rows_latest, rows_prior = _canonical_rows(rows_latest), _canonical_rows(rows_prior)
    res["rows_latest"], res["rows_prior"] = len(rows_latest), len(rows_prior)
    if len(rows_latest) < SI_BULK_MIN_ROWS_RATIO * len(rows_prior):
        res["error"] = ("partial settlement %s: %d of %d rows"
                        % (latest, len(rows_latest), len(rows_prior)))
        return

    denoms = _denominators(db)
    now = time.time()
    ops: list = []       # (kind, sym, payload)
    built = set()
    for t, row in rows_latest.items():
        ex = existing.get(t)
        ex_sd = str((ex or {}).get("settlement_date") or "")[:10]
        if ex and ex_sd and ex_sd > latest:
            continue                       # never move a doc backwards
        if not force and ex and ex.get("v") == 2 and ex_sd == latest:
            built.add(t)
            continue
        doc = _build_doc(t, row, rows_prior.get(t), denoms.get(t),
                         latest=latest, prior=prior, fetched_at=now)
        if doc is None:
            continue
        ops.append(("replace", t, doc))
        built.add(t)
    # Inside the ingest window (publication day through due_date(latest)) the
    # provider may still be loading the settlement: a universe name missing
    # from it is left PENDING (no `checked_settlement`, no miss doc) so a later
    # run fetches again. Only after the window is a missing name recorded.
    settled = SR._today(today) > SR.due_date(SR._as_date(latest))
    for s in names:
        if s in built:
            continue
        ex = existing.get(s)
        ex_sd = str((ex or {}).get("settlement_date") or "")[:10]
        if ex and ex_sd:
            # A good older number: keep the data, record that it was checked.
            if ex_sd <= latest:
                op = ("check", s, None)
            else:
                continue
        else:
            op = ("miss", s, {"_id": s, "symbol": s, "v": 2, "settlement_date": None,
                              "checked_settlement": latest, "fetched_at": now})
        if not settled:
            res["deferred"] += 1
            continue
        ops.append(op)

    if dry_run:
        res["docs"] = [p for k, _s, p in ops if k in ("replace", "miss")]
        res["written"] = sum(1 for k, _s, _p in ops if k == "replace")
        res["misses"] = sum(1 for k, _s, _p in ops if k == "miss")
        res["kept"] = sum(1 for k, _s, _p in ops if k == "check")
        return

    from pymongo import ReplaceOne, UpdateOne
    for i in range(0, len(ops), SI_BULK_WRITE_CHUNK):
        chunk = ops[i:i + SI_BULK_WRITE_CHUNK]
        reqs = []
        for kind, sym, payload in chunk:
            if kind == "check":
                reqs.append(UpdateOne({"_id": sym}, {"$set": {"checked_settlement": latest}}))
            else:
                reqs.append(ReplaceOne({"_id": sym}, payload, upsert=True))
        try:
            coll.bulk_write(reqs, ordered=False)
        except Exception as exc:                               # noqa: BLE001
            log.warning("short_interest(bulk): write failed: %s", type(exc).__name__)
            res["error"] = "write failed: %s" % type(exc).__name__
            return
        for kind, _s, _p in chunk:
            key = {"replace": "written", "miss": "misses", "check": "kept"}[kind]
            res[key] += 1


def _main(argv=None) -> int:
    """`python -m short_interest.client warm-si [--dry-run] [--force]`
    `| warm-si --per-symbol [--all-passers | --symbols A,B,C] [--sleep 0.25] [--force]`
    `| show-si`.

    `warm-si` (2026-10-03) is the BULK warm over the `full` universe: 0, 1 or 3
    provider calls (see `warm_short_interest_bulk`). `--per-symbol` keeps the
    old per-name path: default scope the Bonde board's shown names (≤260);
    `--all-passers` widens to every Bonde-pillar passer (~1,051 names, ~35 min).
    `--symbols` or `--all-passers` alone still means the per-name path (what
    those invocations did before the bulk warm), never a silent whole-market run.

    `from sepa import …` lives INSIDE this function on purpose: the board path
    is sepa.bonde → sepa.bonde_picks → (inside attach) short_interest.client, so
    a module-level import here would close the cycle. Never prints the key or
    a URL.
    """
    import sys
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = (args[0] if args else "warm-si").lower()
    db = _get_db()

    if cmd == "show-si":
        coll = _si_coll(db)
        if coll is None:
            print("short_interest: no db")
            return 1
        docs = list(coll.find({}))
        n = len(docs)
        fresh = stale = miss = v2 = 0
        checked = []
        for d in docs:
            age = _age_days(d.get("settlement_date"))
            if age is None:
                miss += 1
            elif age > SI_STALE_DAYS:
                stale += 1
            else:
                fresh += 1
            if d.get("v") == 2:
                v2 += 1
            if d.get("checked_settlement"):
                checked.append(str(d["checked_settlement"])[:10])
        print("short_interest(%s): %d docs, %d fresh (<=%dd), %d stale, %d no-record"
              % (SI_COLL, n, fresh, SI_STALE_DAYS, stale, miss))
        print("short_interest(%s): %d v2 (bulk), %d legacy, max checked_settlement %s"
              % (SI_COLL, v2, n - v2, max(checked) if checked else None))
        return 0

    if cmd != "warm-si":
        print("usage: python -m short_interest.client warm-si [--dry-run] [--force] "
              "| warm-si --per-symbol [...] | show-si")
        return 2

    force = "--force" in args

    per_symbol = any(f in args for f in ("--per-symbol", "--symbols", "--all-passers"))
    if not per_symbol:
        try:
            from sepa import universe       # function-local: see the docstring
            scope = list(universe.load_universe("full") or [])
        except Exception as exc:                               # noqa: BLE001
            log.warning("short_interest(bulk): universe unavailable: %s", type(exc).__name__)
            scope = []
        res = warm_short_interest_bulk(scope=scope, db=db, force=force,
                                       dry_run="--dry-run" in args)
        print("short_interest(bulk%s): latest %s prior %s, %d provider calls, rows %d/%d, "
              "%d written, %d misses, %d kept, %d deferred, skipped=%s, error=%s"
              % (" DRY-RUN" if "--dry-run" in args else "", res["latest"], res["prior"],
                 res["provider_calls"], res["rows_latest"], res["rows_prior"],
                 res["written"], res["misses"], res["kept"], res["deferred"],
                 res["skipped_reason"],
                 res["error"]))
        return 0 if not res["error"] else 1

    sleep_sec = 0.25
    if "--sleep" in args:
        try:
            sleep_sec = float(args[args.index("--sleep") + 1])
        except (IndexError, ValueError):
            sleep_sec = 0.25

    syms: list = []
    if "--symbols" in args:
        try:
            syms = [s.strip().upper()
                    for s in args[args.index("--symbols") + 1].split(",") if s.strip()]
        except IndexError:
            syms = []
    if not syms:
        if "--all-passers" in args:
            # Every passer off the latest scan, by the SAME rule the board uses
            # (buyable_verdict._bonde_pillar) — never a second pass rule here.
            from sepa import scanner, buyable_verdict as BV
            scan = scanner.load_latest() or {}
            syms = sorted({str(r.get("symbol") or "").upper()
                           for r in (scan.get("all_results") or [])
                           if r.get("symbol")
                           and BV._bonde_pillar(r).get("passed") is True})
        else:
            from sepa import bonde          # function-local: see the docstring
            syms = bonde.symbols(db=db)

    res = warm_short_interest(syms, db=db, sleep_sec=sleep_sec, force=force)
    print("short_interest: %d symbols, %d fetched, %d written, %d skipped, %d failed, %d kept"
          % (res["n"], res["fetched"], res["written"], res["skipped"], res["failed"],
             res["kept"]))
    return 0


if __name__ == "__main__":                                  # pragma: no cover
    raise SystemExit(_main())
