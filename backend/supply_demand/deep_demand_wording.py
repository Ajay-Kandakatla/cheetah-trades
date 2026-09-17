"""Deep Demand — WHERE PRICE IS, and WHICH PRINT THAT IS MEASURED ON.

Ajay, on APLD this morning (2026-09-17): "Some of these are not accurate.
APLD is showing wrong in Deep demand" — and, once the numbers were in front of
him, "Ok it should be ok to be there. but I know its not 5% band thats ok.."

HIS DECISION: the name STAYS on the board. `chart_maps.board.BOUNCE_DONE_PCT`
(7.0) is untouched, no gate moves, no cohort changes. ONLY THE WORDS CHANGE.

WHAT WAS WRONG. The tile printed, side by side and unlabelled:

    why  = "broke its 1st demand band (10% below it), now 5.24% above the 2nd
            band (reclaimed from below) — sales +877% YoY …"
    stat = "Bands: … floor 1.5% wide, 2nd band 0.8% under"

with band 24.03-24.41, the scan close 24.39 (INSIDE the band) and a pre-market
print of 25.76 (+5.24% over the band top). Every number is right on its OWN
basis:

  * "10% below it"   — the SCAN CLOSE against the FIRST CROSSED band's floor
                       (`deep_demand.read`: `(t_lo - last) / t_lo * 100`).
  * "5.24% above"    — the LIVE print against the ARRIVAL band's top.
  * "0.8% under"     — not a distance from price at all: the GAP between the
                       first demand band's floor and the next band's top
                       (`band_structure.floor_read.gap_pct`).

Read together they describe the same band as 0.8% UNDER and 5.24% ABOVE, and
"Reclaiming" / "Entering" claimed an arrival the live tape had already left.
Of the 19 deep tiles that morning 10 carried a pre-market print and 8 of those
had left their band (+0.03% … +5.24%), so this is the board's normal state,
not one odd name.

WHAT THIS MODULE IS. Every sentence the deep tile says about POSITION is built
here, in ONE place, and every number it emits carries the basis it was measured
on. It is PURE: numbers and flags in, strings out. No store, no clock, no live
feed, no import from `chart_maps`. The ordinals come from `deep_demand.ordinal`
— never retyped — and no distance threshold is written here, because this
module decides nothing about who is on the board.

THE THREE CASES IT MUST READ CORRECTLY (his ask, measured that morning):
  * still IN the band     (WERN, dist <= 0)
  * a hair above it       (HGV, +0.03%)
  * well above it         (APLD, +5.24%)

THE VOCABULARY RULES:
  1. Every position number says which print it is on — "on the live print" or
     "on the close". `basis_word` is the only place those two phrases exist.
  2. ONE noun per band role. The arrival band is "its Nth demand level".
     The phrase "2nd band" leaves this surface entirely — `band_structure`'s
     floor clause owns "the next demand band below it", which is a DIFFERENT
     band, and the collision is what he read wrong.
  3. NO arrival verb when the print is above the band. Not "entering", not
     "arriving", not "reclaiming". It is above it, and the number says by how
     much.
  4. `reclaiming` is a PRIOR-CLOSE fact (`deep_demand.py:363`,
     `prev_close < band.lo`), so it is said as one — "yesterday closed under
     it" — and it is dropped entirely when there is no prior close behind it.
  5. Reversal, never bounce, on anything he reads.

EVERY INTERPOLATED CLAUSE IS BUILT INSIDE THE GUARD THAT PROVES ITS INPUTS
EXIST. This board took itself down once (2026-09-16) because an f-string was
evaluated before its guard, and a board-wide loop takes every OTHER tile with
it. A missing field renders a SHORTER honest sentence; it never raises.
"""
from __future__ import annotations

from typing import Optional

from supply_demand.deep_demand import ordinal

# ═════════════════════════════════════════════════════════════════════════════
# THE TWO PRINTS, NAMED ONCE
# ═════════════════════════════════════════════════════════════════════════════
# The closed bar the deep read was computed on: the level, the break, the
# `below_top_pct` and the reclaim flag are ALL measured here.
SCAN_BASIS = "scan"
# The bulk snapshot print (pre-market / RTH / after-hours): the position, the
# room and the live re-rank are measured here.
LIVE_BASIS = "live"

_BASIS_WORDS = {SCAN_BASIS: "on the close", LIVE_BASIS: "on the live print"}

