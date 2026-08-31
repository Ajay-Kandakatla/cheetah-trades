"""Demand-zone RE-ENTRY scan — S&P 500 names that have pulled back DOWN into a
tested demand band while the uptrend is still intact.

Ajay 2026-08-13: "update my Supply and demand page with stocks that entering
back in to demand zones … scan only S&P 500 stocks for this."

WHAT MAKES THIS DIFFERENT FROM `price_zones`
--------------------------------------------
`price_zones.py` answers "where are this ticker's bands right now?" — a
snapshot. This module answers a *transition* question: **did price come back
down INTO a demand band it had already left?** A name that has simply been
sitting inside a band for months is not "entering back in"; a name that ran
+18% above the band and has now returned to it is.

METHOD NOTE — this is a PRAGMATIC price-structure read, **not** a named book
methodology, and as of 2026-08-13 it is deliberately INDEPENDENT of the
Minervini/SEPA stack (Ajay: "The Supply demand are outside of this strategy…
Oh ignore the minervini for this please"). Every threshold below is a
CONFIGURED house value. The only borrowed number left is the stop sanity cap,
`trading.risk_rules.ABS_MAX_STOP_PCT`.
Decision-support only — NOT a buy signal and NOT financial advice.

WHY THE BANDS ARE WIDER HERE
----------------------------
The /zones page defaults (`ZONE_MERGE_PCT` 1.75, `ZONE_HALF_WIDTH_PCT` 0.6)
produce ~1%-wide lines. Measured 2026-08-13 across the S&P 500, those thin
bands made "re-entry" meaningless — 21 hits, almost all utilities, most of them
1 bar after price crossed a band 0.5% wide. That is noise, not demand. A
tradeable zone is a band you can put a stop underneath, so this module passes
wider geometry (merge 4.0%, half-width 1.75%, swing window 5) via the optional
knobs on `price_zones.compute`. Defaults elsewhere are untouched.

THE FALLING-KNIFE GUARD (replaced the Minervini trend gate, 2026-08-13)
----------------------------------------------------------------------
A pullback into support inside a DOWNtrend is a falling knife, not a demand
zone — so a guard is needed. It used to be "Minervini trend template >= 6 of
8". That gate is gone, for two reasons:

  1. Ajay is running supply/demand as a SEPARATE strategy and asked for the
     Minervini coupling out.
  2. It did not actually do the job. The template leans on long-term moving
     averages, which roll over late. On 2026-08-13 it passed CIEN at 7/8 while
     CIEN's swing lows read 424 -> 404 -> 359 -> 323, its 50-day was falling,
     and its big prints ran 7:1 to the sell side. Three of the four names on
     that day's board (CIEN, VRT, CAT) were falling knives that the template
     waved through.

The replacement is `sd_liquidity.is_falling_knife`: swing lows stepping DOWN
**and** a falling 50-day average. Both must agree, so one shakeout low inside
an uptrend does not disqualify a zone. Measured in the 2026-08-13 walk-forward
backtest (`sd_backtest.py`), this filter improved expectancy in every single
target/hold configuration tested, and the knives-only cohort was the worst
performer in all of them.

THE BROKEN-BAND GUARD (2026-08-17)
---------------------------------
A band price CLOSED below and then bounced back into is not support, and a
re-entry into it is not a buy. On the S&P 500 board the day it was added, 8 of
17 rows were broken bands — SWKS was reading "back in demand" 18% under the band
it had supposedly returned to. See `reentry_read`, and
docs/supply_demand/broken_band_guard.md for the NBIX case that forced it.

Spec + measured tuning notes: docs/supply_demand/demand_reentry_methodology.md
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd

from sepa import prices, universe as universe_mod, company_names
from . import sd_liquidity as liq
from . import price_zones

log = logging.getLogger("supply_demand.demand_reentry")

# ── Zone geometry (house values — see module docstring for the measurement) ────
SWING_WINDOW    = 5
MERGE_PCT       = 4.0
HALF_WIDTH_PCT  = 1.75

# ── Re-entry qualification (all CONFIGURED house values) ──────────────────────
REENTRY_LOOKBACK_BARS = 40    # window in which price must have been above the band
MIN_RISE_ABOVE_PCT    = 5.0   # it must have traded >= this % above the band top
MIN_TOUCHES           = 2     # the band must have been tested at least twice
MIN_ZONE_STRENGTH     = 40.0  # 0-100 price_zones strength (tests + volume)
# Falling-knife guard. NOT Minervini — see the module docstring. Swing lows
# stepping down AND a falling 50-day average.
STRUCTURE_SWING_WINDOW = 5
MA_SLOPE_LOOKBACK      = 10

# Stop sits this far under the band floor (room for a wick through support).
STOP_BUFFER_PCT = 1.5

# How far back a proposed stop is checked against the bars that already traded.
# Ajay 2026-08-17, on NBIX: the board offered a $150.25 stop on the same morning
# the stock printed a $148.78 low. A stop the market has already run is not a
# stop; the plan it belongs to was stopped out before it was quoted.
#
# Two trading weeks is a CONFIGURED house value, and the window matters in both
# directions: a stop taken out three months ago against a band that has been
# rebuilt and retested since is stale news, while one taken out in the last few
# sessions describes the structure being traded right now. Unlike the broken-band
# guard this only WARNS — the level is a fact about the plan, not about the zone,
# and Ajay may still want the name on the board with the caveat attached.
STOP_HIT_LOOKBACK_BARS = 10

MIN_BARS = 220                # ~1y of bars for the structure read

# ── Liquidity tiers (avg 50-day dollar volume) ───────────────────────────────
# Ajay 2026-08-13: "if there are no order flow or book map or volume no point
# buying". A great R:R on a name you cannot get filled in is not a trade — and
# on thin tape the spread alone can exceed the edge. House values.
LIQ_DEEP_USD  = 50_000_000.0   # institutional-grade tape
LIQ_OK_USD    = 10_000_000.0   # comfortably tradeable in retail size
LIQ_THIN_USD  =  2_000_000.0   # tradeable only in small size, wider spreads
# Below LIQ_THIN_USD the spread and slippage swamp a 2R edge -> not tradeable.

# Dark-pool + retail detail costs a TAPE and an NBBO fetch per name, so only
# the top rows by R:R get it — those are the only ones worth acting on.
VENUE_DETAIL_TOP_N = 15

# Hard wall-clock budget for that enrichment, and how many names to fetch at
# once. Both added 2026-08-14 after a live 524: adding the retail NBBO pull
# doubled the per-row cost and the cold sp1500 request ran past 600s, well
# beyond Cloudflare's ~100s gateway timeout. The board itself scans in ~7s —
# it was never the scan that was slow.
#
# Enrichment is now best-effort: whatever finishes inside the budget is
# attached, the rest of the rows simply have no venue/retail detail and the UI
# already renders that as "—" with a tooltip saying no tape was pulled. A
# board that loads without the extra columns beats a board that times out.
VENUE_BUDGET_SEC = 25.0
# Grace past the budget before as_completed gives up entirely. A knob so the
# hung-future regression test does not have to wait five real seconds.
_VENUE_SLACK_SEC = 5.0
VENUE_WORKERS = 6

# NBBO is only needed to SIGN retail prints, not to reconstruct the session, so
# the quote pull is capped well below the classifier's default. A partial NBBO
# still signs the prints it covers and `retail.identify` reports coverage.
VENUE_QUOTE_PAGES = 4

# How far ABOVE price a demand band may sit and still be the entry band. Covers
# price resting a hair under a floor it has been trading in (VRT, 4 cents);
# anything further means price has broken below the band, not approached it.
ENTRY_ABOVE_TOL_PCT = 1.5

# ── "Approaching" (Ajay 2026-08-31) ──────────────────────────────────────────
# "What I am seeing in Demand zones and Deep Demand zones are already reached
#  Demand zones and bouncing.. I need the ones that are about to reach and
#  catch them..."
#
# The reached board answers "price is back INSIDE a tested band". This asks the
# question one step earlier: price is still ABOVE the band, close, and FALLING
# toward it. Both halves matter — distance alone cannot tell an approach from a
# departure, because a name 3% above its band that bounced yesterday is LEAVING.
# The drift test is what separates them.
APPROACH_NEAR_PCT = 5.0        # band top within this % below price
APPROACH_DRIFT_BARS = 5        # sessions the direction is measured over
APPROACH_MIN_DRIFT_PCT = 0.5   # must have FALLEN at least this % over those bars

# Order-block approaches (Ajay 2026-08-31: "find stocks closer to orderblocks
# .. Approaching order block vs Approaching Demand Zone"). Same near/drift
# tests as the zone approach; the LEVEL is different — an SMC order block (the
# last down candle before a >=1.2 ATR up-displacement, daily bars) instead of
# a swing-cluster band. CONVENTION, like everything SMC: no canonical text.
OB_APPROACH_MAX_AGE_BARS = 90  # daily bars; older blocks are stale structure
# "In the order block" (Ajay 2026-08-31: "hit the 'In the orderblock' to see
# all the stocks"): the arrival must be RECENT — the first touch began within
# this many bars. A name that has sat in/under its block for weeks is not
# "in the order block", it is a block that failed to bounce. CONVENTION.
OB_FIRST_TOUCH_BARS = 5

# How far BELOW price a demand band may sit and still be an ENTRY rather than
# just distant support.
#
# Ajay 2026-08-16, looking at the ELVN Setup tab: "For the SEPA list why are the
# zones all messed up?" ELVN was trading at $58.82 and the page drew
# BUY $24.89-$25.29 with a STOP at $24.52 — a buy zone 57% below spot. The plan
# was internally inconsistent: entry_low/high came from the band while
# entry_ref, risk_pct and rr were all computed from SPOT, giving risk_pct 58.3%
# and rr 0.07 against a target ($61.23) taken from resistance just above spot.
#
# The tolerance is the house max stop (`trading.risk_rules.ABS_MAX_STOP_PCT`,
# the p.299/p.301 cap) rather than a new invented number: if getting to the band
# costs more than the most you would ever risk on a trade, it is not an entry
# you can place today. It is support, and the band still draws as DEMAND —
# only the BUY/STOP lines go away.
#
# This cannot affect the Back in Demand board: `is_reentry` requires price to be
# INSIDE the band, which is distance zero.
def _entry_below_tol_pct() -> float:
    try:
        from trading.risk_rules import ABS_MAX_STOP_PCT
        return float(ABS_MAX_STOP_PCT)
    except Exception:
        return 10.0

# Relative volume (today / 50-day average) bands.
RVOL_SURGE  = 2.0
RVOL_ACTIVE = 1.2
RVOL_QUIET  = 0.6

# Regular session length, and the earliest fraction at which a projection is
# worth showing. Before this the sample is too small — opening prints alone
# can imply a 5x day.
SESSION_MINUTES = 390          # 09:30-16:00 ET
RVOL_MIN_FRACTION = 0.08       # ~30 minutes in


def _session_fraction(now_et=None) -> float:
    """How much of the regular session has elapsed, 0..1.

    Raw RVOL is a trap mid-session. Measured 2026-08-14 at 10:50 ET (80 of 390
    minutes), every name on the board read "dead" at RVOL 0.01-0.10 — not
    because volume was absent but because the day was 20% old. Worse, the
    frames were INCONSISTENT: some names' last bar was the prior COMPLETE
    session, others' was today's partial one, so the column compared different
    things across rows. Projecting to a full session makes them comparable.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now = now_et or datetime.now(ZoneInfo("America/New_York"))
    mins = (now.hour - 9) * 60 + now.minute - 30
    if mins <= 0:
        return 0.0
    return min(1.0, mins / SESSION_MINUTES)

