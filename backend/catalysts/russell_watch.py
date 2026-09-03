"""Russell inclusion watch — who is ABOUT to be added, so entries can be
tracked before index funds have to buy.

Ajay 2026-09-01, off the EMAT chatter ("no Russell membership to both the
3000 and 2000 in the same cycle"): "can you check if there are more stock
like about to get added to russel 2000 or 1000 ... so we can track those
entries."

Why this is tradeable at all: additions force benchmark-tracking funds to
buy at reconstitution, and anticipatory buying front-runs the effective
date. FTSE Russell moved to SEMI-ANNUAL reconstitution starting 2026 —
June plus a December cycle (rank day 30-Oct-2026, effective after the
close 11-Dec-2026; FTSE moved it from November on 05-Nov-2025). Recent IPOs
are added quarterly (Q3 2026: rank 31-Jul, prelim 21-Aug, effective
21-Sep). The calendar lives in SCHEDULE below with its sources; `add_event`
maps each candidate to the event that would carry it in.

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
from datetime import date, datetime, timezone
from typing import Optional

log = logging.getLogger("catalysts.russell_watch")

# ── When would an add actually happen? ───────────────────────────────────────
# Ajay 2026-09-02: "add the dates of these candidates additions". FTSE's
# PUBLISHED 2026 calendar, held as data with its sources — never a rule of
# thumb. After the last loaded event the board says the schedule is not
# loaded rather than guessing at 2027.
#
# Sources (read 2026-09-02):
#  [1] FTSE Russell notice "Russell US Semi-Annual Reconstitution — Schedule
#      Update", 05 Nov 2025: December cycle effective after the close Fri
#      11-Dec-2026 (open of 14-Dec), cap cut-off / rank 30-Oct-26, IPO review
#      period 3 Aug–30 Oct 2026, indicative products 13-Nov-26, lock-down
#      30-Nov-26. research.ftserussell.com/products/index-notices/home/getnotice/?id=2617649
#  [2] lseg.com/en/ftse-russell/russell-reconstitution: June 2026 prelim lists
#      from 22-May, effective after the close 26-Jun-2026; December 2026 rank
#      day 30-Oct, prelim 13-Nov, updates 20-Nov / 27-Nov / 4-Dec, effective
#      after the close 11-Dec-2026.
#  [3] EMAT release, GlobeNewswire 24-Aug-2026: Q3 2026 IPO additions —
#      preliminary lists published 21-Aug-2026, addition effective
#      21-Sep-2026 (i.e. after the close Fri 18-Sep).
#  [4] FTSE Russell FAQ, Russell US Equity Indexes 2026: quarterly IPO rank
#      date = last business day of Jan/Apr/Jul/Oct; from 2026 the December
#      IPO inclusion is folded into the December reconstitution.
SCHEDULE = {
    "verified_on": "2026-09-02",
    "sources": [
        "https://research.ftserussell.com/products/index-notices/home/getnotice/?id=2617649",
        "https://www.lseg.com/en/ftse-russell/russell-reconstitution",
        "https://www.globenewswire.com/news-release/2026/08/24/3349659/0/en/",
    ],
    "events": [
        {"key": "recon_jun_2026", "kind": "reconstitution", "label": "June 2026 reconstitution",
         "rank_day": "2026-04-30", "prelim": "2026-05-22",
         "effective_close": "2026-06-26", "in_index": "2026-06-29"},
        {"key": "ipo_q3_2026", "kind": "ipo_add", "label": "Q3 2026 IPO additions",
         "rank_day": "2026-07-31", "prelim": "2026-08-21",
         "effective_close": "2026-09-18", "in_index": "2026-09-21",
         # window start = the day after the June rank day (inferred; the
         # December window's 3-Aug start in [1] pins the end at 31-Jul)
         "ipo_window": ["2026-05-01", "2026-07-31"]},
        {"key": "recon_dec_2026", "kind": "reconstitution", "label": "December 2026 reconstitution",
         "rank_day": "2026-10-30", "prelim": "2026-11-13",
         "updates": ["2026-11-20", "2026-11-27", "2026-12-04"], "lockdown": "2026-11-30",
         "effective_close": "2026-12-11", "in_index": "2026-12-14",
         "ipo_window": ["2026-08-03", "2026-10-30"]},
    ],
}


def _d(s: str) -> date:
    return date.fromisoformat(s)


def upcoming_events(today: date) -> list[dict]:
    """Events whose effective close is still ahead of `today`, in order."""
    return [e for e in SCHEDULE["events"] if _d(e["effective_close"]) >= today]


def add_event(board: str, listed: Optional[str], today: date) -> Optional[dict]:
    """The published event that would carry this candidate in, and its dates.

    * promote_r1000  — membership moves only at a reconstitution.
    * add_r2000      — an outsider that LISTED inside a quarterly IPO window
                       rides that IPO add; everything else (and IPOs in the
                       December window) waits for the next reconstitution.
    `lists_published` is True once FTSE's preliminary list for that event is
    out: from then on our cap screen is a guess at a list that already exists —
    the row says to check it. None = no loaded event ahead (schedule ran out)."""
    ahead = upcoming_events(today)
    if not ahead:
        return None
    pick = None
    if board == "add_r2000" and listed:
        for e in ahead:
            w = e.get("ipo_window")
            if e["kind"] == "ipo_add" and w and w[0] <= listed <= w[1]:
                pick = e
                break
    if pick is None:
        pick = next((e for e in ahead if e["kind"] == "reconstitution"), None)
    if pick is None:
        return None
    return {
        "key": pick["key"], "kind": pick["kind"], "label": pick["label"],
        "rank_day": pick["rank_day"], "prelim": pick["prelim"],
        "effective_close": pick["effective_close"], "in_index": pick["in_index"],
        "lists_published": _d(pick["prelim"]) <= today,
        "listed": listed,
    }


def _seen_coll():
    try:
        from pymongo import MongoClient
        c = MongoClient(os.environ.get("MONGO_URL", "mongodb://mongo:27017"),
                        serverSelectionTimeoutMS=2000)
        return c.get_database("cheetah")["russell_watch_seen"]
    except Exception:
        return None


def stamp_first_seen(rows: list[dict], prior: Optional[dict], coll, now_iso: str) -> None:
    """`first_seen` = the first build that flagged this (board, symbol).

    The ledger starts today, so names already on the PRIOR cached board are
    seeded with that board's `as_of` (the earliest we can prove), never with
    now. Mongo down → rows carry first_seen=None and the FE prints a dash."""
    prior_at = (prior or {}).get("as_of")
    prior_keys = set()
    for k in ("adds_r2000", "promotions_r1000"):
        for r in (prior or {}).get(k) or []:
            prior_keys.add((r.get("board"), r.get("symbol")))
    for r in rows:
        key = f"{r['board']}:{r['symbol']}"
        seed = prior_at if (r["board"], r["symbol"]) in prior_keys and prior_at else now_iso
        if coll is None:
            r["first_seen"] = None
            continue
        try:
            doc = coll.find_one({"_id": key})
            if doc and doc.get("first_seen"):
                coll.update_one({"_id": key}, {"$set": {"last_seen": now_iso}})
                r["first_seen"] = doc["first_seen"]
            else:
                coll.update_one({"_id": key},
                                {"$set": {"first_seen": seed, "last_seen": now_iso,
                                          "board": r["board"], "symbol": r["symbol"]}},
                                upsert=True)
                r["first_seen"] = seed
        except Exception as exc:
            log.warning("russell_watch: seen ledger for %s failed: %s", key, exc)
            r["first_seen"] = None

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
    prior = None
    if coll is not None:
        try:
            prior = (coll.find_one({"_id": "board"}) or {}).get("payload")
        except Exception:
            prior = None

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

    # When would each one actually go in? Listing date (profile provider,
    # cached forever) decides IPO-window vs reconstitution; the ledger says
    # how long the screen has been flagging it.
    today = datetime.now(timezone.utc).date()
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        from sepa.ipo_age import listing_date
    except Exception:                                       # pragma: no cover
        listing_date = lambda sym: None                     # noqa: E731
    for r in adds:
        r["listed"] = listing_date(r["symbol"])
        r["add_event"] = add_event(r["board"], r["listed"], today)
    for r in promos:
        r["listed"] = None
        r["add_event"] = add_event(r["board"], None, today)
    stamp_first_seen(adds + promos, prior, _seen_coll(), now_iso)

    payload = {
        "adds_r2000": adds,
        "promotions_r1000": promos,
        "schedule": {
            "verified_on": SCHEDULE["verified_on"], "sources": SCHEDULE["sources"],
            "upcoming": upcoming_events(today),
            "note": ("FTSE's published 2026 calendar. An outsider that listed inside a "
                     "quarterly IPO window goes in at that IPO add; everything else, and "
                     "every promotion, waits for the next reconstitution. Once a "
                     "preliminary list is out, this cap screen is a guess at a list that "
                     "already exists — check it on lseg.com/ftse-russell."),
        },
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
                        "cannot check. 2026 begins SEMI-ANNUAL reconstitution "
                        "(June + December); recent IPOs are added quarterly "
                        "(EMAT: Q3 2026 IPO add, preliminary list 2026-08-21, "
                        "effective 2026-09-21 — an IPO add, NOT the second "
                        "reconstitution, which is effective 2026-12-11). This "
                        "board is the cap-screen guess at FTSE's lists. Promotions to R1000 are "
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
