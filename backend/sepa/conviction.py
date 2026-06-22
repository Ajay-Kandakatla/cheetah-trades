"""SEPA conviction rank — "which buyable name has the most return potential."

Ajay 2026-06-22: rank the lists by a single book-faithful number built from the
three signals he named — **volume, dried volume, and momentum** — so the names
closest to Minervini's highest-expectancy launchpad float to the top of the SEPA
page, the Leaderboard and the Breakouts board.

This is a CONVICTION / reward-to-risk rank, NOT a predicted % return. Minervini
gives leading indicators of explosive moves, not a return forecast, so we rank by
how closely a setup matches the book's ideal — and surface the sub-scores so the
"why" is visible — rather than inventing a fake percentage.

Derivation straight from the books (cited; no training/internet, Rule #1):

  MOMENTUM / LEADERSHIP  (weight 35) — the dominant ranking factor.
    The SEPA ranking process itself ranks on relative strength + the Leadership
    Profile (TLSW p.34). The Trend Template wants RS ≥70, "preferably in the 80s
    or 90s, which will generally be the case with the better selections"
    (TLSW p.79). Leaders "power up the most percentagewise" and make new highs
    first (TLSW p.96); the top RS leaders "show the greatest appreciation"
    (p.111); the whole of Ch.9 is "Follow the Leaders" (p.161-165). Antonacci's
    absolute-momentum gate (12m > 0) and the beats-SPY winner filter confirm the
    name is in a real uptrend, not a dead-cat.

  COIL / VOLUME DRY-UP  (weight 30) — the entry-timing / risk quality.
    VCP's "main role … is establishing a precise entry point at the line of least
    resistance" (TLSW p.198). The pivot must form on a SIGNIFICANT volume
    contraction — volume drying "at or near the lowest levels" of the base, below
    the 50-day average (TLSW p.203, p.226), proving supply has stopped (p.206,
    "be the last weak holder"). The tighter the coil + the drier the volume, the
    more explosive and lower-risk the move. This is a setup-quality multiplier on
    the leader, NOT the primary ranker (a pure coil-led sort would be backwards).

  DEMAND / VOLUME CONFIRMATION  (weight 25) — are institutions actually buying.
    A breakout must be volume-confirmed (TLSW p.203). Accumulation strength,
    Chaikin money-flow inflow, the up/down volume ratio and a pocket-pivot /
    high-volume breakout footprint say big money is stepping in now.

  REWARD : RISK  (weight 10) — buy near the pivot with a tight stop.
    "Buy as close to the pivot … as possible without chasing … more than a few
    percentage points" (TLSW p.224). A tight stop and an in-zone entry give the
    biggest return PER UNIT OF RISK; chasing an extended breakout erodes it.

SUPPRESSION (the AMAT case). A climax-top distribution (TTLAC pp.186-188) or a
late-stage MVP exhaustion (TTLAC §9 p.199) is a SELL signal, not a buy — the book
says to "sell aggressively into strength," not initiate. Such a name can score a
high RS and still be the worst thing to buy, so its conviction is crushed to the
bottom regardless of its raw legs. This keeps the rank in lock-step with the
is_buyable gate and the (now climax-aware) ENTER verdict.

Pure read of fields the scanner already computes — no new market math here.
"""
from __future__ import annotations

from typing import Optional

# Locked weights (source-guarded in tests/test_sepa_contracts.py). Momentum-led
# per the book's SEPA ranking (TLSW p.34/p.79); coil + demand are the entry
# quality; reward:risk is the closer (Ajay 2026-06-22).
CONVICTION_WEIGHTS = {
    "momentum":    0.35,
    "coil":        0.30,
    "demand":      0.25,
    "reward_risk": 0.10,
}

# A distributing climax / exhaustion is a sell, never a buy — sink it hard so it
# can never sit near the top of a "most return" list (TTLAC pp.186-188 / §9 p.199).
SUPPRESS_MULT = 0.15

# Accumulation-strength → demand base points.
_ACCUM_POINTS = {"strong": 85.0, "accumulating": 65.0, "neutral": 40.0, "distributing": 5.0}


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _ext_cap() -> float:
    """scanner.BUYABLE_MAX_EXT_PCT, imported lazily to avoid a circular import
    (scanner imports this module)."""
    try:
        from . import scanner
        return float(scanner.BUYABLE_MAX_EXT_PCT)
    except Exception:
        return 3.0


