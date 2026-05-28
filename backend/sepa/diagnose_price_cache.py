"""Read-only diagnostic: inspect the Mongo price_cache for intraday-shaped bars.

Hypothesis (2026-05-27): commit 02c5a66 added `patch_latest_closes` which
appends today's bar from `bulk_snapshot` into the cached daily series. If
called during market hours, that bar is INTRADAY (partial day, wider H/L
range, lower volume) — which would silently corrupt VCP detection and
explain "only 1 candidate" symptom.

This script does NOT modify Mongo. It reads the last N bars of each symbol
in SAMPLE and prints a table so you can eyeball:
  - Does the last bar's date == today (US/Eastern)?
  - Is the last bar's range% materially wider than the median of prior bars?
  - Is the last bar's volume materially lower than the 50-bar avg?

Run from the api container so it can reach Mongo on the compose network:

    docker compose exec api python -m sepa.diagnose_price_cache

Optional override (one-shot, no edit):

    docker compose exec api python -m sepa.diagnose_price_cache \\
        --symbols MU,LRCX,AMAT,AMD,AEHR,ANET,ANTX,NVDA --bars 20

Or to print a single symbol's full tail:

    docker compose exec api python -m sepa.diagnose_price_cache --symbols MU --bars 50
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from statistics import median

# 18 names that passed 8/8 Trend Template + Stage 2 in the most recent cached
# scan (plus the one current candidate ANTX, plus a benchmark SPY). These are
# the ones we'd most expect to also have a VCP base; if they don't, the
# detector is misbehaving.
DEFAULT_SYMBOLS = [
    "MU", "LRCX", "AMAT", "AMD", "AEHR", "ANET", "NVDA", "AVGO",
    "ANTX", "SPY",
]


def _today_iso_et() -> str:
    """Today's date in US/Eastern as YYYY-MM-DD. Best effort if zoneinfo
    isn't available (older Python or stripped images)."""
    try:
        from zoneinfo import ZoneInfo  # py >=3.9
        return datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        # Fallback: assume container TZ is set to ET (docker-compose sets
        # TZ: America/New_York for both api and cron services).
        return datetime.now().date().isoformat()


