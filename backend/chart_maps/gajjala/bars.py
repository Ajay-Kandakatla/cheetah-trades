"""Closed 5- and 15-minute frames for the listed names (spec §3.1.4) — the detectors' ONLY input.

Two sessions of 1-minute Massive bars (the prior market day from the cache, today re-fetched), pre-market and
after-hours included, resampled by the house resampler (`timeframes.resample_ohlcv`: LEFT-closed, RIGHT-labelled —
the bar stamped 10:05 holds 10:00–10:04). A bar counts only once its right label is BAR_SETTLE_SEC in the past:
the detectors never see a bucket still printing. The 9/21 EMAs (`orderflow.signals.ema`, the one definition) run
over the whole 2-session frame, extended hours included, with the first `period − 1` bars masked to None — warm-up
is a gap, never a guess (the chart_maps.board rule). Legs and bases use TODAY's bars only; the prior session only
warms the EMAs, K1's 20-bar range average and the 50-bar volume average.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable, Optional

import pandas as pd

from chart_maps import board
from chart_maps.support import _frame_bars, _intraday_stamp
from orderflow.signals import ema

from . import constants as GC

log = logging.getLogger("chart_maps.gajjala.bars")

RULES = {"5m": "5min", "15m": "15min"}
EMA_TONES = (("ema9", "9 EMA", GC.EMA_FAST), ("ema21", "21 EMA", GC.EMA_SLOW))


@dataclass
class Frame:
    """One timeframe, CLOSED bars only, oldest first, prior session + today (the detectors' `F`)."""
    o: list
    h: list
    l: list                                                     # noqa: E741 — the spec's name
    c: list
    v: list
    t: list                                                     # ET stamps "%Y-%m-%d %H:%M" = the bar's CLOSE time
    session: list                                               # premarket | rth | afterhours per bar
    ema9: list                                                  # float | None (warm-up)
    ema21: list
    today: range                                                # indices of today's bars
    df: pd.DataFrame = field(repr=False)                        # the same bars (+ ema9 / ema21 columns), UTC index
    minutes: dict = field(default_factory=dict, repr=False)     # t[j] -> that bucket's 1-min (o, h, l, c, v), today only
    frame: str = "5m"                                           # "5m" | "15m" (the detectors' Read.frame)

    def __len__(self) -> int:
        return len(self.t)


@dataclass
class Frames:
    """Both timeframes for one symbol + the 1-minute bars inside each of today's closed buckets."""
    symbol: str
    session: str
    f5: Frame
    f15: Frame
    minutes5: dict                                              # bar_t -> [(o, h, l, c, v) 1-min, time order]
    minutes15: dict
    raw: pd.DataFrame = field(repr=False)                       # the 1-minute bars (both sessions, UTC index)

    @property
    def df5(self) -> pd.DataFrame:
        return self.f5.df

    @property
    def df15(self) -> pd.DataFrame:
        return self.f15.df

    @property
    def today_idx5(self) -> range:
        return self.f5.today

    @property
    def today_idx15(self) -> range:
        return self.f15.today

    @property
    def as_of_bar_t5(self) -> Optional[str]:
        return self.f5.t[-1] if self.f5.t else None

    @property
    def as_of_bar_t15(self) -> Optional[str]:
        return self.f15.t[-1] if self.f15.t else None

    @property
    def as_of_bar_t(self) -> dict:
        """{"5m": stamp, "15m": stamp} — pushability is judged per frame (the latest CLOSED bar of THAT frame)."""
        return {"5m": self.as_of_bar_t5, "15m": self.as_of_bar_t15}

    @property
    def minutes(self) -> dict:
        return {"5m": self.minutes5, "15m": self.minutes15}

    def frame(self, tf: str) -> Frame:
        return self.f15 if tf == "15m" else self.f5

    def detector_frames(self) -> dict:
        """{"5m": Frame, "15m": Frame} — the shape `detectors.read_all(frames, ctx)` takes (each carries `minutes`)."""
        return {"5m": self.f5, "15m": self.f15}


def _utc_naive(now) -> pd.Timestamp:
    """Any clock (aware, or naive = UTC like the minute loader's index) -> a naive UTC Timestamp."""
    ts = pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz="UTC")
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts


