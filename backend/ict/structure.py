"""ICT structure primitives — PURE. Pandas OHLC frames in, plain dicts out,
no I/O, no network, never raises on a malformed or short frame ([] / None).

Source: Ajay's spec (2026-09-03) + Jesse Rogers,
https://www.youtube.com/watch?v=Q7Ryv1M7CvI — timestamps cited per rule:
    02:39  lack of displacement (the manipulation)
    03:57  multiple consolidations toward an HTF fair value gap
    05:30  Power of 3 — accumulation first, then the manipulation below it
    plus   "confirm with opposite displacement creating a new FVG"

Nothing here is a moving average or a volume-weighted price: every rule is a
statement about highs, lows, opens and closes. Every threshold the spec does
not give is an OWNER CONSTANT (marked "owner rule — not from the video").

Conventions
-----------
* `i` is an integer iloc into the frame, `at` is `str(df.index[i])`.
  The engine turns `at` into an ET timestamp + date; this module does not
  know what timeframe it is looking at and does not need to.
* "swing" = the spec's 3-candle fractal: High[i-1] < High[i] > High[i+1]
  (lows mirrored). Ties are NOT swings. `FRACTAL_WINDOW` = 1 bar each side
  is the spec; the community window variant is exposed separately.
* A fair value gap is the RAW three-candle gap: bullish when
  Low[i+2] > High[i], bearish when High[i+2] < Low[i]. Touching is not a
  gap. No displacement or width filter — the spec's FVG has none.
"""
from __future__ import annotations

from typing import Optional

VIDEO_URL = "https://www.youtube.com/watch?v=Q7Ryv1M7CvI"
TIMESTAMPS = {
    "02:39": "lack of displacement — the manipulation wicks past the level but does not close through it",
    "03:57": "two or more consolidations as price moves toward a higher-timeframe fair value gap",
    "05:30": "Power of 3 — the accumulation range first; the manipulation is the move below its lows",
    "confirm": "opposite displacement that creates a new fair value gap",
}

# ── spec-given ───────────────────────────────────────────────────────────────
FRACTAL_WINDOW = 1        # spec: 3-candle fractal, one bar each side
STACK_MIN = 2             # video 03:57: "two or more" consolidations

# ── owner constants — owner rule, not from the video ─────────────────────────
ATR_PERIOD = 14           # owner rule — not from the video: the range unit every ATR rule uses
CONSOL_MIN_BARS = 5       # owner rule — not from the video: a consolidation needs this many bars
CONSOL_MAX_ATR = 1.5      # owner rule — not from the video: ...whose high-low span <= this x ATR
DISPLACE_MAX_ATR = 0.0    # owner rule — not from the video: manipulation close tolerance
#                           (0.0 = the bar must close back at or above the swept level)
DISPLACE_MIN_ATR = 1.0    # owner rule — not from the video: opposite-displacement body >= this x ATR
CONFIRM_MAX_BARS = 3      # owner rule — not from the video: displacement must arrive within this many bars
MSS_FVG_WITHIN_BARS = 1   # owner rule — not from the video: the new FVG's third bar within this many bars of the MSS close
STACK_LOOKBACK_BARS = 60  # owner rule — not from the video: window the stacked consolidations are counted in

PARAMS = {
    "FRACTAL_WINDOW": FRACTAL_WINDOW,
    "STACK_MIN": STACK_MIN,
    "ATR_PERIOD": ATR_PERIOD,
    "CONSOL_MIN_BARS": CONSOL_MIN_BARS,
    "CONSOL_MAX_ATR": CONSOL_MAX_ATR,
    "DISPLACE_MAX_ATR": DISPLACE_MAX_ATR,
    "DISPLACE_MIN_ATR": DISPLACE_MIN_ATR,
    "CONFIRM_MAX_BARS": CONFIRM_MAX_BARS,
    "MSS_FVG_WITHIN_BARS": MSS_FVG_WITHIN_BARS,
    "STACK_LOOKBACK_BARS": STACK_LOOKBACK_BARS,
}
# Which of the above the video actually states. Everything else is the owner's.
FROM_VIDEO = ("FRACTAL_WINDOW", "STACK_MIN")


