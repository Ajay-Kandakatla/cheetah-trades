"""AMD "raided, not yet marked up" — measured against a placebo.

2026-09-13: INVERTED (−8.9pp) on 2,666 names with the old detector.
2026-09-14: RE-MEASURED after the detector learned to FAIL a cycle, on the wide
list (`full` ∪ `broad`, 3,712 names). Most of the inversion was the old
detector: it never ended a cycle on a close through the raided edge, so every
bar within 10 sessions of a raid whose base had ALREADY broken still counted
as "raided" — 237,802 such bars, as many as the real fires (240,461). Kept in
the repo, runnable verbatim, because every number printed under the 🌀 AMD
Raided tab comes from here.

RUN IT (staged — `walk` first, it writes the observation matrix the rest read):
    cd /Users/ajay/clinet-test/cheetah-market-app
    docker compose cp backend/scripts/turning_bullish_amd_study.py api:/tmp/amd.py
    docker compose exec -T api python /tmp/amd.py walk
    docker compose exec -T api python /tmp/amd.py stats
    docker compose exec -T api python /tmp/amd.py claim
    docker compose exec -T api python /tmp/amd.py subsets
    docker compose exec -T api python /tmp/amd.py overlap

Inside the api container ONLY. The walk is ~200s on 3,712 names: it calls the
REAL `supply_demand.amd.find_cycle` on `df.iloc[:t+1]` at EVERY bar — nothing
reimplemented, no every-Nth-bar sampling, no lookahead (the failure scan runs
to the end of the SLICE, never past t).

WHAT IT FOUND (2026-09-14, 3,712 names, 1,592,057 evaluated bars,
2024-12-09 → 2026-09-14, the detector as shipped — failed phase AND the
age-out that lets a base formed after a failure be the live read):
The state fires on 15.1% of all bars (30.3% on 2026-09-13 with the old
detector) and carries 759 of 3,634
names on the last close at the 10-session bound, 589 at the board's 3. Forward
returns against every other bar of the same names: 5d −0.36% [−0.77, −0.06],
10d −0.48% [−1.07, −0.02], 21d −0.41% [−1.11, +0.15]; medians span zero; win
rate 49.2% vs 50.7% at 5d. The page's ONE claim — a fresh raid precedes a
close above the base top within 21 sessions — against a like-for-like bar
sitting inside its own LIVE base at the same distance below the top: 51.9%
vs 56.1%, −4.2pp, 95% CI −6.92 to −1.89 (the wider of symbol- and date-block-
clustered), NEGATIVE IN ALL SEVEN distance buckets (−1.5 to −6.8pp). STILL
INVERTED, smaller than the −8.9pp of 2026-09-13. The board's own cut (raid
0-3 bars ago) is worse: 48.9% vs 54.4%, −5.6pp [−8.97, −2.69]; stale 4-10 is
−1.3pp [−3.12, +0.30]. Forward returns against the same like-for-like bar:
5d −0.34% [−0.63, −0.09], 10d −0.42% [−0.81, −0.07], 21d −0.47% [−1.39,
+0.28]. Narrower placebo pools all agree: never-distributed −4.1pp [−6.47,
−1.44], stale raid −2.9pp [−4.86, −0.66], already distributing −5.3pp
[−8.05, −2.60], live base only −5.3pp [−7.72, −2.71].

WHY THE FIRST RE-RUN THAT DAY SAID "NULL": with the failed phase but WITHOUT
the age-out, 57% of all bars sat in a dead base and the like-for-like placebo
was two-thirds dead-base bars (315,627 vs 513,007 now) — it measured −2.1pp
[−4.27, +0.08]. The numbers quoted anywhere are from the shipped detector.

Raid recency still separates nothing on returns: fresh (0-3) minus stale
(4-10) is −0.17% / −0.20% / −0.05% at 5/10/21d, every CI spanning zero. So
`turning_bullish.MAX_RAID_BARS_AGO = 3` is a BOARD-SIZE cut and must never be
described as an accuracy improvement.

THE TRAP THIS SCRIPT EXISTS TO DOCUMENT: with the obvious "edge still above
price" placebo the read measures +2.4pp [+0.19, +4.22] and could ship as a
small win. That pool is stuffed with names sitting far below a base and never
climbing back — the signal LOSES in all four near-distance buckets (0-5%:
−1.2, −1.0, −4.0, −4.5pp) and only "wins" from 5% out, i.e. entirely off
broken placebo names. The "module's own phase reads distribution within 21
bars" secondary is not like-for-like (a failed base cannot read distribution
without a whole new cycle) and is not quoted anywhere.
"""

