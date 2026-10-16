"""🕯️ Doji Sweep — the pre-registered study's verdict literal (2026-10-16).

Ajay 2026-10-16, verbatim: "create me a new tab for Doji candle after a sweep.
For any stocks after a down trend. May be from all chart maps especially on the
60% 70% down stocks" — and K1: "I heard but do some research and back test
please on accuracy".

`doji_sweep_tab.study_block()` reads MEASURED lazily. The one pre-registered
outcome run (2026-10-16, head 2845fe24) is pasted below; the served line says
MEASURED. The placeholder `{"state": "unmeasured"}` is what this literal was
before the run (load() still falls back to it for a non-dict).

HOW IT CHANGES (never by hand-typing numbers):
  1. the prereg docs/research/doji_sweep_study_2026_10_16.md is committed;
  2. backend/scripts/doji_sweep_study.py --prereg-commit <hash> --prereg-blob
     <sha> runs in the throwaway container outside 09:00–16:30 ET (Mongo
     read-only, no provider call — AMENDMENTS6 B18);
  3. the artifact is copied to backend/scripts/doji_sweep_measured.json and the
     printed measured_literal pasted below verbatim —
     tests/test_doji_sweep_study.py pins it field-for-field.

THE SCHEMA the study emits lives here (one place; the study script and the tab
both read these names):
  * ARTIFACT_KEYS — the artifact JSON, exactly;
  * CELL_KEYS — one outcome cell, exactly (COUNT_CELL_KEYS in a smoke /
    count-only artifact: no outcome key exists there — no peeking);
  * LITERAL_TOP_KEYS / LITERAL_PRIMARY_KEYS / LITERAL_CELL_KEYS — the pasted
    literal, exactly.

AMENDMENTS6 (binding, 2026-10-16):
  * B2 — the binding CI is a BLOCK bootstrap over `BLOCK_SESSIONS`-session date
    blocks (`ci_block`); the by-name CI (`ci_symbol`) is the second axis; a
    verdict cell reads "separates" / "inverted" only when BOTH axes agree, else
    "axes_disagree". Every outcome is also served market-adjusted (minus SPY's
    return over the identical window — the `adj_*` keys) and the verdict uses
    the market-adjusted read.
  * B4 — the PRIMARY cell is his "60% 70%": 60%+ under the 52-week high, the
    house 5% body, his 5% test, the 10-session horizon, market-adjusted.
  * B5 — the doji contrast `test_no_doji` (the same test, no doji) is
    pre-registered and its verdict is served beside the primary.
  * B6 — verdict words for exactly `VERDICT_CELLS` (Holm-corrected across the
    three); every other cell is served as numbers with `EXPLORATORY_LABEL`.
  * B1 — `placebo_short_pool` counts the events whose placebo pool held fewer
    than k eligible days after the window exclusions; it and `n_unmatched` are
    carried into the literal's primary so the tab can serve them.
  * B4 — `w52_70` is PREDECLARED_TOO_SMALL: served with its count, never a
    verdict word.

Fix round 1 (2026-10-16, the WP-A critic):
  * `test_no_doji` is a normal cell — tests WITHOUT a doji against their OWN
    matched days. Its verdict says how those tests did against the matched
    days; it is NOT a primary-minus-no-doji contrast, and the tab never words
    it as "the doji adds". The reader compares the primary line with it.
  * Every verdict cell carries `ci_pct` (the level of the CIs its verdict
    used) and `p_holm` (the Holm-adjusted p across the three VERDICT_CELLS, or
    None when the study did not record one). The tab prints the CI at
    `ci_pct` and says "Holm-corrected" only when all three carry a `p_holm`.
  * Exploratory cells carry NO `verdict` key in the literal and a `verdict` of
    None in the artifact (B6: never a verdict word).

Fix round 2 (2026-10-16, the WP-S critic):
  * `n_detected` (every detected event) and `n_blocks` (the contrast set's
    BLOCK_SESSIONS-session blocks) join CELL_KEYS and LITERAL_PRIMARY_KEYS, so
    the counts behind a verdict are visible; the prereg sets NO block-count
    floor (n_blocks is served, never a gate).
  * GIT_KEYS carries `source` ("measured" = git read in-process, "attested" =
    the launcher's --git-head / --git-clean), so an attested clean tree is never
    served as a measured one.
"""
from __future__ import annotations

