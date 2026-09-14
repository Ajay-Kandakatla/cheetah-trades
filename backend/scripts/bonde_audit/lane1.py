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
# WHAT THIS ONE IS: the headline. Episodic Pivots reconstructed bar by bar
# (gap >= 8% on >= 5x 50-day volume, deduped to one per symbol per 5 sessions),
# split by the as-of Bonde sales state, against a date-matched placebo.
# RESULT: 780 classifiable EPs; the 376 that ALSO passed his sales gate ran a
# 21-day median -3.22% (win 39.8%) against -0.11% (49.6%) for date-matched
# non-EP names — a lift of -3.11pp, 95% CI -5.28 to -1.16. INVERTED.
# ─────────────────────────────────────────────────────────────────────────────

import sys, json, pickle, time
sys.path.insert(0,"/app")
sys.path.insert(0,"/root/.cheetah/aud")
exec(open("/root/.cheetah/aud/core.py").read())
import numpy as np

MIN_GAP=8.0; MIN_VOL=5.0; AVGW=50; DEDUP=5
HOR=[3,5,10,21]
px,fin=load()
px.pop("SPY",None) if False else None
ANCH={"SPY","QQQ","IWM"}
recs=prep_fin(fin,"plus90")
recs_drop=prep_fin(fin,"drop")

# ---------- 1. reconstruct EP events from bars ----------
events=[]   # (sym, date_iso, i)
for s,P in px.items():
    if s in ANCH: continue
    o,c,v,d=P["o"],P["c"],P["v"],P["d"]
    n=len(c)
    if n<AVGW+2: continue
    # rolling mean of prior 50 vols, trailing, EXCLUDING bar i
    cs=np.concatenate([[0.0],np.cumsum(v)])
    last=-99
    for i in range(AVGW+1,n):
        if i-last<DEDUP: continue
        av=(cs[i]-cs[i-AVGW])/AVGW
        if av<=0: continue
        pc=c[i-1]
        if pc<=0: continue
        if (o[i]-pc)/pc*100.0 >= MIN_GAP and v[i]/av >= MIN_VOL:
            events.append((s,d[i],i)); last=i
print("EP events", len(events), "symbols", len(set(e[0] for e in events)), flush=True)

# ---------- 2. oracle check vs stored setups docs ----------
import os
from pymongo import MongoClient
mc=MongoClient(os.getenv("MONGO_URL") or "mongodb://mongo:27017")
db=mc[os.getenv("MONGO_DB") or "cheetah"]
docs=list(db.setups.find({"setup_type":"episodic_pivot"}))
print("stored EP docs", len(docs), "statuses", {})
repro=0; tot=0; miss=[]
for doc in docs:
    sym=doc.get("symbol"); meta=doc.get("meta") or {}
    gh=meta.get("gap_day_high")
    if sym not in px or gh is None: miss.append((sym,"nobars")); continue
    tot+=1
    P=px[sym]; hi=P["h"]
    j=int(np.argmin(np.abs(hi-gh)))
    if abs(hi[j]-gh)/max(gh,1e-9) > 0.005: miss.append((sym,"nobar_match")); continue
    o,c,v=P["o"],P["c"],P["v"]
    if j<AVGW+1: miss.append((sym,"tooearly")); continue
    av=v[j-AVGW:j].mean()
    g=(o[j]-c[j-1])/c[j-1]*100.0; vm=v[j]/av if av>0 else 0
    if g>=MIN_GAP and vm>=MIN_VOL: repro+=1
    else: miss.append((sym,f"g={g:.1f} vm={vm:.1f}"))
print(f"ORACLE: reproduced {repro}/{tot} stored EP docs; misses={miss[:8]}", flush=True)

# ---------- 3. forward returns + classification ----------
def fwd(P,i,k):
    e=i+1
    if e+k>=len(P["c"]): return None
    a=P["c"][e]; b=P["c"][e+k]
    if a<=0: return None
    return (b-a)/a*100.0

def fwd_open(P,i,k):
    e=i+1
    if e+k>=len(P["c"]): return None
    a=P["o"][e]; b=P["c"][e+k]
    if a<=0: return None
    return (b-a)/a*100.0

sym_ids={}
def sid(s):
    if s not in sym_ids: sym_ids[s]=len(sym_ids)
    return sym_ids[s]

