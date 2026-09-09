"""Does raising the room floor help? MY OWN run, on the study's event table.

Both auditors returned do_not_quote on the study's headline. The specific reasons
that matter here:
  * mean R is tail-dominated (top 1% of events carry most of total R) and the
    MEDIAN R is -1.0 in every cohort -> lead on win/stop rate, which are
    binomials with tight intervals.
  * events cluster on dates -> resample whole DATES, never individual events.
Room is a TIGHTENING of an existing gate (ALERT_MIN_ROOM_PCT = 5.0), so it is
the only candidate here that cannot be accused of loosening anything.
"""
import numpy as np, pandas as pd

D = pd.read_csv("/tmp/bq_events.csv")
B = D[D["dir"] == "bouncing"].copy()
B["clear"] = B["clear"].astype(bool)
print("bouncing events: n=%d  names=%d  dates=%d  %s -> %s"
      % (len(B), B.symbol.nunique(), B.date.nunique(), B.date.min(), B.date.max()))

r = B["R"].values
srt = np.sort(r)[::-1]
top1 = int(len(r) * 0.01)
print("TAIL: median R %.3f | mean R %.3f | top 1%% (n=%d) carry %.1f%% of total R | max %.1f"
      % (np.median(r), r.mean(), top1, 100.0 * srt[:top1].sum() / r.sum(), r.max()))
print("      win %.1f%% | stop-out %.1f%%" % (100.0*(r > 0).mean(),
                                              100.0*(B["why"] == "stop").mean()))
print()

dates = B["date"].values
uniq = np.unique(dates)
rng = np.random.default_rng(7)

def clustered(mask, draws=2000):
    """Resample whole DATES; return the delta in win rate and in mean R."""
    keep, drop = B[mask], B[~mask]
    if len(keep) < 50 or len(drop) < 50:
        return None
    dw, dr = [], []
    idx_by_date = {d: np.flatnonzero(dates == d) for d in uniq}
    for _ in range(draws):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        rows = np.concatenate([idx_by_date[d] for d in pick])
        s = B.iloc[rows]
        k, o = s[mask.values[rows]], s[~mask.values[rows]]
        if len(k) < 20 or len(o) < 20:
            continue
        dw.append(100.0*(k["R"] > 0).mean() - 100.0*(o["R"] > 0).mean())
        dr.append(k["R"].mean() - o["R"].mean())
    return (np.percentile(dw, [2.5, 97.5]), np.percentile(dr, [2.5, 97.5]),
            np.mean(dw), np.mean(dr))

def row(label, mask):
    keep, drop = B[mask], B[~mask]
    if not len(keep) or not len(drop):
        print("  %-30s n=0" % label); return
    c = clustered(mask)
    ci = ("win Δ %+5.1fpp CI[%+5.1f,%+5.1f] | R Δ %+.3f CI[%+.3f,%+.3f]"
          % (c[2], c[0][0], c[0][1], c[3], c[1][0], c[1][1])) if c else "(too few)"
    print("  %-30s keep %5d (%4.1f%%) | win %4.1f%% vs %4.1f%% | stop %4.1f%% vs %4.1f%% | %s"
          % (label, len(keep), 100.0*len(keep)/len(B),
             100.0*(keep["R"] > 0).mean(), 100.0*(drop["R"] > 0).mean(),
             100.0*(keep["why"] == "stop").mean(), 100.0*(drop["why"] == "stop").mean(), ci))

print("ROOM — a TIGHTENING of ALERT_MIN_ROOM_PCT (live floor = 5.0):")
for t in (10, 15, 20, 25):
    row("room_pct >= %d or clear" % t, (B["room_pct"] >= t) | B["clear"])
row("CLEAR runway only", B["clear"])
print()
print("THE GATES SHIPPED THIS AFTERNOON (proxy versions, for contrast):")
row("not a falling knife", ~B["knife"].astype(bool))
row("mood >= 25 (full frame)", B["mood"] >= 25)
row("stationary bottom (shelf)", B["shelf_ok"].astype(bool))
