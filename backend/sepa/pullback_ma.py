"""Pullback to Moving Average — Minervini Stage-2 pullback scanner.

Surfaces leaders in a CONFIRMED Stage-2 uptrend (Trend Template, book p.79)
that have just made a "natural reaction" — a brief, shallow pullback toward
the rising 50-day moving average on CONTRACTING volume. This is the
constructive re-entry Minervini calls "tennis ball" action (pp.237-238): a
healthy stock dips and is "met with support that pushes the stock to new
highs within just days."

Book grounding (Mark Minervini, *Trade Like a Stock Market Wizard*, 2013):

  - Trend Template qualifier (p.79): "The current stock price is trading
    above the 50-day moving average" (#5) and "The 50-day moving average is
    above both the 150-day and 200-day" (#4). We require that structural
    subset — price above a rising 50/150/200 stack — so every row is a
    genuine uptrending leader, not a falling knife.

  - Stage-2 footprint (p.72): "Volume spikes on big up days and big up weeks
    are contrasted by VOLUME CONTRACTIONS during normal price pullbacks." So
    a HEALTHY pullback happens on BELOW-average volume — the page's
    Vol Ratio < 1.0x test.

  - Natural reaction / tennis ball (pp.237-238): healthy pullbacks are
    "brief ... met with support." "Volume should contract during the
    pullback and then expand as the stock moves back into new highs."
    Shallow + dry = constructive; deep/heavy = an "egg", needs caution.

Reuses existing scan data, exactly like dual_momentum.py — NO change to the
daily money-path scan, no second universe fetch, no extra provider calls:

  - scanner.load_latest() supplies the universe, names, the already-computed
    50/150/200-day MAs (the `trend` dict) and RS rank.
  - Price-derived columns (recent-high pullback %, 20-day volume ratio,
    3-month return) come from the same Mongo-cached daily bars
    (prices.load_prices).

Configured thresholds NOT specified in the book — operationalized from the
user's "How to trade the Pullback to MA" spec (2026-06-05). They live here as
named constants and are documented as *configured* (not book-derived) in
docs/sepa/pullback_ma_methodology.md so they can be tuned without pretending
the precision came from Minervini:

  - Pullback bands: tight < 5%, mid 5-8%, deep > 8% (retrace from recent high)
  - "Recent high" window: 25 trading days (~5 weeks)
  - Volume average window: 20 trading days
  - Inclusion zone: price within +8% of the 50-day MA (the "pulled back
    TOWARD that level" requirement — above the line but not extended)
"""
from __future__ import annotations

import json
import logging
import time
from typing import Optional

from . import prices, company_names
from . import scanner as sepa_scanner
from .universe import load_universe

log = logging.getLogger("sepa.pullback_ma")

# ── Configured parameters (see module docstring + methodology doc) ───────────
RECENT_HIGH_LOOKBACK = 25      # trading days defining the "recent high"
VOL_AVG_LOOKBACK = 20          # spec: "current volume vs the 20-day average"
RS_LOOKBACK = 63               # ~3 months -> RS 3M (matches dual_momentum 3m)
PULLBACK_ZONE_CEILING = 8.0    # include names within +8% above the 50-day MA
MIN_PULLBACK_PCT = 0.5         # must have actually retraced from the recent high
BAND_TIGHT_MAX = 5.0           # tight pullback  < 5%   (spec)
BAND_MID_MAX = 8.0             # mid pullback   5-8%; deep > 8%  (spec)
VOL_HEALTHY_MAX = 1.0          # vol ratio < 1x = contracting (book p.72)
UNIVERSE_MODE = "sp500"        # scan the S&P 500 only (Ajay 2026-06-05)

# Cron pre-warm artifact — lives on the shared `cheetah-scans` volume next to
# latest.json so the `cron` container writes it and the `api` container reads
# it (docker-compose mounts cheetah-scans:/root/.cheetah into both).
ARTIFACT_PATH = sepa_scanner.CACHE_DIR / "latest_pullback.json"


def _return_pct(df, lookback_days: int) -> Optional[float]:
    """Percent change over `lookback_days` trading days (close-to-close)."""
    if df is None or len(df) < lookback_days + 1:
        return None
    start = float(df["close"].iloc[-lookback_days - 1])
    end = float(df["close"].iloc[-1])
    if start == 0:
        return None
    return round((end / start - 1.0) * 100.0, 2)


def _recent_high(df, lookback: int) -> Optional[float]:
    """Highest intraday high over the last `lookback` bars — the swing high the
    pullback is measured from ("retraced from its recent high")."""
    if df is None or len(df) < 2:
        return None
    window = df["high"].iloc[-lookback:]
    if window.empty:
        return None
    return float(window.max())


