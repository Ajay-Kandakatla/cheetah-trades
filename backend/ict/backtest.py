"""ICT board walk-forward backtest — what the board WOULD have shown at every
60-minute close, and what price did next.

Ajay 2026-09-04: "Did you back test this?" ... "yes please run it." The rules
under test are the ones in ict/structure.py and ict/engine.py (Ajay's spec +
Jesse Rogers, https://www.youtube.com/watch?v=Q7Ryv1M7CvI). Nothing here
re-implements a rule: every read goes through engine.macro() and
engine.micro() exactly as the cron does, on frames cut to what existed at
that moment. The method doc is docs/ict/backtest_method.md.

No lookahead — the hard rules (each one has a test in tests/test_ict_backtest.py)
---------------------------------------------------------------------------------
1. Time axis = the 60m bars supply_demand.timeframes.frame_for produces from
   the 1-minute bars (the HOUSE closed=left resample, never re-done by hand),
   evaluated in order. At the close t of one bar the model sees:
     * micro  = the 60m bars with index <= t, windowed the way production
       fetches them (engine.micro_raw_window: MICRO_DAYS + 4 calendar days);
     * macro  = the daily sessions CLOSED strictly before t's session (from
       sepa.prices.load_prices, no period argument — it would poison the
       shared cache) PLUS one partial bar for t's session built from that
       session's 1-minute bars with stamps < t (open = the first minute's
       open, high/low = the running extremes, close = the last minute's
       close, volume summed). Never the live today-bar overlay, never the
       full daily bar of the current session, never a bar after t.
2. The daily read is a plain engine.macro(df=as_of_frame) call per 60m
   close. Profiled at ~2.5 ms on a 500-bar frame, so no structural cache is
   needed and nothing can drift from what the board computes.
3. Dormant loop like production: engine.micro() runs only when macro's
   `tapped` is not None at that close.
4. A SIGNAL is the FIRST close at which (symbol, bias, manipulation bar
   time) reaches state "entry"; the fill is that close (market fill, not the
   zone edge). Confirmed-but-not-entered keys are kept in a second table.
5. Outcomes walk 1-minute bars strictly after t (stamps >= t) through the
   rest of that session plus HORIZON_SESSIONS more: first touch of stop vs
   target, a same-minute tie counts as STOP, no target = stop or horizon
   only. A window that runs past the data end is "unresolved".
6. Placebo = same symbol, same direction, same stop / target distances in
   percent (so the same R multiple), entered at a seeded random 60m close
   whose own outcome window ends before the signal's session (at least
   HORIZON_SESSIONS + 1 sessions earlier). SPY / RSP forward returns over
   the same horizons are the market context line. The placebo line is over
   the placebos of the RESOLVED signals only.

Report style (docs/supply_demand/zone_backtest.md): medians, a mean only as
the expectancy line, small-n flags under SMALL_N resolved, no ranking on
win rate, and the caveats printed with the numbers.

Run (inside the api container, where the price cache and Mongo live):
    cd /app && PYTHONPATH=/app python -m ict.backtest --names 300 --months 6 \
        --out /tmp/ict_bt.json --md /tmp/ict_bt.md --seed 7 --workers 4
`--resume` re-reads <out>.partial.jsonl and skips finished symbols.
"""
from __future__ import annotations

import json
import logging
import random
import statistics
import threading
import time
from datetime import date, datetime, timedelta
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from ict import engine as E
from ict import structure as S

log = logging.getLogger("ict.backtest")

ET = ZoneInfo("America/New_York")
VIDEO_URL = S.VIDEO_URL
MICRO_TF = E.MICRO_TF_DEFAULT

# ── owner constants — owner rule, not from the video ─────────────────────────
HORIZON_SESSIONS = 10     # owner rule — not from the video: sessions after the signal session an outcome may take
MIN_SESSIONS = 60         # owner rule — not from the video: a name with fewer minute sessions is skipped
SMALL_N = 30              # owner rule — not from the video: a bucket with fewer resolved rows is flagged small-n
MISMATCH_TOL_PCT = 3.0    # owner rule — not from the video: daily close vs minute session close tolerance
MISMATCH_MAX_FRAC = 0.02  # owner rule — not from the video: more mismatched sessions than this = skip (split drift)
WARMUP_DAYS = int(E.MICRO_DAYS) + 4   # owner rule — not from the video: calendar days of minutes fetched
                          # before the span = engine.micro_raw_window's span, so the FIRST evaluated
                          # close already sees the full production micro window (review 2026-09-04:
                          # 10 days gave the first two weeks a shorter frame than the cron's, and
                          # consolidations() segments from the frame start)
BENCHMARKS = ("SPY", "RSP")
GRADE_BUCKETS = (80, 100)
_NS_PER_DAY = 86_400 * 1_000_000_000
_NS_PER_MIN = 60 * 1_000_000_000

BACKTEST_PARAMS = {
    "HORIZON_SESSIONS": HORIZON_SESSIONS, "MIN_SESSIONS": MIN_SESSIONS,
    "SMALL_N": SMALL_N, "MISMATCH_TOL_PCT": MISMATCH_TOL_PCT,
    "MISMATCH_MAX_FRAC": MISMATCH_MAX_FRAC, "WARMUP_DAYS": WARMUP_DAYS,
}

CAVEATS = [
    "Survivorship: the universe is TODAY's big caps (zone_store.big_cap_universe), "
    "so names that fell out of it during the span are not tested.",
    "Fills are the 60m close at the signal bar, not the zone edge; no slippage, no commissions.",
    "A same-minute touch of both stop and target counts as a STOP (conservative).",
    "A plan whose target the fill had already passed, or whose stop the fill had already "
    "crossed, is 'bad geometry': skipped and counted, never a target hit.",
    "The placebo line is the placebos of the RESOLVED signals only, each placed so its own "
    "window ends before its signal's session.",
    "The board is read at 60m bar CLOSES only; the cron re-reads every 15 minutes with a "
    "partial hour bar, so a state that flickered intra-hour is not a signal here.",
    "The as-of daily bar is RTH minutes only; the live board overlays the provider's day "
    "bar, which can differ by the auction prints.",
    "The daily history is today's 2y cache cut at each session, so the frame start sits "
    "~18 months before an early signal instead of 24 — only the display-side "
    "consolidation count can differ from what the live board computed that day.",
    "Every threshold is an owner constant unless the video states it; values are listed "
    "under `params` and in docs/ict/backtest_method.md.",
]