SCHEMA_VERSION = 1                 # TRANSPORT — bump with the artifact's shape
MIN_CELL_EVENTS = 100              # MINE (HIS CALL Q10) — fewer events and a cell reads "too_small"
MIN_CELL_DATES = 30                # Cheetah default (house) — == scripts.explosive_study.MIN_BUCKET_N (test-pinned, never imported here)
BLOCK_SESSIONS = 10                # MINE (AMENDMENTS6 B2) — the date-block length of the binding bootstrap: outcomes overlap for up to the 10-session primary horizon

# B6 — the three pre-registered verdict cells, in served order. Every other
# cell is exploratory.
VERDICT_CELLS = ("primary", "any_read", "test_no_doji")
ROLE_VERDICT = "verdict"
EXPLORATORY_LABEL = "exploratory — no verdict"
ROLES = (ROLE_VERDICT, EXPLORATORY_LABEL)
# The verdict values a verdict cell may carry (W31 words in doji_sweep_tab).
VERDICTS = ("separates", "no_signal", "inverted", "too_small", "axes_disagree")

# B4 — pre-declared too small before the run (69 events on 59 dates in the
# critic's count-only probe, under MIN_CELL_EVENTS): served with its count as
# "too small", never a verdict word.
PREDECLARED_TOO_SMALL = ("w52_70",)
# The cells the pasted literal carries beside `primary` (the two other verdict
# cells first, then the exploratory cells the ℹ️ section may quote).
SERVED_CELLS = ("any_read", "test_no_doji", "w52_70", "ath_60", "mas", "doji10",
                "undercut_reclaimed", "swing_sweep")

ARTIFACT_KEYS = ("study", "schema", "script", "prereg", "prereg_commit", "prereg_blob", "smoke",
                 "count_only", "run_date", "as_of", "universe_n", "n_names_with_bars",
                 "n_names_eligible", "first_session", "last_session", "n_sessions", "ath_basis",
                 "definitions", "primary", "cells", "baselines", "limits", "runtime_sec",
                 "phase_sec", "attempted_writes", "provider_calls", "git")
# B12 — the artifact's `git` block, exactly.
GIT_KEYS = ("head", "porcelain_empty", "script_blob", "detector_blob", "measured_blob",
            "prereg_blob", "source")
CELL_KEYS = ("label", "definition", "role", "verdict", "ci_pct", "p_holm", "horizon", "entry",
             "n_events", "n_dates", "n_symbols", "n_detected", "n_blocks", "n_placebo", "n_unmatched",
             "placebo_short_pool", "event_median_pct",
             "placebo_median_pct", "median_diff_pp", "ci_block", "ci_date", "ci_symbol", "robust",
             "adj_event_median_pct", "adj_placebo_median_pct", "adj_median_diff_pp",
             "adj_ci_block", "adj_ci_symbol", "event_mean_pct", "placebo_mean_pct",
             "mean_diff_pp", "ci_mean_block", "net_mean_pct", "confirm_pct",
             "placebo_confirm_pct", "confirm_diff_pp", "ci_confirm_block", "stop_pct",
             "placebo_stop_pct", "mfe_median_pct", "mae_median_pct", "by_horizon")
COUNT_CELL_KEYS = ("label", "definition", "role", "n_events", "n_dates", "n_symbols")   # smoke / count-only: NO outcome key
HORIZON_KEYS = ("n_events", "event_median_pct", "placebo_median_pct", "median_diff_pp", "ci_block",
                "adj_median_diff_pp", "adj_ci_block")
BASELINE_KEYS = ("n_days", "n_dates", "median_pct", "mean_pct")
LITERAL_TOP_KEYS = ("status", "schema", "script", "artifact", "prereg", "prereg_commit",
                    "prereg_blob", "run_date", "as_of", "first_session", "last_session", "cohort",
                    "cost_round_trip_pct", "confirm_sessions", "block_sessions", "primary", "cells")
