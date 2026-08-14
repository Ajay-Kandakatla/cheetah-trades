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

MIN_BARS = 220                # ~1y of bars for the structure read

# ── Liquidity tiers (avg 50-day dollar volume) ───────────────────────────────
# Ajay 2026-08-13: "if there are no order flow or book map or volume no point
# buying". A great R:R on a name you cannot get filled in is not a trade — and
# on thin tape the spread alone can exceed the edge. House values.
LIQ_DEEP_USD  = 50_000_000.0   # institutional-grade tape
LIQ_OK_USD    = 10_000_000.0   # comfortably tradeable in retail size
LIQ_THIN_USD  =  2_000_000.0   # tradeable only in small size, wider spreads
# Below LIQ_THIN_USD the spread and slippage swamp a 2R edge -> not tradeable.

# Dark-pool detail is pulled from the day's tape, which costs a fetch per name,
# so only the top rows by R:R get it — those are the only ones worth acting on.
VENUE_DETAIL_TOP_N = 15

# How far ABOVE price a demand band may sit and still be the entry band. Covers
# price resting a hair under a floor it has been trading in (VRT, 4 cents);
# anything further means price has broken below the band, not approached it.
ENTRY_ABOVE_TOL_PCT = 1.5

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
    it got (`fell_from_pct`) and how many bars ago it was last above
    (`bars_since_above`). Requires price to be INSIDE the band now — a name
    below the floor has broken support, which is the opposite of this signal.
    """
    out = {"is_reentry": False, "fell_from_pct": None,
           "bars_since_above": None, "in_band": False}
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
    out["is_reentry"] = bool(rise >= min_rise_pct and above_idx)
    return out


def trade_plan(last_price: float, entry_zone: Optional[dict],
               resistance, stop_buffer_pct: float = STOP_BUFFER_PCT) -> Optional[dict]:
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

    try:
        from trading.risk_rules import ABS_MAX_STOP_PCT as _MAX
    except Exception:
        _MAX = 10.0

    return {
        "entry_low": round(float(lo), 2),
        "entry_high": round(float(hi), 2),
        "entry_ref": round(float(last_price), 2),
        "stop": stop,
        "risk_pct": risk_pct,
        "target": target,
        "reward_pct": reward_pct,
        "rr": rr,
        "risk_exceeds_max": bool(risk_pct is not None and risk_pct > _MAX),
        "max_stop_pct": _MAX,
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
    return min(eligible,
               key=lambda z: (distance(z), 0 if (z.get("hi") or 0) <= last_price else 1))


def _series_for_chart(df: pd.DataFrame, bars: int = 180) -> list[dict]:
    """Compact close series the FE draws the bands against."""
    tail = df.iloc[-bars:]
    out = []
    for idx, row in tail.iterrows():
        d = row.get("date") if "date" in tail.columns else idx
        try:
            ds = pd.Timestamp(d).strftime("%Y-%m-%d")
        except Exception:
            ds = str(d)[:10]
        out.append({"date": ds, "close": round(float(row["close"]), 2)})
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
                "bars_since_above": None, "in_band": False}

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
                      + (zones.get("demand_zones") or []))

    rec = {
        "symbol": sym,
        "name": company_names.name_for(sym) or sym,
        "last_price": last_price,
        "supply_zones": supply,
        "demand_zones": demand,
        "nearest_resistance": zones.get("nearest_resistance"),
        "nearest_support": zones.get("nearest_support"),
        "verdict": zones.get("verdict"),
        # The re-entry read.
        "in_demand_band": band["in_band"],
        "is_reentry": bool(band["is_reentry"] and trend_ok and quality_ok),
        "fell_from_pct": band["fell_from_pct"],
        "bars_since_above": band["bars_since_above"],
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
    if with_series:
        rec["series"] = _series_for_chart(df)
        # Detail view only: today's off-exchange prints, so the zone chart can
        # mark WHERE big size changed hands relative to the bands. Ajay
        # 2026-08-13: "Add the darkpool and order block details in to the
        # SEPA/Details tab". Best-effort — a failed tape pull just omits it.
        rec["venues"] = _session_venues(sym)
    return rec


def _session_venues(symbol: str) -> dict:
    """Today's (or the prior session's) venue split + large off-exchange
    blocks, each with the price it printed at."""
    from datetime import date as _d
    from orderflow import darkpool, quotes as quotes_mod, retail as retail_mod, tape as tape_mod

    out = {"available": False, "blocks": [], "rating": None}
    try:
        trades = tape_mod.fetch_trades(symbol, _d.today())
        if trades is None or trades.empty:
            trades = tape_mod.fetch_trades(symbol, _d.today() - timedelta(days=1))
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


def _attach_venues(rows: list, top_n: int = VENUE_DETAIL_TOP_N) -> None:
    """Add today's venue mix to the top `top_n` rows by R:R, in place."""
    from datetime import date as _d
    from orderflow import darkpool, quotes as quotes_mod, retail as retail_mod, tape as tape_mod

    ranked = sorted(rows, key=lambda r: -((r.get("plan") or {}).get("rr") or 0))
    for r in ranked[:top_n]:
        tape_is_today = True
        try:
            trades = tape_mod.fetch_trades(r["symbol"], _d.today())
            if trades is None or trades.empty:
                tape_is_today = False
                trades = tape_mod.fetch_trades(r["symbol"], _d.today() - timedelta(days=1))
            v = darkpool.split_venues(trades) if trades is not None else {"available": False}
            # Keep the LIST — `divergence` needs the blocks themselves. Only the
            # payload carries the count. Conflating the two silently broke the
            # retail read on every row that HAD blocks (len() on an int), which
            # is the opposite of the rows you would notice.
            block_list = darkpool.dark_blocks(trades) if trades is not None else []
        except Exception as exc:
            log.debug("demand-reentry: venue fetch failed for %s: %s", r["symbol"], exc)
            v, block_list = {"available": False}, []
        r["venues"] = {**v, "blocks": len(block_list),
                       "rating": _venue_rating(v.get("dark_pct"))}

        # Retail flow on the same tape. NBBO is what makes the SIGN usable —
        # sub-penny signing mis-signs 28% of trades (Barber et al. 2024), so
        # without quotes we report counts and no direction.
        try:
            nbbo = quotes_mod.fetch_quotes(r["symbol"], _d.today()) if tape_is_today else None
            rt = retail_mod.identify(trades, nbbo)
            r["retail"] = {**rt, "divergence": retail_mod.divergence(rt, block_list)}
        except Exception as exc:
            log.debug("demand-reentry: retail read failed for %s: %s", r["symbol"], exc)
            r["retail"] = {"available": False}

        # Live tape gives an ACCURATE today-volume for these rows, so fill in
        # the RVOL that _liquidity had to leave pending. Same fetch, no extra
        # cost. Projected to a full session when the day is still running.
        L = r.get("liquidity") or {}
        avg = L.get("avg_vol_50") or 0
        total = v.get("total_shares") or 0
        if avg > 0 and total > 0:
            # The fraction must follow the TAPE's day, not the daily bar's.
            # CENX had a complete prior-session bar (rvol_partial False) but
            # the tape was today's 80 minutes, so it went un-prorated and read
            # 0.10 against names that were prorated — not comparable.
            frac = _session_fraction() if tape_is_today else 1.0
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
UNIVERSES = {
    "sp500":  ("S&P 500", lambda: universe_mod.fetch_sp500()),
    "sp1500": ("S&P 1500 (500 + 400 mid + 600 small)", lambda: universe_mod.fetch_sp1500()),
    "sp400":  ("S&P 400 MidCap", lambda: universe_mod.fetch_sp400()),
    "sp600":  ("S&P 600 SmallCap", lambda: universe_mod.fetch_sp600()),
}
# Default universe. sp1500 since 2026-08-14 (Ajay: "make it default scan
# 1500") — the S&P 500 alone surfaced ~3 names at a tradeable R:R, the full
# 1500 surfaces ~12. Warmed by cron so the page load is instant, see crontab.
DEFAULT_UNIVERSE = "sp1500"


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
    parts = ["sp500", "sp400", "sp600"] if k == "sp1500" else [k]

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

    stale_ages = [(v or {}).get("age_days") or 0.0 for v in prov.values()
                  if v and v.get("source") == "stale-cache"]
    stale = int(round(max(stale_ages))) if stale_ages else None
    return syms, label, prov, stale, k


