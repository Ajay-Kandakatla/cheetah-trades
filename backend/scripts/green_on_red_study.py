"""Green on a red day — the STUDY (pre-registered 2026-09-28, rev 1; nothing is wired).

THE ASK, verbatim (Ajay, Mon 2026-09-28, after the close):
  "I have a theory, Stocks that are green in this bearish day are lilly to be
   in high demand what are those? I saw Voyager is one of the,"

The "what are those?" half is the main session's 56-name list (VOYG in it).
This script answers the "theory" half only. It is a Rule #10 research step: no
surface, lane, gate, alert, sort, chip or rule line changes because of it.

PRE-REGISTRATION (rev 1, frozen before the full run; the spec is
docs/research/green_on_red_2026_09_28_prereg.md, sections 3.2-3.15):
  * Red day: RSP close-to-close <= RED_RSP_PCT AND <= RED_BREADTH_MAX of the
    study's own names closed up, with >= MIN_BREADTH_NAMES valid names.
  * Signal S2 (the list he saw): up on the day, close >= PRICE_FLOOR,
    close*volume >= DVOL_MIN, RVOL >= RVOL_MIN (day t never in the
    denominator), close in the upper half of the day's range.
  * Twin: one same-day, strictly red-closing, liquid name, nearest neighbour
    on pre-signal features at t-1 (r21, r63, off52, ldv20, vol20, beta63),
    exact on above50, per-covariate caliper CALIPER_SD pooled SDs, without
    replacement, deterministic.
  * PRIMARY: bought at the NEXT SESSION'S OPEN, held H_PRIMARY sessions,
    excess over RSP; lift = mean signal excess minus mean twin excess over
    complete pairs. CI = widest of three paired cluster bootstraps (red day,
    fixed t//h blocks, fixed t//BLOCK_SESSIONS blocks); NULL below
    MIN_CLUSTERS clusters or MIN_BOOT_REPS usable draws in ANY grouping.
  * Verdict: `verdict()` below, mechanical and symmetric (3.12).

READ-ONLY: frames come from `sepa.prices.bulk_cached_frames` (one find, never
a network call), capped at one AS_OF day for every name; bar digests are
compared at the end so a cache refresh that moves a used name's bars marks
the run invalid (exit 4). Nothing here writes to any database. The script
refuses to run Mon-Fri 09:00-17:30 ET (exit 5) unless --force-window.

RUN (after 17:30 ET or before 09:00 ET; never RTH):
  docker cp backend/scripts/green_on_red_study.py cheetah-market-app-api-1:/tmp/green_on_red_study.py
  docker cp <scratchpad>/gor_dem_2026_09_28.json cheetah-market-app-api-1:/tmp/gor_dem_2026_09_28.json
  docker exec -d -w /app -e PYTHONPATH=/app cheetah-market-app-api-1 sh -c 'mkdir -p /tmp/gor_out &&
    python -u /tmp/green_on_red_study.py --stage all --out /tmp/gor_out --git-head SHA
    --expect /tmp/gor_dem_2026_09_28.json > /tmp/gor_out.log 2>&1'
  docker cp cheetah-market-app-api-1:/tmp/gor_out/green_on_red_measured.json backend/scripts/green_on_red_measured.json
  Smoke: --stage match (no outcome is computed; NOT quotable).

RESULTS: NOT RUN at the pre-registration. The measured numbers live only in
backend/scripts/green_on_red_measured.json and docs/research/green_on_red_2026_09_28.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import resource
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from rotation import tracker as RT
from scripts import explosive_study as ES
from scripts import promo_tag_study as PT
from scripts import turning_bullish_amd_study as AS
from sepa import breakout_audit as BA
from sepa import prices as PR
from sepa import universe as U
from supply_demand import demand_reentry as DR
from supply_demand import momentum_burst as MB
from supply_demand import stock_supply_demand as SSD
from trading import safety_floor as SF

ET = ZoneInfo("America/New_York")

# ── constants reused BY NAME (never retyped; test 17 pins identity) ─────────
BENCH = RT.BENCHMARK                       # "RSP"
R_SHORT = RT.WINDOW_SHORT                  # 21
R_MED = RT.WINDOW_MED                      # 63
VOL_BARS = BA.VOL_AVG_BARS                 # 50 (prior-only denominator)
RVOL_MIN = MB.BURST_RVOL_MIN               # 1.5 (inclusive)
PRICE_FLOOR = SF.MIN_SHARE_PRICE           # 2.00
DVOL_APP = SF.MIN_DOLLAR_VOL               # 20M (secondary S8 only)
HIGH_BARS = SSD.LOOKBACK_DAYS              # 252
LEADER_NEAR_HIGH_PCT = SSD.NEAR_HIGH_PCT   # 15.0
HORIZONS = AS.HORIZONS                     # (5, 10, 21)
MIN_CLUSTERS = PT.MIN_CLUSTERS             # 20

# ── study design (rev 1, frozen) ─────────────────────────────────────────────
STUDY = "green_on_red_study_2026_09_28"    # STUDY DESIGN
PREREG_REV = 1                             # STUDY DESIGN
UNIVERSE_MODE = "full"                     # STUDY DESIGN
RED_RSP_PCT = -0.5                         # STUDY DESIGN: RSP %, rounded to 4 dp, inclusive <=
RED_BREADTH_MAX = 0.35                     # STUDY DESIGN: share of valid names up, inclusive <=
MIN_BREADTH_NAMES = 1000                   # STUDY DESIGN: fewer valid names -> UNCLASSIFIED
SPY_SYMBOL = "SPY"                         # STUDY DESIGN
SPY_RED_PCT = -0.5                         # STUDY DESIGN: sensitivity definition (S6)
DVOL_MIN = 10_000_000.0                    # STUDY DESIGN: the list he saw
CR_MIN = 0.5                               # STUDY DESIGN: (C-L)/(H-L) >= 0.5; H == L -> not S2
MA50_BARS = 50                             # STUDY DESIGN: sepa/trend_template.py:40 literal
FIRST_T = R_MED + 1                        # STUDY DESIGN: 64
HIGH_MIN_BARS = R_MED                      # STUDY DESIGN: off52 lookback floor
H_PRIMARY = 10                             # STUDY DESIGN
PRIMARY_ENTRY = "O"                        # STUDY DESIGN: the next session's open
CHECK_ENTRY = "C"                          # STUDY DESIGN: signal-day close, criterion (e)
ENTRIES = ("O", "C")                       # STUDY DESIGN
EVENT_POP_PCT = 20.0                       # STUDY DESIGN: S5
MATCH_VARS = ("r21", "r63", "off52", "ldv20", "vol20", "beta63")   # STUDY DESIGN
MATCH_VARS_REV0 = ("r21", "r63", "off52", "ldv20", "vol20")        # STUDY DESIGN: S9 only
EXACT_VARS = ("above50",)                  # STUDY DESIGN
CALIPER_SD = 0.6                           # STUDY DESIGN
CALIPER_SD_HOUSE = 0.4                     # STUDY DESIGN: stability run (f2)
BALANCE_SMD_MAX = 0.1                      # STUDY DESIGN
MIN_MATCHED_SHARE = 0.80                   # STUDY DESIGN: HIS CALL 7-8
MIN_BOOT_REPS = 100                        # STUDY DESIGN: explosive_study.py:904 / promo_tag_study.py:536 literal
BOOT_B = 2000                              # STUDY DESIGN
BOOT_SEED = 7                              # STUDY DESIGN
MDL_Z = 2.8                                # STUDY DESIGN
BLOCK_SESSIONS = R_SHORT                   # STUDY DESIGN: 21-session fixed blocks
BETA_MIN_PAIRS = 60                        # STUDY DESIGN
BIG_MOVE_PCT = 40.0                        # STUDY DESIGN: data audit only
NEAR_FLOOR_BAND = 2.0                      # STUDY DESIGN: audit only (L9)
PIT_CHECK_NAMES = 50                       # STUDY DESIGN
PIT_SEED = 20260928                        # STUDY DESIGN
ENDED_GRACE_DAYS = 7                       # STUDY DESIGN: cache check only
REFUSE_WINDOW_ET = ("09:00", "17:30")      # STUDY DESIGN: Mon-Fri; exit 5 unless --force-window
REPRO_DAY = "2026-09-28"                   # STUDY DESIGN
ANECDOTE_SYMBOL = "VOYG"                   # STUDY DESIGN

VERDICT_RULE_TEXT = """invalid_snapshot        if not res.snapshot.ok
invalid_pit             if res.pit.mismatch > 0
no_signal [imbalanced]  if not res.balance.primary.balanced
                        (gated on the H_PRIMARY-eligible pairs; stats stops BEFORE any outcome is computed)

Gates common to both directions:
  (g) matched_share >= MIN_MATCHED_SHARE                 (H_PRIMARY-eligible subset)
  (k) primary ci is not null                             (every grouping has >= MIN_CLUSTERS clusters
                                                          and >= MIN_BOOT_REPS usable draws)
Primary = S2 red vs twins, h = H_PRIMARY, entry PRIMARY_ENTRY (next open).

signal    iff (g) and (k) and ALL of:
  (a)   primary ci.lo > 0
  (b)   primary sig_ci.lo > 0                            (the signal arm itself beats RSP)
  (c)   lift_H1 > 0 and lift_H2 > 0
  (c2)  min drop-one-block lift > 0
  (d)   one-per-symbol lift > 0
  (e)   entry-C h10 lift > 0
  (f)   cache-universe lift > 0 and that re-match balanced
  (f2)  CALIPER_SD_HOUSE lift > 0 and that re-match balanced

inverted  iff (g) and (k) and ALL of the mirrors:
  (a-)  primary ci.hi < 0
  (c-)  lift_H1 < 0 and lift_H2 < 0
  (c2-) max drop-one-block lift < 0
  (d-)  one-per-symbol lift < 0
  (e-)  entry-C h10 lift < 0
  (f-)  cache-universe lift < 0 and that re-match balanced
  (f2-) CALIPER_SD_HOUSE lift < 0 and that re-match balanced
  ((b) has no mirror: INVERTED is a claim about the twin comparison; the arm-vs-RSP CI is reported.)

else no_signal, tags (additive):
  relative_only    (a and not b)
  absolute_only    (b and not a)
  fragile          (a and b and any of c, c2, d, e, f, f2 fails)
  inverted_fragile (a- and any of c-, c2-, d-, e-, f-, f2- fails)
  undermatched     (not g)
  few_clusters     (not k)

