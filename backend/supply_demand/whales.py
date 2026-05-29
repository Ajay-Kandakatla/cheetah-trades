"""Whale tracking — institutional holders + recent buys/sells per ticker.

Data source: yfinance, which scrapes Yahoo Finance's institutional_holders
endpoint (which itself sources from 13F filings + mutual fund disclosures).

Honest scope:
  - 13F filings are quarterly with a 45-day lag — "recent moves" means
    most recent quarter vs prior quarter, not real time.
  - yfinance gives us top ~10 institutional holders + top ~10 mutual funds.
  - We compute delta vs prior period when Yahoo provides "% Change" column.
  - Free; no API key needed; no extra spend.

Future upgrade paths:
  - WhaleWisdom Premium ($50-150/mo) — real-time 13F alerts + cloning UIs
  - Quiver Quantitative ($10-30/mo) — congressional trades + alt data
  - SEC EDGAR direct (free, harder) — parse 13F-HR XML for full holdings table

Cached 24h in Mongo (these only update quarterly).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("supply_demand.whales")

_CACHE_TTL_SEC = 24 * 60 * 60  # 24 hours


# --- Mongo cache ---------------------------------------------------------

def _cache_coll():
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        c = client[db]["whales_cache"]
        c.create_index([("ticker", ASCENDING)], unique=True)
        return c
    except Exception as exc:
        log.warning("whales cache mongo unavailable: %s", exc)
        return None


def _cache_get(ticker: str) -> Optional[dict]:
    coll = _cache_coll()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"ticker": ticker.upper()})
        if not doc:
            return None
        ts = doc.get("cached_at")
        if not isinstance(ts, datetime):
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        if age > _CACHE_TTL_SEC:
            return None
        payload = doc.get("payload")
        if isinstance(payload, dict):
            payload = dict(payload)
            payload["_cached"] = True
            payload["_cache_age_sec"] = round(age)
            return payload
    except Exception as exc:
        log.warning("whales cache get failed for %s: %s", ticker, exc)
    return None


def _cache_put(ticker: str, payload: dict) -> None:
    coll = _cache_coll()
    if coll is None:
        return
    try:
        coll.update_one(
            {"ticker": ticker.upper()},
            {"$set": {"ticker": ticker.upper(),
                      "cached_at": datetime.now(timezone.utc),
                      "payload": payload}},
            upsert=True,
        )
    except Exception as exc:
        log.warning("whales cache put failed for %s: %s", ticker, exc)


# --- Public-style hedge fund / institution name normalization ------------

# Heuristics for identifying high-profile institutions vs faceless index funds.
# Yahoo returns names like "Vanguard Group Inc", "BlackRock Inc",
# "Berkshire Hathaway Inc", etc. These tags drive UI grouping.
_HEDGE_FUND_KEYWORDS = (
    "berkshire", "renaissance", "bridgewater", "citadel", "two sigma",
    "tudor", "appaloosa", "elliott", "third point", "pershing",
    "viking", "tiger global", "coatue", "soroban", "sequoia capital",
    "lone pine", "millennium", "balyasny", "point72", "d.e. shaw",
    "de shaw", "marshall wace", "hudson bay", "schonfeld", "verition",
    "altimeter", "scion", "icahn", "starboard", "trian", "pelican",
)
_INDEX_GIANT_KEYWORDS = (
    "vanguard", "blackrock", "state street", "fidelity", "geode",
    "northern trust", "morgan stanley investment", "wellington",
    "t. rowe price", "t rowe price", "capital research", "capital world",
    "jp morgan asset", "jpmorgan asset", "ubs asset", "bank of america",
)


def _classify_holder(name: str) -> str:
    """Return one of: 'hedge_fund', 'index_giant', 'other'."""
    n = (name or "").lower()
    for kw in _HEDGE_FUND_KEYWORDS:
        if kw in n:
            return "hedge_fund"
    for kw in _INDEX_GIANT_KEYWORDS:
        if kw in n:
            return "index_giant"
    return "other"


# --- Core fetch ----------------------------------------------------------

def _fetch_yfinance_holders(ticker: str) -> dict:
    """Pull institutional + mutual-fund holders from yfinance.

    Returns dict with `institutional` and `mutual_fund` lists. Each entry:
        {holder, shares, value, pct_held, pct_change, date_reported, type}

    `pct_change` is None when Yahoo doesn't provide it (some tickers).
    `type` is 'hedge_fund' | 'index_giant' | 'other' for UI grouping.
    """
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)

        institutional = []
        mutual = []

        # institutional_holders is a pandas DataFrame; columns vary by yfinance version
        try:
            df = t.institutional_holders
            if df is not None and not df.empty:
                for _, row in df.head(15).iterrows():
                    institutional.append(_row_to_holder(row, ticker, kind="institutional"))
        except Exception as exc:
            log.warning("institutional_holders failed for %s: %s", ticker, exc)

        try:
            df = t.mutualfund_holders
            if df is not None and not df.empty:
                for _, row in df.head(10).iterrows():
                    mutual.append(_row_to_holder(row, ticker, kind="mutual_fund"))
        except Exception as exc:
            log.warning("mutualfund_holders failed for %s: %s", ticker, exc)

        # Major holders: % insider, % institution, etc.
        major = {}
        try:
            mh = t.major_holders
            if mh is not None and not mh.empty:
                # pandas: usually 2 cols (value, label)
                for _, row in mh.iterrows():
                    label = str(row.iloc[1]).strip().lower() if len(row) > 1 else ""
                    val = str(row.iloc[0]).strip() if len(row) > 0 else ""
                    if "insider" in label and "%" not in major.get("insider_pct", ""):
                        major["insider_pct"] = val
                    elif "institution" in label and "float" not in label:
                        major["institutional_pct"] = val
                    elif "float" in label:
                        major["institutional_float_pct"] = val
                    elif "number" in label:
                        major["n_institutions"] = val
        except Exception:
            pass

        return {"institutional": institutional, "mutual_fund": mutual, "major": major}
    except Exception as exc:
        log.warning("yfinance whales fetch failed for %s: %s", ticker, exc)
        return {"institutional": [], "mutual_fund": [], "major": {}}


def _row_to_holder(row, ticker: str, kind: str) -> dict:
    """Normalize a yfinance holders DataFrame row into a clean dict."""
    def _get(key_options, default=None):
        for k in key_options:
            try:
                v = row.get(k) if hasattr(row, "get") else None
                if v is not None and str(v).strip() != "":
                    return v
            except Exception:
                continue
        return default

    holder = str(_get(["Holder", "holder"], "")).strip()
    shares = _get(["Shares", "shares"], None)
    value = _get(["Value", "value"], None)
    pct_held = _get(["% Out", "pctHeld", "% Held"], None)
    pct_change = _get(["% Change", "pctChange"], None)
    date_reported = _get(["Date Reported", "dateReported"], None)

    # Coerce to plain types (Mongo doesn't like numpy/pandas)
    def _num(x):
        if x is None: return None
        try:
            return float(x)
        except Exception:
            return None

    def _str(x):
        if x is None: return None
        return str(x)

    return {
        "holder": holder,
        "shares": _num(shares),
        "value": _num(value),
        "pct_held": _num(pct_held),
        "pct_change": _num(pct_change),
        "date_reported": _str(date_reported),
        "kind": kind,
        "type": _classify_holder(holder),
        "ticker": ticker.upper(),
    }


def _summarize_period(holders: list[dict]) -> dict | None:
    """Aggregate `date_reported` across all funds into a single timeline.

    yfinance emits per-fund date_reported strings like '2026-03-31 00:00:00'.
    Most institutional funds line up on 13F quarter-ends (Mar/Jun/Sep/Dec
    last day) since 13F is quarterly; mutual funds add monthly stamps.
    Surface the dominant (mode) date as the headline, with earliest/latest
    span so the user can see how stale the oldest fund's snapshot is.
    """
    from collections import Counter
    dates = []
    for h in holders:
        d = h.get("date_reported")
        if not d:
            continue
        # Strip time portion: "2026-03-31 00:00:00" -> "2026-03-31".
        # Ignore anything that doesn't start with YYYY-MM-DD.
        head = str(d)[:10]
        if len(head) == 10 and head[4] == "-" and head[7] == "-":
            dates.append(head)
    if not dates:
        return None
    sorted_dates = sorted(dates)
    earliest = sorted_dates[0]
    latest = sorted_dates[-1]
    dominant = Counter(dates).most_common(1)[0][0]

    # Derive quarter label from dominant date (most reflects the 13F period).
    try:
        y, m, _ = dominant.split("-")
        month = int(m)
        q = (month - 1) // 3 + 1
        quarter_label = f"Q{q} {y}"
    except Exception:
        quarter_label = None

    # Human-readable "As of Mon DD, YYYY" for the dominant period.
    try:
        from datetime import datetime as _dt
        dom_dt = _dt.strptime(dominant, "%Y-%m-%d")
        human_dominant = dom_dt.strftime("%b %-d, %Y")
    except Exception:
        human_dominant = dominant

    return {
        "dominant": dominant,
        "earliest": earliest,
        "latest": latest,
        "quarter_label": quarter_label,
        "human": f"As of {quarter_label} ({human_dominant})" if quarter_label else f"As of {human_dominant}",
        "n_dates": len(set(dates)),
    }


def _summarize_moves(holders: list[dict]) -> dict:
    """Compute aggregate buy/sell signal from holders' pct_change values."""
    n_buying = 0
    n_selling = 0
    n_unchanged = 0
    n_new = 0
    n_sold_out = 0
    total_buy_pct = 0.0
    total_sell_pct = 0.0
    notable_buys = []
    notable_sells = []

    for h in holders:
        pc = h.get("pct_change")
        if pc is None:
            continue
        if pc > 0.05:
            n_buying += 1
            total_buy_pct += pc
            if pc > 0.10:  # >10% increase = notable
                # ADDITIVE: also forward value (position $) + pct_held (%
                # of float). The FE uses these for the fund-credibility
                # tier score added 2026-05-28 (size + concentration are
                # half the rubric; the smart-money curated list is the
                # other half). No change to ranking / classification
                # logic — these fields are already collected by
                # _row_to_holder, just weren't being exposed.
                notable_buys.append({
                    "holder":     h["holder"],
                    "pct_change": pc,
                    "type":       h.get("type"),
                    "value":      h.get("value"),
                    "pct_held":   h.get("pct_held"),
                })
        elif pc < -0.05:
            n_selling += 1
            total_sell_pct += abs(pc)
            if pc < -0.10:
                notable_sells.append({
                    "holder":     h["holder"],
                    "pct_change": pc,
                    "type":       h.get("type"),
                    "value":      h.get("value"),
                    "pct_held":   h.get("pct_held"),
                })
        else:
            n_unchanged += 1

    # Sort notable lists by magnitude
    notable_buys.sort(key=lambda x: x["pct_change"], reverse=True)
    notable_sells.sort(key=lambda x: x["pct_change"])

    # Sentiment: net buying ratio
    net_signal = (
        "accumulating" if n_buying > n_selling * 1.5 else
        "distributing" if n_selling > n_buying * 1.5 else
        "balanced"
    )

    return {
        "net_signal": net_signal,
        "n_buying": n_buying,
        "n_selling": n_selling,
        "n_unchanged": n_unchanged,
        "n_new": n_new,
        "n_sold_out": n_sold_out,
        # Expose top 10 each (was 5) — the per-ticker endpoint feeds
        # the WhalesFlowModal which renders both columns; 10 fits cleanly
        # on a phone modal and gives the user enough breadth to spot
        # named funds they recognize. The bulk /whales-flow endpoint
        # still only surfaces the FIRST entry as top_buy/top_sell, so
        # this cap only affects per-ticker drill-ins.
        "notable_buys":  notable_buys[:10],
        "notable_sells": notable_sells[:10],
    }