def closed_only(df, now):
    """Bars whose right label (= close time) is at least BAR_SETTLE_SEC before `now`."""
    if df is None or len(df) == 0:
        return df
    cutoff = _utc_naive(now) - pd.Timedelta(seconds=GC.BAR_SETTLE_SEC)
    return df[df.index <= cutoff]


def _masked_ema(close: pd.Series, period: int) -> list:
    vals = ema(close.astype(float), period).tolist()
    out = [None if (x is None or x != x) else round(float(x), 6) for x in vals]
    for i in range(min(period - 1, len(out))):
        out[i] = None
    return out


def build_frame(closed: pd.DataFrame, session_iso: str, rule: str) -> Frame:
    """`Frame` over an already-closed resampled frame; `today` = bars whose bucket STARTS on the session date."""
    df = closed.copy()
    n = len(df)
    e9 = _masked_ema(df["close"], GC.EMA_FAST) if n else []
    e21 = _masked_ema(df["close"], GC.EMA_SLOW) if n else []
    df["ema9"] = pd.Series(e9, index=df.index, dtype=object)     # None stays None (warm-up is a gap)
    df["ema21"] = pd.Series(e21, index=df.index, dtype=object)
    starts = ((df.index - pd.Timedelta(rule)).tz_localize("UTC").tz_convert("America/New_York")
              .strftime("%Y-%m-%d").tolist() if n else [])
    first = next((i for i, d in enumerate(starts) if d == session_iso), n)
    sess = (df["session"].astype(str).tolist() if "session" in df.columns else [""] * n)
    return Frame(o=df["open"].astype(float).tolist(), h=df["high"].astype(float).tolist(),
                 l=df["low"].astype(float).tolist(), c=df["close"].astype(float).tolist(),
                 v=(df["volume"].astype(float).tolist() if "volume" in df.columns else [0.0] * n),
                 t=[_intraday_stamp(ts) for ts in df.index], session=sess, ema9=e9, ema21=e21,
                 today=range(first, n), df=df, frame=next(k for k, r in RULES.items() if r == rule))


def _minutes_by_bucket(raw: pd.DataFrame, frame: Frame, rule: str) -> dict:
    """{bar_t: [(o, h, l, c, v), …]} — the 1-minute bars inside each of TODAY's closed buckets, time order."""
    if raw is None or raw.empty or not len(frame.today):
        return {}
    want = {frame.t[i] for i in frame.today}
    first_label = frame.df.index[frame.today.start]
    raw = raw[raw.index >= first_label - pd.Timedelta(rule)]          # today's buckets only
    labels = raw.index.floor(rule) + pd.Timedelta(rule)
    names = {ts: _intraday_stamp(ts) for ts in labels.unique()}     # one stamp per bucket, the support format
    stamps = [names[ts] for ts in labels]
    vol = raw["volume"].astype(float).fillna(0.0).tolist() if "volume" in raw.columns else [0.0] * len(raw)
    out: dict = {}
    for st, o, h, l, c, v in zip(stamps, raw["open"].astype(float).tolist(), raw["high"].astype(float).tolist(),
                                 raw["low"].astype(float).tolist(), raw["close"].astype(float).tolist(), vol):
        if st in want:
            out.setdefault(st, []).append((o, h, l, c, v))
    return out


def build_frames(symbol: str, session, now, raw_prev, raw_today) -> Optional[Frames]:
    """Frames from the two raw 1-minute days; None when today has no bars yet (nothing to read)."""
    from supply_demand.timeframes import resample_ohlcv
    session_iso = session.isoformat() if isinstance(session, (date, datetime)) else str(session)
    if raw_today is None or len(raw_today) == 0:
        return None
    parts = [p for p in (raw_prev, raw_today) if p is not None and len(p)]
    raw = pd.concat(parts).sort_index()
    raw = raw[~raw.index.duplicated(keep="last")]
    out = {}
    for tf, rule in RULES.items():
        res = resample_ohlcv(raw, rule)
        closed = closed_only(res, now) if res is not None else None
        if closed is None or closed.empty:
            closed = pd.DataFrame(columns=["open", "high", "low", "close", "volume"],
                                  index=pd.DatetimeIndex([]))
        out[tf] = build_frame(closed, session_iso, rule)
    if not len(out["5m"].today):
        return None
    for tf, rule in RULES.items():
        out[tf].minutes = _minutes_by_bucket(raw, out[tf], rule)
    return Frames(symbol=symbol, session=session_iso, f5=out["5m"], f15=out["15m"],
                  minutes5=out["5m"].minutes, minutes15=out["15m"].minutes, raw=raw)


