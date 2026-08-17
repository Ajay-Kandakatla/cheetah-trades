"""Chart-ready tiles for the three Chart Maps tabs.

WHY ONE ENDPOINT INSTEAD OF N FETCHES
-------------------------------------
A 24-tile grid assembled client-side is 1 board call + 24 `/sepa/price-bars`
round-trips, and every tile pops in separately. The geometry each tile needs
(which band, which lines, which marker) is also tab-specific, so putting it in
the browser means three different assembly paths in TypeScript. Instead the
server returns ONE uniform tile shape and the frontend renders it dumbly.

THE TILE CONTRACT (identical across tabs)
-----------------------------------------
    symbol, name, href            — where the tile links (SEPA detail + tab)
    bars   [{t,o,h,l,c,v}]        — daily candles, oldest first
    bands  [{kind,lo,hi,label}]   — filled price boxes (base, demand, supply)
    lines  [{price,label,tone}]   — horizontal levels (buy/stop/target/now)
    markers[{date,label,kind}]    — dated vertical marks
    stats  [{k,v}]                — the two or three numbers worth reading
    why    str                    — one line: why this chart is on the board
    theme  str|None               — quantum/nuclear/robotics/ai_semis/ai_infra

WHAT THIS MODULE DOES NOT DO
----------------------------
It never scans. Tabs 1 and 2 read caches that other schedulers fill
(`scanner.load_latest()`, `demand_reentry.cached_or_warm()`) and tab 3 reads a
Mongo ledger that only ever accumulates. A page load can therefore never block
on a 3-minute universe pass — the 524 that took the demand board down on
2026-08-14 came from exactly that mistake.

Not advice. Tab 3 in particular shows what DID happen to a sample of past
setups; it is a study aid, not a forecast.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("chart_maps.board")

TABS = ("vcp", "zones", "winners")

BARS_DEFAULT = 130          # ~6 months of daily bars — a base plus its run-up
BARS_MAX = 400
LIMIT_DEFAULT = 24
LIMIT_MAX = 60

# A VCP is only worth studying once it has actually tightened. vcp.py bands
# tightness as tight ≥70 / developing 40-69 / early <40; "Strong VCP" is the
# top band plus the scanner independently naming VCP as the entry setup.
STRONG_TIGHTNESS = 70

# "The relative strength (RS) ranking ... is no less than 70, but preferably in
# the 90s" — TTLAC §6 (ebook p.106) criterion 7; TLSW p.79. The trend template
# already enforces this, but it is carried separately so a rejection can NAME
# it: RS 43 is why AVGO was on this board and should not have been.
MIN_RS_RANK = 70

# Stage 2 requires "more up days and up weeks on above-average volume than down
# days and down weeks on above-average volume" (TLSW p.71-72). A ratio below 1
# means the opposite — institutions distributing into the base. Checked here
# directly because `accumulation_strength` only says "distributing" at <= 0.70,
# so AVGO's 0.91 reads "neutral" while failing the book's own test.
MIN_UP_DOWN_VOL_RATIO = 1.0

# Winners: the ledger races the measure-rule target against the stop over 21
# bars (patterns/history.py::_grade_pattern). Both touched on one bar counts
# as the stop, so `target_first` is already the pessimistic reading.
WIN_OUTCOME = "target_first"
LOSS_OUTCOME = "stop_first"

DISCLAIMER = ("Study board. Past pattern outcomes are a measured sample of what "
              "happened, not a forecast — position sizing and stops still decide "
              "the result. Not financial advice.")


# ---------------------------------------------------------------------------
# bars
# ---------------------------------------------------------------------------
def _norm_frame(df):
    """Lower-case the OHLCV columns. Returns None when unusable."""
    if df is None or getattr(df, "empty", True):
        return None
    out = df.rename(columns={c: str(c).lower() for c in df.columns})
    if not {"open", "high", "low", "close"} <= set(out.columns):
        return None
    return out


def _row_date(ts) -> str:
    return ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts)[:10]


def _frame_to_bars(df) -> list[dict]:
    bars: list[dict] = []
    for ts, row in df.iterrows():
        try:
            bars.append({
                "t": _row_date(ts),
                "o": round(float(row["open"]), 4),
                "h": round(float(row["high"]), 4),
                "l": round(float(row["low"]), 4),
                "c": round(float(row["close"]), 4),
                "v": float(row.get("volume") or 0.0),
            })
        except Exception:
            continue
    return bars


def bars_for(symbol: str, days: int = BARS_DEFAULT,
             around: Optional[str] = None, pad_after: int = 25) -> list[dict]:
    """Daily candles for `symbol`.

    `around` centres the window on a dated event (a pattern confirmation),
    keeping `days` bars of run-up before it and `pad_after` bars after so the
    outcome is visible. Without it, the trailing `days` bars.

    A date not in the frame falls back to the tail rather than returning empty
    — a missing session (holiday, halt, a ledger date recorded off-calendar)
    should degrade to a usable chart, not a blank tile.
    """
    from sepa import prices
    try:
        df = _norm_frame(prices.load_prices(symbol.upper()))
    except Exception as exc:
        log.debug("chart-maps: bars %s failed: %s", symbol, exc)
        return []
    if df is None:
        return []

    days = max(20, min(int(days or BARS_DEFAULT), BARS_MAX))
    if around:
        dates = [_row_date(d) for d in df.index]
        try:
            i = dates.index(str(around)[:10])
        except ValueError:
            i = -1
        if i >= 0:
            lo = max(0, i - days)
            hi = min(len(df), i + max(0, int(pad_after)) + 1)
            return _frame_to_bars(df.iloc[lo:hi])
    return _frame_to_bars(df.tail(days))


# ---------------------------------------------------------------------------
# shared tile helpers
# ---------------------------------------------------------------------------
def _name_for(symbol: str) -> Optional[str]:
    try:
        from sepa import company_names
        return company_names.name_for(symbol)
    except Exception:
        return None


def _theme(symbol: str) -> Optional[str]:
    try:
        from sepa import universe as U
        return U.theme_for(symbol)
    except Exception:
        return None


def _num(v) -> Optional[float]:
    """Coerce to a finite float, else None. Guards NaN reaching JSON."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def _href(symbol: str, tab: str) -> str:
    return f"/sepa/{symbol.upper()}?tab={tab}"


def _theme_rank(theme: Optional[str]) -> int:
    try:
        from sepa import universe as U
        return U.theme_rank(theme)
    except Exception:
        return 0 if theme else 99


# Chart window bounds for a zone tile. 130 = the non-Retina legibility limit
# (measured: candle gap falls under one device pixel past 127 bars at DPR 1);
# 252 = one trading year, just inside the Retina limit of 255.
ZONE_BARS_MIN = 130
ZONE_BARS_MAX = 252
# Padding so the oldest defining swing is not flush against the left edge.
ZONE_BARS_PAD = 15


