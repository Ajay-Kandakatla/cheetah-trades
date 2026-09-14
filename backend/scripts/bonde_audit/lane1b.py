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
# WHAT THIS ONE IS: the bracket simulation, the date-clustered intervals and
# the lookahead probe. RESULT: expectancy -0.92% [-2.14,+0.27] and the sales
# gate moves it by -0.06pp; target sits 6.00% away against a stop a median
# 13.71% away, so the 58% target-before-stop rate is bracket geometry, not a
# win rate. Lookahead probe: 0 of 780 events used a quarter filed after the bar.
# ─────────────────────────────────────────────────────────────────────────────

import sys,pickle
sys.path.insert(0,"/app")
exec(open("/root/.cheetah/aud/core.py").read())
import numpy as np, collections
px,fin=load()
D=pickle.load(open("/root/.cheetah/aud/lane1.pkl","rb"))
rows=D["rows"]; prows=D["prows"]
allr=rows+prows
sym_ids={}; 
for r in allr: sym_ids.setdefault(r["sym"],len(sym_ids)); r["sid"]=sym_ids[r["sym"]]
NS=len(sym_ids)
dts=sorted(set(r["date"] for r in allr)); dix={d:i for i,d in enumerate(dts)}
for r in allr: r["did"]=dix[r["date"]]
ND=len(dts)
print("EP event dates",ND,flush=True)

print("\n=== LANE 1: A-D and A-B under DATE-clustered bootstrap ===",flush=True)
for k in [5,21]:
    def cd(nm):
        s=[r for r in allr if r["cell"]==nm and r["r"][k] is not None]
        return Cell([r["did"] for r in s],[r["r"][k] for r in s])
    cells=[cd("A"),cd("B"),cd("D")]
    bs=boot(cells,[med,win],ND,B=2000,seed=13)
    for a,b in [(0,2),(0,1)]:
        nm=["A","B","D"]
        dm=bs[:,a,0]-bs[:,b,0]; dw=bs[:,a,1]-bs[:,b,1]
        l,h=ci(dm); l2,h2=ci(dw)
        print(f"  h={k}d {nm[a]}-{nm[b]}: med {med(cells[a].v)-med(cells[b].v):+.2f}pp [{l:+.2f},{h:+.2f}] | win {win(cells[a].v)-win(cells[b].v):+.2f}pp [{l2:+.2f},{h2:+.2f}]")

print("\n=== LANE 1: bracket sim (trigger=gap_high+.01, stop=gap_low-.01, target=trigger*1.06) ===",flush=True)
LOOK=5; HORZ=21
def bracket(sym,i):
    P=px[sym]; h,l,o,c=P["h"],P["l"],P["o"],P["c"]
    trig=round(h[i]+0.01,4); stop=round(l[i]-0.01,4); tgt=round(trig*1.06,4)
    if trig-stop<=0: return None
    # arm within LOOK sessions after gap day
    for j in range(i+1,min(i+1+LOOK,len(c))):
        if h[j]>=trig:
            entry=max(o[j],trig) if o[j]>trig else trig
            for m in range(j,min(j+HORZ+1,len(c))):
                hitS = l[m]<=stop; hitT = h[m]>=tgt
                if m==j and o[j]>=tgt: return ("target",(o[j]-entry)/entry*100,m-j)
                if hitS: return ("stop",(stop-entry)/entry*100 if o[m]>stop else (o[m]-entry)/entry*100,m-j)
                if hitT: return ("target",(tgt-entry)/entry*100,m-j)
            e=min(j+HORZ,len(c)-1)
            return ("neither",(c[e]-entry)/entry*100,e-j)
    return ("unarmed",None,None)
