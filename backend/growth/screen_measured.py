"""MEASURED 2026-09-21 — the 🚀 100/100 screen ITSELF (cell G100, every member).

Ajay 2026-10-12, his-call #1 ("Reword those outdated 'never measured'
lines?" -> "yes"). The 2026-09-21 point-in-time replay
(`backend/scripts/board_growth_replay.py`, write-up
`docs/research/board_growth_2026_09_21.md`) DID measure the screen, so every
surface that called it unmeasured now says what was
measured instead — from THIS module, never retyped.

Two cells, two functions, never concatenated:
  * G100        — every name on the screen (this module).
  * G100_ARRIVE — names ARRIVING on it (`growth.arrivals.honesty_line`).
"Every interval spans zero" is TRUE for G100_ARRIVE and FALSE here: the
126-day DATE-clustered lift interval clears zero while its symbol-clustered
twin does not. Which intervals clear, and how many control medians are
negative, are COMPUTED from `SCREEN_MEASURED`, so a re-run that flips a sign
changes the sentence (and fails the pins in `tests/test_screen_measured.py`
first, where every field is pinned to the replay's artifact).

A LEAF: imports nothing from the repo, so `sepa.board_arrival`,
`growth.arrivals`, `growth.api` and `supply_demand.rules_info` can all import
it without a cycle (subprocess DAG pin in `tests/test_growth_arrivals.py`).

Rule #10: it sorts nothing, filters nothing, gates nothing and sends nothing.
"""
from __future__ import annotations

from typing import List, Tuple

HORIZONS = ("h21", "h63", "h126")
CLUSTERINGS = (("ci_symbol", "symbol-clustered"), ("ci_date", "date-clustered"))

SCREEN_MEASURED = {
    "run_date": "2026-09-21",
    "doc": "docs/research/board_growth_2026_09_21.md",
    "script": "backend/scripts/board_growth_replay.py",
    "panel_dates": 24,                               # repro.n_dates_panel
    "cell": "G100",
    # MEDIAN lift vs the scored universe, BOTH clusterings, EVERY horizon (2dp).
    "lift": {
        "h21":  {"n": 265, "n_symbols": 72, "n_dates": 20, "median_lift_pp": 1.11,
                 "ci_symbol": (-0.81, 2.89), "ci_date": (-1.23, 3.10)},
        "h63":  {"n": 237, "n_symbols": 70, "n_dates": 18, "median_lift_pp": 3.44,
                 "ci_symbol": (-3.68, 8.30), "ci_date": (-2.64, 8.36)},
        "h126": {"n": 191, "n_symbols": 48, "n_dates": 15, "median_lift_pp": 6.96,
                 "ci_symbol": (-1.08, 14.35), "ci_date": (1.41, 15.37)},
    },
    # Excess over the trailing-momentum-quintile mean of all-scored. The CI is
    # on the MEAN and symbol-clustered ONLY (the artifact carries no
    # date-clustered interval for this read), so the MEDIAN rides beside it.
    "momentum_control": {
        "h21":  {"n": 225, "mean_excess_pp": 1.89, "median_excess_pp": -0.42,
                 "ci_symbol": (-0.42, 4.20)},
        "h63":  {"n": 197, "mean_excess_pp": 6.85, "median_excess_pp": -1.55,
                 "ci_symbol": (0.31, 13.85)},
        "h126": {"n": 151, "mean_excess_pp": 8.21, "median_excess_pp": -2.06,
                 "ci_symbol": (-2.77, 20.38)},
    },
}


def sgn(v, d: int = 2) -> str:
    """'+3.69' / '−0.22' — always signed, with a REAL minus (U+2212).

    Moved here from `growth.arrivals._sgn` (same body; arrivals re-exports it
    as `_sgn`). Applied per NUMBER only — never a sentence-wide replace, which
    would eat the hyphens in '2026-09-21', 'point-in-time' and
    'symbol-clustered'."""
    return ("%s%%.%df" % ("+" if v >= 0 else "−", d)) % abs(v)


def ci(pair) -> str:
    """'−0.81 to +2.89'."""
    return "%s to %s" % (sgn(pair[0]), sgn(pair[1]))


def clears_zero(pair) -> bool:
    """The ONE definition: the interval's low end is above zero. Every lift
    interval in the artifact has hi > 0, so 'spans zero' = not clears_zero."""
    return float(pair[0]) > 0


def _days(h: str) -> int:
    return int(h[1:])


