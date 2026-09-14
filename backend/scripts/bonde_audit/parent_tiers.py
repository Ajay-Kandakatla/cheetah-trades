# ─────────────────────────────────────────────────────────────────────────────
# Bonde board — FIRST PASS, SUPERSEDED. Kept because it is the measurement the
# audit checked, and because three of its claims did NOT reproduce and a reader
# should be able to see exactly what was struck:
#
#   1. "EP + sales-PASS loses to EP + sales-FAIL" (-3.36pp [-5.84,-0.87]).
#      Re-measured at -2.42pp [-4.88,+0.30]; spans zero in all four variants.
#      STRUCK — the board does not say it.
#   2. "BOTH character clauses are inverted." Only `consecutive_growth_q >= 2`
#      measures negative. `accelerating` is a NULL (+1.63pp, CI -0.85 to +7.54).
#   3. "Coverage is 46%, so this is the large/mid-cap half." That was this
#      script's own no-retry fetcher losing ~half its requests, not a Massive
#      limit. 1,301 names it called "no financials" do return financials.
#
# What DID reproduce is the headline, and it is the reason the tab reads the way
# it does: the Episodic Pivot confirmed by Bonde's sales gate measures INVERTED
# against a date-matched placebo.
#
# The authority is the sibling audit scripts in this directory. Quote those.
# ─────────────────────────────────────────────────────────────────────────────

