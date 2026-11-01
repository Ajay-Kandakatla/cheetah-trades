"""🥇 Luk's frames (spec §3.5) — 1-minute, 5-minute and hourly bars per shortlisted name, the detectors' ONLY input.

GG's engines by import, no copy: the house resampler (`timeframes.resample_ohlcv`, LEFT-closed, RIGHT-labelled), GG's
settle rule (`gajjala.bars.closed_only` — a bar counts once its right label is GC.BAR_SETTLE_SEC old), GG's `Frame` /
`Frames` / `build_frame` (9/21 EMAs masked through warm-up) and `_minutes_by_bucket`.

  1m / 5m   every minute of the prior LC.LUK_HOURLY_SESSIONS sessions + today, pre-market and after-hours included
            (each bar carries its `session` tag, like GG's frames)
  60m       RTH minutes only (LC.LUK_HOURLY_SESSION) — his hourly 9 / 21 EMA (E2) = this frame's ema9 / ema21. The
            buckets are CLOCK-anchored (the house resampler; the first RTH bar 09:30–10:00 is a half hour); TradingView
            anchors 09:30 — a fact, HIS CALL #7.

Every lookback a detector judges reads THROUGH the judged bar (spec C7 / C8): `rth_low(F, through_t)` never sees a low
printed after `through_t`; `hourly_ref(F, before_t)` is the last hourly bar CLOSED by `before_t`, never "as of now".
Times: Frame stamps are ET "%Y-%m-%d %H:%M" = the bar's CLOSE; a datetime argument is converted to ET (a naive one is
read as the ET wall clock — the same convention as `latest_closed_t`'s return).
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time as dtime
from typing import Callable, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from chart_maps import board
from chart_maps.gajjala import bars as GB

from . import constants as LC
from .variant import LUK

log = logging.getLogger("chart_maps.luk.bars")

ET = ZoneInfo("America/New_York")
STAMP_FMT = "%Y-%m-%d %H:%M"
ONE_MIN, FIVE_MIN, HOURLY = "1m", "5m", "60m"
# GG's `build_frame` names a frame from its own RULE_OF (1m / 5m / 15m); the hourly frame is built through it with a
# 15-minute bucket width and relabelled — `today` = the bucket START's ET date, identical for RTH-only hourly buckets
# (none crosses midnight), and the bars / EMAs do not read the rule at all.
_PROXY_RULE = "15min"


def _iso(session) -> str:
    return session.isoformat() if isinstance(session, (date, datetime)) else str(session)


def _as_date(session) -> date:
    if isinstance(session, datetime):
        return session.date()
    return session if isinstance(session, date) else date.fromisoformat(str(session))


def _stamp(t) -> Optional[str]:
    """Any time → the Frame stamp format: an aware datetime → ET; a naive one = ET wall clock; a str → its first 16
    chars (already a stamp); None → None."""
    if t is None:
        return None
    if isinstance(t, str):
        return t[:16]
    if isinstance(t, pd.Timestamp):
        t = t.to_pydatetime()
    if isinstance(t, datetime):
        if t.tzinfo is not None:
            t = t.astimezone(ET)
        return t.strftime(STAMP_FMT)
    raise TypeError(f"not a time: {t!r}")


def _parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, STAMP_FMT).replace(tzinfo=ET)


def _frame(fr: Optional["GB.Frames"], tf: str) -> Optional["GB.Frame"]:
    if fr is None:
        return None
    by = getattr(fr, "by", None) or {}
    return by.get(tf)


# ── loading ────────────────────────────────────────────────────────────────────────────────────────────────────
def load_days(sym: str, session, *, load_day: Callable) -> tuple:
    """(raw_prior: [df…] oldest first, raw_today: df | None, failed: bool). The prior LC.LUK_HOURLY_SESSIONS market
    days (`gajjala.context.history_window`, the house calendar) through the minute cache; today `force=True`. Asked in
    Massive's spelling (`sepa.symbols.for_massive`). `failed` = a None that came from a PROVIDER failure
    (`daytrading.data.last_fetch_failed`), never an empty day."""
    from chart_maps.gajjala.context import history_window
    from daytrading import data as dt_data
    from sepa.symbols import for_massive
    d = _as_date(session)
    msym = for_massive(sym)
    failed = False
    prior = []
    for day in history_window(d, LC.LUK_HOURLY_SESSIONS):
        dt_data.clear_fetch_failed()
        df = load_day(msym, day, include_premarket=True, include_afterhours=True)
        if df is None:
            failed = failed or dt_data.last_fetch_failed()
        elif len(df):
            prior.append(df)
    dt_data.clear_fetch_failed()
    today = load_day(msym, d, force=True, include_premarket=True, include_afterhours=True)
    if today is None:
        failed = failed or dt_data.last_fetch_failed()
    return prior, today, bool(failed)


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=["open", "high", "low", "close", "volume"], index=pd.DatetimeIndex([]))


def _build_one(raw: pd.DataFrame, now, session_iso: str, tf: str, rule: str) -> "GB.Frame":
    from supply_demand.timeframes import resample_ohlcv
    res = resample_ohlcv(raw, rule) if raw is not None and len(raw) else None
    closed = GB.closed_only(res, now) if res is not None else None
    if closed is None or closed.empty:
        closed = _empty()
    if tf in GB.RULE_OF and GB.RULE_OF[tf] == rule:
        fr = GB.build_frame(closed, session_iso, rule)
    else:
        fr = GB.build_frame(closed, session_iso, _PROXY_RULE)
        fr.frame = tf
    fr.minutes = GB._minutes_by_bucket(raw, fr, rule) if raw is not None and len(raw) else {}
    return fr


def build(symbol: str, session, now, raw_prior, raw_today) -> Optional["GB.Frames"]:
    """Frames {"1m", "5m", "60m"} (LUK.rules order) from the prior days + today. 1m / 5m read every minute (pre + RTH +
    AH); 60m reads RTH minutes only. None when the 5-minute frame (LUK.primary) has no closed bar today."""
    if raw_today is None or len(raw_today) == 0:
        return None
    session_iso = _iso(session)
    parts = [p for p in list(raw_prior or []) + [raw_today] if p is not None and len(p)]
    raw = pd.concat(parts).sort_index()
    raw = raw[~raw.index.duplicated(keep="last")]
    if "session" in raw.columns:
        rth = raw[raw["session"].astype(str) == LC.LUK_HOURLY_SESSION]
    else:
        rth = raw.iloc[0:0]
    by = {}
    for tf, rule in LUK.rules:
        src = rth if tf == HOURLY else raw
        by[tf] = _build_one(src, now, session_iso, tf, rule)
    if not len(by[LUK.primary].today):
        return None
    return GB.Frames(symbol, session_iso, by, raw, primary=LUK.primary, slow=LUK.slow)


def frames_for(symbols, session, now, *, load_day: Optional[Callable] = None, budget_sec: float,
               stats: Optional[dict] = None, workers: int = board.BAR_WORKERS) -> dict:
    """{SYM: Frames} for the shortlist — gajjala.bars.frames_for's shape: a name that would START after `budget_sec`
    is `over_budget`, a raise or a provider-failed None is `failed`, no closed 5-minute bar today is `no_bars`; `stats`
    is filled in place (loaded / no_bars / failed / over_budget). The dict key stays the listed symbol."""
    from daytrading import data as dt_data
    load = load_day or dt_data.load_intraday
    deadline = time.monotonic() + float(budget_sec)
    st = stats if stats is not None else {}
    for k in ("loaded", "no_bars", "failed", "over_budget"):
        st.setdefault(k, 0)

    def one(sym: str):
        if time.monotonic() > deadline:
            return sym, None, "over_budget"
        try:
            prior, today, failed = load_days(sym, session, load_day=load)
            fr = build(sym, session, now, prior, today)
            if fr is None:
                return sym, None, ("failed" if failed else "no_bars")
            return sym, fr, "loaded"
        except Exception as exc:                                # noqa: BLE001
            log.warning("luk bars %s failed: %s", sym, exc)
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


# ── reads (pure) ───────────────────────────────────────────────────────────────────────────────────────────────
def latest_closed_t(F, tf: str) -> Optional[datetime]:
    """ET-aware CLOSE time of the last closed bar of frame `tf` dated today; None when the frame has none today."""
    f = _frame(F, tf)
    if f is None or not len(f.today):
        return None
    return _parse(f.t[f.today[-1]])


def _rth_today(F, through_t) -> list:
    f = _frame(F, ONE_MIN)
    if f is None:
        return []
    cut = _stamp(through_t)
    return [i for i in f.today
            if f.session[i] == LC.LUK_LOD_SESSION and (cut is None or f.t[i] <= cut)]


def rth_low(F, through_t=None) -> Optional[float]:
    """Today's regular-session low (LC.LUK_LOD_SESSION — pre-market excluded) over the 1-minute bars CLOSED by
    `through_t` (spec C7: a later low never moves a judged read). `through_t` None = every closed bar — `forming` only."""
    idx = _rth_today(F, through_t)
    f = _frame(F, ONE_MIN)
    return min(f.l[i] for i in idx) if idx else None


def rth_high(F, through_t=None) -> Optional[float]:
    """Today's regular-session high over the 1-minute bars closed by `through_t` (None = every closed bar)."""
    idx = _rth_today(F, through_t)
    f = _frame(F, ONE_MIN)
    return max(f.h[i] for i in idx) if idx else None


