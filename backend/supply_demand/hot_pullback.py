"""🔥 Hot Pullback — a HOT name takes one hard flush into a demand band and
reverses the same day.

Ajay 2026-09-09: *"Can you create a new tab for hot pull back like 21 day moving
average drops but have a reversal from demand zones? The drop should be someting
like DYN today which bounced back quick. I wanna see such names whcih dropped
huge but have been hot in the market. Are having reversals"*

THE ARCHETYPE — DYN, 2026-09-08 (measured, closed bars):
    prev close 24.28 -> opened 17.08 -> low 17.00 -> closed 20.31
    the low landed INSIDE a 4-touch demand band at 16.56-17.02 (strength 92)
    the close finished +19.5% off that low, 85% of the way up the day's range,
    20.6% under the 21-day line, on 11x average volume.

OWNER RULES. Price-structure heuristics, this app's own. No book, no cites —
this is Supply & Demand / day-trade scope, never Minervini (see the SEPA-scope
rule). Not advice, and nothing here places an order.

── WHAT THE STUDY FOUND (2 years, 2,650-name universe, no lookahead; bands
   rebuilt at every historical date from PRIOR bars only with the live
   geometry, `zone_store`'s own `demand_reentry.zone_geom`) ───────────────────

Placebo — every hot + liquid bar (n=238,857): fwd1 +0.05%, fwd3 +0.19%, 52% up.

  1. The flush and the snapback ALONE are WORSE than the placebo. A >=20% fall
     into a reversal close (n=5,314) gives ~50% up against 53%. The sharper the
     intraday snapback WITHOUT a zone, the worse it gets: off-low >=12% with a
     top-30% close measured fwd5 -2.83%, 47% up.
  2. The DEMAND BAND is the load-bearing condition. Same reversal NOT in a band
     (n=434): fwd1 +0.06%, bootstrap p=0.461 — no day-one effect at all.
  3. The full rule (n=65 events, 56 names): fwd1 +1.60% median / 62% up
     (p=0.000), fwd3 +2.50% / 63% up (p=0.001).
  4. **The edge is gone by day 5** — fwd5 +0.39%, 51% up, p=0.450. This is a
     one-to-three day trade, not a hold. That is exactly what "bounced back
     quick" means, and the numbers agree with him.
  5. Requiring a PROVEN band (2+ touches) makes it WORSE, not better: 52% up
     against 53% for any band, and 3+ touches drops to 50%. So the band must be
     tested, not proven — `is_proven_band` is deliberately NOT applied here.
  6. Entry matters. The signal day gaps DOWN into the next open 60% of the time
     (median -0.53%), so the next open is a BETTER fill than the close:
        at the signal close   fwd1 +1.60% / 62% up   fwd3 +2.50% / 63%
        at the NEXT OPEN      +1d  +2.40% / 57% up   +2d  +2.85% / 66%
        trigger over the signal-day high (fires 83% of the time)
                              +1d  +0.80%            +3d  +2.37% / 65% up,
                              and only 17% get stopped under the signal low
                              inside three sessions.
  7. THE SIMULATED TRADE, which is the number that actually decides it. A
     median forward return is not expectancy — a reviewer was right to say so.
     Buying the next open, stopping 0.5% under the signal-day low and exiting
     at the 21-day line or after 3 sessions (intrabar stops honoured), across
     the same 65 events: **58% win rate, mean +2.29%, median +2.37%, average
     win +8.28% against an average loss of -6.14%, expectancy +0.27R** on a
     median 8.4% risk. Exits: 42 on the clock, 15 stopped, 8 at target.
     The STOP is what makes it work — the raw column's -36.1% worst case
     becomes -13.3% once the stop is honoured, and NO simulated trade lost more
     than 15%.
  8. WHAT IS STILL WRONG WITH IT. 65 trades sit on only 41 distinct dates and
     one day carries six of them, so the trades are correlated market-wide
     flush days and the effective sample is nearer 41 than 65. And the rule is
     price-only: it cannot tell a liquidation flush from a permanent
     repricing. The archetype is the warning — DYN fell on 2026-09-08 because
     ANOTHER company (Avidity/Novartis) missed the primary endpoint that Dyne's
     own registrational study uses. Boudoukh et al. (NBER 18725) measured
     exactly this fork: after extreme moves, no-news names REVERSE while
     identified-news names CONTINUE. Nothing in this board sees that.

WHY THE EXISTING ALERTS CANNOT SHOW HIM THIS. On the archetype the close sat
+19.3% above the band top and had 3.4% of room to the first lid. Both standing
gates (`alert_gates`: <=1% above the band, >=5% room) correctly refuse it. This
board is a different question asked of the same structure, and it does NOT
loosen those gates — it never touches them.

RELATED, AND NOT THE SAME: `kell/reversal_extension.py` is Oliver Kell's
capitulation bottom (Victory in Stock Trading, pp. 16, 22-23) — extended below
the 10 EMA after a DOWNTREND. Ajay wants the opposite context: a name that has
been HOT and takes one hard hit. Kell's version has fired 4 times in this app
and triggered zero of them; its sibling `exhaustion_extension` fired 122 times
and triggered none. Different setup, kept separate on purpose.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

log = logging.getLogger("supply_demand.hot_pullback")

ET = ZoneInfo("America/New_York")

# ── the rule (owner constants; every one is a MEASURED cut, see the study) ──
HOT_ABOVE_52W_LOW_PCT = 30.0    # yesterday's close this far above its own 52w low
MIN_DOLLAR_VOL_USD = 5e6        # median 50-day dollar volume
FALL_FROM_10D_HIGH_PCT = -12.0  # today's LOW this far under the prior 10-day high
UNDER_MA21_PCT = -10.0          # today's close this far under the 21-day line
OFF_LOW_PCT = 8.0               # the close this far off today's low
RANGE_POS_MIN = 0.70            # and in the top 30% of today's range
MA_LEN = 21                     # "21 day moving average drops" — his words
HIGH_LOOKBACK = 10              # the prior 10-day high the flush is measured from

# What the study measured, carried on the payload so the board can print it and
# nobody has to trust a number typed into a component.
STUDY = {
    "events": 65, "names": 56, "window": "2 years",
    "fwd1_median_pct": 1.60, "fwd1_up_pct": 62, "fwd1_p": 0.000,
    "fwd3_median_pct": 2.50, "fwd3_up_pct": 63, "fwd3_p": 0.001,
    "fwd5_median_pct": 0.39, "fwd5_up_pct": 51, "fwd5_p": 0.450,
    "placebo_fwd1_pct": 0.05, "placebo_fwd3_pct": 0.19, "placebo_up_pct": 52,
    "no_band_fwd1_pct": 0.06, "no_band_p": 0.461, "no_band_n": 434,
    "next_open_fwd1_pct": 2.40, "next_open_fwd2_pct": 2.85, "next_open_up2_pct": 66,
    "trigger_rate_pct": 83, "trigger_fwd3_pct": 2.37, "trigger_up3_pct": 65,
    "trigger_stopped_3d_pct": 17,
    "worst_3d_pct": -36.1, "mean_fwd3_pct": 0.97,
    # THE SIMULATED TRADE — the numbers that actually decide it. Buy the next
    # open, stop 0.5% under the signal-day low, out at the 21-day line or after
    # 3 sessions, intrabar stops honoured. Added 2026-09-09 after a reviewer
    # correctly pointed out that a median forward return is not expectancy.
    "sim_n": 65, "sim_win_pct": 58,
    "sim_mean_pct": 2.29, "sim_median_pct": 2.37,
    "sim_avg_win_pct": 8.28, "sim_avg_loss_pct": -6.14,
    "sim_worst_pct": -13.3, "sim_best_pct": 19.9,
    "sim_median_risk_pct": 8.4, "sim_expectancy_r": 0.27,
    "sim_exit_clock": 42, "sim_exit_stop": 15, "sim_exit_target": 8,
    "sim_distinct_dates": 41,
}

CACHE_TTL_SEC = 180
MAX_ROWS = 60


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if v != v else v


# ── the pure rule ──────────────────────────────────────────────────────────
def is_hot(prev_close, low_252) -> bool:
    """Was it hot BEFORE the flush? Yesterday's close well above its own
    52-week low. Deliberately NOT 'near the 52-week high': the archetype was
    24% off its high when it broke."""
    pc, lo = _f(prev_close), _f(low_252)
    if pc is None or lo is None or lo <= 0:
        return False
    return (pc / lo - 1.0) * 100.0 >= HOT_ABOVE_52W_LOW_PCT


def flush_pct(day_low, high_10d) -> Optional[float]:
    """How far today's low fell below the prior 10-day high, negative."""
    lo, hi = _f(day_low), _f(high_10d)
    if lo is None or hi is None or hi <= 0:
        return None
    return (lo / hi - 1.0) * 100.0


