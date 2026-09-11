"""Sector rotation tracker — where money left, where it went, and since when.

Ajay 2026-08-16: *"I want you to have sector rotation tracker what I feel now is
money is rotating out of that themes I gave you"* and *"add a rule to also track
sector rotations time to time and make sure few other sectors that wallstreet
rotates in to historically. Like safe haves vs in general."*

METHOD NOTE — this is a PRAGMATIC relative-strength measurement, not a named
book methodology. Nothing here is Minervini. It reports what moved; it does not
predict what moves next, and it does not claim to identify a business-cycle
phase. Decision support only, NOT a buy signal.

FOUR DECISIONS THAT DECIDE WHETHER THE NUMBERS ARE HONEST
---------------------------------------------------------
Each of these flipped real conclusions during the 2026-08-16 measurement, so
each is pinned by a test rather than left as an implementation detail.

1. **Benchmark is RSP, not SPY.** Equal-weight, because cap-weight drag is not
   rotation. Measured 2026-05-29 -> 2026-08-14: RSP +6.68% vs SPY +2.63%, so
   4.05pp of "outperformance" against SPY was pure index construction. Nine
   ETFs flip sign when rebased (IWM, XLP, XLRE, XLB, XLU, GDX, XHB, ITB, XAR).

2. **Anchor is the last close STRICTLY BEFORE the window start.** Not
   on-or-before. The two conventions flip IGV, XLU, XLY and VPU. A window that
   starts on a non-trading day must resolve identically for every symbol,
   including the benchmark, or the comparison is between different windows.

3. **Median member, not the group ETF.** SOXX read -3.28% while the median
   liquid semiconductor stock was -11.67% — the ETF's cap weighting hid the
   damage in the names Ajay would actually buy. Both are reported; the median
   is the ranking key.

4. **Dead tickers are dropped, not counted as flat.** `bars_for` happily
   returns a stale frame for a delisted name: MRO's last bar is 2024-11-21
   (acquired by COP), HES's is 2025-07-17 (acquired by CVX). Their anchor falls
   after their final bar, so a naive return is exactly 0.0% — which silently
   drags a sector median toward zero. Any series whose last bar is more than
   `MAX_STALE_DAYS` behind the freshest bar in the run is excluded and counted
   in `dropped`.

WHAT THIS DELIBERATELY DOES NOT DO
----------------------------------
It does not read 13F. Institutional holdings are filed 45 days after quarter
end and our cache caps holders at 10 per ticker, so they are a LAGGING LEVEL,
never a flow. Calling a 13F level "money flowing in" is the exact error that
once printed +968% on this project.

THE MEMBER TABLE (Ajay 2026-09-10)
----------------------------------
"I would like to click on the sector category and see the related stocks list
in a pop over to see which ones are gaining traction."

Every row above is a MEDIAN over a deterministic 25-to-40-name sample of its
group — cheap, stable, and the number he already reads on the strip. The
popover asks a different question ("which NAMES"), and a sample would answer
it wrongly: 25 of Technology's 298 liquid names, presented as the sector.

So `build` also emits a per-member table over the FULL liquidity-filtered
membership (`members`, see `_member_table`). Two rules keep the two honest:

  * the sampled medians are computed EXACTLY as before — this table is
    additive and changes no number already on a screen;
  * the table carries its own full-membership median (`median_21d_full`)
    beside the published sampled one, and `MEMBER_NOTE` says in one line that
    they are two populations. They are never silently reconciled.

Cost, measured 2026-09-10 on the live scan: the full membership is 1,712
symbols against the 1,480 the sampled grid already loads, so ONE `_load` over
the union adds 251 fetches / +6.4 s, and the demand-zone marker adds ~0.1 s.
"""
from __future__ import annotations

import logging
import statistics
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable, Optional

log = logging.getLogger("rotation.tracker")

# Equal-weight S&P. See decision 1 above.
BENCHMARK = "RSP"
# Fallback if RSP has no frame — reported in the payload so a SPY-based run is
# never mistaken for an RSP-based one.
BENCHMARK_FALLBACK = "SPY"

# A series this far behind the freshest bar in the run is a dead ticker.
MAX_STALE_DAYS = 10

# Trailing windows, in trading days.
WINDOW_SHORT = 21
WINDOW_MED = 63
# The member table's "this week" leg (2026-09-10). Only the popover reads it —
# no group median is computed over it, so nothing on an existing screen moves.
WINDOW_FAST = 5

# Same day (2026-09-10, Ajay: "Can you also check for same day sector too
# please? ... Instead of 5 days"). One session: the member's last close against
# the one before it, and the group's MEDIAN of those — "what is this sector
# doing TODAY", which no window here answered.
#
# Deliberately NOT wired into `traction`: over one session a single gap flags a
# name, and the standing instruction is that signals get more accurate, never
# noisier. It is a column and a group median, printed beside the flag rather
# than feeding it.
WINDOW_DAY = 1

# Bars pulled per symbol. 260 covers a year, enough for any window here plus
# the pre-window anchor.
BARS = 260
WORKERS = 8

# Groups Wall Street rotates between, by behaviour rather than by cycle phase.
# Ajay asked for "safe havens vs in general". These are DESCRIPTIVE buckets of
# our own sector labels — they say what a group has historically behaved like,
# not what phase the economy is in. A tracker that claims to know the phase is
# making a forecast; this one reports a measurement.
DEFENSIVE = ("Utilities", "Consumer Defensive", "Healthcare", "Real Estate")
CYCLICAL = ("Technology", "Consumer Cyclical", "Industrials",
            "Financial Services", "Basic Materials", "Communication Services")
