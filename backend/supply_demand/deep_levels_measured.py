"""DEEP DEMAND LEVELS — the measurement, in exactly ONE place.

Ajay 2026-09-16, verbatim:
  "For the deep demand stocks I need the logic to be, the stocks that crosses
   the first level of support and lying in second or third level of support.
   Like CRDO dropped after the earning it crossed multiple support level."

The Deep Demand read (`supply_demand/deep_demand.py`) now walks the served
demand window and reports `levels_broken` / `level`. This module says whether
that DEPTH — and the band-quality gate applied to the ARRIVAL band — was ever
MEASURED to separate an outcome.

STATUS TODAY: **pending**. `MEASURED = None`. The replay
(`backend/scripts/deep_levels_study.py`) has not been run on the full universe
yet, so nothing on any board may order on depth, gate on depth, badge depth as
good, or imply a deeper arrival is a better one. A `pending` dict and a
`no_signal` dict must read IDENTICALLY at every call site.

THE PRIOR IS NULL, and it is not this file's job to soften that: the
2026-09-16 `band_structure` study came back `no_signal` on the adjacent claim
("a second band below catches the name"), and a BIGGER first support band
measured HARMFUL (`supply_demand/band_structure.py`, `docs/supply_demand/
band_structure.md`). So the honest default while this is pending is the same
sentence the board prints either way.

HOW THIS FILE GETS ITS NUMBER. Run the study's `--stage stats --emit-measured`
and paste the emitted `MEASURED = {...}` literal in here verbatim, beside the
JSON it wrote (`backend/scripts/deep_levels_measured.json`). Never hand-edit a
number, never round one, never quote a point estimate without the CI that came
with it (Rule: ship the backtest with the claim).
"""
from __future__ import annotations

from typing import Optional

STATUS_SEPARATES = "separates"
STATUS_NO_SIGNAL = "no_signal"
STATUS_PENDING = "pending"

# The one sentence a surface prints while nothing has been measured. The board
# imports this rather than carrying its own copy; the wording is deliberately
# flat — it must not hint that a measurement is expected to come back positive.
NOT_MEASURED_NOTE = "Depth is NOT measured yet — levels order nothing and gate nothing."

# ── the measurement, pasted verbatim from --emit-measured ───────────────────
MEASURED: Optional[dict] = None


def status() -> str:
    """`separates` | `no_signal` | `pending`. A missing or malformed MEASURED
    is PENDING — never silently `no_signal`, and never `separates`."""
    if not isinstance(MEASURED, dict):
        return STATUS_PENDING
    s = str(MEASURED.get("status") or "").strip().lower()
    if s in (STATUS_SEPARATES, STATUS_NO_SIGNAL, STATUS_PENDING):
        return s
    return STATUS_PENDING


def separates() -> bool:
    """True ONLY for a quotable run that came back `separates`. Anything else —
    pending, no_signal, a smoke run, a run with no survivorship replay — is
    False, so a caller that asks "may I order on this?" fails closed."""
    return status() == STATUS_SEPARATES and bool((MEASURED or {}).get("quotable"))


def quotable() -> bool:
    """Whether the run behind MEASURED may be quoted at all (full universe, no
    --stride / --names subsample, survivorship replay in hand)."""
    return bool(isinstance(MEASURED, dict) and MEASURED.get("quotable"))


def note() -> str:
    """The sentence a board note ends with. Pending and no_signal read the
    same; a `separates` run still only quotes its own status, never a promise."""
    st = status()
    if st == STATUS_SEPARATES and quotable():
        return "Depth measured %s on %s — see docs/supply_demand/deep_levels_study.md." % (
            st, (MEASURED or {}).get("run_date") or "an unnamed run")
    return NOT_MEASURED_NOTE