def _vol_ratio(df, lookback: int) -> Optional[float]:
    """Today's volume / the trailing `lookback`-day average volume. Below 1.0
    means the pullback is happening on contracting volume (book p.72)."""
    if df is None or len(df) < lookback + 1:
        return None
    avg = float(df["volume"].iloc[-lookback:].mean())
    last = float(df["volume"].iloc[-1])
    if avg <= 0:
        return None
    return round(last / avg, 2)


def _band(pullback_pct: Optional[float]) -> Optional[str]:
    """Classify pullback depth per the configured bands (spec)."""
    if pullback_pct is None:
        return None
    if pullback_pct < BAND_TIGHT_MAX:
        return "tight"
    if pullback_pct <= BAND_MID_MAX:
        return "mid"
    return "deep"


def _ma(trend: dict, key: str, df) -> Optional[float]:
    """Reuse the scanner's already-computed MA from the `trend` dict; fall back
    to recomputing from the cached bars if it's missing."""
    v = (trend or {}).get(key)
    if v:
        try:
            return float(v)
        except (TypeError, ValueError):
            pass
    win = {"ma50": 50, "ma150": 150, "ma200": 200}.get(key)
    if not win or df is None or len(df) < win:
        return None
    return float(df["close"].rolling(win).mean().iloc[-1])


def _evaluate_row(rec: dict) -> Optional[dict]:
    """Turn one scan record into a Pullback-to-MA row, or None if it isn't a
    Stage-2 name sitting in a pullback toward its 50-day MA."""
    sym = rec.get("symbol")
    if not sym:
        return None
    df = prices.load_prices(sym)
    if df is None or len(df) < 60:
        return None

    trend = rec.get("trend") or {}
    last_close = rec.get("last_close")
    if last_close is None:
        last_close = float(df["close"].iloc[-1])
    last_close = float(last_close)

    ma50 = _ma(trend, "ma50", df)
    ma150 = _ma(trend, "ma150", df)
    ma200 = _ma(trend, "ma200", df)
    if not (ma50 and ma150 and ma200):
        return None

    # ── Defined-uptrend gate (Trend Template structural subset, book p.79
    #    criteria 1, 2, 4, 5): price above a rising 50 > 150 > 200 stack. ──
    if not (last_close > ma50 and ma50 > ma150 > ma200 and last_close > ma200):
        return None

    pct_from_ma50 = round((last_close / ma50 - 1.0) * 100.0, 2)
    pct_from_ma200 = round((last_close / ma200 - 1.0) * 100.0, 2)

    # "Pulled back TOWARD the 50-day": above the line but inside the zone, not
    # extended far above it. (spec: % from MA50 close to 0% = most actionable)
    if pct_from_ma50 > PULLBACK_ZONE_CEILING:
        return None

    recent_high = _recent_high(df, RECENT_HIGH_LOOKBACK)
    if not recent_high or recent_high <= 0:
        return None
    pullback_pct = round(
        max(0.0, (recent_high - last_close) / recent_high * 100.0), 2
    )
    if pullback_pct < MIN_PULLBACK_PCT:
        return None  # still pinned to highs — hasn't reacted yet

    vol_ratio = _vol_ratio(df, VOL_AVG_LOOKBACK)
    rs_3m = (rec.get("dual_momentum") or {}).get("return_3m")
    if rs_3m is None:
        rs_3m = _return_pct(df, RS_LOOKBACK)

    band = _band(pullback_pct)
    vol_healthy = bool(vol_ratio is not None and vol_ratio < VOL_HEALTHY_MAX)
    rs_rank = rec.get("rs_rank")

    # ── Actionability score — ranking heuristic, not a book formula. Its
    #    INPUTS are book-grounded: proximity to the 50-day line (spec: "most
    #    actionable zone"), a tight/brief pullback (tennis ball, pp.237-238),
    #    contracting volume (p.72), and a still-positive 3-month trend
    #    ("in a definite uptrend before ... big advances", p.79). ──────────
    score = 0.0
    score += max(0.0, PULLBACK_ZONE_CEILING - pct_from_ma50) * 4.0
    if band == "tight":
        score += 25
    elif band == "mid":
        score += 12
    if vol_healthy:
        score += 20
    if vol_ratio is not None:
        score += max(0.0, VOL_HEALTHY_MAX - vol_ratio) * 10.0
    if rs_3m is not None and rs_3m > 0:
        score += 10
    if rs_rank:
        score += min(rs_rank, 99) / 99.0 * 10.0
    score = round(score, 2)

    return {
        "symbol": sym,
        "name": rec.get("name") or company_names.name_for(sym),
        "last_close": round(last_close, 2),
        "pullback_pct": pullback_pct,
        "pullback_band": band,
        "pct_from_ma50": pct_from_ma50,
        "pct_from_ma200": pct_from_ma200,
        "rs_3m": rs_3m,
        "rs_rank": rs_rank,
        "vol_ratio": vol_ratio,
        "vol_healthy": vol_healthy,
        "ma50": round(ma50, 2),
        "recent_high": round(recent_high, 2),
        "stage": (rec.get("stage") or {}).get("stage"),
        "is_sepa_candidate": bool(rec.get("is_candidate")),
        "score": score,
    }