status signal or inverted also gets:
  not_red_specific unless S3 (red lift minus non-red lift, entry O, h10) points the same way:
  signal needs S3 ci.lo > 0; inverted needs S3 ci.hi < 0.
  A null S3 CI or an imbalanced S3 re-match sets the tag."""   # STUDY DESIGN (3.12 verbatim)

TAG_TEXT = {                                                    # STUDY DESIGN (3.13 verbatim)
    "relative_only": "beats the twins, not RSP",
    "absolute_only": "beats RSP, not the twins",
    "fragile": "fails a stability check",
    "inverted_fragile": "the shortfall fails a stability check",
    "undermatched": "too few signals found a twin",
    "few_clusters": "too few independent periods for an interval",
    "not_red_specific": "not specific to red days",
    "imbalanced": "the twins did not match the signals",
}

assert H_PRIMARY in HORIZONS


# ═════════════════════════════════════════════════════════════════════════════
# FRAMES (read-only)
# ═════════════════════════════════════════════════════════════════════════════
class FrameSet(dict):
    """{SYM: prepared frame}; carries the load audit (dup day keys, digests)."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.dup_day_keys = 0
        self.digests = {}


def day_keys(df) -> list:
    idx = df.index
    try:
        return list(pd.DatetimeIndex(idx).strftime("%Y-%m-%d"))
    except Exception:                                          # noqa: BLE001
        return [str(x)[:10] for x in idx]


def cap_as_of(df, as_of: str):
    """Rows whose YYYY-MM-DD is <= as_of (mixed 00:00/04:00 stamps: day keys only)."""
    if df is None or not len(df):
        return df
    keys = np.array(day_keys(df))
    return df.loc[keys <= str(as_of)[:10]]


def dedupe_day_keys(df):
    """Duplicate day keys keep the LAST row. Returns (frame, n_dropped)."""
    if df is None or not len(df):
        return df, 0
    keys = pd.Index(day_keys(df))
    dup = keys.duplicated(keep="last")
    n = int(dup.sum())
    return (df.loc[~dup] if n else df), n


def bars_digest(df) -> str:
    arr = np.ascontiguousarray(df[["open", "high", "low", "close", "volume"]].to_numpy(dtype=np.float64))
    return hashlib.sha1(arr.tobytes()).hexdigest()


def prep_frame(df, as_of: str):
    """split_today_partial -> cap_as_of -> dedupe. Returns (frame or None, n_dup)."""
    if df is None or not len(df):
        return None, 0
    df = DR.split_today_partial(df)[0]
    df = cap_as_of(df, as_of)
    df, n = dedupe_day_keys(df)
    if df is None or not len(df):
        return None, n
    return df, n


def prep_frames(raw: dict, as_of: str) -> FrameSet:
    out = FrameSet()
    for s in sorted(raw):
        df, n = prep_frame(raw[s], as_of)
        out.dup_day_keys += n
        if df is not None:
            out[s] = df
            out.digests[s] = bars_digest(df)
    return out


def load_frames(symbols, as_of: str) -> FrameSet:
    """bulk_cached_frames (ONE find, never a fetch) -> prep_frame per name."""
    return prep_frames(PR.bulk_cached_frames(list(symbols)), as_of)


def as_of_day() -> str:
    raw = PR.bulk_cached_frames([BENCH])
    b = DR.split_today_partial(raw[BENCH])[0]
    return day_keys(b)[-1]


def exclude_set() -> set:
    return set(U.fetch_etf_universe()) | set(U.RS_ANCHORS) | {BENCH}


def study_names(universe: list, exclude: set) -> list:
    return [s for s in dict.fromkeys(universe) if s not in exclude]


def is_ended(last_day: str, as_of: str) -> bool:
    last = datetime.strptime(str(last_day)[:10], "%Y-%m-%d")
    ref = datetime.strptime(str(as_of)[:10], "%Y-%m-%d")
    return last < ref - timedelta(days=ENDED_GRACE_DAYS)


def in_refusal_window(now_et: datetime) -> bool:
    if now_et.weekday() >= 5:
        return False
    hm = now_et.strftime("%H:%M")
    return REFUSE_WINDOW_ET[0] <= hm < REFUSE_WINDOW_ET[1]


# ═════════════════════════════════════════════════════════════════════════════
# PANEL
# ═════════════════════════════════════════════════════════════════════════════
@dataclass
class Panel:
    syms: list
    cal: list
    O: np.ndarray
    H: np.ndarray
    L: np.ndarray
    C: np.ndarray
    V: np.ndarray
    off_calendar_bars: int = 0


def build_panel(frames: dict, cal: list) -> Panel:
    """N x T float64 on the calendar; a missing session is NaN; never dropna."""
    syms = sorted(frames)
    pos = {d: k for k, d in enumerate(cal)}
    N, T = len(syms), len(cal)
    arr = {c: np.full((N, T), np.nan) for c in ("open", "high", "low", "close", "volume")}
    off = 0
    for i, s in enumerate(syms):
        df = frames[s]
        keys = day_keys(df)
        cols = np.array([pos.get(k, -1) for k in keys], dtype=np.int64)
        inside = cols >= 0
        off += int((~inside).sum())
        for c in arr:
            v = df[c].to_numpy(dtype=float)
            arr[c][i, cols[inside]] = v[inside]
    for c in ("open", "high", "low", "close"):
        a = arr[c]
        a[~(np.isfinite(a) & (a > 0))] = np.nan
    v = arr["volume"]
    v[~np.isfinite(v)] = np.nan
    return Panel(syms, list(cal), arr["open"], arr["high"], arr["low"], arr["close"], arr["volume"], off)


def bench_arrays(df, cal: list):
    """(open, close) of one frame aligned on cal by day key; NaN when missing."""
    if df is None or not len(df):
        return np.full(len(cal), np.nan), np.full(len(cal), np.nan)
    s = pd.DataFrame({"open": df["open"].to_numpy(dtype=float), "close": df["close"].to_numpy(dtype=float)},
                     index=day_keys(df))
    s = s[~s.index.duplicated(keep="last")].reindex(cal)
    o, c = s["open"].to_numpy(dtype=float), s["close"].to_numpy(dtype=float)
    o = np.where(np.isfinite(o) & (o > 0), o, np.nan)
    c = np.where(np.isfinite(c) & (c > 0), c, np.nan)
    return o, c


# ═════════════════════════════════════════════════════════════════════════════
# DAY CHANGE, BREADTH, RED DAYS
# ═════════════════════════════════════════════════════════════════════════════
_glitch_vec = np.frompyfunc(PR._is_scale_glitch, 2, 1)


def glitch_matrix(C: np.ndarray) -> np.ndarray:
    """True on t when C[t] vs C[t-1] (prior SESSION) is a scale glitch."""
    g = np.zeros(C.shape, dtype=bool)
    if C.shape[1] < 2:
        return g
    a, b = C[:, 1:], C[:, :-1]
    both = np.isfinite(a) & np.isfinite(b) & (a > 0) & (b > 0)
    sub = np.zeros(a.shape, dtype=bool)
    if both.any():
        sub[both] = _glitch_vec(a[both], b[both]).astype(bool)
    g[:, 1:] = sub
    return g


