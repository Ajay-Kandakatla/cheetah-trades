"""🧱 Zone-pad study (2026-09-30): does a 1% pad under demand floors and support key levels pay?

Ajay 2026-09-30, verbatim:
  "Also increase our Demand zone and key levels sizes by 1%. becuz Generally we are missing
   this, I been noticing if the demand zone or key level is 133, it holding at 132. My theory
   is MMs know stoplosses are beyond 133."

The pad itself shipped as HIS RULE (`supply_demand/level_pad.py`, UNMEASURED). This script is
the measurement the ℹ️ panel quotes through `supply_demand/zone_pad_measured.py`. The
pre-registration (questions, cohorts, placebo, CI, verdict rule) is
`docs/supply_demand/zone_pad_study_2026_09_30.md` §1-§4 and was written BEFORE any outcome.

RE-RUN (read-only: Mongo bars cache + zone_store, no provider calls, no writes)
------------------------------------------------------------------------------
    docker cp backend/scripts/zone_pad_study_2026_09_30.py cheetah-market-app-api-1:/tmp/zp.py
    docker exec -d -w /tmp cheetah-market-app-api-1 sh -c \
      'PYTHONPATH=/app python -u /tmp/zp.py --stage all > /tmp/zp.log 2>&1'
    ...then, when /tmp/zp.log says DONE:
    docker exec -w /tmp cheetah-market-app-api-1 sh -c \
      'PYTHONPATH=/app python -u /tmp/zp.py --stage stats --emit-measured'
    docker cp cheetah-market-app-api-1:/tmp/zone_pad_measured.json backend/scripts/

OR, touching nothing inside the live container (a throwaway on the same network, the worktree
mounted read-only; arm A then runs the branch code with level_pad switched OFF):
    docker run --rm --cpus 4 --memory 1.5g --network cheetah-market-app_default \
      -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e PYTHONPATH=/app \
      -e PYTHONDONTWRITEBYTECODE=1 -v <worktree>/backend:/app:ro -v <outdir>:/out -w /out \
      cheetah-api:latest python -u /app/scripts/zone_pad_study_2026_09_30.py --stage all \
      --events /out/zp_events.csv --kl /out/zp_kl.csv --placebo /out/zp_placebo.csv \
      --stats-json /out/zp_stats.json --measured-out /out/zone_pad_measured.json --emit-measured

Stages: replay (Q1/Q2/Q4 -> /tmp/zp_events.csv), keylevels (Q3 -> /tmp/zp_kl.csv), placebo
(matched random levels -> /tmp/zp_placebo.csv), stats (report; --emit-measured writes
zone_pad_measured.json beside this script and prints the MEASURED literal). `--limit-names N`
is a smoke run whose numbers are NEVER quoted. Full runs only after 20:00 ET and never while a
deploy is pending (a deploy recreates the container and kills the run).

ARMS
----
Written before the pad shipped; since 2026-10-01 `level_pad` is on main. Arm A (the pre-pad
engine) is the main-code chain on DRAWN bands: `LP.DEMAND_PAD_PCT` is set to 0 for the run
(every pad read is at call time), and on a tree without `level_pad` nothing needs changing. Arm B (the
pad) is EMULATED here from the one number `sd_liquidity.STOP_SHELF_PCT`:
    _floor_b(band)  = round(lo x (1 - pad/100), 2)
    B-proximity     = _floor_b <= px <= hi x (1 + ALERT_MAX_ABOVE_DEMAND_PCT/100)
    B-approach      = AG.approach_read(px, {**band, "lo": _floor_b(band)}, prev, day_low)
    B-room          = AG.room_gate over the bands with the entry band removed BY IDENTITY
The main session pins emulation == branch engine (tests/test_zone_pad_study_pin.py).

LIMITATIONS (read before quoting)
---------------------------------
* ~2 years of cached daily bars per name, minus a 252-bar floor and the 60-session clock:
  ONE regime.
* Entry = the event bar's CLOSE (BQ's print proxy). Stop is checked BEFORE target inside a
  bar; a bar that gaps through the stop books AT the stop (optimistic on the stop side).
* "kept falling" (a close) and "reversed" (a high) in the same bar count as kept falling.
* Q1 / Q3 buckets (amended 2026-10-01, before any full run): the pierce depth is the deepest
  low over a FIXED window j..j+RECLAIM_MAX_BARS; reversed / kept falling are scored only on
  the HOLD bars AFTER it. Depth-to-resolution (the pre-amendment read) pinned every 'fell' in
  3pad_plus and made the shallow buckets 100% reversed / 0% fell by construction. A reversal
  (or a fall) inside the depth window is not an outcome; the forward % at each clock still
  runs from close[j].
* Bands are recomputed per bar; the Q1 per-band cooldown matches a band at the 2-dp grain.
* The live push also needs the cap floor and the floor-held gate. Cohort A carries neither;
  sub-cohort A_held = A + `AG.floor_held_gate` on the DRAWN floor (the gate every demand push
  path runs, PAD_FLOOR_HELD = False) — the population the phone actually sends. The cap floor
  is still not applied. Q4 measures the floor-held flip on its own.
"""
from __future__ import annotations

import argparse
import json
import os
import pprint
import sys
import time
import zlib
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from scripts import entry_trigger_study as ETS
from scripts import explosive_study as ES
from studies import bounce_quality_study as BQ
from supply_demand import alert_gates as AG
from supply_demand import demand_reentry as DR
from supply_demand import key_levels as KL
from supply_demand import price_zones as PZ
from supply_demand import sd_liquidity as SL

SCRIPT = "backend/scripts/zone_pad_study_2026_09_30.py"
RUN_TAG = "zone_pad_2026_09_30"

# ── every threshold is somebody else's constant, imported by name ────────────
PAD_PCT = SL.STOP_SHELF_PCT                  # the pad (level_pad.DEMAND_PAD_PCT is this)
PIERCE_PCT = SL.SWEEP_MIN_PIERCE_PCT         # 0.15 — "through the level" (== KL.PIERCE_PCT)
RECLAIM_BARS = SL.RECLAIM_MAX_BARS           # 12 — cooldown per band / reclaim window
DEPTH_BARS = SL.RECLAIM_MAX_BARS             # 12 — the pierce-depth window (j..j+12), closed
                                             # BEFORE reversed / kept falling is scored
HOLD = BQ.HOLD_SESSIONS                      # 20 — the reported clock
CLOCKS = BQ.CLOCKS                           # (5, 10, 20, 60)
FLOOR = BQ.MIN_HISTORY_BARS                  # 252 bars of history before an event counts
REVERSAL_PCT = AG.ALERT_MIN_ROOM_PCT         # 5.0 — "reversed" = high >= close x 1.05
TOUCH_TOL_PCT = AG.APPROACH_TOUCH_TOL_PCT    # 1.0 — the day's low within 1% of the band top
STOP_BUFFER_PCT = AG.STOP_BUFFER_PCT         # 0.5 — stop under the floor
MAX_ABOVE_PCT = AG.ALERT_MAX_ABOVE_DEMAND_PCT  # 1.0 — proximity above the band top
MIN_CELL_N = ETS.MIN_CELL_N                  # 120 — a cell below this prints "not shown"
SWEEP_WINDOW = AG.SWEEP_WINDOW_BARS          # 15 — the floor-held read's window
BOOT_DRAWS = BQ.BOOT_DRAWS                   # 5,000 date-clustered resamples
PERM_DRAWS = BQ.PERM_DRAWS                   # 2,000
PLACEBO_BAND_DRAWS = BQ.PLACEBO_DRAWS        # 2,000 date-block keeps (Q4)
SEED_BOOT, SEED_PLACEBO = ES.SEED_BOOT, ES.SEED_PLACEBO

# ── the three numbers the SPEC itself fixes (pre-registered, §2 of the doc) ──
FALL_PADS = 3                                # "kept falling" = close < level x (1 - 3 x pad/100)
PLACEBO_MAX_TRIES = 50                       # <= 50 random draws per real event
QUOTABLE_MIN_DATES = 100                     # quotable only with >= 100 dates

