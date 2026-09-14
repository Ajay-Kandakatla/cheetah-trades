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
# WHAT THIS ONE IS: the three attacks the first pass never ran — DATE
# clustering (3.67x wider than iid here, while symbol clustering buys 0-15%),
# a per-date sign test, and a tail trim. RESULT: the tier 'edge' is the right
# tail. Strong's 21d mean lift falls +5.27pp -> +0.62pp dropping the top 1% ->
# +0.26pp dropping the top 5%, and every date-clustered CI spans zero.
# ─────────────────────────────────────────────────────────────────────────────

import sys,pickle,collections
sys.path.insert(0,"/app")
exec(open("/root/.cheetah/aud/core.py").read())
import numpy as np
px,fin=load()
recs=prep_fin(fin,"plus90")
ANCH={"SPY","QQQ","IWM"}
cal=list(px["SPY"]["d"]); DATES=[cal[i] for i in range(0,len(cal),21)]
H=[21,63]
rows=[]
for s,P in px.items():
    if s in ANCH: continue
    d=P["d"]; c=P["c"]; v=P["v"]; pos={dd:i for i,dd in enumerate(d)}
    rec=recs.get(s)
    for dt in DATES:
        i=pos.get(dt)
        if i is None or i<60: continue
        st=state_asof(rec,dt) if rec else None
        rows.append(dict(sym=s,date=dt,st=st,
            r={k:((c[i+k]-c[i])/c[i]*100.0) if i+k<len(c) and c[i]>0 else None for k in H},
            mom=float((c[i]-c[i-126])/c[i-126]*100) if i>=126 and c[i-126]>0 else None))
scored=[r for r in rows if r["st"]]
sym_ids={}
for r in rows: sym_ids.setdefault(r["sym"],len(sym_ids)); r["sid"]=sym_ids[r["sym"]]
NS=len(sym_ids)
dix={d:i for i,d in enumerate(DATES)}
for r in rows: r["did"]=dix[r["date"]]
ND=len(DATES)

def cellsym(sel,k): 
    s=[r for r in sel if r["r"][k] is not None]; return Cell([r["sid"] for r in s],[r["r"][k] for r in s])
def celldate(sel,k):
    s=[r for r in sel if r["r"][k] is not None]; return Cell([r["did"] for r in s],[r["r"][k] for r in s])

TIERS={"explosive":lambda r:r["st"]["tier"]=="explosive","strong":lambda r:r["st"]["tier"]=="strong",
       "strong+explosive":lambda r:r["st"]["tier"] in ("strong","explosive"),
       "steady":lambda r:r["st"]["tier"]=="steady","declining":lambda r:r["st"]["tier"]=="declining",
       "BONDE PASS":lambda r:r["st"]["bonde_pass"],
       "floorY_charN":lambda r:r["st"]["cleared_floor"] and not r["st"]["character"],
       "floorY_charY":lambda r:r["st"]["cleared_floor"] and r["st"]["character"]}

print("===== MEDIAN & WIN LIFTS vs ALL SCORED, symbol-clustered =====",flush=True)
for k in H:
    print(f"\n h={k}d")
    base=cellsym(scored,k)
    for nm,f in TIERS.items():
        c=cellsym([r for r in scored if f(r)],k)
        bs=boot([c,base],[med,mean,win],NS,B=500,seed=7)
        dm=bs[:,0,0]-bs[:,1,0]; dmu=bs[:,0,1]-bs[:,1,1]; dw=bs[:,0,2]-bs[:,1,2]
        l1,h1=ci(dm); l2,h2=ci(dmu); l3,h3=ci(dw)
        print(f"  {nm:17s} n={len(c.v):6d} med {med(c.v)-med(base.v):+.2f}pp [{l1:+.2f},{h1:+.2f}] | mean {mean(c.v)-mean(base.v):+.2f}pp [{l2:+.2f},{h2:+.2f}] | win {win(c.v)-win(base.v):+.2f}pp [{l3:+.2f},{h3:+.2f}]")

