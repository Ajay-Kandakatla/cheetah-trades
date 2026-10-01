"""🛡️ RESILIENCY — the persistence study behind the Chart Maps Resiliency tab.

THE ASK (Ajay 2026-09-30, verbatim)
  "Can you build me a new tab- Resileincy. This is to help me with #1 - Stocks
   that are not going to by more than 0.5% during a T1 event like FOMC or any
   others like todays Inflation and GDP track T2s as well. #3 - Tape is
   positive and bullish EOD or Pre market. but volume has to be accounted for.
   We have all of this data already."

The tab SHOWS which names held on past data days. Whether that says anything
about the NEXT data day is a claim, and a claim ships with this script, a CI
and a placebo (house rule). THE PRIOR IS NULL: the closest prior read —
green-on-a-red-day 2026-09-28 — measured NO_SIGNAL.

PRE-REGISTERED in `docs/research/resiliency_2026_09_30_prereg.md`. The prereg
is committed BEFORE any outcome run; the commit hash is passed as
`--prereg-commit` and written into the artifact. Nothing below may change
after that commit without a new prereg.

  Q1 PRIMARY — T1 persistence, walk-forward (out-of-sample by construction).
     Test events E = T1 sessions with at least HOLD_WINDOW_DAYS of trailing
     bars. Label R at E = the tab's own 🛡️ box (`box_pass(tier_stats(...))`)
     over the T1 sessions in [E - 365d, E) ONLY — never E itself
     (`check_no_leak`). Control = rated and not R. Outcome Y = `held(ret on E)`.
     Strata per E: σ quintile x β tercile of that day's rated cross-section
     (σ = `sigma_pct`, 50 bars before E; β = `beta`, 252 bars before E).
     Lift_E = Σ_cells n_R (mean Y_R - mean Y_C) / Σ n_R over cells holding both
     groups; pooled = R-weighted mean over E. 95% CI = bootstrap over event
     dates. Also: raw (unmatched) lift, the share of R in the lowest σ
     quintile, the stratified event-day return difference (the expectancy
     line), first half vs second half of E.
  PLACEBO P1 — the same contrast with Y on the first NON-event session after
     each E; event-specific = lift(E) - lift(P1) on the SAME resampled dates.
     THE Q1/Q2 VERDICT READS THIS CONTRAST (see VERDICTS).
  Q2 — Q1 on T2-only sessions.
  Q3 — EOD tape: every session d with >= 51 prior bars and a next session.
     Cohort = up close AND upper-half close; R = the accumulation day
     (`sepa.volume.accumulation_day`), control = the same two price legs on
     volume <= the 50-session average. Y = next-session close->close %; also
     next open->close. Strata = σ quintile per d; bootstrap over d; a
     label-shuffle placebo within d x σ cells. No stop exists here, so there
     is no stop-out rate — said so in the artifact.
  Q4 — pre-market: UNMEASURED (the intraday cache is <= 31 patchy sessions).

VERDICTS (pre-registered): clusters < MIN_BUCKET_N -> too_small; CI lower > 0
-> separates; CI upper < 0 -> inverted; else no_signal. For Q1/Q2 the CI the
verdict reads is the EVENT-SPECIFIC contrast (lift on E minus lift on the P1
placebo, same resampled dates) — NOT the stratified lift. Why (2026-09-30
critic, fix round): σ quintile x β tercile does not remove the low-volatility
confound. On a synthetic universe with NO persistence at all (iid returns,
holding driven only by σ and β) the stratified lift "separated" in 3 of 3
seeds (+5.78pp [4.26, 7.77] ...) while the placebo lift was just as large and
the event-specific CI spanned 0 every time. A quiet-name trait shows up on
ordinary days too; only the contrast against them is an event read.
`tests/test_resiliency_study.py` pins that synthetic null to no_signal.
Q1/Q2 `specific`: event_specific (the primary verdict separates) | general
(the stratified lift CI lower > 0 but the event-specific one is not — the
names also hold more on ordinary days: a trait, not an event read) | unclear.

NOTHING HERE IS TYPED TWICE. Every definition is imported from
`chart_maps.resiliency_tab` (the tab's own pure functions and constants),
`sepa.volume.accumulation_day` (the one accumulation-day engine) and
`scripts.explosive_study.MIN_BUCKET_N`. This file never imports
`supply_demand.key_levels` (the display-only import guard scans scripts/).

READ-ONLY. Every pymongo write method is replaced in-process by a recorded
no-op before anything connects; the attempted writes are printed.

RUN (OUTSIDE 09:00–16:30 ET, in a THROWAWAY container — never inside the live
api: a study there starved it into HTTP 524s on 2026-09-30):
  docker run --rm --cpus 4 --memory 3g --network cheetah-market-app_default \
      --env-file <file holding FRED_API_KEY> -e MONGO_URL=mongodb://mongo:27017 \
      -e MONGO_DB=cheetah -e TZ=America/New_York -e SEPA_UNIVERSE_MODE=full \
      -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 \
      -v <main tree>/backend:/app:ro -v cheetah-market-app_cheetah-scans:/root/.cheetah:ro \
      -v <out dir>:/out -w /out cheetah-api:latest \
      python -u /app/scripts/resiliency_study.py --prereg-commit <hash> \
      --out /out/resiliency_measured.json
  cp <out dir>/resiliency_measured.json backend/scripts/resiliency_measured.json
Then paste `measured_literal(<json>)` into `chart_maps/resiliency_measured.py`.
"""
from __future__ import annotations

