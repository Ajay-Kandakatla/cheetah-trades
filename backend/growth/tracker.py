"""🚀 Explosive Growth tracker — the 100/100 screen.

Ajay 2026-09-11: *"can you verify all the sectors and tell me which new ones
are blowing up? in Sales by 100% or more and 100 growth Quarter over Quarter.
Hot sector top growth stocks I need the same rules in demand zone for these. I
wanna know when ever these are in demand, separately just trackers. I wanna
keep adding during instituional orderblocks are present for these... this is
outside of regular supply and demand"* — and *"remove the 700M rule for this
page"*, and *"I want real growing stocks like AXTI and SABR with genuine
sales"*.

THE SCREEN (all four, on the latest reported quarter):
  1. sales YoY            >= MIN_SALES_GROWTH_PCT   (100%)
  2. quarterly EPS YoY    >= MIN_EPS_GROWTH_PCT     (100%)
  3. the PRIOR quarter's sales YoY > MIN_PRIOR_SALES_PCT (0%) — one quarter is
     a comparison artifact; two in a row is a business. This is the gate that
     separates a real ramp from an easy year-ago base.
  4. a known last price (so the row can be read at all)

NO MARKET-CAP FLOOR — his explicit call for THIS page. Every other board in
the app filters to cap >= $700M; this one does not, because a name doubling
sales is often small before it is big and he wants to see it early. The cap
floor still applies at the BROKER: trading/safety_floor.py blocks a sub-$2
quote and a known sub-$700M cap on every entry lane. So a name can legitimately
appear HERE and be refused THERE. That is not a bug and it must not be silent:
every row carries `warnings` saying exactly that, which is the *"or warn me"*
half of his 2026-09-11 ask.

UNIVERSE — `broad` (3,703: Russell 3000 + micro-cap IWC + ETFs), read through
the weekly research cache. NOT "massive": that is not a real load_universe mode
and silently falls back to 157 curated names (verified 2026-09-11). The hourly
scan and every alert path run `full` (2,652), which is NARROWER than this board
— so a name can screen here and still have no zone bands. `zone_missing` says
so on the row rather than pretending the demand read is simply empty.

THE DEMAND TRIGGER is the one gate that measured: the band floor never pierced
(`alert_gates.floor_held_gate`, +8.6pp win rate, n=31,861). Order blocks are a
DISPLAY FLAG only — the 2026-09-04 ICT study measured +0.03R over 6,004 signals
against placebo, so nothing here may gate on one.

NOTHING ON THIS BOARD IS BACKTESTED. The 100/100 screen has never been measured
forward. It is a discovery list.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

log = logging.getLogger("growth.tracker")

MIN_SALES_GROWTH_PCT = 100.0     # latest quarter, YoY
MIN_EPS_GROWTH_PCT = 100.0       # latest quarter, YoY
MIN_PRIOR_SALES_PCT = 0.0        # the quarter before must also be growing
MIN_CAP_USD = None               # DELIBERATELY none — "remove the 700M rule for this page"

UNIVERSE_MODE = "broad"
COLL = "growth_board"
MAX_ROWS = 300                   # a screen this strict returns tens, not thousands

# Warning tiers — this board has no cap floor, so it says out loud what the
# entry path will refuse. Kept in sync with trading/safety_floor.py by
# tests/test_growth_tracker.py::test_warnings_quote_the_real_entry_floors.
from trading import safety_floor as SF                                 # noqa: E402

SMALL_CAP_WARN_USD = SF.MIN_CAP_USD          # $700M — the app-wide floor
MICRO_CAP_WARN_USD = 100_000_000.0           # $100M — "one buyer is the market"


def _f(v) -> Optional[float]:
    """float or None; NaN and inf are None (a NaN passes every >=)."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (f != f or f in (float("inf"), float("-inf"))) else f


def _db():
    try:
        from portfolio.store import _get_db
        return _get_db()
    except Exception as exc:                                   # noqa: BLE001
        log.warning("growth.tracker: no mongo: %s", exc)
        return None