def day_change(P: Panel) -> np.ndarray:
    C = P.C
    chg = np.full(C.shape, np.nan)
    if C.shape[1] < 2:
        return chg
    a, b = C[:, 1:], C[:, :-1]
    both = np.isfinite(a) & np.isfinite(b) & (a > 0) & (b > 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        r = a / b - 1.0
    ok = both & ~glitch_matrix(C)[:, 1:]
    chg[:, 1:] = np.where(ok, r, np.nan)
    return chg


def breadth(chg: np.ndarray):
    fin = np.isfinite(chg)
    n_valid = fin.sum(axis=0)
    up = (np.where(fin, chg, 0.0) > 0).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        share = np.where(n_valid > 0, up / np.maximum(n_valid, 1), np.nan)
    return share, n_valid


def _pct_change_4dp(x: np.ndarray) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if len(x) < 2:
        return out
    with np.errstate(invalid="ignore", divide="ignore"):
        out[1:] = np.round(100.0 * (x[1:] / x[:-1] - 1.0), 4)
    return out


def classified_days(bench_close: np.ndarray, n_valid: np.ndarray) -> np.ndarray:
    return np.isfinite(_pct_change_4dp(bench_close)) & (n_valid >= MIN_BREADTH_NAMES)


def red_days(bench_close: np.ndarray, share: np.ndarray, n_valid: np.ndarray) -> np.ndarray:
    pct = _pct_change_4dp(bench_close)
    with np.errstate(invalid="ignore"):
        return (np.isfinite(pct) & (pct <= RED_RSP_PCT) & np.isfinite(share)
                & (share <= RED_BREADTH_MAX) & (n_valid >= MIN_BREADTH_NAMES))


def spy_red_days(spy_close: np.ndarray) -> np.ndarray:
    pct = _pct_change_4dp(spy_close)
    with np.errstate(invalid="ignore"):
        return np.isfinite(pct) & (pct <= SPY_RED_PCT)


# ═════════════════════════════════════════════════════════════════════════════
# SIGNAL SETS (bars <= t) AND MATCH FEATURES (bars <= t-1)
# ═════════════════════════════════════════════════════════════════════════════
def _roll(a: np.ndarray, w: int, how: str, minp: int = None) -> pd.DataFrame:
    df = pd.DataFrame(a.T)
    r = df.rolling(w, min_periods=w if minp is None else minp)
    return getattr(r, how)()


def rvol(P: Panel) -> np.ndarray:
    """V[t] / mean(V[t-VOL_BARS .. t-1]); all prior values finite, mean > 0; t never in the denominator."""
    den = _roll(P.V, VOL_BARS, "mean").shift(1).to_numpy().T
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(np.isfinite(den) & (den > 0) & np.isfinite(P.V), P.V / den, np.nan)
    return out


def close_pos(P: Panel) -> np.ndarray:
    rng = P.H - P.L
    with np.errstate(invalid="ignore", divide="ignore"):
        cp = (P.C - P.L) / rng
    return np.where(np.isfinite(rng) & (rng > 0) & np.isfinite(cp), cp, np.nan)


def liquid(P: Panel) -> np.ndarray:
    with np.errstate(invalid="ignore"):
        return (P.C >= PRICE_FLOOR) & (P.C * P.V >= DVOL_MIN)


def signal_sets(P: Panel, chg: np.ndarray, rv: np.ndarray, cp: np.ndarray) -> dict:
    liq = liquid(P)
    fin = np.isfinite(chg)
    with np.errstate(invalid="ignore"):
        s1 = fin & (np.where(fin, chg, 0.0) > 0) & liq
        s2 = s1 & np.isfinite(rv) & (rv >= RVOL_MIN) & np.isfinite(cp) & (cp >= CR_MIN)
        pool = fin & (np.where(fin, chg, 0.0) < 0) & liq
    return {"S1": s1, "S2": s2, "POOL": pool, "liquid": liq}


def leader_at_t(P: Panel) -> np.ndarray:
    """The list's own definition (includes t): above the 50-day SMA AND within
    LEADER_NEAR_HIGH_PCT of the max high over up to HIGH_BARS bars."""
    ma = _roll(P.C, MA50_BARS, "mean").to_numpy().T
    hi = _roll(P.H, HIGH_BARS, "max", minp=1).to_numpy().T
    with np.errstate(invalid="ignore", divide="ignore"):
        return (np.isfinite(ma) & np.isfinite(P.C) & (P.C > ma) & np.isfinite(hi)
                & (P.C / hi - 1.0 >= -LEADER_NEAR_HIGH_PCT / 100.0))


def _rolling_beta(y: np.ndarray, x: np.ndarray, w: int) -> np.ndarray:
    """OLS slope of y on x over the w bars ENDING at each index, masked pairwise;
    NaN below BETA_MIN_PAIRS finite pairs. y: N x T, x: T."""
    X = np.broadcast_to(x[None, :], y.shape)
    m = np.isfinite(y) & np.isfinite(X)
    y0 = np.where(m, y, 0.0)
    x0 = np.where(m, X, 0.0)
    n = _roll(m.astype(float), w, "sum", minp=1).to_numpy().T
    sx = _roll(x0, w, "sum", minp=1).to_numpy().T
    sy = _roll(y0, w, "sum", minp=1).to_numpy().T
    sxx = _roll(x0 * x0, w, "sum", minp=1).to_numpy().T
    sxy = _roll(x0 * y0, w, "sum", minp=1).to_numpy().T
    with np.errstate(invalid="ignore", divide="ignore"):
        den = n * sxx - sx * sx
        b = (n * sxy - sx * sy) / den
    return np.where((n >= BETA_MIN_PAIRS) & np.isfinite(b) & (den > 0), b, np.nan)


def features_prev(P: Panel, bench_close: np.ndarray, chg: np.ndarray = None) -> dict:
    """Match features for day t from bars <= t-1 only (rolling(...).shift(1))."""
    if chg is None:
        chg = day_change(P)
    dfC = pd.DataFrame(P.C.T)
    prevC = dfC.shift(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        r21 = (prevC / dfC.shift(1 + R_SHORT) - 1.0).to_numpy().T
        r63 = (prevC / dfC.shift(1 + R_MED) - 1.0).to_numpy().T
        hmax = _roll(P.H, HIGH_BARS, "max", minp=HIGH_MIN_BARS).shift(1).to_numpy().T
        off52 = prevC.to_numpy().T / hmax - 1.0
        off52_bars = _roll(np.isfinite(P.H).astype(float), HIGH_BARS, "sum", minp=1).shift(1).to_numpy().T
        ma50 = _roll(P.C, MA50_BARS, "mean").shift(1).to_numpy().T
        pc = prevC.to_numpy().T
        above50 = np.where(np.isfinite(ma50) & np.isfinite(pc), (pc > ma50).astype(float), np.nan)
        dv = P.C * P.V
        dv = np.where(np.isfinite(dv) & (dv > 0), dv, np.nan)
        ldv20 = np.log(_roll(dv, 20, "mean").shift(1).to_numpy().T)
        lr = np.log(P.C[:, 1:] / P.C[:, :-1])
        lr = np.concatenate([np.full((P.C.shape[0], 1), np.nan), lr], axis=1)
        vol20 = _roll(lr, 20, "std").shift(1).to_numpy().T
        br = np.full(len(bench_close), np.nan)
        br[1:] = bench_close[1:] / bench_close[:-1] - 1.0
    beta = _rolling_beta(chg, br, R_MED)
    beta63 = np.full(beta.shape, np.nan)
    beta63[:, 1:] = beta[:, :-1]
    off52 = np.where(np.isfinite(off52), off52, np.nan)
    return {"r21": r21, "r63": r63, "off52": off52, "off52_bars": off52_bars, "above50": above50,
            "ldv20": ldv20, "vol20": vol20, "beta63": beta63}


# ═════════════════════════════════════════════════════════════════════════════
# CONTEXT (all per-(name, day) arrays of one panel)
# ═════════════════════════════════════════════════════════════════════════════
def compute_ctx(P: Panel, B_O, B_C, S_C=None, red_frozen=None, nonred_frozen=None) -> dict:
    chg = day_change(P)
    share, n_valid = breadth(chg)
    if red_frozen is None:
        red = red_days(B_C, share, n_valid)
        cls = classified_days(B_C, n_valid)
        nonred = cls & ~red
    else:
        red, nonred = red_frozen.copy(), nonred_frozen.copy()
        cls = red | nonred
    rv = rvol(P)
    cp = close_pos(P)
    sets = signal_sets(P, chg, rv, cp)
    feats = features_prev(P, B_C, chg)
    return {"P": P, "B_O": B_O, "B_C": B_C, "T": len(P.cal), "chg": chg, "share": share, "n_valid": n_valid,
            "red": red, "nonred": nonred, "classified": cls,
            "spyred": spy_red_days(S_C) if S_C is not None else np.zeros(len(P.cal), dtype=bool),
            "rvol": rv, "cr": cp, "leader": leader_at_t(P), "glitch": glitch_matrix(P.C), "feats": feats, **sets}


def feature_ok(feats: dict, match_vars) -> np.ndarray:
    ok = np.isfinite(feats["above50"])
    for v in match_vars:
        ok &= np.isfinite(feats[v])
    return ok


def first_feature_t(ctx: dict):
    ok = feature_ok(ctx["feats"], MATCH_VARS)
    cols = np.flatnonzero(ok.any(axis=0))
    return int(cols[0]) if len(cols) else None


# ═════════════════════════════════════════════════════════════════════════════
# MATCHING
# ═════════════════════════════════════════════════════════════════════════════
def rows_table(ctx: dict, mask: np.ndarray, day_mask: np.ndarray, match_vars, tmax: int):
    """(rows with every feature, n_no_features). Rows sorted by (day, sym); id = position."""
    T = ctx["T"]
    tm = np.zeros(T, dtype=bool)
    if tmax >= FIRST_T:
        tm[FIRST_T:tmax + 1] = True
    m = mask & (day_mask & tm)[None, :]
    i, t = np.nonzero(m)
    ok = feature_ok(ctx["feats"], match_vars)[i, t]
    nof = int((~ok).sum())
    i, t = i[ok], t[ok]
    o = np.lexsort((i, t))
    i, t = i[o], t[o]
    syms = np.asarray(ctx["P"].syms, dtype=object)
    df = pd.DataFrame({"id": np.arange(len(i), dtype=np.int64), "i": i.astype(np.int64),
                       "sym": syms[i] if len(i) else np.array([], dtype=object),
                       "day": t.astype(np.int64), "above50": ctx["feats"]["above50"][i, t]})
    for v in match_vars:
        df[v] = ctx["feats"][v][i, t]
    return df, nof


def pooled_sd(sig: pd.DataFrame, pool: pd.DataFrame, match_vars) -> np.ndarray:
    out = []
    for v in match_vars:
        a = np.asarray(sig[v], dtype=float); b = np.asarray(pool[v], dtype=float)
        a, b = a[np.isfinite(a)], b[np.isfinite(b)]
        out.append(math.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2.0) if a.size > 1 and b.size > 1 else float("nan"))
    return np.asarray(out, dtype=float)


def match_same_day(sig: pd.DataFrame, pool: pd.DataFrame, sd, *, caliper, match_vars):
    """1:1 nearest neighbour, same day only, exact on above50, |z diff| <= caliper on
    EVERY covariate, greedy by (dist, sid, pid), without replacement, fully deterministic.
    Returns (pairs DataFrame[sid, pid, day, dist], sorted unmatched sids)."""
    sd = np.asarray(sd, dtype=float)
    mv = list(match_vars)
    rows = []
    unmatched = []
    if len(sig) == 0:
        return pd.DataFrame({"sid": [], "pid": [], "day": [], "dist": []}).astype(
            {"sid": np.int64, "pid": np.int64, "day": np.int64, "dist": float}), []
    s_id = sig["id"].to_numpy(dtype=np.int64); p_id = pool["id"].to_numpy(dtype=np.int64)
    s_day = sig["day"].to_numpy(dtype=np.int64); p_day = pool["day"].to_numpy(dtype=np.int64)
    s_ab = sig["above50"].to_numpy(dtype=float); p_ab = pool["above50"].to_numpy(dtype=float)
    Zs_all = sig[mv].to_numpy(dtype=float) / sd
    Zp_all = pool[mv].to_numpy(dtype=float) / sd
    pgroups: dict = {}
    for j in range(len(p_id)):
        pgroups.setdefault((int(p_day[j]), float(p_ab[j])), []).append(j)
    sgroups: dict = {}
    for j in range(len(s_id)):
        sgroups.setdefault((int(s_day[j]), float(s_ab[j])), []).append(j)
    for key in sorted(sgroups):
        si = np.asarray(sgroups[key], dtype=np.int64)
        pi = np.asarray(pgroups.get(key, []), dtype=np.int64)
        if len(pi) == 0:
            unmatched.extend(int(s_id[k]) for k in si)
            continue
        D = Zs_all[si][:, None, :] - Zp_all[pi][None, :, :]
        ok = (np.abs(D) <= caliper).all(axis=2)
        a, b = np.nonzero(ok)
        dist = np.sqrt((D[a, b] ** 2).sum(axis=1))
        o = np.lexsort((p_id[pi[b]], s_id[si[a]], dist))
        used_s, used_p = set(), set()
        for k in o:
            if len(used_s) == len(si) or len(used_p) == len(pi):
                break
            sa, pb = int(si[a[k]]), int(pi[b[k]])
            if sa in used_s or pb in used_p:
                continue
            used_s.add(sa); used_p.add(pb)
            rows.append((int(s_id[sa]), int(p_id[pb]), int(key[0]), float(dist[k])))
        unmatched.extend(int(s_id[k]) for k in si if int(k) not in used_s)
    pairs = pd.DataFrame(rows, columns=["sid", "pid", "day", "dist"]).astype(
        {"sid": np.int64, "pid": np.int64, "day": np.int64, "dist": float})
    return pairs, sorted(unmatched)


def smd(a, b) -> float:
    a = np.asarray(a, dtype=float); b = np.asarray(b, dtype=float)
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if a.size < 2 or b.size < 2:
        return float("nan")
    den = math.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2.0)
    diff = float(a.mean() - b.mean())
    if den == 0:
        return 0.0 if diff == 0 else float("inf") * (1 if diff > 0 else -1)
    return diff / den


