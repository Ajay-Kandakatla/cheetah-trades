"""ⓘ Quality — the plain-words description of `eq_score`, built from the engine.

Ajay 2026-09-28, on the 🔥 Hottest board: "also can you help with info icon on
the quality?"

The Quality column prints `sepa.earnings_quality.compute()`'s 0–100 `score`.
This module describes that score EXACTLY as the code computes it, so the ⓘ
beside the header can never say something the engine does not do:

  * every named threshold is read from `earnings_quality` / `sales` INSIDE
    `describe()` — patch a constant and the text changes with it;
  * the point weights, penalties, the `steady` cut and the 5-quarter minimum
    are INLINE literals in `compute()` (no names there, and the SEPA engine is
    not edited for a description). They are mirrored below and pinned
    BEHAVIOURALLY by `tests/test_earnings_quality_info.py`: each mirror must
    equal the score delta `compute()` actually produces, so a changed literal
    turns that test red instead of leaving the ⓘ wrong;
  * the freshness sentence takes `max_age_sec` from the caller (the board
    passes `research.CACHE_TTL_SEC`, the age `decision_snapshot` drops a row
    at) — this module never imports `sepa.research` and states no refresh
    cadence number, because none exists as a constant.

WHAT IT IS NOT. `MEASURED = False`: no study on this app has tested whether a
higher Quality score leads to better forward returns. The explainer says so
first. It carries no page numbers, no quotes and no attribution — `compute()`'s
own `reason` strings (which carry page cites) are never served from here.
"""
from __future__ import annotations

from typing import Optional

from sepa import earnings_quality as EQ
from sepa import sales as S

VERSION = 1

# Honesty flag, the `growth/capital_quality.py` pattern. May flip True only
# once a study exists at STUDY_SCRIPT (guarded by the test).
MEASURED = False
STUDY_SCRIPT = "backend/scripts/eq_score_forward_returns_study.py"   # does not exist
MEASURED_NOTE = ("A description of the company's last filed quarters, not a measured "
                 "predictor of returns: no study on this app has tested whether a higher "
                 "Quality score leads to better forward returns.")

# Mirrors of compute()'s INLINE literals — pinned behaviourally by
# tests/test_earnings_quality_info.py (each equals the delta compute() makes).
PTS = {"eps_level": 20.0, "sales": 20.0, "margin": 15.0, "eps_accel": 12.0,
       "sales_accel": 12.0, "margin_accel": 11.0, "surprise": 10.0}
MARGIN_FLAT_PTS = 7.0
EPS_ACCEL_2Q_PTS = 6.0
SALES_ACCEL_PTS = 6.0
PENALTY = {"low_quality_beat": 25.0, "inventory": 10.0, "double_trouble": 20.0}
STEADY_MIN_SCORE = 55
MIN_QUARTERS = 5
# canslim never passes `surprise_pct` into compute(); a source guard in the
# test turns red the day it does, so this flag and the wording move together.
SURPRISE_WIRED = False

TIER_ORDER = ("code33", "red_flag", "accelerating", "steady", "weak", "unknown")

# When compute() returns score=None: `eps_g[0] is None and rev_g[0] is None`,
# and `_yoy` is None when the series is 4 quarters or shorter, the latest or
# the year-ago value is missing, or the year-ago value is zero. So a name with
# 8 quarters on file can still be blank (critic 2026-09-28) — the text names
# every way, pinned by test_earnings_quality_info.py.
NO_YOY_TEXT = (f"neither EPS nor sales can be compared with a year ago for the latest "
               f"quarter — fewer than {MIN_QUARTERS} quarters on file, the latest or the "
               f"year-ago quarter missing, or a year-ago value of zero.")


def _g(x) -> str:
    """One number format for every served sentence: 25.0 -> '25', 0.5 -> '0.5'."""
    return f"{float(x):g}"


def _n(x):
    """A served number: an int when whole, else the float."""
    f = float(x)
    return int(f) if f.is_integer() else f


def ceiling_today() -> int:
    """The most a name can score on today's data path."""
    total = sum(PTS.values()) - (0.0 if SURPRISE_WIRED else PTS["surprise"])
    return int(round(min(total, 100.0)))


