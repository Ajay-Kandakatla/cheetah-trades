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

# Persist cron logs to the shared rotating file so silent failures leave a trail.
try:
    from observability.logsetup import install_file_handler as _install_file_handler
    from observability.logsetup import install_redaction as _install_redaction
    _install_file_handler()
    _install_redaction()
except Exception:
    pass


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

    sub.add_parser(
        "stage-out-alerts",
        help="Check live prices vs MA50/MA200 for Stage-2 candidates and fire alerts",
    )

    s_pb = sub.add_parser(
        "pullback-scan",
        help="Pre-warm the Pullback-to-MA list (Stage-2 pullbacks toward the "
             "50-day MA) from the latest scan",
    )
    s_pb.add_argument("--top-n", type=int, default=50,
                      help="How many top-ranked picks to keep in the artifact")

    s_ha = sub.add_parser(
        "health-audit",
        help="Fail-safe health audit — checks critical data fired + app logs, "
             "pushes the owner on a silent failure",
    )
    s_ha.add_argument("--digest", action="store_true",
                      help="Send a summary push even when healthy (the 2-day digest)")

    sub.add_parser(
        "market-gauge-preopen",
        help="Recompute the Market Gauge pre-open (8:30am ET) with the SPY/QQQ "
             "ETF pre-market gap + weekly read, and persist it so the nav badge "
             "shows the morning read all day",
    )

    sub.add_parser(
        "fear-greed-refresh",
        help="Refresh CNN's Fear & Greed index into Mongo so the Market Gauge "
             "page's dial serves instantly (market-hours cron)",
    )

    sub.add_parser(
        "macro-indicators-refresh",
        help="Refresh the FRED macro dashboard (CPI/Core CPI/unemployment/Fed "
             "funds/yield curve + trends + next-release dates) into Mongo (daily cron)",
    )

    sub.add_parser(
        "scalping-watch",
        help="SEPA-cross tape watch tick: read every watched name's latest 5-min "
             "candle at its levels, push alerts on new alertable reads (deduped), "
             "and grade past alerts against the +30-min tape",
    )

    sub.add_parser(
        "scalping-paper-record",
        help="Record live scalping signals as forward paper trades with the real "
             "captured spread (every ~5 min in market hours)",
    )
    sub.add_parser(
        "scalping-paper-resolve",
        help="Resolve open scalping paper trades to stop/target/time-stop/EOD on "
             "the tape (every ~5 min in market hours + EOD)",
    )

    sub.add_parser(
        "breakout-audit",
        help="Integrity tripwire — re-derive 'broke out today' from raw bars "
             "(book p.203) vs the persisted scan; logs + exits nonzero on any "
             "discrepancy (run post-close after the fast-scan).",
    )

    sub.add_parser(
        "trade-flash-watch",
        help="Poll the demand/supply-board names for zone-tied tape bursts and "
             "push new ones (RTH only; one consolidated push per cycle).",
    )

    sub.add_parser(
        "zero-dte-record",
        help="Record today's 0DTE board to the ledger. Run DURING the session, "
             "not after it: the suggestion has to be frozen while the chain is "
             "live, and grading is already blind to the intraday path.",
    )

    sub.add_parser(
        "zero-dte-resolve",
        help="Grade recorded 0DTE suggestions against the day's bar "
             "(post-close, once the price cache holds it).",
    )

    args = p.parse_args()

    if args.cmd == "breakout-audit":
        from . import breakout_audit
        rep = breakout_audit.audit_latest()
        if not rep.get("ok"):
            log.warning("breakout-audit: could not run (%s)", rep.get("error"))
            return 0
        if rep["clean"]:
            log.info("breakout-audit CLEAN — %d checked, %d flagged today, all confirmed",
                     rep["checked"], rep["flagged_today"])
            return 0
        log.warning("breakout-audit TRIPWIRE TRIPPED — false_positives=%s false_negatives=%s",
                    rep["false_positives"][:15], rep["false_negatives"][:15])
        return 1

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
        from . import alerts, price_alerts, pivot_alerts, pankaj_alerts
        pos = alerts.check_positions()
        pa = price_alerts.check_alerts()
        pv = pivot_alerts.check_pivot_alerts()
        pk = pankaj_alerts.check_pankaj_alerts()
        log.info("ALERTS — positions: fired=%d skipped=%d  price_alerts: fired=%d/%d  pivot: fired=%d  pankaj: fired=%d",
                 len(pos["fired"]), len(pos["skipped"]),
                 pa["fired"], pa["checked"], len(pv["fired"]), len(pk["fired"]))
        # Stamp the engine heartbeat so the UI can show a "paused" banner if this
        # job stops running (e.g. the host slept). Best-effort; never blocks.
        try:
            from observability.engine_heartbeat import beat
            beat("alerts")
        except Exception:
            pass
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

    if args.cmd == "stage-out-alerts":
        from . import alerts
        r = alerts.check_stage_outs()
        log.info("STAGE-OUTS — checked=%d fired=%s skipped=%s",
                 r.get("checked", 0), r.get("fired"), r.get("skipped"))
        return 0

    if args.cmd == "pullback-scan":
        from . import pullback_ma
        r = pullback_ma.run_and_persist(top_n=args.top_n)
        log.info("PULLBACK-MA — %d candidates from %d analyzed in %.1fs",
                 r.get("candidate_count", 0), r.get("universe_size", 0),
                 r.get("duration_sec", 0.0))
        for c in r.get("picks", [])[:10]:
            log.info("  %-6s  pullback=%.1f%% (%s)  fromMA50=%.1f%%  vol=%.2fx",
                     c["symbol"], c.get("pullback_pct") or 0,
                     c.get("pullback_band"), c.get("pct_from_ma50") or 0,
                     c.get("vol_ratio") or 0)
        return 0

    if args.cmd == "health-audit":
        from observability import health_audit
        r = health_audit.run_audit(alert=True, digest=bool(args.digest))
        log.info("HEALTH-AUDIT — status=%s critical=%d warn=%d (%d checks, %.1fs)",
                 r["status"], r["n_critical"], r["n_warn"], r["n_checks"],
                 r["duration_sec"])
        for c in r["checks"]:
            if not c["ok"]:
                log.warning("  %-18s [%s] %s", c["name"], c["severity"], c["detail"])
        return 0

    if args.cmd == "market-gauge-preopen":
        from . import market_gauge
        r = market_gauge.run_and_persist()
        w = r.get("weekly") or {}
        o = r.get("next_day_outlook") or {}
        log.info("MARKET-GAUGE PRE-OPEN — daily=%s (%s) weekly=%s (%s) | %s",
                 r.get("score"), r.get("state"),
                 w.get("score", "n/a"), w.get("state", "n/a"), o.get("label", ""))
        for wch in (o.get("watch") or []):
            log.info("  watch: %s", wch)
        return 0

    if args.cmd == "fear-greed-refresh":
        from . import fear_greed
        r = fear_greed.run_and_persist()
        if r.get("error"):
            log.warning("FEAR-GREED — feed unavailable (%s); kept last persisted", r["error"])
        else:
            log.info("FEAR-GREED — score=%s (%s) | prev_close=%s",
                     r.get("score"), r.get("rating"),
                     (r.get("previous") or {}).get("close", {}).get("value"))
        return 0

    if args.cmd == "macro-indicators-refresh":
        import macro_indicators
        r = macro_indicators.run_and_persist()
        for ind in r.get("indicators", []):
            log.info("MACRO — %-11s %s%s (chg %s, next %s)",
                     ind["id"], ind["value"], ind["unit"], ind["change"],
                     ind.get("next_release_label") or "—")
        return 0

    if args.cmd == "scalping-watch":
        from scalping import sepa_watch
        r = sepa_watch.run_watch()
        log.info("SCALPING-WATCH: %s", r)
        return 0

    if args.cmd == "scalping-paper-record":
        from scalping import paper
        r = paper.record_live()
        log.info("SCALPING-PAPER record: %s", r)
        return 0

    if args.cmd == "scalping-paper-resolve":
        from scalping import paper
        r = paper.resolve_open()
        log.info("SCALPING-PAPER resolve: %s", r)
        return 0

    if args.cmd == "trade-flash-watch":
        from orderflow import trade_flash
        r = trade_flash.run_watch()
        # A quiet tape produces zero events, so the events collection cannot
        # prove this job ran — the heartbeat is that proof. Same plumbing as
        # the alerts engine; read by health_audit.check_trade_flash_heartbeat
        # (2026-08-25: the pullback scan sat silently broken for 96h and the
        # ask was "make sure all scans are successful").
        try:
            from observability import engine_heartbeat
            engine_heartbeat.beat("trade_flash")
        except Exception:
            pass
        log.info("TRADE-FLASH watch: %s", r)
        return 0

    if args.cmd == "zero-dte-record":
        from options import zero_dte, zero_dte_history
        board = zero_dte.board(fresh=True)
        r = zero_dte_history.record_board(board)
        log.info("0DTE record: %s (session=%s, %s/%s tradeable)", r,
                 (board.get("session") or {}).get("state"),
                 board.get("with_contract"), board.get("with_chain"))
        return 0

    if args.cmd == "zero-dte-resolve":
        from options import zero_dte_history
        r = zero_dte_history.resolve_open()
        log.info("0DTE resolve: %s", r)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
