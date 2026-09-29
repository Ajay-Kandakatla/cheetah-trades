"""Pin tests for scripts/green_on_red_study.py (pre-registration rev 1, spec §4 WP-A).

No Mongo, no network: every frame here is synthetic. NEGATIVES are most of the
file — a red or unchanged close is never a signal, day t never enters its own
RVOL or match features, AS_OF is never scored, a non-red day never counts as
red, a CI with one grouping under MIN_CLUSTERS is NULL (no fallback), an
imbalanced run computes no outcome, and neither SIGNAL nor INVERTED survives a
single failed stability check.
"""
from __future__ import annotations

import inspect
import json
import math
import re
from contextlib import contextmanager
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from scripts import green_on_red_study as G
from scripts import explosive_study as ES
from scripts import promo_tag_study as PT
from scripts import turning_bullish_amd_study as AS
from rotation import tracker as RT
from sepa import breakout_audit as BA
from sepa import prices as PR
from supply_demand import momentum_burst as MB
from supply_demand import stock_supply_demand as SSD
from trading import safety_floor as SF

ET = G.ET
SRC = inspect.getsource(G)


# ── fixtures ─────────────────────────────────────────────────────────────────
def _dates(n, start="2024-01-01", hour=4):
    return pd.bdate_range(start, periods=n) + pd.Timedelta(hours=hour)


def mkframe(close, open_=None, high=None, low=None, vol=None, start="2024-01-01", index=None):
    c = np.asarray(close, dtype=float)
    o = np.r_[c[0], c[:-1]] if open_ is None else np.asarray(open_, dtype=float)
    h = np.maximum(o, c) * 1.002 if high is None else np.asarray(high, dtype=float)
    lo = np.minimum(o, c) * 0.998 if low is None else np.asarray(low, dtype=float)
    v = np.full(len(c), 1e6) if vol is None else np.asarray(vol, dtype=float)
    idx = _dates(len(c), start) if index is None else index
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c, "volume": v}, index=idx)


def cal_of(df):
    return G.day_keys(df)


def rw(n, seed=0, c0=50.0, sd=0.01):
    rng = np.random.default_rng(seed)
    return c0 * np.cumprod(1 + rng.normal(0, sd, n))


@contextmanager
def patched(**kw):
    old = {k: getattr(G, k) for k in kw}
    try:
        for k, v in kw.items():
            setattr(G, k, v)
        yield
    finally:
        for k, v in old.items():
            setattr(G, k, v)


def synth(drift=0.0, gap=0.0, post_noise=False, n_groups=60, T=320, first_red=70, every=21,
          per_day=5, seed=3, low_price_groups=0):
    """Pairs of names (A, A') identical up to their ONE signal day; on a planted red
    day A closes green on 3x volume, A' closes red. `drift` is planted from the next
    open over H_PRIMARY sessions; `gap` is an open gap on t+1 only."""
    rng = np.random.default_rng(seed)
    idx = _dates(T)
    br = rng.uniform(-0.003, 0.003, T); br[0] = 0.0
    red_ts = list(range(first_red, T - 1 - G.H_PRIMARY + 1, every))
    for t in red_ts:
        br[t] = -0.01
    B = 100 * np.cumprod(1 + br)
    bench = pd.DataFrame({"open": np.r_[B[0], B[:-1]], "high": B * 1.001, "low": B * 0.999, "close": B,
                          "volume": np.full(T, 1e7)}, index=idx)
    order = rng.permutation(n_groups)
    sig_day = {}
    k = 0
    for t in red_ts:
        for _ in range(per_day):
            if k < n_groups:
                sig_day[int(order[k])] = t
                k += 1
    frames = {}
    for g in range(n_groups):
        beta = rng.uniform(0.5, 1.5); dr = rng.uniform(-0.001, 0.001)
        c0 = 3.0 if g < low_price_groups else rng.uniform(20, 100)
        vbase = rng.uniform(1e6, 5e6) if g >= low_price_groups else 8e6
        noise = rng.normal(0, 0.005, T)
        base = beta * br + dr + noise
        for t in red_ts:
            base[t] = min(base[t], -0.004)
        vol = vbase * (1 + rng.uniform(-0.1, 0.1, T))
        rA = base.copy(); rB = base.copy(); gA = np.zeros(T)
        vA = vol.copy()
        t = sig_day.get(g)
        if t is not None:
            rA[t] = 0.01
            vA[t] = vol[t] * 3
            if post_noise:
                rA[t + 1:] = base[t + 1:] + rng.normal(0, 0.005, T - t - 1)
            for j in range(1, G.H_PRIMARY + 1):
                if t + j < T:
                    rA[t + j] += drift / G.H_PRIMARY
            if t + 1 < T:
                gA[t + 1] = gap
        for name, r, gg, v in (("A%02d" % g, rA, gA, vA), ("B%02d" % g, rB, np.zeros(T), vol)):
            r = r.copy(); r[0] = 0.0
            C = np.empty(T); O = np.empty(T)
            C[0] = c0; O[0] = c0
            for j in range(1, T):
                O[j] = C[j - 1] * (1 + gg[j])
                C[j] = O[j] * (1 + r[j]) if gg[j] != 0 else C[j - 1] * (1 + r[j])
            frames[name] = mkframe(C, O, vol=v, index=idx)
    return frames, bench, red_ts, sig_day


def run(frames, bench, stage="all", expect=None, cache=True, **extra):
    kw = dict(MIN_BREADTH_NAMES=50, MIN_CLUSTERS=8, BOOT_B=300)
    kw.update(extra)
    with patched(**kw):
        return G.run_study(frames, bench, bench, G.day_keys(bench)[-1],
                           cache_frames=(frames if cache else None), expect=expect, stage=stage, quiet=True)


