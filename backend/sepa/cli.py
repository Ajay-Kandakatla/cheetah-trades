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
    s_scan.add_argument("--mode", type=str, default=None,
                        help="Universe mode: curated / sp500 / russell1000 / expanded")

    s_fast = sub.add_parser("fast-scan",
                            help="Hot scan reusing the cached research blobs (20-30s)")
    s_fast.add_argument("--symbols", type=str, default=None)
    s_fast.add_argument("--mode", type=str, default=None)
    s_fast.add_argument("--no-fallback", action="store_true",
                        help="Skip symbols missing from the research cache "
                             "instead of falling back to full analysis")

    s_research = sub.add_parser(
        "research-refresh",
        help="Heavy weekly batch — refreshes research cache for the universe. "
             "Run on Sundays.",
    )
    s_research.add_argument("--symbols", type=str, default=None)
    s_research.add_argument("--mode", type=str, default=None)
    s_research.add_argument("--no-canslim", action="store_true",
                            help="Skip CANSLIM fundamentals (saves ~minutes)")
    s_research.add_argument("--workers", type=int, default=6)

    sub.add_parser("research-status", help="Print research cache freshness")

    sub.add_parser("brief", help="Generate the morning brief from the latest scan")
    sub.add_parser("alerts", help="Check positions and fire WhatsApp alerts")

    s_re = sub.add_parser("rescan", help="Refresh a single ticker")
    s_re.add_argument("symbol", type=str)

    s_vcp = sub.add_parser(
        "vcp-watch",
        help="Run a fast scan, diff against last run, notify on new VCP setups",
    )
    s_vcp.add_argument("--include-power-play", action="store_true",
                       help="Also alert on Power Play setups (looser than VCP).")
    s_vcp.add_argument("--mode", type=str, default=None,
                       help="Universe mode: curated/sp500/russell1000/expanded. "
                            "Defaults to SEPA_UNIVERSE_MODE env var.")

    s_jug = sub.add_parser(
        "juggernauts",
        help="Scan watchlist for accumulation + rising-momentum tickers and "
             "send the consolidated push if new names emerged today.",
    )
    s_jug.add_argument("--force", action="store_true",
                       help="Send push even when no NEW names emerged today.")
    s_jug.add_argument("--dry-run", action="store_true",
                       help="Compute and print the set, don't persist state "
                            "or fire a push.")

    args = p.parse_args()

    if args.cmd == "scan":
        from . import scanner
        from .universe import load_universe
        syms = args.symbols.split(",") if args.symbols else load_universe(args.mode)
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

    if args.cmd == "fast-scan":
        from . import scanner
        syms = args.symbols.split(",") if args.symbols else None
        result = scanner.scan_universe_fast(
            symbols=syms,
            universe_mode=args.mode,
            fallback_when_missing=not args.no_fallback,
        )
        log.info("FAST SCAN DONE — %d candidates from %d analyzed in %.1fs "
                 "(cache hits=%d misses=%d)",
                 result["candidate_count"], result["analyzed"],
                 result["duration_sec"],
                 result.get("research_cache_hits"),
                 result.get("research_cache_misses"))
        return 0

    if args.cmd == "research-refresh":
        from . import research
        from .universe import load_universe
        syms = args.symbols.split(",") if args.symbols else load_universe(args.mode)
        result = research.refresh_universe(
            syms,
            max_workers=args.workers,
            with_canslim=not args.no_canslim,
        )
        log.info("RESEARCH DONE — refreshed=%d failed=%d in %.1fs",
                 len(result["refreshed"]), len(result["failed"]),
                 result["duration_sec"])
        return 0

    if args.cmd == "research-status":
        from . import research
        log.info(json.dumps(research.status(), indent=2))
        return 0

    if args.cmd == "brief":
        from . import brief
        result = brief.generate_brief()
        log.info("BRIEF READY — %d candidates, %d watchlist alerts, market=%s",
                 len(result.get("top_candidates") or []),
                 len(result.get("watchlist_alerts") or []),
                 (result.get("market_context") or {}).get("label"))
        return 0

    if args.cmd == "alerts":
        from . import alerts, price_alerts
        pos = alerts.check_positions()
        pa = price_alerts.check_alerts()
        log.info("ALERTS — positions: fired=%d skipped=%d  price_alerts: fired=%d/%d",
                 len(pos["fired"]), len(pos["skipped"]),
                 pa["fired"], pa["checked"])
        return 0

    if args.cmd == "rescan":
        from . import prices, scanner
        prices.load_prices(args.symbol, force=True)
        # Refresh cached scan record for this symbol
        latest = scanner.load_latest() or {"candidates": [], "all_results": []}
        # Not a full rescan — just force a price refresh; next /sepa/scan rebuilds.
        log.info("price cache refreshed for %s", args.symbol)
        return 0

    if args.cmd == "vcp-watch":
        from . import vcp_watch
        result = vcp_watch.run(
            include_power_play=bool(args.include_power_play),
            universe_mode=args.mode,
        )
        kind = "VCP+PP" if args.include_power_play else "VCP"
        log.info(
            "VCP-WATCH — %s setups: %d total · %d new · %d cleared · "
            "notified=%d · %.1fs",
            kind, result["current_setups"], result["new_count"],
            result["cleared_count"], result["notified"], result["duration_sec"],
        )
        if result["new_symbols"]:
            log.info("  NEW: %s", ", ".join(result["new_symbols"]))
        if result["cleared_symbols"]:
            log.info("  CLEARED: %s", ", ".join(result["cleared_symbols"]))
        return 0

    if args.cmd == "juggernauts":
        from . import juggernaut
        r = juggernaut.scan(force_push=bool(args.force), dry_run=bool(args.dry_run))
        if not r.get("ok"):
            log.warning("JUGGERNAUT — skipped: %s", r.get("reason"))
            return 0
        log.info(
            "JUGGERNAUT — %d current · %d new · pushed=%d (%s)",
            len(r["juggernauts"]), len(r["new_today"]),
            r["pushed"], r["today_et"],
        )
        if r["new_today"]:
            log.info("  NEW: %s", ", ".join(r["new_today"]))
        for j in r["juggernauts"][:10]:
            log.info("    %s  ud=%s  todayVol=%.2f×  %s",
                     j["ticker"], j["ud_ratio"], j["today_vol_mult"],
                     j["momentum"])
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
