"""Keltner channels, plus the squeeze — a chart overlay, not a tab.

Ajay 2026-09-12: *"Can you then implement the Keltner channel strategy a new tab
in chart maps please"*, then, asked tab-or-overlay:
*"Over lay I think is better to toggle off if I want to"*. So: one more
checkbox in the ledger, OFF by default like the other three studies.

WHICH "KELTNER STRATEGY"
───────────────────────
There are three and they trade OPPOSITE ways — band-fade (sell the top, buy the
bottom), trend-pullback (ride the upper band, buy the midline retest), and
squeeze-breakout (compression, then expansion). An overlay does not have to
choose: it draws the CHANNEL, which all three read, and labels the one state
that is not visible by eye — the squeeze.

Band-fade in particular is deliberately NOT modelled as a signal here: it would
duplicate `supply_demand/meanrev.py`, shipped the same day, and neither has
been measured.

SOURCE STATUS
─────────────
Chester Keltner's original used a 10-day SMA of typical price with the daily
range; the modern form below (EMA + ATR) is Linda Raschke's revision, and the
squeeze test is John Carter's TTM construction. **None of that is a cited book
in Ajay's library, and none of it has been measured forward on his names.**
`CITED = False`. It gates nothing: no scan reads it, no alert fires from it, no
lane buys on it.

THE ARITHMETIC, written out so it is auditable without a platform
────────────────────────────────────────────────────────────────
  mid    = EMA(close, EMA_LEN)
  upper  = mid + MULT * ATR(ATR_LEN)
  lower  = mid - MULT * ATR(ATR_LEN)

  squeeze  =  Bollinger(BB_LEN, BB_STD) sits INSIDE Keltner(SQUEEZE_MULT)
              i.e. bb_upper < k_upper AND bb_lower > k_lower

A squeeze is a statement about VOLATILITY, not direction. It says the range has
compressed; it says nothing about which way the expansion goes, and this module
never claims one.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("supply_demand.keltner")

# CONVENTION, all of them. EMA 20 / ATR 10 / 2.0 is the modern default the
# charting packages ship; Carter's squeeze compares against a TIGHTER 1.5x
# channel, which is why SQUEEZE_MULT is separate from MULT.
EMA_LEN = 20
ATR_LEN = 10
MULT = 2.0
SQUEEZE_MULT = 1.5
BB_LEN = 20
BB_STD = 2.0
MIN_BARS = 40

CITED = False
SOURCE_NOTE = ("Keltner channel (Raschke's EMA+ATR form) and the TTM squeeze "
               "(Carter) — chart convention, no cited source in his library, "
               "never measured forward. Display only: nothing gates on it. A "
               "squeeze is a volatility statement, never a direction.")


def _f(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (f != f or f in (float("inf"), float("-inf"))) else f


def _atr(df, period: int = ATR_LEN):
    """Wilder ATR as a SERIES. `patterns.atr` returns the last value only, and
    the squeeze has to be evaluated bar by bar."""
    import pandas as pd
    h, l = df["high"].astype(float), df["low"].astype(float)
    c = df["close"].astype(float).shift(1)
    tr = pd.concat([h - l, (h - c).abs(), (l - c).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def channel(df, *, ema_len: int = EMA_LEN, atr_len: int = ATR_LEN,
            mult: float = MULT) -> Optional[dict]:
    """{"mid","upper","lower","width_pct","position"} at the LAST bar, or None.

    `position` is where the close sits in the channel: 0.0 at the lower band,
    1.0 at the upper, and it runs outside [0,1] when price is beyond a band —
    clamping would hide exactly the case the overlay exists to show.
    """
    if df is None or len(df) < max(MIN_BARS, ema_len, atr_len):
        return None
    try:
        close = df["close"].astype(float)
        mid_s = close.ewm(span=ema_len, adjust=False).mean()
        atr_s = _atr(df, atr_len)
        mid, atr = _f(mid_s.iloc[-1]), _f(atr_s.iloc[-1])
        last = _f(close.iloc[-1])
    except Exception as exc:                                   # noqa: BLE001
        log.debug("keltner: channel failed: %s", exc)
        return None
    if mid is None or atr is None or last is None or atr <= 0:
        return None
    upper, lower = mid + mult * atr, mid - mult * atr
    span = upper - lower
    return {"mid": round(mid, 4), "upper": round(upper, 4),
            "lower": round(lower, 4), "atr": round(atr, 4),
            "width_pct": round(100.0 * span / mid, 2) if mid else None,
            "position": round((last - lower) / span, 3) if span > 0 else None,
            "last": last}


def squeeze(df, *, ema_len: int = EMA_LEN, atr_len: int = ATR_LEN,
            squeeze_mult: float = SQUEEZE_MULT, bb_len: int = BB_LEN,
            bb_std: float = BB_STD) -> Optional[dict]:
    """{"on","bars","released"} — is the Bollinger band inside the Keltner one?

    `bars` counts how many consecutive bars the squeeze has been on (0 when
    off). `released` is True on the FIRST bar after a squeeze of any length
    ends, which is the only moment the construction actually marks.
    """
    if df is None or len(df) < max(MIN_BARS, bb_len, atr_len) + 2:
        return None
    try:
        close = df["close"].astype(float)
        mid = close.ewm(span=ema_len, adjust=False).mean()
        atr = _atr(df, atr_len)
        k_up, k_dn = mid + squeeze_mult * atr, mid - squeeze_mult * atr
        bb_mid = close.rolling(bb_len).mean()
        bb_sd = close.rolling(bb_len).std(ddof=0)
        b_up, b_dn = bb_mid + bb_std * bb_sd, bb_mid - bb_std * bb_sd
        on = (b_up < k_up) & (b_dn > k_dn)
        on = on.fillna(False).tolist()
    except Exception as exc:                                   # noqa: BLE001
        log.debug("keltner: squeeze failed: %s", exc)
        return None
    if not on:
        return None
    now = bool(on[-1])
    bars = 0
    if now:
        for v in reversed(on):
            if not v:
                break
            bars += 1
    return {"on": now, "bars": bars,
            "released": bool(len(on) >= 2 and on[-2] and not on[-1])}


def reading(df, **kw) -> Optional[dict]:
    """The one-line verdict: channel position plus the squeeze state."""
    ch = channel(df, **{k: v for k, v in kw.items()
                        if k in ("ema_len", "atr_len", "mult")})
    if not ch:
        return None
    sq = squeeze(df) or {"on": False, "bars": 0, "released": False}
    pos = ch["position"]
    # "unknown" is a real branch, not a tidy-up. `position` is None whenever the
    # channel has no span (ATR collapsed to zero on a halted or one-price
    # name), and the old chain fell through every test to the CONCRETE string
    # "lower half" — an unmeasurable name reading as a definite state. Anything
    # written off `where` (a badge, a "not coiled so it's clear" sentence)
    # would then be asserting the favourable read on no evidence.
    where = ("unknown" if pos is None else
             "above the upper band" if pos > 1 else
             "below the lower band" if pos < 0 else
             "upper half" if pos >= 0.5 else "lower half")
    return {**ch, "squeeze": sq["on"], "squeeze_bars": sq["bars"],
            "squeeze_released": sq["released"], "where": where,
            # said every time, because a squeeze reads like a signal and is not
            "note": "a squeeze is compression, not a direction"}


def channel_series(df, *, ema_len: int = EMA_LEN, atr_len: int = ATR_LEN,
                   mult: float = MULT) -> Optional[dict]:
    """The channel as a SERIES — one upper/mid/lower per bar, keyed by date.

    THE BUG THIS EXISTS TO FIX (Ajay 2026-09-13, MU): *"I was hoping to see the
    KC bands like this but it should flat horizontal. Are they accurate?"*
    `chart_lines` returns the channel at the LAST bar as three scalars, and a
    scalar renders as a horizontal level across the whole tile. The numbers
    were right for the last bar and wrong for every other bar on the screen:
    the drawing asserted the band sat at 1056.21 three months ago, when it was
    somewhere else entirely. A Keltner channel is an EMA plus an ATR multiple;
    both move every bar, so the channel bends and the drawing has to bend with
    it.

    Computed on the FULL frame that comes in, never on a zoom slice — an EMA
    and a Wilder ATR both need warm-up, and seeding them at the left edge of a
    6-month window would draw a channel that is wrong exactly where the eye
    lands first.

    Returns {"dates": [...], "upper": [...], "mid": [...], "lower": [...]} with
    None in any slot the warm-up has not filled, or None when the frame is too
    short. A None must survive to the renderer as a GAP: joining across it
    would draw a straight segment through prices the channel never had.
    """
    if df is None or len(df) < max(MIN_BARS, ema_len, atr_len):
        return None
    try:
        close = df["close"].astype(float)
        mid_s = close.ewm(span=ema_len, adjust=False).mean()
        atr_s = _atr(df, atr_len)
        dates = [str(getattr(d, "date", lambda: d)())[:10] for d in df.index]
    except Exception as exc:                                   # noqa: BLE001
        log.debug("keltner: channel_series failed: %s", exc)
        return None
    up, mi, lo = [], [], []
    for m, a in zip(mid_s.tolist(), atr_s.tolist()):
        mf, af = _f(m), _f(a)
        if mf is None or af is None or af <= 0:
            up.append(None), mi.append(None), lo.append(None)
            continue
        up.append(round(mf + mult * af, 4))
        mi.append(round(mf, 4))
        lo.append(round(mf - mult * af, 4))
    if not any(v is not None for v in mi):
        return None
    return {"dates": dates, "upper": up, "mid": mi, "lower": lo}


def chart_lines(df, **kw) -> list:
    """Three lines for a tile: {price, label, tone}. Tone is always "keltner"
    so the family gets its own checkbox and can never be mistaken for the
    demand/supply levels he trades."""
    r = reading(df, **kw)
    if not r:
        return []
    tag = " · squeeze %db" % r["squeeze_bars"] if r["squeeze"] else ""
    return [
        {"price": r["upper"], "tone": "keltner", "label": "KC upper %.2f" % r["upper"]},
        {"price": r["mid"], "tone": "keltner",
         "label": "KC mid %.2f%s" % (r["mid"], tag)},
        {"price": r["lower"], "tone": "keltner", "label": "KC lower %.2f" % r["lower"]},
    ]
