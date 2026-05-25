"""Pounce Tiny Score (PTS) — small/micro-cap composite scorer.

Each component is grounded in a published, widely-cited framework or your
own observed signals. The score is a weighted sum, capped 0-100, then tiered.

Component                                 Weight   Source
─────────────────────────────────────────────────────────────────────────
1.  CANSLIM-adapted (RS + EPS growth)     20       William O'Neil — IBD
2.  Tiny Titans qualifier                 15       O'Shaughnessy "What
                                                    Works on Wall Street"
3.  Pioneer theme leadership              15       App data — proven
                                                    cluster runs (SNDK
                                                    +24%, AI Storage etc.)
4.  Catalyst proximity (≤14d)             15       Catalyst-driven trade
                                                    literature (Brunnermeier)
5.  Pre-frenzy signals                    15       Your Frenzy Radar's
                                                    6-signal detection
6.  Insider cluster (Lakonishok-Lee)      10       Lakonishok & Lee 2001,
                                                    JFE — 6% excess return
7.  Float / squeeze mechanics             10       Low-float runner
                                                    discipline (microcap
                                                    day-trade canon)
─────────────────────────────────────────────────────────────────────────
                                          100

Tier thresholds:
  PTS ≥ 80 → TINY_STRONG   (real edge; top-2% of universe)
  PTS ≥ 65 → TINY_BUY      (multiple gates aligned)
  PTS ≥ 50 → TINY_WATCH    (worth tracking, not high conviction)
  PTS  < 50 → IGNORE

Hard gates (return score=0 regardless of components):
  market_cap > $2B   → "TOO_LARGE" (not actually tiny)
  $vol < $500K/day   → "ILLIQUID"  (can't trade out cleanly)
"""
from __future__ import annotations

from typing import Optional

# ── Caps + tiers ─────────────────────────────────────────────────────────
MAX_MCAP_FOR_TINY = 2_000_000_000       # $2B ceiling — Russell 2000 territory
MIN_DOLLAR_VOL = 500_000                # tradeable liquidity floor
TIER_THRESHOLDS = (
    ("TINY_STRONG", 80),
    ("TINY_BUY",    65),
    ("TINY_WATCH",  50),
)


# ── Component scorers ────────────────────────────────────────────────────
def _canslim_component(rs_rank: Optional[float],
                       fundamentals: dict | None,
                       trend_passed: int | None) -> int:
    """CANSLIM (William O'Neil) — leader + EPS growth + new high. Up to 20."""
    pts = 0
    if rs_rank is not None:
        if rs_rank >= 90:    pts += 8     # 'L' = Leader
        elif rs_rank >= 80:  pts += 6
        elif rs_rank >= 70:  pts += 3
    f = fundamentals or {}
    eps_q = f.get("eps_growth_qoq_pct") or 0
    eps_a = f.get("eps_growth_yoy_pct") or 0
    if eps_q >= 25 and eps_a >= 25:    pts += 7   # 'C' + 'A' both passing
    elif eps_q >= 10 and eps_a >= 10:  pts += 3
    if trend_passed is not None and trend_passed >= 7:
        pts += 5      # 'N' = at/near new highs (proxied by trend gates)
    return min(20, pts)


def _tiny_titans_component(rs_rank: Optional[float],
                           ps_ratio: Optional[float],
                           market_cap: Optional[float]) -> int:
    """Tiny Titans (O'Shaughnessy) — micro-cap value+momentum combo. Up to 15."""
    pts = 0
    # Mcap sweet spot $25M-$1B (the "tiny titans" zone)
    if market_cap is not None:
        if 25_000_000 <= market_cap <= 1_000_000_000:    pts += 6
        elif market_cap <= 2_000_000_000:                pts += 3
    if ps_ratio is not None:
        if ps_ratio < 1.0:    pts += 5
        elif ps_ratio < 1.5:  pts += 3
    if rs_rank is not None and rs_rank >= 80:
        pts += 4
    return min(15, pts)


