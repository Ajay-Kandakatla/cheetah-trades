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

MEASURED = {"state": "unmeasured"}


def load() -> dict:
    """The literal (a copy), or the placeholder when it is not a dict."""
    return dict(MEASURED) if isinstance(MEASURED, dict) else {"state": "unmeasured"}