def _ttl_text(max_age_sec) -> Optional[str]:
    try:
        v = float(max_age_sec)
    except (TypeError, ValueError):
        return None
    if not v > 0:
        return None
    return f"{v / 86400:g} days"


def describe(fundamentals_as_of: Optional[dict] = None,
             max_age_sec=None) -> dict:
    """The served `quality_info` block. PURE — no I/O, no clock."""
    ttl = _ttl_text(max_age_sec)
    band = _g(EQ.MARGIN_FLAT_BAND_PCT)
    gap = _g(EQ.INV_OVER_SALES_GAP_PCT)
    floor = _g(EQ.INV_REDFLAG_ABS_FLOOR_PCT)

    surprise_rule = f"Up to {_g(PTS['surprise'])}: the earnings surprise in %, capped."
    if not SURPRISE_WIRED:
        surprise_rule += (" This app's data path never passes a surprise in, so it is 0 "
                          "on every name today.")

    points = [
        {"key": "eps_level", "label": "EPS growth", "max": _n(PTS["eps_level"]),
         "rule": (f"Latest quarter's EPS vs the same quarter a year ago: 0 points at 0% or "
                  f"below, rising evenly to the full {_g(PTS['eps_level'])} at "
                  f"+{_g(EQ.STRONG_EPS_YOY_PCT)}% or more.")},
        {"key": "sales", "label": "Sales score", "max": _n(PTS["sales"]),
         "rule": (f"The app's Sales score (0–100) scaled down to {_g(PTS['sales'])}. It rises "
                  f"with sales growth vs a year ago, with bonuses — only at "
                  f"+{_g(S.SALES_FLOOR_PCT)}% growth or more — for accelerating sales, "
                  f"consecutive growing quarters and sales outgrowing EPS.")},
        {"key": "margin", "label": "Net margin vs a year ago", "max": _n(PTS["margin"]),
         "rule": (f"Latest quarter's net margin vs the same quarter a year ago: "
                  f"{_g(PTS['margin'])} if it widened by more than {band} percentage point, "
                  f"0 if it narrowed by more than that, {_g(MARGIN_FLAT_PTS)} if in between "
                  f"or unknown.")},
        {"key": "eps_accel", "label": "EPS growth speeding up", "max": _n(PTS["eps_accel"]),
         "rule": (f"{_g(PTS['eps_accel'])} if the EPS growth rate rose step by step across the "
                  f"last three quarters (oldest lowest, latest highest and above zero); "
                  f"{_g(EPS_ACCEL_2Q_PTS)} if only the latest quarter's rate beat the one "
                  f"before (and is above zero); otherwise 0.")},
        {"key": "sales_accel", "label": "Sales growth speeding up",
         "max": _n(PTS["sales_accel"]),
         "rule": (f"{_g(PTS['sales_accel'])} if the sales growth rate rose step by step across "
                  f"the last three quarters (latest above zero); {_g(SALES_ACCEL_PTS)} if the "
                  f"Sales score calls sales accelerating (latest quarter's growth above the "
                  f"one before, and above zero); otherwise 0.")},
        {"key": "margin_accel", "label": "Net margin rising", "max": _n(PTS["margin_accel"]),
         "rule": (f"{_g(PTS['margin_accel'])} if net margin rose step by step across the last "
                  f"three quarters, quarter over quarter; otherwise 0.")},
        {"key": "surprise", "label": "Earnings surprise", "max": _n(PTS["surprise"]),
         "rule": surprise_rule},
    ]

    penalties = [
        {"key": "low_quality_beat", "label": "A beat with no sales behind it",
         "points": _n(PENALTY["low_quality_beat"]),
         "rule": (f"EPS up {_g(EQ.LOWQ_EPS_MIN_PCT)}% or more on sales up less than "
                  f"{_g(EQ.LOWQ_SALES_MAX_PCT)}%, with net margin not widening by more than "
                  f"{band} point year over year.")},
        {"key": "inventory", "label": "⚠️ inventory flag",
         "points": _n(PENALTY["inventory"]),
         "rule": "The ⚠️ mark below."},
        {"key": "double_trouble", "label": "Double trouble",
         "points": _n(PENALTY["double_trouble"]),
         "rule": (f"The ⚠️ flag AND receivables growing more than {gap} points faster than "
                  f"sales (and above {floor}%): takes {_g(PENALTY['double_trouble'])} instead "
                  f"of the {_g(PENALTY['inventory'])}. Receivables are read only for the names "
                  f"that get the supplemental read.")},
    ]

    ceiling = ceiling_today()
    ceiling_note = "Added up and clamped to 0–100, then rounded."
    if not SURPRISE_WIRED:
        ceiling_note += (f" The most a name can score today is {ceiling}: the surprise "
                         f"points never arrive.")

    tiers = [
        {"key": "code33", "label": "🎯 Code 33",
         "rule": ("EPS growth rate, sales growth rate and net margin all rose step by step "
                  "across the last three quarters (EPS and sales growth above zero in the "
                  "latest).")},
        {"key": "red_flag", "label": "Red flag",
         "rule": "Double trouble, a beat with no sales behind it, or the ⚠️ inventory flag."},
        {"key": "accelerating", "label": "Accelerating",
         "rule": (f"The latest EPS growth rate beat the quarter before (and is above zero), "
                  f"or sales are accelerating — and net margin did not narrow by more than "
                  f"{band} point year over year.")},
        {"key": "steady", "label": "Steady",
         "rule": f"None of the above, and a score of {STEADY_MIN_SCORE} or more."},
        {"key": "weak", "label": "Weak", "rule": "Everything else that has a score."},
        {"key": "unknown", "label": "Blank (—)",
         "rule": f"No score: {NO_YOY_TEXT}"},
    ]

    marks = [
        {"mark": "🎯", "rule": "Code 33 — the top tier above."},
        {"mark": "⚠️",
         "rule": (f"Inventory grew more than {gap} points faster than sales year over year, "
                  f"inventory growth is above {floor}%, and sales growth is below "
                  f"{_g(EQ.INV_REDFLAG_SALES_STRONG_PCT)}% (a build alongside strong sales is "
                  f"left alone). Total inventory only.")},
    ]

    stale = (f"The name's research-cache row is older than {ttl}, so the board does not "
             f"use it." if ttl else
             "The name's research-cache row is too old for the board to use.")
    blank = [
        NO_YOY_TEXT[0].upper() + NO_YOY_TEXT[1:],
        ("Names whose fundamentals came from the fallback data source are left unscored on "
         "purpose — the score is only computed from the filing-backed data."),
        stale,
        "No research-cache row for the name yet.",
    ]

    as_of = None
    if isinstance(fundamentals_as_of, dict) and fundamentals_as_of.get("oldest"):
        note = ("From the research cache, which a scheduled job refreshes — a fresh print "
                "shows here only after its next run.")
        if ttl:
            note += f" A row older than {ttl} is not used."
        as_of = {"oldest": fundamentals_as_of.get("oldest"),
                 "newest": fundamentals_as_of.get("newest"),
                 "n": fundamentals_as_of.get("n"),
                 "note": note}

    return {
        "version": VERSION,
        "title": "Quality — how the 0–100 score is built",
        "summary": ("A 0–100 read of how the last filed quarters' earnings were built: growth "
                    "backed by sales, margins widening, growth rates speeding up — minus "
                    "penalties for a beat with no sales behind it and for inventory piling up."),
        "measured": MEASURED,
        "measured_note": MEASURED_NOTE,
        "weights_note": "The point weights and most cut-offs are this app's own choices.",
        "points": points,
        "penalties": penalties,
        "ceiling_today": ceiling,
        "ceiling_note": ceiling_note,
        "tiers": tiers,
        "tier_note": ("The first tier that matches wins, in this order. Hover a score to see "
                      "its tier."),
        "marks": marks,
        "blank": blank,
        "group_rows": ("Sector, industry and roster rows show the median score of their full "
                       "membership, with no 🎯 or ⚠️."),
        "fundamentals_as_of": as_of,
        "source": "sepa/earnings_quality.py · compute()",
    }