@pytest.fixture(scope="module")
def sig_run():
    f, b, red_ts, sd = synth(drift=0.03)
    return run(f, b), red_ts, sd


# ── 01 ───────────────────────────────────────────────────────────────────────
def _one_day_panel(last_closes, prev=10.0, vol_t=3e6):
    n = 60
    frames = {}
    for k, c in enumerate(last_closes):
        close = np.full(n, prev); close[-1] = c
        v = np.full(n, 1e6); v[-1] = vol_t
        hi = np.maximum(close, prev) + 0.01; lo = np.minimum(close, prev) - 0.01
        frames["N%d" % k] = mkframe(close, np.full(n, prev), hi, lo, v)
    cal = cal_of(frames["N0"])
    P = G.build_panel(frames, cal)
    chg = G.day_change(P)
    return P, chg, G.signal_sets(P, chg, G.rvol(P), G.close_pos(P))


def test_01_red_unchanged_green_sets():
    P, chg, s = _one_day_panel([10.5, 9.5, 10.0])
    t = P.C.shape[1] - 1
    assert s["S1"][0, t] and s["S2"][0, t] and not s["POOL"][0, t]
    assert not s["S1"][1, t] and not s["S2"][1, t] and s["POOL"][1, t]          # red close: never S1/S2
    assert not s["S1"][2, t] and not s["S2"][2, t] and not s["POOL"][2, t]      # unchanged: neither
    share, n_valid = G.breadth(chg)
    assert n_valid[t] == 3 and share[t] == pytest.approx(1 / 3)                 # unchanged is valid, not green


# ── 02 ───────────────────────────────────────────────────────────────────────
def test_02_rvol_excludes_day_t():
    rng = np.random.default_rng(1)
    v = rng.uniform(5e5, 2e6, 120)
    def rv(vv):
        P = G.build_panel({"X": mkframe(rw(120), vol=vv)}, cal_of(mkframe(rw(120))))
        return G.rvol(P)[0]
    base = rv(v); t = 100
    den = v[t] / base[t]
    v2 = v.copy(); v2[t] *= 100
    assert v2[t] / rv(v2)[t] == pytest.approx(den, rel=1e-12)                   # denominator untouched by V_t
    v3 = v.copy(); v3[t - 51] *= 7
    assert rv(v3)[t] == pytest.approx(base[t], rel=1e-12)                       # outside the 50-bar window
    v4 = v.copy(); v4[t - 1] *= 7
    assert rv(v4)[t] != pytest.approx(base[t], rel=1e-6)                        # inside
    for i in range(50, 120):
        assert base[i] == pytest.approx(ES._rvol(v, i, G.VOL_BARS), rel=1e-9)
    assert np.isnan(base[49]) and np.isfinite(base[50])                         # 49-bar history -> NaN


# ── 03 ───────────────────────────────────────────────────────────────────────
def _rand_frames(n_names=6, T=200, seed=5):
    rng = np.random.default_rng(seed)
    fr = {}
    for k in range(n_names):
        c = rw(T, seed=seed + k)
        fr["S%d" % k] = mkframe(c, vol=rng.uniform(5e5, 3e6, T))
    b = rw(T, seed=99, c0=100)
    return fr, mkframe(b)


def _ctx(fr, bench, cal=None):
    cal = cal or cal_of(bench)
    P = G.build_panel(fr, cal)
    B_O, B_C = G.bench_arrays(bench, cal)
    return G.compute_ctx(P, B_O, B_C, B_C)


FEATS = tuple(G.MATCH_VARS) + ("above50", "off52_bars")
FLAGS = ("S1", "S2", "POOL", "chg", "rvol", "cr", "leader")


def _eq(a, b):
    return np.array_equal(np.asarray(a, float), np.asarray(b, float), equal_nan=True)


def test_03_no_bar_after_t_and_features_prev():
    fr, b = _rand_frames()
    t = 150
    with patched(MIN_BREADTH_NAMES=1):
        c0 = _ctx(fr, b)
        fr2 = {s: f.copy() for s, f in fr.items()}; b2 = b.copy()
        for f in list(fr2.values()) + [b2]:
            f.iloc[t + 1:, :] = f.iloc[t + 1:, :].to_numpy() * 3.7
        c1 = _ctx(fr2, b2)
        for k in FEATS:
            assert _eq(c0["feats"][k][:, t], c1["feats"][k][:, t]), k
        for k in FLAGS:
            assert _eq(c0[k][:, t], c1[k][:, t]), k
        assert c0["red"][t] == c1["red"][t]
        fr3 = {s: f.copy() for s, f in fr.items()}; b3 = b.copy()
        for f in list(fr3.values()) + [b3]:
            f.iloc[t, :] = f.iloc[t, :].to_numpy() * 1.9
        c3 = _ctx(fr3, b3)
        for k in tuple(G.MATCH_VARS) + ("above50",):
            assert _eq(c0["feats"][k][:, t], c3["feats"][k][:, t]), k
        cal = cal_of(b)
        ctr = _ctx({s: G.cap_as_of(f, cal[t]) for s, f in fr.items()}, G.cap_as_of(b, cal[t]), cal[:t + 1])
        for k in FEATS:
            assert _eq(ctr["feats"][k][:, t], c0["feats"][k][:, t]), k