def under_ma_pct(close, ma) -> Optional[float]:
    c, m = _f(close), _f(ma)
    if c is None or m is None or m <= 0:
        return None
    return (c / m - 1.0) * 100.0


def reversal(close, day_low, day_high) -> Optional[dict]:
    """The snapback: how far off the low the close finished, and where in the
    day's range it sits. None when the bar has no range."""
    c, lo, hi = _f(close), _f(day_low), _f(day_high)
    if c is None or lo is None or hi is None or lo <= 0 or hi <= lo:
        return None
    return {
        "off_low_pct": round((c / lo - 1.0) * 100.0, 2),
        "range_pos": round((c - lo) / (hi - lo), 3),
    }


def band_for_low(day_low, bands) -> Optional[dict]:
    """The demand band today's LOW landed inside, or None.

    Any TESTED demand band counts. `alert_gates.is_proven_band` is deliberately
    NOT applied: requiring 2+ touches measured WORSE (52% up vs 53%), and 3+
    touches worse again (50%). Tightening here would cost, not help.
    """
    lo = _f(day_low)
    if lo is None or lo <= 0:
        return None
    best = None
    for b in bands or []:
        if "demand" not in str(b.get("kind") or "").lower():
            continue
        blo, bhi = _f(b.get("lo")), _f(b.get("hi"))
        if blo is None or bhi is None or blo <= 0 or bhi < blo:
            continue
        if blo <= lo <= bhi:
            if best is None or (_f(b.get("strength")) or 0) > (_f(best.get("strength")) or 0):
                best = b
    return best