LITERAL_PRIMARY_KEYS = ("role", "verdict", "ci_pct", "p_holm", "horizon", "entry", "n_events",
                        "n_dates", "n_symbols", "n_detected", "n_blocks", "n_placebo", "n_unmatched", "placebo_short_pool",
                        "event_median_pct", "placebo_median_pct", "median_diff_pp",
                        "ci_block", "ci_symbol", "robust", "adj_event_median_pct",
                        "adj_placebo_median_pct", "adj_median_diff_pp", "adj_ci_block",
                        "adj_ci_symbol", "event_mean_pct", "placebo_mean_pct", "ci_mean_block",
                        "net_mean_pct", "confirm_pct", "placebo_confirm_pct", "ci_confirm_block",
                        "stop_pct", "placebo_stop_pct")
# An exploratory literal cell: numbers only — no verdict key (B6).
LITERAL_CELL_KEYS = ("role", "n_events", "n_dates", "median_diff_pp", "ci_block", "ci_symbol",
                     "adj_median_diff_pp", "adj_ci_block", "adj_ci_symbol")
# A verdict literal cell (VERDICT_CELLS[1:]): the exploratory keys + the
# verdict, the CI level it used and the Holm-adjusted p.
LITERAL_VERDICT_CELL_KEYS = LITERAL_CELL_KEYS[:1] + ("verdict", "ci_pct", "p_holm") + LITERAL_CELL_KEYS[1:]


def literal_cell_keys(key: str) -> tuple:
    """The exact keys of the literal's `cells[key]` — a verdict cell's or an
    exploratory cell's (B6)."""
    return LITERAL_VERDICT_CELL_KEYS if key in VERDICT_CELLS else LITERAL_CELL_KEYS


