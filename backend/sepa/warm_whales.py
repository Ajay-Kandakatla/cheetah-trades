"""Bulk-warm the institutional 13F holder cache across the whole universe.

Ajay 2026-08-16: *"Can you run this for all the russel 300 and all the tickers
we have.. we have too keep updating."*

WHY THIS FILE HAD TO EXIST
--------------------------
`warm_whales_13d.py` opens with "Mirror of warm_whales.py" — but warm_whales.py
was never actually written. So `whales_cache` has been **lazy-only since day
one**: a ticker's 13F holders are fetched when someone opens that ticker's
modal, and never otherwise.

The consequence was invisible until the Q2 2026 roll. Measured 2026-08-16:
1,377 of 1,379 cached tickers were older than the 24h TTL, and a 40-ticker
sample showed **32 of 40 stale** — cached "Q1 2026" while a fresh fetch
returned Q2. The provider had rolled; nobody had asked it for those names. The
board was quietly showing a quarter-old picture of who owns what.

COST
----
Measured 0.17s per ticker against the provider, so ~3,700 names is roughly
10 minutes sequential — cheap enough to run on a schedule rather than hope
someone clicks. Concurrency is deliberately LOW (see WORKERS): the constraint
is the provider's tolerance, not our CPU, and a bulk job that gets us
rate-limited costs more than it saves.

WHAT "STALE" MEANS HERE
-----------------------
Not "old". 13F data changes exactly four times a year, so an entry cached six
weeks ago can be perfectly current. `--stale-only` (the default) skips any
ticker already reporting the quarter that `period_freshness` says should be
public, which after the first full sweep turns a 10-minute job into a
30-second one.
"""
from __future__ import annotations

import argparse
import logging
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

log = logging.getLogger("sepa.warm_whales")

# Low on purpose. The provider is an unofficial, unpaid endpoint; 4 concurrent
# readers finishes ~3,700 names in a few minutes and has not tripped throttling,
# whereas a wide pool risks a block that takes the whole feature down.
WORKERS = 4

# Small jitter between requests so we never present a perfectly regular
# machine-gun pattern to the provider.
JITTER_SEC = (0.02, 0.12)

# Hard wall-clock stop. A warm that overruns into the trading day competes with
# the live crons, so it gives up and reports instead of running forever.
DEFAULT_BUDGET_SEC = 45 * 60

PROGRESS_EVERY = 250


def universe() -> list:
    """Every ticker we might show a 13F panel for.

    `fetch_broad` is the widest net the app has — curated ∪ themes ∪ S&P 500 ∪
    S&P 400 ∪ Russell 3000 ∪ micro-caps ∪ ETFs — which is exactly the "all the
    tickers we have" Ajay asked for, and it already contains the Russell 3000.

    ETFs are removed. A fund does not file a 13F about itself, so the provider
    answers 404 ("No fundamentals data found for symbol: SPY") and the empty
    result is cached under the 1-hour empty-TTL, meaning every sweep would
    re-ask for the same nothing. Measured 2026-08-16: ~400 of them.
    """
    from sepa import universe as U
    syms = list(U.fetch_broad())
    try:
        etfs = set(U.fetch_etf_universe())
    except Exception:
        etfs = set()
    return [s for s in syms if s not in etfs]


def _is_current(ticker: str, expected: str, coll) -> bool:
    """True when the cached payload already reports `expected` or newer."""
    try:
        doc = coll.find_one({"ticker": ticker}, {"payload.period.dominant": 1})
    except Exception:
        return False
    dom = (((doc or {}).get("payload") or {}).get("period") or {}).get("dominant")
    return bool(dom and dom >= expected)