def _connect():
    """Open a Mongo client. Honors MONGO_URL / MONGO_DB env vars."""
    from pymongo import MongoClient
    url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DB", "cheetah")
    client = MongoClient(url, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")
    return client[db_name].price_cache


def _bar_iso(b: dict) -> str:
    d = b.get("date")
    if d is None:
        return ""
    if hasattr(d, "date"):
        return d.date().isoformat()
    return str(d)[:10]


def _range_pct(b: dict) -> float | None:
    hi, lo, cl = b.get("high"), b.get("low"), b.get("close")
    if not hi or not lo or not cl:
        return None
    try:
        return round((float(hi) - float(lo)) / float(cl) * 100, 2)
    except Exception:
        return None


def _fmt(v, w=10, prec=2):
    if v is None:
        return "n/a".ljust(w)
    if isinstance(v, float):
        return f"{v:.{prec}f}".ljust(w)
    return str(v).ljust(w)


def inspect_symbol(coll, symbol: str, n_bars: int, today: str) -> dict:
    """Print last `n_bars` bars for one symbol. Returns a small summary
    dict for the rollup table."""
    doc = coll.find_one({"symbol": symbol.upper()})
    if not doc:
        print(f"\n{symbol}: NO CACHE ENTRY")
        return {"symbol": symbol, "status": "no_cache"}

    bars = doc.get("bars") or []
    cached_at = doc.get("cached_at")
    if not bars:
        print(f"\n{symbol}: cache doc exists but bars empty")
        return {"symbol": symbol, "status": "empty"}

    tail = bars[-n_bars:]
    print(f"\n=== {symbol} ({len(bars)} bars total, last {len(tail)} shown; cached_at={cached_at}) ===")
    print(f"{'date':12} {'open':>10} {'high':>10} {'low':>10} {'close':>10} {'volume':>14} {'range%':>8} {'today?':>7}")
    for b in tail:
        iso = _bar_iso(b)
        is_today = "★" if iso == today else ""
        print(
            f"{iso:12} "
            f"{_fmt(b.get('open'), 10):>10} "
            f"{_fmt(b.get('high'), 10):>10} "
            f"{_fmt(b.get('low'), 10):>10} "
            f"{_fmt(b.get('close'), 10):>10} "
            f"{_fmt(b.get('volume'), 14, 0):>14} "
            f"{_fmt(_range_pct(b), 8):>8} "
            f"{is_today:>7}"
        )

    # Quick numerical comparison: last-bar range% vs median of prior bars,
    # last-bar volume vs avg of prior bars.
    last = bars[-1]
    last_iso = _bar_iso(last)
    last_range = _range_pct(last)
    last_vol = last.get("volume")

    prior = bars[-51:-1] if len(bars) >= 51 else bars[:-1]
    prior_ranges = [r for r in (_range_pct(b) for b in prior) if r is not None]
    prior_vols = [float(b["volume"]) for b in prior if b.get("volume")]
    med_range = round(median(prior_ranges), 2) if prior_ranges else None
    avg_vol = round(sum(prior_vols) / len(prior_vols), 0) if prior_vols else None

    range_ratio = (
        round(last_range / med_range, 2) if last_range and med_range else None
    )
    vol_ratio = (
        round(float(last_vol) / avg_vol, 2) if last_vol and avg_vol else None
    )

    print(
        f"  → last bar date={last_iso} | range%={last_range} (median prior 50 = {med_range}, ratio={range_ratio})"
        f" | vol_ratio={vol_ratio}"
    )

    flags = []
    if last_iso == today:
        flags.append("LAST_BAR_IS_TODAY")
    if range_ratio is not None and range_ratio >= 1.5:
        flags.append(f"WIDE_RANGE_x{range_ratio}")
    if vol_ratio is not None and vol_ratio <= 0.4:
        flags.append(f"LOW_VOL_x{vol_ratio}")
    if flags:
        print(f"  ⚠ {' '.join(flags)}")

    return {
        "symbol":      symbol,
        "status":      "ok",
        "last_date":   last_iso,
        "is_today":    last_iso == today,
        "range_pct":   last_range,
        "range_ratio": range_ratio,
        "vol_ratio":   vol_ratio,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Inspect price_cache for intraday-shaped bars.")
    p.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS),
                   help="Comma-separated symbols (default: trend-template passers + ANTX + SPY)")
    p.add_argument("--bars", type=int, default=15,
                   help="How many tail bars to print per symbol (default 15)")
    args = p.parse_args(argv)

    today = _today_iso_et()
    print(f"Today (ET): {today}")
    print(f"UTC now:    {datetime.now(timezone.utc).isoformat()}")

    try:
        coll = _connect()
    except Exception as exc:
        print(f"ERROR: cannot connect to Mongo: {exc}", file=sys.stderr)
        print("Hint: run this inside the api container (docker compose exec api ...)", file=sys.stderr)
        sys.exit(2)

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    results = []
    for sym in symbols:
        try:
            results.append(inspect_symbol(coll, sym, args.bars, today))
        except Exception as exc:
            print(f"\n{sym}: inspection failed: {exc}", file=sys.stderr)

    # Rollup
    print("\n=== ROLLUP ===")
    print(f"{'symbol':10} {'last_date':12} {'today?':>7} {'range%':>8} {'r_ratio':>8} {'v_ratio':>8}")
    for r in results:
        if r.get("status") != "ok":
            print(f"{r['symbol']:10} {r.get('status','?')}")
            continue
        print(
            f"{r['symbol']:10} {r['last_date']:12} {'★' if r['is_today'] else '':>7} "
            f"{_fmt(r['range_pct'], 8):>8} {_fmt(r['range_ratio'], 8):>8} {_fmt(r['vol_ratio'], 8):>8}"
        )

    n_today = sum(1 for r in results if r.get("is_today"))
    n_wide = sum(1 for r in results if (r.get("range_ratio") or 0) >= 1.5)
    n_lowvol = sum(1 for r in results if 0 < (r.get("vol_ratio") or 1) <= 0.4)
    print(f"\nSummary: {n_today}/{len(results)} have today's bar as last; "
          f"{n_wide} have wide-range last bar (≥1.5× median); "
          f"{n_lowvol} have low-vol last bar (≤0.4× avg).")

    if n_today >= 1 and (n_wide >= 1 or n_lowvol >= 1):
        print("\n→ Hypothesis SUPPORTED: at least one cached series has today's bar")
        print("  with anomalous range/volume, consistent with an intraday-shaped")
        print("  snapshot being appended by patch_latest_closes().")
    elif n_today == 0:
        print("\n→ No today-bars cached: real-time patcher hasn't run yet, OR cache")
        print("  is older than today. VCP regression unlikely caused by intraday bar.")
    else:
        print("\n→ Today bars present but ranges/volumes look normal — intraday-bar")
        print("  hypothesis weakened. Look elsewhere (universe gating, swing window).")


if __name__ == "__main__":
    main()
