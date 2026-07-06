"""SOIR scanner — runs SOIR computation across the SEPA candidate universe.

Designed to be invoked by cron (overnight + post-close). Results are
persisted to Mongo; the API + frontend read from there.

Universe construction (mode-driven, mirrors SEPA):
  • "curated"     — ~150 hand-picked names (default)
  • "sp500"       — S&P 500 holdings
  • "russell1000" — ~1000 Russell 1000 names (full coverage)
  • "expanded"    — curated ∪ S&P 500
  Plus always: latest SEPA candidates + watchlist primaries.

Parallelism: HTTP fetches are I/O-bound. We use a ThreadPoolExecutor
with bounded concurrency.

Data source priority:
  1. Massive (Polygon.io shape) — paid, 1 HTTP call per ticker for the
     full chain. Used when MASSIVE_API_KEY is set. Rate limit on the
     developer plan is ~100 req/sec, so 10-20 workers is comfortable.
  2. yfinance fallback — free, 3 HTTP calls per ticker. Throttles around
     5-10 req/sec per IP, so workers should stay ≤ 10.

A 1000-ticker scan via Massive completes in ~60-90s; via yfinance ~3-5min.
"""
from __future__ import annotations

import logging
import os
from massive_keys import options_key
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional

from . import soir

log = logging.getLogger("options.scanner")

# Concurrency.
#  • With Massive (1 HTTP call/ticker, ~100 req/s plan limit): 20 workers safe
#  • With yfinance fallback (3 calls/ticker, ~5-10 req/s before throttle): 10 max
# We pick a value that's safe for both, override with SOIR_WORKERS env.
DEFAULT_WORKERS = int(os.getenv(
    "SOIR_WORKERS",
    "20" if options_key() else "10",
))

# Hard ceiling — never burn more than this many ticker fetches per run.
# Override per-run via the run() arg.
DEFAULT_MAX_UNIVERSE = int(os.getenv("SOIR_MAX_UNIVERSE", "1100"))

# Always-include core (S&P megacaps for cross-section percentile bootstrap +
# index ETFs as macro context).
CORE_TICKERS = [
    "SPY", "QQQ", "IWM", "DIA",
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
    "AVGO", "AMD", "TSM", "NFLX", "JPM", "BRK-B", "V", "MA", "UNH",
]


def _always_include_symbols() -> list[str]:
    """Portfolio holdings (all users) + the SEPA file-watchlist. Best-effort:
    each source degrades to empty on failure, never blocks the scan."""
    out: list[str] = []
    try:
        from portfolio.store import _get_db
        db = _get_db()
        if db is not None:
            out.extend(db.portfolio_holdings.distinct("ticker"))
    except Exception as exc:
        log.debug("portfolio symbols skipped: %s", exc)
    try:
        from sepa import scanner as sepa_scanner
        out.extend((x.get("symbol") or "") for x in sepa_scanner.load_watchlist())
    except Exception as exc:
        log.debug("sepa file-watchlist skipped: %s", exc)
    return [t.upper() for t in out if t and t.strip()]