BUCKETS = ("held", "pierce_to_pad", "pad_to_2pad", "2pad_to_3pad", "3pad_plus")
PAD_BUCKET = BUCKETS[1]                      # his case: pierced, but inside the pad
OUTCOMES = ("reversed", "fell", "clock")

STATUS_SUPPORTS, STATUS_NO_SIGNAL, STATUS_INVERTED = "supports", "no_signal", "inverted"

EVENTS_CSV, KL_CSV, PLACEBO_CSV = "/tmp/zp_events.csv", "/tmp/zp_kl.csv", "/tmp/zp_placebo.csv"
STATS_JSON = "/tmp/zp_stats.json"
MEASURED_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zone_pad_measured.json")
CHECKPOINT_EVERY = 200

P = ES.P


# ═════════════════════════════════════════════════════════════════════════════
# ARMS
# ═════════════════════════════════════════════════════════════════════════════
def geom() -> dict:
    """The board geometry with any `demand_pad_pct` key stripped: DRAWN bands on main AND on
    the branch."""
    return {k: v for k, v in DR.zone_geom().items() if k != "demand_pad_pct"}


def arm_a_pad_off():
    """Arm A = the pre-pad engine. Where `level_pad` exists (main since 2026-10-01), turn the
    pad off for this process and return the value it had; without it return None."""
    try:
        from supply_demand import level_pad as LP
    except ImportError:
        return None
    prev = LP.DEMAND_PAD_PCT
    LP.DEMAND_PAD_PCT = 0.0
    return prev


def _pad(pad) -> float:
    p = PAD_PCT if pad is None else pad
    try:
        p = float(p)
    except (TypeError, ValueError):
        return 0.0
    return p if np.isfinite(p) and p > 0 else 0.0


def _valid(band) -> bool:
    if not isinstance(band, dict):
        return False
    lo, hi = ES._f(band.get("lo")), ES._f(band.get("hi"))
    return lo is not None and hi is not None and 0 < lo <= hi


def _floor_b(band, pad=None) -> Optional[float]:
    """Arm B's floor: round(lo x (1 - pad/100), 2) — sd_liquidity.stop_shelf's bottom."""
    if not _valid(band):
        return None
    return round(float(band["lo"]) * (1.0 - _pad(pad) / 100.0), 2)


def prox_b(px, band, pad=None) -> bool:
    fl, p = _floor_b(band, pad), ES._f(px)
    if fl is None or p is None or p <= 0:
        return False
    return bool(fl <= p <= float(band["hi"]) * (1.0 + MAX_ABOVE_PCT / 100.0))


def approach_b(px, band, prev, day_low, pad=None) -> Optional[dict]:
    fl = _floor_b(band, pad)
    if fl is None:
        return None
    return AG.approach_read(px, {**band, "lo": fl}, prev, day_low)


def room_b(px, bands, prev, entry_band) -> tuple:
    """AG.room_gate with the band the event is ABOUT removed by identity (never its own
    ceiling)."""
    return AG.room_gate(px, [b for b in (bands or []) if b is not entry_band], prev)


def pick_event(bands, demand, px, prev, day_low, arm: str, pad=None) -> Optional[dict]:
    """BQ's rule on one bar: every demand band passing proximity with a readable approach,
    the HIGHEST floor wins, it must be reversing ("bouncing" internally), and room >= 5% must
    pass. Arm "A" = the main-code gates on drawn bands; arm "B" = the emulated pad chain."""
    hits = []
    for b in demand or []:
        if arm == "A":
            if not AG.demand_proximity_gate(px, b):
                continue
            ap = AG.approach_read(px, b, prev, day_low)
        else:
            if not prox_b(px, b, pad):
                continue
            ap = approach_b(px, b, prev, day_low, pad)
        if isinstance(ap, dict):
            hits.append((float(b["lo"]), b, ap))
    if not hits:
        return None
    _, band, ap = max(hits, key=lambda t: t[0])
    if not AG.direction_gate(ap):
        return None
    ok, room = AG.room_gate(px, bands, prev) if arm == "A" else room_b(px, bands, prev, band)
    if not ok:
        return None
    return {"band": band, "dir": ap.get("dir"), "room": room}


def stops(band, pad=None) -> tuple:
    """(stop_A, stop_B): STOP_BUFFER_PCT under the drawn floor / under the pad floor."""
    k = 1.0 - STOP_BUFFER_PCT / 100.0
    return float(band["lo"]) * k, float(_floor_b(band, pad)) * k


# ═════════════════════════════════════════════════════════════════════════════
# FORWARD MECHANICS (pure)
# ═════════════════════════════════════════════════════════════════════════════
def forward(h, l, c, j: int, entry: float, stop: float, target: Optional[float],
            clocks=CLOCKS) -> Optional[dict]:
    """BQ's trade: bars j+1.. ; stop checked BEFORE target inside a bar; a stop exit books AT
    the stop even through a gap; else the close at each clock. NaN bars never trigger."""
    if not (entry > stop > 0):
        return None
    mc = max(clocks)
    if j + mc >= len(c):
        return None
    hit_k = hit_px = hit_why = None
    for k in range(1, mc + 1):
        t = j + k
        if l[t] <= stop:
            hit_k, hit_px, hit_why = k, stop, "stop"
            break
        if target is not None and h[t] >= target:
            hit_k, hit_px, hit_why = k, target, "target"
            break
    out = {}
    for cl in clocks:
        if hit_k is not None and hit_k <= cl:
            ex, wy = hit_px, hit_why
        else:
            ex, wy = float(c[j + cl]), "clock"
        out["R%d" % cl] = (ex - entry) / (entry - stop)
        out["pct%d" % cl] = (ex / entry - 1.0) * 100.0
        out["why%d" % cl] = wy
    return out


def bucket(depth_pct, pad=None) -> str:
    """How deep the low went UNDER the drawn level, in % of it."""
    p = _pad(pad)
    d = ES._f(depth_pct)
    if d is None or d < PIERCE_PCT:
        return BUCKETS[0]
    if d < p:
        return BUCKETS[1]
    if d < 2 * p:
        return BUCKETS[2]
    if d < 3 * p:
        return BUCKETS[3]
    return BUCKETS[4]


def resolve(h, l, c, j: int, level: float, hold: int = HOLD, pad=None,
            depth_bars: Optional[int] = None) -> Optional[dict]:
    """Two windows that never overlap (amended 2026-10-01, before any full run):

    DEPTH window = bars j .. e, e = j + DEPTH_BARS (RECLAIM_MAX_BARS, 12): the deepest low
    under `level` (NaN lows skipped) — this alone sets the bucket.
    OUTCOME window = bars e+1 .. e+hold, scored only AFTER the depth window closed:
    reversed = a high >= close[j] x (1 + 5%); kept falling = a close under
    level x (1 - 3 x pad); else the clock. Same bar -> kept falling.

    Before the amendment the depth ran to the RESOLUTION bar, so every 'fell' landed in
    3pad_plus by construction and the shallow buckets could only read reversed / clock;
    real - placebo on the pierce-to-pad bucket was pinned at 0. `res_k` counts bars from j."""
    wn = DEPTH_BARS if depth_bars is None else int(depth_bars)
    e = j + wn
    if wn < 0 or e + hold >= len(c) or not (level > 0) or not np.isfinite(c[j]):
        return None
    w = np.asarray(l[j:e + 1], dtype=float)
    w = w[np.isfinite(w)]
    depth = (float(level) - float(w.min())) / float(level) * 100.0 if w.size else float("nan")
    tgt = float(c[j]) * (1.0 + REVERSAL_PCT / 100.0)
    fall = float(level) * (1.0 - FALL_PADS * _pad(pad) / 100.0)
    outcome, res_k = "clock", wn + hold
    for k in range(1, hold + 1):
        t = e + k
        if c[t] < fall:
            outcome, res_k = "fell", wn + k
            break
        if h[t] >= tgt:
            outcome, res_k = "reversed", wn + k
            break
    return {"outcome": outcome, "res_k": res_k, "depth_pct": depth, "bucket": bucket(depth, pad)}


