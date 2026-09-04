"""ICT engine — daily key levels, the DORMANT 60-minute loop, the scan.

Ajay 2026-09-03 (late): "create a new chart maps tab for ICT Strategy,
replace supply tab with this new tab." Source: his spec + Jesse Rogers,
https://www.youtube.com/watch?v=Q7Ryv1M7CvI (02:39 lack of displacement,
03:57 consolidations toward an HTF FVG, 05:30 Power of 3, plus "confirm
with opposite displacement creating a new FVG"). The rules themselves live
in ict/structure.py; this module decides WHEN they run and on WHAT.

Multi-timeframe, the way the spec says it
-----------------------------------------
* MACRO = the daily frame (sepa.prices.load_prices + with_today_bar). It
  sets the key levels: the last N_SWINGS fractal swing lows / highs, the
  unfilled and inverted daily fair value gaps, the daily consolidations,
  and whether price has TAPPED one of those coordinates recently (traded
  into a daily gap, or swept a daily swing low / high, within TAP_LOOKBACK
  sessions and TAP_TOL_PCT).
* MICRO = the 60-minute frame (supply_demand.timeframes.frame_for, RTH
  only). It gives the triggers: Power of 3 / the manipulation at the tapped
  level, the opposite displacement, the market structure shift, the
  inverted-FVG entry.
* The micro loop is DORMANT until a macro coordinate is tapped. An untapped
  name never loads an intraday frame — that is what keeps ~1,100 daily
  reads plus a few dozen intraday reads inside the budget, and it is also
  the spec: "the micro loop stays dormant until a macro coordinate is
  tapped".

State machine (per name, per bias; both biases scanned)
    accumulation -> manipulation -> confirmed (MSS + new FVG) -> entry
    (price within ENTRY_TOL_PCT of the inverted FVG or the new FVG)
Grade 0-100 (owner scoring): manipulation 30 + opposite displacement 20 +
MSS 30 + entry 20.

Trade plan is DISPLAY ONLY, not advice: entry zone = the IFVG / new FVG,
stop = the manipulation extreme +/- STOP_BUFFER_ATR (60m ATR), target = the
next daily swing in the trade direction (external liquidity), rr = reward
over risk from the zone's proximal edge.

Persistence: Mongo `ict_board` — {_id: "latest"} (60m; "latest:15m" for
the other micro frame) plus dated copies purged after KEEP_DAYS.
`cached_or_warm` serves the latest doc and, when it is older than
ICT_TTL_SEC, kicks a background scan and answers warming:true at once —
never blocks (Cloudflare cuts at ~100 s). `python -m ict.engine` = one
scan + one INFO line (cron: every 15 min in RTH + a post-close pass).

Every threshold below that the spec does not give is an owner constant —
"owner rule — not from the video". No moving averages anywhere: purely
price action.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Iterable, Optional
from zoneinfo import ZoneInfo

from ict import structure as S

log = logging.getLogger("ict.engine")

ET = ZoneInfo("America/New_York")
COLL = "ict_board"
VIDEO_URL = S.VIDEO_URL
SOURCE = {"video": VIDEO_URL,
          "timestamps": [f"{k} — {v}" for k, v in S.TIMESTAMPS.items()],
          "note": ("Ajay's spec + Jesse Rogers' video. Every threshold not in the "
                   "video is an owner setting (listed under the board). No book, "
                   "no moving averages — price action only.")}
DISCLAIMER = ("ICT study board. Key levels, manipulations, structure shifts and "
              "the plan lines are a mechanised read of one video's rules plus the "
              "owner's own settings — decision support, not advice.")

MICRO_TF_DEFAULT = "60m"
MICRO_TFS = ("60m", "15m")
STATES = ("accumulation", "manipulation", "confirmed", "entry")
STATE_RANK = {"entry": 0, "confirmed": 1, "manipulation": 2, "accumulation": 3}

# ── owner constants — owner rule, not from the video ─────────────────────────
N_SWINGS = 5              # owner rule — not from the video: daily swing lows/highs kept as key levels
TAP_LOOKBACK = 2          # owner rule — not from the video: sessions in which a tap counts
TAP_TOL_PCT = 0.25        # owner rule — not from the video: % tolerance for "traded into / swept"
ENTRY_TOL_PCT = 0.5       # owner rule — not from the video: price within this % of the entry zone
STOP_BUFFER_ATR = 0.2     # owner rule — not from the video: stop beyond the manipulation extreme, 60m ATR
MICRO_MAX = 40            # owner rule — not from the video: most names the micro loop runs per scan
BUDGET_SEC = 120          # owner rule — not from the video: wall-clock budget per scan
ICT_TTL_SEC = 900         # owner rule — not from the video: a scan older than this re-warms
KEEP_DAYS = 5             # owner rule — not from the video: dated scan copies kept this long
MACRO_MIN_BARS = 60       # owner rule — not from the video: fewer daily bars = no structure to read
MICRO_MIN_BARS = 30       # owner rule — not from the video: fewer intraday bars = no read
MACRO_FVG_LOOKBACK = 120  # owner rule — not from the video: daily bars scanned for gaps
MACRO_FVG_KEEP = 6        # owner rule — not from the video: newest live daily gaps carried on the row
LIQ_WINDOW = 50           # owner rule — not from the video: sessions in the $-volume average
MACRO_WORKERS = 8
MICRO_WORKERS = 4
MICRO_DAYS = 21           # owner rule — not from the video: calendar days of 1-minute bars
                          # fetched per tapped name (~15 sessions); frame_for's 70-day span
                          # made one 60m frame cost ~20 s and starved the micro budget
TAP_SWING_WINDOW = 3      # owner rule — not from the video: the DAILY swings the wake-up tap
                          # listens to are local extrema over +/- this many bars (a "key
                          # structural low/high"); 1-bar fractals stay the spec's targets, but
                          # tapping every fractal wiggle woke 685 of 1,123 names a day
MIN_TARGET_R = 1.0        # owner rule — not from the video: the next daily swing counts as
                          # the target only when it pays >= this many R; a 3-candle fractal
                          # a few cents above the entry is not external liquidity worth aiming at
GRADE = {"manipulation": 30, "displacement": 20, "mss": 30, "entry": 20}

_ENGINE_PARAMS = {
    "N_SWINGS": N_SWINGS, "TAP_LOOKBACK": TAP_LOOKBACK, "TAP_TOL_PCT": TAP_TOL_PCT,
    "ENTRY_TOL_PCT": ENTRY_TOL_PCT, "STOP_BUFFER_ATR": STOP_BUFFER_ATR,
    "MICRO_MAX": MICRO_MAX, "BUDGET_SEC": BUDGET_SEC, "ICT_TTL_SEC": ICT_TTL_SEC,
    "KEEP_DAYS": KEEP_DAYS, "MACRO_MIN_BARS": MACRO_MIN_BARS,
    "MICRO_MIN_BARS": MICRO_MIN_BARS, "MACRO_FVG_LOOKBACK": MACRO_FVG_LOOKBACK,
    "MACRO_FVG_KEEP": MACRO_FVG_KEEP, "LIQ_WINDOW": LIQ_WINDOW,
    "GRADE_MANIPULATION": GRADE["manipulation"], "GRADE_DISPLACEMENT": GRADE["displacement"],
    "GRADE_MSS": GRADE["mss"], "GRADE_ENTRY": GRADE["entry"],
    "MICRO_DAYS": MICRO_DAYS,
    "TAP_SWING_WINDOW": TAP_SWING_WINDOW,
    "MIN_TARGET_R": MIN_TARGET_R,
}


def params() -> list:
    """Every constant with its value and whether the video states it —
    rendered under the board so a setting is never mistaken for a rule."""
    out = []
    for k, v in S.PARAMS.items():
        out.append({"key": k, "value": v, "from_video": k in S.FROM_VIDEO,
                    "note": "video" if k in S.FROM_VIDEO else "owner rule — not from the video"})
    for k, v in _ENGINE_PARAMS.items():
        out.append({"key": k, "value": v, "from_video": False,
                    "note": "owner rule — not from the video"})
    return out


# ── small helpers ────────────────────────────────────────────────────────────
def _num(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def _r(v, nd: int = 4) -> Optional[float]:
    f = _num(v)
    return round(f, nd) if f is not None else None


def _norm(df):
    """Lower-case OHLC columns; None when unusable."""
    if df is None or getattr(df, "empty", True):
        return None
    try:
        out = df.rename(columns={c: str(c).lower() for c in df.columns})
    except Exception:
        return None
    if not {"open", "high", "low", "close"} <= set(out.columns):
        return None
    return out


def _stamp(ts, intraday: bool) -> tuple:
    """(iso, date) in ET. Intraday indexes are UTC (naive or aware — the
    minute loader strips the zone); daily indexes are session dates and are
    read as-is (localising a midnight date as UTC would shift it a day)."""
    import pandas as pd
    try:
        t = pd.Timestamp(ts)
    except Exception:
        s = str(ts)
        return s, s[:10]
    if intraday:
        if t.tzinfo is None:
            t = t.tz_localize("UTC")
        t = t.tz_convert("America/New_York")
        return t.isoformat(), t.strftime("%Y-%m-%d")
    return t.strftime("%Y-%m-%d"), t.strftime("%Y-%m-%d")


def _dated(df, rec: Optional[dict], intraday: bool, keys=("i",)) -> Optional[dict]:
    """Copy `rec` with `at`/`date` in ET for its bar index."""
    if not rec:
        return None
    out = dict(rec)
    try:
        i = int(out.get(keys[0]))
        iso, d = _stamp(df.index[i], intraday)
        out["at"], out["date"] = iso, d
    except Exception:
        pass
    return out


def _gap_public(df, g: dict, intraday: bool) -> dict:
    out = {"kind": g.get("kind"), "lo": _r(g.get("lo")), "hi": _r(g.get("hi")),
           "status": g.get("status", "active"), "inverted_kind": g.get("inverted_kind"),
           "i": g.get("i")}
    try:
        out["at"], out["date"] = _stamp(df.index[int(g["i"])], intraday)
    except Exception:
        out["at"], out["date"] = g.get("at"), str(g.get("at"))[:10]
    if g.get("status_i") is not None:
        try:
            out["status_at"], out["status_date"] = _stamp(df.index[int(g["status_i"])], intraday)
        except Exception:
            out["status_at"], out["status_date"] = None, None
    return out


# ── loaders (the only I/O; injectable for tests) ─────────────────────────────
def _load_daily(symbol: str, snap: Optional[dict] = None, overlay: bool = True):
    """Daily OHLCV with today's live bar overlaid. `snap` is the symbol's
    bulk-snapshot row when the caller already fetched one for the whole
    universe; `overlay=False` skips the live bar entirely (a scan whose bulk
    fetch failed must not fall back to one HTTP call per name).

    A name ABSENT from the bulk snapshot stays on closed bars too:
    `with_today_bar(df, sym, snap=None)` fetches its own snapshot, and the
    bulk call silently omits errored / unmapped tickers — so without this
    guard every missing name in a 1,100-name macro pass costs one HTTP call
    from inside the thread pool."""
    from sepa import prices
    df = prices.load_prices((symbol or "").upper())
    if df is None or overlay is False or not snap:
        return df
    fn = getattr(prices, "with_today_bar", None)
    if fn is None:
        return df
    try:
        df, _info = fn(df, symbol.upper(), snap=snap)
    except Exception as exc:                                    # pragma: no cover
        log.debug("ict: today-bar overlay %s failed: %s", symbol, exc)
    return df


def micro_raw_window(today=None) -> tuple:
    """(start, end) calendar dates for the 1-minute fetch behind a micro
    frame: MICRO_DAYS back from today (+4 days weekend padding like
    timeframes.intraday_raw)."""
    from datetime import date as _date, timedelta as _td
    end = today or _date.today()
    return end - _td(days=int(MICRO_DAYS) + 4), end


def _load_micro(symbol: str, tf: str = MICRO_TF_DEFAULT):
    """The micro frame through the HOUSE resampler (closed=left), fed a
    MICRO_DAYS raw minute window instead of frame_for's 70-day span."""
    from supply_demand.timeframes import frame_for
    sym = (symbol or "").upper()
    raw = None
    try:
        from daytrading.data import load_intraday_range
        start, end = micro_raw_window()
        raw = load_intraday_range(sym, start, end, include_premarket=False,
                                  include_afterhours=False)
    except Exception as exc:                                    # pragma: no cover
        log.debug("ict: short minute window for %s failed (%s); frame_for fetches", sym, exc)
        raw = None
    df, _meta = frame_for(sym, tf, raw=raw) if raw is not None else frame_for(sym, tf)
    return df


