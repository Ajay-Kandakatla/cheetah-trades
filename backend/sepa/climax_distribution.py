"""Climax-top institutional distribution — "selling on the way up".

Ajay 2026-06-21: "on the climax run the volume momentum and bulk purchase by
customers make institutions sell in bulk. Can you track the concept."

This is Minervini's climax-top mechanic, verbatim (Think & Trade Like a Champion,
Ch.9 pp.186-188):

    "big institutions need buyers to absorb their large blocks of shares … as a
    result, liquidation takes place on the way up when the price is advancing and
    there are buyers available, as the stock moves from strong professional hands
    to weak retail hands. Eventually, the large institutional volume overwhelms
    the retail appetite, and the stock comes crashing down."  (p.186)

So during a parabolic climax run, the retail bulk-buying (volume momentum, a run
of up days) is the *liquidity* institutions sell their big blocks into. We detect
that syndrome — the stock is still going UP, but the tape shows the big boys
distributing — so the read is "sell into strength," BEFORE the breakdown that
`sell_signals.evaluate` (TLSW Ch.12-13) catches after the fact. The two are
complementary: this is the top, that is the break.

The book's specific, quantifiable tells (p.187-188):
  * Climax run — price up 25-50%+ in one to three weeks (p.187).
  * Up-day dominance — "70 percent or more up days … over a 7- to 15-day period"
    (the retail demand, p.187).
  * Heavy volume on a DOWN day — "If so, then you are seeing large investors
    liquidating their positions" (p.188).
  * The largest-volume day of the move is a DOWN day — distribution (p.188).
  * Churning — "elevated volume without much price progress" (p.188).
  * High-volume reversal — closes weak on heavy volume after running up (p.188).
  * The last blast — largest up day / widest spread / a recent exhaustion gap
    "usually signals that the run is over" (p.187-188).

Pure function: df (OHLCV) in, dict out. Display / read only — it does NOT feed the
SEPA score or any buy gate. A read for names you OWN or are watching late.
"""
from __future__ import annotations

from typing import Optional
import pandas as pd

# ── Thresholds — all book-derived (TTLAC pp.186-188) ─────────────────────────
CLIMAX_WINDOW          = 15      # "one to three weeks" — 3 trading weeks (p.187)
CLIMAX_GAIN_MIN        = 25.0    # "+25 to 50 percent or more" over the window (p.187)
UP_DAY_WINDOW          = 10      # "7- to 15-day period" — read the last 10 (p.187)
UP_DAY_RATIO_MIN       = 0.70    # "70 percent or more up days" (p.187)
HEAVY_VOL_MULT         = 1.5     # heavy = > 1.5× the 50-day average volume
CHURN_PROGRESS_MAX_PCT = 1.0     # churn = heavy volume but |daily move| < 1% (p.188)
REVERSAL_LOC_MAX       = -0.10   # close in the lower part of the range = reversal (p.188)
EXHAUSTION_GAP_MIN_PCT = 3.0     # a gap-up open ≥ 3% above the prior close (p.188)
RECENT_BARS            = 5       # "can occur on just one or a few days" (p.188)


def _close_loc(h: float, l: float, c: float) -> float:
    rng = h - l
    return (((c - l) - (h - c)) / rng) if rng > 0 else 0.0


