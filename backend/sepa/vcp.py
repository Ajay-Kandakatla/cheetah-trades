"""VCP — Volatility Contraction Pattern detector.

Book Ch 10 (p.198-213):
  - Base forms over ~3 to 60 weeks after a Stage 2 advance (p.197). The 325-bar
    (≈65-week) lookback below is the SEARCH window — the 60-week max base plus a
    buffer — NOT the base length itself.
  - 2 to 6 successive contractions ("Ts"), each ~half the previous.
  - Ideal correction 25-35%; >50% is "generally too much" (p.186). (The code's
    too_deep cutoff is a tighter 40% — see vcp_methodology.md / SEPA_CONTRACTS §7.)
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


def _tightness_score(base, final_depth, base_depth_pct, vol_drying,
                     n_contractions, pivot_price, last_close):
    """0-100 VCP quality / tightness — how textbook the contraction footprint is.

    Aggregates the detector's book-grounded components (Minervini pp.198-205):
    end-to-end tightening, right-side handle tightness, volume dry-up, constructive
    depth + contraction count, and proximity to the pivot. Each PIECE is from the
    book; the WEIGHTING (35/25/20/10/10) is OURS — a presentation heuristic, not a
    Minervini formula. Banded: ≥70 tight (well-formed) · 40-69 developing · <40 early.
    Returns (score, band, drivers) or (None, None, []) when there's no contraction
    sequence to grade."""
    if not base or n_contractions < 2:
        return None, None, []
    depths = [c["depth_pct"] for c in base]
    first, last = depths[0], depths[-1]
    score = 0.0
    drivers: list = []

    # 1) End-to-end tightening — the heart of a VCP (p.199). 35 pts.
    #    ratio 1.0 (no tightening) → 0; ratio ≤ 0.25 (≥4× tighter) → full.
    if first > 0:
        ratio = last / first
        score += 35 * max(0.0, min(1.0, (1.0 - ratio) / 0.75))
        if ratio <= 0.45:
            drivers.append(f"tightens {first:.0f}%→{last:.0f}%")

    # 2) Right-side tightness — the handle (pp.198, 202). 25 pts. ≤4% → full, ≥12% → 0.
    score += 25 * max(0.0, min(1.0, (12.0 - final_depth) / 8.0))
    if final_depth <= 6:
        drivers.append(f"{final_depth:.0f}% handle")

    # 3) Volume drying up (p.205). 20 pts.
    if vol_drying:
        score += 20
        drivers.append("volume drying up")

    # 4) Constructive depth + contraction count (pp.198-199). 10 pts.
    if 8 <= base_depth_pct <= 35:
        score += 6
    if 2 <= n_contractions <= 6:
        score += 4
        drivers.append(f"{n_contractions} contractions")

    # 5) Proximity to the pivot — ready when it's at the line (p.203). 10 pts.
    if pivot_price and last_close:
        above = (pivot_price / last_close - 1) * 100   # +ve = pivot still above price
        if -1 <= above <= 4:
            score += 10
            drivers.append("at the pivot")
        elif above <= 8:
            score += 5

    s = int(round(min(100.0, score)))
    band = "tight" if s >= 70 else "developing" if s >= 40 else "early"
    return s, band, drivers[:3]


def detect(df: pd.DataFrame, lookback_days: int = 325) -> Optional[dict]:
    # Book p.197: bases form over ~3 to 60 weeks. The 325-bar default is the
    # SEARCH horizon (60-week max base + buffer ≈ 65 weeks), NOT the base length.
    # Previous default of 90 missed legitimate long bases.
    """Detect a VCP in the last `lookback_days` bars. Returns None if no
    discernible base is found."""
    if df is None or len(df) < lookback_days + 10:
        return None
    c = df["close"].iloc[-lookback_days:]
    v = df["volume"].iloc[-lookback_days:]
    cr = c.reset_index(drop=True)
    vr = v.reset_index(drop=True)

    _empty = {
        "has_base": False, "base_depth_pct": None, "contractions": [],
        "n_contractions": 0, "too_deep": False, "volume_drying": False,
        "good_contraction_count": False, "ideal_depth_range": False,
        "pivot_buy_price": None, "suggested_stop": None,
        "tightness": None, "tightness_band": None, "tightness_drivers": [],
    }

    swings = _find_swings(cr, window=5)
    if len(swings) < 3:
        return {**_empty, "reason": "not enough swings"}

    # Pair each swing high with the next swing low → contractions (left→right).
    contractions: List[dict] = []
    highs = [s for s in swings if s[2] == "H"]
    lows = [s for s in swings if s[2] == "L"]
    i = j = 0
    while i < len(highs) and j < len(lows):
        h = highs[i]
        while j < len(lows) and lows[j][0] <= h[0]:
            j += 1
        if j >= len(lows):
            break
        l = lows[j]
        depth = (1 - l[1] / h[1]) * 100
        contractions.append({
            "top_idx": h[0], "top_price": round(h[1], 2),
            "bot_idx": l[0], "bot_price": round(l[1], 2),
            "depth_pct": round(depth, 2),
        })
        i += 1

    if not contractions:
        return {**_empty, "reason": "no contractions"}

    # ── Isolate the RECENT base (BUGFIX 2026-06-01) ────────────────────────
    # The old code measured base depth as high-to-low across the ENTIRE 325-bar
    # (16-month) window, so every momentum leader read as a 60-94% "base" and
    # failed `too_deep` — zero VCPs ever fired. A VCP base is the most recent
    # CONTRACTING consolidation, not the whole prior advance. Book p.205: "the
    # contractions will be smaller from left to right as supply is absorbed."
    # So take the maximal suffix of contractions whose depths are (weakly)
    # decreasing left→right — that IS the volatility-contraction footprint —
    # and measure everything within it.
    depths_all = [ct["depth_pct"] for ct in contractions]
    m = len(depths_all) - 1
    while m > 0 and depths_all[m - 1] >= depths_all[m]:
        m -= 1
    base = contractions[m:]
    n_contractions = len(base)
    depths = [ct["depth_pct"] for ct in base]

    base_start_idx = base[0]["top_idx"]
    base_high = base[0]["top_price"]
    base_low = min(ct["bot_price"] for ct in base)
    base_depth_pct = (1 - base_low / base_high) * 100 if base_high else 0.0

    # Book pp.197-200: a proper base corrects the LEAST; the worked VCP first
    # contraction is ~25% (flat base 10-15%). >40% from the base high is a deep,
    # failure-prone correction, not a VCP.
    too_deep = base_depth_pct > 40

    # Book p.199: each contraction "about half (plus or minus a reasonable
    # amount) of the previous" (25→15→8 or 25→10→5). Enforce as an END-TO-END
    # tightening (final ≤ ~half the first) — robust to noise, where the old
    # every-step ≤0.65 over-tightened and rejected real bases.
    monotonic = all(depths[k] <= depths[k - 1] for k in range(1, len(depths)))  # smaller L→R
    meaningful_tightening = len(depths) >= 2 and depths[-1] <= depths[0] * 0.6

    # Right-side tightness: book final contraction ~5-8% (handle ~5%). ≤12% is a
    # lenient ceiling that still demands a tight pivot area.
    final_depth = depths[-1]
    tight_right = final_depth <= 12

    pivot_price = base[-1]["top_price"]
    stop_price = base[-1]["bot_price"]

    # Pivot quality: a base forms AFTER an advance (p.197). Require ≥20% run from
    # the pre-base low to the base's left-side high.
    pivot_quality_ok = False
    pivot_prior_advance_pct = None
    if base_start_idx > 10:
        pre_base = cr.iloc[:base_start_idx]
        if len(pre_base) > 0:
            pre_low = float(pre_base.min())
            if pre_low > 0:
                pivot_prior_advance_pct = round((base_high / pre_low - 1) * 100, 2)
                pivot_quality_ok = pivot_prior_advance_pct >= 20

    # Volume drying in the base vs the run into it (p.205: volume contracts as
    # supply is absorbed).
    avg_vol_base = float(vr.iloc[base_start_idx:].mean()) if base_start_idx < len(vr) else float(vr.mean())
    final_bot = base[-1]["bot_idx"]
    final_vol = float(vr.iloc[final_bot:].mean()) if final_bot < len(vr) else avg_vol_base
    vol_drying = (final_vol / avg_vol_base) < 0.8 if avg_vol_base > 0 else False

    good_count = 2 <= n_contractions <= 6          # book p.199: "two to four ... five or six"
    good_depth = 8 <= base_depth_pct <= 35
    # A real contraction needs a real pullback to contract from; a sub-handle
    # (~5%, p.198) total range is a flat line / low-vol drift, not a VCP base.
    deep_enough = base_depth_pct >= 5

    has_base = (
        n_contractions >= 2
        and meaningful_tightening
        and deep_enough
        and not too_deep
        and tight_right
        and pivot_quality_ok
    )

    tightness, tightness_band, tightness_drivers = _tightness_score(
        base, final_depth, base_depth_pct, vol_drying, n_contractions,
        pivot_price, float(cr.iloc[-1]),
    )

    return {
        "has_base": has_base,
        "base_depth_pct": round(base_depth_pct, 2),
        "base_high": round(base_high, 2),
        "base_low": round(base_low, 2),
        "base_bars": int(len(cr) - base_start_idx),
        "n_contractions": n_contractions,
        "contractions": base,
        "monotonic_shrinkage": monotonic,
        "final_vs_first_ok": meaningful_tightening,
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
        "tightness": tightness,                 # 0-100 VCP quality (None if <2 contractions)
        "tightness_band": tightness_band,        # tight | developing | early
        "tightness_drivers": tightness_drivers,  # short human reasons
    }
