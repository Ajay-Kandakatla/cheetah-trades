"""🔑 KEY LEVELS (Ajay 2026-09-25) — prior-period highs and lows on the charts.

The ask, verbatim: "Can you build be key levels in to our charts? They are
like demand zones. but very critical. … With check box give it a brigh color
in the chart. I wanna know when key levels are broken for a stock. Figure out
if they have to be recalculated by daily closing of revious day or current day
dybamincally and time frames yourself".

WHAT A KEY LEVEL IS HERE. The regular-session (RTH) high and low of the prior
day, the prior COMPLETE week (W-FRI), the prior calendar month and the last
`YEAR_BARS` closed sessions, plus today's pre-market high/low on the 5-minute
frames (fixed at `PRE_FROZEN_AT`). Every level is computed ONCE from CLOSED
daily bars (`zone_store.drop_today(df, session)` — the house closed-bar cut)
and frozen for the session; it rolls at `ROLL_AT` (= zone_edge.SESSION_CLOSE).
Only the BREAK TEST is live.

WHAT "BROKEN" MEANS. Per member level, sided by the last closed close (the
house rule: above = support, below = resistance; a close exactly AT a high
keeps it resistance, at a low keeps it support). Pre-market levels are sided
by kind (high = resistance, low = support) — they are set after that close. Beyond = through the
level by `PIERCE_PCT` (the house stop-sweep minimum, reused by name). Before
the close-confirm minute a FRESH print decides `broken`; from it, the CLOSE
decides (`closed_beyond` / `reversal` / `tested` / `intact`) and "broke" is
never served. A pierce that came back inside is a `reversal`.

DISPLAY ONLY and UNMEASURED (`MEASURED = False`): nothing in trading/, the
scans, the gates or any lane imports this module (a source-guard test pins
it). No in-house study measures these breaks; the follow-up study is
pre-registered in docs/chart_maps/key_levels_2026_09_25.md.

Spec: the key-levels build spec v2 (2026-09-25), §3.1–§3.4. Pure except
`read_first_seen`; heavy imports are lazy inside the functions.
"""
from __future__ import annotations

import logging
import math
from datetime import date, datetime, time as dtime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from scalping import candles
from supply_demand import sd_liquidity

log = logging.getLogger("supply_demand.key_levels")

ET = ZoneInfo("America/New_York")

PERIOD_RANK = {"pre": 0, "day": 1, "week": 2, "month": 3, "year": 4}
LABELS = {("day", "high"): "PDH", ("day", "low"): "PDL",
          ("week", "high"): "PWH", ("week", "low"): "PWL",
          ("month", "high"): "PMH", ("month", "low"): "PML",
          ("year", "high"): "52wH", ("year", "low"): "52wL",
          ("pre", "high"): "pre-mkt H", ("pre", "low"): "pre-mkt L"}
NAMES = {"PDH": "prior-day high", "PDL": "prior-day low",
         "PWH": "prior-week high", "PWL": "prior-week low",
         "PMH": "prior-month high", "PML": "prior-month low",
         "52wH": "52-week high", "52wL": "52-week low",
         "pre-mkt H": "pre-market high", "pre-mkt L": "pre-market low"}
# keys pinned == timeframes.DAILY / H1 / M15 / M5_TODAY / H24 by a test
FRAME_PERIODS = {"daily": ("week", "month", "year"),
                 "60m": ("day", "week", "month", "year"),
                 "15m": ("day", "week", "month", "year"),
                 "5m_today": ("pre", "day", "week", "month", "year"),
                 "24h": ("pre", "day", "week", "month", "year")}
EXT_FRAMES = ("5m_today", "24h")                 # the chart shows extended hours: labels say RTH
PUSH_PERIODS = ("week", "month", "year")         # pinned == FRAME_PERIODS["daily"]
GRID_PER_SIDE = 1
SUPPORT_PER_SIDE = 2
YEAR_BARS = 252                                  # pinned by equality with zone_store high_252
PIERCE_PCT = sd_liquidity.SWEEP_MIN_PIERCE_PCT   # through the level by this much = beyond
AT_LEVEL_PCT = candles.LEVEL_TOL_PCT             # "at the level" band (tested / merge-for-drawing)
ROLL_AT = dtime(20, 0)                           # pinned == zone_edge.SESSION_CLOSE
SESSION_START = dtime(4, 0)                      # pinned == zone_edge.SESSION_OPEN
STALE_PRINT_SEC = 180                            # pinned == zone_edge.STALE_PRINT_SEC
PRE_FROZEN_AT = dtime(9, 30)
CLOSE_CONFIRM_AT = dtime(16, 5)
CLOSE_CONFIRM_AT_HALF = dtime(13, 5)
STATE_COLL = "key_level_state"   # one doc per session: {_id: "YYYY-MM-DD", first: {key: "HH:MM"}, updated_at}
MEASURED = False
TONE, TONE_BROKEN = "key", "key_broken"
MARK = "🔑"

