"""Score a candidate on two ORTHOGONAL axes:

  - chatter_score (0-100): how loud the social signal is
  - evidence_score (0-100): how solid the supporting hard data is

We deliberately do NOT collapse these into a single composite. The whole
point of this tab is to let the user spot RYOJ-style names where chatter
is high but evidence is missing — that's the pump warning signal.

A composite is offered as a convenience for sorting, but the UI shows
both axes prominently.

Quadrant labels (referenced by the frontend):
  REAL       — chatter HIGH, evidence HIGH (both confirm)
  OVERLOOKED — chatter LOW,  evidence HIGH (early/quiet)
  PUMP_RISK  — chatter HIGH, evidence LOW  (RYOJ-style — needs more)
  DEAD       — chatter LOW,  evidence LOW  (filter these out)
"""
from __future__ import annotations

import math
from typing import Optional


def _log_scale(x: float, max_x: float, ceiling: float = 100.0) -> float:
    """Compress wide-range values logarithmically to [0, ceiling]."""
    if x <= 0:
        return 0.0
    return min(ceiling, math.log10(1 + x) / math.log10(1 + max_x) * ceiling)


def chatter_score(chatter: dict) -> float:
    """0-100 score from chatter signals.

    Inputs:
      stocktwits.n_24h    : messages in last 24h (~5 = quiet, 50 = loud)
      reddit.n_posts_24h  : posts in last 24h (~2 = quiet, 20 = loud)
      stocktwits.n_messages : total visible messages (caps at 30 per stream)
    """
    if not chatter:
        return 0.0

    st = chatter.get("stocktwits") or {}
    rd = chatter.get("reddit") or {}

    # Stocktwits: 50+ msgs/24h ≈ very loud
    st_24 = st.get("n_24h") or 0
    st_score = _log_scale(st_24, 50, 60)  # max 60 pts

    # Reddit: 20 posts/24h across catalyst subs ≈ very loud
    rd_24 = rd.get("n_posts_24h") or 0
    rd_score = _log_scale(rd_24, 20, 40)  # max 40 pts

    score = st_score + rd_score
    return round(min(100.0, score), 1)


def evidence_score(evidence: dict, *, candidate: Optional[dict] = None) -> float:
    """0-100 score from hard evidence.

    Categories (additive, capped):
      Bullish news (Massive)        : up to 30 pts
      Material 8-K filing            : 20 pts
      13D/13G filing (smart money)   : 25 pts
      Insider buy filing (Form 4)    : 15 pts
      Volume surge ratio             : up to 20 pts (1.5x = 5pts, 5x = 15pts, 10x+ = 20pts)
      Bearish news / dilutive S-3    : NEGATIVE (subtract from score)

    Note: a stock with 50× volume surge alone shouldn't be high evidence —
    real evidence is news+filings. Volume surge is corroboration, weighted
    moderately.
    """
    if not evidence:
        return 0.0

    score = 0.0

    news = evidence.get("news") or {}
    n_bull = news.get("n_bullish") or 0
    n_bear = news.get("n_bearish") or 0
    score += min(30, n_bull * 12)
    score -= min(40, n_bear * 14)  # bearish news heavily punishes

    sec = evidence.get("sec_filings") or {}
    if sec.get("has_8k"):
        score += 20
    if sec.get("has_13d"):
        score += 25
    if sec.get("has_insider_trade"):
        score += 15
    if sec.get("has_offering"):
        # Offerings = dilutive. RYOJ-style names often run on hype, then a
        # secondary kills them. Heavy penalty.
        score -= 25

    # Volume surge contribution
    if candidate:
        surge = candidate.get("volume_surge_ratio") or 0
        if surge >= 1.5:
            score += min(20, math.log10(1 + surge) / math.log10(11) * 20)

    return round(max(0.0, min(100.0, score)), 1)


def quadrant(chat: float, evid: float, *,
             chatter_threshold: float = 40.0,
             evidence_threshold: float = 35.0) -> str:
    """Label the candidate by which 2x2 cell it lands in."""
    chat_high = chat >= chatter_threshold
    evid_high = evid >= evidence_threshold
    if chat_high and evid_high:
        return "REAL"
    if chat_high and not evid_high:
        return "PUMP_RISK"
    if not chat_high and evid_high:
        return "OVERLOOKED"
    return "DEAD"


