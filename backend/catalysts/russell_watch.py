"""Russell inclusion watch — who is ABOUT to be added, so entries can be
tracked before index funds have to buy.

Ajay 2026-09-01, off the EMAT chatter ("no Russell membership to both the
3000 and 2000 in the same cycle"): "can you check if there are more stock
like about to get added to russel 2000 or 1000 ... so we can track those
entries."

Why this is tradeable at all: additions force benchmark-tracking funds to
buy at reconstitution, and anticipatory buying front-runs the effective
date. FTSE Russell moved to SEMI-ANNUAL reconstitution starting 2026 —
June plus a new November cycle (rank day around end-September, effective
late November) — so the September cap snapshot is what November adds are
judged on. Dates are stated as context, not computed: verify the current
schedule on ftserussell.com before trading it.

METHOD (approximation, uncited — NOT FTSE's actual rules):
  FTSE ranks by float-adjusted total market cap with banding hysteresis,
  IPO windows and float/pricing hurdles. We approximate with plain
  market cap (shares_outstanding x live price, sepa/volume_movers
  shares_for cache) against the CURRENT members' cap distribution:

    * R2000 ADD candidate:   not in the R3000 baseline, cap >= the p25 cap
      of current R2000 members (comfortably inside the band, not scraping
      the floor).
    * R1000 PROMOTION cand.: in R2000 baseline, cap >= the p10 cap of
      current R1000 members. Promotions are flagged with the flow caveat:
      more index money tracks R2000 than R1000, so a promotion is usually
      NET SELLING by trackers, not buying.

  Membership baseline = the iShares XLS snapshots in sepa/data (manual
  downloads — iShares blocks programmatic fetch). The payload carries the
  baseline file date; a name added since that date (EMAT) will wrongly
  appear as a candidate until the files are re-downloaded.

Coverage is honest and incremental: caps come from the weekly shares
cache, topped up with at most MAX_FRESH_FETCHES yfinance lookups per
build, so the first build states its coverage and the cache warms with
use. Cached in Mongo for CACHE_TTL_SEC.
"""
from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

log = logging.getLogger("catalysts.russell_watch")

CACHE_TTL_SEC = 6 * 3600
MAX_FRESH_FETCHES = 200          # new yfinance share lookups per build
MIN_DOLLAR_VOL = 2_000_000       # skip untradeable names — this tracks ENTRIES
ADD_PCTL = 25                    # R2000 add: cap >= p25 of current R2000 caps
PROMO_PCTL = 10                  # R1000 promo: cap >= p10 of current R1000 caps
MAX_ROWS = 40

# Names we KNOW are non-US companies (Russell requires US incorporation/HQ;
# we cannot check that from the data we have, so obvious foreign large names
# are excluded by hand). Conservative: only names we are sure about — the
# method note owns the rest of the leakage.
NON_US_BLOCKLIST = frozenset({
    "ASML", "BABA", "TSM", "SONY", "SAP", "TM", "SHOP", "MELI",
    "RY", "BMO", "BNS", "CM", "ENB", "CNQ", "BTE", "AEM", "BN", "SU", "TRP",
    "BB", "DOO", "HIMX", "ASX", "UMC", "GOLD", "WCN", "TRI", "CP", "CNI",
})


def _pctl(sorted_vals: list, p: float) -> Optional[float]:
    """Percentile by nearest-rank on a PRE-SORTED ascending list. Pure."""
    if not sorted_vals:
        return None
    k = max(0, min(len(sorted_vals) - 1, int(round(p / 100.0 * (len(sorted_vals) - 1)))))
    return float(sorted_vals[k])


def classify(symbol: str, cap: Optional[float], in_r1000: bool, in_r3000: bool,
             r2000_p25: Optional[float], r1000_p10: Optional[float]) -> Optional[dict]:
    """Which watch board (if any) one name belongs on. Pure — the whole
    decision table, so the EMAT-shaped false positive is at least visible:
    a name added AFTER the baseline files still classifies as add_r2000.

    The add window is BOUNDED above: an outsider already sized for the
    R1000 is almost never a missed add — it is a foreign/ineligible name
    (the first live run's "top adds" were ASML, BABA and four Canadian
    banks; Russell only takes US companies, which we cannot check
    directly). R2000 adds must be R2000-SIZED."""
    if not cap or cap <= 0:
        return None
    if in_r1000:
        return None                              # already at the top table
    if in_r3000:
        # current R2000 member — promotion watch only
        if r1000_p10 and cap >= r1000_p10:
            return {"board": "promote_r1000", "cap": cap}
        return None
    if r2000_p25 and r1000_p10 and r2000_p25 <= cap < r1000_p10:
        return {"board": "add_r2000", "cap": cap}
    return None


