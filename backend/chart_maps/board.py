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

# One definition of "closest to the level first, money flow breaks ties" for
# every demand board that is not the reached one (Ajay 2026-09-03). Pure module
# (no scan imports), so it is safe to import at module load even where the
# tests stub supply_demand.demand_reentry.
from supply_demand import demand_order as _order

log = logging.getLogger("chart_maps.board")

# "ict" took the Into Supply SLOT on the page (Ajay 2026-09-03 late: "create a
# new chart maps tab for ICT Strategy, replace supply tab with this new tab").
# "supply" stays registered here so an old ?tab=supply bookmark still resolves
# on the backend; the frontend maps it to ict.
TABS = ("vcp", "topping", "zones", "supply", "ict", "deep_demand", "quick_bounce", "gabbar", "undervalue", "zero_dte", "winners", "earnings")

BARS_DEFAULT = 130          # ~6 months of daily bars — a base plus its run-up
BARS_MAX = 400
LIMIT_DEFAULT = 24
# 80 since 2026-08-27 (was 60): the gabbar tab shows ALL 66 covered names
# ("can you just show me all of them there") and 60 silently cut the ladder.
LIMIT_MAX = 80

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
        raw = prices.load_prices(symbol.upper())
        # Today's live bar on the tile too (Ajay 2026-09-03, CHPT) — the same
        # overlay the Supply/Demand tab draws; stubs without it just skip.
        fn = getattr(prices, "with_today_bar", None)
        if fn is not None and raw is not None:
            try:
                raw, _info = fn(raw, symbol.upper())
            except Exception as exc:                            # pragma: no cover
                log.debug("chart-maps: today-bar overlay %s failed: %s", symbol, exc)
        df = _norm_frame(raw)
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


def _href(symbol: str, tab: str = "supply") -> str:
    """Tile click target. Default = the Supply / Demand tab (Ajay 2026-09-03:
    "when ever I click on SEPA I need it to go Supply and Demand tab in all
    pages") — supersedes the 2026-08-17 "open straight on the Setup tab" ask
    for the vcp / zones / earnings / deep-demand / topping / gabbar tiles.
    Purposed deep links (winners → breakout, 0DTE → options, undervalue →
    analysis) keep their tab."""
    return f"/sepa/{symbol.upper()}?tab={tab}"


# Ajay 2026-09-03: "from all chart maps Demand zones remove anything that
# already did about 7% bounce from Demand Zone." A demand board is a list of
# names AT a level; once price has run 7% off the band the arrival he wanted
# to catch is over, and the tile is a story, not a setup. The scan that feeds
# these boards is cached for hours, so a name that touched at 10:00 and ran by
# 14:00 would otherwise sit on the board all afternoon — the gate therefore
# reads the LIVE print and falls back to the scan's last_price only when the
# tape is unreachable. Measured from the band TOP (price re-enters from above;
# the top is where the bounce starts). Applies to every demand board here:
# zones (reached | approaching × zone | order block) and deep demand.
BOUNCE_DONE_PCT = 7.0


def bounce_pct(price, band_hi) -> Optional[float]:
    """% that `price` sits above the band top; None when either is unusable."""
    px, hi = _num(price), _num(band_hi)
    if px is None or hi is None or hi <= 0:
        return None
    return (px - hi) / hi * 100.0


def already_bounced(price, band_hi, done_pct: float = BOUNCE_DONE_PCT) -> bool:
    b = bounce_pct(price, band_hi)
    return b is not None and b >= done_pct


def _room_prev_close(r: dict, live_px) -> Optional[float]:
    """The prior CLOSED bar's close behind the room read's broken-supply rule:
    with a live print the scan's last_price is the last closed bar it saw;
    on the scan basis the record's own `prev_close` (None on rows cached
    before 2026-09-05 = every supply band counts, the conservative side)."""
    if live_px is not None:
        return _num(r.get("last_price"))
    return _num(r.get("prev_close"))


def drop_low_room(rows: list, live: Optional[dict], min_room: Optional[float]) -> tuple:
    """(kept_rows, hidden_count, room_by_symbol) — the room floor on a demand
    board (Ajay 2026-09-05, TRU: "There is only 0.5% room"; "the same logic
    in Demand and deep demand zone ... more room atleast >5%"). Room is
    room_floor.room_block on the LIVE print when the tape has one (basis
    "live"), else the scan price ("scan"), to the first unbroken band
    overhead, the row's own entry band excluded. None = the house default
    (alert_gates.ALERT_MIN_ROOM_PCT via room_floor); 0 = off — every tile
    kept, the room still read and said. An unreadable room fails a real
    floor, the R:R-floor rule."""
    from supply_demand import room_floor as RF
    floor = RF.MIN_ROOM_DEFAULT if min_room is None else float(min_room)
    kept, hidden, rooms = [], 0, {}
    for r in rows:
        sym = (r.get("symbol") or "").upper()
        live_px = (live or {}).get(sym)
        px = live_px if live_px is not None else _num(r.get("last_price"))
        room = RF.room_block(px, RF.row_bands(r), RF.row_entry_band(r),
                             _room_prev_close(r, live_px),
                             "live" if live_px is not None else "scan")
        rooms[sym] = room
        if not RF.meets_room_floor(room, floor):
            hidden += 1
            continue
        kept.append(r)
    return kept, hidden, rooms


def _room_stat_row(rooms: dict, sym: str) -> dict:
    from supply_demand import room_floor as RF
    return {"k": "room", "v": RF.room_stat(rooms.get(sym))}


def _room_meta(min_room: Optional[float], hidden: int) -> dict:
    from supply_demand import room_floor as RF
    floor = RF.MIN_ROOM_DEFAULT if min_room is None else max(0.0, float(min_room))
    return {"min_room": floor, "min_room_default": RF.MIN_ROOM_DEFAULT,
            "hidden_low_room": hidden}


def _live_last(symbols: list) -> dict:
    """Live print per symbol for the bounce gate. {} on any failure — the
    scan's own last_price then decides, so a tape outage never empties a board
    or lets a stale one through unexamined."""
    syms = sorted({(s or "").upper() for s in symbols if s})
    if not syms:
        return {}
    try:
        from sepa import prices as _p
        live = _p.bulk_live_prices(syms) or {}
    except Exception as exc:
        log.debug("chart maps: live prices unavailable for the bounce gate: %s", exc)
        return {}
    return {k: _snapshot_print(v) for k, v in live.items()}


def _snapshot_print(snap) -> Optional[float]:
    """The usable live print in one bulk_live_prices row: the last trade
    (extended hours included — the same field zone_bounce_alerts.
    print_from_snapshot reads, without its staleness drop) first, else the
    day bar close. A NON-POSITIVE value is MISSING, never a price: the day
    bar `price` is 0 before the open (portfolio/supply_watch.py, sepa/
    prices.py), and 0.0 fed to the bounce gate / live re-rank made every
    row STATE_UNKNOWN so the boards fell to money-flow order (2026-09-05
    fix). None lets the callers fall back to the row's scan price."""
    snap = snap or {}
    for key in ("last_trade_price", "price"):
        px = _num(snap.get(key))
        if px is not None and px > 0:
            return px
    return None


def _bounce_ref_hi(r: dict, phase: str, target: str) -> Optional[float]:
    """The band top the bounce is measured from: the order block when that is
    the target, else the demand band."""
    if target == "order_block":
        ob = (r.get("approaching_ob") if phase == "approaching" else r.get("in_ob")) or {}
        hi = _num((ob.get("block") or {}).get("hi"))
        if hi is not None:
            return hi
    return _num((r.get("entry_zone") or {}).get("hi"))


def drop_bounced(rows: list, ref_hi, live: Optional[dict] = None) -> tuple:
    """(kept_rows, dropped_count). `ref_hi(row)` gives the band top; `live`
    maps SYMBOL → live price (missing/None entries fall back to row last_price)."""
    live = live or {}
    kept, dropped = [], 0
    for r in rows:
        sym = (r.get("symbol") or "").upper()
        px = live.get(sym)
        if px is None:
            px = _num(r.get("last_price"))
        if already_bounced(px, ref_hi(r)):
            dropped += 1
            continue
        kept.append(r)
    return kept, dropped


def _live_px(r: dict, live: Optional[dict]):
    """The price a READ-TIME rank runs on: the live print when the tape has
    one, else the scan's last_price. Same fallback the bounce gate uses."""
    px = (live or {}).get((r.get("symbol") or "").upper())
    return px if px is not None else _num(r.get("last_price"))


def _disp_dist(r: dict, live: Optional[dict], read: Optional[dict], level_key: str):
    """Distance to print on an approaching tile: the LIVE % above the level when
    a fresh print is known (the same number the ranking used) — 0.0 once that
    print is AT or INSIDE the level (the rank already treats it as in; the
    stale scan number must not contradict it, 2026-09-05 fix) — else the
    scan's dist_pct. Ajay reads the badge to predict the order, so they must
    agree."""
    read = read or {}
    hi = _num((read.get(level_key) or {}).get("hi"))
    px = _live_px(r, live)
    if px is not None and hi is not None and px > 0:
        if px <= hi:
            return 0.0
        return round((px - hi) / px * 100.0, 2)
    return read.get("dist_pct")


def _dist_text(dist, above: str, inside: str) -> str:
    """'1.96% above it' — or 'now in the band' once the distance reads 0
    (the live print is at/inside the level)."""
    d = _num(dist)
    if d is not None and d <= 0:
        return f"now in {inside}"
    return f"{dist}% above {above}"


def _dist_badge(dist, noun: str) -> dict:
    d = _num(dist)
    if d is not None and d <= 0:
        return {"text": f"\u25c9 in {noun}", "tone": "good"}
    return {"text": f"\u2192 {dist}% above {noun}", "tone": "warn"}


def rerank_live(rows: list, key, live: Optional[dict]) -> list:
    """Ajay 2026-09-03: "keep the closest one to demand zones on the top. Of
    course CMF inflow too considered." The scan sorted these rows on ITS
    last_price, and that cache is warmed at 9:25 / 16:55 — by mid-session
    the name that was 2% out may be inside the band. Re-rank on the live
    print with the SAME per-board key the scan used (demand_order), so the
    two surfaces only ever differ by the price they were read at."""
    return sorted(rows, key=lambda r: key(r, px=_live_px(r, live)))


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
        # Average SHARE volume — attach_velocity divides it by shares
        # outstanding. Kept separate from avg_turnover (dollars).
        "avg_shares": avg_vol,
        # % of shares outstanding traded on an average day. Filled by
        # attach_velocity (needs a per-symbol reference lookup); None until
        # then, and a None column triggers the honest sort_unavailable note.
        "velocity": None,
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
    "velocity": "🐆 % of shares traded/day",
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


# Descriptive velocity bands, NOT book thresholds — a label for how fast the
# share supply turns over. AVGO trades ~0.3%/day of a 4-billion-share supply:
# every dollar of demand meets an ocean of stock, which is why it cannot "run
# like a cheetah" no matter how pretty the zone (Ajay 2026-08-25). The floor
# and the R:R rank never measured this; now the tile says it.
VELOCITY_FAST_PCT = 2.0
VELOCITY_SLOW_PCT = 0.5
VELOCITY_BUDGET_SEC = 3.0
VELOCITY_WORKERS = 8


