"""🌀 Raid-low entry — the STUDY (pre-registered 2026-09-24; nothing is wired).

THE ASK, verbatim:
  * Ajay 2026-09-17: "I am rely on manipulation.. I wanna use that as an entry
    the bottom of manipulation"
  * Ajay 2026-09-24, asked whether to measure it: "yes please build raid low"

The level is the RAID LOW — `raid_price`, the low that printed on the raid bar
of `supply_demand.amd.find_raids` — NOT `raid_level` (the swept base edge).
This measures HIS rule. It is a Rule #10 research step: no surface, lane,
gate, alert, sort or rule line changes because of anything in here.

PRE-REGISTRATION (frozen before the full run; the spec is
docs/supply_demand/amd_raid_low_study_2026_09_24.md):
  * Events: every bullish raid of the ONE raid engine, found by running
    `A.find_raids` on the frame TRUNCATED at each bar t >= WARMUP_PIT (a
    literal point-in-time walk; the raid is known only once bar t CLOSES).
  * PRIMARY rule E1: after the raid bar closes, rest a buy limit at the raid
    low for ORDER_WINDOW sessions, no cancel, filled only when a later bar
    trades BELOW it (an exact touch is not a fill); stop STOP_PCT% under the
    raid low; target the base top; exit HOLD sessions after the fill.
  * PRIMARY outcome: mean return per filled E1 trade, against ONE
    nearest-neighbour twin per event (an ordinary low near the floor of a
    live, unraided base on another name, same date; within CALIPER_SD pooled
    SD on rho, delta and nu; without replacement).
  * Verdict: `verdict()` below, mechanical. Needs the balance gate, the lift's
    CI above 0, the excess-over-RSP CI above 0, and every stability check.
  * AMENDMENT 1 (2026-09-25, before any outcome): see AMENDMENT_1 and the doc.
  * Entering at the raid low ON the raid bar is lookahead. It is printed once
    as a labelled HINDSIGHT diagnostic and never scored.

READ-ONLY: frames come from `sepa.prices.bulk_cached_frames` (one find, no
TTL, never a network call), capped at one AS_OF date for every name; bar
digests are compared at the end of the walk so a refresh that moves a walked
name's bars aborts the run (exit 4). Nothing here writes to any database.

RUN (throwaway container, never the live api container; outside RTH):
  OUT=<scratchpad>/raid_low_out
  mkdir -p $OUT
  docker cp cheetah-market-app-api-1:/root/.cheetah/universe $OUT/universe_snapshot
  docker run --rm -d --name raidlow-study --memory 1.5g --memory-swap 1.5g \
    --cpus 4 --network cheetah-market-app_default \
    -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah \
    -e TZ=America/New_York \
    -v <worktree>/backend/scripts/amd_raid_low_study.py:/study/amd_raid_low_study.py:ro \
    -v $OUT/universe_snapshot:/root/.cheetah/universe -v $OUT:/out \
    cheetah-api:latest sh -c 'cd /app && PYTHONPATH=/app python -u \
    /study/amd_raid_low_study.py --stage all --universe cache --procs 4 \
    --out /out/run --git-head PREREG_SHA > /out/run.log 2>&1'
  Resume = the same command (finished chunks are skipped, AS_OF is reused).
  Exit 3 = a worker died (rerun with --procs 3). Exit 4 = the snapshot moved
  (remove the chunks named in snapshot_fail.json, rerun).
  Smoke: add --features-only --stride 5 and --stage walk,sanity,match (the NN
  matcher needs the density; spec 3.10).
  SMOKE RUNS ARE NOT QUOTABLE (a stride sample, and no outcome is computed).

RESULTS: NOT RUN.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import resource
import sys
import time
import zlib
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from datetime import datetime, timedelta
from functools import partial
from typing import Optional

import numpy as np
import pandas as pd

from supply_demand import amd as A
from supply_demand import turning_bullish as TB
from supply_demand import alert_gates as AG
from supply_demand import patterns as PT
from trading import safety_floor as SF
from rotation import tracker as RT
from scripts import turning_bullish_amd_study as AS
from scripts import explosive_study as ES

log = logging.getLogger("scripts.amd_raid_low_study")

STUDY = "amd_raid_low_study_2026_09_24"

# ── constants reused BY NAME (none retyped) ─────────────────────────────────
WARMUP_PIT = A.MAX_BASE_BARS + A.MAX_RAID_AGE    # a base is never clipped from t >= this
NEED_BARS = WARMUP_PIT + 2
ORDER_WINDOW = TB.MAX_RAID_BARS_AGO              # how long the 🌀 board lists a raid
HOLD = AS.REACH_H                                # sessions after the fill
STOP_PCT = AG.STOP_BUFFER_PCT                    # stop = raid low less this %
STOP_ATR = PT.STOP_BUFFER_ATR                    # secondary S1
STOP_ATR_FLOOR_PCT = PT.MIN_STOP_BUFFER_PCT      # S1's floor
WINDOWS_SECONDARY = (AS.BARS_AGO_MAX, A.MAX_MARKUP_BARS)
BENCH = RT.BENCHMARK
PRICE_FLOOR = SF.MIN_SHARE_PRICE                 # secondary cut only

# ── STUDY-DESIGN constants (typed here; each is a design choice, not a rule) ─
STOP_ATR_WIDE = 1.0            # STUDY CONVENTION: S2 = the brief's "1 ATR" stop
RAID_FIELDS = ("date", "raid_level", "raid_price", "raid_close", "depth_pct",
               "vol_ratio", "base_lo", "base_hi", "base_bars", "base_date",
               "base_end_date")
CHAIN_FIELDS = ("sweep_seq", "resweep_of", "chain_root")
OPEN_BASE_FIELDS = ("lo", "hi", "bars", "date", "end_date")
K_PLACEBO = 5                  # v1 — SUPERSEDED by Amendment 1; balance_v1 record only
PLACEBO_LOWER_FRACTION = 1 / 3  # STUDY DESIGN: pool low sits in the base's lower third
DATE_WIDEN = 2                 # STUDY DESIGN: widen by +-2 sessions when a date is empty
DELTA_BINS = 3                 # v1 — SUPERSEDED by Amendment 1; balance_v1 record only
RHO_BINS = 5                   # v1 — SUPERSEDED by Amendment 1; balance_v1 record only
NU_BINS = 3                    # v1 — SUPERSEDED by Amendment 1; balance_v1 record only
BALANCE_SMD_MAX = 0.1          # STUDY DESIGN: the pre-outcome balance gate
MATCH_VARS = ("rho", "delta", "nu")   # AMENDMENT 1: matched AND gated covariates
CALIPER_SD = 0.4                      # AMENDMENT 1: per-covariate caliper, pooled SDs (spec 3.10 A1.1)
K_NN = 1                              # AMENDMENT 1: one nearest twin per event (no weights needed)
AMENDMENT_1 = ("2026-09-25, before any outcome: P1/P1s/cache-all = 1:1 nearest neighbour "
               "without replacement on z(rho, delta, nu), caliper CALIPER_SD pooled SD per "
               "covariate, same date then +-DATE_WIDEN only if needed, ties by (distance, eid, "
               "pid); gate |SMD| < BALANCE_SMD_MAX on rho, delta AND nu; stats stops before any "
               "outcome if imbalanced; headline pairs the matched E1 mean with P1.")
ENDED_GRACE_DAYS = 7           # STUDY DESIGN: calendar days before a name counts as ended
BOOT_B = 2000                  # STUDY DESIGN: bootstrap replicates
BOOT_SEED = 7                  # the prior harness's boot_diff default seed
SEED = 20260924                # STUDY DESIGN: placebo draws
MIN_MATCHED_SHARE = 0.90       # STUDY DESIGN: verdict criterion (g)
PIT_CHECK_NAMES = 50           # STUDY DESIGN: names re-walked full-frame in sanity
MDL_Z = 2.8                    # STUDY DESIGN: MDL = 2.8 x SD (80% power, 5% two-sided)
WHY = ("unfilled", "cancelled", "gap_stop", "stop", "target", "clock",
       "terminal", "gap_skip")

EVENT_ARMS = ("E1", "E1_S1", "E1_S2", "E1_X1", "E1_X2", "E1_X3", "E1_W10",
              "E1_W25", "E1_FT", "E1_CX", "E2", "E0", "E0N", "HS")
POOL_ARMS = ("P", "P_S1", "P_S2", "P_X2", "P_X3", "P_W10", "P_W25", "P_FT")
ARM_SUFFIX = ("_f", "_r", "_w", "_d", "_fd", "_xd", "_e")
SECONDARY = (("S1", "E1_S1", "P_S1"), ("S2", "E1_S2", "P_S2"), ("X1", "E1_X1", None),
             ("X2", "E1_X2", "P_X2"), ("X3", "E1_X3", "P_X3"), ("W10", "E1_W10", "P_W10"),
             ("W25", "E1_W25", "P_W25"), ("FT", "E1_FT", "P_FT"), ("CX", "E1_CX", None))

VERDICT_RULE_TEXT = (
    "invalid_snapshot if the snapshot verify failed. If NOT balanced (|SMD| of rho, "
    "delta and nu < BALANCE_SMD_MAX; Amendment 1) -> no_signal + imbalanced. inverted if balanced and "
    "CI_delta.hi < 0. edge only if balanced and ALL of: (a) CI_delta.lo > 0; (b) "
    "CI_xs.lo > 0; (c) delta > 0 in all four halves; (c2) delta > 0 in every "
    "drop-one-date-block run; (d) delta > 0 one-per-date AND one-per-symbol; (e) "
    "delta(P1s) > 0; (f) delta(cache-all) > 0; (g) matched share >= MIN_MATCHED_SHARE. "
    "Otherwise no_signal with tags relative_only ((a) passes, (b) fails), "
    "absolute_only ((b) passes, (a) fails), fragile ((a),(b) pass, any of "
    "(c),(c2),(d),(e),(f) fails), undermatched ((g) fails).")


def _flt(v) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return float("nan")
    return f if math.isfinite(f) else float("nan")


def _dint(s) -> int:
    """'YYYY-MM-DD' -> YYYYMMDD int (0 when unknown)."""
    if s is None:
        return 0
    s = str(s)[:10]
    try:
        return int(s.replace("-", ""))
    except ValueError:
        return 0


def _dstr(d: int) -> str:
    d = int(d)
    return "%04d-%02d-%02d" % (d // 10000, (d // 100) % 100, d % 100)


def _day_keys(df) -> list:
    idx = df.index
    if hasattr(idx, "strftime"):
        try:
            return list(idx.strftime("%Y-%m-%d"))
        except Exception:                                      # noqa: BLE001
            pass
    return [str(x)[:10] for x in idx]


# ═════════════════════════════════════════════════════════════════════════════
# FRAMES
# ═════════════════════════════════════════════════════════════════════════════
def cap_as_of(df, as_of: str):
    """Keep the rows whose YYYY-MM-DD is <= as_of (timestamps are mixed
    04:00 / 00:00 in the cache, so the day key is the only safe compare)."""
    if df is None or not len(df):
        return df
    keys = np.array(_day_keys(df))
    return df.loc[keys <= str(as_of)[:10]]


def bars_digest(df) -> str:
    """sha1 of the O/H/L/C/V float64 bytes."""
    arr = np.ascontiguousarray(
        df[["open", "high", "low", "close", "volume"]].to_numpy(dtype=np.float64))
    return hashlib.sha1(arr.tobytes()).hexdigest()


def is_ended(last_date: str, as_of: str) -> bool:
    last = datetime.strptime(str(last_date)[:10], "%Y-%m-%d")
    ref = datetime.strptime(str(as_of)[:10], "%Y-%m-%d")
    return last < ref - timedelta(days=ENDED_GRACE_DAYS)


def ohlc_ok(df) -> bool:
    a = df[["open", "high", "low", "close"]].to_numpy(dtype=float)
    return bool(np.isfinite(a).all() and (a > 0).all())


def load_closed(sym, as_of):
    """(frame, None) or (None, reason). bulk_cached_frames -> closed bars ->
    capped at AS_OF. Read-only: one find on price_cache, never a fetch."""
    from sepa import prices as PR
    from supply_demand import demand_reentry as DR
    s = str(sym).upper()
    df = PR.bulk_cached_frames([s]).get(s)
    if df is None or not len(df):
        return None, "no_doc"
    df = DR.split_today_partial(df)[0]
    df = cap_as_of(df, as_of)
    if df is None or len(df) < NEED_BARS:
        return None, "short"
    if not ohlc_ok(df):
        return None, "bad_ohlc"
    return df, None


# ═════════════════════════════════════════════════════════════════════════════
# ORDER SIMULATION (pure)
# ═════════════════════════════════════════════════════════════════════════════
def walk_exit(o, h, l, c, start: int, last: int, stop, target, *, terminal_ok: bool):
    """(idx, px, why) over bars start..last (last = the clock bar, may lie past
    the frame). Stop first (exit min(open, stop)), then target (exit
    max(open, target)); a same-bar tie is a STOP. No exit -> close[last]
    ('clock'), or close[n-1] ('terminal') when the frame ends first and
    terminal_ok; otherwise (None, None, None) — the trade is still open."""
    n = len(c)
    for k in range(start, min(last, n - 1) + 1):
        if stop is not None and l[k] <= stop:
            return k, float(min(o[k], stop)), "stop"
        if target is not None and h[k] >= target:
            return k, float(max(o[k], target)), "target"
    if last <= n - 1:
        return last, float(c[last]), "clock"
    if terminal_ok:
        return n - 1, float(c[n - 1]), "terminal"
    return None, None, None


def _res(filled, fill_idx, fill_px, exit_idx, exit_px, why, t, complete, terminal):
    ret = (exit_px / fill_px - 1.0) if (filled and exit_px is not None) else float("nan")
    return {"filled": bool(filled), "fill_idx": fill_idx, "fill_px": fill_px,
            "exit_idx": exit_idx, "exit_px": exit_px, "why": why, "ret": ret,
            "delay": (fill_idx - t) if fill_idx is not None else None,
            "complete": bool(complete), "terminal": bool(terminal),
            "evaluable": bool(complete or terminal)}


def simulate_limit(o, h, l, c, t: int, level: float, stop, target, *, window: int,
                   hold: int, ended: bool, strict: bool = True,
                   cancel_above: Optional[float] = None,
                   cancel_below: Optional[float] = None) -> dict:
    """A buy limit at `level` resting on bars t+1..min(t+window, n-1).

    Fill: the first bar whose low is BELOW the level (strict) or at/below it
    (strict=False); fill price min(open, level). Fill bar: open <= stop ->
    gap_stop with ret 0.0; else low <= stop -> stop at the stop; the target is
    never credited on the fill bar. Then walk_exit over j+1..j+hold. Cancels
    (secondary CX only) read the CLOSE after the fill check, while unfilled."""
    n = len(c)
    complete = t + window + hold <= n - 1
    terminal = (not complete) and bool(ended)
    last_w = min(t + window, n - 1)
    for j in range(t + 1, last_w + 1):
        hit = (l[j] < level) if strict else (l[j] <= level)
        if hit:
            px = float(min(o[j], level))
            if stop is not None and o[j] <= stop:
                return _res(True, j, px, j, px, "gap_stop", t, complete, terminal)
            if stop is not None and l[j] <= stop:
                return _res(True, j, px, j, float(stop), "stop", t, complete, terminal)
            k, xp, why = walk_exit(o, h, l, c, j + 1, j + hold, stop, target,
                                   terminal_ok=bool(ended))
            return _res(True, j, px, k, xp, why, t, complete, terminal)
        if ((cancel_above is not None and c[j] > cancel_above)
                or (cancel_below is not None and c[j] < cancel_below)):
            return _res(False, None, None, None, None, "cancelled", t, complete, terminal)
    return _res(False, None, None, None, None, "unfilled", t, complete, terminal)


def simulate_market(o, h, l, c, t: int, *, entry: str, stop, target, hold: int,
                    ended: bool) -> dict:
    """entry 'close' (close[t]), 'next_open' (open[t+1]; gap_skip when it is at
    or under the stop), 'hindsight_low' (low[t] ON the raid bar — lookahead,
    a diagnostic only). The walk covers t+1..t+hold, clock close[t+hold]."""
    n = len(c)
    complete = t + hold <= n - 1
    terminal = (not complete) and bool(ended)
    if entry == "close":
        px = float(c[t])
    elif entry == "hindsight_low":
        px = float(l[t])
    elif entry == "next_open":
        if t + 1 > n - 1:
            return _res(False, None, None, None, None, "unfilled", t, complete, terminal)
        if stop is not None and o[t + 1] <= stop:
            return _res(False, None, None, None, None, "gap_skip", t, complete, terminal)
        px = float(o[t + 1])
    else:
        raise ValueError("entry must be close|next_open|hindsight_low")
    k, xp, why = walk_exit(o, h, l, c, t + 1, t + hold, stop, target,
                           terminal_ok=bool(ended))
    fi = t + 1 if entry == "next_open" else t
    return _res(True, fi, px, k, xp, why, t, complete, terminal)


def _flat(prefix: str, r: Optional[dict], t: int) -> dict:
    if r is None:
        return {prefix + "_f": 0, prefix + "_r": float("nan"), prefix + "_w": -1,
                prefix + "_d": -1, prefix + "_fd": -1, prefix + "_xd": -1, prefix + "_e": 0}
    return {prefix + "_f": int(r["filled"]), prefix + "_r": float(r["ret"]),
            prefix + "_w": WHY.index(r["why"]) if r["why"] in WHY else -1,
            prefix + "_d": int(r["delay"]) if r["delay"] is not None else -1,
            prefix + "_fd": int(r["fill_idx"]) if r["fill_idx"] is not None else -1,
            prefix + "_xd": int(r["exit_idx"]) if r["exit_idx"] is not None else -1,
            prefix + "_e": int(r["evaluable"])}


def stop_s0(level: float) -> float:
    return level * (1.0 - STOP_PCT / 100.0)


def stop_s1(level: float, atr: float) -> float:
    a = atr if (atr is not None and math.isfinite(atr)) else 0.0
    return level - max(a * STOP_ATR, level * STOP_ATR_FLOOR_PCT / 100.0)


def stop_s2(level: float, atr: float) -> Optional[float]:
    if atr is None or not math.isfinite(atr):
        return None
    return level - STOP_ATR_WIDE * atr


def event_arms(o, h, l, c, atr, ev: dict, n: int, ended: bool) -> dict:
    """Every arm for one event. `atr` is the ATR-14 value at t."""
    t = int(ev["t"])
    L, E, T = float(ev["raid_price"]), float(ev["raid_level"]), float(ev["base_hi"])
    s0 = stop_s0(L)
    lim = partial(simulate_limit, o, h, l, c, t, hold=HOLD, ended=ended)
    s2 = stop_s2(L, atr)
    arms = {
        "E1": lim(L, s0, T, window=ORDER_WINDOW),
        "E1_S1": lim(L, stop_s1(L, atr), T, window=ORDER_WINDOW),
        "E1_S2": lim(L, s2, T, window=ORDER_WINDOW) if s2 is not None else None,
        "E1_X1": lim(L, s0, E, window=ORDER_WINDOW),
        "E1_X2": lim(L, s0, None, window=ORDER_WINDOW),
        "E1_X3": lim(L, None, None, window=ORDER_WINDOW),
        "E1_W10": lim(L, s0, T, window=WINDOWS_SECONDARY[0]),
        "E1_W25": lim(L, s0, T, window=WINDOWS_SECONDARY[1]),
        "E1_FT": lim(L, s0, T, window=ORDER_WINDOW, strict=False),
        "E1_CX": lim(L, s0, T, window=ORDER_WINDOW, cancel_above=T, cancel_below=E),
        "E2": lim(E, s0, T, window=ORDER_WINDOW),
        "E0": simulate_market(o, h, l, c, t, entry="close", stop=s0, target=T,
                              hold=HOLD, ended=ended),
        "E0N": simulate_market(o, h, l, c, t, entry="next_open", stop=s0, target=T,
                               hold=HOLD, ended=ended),
        "HS": simulate_market(o, h, l, c, t, entry="hindsight_low", stop=s0, target=T,
                              hold=HOLD, ended=ended),
    }
    out = {}
    for k in EVENT_ARMS:
        out.update(_flat(k, arms[k], t))
    return out


def pool_arms(o, h, l, c, atr, pr: dict, n: int, ended: bool) -> dict:
    """The placebo's arms: IDENTICAL mechanics to E1 at L' = low_t, target the
    open base's top. No cancel, strict fill."""
    t = int(pr["t"])
    L, T = float(pr["level"]), float(pr["ob_hi"])
    s0 = stop_s0(L)
    lim = partial(simulate_limit, o, h, l, c, t, hold=HOLD, ended=ended)
    s2 = stop_s2(L, atr)
    arms = {
        "P": lim(L, s0, T, window=ORDER_WINDOW),
        "P_S1": lim(L, stop_s1(L, atr), T, window=ORDER_WINDOW),
        "P_S2": lim(L, s2, T, window=ORDER_WINDOW) if s2 is not None else None,
        "P_X2": lim(L, s0, None, window=ORDER_WINDOW),
        "P_X3": lim(L, None, None, window=ORDER_WINDOW),
        "P_W10": lim(L, s0, T, window=WINDOWS_SECONDARY[0]),
        "P_W25": lim(L, s0, T, window=WINDOWS_SECONDARY[1]),
        "P_FT": lim(L, s0, T, window=ORDER_WINDOW, strict=False),
    }
    out = {}
    for k in POOL_ARMS:
        out.update(_flat(k, arms[k], t))
    return out