# ── 04 ───────────────────────────────────────────────────────────────────────
def test_04_today_never_scored_and_horizon_edges():
    fr, b = _rand_frames(n_names=2, T=120)
    ctx = _ctx(fr, b)
    T = ctx["T"]
    last = pd.DataFrame({"t": [T - 1], "i_s": [0], "i_p": [1]})
    for h in G.HORIZONS:
        for e in G.ENTRIES:
            r, _ = G.cell(ctx, last, h, e)
            assert r["n_pairs"] == 0 and r["n_eligible_pairs"] == 0
    for a, bb in zip(G.HORIZONS[:-1], G.HORIZONS[1:]):
        p = pd.DataFrame({"t": [T - 1 - a], "i_s": [0], "i_p": [1]})
        assert G.cell(ctx, p, a, "O")[0]["n_pairs"] == 1
        assert G.cell(ctx, p, bb, "O")[0]["n_eligible_pairs"] == 0
    # the matcher's row table stops at T-1-min(HORIZONS): AS_OF is never a signal row
    everything = np.ones_like(ctx["S1"])
    rows, _ = G.rows_table(ctx, everything, np.ones(T, bool), G.MATCH_VARS, T - 1 - min(G.HORIZONS))
    assert rows["day"].max() <= T - 1 - min(G.HORIZONS)


# ── 05 ───────────────────────────────────────────────────────────────────────
def test_05_red_day_rule_boundaries():
    B = np.array([100.0, 99.51, 99.51 * 0.994, 100.0, 99.5, 100.0, 99.0])
    share = np.array([np.nan, 0.10, 0.36, 0.2, 0.35, 0.2, 0.10])
    n = np.array([0, 2000, 2000, 2000, 2000, 2000, 999])
    red = G.red_days(B, share, n)
    assert not red[1]                     # RSP -0.49% with breadth 0.10
    assert not red[2]                     # RSP -0.60% with breadth 0.36
    assert red[4]                         # exactly -0.5000% and exactly 0.35 -> red
    assert not red[6]                     # n_valid < MIN_BREADTH_NAMES
    cls = G.classified_days(B, n)
    assert not cls[6] and not cls[0]      # unclassified: neither red nor non-red
    nonred = cls & ~red
    assert not nonred[6] and not red[6]


# ── 06 ───────────────────────────────────────────────────────────────────────
def test_06_breadth_same_universe():
    fr, b = _rand_frames(n_names=4, T=120)
    fr = dict(fr)
    fr["SMH"] = mkframe(rw(120, 44))           # an ETF
    fr["SPY"] = mkframe(rw(120, 45))           # an RS anchor
    assert "SMH" in G.exclude_set() and "SPY" in G.exclude_set() and G.BENCH in G.exclude_set()
    res = run(fr, b, stage="features", MIN_BREADTH_NAMES=1)
    assert res["sample"]["names"] == 4 and res["sample"]["etf_excluded_present"] == 2
    assert G.study_names(["AAA", "SMH", "SPY", "AAA", G.BENCH], G.exclude_set()) == ["AAA"]
    # a gap on cal[t-1] and a scale glitch are not in the denominator
    c = rw(120, 7); c2 = c.copy(); c2[80] = c2[79] * 6.0
    idx = _dates(120)
    f_gap = mkframe(c).drop(idx[79])
    P = G.build_panel({"G": f_gap, "X": mkframe(c2), "Y": mkframe(c)}, G.day_keys(mkframe(c)))
    chg = G.day_change(P)
    share, n_valid = G.breadth(chg)
    assert n_valid[80] == 1 and n_valid[81] == 2
    ctx = G.compute_ctx(P, *G.bench_arrays(mkframe(rw(120, 9, 100)), P.cal))
    assert ctx["P"] is P and _eq(ctx["n_valid"], np.isfinite(ctx["chg"]).sum(0))
    red_f = np.zeros(120, bool); red_f[90] = True
    cc = G.compute_ctx(P, *G.bench_arrays(mkframe(rw(120, 9, 100)), P.cal), red_frozen=red_f,
                       nonred_frozen=~red_f)
    assert _eq(cc["red"], red_f)


# ── 07 ───────────────────────────────────────────────────────────────────────
def test_07_prior_close_is_prior_session():
    c = np.linspace(10, 12, 60)
    idx = _dates(60)
    f = mkframe(c).drop(idx[40])
    P = G.build_panel({"X": f}, G.day_keys(mkframe(c)))
    chg = G.day_change(P)
    assert np.isnan(chg[0, 41]) and np.isnan(chg[0, 40]) and chg[0, 42] > 0


# ── 08 ───────────────────────────────────────────────────────────────────────
def _single(c_t, v_t, h_t, l_t, prev=1.9, vprev=1e6, n=60):
    c = np.full(n, prev); c[-1] = c_t
    v = np.full(n, vprev); v[-1] = v_t
    hi = np.full(n, prev + 0.01); lo = np.full(n, prev - 0.01)
    hi[-1] = h_t; lo[-1] = l_t
    P = G.build_panel({"X": mkframe(c, np.full(n, prev), hi, lo, v)}, cal_of(mkframe(c)))
    chg = G.day_change(P)
    s = G.signal_sets(P, chg, G.rvol(P), G.close_pos(P))
    return bool(s["S2"][0, -1])


def test_08_inclusive_boundaries():
    assert _single(2.0, 5e6, 3.0, 1.0)                  # C == 2.00, C*V == 10M, cr == 0.5 exactly
    assert not _single(1.99, 6e6, 3.0, 0.98)            # under the price floor
    assert not _single(2.0, 4.9e6, 3.0, 1.0)            # C*V under 10M
    assert not _single(2.0, 5e6, 3.02, 1.0)             # cr 0.495
    assert not _single(2.0, 5e6, 2.0, 2.0)              # H == L -> never S2
    assert _single(5.0, 3e6, 6.0, 4.0, prev=4.9, vprev=2e6)     # rvol exactly 1.5
    assert not _single(5.0, 2.99e6, 6.0, 4.0, prev=4.9, vprev=2e6)


