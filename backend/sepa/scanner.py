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
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List

# Scan parallelism — the per-symbol analyze is an I/O (Mongo price reads) + CPU
# (pandas) mix, so we oversubscribe the cores. Defaults to 2× CPU count (capped
# 32) instead of the old hardcoded 8, which left a big multi-core box idle.
# Override with SEPA_SCAN_WORKERS to tune for the host (e.g. the M5 Pro).
_SCAN_WORKERS = int(os.getenv("SEPA_SCAN_WORKERS", "0") or 0) or min(32, (os.cpu_count() or 8) * 2)
# Retries are for rate-limited/transient failures — keep that pass gentle so we
# don't re-hammer the same flaky source.
_SCAN_RETRY_WORKERS = max(2, _SCAN_WORKERS // 8)

from .progress import ProgressEmitter

from . import (
    prices, trend_template, rs_rank, stage, volume, vcp,
    base_count, market_context, power_play, ipo_age, sell_signals, risk,
    adr, canslim, company_names, research as research_mod,
    dual_momentum as dm, etf_info, pioneers, venky_filters,
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


def _determine_setup(vcp_info, pp_info, vol, last_px):
    """Entry setup + score multipliers (book pp.198-205, p.203).

    Priority: VCP base > Power Play > volume-confirmed breakout with NO detected
    base. Book p.203: the buy point IS the breakout above the pivot on EXPANDING
    volume (a pocket pivot is the in-base institutional buy). So a Stage-2 leader
    breaking out on volume is a valid setup even when the base detector didn't
    catch the consolidation shape — it often resolves INTO the breakout (e.g.
    DDOG). Returns (entry_setup|None, base_mult, risk_mult, risk_to_stop_pct).
    """
    entry_setup = None
    base_mult = 0.0
    if vcp_info and vcp_info.get("has_base"):
        entry_setup = {"type": "VCP", "pivot": vcp_info["pivot_buy_price"], "stop": vcp_info["suggested_stop"]}
        base_mult = 1.0
    elif pp_info and pp_info.get("is_power_play"):
        entry_setup = {"type": "POWER_PLAY", "pivot": pp_info["pivot_buy_price"], "stop": pp_info["suggested_stop"]}
        base_mult = 0.85
    elif vol and (vol.get("high_vol_breakout") or vol.get("pocket_pivot")):
        pp_only = bool(vol.get("pocket_pivot") and not vol.get("high_vol_breakout"))
        entry_setup = {
            "type": "POCKET_PIVOT" if pp_only else "BREAKOUT",
            "pivot": round(last_px, 2),
            "stop": round(last_px * 0.92, 2),   # tight 8% Minervini-discipline stop
        }
        base_mult = 0.70

    # Risk-to-stop: a proper entry has a TIGHT stop (Minervini cut-loss ~7-8%,
    # max ~10%). Scale the setup credit DOWN as the stop widens — a 25% stop is
    # barely a setup (it was letting an un-triggered Power Play top the rank).
    risk_mult = 1.0
    risk_to_stop_pct = None
    if entry_setup and entry_setup.get("pivot") and entry_setup.get("stop"):
        p, s = entry_setup["pivot"], entry_setup["stop"]
        if p and p > 0:
            risk_to_stop_pct = round((p - s) / p * 100, 1)
            if risk_to_stop_pct <= 8:
                risk_mult = 1.0
            elif risk_to_stop_pct <= 12:
                risk_mult = 0.80
            elif risk_to_stop_pct <= 18:
                risk_mult = 0.55
            else:
                risk_mult = 0.30
    return entry_setup, base_mult, risk_mult, risk_to_stop_pct


def _is_setup_ready(tr, stg, bc, liq, entry_setup) -> bool:
    """The book buy-now gate MINUS the volume-breakout trigger (pp.79-83, 198):
    Trend Template + Stage 2 advancing + a setup + not a late-stage base +
    liquid. A name that is_setup_ready is sitting in a proper base one
    volume-confirmed breakout away from is_buyable — the "ready, waiting for the
    trigger" tier. Exposed so the FE 'Breakout: ≤1wk / Any' toggle can relax the
    strict SAME-DAY breakout requirement (the breakout may have fired earlier in
    the week, or the user may want the ready set without a trigger gate)."""
    return bool(
        tr.pass_all
        and stg and stg.get("stage") == 2
        and entry_setup is not None
        and (bc is None or not bc.get("is_late_stage"))
        and liq.get("liquid")
    )


def _is_buyable(tr, stg, bc, liq, vol, entry_setup) -> bool:
    """Book buy-now gate (pp.79-83, 198-203): `_is_setup_ready` PLUS a TODAY
    VOLUME-CONFIRMED breakout (high_vol_breakout or pocket_pivot, p.203). This
    is the canonical strict gate and is intentionally unchanged."""
    return bool(
        _is_setup_ready(tr, stg, bc, liq, entry_setup)
        and vol and (vol.get("high_vol_breakout") or vol.get("pocket_pivot"))
    )


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


# ── Institutional-sponsorship ranking penalty (Minervini p.195) ──────────────
# The book: "limit your selections to those displaying evidence of being
# supported by institutional buying" (p.195). Thin names can't be accumulated
# by institutions and are the easily-manipulated single-digit stocks. The book
# gives the CONCEPT but NO dollar threshold, and uses NO nominal share-price
# floor (its "Cheap Trap", p.43, is about VALUATION, not share price). So we
# rank-demote by average daily DOLLAR-volume in tiers. Bands are our
# codification, user-approved 2026-05-31 ("tiered bands; stay book-pure, no
# price floor"). Applied as a post-sum penalty (like the late-stage −8), so the
# SCORE_WEIGHTS contract (§4, sums to 100) is unchanged.
SPONSORSHIP_TIERS = [
    (100_000_000.0,  0.0),   # ≥ $100M/day — full institutional sponsorship
    ( 20_000_000.0,  4.0),   # $20M–$100M  — minor demotion
    (  5_000_000.0, 10.0),   # $5M–$20M    — moderate (light sponsorship)
    (          0.0, 18.0),   # < $5M       — heavy (thin/manipulable; CVGI ≈ $2.3M)
]


def _sponsorship_penalty(avg_dollar_vol: Optional[float]) -> float:
    """Rank demotion for names lacking institutional sponsorship (book p.195).

    Tiered by average daily dollar-volume. Returns 0.0 when liquidity is
    unknown (don't punish missing data) or for genuinely liquid leaders.
    """
    if avg_dollar_vol is None:
        return 0.0
    for floor, penalty in SPONSORSHIP_TIERS:
        if avg_dollar_vol >= floor:
            return penalty
    return 0.0


# SPY's 12-month return — cached at scan start. dual_momentum.metrics_for_df
# uses this to compute the per-ticker `beats_spy` flag without each worker
# re-loading SPY's price file. Reset by scan_universe / scan_universe_fast.
_SPY_12M_RETURN: Optional[float] = None


def _refresh_spy_baseline() -> Optional[float]:
    """Compute SPY's 12m return once at scan start; stash for per-symbol use."""
    global _SPY_12M_RETURN
    try:
        _SPY_12M_RETURN = dm._benchmark_return("SPY", 252)
    except Exception as exc:
        log.warning("scanner: SPY 12m baseline fetch failed (%s)", exc)
        _SPY_12M_RETURN = None
    return _SPY_12M_RETURN


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

    # ── Day change (last close vs prior close, %) ────────────────────────
    # Used for the "Sort: Day %" filter and the daily-mover badge on cards.
    day_change_pct = None
    last_close = None
    try:
        if len(df) >= 2:
            last = float(df["close"].iloc[-1])
            prev = float(df["close"].iloc[-2])
            last_close = round(last, 2)
            if prev > 0:
                day_change_pct = round((last / prev - 1) * 100, 2)
    except Exception:
        pass

    # ── Dual Momentum metrics (Antonacci) ────────────────────────────────
    # 1m/3m/6m/12m returns + abs_mom_pass + beats_spy. Computed from the same
    # df we already loaded — zero extra fetches. Surfaces sort/filter on the
    # SEPA page without users having to bounce to /dual-momentum.
    try:
        dm_metrics = dm.metrics_for_df(df, spy_12m=_SPY_12M_RETURN)
    except Exception as exc:
        log.debug("dm metrics failed for %s: %s", symbol, exc)
        dm_metrics = None

    # ── ETF detection ────────────────────────────────────────────────────
    # Cached 30 days in Mongo. Negative-result is cached too, so equity
    # tickers only pay the yfinance call once per month.
    try:
        etf_data = etf_info.etf_data_for(symbol)
    except Exception as exc:
        log.debug("etf_info failed for %s: %s", symbol, exc)
        etf_data = None

    # ── Pioneer theme membership (static) ────────────────────────────────
    # Cheap dict lookup — no network. Live news scoring happens lazily via
    # the /sepa/pioneers endpoint when the user clicks the Pioneers tab.
    pioneer_themes = pioneers.themes_for_symbol(symbol)

    tr = trend_template.evaluate(symbol, df)
    if tr is None:
        return None
    rs = rs_map.get(symbol)
    # Re-apply RS gate
    tr.checks["rs_rank_at_least_70"] = bool(rs and rs >= 70)
    tr.pass_all = all(tr.checks.values())
    tr.passed = sum(1 for v in tr.checks.values() if v)

    # Compute volume signals FIRST so stage.classify() can consult them
    # for the Stage-2 volume-confirmation check (book p.71-72: Stage 2
    # requires accumulation; distribution downgrades to Stage 3).
    vol = volume.analyze(df)
    stg = stage.classify(df, vol=vol)
    vcp_info = vcp.detect(df)
    pp_info = power_play.detect(df)
    bc = base_count.count_bases(df)
    sells = sell_signals.evaluate(df)
    # Venky's filter stack (weekly 21-SMA + ATR + ADX). Always returns a
    # nested dict shape so the FE chips can rely on the schema; gates
    # internally set `error` rather than raising.
    venky = venky_filters.compute_all(df)

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
    # Setup quality — determined here (not later) so the credit can be RISK-
    # SCALED and a live volume breakout with no detected base can earn credit.
    # See _determine_setup (book pp.198-205, p.203).
    _last_px = float(last_close) if last_close else float(df["close"].iloc[-1])
    entry_setup, _setup_base_mult, _risk_mult, risk_to_stop_pct = _determine_setup(
        vcp_info, pp_info, vol, _last_px)
    if entry_setup:
        score += SCORE_WEIGHTS["setup"] * _setup_base_mult * _risk_mult
        # Textbook-VCP volume-signature bonus (book p.199-200: volume dries up
        # at the pivot).
        if (entry_setup["type"] == "VCP" and vcp_info
                and vcp_info.get("ideal_depth_range")
                and vcp_info.get("good_contraction_count")
                and vcp_info.get("volume_drying")):
            score += 2
    # Volume confirmation
    # Volume signals — refactored 2026-05-21 from binary accum/breakout to
    # a graded contribution. The old code awarded 0.5 weight for the loose
    # `accumulation` flag (49% of universe tripped it — meaningless) and
    # 0.5 for high_vol_breakout (0.6% — too strict). Now distributed
    # across four signals so a name with multiple accumulation
    # confirmations scores higher than one with just a barely-above-1
    # up/down ratio.
    if vol:
        strength = vol.get("accumulation_strength")
        if strength == "strong":
            score += SCORE_WEIGHTS["volume"] * 0.40   # ratio≥1.5 + cmf inflow + ≤1 dist day
        elif strength == "accumulating":
            score += SCORE_WEIGHTS["volume"] * 0.20
        elif strength == "distributing":
            score -= SCORE_WEIGHTS["volume"] * 0.20   # penalize active distribution
        if vol.get("pocket_pivot"):
            score += SCORE_WEIGHTS["volume"] * 0.20   # Minervini's pre-breakout signal
        if vol.get("high_vol_breakout"):
            score += SCORE_WEIGHTS["volume"] * 0.20   # confirmed breakout
        if vol.get("cmf_signal") == "inflow":
            score += SCORE_WEIGHTS["volume"] * 0.20   # CMF confirms institutional money in
    # Liquidity / ADR bonus
    if liq["liquid"]:
        score += SCORE_WEIGHTS["liquidity_adr"] * 0.4
    if adr_value and adr_value >= 4.0:
        score += SCORE_WEIGHTS["liquidity_adr"] * 0.6
    # Base count penalty (late stage = exhaustion)
    if bc and bc.get("is_late_stage"):
        score -= 8
    # Institutional-sponsorship demotion (book p.195) — thin names rank below
    # liquid leaders so single-digit/manipulable stocks can't top the list.
    score -= _sponsorship_penalty(liq.get("avg_dollar_vol"))

    # Actionability bonus (book p.203): a name you can BUY today — a volume-
    # confirmed breakout in a Stage-2 setup, not late — outranks one still
    # waiting below its trigger (ranks in-buy-zone above WAIT). 2026-06-01.
    buyable = _is_buyable(tr, stg, bc, liq, vol, entry_setup)
    setup_ready = _is_setup_ready(tr, stg, bc, liq, entry_setup)
    if buyable:
        score += 4

    score = max(0.0, min(score, 100.0))

    # entry_setup + risk_to_stop_pct were determined above (before scoring) so
    # the setup credit could be risk-scaled and a live breakout could earn it.

    # Comprehensive trade plan (entry/stop/target/support/resistance/levels)
    # — built for every analyzed ticker, NOT just those with a VCP base.
    # Falls back to current-price entry + Minervini 7% / ATR×2 stop when
    # no clean base is detected, so the cards still surface actionable
    # numbers for stage-2 names without a textbook setup.
    try:
        from analysis.trade_plan import build_plan as _build_trade_plan
        trade_plan = _build_trade_plan(
            last_close=float(last_close) if last_close else float(df["close"].iloc[-1]),
            df=df,
            vcp_setup=vcp_info,
            powerplay_setup=pp_info,
            direction="long",
        )
    except Exception as exc:
        log.debug("trade plan failed for %s: %s", symbol, exc)
        trade_plan = None

    # Timed entry/exit + decision verdict — pure synthesis of the plan +
    # stage + volume + venky (ATR/ADX). Answers "what do I do THIS week"
    # with a dated timeline + missed-entry recovery. Added 2026-05-29.
    try:
        from . import entry_exit as _ee
        entry_exit_plan = _ee.build_entry_exit(
            last_close=float(last_close) if last_close else float(df["close"].iloc[-1]),
            trade_plan=trade_plan,
            df=df,
            stage=stg,
            vol=vol,
        )
    except Exception as exc:
        log.debug("entry_exit failed for %s: %s", symbol, exc)
        entry_exit_plan = None

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
        "trade_plan":  trade_plan,
        # Venky's filter stack — weekly 21-SMA + ATR + ADX. Surfaced as
        # optional toggle chips on the SEPA filter bar (added 2026-05-29).
        "venky":       venky,
        # Timed entry/exit decision + dated timeline (added 2026-05-29).
        "entry_exit":  entry_exit_plan,
        "adr_pct": adr_value,
        "day_change_pct": day_change_pct,
        "last_close": last_close,
        "dual_momentum": dm_metrics,
        "is_etf":        bool(etf_data and etf_data.get("is_etf")),
        "etf_data":      etf_data if (etf_data and etf_data.get("is_etf")) else None,
        "pioneer_themes": pioneer_themes,
        "is_pioneer":    bool(pioneer_themes),
        "liquidity": liq,
        # Minervini's "candidate" semantics — book p.79 verbatim:
        # *"The Trend Template is a qualifier. If a stock doesn't meet the
        # Trend Template criteria, I don't consider it."*
        #
        # FIXED 2026-05-28 per user feedback: previous version had
        # is_candidate as the strict "buyable-now" gate (Stage 2 + setup +
        # not-late-base). That contradicts the book — a Minervini "candidate"
        # is a name worth CONSIDERING, not a name worth BUYING TODAY. The
        # buyable-now gate is now exposed separately as `is_buyable` so the
        # V1 page surfaces the wider watchlist matching V2's 230-name view.
        "qualifier": bool(tr.pass_all and liq["liquid"]),
        # Per the book: candidate = qualifier. Same field, kept for backward
        # compatibility with existing FE / API consumers that read
        # `is_candidate`. They'll now correctly receive the watchlist tier.
        "is_candidate": bool(tr.pass_all and liq["liquid"]),
        # The strict "ready to buy NOW" gate — book pp.79-83, 198-203:
        # Trend Template + Stage 2 advancing + tight base setup (VCP or
        # Power Play) + not a late-stage base + a VOLUME-CONFIRMED breakout.
        # Book p.203 verbatim: "the point at which you want to buy is when the
        # stock moves above the pivot point ON EXPANDING VOLUME." A breakout on
        # below-average volume is NOT a Minervini buy (p.203-204: "almost every
        # failed base structure can be traced back to some faulty characteristic
        # that was overlooked"). high_vol_breakout = breaking out on volume now;
        # pocket_pivot = Minervini's in-base institutional-footprint buy point.
        # Without one of those the name stays a watchlist candidate, not buyable.
        # (Hard-gate chosen by user 2026-05-31; fixes CVGI-class low-vol breakouts.)
        "is_buyable": buyable,
        # Same gates as is_buyable MINUS the same-day volume breakout — the
        # "set up, waiting for the trigger" tier. Feeds the FE 'Breakout:
        # ≤1wk / Any' toggle (2026-06-02): combine with volume.days_since_breakout
        # to admit a breakout that fired earlier in the week, or with no breakout
        # gate at all. Strict same-day buyable stays `is_buyable`.
        "setup_ready": setup_ready,
        "risk_to_stop_pct": risk_to_stop_pct,
    }


def scan_universe(symbols: Optional[List[str]] = None,
                  with_catalyst: bool = False,
                  persist: bool = True,
                  emitter: Optional[ProgressEmitter] = None) -> dict:
    """Run the full SEPA scan across the universe.

    If `emitter` is provided, fires per-phase + per-ticker progress events.
    See sepa.progress for the event shape; safe to omit for non-streaming
    callers (e.g. POST /sepa/scan, the cron CLI).
    """
    def _emit(event_type: str, **kw):
        if emitter:
            emitter.emit(event_type, **kw)

    t0 = time.time()
    symbols = symbols or load_universe()
    # Exclude benchmarks from candidate list
    work = [s for s in symbols if s not in {"SPY", "QQQ", "IWM"}]

    _emit("phase", phase="loading_universe", total=len(work))

    # Refresh SPY's 12m return once at scan start. Used by dual_momentum.
    # metrics_for_df for the per-ticker `beats_spy` flag.
    _refresh_spy_baseline()

    # ── Bulk price patch — append today's close to all cached histories ──
    # This converts "re-download 2y of history" cold-starts into a single
    # bulk snapshot call. No-ops silently if Massive isn't configured.
    try:
        patch_stats = prices.patch_latest_closes(work)
        log.info("price patch: patched=%d already_current=%d no_cache=%d",
                 patch_stats.get("patched", 0),
                 patch_stats.get("already_current", 0),
                 patch_stats.get("no_cache", 0))
        _emit("log", level="info",
              message=f"Price cache patched: {patch_stats.get('patched', 0)} updated, "
                      f"{patch_stats.get('already_current', 0)} current")
    except Exception as exc:
        log.warning("scanner: bulk price patch failed (%s) — proceeding", exc)

    log.info("Computing RS ranks over %d symbols...", len(work))
    rs_map = rs_rank.rs_ranks(work, emitter=emitter)

    # Warm company-name cache so each result can attach its long name without
    # paying a per-row yfinance lookup. Cached 30 days in Mongo.
    # bulk_warm emits its own `phase` event (with hits vs missing breakdown)
    # plus `name_progress` ticks, so we don't pre-emit here.
    try:
        # CACHE-ONLY during the scan (fetch=False): the broad universe has
        # thousands of un-cached names, and fetching them live here floods
        # yfinance → 429 storm. Missing names fall back to the ticker; the
        # daily `sepa.warm_names` cron fills them in the background.
        company_names.bulk_warm(work, emitter=emitter, fetch=False)
    except Exception as exc:
        log.warning("company_names bulk_warm skipped: %s", exc)
        _emit("log", level="warn", message=f"company_names bulk_warm skipped: {exc}")

    _emit("phase", phase="scanning", total=len(work))

    results: List[dict] = []
    failures: List[dict] = []  # symbols that errored on the first pass
    # Use a thread pool since yfinance + pandas are I/O + CPU mix.
    # Switched from ex.map() to as_completed() so progress events fire on
    # actual completion order (which symbol just finished), not submission order.
    with ThreadPoolExecutor(max_workers=_SCAN_WORKERS) as ex:
        futures = {ex.submit(_analyze_symbol, s, rs_map): s for s in work}
        completed = 0
        for fut in as_completed(futures):
            sym = futures[fut]
            completed += 1
            try:
                res = fut.result()
            except Exception as exc:
                log.warning("scan failed for %s: %s", sym, exc)
                err_msg = str(exc) or type(exc).__name__
                failures.append({"symbol": sym, "error": err_msg, "attempt": 1})
                _emit("failure",
                      symbol=sym, error=err_msg, attempt=1,
                      will_retry=True,
                      current=completed, total=len(work))
                res = None
            if res is not None:
                results.append(res)
                if res.get("is_candidate"):
                    _emit("candidate",
                          symbol=res["symbol"],
                          score=res["score"],
                          rating=res.get("rating"),
                          rs_rank=res.get("rs_rank"))
            _emit("ticker",
                  current=completed, total=len(work),
                  symbol=sym,
                  analyzed=len(results),
                  candidate_count=sum(1 for r in results if r.get("is_candidate")),
                  failures=len(failures))

    # Retry pass — single attempt, lower concurrency, brief settle delay.
    # Most failures are yfinance rate-limits or transient network blips that
    # clear in a few seconds. Permanent failures (delisted, malformed symbol)
    # land in `failures` for the final payload.
    permanent_failures: List[dict] = []
    if failures:
        retry_targets = [f["symbol"] for f in failures]
        _emit("phase", phase="retrying", total=len(retry_targets),
              message=f"Retrying {len(retry_targets)} failed tickers")
        time.sleep(0.5)  # tiny settle for transient yfinance rate-limits

        with ThreadPoolExecutor(max_workers=_SCAN_RETRY_WORKERS) as ex:
            retry_futures = {ex.submit(_analyze_symbol, s, rs_map): s for s in retry_targets}
            retry_done = 0
            for fut in as_completed(retry_futures):
                sym = retry_futures[fut]
                retry_done += 1
                _emit("retry",
                      symbol=sym, attempt=2,
                      current=retry_done, total=len(retry_targets))
                try:
                    res = fut.result()
                except Exception as exc:
                    err_msg = str(exc) or type(exc).__name__
                    permanent_failures.append({
                        "symbol": sym, "error": err_msg, "attempt": 2,
                    })
                    _emit("failure",
                          symbol=sym, error=err_msg, attempt=2,
                          will_retry=False,
                          current=retry_done, total=len(retry_targets))
                    continue
                if res is None:
                    permanent_failures.append({
                        "symbol": sym, "error": "no data after retry", "attempt": 2,
                    })
                    _emit("failure",
                          symbol=sym, error="no data after retry", attempt=2,
                          will_retry=False,
                          current=retry_done, total=len(retry_targets))
                    continue
                results.append(res)
                _emit("recovered",
                      symbol=sym,
                      score=res.get("score"),
                      rating=res.get("rating"))
                if res.get("is_candidate"):
                    _emit("candidate",
                          symbol=res["symbol"],
                          score=res["score"],
                          rating=res.get("rating"),
                          rs_rank=res.get("rs_rank"))

    # Rank + cut to candidates
    results.sort(key=lambda x: x["score"], reverse=True)
    candidates = [r for r in results if r["is_candidate"]]

    # Market context
    _emit("phase", phase="market_context")
    mkt = market_context.market_state()

    # Optional catalyst/insider/fundamentals enrichment on top N candidates only
    if with_catalyst and candidates:
        top = candidates[:20]
        _emit("phase", phase="enriching", total=len(top),
              message=f"Catalyst + insider + CANSLIM on top {len(top)} candidates")

        async def enrich_all() -> None:
            sem = asyncio.Semaphore(4)
            done = {"n": 0}

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
                    # Buffett moat — same yfinance.info call as canslim, so cheap.
                    try:
                        from sepa import moat as _moat
                        rec["moat"] = await asyncio.to_thread(
                            _moat.compute_moat, rec["symbol"],
                        )
                    except Exception as exc:
                        log.warning("moat failed for %s: %s", rec["symbol"], exc)
                    done["n"] += 1
                    _emit("enrich",
                          current=done["n"], total=len(top),
                          symbol=rec["symbol"])

            await asyncio.gather(*(one(r) for r in top))

        asyncio.run(enrich_all())
        # Re-sort after fundamentals bumps
        candidates.sort(key=lambda x: x["score"], reverse=True)

    payload = {
        "generated_at": int(time.time()),
        "duration_sec": round(time.time() - t0, 2),
        "universe_size": len(work),
        "analyzed": len(results),
        # Book p.79: candidate = passes Trend Template = qualifier. The
        # strict "buyable today" gate is now `buyable_count` below.
        "candidate_count": len(candidates),
        "qualifier_count": sum(1 for r in results if r.get("qualifier")),
        # New buyable_count — the count surfaced for "ready to buy NOW"
        # (Stage 2 + setup + not late base + liquid). Was the old
        # candidate_count semantic before the 2026-05-28 fix.
        "buyable_count": sum(1 for r in results if r.get("is_buyable")),
        "market_context": mkt,
        "candidates": candidates,
        "all_results": results,
        "retry_count": len(failures),
        "permanent_failures": permanent_failures,
        "recovered_count": len(failures) - len(permanent_failures),
    }
    if persist:
        _emit("phase", phase="writing")
        LATEST_PATH.write_text(json.dumps(payload, default=str))
        log.info("Scan persisted to %s", LATEST_PATH)
        try:
            from sepa import history
            history.write_scan(payload)
        except Exception as exc:
            log.warning("history write skipped: %s", exc)
        # ── Live signal logging for the calibration loop ──────────────
        # Every SEPA-positive candidate becomes a `pending` observation.
        # The hourly resolver cron grades them after their 24h horizon.
        try:
            from learning import observations as _obs
            from tiny_stocks import scorer as _tiny
            _ts = int(payload.get("generated_at") or 0)
            _positive = {"STRONG_BUY", "BUY", "WATCH"}
            for c in payload.get("all_results") or payload.get("candidates") or []:
                rating = c.get("rating")
                px = c.get("last_close")
                if not px or not c.get("symbol"):
                    continue

                # Log SEPA observation if positive
                if rating in _positive:
                    _obs.record_observation(
                        source=f"sepa_tier_{rating}",
                        ticker=c["symbol"],
                        ts=_ts,
                        direction="up",
                        value=float(c.get("score") or 0.0),
                        baseline_price=float(px),
                        horizon_hours=24,
                        predicted_pct=0.0,
                    )

                # Compute Pounce Tiny Score (PTS) on every candidate that has
                # a small/micro-cap profile, regardless of SEPA rating. Tiny
                # stocks often fail SEPA's institutional-sponsorship gate but
                # are excellent under the small-cap-specific composite.
                try:
                    tiny_result = _tiny.score_candidate(
                        c,
                        market_cap=c.get("market_cap"),
                        frenzy=c.get("frenzy") or {},
                        avg_dollar_volume=(c.get("liquidity") or {}).get("avg_dollar_volume"),
                        float_shares=(c.get("liquidity") or {}).get("float"),
                        si_pct=(c.get("short_interest") or {}).get("si_pct"),
                        days_to_cover=(c.get("short_interest") or {}).get("days_to_cover"),
                        ps_ratio=(c.get("fundamentals") or {}).get("ps_ratio"),
                    )
                    c["tiny_score"] = tiny_result["score"]
                    c["tiny_tier"] = tiny_result["tier"]
                    c["tiny_components"] = tiny_result.get("components") or {}
                    c["tiny_narrative"] = tiny_result.get("narrative") or ""

                    # Log tiny tier as an observation IF the score is meaningful
                    # (TINY_WATCH+) — tracks accuracy via the same calibration loop
                    if tiny_result["tier"] in ("TINY_STRONG", "TINY_BUY", "TINY_WATCH"):
                        _obs.record_observation(
                            source=f"tiny_tier_{tiny_result['tier'].replace('TINY_', '')}",
                            ticker=c["symbol"],
                            ts=_ts,
                            direction="up",
                            value=float(tiny_result["score"]),
                            baseline_price=float(px),
                            horizon_hours=72,   # tiny stocks move faster — 3d horizon
                            predicted_pct=0.0,
                        )
                except Exception as exc:
                    log.warning("tiny_stocks scoring failed for %s: %s",
                                c.get("symbol"), exc)
        except Exception as exc:
            log.warning("learning observation log skipped: %s", exc)
    return payload


def _hot_recompute(symbol: str, df, rs_map: dict, blob: dict) -> Optional[dict]:
    """Re-evaluate the price-derived layers using cached research as scaffolding.

    The research blob supplies VCP / Power Play / base count / fundamentals /
    liquidity / ADR / IPO age / company name. We only re-run trend template,
    stage classifier, today's volume, and the entry-setup match.
    """
    liq = blob.get("liquidity") or {}
    if not liq.get("liquid"):
        return None

    tr = trend_template.evaluate(symbol, df)
    if tr is None:
        return None
    rs = rs_map.get(symbol)
    tr.checks["rs_rank_at_least_70"] = bool(rs and rs >= 70)
    tr.pass_all = all(tr.checks.values())
    tr.passed = sum(1 for v in tr.checks.values() if v)

    # See above; vol-first ordering enables Stage-2 volume confirmation.
    vol = volume.analyze(df)
    stg = stage.classify(df, vol=vol)
    sells = sell_signals.evaluate(df)
    # Venky's filter stack — recomputed live since it's price-derived
    # (weekly resample changes when new weekly close comes in).
    venky = venky_filters.compute_all(df)

    # Day change (today's close vs yesterday's, %) — used for "Sort: Day %"
    day_change_pct = None
    last_close = None
    try:
        if len(df) >= 2:
            last = float(df["close"].iloc[-1])
            prev = float(df["close"].iloc[-2])
            last_close = round(last, 2)
            if prev > 0:
                day_change_pct = round((last / prev - 1) * 100, 2)
    except Exception:
        pass

    # Dual Momentum metrics — same as the full scanner path, recomputed live
    # off today's df (these layers are cheap and intraday-sensitive).
    try:
        dm_metrics = dm.metrics_for_df(df, spy_12m=_SPY_12M_RETURN)
    except Exception:
        dm_metrics = None

    # ETF detection — Mongo-cached 30d, fast on cache hit.
    try:
        etf_data = etf_info.etf_data_for(symbol)
    except Exception:
        etf_data = None

    # Pioneer theme membership (static) — same as the full scanner path.
    pioneer_themes = pioneers.themes_for_symbol(symbol)

    # Composite score — same weights as full scan
    vcp_info = blob.get("vcp")
    pp_info = blob.get("power_play")
    bc = blob.get("base_count")
    adr_value = blob.get("adr_baseline")
    fundamentals = blob.get("fundamentals")
    moat = blob.get("moat")

    score = 0.0
    score += SCORE_WEIGHTS["trend_template"] * (tr.passed / 8.0)
    if rs and rs >= 70:
        score += SCORE_WEIGHTS["rs_rank"] * (min(rs, 99) / 99.0)
    if stg and stg.get("stage") == 2:
        score += SCORE_WEIGHTS["stage_2"]
    _last_px = float(last_close) if last_close else float(df["close"].iloc[-1])
    entry_setup, _setup_base_mult, _risk_mult, risk_to_stop_pct = _determine_setup(
        vcp_info, pp_info, vol, _last_px)
    if entry_setup:
        score += SCORE_WEIGHTS["setup"] * _setup_base_mult * _risk_mult
        if (entry_setup["type"] == "VCP" and vcp_info
                and vcp_info.get("ideal_depth_range")
                and vcp_info.get("good_contraction_count")):
            score += 2
    # Volume signals — refactored 2026-05-21 from binary accum/breakout to
    # a graded contribution. The old code awarded 0.5 weight for the loose
    # `accumulation` flag (49% of universe tripped it — meaningless) and
    # 0.5 for high_vol_breakout (0.6% — too strict). Now distributed
    # across four signals so a name with multiple accumulation
    # confirmations scores higher than one with just a barely-above-1
    # up/down ratio.
    if vol:
        strength = vol.get("accumulation_strength")
        if strength == "strong":
            score += SCORE_WEIGHTS["volume"] * 0.40   # ratio≥1.5 + cmf inflow + ≤1 dist day
        elif strength == "accumulating":
            score += SCORE_WEIGHTS["volume"] * 0.20
        elif strength == "distributing":
            score -= SCORE_WEIGHTS["volume"] * 0.20   # penalize active distribution
        if vol.get("pocket_pivot"):
            score += SCORE_WEIGHTS["volume"] * 0.20   # Minervini's pre-breakout signal
        if vol.get("high_vol_breakout"):
            score += SCORE_WEIGHTS["volume"] * 0.20   # confirmed breakout
        if vol.get("cmf_signal") == "inflow":
            score += SCORE_WEIGHTS["volume"] * 0.20   # CMF confirms institutional money in
    if liq.get("liquid"):
        score += SCORE_WEIGHTS["liquidity_adr"] * 0.4
    if adr_value and adr_value >= 4.0:
        score += SCORE_WEIGHTS["liquidity_adr"] * 0.6
    if fundamentals and fundamentals.get("passed"):
        score += SCORE_WEIGHTS["fundamentals"] * (fundamentals["passed"] / 3.0)
    if bc and bc.get("is_late_stage"):
        score -= 8
    # Institutional-sponsorship demotion (book p.195) — see full-scan path.
    score -= _sponsorship_penalty(liq.get("avg_dollar_vol"))
    # Actionability bonus (book p.203) — see full-scan path.
    buyable = _is_buyable(tr, stg, bc, liq, vol, entry_setup)
    setup_ready = _is_setup_ready(tr, stg, bc, liq, entry_setup)
    if buyable:
        score += 4
    score = max(0.0, min(score, 100.0))

    # entry_setup determined above (before scoring) — see _determine_setup.

    # Comprehensive trade plan — see top scanner branch for rationale.
    try:
        from analysis.trade_plan import build_plan as _build_trade_plan
        trade_plan = _build_trade_plan(
            last_close=float(last_close) if last_close else float(df["close"].iloc[-1]),
            df=df,
            vcp_setup=vcp_info,
            powerplay_setup=pp_info,
            direction="long",
        )
    except Exception as exc:
        log.debug("trade plan failed for %s (fast scan): %s", symbol, exc)
        trade_plan = None

    # Timed entry/exit + decision verdict — recomputed live (price-derived).
    try:
        from . import entry_exit as _ee
        entry_exit_plan = _ee.build_entry_exit(
            last_close=float(last_close) if last_close else float(df["close"].iloc[-1]),
            trade_plan=trade_plan,
            df=df,
            stage=stg,
            vol=vol,
        )
    except Exception as exc:
        log.debug("entry_exit failed for %s (fast scan): %s", symbol, exc)
        entry_exit_plan = None

    return {
        "symbol": symbol,
        "name": blob.get("name") or company_names.name_for(symbol),
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
        "trade_plan":  trade_plan,
        # Venky's filter stack — weekly 21-SMA + ATR + ADX. Surfaced as
        # optional toggle chips on the SEPA filter bar (added 2026-05-29).
        "venky":       venky,
        # Timed entry/exit decision + dated timeline (added 2026-05-29).
        "entry_exit":  entry_exit_plan,
        "adr_pct": adr_value,
        "day_change_pct": day_change_pct,
        "last_close": last_close,
        "dual_momentum": dm_metrics,
        "is_etf":        bool(etf_data and etf_data.get("is_etf")),
        "etf_data":      etf_data if (etf_data and etf_data.get("is_etf")) else None,
        "pioneer_themes": pioneer_themes,
        "is_pioneer":    bool(pioneer_themes),
        "liquidity": liq,
        "fundamentals": fundamentals,
        "moat": moat,
        # Book p.79 candidate = qualifier. See full-scan path for rationale.
        # is_candidate aligned with the book; is_buyable holds the strict
        # entry-now gate. Fix applied 2026-05-28.
        "qualifier": bool(tr.pass_all and liq.get("liquid")),
        "is_candidate": bool(tr.pass_all and liq.get("liquid")),
        # Volume-confirmed breakout required (book p.203). See full-scan path.
        "is_buyable": buyable,
        # is_buyable minus the same-day breakout trigger — see full-scan path.
        "setup_ready": setup_ready,
        "risk_to_stop_pct": risk_to_stop_pct,
        "from_cache": True,
    }


def scan_universe_fast(symbols: Optional[List[str]] = None,
                       persist: bool = True,
                       universe_mode: Optional[str] = None,
                       fallback_when_missing: bool = True,
                       emitter: Optional[ProgressEmitter] = None) -> dict:
    """Hot scan that joins cached research with today's prices.

    Two orders of magnitude faster than `scan_universe()` (typically 20-30s
    instead of 3-15min) because it skips VCP detection, fundamentals, IPO
    age, and base-count analysis — those come from the research cache that
    Sunday's cron warmed.

    Args:
        symbols: optional explicit list; otherwise resolves via universe loader.
        persist: write the result to ~/.cheetah/scans/latest.json + history.
        universe_mode: "curated" / "sp500" / "russell1000" / "expanded".
        fallback_when_missing: if a symbol has no cached research, fall back to
            full per-symbol analysis (slower but no gaps in coverage).
        emitter: optional ProgressEmitter for SSE streaming (see sepa.progress).
    """
    def _emit(event_type: str, **kw):
        if emitter:
            emitter.emit(event_type, **kw)

    t0 = time.time()
    symbols = symbols or load_universe(universe_mode)
    work = [s for s in symbols if s not in {"SPY", "QQQ", "IWM"}]

    _emit("phase", phase="loading_universe", total=len(work),
          mode=universe_mode or "default")

    cache = research_mod.get_all_research()
    log.info("fast scan: %d symbols, %d in research cache", len(work), len(cache))
    _emit("log", level="info",
          message=f"Research cache: {len(cache)} entries · universe: {len(work)}")

    # Refresh SPY 12m baseline for the per-ticker beats_spy flag.
    _refresh_spy_baseline()

    # ── Bulk price patch (same as scan_universe) ─────────────────────────
    try:
        patch_stats = prices.patch_latest_closes(work)
        log.info("fast-scan price patch: patched=%d already_current=%d no_cache=%d",
                 patch_stats.get("patched", 0),
                 patch_stats.get("already_current", 0),
                 patch_stats.get("no_cache", 0))
    except Exception as exc:
        log.warning("scanner: bulk price patch failed (%s) — proceeding", exc)

    log.info("Computing RS ranks over %d symbols (fast scan)...", len(work))
    rs_map = rs_rank.rs_ranks(work, emitter=emitter)

    _emit("phase", phase="scanning", total=len(work))

    results: List[dict] = []
    missing: List[str] = []

    def _run(symbol: str) -> Optional[dict]:
        blob = cache.get(symbol.upper())
        if blob is None:
            missing.append(symbol)
            if fallback_when_missing:
                return _analyze_symbol(symbol, rs_map)
            return None
        df = prices.load_prices(symbol)
        if df is None or len(df) < 220:
            return None
        return _hot_recompute(symbol, df, rs_map, blob)

    failures: List[dict] = []
    with ThreadPoolExecutor(max_workers=_SCAN_WORKERS) as ex:
        futures = {ex.submit(_run, s): s for s in work}
        completed = 0
        for fut in as_completed(futures):
            sym = futures[fut]
            completed += 1
            try:
                res = fut.result()
            except Exception as exc:
                log.warning("fast scan failed for %s: %s", sym, exc)
                err_msg = str(exc) or type(exc).__name__
                failures.append({"symbol": sym, "error": err_msg, "attempt": 1})
                _emit("failure",
                      symbol=sym, error=err_msg, attempt=1,
                      will_retry=True,
                      current=completed, total=len(work))
                res = None
            if res is not None:
                results.append(res)
                if res.get("is_candidate"):
                    _emit("candidate",
                          symbol=res["symbol"],
                          score=res["score"],
                          rating=res.get("rating"),
                          rs_rank=res.get("rs_rank"))
            _emit("ticker",
                  current=completed, total=len(work),
                  symbol=sym,
                  analyzed=len(results),
                  candidate_count=sum(1 for r in results if r.get("is_candidate")),
                  cache_hits=completed - len(missing),
                  cache_misses=len(missing),
                  failures=len(failures))

    # Retry pass — reuse _run so cache hits/misses behave identically.
    permanent_failures: List[dict] = []
    if failures:
        retry_targets = [f["symbol"] for f in failures]
        _emit("phase", phase="retrying", total=len(retry_targets),
              message=f"Retrying {len(retry_targets)} failed tickers")
        time.sleep(0.5)

        with ThreadPoolExecutor(max_workers=_SCAN_RETRY_WORKERS) as ex:
            retry_futures = {ex.submit(_run, s): s for s in retry_targets}
            retry_done = 0
            for fut in as_completed(retry_futures):
                sym = retry_futures[fut]
                retry_done += 1
                _emit("retry",
                      symbol=sym, attempt=2,
                      current=retry_done, total=len(retry_targets))
                try:
                    res = fut.result()
                except Exception as exc:
                    err_msg = str(exc) or type(exc).__name__
                    permanent_failures.append({"symbol": sym, "error": err_msg, "attempt": 2})
                    _emit("failure",
                          symbol=sym, error=err_msg, attempt=2, will_retry=False,
                          current=retry_done, total=len(retry_targets))
                    continue
                if res is None:
                    permanent_failures.append({"symbol": sym, "error": "no data after retry", "attempt": 2})
                    _emit("failure",
                          symbol=sym, error="no data after retry", attempt=2, will_retry=False,
                          current=retry_done, total=len(retry_targets))
                    continue
                results.append(res)
                _emit("recovered",
                      symbol=sym,
                      score=res.get("score"),
                      rating=res.get("rating"))
                if res.get("is_candidate"):
                    _emit("candidate",
                          symbol=res["symbol"],
                          score=res["score"],
                          rating=res.get("rating"),
                          rs_rank=res.get("rs_rank"))

    results.sort(key=lambda x: x["score"], reverse=True)
    candidates = [r for r in results if r["is_candidate"]]
    _emit("phase", phase="market_context")
    mkt = market_context.market_state()

    payload = {
        "generated_at": int(time.time()),
        "duration_sec": round(time.time() - t0, 2),
        "universe_size": len(work),
        "analyzed": len(results),
        # Book p.79: candidate = qualifier; buyable is the strict tier.
        "candidate_count": len(candidates),
        "qualifier_count": sum(1 for r in results if r.get("qualifier")),
        "buyable_count": sum(1 for r in results if r.get("is_buyable")),
        "fast_scan": True,
        "research_cache_hits": len(work) - len(missing),
        "research_cache_misses": len(missing),
        "research_status": research_mod.status(),
        "market_context": mkt,
        "candidates": candidates,
        "all_results": results,
        "retry_count": len(failures),
        "permanent_failures": permanent_failures,
        "recovered_count": len(failures) - len(permanent_failures),
    }
    if persist:
        _emit("phase", phase="writing")
        LATEST_PATH.write_text(json.dumps(payload, default=str))
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