# ── frame helpers ────────────────────────────────────────────────────────────
def _ohlc(df):
    """(open, high, low, close) as float arrays, or None when unusable."""
    if df is None:
        return None
    try:
        if len(df) == 0:
            return None
        cols = {str(c).lower(): c for c in df.columns}
        if not {"open", "high", "low", "close"} <= set(cols):
            return None
        o = df[cols["open"]].to_numpy(dtype=float)
        h = df[cols["high"]].to_numpy(dtype=float)
        lo = df[cols["low"]].to_numpy(dtype=float)
        c = df[cols["close"]].to_numpy(dtype=float)
    except Exception:
        return None
    return o, h, lo, c


def _ts(df, i: int) -> Optional[str]:
    try:
        return str(df.index[i])
    except Exception:
        return None


def atr14(df, period: int = ATR_PERIOD) -> Optional[float]:
    """Average true range on whatever frame is passed. None when the frame is
    too short — never a guessed range. Reuses the app's one ATR."""
    try:
        from supply_demand.patterns import atr
        return atr(df, period)
    except Exception:
        return None


# ── swing points ─────────────────────────────────────────────────────────────
def swing_points_fractal(df, window: int = FRACTAL_WINDOW) -> tuple:
    """(lows, highs) as [(iloc, price)] — the spec's 3-candle fractal.

    High[i-1] < High[i] > High[i+1] (strict on BOTH sides, so an equal high
    is not a swing); lows mirrored. `window` > 1 widens each side but stays
    strict. These are the take-profit targets (external liquidity): stops
    rest under swing lows and over swing highs.
    """
    lows: list = []
    highs: list = []
    arrs = _ohlc(df)
    if arrs is None:
        return lows, highs
    _o, h, lo, _c = arrs
    w = max(1, int(window or 1))
    n = len(h)
    if n < 2 * w + 1:
        return lows, highs
    for i in range(w, n - w):
        if h[i] > h[i - w:i].max() and h[i] > h[i + 1:i + w + 1].max():
            highs.append((i, float(h[i])))
        if lo[i] < lo[i - w:i].min() and lo[i] < lo[i + 1:i + w + 1].min():
            lows.append((i, float(lo[i])))
    return lows, highs


def swing_points_window(df, window: int = 3) -> tuple:
    """The community (smc.py) variant: strict-or-equal local extrema over a
    wider window. Exposed for comparison; the engine uses the fractal."""
    try:
        from supply_demand.smc import swing_points
        return swing_points(df, window)
    except Exception:
        return [], []


def swing_points_strict(df, window: int = 3) -> tuple:
    """(lows, highs) as [(iloc, price)] — STRICT local extrema over +/- `window`
    bars: the bar's low is below EVERY other low in the window (highs
    mirrored). window=1 is exactly the spec's 3-candle fractal; wider windows
    are the engine's "key structural low/high" for the wake-up tap (owner
    rule TAP_SWING_WINDOW). Unlike smc.swing_points (strict-or-equal), a flat
    plateau of equal lows is NOT a run of swings."""
    lows: list = []
    highs: list = []
    w = int(window)
    if df is None or w < 1 or len(df) < 2 * w + 1:
        return lows, highs
    arrs = _ohlc(df)
    if arrs is None:
        return lows, highs
    _o, h, lo, _c = arrs
    n = len(lo)
    for i in range(w, n - w):
        left_lo, right_lo = lo[i - w:i], lo[i + 1:i + w + 1]
        if lo[i] < min(left_lo) and lo[i] < min(right_lo):
            lows.append((i, float(lo[i])))
        left_hi, right_hi = h[i - w:i], h[i + 1:i + w + 1]
        if h[i] > max(left_hi) and h[i] > max(right_hi):
            highs.append((i, float(h[i])))
    return lows, highs


def swing_targets(df, lows: list, highs: list) -> list:
    """Swings as dated target records, oldest first:
    [{kind: swing_low|swing_high, price, i, at}]."""
    out = [{"kind": "swing_low", "price": float(p), "i": int(i), "at": _ts(df, i)}
           for i, p in (lows or [])]
    out += [{"kind": "swing_high", "price": float(p), "i": int(i), "at": _ts(df, i)}
            for i, p in (highs or [])]
    out.sort(key=lambda s: s["i"])
    return out