import argparse
import ast
import json
import math
import sys
import time
from bisect import bisect_right
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import macro_calendar  # noqa: E402
from chart_maps import resiliency_tab as RT  # noqa: E402
from scripts.explosive_study import MIN_BUCKET_N  # noqa: E402
from sepa import prices  # noqa: E402
from sepa import volume as V  # noqa: E402
from supply_demand import demand_reentry as DR  # noqa: E402

ET = ZoneInfo("America/New_York")
STUDY = "resiliency_2026_09_30"
SCRIPT = "backend/scripts/resiliency_study.py"
ARTIFACT = "backend/scripts/resiliency_measured.json"
PREREG = "docs/research/resiliency_2026_09_30_prereg.md"
UNIVERSE_KEY = "full"
DRAWS_DEFAULT = 2000
SEED_DEFAULT = 20260930
SHUFFLE_DRAWS = 200            # the Q3 label-shuffle placebo (spec §3.13)
CI_PCT = 95.0
SIGMA_BINS = 5                 # σ quintile (spec §3.13 strata)
BETA_BINS = 3                  # β tercile
EOD_MIN_PRIOR_BARS = RT.VOL_AVG_BARS + 1    # 51: the 50-bar average + the prior close
REFUSE_FROM = (9, 0)           # the outcome run never overlaps the session (spec §3.13)
REFUSE_TO = (16, 30)
BENCH = RT.BENCH
WRITE_METHODS = ("insert_one", "insert_many", "update_one", "update_many", "replace_one",
                 "delete_one", "delete_many", "find_one_and_update", "find_one_and_replace",
                 "find_one_and_delete", "bulk_write", "create_index", "create_indexes",
                 "drop", "drop_index", "drop_indexes", "rename")
ATTEMPTED: list = []
LIMITS = [
    "survivorship: the universe is today's list — names that left it are absent from both "
    "groups",
    "two-year price cache: the first test event needs a full year of trailing data days, so "
    "only about one year of test events exists",
    "FRED revision dates (e.g. a retail-sales or GDP revision day) count as event sessions, "
    "exactly as the tab counts them",
    "ISM and Fed-speaker remarks have no dated history and are absent from T2",
    "pre-market volume history is the intraday cache (<= 31 patchy sessions) — Q4 is not "
    "measured",
    "Q3 has no stop, so no stop-out rate exists; the next-session return is the expectancy "
    "line",
]
Q4_BLOCK = {"verdict": "unmeasured",
            "reason": ("pre-market volume history is the intraday cache: ≤31 sessions, patchy — "
                       "too short to measure")}


class LeakError(AssertionError):
    """A label window that contains (or runs past) its own outcome event."""


# ---------------------------------------------------------------------------
# the clock gate + the as-of rule
# ---------------------------------------------------------------------------
def refused_window(now_et: datetime) -> bool:
    """True inside 09:00–16:30 ET (any day — the conservative reading)."""
    t = (now_et.hour, now_et.minute)
    return REFUSE_FROM <= t < REFUSE_TO


def default_as_of(trading_days: list, now_et: datetime) -> Optional[str]:
    """The last CLOSED session in the benchmark's cached calendar: a bar dated
    today counts only from 16:30 ET (the cache patches today's bar hourly)."""
    today = now_et.date().isoformat()
    closed_today = (now_et.hour, now_et.minute) >= REFUSE_TO
    ok = [d for d in trading_days if d < today or (closed_today and d == today)]
    return ok[-1] if ok else None


# ---------------------------------------------------------------------------
# frames -> aligned arrays
# ---------------------------------------------------------------------------
def frame_days(frame) -> list:
    """ET day ISO of every index stamp (== RT.day_iso, vectorized)."""
    idx = pd.DatetimeIndex(pd.to_datetime(frame.index))
    if idx.tz is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    return [d.isoformat() for d in idx.date]


