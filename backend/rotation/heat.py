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
bar: every number here is `rel_21d` from `rotation.tracker.build` — the median
member's 21-session return minus the equal-weight benchmark's. One definition
of "hot", shared with the Hot-sectors strip he already reads.

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

HOT IS A RANK, NOT A THRESHOLD — AND THE RANK IS POOLED
------------------------------------------------------
There is no measured number that says "+2% relative is hot". Rather than invent
one, a group is scored by its PERCENTILE among every live group on the rotation
map: top third = hot, bottom third = cold, middle = neutral. Self-calibrating —
a flat tape has no hot end by construction — and the raw rel_21d always rides
alongside so the rank never hides the number.

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
actually predicts anything on his own tape is a separate, measured question —
see docs/supply_demand/sector_heat.md for the number.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("rotation.heat")

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
    """{grain: {GROUP_KEY: row}} plus the sorted rel_21d list per grain, from a
    `rotation.tracker.build` payload. PURE. {} on anything unreadable — a heat
    read that cannot be made must read as UNKNOWN, never as hot."""
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
            v = _num(row.get("rel_21d"))
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
    a live cohort with a computable rel_21d. Falling through to a coarser grain
    is deliberate: a sector answer is worse than an industry answer but far
    better than silence, and `grain` says which one you got.
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
        rel = _num(row.get("rel_21d"))
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
            "grain": grain, "group": row.get("group"), "rel_21d": round(rel, 2),
            "rel_63d": _num(row.get("rel_63d")), "pct_positive": row.get("pct_positive"),
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
        rel = _num(row.get("rel_21d"))
        if rel is None:
            return None
        pctl = _percentile(index.get("scale") or [], rel)
        n = int(row.get("n") or 0)
        return {"grain": "theme", "group": row.get("group"),
                "rel_21d": round(rel, 2), "rel_63d": _num(row.get("rel_63d")),
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
    rel = _num(heat.get("rel_21d"))
    if not group or rel is None or tone == "unknown":
        return ""
    label = {"hot": HOT_LABEL, "cold": COLD_LABEL}.get(tone, NEUTRAL_LABEL)
    out = "%s %s %+.1f%% vs %s (21d)" % (label, group, rel,
                                         heat.get("benchmark") or "RSP")
    if heat.get("thin"):
        out += " · thin (n=%d)" % int(heat.get("n") or 0)
    # The curated roster only earns space when it DISAGREES with the objective
    # label — that gap is the finding (ai_semis +0.3 vs Semiconductors -2.0 on
    # 2026-09-09). When they agree it is a second way of saying one thing.
    side = heat.get("theme_heat") or {}
    s_tone, s_rel = side.get("tone"), _num(side.get("rel_21d"))
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