# ── fair value gaps ──────────────────────────────────────────────────────────
def fair_value_gaps_raw(df, lookback: Optional[int] = None) -> list:
    """Raw three-candle gaps, oldest first.

    bullish: Low[i+2] > High[i]  -> band [High[i], Low[i+2]]
    bearish: High[i+2] < Low[i]  -> band [High[i+2], Low[i]]

    Each: {kind, lo, hi, i, disp_i, at, disp_at}. `i` is the THIRD bar —
    the gap exists from that bar on; `disp_i` (= i-1) is the displacement
    candle that left it. Touching (Low[i+2] == High[i]) is not a gap. No
    width or displacement filter: the spec's FVG is the raw gap.
    """
    out: list = []
    arrs = _ohlc(df)
    if arrs is None:
        return out
    _o, h, lo, _c = arrs
    n = len(h)
    if n < 3:
        return out
    start = 0 if not lookback else max(0, n - int(lookback) - 2)
    for i in range(start, n - 2):
        if lo[i + 2] > h[i]:
            out.append({"kind": "bullish", "lo": float(h[i]), "hi": float(lo[i + 2]),
                        "i": i + 2, "disp_i": i + 1,
                        "at": _ts(df, i + 2), "disp_at": _ts(df, i + 1)})
        elif h[i + 2] < lo[i]:
            out.append({"kind": "bearish", "lo": float(h[i + 2]), "hi": float(lo[i]),
                        "i": i + 2, "disp_i": i + 1,
                        "at": _ts(df, i + 2), "disp_at": _ts(df, i + 1)})
    return out


_STATUS_RANK = {"active": 0, "mitigated": 1, "filled": 2, "inverted": 3}


def fvg_state(gaps: list, df) -> list:
    """Each gap with its status against the bars AFTER it formed.

    active     nothing has traded into it
    mitigated  price traded INTO the band (a wick reached it)
    filled     price traded THROUGH it (a wick reached the far edge)
    inverted   a candle CLOSED beyond the far edge — a bearish gap closed
               above its hi becomes inverted bullish support; a bullish gap
               closed below its lo becomes inverted bearish resistance.
               A wick through the far edge is `filled`, not inverted: the
               inversion is the close.

    Adds {status, status_i, status_at, mitigated_i, inverted_kind}. Never
    raises; a gap it cannot read stays `active`.
    """
    out: list = []
    arrs = _ohlc(df)
    if arrs is None:
        return [dict(g, status="active", status_i=None, status_at=None,
                     mitigated_i=None, inverted_kind=None) for g in (gaps or [])]
    _o, h, lo, c = arrs
    n = len(h)
    for g in gaps or []:
        rec = dict(g, status="active", status_i=None, status_at=None,
                   mitigated_i=None, inverted_kind=None)
        try:
            start = int(g["i"]) + 1
            g_lo, g_hi, kind = float(g["lo"]), float(g["hi"]), g["kind"]
        except (KeyError, TypeError, ValueError):
            out.append(rec)
            continue

        def _set(status: str, j: int) -> None:
            if _STATUS_RANK[status] > _STATUS_RANK[rec["status"]]:
                rec["status"], rec["status_i"], rec["status_at"] = status, j, _ts(df, j)

        for j in range(max(0, start), n):
            if kind == "bullish":
                if c[j] < g_lo:
                    _set("inverted", j)
                    rec["inverted_kind"] = "bearish"
                    break
                if lo[j] <= g_lo:
                    if rec["mitigated_i"] is None:
                        rec["mitigated_i"] = j
                    _set("filled", j)
                elif lo[j] <= g_hi:
                    if rec["mitigated_i"] is None:
                        rec["mitigated_i"] = j
                    _set("mitigated", j)
            else:
                if c[j] > g_hi:
                    _set("inverted", j)
                    rec["inverted_kind"] = "bullish"
                    break
                if h[j] >= g_hi:
                    if rec["mitigated_i"] is None:
                        rec["mitigated_i"] = j
                    _set("filled", j)
                elif h[j] >= g_lo:
                    if rec["mitigated_i"] is None:
                        rec["mitigated_i"] = j
                    _set("mitigated", j)
        out.append(rec)
    return out