def _momentum_leg(row: dict) -> float:
    """Leadership / relative strength (TLSW p.34, p.79, p.96, p.111, Ch.9)."""
    rs = row.get("rs_rank")
    mom = float(rs) if rs is not None else 0.0          # 0-99 RS percentile
    dm = row.get("dual_momentum") or {}
    # Antonacci absolute-momentum gate: 12m return ≤ 0 means it is NOT a leader in
    # a real uptrend — halve the leg (explicitly False; None = unknown, leave it).
    if dm.get("abs_mom_pass") is False:
        mom *= 0.5
    if dm.get("beats_spy"):                              # winner filter
        mom += 5.0
    return _clamp(mom)


def _coil_leg(row: dict) -> float:
    """VCP tightness + volume dry-up (TLSW p.198, p.203, p.206, p.226)."""
    vcp = row.get("vcp") or {}
    vol = row.get("volume") or {}
    tight = float(vcp.get("tightness") or 0.0)           # 0-100 VCP quality
    vd = vol.get("vol_dryup")                             # 10d avg ÷ 50d avg
    if vd is None:
        dry = 0.0
    else:
        # Below the 50-day average = supply absorbed (p.203/226). 0.5 → full
        # credit, 1.0 (no contraction) → none.
        dry = _clamp((1.0 - float(vd)) / 0.5 * 100.0)
    coil = 0.6 * tight + 0.4 * dry
    if not vcp.get("has_base"):                           # no clean base = weaker coil
        coil *= 0.6
    return _clamp(coil)


def _demand_leg(row: dict) -> float:
    """Volume confirmation / accumulation (TLSW p.203; CMF inflow; pocket pivot)."""
    vol = row.get("volume") or {}
    dem = _ACCUM_POINTS.get(vol.get("accumulation_strength"), 40.0)
    sig = vol.get("cmf_signal")
    if sig == "inflow":
        dem += 10.0
    elif sig == "outflow":
        dem -= 25.0
    udvr = vol.get("up_down_vol_ratio")
    if udvr is not None:
        if udvr >= 1.5:
            dem += 8.0
        elif udvr >= 1.3:
            dem += 4.0
    if vol.get("high_vol_breakout") or vol.get("pocket_pivot"):
        dem += 7.0
    return _clamp(dem)


def _reward_risk_leg(row: dict) -> float:
    """Stop tightness + pivot proximity (TLSW p.224)."""
    rtp = row.get("risk_to_stop_pct")
    if rtp is None:
        rr = 50.0
    elif rtp <= 5:
        rr = 100.0
    elif rtp <= 8:
        rr = 80.0
    elif rtp <= 12:
        rr = 55.0
    elif rtp <= 18:
        rr = 30.0
    else:
        rr = 10.0
    ext = row.get("ext_from_pivot_pct")
    if ext is not None and ext > _ext_cap():             # chasing erodes reward:risk
        rr *= 0.5
    return _clamp(rr)


def _suppress_reason(row: dict) -> Optional[str]:
    if (row.get("climax_distribution") or {}).get("is_distribution"):
        return "climax-top distribution — sell into strength, not buy (TTLAC p.186-188)"
    if row.get("distribution_selling"):
        return row.get("distribution_reason") or "institutional distribution into the breakout"
    if row.get("mvp_exhaustion"):
        return "late-stage MVP exhaustion — a sell signal (TTLAC §9 p.199)"
    return None


def score(row: dict) -> dict:
    """Conviction blob for one scan row. Always returns the full schema.

    Returns ``{"conviction": float 0-100, "legs": {...}, "suppressed": bool,
    "suppress_reason": str|None, "lead": str, "weights": {...}}``.
    """
    legs = {
        "momentum":    round(_momentum_leg(row), 1),
        "coil":        round(_coil_leg(row), 1),
        "demand":      round(_demand_leg(row), 1),
        "reward_risk": round(_reward_risk_leg(row), 1),
    }
    raw = sum(legs[k] * CONVICTION_WEIGHTS[k] for k in CONVICTION_WEIGHTS)

    reason = _suppress_reason(row)
    suppressed = reason is not None
    conviction = raw * SUPPRESS_MULT if suppressed else raw

    # Which leg is carrying the rank (for the FE "why ranked here" tooltip).
    lead = max(legs, key=lambda k: legs[k])

    return {
        "conviction":      round(_clamp(conviction), 1),
        "legs":            legs,
        "suppressed":      suppressed,
        "suppress_reason": reason,
        "lead":            lead,
        "weights":         dict(CONVICTION_WEIGHTS),
    }