def touch_band(prev_close, low_j, hi) -> bool:
    """Q1 touch: yesterday closed ABOVE the band, today's low came within 1% of its top."""
    pc, lj, top = ES._f(prev_close), ES._f(low_j), ES._f(hi)
    if pc is None or lj is None or top is None or top <= 0:
        return False
    return bool(pc > top and lj <= top * (1.0 + TOUCH_TOL_PCT / 100.0))


def touch_level(prev_close, low_j, L) -> bool:
    """Q3 support test: prior close above L, today's low within AT_LEVEL_PCT of it."""
    pc, lj, lv = ES._f(prev_close), ES._f(low_j), ES._f(L)
    if pc is None or lj is None or lv is None or lv <= 0:
        return False
    return bool(pc > lv and lj <= lv * (1.0 + KL.AT_LEVEL_PCT / 100.0))


def _through(close, edge) -> bool:
    """key_levels._beyond on the support side: through `edge` by >= PIERCE_PCT, in %."""
    x = ES._f(close)
    if x is None or not edge or edge <= 0:
        return False
    return (edge - x) / edge * 100.0 >= PIERCE_PCT - 1e-9


def key_pad_edge(L, pad=None) -> float:
    """The padded key-level edge (4 dp, key_levels' member grain)."""
    return round(float(L) * (1.0 - _pad(pad) / 100.0), 4)


def reclaim_read(l, c, j: int, L: float) -> dict:
    """Pierced (low through L by PIERCE_PCT) within RECLAIM_BARS of j, and a close >= L at or
    after the pierce inside that window."""
    end = min(len(c) - 1, j + RECLAIM_BARS)
    thr = L * (1.0 - PIERCE_PCT / 100.0)
    pk = next((k for k in range(j, end + 1) if l[k] <= thr), None)
    if pk is None:
        return {"pierced": False, "reclaimed": False}
    return {"pierced": True, "reclaimed": any(c[m] >= L for m in range(pk, end + 1))}


def suppressed_sell(c, j: int, L: float, hold: int = HOLD, pad=None) -> dict:
    """Q3b. The first close within `hold` that breaks L by PIERCE (today's key_level_alert).
    Suppressed = it did NOT break the padded edge by PIERCE too. Then: closed back >= L within
    RECLAIM_BARS, or later broke the padded edge within `hold` (extra % lost at that later
    close vs the raw signal close; negative = lost more)."""
    out = {"raw_fired": False, "suppressed": False, "supp_reclaimed": np.nan,
           "supp_pad_broke": np.nan, "extra_pct": np.nan}
    edge = key_pad_edge(L, pad)
    end = min(len(c) - 1, j + hold)
    rk = next((k for k in range(j, end + 1) if _through(c[k], L)), None)
    if rk is None:
        return out
    out["raw_fired"] = True
    if _through(c[rk], edge):
        return out
    out["suppressed"] = True
    rend = min(len(c) - 1, rk + RECLAIM_BARS)
    out["supp_reclaimed"] = float(any(c[m] >= L for m in range(rk + 1, rend + 1)))
    pend = min(len(c) - 1, rk + hold)
    pk = next((m for m in range(rk + 1, pend + 1) if _through(c[m], edge)), None)
    out["supp_pad_broke"] = float(pk is not None)
    if pk is not None:
        out["extra_pct"] = (float(c[pk]) / float(c[rk]) - 1.0) * 100.0
    return out


# ═════════════════════════════════════════════════════════════════════════════
# KEY LEVELS, vectorized (pinned == KL.period_levels in the tests)
# ═════════════════════════════════════════════════════════════════════════════
def period_lows(f: pd.DataFrame, periods=None) -> dict:
    """{period: array} — for every bar j, the support LOW `KL.period_levels(bars[:j],
    session=date[j])` would return (4 dp), NaN when it has none."""
    periods = tuple(periods or KL.BOARD_PERIODS)
    low = pd.to_numeric(f["low"], errors="coerce").astype(float).reset_index(drop=True)
    raw = f["d"].astype(str).str[:10].to_numpy() if "d" in f.columns else KL._norm_index(f)
    dts = pd.Series(pd.to_datetime(np.asarray(raw)))
    n = len(low)
    out = {}
    for per, freq in (("week", "W-FRI"), ("month", "M")):
        if per not in periods:
            continue
        pr = dts.dt.to_period(freq)
        mins = low.groupby(pr).min()
        prev = pr - 1
        v = pd.Series(mins.reindex(pd.PeriodIndex(prev)).to_numpy(), dtype=float).to_numpy()
        out[per] = v
    if "year" in periods:
        yb = KL.YEAR_BARS
        v = low.rolling(yb, min_periods=1).min().shift(1).to_numpy(dtype=float)
        v[:yb] = np.nan
        out["year"] = v
    for per, v in out.items():
        v = np.where(np.isfinite(v) & (v > 0), np.round(v, 4), np.nan)
        out[per] = v
    return out


# ═════════════════════════════════════════════════════════════════════════════
# REPLAY (per symbol, pure given a frame)
# ═════════════════════════════════════════════════════════════════════════════
def _arrays(f: pd.DataFrame) -> tuple:
    return tuple(pd.to_numeric(f[k], errors="coerce").to_numpy(dtype=float)
                 for k in ("high", "low", "close"))


def _last_bar(n: int) -> int:
    return n - max(CLOCKS) - 1


def _sweep_win(f: pd.DataFrame, j: int) -> pd.DataFrame:
    return f.iloc[max(0, j - SWEEP_WINDOW - 2):j + 1]


def _sweep_state(band, f: pd.DataFrame, j: int, lo: float) -> Optional[str]:
    r = AG.sweep_read({**band, "lo": lo}, frame=_sweep_win(f, j))
    return r.get("state") if isinstance(r, dict) else None


def floor_held_a(band, f: pd.DataFrame, j: int) -> bool:
    """The phone's floor-held gate, verbatim: `AG.floor_held_gate` on the DRAWN band over the
    same closed-bar window the sweep reads use (A_held = cohort A where this is True)."""
    return bool(AG.floor_held_gate(band, frame=_sweep_win(f, j)))


def _arm_cols(prefix: str, fw: Optional[dict]) -> dict:
    if not fw:
        return {}
    return {"%s_%s" % (prefix, k): v for k, v in fw.items()}