"""Do Bonde's SALES TIERS separate forward returns, independent of the EP?

Run (the Massive key only exists in the running api container):

    cd /Users/ajay/clinet-test/cheetah-market-app && \
      docker compose exec -T api python - < /tmp/scratch/bonde/tiers.py

Design notes that matter for reading the numbers:

* NO LOOKAHEAD. The sales state at bar D is rebuilt from quarterly reports whose
  AVAILABILITY DATE is <= D. Availability = Massive's `filing_date`. Rows with
  `filing_date is None` are the DERIVED Q4s (annual minus the three reported
  quarters, sepa/board_metrics.py:48) — they have no filing date at all, so they
  are given end_date + 90 days (the 10-K deadline) and the whole study is re-run
  with them dropped as a sensitivity.
* The series handed to `sepa.sales.compute` is DENSE BY PERIOD INDEX
  (fiscal_year*4 + quarter-1), not by list position. Massive omits missing
  quarters, so position i vs i+4 is not always four quarters apart — the repo
  documents this at sepa/canslim.py:262. Densifying makes `compute`'s YoY a real
  YoY. A raw-position variant is also run as a sensitivity.
* `sepa.sales.compute` itself is called — nothing about the tiers is
  reimplemented here, so the tab and this study cannot disagree.
* Every CI is a SYMBOL-CLUSTERED bootstrap. Bars inside a name are
  autocorrelated and the 63d windows overlap, so an iid interval over bars would
  be several times too tight.
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

sys.path.insert(0, "/app")

import numpy as np
import pandas as pd

from sepa import sales as sales_mod
from sepa.sales import SALES_FLOOR_PCT
from sepa.buyable_verdict import BONDE_MIN_CONSEC_Q
from sepa.prices import load_prices
from sepa.universe import load_universe
from sepa.canslim import _income_value, _period_index

CACHE = "/root/.cheetah/bonde_fin_cache_v1.json.gz"
FIN_LIMIT = 30          # quarters per name (~7 years) — enough to rebuild 2y of states
SAMPLE_EVERY = 21       # trading days between sampled bars (~monthly)
HORIZONS = (21, 63)
B_MEAN = 1000           # bootstrap draws for mean / win-rate CIs
B_MED = 300             # bootstrap draws for median CIs (slower path)
DERIVED_LAG_DAYS = 90   # 10-K deadline, used only for filing_date-None rows
RNG = np.random.default_rng(20260913)


# ---------------------------------------------------------------------------
# 1. Financials, cached
# ---------------------------------------------------------------------------
def fetch_financials(symbols):
    if os.path.exists(CACHE):
        with gzip.open(CACHE, "rt") as fh:
            cached = json.load(fh)
        if set(symbols) <= set(cached):
            print(f"[fin] cache hit: {len(cached)} symbols")
            return cached
    else:
        cached = {}

    import requests
    from massive_keys import stocks_key
    key = stocks_key()
    base = "https://api.massive.com/vX/reference/financials"
    todo = [s for s in symbols if s not in cached]
    print(f"[fin] fetching {len(todo)} symbols from Massive ...")

    def one(sym):
        try:
            r = requests.get(base, params={"ticker": sym, "limit": FIN_LIMIT,
                                           "timeframe": "quarterly", "apiKey": key},
                             timeout=20)
            if r.status_code != 200:
                return sym, []
            out = []
            for q in (r.json() or {}).get("results") or []:
                out.append({
                    "p": _period_index(q),
                    "end": q.get("end_date"),
                    "filed": q.get("filing_date"),
                    "rev": _income_value(q, "revenues"),
                    "eps": _income_value(q, "diluted_earnings_per_share"),
                })
            return sym, out
        except Exception:
            return sym, []

    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for sym, rows in ex.map(one, todo):
            cached[sym] = rows
            done += 1
            if done % 500 == 0:
                print(f"   {done}/{len(todo)}  {time.time()-t0:.0f}s")
    with gzip.open(CACHE, "wt") as fh:
        json.dump(cached, fh)
    print(f"[fin] done in {time.time()-t0:.0f}s")
    return cached


def prep_reports(rows, drop_derived):
    """API-order (newest-first) reports with an availability DATE attached."""
    out, seen = [], set()
    for r in rows:
        if r["p"] is None or r["rev"] is None:
            continue
        if r["p"] in seen:          # restatement — keep the most recent filing
            continue
        filed, derived = r["filed"], False
        if not filed:
            derived = True
            if drop_derived:
                continue
            if not r["end"]:
                continue
            filed = str((pd.Timestamp(r["end"]) + timedelta(days=DERIVED_LAG_DAYS)).date())
        seen.add(r["p"])
        out.append({"p": r["p"], "avail": pd.Timestamp(filed), "rev": r["rev"],
                    "eps": r["eps"], "derived": derived})
    return out


def state_at(reports, asof, dense=True):
    """Bonde sales state as of `asof`, from quarters available by then only."""
    avail = [r for r in reports if r["avail"] <= asof]
    if len(avail) < 5:
        return None
    if dense:
        p0 = max(r["p"] for r in avail)
        by_p = {r["p"]: r for r in avail}
        rev = [by_p[p0 - i]["rev"] if (p0 - i) in by_p else None for i in range(8)]
        eps = [by_p[p0 - i]["eps"] if (p0 - i) in by_p else None for i in range(8)]
        latest_avail = by_p[p0]["avail"]
    else:                                    # raw list position, as canslim does
        rev = [r["rev"] for r in avail[:8]]
        eps = [r["eps"] for r in avail[:8]]
        latest_avail = avail[0]["avail"]
    # q_eps_growth_pct exactly as sepa/canslim.py::_compute_q_eps_growth does it
    q_eps = None
    if len(eps) > 4 and eps[0] is not None and eps[4] not in (None, 0):
        q_eps = round((eps[0] - eps[4]) / abs(eps[4]) * 100, 2)
    info = sales_mod.compute(rev, q_eps)
    info["age_days"] = int((asof - latest_avail).days)
    return info


# ---------------------------------------------------------------------------
# 2. Observation panel
# ---------------------------------------------------------------------------
def build_panel(fin, symbols, drop_derived=False, dense=True):
    spy = load_prices("SPY")
    ref_dates = list(spy.index[::SAMPLE_EVERY])
    print(f"[panel] {len(ref_dates)} sample dates {ref_dates[0].date()} -> {ref_dates[-1].date()}")

    rows = []
    for n, sym in enumerate(symbols):
        if n % 500 == 0:
            print(f"   panel {n}/{len(symbols)}")
        try:
            df = load_prices(sym)
        except Exception:
            continue
        if df is None or len(df) < 90:
            continue
        idx = df.index
        close = df["close"].to_numpy(dtype=float)
        reports = prep_reports(fin.get(sym) or [], drop_derived)
        pos_of = {d: i for i, d in enumerate(idx)}
        for d in ref_dates:
            i = pos_of.get(d)
            if i is None or close[i] <= 0 or not np.isfinite(close[i]):
                continue
            fwd = {}
            for h in HORIZONS:
                fwd[h] = (close[i + h] / close[i] - 1.0) * 100 if i + h < len(close) else np.nan
            if not np.isfinite(fwd[HORIZONS[0]]):
                continue
            st = state_at(reports, d, dense=dense) if reports else None
            rows.append({
                "sym": sym, "date": d, "px": close[i],
                "f21": fwd[21], "f63": fwd[63],
                "tier": (st or {}).get("tier", "unknown"),
                "score": (st or {}).get("score"),
                "yoy": (st or {}).get("growth_yoy_pct"),
                "accel": (st or {}).get("accelerating"),
                "consec": (st or {}).get("consecutive_growth_q"),
                "sales_led": (st or {}).get("sales_led"),
                "age": (st or {}).get("age_days"),
                "has_fin": st is not None,
            })
    p = pd.DataFrame(rows)
    p["tier"] = p["tier"].fillna("unknown")
    p.loc[p["score"].isna(), "tier"] = "unknown"
    cleared = p["yoy"].notna() & (p["yoy"] >= SALES_FLOOR_PCT)
    character = (p["accel"] == True) | (p["consec"].fillna(0) >= BONDE_MIN_CONSEC_Q)
    p["cleared_floor"] = cleared
    p["bonde_pass"] = cleared & character
    return p


# ---------------------------------------------------------------------------
# 3. Symbol-clustered bootstrap
# ---------------------------------------------------------------------------
def _by_sym(vals, syms, nsym):
    """Per-symbol (sum, count, wins) for a fast exact clustered bootstrap."""
    s = np.bincount(syms, weights=vals, minlength=nsym)
    c = np.bincount(syms, minlength=nsym).astype(float)
    w = np.bincount(syms, weights=(vals > 0).astype(float), minlength=nsym)
    return s, c, w


def clustered_stats(vals, syms, nsym, draws):
    vals = np.asarray(vals, float)
    ok = np.isfinite(vals)
    vals, syms = vals[ok], np.asarray(syms)[ok]
    if vals.size == 0:
        return None
    s, c, w = _by_sym(vals, syms, nsym)
    S, C, W = s[draws].sum(1), c[draws].sum(1), w[draws].sum(1)
    good = C > 0
    bmean = S[good] / C[good]
    bwin = W[good] / C[good] * 100
    # medians: slower path, fewer draws
    order = np.argsort(syms, kind="stable")
    vs, ss = vals[order], syms[order]
    starts = np.searchsorted(ss, np.arange(nsym), "left")
    ends = np.searchsorted(ss, np.arange(nsym), "right")
    bmed = []
    for row in draws[:B_MED]:
        parts = [vs[starts[j]:ends[j]] for j in row if ends[j] > starts[j]]
        if parts:
            bmed.append(np.median(np.concatenate(parts)))
    return {
        "n": int(vals.size), "nsym": int((c > 0).sum()),
        "mean": float(vals.mean()),
        "mean_lo": float(np.percentile(bmean, 2.5)), "mean_hi": float(np.percentile(bmean, 97.5)),
        "median": float(np.median(vals)),
        "med_lo": float(np.percentile(bmed, 2.5)) if bmed else float("nan"),
        "med_hi": float(np.percentile(bmed, 97.5)) if bmed else float("nan"),
        "win": float((vals > 0).mean() * 100),
        "win_lo": float(np.percentile(bwin, 2.5)), "win_hi": float(np.percentile(bwin, 97.5)),
    }


def clustered_diff(vals_a, syms_a, vals_b, syms_b, nsym, draws):
    """Paired (same resampled symbols) mean difference A - B, and win-rate diff."""
    a, sa = np.asarray(vals_a, float), np.asarray(syms_a)
    b, sb = np.asarray(vals_b, float), np.asarray(syms_b)
    ma, mb = np.isfinite(a), np.isfinite(b)
    a, sa, b, sb = a[ma], sa[ma], b[mb], sb[mb]
    if a.size == 0 or b.size == 0:
        return None
    s1, c1, w1 = _by_sym(a, sa, nsym)
    s2, c2, w2 = _by_sym(b, sb, nsym)
    S1, C1, W1 = s1[draws].sum(1), c1[draws].sum(1), w1[draws].sum(1)
    S2, C2, W2 = s2[draws].sum(1), c2[draws].sum(1), w2[draws].sum(1)
    good = (C1 > 0) & (C2 > 0)
    d = S1[good] / C1[good] - S2[good] / C2[good]
    dw = (W1[good] / C1[good] - W2[good] / C2[good]) * 100
    return {
        "diff": float(a.mean() - b.mean()),
        "lo": float(np.percentile(d, 2.5)), "hi": float(np.percentile(d, 97.5)),
        "win_diff": float((a > 0).mean() * 100 - (b > 0).mean() * 100),
        "win_lo": float(np.percentile(dw, 2.5)), "win_hi": float(np.percentile(dw, 97.5)),
    }


def spearman(a, b):
    """Rank correlation without scipy — Pearson on ranks."""
    a, b = pd.Series(a).rank(), pd.Series(b).rank()
    if a.std() == 0 or b.std() == 0:
        return np.nan
    return float(np.corrcoef(a, b)[0, 1])


def fmt(st):
    if not st:
        return "  (empty)"
    return (f"n={st['n']:>6} sym={st['nsym']:>5}  "
            f"med {st['median']:+6.2f}% [{st['med_lo']:+.2f},{st['med_hi']:+.2f}]  "
            f"mean {st['mean']:+6.2f}% [{st['mean_lo']:+.2f},{st['mean_hi']:+.2f}]  "
            f"win {st['win']:5.1f}% [{st['win_lo']:.1f},{st['win_hi']:.1f}]")


def fmt_d(d, label):
    if not d:
        return f"  {label}: (empty)"
    star = "" if (d["lo"] <= 0 <= d["hi"]) else "  *"
    return (f"  {label}: mean {d['diff']:+.2f}pp [{d['lo']:+.2f},{d['hi']:+.2f}]"
            f"   win {d['win_diff']:+.1f}pp [{d['win_lo']:+.1f},{d['win_hi']:+.1f}]{star}")


# ---------------------------------------------------------------------------
# 4. Report
# ---------------------------------------------------------------------------
def report(p, tag):
    syms = sorted(p["sym"].unique())
    code = {s: i for i, s in enumerate(syms)}
    nsym = len(syms)
    p = p.assign(sc=p["sym"].map(code))
    draws = RNG.integers(0, nsym, size=(B_MEAN, nsym))

    print("\n" + "=" * 100)
    print(f"  {tag}")
    print("=" * 100)
    print(f"observations {len(p)}  symbols {nsym}  dates {p['date'].nunique()}"
          f"  ({p['date'].min().date()} -> {p['date'].max().date()})")

    for h, col in ((21, "f21"), (63, "f63")):
        print(f"\n--- forward {h}d ------------------------------------------------------")
        base = clustered_stats(p[col], p["sc"], nsym, draws)
        print(f"ALL BARS (placebo)   {fmt(base)}")
        sc_all = p[p["score"].notna()]
        base_s = clustered_stats(sc_all[col], sc_all["sc"], nsym, draws)
        print(f"ALL SCORED (placebo) {fmt(base_s)}")
        print(fmt_d(clustered_diff(sc_all[col].to_numpy(float), sc_all["sc"].to_numpy(),
                                   p[col].to_numpy(float), p["sc"].to_numpy(), nsym, draws),
                    "having financials at all, vs ALL"))
        av, asy = p[col].to_numpy(float), p["sc"].to_numpy()
        sv, ssy = sc_all[col].to_numpy(float), sc_all["sc"].to_numpy()
        for tier in ("explosive", "strong", "steady", "weak", "declining", "unknown"):
            q = p[p["tier"] == tier]
            if q.empty:
                continue
            st = clustered_stats(q[col], q["sc"], nsym, draws)
            print(f"{tier:<20} {fmt(st)}")
            print(fmt_d(clustered_diff(q[col].to_numpy(float), q["sc"].to_numpy(),
                                       av, asy, nsym, draws), "lift vs ALL   "))
            if tier != "unknown":
                print(fmt_d(clustered_diff(q[col].to_numpy(float), q["sc"].to_numpy(),
                                           sv, ssy, nsym, draws), "lift vs SCORED"))
        for name, mask in (("BONDE PASS", p["bonde_pass"]),
                           ("cleared 5% floor", p["cleared_floor"]),
                           ("NOT declining", p["score"].notna() & (p["tier"] != "declining")),
                           ("strong+explosive", p["tier"].isin(["strong", "explosive"]))):
            q = p[mask]
            st = clustered_stats(q[col], q["sc"], nsym, draws)
            print(f"{name:<20} {fmt(st)}")
            print(fmt_d(clustered_diff(q[col].to_numpy(float), q["sc"].to_numpy(),
                                       av, asy, nsym, draws), "lift vs ALL   "))
            print(fmt_d(clustered_diff(q[col].to_numpy(float), q["sc"].to_numpy(),
                                       sv, ssy, nsym, draws), "lift vs SCORED"))

        # --- clause tests, inside the cleared-floor cohort -------------------
        cf = p[p["cleared_floor"]]
        for clause, m in (("accelerating", (cf["accel"] == True)),
                          (f"consec>={BONDE_MIN_CONSEC_Q}", cf["consec"].fillna(0) >= BONDE_MIN_CONSEC_Q),
                          ("sales_led", (cf["sales_led"] == True))):
            yes, no = cf[m], cf[~m]
            sy = clustered_stats(yes[col], yes["sc"], nsym, draws)
            sn = clustered_stats(no[col], no["sc"], nsym, draws)
            print(f"clause {clause:<13} YES {fmt(sy)}")
            print(f"{'':<20} NO  {fmt(sn)}")
            print(fmt_d(clustered_diff(yes[col].to_numpy(float), yes["sc"].to_numpy(),
                                       no[col].to_numpy(float), no["sc"].to_numpy(),
                                       nsym, draws), f"{clause} YES-NO"))

        # --- head-to-head contrasts: where does the line actually cut? ------
        print("  -- head-to-head (A vs B, paired symbol-clustered) --")
        scored = p["score"].notna()
        pairs = [
            ("explosive", p["tier"] == "explosive", "strong", p["tier"] == "strong"),
            ("strong", p["tier"] == "strong", "steady", p["tier"] == "steady"),
            ("steady(5-25%)", p["tier"] == "steady",
             "weak+declining(<5%)", scored & p["tier"].isin(["weak", "declining"])),
            (">=5% floor", p["cleared_floor"],
             "scored but <5%", scored & ~p["cleared_floor"]),
            (">=25% gate", p["tier"].isin(["strong", "explosive"]),
             ">=5% gate", p["cleared_floor"]),
            ("BONDE PASS", p["bonde_pass"],
             "floor only, no character", p["cleared_floor"] & ~p["bonde_pass"]),
        ]
        for na, ma, nb, mb in pairs:
            qa, qb = p[ma], p[mb]
            d = clustered_diff(qa[col].to_numpy(float), qa["sc"].to_numpy(),
                               qb[col].to_numpy(float), qb["sc"].to_numpy(), nsym, draws)
            print(f"    {na} ({int(ma.sum())}) vs {nb} ({int(mb.sum())})")
            print(fmt_d(d, "  A-B"))

    # --- ranking: score vs raw YoY -----------------------------------------
    print("\n--- ranking: sales.score vs raw YoY ---------------------------------")
    sc = p[p["score"].notna() & p["f21"].notna()]
    ics_s, ics_y, ics_sy = [], [], []
    for d, g in sc.groupby("date"):
        if len(g) < 50:
            continue
        ics_s.append(spearman(g["score"], g["f21"]))
        ics_y.append(spearman(g["yoy"], g["f21"]))
        ics_sy.append(spearman(g["score"], g["yoy"]))
    ics_s, ics_y = np.array(ics_s, float), np.array(ics_y, float)

    def boot_dates(x, b=4000):
        dr = RNG.integers(0, len(x), size=(b, len(x)))
        m = x[dr].mean(1)
        return np.percentile(m, 2.5), np.percentile(m, 97.5)

    for nm, arr in (("score", ics_s), ("raw YoY", ics_y)):
        lo, hi = boot_dates(arr)
        print(f"cross-sectional IC vs f21, {nm:<8} mean {arr.mean():+.4f} "
              f"[{lo:+.4f},{hi:+.4f}]  over {len(arr)} dates")
    print(f"rank corr score vs raw YoY (mean per date): {np.nanmean(ics_sy):+.3f}")

    for h, col in ((21, "f21"), (63, "f63")):
        for key in ("score", "yoy"):
            picks = []
            for d, g in sc.groupby("date"):
                if len(g) < 50:
                    continue
                k = max(1, int(len(g) * 0.10))
                picks.append(g.nlargest(k, key))
            q = pd.concat(picks)
            st = clustered_stats(q[col], q["sc"], nsym, draws)
            print(f"top-decile by {key:<6} f{h}d  {fmt(st)}")
            print(fmt_d(clustered_diff(q[col].to_numpy(float), q["sc"].to_numpy(),
                                       p[col].to_numpy(float), p["sc"].to_numpy(),
                                       nsym, draws), "lift vs ALL   "))
            sc_all = p[p["score"].notna()]
            print(fmt_d(clustered_diff(q[col].to_numpy(float), q["sc"].to_numpy(),
                                       sc_all[col].to_numpy(float), sc_all["sc"].to_numpy(),
                                       nsym, draws), "lift vs SCORED"))
    for h, col in ((21, "f21"), (63, "f63")):
        sel = {}
        for key in ("score", "yoy"):
            picks = []
            for d, g in sc.groupby("date"):
                if len(g) < 50:
                    continue
                k = max(1, int(len(g) * 0.10))
                picks.append(g.nlargest(k, key))
            sel[key] = pd.concat(picks)
        d = clustered_diff(sel["score"][col].to_numpy(float), sel["score"]["sc"].to_numpy(),
                           sel["yoy"][col].to_numpy(float), sel["yoy"]["sc"].to_numpy(),
                           nsym, draws)
        print(fmt_d(d, f"f{h}d  top-decile SCORE minus top-decile RAW-YoY"))

    ov = []
    for d, g in sc.groupby("date"):
        if len(g) < 50:
            continue
        k = max(1, int(len(g) * 0.10))
        a = set(g.nlargest(k, "score")["sym"])
        b = set(g.nlargest(k, "yoy")["sym"])
        ov.append(len(a & b) / k)
    print(f"top-decile overlap score vs YoY: {np.mean(ov)*100:.1f}%")

    # --- what the floor excludes -------------------------------------------
    print("\n--- what the 5% floor is excluding ----------------------------------")
    tot = len(p)
    print(f"bars with a sales score        {p['score'].notna().sum():>6} ({p['score'].notna().mean()*100:.1f}%)")
    print(f"bars clearing the 5% floor     {p['cleared_floor'].sum():>6} ({p['cleared_floor'].mean()*100:.1f}%)")
    print(f"bars passing the FULL Bonde    {p['bonde_pass'].sum():>6} ({p['bonde_pass'].mean()*100:.1f}%)")
    scored = p[p["score"].notna()]
    print(f"of SCORED bars, floor pass     {scored['cleared_floor'].mean()*100:.1f}%"
          f"   full pass {scored['bonde_pass'].mean()*100:.1f}%")
    print("tier mix of scored bars:")
    print((scored["tier"].value_counts(normalize=True) * 100).round(1).to_string())
    last = p[p["date"] == p["date"].max()]
    print(f"tier COUNTS on the last sampled date ({last['date'].max().date()}, n={len(last)}):")
    print(last["tier"].value_counts().to_string())

    print("\n--- staleness of the point-in-time state ---------------------------")
    ag = p["age"].dropna()
    if len(ag):
        print(f"days since the newest available filing: median {ag.median():.0f}  "
              f"p75 {ag.quantile(.75):.0f}  p90 {ag.quantile(.90):.0f}  "
              f"share > 120d {float((ag > 120).mean())*100:.1f}%")
    return p


def main():
    universe = load_universe()
    fin = fetch_financials(universe)
    have = sum(1 for s in universe if fin.get(s))
    derived = sum(1 for s in universe for r in (fin.get(s) or []) if not r["filed"])
    allrows = sum(len(fin.get(s) or []) for s in universe)
    print(f"[fin] symbols with financials {have}/{len(universe)}; "
          f"rows {allrows}; filing_date-None (derived) {derived} ({derived/max(allrows,1)*100:.1f}%)")

    panel = build_panel(fin, universe, drop_derived=False, dense=True)
    panel.to_pickle("/root/.cheetah/bonde_panel.pkl")
    report(panel, "PRIMARY — dense period series, derived Q4 available at end+90d")

    # price floor sensitivity (the repo's own $2 safety floor)
    report(panel[panel["px"] >= 2.0].copy(), "SENSITIVITY — price >= $2 only")
    report(panel[(panel["age"].isna()) | (panel["age"] <= 120)].copy(),
           "SENSITIVITY — state fresh (newest filing <= 120d old) or unknown")

    p2 = build_panel(fin, universe, drop_derived=True, dense=True)
    report(p2, "SENSITIVITY — derived Q4 rows DROPPED entirely")

    p3 = build_panel(fin, universe, drop_derived=False, dense=False)
    report(p3, "SENSITIVITY — raw list-position series (what canslim feeds today)")


if __name__ == "__main__":
    main()
