"""Bulk-warm the whales Mongo cache for every ticker in the latest scan.

Why this exists (2026-05-29): the bulk /supply-demand/whales-flow endpoint
reads from the per-ticker cache that the modal populates on click. After
a cache clear (e.g. to invalidate stale per-fund value/pct_held payload
shape), the bulk endpoint returns empty until users click each ticker —
which breaks the 🐋 Whales Accumulating filter on the SEPA page and the
🎯 Whales+Volume conviction chip's whale_score.

Usage:
    docker compose exec api python -m sepa.warm_whales
    docker compose exec api python -m sepa.warm_whales --top 50
    docker compose exec api python -m sepa.warm_whales --force      # force re-fetch even if cached

Runtime: ~1-2 sec per ticker (yfinance throughput limited). 231 tickers
= ~4-8 minutes. Run it after `whales._cache_coll().delete_many({})`
or any deploy that changes the whales payload shape.
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Optional


def main(top: Optional[int] = None, force: bool = False) -> None:
    from sepa import scanner
    from supply_demand import whales

    latest = scanner.load_latest() or {}
    all_results = latest.get("all_results") or []
    if not all_results:
        print("No latest scan found — run /sepa/scan first.")
        sys.exit(1)

    syms = [r["symbol"] for r in all_results if r.get("symbol")]
    if top is not None:
        syms = syms[: top]

    print(f"Warming whales cache for {len(syms)} tickers (force={force})...")
    t0 = time.time()
    ok = err = skipped = 0
    for i, sym in enumerate(syms):
        try:
            data = whales.get_whales(sym, force=force)
            if data and (data.get("moves") or {}).get("net_signal"):
                ok += 1
            else:
                skipped += 1
        except Exception as exc:
            err += 1
            if err <= 5:
                print(f"  {sym}: {exc}")
        if (i + 1) % 25 == 0 or i + 1 == len(syms):
            elapsed = time.time() - t0
            print(f"  {i + 1}/{len(syms)}  cached={ok} skipped={skipped} err={err}  {elapsed:.0f}s elapsed")
    print(f"Done in {time.time() - t0:.0f}s: {ok} cached, {skipped} no-data, {err} failed")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--top", type=int, default=None,
                   help="Only warm the top N tickers by score (default: all)")
    p.add_argument("--force", action="store_true",
                   help="Force re-fetch even if a fresh cache entry exists")
    args = p.parse_args()
    main(top=args.top, force=args.force)
