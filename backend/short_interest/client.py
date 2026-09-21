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
        log.warning("short_interest(SI): fetch failed for %s: %s", symbol, exc)
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
            log.debug("short_interest(shares): %s failed: %s", sym, exc)
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


def warm_short_interest(symbols, db=None, sleep_sec: float = 0.25,
                        force: bool = False) -> dict:
    """Fetch + store short interest for `symbols`. Network, cron-only.

    TWO Massive calls per name, so it sleeps between names and skips anything
    fetched within `SI_WARM_TTL_SEC` unless `force`. A `None` answer is WRITTEN
    as a remembered miss (`settlement_date: None`) so the next warm does not
    re-pay for a name the provider has no record for, and the board can tell
    "never warmed" from "warmed, no record". Never raises.
    """
    syms = []
    for s in symbols or []:
        s = str(s or "").strip().upper()
        if s and s not in syms:
            syms.append(s)
    res = {"n": len(syms), "fetched": 0, "written": 0, "skipped": 0, "failed": 0}
    coll = _si_coll(db)
    if coll is None or not syms:
        return res

    fresh = set()
    if not force:
        cutoff = time.time() - SI_WARM_TTL_SEC
        try:
            fresh = {d["_id"] for d in coll.find(
                {"_id": {"$in": syms}, "fetched_at": {"$gte": cutoff}}, {"_id": 1})}
        except Exception as exc:                               # noqa: BLE001
            log.warning("short_interest: warm freshness read failed: %s", exc)
            fresh = set()

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


def _main(argv=None) -> int:
    """`python -m short_interest.client warm-si [--all-passers] [--force]
    [--symbols A,B,C] [--sleep 0.25] | show-si`.

    Default scope is the Bonde board's shown names (≤260). `--all-passers`
    widens to every Bonde-pillar passer off the latest scan (~1,051 names, so
    ~35 min at the default sleep — run it detached, off-RTH).

    `from sepa import bonde` lives INSIDE this function on purpose: the board
    path is sepa.bonde → sepa.bonde_picks → (inside attach) short_interest.client,
    so a module-level import here would close the cycle.
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
        fresh = stale = miss = 0
        for d in docs:
            age = _age_days(d.get("settlement_date"))
            if age is None:
                miss += 1
            elif age > SI_STALE_DAYS:
                stale += 1
            else:
                fresh += 1
        print("short_interest(%s): %d docs, %d fresh (<=%dd), %d stale, %d no-record"
              % (SI_COLL, n, fresh, SI_STALE_DAYS, stale, miss))
        return 0

    if cmd != "warm-si":
        print("usage: python -m short_interest.client warm-si|show-si")
        return 2

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

    res = warm_short_interest(syms, db=db, sleep_sec=sleep_sec,
                              force="--force" in args)
    print("short_interest: %d symbols, %d fetched, %d written, %d skipped, %d failed"
          % (res["n"], res["fetched"], res["written"], res["skipped"], res["failed"]))
    return 0


if __name__ == "__main__":                                  # pragma: no cover
    raise SystemExit(_main())