def _shares_cached_only(sym: str) -> Optional[dict]:
    """shares_cache read WITHOUT a yfinance fallback — coverage counting."""
    try:
        from sepa import volume_movers as vm
        coll = vm._shares_coll()
        if coll is None:
            return None
        doc = coll.find_one({"_id": sym})
        if doc and doc.get("shares_outstanding"):
            return {"shares_outstanding": doc["shares_outstanding"]}
    except Exception:
        pass
    return None


def _candidate_pool() -> list[str]:
    """Names worth watching: the SEPA universe + day-trade pool + the
    R3000 baseline itself (for promotions). Bounded and liquid-ish."""
    pool: set = set()
    try:
        from sepa import universe as U
        pool.update(U.load_universe())
    except Exception as exc:
        log.warning("russell_watch: sepa universe unavailable: %s", exc)
    try:
        from daytrading import universe as DU
        pool.update(n["symbol"] for n in DU.day_trade_universe("aggressive")["names"])
    except Exception:
        pass
    # the catalyst scan is where EMAT-shaped names first show up — without
    # this the board missed the one add candidate the whole page was about.
    # Read the Mongo doc RAW: the scan cache's freshness TTL (minutes) is
    # about price data; membership candidacy is fine with an hours-old list,
    # and _cache_get() returning None overnight is exactly how EMAT vanished.
    hot: list = []
    try:
        from . import api as cat_api
        coll = cat_api._cache_coll()
        doc = coll.find_one({"_id": "scan_latest"}) if coll is not None else None
        for c in ((doc or {}).get("payload", {}) or {}).get("candidates", []) or []:
            t = (c.get("ticker") or c.get("symbol") or "").upper()
            if t and t not in pool:
                hot.append(t)
    except Exception:
        pass
    ordered = [s for s in hot if s not in NON_US_BLOCKLIST] + \
              sorted(s for s in pool if s not in NON_US_BLOCKLIST)
    seen: set = set()
    return [s for s in ordered if not (s in seen or seen.add(s))]


def _baseline() -> tuple[set, set, Optional[str]]:
    """(r1000, r3000, baseline_date) from the iShares snapshots."""
    from sepa import universe as U
    r1000 = set(U.fetch_russell1000())
    r3000 = set(U.fetch_russell3000())
    date = None
    try:
        p = U._LOCAL_IWB_PATH
        date = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(p)))
    except Exception:
        pass
    return r1000, r3000, date


def _cache_coll():
    try:
        from pymongo import MongoClient
        c = MongoClient(os.environ.get("MONGO_URL", "mongodb://mongo:27017"),
                        serverSelectionTimeoutMS=2000)
        return c.get_database("cheetah")["russell_watch_cache"]
    except Exception:
        return None


_REFRESHING = {"on": False}


def build(force: bool = False) -> dict:
    """Stale-while-revalidate: a cold build takes minutes (bulk snapshots +
    yfinance share fetches) and the proxy kills ~100s requests, so an
    EXPIRED cache is served immediately with `stale: true` while one
    daemon thread rebuilds. Only the first-ever call blocks."""
    coll = _cache_coll()
    if coll is not None and not force:
        try:
            doc = coll.find_one({"_id": "board"})
            if doc:
                fresh = (time.time() - doc.get("ts", 0)) < CACHE_TTL_SEC
                if fresh:
                    return doc["payload"]
                if not _REFRESHING["on"]:
                    import threading
                    _REFRESHING["on"] = True

                    def _rebuild():
                        try:
                            _build_now()
                        except Exception as exc:      # pragma: no cover
                            log.warning("russell_watch refresh failed: %s", exc)
                        finally:
                            _REFRESHING["on"] = False
                    threading.Thread(target=_rebuild, daemon=True).start()
                return {**doc["payload"], "stale": True,
                        "stale_note": "refreshing in the background — reload in a few minutes"}
        except Exception:
            pass
    return _build_now()


