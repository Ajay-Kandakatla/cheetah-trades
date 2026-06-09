"""Earnings-Quality score — Minervini, *Trade Like a Stock Market Wizard* (2013),
Chapter 8 "Assessing Earnings Quality" (book pp. 140-159).

The chapter's thesis (p.141): high-quality earnings are **revenue-driven**.
Earnings from cost-cutting, plant closures, or one-time gains "walk on short
legs" — "sustainable earnings growth requires revenue growth." This module turns
the chapter's quantifiable rules into a 0-100 earnings-quality score + flags,
computed from the newest-first quarterly series canslim already fetches from
Massive (EPS, revenue, net income, inventory) — no extra API call.

What it encodes (every rule page-cited):
  * EPS acceleration ............... growth RATE rising across quarters (p.140,158)
  * Sales acceleration ............. reuses sepa/sales.py (Bonde)        (p.140,158)
  * Margin expansion ............... net-profit-margin trend             (p.145-147)
  * The Code 33 .................... EPS + sales + margins all accelerating
                                     3 consecutive quarters (the headline) (p.158-159)
  * Sales-driven quality penalty ... EPS jumps with flat sales & no margin
                                     expansion = low-quality beat        (p.141-144)
  * Inventory red flag ............. inventory growing much faster than
                                     sales (product piling up)           (p.153-155)

HONEST DATA LIMITS (Rule #1 — no invented precision; see methodology doc):
  * Massive's standardized balance sheet exposes TOTAL inventory only — NOT the
    finished-goods/WIP/raw split Minervini uses in Fig 8.9. We compare total
    inventory vs sales, which captures his aggregate signal, not the sub-breakdown.
  * Accounts receivable is NOT on Massive — the receivables half of "double
    trouble" (p.156-157) arrives via a yfinance supplement (top-N enrich only),
    passed in as ``recv_q_series``. Absent here, the receivables flag is None.

All thresholds marked "(codification)" are OURS — Minervini gives the concept and
direction but not an exact cutoff. They are locked in test_sepa_contracts.py.
"""
from __future__ import annotations

from typing import List, Optional

from sepa import sales

# ── Codified thresholds (Minervini gives direction, not exact numbers) ────────
# Locked in test_sepa_contracts.py. "(p.X)" notes the rule each anchors to.
STRONG_EPS_YOY_PCT = 25.0      # top of Minervini's "20 to 25 percent" Q-EPS minimum (book p.127; p.140 bullets "accelerating EPS" but states no number)
SALES_FLOOR_PCT = 5.0          # Bonde floor reused for "sales-backed" (p.141)
MARGIN_FLAT_BAND_PCT = 0.5     # |Δ net margin| <= this (pp) reads as "flat"
INV_OVER_SALES_GAP_PCT = 15.0  # CODIFICATION of book p.156 "twice or more": the book
#   states the red flag MULTIPLICATIVELY (inv/recv growing ≥ ~2× sales). We approximate
#   it as an ADDITIVE +15pp gap (inv YoY > sales YoY + 15). Owned deviation — a future
#   pass could switch to the literal ratio test. See SEPA_CONTRACTS.md §4.
INV_REDFLAG_ABS_FLOOR_PCT = 10.0  # CODIFICATION, NOT a book number: book p.155 says the
#   absolute inventory level "is not that meaningful" — this floor only suppresses the
#   flag on tiny-denominator noise (inv/recv YoY ≤ 10%). Owned deviation, locked below.
INV_REDFLAG_SALES_STRONG_PCT = 25.0  # p.156: inventory build WITH strong sales is
#   demand-anticipation, NOT piling up. Suppress the flag above this sales YoY.
LOWQ_EPS_MIN_PCT = 25.0        # "EPS jumped" leg of a low-quality beat (p.143)
LOWQ_SALES_MAX_PCT = 5.0       # "...on ~flat sales" leg (p.143)


def _yoy(series: List[Optional[float]], i: int) -> Optional[float]:
    """YoY % growth for newest-first quarter index ``i``: series[i] vs
    series[i+4] (same quarter a year earlier). None if either side is missing or
    the base is zero. Matches canslim._compute_q_eps_growth / sepa.sales._yoy."""
    if series is None or len(series) <= i + 4:
        return None
    a, b = series[i], series[i + 4]
    if a is None or b is None or b == 0:
        return None
    return (a - b) / abs(b) * 100.0


def _npm(ni: List[Optional[float]], rev: List[Optional[float]], i: int) -> Optional[float]:
    """Net profit margin (%) for quarter index ``i`` = net_income / revenue."""
    if ni is None or rev is None or i >= len(ni) or i >= len(rev):
        return None
    n, r = ni[i], rev[i]
    if n is None or r is None or r == 0:
        return None
    return n / r * 100.0