def _bulk_snapshot(symbols: list) -> dict:
    try:
        from sepa import prices
        return prices.bulk_snapshot(list(symbols)) or {}
    except Exception as exc:
        log.warning("ict: bulk snapshot failed (%s) — scanning closed bars only", exc)
        return {}


def _default_universe() -> list:
    from supply_demand.zone_store import big_cap_universe
    return big_cap_universe()


def _name_for(symbol: str) -> Optional[str]:
    try:
        from sepa import company_names
        return company_names.name_for(symbol)
    except Exception:
        return None


# ── MACRO: daily key levels ──────────────────────────────────────────────────
def _liquidity(df) -> dict:
    """50-session average dollar volume from the daily frame — the same
    number chart_maps.tile_metrics reads, so the board's liquidity floor
    works on these rows."""
    try:
        if "volume" not in df.columns:
            return {"avg_dollar_vol_50": None}
        tail = df.tail(LIQ_WINDOW)
        dv = (tail["close"].astype(float) * tail["volume"].astype(float))
        v = _num(dv.mean())
        return {"avg_dollar_vol_50": round(v, 0) if v is not None else None}
    except Exception:
        return {"avg_dollar_vol_50": None}


def _tapped(df, recent_lows: list, recent_highs: list, gaps: list,
            lookback: int = TAP_LOOKBACK, tol_pct: float = TAP_TOL_PCT) -> Optional[dict]:
    """Did price reach a daily coordinate within the last `lookback` bars?

    swing_low   bar low  <= swing low  x (1 + tol)   -> bullish bias
    swing_high  bar high >= swing high x (1 - tol)   -> bearish bias
    fvg         the bar's range intersects a live daily gap (tolerance on
                both edges) -> the gap's own bias (an inverted gap carries
                its inverted bias)
    The swing must have FORMED before the tapping bar (its right-hand bar
    closed), or the bar that made the swing would tap itself. Newest bar
    wins; on one bar a swing beats a gap.
    """
    arrs = S._ohlc(df)
    if arrs is None:
        return None
    _o, h, lo, _c = arrs
    n = len(h)
    tol = float(tol_pct) / 100.0
    for i in range(n - 1, max(-1, n - 1 - int(lookback)), -1):
        iso, d = _stamp(df.index[i], intraday=False)
        # FRESH touch only (fix 2026-09-04 after the first seed woke 1,122 of
        # 1,123 names): the bar BEFORE the tap must still be on the far side
        # of the level — a name that has sat under an old swing low for a
        # week is not "reaching" it, it already broke it. Same for a gap: the
        # prior bar must not already intersect it.
        prev_lo = lo[i - 1] if i >= 1 else None
        prev_hi = h[i - 1] if i >= 1 else None
        for j, p in reversed(recent_lows):
            if (j + 1 < i and lo[i] <= p * (1 + tol)
                    and (prev_lo is None or prev_lo > p * (1 + tol))):
                return {"kind": "swing_low", "price": _r(p), "at": d, "date": d,
                        "bar_i": i, "level_i": j, "bias": "bullish"}
        for j, p in reversed(recent_highs):
            if (j + 1 < i and h[i] >= p * (1 - tol)
                    and (prev_hi is None or prev_hi < p * (1 - tol))):
                return {"kind": "swing_high", "price": _r(p), "at": d, "date": d,
                        "bar_i": i, "level_i": j, "bias": "bearish"}
        for g in reversed(gaps):
            if int(g.get("i", n)) >= i:
                continue
            g_lo, g_hi = float(g["lo"]), float(g["hi"])
            prev_in = (prev_lo is not None and prev_hi is not None
                       and prev_lo <= g_hi * (1 + tol) and prev_hi >= g_lo * (1 - tol))
            if prev_in:
                continue                     # already inside the gap yesterday
            # FIRST touch only (2026-09-04: 44 of 63 gap taps in a 150-name
            # sample were re-touches of long-inverted daily gaps): a
            # mitigated gap wakes the loop on its mitigation bar only; an
            # inverted gap on the first bar that retests it after the
            # inversion; a filled gap never.
            st, sti = g.get("status"), g.get("status_i")
            if st == "filled":
                continue
            if st == "mitigated" and sti is not None and int(sti) != i:
                continue
            if st == "inverted":
                if sti is None or i <= int(sti):
                    continue
                if any(lo[k] <= g_hi * (1 + tol) and h[k] >= g_lo * (1 - tol)
                       for k in range(int(sti) + 1, i)):
                    continue                 # already retested since the inversion
            if lo[i] <= g_hi * (1 + tol) and h[i] >= g_lo * (1 - tol):
                bias = g.get("inverted_kind") or g.get("kind")
                near = g_hi if bias == "bullish" else g_lo
                return {"kind": "fvg", "price": _r(near), "lo": _r(g_lo), "hi": _r(g_hi),
                        "at": d, "date": d, "bar_i": i, "level_i": g.get("i"),
                        "bias": bias, "gap_status": g.get("status")}
    return None