def qualifies(row: dict) -> tuple:
    """(ok, reasons). `row` carries the computed features. Every failure is
    named so the board can show near-misses instead of a silent empty list."""
    miss = []
    if not row.get("hot"):
        miss.append(f"not hot — the prior close is under {HOT_ABOVE_52W_LOW_PCT:g}% above its 52-week low")
    fall = _f(row.get("flush_pct"))
    if fall is None or fall > FALL_FROM_10D_HIGH_PCT:
        have = f"{fall:.1f}%" if fall is not None else "unknown"
        miss.append(f"the flush is only {have} off the 10-day high (rule {FALL_FROM_10D_HIGH_PCT:g}%)")
    ma = _f(row.get("under_ma21_pct"))
    if ma is None or ma > UNDER_MA21_PCT:
        have = f"{ma:.1f}%" if ma is not None else "unknown"
        miss.append(f"only {have} under the {MA_LEN}-day line (rule {UNDER_MA21_PCT:g}%)")
    rev = row.get("reversal") or {}
    if (_f(rev.get("off_low_pct")) or -99) < OFF_LOW_PCT:
        miss.append(f"the close is under {OFF_LOW_PCT:g}% off the low — no real snapback")
    if (_f(rev.get("range_pos")) or -1) < RANGE_POS_MIN:
        miss.append(f"the close is not in the top {(1-RANGE_POS_MIN)*100:.0f}% of the day's range")
    if not row.get("band"):
        miss.append("the low never reached a tested demand band — the study says this is the one that matters")
    return (not miss), miss


