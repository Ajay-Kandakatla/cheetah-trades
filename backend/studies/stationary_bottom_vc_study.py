"""STATIONARY BOTTOM — the volatility-contraction reading. Re-runnable.

    docker cp studies/stationary_bottom_vc_study.py cheetah-market-app-api-1:/tmp/sb.py
    docker exec cheetah-market-app-api-1 sh -c 'cd /app && PYTHONPATH=/app python -u /tmp/sb.py'

WHY THIS FILE EXISTS
────────────────────
Ajay 2026-09-09, after buying CASY into an earnings gap: "I need only bullish
reversal stocks that touched demand zone and bouncing back ... After a
stationary bottommed stocks as I caught a fallig knife today with Casy".

`alert_gates.direction_gate` already answers "is it turning UP right now" and
`sd_liquidity.is_falling_knife` answers "are the swing lows stepping down".
Neither answers "has it STOPPED FALLING" — a name can print one bouncing bar
in the middle of an accelerating slide. This file defines that fourth
condition through RANGE and DRIFT, and measures it.

THE READING, in neutral price-structure terms (no book, no SEPA/Minervini)
─────────────────────────────────────────────────────────────────────────
Sellers who are still hitting bids leave two marks on a daily bar chart:
the bars get WIDER (each session covers more ground), and the closes keep
NETTING lower. A supply that has been used up leaves the opposite: the daily
true range compresses against what it was during the slide, and the net change
across the recent window flattens toward zero, at a price near the low of that
slide. That is all "stationary bottomed" is asked to mean here — a measurable
loss of downside range and drift, not a forecast.

Everything below is measured on CLOSED daily bars only. The still-forming bar
never enters a window (`upto()` slices STRICTLY BEFORE the decision date).

TRAPS THIS FILE AVOIDS (each has burned a number in this repo)
──────────────────────────────────────────────────────────────
* `sepa.prices.load_prices` ignores `period` and returns ~501 bars. This rule
  needs 31, so it is reachable across the whole cache; it is stated, not assumed.
* No `dropna()` before a rolling window. True range is computed on the RAW
  frame and only then sliced by position, so window k is bars k..k+n, never
  k+warmup (the off-by-49 that made hot_pullback read +0.27R instead of +0.10R).
* Every rate ships its placebo (the same cohort's base rate) and a bootstrap CI.
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from sepa import prices

# ── Constants. Every one of them is swept in `sweep()`; none is a book value ──
BASE_LEN = 10            # closed bars that must look stationary          sweep 5..20
DECLINE_LEN = 20         # closed bars BEFORE the base = the slide        sweep 10..40
CONTRACTION_MAX = 0.75   # base mean TR% / decline mean TR%               sweep 0.50..1.00
DRIFT_MAX_ATR = 1.0      # |net % across the base| in base-ATR% units     sweep 0.5..2.0
EXPANSION_MAX_X = 1.0    # widest base TR% / decline mean TR%             sweep 0.8..1.5
LOW_PROX_ATR = 1.0       # base low above the window low, in base ATR%    sweep 0.5..3.0
HALF_STEP_MAX = 1.10     # 2nd half of base TR% / 1st half               sweep 1.0..1.5 (inf = off)

MIN_BARS = DECLINE_LEN + BASE_LEN + 1


def tr_pct(df: pd.DataFrame) -> np.ndarray:
    """Per-bar true range as a percent of the PRIOR close. Percent, not dollars:
    a name that fell 40% would show a shrinking dollar range from the price
    level alone. Computed on the raw frame — no dropna before any window."""
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    pc = np.empty_like(c)
    pc[0] = c[0]
    pc[1:] = c[:-1]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return np.where(pc > 0, tr / pc * 100.0, np.nan)


def range_settled(df, base_len=BASE_LEN, dec_len=DECLINE_LEN,
                  contraction_max=CONTRACTION_MAX, drift_max_atr=DRIFT_MAX_ATR,
                  expansion_max_x=EXPANSION_MAX_X, low_prox_atr=LOW_PROX_ATR,
                  half_step_max=HALF_STEP_MAX) -> dict:
    """Has the daily range compressed and the drift flattened, at the low?

    `df` = CLOSED daily bars, ascending, ending on the last completed session.
    Returns the five sub-reads plus `settled`. Unknown = NOT settled: too little
    history fails closed, the same side `direction_gate` fails on."""
    out = {"settled": False, "reason": "history", "checks": {}}
    if df is None or len(df) < MIN_BARS or not {"high", "low", "close"} <= set(df.columns):
        return out
    n = len(df)
    b0 = n - base_len                       # first bar of the base
    d0 = n - base_len - dec_len             # first bar of the decline window
    if d0 < 1:
        return out
    t = tr_pct(df)
    c = df["close"].values.astype(float)
    lo = df["low"].values.astype(float)
    atrp_base = float(np.nanmean(t[b0:n]))
    atrp_dec = float(np.nanmean(t[d0:b0]))
    if not (atrp_base > 0 and atrp_dec > 0):
        out["reason"] = "flat"
        return out

    contraction = atrp_base / atrp_dec                    # <1 = range compressing
    anchor = float(c[b0 - 1])                             # close before the base
    drift_pct = (float(c[n - 1]) / anchor - 1.0) * 100.0
    drift_atr = abs(drift_pct) / atrp_base                # flat in its OWN units
    expansion = float(np.nanmax(t[b0:n])) / atrp_dec      # no single wide bar
    win_low = float(np.nanmin(lo[d0:n]))
    base_low = float(np.nanmin(lo[b0:n]))
    lowprox = ((base_low / win_low) - 1.0) * 100.0 / atrp_base if win_low > 0 else np.inf
    half = base_len // 2
    h1 = float(np.nanmean(t[b0:b0 + half]))
    h2 = float(np.nanmean(t[n - half:n]))
    half_step = h2 / h1 if h1 > 0 else np.inf

    checks = {
        "contraction": contraction <= contraction_max,   # range died vs the slide
        "drift": drift_atr <= drift_max_atr,             # net change ~ flat
        "expansion": expansion <= expansion_max_x,       # no wide bar in the base
        "low_prox": lowprox <= low_prox_atr,             # the base IS the bottom
        "half_step": half_step <= half_step_max,         # still compressing, not re-opening
    }
    out.update({
        "settled": all(checks.values()), "checks": checks,
        "atrp_base": round(atrp_base, 3), "atrp_dec": round(atrp_dec, 3),
        "contraction": round(contraction, 3), "drift_pct": round(drift_pct, 2),
        "drift_atr": round(drift_atr, 3), "expansion": round(expansion, 3),
        "low_prox_atr": round(lowprox, 3), "half_step": round(half_step, 3),
        "reason": None if all(checks.values()) else ",".join(k for k, v in checks.items() if not v),
    })
    return out


def upto(df, date_str: str):
    """CLOSED bars only: everything STRICTLY BEFORE `date_str`."""
    if df is None:
        return None
    d = df.index.astype(str).str[:10]
    return df[d < date_str]


# ── 1. the acceptance test ───────────────────────────────────────────────────
def casy(argv=None) -> bool:
    f = prices.load_prices("CASY")
    sub = upto(f, "2026-09-09")
    r = range_settled(sub)
    print("CASY  decision date 2026-09-09 (alert fired 08:13 ET)")
    print("  last CLOSED bar   %s  close %.2f" % (str(sub.index[-1])[:10], sub['close'].iloc[-1]))
    for k in ("atrp_dec", "atrp_base", "contraction", "drift_pct", "drift_atr",
              "expansion", "low_prox_atr", "half_step"):
        print("  %-14s %s" % (k, r[k]))
    print("  checks          ", r["checks"])
    print("  SETTLED         ", r["settled"], "  failed:", r["reason"])
    assert r["settled"] is False, "CASY must FAIL — it is the acceptance test"
    return r["settled"]


# ── 2. contrast names: it must not be a constant False ───────────────────────
def contrast(names) -> None:
    print("\nCONTRAST NAMES (rule evaluated on bars strictly before the date)")
    print("  %-6s %-11s %-8s %6s %7s %7s %7s %7s  %s"
          % ("sym", "date", "settled", "contr", "driftA", "expan", "lowprx", "half", "failed"))
    for sym, date in names:
        f = prices.load_prices(sym)
        r = range_settled(upto(f, date))
        print("  %-6s %-11s %-8s %6s %7s %7s %7s %7s  %s"
              % (sym, date, r["settled"], r.get("contraction"), r.get("drift_atr"),
                 r.get("expansion"), r.get("low_prox_atr"), r.get("half_step"),
                 r.get("reason") or "-"))


# ── 3. does it separate? episodes cross-tab, placebo beside every rate ───────
def episodes(limit: int = 0) -> pd.DataFrame:
    coll = prices._get_mongo().database["demand_episodes"]
    q = {"outcome": {"$in": ["target_first", "stop_first"]}}
    docs = list(coll.find(q, {"symbol": 1, "first_seen": 1, "outcome": 1, "_id": 0}))
    if limit:
        docs = docs[:limit]
    rows = []
    cache = {}
    for i, d in enumerate(docs):
        if i % 200 == 0:
            print("  %d/%d" % (i, len(docs)), file=sys.stderr, flush=True)
        sym = d.get("symbol")
        day = str(d.get("first_seen") or "")[:10]
        if not sym or len(day) != 10:
            continue
        if sym not in cache:
            cache[sym] = prices.load_prices(sym)
        r = range_settled(upto(cache[sym], day))
        if r.get("reason") == "history":
            continue
        # The knife guard on the SAME closed bars, so the two can be crossed.
        c = cache[sym]["close"] if cache[sym] is not None else None
        sub = upto(cache[sym], day)
        knife = None
        try:
            from supply_demand import sd_liquidity as SL
            ma = sub["close"].rolling(50).mean()
            st = SL.structure_read(sub["close"].values, sub["low"].values)
            knife = bool(SL.is_falling_knife(st, float(sub["close"].iloc[-1]),
                                             float(ma.iloc[-1]), float(ma.iloc[-2])))
        except Exception:                                        # noqa: BLE001
            knife = None
        rows.append({"symbol": sym, "date": day, "win": d["outcome"] == "target_first",
                     "settled": bool(r["settled"]), "knife": knife, **{k: r.get(k) for k in
                     ("contraction", "drift_atr", "expansion", "low_prox_atr", "half_step")}})
    E = pd.DataFrame(rows)
    if not E.empty:
        # One episode per (symbol, day): demand_episodes carries the same event
        # once per universe (sp500 / full / ...), which would triple-count names.
        E = E.drop_duplicates(subset=["symbol", "date"]).reset_index(drop=True)
    return E


def _boot_diff(a: np.ndarray, b: np.ndarray, draws: int = 20000) -> tuple:
    rng = np.random.default_rng(13)
    out = np.empty(draws)
    for i in range(draws):
        out[i] = rng.choice(a, len(a), True).mean() - rng.choice(b, len(b), True).mean()
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5)), float((out <= 0).mean())


def report(E: pd.DataFrame) -> None:
    if E.empty:
        print("no episodes")
        return
    base = E.win.mean() * 100
    print("\nDEMAND EPISODES  n=%d  names=%d  %s -> %s"
          % (len(E), E.symbol.nunique(), E.date.min(), E.date.max()))
    print("  PLACEBO (every episode)      %.1f%% reached target first" % base)
    for flag in (True, False):
        s = E[E.settled == flag]
        if len(s) < 10:
            print("  settled=%-5s n=%-4d too small" % (flag, len(s)))
            continue
        print("  settled=%-5s n=%-4d          %.1f%% target-first   (%+.1fpp vs placebo)"
              % (flag, len(s), s.win.mean() * 100, s.win.mean() * 100 - base))
    y = E[E.settled].win.values.astype(float)
    n_ = E[~E.settled].win.values.astype(float)
    if len(y) >= 10 and len(n_) >= 10:
        lo, hi, p = _boot_diff(y, n_)
        print("  95%% CI on the gap            %+.1fpp to %+.1fpp   P(gap<=0)=%.3f"
              % (lo * 100, hi * 100, p))
    print("\n  EACH CHECK ALONE (marginal keep rate + its own hit rate):")
    for k, lim in (("contraction", CONTRACTION_MAX), ("drift_atr", DRIFT_MAX_ATR),
                   ("expansion", EXPANSION_MAX_X), ("low_prox_atr", LOW_PROX_ATR),
                   ("half_step", HALF_STEP_MAX)):
        m = E[k].values <= lim
        if m.sum() >= 10:
            print("    %-13s alone keeps %5.1f%%  ->  %.1f%% target-first (%+.1fpp)"
                  % (k, m.mean() * 100, E[m].win.mean() * 100, E[m].win.mean() * 100 - base))
        else:
            print("    %-13s alone keeps %5.1f%%  (n=%d too small)" % (k, m.mean() * 100, int(m.sum())))
    print("  kept %.1f%% of episodes (a TIGHTENING: %d of %d would still push)"
          % (E.settled.mean() * 100, int(E.settled.sum()), len(E)))


def sweep(E: pd.DataFrame) -> None:
    """Sensitivity: one constant moved at a time, everything else at default."""
    print("\nSWEEP (recomputed per setting — see --sweep to run the full one)")
    print("  (uses the cached per-episode sub-reads: a constant only ever moves its own check)")
    base = E.win.mean() * 100
    grid = {"contraction": [0.50, 0.60, 0.75, 0.85, 1.00],
            "drift_atr": [0.5, 0.75, 1.0, 1.5, 2.0],
            "expansion": [0.8, 1.0, 1.2, 1.5],
            "low_prox_atr": [0.5, 1.0, 2.0, 3.0],
            "half_step": [1.0, 1.10, 1.25, 1.50, np.inf]}
    dflt = {"contraction": CONTRACTION_MAX, "drift_atr": DRIFT_MAX_ATR,
            "expansion": EXPANSION_MAX_X, "low_prox_atr": LOW_PROX_ATR,
            "half_step": HALF_STEP_MAX}
    for col, vals in grid.items():
        for v in vals:
            cut = dict(dflt); cut[col] = v
            m = np.ones(len(E), bool)
            for k, lim in cut.items():
                m &= E[k].values <= lim
            s = E[m]
            if len(s) < 10:
                print("    %-13s <= %-5s n=%-4d too small" % (col, v, len(s)))
                continue
            print("    %-13s <= %-5s n=%-4d  %.1f%% target-first  (%+.1fpp vs %.1f%% placebo)  keep %.0f%%"
                  % (col, v, len(s), s.win.mean() * 100, s.win.mean() * 100 - base, base,
                     m.mean() * 100))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", type=int, default=0)
    ap.add_argument("--contrast", default="")
    a = ap.parse_args()
    casy()
    contrast([("CASY", "2026-09-09"), ("KR", "2026-08-20"), ("JD", "2026-09-01"),
              ("WDC", "2026-09-03"), ("OHI", "2026-08-31"), ("TCBI", "2026-08-18"),
              ("EXR", "2026-08-25")])
    E = episodes(a.names)
    report(E)
    sweep(E)
    if "knife" in E.columns and E.knife.notna().any():
        print("\nVS THE KNIFE GUARD (sd_liquidity.is_falling_knife, same closed bars):")
        print(pd.crosstab(E.knife, E.settled, margins=True).to_string())
        nk = E[E.knife == False]                                  # noqa: E712
        print("  knife guard PASSES %d of %d episodes -> %.1f%% target-first"
              % (len(nk), len(E), nk.win.mean() * 100))
        print("  of those, range_settled REJECTS %d (%.1f%%) — the two are not redundant"
              % (int((~nk.settled).sum()), (~nk.settled).mean() * 100))
    print("\nWINNERS THE RULE KEPT (settled=True, target_first) — sample:")
    print(E[E.settled & E.win].head(15).to_string(index=False))
    print("\nLOSERS THE RULE KEPT (settled=True, stop_first) — sample:")
    print(E[E.settled & ~E.win].head(10).to_string(index=False))
