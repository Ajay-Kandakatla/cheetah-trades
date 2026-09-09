"""Which clause of the shelf definition earns its place — on the WIN RATE, the
estimator that is not defined by the gate.

R is measured to the target and the target IS the room, so any gate correlated
with room buys R almost definitionally. Win rate and stop rate are binomials and
cannot be gamed that way, so they decide here.
"""
import numpy as np, pandas as pd

D = pd.read_csv("/tmp/bq_events.csv")
B = D[D["dir"] == "bouncing"].copy()
dates = B["date"].values
uniq = np.unique(dates)
idx_by_date = {d: np.flatnonzero(dates == d) for d in uniq}
rng = np.random.default_rng(11)

def clustered(mask, draws=1500):
    dw, ds = [], []
    mv = mask.values
    for _ in range(draws):
        rows = np.concatenate([idx_by_date[d] for d in rng.choice(uniq, len(uniq), True)])
        s, m = B.iloc[rows], mv[rows]
        k, o = s[m], s[~m]
        if len(k) < 20 or len(o) < 20:
            continue
        dw.append(100.0*(k["R"] > 0).mean() - 100.0*(o["R"] > 0).mean())
        ds.append(100.0*(k["why"] == "stop").mean() - 100.0*(o["why"] == "stop").mean())
    return np.mean(dw), np.percentile(dw, [2.5, 97.5]), np.mean(ds), np.percentile(ds, [2.5, 97.5])

def row(label, mask):
    k, o = B[mask], B[~mask]
    if len(k) < 100 or len(o) < 100:
        print("  %-34s keep %5d — too few" % (label, len(k))); return
    w, wci, s, sci = clustered(mask)
    star = "  <<<" if wci[0] > 0 else ""
    print("  %-34s keep %5d (%4.1f%%) | win %4.1f%% vs %4.1f%% Δ%+5.2fpp CI[%+5.2f,%+5.2f] | stop Δ%+5.2fpp CI[%+5.2f,%+5.2f]%s"
          % (label, len(k), 100.0*len(k)/len(B),
             100.0*(k["R"] > 0).mean(), 100.0*(o["R"] > 0).mean(),
             w, wci[0], wci[1], s, sci[0], sci[1], star))

print("baseline: n=%d  win %.1f%%  stop %.1f%%  (192 dates)"
      % (len(B), 100.0*(B["R"] > 0).mean(), 100.0*(B["why"] == "stop").mean()))
print()
print("THE SHELF DEFINITION, CLAUSE BY CLAUSE (win rate, date-clustered):")
row("full shelf_ok (all clauses)", B["shelf_ok"].astype(bool))
for t in (2, 3, 5, 8, 10):
    row("no new low in >= %d sessions" % t, B["sh_bars_since_new_low"] >= t)
for t in (3, 4, 5, 6):
    row("lows at the shelf >= %d" % t, B["sh_lows_at_shelf"] >= t)
for t in (5, 8, 10):
    row("shelf span >= %d sessions" % t, B["sh_shelf_span"] >= t)
for t in (3, 5, 8):
    row("no cut under the shelf in >= %d" % t, B["sh_bars_since_break"] >= t)
print()
print("STACKED WITH WHAT SHIPPED TODAY:")
nk = ~B["knife"].astype(bool)
nl = B["sh_bars_since_new_low"] >= 5
row("not-knife", nk)
row("not-knife + no new low >= 5", nk & nl)
row("not-knife + no new low >= 5 + shelf", nk & B["shelf_ok"].astype(bool))