# ── consolidations ───────────────────────────────────────────────────────────
def consolidations(df, atr: Optional[float] = None, *,
                   min_bars: int = CONSOL_MIN_BARS,
                   max_atr: float = CONSOL_MAX_ATR) -> list:
    """Sideways ranges, oldest first, non-overlapping.

    A run of >= `min_bars` consecutive bars whose combined high-low span is
    <= `max_atr` x ATR (both owner rules — the video says "consolidation"
    and gives no number). One bar too wide ends the run: the range closes on
    the bar before it. Each: {start, end, bars, lo, hi, span_atr, at_start,
    at_end}.
    """
    out: list = []
    arrs = _ohlc(df)
    if arrs is None:
        return out
    _o, h, lo, _c = arrs
    a = atr if atr else atr14(df)
    if not a or a <= 0:
        return out
    n = len(h)
    need = max(2, int(min_bars))
    cap = float(max_atr) * float(a)
    s = 0
    while s < n:
        e = s
        top, bot = h[s], lo[s]
        while e + 1 < n and (max(top, h[e + 1]) - min(bot, lo[e + 1])) <= cap:
            e += 1
            top, bot = max(top, h[e]), min(bot, lo[e])
        if e - s + 1 >= need:
            out.append({"start": s, "end": e, "bars": e - s + 1,
                        "lo": float(bot), "hi": float(top),
                        "span_atr": round((top - bot) / a, 2),
                        "at_start": _ts(df, s), "at_end": _ts(df, e)})
            s = e + 1
        else:
            s += 1
    return out


# ── the manipulation (02:39 — lack of displacement) ──────────────────────────
def manipulation(df, key_low: Optional[float] = None,
                 key_high: Optional[float] = None, *,
                 atr: Optional[float] = None,
                 after: Optional[int] = None,
                 lookback: Optional[int] = None,
                 close_tol_atr: float = DISPLACE_MAX_ATR) -> Optional[dict]:
    """The newest bar that wicked THROUGH a key level but failed to displace.

    Video 02:39: the manipulation drops below the key low but does not close
    strongly below it. Mechanised: Low < key_low AND Close >= key_low -
    close_tol_atr x ATR (owner rule; 0.0 = must close back at or above the
    level). Mirrored for key_high.

    Scans newest-first and DECIDES on the newest bar that traded through the
    level: if that bar closed through by more than the tolerance it is a
    true break, the level is gone, and the answer is None — not an older
    manipulation that the break has since invalidated.

    {i, at, side: low|high, level, extreme, close, displaced: False, bias}.
    """
    arrs = _ohlc(df)
    if arrs is None:
        return None
    _o, h, lo, c = arrs
    n = len(h)
    if key_low is None and key_high is None:
        return None
    a = atr if atr else atr14(df)
    tol = float(close_tol_atr) * float(a) if (a and close_tol_atr) else 0.0
    start = max(0, int(after)) if after is not None else 0
    if lookback:
        start = max(start, n - int(lookback))
    for i in range(n - 1, start - 1, -1):
        if key_low is not None and lo[i] < float(key_low):
            if c[i] >= float(key_low) - tol:
                return {"i": i, "at": _ts(df, i), "side": "low",
                        "level": float(key_low), "extreme": float(lo[i]),
                        "close": float(c[i]), "displaced": False, "bias": "bullish"}
            return None
        if key_high is not None and h[i] > float(key_high):
            if c[i] <= float(key_high) + tol:
                return {"i": i, "at": _ts(df, i), "side": "high",
                        "level": float(key_high), "extreme": float(h[i]),
                        "close": float(c[i]), "displaced": False, "bias": "bearish"}
            return None
    return None


# ── Power of 3 (05:30) ───────────────────────────────────────────────────────
def power_of_three(df, *, atr: Optional[float] = None,
                   consols: Optional[list] = None,
                   direction: Optional[str] = None) -> Optional[dict]:
    """Accumulation range, then the manipulation beyond it.

    Video 05:30: find the accumulation range FIRST; the manipulation is the
    move below its lows (bullish bias) — mirrored above its highs (bearish).
    Newest complete range first; a range still in progress on the last bar
    has no manipulation yet and is skipped.

    {accumulation: <consolidation>, manipulation: <manipulation>, bias}
    """
    arrs = _ohlc(df)
    if arrs is None:
        return None
    n = len(arrs[1])
    a = atr if atr else atr14(df)
    ranges = consols if consols is not None else consolidations(df, a)
    for cs in reversed(ranges or []):
        if cs["end"] >= n - 1:
            continue
        m = manipulation(
            df,
            key_low=cs["lo"] if direction in (None, "bullish") else None,
            key_high=cs["hi"] if direction in (None, "bearish") else None,
            atr=a, after=cs["end"] + 1)
        if m:
            return {"accumulation": cs, "manipulation": m, "bias": m["bias"]}
    return None


