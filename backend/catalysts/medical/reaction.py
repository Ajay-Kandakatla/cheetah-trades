"""🧬 Medical catalysts — price reaction WITHOUT lookahead (spec §3.7).

PURE: no I/O. Every function takes the frame / snapshot it reads.

Frames are `sepa.prices.bulk_cached_frames` shapes (DatetimeIndex; columns
open high low close volume). THE LIVE-BAR OVERLAY TRAP (memory
cheetah_live_bar_overlay): the Mongo price cache is patched hourly with
TODAY's in-progress bar, so a daily frame read intraday carries a bar that
is not closed. `closed_frame` drops a bar dated today before
CLOSE_FILL_AFTER_ET (after the 16:30 fast-scan refresh) and every future bar;
every block below reads only what `closed_frame` leaves.

  * the BASE is the close of the market day BEFORE the event session — the
    closed bar when the frame has it, else the snapshot's prior close
    (stamped with its basis), else unknown (the push gate fails closed);
  * liquidity uses ONLY bars dated before the session (a +178% event bar can
    never inflate its own ADV);
  * `at_close` exists only once the session's own bar is closed;
  * `forward` counts sessions strictly after the event session.

UNMEASURED: these are descriptions of what a stock did, not a prediction.
"""
from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

ADV_SESSIONS = 50
PRE_RET_SESSIONS = 20
FWD_SESSIONS = (5, 21)
CLOSE_FILL_AFTER_ET = time(16, 45)     # after the 16:30 fast-scan frame refresh; else next run/morning
_HALF_DAY_CLOSE = time(13, 0)
_OVERNIGHT_END = time(4, 0)            # daytrading.data.ET_PREMARKET_OPEN
_AFTERHOURS_END = time(20, 0)          # daytrading.data.ET_AFTERHOURS_CLOSE


# ---------------------------------------------------------------------------
# calendar
# ---------------------------------------------------------------------------
def _rth_bounds():
    from daytrading.data import ET_RTH_OPEN, ET_RTH_CLOSE
    return ET_RTH_OPEN, ET_RTH_CLOSE


def _half_days() -> set:
    from supply_demand.timeframes import HALF_DAYS
    return set(HALF_DAYS)


def is_market_day(d: date) -> bool:
    from market_hours.reminder import is_market_day as _imd
    return bool(_imd(datetime(d.year, d.month, d.day, 12, 0)))


def rth_close_time(d: date) -> time:
    """16:00 ET; 13:00 on a supply_demand.timeframes.HALF_DAYS date."""
    _o, c = _rth_bounds()
    return _HALF_DAY_CLOSE if d.isoformat() in _half_days() else c


def next_market_day(d: date) -> date:
    n = d + timedelta(days=1)
    for _ in range(15):
        if is_market_day(n):
            return n
        n += timedelta(days=1)
    return n


def prev_market_day(d: date) -> date:
    n = d - timedelta(days=1)
    for _ in range(15):
        if is_market_day(n):
            return n
        n -= timedelta(days=1)
    return n


def add_market_days(d: date, n: int) -> date:
    out = d
    step = next_market_day if n >= 0 else prev_market_day
    for _ in range(abs(int(n))):
        out = step(out)
    return out


def as_et(ts) -> Optional[datetime]:
    """epoch seconds / aware datetime / naive (UTC) datetime / ISO -> ET datetime."""
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        if ts != ts:
            return None
        if ts > 1e12:
            ts = ts / 1000.0
        return datetime.fromtimestamp(float(ts), tz=ZoneInfo("UTC")).astimezone(ET)
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=ZoneInfo("UTC"))
        return ts.astimezone(ET)
    return None


def session_date_for(published_et: datetime) -> date:
    """Market day D and t < the RTH close (13:00 on HALF_DAYS) -> D; else the
    next market day (after the bell, a weekend, a holiday)."""
    p = as_et(published_et)
    d = p.date()
    if is_market_day(d) and p.time() < rth_close_time(d):
        return d
    return next_market_day(d)


def released_bucket(published_et: datetime) -> str:
    """premarket | intraday | afterhours | closed_day | overnight."""
    p = as_et(published_et)
    d = p.date()
    if not is_market_day(d):
        return "closed_day"
    t = p.time()
    o, _c = _rth_bounds()
    close = rth_close_time(d)
    if t < _OVERNIGHT_END or t >= _AFTERHOURS_END:
        return "overnight"
    if t < o:
        return "premarket"
    if t < close:
        return "intraday"
    return "afterhours"


def prev_regular_close(now_et: datetime) -> datetime:
    """The last regular-session close strictly before `now_et`."""
    n = as_et(now_et)
    d = n.date()
    if is_market_day(d):
        c = datetime.combine(d, rth_close_time(d), tzinfo=ET)
        if c < n:
            return c
    p = prev_market_day(d)
    return datetime.combine(p, rth_close_time(p), tzinfo=ET)


