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
has 7 (the last one is a half hour), so "60 bars of structure" is 2.5
sessions on the 15m and 9 on the hourly. The dropdown labels state the
real calendar span so the zoom is never ambiguous.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

log = logging.getLogger("supply_demand.timeframes")

DAILY = "daily"
H1 = "60m"
M15 = "15m"
M15_OPEN = "15m_open"
M5_LIVE = "5m_live"

# `bars` is what the zone engine reads; `days` is the calendar fetch span.
# swing_window shrinks intraday on purpose — a 3-bar swing on a 15m chart
# is 45 minutes, which is already a real intraday pivot; the daily default
# of 4-5 would find two levels a session and call the chart structureless.
TIMEFRAMES: tuple[dict, ...] = (
    {"key": DAILY, "label": "Daily", "bars": 252, "days": 0,
     "swing_window": 4, "span": "1 year of daily bars",
     "orb_minutes": 30},
    # 330 bars ≈ 47 sessions ≈ 9 weeks — deliberately wide enough that
    # Bulkowski's minimum cup ("7 weeks" = 245 hourly bars) can actually
    # form. A shorter budget would make the cup detector silently barren
    # on this timeframe and look like a bug.
    {"key": H1, "label": "1 hour", "bars": 330, "days": 70,
     "swing_window": 3, "span": "~47 sessions of hourly bars",
     "orb_minutes": 60},
    {"key": M15, "label": "15 min", "bars": 260, "days": 15,
     "swing_window": 2, "span": "~10 sessions of 15-minute bars",
     "orb_minutes": 15},
    # Ajay 2026-08-29: "can you create 15 mins from Market open time
    # please?" — TODAY only, anchored at 09:30 ET. A session view: the
    # levels that matter are the ones this session built, so the frame
    # deliberately forgets everything before the bell.
    {"key": M15_OPEN, "label": "15 min · from the open", "bars": 26,
     "days": 1, "swing_window": 2,
     "span": "today's session only, from 09:30 ET", "orb_minutes": 15},
    # Ajay 2026-09-02: "add live chart please, for supply demand? I wanna
    # see where things bounced over night." The ONE frame that draws
    # pre-market and after-hours bars (04:00-20:00 ET, the last ~2.5
    # sessions of 5-minute candles), refreshed every 30s while any
    # extended session is open. Levels come from the DAILY window (see
    # chart_maps.support.for_symbol) — the session policy below is about
    # what a LEVEL is made of, not about what the chart is allowed to show.
    {"key": M5_LIVE, "label": "5 min · live · pre/post market", "bars": 480,
     "days": 3, "swing_window": 2, "rule": "5min", "ext_hours": True,
     "span": "last ~2.5 sessions of 5-minute bars incl. pre/post market",
     "orb_minutes": 5},
)

DEFAULT_TF = DAILY
_BY_KEY = {t["key"]: t for t in TIMEFRAMES}

# Aliases so a URL can say what a human would type.
_ALIAS = {"1d": DAILY, "d": DAILY, "day": DAILY, "1day": DAILY,
          "1h": H1, "h": H1, "hour": H1, "hourly": H1, "60min": H1,
          "15": M15, "15min": M15, "m15": M15, "15m": M15,
          "open": M15_OPEN, "session": M15_OPEN, "15m_open": M15_OPEN,
          "15open": M15_OPEN,
          "5m": M5_LIVE, "5min": M5_LIVE, "live": M5_LIVE, "5m_live": M5_LIVE,
          "5m_ext": M5_LIVE}


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

    `5m_live` is HIDDEN by default: it is a CHART frame whose bars include
    pre/post market, and the zone engine must never read swings off a
    07:12 print on 400 shares (module docstring). Only the Support tab —
    which reads its levels from the DAILY window and uses these bars for
    drawing alone — asks for it.
    """
    return [{"key": t["key"], "label": t["label"], "span": t["span"],
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

    if key == M15_OPEN:
        # Keep only the most recent SESSION. Before the first bell of a new
        # day that is yesterday's session, which is the honest answer —
        # inventing an empty frame for a day that has not opened would be
        # worse than showing the one that just closed, and the label says
        # which day it is.
        try:
            import pandas as pd
            idx = df.index
            et = (idx.tz_localize("UTC") if idx.tz is None
                  else idx).tz_convert("America/New_York")
            days = pd.Series(et.date, index=idx)
            session = days.max()
            df = df[days == session]
            meta["session"] = str(session)
        except Exception as exc:                            # pragma: no cover
            log.warning("timeframes: session slice failed: %s", exc)
    df = df.tail(want)
    meta.update({"bars": len(df), "available": True,
                 "source": (f"1-minute bars resampled to {spec['label']}, "
                            + ("pre/post market drawn, structure from RTH"
                               if spec.get("ext_hours") else "RTH only")),
                 "as_of": str(df.index[-1]),
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
