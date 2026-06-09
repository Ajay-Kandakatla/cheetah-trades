"""Industry-group leadership + laggard annotation (Minervini Ch.6).

Source of truth: Mark Minervini, *Trade Like a Stock Market Wizard* (2013),
Chapter 6 "Categories, Industry Groups, and Catalysts," pp. 95-116.

> **Book p.102:** "You should concentrate on the top two or three stocks in a
> group: the leaders in terms of earnings, sales, margins, and relative price
> strength. This is especially true if the industry group is a leading sector
> during a bull market."
>
> **Book p.108 ("Stay Away from the Laggards"):** "A laggard is a stock that
> belongs to the same group as the market leader but has inferior price
> performance ... Don't be tempted by a stock with a relatively low P/E or one
> that hasn't appreciated as much as has the leader."

WHAT THIS DOES — and what it deliberately does NOT do.

The scanner ranks RS as a percentile across the WHOLE universe; it never groups a
stock against its industry peers, so it cannot tell "leader of a leading group"
from "laggard riding the group's draft." This module is an **additive,
DISPLAY-only** annotation that re-ranks RS *within each industry group* and tags:

  - ``group_leader``  — top N of its group by RS (the "top two or three", p.102)
  - ``is_laggard``    — same group as a leader but RS materially lower (p.108)
  - ``group_rs_rank`` / ``group_size`` / ``group_leader_symbol`` (context)

It is **NOT** a scoring change. Per SEPA_CONTRACTS.md §12 these are optional new
fields the v1 formula does not read — ``is_candidate``/``is_buyable``/``score``
and ``SCORE_WEIGHTS`` are untouched. The user's chosen policy (2026-06-09) is
"caution chip only": laggards are flagged, not demoted or excluded. Any future
*scored* use lives on the SEPA-v2 path (RFC 001).

Group source: yfinance ``industry`` via ``companies.store`` cache (the same
source ``sepa.moat_peers`` uses). Names with no cached industry, or industry
groups with only one scanned member, simply get null group fields — graceful
degradation, never faked (Rule #1).
"""
from __future__ import annotations

from typing import Optional

# ── Configured thresholds (book gives the CONCEPT, not these numbers) ──────────
# Locked in tests/test_sepa_contracts.py::test_group_leadership_constants_locked.
GROUP_LEADER_TOP_N = 3      # "top two or three stocks in a group" (p.102) -> top 3
LAGGARD_RS_GAP = 20.0       # RS points below the group's strongest = laggard (p.108).
#                             Configured (the book is qualitative "inferior ... price
#                             performance"); chosen, not a Minervini number.
MIN_GROUP_SIZE = 2          # need >=2 scanned members for a leadership contest.

# Keys this module writes onto each row (all additive; the v1 formula ignores them).
ANNOTATED_KEYS = (
    "industry", "sector", "group_rs_rank", "group_size",
    "group_leader", "is_laggard", "group_leader_symbol",
)


def _industry_map(symbols: list[str]) -> dict:
    """{SYMBOL: (industry, sector)} from the companies cache (cache-only)."""
    try:
        from companies import store
    except Exception:
        return {}
    info = store.get_many_cached(symbols)
    out: dict = {}
    for sym, doc in info.items():
        out[sym] = (doc.get("industry"), doc.get("sector"))
    return out


def annotate(rows: list[dict], industry_map: Optional[dict] = None) -> list[dict]:
    """Mutate each scan row IN PLACE with industry-group leadership fields.

    Parameters
    ----------
    rows : list[dict]
        Scan result rows (each must have ``symbol``; ``rs_rank`` may be None).
    industry_map : dict, optional
        ``{SYMBOL: (industry, sector)}`` override (used by tests). When omitted,
        it is read cache-only from ``companies.store`` — never hits yfinance, so
        this is safe to call on the daily scan hot path.

    Returns the same ``rows`` list (mutated) for convenience. Every row always
    ends up with all ``ANNOTATED_KEYS`` present (null/False when ungrouped), so
    downstream readers never KeyError.
    """
    if not rows:
        return rows

    symbols = [r.get("symbol") for r in rows if r.get("symbol")]
    imap = industry_map if industry_map is not None else _industry_map(symbols)

    # First pass: stamp industry/sector + null group fields on every row so the
    # output shape is uniform even for ungrouped names.
    for r in rows:
        sym = (r.get("symbol") or "").upper()
        industry, sector = (imap.get(sym) or (None, None))
        r["industry"] = industry
        r["sector"] = sector
        r["group_rs_rank"] = None
        r["group_size"] = None
        r["group_leader"] = False
        r["is_laggard"] = False
        r["group_leader_symbol"] = None

    # Group the rows that have BOTH an industry label and an RS rank.
    groups: dict = {}
    for r in rows:
        ind = r.get("industry")
        rs = r.get("rs_rank")
        if ind and rs is not None:
            groups.setdefault(ind, []).append(r)

    for ind, members in groups.items():
        size = len(members)
        if size < MIN_GROUP_SIZE:
            # A one-name "group" has no leadership contest — leave null.
            for r in members:
                r["group_size"] = size
            continue
        # Rank by RS desc; ties broken by composite score then symbol for stability.
        members.sort(key=lambda r: (-(r.get("rs_rank") or 0), -(r.get("score") or 0), r.get("symbol") or ""))
        top_rs = members[0].get("rs_rank") or 0
        leader_symbol = members[0].get("symbol")
        for i, r in enumerate(members):
            rank = i + 1
            rs = r.get("rs_rank") or 0
            gap = top_rs - rs
            r["group_size"] = size
            r["group_rs_rank"] = rank
            r["group_leader_symbol"] = leader_symbol
            # Leader and laggard are OPPOSITE ENDS, not just rank: a name can be
            # rank-2 yet a laggard if it trails the group's strongest by a wide
            # margin (book p.108 — "inferior price performance" vs the leader).
            # So laggard is gap-based (rank-agnostic), and a leader must be both
            # top-N AND close to the top — making the two mutually exclusive.
            r["is_laggard"] = gap >= LAGGARD_RS_GAP
            r["group_leader"] = (rank <= GROUP_LEADER_TOP_N) and not r["is_laggard"]

    return rows