MEASURED = {
    "status": "measured",
    "schema": 1,
    "script": "backend/scripts/doji_sweep_study.py",
    "artifact": "backend/scripts/doji_sweep_measured.json",
    "prereg": "docs/research/doji_sweep_study_2026_10_16.md",
    "prereg_commit": "2845fe2458bdead69d1db1c2b96245e80f4d6b06",
    "prereg_blob": "77cd374b966631fbb95bc9e60231e912bff76c3b",
    "run_date": "2026-10-16",
    "as_of": "2026-10-15",
    "first_session": "2025-10-10",
    "last_session": "2026-10-15",
    "cohort": "survivors-only",
    "cost_round_trip_pct": 0.5,
    "confirm_sessions": 5,
    "block_sessions": 10,
    "primary": {
        "role": "verdict",
        "verdict": "no_signal",
        "ci_pct": 98.33,
        "p_holm": 0.129,
        "horizon": 10,
        "entry": "next_open",
        "n_events": 145,
        "n_dates": 98,
        "n_symbols": 102,
        "n_detected": 168,
        "n_blocks": 24,
        "n_placebo": 770,
        "n_unmatched": 14,
        "placebo_short_pool": 13,
        "event_median_pct": -2.9,
        "placebo_median_pct": 0.2,
        "median_diff_pp": -3.1,
        "ci_block": [
            -7.62,
            2.4
        ],
        "ci_symbol": [
            -7.51,
            1.9
        ],
        "robust": True,
        "adj_event_median_pct": -3.32,
        "adj_placebo_median_pct": 0.54,
        "adj_median_diff_pp": -3.85,
        "adj_ci_block": [
            -7.23,
            0.72
        ],
        "adj_ci_symbol": [
            -6.41,
            0.68
        ],
        "event_mean_pct": -0.63,
        "placebo_mean_pct": 1.72,
        "ci_mean_block": [
            -6.55,
            2.46
        ],
        "net_mean_pct": -1.13,
        "confirm_pct": 46.36,
        "placebo_confirm_pct": 47.68,
        "ci_confirm_block": [
            -11.78,
            8.4
        ],
        "stop_pct": 78.62,
        "placebo_stop_pct": 66.76
    },
    "cells": {
        "any_read": {
            "role": "verdict",
            "verdict": "axes_disagree",
            "ci_pct": 97.5,
            "p_holm": 0.612,
            "n_events": 2802,
            "n_dates": 242,
            "median_diff_pp": -0.38,
            "ci_block": [
                -1.48,
                0.82
            ],
            "ci_symbol": [
                -0.74,
                -0.02
            ],
            "adj_median_diff_pp": -0.5,
            "adj_ci_block": [
                -1.75,
                0.68
            ],
            "adj_ci_symbol": [
                -0.89,
                -0.13
            ]
        },
        "test_no_doji": {
            "role": "verdict",
            "verdict": "no_signal",
            "ci_pct": 95.0,
            "p_holm": 0.832,
            "n_events": 2563,
            "n_dates": 241,
            "median_diff_pp": 0.96,
            "ci_block": [
                -2.12,
                4.13
            ],
            "ci_symbol": [
                -0.87,
                2.97
            ],
            "adj_median_diff_pp": 0.17,
            "adj_ci_block": [
                -2.07,
                2.88
            ],
            "adj_ci_symbol": [
                -1.09,
                2.0
            ]
        },
        "w52_70": {
            "role": "exploratory — no verdict",
            "n_events": 53,
            "n_dates": 47,
            "median_diff_pp": -1.36,
            "ci_block": [
                -5.94,
                3.7
            ],
            "ci_symbol": [
                -7.17,
                4.59
            ],
            "adj_median_diff_pp": -1.98,
            "adj_ci_block": [
                -5.84,
                1.35
            ],
            "adj_ci_symbol": [
                -6.92,
                2.98
            ]
        },
        "ath_60": {
            "role": "exploratory — no verdict",
            "n_events": 1027,
            "n_dates": 235,
            "median_diff_pp": -0.41,
            "ci_block": [
                -1.7,
                0.81
            ],
            "ci_symbol": [
                -1.19,
                0.16
            ],
            "adj_median_diff_pp": -0.73,
            "adj_ci_block": [
                -1.75,
                0.28
            ],
            "adj_ci_symbol": [
                -1.25,
                -0.11
            ]
        },
        "mas": {
            "role": "exploratory — no verdict",
            "n_events": 2359,
            "n_dates": 241,
            "median_diff_pp": -0.46,
            "ci_block": [
                -1.55,
                0.84
            ],
            "ci_symbol": [
                -0.8,
                -0.09
            ],
            "adj_median_diff_pp": -0.47,
            "adj_ci_block": [
                -1.67,
                0.66
            ],
            "adj_ci_symbol": [
                -0.88,
                -0.12
            ]
        },
        "doji10": {
            "role": "exploratory — no verdict",
            "n_events": 5578,
            "n_dates": 242,
            "median_diff_pp": -0.31,
            "ci_block": [
                -1.39,
                0.84
            ],
            "ci_symbol": [
                -0.56,
                -0.04
            ],
            "adj_median_diff_pp": -0.34,
            "adj_ci_block": [
                -1.41,
                0.65
            ],
            "adj_ci_symbol": [
                -0.6,
                -0.09
            ]
        },
        "undercut_reclaimed": {
            "role": "exploratory — no verdict",
            "n_events": 237,
            "n_dates": 126,
            "median_diff_pp": -1.34,
            "ci_block": [
                -2.94,
                0.48
            ],
            "ci_symbol": [
                -2.62,
                0.21
            ],
            "adj_median_diff_pp": -0.52,
            "adj_ci_block": [
                -1.91,
                0.95
            ],
            "adj_ci_symbol": [
                -1.77,
                0.88
            ]
        },
        "swing_sweep": {
            "role": "exploratory — no verdict",
            "n_events": 2386,
            "n_dates": 242,
            "median_diff_pp": -0.44,
            "ci_block": [
                -1.62,
                0.97
            ],
            "ci_symbol": [
                -0.86,
                -0.07
            ],
            "adj_median_diff_pp": -0.29,
            "adj_ci_block": [
                -1.35,
                0.86
            ],
            "adj_ci_symbol": [
                -0.76,
                0.13
            ]
        }
    }
}


def load() -> dict:
    """The literal (a copy), or the placeholder when it is not a dict."""
    return dict(MEASURED) if isinstance(MEASURED, dict) else {"state": "unmeasured"}