def _zone_window(zone: Optional[dict]) -> int:
    """Bars needed to show the structure that defines this band. PURE.

    Falls back to the board default when a zone carries no `oldest_touch_bars`
    — an older cached payload, or a band built before the field existed.
    """
    oldest = _num((zone or {}).get("oldest_touch_bars"))
    if oldest is None:
        return BARS_DEFAULT
    return int(min(ZONE_BARS_MAX, max(ZONE_BARS_MIN, int(oldest) + ZONE_BARS_PAD)))


# ---------------------------------------------------------------------------
# Sort — Ajay 2026-08-17: "the same logic as In demand page from supply demand
# such as volume sort and you gave a dedicated dropdown can you add them"
# ---------------------------------------------------------------------------
# WHY THIS IS A BACKEND PARAM AND NOT A CLIENT-SIDE RE-SORT
#
# The Breakouts page sorts rows it already holds, which is honest there — it
# holds every breakout. This board does not. `_finish` ranks, applies
# MAX_PER_THEME, and then loads price bars for only `limit + BAR_BUFFER` tiles,
# because loading frames for all 265 matches to display 24 took minutes on a
# cold cache. So a dropdown that re-ordered what is on screen would sort the 24
# tiles THEME PRIORITY already chose — "highest volume" would mean "highest
# volume among the names the theme ranking happened to pick", which reads
# identically and means something else entirely.
#
# Sorting here, before the cut, is the only version of this feature that
# answers the question the label asks.

