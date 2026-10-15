"""🎢 HIGH BETA — the down-day study behind the Chart Maps High Beta tab.

THE ASK (Ajay 2026-10-14, verbatim, the part this study answers)
  "a lot of AI stocks are down like 5 to 10% today like NBIS, IREN. Yeah look
   at historically but today after the CPI it was all down"

The tab ORDERS today's red High-Beta names by β × today's drop. Whether a
High-Beta name that closed down hard does anything different in the next few
sessions is a claim, and a claim ships with this script, a CI and a placebo
(house rule). THE PRIOR IS NULL: green-on-a-red-day measured NO_SIGNAL
(−0.30pp [−0.76, +0.15]); 🛡️ T1 no_signal, T2 INVERTED; Hot Pullback +0.100R
with a CI spanning 0.

PRE-REGISTERED in `docs/research/high_beta_2026_10_14_prereg.md`. The prereg is
committed BEFORE any outcome run; its hash is passed as `--prereg-commit` and
written into the artifact. Nothing below may change after that commit without a
new prereg.

  Q1 PRIMARY — every session d (ALL days, any SPY direction) in the last
     `SESSIONS_MAX` SPY sessions with a full β window behind it and
     max(`HORIZONS`) sessions after it. Rows = names with β_d ≥ `HB.B15_MIN`
     (β_d = the house cov/var of the `HB.BETA_LOOKBACK` daily log returns
     ENDING d−1, no holes, 2 dp — `sepa.beta._beta` on a gap-free name) and a
     close-to-close return r_d. Cohort R: r_d ≤ −`HB.DOWN_CHIP_PCT`%. Placebo
     P: the same session, the same β tercile (rank-based within that day's
     R ∪ P rows, ties by symbol), r_d > −cut. Outcome Y_3 = close_{d+3} /
     close_d − 1 (%), every bar d..d+3 present (no gap-bridging).
     Contrast_d = Σ_cells n_R (mean Y_R − mean Y_P) / Σ n_R over cells holding
     both; pooled = Σ_d num_d / Σ_d w_d (R-weighted).
     CI (A6): a moving-block bootstrap over sessions (block `BLOCK_LEN`)
     CROSSED with an iid bootstrap over symbols — per draw, session weights
     (block counts) × symbol weights (multinomial counts) = the row weight;
     ONE weight matrix shared by every series; `DRAWS_DEFAULT` draws, seed
     `SEED_DEFAULT`, 95% percentile CI. The session-only CI sits beside it.
  Reported, NEVER the verdict: Y_1 and Y_5; MFE_3 / MAE_3 contrasts (MFE is
     mechanically larger for volatile names); the raw cohort / placebo means
     (the expectancy line); the share of R whose 3-session low printed a
     further cut% under close_d (the drawdown line — a proxy, no stop exists);
     "SPY-red days only" (SPY r_d < 0) and SPY-green days; β ≥ `HB.B20_MIN`;
     the top `HB.TOP_PCT`% (that day's rated cross-section, ties included —
     `HB.categories`); σ tercile × β tercile cells (the volatility check);
     LEAVE-TOP-5-SESSIONS-OUT (the `LEAVE_OUT_TOP` sessions with the largest
     contribution in the direction of the pooled sign dropped); a label
     shuffle within (d × cell), `SHUFFLE_DRAWS` draws; first vs second half.

VERDICT (fixed): sessions with a contrast < MIN_BUCKET_N or no CI ->
too_small; CI lower > 0 -> separates; CI upper < 0 -> inverted; else
no_signal (a bound exactly 0 is no_signal). `resiliency_study.verdict`.

SURVIVORS ONLY (A7): the cohort is TODAY's full ∪ Nasdaq-100 list; a name that
left it is absent from both groups. Said in the artifact and the served line.

LEAK RULE: β / σ read bars ≤ d−1, the cohort reads d's close, the outcomes
d+1..d+k only — `check_no_leak` raises otherwise (a test moves the feature
window onto d and watches it fail).

NOTHING HERE IS TYPED TWICE: the cuts are `chart_maps.high_beta_tab`'s; the
strata, CI, verdict, clock and as-of helpers are `scripts.resiliency_study`'s;
`MIN_BUCKET_N` is `scripts.explosive_study`'s. This file never imports
`supply_demand.key_levels`.

READ-ONLY. Every pymongo write method is replaced in-process by a recorded
no-op before anything connects; the attempted writes are printed.

RUN (OUTSIDE 09:00–16:30 ET, in a THROWAWAY container — never inside the live api):
  docker run --rm --cpus 4 --memory 3g --network cheetah-market-app_default \\
      -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e TZ=America/New_York \\
      -e SEPA_UNIVERSE_MODE=full -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 \\
      -v <tree>/backend:/app:ro -v cheetah-market-app_cheetah-scans:/root/.cheetah:ro \\
      -v <out dir>:/out -w /out cheetah-api:latest \\
      python -u /app/scripts/high_beta_study.py --prereg-commit <hash> \\
      --out /out/high_beta_measured.json
  cp <out dir>/high_beta_measured.json backend/scripts/high_beta_measured.json
Then paste the printed `measured_literal` into `chart_maps/high_beta_measured.py`.
"""
from __future__ import annotations

