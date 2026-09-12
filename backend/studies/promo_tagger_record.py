"""Forward record of the promo-circuit taggers — re-runnable.

Ajay 2026-09-11: "find influences or Reddit groups or users or stock witz users
that predicted explosive sector stocks ahead of time?"

MEASURED 2026-09-11 over push_history promo_alert rows (2026-09-02 .. 2026-09-11,
440 alerts, 165 tickers, 15 tagger handles). Median forward return from the TAG
date, against a placebo drawn from our own universe on the SAME dates:

    tagger                tags     +1d      +3d      +5d
    @topstockalerts        261   -2.94%   -6.55%   -9.15%
    @StockSenseiTrendTrade  33   -4.35%   -9.21%  -18.66%
    @PSM_EmpowerTrading     30   -4.78%   -8.93%  -17.16%
    @beppels                10   -9.03%  -37.80%  -59.30%
    PLACEBO (random)             -0.41%   -1.19%   -2.14%

Every handle is NEGATIVE at every horizon and WORSE than a random name. Win
rates 35%/26%/28% for the biggest account vs 40%/35%/26% random. Being tagged
is a FADE, not a signal — which is what the board already says: promotion is
never foresight.

CAVEAT, stated because the magnitudes invite over-reading: the window is NINE
DAYS. The direction is uniform across all eight measurable handles and the
sample is 261 tags for the largest, but this is one regime, not a multi-year
verdict. Re-run it as push_history grows.

RUN:
  docker run --rm --network cheetah-market-app_default \
    -e MONGO_URL="mongodb://mongo:27017" -v "$(pwd)/backend":/app:ro -w /app \
    -e PYTHONPATH=/app -v cheetah-market-app_cheetah-scans:/root/.cheetah:ro \
    -v /tmp/scratch:/scratch cheetah-api:latest \
    python -u /app/studies/promo_tagger_record.py
"""
import sys; sys.path.insert(0,'/app')
import os, re, random, statistics as st, time
from collections import defaultdict
from pymongo import MongoClient

c = MongoClient(os.environ.get("MONGO_URL","mongodb://mongo:27017"))
db = c.get_database("cheetah")
pc = db["price_cache"]

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

def fwd(sym, d0, n):
    """Return % from the close on/after d0 to n sessions later. None if unpriceable."""
    s = series(sym)
    if not s: return None
    ks = sorted(s)
    i = next((j for j, k in enumerate(ks) if k >= d0), None)
    if i is None or i + n >= len(ks): return None
    a, b = s[ks[i]], s[ks[i + n]]
    if not a: return None
    return 100.0 * (b - a) / a

rows = list(db["push_history"].find({"kind": "promo_alert"}, {"ticker":1,"title":1,"ts":1}))
print("promo_alert rows in push_history: %d" % len(rows))

# tag date = alert date minus the "Nd ago" the title records
tags = defaultdict(list)          # handle -> [(ticker, tag_date)]
seen = set()
for r in rows:
    t = r.get("title") or ""
    sym = r.get("ticker")
    if not sym: continue
    m = re.search(r"tagged by (.+?) (\d+)d ago", t)
    if not m: continue
    days = int(m.group(2))
    d0 = time.strftime("%Y-%m-%d", time.localtime(r.get("ts", 0) - days * 86400))
    for h in re.findall(r"@([A-Za-z0-9_]+)", m.group(1)):
        key = (h, sym, d0)
        if key in seen: continue
        seen.add(key)
        tags[h].append((sym, d0))

print("distinct tagger handles: %d" % len(tags))
print()

HORIZONS = [1, 3, 5, 10]
univ = None
def placebo(dates, n, draws=400):
    global univ
    if univ is None:
        from sepa import universe as U
        univ = [s for s in (U.load_universe("broad") or []) if series(s)]
    random.seed(7)
    out = []
    for _ in range(draws):
        s = random.choice(univ); d = random.choice(dates)
        v = fwd(s, d, n)
        if v is not None: out.append(v)
    return out

ranked = sorted(tags.items(), key=lambda kv: -len(kv[1]))[:8]
print("%-22s %5s  %s" % ("TAGGER", "tags", "  ".join("%9s" % ("+%dd" % n) for n in HORIZONS)))
print("-" * 78)
alldates = []
for h, lst in ranked:
    cells = []
    for n in HORIZONS:
        vs = [fwd(s, d, n) for s, d in lst]
        vs = [v for v in vs if v is not None]
        cells.append("%+6.2f%%(%d)" % (st.median(vs), len(vs)) if vs else "     -   ")
    alldates += [d for _, d in lst]
    print("%-22s %5d  %s" % ("@" + h[:21], len(lst), "  ".join(cells)))

print()
print("PLACEBO — random names from our universe, same tag dates:")
cells = []
for n in HORIZONS:
    p = placebo(sorted(set(alldates)), n)
    cells.append("%+6.2f%%(%d)" % (st.median(p), len(p)) if p else "  -  ")
print("%-22s %5s  %s" % ("random", "", "  ".join(cells)))

print()
print("=" * 78)
print("WIN RATE — share of tags that were UP n sessions later")
print("=" * 78)
print("%-22s %5s  %s" % ("TAGGER", "tags", "  ".join("%9s" % ("+%dd" % n) for n in HORIZONS)))
for h, lst in ranked:
    cells = []
    for n in HORIZONS:
        vs = [fwd(s, d, n) for s, d in lst]
        vs = [v for v in vs if v is not None]
        cells.append("%8.0f%%" % (100.0*sum(1 for v in vs if v > 0)/len(vs)) if vs else "    -   ")
    print("%-22s %5d  %s" % ("@" + h[:21], len(lst), "  ".join(cells)))
cells = []
for n in HORIZONS:
    p = placebo(sorted(set(alldates)), n)
    cells.append("%8.0f%%" % (100.0*sum(1 for v in p if v > 0)/len(p)) if p else "   -  ")
print("%-22s %5s  %s" % ("random", "", "  ".join(cells)))