def rth_minutes_between(a_et: datetime, b_et: datetime) -> float:
    """Regular-session minutes inside [a, b] — market days only, ET_RTH_OPEN
    to ET_RTH_CLOSE (13:00 on HALF_DAYS); 0 when b <= a. Feeds the push
    gate's `stale` rule (how long the regular session has traded the news)."""
    a, b = as_et(a_et), as_et(b_et)
    if a is None or b is None or b <= a:
        return 0.0
    o, _c = _rth_bounds()
    total = 0.0
    d = a.date()
    for _ in range(400):
        if d > b.date():
            break
        if is_market_day(d):
            s = max(a, datetime.combine(d, o, tzinfo=ET))
            e = min(b, datetime.combine(d, rth_close_time(d), tzinfo=ET))
            if e > s:
                total += (e - s).total_seconds() / 60.0
        d += timedelta(days=1)
    return round(total, 4)


# ---------------------------------------------------------------------------
# frames
# ---------------------------------------------------------------------------
def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v or math.isinf(v):
        return None
    return v


def _bar_dates(frame) -> list:
    out = []
    for ts in frame.index:
        try:
            out.append(ts.date() if hasattr(ts, "date") else date.fromisoformat(str(ts)[:10]))
        except Exception:                                   # noqa: BLE001
            out.append(None)
    return out


def closed_frame(frame, now_et: Optional[datetime]):
    """The frame with every bar that is not yet a CLOSED session removed: a
    future bar, and a bar dated today before CLOSE_FILL_AFTER_ET (the cache's
    in-progress patch). `now_et=None` returns the frame unchanged."""
    if frame is None or now_et is None:
        return frame
    try:
        if len(frame) == 0:
            return frame
    except TypeError:
        return None
    n = as_et(now_et)
    today = n.date()
    keep = []
    for d in _bar_dates(frame):
        if d is None:
            keep.append(False)
        elif d > today:
            keep.append(False)
        elif d == today and n.time() < CLOSE_FILL_AFTER_ET:
            keep.append(False)
        else:
            keep.append(True)
    return frame[keep]


def _bar_on(frame, d: date):
    if frame is None:
        return None
    for i, bd in enumerate(_bar_dates(frame)):
        if bd == d:
            return frame.iloc[i]
    return None


def _before(frame, d: date):
    if frame is None:
        return None
    mask = [bd is not None and bd < d for bd in _bar_dates(frame)]
    return frame[mask]


def base_close(frame, snap: Optional[dict], session_date: date, now_et: datetime) -> tuple:
    """(close, basis) of the market day before `session_date`.
    1. frame bar dated prev_market_day(session_date)          -> "frame"
    2. snapshot: today is that prior day and it has closed      -> snap["price"], "snapshot_day_close"
                 today is the session day, before its close      -> snap["prev_day_close"], "snapshot_prev_close"
    3. else (None, "unknown") — the push gate fails CLOSED."""
    prior = prev_market_day(session_date)
    bar = _bar_on(frame, prior)
    if bar is not None:
        c = _f(bar.get("close"))
        if c is not None and c > 0:
            return c, "frame"
    n = as_et(now_et)
    snap = snap or {}
    if n is not None:
        if n.date() == prior and n.time() >= rth_close_time(prior):
            c = _f(snap.get("price"))
            if c is not None and c > 0:
                return c, "snapshot_day_close"
        if n.date() == session_date and n.time() < rth_close_time(session_date):
            c = _f(snap.get("prev_day_close"))
            if c is not None and c > 0:
                return c, "snapshot_prev_close"
    return None, "unknown"


def liquidity(frame, session_date: date) -> dict:
    """ONLY bars dated < session_date. adv50 = median(close × volume) of the
    last ADV_SESSIONS; avg_vol50 = mean(volume); pre_ret_20d_pct = the
    PRE_RET_SESSIONS-session return into the event."""
    out = {"adv50_usd": None, "avg_vol50": None, "pre_ret_20d_pct": None, "frame_last_date": None}
    pre = _before(frame, session_date)
    if pre is None or len(pre) == 0:
        return out
    last = pre.tail(ADV_SESSIONS)
    closes = [_f(x) for x in last["close"].tolist()]
    vols = [_f(x) for x in last["volume"].tolist()]
    dv = sorted(c * v for c, v in zip(closes, vols) if c is not None and v is not None)
    if dv:
        m = len(dv) // 2
        out["adv50_usd"] = dv[m] if len(dv) % 2 else (dv[m - 1] + dv[m]) / 2.0
    vv = [v for v in vols if v is not None]
    if vv:
        out["avg_vol50"] = sum(vv) / len(vv)
    allc = [_f(x) for x in pre["close"].tolist()]
    if len(allc) > PRE_RET_SESSIONS and allc[-1] and allc[-1 - PRE_RET_SESSIONS]:
        out["pre_ret_20d_pct"] = (allc[-1] / allc[-1 - PRE_RET_SESSIONS] - 1.0) * 100.0
    d = _bar_dates(pre)[-1]
    out["frame_last_date"] = d.isoformat() if d else None
    return out


