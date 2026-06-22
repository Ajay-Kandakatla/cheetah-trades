"""SEPA conviction rank — behavioral + negative + locked weights (2026-06-22).

The conviction rank (sepa.conviction) orders the SEPA page / Leaderboard /
Breakouts board by "most return potential" from the three signals Ajay named —
volume, dried volume, momentum — gated to Minervini's book:

  * MOMENTUM-LED: the dominant leg is relative-strength leadership (TLSW p.34
    SEPA ranking, p.79 RS ≥70/80s-90s). A tight VCP with volume dry-up + clean
    accumulation are the entry-quality boosters, NOT the primary ranker.
  * A climax-top distribution / MVP exhaustion is a SELL, never a buy
    (TTLAC pp.186-188 / §9 p.199) — its conviction is crushed to the bottom.
"""
from sepa import conviction


def _leader(**over):
    row = {
        "rs_rank": 95,
        "dual_momentum": {"abs_mom_pass": True, "beats_spy": True},
        "vcp": {"has_base": True, "tightness": 82},
        "volume": {"vol_dryup": 0.5, "accumulation_strength": "strong",
                   "cmf_signal": "inflow", "up_down_vol_ratio": 1.8,
                   "high_vol_breakout": True},
        "risk_to_stop_pct": 4.5,
        "ext_from_pivot_pct": 1.0,
    }
    row.update(over)
    return row


# ── weights locked (source-guard, Rule #4) ──────────────────────────────────
def test_conviction_weights_locked():
    assert conviction.CONVICTION_WEIGHTS == {
        "momentum": 0.35, "coil": 0.30, "demand": 0.25, "reward_risk": 0.10,
    }


def test_conviction_weights_sum_to_one():
    assert round(sum(conviction.CONVICTION_WEIGHTS.values()), 9) == 1.0


def test_momentum_is_the_heaviest_leg():
    """Book ranking is momentum/leadership-led (TLSW p.34/79) — momentum must be
    the single heaviest weight, ahead of coil and demand."""
    w = conviction.CONVICTION_WEIGHTS
    assert w["momentum"] == max(w.values())
    assert w["momentum"] > w["coil"] > w["demand"] > w["reward_risk"]


# ── behavioral ──────────────────────────────────────────────────────────────
def test_leader_outranks_laggard():
    """A high-RS, tight-VCP, dried-volume, accumulating leader scores well above a
    low-RS, no-base, no-dry-up, extended laggard."""
    leader = _leader()
    laggard = {
        "rs_rank": 45,
        "dual_momentum": {"abs_mom_pass": True, "beats_spy": False},
        "vcp": {"has_base": False, "tightness": 10},
        "volume": {"vol_dryup": 1.1, "accumulation_strength": "neutral",
                   "cmf_signal": "neutral", "up_down_vol_ratio": 1.0},
        "risk_to_stop_pct": 15.0, "ext_from_pivot_pct": 6.0,
    }
    assert conviction.score(leader)["conviction"] > conviction.score(laggard)["conviction"]


def test_legs_and_lead_reported():
    c = conviction.score(_leader())
    assert set(c["legs"]) == {"momentum", "coil", "demand", "reward_risk"}
    assert c["lead"] in c["legs"]
    assert 0 <= c["conviction"] <= 100


def test_volume_dryup_lifts_coil():
    """The 'dried volume' signal: drier volume (lower vol_dryup) lifts the coil leg
    (TLSW p.203/226 — volume below the 50-day avg as supply is absorbed)."""
    dry = conviction.score(_leader(volume={"vol_dryup": 0.45, "accumulation_strength": "strong",
                                           "cmf_signal": "inflow", "up_down_vol_ratio": 1.8,
                                           "high_vol_breakout": True}))
    wet = conviction.score(_leader(volume={"vol_dryup": 1.0, "accumulation_strength": "strong",
                                           "cmf_signal": "inflow", "up_down_vol_ratio": 1.8,
                                           "high_vol_breakout": True}))
    assert dry["legs"]["coil"] > wet["legs"]["coil"]


def test_extended_erodes_reward_risk():
    """Chasing a breakout past the 3% cap erodes the reward:risk leg (TLSW p.224)."""
    near = conviction.score(_leader(ext_from_pivot_pct=1.0))
    chased = conviction.score(_leader(ext_from_pivot_pct=8.0))
    assert near["legs"]["reward_risk"] > chased["legs"]["reward_risk"]


# ── negative / suppression (the AMAT case) ──────────────────────────────────
def test_climax_distribution_suppressed_below_a_plain_laggard():
    """REGRESSION (AMAT-class): a climax-top distribution name keeps a high RS but
    is a SELL — its conviction must be crushed below even a mediocre clean name,
    so it can never sit near the top of a 'most return' list (TTLAC pp.186-188)."""
    climax = _leader(climax_distribution={"is_distribution": True}, distribution_selling=True,
                     distribution_reason="climax-top distribution")
    plain = {
        "rs_rank": 55, "dual_momentum": {"abs_mom_pass": True, "beats_spy": False},
        "vcp": {"has_base": True, "tightness": 30},
        "volume": {"vol_dryup": 0.8, "accumulation_strength": "neutral",
                   "cmf_signal": "neutral", "up_down_vol_ratio": 1.1},
        "risk_to_stop_pct": 9.0, "ext_from_pivot_pct": 2.0,
    }
    cx = conviction.score(climax)
    assert cx["suppressed"] is True
    assert cx["suppress_reason"]
    assert cx["conviction"] < conviction.score(plain)["conviction"]


def test_mvp_exhaustion_suppressed():
    """A late-stage MVP exhaustion (TTLAC §9 p.199) is also a sell — suppressed."""
    c = conviction.score(_leader(mvp_exhaustion=True))
    assert c["suppressed"] is True
    assert c["conviction"] < conviction.score(_leader())["conviction"]


def test_handles_empty_row():
    """Never raises on a sparse row (older cached blob) — returns the schema."""
    c = conviction.score({})
    assert 0 <= c["conviction"] <= 100
    assert set(c["legs"]) == {"momentum", "coil", "demand", "reward_risk"}
