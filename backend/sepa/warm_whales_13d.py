"""Bulk-warm the SC 13D/G filings cache for every ticker in the latest scan.

Mirror of warm_whales.py but for the whales13d_cache Mongo collection.
Why this exists (2026-05-29): the bulk /supply-demand/13d-flow endpoint
reads from the per-ticker cache that the SEPA card chip + modal populate
on click. Without periodic pre-warming, the chip would never render on
SEPA cards because no one would have manually opened the modal first.

Usage:
    docker compose exec api python -m sepa.warm_whales_13d
    docker compose exec api python -m sepa.warm_whales_13d --top 50
    docker compose exec api python -m sepa.warm_whales_13d --force --days 180

Runtime: ~0.3 sec per ticker (SEC EDGAR is much faster than yfinance).
231 tickers = ~1-2 minutes. Safe to run from cron daily.
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Optional


def main(top: Optional[int] = None, force: bool = False, days: int = 120) -> None:
    from sepa import scanner
    from supply_demand import whales_13d

    latest = scanner.load_latest() or {}
    all_results = latest.get("all_results") or []
    if not all_results:
        print("No latest scan found — run /sepa/scan first.")
        sys.exit(1)

    syms = [r["symbol"] for r in all_results if r.get("symbol")]
    if top is not None:
        syms = syms[: top]

    print(f"Warming 13D/G cache for {len(syms)} tickers (force={force}, days={days})...")
    t0 = time.time()
    ok = with_filings = err = 0
    for i, sym in enumerate(syms):
        try:
            data = whales_13d.get_13d(sym, days=days, force=force)
            ok += 1
            if data.get("n_filings", 0) > 0:
                with_filings += 1
        except Exception as exc:
            err += 1
            if err <= 5:
                print(f"  {sym}: {exc}")
        if (i + 1) % 50 == 0 or i + 1 == len(syms):
            elapsed = time.time() - t0
            print(f"  {i + 1}/{len(syms)}  ok={ok} with_filings={with_filings} err={err}  {elapsed:.0f}s elapsed")
    print(f"Done in {time.time() - t0:.0f}s: {ok} cached, {with_filings} had filings, {err} failed")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--top", type=int, default=None,
                   help="Only warm the top N tickers by score (default: all)")
    p.add_argument("--force", action="store_true",
                   help="Force re-fetch even if a fresh cache entry exists")
    p.add_argument("--days", type=int, default=120,
                   help="Lookback window in days (default: 120)")
    args = p.parse_args()
    main(top=args.top, force=args.force, days=args.days)
