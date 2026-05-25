"""Tiny-stock conviction scorer + ranked prediction list.

Synthesizes EVERY independent signal we compute across the catalysts
module into a single conviction score per ticker, then ranks them into
HIGH / MEDIUM / WATCH / AVOID tiers.

The point: any one signal can be noise. A ticker that's in the REAL
catalyst quadrant AND has a 3+ insider buy cluster AND shows multi-day
Chaikin Money Flow accumulation AND has a forward earnings catalyst is
a fundamentally different setup than a single-signal one-day pump.
This module finds the names where multiple independent signals stack.

Signals (positive):
   real_catalyst             (current quadrant = REAL)
   strong_accumulation       (multi-day CMF >= +60)
   accumulation              (multi-day CMF >= +30)
   insider_cluster           (3+ Form 4 buyers in 7d)
   stable_winner             (≥3h on list in REAL/OVERLOOKED with no drift)
   volume_surge              (>5x avg volume today)
   forward_catalyst          (earnings/FDA event in next 7d)
   premarket_gap             (gapped >5% pre-market today)
   multi_day_appearance      (in catalyst scan ≥3 distinct sessions)
   bullish_news              (≥2 bullish news in last 48h, no bearish)
   filing_8k_today           (8-K filed today — material event)

Signals (negative):
   has_offering              (S-3 / S-1 / 424B5 / FWP in 7d) — DILUTION
   insider_sell_cluster      (3+ Form 4 sellers in 7d)
   pump_distribution_phase   (system says we're in late-stage / distribution)
   already_extended          (price up >50% today — chase risk)
   bearish_news              (≥2 bearish news, no bullish)
   pure_chatter              (PUMP_RISK with evidence_score < 10)

Tier thresholds (after weighting):
   HIGH   : ≥ 60
   MEDIUM : 35 - 59
   WATCH  : 15 - 34
   AVOID  : < 15  (or any HARD penalty fires regardless)

Cached 10 min during market, 30 min after. Backed by /catalysts/scan.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger("catalysts.predictions")

_CACHE_TTL_LIVE = 10 * 60
_CACHE_TTL_AFTER = 30 * 60


# --- Mongo cache --------------------------------------------------------

def _cache_coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        return client[db]["predictions_cache"]
    except Exception as exc:
        log.warning("predictions cache mongo unavailable: %s", exc)
        return None


def _cache_get() -> Optional[dict]:
    coll = _cache_coll()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"_id": "latest"})
        if not doc:
            return None
        ts = doc.get("cached_at")
        if not isinstance(ts, datetime):
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        from supply_demand.flow import market_status
        ms = market_status()
        ttl = _CACHE_TTL_LIVE if ms["is_live"] else _CACHE_TTL_AFTER
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        if age > ttl:
            return None
        payload = doc.get("payload")
        if isinstance(payload, dict):
            payload = dict(payload)
            payload["cached"] = True
            payload["cache_age_sec"] = round(age)
            return payload
    except Exception as exc:
        log.warning("predictions cache get failed: %s", exc)
    return None


def _cache_put(payload: dict) -> None:
    coll = _cache_coll()
    if coll is None:
        return
    try:
        coll.update_one(
            {"_id": "latest"},
            {"$set": {"cached_at": datetime.now(timezone.utc), "payload": payload}},
            upsert=True,
        )
    except Exception as exc:
        log.warning("predictions cache put failed: %s", exc)


# --- Signal scoring -----------------------------------------------------

# Signal weights — sum is well above 100; the ceiling is enforced by
# tier thresholds, not by capping individual signals.
SIGNAL_WEIGHTS = {
    "real_catalyst":        25,
    "strong_accumulation":  30,   # CMF ≥ +60 across 10d
    "accumulation":         18,   # CMF +30 to +59
    "insider_cluster":      22,   # 3+ Form 4 buyers in 7d
    "stable_winner":        12,   # holding REAL/OVERLOOKED for 3+ hours
    "volume_surge":         10,   # ≥5x avg
    "forward_catalyst":     12,   # earnings/FDA in next 7d
    "premarket_gap":         6,
    "multi_day_appearance":  8,   # appeared in scan ≥3 sessions
    "bullish_news":          7,
    "filing_8k_today":       6,
}

PENALTY_WEIGHTS = {
    "has_offering":          -30,  # dilution risk — almost always kills setups
    "insider_sell_cluster":  -18,
    "pump_distribution_phase": -12,
    "already_extended":      -8,
    "bearish_news":          -10,
    "pure_chatter":          -10,
}

# Signals that are "hard" — if they fire, the ticker drops to AVOID
# regardless of positive score. Currently just dilution risk.
HARD_VETO_PENALTIES = {"has_offering"}


def _classify_tier(score: float, has_hard_veto: bool) -> str:
    if has_hard_veto:
        return "AVOID"
    if score >= 60:
        return "HIGH"
    if score >= 35:
        return "MEDIUM"
    if score >= 15:
        return "WATCH"
    return "AVOID"


# --- Per-ticker signal extraction --------------------------------------

def _extract_signals(c: dict, *,
                     accum_score: Optional[dict] = None,
                     stale_record: Optional[dict] = None,
                     multi_day_appearance: Optional[int] = None,
                     forward_catalyst: Optional[dict] = None,
                     insider_signal: Optional[dict] = None) -> dict:
    """Return {signals: [...], penalties: [...]} for one candidate."""
    signals: list[dict] = []
    penalties: list[dict] = []

    quadrant = c.get("quadrant")
    pump = c.get("pump") or {}
    pump_phase = pump.get("phase")
    evidence = c.get("evidence") or {}
    sec = evidence.get("sec_filings") or {}
    news = evidence.get("news") or {}
    surge = c.get("volume_surge_ratio") or 0
    chg = c.get("change_pct") or 0
    chatter_score = c.get("chatter_score") or 0
    evidence_score = c.get("evidence_score") or 0

    # ---- POSITIVE ----------------------------------------------------
    if quadrant == "REAL":
        signals.append({
            "type": "real_catalyst",
            "weight": SIGNAL_WEIGHTS["real_catalyst"],
            "detail": f"REAL quadrant (chatter {chatter_score:.0f} + evidence {evidence_score:.0f})",
        })

    if accum_score and accum_score.get("score") is not None:
        s = accum_score["score"]
        if s >= 60:
            signals.append({
                "type": "strong_accumulation",
                "weight": SIGNAL_WEIGHTS["strong_accumulation"],
                "detail": f"CMF +{s:.0f} over {accum_score.get('n_days', 10)}d (strong)",
            })
        elif s >= 30:
            signals.append({
                "type": "accumulation",
                "weight": SIGNAL_WEIGHTS["accumulation"],
                "detail": f"CMF +{s:.0f} over {accum_score.get('n_days', 10)}d",
            })

    if insider_signal and insider_signal.get("cluster_detected"):
        n_buyers = insider_signal.get("n_buyers_7d", 0)
        net = insider_signal.get("net_buy_value_usd_7d", 0)
        net_str = f"${net/1e6:.1f}M" if abs(net) >= 1e6 else f"${net/1e3:.0f}k"
        signals.append({
            "type": "insider_cluster",
            "weight": SIGNAL_WEIGHTS["insider_cluster"],
            "detail": f"{n_buyers} insider buyers, net {net_str} (7d)",
        })

    if stale_record:
        h = stale_record.get("hours_on_list", 0)
        signals.append({
            "type": "stable_winner",
            "weight": SIGNAL_WEIGHTS["stable_winner"],
            "detail": f"On list {h:.0f}h in {quadrant} with stable score",
        })

    if surge >= 5:
        signals.append({
            "type": "volume_surge",
            "weight": SIGNAL_WEIGHTS["volume_surge"],
            "detail": f"{surge:.1f}× avg volume today",
        })

    if forward_catalyst:
        signals.append({
            "type": "forward_catalyst",
            "weight": SIGNAL_WEIGHTS["forward_catalyst"],
            "detail": f"{forward_catalyst.get('type', '?')} on {forward_catalyst.get('date', '?')}: {(forward_catalyst.get('title') or '')[:60]}",
        })

    if multi_day_appearance and multi_day_appearance >= 3:
        signals.append({
            "type": "multi_day_appearance",
            "weight": SIGNAL_WEIGHTS["multi_day_appearance"],
            "detail": f"On catalyst list across {multi_day_appearance} distinct sessions",
        })

    if news.get("n_bullish", 0) >= 2 and news.get("n_bearish", 0) == 0:
        signals.append({
            "type": "bullish_news",
            "weight": SIGNAL_WEIGHTS["bullish_news"],
            "detail": f"{news['n_bullish']} bullish news in last 48h, no bearish",
        })

    if sec.get("has_8k"):
        signals.append({
            "type": "filing_8k_today",
            "weight": SIGNAL_WEIGHTS["filing_8k_today"],
            "detail": "8-K material event filed in last 7d",
        })

    # ---- NEGATIVE ----------------------------------------------------
    if sec.get("has_offering"):
        penalties.append({
            "type": "has_offering",
            "weight": PENALTY_WEIGHTS["has_offering"],
            "hard_veto": True,
            "detail": "S-3/S-1/424B5/FWP filed in last 7d — DILUTION RISK",
        })

    if insider_signal and insider_signal.get("n_sellers_7d", 0) >= 3:
        n_sellers = insider_signal.get("n_sellers_7d", 0)
        penalties.append({
            "type": "insider_sell_cluster",
            "weight": PENALTY_WEIGHTS["insider_sell_cluster"],
            "detail": f"{n_sellers} insiders selling in 7d",
        })

    if pump_phase in ("DISTRIBUTION", "CRASH"):
        penalties.append({
            "type": "pump_distribution_phase",
            "weight": PENALTY_WEIGHTS["pump_distribution_phase"],
            "detail": f"System pump-phase: {pump_phase}",
        })

    if chg >= 50:
        penalties.append({
            "type": "already_extended",
            "weight": PENALTY_WEIGHTS["already_extended"],
            "detail": f"Already +{chg:.0f}% today — chase risk",
        })

    if news.get("n_bearish", 0) >= 2 and news.get("n_bullish", 0) == 0:
        penalties.append({
            "type": "bearish_news",
            "weight": PENALTY_WEIGHTS["bearish_news"],
            "detail": f"{news['n_bearish']} bearish news, no bullish",
        })

    if quadrant == "PUMP_RISK" and evidence_score < 10:
        penalties.append({
            "type": "pure_chatter",
            "weight": PENALTY_WEIGHTS["pure_chatter"],
            "detail": "PUMP_RISK with no evidence backing the chatter",
        })

    return {"signals": signals, "penalties": penalties}


def _synthesize_thesis(c: dict, signals: list[dict], penalties: list[dict]) -> dict:
    """Build short bull/bear narrative from the signal stack."""
    bull_parts = []
    bear_parts = []

    sig_by_type = {s["type"]: s for s in signals}
    pen_by_type = {p["type"]: p for p in penalties}

    # Bull case
    if "real_catalyst" in sig_by_type:
        bull_parts.append("real catalyst (chatter + evidence both confirm)")
    if "strong_accumulation" in sig_by_type:
        bull_parts.append("strong multi-day accumulation pattern")
    elif "accumulation" in sig_by_type:
        bull_parts.append("multi-day accumulation pattern")
    if "insider_cluster" in sig_by_type:
        bull_parts.append("insider buy cluster (3+ insiders, 7d)")
    if "multi_day_appearance" in sig_by_type:
        bull_parts.append("recurring across multiple sessions (sticking power)")
    if "forward_catalyst" in sig_by_type:
        fc = sig_by_type["forward_catalyst"]["detail"]
        bull_parts.append(f"upcoming catalyst ({fc.split(':')[0]})")
    if "volume_surge" in sig_by_type:
        bull_parts.append("volume surge confirms move")

    # Bear case
    if "has_offering" in pen_by_type:
        bear_parts.append("⚠️ DILUTION RISK — secondary offering filed in last 7d")
    if "insider_sell_cluster" in pen_by_type:
        bear_parts.append("insiders selling (3+ in 7d)")
    if "pump_distribution_phase" in pen_by_type:
        bear_parts.append("late-stage / distribution phase")
    if "already_extended" in pen_by_type:
        bear_parts.append(pen_by_type["already_extended"]["detail"])
    if "bearish_news" in pen_by_type:
        bear_parts.append("recent bearish news flow")
    if "pure_chatter" in pen_by_type:
        bear_parts.append("chatter without evidence (pump signature)")

    bull = ("Bull: " + "; ".join(bull_parts) + ".") if bull_parts else None
    bear = ("Bear: " + "; ".join(bear_parts) + ".") if bear_parts else None

    return {"bull_thesis": bull, "bear_thesis": bear}


def _entry_zone_from_pump(c: dict) -> Optional[str]:
    """Use the pump-phase classifier's entry hint as the entry zone."""
    pump = c.get("pump") or {}
    return pump.get("entry_hint")