def macro(symbol: str, df=None, *, loader: Optional[Callable] = None) -> Optional[dict]:
    """Daily key levels for one name, or None when there is no frame.

    {symbol, last, date, atr, key_low, key_high, swings, fvgs,
     consolidations, consol_ranges, stacked, stack, tapped, liquidity}
    """
    sym = (symbol or "").upper().strip()
    if df is None:
        try:
            df = (loader or _load_daily)(sym)
        except Exception as exc:
            log.debug("ict: daily frame %s failed: %s", sym, exc)
            return None
    df = _norm(df)
    if df is None or len(df) < MACRO_MIN_BARS:
        return None
    arrs = S._ohlc(df)
    if arrs is None:
        return None
    _o, _h, _lo, c = arrs
    last = _num(c[-1])
    if last is None or last <= 0:
        return None
    a = S.atr14(df)
    lows, highs = S.swing_points_fractal(df)
    recent_lows, recent_highs = lows[-N_SWINGS:], highs[-N_SWINGS:]

    # Nearest recent swing below / above the last print; when price sits
    # under every recent low (or over every high) the extreme one is the key.
    below = [p for _j, p in recent_lows if p < last]
    above = [p for _j, p in recent_highs if p > last]
    key_low = max(below) if below else (min(p for _j, p in recent_lows) if recent_lows else None)
    key_high = min(above) if above else (max(p for _j, p in recent_highs) if recent_highs else None)

    gaps = S.fvg_state(S.fair_value_gaps_raw(df, lookback=MACRO_FVG_LOOKBACK), df)
    live = [g for g in gaps if g.get("status") in ("active", "mitigated", "inverted")]
    consols = S.consolidations(df, a)
    stack = S.stacked_consolidations(df, live, consols=consols, atr=a, last=last)
    # The wake-up listens to the wider-window swings (owner rule
    # TAP_SWING_WINDOW); key levels, targets and the swings list stay the
    # spec's 3-candle fractals.
    tap_lows, tap_highs = S.swing_points_strict(df, TAP_SWING_WINDOW)
    tapped = _tapped(df, tap_lows[-N_SWINGS:], tap_highs[-N_SWINGS:], live)

    swings = []
    for kind, pts in (("swing_low", recent_lows), ("swing_high", recent_highs)):
        for j, p in pts:
            iso, d = _stamp(df.index[j], intraday=False)
            swings.append({"kind": kind, "price": _r(p), "at": d, "date": d, "i": int(j)})
    swings.sort(key=lambda s: s["i"])
    _iso, as_of_date = _stamp(df.index[-1], intraday=False)
    return {
        "symbol": sym,
        "last": _r(last),
        "date": as_of_date,
        "atr": _r(a),
        "key_low": _r(key_low),
        "key_high": _r(key_high),
        "swings": swings,
        "fvgs": [_gap_public(df, g, intraday=False) for g in live[-MACRO_FVG_KEEP:]],
        "consolidations": len(consols),
        "consol_ranges": [{"lo": _r(cs["lo"]), "hi": _r(cs["hi"]), "bars": cs["bars"],
                           "start": _stamp(df.index[cs["start"]], False)[1],
                           "end": _stamp(df.index[cs["end"]], False)[1]}
                          for cs in consols[-3:]],
        "stacked": bool(stack.get("stacked")),
        "stack": {"count": stack.get("count", 0), "toward": stack.get("toward"),
                  "gap": ({"lo": _r(stack["gap"]["lo"]), "hi": _r(stack["gap"]["hi"]),
                           "kind": stack["gap"].get("kind")} if stack.get("gap") else None)},
        "tapped": tapped,
        "liquidity": _liquidity(df),
    }


