"""Multi-timeframe frames for the zone engine.

Ajay 2026-08-29: "can do this in Daily, Market hourly, 15 mins time charts
... For supply and demand zone".

Every zone surface in this app reads DAILY bars. The same swing-cluster
rule run on 15-minute or hourly bars answers a different question — where
is the level *this session's* trade is standing on — and that is the one
an intraday entry needs. Nothing about the zone methodology changes here;
only the frame it reads.

Sources (both already in the app, no new provider):
  * daily  — sepa.prices.load_prices (Massive daily, parquet/Mongo cached)
  * 60m/15m — daytrading.data.load_intraday_range (Massive 1-minute bars,
    Mongo-cached per completed day) resampled with a right-closed,
    right-labelled OHLCV aggregation so a bar is stamped at the time it
    CLOSES, which is when its high/low become tradeable facts.

Session policy for intraday frames: RTH only. Pre-market prints are thin
and gappy, and a swing low made on 400 shares at 07:12 is not a level
anyone defended — including it would manufacture zones out of noise.

Bar budgets are per timeframe, not shared: 15m RTH has 26 bars a day, 60m
has 7, so "60 bars of structure" is 2.5 sessions on the 15m and 9 on the
hourly. Hourly buckets are CLOCK-anchored (labels 10:00, 11:00 … 16:00 ET),
so the FIRST hourly bar of a session (09:30–10:00) is the half hour and the
remaining six are full hours — not open-anchored 10:30/11:30 bars. The
dropdown labels state the real calendar span so the zoom is never ambiguous.

The last bucket of an intraday frame is usually IN PROGRESS. `frame_for`
stamps `as_of` with the last raw minute actually seen (never the bucket's
future close label) and sets `partial` so a consumer can keep that bucket
out of its structure (2026-09-05, Ajay: "yes please fix the bugs").

FIVE FRAMES, NAMED BY THE JOB (Ajay 2026-09-22)
───────────────────────────────────────────────
> "Once done can you add a 24 hour window for me on the supply demand chart
>  please. I am tired of the pre live post.. It give me for an entire week
>  with lil candles. I mainly need the support levels for the last 24 hours
>  ... even if Pre post I am not expecting to see Sept 15 why do I need the
>  look at the drop down" … "Just simpliyfy this drop down. I wanna use this
>  for entries during the day and it been useless for that."

Six frames became five, and every label now names the QUESTION rather than
the bar size, with the span carried beside it so the answer is readable
without opening the dropdown.

  * `24h` is NEW and is the only TIME-windowed frame in the module. Every
    other frame is a BAR-COUNT budget, and a bar count makes the span a
    function of LIQUIDITY: measured 2026-09-22, the retired `5m_live`'s
    480-bar budget drew 3 sessions of NVDA and 5 of PTGX (2026-09-16 →
    09-22) under one label claiming "~2.5 sessions". PTGX barely prints
    outside RTH, so the same budget reaches further back. A 24-HOUR slice
    is true for a thin name and a liquid one alike.
  * `15m_open` RETIRED → `15m`. Its 26-bar session budget is too thin to
    cluster: measured 2026-09-22, PTGX and NVDA both returned NO support
    band at all on it. `5m_today` answers the same "today only, no previous
    days" question with 192 bars. The alias points at `15m` rather than
    `5m_today` because `15m` is the nearest key that resolves on EVERY
    surface — the extended-hours frames are refused by the structure
    endpoints below, so an old `?tf=15m_open` bookmark on /zones would
    start erroring.
  * `5m_live` RETIRED → `24h`. Same bar size, same pre/post policy, a span
    that is true. Both keys are extended-hours and therefore Support-tab
    only, so the alias adds no new refusal anywhere.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

log = logging.getLogger("supply_demand.timeframes")

DAILY = "daily"
H1 = "60m"
M15 = "15m"
M5_TODAY = "5m_today"
H24 = "24h"

# RETIRED 2026-09-22. The constants stay so an old import keeps working and
# so `RETIRED` can be read as a table; neither key is in `TIMEFRAMES` any
# more, and `parse_tf` resolves both (see the module header for the reason
# each one points where it does).
M15_OPEN = "15m_open"
M5_LIVE = "5m_live"
RETIRED: dict[str, str] = {M15_OPEN: M15, M5_LIVE: H24}


def _span(bar_label: str, window_label: str) -> str:
    """The one sentence the dropdown prints beside a frame's job name.

    Ajay 2026-09-22: "why do I need the look at the drop down" — the span
    has to be readable WITHOUT opening the option, so it is built from the
    two facts that decide it, never written twice."""
    return f"{bar_label} bars · {window_label}"


# `bars` is what the zone engine reads; `days` is the calendar fetch span.
# swing_window shrinks intraday on purpose — a 3-bar swing on a 15m chart
# is 45 minutes, which is already a real intraday pivot; the daily default
# of 4-5 would find two levels a session and call the chart structureless.
#
# `label` names the JOB, `bar_label` the bar size, `window_label` the span.
# The sentences in chart_maps.support read `bar_label`, never `label`: a
# header saying "79 x Today, for an entry bars" would be nonsense.
#
# ORDER IS SHORTEST FIRST (2026-09-22). "I wanna use this for entries during
# the day" — the frame he reaches for most is the one at the top. DEFAULT_TF
# is still `daily`, so nothing opens on a different frame than it used to.
TIMEFRAMES: tuple[dict, ...] = (
    # Ajay 2026-09-17: "For the live 5 min chart data, can you make sure its
    # only showing from todays open only. it going till 6 months." Asked where
    # the day starts, he said "Today 04:00 ET — incl. pre-market".
    #
    # THIS IS THE FRAME THAT ANSWERS his 2026-09-22 fallback ask, "support
    # level from market open but I do not have to see previous days in that".
    #
    # Bar budget: the extended session runs 04:00-20:00 ET = 16 hours =
    # 16 × 60 = 960 minutes; at 5 minutes a bar that is 960 / 5 = 192 buckets.
    # 192 is therefore the whole day and never clips his morning — the frame
    # is clipped to today's ET date first, so `tail(192)` is a no-op by
    # construction rather than a cut.
    {"key": M5_TODAY, "label": "Today, for an entry",
     "bar_label": "5-minute", "window_label": "today only, from 04:00 ET",
     "bars": 192, "days": 1, "swing_window": 2, "rule": "5min",
     "ext_hours": True, "orb_minutes": 5},
    # Ajay 2026-09-22: "can you add a 24 hour window for me on the supply
    # demand chart please ... I mainly need the support levels for the last
    # 24 hours to see the support".
    #
    # THE ONLY TIME-WINDOWED FRAME IN THIS MODULE. `bars` is a CEILING, not
    # the budget: 24 h × 12 buckets an hour = 288, which is what a 5-minute
    # grid can hold in a day, so `tail(288)` is a no-op after the slice. The
    # slice itself is by CLOCK (see `frame_for`), which is the whole point —
    # a bar count would hand a thin name six sessions and a liquid one two
    # and a half under the same label, which is the defect this replaces.
    #
    # `days: 3` is the same calendar fetch the retired `5m_live` paid for, so
    # provider load per tab is unchanged.
    {"key": H24, "label": "Last 24 hours",
     "bar_label": "5-minute",
     "window_label": ("the 24 hours up to the last print, pre-market "
                      "through after-hours"),
     "bars": 288, "days": 3, "swing_window": 2, "rule": "5min",
     "ext_hours": True, "orb_minutes": 5},
    {"key": M15, "label": "The last two weeks",
     "bar_label": "15-minute", "window_label": "the last ~10 sessions",
     "bars": 260, "days": 15, "swing_window": 2, "orb_minutes": 15},
    # 330 bars ≈ 47 sessions ≈ 9 weeks — deliberately wide enough that
    # Bulkowski's minimum cup ("7 weeks" = 245 hourly bars) can actually
    # form. A shorter budget would make the cup detector silently barren
    # on this timeframe and look like a bug.
    {"key": H1, "label": "The last two months",
     "bar_label": "1-hour", "window_label": "the last ~47 sessions",
     "bars": 330, "days": 70, "swing_window": 3, "orb_minutes": 60},
    # Ajay 2026-09-22: "It does help with 6 months". The daily frame is the
    # only one whose span the Zoom dropdown still sets, so the span text
    # says so instead of asserting a number the Zoom can contradict.
    {"key": DAILY, "label": "The big picture",
     "bar_label": "daily",
     "window_label": "1 year by default — the Zoom dropdown sets how far back",
     "bars": 252, "days": 0, "swing_window": 4, "orb_minutes": 30},
)

for _t in TIMEFRAMES:                       # one span sentence, built once
    _t["span"] = _span(_t["bar_label"], _t["window_label"])
del _t

DEFAULT_TF = DAILY
_BY_KEY = {t["key"]: t for t in TIMEFRAMES}

# Aliases so a URL can say what a human would type. The RETIRED keys are
# folded in LAST so an old bookmark resolves instead of erroring.
_ALIAS = {"1d": DAILY, "d": DAILY, "day": DAILY, "1day": DAILY,
          "1h": H1, "h": H1, "hour": H1, "hourly": H1, "60min": H1,
          "15": M15, "15min": M15, "m15": M15, "15m": M15,
          # `open`/`session` used to mean "today's RTH session on 15-minute
          # bars". They follow `15m_open` to `15m` for the same reason: the
          # structure endpoints refuse an extended-hours frame.
          "open": M15, "session": M15, "15open": M15,
          "5m": H24, "5min": H24, "live": H24, "5m_ext": H24,
          "24": H24, "h24": H24, "24hr": H24, "24hour": H24, "last24": H24,
          "5m_today": M5_TODAY, "5today": M5_TODAY, "today": M5_TODAY,
          "5m_day": M5_TODAY, "5m_open": M5_TODAY, "5open": M5_TODAY,
          **RETIRED}


def parse_tf(raw) -> str:
    """Any user-supplied timeframe → a supported key. Unknown → daily: the
    surfaces all worked on daily before this module existed, so that is the
    one fallback that cannot surprise anyone."""
    if not isinstance(raw, str):
        return DEFAULT_TF
    k = raw.strip().lower()
    if k in _BY_KEY:
        return k
    return _ALIAS.get(k, DEFAULT_TF)


def tf_spec(key: str) -> dict:
    return _BY_KEY[parse_tf(key)]


def tf_options(include_live: bool = False) -> list:
    """Dropdown payload for the FE.

    The extended-hours frames (`5m_today`, `24h`) are HIDDEN by default:
    their bars include pre/post market, and the zone engine must never read
    swings off a 07:12 print on 400 shares (module docstring). Only the
    Support tab — which passes `allow_ext=True` and draws them — asks for
    them, and `frame_for` refuses them everywhere else.

    `bar_label` and `span` ride along so the FE can print the bar size and
    the span beside the job name without knowing this table (Ajay
    2026-09-22: he must be able to tell the span without opening the
    option).
    """
    return [{"key": t["key"], "label": t["label"], "span": t["span"],
             "bar_label": t["bar_label"], "window_label": t["window_label"],
             "bars": t["bars"]} for t in TIMEFRAMES
            if include_live or not t.get("ext_hours")]


def resample_ohlcv(df, rule: str):
    """1-minute bars → `rule` bars, stamped at the time the bar CLOSES.

    LEFT-closed, RIGHT-labelled: the bar stamped 09:45 holds the minutes
    09:30-09:44. Closing the interval on the right instead looks equivalent
    and is not — it puts the session's opening minute in a bucket of its
    own, so every session would start with a one-minute bar wearing a
    15-minute label, and that orphan is exactly the kind of fake extreme
    the swing and gap detectors would treat as structure.

    Empty buckets (lunch lulls, halts, the overnight gap between sessions)
    are dropped rather than forward filled — a bar that never traded is not
    a bar, and painting one would invent a level nobody defended."""
    if df is None or df.empty:
        return None
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "volume" in df.columns:
        agg["volume"] = "sum"
    # The per-minute session tag (premarket / rth / afterhours) survives the
    # resample so the live chart can shade extended hours. Safe because every
    # session boundary (04:00, 09:30, 16:00, 20:00 ET) sits on a 5- and
    # 15-minute grid, so no bucket straddles two sessions.
    if "session" in df.columns:
        agg["session"] = "first"
    out = df.resample(rule, label="right", closed="left").agg(agg)
    return out.dropna(subset=["open", "high", "low", "close"])


def intraday_raw(symbol: str, tf: str = M15):
    """The 1-minute bars `frame_for` would fetch for `tf`, or None.

    Exposed 2026-08-31 so a caller needing BOTH the resampled frame and the raw
    minutes (the session board wants the frame for structure and the raw for
    the opening range) pays for one fetch instead of two. Fetching twice was
    doubling today's live requests per symbol and drawing Massive read timeouts
    at 10 workers.
    """
    spec = tf_spec(tf)
    if spec["key"] == DAILY:
        return None
    try:
        from daytrading.data import load_intraday_range
    except Exception as exc:                                # pragma: no cover
        log.warning("timeframes: daytrading.data unavailable: %s", exc)
        return None
    end = date.today()
    start = end - timedelta(days=int(spec["days"]) + 4)      # weekend padding
    ext = bool(spec.get("ext_hours"))
    try:
        return load_intraday_range(symbol, start, end, include_premarket=ext,
                                   include_afterhours=ext)
    except Exception as exc:
        log.warning("timeframes: intraday fetch for %s failed: %s", symbol, exc)
        return None


def frame_for(symbol: str, tf: str = DEFAULT_TF, *,
              bars: Optional[int] = None, raw=None,
              allow_ext: bool = False) -> tuple:
    """(df, meta) for one symbol at one timeframe.

    df is a DataFrame indexed by timestamp with open/high/low/close[/volume],
    trimmed to the timeframe's bar budget. meta always answers, even on a
    miss, so the caller can keep rendering its controls:
      {tf, label, span, bars, available, source, as_of, reason}
    """
    spec = tf_spec(tf)
    key = spec["key"]
    want = int(bars or spec["bars"])
    meta = {"tf": key, "label": spec["label"], "span": spec["span"],
            "bar_label": spec["bar_label"],
            "bars": 0, "available": False, "source": None, "as_of": None,
            "swing_window": spec["swing_window"], "reason": None}
    sym = (symbol or "").upper().strip()
    if not sym:
        meta["reason"] = "no symbol"
        return None, meta

    if key == DAILY:
        try:
            from chart_maps.support import _frame_for as daily_frame
            df, have, as_of = daily_frame(sym, want)
        except Exception as exc:
            log.warning("timeframes: daily frame for %s failed: %s", sym, exc)
            meta["reason"] = "daily bars unavailable"
            return None, meta
        if df is None or not have:
            meta["reason"] = "no daily bars"
            return None, meta
        df = df.tail(want)
        meta.update({"bars": len(df), "available": True,
                     "source": "daily bars", "as_of": as_of})
        return df, meta

    # Intraday: 1-minute bars over the calendar span, then resample. `raw` lets
    # a caller hand in bars it already holds (see `intraday_raw`) so the fetch
    # is not paid for twice.
    if spec.get("ext_hours") and not allow_ext:
        # Guard rail: an extended-hours frame reaching price_zones would
        # manufacture zones out of thin overnight prints. The one caller
        # that legitimately wants these bars (chart_maps.support, for
        # DRAWING only) passes allow_ext=True.
        meta["reason"] = ("the live pre/post-market frame is a chart frame, "
                          "not a structure frame")
        return None, meta
    if raw is None:
        raw = intraday_raw(sym, key)
    if raw is None or raw.empty:
        meta["reason"] = ("no intraday bars — Massive serves minute data for "
                          "liquid US equities only")
        return None, meta

    rule = spec.get("rule") or ("60min" if key == H1 else "15min")
    df = resample_ohlcv(raw, rule)
    if df is None or df.empty:
        meta["reason"] = "resample produced no bars"
        return None, meta

    if key in (M5_TODAY, H24):
        # THE ONE CLOCK-SLICE BLOCK. Both frames that answer "no previous
        # days" are cut here, off the SAME ET conversion, so there is one
        # place where a timezone can be got wrong rather than two.
        #
        # `5m_today` slices by ET CALENDAR DATE and lands on today
        # 04:00-20:00 ET, the pre-market-included day Ajay asked for
        # (2026-09-17). Before the first bar of a new day that is the
        # previous day's session, which is the honest answer — inventing an
        # empty frame for a day that has not opened would be worse than
        # showing the one that just closed, and the label says which day.
        #
        # `24h` slices by CLOCK (2026-09-22), anchored on the LAST BAR
        # PRESENT rather than on wall-clock now(). Anchoring on now() would
        # serve an empty chart every weekend and every holiday, and it would
        # make the frame untestable without freezing time. Anchored on the
        # tape, "the last 24 hours" is true in session and still answers
        # "Friday's day plus Thursday's close" on a Sunday — and the span
        # text says "up to the last print", which is exactly what it is.
        try:
            import pandas as pd
            idx = df.index
            et = (idx.tz_localize("UTC") if idx.tz is None
                  else idx).tz_convert("America/New_York")
            if key == H24:
                end = et.max()
                cutoff = end - pd.Timedelta(hours=24)
                keep = et > cutoff
                df = df[keep]
                meta["window_hours"] = 24
                meta["session"] = (f"{cutoff:%Y-%m-%d %H:%M} → "
                                   f"{end:%Y-%m-%d %H:%M} ET")
                # HOW MANY SESSIONS THE SLICE ACTUALLY HOLDS (2026-09-23).
                # The extended session is 04:00-20:00 ET = 16 h, and the slice
                # is anchored on the LAST BAR PRESENT — so once the tape stops
                # the 24-hour window can only contain that one session, and
                # `24h` draws byte-for-byte what `5m_today` draws. Measured
                # 2026-09-22 after the close: PTGX 79 bars 04:10→16:05 on both,
                # NVDA 192 bars 04:05→20:00 on both, identical levels. Claiming
                # "pre-market through after-hours" over one session would be
                # asserting coverage the chart does not contain, so the label
                # says which of the two it is. The frames still diverge
                # INTRADAY and on a name with no pre-market — this is wording,
                # not a slice change.
                sessions = sorted({str(d) for d in et[keep].date})
                meta["sessions"] = len(sessions)
                if len(sessions) <= 1:
                    meta["window_label"] = (
                        "the 24 hours up to the last print — only "
                        f"{sessions[0] if sessions else 'one session'} "
                        "printed in it")
            else:
                days = pd.Series(et.date, index=idx)
                session = days.max()
                df = df[days == session]
                meta["session"] = str(session)
        except Exception as exc:                            # pragma: no cover
            log.warning("timeframes: session slice failed: %s", exc)
    df = df.tail(want)
    # as_of = the last raw MINUTE seen. The last bucket is labelled by its
    # CLOSE (right label), so at 10:07 ET the 15m frame ends in a bar stamped
    # 10:15 — a future time, and the Support-tab / session-board payloads
    # were carrying it as the read's timestamp. That bucket is `partial`
    # unless the minute before its label has printed (2026-09-05).
    try:
        import pandas as pd
        last_minute = pd.Timestamp(raw.index[-1])
        label = pd.Timestamp(df.index[-1])
        partial = bool((label - last_minute) > pd.Timedelta(minutes=1))
        as_of = str(raw.index[-1])
    except Exception as exc:                                # pragma: no cover
        log.warning("timeframes: as_of from raw minutes failed: %s", exc)
        partial, as_of = True, str(df.index[-1])
    meta.update({"bars": len(df), "available": True,
                 "source": (f"1-minute bars resampled to {spec['bar_label']}, "
                            + ("pre/post market drawn, structure from RTH"
                               if spec.get("ext_hours") else "RTH only")),
                 "as_of": as_of,
                 "partial": partial,
                 "ext_hours": bool(spec.get("ext_hours"))})
    return df, meta


# --- live session state ------------------------------------------------------

LIVE_REFRESH_SEC = 30

# NYSE half days — 13:00 ET close, extended session ends 17:00 ET.
HALF_DAYS = {"2026-11-27", "2026-12-24", "2027-11-26", "2027-12-23"}


def _is_holiday(et) -> bool:
    """Full-closure days from the single holiday table the app already keeps
    (market_hours.reminder). A weekday check alone had the live chart
    polling Massive every 30s all Labor Day."""
    try:
        from market_hours.reminder import ALL_HOLIDAYS
        return et.strftime("%Y-%m-%d") in ALL_HOLIDAYS
    except Exception as exc:                                # pragma: no cover
        log.warning("timeframes: holiday table unavailable: %s", exc)
        return False


def _is_half_day(et) -> bool:
    return et.strftime("%Y-%m-%d") in HALF_DAYS


def live_state(now=None) -> dict:
    """{state, refresh_sec, as_of} for the live chart's poll loop.

    state ∈ premarket | rth | afterhours | closed (ET clock, weekdays only —
    the daytrading session constants are the single source of truth).
    refresh_sec is 0 when nothing can print, so the FE never polls a dead
    tape.
    """
    import pandas as pd
    ts = pd.Timestamp(now) if now is not None else pd.Timestamp.utcnow()
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    et = ts.tz_convert("America/New_York")
    state = "closed"
    if et.weekday() < 5 and not _is_holiday(et):
        try:
            from daytrading.data import _classify_session
            state = _classify_session(ts)
        except Exception as exc:                            # pragma: no cover
            log.warning("timeframes: session classify failed: %s", exc)
        # Half days (day after Thanksgiving, Christmas Eve): NYSE closes
        # 13:00 ET and the after-hours session ends 17:00. Polling a dead
        # tape until 20:00 would burn ~840 provider calls a tab.
        if state != "closed" and _is_half_day(et) and et.hour >= 17:
            state = "closed"
    return {"state": state,
            "refresh_sec": LIVE_REFRESH_SEC if state != "closed" else 0,
            "as_of": et.strftime("%Y-%m-%d %H:%M:%S ET")}