# --- Main entry ---------------------------------------------------------

def build_predictions(force: bool = False, max_results: int = 25) -> dict:
    """Run the full prediction synthesis pipeline."""
    if not force:
        cached = _cache_get()
        if cached:
            return cached

    t0 = time.time()

    # 1) Get current scan (cached internally — won't refetch if recent)
    from .api import _full_scan, _cache_get as _scan_cache_get
    scan = _scan_cache_get()
    if scan is None:
        scan = _full_scan(with_gemma=False, max_results=max_results)
    candidates = scan.get("candidates") or []

    # 2) Pull aux signals across the candidate universe in parallel
    tickers = [c["ticker"] for c in candidates]

    # Multi-day accumulation (cached 1h)
    accum_scores: dict = {}
    try:
        from supply_demand.accumulation import get_accumulation_scores
        accum_scores = get_accumulation_scores(tickers)
    except Exception as exc:
        log.warning("accumulation lookup failed: %s", exc)

    # Stale tracker (today's session)
    stale_by_ticker: dict[str, dict] = {}
    try:
        from .history import get_stalled
        stalled = get_stalled(min_age_hours=3.0)
        for r in stalled.get("stable_winners", []):
            stale_by_ticker[r["ticker"]] = r
    except Exception as exc:
        log.warning("stale lookup failed: %s", exc)

    # Multi-day appearance counts (last 10 days)
    appearance_counts: dict[str, int] = {}
    try:
        from .history import _coll
        coll = _coll()
        if coll is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=10)
            pipe = [
                {"$match": {"snapshot_at": {"$gte": cutoff}}},
                {"$unwind": "$tickers"},
                {"$group": {
                    "_id": "$tickers.ticker",
                    "n_dates": {"$addToSet": "$session_date"},
                }},
                {"$project": {"_id": 1, "n": {"$size": "$n_dates"}}},
            ]
            for r in coll.aggregate(pipe):
                if r.get("_id"):
                    appearance_counts[r["_id"]] = r.get("n", 0)
    except Exception as exc:
        log.warning("appearance count failed: %s", exc)

    # Forward catalyst calendar (next 7 days)
    forward_by_ticker: dict[str, dict] = {}
    try:
        from .calendar import get_calendar
        cal = get_calendar(days=7)
        for ev in cal.get("by_type", {}).get("earnings", []):
            t = ev.get("ticker")
            if t and t.upper() in tickers:
                forward_by_ticker.setdefault(t.upper(), ev)
    except Exception as exc:
        log.warning("calendar lookup failed: %s", exc)

    # Insider signals — only fetch for top-quadrant candidates (it's slow)
    insider_by_ticker: dict[str, dict] = {}
    try:
        from .insiders import get_insider_signal
        from concurrent.futures import ThreadPoolExecutor
        # Only check insiders on names where SEC filings already mention insider trades
        # OR where the candidate is in REAL/OVERLOOKED quadrant.
        candidates_for_insider = [
            c for c in candidates
            if (c.get("evidence") or {}).get("sec_filings", {}).get("has_insider_trade")
            or c.get("quadrant") in ("REAL", "OVERLOOKED")
        ][:15]
        with ThreadPoolExecutor(max_workers=6) as ex:
            results = list(ex.map(lambda c: get_insider_signal(c["ticker"], days=14),
                                   candidates_for_insider))
        for r in results:
            if r and r.get("ticker"):
                insider_by_ticker[r["ticker"]] = r
    except Exception as exc:
        log.warning("insider lookup failed: %s", exc)

    # 3) Build a prediction record per candidate
    predictions = []
    for c in candidates:
        t = c["ticker"]
        sigs = _extract_signals(
            c,
            accum_score=accum_scores.get(t),
            stale_record=stale_by_ticker.get(t),
            multi_day_appearance=appearance_counts.get(t),
            forward_catalyst=forward_by_ticker.get(t),
            insider_signal=insider_by_ticker.get(t),
        )

        score = sum(s["weight"] for s in sigs["signals"])
        score += sum(p["weight"] for p in sigs["penalties"])  # negative
        has_hard_veto = any(p.get("hard_veto") for p in sigs["penalties"])
        tier = _classify_tier(score, has_hard_veto)

        thesis = _synthesize_thesis(c, sigs["signals"], sigs["penalties"])

        predictions.append({
            "ticker": t,
            "company_name": c.get("company_name"),
            "sector": c.get("sector"),
            "price": c.get("price"),
            "change_pct": c.get("change_pct"),
            "volume_surge_ratio": c.get("volume_surge_ratio"),
            "market_cap": c.get("market_cap"),
            "quadrant": c.get("quadrant"),
            "pump_phase": (c.get("pump") or {}).get("phase"),
            "pump_action": (c.get("pump") or {}).get("action"),
            "conviction_score": round(score, 1),
            "conviction_tier": tier,
            "signals": sigs["signals"],
            "penalties": sigs["penalties"],
            **thesis,
            "entry_zone": _entry_zone_from_pump(c),
            "n_signals": len(sigs["signals"]),
            "n_penalties": len(sigs["penalties"]),
            "has_hard_veto": has_hard_veto,
        })

    # 4) Sort by conviction_score desc, with hard vetoes last
    predictions.sort(key=lambda p: (
        1 if p.get("has_hard_veto") else 0,
        -p["conviction_score"],
    ))

    by_tier = {"HIGH": 0, "MEDIUM": 0, "WATCH": 0, "AVOID": 0}
    for p in predictions:
        by_tier[p["conviction_tier"]] = by_tier.get(p["conviction_tier"], 0) + 1

    # 5) Top relevant subset — for Morning Brief embedding
    relevant = [p for p in predictions if p["conviction_tier"] in ("HIGH", "MEDIUM")][:8]

    payload = {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "n_total": len(predictions),
        "by_tier": by_tier,
        "predictions": predictions,
        "top_relevant": relevant,
        "scan_age": scan.get("cache_age_sec") if scan.get("cached") else 0,
        "elapsed_sec": round(time.time() - t0, 1),
        "cached": False,
        "cache_age_sec": 0,
    }
    _cache_put(payload)
    return payload


__all__ = ["build_predictions"]
