"""🧱 ZONE PAD — the measurement, in exactly ONE place (2026-09-30).

Ajay 2026-09-30, verbatim:
  "Also increase our Demand zone and key levels sizes by 1%. becuz Generally we are
   missing this, I been noticing if the demand zone or key level is 133, it holding at
   132. My theory is MMs know stoplosses are beyond 133."

The pad itself lives in `supply_demand/level_pad.py` (his rule, configured). This module
says whether the pad was ever MEASURED to pay: padded stop vs drawn-edge stop, real levels
minus random (placebo) levels, date-clustered 95% CI.

STATUS: **no_signal** (run 2026-10-01 after 20:00 ET in a throwaway read-only container,
529 s, on main 59c5b09e). Padded stop vs drawn-edge stop, real minus random levels:
+0.05% per trade [-0.07, +0.16], 11,133 trades over 190 dates. Artifact
`backend/scripts/zone_pad_measured.json`; every secondary read is in its `q1`-`q3b`.

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

# ── the measurement, pasted verbatim from --emit-measured ──────────────────
MEASURED: Optional[dict] = {'run_date': '2026-10-01',
 'status': 'no_signal',
 'did_pct': 0.04842892692819109,
 'did_ci_lo': -0.07456699089467633,
 'did_ci_hi': 0.15856239180230458,
 'n_trades': 11133,
 'n_dates': 190,
 'clock': 20,
 'placebo_accept_pct': 43.23830977163275,
 'arm_a_win': 25.555382942364457,
 'arm_a_stop': 73.81544197607582,
 'arm_a_mean_R': 0.29642583013031926,
 'arm_b_win': 32.511263010719276,
 'arm_b_stop': 66.38962249495106,
 'arm_b_mean_R': 0.222577519913571,
 'pad_pct': 1.0,
 'universe': 'store',
 'first_date': '2025-10-02',
 'last_date': '2026-07-07',
 'script': 'backend/scripts/zone_pad_study_2026_09_30.py'}

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