import argparse
import ast
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chart_maps import high_beta_tab as HB  # noqa: E402
from scripts import resiliency_study as RS  # noqa: E402
from scripts.explosive_study import MIN_BUCKET_N  # noqa: E402
from sepa import prices  # noqa: E402
from supply_demand import demand_reentry as DR  # noqa: E402

ET = ZoneInfo("America/New_York")
STUDY = "high_beta_2026_10_14"
SCRIPT = "backend/scripts/high_beta_study.py"
ARTIFACT = "backend/scripts/high_beta_measured.json"
PREREG = "docs/research/high_beta_2026_10_14_prereg.md"
UNIVERSE_KEY = "full"
SESSIONS_MAX = 250             # MINE (AMENDMENTS §8) — ~244 fit a 2y cache (n served)
DRAWS_DEFAULT = 2000           # MINE (AMENDMENTS §8)
SEED_DEFAULT = 20261014        # MINE (AMENDMENTS §8)
HORIZONS = (1, 3, 5)           # MINE (AMENDMENTS §8) — sessions after d
PRIMARY_H = 3                  # MINE (AMENDMENTS §8)
BLOCK_LEN = 5                  # MINE (AMENDMENTS §8, A6) — moving-block length in sessions
LEAVE_OUT_TOP = 5              # MINE (AMENDMENTS §8, A6)
SHUFFLE_DRAWS = 200            # MINE (AMENDMENTS §8)
BETA_BINS = 3                  # MINE (AMENDMENTS §8) — β terciles
SIGMA_BINS = 3                 # MINE (AMENDMENTS §8) — σ terciles (the volatility check)
CI_PCT = RS.CI_PCT             # 95
FEATURE_END_OFFSET = 1         # β / σ windows END at d−1 (the leak rule; a test mutates it)
BENCH = HB.BENCH
B15, B20, TOP_PCT, CUT = HB.B15_MIN, HB.B20_MIN, HB.TOP_PCT, HB.DOWN_CHIP_PCT
BETA_LOOKBACK, SIGMA_BARS = HB.BETA_LOOKBACK, HB.SIGMA_BARS
ATTEMPTED: list = []
LIMITS = [
    "survivors-only cohort: the universe is today's full ∪ Nasdaq-100 list — names that left it "
    "are absent from both groups",
    "two-year price cache: the first session needs a full year of β window behind it, so about "
    "one year of sessions exists",
    "the 1-, 3- and 5-session windows of adjacent sessions overlap; the moving-block bootstrap "
    "keeps runs of sessions together but does not remove the overlap",
    "MFE is mechanically larger for volatile names — reported, never the verdict",
    "no stop exists in this read: the drawdown line is the share whose 3-session low printed a "
    "further cut% under the close, a proxy, not a stop-out rate",
    "close-to-close returns on the cached daily bars; no intraday entry is modelled",
]


class LeakError(AssertionError):
    """A feature window that reaches the cohort day, or an outcome that does."""


# ---------------------------------------------------------------------------
# the leak rule
# ---------------------------------------------------------------------------
def feature_window(d: int, length: int) -> range:
    """Return indices (return t = close t−1 -> t) a feature at session d reads."""
    end = d - FEATURE_END_OFFSET
    return range(end - length + 1, end + 1)


