"""📅 Long Term — 🎯 Enterable (zones): one zone read per saved row (2026-11-14, spec ltenter §3.2). Pure, no I/O.

Ajay 2026-11-14, verbatim: "Make a enterable check box in longterm stocks with zone and filters please".

Both zone sheets the tab carries — Pankaj's (seed.pankaj_entries) and Gabbar's (catalysts.gabbar_levels.get_bands,
already split-adjusted) — are read by the ONE engine the tab already uses: `sepa.pankaj_picks.setup_status` (the
/pankaj page's padded in-zone test; criteria.zone_read is its sibling). Only its state + dist_pct are read.

  inside = within the engine's pad (C.PANKAJ_ZONE_PAD_PCT is the same number) of a band;
  near   = above a band's top by at most C.ENTERABLE_ABOVE_PCT (his demand-alert proximity, imported by name);
  else the nearest band decides above / below (not enterable).
A display filter only — it rings nothing, gates nothing and reorders nothing. UNMEASURED.
"""
from __future__ import annotations

from typing import Optional

from catalysts import gabbar_levels as GL
from sepa import pankaj_picks as PK

from . import constants as C
from . import criteria as CR
from . import seed as SD
from . import words as W


def _pair(lo, hi):
    lo, hi = CR._num(lo), CR._num(hi)
    if lo is None or hi is None or lo > hi:
        return None
    return lo, hi


def pankaj_bands(ent, order) -> list:
    """Pankaj's zones in zone order; a None / unreadable / inverted pair is skipped."""
    if not isinstance(ent, dict):
        return []
    zones = ent.get("zones") or {}
    out = []
    for zk in order or tuple(zones.keys()):
        pair = list(zones.get(zk) or (None, None)) + [None, None]
        p = _pair(pair[0], pair[1])
        if p is None:
            continue
        out.append({"source": "pankaj", "key": zk, "level": zk, "label": f"Pankaj {zk}", "lo": p[0], "hi": p[1]})
    return out


def gabbar_bands(sym) -> list:
    """Gabbar's bands in get_bands order (top band first, already ÷ the verified split ratio). The filter `level` comes
    from the band INDEX: below C.GABBAR_DEEP_FROM a band keeps its own label, from it on it folds into
    C.GABBAR_DEEP_LEVEL_KEY. No label is typed here."""
    g = GL.get_bands(sym) if isinstance(sym, str) and sym else None
    out = []
    for i, b in enumerate((g or {}).get("bands") or []):
        if not isinstance(b, dict):
            continue
        p = _pair(b.get("lo"), b.get("hi"))
        label = b.get("label")
        if p is None or not isinstance(label, str):
            continue
        level = label if i < C.GABBAR_DEEP_FROM else C.GABBAR_DEEP_LEVEL_KEY
        out.append({"source": "gabbar", "key": label, "level": level, "label": f"Gabbar {label}",
                    "lo": p[0], "hi": p[1]})
    return out


def gabbar_text(sym) -> Optional[str]:
    g = GL.get_bands(sym) if isinstance(sym, str) and sym else None
    if g and g.get("bands"):
        return W.gabbar_text(C.GABBAR_SNAPSHOT_DATE, g.get("split_adjusted"), g.get("split_date"))
    if isinstance(sym, str) and sym.upper() in GL.TRACKED_NO_LEVELS:
        return W.gabbar_tracked_text(sym.upper())
    return None


def bands_for(sym, ent, order) -> list:
    return pankaj_bands(ent, order) + gabbar_bands(sym)


def band_state(band, price) -> tuple:
    """("in", 0.0) | ("above", dist) | ("below", dist) — the engine's own state and dist_pct (1 dp, signed)."""
    st = PK.setup_status({"kind": "pullback", "zone": {"lo": band["lo"], "hi": band["hi"]}}, float(price))
    state = st.get("state")
    if state == "in_zone":
        return "in", 0.0
    if state == "above_zone":
        return "above", st.get("dist_pct")
    return "below", st.get("dist_pct")


def _price(price) -> Optional[float]:
    px = CR._num(price)
    return px if px is not None and px > 0 else None


def read(bands, price, date, basis="close") -> dict:
    """The zone read of one price against a row's bands. No bands is checked FIRST (no_zone whatever the price),
    then no price (None / NaN / ≤ 0) → no_price. `date` is served as it came in (ISO); the text prints mmdd(date)."""
    px = _price(price)
    base = {"basis": basis, "price": px, "date": date}
    if not bands:
        return {**base, "state": "no_zone", "enterable": None, "band": None, "pct": None,
                "text": W.zone_cell_text("no_zone", None, None, basis, date)}
    if px is None:
        return {**base, "state": "no_price", "enterable": None, "band": None, "pct": None,
                "text": W.zone_cell_text("no_price", None, None, basis, date)}
    states = [(b,) + band_state(b, px) for b in bands]
    pick = next(((b, "inside", 0.0) for b, st, _ in states if st == "in"), None)
    if pick is None:
        near = None
        for b, st, pct in states:
            if st == "above" and pct is not None and pct <= C.ENTERABLE_ABOVE_PCT and (near is None or pct < near[2]):
                near = (b, "near", pct)
        pick = near
    if pick is None:
        best = None
        for b, st, pct in states:
            if pct is None:
                continue
            if best is None or abs(pct) < abs(best[2]):
                best = (b, "above" if st == "above" else "below", pct)
        pick = best
    if pick is None:
        return {**base, "state": "no_price", "enterable": None, "band": None, "pct": None,
                "text": W.zone_cell_text("no_price", None, None, basis, date)}
    band, state, pct = pick
    return {**base, "state": state, "enterable": state in ("inside", "near"), "band": dict(band), "pct": pct,
            "text": W.zone_cell_text(state, band, pct, basis, date)}


def row_block(sym, ent, order, close) -> dict:
    """The served `zone` block of one saved row. `close` is None for a name the closes read did not cover."""
    close = close if isinstance(close, dict) else {}
    bands = bands_for(sym, ent, order)
    return {"bands": bands, "gabbar_text": gabbar_text(sym),
            "close": read(bands, close.get("close"), close.get("date"))}


def gabbar_level_keys(seed) -> tuple:
    """Ordered unique Gabbar `level` keys over the saved names (seed order, band order) — derived from the bands."""
    out = []
    for sym in SD.unique_names(seed):
        for b in gabbar_bands(sym):
            if b["level"] not in out:
                out.append(b["level"])
    return tuple(out)


def zone_symbols(seed) -> list:
    """Every saved symbol with at least one band on either sheet, seed order."""
    pk = SD.pankaj_entries(seed)
    order = SD.zone_order(seed)
    return [s for s in SD.unique_names(seed) if bands_for(s, pk.get(s), order)]


def rules_block(order, seed) -> dict:
    return {"pad_pct": C.PANKAJ_ZONE_PAD_PCT, "above_pct": C.ENTERABLE_ABOVE_PCT,
            "snapshot_date": C.GABBAR_SNAPSHOT_DATE, "ls_key": C.ZONE_FILTER_LS_KEY, "text": W.ZONE_RULES_TEXT,
            "sources": W.zone_sources(), "levels": W.zone_levels(order, gabbar_level_keys(seed)),
            "reasons": W.zone_reasons(), "words": dict(W.ZONE_WORDS)}