def plan_for(row: dict) -> Optional[dict]:
    """The measured plan. Entry is the NEXT OPEN (it measured better than the
    close, because the signal day gaps down into it 60% of the time), with the
    trigger variant carried alongside. Stop under the signal day's LOW, which is
    the low that tagged the band. Target is the 21-day line the flush fell
    from — the thing that has to be reclaimed for the pullback to be over."""
    close = _f(row.get("close"))
    low = _f(row.get("low"))
    high = _f(row.get("high"))
    ma21 = _f(row.get("ma21"))
    if close is None or low is None or high is None or low <= 0:
        return None
    stop = round(low * 0.995, 2)
    risk = (close - stop) / close * 100.0 if close > stop else None
    out = {
        "entry_note": "next open (measured better than the close: the signal day gaps down into it 60% of the time)",
        "trigger": round(high * 1.001, 2),
        "trigger_note": f"or wait for a trade over the signal-day high — fires {STUDY['trigger_rate_pct']}% of the time",
        "stop": stop,
        "stop_note": "0.5% under the signal-day low, the low that tagged the band",
        "risk_from_close_pct": round(risk, 1) if risk is not None else None,
        "target": round(ma21, 2) if ma21 else None,
        "target_note": f"the {MA_LEN}-day line the flush fell away from",
        "horizon": "1-3 sessions — the edge measured gone by day 5",
    }
    if ma21 and close > 0:
        out["target_pct"] = round((ma21 / close - 1.0) * 100.0, 1)
        if risk:
            out["rr"] = round((ma21 - close) / (close - stop), 1) if close > stop else None
    return out


def sort_key(row: dict) -> tuple:
    """Deepest flush first, then the strongest snapback. Nothing about mood
    or band 'quality' — both measured neutral-to-negative here."""
    return (_f(row.get("flush_pct")) or 0.0,
            -(_f((row.get("reversal") or {}).get("off_low_pct")) or 0.0))


def rules_lines() -> list:
    """Every line built from the enforcing constant."""
    s = STUDY
    return [
        f"Hot first: the prior close sits at least {HOT_ABOVE_52W_LOW_PCT:g}% above its own 52-week low, "
        f"median 50-day dollar volume at least ${MIN_DOLLAR_VOL_USD/1e6:.0f}M.",
        f"The flush: today's LOW is at least {abs(FALL_FROM_10D_HIGH_PCT):g}% under the prior "
        f"{HIGH_LOOKBACK}-day high AND the close is at least {abs(UNDER_MA21_PCT):g}% under the "
        f"{MA_LEN}-day line.",
        f"Into demand: that low landed inside a TESTED demand band. Requiring a proven 2+ touch band "
        f"measured worse (52% up vs 53%), so it is deliberately not required.",
        f"The snapback: the close finished at least {OFF_LOW_PCT:g}% off the low and in the top "
        f"{(1-RANGE_POS_MIN)*100:.0f}% of the day's range.",
        f"MEASURED ({s['events']} events, {s['names']} names, {s['window']}): next-open entry "
        f"+{s['next_open_fwd1_pct']:g}% median by the next close, +{s['next_open_fwd2_pct']:g}% by day 2 "
        f"({s['next_open_up2_pct']}% up), against a placebo of +{s['placebo_fwd1_pct']:g}% / "
        f"+{s['placebo_fwd3_pct']:g}%.",
        f"THE EDGE DIES BY DAY 5: fwd5 +{s['fwd5_median_pct']:g}%, {s['fwd5_up_pct']}% up, p={s['fwd5_p']:g}. "
        f"This is a 1-3 session trade, not a hold.",
        f"The demand band is what carries it: the same reversal NOT in a band (n={s['no_band_n']}) "
        f"measured +{s['no_band_fwd1_pct']:g}% on day 1, p={s['no_band_p']:g} — nothing.",
        f"THE ACTUAL TRADE, simulated: buy the next open, stop 0.5% under the signal-day low, out at the "
        f"21-day line or after 3 sessions. {s['sim_win_pct']}% win rate, mean {s['sim_mean_pct']:+g}%, "
        f"average win {s['sim_avg_win_pct']:+g}% against an average loss of {s['sim_avg_loss_pct']:g}%, "
        f"expectancy {s['sim_expectancy_r']:+g}R on a median {s['sim_median_risk_pct']:g}% risk. "
        f"Exits: {s['sim_exit_clock']} on the clock, {s['sim_exit_stop']} stopped, {s['sim_exit_target']} at target.",
        f"The STOP is what makes it work: the raw {s['worst_3d_pct']:g}% worst case becomes "
        f"{s['sim_worst_pct']:g}% once it is honoured, and no simulated trade lost more than 15%.",
        f"STILL WRONG WITH IT: {s['sim_n']} trades sit on only {s['sim_distinct_dates']} distinct dates, so they are "
        f"correlated flush days and the effective sample is nearer {s['sim_distinct_dates']} than {s['sim_n']}. "
        f"And the rule is price-only — it cannot tell a liquidation flush from a permanent repricing. DYN itself fell "
        f"because ANOTHER company missed the endpoint Dyne's own study uses.",
    ]