def outcome_window(d: int, h: int) -> range:
    return range(d + 1, d + h + 1)


def check_no_leak(d: int, features, outcomes) -> None:
    for i in features:
        if i >= d:
            raise LeakError(f"a feature window for session {d} reads index {i}")
    for i in outcomes:
        if i <= d:
            raise LeakError(f"an outcome window for session {d} reads index {i}")


# ---------------------------------------------------------------------------
# arrays on the SPY calendar (PURE)
# ---------------------------------------------------------------------------
def _rolling_sum(a: np.ndarray, n: int) -> np.ndarray:
    """out[t] = sum a[t−n+1 .. t] (NaN-free input), NaN for t < n−1."""
    c = np.concatenate([[0.0], np.cumsum(a)])
    out = np.full(len(a), np.nan)
    if len(a) >= n:
        out[n - 1:] = c[n:] - c[:-n]
    return out


def rolling_beta(lr: np.ndarray, blr: np.ndarray, n: int = BETA_LOOKBACK) -> np.ndarray:
    """β over the n returns ending at t (cov / var; the population and sample
    denominators cancel), NaN unless all n pairs are present — sepa.beta._beta
    on a gap-free name."""
    ok = np.isfinite(lr) & np.isfinite(blr)
    x, y = np.where(ok, lr, 0.0), np.where(ok, blr, 0.0)
    cnt = _rolling_sum(ok.astype(float), n)
    sx, sy = _rolling_sum(x, n), _rolling_sum(y, n)
    sxy, syy = _rolling_sum(x * y, n), _rolling_sum(y * y, n)
    with np.errstate(invalid="ignore", divide="ignore"):
        cov = sxy - sx * sy / n
        var = syy - sy * sy / n
        b = np.where((cnt == n) & (var > 0), cov / np.where(var > 0, var, 1.0), np.nan)
    return b


def rolling_sigma(r: np.ndarray, n: int = SIGMA_BARS) -> np.ndarray:
    """Sample stdev of the n % returns ending at t, NaN unless all present."""
    ok = np.isfinite(r)
    x = np.where(ok, r, 0.0)
    cnt = _rolling_sum(ok.astype(float), n)
    s, ss = _rolling_sum(x, n), _rolling_sum(x * x, n)
    with np.errstate(invalid="ignore"):
        var = (ss - s * s / n) / (n - 1)
        out = np.where(cnt == n, np.sqrt(np.maximum(var, 0.0)), np.nan)
    return out


def series_for(arr: dict, spy_lr: np.ndarray) -> dict:
    """Per name on the SPY calendar: log returns, % returns, rolling β / σ
    (indexed by the window's END), and the closes / highs / lows."""
    c = arr["close"]
    prev = np.concatenate([[np.nan], c[:-1]])
    with np.errstate(invalid="ignore", divide="ignore"):
        lr = np.log(c / prev)
        r = (c / prev - 1.0) * 100.0
    return {"close": c, "high": arr["high"], "low": arr["low"], "r": r,
            "beta": rolling_beta(lr, spy_lr), "sigma": rolling_sigma(r)}


def session_indices(n_days: int, *, sessions_max: int = SESSIONS_MAX) -> list:
    """d with a full β window behind it (returns start at index 1) and
    max(HORIZONS) sessions after it; the last `sessions_max`."""
    first = BETA_LOOKBACK + FEATURE_END_OFFSET
    last = n_days - 1 - max(HORIZONS)
    ds = list(range(first, last + 1))
    return ds[-sessions_max:] if sessions_max else []


def outcome(s: dict, d: int, h: int) -> tuple:
    """(Y, MFE, MAE) in % against close_d; None unless every bar d..d+h exists."""
    c0 = s["close"][d]
    w = outcome_window(d, h)
    cl, hi, lo = s["close"][w.start:w.stop], s["high"][w.start:w.stop], s["low"][w.start:w.stop]
    if not np.isfinite(c0) or len(cl) != h or not (np.isfinite(cl).all() and np.isfinite(hi).all()
                                                   and np.isfinite(lo).all()):
        return None, None, None
    return ((cl[-1] / c0 - 1.0) * 100.0, (hi.max() / c0 - 1.0) * 100.0,
            (lo.min() / c0 - 1.0) * 100.0)


