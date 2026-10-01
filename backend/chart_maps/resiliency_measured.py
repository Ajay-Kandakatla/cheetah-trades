"""🛡️ Resiliency tab — the persistence study's verdict literal (2026-09-30).

`chart_maps.resiliency_tab.study_block()` reads `MEASURED` lazily and turns it
into the served sentences. Until the study has run, the literal is `pending`
and every served box note says UNMEASURED.

HOW IT CHANGES (never by hand-typing numbers):
  1. the prereg `docs/research/resiliency_2026_09_30_prereg.md` is committed;
  2. `backend/scripts/resiliency_study.py --prereg-commit <hash>` runs in the api
     container outside 09:00–16:30 ET and writes
     `backend/scripts/resiliency_measured.json`;
  3. the literal below is replaced by `resiliency_study.measured_literal(<that
     JSON>)` pasted verbatim — `tests/test_resiliency_study.py` pins it
     field-for-field to the JSON, so a hand edit fails the suite.

RUN 2026-10-01 (as of the 2026-09-30 close, prereg 20d84110, throwaway container,
168 s): T1 no_signal (general), T2 inverted, EOD tape no_signal, pre-market
unmeasured.
"""

MEASURED = {
    "status": "measured",
    "script": "backend/scripts/resiliency_study.py",
    "artifact": "backend/scripts/resiliency_measured.json",
    "run_date": "2026-10-01",
    "as_of": "2026-09-30",
    "prereg_commit": "20d84110",
    "t1": {
        "verdict": "no_signal",
        "specific": "general",
        "lift_pp": 4.33,
        "ci": [
            0.72,
            7.83
        ],
        "placebo_lift_pp": 2.87,
        "placebo_ci": [
            -1.28,
            7.47
        ],
        "specific_pp": 1.46,
        "specific_ci": [
            -4.53,
            7.18
        ],
        "n_events": 42
    },
    "t2": {
        "verdict": "inverted",
        "specific": "unclear",
        "lift_pp": 1.43,
        "ci": [
            -0.3,
            3.19
        ],
        "placebo_lift_pp": 4.77,
        "placebo_ci": [
            2.96,
            6.57
        ],
        "specific_pp": -3.33,
        "specific_ci": [
            -5.75,
            -1.01
        ],
        "n_events": 66
    },
    "eod": {
        "verdict": "no_signal",
        "lift_pp": 0.046,
        "ci": [
            -0.011,
            0.093
        ],
        "placebo_pct": 0.0,
        "n_days": 450
    },
    "pre": {
        "verdict": "unmeasured",
        "reason": "pre-market volume history is the intraday cache: ≤31 sessions, patchy — too short to measure"
    }
}