# ── 09 ───────────────────────────────────────────────────────────────────────
def test_09_leader_and_off52_floor():
    n = 300
    c = rw(n, 11)
    f = mkframe(c)
    P = G.build_panel({"X": f}, cal_of(f))
    lead = G.leader_at_t(P)[0]
    for t in (60, 120, 299):
        ma = c[t - 49:t + 1].mean()
        hi = P.H[0, max(0, t - 251):t + 1].max()
        assert lead[t] == bool(c[t] > ma and c[t] / hi - 1 >= -G.LEADER_NEAR_HIGH_PCT / 100)
    feats = G.features_prev(P, P.C[0])
    off = feats["off52"][0]
    assert np.isnan(off[62]) and np.isfinite(off[63])       # 62 highs -> NaN, 63 -> finite
    assert off[100] == pytest.approx(c[99] / P.H[0, :100].max() - 1)
    assert off[299] == pytest.approx(c[298] / P.H[0, 299 - 252:299].max() - 1)
    assert feats["off52_bars"][0, 100] == 100 and feats["off52_bars"][0, 299] == G.HIGH_BARS


# ── 10 ───────────────────────────────────────────────────────────────────────
MV = G.MATCH_VARS


def _tab(rows):
    df = pd.DataFrame(rows)
    df.insert(0, "id", np.arange(len(df)))
    df["sym"] = ["S%d" % k for k in range(len(df))]
    df["i"] = np.arange(len(df))
    return df


def _row(day, ab=1.0, **kw):
    d = {"day": day, "above50": ab}
    d.update({v: kw.get(v, 0.0) for v in MV})
    return d


def test_10_matcher():
    sd = np.ones(len(MV))
    m = lambda s, p, cal=0.6: G.match_same_day(_tab(s), _tab(p), sd, caliper=cal, match_vars=MV)
    pairs, um = m([_row(1)], [_row(2), _row(1, r21=5.0)])
    assert len(pairs) == 0 and um == [0]                                     # same day only
    pairs, um = m([_row(1, ab=1.0)], [_row(1, ab=0.0)])
    assert len(pairs) == 0                                                   # exact above50
    pairs, _ = m([_row(1)], [_row(1, beta63=0.7), _row(1, **{v: 0.5 for v in MV})])
    assert list(pairs["pid"]) == [1]                                         # per-covariate box, beta63 included
    pairs, um = m([_row(1), _row(1)], [_row(1)])
    assert len(pairs) == 1 and um == [1]                                     # without replacement
    pairs, _ = m([_row(1, r21=0.3), _row(1, r21=0.1)], [_row(1), _row(1, r21=0.55)])
    got = dict(zip(pairs["sid"], pairs["pid"]))
    assert got[1] == 0 and got[0] == 1                                       # closest wins, not id order
    pairs, _ = m([_row(1)], [_row(1, r21=0.2), _row(1, r21=-0.2)])
    assert list(pairs["pid"]) == [0]                                         # tie -> lower pid
    pairs, um = m([_row(1, r21=0.2), _row(1, r21=-0.2)], [_row(1)])
    assert list(pairs["sid"]) == [0] and um == [1]                           # tie -> lower sid
    src = inspect.getsource(G.match_same_day)
    assert "np.random" not in src and "default_rng" not in src and "shuffle" not in src
    with pytest.raises(TypeError):
        G.match_same_day(_tab([_row(1)]), _tab([_row(1)]), sd)
    with pytest.raises(TypeError):
        G.match_same_day(_tab([_row(1)]), _tab([_row(1)]), sd, caliper=0.6)


# ── 11 ───────────────────────────────────────────────────────────────────────
def test_11_sd_smd_balance():
    s = _tab([_row(1, r21=x) for x in (1.0, 2.0, 3.0)])
    p = _tab([_row(1, r21=x) for x in (2.0, 4.0, 6.0)])
    sd = G.pooled_sd(s, p, ("r21",))
    assert sd[0] == pytest.approx(math.sqrt((1.0 + 4.0) / 2))
    assert G.smd([1, 2, 3], [2, 4, 6]) == pytest.approx((2 - 4) / math.sqrt(2.5))
    ok = {"smd_" + v: 0.0 for v in MV + ("above50",)}
    assert G.balance_gate(ok, MV)
    assert not G.balance_gate({**ok, "smd_vol20": float("nan")}, MV)       # NaN fails
    assert not G.balance_gate({**ok, "smd_r21": 0.1}, MV)                   # |SMD| = 0.1 fails
    assert not G.balance_gate({**ok, "smd_beta63": -0.165}, MV)             # the rev-0 beta gap fails
    assert not G.balance_gate({**ok, "smd_above50": 0.2}, MV)


# ── 12 ───────────────────────────────────────────────────────────────────────
def test_12_fixed_blocks():
    assert G.blocks([19], 10)[0] != G.blocks([20], 10)[0]
    run30 = np.arange(40, 70)
    assert len(np.unique(G.blocks(run30, G.BLOCK_SESSIONS))) >= 3
    g = G.groupings(np.arange(0, 100), G.BLOCK_SESSIONS)
    assert _eq(g["blk_h"], g["blk_m"])
    t = np.r_[np.arange(0, 400, 21), [399, 398]]
    vals = np.r_[np.ones(len(t) - 2), [50, 50]]
    sig = np.r_[np.ones(len(t) - 2, bool), [False, False]]
    tw = np.zeros(len(t), bool)
    tw[:5] = True; sig[:5] = False
    with patched(MIN_CLUSTERS=1, BOOT_B=200):
        r = G.lift_ci(vals, sig, tw, t, 5)
    assert r["G"]["day"] == len(t) - 2                                        # excluded rows never counted
    h1 = G.date_halves(np.array([5, 5, 5, 9, 12, 12, 30]))
    assert list(h1) == [True, True, True, True, False, False, False]          # unique days (5, 9), not 3 rows