COMMODITY = ("Energy",)

STANCE = {}
for _s in DEFENSIVE:
    STANCE[_s] = "defensive"
for _s in CYCLICAL:
    STANCE[_s] = "cyclical"
for _s in COMMODITY:
    STANCE[_s] = "commodity"

# Group-level ETFs, reported ALONGSIDE the median member so the gap between
# them is visible. That gap is itself the finding — it measures how much of a
# move is mega-cap concentration.
SECTOR_ETF = {
    "Technology": "XLK", "Healthcare": "XLV", "Financial Services": "XLF",
    "Energy": "XLE", "Industrials": "XLI", "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP", "Utilities": "XLU", "Basic Materials": "XLB",
    "Real Estate": "XLRE", "Communication Services": "XLC",
}

# ── Cap-tier cohorts (Ajay 2026-08-31) ──────────────────────────────────────
# "Feel free to categorize more sectors in a similar faction.. Like Health care
# small caps or something please feel free to reinvent the wheel."
#
# Tier = S&P index membership, NOT a computed market cap: the S&P committee
# already maintains the large/mid/small split (500/400/600), the lists are
# cached 30 days in sepa.universe, and membership costs zero API calls — where
# a shares-outstanding × price cap would cost one Massive reference call per
# name per process. The label says which index so the tier is auditable.
CAP_TIERS = (("large", "S&P 500"), ("mid", "S&P 400"), ("small", "S&P 600"))

# A median over a handful of names is noise wearing a number. Cohorts with
# fewer kept members than this are dropped and counted, not shown.
MIN_COHORT_N = 8

# Per-cohort sample cap — same deterministic stride as the sector grid.
COHORT_SAMPLE = 25


def _tier_sets() -> dict:
    """{tier: set(symbols)} from the cached index lists. {} on any failure —
    cohorts then simply do not render, the sector grid is untouched."""
    try:
        from sepa import universe as U
        return {"large": {s.upper() for s in (U.fetch_sp500() or [])},
                "mid": {s.upper() for s in (U.fetch_sp400() or [])},
                "small": {s.upper() for s in (U.fetch_sp600() or [])}}
    except Exception as exc:                                # pragma: no cover
        log.warning("rotation: tier lists unavailable: %s", exc)
        return {}


def _cohort_members(sectors: dict, tiers: dict,
                    sample: int = COHORT_SAMPLE) -> list:
    """[(label, sector, tier, members)] — sector × cap-tier intersections.

    Tiering happens BEFORE sampling, on the full sector membership: sampling
    first and tiering after would leave small-cap cohorts starved by whichever
    names the sector stride happened to pick.

    `sample <= 0` turns the cap OFF and returns the full roster — the member
    table (2026-09-10) needs every name, and it must come out of THIS builder
    rather than a parallel one, or the popover's membership could drift from
    the row it opens under.
    """
    out = []
    for sec, syms in sectors.items():
        pool = sorted({s.upper() for s in syms})
        for tier, index_name in CAP_TIERS:
            members = [s for s in pool if s in (tiers.get(tier) or ())]
            if len(members) < MIN_COHORT_N:
                continue
            if sample > 0 and len(members) > sample:
                step = len(members) / sample
                members = [members[int(i * step)] for i in range(sample)]
            label = f"{sec} · {tier} caps"
            out.append({"label": label, "sector": sec, "tier": tier,
                        "index": index_name, "members": members})
    return out


# ── Industry cohorts (Ajay 2026-09-09) ──────────────────────────────────────
# "increase our sectors It looks like a rotation is happening every other day
# today I see oil and energy had a bunch, money got moved in to technology too
# from Semis or reduced in semis today. Like AVGO had burst with Semis and now
# its down with all semis."
#
# GICS SECTOR IS THE WRONG GRAIN FOR WHAT HE WATCHES. AVGO is labelled
# Technology / Semiconductors. Inside "Technology" (426 scan names) a semis
# rotation is diluted by ~370 software, IT-services and hardware names moving
# on something else entirely — so the sector row can read flat through exactly
# the move he is describing.
#
# The scan rows already carry `industry` and nothing was reading it: 2,643 of
# 2,948 rows have one, across 143 distinct values, 98 of which clear
# MIN_COHORT_N and together cover 2,454 names. That IS his vocabulary —
# Semiconductors (52) and Semiconductor Equipment & Materials (25) as separate
# groups, Oil & Gas E&P (39), Oil & Gas Equipment & Services (33), Oil & Gas
# Midstream (22), Solar (9), Uranium (5, below the floor and correctly
# dropped). Measured 2026-09-09 on the live scan.
#
# Same floor and the same deterministic stride as the cap-tier cohorts: a
# median over a handful of names is noise wearing a number.
MIN_INDUSTRY_N = MIN_COHORT_N
INDUSTRY_SAMPLE = COHORT_SAMPLE


