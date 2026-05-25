"""Reason inference — enrich an observation with context + narrative.

Joins each observation with the matching candidate_snapshot (pulls SEPA
score, RS rank, stage, trend-template gates, VCP/Power Play flags) and
the scan_run's market context (uptrend / caution / risk-off), then
synthesizes a one-line narrative explaining *why* the prediction hit
or missed.

Used by ``/learning/recent`` to drive the accordion drill-in on /track.
"""
from __future__ import annotations

import logging
from typing import Optional

from learning.observations import _get_db

log = logging.getLogger("learning.reasons")


def _market_label(ctx: dict | None) -> str | None:
    if not ctx:
        return None
    return ctx.get("label")


def _trend_summary(trend: dict | None) -> tuple[int | None, list[str]]:
    """Return (passed_count, list_of_failed_gate_names)."""
    if not isinstance(trend, dict):
        return None, []
    passed = trend.get("passed")
    checks = trend.get("checks") or {}
    failed = [k.replace("_", " ") for k, v in checks.items() if v is False]
    return passed, failed


def _vcp_summary(vcp: dict | None) -> str | None:
    if not isinstance(vcp, dict):
        return None
    if vcp.get("has_base"):
        pivot = vcp.get("pivot_buy_price")
        return f"VCP base · pivot ${pivot:.2f}" if pivot else "VCP base"
    return None


def enrich_one(obs: dict) -> dict:
    """Return obs with extra fields: score, rs_rank, stage_label, gates,
    market context, vcp, plus a synthesized ``reason`` narrative + tag list."""
    db = _get_db()
    if db is None:
        return obs

    enriched = dict(obs)
    ticker = obs.get("ticker")
    date_et = obs.get("date_et")

    # Match the same date's candidate_snapshot for this ticker
    snap = None
    if ticker and date_et:
        snap = db.candidate_snapshots.find_one(
            {"symbol": ticker, "date_et": date_et},
            sort=[("generated_at", -1)],
        )

    score = (snap or {}).get("score")
    rs_rank = (snap or {}).get("rs_rank")
    stage = (snap or {}).get("stage")
    stage_label = (snap or {}).get("stage_label")
    trend = (snap or {}).get("trend")
    vcp = (snap or {}).get("vcp")
    entry = (snap or {}).get("entry_setup") or {}

    passed, failed_gates = _trend_summary(trend)
    vcp_str = _vcp_summary(vcp)

    # Match the scan_run for market context
    market_ctx = None
    if snap and snap.get("scan_run_id"):
        run = db.scan_runs.find_one({"_id": snap["scan_run_id"]},
                                    projection={"market_context": 1})
        if run:
            market_ctx = run.get("market_context")
    market = _market_label(market_ctx)

    # Build tag chips
    tags: list[str] = []
    tier = obs.get("source", "").replace("sepa_tier_", "")
    if tier:
        tags.append(f"{tier} tier")
    if score is not None:
        tags.append(f"score {score:.0f}")
    if passed is not None:
        tags.append(f"{passed}/8 trend gates")
    if rs_rank is not None:
        tags.append(f"RS {rs_rank}")
    if stage_label:
        tags.append(stage_label)
    if vcp_str:
        tags.append(vcp_str)
    if entry.get("type"):
        tags.append(f"setup: {entry['type']}")
    if market:
        tags.append(f"market: {market}")

    # Synthesize the narrative
    status = obs.get("status")
    actual_pct = obs.get("actual_pct") or 0.0
    reason = _infer_reason(
        status=status, actual_pct=actual_pct,
        tier=tier, score=score, rs_rank=rs_rank, stage=stage,
        trend_passed=passed, failed_gates=failed_gates,
        market=market, vcp=vcp_str, entry_type=entry.get("type"),
    )

    enriched.update({
        "score": score,
        "rs_rank": rs_rank,
        "stage": stage,
        "stage_label": stage_label,
        "trend_passed": passed,
        "failed_gates": failed_gates[:3],  # cap so rows aren't huge
        "vcp_summary": vcp_str,
        "entry_setup": entry,
        "market_context": market,
        "tags": tags,
        "reason": reason,
    })
    return enriched


def _infer_reason(
    *, status: str, actual_pct: float,
    tier: str, score: Optional[float], rs_rank: Optional[float],
    stage: Optional[int], trend_passed: Optional[int],
    failed_gates: list[str], market: Optional[str],
    vcp: Optional[str], entry_type: Optional[str],
) -> str:
    """Heuristic narrative — what made this hit or miss?

    Tries to identify the dominant factor. Returns a one-line explanation
    using whichever fields are available.
    """
    # ----- HITS -----
    if status == "hit":
        if score is not None and score >= 80 and (trend_passed or 0) >= 7:
            return (f"Strong setup — score {score:.0f}, {trend_passed}/8 gates"
                    + (f", RS {rs_rank}" if rs_rank else "")
                    + f" → +{actual_pct:.1f}%. Full SEPA stack aligned.")
        if market in ("uptrend", "confirmed_uptrend") and (score or 0) >= 65:
            return (f"Setup quality + market tailwind — {tier} tier in {market}"
                    + f" → +{actual_pct:.1f}%. Quality + breadth carried it.")
        if vcp:
            return (f"{vcp} fired — pivot held → +{actual_pct:.1f}%. "
                    f"Volatility contraction worked as designed.")
        if rs_rank and rs_rank >= 90:
            return (f"High relative strength (RS {rs_rank}) → +{actual_pct:.1f}%. "
                    f"Leadership stocks tend to keep leading next-day.")
        return (f"{tier} tier hit — +{actual_pct:.1f}% next day. "
                f"Modest setup, directionally correct.")

    # ----- PARTIAL -----
    if status == "partial":
        return (f"Direction right but magnitude off — actual {actual_pct:+.1f}%. "
                f"Worth keeping but downweighted.")

    # ----- MISS -----
    if status == "miss":
        if market in ("caution", "risk_off") and (score or 0) < 75:
            return (f"Market headwind — {market} regime overrode {tier} setup "
                    f"(score {score or '—'}). Stock dropped {actual_pct:.1f}% with the tape. "
                    f"Lesson: discount setups when market is in caution.")
        if (score or 0) < 65:
            return (f"Borderline setup — score {score or '—'} with only "
                    f"{trend_passed or '—'}/8 gates. {actual_pct:+.1f}% next day. "
                    f"Marginal candidates underperform; tighten the score floor.")
        if failed_gates:
            return (f"Trend template incomplete — failed: {', '.join(failed_gates)}. "
                    f"Stock dropped {actual_pct:.1f}% next day.")
        if stage and stage != 2:
            return (f"Wrong cycle stage — stock was Stage {stage} not 2. "
                    f"Dropped {actual_pct:.1f}%.")
        return (f"Setup didn't follow through — {actual_pct:+.1f}% next day "
                f"despite {tier} tier. Could be intraday news, sector rotation, "
                f"or overall mean reversion.")

    return "Pending — not yet graded."


def enrich_many(rows: list[dict]) -> list[dict]:
    """Enrich a batch of observations. Done sequentially since per-row Mongo
    lookups are <1ms each and the typical batch is ≤50."""
    return [enrich_one(r) for r in rows]
