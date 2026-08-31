"""Fair Value Gaps, Opening Range, and dynamic entry/stop for zones.

Ajay 2026-08-29: "What are the concepts or ORB and Fair value gap ... For
supply and demand zone ... Give me stop loss and Entry calculated
dynamically."

────────────────────────────────────────────────────────────────────────
FAIR VALUE GAP (FVG) — a three-bar imbalance
────────────────────────────────────────────────────────────────────────
A gap in *traded price*, not in time. Bar 2 moves so hard that bar 1 and
bar 3 never overlap, so there is a price band inside which almost nothing
changed hands — one side simply was not there.

  bullish (demand):  bar1.high < bar3.low   → band = [bar1.high, bar3.low]
  bearish (supply):  bar1.low  > bar3.high  → band = [bar3.high, bar1.low]

Why it is a zone and not a curiosity: the band is unfinished business. If
buyers ran price through it without transacting, the resting orders that
would have filled there are still resting there. Price returning to it is
the market offering those fills — which is exactly the premise of every
supply/demand zone in this app, arrived at from the tape rather than from
a swing pivot.

Two filters keep it from firing on noise:
  * DISPLACEMENT — bar 2's range must exceed `min_displacement_atr` × ATR.
    A gap left by a sleepy bar is a rounding error, not an imbalance.
  * MITIGATION — once price trades back into the band, the gap is being
    filled. `fill_pct` tracks how much is gone; past `max_fill_pct` the
    zone is spent and is dropped. An unfilled gap is the whole signal.

SOURCE HONESTY: FVG comes from the ICT (Inner Circle Trader) body of
material, which is video/community-taught and has NO canonical text in
Ajay's book library — unlike VCP or the trend template, which carry
Minervini page cites. The definition above is the one every mainstream
implementation agrees on (3-bar, no-overlap, displacement-filtered), and
it is stated here in full so what the code does is auditable without a
book. Treat the parameters as this app's choices, not as scripture.

────────────────────────────────────────────────────────────────────────
OPENING RANGE (ORB) — the session's first agreed band
────────────────────────────────────────────────────────────────────────
High/low of the first N minutes of regular trading. Overnight orders,
gap reactions and the first institutional prints all clear inside it, so
it is the day's first honest agreement on value. Price above it means
buyers won the auction; below, sellers did.

  Toby Crabel, *Day Trading with Short Term Price Patterns and Opening
  Range Breakout* (1990) — the original framework.
  Linda Raschke, *Street Smarts* (1995) — volume confirmation.

The app already trades this intraday in `daytrading/signals/orb.py`
(15-minute window, volume-confirmed). Here the SAME band is exposed as a
level on the zone surfaces, sized to the chart being viewed: 15 minutes
on a 15m chart, 60 on an hourly, 30 on a daily — because ORB is
intrinsically an intraday construct, and a daily chart borrows it as
"where today's auction opened", not as a daily-bar pattern.

────────────────────────────────────────────────────────────────────────
DYNAMIC ENTRY / STOP
────────────────────────────────────────────────────────────────────────
Every zone is a band, and a band already implies the trade:

  entry = the PROXIMAL edge (the side price reaches first)
  stop  = the DISTAL edge, plus an ATR-scaled buffer beyond it

For a demand zone below price: entry at the top of the band, stop below
the bottom minus buffer. The buffer exists because a stop resting exactly
on the level everyone can see is the liquidity that gets taken; it scales
with ATR so a quiet name gets a tight stop and a volatile one does not
get shaken out by its own noise.

Risk is then a FACT of the geometry, never a preference: the stop is where
the idea is wrong, and the position is sized off that distance elsewhere
(desk/scoring.position_size). Targets are the next opposing band if one
exists — real structure — and otherwise a measured multiple of risk,
labelled as such so a computed target is never mistaken for a level.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("supply_demand.patterns")

# FVG detection
MIN_DISPLACEMENT_ATR = 0.8      # bar 2 range vs ATR — below this it is noise
MIN_GAP_PCT = 0.15              # band must span at least this % of price
MAX_FILL_PCT = 50.0             # more than half-filled → spent, dropped
FVG_LOOKBACK = 120              # bars scanned for gaps

# Dynamic entry/stop
STOP_BUFFER_ATR = 0.25          # beyond the distal edge
MIN_STOP_BUFFER_PCT = 0.10      # floor, for very quiet names
DEFAULT_TARGET_R = 2.0          # when no opposing structure exists


def atr(df, period: int = 14) -> Optional[float]:
    """Wilder-style ATR on whatever frame is passed (daily or intraday).
    None when the frame is too short — never a guessed volatility."""
    if df is None or len(df) < period + 1:
        return None
    try:
        import pandas as pd
        high, low, close = df["high"], df["low"], df["close"]
        prev = close.shift(1)
        tr = pd.concat([high - low, (high - prev).abs(),
                        (low - prev).abs()], axis=1).max(axis=1)
        val = float(tr.rolling(period).mean().iloc[-1])
        return val if val > 0 else None
    except Exception as exc:                                # pragma: no cover
        log.warning("patterns: atr failed: %s", exc)
        return None


# ── Fair Value Gaps ────────────────────────────────────────────────────────
def fair_value_gaps(df, last_price: Optional[float] = None, *,
                    min_displacement_atr: float = MIN_DISPLACEMENT_ATR,
                    min_gap_pct: float = MIN_GAP_PCT,
                    max_fill_pct: float = MAX_FILL_PCT,
                    lookback: int = FVG_LOOKBACK) -> list:
    """Unfilled three-bar imbalances in `df`, newest first.

    Each gap: {kind: demand|supply, lo, hi, mid, width_pct, fill_pct,
    displacement_atr, bar_index, at}. Returns [] rather than raising on any
    malformed frame — a zone surface must keep rendering.
    """
    out: list = []
    if df is None or len(df) < 3:
        return out
    a = atr(df)
    try:
        frame = df.tail(int(lookback) + 2)
        highs = frame["high"].tolist()
        lows = frame["low"].tolist()
        idx = list(frame.index)
    except Exception:
        return out
    if last_price is None:
        try:
            last_price = float(frame["close"].iloc[-1])
        except Exception:
            return out
    if not last_price or last_price <= 0:
        return out

    n = len(highs)
    for i in range(1, n - 1):
        h1, l1 = highs[i - 1], lows[i - 1]
        h3, l3 = highs[i + 1], lows[i + 1]
        if l3 > h1:                                   # bullish: demand below
            lo, hi, kind = h1, l3, "demand"
        elif l1 > h3:                                 # bearish: supply above
            lo, hi, kind = h3, l1, "supply"
        else:
            continue
        width_pct = (hi - lo) / last_price * 100.0
        if width_pct < min_gap_pct:
            continue

        # Displacement: the middle bar must have actually moved.
        disp_atr = None
        if a:
            disp_atr = (highs[i] - lows[i]) / a
            if disp_atr < min_displacement_atr:
                continue

        # Mitigation: how much of the band did later bars trade back into?
        fill = _fill_pct(lo, hi, kind, highs[i + 2:], lows[i + 2:])
        if fill > max_fill_pct:
            continue
        out.append({
            "kind": kind, "lo": round(lo, 4), "hi": round(hi, 4),
            "mid": round((lo + hi) / 2.0, 4),
            "width_pct": round(width_pct, 2),
            "fill_pct": round(fill, 1),
            "displacement_atr": round(disp_atr, 2) if disp_atr else None,
            "bar_index": i,
            "at": str(idx[i]),
            "source": "fvg",
        })
    out.reverse()                                     # newest gap first
    return out


def _fill_pct(lo: float, hi: float, kind: str, later_highs: list,
              later_lows: list) -> float:
    """How far later bars ate into the band, 0-100. A demand gap fills from
    above (price coming down into it); a supply gap fills from below."""
    span = hi - lo
    if span <= 0 or not later_highs:
        return 0.0
    if kind == "demand":
        deepest = min(later_lows)
        if deepest >= hi:
            return 0.0
        return min(100.0, max(0.0, (hi - max(deepest, lo)) / span * 100.0))
    highest = max(later_highs)
    if highest <= lo:
        return 0.0
    return min(100.0, max(0.0, (min(highest, hi) - lo) / span * 100.0))


# ── Opening Range ──────────────────────────────────────────────────────────
def opening_range_from_bars(df, minutes: int = 15) -> Optional[dict]:
    """The most recent session's opening range from a 1-MINUTE frame. PURE.

    Split out of `opening_range` 2026-08-31 so a caller that already holds the
    minute bars does not pay for a second fetch. The session board reads ~99
    symbols per refresh; calling the fetching version there would have doubled
    the provider load for data already in hand.

    `minutes` is a count of 1-minute BARS, so a halted or thin name whose first
    15 minutes contain 9 prints gets a 9-bar range and says `bars: 9` — the
    window is wall-clock in intent, bar-count in fact, and the payload reports
    which it got.
    """
    if df is None or getattr(df, "empty", True):
        return None
    try:
        import pandas as pd
        et = df.index.tz_localize("UTC").tz_convert("America/New_York") \
            if df.index.tz is None else df.index.tz_convert("America/New_York")
        dates = pd.Series(et.date, index=df.index)
        session_day = dates.max()
        day = df[dates == session_day]
        if day.empty:
            return None
        want = max(1, int(minutes))
        window = day.iloc[:want]
        hi, lo = float(window["high"].max()), float(window["low"].min())
        if hi <= lo:
            return None
        # A range built from fewer bars than the window asked for is still
        # FORMING. Verified live 2026-08-31 at 09:31 ET: one minute had
        # printed and the payload was calling a single bar's high/low "the
        # 15-minute opening range". It is real information — it is the first
        # minute — but it is not yet the level Crabel's premise is about, and
        # a caller must be able to tell the difference before it ranks on it.
        complete = len(window) >= want
        return {"kind": "opening_range", "lo": round(lo, 4),
                "hi": round(hi, 4), "mid": round((lo + hi) / 2.0, 4),
                "minutes": want, "session": str(session_day),
                "bars": len(window), "complete": complete,
                "bars_needed": max(0, want - len(window)), "source": "orb"}
    except Exception as exc:
        log.warning("patterns: opening range from bars failed: %s", exc)
        return None


def opening_range(symbol: str, minutes: int = 15) -> Optional[dict]:
    """The most recent session's opening range from 1-minute bars.

    None when intraday data is unavailable — the surfaces treat that as
    "no ORB level today", never as an error, because a daily-only name
    (thin ETFs, some small caps) legitimately has none.
    """
    try:
        from datetime import date, timedelta

        from daytrading.data import load_intraday_range
        end = date.today()
        df = load_intraday_range(symbol, end - timedelta(days=6), end,
                                 include_premarket=False,
                                 include_afterhours=False)
        if df is None or df.empty:
            return None
        return opening_range_from_bars(df, minutes)
    except Exception as exc:
        log.warning("patterns: opening range for %s failed: %s", symbol, exc)
        return None


def orb_state(orb: Optional[dict], last_price: Optional[float]) -> Optional[str]:
    """Where price stands vs the opening range: above | below | inside.

    Crabel's premise is that the opening range is the session's first agreed
    value; which side of it price holds is the whole read. None when either
    input is missing, because "we could not tell" must not render as "inside".
    """
    if not orb or last_price is None:
        return None
    try:
        px, lo, hi = float(last_price), float(orb["lo"]), float(orb["hi"])
    except (TypeError, ValueError, KeyError):
        return None
    if px > hi:
        return "above"
    if px < lo:
        return "below"
    return "inside"


# ── Dynamic entry / stop ───────────────────────────────────────────────────
def trade_levels(band: dict, last_price: Optional[float],
                 atr_value: Optional[float] = None, *,
                 opposing: Optional[dict] = None,
                 buffer_atr: float = STOP_BUFFER_ATR,
                 target_r: float = DEFAULT_TARGET_R) -> Optional[dict]:
    """Entry, stop, target and R for one band — the geometry, computed.

    `band` needs lo/hi. `opposing` is the nearest band on the other side, used
    as target 1 when it exists (real structure beats a multiple). Returns None
    when the inputs cannot support honest math — a fabricated stop is worse
    than no stop.
    """
    try:
        lo, hi = float(band["lo"]), float(band["hi"])
        last = float(last_price)
    except (KeyError, TypeError, ValueError):
        return None
    if lo <= 0 or hi <= lo or last <= 0:
        return None

    side = "long" if last >= lo else "short"
    # A band price sits inside is still a long-from-support read while the
    # low holds; only a band entirely ABOVE price flips the side.
    if last < lo:
        side = "short"

    buf = max((atr_value or 0.0) * buffer_atr, last * MIN_STOP_BUFFER_PCT / 100.0)
    if side == "long":
        entry, stop = hi, lo - buf
        if stop >= entry:
            return None
        risk = entry - stop
        t1 = (float(opposing["lo"]) if opposing and opposing.get("lo")
              else entry + risk * target_r)
        t1_kind = "next supply band" if opposing else f"{target_r:g}R measured"
        if t1 <= entry:
            t1, t1_kind = entry + risk * target_r, f"{target_r:g}R measured"
    else:
        entry, stop = lo, hi + buf
        if stop <= entry:
            return None
        risk = stop - entry
        t1 = (float(opposing["hi"]) if opposing and opposing.get("hi")
              else entry - risk * target_r)
        t1_kind = "next demand band" if opposing else f"{target_r:g}R measured"
        if t1 >= entry:
            t1, t1_kind = entry - risk * target_r, f"{target_r:g}R measured"

    reward = abs(t1 - entry)
    return {
        "side": side,
        "entry": round(entry, 2), "stop": round(stop, 2),
        "target1": round(t1, 2), "target_basis": t1_kind,
        "risk_per_share": round(risk, 4),
        "risk_pct": round(risk / entry * 100.0, 2),
        "rr": round(reward / risk, 2) if risk > 0 else None,
        "distance_pct": round((entry - last) / last * 100.0, 2),
        "stop_buffer": round(buf, 4),
        "buffer_basis": ("ATR" if (atr_value or 0) * buffer_atr
                         > last * MIN_STOP_BUFFER_PCT / 100.0 else "floor"),
    }


def attach_levels(bands: list, last_price: Optional[float],
                  atr_value: Optional[float] = None) -> list:
    """Give every band its own entry/stop/target, using the nearest band on
    the opposite side as the structural target when one exists."""
    if not bands:
        return []
    demand = sorted([b for b in bands if b.get("kind") == "demand"],
                    key=lambda b: -float(b.get("hi") or 0))
    supply = sorted([b for b in bands if b.get("kind") == "supply"],
                    key=lambda b: float(b.get("lo") or 0))
    out = []
    for b in bands:
        opposing = None
        try:
            if b.get("kind") == "demand":
                opposing = next((s for s in supply
                                 if float(s["lo"]) > float(b["hi"])), None)
            elif b.get("kind") == "supply":
                opposing = next((d for d in demand
                                 if float(d["hi"]) < float(b["lo"])), None)
        except (KeyError, TypeError, ValueError):
            opposing = None
        levels = trade_levels(b, last_price, atr_value, opposing=opposing)
        out.append({**b, "trade": levels})
    return out