def replay_symbol(sym: str, f: pd.DataFrame, pad=None, gkw: Optional[dict] = None) -> list:
    """Q1 touches + Q2 events (cohort A, B_new, B_approach) + Q4 sweep reads for one name."""
    gkw = geom() if gkw is None else gkw
    if f is None or len(f) < FLOOR + max(CLOCKS) + 2:
        return []
    h, l, c = _arrays(f)
    dates = f["d"].astype(str).str[:10].to_numpy()
    rows = []
    last_touch: dict = {}
    for j in range(FLOOR, _last_bar(len(f)) + 1):
        px, prev, dl = float(c[j]), float(c[j - 1]), float(l[j])
        if not (np.isfinite(px) and np.isfinite(prev) and np.isfinite(dl)):
            continue
        z = PZ.compute(f.iloc[max(0, j - PZ.LOOKBACK_BARS):j], last_price=px, max_zones=None, **gkw)
        if not z:
            continue
        demand = z.get("demand_zones") or []
        bands = (z.get("supply_zones") or []) + demand
        # ── Q1: every drawn demand band reached from above ───────────────────
        for b in demand:
            if not _valid(b) or not touch_band(prev, dl, b["hi"]):
                continue
            key = (round(float(b["lo"]), 2), round(float(b["hi"]), 2))
            if key in last_touch and j - last_touch[key] < RECLAIM_BARS:
                continue
            last_touch[key] = j
            rs = resolve(h, l, c, j, float(b["lo"]), HOLD, pad)
            if rs is None:
                continue
            rows.append({"q": "q1", "symbol": sym, "date": dates[j], "j": j,
                         "lo": float(b["lo"]), "hi": float(b["hi"]),
                         "touches": int(b.get("touches") or 0),
                         "proven": bool(AG.is_proven_band(b)), "entry": px,
                         "g": (prev - float(b["hi"])) / prev,
                         "h": (float(b["hi"]) - float(b["lo"])) / float(b["lo"]), **rs})
        # ── Q2 / Q4 ──────────────────────────────────────────────────────────
        ea = pick_event(bands, demand, px, prev, dl, "A", pad)
        eb = pick_event(bands, demand, px, prev, dl, "B", pad)
        if ea is None and eb is None:
            continue
        if ea is not None:
            band, room, cohort = ea["band"], ea["room"], "A"
        else:
            band, room = eb["band"], eb["room"]
            cohort = "B_new" if px < float(band["lo"]) else "B_approach"
        sa, sb = stops(band, pad)
        target = float(room["target"]) if room else None
        fa = forward(h, l, c, j, px, sa, target) if cohort == "A" else None
        fb = forward(h, l, c, j, px, sb, target)
        if fb is None or (cohort == "A" and fa is None):
            continue
        lo, hi = float(band["lo"]), float(band["hi"])
        row = {"q": "q2", "cohort": cohort, "symbol": sym, "date": dates[j], "j": j,
               "lo": lo, "hi": hi, "touches": int(band.get("touches") or 0),
               "floor_b": _floor_b(band, pad), "entry": px, "prev": prev, "day_low": dl,
               "stop_a": sa, "stop_b": sb, "target": target,
               "room_pct": (room or {}).get("room_pct_raw"), "clear": room is None,
               "g": (prev - hi) / prev, "h": (hi - lo) / lo,
               "low_in_pad": bool(_floor_b(band, pad) <= dl < lo),
               "b_band_differs": bool(ea is not None and eb is not None and eb["band"] is not band),
               **_arm_cols("a", fa), **_arm_cols("b", fb)}
        if cohort == "A":
            row["sweep_drawn"] = _sweep_state(band, f, j, lo)
            row["sweep_pad"] = _sweep_state(band, f, j, _floor_b(band, pad))
            row["floor_held_a"] = floor_held_a(band, f, j)
        rows.append(row)
    return rows


def kl_symbol(sym: str, f: pd.DataFrame, pad=None) -> list:
    """Q3: support tests of the board's key-level lows, one event per (symbol, date) — the
    highest level tested (the nearest support under the print)."""
    if f is None or len(f) < FLOOR + max(CLOCKS) + 2:
        return []
    h, l, c = _arrays(f)
    dates = f["d"].astype(str).str[:10].to_numpy()
    lows = period_lows(f)
    rows = []
    last_touch: dict = {}
    for j in range(FLOOR, _last_bar(len(f)) + 1):
        prev = float(c[j - 1])
        cands = {}
        for per in KL.BOARD_PERIODS:
            L = lows[per][j]
            if not np.isfinite(L) or not touch_level(prev, l[j], L):
                continue
            key = (per, round(float(L), 4))
            if key in last_touch and j - last_touch[key] < RECLAIM_BARS:
                continue
            last_touch[key] = j
            cands.setdefault(round(float(L), 4), []).append(per)
        if not cands:
            continue
        L = max(cands)
        rs = resolve(h, l, c, j, L, HOLD, pad)
        if rs is None:
            continue
        row = {"q": "q3", "symbol": sym, "date": dates[j], "j": j, "L": L,
               "periods": "+".join(sorted(cands[L])), "entry": float(c[j]),
               "g": (prev - L) / prev, **rs, **reclaim_read(l, c, j, L),
               **suppressed_sell(c, j, L, HOLD, pad)}
        for cl in CLOCKS:
            row["fwd%d" % cl] = (float(c[j + cl]) / float(c[j]) - 1.0) * 100.0
        rows.append(row)
    return rows


# ═════════════════════════════════════════════════════════════════════════════
# PLACEBO — a random level at the matched gap on another name, same date
# ═════════════════════════════════════════════════════════════════════════════
def placebo_band(prev_c, g, h) -> Optional[dict]:
    """hi' = prev' x (1 - g), lo' = hi'/(1 + h), both at the band's 2-dp grain. None when the
    gap is not positive (price was not above the level) or the inputs are garbage."""
    pc, gg, hh = ES._f(prev_c), ES._f(g), ES._f(h)
    if pc is None or gg is None or hh is None or pc <= 0 or gg <= 0 or hh < 0:
        return None
    hi = round(pc * (1.0 - gg), 2)
    lo = round(hi / (1.0 + hh), 2)
    if not (0 < lo <= hi):
        return None
    return {"kind": "demand", "lo": lo, "hi": hi}


def placebo_level(prev_c, g) -> Optional[float]:
    pc, gg = ES._f(prev_c), ES._f(g)
    if pc is None or gg is None or pc <= 0 or gg <= 0:
        return None
    L = round(pc * (1.0 - gg), 4)
    return L if L > 0 else None


def placebo_accepts(ev: dict, h, l, c, j: int, pad=None) -> Optional[dict]:
    """Build the matched level on bar j of ANOTHER name and apply the real event's own entry
    test. Returns the forward row or None (rejected)."""
    if j < 1 or j + max(CLOCKS) >= len(c):
        return None
    pc, lj, px = c[j - 1], l[j], c[j]
    if not (np.isfinite(pc) and np.isfinite(lj) and np.isfinite(px)):
        return None
    q = ev["q"]
    if q == "q3":
        L = placebo_level(pc, ev["g"])
        if L is None or not touch_level(pc, lj, L):
            return None
        rs = resolve(h, l, c, j, L, HOLD, pad)
        if rs is None:
            return None
        row = {"L": L, **rs, **reclaim_read(l, c, j, L), **suppressed_sell(c, j, L, HOLD, pad)}
        for cl in CLOCKS:
            row["fwd%d" % cl] = (float(c[j + cl]) / float(px) - 1.0) * 100.0
        return row
    band = placebo_band(pc, ev["g"], ev["h"])
    if band is None or not touch_band(pc, lj, band["hi"]):
        return None
    if q == "q1":
        rs = resolve(h, l, c, j, band["lo"], HOLD, pad)
        return None if rs is None else {"lo": band["lo"], "hi": band["hi"], **rs}
    # q2: the real event's entry test on the random band (proximity + a reversal read);
    # the target is the real event's room, carried as a percentage.
    band["touches"] = int(ev.get("touches") or 0)
    if not AG.demand_proximity_gate(px, band):
        return None
    if not AG.direction_gate(AG.approach_read(px, band, pc, lj)):
        return None
    rp = ES._f(ev.get("room_pct"))
    target = float(px) * (1.0 + rp / 100.0) if rp is not None else None
    sa, sb = stops(band, pad)
    fa = forward(h, l, c, j, float(px), sa, target)
    fb = forward(h, l, c, j, float(px), sb, target)
    if fa is None or fb is None:
        return None
    return {"lo": band["lo"], "hi": band["hi"], **_arm_cols("a", fa), **_arm_cols("b", fb)}


def ev_id(ev: dict) -> str:
    lvl = ev.get("L") if ev.get("q") == "q3" else ev.get("lo")
    return "%s|%s|%s|%s" % (ev.get("q"), ev.get("symbol"), str(ev.get("date"))[:10], lvl)


def draw_placebo(ev: dict, pool: dict, frames: dict, pad=None) -> tuple:
    """(row or None, tries). Up to PLACEBO_MAX_TRIES seeded draws of another name with a bar on
    the event's date."""
    cands = pool.get(str(ev["date"])[:10])
    if cands is None or len(cands) == 0:
        return None, 0
    rng = np.random.default_rng(zlib.crc32(ev_id(ev).encode()))
    tries = 0
    for _ in range(PLACEBO_MAX_TRIES):
        sym, j = cands[int(rng.integers(0, len(cands)))]
        tries += 1
        if sym == ev["symbol"]:
            continue
        h, l, c = frames[sym]
        row = placebo_accepts(ev, h, l, c, int(j), pad)
        if row is not None:
            return {"ev_id": ev_id(ev), "q": ev["q"], "date": str(ev["date"])[:10],
                    "p_symbol": sym, "tries": tries, **row}, tries
    return None, tries