def attach_velocity(tiles: list, budget_sec: float = VELOCITY_BUDGET_SEC) -> int:
    """Fill _m['velocity'] (% of shares outstanding traded on an average day).

    Share counts come from short_interest.client._shares_outstanding — the
    one existing source, Massive reference, process-cached, and honestly
    labelled OUTSTANDING (a true free float is not in the feed). Time-boxed
    and failure-isolated like attach_tape: a missing count leaves velocity
    None, never sinks a board.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from concurrent.futures import TimeoutError as _FT
    from short_interest.client import _shares_outstanding

    todo = [t for t in tiles
            if (t.get("_m") or {}).get("velocity") is None
            and (t.get("_m") or {}).get("avg_shares")]
    if not todo:
        return 0
    done = 0
    pool = ThreadPoolExecutor(max_workers=VELOCITY_WORKERS)
    try:
        futs = {pool.submit(_shares_outstanding, t["symbol"]): t for t in todo}
        for fut in as_completed(futs, timeout=budget_sec):
            t = futs[fut]
            try:
                shares = fut.result(timeout=0.1)
            except Exception:
                continue
            avg = (t.get("_m") or {}).get("avg_shares")
            if shares and avg:
                t["_m"]["velocity"] = round(avg / shares * 100.0, 2)
                done += 1
    except _FT:
        pass                       # the rest stay None — degrade, don't block
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return done


def _velocity_decor(tiles: list) -> None:
    """Stat + badge from a filled velocity. Only names with a number get a
    row — '—' on every gabbar/ledger tile would be noise, not honesty."""
    for t in tiles:
        v = (t.get("_m") or {}).get("velocity")
        if v is None:
            continue
        t.setdefault("stats", []).append({"k": "Float/day", "v": f"{v:.2f}%"})
        if v >= VELOCITY_FAST_PCT:
            t.setdefault("badges", []).append(
                {"text": f"🐆 Fast supply — {v:.1f}%/day", "tone": "good"})
        elif v <= VELOCITY_SLOW_PCT:
            t.setdefault("badges", []).append(
                {"text": f"🐘 Heavy supply — {v:.2f}%/day of shares", "tone": "muted"})


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

    # 2b — the velocity sort needs the per-symbol share count, which is a
    # reference lookup, not a scan field. Same pool discipline as the tape
    # sorts, same honest fallback when the column comes back empty.
    if sort == "velocity":
        pool = tiles[:min(len(tiles), max(limit, limit * TAPE_POOL_MULT))]
        attach_velocity(pool)
        pool.sort(key=lambda t: _sort_key(t, themes_first, sort))
        tiles = pool + tiles[len(pool):]
        if not any((t.get("_m") or {}).get("velocity") is not None for t in pool):
            sort_unavailable = ("Share counts unavailable right now — the board "
                                "is showing its default order.")

    # 3 — the per-theme cap keeps the board a SPREAD, which is the right default
    # for a study surface. But it fights an explicit ranking: capping a volume
    # sort would silently drop the 7th-highest-volume name for being in a
    # popular theme, and the board would no longer be what the dropdown says.
    if themes_first and not explicit:
        tiles = _spread(tiles, limit)

    short = tiles[:limit + BAR_BUFFER]
    _attach_bars(short, days)
    out = [t for t in short if t.get("bars")][:limit]
    # Velocity stat + 🐆/🐘 badge on every SHOWN tile that has the inputs —
    # the "can it actually run" read (Ajay 2026-08-25, AVGO). Only ~24 cached
    # lookups; a cold miss inside the budget just leaves the tile undecorated.
    attach_velocity(out)
    _velocity_decor(out)
    for t in out:
        t.pop("_score", None)
        t.pop("_bars", None)
        t.pop("_m", None)
        t.pop("_flow", None)
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
            "href": _href(sym, "supply"),
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
def _flash_sell_symbols() -> set:
    """Symbols with a SELL-side zone burst today — institutional selling
    evidence for the topping board. Same failure isolation as _flash_symbols."""
    try:
        from orderflow import trade_flash
        evs = trade_flash.today_events().get("events") or []
        return {e["symbol"] for e in evs if e.get("side") == "sell"}
    except Exception:
        return set()


def _flash_symbols() -> set:
    """Symbols with a zone-tied tape burst TODAY (orderflow/trade_flash).

    Failure-isolated: the zone boards must render identically if the flash
    collection is cold, missing, or Mongo is down — a badge is decoration on
    the board, never a dependency of it.
    """
    try:
        from orderflow import trade_flash
        return set(trade_flash.today_events().get("symbols") or [])
    except Exception:
        return set()


def supply_tiles(limit: int = LIMIT_DEFAULT, days: int = BARS_DEFAULT,
                 universe: str = "full",
                 themes_first: bool = THEMES_FIRST_DEFAULT,
                 sort: str = DEFAULT_SORT,
                 min_tier: str = DEFAULT_MIN_TIER) -> dict:
    """Into Supply — the inverse of the demand board.

    Ajay 2026-08-20: "Now in inversely give me a tab that are in or about to be
    in supply zones please..."

    Reads `supply_rows` from the SAME `demand_reentry` cache the demand tab
    reads. There is no second scan and no second cache: `scan()` evaluates both
    predicates over one record in one loop, so the two tabs cannot disagree
    about a name's bands, and this tab costs a page load rather than three
    minutes. See `supply_demand/into_supply.py`.

    NO PLAN LINES. The demand tiles draw BUY / STOP / TARGET because there is a
    trade to describe. There is no trade here — this is a caution flag on a name
    running into a lid — and drawing a plan would invent one. The lines are the
    two structural levels and the price between them.
    """
    from supply_demand import demand_reentry as D

    data = D.cached_or_warm(universe, limit=LIMIT_MAX)
    if data.get("warming"):
        return {"tiles": [], "warming": True,
                "universe_key": data.get("universe_key") or universe,
                "progress": data.get("progress"),
                "note": "scanning for names running into overhead supply…"}

    # Already ordered by `into_supply.sort_key` inside the scan.
    rows = list(data.get("supply_rows") or [])
    flash_syms = _flash_symbols()
    tiles = []
    for rank, r in enumerate(rows):
        sym = (r.get("symbol") or "").upper()
        sup = r.get("supply") or {}
        ceiling = sup.get("ceiling") or {}
        if not sym or not ceiling:
            continue

        last = _num(r.get("last_price"))
        c_lo, c_hi = _num(ceiling.get("lo")), _num(ceiling.get("hi"))
        floor = sup.get("support_below") or {}
        f_lo, f_hi = _num(floor.get("lo")), _num(floor.get("hi"))

        bands = []
        if c_lo is not None and c_hi is not None:
            bands.append({"kind": "supply", "lo": c_lo, "hi": c_hi,
                          "label": "ceiling"})
        if f_lo is not None and f_hi is not None:
            bands.append({"kind": "demand", "lo": f_lo, "hi": f_hi,
                          "label": "support"})

        # `neutral` for the levels and `now` for price: none of these is a BUY,
        # a STOP or a TARGET, and borrowing those tones would dress a caution
        # flag up as a plan.
        lines = []
        if c_lo is not None:
            lines.append({"price": c_lo, "label": f"ceiling {c_lo:.2f}",
                          "tone": "target"})
        if last is not None:
            lines.append({"price": last, "label": "now", "tone": "now"})
        if f_hi is not None:
            lines.append({"price": f_hi, "label": f"support {f_hi:.2f}",
                          "tone": "neutral"})

        dist = _num(sup.get("distance_pct"))
        down = _num(sup.get("downside_pct"))
        ratio = _num(sup.get("room_ratio"))
        liq = r.get("liquidity") or {}
        stats = [
            {"k": "To ceiling", "v": ("at it" if dist is not None and dist <= 0.05
                                      else f"{dist:.1f}%" if dist is not None else "—")},
            {"k": "To support", "v": f"{down:.1f}%" if down is not None else "—"},
            {"k": "Room up:down", "v": f"{ratio:.2f}" if ratio is not None else "—"},
            {"k": "Ceiling tested", "v": (f"{ceiling.get('touches')}x"
                                          if ceiling.get("touches") else "—")},
            {"k": "Liquidity", "v": (liq.get("tier") or "—")},
        ]

        run = _num(sup.get("run_up_pct"))
        inside = sup.get("state") == "AT_CEILING"
        why = (
            (f"inside overhead supply ${c_lo:.2f}–${c_hi:.2f}" if inside
             else f"{dist:.1f}% under overhead supply ${c_lo:.2f}–${c_hi:.2f}")
            + (f", {ceiling.get('touches')}x tested" if ceiling.get("touches") else "")
            + (f" · rallied {run:.0f}% into it" if run is not None else "")
            + (f" · next support {down:.1f}% below" if down is not None else "")
        )

        badges = []
        # His own observation (2026-08-25): "some of supply ones are actually
        # bullish and accumulating" — now the tile says which. Money flowing
        # IN at a ceiling is pressure to break it; distribution at a ceiling
        # is the lid holding.
        fb = _flow_badge(r.get("inflow"))
        if fb:
            badges.append(fb)
        if inside:
            badges.append({"text": "At the lid", "tone": "warn"})
        if ratio is not None and ratio < 1.0:
            badges.append({"text": "More room down", "tone": "warn"})
        if sup.get("ceiling_bars_since_test") is not None and \
                sup["ceiling_bars_since_test"] <= 21:
            badges.append({"text": "Tested recently", "tone": "muted"})
        if sym in flash_syms:
            # A burst AT a supply ceiling: sell burst = the lid being defended,
            # buy burst = someone paying up into it. Either way he wants to see
            # it (Trade Flash, 2026-08-24) — the side lives in the flash strip.
            badges.append({"text": "⚡ Tape burst at zone", "tone": "warn"})

        tiles.append({
            "symbol": sym,
            "name": r.get("name") or _name_for(sym),
            # Supply, not Setup. The actionable read here IS the zone
            # inventory — there is no plan tab answer to send him to.
            "href": _href(sym, "supply"),
            "bars": [],
            "_bars": {"days": _zone_window(ceiling)},
            "bands": bands,
            "lines": lines,
            "markers": [],
            "stats": stats,
            "why": why,
            "theme": _theme(sym),
            "badges": badges,
            # `_finish` ranks by `_score` DESCENDING. Deriving it from the
            # POSITION in the already-sorted list reproduces
            # `into_supply.sort_key` exactly, without inventing weights to
            # squash a four-part ordering into one number — there stays exactly
            # one definition of "most urgent", and it lives in that function.
            "_score": float(len(rows) - rank),
            "_m": tile_metrics(r),
        })
    out, meta = _finish(tiles, limit, themes_first, days, sort, min_tier)
    gex_as_of = _gex_decor(out, "supply")
    return {"tiles": out, **meta,
            "gex_as_of": gex_as_of,
            "matched": len(rows),
            "universe_key": data.get("universe_key"),
            "universe_label": data.get("universe_label"),
            # The universes the server actually offers, so the tab's
            # dropdown cannot drift from demand_reentry.UNIVERSES.
            "universe_choices": data.get("universe_choices"),
            "scanned": data.get("scanned"),
            "generated_at": data.get("as_of"),
            "note": (None if rows else
                     "Nothing is sitting under a tested ceiling right now."),
            "disclaimer": _supply_disclaimer()}


def zero_dte_tiles(limit: int = LIMIT_DEFAULT, days: int = BARS_DEFAULT,
                   symbols: Optional[list] = None, **_ignored) -> dict:
    """0DTE — same-day expiry calls and puts, under a gamma-regime banner.

    Ajay 2026-08-24: *"a new tab for ODTE type of options calls... put two
    categories... this will require a lot of accuracy and much better data like
    order book"*. He then chose calls/puts as the two categories inside a
    pinned/unpinned banner, with a suggested strike recorded to a ledger.

    Two structural departures from every other tab, both deliberate:

    * **It does not read the demand scan.** Every other board slices one cached
      equity pass. This one reads live option chains, because a 0DTE quote is
      stale in seconds and there is nothing in the daily cache that prices one.
    * **NO PLAN LINES, and no BUY tone anywhere.** The lines are strikes, walls
      and the pin — structure, not a trade. `supply_tiles` made the same call
      for the same reason: drawing an entry would invent one.

    The banner is per-symbol rather than global. Measured 2026-08-24, the same
    session had AMZN/GOOGL/META/MSFT pinned while SPY/QQQ/NVDA/TSLA amplified —
    one banner over the board would have been wrong for half of it.
    """
    from options import zero_dte as Z

    data = Z.board(symbols=symbols)
    rows = list(data.get("rows") or [])
    tiles = []
    for rank, r in enumerate(rows):
        sym = (r.get("symbol") or "").upper()
        spot = _num(r.get("spot"))
        if not sym or spot is None:
            continue
        reg = r.get("regime") or {}
        call, put = r.get("call"), r.get("put")

        # The wall-to-wall range as a band: where dealer hedging is expected to
        # contain the tape. `neutral` because it is a range, not a zone anyone
        # is buying or selling into.
        bands = []
        cw, pw = _num(reg.get("call_wall")), _num(reg.get("put_wall"))
        if cw is not None and pw is not None and pw < cw:
            bands.append({"kind": "neutral", "lo": pw, "hi": cw,
                          "label": "gamma walls"})

        lines = [{"price": spot, "label": "now", "tone": "now"}]
        if call and _num(call.get("strike")) is not None:
            k = _num(call.get("strike"))
            lines.append({"price": k, "label": f"call {k:g}", "tone": "target"})
        if put and _num(put.get("strike")) is not None:
            k = _num(put.get("strike"))
            lines.append({"price": k, "label": f"put {k:g}", "tone": "neutral"})
        mp = _num(r.get("max_pain"))
        # A tied pin is not a pin — opex flags when the runner-up lands within
        # 1% of the minimum, and drawing a magnet the OI grid does not support
        # would be the most confident-looking line on the chart.
        if mp is not None and not r.get("max_pain_tie"):
            lines.append({"price": mp, "label": f"pin {mp:g}", "tone": "neutral"})

        em = _num(r.get("expected_move_pct"))

        def _leg(c):
            """One side, in the two numbers that decide it."""
            if not c:
                return "—"
            mn = _num(c.get("moves_needed"))
            return (f"{c.get('strike'):g} · {mn:g}x" if mn is not None
                    else f"{c.get('strike'):g}")

        # Worst theta across the two suggested legs. The headline risk on a
        # 0DTE is not the spread, it is that theta routinely exceeds the whole
        # premium — measured at 787% on SPY's own suggestion, 2026-08-24.
        burns = [_num((c or {}).get("theta_burn_pct")) for c in (call, put)]
        burns = [b for b in burns if b is not None]
        worst_burn = max(burns) if burns else None
        spreads = [_num((c or {}).get("spread_pct")) for c in (call, put)]
        spreads = [x for x in spreads if x is not None]

        stats = [
            {"k": "Expected move", "v": f"±{em:.2f}%" if em is not None else "—"},
            {"k": "Call", "v": _leg(call)},
            {"k": "Put", "v": _leg(put)},
            {"k": "Theta/day", "v": (f"{worst_burn:.0f}% of premium"
                                     if worst_burn is not None else "—")},
            {"k": "Spread", "v": (f"{min(spreads):.0f}–{max(spreads):.0f}%"
                                  if len(spreads) > 1 else
                                  f"{spreads[0]:.0f}%" if spreads else "—")},
        ]

        pinned = reg.get("regime") == "PINNED"
        best = None
        for c in (call, put):
            v = _num((c or {}).get("moves_needed"))
            if v is not None and (best is None or v < best):
                best = v
        why = (
            (f"needs {best:g}x today's expected move to double"
             if best is not None else "nothing clears the spread and delta floors")
            + (f" · dealers {'PIN' if pinned else 'AMPLIFY'}"
               if reg.get("regime") != "UNKNOWN" else "")
            + (f" · expected ±{em:.2f}%" if em is not None else "")
            + (f" · theta {worst_burn:.0f}%/day" if worst_burn is not None else "")
        )

        badges = []
        if reg.get("regime") == "PINNED":
            # A pin is the WARNING here, not the good news. This board is for
            # someone buying premium, and suppression is the thing that kills it.
            badges.append({"text": "Pinned", "tone": "warn"})
        elif reg.get("regime") == "AMPLIFYING":
            badges.append({"text": "Amplifying", "tone": "good"})
        if reg.get("fragile"):
            badges.append({"text": "Gamma unsettled", "tone": "muted"})
        if worst_burn is not None and worst_burn >= 200:
            badges.append({"text": "Theta > 2x premium", "tone": "warn"})
        if not call and not put:
            badges.append({"text": "Nothing tradeable", "tone": "muted"})
        if r.get("gex_reliability") == "single_name":
            # opex's own caveat, carried rather than dropped: the blind sign
            # rule can invert on single-name momentum leaders.
            badges.append({"text": "Single-name gamma", "tone": "muted"})

        tiles.append({
            "symbol": sym,
            "name": _name_for(sym),
            # The SEPA detail page's own options tab — a tab that EXISTS.
            # This first shipped as _href(sym, "zero_dte"), which is not in
            # SepaCandidate's TABS, so every tile silently fell back to the
            # chart tab. Every other board deep-links somewhere real (setup,
            # supply, breakout); this now does too, and `options` is the
            # topically right landing spot for an options tile.
            "href": _href(sym, "options"),
            "bands": bands,
            "lines": lines,
            "stats": stats,
            "why": why,
            "badges": badges,
            "zero_dte": r,
            # Position, not a weighted score — one definition of "least work
            # required", the same discipline `supply_tiles` uses.
            "_score": float(len(rows) - rank),
        })

    # `min_tier="any"` explicitly. The floor reads `_m.avg_turnover`, which
    # these tiles do not carry — every row would fail it on MISSING data rather
    # than on being thin. It would also be meaningless here: a name only has a
    # daily expiry because it is already among the most liquid on the tape.
    out, meta = _finish(tiles, limit, False, days, sort=DEFAULT_SORT,
                        min_tier="any")
    return {"tiles": out, **meta,
            "matched": len(rows),
            "expiry": data.get("expiry"),
            "session": data.get("session"),
            "with_chain": data.get("with_chain"),
            "with_contract": data.get("with_contract"),
            "cached_age_sec": data.get("cached_age_sec"),
            "generated_at": data.get("as_of"),
            "note": (None if rows else
                     "No same-day expiries found for any name on the list."),
            "disclaimer": data.get("disclaimer")}


def _supply_disclaimer() -> str:
    from supply_demand import into_supply as I
    return I.DISCLAIMER


def zone_tiles(limit: int = LIMIT_DEFAULT, days: int = BARS_DEFAULT,
               universe: str = "full", themes_first: bool = THEMES_FIRST_DEFAULT,
               sort: str = DEFAULT_SORT, min_tier: str = DEFAULT_MIN_TIER,
               phase: str = "reached", target: str = "zone",
               min_room: Optional[float] = None) -> dict:
    # One board, two moments (Ajay 2026-08-31: "find a way to show me both
    # and give me toggle reaching vs already reached"). `reached` is the
    # historical board — price back INSIDE a tested band. `approaching` is the
    # same scan's fourth predicate — price still ABOVE the band, close, and
    # FALLING toward it — so the order can be set BEFORE the arrival instead
    # of read about afterward. Same cache, zero extra scan cost.
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

    # A 2x2 since 2026-08-31 ("hit the 'In the orderblock' to see all the
    # stocks"): the PHASE gives the moment (approaching | reached), the TARGET
    # gives the level (demand band | fresh SMC order block).
    if phase == "approaching":
        rows = (data.get("approaching_ob_rows")
                if target == "order_block"
                else data.get("approaching_rows")) or []
    elif target == "order_block":
        # Reached, order-block flavour: INSIDE a fresh block on its first
        # touch. Youngest block first — the scan pre-sorts.
        rows = data.get("in_ob_rows") or []
    else:
        rows = [r for r in (data.get("rows") or []) if r.get("is_reentry")]
    matched = len(rows)
    live = _live_last([r.get("symbol") for r in rows])     # fetched ONCE, reused
    rows, dropped_bounced = drop_bounced(
        rows, lambda r: _bounce_ref_hi(r, phase, target), live)
    # The room floor (Ajay 2026-09-05, TRU: "There is only 0.5% room"): hide
    # names without `min_room` % of room from the LIVE print to the first
    # unbroken band overhead. Same print the bounce gate just used.
    rows, hidden_low_room, rooms = drop_low_room(rows, live, min_room)
    # Read-time order (2026-09-03). Approaching (both targets) and In-the-block
    # re-rank on the LIVE print with the scan's own key — closest first, flow
    # inside a 0.5% bucket; in_ob keeps block age as the lead. The REACHED zone
    # board is untouched: its rows are all inside the band, and it keeps the
    # measured R:R order plus the cheetah composite below.
    rank_key = (None if phase != "approaching" and target != "order_block"
                else _order.in_ob_key if phase != "approaching"
                else _order.approaching_ob_key if target == "order_block"
                else _order.approaching_key)
    if rank_key is not None:
        rows = rerank_live(rows, rank_key, live)
    flash_syms = _flash_symbols()
    tiles = []
    for rank, r in enumerate(rows):
        sym = (r.get("symbol") or "").upper()
        if not sym:
            continue
        plan = r.get("plan") or {}
        zone = r.get("entry_zone") or {}

        _ob = (None if target != "order_block"
               else r.get("approaching_ob") if phase == "approaching"
               else r.get("in_ob"))

        bands = []
        z_lo, z_hi = _num(zone.get("lo")), _num(zone.get("hi"))
        if z_lo is not None and z_hi is not None:
            bands.append({"kind": "demand", "lo": z_lo, "hi": z_hi, "label": "demand"})
        if _ob:
            blk = _ob.get("block") or {}
            b_lo, b_hi = _num(blk.get("lo")), _num(blk.get("hi"))
            if b_lo is not None and b_hi is not None:
                # The level this flavour is ABOUT — drawn in the SMC purple the
                # other surfaces already use, never in the band green: an order
                # block is a footprint, not the same kind of evidence.
                bands.append({"kind": "order_block", "lo": b_lo, "hi": b_hi,
                              "label": "order block"})
        for s in (r.get("supply_zones") or [])[:2]:
            s_lo, s_hi = _num(s.get("lo")), _num(s.get("hi"))
            if s_lo is not None and s_hi is not None:
                bands.append({"kind": "supply", "lo": s_lo, "hi": s_hi, "label": "supply"})

        lines = []
        if _ob and (_ob.get("trade") or {}).get("entry") is not None:
            # The order-block trade, not the zone plan — drawing the zone's BUY
            # on an order-block tile would price the wrong level.
            t = _ob["trade"]
            lines.append({"price": t["entry"], "label": "BUY", "tone": "buy"})
            if t.get("stop") is not None:
                lines.append({"price": t["stop"], "label": "STOP", "tone": "stop"})
            if t.get("target1") is not None:
                lines.append({"price": t["target1"], "label": "TARGET",
                              "tone": "target"})
        else:
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
                                        if r.get("bars_since_above") is not None else "—")},
                 # Room to the first unbroken band overhead on the live print
                 # ("+12.4% -> 84.10" | "open sky" | "in band"), 2026-09-05.
                 _room_stat_row(rooms, sym)]

        fell = _num(r.get("fell_from_pct"))
        appr_ob = (r.get("approaching_ob")
                   if phase == "approaching" and target == "order_block" else None)
        in_ob = (r.get("in_ob")
                 if phase != "approaching" and target == "order_block" else None)
        appr = (r.get("approaching")
                if phase == "approaching" and target != "order_block" else None)
        if in_ob:
            blk = in_ob.get("block") or {}
            why = (f"inside a fresh order block on its first touch — "
                   f"{in_ob.get('depth_pct')}% deep into the last down candle "
                   f"before a {blk.get('displacement_atr')}×ATR impulse "
                   f"{blk.get('bars_ago')} bars ago")
        elif appr_ob:
            blk = appr_ob.get("block") or {}
            why = (f"falling toward a fresh order block — "
                   f"{_dist_text(_disp_dist(r, live, appr_ob, 'block'), 'it', 'the block')}, "
                   f"down {abs(appr_ob['drift_pct']):.1f}% in "
                   f"{appr_ob['drift_bars']} sessions; the block is the last down "
                   f"candle before a {blk.get('displacement_atr')}×ATR impulse "
                   f"{blk.get('bars_ago')} bars ago")
        elif appr:
            why = (f"falling toward a tested band — "
                   f"{_dist_text(_disp_dist(r, live, appr, 'band'), 'it', 'the band')}, "
                   f"down {abs(appr['drift_pct']):.1f}% in {appr['drift_bars']} sessions")
        else:
            why = ((r.get("verdict") or {}).get("entry_read")
                   or (f"pulled back {fell:.0f}% into a demand zone it had left"
                       if fell is not None else "back inside a demand zone"))

        tiles.append({
            "symbol": sym,
            "name": r.get("name") or _name_for(sym),
            # Supply / Demand tab (Ajay 2026-09-03 "all pages"); this replaced
            # the 2026-08-17 Setup default — the Supply tab draws the same bands
            # at 6 months and carries today's live bar, so the arrival he just
            # saw on the tile is the first thing on the page.
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
            "_flow": _order.inflow_of(r),
            "badges": (([
                # The approach board's own facts lead: how far, how fast.
                _dist_badge(_disp_dist(r, live, appr, 'band'), "the band"),
                {"text": f"\u2193 {abs(appr['drift_pct']):.1f}% / {appr['drift_bars']}d",
                 "tone": "muted"}] if appr else [])
                + ([
                _dist_badge(_disp_dist(r, live, appr_ob, 'block'), "the order block"),
                {"text": f"\u2193 {abs(appr_ob['drift_pct']):.1f}% / {appr_ob['drift_bars']}d",
                 "tone": "muted"},
                {"text": "SMC \u00b7 uncited", "tone": "muted"}] if appr_ob else [])
                + ([
                {"text": "\u25c9 in the order block", "tone": "good"},
                {"text": f"{(in_ob.get('block') or {}).get('bars_ago')} bars old",
                 "tone": "muted"},
                {"text": "SMC \u00b7 uncited", "tone": "muted"}] if in_ob else [])
                + _zone_badges(r))
                + ([fb] if (fb := _flow_badge(_order.inflow_of(r))) else [])
                + (
                # ⚡ Trade Flash (Ajay 2026-08-24): a >= $250k one-sided burst
                # printed in/near this name's zone TODAY — the tape trigger his
                # zone entries were missing. Badge only; the detail lives in
                # the Tape tab and the Supply & Demand flash strip.
                [{"text": "⚡ Tape burst at zone", "tone": "good"}]
                if sym in flash_syms else []),
            # Approaching / In-the-block: the score IS the position in the
            # live re-rank above (`_finish` ranks `_score` DESCENDING) — one
            # definition of the order, not a second weighted one (the
            # supply_tiles pattern). The reached board keeps the quality of
            # the plan (R:R), composited with flow x velocity below.
            "_score": (float(len(rows) - rank) if rank_key is not None
                       else (rr or 0.0)),
            "_m": tile_metrics(r),
        })
    # Cheetahs first (Ajay 2026-08-25: "fix the ranking of these Cheetahs on
    # top"). Default order = money flow, then how fast the share supply turns,
    # then his R:R within each bucket. Velocity needs the reference lookup, so
    # the whole matched set (<= LIMIT_MAX rows, process-cached) is enriched
    # BEFORE ranking — an explicit dropdown sort still overrides all of this.
    attach_velocity(tiles)
    if phase != "approaching" and target != "order_block":
        # Cheetah composite (flow × velocity × R:R) ranks the REACHED board.
        # The approaching board must NOT take it: its whole question is "which
        # band gets hit first", and a strong-flow name 4.8% out ranking above
        # a neutral one 0.3% out would answer a different question than the
        # toggle promises.
        for t in tiles:
            f = {"inflow": 2.0, None: 1.0, "neutral": 1.0,
                 "distribution": 0.0}.get(((t.get("_flow") or {}).get("state")), 1.0)
            v = (t.get("_m") or {}).get("velocity")
            vlead = (2.0 if v is not None and v >= VELOCITY_FAST_PCT else
                     0.0 if v is not None and v <= VELOCITY_SLOW_PCT else 1.0)
            t["_score"] = f * 10000.0 + vlead * 1000.0 + (t.get("_score") or 0.0)
    out, meta = _finish(tiles, limit, themes_first, days, sort, min_tier)
    gex_as_of = _gex_decor(out, "demand")
    return {"tiles": out, **meta,
            "gex_as_of": gex_as_of,
            "phase": ("approaching" if phase == "approaching" else "reached"),
            "target": ("order_block" if target == "order_block" else "zone"),
            "matched": matched,
            "dropped_bounced": dropped_bounced,
            "bounce_done_pct": BOUNCE_DONE_PCT,
            **_room_meta(min_room, hidden_low_room),
            "universe_key": data.get("universe_key"),
            "universe_label": data.get("universe_label"),
            # The universes the server actually offers, so the tab's
            # dropdown cannot drift from demand_reentry.UNIVERSES.
            "universe_choices": data.get("universe_choices"),
            "scanned": data.get("scanned"),
            # demand_reentry stamps its payload "as_of", not "generated_at" —
            # reading the wrong key here sent generated_at:null on every zones
            # response, which is why the board could never say when it scanned
            # (Ajay 2026-08-25: "I am lil skeptical this is working becuz I
            # have been seeing these from 2 days").
            "generated_at": data.get("as_of")}


# ---------------------------------------------------------------------------
# tab — Quick Bounce (Ajay 2026-09-06): names that historically turned at a
# demand band THE SAME DAY (or gapped up next morning), sitting at / just
# above a proven demand band now, with room to the first proven lid.
# supply_demand/quick_bounce.py owns the study + the row rule; this only
# draws. Stats are rebuilt weekly (cron) into Mongo `quick_bounce_stats`.
# ---------------------------------------------------------------------------
def _qb_study(meta: Optional[dict]) -> Optional[dict]:
    if not isinstance(meta, dict):
        return None
    keys = ("as_of", "universe", "studied", "events", "quick", "same_day", "gap_up",
            "quick_rate_pct", "first_day_rate_pct", "placebo_rate_pct", "edge_pts",
            "qualifying", "persistence", "params")
    return {k: meta.get(k) for k in keys}


def quick_bounce_tiles(limit: int = LIMIT_DEFAULT, days: int = BARS_DEFAULT,
                       themes_first: bool = THEMES_FIRST_DEFAULT,
                       sort: str = DEFAULT_SORT, min_tier: str = DEFAULT_MIN_TIER,
                       min_room: Optional[float] = None) -> dict:
    from supply_demand import quick_bounce as QB, zone_store
    from supply_demand import room_floor as RF

    stats = QB.load_stats()
    meta = QB.load_meta()
    study = _qb_study(meta)
    base = {"tiles": [], "study": study, "disclaimer": QB.DISCLAIMER,
            **_room_meta(min_room, 0)}
    if not stats:
        return {**base, "note": "Quick-bounce statistics are not built yet — the weekly study "
                                "(python -m supply_demand.quick_bounce) fills them."}
    qual = {s: st for s, st in stats.items() if QB.qualifies(st)}
    if not qual:
        return {**base, "note": "No name in the universe clears the list bar "
                                "(>= %d visits, >= %d%% quick)." % (QB.MIN_EVENTS, QB.MIN_QUICK_RATE_PCT)}
    store_day, docs = zone_store.load_latest(list(qual))
    live = _live_last(list(qual))
    prints = {s: px for s, px in live.items() if px}
    for s, d in docs.items():
        if s not in prints:                      # no live print: the store's last closed bar
            px = _num(d.get("prev_close"))       # (store docs carry prev_close, not `recent`)
            if px:
                prints[s] = px
    floor = RF.MIN_ROOM_DEFAULT if min_room is None else float(min_room)
    res = QB.live_rows(qual, docs, prints, floor if floor > 0 else None)
    rows = res["rows"]
    tiles = []
    for rank, r in enumerate(rows):
        sym = r["symbol"]
        band = r["band"]
        st = r["stats"] or {}
        room = r.get("room") or {}
        bands = [{"kind": "demand", "lo": band["lo"], "hi": band["hi"], "label": "demand"}]
        tb = room.get("band") or {}
        if _num(tb.get("lo")) is not None and _num(tb.get("hi")) is not None:
            bands.append({"kind": "supply", "lo": float(tb["lo"]), "hi": float(tb["hi"]),
                          "label": "first proven lid"})
        lines = [{"price": float(band["hi"]), "label": "BUY", "tone": "buy"},
                 {"price": float(r["stop"]), "label": "STOP", "tone": "stop"}]
        if r.get("target") is not None:
            lines.append({"price": float(r["target"]), "label": "TARGET", "tone": "target"})
        n, q = int(st.get("events") or 0), int(st.get("quick") or 0)
        rate = st.get("quick_rate_pct")
        first = int(st.get("first_day_quick") or 0)
        stats_rows = [
            {"k": "Quick", "v": f"{q}/{n} ({rate:.0f}%)" if rate is not None else "—"},
            {"k": "1st day", "v": f"{first}/{n}"},
            {"k": "Any-day base", "v": (f"{st['placebo_rate_pct']:.0f}%"
                                        if st.get("placebo_rate_pct") is not None else "—")},
            {"k": "To band", "v": ("inside" if r["state"] == "inside" else f"+{r['dist_pct']:.1f}%")},
            {"k": "Room", "v": (f"+{room['room_pct']:g}% → {room['target']:g}" if room.get("target")
                                else "open sky")},
            {"k": "Risk", "v": f"{r['risk_pct']:.1f}% → {r['stop']:g}"},
            {"k": "Last quick", "v": st.get("last_quick_date") or "—"},
        ]
        edge = st.get("edge_pts")
        badges = [({"text": "◉ in the demand band", "tone": "good"} if r["state"] == "inside"
                   else {"text": f"{r['dist_pct']:.1f}% above the band", "tone": "muted"}),
                  {"text": f"🪃 same-day {int(st.get('same_day') or 0)} · gap-up {int(st.get('gap_up') or 0)}",
                   "tone": "good" if q else "muted"}]
        if edge is not None:
            badges.append({"text": f"{edge:+.0f} pts vs its own base rate",
                           "tone": "good" if edge >= 10 else "muted"})
        if r.get("rr") is not None:
            badges.append({"text": f"{r['rr']:.1f}R to the lid", "tone": "good" if r["rr"] >= 2 else "muted"})
        tiles.append({
            "symbol": sym, "name": _name_for(sym),
            "title": f"{sym} — quick bounce {rate:.0f}% ({q}/{n})" if rate is not None else sym,
            "why": r.get("plan") or "",
            "href": _href(sym, "supply"),
            "bars": [], "_bars": {"days": days},
            "bands": bands, "lines": lines, "markers": [],
            "stats": stats_rows, "badges": badges, "theme": _theme(sym),
            "_score": float(len(rows) - rank),
            "_m": {"avg_turnover": _num(stats.get(sym, {}).get("avg_dollar_vol_50")),
                   "velocity": None, "avg_shares": None},
        })
    out, fmeta = _finish(tiles, limit, themes_first, days, sort, min_tier)
    return {"tiles": out, **fmeta, "study": study, "disclaimer": QB.DISCLAIMER,
            "matched": len(rows), "qualifying": len(qual),
            "no_band": res["no_band"], "no_print": res["no_print"],
            "store_date": store_day.isoformat() if store_day else None,
            "generated_at": (meta or {}).get("generated_at"),
            **_room_meta(min_room, res["hidden_room"])}


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

def earnings_tiles(limit: int = LIMIT_DEFAULT, days: int = BARS_DEFAULT) -> dict:
    """Institutional volume around TODAY's earnings print.

    Ajay 2026-08-19: *"I need a tracker on the Chart maps page a new tab..
    Where it tracks earnings that had huge instituonal volume. Like BULL for
    example and TGT"*.

    Detection lives in `chart_maps/earnings.py`, which reuses the existing
    earnings stack (`sepa/earnings_watch` for the calendar, the shared
    `earnings_picks.reaction_read` to anchor the reaction bar) rather than
    standing up a second one. This function only turns rows into tiles.

    REACTED tiles come first, then UPCOMING. Grouped rather than interleaved by
    size: a name whose numbers are out and one carrying a binary event tonight
    are different decisions, and sorting them together would make him read
    every badge to tell which is which.
    """
    from . import earnings as E

    try:
        data = E.scan()
    except Exception as exc:
        log.warning("chart-maps: earnings scan failed: %s", exc)
        return {"tiles": [], "note": "earnings data unavailable"}

    tiles = []
    groups = [(E.REACTED, data.get("reacted") or []),
              (E.UPCOMING, data.get("upcoming") or [])]
    rank = 0
    for phase, rows in groups:
        for r in rows:
            sym = (r.get("symbol") or "").upper()
            if not sym:
                continue
            rank += 1
            gap = _num(r.get("gap_pct"))
            chg = _num(r.get("change_pct"))
            loc = _num(r.get("close_loc"))
            vr = _num(r.get("vol_ratio"))
            dv = _num(r.get("dollar_vol"))

            stats = [
                {"k": "Volume", "v": f"{vr:.1f}x" if vr is not None else "—"},
                {"k": "$ traded", "v": _usd_short(dv)},
                {"k": "Day", "v": f"{chg:+.1f}%" if chg is not None else "—"},
                # The discriminator. 1.00 = closed on the high.
                {"k": "Close in range", "v": f"{loc:.2f}" if loc is not None else "—"},
            ]
            if gap is not None:
                stats.append({"k": "Gap", "v": f"{gap:+.1f}%"})
            sp = _num(r.get("surprise_pct"))
            if sp is not None:
                stats.append({"k": "EPS surprise", "v": f"{sp:+.0f}%"})

            if phase == E.REACTED:
                badges = [{"text": "Reported today", "tone": "good"}]
                # A gap DOWN that closed near the high is the TGT signature and
                # the most informative thing on the tile — institutions did not
                # just buy, they bought what everyone else was selling.
                if gap is not None and gap < -0.5:
                    badges.append({"text": "Bought the gap down", "tone": "good"})
                why = (f"reported today, {chg:+.1f}% on {vr:.1f}x volume, "
                       f"closed at {loc:.2f} of its range"
                       if None not in (chg, vr, loc) else "institutional buying on the report")
            else:
                badges = [{"text": "Reports " + (r.get("reports_in") or "today"),
                           "tone": "warn"}]
                why = (f"{chg:+.1f}% on {vr:.1f}x volume INTO a print that lands "
                       f"{r.get('reports_in') or 'today'}"
                       if None not in (chg, vr) else "accumulation into the print")

            tiles.append({
                "symbol": sym,
                "name": _name_for(sym),
                # Setup tab, matching the zone tiles (Ajay 2026-08-17).
                "href": _href(sym, "supply"),
                "bars": [],
                "bands": [],
                "lines": ([{"price": _num(r.get("prev_close")), "label": "PRIOR CLOSE",
                            "tone": "neutral"}]
                          if _num(r.get("prev_close")) is not None else []),
                "markers": [{"date": r.get("date"), "label": "earnings",
                             "kind": "confirm"}] if r.get("date") else [],
                "stats": stats,
                "why": why,
                "theme": _theme(sym),
                "badges": badges,
                "phase": phase,
                "_score": float(1000 - rank),
            })

    short = tiles[:limit + BAR_BUFFER]
    _attach_bars(short, days)
    out = [t for t in short if t.get("bars")][:limit]
    for t in out:
        t.pop("_score", None)
        t.pop("_bars", None)
    return {
        "tiles": out,
        "as_of": data.get("as_of"),
        "criteria": data.get("criteria"),
        "counts": {"reacted": len(data.get("reacted") or []),
                   "upcoming": len(data.get("upcoming") or []),
                   "calendar_names": data.get("calendar_names")},
        "note": ("Same-day only: names that reported today, and names reporting "
                 "after today's close that institutions are buying into. "
                 "Buying only — distribution is not shown."),
    }


def _usd_short(v) -> str:
    """$1.5B / $281M. Whole units — a dollar-volume figure carrying cents is
    false precision on a number that moves by millions between prints."""
    n = _num(v)
    if n is None:
        return "—"
    if n >= 1e9:
        return f"${n / 1e9:.1f}B"
    if n >= 1e6:
        return f"${n / 1e6:.0f}M"
    return f"${n / 1e3:.0f}K"

# Bonde sales tiers that clear the falling-knife gate on the Deep Demand and
# Gabbar boards (Ajay 2026-08-25: "both need pradeep bonde's sales and revenus
# quarter logic ... so we are not catching falling knives"). The tier names and
# the 5% floor behind "steady" are sepa/sales.py's — Bonde's own documented
# floor ("I take 5%"), contract-locked there. This tuple only SELECTS tiers;
# it must never redefine a threshold.
from sepa.sales import BONDE_PASS_TIERS  # one definition — sepa/sales.py


def _bonde_gate(snap: Optional[dict]) -> tuple[str, Optional[dict]]:
    """("pass"|"fail"|"unknown", sales_block) for one symbol's sales snapshot."""
    sales = (snap or {}).get("sales") or None
    if not sales or sales.get("score") is None:
        return "unknown", sales
    return ("pass" if sales.get("tier") in BONDE_PASS_TIERS else "fail"), sales