# ── MICRO: the dormant loop ──────────────────────────────────────────────────
def _near_zone(px: float, zone: dict, tol_pct: float = ENTRY_TOL_PCT) -> bool:
    lo_, hi_ = _num(zone.get("lo")), _num(zone.get("hi"))
    if lo_ is None or hi_ is None:
        return False
    t = float(tol_pct) / 100.0
    return lo_ * (1 - t) <= px <= hi_ * (1 + t)


def _direction_read(df, d: str, a: float, gaps: list, swings: tuple, consols: list,
                    tapped: dict) -> Optional[dict]:
    """One bias through the state machine. None when the frame shows neither
    an accumulation range nor a manipulation for this bias."""
    arrs = S._ohlc(df)
    if arrs is None:
        return None
    _o, _h, _lo, c = arrs
    last = float(c[-1])

    # 1. Power of 3 first (05:30): the accumulation range, then the
    #    manipulation beyond it. Failing that, the manipulation at the
    #    tapped DAILY level, with the newest range before it as accumulation.
    p3 = S.power_of_three(df, atr=a, consols=consols, direction=d)
    accum = manip = None
    source = None
    if p3:
        accum, manip, source = p3["accumulation"], p3["manipulation"], "power_of_three"
    else:
        level = None
        if tapped and tapped.get("bias") == d:
            level = _num(tapped.get("price"))
        if level is not None:
            manip = S.manipulation(df, key_low=level if d == "bullish" else None,
                                   key_high=level if d == "bearish" else None, atr=a)
            source = "daily_level" if manip else None
        before = [cs for cs in consols if manip is None or cs["end"] < manip["i"]]
        accum = before[-1] if before else None
    if manip is None and accum is None:
        return None

    state, grade = "accumulation", 0
    disp = mss_ = new_fvg = ifvg = None
    if manip:
        state = "manipulation"
        grade += GRADE["manipulation"]
        disp = S.opposite_displacement(df, manip, atr=a, gaps=gaps)
        if disp:
            grade += GRADE["displacement"]
        mss_ = S.mss(df, swings=swings, gaps=gaps, direction=d, after=manip["i"])
        if mss_:
            state = "confirmed"
            grade += GRADE["mss"]
            new_fvg = mss_["fvg"]
        elif disp:
            new_fvg = disp["fvg"]
        # Inverted FVG: an OPPOSING gap that a candle CLOSED through after
        # the manipulation — the trigger the spec names.
        opp = "bearish" if d == "bullish" else "bullish"
        inv = [g for g in gaps if g.get("kind") == opp and g.get("status") == "inverted"
               and g.get("status_i") is not None and int(g["status_i"]) >= int(manip["i"])]
        # Newest inversion wins; on the same closing bar the most recently
        # formed gap (the one nearest the reversal) is the zone.
        ifvg = max(inv, key=lambda g: (int(g["status_i"]), int(g["i"]))) if inv else None
        if state == "confirmed":
            zone = ifvg or new_fvg
            if zone and _near_zone(last, zone):
                state = "entry"
                grade += GRADE["entry"]
    return {"bias": d, "state": state, "grade": int(grade), "accumulation": accum,
            "manipulation": manip, "displacement": disp, "mss": mss_, "fvg": new_fvg,
            "ifvg": ifvg, "source": source, "last": last}