from __future__ import annotations
import os, sys, json, time
import numpy as np

if "/app" not in sys.path:
    sys.path.insert(0, "/app")   # container package root

WARMUP = 60          # bars of history before the first evaluated bar
BARS_AGO_MAX = 10    # the STUDY's bound. The 🌀 board cuts at turning_bullish.MAX_RAID_BARS_AGO = 3:
                     # the fresh(0-3) cells below ARE the board; the headline is the wider state.
HORIZONS = (5, 10, 21)
REACH_H = 21         # window for "reaches a close above the base's top"
OUT = "/tmp/amd_obs.npz"

PHASE_CODE = {"accumulation": 0, "manipulation": 1, "distribution": 2, "failed": 3}

# The list both 🌀 studies walk (2026-09-14, Ajay: "there should be more names,
# about 4k is what we discussed"): the scan's `full` alias (Russell 3000 ∪
# S&P 1500 ∪ curated ∪ themes ∪ traders) UNION the 16:30 cron's `broad` list
# (R3000 ∪ microcap ∪ ETF) — 3,729 names in the container that day. The 🌀
# boards themselves draw from `full` (2,686), a subset.
UNIVERSE_MODES = ("full", "broad")


def study_universe():
    from sepa import universe as U
    syms = []
    for mode in UNIVERSE_MODES:
        syms.extend(U.load_universe(mode))
    return list(dict.fromkeys(syms))


def walk_symbol(sym):
    from sepa import prices
    from supply_demand.amd import find_cycle
    try:
        df = prices.load_prices(sym)
    except Exception as exc:                                   # noqa: BLE001
        return sym, "load_error:%s" % type(exc).__name__, None
    if df is None or len(df) < WARMUP + REACH_H + 5:
        return sym, "short:%d" % (0 if df is None else len(df)), None
    try:
        close = df["close"].to_numpy(dtype=float)
    except Exception:                                          # noqa: BLE001
        return sym, "bad_frame", None
    if not np.isfinite(close).all() or (close <= 0).any():
        return sym, "bad_close", None
    n = len(df)
    dates = np.array([int(str(d)[:10].replace("-", "")) for d in df.index], dtype=np.int32)

    rows = []
    for t in range(WARMUP, n):
        cyc = find_cycle(df.iloc[:t + 1], direction="bullish")
        if not cyc:
            rows.append((t, dates[t], -1, -1, np.nan, np.nan, close[t], -1))
            continue
        acc = cyc["accumulation"]
        man = cyc["manipulation"]
        fail = cyc.get("failure")
        # Strict lookup: a phase string this table does not know must raise,
        # never fold into "no cycle" (that would put its bars in every placebo).
        rows.append((t, dates[t], PHASE_CODE[cyc["phase"]],
                     int(man["bars_ago"]) if man else -1,
                     float(acc["hi"]), float(acc["lo"]), close[t],
                     int(fail["bars_ago"]) if fail else -1))

    t_idx = np.array([r[0] for r in rows], dtype=np.int32)
    d_ord = np.array([r[1] for r in rows], dtype=np.int32)
    phase = np.array([r[2] for r in rows], dtype=np.int8)
    bago = np.array([r[3] for r in rows], dtype=np.int16)
    b_hi = np.array([r[4] for r in rows], dtype=np.float64)
    b_lo = np.array([r[5] for r in rows], dtype=np.float64)
    c_t = np.array([r[6] for r in rows], dtype=np.float64)
    fago = np.array([r[7] for r in rows], dtype=np.int16)

    fwd = {}
    for h in HORIZONS:
        f = np.full(len(rows), np.nan)
        ok = t_idx + h <= n - 1
        f[ok] = close[t_idx[ok] + h] / c_t[ok] - 1.0
        fwd[h] = f

    # reach: does ANY close in (t, t+21] exceed this bar's own base top?
    reach = np.full(len(rows), -1, dtype=np.int8)
    for k, t in enumerate(t_idx):
        if not np.isfinite(b_hi[k]) or t + REACH_H > n - 1:
            continue
        reach[k] = 1 if (close[t + 1:t + 1 + REACH_H] > b_hi[k]).any() else 0

    # secondary: does the MODULE's own phase read "distribution" within 21 bars?
    reach_mod = np.full(len(rows), -1, dtype=np.int8)
    m = len(rows)
    for k in range(m):
        if k + REACH_H >= m:
            continue
        reach_mod[k] = 1 if (phase[k + 1:k + 1 + REACH_H] == 2).any() else 0

    fired = (phase == 1) & (bago >= 0) & (bago <= BARS_AGO_MAX)
    return sym, None, dict(t=t_idx, date=d_ord, phase=phase, bars_ago=bago,
                           fail_ago=fago,
                           base_hi=b_hi, base_lo=b_lo, close=c_t,
                           f5=fwd[5], f10=fwd[10], f21=fwd[21],
                           reach=reach, reach_mod=reach_mod,
                           fired=fired.astype(np.int8), n_bars=np.int32(n))