# ── 13 ───────────────────────────────────────────────────────────────────────
def _clustered(n_cl=25, per=4, seed=2):
    rng = np.random.default_rng(seed)
    t = np.repeat(np.arange(n_cl) * 21, per)
    cm = rng.normal(0, 1, n_cl)
    a = np.repeat(cm, per) + rng.normal(0, 0.1, len(t))
    b = np.repeat(cm * 0.5, per) + rng.normal(0, 0.1, len(t))
    vals = np.r_[a, b]
    m = np.r_[np.ones(len(t), bool), np.zeros(len(t), bool)]
    return vals, m, np.r_[t, t]


def test_13_cluster_bootstrap_null_rule():
    vals, m, t = _clustered()
    with patched(BOOT_B=400):
        r1 = G.lift_ci(vals, m, ~m, t, 21)
        k = 10
        r2 = G.lift_ci(np.tile(vals, k), np.tile(m, k), np.tile(~m, k), np.tile(t, k), 21)
    w1 = r1["ci"][1] - r1["ci"][0]; w2 = r2["ci"][1] - r2["ci"][0]
    assert w2 > 0.7 * w1                                                      # iid would shrink ~sqrt(10)
    tt = np.arange(20) * 21
    vals = np.r_[np.linspace(0, 1, 20), np.linspace(0, 0.5, 20)]
    m = np.r_[np.ones(20, bool), np.zeros(20, bool)]
    tt2 = np.r_[tt, tt]
    with patched(BOOT_B=300):
        r = G.lift_ci(vals, m, ~m, tt2, 5)
        assert r["ci"] is not None and r["G_min"] == G.MIN_CLUSTERS           # G == MIN_CLUSTERS -> non-null
        cis = [AS.boot_diff(vals, m, ~m, lab, B=300, seed=G.BOOT_SEED)["diff_ci"]
               for lab in G.groupings(tt2, 5).values()]
        assert tuple(r["ci"]) == AS.widest(*cis)                             # widest of the three
        t19 = np.r_[np.arange(19) * 21, [18 * 21 + 1]]
        r19 = G.lift_ci(vals, m, ~m, np.r_[t19, t19], 5)
        assert r19["G"]["day"] == 20 and r19["G"]["blk_m"] == 19
        assert r19["ci"] is None and r19["sig_ci"] is None                    # one grouping short -> NULL
    with patched(BOOT_B=50):
        rr = G.lift_ci(vals, m, ~m, tt2, 5)
        assert rr["ci"] is None                                               # reps < MIN_BOOT_REPS -> NULL


# ── 14 ───────────────────────────────────────────────────────────────────────
def _res(lo=0.5, hi=2.0, slo=0.2, h1=1.0, h2=1.0, dmin=0.5, dmax=1.5, ops=1.0, ec=1.0, ca=1.0, cab=True,
         hc=1.0, hcb=True, share=0.9, s3=(0.1, 1.0), s3b=True):
    return {"snapshot": {"ok": True}, "pit": {"mismatch": 0},
            "balance": {"primary": {"balanced": True, "matched_share": share}},
            "primary": {"h10_O": {"ci": None if lo is None else [lo, hi], "sig_ci": [slo, 3.0], "lift": 1.0}},
            "stability": {"date_h1": {"lift": h1}, "date_h2": {"lift": h2},
                          "drop_one_block": {"min": dmin, "max": dmax}, "one_per_symbol": {"lift": ops},
                          "entry_C": {"lift": ec}, "cache_all": {"lift": ca, "balanced": cab},
                          "house_caliper": {"lift": hc, "balanced": hcb}},
            "secondary": {"S3": {"ci": None if s3 is None else list(s3), "balanced": s3b}}}


def _neg(**kw):
    base = dict(lo=-2.0, hi=-0.5, slo=-1.0, h1=-1.0, h2=-1.0, dmin=-1.5, dmax=-0.5, ops=-1.0, ec=-1.0,
                ca=-1.0, hc=-1.0, s3=(-1.0, -0.1))
    base.update(kw)
    return _res(**base)