def _ms_to_et(ms) -> Optional[datetime]:
    v = _f(ms)
    if v is None or v <= 0:
        return None
    if v > 1e15:                                            # Massive trade stamps are ns
        v = v / 1e6
    elif v < 1e11:
        v = v * 1000.0
    return datetime.fromtimestamp(v / 1000.0, tz=ZoneInfo("UTC")).astimezone(ET)


def at_detection(snap: Optional[dict], base: tuple, now_et: datetime, *, avg_vol50=None,
                 published_et: Optional[datetime] = None,
                 session_date: Optional[date] = None) -> dict:
    """What he could have acted on when WE first saw the news: the live print
    (extended-hours last trade first) against the base close."""
    snap = snap or {}
    n = as_et(now_et)
    base_px, basis = (base or (None, "unknown"))
    price = _f(snap.get("last_trade_price")) or _f(snap.get("price"))
    ts = _ms_to_et(snap.get("last_trade_ts_ms"))
    try:
        from catalysts.promo_live import session_from_ts
        import pandas as pd
        sess = session_from_ts(snap.get("last_trade_ts_ms"),
                               now=pd.Timestamp(n)) if snap.get("last_trade_ts_ms") else "closed"
    except Exception:                                       # noqa: BLE001
        sess = "closed"
    move = None
    if price is not None and base_px:
        move = (price / base_px - 1.0) * 100.0
    vol = _f(snap.get("volume"))
    rvol = (vol / avg_vol50) if (vol is not None and avg_vol50) else None
    lat = None
    p = as_et(published_et)
    if p is not None and n is not None:
        lat = round((n - p).total_seconds() / 60.0, 1)
    post = None
    if session_date is not None and n is not None:
        post = n >= datetime.combine(session_date, rth_close_time(session_date), tzinfo=ET)
    return {"as_of": (ts or n).isoformat() if (ts or n) else None, "session": sess,
            "price": price, "base_close": base_px, "base_basis": basis,
            "move_pct": move, "volume_so_far": vol, "rvol_so_far": rvol,
            "latency_min": lat, "post_session": post}


def at_close(frame, session_date: date, base, avg_vol50) -> Optional[dict]:
    """The event session's CLOSED bar vs the base; None until it exists. Call
    with `closed_frame(frame, now)` — an in-progress bar must never read as a close."""
    bar = _bar_on(frame, session_date)
    if bar is None:
        return None
    base_px = base[0] if isinstance(base, tuple) else base
    o, h, l, c, v = (_f(bar.get(k)) for k in ("open", "high", "low", "close", "volume"))
    if c is None:
        return None

    def pct(x):
        return (x / base_px - 1.0) * 100.0 if (x is not None and base_px) else None
    rng = (h - l) if (h is not None and l is not None) else None
    return {"open": o, "high": h, "low": l, "close": c, "volume": v,
            "gap_pct": pct(o), "day_pct": pct(c),
            "rvol": (v / avg_vol50) if (v is not None and avg_vol50) else None,
            "dollar_volume": (c * v) if v is not None else None,
            "close_loc": ((c - l) / rng) if rng else None,
            "basis": "closed_bar"}


def forward(frame, session_date: date, base, close_of_session=None) -> dict:
    """ret_Nd = close[session+N] / base − 1; drift_5d = close[session+5] /
    close[session] − 1. Sessions strictly after the event session."""
    base_px = base[0] if isinstance(base, tuple) else base
    out = {"ret_5d_pct": None, "ret_21d_pct": None, "drift_5d_pct": None,
           "matured_5d": False, "matured_21d": False}
    if frame is None:
        return out
    dates = _bar_dates(frame)
    closes = [_f(x) for x in frame["close"].tolist()]
    idx = [i for i, d in enumerate(dates) if d == session_date]
    if not idx:
        return out
    i0 = idx[0]
    c0 = _f(close_of_session) if close_of_session is not None else closes[i0]
    for n, key in ((FWD_SESSIONS[0], "5d"), (FWD_SESSIONS[1], "21d")):
        j = i0 + n
        if j < len(closes) and closes[j] is not None:
            out[f"matured_{key}"] = True
            if base_px:
                out[f"ret_{key}_pct"] = (closes[j] / base_px - 1.0) * 100.0
            if key == "5d" and c0:
                out["drift_5d_pct"] = (closes[j] / c0 - 1.0) * 100.0
    return out


__all__ = ["ADV_SESSIONS", "PRE_RET_SESSIONS", "FWD_SESSIONS", "CLOSE_FILL_AFTER_ET",
           "session_date_for", "released_bucket", "prev_regular_close", "rth_minutes_between",
           "base_close", "liquidity", "at_detection", "at_close", "forward", "closed_frame",
           "is_market_day", "next_market_day", "prev_market_day", "add_market_days", "as_et",
           "rth_close_time"]
