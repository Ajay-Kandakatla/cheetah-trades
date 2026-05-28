"""Read-only corruption survey of the Mongo price_cache.

After the 2026-05-27 fix to patch_latest_closes (TZ + overwrite), legacy
rows may still contain:
  (a) Future-dated bars — bars stamped with a date later than today (ET),
      from before the TZ normalization fix.
  (b) Partial-day bars — bars frozen during pre-market / early-morning
      that never got overwritten with end-of-day values. Manifest as
      anomalously low volume (<10% of the symbol's 50-bar median) on
      a recent trading day.

This script does NOT modify the database. It scans every symbol in
price_cache and prints:
  - count of future-dated bars
  - count of suspected partial-day bars (volume < 10% of 50-bar median)
  - list of the worst offenders (top 30 by # of corrupt bars)
  - aggregate stats so you can decide blast radius before running the
    companion repair script (separate file, not yet written).

Run from the api container:

    docker compose exec api python -m sepa.diagnose_cache_corruption

Or via stdin if the module isn't baked into the image yet:

    cat backend/sepa/diagnose_cache_corruption.py | docker compose exec -T api python -

The script intentionally has zero write paths; safe to run any time.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from statistics import median


def _today_iso_et() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        return datetime.now().date().isoformat()


def _connect():
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


def survey():
    today = _today_iso_et()
    coll = _connect()

    n_symbols = 0
    n_bars_total = 0
    n_future_bars = 0
    n_partial_vol_bars = 0
    n_symbols_with_future = 0
    n_symbols_with_partial = 0

    # Detail rollups
    worst_future:  list[tuple[str, int]] = []  # (symbol, future_count)
    worst_partial: list[tuple[str, int]] = []  # (symbol, partial_count)
    sample_future_dates: dict[str, list[str]] = {}  # symbol -> [iso, ...]

    cursor = coll.find({}, {"symbol": 1, "bars": 1})
    for doc in cursor:
        sym = doc.get("symbol") or "?"
        bars = doc.get("bars") or []
        if not bars:
            continue
        n_symbols += 1
        n_bars_total += len(bars)

        # ── Future-dated bars ─────────────────────────────────────────
        future_dates: list[str] = []
        for b in bars:
            iso = _bar_iso(b)
            if iso and iso > today:
                future_dates.append(iso)
        if future_dates:
            n_future_bars += len(future_dates)
            n_symbols_with_future += 1
            worst_future.append((sym, len(future_dates)))
            sample_future_dates[sym] = sorted(set(future_dates))[:5]

        # ── Partial-volume bars (recent trading days only) ────────────
        # Compare each of the last 60 bars' volume against the 50-bar
        # median of OLDER bars from the same series. Flag bars whose
        # volume is < 10% of that median (likely a pre-market partial
        # snapshot frozen as a daily bar).
        vols = [float(b["volume"]) for b in bars if b.get("volume")]
        if len(vols) >= 100:
            # Use bars[-110:-60] as the "normal" reference (avoiding the
            # potentially-corrupt recent window) and inspect bars[-60:].
            ref = vols[-110:-60]
            recent = bars[-60:]
            if ref:
                med_vol = median(ref)
                partial_count = 0
                for b in recent:
                    v = b.get("volume")
                    if v and med_vol > 0 and float(v) < 0.10 * med_vol:
                        partial_count += 1
                if partial_count > 0:
                    n_partial_vol_bars += partial_count
                    n_symbols_with_partial += 1
                    worst_partial.append((sym, partial_count))

    # ── Output ────────────────────────────────────────────────────────
    print(f"Today (ET): {today}")
    print(f"Symbols inspected: {n_symbols}")
    print(f"Total bars across all symbols: {n_bars_total}")
    print()
    print("── Future-dated bars (TZ bug fallout) ──")
    print(f"  Symbols affected: {n_symbols_with_future} / {n_symbols}")
    print(f"  Bars to repair:   {n_future_bars}")
    if worst_future:
        worst_future.sort(key=lambda t: -t[1])
        print(f"  Top 30 offenders:")
        for sym, cnt in worst_future[:30]:
            dates = ", ".join(sample_future_dates.get(sym, [])[:3])
            print(f"    {sym:8} {cnt} future bars  (e.g. {dates})")
    print()
    print("── Partial-volume bars (frozen pre-market snapshots) ──")
    print(f"  Symbols affected: {n_symbols_with_partial} / {n_symbols}")
    print(f"  Bars to repair:   {n_partial_vol_bars}")
    if worst_partial:
        worst_partial.sort(key=lambda t: -t[1])
        print(f"  Top 30 offenders:")
        for sym, cnt in worst_partial[:30]:
            print(f"    {sym:8} {cnt} partial-vol bars in last 60")
    print()
    print("── Recommendation ──")
    if n_future_bars == 0 and n_partial_vol_bars == 0:
        print("  Cache looks clean — TZ + overwrite fixes alone should be enough.")
    elif n_future_bars + n_partial_vol_bars < 100:
        print("  Small blast radius — a targeted force-refresh of the listed")
        print("  symbols will clean it up. Companion repair script can iterate")
        print("  those symbols and call _fetch() (the full 2-year refresh path)")
        print("  to overwrite their entire series.")
    else:
        print(f"  Material corruption ({n_future_bars + n_partial_vol_bars} bars).")
        print("  Easiest path: force a full refresh of the entire price_cache")
        print("  by clearing it and letting the next scan re-populate. The 20-h")
        print("  TTL will trigger a clean re-fetch on first read.")
        print("  CAUTION: full repop takes ~3-5 min on Russell 1000 and bursts")
        print("  Massive. Run off-hours.")


if __name__ == "__main__":
    try:
        survey()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Hint: run inside the api container so it can reach Mongo.", file=sys.stderr)
        sys.exit(2)
