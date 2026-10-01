"""🧱 LEVEL PAD (Ajay 2026-09-30) — the stop-side pad under demand floors and support key levels.

His ask, verbatim: "Also increase our Demand zone and key levels sizes by 1%. becuz Generally we are
missing this, I been noticing if the demand zone or key level is 133, it holding at 132. My theory is
MMs know stoplosses are beyond 133."

THE ONE NUMBER is the house stop shelf, reused by name: sd_liquidity.STOP_SHELF_PCT ("where the stops
actually sit, as a band under the zone floor"). Drawn band edges and key-level prices NEVER move in any
payload; every SUPPORT decision reads support_floor(band) / key_edge(...). Resistance reads, dedupe keys,
the drawn band and the measured floor-held gate keep the drawn edge.

Configured house rule (his), NOT a book method, NOT measured until scripts/zone_pad_study_2026_09_30.py
reports (supply_demand/zone_pad_measured.py). Decision support, not advice.
"""
from __future__ import annotations

import math
from typing import Optional

from supply_demand import sd_liquidity as SL

DEMAND_PAD_PCT = SL.STOP_SHELF_PCT   # his 1%; 0 = pad OFF everywhere (the kill switch)
PAD_BAND_KINDS = ("demand",)         # HIS CALL #2 — band origins padded (broken-supply shelves are not)
PAD_KEY_KINDS = ("low",)             # HIS CALL #3 — key-level kinds padded when on the support side
PAD_FLOOR_HELD = False               # HIS CALL #1 — the measured floor-held gate reads the DRAWN floor
BAND_DP = 2                          # price_zones rounds band edges to 2 dp (_make_zone)
LEVEL_DP = 4                         # key_levels rounds members to 4 dp (_member)


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def pad_pct() -> float:
    p = _f(DEMAND_PAD_PCT)
    return p if p is not None and p > 0 else 0.0


def padded(edge, ndigits: int = BAND_DP, pct: Optional[float] = None) -> Optional[float]:
    """edge x (1 - pad%) rounded; the edge itself (unrounded) when the pad is 0; None for garbage."""
    e = _f(edge)
    if e is None or e <= 0:
        return None
    p = pad_pct() if pct is None else max(0.0, _f(pct) or 0.0)
    if p <= 0:
        return e
    return round(e * (1.0 - p / 100.0), ndigits)


def band_kind(band) -> str:
    """alert_gates._kind's convention: a band with no kind is demand."""
    if not isinstance(band, dict):
        return ""
    return str(band.get("kind") or "demand").lower()


def is_padded(band) -> bool:
    lo = _f(band.get("lo")) if isinstance(band, dict) else None
    return pad_pct() > 0 and band_kind(band) in PAD_BAND_KINDS and lo is not None and lo > 0


def support_floor(band) -> Optional[float]:
    """The floor every SUPPORT decision reads: the drawn lo, padded for a demand band."""
    if not isinstance(band, dict):
        return None
    lo = _f(band.get("lo"))
    if lo is None or lo <= 0:
        return None
    return padded(lo) if is_padded(band) else lo


def in_band(band, px) -> bool:
    fl = support_floor(band)
    hi = _f(band.get("hi")) if isinstance(band, dict) else None
    p = _f(px)
    return fl is not None and hi is not None and p is not None and fl <= p <= hi


def under_floor(band, px) -> bool:
    fl, p = support_floor(band), _f(px)
    return fl is not None and p is not None and p < fl


def same_band(a, b) -> bool:
    """Identity at the 2-dp grain (room_floor._same_band's rule, moved here so the leaf gates can use it)."""
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    alo, blo = _f(a.get("lo")), _f(b.get("lo"))
    if alo is None or blo is None:
        return False
    ahi, bhi = _f(a.get("hi")), _f(b.get("hi"))
    return round(alo, 2) == round(blo, 2) and (ahi is None or bhi is None or round(ahi, 2) == round(bhi, 2))


def sweep_floor(band) -> Optional[float]:
    """The floor the MEASURED floor-held gate reads: the DRAWN lo unless HIS CALL #1 flips it."""
    if PAD_FLOOR_HELD:
        return support_floor(band)
    lo = _f(band.get("lo")) if isinstance(band, dict) else None
    return lo if lo is not None and lo > 0 else None


def pad_fields(band) -> dict:
    """{"pad_lo", "pad_pct"} for a padded band (drawing + ladder); {} otherwise. Never touches lo/hi."""
    if not is_padded(band):
        return {}
    return {"pad_lo": support_floor(band), "pad_pct": pad_pct()}


def proximity_text(max_above_pct) -> str:
    """The served words of alert_gates.demand_proximity_gate, built from the LIVE pad so a
    rules panel can never contradict the gate: 'padded floor band.lo x (1 - 1%) <= print <=
    band.hi x (1 + 1%)'; with the pad off, today's 'band.lo <= print <= …'."""
    p = pad_pct()
    floor = "padded floor band.lo x (1 - %g%%)" % p if p > 0 else "band.lo"
    return "%s <= print <= band.hi x (1 + %g%%)" % (floor, float(max_above_pct))


def key_edge(price, kind, side) -> Optional[float]:
    """A key level's break edge: padded (4 dp) for a support-side low, the level itself otherwise."""
    L = _f(price)
    if L is None or L <= 0:
        return None
    if pad_pct() > 0 and side == "support" and str(kind or "") in PAD_KEY_KINDS:
        return padded(L, LEVEL_DP)
    return L


def describe() -> dict:
    return {"pad_pct": pad_pct(), "band_kinds": list(PAD_BAND_KINDS), "key_kinds": list(PAD_KEY_KINDS),
            "floor_held_reads_pad": bool(PAD_FLOOR_HELD), "shelf_pct": SL.STOP_SHELF_PCT}