# ── the scan ───────────────────────────────────────────────────────────────
def _frames(symbols):
    """{sym: DataFrame} of CLOSED daily bars from the shared price cache.

    Closed bars only, straight from `price_cache`. Today's bar is NEVER taken
    from here — a cached doc written during the session holds a partial bar
    (the PHVS trap, 2026-09-08), so the live day comes from `bulk_snapshot`
    below, which is the tape rather than a frozen fragment.
    """
    import pandas as pd
    from sepa import prices
    coll = prices._get_mongo()
    if coll is None:
        return {}
    out = {}
    cur = coll.find({"symbol": {"$in": list(symbols)}}, {"symbol": 1, "bars": 1, "_id": 0})
    for d in cur:
        bars = d.get("bars") or []
        if len(bars) < 260:
            continue
        f = pd.DataFrame(bars).dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
        if len(f) >= 260:
            out[d["symbol"]] = f
    return out


def _today_bar(sym: str, snap: dict, frame) -> Optional[dict]:
    """Today's o/h/l/c/v for `sym`, and whether it is the live session or the
    last completed one. Returns None when there is nothing usable."""
    row = (snap or {}).get(sym) or {}
    o, h, l = _f(row.get("open")), _f(row.get("high")), _f(row.get("low"))
    c = _f(row.get("close"))
    v = _f(row.get("volume"))
    last_cached = str(frame["date"].iloc[-1])[:10]
    snap_date = str(row.get("date") or "")[:10]
    fresh = bool(snap_date and snap_date > last_cached)
    if fresh and c and h and l and l > 0 and h >= l:
        # RESTAMP GUARD (2026-09-09). Before the open, Massive rolls the
        # snapshot's `date` forward to today while the aggregate still holds
        # YESTERDAY's session. Taken at face value that dates the last closed
        # bar as today and prints a 0.0% day change on it (caught on DYN, whose
        # 09-08 flush came back stamped 09-09). A snapshot whose OHLC matches
        # the last cached bar to the cent is that restamp, not a live session.
        try:
            prev = frame.iloc[-1]
            same = all(
                abs(float(a) - float(b)) < 0.005
                for a, b in ((o, prev["open"]), (h, prev["high"]),
                             (l, prev["low"]), (c, prev["close"]))
                if a is not None and b == b
            )
        except Exception:
            same = False
        if not same:
            return {"open": o, "high": h, "low": l, "close": c, "volume": v,
                    "date": snap_date, "live": True}
    # fall back to the last CLOSED bar (evenings, weekends, a cold snapshot)
    r = frame.iloc[-1]
    try:
        return {"open": _f(r["open"]), "high": _f(r["high"]), "low": _f(r["low"]),
                "close": _f(r["close"]), "volume": _f(r.get("volume")),
                "date": last_cached, "live": False}
    except Exception:
        return None