# What the tile says when it does not know where price is. Never "0%", never
# "in the band" — an unknown position and a position of zero are opposite
# facts, and the 2026-09-16 wrapper served "now None% above it" for this case.
POSITION_UNKNOWN = "position unknown"


def _f(v) -> Optional[float]:
    """float or None. Never raises — a tile with a junk field renders shorter."""
    try:
        if v is None:
            return None
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None                      # NaN is not a number


def _pct(v: float) -> str:
    """'5.24%' — two decimals, trailing zeros trimmed, the way `_dist_text`
    has always served the position number (it prints the stored round(…, 2))."""
    s = ("%.2f" % float(v)).rstrip("0").rstrip(".")
    return "%s%%" % (s or "0")


# ═════════════════════════════════════════════════════════════════════════════
# THE WORDS
# ═════════════════════════════════════════════════════════════════════════════
def basis_word(basis: str) -> str:
    """'on the close' | 'on the live print'.

    The ONLY place those two phrases exist. An unrecognised basis returns ''
    — say nothing rather than guess which print a number came from, which is
    the whole defect this module exists to fix.
    """
    return _BASIS_WORDS.get(basis or "", "")


def band_noun(level: int) -> str:
    """The arrival band's name, ONE noun for the whole tile: 'its 2nd demand
    level'.

    Never the bare "2nd band": `band_structure.stat_line` used that phrase for
    a DIFFERENT band (the next demand band below the print) on the same tile,
    and he read the two as one. Ordinals come from `deep_demand.ordinal`.
    """
    try:
        return "its %s demand level" % ordinal(int(level))
    except (TypeError, ValueError):
        return "its demand level"


def position_phrase(dist_pct, level: int, basis: str) -> str:
    """WHERE THE PRINT IS relative to the arrival band, with its basis said.

        dist <= 0 -> 'in its 2nd demand level on the live print'
        dist >  0 -> '5.24% above its 2nd demand level on the live print'
        dist None -> 'position unknown'

    NO arrival verb, in any branch — see `verb_phrase`. The basis clause is
    omitted (not guessed) when the basis is unrecognised.
    """
    d = _f(dist_pct)
    if d is None:
        return POSITION_UNKNOWN
    noun, word = band_noun(level), basis_word(basis)
    head = "in %s" % noun if d <= 0 else "%s above %s" % (_pct(d), noun)
    return "%s %s" % (head, word) if word else head


def crossed_phrase(levels_broken: int, below_top_pct, basis: str) -> str:
    """'broke its 1st demand level (10% under that level's floor on the close)'
       'crossed 3 demand levels (15% under the first level's floor on the close)'

    The parenthetical names BOTH the reference edge and the basis: `below_top_pct`
    is measured off the crossed band's LO — its FLOOR, not its top
    (`deep_demand.read`: `(t_lo - last) / t_lo * 100`) — on the SCAN close.
    `below_top_pct is None` drops the clause entirely; it is never rendered as
    "(0% below it)", because "we did not measure it" and "it is zero" are
    different facts.
    """
    try:
        n = int(levels_broken)
    except (TypeError, ValueError):
        return ""
    if n < 1:
        return ""
    head = ("broke its %s demand level" % ordinal(1) if n == 1
            else "crossed %d demand levels" % n)
    below = _f(below_top_pct)
    if below is None:
        return head
    edge = "that level's floor" if n == 1 else "the first level's floor"
    word = basis_word(basis)
    inner = "%.0f%% under %s" % (below, edge)
    return "%s (%s)" % (head, "%s %s" % (inner, word) if word else inner)


def verb_phrase(dist_pct, reclaiming: bool, basis: str) -> str:
    """The ONE place an arrival verb is chosen, and it is chosen on the SAME
    print the position is quoted on:

        dist <= 0 and reclaiming -> 'back inside it from below'
        dist <= 0                -> 'standing in it'
        dist >  0                -> 'above it'            (NO arrival verb)
        dist None                -> ''                     (say nothing)

    `reclaiming` is a prior-close fact, so it is only allowed to shape the
    verb while the print is still IN the band; once the print is above it, the
    band was left and the tile says so. `basis` is accepted so a caller cannot
    pick the verb off one print and the number off another.
    """
    d = _f(dist_pct)
    if d is None:
        return ""
    if d > 0:
        return "above it"
    return "back inside it from below" if reclaiming else "standing in it"


