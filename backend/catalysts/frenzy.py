"""Pre-frenzy detection — surface tiny stocks BEFORE they go parabolic.

By the time a name shows up as +50% with rocket emojis on every platform,
you're already too late. The actionable detection window is the
inflection point — when the volume / chatter / accumulation signals are
stacking but the price hasn't extended yet.

Six signals tracked here:

  1. quiet_volume_surge      Volume ≥3× avg AND |change_pct| < 15
                              (Wyckoff Phase D — accumulation under cover)

  2. chatter_acceleration    This snapshot's chatter velocity ≥1.5× prior
                              snapshot's. Rate-of-change matters more than
                              the absolute number.

  3. cross_platform_chatter  Stocktwits ≥10/24h AND Reddit ≥5/24h.
                              Coordinated attention across platforms is
                              much harder to fake than single-thread pumps.

  4. float_in_play           Volume / float ≥30%. The whole float changed
                              hands today; whoever wants in/out is doing it now.

  5. multi_day_accum_buildup Chaikin Money Flow ≥40 over 10d AND no day
                              with >20% move in last 5d. Stored energy.

  6. fresh_appearance        First time on the catalyst list in 5+ sessions.
                              Catch the name before the FOMO crowd does.

Bonus signal:
  7. trading_halt_today      Stock halted today (especially LUDP volatility
                              halts) → already in / approaching parabolic phase.

Score:
  Each signal contributes weighted points. Tier:
    IMMINENT  ≥ 60   (multiple signals stacked — ride or trim, not entry)
    SETUP     35-59  (best entry zone — pre-breakout positioning)
    EARLY     15-34  (one signal — watchlist)
    QUIET     < 15   (filter out)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger("catalysts.frenzy")


SIGNAL_WEIGHTS = {
    "quiet_volume_surge":      30,  # highest signal-to-noise
    "chatter_acceleration":    25,
    "cross_platform_chatter":  20,
    "float_in_play":           25,
    "multi_day_accum_buildup": 22,
    "fresh_appearance":        18,
    "trading_halt_today":      18,
    "parabolic_halts":         12,  # extra if multiple LUDP halts
}


def _classify_tier(score: float) -> str:
    if score >= 60: return "IMMINENT"
    if score >= 35: return "SETUP"
    if score >= 15: return "EARLY"
    return "QUIET"


def _detect_for_candidate(c: dict, *,
                          prior_snapshot_record: Optional[dict] = None,
                          accum_score: Optional[dict] = None,
                          fresh: bool = False,
                          halts: Optional[dict] = None,
                          recent_max_change: Optional[float] = None) -> dict:
    """Return {signals, score, tier} for one candidate."""
    signals: list[dict] = []

    chg_pct = c.get("change_pct") or 0
    surge = c.get("volume_surge_ratio") or 0
    volume = c.get("volume") or 0
    float_shares = c.get("float") or 0
    chatter = c.get("chatter") or {}
    st_24 = (chatter.get("stocktwits") or {}).get("n_24h") or 0
    rd_24 = (chatter.get("reddit") or {}).get("n_posts_24h") or 0
    velocity = chatter.get("velocity_per_hour") or 0

    # 1. Quiet volume surge
    if surge >= 3 and abs(chg_pct) < 15:
        signals.append({
            "type": "quiet_volume_surge",
            "weight": SIGNAL_WEIGHTS["quiet_volume_surge"],
            "detail": f"{surge:.1f}× volume, only {chg_pct:+.1f}% — Wyckoff accumulation under cover",
        })

    # 2. Chatter acceleration vs prior snapshot
    if prior_snapshot_record:
        prior_velocity = (prior_snapshot_record.get("velocity_per_hour")
                          or prior_snapshot_record.get("chatter_velocity")
                          or 0)
        if prior_velocity >= 0.3 and velocity >= prior_velocity * 1.5:
            signals.append({
                "type": "chatter_acceleration",
                "weight": SIGNAL_WEIGHTS["chatter_acceleration"],
                "detail": f"chatter velocity {prior_velocity:.1f}/h → {velocity:.1f}/h ({velocity/prior_velocity:.1f}×)",
            })

    # 3. Cross-platform chatter convergence
    if st_24 >= 10 and rd_24 >= 5:
        signals.append({
            "type": "cross_platform_chatter",
            "weight": SIGNAL_WEIGHTS["cross_platform_chatter"],
            "detail": f"Stocktwits {st_24}/24h + Reddit {rd_24}/24h — coordinated cross-platform interest",
        })

    # 4. Float in play
    if float_shares > 0 and volume > 0:
        float_pct = (volume / float_shares) * 100
        if float_pct >= 30:
            signals.append({
                "type": "float_in_play",
                "weight": SIGNAL_WEIGHTS["float_in_play"],
                "detail": f"{float_pct:.0f}% of float traded today (float {float_shares/1e6:.1f}M)",
                "float_pct": round(float_pct, 1),
            })

    # 5. Multi-day accumulation buildup
    if accum_score and (accum_score.get("score") or 0) >= 40:
        recent_extreme = recent_max_change or 0
        if abs(recent_extreme) < 20:
            signals.append({
                "type": "multi_day_accum_buildup",
                "weight": SIGNAL_WEIGHTS["multi_day_accum_buildup"],
                "detail": f"CMF +{accum_score['score']:.0f} over 10d, no >20% day in 5d — stored energy",
            })

    # 6. Fresh appearance
    if fresh:
        signals.append({
            "type": "fresh_appearance",
            "weight": SIGNAL_WEIGHTS["fresh_appearance"],
            "detail": "First appearance on catalyst list in 5+ sessions — early signal",
        })

    # 7. Trading halts today (mostly relevant when already in motion, but
    # signals "frenzy now" rather than "frenzy upcoming")
    if halts:
        n_halts = halts.get("n_halts", 0)
        n_para = halts.get("n_parabolic_halts", 0)
        if n_halts >= 1:
            reasons = ", ".join(halts.get("reasons", [])[:3])
            signals.append({
                "type": "trading_halt_today",
                "weight": SIGNAL_WEIGHTS["trading_halt_today"],
                "detail": f"{n_halts} halt(s) today: {reasons}",
            })
            if n_para >= 2:
                signals.append({
                    "type": "parabolic_halts",
                    "weight": SIGNAL_WEIGHTS["parabolic_halts"],
                    "detail": f"{n_para} volatility halts (LUDP/T1/T6) — already parabolic",
                })

    score = sum(s["weight"] for s in signals)
    tier = _classify_tier(score)

    return {"signals": signals, "score": score, "tier": tier}


def _build_prior_lookup(snapshots: list[dict]) -> dict[str, dict]:
    """Map ticker → its record in the second-most-recent snapshot, for
    chatter-velocity rate-of-change comparison."""
    if len(snapshots) < 2:
        return {}
    prior = snapshots[-2]  # snapshots are oldest-first
    return {t.get("ticker"): t for t in (prior.get("tickers") or []) if t.get("ticker")}


def _compute_appearance_history(snapshots: list[dict],
                                 lookback_session_dates: int = 5) -> set[str]:
    """Return set of tickers that appeared in scans across the last N
    DISTINCT sessions (excluding today). Used to flag fresh appearances."""
    if not snapshots:
        return set()
    today = snapshots[-1].get("session_date")
    seen_dates_to_tickers: dict[str, set[str]] = {}
    for snap in snapshots:
        sd = snap.get("session_date")
        if sd == today or not sd:
            continue
        if sd not in seen_dates_to_tickers:
            seen_dates_to_tickers[sd] = set()
        for t in (snap.get("tickers") or []):
            if t.get("ticker"):
                seen_dates_to_tickers[sd].add(t["ticker"])

    # Take the last N distinct prior session dates
    sorted_dates = sorted(seen_dates_to_tickers.keys(), reverse=True)
    relevant_dates = sorted_dates[:lookback_session_dates]
    out: set[str] = set()
    for sd in relevant_dates:
        out.update(seen_dates_to_tickers[sd])
    return out


def _recent_max_abs_change(snapshots: list[dict], ticker: str,
                            lookback_sessions: int = 5) -> float:
    """Find the largest |change_pct| seen for `ticker` across the last
    N sessions (rough proxy for "no big day yet")."""
    seen_per_date: dict[str, float] = {}
    for snap in snapshots:
        sd = snap.get("session_date")
        if not sd:
            continue
        for t in (snap.get("tickers") or []):
            if t.get("ticker") == ticker:
                v = abs(t.get("change_pct") or 0)
                if sd not in seen_per_date or v > seen_per_date[sd]:
                    seen_per_date[sd] = v
    if not seen_per_date:
        return 0.0
    sorted_dates = sorted(seen_per_date.keys(), reverse=True)[:lookback_sessions]
    return max(seen_per_date[d] for d in sorted_dates)


def build_frenzy_radar(*,
                       force: bool = False,
                       max_results: int = 25) -> dict:
    """Run pre-frenzy detection across the current catalyst scan.

    Returns ranked list with each candidate's signals + score + tier.
    """
    import time
    t0 = time.time()

    # 1) Get current scan candidates
    from .api import _full_scan, _cache_get as _scan_cache_get
    scan = _scan_cache_get()
    if scan is None:
        scan = _full_scan(with_gemma=False, max_results=max_results)
    candidates = scan.get("candidates") or []

    # 2) Snapshot history — for prior-snapshot lookup + fresh-appearance
    from .history import get_session_snapshots, _coll
    today_snaps = get_session_snapshots()
    # Also pull a wider window for fresh-appearance detection (5+ sessions back)
    all_recent_snaps: list[dict] = []
    coll = _coll()
    if coll is not None:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=8)
            cursor = coll.find({"snapshot_at": {"$gte": cutoff}}).sort("snapshot_at", 1)
            for d in cursor:
                ts = d.get("snapshot_at")
                if hasattr(ts, "isoformat"):
                    d["snapshot_at"] = ts.isoformat()
                d["_id"] = str(d.get("_id"))
                all_recent_snaps.append(d)
        except Exception as exc:
            log.warning("snapshot history pull failed: %s", exc)

    prior_by_ticker = _build_prior_lookup(today_snaps)
    seen_in_recent_sessions = _compute_appearance_history(all_recent_snaps, 5)

    # 3) Accumulation scores
    tickers = [c["ticker"] for c in candidates]
    accum_scores: dict = {}
    try:
        from supply_demand.accumulation import get_accumulation_scores
        accum_scores = get_accumulation_scores(tickers)
    except Exception as exc:
        log.warning("accumulation lookup failed: %s", exc)

    # 4) Halts feed (today)
    halt_data: dict = {}
    try:
        from .halts import get_today_halts
        halt_data = get_today_halts().get("by_ticker", {})
    except Exception as exc:
        log.warning("halts feed failed: %s", exc)

    # 5) Detect signals per candidate
    out = []
    for c in candidates:
        t = c["ticker"]
        is_fresh = bool(seen_in_recent_sessions) and t not in seen_in_recent_sessions
        recent_max = _recent_max_abs_change(all_recent_snaps, t, 5)
        result = _detect_for_candidate(
            c,
            prior_snapshot_record=prior_by_ticker.get(t),
            accum_score=accum_scores.get(t),
            fresh=is_fresh,
            halts=halt_data.get(t),
            recent_max_change=recent_max,
        )

        if result["score"] < 5:
            continue  # skip noise

        out.append({
            "ticker": t,
            "company_name": c.get("company_name"),
            "price": c.get("price"),
            "change_pct": c.get("change_pct"),
            "volume": c.get("volume"),
            "volume_surge_ratio": c.get("volume_surge_ratio"),
            "market_cap": c.get("market_cap"),
            "float": c.get("float"),
            "chatter_velocity_per_hour": (c.get("chatter") or {}).get("velocity_per_hour"),
            "stocktwits_24h": ((c.get("chatter") or {}).get("stocktwits") or {}).get("n_24h"),
            "reddit_24h": ((c.get("chatter") or {}).get("reddit") or {}).get("n_posts_24h"),
            "accumulation_score": (accum_scores.get(t) or {}).get("score"),
            "halts_today": halt_data.get(t),
            **result,
        })

    out.sort(key=lambda x: -x["score"])

    by_tier = {"IMMINENT": 0, "SETUP": 0, "EARLY": 0, "QUIET": 0}
    for r in out:
        by_tier[r["tier"]] = by_tier.get(r["tier"], 0) + 1

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "n_total": len(out),
        "by_tier": by_tier,
        "candidates": out,
        "snapshots_used": len(today_snaps),
        "lookback_sessions_indexed": len({s.get("session_date") for s in all_recent_snaps if s.get("session_date")}),
        "elapsed_sec": round(time.time() - t0, 1),
    }


__all__ = ["build_frenzy_radar"]