class SkipSymbol(Exception):
    """A name the backtest cannot read honestly; `.reason` is counted."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# ── small helpers ────────────────────────────────────────────────────────────
def _num(v) -> Optional[float]:
    return E._num(v)


def _r(v, nd: int = 4) -> Optional[float]:
    return E._r(v, nd)


def _median(xs: list) -> Optional[float]:
    xs = [float(x) for x in xs if x is not None and x == x]
    return round(statistics.median(xs), 4) if xs else None


def _mean(xs: list) -> Optional[float]:
    xs = [float(x) for x in xs if x is not None and x == x]
    return round(sum(xs) / len(xs), 4) if xs else None


def _pct(num: int, den: int) -> Optional[float]:
    return round(100.0 * num / den, 1) if den else None


def _day_int_from_date(d: date) -> int:
    return (d - date(1970, 1, 1)).days


def _date_from_day_int(d: int) -> date:
    return date(1970, 1, 1) + timedelta(days=int(d))


def _et_day_ints(ns_index) -> "np.ndarray":
    """UTC-naive stamps -> ET session date as days since the epoch."""
    import pandas as pd
    idx = pd.DatetimeIndex(ns_index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    et = idx.tz_convert("America/New_York").normalize().tz_localize(None)
    return et.asi8 // _NS_PER_DAY


def _iso_et(ns: int) -> str:
    import pandas as pd
    return pd.Timestamp(int(ns)).tz_localize("UTC").tz_convert("America/New_York").isoformat()


def _norm_daily(df):
    """load_prices frame -> sorted, naive-midnight DatetimeIndex, lower-case
    OHLCV columns. None when unusable."""
    import pandas as pd
    if df is None or getattr(df, "empty", True):
        return None
    out = df.rename(columns={c: str(c).lower() for c in df.columns})
    if not {"open", "high", "low", "close"} <= set(out.columns):
        return None
    if "volume" not in out.columns:
        out["volume"] = 0.0
    out = out[["open", "high", "low", "close", "volume"]].astype(float)
    idx = pd.to_datetime(out.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    out.index = idx.normalize()
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out


# ── the per-symbol context: minutes, sessions, 60m bars, daily history ───────
class Ctx:
    """Everything the walk needs, as numpy arrays. Built once per symbol."""

    def __init__(self, symbol: str, raw, daily, h1):
        import numpy as np
        self.symbol = symbol
        self.mt = raw.index.asi8.astype("int64")
        self.mo = raw["open"].to_numpy(dtype=float)
        self.mh = raw["high"].to_numpy(dtype=float)
        self.ml = raw["low"].to_numpy(dtype=float)
        self.mc = raw["close"].to_numpy(dtype=float)
        self.mv = (raw["volume"].to_numpy(dtype=float) if "volume" in raw.columns
                   else np.zeros(len(raw)))
        self.mday = _et_day_ints(raw.index)
        days, starts = np.unique(self.mday, return_index=True)
        self.sessions = days.astype("int64")                 # ET day ints, ascending
        self.sess_start = starts.astype("int64")
        self.sess_end = np.append(starts[1:], len(self.mt)).astype("int64")
        self.n_sessions = len(days)
        # 60m bars (the house resample) — the time axis
        self.h1 = h1
        self.ht = h1.index.asi8.astype("int64")
        self.hc = h1["close"].to_numpy(dtype=float)
        self.hday = _et_day_ints(h1.index.asi8 - _NS_PER_MIN)   # a close label belongs to the bar before it
        self.hsess = np.searchsorted(self.sessions, self.hday)  # session index per 60m bar
        self.hpos = np.searchsorted(self.mt, self.ht, side="left")  # first minute with stamp >= t
        # daily history
        self.daily = daily
        self.dday = (daily.index.asi8 // _NS_PER_DAY).astype("int64")
        self.dclose = daily["close"].to_numpy(dtype=float)
        # Data completeness: daily sessions inside the minute span that have
        # no minutes (a day the provider call failed or the breaker was
        # open). Not a skip — the horizon counts the sessions that exist —
        # but reported per symbol so a run can say how many days are holes.
        in_span = self.dday[(self.dday >= self.sessions[0]) & (self.dday <= self.sessions[-1])]
        self.missing_sessions = int((~np.isin(in_span, self.sessions)).sum())

    def session_date(self, s_idx: int) -> date:
        return _date_from_day_int(int(self.sessions[s_idx]))


def _drop_open_session(raw, now: Optional[datetime] = None):
    """If the newest session is TODAY (ET) and the bell has not rung, drop it:
    its last 60m bucket would be a partial bar wearing a close label."""
    if raw is None or raw.empty:
        return raw
    now = (now or datetime.now(ET)).astimezone(ET)
    if now.hour >= 16:
        return raw
    today = _day_int_from_date(now.date())
    days = _et_day_ints(raw.index)
    if int(days[-1]) != today:
        return raw
    return raw[days < today]


def prepare(symbol: str, raw, daily, *, min_sessions: Optional[int] = None,
            now: Optional[datetime] = None) -> Ctx:
    """Build the walk context or raise SkipSymbol(reason)."""
    import numpy as np
    from supply_demand.timeframes import frame_for
    min_sessions = MIN_SESSIONS if min_sessions is None else int(min_sessions)
    sym = (symbol or "").upper().strip()
    if raw is None or getattr(raw, "empty", True):
        raise SkipSymbol("no_minutes")
    raw = raw.rename(columns={c: str(c).lower() for c in raw.columns})
    if not {"open", "high", "low", "close"} <= set(raw.columns):
        raise SkipSymbol("bad_minute_columns")
    if "session" in raw.columns:
        raw = raw[raw["session"] == "rth"]
    raw = raw[~raw.index.duplicated(keep="last")].sort_index()
    raw = _drop_open_session(raw, now)
    if raw is None or raw.empty:
        raise SkipSymbol("no_minutes")
    n_sess = len(np.unique(_et_day_ints(raw.index)))
    if n_sess < int(min_sessions):
        raise SkipSymbol("short_minute_history")
    d = _norm_daily(daily)
    if d is None or len(d) < E.MACRO_MIN_BARS:
        raise SkipSymbol("no_daily")
    h1, meta = frame_for(sym, MICRO_TF, raw=raw, bars=len(raw) + 1)
    if h1 is None or h1.empty:
        raise SkipSymbol("no_60m_frame")
    ctx = Ctx(sym, raw, d, h1)
    # Split / adjustment drift guard: the daily cache and the minute cache
    # were fetched at different times. A session whose daily close and
    # minute close disagree by more than MISMATCH_TOL_PCT is a mismatch;
    # too many of them and every level would be off by the split ratio.
    both = np.isin(ctx.sessions, ctx.dday)
    if both.any():
        s_idx = np.nonzero(both)[0]
        m_close = ctx.mc[ctx.sess_end[s_idx] - 1]
        d_pos = np.searchsorted(ctx.dday, ctx.sessions[s_idx])
        d_close = ctx.dclose[d_pos]
        diff = np.abs(d_close - m_close) / np.where(d_close > 0, d_close, np.nan) * 100.0
        bad = int(np.nansum(diff > MISMATCH_TOL_PCT))
        if bad / max(1, len(s_idx)) > MISMATCH_MAX_FRAC and bad >= 2:
            raise SkipSymbol("daily_minute_mismatch")
    return ctx


# ── the as-of frames ─────────────────────────────────────────────────────────
def partial_bar(ctx: Ctx, s_idx: int, j: int) -> tuple:
    """(open, high, low, close, volume) of session s_idx from its first
    minute through the minutes with stamp < the 60m close ht[j]."""
    a, b = int(ctx.sess_start[s_idx]), int(ctx.hpos[j])
    if b <= a:
        return None
    return (float(ctx.mo[a]), float(ctx.mh[a:b].max()), float(ctx.ml[a:b].min()),
            float(ctx.mc[b - 1]), float(ctx.mv[a:b].sum()))


def session_base(ctx: Ctx, s_idx: int):
    """The daily frame as of session s_idx: every CLOSED session strictly
    before it plus one placeholder row stamped with the session date. The
    walk overwrites the placeholder per 60m close (`set_partial`)."""
    import numpy as np
    import pandas as pd
    day = int(ctx.sessions[s_idx])
    k = int(np.searchsorted(ctx.dday, day, side="left"))
    closed = ctx.daily.iloc[:k]
    stamp = pd.Timestamp(_date_from_day_int(day))
    row = pd.DataFrame({"open": [np.nan], "high": [np.nan], "low": [np.nan],
                        "close": [np.nan], "volume": [0.0]}, index=pd.DatetimeIndex([stamp]))
    return pd.concat([closed, row])


def set_partial(base, bar: tuple) -> None:
    o, h, lo, c, v = bar
    n = len(base) - 1
    base.iat[n, 0] = o
    base.iat[n, 1] = h
    base.iat[n, 2] = lo
    base.iat[n, 3] = c
    base.iat[n, 4] = v


def as_of_daily(ctx: Ctx, s_idx: int, j: int):
    """A fresh copy of the frame macro() sees at 60m close j of session
    s_idx (tests compare this with what the walk actually passed)."""
    base = session_base(ctx, s_idx)
    bar = partial_bar(ctx, s_idx, j)
    if bar is None:
        return base.iloc[:-1]
    set_partial(base, bar)
    return base


def micro_window(ctx: Ctx, s_idx: int, j: int, *, window_days: Optional[int] = None,
                 max_bars: Optional[int] = None):
    """The 60m frame at close j: bars with index <= ht[j] whose session lies
    within `window_days` calendar days of the session (production's
    micro_raw_window), trimmed to frame_for's bar budget."""
    import numpy as np
    day = int(ctx.sessions[s_idx])
    if window_days is None:
        start, end = E.micro_raw_window(today=_date_from_day_int(day))
        window_days = (end - start).days
    lo = int(np.searchsorted(ctx.hday, day - int(window_days), side="left"))
    df = ctx.h1.iloc[lo:j + 1]
    if max_bars is None:
        from supply_demand.timeframes import tf_spec
        max_bars = int(tf_spec(MICRO_TF)["bars"])
    return df.tail(int(max_bars))