# ═════════════════════════════════════════════════════════════════════════════
# THE POINT-IN-TIME WALK (pure)
# ═════════════════════════════════════════════════════════════════════════════
def pit_walk(df, *, warmup: int = WARMUP_PIT):
    """(events, pool). At every t >= warmup the ONE raid engine runs on
    df.iloc[:t+1] — the frame ENDS at bar t. An event is a raid whose bar is t
    (rows[-1] is the latest raid). A pool row is a bar with no raid, no base
    broken by it, a live open base holding the close, and the low in the
    base's lower PLACEBO_LOWER_FRACTION. Outcome fields of the engine
    (outcome*, markup_bars_left) are never read."""
    n = len(df)
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    atr = ES.atr14_series(h, l, c)
    days = _day_keys(df)
    events, pool = [], []
    for t in range(warmup, n):
        R = A.find_raids(df.iloc[:t + 1], direction="bullish")
        rows = R.get("raids") or []
        a = _flt(atr[t])
        if rows and rows[-1]["idx"] == t:
            r = rows[-1]
            ev = {k: r.get(k) for k in RAID_FIELDS}
            L, E, C, T = (_flt(r.get("raid_price")), _flt(r.get("raid_level")),
                          _flt(r.get("raid_close")), _flt(r.get("base_hi")))
            B = _flt(r.get("base_lo"))
            ev.update({"t": t, "sweep_seq": int(r.get("sweep_seq") or 1),
                       "resweep_of": r.get("resweep_of"), "chain_root": r.get("chain_root"),
                       "atr": a,
                       "bad_event": not (L < E <= C),
                       "delta": (C - L) / C, "rho": (T - L) / L, "nu": a / C,
                       "depth": (B - L) / B * 100.0 if B else float("nan"),
                       "pos": (L - B) / (T - B) if T > B else float("nan")})
            events.append(ev)
            continue
        if R.get("last_break_base") is not None:
            continue
        ob = R.get("open_base")
        if not ob:
            continue
        lo, hi = _flt(ob.get("lo")), _flt(ob.get("hi"))
        if not (hi > lo):
            continue
        if not (lo <= c[t] <= hi):
            continue
        pos = (l[t] - lo) / (hi - lo)
        if pos > PLACEBO_LOWER_FRACTION:
            continue
        L, C = float(l[t]), float(c[t])
        pool.append({"t": t, "date": days[t], "level": L, "close": C,
                     "ob_lo": lo, "ob_hi": hi, "atr": a,
                     "delta": (C - L) / C, "rho": (hi - L) / L, "nu": a / C,
                     "depth": (lo - L) / lo * 100.0, "pos": pos})
    return events, pool


def raid_fields_equal(a: dict, b: dict) -> bool:
    for k in RAID_FIELDS:
        x, y = a.get(k), b.get(k)
        if isinstance(x, float) or isinstance(y, float):
            fx, fy = _flt(x), _flt(y)
            if not ((fx != fx and fy != fy) or fx == fy):
                return False
        elif x != y:
            return False
    return True


def open_base_equal(a: Optional[dict], b: Optional[dict]) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return all(a.get(k) == b.get(k) for k in OPEN_BASE_FIELDS)


def history_check(df, t: int, *, warmup: int = WARMUP_PIT) -> dict:
    """The raid at t read on the prefix frame vs on the last warmup+1 bars:
    RAID_FIELDS and open_base must match; chain fields are only COUNTED."""
    P = A.find_raids(df.iloc[:t + 1], direction="bullish")
    S = A.find_raids(df.iloc[max(0, t - warmup):t + 1], direction="bullish")
    pr, sr = P.get("raids") or [], S.get("raids") or []
    p_ev = bool(pr) and pr[-1]["idx"] == t
    s_ev = bool(sr) and sr[-1]["idx"] == t - max(0, t - warmup)
    if p_ev != s_ev:
        return {"match": False, "open_base_match": open_base_equal(P.get("open_base"), S.get("open_base")),
                "chain_diff": False}
    if not p_ev:
        return {"match": True, "open_base_match": open_base_equal(P.get("open_base"), S.get("open_base")),
                "chain_diff": False}
    a, b = pr[-1], sr[-1]
    return {"match": raid_fields_equal(a, b),
            "open_base_match": open_base_equal(P.get("open_base"), S.get("open_base")),
            "chain_diff": any(a.get(k) != b.get(k) for k in CHAIN_FIELDS)}


def pit_check(df, ev_t: list, ev_rows: list) -> dict:
    """Full-frame find_raids vs the stored point-in-time events of one name:
    the idx set (>= WARMUP_PIT), RAID_FIELDS, and chain differences."""
    R = A.find_raids(df, direction="bullish")
    full = {r["idx"]: r for r in (R.get("raids") or []) if r["idx"] >= WARMUP_PIT}
    got = {int(t): r for t, r in zip(ev_t, ev_rows)}
    set_mis = len(set(full) ^ set(got))
    attr = chain = 0
    for t in set(full) & set(got):
        if not raid_fields_equal(full[t], got[t]):
            attr += 1
        if int(full[t].get("sweep_seq") or 1) != int(got[t].get("sweep_seq") or 1):
            chain += 1
    return {"set_mismatch": set_mis, "attr_mismatch": attr, "chain_diff": chain,
            "n_full": len(full), "n_pit": len(got)}