# ── the confirmation: opposite displacement that leaves a new FVG ───────────
def opposite_displacement(df, manip: Optional[dict], *,
                          atr: Optional[float] = None,
                          gaps: Optional[list] = None,
                          max_bars: int = CONFIRM_MAX_BARS,
                          min_atr: float = DISPLACE_MIN_ATR) -> Optional[dict]:
    """The energetic push the other way that creates a new fair value gap.

    Video: the fake-out is confirmed when it is immediately followed by
    displacement in the opposite direction that creates a new FVG.
    Mechanised: on the manipulation bar itself or within `max_bars` after
    it (owner rule 3), a bar whose BODY is >= `min_atr` x ATR (owner rule
    1.0) in the opposite direction AND which is the displacement candle of
    a raw FVG in that direction. A big candle that leaves no gap does not
    confirm; a gap left by a small candle does not either.

    {i, at, atr_mult, direction, fvg}
    """
    if not manip:
        return None
    arrs = _ohlc(df)
    if arrs is None:
        return None
    o, h, lo, c = arrs
    n = len(h)
    a = atr if atr else atr14(df)
    if not a or a <= 0:
        return None
    want = "bullish" if manip.get("bias") == "bullish" else "bearish"
    all_gaps = gaps if gaps is not None else fair_value_gaps_raw(df)
    try:
        m_i = int(manip["i"])
    except (KeyError, TypeError, ValueError):
        return None
    for j in range(max(0, m_i), min(n, m_i + 1 + int(max_bars))):
        body = c[j] - o[j]
        if want == "bullish" and body <= 0:
            continue
        if want == "bearish" and body >= 0:
            continue
        if abs(body) < float(min_atr) * a:
            continue
        g = next((g for g in all_gaps if g.get("kind") == want and g.get("disp_i") == j), None)
        if g is None:
            continue
        return {"i": j, "at": _ts(df, j), "atr_mult": round(abs(body) / a, 2),
                "direction": want, "fvg": g}
    return None


# ── market structure shift ───────────────────────────────────────────────────
def mss(df, swings: Optional[tuple] = None, gaps: Optional[list] = None, *,
        direction: Optional[str] = None,
        within: int = MSS_FVG_WITHIN_BARS,
        after: Optional[int] = None,
        lookback: Optional[int] = None) -> Optional[dict]:
    """Market structure shift — the primary entry condition.

    Spec: the current close crosses beyond the most recently formed swing
    point AND a new FVG forms in the breakout direction at the same time.

    Mechanised, newest bar first, reading NOTHING after the bar it labels:
      * the CROSS is bar k — its close is beyond the latest opposing fractal
        swing formed before k while bar k-1's close was not;
      * the GAP is a raw FVG in that direction whose third bar is g (the bar
        the gap exists from);
      * the MSS bar is the LATER of the two, i = max(k, g), with the earlier
        one within `within` bars of it (owner rule 1) and bar i's close still
        beyond the swing.
    The displacement candle that crosses usually leaves its gap one bar
    later, so the MSS is most often labelled on the gap's third bar — the
    first bar on which both conditions are facts. It is never labelled on a
    bar whose gap is only known from the bar after it (that would be a
    look-ahead), and a cross with no gap within the window is not an MSS:
    the scan keeps looking older. `after` bounds both k and i.

    {i, at, level, level_i, direction, fvg, cross_i, cross_at}
    """
    arrs = _ohlc(df)
    if arrs is None:
        return None
    _o, _h, _lo, c = arrs
    n = len(c)
    if n < 3:
        return None
    lows, highs = swings if swings is not None else swing_points_fractal(df)
    all_gaps = gaps if gaps is not None else fair_value_gaps_raw(df)
    dirs = [direction] if direction in ("bullish", "bearish") else ["bullish", "bearish"]
    w = max(0, int(within))
    start = 1
    if after is not None:
        start = max(start, int(after))
    if lookback:
        start = max(start, n - int(lookback))

    def _beyond(d: str, x: float, p: float) -> bool:
        return x > p if d == "bullish" else x < p

    def _prior_swing(pts: list, k: int):
        prior = None
        for j, p in pts:
            if j < k:
                prior = (j, p)
            else:
                break
        return prior

    for i in range(n - 1, start - 1, -1):
        for d in dirs:
            pts = highs if d == "bullish" else lows
            for k in range(i, max(start, i - w) - 1, -1):
                prior = _prior_swing(pts, k)
                if prior is None:
                    continue
                j, p = prior
                if not (_beyond(d, c[k], p) and not _beyond(d, c[k - 1], p)):
                    continue
                if k != i and not _beyond(d, c[i], p):
                    continue
                g = next((g for g in all_gaps
                          if g.get("kind") == d and i - w <= int(g.get("i", -99)) <= i
                          and max(k, int(g.get("i", -99))) == i),
                         None)
                if g is None:
                    continue
                return {"i": i, "at": _ts(df, i), "level": float(p), "level_i": int(j),
                        "direction": d, "fvg": g,
                        "cross_i": int(k), "cross_at": _ts(df, k)}
    return None