# ── outcomes ─────────────────────────────────────────────────────────────────
def outcome(bias: str, fill: float, stop: float, target: Optional[float],
            hi, lo, close, *, resolved_window: bool = True) -> dict:
    """First-touch outcome on forward 1-minute arrays (already sliced to the
    horizon window, oldest first).

    bullish: low <= stop -> stop; high >= target -> target. Bearish mirrored.
    Both in the same minute -> STOP. No target -> stop or horizon only.
    R = |fill - stop|; mfe/mae are measured through the exit minute (or the
    whole window on a horizon exit); ret_at_horizon marks the LAST close of
    the window regardless of the exit (what holding would have paid).
    `resolved_window=False` = the window runs past the data end: outcome is
    "unresolved" and only the partial first touch is kept for reference.
    """
    import numpy as np
    hi = np.asarray(hi, dtype=float)
    lo = np.asarray(lo, dtype=float)
    close = np.asarray(close, dtype=float)
    n = len(close)
    bull = bias == "bullish"
    r_abs = (fill - stop) if bull else (stop - fill)
    out = {"outcome": "unresolved", "bars_to_outcome": None, "r_abs": _r(r_abs),
           "mfe_r": None, "mae_r": None, "ret_at_horizon_r": None,
           "mfe_pct": None, "mae_pct": None, "ret_at_horizon_pct": None,
           "partial_first_touch": None, "bars_available": int(n)}
    if r_abs is None or r_abs <= 0 or fill <= 0:
        out["outcome"] = "bad_geometry"
        return out
    # A target the fill has already passed (bullish target <= fill, bearish
    # target >= fill) would print "target" on the first forward minute for
    # ~0 R — geometry, not an outcome (review 2026-09-04).
    if target is not None and ((bull and target <= fill) or (not bull and target >= fill)):
        out["outcome"] = "bad_geometry"
        return out
    if n == 0:
        return out
    if bull:
        stop_hit = lo <= stop
        tgt_hit = (hi >= target) if target is not None else np.zeros(n, dtype=bool)
    else:
        stop_hit = hi >= stop
        tgt_hit = (lo <= target) if target is not None else np.zeros(n, dtype=bool)
    s_i = int(np.argmax(stop_hit)) if stop_hit.any() else None
    t_i = int(np.argmax(tgt_hit)) if tgt_hit.any() else None
    if s_i is not None and (t_i is None or s_i <= t_i):
        res, exit_i = "stop", s_i
    elif t_i is not None:
        res, exit_i = "target", t_i
    else:
        res, exit_i = "horizon", n - 1
    if not resolved_window:
        out["partial_first_touch"] = res if res != "horizon" else None
        return out
    seg_hi, seg_lo = hi[:exit_i + 1], lo[:exit_i + 1]
    if bull:
        mfe, mae = float(seg_hi.max()) - fill, fill - float(seg_lo.min())
        ret = float(close[-1]) - fill
    else:
        mfe, mae = fill - float(seg_lo.min()), float(seg_hi.max()) - fill
        ret = fill - float(close[-1])
    out.update({
        "outcome": res, "bars_to_outcome": int(exit_i + 1),
        "mfe_r": _r(mfe / r_abs), "mae_r": _r(mae / r_abs), "ret_at_horizon_r": _r(ret / r_abs),
        "mfe_pct": _r(mfe / fill * 100.0, 3), "mae_pct": _r(mae / fill * 100.0, 3),
        "ret_at_horizon_pct": _r(ret / fill * 100.0, 3),
    })
    return out


