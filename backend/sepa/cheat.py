"""3-C cheat (cup-completion cheat) tag — TTLAC §7's EARLIEST entry.

Ajay 2026-06-22: tag qualifiers that are forming a 3-C "cheat", to be surfaced
ONLY in a red (risk_off) market with no buyable pivots. That is the book's exact
use case: cheats develop during a general market correction, and the leaders
that rally off them "bottom first" as the averages turn up
(TTLAC §7 p.123, p.133). When there's nothing to buy the normal (breakout) way,
the cheat is where tomorrow's leaders are quietly setting up. The display gate
(red regime + no pivots) lives in the frontend; this module only DETECTS the
pattern on a scan row.

INFORMATIONAL ONLY — NOT an engine entry. The cheat is Minervini's most
AGGRESSIVE entry: bought inside the base, before a volume-confirmed breakout
(p.132, "called a cheat because ... the earliest point at which you should
attempt to buy any stock"). The deterministic Auto-Pilot keeps taking only
confirmed breakouts and NEVER reads this tag — the engine boundary is intact.

Derivation straight from TTLAC §7 (cited; LOCAL corpus only, Rule #1). Every
threshold below is a book number, not a house knob:

  CONTINUATION AFTER A PRIOR ADVANCE (p.133). The 3-C is a continuation pattern;
    to qualify, the stock "should have already moved up by at least 25 to 100
    percent ... during the previous 3 to 36 months." → a Trend-Template
    qualifier already >= 25% above its 52-week low.

  A MODERATE BASE / CORRECTION OFF THE HIGH (p.119). "Most constructive setups
    correct between 10 percent and 35 percent, some as much as 40 percent. Very
    deep correction patterns ... are failure prone." → must be IN a base 10-40%
    below its 52-week high: not at new highs (that's a breakout, not a cheat),
    not deeper than 40% (failure-prone).

  THE CHEAT PLATEAU = VOLUME CONTRACTION + PRICE TIGHTNESS (p.132, p.134). "A
    valid cheat area should exhibit a contraction in volume and tightness in
    price." → volume drying up (the 10-day average below the 50-day, p.226) AND
    a measured VCP contraction (a real base with >= 1 good contraction).

  NOT YET A BREAKOUT (p.132). The cheat is the entry BEFORE the proper pivot
    clears on expanding volume, so a name that is already `is_buyable`
    (a volume-confirmed breakout) has graduated past the cheat — not tagged.

  OPTIMUM SHAKEOUT (p.134, bonus only). "The optimum situation is to have the
    cheat drift down ... below a prior low point, creating a shakeout." Surfaced
    as a detail when the VCP undercut flag is present; never required.

Pure read of fields the scanner already computes — no new market math.
"""
from __future__ import annotations

from typing import Optional

# Book thresholds (source-guarded in tests/test_sepa_contracts.py). TTLAC §7.
CHEAT_MIN_PRIOR_ADVANCE_PCT = 25.0   # p.133: up >= 25-100% over the prior 3-36 mo
CHEAT_BASE_MIN_PCT = 10.0            # p.119: constructive corrections 10-40% ...
CHEAT_BASE_MAX_PCT = 40.0           # ... deeper than this is failure-prone (p.133)
CHEAT_VOL_DRYUP_MAX = 1.0           # p.226: 10-day avg below the 50-day = contraction


def _f(x) -> Optional[float]:
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def detect(row: dict) -> dict:
    """3-C cheat blob for one scan row. Always returns the full schema:

        {"is_cheat": bool, "off_high_pct": float|None,
         "pct_above_low": float|None, "vol_dryup": float|None,
         "good_contractions": int, "shakeout": bool,
         "reasons": [str], "cite": str}

    `is_cheat` is True only for a Trend-Template QUALIFIER (is_candidate) that
    matches every TTLAC §7 criterion; non-qualifiers are never cheats."""
    trend = row.get("trend") or {}
    vol = row.get("volume") or {}
    vcp = row.get("vcp") or {}

    is_qualifier = bool(row.get("is_candidate"))
    pct_above_low = _f(trend.get("pct_above_low"))
    off_high = _f(trend.get("pct_below_high"))
    vd = _f(vol.get("vol_dryup"))
    good = int(vcp.get("good_contraction_count") or 0)

    prior_advance = pct_above_low is not None and pct_above_low >= CHEAT_MIN_PRIOR_ADVANCE_PCT
    in_base = off_high is not None and CHEAT_BASE_MIN_PCT <= off_high <= CHEAT_BASE_MAX_PCT
    vol_contracting = vd is not None and vd < CHEAT_VOL_DRYUP_MAX
    tight_plateau = bool(vcp.get("has_base")) and good >= 1
    pre_breakout = not bool(row.get("is_buyable"))

    is_cheat = bool(is_qualifier and prior_advance and in_base
                    and vol_contracting and tight_plateau and pre_breakout)

    # Optimum shakeout (p.134) — bonus signal only, defensive read (the VCP
    # detector may or may not expose an undercut flag; absent reads falsy).
    shakeout = bool(vcp.get("undercut_low") or vcp.get("shakeout"))

    reasons = []
    if is_cheat:
        reasons.append("3-C cheat: in a %.0f%% base off the high with volume "
                       "drying up and a tight coil — the earliest entry, before "
                       "the breakout (TTLAC §7 p.132)" % off_high)
        if shakeout:
            reasons.append("optimum: undercut a prior low (shakeout, TTLAC §7 p.134)")

    return {
        "is_cheat":          is_cheat,
        "off_high_pct":      round(off_high, 1) if off_high is not None else None,
        "pct_above_low":     round(pct_above_low, 1) if pct_above_low is not None else None,
        "vol_dryup":         round(vd, 2) if vd is not None else None,
        "good_contractions": good,
        "shakeout":          shakeout,
        "reasons":           reasons,
        "cite":              "TTLAC §7 (ebook p.132)",
    }
