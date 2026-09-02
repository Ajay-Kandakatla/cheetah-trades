"""Supply watch — when does each holding reach SUPPLY (the sell zone)?

Ajay 2026-09-02, with his Fidelity book on screen: "check when is the time
to sell, based on supply and demand — when will they hit supply? Give me a
table in portfolio page and also add alerts."

Per holding: the supply band price meets first going UP (the daily
swing-cluster zones the Chart Maps tabs already print), how far it is in
% and in ATR-days, and a state. Alerts ride on the existing
``position_alert`` kind (his stop/target channel) — no new phone kind —
and fire ONCE per band per day when a holding is inside or within 1% of
its sell zone, pre-market and after-hours included.

Uncited market-structure convention (catalysts/zones family, not SEPA
book logic — see feedback_sepa_book_scope).
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

log = logging.getLogger("portfolio.supply_watch")

NEAR_PCT = 2.0            # <= this under the band bottom -> NEAR
APPROACH_PCT = 5.0        # <= this -> APPROACHING
ALERT_PCT = 1.0           # alert when inside the band or within this of it
CACHE_TTL_SEC = 30 * 60   # zone half; prices re-derive every call
ERROR_RETRY_SEC = 120     # a book whose zone engine missed retries this fast
LIVE_REFRESH_SEC = 60
FRAME_NOTE = "1y frame (252 daily bars)"


def _coll(name: str):
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        return MongoClient(url, serverSelectionTimeoutMS=2000)[db][name]
    except Exception as exc:                                # pragma: no cover
        log.warning("supply_watch mongo unavailable: %s", exc)
        return None


# --- pure ------------------------------------------------------------------

def nearest_supply(zones: list, live: float) -> Optional[dict]:
    """The supply band price meets FIRST going up: the band that contains
    `live`, else the lowest band whose bottom is above it. None = clear."""
    if not live or live <= 0:
        return None
    above = [z for z in (zones or [])
             if z.get("lo") and z.get("hi") and z["hi"] >= z["lo"] and z["hi"] >= live]
    if not above:
        return None
    inside = [z for z in above if z["lo"] <= live]
    if inside:
        return min(inside, key=lambda z: z["lo"])
    return min(above, key=lambda z: z["lo"])


def classify(live: float, band: Optional[dict], atr: Optional[float]) -> dict:
    """Pure decision table.

    IN_SUPPLY   live is inside the band — the sell zone is reached.
    NEAR        <= NEAR_PCT under the band bottom.
    APPROACHING <= APPROACH_PCT.
    FAR         further than that.
    CLEAR       no supply overhead in the frame — trail the stop instead.
    """
    if band is None:
        return {"state": "CLEAR", "distance_pct": None, "atr_days": None}
    if band["lo"] <= live <= band["hi"]:
        return {"state": "IN_SUPPLY", "distance_pct": 0.0, "atr_days": 0.0}
    dist = (band["lo"] / live - 1) * 100
    atr_days = round((band["lo"] - live) / atr, 1) if atr and atr > 0 else None
    state = ("NEAR" if dist <= NEAR_PCT else
             "APPROACHING" if dist <= APPROACH_PCT else "FAR")
    return {"state": state, "distance_pct": round(dist, 2), "atr_days": atr_days}


def should_alert(state: str, distance_pct: Optional[float]) -> bool:
    return state == "IN_SUPPLY" or (
        distance_pct is not None and 0 <= distance_pct <= ALERT_PCT)


def _trading_day_et(now: Optional[datetime] = None) -> str:
    """Dedupe/day key in ET — a 19:02 ET after-hours tick in winter is already
    tomorrow in UTC and would re-fire the same band."""
    now = now or datetime.now(timezone.utc)
    return now.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


def read_for(row: dict) -> str:
    s = row.get("state")
    b = row.get("band") or {}
    if row.get("zones_error"):
        return "Sell zones unavailable — retrying"
    if s == "UNKNOWN":
        return "No live print yet"
    if s == "IN_SUPPLY":
        return "In the sell zone — trim or sell into it"
    if s == "NEAR":
        return f"≤{NEAR_PCT:.0f}% under supply — set the sell order at ${b.get('lo', 0):.2f}"
    if s == "APPROACHING":
        d = row.get("atr_days")
        return (f"~{d:.0f} ATR-days from supply" if d is not None
                else "Approaching supply")
    if s == "FAR":
        return "Room to run before supply"
    return f"No supply overhead in the {FRAME_NOTE} — trail the stop"


# --- build -----------------------------------------------------------------

def _zones_for(sym: str, live: Optional[float] = None) -> tuple:
    """(supply_zones, demand_zones, atr, error) on daily bars — the same engine
    the Chart Maps tabs read, but with EVERY swing cluster (max_zones=None):
    the first band overhead is routinely not among the 4 strongest that the
    tabs surface. Anchored on the last daily close, never on a live print
    (a pre-open 0.0 made compute() divide by zero). `error` is a string when
    the engine missed so the table says 'unavailable', never a false CLEAR."""
    try:
        from supply_demand import price_zones as pz
        out = pz.for_symbol(sym, max_zones=None)
        if out.get("error"):
            return [], [], None, str(out["error"])
        atr = None
        try:
            from sepa import prices
            from supply_demand import patterns as pat
            df = prices.load_prices(sym, period="1y")
            atr = pat.atr(df) if df is not None else None
        except Exception as exc:                            # pragma: no cover
            log.debug("supply_watch: atr for %s failed: %s", sym, exc)
        return (out.get("supply_zones") or [], out.get("demand_zones") or [],
                float(atr) if atr else None, None)
    except Exception as exc:
        log.warning("supply_watch: zones for %s failed: %s", sym, exc)
        return [], [], None, f"{type(exc).__name__}: {exc}"[:160]


def _base(holding: dict, live: Optional[float]) -> Optional[dict]:
    """The SLOW half: zones + ATR off daily bars. Cached for CACHE_TTL_SEC —
    daily structure only changes at the close."""
    sym = (holding.get("ticker") or "").upper()
    if not sym:
        return None
    shares = float(holding.get("shares") or 0)
    cost = float(holding.get("cost_basis") or 0)
    avg = cost / shares if shares and cost else None
    supply, demand, atr, err = _zones_for(sym)
    return {"symbol": sym, "shares": shares, "avg_cost": round(avg, 4) if avg else None,
            "atr": round(atr, 4) if atr else None, "zones_error": err,
            "_zones": {"supply": supply, "demand": demand}}


def derive(base: dict, quote: dict) -> dict:
    """The CHEAP half: today's print against the cached zones. Re-run on
    every read so the table and the alerts see the LIVE price even when the
    zone cache is minutes old."""
    live = quote.get("last") or None
    err = base.get("zones_error")
    supply = (base.get("_zones") or {}).get("supply") or []
    demand = (base.get("_zones") or {}).get("demand") or []
    atr, avg = base.get("atr"), base.get("avg_cost")
    band = nearest_supply(supply, live) if (live and not err) else None
    cls = (classify(live, band, atr) if (live and not err)
           else {"state": "UNKNOWN", "distance_pct": None, "atr_days": None})
    nxt = None
    if band:
        higher = [z for z in supply if z.get("lo") and z["lo"] > band["hi"]]
        nxt = min(higher, key=lambda z: z["lo"]) if higher else None
    support = None
    if live:
        below = [z for z in demand if z.get("hi") and z["hi"] < live]
        support = max(below, key=lambda z: z["hi"]) if below else None
    row = {
        "symbol": base["symbol"], "shares": base.get("shares"), "avg_cost": avg,
        "last": live, "day_pct": quote.get("day_change_pct"),
        "pl_pct": round((live / avg - 1) * 100, 2) if (live and avg) else None,
        "band": ({"lo": band["lo"], "hi": band["hi"], "touches": band.get("touches")}
                 if band else None),
        "next_band": ({"lo": nxt["lo"], "hi": nxt["hi"]} if nxt else None),
        "support": ({"lo": support["lo"], "hi": support["hi"]} if support else None),
        "atr": atr, "session": quote.get("session"), "zones_error": err, **cls,
    }
    row["read"] = read_for(row)
    return row


def _row(holding: dict, quote: dict) -> Optional[dict]:
    """Zones + derive in one go (used when nothing is cached)."""
    base = _base(holding, quote.get("last"))
    return {**derive(base, quote), "_zones": base["_zones"]} if base else None


def _public(rows: list) -> list:
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]


def _rank(rows: list) -> None:
    rank = {"IN_SUPPLY": 0, "NEAR": 1, "APPROACHING": 2, "FAR": 3, "CLEAR": 4, "UNKNOWN": 5}
    rows.sort(key=lambda r: (rank.get(r["state"], 9), r.get("distance_pct") or 0))


def _live_block() -> dict:
    try:
        from supply_demand import timeframes as tf_mod
        st = tf_mod.live_state()
    except Exception:                                       # pragma: no cover
        st = {"state": "closed", "refresh_sec": 0, "as_of": None}
    return {"state": st["state"], "refresh_sec": LIVE_REFRESH_SEC if st["refresh_sec"] else 0,
            "as_of": st.get("as_of")}


METHOD_NOTE = ("Supply = the daily swing-cluster zones above price — same engine as "
               f"Chart Maps ({FRAME_NOTE}), but EVERY cluster, so the first band "
               "overhead counts even when it is weak. Distance is to the band BOTTOM "
               "— the first price that meets sellers. ATR-days = distance ÷ 14-day "
               "ATR, a pace, not a forecast. Prices are the last trade (pre/after-"
               "market included); the zones refresh every 30 min. Alerts fire once "
               "per band per trading day on the position_alert channel.")


def aggregate_holdings(holdings: list) -> list:
    """One row per ticker across accounts: shares and TOTAL cost add, so the
    cost-weighted average falls out for free and the zone engine runs once."""
    agg: dict = {}
    for h in holdings or []:
        sym = (h.get("ticker") or "").upper()
        if not sym:
            continue
        a = agg.setdefault(sym, {"ticker": sym, "shares": 0.0, "cost_basis": 0.0})
        a["shares"] += float(h.get("shares") or 0)
        a["cost_basis"] += float(h.get("cost_basis") or 0)
    return list(agg.values())


def quote_book(syms: list) -> dict:
    """{SYM: {last, day_change_pct, session}} from the Massive snapshot —
    the LAST TRADE (extended hours) over the day bar's close, which is the
    16:00 print all evening and 0 before the open. Falls back to the
    portfolio quote cache for anything Massive did not price."""
    out: dict = {}
    if not syms:
        return out
    try:
        from sepa import prices
        live = prices.bulk_live_prices(list(syms)) or {}
    except Exception as exc:
        log.warning("supply_watch: bulk prices failed: %s", exc)
        live = {}
    try:
        from catalysts.promo_live import session_from_ts
    except Exception:                                       # pragma: no cover
        session_from_ts = None
    for sym in syms:
        q = live.get(sym) or {}
        last = q.get("last_trade_price") or q.get("price")
        prev = q.get("prev_day_close")
        if not last:
            continue
        out[sym] = {
            "last": float(last),
            "day_change_pct": (round((float(last) / float(prev) - 1) * 100, 2)
                               if prev else None),
            "session": session_from_ts(q.get("last_trade_ts_ms")) if session_from_ts else None,
        }
    missing = [x for x in syms if x not in out]
    if missing:
        try:
            from portfolio import quotes
            for sym, q in (quotes.fetch_quotes(missing) or {}).items():
                if q.get("last"):
                    out[sym.upper()] = {"last": float(q["last"]),
                                        "day_change_pct": q.get("day_change_pct"),
                                        "session": None}
        except Exception as exc:                            # pragma: no cover
            log.warning("supply_watch: fallback quotes failed: %s", exc)
    return out


def build(user_email: str, force: bool = False) -> dict:
    """Rows for the Portfolio table. The zone half is cached CACHE_TTL_SEC;
    the price half is re-derived on EVERY call so a 60s poll shows the live
    print, not a 10-minute-old one."""
    cache = _coll("portfolio_supply_cache")
    now = datetime.now(timezone.utc)
    key = (user_email or "").lower()
    from portfolio import store
    holdings = aggregate_holdings(store.list_holdings(user_email))
    held = {h["ticker"] for h in holdings}
    qmap = quote_book(sorted(held))

    bases, cached_at = None, None
    if not force and cache is not None:
        try:
            doc = cache.find_one({"_id": key})
            ts = doc.get("cached_at") if doc else None
            if ts is not None and ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age = (now - ts).total_seconds() if (doc and ts) else None
            errored = any(b.get("zones_error") for b in (doc or {}).get("bases") or [])
            fresh = age is not None and age < (ERROR_RETRY_SEC if errored else CACHE_TTL_SEC)
            same_book = bool(doc) and {b["symbol"] for b in doc.get("bases") or []} == held
            if fresh and same_book:
                bases, cached_at = doc["bases"], ts
        except Exception as exc:
            log.warning("supply cache get failed: %s", exc)

    t0 = time.time()
    if bases is None:
        bases = [b for b in (_base(h, (qmap.get(h["ticker"]) or {}).get("last"))
                             for h in holdings) if b]
        cached_at = now
        if cache is not None:
            try:
                cache.update_one({"_id": key}, {"$set": {"cached_at": now, "bases": bases}},
                                 upsert=True)
            except Exception as exc:
                log.warning("supply cache put failed: %s", exc)
        cached = False
    else:
        cached = True

    rows = [derive(b, qmap.get(b["symbol"]) or {}) for b in bases]
    _rank(rows)
    return {
        "as_of": now.isoformat(), "rows": rows, "n": len(rows),
        "live": _live_block(), "method_note": METHOD_NOTE,
        "zones_as_of": cached_at.isoformat() if cached_at else None,
        "elapsed_sec": round(time.time() - t0, 1), "cached": cached,
        "cache_age_sec": round((now - cached_at).total_seconds()) if cached_at else 0,
    }


# --- alerts ----------------------------------------------------------------

def _alert_key(user_email: str, sym: str, band: dict, day: str) -> str:
    return f"{user_email.lower()}:{sym}:{band['lo']:.2f}:{day}"


def check_alerts(user_email: Optional[str] = None) -> dict:
    """Push ONE position_alert per holding per band per day when the live
    print is inside its sell zone or within ALERT_PCT of it. Runs from cron
    every 5 minutes 04:00-19:55 ET; skips when the tape is closed."""
    from portfolio.alerts import _resolve_owner, _send_push
    from supply_demand import timeframes as tf_mod
    owner = (user_email or _resolve_owner()).lower()
    state = tf_mod.live_state()
    if state["state"] == "closed":
        return {"ok": True, "skipped": "tape closed", "pushed": 0}
    payload = build(owner)          # cheap path: live print vs cached zones
    coll = _coll("portfolio_supply_alerts")
    day = _trading_day_et()
    tag = {"premarket": "PRE", "afterhours": "AH"}.get(state["state"], "")
    pushed, fired = 0, []
    for r in payload["rows"]:
        if not r.get("band") or not should_alert(r["state"], r.get("distance_pct")):
            continue
        key = _alert_key(owner, r["symbol"], r["band"], day)
        if coll is not None:
            try:
                if coll.find_one({"_id": key}):
                    continue
            except Exception as exc:                        # pragma: no cover
                log.warning("supply alert dedupe read failed: %s", exc)
        b = r["band"]
        pl = f" ({r['pl_pct']:+.1f}% P/L)" if r.get("pl_pct") is not None else ""
        where = ("in SUPPLY" if r["state"] == "IN_SUPPLY"
                 else f"{r['distance_pct']:.1f}% under SUPPLY")
        nxt = r.get("next_band")
        msg = {
            "title": f"🎯 {tag + ' · ' if tag else ''}{r['symbol']} {where} "
                     f"${b['lo']:.2f}–${b['hi']:.2f}{pl}",
            "body": (f"Live ${r['last']:.2f} · sell zone reached — trim or sell into it"
                     + (f" · next supply ${nxt['lo']:.2f}–${nxt['hi']:.2f}" if nxt else
                        f" · nothing above this in the {FRAME_NOTE}")),
            "icon": "/icon.svg",
            "tag": f"supply-{r['symbol'].lower()}",
            "url": "/portfolio", "kind": "position_alert", "ticker": r["symbol"],
            "data": {"url": "/portfolio", "symbol": r["symbol"], "source": "supply_watch"},
        }
        res = _send_push(owner, msg, kind="position_alert") or {}
        sent, targets = res.get("sent", 0), res.get("total_targets", 0)
        if sent > 0:
            pushed += 1
        # Terminal outcomes dedupe: delivered, or nobody to deliver to (muted
        # pref / quiet hours / no device). Only a genuine send failure retries.
        if (sent > 0 or targets == 0) and coll is not None:
            try:
                coll.update_one({"_id": key}, {"$set": {"at": datetime.now(timezone.utc),
                                                        "symbol": r["symbol"], "band": b,
                                                        "sent": sent, "targets": targets}},
                                upsert=True)
            except Exception as exc:                        # pragma: no cover
                log.warning("supply alert dedupe write failed: %s", exc)
        fired.append({"symbol": r["symbol"], "state": r["state"], "sent": (res or {}).get("sent", 0)})
    out = {"ok": True, "pushed": pushed, "fired": fired, "session": state["state"]}
    log.info("supply_watch: %s", out)
    return out


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    print(json.dumps(check_alerts(), indent=2, default=str))