def _industry_members(rows: list, sample: int = INDUSTRY_SAMPLE) -> list:
    """[{label, sector, industry, members}] from already-liquidity-filtered scan
    rows. PURE given `rows`.

    Takes the rows rather than re-reading the scan so the liquidity gate and
    the sector grid see EXACTLY the same population — an industry median over a
    different universe than the sector median above it is two answers to one
    question.

    `sample <= 0` turns the cap OFF (see `_cohort_members`).
    """
    pools: dict = {}
    for sym, sec, ind in rows:
        if not ind:
            continue
        pools.setdefault((str(ind), str(sec or "")), set()).add(sym)
    out = []
    for (ind, sec), syms in pools.items():
        members = sorted(syms)
        if len(members) < MIN_INDUSTRY_N:
            continue
        if sample > 0 and len(members) > sample:
            step = len(members) / sample
            members = [members[int(i * step)] for i in range(sample)]
        out.append({"label": ind, "sector": sec or None, "industry": ind,
                    "members": members})
    out.sort(key=lambda c: c["label"])
    return out


# Safe-haven proxies tracked outside the sector grid. Ajay: "make sure few other
# sectors that wallstreet rotates in to historically. Like safe haves."
HAVEN_PROXY = {
    "Gold": "GLD", "Gold miners": "GDX", "Silver": "SLV",
    "Long treasuries": "TLT", "Short treasuries": "SHY",
    "Low volatility": "USMV", "Equal-weight S&P": "RSP",
}


def _bars_for(symbol: str, days: int = BARS):
    from chart_maps.board import bars_for
    return bars_for(symbol, days=days)


def _load(symbols: Iterable[str]) -> dict:
    """Fetch frames concurrently. A failure is an omission, never an exception."""
    syms = [s for s in dict.fromkeys(symbols) if s]

    def one(sym):
        try:
            return sym, (_bars_for(sym) or [])
        except Exception as exc:
            log.debug("rotation: bars %s failed: %s", sym, exc)
            return sym, []

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return dict(pool.map(one, syms))


def _last_date(bars) -> str:
    return str(bars[-1].get("t") or "") if bars else ""


def anchor_close(bars, start: str) -> Optional[float]:
    """Close of the last bar STRICTLY BEFORE `start`. See decision 2. PURE.

    Bars carry `t` as an ISO date string, so a lexicographic compare is the
    correct one and needs no parsing.
    """
    prev = None
    for b in bars or []:
        if str(b.get("t") or "") >= start:
            break
        c = b.get("c")
        if isinstance(c, (int, float)) and c > 0:
            prev = float(c)
    return prev


def window_return(bars, start: str) -> Optional[float]:
    """Percent return from the pre-`start` anchor to the final bar. PURE."""
    a = anchor_close(bars, start)
    if not a:
        return None
    last = (bars or [])[-1].get("c") if bars else None
    if not isinstance(last, (int, float)) or last <= 0:
        return None
    return (float(last) / a - 1.0) * 100.0


def trailing_return(bars, n: int) -> Optional[float]:
    """Percent return over the last `n` bars. PURE."""
    b = bars or []
    if len(b) < n + 1:
        return None
    a, last = b[-(n + 1)].get("c"), b[-1].get("c")
    if not all(isinstance(x, (int, float)) and x > 0 for x in (a, last)):
        return None
    return (float(last) / float(a) - 1.0) * 100.0


def is_stale(bars, freshest: str, max_days: int = MAX_STALE_DAYS) -> bool:
    """Is this series a dead ticker? See decision 4. PURE.

    Compared in CALENDAR days against the freshest bar observed in the same
    run, so a market holiday or a short week never marks a live name dead.
    """
    last = _last_date(bars)
    if not last or not freshest:
        return True
    try:
        from datetime import date
        y1, m1, d1 = (int(x) for x in last.split("-")[:3])
        y2, m2, d2 = (int(x) for x in freshest.split("-")[:3])
        return (date(y2, m2, d2) - date(y1, m1, d1)).days > max_days
    except Exception:
        return True


def _median(vals) -> Optional[float]:
    clean = [v for v in vals if isinstance(v, (int, float))]
    return round(statistics.median(clean), 2) if clean else None


def _pct(n, d) -> Optional[float]:
    return round(100.0 * n / d, 1) if d else None


def _round(v, places: int = 2) -> Optional[float]:
    return round(float(v), places) if isinstance(v, (int, float)) else None


def group_row(name: str, members: list, frames: dict, start: str,
              freshest: str, etf: Optional[str] = None) -> dict:
    """One measured row. PURE given `frames`.

    `dropped` is reported rather than swallowed — a group where half the names
    were dead is a group whose median means little, and the reader must be able
    to see that.
    """
    rets, shorts, meds, kept, dropped = [], [], [], [], []
    for sym in members:
        bars = frames.get(sym) or []
        if not bars or is_stale(bars, freshest):
            dropped.append(sym)
            continue
        kept.append(sym)
        rets.append(window_return(bars, start))
        shorts.append(trailing_return(bars, WINDOW_SHORT))
        meds.append(trailing_return(bars, WINDOW_MED))

    live = [r for r in rets if isinstance(r, (int, float))]
    row = {
        "group": name,
        "n": len(kept),
        "dropped": len(dropped),
        "dropped_symbols": sorted(dropped)[:8],
        "median_window": _median(rets),
        "median_21d": _median(shorts),
        "median_63d": _median(meds),
        "pct_positive": _pct(sum(1 for r in live if r > 0), len(live)),
        "stance": STANCE.get(name),
    }
    if etf:
        bars = frames.get(etf) or []
        row["etf"] = etf
        row["etf_window"] = (None if not bars or is_stale(bars, freshest)
                             else round(window_return(bars, start) or 0.0, 2))
        # The gap IS the finding: how much of the move is mega-cap weighting.
        if row["etf_window"] is not None and row["median_window"] is not None:
            row["etf_vs_median"] = round(row["etf_window"] - row["median_window"], 2)
    return row