_HALF_CENT = 0.005 + 1e-9        # same price to the cent — a representation tolerance, not a threshold
_MINUS = "−"


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _f(v) -> Optional[float]:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _pos(v) -> Optional[float]:
    x = _f(v)
    return x if x is not None and x > 0 else None


def _et(now: Optional[datetime]) -> datetime:
    now = now or datetime.now(ET)
    if now.tzinfo is None:
        return now.replace(tzinfo=ET)
    return now.astimezone(ET)


def _is_market_day(d: date) -> bool:
    from market_hours.reminder import is_market_day
    return is_market_day(datetime.combine(d, dtime(12, 0)))


def _hhmm(t: dtime) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"


def _fmt_pct(d: Optional[float]) -> str:
    if d is None:
        return ""
    sign = "+" if d >= 0 else _MINUS
    a = abs(d)
    return f"{sign}{a:.0f}%" if a >= 10 else f"{sign}{a:.1f}%"


def _day_mmdd(iso: Optional[str], weekday: bool = False,
              ref_year: Optional[int] = None) -> str:
    """MM-DD (or 'Wed MM-DD'); the full ISO date when `ref_year` is given and
    the date falls in another year, so a 52w level set 2025-09-25 never reads
    as today's date."""
    try:
        d = date.fromisoformat(str(iso)[:10])
    except (TypeError, ValueError):
        return str(iso or "")
    if ref_year is not None and d.year != ref_year:
        return d.strftime("%a %Y-%m-%d") if weekday else d.isoformat()
    return d.strftime("%a %m-%d") if weekday else d.strftime("%m-%d")


def _word(kind: str, direction: str) -> str:
    """Facts only: returns are positive after BOTH 52w crossings (Huddart,
    Lang & Yetman 2009), so no word implies a future direction."""
    if kind == "low":
        return "under" if direction == "down" else "back over"
    return "over" if direction == "up" else "back under"


def _natural(kind: Optional[str], direction: Optional[str]) -> bool:
    """A low broken down or a high broken up — the level's own direction.
    The other two (a low reclaimed up, a high lost down) read "back over" /
    "back under" (§3.3 wording), never "broke"."""
    return (kind == "low" and direction == "down") or (kind == "high" and direction == "up")


def _arrow(direction: str) -> str:
    return "↓" if direction == "down" else "↑"


def _side(level: float, ref_close: float, kind: Optional[str] = None) -> tuple[str, str]:
    """(side, break direction) by position — the house rule. On a TIE (the
    close sat exactly on the level, e.g. a stock that closed at its week or
    52-week high) a HIGH is still resistance (break = up) and a low stays
    support (break = down): a high the price never went through is not
    support."""
    if ref_close > level:
        return "support", "down"
    if ref_close < level:
        return "resistance", "up"
    return ("resistance", "up") if kind == "high" else ("support", "down")


def _member_side(level: dict, ref_close: float) -> tuple[str, str]:
    """The side of one member. Pre-market levels are set AFTER yesterday's
    close, so the price sits inside their range at 09:30 by construction:
    they are sided by KIND (high = resistance / up, low = support / down),
    never by yesterday's close (a gap day would flip them). Every other
    member is sided by position (`_side`)."""
    kind = level.get("kind")
    if level.get("period") == "pre" and kind in ("high", "low"):
        return ("resistance", "up") if kind == "high" else ("support", "down")
    return _side(float(level["price"]), float(ref_close), kind)


def _through_pct(side: str, x: float, L: float) -> float:
    """How far x sits THROUGH L in the break direction, % of L."""
    return (L - x) / L * 100.0 if side == "support" else (x - L) / L * 100.0


def _beyond(side: str, x: Optional[float], L: float) -> bool:
    """Through L by at least PIERCE_PCT — the house sweep rule is ">=", and
    the comparison is done in % so 0.15% on a float never reads as 0.1499."""
    if x is None:
        return False
    return _through_pct(side, x, L) >= PIERCE_PCT - 1e-9


def _back_inside(side: str, x: Optional[float], L: float) -> bool:
    """Back on the original side by PIERCE_PCT (the mirror of `_beyond`)."""
    if x is None:
        return False
    return -_through_pct(side, x, L) >= PIERCE_PCT - 1e-9


def _in_buffer(x: Optional[float], L: float) -> bool:
    """Neither beyond nor back inside: within PIERCE_PCT of L either way."""
    if x is None:
        return False
    return abs(x - L) / L * 100.0 < PIERCE_PCT - 1e-9


