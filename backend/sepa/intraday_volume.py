"""Intraday volume projection — extrapolate today's partial-session volume to
a full-session estimate HONESTLY, accounting for the fact that intraday volume
is front-loaded (heavy at the open), not uniform across the session.

WHY THIS EXISTS — CGNX, 2026-06-22. The Auto-Pilot intraday entry gate
projected the full day's volume as ``today_volume / session_fraction`` — a
LINEAR extrapolation that assumes volume accrues evenly through the day. It
does not: the opening drive is the heaviest part of the session, so early on
``today_volume / session_fraction`` massively OVER-projects. CGNX cleared its
pivot on an opening burst, read a fake ~2x projected RelVol at ~10am, the
engine bought it, and it faded to 0.72x of average by the close (below the
21-day high) — a textbook failed breakout the engine should never have taken.

BOOK BASIS:
  - TLSW p.229, "Extrapolating Volume Intraday": judge the day's volume by
    projecting it PROPERLY — a hot open does not guarantee a hot day, because
    the morning trades heavier. Do not assume the current pace holds flat.
  - TLSW p.203: the volume-confirmation bar itself (a breakout wants volume
    well above average, ~1.5x); that threshold lives in the engine
    (auto_entry.AUTO_RELVOL_MIN), unchanged.

The CURVE below is NOT a Minervini number. It is a standard, well-documented
property of U.S. equity intraday volume (heavy at the open, light midday). It
is encoded as an empirical, owner-tunable default and is CONSERVATIVE by
construction: ``expected_session_volume_fraction(f) >= f`` for every f in
(0, 1), so the curve-projected full-day volume is always <= the old linear
projection — never MORE permissive — and converges to the true full-day RelVol
at the close (f = 1). Pure stdlib; host-runnable, unit-tested without pandas.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

# (fraction of the 9:30-16:00 session elapsed, typical share of the full day's
# volume already done by then). Front-loaded: ~13% of daily volume in the first
# ~30 min (frac 0.077), ~21% by the first hour, ~55% by midday. Anchors trace a
# typical US-equity profile; linearly interpolated, monotonic non-decreasing,
# and >= the diagonal everywhere in (0,1) so projection is never over-credited.
# Empirical engineering default (owner-tunable) — NOT a book formula.
_CURVE: List[Tuple[float, float]] = [
    (0.000, 0.000),
    (0.077, 0.130),   # ~first 30 min
    (0.154, 0.210),   # ~first hour
    (0.300, 0.360),
    (0.500, 0.550),   # midday
    (0.750, 0.780),
    (0.900, 0.920),
    (1.000, 1.000),
]


def expected_session_volume_fraction(session_fraction: float) -> float:
    """Typical share of a full day's volume completed by ``session_fraction``
    of the regular session. Piecewise-linear over ``_CURVE``, clamped to
    [0, 1], monotonic non-decreasing, and >= ``session_fraction`` for every
    value in (0, 1).

    Because it is >= the raw elapsed fraction, dividing today's cumulative
    volume by THIS (instead of by the raw fraction) never over-projects a hot
    open the way ``today_volume / session_fraction`` does. Pure function."""
    f = session_fraction
    if f <= 0.0:
        return 0.0
    if f >= 1.0:
        return 1.0
    for (x0, y0), (x1, y1) in zip(_CURVE, _CURVE[1:]):
        if f <= x1:
            if x1 == x0:
                return y1
            t = (f - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return 1.0


def project_full_session_volume(today_volume: Optional[float],
                                session_fraction: float) -> Optional[float]:
    """Project today's cumulative volume to a full-session estimate via the
    intraday curve (TLSW p.229). ``None`` when it can't be computed yet
    (pre-open, or no volume traded). Always <= the naive
    ``today_volume / session_fraction`` in the morning — strictly more
    conservative, so it can only ever make the entry gate HARDER to clear."""
    if not today_volume or today_volume <= 0:
        return None
    frac = expected_session_volume_fraction(session_fraction)
    if frac <= 0.0:
        return None
    return today_volume / frac


def projected_relvol(today_volume: Optional[float],
                     avg_vol_50: Optional[float],
                     session_fraction: float) -> Optional[float]:
    """Curve-aware projected RelVol = projected full-session volume / 50-day
    average volume, rounded to 2dp. ``None`` when not computable. This is the
    honest replacement for ``(today_volume / session_fraction) / avg_vol_50``
    and is the number the Auto-Pilot intraday gate reads (>= AUTO_RELVOL_MIN,
    TLSW p.203)."""
    proj = project_full_session_volume(today_volume, session_fraction)
    if proj is None or not avg_vol_50 or avg_vol_50 <= 0:
        return None
    return round(proj / avg_vol_50, 2)
