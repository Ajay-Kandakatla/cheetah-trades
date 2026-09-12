"""🔥 Hottest Sectors — the ranked sector list, its industries, and the names.

Ajay 2026-09-11:

  "From the sectors. Can you find the hottest of the sectors like the most
   growth and put them in to a new tab. Like in to hottest of the sectors tab.."
  "I am seeing a lot of new names I was not tracking before.. but hottest from
   last 5 days and current. Like ANDE was never on my list but its growing"
  "List needs to be hottest of the sectors and then hottest from a sector in to
   a table. Like the catalyst and keep sales and other crucial metrics for me."

He then chose, when asked: ALL THREE LEGS (today / 5d / 21d) on this board, and
sectors that EXPAND into industries and then names.

WHY THE 21-DAY IS BACK HERE AND NOWHERE ELSE
--------------------------------------------
On 2026-09-10 he stripped the 21-day OFF the Hot-sectors strip ("Ignore the 21
day"). That still stands — `rotation.heat.HEAT_KEY` is untouched and the strip
is unchanged. This board is a different question. His own example proves why:
ANDE is +0.79% today, +1.35% over 5 days and +12.14% over 21. A 5-day-only
board cannot find it. So the 21-day rides HERE, as a discovery leg, and the
strip keeps his rotation read clean.

WHY NAMES ARE NOT RANKED BY `traction`
--------------------------------------
`traction` measures ACCELERATION (pace_5 vs pace_21) — "is it speeding up".
That is not "hottest". Measured on his own example: in Consumer Defensive ANDE
ranks 3/76 by rel_5d and 2/76 by rel_21d, but 23/76 by traction, because it is
strong and DECELERATING. Ranking this board on traction would bury the name
that prompted it. Sorting is by the return legs; `traction` still rides in
every row, because it is the one number the popover already owns and two
definitions of "gaining" on two surfaces is how they start disagreeing.

WHAT THIS BOARD IS AND IS NOT
-----------------------------
It is a DISCOVERY surface: a trailing-return ranking has no measured edge, and
nothing here has been backtested. It answers "what moved and what are its
fundamentals", not "what should I buy". No gate was widened to fill it.

TWO POPULATIONS, BOTH SAID OUT LOUD
-----------------------------------
Group heat is the SHIPPED number — the rotation grid's fixed sample (Technology
measures 40 of 305) — reused verbatim so this board can never disagree with the
strip. Name rows are the FULL liquidity-filtered membership, which is what
makes ANDE reachable at all: he is not in Consumer Defensive's sampled 40, but
he is 2nd of its full 76. Every row carries `basis` so the two are never read
as one.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from . import tracker as T

log = logging.getLogger("cheetah.rotation.hottest")

# The three legs he asked for, in the order the table prints them.
LEGS = ("rel_1d", "rel_5d", "rel_21d")
DEFAULT_SORT = "rel_5d"
# An industry below this never earns a RANKED row in the rotation grid. We
# still SHOW it inside its sector (ANDE's Food Distribution has 6 names and no
# shipped row at all — hiding it is how his example disappears), flagged `thin`
# so a 6-name median is never read as a 25-name one.
THIN_N = 8
NAMES_PER_GROUP = 25          # per sector/industry in the payload; the UI pages

# The fundamental columns the table prints. Ajay 2026-09-12: "Add sort in
# this" — every column he can read, he can rank on. These sort at the BACKEND
# on purpose: the payload keeps only `names_per_group` names per group, so a
# client-side sort would reorder the visible 25 and never reach the 46th name.
FUND_SORTS = ("sales_yoy", "q_eps_yoy", "net_margin", "eq_score")
# Ordinal, not numeric — a tier string has to become a rank before it sorts.
TIER_RANK = {"explosive": 5, "strong": 4, "steady": 3, "weak": 2, "declining": 1}
SORT_KEYS = (LEGS + ("traction", "ret_1d", "ret_5d", "ret_21d") + FUND_SORTS
             + ("sales_tier", "next_earnings"))
SORT_DIRS = ("desc", "asc")
DEFAULT_DIR = "desc"


def _num(v):
    """Floats only; NaN and inf are dropped to None. The JSON scrub downstream
    catches these too, but a NaN that reaches a SORT reorders the board
    silently first (NaN passes every <= comparison)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return f


