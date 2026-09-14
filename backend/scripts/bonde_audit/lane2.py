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
# WHAT THIS ONE IS: the sales-tier panel — 24 monthly cross-sections,
# 54,786 symbol-bars, forward 21d and 63d. RESULT: the >=100% and >=25% tiers
# beat the scored universe by a MEDIAN of +0.45pp and +0.37pp at 21 days and
# both CIs include zero; win rates level with the market.
# ─────────────────────────────────────────────────────────────────────────────

import sys,pickle,collections,time
sys.path.insert(0,"/app")
exec(open("/root/.cheetah/aud/core.py").read())
import numpy as np

px,fin=load()
recs=dict(period=prep_fin(fin,"plus90"), drop=prep_fin(fin,"drop"))
ANCH={"SPY","QQQ","IWM"}
cal=list(px["SPY"]["d"])
DATES=[cal[i] for i in range(0,len(cal),21)]
print("sample dates",len(DATES),DATES[0],DATES[-1],flush=True)
H=[21,63]

def build(align="period",derived="period",strict=False):
    rows=[]
    src=recs[derived]
    for s,P in px.items():
        if s in ANCH: continue
        d=P["d"]; c=P["c"]; v=P["v"]
        pos={dd:i for i,dd in enumerate(d)}
        rec=src.get(s)
        for dt in DATES:
            i=pos.get(dt)
            if i is None or i<60: continue
            r={}
            ok=True
            for k in H:
                r[k]=((c[i+k]-c[i])/c[i]*100.0) if i+k<len(c) and c[i]>0 else None
            st=state_asof(rec,dt,align=align,strict=strict) if rec else None
            rows.append(dict(sym=s,date=dt,price=float(c[i]),
                             dv=float(np.median(c[max(0,i-50):i]*v[max(0,i-50):i])),
                             mom=float((c[i]-c[i-126])/c[i-126]*100) if i>=126 and c[i-126]>0 else None,
                             r=r, st=st))
    return rows

t=time.time(); rows=build(); print("panel",len(rows),"syms",len(set(r['sym'] for r in rows)),round(time.time()-t,1),"s",flush=True)
sym_ids={}
def sid(s):
    if s not in sym_ids: sym_ids[s]=len(sym_ids)
    return sym_ids[s]
for r in rows: r["sid"]=sid(r["sym"])
NS=len(sym_ids)

scored=[r for r in rows if r["st"]]
print("scored bars",len(scored),"(%.1f%%)"%(100*len(scored)/len(rows)),"syms",len(set(r['sym'] for r in scored)),flush=True)
print("tier cells:",collections.Counter(r["st"]["tier"] for r in scored).most_common(),flush=True)
for t_ in ["explosive","strong","steady","weak","declining"]:
    ss=set(r["sym"] for r in scored if r["st"]["tier"]==t_); print("   ",t_,len(ss),"symbols")
print("stale days median %d p90 %d  >120d %.1f%%"%(
    np.median([r["st"]["stale_days"] for r in scored]),
    np.percentile([r["st"]["stale_days"] for r in scored],90),
    100*np.mean([r["st"]["stale_days"]>120 for r in scored])),flush=True)

def C(sel,k):
    s=[r for r in sel if r["r"][k] is not None]
    return Cell([r["sid"] for r in s],[r["r"][k] for r in s])

def report(name_cells,k,B=500,seed=1,pairs=()):
    names=[n for n,_ in name_cells]; cells=[c for _,c in name_cells]
    bs=boot(cells,[med,mean,win],NS,B=B,seed=seed)
    for i,n in enumerate(names):
        x=cells[i].v; lo,hi=ci(bs[:,i,1]); l3,h3=ci(bs[:,i,0])
        print(f"   {n:22s} n={len(x):6d} med {med(x):+6.2f}% [{l3:+.2f},{h3:+.2f}] mean {mean(x):+6.2f}% [{lo:+.2f},{hi:+.2f}] win {win(x):5.1f}%")
    for a,b in pairs:
        ia,ib=names.index(a),names.index(b)
        dmu=bs[:,ia,1]-bs[:,ib,1]; dw=bs[:,ia,2]-bs[:,ib,2]
        l,h=ci(dmu); l2,h2=ci(dw)
        print(f"     {a} - {b}: mean {mean(cells[ia].v)-mean(cells[ib].v):+.2f}pp [{l:+.2f},{h:+.2f}] | win {win(cells[ia].v)-win(cells[ib].v):+.2f}pp [{l2:+.2f},{h2:+.2f}]")
    return names,cells,bs

