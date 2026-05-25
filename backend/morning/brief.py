"""Morning brief — one-screen 'how should I trade today' synthesis.

Combines four signals:
  1. Market regime (confirmed_uptrend / pressure / correction)
  2. VIX level (drives day-trade vs swing weighting)
  3. Live SEPA candidates near pivot (swing entries)
  4. Day-trading conditions (ORB window readiness, premarket gappers)

Output: one verdict per discipline (day vs swing) with confidence + reasons.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from auth import current_user_email
from sepa import market_regime as mr
from sepa import scanner as sepa_scanner

log = logging.getLogger("morning.brief")
router = APIRouter(tags=["morning"])


def _classify_day_trading(regime_data: dict) -> dict:
    """How favorable is the regime for intraday breakout vs reversion strategies?"""
    label = regime_data.get("label")
    score = regime_data.get("score", 50)
    c = regime_data.get("components", {})
    vix = c.get("stress", {}).get("vix")
    dist_count = c.get("distribution", {}).get("count")

    reasons_pro = []
    reasons_con = []
    confidence = 50

    # Volatility: VIX 18-30 is the day-trader sweet spot
    if vix is not None:
        if 18 <= vix <= 30:
            reasons_pro.append(f"VIX {vix} in the day-trade sweet spot — enough movement to break ranges, not panic.")
            confidence += 15
        elif vix < 15:
            reasons_con.append(f"VIX {vix} extremely low — ranges will be tight, breakout strategies struggle.")
            confidence -= 10
        elif vix > 30:
            reasons_con.append(f"VIX {vix} elevated — high whipsaw risk, slippage on entries.")
            confidence -= 5

    # Distribution: high distribution = whippy market, bad for breakouts
    if dist_count is not None and dist_count <= 3:
        reasons_pro.append(f"Distribution count {dist_count}/25 — clean tape, breakout follow-through likely.")
        confidence += 10
    elif dist_count is not None and dist_count >= 5:
        reasons_con.append(f"Distribution count {dist_count}/25 — whippy tape, breakouts often fail.")
        confidence -= 15

    # Trend regime
    if label == "confirmed_uptrend":
        reasons_pro.append("Confirmed uptrend — long bias works for breakouts and continuations.")
        confidence += 10
    elif label == "market_in_correction":
        reasons_con.append("Market in correction — short setups (momentum failure, bear flag) preferred over longs.")
        confidence -= 5
    elif label == "uptrend_under_pressure":
        reasons_pro.append("Mixed regime — small size, take A+ setups only.")

    confidence = max(20, min(95, confidence))
    if confidence >= 70:
        verdict = "favorable"
        headline = "Day trading: GO. Conditions favor breakout strategies."
    elif confidence >= 50:
        verdict = "neutral"
        headline = "Day trading: SELECTIVE. Take only A+ setups, half size."
    else:
        verdict = "caution"
        headline = "Day trading: SIT OUT. Conditions don't favor breakouts."

    return {
        "verdict": verdict,
        "headline": headline,
        "confidence": confidence,
        "reasons_pro": reasons_pro,
        "reasons_con": reasons_con,
    }


def _classify_swing_trading(regime_data: dict, scan_data: Optional[dict]) -> dict:
    """How favorable is the regime for SEPA-style swing entries?"""
    label = regime_data.get("label")
    score = regime_data.get("score", 50)
    c = regime_data.get("components", {})
    breadth_pct = c.get("breadth", {}).get("pct_above_200ma")

    reasons_pro = []
    reasons_con = []
    confidence = 50

    if label == "confirmed_uptrend":
        confidence = 80
        reasons_pro.append("Confirmed uptrend — Minervini's market-context gate is GREEN.")
    elif label == "uptrend_under_pressure":
        confidence = 55
        reasons_pro.append("Uptrend intact but under pressure — tighten stops on existing positions.")
        reasons_con.append("New entries should be A+ setups only (VCP with pivot quality, late-base avoided).")
    else:
        confidence = 25
        reasons_con.append("Market in correction — Minervini's gate says NO new SEPA entries until trend repairs.")

    if breadth_pct is not None:
        if breadth_pct >= 60:
            reasons_pro.append(f"Breadth {breadth_pct:.0f}% — broad participation, leaders likely to extend.")
            confidence += 5
        elif breadth_pct < 40:
            reasons_con.append(f"Breadth {breadth_pct:.0f}% — thin participation, leadership unsustainable.")
            confidence -= 10

    # Count SEPA candidates near pivot (entry-ready)
    candidates_near_pivot = []
    if scan_data:
        for row in (scan_data.get("all_results") or []):
            setup = row.get("entry_setup")
            price = row.get("trend", {}).get("price") if isinstance(row.get("trend"), dict) else None
            if not setup or not price:
                continue
            pivot = setup.get("pivot")
            if not pivot:
                continue
            dist_pct = (price / pivot - 1) * 100
            if -3 <= dist_pct <= 1:  # within 3% below or 1% above pivot
                candidates_near_pivot.append({
                    "symbol": row.get("symbol"),
                    "name": row.get("name"),
                    "score": row.get("score"),
                    "rating": row.get("rating"),
                    "price": price,
                    "pivot": pivot,
                    "stop": setup.get("stop"),
                    "setup_type": setup.get("type"),
                    "distance_to_pivot_pct": round(dist_pct, 2),
                    "rs_rank": row.get("rs_rank"),
                })
        candidates_near_pivot.sort(key=lambda x: -(x.get("score") or 0))
        candidates_near_pivot = candidates_near_pivot[:10]

    confidence = max(15, min(95, confidence))
    if confidence >= 70:
        verdict = "favorable"
        headline = f"Swing trading: GO. {len(candidates_near_pivot)} SEPA candidates within striking distance of pivot."
    elif confidence >= 45:
        verdict = "selective"
        headline = "Swing trading: SELECTIVE. Tighten stops on existing; only A+ new entries."
    else:
        verdict = "caution"
        headline = "Swing trading: NO NEW ENTRIES. Sit on cash, harvest stops on existing."

    return {
        "verdict": verdict,
        "headline": headline,
        "confidence": confidence,
        "reasons_pro": reasons_pro,
        "reasons_con": reasons_con,
        "candidates_near_pivot": candidates_near_pivot,
        "candidates_near_pivot_count": len(candidates_near_pivot),
    }


def _overall_action(day: dict, swing: dict, regime_data: dict) -> dict:
    """Single-line answer to 'what should I do today?'"""
    label = regime_data.get("label")
    if label == "market_in_correction":
        action = "sit_out"
        message = "Market in correction. Sit on cash. Use this time to study setups, not enter them."
    elif day["verdict"] == "favorable" and swing["verdict"] in ("favorable", "selective"):
        action = "go_long"
        message = "Both day-trade and swing-trade conditions are favorable. Trade both — day trades for income, swings for runners."
    elif day["verdict"] == "favorable":
        action = "day_trade_only"
        message = "Day-trade conditions are favorable but swing setups thin. Focus intraday."
    elif swing["verdict"] in ("favorable", "selective"):
        action = "swing_only"
        message = "Swing setups available but intraday tape is choppy. Play swings, skip day trades."
    else:
        action = "tighten_stops"
        message = "Mixed regime. Tighten stops on existing. Pass on new entries."

    return {"action": action, "message": message}


def _options_pulse_summary() -> dict:
    """Top SOIR-derived Schaeffer signals for the morning brief.

    Reads from the cached scan (refreshed nightly by cron). No chain
    fetches here — too slow for a request path. Returns up to 5 of each
    signal type so the morning card can show the strongest setups.
    """
    try:
        from options import soir as soir_mod
        rows = soir_mod.load_latest()
        if not rows:
            return {
                "available": False,
                "reason": "No SOIR data yet — run options.scanner once.",
            }
        bullish = sorted(
            [r for r in rows if r.get("signal") == "BULLISH"],
            key=lambda r: -(r.get("soir_percentile") or 0),
        )[:5]
        bearish = sorted(
            [r for r in rows if r.get("signal") == "BEARISH"],
            key=lambda r: (r.get("soir_percentile") or 100),
        )[:5]
        # Trim each row to a small payload — full record is too heavy
        def _slim(r: dict) -> dict:
            return {
                "symbol": r.get("symbol"),
                "soir": r.get("soir"),
                "soir_percentile": r.get("soir_percentile"),
                "expected_move_pct": r.get("expected_move_pct"),
                "atm_iv": r.get("atm_iv"),
                "signal": r.get("signal"),
                "reason": r.get("reason"),
            }
        return {
            "available": True,
            "n_bullish": len(bullish),
            "n_bearish": len(bearish),
            "bullish":   [_slim(r) for r in bullish],
            "bearish":   [_slim(r) for r in bearish],
            "as_of":     rows[0].get("scanned_at") if rows else None,
        }
    except Exception as exc:
        log.warning("options pulse summary failed: %s", exc)
        return {"available": False, "reason": str(exc)}


def _macbook_deals_section(limit: int = 3) -> dict:
    """Top N strict-verified MacBook deals for the morning brief card.

    Reads from the lifeboard_macbook_deals collection (populated by the
    02/07/12/17 ET cron). Every deal here passed verify_strict — final
    URL on a trusted retailer + a positive in-stock signal at scrape time.
    """
    try:
        from lifeboard import macbook as mb
        from lifeboard import config as lb_cfg
        cfg = lb_cfg.get_config(kind="macbook")
        deals = mb.list_deals(min_storage_gb=cfg.get("min_storage_gb", 256))
        # Trim to display payload — full record is heavy
        def _slim(d: dict) -> dict:
            return {
                "source":       d.get("source"),
                "title":        d.get("title"),
                "url":          d.get("url"),
                "price":        d.get("price"),
                "msrp":         d.get("msrp"),
                "discount_pct": d.get("discount_pct"),
                "config":       d.get("config"),
                "chip":         d.get("chip"),
                "storage_gb":   d.get("storage_gb"),
                "ram_gb":       d.get("ram_gb"),
                "notes":        d.get("notes"),
                "verified_at":  d.get("verified_at"),
                "first_seen":   d.get("first_seen"),
            }
        return {
            "available":      True,
            "count":          len(deals),
            "min_storage_gb": cfg.get("min_storage_gb", 256),
            "last_scan_at":   cfg.get("last_scan_at"),
            "deals":          [_slim(d) for d in deals[:limit]],
        }
    except Exception as exc:
        log.warning("macbook deals section failed: %s", exc)
        return {"available": False, "reason": str(exc), "deals": []}


def _holdings_section(user_email: str, scan: Optional[dict]) -> dict:
    """User's actual portfolio + day P/L + cross-reference with SEPA scan.

    Returns the rollup from `portfolio.api.build_summary` plus an `alerts`
    list per row (e.g. "near SEPA pivot today", "broke down -5%") so the
    brief can flag positions that need attention.
    """
    try:
        from portfolio.api import build_summary
        summary = build_summary(user_email)
        if not summary.get("available"):
            return summary

        # Cross-reference: which of my holdings appear in today's SEPA scan?
        # If a held ticker is "near pivot" or has a fresh setup, flag it.
        scan_by_symbol: dict[str, dict] = {}
        for row in ((scan or {}).get("all_results") or []):
            sym = row.get("symbol")
            if sym:
                scan_by_symbol[sym.upper()] = row

        for r in summary.get("rows", []):
            alerts: list[str] = []
            sr = scan_by_symbol.get(r["ticker"])
            if sr:
                setup = sr.get("entry_setup") or {}
                pivot = setup.get("pivot")
                price = r.get("last") or (sr.get("trend") or {}).get("price")
                if pivot and price:
                    dist = (price / pivot - 1) * 100
                    if -3 <= dist <= 1:
                        alerts.append(f"SEPA pivot {pivot:.2f} ({dist:+.1f}%)")
                rating = sr.get("rating")
                if rating in ("A+", "A"):
                    alerts.append(f"SEPA rating {rating}")
            dc = r.get("day_change_pct")
            if dc is not None:
                if dc <= -3:
                    alerts.append(f"down {dc:.1f}% today")
                elif dc >= 5:
                    alerts.append(f"up {dc:.1f}% today")
            r["alerts"] = alerts

        # Brief headline used by the UI card.
        pl_pct = summary.get("pl_pct")
        day_d = summary.get("day_dollars") or 0
        if pl_pct is None:
            summary["headline"] = f"{summary.get('count')} positions · cost ${summary.get('total_cost'):,.0f}"
        else:
            summary["headline"] = (
                f"${summary.get('total_value'):,.0f} · "
                f"{('+' if pl_pct >= 0 else '')}{pl_pct:.1f}% all-time · "
                f"{('+' if day_d >= 0 else '')}${day_d:,.0f} today"
            )
        return summary
    except Exception as exc:
        log.warning("holdings section failed: %s", exc)
        return {"available": False, "reason": str(exc), "rows": []}


@router.get("/morning/brief")
async def morning_brief(force: bool = False,
                        user_email: str = Depends(current_user_email)):
    """Morning synthesis. Pass ?force=true to bypass the regime + scan
    caches — used by the frontend on first open during 6-10am ET so the
    user gets a fresh view at decision time, not yesterday's snapshot."""
    scan = sepa_scanner.load_latest()
    rows = (scan or {}).get("all_results") or []
    # `force` bypasses the in-process market-regime cache; the SEPA scan
    # itself isn't re-run here (that's the cron's job at 4:30pm ET) — we
    # just re-evaluate the regime against the existing scan rows.
    regime_data = mr.regime(scan_rows=rows, force=force)

    day = _classify_day_trading(regime_data)
    swing = _classify_swing_trading(regime_data, scan)
    action = _overall_action(day, swing, regime_data)
    options_pulse = _options_pulse_summary()
    holdings = _holdings_section(user_email, scan)

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "regime": regime_data,
        "holdings": holdings,
        "day_trading": day,
        "swing_trading": swing,
        "options_pulse": options_pulse,
        "overall": action,
        "scan_age_minutes": _scan_age_minutes(scan),
    }


def _scan_age_minutes(scan: Optional[dict]) -> Optional[int]:
    if not scan:
        return None
    ts = scan.get("scanned_at") or scan.get("as_of")
    if not ts:
        return None
    try:
        import pandas as pd
        scanned = pd.Timestamp(ts)
        if scanned.tzinfo is None:
            scanned = scanned.tz_localize("UTC")
        now = pd.Timestamp.utcnow()
        if now.tzinfo is None:
            now = now.tz_localize("UTC")
        return int((now - scanned).total_seconds() // 60)
    except Exception:
        return None