def frames_for(symbols, session, now, *, load_day: Optional[Callable] = None, workers: int = board.BAR_WORKERS,
               budget_sec: float = GC.PASS_BUDGET_SEC, stats: Optional[dict] = None) -> dict:
    """{SYM: Frames} for the listed names. The prior market day comes from the 1-minute cache; today is fetched
    with `force=True` (never cached — the loader's ET "today"). A name that raises, has no bar today, or would
    start after `budget_sec` is skipped; `stats` (filled in place) counts each: loaded / no_bars / failed /
    over_budget. A None that came from a PROVIDER failure (the 429 cap, the breaker open, non-200 —
    `dt_data.last_fetch_failed`) counts as failed, never as "no bar today". The loader is asked in Massive's
    spelling (`symbols.for_massive`: MOG-A → MOG.A — Massive returns nothing for the dash form); the dict key stays
    the listed (dash) symbol."""
    from daytrading import data as dt_data
    from catalysts.medical.reaction import prev_market_day
    from sepa.symbols import for_massive
    load = load_day or dt_data.load_intraday
    d = session if isinstance(session, date) else date.fromisoformat(str(session))
    prev = prev_market_day(d)
    deadline = time.monotonic() + float(budget_sec)
    st = stats if stats is not None else {}
    for k in ("loaded", "no_bars", "failed", "over_budget"):
        st.setdefault(k, 0)

    def one(sym: str):
        if time.monotonic() > deadline:
            return sym, None, "over_budget"
        try:
            msym = for_massive(sym)
            dt_data.clear_fetch_failed()
            raw_prev = load(msym, prev, include_premarket=True, include_afterhours=True)
            failed = raw_prev is None and dt_data.last_fetch_failed()
            dt_data.clear_fetch_failed()
            raw_today = load(msym, d, force=True, include_premarket=True, include_afterhours=True)
            failed = failed or (raw_today is None and dt_data.last_fetch_failed())
            fr = build_frames(sym, d, now, raw_prev, raw_today)
            if fr is None:
                return sym, None, ("failed" if failed else "no_bars")
            return sym, fr, "loaded"
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala bars %s failed: %s", sym, exc)
            return sym, None, "failed"

    syms = [s for s in dict.fromkeys(symbols or []) if s]
    out: dict = {}
    if not syms:
        return out
    with ThreadPoolExecutor(max_workers=max(1, min(int(workers), len(syms)))) as ex:
        for sym, fr, status in ex.map(one, syms):
            st[status] += 1
            if fr is not None:
                out[sym] = fr
    return out


def tile_payload(frames: Frames, tf: str) -> dict:
    """{bars, curves, vol_avg} for one tile: today's closed bars (`support._frame_bars`, `s` flags kept), the 9/21
    EMA curves aligned BY STAMP, and the served 50-bar volume average computed over the FULL 2-session frame
    (`board._vol_avg_series`, the `_ma_series` rule) and cut to today's stamps — so it exists from today's first
    bar. An all-None curve or average is OMITTED (a line of nulls claims the average exists)."""
    f = frames.frame(tf)
    today_df = f.df.iloc[f.today.start:f.today.stop]
    bars = _frame_bars(today_df)
    curves = []
    for tone, label, _p in EMA_TONES:
        col = getattr(f, tone)
        vals = [col[i] for i in f.today]
        if any(v is not None for v in vals):
            curves.append({"tone": tone, "label": label, "values": vals})
    out = {"bars": bars, "curves": curves, "vol_avg": None}
    if bars:
        try:
            ser = board._vol_avg_series(f.df, stamp=_intraday_stamp)
        except Exception as exc:                                # noqa: BLE001
            log.debug("gajjala vol_avg failed: %s", exc)
            ser = None
        if ser:
            by = {d: i for i, d in enumerate(ser.get("dates") or [])}
            col = ser.get("values") or []
            vals = [col[by[b["t"]]] if b["t"] in by else None for b in bars]
            if any(v is not None for v in vals):
                out["vol_avg"] = {"period": board.VOL_AVG_PERIOD, "label": board.VOL_AVG_LABEL, "values": vals}
    return out
