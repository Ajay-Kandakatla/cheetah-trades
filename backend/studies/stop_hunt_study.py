"""Stop hunt vs falling knife — does a swept-and-reclaimed demand band beat one
that simply broke?

Ajay 2026-09-09: "I am trying to find bullish stocks that got in to demand zone
for some reason in the short while where Institutions hunt for stop losses in
the journey I been catching some falling knives do what ever is best".

THE SETUP HE IS DESCRIBING IS NOT A BOTTOM. It is a strong name whose band gets
sliced through to take resting stops and then bought back. sd_liquidity.find_sweep
already names the three outcomes and has since 2026-08:

    swept    pierced the floor and CLOSED back above it   <- the setup
    broken   pierced and never reclaimed                  <- the falling knife
    intact   never pierced

This measures whether that distinction pays, on the replayed event table from
bounce_quality_study.py.

METHOD, and why it is stated this way
─────────────────────────────────────
* LEAD ON WIN RATE AND STOP-OUT RATE, not mean R. On this cohort the top 1% of
  events carry 86.6% of total R and the median R is -1.000 in EVERY arm. Mean R
  is a tail statistic here. Win and stop rates are binomials.
* Intervals resample WHOLE DATES (192 of them). Events cluster hard on dates;
  an i.i.d. interval is too narrow by construction — that error invalidated
  every "outside placebo" flag in the parent study.
* No lookahead. The sweep window ends at the EVENT BAR, whose low and close are
  both known at the decision point (the entry is that bar's close). Everything
  before it is history.
* `zone_hi` is passed as the event print purely to satisfy find_sweep's
  `zone_hi <= zone_lo` validation; it is not used in the sweep logic.

Re-run:
  docker cp studies/stop_hunt_study.py cheetah-market-app-api-1:/tmp/sh.py
  docker exec cheetah-market-app-api-1 sh -c \
    'cd /app && PYTHONPATH=/app python -u /tmp/sh.py --events /tmp/bq_events.csv'
"""
from __future__ import annotations

import argparse
import numpy as np
import pandas as pd

STOP_BUFFER_PCT = 0.5          # alert_gates.STOP_BUFFER_PCT — stop = floor * (1 - this)
SWEEP_WINDOW_BARS = 15         # bars of history the sweep may live in
BOOT_DRAWS = 1500


def _band_lo(stop: float) -> float:
    """The study's stop is the band floor minus STOP_BUFFER_PCT — invert it."""
    return float(stop) / (1.0 - STOP_BUFFER_PCT / 100.0)


def annotate(events: pd.DataFrame, window: int = SWEEP_WINDOW_BARS) -> pd.DataFrame:
    from sepa import prices
    from supply_demand import sd_liquidity as liq

    out = {"sweep_state": [], "pierce_pct": [], "vol_x": [], "reclaim_bars": [],
           "low_under_floor": []}
    frames: dict = {}
    for sym, date, stop, entry in zip(events["symbol"], events["date"],
                                      events["stop"], events["entry"]):
        if sym not in frames:
            try:
                frames[sym] = prices.load_prices(sym)
            except Exception:                                   # noqa: BLE001
                frames[sym] = None
        df = frames[sym]
        state, pierce, volx, recb, under = "unknown", np.nan, np.nan, np.nan, False
        if df is not None and len(df) > window + 2:
            key = pd.Timestamp(str(date)[:10])
            pos = df.index.normalize().get_indexer([key])[0]
            if pos >= window:
                floor_ = _band_lo(stop)
                # history + the event bar; nothing after it
                w = df.iloc[pos - window + 1:pos + 1]
                under = bool(float(w["low"].iloc[-1]) < floor_)
                sw = liq.find_sweep(w, floor_, max(float(entry), floor_ * 1.001))
                if sw.get("found"):
                    state = "swept"
                    pierce, volx = sw.get("pierce_pct"), sw.get("sweep_volume_x")
                    recb = sw.get("reclaim_bars")
                elif float(w["low"].min()) < floor_:
                    state = "broken"        # pierced somewhere, never reclaimed
                    pierce = (floor_ - float(w["low"].min())) / floor_ * 100.0
                else:
                    state = "intact"
        out["sweep_state"].append(state)
        out["pierce_pct"].append(pierce)
        out["vol_x"].append(volx)
        out["reclaim_bars"].append(recb)
        out["low_under_floor"].append(under)
    for k, v in out.items():
        events[k] = v
    return events