def test_14_verdict_every_branch():
    v = G.verdict(_res())
    assert v["status"] == "signal" and v["tags"] == [] and v["rev"] == 1
    v = G.verdict(_neg())
    assert v["status"] == "inverted" and v["tags"] == []
    assert G.verdict(_res(slo=-0.1)) == {**G.verdict(_res(slo=-0.1)), "status": "no_signal"}
    assert "relative_only" in G.verdict(_res(slo=-0.1))["tags"]
    v = G.verdict(_res(lo=-0.1))
    assert v["status"] == "no_signal" and "absolute_only" in v["tags"]
    flips = {"c": dict(h2=-0.1), "c2": dict(dmin=-0.1), "d": dict(ops=-0.1), "e": dict(ec=-0.1),
             "f": dict(ca=-0.1), "f2": dict(hc=-0.1)}
    for c, kw in flips.items():
        v = G.verdict(_res(**kw))
        assert v["status"] == "no_signal" and "fragile" in v["tags"] and c in v["failed"], c
    mflips = {"c-": dict(h1=0.1), "c2-": dict(dmax=0.1), "d-": dict(ops=0.1), "e-": dict(ec=0.1),
              "f-": dict(ca=0.1), "f2-": dict(hc=0.1)}
    for c, kw in mflips.items():
        v = G.verdict(_neg(**kw))
        assert v["status"] == "no_signal" and "inverted_fragile" in v["tags"] and c in v["failed"], c
    for kw in (dict(cab=False), dict(hcb=False)):            # right-sign lift, imbalanced re-match
        assert G.verdict(_res(**kw))["status"] == "no_signal"
        assert G.verdict(_neg(**kw))["status"] == "no_signal"
    v = G.verdict(_res(share=0.79))
    assert v["status"] == "no_signal" and "undermatched" in v["tags"]
    v = G.verdict(_neg(share=0.79))
    assert v["status"] == "no_signal" and "undermatched" in v["tags"]
    v = G.verdict(_res(lo=None))
    assert v["status"] == "no_signal" and "few_clusters" in v["tags"]
    v = G.verdict(_neg(lo=None))
    assert v["status"] == "no_signal" and "few_clusters" in v["tags"]
    for kw in (dict(s3=(-0.1, 1.0)), dict(s3=None), dict(s3b=False)):
        v = G.verdict(_res(**kw))
        assert v["status"] == "signal" and v["tags"] == ["not_red_specific"]    # tag never changes status
    for kw in (dict(s3=(-1.0, 0.1)), dict(s3=None), dict(s3b=False)):
        v = G.verdict(_neg(**kw))
        assert v["status"] == "inverted" and v["tags"] == ["not_red_specific"]
    assert G.verdict({**_res(), "snapshot": {"ok": False}})["status"] == "invalid_snapshot"
    assert G.verdict({**_res(), "pit": {"mismatch": 1}})["status"] == "invalid_pit"
    bad = _res(); bad["balance"]["primary"]["balanced"] = False
    assert G.verdict(bad) == {"status": "no_signal", "tags": ["imbalanced"], "failed": ["balance"], "rev": 1}


def test_14b_imbalanced_computes_no_outcome(monkeypatch):
    f, b, _, _ = synth(drift=0.03)
    def boom(*a, **k):
        raise AssertionError("an outcome was computed")
    monkeypatch.setattr(G, "outcomes", boom)
    res = run(f, b, BALANCE_SMD_MAX=-1.0)
    assert res["verdict"]["status"] == "no_signal" and res["verdict"]["tags"] == ["imbalanced"]
    assert "primary" not in res


# ── 15 ───────────────────────────────────────────────────────────────────────
def test_15_outcomes():
    n = 40
    c = np.linspace(10, 14, n); o = c * 0.99
    idx = _dates(n)
    f = mkframe(c, o)
    fh = f.drop(idx[25])                                             # halt at t+h
    Bc = np.linspace(100, 104, n); Bo = Bc * 0.995
    bench = mkframe(Bc, Bo)
    cal = cal_of(f)
    P = G.build_panel({"A": f, "B": fh}, cal)
    B_O, B_C = G.bench_arrays(bench, cal)
    g = np.zeros(P.C.shape, bool)
    o5 = G.outcomes(P, B_O, B_C, np.array([0, 1]), np.array([20, 20]), 5, "O", g)
    assert o5["x"][0] == 25 and o5["x"][1] == 24                     # carry-forward through a halt
    assert o5["excess"][0] == pytest.approx(100 * ((c[25] / o[21] - 1) - (Bc[25] / Bo[21] - 1)))
    oc = G.outcomes(P, B_O, B_C, np.array([0]), np.array([20]), 5, "C", g)
    assert oc["excess"][0] == pytest.approx(100 * ((c[25] / c[20] - 1) - (Bc[25] / Bc[20] - 1)))
    f2 = f.drop(idx[21:27])
    P2 = G.build_panel({"A": f2}, cal)
    assert not G.outcomes(P2, B_O, B_C, np.array([0]), np.array([20]), 5, "O", g)["ok"][0]   # no bar in (t,t+h]
    fo = f.copy(); fo.iloc[21, 0] = np.nan
    P3 = G.build_panel({"A": fo, "B": f}, cal)
    assert not G.outcomes(P3, B_O, B_C, np.array([0]), np.array([20]), 5, "O", g)["ok"][0]   # no O[t+1]
    ctx = {"P": P3, "B_O": B_O, "B_C": B_C, "T": n, "glitch": g, "chg": G.day_change(P3)}
    pairs = pd.DataFrame({"t": [20, 22], "i_s": [0, 0], "i_p": [1, 1]})
    po = G.pair_outcomes(ctx, pairs, 5, "O")
    assert list(po["both"]) == [False, True]                          # one missing member -> dropped
    gg = np.zeros(P.C.shape, bool); gg[0, 10] = True
    og = G.outcomes(P, B_O, B_C, np.array([0]), np.array([20]), 5, "O", gg)
    assert not og["ok"][0] and og["glitch_excl"][0]                   # glitch in t-R_MED..x -> excluded


# ── 16 ───────────────────────────────────────────────────────────────────────
def test_16_refusal_window():
    assert G.in_refusal_window(datetime(2026, 9, 28, 10, 0, tzinfo=ET))
    assert G.in_refusal_window(datetime(2026, 9, 28, 9, 0, tzinfo=ET))
    assert not G.in_refusal_window(datetime(2026, 9, 28, 17, 30, tzinfo=ET))
    assert not G.in_refusal_window(datetime(2026, 9, 28, 8, 59, tzinfo=ET))
    assert not G.in_refusal_window(datetime(2026, 9, 26, 12, 0, tzinfo=ET))   # Saturday
    assert "--force-window" in SRC and "return 5" in SRC


