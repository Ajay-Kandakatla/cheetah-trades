"""Keltner "coiled, leaning up" — measured against a placebo (2026-09-13).

THE RESULT IS INVERTED. Ajay asked for a board of names "very close to bullish
in keltners"; this script is what says whether that claim holds, and it does
not. Kept in the repo, runnable verbatim, because every number printed under
the 🌀 KC Coiled tab comes from here and his standing rule is that a measured
number on a board he trades ships with its script and its CI.

RUN IT:
    cd /Users/ajay/clinet-test/cheetah-market-app
    docker compose exec -T api python - < backend/scripts/turning_bullish_keltner_study.py

Inside the api container ONLY — that is the one place the Massive key lives,
and a throwaway container falls back to Yahoo and prints false negatives.
Takes ~55s. Read-only: touches nothing in the repo or in Mongo.

WHAT IT FOUND, in one paragraph so nobody has to re-run it to know:
2,660 names, 1,200,755 closed daily bars, 2024-09-12 → 2026-09-11. The verdict
fires on 5.39% of bars (144 names on the last close). Forward returns are
NEGATIVE at every horizon with every lift CI clear of zero — 21d median lift
−0.33pp [−0.57, −0.12] against the placebo. Against a control differing by
exactly ONE clause (same upper half, same rising EMA, no squeeze) the squeeze
contributes nothing (21d +0.11pp [−0.17, +0.41]) and makes the upper-band
break 14.8pp LESS likely (40.0% vs 55.0%). The one positive cell in the whole
study is coil length 21+ bars (n=2,538, 471 names), which beats the matched
control at all three horizons — one bucket of four, disagreeing with the other
three, and four names on today's board. Exploratory, not a rule.
"""

import json
import sys
import time

import numpy as np
import pandas as pd

from sepa import prices
from sepa import universe as U
from supply_demand import keltner as K

SEED = 42
HORIZONS = (5, 10, 21)
FIRST_BAR = 41          # needs >= 42 bars for squeeze()
PRECEDE_WIN = 21
B_FIRED = 500
B_PLACEBO = 250
MIN_BARS_SYMBOL = 120   # need some history to be worth walking

rng = np.random.default_rng(SEED)


# ---------------------------------------------------------------- per symbol
def series_for(df):
    """Every keltner.py quantity, as a per-bar array. None when unusable."""
    if df is None or len(df) < MIN_BARS_SYMBOL:
        return None
    close = df["close"].astype(float)
    if not np.isfinite(close.to_numpy()).all() or (close <= 0).any():
        return None

    mid = close.ewm(span=K.EMA_LEN, adjust=False).mean()
    atr = K._atr(df, K.ATR_LEN)                       # module's own Wilder ATR

    upper = mid + K.MULT * atr
    lower = mid - K.MULT * atr
    span = (upper - lower).to_numpy()
    pos = np.full(len(df), np.nan)
    ok = np.isfinite(span) & (span > 0)
    pos[ok] = np.round((close.to_numpy()[ok] - lower.to_numpy()[ok]) / span[ok], 3)

    # squeeze: Bollinger(20,2) inside Keltner(1.5*ATR)
    k_up = (mid + K.SQUEEZE_MULT * atr).to_numpy()
    k_dn = (mid - K.SQUEEZE_MULT * atr).to_numpy()
    bb_mid = close.rolling(K.BB_LEN).mean()
    bb_sd = close.rolling(K.BB_LEN).std(ddof=0)
    b_up = (bb_mid + K.BB_STD * bb_sd).to_numpy()
    b_dn = (bb_mid - K.BB_STD * bb_sd).to_numpy()
    with np.errstate(invalid="ignore"):
        on = (b_up < k_up) & (b_dn > k_dn)
    on = np.nan_to_num(on, nan=False).astype(bool)

    n = len(df)
    released = np.zeros(n, bool)
    released[1:] = on[:-1] & ~on[1:]

    # consecutive on-run ending at i (module's squeeze["bars"], 0 when off)
    bars = np.zeros(n, int)
    run = 0
    ended = np.zeros(n, int)     # length of the run that ended just before i
    for i in range(n):
        if on[i]:
            run += 1
        else:
            if run:
                ended[i] = run
            run = 0
        bars[i] = run if on[i] else 0
    # coil length carried into the release bar (module reports bars=0 there)
    coil_len = np.where(on, bars, ended)

    mid_a = mid.to_numpy()
    rise = np.zeros(n, bool)
    rise[K.EMA_LEN:] = mid_a[K.EMA_LEN:] > mid_a[:-K.EMA_LEN]

    atr_a = atr.to_numpy()
    valid = np.zeros(n, bool)
    valid[FIRST_BAR:] = True
    valid &= np.isfinite(pos) & np.isfinite(mid_a) & np.isfinite(atr_a) & (atr_a > 0)

    fired = valid & (on | released) & (pos >= 0.5) & rise
    return {"close": close.to_numpy(), "pos": pos, "on": on, "released": released,
            "bars": bars, "coil_len": coil_len, "valid": valid, "fired": fired,
            "rise": rise, "dates": df.index}


