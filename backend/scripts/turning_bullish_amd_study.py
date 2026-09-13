"""AMD "raided, not yet marked up" — measured against a placebo (2026-09-13).

THE RESULT IS INVERTED, and more clearly than the Keltner one. Kept in the
repo, runnable verbatim, because every number printed under the 🌀 AMD Raided
tab comes from here.

RUN IT (staged — `walk` first, it writes the observation matrix the rest read):
    cd /Users/ajay/clinet-test/cheetah-market-app
    docker compose cp backend/scripts/turning_bullish_amd_study.py api:/tmp/amd.py
    docker compose exec -T api python /tmp/amd.py walk
    docker compose exec -T api python /tmp/amd.py stats
    docker compose exec -T api python /tmp/amd.py claim
    docker compose exec -T api python /tmp/amd.py subsets
    docker compose exec -T api python /tmp/amd.py overlap

Inside the api container ONLY. The walk is ~79s: it calls the REAL
`supply_demand.amd.find_cycle` on `df.iloc[:t+1]` at EVERY bar — nothing
reimplemented, no every-Nth-bar sampling, no lookahead.

WHAT IT FOUND:
2,666 names, 1,150,446 evaluated bars. The state fires on 30.3% of ALL bars
and carries 1,201 of 2,621 names on the last close — a description of the
tape, not a selection. Forward returns are a null leaning negative (21d lift
−0.25%, CI −1.30 to +0.72; every horizon spans zero). And the page's ONE claim
is backwards: against a like-for-like bar sitting inside its own base at the
same distance below the top, a fresh raid makes a close above that top within
21 sessions LESS likely — 42.7% vs 51.6%, −8.9pp [−11.42, −5.91], negative in
all seven distance buckets and monotonically worse with distance.

Raid recency does NOT rescue it: 0-3 bars vs 4-10 separates nothing, and fresh
leans worse. So `turning_bullish.MAX_RAID_BARS_AGO = 3` is a BOARD-SIZE cut and
must never be described as an accuracy improvement.

THE TRAP THIS SCRIPT EXISTS TO DOCUMENT: with the obvious "edge still above
price" placebo the read measures +7.3pp and would have shipped as a win. That
pool is stuffed with names that collapsed far below their base and never climb
back — the signal LOSES in every near-distance bucket and only "wins" at 8-15%
and >15%, i.e. entirely off broken placebo names.
"""

from __future__ import annotations
import os, sys, json, time
import numpy as np

if "/app" not in sys.path:
    sys.path.insert(0, "/app")   # container package root

WARMUP = 60          # bars of history before the first evaluated bar
BARS_AGO_MAX = 10    # the verdict's own recency gate
HORIZONS = (5, 10, 21)
REACH_H = 21         # window for "reaches a close above the base's top"
OUT = "/tmp/amd_obs.npz"

PHASE_CODE = {"accumulation": 0, "manipulation": 1, "distribution": 2}


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
            rows.append((t, dates[t], -1, -1, np.nan, np.nan, close[t]))
            continue
        acc = cyc["accumulation"]
        man = cyc["manipulation"]
        rows.append((t, dates[t], PHASE_CODE.get(cyc["phase"], -1),
                     int(man["bars_ago"]) if man else -1,
                     float(acc["hi"]), float(acc["lo"]), close[t]))

    t_idx = np.array([r[0] for r in rows], dtype=np.int32)
    d_ord = np.array([r[1] for r in rows], dtype=np.int32)
    phase = np.array([r[2] for r in rows], dtype=np.int8)
    bago = np.array([r[3] for r in rows], dtype=np.int16)
    b_hi = np.array([r[4] for r in rows], dtype=np.float64)
    b_lo = np.array([r[5] for r in rows], dtype=np.float64)
    c_t = np.array([r[6] for r in rows], dtype=np.float64)

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
    from sepa import universe as U
    syms = U.load_universe("full")
    syms = [s for s in dict.fromkeys(syms)]
    print("universe full: %d names" % len(syms), flush=True)
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
    print("  names walked          %d   (universe 'full' = 2680; %d skipped)" % (len(names), len(skipped)))
    print("  evaluated bars        %d" % N)
    print("  date span             %s .. %s  (%d sessions)" % (udates[0], udates[-1], len(udates)))
    print("  bars/name             median %d" % int(np.median(np.bincount(sid))))

    print("\nPHASE MIX over all evaluated bars")
    for code, nm in ((-1, "no cycle"), (0, "accumulation"), (1, "manipulation"), (2, "distribution")):
        k = (phase == code).sum()
        print("  %-14s %9d  %5.1f%%" % (nm, k, 100 * k / N))

    print("\n1) FIRE RATE  (verdict: phase==manipulation AND bars_ago<=%d)" % BARS_AGO_MAX)
    print("  fires on              %d / %d bars = %.1f%% of all evaluated bars" % (fired.sum(), N, 100 * fired.mean()))
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
    """Latest-bar overlap with the Keltner near-bullish verdict."""
    from sepa import universe as U
    import multiprocessing as mp
    syms = U.load_universe("full")

    with mp.Pool(16, initializer=_init) as pool:
        out = pool.map(_last_bar, syms, chunksize=8)
    amd = {s for s, a, k in out if a}
    kel = {s for s, a, k in out if k}
    both = amd & kel
    print("latest-bar sets: AMD near-bullish %d, Keltner near-bullish %d, BOTH %d"
          % (len(amd), len(kel), len(both)))
    print("  AMD∩Kel / AMD = %.1f%%   AMD∩Kel / Kel = %.1f%%"
          % (100 * len(both) / max(len(amd), 1), 100 * len(both) / max(len(kel), 1)))
    n_ok = sum(1 for s, a, k in out if a is not None)
    exp = len(amd) * len(kel) / max(n_ok, 1)
    print("  expected overlap if independent: %.1f  observed: %d" % (exp, len(both)))
    print("  both: %s" % ", ".join(sorted(both)[:40]))


def _last_bar(sym):
    from sepa import prices
    from supply_demand.amd import find_cycle
    from supply_demand import keltner as K
    try:
        df = prices.load_prices(sym)
        if df is None or len(df) < 80:
            return sym, None, None
        cyc = find_cycle(df, direction="bullish")
        a = bool(cyc and cyc["phase"] == "manipulation"
                 and cyc["manipulation"] and cyc["manipulation"]["bars_ago"] <= BARS_AGO_MAX)
        ch = K.channel(df); sq = K.squeeze(df)
        mid = df["close"].ewm(span=20, adjust=False).mean().to_numpy()
        rising = len(mid) > 21 and mid[-1] > mid[-21]
        k = bool((sq.get("on") or sq.get("released"))
                 and ch and ch.get("position") is not None
                 and ch["position"] >= 0.5 and rising)
        return sym, a, k
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

    Re-runs the gap-matched reach comparison against three narrower placebo
    pools. All three stay negative, so it is not."""
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