def _window(ctx: Ctx, j: int, horizon: int) -> tuple:
    """(start_pos, end_pos_exclusive, resolved_window, end_session_idx) of the
    forward minute window for 60m close j: the rest of its session plus
    `horizon` more sessions."""
    s_idx = int(ctx.hsess[j])
    start = int(ctx.hpos[j])
    last = s_idx + int(horizon)
    if last < ctx.n_sessions:
        return start, int(ctx.sess_end[last]), True, last
    return start, int(len(ctx.mt)), False, ctx.n_sessions - 1


def evaluate(ctx: Ctx, j: int, bias: str, fill: float, stop: float,
             target: Optional[float], horizon: int = HORIZON_SESSIONS) -> dict:
    """`outcome` on the forward window of 60m close j, plus where it ended."""
    import numpy as np
    start, end, ok, last = _window(ctx, j, horizon)
    res = outcome(bias, fill, stop, target, ctx.mh[start:end], ctx.ml[start:end],
                  ctx.mc[start:end], resolved_window=ok)
    res["horizon_end_ts"] = _iso_et(ctx.mt[end - 1]) if end > start else None
    res["horizon_end_session"] = ctx.session_date(last).isoformat() if ok else None
    res["sessions_to_outcome"] = None
    if res.get("bars_to_outcome") is not None:
        exit_pos = start + res["bars_to_outcome"] - 1
        res["sessions_to_outcome"] = int(np.searchsorted(ctx.sessions, ctx.mday[exit_pos]) - ctx.hsess[j])
    return res


def placebo(ctx: Ctx, j: int, bias: str, fill: float, stop: float, target: Optional[float],
            rng: random.Random, horizon: int = HORIZON_SESSIONS) -> Optional[dict]:
    """Same geometry, random earlier timing: a seeded 60m close of the same
    symbol whose OWN outcome window (rest of its session + `horizon`
    sessions) ends strictly before the signal's session — so the placebo
    never reads a minute the signal's window reads — entered at that close
    with the same stop / target distances in percent (same R multiple)."""
    import numpy as np
    s_idx = int(ctx.hsess[j])
    # candidate sessions <= s_idx - horizon - 1: their window ends at
    # session <= s_idx - 1 (review 2026-09-04: `<= s_idx - horizon` let ~6%
    # of placebo windows run into the signal session)
    k = int(np.searchsorted(ctx.hsess, s_idx - int(horizon) - 1, side="right"))
    if k <= 0:
        return None
    jp = rng.randrange(k)
    p_fill = float(ctx.hc[jp])
    if p_fill <= 0 or fill <= 0:
        return None
    stop_pct = abs(fill - stop) / fill
    tgt_pct = (abs(target - fill) / fill) if target is not None else None
    if bias == "bullish":
        p_stop = p_fill * (1 - stop_pct)
        p_tgt = p_fill * (1 + tgt_pct) if tgt_pct is not None else None
    else:
        p_stop = p_fill * (1 + stop_pct)
        p_tgt = p_fill * (1 - tgt_pct) if tgt_pct is not None else None
    res = evaluate(ctx, jp, bias, p_fill, p_stop, p_tgt, horizon)
    res.update({"ts": _iso_et(ctx.ht[jp]), "session": ctx.session_date(int(ctx.hsess[jp])).isoformat(),
                "bar_i": int(jp), "fill": _r(p_fill), "stop": _r(p_stop), "target": _r(p_tgt),
                "stop_pct": _r(stop_pct * 100.0, 3), "target_pct": _r(tgt_pct * 100.0, 3) if tgt_pct is not None else None})
    return res


# ── the walk ─────────────────────────────────────────────────────────────────
def _record(ctx: Ctx, s_idx: int, j: int, m: dict, mi: dict, base_len: int) -> dict:
    tapped = m.get("tapped") or {}
    plan = mi.get("plan") or {}
    manip = mi.get("manipulation") or {}
    mss_ = mi.get("mss") or {}
    grade = int(mi.get("grade") or 0)
    bar_i = tapped.get("bar_i")
    age = (base_len - 1 - int(bar_i)) if bar_i is not None else None
    ts = _iso_et(ctx.ht[j])
    return {
        "symbol": ctx.symbol, "signal_ts": ts, "session": ctx.session_date(s_idx).isoformat(),
        "month": ts[:7], "bar_i": int(j), "bias": mi.get("bias"), "state": mi.get("state"),
        "grade": grade, "grade_bucket": str(min(GRADE_BUCKETS, key=lambda g: abs(g - grade))),
        "tap_kind": tapped.get("kind"), "tap_age_sessions": age, "tap_price": tapped.get("price"),
        "tap_date": tapped.get("date"), "tap_bias": tapped.get("bias"),
        "bias_matches_tap": (mi.get("bias") == tapped.get("bias")) if tapped.get("bias") else None,
        "source": mi.get("source"),
        "zone": plan.get("zone"), "entry": plan.get("entry"), "entry_lo": plan.get("entry_lo"),
        "entry_hi": plan.get("entry_hi"), "stop": plan.get("stop"), "target": plan.get("target"),
        "rr": plan.get("rr"), "risk_pct": plan.get("risk_pct"),
        "close_at_t": _r(float(ctx.hc[j])), "fill": _r(float(ctx.hc[j])),
        "atr_60m": mi.get("atr"), "macro_date": m.get("date"),
        "manipulation_at": manip.get("at"), "mss_at": mss_.get("at"),
        "ifvg": bool(mi.get("ifvg")), "why": mi.get("why"),
        "key": "|".join([ctx.symbol, str(mi.get("bias")), str(manip.get("at"))]),
    }


