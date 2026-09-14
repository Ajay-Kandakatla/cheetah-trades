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
# WHAT THIS ONE IS: four end-to-end fundamentals variants on both lanes —
# primary (derived Q4 available at end_date+90d), derived Q4s dropped, strict
# filing_date < bar, and raw list position (what production's canslim actually
# feeds). RESULT: Lane 1's inversion holds in all four (-3.11 / -3.45 / -3.07 /
# -2.71 at 21d).
# ─────────────────────────────────────────────────────────────────────────────

import sys,pickle
sys.path.insert(0,"/app")
exec(open("/root/.cheetah/aud/core.py").read())
import numpy as np
px,fin=load()
ANCH={"SPY","QQQ","IWM"}
VAR={"primary(end+90d)":dict(rec=prep_fin(fin,"plus90"),align="period",strict=False),
     "drop derived Q4s":dict(rec=prep_fin(fin,"drop"),align="period",strict=False),
     "strict filed<bar":dict(rec=prep_fin(fin,"plus90"),align="period",strict=True),
     "raw list position":dict(rec=prep_fin(fin,"plus90"),align="raw",strict=False)}

# ---- LANE 1 headline under each variant ----
D=pickle.load(open("/root/.cheetah/aud/lane1.pkl","rb"))
print("=== LANE 1 sensitivity: A vs D, 21d median & win ===",flush=True)
for lbl,kw in VAR.items():
    rows=[]
    for r in D["rows"]+D["prows"]:
        rec=kw["rec"].get(r["sym"])
        if not rec: continue
        st=state_asof(rec,r["date"],align=kw["align"],strict=kw["strict"])
        if st is None: continue
        isEP = r in D["rows"] if False else ("i" in r and r.get("gap") is not None)
        rows.append((r["sym"], "EP" if r.get("gap") is not None else "NO", st["bonde_pass"], r["r"][21]))
    sid={}
    for s,_,_,_ in rows: sid.setdefault(s,len(sid))
    NS=len(sid)
    A=[(sid[s],v) for s,e,p,v in rows if e=="EP" and p and v is not None]
    Dd=[(sid[s],v) for s,e,p,v in rows if e=="NO" and not p and v is not None]
    B=[(sid[s],v) for s,e,p,v in rows if e=="EP" and not p and v is not None]
    ca=Cell([x[0] for x in A],[x[1] for x in A]); cd=Cell([x[0] for x in Dd],[x[1] for x in Dd])
    cb=Cell([x[0] for x in B],[x[1] for x in B])
    bs=boot([ca,cd,cb],[med,win],NS,B=500,seed=31)
    l,h=ci(bs[:,0,0]-bs[:,1,0]); l2,h2=ci(bs[:,0,1]-bs[:,1,1]); l3,h3=ci(bs[:,0,0]-bs[:,2,0])
    print(f"  {lbl:20s} nA={len(A):4d} A-D med {med(ca.v)-med(cd.v):+.2f}pp [{l:+.2f},{h:+.2f}] win {win(ca.v)-win(cd.v):+.2f}pp [{l2:+.2f},{h2:+.2f}] | A-B med {med(ca.v)-med(cb.v):+.2f}pp [{l3:+.2f},{h3:+.2f}]")

# ---- LANE 2 headline under each variant ----
cal=list(px["SPY"]["d"]); DATES=[cal[i] for i in range(0,len(cal),21)]
print("\n=== LANE 2 sensitivity: 21d & 63d, lift vs ALL SCORED ===",flush=True)
base_px={}
for s,P in px.items():
    if s in ANCH: continue
    base_px[s]=({dd:i for i,dd in enumerate(P["d"])},P["c"])
for lbl,kw in VAR.items():
    rec_all=kw["rec"]; recs_rows=[]
    for s,(pos,c) in base_px.items():
        rec=rec_all.get(s)
        if not rec: continue
        for dt in DATES:
            i=pos.get(dt)
            if i is None or i<60: continue
            st=state_asof(rec,dt,align=kw["align"],strict=kw["strict"])
            if st is None: continue
            r21=(c[i+21]-c[i])/c[i]*100 if i+21<len(c) and c[i]>0 else None
            r63=(c[i+63]-c[i])/c[i]*100 if i+63<len(c) and c[i]>0 else None
            recs_rows.append((s,dt,st["tier"],st["bonde_pass"],st["cleared_floor"],st["character"],r21,r63))
    sid={}
    for x in recs_rows: sid.setdefault(x[0],len(sid))
    NS=len(sid)
    print(f"  --- {lbl} (n={len(recs_rows)}) ---")
    for k,col in [(21,6),(63,7)]:
        def cc(f):
            s=[x for x in recs_rows if f(x) and x[col] is not None]
            return Cell([sid[x[0]] for x in s],[x[col] for x in s])
        base=cc(lambda x: True)
        sets={"strong+explosive":lambda x:x[2] in("strong","explosive"),
              "BONDE PASS":lambda x:x[3],
              "floorY_charN":lambda x:x[4] and not x[5]}
        cells=[base]+[cc(f) for f in sets.values()]
        bs=boot(cells,[med,mean,win],NS,B=400,seed=41+k)
        for j,nm in enumerate(sets,start=1):
            l,h=ci(bs[:,j,0]-bs[:,0,0]); l2,h2=ci(bs[:,j,1]-bs[:,0,1]); l3,h3=ci(bs[:,j,2]-bs[:,0,2])
            print(f"    h={k}d {nm:17s} n={len(cells[j].v):6d} med {med(cells[j].v)-med(base.v):+.2f} [{l:+.2f},{h:+.2f}] mean {mean(cells[j].v)-mean(base.v):+.2f} [{l2:+.2f},{h2:+.2f}] win {win(cells[j].v)-win(base.v):+.2f} [{l3:+.2f},{h3:+.2f}]")