def build_rows(frames: dict, *, as_of: str, sessions_max: int = SESSIONS_MAX) -> tuple:
    """(rows DataFrame, days, sessions). One row per (session, name) with a β
    and a return on d: d, sym, beta, sigma, r, spy_r, top20 flag, y/mfe/mae per
    horizon (NaN when a bar is missing)."""
    bdf = frames.get(BENCH)
    if bdf is None or len(bdf) == 0:
        raise ValueError(f"no {BENCH} bars — the sessions cannot be dated")
    days = sorted(d for d in RS._closes_upto(bdf, as_of))
    if len(days) < 2:
        raise ValueError(f"{BENCH} has fewer than two closed bars up to {as_of}")
    spy = series_for(RS.aligned(bdf, days), np.zeros(len(days)))
    spy_c = spy["close"]
    with np.errstate(invalid="ignore", divide="ignore"):
        spy_lr = np.log(spy_c / np.concatenate([[np.nan], spy_c[:-1]]))
    sess = session_indices(len(days), sessions_max=sessions_max)
    per = {}
    for sym, fr in frames.items():
        if sym == BENCH or fr is None or len(fr) == 0:
            continue
        per[sym] = series_for(RS.aligned(fr, days), spy_lr)
    rows = []
    for d in sess:
        fe = d - FEATURE_END_OFFSET
        check_no_leak(d, feature_window(d, BETA_LOOKBACK), outcome_window(d, max(HORIZONS)))
        check_no_leak(d, feature_window(d, SIGMA_BARS), outcome_window(d, max(HORIZONS)))
        day_betas = {}
        for sym, s in per.items():
            b = s["beta"][fe]
            if np.isfinite(b) and np.isfinite(s["r"][d]):
                day_betas[sym] = round(float(b), 2)
        _cats, blk = HB.categories(day_betas)
        cut = blk["top20"]["cut_beta"]
        for sym, b in day_betas.items():
            s = per[sym]
            rec = {"d": days[d], "sym": sym, "beta": b,
                   "sigma": float(s["sigma"][fe]) if np.isfinite(s["sigma"][fe]) else np.nan,
                   "r": float(s["r"][d]), "spy_r": float(spy["r"][d]),
                   "top20": bool(cut is not None and b >= cut)}
            for h in HORIZONS:
                y, mfe, mae = outcome(s, d, h)
                rec[f"y{h}"] = np.nan if y is None else float(y)
                rec[f"mfe{h}"] = np.nan if mfe is None else float(mfe)
                rec[f"mae{h}"] = np.nan if mae is None else float(mae)
            rows.append(rec)
    cols = ["d", "sym", "beta", "sigma", "r", "spy_r", "top20"] + [
        f"{k}{h}" for h in HORIZONS for k in ("y", "mfe", "mae")]
    return pd.DataFrame(rows, columns=cols), days, [days[d] for d in sess]


# ---------------------------------------------------------------------------
# the contrast + the two-way bootstrap (PURE)
# ---------------------------------------------------------------------------
def weights(n_sess: int, n_sym: int, draws: int, seed: int) -> tuple:
    """(session weights draws × n_sess — moving blocks of BLOCK_LEN, symbol
    weights draws × n_sym — multinomial). ONE pair shared by every series."""
    rng = np.random.default_rng(seed)
    ws = np.zeros((draws, max(n_sess, 0)))
    if n_sess > 0:
        L = min(BLOCK_LEN, n_sess)
        nb = int(math.ceil(n_sess / L))
        starts = rng.integers(0, n_sess - L + 1, size=(draws, nb))
        idx = (starts[:, :, None] + np.arange(L)[None, None, :]).reshape(draws, -1)[:, :n_sess]
        for k in range(draws):
            ws[k] = np.bincount(idx[k], minlength=n_sess)
    wy = np.zeros((draws, max(n_sym, 0)))
    if n_sym > 0:
        picks = rng.integers(0, n_sym, size=(draws, n_sym))
        for k in range(draws):
            wy[k] = np.bincount(picks[k], minlength=n_sym)
    return ws, wy