_CACHE_TTL_SEC = 3 * 60 * 60
_cache: dict = {}

# Universes currently being computed in the background, so a burst of page
# loads kicks off one job rather than one per request.
_warming: set = set()
_warm_lock = __import__("threading").Lock()

# ── Live scan progress ────────────────────────────────────────────────────────
# Ajay 2026-08-17, looking at the Back in Demand tab mid-scan: *"I am looking at
# this and its hard to tell if its scanning or now"*. The page said
# "0 in demand · 0/0 scanned" for three minutes — the counters only exist in the
# FINAL payload, so until the scan finished there was nothing to show and the
# static "scanning in the background…" line was indistinguishable from a hang.
#
# The Chart Maps progress panel could not be reused: that one watches
# `/sepa/scan/stream`, a DIFFERENT scan. This board runs its own pass, so it
# needs its own counter.
#
# Deliberately a plain dict of immutable snapshots rather than a mutated one:
# the writer builds a fresh dict and swaps the reference, which is atomic in
# CPython, so a reader can never observe a half-updated record. No lock is taken
# on the read path — a progress read must never be able to block a scan.
_progress: dict = {}

PROGRESS_PHASES = ("universe", "scanning", "enriching", "done", "failed")


def _publish_progress(ukey: str, phase: str, **fields) -> None:
    """Swap in a fresh progress snapshot for `ukey`. Never raises."""
    try:
        prev = _progress.get(ukey) or {}
        snap = {**prev, "universe_key": ukey, "phase": phase,
                "updated_at": time.time(), **fields}
        _progress[ukey] = snap
    except Exception:                                    # pragma: no cover
        pass