def _sales_badge(sales: dict) -> dict:
    g = _f(sales.get("growth_yoy_pct"))
    accel = " · accelerating" if sales.get("accelerating") else ""
    return {"text": f"🟢 Sales {sales.get('tier')} {g:+.0f}%{accel}" if g is not None
            else f"🟢 Sales {sales.get('tier')}", "tone": "good"}


def _gex_decor(tiles: list, wall_kind: str) -> Optional[str]:
    """🧲 dealer-gamma chips on shown tiles (Ajay 2026-08-27: "add the gex
    chips to the demand zone tabs"). Decoration only, applied AFTER _finish
    so ranking never depends on it, and only over the shown slice (~24
    symbols — the topping-tab model).

    The verdict is gex_history.board_bucket — the SAME pure read the GEX
    Board page buckets with, so the two surfaces can never disagree:
    bullish → dips get bought (good for a zone entry), bearish → moves get
    amplified (the knife warning), mixed → NO badge: only a verdict earns
    pixels. Coverage is the nightly ~200-name snapshot universe, so most
    full-universe tiles legitimately carry nothing.

    Wall confluence is the demand-zone-specific read: the put wall sitting
    ON the drawn demand band (call wall on a supply lid) means dealer
    hedging defends the same shelf the chart found — flagged within
    _GEX_WALL_PCT of the band edges.

    Rows are POST-CLOSE snapshots; returns the newest date_et seen so the
    payload can say whose close the chips describe. Never raises."""
    try:
        from options import gex_history as GH
        snaps = GH.snapshot_for([t.get("symbol") for t in tiles])
        if not snaps:
            return None
        as_of = None
        for t in tiles:
            row = snaps.get(t.get("symbol"))
            if not row:
                continue
            as_of = max(as_of or "", row.get("date_et") or "")
            bucket = GH.board_bucket(row)
            if bucket == "bullish":
                t.setdefault("badges", []).append(
                    {"text": "🧲 Gamma helps — dips get bought", "tone": "good"})
            elif bucket == "bearish":
                t.setdefault("badges", []).append(
                    {"text": "🧲 Gamma hurts — moves amplified", "tone": "warn"})
            wall = _f(row.get("put_wall" if wall_kind == "demand" else "call_wall"))
            if wall is None:
                continue
            for b in t.get("bands") or []:
                if b.get("kind") != wall_kind:
                    continue
                lo, hi = _f(b.get("lo")), _f(b.get("hi"))
                if lo is None or hi is None:
                    continue
                if lo * (1 - _GEX_WALL_PCT / 100) <= wall <= hi * (1 + _GEX_WALL_PCT / 100):
                    t.setdefault("badges", []).append(
                        {"text": (f"🛡️ Put wall ${wall:g} at zone"
                                  if wall_kind == "demand"
                                  else f"🧱 Call wall ${wall:g} at lid"),
                         "tone": "good"})
                    break
        return as_of or None
    except Exception as exc:                       # decoration never breaks a board
        log.warning("chart-maps: gex decor failed: %s", exc)
        return None


