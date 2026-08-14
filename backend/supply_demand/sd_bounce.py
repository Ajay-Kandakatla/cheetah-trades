"""Which stocks BOUNCE when they enter a demand zone — a per-symbol study.

Ajay 2026-08-14: "test data to see historically that had quick bounces as they
entered demand zones… Try to test all the 1500 stocks and tell me which ones
bounce back quickly. That will [mean] there are limit orders."

The hypothesis is sound and it is the right thing to measure. A resting bid is
invisible — you cannot see the book (no L2 on our data, and stops are broker
conditionals that exist nowhere until they fire). But a bid that is really
there leaves a footprint: price arrives at the level and **turns quickly**. A
level with nothing behind it gets absorbed and drifts through.

So this measures the footprint, per name, over history:

    when this stock entered a demand band, how often did it turn within
    `BOUNCE_LOOKAHEAD_BARS` bars, and how fast?

This is a DIFFERENT question from `sd_backtest.py`. That one asked "does the
strategy make money" (answer: no edge). This one asks "which names respect
their own levels" — a character statistic. A name can bounce reliably and
still be untradeable if the bounce is smaller than the spread, so the output
carries bounce SIZE alongside bounce RATE and neither is presented alone.

NO LOOKAHEAD
------------
Zones are recomputed at anchors every `ANCHOR_STEP_BARS`, using only bars up
to that anchor. Entry events are then detected in the `ANCHOR_STEP_BARS` that
FOLLOW it, and outcomes are walked forward from the bar after the event.
Nothing about a band is derived from the price action it is used to judge.
`test_zones_never_see_the_bars_they_are_judged_on` locks it.

WHAT COUNTS AS A BOUNCE
-----------------------
From the close that enters the band: price closes `BOUNCE_PCT` above the entry
close within `BOUNCE_LOOKAHEAD_BARS`, WITHOUT first closing below the band
floor by more than `BREAK_BUFFER_PCT`. Breaking the floor first is a failed
zone, not a slow bounce — counting it either way would flatter the result.

All thresholds are CONFIGURED HOUSE VALUES. Not a book method. Not advice.
A high historical bounce rate is a description of the past, not a promise.
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from . import price_zones, demand_reentry as dr

log = logging.getLogger("supply_demand.sd_bounce")

ANCHOR_STEP_BARS      = 21     # recompute zones ~monthly
BOUNCE_LOOKAHEAD_BARS = 5      # "quick" = within a trading week
BOUNCE_PCT            = 2.0    # a real turn, not a tick
BREAK_BUFFER_PCT      = 1.0    # closing this far under the floor = zone failed
MIN_HISTORY_BARS      = 300
MIN_EVENTS            = 4      # below this a "rate" is noise
MIN_TOUCHES           = 2      # only bands that were real support

DISCLAIMER = (
    "Historical bounce behaviour at demand bands, per symbol. A fast turn is "
    "consistent with resting bids but does not prove them — the book is not "
    "observable. Past behaviour of a level is not a forecast. Not advice."
)


def bounce_outcome(closes: list, entry_i: int, band_lo: float,
                   lookahead: int = BOUNCE_LOOKAHEAD_BARS,
                   bounce_pct: float = BOUNCE_PCT,
                   break_buffer_pct: float = BREAK_BUFFER_PCT) -> dict:
    """Did price turn from `entry_i` before losing the band? PURE.

    Returns {bounced, bars_to_bounce, max_gain_pct, broke}.
    """
    out = {"bounced": False, "bars_to_bounce": None,
           "max_gain_pct": None, "broke": False}
    n = len(closes)
    if entry_i < 0 or entry_i >= n - 1 or not band_lo:
        return out
    entry = float(closes[entry_i])
    if entry <= 0:
        return out
    floor_ = band_lo * (1 - break_buffer_pct / 100.0)

    best = 0.0
    for k in range(1, lookahead + 1):
        j = entry_i + k
        if j >= n:
            break
        c = float(closes[j])
        gain = (c / entry - 1) * 100.0
        best = max(best, gain)
        if c < floor_:                      # lost the band first -> failed zone
            out["broke"] = True
            out["max_gain_pct"] = round(best, 2)
            return out
        if gain >= bounce_pct:
            out.update({"bounced": True, "bars_to_bounce": k,
                        "max_gain_pct": round(best, 2)})
            return out
    out["max_gain_pct"] = round(best, 2)
    return out


def study_symbol(df: pd.DataFrame, symbol: str = "",
                 min_history: int = MIN_HISTORY_BARS) -> Optional[dict]:
    """Bounce statistics for one name across its available history.

    `min_history` is the warm-up before the first anchor — it must be long
    enough for price_zones to find real swing structure. The split-sample
    persistence test lowers it, because half of a history is by definition
    half as long; at the default it produced ZERO usable names."""
    if df is None or len(df) < min_history:
        return None
    closes = [float(c) for c in df["close"].tolist()]
    n = len(closes)

    events = []
    anchor = min_history
    while anchor < n - 1:
        hist = df.iloc[:anchor + 1]                    # bars up to the anchor ONLY
        try:
            z = price_zones.compute(hist, **dr.zone_geom())
        except Exception:
            z = None
        if z:
            bands = [b for b in (z.get("demand_zones") or [])
                     if (b.get("touches") or 0) >= MIN_TOUCHES]
            # entries in the window AFTER the anchor
            end = min(n, anchor + ANCHOR_STEP_BARS)
            for i in range(anchor + 1, end):
                prev, cur = closes[i - 1], closes[i]
                for b in bands:
                    lo, hi = b.get("lo") or 0.0, b.get("hi") or 0.0
                    if hi <= lo:
                        continue
                    # ENTERING the band from above — the transition, not
                    # sitting inside it for days on end.
                    if prev > hi >= cur >= lo:
                        r = bounce_outcome(closes, i, lo)
                        events.append({"i": i, "band_lo": lo, "band_hi": hi,
                                       "touches": b.get("touches"), **r})
                        break
        anchor += ANCHOR_STEP_BARS

    if not events:
        return {"symbol": symbol, "events": 0}

    bounced = [e for e in events if e["bounced"]]
    broke = [e for e in events if e["broke"]]
    days = [e["bars_to_bounce"] for e in bounced if e["bars_to_bounce"]]
    gains = sorted(e["max_gain_pct"] for e in events if e["max_gain_pct"] is not None)
    med_gain = gains[len(gains) // 2] if gains else None
    return {
        "symbol": symbol,
        "events": len(events),
        "bounced": len(bounced),
        "bounce_rate_pct": round(100.0 * len(bounced) / len(events), 1),
        "broke": len(broke),
        "break_rate_pct": round(100.0 * len(broke) / len(events), 1),
        "median_bars_to_bounce": (sorted(days)[len(days) // 2] if days else None),
        "median_max_gain_pct": med_gain,
        "avg_max_gain_pct": round(sum(gains) / len(gains), 2) if gains else None,
    }


def run(symbols: list, min_events: int = MIN_EVENTS) -> dict:
    """Study every symbol and rank by how reliably it turns at demand."""
    from sepa import prices

    rows, skipped = [], 0
    for sym in symbols:
        try:
            df = prices.load_prices(sym, period="2y")
        except Exception:
            df = None
        if df is None or len(df) < MIN_HISTORY_BARS:
            skipped += 1
            continue
        df = df.rename(columns={c: str(c).lower() for c in df.columns})
        try:
            rec = study_symbol(df, sym)
        except Exception as exc:
            log.debug("bounce: %s failed: %s", sym, exc)
            skipped += 1
            continue
        if rec and rec.get("events", 0) >= min_events:
            rows.append(rec)

    # Reliability first, then speed, then size — a fast small bounce and a slow
    # big one are different animals and the caller can see both.
    rows.sort(key=lambda r: (-(r["bounce_rate_pct"] or 0),
                             (r["median_bars_to_bounce"] or 99),
                             -(r["median_max_gain_pct"] or 0)))
    universe_rate = (round(sum(r["bounced"] for r in rows) * 100.0
                           / max(1, sum(r["events"] for r in rows)), 1) if rows else None)
    return {
        "rows": rows, "n": len(rows), "skipped": skipped,
        "universe_bounce_rate_pct": universe_rate,
        "params": {
            "anchor_step_bars": ANCHOR_STEP_BARS,
            "bounce_lookahead_bars": BOUNCE_LOOKAHEAD_BARS,
            "bounce_pct": BOUNCE_PCT,
            "break_buffer_pct": BREAK_BUFFER_PCT,
            "min_events": min_events, "min_touches": MIN_TOUCHES,
        },
        "disclaimer": DISCLAIMER,
    }


# ── Persistence: is a high bounce rate a CHARACTER, or was it luck? ──────────
# With ~1,000 names studied and only ~10 events each, the top of any ranking is
# where noise concentrates: at a 47% base rate you expect a handful of names to
# print 85%+ by chance alone. A per-name binomial p-value does not fix this —
# it is a multiple-comparisons problem, and Bonferroni at 0.05/1081 kills every
# name at n=10.
#
# The test that actually answers Ajay's question ("which ones bounce back
# quickly", implying a stable property) is out-of-sample persistence: rank on
# the FIRST half of history, then measure the SECOND half. If the top names
# keep bouncing more than the bottom names, the property is real and tradeable.
# If the gap collapses, the ranking was noise and no per-name list is worth
# acting on — including the pretty one this module prints.
def persistence(symbols: list, min_events_each_half: int = 3,
                period: str = "5y", half_min_bars: int = 250) -> dict:
    """Split-sample test. Rank on the first half, score on the second.

    Needs a LONG frame: each half must still hold enough bars for zone
    structure plus several anchors. At period="2y" every half fell under the
    300-bar warm-up and the test returned zero names."""
    from sepa import prices

    pairs = []
    for sym in symbols:
        try:
            df = prices.load_prices(sym, period=period)
        except Exception:
            continue
        if df is None or len(df) < 2 * half_min_bars:
            continue
        df = df.rename(columns={c: str(c).lower() for c in df.columns})
        mid = len(df) // 2
        try:
            a = study_symbol(df.iloc[:mid], sym, min_history=half_min_bars)
            b = study_symbol(df.iloc[mid:], sym, min_history=half_min_bars)
        except Exception:
            continue
        if not a or not b:
            continue
        if a.get("events", 0) < min_events_each_half or b.get("events", 0) < min_events_each_half:
            continue
        pairs.append({"symbol": sym,
                      "first_rate": a["bounce_rate_pct"], "first_n": a["events"],
                      "second_rate": b["bounce_rate_pct"], "second_n": b["events"]})

    if len(pairs) < 20:
        return {"n": len(pairs), "verdict": "too few names with data in both halves"}

    ranked = sorted(pairs, key=lambda p: -p["first_rate"])
    q = max(1, len(ranked) // 4)
    top, bottom = ranked[:q], ranked[-q:]

    def _w(group):   # event-weighted, so a 1-event name cannot swing it
        num = sum(p["second_rate"] * p["second_n"] for p in group)
        den = sum(p["second_n"] for p in group)
        return round(num / den, 1) if den else None

    top_second, bot_second = _w(top), _w(bottom)
    gap = (round(top_second - bot_second, 1)
           if top_second is not None and bot_second is not None else None)

    # Spearman-ish: plain Pearson on ranks, no scipy in this image.
    n = len(ranked)
    r1 = {p["symbol"]: i for i, p in enumerate(sorted(pairs, key=lambda p: -p["first_rate"]))}
    r2 = {p["symbol"]: i for i, p in enumerate(sorted(pairs, key=lambda p: -p["second_rate"]))}
    d2 = sum((r1[s] - r2[s]) ** 2 for s in r1)
    rho = round(1 - (6 * d2) / (n * (n * n - 1)), 3) if n > 2 else None

    return {
        "n": n,
        "top_quartile_second_half_pct": top_second,
        "bottom_quartile_second_half_pct": bot_second,
        "gap_pct": gap,
        "rank_correlation": rho,
        "verdict": ("persistent" if (gap or 0) >= 5 and (rho or 0) >= 0.15
                    else "not persistent — the ranking does not survive out of sample"),
        "pairs": pairs,
    }
