"""Full-universe conviction scan — Top-20 picks OUTSIDE the SEPA gate
(Ajay 2026-06-10: "full universe scan, doesn't have to follow Minervini's
SEPA… top 20 picks with strong conviction of the pattern and other safer
trend analysis, some fundamentals, a safety net… avoid whale-manipulated
stocks — has to have a good magnitude of volume").

Every analyzed name in the latest scan is eligible — candidate or not. The
score is a TRANSPARENT blend of independent, measured signals (weights are
OUR configuration, shown in the payload — this is not a book formula):

  Pattern conviction (max 35): confirmed bullish pattern ≤1d (30) /
    forming within 3% of its line (12) · bullish last-bar candle (+5).
  Trend safety (max 25): full Trend Template pass (10) or price above the
    200dma (5) · Stage 2 (10) · plus RS rank × 15 (max 15 → total capped).
  Volume magnitude — the anti-manipulation rail (max 20): average dollar
    volume ≥$100M (10) / ≥$50M (7) / ≥$25M (4) · count-based accumulation
    ratio ≥1.2 (10). Big, two-sided institutional volume is the practical
    defense against pump mechanics; thin tape is excluded outright.
  Fundamentals safety net (max 10): earnings-quality score ×10 when the
    name was enriched; unknown EQ scores 0 (neutral), never invented.

HARD EXCLUSIONS (the safety net): price < $5 · avg dollar volume < $25M ·
avg volume < 300k shares · Stage 4 (declining) · earnings-quality red flag ·
bearish last-bar candle read · leveraged/inverse ETFs and ETFs generally.

HONESTY: "conviction" here = how many independent measured signals agree,
scaled 0–100. It is a ranking device, not a probability; the pattern ledger
(/patterns/accuracy) is what will eventually say how often these work.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger("scalping.conviction")

PRICE_FLOOR = 5.0
DOLLAR_VOL_FLOOR = 25_000_000.0     # hard exclusion — thin tape is manipulable
SHARE_VOL_FLOOR = 300_000
ACCUM_RATIO_MIN = 1.2
FORMING_NEAR_PCT = 3.0              # forming counts only this close to its line

W = {"pattern_confirmed": 30, "pattern_forming": 12, "bullish_candle": 5,
     "trend_pass_all": 10, "above_200dma": 5, "stage2": 10, "rs_max": 15,
     "dollar_vol_100m": 10, "dollar_vol_50m": 7, "dollar_vol_25m": 4,
     "accumulation": 10, "eq_max": 10}


def _dollar_vol(row: dict) -> float:
    vol = row.get("volume") or {}
    avg, close = vol.get("avg_vol_50"), row.get("last_close")
    return float(avg) * float(close) if (avg and close) else 0.0


def top_picks(n: int = 20) -> dict:
    from sepa import scanner
    from patterns import scan as pscan

    rows = (scanner.load_latest() or {}).get("all_results") or []
    pool, excluded = [], {"liquidity": 0, "stage4": 0, "red_flag": 0, "etf": 0}
    for r in rows:
        sym = r.get("symbol")
        if not sym:
            continue
        if r.get("is_etf"):
            excluded["etf"] += 1
            continue
        close = r.get("last_close")
        vol = r.get("volume") or {}
        dv = _dollar_vol(r)
        if (not close or close < PRICE_FLOOR or dv < DOLLAR_VOL_FLOOR
                or (vol.get("avg_vol_50") or 0) < SHARE_VOL_FLOOR):
            excluded["liquidity"] += 1
            continue
        stage = (r.get("stage") or {}).get("stage")
        if stage == 4:
            excluded["stage4"] += 1
            continue
        eq = r.get("earnings_quality") or {}
        if eq.get("tier") == "red_flag":
            excluded["red_flag"] += 1
            continue
        pool.append((r, dv))
    if not pool:
        return {"ok": False, "excluded": excluded, "n_universe": len(rows),
                "reason": (f"nothing passes the safety rails ({len(rows)} rows: "
                           f"{excluded['liquidity']} thin/incomplete, {excluded['stage4']} Stage 4, "
                           f"{excluded['red_flag']} red flag, {excluded['etf']} ETF) — "
                           "run a fresh SEPA full scan first")}

    # Pattern verdicts for the whole pool, parallel (~10ms/symbol).
    def verdict(item):
        r, dv = item
        try:
            return r, dv, pscan._verdict_for_symbol(r["symbol"], {})
        except Exception:
            return r, dv, None
    with ThreadPoolExecutor(max_workers=8) as ex:
        graded = list(ex.map(verdict, pool))

    picks = []
    for r, dv, v in graded:
        formations = ((v or {}).get("candles") or {}).get("formations") or []
        if any(f.get("read") == "bearish_warning" for f in formations):
            continue                                   # safety net: bearish tape
        matches = (v or {}).get("matches") or []
        conf = next((m for m in matches if m.get("status") == "confirmed"), None)
        forming = next((m for m in matches if m.get("status") == "forming"
                        and (m.get("to_confirm_pct") or 99) <= FORMING_NEAR_PCT), None)
        bull_candle = next((f["name"] for f in formations
                            if f.get("read") == "bullish_reversal_setup"), None)
        trend = r.get("trend") or {}
        stage = (r.get("stage") or {}).get("stage")
        rs = r.get("rs_rank") or 0
        eq = r.get("earnings_quality") or {}
        accum = (r.get("volume") or {}).get("up_down_vol_ratio")

        score, drivers = 0.0, []
        if conf:
            score += W["pattern_confirmed"]
            drivers.append(f"{conf['pattern'].replace('_', ' ')} CONFIRMED "
                           f"{'today' if conf.get('bars_since_confirm') == 0 else 'yesterday'}")
        elif forming:
            score += W["pattern_forming"]
            drivers.append(f"{forming['pattern'].replace('_', ' ')} forming, "
                           f"{forming.get('to_confirm_pct')}% to its line")
        if bull_candle:
            score += W["bullish_candle"]
            drivers.append(f"bullish candle: {bull_candle.replace('_', ' ')}")
        if trend.get("pass_all"):
            score += W["trend_pass_all"]
            drivers.append("full Trend Template pass")
        elif trend.get("price") and trend.get("ma200") and trend["price"] > trend["ma200"]:
            score += W["above_200dma"]
            drivers.append("above the 200dma")
        if stage == 2:
            score += W["stage2"]
            drivers.append("Stage 2 advancing")
        score += min(max(rs, 0), 100) / 100.0 * W["rs_max"]
        if dv >= 100_000_000:
            score += W["dollar_vol_100m"]
            drivers.append(f"${dv/1e6:.0f}M/day traded — hard to manipulate")
        elif dv >= 50_000_000:
            score += W["dollar_vol_50m"]
            drivers.append(f"${dv/1e6:.0f}M/day traded")
        else:
            score += W["dollar_vol_25m"]
        if accum is not None and accum >= ACCUM_RATIO_MIN:
            score += W["accumulation"]
            drivers.append(f"accumulation: {accum}× more up-days on volume")
        if eq.get("score") is not None:
            score += float(eq["score"]) / 100.0 * W["eq_max"]
            drivers.append(f"earnings quality {eq['score']}/100"
                           + (" · Code 33" if eq.get("code_33") else ""))

        m = conf or forming
        picks.append({
            "symbol": r["symbol"], "conviction": round(score, 1),
            "price": r.get("last_close"), "rs_rank": r.get("rs_rank"),
            "stage": stage, "dollar_vol_m": round(dv / 1e6),
            "pattern": m["pattern"] if m else None,
            "pattern_status": (m or {}).get("status"),
            "neckline": (m or {}).get("neckline"), "target": (m or {}).get("target"),
            "stop": (m or {}).get("stop"),
            "is_candidate": bool(r.get("is_candidate")),
            "is_buyable": bool(r.get("is_buyable")),
            "eq_score": eq.get("score"), "drivers": drivers[:6],
        })

    picks.sort(key=lambda p: -p["conviction"])
    return {
        "ok": True, "generated_at": int(time.time()),
        "n_universe": len(rows), "n_screened": len(pool), "excluded": excluded,
        "picks": picks[:n], "weights": W,
        "criteria": (f"full universe (SEPA gate NOT required) · hard rails: price ≥ ${PRICE_FLOOR:.0f}, "
                     f"≥ ${DOLLAR_VOL_FLOOR/1e6:.0f}M/day + ≥ {SHARE_VOL_FLOOR/1000:.0f}k sh/day, "
                     f"no Stage 4, no EQ red flag, no bearish last-bar candle, no ETFs"),
        "disclaimer": (
            "Conviction = how many independent measured signals agree (our "
            "configured weights, shown in the payload) — a ranking device, not a "
            "probability. Names here may NOT clear the Minervini buy gate; check "
            "the entry discipline before acting. The volume floor is the practical "
            "defense against manipulated tape, not a guarantee. Not advice."),
    }
