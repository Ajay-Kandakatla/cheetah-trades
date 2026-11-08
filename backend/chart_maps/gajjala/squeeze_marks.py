"""🎾 GG's chart marks on the Reversal Squeeze card (SPEC gg-squeeze §3.3 / WP be-ellipses, 2026-11-08).

Ajay 2026-11-08, verbatim: "I need something like this but that big of circle for reversal squeen mainly on the cart
itself also increase the width of the reversal sqeeze chart to show more bars" / "This is from Gajjals". Clarified the
same morning: "They don't have to be circles but indicators did you build them already?"

WHAT. `ellipses(read, bars, …)` turns the STORED 🎾 read's `structure` stamps (detectors.reversal_squeeze — the ONE
engine; nothing here re-runs it) into served chart marks `{kind, from_t, to_t, lo, hi, label, note, tone}`: the earlier
tries that were sold, the tennis ball, the demand run, the quiet base, the entry bar (the A+ marker's own bar — the
caller passes the marker's stamp, ONE rule: the entry mark exists iff the A+ / "A+ (original)" marker exists) and the
prior session's after-hours spike (the K9 carry row of this symbol — the same predicate `scanner._at_least` and the same
constant K9_AH_CARRY_PCT that put the name in the carry; no new number). A mark is served ONLY when BOTH its stamps are
served bars (tab._on_bars' rule) — a stamp off the drawn window draws nothing.

WORDS. The SHORT label is what the chart prints; the note is the hover title and QUOTES GG (his chart's labels and the
S8/S9 lines) — never advice. NOT built (HIS CALLs): "PM - Held its AH price level" (needs a hold rule = a threshold) and
the red "CLOSE OR ADD OPPORTUNITY" (his exits are discretionary).

Display only: nothing here lists, gates, pushes or trades. UNMEASURED — a drawing of what the detector already found.
"""
from __future__ import annotations

import math
from typing import Optional

from . import constants as GC
from .scanner import _at_least                                 # the ONE K9 line predicate (scanner.py), never copied

__all__ = ["KINDS", "TONE", "WORDS", "AH_NOTE_TAIL", "ellipses"]

KINDS = ("ah", "attempt", "tennis", "run", "base", "entry")     # served order
TONE = {"ah": "structure", "attempt": "structure", "tennis": "structure", "run": "structure", "base": "structure",
        "entry": "entry"}
WORDS = {   # (SHORT chart label, the <title>/note — GG's own words, quoted; never buy/sell as advice)
    "ah":      ("AH spike",     'GG: "AH - Price spike with good volume"'),
    "attempt": ("earlier try",  'GG: "it has tried to squeeze in earlier bars and been sold" (S9 2:01:42)'),
    "tennis":  ("tennis ball",  'GG: "Tennis ball action, quick dump and reclaim"'),
    "run":     ("demand",       'GG: "Demand picks up"'),
    "base":    ("quiet base",   'GG S8 36:12: "the pullback is very gradual, all at the top of this bar with gradual '
                                'decrease in volume"'),
    "entry":   ("entry",        'GG: "ENTRY OPPORTUNITY" — the break of the top'),
}
AH_NOTE_TAIL = " · after hours {pct:+.1f}% vs the regular close"   # the carry row's own number


def _num(x) -> Optional[float]:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    x = float(x)
    return x if math.isfinite(x) else None


def _item(kind: str, from_t: str, to_t: str, lo, hi, note: Optional[str] = None) -> Optional[dict]:
    lo, hi = _num(lo), _num(hi)
    if lo is None or hi is None or lo > hi:
        return None
    label, words = WORDS[kind]
    return {"kind": kind, "from_t": from_t, "to_t": to_t, "lo": lo, "hi": hi, "label": label,
            "note": note if note is not None else words, "tone": TONE[kind]}


def _from_box(kind: str, box, served: dict) -> Optional[dict]:
    """A stored structure box {from_t, to_t, lo, hi, bars} → one mark, when both stamps are served bars."""
    if not isinstance(box, dict):
        return None
    a, b = box.get("from_t"), box.get("to_t")
    if not (isinstance(a, str) and isinstance(b, str) and a in served and b in served):
        return None
    return _item(kind, a, b, box.get("lo"), box.get("hi"))


def _ah(bars: list, carry_row, prev_iso) -> Optional[dict]:
    """The prior session's after-hours spike: the served prior-day `s == "ah"` bars whose HIGH clears the K9 carry line
    (reg_close × (1 + K9_AH_CARRY_PCT/100), `scanner._at_least`); the whole AH stretch when none does or the regular
    close is missing / ≤ 0. None without a carry row or without a served prior-day AH bar."""
    if not isinstance(carry_row, dict) or not isinstance(prev_iso, str) or not prev_iso:
        return None
    ah = [b for b in bars if b["t"].split(" ")[0] == prev_iso and b.get("s") == "ah"
          and _num(b.get("h")) is not None and _num(b.get("l")) is not None]
    if not ah:
        return None
    reg = _num(carry_row.get("reg_close"))
    spike = ([b for b in ah if _at_least(_num(b["h"]), reg, GC.K9_AH_CARRY_PCT)]
             if reg is not None and reg > 0 else [])
    pick = spike or ah
    note = WORDS["ah"][1]
    pct = _num(carry_row.get("ah_move_pct"))
    if pct is not None:
        note += AH_NOTE_TAIL.format(pct=pct)
    return _item("ah", pick[0]["t"], pick[-1]["t"], min(_num(b["l"]) for b in pick), max(_num(b["h"]) for b in pick),
                 note)


def ellipses(read: dict, bars: list, *, entry_t: Optional[str], carry_row: Optional[dict],
             prev_iso: Optional[str]) -> list:
    """The served 🎾 marks of one card, in KINDS order. `read` = the STORED read (its `structure`), `bars` = the SERVED
    bars of the drawn frame, `entry_t` = the stamp the A+ marker sits on (None = no marker), `carry_row` = this symbol's
    row of the prior session's carry doc, `prev_iso` = the prior market day. Never raises: junk in → []."""
    try:
        return _ellipses(read, bars, entry_t=entry_t, carry_row=carry_row, prev_iso=prev_iso)
    except Exception:                                           # noqa: BLE001 — a drawing never breaks the card
        return []


def _ellipses(read, bars, *, entry_t, carry_row, prev_iso) -> list:
    bars = [b for b in (bars if isinstance(bars, list) else []) if isinstance(b, dict) and isinstance(b.get("t"), str)]
    served = {b["t"]: b for b in bars}
    st = read.get("structure") if isinstance(read, dict) else None
    st = st if isinstance(st, dict) else {}
    out = []
    ah = _ah(bars, carry_row, prev_iso)
    if ah:
        out.append(ah)
    tries = st.get("attempts") if isinstance(st.get("attempts"), list) else []
    out.extend(m for m in (_from_box("attempt", b, served) for b in tries) if m)
    for kind in ("tennis", "run", "base"):
        m = _from_box(kind, st.get(kind), served)
        if m:
            out.append(m)
    if isinstance(entry_t, str) and entry_t in served:
        b = served[entry_t]
        m = _item("entry", entry_t, entry_t, b.get("l"), b.get("h"))
        if m:
            out.append(m)
    return out
