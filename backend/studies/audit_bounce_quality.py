"""ADVERSARIAL AUDIT of studies/bounce_quality_study.py. Read-only, nothing wired.

Answers the six questions the study's own report does not:
  (a) effective sample size after clustering, and after the full stack
  (b) how many sweep cells are actually printed
  (c) is the CI on the DELTA, and is the estimator it checks stable
  (d) is the placebo matched on anything but SIZE
  (e) date / symbol concentration and the design effect
  (f) is any gate a function of the exit RULE rather than of the setup
  + (g) does the study measure the gates that ACTUALLY SHIPPED at HEAD 854e3dc?

    docker cp studies/audit_bounce_quality.py cheetah-market-app-api-1:/tmp/ab.py
    docker exec cheetah-market-app-api-1 sh -c \
        'cd /app && PYTHONPATH=/app python -u /tmp/ab.py --csv /tmp/bq_events.csv'
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from sepa import prices
from supply_demand import alert_gates as AG
from supply_demand import mood as MD
from supply_demand import sd_liquidity as SL

RNG = np.random.default_rng(20260909)


# ── shared helpers ───────────────────────────────────────────────────────────
def date_boot_delta(base: pd.DataFrame, kept: pd.DataFrame, draws: int = 5000):
    """Same paired date-clustered bootstrap the study uses, so my deltas are
    comparable to its deltas."""
    dates = np.array(sorted(base["date"].unique()))
    if len(dates) < 3 or kept.empty:
        return (np.nan, np.nan, np.nan)
    def agg(D):
        g = D.groupby("date")["R"].agg(["sum", "count"]).reindex(dates).fillna(0.0)
        return g["sum"].to_numpy(float), g["count"].to_numpy(float)
    bs, bc = agg(base)
    ks, kc = agg(kept)
    idx = RNG.integers(0, len(dates), size=(draws, len(dates)))
    bn, bd = bs[idx].sum(1), bc[idx].sum(1)
    kn, kd = ks[idx].sum(1), kc[idx].sum(1)
    ok = (bd > 0) & (kd > 0)
    d = kn[ok] / kd[ok] - bn[ok] / bd[ok]
    if d.size < 100:
        return (np.nan, np.nan, np.nan)
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5)), float((d <= 0).mean())


def cluster_se(D: pd.DataFrame, col: str = "R") -> tuple:
    """IID SE vs date-clustered SE of the mean, and the design effect."""
    x = D[col].to_numpy(float)
    n = len(x)
    se_iid = x.std(ddof=1) / np.sqrt(n)
    g = D.groupby("date")[col].agg(["sum", "count"])
    s, c = g["sum"].to_numpy(float), g["count"].to_numpy(float)
    m = x.mean()
    G = len(g)
    # standard cluster-robust SE of a mean: sum of within-cluster deviations
    u = s - m * c
    se_cl = np.sqrt((u ** 2).sum()) / c.sum()
    se_cl *= np.sqrt(G / max(G - 1, 1))
    return float(se_iid), float(se_cl), float((se_cl / se_iid) ** 2)


# ── (a)(e) clustering ────────────────────────────────────────────────────────
def q_ae(B: pd.DataFrame, masks: dict) -> None:
    print("=" * 110)
    print("(a)+(e)  SAMPLE SIZE AFTER CLUSTERING  — events are not observations")
    print("=" * 110)
    print("  %-24s %7s %7s %7s  %8s %8s %7s  %s" %
          ("cohort", "n", "dates", "names", "se_iid", "se_clust", "deff", "n_effective"))
    for tag, m in masks.items():
        D = B[m]
        if len(D) < 30:
            print("  %-24s n=%d TOO SMALL" % (tag, len(D)))
            continue
        si, sc, deff = cluster_se(D)
        print("  %-24s %7d %7d %7d  %8.4f %8.4f %7.2f  %d" %
              (tag, len(D), D.date.nunique(), D.symbol.nunique(), si, sc, deff,
               int(len(D) / max(deff, 1e-9))))
    print()
    print("  A design effect of D means the cohort carries the information of n/D")
    print("  independent trades. The study quotes raw n everywhere.")
    print()


# ── (c) is the robustness estimator stable? ──────────────────────────────────
def q_c(B: pd.DataFrame, masks: dict, draws: int = 400) -> None:
    print("=" * 110)
    print("(c)  THE 'ONE PER DATE' ROBUSTNESS LINE — study takes the alphabetically")
    print("     FIRST symbol per date, once. Here is what a RANDOM pick per date does.")
    print("=" * 110)
    print("  %-24s %10s %10s   %-24s" % ("cohort", "study_pick", "random_mean", "random 5-95 pct band"))
    for tag, m in masks.items():
        D = B[m]
        if len(D) < 100:
            continue
        study = D.sort_values(["date", "symbol"]).groupby("date").first()["R"].mean()
        # random one-per-date, `draws` times
        codes, uniq = pd.factorize(D["date"])
        R = D["R"].to_numpy(float)
        order = np.argsort(codes, kind="stable")
        cs, rs = codes[order], R[order]
        starts = np.searchsorted(cs, np.arange(len(uniq)))
        counts = np.bincount(cs, minlength=len(uniq))
        out = np.empty(draws)
        for i in range(draws):
            pick = starts + (RNG.random(len(uniq)) * counts).astype(int)
            out[i] = rs[pick].mean()
        print("  %-24s %+10.3f %+10.3f   [%+0.3f, %+0.3f]" %
              (tag, study, out.mean(), np.percentile(out, 5), np.percentile(out, 95)))
    print()
    print("  If the study's single pick sits anywhere inside that band, the line is")
    print("  noise being read as a robustness check.")
    print()


# ── (d) placebo matching ─────────────────────────────────────────────────────
def q_d(B: pd.DataFrame, masks: dict, draws: int = 2000) -> None:
    print("=" * 110)
    print("(d)  IS THE PLACEBO MATCHED?  study = IID random keep of the same SIZE.")
    print("     Here it is re-drawn respecting the DATE blocks the real gates select in.")
    print("=" * 110)
    R = B["R"].to_numpy(float)
    codes, uniq = pd.factorize(B["date"])
    order = np.argsort(codes, kind="stable")
    cs, rs = codes[order], R[order]
    starts = np.searchsorted(cs, np.arange(len(uniq) + 1))
    print("  %-24s %6s %8s  %-22s  %-22s  %s" %
          ("gate", "n_keep", "kept R", "IID placebo 5-95", "DATE-block placebo 5-95", "verdict flips?"))
    for tag, m in masks.items():
        D = B[m]
        n_keep = len(D)
        if n_keep < 50 or n_keep >= len(B):
            continue
        kept_R = D["R"].mean()
        # 1. IID placebo, exactly as the study draws it
        iid = np.array([RNG.choice(R, n_keep, replace=False).mean() for _ in range(400)])
        # 2. date-block placebo: whole dates drawn at random until n_keep reached
        blk = np.empty(draws)
        for i in range(draws):
            perm = RNG.permutation(len(uniq))
            tot = 0
            acc = []
            for d in perm:
                a, b = starts[d], starts[d + 1]
                acc.append(rs[a:b])
                tot += b - a
                if tot >= n_keep:
                    break
            blk[i] = np.concatenate(acc)[:n_keep].mean()
        i5, i95 = np.percentile(iid, 5), np.percentile(iid, 95)
        b5, b95 = np.percentile(blk, 5), np.percentile(blk, 95)
        out_iid = kept_R < i5 or kept_R > i95
        out_blk = kept_R < b5 or kept_R > b95
        print("  %-24s %6d %+8.3f  [%+0.3f, %+0.3f]%s  [%+0.3f, %+0.3f]%s  %s" %
              (tag, n_keep, kept_R, i5, i95, " OUT" if out_iid else "    ",
               b5, b95, " OUT" if out_blk else "    ",
               "YES — study calls it outside, block placebo does not"
               if (out_iid and not out_blk) else "no"))
    print()


# ── (f) is the gate selecting the EXIT RULE rather than the setup? ───────────
def q_f(B: pd.DataFrame) -> None:
    print("=" * 110)
    print("(f)  THE EXIT-RULE CONFOUND. R is scored two different ways depending on")
    print("     whether the event has a target at all. `clear` = no proven lid overhead,")
    print("     so the trade CANNOT book a target win — it can only stop or time out.")
    print("=" * 110)
    buckets = [("mood<-25", B.mood < -25), ("-25..-10", (B.mood >= -25) & (B.mood < -10)),
               ("-10..10", (B.mood >= -10) & (B.mood < 10)),
               ("10..25", (B.mood >= 10) & (B.mood < 25)),
               ("25..40", (B.mood >= 25) & (B.mood < 40)), ("mood>=40", B.mood >= 40)]
    print("  %-12s %7s %7s %9s %9s %9s %9s" %
          ("bucket", "n", "clear%", "R(all)", "R(target)", "R(clear)", "pct(all)%"))
    for tag, m in buckets:
        D = B[m]
        if len(D) < 50:
            continue
        t, c = D[~D.clear], D[D.clear]
        print("  %-12s %7d %6.1f%% %+9.3f %+9.3f %+9.3f %+9.2f" %
              (tag, len(D), 100 * D.clear.mean(), D.R.mean(),
               t.R.mean() if len(t) else np.nan,
               c.R.mean() if len(c) else np.nan, D.trade_pct.mean()))
    print()
    print("  LIKE-FOR-LIKE: the same gate re-measured INSIDE each exit regime, and in")
    print("  raw percent (which no exit rule can distort).")
    print("  %-28s %-32s %-32s %s" % ("gate", "within HAS-TARGET (Δ R)", "within CLEAR (Δ R)", "Δ mean % (all)"))
    nk = B.knife.eq(False)
    gates = {"mood >= 25": AG_pass(B.mood, 25.0),
             "not-knife": nk,
             "not-knife + mood>=25": nk & AG_pass(B.mood, 25.0),
             "DEF2 shelf": B.shelf_ok.astype(bool),
             "DEF3 rp": B.rp_ok.astype(bool)}
    for tag, m in gates.items():
        m = m.fillna(False).astype(bool)
        row = []
        for sel in (~B.clear, B.clear.astype(bool)):
            sub, base = B[m & sel], B[sel]
            if len(sub) < 50:
                row.append("n=%d too small" % len(sub))
                continue
            lo, hi, _ = date_boot_delta(base, sub)
            row.append("n=%-5d %+0.3f  CI[%+0.3f,%+0.3f]" %
                       (len(sub), sub.R.mean() - base.R.mean(), lo, hi))
        dpct = B[m].trade_pct.mean() - B.trade_pct.mean()
        print("  %-28s %-32s %-32s %+0.3f%%" % (tag, row[0], row[1], dpct))
    print()
    print("  ROOM-MATCHED: R is bounded by room/risk. Re-measure inside room deciles.")
    B = B.copy()
    B["room_f"] = B["room_pct"].fillna(999.0)
    B["rq"] = pd.qcut(B["room_f"], 5, labels=False, duplicates="drop")
    for tag, m in (("mood>=25", AG_pass(B.mood, 25.0)),
                   ("not-knife + mood>=25", B.knife.eq(False) & AG_pass(B.mood, 25.0))):
        m = m.fillna(False).astype(bool)
        parts = []
        for q in sorted(B["rq"].dropna().unique()):
            sel = B["rq"] == q
            sub, base = B[m & sel], B[sel]
            if len(sub) < 50:
                parts.append("q%d n/a" % q)
                continue
            parts.append("q%d %+0.3f(n=%d)" % (q, sub.R.mean() - base.R.mean(), len(sub)))
        print("  %-24s %s" % (tag, "  ".join(parts)))
    print()


def AG_pass(col, thr):
    return (pd.to_numeric(col, errors="coerce") >= thr).fillna(False)


# ── (g) did the study measure the gates that SHIPPED? ────────────────────────
def q_g(B: pd.DataFrame, sample: int) -> None:
    print("=" * 110)
    print("(g)  DOES THE STUDY MEASURE THE SHIPPED GATES?  HEAD = 854e3dc")
    print("     demand_alerts.py:481 -> AG.knife_gate      : 50MA now vs 1 BAR ago")
    print("     study _knife()                             : 50MA now vs 10 BARS ago")
    print("     demand_alerts.py:489 -> AG.reversal_mood_gate: mood on the LAST 60 BARS")
    print("     study _mood()                              : mood on the FULL ~500-bar frame")
    print("=" * 110)
    D = B if sample <= 0 or sample >= len(B) else B.sample(sample, random_state=7)
    D = D.sort_values(["symbol", "date"])
    coll = prices._get_mongo()
    rows = []
    cur_sym, f, pos = None, None, None
    for i, (_, e) in enumerate(D.iterrows()):
        if i % 4000 == 0:
            print("   ... %d/%d" % (i, len(D)), file=sys.stderr, flush=True)
        sym = e["symbol"]
        if sym != cur_sym:
            cur_sym = sym
            doc = coll.find_one({"symbol": sym}, {"bars": 1, "_id": 0})
            g = pd.DataFrame((doc or {}).get("bars") or [])
            if g.empty or "close" not in g:
                f = None
                continue
            for c in ("open", "high", "low", "close", "volume"):
                if c not in g:
                    g[c] = np.nan
                g[c] = pd.to_numeric(g[c], errors="coerce")
            g["d"] = g["date"].astype(str).str[:10]
            g = g.dropna(subset=["open", "high", "low", "close"]).sort_values("d")
            f = g.drop_duplicates(subset=["d"], keep="last").reset_index(drop=True)
            pos = {d: k for k, d in enumerate(f["d"])}
        if f is None:
            continue
        j = pos.get(str(e["date"]))
        if j is None or j < 252:
            continue
        sub = f.iloc[:j]                                   # bars strictly before the event bar
        closes, lows = sub["close"], sub["low"]
        ma = closes.rolling(50).mean()
        st = SL.structure_read(closes.tolist(), lows.tolist(), swing_window=5)
        # SHIPPED: alert_gates.knife_read — ma.iloc[-1] vs ma.iloc[-2]
        k_ship = SL.is_falling_knife(st, float(closes.iloc[-1]),
                                     float(ma.iloc[-1]) if pd.notna(ma.iloc[-1]) else None,
                                     float(ma.iloc[-2]) if pd.notna(ma.iloc[-2]) else None)
        # SHIPPED: alert_gates.reversal_mood_read — mood on the last 60 bars
        try:
            m60 = MD.mood(sub.tail(60), closed_only=False)
            s60 = float(m60.get("score")) if m60.get("label") != "unavailable" else np.nan
        except Exception:                                   # noqa: BLE001
            s60 = np.nan
        rows.append({"symbol": sym, "date": e["date"], "R": e["R"], "trade_pct": e["trade_pct"],
                     "clear": e["clear"], "knife_study": bool(e["knife"]), "knife_ship": bool(k_ship),
                     "mood_study": float(e["mood"]), "mood_ship": s60})
    S = pd.DataFrame(rows)
    if S.empty:
        print("  no rows recomputed")
        return
    print("  recomputed n=%d of %d bouncing events" % (len(S), len(B)))
    agree_k = (S.knife_study == S.knife_ship).mean()
    print()
    print("  KNIFE — study (10-bar slope) vs shipped (1-bar slope):")
    print("    agree on %.1f%% of events;  study says knife on %.1f%%, shipped says %.1f%%" %
          (100 * agree_k, 100 * S.knife_study.mean(), 100 * S.knife_ship.mean()))
    print("    keep rate  study not-knife %.1f%%   SHIPPED not-knife %.1f%%" %
          (100 * (~S.knife_study).mean(), 100 * (~S.knife_ship).mean()))
    print()
    print("  MOOD — study (full ~500-bar frame) vs shipped (last 60 bars):")
    ok = S.mood_study.notna() & S.mood_ship.notna()
    print("    corr %.3f   mean study %+.1f   mean shipped %+.1f   mean |diff| %.1f pts" %
          (S.loc[ok, "mood_study"].corr(S.loc[ok, "mood_ship"]),
           S.mood_study.mean(), S.mood_ship.mean(),
           (S.loc[ok, "mood_ship"] - S.loc[ok, "mood_study"]).abs().mean()))
    ks, kp = (S.mood_study >= 25), (S.mood_ship >= 25)
    print("    keep at >=25   study %.1f%%   SHIPPED %.1f%%   agree %.1f%%   "
          "kept by SHIPPED but not by study: %d events" %
          (100 * ks.mean(), 100 * kp.mean(), 100 * (ks == kp).mean(), int((kp & ~ks).sum())))
    print()
    print("  WHAT THE SHIPPED STACK ACTUALLY PAYS ON THIS COHORT:")
    base = S
    for tag, m in (("study nk + study mood>=25", (~S.knife_study) & ks),
                   ("SHIPPED nk + SHIPPED mood>=25", (~S.knife_ship) & kp),
                   ("SHIPPED not-knife only", ~S.knife_ship),
                   ("SHIPPED mood>=25 only", kp)):
        sub = base[m.fillna(False)]
        if len(sub) < 50:
            print("    %-32s n=%d TOO SMALL" % (tag, len(sub)))
            continue
        lo, hi, p = date_boot_delta(base, sub)
        print("    %-32s keep %5d (%4.1f%%)  %+0.3fR   Δ %+0.3fR  CI[%+0.3f,%+0.3f]  P(Δ<=0)=%.3f"
              % (tag, len(sub), 100 * len(sub) / len(base), sub.R.mean(),
                 sub.R.mean() - base.R.mean(), lo, hi, p))
    print()


# ── (b) sweep-cell count ─────────────────────────────────────────────────────
def q_b() -> None:
    print("=" * 110)
    print("(b)  MULTIPLICITY — how many cells does one run actually print?")
    print("=" * 110)
    counts = {
        "gate table rows (each WITH a CI + perm p)": 1 + 5 + 3,
        "stack rows (each WITH a CI + perm p)": 2 + 3 + 1 + 1,
        "MARGINAL KEEP single clauses (no CI)": 15,
        "DEF1 constant sweep (no CI)": len(np.arange(0.50, 1.001, 0.05)) + len(np.arange(0.5, 2.001, 0.25))
                                       + len(np.arange(0.8, 1.501, 0.1)) + 7 + 5,
        "DEF2 constant sweep (no CI)": 6 + 5 + 6 + 5 + 5,
        "DEF3 constant sweep (no CI)": 7 + 6 + 6 + 5 + 5,
        "window-length grid (no CI)": (5 + 4) + (5 + 5 + 2) + (4 + 3 + 2),
        "direction split rows": 6,
    }
    for k, v in counts.items():
        print("  %-46s %4d" % (k, v))
    print("  %-46s %4d" % ("TOTAL cells printed", sum(counts.values())))
    print("  %-46s %4d" % ("of which carry ANY inference (CI/p)", 16))
    print()
    print("  The build agent's own limits say '~90 sweep rows'. The uncorrected,")
    print("  inference-free cells alone number %d." % (sum(counts.values()) - 16 - 6))
    print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="/tmp/bq_events.csv")
    ap.add_argument("--sample", type=int, default=0, help="0 = every bouncing event")
    ap.add_argument("--skip-g", action="store_true")
    a = ap.parse_args()

    E = pd.read_csv(a.csv)
    B = E[E["dir"] == "bouncing"].reset_index(drop=True)
    B["knife"] = B["knife"].astype(bool)
    print("\nEVENT TABLE %s   all=%d  bouncing=%d  names=%d  dates=%d  %s -> %s\n" %
          (a.csv, len(E), len(B), B.symbol.nunique(), B.date.nunique(), E.date.min(), E.date.max()))

    nk = B.knife.eq(False)
    masks = {
        "baseline (bouncing)": pd.Series(True, index=B.index),
        "not-knife": nk,
        "mood>=25": AG_pass(B.mood, 25.0),
        "nk + mood>=25": nk & AG_pass(B.mood, 25.0),
        "nk + mood25 + DEF2": nk & AG_pass(B.mood, 25.0) & B.shelf_ok.astype(bool),
        "nk + mood25 + DEF3": nk & AG_pass(B.mood, 25.0) & B.rp_ok.astype(bool),
        "nk + mood25 + ANY def": nk & AG_pass(B.mood, 25.0)
                                 & (B.vc_ok.astype(bool) | B.shelf_ok.astype(bool) | B.rp_ok.astype(bool)),
        "DEF1 vc": B.vc_ok.astype(bool),
    }
    masks = {k: v.fillna(False).astype(bool) for k, v in masks.items()}
    q_b()
    q_ae(B, masks)
    q_c(B, masks)
    q_d(B, masks)
    q_f(B)
    if not a.skip_g:
        q_g(B, a.sample)