def _build_now() -> dict:
    coll = _cache_coll()

    from sepa import volume_movers as vm
    from supply_demand import flow

    r1000, r3000, baseline_date = _baseline()
    r2000 = r3000 - r1000
    pool = _candidate_pool()          # catalyst-scan names FIRST — they get
    watchable = [s for s in pool if s not in r1000]   # the fresh-fetch budget
    universe_all = sorted(set(watchable) | r3000)

    # one bulk pass for live prices (250-chunks, same as every board)
    snaps: dict = {}
    for i in range(0, len(universe_all), 250):
        try:
            snaps.update(flow._fetch_massive_bulk(universe_all[i:i + 250]) or {})
        except Exception:
            pass

    def cap_of(sym: str, allow_fetch: bool) -> Optional[float]:
        snap = snaps.get(sym) or {}
        px = snap.get("price")
        if not px:
            return None
        sh = _shares_cached_only(sym)
        if sh is None and allow_fetch:
            sh = vm.shares_for(sym)
        if not sh or not sh.get("shares_outstanding"):
            return None
        return float(sh["shares_outstanding"]) * float(px)

    # member cap distributions — cached shares only (members are the
    # yardstick; skewing the yardstick with partial fresh fetches is worse
    # than a smaller sample)
    r2000_caps = sorted(c for c in (cap_of(s, False) for s in r2000) if c)
    r1000_caps = sorted(c for c in (cap_of(s, False) for s in r1000) if c)
    r2000_p25 = _pctl(r2000_caps, ADD_PCTL)
    r1000_p10 = _pctl(r1000_caps, PROMO_PCTL)

    fresh_budget = MAX_FRESH_FETCHES
    rows: list[dict] = []
    no_cap = 0
    for sym in watchable:
        snap = snaps.get(sym) or {}
        dv = snap.get("dollar_volume") or 0
        if dv < MIN_DOLLAR_VOL:
            continue
        allow = fresh_budget > 0
        had = _shares_cached_only(sym) is not None
        cap = cap_of(sym, allow)
        if not had and allow:
            fresh_budget -= 1
        if cap is None:
            no_cap += 1
            continue
        hit = classify(sym, cap, sym in r1000, sym in r3000, r2000_p25, r1000_p10)
        if hit:
            rows.append({
                "symbol": sym,
                "board": hit["board"],
                "market_cap": round(cap),
                "price": snap.get("price"),
                "change_pct": snap.get("change_pct"),
                "dollar_volume": dv,
            })

    adds = sorted((r for r in rows if r["board"] == "add_r2000"),
                  key=lambda r: -r["market_cap"])[:MAX_ROWS]
    promos = sorted((r for r in rows if r["board"] == "promote_r1000"),
                    key=lambda r: -r["market_cap"])[:MAX_ROWS]

    payload = {
        "adds_r2000": adds,
        "promotions_r1000": promos,
        "bands": {
            "r2000_p25_cap": r2000_p25, "r1000_p10_cap": r1000_p10,
            "r2000_sampled": len(r2000_caps), "r1000_sampled": len(r1000_caps),
        },
        "coverage": {
            "pool": len(watchable), "no_cap_data": no_cap,
            "fresh_fetch_budget_left": fresh_budget,
            "note": ("cap = shares x live price from the weekly shares cache; "
                     "coverage grows as the cache warms"),
        },
        "baseline": {
            "files_date": baseline_date,
            "r1000": len(r1000), "r3000": len(r3000),
            "note": ("membership from the iShares XLS snapshots in sepa/data — "
                     "manual downloads; a name added since that date still "
                     "shows as a candidate until the files are refreshed"),
        },
        "method_note": ("Approximation, uncited: plain market cap vs current "
                        "member cap percentiles (add: p25 of R2000 <= cap < p10 "
                        "of R1000 — oversized outsiders are usually foreign/"
                        "ineligible, not missed adds; promote: >= p10 of R1000). "
                        "FTSE uses float-adjusted cap with banding, IPO windows, "
                        "float hurdles and a US-company requirement this proxy "
                        "cannot check. 2026 begins SEMI-ANNUAL reconstitution: "
                        "the second 2026 recon is effective 2026-09-21 (per the "
                        "EMAT preliminary-inclusion announcement) and FTSE's "
                        "preliminary add lists are already published — check "
                        "ftserussell.com for the official lists; this board is "
                        "the cap-screen guess at them. Promotions to R1000 are "
                        "usually NET SELLING by trackers (more money follows "
                        "R2000). Not advice."),
        "as_of": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if coll is not None:
        try:
            coll.update_one({"_id": "board"},
                            {"$set": {"ts": time.time(), "payload": payload}},
                            upsert=True)
        except Exception:
            pass
    return payload