def _sort_value(row: dict, key: str):
    """One comparable for any sortable column: numeric, tier ordinal, or date.

    Returns a `(present, value)` pair, and every caller sorts `reverse=True`.
    A MISSING value is `(0, ...)` and therefore sorts LAST in BOTH directions
    — the whole point of the pair. The old single `-inf` was correct only
    descending; on an ascending sort it floats every blank row to the top,
    which is the "sort by margin ascending shows 300 em-dashes" bug.
    """
    if key == "sales_tier":
        r = TIER_RANK.get(str(row.get(key) or "").lower())
        return (1, float(r)) if r else (0, 0.0)
    if key == "next_earnings":
        # ISO dates compare lexicographically; mapped to a number so the pair
        # stays homogeneous. Soonest-first is the ASCENDING direction.
        d = str(row.get(key) or "")
        if len(d) < 10 or d[4] != "-":
            return (0, 0.0)
        try:
            return (1, float(d[:4] + d[5:7] + d[8:10]))
        except ValueError:
            return (0, 0.0)
    v = _num(row.get(key))
    return (1, v) if v is not None else (0, 0.0)


def _sorter(key: str, direction: str):
    """`sorted(key=...)` for one column + direction, missing values last."""
    asc = direction == "asc"
    def _k(row):
        present, v = _sort_value(row, key)
        return (present, -v if asc else v)
    return _k


def _fund_medians(rows: list) -> dict:
    """A group's own read on each fundamental column: the median of its FULL
    membership. Sectors and industries had NOTHING in these columns, so a sort
    on one of them reordered the tree for no visible reason. The legs stay the
    rotation grid's sampled median (reused verbatim so this board can never
    disagree with the Hot-sectors strip); these are computed here because the
    grid ships no fundamentals at all."""
    out = {k: _median([_num(r.get(k)) for r in rows]) for k in FUND_SORTS}
    tiers = [TIER_RANK.get(str(r.get("sales_tier") or "").lower())
             for r in rows]
    tiers = [t for t in tiers if t]
    if tiers:
        rank = int(round(_median([float(t) for t in tiers]) or 0))
        out["sales_tier"] = next((n for n, v in TIER_RANK.items() if v == rank), None)
    else:
        out["sales_tier"] = None
    out["fund_basis"] = "median of full membership"
    return out


def _fundamentals_row(sym: str, fund: dict, earn: dict) -> dict:
    """The decision columns, flattened. A missing field stays None — the table
    prints an em-dash and never a zero, and a None never wins a sort."""
    f = fund or {}
    sales = f.get("sales") or {}
    eq = f.get("earnings_quality") or {}
    comp = eq.get("components") or {}
    flags = eq.get("red_flags") or {}
    e = earn or {}
    return {
        "sales_yoy": _num(f.get("rev_growth_q_pct")),
        "sales_tier": sales.get("tier") or None,
        "sales_prior_yoy": _num(sales.get("prior_yoy_pct")),
        "sales_accelerating": bool(sales.get("accelerating")) if sales.get("accelerating") is not None else None,
        "q_eps_yoy": _num(f.get("q_eps_growth_pct")),
        "y_eps_growth": _num(f.get("y_eps_growth_pct")),
        "net_margin": _num(comp.get("npm_latest_pct")),
        "margin_expanding": bool(comp.get("npm_expanding")) if comp.get("npm_expanding") is not None else None,
        "eq_score": _num(eq.get("score")),
        "eq_tier": eq.get("tier") or None,
        "code_33": bool(eq.get("code_33")) if eq.get("code_33") is not None else None,
        "sales_backed": bool(comp.get("sales_backed")) if comp.get("sales_backed") is not None else None,
        "inventory_flag": bool(flags.get("inventory_vs_sales")) if flags.get("inventory_vs_sales") is not None else None,
        "next_earnings": e.get("next_date") or None,
        "earnings_when": e.get("when") or None,
        "fundamentals_as_of": f.get("cached_at"),
    }


def _earnings_map(symbols: list[str]) -> dict:
    """TRAP: `earnings_calendar` is keyed by `_id`, NOT by a `symbol` field.
    Querying {"symbol": {"$in": ...}} returns zero documents with no error —
    a silently 100%-blank column that reads like "we have no earnings data"."""
    if not symbols:
        return {}
    try:
        import os
        from pymongo import MongoClient
        c = MongoClient(os.environ.get("MONGO_URL", "mongodb://mongo:27017"),
                        serverSelectionTimeoutMS=2000)
        coll = c.get_database("cheetah")["earnings_calendar"]
        return {d["_id"]: d for d in coll.find(
            {"_id": {"$in": [s.upper() for s in symbols]}},
            {"_id": 1, "next_date": 1, "when": 1})}
    except Exception as exc:
        log.warning("hottest: earnings map failed: %s", exc)
        return {}