def aligned(frame, days: list) -> dict:
    """{open, high, low, close, volume} numpy arrays on the benchmark calendar
    `days` — NaN where the name has no bar (no gap-bridging). Prices must be
    finite > 0; volume finite >= 0. A later duplicate day wins."""
    n = len(days)
    out = {k: np.full(n, np.nan) for k in ("open", "high", "low", "close", "volume")}
    if frame is None or len(frame) == 0:
        return out
    pos = {d: i for i, d in enumerate(days)}
    fdays = frame_days(frame)
    for col in out:
        if col not in frame.columns:
            continue
        vals = pd.to_numeric(frame[col], errors="coerce").to_numpy(dtype=float)
        for d, v in zip(fdays, vals):
            i = pos.get(d)
            if i is None:
                continue
            if not math.isfinite(v) or (v < 0 if col == "volume" else v <= 0):
                out[col][i] = np.nan
            else:
                out[col][i] = v
    return out


def _closes_upto(frame, as_of: str) -> dict:
    return {d: c for d, c in RT.closes_by_day(frame).items() if d <= as_of}


# ---------------------------------------------------------------------------
# windows, placebo sessions, the leak check
# ---------------------------------------------------------------------------
def _minus_days(iso: str, n: int) -> str:
    return (date.fromisoformat(iso) - timedelta(days=n)).isoformat()


def label_window(tier_sessions: dict, e_iso: str) -> dict:
    """The tier's sessions in [E - HOLD_WINDOW_DAYS, E) — the tab's own window
    (`event_sessions(start=session - HOLD_WINDOW_DAYS, end=session)`)."""
    lo = _minus_days(e_iso, RT.HOLD_WINDOW_DAYS)
    return {iso: v for iso, v in tier_sessions.items() if lo <= iso < e_iso}


def check_no_leak(e_iso: str, window) -> None:
    for iso in window:
        if iso >= e_iso:
            raise LeakError(f"label window for {e_iso} contains {iso}")


def placebo_session(days: list, e_iso: str, event_isos: set) -> Optional[str]:
    """The first trading day AFTER E that carries no T1/T2 print; None at the end."""
    i = bisect_right(days, e_iso)
    while i < len(days):
        if days[i] not in event_isos:
            return days[i]
        i += 1
    return None


def outcome_events(tier_sessions: dict, days: list) -> list:
    """Tier sessions with at least HOLD_WINDOW_DAYS of trailing bars."""
    if not days:
        return []
    first = days[0]
    return [e for e in tier_sessions if _minus_days(e, RT.HOLD_WINDOW_DAYS) >= first]


# ---------------------------------------------------------------------------
# strata + contrasts (vectorized; one code path for every question)
# ---------------------------------------------------------------------------
def quantile_bins(values, k: int, tiebreak=None) -> np.ndarray:
    """Rank-based bin 0..k-1 of each value within its own array (ties broken by
    `tiebreak`, then position — deterministic)."""
    v = np.asarray(values, dtype=float)
    n = len(v)
    if n == 0:
        return np.zeros(0, dtype=int)
    tb = np.arange(n) if tiebreak is None else np.asarray(tiebreak)
    order = np.lexsort((np.arange(n), tb, v))
    ranks = np.empty(n, dtype=int)
    ranks[order] = np.arange(n)
    return np.minimum(ranks * k // n, k - 1).astype(int)


def assign_cells(df: pd.DataFrame, cluster: str, covs: list) -> np.ndarray:
    """Cell id per row: the product of per-cluster rank bins of each covariate
    [(col, k), ...]."""
    cell = np.zeros(len(df), dtype=int)
    if len(df) == 0:
        return cell
    sym = df["sym"].to_numpy() if "sym" in df.columns else None
    for _key, idx in df.groupby(cluster, sort=True).indices.items():
        c = np.zeros(len(idx), dtype=int)
        for col, k in covs:
            tb = sym[idx] if sym is not None else None
            c = c * k + quantile_bins(df[col].to_numpy()[idx], k, tb)
        cell[idx] = c
    return cell


def cell_contrast(cluster_codes, cell_codes, labels, y, n_clusters: int):
    """Per cluster (num, w): num = Σ_cells n_R (mean Y_R - mean Y_C), w = Σ n_R,
    over cells holding BOTH groups (a cell with no control — or no R — drops)."""
    cl = np.asarray(cluster_codes, dtype=np.int64)
    ce = np.asarray(cell_codes, dtype=np.int64)
    lab = np.asarray(labels, dtype=float)
    yy = np.asarray(y, dtype=float)
    if len(cl) == 0:
        return np.zeros(n_clusters), np.zeros(n_clusters)
    g_codes, g = np.unique(cl * (int(ce.max()) + 1) + ce, return_inverse=True)
    ng = len(g_codes)
    g_cluster = np.zeros(ng, dtype=np.int64)
    g_cluster[g] = cl
    cnt = np.bincount(g, minlength=ng).astype(float)
    n1 = np.bincount(g, weights=lab, minlength=ng)
    s_all = np.bincount(g, weights=yy, minlength=ng)
    s1 = np.bincount(g, weights=lab * yy, minlength=ng)
    n0 = cnt - n1
    ok = (n1 > 0) & (n0 > 0)
    num_g = np.zeros(ng)
    num_g[ok] = n1[ok] * (s1[ok] / n1[ok] - (s_all[ok] - s1[ok]) / n0[ok])
    w_g = np.where(ok, n1, 0.0)
    num = np.bincount(g_cluster, weights=num_g, minlength=n_clusters)
    w = np.bincount(g_cluster, weights=w_g, minlength=n_clusters)
    return num, w


def pooled(num, w) -> Optional[float]:
    sw = float(np.sum(w))
    return float(np.sum(num) / sw) if sw > 0 else None


def boot_draws(series: list, draws: int, seed: int) -> list:
    """Bootstrap over clusters: ONE index matrix shared by every (num, w)
    series, so contrasts between series use the same resampled dates."""
    if not series:
        return []
    n = len(series[0][0])
    if n == 0:
        return [np.full(draws, np.nan) for _ in series]
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(draws, n))
    out = []
    for num, w in series:
        num, w = np.asarray(num, dtype=float), np.asarray(w, dtype=float)
        sw = w[idx].sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            out.append(np.where(sw > 0, num[idx].sum(axis=1) / np.where(sw > 0, sw, 1), np.nan))
    return out


