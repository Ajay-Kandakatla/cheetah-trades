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
    """
    out = []
    for sec, syms in sectors.items():
        pool = sorted({s.upper() for s in syms})
        for tier, index_name in CAP_TIERS:
            members = [s for s in pool if s in (tiers.get(tier) or ())]
            if len(members) < MIN_COHORT_N:
                continue
            if len(members) > sample:
                step = len(members) / sample
                members = [members[int(i * step)] for i in range(sample)]
            label = f"{sec} · {tier} caps"
            out.append({"label": label, "sector": sec, "tier": tier,
                        "index": index_name, "members": members})
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
    out["_unmapped"] = unmapped
    return out


def build(start: str, min_dollar_vol: float = 20_000_000.0,
          min_price: float = 10.0, sample_per_group: int = 40) -> dict:
    """The rotation map: sectors, Ajay's themes, and safe havens, vs RSP.

    `start` is an ISO date. Returns are anchored on the last close strictly
    BEFORE it, identically for every symbol and for the benchmark.
    """
    from sepa import universe as U

    sectors = _sector_members(min_dollar_vol, min_price)
    unmapped = sectors.pop("_unmapped", 0)
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
    cohorts = _cohort_members(sectors, _tier_sets())

    wanted = {BENCHMARK, BENCHMARK_FALLBACK}
    wanted |= set(SECTOR_ETF.values()) | set(HAVEN_PROXY.values())
    for group in list(trimmed.values()) + list(themes.values()):
        wanted |= set(group)
    for c in cohorts:
        wanted |= set(c["members"])
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
    # A cohort can shrink below the floor AFTER dead tickers drop out.
    cohort_rows = [r for r in cohort_rows if (r.get("n") or 0) >= MIN_COHORT_N]

    for rows in (sector_rows, theme_rows, haven_rows, cohort_rows):
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

    return {
        "start": start,
        "as_of": freshest,
        "benchmark": bench,
        "sectors": sector_rows,
        "themes": theme_rows,
        "havens": haven_rows,
        "cohorts": cohort_rows,
        "hot": hot,
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