def build_pool(frames_d: dict) -> dict:
    """{date: [(symbol, bar index)]} over bars with a prior bar and the full forward clock."""
    pool: dict = {}
    for sym, (dates, c) in frames_d.items():
        n = len(c)
        for j in range(1, n - max(CLOCKS)):
            pool.setdefault(dates[j], []).append((sym, j))
    return pool


# ═════════════════════════════════════════════════════════════════════════════
# STATISTICS — date-clustered, reusing explosive_study.cluster_boot
# ═════════════════════════════════════════════════════════════════════════════
def _nanmean(s) -> float:
    return ES._nanmean(np.asarray(s, dtype=float))


def mean_ci(D: pd.DataFrame, col: str, draws: int = BOOT_DRAWS, seed: int = SEED_BOOT) -> dict:
    """Date-clustered 95% CI on mean(D[col]) (NaN rows ignored): cluster_boot against a
    zero column on the same rows, i.e. mean - 0 on every resample."""
    n = int(np.isfinite(pd.to_numeric(D[col], errors="coerce")).sum()) if len(D) else 0
    out = {"mean": _nanmean(D[col]) if len(D) else float("nan"), "lo": float("nan"),
           "hi": float("nan"), "n": n, "dates": int(D["date"].nunique()) if len(D) else 0}
    if n == 0:
        return out
    d = ES.cluster_boot(D.assign(**{col: 0.0}), D, col, "date", draws, seed)
    if d.size >= 100:
        out["lo"], out["hi"] = float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))
    return out


def two_sample(X: pd.DataFrame, Y: pd.DataFrame, col: str, draws: int = BOOT_DRAWS,
               seed: int = SEED_BOOT) -> dict:
    """mean(Y[col]) - mean(X[col]), date-clustered: cluster_boot over the UNION of dates (X is
    padded with NaN rows on Y-only dates so no Y date drops out of the resample)."""
    out = {"d": float("nan"), "lo": float("nan"), "hi": float("nan"),
           "n_x": int(len(X)), "n_y": int(len(Y)),
           "dates": int(len(set(X["date"]) | set(Y["date"])) if len(X) or len(Y) else 0)}
    if len(X) == 0 or len(Y) == 0:
        return out
    out["d"] = _nanmean(Y[col]) - _nanmean(X[col])
    miss = sorted(set(Y["date"]) - set(X["date"]))
    Xa = X[["date", col]]
    if miss:
        Xa = pd.concat([Xa, pd.DataFrame({"date": miss, col: np.nan})], ignore_index=True)
    d = ES.cluster_boot(Xa, Y[["date", col]].reset_index(drop=True), col, "date", draws, seed)
    if d.size >= 100:
        out["lo"], out["hi"] = float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))
    return out


def verdict(lo, hi) -> str:
    """Pre-registered: supports if the CI lower bound > 0, inverted if the upper bound < 0."""
    a, b = ES._f(lo), ES._f(hi)
    if a is not None and a > 0:
        return STATUS_SUPPORTS
    if b is not None and b < 0:
        return STATUS_INVERTED
    return STATUS_NO_SIGNAL


def quotable(cells: dict, n_dates: int) -> tuple:
    """(ok, reasons): every cell n >= MIN_CELL_N and >= QUOTABLE_MIN_DATES dates."""
    why = ["%s n=%d < %d" % (k, int(v), MIN_CELL_N) for k, v in cells.items() if int(v) < MIN_CELL_N]
    if int(n_dates) < QUOTABLE_MIN_DATES:
        why.append("dates=%d < %d" % (int(n_dates), QUOTABLE_MIN_DATES))
    return (not why), why


def _cell(n) -> str:
    return "" if int(n) >= MIN_CELL_N else "  (n<%d — not shown)" % MIN_CELL_N


def _bool(s) -> pd.Series:
    """A CSV round-trip turns bools into True/False/"True"/NaN: read them as bools, NaN = False."""
    return pd.Series(s).map(lambda v: str(v).strip().lower() in ("true", "1", "1.0"))


def _flags(D: pd.DataFrame) -> pd.DataFrame:
    D = D.copy()
    D["rev100"] = 100.0 * (D["outcome"] == "reversed")
    D["fell100"] = 100.0 * (D["outcome"] == "fell")
    D["clock100"] = 100.0 * (D["outcome"] == "clock")
    D["is_pad100"] = 100.0 * (D["bucket"] == PAD_BUCKET)
    return D


def touch_tables(R: pd.DataFrame, Pc: pd.DataFrame, draws: int) -> dict:
    """Q1/Q3 (a)-(d): bucket shares of reversals, per-bucket outcome rates, real vs placebo, and
    the two pre-registered real - placebo contrasts on the pierce-to-pad bucket."""
    R, Pc = _flags(R), _flags(Pc) if len(Pc) else Pc
    res = {"n": int(len(R)), "dates": int(R["date"].nunique()) if len(R) else 0,
           "n_placebo": int(len(Pc))}
    for tag, D in (("real", R), ("placebo", Pc)):
        rev = D[D["outcome"] == "reversed"] if len(D) else D
        res[tag] = {
            "reversal_share_by_bucket": {b: (100.0 * float((rev["bucket"] == b).mean())
                                             if len(rev) else float("nan")) for b in BUCKETS},
            "by_bucket": {b: {"n": int((D["bucket"] == b).sum()) if len(D) else 0,
                              **{o: (_nanmean(D.loc[D["bucket"] == b, o + "100"])
                                     if len(D) else float("nan")) for o in ("rev", "fell", "clock")}}
                          for b in BUCKETS}}
    if len(R) and len(Pc):
        rp, pp = R[R["bucket"] == PAD_BUCKET], Pc[Pc["bucket"] == PAD_BUCKET]
        res["d_rev_given_pad"] = two_sample(pp, rp, "rev100", draws)
        res["d_pad_share_of_reversals"] = two_sample(Pc[Pc["outcome"] == "reversed"],
                                                     R[R["outcome"] == "reversed"], "is_pad100", draws)
    return res


def arm_stats(D: pd.DataFrame, arm: str) -> dict:
    R = D["%s_R%d" % (arm, HOLD)].astype(float)
    return {"n": int(len(D)), "win": 100.0 * float((R > 0).mean()) if len(D) else float("nan"),
            "stop": 100.0 * float((D["%s_why%d" % (arm, HOLD)] == "stop").mean()) if len(D) else float("nan"),
            "mean_R": _nanmean(R), "median_R": float(np.nanmedian(R)) if len(D) else float("nan"),
            **{"pct%d" % cl: _nanmean(D["%s_pct%d" % (arm, cl)]) for cl in CLOCKS}}


def _paired(D: pd.DataFrame) -> pd.DataFrame:
    D = D.copy()
    for cl in CLOCKS:
        D["d_pct%d" % cl] = D["b_pct%d" % cl].astype(float) - D["a_pct%d" % cl].astype(float)
    D["d_win"] = 100.0 * ((D["b_R%d" % HOLD] > 0).astype(float) - (D["a_R%d" % HOLD] > 0).astype(float))
    D["d_stop"] = 100.0 * ((D["b_why%d" % HOLD] == "stop").astype(float)
                           - (D["a_why%d" % HOLD] == "stop").astype(float))
    D["d_R"] = D["b_R%d" % HOLD].astype(float) - D["a_R%d" % HOLD].astype(float)
    D["b_win100"] = 100.0 * (D["b_R%d" % HOLD] > 0)
    D["b_stop100"] = 100.0 * (D["b_why%d" % HOLD] == "stop")
    return D


