"""Intraday mood and a buy/sell signal, computed on CLOSED bars only.

Ajay 2026-08-29: "I need this in the just in time calculation for support
level for entries and Market sentiment ... on like 15 mins to 1 hours
charts levels to figure out market mood and sentiments for entries. Also
give me a buy signal ... Can you read about Gainz Algo Alpha2 I wonder how
it figures out."

WHAT GAINZALGO ACTUALLY PUBLISHES (researched 2026-08-29)
─────────────────────────────────────────────────────────
Its Pine source is protected and every technical page is vendor-owned. The
published description is "market structure, momentum, volatility and price
action, with adaptive filters, fixed SL/TP, and no repainting". That is an
ARCHITECTURE, not a formula — nobody outside the vendor can reproduce their
weights, and this module does not pretend to. What it does is build the
same architecture out of components this app can verify, and then do the
one thing the vendor cannot do for him: record every signal and measure it
forward (learning/observations), so the hit rate he trades on is HIS, not a
marketing number.

The one claim of theirs worth copying is **no repainting**, and it is a
property, not a feature: a signal is computed from bars that have already
closed and is never revised. `mood()` and `signal()` therefore drop the
final, still-forming bar unless told otherwise. A signal that can change
after you have acted on it is worse than no signal.

MOOD — six components, each bounded, none of them decisive alone
────────────────────────────────────────────────────────────────
  trend      25  price vs EMA20/EMA50 on THIS timeframe, and their order
  momentum   20  RSI(14), scaled around 50, extremes discounted not doubled
  pressure   20  up-volume vs down-volume over the recent window
  vwap       15  price vs session VWAP — the intraday fair-value anchor
  location   10  where price sits in the frame's own range
  structure  10  higher-highs/higher-lows vs lower-highs/lower-lows

Sum is -100..+100. Any component whose input is missing scores 0 and is
reported as unavailable — a missing input is never read as neutral-positive.

BUY SIGNAL — mood is necessary, never sufficient
─────────────────────────────────────────────────
A buy needs BOTH a constructive mood AND price at a level worth buying:
mood >= MOOD_BUY, price inside or within NEAR_PCT of a demand band or an
unfilled bullish fair value gap, and not already extended. The entry, stop
and target come from that band's own geometry (supply_demand.patterns), so
the signal cannot exist without a stop — which is the discipline the whole
app is built on.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("supply_demand.mood")

MOOD_BUY = 25.0            # mood floor for a long signal
MOOD_SELL = -25.0          # mood ceiling for a short/exit signal
NEAR_PCT = 1.5             # how close to a band counts as "at" it
MAX_EXT_PCT = 3.0          # above the band by more than this = chasing
RSI_PERIOD = 14

LABELS = (
    (60.0, "strongly bullish"), (25.0, "bullish"), (10.0, "leaning bullish"),
    (-10.0, "neutral"), (-25.0, "leaning bearish"), (-60.0, "bearish"),
)


def _label(score: float) -> str:
    for floor, name in LABELS:
        if score >= floor:
            return name
    return "strongly bearish"


def _rsi(closes, period: int = RSI_PERIOD) -> Optional[float]:
    try:
        import pandas as pd
        s = pd.Series(closes, dtype=float)
        if len(s) < period + 1:
            return None
        delta = s.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        last_gain, last_loss = float(gain.iloc[-1]), float(loss.iloc[-1])
        if last_loss == 0:
            return 100.0 if last_gain > 0 else 50.0
        rs = last_gain / last_loss
        return float(100 - (100 / (1 + rs)))
    except Exception:
        return None


def _vwap(df) -> Optional[float]:
    """Session VWAP over the LAST session present in the frame. None on a
    daily frame — VWAP is an intraday anchor and a multi-year VWAP is not a
    level anyone trades against."""
    try:
        import pandas as pd
        idx = df.index
        if not isinstance(idx, pd.DatetimeIndex):
            return None
        # The intraday cache indexes bars in NAIVE UTC (daytrading.data does
        # its own tz_localize on read). Treating naive as "no timezone and
        # therefore no VWAP" silently zeroed a 15-point component on exactly
        # the timeframes VWAP exists for — so localize, don't bail.
        et_idx = (idx.tz_localize("UTC") if idx.tz is None else idx
                  ).tz_convert("America/New_York")
        # A daily frame has one bar per day: a "session VWAP" over it is just
        # a slow average, not the intraday anchor traders price against.
        if len(idx) > 1 and (idx[-1] - idx[-2]) >= pd.Timedelta(hours=20):
            return None
        days = pd.Series(et_idx.date, index=idx)
        last_day = days.max()
        day = df[days == last_day]
        if day.empty or "volume" not in day.columns:
            return None
        tp = (day["high"] + day["low"] + day["close"]) / 3.0
        vol = day["volume"].astype(float)
        total = float(vol.sum())
        if total <= 0:
            return None
        return float((tp * vol).sum() / total)
    except Exception:
        return None


def mood(df, *, closed_only: bool = True) -> dict:
    """Market mood on this frame's timeframe. Always answers a dict.

    `closed_only` drops the final still-forming bar — the no-repaint rule.
    """
    out = {"score": 0.0, "label": "unavailable", "components": {},
           "unavailable": [], "bars": 0, "closed_only": closed_only}
    if df is None or len(df) < 5:
        out["unavailable"].append("not enough bars")
        return out
    frame = df.iloc[:-1] if (closed_only and len(df) > 5) else df
    if len(frame) < 5:
        out["unavailable"].append("not enough closed bars")
        return out
    out["bars"] = len(frame)

    try:
        import pandas as pd
        closes = frame["close"].astype(float)
        last = float(closes.iloc[-1])
    except Exception:
        out["unavailable"].append("unreadable frame")
        return out
    if last <= 0:
        out["unavailable"].append("bad price")
        return out

    comp: dict = {}

    # trend (25) — price vs EMA20/EMA50 and their order
    if len(closes) >= 50:
        e20 = float(closes.ewm(span=20, adjust=False).mean().iloc[-1])
        e50 = float(closes.ewm(span=50, adjust=False).mean().iloc[-1])
        pts = 0.0
        pts += 10.0 if last > e20 else -10.0
        pts += 8.0 if last > e50 else -8.0
        pts += 7.0 if e20 > e50 else -7.0
        comp["trend"] = round(pts, 1)
    else:
        comp["trend"] = 0.0
        out["unavailable"].append("trend (needs 50 bars)")

    # momentum (20) — RSI around 50; extremes are discounted, not doubled,
    # because an RSI of 85 is as often exhaustion as strength.
    rsi = _rsi(closes)
    if rsi is None:
        comp["momentum"] = 0.0
        out["unavailable"].append("momentum (needs RSI period)")
    else:
        raw = (rsi - 50.0) / 50.0 * 20.0
        if rsi > 75 or rsi < 25:
            raw *= 0.6
        comp["momentum"] = round(max(-20.0, min(20.0, raw)), 1)
        out["rsi"] = round(rsi, 1)

    # pressure (20) — up vs down volume over the recent window
    if "volume" in frame.columns and len(frame) >= 20:
        win = frame.tail(20)
        up = float(win.loc[win["close"] >= win["open"], "volume"].sum())
        dn = float(win.loc[win["close"] < win["open"], "volume"].sum())
        tot = up + dn
        comp["pressure"] = round(((up - dn) / tot) * 20.0, 1) if tot > 0 else 0.0
        if tot <= 0:
            out["unavailable"].append("pressure (no volume)")
    else:
        comp["pressure"] = 0.0
        out["unavailable"].append("pressure (needs 20 bars of volume)")

    # vwap (15) — intraday fair value; absent on daily frames by design
    vw = _vwap(frame)
    if vw:
        gap = (last - vw) / vw * 100.0
        comp["vwap"] = round(max(-15.0, min(15.0, gap * 5.0)), 1)
        out["vwap"] = round(vw, 2)
    else:
        comp["vwap"] = 0.0
        out["unavailable"].append("vwap (intraday frames only)")

    # location (10) — where price sits in the frame's own range
    hi, lo = float(frame["high"].max()), float(frame["low"].min())
    if hi > lo:
        pos = (last - lo) / (hi - lo)
        comp["location"] = round((pos - 0.5) * 20.0, 1)
    else:
        comp["location"] = 0.0

    # structure (10) — higher highs/lows vs lower
    if len(frame) >= 20:
        half = len(frame) // 2
        a, b = frame.iloc[:half], frame.iloc[half:]
        hh = float(b["high"].max()) > float(a["high"].max())
        hl = float(b["low"].min()) > float(a["low"].min())
        comp["structure"] = 10.0 if (hh and hl) else (-10.0 if not (hh or hl) else 0.0)
    else:
        comp["structure"] = 0.0

    score = round(sum(comp.values()), 1)
    out["components"] = comp
    out["score"] = score
    out["label"] = _label(score)
    out["last"] = round(last, 2)
    return out


def signal(df, bands: list, mood_read: Optional[dict] = None, *,
           last_price: Optional[float] = None,
           atr_value: Optional[float] = None) -> dict:
    """BUY / SELL / WAIT on this timeframe, with the level that justifies it.

    A buy needs a constructive mood AND price at a band worth buying. Mood
    alone is a weather report, not a trade: without a level there is no
    stop, and without a stop there is no position size.
    """
    from supply_demand import patterns as pat_mod

    m = mood_read if mood_read is not None else mood(df)
    out = {"action": "WAIT", "mood": m.get("score"), "mood_label": m.get("label"),
           "reasons": [], "blockers": [], "level": None, "trade": None,
           "no_repaint": True}
    if m.get("label") == "unavailable":
        out["blockers"].append("mood unavailable — not enough closed bars")
        return out

    last = last_price
    if last is None:
        last = m.get("last")
    try:
        last = float(last)
    except (TypeError, ValueError):
        out["blockers"].append("no price")
        return out
    if last <= 0 or not bands:
        out["blockers"].append("no bands on this timeframe")
        return out

    score = float(m.get("score") or 0.0)

    # Nearest demand band at or below price, within reach.
    demand = []
    for b in bands:
        try:
            lo, hi = float(b["lo"]), float(b["hi"])
        except (KeyError, TypeError, ValueError):
            continue
        if b.get("kind") != "demand":
            continue
        if lo <= last <= hi:
            demand.append((0.0, b, "inside"))
        elif last > hi:
            dist = (last - hi) / last * 100.0
            if dist <= NEAR_PCT:
                demand.append((dist, b, "just above"))
        else:
            dist = (lo - last) / last * 100.0
            if dist <= NEAR_PCT:
                demand.append((dist, b, "just below"))
    demand.sort(key=lambda x: x[0])

    if score < MOOD_BUY:
        out["blockers"].append(
            f"mood {score:g} below the {MOOD_BUY:g} floor ({m.get('label')})")
    if not demand:
        out["blockers"].append(
            f"price is not within {NEAR_PCT:g}% of a demand band")

    if not out["blockers"]:
        dist, band, where = demand[0]
        levels = pat_mod.trade_levels(band, last, atr_value)
        if not levels:
            out["blockers"].append("band geometry cannot support a stop")
        elif dist > MAX_EXT_PCT:
            out["blockers"].append(f"{dist:.1f}% above the band — chasing")
        else:
            out["action"] = "BUY"
            out["level"] = {**band, "where": where,
                            "distance_pct": round(dist, 2)}
            out["trade"] = levels
            out["reasons"] = [
                f"mood {score:g} ({m.get('label')})",
                f"price {where} a {band.get('source', 'swing')} demand band "
                f"{band.get('lo')}–{band.get('hi')}",
                f"stop {levels['stop']} = {levels['risk_pct']}% risk, "
                f"{levels['rr']}R to {levels['target1']}",
            ]

    if out["action"] == "WAIT" and score <= MOOD_SELL:
        out["action"] = "SELL"
        out["reasons"] = [f"mood {score:g} ({m.get('label')}) — "
                          "distribution, not a dip to buy"]
        # The blockers explain why a BUY did not fire. On a SELL they would
        # read as reasons the SELL is doubtful, which is the opposite of
        # what they mean, so they move to their own key.
        out["buy_blockers"], out["blockers"] = out["blockers"], []
    return out