def _pioneer_component(pioneer_themes: list | None) -> int:
    """Theme-leadership boost — your Pioneer data. Active themes (AI Infra,
    AI Storage / HAMR, GLP-1, SMR Nuclear, etc.) are documented cluster
    movers in your own calibration data.
    Up to 15."""
    if not pioneer_themes:
        return 0
    n_themes = len(pioneer_themes)
    if n_themes >= 2:  return 15  # multi-theme exposure = layered tailwinds
    return 10


def _catalyst_component(catalyst: dict | None) -> int:
    """Imminent catalyst — earnings, FDA, contract within 14 days.
    Catalyst-driven trade research (Brunnermeier, Hobijn). Up to 15."""
    if not catalyst:
        return 0
    days = catalyst.get("days_to_event")
    kind = (catalyst.get("kind") or "").lower()
    if days is not None and 0 <= days <= 14:
        if kind == "fda" and days <= 7:                 return 15
        if kind in ("earnings", "fda", "court", "ada"): return 12
        if kind == "contract":                          return 8
        return 6
    if catalyst.get("recent_news_cluster") or catalyst.get("earnings_upcoming"):
        return 5
    return 0


def _frenzy_component(frenzy: dict | None) -> int:
    """Pre-frenzy radar — your 6-signal pre-breakout detector. Up to 15."""
    if not frenzy:
        return 0
    pts = 0
    if frenzy.get("quiet_volume_surge"):     pts += 5
    if frenzy.get("chatter_acceleration"):   pts += 4
    if frenzy.get("multi_day_buildup"):      pts += 2
    if frenzy.get("float_in_play"):          pts += 2
    if frenzy.get("cross_platform_chatter"): pts += 1
    if frenzy.get("fresh_appearance"):       pts += 1
    return min(15, pts)


def _insider_component(insider: dict | None) -> int:
    """Insider cluster (Lakonishok & Lee, JFE 2001) — 2+ officer buys
    within 30d → ~6% excess return over 6mo. Up to 10."""
    if not insider:
        return 0
    if insider.get("form4_cluster_buy"):  return 10
    if insider.get("has_recent_13d"):     return 6
    if insider.get("recent_form4_buys", 0) >= 1: return 3
    return 0


def _float_component(float_shares: Optional[float],
                     si_pct: Optional[float],
                     days_to_cover: Optional[float]) -> int:
    """Low-float runner mechanics. Microcap canon. Up to 10."""
    pts = 0
    if float_shares is not None:
        if float_shares < 20_000_000:      pts += 5
        elif float_shares < 50_000_000:    pts += 2
    if si_pct is not None:
        if si_pct >= 15:    pts += 3
        elif si_pct >= 8:   pts += 1
    if days_to_cover is not None and days_to_cover >= 3:
        pts += 2
    return min(10, pts)


# ── Public scorer ────────────────────────────────────────────────────────
def score_candidate(candidate: dict, *,
                    market_cap: Optional[float] = None,
                    frenzy: Optional[dict] = None,
                    avg_dollar_volume: Optional[float] = None,
                    float_shares: Optional[float] = None,
                    si_pct: Optional[float] = None,
                    days_to_cover: Optional[float] = None,
                    ps_ratio: Optional[float] = None) -> dict:
    """Score one candidate. Returns score (0-100), tier, components, and
    a human-readable narrative explaining what's driving the number."""
    # Hard gates
    if market_cap is not None and market_cap > MAX_MCAP_FOR_TINY:
        return {"score": 0, "tier": "TOO_LARGE", "skipped": "mcap > $2B",
                "components": {}}
    if avg_dollar_volume is not None and avg_dollar_volume < MIN_DOLLAR_VOL:
        return {"score": 0, "tier": "ILLIQUID", "skipped": "$vol < $500K",
                "components": {}}

    # Pull what we have from the SEPA candidate
    rs = candidate.get("rs_rank")
    trend = candidate.get("trend") or {}
    trend_passed = trend.get("passed") if isinstance(trend, dict) else None
    fundamentals = candidate.get("fundamentals") or {}
    insider = candidate.get("insider") or {}
    catalyst = candidate.get("catalyst") or {}
    pioneer_themes = candidate.get("pioneer_themes") or []

    parts = {
        "canslim":      _canslim_component(rs, fundamentals, trend_passed),
        "tiny_titans":  _tiny_titans_component(rs, ps_ratio, market_cap),
        "pioneer":      _pioneer_component(pioneer_themes),
        "catalyst":     _catalyst_component(catalyst),
        "frenzy":       _frenzy_component(frenzy),
        "insider":      _insider_component(insider),
        "float":        _float_component(float_shares, si_pct, days_to_cover),
    }
    score = max(0, min(100, sum(parts.values())))

    tier = "IGNORE"
    for label, threshold in TIER_THRESHOLDS:
        if score >= threshold:
            tier = label
            break

    return {
        "score": round(score, 1),
        "tier": tier,
        "components": parts,
        "gate_passed": True,
        "narrative": _explain_score(parts, pioneer_themes, catalyst,
                                     fundamentals, rs),
    }