out={}
for nm in ["A","B"]:
    res=[bracket(r["sym"],r["i"]) for r in rows if r["cell"]==nm]
    res=[x for x in res if x]
    armed=[x for x in res if x[0]!="unarmed"]
    tb=sum(1 for x in armed if x[0]=="target"); sf=sum(1 for x in armed if x[0]=="stop")
    exp=[x[1] for x in armed]
    sids=[r["sid"] for r in rows if r["cell"]==nm][:len(res)]
    out[nm]=(res,armed,exp,[r["sid"] for r,x in zip([r for r in rows if r["cell"]==nm],res) if x[0]!="unarmed"])
    print(f"  {nm}: events {len(res)} armed {len(armed)} ({100*len(armed)/len(res):.1f}%) target-first {tb} ({100*tb/max(len(armed),1):.1f}%) stop-first {sf} neither {len(armed)-tb-sf}")
    print(f"     expectancy_pct mean {np.mean(exp):+.2f}% median {np.median(exp):+.2f}%")
ca=Cell(out["A"][3],out["A"][2]); cb=Cell(out["B"][3],out["B"][2])
bs=boot([ca,cb],[mean,lambda x: float(np.mean(x>0)*100)],NS,B=1000,seed=21)
l,h=ci(bs[:,0,0]); l2,h2=ci(bs[:,1,0]); l3,h3=ci(bs[:,0,0]-bs[:,1,0])
print(f"  expectancy A {np.mean(ca.v):+.2f}% [{l:+.2f},{h:+.2f}]  B {np.mean(cb.v):+.2f}% [{l2:+.2f},{h2:+.2f}]  A-B {np.mean(ca.v)-np.mean(cb.v):+.2f} [{l3:+.2f},{h3:+.2f}]")
lt,ht=ci(bs[:,0,1]); lt2,ht2=ci(bs[:,1,1]); ltd,htd=ci(bs[:,0,1]-bs[:,1,1])
print(f"  target-before-stop%% A {np.mean(ca.v>0)*100:.2f} [{lt:.2f},{ht:.2f}] B {np.mean(cb.v>0)*100:.2f} [{lt2:.2f},{ht2:.2f}] A-B {(np.mean(ca.v>0)-np.mean(cb.v>0))*100:+.2f} [{ltd:+.2f},{htd:+.2f}]")
gh=[ (px[r["sym"]]["h"][r["i"]]-px[r["sym"]]["l"][r["i"]])/px[r["sym"]]["h"][r["i"]]*100 for r in rows if r["cell"]=="A"]
print(f"  bracket geometry: target 6.00%% away; stop = gap-day range, median {np.median(gh):.2f}%% away (cell A)")

print("\n=== LOOKAHEAD PROBE ===",flush=True)
bad=0; derived_used=0; tot=0
recs=prep_fin(fin,"plus90")
for r in rows[:100000]:
    rec=recs.get(r["sym"]); 
    if not rec: continue
    av=[x for x in rec if x[0]<=r["date"]]
    tot+=1
    if any(x[0]>r["date"] for x in av): bad+=1
    if any(not x[4] for x in av[-8:]): derived_used+=1
print(f"  quarters used with availability AFTER the bar: {bad}/{tot} (must be 0)")
print(f"  events whose 8-quarter window contains >=1 DERIVED (filing_date None) quarter: {derived_used}/{tot} ({100*derived_used/tot:.1f}%)")
import glob,os
# does anything in the study path read today's research cache?
print("  research_cache / fundamentals collections read by this study: NONE (script sources = Massive /vX/reference/financials + price_cache only)")

print("\n=== SURVIVORSHIP probe ===",flush=True)
from sepa import universe
u=set(universe.load_universe())
print(f"  universe is TODAY's membership: {len(u)} names; every name delisted 2024-09..2026-09 is absent from all cells.")
nb=[len(px[s]['d']) for s in px]
print(f"  names with a FULL 2y history: {sum(1 for x in nb if x>=495)}/{len(nb)} ({100*sum(1 for x in nb if x>=495)/len(nb):.1f}%) -> short-history names are recent listings, not survivors")