def _came_within(side: str, X: Optional[float], L: float) -> bool:
    """X came within AT_LEVEL_PCT of L on its side, or went through by less
    than PIERCE_PCT (never beyond)."""
    if X is None:
        return False
    if _beyond(side, X, L):
        return False
    return -_through_pct(side, X, L) <= AT_LEVEL_PCT + 1e-9


def _norm_index(frame):
    import pandas as pd
    idx = pd.to_datetime(frame.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    return idx


def _rank_of_id(member_id: str) -> int:
    return PERIOD_RANK.get(str(member_id).split("_", 1)[0], -1)


# ---------------------------------------------------------------------------
# cadence
# ---------------------------------------------------------------------------
def levels_session(now: datetime) -> date:
    """Today (ET) when today trades and now < ROLL_AT; otherwise the NEXT
    market day."""
    et = _et(now)
    today = et.date()
    if _is_market_day(today) and et.time() < ROLL_AT:
        return today
    d = today + timedelta(days=1)
    for _ in range(15):
        if _is_market_day(d):
            return d
        d += timedelta(days=1)
    return d                                                    # pragma: no cover


def prev_market_day(session: date) -> date:
    """The market day before `session` (walks back at most 8 days)."""
    d = session - timedelta(days=1)
    for _ in range(8):
        if _is_market_day(d):
            return d
        d -= timedelta(days=1)
    return d


def close_confirm_at(session: date) -> dtime:
    try:
        from supply_demand.timeframes import HALF_DAYS
    except Exception:                                           # pragma: no cover
        HALF_DAYS = set()
    return CLOSE_CONFIRM_AT_HALF if session.isoformat() in HALF_DAYS else CLOSE_CONFIRM_AT


def phase(now: datetime, session: date) -> Optional[str]:
    """'pre' | 'rth' | 'close' inside the state window (session == today ET,
    a market day, SESSION_START <= t < ROLL_AT); None outside it."""
    et = _et(now)
    if et.date() != session or not _is_market_day(session):
        return None
    t = et.time()
    if t < SESSION_START or t >= ROLL_AT:
        return None
    if t < PRE_FROZEN_AT:
        return "pre"
    if t < close_confirm_at(session):
        return "rth"
    return "close"


def closed_frame(df, session: date):
    from supply_demand import zone_store
    return zone_store.drop_today(df, session)


# ---------------------------------------------------------------------------
# rows and prints
# ---------------------------------------------------------------------------
_ROW_KEYS = ("open", "high", "low", "close", "last_trade_price", "last_trade_ts_ms",
             "prev_day_close")


def row_from_snapshot(raw: Optional[dict]) -> dict:
    """bulk_snapshot row -> the engine's row shape. Non-positive = None."""
    raw = raw if isinstance(raw, dict) else {}
    return {k: _pos(raw.get(k)) for k in _ROW_KEYS}


def row_from_live(row: Optional[dict]) -> dict:
    """bulk_live_prices row (`price` = the day close) -> the same shape.
    Non-positive = None (the day fields are 0 before the open)."""
    row = row if isinstance(row, dict) else {}
    out = {k: _pos(row.get(k)) for k in _ROW_KEYS if k != "close"}
    out["close"] = _pos(row.get("price"))
    return {k: out.get(k) for k in _ROW_KEYS}


def _has_row(row: Optional[dict]) -> bool:
    return isinstance(row, dict) and any(row.get(k) is not None for k in _ROW_KEYS)


def fresh_print(row: Optional[dict], now: datetime, session: date) -> Optional[float]:
    """THE two print engines: `zone_bounce_alerts.print_from_snapshot` (the
    staleness drop) AND `prices.extended_print` (the print is dated the
    session). Anything else is None — never last evening's trade at 04:00."""
    if not isinstance(row, dict):
        return None
    from supply_demand.zone_bounce_alerts import print_from_snapshot
    from sepa import prices
    px, _stale = print_from_snapshot(row, _et(now).timestamp(), STALE_PRINT_SEC)
    if px is None:
        return None
    ep = prices.extended_print(row)
    if not ep or ep.get("date") != session.isoformat():
        return None
    return _f(px)


def _print_session(row: Optional[dict]) -> Optional[str]:
    from sepa import prices
    ep = prices.extended_print(row) if isinstance(row, dict) else None
    return (ep or {}).get("session")


def _is_after_hours_print(row: Optional[dict], session: date) -> bool:
    """The print is an after-hours trade: labelled so by the clock, OR (half
    days, when the regular session ends at 13:00 but the clock label only
    says after-hours from 16:00) stamped on the session at or after
    `close_confirm_at(session)`."""
    if _print_session(row) == "afterhours":
        return True
    from sepa import prices
    ep = prices.extended_print(row) if isinstance(row, dict) else None
    if not ep or ep.get("date") != session.isoformat():
        return False
    try:
        t = datetime.fromtimestamp(float(ep["epoch"]), tz=ET).time()
    except (KeyError, TypeError, ValueError, OverflowError, OSError):
        return False
    return t >= close_confirm_at(session)


# ---------------------------------------------------------------------------
# levels
# ---------------------------------------------------------------------------
def verify_last_row(closed, row: Optional[dict]) -> tuple[Optional[str], bool]:
    """(stale sentence | None, verified). The last closed close must equal
    the snapshot `prev_day_close` OR its day `close`, to the cent — either
    match is enough (before Massive rolls the day it is `close`, after it is
    `prev_day_close`). No snapshot price at all -> (None, False)."""
    if closed is None or len(closed) == 0:
        return None, False
    if not _has_row(row):
        return None, False
    pdc, cl = _pos(row.get("prev_day_close")), _pos(row.get("close"))
    if pdc is None and cl is None:
        return None, False
    last = _f(closed["close"].iloc[-1])
    if last is None:
        return None, False
    for official in (pdc, cl):
        if official is not None and abs(last - official) <= _HALF_CENT:
            return None, True
    d = _norm_index(closed)[-1].date().isoformat()
    official = pdc if pdc is not None else cl
    if cl is not None:
        from sepa import prices
        ep = prices.extended_print(row)
        if ep and ep.get("date") == d:
            official = cl        # the snapshot is still that bar's day: its close is the comparator
    return (f"the {d} bar in our cache is not the final close yet "
            f"({last:.2f} vs {official:.2f})"), False


def _member(period: str, kind: str, price, as_of, *, set_on=None,
            last_close_cross=None) -> Optional[dict]:
    px = _f(price)
    if px is None or px <= 0:
        return None
    label = LABELS[(period, kind)]
    return {"id": f"{period}_{kind}_{int(round(px * 100))}", "period": period,
            "kind": kind, "price": round(px, 4), "label": label, "name": NAMES[label],
            "as_of": as_of, "set_on": set_on, "last_close_cross": last_close_cross}


def _last_close_cross(closed, idx, after: date, level: float,
                      kind: Optional[str] = None) -> Optional[dict]:
    """The most recent closed bar AFTER the level's period end whose close
    went `beyond` the level from the side the PRIOR close sat on (the §3.3
    side rule and buffer, applied bar by bar). {date, direction} or None."""
    closes = closed["close"].tolist()
    days = [d.date() for d in idx]
    found = None
    for i in range(1, len(closes)):
        if days[i] <= after:
            continue
        prev, cur = _f(closes[i - 1]), _f(closes[i])
        if prev is None or cur is None:
            continue
        side, direction = _side(level, prev, kind)
        if _beyond(side, cur, level):
            found = {"date": days[i].isoformat(), "direction": direction}
    return found


def period_levels(closed, session: date, periods) -> list[dict]:
    """Members for the requested periods (day / week / month / year) from
    CLOSED daily bars. Week = the last COMPLETE W-FRI week before the
    session's week; month = the calendar month before the session's; year
    = the last YEAR_BARS bars, omitted below YEAR_BARS."""
    if closed is None or len(closed) == 0:
        return []
    import numpy as np
    import pandas as pd
    idx = _norm_index(closed)
    out: list[dict] = []
    want = set(periods or ())

    def _pair(period, sub_mask):
        sub = closed[sub_mask]
        if len(sub) == 0:
            return
        sub_idx = idx[sub_mask]
        as_of_d = sub_idx[-1].date()
        for kind, col, fn in (("high", "high", "max"), ("low", "low", "min")):
            price = getattr(sub[col], fn)()
            lcc = None
            if period in ("week", "month"):
                px = _f(price)
                lcc = _last_close_cross(closed, idx, as_of_d, px, kind) if px else None
            m = _member(period, kind, price, as_of_d.isoformat(), last_close_cross=lcc)
            if m:
                out.append(m)

    if "day" in want:
        mask = np.zeros(len(closed), dtype=bool)
        mask[-1] = True
        _pair("day", mask)
    if "week" in want:
        wk = idx.to_period("W-FRI")
        target = pd.Period(pd.Timestamp(session), freq="W-FRI") - 1
        _pair("week", np.asarray(wk == target))
    if "month" in want:
        mo = idx.to_period("M")
        target = pd.Period(pd.Timestamp(session), freq="M") - 1
        _pair("month", np.asarray(mo == target))
    if "year" in want and len(closed) >= YEAR_BARS:
        as_of = idx[-1].date().isoformat()
        tail = closed.tail(YEAR_BARS)
        tidx = idx[-YEAR_BARS:]
        for kind, col, fn, arg in (("high", "high", "max", np.nanargmax),
                                   ("low", "low", "min", np.nanargmin)):
            price = getattr(tail[col], fn)()
            try:
                set_on = tidx[int(arg(tail[col].to_numpy(dtype=float)))].date().isoformat()
            except Exception:                                   # noqa: BLE001
                set_on = None
            m = _member("year", kind, price, as_of, set_on=set_on)
            if m:
                out.append(m)
    return out


def premarket_levels(bars, session: date, now: datetime) -> list[dict]:
    """Today's pre-market high/low from the Support bars flagged `s == "pre"`
    whose `t` date is the session — the 09:25–09:29 bar stamped 09:30 is
    included (never filter on t < 09:30). [] before PRE_FROZEN_AT on the
    session: running values are not levels."""
    et = _et(now)
    if (et.date(), et.time()) < (session, PRE_FROZEN_AT):
        return []
    day = session.isoformat()
    hi = lo = None
    for b in bars or []:
        if not isinstance(b, dict) or b.get("s") != "pre":
            continue
        if str(b.get("t") or "")[:10] != day:
            continue
        h, lw = _pos(b.get("h")), _pos(b.get("l"))
        if h is not None:
            hi = h if hi is None else max(hi, h)
        if lw is not None:
            lo = lw if lo is None else min(lo, lw)
    out = []
    for kind, px in (("high", hi), ("low", lo)):
        if px is not None:
            m = _member("pre", kind, px, day)
            if m:
                out.append(m)
    return out


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------
def first_seen_key(symbol, member_id, direction, event) -> str:
    """f"{SYM}|{member_id}|{direction}|{event}", event: through | reversal."""
    return f"{str(symbol or '').upper()}|{member_id}|{direction}|{event}"


def member_state(level: dict, *, ref_close: float, row: Optional[dict], now: datetime,
                 session: date, first: Optional[dict], symbol: str) -> dict:
    """One member's read: {side, direction, state, gap, closed_beyond,
    ah_through, beyond_pct, first_through, reversal_at} — the §3.3 tables."""
    L = float(level["price"])
    side, direction = _member_side(level, ref_close)
    first = first if isinstance(first, dict) else {}
    through_at = first.get(first_seen_key(symbol, level.get("id"), direction, "through"))
    reversal_at = first.get(first_seen_key(symbol, level.get("id"), direction, "reversal"))
    out = {"side": side, "direction": direction, "state": None, "gap": False,
           "closed_beyond": None, "ah_through": False, "beyond_pct": None,
           "first_through": through_at, "reversal_at": reversal_at}
    ph = phase(now, session)
    if ph is None:
        return out
    row = row if isinstance(row, dict) else {}
    x = fresh_print(row, now, session)
    X = None
    if ph in ("rth", "close"):
        X = _pos(row.get("low")) if side == "support" else _pos(row.get("high"))
        op = _pos(row.get("open"))
        out["gap"] = _beyond(side, op, L)
    pierced_before = _beyond(side, X, L) or bool(through_at)

    def _pct(v):
        return round((v - L) / L * 100.0, 2) if v is not None else None

    if ph in ("pre", "rth"):
        if x is not None and _beyond(side, x, L):
            state = "broken"
        elif pierced_before and x is not None and _back_inside(side, x, L):
            state = "reversal"
        elif pierced_before:
            state = "pierced"
        elif _came_within(side, X, L):
            state = "tested"
        elif X is not None or x is not None:
            state = "intact"
        else:
            state = "unknown"
        out["state"] = state
        out["beyond_pct"] = _pct(x if x is not None else X)
        return out

    # ph == "close": the close decides, "broke" is never served.
    C = _pos(row.get("close"))
    if C is None:
        out["state"] = "unknown"
        return out
    if _beyond(side, C, L):
        state = "closed_beyond"
    elif pierced_before and _back_inside(side, C, L):
        state = "reversal"
    elif _came_within(side, X, L) or _in_buffer(C, L):
        state = "tested"
    else:
        state = "intact"
    out["state"] = state
    out["closed_beyond"] = state == "closed_beyond"
    out["beyond_pct"] = _pct(C)
    if (state != "closed_beyond" and x is not None and _beyond(side, x, L)
            and _is_after_hours_print(row, session)):
        out["ah_through"] = True
    return out


def _anchor(row: Optional[dict], now: datetime, session: date, ref_close) -> Optional[float]:
    """The fresh print, else the day close in RTH/AH, else ref_close."""
    x = fresh_print(row, now, session) if isinstance(row, dict) else None
    if x is not None:
        return x
    if phase(now, session) in ("rth", "close") and isinstance(row, dict):
        c = _pos(row.get("close"))
        if c is not None:
            return c
    return _f(ref_close)


def read_levels(levels, *, symbol, ref_close, row, now, session, first_seen) -> list[dict]:
    """Every member with its state and `dist_pct` from the anchor. Per MEMBER,
    never per cluster."""
    anchor = _anchor(row, now, session, ref_close)
    out = []
    for lv in levels or []:
        L = _f(lv.get("price"))
        if L is None or L <= 0:
            continue
        st = member_state(lv, ref_close=ref_close, row=row, now=now, session=session,
                          first=first_seen, symbol=symbol)
        d = round((L - anchor) / anchor * 100.0, 2) if anchor else None
        out.append({**lv, **st, "dist_pct": d if d is None or math.isfinite(d) else None})
    return out


# ---------------------------------------------------------------------------
# drawing
# ---------------------------------------------------------------------------
def merge_for_draw(levels, ref_close: float, tol_pct: float = AT_LEVEL_PCT) -> list[dict]:
    """Members on the SAME side of ref_close within `tol_pct` of the cluster's
    first member (sorted by price) draw as ONE line. Opposite sides never
    merge. Price = the highest-PERIOD_RANK member's printed price; label joins
    members by rank, descending; tone key_broken if any member is broken or
    closed_beyond. Drawing only — state stays per member."""
    ref = _f(ref_close)
    good = [lv for lv in levels or [] if _f(lv.get("price")) is not None]
    good.sort(key=lambda lv: (float(lv["price"]), -PERIOD_RANK.get(lv.get("period"), 0)))
    clusters: list[list[dict]] = []
    for lv in good:
        side = _member_side(lv, ref)[0] if ref is not None else None
        if clusters:
            head = clusters[-1][0]
            hside = _member_side(head, ref)[0] if ref is not None else None
            hp = float(head["price"])
            if side == hside and abs(float(lv["price"]) - hp) / hp * 100.0 <= tol_pct + 1e-12:
                clusters[-1].append(lv)
                continue
        clusters.append([lv])
    out = []
    for members in clusters:
        ordered = sorted(members, key=lambda m: -PERIOD_RANK.get(m.get("period"), 0))
        lead = ordered[0]
        broken = any(m.get("state") in ("broken", "closed_beyond") for m in members)
        out.append({"price": round(float(lead["price"]), 4),
                    "label": " = ".join(m["label"] for m in ordered),
                    "ids": [m["id"] for m in ordered],
                    "tone": TONE_BROKEN if broken else TONE})
    return out


def rank_for_chart(clusters, anchor: Optional[float], per_side: int) -> list[dict]:
    """The nearest `per_side` clusters above the anchor and below it; a tie in
    distance goes to the higher PERIOD_RANK."""
    clusters = list(clusters or [])
    n = max(0, int(per_side or 0))
    if not clusters or n == 0:
        return []

    def rank(c):
        return max((_rank_of_id(i) for i in c.get("ids") or []), default=-1)

    a = _f(anchor)
    if a is None:
        return sorted(clusters, key=lambda c: -rank(c))[: 2 * n]
    above = [c for c in clusters if float(c["price"]) >= a]
    below = [c for c in clusters if float(c["price"]) < a]
    above.sort(key=lambda c: (float(c["price"]) - a, -rank(c)))
    below.sort(key=lambda c: (a - float(c["price"]), -rank(c)))
    return above[:n] + below[:n]


def _has_52w_line(existing_lines) -> bool:
    for ln in existing_lines or ():
        if isinstance(ln, dict) and str(ln.get("label") or "").startswith("52W"):
            return True
    return False


def chart_lines(clusters, *, frame: str, existing_lines=()) -> list[dict]:
    """{price, label, tone} per cluster. Every label starts with 🔑; on the
    extended-hours frames an RTH level says RTH (a pre-market level already
    names its session). A tile that already draws a `52W` line (the Breaking
    tab) gets no line that is only the 52-week high."""
    dedupe = _has_52w_line(existing_lines)
    out = []
    for c in clusters or []:
        ids = list(c.get("ids") or [])
        px = _f(c.get("price"))
        if px is None:
            continue
        if dedupe and ids and all(i.startswith("year_high_") for i in ids):
            continue
        rth = frame in EXT_FRAMES and not any(i.startswith("pre_") for i in ids)
        mid = f"{c.get('label')} RTH" if rth else f"{c.get('label')}"
        out.append({"price": round(px, 4), "label": f"{MARK} {mid} {px:.2f}",
                    "tone": c.get("tone") or TONE})
    return out


# ---------------------------------------------------------------------------
# words
# ---------------------------------------------------------------------------
def chip(levels, ph: Optional[str]) -> Optional[dict]:
    """ONE chip per tile, only while the price is through a level NOW
    (`broken`), or from the close-confirm minute when it CLOSED through one
    (else an after-hours print through one). Never starts with an arrow."""
    levels = [lv for lv in levels or [] if isinstance(lv, dict)]
    if ph in ("pre", "rth"):
        cands = [lv for lv in levels if lv.get("state") == "broken"]
        mode = "broken"
    elif ph == "close":
        cands = [lv for lv in levels if lv.get("state") == "closed_beyond"]
        mode = "closed"
        if not cands:
            cands = [lv for lv in levels if lv.get("ah_through")]
            mode = "ah"
    else:
        return None
    if not cands:
        return None
    cands.sort(key=lambda lv: (-PERIOD_RANK.get(lv.get("period"), 0),
                               -abs(_f(lv.get("beyond_pct")) or 0.0)))
    w = cands[0]
    name = f"{w['label']} {float(w['price']):.2f}"
    if mode == "broken":
        verb = "broke" if _natural(w.get("kind"), w.get("direction")) else _word(w["kind"], w["direction"])
        if w.get("gap"):
            gv = "through" if verb == "broke" else verb
            text = f"{MARK} gapped {gv} {name} {_arrow(w['direction'])}"
        else:
            text = f"{MARK} {verb} {name} {_arrow(w['direction'])}"
            if w.get("first_through"):
                text += f" {w['first_through']}"
    elif mode == "closed":
        text = f"{MARK} closed {_word(w['kind'], w['direction'])} {name}"
    else:
        text = f"{MARK} after-hrs {_word(w['kind'], w['direction'])} {name}"
    if len(cands) > 1:
        text += f" +{len(cands) - 1}"
    if ph == "pre":
        from supply_demand.zone_edge import tape_tag
        text += tape_tag("premarket")
    return {"text": text, "tone": "warn"}


def _fold_state(lv: dict) -> str:
    st = lv.get("state")
    kind, direction = lv.get("kind"), lv.get("direction")
    parts = []
    if st == "broken":
        verb = "broke" if _natural(kind, direction) else _word(kind, direction)
        if lv.get("gap"):
            parts.append("gapped through" if verb == "broke" else f"gapped {verb}")
        else:
            parts.append(f"{verb} {lv['first_through']}" if lv.get("first_through") else verb)
    elif st == "pierced":
        parts.append(f"pierced {lv['first_through']}" if lv.get("first_through") else "pierced")
    elif st == "reversal":
        parts.append(f"reversal {lv['reversal_at']}" if lv.get("reversal_at") else "reversal")
    elif st == "tested":
        parts.append("tested")
    elif st == "closed_beyond":
        parts.append(f"closed {_word(kind, direction)}")
    if lv.get("ah_through"):
        parts.append(f"after-hrs {_word(kind, direction)}")
    lcc = lv.get("last_close_cross")
    if isinstance(lcc, dict) and lcc.get("date"):
        parts.append(f"closed {_word(kind, lcc.get('direction'))} "
                     f"{_day_mmdd(lcc['date'], weekday=True)}")
    return " ".join(parts)


def fold_text(levels, *, frame: str, stale_note: Optional[str],
              session: Optional[date] = None) -> Optional[str]:
    """The ▸ more line: every member (drawn or not) with its distance and
    state, then the stale note. Starts `🔑 RTH levels · `."""
    items = []
    order = sorted([lv for lv in levels or [] if isinstance(lv, dict)],
                   key=lambda lv: (PERIOD_RANK.get(lv.get("period"), 0),
                                   0 if lv.get("kind") == "high" else 1))
    for lv in order:
        px = _f(lv.get("price"))
        if px is None:
            continue
        s = f"{lv.get('label')} {px:.2f}"
        if lv.get("period") == "year" and lv.get("set_on"):
            s += f" (set {_day_mmdd(lv['set_on'], ref_year=session.year if session else None)})"
        d = _f(lv.get("dist_pct"))
        if d is not None:
            s += f" {_fmt_pct(d)}"
        st = _fold_state(lv)
        if st:
            s += f" {st}"
        items.append(s)
    if stale_note:
        items.append(str(stale_note))
    if not items:
        return None
    return f"{MARK} RTH levels · " + " · ".join(items)


def rule_text() -> str:
    """One sentence, every number from the constants above."""
    return (f"{MARK} Key levels are the regular-session highs and lows of the prior day, "
            f"week, month and {YEAR_BARS} sessions (plus the pre-market high/low from "
            f"{_hhmm(PRE_FROZEN_AT)} ET on the 5-minute charts), each frozen at the close of "
            f"its own period and rolled at {_hhmm(ROLL_AT)} ET; a level counts as broken when "
            f"a fresh print (under {STALE_PRINT_SEC} s old) is {PIERCE_PCT:g}% beyond it, and "
            f"from {_hhmm(CLOSE_CONFIRM_AT)} ET ({_hhmm(CLOSE_CONFIRM_AT_HALF)} on half days) the "
            f"close decides; levels within {AT_LEVEL_PCT:g}% on the same side draw as one line, "
            f"{GRID_PER_SIDE} above and {GRID_PER_SIDE} below the price on the cards and "
            f"{SUPPORT_PER_SIDE} each way on the Support tab — UNMEASURED, a drawing and a "
            f"fact, not a signal.")


# ---------------------------------------------------------------------------
# one tile
# ---------------------------------------------------------------------------
def tile_block(symbol, df, *, frame, row, now, per_side, bars=None, first_seen=None,
               existing_lines=()) -> tuple[dict, list]:
    """(tile['key_levels'] block, lines to append) for one tile."""
    sym = str(symbol or "").upper()
    frame = frame if frame in FRAME_PERIODS else "daily"
    periods = FRAME_PERIODS[frame]
    now_et = _et(now)
    session = levels_session(now_et)
    ph = phase(now_et, session)
    row = row if _has_row(row) else None
    stale_note: Optional[str] = None
    verified = False
    levels: list[dict] = []
    ref_close = None

    closed = closed_frame(df, session) if df is not None else None
    if closed is None or len(closed) == 0:
        stale_note = f"no cached daily bars for {sym}"
    else:
        last_d = _norm_index(closed)[-1].date()
        need = prev_market_day(session)
        if last_d < need:
            stale_note = (f"key levels need bars through {need.isoformat()}; "
                          f"cached bars end {last_d.isoformat()}")
        else:
            stale_note, verified = verify_last_row(closed, row)
        ref_close = _f(closed["close"].iloc[-1])
        levels = period_levels(closed, session, [p for p in periods if p != "pre"])
    if "pre" in periods:
        levels += premarket_levels(bars, session, now_et)

    if ref_close is not None:
        read = read_levels(levels, symbol=sym, ref_close=ref_close, row=row, now=now_et,
                           session=session, first_seen=first_seen)
    else:
        read = [{**lv, "side": None, "direction": None, "state": None, "gap": False,
                 "closed_beyond": None, "ah_through": False, "beyond_pct": None,
                 "first_through": None, "reversal_at": None, "dist_pct": None}
                for lv in levels]
    if stale_note:
        for lv in read:
            lv.update({"state": None, "gap": False, "closed_beyond": None,
                       "ah_through": False, "beyond_pct": None})
    read = [lv for lv in read if _f(lv.get("price")) is not None]

    drawn: list[dict] = []
    lines: list[dict] = []
    if not stale_note and ref_close is not None and read:
        pool = read
        if _has_52w_line(existing_lines):
            pool = [lv for lv in read if not str(lv.get("id")).startswith("year_high_")]
        clusters = merge_for_draw(pool, ref_close)
        drawn = rank_for_chart(clusters, _anchor(row, now_et, session, ref_close), per_side)
        lines = chart_lines(drawn, frame=frame, existing_lines=existing_lines)
    drawn_ids = {i for c in drawn for i in c.get("ids") or []}
    for lv in read:
        lv["drawn"] = lv.get("id") in drawn_ids
        for k in ("dist_pct", "beyond_pct"):
            if lv.get(k) is not None and not math.isfinite(float(lv[k])):
                lv[k] = None

    block = {"session": session.isoformat(), "frame": frame, "phase": ph,
             "measured": MEASURED, "verified": bool(verified), "levels": read,
             "drawn": drawn, "chip": None if stale_note else chip(read, ph),
             "fold": fold_text(read, frame=frame, stale_note=stale_note, session=session),
             "rule": rule_text(), "stale_note": stale_note}
    return block, lines


# ---------------------------------------------------------------------------
# first-seen memory (written by the zone_edge hook in key_level_alerts)
# ---------------------------------------------------------------------------
def _coll(name: str):
    try:
        from portfolio.store import _get_db
        db = _get_db()
        return db[name] if db is not None else None
    except Exception as exc:                                    # noqa: BLE001
        log.debug("key_levels: no mongo for %s: %s", name, exc)
        return None


def read_first_seen(session_iso: str, coll=None) -> dict:
    """{first_seen_key: "HH:MM"} for the session — ONE find_one; {} on any
    failure (the chip then shows no time, never a wrong one)."""
    try:
        coll = coll if coll is not None else _coll(STATE_COLL)
        if coll is None:
            return {}
        doc = coll.find_one({"_id": str(session_iso)})
        first = (doc or {}).get("first") or {}
        return {str(k): str(v) for k, v in first.items()} if isinstance(first, dict) else {}
    except Exception as exc:                                    # noqa: BLE001
        log.debug("key_levels: first_seen read failed: %s", exc)
        return {}