def scan(force: bool = False, limit: Optional[int] = None,
         universe: str = DEFAULT_UNIVERSE) -> dict:
    """Scan the S&P 500 for demand-zone re-entries. Cached `_CACHE_TTL_SEC`.

    Universe is `sepa.universe.fetch_sp500()`, which resolves fresh cache →
    Wikipedia → datahub mirror → STALE cache → curated. `universe_note`
    reports which list was actually used so the page can't quietly claim
    "S&P 500" over the wrong names.

    Staleness is reported too (2026-08-13). The curated fallthrough is loud —
    `universe_is_sp500` goes False and the UI warns — but a stale cache is
    silent by construction: it holds the real constituents, just frozen at
    the day the live fetch broke. Between 2026-05-29 and 2026-08-13 that list
    aged 76 days with nothing on the page saying so. `universe_stale_days`
    closes that hole.
    """
    ukey = _universe_key(universe)
    if not force:
        c = _cache.get(ukey)
        if c and (time.time() - c["ts"]) < _CACHE_TTL_SEC:
            return {**c["data"], "cached": True}

    t0 = time.time()
    syms, ulabel, uprov, ustale, ukey = _resolve_universe(ukey)
    # Provenance across every layer of the chosen universe. A record is only
    # trusted when it describes the list we actually got back — a stale record
    # from an earlier resolve, or a test double standing in for a fetcher,
    # must not mislabel it. sp1500 reports its WORST layer.
    curated_n = len(getattr(universe_mod, "UNIVERSE", []) or [])
    sources = [v.get("source") for v in uprov.values() if v]
    looks_curated = ("curated" in sources) or (len(syms) == curated_n and len(uprov) == 1)

    if looks_curated:
        universe_note = f"{ulabel} unavailable — scanned the curated list instead"
    elif ustale is not None:
        universe_note = (f"{ulabel} ({len(syms)} names) from a "
                         f"{int(ustale)}-day-old cached list — the live "
                         f"constituent fetch is failing")
    else:
        universe_note = f"{ulabel} ({len(syms)} names)"

    rows, scanned, errors = [], 0, 0
    for sym in syms:
        try:
            rec = analyze_symbol(sym)
        except Exception as exc:
            errors += 1
            log.debug("demand-reentry: %s failed: %s", sym, exc)
            continue
        if not rec:
            continue
        scanned += 1
        if rec["is_reentry"]:
            rec.pop("series", None)
            rows.append(rec)

    # Sorted by R:R descending (2026-08-13). The backtest found R:R >= 1.5 was
    # the ONLY cohort with positive expectancy, so the number that decides
    # whether a row is worth reading leads the list. Ties break on freshness.
    rows.sort(key=lambda r: (-((r.get("plan") or {}).get("rr") or 0.0), _rank_key(r)))
    if limit:
        rows = rows[:int(limit)]

    _attach_venues(rows)

    data = {
        "rows": rows,
        "n": len(rows),
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
    }
    _cache[ukey] = {"ts": time.time(), "data": data}
    log.info("demand-reentry: %d hits from %d scanned (%s) in %.1fs",
             len(rows), scanned, universe_note, data["took_sec"])
    return data