# Wall-on-band tolerance, % beyond the band edges. 2% mirrors CLUSTER_PCT's
# "same level seen twice" scale in chart_maps/support.py.
_GEX_WALL_PCT = 2.0


def _flow_badge(inflow: Optional[dict]) -> Optional[dict]:
    """The Deep Demand flow verdict as one badge, for any board whose rows
    carry it (Ajay 2026-08-25: "bake in CMF flow logic in to this one too").
    Neutral and missing render NOTHING — only a verdict earns pixels."""
    f = inflow or {}
    cmf = _f(f.get("cmf_20"))
    if f.get("state") == "inflow":
        return {"text": (f"💰 Money flowing in — CMF {cmf:+.2f}"
                         if cmf is not None else "💰 Money flowing in"),
                "tone": "good"}
    if f.get("state") == "distribution":
        return {"text": (f"🔻 Still distributing — CMF {cmf:+.2f}"
                         if cmf is not None else "🔻 Still distributing"),
                "tone": "warn"}
    return None


def deep_demand_tiles(limit: int = LIMIT_DEFAULT, days: int = BARS_DEFAULT,
                      universe: str = "full",
                      themes_first: bool = THEMES_FIRST_DEFAULT,
                      sort: str = DEFAULT_SORT,
                      min_tier: str = DEFAULT_MIN_TIER,
                      phase: str = "reached",
                      min_room: Optional[float] = None) -> dict:
    """Deep Demand: broke the FIRST demand band, entering the SECOND — and
    Bonde sales say the business didn't break with the price.

    Ajay 2026-08-25: "stocks entering second level of demand zone from the top
    but sales are intact ... penalized stocks that actually have good revenue
    but market does not realize it."

    Price half comes from the demand scan's `deep_rows` (computed in-scan
    because these names usually fail trend_ok and never reach `rows` —
    supply_demand/deep_demand.py). Sales half joins the weekly research cache
    at read time. The gate here is STRICT both ways: failing Bonde's floor
    excludes, and UNKNOWN sales also exclude — this board's whole claim is
    "the revenue is intact", which cannot be said about a name with no data.
    Both exclusion counts ride on the payload; a thin board explains itself.
    """
    from supply_demand import demand_reentry as D
    from sepa import research

    data = D.cached_or_warm(universe, limit=LIMIT_MAX)
    if data.get("warming"):
        return {"tiles": [], "warming": True,
                "universe_key": data.get("universe_key") or universe,
                "progress": data.get("progress"),
                "note": "scanning for second-level demand arrivals…"}

    rows = data.get("deep_rows") or []
    # The toggle (Ajay 2026-08-31). deep_demand.read already classifies every
    # row "in" (inside the second band) vs "near" (falling toward it within
    # NEAR_PCT), and the old board mixed the two. The toggle splits along that
    # existing line: reached = in, approaching = near. A filter, not a new
    # predicate — nothing about what qualifies changed.
    want_state = "near" if phase == "approaching" else "in"
    rows = [r for r in rows
            if ((r.get("deep_demand") or {}).get("state") == want_state)]
    live = _live_last([r.get("symbol") for r in rows])     # fetched ONCE, reused
    rows, dropped_bounced = drop_bounced(
        rows, lambda r: _num(((r.get("deep_demand") or {}).get("second_band") or {}).get("hi")),
        live)
    # The room floor (Ajay 2026-09-05: "the same logic in Demand and deep
    # demand zone"). Room is read to the first unbroken band overhead — for a
    # deep row that is usually its BROKEN first band, drawn on the tile as
    # the lid — from the live print, the second band excluded as the entry.
    rows, hidden_low_room, rooms = drop_low_room(rows, live, min_room)
    # Closest to the second band first on the LIVE print, flow inside a 0.5%
    # bucket (Ajay 2026-09-03) — the same key the scan sorted with
    # (deep_demand.sort_key -> demand_order.deep_key), re-read at the live
    # price. Supersedes the 2026-08-26 CMF-first weighted score.
    rows = rerank_live(rows, _order.deep_key, live)
    snaps = research.sales_snapshot([r.get("symbol") for r in rows if r.get("symbol")])
    flash_syms = _flash_symbols()

    tiles, dropped_weak, dropped_unknown = [], 0, 0
    for rank, r in enumerate(rows):
        sym = (r.get("symbol") or "").upper()
        d = r.get("deep_demand") or {}
        if not sym or not d:
            continue
        state, sales = _bonde_gate(snaps.get(sym))
        if state == "fail":
            dropped_weak += 1
            continue
        if state == "unknown":
            dropped_unknown += 1
            continue

        top, second = d.get("top_band") or {}, d.get("second_band") or {}
        bands = []
        if _num(top.get("lo")) is not None:
            bands.append({"kind": "supply", "lo": _num(top.get("lo")),
                          "hi": _num(top.get("hi")),
                          "label": "1st demand · broken"})
        if _num(second.get("lo")) is not None:
            bands.append({"kind": "demand", "lo": _num(second.get("lo")),
                          "hi": _num(second.get("hi")),
                          "label": ("2nd demand · approaching"
                                    if phase == "approaching"
                                    else "2nd demand · entering")})

        lines = []
        plan = r.get("plan") or {}
        for key, label, tone in (("entry_ref", "BUY", "buy"),
                                 ("stop", "STOP", "stop"),
                                 ("target", "TARGET", "target")):
            pv = _num(plan.get(key))
            if pv is not None:
                lines.append({"price": pv, "label": label, "tone": tone})

        g = _f((sales or {}).get("growth_yoy_pct"))
        below = _f(d.get("below_top_pct"))
        arriving = ("inside the 2nd band" if d.get("state") == "in"
                    else f"{d.get('dist_pct'):.1f}% above the 2nd band")
        why = (f"broke its 1st demand band ({below:.0f}% below it), now "
               f"{arriving} — sales {'+' if (g or 0) >= 0 else ''}{g:.0f}% YoY "
               f"say the business didn't break with the price"
               if below is not None and g is not None else
               "second-level demand arrival with Bonde-intact sales")

        badges = [{"text": ("🩹 In 2nd demand band" if d.get("state") == "in"
                             else "🩹 Entering 2nd band"), "tone": "warn"}]
        # The flow verdict (Ajay 2026-08-25: "bullish momentum stocks and
        # inflow signals"). States and numbers come from sepa/volume via
        # deep_demand.inflow_read — never re-derived here.
        flow = _order.inflow_of(r) or {}
        f_state = flow.get("state")
        f_cmf = _f(flow.get("cmf_20"))
        if f_state == "inflow":
            badges.append({"text": (f"💰 Money flowing in — CMF {f_cmf:+.2f} · "
                                     f"{flow.get('accum_days_25', 0)}↑/"
                                     f"{flow.get('dist_days_25', 0)}↓ days"
                                     if f_cmf is not None else "💰 Money flowing in"),
                           "tone": "good"})
        elif f_state == "distribution":
            badges.append({"text": (f"🔻 Still distributing — CMF {f_cmf:+.2f}"
                                     if f_cmf is not None else "🔻 Still distributing"),
                           "tone": "warn"})
        if flow.get("pocket_pivot"):
            badges.append({"text": "⚡ Pocket pivot", "tone": "good"})
        if sales:
            badges.append(_sales_badge(sales))
        if not r.get("trend_ok", True):
            badges.append({"text": "⚠ Trend gate failed — that's the premise",
                           "tone": "muted"})
        if sym in flash_syms:
            badges.append({"text": "⚡ Tape burst at zone", "tone": "good"})

        liq = r.get("liquidity") or {}
        stats = [{"k": "Sales YoY", "v": f"{g:+.0f}%" if g is not None else "—"},
                 {"k": "Flow", "v": (f"CMF {f_cmf:+.2f}" if f_cmf is not None else "—")},
                 {"k": "Vol days", "v": (f"{flow.get('accum_days_25')}↑ / "
                                          f"{flow.get('dist_days_25')}↓"
                                          if flow.get("accum_days_25") is not None else "—")},
                 {"k": "Liquidity", "v": (liq.get("tier") or "—")},
                 _room_stat_row(rooms, sym)]

        # The score IS the position in the live re-rank above (`_finish`
        # ranks `_score` DESCENDING): inside the band, then nearest, flow
        # and CMF inside a 0.5% bucket. Sales growth no longer ranks — it
        # GATES (Bonde) and is said on the badge. Replaced the 2026-08-26
        # weighted flow/CMF/in-band/sales score on 2026-09-03.
        tiles.append({
            "symbol": sym,
            "name": r.get("name") or _name_for(sym),
            "href": _href(sym, "supply"),
            "bars": [],
            "_bars": {"days": _zone_window(second) if second else days},
            "bands": bands,
            "lines": lines,
            "markers": [],
            "stats": stats,
            "why": why,
            "theme": _theme(sym),
            "badges": badges,
            "_score": float(len(rows) - rank),
            "_m": tile_metrics(r),
        })

    out, meta = _finish(tiles, limit, themes_first, days, sort, min_tier)
    gex_as_of = _gex_decor(out, "demand")
    flow_counts = {"inflow": 0, "neutral": 0, "distribution": 0}
    for t in tiles:
        st = next((b for b in t.get("badges") or [] if "Money flowing in" in b["text"]), None)
        if st:
            flow_counts["inflow"] += 1
        elif any("Still distributing" in b["text"] for b in t.get("badges") or []):
            flow_counts["distribution"] += 1
        else:
            flow_counts["neutral"] += 1
    return {"tiles": out, **meta,
            "phase": ("approaching" if phase == "approaching" else "reached"),
            "matched": len(rows),
            "gex_as_of": gex_as_of,
            "flow_counts": flow_counts,
            "dropped_weak_sales": dropped_weak,
            "dropped_bounced": dropped_bounced, "bounce_done_pct": BOUNCE_DONE_PCT,
            **_room_meta(min_room, hidden_low_room),
            "dropped_no_sales_data": dropped_unknown,
            "deep_n": data.get("deep_n"),
            "universe_key": data.get("universe_key"),
            "universe_label": data.get("universe_label"),
            "universe_choices": data.get("universe_choices"),
            "scanned": data.get("scanned"),
            "note": (f"Names that broke their highest demand band and are arriving at the "
                     f"second — kept only when Bonde sales tiers (steady/strong/explosive, "
                     f"his 5% YoY floor) say the business is intact. This scan: "
                     f"{len(rows)} arrivals, {dropped_weak} dropped for weak/declining "
                     f"sales, {dropped_unknown} dropped for no sales data. Money flow "
                     f"(CMF-20 + up/down volume days, Minervini p.71-76 counts): "
                     f"{flow_counts['inflow']} flowing in · {flow_counts['neutral']} neutral · "
                     f"{flow_counts['distribution']} still distributing. Order: "
                     f"{'nearest the second band first' if phase == 'approaching' else 'inside the second band first'}"
                     f" on the live print, money flow (CMF) ranking within a 0.5% "
                     f"distance bucket; names already {BOUNCE_DONE_PCT:.0f}% off the band "
                     f"are dropped, and so are names with under "
                     f"{_room_meta(min_room, 0)['min_room']:g}% of room to the first band "
                     f"overhead on the live print ({hidden_low_room} hidden). These fail the "
                     f"trend gate BY DESIGN — size and stop accordingly."),
            "generated_at": data.get("as_of")}


