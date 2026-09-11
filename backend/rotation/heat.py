"""Sector heat for one symbol — "is this name's money coming in or going out?"

Ajay 2026-09-09 (verbatim):

    "increase our sectors It looks like a rotation is happening every other day
     today I see oil and energy had a bunch, money got moved in to technology
     too from Semis or reduced in semis today. I want you to consider that in
     the winning criteria. Like AVGO had burst with Semis and now its down with
     all semis.. So when we are looking at newly stocks getting dropped in to
     demand zone they might be too late. What we are looking for hot sectors in
     demand zone. I know its tough but atleast give me an indicator that its in
     hot sector or not.. Becuz when money is moved from a sector its just
     sitting there stock is not reversing quick."

and, minutes later:

    "yeah rare earth minerals and nuclear energy, and any other hot sectors.
     just find all the hot sectors and AI related sectors and cyclical sectors
     track all of those I think its needed."

WHAT THIS IS. A read, off the rotation tracker's own numbers. It does NOT
compute a new return, does not define a new window and does not re-fetch a
bar: every number here is `HEAT_KEY` from `rotation.tracker.build` — the median
member's return over that window minus the equal-weight benchmark's. One
definition of "hot", shared with the Hot-sectors strip he already reads.

THE GRAINS, AND WHICH ONE DECIDES
---------------------------------
  industry   73 live cohorts off the scan's own `industry` field
             (Semiconductors, Semiconductor Equipment & Materials, Oil & Gas
             E&P, Uranium, Solar, ...). ~2,450 names. THIS DECIDES THE TONE.
  sector     the 11 GICS sectors. The fallback: ~90% of the scan has one.
  theme      the 11 curated build-out rosters (ai_semis, ai_power, nuclear,
             rare_earth, space, quantum, optical, robotics, ai_infra, defense,
             energy). Carried ALONGSIDE, never as the headline.

WHY INDUSTRY DECIDES AND THEME ONLY RIDES ALONG. They disagree, and not by a
little: on 2026-09-09 the curated `ai_semis` roster read rel_21d +0.28 while
the GICS `Semiconductors` cohort read −1.95 — opposite signs on the same
question. `ai_semis` is 22 names WE picked; `Semiconductors` is the provider's
own label over 52. "AVGO ... is down with all semis" is a claim about all
semis, so the objective label answers it and the roster we curated does not
get to overrule the data. The theme read is still returned (he asked for the
AI complex, rare earths and nuclear by name) — it just cannot flip the badge.

WHY NOT SECTOR ALONE — the measurement that forced this. On 2026-09-09 the
Technology sector read rel_21d −4.72 / rel_63d −11.86. Inside it:

    Semiconductors                       rel_21d −1.95   rel_63d −13.32   32% positive
    Semiconductor Equipment & Materials  rel_21d −2.72   rel_63d −11.63   30% positive
    Software - Infrastructure            rel_21d −0.66   rel_63d +19.10   76% positive

A 33-point rel_63d spread INSIDE one sector row. "Money got moved in to
technology too from Semis" is invisible at the sector grain and obvious one
grain down. That is the whole reason this module exists.

THE WINDOW IS FIVE SESSIONS, NOT TWENTY-ONE (2026-09-10)
--------------------------------------------------------
Ajay, looking at the Aerospace & Defense chip (verbatim):

    "Actually this is red but it picked up today so its the inverse.. Basically
     what ever today is what I wanna see in green but keep the other days too,
     In general Aero was red but if you see 5 days to today its green. May be
     just keep 5days and today. That is what it should show.. Lately sector
     rotation is with in a week since its bear market... Ignore the 21 day even
     if its read now recently market rotated that is the actual truth to us"

The chip that prompted it: Aerospace & Defense read rel_21d −11.9% (−14.3% over
the full membership) — deep COLD — while over the last five sessions AIR +3.0,
MOG-A +2.9, ATRO +2.5, TXT +2.4, LMT +2.2, AVAV +4.1, RDW +7.5. The 21-day
window was describing a rotation that had already FINISHED, so the badge
printed the inverse of what the tape was doing. Hence `HEAT_KEY = "rel_5d"`:
the tone is decided on the last week, the horizon he says rotation now runs on.

rel_21d and rel_63d still ride in every read — "keep the other days too" — they
simply stopped choosing the word. Neither one is renamed and neither one is
dropped; a five-day answer is carried under a five-day name (see `heat_window`)
so no surface can print a week's move under a month's label.

HONESTY — THE MEASUREMENT DOES NOT TRANSFER TO THIS WINDOW
----------------------------------------------------------
`studies/sector_heat_study.py` measured the **rel_21d** definition over 50,191
replayed demand-zone arrivals and found NO edge: hot −0.57pp on win rate, 95%
[−1.87, +0.71]. That result describes the 21-day indicator, and the 21-day
indicator is no longer what ships. **The five-session heat below is UNMEASURED.**
The old null neither validates nor condemns it — it is a number about a
different indicator, and it must never be quoted as evidence for this one.
Re-running `sector_heat_study.py` on HEAT_KEY is the honest follow-up and it
has not been done. (The one "5d" column in that study is a five-session OUTCOME
clock measured on 21-day heat — a third thing again, and not evidence about
this window either.)

HOT IS A RANK, NOT A THRESHOLD — AND THE RANK IS POOLED
------------------------------------------------------
There is no measured number that says "+2% relative is hot". Rather than invent
one, a group is scored by its PERCENTILE among every live group on the rotation
map: top third = hot, bottom third = cold, middle = neutral. Self-calibrating —
a flat tape has no hot end by construction — and the raw HEAT_KEY value always
rides alongside so the rank never hides the number.

The scale is POOLED across all three grains (95 groups on 2026-09-09), not
computed within a grain. Ranking within a grain was the first cut and it was
wrong: with only 11 sectors, "top third" is the top three, so Utilities at
rel_21d +1.2% — a group sitting essentially ON the benchmark — was labelled
🔥 hot, while a 73-group industry scale set a far harder bar for the same
words. One scale means "hot" means one thing no matter which grain answered.

THIN COHORTS ARE LABELLED, NOT DROPPED. He named rare_earth and nuclear
explicitly; rare_earth has 4 members, quantum 5, defense 6 — under the
tracker's MIN_COHORT_N of 8. A median over four names is noise wearing a
number, so they are reported with `thin: True` and the member count visible.

NOT A GATE. Nothing here blocks a push or hides a board row. It is context
beside the setup, exactly like the mood and sweep reads. Whether sector heat
actually predicts anything on his own tape is a separate question — see
docs/supply_demand/sector_heat.md, remembering that the number there was
measured on rel_21d and not on the window this module now ships.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("rotation.heat")

# THE window. One constant, read by the pooled scale in `build_index` and by
# the per-name lookup in `read`, so the two can never end up ranking one window
# and answering about another. Ajay 2026-09-10: "Ignore the 21 day ... Lately
# sector rotation is with in a week since its bear market."
HEAT_KEY = "rel_5d"
# The label that ships beside the number, DERIVED from the key so a future
# window move cannot leave a stale "5d" printed under a different leg.
HEAT_WINDOW = HEAT_KEY.split("_", 1)[-1]

# Order the HEADLINE tone resolves in. `theme` is deliberately absent — see the
# docstring: it is reported beside the answer, never as the answer.
GRAINS = ("industry", "sector")
ALL_GRAINS = ("industry", "sector", "theme")

# Percentile cuts within a grain. Thirds: no threshold to justify, and a flat
# tape produces no hot end because the cuts move with the distribution.
HOT_PCTL = 66.7
COLD_PCTL = 33.3

HOT_LABEL = "\U0001F525 hot sector"
COLD_LABEL = "\U0001F9CA cold sector"
NEUTRAL_LABEL = "— sector flat"


def _num(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None          # NaN guard


def build_index(payload: Optional[dict]) -> dict:
    """{grain: {GROUP_KEY: row}} plus the sorted HEAT_KEY list per grain, from a
    `rotation.tracker.build` payload. PURE. {} on anything unreadable — a heat
    read that cannot be made must read as UNKNOWN, never as hot.

    A row with no HEAT_KEY leg contributes NOTHING to the scale. A payload
    written before that leg existed therefore produces an empty scale and every
    read goes silent until the next scan — which is the correct failure: no
    badge at all beats a badge ranked on a window the row does not carry.
    """
    payload = payload or {}
    idx: dict = {"as_of": payload.get("as_of"),
                 "benchmark": (payload.get("benchmark") or {}).get("symbol"),
                 "by": {g: {} for g in ALL_GRAINS},
                 # ONE pooled scale — see the docstring. Keyed per grain only
                 # so a caller can still inspect a grain's own spread.
                 "scale": [], "by_grain_scale": {g: [] for g in ALL_GRAINS}}
    for grain, key in (("industry", "industries"), ("sector", "sectors"),
                       ("theme", "themes")):
        for row in payload.get(key) or []:
            name = row.get("group")
            if not name:
                continue
            idx["by"][grain][str(name).strip().lower()] = row
            v = _num(row.get(HEAT_KEY))
            if v is not None:
                idx["scale"].append(v)
                idx["by_grain_scale"][grain].append(v)
        idx["by_grain_scale"][grain].sort()
    idx["scale"].sort()
    return idx


def _percentile(sorted_vals: list, v: float) -> Optional[float]:
    """Percent of the grain's groups at or below `v`. PURE."""
    n = len(sorted_vals)
    if n < 3:                       # too few groups for a rank to mean anything
        return None
    below = sum(1 for x in sorted_vals if x <= v)
    return 100.0 * below / n