def _relativize(rows: list, bench: dict) -> list:
    """Restate every return relative to the benchmark. See decision 1."""
    for r in rows:
        for key, bkey in (("median_window", "window"), ("median_21d", "d21"),
                          ("median_63d", "d63")):
            v, b = r.get(key), bench.get(bkey)
            r[key.replace("median", "rel")] = (
                None if v is None or b is None else round(v - b, 2))
    return rows


def _sector_members(min_dollar_vol: float, min_price: float) -> dict:
    """Liquid operating companies grouped by sector, from the latest scan.

    Liquidity-gated on purpose: a sector median computed over names Ajay cannot
    get filled in is not a tradeable read.
    """
    from sepa import scanner

    scan = scanner.load_latest() or {}
    rows = scan.get("all_results") or scan.get("candidates") or []
    out: dict = {}
    unmapped = 0
    rows_out: list = []
    for r in rows:
        sym = (r.get("symbol") or "").upper()
        if not sym:
            continue
        liq = (r.get("liquidity") or {}).get("avg_dollar_vol")
        px = r.get("last_close")
        if not isinstance(liq, (int, float)) or liq < min_dollar_vol:
            continue
        if not isinstance(px, (int, float)) or px < min_price:
            continue
        # The scan row carries its own sector (2,667 of 2,974 rows as of
        # 2026-08-14). supply_demand.sectors is deliberately NOT used: it is a
        # curated AI-theme roster, a different question from "what sector is
        # this", and using it here would silently restrict the grid to names
        # someone had already tagged as AI-adjacent.
        sec = r.get("sector")
        if not sec:
            unmapped += 1
            continue
        out.setdefault(str(sec), []).append(sym)
        # Same population, one grain finer (2026-09-09). Collected HERE rather
        # than by a second scan read so the industry medians and the sector
        # medians can never be computed over different universes.
        rows_out.append((sym, str(sec), r.get("industry")))
    out["_unmapped"] = unmapped
    out["_rows"] = rows_out
    return out


# ── Per-member table (Ajay 2026-09-10) ──────────────────────────────────────
# "I would like to click on the sector category and see the related stocks list
# in a pop over to see which ones are gaining traction."
#
# The four grains a member table exists for. Havens are single-symbol proxies —
# a popover listing one name is not a popover, so they are not a grain.
MEMBER_GRAINS = ("sector", "cohort", "industry", "theme")

# The build payload's key, and the API's read key. Named once so a rename can
# never leave the endpoint reading a key the tracker stopped writing.
MEMBERS_KEY = "members"

# "Gaining traction" thresholds — see `traction_read` for what they gate. Both
# are 0.0 BY DEFINITION ("faster than its own month", "ahead of its own
# group"), not a level anyone measured. Constants so the gate is one edit, and
# so nothing here can be mistaken for a tested edge.
TRACTION_MIN_ACCEL_PP = 0.0
TRACTION_MIN_VS_GROUP_PP = 0.0

# How many dropped names a group prints. Same 8 as group_row's dropped_symbols.
MEMBER_UNPRICED_SAMPLE = 8

# Shipped WITH the number, every time it is served (his standing rule: any
# per-name measure on a board he trades ships its definition).
TRACTION_SPEC = {
    "field": "traction",
    "units": "percentage points per session",
    "formula": ("pace_5 = ret_5d/5 · pace_21 = ret_21d/21 · "
                "traction = pace_5 - pace_21 · "
                "vs_group_21 = ret_21d - the group's published median_21d · "
                "gaining = traction > %.1f AND vs_group_21 > %.1f"
                % (TRACTION_MIN_ACCEL_PP, TRACTION_MIN_VS_GROUP_PP)),
    "min_accel_pp": TRACTION_MIN_ACCEL_PP,
    "min_vs_group_pp": TRACTION_MIN_VS_GROUP_PP,
    "sort": "gaining desc, traction desc, vs_group_21 desc, symbol asc",
    "not_a_signal": ("A ranking of what already moved, like every other number "
                     "in this module. Not a buy signal and not advice."),
}

# The one line that keeps the popover from reading as the source of the median
# printed above it. Two populations, said out loud rather than reconciled.
MEMBER_NOTE = (
    "Full liquidity-filtered membership. The group median above this table is "
    "measured on the rotation grid's fixed sample of the group, so it is a "
    "DIFFERENT population from the rows below — median_21d_full is this "
    "table's own median. Shown side by side on purpose, not reconciled.")


def member_stats(bars, freshest: str) -> Optional[dict]:
    """The symbol half of a member row — everything that does NOT depend on
    which group the name is being viewed inside. PURE.

    None for a series that cannot be priced (no frame, or a dead ticker by
    decision 4) so the caller COUNTS the drop instead of printing a zero. Same
    staleness rule as `group_row`: one definition of "dead" in this module.
    """
    if not bars or is_stale(bars, freshest):
        return None
    last = bars[-1].get("c")
    if not isinstance(last, (int, float)) or last <= 0:
        return None
    out = {"last_close": round(float(last), 2)}
    for key, n in (("ret_1d", WINDOW_DAY), ("ret_5d", WINDOW_FAST),
                   ("ret_21d", WINDOW_SHORT), ("ret_63d", WINDOW_MED)):
        v = trailing_return(bars, n)
        out[key] = None if v is None else round(v, 2)
    return out