def _plan(read: dict, macro_ctx: Optional[dict], a: float) -> Optional[dict]:
    """Display-only plan. Entry zone = the IFVG (preferred) or the new FVG;
    the entry price is the zone's PROXIMAL edge (a bullish trade is filled
    coming down into the gap, so its hi; bearish its lo). Stop beyond the
    manipulation extreme by STOP_BUFFER_ATR of the 60m ATR. Target = the
    next daily swing in the trade direction (external liquidity)."""
    manip = read.get("manipulation")
    zone = read.get("ifvg") or read.get("fvg")
    if not manip or not zone:
        return None
    d = read["bias"]
    z_lo, z_hi = _num(zone.get("lo")), _num(zone.get("hi"))
    ext = _num(manip.get("extreme"))
    if z_lo is None or z_hi is None or ext is None:
        return None
    buf = float(STOP_BUFFER_ATR) * float(a or 0.0)
    swings = (macro_ctx or {}).get("swings") or []
    if d == "bullish":
        entry, stop = z_hi, ext - buf
        risk = entry - stop
        cands = [s["price"] for s in swings if s.get("kind") == "swing_high"
                 and _num(s.get("price")) is not None
                 and s["price"] - entry >= float(MIN_TARGET_R) * max(risk, 0.0)
                 and s["price"] > entry]
        target = min(cands) if cands else None
        reward = (target - entry) if target is not None else None
    else:
        entry, stop = z_lo, ext + buf
        risk = stop - entry
        cands = [s["price"] for s in swings if s.get("kind") == "swing_low"
                 and _num(s.get("price")) is not None
                 and entry - s["price"] >= float(MIN_TARGET_R) * max(risk, 0.0)
                 and s["price"] < entry]
        target = max(cands) if cands else None
        reward = (entry - target) if target is not None else None
    rr = round(reward / risk, 2) if (reward is not None and risk and risk > 0) else None
    return {"entry_lo": _r(z_lo), "entry_hi": _r(z_hi), "entry": _r(entry),
            "stop": _r(stop), "target": _r(target), "rr": rr,
            "zone": "ifvg" if read.get("ifvg") else "fvg",
            "risk_pct": _r(risk / entry * 100.0, 2) if entry else None}