def _wcontrast(g, lab, y, w, ng) -> Optional[float]:
    n1 = np.bincount(g, weights=w * lab, minlength=ng)
    n0 = np.bincount(g, weights=w * (1.0 - lab), minlength=ng)
    s1 = np.bincount(g, weights=w * lab * y, minlength=ng)
    s0 = np.bincount(g, weights=w * (1.0 - lab) * y, minlength=ng)
    ok = (n1 > 0) & (n0 > 0)
    if not ok.any():
        return None
    num = n1[ok] * (s1[ok] / n1[ok] - s0[ok] / n0[ok])
    den = n1[ok].sum()
    return float(num.sum() / den) if den > 0 else None


def analyse(df: pd.DataFrame, ycol: str, *, sess_codes: dict, sym_codes: dict, W: tuple,
            covs=(("beta", BETA_BINS),), shuffle_draws: int = 0, seed: int = SEED_DEFAULT) -> dict:
    """One series: the R vs P contrast on `ycol`, its two-way and session-only
    CIs, the verdict, and the expectancy / drawdown lines."""
    out = {"verdict": "too_small", "contrast_pp": None, "ci": None, "ci_session_only": None,
           "n_sessions": 0, "n_cohort": 0, "n_placebo": 0, "cohort_mean_pct": None,
           "placebo_mean_pct": None, "mae_mean_pct": None, "drawdown_share_pct": None}
    if df is None or len(df) == 0:
        return out
    df = df[np.isfinite(df[ycol].to_numpy(dtype=float))]
    for col, _k in covs:
        df = df[np.isfinite(df[col].to_numpy(dtype=float))]
    df = df.reset_index(drop=True)
    if len(df) == 0:
        return out
    lab = (df["r"].to_numpy(dtype=float) <= -CUT).astype(float)
    y = df[ycol].to_numpy(dtype=float)
    cell = RS.assign_cells(df, "d", list(covs))
    sc = np.array([sess_codes[d] for d in df["d"]], dtype=np.int64)
    yc = np.array([sym_codes[s] for s in df["sym"]], dtype=np.int64)
    n_sess = len(sess_codes)
    num, w = RS.cell_contrast(sc, cell, lab, y, n_sess)
    n_ok = int((w > 0).sum())
    point = RS.pooled(num, w)
    r_ = lab == 1
    out.update(n_sessions=n_ok, n_cohort=int(r_.sum()), n_placebo=int((~r_).sum()),
               cohort_mean_pct=RS._r(y[r_].mean()) if r_.any() else None,
               placebo_mean_pct=RS._r(y[~r_].mean()) if (~r_).any() else None,
               contrast_pp=RS._r(point))
    mae_col = f"mae{ycol[-1]}" if ycol[-1].isdigit() else None
    if mae_col and mae_col in df.columns and r_.any():
        mae = df[mae_col].to_numpy(dtype=float)[r_]
        mae = mae[np.isfinite(mae)]
        if mae.size:
            out["mae_mean_pct"] = RS._r(mae.mean())
            out["drawdown_share_pct"] = RS._r(float((mae <= -CUT).mean()) * 100.0)
    if point is None:
        return out
    g = sc * (int(cell.max()) + 1) + cell
    _u, g = np.unique(g, return_inverse=True)
    ng = int(g.max()) + 1
    ws, wy = W
    two, one = [], []
    for k in range(ws.shape[0]):
        rw = ws[k][sc] * wy[k][yc]
        v = _wcontrast(g, lab, y, rw, ng)
        two.append(np.nan if v is None else v)
        v = _wcontrast(g, lab, y, ws[k][sc], ng)
        one.append(np.nan if v is None else v)
    out["ci"] = RS.ci_of(two)
    out["ci_session_only"] = RS.ci_of(one)
    out["verdict"] = RS.verdict(n_ok, out["ci"])
    if shuffle_draws:
        sh = RS.shuffle_lifts(sc, cell, lab, y, n_sess, shuffle_draws, seed)
        sh = sh[np.isfinite(sh)]
        if sh.size:
            out["shuffle_pct"] = RS._r(float((sh >= point).mean()) * 100.0)
            out["shuffle_mean_pp"] = RS._r(sh.mean())
            out["shuffle_band"] = RS.ci_of(sh)
    out["_per_session"] = {d: (float(num[sess_codes[d]]), float(w[sess_codes[d]]))
                           for d in sess_codes if w[sess_codes[d]] > 0}
    return out


