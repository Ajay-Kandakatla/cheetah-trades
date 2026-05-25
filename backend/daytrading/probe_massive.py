"""Probe Massive (Polygon-rebrand) API for day-trading data layers.

Verifies — for the configured MASSIVE_API_KEY — what endpoints are accessible
on this tier. We need to know BEFORE building the day-trading module whether
we have:

  1. 1-minute aggregate bars (last 5 days)
  2. 1-minute aggregate bars (last 60 days, for backtest)
  3. Premarket bar coverage (4:00-9:30 ET)
  4. Real-time snapshot endpoint
  5. Level-1 quotes (NBBO bid/ask)
  6. WebSocket trades stream (advanced tier)
  7. Level-2 / order book (top tier)

Run:
    docker exec cheetah-market-app-api-1 python -m daytrading.probe_massive
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional

import requests


BASE = "https://api.massive.com"
SYMBOL = "SPY"


def _hit(path: str, params: Optional[dict] = None, label: str = "") -> dict:
    """Hit an endpoint, return {ok, status, sample, error}."""
    key = os.getenv("MASSIVE_API_KEY")
    if not key:
        return {"ok": False, "error": "MASSIVE_API_KEY not set"}
    p = dict(params or {})
    p["apiKey"] = key
    try:
        r = requests.get(f"{BASE}{path}", params=p, timeout=15)
    except Exception as exc:
        return {"ok": False, "error": f"network: {exc}"}
    if r.status_code != 200:
        body = r.text[:300]
        return {"ok": False, "status": r.status_code, "error": body}
    try:
        body = r.json()
    except Exception:
        return {"ok": False, "status": r.status_code, "error": "non-JSON response"}
    return {"ok": True, "status": r.status_code, "body": body}


def probe():
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    three_months_ago = today - timedelta(days=90)
    year_ago = today - timedelta(days=365)
    five_years_ago = today - timedelta(days=5 * 365)

    print(f"\nMassive API Probe — {SYMBOL}")
    print(f"Today UTC: {today}")
    print("=" * 70)

    results = {}

    # ---------------------------------------------------------------
    # 1) 1-minute aggregates — last 5 days
    # ---------------------------------------------------------------
    print("\n[1] 1-minute aggregates (last 7 days)")
    r = _hit(f"/v2/aggs/ticker/{SYMBOL}/range/1/minute/{week_ago}/{today}",
             params={"adjusted": "true", "sort": "asc", "limit": 50000},
             label="1m_7d")
    if r["ok"]:
        rows = (r["body"].get("results") or [])
        print(f"  ✓ HTTP 200 — {len(rows):,} bars returned")
        if rows:
            first = datetime.utcfromtimestamp(rows[0]["t"] / 1000)
            last = datetime.utcfromtimestamp(rows[-1]["t"] / 1000)
            print(f"  range: {first} → {last}")
            print(f"  sample: o={rows[0].get('o')} h={rows[0].get('h')} l={rows[0].get('l')} c={rows[0].get('c')} v={rows[0].get('v')}")
            # Premarket detection: bars before 13:30 UTC (= 9:30 ET pre-DST)
            pre_count = sum(1 for x in rows if datetime.utcfromtimestamp(x["t"] / 1000).hour < 13)
            after_count = sum(1 for x in rows if datetime.utcfromtimestamp(x["t"] / 1000).hour >= 20)
            print(f"  premarket-zone bars (UTC <13): {pre_count}")
            print(f"  after-hours bars (UTC >=20):   {after_count}")
            results["1m_recent"] = {"ok": True, "bars": len(rows), "premarket_bars": pre_count, "afterhours_bars": after_count}
        else:
            results["1m_recent"] = {"ok": True, "bars": 0}
    else:
        print(f"  ✗ {r.get('status')} — {r.get('error', '')[:200]}")
        results["1m_recent"] = {"ok": False, "error": r.get("error")}

    # ---------------------------------------------------------------
    # 2) 1-minute aggregates — 30 days back (for backtest depth)
    # ---------------------------------------------------------------
    print("\n[2] 1-minute aggregates (30 days back — backtest depth)")
    r = _hit(f"/v2/aggs/ticker/{SYMBOL}/range/1/minute/{month_ago}/{today}",
             params={"adjusted": "true", "sort": "asc", "limit": 50000},
             label="1m_30d")
    if r["ok"]:
        rows = (r["body"].get("results") or [])
        next_url = r["body"].get("next_url")
        print(f"  ✓ HTTP 200 — {len(rows):,} bars (paginated: {bool(next_url)})")
        results["1m_30d"] = {"ok": True, "bars": len(rows), "paginated": bool(next_url)}
    else:
        print(f"  ✗ {r.get('status')} — {r.get('error', '')[:200]}")
        results["1m_30d"] = {"ok": False, "error": r.get("error")}

    # ---------------------------------------------------------------
    # 3) 1-minute aggregates — 1 year back
    # ---------------------------------------------------------------
    print("\n[3] 1-minute aggregates (1 year back — long backtest)")
    r = _hit(f"/v2/aggs/ticker/{SYMBOL}/range/1/minute/{year_ago}/{year_ago + timedelta(days=2)}",
             params={"adjusted": "true", "sort": "asc", "limit": 50000},
             label="1m_1y_window")
    if r["ok"]:
        rows = (r["body"].get("results") or [])
        print(f"  ✓ HTTP 200 — {len(rows):,} bars in 2-day window 1y ago")
        results["1m_1y"] = {"ok": True, "bars": len(rows)}
    else:
        print(f"  ✗ {r.get('status')} — {r.get('error', '')[:200]}")
        results["1m_1y"] = {"ok": False, "error": r.get("error")}

    # ---------------------------------------------------------------
    # 4) 1-minute aggregates — 5 years back (max depth check)
    # ---------------------------------------------------------------
    print("\n[4] 1-minute aggregates (5 years back — max history depth)")
    r = _hit(f"/v2/aggs/ticker/{SYMBOL}/range/1/minute/{five_years_ago}/{five_years_ago + timedelta(days=2)}",
             params={"adjusted": "true", "sort": "asc", "limit": 50000},
             label="1m_5y_window")
    if r["ok"]:
        rows = (r["body"].get("results") or [])
        if rows:
            print(f"  ✓ HTTP 200 — {len(rows):,} bars in 2-day window 5y ago")
        else:
            print(f"  ✓ HTTP 200 but no bars (possible weekend or limit)")
        results["1m_5y"] = {"ok": True, "bars": len(rows)}
    else:
        print(f"  ✗ {r.get('status')} — {r.get('error', '')[:200]}")
        results["1m_5y"] = {"ok": False, "error": r.get("error")}

    # ---------------------------------------------------------------
    # 5) 5-minute aggregates (lower-frequency intraday)
    # ---------------------------------------------------------------
    print("\n[5] 5-minute aggregates (last 7 days)")
    r = _hit(f"/v2/aggs/ticker/{SYMBOL}/range/5/minute/{week_ago}/{today}",
             params={"adjusted": "true", "sort": "asc", "limit": 50000},
             label="5m_7d")
    if r["ok"]:
        rows = (r["body"].get("results") or [])
        print(f"  ✓ HTTP 200 — {len(rows):,} bars")
        results["5m_recent"] = {"ok": True, "bars": len(rows)}
    else:
        print(f"  ✗ {r.get('status')} — {r.get('error', '')[:200]}")
        results["5m_recent"] = {"ok": False, "error": r.get("error")}

    # ---------------------------------------------------------------
    # 6) Real-time snapshot (full ticker)
    # ---------------------------------------------------------------
    print("\n[6] Real-time snapshot — /v2/snapshot/locale/us/markets/stocks/tickers/SPY")
    r = _hit(f"/v2/snapshot/locale/us/markets/stocks/tickers/{SYMBOL}", label="snapshot")
    if r["ok"]:
        snap = r["body"].get("ticker") or {}
        print(f"  ✓ HTTP 200")
        print(f"  day open:   {snap.get('day', {}).get('o')}")
        print(f"  last trade: {snap.get('lastTrade', {}).get('p')} @ {snap.get('lastTrade', {}).get('t')}")
        print(f"  last quote: bid={snap.get('lastQuote', {}).get('p')} ask={snap.get('lastQuote', {}).get('P')}")
        print(f"  todaysChangePerc: {snap.get('todaysChangePerc')}")
        results["snapshot"] = {"ok": True, "has_quote": bool(snap.get("lastQuote", {}).get("p"))}
    else:
        print(f"  ✗ {r.get('status')} — {r.get('error', '')[:200]}")
        results["snapshot"] = {"ok": False, "error": r.get("error")}

    # ---------------------------------------------------------------
    # 7) Last quote (NBBO)
    # ---------------------------------------------------------------
    print("\n[7] Last NBBO quote — /v2/last/nbbo/SPY")
    r = _hit(f"/v2/last/nbbo/{SYMBOL}", label="nbbo")
    if r["ok"]:
        q = r["body"].get("results") or {}
        print(f"  ✓ HTTP 200 — bid={q.get('p')} (size {q.get('s')}) ask={q.get('P')} (size {q.get('S')})")
        results["nbbo"] = {"ok": True}
    else:
        print(f"  ✗ {r.get('status')} — {r.get('error', '')[:200]}")
        results["nbbo"] = {"ok": False, "error": r.get("error")}

    # ---------------------------------------------------------------
    # 8) Trades (tick data) — last 100 trades
    # ---------------------------------------------------------------
    print("\n[8] Trades (tick stream) — /v3/trades/SPY")
    r = _hit(f"/v3/trades/{SYMBOL}", params={"limit": 100, "order": "desc"}, label="trades")
    if r["ok"]:
        trades = r["body"].get("results") or []
        print(f"  ✓ HTTP 200 — {len(trades)} trades")
        if trades:
            t = trades[0]
            print(f"  most recent: {t.get('size')}@${t.get('price')} ts={t.get('participant_timestamp')}")
        results["trades"] = {"ok": True, "n": len(trades)}
    else:
        print(f"  ✗ {r.get('status')} — {r.get('error', '')[:200]}")
        results["trades"] = {"ok": False, "error": r.get("error")}

    # ---------------------------------------------------------------
    # 9) Quotes (level-1 NBBO history)
    # ---------------------------------------------------------------
    print("\n[9] Quotes history (level-1 NBBO) — /v3/quotes/SPY")
    r = _hit(f"/v3/quotes/{SYMBOL}", params={"limit": 50, "order": "desc"}, label="quotes")
    if r["ok"]:
        quotes = r["body"].get("results") or []
        print(f"  ✓ HTTP 200 — {len(quotes)} quotes")
        results["quotes"] = {"ok": True, "n": len(quotes)}
    else:
        print(f"  ✗ {r.get('status')} — {r.get('error', '')[:200]}")
        results["quotes"] = {"ok": False, "error": r.get("error")}

    # ---------------------------------------------------------------
    # 10) Grouped daily (universe-wide)
    # ---------------------------------------------------------------
    print(f"\n[10] Grouped daily — /v2/aggs/grouped/locale/us/market/stocks/{yesterday}")
    r = _hit(f"/v2/aggs/grouped/locale/us/market/stocks/{yesterday}",
             params={"adjusted": "true"}, label="grouped")
    if r["ok"]:
        rows = (r["body"].get("results") or [])
        print(f"  ✓ HTTP 200 — {len(rows):,} symbols")
        results["grouped"] = {"ok": True, "n_symbols": len(rows)}
    else:
        print(f"  ✗ {r.get('status')} — {r.get('error', '')[:200]}")
        results["grouped"] = {"ok": False, "error": r.get("error")}

    # ---------------------------------------------------------------
    # 11) News (real-time)
    # ---------------------------------------------------------------
    print("\n[11] News — /v2/reference/news?ticker=SPY")
    r = _hit("/v2/reference/news", params={"ticker": SYMBOL, "limit": 5, "order": "desc"}, label="news")
    if r["ok"]:
        items = r["body"].get("results") or []
        print(f"  ✓ HTTP 200 — {len(items)} items")
        if items:
            print(f"  headline: {(items[0].get('title') or '')[:100]}")
        results["news"] = {"ok": True, "n": len(items)}
    else:
        print(f"  ✗ {r.get('status')} — {r.get('error', '')[:200]}")
        results["news"] = {"ok": False, "error": r.get("error")}

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for k, v in results.items():
        status = "✓" if v.get("ok") else "✗"
        extra = ""
        if v.get("ok"):
            if "bars" in v: extra = f"  ({v['bars']:,} bars)"
            elif "n_symbols" in v: extra = f"  ({v['n_symbols']:,} syms)"
            elif "n" in v: extra = f"  ({v['n']} items)"
            elif v.get("premarket_bars") is not None:
                extra = f"  (premkt={v['premarket_bars']}, after={v.get('afterhours_bars')})"
        else:
            extra = f"  → {(v.get('error') or '')[:80]}"
        print(f"  {status} {k:<14}{extra}")

    print("\nWritten: /tmp/massive_probe.json")
    with open("/tmp/massive_probe.json", "w") as f:
        json.dump(results, f, indent=2, default=str)


if __name__ == "__main__":
    probe()