def scan(universe_key: str = "full", limit: int = MAX_ROWS,
         include_near_miss: bool = True) -> dict:
    """Today's hot-pullback rows. Reads caches; never mutates the price cache."""
    import numpy as np
    from sepa import prices, universe as U
    from supply_demand import zone_store as ZS

    try:
        syms = sorted(set(U.load_universe(universe_key)))
    except Exception as exc:
        log.warning("hot_pullback: universe failed: %s", exc)
        return {"rows": [], "near_miss": [], "error": "universe unavailable"}

    frames = _frames(syms)
    if not frames:
        return {"warming": True, "rows": [], "near_miss": []}

    # one snapshot for the live day, one zone-store read for the bands
    try:
        snap = prices.bulk_snapshot(list(frames))
    except Exception as exc:
        log.warning("hot_pullback: snapshot failed: %s", exc)
        snap = {}
    try:
        store_day, store = ZS.load_latest(list(frames))
    except Exception as exc:
        log.warning("hot_pullback: zone_store failed: %s", exc)
        store_day, store = None, {}

    hits, near = [], []
    for sym, f in frames.items():
        try:
            c = f["close"].astype(float)
            h = f["high"].astype(float)
            v = f["volume"].astype(float)
            today = _today_bar(sym, snap, f)
            if not today or not today.get("close"):
                continue
            live = bool(today["live"])
            # history = every bar BEFORE today's
            hist_c = c if not live else c
            prior_c = hist_c.iloc[-1] if live else hist_c.iloc[-2]
            prior_hi10 = (h.iloc[-HIGH_LOOKBACK:] if live else h.iloc[-HIGH_LOOKBACK-1:-1]).max()
            lo252 = (hist_c.iloc[-252:] if live else hist_c.iloc[-253:-1]).min()
            ma_src = list(hist_c.iloc[-(MA_LEN-1):]) + [today["close"]] if live else list(hist_c.iloc[-MA_LEN:])
            ma21 = float(np.mean(ma_src))
            dvol = float((c * v).iloc[-50:].median())
            v50 = float(v.iloc[-50:].mean())

            row = {
                "symbol": sym, "date": today["date"], "live": live,
                "close": round(float(today["close"]), 4),
                "open": today["open"], "high": today["high"], "low": today["low"],
                "prev_close": round(float(prior_c), 4),
                "change_pct": round((today["close"] / float(prior_c) - 1) * 100, 2) if prior_c else None,
                "ma21": round(ma21, 4),
                "high_10d": round(float(prior_hi10), 4),
                "low_252": round(float(lo252), 4),
                "dollar_vol_musd": round(dvol / 1e6, 1),
                "vol_x": round(float(today["volume"]) / v50, 1) if (today.get("volume") and v50) else None,
                "hot": is_hot(prior_c, lo252),
                "above_52w_low_pct": round((float(prior_c) / float(lo252) - 1) * 100, 1) if lo252 else None,
                "flush_pct": round(flush_pct(today["low"], prior_hi10) or 0.0, 2),
                "under_ma21_pct": round(under_ma_pct(today["close"], ma21) or 0.0, 2),
                "reversal": reversal(today["close"], today["low"], today["high"]),
                "band": None,
            }
            if dvol < MIN_DOLLAR_VOL_USD:
                continue
            row["band"] = band_for_low(today["low"], (store.get(sym) or {}).get("bands") or [])
            ok, miss = qualifies(row)
            row["misses"] = miss
            row["plan"] = plan_for(row) if ok else None
            if ok:
                hits.append(row)
            elif include_near_miss and len(miss) == 1 and row["hot"]:
                near.append(row)
        except Exception as exc:                                # pragma: no cover
            log.debug("hot_pullback: %s failed: %s", sym, exc)

    hits.sort(key=sort_key)
    near.sort(key=sort_key)
    return {
        "warming": False,
        "universe": universe_key,
        "as_of": datetime.now(tz=ET).isoformat(timespec="seconds"),
        "zone_store_day": store_day.isoformat() if store_day else None,
        "scanned": len(frames),
        "n": len(hits),
        "rows": hits[:max(1, int(limit))],
        "near_miss": near[:12],
        "study": STUDY,
        "rules": rules_lines(),
    }