def _tone(pctl: Optional[float]) -> str:
    if pctl is None:
        return "unknown"
    if pctl >= HOT_PCTL:
        return "hot"
    if pctl <= COLD_PCTL:
        return "cold"
    return "neutral"


def group_for(symbol: str, sector=None, industry=None, theme=None) -> list:
    """[(grain, group_name)] most specific first, for the labels supplied.
    `theme` defaults to the curated roster when not passed. PURE-ish (one
    lazy import for the theme roster)."""
    sym = str(symbol or "").strip().upper()
    if theme is None and sym:
        try:
            from sepa import universe as U
            theme = U.theme_for(sym)
        except Exception:                                   # pragma: no cover
            theme = None
    out = []
    for grain, name in (("industry", industry), ("sector", sector), ("theme", theme)):
        if name:
            out.append((grain, str(name).strip()))
    return out


def read(symbol: str, index: dict, sector=None, industry=None,
         theme=None) -> Optional[dict]:
    """The heat read for one name, or None when no grain covers it.

    Resolves theme -> industry -> sector and stops at the FIRST grain that has
    a live cohort with a computable HEAT_KEY. Falling through to a coarser grain
    is deliberate: a sector answer is worse than an industry answer but far
    better than silence, and `grain` says which one you got.

    A cohort carrying rel_21d but NO HEAT_KEY leg is UNKNOWN and falls through
    exactly like a missing cohort — it is never scored on the leg it still has.
    Answering off rel_21d because it happens to be there is the Aerospace bug
    the window move exists to kill.
    """
    if not index or not index.get("by"):
        return None
    resolved = group_for(symbol, sector, industry, theme)
    side = _theme_read(resolved, index)
    for grain, name in resolved:
        if grain == "theme":
            continue                     # never the headline (see the docstring)
        row = (index["by"].get(grain) or {}).get(name.lower())
        if not row:
            continue
        rel = _num(row.get(HEAT_KEY))
        if rel is None:
            continue
        pctl = _percentile(index.get("scale") or [], rel)
        if pctl is None:
            # The grain exists but carries too few groups to rank against, so
            # the tone would be "unknown". Fall THROUGH to the coarser grain
            # rather than answer with a shrug: a sector answer beats silence.
            continue
        n = int(row.get("n") or 0)
        return {
            "theme_heat": side,
            "grain": grain, "group": row.get("group"),
            # The deciding number, under the name of its OWN window, plus that
            # window spelled out so a caller never has to infer it from a key.
            HEAT_KEY: round(rel, 2), "heat_window": HEAT_WINDOW,
            # "keep the other days too" — carried, each still true to its own
            # label, none of them deciding. `rel_1d` is the "what ever today
            # is" leg he asked to see; `pct_positive_1d` is the breadth behind
            # it ("when there are none hot that day it helps to know overall
            # market it red").
            "rel_1d": _num(row.get("rel_1d")),
            "rel_21d": _num(row.get("rel_21d")),
            "rel_63d": _num(row.get("rel_63d")), "pct_positive": row.get("pct_positive"),
            "pct_positive_1d": row.get("pct_positive_1d"),
            "n": n, "percentile": None if pctl is None else round(pctl, 1),
            "tone": _tone(pctl),
            # Under the tracker's own cohort floor: reported, never silently
            # dropped (he asked for rare_earth and nuclear by name), but the
            # caller must be able to see that the median is thin.
            "thin": n > 0 and n < _min_n(),
            "sector": row.get("sector"),
            "as_of": index.get("as_of"), "benchmark": index.get("benchmark"),
        }
    return None


