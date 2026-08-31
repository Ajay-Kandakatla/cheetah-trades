"""Bullish chart patterns on ANY timeframe — hourly, 15-minute or daily.

Ajay 2026-08-29: "if there are any other bullish patterns on an hourly
chart I would like to know.. Such as Cup handle or Inverse head and
shoulder or Flat top. and any other bullish signals".

WHAT THIS REUSES AND WHAT IT DOES NOT
─────────────────────────────────────
The four detectors in `patterns/detector.py` (double bottom, inverse head
and shoulders, triple bottom, cup with handle) are Bulkowski/LMW-cited and
already carry their page references. This module runs those SAME functions
on a resampled frame; it does not re-derive them, and it does NOT write to
the pattern_observations ledger — that ledger is daily-only by design and
its accuracy stats would be corrupted by mixing bar sizes.

THE ONE THING THAT DOES NOT TRANSFER: the statistics
─────────────────────────────────────────────────────
Bulkowski's numbers — 62% throwback, the 61%/74% measure-rule factors, the
"47% dropped substantially within two months" warning — were all measured
on DAILY bars. The SHAPE rules are scale-free (three lows are three lows on
any chart); the HIT RATES are not. Every non-daily record here is stamped
`stats_transfer: False` and carries `stats_caveat`, and the app's own
forward ledger (`GET /patterns/accuracy`) likewise measures daily only.
Read an hourly cup as "this shape is present", never as "62% of these
throw back".

DURATION GATES ARE SCALED BY CALENDAR TIME, NOT COPIED
───────────────────────────────────────────────────────
Bulkowski cites cup duration as "7 to 65 weeks" — calendar, not bars. On a
daily chart 7 weeks is 35 bars; on an hourly chart it is ~245 (7 bars a
session), and on 15-minute ~910. Copying the daily bar-count would find a
"7-week cup" inside two sessions and label it with a citation it does not
have. `BARS_PER_SESSION` below converts, so the cited DURATION survives the
timeframe change even though the bar count does not.

FLAT TOP (ascending triangle) — the one new shape
──────────────────────────────────────────────────
Horizontal resistance tested repeatedly while lows rise into it: supply is
parked at one price, demand keeps paying up to reach it, and the apex
forces resolution. Bullish because the seller is the one being exhausted.

  * 2+ swing highs within `flat_tol_pct` of each other  → the flat top
  * 2+ swing lows, each strictly higher                 → the rising base
  * confirmation: a close above the flat top

SOURCE HONESTY: unlike the four detectors above, this one has NO cited
source in Ajay's library — the parameters below are this app's CONVENTION,
labelled as such, exactly the way `detector.py` labels its own uncited
choices. The measure rule (height added at the breakout) is the standard
construction and is reported as a measured move, never as a probability.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("patterns.timeframe")

# RTH bars per session, used to convert Bulkowski's calendar durations.
BARS_PER_SESSION = {"daily": 1, "60m": 7, "15m": 26}

# Flat top (ascending triangle) — CONVENTION, no cited source.
FLAT_TOL_PCT = 1.5          # how equal the highs must be to read as one level
MIN_TOUCHES = 2             # taps on the flat top
MIN_RISING_LOWS = 2         # rising lows beneath it
FLAT_MIN_BARS = 12          # shortest span that can look like a triangle
FLAT_MAX_BARS = 200
RISE_MIN_PCT = 0.5          # each low must clear the prior by this much

STATS_CAVEAT = (
    "Shape only. Bulkowski's hit rates, throwback frequency and measure-rule "
    "factors were measured on DAILY bars and do not transfer to this "
    "timeframe; this app's own forward ledger is daily-only too.")


def _scaled_kwargs(tf: str) -> dict:
    """Detector gates converted from daily bars to `tf` bars by calendar
    equivalence. Daily returns {} so the cited defaults are used verbatim."""
    mult = BARS_PER_SESSION.get(tf, 1)
    if mult <= 1:
        return {}
    return {
        # Cup: "7 to 65 weeks" in calendar time, expressed in tf bars.
        "cup_min_bars": 35 * mult,
        "cup_max_bars": 325 * mult,
        "handle_min_bars": 5 * mult,
        # Double bottom: LMW's "more than 22 trading days apart".
        "min_separation": 23 * mult,
        "max_separation": 35 * mult,
        # A 5-bar zigzag is a week on daily; keep it a week here too, but
        # cap it so a 15m frame does not need a month to find one swing.
        "swing_window": min(5 * mult, 12),
    }


def flat_top(df, *, flat_tol_pct: float = FLAT_TOL_PCT,
             min_touches: int = MIN_TOUCHES,
             min_rising_lows: int = MIN_RISING_LOWS,
             min_bars: int = FLAT_MIN_BARS, max_bars: int = FLAT_MAX_BARS,
             swing_window: int = 3) -> dict:
    """Ascending triangle: flat resistance, rising lows. {fresh: [...]}.

    Returns the same envelope shape as the cited detectors so callers can
    treat all five identically. Never raises.
    """
    out: dict = {"fresh": []}
    if df is None or len(df) < min_bars:
        return out
    try:
        from .detector import swing_points
        # swing_points yields (iloc, price) tuples — take the indices.
        sw_lows, sw_highs = swing_points(df, swing_window)
        lows_idx = [i for i, _p in sw_lows]
        highs_idx = [i for i, _p in sw_highs]
        highs = df["high"].to_numpy(dtype=float)
        lows = df["low"].to_numpy(dtype=float)
        closes = df["close"].to_numpy(dtype=float)
    except Exception as exc:                                # pragma: no cover
        log.warning("flat_top: frame unusable: %s", exc)
        return out
    if len(highs_idx) < min_touches or len(lows_idx) < min_rising_lows:
        return out

    last_close = float(closes[-1])
    n = len(df)
    # Walk candidate flat tops newest-first: the level nearest in time is the
    # one still in force.
    for a in range(len(highs_idx) - 1, 0, -1):
        anchor = highs_idx[a]
        level = float(highs[anchor])
        if level <= 0:
            continue
        touches = [i for i in highs_idx
                   if abs(float(highs[i]) - level) / level * 100.0 <= flat_tol_pct]
        if len(touches) < min_touches:
            continue
        first, last_t = min(touches), max(touches)
        span = last_t - first
        if span < min_bars or span > max_bars:
            continue
        # Rising lows strictly inside the triangle.
        inner = [i for i in lows_idx if first <= i <= n - 1]
        if len(inner) < min_rising_lows:
            continue
        rising, prev = [], None
        for i in inner:
            v = float(lows[i])
            if prev is None or (v - prev) / prev * 100.0 >= RISE_MIN_PCT:
                rising.append(i)
                prev = v
        if len(rising) < min_rising_lows:
            continue
        base = float(lows[rising[0]])
        height = level - base
        if height <= 0:
            continue
        confirmed = last_close > level
        out["fresh"].append({
            "kind": "flat_top",
            "label": "Flat top (ascending triangle)",
            "resistance": round(level, 4),
            "base": round(base, 4),
            "touches": len(touches),
            "rising_lows": len(rising),
            "span_bars": int(span),
            "height_pct": round(height / level * 100.0, 2),
            "confirmed": bool(confirmed),
            "breakout_level": round(level, 4),
            "entry": round(level, 4),
            "stop": round(float(lows[rising[-1]]), 4),
            "target": round(level + height, 4),
            "target_basis": "measured move — triangle height added at the top",
            "distance_pct": round((level - last_close) / last_close * 100.0, 2),
            "cited": False,
            "note": "CONVENTION parameters — no cited source in the library.",
        })
        break                                   # newest valid triangle only
    return out


def reachable(tf: str, bars: int) -> dict:
    """Which detectors CAN fire given this timeframe's bar budget.

    A cited pattern needs its cited calendar duration, and on fast bars
    that is a lot of them (a 7-week cup is 910 fifteen-minute bars). A
    detector that cannot reach its own minimum is reported as out of
    range, never left to return nothing and look broken.
    """
    kw = _scaled_kwargs(tf)
    need = {
        "cup_with_handle": kw.get("cup_min_bars", 35) + kw.get("handle_min_bars", 5),
        "double_bottom": kw.get("max_separation", 35) + 10,
        "triple_bottom": kw.get("max_separation", 35) * 2,
        "inverse_head_shoulders": 4 * kw.get("swing_window", 5) + 10,
        "flat_top": FLAT_MIN_BARS,
    }
    return {k: {"needs_bars": v, "reachable": bars >= v}
            for k, v in need.items()}


def scan(symbol: str, tf: str = "60m", *, df=None) -> dict:
    """Every bullish pattern this app can read, on one symbol, one timeframe.

    Always answers a dict — a thin frame or a data miss comes back with
    `patterns: []` and a reason, because this rides on a level surface that
    has to keep rendering.
    """
    from supply_demand import timeframes as tf_mod
    key = tf_mod.parse_tf(tf)
    meta = None
    if df is None:
        df, meta = tf_mod.frame_for(symbol, key)
    if df is None or not len(df):
        return {"symbol": (symbol or "").upper(), "timeframe": key,
                "patterns": [], "stats_transfer": key == "daily",
                "reason": (meta or {}).get("reason") or "no bars",
                "bars": 0}

    kw = _scaled_kwargs(key)
    found: list = []
    try:
        from .detector import DETECTORS
        for name, fn in DETECTORS.items():
            try:
                res = fn(df, **kw) or {}
            except Exception as exc:
                log.warning("timeframe scan: %s on %s failed: %s",
                            name, symbol, exc)
                continue
            for rec in (res.get("fresh") or []):
                found.append({**rec, "kind": rec.get("kind") or name,
                              "cited": True})
    except Exception as exc:                                # pragma: no cover
        log.warning("timeframe scan: detectors unavailable: %s", exc)

    try:
        sw = 3 if key == "daily" else max(2, min(kw.get("swing_window", 3), 5))
        found.extend(flat_top(df, swing_window=sw).get("fresh") or [])
    except Exception as exc:
        log.warning("timeframe scan: flat_top failed: %s", exc)

    transfers = key == "daily"
    for f in found:
        f["timeframe"] = key
        f["stats_transfer"] = transfers and bool(f.get("cited"))
        if not f["stats_transfer"]:
            f["stats_caveat"] = STATS_CAVEAT
    reach = reachable(key, len(df))
    return {"symbol": (symbol or "").upper(), "timeframe": key,
            "bars": len(df), "patterns": found,
            "stats_transfer": transfers,
            "gates_scaled": bool(kw),
            "reachable": reach,
            "out_of_range": [k for k, v in reach.items() if not v["reachable"]],
            "note": (None if transfers else STATS_CAVEAT)}