def balance_gate(bal: dict, match_vars) -> bool:
    """|SMD| < BALANCE_SMD_MAX on every match var and above50; NaN fails."""
    for v in tuple(match_vars) + EXACT_VARS:
        x = bal.get("smd_" + v)
        if x is None or not (x == x) or not (abs(x) < BALANCE_SMD_MAX):
            return False
    return True


def primary_eligible_tmax(T: int) -> int:
    return T - 1 - H_PRIMARY


def do_match(ctx: dict, sig_mask, pool_mask, day_mask, *, caliper, match_vars, diag_beta=False) -> dict:
    """Rows -> pooled SD -> matcher -> balance on the H_PRIMARY-eligible subset."""
    T = ctx["T"]
    tmax = T - 1 - min(HORIZONS)
    sig, nof_s = rows_table(ctx, sig_mask, day_mask, match_vars, tmax)
    pool, nof_p = rows_table(ctx, pool_mask, day_mask, match_vars, tmax)
    sd = pooled_sd(sig, pool, match_vars)
    pairs, unmatched = match_same_day(sig, pool, sd, caliper=caliper, match_vars=match_vars)
    pairs = pairs.assign(i_s=sig["i"].to_numpy()[pairs["sid"].to_numpy()] if len(pairs) else np.array([], np.int64),
                         i_p=pool["i"].to_numpy()[pairs["pid"].to_numpy()] if len(pairs) else np.array([], np.int64))
    pairs = pairs.rename(columns={"day": "t"})
    bal = balance_report(ctx, sig, pool, pairs, unmatched, sd, caliper, match_vars, diag_beta=diag_beta)
    return {"sig": sig, "pool": pool, "pairs": pairs, "unmatched": unmatched, "balance": bal,
            "no_features": {"sig": nof_s, "pool": nof_p}}


def balance_report(ctx, sig, pool, pairs, unmatched, sd, caliper, match_vars, diag_beta=False) -> dict:
    T = ctx["T"]
    tp = primary_eligible_tmax(T)
    pm = pairs[pairs["t"] <= tp] if len(pairs) else pairs
    n_sig_sub = int((sig["day"] <= tp).sum()) if len(sig) else 0
    sp = sig.set_index("id").loc[pm["sid"].to_numpy()] if len(pm) else sig.iloc[:0]
    pp = pool.set_index("id").loc[pm["pid"].to_numpy()] if len(pm) else pool.iloc[:0]
    out = {}
    for v in tuple(match_vars) + EXACT_VARS:
        out["smd_" + v] = smd(sp[v], pp[v]) if len(pm) else float("nan")
    i_s = pm["i_s"].to_numpy() if len(pm) else np.array([], np.int64)
    i_p = pm["i_p"].to_numpy() if len(pm) else np.array([], np.int64)
    t = pm["t"].to_numpy() if len(pm) else np.array([], np.int64)
    P = ctx["P"]
    with np.errstate(invalid="ignore", divide="ignore"):
        diag = {"chg": ctx["chg"], "rvol": ctx["rvol"], "close_pos": ctx["cr"], "ln_close": np.log(P.C)}
    if diag_beta:
        diag["beta63"] = ctx["feats"]["beta63"]
    for k, a in diag.items():
        out["diag_" + k] = smd(a[i_s, t], a[i_p, t]) if len(pm) else float("nan")
    out["balanced"] = balance_gate(out, match_vars)
    out["matched_share"] = (len(pm) / n_sig_sub) if n_sig_sub else float("nan")
    out["n_pairs"] = int(len(pm))
    out["n_pairs_all_days"] = int(len(pairs))
    out["n_signal_rows"] = n_sig_sub
    out["n_unmatched"] = int(sum(1 for u in unmatched if int(sig["day"].iloc[u]) <= tp)) if len(sig) else 0
    out["sd"] = {v: float(x) for v, x in zip(match_vars, sd)}
    out["caliper"] = caliper
    out["match_vars"] = list(match_vars)
    g = groupings(t, H_PRIMARY)
    out["G"] = {k: int(len(np.unique(v))) for k, v in g.items()}
    out["G"]["G_min"] = int(min(out["G"].values())) if len(t) else 0
    return out


# ═════════════════════════════════════════════════════════════════════════════
# CLUSTERS AND CI (fixed blocks, never chained)
# ═════════════════════════════════════════════════════════════════════════════
def blocks(t_idx, size: int) -> np.ndarray:
    return np.asarray(t_idx, dtype=np.int64) // int(size)


def groupings(t_idx, h: int) -> dict:
    t_idx = np.asarray(t_idx, dtype=np.int64)
    return {"day": t_idx, "blk_h": blocks(t_idx, h), "blk_m": blocks(t_idx, BLOCK_SESSIONS)}


def _null_ci_block(G: dict, reps: dict) -> dict:
    return {"ci": None, "sig_ci": None, "twin_ci": None, "G": G, "G_min": min(G.values()) if G else 0,
            "reps": reps, "mdl": None}


def lift_ci(vals, is_sig, is_twin, t_idx, h: int) -> dict:
    """Paired cluster bootstrap (AS.boot_diff) under three FIXED groupings; the CI is the
    widest of the three, and NULL if ANY grouping has < MIN_CLUSTERS clusters or
    < MIN_BOOT_REPS usable draws (no fallback to the other groupings)."""
    vals = np.asarray(vals, dtype=float)
    is_sig = np.asarray(is_sig, dtype=bool); is_twin = np.asarray(is_twin, dtype=bool)
    rows = is_sig | is_twin
    sig_mean = float(vals[is_sig].mean()) if is_sig.any() else float("nan")
    twin_mean = float(vals[is_twin].mean()) if is_twin.any() else float("nan")
    base = {"lift": sig_mean - twin_mean, "sig": sig_mean, "twin": twin_mean,
            "n_sig": int(is_sig.sum()), "n_twin": int(is_twin.sum())}
    gs = groupings(t_idx, h)
    G = {k: int(len(np.unique(v[rows]))) for k, v in gs.items()}
    reps, diffs, acis, bcis = {}, [], [], []
    null = False
    for k, lab in gs.items():
        if k == "blk_m" and h == BLOCK_SESSIONS:
            reps[k] = reps["blk_h"]
            continue
        if G[k] < MIN_CLUSTERS or not is_sig.any() or not is_twin.any():
            reps[k] = None
            null = True
            continue
        try:
            r = AS.boot_diff(vals, is_sig, is_twin, lab, B=BOOT_B, seed=BOOT_SEED)
        except (IndexError, ValueError):
            reps[k] = 0
            null = True
            continue
        reps[k] = int(r["reps"])
        if r["reps"] < MIN_BOOT_REPS:
            null = True
            continue
        diffs.append(r["diff_ci"]); acis.append(r["a_ci"]); bcis.append(r["b_ci"])
    if null:
        return {**base, **_null_ci_block(G, reps)}
    ci = AS.widest(*diffs)
    return {**base, "ci": list(ci), "sig_ci": list(AS.widest(*acis)), "twin_ci": list(AS.widest(*bcis)),
            "G": G, "G_min": min(G.values()), "reps": reps, "mdl": MDL_Z * (ci[1] - ci[0]) / 3.92}


def arm_ci(vals, t_idx, h: int) -> dict:
    """One arm's mean with the same three-grouping null rule (S11, descriptive)."""
    vals = np.asarray(vals, dtype=float)
    m = np.ones(len(vals), dtype=bool)
    r = lift_ci(vals, m, m, t_idx, h)
    return {"mean": r["sig"], "n": int(len(vals)), "ci": r["sig_ci"], "G": r["G"], "G_min": r["G_min"],
            "reps": r["reps"]}


# ═════════════════════════════════════════════════════════════════════════════
# OUTCOMES (bars after t only)
# ═════════════════════════════════════════════════════════════════════════════
def _window(A: np.ndarray, i: np.ndarray, start: np.ndarray, width: int, stop: np.ndarray):
    """A[i, start..stop] as an (n x width) block, NaN outside [0, T-1] and past stop."""
    T = A.shape[1]
    ks = start[:, None] + np.arange(width)[None, :]
    inside = (ks >= 0) & (ks <= T - 1) & (ks <= stop[:, None])
    w = A[i[:, None], np.clip(ks, 0, T - 1)].astype(float)
    w[~inside] = np.nan
    return w, inside


def outcomes(P: Panel, B_O, B_C, i, t, h: int, entry: str, glitch: np.ndarray, chg: np.ndarray = None) -> dict:
    """Per row: exit x = last finite close in (t, t+h] (carry-forward through a halt);
    entry O = O[t+1] (bench on RSP's open t+1), entry C = C[t] (bench C[t]).
    Rows whose t-R_MED..x window holds a scale glitch are excluded (glitch_excl)."""
    i = np.asarray(i, dtype=np.int64); t = np.asarray(t, dtype=np.int64)
    n = len(i)
    T = P.C.shape[1]
    nan = np.full(n, np.nan)
    if n == 0:
        z = np.zeros(0, dtype=bool)
        return {"ok": z, "excess": nan, "ret": nan, "bench": nan, "undercut": z, "mae": nan,
                "x": np.zeros(0, np.int64), "glitch_excl": z, "big": z}
    stop = t + h
    Cw, _ = _window(P.C, i, t + 1, h, stop)
    fin = np.isfinite(Cw)
    has = fin.any(axis=1)
    last = (h - 1) - np.argmax(fin[:, ::-1], axis=1)
    x = np.where(has, t + 1 + last, t)
    xc = np.clip(x, 0, T - 1)
    if entry == "O":
        tn = np.clip(t + 1, 0, T - 1)
        ent = np.where(t + 1 <= T - 1, P.O[i, tn], np.nan)
        bent = np.where(t + 1 <= T - 1, B_O[tn], np.nan)
    elif entry == "C":
        ent = P.C[i, t]
        bent = B_C[t]
    else:
        raise ValueError("entry must be O or C")
    with np.errstate(invalid="ignore", divide="ignore"):
        cx = P.C[i, xc]
        bx = B_C[xc]
        ok = (has & np.isfinite(ent) & (ent > 0) & np.isfinite(bent) & (bent > 0)
              & np.isfinite(cx) & np.isfinite(bx))
        ret = cx / ent - 1.0
        bench = bx / bent - 1.0
        excess = 100.0 * (ret - bench)
        Lw, _ = _window(P.L, i, t + 1, h, x)
        anyL = np.isfinite(Lw).any(axis=1)
        minL = np.where(anyL, np.nanmin(np.where(np.isfinite(Lw), Lw, np.inf), axis=1), np.nan)
        undercut = anyL & np.isfinite(P.L[i, t]) & (minL < P.L[i, t])
        mae = 100.0 * (minL / ent - 1.0)
    width = R_MED + h + 1
    gw, gin = _window(glitch.astype(float), i, t - R_MED, width, x)
    g_any = (np.nan_to_num(gw, nan=0.0) > 0).any(axis=1)
    big = np.zeros(n, dtype=bool)
    if chg is not None:
        cw, _ = _window(chg, i, t - R_MED, width, x)
        with np.errstate(invalid="ignore"):
            big = (np.abs(np.nan_to_num(cw, nan=0.0)) >= BIG_MOVE_PCT / 100.0).any(axis=1)
    glitch_excl = ok & g_any
    ok = ok & ~g_any
    return {"ok": ok, "excess": np.where(ok, excess, np.nan), "ret": np.where(ok, 100.0 * ret, np.nan),
            "bench": np.where(ok, 100.0 * bench, np.nan), "undercut": undercut & ok,
            "mae": np.where(ok, mae, np.nan), "x": x, "glitch_excl": glitch_excl, "big": big & ok}


