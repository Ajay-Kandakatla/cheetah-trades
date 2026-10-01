"""🧱 ZONE PAD — the measurement, in exactly ONE place (2026-09-30).

Ajay 2026-09-30, verbatim:
  "Also increase our Demand zone and key levels sizes by 1%. becuz Generally we are
   missing this, I been noticing if the demand zone or key level is 133, it holding at
   132. My theory is MMs know stoplosses are beyond 133."

The pad itself lives in `supply_demand/level_pad.py` (his rule, configured). This module
says whether the pad was ever MEASURED to pay: padded stop vs drawn-edge stop, real levels
minus random (placebo) levels, date-clustered 95% CI.

STATUS TODAY: **pending**. `MEASURED = None`. The replay
(`backend/scripts/zone_pad_study_2026_09_30.py`) has not reported yet.

HOW THIS FILE GETS ITS NUMBER. Run the study's `--stage stats --emit-measured` and paste the
emitted `MEASURED = {...}` literal in here verbatim, beside the JSON it wrote
(`backend/scripts/zone_pad_measured.json`). Never hand-edit a number, never round one, never
quote a point estimate without the CI that came with it.
"""
from __future__ import annotations

from typing import Optional

STATUS_SUPPORTS = "supports"
STATUS_NO_SIGNAL = "no_signal"
STATUS_INVERTED = "inverted"
STATUS_PENDING = "pending"

PENDING_NOTE = "The 1% pad is his rule, UNMEASURED — no study here says it pays."

# ── the measurement, pasted verbatim from --emit-measured (none yet) ────────
MEASURED: Optional[dict] = None

_KNOWN = (STATUS_SUPPORTS, STATUS_NO_SIGNAL, STATUS_INVERTED)


def status() -> str:
    m = MEASURED
    if not isinstance(m, dict):
        return STATUS_PENDING
    s = m.get("status")
    return s if s in _KNOWN else STATUS_PENDING


def verdict_line() -> str:
    """One sentence for every surface; built only from MEASURED keys."""
    st = status()
    if st == STATUS_PENDING:
        return PENDING_NOTE
    m = MEASURED or {}
    try:
        return ("MEASURED {run_date}: {status} — padded stop vs drawn-edge stop, real levels "
                "minus random levels: {d:+.2f}% per trade [{lo:+.2f}, {hi:+.2f}], {n} trades "
                "over {dates} dates.").format(
            run_date=m["run_date"], status=st, d=float(m["did_pct"]),
            lo=float(m["did_ci_lo"]), hi=float(m["did_ci_hi"]),
            n=int(m["n_trades"]), dates=int(m["n_dates"]))
    except (KeyError, TypeError, ValueError):
        return PENDING_NOTE