def _decision_map(symbols: list[str]) -> dict:
    if not symbols:
        return {}
    try:
        from sepa import research
        return research.decision_snapshot(list(symbols))
    except Exception as exc:
        log.warning("hottest: decision snapshot failed: %s", exc)
        return {}


def _group_legs(row: dict) -> dict:
    out = {k: _num(row.get(k)) for k in LEGS}
    out["pct_positive_1d"] = _num(row.get("pct_positive_1d"))
    out["n_measured"] = row.get("n")
    out["dropped"] = row.get("dropped")
    return out


def _median(vals: list) -> Optional[float]:
    xs = sorted(v for v in vals if v is not None)
    if not xs:
        return None
    n = len(xs)
    m = xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0
    # rounded to match the precision the shipped group rows already carry —
    # an unrounded average of two floats prints as -1.1849999999999998 beside
    # a shipped 1.49 and reads like a different kind of number
    return round(m, 2)


def build(payload: dict, *, sort: str = DEFAULT_SORT,
          direction: str = DEFAULT_DIR,
          names_per_group: int = NAMES_PER_GROUP) -> dict:
    """Assemble the board from an already-built rotation payload. PURE — no
    Mongo, no fetch — except the two bulk joins, which are injected by
    `build_live`. Keeps the shape testable off a fixture."""
    return _build(payload, sort=sort, direction=direction,
                  names_per_group=names_per_group,
                  decisions={}, earnings={})


def build_live(payload: dict, *, sort: str = DEFAULT_SORT,
          direction: str = DEFAULT_DIR,
               names_per_group: int = NAMES_PER_GROUP) -> dict:
    """`build` plus the two bulk reads, done ONCE for the whole board rather
    than per row."""
    table = (payload or {}).get(T.MEMBERS_KEY) or {}
    syms = list((table.get("by_symbol") or {}).keys())
    return _build(payload, sort=sort, direction=direction,
                  names_per_group=names_per_group,
                  decisions=_decision_map(syms), earnings=_earnings_map(syms))