def _build_universe(mode: Optional[str] = None,
                    max_size: int = DEFAULT_MAX_UNIVERSE) -> list[tuple[str, Optional[dict]]]:
    """Assemble (symbol, sepa_record_or_None) pairs to scan.

    Order of preference (deduplicated as we go):
      1. SEPA scan candidates — full record passed through for trend / score
      2. Watchlist primaries
      3. Universe-mode names (curated / sp500 / russell1000 / expanded)
      4. Core mega-cap context names (last so they don't crowd out universe)
    """
    seen: set[str] = set()
    universe: list[tuple[str, Optional[dict]]] = []

    # 1. SEPA candidates — pass their full record so we can read trend + score.
    # These also seed the SEPA score / trend pillars cheaply.
    sepa_record_by_symbol: dict[str, dict] = {}
    try:
        from sepa import scanner as sepa_scanner
        latest = sepa_scanner.load_latest() or {}
        for c in (latest.get("all_results") or latest.get("candidates") or []):
            t = (c.get("symbol") or "").upper()
            if t:
                sepa_record_by_symbol[t] = c
        # Add candidates first (they're already prioritized)
        for c in (latest.get("candidates") or []):
            t = (c.get("symbol") or "").upper()
            if t and t not in seen:
                seen.add(t)
                universe.append((t, c))
    except Exception as exc:
        log.debug("sepa universe seed skipped: %s", exc)

    # 2. Watchlist primaries
    try:
        from watchlist import store as wl_store
        for entry in wl_store.list_entries():
            t = (entry.get("ticker") or "").upper()
            if t and t not in seen and entry.get("primary_ticker") is None:
                seen.add(t)
                rec = sepa_record_by_symbol.get(t)
                if not rec:
                    r = entry.get("research") or {}
                    rec = {
                        "symbol": t,
                        "price":  r.get("last_price"),
                        "score":  r.get("score"),
                    }
                universe.append((t, rec))
    except Exception as exc:
        log.debug("watchlist universe skipped: %s", exc)

    # 2b. Names the user actually OWNS or WATCHES — these must never go
    # stale regardless of universe mode (2026-07-06: AMBA/CRWV sat on
    # 5-week-old SOIR because they're outside russell1000 and outside the
    # competitor watchlist; their pop showed 79-88 pct put-crowding that the
    # nightly sweep never refreshed).
    for t in _always_include_symbols():
        if t not in seen:
            seen.add(t)
            universe.append((t, sepa_record_by_symbol.get(t)))

    # 3. Universe-mode bulk add (russell1000 by default for full SEPA parity)
    try:
        from sepa.universe import load_universe
        chosen_mode = mode or os.getenv("SOIR_UNIVERSE_MODE") \
                          or os.getenv("SEPA_UNIVERSE_MODE") \
                          or "russell1000"
        for sym in load_universe(chosen_mode):
            t = (sym or "").upper()
            if t and t not in seen:
                seen.add(t)
                universe.append((t, sepa_record_by_symbol.get(t)))
    except Exception as exc:
        log.warning("universe load failed: %s", exc)

    # 4. Core mega-caps (only if room left)
    for t in CORE_TICKERS:
        if t not in seen:
            seen.add(t)
            universe.append((t, sepa_record_by_symbol.get(t)))

    return universe[:max_size]


# Thread-local state — yfinance creates per-thread Session objects internally
# but we want to centralize logging counters.
_progress_lock = threading.Lock()


