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
# WHAT THIS ONE IS: shared loaders, the point-in-time Bonde sales state
# (availability = filing_date; derived Q4s get end_date+90d), and the clustered
# percentile bootstrap. Every other script execs this file.
# ─────────────────────────────────────────────────────────────────────────────

"""Independent audit core: shared loaders, as-of Bonde sales state, clustered bootstrap."""
import os, sys, json, gzip, pickle, math
sys.path.insert(0,"/app")
import numpy as np
from datetime import date, timedelta
from sepa import sales as sales_mod
from sepa.sales import SALES_FLOOR_PCT, SALES_PREFERRED_PCT

PX  = "/root/.cheetah/audit_px_v1.pkl"
FIN = "/root/.cheetah/audit_fin_v1.json.gz"

def load():
    px = pickle.load(open(PX,"rb"))
    fin = json.loads(gzip.open(FIN,"rt").read())
    return px, fin

def d2i(s):
    return date(int(s[:4]),int(s[5:7]),int(s[8:10]))

def prep_fin(fin, derived="plus90"):
    """Per symbol: list of (avail_date_iso, period_index, rev, eps) sorted by avail.
    derived: 'plus90' -> filed=None rows get end_date+90d; 'drop' -> excluded."""
    out={}
    for s,v in fin.items():
        rows=v.get("q")
        if not rows: continue
        rec=[]
        for q in rows:
            fy,fp = q.get("fy"), str(q.get("fp") or "").upper().strip()
            if not fp.startswith("Q"): continue
            try:
                qq=int(fp[1:])
                if not 1<=qq<=4: continue
                p=int(fy)*4+(qq-1)
            except (TypeError,ValueError): continue
            filed=q.get("filed")
            if filed:
                avail=filed
            else:
                if derived=="drop": continue
                e=q.get("end")
                if not e: continue
                avail=(d2i(e)+timedelta(days=90)).isoformat()
            rec.append((avail,p,q.get("rev"),q.get("eps"),bool(filed)))
        if rec:
            rec.sort(key=lambda r:r[0])
            out[s]=rec
    return out

def state_asof(rec, asof_iso, align="period", strict=False, n=8):
    """Bonde sales state from quarters available at asof. Returns dict or None."""
    if strict:
        av=[r for r in rec if r[0] < asof_iso]
    else:
        av=[r for r in rec if r[0] <= asof_iso]
    if len(av) < 5: return None
    if align=="period":
        # newest period among available; densify backwards by period index
        best={}
        for a,p,rev,eps,f in av:
            if p not in best or a > best[p][0]: best[p]=(a,rev,eps)
        p0=max(best)
        revs=[ (best[p0-j][1] if (p0-j) in best else None) for j in range(n)]
        epss=[ (best[p0-j][2] if (p0-j) in best else None) for j in range(n)]
        newest_avail=best[p0][0]
    else:  # raw list position, newest-by-availability first (what canslim feeds)
        av2=sorted(av, key=lambda r:r[0], reverse=True)[:n]
        revs=[r[2] for r in av2]; epss=[r[3] for r in av2]
        newest_avail=av2[0][0]
    eg=None
    if len(epss)>=5 and epss[0] is not None and epss[4] not in (None,0):
        eg=round((epss[0]-epss[4])/abs(epss[4])*100,2)
    st=sales_mod.compute(revs, eg)
    if st.get("score") is None: return None
    g=st["growth_yoy_pct"]
    cleared = bool(g is not None and g >= SALES_FLOOR_PCT)      # ROUNDED, as _bonde_pillar does
    character = bool(st["accelerating"]) or int(st["consecutive_growth_q"] or 0) >= 2
    st["cleared_floor"]=cleared; st["character"]=character
    st["bonde_pass"]= bool(cleared and character)
    st["stale_days"]=(d2i(asof_iso)-d2i(newest_avail)).days
    return st

# ---------------- clustered bootstrap ----------------
class Cell:
    """values grouped by symbol cluster."""
    def __init__(self, sym_ids, vals):
        self.sym=np.asarray(sym_ids,dtype=np.int64); self.v=np.asarray(vals,dtype=float)
    def __len__(self): return len(self.v)

def build_index(cells, nsym):
    """per-cell: list of index arrays by symbol id."""
    idx=[]
    for c in cells:
        order=np.argsort(c.sym,kind="stable")
        s=c.sym[order]; vv=c.v[order]
        bounds=np.searchsorted(s, np.arange(nsym+1))
        idx.append((vv,bounds))
    return idx

def boot(cells, stats, nsym, B=1000, seed=7):
    """cells: list of Cell. stats: list of fn(np.array)->float.
    Returns array [B, ncell, nstat] using the SAME symbol resample per replicate."""
    rng=np.random.default_rng(seed)
    prep=build_index(cells,nsym)
    out=np.full((B,len(cells),len(stats)), np.nan)
    for b in range(B):
        draw=rng.integers(0,nsym,nsym)
        for ci,(vv,bounds) in enumerate(prep):
            lens=bounds[draw+1]-bounds[draw]
            tot=int(lens.sum())
            if tot==0: continue
            starts=bounds[draw]
            # build flat index
            ii=np.repeat(starts, lens) + (np.arange(tot) - np.repeat(np.cumsum(lens)-lens, lens))
            x=vv[ii]
            for si,f in enumerate(stats):
                out[b,ci,si]=f(x)
    return out

def ci(arr):
    a=arr[~np.isnan(arr)]
    if len(a)==0: return (float('nan'),float('nan'))
    return float(np.percentile(a,2.5)), float(np.percentile(a,97.5))

def med(x): return float(np.median(x)) if len(x) else float('nan')
def mean(x): return float(np.mean(x)) if len(x) else float('nan')
def win(x): return float(np.mean(x>0)*100) if len(x) else float('nan')

def fmt(pt, lo, hi, u="%"):
    return f"{pt:+.2f}{u} [{lo:+.2f},{hi:+.2f}]"