# ── cache ──────────────────────────────────────────────────────────────────
_CACHE: dict = {}
_LOCK = threading.Lock()
_SCAN_LOCKS: dict = {}


def _scan_lock(key: str) -> threading.Lock:
    """One lock per cache key, so two forced passes coalesce onto one scan."""
    with _LOCK:
        lk = _SCAN_LOCKS.get(key)
        if lk is None:
            lk = _SCAN_LOCKS[key] = threading.Lock()
        return lk


def cached_or_warm(universe_key: str = "full", limit: int = MAX_ROWS,
                   force: bool = False) -> dict:
    """Serve what we have, warm in a thread. Never blocks (the 2026-08-14 524)
    — EXCEPT under `force`, which blocks and re-scans.

    `force` used to fall through to the background-warm path and hand back the
    STALE board flagged `warming: True`. Two things read that as a failure: the
    Scan button, which showed the same rows and looked like nothing happened,
    and `record()`, which refuses a warming payload — so the 17:05 cron, the one
    the paper lane depends on, wrote nothing. The 2026-08-14 524 was a ~100s
    Cloudflare cut; this scan is ~6s, so blocking here is safe.
    """
    key = f"{universe_key}:{limit}"
    if force:
        with _LOCK:
            before = float((_CACHE.get(key) or {}).get("ts") or 0.0)
        with _scan_lock(key):
            with _LOCK:
                hit = _CACHE.get(key)
                if hit and float(hit.get("ts") or 0.0) > before and not hit.get("warming"):
                    return {**hit["data"], "cached": True}   # another Scan just ran
            data = scan(universe_key, limit)
            with _LOCK:
                _CACHE[key] = {"ts": time.time(), "data": data, "warming": False}
            return data
    now = time.time()
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and (now - hit["ts"]) < CACHE_TTL_SEC:
            return {**hit["data"], "cached": True}
        warming = bool(hit and hit.get("warming"))
    if hit and not warming:
        with _LOCK:
            _CACHE[key] = {**hit, "warming": True}

        def _work():
            try:
                data = scan(universe_key, limit)
                with _LOCK:
                    _CACHE[key] = {"ts": time.time(), "data": data, "warming": False}
            except Exception as exc:
                log.warning("hot_pullback warm failed: %s", exc)
                with _LOCK:
                    _CACHE[key] = {**_CACHE.get(key, {}), "warming": False}

        threading.Thread(target=_work, daemon=True).start()
        return {**hit["data"], "cached": True, "warming": True}
    data = scan(universe_key, limit)
    with _LOCK:
        _CACHE[key] = {"ts": time.time(), "data": data, "warming": False}
    return data


# ── history ────────────────────────────────────────────────────────────────
# The board is computed off the LATEST bar. During RTH that bar is today's
# live partial session, so a lane that re-scans at 09:35 sees rows dated TODAY
# and `hot_pullback_entry.signal_is_fresh` rejects every one of them — the lane
# could never fire. The signal day is a CLOSED session, so it has to be written
# down when it closes and read back the next morning. That is what this is for.
RUNS_COLL = "hot_pullback_runs"
_KEEP = ("symbol", "date", "live", "close", "open", "high", "low", "prev_close",
         "change_pct", "ma21", "high_10d", "low_252", "dollar_vol_musd", "vol_x",
         "above_52w_low_pct", "flush_pct", "under_ma21_pct", "reversal", "band",
         "plan", "misses")


def market_closed_reason(now: Optional[datetime] = None) -> Optional[str]:
    """'weekend' / 'holiday YYYY-MM-DD' / None — the one calendar
    (`market_hours.gate`). The BOARD still renders on a closed day, on purpose;
    only `record` is gated, so a holiday cron cannot write a history row built
    from stale prices."""
    try:
        from market_hours import gate
        return gate.closed_reason(now or datetime.now(ET))
    except Exception:
        return None


