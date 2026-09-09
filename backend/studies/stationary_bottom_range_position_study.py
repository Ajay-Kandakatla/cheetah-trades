"""'Stationary bottomed', read through WHERE PRICE SITS IN ITS OWN RECENT RANGE.

    docker cp studies/stationary_bottom_range_position_study.py \
        cheetah-market-app-api-1:/tmp/sb.py
    docker exec cheetah-market-app-api-1 sh -c \
        'cd /app && PYTHONPATH=/app python -u /tmp/sb.py'
    ... --sweeps        every constant swept
    ... --casy          just the acceptance test

WHY THIS FILE EXISTS
--------------------
Ajay 2026-09-09, after being knifed on CASY: "I need only bullish reversal
stocks that touched demand zone and bouncing back... After a stationary
bottommed stocks as I caught a fallig knife today with Casy".

`alert_gates.direction_gate` already requires the bounce. `sd_liquidity.
is_falling_knife` is a NEGATIVE (nothing proves it is still falling).
"Stationary bottomed" is the missing POSITIVE: evidence the decline actually
STOPPED before the bounce. This file defines one candidate for it and measures
it. Rule "ship the backtest with the claim" — the claim here is a NULL, and a
bad one, so the number ships louder than the rule.

THE LENS (neutral price structure — no book, no trend template, no stage)
------------------------------------------------------------------------
While a name is falling, every close finishes near the BOTTOM of its own
trailing range, because each new bar drags the range's floor down with it. The
close-position-in-trailing-range is pinned near 0 by construction. Once the
decline stops, two things change together and neither one alone is enough:

  * closes start finishing in the UPPER part of the trailing range, and
  * the trailing range's LOW stops migrating down.

A name can have (1) without (2) — a dead-cat bounce inside a slide. It can have
(2) without (1) — a flat range whose closes still hug the floor, i.e. still
distributing. "Stationary bottomed" requires both, plus that the LAST closed
bar did not itself finish on the floor.

DEFINITIONS (all on CLOSED daily bars — today's forming bar never enters)
    RH_t = max(high[t-N+1..t])      RL_t = min(low[t-N+1..t])
    rp_t = (close_t - RL_t) / (RH_t - RL_t)          in [0, 1]
    ATR  = simple mean of true range over ATR_LEN bars

    A  PERCH   mean(rp over the last K bars)      >= RP_MEAN_MIN
    B  FLOOR   (RL_t - RL_{t-N}) / ATR_t          >= -FLOOR_DRIFT_MAX_ATR
    C  LAST    rp_t                               >= LAST_BAR_MIN_RP
    D  NEWLOW  bars since the 2N-window's lowest low >= MIN_BARS_SINCE_LOW
    E  WIDTH   (RH_t - RL_t) / ATR_t              <= BASE_MAX_WIDTH_ATR

B and E are ATR-normalised on purpose: the first draft used percent, and a 1%
floor-drift line that is nothing for a $12 uranium name is three ATR for CASY.
Percent made the rule near-constant-False on the winners.

NO LOOKAHEAD. Every read is on `df[df.date < event_date]`. Rolling windows use
min_periods=N and are computed BEFORE any dropna — the hot_pullback off-by-49
came from the other order.

WINDOW REACHABILITY. This needs 2N+5 = 25 closed bars. sepa.prices.load_prices
ignores its `period` and returns ~501 bars, so unlike a 252-bar gate every
event in the sample is reachable. That is the one thing this definition has
going for it.

WHAT THE MEASUREMENT SAYS (2026-09-09, cohort `demand_episodes`)
---------------------------------------------------------------
It rejects CASY on 2026-09-09 on four of five clauses. It also FAILS as a gate:
passers took MORE drawdown than the placebo, not less (+8.2pp on
P(5-session drawdown <= -5%), 95% CI [+3.8, +12.7], P(delta<0)=0.001). Every
clause pointed the same way. Do not ship this as a phone gate on these numbers.
See `report()` for the mechanism (arriving at demand perched high in the range
means the discount has NOT happened yet).

Configured house heuristic, S/D scope. Not a book method. Not advice.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from sepa import prices
from supply_demand import sd_liquidity as SL

# ── Owner constants. Every one is swept by --sweeps; none is a book number. ──
RANGE_N             = 10     # trailing range window            sweep 5..20
PERCH_K             = 10     # bars the perch is read over       sweep 5..20
RP_MEAN_MIN         = 0.40   # mean close-position in the range  sweep 0.25..0.55
FLOOR_DRIFT_MAX_ATR = 1.5    # allowed slip of the trailing low  sweep 0.5..3.0
LAST_BAR_MIN_RP     = 0.20   # last closed bar off its floor     sweep 0.0..0.50
MIN_BARS_SINCE_LOW  = 1      # yesterday must not BE the 2N low  sweep 0..5
BASE_MAX_WIDTH_ATR  = 6.0    # containment of the trailing range sweep 4..99
ATR_LEN             = 14     # true-range window                 sweep 10..20
COHORT_MDD_SESSIONS = 5      # forward window the tail is read over
BOOTSTRAP_DRAWS     = 4_000


def stationary_bottom(df, N=RANGE_N, K=PERCH_K, rp_mean_min=RP_MEAN_MIN,
                      drift_atr=FLOOR_DRIFT_MAX_ATR, last_rp_min=LAST_BAR_MIN_RP,
                      min_since_low=MIN_BARS_SINCE_LOW,
                      width_max=BASE_MAX_WIDTH_ATR, atr_len=ATR_LEN) -> dict:
    """PURE. `df` is CLOSED daily OHLCV ascending. Fails closed on thin data."""
    out = {"ok": False, "why": "insufficient bars"}
    need = max(2 * N + 5, atr_len + 1, K + N)
    if df is None or len(df) < need:
        out["bars"] = 0 if df is None else len(df)
        return out
    h, l, c = df["high"].astype(float), df["low"].astype(float), df["close"].astype(float)
    RH = h.rolling(N, min_periods=N).max()
    RL = l.rolling(N, min_periods=N).min()
    rng = RH - RL
    rp = (c - RL) / rng.where(rng > 0)                  # NaN when the range is flat
    prev_c = c.shift(1)
    tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    atr = tr.rolling(atr_len, min_periods=atr_len).mean()

    tail = rp.iloc[-K:]
    if tail.isna().any() or not np.isfinite(atr.iloc[-1]) or atr.iloc[-1] <= 0:
        out["bars"] = len(df)
        return out
    a = float(atr.iloc[-1])
    rp_mean = float(tail.mean())
    rl_now, rl_prior = float(RL.iloc[-1]), float(RL.iloc[-1 - N])
    drift = (rl_now - rl_prior) / a
    width = (float(RH.iloc[-1]) - rl_now) / a
    last_rp = float(rp.iloc[-1])
    w2 = l.iloc[-2 * N:].values
    since_low = int(len(w2) - 1 - int(np.argmin(w2)))

    out.update({"rp_mean": round(rp_mean, 3),
                "rp_frac_upper": round(float((tail >= 0.5).mean()), 2),
                "last_rp": round(last_rp, 3), "rl_now": round(rl_now, 2),
                "rl_prior": round(rl_prior, 2), "floor_drift_atr": round(drift, 2),
                "floor_drift_pct": round((rl_now / rl_prior - 1) * 100, 2),
                "atr": round(a, 2), "width_atr": round(width, 2),
                "bars_since_low": since_low,
                "rp_slope": round(float(np.polyfit(np.arange(K), tail.values, 1)[0]), 4),
                "rp_tail": [round(float(v), 2) for v in tail],
                "asof": str(df.index[-1])[:10], "bars": len(df)})
    fails = []
    if rp_mean < rp_mean_min:          fails.append(f"perch {rp_mean:.2f}<{rp_mean_min}")
    if drift < -drift_atr:             fails.append(f"floor slipped {drift:.2f}ATR<-{drift_atr}")
    if last_rp < last_rp_min:          fails.append(f"last_rp {last_rp:.2f}<{last_rp_min}")
    if since_low < min_since_low:      fails.append(f"new low yday ({since_low}<{min_since_low})")
    if width > width_max:              fails.append(f"width {width:.2f}ATR>{width_max}")
    out["ok"] = not fails
    out["why"] = "PASS" if not fails else " | ".join(fails)
    return out


def closed_before(df, date: str):
    """Bars strictly BEFORE `date` — the frame a pre-open alert may legally see."""
    return df[df.index.astype(str).str[:10] < date]


def knife(df):
    """sd_liquidity.is_falling_knife on the same closed frame, for the cross-tab."""
    if df is None or len(df) < 60:
        return None
    c, l = df["close"].astype(float), df["low"].astype(float)
    st = SL.structure_read(list(c), list(l))
    ma = c.rolling(50, min_periods=50).mean()
    return SL.is_falling_knife(st, float(c.iloc[-1]), float(ma.iloc[-1]), float(ma.iloc[-2]))


# ── acceptance test ─────────────────────────────────────────────────────────
def show(tag: str, df, date: str, **kw) -> dict:
    r = stationary_bottom(closed_before(df, date), **kw)
    print(f"\n=== {tag}   closed bars < {date}  (asof {r.get('asof')}, n={r.get('bars')})")
    for k in ("rp_mean", "rp_frac_upper", "last_rp", "rl_now", "rl_prior",
              "floor_drift_atr", "floor_drift_pct", "atr", "width_atr",
              "bars_since_low", "rp_slope"):
        print(f"    {k:<17} {r.get(k)}")
    print(f"    rp_tail           {r.get('rp_tail')}")
    print(f"    ---> stationary_bottomed = {r['ok']}   [{r['why']}]")
    return r


def casy_acceptance():
    d = prices.load_prices("CASY")
    show("CASY  <-- the 2026-09-09 08:13 ET alert fired here", d, "2026-09-09")
    show("CASY  one day on (the -13% earnings bar closed)", d, "2026-09-10")


# ── cohort ──────────────────────────────────────────────────────────────────
def cohort(**kw) -> pd.DataFrame:
    coll = prices._get_mongo()
    eps = list(coll.database.demand_episodes.find(
        {}, {"symbol": 1, "first_seen": 1, "outcome": 1, "net_pct": 1, "_id": 0}))
    frames, rows = {}, []
    for e in eps:
        s = e["symbol"]
        if s not in frames:
            frames[s] = prices.load_prices(s)
        d = frames[s]
        if d is None:
            continue
        prior = closed_before(d, e["first_seen"])
        r = stationary_bottom(prior, **kw)
        if r.get("rp_mean") is None:
            continue
        fwd = d[d.index.astype(str).str[:10] >= e["first_seen"]]
        if len(fwd) <= COHORT_MDD_SESSIONS:
            continue
        entry = float(fwd["open"].iloc[0])
        if entry <= 0:
            continue
        rows.append({
            "symbol": s, "date": e["first_seen"], "outcome": e.get("outcome"),
            "net_pct": e.get("net_pct"), "pass": r["ok"], "rp_mean": r["rp_mean"],
            "last_rp": r["last_rp"], "drift": r["floor_drift_atr"],
            "since_low": r["bars_since_low"], "width": r["width_atr"],
            "knife": knife(prior),
            "mdd5": (float(fwd["low"].iloc[:COHORT_MDD_SESSIONS].min()) / entry - 1) * 100,
            "f5": (float(fwd["close"].iloc[COHORT_MDD_SESSIONS - 1]) / entry - 1) * 100,
        })
    return pd.DataFrame(rows)


def _line(tag, S, ALL):
    if not len(S):
        print(f"  {tag:<28} n=0"); return
    print(f"  {tag:<28} n={len(S):4d} ({len(S)/len(ALL)*100:5.1f}%)  "
          f"mdd{COHORT_MDD_SESSIONS} med {S.mdd5.median():+6.2f}%  "
          f"p10 {np.percentile(S.mdd5, 10):+7.2f}%  "
          f"P(<=-5%) {(S.mdd5 <= -5).mean()*100:5.1f}%  "
          f"P(<=-10%) {(S.mdd5 <= -10).mean()*100:5.1f}%  "
          f"f{COHORT_MDD_SESSIONS} {S.f5.mean():+6.2f}%")


def report(R: pd.DataFrame):
    print(f"\ncohort n={len(R)}  names={R.symbol.nunique()}  "
          f"dates {R.date.min()} -> {R.date.max()} ({R.date.nunique()} sessions)")
    print("\nENTERED AT THE NEXT OPEN. PLACEBO = every episode, ungated.")
    _line("PLACEBO all episodes", R, R)
    _line("stationary_bottomed", R[R["pass"]], R)
    _line("NOT stationary", R[~R["pass"]], R)
    K = R[R.knife.notna()]
    if len(K):
        print()
        _line("knife guard passes", K[~K.knife.astype(bool)], K)
        _line("knife guard rejects", K[K.knife.astype(bool)], K)
        print()
        _line("knife-OK AND stationary", K[(~K.knife.astype(bool)) & K["pass"]], K)
        _line("knife-OK NOT stationary", K[(~K.knife.astype(bool)) & (~K["pass"])], K)

    res = R[R.outcome.isin(["target_first", "stop_first"])]
    if len(res):
        b = (res.outcome == "target_first").mean() * 100
        p = res[res["pass"]]
        print(f"\n  bracket outcome   PLACEBO target_first {b:.1f}% (n={len(res)})   "
              f"passers {(p.outcome == 'target_first').mean()*100:.1f}% (n={len(p)})")

    print(f"\n  each clause ALONE on the full cohort (does any one cut the tail?):")
    for lab, m in [("perch>=0.40", R.rp_mean >= 0.40), ("perch>=0.50", R.rp_mean >= 0.50),
                   ("last_rp>=0.20", R.last_rp >= 0.20), ("drift>=-1.5ATR", R.drift >= -1.5),
                   ("drift>=-1.0ATR", R.drift >= -1.0), ("since_low>=1", R.since_low >= 1),
                   ("since_low>=3", R.since_low >= 3)]:
        S = R[m]
        print(f"    {lab:<16} keeps {len(S):4d} ({len(S)/len(R)*100:5.1f}%)  "
              f"P(<=-5%) {(S.mdd5 <= -5).mean()*100:5.1f}%  "
              f"P(<=-10%) {(S.mdd5 <= -10).mean()*100:5.1f}%  f5 {S.f5.mean():+.2f}%")

    # Bootstrap over DATES: episodes cluster on market-wide days.
    rng = np.random.default_rng(7)
    days = R.date.unique()
    by = {d: R[R.date == d] for d in days}
    dr = np.empty(BOOTSTRAP_DRAWS)
    for i in range(BOOTSTRAP_DRAWS):
        S = pd.concat([by[d] for d in rng.choice(days, size=len(days), replace=True)])
        p = S[S["pass"]]
        dr[i] = ((p.mdd5 <= -5).mean() - (S.mdd5 <= -5).mean()) * 100 if len(p) else np.nan
    dr = dr[np.isfinite(dr)]
    print(f"\n  BOOTSTRAP by date, delta in P(mdd<=-5%) passers vs cohort:")
    print(f"    {dr.mean():+.2f}pp   95% CI [{np.percentile(dr, 2.5):+.2f}, "
          f"{np.percentile(dr, 97.5):+.2f}]   P(delta<0)={float((dr < 0).mean()):.3f}")
    print("    NEGATIVE delta would mean the gate helps. It does not.")


def sweeps():
    grid = {"rp_mean_min": [0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55],
            "drift_atr": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0],
            "last_rp_min": [0.0, 0.10, 0.20, 0.30, 0.40, 0.50],
            "min_since_low": [0, 1, 2, 3, 5],
            "width_max": [4.0, 5.0, 6.0, 8.0, 99.0],
            "N": [5, 8, 10, 15, 20], "K": [5, 10, 15, 20],
            "atr_len": [10, 14, 20]}
    for k, vals in grid.items():
        print(f"\n  -- {k}")
        for v in vals:
            R = cohort(**{k: v})
            if R.empty:
                print(f"     {v:<6} no events"); continue
            P = R[R["pass"]]
            if not len(P):
                print(f"     {v:<6} pass 0"); continue
            print(f"     {v:<6} pass {len(P):4d} ({len(P)/len(R)*100:5.1f}%)  "
                  f"P(mdd<=-5%) {(P.mdd5 <= -5).mean()*100:5.1f}% "
                  f"(cohort {(R.mdd5 <= -5).mean()*100:5.1f}%)  f5 {P.f5.mean():+.2f}%")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--casy", action="store_true", help="acceptance test only")
    ap.add_argument("--sweeps", action="store_true", help="sweep every constant")
    a = ap.parse_args()
    casy_acceptance()
    if not a.casy:
        report(cohort())
    if a.sweeps:
        sweeps()