def walk(ctx: Ctx, *, eval_from_day: Optional[int] = None, horizon: int = HORIZON_SESSIONS,
         seed: int = 7, macro_fn: Optional[Callable] = None, micro_fn: Optional[Callable] = None,
         micro_window_days: Optional[int] = None) -> dict:
    """Replay every 60m close in order. Returns
    {signals, confirmed, bars, evaluated, macro_none, tapped_bars, micro_calls,
     skipped_no_plan, skipped_bad_geometry, placebo_skipped}."""
    import numpy as np
    macro_fn = macro_fn or (lambda sym, df: E.macro(sym, df=df))
    micro_fn = micro_fn or (lambda sym, df, ctx_: E.micro(sym, MICRO_TF, df=df, macro_ctx=ctx_))
    rng = random.Random(f"{seed}:{ctx.symbol}")
    counts = {"bars": int(len(ctx.ht)), "evaluated": 0, "macro_none": 0, "tapped_bars": 0,
              "micro_calls": 0, "skipped_no_plan": 0, "skipped_bad_geometry": 0,
              "placebo_skipped": 0}
    entries: dict = {}
    confirmed: dict = {}
    seen_entry: set = set()
    cur_s = -1
    base = None
    for j in range(len(ctx.ht)):
        s_idx = int(ctx.hsess[j])
        if eval_from_day is not None and int(ctx.sessions[s_idx]) < int(eval_from_day):
            continue
        if s_idx != cur_s:
            cur_s = s_idx
            base = session_base(ctx, s_idx)
        bar = partial_bar(ctx, s_idx, j)
        if bar is None:
            continue
        set_partial(base, bar)
        counts["evaluated"] += 1
        m = macro_fn(ctx.symbol, base)
        if not m:
            counts["macro_none"] += 1
            continue
        if not m.get("tapped"):
            continue                      # dormant, exactly like the cron
        counts["tapped_bars"] += 1
        mdf = micro_window(ctx, s_idx, j, window_days=micro_window_days)
        counts["micro_calls"] += 1
        mi = micro_fn(ctx.symbol, mdf, m)
        if not mi or mi.get("state") not in ("confirmed", "entry"):
            continue
        manip = mi.get("manipulation") or {}
        if not manip.get("at"):
            continue
        key = (mi.get("bias"), manip.get("at"))
        rec = _record(ctx, s_idx, j, m, mi, len(base))
        if mi["state"] == "confirmed":
            if key not in confirmed and key not in seen_entry:
                confirmed[key] = rec
            continue
        # entry
        if key in seen_entry:
            continue
        seen_entry.add(key)
        if key in confirmed:
            confirmed[key]["entered_later"] = True
        plan = mi.get("plan")
        if not plan or _num(plan.get("stop")) is None:
            counts["skipped_no_plan"] += 1
            continue
        entries[key] = rec

    def _score(rec: dict, is_entry: bool) -> dict:
        fill, stop, tgt = float(rec["fill"]), float(rec["stop"]), _num(rec.get("target"))
        res = evaluate(ctx, rec["bar_i"], rec["bias"], fill, stop, tgt, horizon)
        out = dict(rec, **res)
        if res["outcome"] == "bad_geometry":
            return out
        pl = placebo(ctx, rec["bar_i"], rec["bias"], fill, stop, tgt, rng, horizon)
        out["placebo"] = pl
        if pl is None and is_entry:
            counts["placebo_skipped"] += 1
        return out

    signals = []
    for rec in entries.values():
        out = _score(rec, True)
        if out["outcome"] == "bad_geometry":
            counts["skipped_bad_geometry"] += 1
            continue
        out["kind"] = "entry"
        signals.append(out)
    conf = []
    for rec in confirmed.values():
        rec.setdefault("entered_later", False)
        if _num(rec.get("stop")) is None:
            conf.append(dict(rec, outcome="no_plan", kind="confirmed"))
            continue
        out = _score(rec, False)
        out["kind"] = "confirmed"
        conf.append(out)
    signals.sort(key=lambda r: r["signal_ts"])
    conf.sort(key=lambda r: r["signal_ts"])
    return dict(counts, signals=signals, confirmed=conf, sessions=int(ctx.n_sessions),
                missing_sessions=int(getattr(ctx, "missing_sessions", 0)))


# ── loaders (the only I/O; injectable) ───────────────────────────────────────
def _default_minute_loader(symbol: str, start: date, end: date, source: str = "cache"):
    if source == "range":
        # One paged provider call for the whole span (bypasses the per-day
        # Mongo cache — fastest on a cold cache, writes nothing back).
        from daytrading.data import _fetch_massive_minute, _filter_sessions
        df = _fetch_massive_minute(symbol, start, end)
        return _filter_sessions(df, False, False) if df is not None else None
    from daytrading.data import load_intraday_range
    return load_intraday_range(symbol, start, end, include_premarket=False,
                               include_afterhours=False)


def _default_daily_loader(symbol: str):
    from sepa import prices
    return prices.load_prices((symbol or "").upper())


def _default_universe() -> list:
    from supply_demand.zone_store import big_cap_universe
    return list(big_cap_universe())


def one_symbol(symbol: str, *, fetch_start: date, fetch_end: date, eval_from_day: int,
               horizon: int = HORIZON_SESSIONS, seed: int = 7,
               minute_loader: Optional[Callable] = None, daily_loader: Optional[Callable] = None,
               minute_source: str = "cache", now: Optional[datetime] = None,
               min_sessions: Optional[int] = None) -> dict:
    t0 = time.time()
    sym = (symbol or "").upper().strip()
    ml = minute_loader or (lambda s, a, b: _default_minute_loader(s, a, b, minute_source))
    dl = daily_loader or _default_daily_loader
    try:
        raw = ml(sym, fetch_start, fetch_end)
        daily = dl(sym)
        ctx = prepare(sym, raw, daily, now=now, min_sessions=min_sessions)
        res = walk(ctx, eval_from_day=eval_from_day, horizon=horizon, seed=seed)
    except SkipSymbol as exc:
        return {"symbol": sym, "status": "skipped", "reason": exc.reason,
                "seconds": round(time.time() - t0, 2)}
    except Exception as exc:
        log.warning("ict.backtest: %s failed: %s", sym, exc)
        return {"symbol": sym, "status": "error", "reason": f"{type(exc).__name__}: {exc}"[:200],
                "seconds": round(time.time() - t0, 2)}
    return dict(res, symbol=sym, status="ok", seconds=round(time.time() - t0, 2))


# ── benchmarks ───────────────────────────────────────────────────────────────
def bench_forward(daily, session_iso: str, horizon: int = HORIZON_SESSIONS) -> Optional[float]:
    """Close-to-close % return from the signal session's close to the close
    `horizon` sessions later on a daily frame; None when either is missing."""
    import numpy as np
    d = _norm_daily(daily)
    if d is None:
        return None
    day = _day_int_from_date(date.fromisoformat(session_iso))
    dday = d.index.asi8 // _NS_PER_DAY
    pos = int(np.searchsorted(dday, day, side="right")) - 1
    if pos < 0 or pos + int(horizon) >= len(d):
        return None
    c0, c1 = float(d["close"].iloc[pos]), float(d["close"].iloc[pos + int(horizon)])
    return _r((c1 / c0 - 1.0) * 100.0, 3) if c0 > 0 else None