def _build(payload: dict, *, sort: str, names_per_group: int,
           decisions: dict, earnings: dict,
           direction: str = DEFAULT_DIR) -> dict:
    sort_key = sort if sort in SORT_KEYS else DEFAULT_SORT
    sort_dir = direction if direction in SORT_DIRS else DEFAULT_DIR
    _by = _sorter(sort_key, sort_dir)
    payload = payload or {}
    table = payload.get(T.MEMBERS_KEY) or {}
    by_symbol = table.get("by_symbol") or {}
    groups = table.get("groups") or {}
    bench = table.get("benchmark") or {}
    sector_groups = groups.get("sector") or {}
    industry_groups = groups.get("industry") or {}
    # THE GRAIN THIS BOARD COULD NOT SEE (Ajay 2026-09-12, looking at the
    # table): "Where is Robitics and crypto here?"
    #
    # It read `sector` and `industry` and nothing else, so the twelve curated
    # rosters — robotics, nuclear, quantum, rare_earth, optical, space, the AI
    # complex — were invisible here even though the Hot-sectors strip has
    # ranked them as THEME IN / THEME OUT chips for days and the members table
    # has carried the grain all along (`T.MEMBER_GRAINS`). Robotics was never
    # missing; this board simply never asked for it.
    theme_groups = groups.get("theme") or {}

    shipped_sectors = {r.get("group"): r for r in (payload.get("sectors") or [])}
    shipped_inds = {r.get("group"): r for r in (payload.get("industries") or [])}
    shipped_themes = {r.get("group"): r for r in (payload.get("themes") or [])}
    sampled = payload.get("sampled") or {}

    def _names(symbols: list, group_median) -> list:
        rows = []
        for s in symbols or []:
            stat = by_symbol.get(s)
            if not stat:
                continue
            # the SHARED builder — one definition of traction / rel_* app-wide
            r = T.traction_row(s, stat, group_median, bench)
            # ...but scrub what it hands back. A NaN in a price series survives
            # every arithmetic step and then passes EVERY <= comparison, so one
            # bad bar silently reorders the board. The endpoint's JSON scrub
            # runs far too late to protect a sort.
            r = {k: (_num(v) if isinstance(v, float) else v) for k, v in r.items()}
            r.update(_fundamentals_row(s, decisions.get(s), earnings.get(s)))
            rows.append(r)
        rows.sort(key=_by, reverse=True)
        return rows

    out_sectors = []
    for name, grp in sector_groups.items():
        shipped = shipped_sectors.get(name) or {}
        symbols = list(grp.get("symbols") or [])
        med21 = grp.get("median_21d")
        names = _names(symbols, med21)

        # every industry present in THIS sector's full membership, including
        # the ones too small for a ranked row of their own
        buckets: dict[str, list] = {}
        for s in symbols:
            ind = (by_symbol.get(s) or {}).get("industry") or "—"
            buckets.setdefault(ind, []).append(s)

        inds = []
        for ind, syms in buckets.items():
            ship = shipped_inds.get(ind)
            igrp = industry_groups.get(ind) or {}
            imed = igrp.get("median_21d")
            irows = _names(syms, imed)
            legs = (_group_legs(ship) if ship else
                    {k: _median([_num(r.get(k)) for r in irows]) for k in LEGS})
            if not ship:
                legs.update({"pct_positive_1d": None, "n_measured": len(syms), "dropped": None})
            inds.append({
                "group": ind,
                "n_full": len(syms),
                "ranked": bool(ship),
                "thin": len(syms) < THIN_N,
                # a computed row and a shipped row are NOT the same measurement
                "basis": "rotation grid sample" if ship else "full membership",
                "names": irows[:names_per_group],
                "names_total": len(irows),
                **legs,
                **_fund_medians(irows),
            })
        inds.sort(key=_by, reverse=True)

        samp = sampled.get(name) or {}
        out_sectors.append({
            "group": name,
            "n_full": len(symbols),
            "sampled_of": samp.get("of"),
            "sampled_used": samp.get("used"),
            "basis": "rotation grid sample",
            "industries": inds,
            "names": names[:names_per_group],
            "names_total": len(names),
            **_group_legs(shipped),
            **_fund_medians(names),
        })
    out_sectors.sort(key=_by, reverse=True)

    # ── Themes ────────────────────────────────────────────────────────────
    # A theme is a FLAT roster: no industry layer, because the whole point of a
    # curated theme is that it cuts ACROSS the provider's industries — robotics
    # spans Technology, Industrials and Consumer Cyclical, and splitting it back
    # into them would undo the only thing the roster is for.
    #
    # They ride ALONGSIDE the sectors and never replace them (rotation/heat.py
    # states why at length): on 2026-09-09 the curated `ai_semis` roster read
    # rel_21d +0.28 while the provider's `Semiconductors` cohort read −1.95 —
    # opposite signs on the same question. The objective label answers "how are
    # semis doing"; a roster we picked does not get to overrule it.
    out_themes = []
    for name, grp in theme_groups.items():
        shipped = shipped_themes.get(name) or {}
        symbols = list(grp.get("symbols") or [])
        med21 = grp.get("median_21d")
        trows = _names(symbols, med21)
        legs = (_group_legs(shipped) if shipped else
                {k: _median([_num(r.get(k)) for r in trows]) for k in LEGS})
        if not shipped:
            legs.update({"pct_positive_1d": None, "n_measured": len(symbols),
                         "dropped": None})
        out_themes.append({
            "group": name,
            "n_full": len(symbols),
            # Thin rosters are KEPT and FLAGGED, never dropped — he asked for
            # rare_earth (n=4) and nuclear by name, and a four-name median is
            # worth seeing as long as the row says how few names made it.
            "thin": len(symbols) < THIN_N,
            "ranked": bool(shipped),
            "basis": "rotation grid sample" if shipped else "full membership",
            "industries": [],
            "names": trows[:names_per_group],
            "names_total": len(trows),
            **legs,
            **_fund_medians(trows),
        })
    out_themes.sort(key=_by, reverse=True)

    covered = sum(1 for s in by_symbol if s in decisions)
    return {
        "as_of": payload.get("as_of"),
        "benchmark": payload.get("benchmark") or (bench or {}).get("symbol") or "RSP",
        "market": payload.get("market"),
        "sorted_by": sort_key,
        "sorted_dir": sort_dir,
        "sortable": list(SORT_KEYS),
        "legs": list(LEGS),
        "sectors": out_sectors,
        "themes": out_themes,
        "names_per_group": names_per_group,
        "coverage": {
            "priced": len(by_symbol),
            "with_fundamentals": covered,
            "pct": round(100.0 * covered / len(by_symbol), 1) if by_symbol else None,
        },
        "traction": T.TRACTION_SPEC,
        "note": (
            "Sector heat is the rotation grid's sampled median (the same number the "
            "Hot-sectors strip prints). Name rows are the FULL membership, which is why "
            "a strong name in a cold sector is still reachable. Themes are our own "
            "curated rosters and cut ACROSS the provider's sectors, so they ride "
            "alongside rather than replacing them — they disagree, and the objective "
            "label wins. Trailing returns only — a discovery list, not a measured signal."
        ),
        "built_at": int(time.time()),
    }