def _theme_read(resolved: list, index: dict) -> Optional[dict]:
    """The curated-roster read that rides ALONGSIDE the headline. Same shape,
    minus the recursion. None when the name is in no roster."""
    for grain, name in resolved:
        if grain != "theme":
            continue
        row = (index["by"].get("theme") or {}).get(name.lower())
        if not row:
            return None
        rel = _num(row.get(HEAT_KEY))
        if rel is None:
            return None                  # same leg as the headline, or silence
        pctl = _percentile(index.get("scale") or [], rel)
        n = int(row.get("n") or 0)
        return {"grain": "theme", "group": row.get("group"),
                HEAT_KEY: round(rel, 2), "heat_window": HEAT_WINDOW,
                "rel_1d": _num(row.get("rel_1d")),
                "rel_21d": _num(row.get("rel_21d")),
                "rel_63d": _num(row.get("rel_63d")),
                "n": n, "percentile": None if pctl is None else round(pctl, 1),
                "tone": _tone(pctl), "thin": n > 0 and n < _min_n()}
    return None


def _min_n() -> int:
    try:
        from rotation.tracker import MIN_COHORT_N
        return int(MIN_COHORT_N)
    except Exception:                                       # pragma: no cover
        return 8


def txt(heat: Optional[dict]) -> str:
    """One line for a push body or a board chip. '' when there is no read —
    silence, never a guess."""
    if not isinstance(heat, dict):
        return ""
    tone, group = heat.get("tone"), heat.get("group")
    rel = _num(heat.get(HEAT_KEY))
    if not group or rel is None or tone == "unknown":
        return ""
    label = {"hot": HOT_LABEL, "cold": COLD_LABEL}.get(tone, NEUTRAL_LABEL)
    # The window is printed, never assumed. This line rides in push bodies he
    # acts on; "+3.0% vs RSP" with the wrong window on it is the whole bug.
    out = "%s %s %+.1f%% vs %s (%s)" % (label, group, rel,
                                        heat.get("benchmark") or "RSP",
                                        heat.get("heat_window") or HEAT_WINDOW)
    if heat.get("thin"):
        out += " · thin (n=%d)" % int(heat.get("n") or 0)
    # The curated roster only earns space when it DISAGREES with the objective
    # label — that gap is the finding (ai_semis +0.3 vs Semiconductors -2.0 on
    # 2026-09-09). When they agree it is a second way of saying one thing.
    side = heat.get("theme_heat") or {}
    s_tone, s_rel = side.get("tone"), _num(side.get(HEAT_KEY))
    if s_tone and s_tone not in ("unknown",) and s_tone != heat.get("tone") and s_rel is not None:
        out += " · %s %+.1f%%" % (side.get("group"), s_rel)
        if side.get("thin"):
            out += " (thin n=%d)" % int(side.get("n") or 0)
    return out


def badge(heat: Optional[dict]) -> Optional[dict]:
    """Board-tile badge {text, tone} or None. Tones match chart_maps.board's
    existing vocabulary (good / warn / muted)."""
    line = txt(heat)
    if not line:
        return None
    tone = {"hot": "good", "cold": "warn"}.get(heat.get("tone"), "muted")
    return {"text": line, "tone": tone}
