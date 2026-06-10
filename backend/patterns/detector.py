"""Pattern geometry — pure functions over daily OHLCV DataFrames.

Detection follows the Lo-Mamaysky-Wang approach in spirit (patterns defined as
geometric conditions on a sequence of local extrema) with Bulkowski's
identification conventions (two bottoms near-equal, weeks apart, a meaningful
interim peak, and — non-negotiable — the CONFIRMATION close above the peak /
neckline; the measure-rule target; the stop under the pattern low).

All numeric thresholds are CONFIGURED conventions (no magnitude threshold has
academic validation — Caginalp & Laurent's positive result explicitly removed
magnitude conditions). Every detector returns BOTH the current/fresh patterns
and the full historical list of confirmed events so the scanner can measure our
own universe's outcomes (self-validation) in the same pass.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

# ── Geometry — cited where a source exists, labeled CONVENTION where not ─────
# (verified pass 2026-06-09; see docs/scalping_methodology.md → Patterns)
SWING_WINDOW = 5            # CONVENTION — zigzag substitute for LMW's kernel-smoothed extrema
LOW_TOLERANCE_PCT = 3.0     # default inside the honest band: 1.5% (LMW Def. 5 strict) … 6% (Bulkowski)
MIN_SEPARATION = 23         # CITED — LMW: bottoms "more than 22 trading days" apart (after Edwards & Magee)
MAX_SEPARATION = 35         # CITED — Bulkowski: most double bottoms fall in the 2–7 week range
MIN_INTERIM_RISE_PCT = 10.0  # CITED — Bulkowski: ≥10% rise between the bottoms
CONFIRM_MAX_AGE = 1         # CONVENTION — a confirmation is actionable TODAY or yesterday only
                            # (Ajay 2026-06-09: "current day … or most recent past within 24
                            # hours. To make a decision in the moment, not to inform me of
                            # historical cup patterns"). Older confirmations live on ONLY in
                            # historical_confirms (self-validation + Chart School), never as
                            # a fresh match. Was 15 — that surfaced 3-week-old entries.
FORMING_MAX_GAP_PCT = 8.0   # CONVENTION — forming shown only within this of the line
FORMING_MAX_AGE = 60        # CONVENTION — no confirming close within 60 bars of low2 = expired
HEAD_DEPTH_PCT = 3.0        # CONVENTION — no head-depth gate is cited anywhere; this is ours
SHOULDER_TOL_PCT = 1.5      # CITED — LMW Def. 1: shoulders within 1.5% of their average
ARMPIT_TOL_PCT = 1.5        # CITED — LMW Def. 1: armpits within 1.5% of their average
VALIDATION_HORIZON = 21     # CONVENTION — self-validation forward window (bars ≈ 1 month)

# Triple bottom (Bulkowski tb.html, verified verbatim 2026-06-09)
TB_MIN_ADJ_SEP = 10         # CONVENTION — "three DISTINCT valleys" needs separation; no bar count is cited
TB_MAX_SPAN = 120           # CONVENTION — total width cap; the page cites no min/max duration
TB_TARGET_FACTOR = 0.74     # CITED — Bulkowski's measure rule multiplies the height by his 74% target-hit rate

# Cup with handle (Bulkowski cup.html, verified verbatim 2026-06-09)
CUP_MIN_BARS = 35           # CITED — cup duration "from 7 to 65 weeks" (7wk ≈ 35 bars)
CUP_MAX_BARS = 325          # CITED — 65 weeks ≈ 325 bars
RIM_TOL_PCT = 5.0           # CONVENTION — "rims near the same price level but be flexible" (no number cited)
CUP_MIN_DEPTH_PCT = 8.0     # CONVENTION — "a rounded turn that looks like a cup" needs real depth; uncited
CUP_U_SHAPE_BARS = 3        # CONVENTION — ≥3 bars near the low = "U-shaped, not V-shaped" operationalized
CUP_LOW_POS = (0.15, 0.85)  # CONVENTION — cup low must sit in the middle of the span (U, not a ramp)
HANDLE_MIN_BARS = 5         # CITED — handle "1 week minimum with no maximum"
CWH_TARGET_FACTOR = 0.61    # CITED — measure rule multiplies the height by his 61% target-hit rate


def swing_points(df: pd.DataFrame, window: int = SWING_WINDOW) -> tuple:
    """(lows, highs) — lists of (iloc_index, price) strict local extrema."""
    lows_arr = df["low"].to_numpy(dtype=float)
    highs_arr = df["high"].to_numpy(dtype=float)
    n = len(df)
    lows, highs = [], []
    for i in range(window, n - window):
        lo_win = lows_arr[i - window: i + window + 1]
        hi_win = highs_arr[i - window: i + window + 1]
        # First-occurrence-of-extreme semantics: ties (flat/double-touch lows)
        # yield ONE swing point, at the first bar that printed the extreme.
        if int(np.argmin(lo_win)) == window:
            lows.append((i, float(lows_arr[i])))
        if int(np.argmax(hi_win)) == window:
            highs.append((i, float(highs_arr[i])))
    return lows, highs


def _date(df: pd.DataFrame, i: int) -> str:
    ts = df.index[i]
    try:
        return ts.strftime("%Y-%m-%d")
    except Exception:
        return str(ts)


def _confirm_index(closes: np.ndarray, start: int, level: float) -> Optional[int]:
    """First bar index > start whose CLOSE exceeds `level`, or None."""
    for k in range(start + 1, len(closes)):
        if closes[k] > level:
            return k
    return None


def _dedupe_confirms(confirms: list) -> list:
    """Overlapping pattern pairs often share ONE breakout bar — count each
    confirmation bar once or the self-validation n is inflated with duplicates."""
    seen, out = set(), []
    for c in confirms:
        if c["confirm_idx"] in seen:
            continue
        seen.add(c["confirm_idx"])
        out.append(c)
    return out


def _pattern_record(df, kind, lows_idx, low_prices, neckline, confirm_idx,
                    last_close) -> dict:
    """Shared record shape for one detected pattern."""
    n = len(df)
    pattern_low = min(low_prices)
    target = neckline + (neckline - pattern_low)         # Bulkowski measure rule
    rec = {
        "pattern": kind,
        "lows": [{"date": _date(df, i), "price": round(p, 2)}
                 for i, p in zip(lows_idx, low_prices)],
        "neckline": round(neckline, 2),                  # the confirmation level
        "pattern_low": round(pattern_low, 2),
        "target": round(target, 2),                      # measure rule — a convention, not a promise
        "stop": round(pattern_low * 0.99, 2),            # just under the pattern low
        "last_close": round(last_close, 2),
    }
    if confirm_idx is not None:
        rec["status"] = "confirmed"
        rec["confirmed_date"] = _date(df, confirm_idx)
        rec["bars_since_confirm"] = n - 1 - confirm_idx
        rec["ext_past_confirm_pct"] = round((last_close / neckline - 1) * 100, 2)
    else:
        rec["status"] = "forming"
        rec["to_confirm_pct"] = round((neckline / last_close - 1) * 100, 2)
    return rec


def double_bottom(df: pd.DataFrame, **kw) -> dict:
    """Double bottom (W). Two near-equal swing lows, weeks apart, a ≥10% interim
    peak, CONFIRMED only on a close above that peak (Bulkowski's confirmation
    line — an unconfirmed W is a shape, not a signal).

    Returns {"fresh": [...], "historical_confirms": [(confirm_idx, neckline), ...]}.
    """
    tol = kw.get("low_tolerance_pct", LOW_TOLERANCE_PCT)
    min_sep = kw.get("min_separation", MIN_SEPARATION)
    max_sep = kw.get("max_separation", MAX_SEPARATION)
    min_rise = kw.get("min_interim_rise_pct", MIN_INTERIM_RISE_PCT)
    out: dict = {"fresh": [], "historical_confirms": []}
    if df is None or len(df) < min_sep + 2 * SWING_WINDOW + 5:
        return out
    closes = df["close"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    lows_arr = df["low"].to_numpy(dtype=float)
    last_close = float(closes[-1])
    swing_lows, _ = swing_points(df)
    n = len(df)
    seen_keys = set()

    for a in range(len(swing_lows)):
        i, p1 = swing_lows[a]
        for b in range(a + 1, len(swing_lows)):
            j, p2 = swing_lows[b]
            sep = j - i
            if sep < min_sep:
                continue
            if sep > max_sep:
                break
            lo, hi_p = min(p1, p2), max(p1, p2)
            if (hi_p / lo - 1) * 100 > tol:
                continue
            # The two bottoms must be the section's dominant lows.
            between_low = lows_arr[i + 1: j].min() if j - i > 1 else lo
            if between_low < lo * 0.995:
                continue
            peak = float(highs[i + 1: j].max())
            if (peak / lo - 1) * 100 < min_rise:
                continue
            k = _confirm_index(closes, j, peak)
            if k is not None:
                out["historical_confirms"].append({"confirm_idx": k, "neckline": peak,
                                                   "pattern_low": lo, "start_idx": i})
            # Fresh? confirmed recently, or still forming near the line (and not
            # expired — no confirming close within FORMING_MAX_AGE of low2).
            fresh_confirm = k is not None and (n - 1 - k) <= CONFIRM_MAX_AGE
            forming = (k is None and last_close > lo
                       and (n - 1 - j) <= FORMING_MAX_AGE
                       and (peak / last_close - 1) * 100 <= FORMING_MAX_GAP_PCT)
            if fresh_confirm or forming:
                key = (round(peak, 2), df.index[j])
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                out["fresh"].append(_pattern_record(
                    df, "double_bottom", [i, j], [p1, p2], peak, k, last_close))
    # Keep the most relevant per symbol: confirmed first, then nearest-to-confirm.
    out["historical_confirms"] = _dedupe_confirms(out["historical_confirms"])
    out["fresh"].sort(key=lambda r: (0 if r["status"] == "confirmed" else 1,
                                     r.get("bars_since_confirm", 99),
                                     r.get("to_confirm_pct", 99)))
    out["fresh"] = out["fresh"][:2]
    return out


def inverse_head_shoulders(df: pd.DataFrame, **kw) -> dict:
    """Inverse head-and-shoulders. Three swing lows — head below both shoulders,
    shoulders near-equal — confirmed on a close above the neckline (the higher
    of the two interim peaks; horizontal-neckline simplification, documented).
    """
    head_depth = kw.get("head_depth_pct", HEAD_DEPTH_PCT)
    sh_tol = kw.get("shoulder_tol_pct", SHOULDER_TOL_PCT)
    out: dict = {"fresh": [], "historical_confirms": []}
    if df is None or len(df) < 4 * SWING_WINDOW + 10:
        return out
    closes = df["close"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    last_close = float(closes[-1])
    swing_lows, _ = swing_points(df)
    n = len(df)
    seen = set()

    for t in range(len(swing_lows) - 2):
        (i, ls), (j, h), (k2, rs) = swing_lows[t], swing_lows[t + 1], swing_lows[t + 2]
        if not (h < ls and h < rs):
            continue
        if (min(ls, rs) / h - 1) * 100 < head_depth:
            continue                                     # head-depth gate — OUR convention (uncited)
        # LMW Definition 1 (CITED): shoulders within 1.5% of their average.
        sh_avg = (ls + rs) / 2.0
        if abs(ls - rs) / sh_avg * 100 > sh_tol:
            continue
        if k2 - i > MAX_SEPARATION * 2:
            continue
        peak1 = float(highs[i + 1: j].max()) if j - i > 1 else None
        peak2 = float(highs[j + 1: k2].max()) if k2 - j > 1 else None
        if not peak1 or not peak2:
            continue
        # LMW Definition 1 (CITED): armpits within 1.5% of their average too.
        ap_avg = (peak1 + peak2) / 2.0
        if abs(peak1 - peak2) / ap_avg * 100 > ARMPIT_TOL_PCT:
            continue
        # Horizontal-neckline simplification: confirm above the HIGHER armpit —
        # conservative vs the sloping line at breakout time (documented).
        neckline = max(peak1, peak2)
        if (neckline / h - 1) * 100 < MIN_INTERIM_RISE_PCT:
            continue
        c = _confirm_index(closes, k2, neckline)
        if c is not None:
            out["historical_confirms"].append({"confirm_idx": c, "neckline": neckline,
                                               "pattern_low": h, "start_idx": i})
        fresh_confirm = c is not None and (n - 1 - c) <= CONFIRM_MAX_AGE
        forming = (c is None and last_close > h
                   and (n - 1 - k2) <= FORMING_MAX_AGE
                   and (neckline / last_close - 1) * 100 <= FORMING_MAX_GAP_PCT)
        if fresh_confirm or forming:
            key = (round(neckline, 2), df.index[k2])
            if key in seen:
                continue
            seen.add(key)
            rec = _pattern_record(df, "inverse_head_shoulders",
                                  [i, j, k2], [ls, h, rs], neckline, c, last_close)
            rec["stop"] = round(rs * 0.99, 2)            # under the right shoulder
            out["fresh"].append(rec)
    out["historical_confirms"] = _dedupe_confirms(out["historical_confirms"])
    out["fresh"].sort(key=lambda r: (0 if r["status"] == "confirmed" else 1,
                                     r.get("bars_since_confirm", 99),
                                     r.get("to_confirm_pct", 99)))
    out["fresh"] = out["fresh"][:1]
    return out


def triple_bottom(df: pd.DataFrame, **kw) -> dict:
    """Triple bottom. Bulkowski's ID rules (tb.html, verified verbatim):
    "three distinct valleys that look similar", bottoming "near the same price
    — allow variations", and the pattern "confirms as a true triple bottom once
    price closes above the highest peak between the valleys". His volume
    guideline (downward 61% of the time) is descriptive, so it does not gate.
    Measure rule per the page: height × 74% added to the breakout price.
    """
    tol = kw.get("low_tolerance_pct", LOW_TOLERANCE_PCT)
    out: dict = {"fresh": [], "historical_confirms": []}
    if df is None or len(df) < 2 * TB_MIN_ADJ_SEP + 2 * SWING_WINDOW + 5:
        return out
    closes = df["close"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    lows_arr = df["low"].to_numpy(dtype=float)
    last_close = float(closes[-1])
    swing_lows, _ = swing_points(df)
    n = len(df)
    seen = set()

    for t in range(len(swing_lows) - 2):
        (i, p1), (j, p2), (k2, p3) = swing_lows[t], swing_lows[t + 1], swing_lows[t + 2]
        if j - i < TB_MIN_ADJ_SEP or k2 - j < TB_MIN_ADJ_SEP:
            continue
        if k2 - i > TB_MAX_SPAN:
            continue
        lo = min(p1, p2, p3)
        if (max(p1, p2, p3) / lo - 1) * 100 > tol:
            continue                                     # valleys not "near the same price"
        # The three valleys must be the section's dominant lows (nothing between
        # undercuts them — same dominance check as the double bottom).
        if float(lows_arr[i + 1: k2].min()) < lo * 0.995:
            continue
        peak1 = float(highs[i + 1: j].max()) if j - i > 1 else None
        peak2 = float(highs[j + 1: k2].max()) if k2 - j > 1 else None
        if not peak1 or not peak2:
            continue
        neckline = max(peak1, peak2)                     # CITED — "the highest peak between the valleys"
        if (neckline / lo - 1) * 100 < MIN_INTERIM_RISE_PCT:
            continue                                     # rises between valleys must be real (shared gate)
        c = _confirm_index(closes, k2, neckline)
        if c is not None:
            out["historical_confirms"].append({"confirm_idx": c, "neckline": neckline,
                                               "pattern_low": lo, "start_idx": i})
        fresh_confirm = c is not None and (n - 1 - c) <= CONFIRM_MAX_AGE
        forming = (c is None and last_close > lo
                   and (n - 1 - k2) <= FORMING_MAX_AGE
                   and (neckline / last_close - 1) * 100 <= FORMING_MAX_GAP_PCT)
        if fresh_confirm or forming:
            key = (round(neckline, 2), df.index[k2])
            if key in seen:
                continue
            seen.add(key)
            rec = _pattern_record(df, "triple_bottom",
                                  [i, j, k2], [p1, p2, p3], neckline, c, last_close)
            # Bulkowski's stated measure rule: height × his 74% target-hit rate.
            rec["target"] = round(neckline + TB_TARGET_FACTOR * (neckline - lo), 2)
            out["fresh"].append(rec)
    out["historical_confirms"] = _dedupe_confirms(out["historical_confirms"])
    out["fresh"].sort(key=lambda r: (0 if r["status"] == "confirmed" else 1,
                                     r.get("bars_since_confirm", 99),
                                     r.get("to_confirm_pct", 99)))
    out["fresh"] = out["fresh"][:1]
    return out


def cup_with_handle(df: pd.DataFrame, **kw) -> dict:
    """Cup with handle. Bulkowski's ID rules (cup.html, verified verbatim):
    a U-shaped (not V-shaped) cup of "7 to 65 weeks", "cup rims should be near
    the same price level but be flexible", a mandatory handle on the right of
    "1 week minimum with no maximum, forming in the upper half of the cup", and
    breakout above the right cup lip. Measure rule per the page: height (right
    lip to lowest valley) × 61% added to the breakout price.
    """
    rim_tol = kw.get("rim_tol_pct", RIM_TOL_PCT)
    out: dict = {"fresh": [], "historical_confirms": []}
    if df is None or len(df) < CUP_MIN_BARS + HANDLE_MIN_BARS + 2 * SWING_WINDOW:
        return out
    closes = df["close"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    lows_arr = df["low"].to_numpy(dtype=float)
    last_close = float(closes[-1])
    _, swing_highs = swing_points(df)
    n = len(df)
    seen = set()

    for a in range(len(swing_highs)):
        i, left_rim = swing_highs[a]
        for b in range(a + 1, len(swing_highs)):
            j, right_rim = swing_highs[b]
            span = j - i
            if span < CUP_MIN_BARS:
                continue
            if span > CUP_MAX_BARS:
                break
            rim_avg = (left_rim + right_rim) / 2.0
            if abs(left_rim - right_rim) / rim_avg * 100 > rim_tol:
                continue                                 # rims not near the same level
            inner_lows = lows_arr[i + 1: j]
            cup_low = float(inner_lows.min())
            depth_pct = (min(left_rim, right_rim) / cup_low - 1) * 100
            if depth_pct < CUP_MIN_DEPTH_PCT:
                continue                                 # too shallow to be a cup (our gate)
            # Nothing inside the cup may poke meaningfully above the rims.
            if float(highs[i + 1: j].max()) > max(left_rim, right_rim) * 1.005:
                continue
            # U-shape, operationalized: the low sits in the middle of the span
            # and price spent ≥ CUP_U_SHAPE_BARS bars near it (not a one-bar V).
            m_rel = int(np.argmin(inner_lows)) + 1
            if not (CUP_LOW_POS[0] * span <= m_rel <= CUP_LOW_POS[1] * span):
                continue
            if int((inner_lows <= cup_low * 1.05).sum()) < CUP_U_SHAPE_BARS:
                continue
            # Handle: everything after the right rim must hold the upper half
            # of the cup ("forming in the upper half") for ≥ HANDLE_MIN_BARS.
            half_level = right_rim - 0.5 * (right_rim - cup_low)
            c = _confirm_index(closes, j + HANDLE_MIN_BARS - 1, right_rim)
            handle_end = c if c is not None else n
            if handle_end - (j + 1) < HANDLE_MIN_BARS:
                continue                                 # no handle yet — still just a cup
            handle_lows = lows_arr[j + 1: handle_end]
            if handle_lows.size == 0 or float(handle_lows.min()) < half_level:
                continue                                 # handle broke the upper half — pattern void
            if c is not None:
                out["historical_confirms"].append({"confirm_idx": c, "neckline": right_rim,
                                                   "pattern_low": cup_low, "start_idx": i})
            fresh_confirm = c is not None and (n - 1 - c) <= CONFIRM_MAX_AGE
            forming = (c is None
                       and (right_rim / last_close - 1) * 100 <= FORMING_MAX_GAP_PCT)
            if fresh_confirm or forming:
                key = (round(right_rim, 2), df.index[j])
                if key in seen:
                    continue
                seen.add(key)
                rec = _pattern_record(df, "cup_with_handle",
                                      [i + 1 + (m_rel - 1)], [cup_low],
                                      right_rim, c, last_close)
                # Bulkowski's stated measure rule: height × his 61% hit rate.
                rec["target"] = round(right_rim + CWH_TARGET_FACTOR * (right_rim - cup_low), 2)
                # Stop under the handle low (tighter than the cup low — the cup
                # low invalidates far too late; same under-the-low family).
                rec["stop"] = round(float(handle_lows.min()) * 0.99, 2)
                rec["rims"] = [{"date": _date(df, i), "price": round(left_rim, 2)},
                               {"date": _date(df, j), "price": round(right_rim, 2)}]
                rec["handle_low"] = round(float(handle_lows.min()), 2)
                out["fresh"].append(rec)
    out["historical_confirms"] = _dedupe_confirms(out["historical_confirms"])
    out["fresh"].sort(key=lambda r: (0 if r["status"] == "confirmed" else 1,
                                     r.get("bars_since_confirm", 99),
                                     r.get("to_confirm_pct", 99)))
    out["fresh"] = out["fresh"][:1]
    return out


DETECTORS = {
    "double_bottom": double_bottom,
    "inverse_head_shoulders": inverse_head_shoulders,
    "triple_bottom": triple_bottom,
    "cup_with_handle": cup_with_handle,
}


def measure_outcomes(df: pd.DataFrame, confirms: list,
                     horizon: int = VALIDATION_HORIZON) -> list:
    """Self-validation: for each historical confirmation with a full forward
    window, the +horizon close-to-close return and the max gain within it."""
    closes = df["close"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    out = []
    for c in confirms:
        k = c["confirm_idx"]
        if k + horizon >= len(closes):
            continue                                     # window not complete — skip, don't peek
        base = closes[k]
        if base <= 0:
            continue
        fwd = (closes[k + horizon] / base - 1) * 100
        max_gain = (highs[k + 1: k + horizon + 1].max() / base - 1) * 100
        out.append({"fwd_pct": round(float(fwd), 2),
                    "max_gain_pct": round(float(max_gain), 2)})
    return out
