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
# WHAT THIS ONE IS: validates the reconstructed Episodic Pivot rule against
# the 63 stored `setups` docs (field is `kind`, not `setup_type`). 62 of 63
# reproduce; FBRX disagrees on a price-adjustment artifact. The stored docs are
# used ONLY as an oracle for the rule — they are all status=expired and are not
# a track record of anything.
# ─────────────────────────────────────────────────────────────────────────────

import sys,os,pickle,collections
sys.path.insert(0,"/app")
import numpy as np
from pymongo import MongoClient
px=pickle.load(open("/root/.cheetah/audit_px_v1.pkl","rb"))
mc=MongoClient(os.getenv("MONGO_URL") or "mongodb://mongo:27017")
db=mc[os.getenv("MONGO_DB") or "cheetah"]
docs=list(db.setups.find({"kind":"episodic_pivot"}))
print("stored EP docs",len(docs))
print("statuses",collections.Counter(d.get("status") for d in docs))
print("dates",min(d.get("date_et","") for d in docs),max(d.get("date_et","") for d in docs))
print("dupes",collections.Counter(d["symbol"] for d in docs).most_common(5))
AVGW=50
rep=0;tot=0;miss=[]
for d in docs:
    s=d["symbol"]; m=d.get("meta") or {}; gh=m.get("gap_day_high")
    if gh is None: miss.append((s,"nogh")); continue
    P=px.get(s)
    if P is None:
        from sepa import prices
        df=prices.load_prices(s)
        if df is None: miss.append((s,"nobars")); continue
        P=dict(o=df["open"].to_numpy(float),c=df["close"].to_numpy(float),
               h=df["high"].to_numpy(float),v=df["volume"].to_numpy(float))
    tot+=1
    j=int(np.argmin(np.abs(P["h"]-gh)))
    if abs(P["h"][j]-gh)/max(gh,1e-9)>0.005: miss.append((s,"nomatchbar",gh)); continue
    if j<AVGW+1: miss.append((s,"early")); continue
    av=P["v"][j-AVGW:j].mean()
    g=(P["o"][j]-P["c"][j-1])/P["c"][j-1]*100; vm=P["v"][j]/av if av>0 else 0
    if g>=8.0 and vm>=5.0: rep+=1
    else: miss.append((s,round(g,1),round(vm,1),m.get("gap_pct"),m.get("vol_mult")))
print(f"ORACLE reproduced {rep}/{tot}")
for x in miss: print("  miss",x)
