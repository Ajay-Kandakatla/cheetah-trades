"""〰️ 9 EMA · W/M — the 9-period EMA drawn on WEEKLY and MONTHLY bars.

Ajay 2026-09-23, verbatim: *"Also a new tab for 9EMA lines on our charts for
weekly charts and monthly charts please"*.

ONE tab, one frame at a time (weekly | monthly). Nothing here is measured:
no study on this app's universe has ever tested a 9-period EMA on weekly or
monthly bars, so this module gates nothing, orders nothing, filters nothing
and alerts nothing. It DRAWS.

────────────────────────────────────────────────────────────────────────────
THE RESAMPLE CONVENTION, AND WHY IT IS NOT THE INTRADAY ONE
────────────────────────────────────────────────────────────────────────────
`supply_demand.timeframes.resample_ohlcv` resamples 1-MINUTE bars with
`label="right", closed="left"`, and that is correct THERE: an intraday index
stamp is the START of its interval, so the 09:30 minute covers 09:30–09:31 and
must be the first minute of the 09:30 fifteen-minute bar, not the last minute
of the one before it.

A DAILY bar is not an interval stamp. Its index is the SESSION DATE — a whole
day, not the instant it opened — so the week it belongs to is decided by the
calendar, and the natural label for a week of sessions is the day it ends on.
That is pandas' own default for a date anchor (`label="right",
closed="right"`) and it is what this codebase already does everywhere it takes
daily bars to weekly: `sepa.market_gauge._to_weekly` and
`sepa.venky_filters` both call `df.resample("W-FRI")` with the defaults.

    weekly   W-FRI, pandas defaults  -> bins (Fri_{k-1}, Fri_k], i.e. Mon–Fri,
                                        labelled by that week's Friday.
    monthly  ME,    pandas defaults  -> bins (month-end, month-end], i.e. one
                                        calendar month, labelled by its last
                                        calendar day.

W-FRI, not W-SUN: a Sunday anchor labels a US equity week with a day the market
was shut, and the two existing weekly readers in this repo are Friday-anchored
— two weekly conventions in one app is how the same name gets two different
weekly closes on two pages.

"ME", not "M": pandas 2.x deprecated the bare "M" alias. (`tv_datafeed._resample`
still passes "M"; it is the TradingView UDF feed, has its own label convention
for a charting client, and is not touched here.)

────────────────────────────────────────────────────────────────────────────
THE FORMING BAR
────────────────────────────────────────────────────────────────────────────
Today is mid-week and mid-month, so the last weekly and the last monthly bar
are INCOMPLETE. They are shown — a trader reads where this week is trading
against the line, not where last week finished — and they are MARKED, three
ways that cannot drift apart: the bar carries `s: "forming"` (PatternChart
already shades and dims a tagged bar), the tile carries a badge saying so, and
the payload carries `forming` with the period's end date. A forming bar drawn
as a finished one is the same class of lie as a last-close number under a live
header, which this app has shipped twice.

A period is forming when its END date has not passed yet (label >= today, ET).
That rule errs toward "forming": on Friday after the close the week is still
called forming until Saturday. Over-marking is the safe side of this error.

CLOSED DAILY SESSIONS ONLY. `prices.with_today_bar` is NOT applied — today's
pre/after-hours print is never folded into a weekly OHLC. The forming bar is
built from the closed sessions of this week/month and nothing else, which is
also why the tile can say plainly what it is made of.

────────────────────────────────────────────────────────────────────────────
THE EMA
────────────────────────────────────────────────────────────────────────────
`ewm(span=9, adjust=False)` — the house call — on the RESAMPLED closes. A
9-WEEK EMA, a 9-MONTH EMA. Never a 9-day EMA relabelled: that is the bug the
tests pin.

9 is HIS number. There is no 10, no 21, no 50 here.

WARM-UP: the first 8 points of a span-9 EMA are computed from fewer than 9
periods, so they are served as GAPS, and a frame with fewer than 9 COMPLETED
periods serves no curve at all with a served sentence saying how many it has.
That is arithmetic — "is there enough data to compute it" — not a quality bar.

The curve is aligned to the tile's bars BY DATE, never by position, following
`board._keltner_curves`. Here the bars and the series come off the same
resampled frame, so a positional tail would happen to work today; it is done by
date anyway because the day it stops being true is the day the chart is wrong
everywhere and says nothing.
"""
from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Optional