def _strictly_rising(vals: List[Optional[float]], require_positive_latest: bool = False) -> bool:
    """True iff every value is present and vals[0] > vals[1] > ... (newest-first,
    so the most recent is the largest = accelerating)."""
    if any(v is None for v in vals) or len(vals) < 2:
        return False
    if require_positive_latest and vals[0] <= 0:
        return False
    return all(vals[k] > vals[k + 1] for k in range(len(vals) - 1))


def compute(
    eps_q_series: List[Optional[float]],
    rev_q_series: List[Optional[float]],
    ni_q_series: List[Optional[float]],
    inv_q_series: Optional[List[Optional[float]]] = None,
    recv_q_series: Optional[List[Optional[float]]] = None,
    surprise_pct: Optional[float] = None,
) -> dict:
    """Compute the Chapter-8 earnings-quality verdict from newest-first quarterly
    series. Returns a dict with ``score`` (0-100 or None when history is too
    thin), ``code_33`` (bool), ``tier``, ``reason``, ``components`` and
    ``red_flags``. Pure — no network, no I/O.
    """
    eps = list(eps_q_series or [])
    rev = list(rev_q_series or [])
    ni = list(ni_q_series or [])
    inv = list(inv_q_series or []) if inv_q_series else []
    recv = list(recv_q_series or []) if recv_q_series else []

    # YoY growth sequences (newest-first): index 0 is the latest quarter.
    eps_g = [_yoy(eps, i) for i in range(3)]   # needs eps[0..6]
    rev_g = [_yoy(rev, i) for i in range(3)]
    npm = [_npm(ni, rev, i) for i in range(3)]
    npm_yoy_now = _npm(ni, rev, 0)
    npm_yoy_prior = _npm(ni, rev, 4)

    # Not enough history for even one YoY read -> unscored (mirrors sales.py).
    if eps_g[0] is None and rev_g[0] is None:
        return {
            "score": None, "code_33": False, "tier": "unknown",
            "reason": "insufficient financial history (need >= 5 quarters)",
            "components": {}, "red_flags": {},
            "_insufficient": True,
        }

    # ── Sales acceleration — reuse the Bonde-anchored Sales Confidence score ──
    sales_info = sales.compute(rev, eps_g[0])
    sales_score = sales_info.get("score")
    rev_accelerating = bool(sales_info.get("accelerating"))

    # ── EPS acceleration (p.140,158) ─────────────────────────────────────────
    eps_accel_2q = bool(eps_g[0] is not None and eps_g[1] is not None
                        and eps_g[0] > eps_g[1] and eps_g[0] > 0)
    eps_accel_3q = _strictly_rising(eps_g, require_positive_latest=True)

    # ── Margin expansion (p.145-147) ─────────────────────────────────────────
    # YoY net-margin expansion (seasonality-robust) + sequential 3q rise.
    npm_expanding_yoy = bool(npm_yoy_now is not None and npm_yoy_prior is not None
                             and npm_yoy_now > npm_yoy_prior + MARGIN_FLAT_BAND_PCT)
    npm_contracting_yoy = bool(npm_yoy_now is not None and npm_yoy_prior is not None
                               and npm_yoy_now < npm_yoy_prior - MARGIN_FLAT_BAND_PCT)
    npm_seq_rising = _strictly_rising(npm)

    # ── The Code 33 (p.158-159) — EPS + sales + margins all accelerating for ──
    # three consecutive quarters. The chapter's headline rule.
    rev_accel_3q = _strictly_rising(rev_g, require_positive_latest=True)
    code_33 = bool(eps_accel_3q and rev_accel_3q and npm_seq_rising)

    # ── Sales-driven quality (p.141-144) ─────────────────────────────────────
    # Low-quality beat: EPS jumps while sales are ~flat and margins aren't
    # expanding -> earnings probably came from cost-cuts/one-times, not revenue.
    low_quality_beat = bool(
        eps_g[0] is not None and rev_g[0] is not None
        and eps_g[0] >= LOWQ_EPS_MIN_PCT
        and rev_g[0] < LOWQ_SALES_MAX_PCT
        and not npm_expanding_yoy
    )
    sales_backed = bool(rev_g[0] is not None and rev_g[0] >= SALES_FLOOR_PCT
                        and eps_g[0] is not None and eps_g[0] > 0)

    # ── Inventory red flag (p.153-155) ───────────────────────────────────────
    # Fires when inventory grows much faster than sales — UNLESS sales are
    # themselves strong, in which case the build is demand-anticipation, not
    # product piling up (p.156: "raw materials building up ... sales should show
    # signs of acceleration shortly afterward to confirm").
    inv_g0 = _yoy(inv, 0) if inv else None
    sales_strong = bool(rev_g[0] is not None and rev_g[0] >= INV_REDFLAG_SALES_STRONG_PCT)
    inventory_redflag = bool(
        inv_g0 is not None and rev_g[0] is not None
        and inv_g0 > rev_g[0] + INV_OVER_SALES_GAP_PCT
        and inv_g0 > INV_REDFLAG_ABS_FLOOR_PCT
        and not sales_strong
    )
    # Receivables red flag (p.156-157) — only when the yfinance supplement is
    # provided (top-N enrich). "Double trouble" = inventory AND receivables both
    # outrunning sales (p.157).
    recv_g0 = _yoy(recv, 0) if recv else None
    receivables_redflag = (
        bool(recv_g0 is not None and rev_g[0] is not None
             and recv_g0 > rev_g[0] + INV_OVER_SALES_GAP_PCT and recv_g0 > INV_REDFLAG_ABS_FLOOR_PCT)
        if recv else None
    )
    double_trouble = bool(inventory_redflag and receivables_redflag)

    # ── Assemble the 0-100 score ─────────────────────────────────────────────
    # Positive: sales-backed growth + margin expansion + acceleration (Code 33).
    # Negative: low-quality beat + balance-sheet red flags.
    eps_level_pts = _clamp((eps_g[0] or 0.0) / STRONG_EPS_YOY_PCT, 0.0, 1.0) * 20.0
    sales_pts = (sales_score / 100.0 * 20.0) if sales_score is not None else 0.0
    if npm_expanding_yoy:
        margin_pts = 15.0
    elif npm_contracting_yoy:
        margin_pts = 0.0
    else:
        margin_pts = 7.0   # flat / unknown
    eps_accel_pts = 12.0 if eps_accel_3q else (6.0 if eps_accel_2q else 0.0)
    rev_accel_pts = 12.0 if rev_accel_3q else (6.0 if rev_accelerating else 0.0)
    margin_accel_pts = 11.0 if npm_seq_rising else 0.0
    surprise_pts = _clamp((surprise_pct or 0.0), 0.0, 10.0) if surprise_pct else 0.0

    quality_penalty = 25.0 if low_quality_beat else 0.0
    inv_penalty = (20.0 if double_trouble else (10.0 if inventory_redflag else 0.0))

    raw = (eps_level_pts + sales_pts + margin_pts
           + eps_accel_pts + rev_accel_pts + margin_accel_pts + surprise_pts
           - quality_penalty - inv_penalty)
    score = int(round(_clamp(raw, 0.0, 100.0)))

    # ── Tier + human reason (for the card chip) ──────────────────────────────
    if code_33:
        tier, reason = "code33", "Code 33 — EPS, sales & margins accelerating 3 quarters (p.158)"
    elif double_trouble:
        tier, reason = "red_flag", "Inventory AND receivables outrunning sales — 'double trouble' (p.157)"
    elif low_quality_beat:
        tier, reason = "red_flag", "EPS jump on flat sales & no margin expansion — low-quality beat (p.143)"
    elif inventory_redflag:
        tier, reason = "red_flag", "Inventory growing much faster than sales (p.155)"
    elif (eps_accel_2q or rev_accelerating) and not npm_contracting_yoy:
        tier, reason = "accelerating", "Earnings/sales accelerating with stable-or-rising margins (p.140)"
    elif score >= 55:
        tier, reason = "steady", "Sales-backed earnings, no acceleration or red flags"
    else:
        tier, reason = "weak", "Earnings growth weak or not sales-driven (p.141)"

    return {
        "score": score,
        "code_33": code_33,
        "tier": tier,
        "reason": reason,
        "components": {
            "eps_growth_yoy_pct":   _round(eps_g[0]),
            "eps_prior_yoy_pct":    _round(eps_g[1]),
            "eps_accelerating":     eps_accel_2q,
            "eps_accelerating_3q":  eps_accel_3q,
            "rev_growth_yoy_pct":   _round(rev_g[0]),
            "rev_accelerating":     rev_accelerating,
            "rev_accelerating_3q":  rev_accel_3q,
            "npm_latest_pct":       _round(npm_yoy_now),
            "npm_prior_year_pct":   _round(npm_yoy_prior),
            "npm_expanding":        npm_expanding_yoy,
            "npm_seq_rising_3q":    npm_seq_rising,
            "sales_score":          sales_score,
            "sales_backed":         sales_backed,
        },
        "red_flags": {
            "low_quality_beat":     low_quality_beat,
            "inventory_vs_sales":   inventory_redflag,
            "inv_growth_yoy_pct":   _round(inv_g0),
            "receivables_vs_sales": receivables_redflag,   # None when no yfinance supplement
            "recv_growth_yoy_pct":  _round(recv_g0),
            "double_trouble":       double_trouble,
        },
        "_insufficient": False,
    }


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _round(x: Optional[float], n: int = 1) -> Optional[float]:
    return round(x, n) if x is not None else None