def topping_tiles(limit: int = LIMIT_DEFAULT, days: int = BARS_DEFAULT,
                  themes_first: bool = THEMES_FIRST_DEFAULT,
                  sort: str = DEFAULT_SORT,
                  min_tier: str = DEFAULT_MIN_TIER) -> dict:
    """S3 Topping / short candidates — aggressive distribution, book-cited.

    Ajay 2026-08-25: "for shorting I need ones which recently got heavy
    institutional selling and in S3 topping stage. Our flow and distribution
    is occurring aggressively. Add any other indicators that are in the book."

    A pure SLICE of the SEPA scan file — every read below already exists on
    the row, each from a book-cited module (verified against the brain RAG,
    both books, 2026-08-25):

      * stage 3 "Topping" / 4 "Decline"        — sepa/stage.py, TLSW pp.73-76
      * more down days on above-avg volume     — sepa/volume.py, TLSW p.76
      * CMF outflow zone                       — sepa/volume.py thresholds
      * largest 1-day/1-week drop since Stage 2— sepa/sell_signals.py, TLSW p.90
      * below 50-day on heavy vol / below 200  — sell_signals; TLSW p.75,
                                                 TTLAC §6 (200-day break is
                                                 Minervini's own short trigger)
      * climax / churn / heavy-vol down day /
        high-vol reversal / exhaustion gap     — sepa/climax_distribution.py,
                                                 TTLAC §9 pp.186-188
      * late-stage base count (4th/5th)        — row.base_count, TLSW pp.81-82

    Gate: stage in (3, 4) AND at least TWO independent distribution
    evidences. Ranked by how aggressively the selling reads (evidence count,
    then climax + sell-signal severity, then RS weakness). Declining Bonde
    sales appear as a CONFIRMING badge only — fundamentals lag at tops.
    NOT an inverted buy list: nothing here is backtested, and the note says
    so out loud.
    """
    from sepa import scanner
    from sepa import research
    from sepa.volume import DIST_RATIO_THRESHOLD

    latest = scanner.load_latest()
    if not latest:
        return {"tiles": [], "note": "no scan yet — run a SEPA scan first"}
    rows = latest.get("all_results") or []
    sell_flash = _flash_sell_symbols()

    picked = []
    for r in rows:
        stg = r.get("stage") or {}
        if stg.get("stage") not in (3, 4):
            continue
        # No ETFs: the first live board surfaced LABD — a 3x INVERSE fund —
        # as a "short". Wrappers track baskets; stage/distribution reads on
        # them describe the basket, not an institutional exit.
        if r.get("is_etf"):
            continue
        vol = r.get("volume") or {}
        sell = r.get("sell_signals") or {}
        sig = sell.get("signals") or {}
        clim = r.get("climax_distribution") or {}
        tells = clim.get("tells") or {}

        evidence = []   # (badge_text, tone)
        dn, up = vol.get("dn_days_on_avg_vol"), vol.get("up_days_on_avg_vol")
        ratio = _f(vol.get("up_down_vol_ratio"))
        if (vol.get("accumulation_strength") == "distributing"
                or (ratio is not None and ratio <= DIST_RATIO_THRESHOLD)):
            evidence.append((f"📉 {dn}↓ vs {up}↑ days on above-avg volume", "warn"))
        cmf = _f(vol.get("cmf_20"))
        if vol.get("cmf_signal") == "outflow":
            evidence.append((f"🔻 Outflow — CMF {cmf:+.2f}" if cmf is not None
                             else "🔻 Outflow", "warn"))
        dd, ad = vol.get("distribution_days_25") or 0, vol.get("accumulation_days_25") or 0
        if dd - ad >= 3:
            evidence.append((f"📉 {dd} distribution vs {ad} accumulation days", "warn"))
        if sig.get("largest_1d_decline_since_stage2") or sig.get("largest_1w_decline_since_stage2"):
            span = "1-day" if sig.get("largest_1d_decline_since_stage2") else "1-week"
            evidence.append((f"💥 Largest {span} drop since the Stage 2 advance", "warn"))
        if sig.get("close_below_50ma_on_high_vol"):
            evidence.append(("⬇ Closed below the 50-day on heavy volume", "warn"))
        if sig.get("close_below_200ma"):
            evidence.append(("⬇ Below the 200-day — Minervini's own short trigger", "warn"))
        if r.get("distribution_selling"):
            why_d = (r.get("distribution_reason") or "selling into strength")
            evidence.append((f"🏦 {why_d}", "warn"))
        if clim.get("in_climax") or sig.get("climax_run_25pct_in_3w"):
            g = _f(clim.get("climax_gain_pct")) or _f(sell.get("climax_15d_gain_pct"))
            evidence.append((f"🔺 Climax run {g:+.0f}% in 3 weeks" if g is not None
                             else "🔺 Climax run", "warn"))
        if tells.get("churning"):
            evidence.append(("🌀 Churning — heavy volume, no progress", "warn"))
        if tells.get("heavy_volume_down_day") or tells.get("largest_volume_down_in_move"):
            evidence.append(("⚠ Heaviest volume landed on a DOWN day", "warn"))
        if tells.get("high_volume_reversal"):
            evidence.append(("↩ High-volume reversal", "warn"))
        if tells.get("exhaustion_gap"):
            evidence.append(("⛽ Exhaustion gap", "warn"))
        bc = r.get("base_count")
        if isinstance(bc, (int, float)) and bc >= 4:
            evidence.append((f"🏗 Base #{int(bc)} — late stage", "muted"))

        # Three independent reads, not two: at two, a cautious tape put more
        # than HALF the 1,673-name universe on the board (measured 1,054 on
        # 2026-08-25) — a list that size is a market comment, not a short
        # list. "Aggressively" was the ask.
        if len(evidence) < 3:
            continue

        rs = _f(r.get("rs_rank"))
        # Stage 3 outranks stage 4 at equal evidence: HIS ask is the TOPPING
        # stage, and Minervini's short trigger (TTLAC §6) fires at the fresh
        # 200-day break — an RS-1 name a year into Stage 4 is a corpse, not
        # a setup. RS weakness stays as a mild tiebreak only.
        score = (len(evidence) * 10.0
                 + (clim.get("severity") or 0) * 3.0
                 + (sell.get("severity") or 0) * 2.0
                 + (8.0 if stg.get("stage") == 3 else 0.0)
                 + ((100.0 - rs) / 20.0 if rs is not None else 0.0))

        trend = r.get("trend") or {}
        lines = []
        for key, label, tone in (("ma200", "200d", "stop"), ("ma50", "50d", "neutral")):
            mv = _f(trend.get(key))
            if mv is not None:
                lines.append({"price": mv, "label": label, "tone": tone})

        badges = [{"text": ("S4 Decline" if stg.get("stage") == 4 else
                            ("S3 Topping · volume disagreement"
                             if stg.get("volume_disagreement") else "S3 Topping")),
                   "tone": "warn"}]
        badges += [{"text": t, "tone": tone} for t, tone in evidence[:5]]
        if len(evidence) > 5:
            # The cap keeps tiles readable; the count keeps it honest — a name
            # with 8 tells must not LOOK like a name with 5.
            badges.append({"text": f"+{len(evidence) - 5} more tells", "tone": "muted"})
        if sym_in_flash := (r.get("symbol") in sell_flash):
            badges.append({"text": "⚡ Sell burst at zone today", "tone": "warn"})

        picked.append({
            "symbol": (r.get("symbol") or "").upper(),
            "name": r.get("name"),
            "href": _href((r.get("symbol") or "").upper(), "supply"),
            "bars": [],
            "_bars": {"days": days},
            "bands": [],
            "lines": lines,
            "markers": [],
            "stats": [
                {"k": "Stage", "v": stg.get("label") or "—"},
                {"k": "Dist days", "v": f"{dd}↓ / {ad}↑"},
                {"k": "CMF", "v": f"{cmf:+.2f}" if cmf is not None else "—"},
                {"k": "RS", "v": f"{rs:.0f}" if rs is not None else "—"},
            ],
            "why": (f"{len(evidence)} distribution tells — " +
                    "; ".join(t for t, _ in evidence[:3])),
            "theme": _theme((r.get("symbol") or "").upper()),
            "badges": badges,
            "_score": score,
            "_m": tile_metrics(r),
        })

    # Bonde inverse — declining sales CONFIRM a short read (badge only;
    # fundamentals lag at tops, so never a gate).
    try:
        snaps = research.sales_snapshot([t["symbol"] for t in picked])
        for t in picked:
            gate, sales = _bonde_gate(snaps.get(t["symbol"]))
            if gate == "fail" and sales:
                gs = _f(sales.get("growth_yoy_pct"))
                t["badges"].append({"text": (f"📉 Sales {sales.get('tier')} "
                                              f"{gs:+.0f}%" if gs is not None
                                              else f"📉 Sales {sales.get('tier')}"),
                                    "tone": "warn"})
                t["_score"] += 5.0
    except Exception:
        pass

    out, meta = _finish(picked, limit, themes_first, days, sort, min_tier)
    return {"tiles": out, **meta,
            "matched": len(picked),
            "note": ("Stage 3 topping / Stage 4 decline with at least two independent "
                     "distribution reads, ranked by how aggressive the selling is. "
                     "Every tell is the book's own: stage characteristics TLSW "
                     "pp.73-76; down-days-on-volume p.76; largest drop since the "
                     "Stage 2 advance p.90; climax/churn/reversal TTLAC §9 "
                     "pp.186-188 (ebook); the 200-day break close-on-low is "
                     "Minervini's own Stage 4 short trigger, TTLAC §6. Declining "
                     "Bonde sales shown as confirmation only — fundamentals LAG at "
                     "tops. NOT an inverted buy list: none of this is backtested, "
                     "shorting risk is unlimited, and squeezes do not care about "
                     "chart stages — size accordingly."),
            "scan_generated_at": latest.get("generated_at")}


