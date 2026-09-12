"""Score a dated social conviction list forward, with a placebo — re-runnable.

Built 2026-09-11 for Ajay's question about who calls sector moves early. Scores
@stealingtime's dated StockTwits "Top 10 Conviction Plays" lists (the rare case
of a public, timestamped, complete record) from the close of the first session
AFTER each post, against RSP, SMH, and 2,000 random same-size baskets drawn from
our own universe over the identical window.

MEASURED 2026-09-11 (exit 2026-09-11):
    list of 8/17  basket  -0.66%   vs RSP  +1.50pp   vs SMH  -1.06pp   beat  80.1% of random
    list of 8/24  basket  +6.92%   vs RSP  +9.95pp   vs SMH  +4.00pp   beat 100.0%
    list of 8/31  basket +10.68%   vs RSP +11.85pp   vs SMH  +5.75pp   beat 100.0%
    list of 9/7   basket  -2.88%   vs RSP  -2.11pp   vs SMH  -2.60pp   beat  18.6%

READ IT AGAINST SMH, NOT RSP. The edge vs the equal-weight benchmark averages
+5.3pp and looks spectacular; against the semis ETF it averages +1.5pp and is
NEGATIVE on two of four lists. Most of the apparent skill is sector beta from
being in semis during a semis rally. n=4 lists is far too small to call skill.

AXTI appeared in NONE of the four lists — first mentioned 2026-09-10, after the
+23.8% run, +0.11% since.

IQEPF and SIVEF are OTC and absent from price_cache; they are NAMED as unpriced
rather than dropped silently.

RUN: same container recipe as promo_tagger_record.py.
"""
import sys; sys.path.insert(0,'/app')
import os, random, statistics as st
from pymongo import MongoClient

c = MongoClient(os.environ.get("MONGO_URL","mongodb://mongo:27017"))
db = c.get_database("cheetah")
pc = db["price_cache"]

LISTS = [
    ("2026-08-17", "2026-08-18", ["SNDK","NBIS","DRAM","SKHY","AAOI","IQEPF","SIVEF","KEEL","STX","WDC"]),
    ("2026-08-24", "2026-08-25", ["SNDK","NBIS","DRAM","BE","SKHY","IQEPF","SIVEF","AAOI","KEEL","IBIT"]),
    ("2026-08-31", "2026-09-01", ["SNDK","SKHY","DRAM","NBIS","BE","IQEPF","AAOI","SIVEF","ALAB","LITE"]),
    ("2026-09-07", "2026-09-08", ["SNDK","SKHY","DRAM","BE","NBIS","IQEPF","AAOI","SIVEF","MU","ALAB"]),
]
EXIT = "2026-09-11"
BENCH = ["RSP", "SMH"]

_cache = {}
def series(sym):
    if sym in _cache: return _cache[sym]
    d = pc.find_one({"symbol": sym}) or {}
    out = {}
    for b in (d.get("bars") or d.get("data") or []):
        dt = b.get("d") or b.get("date") or b.get("t")
        cl = b.get("c") if b.get("c") is not None else b.get("close")
        if dt and cl:
            try: out[str(dt)[:10]] = float(cl)
            except (TypeError, ValueError): pass
    _cache[sym] = out
    return out

def ret(sym, d0, d1):
    s = series(sym)
    if not s: return None
    ks = sorted(s)
    a = next((k for k in ks if k >= d0), None)
    b = next((k for k in reversed(ks) if k <= d1), None)
    if not a or not b or a >= b: return None
    return 100.0 * (s[b] - s[a]) / s[a]

print("=" * 78)
print("@stealingtime — dated 'Top 10 Conviction Plays', scored to %s" % EXIT)
print("=" * 78)

all_rows = []
for posted, entry, names in LISTS:
    rs, missing = [], []
    for n in names:
        r = ret(n, entry, EXIT)
        (rs.append((n, r)) if r is not None else missing.append(n))
    vals = [r for _, r in rs]
    bench = {b: ret(b, entry, EXIT) for b in BENCH}
    avg = sum(vals)/len(vals) if vals else None
    med = st.median(vals) if vals else None
    win = 100.0*sum(1 for v in vals if v > 0)/len(vals) if vals else None
    print()
    print("LIST OF %s   (entry = %s close -> %s)" % (posted, entry, EXIT))
    print("   priced %d of %d   unpriced: %s" % (len(vals), len(names), ", ".join(missing) or "none"))
    for n, r in sorted(rs, key=lambda x: -x[1]):
        print("      %-6s %+7.2f%%" % (n, r))
    print("   basket avg %+.2f%%  median %+.2f%%  %.0f%% up" % (avg, med, win))
    for b in BENCH:
        if bench[b] is not None:
            print("      vs %-4s %+7.2f%%   -> edge %+.2f pp" % (b, bench[b], avg - bench[b]))
    all_rows.append((posted, avg, med, win, bench))

print()
print("=" * 78)
print("PLACEBO — same entry/exit dates, random names from OUR universe")
print("=" * 78)
from sepa import universe as U
univ = [s for s in (U.load_universe("full") or []) if series(s)]
random.seed(11)
for posted, entry, names in LISTS:
    k = len(names)
    draws = []
    for _ in range(2000):
        pick = random.sample(univ, k)
        vs = [ret(s, entry, EXIT) for s in pick]
        vs = [v for v in vs if v is not None]
        if vs: draws.append(sum(vs)/len(vs))
    draws.sort()
    real = [r for r in (ret(n, entry, EXIT) for n in names) if r is not None]
    realavg = sum(real)/len(real)
    pct = 100.0*sum(1 for d in draws if d < realavg)/len(draws)
    lo, hi = draws[int(.05*len(draws))], draws[int(.95*len(draws))]
    print()
    print("LIST OF %s: basket %+.2f%%   random-%d basket median %+.2f%%  (90%% band %+.2f%% .. %+.2f%%)"
          % (posted, realavg, k, st.median(draws), lo, hi))
    print("   the basket beat %.1f%% of 2,000 random %d-name baskets over the same window" % (pct, k))

print()
print("=" * 78)
print("AXTI specifically")
print("=" * 78)
print("   AXTI never appeared in ANY of the four dated lists.")
print("   first AXTI mention by this account: 2026-09-10 18:10 UTC")
for d0, lbl in (("2026-09-03","from the 9/3 low close"), ("2026-09-10","from the 9/10 mention")):
    print("   AXTI %s -> %s : %+.2f%%" % (lbl, EXIT, ret("AXTI", d0, EXIT) or 0.0))
