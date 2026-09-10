"""Does a BIG gap to overhead supply make the demand bounce QUICKER?

Ajay 2026-09-10: "I wanna be able to find all demand zone that have great gap
with over heads. I wanna set limit orders for these becuz the bounce is so
quick like ATKR, Netapp few others had this kind of setup lately."

Same cohort/gates/trade as studies/bounce_quality_study.events() -- replicated
lean because the full harness OOM-killed at 2,400/2,650 names computing ~40
columns of stationary-bottom definitions this question does not use.

CIRCULARITY, stated up front: R and "target hit" are DEFINED by room (target IS
the overhead band), so ranking on them is a tautology -- measured and noted
2026-09-09. Headline metrics here are FIXED-PERCENT and TIME, which room does
not define. `bars_to_3pct` is the literal reading of "the bounce is so quick".
"""
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/app")
from sepa import prices, universe
from supply_demand import price_zones, demand_reentry, alert_gates as AG

FLOOR, MAXC = 252, 20
MIN_DVOL = 2_000_000.0
rng = np.random.default_rng(20260910)
geom = demand_reentry.zone_geom()
coll = prices._get_mongo()

# Use the study's OWN loader, not a reimplementation. My first pass queried
# {"_id": sym} on a cache that keys on "symbol" and read a "d" column that
# _frame is the thing that builds -- so every frame came back None and the
# replay reported events=0 instead of failing loudly.
sys.argv = ["x"]
from studies.bounce_quality_study import _frame

def frame(sym):
    try:
        f = _frame(coll, sym)
    except Exception:
        return None
    return f if f is not None and len(f) >= FLOOR + MAXC + 2 else None

syms = universe.load_universe("full") or []
rows = []
for i, sym in enumerate(syms):
    if i % 250 == 0:
        print("  %d/%d events=%d" % (i, len(syms), len(rows)), file=sys.stderr, flush=True)
    f = frame(sym)
    if f is None:
        continue
    c = f["close"].to_numpy(float); hi = f["high"].to_numpy(float)
    lo = f["low"].to_numpy(float);  vol = f["volume"].to_numpy(float)
    dv = pd.Series(c * vol).rolling(50, min_periods=50).median().to_numpy()
    dates = f["d"].to_numpy()
    for j in range(FLOOR, len(f) - MAXC - 1):
        if not (dv[j - 1] >= MIN_DVOL):
            continue
        px, prev, dlow = float(c[j]), float(c[j - 1]), float(lo[j])
        z = price_zones.compute(f.iloc[max(0, j - 252):j], last_price=px,
                                max_zones=None, **geom)
        if not z:
            continue
        bands = (z.get("supply_zones") or []) + (z.get("demand_zones") or [])
        hits = []
        for b in (z.get("demand_zones") or []):
            if not AG.demand_proximity_gate(px, b):
                continue
            ap = AG.approach_read(px, b, prev, dlow)
            if isinstance(ap, dict):
                hits.append((float(b["lo"]), b, ap))
        if not hits:
            continue
        band_lo, band, ap = max(hits, key=lambda t: t[0])
        if ap.get("dir") != "bouncing":          # the shipped baseline cohort
            continue
        ok_room, room = AG.room_gate(px, bands, prev)
        if not ok_room or room is None:          # CLEAR has no overhead to rank
            continue
        rp = room.get("room_pct_raw")
        if rp is None:
            continue
        stop = float(band["lo"]) * (1.0 - AG.STOP_BUFFER_PCT / 100.0)
        if px <= stop:
            continue
        tgt = float(room["target"])
        k3 = np.nan; stopped_at = np.nan; hit_t = np.nan
        for k in range(1, MAXC + 1):
            t = j + k
            if np.isnan(k3) and hi[t] >= px * 1.03:
                k3 = k
            if np.isnan(stopped_at) and lo[t] <= stop:
                stopped_at = k
            if np.isnan(hit_t) and hi[t] >= tgt:
                hit_t = k
            if not np.isnan(stopped_at):
                break
        rows.append((float(rp), float(str(dates[j])[:10].replace("-", "")),
                     (c[j + 5] / px - 1) * 100, (c[j + 10] / px - 1) * 100,
                     (c[j + 20] / px - 1) * 100, k3, stopped_at, hit_t))

D = pd.DataFrame(rows, columns=["room", "date", "p5", "p10", "p20",
                                "k3", "kstop", "ktgt"])
print("\nevents=%d  dates=%d" % (len(D), D["date"].nunique()))
D["q3_5"]  = (D["k3"] <= 5) & (D["kstop"].isna() | (D["k3"] <= D["kstop"]))
D["u5_20"] = D["p20"] >= 5.0
D["stop"]  = D["kstop"].notna()

def boot(d, col, draws=4000):
    u = d["date"].unique(); idx = {x: np.where(d["date"].to_numpy() == x)[0] for x in u}
    v = d[col].to_numpy(float); out = np.empty(draws)
    for b in range(draws):
        s = np.concatenate([idx[x] for x in rng.choice(u, len(u), replace=True)])
        out[b] = v[s].mean()
    return np.percentile(out, [2.5, 97.5])

assert len(D) > 1000, "replay produced %d events -- loader/gate bug, not a result" % len(D)
D["bucket"] = pd.qcut(D["room"], 4, labels=["Q1 tight", "Q2", "Q3", "Q4 BIG"])
print("\n%-10s %7s %7s %9s %9s %9s   %9s" %
      ("bucket", "n", "room%", "+3%<=5d", "med d>+3%", "STOPPED", "[circ]tgt"))
for b, g in D.groupby("bucket", observed=True):
    print("%-10s %7d %7.1f %8.1f%% %9.1f %8.1f%%   %8.1f%%" %
          (b, len(g), g["room"].median(), g["q3_5"].mean()*100,
           g["k3"].median(), g["stop"].mean()*100, g["ktgt"].notna().mean()*100))

A, B = D[D.bucket == "Q4 BIG"], D[D.bucket == "Q1 tight"]
print("\nBIG gap minus tight, whole-DATE bootstrap 95%:")
for col, lab in (("q3_5", "+3% within 5d"), ("u5_20", "+5% by 20d"), ("stop", "stopped out")):
    a, c_ = boot(A, col), boot(B, col)
    d_ = (A[col].mean() - B[col].mean()) * 100
    l, h = (a[0]-c_[1])*100, (a[1]-c_[0])*100
    print("  %-15s %+6.2f pp  [%+.2f, %+.2f]%s" %
          (lab, d_, l, h, "" if (l > 0) == (h > 0) else "   <-- INCLUDES ZERO"))

print("\nabsolute cutoff sweep (what a board threshold selects):")
print("%-10s %7s %9s %9s %9s" % ("room >=", "n", "+3%<=5d", "med d", "STOPPED"))
for t in (5, 8, 10, 12, 15, 20, 25, 30):
    g = D[D.room >= t]
    if len(g) < 300: continue
    print("%-10s %7d %8.1f%% %9.1f %8.1f%%" %
          ("%d%%" % t, len(g), g["q3_5"].mean()*100, g["k3"].median(), g["stop"].mean()*100))
print("BASELINE all: n=%d  +3%%<=5d=%.1f%%  med d=%.1f  stopped=%.1f%%"
      % (len(D), D["q3_5"].mean()*100, D["k3"].median(), D["stop"].mean()*100))