def traction_read(ret_fast, ret_short, group_median_21d) -> dict:
    """"Which ones are gaining traction", as a DEFINED number. PURE.

      pace_5      = ret_5d  / WINDOW_FAST    percent per session, last week
      pace_21     = ret_21d / WINDOW_SHORT   percent per session, last month
      traction    = pace_5 - pace_21         percentage points per session
      vs_group_21 = ret_21d - the group's published median_21d

      gaining     = traction > TRACTION_MIN_ACCEL_PP
                    AND vs_group_21 > TRACTION_MIN_VS_GROUP_PP

    TWO conditions, because either one alone lies. A name can accelerate while
    its whole group runs harder — it is being carried, not leading. And a name
    can lead a dead group while decelerating — it led LAST month. Traction is
    the name pulling ahead of its own group AND doing it faster this week than
    it managed over the month.

    Everything unknown fails closed: no 5-day frame, no 21-day frame, or no
    group median leaves traction / vs_group_21 None and `gaining` False. A name
    we cannot measure never ranks as the one gaining traction.
    """
    pace_f = None if not isinstance(ret_fast, (int, float)) else ret_fast / float(WINDOW_FAST)
    pace_s = None if not isinstance(ret_short, (int, float)) else ret_short / float(WINDOW_SHORT)
    traction = (None if pace_f is None or pace_s is None
                else round(pace_f - pace_s, 3))
    vs = (None if pace_s is None or not isinstance(group_median_21d, (int, float))
          else round(float(ret_short) - float(group_median_21d), 2))
    return {
        "pace_5": None if pace_f is None else round(pace_f, 3),
        "pace_21": None if pace_s is None else round(pace_s, 3),
        "traction": traction,
        "vs_group_21": vs,
        "gaining": bool(traction is not None and vs is not None
                        and traction > TRACTION_MIN_ACCEL_PP
                        and vs > TRACTION_MIN_VS_GROUP_PP),
    }


def traction_row(symbol: str, stat: dict, group_median_21d,
                 bench: Optional[dict] = None) -> dict:
    """One popover row: the persisted symbol stats plus the group-dependent
    half. PURE.

    Lives HERE and not in the API so `traction` has exactly one definition
    however many surfaces end up sorting on it — the same reason
    supply_demand.bounce_room owns "bouncing" for its three pages.

    `bench` restates each window against the benchmark (decision 1), because
    the CHIP the popover opens under prints rel_21d. Raw member returns beside
    a rebased chip number are two measures in one column. Rebased HERE rather
    than persisted per name: it is the same three subtractions for every row,
    so the table stores the benchmark's three returns once instead of 5,136
    derived numbers.

    `vs_group_21` is deliberately NOT rebased — it is a difference of two
    returns over the same window, so the benchmark cancels out of it. Rebasing
    both legs would print the identical number with a longer story.
    """
    stat = stat or {}
    row = {"symbol": symbol}
    for k in ("name", "sector", "industry", "last_close", "ret_1d", "ret_5d",
              "ret_21d", "ret_63d",
              "at_demand", "zone_role", "zone_depth_pct", "zone_off_floor_pct"):
        if k in stat:
            row[k] = stat[k]
    # No zone coverage is UNMARKED, never "not at demand" and never a drop.
    row.setdefault("at_demand", None)
    for key, bkey in (("rel_1d", "ret_1d"), ("rel_5d", "ret_5d"),
                      ("rel_21d", "ret_21d"),
                      ("rel_63d", "ret_63d")):
        v, b = stat.get(bkey), (bench or {}).get(bkey)
        row[key] = (None if not isinstance(v, (int, float))
                    or not isinstance(b, (int, float)) else round(v - b, 2))
    row.update(traction_read(stat.get("ret_5d"), stat.get("ret_21d"),
                             group_median_21d))
    return row


def traction_sort_key(row: dict):
    """gaining first, then traction, then the group-relative 21d, then symbol.
    PURE and total — no input raises.

    A None sorts LAST in every position: a name whose frame was too short to
    measure must never rank above one that was measured and won.
    """
    def num(v):
        return float(v) if isinstance(v, (int, float)) else float("-inf")

    return (0 if row.get("gaining") else 1,
            -num(row.get("traction")), -num(row.get("vs_group_21")),
            str(row.get("symbol") or ""))