def warm(symbols: Optional[list] = None, *, force: bool = False,
         stale_only: bool = True, workers: int = WORKERS,
         budget_sec: float = DEFAULT_BUDGET_SEC,
         progress=None) -> dict:
    """Refetch 13F holders for `symbols` (default: the whole broad universe).

    Returns counts rather than raising: one bad ticker must not abort a sweep
    of several thousand.
    """
    from supply_demand import whales
    from observability import period_freshness as pf

    syms = list(symbols) if symbols is not None else universe()
    coll = whales._cache_coll()
    expected = pf.expected_13f_quarter().isoformat()

    todo = syms
    skipped_current = 0
    if stale_only and coll is not None and not force:
        todo = []
        for s in syms:
            if _is_current(s, expected, coll):
                skipped_current += 1
            else:
                todo.append(s)

    t0 = time.time()
    done = ok = failed = 0
    rolled = []

    def _one(sym: str):
        time.sleep(random.uniform(*JITTER_SEC))
        before = None
        if coll is not None:
            try:
                d = coll.find_one({"ticker": sym}, {"payload.period.dominant": 1})
                before = (((d or {}).get("payload") or {}).get("period") or {}).get("dominant")
            except Exception:
                before = None
        r = whales.get_whales(sym, force=True)
        after = ((r or {}).get("period") or {}).get("dominant")
        return sym, before, after

    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
        futures = {pool.submit(_one, s): s for s in todo}
        for fut in as_completed(futures):
            done += 1
            if time.time() - t0 > budget_sec:
                for f in futures:
                    f.cancel()
                log.warning("warm-whales: budget %.0fs exhausted after %d tickers",
                            budget_sec, done)
                break
            try:
                sym, before, after = fut.result()
                ok += 1
                if after and before != after:
                    rolled.append({"symbol": sym, "was": before, "now": after})
            except Exception as exc:
                failed += 1
                log.debug("warm-whales: %s failed: %s", futures[fut], exc)
            if progress and done % PROGRESS_EVERY == 0:
                progress(done, len(todo), time.time() - t0)

    took = round(time.time() - t0, 1)
    out = {
        "universe": len(syms),
        "attempted": len(todo),
        "skipped_already_current": skipped_current,
        "ok": ok,
        "failed": failed,
        "rolled_to_new_quarter": len(rolled),
        "expected_quarter": expected,
        "took_sec": took,
        "examples": rolled[:10],
    }
    log.info("warm-whales: %d/%d ok, %d failed, %d rolled forward, %d already "
             "current, %.0fs", ok, len(todo), failed, len(rolled),
             skipped_current, took)
    return out


def main(argv=None) -> int:                                  # pragma: no cover
    ap = argparse.ArgumentParser(description="Bulk-warm the 13F holder cache.")
    ap.add_argument("--top", type=int, default=None,
                    help="only the first N tickers (smoke test)")
    ap.add_argument("--all", action="store_true",
                    help="refetch every ticker, even ones already on the current quarter")
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--budget-sec", type=float, default=DEFAULT_BUDGET_SEC)
    args = ap.parse_args(argv)

    syms = universe()
    if args.top:
        syms = syms[: args.top]

    def _progress(done, total, el):
        rate = done / el if el else 0
        print(f"  {done}/{total}  {el:.0f}s  {rate:.1f}/s", flush=True)

    print(f"Warming 13F holders for {len(syms)} tickers "
          f"(stale_only={not args.all}, workers={args.workers})...", flush=True)
    res = warm(syms, stale_only=not args.all, workers=args.workers,
               budget_sec=args.budget_sec, progress=_progress)
    print(f"done: {res['ok']} ok, {res['failed']} failed, "
          f"{res['rolled_to_new_quarter']} rolled to a new quarter, "
          f"{res['skipped_already_current']} already current, {res['took_sec']}s")
    for ex in res["examples"]:
        print(f"   {ex['symbol']}: {ex['was']} -> {ex['now']}")
    return 0 if res["failed"] < max(10, 0.2 * max(res["attempted"], 1)) else 1


if __name__ == "__main__":                                   # pragma: no cover
    sys.exit(main())