log = logging.getLogger("chart_maps.ema_frames")

# ── the two frames he asked for ─────────────────────────────────────────────
FRAMES = ("weekly", "monthly")
DEFAULT_FRAME = "weekly"

#: pandas resample rule per frame. See the module docstring for the label /
#: closed convention and why it differs from the intraday one.
FRAME_RULE = {"weekly": "W-FRI", "monthly": "ME"}
#: The period noun, for sentences the reader sees ("9-week EMA").
FRAME_NOUN = {"weekly": "week", "monthly": "month"}
#: What the frame IS, spelled out once, so no surface types its own version.
FRAME_WHAT = {
    "weekly": "Mon–Fri bars, labelled by that week’s Friday (W-FRI)",
    "monthly": "calendar-month bars, labelled by the month end (ME)",
}

#: HIS number. 9, and only 9.
EMA_SPAN = 9
#: The fewest COMPLETED periods an EMA of span 9 can be computed from at all.
#: Deliberately the span itself — it is arithmetic, not a quality threshold.
MIN_PERIODS = EMA_SPAN

#: The curve tone. Shared with the daily 9 EMA overlay so ONE checkbox governs
#: every 9 EMA this app draws, on any timeframe.
CURVE_TONE = "ema9"

#: The forming bar's session tag. PatternChart shades and dims any tagged bar.
FORMING_TAG = "forming"

#: Daily bars fetched before resampling — the board's own deep window (5y), so
#: a monthly frame has something to be a monthly frame OF. No new number.
DAILY_BARS = 1260

NO_SYMBOL = "Type a ticker — this tab draws one chart per name on your ⚡ Signals watchlist."
NOT_MEASURED = ("Nothing about a 9 EMA on weekly or monthly bars has been "
                "measured on this universe — no study, no interval, no "
                "out-of-sample. It is a drawing: it orders nothing, hides "
                "nothing and alerts nothing.")


def parse_frame(v) -> str:
    """'weekly' | 'monthly'. Anything else is the default — a stale bookmark
    should draw the board, never a 422."""
    s = (v if isinstance(v, str) else "").strip().lower()
    return s if s in FRAMES else DEFAULT_FRAME


def resample_ohlcv(df, frame: str):
    """Daily OHLCV (DatetimeIndex) -> weekly or monthly OHLCV. None when unusable.

    Pandas DEFAULTS on the label/closed pair — see the module docstring. Buckets
    with no session at all (a holiday-shortened frame's empty week) are dropped
    rather than served as a NaN bar.
    """
    if df is None or not len(df):
        return None
    rule = FRAME_RULE.get(parse_frame(frame))
    try:
        d = df.rename(columns={c: str(c).lower() for c in df.columns})
        if not {"open", "high", "low", "close"} <= set(d.columns):
            return None
        agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
        if "volume" in d.columns:
            agg["volume"] = "sum"
        out = d.resample(rule).agg(agg).dropna(how="any")
        return out if len(out) else None
    except Exception as exc:                                    # pragma: no cover
        log.debug("ema-frames: resample %s failed: %s", frame, exc)
        return None


def is_forming(period_end, today: Optional[date] = None) -> bool:
    """True when this period has not ended yet — its label date is today or
    later. The rule errs toward forming; see the module docstring."""
    if period_end is None:
        return False
    try:
        end = period_end.date() if hasattr(period_end, "date") else date.fromisoformat(str(period_end)[:10])
    except Exception:                                           # pragma: no cover
        return False
    return end >= (today or _today_et())


def _today_et() -> date:
    try:
        from .board import ET
        return datetime.now(ET).date()
    except Exception:                                           # pragma: no cover
        return datetime.now().date()