def _q2_cohort(A: pd.DataFrame, pl: pd.DataFrame, draws: int) -> dict:
    """Arm stats, paired B - A CIs and the DiD vs the placebo pairs of THIS cohort's events."""
    out = {"n": int(len(A)), "dates": int(A["date"].nunique()) if len(A) else 0,
           "arm_A": arm_stats(A, "a"), "arm_B": arm_stats(A, "b"), "paired": {}}
    for col in ["d_pct%d" % cl for cl in CLOCKS] + ["d_win", "d_stop", "d_R"]:
        out["paired"][col] = mean_ci(A, col, draws)
    out["paired"]["d_median_R"] = (float(np.nanmedian(A["b_R%d" % HOLD]) - np.nanmedian(A["a_R%d" % HOLD]))
                                   if len(A) else float("nan"))
    col = "d_pct%d" % HOLD
    if len(A) and len(pl):
        ids = A.apply(lambda r: ev_id(r.to_dict()), axis=1)
        Rm = A[ids.isin(set(pl["ev_id"]))].reset_index(drop=True)
        plc = pl[pl["ev_id"].isin(set(ids))].reset_index(drop=True)
        out["did"] = {**two_sample(plc, Rm, col, draws), "col": col,
                      "n_pairs": int(len(Rm)), "placebo_mean": _nanmean(plc[col]),
                      "real_mean": _nanmean(Rm[col])}
        out["did_stop"] = two_sample(plc, Rm, "d_stop", draws)
        out["did_win"] = two_sample(plc, Rm, "d_win", draws)
    else:
        out["did"] = {"d": float("nan"), "lo": float("nan"), "hi": float("nan"), "n_pairs": 0,
                      "dates": 0, "col": col}
    return out


def q2_tables(E: pd.DataFrame, PL: pd.DataFrame, draws: int, perm: int) -> dict:
    A = _paired(E[(E["q"] == "q2") & (E["cohort"] == "A")].reset_index(drop=True))
    # PRIMARY — DiD on matched pairs: (B - A mean % at HOLD, real) - (same, placebo)
    pl = _paired(PL[PL["q"] == "q2"].reset_index(drop=True)) if len(PL) else pd.DataFrame()
    ca = _q2_cohort(A, pl, draws)
    out = {"n_A": ca["n"], "dates_A": ca["dates"], "arm_A": ca["arm_A"], "arm_B": ca["arm_B"],
           "paired": ca["paired"], "did": ca["did"]}
    for k in ("did_stop", "did_win"):
        if k in ca:
            out[k] = ca[k]
    # A_held: cohort A + the floor-held gate on the DRAWN floor — what the phone pushes
    if len(A) and "floor_held_a" in A:
        Ah = A[_bool(A["floor_held_a"]).to_numpy()].reset_index(drop=True)
        out["A_held"] = _q2_cohort(Ah, pl, draws)
    else:
        out["A_held"] = {"n": 0, "dates": 0, "missing": "floor_held_a not in the replay rows"}
    # B_new: the events only the pad chain admits (print inside the pad), stop_B both sides
    Bn = E[(E["q"] == "q2") & (E["cohort"] == "B_new")].reset_index(drop=True)
    out["n_B_approach"] = int(((E["q"] == "q2") & (E["cohort"] == "B_approach")).sum())
    if len(Bn):
        Bn = Bn.assign(b_win100=100.0 * (Bn["b_R%d" % HOLD] > 0),
                       b_stop100=100.0 * (Bn["b_why%d" % HOLD] == "stop"))
        out["B_new"] = {"stats": arm_stats(Bn, "b"),
                        "vs_A_stopB": {k: two_sample(A, Bn, k, draws)
                                       for k in ("b_win100", "b_stop100", "b_pct%d" % HOLD)},
                        "perm_p_pct": ES.perm_p(Bn, A, "b_pct%d" % HOLD, perm)}
    else:
        out["B_new"] = {"stats": {"n": 0}}
    # Q4 — the floor-held flip (HIS CALL #1), stop_B on both sides
    if len(A) and "sweep_drawn" in A:
        pierced = A["sweep_drawn"].isin(["swept", "broken"])
        rescued = A[pierced & (A["sweep_pad"] == "intact")].reset_index(drop=True)
        intact = A[A["sweep_drawn"] == "intact"].reset_index(drop=True)
        q4 = {"n_rescued": int(len(rescued)), "n_drawn_intact": int(len(intact)),
              "rescued": arm_stats(rescued, "b") if len(rescued) else {"n": 0},
              "drawn_intact": arm_stats(intact, "b") if len(intact) else {"n": 0}}
        if len(rescued) and len(intact):
            q4["rescued_minus_intact"] = {k: two_sample(intact, rescued, k, draws)
                                          for k in ("b_win100", "b_stop100", "b_pct%d" % HOLD)}
            band = ES.placebo_dates(A, len(rescued), ["b_win100", "b_stop100", "b_pct%d" % HOLD],
                                    PLACEBO_BAND_DRAWS)
            q4["size_matched_date_block_5_95"] = {k: list(v) for k, v in band.items()}
        out["q4"] = q4
    return out


def q3b_tables(R: pd.DataFrame, Pc: pd.DataFrame, draws: int) -> dict:
    def one(D):
        S = D[_bool(D["suppressed"]).to_numpy()] if len(D) else D
        return S, {"n_tests": int(len(D)), "raw_fired": int(_bool(D["raw_fired"]).sum()) if len(D) else 0,
                   "suppressed": int(len(S)),
                   "reclaimed_pct": 100.0 * _nanmean(S["supp_reclaimed"]) if len(S) else float("nan"),
                   "later_pad_broke_pct": 100.0 * _nanmean(S["supp_pad_broke"]) if len(S) else float("nan"),
                   "extra_pct_mean": _nanmean(S["extra_pct"]) if len(S) else float("nan")}
    Sr, real = one(R)
    Sp, plc = one(Pc) if len(Pc) else (Pc, {"suppressed": 0})
    out = {"real": real, "placebo": plc, "extra_pct_ci": mean_ci(Sr.dropna(subset=["extra_pct"]), "extra_pct", draws)
           if len(Sr) else {}}
    if len(Sr) and len(Sp):
        Sr = Sr.assign(rec100=100.0 * Sr["supp_reclaimed"].astype(float))
        Sp = Sp.assign(rec100=100.0 * Sp["supp_reclaimed"].astype(float))
        out["real_minus_placebo"] = {"reclaimed_pct": two_sample(Sp, Sr, "rec100", draws),
                                     "extra_pct": two_sample(Sp, Sr, "extra_pct", draws)}
    return out


# ═════════════════════════════════════════════════════════════════════════════
# THE MEASURED LITERAL
# ═════════════════════════════════════════════════════════════════════════════
MEASURED_KEYS = ("run_date", "status", "did_pct", "did_ci_lo", "did_ci_hi", "n_trades", "n_dates")


def measured_block(q2: dict, meta: dict) -> tuple:
    """(dict or None, reasons). None = not quotable -> nothing is emitted (the panel keeps
    saying UNMEASURED)."""
    did = q2.get("did") or {}
    n_pairs, n_pl, n_dates = int(did.get("n_pairs") or 0), int(did.get("n_x") or 0), int(did.get("dates") or 0)
    ok, why = quotable({"real_pairs": n_pairs, "placebo_pairs": n_pl}, n_dates)
    core = [ES._f(did.get(k)) for k in ("d", "lo", "hi")]
    if any(v is None for v in core):
        ok, why = False, why + ["the DiD or its CI is undefined"]
    if not ok:
        return None, why
    a, b = q2["arm_A"], q2["arm_B"]
    m = {"run_date": meta["run_date"], "status": verdict(core[1], core[2]),
         "did_pct": core[0], "did_ci_lo": core[1], "did_ci_hi": core[2],
         "n_trades": n_pairs, "n_dates": n_dates, "clock": HOLD,
         "placebo_accept_pct": meta.get("placebo_accept_pct_q2"),
         "arm_a_win": a["win"], "arm_a_stop": a["stop"], "arm_a_mean_R": a["mean_R"],
         "arm_b_win": b["win"], "arm_b_stop": b["stop"], "arm_b_mean_R": b["mean_R"],
         "pad_pct": PAD_PCT, "universe": meta.get("universe"),
         "first_date": meta.get("first_date"), "last_date": meta.get("last_date"),
         "script": SCRIPT}
    return ES._clean(m), []