# ═════════════════════════════════════════════════════════════════════════════
# MATCHING (pure)
# ═════════════════════════════════════════════════════════════════════════════
def bin_edges(ev_df) -> dict:
    """Quantile edges from the EVENTS only (evaluable in_study), fixed before
    any outcome exists."""
    def q(x, k):
        x = np.asarray(x, dtype=float)
        x = x[np.isfinite(x)]
        return [float(v) for v in np.quantile(x, [i / k for i in range(1, k)])]
    return {"delta": q(ev_df["delta"], DELTA_BINS), "rho": q(ev_df["rho"], RHO_BINS),
            "nu": q(ev_df["nu"], NU_BINS)}


def cell_of(delta, rho, nu, edges) -> np.ndarray:
    """0..44; -1 when any input is NaN. Values past the event range fall into
    the open-ended edge bins."""
    d = np.asarray(delta, dtype=float)
    r = np.asarray(rho, dtype=float)
    u = np.asarray(nu, dtype=float)
    bd = np.searchsorted(edges["delta"], d, side="right")
    br = np.searchsorted(edges["rho"], r, side="right")
    bu = np.searchsorted(edges["nu"], u, side="right")
    cell = (RHO_BINS * NU_BINS) * bd + NU_BINS * br + bu
    bad = ~(np.isfinite(d) & np.isfinite(r) & np.isfinite(u))
    return np.where(bad, -1, cell).astype(np.int16)


def draw_matched(ev_df, pool_df, *, k: int, seed: int, same_symbol: bool,
                 widen: int, gap: int) -> pd.DataFrame:
    """Placebo draws. ev_df / pool_df columns: eid|pid, sym, date, dpos, cell, t.

    same_symbol=False (P1): same date, same cell, another symbol; widen to
    |dpos diff| <= widen when the date is empty ('widened'); else unmatched.
    same_symbol=True (P1s): same symbol, same cell, |t' - t| > gap, any date.
    K draws without replacement when >= K candidates, with replacement when
    1..K-1. Deterministic in eid order. Unmatched eids in .attrs."""
    rng = np.random.default_rng(seed)
    p_sym = pool_df["sym"].to_numpy()
    p_cell = pool_df["cell"].to_numpy()
    p_pid = pool_df["pid"].to_numpy()
    p_t = pool_df["t"].to_numpy()
    groups: dict = {}
    if same_symbol:
        keys = zip(p_sym, p_cell)
    else:
        keys = zip(pool_df["dpos"].to_numpy(), p_cell)
    for i, key in enumerate(keys):
        groups.setdefault((key[0], int(key[1])), []).append(i)
    groups = {kk: np.asarray(v, dtype=np.int64) for kk, v in groups.items()}
    out_e, out_p, out_k, unmatched = [], [], [], []
    ev = ev_df.sort_values("eid")
    for eid, sym, dpos, cell, t in zip(ev["eid"].to_numpy(), ev["sym"].to_numpy(),
                                       ev["dpos"].to_numpy(), ev["cell"].to_numpy(),
                                       ev["t"].to_numpy()):
        cell = int(cell)
        if cell < 0:
            unmatched.append(int(eid))
            continue
        kind = "exact"
        if same_symbol:
            idx = groups.get((sym, cell), np.empty(0, dtype=np.int64))
            idx = idx[np.abs(p_t[idx] - t) > gap]
        else:
            idx = groups.get((dpos, cell), np.empty(0, dtype=np.int64))
            idx = idx[p_sym[idx] != sym]
            if idx.size == 0 and widen > 0:
                parts = [groups.get((dpos + dd, cell), np.empty(0, dtype=np.int64))
                         for dd in range(-widen, widen + 1)]
                idx = np.concatenate(parts)
                idx = idx[p_sym[idx] != sym]
                kind = "widened"
        if idx.size == 0:
            unmatched.append(int(eid))
            continue
        pick = rng.choice(idx, size=k, replace=idx.size < k)
        out_e.extend([int(eid)] * k)
        out_p.extend(int(p_pid[i]) for i in pick)
        out_k.extend([kind] * k)
    res = pd.DataFrame({"eid": np.asarray(out_e, dtype=np.int64),
                        "pid": np.asarray(out_p, dtype=np.int64),
                        "kind": np.asarray(out_k, dtype=object)})
    res.attrs["unmatched"] = unmatched
    return res


def match_sd(ev_df, pl_df) -> np.ndarray:
    """Pooled SD per MATCH_VARS over the whole matching population (Amendment 1):
    sqrt((var_ev + var_pool)/2), ddof=1, finite values only. Computed once, before any draw."""
    out = []
    for v in MATCH_VARS:
        a = np.asarray(ev_df[v], dtype=float); b = np.asarray(pl_df[v], dtype=float)
        a, b = a[np.isfinite(a)], b[np.isfinite(b)]
        out.append(math.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2.0) if a.size > 1 and b.size > 1 else float("nan"))
    return np.asarray(out, dtype=float)


def match_nn(ev_df, pl_df, s, *, k: int = K_NN, caliper: float = CALIPER_SD,
             widen: int = DATE_WIDEN, same_symbol: bool = False,
             gap: int = ORDER_WINDOW + HOLD) -> pd.DataFrame:
    """Amendment 1 matcher. ev_df: eid, sym, dpos, t + MATCH_VARS; pl_df: pid, sym, dpos,
    t + MATCH_VARS. Admissible pair: |z_e - z_p| <= caliper on EVERY covariate (z = x/s),
    another symbol (P1) or the same symbol with |t'-t| > gap (P1s). Greedy by Euclidean
    z-distance, ties by (eid, pid); a pool row serves at most one event. Exact dpos first;
    events with no draw then try |dpos diff| <= widen ('widened'). Deterministic.
    Returns eid, pid, kind, dist; .attrs['unmatched'] = sorted eids with no draw."""
    s = np.asarray(s, dtype=float)
    Ze = ev_df[list(MATCH_VARS)].to_numpy(dtype=float) / s
    Zp = pl_df[list(MATCH_VARS)].to_numpy(dtype=float) / s
    e_id = ev_df["eid"].to_numpy(dtype=np.int64); p_id = pl_df["pid"].to_numpy(dtype=np.int64)
    e_sym, p_sym = ev_df["sym"].to_numpy(), pl_df["sym"].to_numpy()
    e_dp = ev_df["dpos"].to_numpy(dtype=np.int64); p_dp = pl_df["dpos"].to_numpy(dtype=np.int64)
    e_t = ev_df["t"].to_numpy(dtype=np.int64); p_t = pl_df["t"].to_numpy(dtype=np.int64)
    ok_e, ok_p = np.isfinite(Ze).all(axis=1), np.isfinite(Zp).all(axis=1)
    used = np.zeros(len(p_id), dtype=bool)
    nd = np.zeros(len(e_id), dtype=np.int64)
    key = p_sym if same_symbol else p_dp
    groups: dict = {}
    for j in np.flatnonzero(ok_p):
        groups.setdefault(key[j], []).append(j)
    groups = {g: np.asarray(v, dtype=np.int64) for g, v in groups.items()}
    empty = np.empty(0, dtype=np.int64)
    rows = []

    def cands(i, span):
        if same_symbol:
            c = groups.get(e_sym[i], empty)
            return c[np.abs(p_t[c] - e_t[i]) > gap]
        c = np.concatenate([groups.get(e_dp[i] + x, empty) for x in span])
        return c[p_sym[c] != e_sym[i]]

    def assign(ev_rows, span, kind):
        E, P, D = [], [], []
        for i in ev_rows:
            c = cands(i, span)
            c = c[~used[c]]
            dz = Zp[c] - Ze[i]
            inside = (np.abs(dz) <= caliper).all(axis=1)
            c, dz = c[inside], dz[inside]
            E.append(np.full(c.size, i, dtype=np.int64)); P.append(c)
            D.append(np.sqrt((dz ** 2).sum(axis=1)))
        if not E:
            return
        E, P, D = np.concatenate(E), np.concatenate(P), np.concatenate(D)
        o = np.lexsort((p_id[P], e_id[E], D))
        E, P, D = E[o], P[o], D[o]
        for r in range(k):
            for i, j, d in zip(E, P, D):
                if nd[i] == r and not used[j]:
                    used[j] = True
                    nd[i] += 1
                    rows.append((int(e_id[i]), int(p_id[j]), kind, float(d)))

    live = [i for i in np.argsort(e_id, kind="stable") if ok_e[i]]
    if same_symbol:
        assign(live, [0], "exact")
    else:
        by_day: dict = {}
        for i in live:
            by_day.setdefault(int(e_dp[i]), []).append(i)
        for d in sorted(by_day):
            assign(by_day[d], [0], "exact")
    if not same_symbol and widen > 0:
        assign([i for i in live if nd[i] == 0], list(range(-widen, widen + 1)), "widened")
    res = pd.DataFrame(rows, columns=["eid", "pid", "kind", "dist"])
    res.attrs["unmatched"] = sorted(int(e_id[i]) for i in range(len(e_id)) if nd[i] == 0)
    return res


def balance_gate(bal: dict) -> bool:
    """Amendment 1: |SMD| < BALANCE_SMD_MAX on EVERY MATCH_VARS covariate; NaN fails."""
    for v in MATCH_VARS:
        x = _flt(bal.get("smd_" + v))
        if not (x == x and abs(x) < BALANCE_SMD_MAX):
            return False
    return True