rows=[]  # dict per event
unclass=0; reason_few=0; reason_nofin=0
for s,dt,i in events:
    rec=recs.get(s)
    if not rec:
        unclass+=1; reason_nofin+=1; continue
    st=state_asof(rec,dt)
    if st is None:
        unclass+=1; reason_few+=1; continue
    P=px[s]
    rows.append(dict(sym=s,date=dt,i=i,cell="A" if st["bonde_pass"] else "B",
                     tier=st["tier"],g=st["growth_yoy_pct"],stale=st["stale_days"],
                     cleared=st["cleared_floor"],char=st["character"],
                     r={k:fwd(P,i,k) for k in HOR},
                     ro={k:fwd_open(P,i,k) for k in HOR},
                     px=float(P["c"][i+1]) if i+1<len(P["c"]) else float('nan'),
                     dv=float(np.median(P["c"][max(0,i-50):i]*P["v"][max(0,i-50):i])),
                     gap=(P["o"][i]-P["c"][i-1])/P["c"][i-1]*100,
                     vm=P["v"][i]/P["v"][i-AVGW:i].mean()))
print("classified",len(rows),"unclassified",unclass,"(few quarters",reason_few,", no fin",reason_nofin,")",flush=True)
nA=sum(1 for r in rows if r["cell"]=="A"); nB=len(rows)-nA
print("A",nA,"symbols",len(set(r['sym'] for r in rows if r['cell']=='A')),
      "B",nB,"symbols",len(set(r['sym'] for r in rows if r['cell']=='B')),flush=True)

# ---------- 4. placebo, date-matched ----------
rng=np.random.default_rng(11)
pool=sorted([s for s in px if s not in ANCH])
pool=[pool[k] for k in rng.choice(len(pool),700,replace=False)]
ev_by_sym={}
for s,dt,i in events: ev_by_sym.setdefault(s,[]).append(i)
dateidx={s:{d:k for k,d in enumerate(px[s]["d"])} for s in pool}
A_dates=set(r["date"] for r in rows if r["cell"]=="A")
prows=[]
for s,dt,i in events:
    cand=[]
    tries=0
    while len(cand)<3 and tries<40:
        tries+=1
        t=pool[rng.integers(0,len(pool))]
        if t==s or t in [c[0] for c in cand]: continue
        j=dateidx[t].get(dt)
        if j is None or j<AVGW+1: continue
        if any(abs(j-e)<=21 for e in ev_by_sym.get(t,[])): continue
        cand.append((t,j))
    for t,j in cand:
        rec=recs.get(t)
        st=state_asof(rec,dt) if rec else None
        if st is None: continue
        P=px[t]
        prows.append(dict(sym=t,date=dt,i=j,cell="C" if st["bonde_pass"] else "D",
                          r={k:fwd(P,j,k) for k in HOR},
                          ro={k:fwd_open(P,j,k) for k in HOR},
                          on_A_date=dt in A_dates))
print("placebo draws",len(prows),"C",sum(1 for p in prows if p['cell']=='C'),
      "D",sum(1 for p in prows if p['cell']=='D'),flush=True)

pickle.dump(dict(rows=rows,prows=prows,events=events),open("/root/.cheetah/aud/lane1.pkl","wb"))

# ---------- 5. stats ----------
allrows=rows+prows
for r in allrows: r["sid"]=sid(r["sym"])
NS=len(sym_ids)
print("clusters (symbols)",NS,flush=True)

def cell_of(r, name):
    if name=="Da": return r["cell"]=="D" and r.get("on_A_date")
    return r["cell"]==name
NAMES=["A","B","C","D","Da"]
print("\n=== LANE 1 forward close-to-close (median / mean / win%), symbol-clustered 95% CI ===",flush=True)
res={}
for k in HOR:
    cells=[]; 
    for nm in NAMES:
        sel=[r for r in allrows if cell_of(r,nm) and r["r"][k] is not None]
        cells.append(Cell([r["sid"] for r in sel],[r["r"][k] for r in sel]))
    bs=boot(cells,[med,mean,win],NS,B=600,seed=100+k)
    print(f"\n h={k}d")
    for ci_,nm in enumerate(NAMES):
        x=cells[ci_].v
        lo,hi=ci(bs[:,ci_,0]); lo2,hi2=ci(bs[:,ci_,1]); lo3,hi3=ci(bs[:,ci_,2])
        print(f"  {nm:3s} n={len(x):5d} med {med(x):+6.2f}% [{lo:+.2f},{hi:+.2f}]  mean {mean(x):+6.2f}% [{lo2:+.2f},{hi2:+.2f}]  win {win(x):5.1f}% [{lo3:.1f},{hi3:.1f}]")
    pairs=[("A","B"),("A","C"),("A","D"),("A","Da"),("C","D"),("B","D")]
    for a,b in pairs:
        ia,ib=NAMES.index(a),NAMES.index(b)
        dm=bs[:,ia,0]-bs[:,ib,0]; dw=bs[:,ia,2]-bs[:,ib,2]; dmu=bs[:,ia,1]-bs[:,ib,1]
        pm=med(cells[ia].v)-med(cells[ib].v); pw=win(cells[ia].v)-win(cells[ib].v)
        pmu=mean(cells[ia].v)-mean(cells[ib].v)
        l1,h1=ci(dm); l2,h2=ci(dw); l3,h3=ci(dmu)
        print(f"   {a}-{b}: med {pm:+.2f}pp [{l1:+.2f},{h1:+.2f}] | mean {pmu:+.2f}pp [{l3:+.2f},{h3:+.2f}] | win {pw:+.2f}pp [{l2:+.2f},{h2:+.2f}]")
    res[k]=(cells,bs)