def _clustered(B: pd.DataFrame, mask: pd.Series, draws: int = BOOT_DRAWS, seed: int = 13):
    """Δ win-rate and Δ stop-rate (kept minus dropped), resampling whole DATES."""
    dates = B["date"].values
    uniq = np.unique(dates)
    idx = {d: np.flatnonzero(dates == d) for d in uniq}
    rng = np.random.default_rng(seed)
    mv = mask.values
    dw, ds = [], []
    for _ in range(draws):
        rows = np.concatenate([idx[d] for d in rng.choice(uniq, len(uniq), True)])
        s, m = B.iloc[rows], mv[rows]
        k, o = s[m], s[~m]
        if len(k) < 20 or len(o) < 20:
            continue
        dw.append(100.0 * (k["R"] > 0).mean() - 100.0 * (o["R"] > 0).mean())
        ds.append(100.0 * (k["why"] == "stop").mean() - 100.0 * (o["why"] == "stop").mean())
    if not dw:
        return None
    return (np.mean(dw), np.percentile(dw, [2.5, 97.5]),
            np.mean(ds), np.percentile(ds, [2.5, 97.5]))


def line(B: pd.DataFrame, label: str, mask: pd.Series) -> None:
    k, o = B[mask], B[~mask]
    if len(k) < 100 or len(o) < 100:
        print("  %-38s keep %5d — too few to say anything" % (label, len(k)))
        return
    c = _clustered(B, mask)
    tail = ""
    if c:
        star = "  <<<" if c[1][0] > 0 else ("  (worse)" if c[1][1] < 0 else "")
        tail = ("Δwin %+5.2fpp CI[%+5.2f,%+5.2f] | Δstop %+5.2fpp CI[%+5.2f,%+5.2f]%s"
                % (c[0], c[1][0], c[1][1], c[2], c[3][0], c[3][1], star))
    print("  %-38s keep %5d (%4.1f%%) | win %4.1f%% vs %4.1f%% | stop %4.1f%% vs %4.1f%% | %s"
          % (label, len(k), 100.0 * len(k) / len(B),
             100.0 * (k["R"] > 0).mean(), 100.0 * (o["R"] > 0).mean(),
             100.0 * (k["why"] == "stop").mean(), 100.0 * (o["why"] == "stop").mean(), tail))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default="/tmp/bq_events.csv")
    ap.add_argument("--out", default="/tmp/stop_hunt_events.csv")
    ap.add_argument("--annotated", default=None,
                    help="skip the replay and read an already-annotated CSV")
    a = ap.parse_args()

    if a.annotated:
        B = pd.read_csv(a.annotated)
    else:
        D = pd.read_csv(a.events)
        B = D[D["dir"] == "bouncing"].copy().reset_index(drop=True)
        print("annotating %d bouncing events across %d names ..." % (len(B), B.symbol.nunique()))
        B = annotate(B)
        B.to_csv(a.out, index=False)
        print("wrote", a.out)

    print()
    print("COHORT  n=%d  names=%d  dates=%d  %s -> %s"
          % (len(B), B.symbol.nunique(), B.date.nunique(), B.date.min(), B.date.max()))
    print("BASELINE  win %.1f%%  stop-out %.1f%%  median R %.3f  (mean R %.3f is TAIL-DOMINATED)"
          % (100.0 * (B["R"] > 0).mean(), 100.0 * (B["why"] == "stop").mean(),
             B["R"].median(), B["R"].mean()))
    print()
    print("SWEEP STATE — the whole question:")
    for st in ("swept", "broken", "intact", "unknown"):
        s = B[B["sweep_state"] == st]
        if len(s):
            print("    %-9s n=%6d (%4.1f%%) | win %4.1f%% | stop %4.1f%% | median R %+.3f"
                  % (st, len(s), 100.0 * len(s) / len(B),
                     100.0 * (s["R"] > 0).mean(), 100.0 * (s["why"] == "stop").mean(),
                     s["R"].median()))
    print()
    print("AS GATES (date-clustered; <<< = the interval clears zero):")
    swept = B["sweep_state"] == "swept"
    line(B, "swept (pierced AND reclaimed)", swept)
    line(B, "NOT broken (swept or intact)", B["sweep_state"] != "broken")
    line(B, "broken (pierced, never reclaimed)", B["sweep_state"] == "broken")
    print()
    print("HIS WORDS: BULLISH stocks that got swept:")
    bull = B["mood"] >= 25
    line(B, "mood >= 25 alone", bull)
    line(B, "swept + mood >= 25", swept & bull)
    line(B, "swept + not a knife", swept & (~B["knife"].astype(bool)))
    line(B, "swept + mood >= 25 + not a knife", swept & bull & (~B["knife"].astype(bool)))
    print()
    print("SWEEP DEPTH (his 'in the short while' — how deep the stop run went):")
    for lo, hi in ((0.0, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, 4.0)):
        m = swept & (B["pierce_pct"] >= lo) & (B["pierce_pct"] < hi)
        line(B, "swept, pierce %.1f-%.1f%%" % (lo, hi), m)
    print()
    print("RECLAIM SPEED (a same-bar reclaim is the classic stop run):")
    for b in (0, 1, 2, 5):
        m = swept & (B["reclaim_bars"] <= b)
        line(B, "swept, reclaimed within %d bar(s)" % b, m)


if __name__ == "__main__":
    main()