def ci_of(draws_arr, dp: int = 2) -> Optional[list]:
    a = np.asarray(draws_arr, dtype=float)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return None
    lo, hi = np.percentile(a, [(100 - CI_PCT) / 2, 100 - (100 - CI_PCT) / 2])
    return [_r(lo, dp), _r(hi, dp)]


def verdict(n_clusters: int, ci) -> str:
    if int(n_clusters or 0) < MIN_BUCKET_N or not ci or ci[0] is None or ci[1] is None:
        return "too_small"
    if ci[0] > 0:
        return "separates"
    if ci[1] < 0:
        return "inverted"
    return "no_signal"


def specific_word(v: str, lift_ci) -> str:
    """`v` = the PRIMARY verdict (read on the event-specific CI); `lift_ci` = the
    stratified lift's CI. event_specific iff the primary separates; general when
    the stratified lift alone clears zero (the same names also hold more on
    ordinary days — a trait); else unclear."""
    if v == "too_small":
        return "unclear"
    if v == "separates":
        return "event_specific"
    if lift_ci and lift_ci[0] is not None and lift_ci[0] > 0:
        return "general"
    return "unclear"


def _r(x, dp: int = 2) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return float(round(v, dp)) if math.isfinite(v) else None


# ---------------------------------------------------------------------------
# Q1 / Q2 — the walk-forward label rows
# ---------------------------------------------------------------------------
def tier_rows(tier_sessions: dict, *, days: list, event_isos: set, closes_by_sym: dict,
              bench_closes: dict, rets_by_sym: dict, bench_rets: dict, tier: int,
              window_fn=None) -> pd.DataFrame:
    """One row per (test event E, rated name with a read on E and σ, β):
    E, sym, R (1/0), sigma, beta, y (held on E), y_p (held on the placebo
    session, or NaN), ret (event-day %)."""
    wf = window_fn or label_window
    pos = {d: i for i, d in enumerate(days)}
    rows = []
    for e in outcome_events(tier_sessions, days):
        i = pos.get(e)
        if i is None:
            continue
        win = wf(tier_sessions, e)
        check_no_leak(e, win)
        p = placebo_session(days, e, event_isos)
        p_prev = days[pos[p] - 1] if p is not None else None
        sig_days = days[max(0, i - RT.VOL_AVG_BARS - 1):i]
        beta_days = days[max(0, i - RT.BETA_BARS - 1):i]
        for sym, closes in closes_by_sym.items():
            rets = rets_by_sym.get(sym) or {}
            y = RT.held(rets.get(e))
            if y is None:
                continue
            lab = RT.box_pass(RT.tier_stats(rets, win, bench_rets, tier=tier))
            if lab is None:
                continue
            sg = RT.sigma_pct(closes, sig_days)
            if sg is None:
                continue
            b = RT.beta(closes, bench_closes, beta_days)
            if b is None:
                continue
            yp = (RT.held(RT.pct_ret(closes.get(p), closes.get(p_prev)))
                  if p is not None else None)
            rows.append((e, sym, int(lab), float(sg), float(b), int(y),
                         np.nan if yp is None else float(yp), float(rets[e])))
    return pd.DataFrame(rows, columns=["E", "sym", "R", "sigma", "beta", "y", "y_p", "ret"])


def _codes(series) -> tuple:
    cats = sorted(set(series))
    m = {c: i for i, c in enumerate(cats)}
    return np.array([m[c] for c in series], dtype=np.int64), cats


