"""Overnight gappers — the pre-market "set the day" checklist made live.

Operationalizes the day-trading pre-market routine: which names gapped overnight
≥ 2% on real volume, their premarket high/low (the intraday levels you trade off),
relative volume vs the 10-day average, and whether earnings land in the next
session.

Cheap broad pass: ONE bulk snapshot over the dynamic day-trade universe gives
gap% (last trade vs prev close) + today's volume for every name. We filter the
gappers, then enrich only the TOP N (in parallel) with premarket H/L (intraday
bars) + the proper 10-day relative volume + earnings-ahead — so the data cost
stays bounded.

Day-trading heuristics (configured, consistent with the gap_and_go strategy +
the in-app checklist), NOT a book formula:
  • gap ≥ 2%      — institutions repositioned overnight (Cameron / Warrior Trading).
  • RelVol ≥ 1.5× — elevated interest; < 1× = thin tape, slippage will hurt.

Not advice — a pre-market scan of what's in play.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger("daytrading.premarket")

GAP_MIN_PCT      = 2.0      # |gap| ≥ this → "in play"
REL_VOL_ELEVATED = 1.5      # RelVol ≥ this → elevated interest
ENRICH_TOP_N     = 15       # how many gappers to enrich with PM H/L + relvol + earnings
EARNINGS_SOON_DAYS = 2      # flag earnings within this many days
_TTL = 120                  # 2-min cache (premarket moves)

_cache: dict = {}


def _enrich_one(symbol: str) -> tuple[str, dict]:
    """Premarket H/L + proper 10-day relative volume + earnings-ahead for one
    name. Best-effort — any piece that fails just stays absent."""
    out: dict = {}
    try:
        from . import data as data_mod, indicators as ind
        df = data_mod.load_intraday(symbol, datetime.utcnow().date(), include_premarket=True)
        if df is not None and not df.empty:
            pm = ind.premarket_levels(df)
            if pm:
                out["pm_high"] = round(float(pm["high"]), 2)
                out["pm_low"] = round(float(pm["low"]), 2)
            rv = ind.relative_volume(df, lookback_days=10)
            if rv is not None:
                out["rel_vol_10d"] = round(float(rv), 2)
    except Exception as exc:
        log.debug("gappers: bar enrich failed %s: %s", symbol, exc)
    try:
        from catalysts.calendar import _next_earnings
        e = _next_earnings(symbol)
        if e and e.get("date"):
            d = datetime.strptime(e["date"], "%Y-%m-%d").date()
            today = datetime.now(timezone.utc).date()
            out["earnings_date"] = e["date"]
            out["earnings_soon"] = bool(today <= d <= today + timedelta(days=EARNINGS_SOON_DAYS))
    except Exception as exc:
        log.debug("gappers: earnings enrich failed %s: %s", symbol, exc)
    return symbol, out


def gappers(profile: str = "aggressive", force: bool = False) -> dict:
    """Overnight gappers for the day-trade universe, ranked by gap × relvol.
    Top names enriched with PM H/L + 10d RelVol + earnings. Cached `_TTL`."""
    from . import universe as U
    profile = U._norm_profile(profile)
    if not force:
        hit = _cache.get(profile)
        if hit and (time.time() - hit["ts"]) < _TTL:
            return hit["data"]

    pool = U.day_trade_universe(profile)["names"]
    avg = {n["symbol"]: n.get("avg_vol_50") for n in pool}
    syms = [n["symbol"] for n in pool]
    snaps = U._bulk_snapshot(syms)

    rows: list[dict] = []
    for s in syms:
        snap = snaps.get(s)
        if not snap:
            continue
        gap = snap.get("change_pct")
        if gap is None or abs(float(gap)) < GAP_MIN_PCT:
            continue
        vol = snap.get("volume")
        a = avg.get(s)
        relvol = round(float(vol) / float(a), 2) if (vol and a) else None
        rows.append({
            "symbol": s,
            "gap_pct": round(float(gap), 2),
            "direction": "up" if gap > 0 else "down",
            "rel_vol": relvol,                    # snapshot-volume vs 50d avg (rough)
            "last": snap.get("price"),
            "prev_close": snap.get("prev_close"),
        })

    # Rank: biggest gaps backed by the most volume first.
    rows.sort(key=lambda r: -(abs(r["gap_pct"]) * (r["rel_vol"] or 1.0)))
    top = rows[:ENRICH_TOP_N]

    if top:
        try:
            with ThreadPoolExecutor(max_workers=8) as ex:
                enriched = dict(ex.map(lambda r: _enrich_one(r["symbol"]), top))
            for r in top:
                r.update(enriched.get(r["symbol"], {}))
        except Exception as exc:
            log.warning("gappers: enrichment pool failed: %s", exc)

    data = {
        "gappers": top,
        "n_gappers": len(rows),
        "n_enriched": len(top),
        "gap_min_pct": GAP_MIN_PCT,
        "rel_vol_elevated": REL_VOL_ELEVATED,
        "profile": profile,
        "live": bool(rows),
        "as_of": datetime.now(timezone.utc).isoformat(),
        "disclaimer": ("Overnight gap scan — gap% is last trade vs prior close; "
                       "premarket H/L and 10-day RelVol enrich the top names. "
                       "Educational, not advice."),
    }
    _cache[profile] = {"ts": time.time(), "data": data}
    log.info("gappers[%s]: %d gappers (%d enriched)", profile, len(rows), len(top))
    return data