def fwd(close, h):
    out = np.full(len(close), np.nan)
    if len(close) > h:
        out[:-h] = close[h:] / close[:-h] - 1.0
    return out


# ------------------------------------------------------------------ bootstrap
def _flat(per_sym):
    """[(sym, arr)] -> (big array, list of (start, stop))."""
    arrs = [a for _, a in per_sym]
    if not arrs:
        return np.array([]), []
    big = np.concatenate(arrs)
    slices, k = [], 0
    for a in arrs:
        slices.append((k, k + len(a)))
        k += len(a)
    return big, slices


def cluster_ci(per_sym, B, stat="median"):
    """Symbol-clustered bootstrap CI. per_sym = [(sym, values array)]."""
    big, slices = _flat(per_sym)
    if len(big) == 0:
        return {"n": 0, "n_sym": 0, "point": None, "lo": None, "hi": None}
    fn = np.median if stat == "median" else np.mean
    point = float(fn(big))
    m = len(slices)
    draws = np.empty(B)
    for b in range(B):
        pick = rng.integers(0, m, m)
        draws[b] = fn(np.concatenate([big[slices[j][0]:slices[j][1]] for j in pick]))
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return {"n": int(len(big)), "n_sym": m, "point": point,
            "lo": float(lo), "hi": float(hi)}


def cluster_prop_ci(per_sym_kn, B=2000):
    """Clustered bootstrap CI for a pooled proportion. [(sym, k, n)]."""
    if not per_sym_kn:
        return {"n": 0, "k": 0, "point": None, "lo": None, "hi": None}
    k = np.array([x[1] for x in per_sym_kn], float)
    n = np.array([x[2] for x in per_sym_kn], float)
    tot_n, tot_k = n.sum(), k.sum()
    if tot_n == 0:
        return {"n": 0, "k": 0, "point": None, "lo": None, "hi": None}
    point = tot_k / tot_n
    m = len(n)
    draws = np.empty(B)
    for b in range(B):
        pick = rng.integers(0, m, m)
        nn = n[pick].sum()
        draws[b] = k[pick].sum() / nn if nn else np.nan
    lo, hi = np.nanpercentile(draws, [2.5, 97.5])
    return {"n": int(tot_n), "k": int(tot_k), "point": float(point),
            "lo": float(lo), "hi": float(hi)}


def paired_prop_diff_ci(rows, B=2000):
    """CI on (rate A - rate B) where both rates come from the SAME resampled
    symbols. rows = [(sym, kA, nA, kB, nB)]."""
    if not rows:
        return {"point": None, "lo": None, "hi": None}
    ka = np.array([r[1] for r in rows], float); na = np.array([r[2] for r in rows], float)
    kb = np.array([r[3] for r in rows], float); nb = np.array([r[4] for r in rows], float)
    if na.sum() == 0 or nb.sum() == 0:
        return {"point": None, "lo": None, "hi": None}
    point = ka.sum() / na.sum() - kb.sum() / nb.sum()
    m = len(rows); draws = np.empty(B)
    for b in range(B):
        pick = rng.integers(0, m, m)
        sa, sb = na[pick].sum(), nb[pick].sum()
        draws[b] = (ka[pick].sum() / sa if sa else np.nan) - (kb[pick].sum() / sb if sb else np.nan)
    lo, hi = np.nanpercentile(draws, [2.5, 97.5])
    return {"point": float(point), "lo": float(lo), "hi": float(hi)}


def diff_ci(a_per_sym, b_per_sym, B=400, stat="median"):
    """CI on (group A stat - group B stat), resampling symbols in BOTH."""
    A, sa = _flat(a_per_sym)
    Bb, sb = _flat(b_per_sym)
    if len(A) == 0 or len(Bb) == 0:
        return {"point": None, "lo": None, "hi": None}
    fn = np.median if stat == "median" else np.mean
    point = float(fn(A) - fn(Bb))
    ma, mb = len(sa), len(sb)
    draws = np.empty(B)
    for b in range(B):
        pa = rng.integers(0, ma, ma)
        pb = rng.integers(0, mb, mb)
        va = fn(np.concatenate([A[sa[j][0]:sa[j][1]] for j in pa]))
        vb = fn(np.concatenate([Bb[sb[j][0]:sb[j][1]] for j in pb]))
        draws[b] = va - vb
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return {"point": point, "lo": float(lo), "hi": float(hi)}


