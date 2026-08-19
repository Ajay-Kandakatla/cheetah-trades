"""Institutional volume around the earnings print.

Ajay 2026-08-19: *"I need a tracker on the Chart maps page a new tab.. Where it
tracks earnings that had huge instituonal volume. Like BULL for example and
TGT"*.

THE TWO NAMES ARE TWO DIFFERENT EVENTS, AND THAT SHAPED THE MODULE
-----------------------------------------------------------------
Checked before building, and they are not the same thing:

  TGT   next_date 2026-08-19, reported that morning. It GAPPED DOWN to 147.80
        from a 152.48 close, traded as low as 146.21, and closed at 159.00 on
        2.2x volume — institutions absorbing the gap and marking it up all day.
        A post-report REACTION.
  BULL  next_date 2026-08-19, `when: AMC`. It had not reported at all. The
        +8.95% on 3.1x volume was accumulation INTO a print that lands after
        the close. A pre-report RUN-UP.

He then asked for "current day only or next day earnings", which is exactly
those two halves. So the board has two groups and never blurs them: a name that
has already told the market its numbers is a different risk from one that has
not, and showing them in one undifferentiated list would hide the binary event
still ahead of the second group.

WHAT "INSTITUTIONAL" MEANS HERE
-------------------------------
Three conditions, all on the reaction bar, and each answers a different
question. A size test alone is not enough: VIK printed 2.37x volume on the same
day and closed at 0.01 of its range — enormous participation, and every bit of
it selling.

  1. PARTICIPATION — volume >= MIN_VOL_RATIO x the 60-day median.
     Median, not mean: one prior earnings bar in the window drags a mean up and
     quietly raises the bar for the next report.
  2. WHO WON THE DAY — the close sits in the top (1 - MIN_CLOSE_LOC) of the
     bar's own range. This is the discriminator. TGT 0.81 and BULL 0.92 both
     pass; VIK 0.01, TJX 0.30 and BILL 0.23 do not, and those are the names
     institutions were selling.
  3. SIZE — dollar volume >= MIN_DOLLAR_VOL. A ratio is scale-free, and
     scale-free is exactly wrong for a question about institutions: COTY
     cleared 1.7x on the same day having traded $47M, which no institution
     moved. Same $50M line as `demand_reentry.LIQ_DEEP_USD`, imported rather
     than re-typed.

BUILT ON THE EXISTING EARNINGS STACK, NOT BESIDE IT
---------------------------------------------------
Ajay 2026-08-19: *"We do have a earnings tracking component on the SEPA
dashboard and multiple places.. Look at that and see where it pulls stuff
from"*. Surveyed before writing a line of assembly:

  `sepa/earnings_watch.py`  the calendar — yfinance → Mongo `earnings_calendar`,
                            3,096 names with `when` (BMO/AMC). REUSED.
  `sepa/earnings_picks.py`  `reaction_read()` already anchors the reaction bar
                            correctly for BMO vs AMC. REUSED — that anchoring is
                            the one genuinely subtle thing here and a second
                            copy of it would drift.

What that stack does NOT answer, measured on the live doc rather than assumed:

  * it is a NIGHTLY doc (cron 19:10) and was 23 hours old when checked, so
    names that reported this morning — TGT, EL — could not be in it at all;
  * it has no size floor: 12 of its 21 picks traded >= $50M on the reaction
    bar, the rest being CAMP at $2M, DERM at $5M, AURA at $8M;
  * it RANKS by reaction %, so micro-caps win — CURI sat second at +42.5% on
    $81M while TGT ($1.5B) and EL ($1.33B) were absent entirely;
  * it has no close-location test, so a +8% gap that closes on its low passes
    every gate; and nothing anywhere reads volume BEFORE a report.

So this module adds exactly those four things and borrows the rest. The picks
list is deliberately left alone: it answers "what reacted well this week" for
three other pages, which is a different question from "where are institutions
right now".

RIDING INTO THE PRINT — HIS CALL, WITH THE RISK ON THE TILE
-----------------------------------------------------------
Ajay 2026-08-19: *"So pre earnings bullish momentum is also fine.. If
Institutions are coming in I want to ride along the momentum"*. So the UPCOMING
group ships. But `earnings_watch` exists in this codebase *because* ATEX passed
every technical gate, was bought, and reported that evening at -28% surprise —
so every upcoming tile states when the print lands (`reports_in`, and "tonight"
for an AMC report dated today). The tile does not argue with him; it makes the
binary event impossible to miss so the choice to hold through it is a choice.

BUYING ONLY — HIS EXPLICIT CHOICE (2026-08-19)
----------------------------------------------
Offered the mirror image (gap up, close on the low, institutions dumping into
the pop) and he chose buying only. The detector is therefore SIGNED: `up` is a
condition, not a sort. The distribution case is deliberately absent, not
accidentally missing — `is_institutional_buy` returning False for a 5x-volume
collapse is the intended answer, and `test_a_high_volume_COLLAPSE_is_not_a_buy`
pins it so a later "let's show both" edit has to be a decision.

NOT a book method. Configured house thresholds, measured on the 2026-08-19
tape. Decision support, not a buy signal, not advice.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("chart_maps.earnings")

# Volume against the bar's own 60-day median.
MIN_VOL_RATIO = 1.5

# Where the close sits inside the bar's range: 0 = on the low, 1 = on the high.
# 0.60 keeps TGT (0.81) and BULL (0.92) and rejects TJX (0.30) and BILL (0.23).
MIN_CLOSE_LOC = 0.60

# Institutions need size. Shared scale with the demand board / chart maps.
try:                                              # pragma: no cover - import shim
    from supply_demand.demand_reentry import LIQ_DEEP_USD as MIN_DOLLAR_VOL
except Exception:                                 # pragma: no cover
    MIN_DOLLAR_VOL = 50_000_000.0

# Bars of history needed before the median is a median.
MIN_BARS = 60

# Calendar window. Ajay 2026-08-19, after seeing UI on the first run at two
# sessions out: *"remove the ones that are coming not pre earning of same day
# earnings and institutions momemtum is there. I do not want to see those on
# the list."*
#
# So there is no look-ahead at all: a report must be TODAY to qualify, and the
# scored bar must be the latest session. Every tile on this board is today's
# bar — that is the whole rule, and it is what keeps the board readable at a
# glance instead of being a second copy of the rolling-week picks list.
#
# The look-BACK is not symmetric, and that is not an oversight: a report that
# landed after yesterday's close has its reaction bar TODAY, and that bar is
# exactly today's institutional action. Dropping it would hide every
# after-close reporter, which is most of them.
LOOKBACK_DAYS = 2
LOOKAHEAD_DAYS = 0

REACTED = "reacted"          # the numbers are out; this bar is the response
UPCOMING = "upcoming"        # reports today after the close, or next session


def _f(v) -> Optional[float]:
    """A finite float, or None.

    Deliberately strict about TYPE, not just value. `bool` is refused because
    `True >= 0.60` is True and a stray flag would pass the close-location gate
    as a real reading. Strings are refused for the same reason one step later:
    `float("10")` succeeds, so a price that arrived as text — a JSON field that
    changed shape, a CSV column that never got cast — would be silently
    accepted and this board would publish it as measured size. Every input here
    comes from a pandas frame or a Mongo number, so a string is evidence of an
    upstream bug, and the useful behaviour is to drop the row rather than
    launder it.
    """
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def close_location(high, low, close) -> Optional[float]:
    """Where the close sits in the bar's range. 1.0 = on the high.

    None for a zero-range bar rather than 0.5: a bar that never moved has no
    opinion about who won it, and inventing a neutral reading would let a
    halted or untraded session look like a normal one.
    """
    h, l, c = _f(high), _f(low), _f(close)
    if h is None or l is None or c is None or h < l:
        return None
    if h == l:
        return None
    return round((c - l) / (h - l), 4)


def volume_ratio(volume, median_volume) -> Optional[float]:
    v, m = _f(volume), _f(median_volume)
    if v is None or m is None or m <= 0 or v < 0:
        return None
    return round(v / m, 2)


def is_institutional_buy(bar: dict,
                         min_vol_ratio: float = MIN_VOL_RATIO,
                         min_close_loc: float = MIN_CLOSE_LOC,
                         min_dollar_vol: float = MIN_DOLLAR_VOL) -> bool:
    """Did institutions buy this bar? PURE.

    `bar` carries vol_ratio, close_loc, dollar_vol and change_pct. Every one
    must be present AND pass: an absent field is a fail, never a skip, because
    "we could not measure participation" and "participation was large" must not
    render as the same tile.
    """
    if not isinstance(bar, dict):
        return False
    vr, loc = _f(bar.get("vol_ratio")), _f(bar.get("close_loc"))
    dv, chg = _f(bar.get("dollar_vol")), _f(bar.get("change_pct"))
    if None in (vr, loc, dv, chg):
        return False
    return (vr >= min_vol_ratio and loc >= min_close_loc
            and dv >= min_dollar_vol and chg > 0)


def read_bar(df, median_lookback: int = MIN_BARS) -> Optional[dict]:
    """The last bar's institutional-footprint numbers. PURE w.r.t. the frame.

    Returns None when the frame is too short to have a median worth comparing
    against — a ratio computed over ten bars is not a participation measure.
    """
    if df is None or len(df) < median_lookback:
        return None
    try:
        r = df.iloc[-1]
        prev_close = _f(df["close"].iloc[-2])
        med = _f(df["volume"].tail(median_lookback).median())
        o, h, l, c = (_f(r["open"]), _f(r["high"]), _f(r["low"]), _f(r["close"]))
        v = _f(r["volume"])
        date = str(df.index[-1])[:10]
    except Exception:
        return None
    if None in (h, l, c, v) or prev_close in (None, 0):
        return None
    return {
        "date": date,
        "open": o, "high": h, "low": l, "close": c, "volume": v,
        "prev_close": prev_close,
        "vol_ratio": volume_ratio(v, med),
        "close_loc": close_location(h, l, c),
        "dollar_vol": round(c * v, 2),
        "change_pct": round((c / prev_close - 1) * 100, 2),
        "range_pct": round((h - l) / l * 100, 2) if l else None,
        # Negative when the bar opened BELOW the prior close. TGT's -3.07% gap
        # is the whole story of that tile: institutions bought a gap down.
        "gap_pct": round((o / prev_close - 1) * 100, 2) if o else None,
    }


def phase_for(cal: dict, bar_date: str, today: str) -> Optional[str]:
    """REACTED or UPCOMING for one name, from its calendar row. PURE.

    The distinction is NOT "did the date pass" — it is whether the market has
    seen the numbers yet, and an after-close report on today's date has not
    been seen by today's bar. That single rule is what separates TGT from BULL,
    and getting it backwards would put a name with a binary event still ahead
    of it on the same footing as one whose news is already priced.

    A report whose timing is unknown (`when` is null, as it is for TGT) is
    treated as ALREADY OUT once its date is today or past — the conservative
    read, since calling a released report "upcoming" would understate risk far
    less visibly than the reverse.
    """
    if not isinstance(cal, dict) or not bar_date or not today:
        return None
    nxt = str(cal.get("next_date") or "")[:10]
    when = (cal.get("when") or "").upper()
    last = str(((cal.get("last_report") or {}) or {}).get("date") or "")[:10]

    if nxt:
        if nxt > today:
            return UPCOMING                        # reports a later session
        if nxt == today:
            # After the close today → today's bar traded WITHOUT the numbers.
            return UPCOMING if when == "AMC" else REACTED
        # nxt < today: the date has passed, so the numbers are out.
        return REACTED
    if last and last <= today:
        return REACTED
    return None


def bar_metrics(df, k: int, median_lookback: int = MIN_BARS) -> Optional[dict]:
    """Institutional-footprint numbers for the bar at position `k`. PURE.

    Indexed rather than always-last because the two halves ask about different
    bars: the reacted half scores the REACTION bar (which `reaction_read`
    locates, and which is not today's bar for an AMC report), while the
    upcoming half scores the latest one. Computing both from `df.iloc[-1]`
    would silently mis-score every after-close reporter.

    The median window looks only at bars BEFORE `k` — including the bar being
    judged would let a 5x volume day raise its own bar.
    """
    if df is None or k is None:
        return None
    try:
        n = len(df)
    except Exception:
        return None
    if k < 1 or k >= n or k < median_lookback:
        return None
    try:
        r = df.iloc[k]
        prev_close = _f(df["close"].iloc[k - 1])
        med = _f(df["volume"].iloc[max(0, k - median_lookback):k].median())
        o, h, l, c = _f(r["open"]), _f(r["high"]), _f(r["low"]), _f(r["close"])
        v = _f(r["volume"])
        date = str(df.index[k])[:10]
    except Exception:
        return None
    if None in (h, l, c, v) or not prev_close:
        return None
    return {
        "date": date,
        "open": o, "high": h, "low": l, "close": c, "volume": v,
        "prev_close": prev_close,
        "vol_ratio": volume_ratio(v, med),
        "close_loc": close_location(h, l, c),
        "dollar_vol": round(c * v, 2),
        "change_pct": round((c / prev_close - 1) * 100, 2),
        "range_pct": round((h - l) / l * 100, 2) if l else None,
        # Negative when the bar OPENED below the prior close. TGT's gap down
        # is the whole story of that tile — institutions bought the gap.
        "gap_pct": round((o / prev_close - 1) * 100, 2) if o else None,
    }


def read_bar(df, median_lookback: int = MIN_BARS) -> Optional[dict]:
    """The latest bar's numbers — the upcoming half's reading."""
    try:
        return bar_metrics(df, len(df) - 1, median_lookback)
    except Exception:
        return None


def _calendar_rows(today: str) -> dict:
    """{SYMBOL: calendar doc} for names whose report is near `today`.

    Reads the SAME Mongo collection `earnings_watch` fills. No second fetcher:
    a private yfinance call here would double the rate-limit pressure on the
    module that owns this data and could disagree with it.
    """
    try:
        from sepa import earnings_watch
        coll = earnings_watch._coll()
        if coll is None:
            return {}
    except Exception as exc:
        log.warning("earnings tiles: calendar unavailable: %s", exc)
        return {}
    from datetime import date, timedelta
    try:
        y, m, d = (int(x) for x in str(today)[:10].split("-"))
        t0 = date(y, m, d)
    except Exception:
        return {}
    # A window either side: reports dated a few days back can still have their
    # reaction bar as the latest session, and the upcoming half needs the days
    # ahead. Kept small deliberately — this board is about NOW.
    lo = (t0 - timedelta(days=LOOKBACK_DAYS)).isoformat()
    hi = (t0 + timedelta(days=LOOKAHEAD_DAYS)).isoformat()
    q = {"$or": [{"next_date": {"$gte": lo, "$lte": hi}},
                 {"last_report.date": {"$gte": lo, "$lte": hi}}]}
    try:
        return {d["_id"]: d for d in coll.find(q) if d.get("_id")}
    except Exception as exc:
        log.warning("earnings tiles: calendar query failed: %s", exc)
        return {}


def scan(today: Optional[str] = None, min_vol_ratio: float = MIN_VOL_RATIO,
         min_close_loc: float = MIN_CLOSE_LOC,
         min_dollar_vol: float = MIN_DOLLAR_VOL) -> dict:
    """Both halves of the board. Impure: reads Mongo + the price cache.

    Returns `{"reacted": [...], "upcoming": [...], ...}` — never one merged
    list. A name that has already told the market its numbers and one that has
    not are different risks, and the tab keeps them apart for that reason.
    """
    import time as _time
    t0 = _time.time()
    from sepa import prices, earnings_picks

    d = str(today or _et_today())[:10]
    cal = _calendar_rows(d)
    reacted, upcoming, checked, skipped = [], [], 0, 0

    for sym, row in cal.items():
        try:
            df = prices.load_prices(sym)
        except Exception:
            df = None
        if df is None or len(df) < MIN_BARS:
            skipped += 1
            continue
        checked += 1
        last_bar = str(df.index[-1])[:10]
        phase = phase_for(row, last_bar, d)
        if phase is None:
            continue

        if phase == REACTED:
            # Anchor on the SHARED reader so the reaction bar is located the
            # same way the picks list locates it.
            rpt = str(row.get("next_date") or
                      ((row.get("last_report") or {}) or {}).get("date") or "")[:10]
            rr = earnings_picks.reaction_read(df, rpt, row.get("when")) if rpt else None
            if not rr:
                continue
            rdate = rr.get("reaction_date")
            try:
                import pandas as pd
                k = int(df.index.searchsorted(pd.Timestamp(rdate), side="left"))
            except Exception:
                continue
            m = bar_metrics(df, k)
            if not m or m["date"] != rdate:
                continue
            # Today's bar only. A reaction from two sessions ago is history,
            # and history is what `earnings_picks` already lists elsewhere.
            if m["date"] != last_bar:
                continue
            if not is_institutional_buy(m, min_vol_ratio, min_close_loc, min_dollar_vol):
                continue
            reacted.append({
                "symbol": sym, "phase": REACTED, "report_date": rpt,
                "when": row.get("when"),
                "surprise_pct": ((row.get("last_report") or {}) or {}).get("surprise_pct"),
                "drift_since_pct": rr.get("drift_since_pct"),
                "still_above_pre": rr.get("still_above_pre"),
                **m,
            })
        else:
            m = read_bar(df)
            if not m:
                continue
            if not is_institutional_buy(m, min_vol_ratio, min_close_loc, min_dollar_vol):
                continue
            nxt = str(row.get("next_date") or "")[:10]
            when = (row.get("when") or "").upper()
            # Same-day prints only. A report two sessions out is not "the
            # institutions are coming in ahead of THIS print" — it is a name
            # that happens to be strong, which the scanner already covers.
            if nxt != d:
                continue
            # Today's bar, or it is not today's momentum.
            if m["date"] != last_bar:
                continue
            upcoming.append({
                "symbol": sym, "phase": UPCOMING, "report_date": nxt,
                "when": row.get("when"),
                "eps_estimate": row.get("eps_estimate"),
                # The sentence the tile shows. "tonight" is not decoration: an
                # AMC report dated today means the position spans the print
                # before the next open — the ATEX case exactly.
                "reports_in": ("tonight, after the close" if when == "AMC"
                               else "today, timing unconfirmed"),
                **m,
            })

    # Strongest institutional footprint first. Dollar volume, not percentage
    # move — the question this board answers is "where is the size", and a
    # micro-cap doubling on $2M is exactly what the ranking must not reward.
    reacted.sort(key=lambda r: -(r.get("dollar_vol") or 0))
    upcoming.sort(key=lambda r: -(r.get("dollar_vol") or 0))
    return {
        "reacted": reacted,
        "upcoming": upcoming,
        "as_of": d,
        "checked": checked,
        "skipped": skipped,
        "calendar_names": len(cal),
        "criteria": {
            "min_vol_ratio": min_vol_ratio,
            "min_close_loc": min_close_loc,
            "min_dollar_vol": min_dollar_vol,
            "gates": ("volume >= %.1fx the 60-day MEDIAN, close in the top %d%% "
                      "of the bar's range, >= $%.0fM traded, and up on the day"
                      % (min_vol_ratio, round((1 - min_close_loc) * 100),
                         min_dollar_vol / 1e6)),
            "direction": "buying only — distribution is deliberately not shown",
        },
        "took_sec": round(_time.time() - t0, 1),
    }


def _et_today() -> str:
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().astimezone().strftime("%Y-%m-%d")
