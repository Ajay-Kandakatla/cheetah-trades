"""ICT rows -> Chart Maps tile geometry. PURE (no I/O).

Source for the concepts: Ajay's spec + Jesse Rogers,
https://www.youtube.com/watch?v=Q7Ryv1M7CvI. This module only DRAWS what
ict/engine.py found; it decides nothing.

The tile chart draws DAILY bars (chart_maps.board.bars_for), so every
60-minute event is placed by the ET DATE of its bar: several micro events
can share a date, and the newest per marker kind wins. Bands and lines are
prices, so they need no translation.

Legend (matches frontend PatternChart):
    bands   base    "accumulation" — the 60m range the manipulation swept
            demand  bullish FVG (60m "FVG", daily "daily FVG")
            supply  bearish FVG (same labels)
            neutral inverted FVG ("IFVG")
            demand/supply "entry" — the plan's entry zone, by bias
    lines   stop / target (plan tones), key low / key high (neutral),
            now (the last print)
    markers sweep "MANIP" — the manipulation bar
            bos   "MSS"   — the market structure shift close
            buy/sell "IFVG" — the inverted-FVG close (bullish buy, bearish sell)
"""
from __future__ import annotations

from typing import Callable, Optional

STATE_LABEL = {"accumulation": "Accumulation", "manipulation": "Manipulation",
               "confirmed": "Confirmed (MSS + FVG)", "entry": "Entry"}