# ---------- 6. iid vs clustered CI on cell A @21d ----------
k=21
selA=[r for r in allrows if r["cell"]=="A" and r["r"][k] is not None]
vA=np.array([r["r"][k] for r in selA]); sA=np.array([r["sid"] for r in selA])
rng2=np.random.default_rng(5)
iid=np.array([np.median(vA[rng2.integers(0,len(vA),len(vA))]) for _ in range(2000)])
cl=boot([Cell(sA,vA)],[med],NS,B=2000,seed=5)[:,0,0]
li,hi_=ci(iid); lc,hc=ci(cl)
print(f"\n=== CI CHECK cell A 21d median ===")
print(f"  iid-over-events  95% CI [{li:+.2f},{hi_:+.2f}] width {hi_-li:.2f}")
print(f"  symbol-clustered 95% CI [{lc:+.2f},{hc:+.2f}] width {hc-lc:.2f}")
print(f"  clustered/iid width ratio = {(hc-lc)/(hi_-li):.2f}x  (iid is {(hc-lc)/(hi_-li):.2f}x too tight)")

# ---------- 7. entry at open robustness ----------
print("\n=== robustness: entry at OPEN of bar i+1 ===",flush=True)
for k in [5,21]:
    cells=[]
    for nm in ["A","D"]:
        sel=[r for r in allrows if cell_of(r,nm) and r["ro"][k] is not None]
        cells.append(Cell([r["sid"] for r in sel],[r["ro"][k] for r in sel]))
    bs=boot(cells,[med],NS,B=400,seed=300+k)
    d=bs[:,0,0]-bs[:,1,0]; l,h=ci(d)
    print(f"  h={k}d A-D med {med(cells[0].v)-med(cells[1].v):+.2f}pp [{l:+.2f},{h:+.2f}]")

# ---------- 8. sensitivities on classification ----------
print("\n=== classification sensitivities ===",flush=True)
for label,kw in [("drop derived Q4s",dict(rec=recs_drop)),("strict filed<gap",dict(strict=True)),
                 ("raw list position",dict(align="raw"))]:
    flips=0; nn=0
    for r in rows:
        rec = kw.get("rec",{}).get(r["sym"]) if "rec" in kw else recs.get(r["sym"])
        if not rec: continue
        st=state_asof(rec,r["date"],align=kw.get("align","period"),strict=kw.get("strict",False))
        if st is None: continue
        nn+=1
        if ("A" if st["bonde_pass"] else "B")!=r["cell"]: flips+=1
    print(f"  {label}: {flips}/{nn} flip ({100*flips/max(nn,1):.1f}%)")
fresh=sum(1 for r in rows if r["stale"]<=45)
print(f"  events judged on a quarter filed within 45d of the gap: {fresh}/{len(rows)} ({100*fresh/len(rows):.1f}%)")
import collections
print("  tier mix:",collections.Counter((("pass" if r["cell"]=="A" else "fail")+"/"+r["tier"]) for r in rows).most_common())
print("  A median gap %.1f%% vol %.1fx entry $%.2f 50d$vol $%.1fM sales %+.1f%%"%(
    np.median([r["gap"] for r in rows if r["cell"]=="A"]),np.median([r["vm"] for r in rows if r["cell"]=="A"]),
    np.median([r["px"] for r in rows if r["cell"]=="A"]),np.median([r["dv"] for r in rows if r["cell"]=="A"])/1e6,
    np.median([r["g"] for r in rows if r["cell"]=="A"])))
print("  B median gap %.1f%% vol %.1fx entry $%.2f 50d$vol $%.1fM sales %+.1f%%"%(
    np.median([r["gap"] for r in rows if r["cell"]=="B"]),np.median([r["vm"] for r in rows if r["cell"]=="B"]),
    np.median([r["px"] for r in rows if r["cell"]=="B"]),np.median([r["dv"] for r in rows if r["cell"]=="B"])/1e6,
    np.median([r["g"] for r in rows if r["cell"]=="B"])))