# Band-type lens for the gabbar tab (Ajay 2026-08-25: "may be a switch of
# select toggle for conservative 1 conservative 2 and aggressive"). "all"
# keeps the nearest-band read; a specific label re-measures every name
# against ONLY that band type, so "who is at their conservative 2 level"
# is one click, not a scan of the Conserv. stats.
GABBAR_LEVELS = ("all", "aggressive", "conservative 1", "conservative 2")


# Under Value gate (Ajay 2026-08-28: "undervalued stocks whose sales are
# incredible but their comparitive stock value is less.. Like Light path as
# an example"). PSG = price-to-sales DIVIDED BY revenue growth — a
# sales-based PEG. Calibrated on his archetype: LPTH at ~11.9x sales with
# +109% growth = PSG 0.11, so the bar sits at 0.15. Bonde tier must be
# strong (>=25%) or explosive (>=100%) first — "incredible sales" is the
# premise, cheapness alone is a value trap.
UNDERVALUE_MAX_PSG = 0.15
UNDERVALUE_TIERS = ("strong", "explosive")
UNDERVALUE_MAX_CANDIDATES = 120
# Base-effect guard: a company going from ~zero revenue to something posts
# +250,000% "growth" and any P/S — even JOBY's 59x — divides down to a
# PSG of ~0. That is a lottery ticket, not a mispriced grower. Growth is
# CAPPED here for the ratio, so past this point cheapness must come from
# the P/S side. LPTH (+109%) sits far below the cap and is untouched.
UNDERVALUE_GROWTH_CAP_PCT = 300.0


def psg_ratio(mkt_cap, rev_ttm, growth_yoy_pct):
    """Price/sales over growth (growth capped at UNDERVALUE_GROWTH_CAP_PCT).
    None whenever an input is missing or nonsensical — a fabricated
    valuation is worse than none."""
    try:
        mkt_cap = float(mkt_cap)
        rev_ttm = float(rev_ttm)
        growth = float(growth_yoy_pct)
    except (TypeError, ValueError):
        return None
    if mkt_cap <= 0 or rev_ttm <= 0 or growth <= 0:
        return None
    return (mkt_cap / rev_ttm) / min(growth, UNDERVALUE_GROWTH_CAP_PCT)


