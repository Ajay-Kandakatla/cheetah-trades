# ─────────────────────────────────────────────────────────────────────────────
# Bonde board — the measurement the board prints. Run 2026-09-13.
#
# These are the INDEPENDENT AUDIT scripts. They re-measured the first pass
# (parent_ep.py / parent_tiers.py) with their own code, their own fetch and
# ~2x the panel, and they are the authority: the Bonde tab, sepa/bonde.py and
# docs/sepa/bonde_board.md all quote THESE numbers.
#
# Run them inside the api container — that is the only place the Massive key
# lives, and a throwaway container silently falls back to Yahoo:
#
#   cd /Users/ajay/clinet-test/cheetah-market-app
#   docker compose exec -T api mkdir -p /root/.cheetah/aud
#   docker compose cp backend/scripts/bonde_audit/core.py api:/root/.cheetah/aud/core.py
#   docker compose exec -T api python - < backend/scripts/bonde_audit/fetch.py
#   docker compose exec -T api python - < backend/scripts/bonde_audit/oracle.py
#   docker compose exec -T api python - < backend/scripts/bonde_audit/lane1.py
#   docker compose exec -T api python - < backend/scripts/bonde_audit/lane1b.py
#   docker compose exec -T api python - < backend/scripts/bonde_audit/lane2.py
#   docker compose exec -T api python - < backend/scripts/bonde_audit/attack.py
#   docker compose exec -T api python - < backend/scripts/bonde_audit/sens.py
#
# Heredoc/stdin, never `python /tmp/x.py` — that puts /tmp on sys.path instead
# of /app and the sepa imports fail. Caches live at /root/.cheetah/audit_px_v1.pkl
# and audit_fin_v1.json.gz; delete them to refetch (~80s).
# ─────────────────────────────────────────────────────────────────────────────
#
# WHAT THIS ONE IS: the fetch. Massive /vX/reference/financials quarterly,
# 10 workers WITH RETRY. The retry is the point — the first pass had none and
# silently lost half the universe (1,245 of 2,685 names vs 2,546 here), which
# is what made its 'coverage is 46%' limitation an artifact of its own code.
# ─────────────────────────────────────────────────────────────────────────────

import os, sys, json, gzip, pickle, time
sys.path.insert(0,"/app")
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from sepa import universe, prices
import sepa.canslim as cs
import requests

OUT_PX  = "/root/.cheetah/audit_px_v1.pkl"
OUT_FIN = "/root/.cheetah/audit_fin_v1.json.gz"

syms = sorted(set(universe.load_universe()))
print("universe", len(syms), flush=True)

# ---------- prices ----------
if os.path.exists(OUT_PX):
    px = pickle.load(open(OUT_PX,"rb")); print("px cache hit", len(px), flush=True)
else:
    px = {}
    t=time.time()
    def one(s):
        try:
            df = prices.load_prices(s)
        except Exception:
            return s, None
        if df is None or len(df) < 60: return s, None
        idx = np.array([d.date().isoformat() for d in df.index])
        return s, dict(d=idx,
                       o=df["open"].to_numpy(float), h=df["high"].to_numpy(float),
                       l=df["low"].to_numpy(float),  c=df["close"].to_numpy(float),
                       v=df["volume"].to_numpy(float))
    with ThreadPoolExecutor(8) as ex:
        for s,r in ex.map(one, syms):
            if r is not None: px[s]=r
    pickle.dump(px, open(OUT_PX,"wb"))
    print("px fetched", len(px), round(time.time()-t,1), "s", flush=True)

nb=[len(v["d"]) for v in px.values()]
print("bars median", int(np.median(nb)), "min", min(nb), "max", max(nb), flush=True)
alld=sorted(set(px["SPY"]["d"]))
print("window", alld[0], alld[-1], len(alld), flush=True)

# ---------- financials (raw, point-in-time fields only) ----------
if os.path.exists(OUT_FIN):
    fin = json.loads(gzip.open(OUT_FIN,"rt").read()); print("fin cache hit", len(fin), flush=True)
else:
    key = cs.stocks_key()
    base = "https://api.massive.com/vX/reference/financials"
    def grab(s):
        out=[]
        for attempt in range(3):
            try:
                sess=requests.Session()
                r=sess.get(base, params={"ticker":s.upper(),"limit":30,
                                         "timeframe":"quarterly","apiKey":key}, timeout=20)
                if r.status_code!=200:
                    if r.status_code in (429,):
                        time.sleep(1.5); continue
                    return s, {"err":r.status_code}
                res=(r.json() or {}).get("results") or []
                for q in res:
                    out.append({
                        "fy": q.get("fiscal_year"), "fp": q.get("fiscal_period"),
                        "end": q.get("end_date"), "filed": q.get("filing_date"),
                        "start": q.get("start_date"),
                        "rev": cs._income_value(q,"revenues"),
                        "eps": cs._income_value(q,"diluted_earnings_per_share"),
                    })
                return s, {"q":out}
            except Exception as e:
                time.sleep(1.0)
        return s, {"err":"exc"}
    fin={}; t=time.time()
    with ThreadPoolExecutor(10) as ex:
        for i,(s,r) in enumerate(ex.map(grab, syms)):
            fin[s]=r
            if i%500==0: print(" fin", i, round(time.time()-t,1), flush=True)
    gzip.open(OUT_FIN,"wt").write(json.dumps(fin))
    print("fin fetched", len(fin), round(time.time()-t,1),"s", flush=True)

ok=[s for s,v in fin.items() if v.get("q")]
print("fin with rows", len(ok), "err", sum(1 for v in fin.values() if v.get("err")), flush=True)
nq=[len(fin[s]["q"]) for s in ok]
print("quarters median", int(np.median(nq)), flush=True)
# filing_date coverage
tot=sum(nq); nofile=sum(1 for s in ok for q in fin[s]["q"] if not q["filed"])
print("rows", tot, "filing_date None", nofile, round(100*nofile/tot,1),"%", flush=True)
# how many symbols have >=5 quarters WITH filing dates
c=sum(1 for s in ok if sum(1 for q in fin[s]["q"] if q["filed"] and q["rev"] is not None)>=5)
print("syms with >=5 filed rev quarters", c, flush=True)