def detect_pump_phase(candidate: dict, chatter: dict, evidence: dict,
                       chat_score: float, evid_score: float) -> dict:
    """Classify a candidate by 5-phase pump model.

    Returns {phase, action, entry_hint, stop_signal} where:
      phase in {ACCUMULATION, BREAKOUT, FRENZY, DISTRIBUTION, CRASH, NONE}
      action in {WATCH, ENTER_VWAP, TRIM, EXIT, AVOID}
      entry_hint: short trader-friendly entry guidance
      stop_signal: hard-stop reason if any

    Heuristics are conservative — better to flag DISTRIBUTION early than
    miss the dump warning.
    """
    chg = candidate.get("change_pct") or 0
    surge = candidate.get("volume_surge_ratio") or 1
    sec = (evidence or {}).get("sec_filings") or {}
    has_offering = sec.get("has_offering") or False
    has_8k = sec.get("has_8k") or False
    velocity = (chatter or {}).get("velocity_per_hour") or 0
    cap = candidate.get("market_cap") or 0
    price = candidate.get("price") or 0

    # --- DISTRIBUTION: hard exit signals override everything ---------
    if has_offering:
        return {
            "phase": "DISTRIBUTION",
            "action": "EXIT",
            "entry_hint": "Recent S-3/S-1/FWP filing — secondary offering risk. Avoid.",
            "stop_signal": "dilutive offering filed in last 7 days",
        }

    # --- CRASH: down hard but chatter still loud (pump victims) ------
    if chg < -15 and chat_score > 30:
        return {
            "phase": "CRASH",
            "action": "AVOID",
            "entry_hint": "Already crashed. Don't catch the knife. Wait 1-2 sessions for capitulation.",
            "stop_signal": None,
        }

    # --- FRENZY: late-stage retail FOMO ------------------------------
    if chg > 30 and chat_score > 50 and surge > 5:
        return {
            "phase": "FRENZY",
            "action": "TRIM",
            "entry_hint": "Late-stage FOMO. If long: take profits in chunks. New entry only on -15% pullback to VWAP with hold.",
            "stop_signal": None,
        }

    # --- BREAKOUT: best risk/reward zone -----------------------------
    if 15 <= chg <= 50 and 2.5 <= surge <= 6:
        # Add an extra check that the chatter isn't pure noise — need
        # SOME evidence or at least 8-K filed
        if evid_score >= 20 or has_8k or chat_score >= 30:
            return {
                "phase": "BREAKOUT",
                "action": "ENTER_VWAP",
                "entry_hint": (
                    "Best risk/reward zone. Buy on VWAP retest with hold. "
                    "Stop -8% or below LoD. Take 1/3 at +25%, ride trail."
                ),
                "stop_signal": None,
            }

    # --- ACCUMULATION: quiet, but float being bought -----------------
    if chg < 15 and surge >= 1.5 and chat_score < 30:
        return {
            "phase": "ACCUMULATION",
            "action": "WATCH",
            "entry_hint": "Quiet accumulation pattern. Add to watchlist; alert on first 20%+ break with chatter spike.",
            "stop_signal": None,
        }

    # --- DEFAULT: not a clear pump signal ----------------------------
    if abs(chg) < 8:
        return {"phase": "NONE", "action": "AVOID", "entry_hint": "Too quiet — not a pump candidate.", "stop_signal": None}

    # Catch-all: chatter loud but evidence/volume not confirming = retail-only fluff
    if chat_score >= 50 and evid_score < 20 and surge < 3:
        return {
            "phase": "FRENZY",
            "action": "AVOID",
            "entry_hint": "Pure chatter, no real volume confirmation. RYOJ-style hopium. Skip until volume confirms.",
            "stop_signal": None,
        }

    # Mild move with some volume — could be early breakout
    if 8 <= chg <= 25 and surge >= 1.5:
        return {
            "phase": "BREAKOUT",
            "action": "ENTER_VWAP" if evid_score >= 20 else "WATCH",
            "entry_hint": "Early breakout. Need evidence confirmation OR fresh chatter spike before entering.",
            "stop_signal": None,
        }

    # Sharp drop without distribution flags
    if chg < -10:
        return {
            "phase": "CRASH",
            "action": "AVOID",
            "entry_hint": "Selling off. Don't try to bottom-fish microcaps without a catalyst.",
            "stop_signal": None,
        }

    return {"phase": "NONE", "action": "WATCH", "entry_hint": None, "stop_signal": None}


def score_candidate(candidate: dict, chatter: Optional[dict], evidence: Optional[dict]) -> dict:
    """Apply both scores + quadrant label and a sortable composite."""
    chat = chatter_score(chatter or {})
    evid = evidence_score(evidence or {}, candidate=candidate)
    quad = quadrant(chat, evid)
    pump = detect_pump_phase(candidate, chatter or {}, evidence or {}, chat, evid)

    # Composite: weighted toward evidence (we want REAL > PUMP_RISK > OVERLOOKED > DEAD)
    # Plus a kicker for absolute price move because sorting by score alone
    # buries names that are up 50% with no chatter yet.
    move_kicker = min(20.0, abs(candidate.get("change_pct") or 0) * 0.4)
    composite = round(chat * 0.35 + evid * 0.55 + move_kicker, 1)

    return {
        "chatter_score": chat,
        "evidence_score": evid,
        "quadrant": quad,
        "composite_score": composite,
        "pump": pump,
    }


__all__ = ["chatter_score", "evidence_score", "quadrant", "score_candidate", "detect_pump_phase"]
