"""🕯️ Doji Sweep — the pre-registered study's verdict literal (2026-10-16).

Ajay 2026-10-16, verbatim: "create me a new tab for Doji candle after a sweep.
For any stocks after a down trend. May be from all chart maps especially on the
60% 70% down stocks" — and K1: "I heard but do some research and back test
please on accuracy".

`doji_sweep_tab.study_block()` reads MEASURED lazily. Until the study runs the
literal is the placeholder and every served line says UNMEASURED.

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


MEASURED = {"state": "unmeasured"}


def load() -> dict:
    """The literal (a copy), or the placeholder when it is not a dict."""
    return dict(MEASURED) if isinstance(MEASURED, dict) else {"state": "unmeasured"}