def analyse_tier(df: pd.DataFrame, *, draws: int, seed: int) -> dict:
    blank = {"verdict": "too_small", "specific": "unclear", "lift_pp": None, "ci": None,
             "raw_lift_pp": None, "raw_ci": None, "placebo_lift_pp": None, "placebo_ci": None,
             "specific_pp": None, "specific_ci": None, "ret_diff_pp": None, "ret_ci": None,
             "n_events": 0, "n_label_rows": 0 if df is None else int(len(df)), "n_r_rows": 0,
             "low_sigma_share_pct": None, "halves": None}
    if df is None or len(df) == 0:
        return blank
    df = df.reset_index(drop=True)
    cell = assign_cells(df, "E", [("sigma", SIGMA_BINS), ("beta", BETA_BINS)])
    q_sig = cell // BETA_BINS
    cl, cats = _codes(df["E"].tolist())
    nc = len(cats)
    lab = df["R"].to_numpy(dtype=float)
    y = df["y"].to_numpy(dtype=float) * 100.0
    num, w = cell_contrast(cl, cell, lab, y, nc)
    num_raw, w_raw = cell_contrast(cl, np.zeros(len(df), dtype=int), lab, y, nc)
    num_ret, w_ret = cell_contrast(cl, cell, lab, df["ret"].to_numpy(dtype=float), nc)
    pm = np.isfinite(df["y_p"].to_numpy(dtype=float))
    num_p, w_p = cell_contrast(cl[pm], cell[pm], lab[pm],
                               df["y_p"].to_numpy(dtype=float)[pm] * 100.0, nc)
    valid = w > 0
    n_events = int(valid.sum())
    out = dict(blank)
    out["n_events"] = n_events
    out["n_r_rows"] = int(lab.sum())
    r_mask = lab == 1
    out["low_sigma_share_pct"] = (_r(float((q_sig[r_mask] == 0).mean()) * 100.0)
                                  if r_mask.any() else None)
    if n_events == 0:
        return out
    # every series is read over the SAME clusters: the events with a stratified contrast
    num, w, num_p, w_p = num[valid], w[valid], num_p[valid], w_p[valid]
    num_raw, w_raw, num_ret, w_ret = num_raw[valid], w_raw[valid], num_ret[valid], w_ret[valid]
    vcats = [c for c, ok in zip(cats, valid) if ok]
    b_main, b_p, b_raw, b_ret = boot_draws([(num, w), (num_p, w_p), (num_raw, w_raw),
                                            (num_ret, w_ret)], draws, seed)
    lift, pl = pooled(num, w), pooled(num_p, w_p)
    out.update(lift_pp=_r(lift), ci=ci_of(b_main),
               raw_lift_pp=_r(pooled(num_raw, w_raw)), raw_ci=ci_of(b_raw),
               placebo_lift_pp=_r(pl), placebo_ci=ci_of(b_p),
               specific_pp=_r(lift - pl) if lift is not None and pl is not None else None,
               specific_ci=ci_of(b_main - b_p),
               ret_diff_pp=_r(pooled(num_ret, w_ret)), ret_ci=ci_of(b_ret))
    # PRIMARY (pre-registered, fix round 2026-09-30): the event-specific
    # contrast — σ x β strata alone leave the low-volatility confound in.
    out["verdict"] = verdict(n_events, out["specific_ci"])
    out["specific"] = specific_word(out["verdict"], out["ci"])
    # first half vs second half of the valid events (date order)
    half = n_events // 2
    halves = {}
    for name, part in (("first", np.arange(0, half)), ("second", np.arange(half, n_events))):
        if len(part) == 0:
            halves[name] = {"from": None, "to": None, "n_events": 0, "lift_pp": None,
                            "ci": None}
            continue
        (bd,) = boot_draws([(num[part], w[part])], draws, seed)
        halves[name] = {"from": vcats[int(part[0])], "to": vcats[int(part[-1])],
                        "n_events": int(len(part)),
                        "lift_pp": _r(pooled(num[part], w[part])), "ci": ci_of(bd)}
    out["halves"] = halves
    return out


# ---------------------------------------------------------------------------
# Q3 — EOD tape vs volume-unconfirmed twins
# ---------------------------------------------------------------------------
def eod_rows(arrs_by_sym: dict, days: list) -> pd.DataFrame:
    """One row per (d, name) in the up-close + upper-half cohort with >= 51
    prior bars and a next session: d, sym, R (the accumulation day), sigma
    (50 returns before d), y (next close->close %), y_oc (next open->close %),
    avg (the 50-session volume average before d)."""
    rows = []
    nb = RT.VOL_AVG_BARS
    for sym, a in arrs_by_sym.items():
        c, o, h, lo, v = a["close"], a["open"], a["high"], a["low"], a["volume"]
        n = len(c)
        if n < EOD_MIN_PRIOR_BARS + 2:
            continue
        rets = np.array([np.nan] + [
            np.nan if (x := RT.pct_ret(c[i], c[i - 1])) is None else x for i in range(1, n)])
        vol_prev = pd.Series(v).shift(1)
        avg = vol_prev.rolling(nb, min_periods=nb).mean().to_numpy()
        sig = pd.Series(rets).shift(1).rolling(nb, min_periods=nb).std(ddof=1).to_numpy()
        for i in range(EOD_MIN_PRIOR_BARS, n - 1):
            ci_, p, hi, l_ = c[i], c[i - 1], h[i], lo[i]
            if not (np.isfinite(ci_) and np.isfinite(p) and np.isfinite(hi) and np.isfinite(l_)):
                continue
            if hi <= l_ or not (ci_ > p) or (ci_ - l_) / (hi - l_) < 0.5:
                continue
            if not (np.isfinite(v[i]) and np.isfinite(avg[i]) and avg[i] > 0
                    and np.isfinite(sig[i])):
                continue
            y = RT.pct_ret(c[i + 1], ci_)
            if y is None:
                continue
            y_oc = RT.pct_ret(c[i + 1], o[i + 1])
            lab = V.accumulation_day(float(ci_), float(p), float(hi), float(l_),
                                     float(v[i]), float(avg[i]))
            rows.append((days[i], sym, int(lab), float(round(sig[i], 2)), float(y),
                         np.nan if y_oc is None else float(y_oc), float(avg[i])))
    return pd.DataFrame(rows, columns=["d", "sym", "R", "sigma", "y", "y_oc", "avg"])