def _f(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


# ---------------------------------------------------------------------------
# Liquidity — Ajay 2026-08-17: "we want to make that average turn over is high
# for these"
# ---------------------------------------------------------------------------
# He was right to ask. The board inherits the SEPA scanner's gate, and that gate
# is an OR (sepa/adr.py:45):
#
#     liquid = avg_dollar_vol >= $20M  OR  avg_shares >= 200,000
#
# The shares branch is there so a genuinely tradeable small-cap is not excluded
# for having a low price. But it also admits names that are nowhere near
# institutional turnover. Measured on the live board, 2026-08-17 — 7 of the 17
# strong-VCP names passed on SHARES ONLY:
#
#     ANTX  $1.5M/day     BOLD $4.1M     WEST $5.4M     EGBN $8.5M
#     DIN  $11.2M         UHAL $15.0M    CADL $15.4M
#
# On the Back in Demand page's own scale ANTX is "illiquid" and three more are
# "thin" — so the same stock was reading differently on two of his surfaces.
#
# The thresholds are IMPORTED, not re-declared, so the two boards can never
# drift apart again.
try:
    from supply_demand.demand_reentry import (LIQ_DEEP_USD, LIQ_OK_USD,
                                              LIQ_THIN_USD)
except Exception:                                   # pragma: no cover
    LIQ_DEEP_USD, LIQ_OK_USD, LIQ_THIN_USD = 50_000_000.0, 10_000_000.0, 2_000_000.0

LIQ_TIERS = {"deep": LIQ_DEEP_USD, "ok": LIQ_OK_USD, "thin": LIQ_THIN_USD,
             "any": 0.0}

# Default floor. "ok" = $10M/day, the demand page's "comfortably tradeable in
# retail size". Deliberately not "any": a study board that teaches him the shape
# of a $1.5M/day base is teaching him a pattern he cannot actually trade.
DEFAULT_MIN_TIER = "ok"


def liquidity_tier(avg_dollar_vol: Optional[float]) -> Optional[str]:
    """Which tier this turnover sits in. PURE. Same scale as Back in Demand."""
    d = _f(avg_dollar_vol)
    if d is None:
        return None
    if d >= LIQ_DEEP_USD:
        return "deep"
    if d >= LIQ_OK_USD:
        return "ok"
    if d >= LIQ_THIN_USD:
        return "thin"
    return "illiquid"


def passes_liquidity(avg_dollar_vol: Optional[float], min_tier: str) -> bool:
    """Does this name clear the floor? PURE.

    An UNKNOWN turnover fails any real floor. The alternative — letting it
    through — means the one name whose liquidity we could not measure is the one
    that shows up unfiltered, which is exactly backwards.
    """
    floor = LIQ_TIERS.get(min_tier, LIQ_TIERS[DEFAULT_MIN_TIER])
    if floor <= 0:
        return True
    d = _f(avg_dollar_vol)
    return d is not None and d >= floor


def tile_metrics(row: dict) -> dict:
    """Sortable numbers for one row, from either row shape. PURE.

    Two producers feed this board: SEPA scan rows (`sepa.scanner`) and
    demand-reentry rows (`supply_demand.demand_reentry`). They spell liquidity
    differently — `liquidity.avg_dollar_vol` vs `liquidity.avg_dollar_vol_50` —
    so both spellings are read rather than making the callers normalise.
    """
    row = row or {}
    liq = row.get("liquidity") or {}
    vol = row.get("volume") or {}

    avg_dollar = _f(liq.get("avg_dollar_vol")) or _f(liq.get("avg_dollar_vol_50"))
    today_vol = _f(liq.get("today_vol")) or _f(vol.get("last_vol"))
    avg_vol = _f(liq.get("avg_vol_50")) or _f(vol.get("avg_vol_50"))

    # rvol: prefer the one the producer computed (it knows whether the session
    # is partial and suppresses the number rather than publishing a fraction of
    # a day against a full one). Only derive when it did not.
    rvol = _f(liq.get("rvol"))
    if rvol is None and today_vol and avg_vol and avg_vol > 0:
        rvol = today_vol / avg_vol

    today_dollar = _f(liq.get("today_dollar_vol"))
    if today_dollar is None and today_vol is not None:
        px = _f(row.get("last_close")) or _f(row.get("last_price"))
        if px:
            today_dollar = today_vol * px

    # Retail + off-exchange come from an intraday TAPE pull, never from a daily
    # bar, so they are only present once `attach_tape` has run. Reading them
    # here (rather than in a second extractor) keeps one definition of every
    # sortable number.
    ven = row.get("venues") or {}
    ret = row.get("retail") or {}

    return {
        "volume": today_vol,
        "rvol": rvol,
        "turnover": today_dollar,
        "avg_turnover": avg_dollar,
        "conviction": _f((row.get("conviction") or {}).get("score")
                         if isinstance(row.get("conviction"), dict)
                         else row.get("conviction")),
        "rs": _f(row.get("rs_rank")),
        "change": _f(row.get("day_change_pct")),
        # Same three the Back in Demand dropdown offers, same field names.
        "dark": _f(ven.get("dark_pct")),
        "retailimb": _f(ret.get("imbalance_pct")),
        "retailpct": _f(ret.get("retail_pct_of_volume")),
    }


# Dropdown options, in the order they are offered. `theme` is the default and
# keeps the board's existing behaviour exactly.
# Mirrors the Back in Demand dropdown (DemandReentryPanel.tsx SORTS) so the two
# surfaces mean the same thing by the same word — Ajay 2026-08-17: "exactly what
# you did in the other place". Retail imbalance, retail % and off-exchange % are
# the three that make it HIS dropdown rather than a generic one; they need the
# tape pull below. The trailing four have no equivalent there but come free from
# the scan row, so they are offered rather than withheld.
# Ajay 2026-08-17, on this dropdown:
#   "Remove default themes checked and AI sector from drop down… Volume instead
#    or turn over. What is turn over is it average volume?"
#
# THE WORD "TURNOVER" IS GONE FROM THIS DROPDOWN. It never meant average volume:
#   volume        today's SHARES traded          3.8M
#   turnover      today's DOLLARS traded         $265M   (shares x price)
#   avg_turnover  50-day average DOLLARS/day     $370M
# Three volume-ish entries with two different units and one ambiguous label is
# what made the question necessary. `turnover` is dropped — it ranks nearly the
# same names as today's volume, differing only by price — and the survivors say
# their unit in the label.
#
# `avg_turnover` STAYS despite carrying the word internally: it is the number
# behind the liquidity floor he asked for earlier the same day ("we want to make
# that average turn over is high for these"), and its key is referenced by
# `passes_liquidity`. Only its label changes.
SORTS: dict[str, str] = {
    "default": "⭐ Best setup first",
    "retailimb": "🧍 Retail imbalance",
    "retailpct": "🧍 Retail % of volume",
    "dark": "🟣 Off-exchange %",
    "rvol": "📊 Relative volume",
    "volume": "📈 Volume today (shares)",
    "avg_turnover": "🏦 Avg daily volume ($)",
    "conviction": "🏆 Conviction",
    "rs": "⚡ RS rank",
}

# Sorts that cannot be answered from a daily bar. Choosing one triggers the tape
# pull; without it the column is null for every row and the "sort" is a no-op
# that silently returns the default order — which is what happens on the demand
# page today, where only the top 15 rows are ever enriched.
TAPE_SORTS = ("retailimb", "retailpct", "dark")

# The non-explicit ordering: the tab's own score (base tightness for VCP, R:R
# for demand), optionally led by theme when `themes_first` is on.
#
# It used to be the key "theme", labelled "🤖 AI sectors (default)" — which was
# two claims in one entry. The theme lead is the CHECKBOX; this is the ordering
# that applies when no metric is chosen. Separating them is what lets the
# checkbox default OFF (Ajay 2026-08-17: "Remove default themes checked and AI
# sector from drop down") without also removing the concept of a default order.
DEFAULT_SORT = "default"

# Themes no longer lead by DEFAULT — Ajay 2026-08-17: "Remove default themes
# checked". The checkbox stays, so the AI-ecosystem lead is one click away; it
# is simply no longer imposed on a board he opens to study whatever is working.
#
# Note this is narrower than his standing "breakout lists lead with AI sectors"
# rule: /chart-maps is a study surface, not a breakout list, and the ranking it
# forced was also silently reshuffling the per-theme spread cap underneath every
# other control on the page.
THEMES_FIRST_DEFAULT = False


# Tape enrichment budget. Mirrors demand_reentry's own numbers so the two
# surfaces cost the same per row; the board only ever enriches the tiles it is
# about to show, which is far fewer than the demand page's 15-of-hundreds.
TAPE_BUDGET_SEC = 25.0
TAPE_WORKERS = 6
# How deep to enrich before re-sorting on a tape metric, as a multiple of the
# page size. 3x24 = 72 tape pulls at 6 workers inside a 25s budget.
TAPE_POOL_MULT = 3


def attach_tape(rows: list, budget_sec: float = TAPE_BUDGET_SEC) -> int:
    """Pull each row's intraday tape for venue + retail detail, in place.

    Returns how many rows actually got data.

    This is the ONLY way to answer "retail imbalance" or "off-exchange %" — a
    daily bar carries one consolidated volume number and no venue breakdown at
    all. `sepa.scanner` rows have no `venues`/`retail` key whatsoever (checked
    2026-08-17), so without this the three tape sorts would rank a column that
    is null for every row and silently return the default order.

    Concurrent and time-boxed, reusing demand_reentry's own worker so the two
    surfaces cannot disagree about what "retail" or "dark" means. Rows that miss
    the budget are left without detail rather than holding up the response —
    they sort last, and the caller reports the count so the UI can say so.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from datetime import date as _d
    import time as _time

    if not rows:
        return 0
    try:
        from orderflow import darkpool, quotes as quotes_mod, retail as retail_mod, tape as tape_mod
        from supply_demand.demand_reentry import _enrich_one
    except Exception as exc:
        log.warning("chart-maps: tape enrichment unavailable: %s", exc)
        return 0

    t0 = _time.time()
    done = 0
    try:
        with ThreadPoolExecutor(max_workers=TAPE_WORKERS) as pool:
            futures = {pool.submit(_enrich_one, r, tape_mod, quotes_mod,
                                   darkpool, retail_mod, _d): r for r in rows}
            for fut in as_completed(futures, timeout=budget_sec + 5):
                if _time.time() - t0 > budget_sec:
                    break
                row = futures[fut]
                try:
                    got = fut.result()
                except Exception:
                    continue
                if not got:
                    continue
                row["venues"] = got.get("venues") or {}
                row["retail"] = got.get("retail") or {}
                done += 1
    except Exception as exc:
        log.debug("chart-maps: tape enrichment ended early: %s", exc)
    return done


def _sort_key(tile: dict, themes_first: bool, sort: str = DEFAULT_SORT):
    """Theme names lead when asked (Ajay's standing rule that any board leads
    with the AI-ecosystem winners), ordered BETWEEN themes by his stated
    priority — space, quantum, semis, optical, robotics, infra, nuclear — then
    the tab's own metric descending.

    Before 2026-08-16 this was binary (theme / no theme), so the board could
    answer "is this a theme name?" but never "which theme leads?".

    An explicit metric REPLACES the theme ranking rather than tie-breaking
    inside it — picking "Today's volume" and still getting space names first
    would not be a volume sort. A tile with no value for the chosen metric goes
    last, never first: missing data must not masquerade as a top result. The
    tab's own score breaks ties so the order stays stable.
    """
    if sort != DEFAULT_SORT and sort in SORTS:
        v = (tile.get("_m") or {}).get(sort)
        return (0 if v is not None else 1, -(v or 0.0), -(tile.get("_score") or 0.0))
    rank = _theme_rank(tile.get("theme")) if themes_first else 1
    return (rank, -(tile.get("_score") or 0.0), 0.0)


# Spare tiles fetched beyond `limit`, to cover symbols whose price frame turns
# out to be missing or too short to chart.
BAR_BUFFER = 6
BAR_WORKERS = 8

# Most tiles any single theme may occupy on one board.
#
# Ordering alone is not enough once the rosters are this big: space + quantum +
# ai_semis is 33 names, so on a strong day for one theme the top-priority
# roster could take all 24 slots and Ajay would never see the optical or
# robotics setups he explicitly asked to watch. The cap keeps the board a
# STUDY surface — a spread of what is working — rather than a single-sector
# feed. Priority still decides who leads and who gets cut when slots run out.
MAX_PER_THEME = 6


def _spread(tiles: list[dict], limit: int) -> list[dict]:
    """Apply MAX_PER_THEME, keeping overflow as a tail in case slots remain.

    Overflow is not discarded: if the capped set cannot fill `limit` (a quiet
    day, or one theme is the only thing setting up), the best of the overflow
    is appended in rank order rather than showing a half-empty board. PURE.
    """
    kept: list[dict] = []
    spill: list[dict] = []
    seen: dict[str, int] = {}
    for t in tiles:
        theme = t.get("theme")
        if not theme:
            kept.append(t)
            continue
        n = seen.get(theme, 0)
        if n < MAX_PER_THEME:
            seen[theme] = n + 1
            kept.append(t)
        else:
            spill.append(t)
    return kept + spill


def _finish(tiles: list[dict], limit: int, themes_first: bool, days: int,
            sort: str = DEFAULT_SORT,
            min_tier: str = DEFAULT_MIN_TIER) -> tuple[list[dict], dict]:
    """Rank on metadata, THEN load bars for only the tiles that will be shown.

    Ordering matters for latency, not just tidiness. Ranking after fetching
    meant loading price frames for every match — 265 names to display 24. On a
    cold price cache that is minutes, and minutes is a 524. Sorting first caps
    the work at `limit + BAR_BUFFER` frames regardless of how many matched.
    """
    explicit = sort != DEFAULT_SORT and sort in SORTS

    # 1 — the liquidity floor, before anything else. Ajay 2026-08-17: "we want
    # to make that average turn over is high for these". Dropping here rather
    # than filtering the finished board means the limit is filled with names
    # that CLEAR the floor instead of leaving gaps where thin names were cut.
    kept = [t for t in tiles if passes_liquidity((t.get("_m") or {}).get("avg_turnover"),
                                                 min_tier)]
    dropped_thin = len(tiles) - len(kept)
    tiles = kept

    tiles.sort(key=lambda t: _sort_key(t, themes_first, sort))

    # 2 — the tape pull, for the three sorts a daily bar cannot answer.
    #
    # Enriching every match is not affordable (one tape + NBBO fetch per symbol,
    # hundreds of matches). So the pool is the top TAPE_POOL_MULT * limit by the
    # ORDINARY ranking, enriched, then re-sorted by the tape metric. That is a
    # real limit and it is the same one the demand page has — it enriches its
    # top 15 by R:R — but it must be SAID rather than implied, so the count goes
    # back to the caller and onto the page.
    tape_pool = 0
    tape_enriched = 0
    sort_unavailable = None
    if sort in TAPE_SORTS:
        pool = tiles[:min(len(tiles), max(limit, limit * TAPE_POOL_MULT))]
        tape_pool = len(pool)
        tape_enriched = attach_tape(pool)
        for t in pool:
            t["_m"] = tile_metrics(t)          # re-read now that venues/retail exist
        pool.sort(key=lambda t: _sort_key(t, themes_first, sort))
        tiles = pool + tiles[len(pool):]

        # Did the chosen column actually come back with anything? "Retail
        # imbalance" cannot be answered outside a live session at all: signing a
        # retail print buy-vs-sell needs the NBBO, and orderflow.retail refuses
        # to guess — "Retail prints identified but unsigned; sub-penny signing
        # mis-signs 28% of trades". Measured off-session on USB: dark_pct 16.3
        # and retail_pct 2.3 both present, imbalance_pct null.
        #
        # A sort over an all-null column returns the default order, which looks
        # like a working sort and is not one. Say so instead.
        have = sum(1 for t in pool if (t.get("_m") or {}).get(sort) is not None)
        if not have:
            sort_unavailable = (
                "Retail buys and sells cannot be told apart without live NBBO "
                "quotes, so this ranking is unavailable outside market hours — "
                "the board is showing its default order."
                if sort == "retailimb" else
                "No data for this ranking in the last session — the board is "
                "showing its default order.")

    # 3 — the per-theme cap keeps the board a SPREAD, which is the right default
    # for a study surface. But it fights an explicit ranking: capping a volume
    # sort would silently drop the 7th-highest-volume name for being in a
    # popular theme, and the board would no longer be what the dropdown says.
    if themes_first and not explicit:
        tiles = _spread(tiles, limit)

    short = tiles[:limit + BAR_BUFFER]
    _attach_bars(short, days)
    out = [t for t in short if t.get("bars")][:limit]
    for t in out:
        t.pop("_score", None)
        t.pop("_bars", None)
        t.pop("_m", None)
        t.pop("venues", None)
        t.pop("retail", None)
    # Returned, not stashed on the function: `board()` runs inside
    # asyncio.to_thread and two concurrent requests would clobber a module-level
    # slot, handing one caller the other's counts.
    return out, {"dropped_thin": dropped_thin, "min_tier": min_tier,
                 "tape_pool": tape_pool, "tape_enriched": tape_enriched,
                 "sort_unavailable": sort_unavailable}


def _attach_bars(tiles: list[dict], days: int) -> None:
    """Fill `bars` on each tile, concurrently. Mutates in place.

    Time-boxed by the pool rather than per-task: every miss simply leaves
    `bars` empty and the tile is dropped, so a slow or delisted name costs one
    empty slot instead of the whole board.
    """
    if not tiles:
        return
    from concurrent.futures import ThreadPoolExecutor

    def _one(t: dict):
        spec = t.get("_bars") or {}
        try:
            t["bars"] = bars_for(t["symbol"],
                                 days=spec.get("days") or days,
                                 around=spec.get("around"),
                                 pad_after=spec.get("pad_after", 25))
        except Exception as exc:
            log.debug("chart-maps: bars %s failed: %s", t.get("symbol"), exc)
            t["bars"] = []

    with ThreadPoolExecutor(max_workers=BAR_WORKERS) as pool:
        list(pool.map(_one, tiles))


# ---------------------------------------------------------------------------
# tab 1 — strong VCP
# ---------------------------------------------------------------------------
def strong_vcp_reject(row: dict) -> Optional[str]:
    """Why this chart is NOT a Minervini VCP setup, or None if it qualifies.

    Returns the REASON rather than a bool so the rejection is inspectable and
    testable — "AVGO fails on rs_rank" beats "AVGO returned False".

    WHY THIS GOT STRICTER (Ajay 2026-08-16, looking at AVGO on the board):
    "our SEPA VCP has a problem.. We are not differentiating between Institution
    selling vs not selling.. Its not stage 2 now. Make sure it also has a base
    formed not institutions selling."

    He was right. The first version asked only two questions — is the setup
    named VCP, and is the base tight — and AVGO passed both while failing
    almost everything the book actually requires:

        is_candidate    False   (trend template not met)
        rs_rank         43      (book wants >= 70, "preferably in the 90s")
        base_count      6       (is_avoid_stage True)
        up/down vol     0.91    (more volume on down days than up)
        accumulation    False

    THE GATES, each with its source
    -------------------------------
    1. Trend Template FIRST. "Stocks must first meet my Trend Template to be
       considered a potential SEPA candidate" — TLSW p.34. That is exactly what
       `is_candidate` encodes (trend.pass_all AND liquidity.liquid, p.79).
    2. RS >= 70. "The relative strength (RS) ranking ... is no less than 70, but
       preferably in the 90s" — TTLAC §6 (ebook p.106) criterion 7; TLSW p.79.
       Carried explicitly as well as via the template, because it is the single
       criterion AVGO failed and it must be visible in the reject reason.
    3. Stage 2 only. "Stage 2 - Advancing phase: accumulation / Stage 3 -
       Topping phase: distribution" — TLSW p.66, TTLAC §6 (ebook p.104).
       Institutions selling IS Stage 3 by definition.
    4. Not a late-stage base. "By the time a fourth or fifth base occurs ... the
       trend is ... definitely in its late stages. By this point, abrupt base
       failures" — TLSW p.81. `base_count.is_avoid_stage` encodes it.
    5. Not under distribution. Stage 2 requires "more up days and up weeks on
       above-average volume than down days and down weeks on above-average
       volume" — TLSW p.71-72. Checked DIRECTLY here, because the coarse
       `accumulation_strength` label reads "neutral" at AVGO's 0.91 ratio.
    6. The base is tight. Contractions "correct less and less from left to
       right on successively lower volume" — TTLAC §6 (ebook p.110).
    """
    setup = row.get("entry_setup") or {}
    if (setup.get("type") or "").upper() != "VCP":
        return "no VCP setup"

    vcp = row.get("vcp") or {}
    t = _num(vcp.get("tightness"))
    if t is None or t < STRONG_TIGHTNESS:
        return f"base not tight enough (tightness {t if t is not None else '—'})"

    # 1 — the template gate, the book's own step one
    if not row.get("is_candidate"):
        return "fails the trend template (not a SEPA qualifier)"

    # 2 — RS floor, stated explicitly
    rs = _num(row.get("rs_rank"))
    if rs is not None and rs < MIN_RS_RANK:
        return f"RS {int(rs)} below {MIN_RS_RANK}"

    # 3 — Stage 2 only
    stage = (row.get("stage") or {}).get("stage")
    if stage is not None and int(stage) != 2:
        return f"stage {stage}, not Stage 2 (advancing/accumulation)"

    # 4 — base count
    bc = row.get("base_count") or {}
    if bc.get("is_avoid_stage") or bc.get("is_late_stage"):
        return f"late-stage base #{bc.get('base_count')}"

    # 5 — institutions must not be net sellers
    vol = row.get("volume") or {}
    ratio = _num(vol.get("up_down_vol_ratio"))
    if ratio is not None and ratio < MIN_UP_DOWN_VOL_RATIO:
        return f"distribution: up/down volume {ratio:.2f}"
    up_d, dn_d = vol.get("up_days_on_avg_vol"), vol.get("dn_days_on_avg_vol")
    if isinstance(up_d, int) and isinstance(dn_d, int) and dn_d > up_d:
        return f"more down days on volume than up ({dn_d} vs {up_d})"
    if (vol.get("accumulation_strength") or "").lower() == "distributing":
        return "volume tape is distributing"
    if row.get("distribution"):
        return "flagged under distribution"

    return None


def _is_strong_vcp(row: dict) -> bool:
    return strong_vcp_reject(row) is None


def vcp_tiles(limit: int = LIMIT_DEFAULT, days: int = BARS_DEFAULT,
              themes_first: bool = THEMES_FIRST_DEFAULT, min_tightness: int = STRONG_TIGHTNESS,
              sort: str = DEFAULT_SORT, min_tier: str = DEFAULT_MIN_TIER) -> dict:
    from sepa import scanner

    scan = scanner.load_latest()
    if not scan:
        return {"tiles": [], "note": "no SEPA scan on disk yet — run a scan first"}

    rows = scan.get("all_results") or scan.get("candidates") or []
    picked = []
    for r in rows:
        if not _is_strong_vcp(r):
            continue
        v = r.get("vcp") or {}
        if (_num(v.get("tightness")) or 0) < min_tightness:
            continue
        picked.append(r)

    tiles = []
    for r in picked:
        sym = (r.get("symbol") or "").upper()
        if not sym:
            continue
        v = r.get("vcp") or {}
        setup = r.get("entry_setup") or {}
        base_hi, base_lo = _num(v.get("base_high")), _num(v.get("base_low"))
        pivot = _num(v.get("pivot_buy_price")) or _num(setup.get("pivot"))
        stop = _num(v.get("suggested_stop")) or _num(setup.get("stop"))
        tight = _num(v.get("tightness"))

        bands = []
        if base_hi is not None and base_lo is not None and base_hi > base_lo:
            bands.append({"kind": "base", "lo": base_lo, "hi": base_hi,
                          "label": f"base {v.get('base_bars') or '?'}d"})
        lines = []
        if pivot is not None:
            lines.append({"price": pivot, "label": "PIVOT", "tone": "buy"})
        if stop is not None:
            lines.append({"price": stop, "label": "STOP", "tone": "stop"})

        drivers = [d for d in (v.get("tightness_drivers") or []) if d]
        stats = [{"k": "Tightness", "v": f"{int(tight)}" if tight is not None else "—"},
                 {"k": "Contractions", "v": str(v.get("n_contractions") or "—")},
                 {"k": "Final", "v": (f"{_num(v.get('final_contraction_pct')):.1f}%"
                                      if _num(v.get('final_contraction_pct')) is not None else "—")}]
        rs = _num(r.get("rs_rank"))
        if rs is not None:
            stats.append({"k": "RS", "v": str(int(rs))})

        tiles.append({
            "symbol": sym,
            "name": r.get("name") or _name_for(sym),
            "href": _href(sym, "setup"),
            "bars": [],
            "bands": bands,
            "lines": lines,
            "markers": [],
            "stats": stats,
            "why": " · ".join(drivers) if drivers else "VCP base tightening",
            "theme": _theme(sym),
            "badges": _vcp_badges(r),
            "_score": tight or 0.0,
            "_m": tile_metrics(r),
        })
    out, meta = _finish(tiles, limit, themes_first, days, sort, min_tier)
    return {"tiles": out, **meta,
            "matched": len(picked),
            "scanned": len(rows),
            "scan_generated_at": scan.get("generated_at")}


def _vcp_badges(row: dict) -> list[dict]:
    """Tier badges. `is_candidate` is the WATCHLIST tier (trend + liquidity,
    p.79), NOT a buy — labelling it 'buyable' is the exact mislabel the
    2026-05-28 book-alignment pass fixed, so the words stay distinct."""
    out = []
    if row.get("is_buyable"):
        out.append({"text": "Buyable", "tone": "good"})
    elif row.get("setup_ready"):
        out.append({"text": "Setup ready", "tone": "warn"})
    elif row.get("is_candidate"):
        out.append({"text": "Qualifier", "tone": "muted"})
    if (row.get("vcp") or {}).get("volume_drying"):
        out.append({"text": "Vol drying", "tone": "good"})
    return out


# ---------------------------------------------------------------------------
# tab 2 — pullbacks into demand
# ---------------------------------------------------------------------------
def zone_tiles(limit: int = LIMIT_DEFAULT, days: int = BARS_DEFAULT,
               universe: str = "sp1500_plus", themes_first: bool = THEMES_FIRST_DEFAULT,
               sort: str = DEFAULT_SORT, min_tier: str = DEFAULT_MIN_TIER) -> dict:
    from supply_demand import demand_reentry as D

    data = D.cached_or_warm(universe, limit=LIMIT_MAX)
    if data.get("warming"):
        # Deliberately non-blocking: the board warms in a background thread and
        # the page polls. Never wait here (see the 2026-08-14 524).
        # Same live counter the Back in Demand tab shows. Both tabs read the
        # SAME demand_reentry cache, so they are watching one scan — showing it
        # in one place and a static sentence in the other is what made Ajay ask
        # whether the two pages were even being updated together (2026-08-17).
        return {"tiles": [], "warming": True,
                "universe_key": data.get("universe_key") or universe,
                "progress": data.get("progress"),
                "note": "scanning for demand-zone pullbacks…"}

    rows = [r for r in (data.get("rows") or []) if r.get("is_reentry")]
    tiles = []
    for r in rows:
        sym = (r.get("symbol") or "").upper()
        if not sym:
            continue
        plan = r.get("plan") or {}
        zone = r.get("entry_zone") or {}

        bands = []
        z_lo, z_hi = _num(zone.get("lo")), _num(zone.get("hi"))
        if z_lo is not None and z_hi is not None:
            bands.append({"kind": "demand", "lo": z_lo, "hi": z_hi, "label": "demand"})
        for s in (r.get("supply_zones") or [])[:2]:
            s_lo, s_hi = _num(s.get("lo")), _num(s.get("hi"))
            if s_lo is not None and s_hi is not None:
                bands.append({"kind": "supply", "lo": s_lo, "hi": s_hi, "label": "supply"})

        lines = []
        for key, label, tone in (("entry_ref", "BUY", "buy"),
                                 ("stop", "STOP", "stop"),
                                 ("target", "TARGET", "target")):
            p = _num(plan.get(key))
            if p is not None:
                lines.append({"price": p, "label": label, "tone": tone})

        rr = _num(plan.get("rr"))
        be = _num(r.get("breakeven_win_pct"))
        liq = r.get("liquidity") or {}
        stats = [{"k": "R:R", "v": f"{rr:.1f}R" if rr is not None else "—"},
                 {"k": "Break-even", "v": f"{be:.0f}%" if be is not None else "—"},
                 {"k": "Liquidity", "v": (liq.get("tier") or "—")},
                 {"k": "Back in", "v": (f"{r.get('bars_since_above')}d"
                                        if r.get("bars_since_above") is not None else "—")}]

        fell = _num(r.get("fell_from_pct"))
        why = ((r.get("verdict") or {}).get("entry_read")
               or (f"pulled back {fell:.0f}% into a demand zone it had left"
                   if fell is not None else "back inside a demand zone"))

        tiles.append({
            "symbol": sym,
            "name": r.get("name") or _name_for(sym),
            "href": _href(sym, "supply"),
            "bars": [],
            # Per-TILE window, not the board default. Zones are computed over
            # 252 bars while the board charted 130, so a band could be drawn
            # with every touch that defines it off-screen — measured
            # 2026-08-16, and Ajay studies these charts to learn the pattern.
            # Reach back far enough to show the oldest defining swing, clamped
            # so a legible chart is never traded away: 130 is the floor (the
            # non-Retina legibility limit) and 252 the ceiling (the Retina one,
            # measured at 255). Median lands ~156 rather than a flat 252, which
            # is why this costs ~52KB instead of ~248KB on a 24-tile board.
            "_bars": {"days": _zone_window(zone)},
            "bands": bands,
            "lines": lines,
            "markers": [],
            "stats": stats,
            "why": why,
            "theme": _theme(sym),
            "badges": _zone_badges(r),
            "_score": rr or 0.0,
            "_m": tile_metrics(r),
        })
    out, meta = _finish(tiles, limit, themes_first, days, sort, min_tier)
    return {"tiles": out, **meta,
            "matched": len(rows),
            "universe_key": data.get("universe_key"),
            "universe_label": data.get("universe_label"),
            "scanned": data.get("scanned"),
            "generated_at": data.get("generated_at")}


def _zone_badges(r: dict) -> list[dict]:
    out = []
    v = (r.get("verdict") or {}).get("state")
    if v:
        out.append({"text": str(v).title(),
                    "tone": {"enter": "good", "watch": "warn"}.get(str(v).lower(), "muted")})
    sweep = (r.get("sweep") or {}).get("state")
    if sweep == "swept":
        out.append({"text": "Liquidity swept", "tone": "good"})
    rating = (r.get("venues") or {}).get("rating")
    if rating:
        out.append({"text": f"Dark {rating}", "tone": "muted"})
    return out


# ---------------------------------------------------------------------------
# tab 3 — previously winning patterns
# ---------------------------------------------------------------------------
def _pattern_label(p: str) -> str:
    return (p or "").replace("_", " ").title()


def zone_winner_tiles(limit: int = LIMIT_DEFAULT, days: int = 90) -> dict:
    """Demand-zone re-entries that reached target before stop.

    Ajay 2026-08-16: "In the past winners tab I wanna see the deman zones that
    were successful as well please."

    Source is the walk-forward backtest ledger written by
    `supply_demand.zone_backtest` (kind='zone', backtested=True), NOT live
    observations — there were none, the outcome was never recorded before now.
    Every row is a no-lookahead score: the decision saw bars only up to its own
    day, entry is the NEXT session's open, and a bar containing both stop and
    target counts as a loss.

    HONESTY: the same-bar wins are excluded here. 135 of 694 backtested trades
    hit their target on the entry bar itself because the first supply band sat
    a fraction above entry — those charts teach nothing about a re-entry, they
    just show a target that was never far away.
    """
    from patterns import history

    coll = history._coll()
    if coll is None:
        return {"tiles": [], "note": "zone ledger unavailable"}

    try:
        rows = list(coll.find({"kind": "zone",
                               "outcome": {"$in": [WIN_OUTCOME, LOSS_OUTCOME]}},
                              {"_id": 0}))
    except Exception as exc:
        log.warning("chart-maps: zone winners query failed: %s", exc)
        return {"tiles": [], "note": "zone ledger unavailable"}

    usable = [o for o in rows if (o.get("bars_to_outcome") or 0) > 0]
    wins = [o for o in usable if o.get("outcome") == WIN_OUTCOME]
    losses = [o for o in usable if o.get("outcome") == LOSS_OUTCOME]
    wins.sort(key=lambda o: str(o.get("et_date") or ""), reverse=True)

    tiles = []
    for i, o in enumerate(wins):
        sym = (o.get("symbol") or "").upper()
        confirm = str(o.get("confirmed_date") or o.get("et_date") or "")[:10]
        if not sym or not confirm:
            continue
        lo, hi = _num(o.get("zone_lo")), _num(o.get("zone_hi"))
        entry, tgt, stp = (_num(o.get("entry_open")), _num(o.get("target")),
                           _num(o.get("stop")))

        bands = []
        if lo is not None and hi is not None and hi > lo:
            bands.append({"kind": "demand", "lo": lo, "hi": hi, "label": "demand"})
        lines = []
        for v, label, t in ((entry, "BUY", "buy"), (stp, "STOP", "stop"),
                            (tgt, "TARGET", "target")):
            if v is not None:
                lines.append({"price": v, "label": label, "tone": t})

        bto = o.get("bars_to_outcome")
        net = _num(o.get("net_pct"))
        rr = _num(o.get("rr"))
        stats = [{"k": "Entered", "v": confirm},
                 {"k": "Bars to target", "v": str(bto) if bto is not None else "—"},
                 {"k": "Net", "v": f"+{net:.1f}%" if net is not None else "—"},
                 {"k": "Planned R:R", "v": f"{rr:.1f}" if rr is not None else "—"}]
        fell = _num(o.get("fell_from_pct"))
        if fell is not None:
            stats.append({"k": "Fell from", "v": f"{fell:.0f}%"})

        tiles.append({
            "symbol": sym,
            "name": _name_for(sym),
            "href": _href(sym, "supply"),
            "bars": [],
            "_bars": {"around": confirm,
                      "pad_after": int(bto or 21) + 12},
            "bands": bands,
            "lines": lines,
            "markers": [{"date": confirm, "label": "entry", "kind": "confirm"}],
            "stats": stats,
            "why": (f"came back into demand, hit target in {bto} bars"
                    if bto is not None else "came back into demand, hit target"),
            "theme": _theme(sym),
            "badges": [{"text": "Target hit", "tone": "good"},
                       {"text": "Backtested", "tone": "muted"}],
            "_score": float(len(wins) - i),
        })

    n = len(usable)
    return {
        "tiles": _finish(tiles, limit, themes_first=False, days=days,
                         min_tier="any")[0],
        "record": {
            "overall": {"wins": len(wins), "losses": len(losses), "n": n,
                        "win_pct": round(100.0 * len(wins) / n, 1) if n else None},
            "caveat": ("Walk-forward backtest, not live observations. Universe is "
                       "TODAY's liquid names, so delisted tickers are absent and "
                       "this number is biased UPWARD. Same-bar wins are excluded "
                       "from the charts. Read expectancy, not win rate — the live "
                       "board applies no minimum R:R, so trivially close targets "
                       "raise the win rate while paying nothing."),
        },
    }


def winner_tiles(limit: int = LIMIT_DEFAULT, days: int = 90,
                 pattern: Optional[str] = None,
                 minervini_only: bool = False) -> dict:
    """Past setups that reached their measure-rule target before their stop.

    HONESTY RULES BAKED IN HERE
    ---------------------------
    * The record reports wins AND the stop-first losses from the same raced
      denominator. A winners-only wall is a highlight reel.
    * Observations already at or past target when recorded are EXCLUDED: the
      move had happened before the ledger saw it, so the chart teaches nothing
      about the entry. Measured 2026-08-15: 8 of 117 raced observations.
    * Patterns are never ranked against each other by raw win-%. Their stop
      brackets differ roughly 2x (a double bottom's stop sits far below entry,
      a cup's handle stop is tight), which is exactly the comparison the
      2026-07-10 audit found broken.
    """
    from patterns import history

    coll = history._coll()
    if coll is None:
        return {"tiles": [], "note": "pattern ledger unavailable"}

    q = {"kind": "pattern", "status": "confirmed",
         "outcome": {"$in": [WIN_OUTCOME, LOSS_OUTCOME]}}
    if pattern:
        q["pattern"] = pattern
    try:
        raced = list(coll.find(q, {"_id": 0}))
    except Exception as exc:
        log.warning("chart-maps: winners query failed: %s", exc)
        return {"tiles": [], "note": "pattern ledger unavailable"}

    def _already_past(o: dict) -> bool:
        t, c = _num(o.get("target")), _num(o.get("obs_close"))
        return t is not None and c is not None and c >= t

    usable = [o for o in raced if not _already_past(o)]
    # Ajay 2026-08-16: "Also the Minervini one that have been successfull to
    # learn and memorize charts." The ledger records is_candidate at OBSERVATION
    # time, so this is what the trend template said then — not a hindsight
    # relabel from today's scan.
    if minervini_only:
        usable = [o for o in usable if o.get("is_candidate")]
    wins = [o for o in usable if o.get("outcome") == WIN_OUTCOME]
    losses = [o for o in usable if o.get("outcome") == LOSS_OUTCOME]
    wins.sort(key=lambda o: str(o.get("et_date") or ""), reverse=True)

    tiles = []
    for i, o in enumerate(wins):
        sym = (o.get("symbol") or "").upper()
        confirm = str(o.get("confirmed_date") or o.get("et_date") or "")[:10]
        if not sym or not confirm:
            continue
        neck, tgt, stp = _num(o.get("neckline")), _num(o.get("target")), _num(o.get("stop"))
        lines = []
        if neck is not None:
            lines.append({"price": neck, "label": "BREAKOUT", "tone": "buy"})
        if tgt is not None:
            lines.append({"price": tgt, "label": "TARGET", "tone": "target"})
        if stp is not None:
            lines.append({"price": stp, "label": "STOP", "tone": "stop"})

        gain = _num(o.get("max_gain_pct"))
        bto = o.get("bars_to_outcome")
        stats = [{"k": "Pattern", "v": _pattern_label(o.get("pattern"))},
                 {"k": "Confirmed", "v": confirm},
                 {"k": "Best gain", "v": f"+{gain:.1f}%" if gain is not None else "—"},
                 {"k": "Bars to target", "v": str(bto) if bto is not None else "—"}]
        rs = _num(o.get("rs_rank"))
        if rs is not None:
            stats.append({"k": "RS then", "v": str(int(rs))})

        tiles.append({
            "symbol": sym,
            "name": _name_for(sym),
            "href": _href(sym, "breakout"),
            "bars": [],
            # Enough bars after the confirmation to show the resolution.
            "_bars": {"around": confirm,
                      "pad_after": int(o.get("bars_to_outcome") or 21) + 12},
            "bands": [],
            "lines": lines,
            "markers": [{"date": confirm, "label": "confirmed", "kind": "confirm"}],
            "stats": stats,
            "why": (f"{_pattern_label(o.get('pattern'))} — hit target in "
                    f"{bto} bars" if bto is not None
                    else f"{_pattern_label(o.get('pattern'))} — reached target"),
            "theme": _theme(sym),
            "badges": ([{"text": "Target hit", "tone": "good"}]
                       + ([{"text": "SEPA qualifier", "tone": "info"}]
                          if o.get("is_candidate") else [])
                       + ([{"text": "Buyable then", "tone": "good"}]
                          if o.get("is_buyable") else [])),
            "pattern": o.get("pattern"),
            # Already sorted newest-first; a descending score preserves that
            # order through _finish's shared sort.
            "_score": float(len(wins) - i),
        })

    return {"tiles": _finish(tiles, limit, themes_first=False, days=days,
                             min_tier="any")[0],
            "record": _winner_record(usable, wins, losses),
            "excluded_already_past_target": len(raced) - len(usable),
            "patterns": sorted({o.get("pattern") for o in usable if o.get("pattern")})}


def _winner_record(usable: list, wins: list, losses: list) -> dict:
    """Per-pattern wins vs stop-firsts. Never a cross-pattern ranking."""
    by: dict[str, dict] = {}
    for o in usable:
        p = o.get("pattern") or "unknown"
        rec = by.setdefault(p, {"pattern": p, "label": _pattern_label(p),
                                "wins": 0, "losses": 0})
        rec["wins" if o.get("outcome") == WIN_OUTCOME else "losses"] += 1
    for rec in by.values():
        n = rec["wins"] + rec["losses"]
        rec["n"] = n
        rec["win_pct"] = round(100.0 * rec["wins"] / n, 1) if n else None
    return {
        "overall": {"wins": len(wins), "losses": len(losses),
                    "n": len(usable),
                    "win_pct": (round(100.0 * len(wins) / len(usable), 1)
                                if usable else None)},
        "by_pattern": sorted(by.values(), key=lambda r: -r["n"]),
        "caveat": ("Wins are target-before-stop within 21 bars. Stop brackets "
                   "differ ~2x between patterns, so these win rates are NOT "
                   "comparable across patterns — read each against its own "
                   "target and stop distance."),
    }


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------
def board(tab: str = "vcp", limit: int = LIMIT_DEFAULT, days: int = BARS_DEFAULT,
          universe: str = "sp1500_plus", themes_first: bool = THEMES_FIRST_DEFAULT,
          pattern: Optional[str] = None, source: str = "pattern",
          minervini_only: bool = False, sort: str = DEFAULT_SORT,
          min_tier: str = DEFAULT_MIN_TIER) -> dict:
    """One tab's tiles. Never scans; reads caches and the pattern ledger.

    `source` splits the winners tab (Ajay 2026-08-16): "pattern" is the
    chart-pattern ledger, "zone" is the demand-zone re-entry backtest.
    `minervini_only` narrows the pattern winners to those that were SEPA
    qualifiers at observation time.
    """
    t = tab if tab in TABS else TABS[0]
    limit = max(1, min(int(limit or LIMIT_DEFAULT), LIMIT_MAX))
    days = max(20, min(int(days or BARS_DEFAULT), BARS_MAX))
    src = source if source in ("pattern", "zone") else "pattern"
    # An unknown sort falls back to the default rather than erroring: a stale
    # bookmark should show the board, not a 422.
    srt = sort if sort in SORTS else DEFAULT_SORT
    tier = min_tier if min_tier in LIQ_TIERS else DEFAULT_MIN_TIER

    if t == "zones":
        out = zone_tiles(limit, days, universe, themes_first, srt, tier)
    elif t == "winners":
        if src == "zone":
            out = zone_winner_tiles(limit, days=min(days, 90))
        else:
            out = winner_tiles(limit, days=min(days, 90), pattern=pattern,
                               minervini_only=bool(minervini_only))
        out["source"] = src
    else:
        out = vcp_tiles(limit, days, themes_first, sort=srt, min_tier=tier)

    out["tab"] = t
    out["count"] = len(out.get("tiles") or [])
    # The winners tabs read a ledger, not a scan, so they carry no live volume
    # to sort by. Say so rather than offering a control that silently does
    # nothing.
    out["sort"] = DEFAULT_SORT if t == "winners" else srt
    out["sorts"] = [] if t == "winners" else [{"key": k, "label": v}
                                              for k, v in SORTS.items()]
    # The winners tabs read a ledger and are not liquidity-filtered — saying
    # "any" there is honest; pretending a floor applied would not be.
    out["min_tier"] = "any" if t == "winners" else tier
    out["tiers"] = [] if t == "winners" else [
        {"key": "deep", "label": f"Deep · ≥${int(LIQ_DEEP_USD/1e6)}M/day"},
        {"key": "ok", "label": f"Tradeable · ≥${int(LIQ_OK_USD/1e6)}M/day"},
        {"key": "thin", "label": f"Thin · ≥${int(LIQ_THIN_USD/1e6)}M/day"},
        {"key": "any", "label": "No floor (shows illiquid names)"},
    ]
    out["tape_sorts"] = list(TAPE_SORTS)
    out["disclaimer"] = DISCLAIMER
    return out