def hourly_ref(F, before_t) -> Optional[dict]:
    """{"ema9", "ema21", "bar_t"} of the LAST hourly bar whose CLOSE ≤ `before_t` (spec C8 — the judged 5-minute
    bar's OPEN): a 5-minute bar opening before 10:00 ET reads yesterday's last hourly bar; the 10:00 hourly bar (which
    holds the flush itself) is first usable by the bar opening 10:00. EMAs may be None (warm-up). None when no hourly
    bar closed by then."""
    f = _frame(F, HOURLY)
    cut = _stamp(before_t)
    if f is None or cut is None:
        return None
    j = None
    for i, t in enumerate(f.t):
        if t <= cut:
            j = i
        else:
            break
    if j is None:
        return None
    return {"ema9": f.ema9[j], "ema21": f.ema21[j], "bar_t": f.t[j]}


def frame_for_close(t_et_time, *, switch_min) -> Optional[str]:
    """Which frame his trigger reads at a bar CLOSE time (ET): close ≤ 09:30 + `switch_min` → "1m"; ≤ 09:30 +
    LC.LUK_TRIGGER_WINDOW_END_MIN → "5m"; else (or at / before the open) None. Pullback: switch_min =
    LC.LUK_ONE_MIN_UNTIL_MIN; opening range: switch_min = LC.LUK_ORH_SWITCH_MIN (HIS CALL #6)."""
    from daytrading.data import ET_RTH_OPEN
    if isinstance(t_et_time, datetime):
        if t_et_time.tzinfo is not None:
            t_et_time = t_et_time.astimezone(ET)
        t_et_time = t_et_time.time()
    if not isinstance(t_et_time, dtime):
        return None
    sec = (t_et_time.hour * 3600 + t_et_time.minute * 60 + t_et_time.second) - (
        ET_RTH_OPEN.hour * 3600 + ET_RTH_OPEN.minute * 60)
    if sec <= 0:
        return None
    if sec <= float(switch_min) * 60:
        return ONE_MIN
    if sec <= float(LC.LUK_TRIGGER_WINDOW_END_MIN) * 60:
        return FIVE_MIN
    return None