# ── 17 ───────────────────────────────────────────────────────────────────────
REUSED = {"BENCH": (RT, "BENCHMARK"), "R_SHORT": (RT, "WINDOW_SHORT"), "R_MED": (RT, "WINDOW_MED"),
          "VOL_BARS": (BA, "VOL_AVG_BARS"), "RVOL_MIN": (MB, "BURST_RVOL_MIN"),
          "PRICE_FLOOR": (SF, "MIN_SHARE_PRICE"), "DVOL_APP": (SF, "MIN_DOLLAR_VOL"),
          "HIGH_BARS": (SSD, "LOOKBACK_DAYS"), "LEADER_NEAR_HIGH_PCT": (SSD, "NEAR_HIGH_PCT"),
          "HORIZONS": (AS, "HORIZONS"), "MIN_CLUSTERS": (PT, "MIN_CLUSTERS")}


def test_17_constants_by_name(monkeypatch):
    for name, (mod, attr) in REUSED.items():
        assert getattr(G, name) is getattr(mod, attr), name
        assert not re.search(r"^%s\s*=\s*[-\d\"'(\[]" % name, SRC, re.M), name
    assert G.H_PRIMARY in G.HORIZONS and G.FIRST_T == G.R_MED + 1 and G.PRIMARY_ENTRY == "O"
    assert "beta63" in G.MATCH_VARS and G.MATCH_VARS_REV0 == G.MATCH_VARS[:5]
    assert G.BLOCK_SESSIONS == G.R_SHORT and G.HIGH_MIN_BARS == G.R_MED
    B = np.array([100.0, 99.0]); share = np.array([np.nan, 0.1]); n = np.array([0, 500])
    assert not G.red_days(B, share, n)[1]
    monkeypatch.setattr(G, "MIN_BREADTH_NAMES", 400)
    assert G.red_days(B, share, n)[1]                             # read at call time, not bound
    for fn in (G.red_days, G.lift_ci, G.match_same_day, G.verdict, G.rvol, G.outcomes):
        sig = inspect.signature(fn)
        for p in sig.parameters.values():
            assert not (isinstance(p.default, (int, float)) and not isinstance(p.default, bool)
                        and p.default in (G.MIN_BREADTH_NAMES, G.MIN_CLUSTERS, G.CALIPER_SD)), fn


# ── 18 ───────────────────────────────────────────────────────────────────────
def test_18_read_only_guard():
    for tok in ("load_prices", "_fetch", "_mongo_put", "insert", "update_", "replace_one", "delete",
                "bulk_write", "create_index", "bulk_snapshot", "patch_latest_closes"):
        assert tok not in SRC, tok


# ── 19 ───────────────────────────────────────────────────────────────────────
BANNED = ("bounce", "fake", "Minervini", "TLSW", "TTLAC")


def test_19_json_and_headline():
    assert json.loads(json.dumps(ES._clean({"a": float("nan"), "b": [np.float64("nan"), 1.0]}))) == \
        {"a": None, "b": [None, 1.0]}
    res = _res()
    res["primary"]["h10_O"].update({"sig": 1.2, "n_pairs": 100, "n_days": 30, "G_min": 21,
                                    "first_day": "2025-01-02", "last_day": "2026-09-14"})
    res["verdict"] = {"status": "no_signal", "tags": ["fragile", "not_red_specific"]}
    hl = G.headline(res)
    assert "next open" in hl and "NO_SIGNAL" in hl
    assert TAG_OK(hl, ["fragile", "not_red_specific"])
    assert "$2" in hl and "$10M" in hl and "1.5×" in hl and "50-day" in hl and "held 10 sessions" in hl
    res["primary"]["h10_O"]["ci"] = None
    assert "[n/a: 21 periods]" in G.headline(res)
    for w in BANNED:
        assert w.lower() not in hl.lower()
        assert w.lower() not in SRC.lower(), w
        for t in G.TAG_TEXT.values():
            assert w.lower() not in t.lower()
    assert re.search(r"p\.\s?\d+", hl) is None


def TAG_OK(hl, tags):
    return (" (" + "; ".join(G.TAG_TEXT[t] for t in tags) + ")") in hl


# ── 20 ───────────────────────────────────────────────────────────────────────
def test_20_end_to_end_signal(sig_run):
    res, red_ts, sd = sig_run
    assert res["sample"]["first_t"] == G.FIRST_T
    assert res["balance"]["primary"]["balanced"] and res["balance"]["primary"]["matched_share"] == 1.0
    assert res["pit"]["mismatch"] == 0 and res["pit"]["names"] > 0
    assert res["verdict"]["status"] == "signal", res["verdict"]
    assert res["primary"]["h10_O"]["lift"] == pytest.approx(3.0, abs=0.2)
    assert res["stability"]["cache_all"]["red_frozen"] and res["stability"]["cache_all"]["balanced"]
    assert len(np.unique(G.blocks(red_ts, G.BLOCK_SESSIONS))) >= 10


def test_20b_noise_is_not_signal():
    f, b, _, _ = synth(drift=0.0, post_noise=True, seed=4)
    res = run(f, b)
    assert res["verdict"]["status"] != "signal"


def test_20c_inverted():
    f, b, _, _ = synth(drift=-0.03)
    res = run(f, b)
    assert res["verdict"]["status"] == "inverted", res["verdict"]


def test_20d_gain_only_in_the_gap_is_not_signal():
    f, b, _, _ = synth(drift=0.0, gap=0.03)
    res = run(f, b)
    assert res["stability"]["entry_C"]["lift"] > 2.0
    assert abs(res["primary"]["h10_O"]["lift"]) < 0.5
    assert res["verdict"]["status"] != "signal"


def test_20e_real_constants_never_signal():
    f, b, _, _ = synth(drift=0.03)
    res = G.run_study(f, b, b, G.day_keys(b)[-1], cache_frames=f, stage="all", quiet=True)
    assert all(v["n"] == 0 for v in res["sample"]["red_days"].values())      # 120 names < MIN_BREADTH_NAMES
    assert res["verdict"]["status"] != "signal"