def context_lines(signals: list, bench_loader: Optional[Callable] = None,
                  horizon: int = HORIZON_SESSIONS) -> dict:
    bl = bench_loader or _default_daily_loader
    out = {}
    resolved = [s for s in signals if s.get("outcome") in ("target", "stop", "horizon")]
    for b in BENCHMARKS:
        try:
            df = bl(b)
        except Exception as exc:
            log.warning("ict.backtest: benchmark %s failed: %s", b, exc)
            df = None
        rets = [bench_forward(df, s["session"], horizon) for s in resolved] if df is not None else []
        rets = [x for x in rets if x is not None]
        by_month: dict = {}
        if df is not None:
            for s in resolved:
                x = bench_forward(df, s["session"], horizon)
                if x is not None:
                    by_month.setdefault(s["month"], []).append(x)
        out[b] = {"n": len(rets), "median_fwd_pct": _median(rets), "mean_fwd_pct": _mean(rets),
                  "by_month": {k: {"n": len(v), "median_fwd_pct": _median(v)}
                               for k, v in sorted(by_month.items())}}
    return out


# ── summary ──────────────────────────────────────────────────────────────────
def stats(recs: list) -> dict:
    n = len(recs)
    res = [r for r in recs if r.get("outcome") in ("target", "stop", "horizon")]
    with_t = [r for r in res if r.get("target") is not None]
    tgt = sum(1 for r in with_t if r["outcome"] == "target")
    stp = sum(1 for r in res if r["outcome"] == "stop")
    hz = sum(1 for r in res if r["outcome"] == "horizon")
    return {
        "n": n, "resolved": len(res), "unresolved": n - len(res), "with_target": len(with_t),
        "target_before_stop_pct": _pct(tgt, len(with_t)),
        "stop_pct": _pct(stp, len(res)), "horizon_pct": _pct(hz, len(res)),
        "median_mfe_r": _median([r.get("mfe_r") for r in res]),
        "median_mae_r": _median([r.get("mae_r") for r in res]),
        "median_ret_at_horizon_r": _median([r.get("ret_at_horizon_r") for r in res]),
        "mean_ret_at_horizon_r": _mean([r.get("ret_at_horizon_r") for r in res]),
        "median_ret_at_horizon_pct": _median([r.get("ret_at_horizon_pct") for r in res]),
        "median_rr": _median([r.get("rr") for r in recs]),
        "median_bars_to_outcome": _median([r.get("bars_to_outcome") for r in res]),
        "small_n": len(res) < SMALL_N,
    }


def _by(recs: list, key: Callable) -> dict:
    groups: dict = {}
    for r in recs:
        groups.setdefault(str(key(r)), []).append(r)
    return {k: stats(v) for k, v in sorted(groups.items())}


def summarize(signals: list, confirmed: list, per_symbol: list) -> dict:
    counts = {"symbols": len(per_symbol),
              "ok": sum(1 for p in per_symbol if p.get("status") == "ok"),
              "skipped": sum(1 for p in per_symbol if p.get("status") == "skipped"),
              "errors": sum(1 for p in per_symbol if p.get("status") == "error"),
              "skip_reasons": {}, "bars": 0, "evaluated": 0, "macro_none": 0, "tapped_bars": 0,
              "micro_calls": 0, "skipped_no_plan": 0, "skipped_bad_geometry": 0,
              "placebo_skipped": 0, "missing_sessions": 0, "symbols_with_missing_sessions": 0}
    for p in per_symbol:
        if p.get("status") != "ok":
            counts["skip_reasons"][p.get("reason") or "?"] = counts["skip_reasons"].get(p.get("reason") or "?", 0) + 1
            continue
        for k in ("bars", "evaluated", "macro_none", "tapped_bars", "micro_calls",
                  "skipped_no_plan", "skipped_bad_geometry", "placebo_skipped", "missing_sessions"):
            counts[k] += int(p.get(k) or 0)
        if int(p.get("missing_sessions") or 0) > 0:
            counts["symbols_with_missing_sessions"] += 1
    # Like for like: the placebo line is the placebos of the RESOLVED signals
    # (an unresolved signal's placebo always resolves — it sits a horizon
    # earlier — and would pad the placebo population; review 2026-09-04).
    resolved_sig = [s for s in signals if s.get("outcome") in ("target", "stop", "horizon")]
    placebos = [s["placebo"] for s in resolved_sig if s.get("placebo")]
    never = [c for c in confirmed if not c.get("entered_later")]
    return {
        "counts": counts,
        "overall": stats(signals),
        "placebo": stats(placebos),
        "by_bias": _by(signals, lambda r: r.get("bias")),
        "by_grade": _by(signals, lambda r: r.get("grade_bucket")),
        "by_tap_kind": _by(signals, lambda r: r.get("tap_kind")),
        "by_zone": _by(signals, lambda r: r.get("zone")),
        "by_tap_agreement": _by(signals, lambda r: ("bias agrees with tap" if r.get("bias_matches_tap")
                                                   else "bias opposes tap")),
        "by_source": _by(signals, lambda r: r.get("source")),
        "by_month": _by(signals, lambda r: r.get("month")),
        "placebo_by_bias": _by([dict(p, bias=s.get("bias")) for s in resolved_sig for p in [s.get("placebo")] if p],
                               lambda r: r.get("bias")),
        "confirmed_never_entered": stats(never),
        "confirmed_never_entered_by_bias": _by(never, lambda r: r.get("bias")),
        "confirmed_total": len(confirmed),
        "confirmed_entered_later": sum(1 for c in confirmed if c.get("entered_later")),
    }


# ── report ───────────────────────────────────────────────────────────────────
def _f(v, nd: int = 2) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def _p(v, nd: int = 1) -> str:
    return "n/a" if v is None else f"{v:.{nd}f}%"


def _row(label: str, s: dict) -> str:
    note = "⚠ small n" if s.get("small_n") and s.get("resolved") else ("no rows" if not s.get("resolved") else "")
    return (f"| {label} | {s['n']} | {s['resolved']} | {s['unresolved']} | "
            f"{_p(s['target_before_stop_pct'])} ({s['with_target']}) | {_p(s['stop_pct'])} | "
            f"{_p(s['horizon_pct'])} | {_f(s['median_mfe_r'])} | {_f(s['median_mae_r'])} | "
            f"{_f(s['median_ret_at_horizon_r'])} | {_f(s['mean_ret_at_horizon_r'])} | {note} |")


_HEAD = ("| bucket | n | resolved | unresolved | target-first % (n w/ target) | stop % | horizon % | "
         "med MFE R | med MAE R | med ret@H R | mean ret@H R | note |\n"
         "|---|---|---|---|---|---|---|---|---|---|---|---|")