def ema_values(closes: list, span: int = EMA_SPAN,
               min_periods: int = MIN_PERIODS) -> list:
    """`ewm(span, adjust=False)` over `closes`, with the first
    `min_periods - 1` points served as None.

    A point computed from fewer than `min_periods` closes is a seed, not a
    9-period average, and a seed drawn as the line is a number that means
    something other than its label.
    """
    vals = [float(c) for c in (closes or [])]
    if not vals:
        return []
    import pandas as pd
    ser = pd.Series(vals).ewm(span=int(span), adjust=False).mean()
    out: list = []
    for i, v in enumerate(ser.tolist()):
        out.append(None if i < max(0, int(min_periods) - 1) or v != v else round(float(v), 4))
    return out


def _frame_to_bars(df, forming_date: Optional[str]) -> list[dict]:
    """Resampled rows -> the tile's bar dicts. The forming period carries
    `s: FORMING_TAG`; every completed period carries no tag at all."""
    bars: list[dict] = []
    for ts, row in df.iterrows():
        try:
            t = ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts)[:10]
            b = {
                "t": t,
                "o": round(float(row["open"]), 4),
                "h": round(float(row["high"]), 4),
                "l": round(float(row["low"]), 4),
                "c": round(float(row["close"]), 4),
                "v": float(row.get("volume") or 0.0),
            }
            if forming_date and t == forming_date:
                b["s"] = FORMING_TAG
            bars.append(b)
        except Exception:                                       # pragma: no cover
            continue
    return bars


def curve_for(bars: list, dates: list, values: list, frame: str) -> Optional[dict]:
    """The 9 EMA as ONE curve aligned to `bars` BY DATE.

    `dates` / `values` are the resampled series. A bar with no value for its
    date becomes a gap (None), never a guess. Returns None when the alignment
    leaves nothing to draw.
    """
    by_date = {str(d): v for d, v in zip(dates or [], values or [])}
    vals = [by_date.get(str(b.get("t"))) for b in (bars or [])]
    if not any(v is not None for v in vals):
        return None
    return {"tone": CURVE_TONE,
            "label": f"9 EMA ({parse_frame(frame)})",
            "values": vals}


def no_curve_reason(completed: int, frame: str) -> str:
    noun = FRAME_NOUN[parse_frame(frame)]
    return (f"{completed} completed {noun}{'' if completed == 1 else 's'} of history "
            f"— a {EMA_SPAN}-{noun} EMA needs {MIN_PERIODS}.")


def forming_note(frame: str, period_end: str) -> str:
    noun = FRAME_NOUN[parse_frame(frame)]
    return (f"The last bar is this {noun} still forming — it ends "
            f"{period_end} and is drawn from the closed daily sessions so far.")


def _why(frame: str, reason: Optional[str], forming: bool, last_date: str) -> str:
    """The tile's one sentence. The MISSING curve outranks the forming bar:
    "there is no line yet" is the first thing to say when there is no line."""
    if reason:
        return reason
    if forming:
        return forming_note(frame, last_date)
    return f"9-{FRAME_NOUN[parse_frame(frame)]} EMA on {FRAME_WHAT[parse_frame(frame)]}."