def _init():
    from sepa import prices
    prices._mongo_coll = None
    prices._mongo_disabled = False


def stage_walk():
    import multiprocessing as mp
    syms = study_universe()
    print("universe %s: %d names" % (" ∪ ".join(UNIVERSE_MODES), len(syms)), flush=True)
    t0 = time.time()
    keep, skipped = {}, {}
    with mp.Pool(16, initializer=_init) as pool:
        for i, (sym, err, d) in enumerate(pool.imap_unordered(walk_symbol, syms, chunksize=8)):
            if err:
                skipped[sym] = err
            else:
                keep[sym] = d
            if (i + 1) % 250 == 0:
                print("  %d/%d  %.0fs" % (i + 1, len(syms), time.time() - t0), flush=True)
    print("walked %d names, skipped %d, %.0fs" % (len(keep), len(skipped), time.time() - t0))
    from collections import Counter
    print("skip reasons:", Counter(v.split(":")[0] for v in skipped.values()))

    names = sorted(keep)
    flat, sid = {}, []
    for j, s in enumerate(names):
        d = keep[s]
        sid.append(np.full(len(d["t"]), j, dtype=np.int32))
        for k, v in d.items():
            if k == "n_bars":
                continue
            flat.setdefault(k, []).append(v)
    out = {k: np.concatenate(v) for k, v in flat.items()}
    out["sid"] = np.concatenate(sid)
    np.savez_compressed(OUT, names=np.array(names), skipped=np.array(json.dumps(skipped)), **out)
    print("saved %s  rows=%d" % (OUT, len(out["sid"])))


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def _clusters(labels):
    order = np.argsort(labels, kind="stable")
    ls = labels[order]
    bounds = np.flatnonzero(np.r_[True, ls[1:] != ls[:-1], True])
    return [order[bounds[i]:bounds[i + 1]] for i in range(len(bounds) - 1)]


def boot_diff(vals, mask_a, mask_b, groups, B=600, seed=7, stat="mean"):
    """Paired cluster bootstrap of (stat over A) - (stat over B).

    One resample of CLUSTERS feeds both arms, so the difference keeps the
    correlation that makes an unpaired interval too tight."""
    rng = np.random.default_rng(seed)
    cl = _clusters(groups)
    f = np.mean if stat == "mean" else np.median
    a_obs, b_obs = f(vals[mask_a]), f(vals[mask_b])
    da, db, dd = [], [], []
    ncl = len(cl)
    for _ in range(B):
        pick = rng.integers(0, ncl, ncl)
        idx = np.concatenate([cl[p] for p in pick])
        ma, mb = mask_a[idx], mask_b[idx]
        if ma.sum() < 5 or mb.sum() < 5:
            continue
        va, vb = f(vals[idx][ma]), f(vals[idx][mb])
        da.append(va); db.append(vb); dd.append(va - vb)
    q = lambda x: (float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5)))
    return dict(a=float(a_obs), b=float(b_obs), diff=float(a_obs - b_obs),
                a_ci=q(da), b_ci=q(db), diff_ci=q(dd), reps=len(dd))


