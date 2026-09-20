# ─────────────────────────────────────────────────────────────────────────────
# Bonde board — the EP RE-MEASURE at his PUBLISHED numbers. Written 2026-09-20.
#
# Ajay, 2026-09-20 (his-call #5): "RE-MEASURE the Episodic Pivot at Bonde's
# published numbers before any gate talk."
#
# The 2026-09-13 audit (lane1.py) reconstructed EPs at the SHIPPED detector's
# thresholds — 8% gap on 5x volume — which are OURS. Bonde's published entry is
# `c/c1>1.04 and v>3*avgv50.1 and v>=300000`: a CLOSE/close move, looser, with a
# share floor. This script runs BOTH, plus the "4% gap" paraphrase as a named
# sensitivity, over the SAME cached panel, the SAME seeded date-matched placebo
# and the SAME clustered bootstrap, so the difference is a number.
#
# NOTHING IS CHANGED BY THIS SCRIPT (Rule #10). No gate, no threshold, no
# detector. The rules live in ep_rules.py; `shipped()` imports the app's own
# constants. Whether any number here reaches a surface is Ajay's call.
#
# Run inside the api container only — the Massive key and the caches live there:
#
#   cd /Users/ajay/clinet-test/cheetah-market-app
#   docker compose exec -T api mkdir -p /root/.cheetah/aud
#   docker compose cp backend/scripts/bonde_audit/core.py api:/root/.cheetah/aud/core.py
#   docker compose cp backend/scripts/bonde_audit/ep_rules.py api:/root/.cheetah/aud/ep_rules.py
#   docker compose exec -T api python - < backend/scripts/bonde_audit/lane1_published.py
#
# Heredoc/stdin, never `python /tmp/x.py`. Requires the caches lane1.py built
# (/root/.cheetah/audit_px_v1.pkl, audit_fin_v1.json.gz) — run fetch.py first if
# they are gone (~80s). Outside RTH (09:30-16:00 ET).
# ─────────────────────────────────────────────────────────────────────────────
#
# WHAT THIS ONE IS: three EP entry rules x {rule alone, rule x Bonde's sales
# gate} vs the date-matched placebo, 3/5/10/21-day forward closes, symbol- AND
# date-clustered 95% CIs. Writes /root/.cheetah/aud/lane1_published.json.
#
# REPRODUCTION GATE: the `shipped` rule must reproduce lane1.py's published
# headline on this panel (780 classified events, A n=376, 21d lift -3.11pp, CI
# -5.28..-1.16). If it does not, the panel moved and the comparison below is on
# DIFFERENT data — the script says so loudly and the doc must repeat it.
# ─────────────────────────────────────────────────────────────────────────────

import importlib.util
import json
import pickle
import sys

sys.path.insert(0, "/app")
sys.path.insert(0, "/root/.cheetah/aud")
exec(open("/root/.cheetah/aud/core.py").read())          # noqa: S102 — the sibling idiom
import numpy as np

# ep_rules.py is PURE and is loaded by path (the tests load it the same way).
_spec = importlib.util.spec_from_file_location("ep_rules", "/root/.cheetah/aud/ep_rules.py")
ep_rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ep_rules)

HOR = [3, 5, 10, 21]
DEDUP = 5
ANCH = {"SPY", "QQQ", "IWM"}

# lane1.py's published headline on this panel — the reproduction gate.
GATE_EVENTS = 780          # CLASSIFIED events (README: 24.6% of raw events are unclassifiable)
GATE_A = 376
GATE_LIFT_21 = -3.11
GATE_CI_21 = (-5.28, -1.16)
GATE_LIFT_TOL = 0.05
GATE_CI_TOL = 0.10

px, fin = load()
recs = prep_fin(fin, "plus90")
panel = {s: v for s, v in px.items() if s not in ANCH}     # panel ORDER matters (placebo draws)
print("panel symbols", len(panel), flush=True)


def state_label(sym, dt):
    """point-in-time Bonde sales state -> 'pass' | 'fail' | None (core.state_asof)."""
    rec = recs.get(sym)
    if not rec:
        return None
    st = state_asof(rec, dt, align="period")
    if st is None:
        return None
    return "pass" if st["bonde_pass"] else "fail"


def fwd(P, i, k):
    e = i + 1
    if e + k >= len(P["c"]):
        return None
    a = P["c"][e]
    if a <= 0:
        return None
    return (P["c"][e + k] - a) / a * 100.0