def shuffle_lifts(cl, cell, lab, y, nc: int, draws: int, seed: int) -> np.ndarray:
    """Pooled lift with R shuffled WITHIN each (cluster, cell) block."""
    rng = np.random.default_rng(seed)
    g = np.asarray(cl, dtype=np.int64) * (int(np.max(cell)) + 1 if len(cell) else 1) + cell
    by_g = np.argsort(g, kind="stable")
    out = np.empty(draws)
    for k in range(draws):
        perm = np.lexsort((rng.random(len(g)), g))
        nl = np.empty_like(lab)
        nl[by_g] = lab[perm]
        num, w = cell_contrast(cl, cell, nl, y, nc)
        p = pooled(num, w)
        out[k] = np.nan if p is None else p
    return out


def analyse_eod(df: pd.DataFrame, *, draws: int, seed: int,
                shuffle_draws: int = SHUFFLE_DRAWS) -> dict:
    out = {"verdict": "too_small", "lift_pp": None, "ci": None, "placebo_pct": None,
           "placebo_mean_pp": None, "placebo_band": None, "oc_lift_pp": None, "oc_ci": None,
           "n_days": 0, "n_rows": 0 if df is None else int(len(df)), "n_r_rows": 0,
           "mean_next_pct": None, "share_up_pct": None,
           "control_mean_next_pct": None, "control_share_up_pct": None,
           "stop_out": "no stop exists in this read — no stop-out rate"}
    if df is None or len(df) == 0:
        return out
    df = df.reset_index(drop=True)
    cell = assign_cells(df, "d", [("sigma", SIGMA_BINS)])
    cl, cats = _codes(df["d"].tolist())
    nc = len(cats)
    lab = df["R"].to_numpy(dtype=float)
    y = df["y"].to_numpy(dtype=float)
    num, w = cell_contrast(cl, cell, lab, y, nc)
    om = np.isfinite(df["y_oc"].to_numpy(dtype=float))
    num_oc, w_oc = cell_contrast(cl[om], cell[om], lab[om],
                                 df["y_oc"].to_numpy(dtype=float)[om], nc)
    n_days = int((w > 0).sum())
    r, c_ = lab == 1, lab == 0
    out.update(n_days=n_days, n_r_rows=int(r.sum()),
               mean_next_pct=_r(y[r].mean()) if r.any() else None,
               share_up_pct=_r((y[r] > 0).mean() * 100.0) if r.any() else None,
               control_mean_next_pct=_r(y[c_].mean()) if c_.any() else None,
               control_share_up_pct=_r((y[c_] > 0).mean() * 100.0) if c_.any() else None)
    if n_days == 0:
        return out
    valid = w > 0
    b_main, b_oc = boot_draws([(num[valid], w[valid]), (num_oc[valid], w_oc[valid])],
                              draws, seed)
    lift = pooled(num[valid], w[valid])
    out.update(lift_pp=_r(lift, 3), ci=ci_of(b_main, 3),
               oc_lift_pp=_r(pooled(num_oc[valid], w_oc[valid]), 3), oc_ci=ci_of(b_oc, 3))
    sh = shuffle_lifts(cl, cell, lab, y, nc, shuffle_draws, seed)
    sh = sh[np.isfinite(sh)]
    if sh.size and lift is not None:
        out["placebo_pct"] = _r(float((sh >= lift).mean()) * 100.0)
        out["placebo_mean_pp"] = _r(sh.mean(), 3)
        out["placebo_band"] = ci_of(sh, 3)
    out["verdict"] = verdict(n_days, out["ci"])
    return out