def render_markdown(doc: dict) -> str:
    sm, ctx = doc["summary"], doc.get("context") or {}
    c = sm["counts"]
    ov, pl = sm["overall"], sm["placebo"]
    a = doc.get("args") or {}
    lines = []
    lines.append("# ICT board — walk-forward backtest")
    lines.append("")
    lines.append(f"Run {doc.get('as_of')} · span {doc.get('span_start')} → {doc.get('span_end')} "
                 f"({a.get('months')} months) · sample {c['symbols']} of {doc.get('universe_size')} "
                 f"big caps (seed {a.get('seed')}) · horizon = rest of the signal session + "
                 f"{doc.get('horizon')} sessions · method: docs/ict/backtest_method.md")
    lines.append("")
    lines.append("**Read this first.** The universe is TODAY's big caps (survivorship). Fills are the "
                 "60m close of the signal bar, not the zone edge. Medians lead; the mean is the "
                 "expectancy line only. A bucket under "
                 f"{SMALL_N} resolved rows is flagged ⚠ and is not evidence. Nothing here ranks on win rate.")
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    lines.append(f"- symbols: {c['ok']} read, {c['skipped']} skipped, {c['errors']} errors "
                 f"(reasons: {json.dumps(c['skip_reasons'])})")
    lines.append(f"- 60m closes evaluated: {c['evaluated']:,} · tapped closes: {c['tapped_bars']:,} · "
                 f"micro() calls: {c['micro_calls']:,} · macro() with no read: {c['macro_none']:,}")
    lines.append(f"- entry signals: **{ov['n']}** · resolved {ov['resolved']} · unresolved {ov['unresolved']} · "
                 f"skipped (no plan / no stop) {c['skipped_no_plan']} · skipped (bad geometry) "
                 f"{c['skipped_bad_geometry']} · placebo missing {c['placebo_skipped']}")
    lines.append(f"- confirmed (MSS + FVG) keys: {sm['confirmed_total']}, of which "
                 f"{sm['confirmed_entered_later']} later reached entry")
    lines.append(f"- minute-data holes: {c.get('missing_sessions', 0)} daily sessions with no minutes across "
                 f"{c.get('symbols_with_missing_sessions', 0)} symbols (the horizon counts the sessions that exist)")
    lines.append("")
    lines.append("## Signal vs placebo")
    lines.append("")
    lines.append(_HEAD)
    lines.append(_row("**signal**", ov))
    lines.append(_row("placebo (same geometry, random earlier close)", pl))
    for b, s in (sm.get("placebo_by_bias") or {}).items():
        lines.append(_row(f"placebo · {b}", s))
    lines.append("")
    ctx_bits = []
    for b in BENCHMARKS:
        cb = ctx.get(b) or {}
        ctx_bits.append(f"{b} median {_p(cb.get('median_fwd_pct'), 2)} (mean {_p(cb.get('mean_fwd_pct'), 2)}, n={cb.get('n', 0)})")
    lines.append("Market context over the same horizons from the signal sessions: " + " · ".join(ctx_bits) + ".")
    lines.append("")
    for title, key in (("By bias", "by_bias"), ("By grade (80 = no displacement credit, 100 = with)", "by_grade"),
                       ("By tap kind", "by_tap_kind"), ("By zone kind", "by_zone"),
                       ("By tap agreement (the board scans both biases; the tap's bias is only a tiebreak)",
                        "by_tap_agreement"),
                       ("By manipulation source (Power of 3 range vs the tapped daily level)", "by_source"),
                       ("By month", "by_month")):
        lines.append(f"## {title}")
        lines.append("")
        lines.append(_HEAD)
        rows = sm.get(key) or {}
        if not rows:
            lines.append("| (none) | 0 | 0 | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | no rows |")
        for k, s in rows.items():
            lines.append(_row(k, s))
        lines.append("")
    lines.append("## Confirmed but never entered (MSS + FVG, price never came to the zone)")
    lines.append("")
    lines.append("Filled at the confirmation close for comparison only — the board never showed these as entries.")
    lines.append("")
    lines.append(_HEAD)
    lines.append(_row("confirmed, never entered", sm["confirmed_never_entered"]))
    for k, s in (sm.get("confirmed_never_entered_by_bias") or {}).items():
        lines.append(_row(f"· {k}", s))
    lines.append("")
    lines.append("## Caveats")
    lines.append("")
    for cv in doc.get("caveats") or []:
        lines.append(f"- {cv}")
    lines.append("")
    lines.append("## Owner constants in force")
    lines.append("")
    lines.append("| key | value | source |")
    lines.append("|---|---|---|")
    for p in doc.get("params") or []:
        lines.append(f"| {p['key']} | {p['value']} | {p['note']} |")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    d_ret = (None if ov["median_ret_at_horizon_r"] is None or pl["median_ret_at_horizon_r"] is None
             else round(ov["median_ret_at_horizon_r"] - pl["median_ret_at_horizon_r"], 3))
    d_tgt = (None if ov["target_before_stop_pct"] is None or pl["target_before_stop_pct"] is None
             else round(ov["target_before_stop_pct"] - pl["target_before_stop_pct"], 1))
    lines.append(
        f"_Template — the orchestrator fills the judgement:_ Over **{ov['resolved']}** resolved entry signals "
        f"({ov['n']} total, {ov['unresolved']} unresolved) the board's median ret@horizon was "
        f"**{_f(ov['median_ret_at_horizon_r'])} R** against **{_f(pl['median_ret_at_horizon_r'])} R** for its own "
        f"placebo (difference {_f(d_ret, 3)} R), and target-before-stop was **{_p(ov['target_before_stop_pct'])}** "
        f"against **{_p(pl['target_before_stop_pct'])}** (difference {_f(d_tgt, 1)} pp). "
        f"[ORCHESTRATOR: state plainly whether the signal BEATS or LOSES TO its placebo on both lines and by how much, "
        f"whether the market context (SPY/RSP) explains the raw number, and repeat the small-n caveat where any "
        f"bucket leaned on has fewer than {SMALL_N} resolved rows. Do not rank buckets on win rate.]")
    lines.append("")
    return "\n".join(lines)


# ── the run ──────────────────────────────────────────────────────────────────
def _read_partial(path: str) -> dict:
    done = {}
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("symbol"):
                    done[rec["symbol"]] = rec
    except FileNotFoundError:
        return {}
    return done


def sample_universe(universe: list, names: int, seed: int) -> list:
    pool = sorted({str(s).upper() for s in universe if s})
    rng = random.Random(int(seed))
    if names >= len(pool):
        return pool
    return sorted(rng.sample(pool, int(names)))