# ── the placebo: lane1.py §4, same seed, same pool, same exclusion ───────────
def placebo(evts, minbar):
    rng = np.random.default_rng(11)
    pool = sorted([s for s in px if s not in ANCH])
    pool = [pool[k] for k in rng.choice(len(pool), 700, replace=False)]
    ev_by_sym = {}
    for s, dt, i in evts:
        ev_by_sym.setdefault(s, []).append(i)
    dateidx = {s: {d: k for k, d in enumerate(px[s]["d"])} for s in pool}
    prows = []
    for s, dt, i in evts:
        cand = []
        tries = 0
        while len(cand) < 3 and tries < 40:
            tries += 1
            t = pool[rng.integers(0, len(pool))]
            if t == s or t in [c[0] for c in cand]:
                continue
            j = dateidx[t].get(dt)
            if j is None or j < minbar:
                continue
            if any(abs(j - e) <= 21 for e in ev_by_sym.get(t, [])):
                continue
            cand.append((t, j))
        for t, j in cand:
            lab = state_label(t, dt)
            P = px[t]
            prows.append(dict(sym=t, date=dt, i=j, cell=("C" if lab == "pass" else "D") if lab else None,
                              r={k: fwd(P, j, k) for k in HOR}))
    return prows


sym_ids = {}
date_ids = {}


def sid(s):
    if s not in sym_ids:
        sym_ids[s] = len(sym_ids)
    return sym_ids[s]


def did(d):
    if d not in date_ids:
        date_ids[d] = len(date_ids)
    return date_ids[d]


def cell_rows(evts, cell_name, split):
    """events -> rows with forward returns, for one lettered cell."""
    keep = split[cell_name] if cell_name in ("A", "B", "AB") else None
    out = []
    for sym, dt, i in (keep if keep is not None else evts):
        P = px[sym]
        out.append(dict(sym=sym, date=dt, sid=sid(sym), did=did(dt), r={k: fwd(P, i, k) for k in HOR}))
    return out


report = {}
for rule in (ep_rules.shipped(), ep_rules.PUBLISHED, ep_rules.PUBLISHED_GAP):
    name = rule["name"]
    evts = ep_rules.events(panel, rule, dedup=DEDUP)
    split = ep_rules.cells(evts, state_label)
    nA, nB, nU = len(split["A"]), len(split["B"]), split["unclassified"]
    print(f"\n===== RULE {name} =====", flush=True)
    print(f"  cite: {rule['cite']}")
    print(f"  raw events {len(evts)}  symbols {len(set(e[0] for e in evts))}"
          f"  classified {nA + nB}  A {nA}  B {nB}  unclassified {nU}", flush=True)

    rows = {"A": cell_rows(evts, "A", split), "B": cell_rows(evts, "B", split),
            "AB": cell_rows(evts, "AB", split)}
    prows = placebo(evts, int(rule["avg_window"]) + 1)
    for p in prows:
        p["sid"] = sid(p["sym"])
        p["did"] = did(p["date"])
    rows["C"] = [p for p in prows if p["cell"] == "C"]
    rows["D"] = [p for p in prows if p["cell"] == "D"]
    rows["CD"] = list(prows)
    print(f"  placebo draws {len(prows)}  C {len(rows['C'])}  D {len(rows['D'])}", flush=True)

    NAMES = ["A", "B", "AB", "C", "D", "CD"]
    NS, ND = len(sym_ids), len(date_ids)
    per_h = {}
    for k in HOR:
        csym, cdate, pts = [], [], {}
        for nm in NAMES:
            sel = [r for r in rows[nm] if r["r"][k] is not None]
            csym.append(Cell([r["sid"] for r in sel], [r["r"][k] for r in sel]))
            cdate.append(Cell([r["did"] for r in sel], [r["r"][k] for r in sel]))
            x = csym[-1].v
            pts[nm] = dict(n=len(x), med=med(x), mean=mean(x), win=win(x))
        bs = boot(csym, [med, mean, win], NS, B=600, seed=100 + k)
        bd = boot_dates(cdate, [med, mean, win], ND, B=600, seed=100 + k)
        print(f"\n  h={k}d")
        for ci_, nm in enumerate(NAMES):
            lo, hi = ci(bs[:, ci_, 0])
            w1, w2 = ci(bs[:, ci_, 2])
            print(f"    {nm:3s} n={pts[nm]['n']:5d} med {pts[nm]['med']:+6.2f}% [{lo:+.2f},{hi:+.2f}]"
                  f"  win {pts[nm]['win']:5.1f}% [{w1:.1f},{w2:.1f}]")
        lifts = {}
        for a, b in [("A", "D"), ("AB", "CD"), ("A", "C")]:
            ia, ib = NAMES.index(a), NAMES.index(b)
            pm = pts[a]["med"] - pts[b]["med"]
            pw = pts[a]["win"] - pts[b]["win"]
            l1, h1 = ci(bs[:, ia, 0] - bs[:, ib, 0])
            l2, h2 = ci(bd[:, ia, 0] - bd[:, ib, 0])
            l3, h3 = ci(bs[:, ia, 2] - bs[:, ib, 2])
            lifts[f"{a}-{b}"] = dict(med=pm, sym_ci=[l1, h1], date_ci=[l2, h2], win=pw, win_ci=[l3, h3])
            print(f"     {a}-{b}: med {pm:+.2f}pp sym[{l1:+.2f},{h1:+.2f}] date[{l2:+.2f},{h2:+.2f}]"
                  f" | win {pw:+.2f}pp [{l3:+.2f},{h3:+.2f}]")
        per_h[k] = dict(points=pts, lifts=lifts)
    report[name] = dict(cite=rule["cite"], rule={k: v for k, v in rule.items() if k != "cite"},
                        n_events=len(evts), n_classified=nA + nB, nA=nA, nB=nB, unclassified=nU,
                        n_symbols=len(set(e[0] for e in evts)), placebo=len(prows), horizons=per_h)