def measured_literal(m: dict) -> str:
    return "MEASURED = " + pprint.pformat(m, sort_dicts=False, width=100)


# ═════════════════════════════════════════════════════════════════════════════
# STAGES
# ═════════════════════════════════════════════════════════════════════════════
def _coll():
    from sepa import prices
    return prices._get_mongo()


def load_frame(coll, sym) -> Optional[pd.DataFrame]:
    f = BQ._frame(coll, sym)
    if f is None:
        return None
    return ES.apply_tail_rule(ES.drop_nonpositive(f, None), ES._today_et(), None)


def symbols(mode: str, limit: int = 0) -> list:
    if mode == "store":
        from supply_demand import zone_store as ZS
        _, docs = ZS.load_latest()
        syms = sorted(docs)
    else:
        from sepa import universe
        syms = list(universe.load_universe(mode))
    return syms[:limit] if limit else syms


def _loop(syms: list, fn, out_csv: str, resume: bool) -> pd.DataFrame:
    done_path = out_csv + ".done.json"
    rows, done = [], set()
    if resume and os.path.exists(out_csv) and os.path.exists(done_path):
        rows = pd.read_csv(out_csv).to_dict("records")
        done = set(json.load(open(done_path)))
    coll = _coll()
    t0 = time.time()
    for i, sym in enumerate(syms):
        if sym in done:
            continue
        try:
            rows.extend(fn(sym, load_frame(coll, sym)))
        except Exception as e:                                   # noqa: BLE001
            print("  %s skipped: %s" % (sym, type(e).__name__), file=sys.stderr, flush=True)
        done.add(sym)
        if (i + 1) % CHECKPOINT_EVERY == 0:
            pd.DataFrame(rows).to_csv(out_csv, index=False)
            json.dump(sorted(done), open(done_path, "w"))
            print("  %d/%d names  rows=%d  %.0fs" % (i + 1, len(syms), len(rows), time.time() - t0),
                  file=sys.stderr, flush=True)
    D = pd.DataFrame(rows)
    D.to_csv(out_csv, index=False)
    json.dump(sorted(done), open(done_path, "w"))
    return D


def stage_replay(a) -> None:
    D = _loop(symbols(a.universe, a.limit_names), lambda s, f: replay_symbol(s, f), a.events, a.resume)
    P("replay: %d rows -> %s" % (len(D), a.events))


def stage_keylevels(a) -> None:
    D = _loop(symbols(a.universe, a.limit_names), lambda s, f: kl_symbol(s, f), a.kl, a.resume)
    P("keylevels: %d rows -> %s" % (len(D), a.kl))


def stage_placebo(a) -> None:
    coll = _coll()
    frames, frames_d = {}, {}
    for sym in symbols(a.universe, a.limit_names):
        f = load_frame(coll, sym)
        if f is None or len(f) < max(CLOCKS) + 2:
            continue
        h, l, c = _arrays(f)
        frames[sym] = (h, l, c)
        frames_d[sym] = (f["d"].astype(str).str[:10].to_numpy(), c)
    pool = build_pool(frames_d)
    evs = []
    if os.path.exists(a.events):
        E = pd.read_csv(a.events)
        evs += E[(E["q"] == "q1") | ((E["q"] == "q2") & (E["cohort"] == "A"))].to_dict("records")
    if os.path.exists(a.kl):
        evs += pd.read_csv(a.kl).to_dict("records")
    rows, att = [], {}
    for ev in evs:
        row, tries = draw_placebo(ev, pool, frames)
        s = att.setdefault(ev["q"], {"events": 0, "accepted": 0, "tries": 0})
        s["events"] += 1
        s["tries"] += tries
        if row is not None:
            s["accepted"] += 1
            rows.append({**row, **{k: ev.get(k) for k in ("proven",) if k in ev}})
    pd.DataFrame(rows).to_csv(a.placebo, index=False)
    json.dump(att, open(a.placebo + ".accept.json", "w"))
    for q, s in sorted(att.items()):
        P("placebo %s: %d/%d accepted (%.1f%%), %.1f draws/event"
          % (q, s["accepted"], s["events"], 100.0 * s["accepted"] / max(1, s["events"]),
             s["tries"] / max(1, s["events"])))


def _fmt_ci(r: dict, unit: str = "pp") -> str:
    if not r:
        return "n/a"
    return "%+.2f%s [%+.2f, %+.2f]" % (r.get("d", r.get("mean", float("nan"))), unit,
                                       r.get("lo", float("nan")), r.get("hi", float("nan")))


