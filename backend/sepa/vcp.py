"""VCP — Volatility Contraction Pattern detector.

Book Ch 10 (p.198-213):
  - Base forms over 3-65 weeks after a Stage 2 advance.
  - 2 to 6 successive contractions ("Ts"), each ~half the previous.
  - Total base depth typically 10-35%; AVOID >60% corrections (failure-prone).
  - Right-side tightness: final pullback <10%, volume drying up.
  - Pivot = high of final contraction. Buy on volume expansion above pivot.

Algorithm (pragmatic approximation):
  1. Find local high (peak of the base) and local low (deepest trough) in the
     lookback window.
  2. From peak, find sequence of lower pivots (tops of each rally) separated
     by troughs. Each (top→trough) drop is one contraction.
  3. Contractions must be monotonically shrinking (within tolerance).
  4. Final contraction depth <= 10% (tight right side).
  5. Emit pivot = most recent swing-high; stop = deepest point of final contraction.
"""
from __future__ import annotations

from typing import Optional, List, Tuple
import pandas as pd
import numpy as np


def _find_swings(c: pd.Series, window: int = 5) -> List[Tuple[int, float, str]]:
    """Return [(idx, price, 'H'|'L'), ...] using simple local-extrema rule."""
    arr = c.values
    n = len(arr)
    out: List[Tuple[int, float, str]] = []
    for i in range(window, n - window):
        left = arr[i - window:i]
        right = arr[i + 1:i + 1 + window]
        if arr[i] >= left.max() and arr[i] >= right.max():
            out.append((i, float(arr[i]), "H"))
        elif arr[i] <= left.min() and arr[i] <= right.min():
            out.append((i, float(arr[i]), "L"))
    # Collapse consecutive same-type swings, keep the more extreme one.
    clean: List[Tuple[int, float, str]] = []
    for sw in out:
        if clean and clean[-1][2] == sw[2]:
            if sw[2] == "H" and sw[1] > clean[-1][1]:
                clean[-1] = sw
            elif sw[2] == "L" and sw[1] < clean[-1][1]:
                clean[-1] = sw
        else:
            clean.append(sw)
    return clean


def detect(df: pd.DataFrame, lookback_days: int = 325) -> Optional[dict]:
    # Book p.212: bases form over 3-65 weeks. 65w * 5 trading days = 325 bars.
    # Previous default of 90 missed legitimate long bases.
    """Detect a VCP in the last `lookback_days` bars. Returns None if no
    discernible base is found."""
    if df is None or len(df) < lookback_days + 10:
        return None
    c = df["close"].iloc[-lookback_days:]
    v = df["volume"].iloc[-lookback_days:]

    base_high = float(c.max())
    base_low = float(c.min())
    base_depth_pct = (1 - base_low / base_high) * 100 if base_high else 0

    # Book: avoid corrections >60%; flag deep bases.
    too_deep = base_depth_pct > 60

    swings = _find_swings(c.reset_index(drop=True), window=5)
    if len(swings) < 3:
        return {
            "has_base": False,
            "base_depth_pct": round(base_depth_pct, 2),
            "contractions": [],
            "too_deep": too_deep,
            "reason": "not enough swings",
        }

    # Extract (top, bottom) pairs = contractions.
    contractions: List[dict] = []
    highs = [s for s in swings if s[2] == "H"]
    lows = [s for s in swings if s[2] == "L"]
    # Pair each high with the next low.
    i = j = 0
    while i < len(highs) and j < len(lows):
        h = highs[i]
        # Find first low after this high
        while j < len(lows) and lows[j][0] <= h[0]:
            j += 1
        if j >= len(lows):
            break
        l = lows[j]
        depth = (1 - l[1] / h[1]) * 100
        contractions.append({
            "top_idx": h[0],
            "top_price": round(h[1], 2),
            "bot_idx": l[0],
            "bot_price": round(l[1], 2),
            "depth_pct": round(depth, 2),
        })
        i += 1

    n_contractions = len(contractions)
    if n_contractions == 0:
        return {
            "has_base": False,
            "base_depth_pct": round(base_depth_pct, 2),
            "contractions": [],
            "too_deep": too_deep,
            "reason": "no contractions",
        }

    # Book p.199: each contraction "about half" the previous, ±tolerance.
    # Enforce <= 75% of previous (allows 0.5 ideal, tolerates noisy 0.6-0.7).
    depths = [ct["depth_pct"] for ct in contractions]
    monotonic = all(depths[k] <= depths[k - 1] * 0.75 for k in range(1, len(depths)))

    # Right-side tightness: final contraction depth ≤ 10% = ideal per book
    final_depth = depths[-1]
    tight_right = final_depth <= 10

    # Pivot = most recent swing high (top of final contraction)
    pivot_price = contractions[-1]["top_price"]
    stop_price = contractions[-1]["bot_price"]

    # Pivot quality (cookstock PIVOT_PRICE_PERC=0.20):
    # the pivot must sit at the top of a meaningful prior advance, not just
    # be a noise high. Require ≥20% advance from the lowest low BEFORE the
    # base started, to the pivot price.
    pivot_quality_ok = False
    pivot_prior_advance_pct = None
    pivot_top_idx = contractions[-1]["top_idx"]
    if pivot_top_idx > 10:
        pre_base = c.iloc[: pivot_top_idx]
        if len(pre_base) > 0:
            pre_low = float(pre_base.min())
            if pre_low > 0:
                pivot_prior_advance_pct = round((pivot_price / pre_low - 1) * 100, 2)
                pivot_quality_ok = pivot_prior_advance_pct >= 20

    # Volume drying up in final contraction: compare vol in final contraction
    # window vs avg over base.
    start_bot = contractions[-1]["bot_idx"]
    avg_vol_base = float(v.mean())
    final_vol = float(v.iloc[start_bot:].mean()) if start_bot < len(v) else avg_vol_base
    vol_drying = (final_vol / avg_vol_base) < 0.8 if avg_vol_base > 0 else False

    # Quality flags per book
    good_count = 2 <= n_contractions <= 6
    good_depth = 10 <= base_depth_pct <= 35  # "most constructive setups"

    has_base = (
        n_contractions >= 2
        and monotonic
        and tight_right
        and not too_deep
        and pivot_quality_ok
    )

    return {
        "has_base": has_base,
        "base_depth_pct": round(base_depth_pct, 2),
        "base_high": round(base_high, 2),
        "base_low": round(base_low, 2),
        "n_contractions": n_contractions,
        "contractions": contractions,
        "monotonic_shrinkage": monotonic,
        "final_contraction_pct": round(final_depth, 2),
        "tight_right_side": tight_right,
        "volume_drying": vol_drying,
        "too_deep": too_deep,
        "good_contraction_count": good_count,
        "ideal_depth_range": good_depth,
        "pivot_buy_price": pivot_price,
        "suggested_stop": stop_price,
        "pivot_quality_ok": pivot_quality_ok,
        "pivot_prior_advance_pct": pivot_prior_advance_pct,
    }