def _why(read: dict, tf: str, tapped: Optional[dict], plan: Optional[dict]) -> str:
    d = read["bias"]
    parts = [d]
    if tapped:
        parts.append(f"tapped daily {tapped.get('kind', '').replace('_', ' ')} "
                     f"{_num(tapped.get('price')) or 0:.2f}")
    m = read.get("manipulation")
    if m:
        side = "under" if m.get("side") == "low" else "over"
        parts.append(f"{tf} wick {side} {m['level']:.2f} closed back "
                     f"{'above' if side == 'under' else 'below'} it (no displacement)")
    elif read.get("accumulation"):
        cs = read["accumulation"]
        parts.append(f"{tf} accumulation {cs['lo']:.2f}–{cs['hi']:.2f}, no sweep yet")
    if read.get("displacement"):
        parts.append(f"{read['displacement']['atr_mult']:.1f} ATR push left a new FVG")
    if read.get("mss"):
        parts.append(f"MSS {'above' if d == 'bullish' else 'below'} {read['mss']['level']:.2f}")
    if read.get("ifvg"):
        parts.append(f"IFVG {read['ifvg']['lo']:.2f}–{read['ifvg']['hi']:.2f}")
    if read["state"] == "entry":
        parts.append("price at the entry zone")
    if plan and plan.get("rr") is not None:
        parts.append(f"{plan['rr']:.1f}R to the next daily swing")
    return " · ".join(parts)


def micro(symbol: str, tf: str = MICRO_TF_DEFAULT, df=None,
          macro_ctx: Optional[dict] = None, *,
          loader: Optional[Callable] = None) -> Optional[dict]:
    """The micro read for ONE tapped name. Callers must gate on
    macro['tapped'] — this function does not (see `scan`)."""
    sym = (symbol or "").upper().strip()
    tf = tf if tf in MICRO_TFS else MICRO_TF_DEFAULT
    if df is None:
        try:
            df = (loader or _load_micro)(sym, tf)
        except Exception as exc:
            log.debug("ict: micro frame %s %s failed: %s", sym, tf, exc)
            return None
    df = _norm(df)
    if df is None or len(df) < MICRO_MIN_BARS:
        return None
    a = S.atr14(df)
    if not a:
        return None
    gaps = S.fvg_state(S.fair_value_gaps_raw(df), df)
    swings = S.swing_points_fractal(df)
    consols = S.consolidations(df, a)
    tapped = (macro_ctx or {}).get("tapped") or {}

    reads = []
    for d in ("bullish", "bearish"):
        try:
            r = _direction_read(df, d, a, gaps, swings, consols, tapped)
        except Exception as exc:                                # pragma: no cover
            log.debug("ict: %s %s read failed: %s", sym, d, exc)
            r = None
        if r:
            reads.append(r)
    if not reads:
        return None
    tap_bias = tapped.get("bias")
    reads.sort(key=lambda r: (STATE_RANK[r["state"]], -r["grade"],
                              0 if r["bias"] == tap_bias else 1))
    best = reads[0]
    plan = _plan(best, macro_ctx, a)

    def _acc(cs):
        if not cs:
            return None
        return {"lo": _r(cs["lo"]), "hi": _r(cs["hi"]), "bars": cs["bars"],
                "at": _stamp(df.index[cs["start"]], True)[0],
                "date": _stamp(df.index[cs["start"]], True)[1],
                "end_date": _stamp(df.index[cs["end"]], True)[1]}

    m = _dated(df, best.get("manipulation"), True)
    if m:
        m = {"at": m["at"], "date": m["date"], "side": m["side"], "level": _r(m["level"]),
             ("low" if m["side"] == "low" else "high"): _r(m["extreme"]),
             "extreme": _r(m["extreme"]), "close": _r(m["close"]), "displaced": False}
    disp = _dated(df, best.get("displacement"), True)
    if disp:
        disp = {"at": disp["at"], "date": disp["date"], "atr_mult": disp["atr_mult"]}
    ms = _dated(df, best.get("mss"), True)
    if ms:
        ms = {"at": ms["at"], "date": ms["date"], "level": _r(ms["level"]),
              "direction": ms["direction"]}
    fvg = _gap_public(df, best["fvg"], True) if best.get("fvg") else None
    ifvg = None
    if best.get("ifvg"):
        g = _gap_public(df, best["ifvg"], True)
        ifvg = {"lo": g["lo"], "hi": g["hi"], "at": g.get("status_at") or g["at"],
                "date": g.get("status_date") or g["date"], "from": g["kind"]}
    _iso, as_of_date = _stamp(df.index[-1], True)
    return {
        "tf": tf, "bars": int(len(df)), "as_of": _iso, "atr": _r(a),
        "bias": best["bias"], "state": best["state"], "grade": best["grade"],
        "source": best.get("source"),
        "accumulation": _acc(best.get("accumulation")),
        "manipulation": m, "displacement": disp, "mss": ms,
        "fvg": fvg, "ifvg": ifvg, "consolidations": len(consols),
        "plan": plan, "last": _r(best["last"]),
        "why": _why(best, tf, tapped, plan),
    }