# ── stacked consolidations toward the HTF gap (03:57) ────────────────────────
def stacked_consolidations(df, htf_gaps: list, *, consols: Optional[list] = None,
                           atr: Optional[float] = None,
                           last: Optional[float] = None,
                           lookback: int = STACK_LOOKBACK_BARS,
                           min_count: int = STACK_MIN) -> dict:
    """Two or more consolidations between the current price and the nearest
    higher-timeframe fair value gap (video 03:57).

    Mechanised: pick the nearest unfilled HTF gap to the last price. Within
    the last `lookback` bars (owner rule 60), take the consolidations that
    sit on the price side of that gap and step TOWARD it — each successive
    range's midpoint closer to the gap than the one before. Count >=
    `min_count` (video: two or more) is stacked.

    {stacked, count, gap, consolidations, toward: below|above|None}
    """
    empty = {"stacked": False, "count": 0, "gap": None, "consolidations": [],
             "toward": None}
    arrs = _ohlc(df)
    if arrs is None or not htf_gaps:
        return empty
    _o, _h, _lo, c = arrs
    n = len(c)
    try:
        px = float(last) if last is not None else float(c[-1])
    except (TypeError, ValueError):
        return empty
    live = [g for g in htf_gaps
            if g.get("status", "active") in ("active", "mitigated", "inverted")
            and g.get("lo") is not None and g.get("hi") is not None]
    if not live:
        return empty

    def _dist(g):
        lo_, hi_ = float(g["lo"]), float(g["hi"])
        if lo_ <= px <= hi_:
            return 0.0
        return min(abs(px - lo_), abs(px - hi_))

    gap = min(live, key=_dist)
    g_lo, g_hi = float(gap["lo"]), float(gap["hi"])
    a = atr if atr else atr14(df)
    ranges = consols if consols is not None else consolidations(df, a)
    lb = max(1, int(lookback))
    recent = [cs for cs in (ranges or []) if cs["end"] >= n - lb]
    if not recent:
        return dict(empty, gap=gap)

    # Which side is price approaching from? Where it was at the start of the
    # window decides when it is already inside the gap.
    if g_hi < px:
        toward = "below"
    elif g_lo > px:
        toward = "above"
    else:
        origin = float(c[max(0, n - lb)])
        toward = "below" if origin > g_hi else "above"

    kept: list = []
    prev_mid = None
    for cs in recent:                                   # oldest first
        mid = (cs["lo"] + cs["hi"]) / 2.0
        if toward == "below":
            if cs["lo"] < g_hi:                         # sits inside/under the gap: not on the path
                continue
            if prev_mid is not None and mid >= prev_mid:
                continue
        else:
            if cs["hi"] > g_lo:
                continue
            if prev_mid is not None and mid <= prev_mid:
                continue
        kept.append(cs)
        prev_mid = mid
    return {"stacked": len(kept) >= int(min_count), "count": len(kept), "gap": gap,
            "consolidations": kept, "toward": toward}