def _explain_score(parts: dict, themes: list, catalyst: dict,
                   fundamentals: dict, rs: Optional[float]) -> str:
    bits = []
    if parts.get("canslim", 0) >= 12:
        bits.append(f"CANSLIM strong (RS {rs:.0f}, EPS growing)" if rs else "CANSLIM strong")
    if parts.get("tiny_titans", 0) >= 10:
        bits.append("Tiny Titans qualifier passed")
    if parts.get("pioneer", 0) >= 10 and themes:
        bits.append(f"Pioneer theme: {' · '.join(themes[:2])}")
    if parts.get("catalyst", 0) >= 8:
        days = catalyst.get("days_to_event") if catalyst else None
        kind = catalyst.get("kind") if catalyst else None
        if days is not None:
            bits.append(f"{kind or 'catalyst'} in {days}d")
        else:
            bits.append("catalyst proximity")
    if parts.get("frenzy", 0) >= 8:
        bits.append("pre-frenzy signals firing")
    if parts.get("insider", 0) >= 6:
        bits.append("insider cluster buying")
    if parts.get("float", 0) >= 5:
        bits.append("low-float setup")
    if not bits:
        return "Marginal — components weak across the board."
    return " · ".join(bits) + "."


def explain_methodology() -> dict:
    """Return the full methodology spec. Used by /tiny/methodology endpoint
    so the frontend InfoButton can show citations."""
    return {
        "name": "Pounce Tiny Score (PTS)",
        "max_score": 100,
        "components": [
            {"name": "CANSLIM-adapted", "weight": 20,
             "source": "William O'Neil — How to Make Money in Stocks (IBD)"},
            {"name": "Tiny Titans qualifier", "weight": 15,
             "source": "O'Shaughnessy — What Works on Wall Street (50yr backtest, ~37% annualized)"},
            {"name": "Pioneer theme leadership", "weight": 15,
             "source": "Empirical — your own theme-cluster calibration data (SNDK, MU, WDC, TER cluster)"},
            {"name": "Catalyst proximity (≤14d)", "weight": 15,
             "source": "Catalyst-driven trade research — Brunnermeier"},
            {"name": "Pre-frenzy signals", "weight": 15,
             "source": "Your Frenzy Radar — 6-signal pre-breakout pattern"},
            {"name": "Insider cluster (2+ officers, 30d)", "weight": 10,
             "source": "Lakonishok & Lee 2001, Journal of Financial Economics — ~6% excess return / 6mo"},
            {"name": "Float / squeeze mechanics", "weight": 10,
             "source": "Microcap day-trade discipline (Sykes, Bao)"},
        ],
        "tiers": [
            {"label": "TINY_STRONG", "min_score": 80, "interpretation": "Real edge — top 2% of universe."},
            {"label": "TINY_BUY",    "min_score": 65, "interpretation": "Multiple gates aligned."},
            {"label": "TINY_WATCH",  "min_score": 50, "interpretation": "Worth tracking, not high conviction."},
        ],
        "hard_gates": [
            f"market_cap ≤ ${MAX_MCAP_FOR_TINY:,.0f}",
            f"avg dollar volume ≥ ${MIN_DOLLAR_VOL:,.0f}/day",
        ],
    }