def stage_stats(a) -> dict:
    E = pd.read_csv(a.events) if os.path.exists(a.events) else pd.DataFrame(columns=["q", "date"])
    K = pd.read_csv(a.kl) if os.path.exists(a.kl) else pd.DataFrame(columns=["q", "date"])
    PL = pd.read_csv(a.placebo) if os.path.exists(a.placebo) else pd.DataFrame(columns=["q", "date", "ev_id"])
    acc_path = a.placebo + ".accept.json"
    acc = json.load(open(acc_path)) if os.path.exists(acc_path) else {}
    for D in (E, K, PL):
        if len(D):
            D["date"] = D["date"].astype(str).str[:10]
    draws, perm = a.boot, a.perm
    meta = {"run_date": datetime.now().strftime("%Y-%m-%d"), "universe": a.universe,
            "first_date": str(E["date"].min()) if len(E) else None,
            "last_date": str(E["date"].max()) if len(E) else None,
            "placebo_accept": acc}
    s2 = acc.get("q2") or {}
    meta["placebo_accept_pct_q2"] = (100.0 * s2["accepted"] / s2["events"]) if s2.get("events") else None
    res = {"meta": meta, "constants": {"pad_pct": PAD_PCT, "pierce_pct": PIERCE_PCT,
                                       "reclaim_bars": RECLAIM_BARS, "hold": HOLD, "clocks": list(CLOCKS),
                                       "stop_buffer_pct": STOP_BUFFER_PCT, "reversal_pct": REVERSAL_PCT,
                                       "fall_pads": FALL_PADS, "min_cell_n": MIN_CELL_N,
                                       "quotable_min_dates": QUOTABLE_MIN_DATES}}
    P("=" * 100)
    P("ZONE PAD STUDY — %s  universe=%s  %s -> %s" % (meta["run_date"], a.universe,
                                                      meta["first_date"], meta["last_date"]))
    P("pad %.2f%% (sd_liquidity.STOP_SHELF_PCT) · clock %d · placebo accept %s" % (PAD_PCT, HOLD, acc))
    # Q1
    if len(E):
        q1 = E[E["q"] == "q1"]
        p1 = PL[PL["q"] == "q1"] if len(PL) else PL
        res["q1"] = {}
        for tag, keep in (("all_bands", None), ("proven_only", True)):
            R = q1 if keep is None else q1[_bool(q1["proven"]).to_numpy()]
            Pc = p1 if (keep is None or not len(p1) or "proven" not in p1) else p1[_bool(p1["proven"]).to_numpy()]
            res["q1"][tag] = touch_tables(R.reset_index(drop=True), Pc.reset_index(drop=True), draws)
            t = res["q1"][tag]
            P("\nQ1 his observation — zones, %s: n=%d dates=%d placebo n=%d"
              % (tag, t["n"], t["dates"], t["n_placebo"]))
            for b in BUCKETS:
                r, pc_ = t["real"]["by_bucket"][b], (t.get("placebo") or {}).get("by_bucket", {}).get(b, {})
                P("  %-14s n=%6d  reversed %5.1f%%  fell %5.1f%%  clock %5.1f%% | placebo n=%6d reversed %5.1f%%%s"
                  % (b, r["n"], r["rev"], r["fell"], r["clock"], pc_.get("n", 0),
                     pc_.get("rev", float("nan")), _cell(r["n"])))
            if "d_rev_given_pad" in t:
                P("  real - placebo  P(reversed | pierce_to_pad) %s" % _fmt_ci(t["d_rev_given_pad"]))
                P("  real - placebo  pierce_to_pad share of reversals %s" % _fmt_ci(t["d_pad_share_of_reversals"]))
        # Q2 + Q4
        q2 = q2_tables(E, PL, draws, perm)
        res["q2"] = q2
        A, B = q2["arm_A"], q2["arm_B"]
        P("\nQ2 the pad vs today, cohort A n=%d dates=%d (win / stop-out / mean R / median R):" % (q2["n_A"], q2["dates_A"]))
        for tag, s in (("A drawn stop", A), ("B pad stop  ", B)):
            P("  %s win %5.1f%%  stop %5.1f%%  mean R %+.3f  median R %+.3f  %s"
              % (tag, s["win"], s["stop"], s["mean_R"], s["median_R"],
                 "  ".join("%%@%d %+.2f" % (cl, s["pct%d" % cl]) for cl in CLOCKS)))
        for k in ("d_win", "d_stop", "d_R", "d_pct%d" % HOLD):
            P("  paired B - A %-8s %s" % (k, _fmt_ci(q2["paired"][k], "")))
        did = q2["did"]
        P("  PRIMARY DiD (B - A %%@%d, real - placebo): %s  pairs=%d dates=%d  -> %s"
          % (HOLD, _fmt_ci(did, "%"), did.get("n_pairs", 0), did.get("dates", 0),
             verdict(did.get("lo"), did.get("hi"))))
        ah = q2["A_held"]
        P("\n  A_held (cohort A + floor held on the drawn floor = what the phone pushes) n=%d dates=%d%s"
          % (ah.get("n", 0), ah.get("dates", 0), _cell(ah.get("n", 0))))
        if ah.get("n"):
            for tag, s in (("A drawn stop", ah["arm_A"]), ("B pad stop  ", ah["arm_B"])):
                P("    %s win %5.1f%%  stop %5.1f%%  mean R %+.3f  median R %+.3f"
                  % (tag, s["win"], s["stop"], s["mean_R"], s["median_R"]))
            for k in ("d_win", "d_stop", "d_R", "d_pct%d" % HOLD):
                P("    paired B - A %-8s %s" % (k, _fmt_ci(ah["paired"][k], "")))
            hd = ah["did"]
            P("    DiD (B - A %%@%d, real - placebo): %s  pairs=%d dates=%d  -> %s"
              % (HOLD, _fmt_ci(hd, "%"), hd.get("n_pairs", 0), hd.get("dates", 0),
                 verdict(hd.get("lo"), hd.get("hi"))))
        bn = q2["B_new"]
        P("  B_new (print inside the pad, pad chain only): n=%d  approach-flip only: n=%d"
          % (bn["stats"].get("n", 0), q2["n_B_approach"]))
        if bn["stats"].get("n"):
            s = bn["stats"]
            P("    win %5.1f%%  stop %5.1f%%  mean R %+.3f  | vs A (stop_B): win %s  stop %s  %%@%d %s  perm p %.3f%s"
              % (s["win"], s["stop"], s["mean_R"], _fmt_ci(bn["vs_A_stopB"]["b_win100"]),
                 _fmt_ci(bn["vs_A_stopB"]["b_stop100"]), HOLD,
                 _fmt_ci(bn["vs_A_stopB"]["b_pct%d" % HOLD], "%"), bn["perm_p_pct"], _cell(s["n"])))
        if "q4" in q2:
            q4 = q2["q4"]
            P("\nQ4 floor-held flip: rescued (pierced on drawn, intact on pad) n=%d vs drawn-intact n=%d%s"
              % (q4["n_rescued"], q4["n_drawn_intact"], _cell(q4["n_rescued"])))
            if "rescued_minus_intact" in q4:
                m = q4["rescued_minus_intact"]
                P("  rescued - intact: win %s  stop %s  %%@%d %s" % (
                    _fmt_ci(m["b_win100"]), _fmt_ci(m["b_stop100"]), HOLD, _fmt_ci(m["b_pct%d" % HOLD], "%")))
    # Q3
    if len(K):
        p3 = PL[PL["q"] == "q3"] if len(PL) else PL
        res["q3"] = touch_tables(K, p3.reset_index(drop=True), draws)
        res["q3"]["reclaim_pct"] = {b: 100.0 * _nanmean(_bool(K.loc[K["bucket"] == b, "reclaimed"]).astype(float))
                                    for b in BUCKETS}
        res["q3"]["fwd_by_bucket"] = {b: {"fwd%d" % cl: _nanmean(K.loc[K["bucket"] == b, "fwd%d" % cl])
                                          for cl in CLOCKS} for b in BUCKETS}
        res["q3b"] = q3b_tables(K, p3.reset_index(drop=True), draws)
        t = res["q3"]
        P("\nQ3 key levels (PWL/PML/52wL support tests): n=%d dates=%d placebo n=%d" % (t["n"], t["dates"], t["n_placebo"]))
        for b in BUCKETS:
            r = t["real"]["by_bucket"][b]
            P("  %-14s n=%6d  reversed %5.1f%%  fell %5.1f%%  clock %5.1f%%  reclaimed %5.1f%%  %%@%d %+.2f%s"
              % (b, r["n"], r["rev"], r["fell"], r["clock"], t["reclaim_pct"][b], HOLD,
                 t["fwd_by_bucket"][b]["fwd%d" % HOLD], _cell(r["n"])))
        if "d_rev_given_pad" in t:
            P("  real - placebo  P(reversed | pierce_to_pad) %s" % _fmt_ci(t["d_rev_given_pad"]))
            P("  real - placebo  pierce_to_pad share of reversals %s" % _fmt_ci(t["d_pad_share_of_reversals"]))
        s3 = res["q3b"]
        P("  Q3b suppressed sells: %d of %d raw close-throughs; reclaimed %.1f%%, later broke the pad %.1f%%, "
          "extra %% at the later padded close %s"
          % (s3["real"]["suppressed"], s3["real"]["raw_fired"], s3["real"]["reclaimed_pct"],
             s3["real"]["later_pad_broke_pct"], _fmt_ci(s3.get("extra_pct_ci") or {}, "%")))
    # the measured block
    m, why = measured_block(res.get("q2") or {"did": {}}, meta)
    res["measured"] = m
    res["not_quotable_because"] = why
    json.dump(ES._clean(res), open(a.stats_json, "w"), indent=1)
    P("\nstats -> %s" % a.stats_json)
    if a.emit_measured:
        if m is None:
            P("NOT EMITTED — not quotable: %s" % "; ".join(why))
        else:
            json.dump(ES._clean(res), open(a.measured_out, "w"), indent=1)
            P("measured -> %s\n" % a.measured_out)
            P(measured_literal(m))
    return res


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stage", default="all", choices=("replay", "keylevels", "placebo", "stats", "all"))
    ap.add_argument("--universe", default="store")
    ap.add_argument("--limit-names", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--events", default=EVENTS_CSV)
    ap.add_argument("--kl", default=KL_CSV)
    ap.add_argument("--placebo", default=PLACEBO_CSV)
    ap.add_argument("--stats-json", default=STATS_JSON)
    ap.add_argument("--measured-out", default=MEASURED_JSON)
    ap.add_argument("--emit-measured", action="store_true")
    ap.add_argument("--boot", type=int, default=BOOT_DRAWS)
    ap.add_argument("--perm", type=int, default=PERM_DRAWS)
    a = ap.parse_args(argv)
    prev = arm_a_pad_off()
    P("arm A = today's engine (%s)" % ("branch, level_pad OFF (was %r)" % prev if prev is not None
                                      else "main: no level_pad"))
    t0 = time.time()
    if a.stage in ("replay", "all"):
        stage_replay(a)
    if a.stage in ("keylevels", "all"):
        stage_keylevels(a)
    if a.stage in ("placebo", "all"):
        stage_placebo(a)
    if a.stage in ("stats", "all"):
        stage_stats(a)
    P("DONE %.0fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
