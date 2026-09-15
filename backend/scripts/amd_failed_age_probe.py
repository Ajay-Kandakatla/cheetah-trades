"""How many names read "AMD base failed · Nd ago" over a FRESHER base?

The probe behind the age-out clause in `amd.find_cycle` (2026-09-14). Run it
in the api container against the detector as deployed:

    docker compose cp backend/scripts/amd_failed_age_probe.py api:/tmp/probe.py
    docker compose exec -T api python /tmp/probe.py

Before the clause (failed phase, no age-out) on the 2,673 `full` names: 1,572
read failed, and 699 of those had a base that formed entirely after the
failure bar (11-30 sessions old: 296; 31-90: 330; >90: 27; 4-10: 46). After
it: failed 885, accumulation 686, and the residual "fresh_base" rows are the
dozen where the probe's search finds a base the detector's single-pass
walk-back does not. Read-only; touches nothing.
"""
import sys, time
sys.path.insert(0, "/app")
from collections import Counter
import multiprocessing as mp

def _init():
    from sepa import prices
    prices._mongo_coll = None
    prices._mongo_disabled = False

def probe(sym):
    from sepa import prices
    from supply_demand import amd
    try:
        df = prices.load_prices(sym)
        if df is None or len(df) < 80:
            return sym, None
        cyc = amd.find_cycle(df, direction="bullish")
        if not cyc:
            return sym, ("none", None, False)
        ph = cyc["phase"]
        fa = (cyc.get("failure") or {}).get("bars_ago")
        n = len(df)
        # is there a fresher bare base the walk-back skipped? mirror find_cycle's acc_only rule
        fresh = False
        if ph in ("failed", "manipulation", "distribution"):
            end_hi = cyc["accumulation"]["end"]
            for end_at in range(n - 1, max(end_hi, amd.MIN_BASE_BARS), -1):
                base = amd.find_base(df, end=end_at)
                if base and base["end"] >= n - 1 - amd.MAX_RAID_AGE and base["start"] > (cyc.get("failure") or cyc.get("manipulation") or {}).get("idx", -1):
                    fresh = True
                    break
        return sym, (ph, fa, fresh)
    except Exception as exc:
        return sym, ("err:%s" % type(exc).__name__, None, False)

if __name__ == "__main__":
    from sepa import universe as U
    syms = list(dict.fromkeys(U.load_universe("full")))
    t0 = time.time()
    with mp.Pool(16, initializer=_init) as pool:
        out = pool.map(probe, syms, chunksize=8)
    rows = [(s, r) for s, r in out if r]
    print("names", len(rows), "%.0fs" % (time.time() - t0))
    print("phase mix", Counter(r[0] for _, r in rows))
    ages = Counter()
    for _, (ph, fa, fresh) in rows:
        if ph == "failed":
            b = "<=3" if fa <= 3 else "4-10" if fa <= 10 else "11-30" if fa <= 30 else "31-90" if fa <= 90 else ">90"
            ages[(b, "fresh_base" if fresh else "no_fresh_base")] += 1
    for k in sorted(ages): print("  failed", k, ages[k])
    st = Counter()
    for _, (ph, fa, fresh) in rows:
        if ph in ("manipulation", "distribution"):
            st[(ph, "fresh_base" if fresh else "no_fresh_base")] += 1
    for k in sorted(st): print("  ", k, st[k])