def _uv_band_state(zones, df, last):
    """(state, dist_pct) for the Under Value phase lens. PURE-ish.

    state: "in" (inside a demand band) | "near" (within APPROACH_NEAR_PCT
    above one AND falling per the demand scan's drift test) | "away" | None
    (no zones computed). The near test reuses demand_reentry's constants —
    one definition of "approaching" across every tab.
    """
    from supply_demand import demand_reentry as _dr

    if not zones:
        return None, None
    try:
        lp = float(last)
    except (TypeError, ValueError):
        return None, None
    demand = zones.get("demand_zones") or []
    for z in demand:
        lo, hi = z.get("lo"), z.get("hi")
        if lo is not None and hi is not None and lo <= lp <= hi:
            return "in", 0.0
    tops = [z.get("hi") for z in demand
            if z.get("hi") is not None and z["hi"] < lp]
    if not tops:
        return "away", None
    hi = max(tops)
    dist = (lp - hi) / lp * 100.0
    if dist > _dr.APPROACH_NEAR_PCT:
        return "away", round(dist, 2)
    try:
        closes = df["close"].tolist()
        ref = float(closes[-(_dr.APPROACH_DRIFT_BARS + 1)])
        drift = (float(closes[-1]) - ref) / ref * 100.0
    except Exception:
        return "away", round(dist, 2)
    if drift > -float(_dr.APPROACH_MIN_DRIFT_PCT):
        return "away", round(dist, 2)          # close, but rising = departing
    return "near", round(dist, 2)


def undervalue_tiles(limit: int = LIMIT_DEFAULT, days: int = BARS_DEFAULT,
                     themes_first: bool = THEMES_FIRST_DEFAULT,
                     sort: str = DEFAULT_SORT,
                     min_tier: str = DEFAULT_MIN_TIER,
                     phase: str = "all") -> dict:
    """Under Value board: explosive sales, lagging price tag.

    Screen: Bonde tier strong/explosive across the whole universe (weekly
    research cache, one query) → top UNDERVALUE_MAX_CANDIDATES by growth →
    market cap (shares outstanding × last close) and TTM revenue (rev_ttm
    Mongo cache, time-boxed fills) → keep PSG <= UNDERVALUE_MAX_PSG.
    Missing shares or revenue EXCLUDES with a count — never a made-up
    ratio. Zones computed per finalist from the shared price frame, so the
    tab is "supply demand zones for the undervalued" exactly as asked.
    """
    from sepa import prices, research, rev_ttm as rev_mod
    from sepa import universe as universe_mod
    from supply_demand import price_zones as pz

    try:
        universe = universe_mod.load_universe("full")
    except Exception:
        universe = []
    snaps = {}
    try:
        snaps = research.sales_snapshot(universe)
    except Exception as exc:
        log.warning("undervalue: sales snapshot failed: %s", exc)

    cands = []
    for sym, snap in snaps.items():
        sales = (snap or {}).get("sales") or {}
        if sales.get("tier") in UNDERVALUE_TIERS and sales.get("growth_yoy_pct"):
            cands.append((sym, sales))
    cands.sort(key=lambda t: -(t[1].get("growth_yoy_pct") or 0.0))
    cands = cands[:UNDERVALUE_MAX_CANDIDATES]

    revs = rev_mod.bulk([s for s, _ in cands])

    from short_interest import client as si_client
    flash_syms = _flash_symbols()
    tiles, no_rev, no_shares, too_rich = [], 0, 0, 0
    for sym, sales in cands:
        rev = revs.get(sym)
        if not rev:
            no_rev += 1
            continue
        try:
            shares = si_client._shares_outstanding(sym)
        except Exception:
            shares = None
        if not shares:
            no_shares += 1
            continue
        df = None
        try:
            df = prices.load_prices(sym)
        except Exception:
            pass
        if df is None or not len(df):
            continue
        last = float(df["close"].iloc[-1])
        mkt_cap = shares * last
        ratio = psg_ratio(mkt_cap, rev, sales.get("growth_yoy_pct"))
        if ratio is None:
            continue
        if ratio > UNDERVALUE_MAX_PSG:
            too_rich += 1
            continue

        zones = None
        try:
            zones = pz.compute(df)
        except Exception:
            zones = None
        bands = []
        for b in ((zones or {}).get("demand_zones") or [])[:2]:
            bands.append({"kind": "demand", "lo": float(b["lo"]),
                          "hi": float(b["hi"]), "label": "demand"})
        for b in ((zones or {}).get("supply_zones") or [])[:2]:
            bands.append({"kind": "supply", "lo": float(b["lo"]),
                          "hi": float(b["hi"]), "label": "supply"})

        ps = mkt_cap / rev
        g = sales.get("growth_yoy_pct")
        tail = df["close"].iloc[-min(len(df), 50):]
        avg_turnover = float((df["close"] * df["volume"])
                             .iloc[-min(len(df), 50):].mean())
        # Phase lens (Ajay 2026-08-31: "I need it in all the tabs possible").
        # A FILTER here, not a population switch: this board's population is a
        # valuation screen, and the default ("all") is the historical board
        # byte for byte. reached = inside a demand band; approaching = within
        # the demand scan's own near/drift standards above one. Same constants
        # imported so the tabs can never disagree on what "approaching" means.
        band_state, band_dist = _uv_band_state(zones, df, last)
        if phase == "reached" and band_state != "in":
            continue
        if phase == "approaching" and band_state != "near":
            continue

        badges = [
            {"text": f"💎 {ps:.1f}x sales vs +{g:.0f}% growth", "tone": "good"},
            _sales_badge(sales),
        ]
        if phase != "all" and band_state == "in":
            badges.insert(0, {"text": "\u25c9 in the demand band", "tone": "good"})
        elif phase != "all" and band_state == "near" and band_dist is not None:
            badges.insert(0, {"text": f"\u2192 {band_dist}% above the band",
                              "tone": "warn"})
        if sym in flash_syms:
            badges.append({"text": "⚡ Tape burst at zone", "tone": "good"})
        tiles.append({
            "symbol": sym,
            "name": _name_for(sym),
            "href": _href(sym, "analysis"),
            "bars": [],
            "_bars": {"days": days},
            "bands": bands,
            "lines": [{"price": last, "label": "now", "tone": "now"}],
            "markers": [],
            "stats": [
                {"k": "P/S", "v": f"{ps:.1f}x"},
                {"k": "Rev YoY", "v": f"+{g:.0f}%"},
                {"k": "PSG", "v": f"{ratio:.3f}"},
                {"k": "Mkt cap", "v": _usd_short(mkt_cap)},
            ],
            "why": (f"{g:+.0f}% revenue growth priced at {ps:.1f}x sales "
                    f"(PSG {ratio:.2f}) — the market hasn't re-rated it yet"),
            "theme": _theme(sym),
            "badges": badges,
            "_score": -ratio * 1000.0,          # cheapest-for-growth first
            "_m": tile_metrics({"liquidity": {"avg_dollar_vol": avg_turnover},
                                "last_close": last}),
        })

    out, meta = _finish(tiles, limit, themes_first, days, sort, min_tier)
    gex_as_of = _gex_decor(out, "demand")
    return {"tiles": out, **meta,
            "phase": (phase if phase in ("reached", "approaching") else "all"),
            "matched": len(tiles),
            "gex_as_of": gex_as_of,
            "screened": len(cands),
            "no_rev_data": no_rev,
            "no_shares_data": no_shares,
            "priced_for_growth": too_rich,
            "note": (f"Bonde strong/explosive sales across the whole universe "
                     f"({len(cands)} screened), kept only when the price tag "
                     f"LAGS the growth: price-to-sales ÷ revenue growth (PSG) "
                     f"≤ {UNDERVALUE_MAX_PSG:g} — calibrated on LPTH (~12x "
                     f"sales at +109% = 0.11). {too_rich} growers already "
                     f"priced for it; {no_rev} lacked a revenue figure and "
                     f"{no_shares} a share count — excluded, never estimated. "
                     f"Backlog and contracts are not machine-readable, so "
                     f"check the story before the chart. Cheapest-for-growth "
                     f"ranks first."),
            "generated_at": None}


