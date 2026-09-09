"""STATIONARY BOTTOM — the swing-structure lens. Re-runnable measurement.

    docker cp studies/stationary_bottom_swing_study.py cheetah-market-app-api-1:/tmp/sb.py
    docker exec cheetah-market-app-api-1 sh -c 'cd /app && PYTHONPATH=/app python -u /tmp/sb.py'
    ... --sweep      run the constant sensitivity sweep on the named cases
    ... --symbols CASY,HOOD,OLLI

WHY THIS FILE EXISTS
--------------------
Ajay 2026-09-09, after buying CASY into an earnings gap: "I need only bullish
reversal stocks that touched demand zone and bouncing back ... After a
stationary bottommed stocks as I caught a fallig knife today with Casy".

`alert_gates.direction_gate` already says price is BOUNCING today.
`sd_liquidity.is_falling_knife` already says the name is not in a stepping-down
downtrend. Neither says price has gone FLAT. `structure_read` compares the last
two 5-bar pivot lows and answers "higher or lower" — it has no notion of how
long ago the newest low was printed, of how many sessions were spent at that
level, or of whether the lows cluster at all. A single pivot one cent above the
last one reads "rising" in a name that is still sliding a percent a day.

THE CLAIM, in neutral price-structure terms (no book, no SEPA/Minervini
concepts, no trend template, no stage, no base counts):

    A stationary bottom is a price SHELF. Over the last K closed sessions the
    lowest low is not the newest one, and that lowest level has been visited
    repeatedly, over a stretch of time, rather than printed once on the way
    down.

Four measurements, all from daily OHLCV, all on CLOSED bars:

    B  bars_since_new_low   sessions since the window's lowest low was printed
    C  lows_at_shelf        how many of the K lows sit within TOL% of that low
    S  shelf_span           first-to-last distance between those touches
    E  above_shelf_pct      how far the last close has left the shelf

This is a TIGHTENING and nothing else: it is an EXTRA condition ANDed onto the
existing phone gates (direction_gate, room_gate, demand_proximity_gate,
is_falling_knife, mood). It can only remove pushes, never add one.

ALL CONSTANTS ARE CONFIGURED HOUSE VALUES chosen to be swept, not asserted.
Not a book method, not advice.

NO LOOKAHEAD. `evaluate(frame, asof)` slices to bars strictly BEFORE `asof`, so
the morning-of-D read never sees D's own still-forming bar.
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

# ── Constants (house values; every one has a sweep range in report()) ────────
SHELF_WINDOW_BARS      = 20     # K   the shelf lookback, closed sessions
SHELF_TOL_PCT          = 3.0    # TOL a low within this % of the base is "at the shelf"
MIN_LOWS_AT_SHELF      = 4      # C   how many of the K lows must be at it
MIN_SHELF_SPAN_BARS    = 8      # S   first-to-last spread of those touches
MIN_BARS_SINCE_NEW_LOW = 5      # B   the base must be at least this old
MAX_ABOVE_SHELF_PCT    = 8.0    # E   the close must still be ON the shelf
MIN_BARS_SINCE_BREAK   = 5      # F   sessions since a low cut UNDER the shelf floor
# The shelf level. "band" anchors the shelf on the demand band the alert is
# about; "window_min" falls back to the window's own lowest low when no band is
# supplied. MEASURED (report() below, n=6): band-anchored separates the sample
# 3/3 winners TRUE vs 2/2 losers FALSE; window_min rejects HOOD and OLLI, both
# winners, because their 20-session minimum sat 15% / 4% BELOW the band that was
# actually being bought. n=6 is an anecdote, not a rate.
SHELF_ANCHOR           = "band"

SWEEPS = {
    "SHELF_WINDOW_BARS":      [10, 15, 20, 25, 30, 40],
    "SHELF_TOL_PCT":          [1.0, 1.5, 2.0, 3.0, 4.0, 5.0],
    "MIN_LOWS_AT_SHELF":      [2, 3, 4, 5, 6, 8],
    "MIN_SHELF_SPAN_BARS":    [3, 5, 8, 10, 12],
    "MIN_BARS_SINCE_NEW_LOW": [2, 3, 5, 8, 10, 13],
    "MAX_ABOVE_SHELF_PCT":    [4.0, 6.0, 8.0, 10.0, 15.0],
    "MIN_BARS_SINCE_BREAK":   [0, 3, 5, 8, 10],
    "SHELF_ANCHOR":           ["band", "window_min"],
}


def stationary_bottom(lows, closes, band=None,
                      window: int = SHELF_WINDOW_BARS,
                      tol_pct: float = SHELF_TOL_PCT,
                      min_at_shelf: int = MIN_LOWS_AT_SHELF,
                      min_span: int = MIN_SHELF_SPAN_BARS,
                      min_bars_since_low: int = MIN_BARS_SINCE_NEW_LOW,
                      max_above_pct: float = MAX_ABOVE_SHELF_PCT,
                      min_bars_since_break: int = MIN_BARS_SINCE_BREAK,
                      anchor: str = SHELF_ANCHOR) -> dict:
    """PURE. Has price gone FLAT at its own lows? Closed daily bars only.

    `lows` / `closes` ascending, last element = the most recently CLOSED
    session. `band` = {"lo","hi"} of the demand band the alert is about; when
    it is None (or anchor="window_min") the shelf is anchored on the window's
    own lowest low instead. Fails closed on short history or NaN.
    """
    out = {"ok": False, "reason": None, "shelf_lo": None, "shelf_hi": None,
           "window_min": None, "bars_since_new_low": None, "lows_at_shelf": None,
           "shelf_span": None, "above_shelf_pct": None, "bars_since_break": None,
           "anchor": anchor}
    lows = [float(x) for x in lows]
    closes = [float(x) for x in closes]
    K = int(window)
    if len(lows) < K or len(closes) < 1 or K < 3:
        out["reason"] = "history"                       # fail closed
        return out
    w = lows[-K:]
    if not all(np.isfinite(w)) or not np.isfinite(closes[-1]):
        out["reason"] = "nan"
        return out
    wmin = min(w)
    if wmin <= 0:
        out["reason"] = "bad_price"
        return out

    # ── B: sessions since the window printed a NEW low. Always the window min:
    # "it stopped going down" is a statement about price, not about the band.
    # LAST occurrence of the minimum = the most recent new low.
    i_min = max(i for i, v in enumerate(w) if v == wmin)
    bars_since = (K - 1) - i_min

    # ── the shelf itself
    use_band = (anchor == "band" and isinstance(band, dict)
                and band.get("lo") and band.get("hi")
                and 0 < float(band["lo"]) <= float(band["hi"]))
    if use_band:
        s_lo, s_hi = float(band["lo"]), float(band["hi"])
    else:
        s_lo = s_hi = wmin
    floor_ = s_lo * (1.0 - float(tol_pct) / 100.0)
    top_ = s_hi * (1.0 + float(tol_pct) / 100.0)

    at = [i for i, v in enumerate(w) if floor_ <= v <= top_]
    n_at = len(at)
    span = (at[-1] - at[0] + 1) if at else 0
    broke = [i for i, v in enumerate(w) if v < floor_]
    bars_since_break = ((K - 1) - max(broke)) if broke else K
    above = (closes[-1] / s_hi - 1.0) * 100.0

    out.update({"shelf_lo": round(s_lo, 4), "shelf_hi": round(top_, 4),
                "window_min": round(wmin, 4), "bars_since_new_low": int(bars_since),
                "lows_at_shelf": int(n_at), "shelf_span": int(span),
                "bars_since_break": int(bars_since_break),
                "above_shelf_pct": round(above, 2), "anchor": "band" if use_band else "window_min"})

    fails = []
    if bars_since < min_bars_since_low:
        fails.append("new_low_%dd_ago<%d" % (bars_since, min_bars_since_low))
    if n_at < min_at_shelf:
        fails.append("touches_%d<%d" % (n_at, min_at_shelf))
    if span < min_span:
        fails.append("span_%d<%d" % (span, min_span))
    if bars_since_break < min_bars_since_break:
        fails.append("cut_under_%dd_ago<%d" % (bars_since_break, min_bars_since_break))
    if above > max_above_pct:
        fails.append("above_%.1f%%>%.1f%%" % (above, max_above_pct))
    out["ok"] = not fails
    out["reason"] = "based" if not fails else " + ".join(fails)
    return out


# ── plumbing ────────────────────────────────────────────────────────────────
def _frame(sym: str):
    from sepa import prices
    f = prices.load_prices(sym)                 # NOTE: ignores period, ~501 bars
    if f is None or len(f) == 0:
        return None
    f = f.copy()
    f.columns = [str(c).lower() for c in f.columns]
    if "date" in f.columns:
        f["d"] = f["date"].astype(str).str[:10]
    else:
        f["d"] = pd.Series(f.index).astype(str).str[:10].values
    for c in ("open", "high", "low", "close", "volume"):
        if c in f.columns:
            f[c] = pd.to_numeric(f[c], errors="coerce")
    return f.dropna(subset=["low", "close"]).sort_values("d").reset_index(drop=True)


def evaluate(f, asof: str, band=None, include_asof: bool = False, **kw) -> dict:
    """The read a phone gate would make on the morning of `asof`: CLOSED bars
    only, i.e. bars strictly BEFORE `asof` unless include_asof."""
    sub = f[f["d"] <= asof] if include_asof else f[f["d"] < asof]
    if len(sub) == 0:
        return {"ok": False, "reason": "no_bars"}
    r = stationary_bottom(sub["low"].tolist(), sub["close"].tolist(), band=band, **kw)
    r["last_closed_bar"] = sub["d"].iloc[-1]
    r["last_close"] = round(float(sub["close"].iloc[-1]), 2)
    r["n_bars"] = len(sub)
    return r


def other_gates(f, asof: str) -> dict:
    """What the gates that ALREADY exist say, for contrast."""
    from supply_demand import sd_liquidity, mood as mood_mod
    sub = f[f["d"] < asof]
    if len(sub) < 60:
        return {}
    closes, lows = sub["close"].tolist(), sub["low"].tolist()
    st = sd_liquidity.structure_read(closes, lows)
    ma = sub["close"].rolling(50).mean()
    knife = sd_liquidity.is_falling_knife(st, closes[-1], float(ma.iloc[-1]),
                                          float(ma.iloc[-2]))
    try:
        m = mood_mod.mood(sub)
        mood = "%s %s" % (round(float(m.get("score")), 1), m.get("label"))
    except Exception as exc:                                       # noqa: BLE001
        mood = "err:%s" % exc
    return {"structure_trend": st.get("trend"), "swing_lows": st.get("swing_lows"),
            "ma50": round(float(ma.iloc[-1]), 2), "ma50_prior": round(float(ma.iloc[-2]), 2),
            "is_falling_knife": bool(knife), "mood": mood}


# (symbol, asof, demand band the alert was about, what it was)
# Bands: CASY from the 08:13 ET push text; the rest are demand_episodes.zone_lo/hi.
CASES = [
    ("CASY", "2026-09-09", {"lo": 627.49, "hi": 651.00}, "THE FALLING KNIFE — must FAIL"),
    ("HOOD", "2026-08-18", {"lo": 92.80, "hi": 95.66},   "demand_episode target_first +9.9%"),
    ("OLLI", "2026-08-27", {"lo": 70.85, "hi": 73.61},   "demand_episode target_first +8.5%"),
    ("SYM",  "2026-08-31", {"lo": 38.19, "hi": 39.67},   "demand_episode target_first +12.5%"),
    ("KBH",  "2026-08-25", {"lo": 54.01, "hi": 56.02},   "demand_episode stop_first -6.5%"),
    ("GLXY", "2026-08-26", {"lo": 23.86, "hi": 24.62},   "demand_episode stop_first -6.3%"),
]


def report(symbols=None, sweep: bool = False):
    cases = [c for c in CASES if not symbols or c[0] in symbols]
    frames = {}
    print("=" * 78)
    print("STATIONARY BOTTOM (swing_structure lens)  K=%d TOL=%.1f%% "
          "touches>=%d span>=%d newlow>=%dd above<=%.1f%%"
          % (SHELF_WINDOW_BARS, SHELF_TOL_PCT, MIN_LOWS_AT_SHELF,
             MIN_SHELF_SPAN_BARS, MIN_BARS_SINCE_NEW_LOW, MAX_ABOVE_SHELF_PCT))
    print("=" * 78)
    for sym, asof, band, note in cases:
        f = frames.get(sym) or _frame(sym)
        frames[sym] = f
        if f is None:
            print("%-6s %s  NO DATA" % (sym, asof))
            continue
        r = evaluate(f, asof, band=band)
        g = other_gates(f, asof)
        print("\n%-5s  asof %s   (%s)" % (sym, asof, note))
        print("  last CLOSED bar %s  close %s   bars=%d"
              % (r.get("last_closed_bar"), r.get("last_close"), r.get("n_bars", 0)))
        print("  anchor=%-10s shelf %s .. %s   window_min %s"
              % (r.get("anchor"), r.get("shelf_lo"), r.get("shelf_hi"), r.get("window_min")))
        print("  B new_low %-3sd ago   C touches %-3s   S span %-3s   "
              "F cut_under %-3sd ago   E above %+.2f%%"
              % (r.get("bars_since_new_low"), r.get("lows_at_shelf"),
                 r.get("shelf_span"), r.get("bars_since_break"),
                 r.get("above_shelf_pct") or 0.0))
        print("  >>> STATIONARY BOTTOM = %-5s   (%s)" % (r["ok"], r["reason"]))
        if g:
            print("  existing gates: structure=%s knife=%s mood=%s  swing_lows=%s"
                  % (g["structure_trend"], g["is_falling_knife"], g["mood"],
                     g["swing_lows"]))
        # CASY also with its own gap bar included — must fail both ways.
        if sym == "CASY":
            r2 = evaluate(f, asof, band=band, include_asof=True)
            print("  [with the %s bar itself included] ok=%s (%s) B=%s C=%s S=%s"
                  % (asof, r2["ok"], r2["reason"], r2.get("bars_since_new_low"),
                     r2.get("lows_at_shelf"), r2.get("shelf_span")))

    if not sweep:
        return
    print("\n" + "=" * 78)
    print("CONSTANT SWEEP — one constant moved at a time, others at house value")
    print("=" * 78)
    base_kw = dict(window=SHELF_WINDOW_BARS, tol_pct=SHELF_TOL_PCT,
                   min_at_shelf=MIN_LOWS_AT_SHELF, min_span=MIN_SHELF_SPAN_BARS,
                   min_bars_since_low=MIN_BARS_SINCE_NEW_LOW,
                   max_above_pct=MAX_ABOVE_SHELF_PCT,
                   min_bars_since_break=MIN_BARS_SINCE_BREAK, anchor=SHELF_ANCHOR)
    argname = {"SHELF_WINDOW_BARS": "window", "SHELF_TOL_PCT": "tol_pct",
               "MIN_LOWS_AT_SHELF": "min_at_shelf", "MIN_SHELF_SPAN_BARS": "min_span",
               "MIN_BARS_SINCE_NEW_LOW": "min_bars_since_low",
               "MAX_ABOVE_SHELF_PCT": "max_above_pct",
               "MIN_BARS_SINCE_BREAK": "min_bars_since_break",
               "SHELF_ANCHOR": "anchor"}
    for const, vals in SWEEPS.items():
        print("\n%s" % const)
        for v in vals:
            kw = dict(base_kw)
            kw[argname[const]] = v
            line = []
            for sym, asof, band, _n in cases:
                f = frames.get(sym)
                if f is None:
                    continue
                line.append("%s=%s" % (sym, "T" if evaluate(f, asof, band=band, **kw)["ok"] else "."))
            print("   %-6s  %s" % (v, "  ".join(line)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="")
    ap.add_argument("--sweep", action="store_true")
    a = ap.parse_args()
    syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    report(syms or None, sweep=a.sweep)