# --------------------------------------------------------------------------
# The screen
# --------------------------------------------------------------------------
def qualifies(fundamentals: Optional[dict]) -> tuple[bool, dict]:
    """(passes, legs). `legs` always carries every number the row displays,
    pass or fail, so a near-miss is explainable without a second read."""
    f = fundamentals or {}
    sales = f.get("sales") or {}
    eq = ((f.get("earnings_quality") or {}).get("components")) or {}

    legs = {
        "sales_growth_pct": _f(sales.get("growth_yoy_pct")),
        "sales_prior_pct": _f(sales.get("prior_yoy_pct")),
        "sales_tier": sales.get("tier"),
        "sales_accelerating": bool(sales.get("accelerating")),
        "consecutive_growth_q": sales.get("consecutive_growth_q"),
        "q_eps_growth_pct": _f(f.get("q_eps_growth_pct")),
        "eps_prior_pct": _f(eq.get("eps_prior_yoy_pct")),
        "npm_latest_pct": _f(eq.get("npm_latest_pct")),
        "npm_expanding": bool(eq.get("npm_expanding")),
        "inst_ownership_pct": _f(f.get("inst_ownership_pct")),
    }
    s, e, p = legs["sales_growth_pct"], legs["q_eps_growth_pct"], legs["sales_prior_pct"]
    ok = (s is not None and s >= MIN_SALES_GROWTH_PCT
          and e is not None and e >= MIN_EPS_GROWTH_PCT
          and p is not None and p > MIN_PRIOR_SALES_PCT)
    return ok, legs


def row_warnings(price, cap, dollar_vol, promo_tagged: bool,
                 zone_missing: bool) -> list[str]:
    """The "or warn me" half. This board has NO cap floor, so it must say
    plainly which rows the broker will refuse and which are whale-movable."""
    out = []
    p, c, d = _f(price), _f(cap), _f(dollar_vol)

    if p is not None and p < SF.MIN_SHARE_PRICE:
        out.append("⛔ $%.2f is under the $%.2f entry floor — the engine will "
                   "REFUSE to buy this" % (p, SF.MIN_SHARE_PRICE))
    if c is None:
        out.append("⚠️ market cap unknown")
    elif c < MICRO_CAP_WARN_USD:
        out.append("⛔ $%.0fM cap — micro-cap, one buyer is the market, and "
                   "the engine will REFUSE to buy it" % (c / 1e6))
    elif c < SMALL_CAP_WARN_USD:
        out.append("⛔ $%.0fM cap is under the $%.0fM floor every other board "
                   "uses — the engine will REFUSE to buy it"
                   % (c / 1e6, SMALL_CAP_WARN_USD / 1e6))

    liq = SF.liquidity_warning(d)
    if liq:
        out.append("⚠️ " + liq)
    if promo_tagged:
        out.append("⚠️ promo-tagged — a pump account has pushed this name; the "
                   "tag is promotion, never foresight")
    if zone_missing:
        out.append("⚠️ no zone bands — this name is outside the scan universe, "
                   "so the demand read is blank, not empty")
    return out


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------
def _promo_tagged(symbols: Iterable[str]) -> set:
    try:
        from catalysts.promo_circuit import _coll
        coll = _coll("promo_circuit_tags")
        if coll is None:
            return set()
        syms = [s.upper() for s in symbols]
        return {(d.get("symbol") or d.get("_id") or "").upper()
                for d in coll.find({"$or": [{"symbol": {"$in": syms}},
                                            {"_id": {"$in": syms}}]},
                                   {"symbol": 1})}
    except Exception as exc:                                   # noqa: BLE001
        log.debug("growth.tracker: promo tags unavailable: %s", exc)
        return set()


def _sectors(symbols) -> dict:
    """{SYM: (sector, industry)} from the companies collection.

    Ajay 2026-09-11: "I wanna see the secorts in the growth.. To show that only
    some are growing." This is the GICS axis the 🔥 Hottest tab groups by —
    NOT supply_demand/sectors.py, which is the curated thematic list and shares
    no code path with it.

    TRAP: `companies` is keyed by an ObjectId _id with the ticker in `symbol`.
    Querying it by _id returns zero docs with no error."""
    db = _db()
    if db is None:
        return {}
    try:
        return {(d.get("symbol") or "").upper(): (d.get("sector"), d.get("industry"))
                for d in db.companies.find(
                    {"symbol": {"$in": list(symbols)}},
                    {"symbol": 1, "sector": 1, "industry": 1})
                if d.get("symbol")}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("growth.tracker: sector read failed: %s", exc)
        return {}


def _caps(symbols) -> dict:
    try:
        from sepa import volume_movers as vm
        coll = vm._shares_coll()
        if coll is None:
            return {}
        return {d["_id"]: _f(d.get("market_cap"))
                for d in coll.find({"_id": {"$in": list(symbols)}},
                                   {"market_cap": 1})}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("growth.tracker: shares cache read failed: %s", exc)
        return {}