def run(universe_override: Optional[list[str]] = None,
        mode: Optional[str] = None,
        workers: int = DEFAULT_WORKERS,
        max_universe: int = DEFAULT_MAX_UNIVERSE,
        sleep_jitter_sec: float = 0.05) -> dict:
    """Execute one full SOIR scan. Returns summary dict.

    Args:
      universe_override: explicit list of symbols (skips _build_universe)
      mode: 'curated' | 'sp500' | 'russell1000' | 'expanded' (default: env or russell1000)
      workers: parallel HTTP fetch concurrency
      max_universe: hard cap on tickers fetched
      sleep_jitter_sec: small randomized pause inside each worker to
        smooth request bursts and reduce yfinance rate-limit hits
    """
    started_at = time.time()
    if universe_override:
        # Even when caller specifies an explicit ticker list, look up each
        # ticker's SEPA record so the trend + fundamental pillars get
        # populated. Without this, manual scans always classify NEUTRAL
        # because trend stays None.
        sepa_record_by_symbol: dict[str, dict] = {}
        try:
            from sepa import scanner as sepa_scanner
            latest = sepa_scanner.load_latest() or {}
            for c in (latest.get("all_results") or latest.get("candidates") or []):
                t = (c.get("symbol") or "").upper()
                if t:
                    sepa_record_by_symbol[t] = c
        except Exception as exc:
            log.debug("could not load SEPA records for override scan: %s", exc)
        symbols = [(s.upper(), sepa_record_by_symbol.get(s.upper())) for s in universe_override]
    else:
        symbols = _build_universe(mode=mode, max_size=max_universe)

    log.info("SOIR scan starting — universe=%d workers=%d mode=%s",
             len(symbols), workers, mode or "auto")

    snapshots: list[dict] = []
    failed: list[str] = []
    completed = {"n": 0}

    # Per-thread session storage for connection pool reuse. requests.Session
    # is not thread-safe for shared use, so we give each worker its own.
    _local = threading.local()

    def _get_session():
        s = getattr(_local, "session", None)
        if s is None:
            try:
                import requests
                s = requests.Session()
                _local.session = s
            except ImportError:
                s = None
        return s

    def _worker(item: tuple[str, Optional[dict]]) -> Optional[dict]:
        sym, sepa_rec = item
        # Tiny jitter to de-synchronize burst at worker pool start so we
        # don't trigger rate limiting on the first batch.
        if sleep_jitter_sec > 0:
            time.sleep(sleep_jitter_sec * (1 + (hash(sym) & 0xff) / 255.0))
        try:
            return soir.compute_for_symbol(
                sym, sepa_record=sepa_rec, session=_get_session(),
            )
        except Exception as exc:
            log.warning("worker %s failed: %s", sym, exc)
            return None
        finally:
            with _progress_lock:
                completed["n"] += 1
                if completed["n"] % 50 == 0:
                    log.info("SOIR progress: %d/%d (%.1f%%)",
                             completed["n"], len(symbols),
                             100.0 * completed["n"] / max(1, len(symbols)))

    # ThreadPoolExecutor: yfinance is HTTP-bound, threads parallelize the
    # waits efficiently. 10 workers × 3 reqs/ticker × ~3-5s/req converges
    # to ~3-5 min for 1000 tickers vs ~80 min sequential.
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="soir") as ex:
        futures = {ex.submit(_worker, item): item[0] for item in symbols}
        for fut in as_completed(futures):
            sym = futures[fut]
            rec = fut.result()
            if rec is None:
                failed.append(sym)
            else:
                snapshots.append(rec)

    # Bootstrap cross-section percentile for tickers without time-series
    # history yet. Ranks each ticker's current SOIR against the universe.
    all_soirs = [s["soir"] for s in snapshots if s.get("soir") is not None]
    for s in snapshots:
        if s.get("soir_percentile") is None and s.get("soir") is not None:
            xs_pct = soir._cross_section_percentile(s["symbol"], s["soir"], all_soirs)
            if xs_pct is not None:
                s["soir_percentile"] = xs_pct
                s["percentile_source"] = "cross_section"
                cls = soir._classify(xs_pct, s.get("trend"), s.get("sepa_score"))
                s["signal"] = cls["signal"]
                s["reason"] = cls["reason"] + " (cross-section bootstrap; "\
                              "will switch to time-series once 30+ days collected)"
                s["pillars"] = cls["pillars"]
        elif s.get("soir_percentile") is not None:
            s["percentile_source"] = "time_series"

    soir.save_latest(snapshots)

    bullish = sorted(
        [s for s in snapshots if s.get("signal") == "BULLISH"],
        key=lambda r: -(r.get("soir_percentile") or 0),
    )[:25]
    bearish = sorted(
        [s for s in snapshots if s.get("signal") == "BEARISH"],
        key=lambda r:  (r.get("soir_percentile") or 100),
    )[:25]
    watch = sorted(
        [s for s in snapshots if s.get("signal") == "WATCH"],
        key=lambda r: -(r.get("soir_percentile") or 0),
    )[:25]

    duration = round(time.time() - started_at, 1)
    summary = {
        "as_of":       datetime.now(timezone.utc).isoformat(),
        "scanned":     len(snapshots),
        "failed":      failed,
        "duration_sec": duration,
        "workers":     workers,
        "mode":        mode or os.getenv("SOIR_UNIVERSE_MODE") or os.getenv("SEPA_UNIVERSE_MODE") or "russell1000",
        "bullish":     bullish,
        "bearish":     bearish,
        "watch":       watch,
        "n_bullish":   len(bullish),
        "n_bearish":   len(bearish),
        "n_watch":     len(watch),
        "universe_size": len(symbols),
    }
    log.info("SOIR scan done — %d snapshots, %d failed, bullish=%d bearish=%d watch=%d in %.1fs",
             len(snapshots), len(failed), len(bullish), len(bearish), len(watch), duration)
    return summary


__all__ = ["run", "CORE_TICKERS", "DEFAULT_WORKERS", "DEFAULT_MAX_UNIVERSE"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s — %(message)s")
    import sys
    mode_arg = sys.argv[1] if len(sys.argv) > 1 else None
    result = run(mode=mode_arg)
    log.info("scan result: scanned=%d failed=%d duration=%.1fs",
             result["scanned"], len(result["failed"]), result["duration_sec"])
