"""Daily, throttled warmer for yfinance-backed company metadata.

The scan path is cache-only now (no live yfinance), so company names + business
descriptions are filled here instead — once a day, slowly, so Yahoo doesn't
rate-limit us into a 429 storm (2026-05-31). Both layers skip names that are
already cached, so re-runs are cheap and resumable.

Run:
    python -m sepa.warm_names                 # whole broad universe
    python -m sepa.warm_names --delay 2.0     # gentler
    python -m sepa.warm_names --names-only

Cron (daily, before the morning scan), in backend/crontab:
    0 17 * * * /usr/local/bin/python -m sepa.warm_names
"""
from __future__ import annotations

import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sepa.warm_names")


def main() -> None:
    ap = argparse.ArgumentParser(description="Warm company names + descriptions (throttled).")
    ap.add_argument("--delay", type=float, default=1.5,
                    help="Seconds between yfinance calls (default 1.5).")
    ap.add_argument("--mode", default="broad",
                    help="Universe mode to warm (default broad).")
    ap.add_argument("--names-only", action="store_true",
                    help="Skip the description backfill.")
    ap.add_argument("--descriptions-only", action="store_true",
                    help="Skip the name warm.")
    args = ap.parse_args()

    from . import universe, company_names
    syms = universe.load_universe(args.mode)
    log.info("warm_names: %d symbols (mode=%s, delay=%.1fs)", len(syms), args.mode, args.delay)

    if not args.descriptions_only:
        res = company_names.bulk_warm(syms, fetch=True, throttle_sec=args.delay)
        filled = sum(1 for v in res.values() if v)
        log.info("warm_names: names — %d resolved / %d total", filled, len(res))

    if not args.names_only:
        try:
            from companies import store as companies_store
            stats = companies_store.backfill_descriptions(syms, delay_sec=args.delay)
            log.info("warm_names: descriptions — %s", stats)
        except Exception as exc:
            log.warning("warm_names: description backfill failed: %s", exc)


if __name__ == "__main__":
    main()