def detect(df: pd.DataFrame, bc: Optional[dict] = None) -> dict:
    """Read the climax-top institutional-distribution syndrome.

    ``bc`` is the optional base-count blob (sepa.base_count) — a late/extended
    base raises conviction (the book reads these tells "once the stock is
    extended", p.187), but is not required. Returns a dict; never raises."""
    base = {
        "is_distribution": False, "in_climax": False, "read": "none",
        "climax_gain_pct": None, "up_day_ratio": None, "up_day_dominant": False,
        "severity": 0, "tells": {}, "note": None,
    }
    try:
        if df is None or len(df) < 60:
            return base
        c = df["close"].astype(float)
        h = df["high"].astype(float)
        l = df["low"].astype(float)
        v = df["volume"].astype(float)
        n = len(df)
        last = float(c.iloc[-1])
        avg50 = float(v.iloc[-50:].mean()) or 1.0

        # Climax run magnitude over the trailing window (p.187).
        ref = float(c.iloc[-(CLIMAX_WINDOW + 1)]) if n > CLIMAX_WINDOW else float(c.iloc[0])
        climax_gain = ((last / ref) - 1.0) * 100.0 if ref > 0 else 0.0
        in_climax = climax_gain >= CLIMAX_GAIN_MIN

        # Up-day dominance over the read window (p.187).
        ups = downs = 0
        for i in range(n - UP_DAY_WINDOW, n):
            if i < 1:
                continue
            if c.iloc[i] > c.iloc[i - 1]:
                ups += 1
            elif c.iloc[i] < c.iloc[i - 1]:
                downs += 1
        total = ups + downs
        up_day_ratio = (ups / total) if total else 0.0
        up_day_dominant = up_day_ratio >= UP_DAY_RATIO_MIN

        # ── Distribution tells, read over the climax window ──────────────────
        wstart = max(1, n - CLIMAX_WINDOW)
        heavy_down_day = False
        churning = False
        high_vol_reversal = False
        exhaustion_gap = False
        max_vol = -1.0
        max_vol_is_down = False
        for i in range(wstart, n):
            vi = float(v.iloc[i])
            ci = float(c.iloc[i]); cp = float(c.iloc[i - 1])
            ret = ((ci - cp) / cp * 100.0) if cp > 0 else 0.0
            heavy = vi > HEAVY_VOL_MULT * avg50
            loc = _close_loc(float(h.iloc[i]), float(l.iloc[i]), ci)
            if vi > max_vol:
                max_vol = vi
                max_vol_is_down = ci < cp
            if heavy and ci < cp:
                heavy_down_day = True                              # p.188
            if heavy and abs(ret) < CHURN_PROGRESS_MAX_PCT:
                churning = True                                    # p.188
            if i >= n - RECENT_BARS:                               # the recent tape
                if heavy and loc <= REVERSAL_LOC_MAX and ret <= 0:
                    high_vol_reversal = True                       # p.188
                if float(df["open"].iloc[i]) >= cp * (1 + EXHAUSTION_GAP_MIN_PCT / 100.0):
                    exhaustion_gap = True                          # p.188

        largest_vol_down_in_move = bool(max_vol_is_down)           # p.188

        tells = {
            "heavy_volume_down_day": heavy_down_day,
            "largest_volume_down_in_move": largest_vol_down_in_move,
            "churning": churning,
            "high_volume_reversal": high_vol_reversal,
            "exhaustion_gap": exhaustion_gap,
        }
        # Distribution evidence = the selling tells (not the climb itself).
        sell_tells = [heavy_down_day, largest_vol_down_in_move, churning, high_vol_reversal]
        severity = sum(1 for t in sell_tells if t)
        late = bool(bc and (bc.get("is_late_stage") or bc.get("is_avoid_stage")))

        is_distribution = bool(in_climax and severity >= 1)
        if is_distribution:
            read = "distribution_underway"
            note = ("Climax run +%.0f%% with %.0f%% up days — and the tape shows "
                    "institutions distributing into it (sell into strength, "
                    "TTLAC p.186-188)." % (climax_gain, up_day_ratio * 100))
        elif in_climax and up_day_dominant:
            read = "climax_extended"
            note = ("Climax run +%.0f%% on %.0f%% up days — extended/exhaustion "
                    "risk; watch for heavy-volume down days (TTLAC p.187)."
                    % (climax_gain, up_day_ratio * 100))
        else:
            read = "none"
            note = None

        return {
            "is_distribution": is_distribution,
            "in_climax": in_climax,
            "read": read,
            "climax_gain_pct": round(climax_gain, 1),
            "up_day_ratio": round(up_day_ratio, 2),
            "up_day_dominant": up_day_dominant,
            "severity": severity,
            "late_stage": late,
            "tells": tells,
            "note": note,
        }
    except Exception:
        return base
