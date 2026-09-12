"""Impact of deleting the share-count liquidity leg in sepa/adr.py.

Re-runnable (Rule: ship the backtest with the claim). Reads the latest stored
SEPA scan and re-scores each row's liquidity three ways:

    OR   (the old rule)   avg_dollar_vol >= $20M OR avg_shares >= 200k
    AND  (his first pick)  avg_dollar_vol >= $20M AND avg_shares >= 200k
    $VOL (shipped)         avg_dollar_vol >= $20M

MEASURED 2026-09-11 over 3,738 sepa_research_cache rows:

    OR   3,091 liquid
    AND  2,113 liquid   -978 (-31.6%)   ... and 53 of those are NVR-class
    $VOL 2,166 liquid   -925 (-29.9%)   ... keeping all 53

    925 rows passed on the SHARE leg alone; 365 of them under $5.
    Worst: ARAI $0.29 on $148,074/day, AITX $0.02 on 3.76M shares.
    53 kept by $VOL, deleted by AND: NVR $6,404, SEB $4,308, FCNCA $2,150,
    WTM $2,138, MKL $1,895, MTD $1,357, GHC $1,167, NEU $851.
    208 rows price under $2.00; 3 of them (BTBT, GPRO, UWMC) clear $20M/day
    and are stopped ONLY by the new $2 price floor.

Price is the 50-day AVERAGE, derived as avg_dollar_vol / avg_shares — the
research cache carries no price column, and the derivation is exact from the
same two stored fields.

Run:
  docker run --rm --network cheetah-market-app_default -e MONGO_URL="mongodb://mongo:27017" \
    -v "$(pwd)/backend":/app:ro -w /app -e PYTHONPATH=/app \
    -v cheetah-market-app_cheetah-scans:/root/.cheetah:ro -v /tmp/scratch:/scratch \
    cheetah-api:latest python -u /scratch/liq_leg_impact.py
"""
import os
from pymongo import MongoClient

MIN_DV, MIN_SH = 20_000_000.0, 200_000

db = MongoClient(os.getenv("MONGO_URL", "mongodb://mongo:27017"))["cheetah"]

rows = list(db.sepa_research_cache.find(
    {}, {"symbol": 1, "liquidity": 1, "price": 1, "last_close": 1,
         "last_bar_date": 1, "cached_at": 1}))
if not rows:
    raise SystemExit("sepa_research_cache is empty")
print("sepa_research_cache — %d rows" % len(rows))

def legs(r):
    liq = r.get("liquidity") or {}
    dv = liq.get("avg_dollar_vol")
    sh = liq.get("avg_shares")
    try:
        dv = float(dv) if dv is not None else None
        sh = float(sh) if sh is not None else None
    except (TypeError, ValueError):
        return None, None
    if dv != dv or sh != sh:
        return None, None
    return dv, sh

share_only, lost_inst, under5 = [], [], 0
n_or = n_and = n_dv = 0
for r in rows:
    dv, sh = legs(r)
    if dv is None or sh is None:
        continue
    # 50-day AVERAGE price, derived from the same two stored fields. The
    # research cache carries no price column; dv/sh is exact and self-consistent.
    px = (dv / sh) if sh else 0.0
    a, b = dv >= MIN_DV, sh >= MIN_SH
    n_or += (a or b); n_and += (a and b); n_dv += a
    if b and not a:                       # passed on the share leg ALONE
        share_only.append((r.get("symbol"), px, dv, sh))
        under5 += px < 5
    if a and not b:                       # would DIE under AND
        lost_inst.append((r.get("symbol"), px, dv, sh))

print("\nliquid=True counts")
print("  OR  (old)      %5d" % n_or)
print("  AND (his pick) %5d   removes %d (%.1f%%) vs OR"
      % (n_and, n_or - n_and, 100.0 * (n_or - n_and) / max(n_or, 1)))
print("  $VOL (shipped) %5d   removes %d (%.1f%%) vs OR"
      % (n_dv, n_or - n_dv, 100.0 * (n_or - n_dv) / max(n_or, 1)))

print("\npassed on the SHARE leg alone (deleted by both AND and $VOL): %d"
      % len(share_only))
print("  of those, under $5 (50d avg): %d" % under5)
for sym, px, dv, sh in sorted(share_only, key=lambda x: x[2])[:8]:
    print("    %-6s $%8.2f  $%10.0f/day  %9.0f sh" % (sym, px, dv, sh))

print("\nKEPT by $VOL but DELETED by AND (high-priced institutional): %d"
      % len(lost_inst))
for sym, px, dv, sh in sorted(lost_inst, key=lambda x: -x[1])[:10]:
    print("    %-6s $%8.2f  $%10.0f/day  %9.0f sh" % (sym, px, dv, sh))

u2 = [(r.get("symbol"), legs(r)) for r in rows]
u2 = [(s_, dv / sh) for s_, (dv, sh) in u2 if dv and sh and dv / sh < 2.0]
print("\nunder $2.00 (50d avg price): %d of %d rows" % (len(u2), len(rows)))
still = [s_ for s_, px in u2
         if (lambda dv: dv is not None and dv >= MIN_DV)(
             (lambda r: (r.get("liquidity") or {}).get("avg_dollar_vol"))(
                 next(x for x in rows if x.get("symbol") == s_)))]
print("  of those, still liquid under the shipped $VOL rule: %d  %s"
      % (len(still), sorted(still)[:12]))