def _num(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def _band(kind: str, lo, hi, label: str) -> Optional[dict]:
    lo_, hi_ = _num(lo), _num(hi)
    if lo_ is None or hi_ is None or hi_ < lo_:
        return None
    return {"kind": kind, "lo": lo_, "hi": hi_, "label": label}


def bands_for(row: dict) -> list:
    """Accumulation range, daily and 60m gaps, the entry zone."""
    out: list = []
    micro = row.get("micro") or {}
    macro = row.get("macro") or {}
    plan = row.get("plan") or {}
    bias = row.get("bias")

    acc = micro.get("accumulation") or {}
    b = _band("base", acc.get("lo"), acc.get("hi"), "accumulation")
    if b:
        out.append(b)
    for g in macro.get("fvgs") or []:
        st = g.get("status")
        if st == "inverted":
            b = _band("neutral", g.get("lo"), g.get("hi"), "IFVG (daily)")
        elif st == "filled":
            b = None
        else:
            b = _band("demand" if g.get("kind") == "bullish" else "supply",
                      g.get("lo"), g.get("hi"), "daily FVG")
        if b:
            out.append(b)
    g = micro.get("fvg") or {}
    if g:
        b = _band("demand" if g.get("kind") == "bullish" else "supply",
                  g.get("lo"), g.get("hi"), "FVG")
        if b:
            out.append(b)
    ig = micro.get("ifvg") or {}
    if ig:
        b = _band("neutral", ig.get("lo"), ig.get("hi"), "IFVG")
        if b:
            out.append(b)
    if plan:
        b = _band("demand" if bias == "bullish" else "supply",
                  plan.get("entry_lo"), plan.get("entry_hi"), "entry")
        if b:
            out.append(b)
    return out


def lines_for(row: dict) -> list:
    out: list = []
    plan = row.get("plan") or {}
    macro = row.get("macro") or {}
    stop, target = _num(plan.get("stop")), _num(plan.get("target"))
    if stop is not None:
        out.append({"price": stop, "label": f"STOP {stop:.2f}", "tone": "stop"})
    if target is not None:
        out.append({"price": target, "label": f"TARGET {target:.2f}", "tone": "target"})
    kl, kh = _num(macro.get("key_low")), _num(macro.get("key_high"))
    if kl is not None:
        out.append({"price": kl, "label": f"key low {kl:.2f}", "tone": "neutral"})
    if kh is not None:
        out.append({"price": kh, "label": f"key high {kh:.2f}", "tone": "neutral"})
    last = _num(row.get("last"))
    if last is not None:
        out.append({"price": last, "label": "now", "tone": "now"})
    return out


def markers_for(row: dict) -> list:
    """One marker per kind, dated by the ET date of the 60m bar; when
    several events share a kind (never, per row — but keep it honest) the
    newest date wins."""
    micro = row.get("micro") or {}
    bias = row.get("bias")
    cands: list = []
    m = micro.get("manipulation") or {}
    if m.get("date"):
        cands.append({"date": str(m["date"])[:10], "label": "MANIP", "kind": "sweep",
                      "price": _num(m.get("extreme"))})
    ms = micro.get("mss") or {}
    if ms.get("date"):
        cands.append({"date": str(ms["date"])[:10], "label": "MSS", "kind": "bos",
                      "price": _num(ms.get("level"))})
    ig = micro.get("ifvg") or {}
    if ig.get("date"):
        cands.append({"date": str(ig["date"])[:10], "label": "IFVG",
                      "kind": "buy" if bias == "bullish" else "sell",
                      "price": _num(ig.get("hi") if bias == "bullish" else ig.get("lo"))})
    elif row.get("state") == "entry" and (micro.get("fvg") or {}).get("date"):
        g = micro["fvg"]
        cands.append({"date": str(g["date"])[:10], "label": "ENTRY",
                      "kind": "buy" if bias == "bullish" else "sell",
                      "price": _num(g.get("hi") if bias == "bullish" else g.get("lo"))})
    newest: dict = {}
    for c in cands:
        k = c["kind"]
        if k not in newest or c["date"] > newest[k]["date"]:
            newest[k] = c
    out = [{k: v for k, v in c.items() if v is not None} for c in newest.values()]
    out.sort(key=lambda c: c["date"])
    return out


def stats_for(row: dict) -> list:
    micro = row.get("micro") or {}
    macro = row.get("macro") or {}
    plan = row.get("plan") or {}
    tapped = macro.get("tapped") or {}
    rr = _num(plan.get("rr"))
    return [
        {"k": "State", "v": STATE_LABEL.get(row.get("state"), str(row.get("state") or "—"))},
        {"k": "Grade", "v": f"{int(row.get('grade') or 0)}"},
        {"k": "R:R", "v": f"{rr:.2f}" if rr is not None else "—"},
        {"k": "Bias", "v": str(row.get("bias") or "—")},
        {"k": "Micro tf", "v": str(micro.get("tf") or "—")},
        {"k": "Tapped", "v": (f"{tapped.get('kind', '').replace('_', ' ')} "
                              f"{_num(tapped.get('price')) or 0:.2f}"
                              if tapped else "—")},
    ]


def badges_for(row: dict) -> list:
    micro = row.get("micro") or {}
    macro = row.get("macro") or {}
    out: list = []
    if micro.get("mss"):
        out.append({"text": "MSS ✓", "tone": "good"})
    if micro.get("manipulation"):
        out.append({"text": "no displacement ✓", "tone": "good"})
    if micro.get("displacement"):
        out.append({"text": f"push {micro['displacement'].get('atr_mult')} ATR + FVG ✓",
                    "tone": "good"})
    if micro.get("ifvg"):
        out.append({"text": "IFVG", "tone": "good"})
    if row.get("state") == "entry":
        out.append({"text": "at entry zone", "tone": "good"})
    if macro.get("stacked"):
        out.append({"text": "stacked consolidations", "tone": "warn"})
    tapped = macro.get("tapped") or {}
    if tapped:
        out.append({"text": f"tapped {tapped.get('kind', '').replace('_', ' ')}",
                    "tone": "muted"})
    return out


def tile_from_row(row: dict, *, href: Callable, name_for: Callable,
                  theme: Callable, metrics: Callable) -> Optional[dict]:
    sym = (row.get("symbol") or "").upper()
    if not sym:
        return None
    return {
        "symbol": sym,
        "name": row.get("name") or name_for(sym),
        "href": href(sym, "supply"),
        "bars": [],
        "bands": bands_for(row),
        "lines": lines_for(row),
        "markers": markers_for(row),
        "stats": stats_for(row),
        "why": row.get("why") or "",
        "theme": theme(sym),
        "badges": badges_for(row),
        "state": row.get("state"),
        "bias": row.get("bias"),
        "grade": row.get("grade"),
        "plan": row.get("plan"),
        "_score": float(row.get("grade") or 0),
        "_m": metrics(row),
    }


def tiles_from_rows(rows: list, *, bias: str = "all", href: Optional[Callable] = None,
                    name_for: Optional[Callable] = None, theme: Optional[Callable] = None,
                    metrics: Optional[Callable] = None) -> list:
    """Rows (already state/grade sorted by the engine) -> tiles, in order.
    `bias` all | bullish | bearish filters the rows."""
    if href is None or name_for is None or theme is None or metrics is None:
        from chart_maps import board as B
        href = href or B._href
        name_for = name_for or B._name_for
        theme = theme or B._theme
        metrics = metrics or B.tile_metrics
    want = bias if bias in ("bullish", "bearish") else "all"
    out: list = []
    for r in rows or []:
        if want != "all" and r.get("bias") != want:
            continue
        t = tile_from_row(r, href=href, name_for=name_for, theme=theme, metrics=metrics)
        if t:
            out.append(t)
    return out