def leave_top_out(df: pd.DataFrame, per_session: dict, point, **kw) -> dict:
    """The primary with the LEAVE_OUT_TOP sessions contributing most in the
    direction of the pooled sign dropped."""
    if not per_session or point is None:
        return {"verdict": "too_small", "contrast_pp": None, "ci": None, "n_sessions": 0,
                "dropped": []}
    sign = 1.0 if point >= 0 else -1.0
    top = sorted(per_session, key=lambda d: (-sign * per_session[d][0], d))[:LEAVE_OUT_TOP]
    blk = analyse(df[~df["d"].isin(top)], f"y{PRIMARY_H}", **kw)
    blk["dropped"] = sorted(top)
    return blk


def _clean(blk: dict) -> dict:
    return {k: v for k, v in blk.items() if not k.startswith("_")}


def run_study(frames: dict, *, as_of: str, draws: int = DRAWS_DEFAULT, seed: int = SEED_DEFAULT,
              sessions_max: int = SESSIONS_MAX, shuffle_draws: int = SHUFFLE_DRAWS) -> dict:
    """The artifact body (everything but the provenance keys main() adds)."""
    rows, days, sessions = build_rows(frames, as_of=as_of, sessions_max=sessions_max)
    hb = rows[rows["beta"] >= B15] if len(rows) else rows
    sess_codes = {d: i for i, d in enumerate(sessions)}
    syms = sorted(set(rows["sym"])) if len(rows) else []
    sym_codes = {s: i for i, s in enumerate(syms)}
    W = weights(len(sessions), len(syms), draws, seed)
    kw = {"sess_codes": sess_codes, "sym_codes": sym_codes, "W": W}
    prim = analyse(hb, f"y{PRIMARY_H}", shuffle_draws=shuffle_draws, seed=seed, **kw)
    out = {"primary": {"horizon": PRIMARY_H, **_clean(prim)}}
    for h in HORIZONS:
        if h != PRIMARY_H:
            out[f"h{h}"] = {"horizon": h, **_clean(analyse(hb, f"y{h}", **kw))}
    out["mfe3"] = _clean(analyse(hb, f"mfe{PRIMARY_H}", **kw))
    out["mae3"] = _clean(analyse(hb, f"mae{PRIMARY_H}", **kw))
    out["spy_red"] = _clean(analyse(hb[hb["spy_r"] < 0], f"y{PRIMARY_H}", **kw))
    out["spy_green"] = _clean(analyse(hb[hb["spy_r"] > 0], f"y{PRIMARY_H}", **kw))
    out["b20"] = _clean(analyse(rows[rows["beta"] >= B20] if len(rows) else rows,
                                f"y{PRIMARY_H}", **kw))
    out["top20"] = _clean(analyse(rows[rows["top20"]] if len(rows) else rows,
                                  f"y{PRIMARY_H}", **kw))
    out["sigma_matched"] = _clean(analyse(hb, f"y{PRIMARY_H}",
                                          covs=(("sigma", SIGMA_BINS), ("beta", BETA_BINS)), **kw))
    out["leave_top5"] = _clean(leave_top_out(hb, prim.get("_per_session"),
                                             prim.get("contrast_pp"), **kw))
    half = len(sessions) // 2
    out["first_half"] = _clean(analyse(hb[hb["d"].isin(sessions[:half])], f"y{PRIMARY_H}", **kw))
    out["second_half"] = _clean(analyse(hb[hb["d"].isin(sessions[half:])], f"y{PRIMARY_H}",
                                        **kw))
    out.update(n_sessions_window=len(sessions), first_session=sessions[0] if sessions else None,
               last_session=sessions[-1] if sessions else None,
               n_names_with_bars=len([s for s in frames if s != BENCH]),
               n_rows=int(len(rows)), n_hb_rows=int(len(hb)), first_bar=days[0],
               last_bar=days[-1])
    return out