def _q(a, p):
    a = np.asarray(a, dtype=float)
    a = a[np.isfinite(a)]
    return float(np.percentile(a, p)) if a.size else float("nan")


def _arm_stats(o: dict, keep: np.ndarray) -> dict:
    ex = o["excess"][keep]
    return {"mean_excess": float(ex.mean()) if ex.size else float("nan"),
            "median_excess": _q(ex, 50), "trimmed_mean_excess": ES.trimmed_mean(ex),
            "raw_mean_return": float(o["ret"][keep].mean()) if ex.size else float("nan"),
            "hit_rate": float((ex > 0).mean()) if ex.size else float("nan"),
            "undercut_rate": float(o["undercut"][keep].mean()) if ex.size else float("nan"),
            "mae_p50": _q(o["mae"][keep], 50), "mae_p90": _q(o["mae"][keep], 10)}


def pair_outcomes(ctx: dict, pairs: pd.DataFrame, h: int, entry: str, sub=None) -> dict:
    """Outcomes for both members of the pairs with t <= T-1-h (and `sub`); complete = both ok."""
    T = ctx["T"]
    t_all = pairs["t"].to_numpy(dtype=np.int64) if len(pairs) else np.zeros(0, np.int64)
    m = t_all <= T - 1 - h
    if sub is not None:
        m &= np.asarray(sub, dtype=bool)
    ps = pairs[m] if len(pairs) else pairs
    t = ps["t"].to_numpy(dtype=np.int64) if len(ps) else np.zeros(0, np.int64)
    i_s = ps["i_s"].to_numpy(dtype=np.int64) if len(ps) else np.zeros(0, np.int64)
    i_p = ps["i_p"].to_numpy(dtype=np.int64) if len(ps) else np.zeros(0, np.int64)
    os_ = outcomes(ctx["P"], ctx["B_O"], ctx["B_C"], i_s, t, h, entry, ctx["glitch"], ctx["chg"])
    ot = outcomes(ctx["P"], ctx["B_O"], ctx["B_C"], i_p, t, h, entry, ctx["glitch"], ctx["chg"])
    both = os_["ok"] & ot["ok"]
    return {"t": t, "i_s": i_s, "i_p": i_p, "sig": os_, "twin": ot, "both": both, "n_eligible": int(len(t)),
            "diff": (os_["excess"] - ot["excess"])[both]}


def cell(ctx: dict, pairs: pd.DataFrame, h: int, entry: str, sub=None) -> tuple:
    """(report dict, pair-outcome internals) for one (h, entry) statistic."""
    po = pair_outcomes(ctx, pairs, h, entry, sub)
    b = po["both"]
    t = po["t"][b]
    vals = np.concatenate([po["sig"]["excess"][b], po["twin"]["excess"][b]])
    n = int(b.sum())
    is_sig = np.r_[np.ones(n, bool), np.zeros(n, bool)]
    r = lift_ci(vals, is_sig, ~is_sig, np.r_[t, t], h)
    cal = ctx["P"].cal
    r.update({"h": h, "entry": entry, "n_pairs": n, "n_days": int(len(np.unique(t))),
              "first_day": cal[int(t.min())] if n else None, "last_day": cal[int(t.max())] if n else None,
              "sig_arm": _arm_stats(po["sig"], b), "twin_arm": _arm_stats(po["twin"], b),
              "no_outcome": {"sig": int((~po["sig"]["ok"] & ~po["sig"]["glitch_excl"]).sum()),
                             "twin": int((~po["twin"]["ok"] & ~po["twin"]["glitch_excl"]).sum())},
              "glitch_rows": {"sig": int(po["sig"]["glitch_excl"].sum()),
                              "twin": int(po["twin"]["glitch_excl"].sum())},
              "n_eligible_pairs": po["n_eligible"]})
    return r, po


