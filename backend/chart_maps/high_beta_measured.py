"""🎢 High Beta tab — the down-day study's verdict literal (2026-10-14).

`chart_maps.high_beta_tab.study_block()` reads `MEASURED` lazily and turns it
into the served line. Until the study has run, the literal is the placeholder
below and the served note says UNMEASURED.

HOW IT CHANGES (never by hand-typing numbers):
  1. the prereg `docs/research/high_beta_2026_10_14_prereg.md` is committed;
  2. `backend/scripts/high_beta_study.py --prereg-commit <hash>` runs in a
     THROWAWAY container outside 09:00–16:30 ET and writes
     `backend/scripts/high_beta_measured.json`;
  3. the literal below is replaced by `high_beta_study.measured_literal(<that
     JSON>)` pasted verbatim — `tests/test_high_beta_study.py` pins it
     field-for-field to the JSON, so a hand edit fails the suite.
"""

MEASURED = {
    "status": "measured",
    "script": "backend/scripts/high_beta_study.py",
    "artifact": "backend/scripts/high_beta_measured.json",
    "run_date": "2026-10-14",
    "as_of": "2026-10-14",
    "prereg_commit": "80c5f516",
    "cohort": "survivors-only",
    "primary": {
        "verdict": "no_signal",
        "horizon": 3,
        "contrast_pp": 0.16,
        "ci": [
            -0.45,
            0.82
        ],
        "ci_session_only": [
            -0.39,
            0.77
        ],
        "n_sessions": 244,
        "n_cohort": 12998,
        "n_placebo": 121851,
        "cohort_mean_pct": 0.76,
        "placebo_mean_pct": 0.27,
        "mae_mean_pct": -6.2,
        "drawdown_share_pct": 52.7
    },
    "h1": {
        "verdict": "no_signal",
        "contrast_pp": 0.1,
        "ci": [
            -0.17,
            0.36
        ],
        "n_sessions": 244
    },
    "h5": {
        "verdict": "no_signal",
        "contrast_pp": 0.31,
        "ci": [
            -0.41,
            1.1
        ],
        "n_sessions": 244
    },
    "mfe3": {
        "verdict": "separates",
        "contrast_pp": 1.43,
        "ci": [
            0.91,
            1.95
        ],
        "n_sessions": 244
    },
    "spy_red": {
        "verdict": "no_signal",
        "contrast_pp": 0.33,
        "ci": [
            -0.46,
            1.15
        ],
        "n_sessions": 115
    },
    "spy_green": {
        "verdict": "no_signal",
        "contrast_pp": -0.36,
        "ci": [
            -1.18,
            0.5
        ],
        "n_sessions": 129
    },
    "b20": {
        "verdict": "no_signal",
        "contrast_pp": 0.09,
        "ci": [
            -0.73,
            0.99
        ],
        "n_sessions": 240
    },
    "top20": {
        "verdict": "no_signal",
        "contrast_pp": 0.19,
        "ci": [
            -0.44,
            0.85
        ],
        "n_sessions": 244
    },
    "sigma_matched": {
        "verdict": "no_signal",
        "contrast_pp": 0.18,
        "ci": [
            -0.42,
            0.79
        ],
        "n_sessions": 244
    },
    "leave_top5": {
        "verdict": "no_signal",
        "contrast_pp": -0.22,
        "ci": [
            -0.74,
            0.33
        ],
        "n_sessions": 239
    }
}


def load() -> dict:
    """The literal (a copy), or the placeholder when it is not a dict."""
    return dict(MEASURED) if isinstance(MEASURED, dict) else {"state": "unmeasured"}