def build(symbol: str, frame: str = DEFAULT_FRAME, *,
          today: Optional[date] = None, df=None) -> dict:
    """One name, one frame: `{symbol, frame, tile, forming, note, error}`.

    `df` (tests, and any caller that already holds the daily frame) skips the
    price fetch entirely. Otherwise the CLOSED 5-year daily frame comes from
    `chart_maps.support._frame_for` — the Support tab's own deep frame, with
    the Support tab's own cache, so this tab costs no new provider call when
    that one has already been opened.
    """
    sym = (symbol if isinstance(symbol, str) else "").strip().upper()
    fr = parse_frame(frame)
    if not sym:
        return {"symbol": "", "frame": fr, "tile": None, "error": NO_SYMBOL,
                "note": NOT_MEASURED}

    if df is None:
        try:
            from . import support as _support
            # `snap={}` = "already fetched, this symbol was absent" — no
            # fetch, NO OVERLAY (support._overlay_today's own documented
            # sentinel). It is load-bearing, not an optimisation:
            # `_closed_of` only strips the last row when `with_today_bar` set
            # `partial=True`, and NEITHER after-hours branch does
            # (prices.py:706 sets no `partial`; :753 sets
            # `partial=(session != "afterhours")` → False). Both call
            # `_extend_last_row`, which OVERWRITES the last daily close with
            # the after-hours print and widens its high/low. So between 16:00
            # and 20:00 ET a frame fetched with an overlay hands this resample
            # an AH close on its last session, and the forming weekly/monthly
            # bar would close on it while the tile's own sentence says the
            # bars are closed sessions. Refusing the overlay outright is the
            # only way that sentence stays true — and it costs one fewer
            # HTTPS call per name. Do NOT "fix" this by flipping `partial` in
            # prices.py; that changes what every other caller reads.
            res = _support._frame_for(sym, DAILY_BARS, with_closed=True, snap={})
            # CLOSED bars only. index 3 is the frame without today's live bar;
            # a 3-tuple stub has no live overlay to strip in the first place.
            df = res[3] if len(res) > 3 and res[3] is not None else res[0]
        except Exception as exc:                                # noqa: BLE001
            log.debug("ema-frames: frame for %s failed: %s", sym, exc)
            df = None

    rs = resample_ohlcv(df, fr)
    if rs is None:
        return {"symbol": sym, "frame": fr, "tile": None,
                "error": f"No price history for {sym}.", "note": NOT_MEASURED}

    last_idx = rs.index[-1]
    forming = is_forming(last_idx, today)
    forming_date = (last_idx.strftime("%Y-%m-%d") if forming and hasattr(last_idx, "strftime")
                    else None)
    bars = _frame_to_bars(rs, forming_date)
    completed = len(bars) - (1 if forming else 0)

    dates = [b["t"] for b in bars]
    curve = None
    reason = None
    if completed >= MIN_PERIODS:
        curve = curve_for(bars, dates, ema_values([b["c"] for b in bars]), fr)
    if curve is None:
        reason = no_curve_reason(max(0, completed), fr)

    badges = []
    if forming:
        badges.append({"text": f"▱ {FRAME_NOUN[fr]} still forming", "tone": "warn"})
    if reason:
        badges.append({"text": "no 9 EMA yet", "tone": "muted"})

    last_ema = None
    if curve:
        for v in reversed(curve["values"]):
            if v is not None:
                last_ema = v
                break

    tile = {
        "symbol": sym,
        "name": _name_for(sym),
        "href": _href(sym),
        "bars": bars,
        "bands": [],
        "lines": [],
        "markers": [],
        "curves": ([curve] if curve else []),
        "badges": badges,
        "stats": [
            {"k": "Frame", "v": f"{fr.capitalize()} — {FRAME_WHAT[fr]}"},
            {"k": f"{FRAME_NOUN[fr].capitalize()}s drawn", "v": str(len(bars))},
            {"k": f"9-{FRAME_NOUN[fr]} EMA",
             "v": (f"{last_ema:.2f}" if last_ema is not None else "—")},
            {"k": "Last bar",
             "v": f"{dates[-1]} · forming" if forming else dates[-1]},
        ],
        "why": _why(fr, reason, forming, dates[-1]),
        "theme": _theme(sym),
    }
    return {"symbol": sym, "frame": fr, "tile": tile,
            "periods": len(bars), "completed_periods": completed,
            "forming": ({"date": dates[-1], "frame": fr,
                         "note": forming_note(fr, dates[-1])} if forming else None),
            "curve_reason": reason, "error": None, "note": NOT_MEASURED}


def _name_for(symbol: str) -> Optional[str]:
    try:
        from .board import _name_for as f
        return f(symbol)
    except Exception:                                           # pragma: no cover
        return None


def _theme(symbol: str) -> Optional[str]:
    try:
        from .board import _theme as f
        return f(symbol)
    except Exception:                                           # pragma: no cover
        return None


def _href(symbol: str) -> str:
    try:
        from .board import _href as f
        return f(symbol, "support")
    except Exception:                                           # pragma: no cover
        return f"/chart-maps?tab=support&symbol={symbol}"