def definitions(draws: int, seed: int) -> dict:
    return {"B15_MIN": B15, "B20_MIN": B20, "TOP_PCT": TOP_PCT, "DOWN_CHIP_PCT": CUT,
            "BETA_LOOKBACK": int(BETA_LOOKBACK), "SIGMA_BARS": int(SIGMA_BARS), "BENCH": BENCH,
            "MIN_BUCKET_N": int(MIN_BUCKET_N), "SESSIONS_MAX": SESSIONS_MAX,
            "HORIZONS": list(HORIZONS), "PRIMARY_H": PRIMARY_H, "BLOCK_LEN": BLOCK_LEN,
            "LEAVE_OUT_TOP": LEAVE_OUT_TOP, "BETA_BINS": BETA_BINS, "SIGMA_BINS": SIGMA_BINS,
            "CI_PCT": CI_PCT, "draws": int(draws), "seed": int(seed),
            "shuffle_draws": SHUFFLE_DRAWS, "cohort": "survivors-only (today's list)",
            "refuse_window_et": f"{RS.REFUSE_FROM[0]:02d}:{RS.REFUSE_FROM[1]:02d}–"
                                f"{RS.REFUSE_TO[0]:02d}:{RS.REFUSE_TO[1]:02d}",
            "universe": f"{UNIVERSE_KEY} ∪ nasdaq100 − ETFs − delisted"}


SECONDARY_KEYS = ("verdict", "contrast_pp", "ci", "n_sessions")
PRIMARY_KEYS = ("verdict", "horizon", "contrast_pp", "ci", "ci_session_only", "n_sessions",
                "n_cohort", "n_placebo", "cohort_mean_pct", "placebo_mean_pct", "mae_mean_pct",
                "drawdown_share_pct")
SECONDARY_BLOCKS = ("h1", "h5", "mfe3", "spy_red", "spy_green", "b20", "top20", "sigma_matched",
                    "leave_top5")


def measured_literal(art: dict) -> dict:
    """The `chart_maps.high_beta_measured.MEASURED` literal for an artifact."""
    def pick(blk, keys):
        blk = blk if isinstance(blk, dict) else {}
        return {k: blk.get(k) for k in keys}
    out = {"status": "measured", "script": SCRIPT, "artifact": ARTIFACT,
           "run_date": art.get("run_date"), "as_of": art.get("as_of"),
           "prereg_commit": art.get("prereg_commit"), "cohort": "survivors-only",
           "primary": pick(art.get("primary"), PRIMARY_KEYS)}
    for k in SECONDARY_BLOCKS:
        out[k] = pick(art.get(k), SECONDARY_KEYS)
    return out


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------
def block_writes() -> None:
    """Every pymongo write method -> a recorded no-op (this process only)."""
    from pymongo.collection import Collection

    def _make(name):
        def _noop(self, *a, **k):
            ATTEMPTED.append(f"{getattr(self, 'name', '?')}.{name}")
            return "blocked_index" if name == "create_index" else None
        return _noop
    for m in RS.WRITE_METHODS:
        if hasattr(Collection, m):
            setattr(Collection, m, _make(m))


def default_universe(*, universe_fn=None, qqq_fn=None, etf_fn=None, is_delisted=None) -> tuple:
    """(symbols, ndx block): full ∪ Nasdaq-100 − ETFs − delisted (today's list)."""
    qqq, qblock = HB.qqq_members(qqq_fn)
    syms, _n = HB.resolve_symbols(UNIVERSE_KEY, qqq,
                                  universe_fn or (lambda k: DR._resolve_universe(k)[0]))
    if etf_fn is None:
        from chart_maps import fallen_tab as FAL
        etf_fn = FAL._static_etfs
    if is_delisted is None:
        from sepa import symbols
        is_delisted = symbols.is_delisted
    etfs = etf_fn()
    return [s for s in syms if s not in etfs and not is_delisted(s)], qblock


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="High Beta down-day study (read-only).")
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD (default: last closed session)")
    ap.add_argument("--draws", type=int, default=DRAWS_DEFAULT)
    ap.add_argument("--seed", type=int, default=SEED_DEFAULT)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "high_beta_measured.json"))
    ap.add_argument("--prereg-commit", default=None,
                    help="the commit hash of the prereg (required for an outcome run)")
    ap.add_argument("--force-window", action="store_true", help="run inside 09:00–16:30 ET anyway")
    ap.add_argument("--limit", type=int, default=None,
                    help="SMOKE: first N names only — NOT QUOTABLE, never the default --out")
    return ap.parse_args(argv)