def gabbar_tiles(limit: int = LIMIT_DEFAULT, days: int = BARS_DEFAULT,
                 themes_first: bool = THEMES_FIRST_DEFAULT,
                 sort: str = DEFAULT_SORT,
                 min_tier: str = DEFAULT_MIN_TIER,
                 level: str = "all",
                 touching_only: bool = False,
                 phase: str = "all") -> dict:
    """Gabbar's Price Levels board (Ajay 2026-08-25: "create a tab for gabbars
    price level and if anything is touching the gabbars levels").

    The bands are veerenj's hand-curated buy zones, already mirrored in
    catalysts/gabbar_levels.py for the SEPA candidate page. This board turns
    the per-ticker lookup inside out: all 66 covered names, TOUCHING first.

    * "Touching" reuses price_zones.NEAR_PCT — one scale for "at a level"
      across the whole app (the same constant Trade Flash gates on).
    * The bands are a snapshot of the author's judgment, not a computation.
      The snapshot date rides on the board note because a 3-month-old level
      on a moved stock is an opinion about a different chart.
    * Liquidity floor works like every scan tab: avg $ turnover is computed
      from the same cached daily frame the tile is drawn from.
    """
    from catalysts import gabbar_levels as GL
    from supply_demand.price_zones import NEAR_PCT
    from sepa import research

    lens = level if isinstance(level, str) and level.strip().lower() in GABBAR_LEVELS \
        else "all"
    lens = lens.strip().lower() if isinstance(lens, str) else "all"

    covered = GL.list_covered_symbols()
    snaps = research.sales_snapshot(covered)
    flash_syms = _flash_symbols()
    tiles, dropped_weak, without_level = [], 0, 0
    away_hidden = 0
    for sym in covered:
        payload = GL.get_bands(sym)
        if not payload or not payload.get("bands"):
            continue
        # Bonde read (Ajay 2026-08-25 "pradeep bonde's sales and revenus
        # quarter logic", REVISED 2026-08-27: "dont suppress show with a
        # chip"). Weak/declining sales no longer hide a hand-drawn level —
        # they wear the 📉 warn chip (same vocabulary as the topping tab)
        # and rank LAST in their state group, below even unknown-sales
        # names. The knife warning is on the tile instead of in a count.
        gate, sales = _bonde_gate(snaps.get(sym))
        if gate == "fail":
            dropped_weak += 1
        bars = bars_for(sym, days=60)
        if not bars:
            continue
        last = _f(bars[-1].get("c"))
        if not last:
            continue
        tail = bars[-50:]
        avg_turnover = sum((b.get("c") or 0) * (b.get("v") or 0) for b in tail) / max(1, len(tail))

        # Nearest band by edge distance; inside any band wins outright.
        # Under a lens, only bands of the chosen label are measured — a name
        # the author never drew that band for is dropped (and counted), not
        # shown with a fabricated distance.
        read_bands = payload["bands"] if lens == "all" else [
            b for b in payload["bands"]
            if str(b.get("label") or "").strip().lower() == lens]
        if not read_bands:
            without_level += 1
            continue
        state, best_label, best_dist = None, None, None
        for b in read_bands:
            lo, hi = _f(b.get("lo")), _f(b.get("hi"))
            if lo is None or hi is None:
                continue
            if lo <= last <= hi:
                state, best_label, best_dist = "in", b.get("label"), 0.0
                break
            edge = lo if last < lo else hi
            dist = abs(last - edge) / last * 100.0
            if best_dist is None or dist < best_dist:
                best_label, best_dist = b.get("label"), dist
        if best_dist is None:
            continue
        if state != "in":
            state = "near" if best_dist <= NEAR_PCT else "away"

        # Conservative entries (Ajay 2026-08-25: "In gabbars levels can you
        # show me conservative entries please"). The author labels each band
        # "aggressive" (shallowest) or "conservative N" (deeper discounts);
        # the nearest-band read above is label-blind, so a name camped at its
        # deep level looked identical to one at its chase level. Track the
        # nearest CONSERVATIVE band separately so the tile can say which one
        # the price is actually offering.
        def _is_cons(label) -> bool:
            return str(label or "").startswith("conservative")

        cons_state, cons_dist, cons_lo, cons_hi = None, None, None, None
        for b in payload["bands"]:
            if not _is_cons(b.get("label")):
                continue
            lo, hi = _f(b.get("lo")), _f(b.get("hi"))
            if lo is None or hi is None:
                continue
            if lo <= last <= hi:
                cons_state, cons_dist, cons_lo, cons_hi = "in", 0.0, lo, hi
                break
            edge = lo if last < lo else hi
            d = abs(last - edge) / last * 100.0
            if cons_dist is None or d < cons_dist:
                cons_dist, cons_lo, cons_hi = d, lo, hi
        # Touching-only OPT-IN (flipped 2026-08-27, "can you just show me all
        # of them there? And just rank them by whcih where one are in the
        # zones" — the full ladder, in-band first, is the default again; the
        # checkbox narrows to at-the-level names when he wants the 08-26
        # "is anything AT his levels" view).
        if touching_only is True and state == "away":
            away_hidden += 1
            continue
        # Phase lens (Ajay 2026-08-31: "I need it in all the tabs possible").
        # The board already classifies every name in/near/away against the
        # hand-drawn bands, so the lens filters a state that exists — reached =
        # inside a band, approaching = near one. Default "all" keeps the
        # historical distance ladder byte for byte.
        if phase == "reached" and state != "in":
            continue
        if phase == "approaching" and state != "near":
            continue

        if cons_dist is not None and cons_state != "in":
            cons_state = "near" if cons_dist <= NEAR_PCT else "away"
        # The +250 group boost only means something in "all" mode — under a
        # lens every measured band shares one label and the boost would be a
        # constant offset.
        at_conservative = (lens == "all" and _is_cons(best_label)
                           and state in ("in", "near"))

        bands = [{"kind": "demand", "lo": float(b["lo"]), "hi": float(b["hi"]),
                  "label": f"Gabbar · {b.get('label') or 'band'}"}
                 for b in payload["bands"]]

        above = last > max(float(b["hi"]) for b in read_bands)
        if state == "in":
            why = f"inside Gabbar's {best_label} band right now"
        elif state == "near":
            why = f"{best_dist:.1f}% from Gabbar's {best_label} band"
        else:
            side = "above" if above else "past"
            why = f"{best_dist:.0f}% {side} the nearest Gabbar band ({best_label})"

        badges = []
        icon = "🛡️" if _is_cons(best_label) else "🎯"
        if state == "in":
            badges.append({"text": f"{icon} In Gabbar band ({best_label})",
                           "tone": "good"})
        elif state == "near":
            badges.append({"text": f"{icon} {best_dist:.1f}% from {best_label}",
                           "tone": "warn"})
        if gate == "pass" and sales:
            badges.append(_sales_badge(sales))
        elif gate == "fail" and sales:
            gs = _f(sales.get("growth_yoy_pct"))
            badges.append({"text": (f"📉 Sales {sales.get('tier')} {gs:+.0f}%"
                                     if gs is not None
                                     else f"📉 Sales {sales.get('tier')}"),
                           "tone": "warn"})
        elif gate == "unknown":
            badges.append({"text": "❔ Sales data missing", "tone": "muted"})
        if sym in flash_syms:
            badges.append({"text": "⚡ Tape burst at zone", "tone": "good"})

        # Touching sorts first, then by proximity. 1000-scale keeps IN ahead
        # of every NEAR ahead of every AWAY regardless of raw distances; an
        # unknown-sales name ranks after every Bonde-passing one in its state.
        rank = {"in": 2000.0, "near": 1000.0}.get(state, 0.0) - best_dist
        # A conservative-band touch is the deeper discount — it leads its
        # state group. +250 stays inside the 1000-per-state bucket, so a
        # conservative NEAR can never outrank an aggressive IN.
        if at_conservative:
            rank += 250.0
        if gate == "unknown":
            rank -= 500.0
        elif gate == "fail":
            rank -= 800.0            # visible, chipped, and last in its group

        tiles.append({
            "symbol": sym,
            "name": _name_for(sym),
            "href": _href(sym, "supply"),
            "bars": [],
            "_bars": {"days": days},
            "bands": bands,
            "lines": [],
            "markers": [],
            "stats": [
                {"k": "Level", "v": str(best_label or "—")},
                {"k": "Dist", "v": ("in band" if state == "in" else f"{best_dist:.1f}%")},
                {"k": "Conserv.", "v": ("—" if cons_dist is None else
                                        "in band" if cons_state == "in" else
                                        f"{cons_lo:g}–{cons_hi:g} · {cons_dist:.1f}%")},
                {"k": "Avg $/day", "v": _usd_short(avg_turnover)},
            ],
            "why": why,
            "theme": _theme(sym),
            "badges": badges,
            "_score": rank,
            "_m": {**tile_metrics({"liquidity": {"avg_dollar_vol": avg_turnover},
                                   "last_close": last})},
        })

    out, meta = _finish(tiles, limit, themes_first, days, sort, min_tier)
    touching = sum(1 for t in tiles
                   if any((b.get("text") or "").startswith(("🎯", "🛡️"))
                          for b in t.get("badges") or []))
    cons_touching = sum(1 for t in tiles
                        if any((b.get("text") or "").startswith("🛡️")
                               for b in t.get("badges") or []))
    attr = GL.BAND_ATTRIBUTION
    tracked_stubs = list(getattr(GL, "TRACKED_NO_LEVELS", ()) or ())
    return {"tiles": out, **meta,
            "phase": (phase if phase in ("reached", "approaching") else "all"),
            "tracked_no_levels": tracked_stubs,
            "matched": len(tiles),
            "touching": touching,
            "conservative_touching": cons_touching,
            "weak_sales_flagged": dropped_weak,
            "level": lens,
            "level_choices": list(GABBAR_LEVELS),
            "without_level": without_level,
            "touching_only": touching_only is True,
            "away_hidden": away_hidden,
            "note": (f"Hand-curated buy zones from {attr.get('source')} "
                     f"({attr.get('author')}, {attr.get('license')}), snapshot "
                     f"{attr.get('snapshot_date')} — the author's judgment, not a "
                     f"computation, and levels this old describe the chart as it "
                     f"was then. Touching names sort first; 🛡️ marks a name at its CONSERVATIVE (deeper "
                     f"discount) band, which leads its group. Bonde sales read: "
                     f"{dropped_weak} covered name(s) wear the 📉 weak/declining "
                     f"chip and rank last — a level under a shrinking business "
                     f"is the knife, so it is flagged, not hidden."
                     + (f" Lens: {lens} — distances measure that band type only; "
                        f"{without_level} covered name(s) have no such band and "
                        f"are hidden." if lens != "all" else "")
                     + (f" Touching only: {away_hidden} covered name(s) more "
                        f"than {NEAR_PCT:g}% from every band are hidden — untick "
                        f"to see the full distance ladder."
                        if touching_only is True and away_hidden else "")
                     + (f" The author also tracks {len(tracked_stubs)} names "
                        f"with NO levels drawn yet ({', '.join(tracked_stubs[:5])}, "
                        f"…) — they sit as empty stubs in his script and cannot "
                        f"appear here until he draws them."
                        if tracked_stubs else "")),
            "generated_at": None}


# ---------------------------------------------------------------------------
# tab — ICT (took the Into Supply slot, 2026-09-03)
# ---------------------------------------------------------------------------
def ict_tiles(limit: int = LIMIT_DEFAULT, days: int = BARS_DEFAULT,
              themes_first: bool = THEMES_FIRST_DEFAULT,
              sort: str = DEFAULT_SORT,
              min_tier: str = DEFAULT_MIN_TIER,
              bias: str = "all", micro: str = "60m") -> dict:
    """ICT Strategy — daily key levels, the dormant 60-minute loop.

    Ajay 2026-09-03 (late): "create a new chart maps tab for ICT Strategy,
    replace supply tab with this new tab." Concepts from his spec + Jesse
    Rogers' video (ict/engine.py carries the URL and timestamps); every
    threshold the video does not give is an owner setting and is returned
    in `params` so the page can list it under the board.

    Reads `ict.engine.cached_or_warm` — the Mongo doc the 15-minute cron
    writes. Never scans on the request path: a stale doc answers with its
    rows and warming:true while a daemon thread refreshes it.

    Tile geometry lives in ict/board.py (pure): accumulation range + gaps +
    entry zone as bands, stop/target/key levels as lines, MANIP/MSS/IFVG as
    dated markers on the DAILY chart (each 60m bar placed by its ET date).
    """
    from ict import board as IB
    from ict import engine as IE

    want = bias if bias in ("all", "bullish", "bearish") else "all"
    tf = micro if micro in IE.MICRO_TFS else IE.MICRO_TF_DEFAULT
    data = IE.cached_or_warm(limit=LIMIT_MAX, micro_tf=tf)
    rows = list(data.get("rows") or [])
    tiles = IB.tiles_from_rows(rows, bias=want, href=_href, name_for=_name_for,
                               theme=_theme, metrics=tile_metrics)
    matched = len(tiles)
    tiles, meta = _finish(tiles, limit, themes_first, days, sort, min_tier)
    warming = bool(data.get("warming"))
    counts = {"macro_n": data.get("macro_n") or 0, "tapped_n": data.get("tapped_n") or 0,
              "micro_n": data.get("micro_n") or 0, "rows": len(rows), "matched": matched}
    if warming and not rows:
        note = "first ICT scan running — daily levels over the $1B+ universe, then the 60-minute loop on the tapped names…"
    elif warming:
        note = "showing the last scan while a fresh one runs"
    elif not rows:
        note = "no name has tapped a daily key level in the last two sessions — the 60-minute loop is dormant"
    elif not tiles and matched == 0:
        note = f"no {want} setups in the last scan"
    else:
        note = None
    return {"tiles": tiles, **meta, "note": note, "warming": warming,
            "as_of": data.get("as_of"), "generated_at": data.get("as_of"),
            "cached": bool(data.get("cached")), "stale_sec": data.get("stale_sec"),
            "truncated": bool(data.get("truncated")),
            "counts": counts, "bias": want, "micro": tf,
            "params": data.get("params") or IE.params(),
            "source": data.get("source") or IE.SOURCE,
            "disclaimer": IE.DISCLAIMER}


def board(tab: str = "vcp", limit: int = LIMIT_DEFAULT, days: int = BARS_DEFAULT,
          universe: str = "full", themes_first: bool = THEMES_FIRST_DEFAULT,
          pattern: Optional[str] = None, source: str = "pattern",
          minervini_only: bool = False, sort: str = DEFAULT_SORT,
          min_tier: str = DEFAULT_MIN_TIER, level: str = "all",
          touching_only: bool = False, phase: str = "",
          target: str = "zone", bias: str = "all", micro: str = "60m",
          min_room: Optional[float] = None) -> dict:
    """One tab's tiles. Never scans; reads caches and the pattern ledger.

    `min_room` (2026-09-05) reaches ONLY the zones and deep_demand tabs — the
    room floor on the live print (None = the house default, 0 = off). Every
    other tab ignores it and carries no room keys.

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

    if t == "earnings":
        out = earnings_tiles(limit, days)
    elif t == "zones":
        # Phase normalisation: the demand boards' default moment is "reached"
        # (their population IS the reached set), while the lens tabs below
        # default to "all" (their population is a screen the lens narrows).
        # An empty phase means "the tab's own default" so URLs from before any
        # of this behave identically on every tab.
        out = zone_tiles(limit, days, universe, themes_first, srt, tier,
                         phase=(phase or "reached"), target=target,
                         min_room=min_room)
    elif t == "supply":
        out = supply_tiles(limit, days, universe, themes_first, srt, tier)
    elif t == "ict":
        out = ict_tiles(limit, days, themes_first, srt, tier,
                        bias=bias if isinstance(bias, str) else "all",
                        micro=micro if isinstance(micro, str) else "60m")
    elif t == "topping":
        out = topping_tiles(limit, days, themes_first, srt, tier)
    elif t == "deep_demand":
        out = deep_demand_tiles(limit, days, universe, themes_first, srt, tier,
                                phase=(phase or "reached"), min_room=min_room)
    elif t == "quick_bounce":
        out = quick_bounce_tiles(limit, days, themes_first, srt, tier, min_room=min_room)
    elif t == "undervalue":
        out = undervalue_tiles(limit, days, themes_first, srt, tier,
                               phase=(phase or "all"))
    elif t == "gabbar":
        out = gabbar_tiles(limit, days, themes_first, srt, tier,
                           level=level if isinstance(level, str) else "all",
                           touching_only=touching_only is True,
                           phase=(phase or "all"))
    elif t == "zero_dte":
        out = zero_dte_tiles(limit, days)
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
    # 0DTE joins the ledger tabs here: it reads live option chains, not the
    # equity scan, so there is no share volume to sort by and no dollar-volume
    # floor to apply. Offering either control would be a switch that does
    # nothing — the same reason `winners` and `earnings` are fixed.
    _fixed = t in ("winners", "earnings", "zero_dte")
    out["sort"] = DEFAULT_SORT if _fixed else srt
    out["sorts"] = [] if _fixed else [{"key": k, "label": v}
                                              for k, v in SORTS.items()]
    # The winners tabs read a ledger and are not liquidity-filtered — saying
    # "any" there is honest; pretending a floor applied would not be.
    out["min_tier"] = "any" if _fixed else tier
    out["tiers"] = [] if _fixed else [
        {"key": "deep", "label": f"Deep · ≥${int(LIQ_DEEP_USD/1e6)}M/day"},
        {"key": "ok", "label": f"Tradeable · ≥${int(LIQ_OK_USD/1e6)}M/day"},
        {"key": "thin", "label": f"Thin · ≥${int(LIQ_THIN_USD/1e6)}M/day"},
        {"key": "any", "label": "No floor (shows illiquid names)"},
    ]
    out["tape_sorts"] = list(TAPE_SORTS)
    # A tab that states its OWN limits keeps them. The Into Supply board is a
    # caution flag, not a study board, and the generic line would have
    # overwritten the sentence that says it is not a short signal.
    out["disclaimer"] = out.get("disclaimer") or DISCLAIMER
    return out