def run(*, names: int = 300, months: int = 6, seed: int = 7, workers: int = 4,
        universe: Optional[list] = None, symbols: Optional[list] = None,
        minute_loader: Optional[Callable] = None, daily_loader: Optional[Callable] = None,
        bench_loader: Optional[Callable] = None, out: Optional[str] = None,
        resume: bool = False, horizon: int = HORIZON_SESSIONS, today: Optional[date] = None,
        minute_source: str = "cache", log_every: int = 25, now: Optional[datetime] = None,
        min_sessions: Optional[int] = None) -> dict:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    t0 = time.time()
    now = (now or datetime.now(ET)).astimezone(ET)
    today = today or now.date()
    span_start = today - timedelta(days=int(months) * 31)
    fetch_start = span_start - timedelta(days=WARMUP_DAYS)
    eval_from_day = _day_int_from_date(span_start)
    if symbols:
        sample = sorted({str(s).upper() for s in symbols if s})
        universe_size = len(sample)
    else:
        pool = list(universe) if universe is not None else _default_universe()
        universe_size = len(pool)
        sample = sample_universe(pool, int(names), int(seed))
    partial_path = (out + ".partial.jsonl") if out else None
    done = _read_partial(partial_path) if (resume and partial_path) else {}
    # An errored symbol (provider timeout) or one skipped for having NO
    # minutes at all (the breaker was open) is not done: --resume re-runs it
    # and its newer line wins in _read_partial.
    done = {k: v for k, v in done.items()
            if v.get("status") != "error" and v.get("reason") != "no_minutes"}
    todo = [s for s in sample if s not in done]
    log.info("ict.backtest: %d names (%d resumed), span %s -> %s, horizon %d sessions, %d workers",
             len(sample), len(done), span_start, today, horizon, workers)
    results = dict(done)
    lock = threading.Lock()
    # A fresh run truncates the partial file so a later --resume cannot pick
    # up lines from an older run with a different span or seed.
    fh = open(partial_path, "a" if resume else "w") if partial_path else None

    def _work(sym: str) -> dict:
        return one_symbol(sym, fetch_start=fetch_start, fetch_end=today, eval_from_day=eval_from_day,
                          horizon=horizon, seed=seed, minute_loader=minute_loader,
                          daily_loader=daily_loader, minute_source=minute_source, now=now,
                          min_sessions=min_sessions)

    finished = 0
    try:
        with ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool_:
            futs = {pool_.submit(_work, s): s for s in todo}
            for fut in as_completed(futs):
                rec = fut.result()
                with lock:
                    results[rec["symbol"]] = rec
                    if fh is not None:
                        fh.write(json.dumps(rec, default=str) + "\n")
                        fh.flush()
                    finished += 1
                    if log_every and finished % int(log_every) == 0:
                        el = time.time() - t0
                        rate = el / finished
                        log.info("ict.backtest: %d/%d symbols in %.0fs — ETA %.0fs",
                                 finished, len(todo), el, rate * (len(todo) - finished))
    finally:
        if fh is not None:
            fh.close()

    per_symbol = [results[s] for s in sample if s in results]
    signals = [x for p in per_symbol if p.get("status") == "ok" for x in (p.get("signals") or [])]
    confirmed = [x for p in per_symbol if p.get("status") == "ok" for x in (p.get("confirmed") or [])]
    signals.sort(key=lambda r: (r["signal_ts"], r["symbol"]))
    confirmed.sort(key=lambda r: (r["signal_ts"], r["symbol"]))
    summary = summarize(signals, confirmed, per_symbol)
    context = context_lines(signals, bench_loader, horizon)
    params = E.params() + [{"key": k, "value": v, "from_video": False,
                            "note": "owner rule — not from the video (backtest)"}
                           for k, v in BACKTEST_PARAMS.items()]
    doc = {
        "as_of": now.isoformat(), "span_start": span_start.isoformat(), "span_end": today.isoformat(),
        "fetch_start": fetch_start.isoformat(), "horizon": int(horizon),
        "args": {"names": names, "months": months, "seed": seed, "workers": workers,
                 "resume": bool(resume), "minute_source": minute_source},
        "universe_size": universe_size, "sample": sample,
        "per_symbol": [{k: v for k, v in p.items() if k not in ("signals", "confirmed")} for p in per_symbol],
        "summary": summary, "context": context,
        "signals": signals, "confirmed": confirmed,
        "caveats": list(CAVEATS), "params": params, "source": E.SOURCE,
        "seconds": round(time.time() - t0, 1),
    }
    log.info("ict.backtest: done — %d symbols, %d signals (%d resolved), %d confirmed-only, %.0fs",
             len(per_symbol), summary["overall"]["n"], summary["overall"]["resolved"],
             summary["confirmed_total"] - summary["confirmed_entered_later"], doc["seconds"])
    return doc


def write_outputs(doc: dict, out: Optional[str], md: Optional[str]) -> None:
    if out:
        with open(out, "w") as fh:
            json.dump(doc, fh, indent=1, default=str)
    if md:
        with open(md, "w") as fh:
            fh.write(render_markdown(doc))


def main(argv=None, **overrides) -> dict:
    import argparse
    ap = argparse.ArgumentParser(description="Walk-forward backtest of the ICT board (no lookahead)")
    ap.add_argument("--names", type=int, default=300, help="random sample size from big_cap_universe")
    ap.add_argument("--months", type=int, default=6)
    ap.add_argument("--out", default="/tmp/ict_bt.json")
    ap.add_argument("--md", default="/tmp/ict_bt.md")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--resume", action="store_true", help="skip symbols already in <out>.partial.jsonl")
    ap.add_argument("--symbols", default="", help="comma-separated override of the sample")
    ap.add_argument("--horizon", type=int, default=HORIZON_SESSIONS)
    ap.add_argument("--minute-source", default="cache", choices=("cache", "range"),
                    help="cache = load_intraday_range per day (Mongo-cached); range = one paged provider call")
    a = ap.parse_args(argv)
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()] or None
    kw = dict(names=a.names, months=a.months, seed=a.seed, workers=a.workers, out=a.out,
              resume=a.resume, symbols=syms, horizon=a.horizon, minute_source=a.minute_source)
    kw.update(overrides)
    doc = run(**kw)
    write_outputs(doc, a.out, a.md)
    ov = doc["summary"]["overall"]
    log.info("ict.backtest: wrote %s and %s — signals=%d resolved=%d median_ret_r=%s placebo=%s",
             a.out, a.md, ov["n"], ov["resolved"], ov["median_ret_at_horizon_r"],
             doc["summary"]["placebo"]["median_ret_at_horizon_r"])
    return doc


if __name__ == "__main__":
    main()