print("\n===== LANE 2: TIERS =====",flush=True)
for k in H:
    print(f"\n h={k}d")
    nc=[("ALL BARS",C(rows,k)),("ALL SCORED",C(scored,k))]
    for t_ in ["explosive","strong","steady","weak","declining"]:
        nc.append((t_,C([r for r in scored if r["st"]["tier"]==t_],k)))
    nc.append(("BONDE PASS",C([r for r in scored if r["st"]["bonde_pass"]],k)))
    pairs=[(t_,"ALL SCORED") for t_ in ["explosive","strong","steady","weak","declining"]]
    pairs+=[("explosive","ALL BARS"),("strong","ALL BARS"),("explosive","strong"),("strong","steady"),
            ("BONDE PASS","ALL BARS"),("BONDE PASS","ALL SCORED")]
    report(nc,k,B=500,seed=20+k,pairs=pairs)

print("\n===== 2x2 floor x character (scored only) =====",flush=True)
for k in H:
    print(f"\n h={k}d")
    q=lambda f,ch:[r for r in scored if r["st"]["cleared_floor"]==f and r["st"]["character"]==ch]
    nc=[("floorY_charY(PASS)",C(q(True,True),k)),("floorY_charN(REJECT)",C(q(True,False),k)),
        ("floorN_charY",C(q(False,True),k)),("floorN_charN",C(q(False,False),k)),
        ("ALL SCORED",C(scored,k))]
    report(nc,k,B=500,seed=40+k,pairs=[("floorY_charY(PASS)","floorY_charN(REJECT)")])
    # character clauses inside cleared-floor cohort
    fl=[r for r in scored if r["st"]["cleared_floor"]]
    for clause in ["accelerating","consec2","sales_led"]:
        f=(lambda r: bool(r["st"]["accelerating"])) if clause=="accelerating" else \
          (lambda r: int(r["st"]["consecutive_growth_q"] or 0)>=2) if clause=="consec2" else \
          (lambda r: bool(r["st"]["sales_led"]))
        nc2=[("YES",C([r for r in fl if f(r)],k)),("NO",C([r for r in fl if not f(r)],k))]
        nm,cs,bs=report(nc2,k,B=400,seed=60+k,pairs=[("YES","NO")])
        print(f"     ^ clause={clause}")

print("\n===== DATE-NEUTRAL check (each bar demeaned by its own cross-section) =====",flush=True)
for k in H:
    bydate=collections.defaultdict(list)
    for r in scored:
        if r["r"][k] is not None: bydate[r["date"]].append(r["r"][k])
    mu={d:np.mean(v) for d,v in bydate.items()}
    print(f" h={k}d (excess vs same-date all-scored mean)")
    nc=[]
    for t_ in ["explosive","strong","steady","weak","declining"]:
        s=[r for r in scored if r["st"]["tier"]==t_ and r["r"][k] is not None]
        nc.append((t_,Cell([r["sid"] for r in s],[r["r"][k]-mu[r["date"]] for r in s])))
    s=[r for r in scored if r["st"]["bonde_pass"] and r["r"][k] is not None]
    nc.append(("BONDE PASS",Cell([r["sid"] for r in s],[r["r"][k]-mu[r["date"]] for r in s])))
    bs=boot([c for _,c in nc],[mean],NS,B=500,seed=80+k)
    for i,(n,c) in enumerate(nc):
        l,h=ci(bs[:,i,0]); print(f"   {n:12s} excess mean {mean(c.v):+6.2f}pp [{l:+.2f},{h:+.2f}]  n={len(c.v)}")

