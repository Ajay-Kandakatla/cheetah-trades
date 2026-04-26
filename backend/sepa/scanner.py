"""SEPA scanner — the orchestrator.

Responsibility: walk the universe, apply the gate stack, rank winners, and
persist a JSON result the UI / morning-brief can consume.

Gate stack (order matters — fail fast):
  1. Trend Template (all 8) — the non-negotiable
  2. RS Rank ≥ 70 (pref ≥ 80)
  3. Stage classifier returns Stage 2
  4. Volume: accumulation (up/down vol ≥ 1)
  5. Base: VCP detected OR Power Play detected
  6. Base count ≤ 3 (early/mid stage)
  7. Optional: market_context allows longs

Each candidate emits a compact dict suitable for serving to the frontend.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List

from . import (
    prices, trend_template, rs_rank, stage, volume, vcp,
    base_count, market_context, power_play, ipo_age, sell_signals, risk,
    adr, canslim, company_names,
)
from .universe import load_universe
from .catalyst import catalyst_for
from .insider import insider_activity

log = logging.getLogger("sepa.scanner")

CACHE_DIR = Path.home() / ".cheetah" / "scans"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
LATEST_PATH = CACHE_DIR / "latest.json"
WATCH_PATH = CACHE_DIR / "watchlist.json"


def _rating_label(score: float) -> str:
    """Map 0-100 composite to a human-readable rating tier."""
    if score >= 85: return "STRONG_BUY"
    if score >= 70: return "BUY"
    if score >= 60: return "WATCH"
    if score >= 40: return "NEUTRAL"
    return "AVOID"


# Composite score weights — each component contributes up to N points; total = 100.
# Weights chosen to bias toward Minervini's hard gates (Trend Template + RS), with
# bonus contribution from setup quality and fundamentals.
SCORE_WEIGHTS = {
    "trend_template": 30,   # 8/8 = 30, 7/8 = 26, 6/8 = 22 ...
    "rs_rank":        25,   # rs/99 * 25
    "stage_2":        10,
    "setup":          15,   # VCP or PowerPlay
    "fundamentals":   10,   # CANSLIM C+A+I checks
    "volume":          5,
    "liquidity_adr":   5,
}


def _analyze_symbol(symbol: str, rs_map: dict, *,
                    require_liquidity: bool = True,
                    require_min_adr: float = 0.0) -> Optional[dict]:
    df = prices.load_prices(symbol)
    if df is None or len(df) < 220:
        return None

    # ── Liquidity floor (institutional-grade) ────────────────────────────
    liq = adr.liquidity_check(df)
    if require_liquidity and not liq["liquid"]:
        return None  # cookstock-style floor: skip thinly traded names

    # ── ADR (volatility quality) ─────────────────────────────────────────
    adr_value = adr.adr_pct(df, period=20)
    if require_min_adr and adr_value is not None and adr_value < require_min_adr:
        return None

    tr = trend_template.evaluate(symbol, df)
    if tr is None:
        return None
    rs = rs_map.get(symbol)
    # Re-apply RS gate
    tr.checks["rs_rank_at_least_70"] = bool(rs and rs >= 70)
    tr.pass_all = all(tr.checks.values())
    tr.passed = sum(1 for v in tr.checks.values() if v)

    stg = stage.classify(df)
    vol = volume.analyze(df)
    vcp_info = vcp.detect(df)
    pp_info = power_play.detect(df)
    bc = base_count.count_bases(df)
    sells = sell_signals.evaluate(df)

    # ── Normalized composite 0-100 ───────────────────────────────────────
    score = 0.0
    # Trend template — partial credit per check passed
    score += SCORE_WEIGHTS["trend_template"] * (tr.passed / 8.0)
    # RS — up to 25 pts; require rs ≥ 70 to count any (book threshold)
    if rs and rs >= 70:
        score += SCORE_WEIGHTS["rs_rank"] * (min(rs, 99) / 99.0)
    # Stage 2 only
    if stg and stg.get("stage") == 2:
        score += SCORE_WEIGHTS["stage_2"]
    # Setup quality
    if vcp_info and vcp_info.get("has_base"):
        score += SCORE_WEIGHTS["setup"]
        if vcp_info.get("ideal_depth_range") and vcp_info.get("good_contraction_count"):
            score += 2  # quality bonus
    elif pp_info and pp_info.get("is_power_play"):
        score += SCORE_WEIGHTS["setup"] * 0.85  # PowerPlay slightly less strict
    # Volume confirmation
    if vol and vol.get("accumulation"):
        score += SCORE_WEIGHTS["volume"] * 0.5
    if vol and vol.get("high_vol_breakout"):
        score += SCORE_WEIGHTS["volume"] * 0.5
    # Liquidity / ADR bonus
    if liq["liquid"]:
        score += SCORE_WEIGHTS["liquidity_adr"] * 0.4
    if adr_value and adr_value >= 4.0:
        score += SCORE_WEIGHTS["liquidity_adr"] * 0.6
    # Base count penalty (late stage = exhaustion)
    if bc and bc.get("is_late_stage"):
        score -= 8

    score = max(0.0, min(score, 100.0))

    entry_setup = None
    if vcp_info and vcp_info.get("has_base"):
        entry_setup = {
            "type": "VCP",
            "pivot": vcp_info["pivot_buy_price"],
            "stop": vcp_info["suggested_stop"],
        }
    elif pp_info and pp_info.get("is_power_play"):
        entry_setup = {
            "type": "POWER_PLAY",
            "pivot": pp_info["pivot_buy_price"],
            "stop": pp_info["suggested_stop"],
        }

    return {
        "symbol": symbol,
        "name": company_names.name_for(symbol),
        "score": round(score, 1),
        "rating": _rating_label(score),
        "trend": tr.to_dict(),
        "rs_rank": rs,
        "stage": stg,
        "volume": vol,
        "vcp": vcp_info,
        "power_play": pp_info,
        "base_count": bc,
        "sell_signals": sells,
        "entry_setup": entry_setup,
        "adr_pct": adr_value,
        "liquidity": liq,
        "is_candidate": bool(
            tr.pass_all
            and stg and stg.get("stage") == 2
            and entry_setup is not None
            and (bc is None or not bc.get("is_late_stage"))
            and liq["liquid"]
        ),
    }


def scan_universe(symbols: Optional[List[str]] = None,
                  with_catalyst: bool = False,
                  persist: bool = True) -> dict:
    t0 = time.time()
    symbols = symbols or load_universe()
    # Exclude benchmarks from candidate list
    work = [s for s in symbols if s not in {"SPY", "QQQ", "IWM"}]

    log.info("Computing RS ranks over %d symbols...", len(work))
    rs_map = rs_rank.rs_ranks(work)

    # Warm company-name cache so each result can attach its long name without
    # paying a per-row yfinance lookup. Cached 30 days in Mongo.
    try:
        company_names.bulk_warm(work)
    except Exception as exc:
        log.warning("company_names bulk_warm skipped: %s", exc)

    results: List[dict] = []
    # Use a thread pool since yfinance + pandas are I/O + CPU mix
    with ThreadPoolExecutor(max_workers=8) as ex:
        for res in ex.map(lambda s: _analyze_symbol(s, rs_map), work):
            if res is not None:
                results.append(res)

    # Rank + cut to candidates
    results.sort(key=lambda x: x["score"], reverse=True)
    candidates = [r for r in results if r["is_candidate"]]

    # Market context
    mkt = market_context.market_state()

    # Optional catalyst/insider/fundamentals enrichment on top N candidates only
    if with_catalyst and candidates:
        top = candidates[:20]

        async def enrich_all() -> None:
            sem = asyncio.Semaphore(4)

            async def one(rec: dict) -> None:
                async with sem:
                    try:
                        rec["catalyst"] = await catalyst_for(rec["symbol"])
                    except Exception as exc:
                        log.warning("catalyst failed for %s: %s", rec["symbol"], exc)
                    try:
                        rec["insider"] = await insider_activity(rec["symbol"])
                    except Exception as exc:
                        log.warning("insider failed for %s: %s", rec["symbol"], exc)
                    # CANSLIM fundamentals (sync yfinance, run in thread)
                    try:
                        rec["fundamentals"] = await asyncio.to_thread(
                            canslim.fundamentals_for, rec["symbol"]
                        )
                        # Re-score with fundamentals bump
                        f = rec["fundamentals"]
                        if f and f.get("passed"):
                            bonus = SCORE_WEIGHTS["fundamentals"] * (f["passed"] / 3.0)
                            rec["score"] = round(min(100.0, rec["score"] + bonus), 1)
                            rec["rating"] = _rating_label(rec["score"])
                    except Exception as exc:
                        log.warning("fundamentals failed for %s: %s", rec["symbol"], exc)

            await asyncio.gather(*(one(r) for r in top))

        asyncio.run(enrich_all())
        # Re-sort after fundamentals bumps
        candidates.sort(key=lambda x: x["score"], reverse=True)

    payload = {
        "generated_at": int(time.time()),
        "duration_sec": round(time.time() - t0, 2),
        "universe_size": len(work),
        "analyzed": len(results),
        "candidate_count": len(candidates),
        "market_context": mkt,
        "candidates": candidates,
        "all_results": results,
    }
    if persist:
        LATEST_PATH.write_text(json.dumps(payload, default=str))
        log.info("Scan persisted to %s", LATEST_PATH)
        try:
            from sepa import history
            history.write_scan(payload)
        except Exception as exc:
            log.warning("history write skipped: %s", exc)
    return payload


def load_latest() -> Optional[dict]:
    if not LATEST_PATH.exists():
        return None
    try:
        return json.loads(LATEST_PATH.read_text())
    except Exception as exc:
        log.warning("failed to read latest scan: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Watchlist — user-tracked SEPA positions (symbol + entry + stop).
# ---------------------------------------------------------------------------
def load_watchlist() -> List[dict]:
    if not WATCH_PATH.exists():
        return []
    try:
        return json.loads(WATCH_PATH.read_text())
    except Exception:
        return []


def save_watchlist(items: List[dict]) -> None:
    WATCH_PATH.write_text(json.dumps(items, default=str))


def add_to_watchlist(symbol: str, entry: float, stop: float,
                     shares: float = 0.0) -> List[dict]:
    items = load_watchlist()
    items = [x for x in items if x["symbol"] != symbol.upper()]
    items.append({
        "symbol": symbol.upper(),
        "entry": entry,
        "stop": stop,
        "shares": shares,
        "added": int(time.time()),
    })
    save_watchlist(items)
    return items


def remove_from_watchlist(symbol: str) -> List[dict]:
    items = [x for x in load_watchlist() if x["symbol"] != symbol.upper()]
    save_watchlist(items)
    return items
