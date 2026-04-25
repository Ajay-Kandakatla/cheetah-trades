"""SEPA command-line entrypoints — invoked by launchd cron jobs.

Usage:
    python -m sepa.cli scan       # 5pm post-close full SEPA scan
    python -m sepa.cli brief      # 8:30am morning brief
    python -m sepa.cli rescan SYM # refresh a single ticker in the scan cache
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("sepa.cli")


def main() -> int:
    p = argparse.ArgumentParser(prog="sepa.cli")
    sub = p.add_subparsers(dest="cmd", required=True)

    s_scan = sub.add_parser("scan", help="Run full SEPA scan across the universe")
    s_scan.add_argument("--no-catalyst", action="store_true",
                        help="Skip catalyst + insider enrichment (faster)")
    s_scan.add_argument("--symbols", type=str, default=None,
                        help="Comma-separated override for universe")

    sub.add_parser("brief", help="Generate the morning brief from the latest scan")

    s_re = sub.add_parser("rescan", help="Refresh a single ticker")
    s_re.add_argument("symbol", type=str)

    args = p.parse_args()

    if args.cmd == "scan":
        from . import scanner
        syms = args.symbols.split(",") if args.symbols else None
        result = scanner.scan_universe(symbols=syms,
                                        with_catalyst=not args.no_catalyst)
        log.info("SCAN DONE — %d candidates from %d analyzed in %.1fs",
                 result["candidate_count"], result["analyzed"],
                 result["duration_sec"])
        for c in result["candidates"][:10]:
            setup = c.get("entry_setup") or {}
            log.info("  %-6s  score=%.1f  RS=%s  setup=%s  pivot=%s stop=%s",
                     c["symbol"], c["score"], c["rs_rank"],
                     setup.get("type"), setup.get("pivot"), setup.get("stop"))
        return 0

    if args.cmd == "brief":
        from . import brief
        result = brief.generate_brief()
        log.info("BRIEF READY — %d candidates, %d watchlist alerts, market=%s",
                 len(result.get("top_candidates") or []),
                 len(result.get("watchlist_alerts") or []),
                 (result.get("market_context") or {}).get("label"))
        return 0

    if args.cmd == "rescan":
        from . import prices, scanner
        prices.load_prices(args.symbol, force=True)
        # Refresh cached scan record for this symbol
        latest = scanner.load_latest() or {"candidates": [], "all_results": []}
        # Not a full rescan — just force a price refresh; next /sepa/scan rebuilds.
        log.info("price cache refreshed for %s", args.symbol)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