def main(argv=None, *, now: Optional[datetime] = None, universe_fn=None, frames_fn=None,
         block=True) -> int:
    a = parse_args(argv)
    now_et = (now or datetime.now(tz=ET)).astimezone(ET)
    if RS.refused_window(now_et) and not a.force_window:
        print(f"REFUSED: {now_et:%H:%M} ET is inside {RS.REFUSE_FROM[0]:02d}:"
              f"{RS.REFUSE_FROM[1]:02d}–{RS.REFUSE_TO[0]:02d}:{RS.REFUSE_TO[1]:02d} ET; pass "
              "--force-window to override.", file=sys.stderr)
        return 2
    smoke = a.limit is not None
    default_out = str(Path(__file__).resolve().parent / "high_beta_measured.json")
    if smoke and str(Path(a.out).resolve()) == default_out:
        print("REFUSED: a --limit smoke never writes the real artifact path.", file=sys.stderr)
        return 2
    if not smoke and not (a.prereg_commit or "").strip():
        print("REFUSED: an outcome run needs --prereg-commit (commit the prereg first).",
              file=sys.stderr)
        return 2
    if block:
        block_writes()
    t0 = time.time()
    if universe_fn is not None:
        syms, qblock = [str(s).upper() for s in universe_fn()], {"available": None}
    else:
        syms, qblock = default_universe()
    if smoke:
        syms = syms[:max(0, int(a.limit))]
    frames = (frames_fn or prices.bulk_cached_frames)(syms + [BENCH])
    if not frames or frames.get(BENCH) is None:
        print(f"REFUSED: the price cache returned no {BENCH} frame.", file=sys.stderr)
        return 2
    bench_days = sorted(HB.RES.closes_by_day(frames[BENCH]))
    as_of = a.as_of or RS.default_as_of(bench_days, now_et)
    if not as_of:
        print("REFUSED: no closed session to measure up to.", file=sys.stderr)
        return 2
    body = run_study(frames, as_of=as_of, draws=a.draws, seed=a.seed)
    art = {"study": STUDY, "script": SCRIPT, "prereg": PREREG,
           "prereg_commit": (a.prereg_commit or None), "smoke": bool(smoke),
           "run_date": now_et.date().isoformat(), "as_of": as_of, "universe_n": len(syms),
           "nasdaq100": qblock, "definitions": definitions(a.draws, a.seed), **body,
           "limits": list(LIMITS), "runtime_sec": round(time.time() - t0, 1),
           "attempted_writes": sorted(set(ATTEMPTED))}
    Path(a.out).write_text(json.dumps(art, indent=1, allow_nan=False, default=str) + "\n",
                           encoding="utf-8")
    p = art["primary"]
    print(f"primary (Y_{PRIMARY_H}, all sessions): {p['verdict']} {p['contrast_pp']}pp CI "
          f"{p['ci']} (session-only {p['ci_session_only']}) · sessions {p['n_sessions']} · "
          f"cohort {p['n_cohort']} / placebo {p['n_placebo']}")
    for k in SECONDARY_BLOCKS:
        b = art.get(k) or {}
        print(f"{k}: {b.get('verdict')} {b.get('contrast_pp')}pp CI {b.get('ci')} · "
              f"sessions {b.get('n_sessions')}")
    print(f"names {art['n_names_with_bars']} of {len(syms)} · as_of {as_of} · attempted writes "
          f"{art['attempted_writes']} · {art['runtime_sec']}s -> {a.out}")
    print("measured_literal (paste into chart_maps/high_beta_measured.py):")
    print(json.dumps(measured_literal(art), indent=4, ensure_ascii=False))
    return 0


def imported_modules(path: Optional[str] = None) -> set:
    """Top-level module names this file imports (the import-scope test reads it)."""
    src = Path(path or __file__).read_text(encoding="utf-8")
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods.update(n.name for n in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.update(f"{node.module}.{n.name}" for n in node.names)
    return mods


if __name__ == "__main__":
    raise SystemExit(main())