def _zone_marks(closes: dict, day=None, docs=None) -> tuple:
    """({SYMBOL: mark}, meta) — which members are standing INSIDE a demand band.

    CONTEXT, never a gate. Nothing is dropped for lacking a zone; `unmarked`
    counts the names the store has no doc for (556 of 1,731 on 2026-09-10).

    ONE definition, imported: supply_demand.bounce_room.load_docs for the
    stored bands and `in_demand_read` for the read the SEPA 🪃 chip, the demand
    board and the phone's zone kinds already use. A second definition of "at
    demand" inside the rotation package would be a second answer to a question
    this app has already answered once.

    The price is the member's last CLOSED bar — the same frame every other
    number in this module is computed on. Deliberately not a live print: the
    rotation map is a daily read, and an intraday print would make the marker
    disagree with the returns sitting next to it.

    Imported inside the fence on purpose. A zone-store failure must degrade the
    MARKER — every name unmarked, `error` saying why — never the rotation build
    or the endpoint that reads it.
    """
    meta = {"day": None, "covered": 0, "unmarked": len(closes or {}),
            "at_demand": 0, "source": "unavailable", "error": None}
    if not closes:
        return {}, meta
    try:
        from supply_demand import bounce_room as BR, zone_store as ZS

        symbols = sorted(closes)
        if day is None:
            day = ZS.latest_store_day()
        if day is None:
            meta["error"] = "zone store is cold"
            return {}, meta
        if docs is None:
            docs, _missing = BR.load_docs(symbols, day)
        marks = {}
        for sym in symbols:
            doc = (docs or {}).get(sym)
            # A tombstone doc ("error") is NOT coverage — marking it "not at
            # demand" would print a measurement we never made.
            if not doc or doc.get("error"):
                continue
            read = BR.in_demand_read(closes.get(sym), doc)
            if read:
                marks[sym] = {"at_demand": True, "zone_role": read.get("role"),
                              "zone_depth_pct": read.get("depth_pct"),
                              "zone_off_floor_pct": read.get("off_floor_pct")}
            else:
                marks[sym] = {"at_demand": False}
        meta.update(day=str(day), covered=len(marks),
                    unmarked=len(closes) - len(marks),
                    at_demand=sum(1 for m in marks.values() if m["at_demand"]),
                    source="zone_store")
        return marks, meta
    except Exception as exc:                                   # noqa: BLE001
        log.warning("rotation: demand-zone marker unavailable: %s", exc)
        meta["error"] = f"{type(exc).__name__}: {exc}"[:120]
        return {}, meta


def _member_table(full_groups: dict, published: dict, labels: dict,
                  frames: dict, freshest: str,
                  bench: Optional[dict] = None) -> dict:
    """The per-member table behind the popover. PURE given `frames`, apart from
    the fenced demand-zone read.

    `full_groups`  {grain: {group: [FULL membership]}}
    `published`    {grain: {group: the row he actually sees}} — a group is in
                   the table ONLY if it survived the member floor and the
                   dead-ticker drops upstream, so every chip on the strip opens
                   on a table and no orphan table rides along in the payload.
    `labels`       {SYMBOL: (sector, industry)} from the same scan rows.

    Every symbol is priced ONCE into `by_symbol`, not once per group: a name
    sits in a sector, a cap-tier cohort, an industry and sometimes a theme, and
    duplicating its row four times would quadruple a payload that already
    crosses the wire into Mongo.
    """
    wanted = set()
    for grain, groups in full_groups.items():
        pub = published.get(grain) or {}
        for name, syms in groups.items():
            if name in pub:
                wanted |= {str(s).upper() for s in syms}

    by_symbol: dict = {}
    unpriced: list = []
    for sym in sorted(wanted):
        stat = member_stats(frames.get(sym), freshest)
        if stat is None:
            unpriced.append(sym)          # counted, never silently absent
            continue
        sec, ind = labels.get(sym) or (None, None)
        if sec:
            stat["sector"] = sec
        if ind:
            stat["industry"] = ind
        by_symbol[sym] = stat

    # The full-membership median is taken on UNROUNDED returns, exactly as
    # group_row takes the sampled one. Medianing the 2-dp row values instead
    # moved a same-population theme by 0.01 (ai_infra, 2026-09-10) — a
    # rounding artefact that would read on screen as a real disagreement
    # between the two medians. Never persisted; only the median uses it.
    raw_21 = {s: trailing_return(frames.get(s), WINDOW_SHORT) for s in by_symbol}
    # The same-day leg, per symbol, so each group can carry TODAY'S median.
    raw_1 = {s: trailing_return(frames.get(s), WINDOW_DAY) for s in by_symbol}
    # Company names (Ajay 2026-09-10: "Cna you add company name too next to
    # these tickers"). ONE cache read for the whole map -- 6,021 entries in
    # 0.12 s, covering 99% of the universe -- never name_for() per symbol,
    # which is a Mongo round trip each. CACHE ONLY: company_names.name_for
    # does not fetch, and warming is somebody else's cron. A name we do not
    # have is simply absent, never a blank row and never a provider call from
    # inside the rotation build.
    try:
        from sepa import company_names
        names = company_names.all_names() or {}
    except Exception as exc:                                # pragma: no cover
        log.warning("rotation: company names unavailable (%s) — rows ship "
                    "without them", exc)
        names = {}
    for sym, stat in by_symbol.items():
        nm = names.get(sym)
        if nm:
            stat["name"] = nm

    marks, zone_meta = _zone_marks({s: v["last_close"] for s, v in by_symbol.items()})
    for sym, stat in by_symbol.items():
        stat.update(marks.get(sym) or {"at_demand": None})

    groups_out: dict = {}
    for grain, groups in full_groups.items():
        pub = published.get(grain) or {}
        out: dict = {}
        for name, syms in groups.items():
            row = pub.get(name)
            if row is None:
                continue
            members = sorted({str(s).upper() for s in syms})
            priced = [s for s in members if s in by_symbol]
            missing = [s for s in members if s not in by_symbol]
            out[name] = {
                # Echoed from the published row so the endpoint can CROSS-CHECK
                # the sector / tier the clicked chip rode in with, instead of
                # re-parsing " · large caps" back out of a display label.
                "sector": row.get("sector"),
                "tier": row.get("tier"),
                "industry": row.get("industry"),
                # The number he already sees, over the grid's sample …
                "median_21d": row.get("median_21d"),
                "n_measured": row.get("n"),
                # The published row's POPULATION, not its survivors: n is what
                # priced, dropped is what did not, and their sum is the set the
                # grid actually sampled. `n_measured < n_full` looked like the
                # sampled test and is not — one dead name in a full-membership
                # group makes it true, and the popover then announces a sample
                # that was never taken (themes are never strided at all).
                "n_population": (row.get("n") or 0) + (row.get("dropped") or 0),
                # … and this table's own, over everything below it. Never
                # reconciled — see MEMBER_NOTE.
                "median_21d_full": _median([raw_21.get(s) for s in priced]),
                # TODAY, over the same full membership as the table below it.
                "median_1d_full": _median([raw_1.get(s) for s in priced]),
                "up_today": sum(1 for s in priced
                                if isinstance(raw_1.get(s), (int, float))
                                and raw_1[s] > 0),
                "n_full": len(members),
                "priced": len(priced),
                "unpriced": len(missing),
                "unpriced_symbols": missing[:MEMBER_UNPRICED_SAMPLE],
                "at_demand": sum(1 for s in priced
                                 if by_symbol[s].get("at_demand") is True),
                "zone_unmarked": sum(1 for s in priced
                                     if by_symbol[s].get("at_demand") is None),
                "symbols": priced,
            }
        groups_out[grain] = out

    return {
        "as_of": freshest,
        "windows": {"day": WINDOW_DAY, "fast": WINDOW_FAST,
                    "short": WINDOW_SHORT, "med": WINDOW_MED},
        # The benchmark's own three windows, stored ONCE. `traction_row`
        # subtracts them to rebase each member (decision 1) — the chip the
        # popover opens under prints rel_21d, so raw member returns beside it
        # would be two different measures sharing a column.
        "benchmark": dict(bench or {}),
        "traction": TRACTION_SPEC,
        "zone": zone_meta,
        "coverage": {"symbols": len(wanted), "priced": len(by_symbol),
                     "unpriced": len(unpriced),
                     "unpriced_symbols": unpriced[:MEMBER_UNPRICED_SAMPLE]},
        "by_symbol": by_symbol,
        "groups": groups_out,
        "note": MEMBER_NOTE,
    }