def screen(limit: int = MAX_ROWS) -> list[dict]:
    """Every name that clears the 100/100 screen, richest sales growth first.

    Reads the weekly research cache only — never a provider, never a price
    fetch per symbol. A row whose fundamentals are missing simply does not
    qualify; it is never assumed."""
    db = _db()
    if db is None:
        return []
    docs = list(db.sepa_research_cache.find(
        {}, {"symbol": 1, "name": 1, "fundamentals": 1, "liquidity": 1,
             "last_bar_date": 1, "cached_at": 1}))

    hits = []
    for d in docs:
        sym = (d.get("symbol") or d.get("_id") or "").upper()
        if not sym:
            continue
        ok, legs = qualifies(d.get("fundamentals"))
        if not ok:
            continue
        hits.append((sym, d, legs))

    syms = [h[0] for h in hits]
    caps = _caps(syms)
    secs = _sectors(syms)
    promo = _promo_tagged(syms)
    prices = _prices(syms)

    rows = []
    for sym, d, legs in hits:
        liq = d.get("liquidity") or {}
        dv = _f(liq.get("avg_dollar_vol"))
        sh = _f(liq.get("avg_shares"))
        # 50-day average price as the fallback: the research cache has no price
        # column, and dv/sh is exact from the two fields it does store.
        px = prices.get(sym) or ((dv / sh) if (dv and sh) else None)
        cap = caps.get(sym)
        zone = _zone_read(sym)
        rows.append({
            "symbol": sym,
            "name": d.get("name"),
            "sector": secs.get(sym, (None, None))[0],
            "industry": secs.get(sym, (None, None))[1],
            "price": round(px, 2) if px else None,
            "market_cap": cap,
            "avg_dollar_vol": dv,
            "liquid": bool(dv is not None and dv >= SF.MIN_DOLLAR_VOL),
            "promo_tagged": sym in promo,
            "as_of": d.get("last_bar_date") or d.get("cached_at"),
            "zone": zone,
            "warnings": row_warnings(px, cap, dv, sym in promo,
                                     zone.get("missing", False)),
            **legs,
        })
    rows.sort(key=lambda r: (-(r.get("sales_growth_pct") or 0.0), r["symbol"]))
    return rows[:limit]


def _prices(symbols) -> dict:
    """Last CLOSED bar close per symbol from the shared price cache. Best
    effort — a miss falls back to the derived 50-day average."""
    out = {}
    try:
        from sepa import prices as P
        for sym in symbols:
            try:
                df = P.load_prices(sym)
                if df is not None and len(df):
                    out[sym] = float(df["close"].iloc[-1])
            except Exception:                                  # noqa: BLE001,S112
                continue
    except Exception as exc:                                   # noqa: BLE001
        log.debug("growth.tracker: price cache unavailable: %s", exc)
    return out


def _zone_read(symbol: str) -> dict:
    """The demand half: is price in a demand band whose floor is INTACT.

    `intact` is the only gate that measured (+8.6pp, n=31,861). Order-block
    presence rides along as a DISPLAY flag and decides nothing — the ICT study
    measured +0.03R over 6,004 signals, i.e. nothing."""
    empty = {"missing": True, "in_band": False, "intact": None,
             "band": None, "order_block": False}
    db = _db()
    if db is None:
        return empty
    try:
        doc = db.zone_store.find_one({"symbol": symbol.upper()},
                                     sort=[("date", -1)])
    except Exception as exc:                                   # noqa: BLE001
        log.debug("growth.tracker: zone read failed for %s: %s", symbol, exc)
        return empty
    if not doc:
        return empty

    px = _f(doc.get("prev_close"))
    bands = [b for b in (doc.get("bands") or []) if b.get("kind") == "demand"]
    band = None
    if px is not None:
        for b in bands:
            lo, hi = _f(b.get("lo")), _f(b.get("hi"))
            if lo is not None and hi is not None and lo <= px <= hi:
                band = b
                break
    out = {"missing": False, "in_band": band is not None, "intact": None,
           "band": band, "order_block": False, "zone_date": doc.get("date")}
    if band is not None:
        try:
            from supply_demand import alert_gates as AG
            # READ FIRST, THEN GATE — and keep the two apart. (2026-09-12)
            #
            # `floor_held_gate` FAILS CLOSED by design: an unreadable price
            # frame returns plain False, byte-identical to a real pierce
            # ("Unreadable = False (fails closed)", alert_gates.floor_held_gate).
            # That is exactly right for a PHONE ALERT and must not change.
            #
            # It is wrong for a BOARD. `bool(floor_held_gate(...))` collapsed
            # unknown into False, so a name whose prices simply did not load
            # was printed as "in band, pierced" — a fact nobody checked — and
            # the 2026-09-12 demand sort then ranked it ABOVE every row the
            # board honestly marks unknown. It matters on the only scheduled
            # run there is: `growth build` fires Sunday 09:00 ET, ~40h after
            # Friday's last price-cache write, and prices.CACHE_TTL_SEC is 20h,
            # so every symbol misses both cache tiers and any failed refetch
            # lands here.
            #
            # So the READ decides whether we know anything, and only then does
            # the gate decide the answer. `read=` is passed through so this
            # costs no second fetch. Nothing downstream is loosened: `intact`
            # stays falsy when unknown, so growth.alerts still refuses it.
            r = AG.sweep_read(band, symbol)
            out["intact"] = (bool(AG.floor_held_gate(band, symbol, read=r))
                             if isinstance(r, dict) else None)
        except Exception as exc:                               # noqa: BLE001
            log.debug("growth.tracker: intact read failed for %s: %s", symbol, exc)
    return out