# --- Public API ----------------------------------------------------------

def get_whales(ticker: str, force: bool = False) -> dict:
    """Return whale snapshot for `ticker`.

    Output:
      {
        ticker,
        as_of,
        holders: [{holder, shares, value, pct_held, pct_change, type, kind}, ...],
        mutual_funds: [...],
        major: {insider_pct, institutional_pct, n_institutions},
        moves: {net_signal, n_buying, n_selling, notable_buys, notable_sells},
        disclaimer,
      }
    """
    t = ticker.upper()
    if not force:
        cached = _cache_get(t)
        if cached:
            return cached

    raw = _fetch_yfinance_holders(t)
    holders = raw.get("institutional", [])
    mutuals = raw.get("mutual_fund", [])

    # Combine for aggregate summary (institutional + mutual)
    combined = holders + mutuals
    moves = _summarize_moves(combined)
    period = _summarize_period(combined)

    payload = {
        "ticker": t,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "period": period,
        "holders": holders,
        "mutual_funds": mutuals,
        "major": raw.get("major", {}),
        "moves": moves,
        "n_holders": len(holders),
        "n_mutuals": len(mutuals),
        "disclaimer": (
            "13F filings are quarterly with a 45-day lag. % Change reflects "
            "delta from prior 13F. Holdings under $100M AUM aren't required to "
            "file. This is a snapshot, not real-time activity."
        ),
        "source": "yfinance / Yahoo Finance (sourced from SEC 13F-HR filings)",
    }

    _cache_put(t, payload)
    return payload


__all__ = ["get_whales"]


if __name__ == "__main__":
    # Smoke test: python -m supply_demand.whales NVDA
    import json
    import sys
    tk = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    print(json.dumps(get_whales(tk, force=True), indent=2, default=str))