def date_split(dates) -> int:
    """First H2 date: H1 = the first floor(D/2) UNIQUE dates (explosive_study split)."""
    ds = np.unique(np.asarray(dates))
    return int(ds[len(ds) // 2]) if len(ds) else 0


def smd(a, b) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if a.size < 2 or b.size < 2:
        return float("nan")
    den = math.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2.0)
    diff = float(a.mean() - b.mean())
    if den == 0:
        return 0.0 if diff == 0 else float("inf") * (1 if diff > 0 else -1)
    return diff / den


def bench_returns(fill_dates, exit_dates, bench_df) -> np.ndarray:
    """close[exit_date] / open[fill_date] - 1 of the benchmark, keyed by
    YYYYMMDD ints; NaN when either date is missing."""
    keys = [_dint(k) for k in _day_keys(bench_df)]
    op = dict(zip(keys, bench_df["open"].to_numpy(dtype=float)))
    cl = dict(zip(keys, bench_df["close"].to_numpy(dtype=float)))
    out = np.full(len(fill_dates), np.nan)
    for i, (fd, xd) in enumerate(zip(fill_dates, exit_dates)):
        o_ = op.get(int(fd))
        c_ = cl.get(int(xd))
        if o_ is not None and c_ is not None and o_ > 0:
            out[i] = c_ / o_ - 1.0
    return out


# ═════════════════════════════════════════════════════════════════════════════
# STATISTICS (pure)
# ═════════════════════════════════════════════════════════════════════════════
def delta_point(vals, is_ev, is_draw, filled, sel=None) -> float:
    m = np.ones(len(vals), dtype=bool) if sel is None else sel
    a = vals[is_ev & filled & m]
    b = vals[is_draw & filled & m]
    if a.size == 0 or b.size == 0:
        return float("nan")
    return float(np.mean(a) - np.mean(b))


def drop_one_block(vals, is_ev, is_draw, filled, block) -> dict:
    """Delta with each date block removed in turn."""
    per = {}
    for b in np.unique(block[(is_ev | is_draw) & filled]):
        per[int(b)] = delta_point(vals, is_ev, is_draw, filled, block != b)
    finite = {k: v for k, v in per.items() if v == v}
    if not finite:
        return {"per_block": per, "min": float("nan"), "argmin": None}
    arg = min(finite, key=finite.get)
    return {"per_block": per, "min": finite[arg], "argmin": arg}


def boot_mean(vals, mask, groups, B: Optional[int] = None, seed: int = BOOT_SEED) -> dict:
    """Cluster bootstrap of mean(vals[mask]) (clusters = groups)."""
    B = BOOT_B if B is None else B
    v = np.asarray(vals, dtype=float)[mask]
    g = np.asarray(groups)[mask]
    ok = np.isfinite(v)
    v, g = v[ok], g[ok]
    if v.size < 2:
        return {"mean": float(v.mean()) if v.size else float("nan"),
                "ci": [float("nan"), float("nan")], "reps": 0, "n": int(v.size)}
    cl = AS._clusters(g)
    rng = np.random.default_rng(seed)
    ncl = len(cl)
    sums = np.array([v[c].sum() for c in cl])
    cnts = np.array([len(c) for c in cl])
    reps = []
    for _ in range(B):
        pick = rng.integers(0, ncl, ncl)
        nn = cnts[pick].sum()
        if nn:
            reps.append(sums[pick].sum() / nn)
    return {"mean": float(v.mean()),
            "ci": [float(np.percentile(reps, 2.5)), float(np.percentile(reps, 97.5))],
            "reps": len(reps), "n": int(v.size)}


def boot_delta(vals, ma, mb, groups, B: Optional[int] = None, seed: int = BOOT_SEED) -> dict:
    """AS.boot_diff on the rows of either arm only (a cluster with no row in
    either arm adds nothing to either mean)."""
    B = BOOT_B if B is None else B
    keep = ma | mb
    if ma.sum() < 5 or mb.sum() < 5:
        return {"a": float("nan"), "b": float("nan"), "diff": float("nan"),
                "diff_ci": (float("nan"), float("nan")), "reps": 0}
    return AS.boot_diff(np.asarray(vals, dtype=float)[keep], ma[keep], mb[keep],
                        np.asarray(groups)[keep], B=B, seed=seed)


def ci_width_sd(ci) -> float:
    """SD read off a 95% percentile interval (width / 3.92): boot_diff returns
    the interval, not its draws."""
    lo, hi = ci
    return float((hi - lo) / 3.92) if (lo == lo and hi == hi) else float("nan")


def _gt0(x) -> bool:
    try:
        return x is not None and float(x) > 0
    except (TypeError, ValueError):
        return False


def verdict(res: dict) -> dict:
    """The pre-registered verdict (VERDICT_RULE_TEXT). Mechanical; the printed
    status is this function's output."""
    snap = res.get("snapshot") or {}
    if not snap.get("ok"):
        return {"status": "invalid_snapshot", "tags": [], "failed": ["snapshot"]}
    pr = res.get("primary") or {}
    st = res.get("stability") or {}
    dci = pr.get("diff_ci") or [float("nan"), float("nan")]
    xci = pr.get("xs_ci") or [float("nan"), float("nan")]
    per_block = ((st.get("drop_one_block") or {}).get("per_block") or {})
    crit = {
        "a": _gt0(dci[0]),
        "b": _gt0(xci[0]),
        "c": all(_gt0(st.get(k)) for k in ("date_h1", "date_h2", "sym_p0", "sym_p1")),
        "c2": bool(per_block) and all(_gt0(v) for v in per_block.values()),
        "d": _gt0(st.get("one_per_date")) and _gt0(st.get("one_per_symbol")),
        "e": _gt0(st.get("same_symbol")),
        "f": _gt0(((res.get("survivorship") or {}).get("cache_all") or {}).get("diff")),
        "g": (pr.get("matched_share") is not None
              and float(pr.get("matched_share")) >= MIN_MATCHED_SHARE),
    }
    failed = [k for k, v in crit.items() if not v]
    if not (res.get("balance") or {}).get("balanced"):
        return {"status": "no_signal", "tags": ["imbalanced"], "failed": ["balance"] + failed}
    try:
        hi = float(dci[1])
    except (TypeError, ValueError):
        hi = float("nan")
    if hi == hi and hi < 0:
        return {"status": "inverted", "tags": [], "failed": failed}
    if not failed:
        return {"status": "edge", "tags": [], "failed": []}
    tags = []
    if crit["a"] and not crit["b"]:
        tags.append("relative_only")
    if crit["b"] and not crit["a"]:
        tags.append("absolute_only")
    if crit["a"] and crit["b"] and not all(crit[k] for k in ("c", "c2", "d", "e", "f")):
        tags.append("fragile")
    if not crit["g"]:
        tags.append("undermatched")
    return {"status": "no_signal", "tags": tags, "failed": failed}


def headline(res: dict) -> str:
    """The one sentence built for him; the window and the stop come from the
    constants. Amendment 1 (A1.4): the per-fill number beside the placebo is the
    MATCHED E1 mean, so e1 - p1 == lift; the all-fills E1 mean has its own clause."""
    pr = res.get("primary") or {}
    fl = res.get("fills") or {}
    v = res.get("verdict") or {}

    def pc(x):
        x = _flt(x)
        return x * 100.0 if x == x else float("nan")
    dci = pr.get("diff_ci") or [float("nan")] * 2
    xci = pr.get("xs_ci") or [float("nan")] * 2
    status = str(v.get("status") or "not_run").upper()
    if v.get("tags"):
        status += " (" + ", ".join(v["tags"]) + ")"
    return ("🌀 Raid-low entry (buy limit at the raid low for %d sessions, filled only "
            "when price trades below it, stop %s%% under): %s — matched raids %+.2f%% per "
            "fill vs %+.2f%% at an ordinary base low · lift %+.2fpp [%+.2f, %+.2f] · all "
            "raid fills %+.2f%% · vs RSP %+.2fpp [%+.2f, %+.2f] · filled %.0f%% vs %.0f%% · "
            "stopped %.0f%%"
            % (ORDER_WINDOW, STOP_PCT, status, pc(pr.get("e1_mean_matched")), pc(pr.get("p1_mean")),
               pc(pr.get("diff")), pc(dci[0]), pc(dci[1]), pc(pr.get("e1_mean_all")),
               pc(pr.get("xs_mean")),
               pc(xci[0]), pc(xci[1]), pc((fl.get("E1") or {}).get("rate")),
               pc((fl.get("P1") or {}).get("rate")), pc(pr.get("stop_rate"))))


# ═════════════════════════════════════════════════════════════════════════════
# PROCESSES
# ═════════════════════════════════════════════════════════════════════════════
def peak_rss_mb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return float(r) / (1024.0 * 1024.0) if sys.platform == "darwin" else float(r) / 1024.0


def run_pool(fn, items, procs: int, *, executor_cls=ProcessPoolExecutor,
             initializer=None):
    """Results of fn over items, in order. A dead worker raises
    BrokenProcessPool here (a multiprocessing.Pool would hang forever): log it
    and exit 3 — never a silent partial result."""
    try:
        with executor_cls(max_workers=procs, initializer=initializer) as ex:
            for r in ex.map(fn, items):
                yield r
    except BrokenProcessPool as exc:
        log.error("a worker died (likely OOM inside the container): %s", exc)
        print("FATAL: a worker process died (BrokenProcessPool) — rerun with fewer --procs",
              flush=True)
        raise SystemExit(3)


def _ev_columns(events):
    cols = {
        "t": np.array([e["t"] for e in events], dtype=np.int32),
        "date": np.array([_dint(e["date"]) for e in events], dtype=np.int32),
        "L": np.array([_flt(e["raid_price"]) for e in events]),
        "E": np.array([_flt(e["raid_level"]) for e in events]),
        "C": np.array([_flt(e["raid_close"]) for e in events]),
        "base_lo": np.array([_flt(e["base_lo"]) for e in events]),
        "base_hi": np.array([_flt(e["base_hi"]) for e in events]),
        "base_bars": np.array([int(e["base_bars"] or 0) for e in events], dtype=np.int16),
        "depth_pct": np.array([_flt(e["depth_pct"]) for e in events]),
        "vol_ratio": np.array([_flt(e["vol_ratio"]) for e in events]),
        "base_date": np.array([_dint(e["base_date"]) for e in events], dtype=np.int32),
        "base_end_date": np.array([_dint(e["base_end_date"]) for e in events], dtype=np.int32),
        "sweep_seq": np.array([e["sweep_seq"] for e in events], dtype=np.int16),
        "atr": np.array([e["atr"] for e in events]),
        "delta": np.array([e["delta"] for e in events]),
        "rho": np.array([e["rho"] for e in events]),
        "nu": np.array([e["nu"] for e in events]),
        "depth": np.array([e["depth"] for e in events]),
        "pos": np.array([e["pos"] for e in events]),
        "bad_event": np.array([bool(e["bad_event"]) for e in events], dtype=bool),
    }
    return cols


def _pl_columns(pool):
    f32 = np.float32
    return {
        "t": np.array([p["t"] for p in pool], dtype=np.int32),
        "date": np.array([_dint(p["date"]) for p in pool], dtype=np.int32),
        "L": np.array([p["level"] for p in pool], dtype=f32),
        "C": np.array([p["close"] for p in pool], dtype=f32),
        "ob_lo": np.array([p["ob_lo"] for p in pool], dtype=f32),
        "ob_hi": np.array([p["ob_hi"] for p in pool], dtype=f32),
        "atr": np.array([p["atr"] for p in pool], dtype=f32),
        "delta": np.array([p["delta"] for p in pool], dtype=f32),
        "rho": np.array([p["rho"] for p in pool], dtype=f32),
        "nu": np.array([p["nu"] for p in pool], dtype=f32),
        "depth": np.array([p["depth"] for p in pool], dtype=f32),
        "pos": np.array([p["pos"] for p in pool], dtype=f32),
    }


def _flags(t_arr, n, ended, window=ORDER_WINDOW):
    complete = t_arr + window + HOLD <= n - 1
    terminal = (~complete) & bool(ended)
    return complete, terminal, complete | terminal


def _arm_columns(rows, names, dates_int):
    out = {}
    for a in names:
        for s in ARM_SUFFIX:
            key = a + s
            vals = [r[key] for r in rows]
            if s == "_r":
                out[key] = np.array(vals, dtype=np.float32)
            elif s in ("_fd", "_xd"):
                out[key] = np.array([dates_int[v] if v >= 0 else 0 for v in vals], dtype=np.int32)
            elif s == "_d":
                out[key] = np.array(vals, dtype=np.int16)
            else:
                out[key] = np.array(vals, dtype=np.int8)
    return out


def walk_symbol(sym, as_of, features_only):
    """(sym, err, payload). payload = column arrays + meta."""
    t0 = time.time()
    try:
        df, reason = load_closed(sym, as_of)
    except Exception as exc:                                   # noqa: BLE001
        return sym, "load_error:%s" % type(exc).__name__, None
    if df is None:
        return sym, reason, None
    try:
        events, pool = pit_walk(df)
    except Exception as exc:                                   # noqa: BLE001
        return sym, "walk_error:%s" % type(exc).__name__, None
    n = len(df)
    days = _day_keys(df)
    dates_int = np.array([_dint(d) for d in days], dtype=np.int32)
    ended = is_ended(days[-1], as_of)
    ev = _ev_columns(events)
    pl = _pl_columns(pool)
    for cols in (ev, pl):
        cmp_, term, evl = _flags(cols["t"].astype(np.int64), n, ended)
        cols["complete"], cols["terminal"], cols["evaluable"] = cmp_, term, evl
    payload = {"ev": ev, "pl": pl, "ev_arms": None, "pl_arms": None}
    if not features_only:
        o = df["open"].to_numpy(dtype=float)
        h = df["high"].to_numpy(dtype=float)
        l = df["low"].to_numpy(dtype=float)
        c = df["close"].to_numpy(dtype=float)
        er = [event_arms(o, h, l, c, e["atr"], e, n, ended) for e in events]
        pr = [pool_arms(o, h, l, c, p["atr"], p, n, ended) for p in pool]
        payload["ev_arms"] = _arm_columns(er, EVENT_ARMS, dates_int)
        payload["pl_arms"] = _arm_columns(pr, POOL_ARMS, dates_int)
    payload["meta"] = {"n": n, "first": int(dates_int[0]), "last": int(dates_int[-1]),
                       "ended": bool(ended), "digest": bars_digest(df),
                       "rss_mb": peak_rss_mb(), "wall": time.time() - t0}
    return sym, None, payload


# ═════════════════════════════════════════════════════════════════════════════
# CHUNK FILES
# ═════════════════════════════════════════════════════════════════════════════
def _chunk_path(out, ci, kind):
    return os.path.join(out, "walk", "chunk_%04d_%s.npz" % (ci, kind))


def _write_chunk(out, ci, results, in_study_set, features_only):
    names, meta, skipped = [], [], {}
    ev_parts, pl_parts, eva_parts, pla_parts = [], [], [], []
    for sym, err, p in results:
        if err:
            skipped[sym] = err
            continue
        sid = len(names)
        names.append(sym)
        meta.append(p["meta"])
        ev_parts.append((sid, p["ev"], p["ev_arms"]))
        pl_parts.append((sid, p["pl"], p["pl_arms"]))

    def cat(parts, which):
        acc = {}
        sids = []
        for sid, cols, arms in parts:
            src = cols if which == "feat" else arms
            if src is None:
                continue
            m = len(cols["t"])
            sids.append(np.full(m, sid, dtype=np.int32))
            for k in src:
                acc.setdefault(k, []).append(src[k])
        res = {k: np.concatenate(v) for k, v in acc.items()}
        res["sid"] = np.concatenate(sids) if sids else np.empty(0, dtype=np.int32)
        return res

    feat = {"names": np.array(names, dtype=str),
            "in_study": np.array([s in in_study_set for s in names], dtype=bool),
            "m_n": np.array([m["n"] for m in meta], dtype=np.int32),
            "m_first": np.array([m["first"] for m in meta], dtype=np.int32),
            "m_last": np.array([m["last"] for m in meta], dtype=np.int32),
            "m_ended": np.array([m["ended"] for m in meta], dtype=bool),
            "m_digest": np.array([m["digest"] for m in meta], dtype=str),
            "m_rss": np.array([m["rss_mb"] for m in meta], dtype=float),
            "m_wall": np.array([m["wall"] for m in meta], dtype=float),
            "skipped": np.array(json.dumps(skipped))}
    for k, v in cat(ev_parts, "feat").items():
        feat["ev_" + k] = v
    for k, v in cat(pl_parts, "feat").items():
        feat["pl_" + k] = v
    os.makedirs(os.path.join(out, "walk"), exist_ok=True)
    np.savez_compressed(_chunk_path(out, ci, "feat"), **feat)
    if not features_only:
        arms = {}
        for k, v in cat(ev_parts, "arms").items():
            arms["ev_" + k] = v
        for k, v in cat(pl_parts, "arms").items():
            arms["pl_" + k] = v
        np.savez_compressed(_chunk_path(out, ci, "arms"), **arms)
    return names, skipped, meta


def load_chunks(out, kind: str = "feat") -> dict:
    """Every chunk of one kind concatenated, in chunk order. In a feat load
    `*_sid` becomes a global name id; an arms load carries no ids (its rows
    line up with the feat rows of the same chunks — `chunks` lists them)."""
    d = os.path.join(out, "walk")
    suffix = "_%s.npz" % kind
    files = sorted(f for f in os.listdir(d) if f.endswith(suffix)) if os.path.isdir(d) else []
    names, acc, skipped, chunk_of, chunks = [], {}, {}, [], []
    for f in files:
        ci = int(f.split("_")[1])
        chunks.append(ci)
        with np.load(os.path.join(d, f)) as z:
            off = len(names)
            if kind == "feat":
                cn = [str(x) for x in z["names"]]
                names.extend(cn)
                chunk_of.extend([ci] * len(cn))
                skipped.update(json.loads(str(z["skipped"])))
            for k in z.files:
                if k in ("names", "skipped"):
                    continue
                v = z[k]
                if k.endswith("_sid"):
                    if kind != "feat":
                        continue
                    v = v + off
                acc.setdefault(k, []).append(v)
    res = {k: np.concatenate(v) for k, v in acc.items()}
    res["names"] = np.array(names, dtype=str)
    res["skipped"] = skipped
    res["chunk_of"] = np.array(chunk_of, dtype=np.int32)
    res["chunks"] = chunks
    return res


# ═════════════════════════════════════════════════════════════════════════════
# STAGES
# ═════════════════════════════════════════════════════════════════════════════
def _json_dump(path, obj):
    with open(path, "w") as fh:
        json.dump(ES._clean(obj), fh, indent=1, sort_keys=True)


def _read_json(path, default=None):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def read_stamps(syms) -> dict:
    """{symbol: cached_at} — a projection-only find (read-only)."""
    from sepa import prices as PR
    coll = PR._get_mongo()
    if coll is None:
        raise RuntimeError("price_cache unavailable")
    out = {}
    syms = list(syms)
    for i in range(0, len(syms), 1000):
        for d in coll.find({"symbol": {"$in": syms[i:i + 1000]}},
                           {"symbol": 1, "cached_at": 1, "_id": 0}):
            out[str(d.get("symbol"))] = d.get("cached_at")
    return out


def bench_frame(as_of: Optional[str] = None):
    from sepa import prices as PR
    from supply_demand import demand_reentry as DR
    df = PR.bulk_cached_frames([BENCH]).get(BENCH)
    if df is None:
        raise RuntimeError("benchmark %s missing from price_cache" % BENCH)
    df = DR.split_today_partial(df)[0]
    return cap_as_of(df, as_of) if as_of else df


def _universe(a) -> list:
    if a.universe == "cache":
        return ES.symbols_for("cache", NEED_BARS, stride=a.stride, names=a.names)
    syms = sorted(dict.fromkeys(str(s).upper() for s in AS.study_universe()))
    if a.stride > 1:
        syms = syms[::a.stride]
    if a.names:
        syms = syms[:a.names]
    return syms


def stage_walk(a) -> None:
    out = a.out
    os.makedirs(os.path.join(out, "walk"), exist_ok=True)
    snap_p = os.path.join(out, "snapshot_t0.json")
    snap = _read_json(snap_p)
    if snap is None:
        syms = _universe(a)
        bdf = bench_frame()
        as_of = _day_keys(bdf)[-1]
        stamps = read_stamps(syms)
        study = sorted(dict.fromkeys(str(s).upper() for s in AS.study_universe()))
        with open(os.path.join(out, "in_study.txt"), "w") as fh:
            fh.write("\n".join(study) + "\n")
        snap = {"as_of": as_of, "stamps": stamps, "universe": a.universe,
                "stride": a.stride, "names_cap": a.names, "symbols": syms,
                "t0_max_cached_at": max([v for v in stamps.values() if v is not None] or [None]),
                "created": datetime.now().isoformat(timespec="seconds"),
                "features_only": bool(a.features_only)}
        _json_dump(snap_p, snap)
        print("snapshot_t0 written: AS_OF %s, %d names" % (as_of, len(syms)), flush=True)
    else:
        print("snapshot_t0 reused: AS_OF %s, %d names" % (snap["as_of"], len(snap["symbols"])),
              flush=True)
    as_of, syms = snap["as_of"], snap["symbols"]
    with open(os.path.join(out, "in_study.txt")) as fh:
        study = set(x.strip() for x in fh if x.strip())
    chunks = [syms[i:i + a.chunk] for i in range(0, len(syms), a.chunk)]
    todo = [ci for ci in range(len(chunks))
            if not os.path.exists(_chunk_path(out, ci, "feat"))
            or (not a.features_only and not os.path.exists(_chunk_path(out, ci, "arms")))]
    print("walk: %d chunks, %d to do (features_only=%s, procs=%d)"
          % (len(chunks), len(todo), a.features_only, a.procs), flush=True)
    items = [s for ci in todo for s in chunks[ci]]
    fn = partial(walk_symbol, as_of=as_of, features_only=bool(a.features_only))
    t0 = time.time()
    buf, pos, done = [], 0, 0
    peak = 0.0
    it = run_pool(fn, items, a.procs, initializer=AS._init)
    for ci in todo:
        need = len(chunks[ci])
        buf = []
        for _ in range(need):
            r = next(it)
            buf.append(r)
            if r[2] is not None:
                peak = max(peak, r[2]["meta"]["rss_mb"])
        _write_chunk(out, ci, buf, study, bool(a.features_only))
        done += need
        print("  chunk %04d  %d/%d names %.0fs peak_worker_rss=%.0fMB"
              % (ci, done, len(items), time.time() - t0, peak), flush=True)
    for _ in it:
        pass
    ok = snapshot_verify(out, snap)
    if not ok:
        raise SystemExit(4)


def snapshot_verify(out, snap) -> bool:
    F = load_chunks(out, "feat")
    names = [str(x) for x in F["names"]]
    digests = dict(zip(names, (str(x) for x in F["m_digest"])))
    chunk_of = dict(zip(names, (int(x) for x in F["chunk_of"])))
    t0 = snap["stamps"]
    now = read_stamps(list(t0))
    docs_moved = [s for s in t0 if now.get(s) != t0.get(s)]
    walked_moved = [s for s in docs_moved if s in digests]
    differ = []
    for s in walked_moved:
        df, err = load_closed(s, snap["as_of"])
        if df is None or bars_digest(df) != digests[s]:
            differ.append(s)
    ok = not differ
    rep = {"ok": ok, "as_of": snap["as_of"], "t0_max_cached_at": snap.get("t0_max_cached_at"),
           "docs_moved": len(docs_moved), "walked_moved": len(walked_moved),
           "bars_differ": len(differ), "checked": datetime.now().isoformat(timespec="seconds")}
    _json_dump(os.path.join(out, "snapshot_verify.json"), rep)
    print("snapshot verify: docs moved %d, walked names moved %d, bars differ %d -> %s"
          % (len(docs_moved), len(walked_moved), len(differ), "OK" if ok else "FAIL"), flush=True)
    if not ok:
        _json_dump(os.path.join(out, "snapshot_fail.json"),
                   {"names": differ, "chunks": sorted({chunk_of[s] for s in differ})})
    return ok


def _dpos(dates, udates):
    return np.searchsorted(udates, dates).astype(np.int64)


def _sha256_file(p) -> Optional[str]:
    try:
        with open(p, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def _cgroup_peak_mb() -> Optional[float]:
    for p in ("/sys/fs/cgroup/memory.peak", "/sys/fs/cgroup/memory/memory.max_usage_in_bytes"):
        try:
            with open(p) as fh:
                return int(fh.read().strip()) / (1024.0 * 1024.0)
        except (OSError, ValueError):
            continue
    return None


def _event_frame(F, in_study_only=True, evaluable_only=True):
    sid = F["ev_sid"]
    keep = ~F["ev_bad_event"]
    if evaluable_only:
        keep &= F["ev_evaluable"]
    if in_study_only:
        keep &= F["in_study"][sid]
    return keep


def stage_sanity(a) -> dict:
    """Opens ONLY the _feat files (no outcome exists in them)."""
    out = a.out
    snap = _read_json(os.path.join(out, "snapshot_t0.json")) or {}
    F = load_chunks(out, "feat")
    names = F["names"]
    stride = int(snap.get("stride") or 1)
    ev_ok = ~F["ev_bad_event"]
    print("=" * 100)
    print("SANITY (features only — no outcome is read here)")
    from collections import Counter
    sk = Counter(str(v).split(":")[0] for v in F["skipped"].values())
    print("  AS_OF %s   names walked %d   skipped %d %s"
          % (snap.get("as_of"), len(names), len(F["skipped"]), dict(sk)))
    n_ev = len(F["ev_t"])
    print("  events %d (bad_event %d)  evaluable %d  terminal %d  open %d   events/name %.1f"
          % (n_ev, int(F["ev_bad_event"].sum()), int((F["ev_evaluable"] & ev_ok).sum()),
             int((F["ev_terminal"] & ev_ok).sum()), int((~F["ev_evaluable"] & ev_ok).sum()),
             n_ev / max(len(names), 1)))
    print("  pool rows %d  evaluable %d" % (len(F["pl_t"]), int(F["pl_evaluable"].sum())))
    alld = np.concatenate([F["ev_date"], F["pl_date"]]) if n_ev else F["pl_date"]
    if alld.size:
        print("  date span %s .. %s (%d sessions)" % (_dstr(alld.min()), _dstr(alld.max()),
                                                     len(np.unique(alld))))
    try:
        with open(os.path.join(out, "in_study.txt")) as fh:
            n_study = sum(1 for x in fh if x.strip())
    except OSError:
        n_study = 0
    print("  in_study list %d names (expect 3,766 +-1%%); walked in_study %d; ended names %d"
          % (n_study, int(F["in_study"].sum()), int(F["m_ended"].sum())))
    # PIT checks
    step = max(1, len(names) // PIT_CHECK_NAMES)
    pick = list(range(0, len(names), step))[:PIT_CHECK_NAMES]
    pc = {"names": 0, "set_mismatch": 0, "attr_mismatch": 0, "history_mismatch": 0,
          "open_base_mismatch": 0, "chain_diff": 0, "history_chain_diff": 0,
          "digest_moved": 0, "events_checked": 0}
    as_of = snap.get("as_of")
    t_chk = time.time()
    for g in pick:
        sym = str(names[g])
        df, err = load_closed(sym, as_of)
        if df is None:
            continue
        if bars_digest(df) != str(F["m_digest"][g]):
            pc["digest_moved"] += 1
            continue
        m = F["ev_sid"] == g
        ts = F["ev_t"][m]
        rows = []
        for j in np.flatnonzero(m):
            rows.append({"date": _dstr(F["ev_date"][j]), "raid_level": float(F["ev_E"][j]),
                         "raid_price": float(F["ev_L"][j]), "raid_close": float(F["ev_C"][j]),
                         "depth_pct": _nan_none(F["ev_depth_pct"][j]),
                         "vol_ratio": _nan_none(F["ev_vol_ratio"][j]),
                         "base_lo": float(F["ev_base_lo"][j]), "base_hi": float(F["ev_base_hi"][j]),
                         "base_bars": int(F["ev_base_bars"][j]),
                         "base_date": _dstr(F["ev_base_date"][j]),
                         "base_end_date": _dstr(F["ev_base_end_date"][j]),
                         "sweep_seq": int(F["ev_sweep_seq"][j])})
        r = pit_check(df, list(ts), rows)
        pc["names"] += 1
        for k in ("set_mismatch", "attr_mismatch", "chain_diff"):
            pc[k] += r[k]
        for t in ts:
            hc = history_check(df, int(t))
            pc["events_checked"] += 1
            pc["history_mismatch"] += int(not hc["match"])
            pc["open_base_mismatch"] += int(not hc["open_base_match"])
            pc["history_chain_diff"] += int(hc["chain_diff"])
    print("  PIT check on %d stride names (%.0fs): set_mismatch %d  attr_mismatch %d  "
          "history_mismatch %d (open_base %d) over %d events  chain_diff %d (full vs prefix, "
          "informational)  history chain_diff %d  digest moved %d"
          % (pc["names"], time.time() - t_chk, pc["set_mismatch"], pc["attr_mismatch"],
             pc["history_mismatch"], pc["open_base_mismatch"], pc["events_checked"],
             pc["chain_diff"], pc["history_chain_diff"], pc["digest_moved"]))
    print("  matching: Amendment 1 NN matcher — matched share, balance and the density "
          "read print in match")
    mem = {"peak_worker_rss_mb": float(F["m_rss"].max()) if len(F["m_rss"]) else None,
           "parent_rss_mb": peak_rss_mb(), "container_peak_mb": _cgroup_peak_mb(),
           "wall_per_name_s": float(F["m_wall"].mean()) if len(F["m_wall"]) else None}
    print("  memory: peak worker RSS %s MB  parent RSS %.0f MB  container peak %s MB  "
          "wall per name %.2fs"
          % (_fmt(mem["peak_worker_rss_mb"]), mem["parent_rss_mb"],
             _fmt(mem["container_peak_mb"]), mem["wall_per_name_s"] or float("nan")))
    shas = {"amd_sha256": _sha256_file(A.__file__), "script_sha256": _sha256_file(__file__)}
    print("  sha256 amd.py %s  script %s" % (shas["amd_sha256"], shas["script_sha256"]))
    rep = {"pit_checks": pc, "memory": mem, **shas}
    _json_dump(os.path.join(out, "sanity.json"), rep)
    return rep


def _nan_none(x):
    x = _flt(x)
    return None if x != x else x


def _fmt(x):
    return "n/a" if x is None else "%.0f" % x


def stage_match(a) -> dict:
    """Opens ONLY the _feat files. Amendment 1: the 1:1 nearest-twin P1 / P1s /
    cache-all draws, the balance gate on rho, delta AND nu, the unmatched
    profile, a half-density read, per-block matched counts and the largest
    block. The v1 cell draw is kept as a record only (balance_v1)."""
    out = a.out
    F = load_chunks(out, "feat")
    ke = _event_frame(F)
    if ke.sum() < 10:
        print("match: fewer than 10 evaluable in_study events — nothing to match")
        return {}
    edges = bin_edges({"delta": F["ev_delta"][ke], "rho": F["ev_rho"][ke], "nu": F["ev_nu"][ke]})
    ecell = cell_of(F["ev_delta"], F["ev_rho"], F["ev_nu"], edges)
    pcell = cell_of(F["pl_delta"], F["pl_rho"], F["pl_nu"], edges)
    cal = np.unique(np.concatenate([F["ev_date"], F["pl_date"]]))
    ev_all = pd.DataFrame({"eid": np.arange(len(F["ev_t"])), "sym": F["ev_sid"],
                           "date": F["ev_date"], "dpos": _dpos(F["ev_date"], cal),
                           "t": F["ev_t"], "cell": ecell,
                           **{v: np.asarray(F["ev_" + v], dtype=np.float64) for v in MATCH_VARS}})
    pl_all = pd.DataFrame({"pid": np.arange(len(F["pl_t"])), "sym": F["pl_sid"],
                           "date": F["pl_date"], "dpos": _dpos(F["pl_date"], cal),
                           "t": F["pl_t"], "cell": pcell,
                           **{v: np.asarray(F["pl_" + v], dtype=np.float64) for v in MATCH_VARS}})
    kp = F["pl_evaluable"] & F["in_study"][F["pl_sid"]]
    kp_all = F["pl_evaluable"].copy()
    ke_all = _event_frame(F, in_study_only=False)
    gap = ORDER_WINDOW + HOLD
    s = match_sd(ev_all[ke], pl_all[kp])
    P1 = match_nn(ev_all[ke], pl_all[kp], s)
    P1s = match_nn(ev_all[ke], pl_all[kp], s, same_symbol=True, widen=0)
    CA = match_nn(ev_all[ke_all], pl_all[kp_all], s)
    matched = np.unique(P1["eid"].to_numpy(dtype=np.int64))
    n_ev = int(ke.sum())
    widened = int(P1.loc[P1["kind"] == "widened", "eid"].nunique())
    ev_m = matched
    d_idx = P1["pid"].to_numpy(dtype=np.int64)
    dist = P1["dist"].to_numpy(dtype=float)
    bal = {}
    for f in MATCH_VARS + ("depth", "pos"):
        bal["smd_" + f] = smd(F["ev_" + f][ev_m], F["pl_" + f][d_idx])
    for j, v in enumerate(MATCH_VARS):
        a_ = np.asarray(F["ev_" + v][ev_m], dtype=float)
        b_ = np.asarray(F["pl_" + v][d_idx], dtype=float)
        bal["smd_fixed_" + v] = (float((a_.mean() - b_.mean()) / s[j])
                                 if a_.size and b_.size else float("nan"))
    bal["balanced"] = balance_gate(bal)
    bal["gate_vars"] = list(MATCH_VARS)
    bal["match_sd"] = {v: float(s[j]) for j, v in enumerate(MATCH_VARS)}
    bal["caliper_sd"] = CALIPER_SD
    bal["k_nn"] = K_NN
    bal["pair_dist_p50"] = float(np.percentile(dist, 50)) if dist.size else float("nan")
    bal["pair_dist_p90"] = float(np.percentile(dist, 90)) if dist.size else float("nan")
    V1 = draw_matched(ev_all[ke], pl_all[kp], k=K_PLACEBO, seed=SEED, same_symbol=False,
                      widen=DATE_WIDEN, gap=gap)
    v1_ev = np.unique(V1["eid"].to_numpy(dtype=np.int64))
    v1_pid = V1["pid"].to_numpy(dtype=np.int64)
    bal["balance_v1"] = {"label": "SUPERSEDED by Amendment 1 — record only",
                         "matched_share": len(v1_ev) / n_ev if n_ev else float("nan"),
                         **{"smd_" + v: smd(F["ev_" + v][v1_ev], F["pl_" + v][v1_pid])
                            for v in MATCH_VARS}}
    un_ids = np.asarray(P1.attrs["unmatched"], dtype=np.int64)
    unmatched_profile = {
        "n": int(len(un_ids)), "share": len(un_ids) / n_ev if n_ev else float("nan"),
        "matched_mean": {v: float(np.nanmean(np.asarray(F["ev_" + v][ev_m], dtype=float)))
                         if len(ev_m) else float("nan") for v in MATCH_VARS},
        "unmatched_mean": {v: float(np.nanmean(np.asarray(F["ev_" + v][un_ids], dtype=float)))
                           if len(un_ids) else float("nan") for v in MATCH_VARS}}
    p1s_share = P1s["eid"].nunique() / n_ev if n_ev else float("nan")
    n_ca = int(ke_all.sum())
    ca_share = CA["eid"].nunique() / n_ca if n_ca else float("nan")
    half = np.array([zlib.crc32(str(x).encode()) % 2 == 0 for x in F["names"]], dtype=bool)
    ke_h = ke & half[F["ev_sid"]]
    kp_h = kp & half[F["pl_sid"]]
    n_h = int(ke_h.sum())
    PH = match_nn(ev_all[ke_h], pl_all[kp_h], s) if n_h else None
    density_half_share = (PH["eid"].nunique() / n_h) if n_h else float("nan")
    udates = np.unique(F["ev_date"][ke])
    blk = _dpos(F["ev_date"], udates) // HOLD
    mb = pd.Series(blk[matched]).value_counts().sort_index()
    largest = int(mb.idxmax()) if len(mb) else None
    lb_dates = ([_dstr(udates[min(largest * HOLD, len(udates) - 1)]),
                 _dstr(udates[min(largest * HOLD + HOLD - 1, len(udates) - 1)])]
                if largest is not None else None)
    rep = {"feat_fingerprint": feat_fingerprint(F), "amendment": AMENDMENT_1,
           "edges": edges, "n_events": n_ev, "matched": int(len(matched)),
           "matched_share": len(matched) / n_ev if n_ev else float("nan"),
           "widened": widened, "unmatched": len(P1.attrs["unmatched"]),
           "p1_draws": int(len(P1)), "p1s_matched": int(P1s["eid"].nunique()),
           "p1s_matched_share": p1s_share,
           "ca_events": n_ca, "ca_matched": int(CA["eid"].nunique()),
           "ca_matched_share": ca_share,
           "density_half_events": n_h, "density_half_share": density_half_share,
           "unmatched_profile": unmatched_profile,
           "balance": bal, "per_block_matched": {int(k): int(v) for k, v in mb.items()},
           "largest_block": {"id": largest, "dates": lb_dates,
                             "n": int(mb.max()) if len(mb) else 0}}
    print("=" * 100)
    print("MATCH (features only)")
    print("  AMENDMENT 1 matcher: 1:%d nearest twin, caliper %s pooled SD on rho/delta/nu, "
          "same date then +-%d, without replacement" % (K_NN, CALIPER_SD, DATE_WIDEN))
    print("  pooled SD (whole P1 population): %s   pair distance p50 %.2f  p90 %.2f"
          % ("  ".join("%s %.4f" % (v, s[j]) for j, v in enumerate(MATCH_VARS)),
             bal["pair_dist_p50"], bal["pair_dist_p90"]))
    print("  evaluable in_study events %d  matched %d (%.1f%%)  widened %d  unmatched %d"
          % (n_ev, len(matched), 100 * rep["matched_share"], widened, rep["unmatched"]))
    print("  BALANCE GATE (|SMD| < %.2f on rho, delta and nu): rho %+.3f  delta %+.3f  nu %+.3f  -> %s"
          % (BALANCE_SMD_MAX, bal["smd_rho"], bal["smd_delta"], bal["smd_nu"],
             "BALANCED" if bal["balanced"] else "IMBALANCED"))
    print("  printed only: SMD depth %+.3f  pos %+.3f (depth/pos differ by construction); "
          "pre-match denominator: rho %+.3f  delta %+.3f  nu %+.3f"
          % (bal["smd_depth"], bal["smd_pos"], bal["smd_fixed_rho"], bal["smd_fixed_delta"],
             bal["smd_fixed_nu"]))
    v1 = bal["balance_v1"]
    print("  SUPERSEDED v1 cells (record only): matched %.1f%%  rho %+.3f  delta %+.3f  nu %+.3f"
          % (100 * v1["matched_share"], v1["smd_rho"], v1["smd_delta"], v1["smd_nu"]))
    print("  unmatched %d (%.1f%%) mean rho %.3f  delta %.3f  nu %.3f   vs matched rho %.3f  "
          "delta %.3f  nu %.3f"
          % (unmatched_profile["n"], 100 * unmatched_profile["share"],
             *(unmatched_profile["unmatched_mean"][v] for v in MATCH_VARS),
             *(unmatched_profile["matched_mean"][v] for v in MATCH_VARS)))
    print("  P1s matched %.1f%%   cache-all events %d matched %d (%.1f%%)"
          % (100 * p1s_share, n_ca, rep["ca_matched"], 100 * ca_share))
    print("  matched share %.1f%% at this density, %.1f%% at half of it — the full run has "
          "1/stride more candidates per date" % (100 * rep["matched_share"], 100 * density_half_share))
    print("  matched events per date block: %s" % rep["per_block_matched"])
    print("  largest block %s %s (n=%d)" % (largest, lb_dates, rep["largest_block"]["n"]))
    np.savez_compressed(os.path.join(out, "matched.npz"),
                        p1_eid=P1["eid"].to_numpy(dtype=np.int64), p1_pid=d_idx,
                        p1_dist=dist,
                        p1_widened=(P1["kind"] == "widened").to_numpy(dtype=bool),
                        p1_unmatched=un_ids,
                        p1s_eid=P1s["eid"].to_numpy(dtype=np.int64),
                        p1s_pid=P1s["pid"].to_numpy(dtype=np.int64),
                        ca_eid=CA["eid"].to_numpy(dtype=np.int64),
                        ca_pid=CA["pid"].to_numpy(dtype=np.int64),
                        ca_unmatched=np.array(CA.attrs["unmatched"], dtype=np.int64))
    _json_dump(os.path.join(out, "match.json"), rep)
    return rep


def feat_fingerprint(F) -> dict:
    """Identity of the feat files that matched.npz indexes into: the chunk
    list, the walked names with their bar digests, and the row counts. stats
    refuses a matched.npz built from any other walk (stale eids / pids)."""
    h = hashlib.sha1()
    h.update(json.dumps([int(c) for c in F["chunks"]]).encode())
    h.update("\n".join(str(x) for x in F["names"]).encode())
    h.update("\n".join(str(x) for x in F.get("m_digest", [])).encode())
    return {"sha1": h.hexdigest(), "n_ev": int(len(F["ev_t"])), "n_pl": int(len(F["pl_t"]))}


# ── stats helpers ───────────────────────────────────────────────────────────
class _Stack:
    """One array holding matched events and their draws; a draw carries its
    EVENT's cluster labels (the matched set is the unit)."""

    def __init__(self, eids, pids, ev_cols, pl_cols, ev_sym, ev_blk, ev_date, ev_mask=None):
        ue = np.unique(eids)
        if ev_mask is not None:
            ue = ue[ev_mask[ue]]
            keep = np.isin(eids, ue)
            eids, pids = eids[keep], pids[keep]
        self.eids_ev = ue
        self.n_ev = len(ue)
        self.row_eid = np.concatenate([ue, eids])
        self.is_ev = np.r_[np.ones(len(ue), bool), np.zeros(len(eids), bool)]
        self.is_draw = ~self.is_ev
        self.sym = ev_sym[self.row_eid]
        self.blk = ev_blk[self.row_eid]
        self.date = ev_date[self.row_eid]
        self._ev, self._pl, self._e, self._p = ev_cols, pl_cols, ue, pids

    def col(self, ev_key, pl_key):
        return np.r_[np.asarray(self._ev[ev_key], dtype=float)[self._e],
                     np.asarray(self._pl[pl_key], dtype=float)[self._p]]



def _arm(S, ev_arm, pl_arm):
    r = S.col("ev_" + ev_arm + "_r", "pl_" + pl_arm + "_r")
    f = S.col("ev_" + ev_arm + "_f", "pl_" + pl_arm + "_f") > 0
    e = S.col("ev_" + ev_arm + "_e", "pl_" + pl_arm + "_e") > 0
    return r, f & e & np.isfinite(r), e


def _delta_ci(r, fe, S, sel=None, B=None):
    m = np.ones(len(r), bool) if sel is None else sel
    ma, mb = S.is_ev & fe & m, S.is_draw & fe & m
    rs = boot_delta(r, ma, mb, S.sym, B=B)
    rb = boot_delta(r, ma, mb, S.blk, B=B)
    ci = AS.widest(rs["diff_ci"], rb["diff_ci"])
    wider = rs if (rs["diff_ci"][1] - rs["diff_ci"][0]) >= (rb["diff_ci"][1] - rb["diff_ci"][0]) else rb
    return {"a": rs["a"], "b": rs["b"], "diff": rs["diff"], "ci": list(ci),
            "ci_symbol": list(rs["diff_ci"]), "ci_date": list(rb["diff_ci"]),
            "sd": ci_width_sd(wider["diff_ci"]), "n_a": int(ma.sum()), "n_b": int(mb.sum())}


def _mean_ci(vals, mask, sym, blk, B=None):
    rs = boot_mean(vals, mask, sym, B=B)
    rb = boot_mean(vals, mask, blk, B=B)
    return {"mean": rs["mean"], "ci": list(AS.widest(rs["ci"], rb["ci"])), "n": rs["n"]}


def _why_rates(w, fmask):
    n = int(fmask.sum())
    if not n:
        return {k: float("nan") for k in WHY}
    return {k: float((w[fmask] == i).sum()) / n for i, k in enumerate(WHY)}


def stage_stats(a) -> dict:
    out = a.out
    ver = _read_json(os.path.join(out, "snapshot_verify.json")) or {}
    if not ver.get("ok"):
        print("stats: REFUSED — no passed snapshot verify (status invalid_snapshot)")
        res = {"snapshot": ver, "verdict": verdict({"snapshot": ver})}
        print(headline(res))
        return res
    F = load_chunks(out, "feat")
    snap = _read_json(os.path.join(out, "snapshot_t0.json")) or {}
    san = _read_json(os.path.join(out, "sanity.json")) or {}
    mt = _read_json(os.path.join(out, "match.json")) or {}
    if mt.get("feat_fingerprint") != feat_fingerprint(F):
        raise SystemExit("stats: match.json / matched.npz were built from a different walk "
                         "(chunks, names or row counts differ) — rerun --stage match,stats")
    if not (mt.get("balance") or {}).get("balanced"):
        # Amendment 1 (A1.2): the gate failed in match, so no outcome is looked at.
        print("stats: STOPPED — the pre-registered balance gate failed in match (Amendment 1: "
              "|SMD| < %.2f on rho, delta and nu); no outcome file was opened" % BALANCE_SMD_MAX)
        res = {"snapshot": {"ok": True}, "balance": mt.get("balance"),
               "verdict": verdict({"snapshot": {"ok": True}, "balance": mt.get("balance")})}
        print(headline(res))
        return res
    AR = load_chunks(out, "arms")
    Z = np.load(os.path.join(out, "matched.npz"))
    if AR["chunks"] != F["chunks"] or len(AR.get("ev_E1_f", [])) != len(F["ev_t"]):
        raise SystemExit("stats: arms files do not line up with the feature files "
                         "(a features-only walk?) — rerun walk without --features-only")
    ev = {k: v for k, v in F.items() if k.startswith("ev_")}
    ev.update({k: v for k, v in AR.items() if k.startswith("ev_")})
    pl = {k: v for k, v in F.items() if k.startswith("pl_")}
    pl.update({k: v for k, v in AR.items() if k.startswith("pl_")})
    n_ev = len(F["ev_t"])
    ev_sid = F["ev_sid"]
    in_study_ev = F["in_study"][ev_sid]
    ke = _event_frame(F)
    ke_all = _event_frame(F, in_study_only=False)
    udates = np.unique(F["ev_date"][ke])
    ev_blk = (_dpos(F["ev_date"], udates) // HOLD).astype(np.int64)
    ev_date = F["ev_date"].astype(np.int64)
    ev_symg = ev_sid.astype(np.int64)
    res = {"study": STUDY, "run_date": datetime.now().isoformat(timespec="seconds"),
           "git_head": a.git_head, "script_sha256": _sha256_file(__file__),
           "amd_sha256": _sha256_file(A.__file__)}
    res["prereg"] = {k: globals()[k] for k in (
        "WARMUP_PIT", "NEED_BARS", "ORDER_WINDOW", "HOLD", "STOP_PCT", "STOP_ATR",
        "STOP_ATR_FLOOR_PCT", "STOP_ATR_WIDE", "WINDOWS_SECONDARY", "BENCH", "PRICE_FLOOR",
        "RAID_FIELDS", "K_PLACEBO", "PLACEBO_LOWER_FRACTION", "DATE_WIDEN", "DELTA_BINS",
        "RHO_BINS", "NU_BINS", "BALANCE_SMD_MAX", "ENDED_GRACE_DAYS", "BOOT_B", "SEED",
        "MIN_MATCHED_SHARE", "MDL_Z", "MATCH_VARS", "CALIPER_SD", "K_NN")}
    res["prereg"]["verdict_rule"] = VERDICT_RULE_TEXT
    res["prereg"]["amendment_1"] = AMENDMENT_1
    res["snapshot"] = {"as_of": snap.get("as_of"), "t0_max_cached_at": snap.get("t0_max_cached_at"),
                       "docs_moved": ver.get("docs_moved"), "walked_moved": ver.get("walked_moved"),
                       "bars_differ": ver.get("bars_differ"), "ok": bool(ver.get("ok"))}
    res["memory"] = san.get("memory") or {}
    try:
        with open(os.path.join(out, "in_study.txt"), "rb") as fh:
            in_sha = hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        in_sha = None
    alld = np.concatenate([F["ev_date"], F["pl_date"]])
    evl = F["ev_evaluable"] & ~F["ev_bad_event"]
    res["sample"] = {"universe": snap.get("universe"), "in_study_sha256": in_sha,
                     "names_walked": int(len(F["names"])),
                     "skipped": dict(pd.Series([str(v).split(":")[0] for v in F["skipped"].values()],
                                               dtype=object).value_counts()) if F["skipped"] else {},
                     "events": n_ev, "bad_event": int(F["ev_bad_event"].sum()),
                     "evaluable": int((evl & in_study_ev).sum()),
                     "terminal": int((F["ev_terminal"] & ~F["ev_bad_event"] & in_study_ev).sum()),
                     "open": int((~F["ev_evaluable"] & ~F["ev_bad_event"] & in_study_ev).sum()),
                     "pool": int(len(F["pl_t"])),
                     "date_span": [_dstr(alld.min()), _dstr(alld.max())] if alld.size else None,
                     "sessions": int(len(np.unique(alld))), "ended_names": int(F["m_ended"].sum())}
    res["pit_checks"] = san.get("pit_checks") or {}

    # ── P1 stack (matched events only) ──
    S = _Stack(Z["p1_eid"], Z["p1_pid"], ev, pl, ev_symg, ev_blk, ev_date)
    r, fe, e_ok = _arm(S, "E1", "P")
    prim = _delta_ci(r, fe, S)
    rd = boot_delta(r, S.is_ev & fe, S.is_draw & fe, S.date)
    # headline population: ALL filled evaluable in_study events
    E1r = ev["ev_E1_r"].astype(float)
    E1f = (ev["ev_E1_f"] > 0) & ke & np.isfinite(E1r)
    e1_all = _mean_ci(E1r, E1f, ev_symg, ev_blk)
    bdf = bench_frame(snap.get("as_of"))
    rsp = bench_returns(ev["ev_E1_fd"], ev["ev_E1_xd"], bdf)
    xs = E1r - rsp
    xs_mask = E1f & np.isfinite(xs)
    xsr = _mean_ci(xs, xs_mask, ev_symg, ev_blk)
    w = ev["ev_E1_w"]
    rates = _why_rates(w, E1f)
    matched_share = mt.get("matched_share")
    un = Z["p1_unmatched"]
    un_mask = np.zeros(n_ev, bool)
    un_mask[un] = True
    un_eval = un_mask & ke
    res["primary"] = {
        "e1_mean_all": e1_all["mean"], "e1_ci_all": e1_all["ci"],
        "e1_mean_matched": prim["a"], "p1_mean": prim["b"], "diff": prim["diff"],
        "diff_ci_symbol": prim["ci_symbol"], "diff_ci_date": prim["ci_date"],
        "diff_ci": prim["ci"], "diff_ci_perdate": list(rd["diff_ci"]),
        "mdl": MDL_Z * prim["sd"] if prim["sd"] == prim["sd"] else float("nan"),
        "xs_mean": xsr["mean"], "xs_ci": xsr["ci"], "n_xs": int(xs_mask.sum()),
        "no_bench": int((E1f & ~np.isfinite(rsp)).sum()),
        "n_e1_fills": int(E1f.sum()), "n_p1_fills": prim["n_b"],
        "matched_share": matched_share, "widened": mt.get("widened"),
        "unmatched": {"n": int(un_eval.sum()),
                      "share": float(un_eval.sum()) / max(int(ke.sum()), 1),
                      "fill_rate": float((ev["ev_E1_f"][un_eval] > 0).mean()) if un_eval.any() else float("nan"),
                      "e1_mean": float(np.nanmean(E1r[un_eval & E1f])) if (un_eval & E1f).any() else float("nan")},
        "stop_rate": rates["stop"] + rates["gap_stop"], "gap_stop": rates["gap_stop"],
        "target_rate": rates["target"], "clock_rate": rates["clock"],
        "terminal_rate": rates["terminal"],
        "win_rate": float((E1r[E1f] > 0).mean()) if E1f.any() else float("nan"),
        "median": float(np.median(E1r[E1f])) if E1f.any() else float("nan"),
        "trimmed": ES.trimmed_mean(E1r[E1f]),
        "per_event_expectancy": float(np.nan_to_num(np.where(E1f, E1r, 0.0))[ke].mean()),
        "mean_delay": float(ev["ev_E1_d"][E1f].mean()) if E1f.any() else float("nan"),
        "mdl_note": "SD read off the wider 95% interval as width/3.92",
    }
    # fills
    fl_ev = (ev["ev_E1_f"] > 0).astype(float)
    fills = {"E1": _mean_ci(fl_ev, ke, ev_symg, ev_blk),
             "E2": _mean_ci((ev["ev_E2_f"] > 0).astype(float), ke, ev_symg, ev_blk)}
    fcol = S.col("ev_E1_f", "pl_P_f") > 0
    fcol = fcol.astype(float)
    fp = boot_mean(fcol, S.is_draw, S.sym)
    fills["P1"] = {"mean": fp["mean"], "ci": fp["ci"]}
    for k in ("E1", "E2", "P1"):
        fills[k]["rate"] = fills[k].pop("mean")
    fd = _delta_ci(fcol, np.ones(len(fcol), bool), S)
    fills["diff"] = fd["diff"]
    fills["diff_ci"] = fd["ci"]
    res["fills"] = fills
    # balance
    ev_m = S.eids_ev
    bal = dict((mt.get("balance") or {}))
    fe_ev = (ev["ev_E1_f"][ev_m] > 0)
    fe_pl = (pl["pl_P_f"][Z["p1_pid"]] > 0)
    bal["filled"] = {"smd_" + f: smd(F["ev_" + f][ev_m][fe_ev], F["pl_" + f][Z["p1_pid"]][fe_pl])
                     for f in ("delta", "rho", "nu", "depth", "pos")}
    res["balance"] = bal
    # stability
    dates_ev = S.date
    med = date_split(dates_ev[S.is_ev])
    par = np.array([zlib.crc32(str(F["names"][s]).encode()) % 2 for s in S.sym])
    st = {"date_h1": delta_point(r, S.is_ev, S.is_draw, fe, dates_ev < med),
          "date_h2": delta_point(r, S.is_ev, S.is_draw, fe, dates_ev >= med),
          "sym_p0": delta_point(r, S.is_ev, S.is_draw, fe, par == 0),
          "sym_p1": delta_point(r, S.is_ev, S.is_draw, fe, par == 1)}
    rng = np.random.default_rng(SEED)
    for key, lab in (("one_per_date", S.date), ("one_per_symbol", S.sym)):
        evl_ = S.row_eid[S.is_ev]
        labs = lab[S.is_ev]
        chosen = set()
        for u in np.unique(labs):
            cands = evl_[labs == u]
            chosen.add(int(rng.choice(cands)))
        sel = np.isin(S.row_eid, list(chosen))
        st[key] = delta_point(r, S.is_ev, S.is_draw, fe, sel)
    S2 = _Stack(Z["p1s_eid"], Z["p1s_pid"], ev, pl, ev_symg, ev_blk, ev_date)
    r2, fe2, _ = _arm(S2, "E1", "P")
    st["same_symbol"] = delta_point(r2, S2.is_ev, S2.is_draw, fe2)
    dob = drop_one_block(r, S.is_ev, S.is_draw, fe, S.blk)
    am = dob["argmin"]
    st["drop_one_block"] = {"per_block": dob["per_block"], "min": dob["min"],
                            "argmin_dates": _block_dates(am, udates)}
    lb = (mt.get("largest_block") or {}).get("id")
    if lb is not None:
        sel_out = S.blk != lb
        w_ = _delta_ci(r, fe, S)
        wo = _delta_ci(r, fe, S, sel=sel_out)
        e_out = E1f & (ev_blk != lb)
        st["largest_block"] = {
            "dates": _block_dates(lb, udates), "n": (mt.get("largest_block") or {}).get("n"),
            "with": {"diff": w_["diff"], "diff_ci": w_["ci"], "e1_mean": e1_all["mean"],
                     "xs": xsr["mean"], "xs_ci": xsr["ci"]},
            "without": {"diff": wo["diff"], "diff_ci": wo["ci"],
                        "e1_mean": float(E1r[e_out].mean()) if e_out.any() else float("nan"),
                        **{k: v for k, v in zip(("xs", "xs_ci"), _xs_pair(xs, xs_mask & (ev_blk != lb), ev_symg, ev_blk))}}}
    res["stability"] = st
    # survivorship
    SC = _Stack(Z["ca_eid"], Z["ca_pid"], ev, pl, ev_symg, ev_blk, ev_date)
    rc, fec, _ = _arm(SC, "E1", "P")
    cache_only_ev = ~in_study_ev
    ended_ev = F["m_ended"][ev_sid]
    E1f_all = (ev["ev_E1_f"] > 0) & ke_all & np.isfinite(E1r)
    surv = {"note": "price_cache holds only names the app ever cached (since ~2024-09): a PARTIAL check",
            "cache_all": {"diff": delta_point(rc, SC.is_ev, SC.is_draw, fec),
                          "e1_mean": float(E1r[E1f_all].mean()) if E1f_all.any() else float("nan"),
                          "n_events": int(ke_all.sum())}}
    for key, m_ in (("cache_only", cache_only_ev), ("ended", ended_ev)):
        sel = m_[SC.row_eid]
        em = E1f_all & m_
        surv[key] = {"diff": delta_point(rc, SC.is_ev, SC.is_draw, fec, sel),
                     "e1_mean": float(E1r[em].mean()) if em.any() else float("nan"),
                     "n_events": int((ke_all & m_).sum())}
    term_ev = ke_all & F["ev_terminal"]
    term_pl = F["pl_terminal"] & F["pl_evaluable"]
    plr = pl["pl_P_r"].astype(float)
    plf = (pl["pl_P_f"] > 0) & np.isfinite(plr)
    surv["terminal_by_arm"] = {
        "E1": {"rows": int(term_ev.sum()), "fills": int((term_ev & E1f_all).sum()),
               "mean": float(E1r[term_ev & E1f_all].mean()) if (term_ev & E1f_all).any() else float("nan")},
        "P": {"rows": int(term_pl.sum()), "fills": int((term_pl & plf).sum()),
              "mean": float(plr[term_pl & plf].mean()) if (term_pl & plf).any() else float("nan")}}
    res["survivorship"] = surv
    # secondary grid
    sec = {}
    for key, ea, pa in SECONDARY:
        er_ = ev["ev_%s_r" % ea].astype(float)
        ef_ = (ev["ev_%s_f" % ea] > 0) & (ev["ev_%s_e" % ea] > 0) & ke & np.isfinite(er_)
        row = {"label": "SECONDARY", "e1": _mean_ci(er_, ef_, ev_symg, ev_blk)}
        if pa:
            rr, ff, _ = _arm(S, ea, pa)
            row["delta"] = _delta_ci(rr, ff, S)
        if key == "CX":
            base_ = np.where((ev["ev_E1_f"] > 0), E1r, 0.0)
            cx_ = np.where(ev["ev_E1_CX_f"] > 0, er_, 0.0)
            dd = np.nan_to_num(cx_) - np.nan_to_num(base_)
            row["paired_minus_E1"] = _mean_ci(dd, ke, ev_symg, ev_blk)
        sec[key] = row
    for key, sel_ev in (("price_floor", F["ev_L"] >= PRICE_FLOOR),
                        ("first_sweep", F["ev_sweep_seq"] == 1),
                        ("resweep", F["ev_sweep_seq"] > 1)):
        sel = sel_ev[S.row_eid]
        em = E1f & sel_ev
        sec[key] = {"label": "SECONDARY", "e1": _mean_ci(E1r, em, ev_symg, ev_blk),
                    "delta": _delta_ci(r, fe, S, sel=sel)}
    for key in ("E0", "E0N", "E2"):
        rr = ev["ev_%s_r" % key].astype(float)
        mm = (ev["ev_%s_f" % key] > 0) & ke & np.isfinite(rr)
        sec[key] = {"label": "SECONDARY", "mean": _mean_ci(rr, mm, ev_symg, ev_blk),
                    "fill_rate": float((ev["ev_%s_f" % key] > 0)[ke].mean())}
    for key, other in (("E1_minus_E0", "E0"), ("E1_minus_E2", "E2")):
        a1 = np.nan_to_num(np.where(ev["ev_E1_f"] > 0, E1r, 0.0))
        oo = ev["ev_%s_r" % other].astype(float)
        a2 = np.nan_to_num(np.where(ev["ev_%s_f" % other] > 0, oo, 0.0))
        sec[key] = {"label": "SECONDARY (paired per event, unfilled = 0)",
                    "mean": _mean_ci(a1 - a2, ke, ev_symg, ev_blk)}
    e0 = ev["ev_E0_r"].astype(float)
    e0m = (ev["ev_E0_f"] > 0) & ke & np.isfinite(e0)
    sec["E0_given_E1_fill"] = {"label": "SECONDARY (selection diagnostic)",
                               "mean": _mean_ci(e0, e0m & (ev["ev_E1_f"] > 0), ev_symg, ev_blk)}
    sec["E0_given_E1_nofill"] = {"label": "SECONDARY (selection diagnostic)",
                                 "mean": _mean_ci(e0, e0m & (ev["ev_E1_f"] == 0), ev_symg, ev_blk)}
    res["secondary"] = sec
    hs = ev["ev_HS_r"].astype(float)
    hsm = (ev["ev_HS_f"] > 0) & ke & np.isfinite(hs)
    res["diagnostics_not_tradable"] = {
        "hindsight": {"label": "HINDSIGHT — entry at the raid low ON the raid bar; NOT TRADABLE, never scored",
                      "mean": float(hs[hsm].mean()) if hsm.any() else float("nan"), "n": int(hsm.sum())}}
    res["verdict"] = verdict(res)
    _print_report(res)
    _json_dump(os.path.join(out, "amd_raid_low_measured.json"), res)
    print("wrote %s" % os.path.join(out, "amd_raid_low_measured.json"))
    return res


def _xs_pair(xs, mask, sym, blk):
    r = _mean_ci(xs, mask, sym, blk)
    return r["mean"], r["ci"]


def _block_dates(b, udates):
    if b is None or not len(udates):
        return None
    lo = min(int(b) * HOLD, len(udates) - 1)
    hi = min(int(b) * HOLD + HOLD - 1, len(udates) - 1)
    return [_dstr(udates[lo]), _dstr(udates[hi])]


def _pp(x):
    x = _flt(x)
    return "   n/a" if x != x else "%+.2f" % (100 * x)


def _print_report(res):
    pr, fl, st = res["primary"], res["fills"], res["stability"]
    print("=" * 100)
    print("PRIMARY (pre-registered) — E1 vs P1 (cross-name nearest twin, same date; Amendment 1)")
    print("  E1 mean per fill (all evaluable in_study) %s%%  CI [%s, %s]  n=%d"
          % (_pp(pr["e1_mean_all"]), _pp(pr["e1_ci_all"][0]), _pp(pr["e1_ci_all"][1]), pr["n_e1_fills"]))
    print("  matched: E1 %s%%  P1 %s%%  lift %spp  CI [%s, %s] (widest of symbol %s and date-block %s)  "
          "per-date CI [%s, %s]  MDL %spp"
          % (_pp(pr["e1_mean_matched"]), _pp(pr["p1_mean"]), _pp(pr["diff"]),
             _pp(pr["diff_ci"][0]), _pp(pr["diff_ci"][1]), pr["diff_ci_symbol"],
             pr["diff_ci_date"], _pp(pr["diff_ci_perdate"][0]), _pp(pr["diff_ci_perdate"][1]),
             _pp(pr["mdl"])))
    print("  (all fills E1 mean above is NOT the lift's left side; lift = matched E1 − P1)")
    print("  vs RSP: excess %s%%  CI [%s, %s]  n=%d  (no_bench %d)"
          % (_pp(pr["xs_mean"]), _pp(pr["xs_ci"][0]), _pp(pr["xs_ci"][1]), pr["n_xs"], pr["no_bench"]))
    print("  fills E1 %s%%  E2 %s%%  P1 %s%%  (E1-P1 %spp CI [%s, %s])"
          % (_pp(fl["E1"]["rate"]), _pp(fl["E2"]["rate"]), _pp(fl["P1"]["rate"]),
             _pp(fl["diff"]), _pp(fl["diff_ci"][0]), _pp(fl["diff_ci"][1])))
    print("  stopped %s%% (gap %s%%)  target %s%%  clock %s%%  terminal %s%%  win %s%%  median %s%%  "
          "trimmed %s%%  per-event expectancy %s%%  mean delay %.2f"
          % (_pp(pr["stop_rate"]), _pp(pr["gap_stop"]), _pp(pr["target_rate"]), _pp(pr["clock_rate"]),
             _pp(pr["terminal_rate"]), _pp(pr["win_rate"]), _pp(pr["median"]), _pp(pr["trimmed"]),
             _pp(pr["per_event_expectancy"]), _flt(pr["mean_delay"])))
    print("  matched share %s  widened %s  unmatched %s" % (pr["matched_share"], pr["widened"], pr["unmatched"]))
    print("  balance %s" % json.dumps(ES._clean(res["balance"])))
    print("STABILITY  %s" % json.dumps(ES._clean({k: v for k, v in st.items()
                                                 if k not in ("drop_one_block", "largest_block")})))
    print("  drop-one-block min %s at %s" % (_pp(st["drop_one_block"]["min"]),
                                             st["drop_one_block"]["argmin_dates"]))
    print("  largest block %s" % json.dumps(ES._clean(st.get("largest_block"))))
    print("SURVIVORSHIP (partial) %s" % json.dumps(ES._clean(res["survivorship"])))
    print("SECONDARY — labelled, no verdict")
    for k, v in res["secondary"].items():
        print("  %-20s %s" % (k, json.dumps(ES._clean(v))))
    print("HINDSIGHT (NOT TRADABLE, never scored) %s"
          % json.dumps(ES._clean(res["diagnostics_not_tradable"])))
    print("VERDICT %s" % json.dumps(res["verdict"]))
    print(headline(res))


def explain(a, sym: str, date: str) -> None:
    """Raw bars around one bar of one name: the raid (or pool row) read at
    that date and the E1 / P order walked to its exit."""
    snap = _read_json(os.path.join(a.out, "snapshot_t0.json")) or {}
    as_of = snap.get("as_of") or _day_keys(bench_frame())[-1]
    df, err = load_closed(sym, as_of)
    if df is None:
        print("%s: %s" % (sym, err))
        return
    days = _day_keys(df)
    if date not in days:
        print("%s: no bar on %s" % (sym, date))
        return
    t = days.index(date)
    n = len(df)
    o, h, l, c = (df[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
    atr = ES.atr14_series(h, l, c)
    ended = is_ended(days[-1], as_of)
    R = A.find_raids(df.iloc[:t + 1], direction="bullish")
    rows = R.get("raids") or []
    print("%s %s (t=%d of %d, AS_OF %s, ended %s)" % (sym, date, t, n, as_of, ended))
    if rows and rows[-1]["idx"] == t:
        r = rows[-1]
        print("  EVENT: " + ", ".join("%s=%s" % (k, r.get(k)) for k in RAID_FIELDS + ("sweep_seq",)))
        ev = {k: r.get(k) for k in RAID_FIELDS}
        ev["t"] = t
        res = simulate_limit(o, h, l, c, t, float(r["raid_price"]), stop_s0(float(r["raid_price"])),
                             float(r["base_hi"]), window=ORDER_WINDOW, hold=HOLD, ended=ended)
    else:
        evs, pool = pit_walk(df.iloc[:t + 1], warmup=t)
        if not pool:
            print("  neither an event nor a pool row on this bar")
            return
        p = pool[-1]
        print("  POOL ROW: " + ", ".join("%s=%s" % (k, p[k]) for k in ("level", "close", "ob_lo", "ob_hi", "pos")))
        res = simulate_limit(o, h, l, c, t, p["level"], stop_s0(p["level"]), p["ob_hi"],
                             window=ORDER_WINDOW, hold=HOLD, ended=ended)
    print("  order: %s" % json.dumps(ES._clean(res)))
    last = res["exit_idx"] if res["exit_idx"] is not None else min(t + ORDER_WINDOW, n - 1)
    for k in range(t, min(last, n - 1) + 1):
        print("   %s  o %.2f  h %.2f  l %.2f  c %.2f  atr %.2f" % (days[k], o[k], h[k], l[k], c[k], _flt(atr[k])))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="🌀 raid-low entry study (pre-registered)")
    ap.add_argument("--stage", default=None,
                    help="walk|sanity|match|stats|all or a comma list")
    ap.add_argument("--universe", default="cache", choices=("cache", "study"))
    ap.add_argument("--out", default="/tmp/raid_low")
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--chunk", type=int, default=100)
    ap.add_argument("--features-only", action="store_true",
                    help="smoke: no outcome is computed")
    ap.add_argument("--stride", type=int, default=1, help="smoke only (NOT QUOTABLE)")
    ap.add_argument("--names", type=int, default=0, help="smoke only (NOT QUOTABLE)")
    ap.add_argument("--git-head", default=None)
    ap.add_argument("--explain", nargs=2, metavar=("SYM", "DATE"), default=None)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    if a.explain:
        explain(a, a.explain[0].upper(), a.explain[1])
        return
    if not a.stage:
        ap.error("--stage is required unless --explain is given")
    stages = ["walk", "sanity", "match", "stats"] if a.stage == "all" else a.stage.split(",")
    for s in stages:
        if s not in ("walk", "sanity", "match", "stats"):
            ap.error("unknown stage %s" % s)
    os.makedirs(a.out, exist_ok=True)
    for s in stages:
        {"walk": stage_walk, "sanity": stage_sanity, "match": stage_match,
         "stats": stage_stats}[s](a)


if __name__ == "__main__":
    main()