SEEN_COLL = "growth_seen"
# A name counts as NEWLY FOUND for this long after it first appears on the
# board. The board rebuilds Sundays, so a month is about four builds — long
# enough that a fresh print is still "new" when he looks mid-week.
NEW_GROWTH_DAYS = 30


def _record_seen(rows: list, db=None) -> None:
    """Remember when each name FIRST appeared on the growth board.

    Ajay 2026-09-12 wants a breakout at stage 1 or 3 allowed when the name is a
    NEWLY FOUND explosive grower — and nothing recorded that. The board doc is
    `_id: "latest"`, latest-only, so the moment a build finished there was no
    way to tell a name that arrived today from one that has sat there for
    months. Same gap the rotation strip had.

    A `__meta__` row stores when tracking itself began, because without it EVERY
    name looks new on the first build — and "unknown" must never read as the
    favourable state."""
    db = db if db is not None else _db()
    if db is None:
        return
    # ONE stamp for the meta row AND every symbol: the first build then has
    # first_seen == tracking_since exactly, and `newly_found`'s strict `>`
    # excludes that cohort. Two clock reads would leave microseconds of
    # drift and badge the entire first board as new.
    now = datetime.now(timezone.utc).isoformat()
    try:
        coll = db[SEEN_COLL]
        coll.update_one({"_id": "__meta__"},
                        {"$setOnInsert": {"tracking_since": now}}, upsert=True)
        for r in rows:
            sym = r.get("symbol")
            if sym:
                coll.update_one({"_id": str(sym).upper()},
                                {"$set": {"last_seen": now},
                                 "$setOnInsert": {"first_seen": now}},
                                upsert=True)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("growth.tracker: first-seen write failed: %s", exc)


def newly_found(days: int = NEW_GROWTH_DAYS, db=None) -> set:
    """Symbols that ARRIVED on the board within `days`.

    A name present at the very first build is NOT new — it is merely the first
    thing we ever saw, which is a different statement. Returns an empty set
    until tracking has actually observed an arrival."""
    db = db if db is not None else _db()
    if db is None:
        return set()
    try:
        coll = db[SEEN_COLL]
        meta = coll.find_one({"_id": "__meta__"}) or {}
        since = meta.get("tracking_since")
        if not since:
            return set()
        cut = (datetime.now(timezone.utc) - timedelta(days=int(days))).isoformat()
        floor = max(str(since), cut)
        return {str(d["_id"]).upper()
                for d in coll.find({"_id": {"$ne": "__meta__"},
                                    "first_seen": {"$gt": floor}}, {"_id": 1})}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("growth.tracker: newly-found read failed: %s", exc)
        return set()


def build(limit: int = MAX_ROWS) -> dict:
    """Screen and persist. The weekly refresh calls this; the API reads the
    stored doc so a page load never runs the screen."""
    rows = screen(limit=limit)
    _record_seen(rows)
    doc = {
        "_id": "latest",
        "built_at": datetime.now(timezone.utc),
        "rows": rows,
        "n": len(rows),
        "screen": {"min_sales_growth_pct": MIN_SALES_GROWTH_PCT,
                   "min_eps_growth_pct": MIN_EPS_GROWTH_PCT,
                   "min_prior_sales_pct": MIN_PRIOR_SALES_PCT,
                   "cap_floor": MIN_CAP_USD,
                   "universe_mode": UNIVERSE_MODE},
    }
    db = _db()
    if db is not None:
        try:
            db[COLL].replace_one({"_id": "latest"}, doc, upsert=True)
        except Exception as exc:                               # noqa: BLE001
            log.warning("growth.tracker: persist failed: %s", exc)
    return doc


def board() -> dict:
    """The stored board, or an empty one. Never runs the screen inline."""
    db = _db()
    if db is None:
        return {"rows": [], "n": 0, "built_at": None}
    try:
        doc = db[COLL].find_one({"_id": "latest"})
    except Exception as exc:                                   # noqa: BLE001
        log.warning("growth.tracker: board read failed: %s", exc)
        return {"rows": [], "n": 0, "built_at": None}
    return doc or {"rows": [], "n": 0, "built_at": None}
