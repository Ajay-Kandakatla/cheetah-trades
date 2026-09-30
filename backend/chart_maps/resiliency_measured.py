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
"""

MEASURED = {
    "status": "pending",
    "script": "backend/scripts/resiliency_study.py",
    "artifact": "backend/scripts/resiliency_measured.json",
}