def test_20f_repro_with_expect():
    f, b, red_ts, sd = synth(drift=0.03)
    cal = G.day_keys(b)
    day = cal[red_ts[3]]
    exp = [{"sym": "A%02d" % g} for g, t in sd.items() if t == red_ts[3]]
    with patched(REPRO_DAY=day, ANECDOTE_SYMBOL=exp[0]["sym"]):
        res = run(f, b, stage="features", expect=exp)
    assert res["repro"]["is_red"] and res["repro"]["match"] and res["repro"]["n_got"] == len(exp)
    with patched(REPRO_DAY=day):
        bad = run(f, b, stage="features", expect=exp[1:] + [{"sym": "ZZZ"}])
    assert bad["repro"]["match"] is False and bad["repro"]["missing"] == ["ZZZ"] \
        and bad["repro"]["extra"] == [exp[0]["sym"]]


# ── 21 ───────────────────────────────────────────────────────────────────────
def test_21_cap_as_of_day_keys_and_dupes():
    idx = pd.DatetimeIndex(["2026-09-24 04:00", "2026-09-25 04:00", "2026-09-28 00:00", "2026-09-29 00:00"])
    df = mkframe([1, 2, 3, 4], index=idx)
    cap = G.cap_as_of(df, "2026-09-28")
    assert G.day_keys(cap) == ["2026-09-24", "2026-09-25", "2026-09-28"]   # 00:00 on AS_OF+1 dropped
    idx2 = pd.DatetimeIndex(["2026-09-25 04:00", "2026-09-28 04:00", "2026-09-28 00:00"])
    d2, n = G.dedupe_day_keys(mkframe([1.0, 2.0, 3.0], index=idx2))
    assert n == 1 and list(d2["close"]) == [1.0, 3.0]                         # last row kept


# ── 22 ───────────────────────────────────────────────────────────────────────
def test_22_beta63():
    n = 150
    rng = np.random.default_rng(8)
    bret = rng.normal(0, 0.01, n); bret[0] = 0
    B = 100 * np.cumprod(1 + bret)
    y = 1.3 * bret + rng.normal(0, 0.005, n); y[0] = 0
    C = 50 * np.cumprod(1 + y)
    P = G.build_panel({"X": mkframe(C)}, cal_of(mkframe(C)))
    f = G.features_prev(P, B)
    t = 120
    xs = B[t - 63:t] / B[t - 64:t - 1] - 1
    ys = C[t - 63:t] / C[t - 64:t - 1] - 1
    assert f["beta63"][0, t] == pytest.approx(np.polyfit(xs, ys, 1)[0], rel=1e-8)
    B2 = B.copy(); B2[t] *= 1.05
    assert G.features_prev(P, B2)["beta63"][0, t] == f["beta63"][0, t]
    B3 = B.copy(); B3[t - 1] *= 1.05
    assert G.features_prev(P, B3)["beta63"][0, t] != pytest.approx(f["beta63"][0, t], rel=1e-6)
    Cg = C.copy(); Cg[t - 10:t - 5] = np.nan
    P2 = G.build_panel({"X": mkframe(Cg)}, cal_of(mkframe(C)))
    fb = G.features_prev(P2, B)
    assert np.isnan(fb["beta63"][0, t])                                      # < BETA_MIN_PAIRS pairs
    assert not G.feature_ok(fb, G.MATCH_VARS)[0, t]                          # -> no_features


# ── 23 ───────────────────────────────────────────────────────────────────────
def test_23_balance_on_primary_eligible_subset():
    fr, b = _rand_frames(n_names=4, T=200)
    ctx = _ctx(fr, b)
    T = ctx["T"]
    tp = T - 1 - G.H_PRIMARY
    def tabs(bad_t):
        rows_s, rows_p, pairs = [], [], []
        for k in range(30):
            t = 100 + k
            rows_s.append(_row(t, r21=k * 0.01)); rows_p.append(_row(t, r21=k * 0.01))
        for k in range(10):
            rows_s.append(_row(bad_t, r21=5.0 + k)); rows_p.append(_row(bad_t, r21=-5.0 - k))
        s, p = _tab(rows_s), _tab(rows_p)
        s["i"] = 0; p["i"] = 1
        pr = pd.DataFrame({"sid": s["id"], "pid": p["id"], "t": s["day"], "dist": 0.0, "i_s": 0, "i_p": 1})
        return s, p, pr
    s, p, pr = tabs(tp + 3)
    bal = G.balance_report(ctx, s, p, pr, [], np.ones(len(MV)), 0.6, MV)
    assert bal["balanced"] and bal["n_pairs"] == 30
    s, p, pr = tabs(tp - 3)
    bal = G.balance_report(ctx, s, p, pr, [], np.ones(len(MV)), 0.6, MV)
    assert not bal["balanced"]


# ── 24 ───────────────────────────────────────────────────────────────────────
def test_24_near_floor_audit_never_filters():
    f, b, _, _ = synth(drift=0.03, low_price_groups=20)
    r1 = run(f, b, cache=False)
    r2 = run(f, b, cache=False, NEAR_FLOOR_BAND=1.0)
    assert r1["data_audit"]["near_floor"]["sig"] > 0
    assert r2["data_audit"]["near_floor"] == {"sig": 0, "twin": 0, "n_pairs": r1["data_audit"]["near_floor"]["n_pairs"]}
    assert r1["primary"]["h10_O"]["n_pairs"] == r2["primary"]["h10_O"]["n_pairs"]
    assert r1["primary"]["h10_O"]["lift"] == r2["primary"]["h10_O"]["lift"]