def _config() -> dict:
    return {
        "universe": UNIVERSE_MODE,
        "recent_high_lookback": RECENT_HIGH_LOOKBACK,
        "vol_avg_lookback": VOL_AVG_LOOKBACK,
        "pullback_zone_ceiling_pct": PULLBACK_ZONE_CEILING,
        "bands": {"tight_max": BAND_TIGHT_MAX, "mid_max": BAND_MID_MAX},
        "vol_healthy_max": VOL_HEALTHY_MAX,
    }


def _universe_filter() -> set:
    """Symbols to keep — the S&P 500 set (UNIVERSE_MODE). The daily scan runs a
    BROAD universe (curated ∪ sp500 ∪ sp400); we narrow the pullback view to the
    index here so the page is S&P 500-only (Ajay 2026-06-05). An empty set means
    "no filter" so a one-off universe-load failure degrades to the full scan
    rather than a blank page."""
    try:
        return {str(s).upper() for s in load_universe(UNIVERSE_MODE)}
    except Exception as exc:
        log.warning("pullback_ma: %s universe load failed (%s) — not filtering",
                    UNIVERSE_MODE, exc)
        return set()


def compute(top_n: int = 20) -> dict:
    """Derive the Pullback-to-MA list from the latest persisted scan.

    Mirrors dual_momentum.compute(): pulls every analyzed name from
    scanner.load_latest(), recomputes the pullback/volume/return columns from
    cached bars, gates to Stage-2 names sitting in a pullback toward the
    50-day MA, and ranks by actionability.

    Returns { generated_at, config, rows, picks, universe_size,
              candidate_count, scan_generated_at, error? }.
    """
    t0 = time.time()
    latest = sepa_scanner.load_latest() or {}
    universe = latest.get("all_results") or []
    if not universe:
        log.warning("pullback_ma: no scan data — run /sepa/scan first")
        return {
            "generated_at": int(t0),
            "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)),
            "duration_sec": 0.0,
            "config": _config(),
            "rows": [],
            "picks": [],
            "universe_size": 0,
            "candidate_count": 0,
            "error": "no_scan",
        }

    keep = _universe_filter()           # S&P 500 only (UNIVERSE_MODE)
    rows: list[dict] = []
    considered = 0
    for rec in universe:
        if keep and (rec.get("symbol") or "").upper() not in keep:
            continue
        considered += 1
        try:
            row = _evaluate_row(rec)
        except Exception as exc:  # one bad symbol must not sink the scan
            log.debug("pullback_ma eval failed for %s: %s", rec.get("symbol"), exc)
            row = None
        if row:
            rows.append(row)

    # Closest-to-line / tightest / driest first (highest actionability).
    rows.sort(key=lambda r: -(r["score"] or 0))
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    picks = rows[: max(0, top_n)]

    return {
        "generated_at": int(time.time()),
        "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_sec": round(time.time() - t0, 2),
        "config": _config(),
        "rows": rows,
        "picks": picks,
        "universe_size": considered,
        "candidate_count": len(rows),
        "scan_generated_at": latest.get("generated_at"),
    }


def run_and_persist(top_n: int = 50) -> dict:
    """Compute + write the artifact to the shared scans volume. Called by the
    `sepa.cli pullback-scan` cron job after the post-close fast-scan."""
    payload = compute(top_n=top_n)
    try:
        ARTIFACT_PATH.write_text(json.dumps(payload, default=str))
        log.info(
            "pullback_ma persisted %d candidates to %s",
            payload.get("candidate_count", 0), ARTIFACT_PATH,
        )
    except Exception as exc:
        log.warning("pullback_ma persist failed: %s", exc)
    return payload


def load_latest_pullback() -> Optional[dict]:
    """Read the cron pre-warmed artifact, or None if it hasn't run yet."""
    if not ARTIFACT_PATH.exists():
        return None
    try:
        return json.loads(ARTIFACT_PATH.read_text())
    except Exception as exc:
        log.warning("pullback_ma artifact read failed: %s", exc)
        return None