def clearing_intervals() -> List[Tuple[int, str]]:
    """[(horizon_days, clustering_label)] for every LIFT interval that clears
    zero — computed from SCREEN_MEASURED, never typed."""
    L = SCREEN_MEASURED["lift"]
    return [(_days(h), label) for h in HORIZONS for key, label in CLUSTERINGS
            if clears_zero(L[h][key])]


def negative_control_count() -> int:
    """How many momentum-matched MEDIAN excesses are below zero."""
    C = SCREEN_MEASURED["momentum_control"]
    return sum(1 for h in HORIZONS if C[h]["median_excess_pp"] < 0)


def _n_intervals() -> int:
    return len(HORIZONS) * len(CLUSTERINGS)


def _verb(n: int) -> str:
    return "clears" if n == 1 else "clear"


def _verdict(pair) -> str:
    return "CLEARS zero" if clears_zero(pair) else "spans zero"


def screen_clause() -> str:
    """ONE short clause — the phone payload's tail and the served board
    `disclaimer`. Numbers via `sgn`, counts and verb agreement computed."""
    m = SCREEN_MEASURED
    L = m["lift"]
    n_clear = len(clearing_intervals())
    lifts = ", ".join("%spp/%dd" % (sgn(L[h]["median_lift_pp"]), _days(h))
                      for h in HORIZONS)
    return (
        "MEASURED %s: 100/100 screen median lift %s; %d of %d CIs %s zero, "
        "momentum-matched median negative %d of %d — a lean, not a finding."
    ) % (m["run_date"], lifts, n_clear, _n_intervals(), _verb(n_clear),
         negative_control_count(), len(HORIZONS))


def screen_line() -> str:
    """The board's folded body — every horizon, both clusterings, the
    control. Each interval's verdict word comes from `clears_zero`."""
    m = SCREEN_MEASURED
    L, C = m["lift"], m["momentum_control"]
    h0, rest = HORIZONS[0], HORIZONS[1:]
    first = L[h0]
    first_txt = (
        "names on the screen beat the scored universe by a MEDIAN %spp over the "
        "next %d sessions (%d symbol-bars, %d symbols, %d dates) — 95%% CI %s "
        "symbol-clustered, %s; %s date-clustered, %s"
    ) % (sgn(first["median_lift_pp"]), _days(h0), int(first["n"]),
         int(first["n_symbols"]), int(first["n_dates"]),
         ci(first["ci_symbol"]), _verdict(first["ci_symbol"]),
         ci(first["ci_date"]), _verdict(first["ci_date"]))
    rest_txt = "; ".join(
        "%spp at %d days (CI %s symbol-clustered, %s; %s date-clustered, %s)" % (
            sgn(L[h]["median_lift_pp"]), _days(h),
            ci(L[h]["ci_symbol"]), _verdict(L[h]["ci_symbol"]),
            ci(L[h]["ci_date"]), _verdict(L[h]["ci_date"]))
        for h in rest)
    clearing = clearing_intervals()
    n_clear = len(clearing)
    clear_txt = "%d of %d lift intervals %s zero" % (
        n_clear, _n_intervals(), _verb(n_clear))
    if clearing:
        clear_txt += ": " + ", ".join("the %d-day %s one" % (d, lab)
                                      for d, lab in clearing)
    ctrl = ", ".join(
        ("%spp at %d days" if i == 0 else "%spp at %d") % (
            sgn(C[h]["median_excess_pp"]), _days(h))
        for i, h in enumerate(HORIZONS))
    ctrl_ci = ", ".join(ci(C[h]["ci_symbol"]) for h in HORIZONS)
    return (
        "MEASURED %s — THE 100/100 SCREEN ITSELF, EVERY MEMBER, NOT ONLY "
        "ARRIVALS. In a point-in-time replay over %d monthly cross-sections, "
        "%s; %s. %s. Against a momentum-matched control the MEDIAN excess is "
        "%s — negative at %d of %d horizons; the control's interval is on the "
        "MEAN and symbol-clustered only (%s). A lean, not a finding. Discovery "
        "list, not a buy signal."
    ) % (m["run_date"], int(m["panel_dates"]), first_txt, rest_txt, clear_txt,
         ctrl, negative_control_count(), len(HORIZONS), ctrl_ci)


def screen_headline() -> str:
    """The fold's headline — the date only, no measured number."""
    return ("MEASURED %s — THE 100/100 SCREEN: A LEAN, NOT A FINDING"
            % SCREEN_MEASURED["run_date"])