def progress_for(universe: str) -> dict:
    """What the running scan for `universe` is doing right now. PURE-ish read.

    Always answers, even when nothing is running — `phase: "idle"` — so the page
    has one shape to render instead of branching on presence.

    `eta_sec` is projected from the elapsed rate rather than a fixed per-symbol
    cost: a warm price cache runs an order of magnitude faster than a cold one,
    so any constant here would be wrong on one of the two paths.
    """
    ukey = _universe_key(universe)
    snap = _progress.get(ukey)
    idle = {"universe_key": ukey, "phase": "idle", "running": False,
            "current": 0, "total": 0, "hits": 0, "symbol": None,
            "elapsed_sec": None, "eta_sec": None, "pct": None}
    if not snap:
        return idle

    # Defensive on the READ side too, not just the write side. This runs on the
    # request path against a dict another thread is writing, so a bad field must
    # degrade to "no number" rather than 500 the endpoint the user is staring at
    # precisely because they cannot tell whether anything is happening.
    def _n(key, default=0):
        v = snap.get(key)
        try:
            return type(default)(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    cur, total = _n("current"), _n("total")
    started = _n("started_at", 0.0) or None
    elapsed = round(time.time() - started, 1) if started else None
    eta = None
    if elapsed and cur > 0 and total > cur:
        eta = round(elapsed / cur * (total - cur), 1)
    return {**snap,
            "current": cur, "total": total, "hits": _n("hits"),
            "running": snap.get("phase") in ("universe", "scanning", "enriching"),
            "elapsed_sec": elapsed,
            "eta_sec": eta,
            "pct": round(100.0 * cur / total, 1) if total else None}


def cached_or_warm(universe: str, limit: Optional[int] = None,
                   min_rr: Optional[float] = None) -> dict:
    """Serve the cache, or start a background compute and say so — never block.

    A cold sp1500 pass is ~3 MINUTES (1,500 price frames, then a tape + NBBO
    fetch per enriched row). Cloudflare cuts the connection at ~100s, which is
    the 524 Ajay hit on 2026-08-14 after sp1500 became the default landing tab.
    No amount of tuning makes a 3-minute job survive a 100-second gateway, so
    the request path stops trying: it returns what it has, kicks the work into
    a thread, and the page polls. The 16:55 cron warm means this is usually a
    cache hit anyway.
    """
    import threading
    ukey = _universe_key(universe)
    c = _cache.get(ukey)
    if c and (time.time() - c["ts"]) < _CACHE_TTL_SEC:
        return {**_apply_limit(_apply_rr_floor(c["data"], min_rr), limit),
                "cached": True, "warming": False}

    with _warm_lock:
        already = ukey in _warming
        if not already:
            _warming.add(ukey)

    if not already:
        def _work():
            try:
                scan(force=True, limit=None, universe=ukey)
            except Exception as exc:
                log.warning("demand-reentry: background warm failed for %s: %s", ukey, exc)
                # Without this the bar freezes wherever it died and the page
                # says "scanning" forever — the exact failure Ajay reported,
                # reintroduced by the thing meant to fix it.
                _publish_progress(ukey, "failed", symbol=None, error=str(exc)[:200])
            finally:
                with _warm_lock:
                    _warming.discard(ukey)
        threading.Thread(target=_work, name=f"warm-{ukey}", daemon=True).start()

    label = UNIVERSES.get(ukey, (ukey,))[0]
    return {"rows": [], "n": 0, "supply_rows": [], "supply_n": 0,
            "deep_rows": [], "deep_n": 0,
            "approaching_rows": [], "approaching_n": 0,
            "approaching_ob_rows": [], "approaching_ob_n": 0,
            "in_ob_rows": [], "in_ob_n": 0,
            "scanned": 0, "universe": 0,
            "universe_key": ukey, "universe_label": label,
            "universe_note": f"{label} — first scan running",
            "universe_is_sp500": True, "universe_stale_days": None,
            "universe_source": None, "universe_choices":
                [{"key": k, "label": v[0]} for k, v in UNIVERSES.items()],
            "errors": 0, "took_sec": 0, "cached": False, "warming": True,
            "min_rr": (MIN_RR_DEFAULT if min_rr is None else float(min_rr)),
            "min_rr_default": MIN_RR_DEFAULT, "dropped_low_rr": 0,
            # Carried on the warming payload as well as the dedicated endpoint,
            # so a page that only polls the board still gets a moving number.
            "progress": progress_for(ukey),
            "as_of": datetime.now(timezone.utc).isoformat(),
            "disclaimer": DISCLAIMER}


# ── The reward:risk floor ────────────────────────────────────────────────────
# Ajay 2026-08-17, after three "buyers in control" candidates were measured and
# all three failed: he picked the R:R floor instead.
#
# WHY 1.0, AND WHY IT IS **NOT** THE BACKTEST'S BEST CELL
# ------------------------------------------------------
# Measured on 737 walk-forward observations (300 S&P names by dollar volume,
# decision days 2025-07-08 → 2026-08-14 — 13.5 months, NOT the 5y the harness
# reports, because load_prices serves a ~500-bar cache):
#
#   floor   raced  win%   exp%    exSPY%   medRR   wins resolved on the ENTRY bar
#   none      680  53.4   +0.02   -0.219    0.94   131  (36% of all wins!)
#   >=1.00    326  39.9   +0.17   -0.101    1.87    27
#   >=1.25    257  37.4   +0.29   -0.003    2.18    16
#   >=1.50    215  32.6   +0.15   -0.247    2.35    12
#   >=2.50     95  31.6   +0.62   +0.034    3.26     3
#
# 1.25 is the best exSPY cell. It is deliberately NOT the default, because
# **exSPY is not monotone** — it falls at 0.75, 1.50, 2.00 and 3.00, four of
# eight steps going the wrong way. Picking the peak of a nine-cell sweep is the
# same in-sample fitting that disqualified the three buyers-in-control
# candidates, and it would be dishonest to apply a stricter standard to those
# than to this.
#
# What IS monotone is the column that describes the actual defect: wins that
# resolve on the ENTRY bar, 131 → 59 → 37 → 27 → 16 → 12 → 9 → 8 → 3 → 2. Those
# are plans whose "target" already sat inside the entry day's range — median
# planned R:R **0.45**. Strip them from the unfiltered board and the whole rule
# reads exp -0.29%, exSPY -0.586%. The board's headline +0.02% is carried by
# 0.45R hops.
#
# So the floor is justified by TRADE CONSTRUCTION, not by a fitted optimum:
# a plan that risks more than its first objective pays is not a trade, whatever
# a 13.5-month sample says. 1.0 is the line that claim implies. It is a house
# value, it is configurable, and `min_rr=0` turns it off.
#
# HONEST LIMIT: no floor makes this board beat SPY on this sample. The
# unfiltered rule is exSPY -0.219% and the best cell reaches -0.003%. The floor
# removes bad trade CONSTRUCTION; it does not turn the rule into an edge.
MIN_RR_DEFAULT = 1.0

# Below this, the plan's reward is gone before its own entry band ends: filling
# at `entry_high` buys less than 1R of upside. Same number as the floor on
# purpose — the claim is "this stops being a trade", not a second opinion about
# how good a trade is.
THIN_BAND_RR = 1.0


def meets_rr_floor(plan: Optional[dict], min_rr: float = MIN_RR_DEFAULT) -> bool:
    """Does this plan's reward:risk clear the floor? PURE.

    An UNCOMPUTABLE R:R fails a real floor — same rule as the chart-maps
    liquidity tier. `rr` is None when no supply band sits above the entry band,
    so there is no first objective to measure against; the backtest skips those
    rows entirely, which means there is no evidence they work either way.
    Letting them through would make "the one we could not measure" the one that
    shows up unfiltered.

    A floor of 0 (or less) is OFF and passes everything, including None.
    """
    if not min_rr or min_rr <= 0:
        return True
    rr = (plan or {}).get("rr")
    return isinstance(rr, (int, float)) and not isinstance(rr, bool) and rr >= min_rr


def _apply_rr_floor(data: dict, min_rr: Optional[float]) -> dict:
    """Filter a scan payload by the R:R floor, reporting what it removed.

    Applied at READ time, never inside `scan`, so the 3-hour cache holds ONE row
    set per universe instead of one per floor value — and so changing the floor
    on the page is instant rather than a fresh 3-minute pass.
    """
    floor = MIN_RR_DEFAULT if min_rr is None else float(min_rr)
    rows = data.get("rows") or []
    if floor <= 0:
        return {**data, "min_rr": 0.0, "dropped_low_rr": 0,
                "min_rr_default": MIN_RR_DEFAULT}
    kept = [r for r in rows if meets_rr_floor(r.get("plan"), floor)]
    return {**data, "rows": kept, "n": len(kept),
            "min_rr": floor,
            "min_rr_default": MIN_RR_DEFAULT,
            "dropped_low_rr": len(rows) - len(kept)}


def _apply_limit(data: dict, limit: Optional[int]) -> dict:
    if not limit:
        return data
    return {**data, "rows": data.get("rows", [])[:int(limit)]}

DISCLAIMER = (
    "Demand-zone re-entry is a configured, pragmatic price-structure read (NOT a "
    "book method) of names that pulled back into a tested support band while the "
    "trend held. Decision-support only — not a buy signal and not advice."
)


def zone_geom() -> dict:
    """The wider geometry this module hands to `price_zones.compute`."""
    return {"swing_window": SWING_WINDOW, "merge_pct": MERGE_PCT,
            "half_width_pct": HALF_WIDTH_PCT}


# ── Pure helpers (unit-tested directly) ───────────────────────────────────────
def reentry_read(closes: list[float], zone_hi: float, zone_lo: float,
                 last_price: float,
                 lookback: int = REENTRY_LOOKBACK_BARS,
                 min_rise_pct: float = MIN_RISE_ABOVE_PCT) -> dict:
    """Did price leave this band above and come back into it? PURE.

    Returns is_reentry plus the supporting evidence: how far above the band top
    it got (`fell_from_pct`), how many bars ago it was last above
    (`bars_since_above`), and whether the band has since been BROKEN.

    Requires price to be INSIDE the band now — a name below the floor has
    broken support, which is the opposite of this signal.

    THE BROKEN-BAND GUARD (Ajay 2026-08-17, on NBIX)
    -----------------------------------------------
    That last sentence was the stated intent and the code did not implement it.
    `in_band` tested only the LAST price, so a name that fell through the floor,
    CLOSED below it, and bounced back the next day read as a clean re-entry::

        2026-08-12  close 156.49                 in band
        2026-08-13  close 150.82   <- below the 152.54 floor
        2026-08-14  close 152.72                 back inside

    The board showed "back in demand · support is right here · entry favorable"
    and offered Buy $152.54-155.30 with a $150.25 stop — a stop the market had
    already traded through that same morning (low $148.78).

    A close beneath the floor is the market rejecting that support. Bouncing
    back above it the next session does not un-break it; it makes the band a
    LEVEL price is fighting over, not a floor to lean on. So the break is
    reported and `is_reentry` is refused.

    Only CLOSES count, deliberately. Intraday wicks through a band are how
    demand zones get tested in the first place — failing on a wick would reject
    the healthy case this signal exists to find.
    """
    out = {"is_reentry": False, "fell_from_pct": None,
           "bars_since_above": None, "in_band": False,
           "broke_below": False, "bars_since_break": None,
           "lowest_close_pct_below": None}
    if not closes or not zone_hi or not zone_lo or zone_hi <= zone_lo:
        return out
    out["in_band"] = bool(zone_lo <= last_price <= zone_hi)
    if not out["in_band"]:
        return out

    window = closes[-int(lookback):] if lookback else closes
    if not window:
        return out
    peak = max(window)
    rise = (peak / zone_hi - 1.0) * 100.0
    out["fell_from_pct"] = round(rise, 1)

    above_idx = [i for i, c in enumerate(window) if c > zone_hi]
    if above_idx:
        out["bars_since_above"] = int(len(window) - 1 - above_idx[-1])

    # Has any bar CLOSED beneath the floor since price was last above the band?
    # Scoped to after the last visit above on purpose: a close below the floor
    # from before the run-up is old structure, already priced in by the fact
    # that price then rose 5%+ through the whole band.
    start = (above_idx[-1] + 1) if above_idx else 0
    below = [(i, c) for i, c in enumerate(window[start:], start) if c < zone_lo]
    if below:
        out["broke_below"] = True
        out["bars_since_break"] = int(len(window) - 1 - below[-1][0])
        worst = min(c for _i, c in below)
        out["lowest_close_pct_below"] = round((1.0 - worst / zone_lo) * 100.0, 2)

    out["is_reentry"] = bool(rise >= min_rise_pct and above_idx
                             and not out["broke_below"])
    return out


def trade_plan(last_price: float, entry_zone: Optional[dict],
               resistance, stop_buffer_pct: float = STOP_BUFFER_PCT,
               recent_lows: Optional[list[float]] = None) -> Optional[dict]:
    """Entry / stop / target for a demand-zone play. PURE.

    entry area = the demand band itself (buy into support, not through it)
    stop       = `stop_buffer_pct` under the band floor — the level that says
                 "demand failed", so the reason for the trade is gone
    target     = the LOW of the first supply band ABOVE THE ENTRY BAND'S TOP:
                 the first place sellers are known to be waiting, not a
                 hoped-for extension.

                 Measured against the band top, NOT against spot (fixed
                 2026-08-13). `price_zones.nearest_resistance` means "first
                 band above the current price", and when price sits just under
                 its own entry band that band IS the nearest thing above —
                 so VRT at $287.07 got a $287.11 "target", i.e. its own floor,
                 for a 0.01R plan. Locked by
                 `test_target_is_never_inside_or_below_the_entry_band`.

    `risk_exceeds_max` flags a stop wider than the house/book hard cap
    (`trading.risk_rules.ABS_MAX_STOP_PCT`, the p.299/p.301 cap) — such a plan
    is not sized down here, it is flagged so the UI can say "too wide".

    `stop_recently_hit` flags a stop the market has ALREADY run inside
    `STOP_HIT_LOOKBACK_BARS` (Ajay 2026-08-17, on NBIX: stop $150.25 quoted the
    same session the stock printed a $148.78 low). Unlike the zone break this
    only annotates the plan — pass `recent_lows` (daily LOWS, oldest first,
    including today's) to enable it. With no lows the field is **None**, not
    False: "not checked" and "checked, clean" are different claims and the UI
    must not render the first as the second.
    """
    if not last_price or not entry_zone:
        return None
    lo = entry_zone.get("lo")
    hi = entry_zone.get("hi")
    if not lo or not hi or hi <= lo:
        return None

    stop = round(lo * (1.0 - stop_buffer_pct / 100.0), 2)
    risk_pct = round((last_price - stop) / last_price * 100.0, 1) if last_price else None

    # `resistance` accepts a single band (legacy) or the full supply-zone list.
    # Either way the target must clear the ENTRY BAND's top, not merely spot.
    cands = resistance if isinstance(resistance, list) else ([resistance] if resistance else [])
    above = [z for z in cands
             if z and z.get("lo") and float(z["lo"]) > max(hi, last_price)]
    target = None
    reward_pct = None
    if above:
        target = round(float(min(above, key=lambda z: z["lo"])["lo"]), 2)
        reward_pct = round((target - last_price) / last_price * 100.0, 1)

    rr = None
    if target is not None and last_price > stop:
        rr = round((target - last_price) / (last_price - stop), 2)

    # R:R at the WORST fill the plan permits — the top of the entry band.
    #
    # `rr` above is measured at `entry_ref` (= spot), but the UI does not tell
    # Ajay to buy at spot, it tells him to buy a BAND ("Buy $16.92-$17.41").
    # Those are different trades, and on 2026-08-31 they disagreed on 41 of 96
    # live rows: QBTS advertised 1.34R at spot and paid 0.01R at the top of its
    # own entry band, because the first objective sat one cent above it.
    #
    # This is the VRT/2026-08-13 defect wearing a different hat. That fix made
    # the target clear the band top (`lo > max(hi, last_price)`); it did not
    # require it to clear by anything worth trading, so an adjacent band still
    # produces a plan whose reward is spent before the entry range ends.
    #
    # Reported, not enforced: the R:R floor still gates on `rr` so the board
    # Ajay reads today does not silently lose 43% of its rows. `thin_across_band`
    # is the honest annotation that lets the card say which half of the band is
    # actually worth filling.
    rr_at_entry_high = None
    if target is not None and hi > stop:
        rr_at_entry_high = round((target - hi) / (hi - stop), 2)

    try:
        from trading.risk_rules import ABS_MAX_STOP_PCT as _MAX
    except Exception:
        _MAX = 10.0

    # Has the market already traded through this stop? LOWS, not closes: a stop
    # is an intraday order, so a wick that reaches it fills it. This is the exact
    # mirror image of the broken-band rule above, which ignores wicks on purpose
    # — the two questions are different. "Did support fail?" is answered by where
    # buyers finished the day. "Would I still be in this trade?" is answered by
    # the worst price that printed.
    hit, bars_since_hit, worst_below = None, None, None
    if recent_lows is not None:
        lows = [float(x) for x in recent_lows[-int(STOP_HIT_LOOKBACK_BARS):]
                if x is not None and float(x) == float(x)]
        idx = [i for i, low in enumerate(lows) if low < stop]
        hit = bool(idx)
        if idx:
            bars_since_hit = int(len(lows) - 1 - idx[-1])
            worst = min(lows[i] for i in idx)
            worst_below = round((1.0 - worst / stop) * 100.0, 2)

    return {
        "entry_low": round(float(lo), 2),
        "entry_high": round(float(hi), 2),
        "entry_ref": round(float(last_price), 2),
        "stop": stop,
        "risk_pct": risk_pct,
        "target": target,
        "reward_pct": reward_pct,
        "rr": rr,
        # R:R if filled at `entry_high` instead of `entry_ref`. None when there
        # is no target to measure against — "not computable" is not "fine".
        "rr_at_entry_high": rr_at_entry_high,
        "thin_across_band": bool(rr_at_entry_high is not None
                                 and rr_at_entry_high < THIN_BAND_RR),
        "thin_band_rr": THIN_BAND_RR,
        "risk_exceeds_max": bool(risk_pct is not None and risk_pct > _MAX),
        "max_stop_pct": _MAX,
        # None = not checked (no lows passed). False = checked and clean.
        "stop_recently_hit": hit,
        "bars_since_stop_hit": bars_since_hit,
        "lowest_low_pct_below_stop": worst_below,
        "stop_hit_lookback_bars": STOP_HIT_LOOKBACK_BARS,
    }


def approaching_read(rec: dict, closes: Optional[list] = None,
                     near_pct: float = APPROACH_NEAR_PCT,
                     drift_bars: int = APPROACH_DRIFT_BARS,
                     min_drift_pct: float = APPROACH_MIN_DRIFT_PCT) -> Optional[dict]:
    """Is this scan record falling TOWARD its tested demand band? PURE.

    Qualifies when ALL of:
      * price is strictly ABOVE the entry band's top (inside is the reached
        board's territory; below is a breakdown)
      * the band top is within `near_pct` below price
      * price has FALLEN at least `min_drift_pct` over the last `drift_bars`
        sessions — the half that distinguishes an approach from a departure.
        Without it a name that bounced off this band YESTERDAY and is rising
        away would show as "about to reach" at the same 3% distance.
      * the band passes the SAME quality bar as the reached board
        (MIN_TOUCHES / MIN_ZONE_STRENGTH) and the falling-knife guard passes —
        an approach board with a weaker standard than the arrival board would
        just be a knife catalogue.

    `closes` is the recent close series (oldest first). With no series the
    drift cannot be measured and the answer is None — "could not tell" must
    not render as "approaching".
    """
    ez = rec.get("entry_zone")
    last = rec.get("last_price")
    if not ez or last is None or not rec.get("trend_ok"):
        return None
    hi, lo = ez.get("hi"), ez.get("lo")
    if hi is None or lo is None or last <= hi:
        return None                        # inside or below: not an approach
    if (ez.get("touches") or 0) < MIN_TOUCHES:
        return None
    if (ez.get("strength") or 0) < MIN_ZONE_STRENGTH:
        return None
    dist_pct = (last - hi) / last * 100.0
    if dist_pct > near_pct:
        return None
    if not closes or len(closes) <= drift_bars:
        return None
    try:
        ref = float(closes[-(drift_bars + 1)])
        drift_pct = (float(closes[-1]) - ref) / ref * 100.0
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    if drift_pct > -float(min_drift_pct):
        return None                        # flat or rising = departing
    return {
        "state": "approaching",
        "dist_pct": round(dist_pct, 2),
        "drift_pct": round(drift_pct, 2),
        "drift_bars": int(drift_bars),
        "band": {"lo": lo, "hi": hi,
                 "touches": ez.get("touches"), "strength": ez.get("strength")},
    }


def approaching_ob_read(rec: dict, df, closes: Optional[list] = None,
                        near_pct: float = APPROACH_NEAR_PCT,
                        drift_bars: int = APPROACH_DRIFT_BARS,
                        min_drift_pct: float = APPROACH_MIN_DRIFT_PCT,
                        max_age_bars: int = OB_APPROACH_MAX_AGE_BARS) -> Optional[dict]:
    """Is price falling toward a FRESH bullish order block below it? PURE.

    The zone approach asks about a swing-cluster band; this asks the SMC
    question — the last down candle before an institutional-sized impulse.
    Same near/drift/knife standards, and two of its own:

      * FRESH only: no bar's low has re-entered the block since it formed
        (checked from two bars after the block, so the displacement bar
        itself does not count as a visit). A block price already traded back
        through is spent — listing it as "about to be reached" would describe
        a first touch that already happened.
      * AGE-capped at `max_age_bars` daily bars — CONVENTION; a months-old
        block is stale structure wearing a fresh label.

    The trade geometry comes from patterns.trade_levels on the block itself
    (entry at the top, ATR-buffered stop under the bottom), with the nearest
    overhead band as target 1 when one exists. `cited` is False everywhere —
    no canonical SMC text (see docs/supply_demand/timeframes_orb_fvg.md).
    """
    last = rec.get("last_price")
    if df is None or last is None or not rec.get("trend_ok"):
        return None
    if not closes or len(closes) <= drift_bars:
        return None
    try:
        ref = float(closes[-(drift_bars + 1)])
        drift_pct = (float(closes[-1]) - ref) / ref * 100.0
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    if drift_pct > -float(min_drift_pct):
        return None                        # flat or rising = departing

    try:
        from supply_demand import smc as smc_mod
        blocks = smc_mod.order_blocks(df, direction="bullish",
                                      lookback=max_age_bars + 5)
        lows = df["low"].to_numpy(dtype=float)
    except Exception:
        return None

    best = None
    for b in blocks:
        if b.get("bars_ago", 10 ** 9) > max_age_bars:
            continue
        hi = b.get("hi")
        if hi is None or last <= hi:
            continue                       # inside or below: not an approach
        start = int(b["idx"]) + 2          # skip the displacement bar
        if start < len(lows) and float(lows[start:].min()) <= float(hi):
            continue                       # already mitigated — not fresh
        if best is None or hi > best["hi"]:
            best = b
    if best is None:
        return None

    dist_pct = (last - best["hi"]) / last * 100.0
    if dist_pct > near_pct:
        return None

    try:
        from supply_demand import patterns as pat_mod
        trade = pat_mod.trade_levels(best, last, pat_mod.atr(df),
                                     opposing=rec.get("nearest_resistance"))
    except Exception:
        trade = None

    return {
        "state": "approaching_ob",
        "dist_pct": round(dist_pct, 2),
        "drift_pct": round(drift_pct, 2),
        "drift_bars": int(drift_bars),
        "block": {"lo": round(best["lo"], 4), "hi": round(best["hi"], 4),
                  "bars_ago": best.get("bars_ago"),
                  "displacement_atr": best.get("displacement_atr")},
        "trade": trade,
        "cited": False,
    }


def in_ob_read(rec: dict, df,
               max_age_bars: int = OB_APPROACH_MAX_AGE_BARS,
               first_touch_bars: int = OB_FIRST_TOUCH_BARS) -> Optional[dict]:
    """Is price INSIDE a bullish order block on its FIRST touch? PURE.

    The reached-side mate of `approaching_ob_read` — same block detector, the
    moment after arrival instead of the moment before. Qualifies when:

      * price sits inside the block (lo <= last <= hi),
      * the block is young enough (`max_age_bars`),
      * the visit is FRESH: the first bar whose low entered the block is
        within the last `first_touch_bars` bars. A name that has camped in or
        under its block for weeks is not "in the order block" — it is a block
        that already failed to produce the bounce this board exists to catch,
      * no bar has CLOSED below the block floor since the visit began — a
        close through the floor is the block failing, not being tested,
      * the falling-knife guard passes.

    Trade geometry from patterns.trade_levels on the block (long from support
    while the floor holds). CONVENTION, cited: false, like everything SMC.
    """
    last = rec.get("last_price")
    if df is None or last is None or not rec.get("trend_ok"):
        return None
    try:
        from supply_demand import smc as smc_mod
        blocks = smc_mod.order_blocks(df, direction="bullish",
                                      lookback=max_age_bars + 5)
        lows = df["low"].to_numpy(dtype=float)
        closes_arr = df["close"].to_numpy(dtype=float)
    except Exception:
        return None
    n = len(lows)

    best = None
    for b in blocks:
        if b.get("bars_ago", 10 ** 9) > max_age_bars:
            continue
        lo_b, hi_b = b.get("lo"), b.get("hi")
        if lo_b is None or hi_b is None:
            continue
        if not (float(lo_b) <= float(last) <= float(hi_b)):
            continue
        start = int(b["idx"]) + 2              # skip the displacement bar
        if start >= n:
            continue
        touched = [j for j in range(start, n) if lows[j] <= float(hi_b)]
        if not touched:
            continue                            # inside on stale data? skip
        first = touched[0]
        if (n - 1 - first) >= first_touch_bars:
            continue                            # camped, not arriving
        if any(closes_arr[j] < float(lo_b) for j in range(first, n)):
            continue                            # closed through the floor
        if best is None or float(hi_b) > best["hi"]:
            best = b
    if best is None:
        return None

    try:
        from supply_demand import patterns as pat_mod
        trade = pat_mod.trade_levels(best, last, pat_mod.atr(df),
                                     opposing=rec.get("nearest_resistance"))
    except Exception:
        trade = None

    return {
        "state": "in_ob",
        "block": {"lo": round(best["lo"], 4), "hi": round(best["hi"], 4),
                  "bars_ago": best.get("bars_ago"),
                  "displacement_atr": best.get("displacement_atr")},
        "depth_pct": round((best["hi"] - float(last))
                           / max(best["hi"] - best["lo"], 1e-9) * 100.0, 1),
        "trade": trade,
        "cited": False,
    }


def _pick_entry_zone(last_price: float, demand_zones: list[dict]) -> Optional[dict]:
    """The band price is INSIDE, else the band NEAREST to price.

    Nearest by distance, not "nearest strictly below" — that older rule had a
    cliff edge. VRT on 2026-08-13 traded at $287.07 against a demand band of
    $287.11-293.88: four cents below the floor, so the band did not count as
    "inside", and the picker fell through to the next band down at
    $159-163 — 45% away. The plan that came out quoted a 45.5% stop and a
    target at the current price. A band four cents away is the band you mean.

    A band ABOVE price is eligible only within `ENTRY_ABOVE_TOL_PCT` — enough
    to catch that four-cent near-miss, nowhere near enough to return a band
    far overhead. Price well below every demand band is a BREAKDOWN, and the
    honest answer there is None, not "buy 60% higher"
    (`test_entry_zone_is_none_when_there_is_no_demand_below`).
    """
    if not demand_zones:
        return None

    def distance(z: dict) -> float:
        lo, hi = z.get("lo") or 0.0, z.get("hi") or 0.0
        if lo <= last_price <= hi:
            return 0.0
        return (lo - last_price) if last_price < lo else (last_price - hi)

    inside = [z for z in demand_zones if distance(z) == 0.0]
    if inside:
        return max(inside, key=lambda z: z.get("strength") or 0)

    tol = last_price * ENTRY_ABOVE_TOL_PCT / 100.0
    eligible = [z for z in demand_zones
                if (z.get("hi") or 0) <= last_price or distance(z) <= tol]
    if not eligible:
        return None
    # 0 = at/below price (buyable on a pullback), 1 = the near-miss above it.
    best = min(eligible,
               key=lambda z: (distance(z), 0 if (z.get("hi") or 0) <= last_price else 1))

    # Price extended far above even the nearest band: support, not an entry.
    #
    # Measured against the prospective STOP, not the band top, so the gate uses
    # the same number the plan would carry. SYRE showed why: at $103.63 with a
    # band at $90.75-93.99 the band top is 9.3% away (inside a 10% tolerance)
    # while the stop under the band floor is 13.7% away — the plan would have
    # survived a band-distance gate carrying a risk the house cap forbids.
    if (best.get("hi") or 0) < last_price:
        lo = best.get("lo") or 0.0
        stop = lo * (1.0 - STOP_BUFFER_PCT / 100.0)
        if last_price > 0 and (last_price - stop) / last_price * 100.0 > _entry_below_tol_pct():
            return None
    return best


# Chart window bounds, matching chart_maps.board so the Setup tab and the
# chart-maps tiles frame the same band the same way.
SERIES_BARS_MIN = 130
SERIES_BARS_MAX = 252
SERIES_BARS_PAD = 15
# Used when no entry band is in play and there is nothing to frame.
SERIES_BARS_DEFAULT = 180


def series_window(zone: Optional[dict]) -> int:
    """Bars needed to show the swings that DEFINE this band. PURE.

    Zones are computed over 252 bars (``price_zones.LOOKBACK_BARS``) while this
    series was hardcoded to 180, so any band whose oldest defining touch sat
    between 181 and 252 bars back was drawn with its own evidence off the left
    edge — the band appeared to rest on nothing. Same rule as
    ``chart_maps.board._zone_window``.
    """
    oldest = (zone or {}).get("oldest_touch_bars")
    try:
        oldest = int(oldest)
    except (TypeError, ValueError):
        return SERIES_BARS_DEFAULT
    return int(min(SERIES_BARS_MAX, max(SERIES_BARS_MIN, oldest + SERIES_BARS_PAD)))


def _series_for_chart(df: pd.DataFrame, bars: int = SERIES_BARS_DEFAULT) -> list[dict]:
    """OHLCV series the FE draws the bands against.

    Ajay 2026-08-16: *"can you also add volume please"*, on the Setup-tab zone
    chart. `close` is kept alongside o/h/l/v so nothing that already reads this
    payload has to change.
    """
    tail = df.iloc[-bars:]
    out = []
    for idx, row in tail.iterrows():
        d = row.get("date") if "date" in tail.columns else idx
        try:
            ds = pd.Timestamp(d).strftime("%Y-%m-%d")
        except Exception:
            ds = str(d)[:10]

        def _f(key):
            """float(row[key]) or None — NaN counts as missing."""
            try:
                v = float(row[key])
            except (KeyError, TypeError, ValueError):
                return None
            return v if v == v else None

        close = _f("close")
        if close is None:
            continue                      # a bar with no close is not a bar
        vol = _f("volume")
        out.append({
            "date": ds,
            # A missing o/h/l degenerates to a doji at the close rather than
            # dropping the bar — a hole in the series would shift every bar
            # after it and silently mis-place the bands.
            "open": round(_f("open") or close, 2),
            "high": round(_f("high") or close, 2),
            "low": round(_f("low") or close, 2),
            "close": round(close, 2),
            # Volume is a count, not a price — never rounded to 2dp.
            "volume": None if vol is None else int(vol),
        })
    return out


def analyze_symbol(symbol: str, with_series: bool = False) -> Optional[dict]:
    """Full zone + re-entry + trade-plan record for one ticker.

    Works for ANY symbol, not only re-entry hits — the individual-stock view
    uses it to draw the bands and label entry/exit even when price sits in
    overhead supply.
    """
    sym = (symbol or "").upper().strip()
    if not sym:
        return None
    df = prices.load_prices(sym, period="2y")
    rec = decide_from_frame(df, sym)
    if rec is None:
        return None

    if with_series:
        # Frame the window around the band being traded, so the swings that
        # DEFINE it are on screen. Falls back to the entry zone, then the
        # nearest support, then the default.
        rec["series"] = _series_for_chart(
            df, series_window(rec.get("entry_zone") or rec.get("nearest_support")))
        # Detail view only: today's off-exchange prints, so the zone chart can
        # mark WHERE big size changed hands relative to the bands. Ajay
        # 2026-08-13: "Add the darkpool and order block details in to the
        # SEPA/Details tab". Best-effort — a failed tape pull just omits it.
        rec["venues"] = _session_venues(sym)
    return rec


def _verdict_after_break(verdict: Optional[dict], entry_zone: Optional[dict],
                         band: dict) -> Optional[dict]:
    """Downgrade a "support is right here" verdict on a band that just broke. PURE.

    `price_zones._verdict` is a SNAPSHOT — it answers "where is price relative to
    the bands *today*", and for price inside a demand band the honest snapshot
    answer is AT_DEMAND / favorable. It has no history, so it cannot know the
    band failed two sessions ago, and giving it history would make every /zones
    read depend on the re-entry rules.

    So the transition module does the downgrade, which is the same split the
    module docstring describes. Ajay 2026-08-17, on NBIX: *"We fell below the
    demand zone but you still say buy in one place"* — the chart drew the break
    and this verdict still read 🟢 favorable underneath it.

    Only AT_DEMAND is touched. AT_SUPPLY and the rest never claimed support.
    """
    if not verdict or not band.get("broke_below"):
        return verdict
    if verdict.get("state") != "AT_DEMAND":
        return verdict
    lo = (entry_zone or {}).get("lo")
    depth = band.get("lowest_close_pct_below")
    return {**verdict,
            "state": "DEMAND_BROKEN",
            "entry_read": "caution",
            "support_pct": None,
            "label": ("Back inside a demand band that BROKE first"
                      + (f" — a close below ${lo}" if lo else "")
                      + (f", {depth}% under it" if depth is not None else "")
                      + ". Reclaiming a floor does not un-break it; treat this as a "
                        "level being fought over, not as support.")}


def decide_from_frame(df, sym: str):
    """The zone + re-entry + trade-plan decision for ONE price frame.

    Extracted from `analyze_symbol` 2026-08-16 so the walk-forward backtest
    (`zone_backtest.py`) can score the SAME rule the live board runs, on a
    truncated frame, instead of a reimplementation that quietly drifts from it.
    `test_zone_backtest.py::test_backtest_and_live_agree_on_the_same_frame`
    pins that they stay identical.

    PURE with respect to the frame: reads `df` and nothing else. No network,
    no clock, no cache — which is what makes it safe to call once per historical
    decision day.
    """
    if df is None or len(df) < MIN_BARS:
        return None

    zones = price_zones.compute(df, **zone_geom())
    if not zones:
        return None

    last_price = zones["last_price"]
    demand = zones.get("demand_zones") or []
    supply = zones.get("supply_zones") or []

    # Falling-knife guard (replaced the Minervini trend template 2026-08-13 —
    # see the module docstring for why, and for the CIEN case that forced it).
    closes, lows_s = df["close"], df["low"]
    structure = liq.structure_read(closes.tolist(), lows_s.tolist(),
                                   swing_window=STRUCTURE_SWING_WINDOW)
    ma50 = closes.rolling(50).mean()
    _ma_now = float(ma50.iloc[-1]) if pd.notna(ma50.iloc[-1]) else None
    _ma_prior = (float(ma50.iloc[-(MA_SLOPE_LOOKBACK + 1)])
                 if len(ma50) > MA_SLOPE_LOOKBACK and pd.notna(ma50.iloc[-(MA_SLOPE_LOOKBACK + 1)])
                 else None)
    is_knife = liq.is_falling_knife(structure, last_price, _ma_now, _ma_prior)
    structure["ma50_rising"] = (None if _ma_now is None or _ma_prior is None
                                else bool(_ma_now > _ma_prior))
    trend_ok = not is_knife

    entry_zone = _pick_entry_zone(last_price, demand)
    closes = [float(c) for c in df["close"].tolist()]

    band = None
    if entry_zone and entry_zone.get("lo", 0) <= last_price <= entry_zone.get("hi", 0):
        band = reentry_read(closes, entry_zone["hi"], entry_zone["lo"], last_price)
    else:
        band = {"is_reentry": False, "fell_from_pct": None,
                "bars_since_above": None, "in_band": False,
                "broke_below": False, "bars_since_break": None,
                "lowest_close_pct_below": None}

    quality_ok = bool(entry_zone
                      and (entry_zone.get("touches") or 0) >= MIN_TOUCHES
                      and (entry_zone.get("strength") or 0) >= MIN_ZONE_STRENGTH)

    # Target candidates: `nearest_resistance` FIRST, because price_zones
    # computes it over every band while `supply_zones`/`demand_zones` are
    # truncated to the strongest four per side — the true first objective is
    # often not in those lists. KLAC's real target ($230.89) was missing from
    # them, so a supply-list-only search jumped to $302, an implausible 11.8R.
    # Band origin is irrelevant here: price_zones keeps it for colour only,
    # since broken support acts as resistance. The entry band excludes itself
    # via the `lo > band top` rule inside trade_plan.
    plan = trade_plan(last_price, entry_zone,
                      [zones.get("nearest_resistance")]
                      + (zones.get("supply_zones") or [])
                      + (zones.get("demand_zones") or []),
                      recent_lows=[float(x) for x in lows_s.tolist()])

    rec = {
        "symbol": sym,
        "name": company_names.name_for(sym) or sym,
        "last_price": last_price,
        "supply_zones": supply,
        "demand_zones": demand,
        "nearest_resistance": zones.get("nearest_resistance"),
        "nearest_support": zones.get("nearest_support"),
        # Break evidence for the HIGHEST surfaced demand band, only when price
        # is below it. The per-band lists carry touch ages, not break history,
        # and `zone_broken` above describes the ENTRY band — which for a name
        # in its second-level band is a different band entirely. Computed here
        # because `closes` exists here; deep_demand.read() consumes it.
        "top_band_read": (reentry_read(closes, demand[0]["hi"], demand[0]["lo"],
                                       last_price)
                          if demand and last_price < demand[0]["lo"] else None),
        "verdict": _verdict_after_break(zones.get("verdict"), entry_zone, band),
        # The re-entry read.
        "in_demand_band": band["in_band"],
        "is_reentry": bool(band["is_reentry"] and trend_ok and quality_ok),
        "fell_from_pct": band["fell_from_pct"],
        "bars_since_above": band["bars_since_above"],
        # The broken-band evidence (Ajay 2026-08-17, NBIX). Surfaced even when
        # it is the reason the row was refused, so the Setup tab can say WHY a
        # name sitting inside its band is not a buy.
        "zone_broken": band["broke_below"],
        "bars_since_zone_break": band["bars_since_break"],
        "lowest_close_pct_below_zone": band["lowest_close_pct_below"],
        # Why it did / didn't qualify — surfaced so the list is auditable.
        "structure": structure,
        "is_knife": is_knife,
        "trend_ok": trend_ok,
        "zone_quality_ok": quality_ok,
        "entry_zone": entry_zone,
        "plan": plan,
        "liquidity": _liquidity(df),
        "breakeven_win_pct": (round(100.0 / (1.0 + plan["rr"]), 1)
                              if plan and plan.get("rr") and plan["rr"] > 0 else None),
        "params": zones.get("params"),
        "resolution": zones.get("resolution"),
        "disclaimer": DISCLAIMER,
    }
    # The INVERSE read (Ajay 2026-08-20): is this name running into a ceiling?
    # Attached here rather than in a second pass because every band it needs
    # was just computed above — see into_supply's header. Imported locally to
    # keep the module-level import graph acyclic (into_supply imports the
    # thresholds from THIS module, so one scale governs both boards).
    #
    # Wrapped: the demand board is what Ajay trades from every day, and a
    # defect in the newer, secondary read must never be able to take it down.
    try:
        from . import into_supply as _isup
        rec["supply"] = _isup.read_from_frame(df, rec)
    except Exception as exc:                                  # pragma: no cover
        log.debug("into-supply: %s failed: %s", sym, exc)
        rec["supply"] = None
    # Falling toward the band, not yet in it (Ajay 2026-08-31). Computed HERE
    # and not in the scan loop because this is the only place the close series
    # is guaranteed to exist: the scan calls analyze_symbol(with_series=False),
    # and the first build read rec["series"] there — a key that path never
    # attaches — so the predicate honestly refused all ~1,750 names and the
    # approaching board deployed empty. Locked by
    # test_decide_from_frame_attaches_the_approaching_read.
    rec["approaching"] = approaching_read(rec, closes)
    # The order-block flavour of the same question (Ajay 2026-08-31). Computed
    # here for the same reason: this is where the frame and closes exist.
    rec["approaching_ob"] = approaching_ob_read(rec, df, closes)
    rec["in_ob"] = in_ob_read(rec, df)

    return rec


def _session_venues(symbol: str) -> dict:
    """Today's (or the prior session's) venue split + large off-exchange
    blocks, each with the price it printed at."""
    from datetime import date as _d
    from orderflow import darkpool, quotes as quotes_mod, retail as retail_mod, tape as tape_mod

    out = {"available": False, "blocks": [], "rating": None}
    try:
        # The most recent day that actually PRINTED, not "yesterday" — a
        # one-calendar-day fallback lands on Sunday every Monday pre-open and
        # returned nothing all weekend (measured 2026-08-17).
        trades, _tape_day = tape_mod.last_session_trades(symbol)
        if trades is None or trades.empty:
            return out
        v = darkpool.split_venues(trades)
        blocks = darkpool.dark_blocks(trades, top=12)
        return {**v, "blocks": blocks, "rating": _venue_rating(v.get("dark_pct")),
                "read": darkpool.read(v), "disclaimer": darkpool.DISCLAIMER}
    except Exception as exc:
        log.debug("zone-map: venue pull failed for %s: %s", symbol, exc)
        return out


def _liquidity(df) -> dict:
    """CAN you trade it (50-day average) and IS anything happening right now
    (today's volume vs that average).

    Ajay 2026-08-14 asked whether the board carried "current volume of trade".
    It did not — only the 50-day average, which says a name is tradeable in
    general but nothing about today. A perfect zone on dead volume and a
    perfect zone on 3x volume are different situations, and RVOL is the
    standard way to tell them apart. Both come free from bars already loaded.

    Dollar volume is NOT a spread measurement — a $5 stock at $3M/day still
    costs more to cross than its tier implies."""
    out = {"avg_vol_50": None, "avg_dollar_vol_50": None,
           "today_vol": None, "today_dollar_vol": None, "rvol": None,
           "rvol_state": None, "tier": None, "tradeable": None}
    try:
        tail = df.iloc[-50:]
        vol = float(tail["volume"].mean())
        dollars = float((tail["close"] * tail["volume"]).mean())
        today_v = float(df["volume"].iloc[-1])
        today_c = float(df["close"].iloc[-1])
    except Exception:
        return out
    if not vol or vol <= 0:
        return out

    tier = ("deep" if dollars >= LIQ_DEEP_USD else
            "ok" if dollars >= LIQ_OK_USD else
            "thin" if dollars >= LIQ_THIN_USD else "illiquid")
    # Is the last bar TODAY's (and therefore possibly partial), or a complete
    # prior session? Only the former needs projecting.
    partial, frac = False, 1.0
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        et = ZoneInfo("America/New_York")
        last_day = df.index[-1]
        last_day = last_day.date() if hasattr(last_day, "date") else None
        if last_day and last_day == datetime.now(et).date():
            frac = _session_fraction()
            partial = 0.0 < frac < 1.0
    except Exception:
        partial, frac = False, 1.0

    # The daily bar for TODAY is a stale snapshot, not a live total. Measured
    # 2026-08-14 at 10:52 ET: live tape showed 1.5-2.6x the volume the daily
    # bar carried (SWKS 890k vs 348k). Any RVOL off that bar understates by
    # whatever the cache lag happens to be — a different amount per name, so
    # the column would not even be internally comparable.
    #
    # So mid-session we publish NO rvol here. `_attach_venues` overwrites it
    # for the top rows using the live tape it already fetches for the venue
    # split; everything else honestly reports "pending".
    rvol, source = None, "daily_bar"
    if partial:
        source = "pending"
    elif vol > 0:
        rvol = round(today_v / vol, 2)

    state = None
    if rvol is not None:
        state = ("surging" if rvol >= RVOL_SURGE else
                 "active" if rvol >= RVOL_ACTIVE else
                 "quiet" if rvol >= RVOL_QUIET else "dead")
    return {"avg_vol_50": int(vol), "avg_dollar_vol_50": int(dollars),
            "today_vol": (None if partial else int(today_v)),
            "today_dollar_vol": (None if partial else int(today_v * today_c)),
            "rvol": rvol, "rvol_state": state,
            "rvol_partial": partial, "today_source": source,
            "session_pct": round(frac * 100) if partial else 100,
            "last_close": round(today_c, 2),
            "tier": tier, "tradeable": tier != "illiquid"}


def _venue_rating(dark_pct: Optional[float]) -> Optional[str]:
    """Plain label for off-exchange share. Venue fact, not intent — the bucket
    mixes dark-pool crossing with retail internalisation (see orderflow.darkpool)."""
    if dark_pct is None:
        return None
    if dark_pct >= 45.0:
        return "heavy"
    if dark_pct >= 30.0:
        return "normal"
    return "light"


def _enrich_one(r: dict, tape_mod, quotes_mod, darkpool, retail_mod, _d):
    """Fetch one row's tape + NBBO and build its venue/retail blocks.

    Returns (venues, retail, block_list, total_shares, tape_is_today) or None.
    Pure I/O per row so the caller can run these concurrently.
    """
    try:
        # Walk back to the last session that printed. The old one-calendar-day
        # fallback meant this returned None for every row all weekend and every
        # Monday pre-open, so the dark-pool and retail SORTS on the board ranked
        # a column of nulls and quietly gave back the default order.
        trades, tape_day = tape_mod.last_session_trades(r["symbol"])
        if trades is None or trades.empty:
            return None
        tape_is_today = tape_day == _d.today()
        v = darkpool.split_venues(trades)
        block_list = darkpool.dark_blocks(trades)
    except Exception as exc:
        log.debug("demand-reentry: venue fetch failed for %s: %s", r["symbol"], exc)
        return None

    retail_block = {"available": False}
    try:
        nbbo = (quotes_mod.fetch_quotes(r["symbol"], _d.today(),
                                        max_pages=VENUE_QUOTE_PAGES)
                if tape_is_today else None)
        rt = retail_mod.identify(trades, nbbo)
        retail_block = {**rt, "divergence": retail_mod.divergence(rt, block_list)}
    except Exception as exc:
        log.debug("demand-reentry: retail read failed for %s: %s", r["symbol"], exc)

    return {
        "venues": {**v, "blocks": len(block_list),
                   "rating": _venue_rating(v.get("dark_pct"))},
        "retail": retail_block,
        "total_shares": v.get("total_shares") or 0,
        "tape_is_today": tape_is_today,
    }


def _attach_venues(rows: list, top_n: int = VENUE_DETAIL_TOP_N,
                   budget_sec: float = VENUE_BUDGET_SEC) -> None:
    """Attach venue + retail detail to the top `top_n` rows by R:R, in place.

    Concurrent and time-boxed. Rows that do not finish inside the budget are
    left without detail rather than holding up the whole response.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from concurrent.futures import TimeoutError as FuturesTimeout
    from datetime import date as _d
    from orderflow import darkpool, quotes as quotes_mod, retail as retail_mod, tape as tape_mod

    ranked = sorted(rows, key=lambda r: -((r.get("plan") or {}).get("rr") or 0))[:top_n]
    if not ranked:
        return

    t0 = time.time()
    done = 0
    # NOT a `with` block: pool.__exit__ is shutdown(wait=True), which would
    # sit on the very future whose hang we are defending against below.
    pool = ThreadPoolExecutor(max_workers=VENUE_WORKERS)
    try:
        futures = {pool.submit(_enrich_one, r, tape_mod, quotes_mod,
                               darkpool, retail_mod, _d): r for r in ranked}
        for fut in as_completed(futures, timeout=budget_sec + _VENUE_SLACK_SEC):
            r = futures[fut]
            if time.time() - t0 > budget_sec:
                break
            try:
                got = fut.result(timeout=0.1)
            except Exception:
                got = None
            if not got:
                continue
            r["venues"] = got["venues"]
            r["retail"] = got["retail"]
            done += 1

            # Live tape gives an ACCURATE today-volume, so fill in the RVOL
            # that _liquidity had to leave pending. The session fraction must
            # follow the TAPE's day, not the daily bar's.
            L = r.get("liquidity") or {}
            avg = L.get("avg_vol_50") or 0
            total = got["total_shares"]
            if avg > 0 and total > 0:
                frac = _session_fraction() if got["tape_is_today"] else 1.0
                if frac <= 0:
                    frac = 1.0
                if frac >= RVOL_MIN_FRACTION:
                    rv = round(total / (avg * frac), 2)
                    L.update({
                        "today_vol": int(total),
                        "today_dollar_vol": int(total * (L.get("last_close") or 0)),
                        "rvol": rv, "today_source": "tape",
                        "rvol_state": ("surging" if rv >= RVOL_SURGE else
                                       "active" if rv >= RVOL_ACTIVE else
                                       "quiet" if rv >= RVOL_QUIET else "dead"),
                    })
                    r["liquidity"] = L
    except FuturesTimeout:
        # `as_completed(timeout=...)` RAISES at the deadline — it does not just
        # stop iterating. Uncaught, one hung fetch escaped this function and
        # killed the entire 1,500-name scan it was decorating, so the warm
        # thread threw everything away and restarted: "background warm failed
        # for sp1500: 1 (of 15) futures unfinished", every ~90s, board saying
        # "Scanning…" forever — the 2026-08-25 morning the Massive key (shared
        # with his friend) hit max_connections. Detail on a few rows is
        # decoration; the scan landing is the product.
        left = sum(1 for f in futures if not f.done())
        log.warning("demand-reentry: venue enrichment timed out with %d/%d "
                    "unfinished — continuing without their detail",
                    left, len(ranked))
    finally:
        # Not the pool's context manager: shutdown(wait=True) would sit on the
        # hung future. cancel_futures kills the queued ones; the running one
        # finishes in the background and its result is discarded.
        pool.shutdown(wait=False, cancel_futures=True)
    log.info("demand-reentry: enriched %d/%d rows in %.1fs (budget %.0fs)",
             done, len(ranked), time.time() - t0, budget_sec)


def _rank_key(r: dict):
    """Freshest, strongest re-entries first: most recently back in the band,
    then the strongest band, then the deepest pullback."""
    bars = r.get("bars_since_above")
    z = r.get("entry_zone") or {}
    return (bars if bars is not None else 9_999,
            -(z.get("strength") or 0),
            -(r.get("fell_from_pct") or 0))


# Universe choices offered on the page. sp1500 is the "beyond the S&P 500"
# ask (Ajay 2026-08-13): S&P 400 MidCap + S&P 600 SmallCap add ~1,000 names
# that still clear S&P's index-committee bar (incl. positive earnings), which
# a raw Russell slice does not.
# Ajay 2026-08-20: "Here is what I want instead of themes, I want QQQ stocks
# and SPY stocks and Nasdaq stocks."
#
# QQQ and SPY are ETFs, so what he is asking for is the INDEX each one tracks:
# QQQ = Nasdaq-100, SPY = S&P 500. Both are labelled with the ticker he thinks
# in, because "S&P 500" and "SPY" being the same list was not obvious from a
# dropdown that only ever said the former.
#
# The theme entries are KEPT and moved to the bottom rather than deleted. They
# are not a slice of an index, they are the names no index holds — IONQ, OKLO,
# SMR and QBTS are NYSE-listed and in no S&P tier, so `nasdaq` does not carry
# them either and removing these entries would silently drop them from every
# board. Deleting them is a one-line change whenever he wants it.
UNIVERSES = {
    # ONE universe (Ajay 2026-08-25: "Remove all these themes and just do
    # default universe scan" + "I need full universe scanned for this").
    # Same `full` alias the SEPA scanner runs — Russell 1000 ∪ S&P 1500 ∪
    # curated ∪ themes, ONE definition in sepa/universe.py so the two engines
    # can never fish different waters again. Legacy keys (sp1500_plus, qqq,
    # sp500, ...) normalise here via _universe_key's default, so old
    # bookmarks, cron lines and cached history keep working.
    "full": ("Full universe (Russell 1000 ∪ S&P 1500 ∪ themes)",
             lambda: universe_mod.load_universe("full")),
}
# The one universe (2026-08-25). History: sp500 → sp1500 (2026-08-14, "make
# it default scan 1500") → the SEPA `full` alias (~1,750 names). Warmed by
# cron so the page load is instant, see crontab.
DEFAULT_UNIVERSE = "full"

# Pinned to the DEMAND universe only (Ajay 2026-08-28, three asks in one
# afternoon: gold+silver "with their supply demand zones"; "keep SPY, QQQ,
# TQQQ, SOXL on the priority list ... optical fibre, Quantum, Energy, rare
# earth mineral ... anything else related to AI infra structure"; "the ones
# Trump has been announcing and some robotic ETFs"). ETFs have no
# sales/earnings, so they are NOT added to sepa/universe's `full` alias —
# the SEPA fundamental scanner never sees them and the one-definition rule
# stays true for stocks. Own provenance seat ("pinned") keeps the
# curated-fallthrough heuristic honest.
#
# Every ticker liquidity-verified 2026-08-28 (web-researched, official
# issuer/AUM sources): all $300M+ AUM or better except LYTE (3 weeks old,
# $357M, 2-3M sh/day). Deliberately EXCLUDED as dead/thin/shells: FIVG
# (ticker dead → UFOX), SRVR (bleeding, DTCR beats it), HUMN ($47M), BOAT
# ($79M), IVEP/NCLD/COOL/CGPT/SMRF/RACK/TCAI (young or tiny). TQQQ/SOXL
# are 3x levered — the frontend leveraged-ETF guardrail chip flags them.
PINNED_ETFS = (
    # havens + his index/leveraged priority list
    "GLD", "SLV", "SPY", "QQQ", "TQQQ", "SOXL",
    # semis + memory (DRAM: $1B AUM in 10 days, Apr-2026 launch)
    "SMH", "SOXX", "DRAM",
    # quantum ($5B AUM)
    "QTUM",
    # nuclear / energy dominance (NUKZ = new-build stack; FCG/XOP = gas/E&P)
    "URA", "NLR", "NUKZ", "XLE", "FCG", "XOP",
    # AI power + grid buildout (AIPO $946M first-mover)
    "GRID", "AIPO",
    # critical minerals / copper (REMX tripled on 2026 executive actions)
    "REMX", "COPX",
    # data-center + AI software
    "DTCR", "AIQ", "IGV",
    # robotics + humanoid (KOID $6.3B — biggest robotics ETF, period)
    "BOTZ", "ROBO", "ARKQ", "KOID",
    # photonics / optical (his LYTE)
    "LYTE",
    # defense + onshoring + crypto policy (ITA/PPA/SHLD; AIRR; IBIT)
    "ITA", "PPA", "SHLD", "AIRR", "IBIT",
    # water/cooling proxy
    "PHO",
)


def _universe_key(key) -> str:
    """Normalise a universe argument to a known key.

    Deliberately tolerant of non-strings: FastAPI resolves `Query(...)`
    defaults at REQUEST time, so a handler called directly — which is how these
    endpoints get smoke-tested in the container — receives the Query object
    itself and `(key or DEFAULT).lower()` blew up on it. Anything unrecognised
    lands on the default rather than raising.
    """
    if not isinstance(key, str) or not key.strip():
        return DEFAULT_UNIVERSE
    k = key.strip().lower()
    return k if k in UNIVERSES else DEFAULT_UNIVERSE


def _resolve_universe(key: str):
    """(symbols, label, provenance, stale_days, key) for a universe.

    Each LAYER is fetched and validated independently: a `last_source` record
    is only trusted when its `n` matches the list that layer actually returned.
    The record is module-global, so a leftover from an earlier resolve — or a
    test double standing in for a fetcher — must never mislabel this scan.
    Multi-layer universes (sp1500) report their WORST layer's staleness.
    """
    k = _universe_key(key)
    label = UNIVERSES[k][0]
    parts = [k]

    syms: list[str] = []
    seen: set[str] = set()
    prov: dict[str, Optional[dict]] = {}
    for part in parts:
        try:
            got = UNIVERSES[part][1]() or []
        except Exception as exc:
            log.warning("demand-reentry: universe layer %s failed: %s", part, exc)
            got = []
        rec = None
        try:
            r = universe_mod.last_source(part)
            if r and r.get("n") == len(got):
                rec = r
        except Exception:
            rec = None
        prov[part] = rec
        for sym in got:
            if sym and sym not in seen:
                seen.add(sym)
                syms.append(sym)

    n_pinned = 0
    for sym in PINNED_ETFS:
        if sym and sym not in seen:
            seen.add(sym)
            syms.append(sym)
            n_pinned += 1
    if n_pinned:
        prov["pinned"] = {"source": "pinned", "n": n_pinned}

    stale_ages = [(v or {}).get("age_days") or 0.0 for v in prov.values()
                  if v and v.get("source") == "stale-cache"]
    stale = int(round(max(stale_ages))) if stale_ages else None
    return syms, label, prov, stale, k


def scan(force: bool = False, limit: Optional[int] = None,
         universe: str = DEFAULT_UNIVERSE) -> dict:
    """Scan the full universe for demand-zone re-entries. Cached `_CACHE_TTL_SEC`.

    Universe is `sepa.universe.load_universe("full")` — the same alias the
    SEPA scanner runs — and each layer inside it resolves fresh cache → live
    fetch → STALE cache → curated. `universe_note` reports which list was
    actually used so the page can't quietly claim more than it scanned.

    Staleness is reported too (2026-08-13). The curated fallthrough is loud —
    `universe_is_sp500` goes False and the UI warns — but a stale cache is
    silent by construction: it holds the real constituents, just frozen at
    the day the live fetch broke. Between 2026-05-29 and 2026-08-13 that list
    aged 76 days with nothing on the page saying so. `universe_stale_days`
    closes that hole.
    """
    ukey = _universe_key(universe)
    # Same FastAPI trap as the universe key: Query(...) defaults resolve at
    # REQUEST time, so a direct call gets the Query OBJECT — which is truthy,
    # so `if not force` never fired and every in-container call silently
    # recomputed instead of using the cache. Coerce to real bools/ints.
    force = force is True
    try:
        limit = int(limit) if limit is not None else None
    except (TypeError, ValueError):
        limit = None
    if not force:
        c = _cache.get(ukey)
        if c and (time.time() - c["ts"]) < _CACHE_TTL_SEC:
            return {**c["data"], "cached": True}

    t0 = time.time()
    # Published BEFORE the constituent fetch: resolving sp1500 means three
    # network calls and can itself take seconds, and a page that shows nothing
    # during them looks hung for exactly the reason Ajay reported.
    _publish_progress(ukey, "universe", started_at=t0, current=0, total=0,
                      hits=0, errors=0, symbol=None, universe_label=None)
    syms, ulabel, uprov, ustale, ukey = _resolve_universe(ukey)
    # Provenance across every layer of the chosen universe. A record is only
    # trusted when it describes the list we actually got back — a stale record
    # from an earlier resolve, or a test double standing in for a fetcher,
    # must not mislabel it. sp1500 reports its WORST layer.
    curated_n = len(getattr(universe_mod, "UNIVERSE", []) or [])
    sources = [v.get("source") for v in uprov.values() if v]
    pinned_n = int((uprov.get("pinned") or {}).get("n") or 0)
    looks_curated = ("curated" in sources) or (
        len(syms) == curated_n + pinned_n
        and len([k for k in uprov if k != "pinned"]) == 1)

    if looks_curated:
        universe_note = f"{ulabel} unavailable — scanned the curated list instead"
    elif ustale is not None:
        universe_note = (f"{ulabel} ({len(syms)} names) from a "
                         f"{int(ustale)}-day-old cached list — the live "
                         f"constituent fetch is failing")
    else:
        universe_note = f"{ulabel} ({len(syms)} names)"

    from . import into_supply as _into_supply
    from . import deep_demand as _deep
    rows, scanned, errors = [], 0, 0
    supply_rows: list = []          # the inverse board, same pass
    deep_rows: list = []            # second-level arrivals, same pass
    approaching_rows: list = []     # falling TOWARD a band, same pass (2026-08-31)
    approaching_ob_rows: list = []  # falling toward a fresh ORDER BLOCK (2026-08-31)
    in_ob_rows: list = []           # INSIDE a fresh order block, first touch (2026-08-31)
    total = len(syms)
    _publish_progress(ukey, "scanning", started_at=t0, current=0, total=total,
                      hits=0, errors=0, symbol=None, universe_label=ulabel)
    for i, sym in enumerate(syms, 1):
        try:
            rec = analyze_symbol(sym)
        except Exception as exc:
            errors += 1
            log.debug("demand-reentry: %s failed: %s", sym, exc)
            rec = None
        if rec:
            scanned += 1
            if rec["is_reentry"]:
                # Same flow verdict the deep board carries (Ajay 2026-08-25:
                # "bake in CMF flow logic in to this one too") — the canonical
                # volume read over the already-warm frame, ~60 hits per scan.
                try:
                    from sepa import volume as _vol2
                    from . import deep_demand as _deep2
                    rec["inflow"] = _deep2.inflow_read(
                        _vol2.analyze(prices.load_prices(sym)))
                except Exception:
                    rec["inflow"] = None
                rec.pop("series", None)
                rows.append(rec)
            # Second predicate, same record, same loop — no extra price load.
            # Guarded for the same reason the read itself is: this must not be
            # able to abort a demand scan.
            try:
                if _into_supply.qualifies(rec):
                    r2 = dict(rec)
                    if "inflow" not in r2:
                        try:
                            from sepa import volume as _vol2
                            from . import deep_demand as _deep2
                            r2["inflow"] = _deep2.inflow_read(
                                _vol2.analyze(prices.load_prices(sym)))
                        except Exception:
                            r2["inflow"] = None
                    r2.pop("series", None)
                    supply_rows.append(r2)
            except Exception as exc:                          # pragma: no cover
                log.debug("into-supply: collecting %s failed: %s", sym, exc)
            # Fourth predicate, same record, same loop (Ajay 2026-08-31:
            # "I need the ones that are about to reach and catch them").
            # decide_from_frame attached the read; this only collects it.
            try:
                a6 = rec.get("in_ob")
                if a6:
                    r6 = dict(rec)
                    r6.pop("series", None)
                    in_ob_rows.append(r6)
            except Exception as exc:                          # pragma: no cover
                log.debug("in-ob: collecting %s failed: %s", sym, exc)
            try:
                a5 = rec.get("approaching_ob")
                if a5:
                    r5 = dict(rec)
                    r5.pop("series", None)
                    approaching_ob_rows.append(r5)
            except Exception as exc:                          # pragma: no cover
                log.debug("approaching-ob: collecting %s failed: %s", sym, exc)
            try:
                a4 = rec.get("approaching")
                if a4:
                    r4 = dict(rec)
                    r4.pop("series", None)
                    r4["approaching"] = a4
                    try:
                        from sepa import volume as _vol4
                        from . import deep_demand as _deep4
                        r4["inflow"] = _deep4.inflow_read(
                            _vol4.analyze(prices.load_prices(sym)))
                    except Exception:
                        r4["inflow"] = None
                    approaching_rows.append(r4)
            except Exception as exc:                          # pragma: no cover
                log.debug("approaching: collecting %s failed: %s", sym, exc)
            # Third predicate, same record, same loop. Trend-gate-independent
            # on purpose: the penalized names this screen exists for are
            # exactly the ones is_reentry refuses (Ajay 2026-08-25).
            try:
                d3 = _deep.read(rec)
                if d3:
                    # The inflow verdict rides on the scan row (Ajay
                    # 2026-08-25: "we are looking for bullish momentum stocks
                    # and inflow signals for these"). volume.analyze is the
                    # canonical read (CMF, accum/dist day counts, p.71-76);
                    # the frame is already in the price cache from the pass
                    # that produced `rec`, so this is a warm re-read, not a
                    # second fetch. Only for deep hits — ~150 names, not 1,500.
                    try:
                        from sepa import volume as _vol
                        d3["inflow"] = _deep.inflow_read(
                            _vol.analyze(prices.load_prices(sym)))
                    except Exception:
                        d3["inflow"] = None
                    r3 = dict(rec)
                    r3.pop("series", None)
                    r3["deep_demand"] = d3
                    deep_rows.append(r3)
            except Exception as exc:                          # pragma: no cover
                log.debug("deep-demand: collecting %s failed: %s", sym, exc)
        # Every symbol, not every Nth: the writer builds one small dict and
        # swaps a reference, which costs far less than the price frame that
        # was just analysed. Sampling would only make the bar stutter.
        _publish_progress(ukey, "scanning", current=i, symbol=sym,
                          hits=len(rows), errors=errors, scanned=scanned)

    # Sorted by R:R descending (2026-08-13). The backtest found R:R >= 1.5 was
    # the ONLY cohort with positive expectancy, so the number that decides
    # whether a row is worth reading leads the list. Ties break on freshness.
    rows.sort(key=lambda r: (-((r.get("plan") or {}).get("rr") or 0.0), _rank_key(r)))
    # Nearest lid first. Sorted separately and by a different key on purpose:
    # the demand board ranks by the quality of a PLAN, this one by urgency —
    # how close the ceiling already is.
    try:
        supply_rows.sort(key=_into_supply.sort_key)
    except Exception as exc:                                  # pragma: no cover
        log.debug("into-supply: sort failed: %s", exc)
    # Deep-demand: in-band first, then closest to arriving. Capped AFTER the
    # sort so a bad-breadth day keeps the best-ranked names; the pre-cap count
    # rides on the payload so a capped day says so instead of looking complete.
    deep_total = len(deep_rows)
    try:
        deep_rows.sort(key=_deep.sort_key)
    except Exception as exc:                                  # pragma: no cover
        log.debug("deep-demand: sort failed: %s", exc)
    deep_rows = deep_rows[:_deep.MAX_ROWS]
    # Approaching: closest to arrival first — this board's urgency IS the
    # distance. Ties break on how hard it is falling (faster drift first).
    approaching_rows.sort(key=lambda r: (
        (r.get("approaching") or {}).get("dist_pct") or 99.0,
        (r.get("approaching") or {}).get("drift_pct") or 0.0))
    approaching_ob_rows.sort(key=lambda r: (
        (r.get("approaching_ob") or {}).get("dist_pct") or 99.0,
        (r.get("approaching_ob") or {}).get("drift_pct") or 0.0))
    # In-the-block: youngest block first — the freshest institutional
    # footprint is the one whose first test is most informative.
    in_ob_rows.sort(key=lambda r: (
        ((r.get("in_ob") or {}).get("block") or {}).get("bars_ago") or 999))

    # Record the FULL qualifying list before anything trims it (Ajay 2026-08-17:
    # "Can you maintain history of our In deman page please… Want you to track
    # it"). Two things must happen here and not two lines below:
    #   * `limit` — the 4:55pm cron warms with limit=1, so recording after the
    #     slice would write a one-name board every single evening.
    #   * the R:R floor, which is applied at READ time by `cached_or_warm`. The
    #     ledger stores `rr` per episode, so the floor stays a question you can
    #     ask of history rather than a filter baked into it.
    # Never allowed to break the board: a Mongo outage must cost the record,
    # not the page.
    try:
        from . import demand_history
        demand_history.record_board({**{k: v for k, v in (
            ("universe_key", ukey), ("universe_label", ulabel),
            ("scanned", scanned), ("universe", len(syms)))},
            "rows": rows, "params": {
                "swing_window": SWING_WINDOW, "merge_pct": MERGE_PCT,
                "half_width_pct": HALF_WIDTH_PCT,
                "min_rise_above_pct": MIN_RISE_ABOVE_PCT,
                "min_touches": MIN_TOUCHES,
                "min_zone_strength": MIN_ZONE_STRENGTH,
                "stop_buffer_pct": STOP_BUFFER_PCT}})
    except Exception as exc:
        log.warning("demand-reentry: history record failed: %s", exc)

    if limit:
        rows = rows[:int(limit)]

    # The tape + NBBO pull for the top rows is time-boxed at VENUE_BUDGET_SEC
    # but still the last thing between the user and a board, so it gets its own
    # phase rather than sitting inside a bar that already reads 100%.
    _publish_progress(ukey, "enriching", current=total, total=total,
                      hits=len(rows), symbol=None)
    _attach_venues(rows)

    data = {
        "rows": rows,
        "n": len(rows),
        # Second-level arrivals, same pass, same isolation rationale as
        # supply_rows below: a separate key touches no existing consumer.
        "deep_rows": deep_rows,
        "deep_n": deep_total,
        # Names falling TOWARD a tested band, same pass (Ajay 2026-08-31:
        # "the ones that are about to reach"). Separate key, same isolation
        # rationale: no existing consumer of `rows` changes by construction.
        "approaching_rows": approaching_rows,
        "approaching_n": len(approaching_rows),
        "approaching_ob_rows": approaching_ob_rows,
        "approaching_ob_n": len(approaching_ob_rows),
        "in_ob_rows": in_ob_rows,
        "in_ob_n": len(in_ob_rows),
        # The inverse board, from the same pass. A separate key so every
        # existing consumer of `rows` — the page, the R:R floor, the limit, the
        # history ledger — is untouched by construction.
        "supply_rows": supply_rows,
        "supply_n": len(supply_rows),
        "scanned": scanned,
        "universe": len(syms),
        "universe_note": universe_note,
        "universe_key": ukey,
        "universe_label": ulabel,
        "universe_sources": uprov,
        "universe_choices": [{"key": k, "label": v[0]} for k, v in UNIVERSES.items()],
        "universe_is_sp500": not looks_curated,
        # None when the constituent list is fresh; an age in days when it came
        # from an expired cache (real names, but no longer tracking adds/drops).
        # None when every layer is fresh; the OLDEST layer's age in days when
        # any came from an expired cache (real names, but no longer tracking
        # adds/drops). Multi-layer universes report their worst layer.
        "universe_stale_days": ustale,
        # Single-layer universes report the bare source; sp1500 reports each
        # layer, since they can resolve differently from one another.
        "universe_source": (
            (uprov.get(ukey) or {}).get("source") if len(uprov) == 1
            else ", ".join(f"{k}:{(v or {}).get('source')}" for k, v in uprov.items())),
        "errors": errors,
        "took_sec": round(time.time() - t0, 1),
        "as_of": datetime.now(timezone.utc).isoformat(),
        "params": {
            "swing_window": SWING_WINDOW, "merge_pct": MERGE_PCT,
            "half_width_pct": HALF_WIDTH_PCT,
            "reentry_lookback_bars": REENTRY_LOOKBACK_BARS,
            "min_rise_above_pct": MIN_RISE_ABOVE_PCT,
            "min_touches": MIN_TOUCHES, "min_zone_strength": MIN_ZONE_STRENGTH,
            "structure_swing_window": STRUCTURE_SWING_WINDOW,
            "ma_slope_lookback": MA_SLOPE_LOOKBACK,
            "stop_buffer_pct": STOP_BUFFER_PCT,
        },
        "disclaimer": DISCLAIMER,
        "cached": False,
        "warming": False,
    }
    _cache[ukey] = {"ts": time.time(), "data": data}
    _publish_progress(ukey, "done", current=total, total=total, hits=len(rows),
                      errors=errors, scanned=scanned, symbol=None,
                      took_sec=data["took_sec"])
    log.info("demand-reentry: %d hits from %d scanned (%s) in %.1fs",
             len(rows), scanned, universe_note, data["took_sec"])
    return data