def pct(d, mult=100.0):
    if d.get("point") is None:
        return "n/a"
    return "%+.2f%% [%+.2f, %+.2f]" % (d["point"] * mult, d["lo"] * mult, d["hi"] * mult)


# ----------------------------------------------------------------------- main
def main():
    t0 = time.time()
    syms = U.load_universe()
    order = list(syms)
    rng2 = np.random.default_rng(SEED)
    rng2.shuffle(order)

    fired_fwd = {h: [] for h in HORIZONS}      # [(sym, arr)]
    plac_fwd = {h: [] for h in HORIZONS}
    bucket_fwd = {}                            # bucket -> h -> [(sym, arr)]
    matched_fwd = {h: [] for h in HORIZONS}   # SECONDARY control, see report
    prec_fired, prec_plac, prec_plac_hi = [], [], []
    prec_paired_all, prec_paired_hi = [], []
    bucket_prec = {}
    tot_valid = tot_fired = 0
    board_today, board_dates, board_liq = [], {}, {}
    names_used, names_fired = 0, 0
    skipped_nodata = skipped_short = 0
    coil_lens_today = {}

    def bucket_of(L):
        if L <= 5:
            return "1-5"
        if L <= 10:
            return "6-10"
        if L <= 20:
            return "11-20"
        return "21+"

    for i, sym in enumerate(order):
        try:
            df = prices.load_prices(sym)
        except Exception:
            df = None
        if df is None or df.empty:
            skipped_nodata += 1
            continue
        if len(df) < MIN_BARS_SYMBOL:
            skipped_short += 1
            continue
        s = series_for(df)
        if s is None:
            skipped_short += 1
            continue
        names_used += 1
        close, valid, fired, pos = s["close"], s["valid"], s["fired"], s["pos"]
        # MATCHED CONTROL: identical position>=0.5 and EMA-rising terms, the
        # squeeze term OFF. Differs from the verdict by exactly one clause.
        matched = valid & (pos >= 0.5) & s["rise"] & ~(s["on"] | s["released"])
        n = len(close)
        tot_valid += int(valid.sum())
        tot_fired += int(fired.sum())
        if fired.any():
            names_fired += 1
        if fired[-1]:
            board_today.append(sym)
            coil_lens_today[sym] = int(s["coil_len"][-1])
            try:
                dv = float(np.median((df["close"] * df["volume"]).to_numpy()[-50:]))
            except Exception:
                dv = float("nan")
            board_liq[sym] = dv
        board_dates[sym] = str(s["dates"][-1])[:10]

        for h in HORIZONS:
            f = fwd(close, h)
            elig = valid & np.isfinite(f)
            fm, pm = elig & fired, elig & ~fired
            if fm.any():
                fired_fwd[h].append((sym, f[fm]))
            if pm.any():
                plac_fwd[h].append((sym, f[pm]))
            mm = elig & matched
            if mm.any():
                matched_fwd[h].append((sym, f[mm]))
            if fm.any():
                cl = s["coil_len"][fm]
                for bkt in ("1-5", "6-10", "11-20", "21+"):
                    sel = np.array([bucket_of(x) == bkt for x in cl])
                    if sel.any():
                        bucket_fwd.setdefault(bkt, {}).setdefault(h, []).append(
                            (sym, f[fm][sel]))

        # precede: does position > 1.0 print within the next 21 bars?
        above = pos > 1.0
        cross = np.zeros(n, bool)
        for j in range(n - PRECEDE_WIN):
            cross[j] = above[j + 1:j + 1 + PRECEDE_WIN].any()
        full = np.zeros(n, bool)
        full[:max(0, n - PRECEDE_WIN)] = True
        base = valid & full
        fm, pm = base & fired, base & ~fired
        if fm.any():
            prec_fired.append((sym, int(cross[fm].sum()), int(fm.sum())))
            cl = s["coil_len"][fm]
            cr = cross[fm]
            for bkt in ("1-5", "6-10", "11-20", "21+"):
                sel = np.array([bucket_of(x) == bkt for x in cl])
                if sel.any():
                    bucket_prec.setdefault(bkt, []).append(
                        (sym, int(cr[sel].sum()), int(sel.sum())))
        if pm.any():
            prec_plac.append((sym, int(cross[pm].sum()), int(pm.sum())))
            hi = base & matched             # one-clause-different control
            if hi.any():
                prec_plac_hi.append((sym, int(cross[hi].sum()), int(hi.sum())))
        if fm.any() and pm.any():
            prec_paired_all.append((sym, int(cross[fm].sum()), int(fm.sum()),
                                    int(cross[pm].sum()), int(pm.sum())))
            hi = base & matched
            if hi.any():
                prec_paired_hi.append((sym, int(cross[fm].sum()), int(fm.sum()),
                                       int(cross[hi].sum()), int(hi.sum())))

        if i % 400 == 0:
            print("  ... %d/%d scanned, %.0fs" % (i, len(order), time.time() - t0),
                  file=sys.stderr, flush=True)

    out = {}
    out["universe_mode"] = "full"
    out["universe_n"] = len(syms)
    out["names_used"] = names_used
    out["names_fired_ever"] = names_fired
    out["skipped_no_data"] = skipped_nodata
    out["skipped_short_history"] = skipped_short
    out["eligible_bars"] = tot_valid
    out["fired_bars"] = tot_fired
    out["fire_rate"] = tot_fired / tot_valid if tot_valid else None
    out["board_today_n"] = len(board_today)
    out["board_today"] = sorted(board_today)
    out["last_bar_dates"] = sorted(set(board_dates.values()))[-3:]

    print("\n=== FIRE RATE ===")
    print(json.dumps({k: out[k] for k in
                      ("universe_n", "names_used", "names_fired_ever",
                       "eligible_bars", "fired_bars", "fire_rate",
                       "board_today_n", "skipped_no_data",
                       "skipped_short_history", "last_bar_dates")}, indent=1))
    print("board today (%d):" % len(board_today), ", ".join(sorted(board_today)))
    bk_today = {"1-5": 0, "6-10": 0, "11-20": 0, "21+": 0}
    for sym in board_today:
        bk_today[bucket_of(coil_lens_today[sym])] += 1
    print("board by coil length:", bk_today)
    print("board coil>=21:", sorted(s2 for s2 in board_today
                                    if coil_lens_today[s2] >= 21))
    liq = np.array([v for v in board_liq.values() if v == v])
    if len(liq):
        print("board 50d median $vol: median $%.1fM | under $5M/day: %d of %d"
              % (np.median(liq) / 1e6, int((liq < 5e6).sum()), len(liq)))
    out["board_by_coil_len"] = bk_today
    out["board_coil_ge_21"] = sorted(s2 for s2 in board_today
                                     if coil_lens_today[s2] >= 21)
    out["board_median_dollar_vol"] = float(np.median(liq)) if len(liq) else None

    print("\n=== FORWARD RETURNS, coiled vs placebo (symbol-clustered 95%% CI) ===")
    fwd_rows = {}
    for h in HORIZONS:
        fmed = cluster_ci(fired_fwd[h], B_FIRED, "median")
        pmed = cluster_ci(plac_fwd[h], B_PLACEBO, "median")
        fmean = cluster_ci(fired_fwd[h], B_FIRED, "mean")
        pmean = cluster_ci(plac_fwd[h], B_PLACEBO, "mean")
        dmed = diff_ci(fired_fwd[h], plac_fwd[h], 300, "median")
        dmean = diff_ci(fired_fwd[h], plac_fwd[h], 300, "mean")
        fwin = cluster_prop_ci([(s, int((a > 0).sum()), len(a)) for s, a in fired_fwd[h]])
        pwin = cluster_prop_ci([(s, int((a > 0).sum()), len(a)) for s, a in plac_fwd[h]])
        fwd_rows[h] = {"fired_median": fmed, "placebo_median": pmed,
                       "fired_mean": fmean, "placebo_mean": pmean,
                       "lift_median": dmed, "lift_mean": dmean,
                       "fired_win": fwin, "placebo_win": pwin}
        print("\n %dd   fired n=%d (%d names) | placebo n=%d (%d names)"
              % (h, fmed["n"], fmed["n_sym"], pmed["n"], pmed["n_sym"]))
        print("   median  fired %s   placebo %s   LIFT %s"
              % (pct(fmed), pct(pmed), pct(dmed)))
        print("   mean    fired %s   placebo %s   LIFT %s"
              % (pct(fmean), pct(pmean), pct(dmean)))
        print("   win%%    fired %s   placebo %s"
              % (pct(fwin), pct(pwin)))
    out["forward"] = fwd_rows

    print("\n=== SECONDARY CONTROL: same position/EMA terms, NO squeeze ===")
    matched_rows = {}
    for h in HORIZONS:
        mmed = cluster_ci(matched_fwd[h], 300, "median")
        dmed = diff_ci(fired_fwd[h], matched_fwd[h], 300, "median")
        matched_rows[h] = {"matched_median": mmed, "lift_vs_matched": dmed}
        print("  %2dd  matched n=%-7d median %s   coiled MINUS matched %s"
              % (h, mmed["n"], pct(mmed), pct(dmed)))
    out["matched_control"] = matched_rows

    print("\n=== PRECEDES? close above the upper band within 21 bars ===")
    pf = cluster_prop_ci(prec_fired)
    pp = cluster_prop_ci(prec_plac)
    ph = cluster_prop_ci(prec_plac_hi)
    print(" coiled          %s  (n=%d)" % (pct(pf), pf["n"]))
    print(" non-coiled ALL  %s  (n=%d)" % (pct(pp), pp["n"]))
    print(" matched (pos>=0.5 + EMA rising, no squeeze) %s  (n=%d)" % (pct(ph), ph["n"]))
    d_all = paired_prop_diff_ci(prec_paired_all)
    d_hi = paired_prop_diff_ci(prec_paired_hi)
    print(" DIFF coiled - non-coiled ALL      %s" % pct(d_all))
    print(" DIFF coiled - matched control     %s" % pct(d_hi))
    out["precede"] = {"coiled": pf, "placebo_all": pp, "placebo_matched": ph,
                      "diff_vs_all": d_all, "diff_vs_matched": d_hi}

    print("\n=== PRE-REGISTERED SPLIT: coil length (squeeze.bars) ===")
    print(" NOTE a release bar reports squeeze.bars == 0 by construction, so the")
    print(" length of the run that JUST ended is used for those bars.")
    bk = {}
    for bkt in ("1-5", "6-10", "11-20", "21+"):
        row = {}
        for h in HORIZONS:
            per = bucket_fwd.get(bkt, {}).get(h, [])
            row["med_%dd" % h] = cluster_ci(per, 300, "median")
            row["lift_vs_placebo_%dd" % h] = diff_ci(per, plac_fwd[h], 200, "median")
            row["lift_vs_matched_%dd" % h] = diff_ci(per, matched_fwd[h], 200, "median")
        row["precede"] = cluster_prop_ci(bucket_prec.get(bkt, []))
        bk[bkt] = row
        n21 = row["med_21d"]["n"]
        print("  %-6s n(21d)=%-7d n_names=%d  precede %s"
              % (bkt, n21, row["med_21d"]["n_sym"], pct(row["precede"])))
        for h in HORIZONS:
            print("           %2dd med %s   vs placebo %s   vs matched %s"
                  % (h, pct(row["med_%dd" % h]), pct(row["lift_vs_placebo_%dd" % h]),
                     pct(row["lift_vs_matched_%dd" % h])))
    out["coil_buckets"] = bk

    # --- prefix spot-check: vectorised series == the real module, bar by bar
    print("\n=== SPOT-CHECK vs supply_demand.keltner (real module, prefixes) ===")
    checks, bad = 0, 0
    for sym in ["AMD", "NVDA", "AAPL"]:
        df = prices.load_prices(sym)
        if df is None or len(df) < 200:
            continue
        s = series_for(df)
        for idx in (120, 200, 300, len(df) - 1):
            sub = df.iloc[:idx + 1]
            ch = K.channel(sub)
            sq = K.squeeze(sub)
            checks += 1
            okp = ch and abs(ch["position"] - s["pos"][idx]) < 1e-6
            oks = sq and sq["on"] == bool(s["on"][idx]) and sq["bars"] == int(s["bars"][idx]) \
                and sq["released"] == bool(s["released"][idx])
            if not (okp and oks):
                bad += 1
                print("  MISMATCH", sym, idx, ch, sq, s["pos"][idx],
                      s["on"][idx], s["bars"][idx], s["released"][idx])
    print("  %d prefix checks, %d mismatches" % (checks, bad))
    out["spot_check"] = {"checks": checks, "mismatches": bad}

    print("\nElapsed %.0fs" % (time.time() - t0))
    print("\n=== JSON ===")
    print(json.dumps(out, default=float)[:12000])


main()