# ---------------------------------------------------------------------------
# the whole study (pure given frames + events)
# ---------------------------------------------------------------------------
def definitions(draws: int, seed: int) -> dict:
    return {"HOLD_MAX_DROP_PCT": float(RT.HOLD_MAX_DROP_PCT),
            "HOLD_WINDOW_DAYS": int(RT.HOLD_WINDOW_DAYS),
            "HOLD_RATE_MIN_PCT": float(RT.HOLD_RATE_MIN_PCT),
            "T2_EXCLUDES_T1_DAYS": bool(RT.T2_EXCLUDES_T1_DAYS),
            "VOL_AVG_BARS": int(RT.VOL_AVG_BARS), "BETA_BARS": int(RT.BETA_BARS),
            "BENCH": BENCH, "PCT_DP": int(RT.PCT_DP), "MIN_BUCKET_N": int(MIN_BUCKET_N),
            "SIGMA_BINS": SIGMA_BINS, "BETA_BINS": BETA_BINS,
            "EOD_MIN_PRIOR_BARS": EOD_MIN_PRIOR_BARS, "CI_PCT": CI_PCT,
            "draws": int(draws), "seed": int(seed), "shuffle_draws": SHUFFLE_DRAWS,
            "refuse_window_et": f"{REFUSE_FROM[0]:02d}:{REFUSE_FROM[1]:02d}–"
                                f"{REFUSE_TO[0]:02d}:{REFUSE_TO[1]:02d}",
            "universe": UNIVERSE_KEY}


def run_study(frames: dict, events: list, *, as_of: str, draws: int = DRAWS_DEFAULT,
              seed: int = SEED_DEFAULT, shuffle_draws: int = SHUFFLE_DRAWS) -> dict:
    """The artifact body (everything but the provenance keys main() adds)."""
    bdf = frames.get(BENCH)
    if bdf is None or len(bdf) == 0:
        raise ValueError(f"no {BENCH} bars — the event sessions cannot be dated")
    bench_closes = _closes_upto(bdf, as_of)
    days = sorted(bench_closes)
    if len(days) < 2:
        raise ValueError(f"{BENCH} has fewer than two closed bars up to {as_of}")
    sessions = RT.event_sessions(events, days, start=date.fromisoformat(days[0]),
                                 end=date.fromisoformat(as_of) + timedelta(days=1))
    event_isos = set(sessions["t1"]) | set(sessions["t2"])
    all_sess = {**sessions["t2"], **sessions["t1"]}
    bench_rets = RT.event_returns(bench_closes, days, all_sess)

    closes_by_sym, rets_by_sym, arrs = {}, {}, {}
    for sym, fr in frames.items():
        if sym == BENCH or fr is None or len(fr) == 0:
            continue
        cl = _closes_upto(fr, as_of)
        if not cl:
            continue
        closes_by_sym[sym] = cl
        rets_by_sym[sym] = RT.event_returns(cl, days, all_sess)
        arrs[sym] = aligned(fr, days)

    out = {}
    for key, tier in (("t1", 1), ("t2", 2)):
        df = tier_rows(sessions[key], days=days, event_isos=event_isos,
                       closes_by_sym=closes_by_sym, bench_closes=bench_closes,
                       rets_by_sym=rets_by_sym, bench_rets=bench_rets, tier=tier)
        blk = analyse_tier(df, draws=draws, seed=seed)
        blk["test_events"] = len(outcome_events(sessions[key], days))
        blk["sessions"] = len(sessions[key])
        out[key] = blk
    out["eod"] = analyse_eod(eod_rows(arrs, days), draws=draws, seed=seed,
                             shuffle_draws=shuffle_draws)
    out["pre"] = dict(Q4_BLOCK)
    out["n_names_with_bars"] = len(closes_by_sym)
    out["first_bar"] = days[0]
    out["last_bar"] = days[-1]
    return out


def measured_literal(art: dict) -> dict:
    """The `chart_maps.resiliency_measured.MEASURED` literal for an artifact."""
    def pick(blk, keys):
        blk = blk if isinstance(blk, dict) else {}
        return {k: blk.get(k) for k in keys}
    tier_keys = ("verdict", "specific", "lift_pp", "ci", "placebo_lift_pp", "placebo_ci",
                 "specific_pp", "specific_ci", "n_events")
    return {"status": "measured", "script": SCRIPT, "artifact": ARTIFACT,
            "run_date": art.get("run_date"), "as_of": art.get("as_of"),
            "prereg_commit": art.get("prereg_commit"),
            "t1": pick(art.get("t1"), tier_keys), "t2": pick(art.get("t2"), tier_keys),
            "eod": pick(art.get("eod"), ("verdict", "lift_pp", "ci", "placebo_pct", "n_days")),
            "pre": pick(art.get("pre"), ("verdict", "reason"))}


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------
def block_writes() -> None:
    """Every pymongo write method -> a recorded no-op (this process only). A
    raise would make `prices._get_mongo` disable the cache, so it never raises."""
    from pymongo.collection import Collection

    def _make(name):
        def _noop(self, *a, **k):
            ATTEMPTED.append(f"{getattr(self, 'name', '?')}.{name}")
            return "blocked_index" if name == "create_index" else None
        return _noop
    for m in WRITE_METHODS:
        if hasattr(Collection, m):
            setattr(Collection, m, _make(m))