print("\n===== MOMENTUM CONTROL: is the >=25%% lift just 6m price momentum? =====",flush=True)
for k in [21]:
    sm=[r for r in scored if r["mom"] is not None and r["r"][k] is not None]
    qs=np.percentile([r["mom"] for r in sm],[20,40,60,80])
    def bucket(r): return int(np.searchsorted(qs,r["mom"]))
    # within-bucket excess for strong+explosive
    ex=[]; exs=[]
    bmu={}
    for b in range(5):
        vals=[r["r"][k] for r in sm if bucket(r)==b]; bmu[b]=np.mean(vals)
    for r in sm:
        if r["st"]["tier"] in ("strong","explosive"):
            ex.append(r["r"][k]-bmu[bucket(r)]); exs.append(r["sid"])
    c=Cell(exs,ex); bs=boot([c],[mean],NS,B=500,seed=99)
    l,h=ci(bs[:,0,0])
    print(f"  strong+explosive excess vs SAME 6m-momentum quintile: {mean(c.v):+.2f}pp [{l:+.2f},{h:+.2f}] n={len(ex)}")
    # raw (uncontrolled) for comparison
    raw=[r["r"][k]-np.mean([q["r"][k] for q in sm]) for r in sm if r["st"]["tier"] in ("strong","explosive")]
    rs=[r["sid"] for r in sm if r["st"]["tier"] in ("strong","explosive")]
    c2=Cell(rs,raw); bs2=boot([c2],[mean],NS,B=500,seed=98); l2,h2=ci(bs2[:,0,0])
    print(f"  strong+explosive excess UNCONTROLLED:                  {mean(c2.v):+.2f}pp [{l2:+.2f},{h2:+.2f}]")
    # momentum quintile spread itself
    print("  6m-momentum quintile 21d means:", [round(bmu[b],2) for b in range(5)])
    # liquidity control
    lq=np.percentile([r["dv"] for r in sm],[20,40,60,80])
    lmu={}
    for b in range(5):
        vals=[r["r"][k] for r in sm if int(np.searchsorted(lq,r["dv"]))==b]; lmu[b]=np.mean(vals)
    ex3=[r["r"][k]-lmu[int(np.searchsorted(lq,r["dv"]))] for r in sm if r["st"]["tier"] in ("strong","explosive")]
    c3=Cell(rs,ex3); bs3=boot([c3],[mean],NS,B=500,seed=97); l3,h3=ci(bs3[:,0,0])
    print(f"  strong+explosive excess vs SAME dollar-volume quintile: {mean(c3.v):+.2f}pp [{l3:+.2f},{h3:+.2f}]")

print("\n===== CI CHECK: clustered vs iid, ALL-SCORED mean 21d =====",flush=True)
k=21
s=[r for r in scored if r["r"][k] is not None]
v=np.array([r["r"][k] for r in s]); sd=np.array([r["sid"] for r in s])
rng=np.random.default_rng(3)
iid=np.array([v[rng.integers(0,len(v),len(v))].mean() for _ in range(2000)])
uniq=np.unique(sd); remap={u:i for i,u in enumerate(uniq)}
sd2=np.array([remap[x] for x in sd])
cl=boot([Cell(sd2,v)],[mean],len(uniq),B=2000,seed=3)[:,0,0]
li,hi_=ci(iid); lc,hc=ci(cl)
print(f"  iid-over-bars    [{li:+.3f},{hi_:+.3f}] width {hi_-li:.3f}")
print(f"  symbol-clustered [{lc:+.3f},{hc:+.3f}] width {hc-lc:.3f}")
print(f"  clustered is {(hc-lc)/(hi_-li):.2f}x WIDER -> an iid CI overstates significance by that factor")
# same for the strong tier lift
st=[r for r in scored if r["st"]["tier"] in ("strong","explosive") and r["r"][k] is not None]
v2=np.array([r["r"][k] for r in st]); sd3=np.array([remap[r["sid"]] for r in st])
iid2=np.array([v2[rng.integers(0,len(v2),len(v2))].mean() for _ in range(2000)])
cl2=boot([Cell(sd3,v2)],[mean],len(uniq),B=2000,seed=4)[:,0,0]
a,b=ci(iid2); c_,d_=ci(cl2)
print(f"  strong+explosive mean: iid width {b-a:.3f} vs clustered {d_-c_:.3f} -> {(d_-c_)/(b-a):.2f}x")

pickle.dump(dict(n=len(rows)),open("/root/.cheetah/aud/l2done.pkl","wb"))