# ── the scan ─────────────────────────────────────────────────────────────────
def _row(m: dict, mi: dict) -> dict:
    sym = m["symbol"]
    return {
        "symbol": sym,
        "name": m.get("name") or _name_for(sym),
        "bias": mi["bias"],
        "state": mi["state"],
        "grade": mi["grade"],
        "macro": {"key_low": m.get("key_low"), "key_high": m.get("key_high"),
                  "tapped": m.get("tapped"), "swings": m.get("swings"),
                  "fvgs": m.get("fvgs"), "consolidations": m.get("consolidations"),
                  "stacked": m.get("stacked"), "stack": m.get("stack"),
                  "atr": m.get("atr"), "date": m.get("date")},
        "micro": {k: mi.get(k) for k in ("tf", "bars", "as_of", "atr", "source",
                                          "accumulation", "manipulation", "displacement",
                                          "mss", "fvg", "ifvg", "consolidations")},
        "plan": mi.get("plan"),
        "last": mi.get("last") if mi.get("last") is not None else m.get("last"),
        "last_price": mi.get("last") if mi.get("last") is not None else m.get("last"),
        "liquidity": m.get("liquidity") or {},
        "why": mi.get("why"),
    }


def sort_rows(rows: list) -> list:
    """entry > confirmed > manipulation > accumulation, then grade desc,
    then symbol so the order is stable."""
    return sorted(rows, key=lambda r: (STATE_RANK.get(r.get("state"), 9),
                                       -(r.get("grade") or 0), r.get("symbol") or ""))


