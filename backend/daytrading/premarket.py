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


def _session_now() -> str:
    """Current US-equity session in ET: regular | premarket | afterhours | closed.
    Drives whether we headline the live extended-hours move or the last regular gap."""
    try:
        import pandas as pd
        now = pd.Timestamp.now(tz="America/New_York")
    except Exception:
        return "closed"
    if now.weekday() >= 5:                         # Sat / Sun
        return "closed"
    mins = now.hour * 60 + now.minute
    if 4 * 60 <= mins < 9 * 60 + 30:
        return "premarket"
    if 9 * 60 + 30 <= mins < 16 * 60:
        return "regular"
    if 16 * 60 <= mins < 20 * 60:
        return "afterhours"
    return "closed"                                # 20:00–04:00 overnight


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

    session = _session_now()
    rows: list[dict] = []
    for s in syms:
        snap = snaps.get(s)
        if not snap:
            continue
        gap = snap.get("change_pct")                     # last regular-session move
        last = snap.get("price")                         # lastTrade (extended-hours aware)
        prev_close = snap.get("prev_close")
        reg_close = snap.get("reg_close") or 0.0

        # Extended-hours / overnight move vs the session-appropriate reference:
        #   premarket  → gap into the open vs the prior regular close
        #   afterhours → reaction vs today's regular close
        #   closed/ON  → last after-hours drift vs the most-recent regular close
        ext, ext_label = None, None
        if last:
            if session == "premarket":
                ref, ext_label = prev_close, "PM"
            elif session == "afterhours":
                ref, ext_label = (reg_close or prev_close), "AH"
            elif session == "closed":
                ref, ext_label = (reg_close or prev_close), "O/N"
            else:
                ref = None                               # regular hours → intraday gap only
            if ref:
                ext = round((last - ref) / ref * 100, 2)

        gap = round(float(gap), 2) if gap is not None else None
        # Keep the name if EITHER the regular gap OR the extended-hours move is material.
        if max(abs(gap or 0.0), abs(ext or 0.0)) < GAP_MIN_PCT:
            continue

        # Headline move: the live extended-hours move when in/around an extended
        # session, else the last regular session's gap.
        if session in ("premarket", "afterhours") and ext is not None:
            move = ext
        elif session == "closed":
            move = ext if (ext is not None and abs(ext) >= GAP_MIN_PCT) else gap
        else:
            move = gap

        vol = snap.get("volume")
        a = avg.get(s)
        relvol = round(float(vol) / float(a), 2) if (vol and a) else None
        rows.append({
            "symbol": s,
            "move_pct": round(float(move), 2) if move is not None else None,
            "direction": "up" if (move or 0) > 0 else "down",
            "gap_pct": gap,                               # last regular-session move
            "ext_move_pct": ext,                          # live extended-hours move
            "ext_label": ext_label,                       # PM | AH | O/N | None
            "rel_vol": relvol,                            # snapshot-volume vs 50d avg (rough)
            "last": last,
            "prev_close": prev_close,
        })

    # Rank: biggest move (regular or extended) backed by the most volume first.
    rows.sort(key=lambda r: -(abs(r.get("move_pct") or 0.0) * (r["rel_vol"] or 1.0)))
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
        "session": session,                          # regular | premarket | afterhours | closed
        "live": bool(rows),
        "as_of": datetime.now(timezone.utc).isoformat(),
        "disclaimer": ("Overnight movers from Massive realtime extended-hours data — "
                       "in/around premarket & after-hours the move is the live "
                       "extended-hours change vs the most-recent regular close; in "
                       "regular hours it's the intraday gap. Educational, not advice."),
    }
    _cache[profile] = {"ts": time.time(), "data": data}
    log.info("gappers[%s]: %d gappers (%d enriched)", profile, len(rows), len(top))
    return data