print("\n===== DATE-CLUSTERED bootstrap (23-24 cross-sections = the real dependence) =====",flush=True)
for k in H:
    print(f"\n h={k}d  (resampling DATES, not symbols)")
    base=celldate(scored,k)
    for nm in ["explosive","strong","strong+explosive","BONDE PASS","floorY_charN"]:
        c=celldate([r for r in scored if TIERS[nm](r)],k)
        bs=boot([c,base],[med,mean,win],ND,B=2000,seed=11)
        dm=bs[:,0,0]-bs[:,1,0]; dmu=bs[:,0,1]-bs[:,1,1]; dw=bs[:,0,2]-bs[:,1,2]
        l1,h1=ci(dm); l2,h2=ci(dmu); l3,h3=ci(dw)
        print(f"  {nm:17s} med {med(c.v)-med(base.v):+.2f}pp [{l1:+.2f},{h1:+.2f}] | mean {mean(c.v)-mean(base.v):+.2f}pp [{l2:+.2f},{h2:+.2f}] | win {win(c.v)-win(base.v):+.2f}pp [{l3:+.2f},{h3:+.2f}]")

print("\n===== PER-DATE SIGN TEST: how many of the cross-sections does the tier actually win? =====",flush=True)
for k in H:
    print(f" h={k}d")
    for nm in ["explosive","strong","strong+explosive","BONDE PASS","floorY_charN"]:
        wins=0; tot=0; diffs=[]
        for d in DATES:
            a=[r["r"][k] for r in scored if r["date"]==d and TIERS[nm](r) and r["r"][k] is not None]
            b=[r["r"][k] for r in scored if r["date"]==d and r["r"][k] is not None]
            if len(a)<20 or len(b)<50: continue
            tot+=1; df=np.median(a)-np.median(b); diffs.append(df)
            if df>0: wins+=1
        print(f"  {nm:17s} median-beats-cross-section in {wins}/{tot} dates; mean of per-date median diffs {np.mean(diffs):+.2f}pp, range [{min(diffs):+.1f},{max(diffs):+.1f}]")

print("\n===== TAIL DEPENDENCE: drop the top 1% of returns in each cell =====",flush=True)
k=21
base=[r["r"][k] for r in scored if r["r"][k] is not None]
for nm in ["explosive","strong","strong+explosive"]:
    a=np.array([r["r"][k] for r in scored if TIERS[nm](r) and r["r"][k] is not None])
    b=np.array(base)
    def trim(x,p): 
        return x[x<=np.percentile(x,p)]
    for p in [100,99,95]:
        print(f"  {nm:17s} trim@{p}th: mean {trim(a,p).mean():+.2f}% vs scored {trim(b,p).mean():+.2f}% -> {trim(a,p).mean()-trim(b,p).mean():+.2f}pp")

print("\n===== CI CHECK 63d (overlapping windows) clustered vs iid =====",flush=True)
k=63
s=[r for r in scored if r["r"][k] is not None]
v=np.array([r["r"][k] for r in s])
uniq=np.unique([r["sid"] for r in s]); rm={u:i for i,u in enumerate(uniq)}
sd=np.array([rm[r["sid"]] for r in s])
rng=np.random.default_rng(2)
iid=np.array([v[rng.integers(0,len(v),len(v))].mean() for _ in range(1500)])
cl=boot([Cell(sd,v)],[mean],len(uniq),B=1500,seed=2)[:,0,0]
dcl=boot([Cell(np.array([r["did"] for r in s]),v)],[mean],ND,B=1500,seed=2)[:,0,0]
a,b=ci(iid); c_,d_=ci(cl); e,f_=ci(dcl)
print(f"  ALL SCORED 63d mean: iid width {b-a:.3f} | symbol-clustered {d_-c_:.3f} ({(d_-c_)/(b-a):.2f}x) | DATE-clustered {f_-e:.3f} ({(f_-e)/(b-a):.2f}x)")