def _db():
    try:
        from sepa import prices as _p
        coll = _p._get_mongo()
        return coll.database if coll is not None else None
    except Exception as exc:                                   # pragma: no cover
        log.warning("hot_pullback: mongo unavailable: %s", exc)
        return None


def closed_session_rows(data: dict) -> tuple:
    """(day, rows) for the CLOSED session in a board payload, or (None, []).

    A row carrying `live: True` is today's unfinished bar. It is a fine thing to
    look at and a terrible thing to trade off tomorrow, so it never gets
    written. All recorded rows share one session date.
    """
    rows = [r for r in (data or {}).get("rows") or []
            if not r.get("live") and r.get("date")]
    if not rows:
        return None, []
    day = max(str(r["date"])[:10] for r in rows)
    return day, [r for r in rows if str(r["date"])[:10] == day]


def record(data: dict) -> bool:
    """Persist one completed pass to Mongo `hot_pullback_runs`, keyed by the
    CLOSED session it describes.

    Called from the endpoint when the cron asks for `record=true`, so the ONE
    scan that warms the API's own cache is also the one that lands in history.
    A cron running `python -m supply_demand.hot_pullback` in the cron container
    would warm a different process's memory and leave the page cold — the same
    trap the 09:25 demand-reentry curl exists to avoid.

    Idempotent: re-running the same session's cron replaces that day's doc
    rather than stacking duplicates.
    """
    if not data or data.get("warming"):
        return False
    closed = market_closed_reason()
    if closed:
        log.info("hot_pullback: not recording — market closed (%s)", closed)
        return False
    day, rows = closed_session_rows(data)
    if not day:
        log.info("hot_pullback: not recording — no closed-session row to write")
        return False
    db = _db()
    if db is None:
        return False
    try:
        getattr(db, RUNS_COLL).replace_one(
            {"day": day},
            {"day": day, "as_of": data.get("as_of"),
             "universe": data.get("universe"), "scanned": data.get("scanned"),
             "n": len(rows),
             "rows": [{k: r.get(k) for k in _KEEP} for r in rows],
             "near_miss": [{k: r.get(k) for k in _KEEP}
                           for r in (data.get("near_miss") or [])[:12]]},
            upsert=True)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("hot_pullback: persist failed: %s", exc)
        return False
    log.info("hot_pullback recorded %s: %d row(s)", day, len(rows))
    return True


def last_closed_signals(before: Optional[str] = None) -> tuple:
    """(day, rows) — the newest RECORDED closed session, for the paper lane.

    `before` (an ET date string) excludes that day and everything after it, so
    a lane running today reads yesterday's board and never its own morning.
    Returns (None, []) when nothing is recorded — the lane then buys nothing,
    which is the correct behaviour for a board that never scanned.
    """
    db = _db()
    if db is None:
        return None, []
    q = {"day": {"$lt": str(before)[:10]}} if before else {}
    try:
        doc = getattr(db, RUNS_COLL).find_one(q, sort=[("day", -1)])
    except Exception as exc:                                   # noqa: BLE001
        log.warning("hot_pullback: history read failed: %s", exc)
        return None, []
    if not doc:
        return None, []
    return doc.get("day"), list(doc.get("rows") or [])


def run(universe_key: str = "full", limit: int = MAX_ROWS) -> dict:
    """Manual / module entry point: scan, persist, seed this process's cache."""
    data = scan(universe_key, limit)
    record(data)
    with _LOCK:
        _CACHE[f"{universe_key}:{limit}"] = {
            "ts": time.time(), "data": data, "warming": False}
    return data


if __name__ == "__main__":  # pragma: no cover - manual entry
    logging.basicConfig(level=logging.INFO)
    d = run()
    print(f"{d.get('n')} row(s) of {d.get('scanned')} scanned")