# ── reproduction gate ────────────────────────────────────────────────────────
sh = report["shipped"]
g21 = sh["horizons"][21]["lifts"]["A-D"]
ok = (sh["n_classified"] == GATE_EVENTS and sh["nA"] == GATE_A
      and abs(g21["med"] - GATE_LIFT_21) <= GATE_LIFT_TOL
      and abs(g21["sym_ci"][0] - GATE_CI_21[0]) <= GATE_CI_TOL
      and abs(g21["sym_ci"][1] - GATE_CI_21[1]) <= GATE_CI_TOL)
report["reproduction_gate"] = dict(ok=bool(ok), expected=dict(classified=GATE_EVENTS, A=GATE_A,
                                   lift_21=GATE_LIFT_21, sym_ci_21=list(GATE_CI_21)),
                                   got=dict(classified=sh["n_classified"], A=sh["nA"],
                                            lift_21=g21["med"], sym_ci_21=g21["sym_ci"]))
print("\n===== REPRODUCTION GATE =====", flush=True)
if ok:
    print("  shipped rule reproduces lane1.py: 780 classified / A 376 / 21d lift -3.11pp"
          " [-5.28,-1.16]. The three rules below are on the SAME panel.", flush=True)
else:
    print("  PANEL MOVED — classified %s vs MEASURED %s, A %s vs %s, 21d lift %+.2f [%+.2f,%+.2f] vs"
          " MEASURED -3.11 [-5.28,-1.16]. The published-rule comparison is on a DIFFERENT panel;"
          " say so in docs/sepa/bonde_ep_remeasure_2026_09_20.md."
          % (sh["n_classified"], GATE_EVENTS, sh["nA"], GATE_A,
             g21["med"], g21["sym_ci"][0], g21["sym_ci"][1]), flush=True)

# ── the doc's table ──────────────────────────────────────────────────────────
print("\n| rule | cell | n | symbols | 21d median | win % | lift vs placebo (sym CI) | (date CI) |", flush=True)
print("|---|---|---|---|---|---|---|---|", flush=True)
for name in ("shipped", ep_rules.PUBLISHED["name"], ep_rules.PUBLISHED_GAP["name"]):
    r = report[name]
    h = r["horizons"][21]
    for cell, lift in (("AB", "AB-CD"), ("A", "A-D")):
        p = h["points"][cell]
        L = h["lifts"][lift]
        label = "rule alone" if cell == "AB" else "rule x sales gate"
        print(f"| {name} | {label} | {p['n']} | {r['n_symbols']} | {p['med']:+.2f}% | {p['win']:.1f}% |"
              f" {L['med']:+.2f}pp [{L['sym_ci'][0]:+.2f},{L['sym_ci'][1]:+.2f}] |"
              f" [{L['date_ci'][0]:+.2f},{L['date_ci'][1]:+.2f}] |", flush=True)

json.dump(report, open("/root/.cheetah/aud/lane1_published.json", "w"), indent=1)
pickle.dump(report, open("/root/.cheetah/aud/lane1_published.pkl", "wb"))
print("\nwrote /root/.cheetah/aud/lane1_published.json", flush=True)
