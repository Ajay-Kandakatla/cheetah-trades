"""Live SEPA gate — recompute the price-dependent Trend Template + a live
relative-volume against the CURRENT quote, not the last scan.

Ajay 2026-06-11: KIM sat on the list at 7/8 Trend Template — it failed ONLY
"≥30% above the 52-week low" by a hair (29.5% on the cached close). Its live
price could cross 30% intraday and flip it to a qualifier, but the panel
froze the scan's value. "Make this live."

How it stays book-faithful (no formula drift): we do NOT re-implement any
gate. We patch the LIVE last-trade price into a COPY of the cached daily
frame's most recent bar and call the SAME trend_template.evaluate() the
scanner uses. The 8 checks, the 30% threshold, the MA math — all unchanged.
The RS-rank check (which evaluate() leaves True standalone) is filled from
the latest scan's rs_rank, since RS doesn't move intraday.

Volume: the cached daily dry-up picture (10d/50d) is left untouched (slow-
moving, honest). The LIVE relative volume is computed separately and
honestly — today's cumulative volume projected to a full session
(÷ fraction elapsed) vs the 50-day average — and labelled with how far
through the session we are, so a partial-day figure is never passed off as
a full-day 2.3x.

Cache-only + one live-quote call; no 2y refetch. GET /sepa/live-gate/{sym}.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger("sepa.live_gate")

# Pretty labels for the 8 Trend Template checks (book Trend Template, p.~80).
CHECK_LABEL = {
    "price_above_ma150_and_ma200": "price > 150- & 200-day MA",
    "ma150_above_ma200": "150-day MA > 200-day MA",
    "ma200_trending_up": "200-day MA trending up",
    "ma50_above_ma150_above_ma200": "50 > 150 > 200-day MA",
    "price_above_ma50": "price > 50-day MA",
    "at_least_30pct_above_52w_low": "≥30% above 52-week low",
    "within_25pct_of_52w_high": "within 25% of 52-week high",
    "rs_rank_at_least_70": "RS rank ≥ 70",
}


def _now_et() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        from datetime import timezone
        return datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.now().astimezone()


def session_fraction(now=None) -> float:
    """Fraction of the 9:30–16:00 ET regular session elapsed (0..1).
    0 pre-open, 1 after close — used to project today's volume pace."""
    now = now or _now_et()
    mins = now.hour * 60 + now.minute
    open_m, close_m = 9 * 60 + 30, 16 * 60
    if mins <= open_m:
        return 0.0
    if mins >= close_m:
        return 1.0
    return (mins - open_m) / (close_m - open_m)


def _patch_price(df, live_price: float):
    """Copy the frame and set its most-recent bar to the live price (overwrite
    today's bar, or append one if the last bar is a prior session). Volume is
    NOT touched — the dry-up averages stay honest."""
    import pandas as pd
    out = df.copy()
    today = pd.Timestamp(_now_et().date())
    last = out.index[-1]
    if last.normalize() == today:
        out.loc[last, "close"] = live_price
        out.loc[last, "high"] = max(float(out.loc[last, "high"]), live_price)
        out.loc[last, "low"] = min(float(out.loc[last, "low"]), live_price)
    else:
        prev_vol = float(out["volume"].iloc[-1]) if "volume" in out else 0.0
        out.loc[today] = {"open": live_price, "high": live_price,
                          "low": live_price, "close": live_price,
                          "volume": prev_vol}
    return out


def _scan_row(symbol: str) -> dict:
    try:
        from . import scanner
        for r in (scanner.load_latest() or {}).get("all_results") or []:
            if r.get("symbol") == symbol:
                return r
    except Exception as exc:
        log.debug("live_gate scan row failed %s: %s", symbol, exc)
    return {}


def live_gate(symbol: str) -> dict:
    """Live Trend Template + relative volume for one symbol."""
    from . import prices, trend_template, volume
    sym = (symbol or "").upper().strip()
    df = prices.load_prices(sym)
    if df is None or len(df) < 220:
        return {"ok": False, "reason": "insufficient daily history", "symbol": sym}

    q = (prices.bulk_live_prices([sym]) or {}).get(sym) or {}
    live_price = q.get("price") or q.get("last_trade_price")
    today_vol = q.get("volume")
    scan = _scan_row(sym)
    rs_rank = scan.get("rs_rank")

    if not live_price:
        # Market closed / no live tick — tell the FE to show the cached read.
        return {"ok": True, "live": False, "symbol": sym,
                "as_of": _now_et().isoformat(),
                "note": "no live quote (market closed or no recent tick) — "
                        "showing the last scan's values"}

    patched = _patch_price(df, float(live_price))
    tr = trend_template.evaluate(sym, patched)
    if tr is None:
        return {"ok": False, "reason": "trend evaluate failed", "symbol": sym}
    d = tr.to_dict() if hasattr(tr, "to_dict") else dict(tr)
    checks = dict(d.get("checks") or {})
    # evaluate() leaves RS True standalone; fill from the scan's real RS rank.
    if rs_rank is not None:
        checks["rs_rank_at_least_70"] = rs_rank >= 70
    passed = sum(1 for v in checks.values() if v)
    pass_all = all(checks.values())

    # nearest-to-flip failing check (the KIM insight)
    borderline = None
    if not checks.get("at_least_30pct_above_52w_low", True):
        lo = d.get("week52_low")
        pa = d.get("pct_above_low")
        if lo and pa is not None:
            borderline = {
                "check": "at_least_30pct_above_52w_low",
                "label": CHECK_LABEL["at_least_30pct_above_52w_low"],
                "current": pa, "needs": 30.0, "gap_pct": round(30.0 - pa, 2),
                "flips_at_price": round(lo * 1.30, 2),
            }

    # live relative volume — projected to a full session, honestly labelled
    vol = None
    try:
        vol = volume.analyze(df)  # cached daily dry-up picture (unpatched)
    except Exception:
        vol = None
    avg50 = (vol or {}).get("avg_vol_50")
    frac = session_fraction()
    proj_relvol = None
    if today_vol and avg50 and frac > 0:
        proj_relvol = round((today_vol / frac) / avg50, 2)

    return {
        "ok": True, "live": True, "symbol": sym,
        "as_of": _now_et().isoformat(),
        "price": round(float(live_price), 4),
        "change_pct": q.get("change_pct"),
        "trend": {
            "pass_all": pass_all, "passed": passed, "of": len(checks),
            "checks": checks,
            "labels": CHECK_LABEL,
            "pct_above_low": d.get("pct_above_low"),
            "pct_below_high": d.get("pct_below_high"),
            "week52_low": d.get("week52_low"),
            "week52_high": d.get("week52_high"),
        },
        "borderline": borderline,
        "qualifier_live": bool(pass_all and (scan.get("liquidity") or {}).get("liquid", True)),
        "qualifier_at_scan": bool(scan.get("is_candidate") or scan.get("qualifier")),
        "volume_live": {
            "today_volume": today_vol,
            "session_pct": round(frac * 100),
            "avg_vol_50": avg50,
            "projected_relvol": proj_relvol,
            "is_drying_up": (vol or {}).get("is_drying_up"),
            "vol_dryup": (vol or {}).get("vol_dryup"),
        },
        "rs_rank": rs_rank,
        "note": ("Trend Template recomputed against the LIVE price (same "
                 "book checks; MAs/52w-low from cache move negligibly "
                 "intraday). Projected RelVol = today's pace ÷ session "
                 "elapsed vs the 50-day average."),
    }