def date_halves(t_idx) -> np.ndarray:
    """True for H1 rows: the first floor(D/2) UNIQUE days (D = distinct days)."""
    t_idx = np.asarray(t_idx, dtype=np.int64)
    ud = np.unique(t_idx)
    return np.isin(t_idx, ud[:len(ud) // 2])


def _lift_of(diff: np.ndarray):
    return float(diff.mean()) if len(diff) else None


def diff_in_lift(po_a: dict, po_b: dict, h: int) -> dict:
    """CI of (lift A - lift B) via the pair differences, both sets' t in the groupings."""
    da, db = po_a["diff"], po_b["diff"]
    ta, tb = po_a["t"][po_a["both"]], po_b["t"][po_b["both"]]
    vals = np.r_[da, db]
    ma = np.r_[np.ones(len(da), bool), np.zeros(len(db), bool)]
    r = lift_ci(vals, ma, ~ma, np.r_[ta, tb], h)
    return r


# ═════════════════════════════════════════════════════════════════════════════
# VERDICT (mechanical; 3.12)
# ═════════════════════════════════════════════════════════════════════════════
def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def _gt0(x) -> bool:
    v = _num(x)
    return v is not None and v > 0


def _lt0(x) -> bool:
    v = _num(x)
    return v is not None and v < 0


def verdict(res: dict) -> dict:
    rev = PREREG_REV
    if not (res.get("snapshot") or {}).get("ok", False):
        return {"status": "invalid_snapshot", "tags": [], "failed": ["snapshot"], "rev": rev}
    if int((res.get("pit") or {}).get("mismatch", 0) or 0) > 0:
        return {"status": "invalid_pit", "tags": [], "failed": ["pit"], "rev": rev}
    bal = ((res.get("balance") or {}).get("primary") or {})
    if not bal.get("balanced", False):
        return {"status": "no_signal", "tags": ["imbalanced"], "failed": ["balance"], "rev": rev}
    pr = (res.get("primary") or {}).get("h%d_%s" % (H_PRIMARY, PRIMARY_ENTRY)) or {}
    st = res.get("stability") or {}
    ci, sig_ci = pr.get("ci"), pr.get("sig_ci")
    share = _num(bal.get("matched_share"))
    g = share is not None and share >= MIN_MATCHED_SHARE
    k = ci is not None
    h1 = (st.get("date_h1") or {}).get("lift"); h2 = (st.get("date_h2") or {}).get("lift")
    dob = st.get("drop_one_block") or {}
    ops = (st.get("one_per_symbol") or {}).get("lift")
    ec = (st.get("entry_C") or {}).get("lift")
    ca = st.get("cache_all") or {}
    hc = st.get("house_caliper") or {}
    crit = {
        "g": g, "k": k,
        "a": k and _gt0(ci[0]),
        "b": sig_ci is not None and _gt0(sig_ci[0]),
        "c": _gt0(h1) and _gt0(h2),
        "c2": _gt0(dob.get("min")),
        "d": _gt0(ops),
        "e": _gt0(ec),
        "f": _gt0(ca.get("lift")) and bool(ca.get("balanced")),
        "f2": _gt0(hc.get("lift")) and bool(hc.get("balanced")),
        "a-": k and _lt0(ci[1]),
        "c-": _lt0(h1) and _lt0(h2),
        "c2-": _lt0(dob.get("max")),
        "d-": _lt0(ops),
        "e-": _lt0(ec),
        "f-": _lt0(ca.get("lift")) and bool(ca.get("balanced")),
        "f2-": _lt0(hc.get("lift")) and bool(hc.get("balanced")),
    }
    pos_stab = ("c", "c2", "d", "e", "f", "f2")
    neg_stab = ("c-", "c2-", "d-", "e-", "f-", "f2-")
    failed = [c for c, v in crit.items() if not v]
    is_signal = g and k and crit["a"] and crit["b"] and all(crit[c] for c in pos_stab)
    is_inverted = g and k and crit["a-"] and all(crit[c] for c in neg_stab)
    tags = []
    if is_signal or is_inverted:
        status = "signal" if is_signal else "inverted"
        s3 = (res.get("secondary") or {}).get("S3") or {}
        s3ci = s3.get("ci")
        s3_ok = bool(s3.get("balanced")) and s3ci is not None and (
            _gt0(s3ci[0]) if is_signal else _lt0(s3ci[1]))
        if not s3_ok:
            tags.append("not_red_specific")
    else:
        status = "no_signal"
        if crit["a"] and not crit["b"]:
            tags.append("relative_only")
        if crit["b"] and not crit["a"]:
            tags.append("absolute_only")
        if crit["a"] and crit["b"] and not all(crit[c] for c in pos_stab):
            tags.append("fragile")
        if crit["a-"] and not all(crit[c] for c in neg_stab):
            tags.append("inverted_fragile")
        if not g:
            tags.append("undermatched")
        if not k:
            tags.append("few_clusters")
    return {"status": status, "tags": tags, "failed": failed, "rev": rev}


# ═════════════════════════════════════════════════════════════════════════════
# HEADLINE (3.13)
# ═════════════════════════════════════════════════════════════════════════════
def _fmt_pp(x) -> str:
    v = _num(x)
    return "n/a" if v is None else "%+.2fpp" % v


def _fmt_ci(ci, G_min) -> str:
    if ci is None:
        return "[n/a: %s periods]" % (G_min if G_min is not None else 0)
    return "[%+.2f, %+.2f]" % (ci[0], ci[1])


def headline(res: dict) -> str:
    v = res.get("verdict") or {}
    pr = (res.get("primary") or {}).get("h%d_%s" % (H_PRIMARY, PRIMARY_ENTRY)) or {}
    ec = (res.get("stability") or {}).get("entry_C") or {}
    tags = v.get("tags") or []
    tag_s = (" (" + "; ".join(TAG_TEXT[t] for t in tags) + ")") if tags else ""
    G_min = pr.get("G_min")
    return ("Green on a red day (up on the day, ≥ $%g, ≥ $%gM traded, volume ≥ %g× its %d-day average, "
            "closed in the upper half of the day's range), bought at the next open and held %d sessions: "
            "%s vs same-day red twins %s, %s vs RSP %s — %s%s. Measured from the signal-day close instead: %s. "
            "n = %d pairs on %d red days (%s independent periods), %s → %s."
            % (PRICE_FLOOR, DVOL_MIN / 1e6, RVOL_MIN, VOL_BARS, H_PRIMARY,
               _fmt_pp(pr.get("lift")), _fmt_ci(pr.get("ci"), G_min),
               _fmt_pp(pr.get("sig")), _fmt_ci(pr.get("sig_ci"), G_min),
               str(v.get("status", "not_run")).upper(), tag_s, _fmt_pp(ec.get("lift")),
               int(pr.get("n_pairs") or 0), int(pr.get("n_days") or 0),
               G_min if G_min is not None else 0, pr.get("first_day") or "n/a", pr.get("last_day") or "n/a"))


# ═════════════════════════════════════════════════════════════════════════════
# RUNTIME SANITY: repro, PIT, anecdote
# ═════════════════════════════════════════════════════════════════════════════
def repro_block(ctx: dict, expect) -> dict:
    cal = ctx["P"].cal
    if REPRO_DAY not in cal:
        return {"day": REPRO_DAY, "present": False}
    t = cal.index(REPRO_DAY)
    syms = ctx["P"].syms
    got = sorted(syms[i] for i in np.flatnonzero(ctx["S2"][:, t]))
    leaders = sorted(syms[i] for i in np.flatnonzero(ctx["S2"][:, t] & ctx["leader"][:, t]))
    B = ctx["B_C"]
    out = {"day": REPRO_DAY, "present": True,
           "rsp_pct": float(100.0 * (B[t] / B[t - 1] - 1.0)) if t > 0 else None,
           "breadth": float(ctx["share"][t]), "n_valid": int(ctx["n_valid"][t]), "is_red": bool(ctx["red"][t]),
           "n_got": len(got), "got": got, "leaders": leaders, "n_leaders": len(leaders),
           "anecdote_present": ANECDOTE_SYMBOL in got}
    if expect is not None:
        exp = sorted({(e["sym"] if isinstance(e, dict) else str(e)).upper() for e in expect})
        out.update({"n_expected": len(exp), "missing": sorted(set(exp) - set(got)),
                    "extra": sorted(set(got) - set(exp)), "match": set(exp) == set(got)})
    else:
        out.update({"n_expected": None, "missing": None, "extra": None, "match": None})
    return out


_PIT_KEYS = ("chg", "rvol", "cr", "S1", "S2", "POOL")


def pit_check(frames: dict, bench_df, ctx: dict) -> dict:
    """Rebuild a one-name panel truncated at cal[t] (BENCH too); every feature and flag at
    t must equal the full panel's value exactly (NaN == NaN)."""
    P = ctx["P"]
    cal = P.cal
    T = ctx["T"]
    s2 = ctx["S2"].copy()
    s2[:, :FIRST_T] = False
    cands = [k for k in range(len(P.syms)) if s2[k].any()]
    rng = np.random.default_rng(PIT_SEED)
    n = min(PIT_CHECK_NAMES, len(cands))
    pick = sorted(rng.choice(len(cands), size=n, replace=False).tolist()) if n else []
    mism, checked, detail = 0, 0, []
    for c in pick:
        i = cands[c]
        ts = np.flatnonzero(s2[i])
        t = int(ts[int(rng.integers(0, len(ts)))])
        sym = P.syms[i]
        f_t = cap_as_of(frames[sym], cal[t])
        b_t = cap_as_of(bench_df, cal[t])
        cal_t = cal[:t + 1]
        P1 = build_panel({sym: f_t}, cal_t)
        B_O1, B_C1 = bench_arrays(b_t, cal_t)
        chg1 = day_change(P1)
        rv1 = rvol(P1); cr1 = close_pos(P1)
        sets1 = signal_sets(P1, chg1, rv1, cr1)
        f1 = features_prev(P1, B_C1, chg1)
        one = {"chg": chg1, "rvol": rv1, "cr": cr1, **sets1}
        bad = []
        for k in _PIT_KEYS:
            a, b = one[k][0, t], ctx[k][i, t]
            if not _same(a, b):
                bad.append(k)
        for k in tuple(MATCH_VARS) + EXACT_VARS + ("off52_bars",):
            a, b = f1[k][0, t], ctx["feats"][k][i, t]
            if not _same(a, b):
                bad.append(k)
        checked += 1
        if bad:
            mism += 1
            detail.append({"sym": sym, "day": cal[t], "fields": bad})
    return {"names": checked, "mismatch": mism, "detail": detail[:20], "seed": PIT_SEED}


def _same(a, b) -> bool:
    a, b = float(a), float(b)
    return (a != a and b != b) or a == b


def anecdote(ctx: dict) -> dict:
    P = ctx["P"]
    if ANECDOTE_SYMBOL not in P.syms:
        return {"symbol": ANECDOTE_SYMBOL, "present": False, "label": "not a measurement"}
    i = P.syms.index(ANECDOTE_SYMBOL)
    cal = P.cal
    out = {"symbol": ANECDOTE_SYMBOL, "present": True, "label": "not a measurement"}
    if REPRO_DAY in cal:
        t = cal.index(REPRO_DAY)
        f = ctx["feats"]
        out["repro_row"] = {"day": REPRO_DAY, "chg_pct": 100 * ctx["chg"][i, t], "rvol": ctx["rvol"][i, t],
                            "close_pos": ctx["cr"][i, t], "S2": bool(ctx["S2"][i, t]),
                            "leader": bool(ctx["leader"][i, t]), "above50_prev": f["above50"][i, t],
                            "off52_prev": f["off52"][i, t]}
    T = ctx["T"]
    ts = [t for t in np.flatnonzero(ctx["S2"][i] & ctx["red"]) if FIRST_T <= t <= T - 1 - H_PRIMARY]
    ts = np.asarray(ts, dtype=np.int64)
    o = outcomes(P, ctx["B_O"], ctx["B_C"], np.full(len(ts), i, np.int64), ts, H_PRIMARY, PRIMARY_ENTRY,
                 ctx["glitch"], ctx["chg"])
    out["past_s2_on_red"] = [{"day": cal[int(t)], "excess_h10_open_pp": o["excess"][k]} for k, t in enumerate(ts)]
    out["n_past"] = int(len(ts))
    return out


# ═════════════════════════════════════════════════════════════════════════════
# THE STUDY (pure given frames)
# ═════════════════════════════════════════════════════════════════════════════
def prereg_block() -> dict:
    names = ["STUDY", "PREREG_REV", "UNIVERSE_MODE", "RED_RSP_PCT", "RED_BREADTH_MAX", "MIN_BREADTH_NAMES",
             "SPY_SYMBOL", "SPY_RED_PCT", "DVOL_MIN", "CR_MIN", "MA50_BARS", "FIRST_T", "HIGH_MIN_BARS",
             "H_PRIMARY", "PRIMARY_ENTRY", "CHECK_ENTRY", "ENTRIES", "EVENT_POP_PCT", "MATCH_VARS",
             "MATCH_VARS_REV0", "EXACT_VARS", "CALIPER_SD", "CALIPER_SD_HOUSE", "BALANCE_SMD_MAX",
             "MIN_MATCHED_SHARE", "MIN_BOOT_REPS", "BOOT_B", "BOOT_SEED", "MDL_Z", "BLOCK_SESSIONS",
             "BETA_MIN_PAIRS", "BIG_MOVE_PCT", "NEAR_FLOOR_BAND", "PIT_CHECK_NAMES", "PIT_SEED",
             "ENDED_GRACE_DAYS", "REFUSE_WINDOW_ET", "REPRO_DAY", "ANECDOTE_SYMBOL",
             "BENCH", "R_SHORT", "R_MED", "VOL_BARS", "RVOL_MIN", "PRICE_FLOOR", "DVOL_APP", "HIGH_BARS",
             "LEADER_NEAR_HIGH_PCT", "HORIZONS", "MIN_CLUSTERS", "VERDICT_RULE_TEXT", "TAG_TEXT"]
    g = globals()
    return {n: g[n] for n in names}


def _say(msg: str, quiet: bool):
    if not quiet:
        print(msg, flush=True)


def run_study(frames: dict, bench_df, spy_df, as_of: str, *, cache_frames=None, expect=None,
              stage: str = "all", verify_snapshot=None, quiet: bool = False) -> dict:
    t0 = time.time()
    excl = exclude_set()
    dup_keys = int(getattr(frames, "dup_day_keys", 0))
    etf_present = int(sum(1 for s in frames if s in excl))
    frames = {s: f for s, f in frames.items() if s not in excl and f is not None and len(f)}
    cal = [k for k in day_keys(cap_as_of(bench_df, as_of))]
    T = len(cal)
    P = build_panel(frames, cal)
    B_O, B_C = bench_arrays(bench_df, cal)
    _, S_C = bench_arrays(spy_df, cal)
    ctx = compute_ctx(P, B_O, B_C, S_C)
    red, nonred = ctx["red"], ctx["nonred"]
    res = {"study": STUDY, "prereg_rev": PREREG_REV, "as_of": as_of, "stage": stage, "prereg": prereg_block()}

    tmin = T - 1 - min(HORIZONS)
    tm = np.zeros(T, bool)
    if tmin >= FIRST_T:
        tm[FIRST_T:tmin + 1] = True
    ft = first_feature_t(ctx)
    _say("window start: first eligible t = %s (FIRST_T = %d), %s" % (ft, FIRST_T, cal[ft] if ft is not None else "n/a"), quiet)
    assert ft == FIRST_T, "first eligible t %s != FIRST_T %d" % (ft, FIRST_T)

    def cnt(mask, days):
        return int((mask & (days & tm)[None, :]).sum())

    uncl = ~ctx["classified"]
    red_by_h = {}
    for h in HORIZONS:
        m = np.zeros(T, bool)
        if T - 1 - h >= FIRST_T:
            m[FIRST_T:T - h] = True
        rd = np.flatnonzero(red & m)
        red_by_h[str(h)] = {"n": int(len(rd)), "first": cal[rd[0]] if len(rd) else None,
                            "last": cal[rd[-1]] if len(rd) else None}
        _say("h%d: %d red days, first %s last %s" % (h, len(rd), red_by_h[str(h)]["first"], red_by_h[str(h)]["last"]), quiet)
    res["sample"] = {
        "names": len(P.syms), "etf_excluded_present": etf_present,
        "dup_day_keys": dup_keys, "off_calendar_bars": P.off_calendar_bars,
        "sessions": T, "first_day": cal[0] if T else None, "last_day": cal[-1] if T else None,
        "first_t": ft, "red_days": red_by_h,
        "red_day_list": [cal[t] for t in np.flatnonzero(red) if t >= FIRST_T],
        "nonred_days": int((nonred & tm).sum()), "unclassified_days": int((uncl & tm).sum()),
        "spy_red_days": int((ctx["spyred"] & tm).sum()),
        "signals": {k: {"red": cnt(ctx[k], red), "nonred": cnt(ctx[k], nonred), "unclassified": cnt(ctx[k], uncl)}
                    for k in ("S1", "S2")},
        "pool_rows": {"red": cnt(ctx["POOL"], red), "nonred": cnt(ctx["POOL"], nonred)},
        "names_last_day_not_as_of": int(sum(1 for s in P.syms if day_keys(frames[s])[-1] != as_of)),
    }
    res["repro"] = repro_block(ctx, expect)
    rp = res["repro"]
    _say("REPRO %s: red=%s rsp=%s breadth=%s n_valid=%s S2=%s expected=%s match=%s missing=%s extra=%s leaders=%s VOYG=%s"
         % (REPRO_DAY, rp.get("is_red"), rp.get("rsp_pct"), rp.get("breadth"), rp.get("n_valid"), rp.get("n_got"),
            rp.get("n_expected"), rp.get("match"), rp.get("missing"), rp.get("extra"), rp.get("n_leaders"),
            rp.get("anecdote_present")), quiet)
    res["pit"] = pit_check(frames, cap_as_of(bench_df, as_of), ctx)
    _say("PIT: %d names checked, %d mismatches" % (res["pit"]["names"], res["pit"]["mismatch"]), quiet)
    res["anecdote"] = {"symbol": ANECDOTE_SYMBOL, "label": "not a measurement"}
    if stage == "features":
        res["memory"] = _mem(t0)
        return res

    # ── matching (no outcome is computed here) ──────────────────────────────
    runs = {}
    runs["primary"] = do_match(ctx, ctx["S2"], ctx["POOL"], red, caliper=CALIPER_SD, match_vars=MATCH_VARS)
    runs["house_caliper"] = do_match(ctx, ctx["S2"], ctx["POOL"], red, caliper=CALIPER_SD_HOUSE, match_vars=MATCH_VARS)
    runs["S3_nonred"] = do_match(ctx, ctx["S2"], ctx["POOL"], nonred, caliper=CALIPER_SD, match_vars=MATCH_VARS)
    runs["S1"] = do_match(ctx, ctx["S1"], ctx["POOL"], red, caliper=CALIPER_SD, match_vars=MATCH_VARS)
    runs["S6"] = do_match(ctx, ctx["S2"], ctx["POOL"], ctx["spyred"], caliper=CALIPER_SD, match_vars=MATCH_VARS)
    runs["S7"] = do_match(ctx, ctx["S2"], ctx["S1"] & ~ctx["S2"], red, caliper=CALIPER_SD, match_vars=MATCH_VARS)
    runs["S9"] = do_match(ctx, ctx["S2"], ctx["POOL"], red, caliper=CALIPER_SD, match_vars=MATCH_VARS_REV0,
                          diag_beta=True)
    res["balance"] = {k: v["balance"] for k, v in runs.items()}
    res["sample"]["no_features"] = runs["primary"]["no_features"]
    res["design"] = {k: {kk: runs[k]["balance"][kk] for kk in runs[k]["balance"]
                         if kk.startswith("smd_") or kk in ("matched_share", "balanced", "G", "n_pairs")}
                     for k in ("primary", "house_caliper", "S3_nonred")}
    for k, d in res["design"].items():
        _say("DESIGN %-13s matched_share=%.4f balanced=%s n_pairs=%d G=%s smd={%s}"
             % (k, d["matched_share"] if d["matched_share"] == d["matched_share"] else float("nan"), d["balanced"],
                d["n_pairs"], d["G"],
                ", ".join("%s: %+.3f" % (kk[4:], vv) for kk, vv in d.items() if kk.startswith("smd_"))), quiet)
    if stage == "match":
        res["memory"] = _mem(t0)
        return res

    # ── outcomes (stage all) ────────────────────────────────────────────────
    stop_early = None
    if not runs["primary"]["balance"]["balanced"]:
        stop_early = "imbalanced"
    elif res["pit"]["mismatch"] > 0:
        stop_early = "invalid_pit"
    if stop_early is None:
        _outcome_stage(res, ctx, runs, cache_frames, cal, as_of, quiet)
    else:
        _say("STOP before outcomes: %s" % stop_early, quiet)
    res["snapshot"] = verify_snapshot() if verify_snapshot is not None else {"ok": True, "skipped": True}
    res["snapshot"].setdefault("as_of", as_of)
    res["verdict"] = verdict(res)
    res["headline"] = headline(res)
    res["memory"] = _mem(t0)
    _say("VERDICT %s" % res["verdict"], quiet)
    _say("HEADLINE %s" % res["headline"], quiet)
    return res


def _mem(t0) -> dict:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    mb = rss / 1024.0 if sys.platform.startswith("linux") else rss / (1024.0 * 1024.0)
    return {"peak_rss_mb": round(mb, 1), "wall_s": round(time.time() - t0, 1)}


def _outcome_stage(res, ctx, runs, cache_frames, cal, as_of, quiet):
    T = ctx["T"]
    prim = runs["primary"]["pairs"]
    primary, internals = {}, {}
    for h in HORIZONS:
        for e in ENTRIES:
            r, po = cell(ctx, prim, h, e)
            primary["h%d_%s" % (h, e)] = r
            internals[(h, e)] = po
            _say("h%-2d %s  n=%-5d lift=%s ci=%s sig=%s sig_ci=%s G=%s" % (
                h, e, r["n_pairs"], _fmt_pp(r["lift"]), r["ci"], _fmt_pp(r["sig"]), r["sig_ci"], r["G"]), quiet)
    res["primary"] = primary
    res["sample"]["clusters"] = {str(h): {**primary["h%d_%s" % (h, PRIMARY_ENTRY)]["G"],
                                          "G_min": primary["h%d_%s" % (h, PRIMARY_ENTRY)]["G_min"]} for h in HORIZONS}
    po = internals[(H_PRIMARY, PRIMARY_ENTRY)]
    b = po["both"]
    t_c = po["t"][b]
    diff = po["diff"]
    res["sample"]["glitch_rows"] = primary["h%d_%s" % (H_PRIMARY, PRIMARY_ENTRY)]["glitch_rows"]
    res["sample"]["no_outcome"] = primary["h%d_%s" % (H_PRIMARY, PRIMARY_ENTRY)]["no_outcome"]

    # ── stability ───────────────────────────────────────────────────────────
    st = {}
    ud = np.unique(t_c)
    half = len(ud) // 2
    h1 = date_halves(t_c)
    st["date_h1"] = {"lift": _lift_of(diff[h1]), "n_pairs": int(h1.sum()), "n_days": int(half),
                     "last_day": cal[int(ud[half - 1])] if half else None}
    st["date_h2"] = {"lift": _lift_of(diff[~h1]), "n_pairs": int((~h1).sum()), "n_days": int(len(ud) - half),
                     "first_day": cal[int(ud[half])] if len(ud) > half else None}
    blk = blocks(t_c, BLOCK_SESSIONS)
    per = {}
    for bb in np.unique(blk):
        per[str(int(bb))] = _lift_of(diff[blk != bb])
    vals = {k: v for k, v in per.items() if v is not None}
    st["drop_one_block"] = {"per": per,
                            "min": min(vals.values()) if vals else None, "max": max(vals.values()) if vals else None,
                            "argmin": min(vals, key=vals.get) if vals else None,
                            "argmax": max(vals, key=vals.get) if vals else None}
    i_s = po["i_s"][b]
    first = {}
    for k in np.lexsort((i_s, t_c)):
        first.setdefault(int(i_s[k]), k)
    ops = np.array(sorted(first.values()), dtype=np.int64)
    st["one_per_symbol"] = {"lift": _lift_of(diff[ops]), "n_pairs": int(len(ops))}
    # (e) entry C on the SAME pairs (complete at entry O)
    sub = np.zeros(len(prim), bool)
    if len(prim):
        tt = prim["t"].to_numpy()
        elig = np.flatnonzero(tt <= T - 1 - H_PRIMARY)
        sub[elig[b]] = True
    _, poC = cell(ctx, prim, H_PRIMARY, CHECK_ENTRY, sub=sub)
    st["entry_C"] = {"lift": _lift_of(poC["diff"]), "n_pairs": int(poC["both"].sum())}
    rhc, _ = cell(ctx, runs["house_caliper"]["pairs"], H_PRIMARY, PRIMARY_ENTRY)
    st["house_caliper"] = {"lift": rhc["lift"] if rhc["n_pairs"] else None, "ci": rhc["ci"], "n_pairs": rhc["n_pairs"],
                           "balanced": runs["house_caliper"]["balance"]["balanced"]}
    res["stability"] = st

    # ── secondary ───────────────────────────────────────────────────────────
    sec = {}

    def pack(r, bal=None):
        keep = ("lift", "ci", "sig", "sig_ci", "twin", "twin_ci", "n_pairs", "n_days", "G", "G_min", "mdl",
                "first_day", "last_day", "sig_arm", "twin_arm")
        d = {k: r.get(k) for k in keep}
        if not r.get("n_pairs"):
            d["lift"] = None
        if bal is not None:
            d["balanced"] = bal["balanced"]; d["matched_share"] = bal["matched_share"]
        return d

    r1, _ = cell(ctx, runs["S1"]["pairs"], H_PRIMARY, PRIMARY_ENTRY)
    sec["S1"] = pack(r1, runs["S1"]["balance"])
    rn, pon = cell(ctx, runs["S3_nonred"]["pairs"], H_PRIMARY, PRIMARY_ENTRY)
    s3 = diff_in_lift(po, pon, H_PRIMARY)
    sec["S3"] = {"red_lift": primary["h%d_%s" % (H_PRIMARY, PRIMARY_ENTRY)]["lift"], "nonred": pack(rn),
                 "diff": s3["lift"] if len(po["diff"]) and len(pon["diff"]) else None, "ci": s3["ci"],
                 "G": s3["G"], "G_min": s3["G_min"], "balanced": runs["S3_nonred"]["balance"]["balanced"]}
    lead = ctx["leader"][prim["i_s"].to_numpy(), prim["t"].to_numpy()] if len(prim) else np.zeros(0, bool)
    rl, pol = cell(ctx, prim, H_PRIMARY, PRIMARY_ENTRY, sub=lead)
    rr, porr = cell(ctx, prim, H_PRIMARY, PRIMARY_ENTRY, sub=~lead)
    s4 = diff_in_lift(pol, porr, H_PRIMARY)
    sec["S4"] = {"leaders": pack(rl), "rest": pack(rr),
                 "diff": s4["lift"] if len(pol["diff"]) and len(porr["diff"]) else None, "ci": s4["ci"],
                 "G_min": s4["G_min"]}
    with np.errstate(invalid="ignore"):
        chg_s = ctx["chg"][prim["i_s"].to_numpy(), prim["t"].to_numpy()] if len(prim) else np.zeros(0)
        dv_s = (ctx["P"].C * ctx["P"].V)[prim["i_s"].to_numpy(), prim["t"].to_numpy()] if len(prim) else np.zeros(0)
    r5, _ = cell(ctx, prim, H_PRIMARY, PRIMARY_ENTRY, sub=(100.0 * chg_s <= EVENT_POP_PCT))
    sec["S5"] = pack(r5)
    r6, _ = cell(ctx, runs["S6"]["pairs"], H_PRIMARY, PRIMARY_ENTRY)
    sec["S6"] = pack(r6, runs["S6"]["balance"])
    r7, _ = cell(ctx, runs["S7"]["pairs"], H_PRIMARY, PRIMARY_ENTRY)
    sec["S7"] = pack(r7, runs["S7"]["balance"])
    r8, _ = cell(ctx, prim, H_PRIMARY, PRIMARY_ENTRY, sub=(dv_s >= DVOL_APP))
    sec["S8"] = pack(r8)
    r9, _ = cell(ctx, runs["S9"]["pairs"], H_PRIMARY, PRIMARY_ENTRY)
    sec["S9"] = pack(r9, runs["S9"]["balance"])
    sec["S9"]["diag_beta63"] = runs["S9"]["balance"].get("diag_beta63")
    ob = ctx["feats"]["off52_bars"]
    strict = ((ob[prim["i_s"].to_numpy(), prim["t"].to_numpy()] == HIGH_BARS)
              & (ob[prim["i_p"].to_numpy(), prim["t"].to_numpy()] == HIGH_BARS)) if len(prim) else np.zeros(0, bool)
    r10, _ = cell(ctx, prim, H_PRIMARY, PRIMARY_ENTRY, sub=strict)
    sec["S10"] = pack(r10)
    sig = runs["primary"]["sig"]
    um = np.asarray(runs["primary"]["unmatched"], dtype=np.int64)
    if len(um):
        ui = sig["i"].to_numpy()[um]; ut = sig["day"].to_numpy()[um]
        keep = ut <= T - 1 - H_PRIMARY
        ui, ut = ui[keep], ut[keep]
    else:
        ui = ut = np.zeros(0, np.int64)
    ou = outcomes(ctx["P"], ctx["B_O"], ctx["B_C"], ui, ut, H_PRIMARY, PRIMARY_ENTRY, ctx["glitch"], ctx["chg"])
    sec["S11"] = {**arm_ci(ou["excess"][ou["ok"]], ut[ou["ok"]], H_PRIMARY), "label": "descriptive, not a comparison",
                  "n_unmatched_rows": int(len(ut))}
    res["secondary"] = sec

    # ── data audit ──────────────────────────────────────────────────────────
    C = ctx["P"].C
    ts_ = po["t"][b]
    near = lambda ii: int(((C[ii, ts_] >= PRICE_FLOOR) & (C[ii, ts_] < NEAR_FLOOR_BAND * PRICE_FLOOR)).sum())
    res["data_audit"] = {
        "big_move": {"sig": int(po["sig"]["big"][b].sum()), "twin": int(po["twin"]["big"][b].sum()),
                     "n_pairs": int(b.sum())},
        "glitch_rows": res["sample"]["glitch_rows"],
        "near_floor": {"sig": near(po["i_s"][b]), "twin": near(po["i_p"][b]), "n_pairs": int(b.sum())},
    }
    res["anecdote"] = anecdote(ctx)

    # ── (f) cache universe (red days FROZEN) ────────────────────────────────
    if cache_frames is not None:
        excl = exclude_set()
        cf = {s: f for s, f in cache_frames.items() if s not in excl and f is not None and len(f)}
        Pc = build_panel(cf, cal)
        ctx_c = compute_ctx(Pc, ctx["B_O"], ctx["B_C"], None, red_frozen=ctx["red"], nonred_frozen=ctx["nonred"])
        frozen_ok = bool(np.array_equal(ctx_c["red"], ctx["red"]))
        mc = do_match(ctx_c, ctx_c["S2"], ctx_c["POOL"], ctx_c["red"], caliper=CALIPER_SD, match_vars=MATCH_VARS)
        rc, _ = cell(ctx_c, mc["pairs"], H_PRIMARY, PRIMARY_ENTRY)
        prim_syms = set(ctx["P"].syms)
        only = [k for k, s in enumerate(Pc.syms) if s not in prim_syms]
        tmx = np.zeros(T, bool)
        if T - 1 - H_PRIMARY >= FIRST_T:
            tmx[FIRST_T:T - H_PRIMARY] = True
        ended = [s for s in Pc.syms if is_ended(day_keys(cf[s])[-1], as_of)]
        res["stability"]["cache_all"] = {
            "lift": rc["lift"] if rc["n_pairs"] else None, "ci": rc["ci"], "n_pairs": rc["n_pairs"],
            "G_min": rc["G_min"], "balanced": mc["balance"]["balanced"], "red_frozen": frozen_ok,
            "names": len(Pc.syms), "cache_only_names": len(only),
            "cache_only_signals": int((ctx_c["S2"][only][:, ctx["red"] & tmx]).sum()) if only else 0,
            "ended_names": len(ended)}
        res["balance"]["cache"] = mc["balance"]
        del ctx_c, Pc, cf
    else:
        res["stability"]["cache_all"] = {"lift": None, "balanced": False, "skipped": True}


# ═════════════════════════════════════════════════════════════════════════════
# I/O
# ═════════════════════════════════════════════════════════════════════════════
def _sha256_file(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("features", "match", "all"), default="all")
    ap.add_argument("--out", required=True)
    ap.add_argument("--git-head", required=True)
    ap.add_argument("--expect", default=None)
    ap.add_argument("--no-cache-check", action="store_true")
    ap.add_argument("--force-window", action="store_true")
    ap.add_argument("--prereg-doc-sha256", default=None)
    a = ap.parse_args(argv)
    now = datetime.now(ET)
    if in_refusal_window(now) and not a.force_window:
        print("refused: %s ET is inside the %s-%s window (cache patches)" % (now.strftime("%a %H:%M"), *REFUSE_WINDOW_ET))
        return 5
    os.makedirs(a.out, exist_ok=True)
    as_of = as_of_day()
    excl = exclude_set()
    uni = U.load_universe(UNIVERSE_MODE)
    names = study_names(uni, excl)
    ulist = "\n".join(sorted(names))
    with open(os.path.join(a.out, "universe.txt"), "w") as fh:
        fh.write(ulist + "\n")
    print("AS_OF %s  universe %s: %d names, %d excluded" % (as_of, UNIVERSE_MODE, len(names), len(uni) - len(names)), flush=True)
    fr = load_frames(names + [BENCH, SPY_SYMBOL], as_of)
    bench_df, spy_df = fr.get(BENCH), fr.get(SPY_SYMBOL)
    frames = FrameSet({s: f for s, f in fr.items() if s not in (BENCH, SPY_SYMBOL) and s not in excl})
    frames.dup_day_keys = fr.dup_day_keys
    cache = None
    if a.stage == "all" and not a.no_cache_check:
        csyms = [s for s in ES.symbols_for("cache", FIRST_T + 2) if s not in excl]
        cache = load_frames(csyms, as_of)
        print("cache universe: %d names" % len(cache), flush=True)
    expect = None
    if a.expect:
        with open(a.expect) as fh:
            expect = json.load(fh)

    def verify():
        used = {**fr.digests, **(cache.digests if cache is not None else {})}
        again = load_frames(list(used), as_of)
        moved = sorted(s for s, d in used.items() if again.digests.get(s) != d)
        return {"as_of": as_of, "ok": not moved, "names_moved": moved[:50], "bars_differ": len(moved),
                "names_checked": len(used)}

    res = run_study(frames, bench_df, spy_df, as_of, cache_frames=cache, expect=expect, stage=a.stage,
                    verify_snapshot=verify if a.stage == "all" else None)
    meta = {"run_date": datetime.now(ET).strftime("%Y-%m-%d %H:%M ET"), "git_head": a.git_head,
            "script_sha256": _sha256_file(__file__), "universe_sha256": hashlib.sha256(ulist.encode()).hexdigest(),
            "prereg_doc_sha256": a.prereg_doc_sha256, "universe_names": len(names),
            "universe_excluded": len(uni) - len(names)}
    out = {"study": res["study"], "prereg_rev": res["prereg_rev"], **meta, **{k: v for k, v in res.items()
                                                                               if k not in ("study", "prereg_rev")}}
    fn = "green_on_red_measured.json" if a.stage == "all" else "green_on_red_%s.json" % a.stage
    with open(os.path.join(a.out, fn), "w") as fh:
        json.dump(ES._clean(out), fh, indent=1, sort_keys=False, default=str)
    print("wrote %s" % os.path.join(a.out, fn), flush=True)
    if a.stage == "all":
        if not res["snapshot"]["ok"]:
            return 4
        if res["pit"]["mismatch"] > 0:
            return 6
    elif res["pit"]["mismatch"] > 0:
        return 6
    return 0


if __name__ == "__main__":
    sys.exit(main())
