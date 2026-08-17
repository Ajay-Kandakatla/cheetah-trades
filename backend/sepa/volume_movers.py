"""Volume Movers board — "highest volume + price change, and how much of the
FLOAT actually traded" (Ajay 2026-06-15).

His model: heavy volume depletes supply -> demand -> price push. The honest read
is TURNOVER (volume ÷ float), not raw share count. A mega-cap like INTC trades
100M+ shares, yet that's a tiny slice of its multi-billion float, so the
"supply" barely moves and the price doesn't get pushed. This board surfaces, for
the day's biggest names:

  * last_vol        — ACTUAL shares traded today
  * rvol            — relative volume = today ÷ the 50-day average (the
                      "unusual volume" read; raw share count alone misleads)
  * dollar_vol      — last_vol × price (where the real money flowed)
  * day_change_pct  — the price move
  * float_shares / shares_outstanding  — the company's TOTAL tradeable shares
  * turnover_pct    — last_vol ÷ float × 100 ("how much of the supply changed
                      hands"). THIS is the supply-depletion read he's after.

Volume / RVOL / $vol / change come straight from the latest scan (free). Float
needs a per-symbol lookup, so it's fetched + cached (weekly) only for the
top-N rows the board actually shows.

DISPLAY-ONLY: never feeds the scanner score.
"""
from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from . import symbols

log = logging.getLogger("sepa.volume_movers")

# Float / shares-outstanding change rarely — refresh at most weekly.
_SHARES_TTL_SEC = 7 * 24 * 3600


def _shares_coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        return client[os.getenv("MONGO_DB", "cheetah")].shares_cache
    except Exception:
        return None


def _fetch_shares_yf(symbol: str):
    try:
        import yfinance as yf
        info = symbols.yf_ticker(symbol).info or {}
        so = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
        fl = info.get("floatShares")
        mc = info.get("marketCap")
        if not so and not fl:
            return None
        return {
            "shares_outstanding": int(so) if so else None,
            "float_shares":       int(fl) if fl else None,
            "market_cap":         int(mc) if mc else None,
        }
    except Exception as exc:                       # noqa: BLE001
        log.debug("shares fetch failed for %s: %s", symbol, exc)
        return None


def shares_for(symbol: str):
    """Cached shares-outstanding / float / market-cap for one symbol (weekly TTL).
    Soft-fails to None — the board still renders, turnover just shows '—'."""
    sym = (symbol or "").upper().strip()
    if not sym:
        return None
    coll = _shares_coll()
    now = int(time.time())
    if coll is not None:
        try:
            doc = coll.find_one({"_id": sym})
            if doc and (now - int(doc.get("as_of", 0))) < _SHARES_TTL_SEC:
                vals = {k: doc.get(k) for k in ("shares_outstanding", "float_shares", "market_cap")}
                # Fresh tombstone (all null) → name has no float (ETF/unknown);
                # honor it so we don't re-hit yfinance every card render.
                return vals if any(v is not None for v in vals.values()) else None
        except Exception:
            pass
    fetched = _fetch_shares_yf(sym)
    if coll is not None:
        # Cache the result — INCLUDING a null tombstone on a miss — so a burst of
        # card renders for the same symbol doesn't stampede yfinance.
        payload = fetched or {"shares_outstanding": None, "float_shares": None, "market_cap": None}
        try:
            coll.update_one({"_id": sym}, {"$set": {**payload, "as_of": now}}, upsert=True)
        except Exception:
            pass
    return fetched


# Server-side sorts — all computable from the scan alone (turnover is a column
# the FE can re-sort the loaded rows by; we don't sort the whole universe by it
# because that would need a float fetch for every name).
_SORTS = {
    "volume":     lambda r: -(r.get("last_vol") or 0),
    "rvol":       lambda r: -(r.get("rvol") or 0),
    "dollar_vol": lambda r: -(r.get("dollar_vol") or 0),
    "change":     lambda r: -(r.get("day_change_pct") or 0),
}


def _base_row(r: dict):
    v = r.get("volume") or {}
    lv = v.get("last_vol")
    if not lv:
        return None
    av = v.get("avg_vol_50")
    close = r.get("last_close")
    rvol = (lv / av) if (av and av > 0) else None
    dollar_vol = (lv * close) if (lv and close) else None
    return {
        "symbol":         r.get("symbol"),
        "name":           r.get("name"),
        "last_close":     close,
        "day_change_pct": r.get("day_change_pct"),
        "last_vol":       int(lv),
        "avg_vol_50":     int(av) if av else None,
        "rvol":           round(rvol, 2) if rvol else None,
        "dollar_vol":     round(dollar_vol) if dollar_vol else None,
    }


def movers(top: int = 25, sort: str = "volume") -> dict:
    """Top-N volume names from the latest scan + float/turnover enrichment.

    sort ∈ {volume, rvol, dollar_vol, change}; default 'volume' (his literal
    ask), with rvol/turnover surfaced so the raw-volume leaders reveal WHY they
    did or didn't move."""
    from sepa import scanner
    scan = scanner.load_latest() or {}
    if sort not in _SORTS:
        sort = "volume"
    top = max(1, min(int(top), 100))

    rows = [x for x in (_base_row(r) for r in (scan.get("all_results") or [])) if x]
    rows.sort(key=_SORTS[sort])
    rows = rows[:top]

    # Enrich the shown rows with float + turnover (concurrent, cached).
    syms = [r["symbol"] for r in rows if r.get("symbol")]
    shares_map = {}
    if syms:
        try:
            with ThreadPoolExecutor(max_workers=8) as ex:
                for sym, sh in zip(syms, ex.map(shares_for, syms)):
                    shares_map[sym] = sh
        except Exception as exc:                   # noqa: BLE001
            log.debug("volume_movers float enrich failed: %s", exc)

    for r in rows:
        sh = shares_map.get(r["symbol"]) or {}
        fl = sh.get("float_shares") or sh.get("shares_outstanding")
        r["float_shares"]       = sh.get("float_shares")
        r["shares_outstanding"] = sh.get("shares_outstanding")
        r["market_cap"]         = sh.get("market_cap")
        r["turnover_pct"]       = round(r["last_vol"] / fl * 100, 2) if (fl and fl > 0) else None

    return {"rows": rows, "sort": sort, "n": len(rows), "scan_ts": scan.get("generated_at")}
