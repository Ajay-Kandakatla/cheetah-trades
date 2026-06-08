"""Long-Term Stocks tracker — live tracking of the ZONETRADER618 report card.

We track a FIXED 70-stock report card (the public "ZONETRADER618 — Long-Term
Stocks Report Card", Mar 27 – May 29 2026). Entry / basis / max-high / exit /
gain in ROSTER are the author's GIVEN numbers — not ours. We enrich each name
with LIVE data so Ajay can watch how it's changing:

  • current price + gain-now vs entry (vs the report's frozen gain)
  • a fresh max-high since the report, and the 10% trailing-stop status
  • whether it's back IN A DEMAND ZONE — using OUR own supply/demand engine
    (stock_supply_demand.analyze_symbol → state == "demand"), NOT the author's
    exact zones, which we don't have
  • whether it's pulling back / ranking in our SEPA leaderboard → a chip the FE
    links to /leaderboard

Daily snapshots are persisted so the page can show deltas over time.

NOT advice. The report card is a public, educational snapshot we mirror; nothing
here is a buy/sell recommendation or a forecast. The author's own note: returns
reflect an extremely bullish phase and "losses can and will occur."

Source label note: the rows say "TSL 15%" but the exits are mathematically 10%
below max high (e.g. RKLB 135.90/151.00 = 0.90), matching the title's "10%
trailing stop." We track forward with 10%.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

log = logging.getLogger("longterm")

TSL_PCT = 0.10           # trailing stop = 10% below the running max high
TTL_SEC = 300

# ── The report card (author's GIVEN data) ───────────────────────────────────
# (category, ticker, entry, entry_basis, report_max_high, report_exit,
#  report_exit_basis, report_gain_pct)
#   entry_basis : "demand" (entered at a demand zone) | "close" (Mar-27 close)
#   exit_basis  : "max_high" (still at/near high) | "tsl" (10% trailing stop hit)
ROSTER = [
    ("Quantum",   "IONQ",  26.00,  "demand", 72.17,   72.17,   "max_high", 177.6),
    ("Mid Cap",   "ENPH",  27.50,  "demand", 73.74,   73.74,   "max_high", 168.1),
    ("AI Chips",  "SMCI",  18.50,  "demand", 48.34,   48.34,   "max_high", 161.3),
    ("Mid Cap",   "AMD",   203.43, "close",  527.20,  527.20,  "max_high", 159.2),
    ("Mid Cap",   "ARM",   151.28, "close",  356.45,  356.45,  "max_high", 135.6),
    ("Mid Cap",   "SNOW",  110.00, "demand", 256.21,  256.21,  "max_high", 132.9),
    ("Space",     "RKLB",  64.22,  "close",  151.00,  135.90,  "tsl",      111.6),
    ("Quantum",   "QBTS",  13.50,  "demand", 31.55,   28.39,   "tsl",      110.3),
    ("Mid Cap",   "PANW",  140.00, "demand", 283.71,  283.71,  "max_high", 102.6),
    ("AI Chips",  "MRVL",  99.00,  "close",  218.26,  196.43,  "tsl",      98.4),
    ("Space",     "IRDM",  27.74,  "close",  52.25,   52.25,   "max_high", 88.4),
    ("Mid Cap",   "CRWD",  390.41, "close",  731.49,  731.49,  "max_high", 87.4),
    ("Quantum",   "RGTI",  14.04,  "close",  27.78,   25.01,   "tsl",      78.1),
    ("Mid Cap",   "FTNT",  81.72,  "close",  138.11,  138.11,  "max_high", 69.0),
    ("Mid Cap",   "FSLR",  197.26, "close",  313.75,  313.75,  "max_high", 59.1),
    ("Large Cap", "AVGO",  285.00, "demand", 448.90,  448.90,  "max_high", 57.5),
    ("AI Chips",  "LRCX",  213.66, "close",  333.33,  333.33,  "max_high", 56.0),
    ("Large Cap", "ORCL",  146.60, "close",  226.29,  226.29,  "max_high", 54.4),
    ("Large Cap", "UNH",   267.50, "demand", 404.15,  404.15,  "max_high", 51.1),
    ("Large Cap", "GOOG",  272.50, "demand", 404.47,  404.47,  "max_high", 48.4),
    ("Nuclear",   "OKLO",  49.59,  "close",  81.50,   73.35,   "tsl",      47.9),
    ("Space",     "ASTS",  82.87,  "close",  133.86,  120.47,  "tsl",      45.4),
    ("Biotech",   "TMDX",  77.50,  "demand", 120.91,  108.82,  "tsl",      40.4),
    ("Mid Cap",   "SHOP",  90.00,  "demand", 137.30,  123.57,  "tsl",      37.3),
    ("Large Cap", "AMZN",  208.27, "close",  278.56,  278.56,  "max_high", 33.7),
    ("Large Cap", "LLY",   865.00, "demand", 1149.10, 1149.10, "max_high", 32.8),
    ("AI Chips",  "ANET",  122.78, "close",  179.80,  161.82,  "tsl",      31.8),
    ("Mid Cap",   "ZS",    131.50, "demand", 191.25,  172.12,  "tsl",      30.9),
    ("Biotech",   "BEAM",  23.83,  "close",  34.38,   30.94,   "tsl",      29.8),
    ("Large Cap", "AAPL",  245.00, "demand", 315.00,  315.00,  "max_high", 28.6),
    ("Nuclear",   "LEU",   165.00, "close",  235.00,  211.50,  "tsl",      28.2),
    ("Large Cap", "TSM",   337.95, "close",  430.55,  430.55,  "max_high", 27.4),
    ("Mid Cap",   "MNST",  72.46,  "close",  89.85,   89.85,   "max_high", 24.0),
    ("Large Cap", "NVDA",  174.40, "close",  236.54,  212.89,  "tsl",      22.1),
    ("Large Cap", "MSFT",  369.37, "close",  450.33,  450.33,  "max_high", 21.9),
    ("Nuclear",   "GEV",   872.90, "close",  1181.95, 1063.75, "tsl",      21.9),
    ("Large Cap", "GS",    845.99, "close",  1027.22, 1027.22, "max_high", 21.4),
    ("Mid Cap",   "BILL",  32.50,  "demand", 43.57,   39.21,   "tsl",      20.6),
    ("Dividend",  "TROW",  90.14,  "close",  106.93,  106.93,  "max_high", 18.6),
    ("Large Cap", "TSLA",  345.00, "demand", 453.40,  408.06,  "tsl",      18.3),
    ("Large Cap", "CRM",   165.00, "demand", 194.14,  194.14,  "max_high", 17.7),
    ("Mid Cap",   "XYZ",   60.18,  "close",  77.16,   69.44,   "tsl",      15.4),
    ("Mid Cap",   "COIN",  174.61, "close",  222.35,  200.12,  "tsl",      14.6),
    ("Mid Cap",   "INTU",  342.50, "demand", 435.24,  391.72,  "tsl",      14.4),
    ("Mid Cap",   "SOFI",  15.88,  "close",  20.13,   18.12,   "tsl",      14.1),
    ("Large Cap", "V",     300.00, "demand", 341.27,  341.27,  "max_high", 13.8),
    ("Biotech",   "CRSP",  47.57,  "close",  59.39,   53.45,   "tsl",      12.4),
    ("Nuclear",   "VST",   135.00, "demand", 168.49,  151.64,  "tsl",      12.3),
    ("Mid Cap",   "PG",    137.50, "demand", 152.42,  152.42,  "max_high", 10.9),
    ("Large Cap", "JPM",   292.66, "close",  320.24,  320.24,  "max_high", 9.4),
    ("Large Cap", "META",  572.13, "close",  691.52,  622.37,  "tsl",      8.8),
    ("Nuclear",   "CCJ",   108.61, "close",  131.21,  118.09,  "tsl",      8.7),
    ("Mid Cap",   "PLTR",  146.28, "close",  157.78,  157.78,  "max_high", 7.9),
    ("Large Cap", "MA",    498.80, "close",  534.21,  534.21,  "max_high", 7.1),
    ("Nuclear",   "CEG",   278.82, "close",  328.29,  295.46,  "tsl",      6.0),
    ("Mid Cap",   "BKNG",  165.00, "demand", 193.92,  174.53,  "tsl",      5.8),
    ("Mid Cap",   "ABNB",  126.28, "close",  147.25,  132.53,  "tsl",      4.9),
    ("Mid Cap",   "PYPL",  45.23,  "close",  52.30,   47.07,   "tsl",      4.1),
    ("Mid Cap",   "UBER",  70.00,  "demand", 80.83,   72.75,   "tsl",      3.9),
    ("Large Cap", "ISRG",  432.50, "demand", 491.15,  442.03,  "tsl",      2.2),
    ("Large Cap", "NFLX",  96.15,  "close",  108.95,  98.05,   "tsl",      2.0),
    ("Large Cap", "COST",  994.99, "close",  1096.50, 986.85,  "tsl",      -0.8),
    ("Mid Cap",   "MELI",  1729.02,"close",  1903.00, 1712.70, "tsl",      -0.9),
    ("Mid Cap",   "TTD",   22.69,  "close",  24.87,   22.38,   "tsl",      -1.4),
    ("Large Cap", "ADBE",  243.08, "close",  265.09,  238.58,  "tsl",      -1.9),
    ("Large Cap", "HD",    328.89, "close",  353.55,  318.19,  "tsl",      -3.3),
    ("Dividend",  "DHR",   189.60, "close",  200.50,  180.45,  "tsl",      -4.8),
    ("Defense",   "LMT",   604.39, "close",  637.92,  574.13,  "tsl",      -5.0),
    ("Mid Cap",   "CELH",  35.48,  "close",  37.40,   33.66,   "tsl",      -5.1),
    ("Large Cap", "ACN",   196.62, "close",  200.46,  180.41,  "tsl",      -8.2),
]

# Author's frozen report card meta (Mar 27 – May 29 2026), shown for reference.
REPORT_META = {
    "title": "ZONETRADER618 — Long-Term Stocks Report Card",
    "window": "Mar 27 – May 29, 2026",
    "n_stocks": 70,
    "tsl_pct": 10,
    "summary": {"winners": 61, "losses": 9, "win_rate_pct": 87, "avg_gain_pct": 39.4,
                "demand_zones_hit": 25, "median_return_pct": 21.9},
    "benchmark": {"sp500_return_pct": 19.0, "portfolio_return_pct": 39.4,
                  "alpha_pct": 20.4, "alpha_x": 2.1, "sharpe": 0.83, "sortino": 1.32,
                  "std_dev_pct": 46.4},
    "notes": {
        "strategy_risk": ("Extremely bullish market phase — returns are unusual. "
                          "Exit rule: 10% trailing stop from max high. Losses can and will occur."),
        "options": "Absolute returns on stock price; options would have returned 5–10x or more.",
        "tsl_label": ("The report labels exits 'TSL 15%' but the math is 10% below max high "
                      "(matching the title) — we track forward with 10%."),
    },
    "disclaimer": "Not financial advice. Educational only. Past performance does not guarantee future results.",
}

_TICKERS = [r[1] for r in ROSTER]


def _live_prices() -> dict:
    out = {}
    try:
        from sepa import prices
        snap = prices.bulk_snapshot(_TICKERS) or {}
        for t in _TICKERS:
            d = snap.get(t) or {}
            px = d.get("last_trade_price") or d.get("close") or d.get("prev_day_close")
            if isinstance(px, (int, float)) and px > 0:
                out[t] = {"price": round(float(px), 2),
                          "change_pct": d.get("change_pct")}
    except Exception as exc:
        log.warning("longterm live prices failed: %s", exc)
    return out


def _demand_states() -> dict:
    """ticker -> 'demand' | 'supply' | 'churning' from OUR supply/demand engine."""
    out = {}
    try:
        from supply_demand import stock_supply_demand as ssd
    except Exception as exc:
        log.debug("longterm demand engine unavailable: %s", exc)
        return out
    for t in _TICKERS:
        try:
            rec = ssd.analyze_symbol(t)
            if rec:
                out[t] = rec.get("state")
        except Exception:
            continue
    return out


def _pullback_and_leaders() -> tuple[set, dict]:
    pull: set = set()
    leaders: dict = {}
    try:
        from sepa import pullback_ma
        art = pullback_ma.load_latest_pullback() or {}
        pull = {r.get("symbol") for r in (art.get("rows") or []) if r.get("symbol")}
    except Exception:
        pass
    try:
        from sepa import leaderboard
        for l in (leaderboard.leaderboard(n=300).get("leaders") or []):
            if l.get("symbol"):
                leaders[l["symbol"]] = {"persistence_pct": l.get("persistence_pct"),
                                        "current_rank": l.get("current_rank")}
    except Exception:
        pass
    return pull, leaders


def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        return client[os.getenv("MONGO_DB", "cheetah")].longterm_snapshots
    except Exception:
        return None


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def compute() -> dict:
    t0 = time.time()
    px = _live_prices()
    demand = _demand_states()
    pull, leaders = _pullback_and_leaders()

    # prior snapshot (most recent before today) for deltas
    prev = {}
    coll = _coll()
    if coll is not None:
        try:
            doc = coll.find_one({"_id": {"$ne": _today()}}, sort=[("_id", -1)])
            if doc:
                prev = doc.get("gains") or {}
        except Exception:
            pass

    rows, gains = [], {}
    for (cat, t, entry, basis, rmax, rexit, rexit_basis, rgain) in ROSTER:
        live = px.get(t) or {}
        price = live.get("price")
        gain_now = round((price / entry - 1.0) * 100.0, 1) if price else None
        live_max = max(rmax, price) if price else rmax
        tsl_level = round(live_max * (1.0 - TSL_PCT), 2)
        new_high = bool(price and price >= rmax - 1e-9)
        tsl_hit = bool(price and price < tsl_level)
        if gain_now is not None:
            gains[t] = gain_now
        delta = (round(gain_now - prev[t], 1) if (gain_now is not None and t in prev) else None)
        rows.append({
            "category": cat, "ticker": t,
            "entry": entry, "entry_basis": basis,
            "report_max_high": rmax, "report_exit": rexit,
            "report_exit_basis": rexit_basis, "report_gain_pct": rgain,
            "price": price, "gain_now_pct": gain_now, "gain_delta_pct": delta,
            "live_max_high": round(live_max, 2), "tsl_level": tsl_level,
            "new_high": new_high, "tsl_hit": tsl_hit,
            "in_demand_zone": demand.get(t) == "demand",
            "demand_state": demand.get(t),
            "pulling_back": t in pull,
            "leaderboard": leaders.get(t),
        })

    scored = [r for r in rows if r["gain_now_pct"] is not None]
    winners = sum(1 for r in scored if r["gain_now_pct"] > 0)
    avg_now = round(sum(r["gain_now_pct"] for r in scored) / len(scored), 1) if scored else None
    prev_avg = round(sum(prev.values()) / len(prev), 1) if prev else None
    summary = {
        "n": len(rows), "priced": len(scored),
        "winners_now": winners, "losers_now": len(scored) - winners,
        "win_rate_now_pct": round(100 * winners / len(scored)) if scored else None,
        "avg_gain_now_pct": avg_now,
        "avg_gain_delta_pct": (round(avg_now - prev_avg, 1) if (avg_now is not None and prev_avg is not None) else None),
        "in_demand_zone": sum(1 for r in rows if r["in_demand_zone"]),
        "pulling_back": sum(1 for r in rows if r["pulling_back"]),
        "in_leaderboard": sum(1 for r in rows if r["leaderboard"]),
        "tsl_hit": sum(1 for r in rows if r["tsl_hit"]),
        "new_high": sum(1 for r in rows if r["new_high"]),
    }
    return {
        "generated_at": int(time.time()),
        "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_sec": round(time.time() - t0, 2),
        "tsl_pct": int(TSL_PCT * 100),
        "rows": rows, "summary": summary, "report": REPORT_META,
        "prev_snapshot_avg_pct": prev_avg,
        "disclaimer": REPORT_META["disclaimer"],
    }


def _persist_snapshot(data: dict) -> None:
    """Upsert today's snapshot (gains per ticker + avg) so deltas accrue daily."""
    coll = _coll()
    if coll is None:
        return
    try:
        gains = {r["ticker"]: r["gain_now_pct"] for r in data["rows"]
                 if r["gain_now_pct"] is not None}
        coll.update_one(
            {"_id": _today()},
            {"$set": {"gains": gains, "avg_gain_now_pct": data["summary"]["avg_gain_now_pct"],
                      "computed_at": int(time.time())}},
            upsert=True,
        )
    except Exception as exc:
        log.debug("longterm snapshot persist failed: %s", exc)


_CACHE: dict = {"at": 0.0, "data": None}


def get_longterm(force: bool = False) -> dict:
    now = time.time()
    if not force and _CACHE["data"] is not None and (now - _CACHE["at"]) < TTL_SEC:
        return _CACHE["data"]
    data = compute()
    _persist_snapshot(data)
    _CACHE.update(at=now, data=data)
    return data