def prior_close_note(reclaiming: bool, prev_close_known: bool) -> str:
    """'yesterday closed under it' — the reclaim said as what it IS.

    `deep_demand.read` sets `reclaiming` from `prev_close < band.lo`
    (deep_demand.py:363): a PRIOR-CLOSE fact, not a statement about the print
    on the screen. Empty when there is no reclaim, and empty when there is no
    prior close standing behind it — an unknown is never asserted as a reclaim.
    """
    return "yesterday closed under it" if (reclaiming and prev_close_known) else ""


def why_sentence(*, levels_broken: int, level: int, below_top_pct,
                 dist_pct, reclaiming: bool, prev_close_known: bool,
                 dist_basis: str, sales_growth_pct) -> str:
    """The whole `why` line. Every number carries its basis.

    Each clause is assembled INSIDE the guard that proves its inputs exist, so
    a row missing `below_top_pct`, `dist_pct` or its sales growth renders a
    SHORTER sentence and never raises (the board-wide loop at
    `chart_maps.board.deep_demand_tiles` would otherwise lose every other tile
    with it). The old guard dropped the whole sentence for a level-only
    fallback when either was missing; this keeps whatever IS known and says
    nothing about what is not.
    """
    head = crossed_phrase(levels_broken, below_top_pct, SCAN_BASIS)
    pos = position_phrase(dist_pct, level, dist_basis)
    pos = pos if pos == POSITION_UNKNOWN else "now %s" % pos
    sentence = "%s, %s" % (head, pos) if head else pos
    note = prior_close_note(reclaiming, prev_close_known)
    if note:
        sentence = "%s (%s)" % (sentence, note)
    g = _f(sales_growth_pct)
    if g is None:
        # The Bonde gate already passed — the tier is intact, the % is not
        # known on this row. Say the fact, invent no number.
        return "%s — Bonde-intact sales" % sentence
    return ("%s — sales %+.0f%% YoY say the business didn't break with the price"
            % (sentence, g))


def band_label(level: int, dist_pct, reclaiming: bool, phase: str) -> str:
    """The chart band's label, same vocabulary as the badge.

        dist <= 0, reclaiming     -> '2nd demand level · back in from below'
        dist <= 0                 -> '2nd demand level · price inside'
        dist  > 0, approaching    -> '2nd demand level · falling toward it'
        dist  > 0                 -> '2nd demand level · price above it'
        dist None                 -> '2nd demand level'
    """
    noun = ordinal(int(level)) if _f(level) is not None else ""
    head = ("%s demand level" % noun) if noun else "demand level"
    d = _f(dist_pct)
    if d is None:
        return head
    if d > 0:
        return "%s · %s" % (head, "falling toward it"
                            if phase == "approaching" else "price above it")
    return "%s · %s" % (head, "back in from below" if reclaiming
                        else "price inside")


def badge_text(level: int, dist_pct, reclaiming: bool) -> str:
    """'🩹 In its 2nd demand level' | '🩹 Back in its 2nd demand level from
    below' | '🩹 Above its 2nd demand level' | '🩹 Its 2nd demand level —
    position unknown'.

    The third case is the one that must never say "Reclaiming" / "Entering":
    8 of the 10 deep tiles with a pre-market print that morning were ABOVE
    their band while the badge claimed an arrival.
    """
    noun = band_noun(level)
    d = _f(dist_pct)
    if d is None:
        return "🩹 %s%s — %s" % (noun[0].upper(), noun[1:], POSITION_UNKNOWN)
    if d > 0:
        return "🩹 Above %s" % noun
    if reclaiming:
        return "🩹 Back in %s from below" % noun
    return "🩹 In %s" % noun


def basis_note(dist_basis: str, n_live: int, n_total: int) -> str:
    """The ONE board-level sentence saying which print the position numbers
    were taken on, and on how many tiles.

    Built from counts the board already has; it claims nothing about who
    qualifies. Empty on an empty board rather than "0 of 0".
    """
    try:
        live, total = int(n_live), int(n_total)
    except (TypeError, ValueError):
        return ""
    if total <= 0:
        return ""
    live = max(0, min(live, total))
    tail = ("The level, the break and the reclaim are always read %s."
            % basis_word(SCAN_BASIS))
    if live <= 0:
        word = basis_word(dist_basis) or basis_word(SCAN_BASIS)
        return ("Where price is now is read %s on all %d tiles here. %s"
                % (word, total, tail))
    return ("Where price is now is read %s on %d of %d tiles here and %s on "
            "the other %d. %s"
            % (basis_word(LIVE_BASIS), live, total, basis_word(SCAN_BASIS),
               total - live, tail))