def widest(*cis):
    lo = min(c[0] for c in cis); hi = max(c[1] for c in cis)
    return (lo, hi)


def pct(x):
    return "%+.2f%%" % (100 * x)


def report_cell(title, vals, fa, fb, sid, blk, B=600, stat="mean"):
    rs = boot_diff(vals, fa, fb, sid, B=B, stat=stat)
    rb = boot_diff(vals, fa, fb, blk, B=B, stat=stat)
    d_ci = widest(rs["diff_ci"], rb["diff_ci"])
    print("  %-26s A=%s (n=%d)  P=%s (n=%d)  lift=%s  95%%CI[%s, %s]%s"
          % (title, pct(rs["a"]), fa.sum(), pct(rs["b"]), fb.sum(),
             pct(rs["diff"]), pct(d_ci[0]), pct(d_ci[1]),
             "" if (d_ci[0] < 0 < d_ci[1]) else "  <-- excludes 0"))
    return rs, rb, d_ci


def stage_stats():
    z = np.load(OUT, allow_pickle=True)
    names = z["names"]; sid = z["sid"]
    phase = z["phase"]; bago = z["bars_ago"]; fired = z["fired"].astype(bool)
    date = z["date"]; close = z["close"]; b_hi = z["base_hi"]
    reach = z["reach"]; reach_mod = z["reach_mod"]
    skipped = json.loads(str(z["skipped"]))
    N = len(sid)

    udates = np.unique(date)
    dpos = np.searchsorted(udates, date)

    print("=" * 78)
    print("SAMPLE")
    print("  names walked          %d   (universe %s; %d skipped)" % (len(names), " ∪ ".join(UNIVERSE_MODES), len(skipped)))
    print("  evaluated bars        %d" % N)
    print("  date span             %s .. %s  (%d sessions)" % (udates[0], udates[-1], len(udates)))
    print("  bars/name             median %d" % int(np.median(np.bincount(sid))))

    print("\nPHASE MIX over all evaluated bars")
    for code, nm in ((-1, "no cycle"), (0, "accumulation"), (1, "manipulation"), (2, "distribution"), (3, "failed")):
        k = (phase == code).sum()
        print("  %-14s %9d  %5.1f%%" % (nm, k, 100 * k / N))

    print("\n1) FIRE RATE  (study state: phase==manipulation AND bars_ago<=%d; the board cuts at 3)" % BARS_AGO_MAX)
    print("  fires on              %d / %d bars = %.1f%% of all evaluated bars" % (fired.sum(), N, 100 * fired.mean()))
    dead = (phase == 3) & (bago >= 0) & (bago <= BARS_AGO_MAX)
    print("  base FAILED within %d bars of its raid: %d bars (%.1f%%) — the 2026-09-13 detector counted these as fired"
          % (BARS_AGO_MAX, dead.sum(), 100 * dead.mean()))
    nf = np.bincount(sid[fired], minlength=len(names))
    print("  names that ever fire  %d / %d (%.0f%%)" % ((nf > 0).sum(), len(names), 100 * (nf > 0).mean()))
    comp = phase == 2
    print("  completed 'bullish' (phase==distribution) fires on %.1f%% of bars" % (100 * comp.mean()))

    last = date == udates[-1]
    print("\n   TODAY'S BOARD (last closed bar %s)" % udates[-1])
    print("     names with a bar   %d" % last.sum())
    print("     near-bullish       %d  (%.1f%%)" % ((last & fired).sum(), 100 * (last & fired).sum() / last.sum()))
    print("     completed bullish  %d  (%.1f%%)" % ((last & comp).sum(), 100 * (last & comp).sum() / last.sum()))
    b03 = last & fired & (bago <= 3)
    print("     of which raid 0-3d %d ; raid 4-10d %d" % (b03.sum(), (last & fired & (bago > 3)).sum()))
    tickers = [str(names[s]) for s in np.unique(sid[last & fired])]
    print("     board: %s" % (", ".join(tickers[:40]) + (" ..." if len(tickers) > 40 else "")))

    blk = {}
    for h in HORIZONS:
        blk[h] = (dpos // h).astype(np.int32)

    print("\n2) FORWARD RETURNS  vs PLACEBO (every non-firing evaluated bar, same names/window)")
    print("   paired cluster bootstrap, 600 reps; CI = WIDER of by-symbol and by-date-block")
    res = {}
    for h in HORIZONS:
        v = z["f%d" % h]
        ok = np.isfinite(v)
        fa = fired & ok
        fb = (~fired) & ok
        print("\n  %dd forward" % h)
        res[(h, "mean")] = report_cell("mean", v, fa, fb, sid, blk[h], stat="mean")
        res[(h, "median")] = report_cell("median", v, fa, fb, sid, blk[h], stat="median")
        wa = (v[fa] > 0).mean(); wb = (v[fb] > 0).mean()
        print("    win rate            A=%.1f%%  P=%.1f%%  lift=%+.1fpp" % (100 * wa, 100 * wb, 100 * (wa - wb)))

    print("\n3) RAID RECENCY  bars_ago 0-3 vs 4-10 (both arms are firing bars)")
    for h in HORIZONS:
        v = z["f%d" % h]
        ok = np.isfinite(v)
        a = fired & ok & (bago <= 3)
        b = fired & ok & (bago > 3)
        print("  %dd" % h)
        report_cell("fresh(0-3) - stale(4-10)", v, a, b, sid, blk[h], stat="mean")
        report_cell("  median", v, a, b, sid, blk[h], stat="median")

    print("\n4) THE CLAIM: does 'raided, not yet marked up' PRECEDE the markup?")
    print("   event = a CLOSE above THIS BAR'S OWN base top within %d sessions." % REACH_H)
    r_ok = reach >= 0
    rv = reach.astype(float)
    above = close > b_hi
    hasb = np.isfinite(b_hi)

    variants = [
        ("literal placebo (all non-firing bars)", r_ok & (~fired) & hasb),
        ("fair placebo (edge still ABOVE price)", r_ok & (~fired) & hasb & (~above)),
    ]
    fa = fired & r_ok & hasb
    for label, fb in variants:
        print("\n  %s" % label)
        report_cell("reach rate", rv, fa, fb, sid, blk[21], stat="mean")

    print("\n  distance-matched (bucket by how far the base top sits above the close)")
    gap = np.where(hasb & (close > 0), b_hi / np.maximum(close, 1e-9) - 1.0, np.nan)
    edges = [0.0, 0.01, 0.02, 0.035, 0.05, 0.08, 0.15, 1e9]
    tot_a = tot_b = 0.0; na = nb = 0
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        m = hasb & np.isfinite(gap) & (gap >= lo) & (gap < hi) & r_ok
        a = m & fired; b = m & (~fired)
        if a.sum() < 30 or b.sum() < 30:
            continue
        ra, rb = rv[a].mean(), rv[b].mean()
        tot_a += ra * a.sum(); na += a.sum()
        tot_b += rb * a.sum(); nb += a.sum()   # reweight placebo to SIGNAL's gap mix
        print("    %5.1f-%5.1f%%   signal %5.1f%% (n=%6d)   placebo %5.1f%% (n=%7d)   lift %+5.1fpp"
              % (100 * lo, 100 * min(hi, 1), 100 * ra, a.sum(), 100 * rb, b.sum(), 100 * (ra - rb)))
    if na:
        print("    gap-weighted:  signal %.1f%%   placebo(reweighted to signal's gap mix) %.1f%%   lift %+.1fpp"
              % (100 * tot_a / na, 100 * tot_b / nb, 100 * (tot_a / na - tot_b / nb)))

    print("\n  secondary: module's OWN phase reads 'distribution' within 21 bars")
    m_ok = reach_mod >= 0
    rm = reach_mod.astype(float)
    report_cell("phase->distribution", rm, fired & m_ok, (~fired) & m_ok, sid, blk[21], stat="mean")

    print("\n  by raid recency")
    report_cell("fresh(0-3)", rv, fired & r_ok & (bago <= 3), r_ok & (~fired) & hasb & (~above), sid, blk[21])
    report_cell("stale(4-10)", rv, fired & r_ok & (bago > 3), r_ok & (~fired) & hasb & (~above), sid, blk[21])
    print("=" * 78)


def stage_overlap():
    """Latest-bar overlap of the two boards, by their own verdict grades."""
    import multiprocessing as mp
    syms = study_universe()

    with mp.Pool(16, initializer=_init) as pool:
        out = pool.map(_last_bar, syms, chunksize=8)
    amd = {s for s, a, k in out if a}
    kel = {s for s, a, k in out if k}
    both = amd & kel
    print("latest-bar BOARDS: 🌀 AMD Raided %d, 🌀 KC Coiled %d, BOTH %d"
          % (len(amd), len(kel), len(both)))
    print("  AMD∩Kel / AMD = %.1f%%   AMD∩Kel / Kel = %.1f%%"
          % (100 * len(both) / max(len(amd), 1), 100 * len(both) / max(len(kel), 1)))
    n_ok = sum(1 for s, a, k in out if a is not None)
    exp = len(amd) * len(kel) / max(n_ok, 1)
    print("  expected overlap if independent: %.1f  observed: %d" % (exp, len(both)))
    print("  both: %s" % ", ".join(sorted(both)[:40]))


def _last_bar(sym):
    """The two BOARDS' own predicates on the last closed bar (2026-09-14;
    before this the Keltner arm was re-implemented by hand with no upper-band
    exclusion and the AMD arm used the study's 10-bar bound, so the printed
    overlap was of two sets neither tab shows)."""
    from sepa import prices
    from supply_demand import turning_bullish as TB
    try:
        df = prices.load_prices(sym)
        if df is None or len(df) < 80:
            return sym, None, None
        a = (TB.amd_verdict(df) or {}).get("grade") == TB.AMD_TURNING
        k = (TB.keltner_verdict(df) or {}).get("grade") == TB.KELTNER_TURNING
        return sym, bool(a), bool(k)
    except Exception:                                          # noqa: BLE001
        return sym, None, None


def _boot_weighted(vals, fa, fb, bucket, groups, w, B=600, seed=11):
    """Paired cluster bootstrap of a GAP-REWEIGHTED rate difference.

    Weights come from the SIGNAL's own gap mix over the full sample, so the
    placebo is asked the same question at the same distance from the level.
    Buckets empty in a replicate are dropped and the weights renormalised."""
    rng = np.random.default_rng(seed)
    cl = _clusters(groups)
    ncl = len(cl)
    ks = sorted(w)

    def _lift(idx):
        va, vb, ww = [], [], []
        v = vals[idx]; ba = fa[idx]; bb = fb[idx]; bk = bucket[idx]
        for k in ks:
            ma = ba & (bk == k); mb = bb & (bk == k)
            if ma.sum() < 5 or mb.sum() < 5:
                continue
            va.append(v[ma].mean()); vb.append(v[mb].mean()); ww.append(w[k])
        if not ww:
            return None
        ww = np.array(ww) / sum(ww)
        return float((ww * np.array(va)).sum()), float((ww * np.array(vb)).sum())

    base = _lift(np.arange(len(vals)))
    dd = []
    for _ in range(B):
        idx = np.concatenate([cl[p] for p in rng.integers(0, ncl, ncl)])
        r = _lift(idx)
        if r:
            dd.append(r[0] - r[1])
    return dict(a=base[0], b=base[1], diff=base[0] - base[1],
                diff_ci=(float(np.percentile(dd, 2.5)), float(np.percentile(dd, 97.5))),
                reps=len(dd))


def stage_claim():
    """The decisive control for the PRECEDES claim.

    A firing bar is, by construction, price INSIDE its own base (it raided the
    low and closed back in). The naive placebo pools bars that have collapsed
    far below the base, which almost never climb back, so it flatters the
    signal. This restricts the placebo to the same geometry and then matches on
    distance to the level as well."""
    z = np.load(OUT, allow_pickle=True)
    sid = z["sid"]; date = z["date"]; close = z["close"]
    b_hi = z["base_hi"]; b_lo = z["base_lo"]
    fired = z["fired"].astype(bool); reach = z["reach"]; bago = z["bars_ago"]
    udates = np.unique(date); dpos = np.searchsorted(udates, date)
    blk21 = (dpos // 21).astype(np.int32)
    hasb = np.isfinite(b_hi)
    r_ok = reach >= 0
    rv = reach.astype(float)
    gap = np.where(hasb & (close > 0), b_hi / np.maximum(close, 1e-9) - 1.0, np.nan)
    inside = hasb & (close <= b_hi) & (close >= b_lo)

    print("GEOMETRY of the two arms (bars with a base and a full 21-bar future)")
    for nm, m in (("signal (fired)", fired & r_ok & hasb),
                  ("placebo: edge above price", (~fired) & r_ok & hasb & (close < b_hi)),
                  ("placebo: INSIDE the base", (~fired) & r_ok & inside)):
        print("  %-28s n=%8d  median gap to top %5.2f%%" % (nm, m.sum(), 100 * np.nanmedian(gap[m])))
    print("  signal inside its base: %.1f%% of firing bars" % (100 * (fired & r_ok & inside).sum() / (fired & r_ok & hasb).sum()))

    edges = [0.0, 0.01, 0.02, 0.035, 0.05, 0.08, 0.15, 1e9]
    bucket = np.full(len(sid), -1, dtype=np.int8)
    for i in range(len(edges) - 1):
        bucket[np.isfinite(gap) & (gap >= edges[i]) & (gap < edges[i + 1])] = i

    fa = fired & r_ok & hasb & (bucket >= 0)
    w = {}
    for i in range(len(edges) - 1):
        c = (fa & (bucket == i)).sum()
        if c:
            w[i] = float(c)

    for label, fb in (("edge-above-price placebo", (~fired) & r_ok & hasb & (close < b_hi) & (bucket >= 0)),
                      ("INSIDE-THE-BASE placebo", (~fired) & r_ok & inside & (bucket >= 0))):
        print("\n%s  (reach a close above the base top within 21 sessions)" % label)
        for i in range(len(edges) - 1):
            a = fa & (bucket == i); b = fb & (bucket == i)
            if a.sum() < 30 or b.sum() < 30:
                continue
            print("   gap %5.1f-%5.1f%%   signal %5.1f%% (n=%6d)   placebo %5.1f%% (n=%7d)   lift %+5.1fpp"
                  % (100 * edges[i], 100 * min(edges[i + 1], 1), 100 * rv[a].mean(), a.sum(),
                     100 * rv[b].mean(), b.sum(), 100 * (rv[a].mean() - rv[b].mean())))
        for gname, g in (("by-symbol", sid), ("by-date-block", blk21)):
            r = _boot_weighted(rv, fa, fb, bucket, g, w)
            print("   GAP-MATCHED  signal %.1f%%  placebo %.1f%%  lift %+.2fpp  95%%CI[%+.2f, %+.2f]pp  (%s clusters)"
                  % (100 * r["a"], 100 * r["b"], 100 * r["diff"],
                     100 * r["diff_ci"][0], 100 * r["diff_ci"][1], gname))

    print("\nSame control on FORWARD RETURNS (placebo = inside its base, gap-matched)")
    for h in HORIZONS:
        v = z["f%d" % h]
        ok = np.isfinite(v)
        a = fired & ok & hasb & (bucket >= 0)
        b = (~fired) & ok & inside & (bucket >= 0)
        wf = {}
        for i in range(len(edges) - 1):
            c = (a & (bucket == i)).sum()
            if c:
                wf[i] = float(c)
        blkh = (dpos // h).astype(np.int32)
        cis = []
        for g in (sid, blkh):
            r = _boot_weighted(v, a, b, bucket, g, wf)
            cis.append(r)
        lo = min(c["diff_ci"][0] for c in cis); hi = max(c["diff_ci"][1] for c in cis)
        print("  %2dd  signal %+.2f%%  placebo %+.2f%%  lift %+.2f%%  95%%CI[%+.2f%%, %+.2f%%]  n=%d/%d"
              % (h, 100 * cis[0]["a"], 100 * cis[0]["b"], 100 * cis[0]["diff"],
                 100 * lo, 100 * hi, a.sum(), b.sum()))

    print("\nRAID RECENCY under the same control (gap-matched vs inside-base placebo)")
    fb = (~fired) & r_ok & inside & (bucket >= 0)
    for nm, a in (("fresh 0-3", fired & r_ok & hasb & (bucket >= 0) & (bago <= 3)),
                  ("stale 4-10", fired & r_ok & hasb & (bucket >= 0) & (bago > 3))):
        wf = {}
        for i in range(len(edges) - 1):
            c = (a & (bucket == i)).sum()
            if c:
                wf[i] = float(c)
        rs = _boot_weighted(rv, a, fb, bucket, sid, wf)
        rb = _boot_weighted(rv, a, fb, bucket, blk21, wf)
        lo = min(rs["diff_ci"][0], rb["diff_ci"][0]); hi = max(rs["diff_ci"][1], rb["diff_ci"][1])
        print("  %-11s reach %.1f%%  placebo %.1f%%  lift %+.2fpp  95%%CI[%+.2f, %+.2f]pp  n=%d"
              % (nm, 100 * rs["a"], 100 * rs["b"], 100 * rs["diff"], 100 * lo, 100 * hi, a.sum()))


def stage_subsets():
    """Is the inversion just the placebo containing already-proven names?

    Re-runs the gap-matched reach comparison against narrower placebo pools.
    The fourth pool (2026-09-14) is the like-for-like placebo restricted to a
    LIVE base — a bar whose own base has not failed — because the signal's
    definition excludes dead bases and the placebo should be asked the same
    question. Read the print; the conclusion is not hard-coded here."""
    z = np.load(OUT, allow_pickle=True)
    sid = z["sid"]; date = z["date"]; close = z["close"]
    b_hi = z["base_hi"]; b_lo = z["base_lo"]; phase = z["phase"]; bago = z["bars_ago"]
    fired = z["fired"].astype(bool); reach = z["reach"]
    ud = np.unique(date); blk = (np.searchsorted(ud, date) // 21).astype(np.int32)
    hasb = np.isfinite(b_hi); r_ok = reach >= 0; rv = reach.astype(float)
    gap = np.where(hasb & (close > 0), b_hi / np.maximum(close, 1e-9) - 1.0, np.nan)
    inside = hasb & (close <= b_hi) & (close >= b_lo)
    edges = [0.0, 0.01, 0.02, 0.035, 0.05, 0.08, 0.15, 1e9]
    bucket = np.full(len(sid), -1, dtype=np.int8)
    for i in range(len(edges) - 1):
        bucket[np.isfinite(gap) & (gap >= edges[i]) & (gap < edges[i + 1])] = i
    fa = fired & r_ok & hasb & (bucket >= 0)
    w = {i: float((fa & (bucket == i)).sum()) for i in range(len(edges) - 1)
         if (fa & (bucket == i)).sum()}
    cases = {
        "inside base, NEVER distributed": (~fired) & r_ok & inside & (bucket >= 0) & (phase != 2),
        "inside base, stale raid (bars_ago>10)": (~fired) & r_ok & inside & (bucket >= 0) & (phase == 1) & (bago > 10),
        "inside base, phase==distribution": (~fired) & r_ok & inside & (bucket >= 0) & (phase == 2),
        "inside a LIVE base (phase != failed)": (~fired) & r_ok & inside & (bucket >= 0) & (phase != 3),
    }
    for nm, fb in cases.items():
        rs = _boot_weighted(rv, fa, fb, bucket, sid, w, B=400)
        rb = _boot_weighted(rv, fa, fb, bucket, blk, w, B=400)
        lo = min(rs["diff_ci"][0], rb["diff_ci"][0]); hi = max(rs["diff_ci"][1], rb["diff_ci"][1])
        print("%-40s signal %.1f%%  placebo %.1f%%  lift %+.2fpp  95%%CI[%+.2f,%+.2f]pp  n_p=%d"
              % (nm, 100 * rs["a"], 100 * rs["b"], 100 * rs["diff"], 100 * lo, 100 * hi, fb.sum()))
    print("firing bars NOT inside their base: %.1f%%"
          % (100 * (fired & r_ok & hasb & ~inside).sum() / (fired & r_ok & hasb).sum()))


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "walk"
    {"walk": stage_walk, "stats": stage_stats, "overlap": stage_overlap,
     "claim": stage_claim, "subsets": stage_subsets}[stage]()