def scan(universe: Optional[Iterable[str]] = None, *,
         micro_max: int = MICRO_MAX, budget_sec: float = BUDGET_SEC,
         now: Optional[datetime] = None, micro_tf: str = MICRO_TF_DEFAULT,
         daily_loader: Optional[Callable] = None,
         micro_loader: Optional[Callable] = None,
         persist: bool = True, coll=None) -> dict:
    """One pass: macro over the universe, micro over the TAPPED names only.

    {as_of, date, macro_n, tapped_n, micro_n, rows, seconds, truncated,
     micro_tf, universe}. `truncated` is True when the budget cut either
     pass short or more names were tapped than `micro_max` allows — the
     board says so rather than pretending it saw everything.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    t0 = time.time()
    now = (now or datetime.now(ET)).astimezone(ET)
    tf = micro_tf if micro_tf in MICRO_TFS else MICRO_TF_DEFAULT
    syms = [str(s).upper() for s in (universe if universe is not None else _default_universe()) if s]
    syms = list(dict.fromkeys(syms))
    truncated = False

    if daily_loader is None:
        snaps = _bulk_snapshot(syms)
        dl = (lambda s: _load_daily(s, snap=snaps.get(s), overlay=bool(snaps)))
    else:
        dl = daily_loader
    ml = micro_loader or _load_micro

    def _safe_macro(s: str):
        try:
            return macro(s, loader=dl)
        except Exception as exc:
            log.debug("ict: macro %s failed: %s", s, exc)
            return None

    macros: dict = {}
    tapped: list = []
    pool = ThreadPoolExecutor(max_workers=MACRO_WORKERS)
    try:
        futs = {pool.submit(_safe_macro, s): s for s in syms}
        for fut in as_completed(futs):
            if time.time() - t0 > budget_sec:
                truncated = True
                break
            m = fut.result()
            if not m:
                continue
            macros[m["symbol"]] = m
            if m.get("tapped"):
                tapped.append(m)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    # Newest tap first, then the most liquid — so a cap falls on the least
    # interesting names rather than on whatever finished last. Newest by the
    # tap's session DATE: `bar_i` is an iloc into each name's own frame and
    # frames differ in length (a 2y history vs a recent listing), so it says
    # nothing across names — a two-day-old tap on a long frame would outrank
    # today's tap on a short one.
    tapped.sort(key=lambda m: m["symbol"])
    tapped.sort(key=lambda m: (str(m["tapped"].get("date") or ""),
                               float((m.get("liquidity") or {}).get("avg_dollar_vol_50") or 0.0)),
                reverse=True)
    targets = tapped[:max(0, int(micro_max))]
    if len(tapped) > len(targets):
        truncated = True

    def _safe_micro(m: dict):
        try:
            mi = micro(m["symbol"], tf, macro_ctx=m, loader=ml)
        except Exception as exc:
            log.debug("ict: micro %s failed: %s", m["symbol"], exc)
            return m, None
        return m, mi

    rows: list = []
    micro_n = 0
    pool = ThreadPoolExecutor(max_workers=MICRO_WORKERS)
    try:
        futs = {pool.submit(_safe_micro, m): m["symbol"] for m in targets}
        for fut in as_completed(futs):
            if time.time() - t0 > budget_sec:
                truncated = True
                break
            m, mi = fut.result()
            micro_n += 1
            if mi:
                rows.append(_row(m, mi))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    doc = {
        "as_of": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "macro_n": len(macros),
        "tapped_n": len(tapped),
        "micro_n": micro_n,
        "rows": sort_rows(rows),
        "seconds": round(time.time() - t0, 1),
        "truncated": bool(truncated),
        "micro_tf": tf,
        "universe": len(syms),
        "params": params(),
        "source": SOURCE,
    }
    if persist:
        _persist(doc, coll=coll, now=now)
    log.info("ict: scan macro=%d tapped=%d micro=%d rows=%d truncated=%s %.1fs",
             doc["macro_n"], doc["tapped_n"], doc["micro_n"], len(doc["rows"]),
             doc["truncated"], doc["seconds"])
    return doc


# ── persistence ──────────────────────────────────────────────────────────────
def _coll(coll=None):
    if coll is not None:
        return coll
    try:
        from portfolio.store import _get_db
        db = _get_db()
        return db[COLL] if db is not None else None
    except Exception as exc:
        log.warning("ict: no mongo: %s", exc)
        return None


def latest_id(tf: str = MICRO_TF_DEFAULT) -> str:
    return "latest" if tf == MICRO_TF_DEFAULT else f"latest:{tf}"


def _persist(doc: dict, coll=None, now: Optional[datetime] = None) -> bool:
    coll = _coll(coll)
    if coll is None:
        return False
    now = (now or datetime.now(ET)).astimezone(ET)
    tf = doc.get("micro_tf") or MICRO_TF_DEFAULT
    body = {k: v for k, v in doc.items() if k != "_id"}
    try:
        coll.replace_one({"_id": latest_id(tf)}, dict(body, _id=latest_id(tf)), upsert=True)
        dated = f"{doc['date']}:{now.strftime('%H%M')}:{tf}"
        coll.replace_one({"_id": dated}, dict(body, _id=dated), upsert=True)
    except Exception as exc:
        log.warning("ict: persist failed: %s", exc)
        return False
    purge(coll=coll, today=now.date())
    return True


def purge(keep_days: int = KEEP_DAYS, coll=None, today: Optional[date] = None) -> int:
    """Drop dated copies older than `keep_days`; the latest docs stay."""
    coll = _coll(coll)
    if coll is None:
        return 0
    cutoff = ((today or datetime.now(ET).date()) - timedelta(days=int(keep_days))).isoformat()
    try:
        res = coll.delete_many({"date": {"$lt": cutoff},
                                "_id": {"$nin": [latest_id(t) for t in MICRO_TFS]}})
        return int(getattr(res, "deleted_count", 0) or 0)
    except Exception as exc:
        log.warning("ict: purge failed: %s", exc)
        return 0


# ── serve: the cache, or warm in the background ─────────────────────────────
_warming: set = set()
_warm_lock = threading.Lock()
_last_warm_thread: Optional[threading.Thread] = None


def _age_sec(as_of, now: Optional[datetime] = None) -> Optional[float]:
    try:
        t = datetime.fromisoformat(str(as_of))
    except (TypeError, ValueError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=ET)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=ET)
    return (now - t).total_seconds()


def _start_warm(tf: str) -> bool:
    """Kick one background scan for `tf` unless one is already running."""
    global _last_warm_thread
    with _warm_lock:
        if tf in _warming:
            return False
        _warming.add(tf)

    def _work():
        try:
            scan(micro_tf=tf)
        except Exception as exc:
            log.warning("ict: background warm failed for %s: %s", tf, exc)
        finally:
            with _warm_lock:
                _warming.discard(tf)

    th = threading.Thread(target=_work, name=f"ict-warm-{tf}", daemon=True)
    _last_warm_thread = th
    th.start()
    return True


def _empty(tf: str, now: datetime) -> dict:
    return {"as_of": None, "date": now.strftime("%Y-%m-%d"), "macro_n": 0,
            "tapped_n": 0, "micro_n": 0, "rows": [], "seconds": 0,
            "truncated": False, "micro_tf": tf, "universe": 0,
            "params": params(), "source": SOURCE}


def cached_or_warm(limit: Optional[int] = None, *, micro_tf: str = MICRO_TF_DEFAULT,
                   coll=None, now: Optional[datetime] = None,
                   ttl_sec: float = ICT_TTL_SEC) -> dict:
    """Serve the latest scan; re-warm in the background when it is stale.

    Never blocks: a fresh doc answers cached:true; a stale or missing one
    answers warming:true WITH whatever rows it still has, and a daemon
    thread runs the scan so the next poll reads the new doc. Mirrors
    demand_reentry.cached_or_warm, except the cache is Mongo rather than
    process memory — so the 15-minute cron in the cron container fills the
    same doc the api container reads.
    """
    tf = micro_tf if micro_tf in MICRO_TFS else MICRO_TF_DEFAULT
    now = (now or datetime.now(ET)).astimezone(ET)
    c = _coll(coll)
    doc = None
    if c is not None:
        try:
            doc = c.find_one({"_id": latest_id(tf)})
        except Exception as exc:
            log.warning("ict: cache read failed: %s", exc)
            doc = None
    base = {k: v for k, v in (doc or {}).items() if k != "_id"} or _empty(tf, now)
    if "params" not in base:
        base["params"] = params()
    if "source" not in base:
        base["source"] = SOURCE
    rows = list(base.get("rows") or [])
    if limit:
        rows = rows[:int(limit)]
    age = _age_sec(base.get("as_of"), now) if doc else None
    fresh = age is not None and 0 <= age < float(ttl_sec)
    if fresh:
        return dict(base, rows=rows, cached=True, warming=False, stale_sec=round(age, 0),
                    disclaimer=DISCLAIMER)
    if c is None:
        # Nowhere to put a result: a warm would burn the budget and vanish.
        return dict(base, rows=rows, cached=False, warming=False, stale_sec=None,
                    note="ICT board store unavailable", disclaimer=DISCLAIMER)
    _start_warm(tf)
    return dict(base, rows=rows, cached=bool(doc), warming=True,
                stale_sec=round(age, 0) if age is not None else None,
                disclaimer=DISCLAIMER)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    res = scan()
    log.info("ICT: date=%s macro=%s tapped=%s micro=%s rows=%s truncated=%s seconds=%s",
             res["date"], res["macro_n"], res["tapped_n"], res["micro_n"],
             len(res["rows"]), res["truncated"], res["seconds"])