def build(start: str, min_dollar_vol: float = 20_000_000.0,
          min_price: float = 10.0, sample_per_group: int = 40) -> dict:
    """The rotation map: sectors, Ajay's themes, and safe havens, vs RSP.

    `start` is an ISO date. Returns are anchored on the last close strictly
    BEFORE it, identically for every symbol and for the benchmark.
    """
    from sepa import universe as U

    sectors = _sector_members(min_dollar_vol, min_price)
    unmapped = sectors.pop("_unmapped", 0)
    scan_rows = sectors.pop("_rows", [])
    # Cap per sector to bound the fetch. Deterministic stride, never random, so
    # the same request returns the same number twice.
    trimmed = {}
    sampled = {}
    for sec, syms in sectors.items():
        syms = sorted(syms)
        if len(syms) > sample_per_group:
            step = len(syms) / sample_per_group
            picked = [syms[int(i * step)] for i in range(sample_per_group)]
            sampled[sec] = {"of": len(syms), "used": len(picked)}
            syms = picked
        trimmed[sec] = syms

    themes = {k: list(v) for k, v in U.THEME_UNIVERSE.items()}

    # Sector × cap-tier cohorts (2026-08-31). Tiered from the FULL sector
    # membership before any sampling, so small-cap cohorts are not starved by
    # the sector stride.
    tiers = _tier_sets()
    cohorts = _cohort_members(sectors, tiers)
    industries = _industry_members(scan_rows)

    # FULL membership per grain, for the popover's member table (2026-09-10).
    # Same builders with the sample cap OFF, so a group's full roster can never
    # drift from the sampled row it opens underneath — one source, two views.
    full_groups = {
        "sector": {sec: sorted({s.upper() for s in syms})
                   for sec, syms in sectors.items()},
        "cohort": {c["label"]: c["members"]
                   for c in _cohort_members(sectors, tiers, sample=0)},
        "industry": {c["label"]: c["members"]
                     for c in _industry_members(scan_rows, sample=0)},
        "theme": {name: sorted({s.upper() for s in syms})
                  for name, syms in themes.items()},
    }

    wanted = {BENCHMARK, BENCHMARK_FALLBACK}
    wanted |= set(SECTOR_ETF.values()) | set(HAVEN_PROXY.values())
    for group in list(trimmed.values()) + list(themes.values()):
        wanted |= set(group)
    for c in cohorts:
        wanted |= set(c["members"])
    for c in industries:
        wanted |= set(c["members"])
    # ONE load for both purposes: the sampled rows and the full-membership
    # table read the SAME frames. A second pass would be duplicate provider
    # work (+6.4 s measured 2026-09-10) and could hand the two views a
    # different last bar for the same name.
    for groups in full_groups.values():
        for syms in groups.values():
            wanted |= set(syms)
    frames = _load(wanted)

    freshest = max((_last_date(b) for b in frames.values() if b), default="")

    bench_sym = BENCHMARK
    bench_bars = frames.get(BENCHMARK) or []
    if not bench_bars or is_stale(bench_bars, freshest):
        bench_sym = BENCHMARK_FALLBACK
        bench_bars = frames.get(BENCHMARK_FALLBACK) or []
    bench = {
        "symbol": bench_sym,
        "window": window_return(bench_bars, start),
        "d21": trailing_return(bench_bars, WINDOW_SHORT),
        "d63": trailing_return(bench_bars, WINDOW_MED),
    }

    sector_rows = _relativize(
        [group_row(sec, syms, frames, start, freshest, SECTOR_ETF.get(sec))
         for sec, syms in trimmed.items() if syms], bench)
    theme_rows = _relativize(
        [group_row(name, syms, frames, start, freshest)
         for name, syms in themes.items()], bench)
    haven_rows = _relativize(
        [group_row(label, [sym], frames, start, freshest)
         for label, sym in HAVEN_PROXY.items()], bench)
    cohort_rows = _relativize(
        [{**group_row(c["label"], c["members"], frames, start, freshest),
          "sector": c["sector"], "tier": c["tier"], "index": c["index"]}
         for c in cohorts], bench)
    industry_rows = _relativize(
        [{**group_row(c["label"], c["members"], frames, start, freshest),
          "sector": c["sector"], "industry": c["industry"]}
         for c in industries], bench)
    # A cohort can shrink below the floor AFTER dead tickers drop out.
    cohort_rows = [r for r in cohort_rows if (r.get("n") or 0) >= MIN_COHORT_N]
    industry_rows = [r for r in industry_rows if (r.get("n") or 0) >= MIN_INDUSTRY_N]

    for rows in (sector_rows, theme_rows, haven_rows, cohort_rows, industry_rows):
        rows.sort(key=lambda r: (r.get("rel_window") is None,
                                 -(r.get("rel_window") or 0)))

    def _stance(kind):
        vals = [r["rel_window"] for r in sector_rows
                if r.get("stance") == kind and r.get("rel_window") is not None]
        return _median(vals)

    # The "hot" ends, ranked by the LAST MONTH (rel_21d) rather than the full
    # window — "where is the money flowing RIGHT NOW" is a 21-day question,
    # while the tables stay sorted by the window like everything else. Only
    # cohorts with a computable 21d rank; a None must not sort as hottest.
    ranked = sorted((r for r in cohort_rows if r.get("rel_21d") is not None),
                    key=lambda r: -r["rel_21d"])
    hot = {
        "in": ranked[:5],
        "out": list(reversed(ranked[-5:])) if len(ranked) > 5 else [],
        "ranked_by": "rel_21d",
    }

    # The curated rosters, ranked at last (Ajay 2026-09-09: "robotics, energy
    # and optic fiber, constructipn like for data centers add these"). They
    # were computed from the start and never surfaced anywhere, so from the
    # boards it looked like they were not tracked. Thin ones are KEPT and
    # flagged rather than dropped — he asked for rare_earth (n=4) and nuclear
    # by name, and a four-name median is worth seeing as long as it says so.
    for r in theme_rows:
        r["thin"] = (r.get("n") or 0) < MIN_COHORT_N
    ranked_thm = sorted((r for r in theme_rows if r.get("rel_21d") is not None),
                        key=lambda r: -r["rel_21d"])
    hot_themes = {"in": ranked_thm[:6],
                  "out": list(reversed(ranked_thm[-6:])) if len(ranked_thm) > 6 else [],
                  "ranked_by": "rel_21d"}

    # The member table is built LAST, off the rows that SURVIVED — so a chip he
    # can click always opens on a table, and a group that was dropped upstream
    # never ships one.
    members = _member_table(
        full_groups,
        {"sector": {r["group"]: r for r in sector_rows},
         "cohort": {r["group"]: r for r in cohort_rows},
         "industry": {r["group"]: r for r in industry_rows},
         "theme": {r["group"]: r for r in theme_rows}},
        {sym: (sec, ind) for sym, sec, ind in scan_rows},
        frames, freshest,
        {"symbol": bench["symbol"],
         "ret_1d": _round(trailing_return(bench_bars, WINDOW_DAY)),
         "ret_5d": _round(trailing_return(bench_bars, WINDOW_FAST)),
         "ret_21d": _round(bench["d21"]), "ret_63d": _round(bench["d63"])})

    ranked_ind = sorted((r for r in industry_rows if r.get("rel_21d") is not None),
                        key=lambda r: -r["rel_21d"])
    hot_industries = {
        "in": ranked_ind[:8],
        "out": list(reversed(ranked_ind[-8:])) if len(ranked_ind) > 8 else [],
        "ranked_by": "rel_21d",
    }

    return {
        "start": start,
        "as_of": freshest,
        "benchmark": bench,
        "sectors": sector_rows,
        "themes": theme_rows,
        "havens": haven_rows,
        "cohorts": cohort_rows,
        "industries": industry_rows,
        "hot": hot,
        "hot_industries": hot_industries,
        "hot_themes": hot_themes,
        # ~350 KB of per-member rows behind the popover (2026-09-10). Persisted
        # with the build and served one group at a time by /rotation/members —
        # /rotation strips it, so no page pays for a table it did not open.
        MEMBERS_KEY: members,
        # Ajay's "safe havens vs in general" read, as a single number each.
        "stance": {"defensive": _stance("defensive"),
                   "cyclical": _stance("cyclical"),
                   "commodity": _stance("commodity")},
        "leaders": [r["group"] for r in sector_rows[:3]],
        "laggards": [r["group"] for r in sector_rows[-3:]],
        "sampled": sampled,
        "unmapped": unmapped,
        "note": ("Relative to %s (equal-weight). Median MEMBER return, not the "
                 "sector ETF. Dead tickers excluded. Measurement of what moved "
                 "— not a forecast and not a buy signal." % bench["symbol"]),
    }
