"""Sequential QoQ vs quarterly-YoY on Ajay's own breakout board.

QUESTION: he asked to "prioritize income and growth only quarter over quarter".
Sequential QoQ (Q0 vs Q1) is a different number from the quarterly YoY the board
prints today (Q0 vs Q4). Minervini uses YoY specifically to kill seasonality.
Before choosing a ranking key, measure on HIS names:
  1. coverage — can we even fill sequential QoQ?
  2. agreement — do the two orderings pick the same leaders?
  3. seasonality — does sequential QoQ just rank by calendar quarter?
"""
import json, statistics as st
from collections import defaultdict

from sepa import breakout as B
from sepa import canslim

N = 80

b = B.board(top=250, stages=False)
syms = [r["symbol"] for r in b["rows"]][:N]
print(f"sampling {len(syms)} of {len(b['rows'])} board names", flush=True)

def pct(cur, prev):
    if cur is None or prev is None or prev == 0:
        return None
    return (cur - prev) / abs(prev) * 100

rows = []
for i, s in enumerate(syms):
    try:
        m = canslim._fetch_massive_financials(s)
    except Exception as exc:
        m = None
    if not m:
        rows.append({"symbol": s, "ok": False})
        continue
    rev = m.get("rev_q_series") or []
    eps = m.get("eps_q_series") or []
    ni  = m.get("ni_q_series") or []
    rows.append({
        "symbol": s, "ok": True,
        "rev_qoq": pct(rev[0] if len(rev) > 0 else None, rev[1] if len(rev) > 1 else None),
        "eps_qoq": pct(eps[0] if len(eps) > 0 else None, eps[1] if len(eps) > 1 else None),
        "ni_qoq":  pct(ni[0] if len(ni) > 0 else None,  ni[1] if len(ni) > 1 else None),
        "rev_yoy": m.get("rev_growth_q_pct"),
        "eps_yoy": m.get("q_eps_growth_pct"),
        "n_rev": len([v for v in rev if v is not None]),
        "n_eps": len([v for v in eps if v is not None]),
        "eps_base_neg": bool(len(eps) > 1 and eps[1] is not None and eps[1] < 0),
        "rev_series": rev[:6], "eps_series": eps[:6],
    })
    if (i + 1) % 20 == 0:
        print(f"  ...{i+1}", flush=True)

try:
    json.dump(rows, open("/tmp/qoq_out.json", "w"), default=str)
except Exception as exc:
    print("dump skipped:", exc)

live = [r for r in rows if r.get("ok")]
print("\nCOVERAGE")
print(f"  fetched            {len(live)}/{len(rows)}")
for k in ("rev_qoq", "eps_qoq", "ni_qoq", "rev_yoy", "eps_yoy"):
    print(f"  {k:9s} filled  {sum(1 for r in live if r.get(k) is not None)}/{len(rows)}")
print(f"  eps prior-Q NEGATIVE (division base flips meaning): "
      f"{sum(1 for r in live if r.get('eps_base_neg'))}")

def rank(key):
    xs = [r for r in live if r.get(key) is not None]
    xs.sort(key=lambda r: -r[key])
    return [r["symbol"] for r in xs]

def spearman(a, b):
    common = [s for s in a if s in b]
    if len(common) < 5:
        return None
    ra = {s: i for i, s in enumerate(a)}
    rb = {s: i for i, s in enumerate(b)}
    n = len(common)
    d2 = sum((ra[s] - rb[s]) ** 2 for s in common)
    return 1 - 6 * d2 / (n * (n * n - 1))

print("\nAGREEMENT (Spearman on the shared names)")
print(f"  rev_qoq vs rev_yoy  {spearman(rank('rev_qoq'), rank('rev_yoy'))}")
print(f"  eps_qoq vs eps_yoy  {spearman(rank('eps_qoq'), rank('eps_yoy'))}")

print("\nTOP 12 BY SEQUENTIAL REV QoQ  (and where YoY ranks them)")
ry = rank("rev_yoy")
for s in rank("rev_qoq")[:12]:
    r = next(x for x in live if x["symbol"] == s)
    pos = ry.index(s) + 1 if s in ry else None
    print(f"  {s:6s} qoq {r['rev_qoq']:8.1f}%   yoy {str(r['rev_yoy']):>8}   yoy-rank {pos}")

print("\nTOP 12 BY QUARTERLY YoY REV  (and where sequential ranks them)")
rq = rank("rev_qoq")
for s in ry[:12]:
    r = next(x for x in live if x["symbol"] == s)
    pos = rq.index(s) + 1 if s in rq else None
    print(f"  {s:6s} yoy {r['rev_yoy']:8.1f}%   qoq {str(round(r['rev_qoq'],1) if r['rev_qoq'] is not None else None):>8}   qoq-rank {pos}")

seq = [r["rev_qoq"] for r in live if r.get("rev_qoq") is not None]
yo  = [r["rev_yoy"] for r in live if r.get("rev_yoy") is not None]
print("\nDISPERSION")
if seq:
    print(f"  rev_qoq  median {st.median(seq):7.1f}%  neg {sum(1 for v in seq if v<0)}/{len(seq)}")
if yo:
    print(f"  rev_yoy  median {st.median(yo):7.1f}%  neg {sum(1 for v in yo if v<0)}/{len(yo)}")