def _load_events_json(path: str) -> list:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("events_used", data)
        if isinstance(data, dict):
            data = data.get("events", [])
    return [e for e in (data or []) if isinstance(e, dict)]


def _default_universe() -> list:
    return list(DR._resolve_universe(UNIVERSE_KEY)[0] or [])


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Resiliency persistence study (read-only).")
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD (default: last closed session)")
    ap.add_argument("--draws", type=int, default=DRAWS_DEFAULT)
    ap.add_argument("--seed", type=int, default=SEED_DEFAULT)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent
                                         / "resiliency_measured.json"))
    ap.add_argument("--events-json", default=None, help="replay a saved event list")
    ap.add_argument("--prereg-commit", default=None,
                    help="the commit hash of the prereg (required for an outcome run)")
    ap.add_argument("--force-window", action="store_true",
                    help="run inside 09:00–16:30 ET anyway")
    ap.add_argument("--limit", type=int, default=None,
                    help="SMOKE: first N names only — NOT QUOTABLE, never the default --out")
    return ap.parse_args(argv)


def main(argv=None, *, now: Optional[datetime] = None, universe_fn=None, frames_fn=None,
         events_fn=None, block=True) -> int:
    a = parse_args(argv)
    now_et = (now or datetime.now(tz=ET)).astimezone(ET)
    if refused_window(now_et) and not a.force_window:
        print(f"REFUSED: {now_et:%H:%M} ET is inside {REFUSE_FROM[0]:02d}:{REFUSE_FROM[1]:02d}–"
              f"{REFUSE_TO[0]:02d}:{REFUSE_TO[1]:02d} ET; pass --force-window to override.",
              file=sys.stderr)
        return 2
    smoke = a.limit is not None
    default_out = str(Path(__file__).resolve().parent / "resiliency_measured.json")
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
    syms = [str(s).upper() for s in (universe_fn or _default_universe)()]
    if smoke:
        syms = syms[:max(0, int(a.limit))]
    universe_n = len(syms)
    frames = (frames_fn or prices.bulk_cached_frames)(syms + [BENCH])
    if not frames or frames.get(BENCH) is None:
        print(f"REFUSED: the price cache returned no {BENCH} frame.", file=sys.stderr)
        return 2
    bench_days = sorted(RT.closes_by_day(frames[BENCH]))
    as_of = a.as_of or default_as_of(bench_days, now_et)
    if not as_of:
        print("REFUSED: no closed session to measure up to.", file=sys.stderr)
        return 2
    if a.events_json:
        events, errors, source = _load_events_json(a.events_json), [], a.events_json
    else:
        past = (events_fn or macro_calendar.past_events)(
            date.fromisoformat(bench_days[0]), date.fromisoformat(as_of))
        if not isinstance(past, dict) or not past.get("available"):
            print("REFUSED: the FRED event history is unavailable.", file=sys.stderr)
            return 2
        events = [e for e in (past.get("events") or []) if isinstance(e, dict)]
        errors = list(past.get("errors") or [])
        source = "macro_calendar.past_events"
    body = run_study(frames, events, as_of=as_of, draws=a.draws, seed=a.seed)
    art = {"study": STUDY, "script": SCRIPT, "prereg": PREREG,
           "prereg_commit": (a.prereg_commit or None), "smoke": bool(smoke),
           "run_date": now_et.date().isoformat(), "as_of": as_of, "universe_n": universe_n,
           "events_used": {"source": source, "errors": errors, "events": events},
           "definitions": definitions(a.draws, a.seed), **body,
           "limits": list(LIMITS), "runtime_sec": round(time.time() - t0, 1),
           "attempted_writes": sorted(set(ATTEMPTED))}
    Path(a.out).write_text(json.dumps(art, indent=1, allow_nan=False, default=str) + "\n",
                           encoding="utf-8")
    for k in ("t1", "t2"):
        b = art[k]
        print(f"{k}: {b['verdict']} ({b['specific']}) lift {b['lift_pp']}pp CI {b['ci']} · "
              f"placebo {b['placebo_lift_pp']}pp CI {b['placebo_ci']} · specific "
              f"{b['specific_pp']}pp CI {b['specific_ci']} · n_events {b['n_events']} · "
              f"rows {b['n_label_rows']}")
    e = art["eod"]
    print(f"eod: {e['verdict']} lift {e['lift_pp']}pp CI {e['ci']} · placebo_pct "
          f"{e['placebo_pct']} · n_days {e['n_days']} · rows {e['n_rows']}")
    print(f"names {art['n_names_with_bars']} of {universe_n} · as_of {as_of} · "
          f"attempted writes {art['attempted_writes']} · {art['runtime_sec']}s -> {a.out}")
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
