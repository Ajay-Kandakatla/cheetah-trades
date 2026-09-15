"""🧨 Explosive read — the STUDY (Phase 1: a measurement; nothing is wired).

THE ASK (Ajay 2026-09-14, verbatim from the brief): a per-stock *explosiveness*
read for names in / arriving at a demand band — the likelihood of a **>= 5% move
from the demand band toward the first supply band** — built from RSI / volume
burst / KC / AMD / the stock's traded volume, **evaluated before it ranks**, and
then ranked on **every Chart Maps tab**.

HOUSE RULES this file is written under: his ONE typed number is the 5%
(= `alert_gates.ALERT_MIN_ROOM_PCT`, imported, never retyped); every other
threshold is an existing constant (imported) or a quantile of the cohort; the
backtest ships with the claim (this script + CI + placebo); no lookahead; nothing
gates an alert or a lane; paper only; read-only container probes.

WHAT IT REUSES (nothing is copied): `studies.bounce_quality_study.events()` is
the cohort — bands from `price_zones.compute` on bars STRICTLY BEFORE the event
bar with the board's own geometry (`demand_reentry.zone_geom()`), the two
standing gates (`room_gate` >= 5% to the first PROVEN lid, `demand_proximity_gate`
<= 1% above the band top), `approach_read` for the direction, the engine's own
forward pass (stop checked BEFORE the target inside a bar). Features are a
post-hoc LEFT join on ["symbol","date"] with a HARD `assert len(X) == len(E)`.

TWO PIECES ARE RE-IMPLEMENTED HERE BECAUSE THE CONTAINER RUNS origin/main, which
lacks them (each is pinned against the worktree function by
tests/test_explosive_study.py on a synthetic frame):
  * `served_band` — the pick of `bounce_room.demand_read` (highest-`hi` demand
    band whose floor is at/below the print);
  * `intact_replica` — `alert_gates.sweep_read(band, frame=closed, day_low,
    last, day)` after the 2026-09-14 F3 fix: the last SWEEP_WINDOW_BARS CLOSED
    bars, then the event bar appended with volume NaN, `sd_liquidity.find_sweep`,
    then the `broken` rule (not found and min(low) < lo).
`scripts.turning_bullish_keltner_study` is NEVER imported (it runs main() at
import); its `series_for` is transcribed as `kc_series` (pos rounded to 3 dp).

CONVENTIONS (design §2.0): P = `_pre` features (bars < j), entry close[j] — the
intraday board / phone at the print. N = `_at` features (bars <= j), entry
open[j+1] — the 08:15 ET board; N skips the event when open[j+1] <= stop.
Outcomes (all on the HIGH, bars j+1.. only, stop first inside a bar): HIT5@cl
(+5% from the entry before the stop, the engine's bar-part = PRIMARY), HIT5B
(+5% from the band TOP, entry-independent), HIT_LID (first proven lid touch,
CLEAR rows out of this denominator only), HIT5C@20 (close-based twin, printed,
never scored), stop@cl, R/why per clock, k_*, max_gain_pct_20.

UNIT OF ANALYSIS = EPISODES (design §4.0): the first event per symbol, then a
`hold`-bar cooldown; forward 20-clock windows never overlap within a symbol.
The flag used for the bouncing headline is computed WITHIN the bouncing rows
(`episode_dir`) — flagging over all directions would drop exactly the bouncing
events that were preceded by a falling/settling contact, a selection bias; the
all-directions flag (`episode`) is kept on the CSV and used for the `all`
control. Analyst choice, stated.

THE RULE OF READING (design §4.1) is printed above the tables and applied
mechanically; the decision (§4.5) needs the top decile of the combined score to
pass it on ALL THREE OOS splits (date halves, reverse, symbol-disjoint) with the
same sign, the 5%/20% decile-width sweep agreeing, and the two-way
(date x symbol) cluster CI excluding 0. Otherwise status = "no_signal" and the
fallback ordering is `intact` then `room_rank` — the two things that measured.

RUN (read-only; the script is piped to /tmp, never written into /app):
  docker exec -i cheetah-market-app-api-1 sh -c 'cat > /tmp/explosive_study.py' \
      < backend/scripts/explosive_study.py
  # smoke — NOT QUOTABLE (a stride, never the first N names)
  docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -u \
      /tmp/explosive_study.py --stage both --universe broad --floor 120 --stride 18 \
      --out /tmp/explosive_smoke.csv --json /tmp/explosive_smoke.json'
  # full — two detached replays (broad = the boards' universe, cache = survivorship)
  docker exec -d -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -u \
      /tmp/explosive_study.py --stage replay --universe broad --floor 120 \
      --out /tmp/explosive_events.csv > /tmp/explosive_broad.log 2>&1'
  docker exec -d -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -u \
      /tmp/explosive_study.py --stage replay --universe cache --floor 120 \
      --out /tmp/explosive_events_cache.csv > /tmp/explosive_cache.log 2>&1'
  # stats (+ the MEASURED literal), then the liquidity control
  docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -u \
      /tmp/explosive_study.py --stage stats --from-csv /tmp/explosive_events.csv \
      --cache-csv /tmp/explosive_events_cache.csv --json /tmp/explosive_measured.json \
      --emit-measured' | tee report.txt
  docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -u \
      /tmp/explosive_study.py --stage stats --from-csv /tmp/explosive_events.csv \
      --min-dvol 10000000 --json /tmp/explosive_measured_liq.json'
Never during RTH (the hourly cache patch rewrites frames from ~10:00 ET).

DEVIATIONS FROM design.md (each stated, none silent)
  1. The headline episode flag is computed WITHIN the bouncing rows
     (`episode_dir`), not over all directions (`episode`, kept on the CSV for
     the `all` control): the all-direction flag drops every reversal that was
     preceded by a falling/settling contact inside 20 bars (44% of them on the
     smoke) — a selection on the approach path, not a de-clustering.
  2. `risk_pct_N` = (open[j+1] - stop) / open[j+1] x 100, the engine's own
     form of `risk_pct`, so P and N are comparable (design wrote open/stop - 1).
  3. `--universe full_broad` falls back to dict.fromkeys(full + broad) when the
     container's scripts/turning_bullish_amd_study.py predates study_universe.
  4. The replay calls the UNTOUCHED `BQ.events()` once per 300-symbol chunk and
     appends to the CSV (`events()` keeps a list of ~5 KB dicts; two concurrent
     replays of ~150k / ~225k rows would not fit in the container's ~750 MB).
  5. In the null branch there is no score and so no decile: the MDL printed is
     the same date-clustered bootstrap on a RANDOM decile-sized keep of the
     scored half — the study's resolution, labelled "random decile keep".
  6. Spearman rho is computed from average ranks (no scipy in the container).
  7. Every bucket prints ΔHIT5 / Δstop / ΔR CIs, the permutation p and both
     placebo bands; the (room x risk) reweight, the dedupe line and the verdict
     run on the TOP oriented bucket (the one the rule is applied to).
  8. The two-way CI falls back to the larger one-way SE when the CGM variance
     is not positive (flagged on the line).
  9. The controls (all reversal EVENTS; all-direction EPISODES) print point
     tables only — the CI machinery is spent on the headline cohort.
 10. The stats stage reads the CSV without the engine's stationary-bottom
     definition columns (vc_/sh_/shelf_/rp_ prefixes) and the cache table with
     its survivorship columns only (memory; nothing in §4 reads them).

RESULTS — 2026-09-15 (broad, floor 120, clocks [5, 10, 20], primary hit5)
  cohort: 3585 names · 157894 events · 92732 reversal events · 24922 EPISODES · 361 dates · window 2025-03-10 -> 2026-08-14
  base (reversal episodes, P): HIT5@5/10/20 28.5 / 32.6 / 34.2 %  ·  HIT5B@20 31.9 %  ·  HIT_LID@20 21.2 % (n=21942)
        stop@20 74.5 %  ·  R20 mean 0.288 median -1.000 trimmed 0.067  ·  win20 24.9 %  ·  tgt/stop/clk 19/74/7  ·  room 15.63 %  risk 2.57 %  ·  clear 12.0 %
  survivorship (cache universe): names 5273 · HIT5@20 32.7 % · stop@20 77.0 % · Δhit5 vs broad -1.47pp · renames 4 · delisted 8
  liquidity control (min dvol 10000000.0): n 14380 · HIT5@20 34.9 % · stop@20 73.1 %
  splits: S1 no_signal (fit 12687 / scored 12235, MDL 2.22 pp) · S2 no_signal (MDL 2.43 pp) · S3 no_signal (MDL 2.53 pp)
  STATUS: no_signal · convention None · selected [] · fallback intact,room_rank
  per-feature top buckets, convention P:
  rvol20_pre         top=Q1   ΔHIT5@20 -0.41pp CI [-1.96, +1.08]  Δstop +1.25pp  reweighted -1.03pp  → inert
  rvol50_pre         top=Q1   ΔHIT5@20 +0.29pp CI [-1.07, +1.64]  Δstop +1.15pp  reweighted -0.05pp  → inert
  rsi14_pre          top=Q1   ΔHIT5@20 +2.70pp CI [+0.67, +4.83]  Δstop -0.32pp  reweighted +3.46pp  → inert (CI>0 but fails: outside_date_placebo,one_per_date_symbol)
  atr_pct_pre        top=Q5   ΔHIT5@20 -1.02pp CI [-2.64, +0.61]  Δstop +7.81pp  reweighted -2.50pp  → inert
  dvol50_pre         top=Q5   ΔHIT5@20 +0.77pp CI [-0.60, +2.12]  Δstop -2.89pp  reweighted +0.39pp  → inert
  kc_coiled_pre      top=yes  ΔHIT5@20 +1.08pp CI [-2.13, +4.21]  Δstop -2.41pp  reweighted +0.56pp  → inert
  kc_fired_pre       top=yes  ΔHIT5@20 +0.66pp CI [-2.40, +3.70]  Δstop -2.19pp  reweighted +0.17pp  → inert
  kc_pos_pre         top=Q1   ΔHIT5@20 +3.20pp CI [+1.25, +5.25]  Δstop -0.69pp  reweighted +4.12pp  → inert (CI>0 but fails: outside_date_placebo,one_per_date_symbol)
  amd_raided_pre     top=no   ΔHIT5@20 +0.15pp CI [-0.06, +0.38]  Δstop -0.11pp  reweighted +1.13pp  → inert
  cmf20_pre          top=Q1   ΔHIT5@20 +1.19pp CI [-0.46, +2.77]  Δstop +0.36pp  reweighted +1.70pp  → inert
  dist_52wh_pct_pre  top=Q5   ΔHIT5@20 +3.19pp CI [+0.03, +6.29]  Δstop -9.41pp  reweighted +0.73pp  → selects smaller trades
  above_52wl_pct_pre top=Q5   ΔHIT5@20 +0.90pp CI [-2.20, +3.83]  Δstop +5.33pp  reweighted -0.49pp  → inert
  intact_at          top=yes  ΔHIT5@20 +8.30pp CI [+6.66, +9.93]  Δstop -9.16pp  reweighted +3.79pp  → selects smaller trades
  room_pct           top=Q5   ΔHIT5@20 +1.80pp CI [+0.09, +3.53]  Δstop +8.84pp  reweighted n/a  → selects wider stops
  per-feature top buckets, convention N:
  rvol20_at          top=Q5   ΔHIT5@20 -0.46pp CI [-2.09, +1.12]  Δstop -1.13pp  reweighted -0.97pp  → inert
  rvol50_at          top=Q5   ΔHIT5@20 -0.59pp CI [-2.24, +1.03]  Δstop -0.41pp  reweighted -0.96pp  → inert
  rsi14_at           top=Q1   ΔHIT5@20 +1.20pp CI [-0.79, +3.14]  Δstop -0.50pp  reweighted +1.15pp  → inert
  atr_pct_at         top=Q5   ΔHIT5@20 +0.22pp CI [-1.45, +1.89]  Δstop +7.28pp  reweighted -2.65pp  → inert
  dvol50_pre         top=Q5   ΔHIT5@20 +0.20pp CI [-1.25, +1.59]  Δstop -3.23pp  reweighted -0.44pp  → inert
  kc_coiled_at       top=yes  ΔHIT5@20 +2.36pp CI [-2.23, +6.99]  Δstop -4.20pp  reweighted +1.89pp  → inert
  kc_fired_at        top=yes  ΔHIT5@20 +2.28pp CI [-2.25, +6.83]  Δstop -4.44pp  reweighted +1.80pp  → inert
  kc_pos_at          top=Q1   ΔHIT5@20 +1.20pp CI [-0.82, +3.25]  Δstop +0.74pp  reweighted +1.56pp  → inert
  amd_raided_at      top=yes  ΔHIT5@20 +0.95pp CI [-0.60, +2.47]  Δstop -0.49pp  reweighted +0.52pp  → inert
  cmf20_at           top=Q1   ΔHIT5@20 +0.70pp CI [-1.02, +2.30]  Δstop +0.55pp  reweighted +0.97pp  → inert
  dist_52wh_pct_pre  top=Q5   ΔHIT5@20 +2.17pp CI [-0.93, +5.05]  Δstop -8.72pp  reweighted -0.09pp  → inert
  above_52wl_pct_pre top=Q5   ΔHIT5@20 +1.89pp CI [-1.25, +4.92]  Δstop +4.48pp  reweighted +0.08pp  → inert
  intact_at          top=yes  ΔHIT5@20 +6.90pp CI [+5.44, +8.41]  Δstop -7.99pp  reweighted +3.19pp  → selects smaller trades
  room_pct           top=Q5   ΔHIT5@20 +2.77pp CI [+1.10, +4.45]  Δstop +8.95pp  reweighted n/a  → selects wider stops
  close_pos_at       top=Q1   ΔHIT5@20 +0.35pp CI [-1.46, +2.19]  Δstop +2.01pp  reweighted +0.19pp  → inert
  day_ret_at         top=Q5   ΔHIT5@20 +1.96pp CI [+0.06, +3.90]  Δstop -2.77pp  reweighted +0.06pp  → selects smaller trades
  pocket_pivot_at    top=yes  ΔHIT5@20 +0.84pp CI [-2.80, +4.29]  Δstop -4.78pp  reweighted -1.38pp  → inert
"""
from __future__ import annotations

import argparse
import json
import math
import os
import pprint
import sys
import time
import types
import zlib
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from studies import bounce_quality_study as BQ
from supply_demand import alert_gates as AG
from supply_demand import amd as A
from supply_demand import demand_reentry as DR
from supply_demand import keltner as K
from supply_demand import mood as MD
from supply_demand import patterns as PT
from supply_demand import price_zones as PZ
from supply_demand import sd_liquidity as SL
from supply_demand import turning_bullish as TB
from supply_demand import zone_store as ZS
from sepa import breakout_audit as BA
from sepa import prices
from sepa import symbols as SY
from sepa import volume as V

SCRIPT = "backend/scripts/explosive_study.py"

# ── every threshold IMPORTED; the 5% is his and it is the only typed number ──
FIVE_PCT = AG.ALERT_MIN_ROOM_PCT            # 5.0 — Ajay's one number
STOP_BUFFER_PCT = AG.STOP_BUFFER_PCT        # 0.5 — stop = band floor less this
FLOOR_DEFAULT = ZS.MIN_BARS                 # 120 — the live board draws bands from here
HOLD_DEFAULT = BQ.HOLD_SESSIONS             # 20 — the reported clock
CLOCKS_DEFAULT = (5, 10, 20)                # quick is the headline (design §1.4)
BOX_BARS = PZ.LOOKBACK_BARS                 # 252 — the 52-week box
RVOL_SHORT = A.VOL_REF_BARS                 # 20 — "volume burst"
RVOL_LONG = BA.VOL_AVG_BARS                 # 50 — the boards' avg_vol_50
SWEEP_WINDOW = AG.SWEEP_WINDOW_BARS         # 15 — the sweep read's window
ATR14 = ZS.ATR_PERIOD                       # 14 — the zone_store atr twin
RSI_PERIOD = MD.RSI_PERIOD                  # 14
POCKET_LOOKBACK = 10                        # sepa.volume._pocket_pivot's own default
LIQ_TIERS = ((DR.LIQ_DEEP_USD, "deep"), (DR.LIQ_OK_USD, "ok"), (DR.LIQ_THIN_USD, "thin"))
CMF_IN, CMF_OUT = V.CMF_INFLOW_THRESHOLD, V.CMF_OUTFLOW_THRESHOLD
MIN_DVOL_CONTROL = DR.LIQ_OK_USD            # the board's default min_tier "ok"
RSI_SLOPE_BARS = BQ.STRUCTURE_SWING_WINDOW  # 5 — typed BY PROXY -> exploratory only
VOL_BURST_BARS = TB.MAX_RAID_BARS_AGO       # 3 — typed BY PROXY -> exploratory only
DIRECTION_BASE = AG.PUSH_DIRECTIONS[0]      # "bouncing" — what pushes today
SEED_BOOT, SEED_PLACEBO, SEED_TWOWAY = 7, 3, 7    # engine seeds
DECILE, TOP5, TOP20 = 0.10, 0.05, 0.20      # the decision cut and its width sweep
MIN_BUCKET_N = 30                           # below this a bucket prints "too small"

# Pre-registered sets — FROZEN before the first full run (design §3).
PREREG_P = ("rvol20_pre", "rvol50_pre", "rsi14_pre", "atr_pct_pre", "dvol50_pre",
            "kc_coiled_pre", "kc_fired_pre", "kc_pos_pre", "amd_raided_pre", "cmf20_pre",
            "dist_52wh_pct_pre", "above_52wl_pct_pre", "intact_at", "room_pct")
PREREG_N = ("rvol20_at", "rvol50_at", "rsi14_at", "atr_pct_at", "dvol50_pre",
            "kc_coiled_at", "kc_fired_at", "kc_pos_at", "amd_raided_at", "cmf20_at",
            "dist_52wh_pct_pre", "above_52wl_pct_pre", "intact_at", "room_pct",
            "close_pos_at", "day_ret_at", "pocket_pivot_at")
assert len(PREREG_P) == 14 and len(PREREG_N) == 17

EXPLORATORY = ("rsi_slope5_pre", "vol_burst3_pre", "atr14_pct_pre", "kc_breaking_pre",
               "kc_breaking_at", "kc_width_ratio_pre", "kc_coil_pre", "kc_on_pre",
               "kc_rise_pre", "amd_grade_pre", "amd_grade_at", "amd_raid_ago_pre",
               "amd_raid_vol_pre", "amd_raid_depth_pre", "intact_state_at",
               "intact_ev_state_at", "stophunt_state", "intact_ev_at", "intact_sh",
               "dvol_tier_pre", "cmf_state_pre", "cmf_state_at", "mood", "knife",
               "n_bands", "risk_pct", "served_is_event")
BOOL_FEATS = {"kc_coiled_pre", "kc_coiled_at", "kc_fired_pre", "kc_fired_at",
              "kc_breaking_pre", "kc_breaking_at", "kc_on_pre", "kc_on_at", "kc_rise_pre",
              "kc_rise_at", "amd_raided_pre", "amd_raided_at", "intact_at", "intact_ev_at",
              "intact_sh", "pocket_pivot_at", "clear", "knife", "gap_N", "served_is_event",
              "episode", "episode_dir"}
STATE_FEATS = {"amd_grade_pre", "amd_grade_at", "intact_state_at", "intact_ev_state_at",
               "stophunt_state", "dvol_tier_pre", "cmf_state_pre", "cmf_state_at", "dir"}
OUTCOMES = ("hit5", "hit5b", "hit_lid")


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and not math.isinf(v) else None


def _nanmean(a) -> float:
    a = np.asarray(a, dtype=float)
    a = a[np.isfinite(a)]
    return float(a.mean()) if a.size else float("nan")


def spearman(x, y) -> float:
    """Spearman rho from average ranks (no scipy in the venv / container)."""
    x = pd.Series(np.asarray(x, dtype=float))
    y = pd.Series(np.asarray(y, dtype=float))
    m = x.notna() & y.notna()
    if m.sum() < 3:
        return float("nan")
    rx, ry = x[m].rank().to_numpy(), y[m].rank().to_numpy()
    if rx.std() == 0 or ry.std() == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def P(*args) -> None:
    print(*args, flush=True)


def _today_et() -> str:
    return datetime.now(ZoneInfo("America/New_York")).date().isoformat()


# ═════════════════════════════════════════════════════════════════════════════
# THE TWO CONTAINER REPLICAS (pinned against the worktree functions by the tests)
# ═════════════════════════════════════════════════════════════════════════════
def served_band(px, demand_zones) -> Optional[dict]:
    """Replica of bounce_room.demand_read's PICK (bounce_room.py:504): the
    highest-`hi` demand band whose floor is at/below the print. {"lo","hi",
    "touches"} or None — the band the tile/row path keys `intact` on."""
    p = _f(px)
    if p is None or p <= 0:
        return None
    cands = []
    for b in demand_zones or []:
        if not isinstance(b, dict):
            continue
        if str(b.get("kind") or "demand").lower() != "demand":
            continue
        lo, hi = _f(b.get("lo")), _f(b.get("hi"))
        if lo is None or hi is None or lo > p:
            continue
        cands.append((lo, hi, int(_f(b.get("touches")) or 0)))
    if not cands:
        return None
    lo, hi, touches = max(cands, key=lambda t: t[1])
    return {"lo": lo, "hi": hi, "touches": touches}


def event_bar_row(close_j: float, low_j: float) -> dict:
    """The session bar `alert_gates.with_session_bar` appends: open = close =
    the print, high = max(print, low), low = min(print, low), volume NaN ON
    PURPOSE (a partial session's volume would always read quiet)."""
    c, dl = float(close_j), float(low_j)
    return {"open": c, "high": max(c, dl), "low": min(c, dl), "close": c,
            "volume": float("nan")}


def intact_replica(closed: pd.DataFrame, lo, hi, day_low, last,
                   window: int = SWEEP_WINDOW) -> Optional[str]:
    """Replica of `AG.sweep_read(band, frame=closed, day_low=low[j],
    last=close[j], day=date_j)["state"]` (worktree alert_gates.py:729, append
    path): the last `window` CLOSED bars + the event bar, `find_sweep`, then
    the `broken` rule. None when it cannot be computed (fails closed)."""
    lo_f, hi_f = _f(lo), _f(hi)
    if closed is None or len(closed) < window + 2:
        return None
    if lo_f is None or hi_f is None or not (0 < lo_f <= hi_f):
        return None
    dl, px = _f(day_low), _f(last)
    cols = [k for k in ("open", "high", "low", "close", "volume") if k in closed.columns]
    if dl is None or dl <= 0:
        w = closed.iloc[-window:][cols]              # no day low = the old read
    else:
        base = closed.iloc[-window:][cols]
        row = {k: float("nan") for k in cols}
        for k, val in event_bar_row(px if (px is not None and px > 0) else dl, dl).items():
            if k in row:
                row[k] = val
        w = pd.concat([base, pd.DataFrame([row], columns=cols).astype(float)], ignore_index=True)
    sw = SL.find_sweep(w, lo_f, hi_f)
    state = sw.get("state") or "intact"
    if not sw.get("found") and float(w["low"].min()) < lo_f:
        state = "broken"
    return state


def intact_stop_hunt(f: pd.DataFrame, j: int, floor_: float, entry: float,
                     window: int = SWEEP_WINDOW) -> Optional[str]:
    """The stop_hunt_study.py:74-78 window: `window - 1` closed bars + the FULL
    event bar (volume included). The +8.60pp was measured on THIS. Printed for
    the reconciliation line only, never scored."""
    if j - window + 1 < 0:
        return None
    w = f.iloc[j - window + 1:j + 1]
    sw = SL.find_sweep(w, floor_, max(float(entry), floor_ * 1.001))
    if sw.get("found"):
        return "swept"
    if float(w["low"].min()) < floor_:
        return "broken"
    return "intact"


# ═════════════════════════════════════════════════════════════════════════════
# FEATURE SERIES (causal; computed once per frame, indexed at j-1 / j)
# ═════════════════════════════════════════════════════════════════════════════
def kc_series(f: pd.DataFrame) -> dict:
    """Keltner state per bar. TRANSCRIBED from scripts/turning_bullish_keltner_
    study.series_for (that file calls main() at import). `pos` rounded to 3 dp
    as series_for and keltner.channel() both do. `fired` = the KC study's
    measured state (includes breaking bars); `coiled` = fired & pos <= 1.0 ==
    turning_bullish.keltner_verdict grade "coiled_up"; `breaking` = valid &
    pos > 1.0 == grade "breaking_up" (graded FIRST, turning_bullish.py:189)."""
    close = f["close"].astype(float)
    mid = close.ewm(span=K.EMA_LEN, adjust=False).mean()
    atr = K._atr(f, K.ATR_LEN)
    upper, lower = mid + K.MULT * atr, mid - K.MULT * atr
    span = (upper - lower).to_numpy()
    n = len(f)
    pos = np.full(n, np.nan)
    ok = np.isfinite(span) & (span > 0)
    pos[ok] = np.round((close.to_numpy()[ok] - lower.to_numpy()[ok]) / span[ok], 3)
    k_up = (mid + K.SQUEEZE_MULT * atr).to_numpy()
    k_dn = (mid - K.SQUEEZE_MULT * atr).to_numpy()
    bb_mid = close.rolling(K.BB_LEN).mean()
    bb_sd = close.rolling(K.BB_LEN).std(ddof=0)
    b_up = (bb_mid + K.BB_STD * bb_sd).to_numpy()
    b_dn = (bb_mid - K.BB_STD * bb_sd).to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        on = (b_up < k_up) & (b_dn > k_dn)
        kw = k_up - k_dn
        width_ratio = np.where(np.isfinite(kw) & (kw > 0), (b_up - b_dn) / kw, np.nan)
    on = np.nan_to_num(on, nan=False).astype(bool)
    released = np.zeros(n, bool)
    released[1:] = on[:-1] & ~on[1:]
    bars, ended, run = np.zeros(n, int), np.zeros(n, int), 0
    for i in range(n):
        if on[i]:
            run += 1
        else:
            if run:
                ended[i] = run
            run = 0
        bars[i] = run if on[i] else 0
    coil_len = np.where(on, bars, ended)
    mid_a = mid.to_numpy()
    rise = np.zeros(n, bool)
    rise[TB.MID_SLOPE_BARS:] = mid_a[TB.MID_SLOPE_BARS:] > mid_a[:-TB.MID_SLOPE_BARS]
    atr_a = atr.to_numpy()
    valid = np.isfinite(pos) & np.isfinite(mid_a) & np.isfinite(atr_a) & (atr_a > 0)
    valid[:K.MIN_BARS + 1] = False          # squeeze() needs MIN_BARS + 2 rows
    fired = valid & (on | released) & (pos >= TB.COILED_MIN_POSITION) & rise
    coiled = fired & (pos <= 1.0)
    breaking = valid & (pos > 1.0)
    c_a = close.to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        atr_pct = np.where(c_a > 0, atr_a / c_a * 100.0, np.nan)
    return {"pos": pos, "on": on, "released": released, "coil_len": coil_len,
            "rise": rise, "fired": fired, "coiled": coiled, "breaking": breaking,
            "valid": valid, "width_ratio": width_ratio, "atr_pct": atr_pct}


def rsi_series(close: np.ndarray, period: int = RSI_PERIOD) -> np.ndarray:
    """mood._rsi (Cutler / SMA) as a series: value at i == mood._rsi(close[:i+1])."""
    s = pd.Series(np.asarray(close, dtype=float))
    delta = s.diff()
    gain = delta.clip(lower=0).rolling(period).mean().to_numpy()
    loss = (-delta.clip(upper=0)).rolling(period).mean().to_numpy()
    out = np.full(len(s), np.nan)
    ok = np.isfinite(gain) & np.isfinite(loss)
    with np.errstate(invalid="ignore", divide="ignore"):
        rs = gain / loss
        val = 100.0 - (100.0 / (1.0 + rs))
    out[ok] = val[ok]
    zero = ok & (loss == 0)
    out[zero] = np.where(gain[zero] > 0, 100.0, 50.0)
    return out


def cmf_series(h, l, c, v, period: int = 20) -> np.ndarray:
    """sepa.volume._chaikin_money_flow(df.iloc[:i+1], period)["cmf"] as a series
    (zero-range bars contribute no money-flow volume, as the function's
    `replace(0, pd.NA)` + skipna sum does; total volume <= 0 -> NaN)."""
    h, l, c, v = (np.asarray(x, dtype=float) for x in (h, l, c, v))
    rng = h - l
    with np.errstate(invalid="ignore", divide="ignore"):
        mfm = np.where(rng > 0, ((c - l) - (h - c)) / np.where(rng > 0, rng, 1.0), np.nan)
    mfv = mfm * v
    mfv_sum = pd.Series(np.nan_to_num(mfv, nan=0.0)).rolling(period).sum().to_numpy()
    vol_sum = pd.Series(np.nan_to_num(v, nan=0.0)).rolling(period).sum().to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(vol_sum > 0, mfv_sum / vol_sum, np.nan)
    return out


def atr14_series(h, l, c, period: int = ATR14) -> np.ndarray:
    """patterns.atr(df.iloc[:i+1], period) as a series (simple mean of TR; a
    non-positive value reads None there -> NaN here)."""
    h, l, c = (pd.Series(np.asarray(x, dtype=float)) for x in (h, l, c))
    prev = c.shift(1)
    tr = pd.concat([h - l, (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    out = tr.rolling(period).mean().to_numpy()
    return np.where(out > 0, out, np.nan)


def _rvol(vol: np.ndarray, i: int, ref: int) -> float:
    """vol[i] over the mean of the `ref` bars before it — amd._vol_ratio's
    arithmetic (prior-only denominator). NaN when unknown, never 0."""
    if i < 1 or i >= len(vol):
        return np.nan
    prev = vol[max(0, i - ref):i]
    prev = prev[np.isfinite(prev)]
    if prev.size == 0 or prev.mean() <= 0 or not np.isfinite(vol[i]):
        return np.nan
    return float(vol[i] / prev.mean())


def _amd(sub: pd.DataFrame) -> dict:
    v = TB.amd_verdict(sub) or {}
    return {"grade": v.get("grade") or "none", "raid_ago": v.get("raid_bars_ago"),
            "raid_vol": v.get("raid_vol_ratio"), "raid_depth": v.get("raid_depth_pct")}


# ═════════════════════════════════════════════════════════════════════════════
# OUTCOMES — bars j+1.. only, the STOP checked first inside a bar (engine rule)
# ═════════════════════════════════════════════════════════════════════════════
def _first_k(mask: np.ndarray) -> Optional[int]:
    idx = np.flatnonzero(mask)
    return int(idx[0]) + 1 if idx.size else None


def outcome_block(fh, fl, fc, entry, stop, target, band_hi, clocks, hold,
                  suffix: str = "") -> dict:
    """Every outcome for one entry convention on the forward bars fh/fl/fc
    (bars j+1..j+max_clock). `entry` is close[j] (P) or open[j+1] (N); the stop
    and target are the same in both. Mirrors events(): the first of stop/target
    decides, ties (same bar) go to the STOP; else exit at close[j+cl]."""
    fh, fl, fc = (np.asarray(x, dtype=float) for x in (fh, fl, fc))
    up5 = float(entry) * (1.0 + FIVE_PCT / 100.0)
    ks = _first_k(fl <= stop)
    kt = _first_k(fh >= float(target)) if target is not None else None
    k5 = _first_k(fh >= up5)
    k5b = _first_k(fh >= float(band_hi) * (1.0 + FIVE_PCT / 100.0)) if band_hi else None
    k5c = _first_k(fc >= up5)
    if ks is not None and (kt is None or ks <= kt):
        first_k, first_px, first_why = ks, float(stop), "stop"
    elif kt is not None:
        first_k, first_px, first_why = kt, float(target), "target"
    else:
        first_k = first_px = first_why = None

    def before_stop(k, cl):
        return k is not None and k <= cl and (ks is None or k < ks)

    out = {"k_5pct" + suffix: k5 if k5 is not None else np.nan,
           "k_stop" + suffix: ks if ks is not None else np.nan,
           "k_target" + suffix: kt if kt is not None else np.nan}
    risk = float(entry) - float(stop)
    for cl in sorted(set(clocks) | {hold}):
        out["hit5_%d%s" % (cl, suffix)] = float(before_stop(k5, cl))
        out["hit5b_%d%s" % (cl, suffix)] = float(before_stop(k5b, cl)) if band_hi else np.nan
        out["hit_lid_%d%s" % (cl, suffix)] = (float(before_stop(kt, cl))
                                             if target is not None else np.nan)
        out["stop_%d%s" % (cl, suffix)] = float(first_why == "stop" and first_k <= cl)
        if first_k is not None and first_k <= cl:
            ex, why = first_px, first_why
        else:
            ex, why = float(fc[cl - 1]), "clock"
        out["R%d%s" % (cl, suffix)] = (ex - float(entry)) / risk
        out["why%d%s" % (cl, suffix)] = why
    out["hit5c_%d%s" % (hold, suffix)] = float(before_stop(k5c, hold))
    out["max_gain_pct_%d%s" % (hold, suffix)] = (float(fh[:hold].max()) / float(entry) - 1.0) * 100.0
    return out


def next_open_block(fo_next, fh, fl, fc, stop, target, band_hi, clocks, hold) -> dict:
    """Convention N: entry = open[j+1]; the event is SKIPPED (every outcome
    NaN, gap_N True) when the open is at/under the stop."""
    o = _f(fo_next)
    if o is None or o <= stop:
        keys = outcome_block(np.ones(max(max(clocks), hold)) * 1e9, np.ones(max(max(clocks), hold)),
                             np.ones(max(max(clocks), hold)), 1.0, 0.5, None, None,
                             clocks, hold, suffix="_N")
        out = {k: (np.nan if not isinstance(v, str) else None) for k, v in keys.items()}
        out.update({"entry_N": o if o is not None else np.nan, "gap_N": True,
                    "risk_pct_N": np.nan})
        return out
    out = outcome_block(fh, fl, fc, o, stop, target, band_hi, clocks, hold, suffix="_N")
    out.update({"entry_N": o, "gap_N": False, "risk_pct_N": (o - stop) / o * 100.0})
    return out


# ═════════════════════════════════════════════════════════════════════════════
# THE TAIL-BAR RULE (design §1.5) and the frame wrapper
# ═════════════════════════════════════════════════════════════════════════════
TAIL = {"names": 0, "today": 0, "phantom": 0, "nonpos_names": 0, "nonpos_rows": 0}
_SEEN: set = set()                        # the wrapper runs in both passes; count a name once


def drop_nonpositive(f: pd.DataFrame, log: Optional[dict] = None) -> pd.DataFrame:
    """Drop rows whose open/high/low/close is not > 0 — the same hygiene BQ._frame
    already applies to NaN, extended to zeros and negatives.

    A 0.0 swing low becomes the seed of a price_zones cluster and then its own
    divisor: `(price - cur[0][0]) / cur[0][0]` at price_zones.py:148 raises
    ZeroDivisionError, which kills the whole 300-symbol chunk (BQ.events has no
    per-symbol guard). 12 price_cache docs carry such a bar — AMMJ, EEGI, ELOX,
    ESNC, MJLB, MWWC, RONN, SING, SRNE, WHEN, YAYO, ZVOI. NONE of them is in
    `broad` (verified server-side against the whole collection), all of the
    >=142-bar ones are in `cache`: the guard is a no-op for the boards' universe
    and only bites on the survivorship replay, whose line reports the count."""
    if f is None or len(f) == 0:
        return f
    ok = np.ones(len(f), dtype=bool)
    for c in ("open", "high", "low", "close"):
        ok &= pd.to_numeric(f[c], errors="coerce").to_numpy(dtype=float) > 0.0
    n_bad = int((~ok).sum())
    if not n_bad:
        return f
    f = f.loc[ok]
    if log is not None:
        log["nonpos_names"] += 1
        log["nonpos_rows"] += n_bad
    return f.reset_index(drop=True)


def apply_tail_rule(f: pd.DataFrame, today: str, log: Optional[dict] = None) -> pd.DataFrame:
    """1. drop the last row when it is stamped `today` (a partial session);
    2. then prices._drop_phantom_tail's equality test on a date-indexed copy
    (an echo bar: same close, volume within 0.5%). Counts each drop."""
    if f is None or len(f) == 0:
        return f
    if str(f["d"].iloc[-1])[:10] == str(today)[:10]:
        f = f.iloc[:-1]
        if log is not None:
            log["today"] += 1
    if len(f) >= 2:
        g = f.set_index(pd.to_datetime(f["d"]))
        n = len(prices._drop_phantom_tail(g))
        if n < len(f):
            f = f.iloc[:n]
            if log is not None:
                log["phantom"] += 1
    return f.reset_index(drop=True)


_ORIG_FRAME = BQ._frame


def frame_with_tail_rule(coll, sym):
    f = _ORIG_FRAME(coll, sym)
    if f is None:
        return None
    if sym in _SEEN:
        return apply_tail_rule(drop_nonpositive(f, None), _today_et(), None)
    _SEEN.add(sym)
    TAIL["names"] += 1
    return apply_tail_rule(drop_nonpositive(f, TAIL), _today_et(), TAIL)


# ═════════════════════════════════════════════════════════════════════════════
# UNIVERSE (three modes; the symbol list is monkeypatched into BQ in-process)
# ═════════════════════════════════════════════════════════════════════════════
UNIVERSE_MODES = ("broad", "full_broad", "cache")


def symbols_for(mode: str, need_bars: int, stride: int = 1, names: int = 0) -> list:
    from sepa import universe as U
    if mode == "broad":
        syms = U.load_universe("broad")
    elif mode == "full_broad":
        try:
            from scripts.turning_bullish_amd_study import study_universe
            syms = study_universe()
        except ImportError:                      # the container's copy predates it
            syms = list(dict.fromkeys(U.load_universe("full") + U.load_universe("broad")))
    elif mode == "cache":
        coll = prices._get_mongo()
        if coll is None:
            raise RuntimeError("price_cache unavailable")
        cur = coll.find({"bars.%d" % (need_bars - 1): {"$exists": True}}, {"symbol": 1, "_id": 0})
        syms = [d["symbol"] for d in cur if d.get("symbol")]
    else:
        raise ValueError("universe must be one of %s" % (UNIVERSE_MODES,))
    syms = sorted(dict.fromkeys(str(s).upper() for s in syms))
    if stride > 1:
        syms = syms[::stride]
    if names:
        syms = syms[:names]
    return syms


# ═════════════════════════════════════════════════════════════════════════════
# FEATURES — a post-hoc LEFT join on the engine's rows (hard assert on the count)
# ═════════════════════════════════════════════════════════════════════════════
def features_for_symbol(sym: str, f: pd.DataFrame, ev: pd.DataFrame, hold: int,
                        clocks, geom: dict, counters: dict) -> list:
    pos_of = {d: i for i, d in enumerate(f["d"].tolist())}
    o = f["open"].to_numpy(dtype=float)
    h = f["high"].to_numpy(dtype=float)
    l = f["low"].to_numpy(dtype=float)
    c = f["close"].to_numpy(dtype=float)
    v = f["volume"].to_numpy(dtype=float)
    n = len(f)
    dvol = pd.Series(c * v).rolling(RVOL_LONG, min_periods=RVOL_LONG).median().to_numpy()
    kc = kc_series(f)
    rsi = rsi_series(c)
    cmf = cmf_series(h, l, c, v)
    atr14 = atr14_series(h, l, c)
    max_clock = max(max(clocks), hold)
    buf = 1.0 - STOP_BUFFER_PCT / 100.0
    out = []
    for r in ev.itertuples(index=False):
        j = pos_of.get(str(r.date))
        if j is None or j < 2 or j + max_clock >= n:
            counters["no_bar"] += 1
            continue
        px, stop = float(r.entry), float(r.stop)
        target = _f(r.target)
        prev, day_low = float(c[j - 1]), float(l[j])
        row = {"symbol": sym, "date": str(r.date), "bar_idx": j}
        # ── bands at j from bars STRICTLY BEFORE j (the engine's own call) ──
        z = PZ.compute(f.iloc[max(0, j - BOX_BARS):j], last_price=px, max_zones=None, **geom)
        dz = (z or {}).get("demand_zones") or []
        hits = [b for b in dz if AG.demand_proximity_gate(px, b)
                and isinstance(AG.approach_read(px, b, prev, day_low), dict)]
        band = max(hits, key=lambda b: float(b["lo"])) if hits else None
        served = served_band(px, dz)
        if band is None:
            counters["no_band"] += 1
            band_lo = band_hi = np.nan
        else:
            band_lo, band_hi = float(band["lo"]), float(band["hi"])
            if abs(band_lo * buf - stop) > 1e-6:
                counters["band_mismatch"] += 1
        row.update({"band_lo": band_lo, "band_hi": band_hi,
                    "band_touches": int(band.get("touches") or 0) if band else np.nan,
                    "served_lo": served["lo"] if served else np.nan,
                    "served_hi": served["hi"] if served else np.nan,
                    "served_touches": served["touches"] if served else np.nan,
                    "served_is_event": (bool(served and band and abs(served["lo"] - band_lo) < 1e-9
                                             and abs(served["hi"] - band_hi) < 1e-9)
                                        if (served and band) else np.nan),
                    "open_next": float(o[j + 1])})
        # ── momentum / volume: pre = index j-1 (bars < j), at = index j ──
        pre, at = f.iloc[:j], f.iloc[:j + 1]
        row["rsi14_pre"], row["rsi14_at"] = float(rsi[j - 1]), float(rsi[j])
        row["rvol20_pre"], row["rvol20_at"] = _rvol(v, j - 1, RVOL_SHORT), _rvol(v, j, RVOL_SHORT)
        row["rvol50_pre"], row["rvol50_at"] = _rvol(v, j - 1, RVOL_LONG), _rvol(v, j, RVOL_LONG)
        row["dvol50_pre"] = float(dvol[j - 1]) if np.isfinite(dvol[j - 1]) else np.nan
        row["cmf20_pre"], row["cmf20_at"] = float(cmf[j - 1]), float(cmf[j])
        row["pocket_pivot_at"] = bool(V._pocket_pivot(at, lookback=POCKET_LOOKBACK).get("is_pocket_pivot"))
        row["day_ret_at"] = (c[j] / c[j - 1] - 1.0) * 100.0 if c[j - 1] > 0 else np.nan
        row["close_pos_at"] = ((c[j] - l[j]) / (h[j] - l[j])) if h[j] > l[j] else np.nan
        row["atr14_pct_pre"] = (atr14[j - 1] / c[j - 1] * 100.0
                                if np.isfinite(atr14[j - 1]) and c[j - 1] > 0 else np.nan)
        for tag, i in (("pre", j - 1), ("at", j)):
            row["kc_pos_" + tag] = float(kc["pos"][i])
            row["kc_on_" + tag] = bool(kc["on"][i])
            row["kc_coil_" + tag] = int(kc["coil_len"][i])
            row["kc_rise_" + tag] = bool(kc["rise"][i])
            row["kc_fired_" + tag] = bool(kc["fired"][i])
            row["kc_coiled_" + tag] = bool(kc["coiled"][i])
            row["kc_breaking_" + tag] = bool(kc["breaking"][i])
            row["kc_width_ratio_" + tag] = float(kc["width_ratio"][i])
            row["atr_pct_" + tag] = float(kc["atr_pct"][i])
        for tag, sub in (("pre", pre), ("at", at)):
            a = _amd(sub)
            row["amd_grade_" + tag] = a["grade"]
            row["amd_raided_" + tag] = a["grade"] == TB.AMD_TURNING
            row["amd_raid_ago_" + tag] = _f(a["raid_ago"]) if a["raid_ago"] is not None else np.nan
            row["amd_raid_vol_" + tag] = _f(a["raid_vol"]) if a["raid_vol"] is not None else np.nan
            row["amd_raid_depth_" + tag] = _f(a["raid_depth"]) if a["raid_depth"] is not None else np.nan
        # ── the 52-week box on closed bars before j; NaN under 252 bars ──
        if j >= BOX_BARS:
            hi52, lo52 = float(np.nanmax(h[j - BOX_BARS:j])), float(np.nanmin(l[j - BOX_BARS:j]))
            row["dist_52wh_pct_pre"] = (c[j - 1] / hi52 - 1.0) * 100.0 if hi52 > 0 else np.nan
            row["above_52wl_pct_pre"] = (c[j - 1] / lo52 - 1.0) * 100.0 if lo52 > 0 else np.nan
        else:
            row["dist_52wh_pct_pre"] = row["above_52wl_pct_pre"] = np.nan
        # ── exploratory (typed by proxy — printed, never scored) ──
        row["rsi_slope5_pre"] = (float(rsi[j - 1] - rsi[j - 1 - RSI_SLOPE_BARS])
                                 if j - 1 - RSI_SLOPE_BARS >= 0 else np.nan)
        row["vol_burst3_pre"] = float(np.nanmax([_rvol(v, i, RVOL_SHORT)
                                                 for i in range(j - VOL_BURST_BARS, j)]))
        # ── intact: the served band (what the board keys on) + controls ──
        st = intact_replica(pre, served["lo"], served["hi"], day_low, px) if served else None
        row["intact_state_at"] = st if st else np.nan
        row["intact_at"] = (st == "intact") if st else np.nan
        if band is not None:
            st_ev = intact_replica(pre, band_lo, band_hi, day_low, px)
            row["intact_ev_state_at"] = st_ev if st_ev else np.nan
            row["intact_ev_at"] = (st_ev == "intact") if st_ev else np.nan
            sh = intact_stop_hunt(f, j, band_lo, px)
            row["stophunt_state"] = sh if sh else np.nan
            row["intact_sh"] = (sh == "intact") if sh else np.nan
        else:
            row["intact_ev_state_at"] = row["intact_ev_at"] = np.nan
            row["stophunt_state"] = row["intact_sh"] = np.nan
        # ── outcomes under both conventions ──
        fh, fl, fc = h[j + 1:j + 1 + max_clock], l[j + 1:j + 1 + max_clock], c[j + 1:j + 1 + max_clock]
        blk = outcome_block(fh, fl, fc, px, stop, target, band_hi if band else None, clocks, hold)
        for cl in sorted(set(clocks) | {hold}):
            eng = getattr(r, "R%d" % cl, None)
            if eng is not None and eng == eng and abs(float(eng) - blk["R%d" % cl]) > 1e-6:
                counters["R_mismatch"] += 1
            blk.pop("R%d" % cl)                      # the engine's R{cl}/why{cl} stay authoritative
            blk.pop("why%d" % cl)
        row.update(blk)
        row.update(next_open_block(o[j + 1], fh, fl, fc, stop, target,
                                   band_hi if band else None, clocks, hold))
        out.append(row)
    return out


def join_features(E: pd.DataFrame, F: pd.DataFrame) -> pd.DataFrame:
    """LEFT join on ["symbol","date"] with the HARD assert — the cohort never
    shrinks (or grows) silently; rows without features land in the NaN bucket."""
    if F is None or F.empty:
        X = E.copy()
    else:
        X = E.merge(F, on=["symbol", "date"], how="left")
    assert len(X) == len(E), "feature join changed the cohort: %d -> %d" % (len(E), len(X))
    return X


def flag_episodes(X: pd.DataFrame, hold: int, within: Optional[str] = None) -> pd.Series:
    """Episode = the first event per symbol, then a `hold`-bar cooldown (bar
    positions, not dates); forward `hold`-windows never overlap within a
    symbol. `within` = a column whose value must also match (the per-direction
    flag)."""
    flag = pd.Series(False, index=X.index)
    keys = ["symbol"] + ([within] if within else [])
    for _, g in X.sort_values(["symbol", "bar_idx"]).groupby(keys, sort=False):
        last = None
        for idx, j in zip(g.index, g["bar_idx"].to_numpy()):
            if last is None or j - last >= hold:
                flag.at[idx] = True
                last = j
    return flag


def add_features(E: pd.DataFrame, hold: int, clocks, counters: dict) -> pd.DataFrame:
    coll = prices._get_mongo()
    geom = DR.zone_geom()
    rows = []
    for sym, ev in E.groupby("symbol", sort=True):
        f = frame_with_tail_rule(coll, sym)
        if f is None:
            counters["no_frame"] += 1
            continue
        rows.extend(features_for_symbol(sym, f, ev, hold, clocks, geom, counters))
    F = pd.DataFrame(rows)
    X = join_features(E, F)
    X["bar_idx"] = pd.to_numeric(X["bar_idx"], errors="coerce")
    X["episode"] = flag_episodes(X, hold)
    X["episode_dir"] = flag_episodes(X, hold, within="dir")
    return X


# ═════════════════════════════════════════════════════════════════════════════
# STAGE: replay
# ═════════════════════════════════════════════════════════════════════════════
def replay(a) -> None:
    t0 = time.time()
    clocks = tuple(int(x) for x in str(a.clocks).split(","))
    hold, floor = int(a.hold), int(a.floor)
    need = floor + hold + 2
    syms = symbols_for(a.universe, need, stride=a.stride, names=a.names)
    if a.names:
        P("NOT QUOTABLE — smoke (--names %d)" % a.names)
    BQ.CLOCKS = clocks                          # events() reads the module global at call time
    BQ._frame = frame_with_tail_rule            # the tail-bar rule on every frame
    P("replay  universe=%s  n=%d  floor=%d  hold=%d  clocks=%s  stride=%d  min_dvol=%g  today=%s"
      % (a.universe, len(syms), floor, hold, clocks, a.stride, a.min_dvol, _today_et()))
    counters = {"no_bar": 0, "no_band": 0, "band_mismatch": 0, "R_mismatch": 0, "no_frame": 0}
    n_rows, first = 0, True
    chunk = max(1, int(a.chunk))
    if os.path.exists(a.out):
        os.remove(a.out)
    for k0 in range(0, len(syms), chunk):
        part = syms[k0:k0 + chunk]
        BQ.universe = types.SimpleNamespace(load_universe=lambda uni=None, ch=part: list(ch))
        E = BQ.events(hold, floor, 0, float(a.min_dvol), a.universe)
        if E.empty:
            continue
        X = add_features(E, hold, clocks, counters)
        X.to_csv(a.out, index=False, mode="a", header=first)
        first = False
        n_rows += len(X)
        P("  chunk %d..%d  events=%d  total=%d  %.0fs" % (k0, k0 + len(part), len(X), n_rows,
                                                        time.time() - t0))
    meta = {"universe_mode": a.universe, "n_universe": len(syms), "symbols": syms,
            "n_frames": TAIL["names"], "tail": dict(TAIL), "counters": counters,
            "clocks": list(clocks), "floor": floor, "hold": hold, "today": _today_et(),
            "n_rows": n_rows, "walltime_s": round(time.time() - t0, 1),
            "stride": a.stride, "names": a.names, "min_dvol": a.min_dvol}
    with open(a.out + ".meta.json", "w") as fh:
        json.dump(meta, fh)
    P("replay done  rows=%d  frames=%d  tail: today=%d phantom=%d  nonpos: names=%d rows=%d  "
      "counters=%s  %.0fs"
      % (n_rows, TAIL["names"], TAIL["today"], TAIL["phantom"], TAIL["nonpos_names"],
         TAIL["nonpos_rows"], counters, time.time() - t0))


# ═════════════════════════════════════════════════════════════════════════════
# STATISTICS — the engine's constructions, parameterised on the column
# ═════════════════════════════════════════════════════════════════════════════
def _by_key(D: pd.DataFrame, keys: np.ndarray, col: str, key: Optional[str]):
    if key is None:                                  # i.i.d.: one cluster per row
        vals = D[col].to_numpy(dtype=float)
        ok = np.isfinite(vals)
        return np.where(ok, vals, 0.0), ok.astype(float)
    return BQ._by_date(D.assign(date=D[key]) if key != "date" else D, keys, col)


def cluster_boot(base: pd.DataFrame, kept: pd.DataFrame, col: str, key: Optional[str],
                 draws: int, seed: int = SEED_BOOT) -> np.ndarray:
    """Bootstrap draws of mean(kept[col]) - mean(base[col]) resampling CLUSTERS
    (`key` = "date" | "symbol" | None for i.i.d.), the SAME resample for both
    cohorts — BQ._boot_delta's construction on any column. Chunked so the
    draws x clusters matrix stays small."""
    if key is None:
        keys = np.arange(len(base))
        bs, bc = _by_key(base, keys, col, None)
        kmask = base.index.isin(kept.index)
        ks, kc = bs * kmask, bc * kmask
    else:
        keys = np.array(sorted(base[key].unique()))
        bs, bc = _by_key(base, keys, col, key)
        ks, kc = _by_key(kept, keys, col, key)
    n = len(keys)
    if n < 3 or kept.empty:
        return np.array([])
    rng = np.random.default_rng(seed)
    out = []
    step = max(1, int(4_000_000 // max(n, 1)))
    done = 0
    while done < draws:
        m = min(step, draws - done)
        idx = rng.integers(0, n, size=(m, n))
        bn, bd = bs[idx].sum(1), bc[idx].sum(1)
        kn, kd = ks[idx].sum(1), kc[idx].sum(1)
        ok = (bd > 0) & (kd > 0)
        out.append(kn[ok] / kd[ok] - bn[ok] / bd[ok])
        done += m
    return np.concatenate(out) if out else np.array([])


def boot_delta_col(base, kept, col, draws, seed: int = SEED_BOOT) -> dict:
    """Date-clustered 95% CI on the delta of `col`, P(Δ<=0), and the bootstrap
    SD (the MDL's ingredient). NaN when fewer than 100 usable draws."""
    d = cluster_boot(base, kept, col, "date", draws, seed)
    if d.size < 100:
        return {"lo": np.nan, "hi": np.nan, "p_le0": np.nan, "sd": np.nan}
    return {"lo": float(np.percentile(d, 2.5)), "hi": float(np.percentile(d, 97.5)),
            "p_le0": float((d <= 0).mean()), "sd": float(d.std(ddof=1))}


def two_way_ci(base, kept, col, delta: float, draws: int) -> dict:
    """Cameron-Gelbach-Miller: SE^2 = SE_date^2 + SE_symbol^2 - SE_iid^2 from
    three bootstraps (same draws/seed); normal interval. A non-positive
    variance falls back to the larger one-way SE (stated)."""
    sd = cluster_boot(base, kept, col, "date", draws, SEED_TWOWAY)
    ss = cluster_boot(base, kept, col, "symbol", draws, SEED_TWOWAY)
    si = cluster_boot(base, kept, col, None, draws, SEED_TWOWAY)
    if min(sd.size, ss.size, si.size) < 100:
        return {"lo": np.nan, "hi": np.nan, "se": np.nan, "fallback": True}
    v = sd.var(ddof=1) + ss.var(ddof=1) - si.var(ddof=1)
    fb = not (v > 0)
    se = math.sqrt(v) if v > 0 else max(sd.std(ddof=1), ss.std(ddof=1))
    return {"lo": delta - 1.96 * se, "hi": delta + 1.96 * se, "se": se, "fallback": fb}


def _date_block_keep(counts: np.ndarray, n_keep: int, rng) -> tuple:
    """One date-block draw: shuffle the dates, take WHOLE dates in order until
    the cumulative count reaches n_keep, trim the last date's events at random.
    Returns (full_dates, partial_date, n_from_partial)."""
    perm = rng.permutation(len(counts))
    cum = np.cumsum(counts[perm])
    k = int(np.searchsorted(cum, n_keep))          # first index with cum >= n_keep
    before = int(cum[k - 1]) if k > 0 else 0
    need = int(n_keep - before)
    if need == counts[perm[k]]:
        return perm[:k + 1], None, 0
    return perm[:k], int(perm[k]), need


def placebo_dates(D: pd.DataFrame, n_keep: int, cols, draws: int, seed: int = SEED_PLACEBO) -> dict:
    """Size-matched DATE-BLOCK placebo (design §4.3): the 5th-95th percentile of
    mean(col) over random keeps of n_keep events taken as whole dates. Rows
    with NaN in a col count toward the size but not toward its mean."""
    dates = np.array(sorted(D["date"].unique()))
    pos = {d: i for i, d in enumerate(dates)}
    di = D["date"].map(pos).to_numpy()
    counts = np.bincount(di, minlength=len(dates))
    if n_keep <= 0 or n_keep >= len(D) or len(dates) < 3:
        return {c: (np.nan, np.nan) for c in cols}
    rng = np.random.default_rng(seed)
    order = np.argsort(di, kind="stable")
    starts = np.concatenate([[0], np.cumsum(counts)])
    vals = {c: D[c].to_numpy(dtype=float)[order] for c in cols}
    sums = {c: np.array([np.nansum(vals[c][starts[i]:starts[i + 1]]) for i in range(len(dates))])
            for c in cols}
    cnts = {c: np.array([np.isfinite(vals[c][starts[i]:starts[i + 1]]).sum() for i in range(len(dates))])
            for c in cols}
    acc = {c: [] for c in cols}
    for _ in range(draws):
        full, part, need = _date_block_keep(counts, n_keep, rng)
        pick = (rng.choice(np.arange(starts[part], starts[part + 1]), size=need, replace=False)
                if part is not None and need > 0 else np.array([], dtype=int))
        for c in cols:
            s = sums[c][full].sum() + (np.nansum(vals[c][pick]) if pick.size else 0.0)
            k = cnts[c][full].sum() + (np.isfinite(vals[c][pick]).sum() if pick.size else 0)
            acc[c].append(s / k if k > 0 else np.nan)
    return {c: (float(np.nanpercentile(acc[c], 5)), float(np.nanpercentile(acc[c], 95)))
            for c in cols}


def _cells(D: pd.DataFrame, risk_col: str) -> np.ndarray:
    """room quintile (CLEAR = its own stratum) x risk quintile — the cohort's
    own edges, nothing typed."""
    room = pd.to_numeric(D["room_pct"], errors="coerce")
    risk = pd.to_numeric(D[risk_col], errors="coerce")
    rq = pd.qcut(room, 5, labels=False, duplicates="drop")
    rq = rq.fillna(-1).astype(int) + 1                          # CLEAR/NaN room -> 0
    kq = pd.qcut(risk, 5, labels=False, duplicates="drop")
    kq = kq.fillna(-1).astype(int) + 1
    return (rq * 10 + kq).to_numpy()


def reweight_delta(D: pd.DataFrame, mask: pd.Series, col: str, risk_col: str,
                   draws: int, seed: int = SEED_BOOT) -> dict:
    """Design §4.4: reweight the REST of the cohort to the bucket's
    (room x risk) cell mix (the AMD study's _boot_weighted construction:
    weights = the bucket's own cell mix, cells with < 5 rows in either arm
    dropped, weights renormalised per replicate), date-clustered CI."""
    cell = _cells(D, risk_col)
    y = D[col].to_numpy(dtype=float)
    ok_y = np.isfinite(y)
    y0 = np.where(ok_y, y, 0.0)
    km = mask.to_numpy(dtype=bool)
    xm = ~km
    cells = np.unique(cell)
    cid = {c: i for i, c in enumerate(cells)}
    ci = np.array([cid[c] for c in cell])
    nK = np.bincount(ci[km], minlength=len(cells))
    nX = np.bincount(ci[xm], minlength=len(cells))
    use = (nK >= 5) & (nX >= 5)
    if not use.any():
        return {"delta": np.nan, "lo": np.nan, "hi": np.nan, "n_cells": 0}
    w = np.where(use, nK, 0).astype(float)
    w = w / w.sum()
    sK = np.bincount(ci[km], weights=y0[km], minlength=len(cells))
    cK = np.bincount(ci[km], weights=ok_y[km].astype(float), minlength=len(cells))
    sX = np.bincount(ci[xm], weights=y0[xm], minlength=len(cells))
    cX = np.bincount(ci[xm], weights=ok_y[xm].astype(float), minlength=len(cells))
    with np.errstate(invalid="ignore", divide="ignore"):
        delta = float(np.nansum(w * (sK / cK - sX / cX)))
    # per-date, per-cell sums and counts -> vectorised date resample
    dates = np.array(sorted(D["date"].unique()))
    dpos = D["date"].map({d: i for i, d in enumerate(dates)}).to_numpy()
    nd, nc = len(dates), len(cells)
    flat = dpos * nc + ci
    SK = np.bincount(flat[km], weights=y0[km], minlength=nd * nc).reshape(nd, nc)
    CK = np.bincount(flat[km], weights=ok_y[km].astype(float), minlength=nd * nc).reshape(nd, nc)
    SX = np.bincount(flat[xm], weights=y0[xm], minlength=nd * nc).reshape(nd, nc)
    CX = np.bincount(flat[xm], weights=ok_y[xm].astype(float), minlength=nd * nc).reshape(nd, nc)
    rng = np.random.default_rng(seed)
    out = []
    step = max(1, int(2_000_000 // max(nd * nc, 1)))
    done = 0
    while done < draws:
        m = min(step, draws - done)
        idx = rng.integers(0, nd, size=(m, nd))
        sk, ck = SK[idx].sum(1), CK[idx].sum(1)
        sx, cx = SX[idx].sum(1), CX[idx].sum(1)
        good = (ck > 0) & (cx > 0) & use[None, :]
        with np.errstate(invalid="ignore", divide="ignore"):
            diff = np.where(good, sk / np.maximum(ck, 1) - sx / np.maximum(cx, 1), 0.0)
            ww = np.where(good, w[None, :], 0.0)
            wsum = ww.sum(1)
            d = (ww * diff).sum(1) / wsum
        out.append(d[wsum > 0])
        done += m
    d = np.concatenate(out)
    if d.size < 100:
        return {"delta": delta, "lo": np.nan, "hi": np.nan, "n_cells": int(use.sum())}
    return {"delta": delta, "lo": float(np.percentile(d, 2.5)), "hi": float(np.percentile(d, 97.5)),
            "n_cells": int(use.sum())}


def dedupe_deltas(D: pd.DataFrame, K: pd.DataFrame, col: str) -> tuple:
    """BQ._dedupe's construction applied to `col`: the one-per-DATE and the
    one-per-SYMBOL point estimates of mean(K) - mean(D)."""
    s = D.sort_values(["date", "symbol"])
    k = K.sort_values(["date", "symbol"])
    d1 = _nanmean(k.groupby("date").first()[col]) - _nanmean(s.groupby("date").first()[col])
    s1 = _nanmean(k.groupby("symbol").first()[col]) - _nanmean(s.groupby("symbol").first()[col])
    return float(d1), float(s1)


def perm_p(K: pd.DataFrame, X: pd.DataFrame, col: str, draws: int) -> float:
    a = K[col].to_numpy(dtype=float)
    b = X[col].to_numpy(dtype=float)
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if len(a) < 10 or len(b) < 10:
        return float("nan")
    return BQ._perm_p(a, b, draws)


def trimmed_mean(x, top_frac: float = 0.01) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return float("nan")
    k = int(math.floor(x.size * top_frac))
    return float(np.sort(x)[:x.size - k].mean()) if k > 0 else float(x.mean())


# ═════════════════════════════════════════════════════════════════════════════
# CONVENTIONS, BUCKETS, ORIENTATION
# ═════════════════════════════════════════════════════════════════════════════
def conventions(primary: str, hold: int) -> dict:
    return {
        "P": {"tag": "P", "label": "P (print: _pre features, entry close[j])",
              "hit": "%s_%d" % (primary, hold), "hit5": "hit5_%d" % hold,
              "hit5b": "hit5b_%d" % hold, "hit_lid": "hit_lid_%d" % hold,
              "stop": "stop_%d" % hold, "R": "R%d" % hold, "why": "why%d" % hold,
              "risk": "risk_pct", "feats": PREREG_P, "suffix": ""},
        "N": {"tag": "N", "label": "N (next-open read: _at features, entry open[j+1])",
              "hit": "%s_%d%s" % (primary, hold, "" if primary == "hit5b" else "_N"),
              "hit5": "hit5_%d_N" % hold, "hit5b": "hit5b_%d" % hold,
              "hit_lid": "hit_lid_%d_N" % hold, "stop": "stop_%d_N" % hold,
              "R": "R%d_N" % hold, "why": "why%d_N" % hold, "risk": "risk_pct_N",
              "feats": PREREG_N, "suffix": "_N"},
    }


def feat_kind(name: str) -> str:
    if name in BOOL_FEATS:
        return "bool"
    if name in STATE_FEATS:
        return "state"
    return "num"


def assign_buckets(series: pd.Series, kind: str, edges=None) -> tuple:
    """(labels: Series[str], order: list, edges). Numeric -> quintiles of the
    series itself (or the given edges); NaN = its own bucket, never merged."""
    if kind == "num":
        x = pd.to_numeric(series, errors="coerce")
        if edges is None:
            xs = x.dropna()
            if xs.nunique() < 2:
                lab = pd.Series(np.where(x.notna(), "Q1", "NaN"), index=series.index)
                return lab, ["Q1", "NaN"], [-np.inf, np.inf]
            _, bins = pd.qcut(xs, 5, retbins=True, duplicates="drop")
            edges = [-np.inf] + [float(b) for b in bins[1:-1]] + [np.inf]
        k = len(edges) - 1
        names = ["Q%d" % (i + 1) for i in range(k)]
        cut = pd.cut(x, edges, labels=names, include_lowest=True)
        lab = cut.astype(object).where(x.notna(), "NaN").astype(str)
        return lab, names + ["NaN"], edges
    if kind == "bool":
        m = series.map(lambda v: "yes" if v is True or v == 1 or str(v) == "True"
                       else ("no" if v is False or v == 0 or str(v) == "False" else "NaN"))
        return m.astype(str), ["no", "yes", "NaN"], None
    lab = series.astype(object).where(series.notna(), "NaN").astype(str)
    order = [s for s in lab.value_counts().index.tolist() if s != "NaN"] + ["NaN"]
    return lab, order, None


def orientation(D: pd.DataFrame, feat: str, kind: str, lab: pd.Series, order: list, hit: str) -> int:
    """+1 = higher is better (the top bucket is the LAST real one); -1 = lower.
    Numeric: sign of the Spearman of bucket index vs the outcome; boolean:
    sign of yes minus no; state: +1 by convention (top = best state)."""
    y = D[hit]
    if kind == "num":
        real = [o for o in order if o != "NaN"]
        idx = lab.map({o: i for i, o in enumerate(real)})
        m = idx.notna() & y.notna()
        if m.sum() < MIN_BUCKET_N or idx[m].nunique() < 2:
            return 1
        rho = spearman(idx[m].to_numpy(dtype=float), y[m].to_numpy(dtype=float))
        return -1 if (rho == rho and rho < 0) else 1
    if kind == "bool":
        yes, no = _nanmean(y[lab == "yes"]), _nanmean(y[lab == "no"])
        return -1 if (yes == yes and no == no and yes < no) else 1
    return 1


def top_bucket(lab: pd.Series, order: list, kind: str, orient: int, D: pd.DataFrame, hit: str) -> str:
    real = [o for o in order if o != "NaN"]
    if not real:
        return "NaN"
    if kind == "num":
        return real[-1] if orient > 0 else real[0]
    if kind == "bool":
        return "yes" if orient > 0 else "no"
    best, best_v = None, -np.inf
    for o in real:
        m = lab == o
        if m.sum() >= MIN_BUCKET_N:
            v = _nanmean(D.loc[m, hit])
            if v == v and v > best_v:
                best, best_v = o, v
    return best or real[0]


def bucket_stats(D: pd.DataFrame, K: pd.DataFrame, conv: dict, clocks, hold: int, E_ev=None) -> dict:
    """The per-bucket line: n_ep, n_ev, n_dates, HIT5@5/10/20, HIT5B@20,
    HIT_LID@20 (n with lid), stop@20, mean/median/trimmed R20, win, tgt/stop/
    clk, room, risk, room/risk, Δrisk vs base, clear%."""
    sfx = conv["suffix"]
    s = {"n_ep": int(len(K)), "n_ev": int(len(E_ev)) if E_ev is not None else int(len(K)),
         "n_dates": int(K["date"].nunique()) if len(K) else 0}
    for cl in sorted(set(clocks) | {hold}):
        s["hit5_%d" % cl] = 100.0 * _nanmean(K["hit5_%d%s" % (cl, sfx)]) if len(K) else np.nan
    s["hit5b_20"] = 100.0 * _nanmean(K[conv["hit5b"]]) if len(K) else np.nan
    lid = K[conv["hit_lid"]]
    s["hit_lid_20"] = 100.0 * _nanmean(lid) if len(K) else np.nan
    s["n_lid"] = int(lid.notna().sum()) if len(K) else 0
    s["stop_20"] = 100.0 * _nanmean(K[conv["stop"]]) if len(K) else np.nan
    R = K[conv["R"]].to_numpy(dtype=float) if len(K) else np.array([])
    s["R20"] = _nanmean(R)
    s["R20_median"] = float(np.nanmedian(R)) if R.size else np.nan
    s["R20_trim"] = trimmed_mean(R)
    s["win20"] = 100.0 * float(np.nanmean(R > 0)) if R.size else np.nan
    why = K[conv["why"]] if len(K) else pd.Series(dtype=object)
    s["tgt_stop_clk"] = "%.0f/%.0f/%.0f" % tuple(100.0 * (why == w).mean() if len(K) else np.nan
                                              for w in ("target", "stop", "clock"))
    s["room_pct"] = _nanmean(K["room_pct"]) if len(K) else np.nan
    s["risk_pct"] = _nanmean(K[conv["risk"]]) if len(K) else np.nan
    s["room_risk"] = s["room_pct"] / s["risk_pct"] if s["risk_pct"] and s["risk_pct"] == s["risk_pct"] else np.nan
    base_risk = _nanmean(D[conv["risk"]])
    s["d_risk"] = s["risk_pct"] - base_risk
    s["clear_pct"] = 100.0 * float(pd.to_numeric(K["clear"], errors="coerce").fillna(0).mean()) if len(K) else np.nan
    s["hit5c_20"] = 100.0 * _nanmean(K["hit5c_%d%s" % (hold, sfx)]) if len(K) else np.nan
    return s


def fmt_row(label: str, s: dict) -> str:
    return ("    %-11s ep %6d ev %6d d %4d | hit5 %5.1f %5.1f %5.1f | 5b %5.1f | lid %5.1f (%5d) | "
            "stop %5.1f | R %+.3f md %+.3f tr %+.3f | win %4.1f | t/s/c %-8s | room %5.2f risk %4.2f r/r %5.2f "
            "Δrisk %+.2f | clear %4.1f"
            % (label[:11], s["n_ep"], s["n_ev"], s["n_dates"], s["hit5_5"], s["hit5_10"], s["hit5_20"],
               s["hit5b_20"], s["hit_lid_20"], s["n_lid"], s["stop_20"], s["R20"], s["R20_median"],
               s["R20_trim"], s["win20"], s["tgt_stop_clk"], s["room_pct"], s["risk_pct"],
               s["room_risk"], s["d_risk"], s["clear_pct"]))


def evaluate_bucket(D: pd.DataFrame, mask: pd.Series, conv: dict, a, base: dict,
                    full: bool = True) -> dict:
    """Design §4.1 — every ingredient of the rule of reading for one bucket vs
    the cohort it sits in, then the mechanical verdict. `full=False` = the
    per-bucket CI line only (ΔHIT5 / Δstop / ΔR CIs, perm p, both placebo
    bands); the reweight, dedupe and verdict run on the TOP bucket."""
    K, X = D[mask], D[~mask]
    hit, stop, R, risk = conv["hit"], conv["stop"], conv["R"], conv["risk"]
    r = {"n": int(len(K))}
    if len(K) < MIN_BUCKET_N or len(X) < MIN_BUCKET_N:
        r.update({"verdict": "too small"})
        return r
    if not full:
        k_hit = _nanmean(K[hit])
        r["hit"] = 100.0 * k_hit
        r["d_hit5"] = 100.0 * (k_hit - _nanmean(D[hit]))
        b = boot_delta_col(D, K, hit, a.boot_draws)
        r["ci"], r["p_le0"] = [100.0 * b["lo"], 100.0 * b["hi"]], b["p_le0"]
        bs = boot_delta_col(D, K, stop, a.boot_draws)
        r["d_stop"] = 100.0 * (_nanmean(K[stop]) - _nanmean(D[stop]))
        r["ci_stop"] = [100.0 * bs["lo"], 100.0 * bs["hi"]]
        br = boot_delta_col(D, K, R, a.boot_draws)
        r["d_R"], r["ci_R"] = _nanmean(K[R]) - _nanmean(D[R]), [br["lo"], br["hi"]]
        r["perm_p"] = perm_p(K, X, hit, a.perm_draws)
        pb = placebo_dates(D, len(K), [hit], a.placebo_draws)
        r["placebo_dates"] = [100.0 * pb[hit][0], 100.0 * pb[hit][1]]
        vals = D[hit].to_numpy(dtype=float)
        vals = vals[np.isfinite(vals)]
        p5, p95 = BQ._placebo(vals, min(len(K), len(vals) - 1), a.placebo_draws)
        r["placebo_iid"] = [100.0 * p5, 100.0 * p95]
        r["outside_date_placebo"] = bool(pb[hit][1] == pb[hit][1] and (k_hit > pb[hit][1] or k_hit < pb[hit][0]))
        return r
    k_hit = _nanmean(K[hit])
    r["hit"] = 100.0 * k_hit
    r["d_hit5"] = 100.0 * (k_hit - _nanmean(D[hit]))
    b = boot_delta_col(D, K, hit, a.boot_draws)
    r["ci"] = [100.0 * b["lo"], 100.0 * b["hi"]]
    r["p_le0"], r["sd"] = b["p_le0"], 100.0 * b["sd"]
    r["d_stop"] = 100.0 * (_nanmean(K[stop]) - _nanmean(D[stop]))
    bs = boot_delta_col(D, K, stop, a.boot_draws)
    r["ci_stop"] = [100.0 * bs["lo"], 100.0 * bs["hi"]]
    r["d_R"] = _nanmean(K[R]) - _nanmean(D[R])
    br = boot_delta_col(D, K, R, a.boot_draws)
    r["ci_R"] = [br["lo"], br["hi"]]
    r["perm_p"] = perm_p(K, X, hit, a.perm_draws)
    pb = placebo_dates(D, len(K), [hit, R], a.placebo_draws)
    r["placebo_dates"] = [100.0 * pb[hit][0], 100.0 * pb[hit][1]]
    r["placebo_dates_R"] = list(pb[R])
    vals = D[hit].to_numpy(dtype=float)
    vals = vals[np.isfinite(vals)]
    p5, p95 = BQ._placebo(vals, min(len(K), len(vals) - 1), a.placebo_draws)
    r["placebo_iid"] = [100.0 * p5, 100.0 * p95]
    rw = reweight_delta(D, mask, hit, risk, a.boot_draws)
    r["d_hit5_reweighted"] = 100.0 * rw["delta"]
    r["ci_rw"] = [100.0 * rw["lo"], 100.0 * rw["hi"]]
    r["rw_cells"] = rw["n_cells"]
    d1, s1 = dedupe_deltas(D, K, hit)
    r["one_per_date"], r["one_per_symbol"] = 100.0 * d1, 100.0 * s1
    room_k, risk_k = _nanmean(K["room_pct"]), _nanmean(K[risk])
    r["room_risk"] = room_k / risk_k if risk_k and risk_k == risk_k else np.nan
    r["room_risk_base"] = base["room_risk"]
    r["d_risk"] = risk_k - base["risk_pct"]
    c1 = b["lo"] == b["lo"] and b["lo"] > 0
    c2 = not (bs["lo"] == bs["lo"] and bs["lo"] > 0)
    c3 = not (r["room_risk"] == r["room_risk"] and base["room_risk"] == base["room_risk"]
              and r["room_risk"] < base["room_risk"])
    c4 = pb[hit][1] == pb[hit][1] and k_hit > pb[hit][1]
    c5 = rw["delta"] == rw["delta"] and rw["delta"] > 0
    c6 = d1 > 0 and s1 > 0
    r["conditions"] = {"ci_excludes_0": bool(c1), "stop_not_raised": bool(c2),
                       "room_risk_kept": bool(c3), "outside_date_placebo": bool(c4),
                       "reweighted_sign": bool(c5), "one_per_date_symbol": bool(c6)}
    if c1 and c2 and c3 and c4 and c5 and c6:
        v = "separates"
    elif c1 and not c3:
        v = "selects smaller trades"
    elif c1 and r["d_risk"] > 0:
        v = "selects wider stops"
    elif b["hi"] == b["hi"] and b["hi"] < 0:
        v = "harmful"
    elif c1:
        v = "inert (CI>0 but fails: %s)" % ",".join(k for k, ok in r["conditions"].items() if not ok)
    else:
        v = "inert"
    r["verdict"] = v
    return r


def fmt_ci_line(r: dict) -> str:
    """The compact per-bucket CI line (every bucket gets one)."""
    if "ci" not in r:
        return "        (n=%d: too small for a CI)" % r.get("n", 0)
    return ("        ΔHIT5 %+.2fpp CI[%+.2f,%+.2f] P(Δ<=0)=%.3f | Δstop %+.2fpp CI[%+.2f,%+.2f] | ΔR20 %+.3f "
            "CI[%+.3f,%+.3f] | perm p=%.3f | placebo dates[%.1f,%.1f] iid[%.1f,%.1f]%s"
            % (r["d_hit5"], r["ci"][0], r["ci"][1], r["p_le0"], r["d_stop"], r["ci_stop"][0], r["ci_stop"][1],
               r["d_R"], r["ci_R"][0], r["ci_R"][1], r["perm_p"], r["placebo_dates"][0],
               r["placebo_dates"][1], r["placebo_iid"][0], r["placebo_iid"][1],
               "  *outside placebo*" if r.get("outside_date_placebo") else ""))


def fmt_eval(r: dict) -> str:
    if r.get("verdict") == "too small" or "ci" not in r:
        return "      -> %s (n=%d)" % (r.get("verdict"), r.get("n", 0))
    return ("      ΔHIT5@20 %+.2fpp CI[%+.2f,%+.2f] P(Δ<=0)=%.3f | Δstop %+.2fpp CI[%+.2f,%+.2f] | "
            "ΔR20 %+.3f CI[%+.3f,%+.3f] | perm p=%.3f | placebo dates[%.1f,%.1f] iid[%.1f,%.1f]%s | "
            "reweighted %+.2fpp CI[%+.2f,%+.2f] (%d cells) | 1/date %+.2f 1/sym %+.2f | "
            "room/risk %.2f vs %.2f Δrisk %+.2f\n      -> %s"
            % (r["d_hit5"], r["ci"][0], r["ci"][1], r["p_le0"], r["d_stop"], r["ci_stop"][0],
               r["ci_stop"][1], r["d_R"], r["ci_R"][0], r["ci_R"][1], r["perm_p"],
               r["placebo_dates"][0], r["placebo_dates"][1], r["placebo_iid"][0], r["placebo_iid"][1],
               "  *outside placebo*" if r["conditions"]["outside_date_placebo"] else "",
               r["d_hit5_reweighted"], r["ci_rw"][0], r["ci_rw"][1], r["rw_cells"],
               r["one_per_date"], r["one_per_symbol"], r["room_risk"], r["room_risk_base"],
               r["d_risk"], r["verdict"]))


# ═════════════════════════════════════════════════════════════════════════════
# SCORING (design §4.5)
# ═════════════════════════════════════════════════════════════════════════════
def fit_edges(fit: pd.DataFrame, feat: str, kind: str) -> Optional[list]:
    if kind != "num":
        return None
    x = pd.to_numeric(fit[feat], errors="coerce").dropna().to_numpy(dtype=float)
    if x.size < 2:
        return None
    return [float(q) for q in np.quantile(x, np.linspace(0.0, 1.0, 101))]


def oriented_rank(values: pd.Series, kind: str, orient: int, edges) -> np.ndarray:
    """Percentile rank against the FIT half's edges, oriented; NaN -> 0.5 (no
    opinion, never a pass); boolean -> 1.0 when in the oriented top state."""
    if kind == "num":
        x = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
        e = np.asarray(edges, dtype=float)
        r = np.searchsorted(e, x, side="right") / float(len(e))
        r = np.clip(r, 0.0, 1.0)
        r = np.where(np.isfinite(x), r, 0.5)
    else:
        lab, _, _ = assign_buckets(values, "bool")
        want = "yes" if orient > 0 else "no"
        r = np.where(lab == "NaN", 0.5, np.where(lab == want, 1.0, 0.0))
        return r
    return r if orient > 0 else np.where(np.isfinite(x), 1.0 - r, 0.5)


def score_rows(D: pd.DataFrame, selected: list, orient: dict, edges: dict) -> np.ndarray:
    if not selected:
        return np.full(len(D), np.nan)
    ranks = [oriented_rank(D[f], feat_kind(f), orient[f], edges.get(f)) for f in selected]
    return np.mean(np.vstack(ranks), axis=0)


def top_frac_mask(D: pd.DataFrame, score: np.ndarray, frac: float) -> pd.Series:
    n_top = max(1, int(round(frac * len(D))))
    order = np.lexsort((D["symbol"].to_numpy(), -score))
    m = np.zeros(len(D), dtype=bool)
    m[order[:n_top]] = True
    return pd.Series(m, index=D.index)


def run_split(D: pd.DataFrame, fit_mask: pd.Series, sc_mask: pd.Series, conv: dict, a,
              name: str, clocks, hold: int) -> dict:
    fit, sc = D[fit_mask], D[sc_mask]
    P("  SPLIT %s — fit n=%d (%d dates) / scored n=%d (%d dates)"
      % (name, len(fit), fit["date"].nunique(), len(sc), sc["date"].nunique()))
    base_fit = bucket_stats(fit, fit, conv, clocks, hold)
    selected, orient, edges = [], {}, {}
    n_tested = 0
    for feat in conv["feats"]:
        if feat not in fit:
            continue
        kind = feat_kind(feat)
        lab, order, _ = assign_buckets(fit[feat], kind)
        o = orientation(fit, feat, kind, lab, order, conv["hit"])
        top = top_bucket(lab, order, kind, o, fit, conv["hit"])
        n_tested += 1
        r = evaluate_bucket(fit, lab == top, conv, a, base_fit)
        P("    fit %-20s orient %+d top %-4s n=%-5d %s" % (feat, o, top, r.get("n", 0),
                                                          r.get("verdict")))
        if r.get("verdict") == "separates":
            selected.append(feat)
            orient[feat] = o
            edges[feat] = fit_edges(fit, feat, kind)
    exp_false = 0.05 * n_tested * 2
    out = {"name": name, "n_fit": int(len(fit)), "n_scored": int(len(sc)), "selected": selected,
           "orientation": orient, "expected_false_selections": exp_false, "n_tested": n_tested}
    P("    selected on the fit half: %s   (expected false selections at 5%%: %.1f)"
      % (selected or "NONE", exp_false))
    if not selected:
        # no score exists, so the study's RESOLUTION is the MDL of a decile-sized
        # random keep on the scored half (same bootstrap, seeded) — the number the
        # null banner reads as "no lift larger than {MDL}pp"
        rng = np.random.default_rng(SEED_BOOT)
        rand = pd.Series(False, index=sc.index)
        rand.iloc[rng.choice(len(sc), size=max(1, int(round(DECILE * len(sc)))), replace=False)] = True
        b = boot_delta_col(sc, sc[rand], conv["hit"], a.boot_draws)
        mdl = 1.96 * 100.0 * b["sd"] if b["sd"] == b["sd"] else np.nan
        P("    resolution (MDL of a random decile-sized keep on the scored half): %.2fpp" % mdl)
        out.update({"verdict": "no_signal", "top_decile_n": 0, "edges": {}, "mdl": mdl,
                    "mdl_source": "random decile keep"})
        return out
    score = score_rows(sc, selected, orient, edges)
    base_sc = bucket_stats(sc, sc, conv, clocks, hold)
    dec = top_frac_mask(sc, score, DECILE)
    r = evaluate_bucket(sc, dec, conv, a, base_sc)
    r["ci_2way"] = [np.nan, np.nan]
    if "ci" in r:
        tw = two_way_ci(sc, sc[dec], conv["hit"], r["d_hit5"] / 100.0, a.boot_draws)
        r["ci_2way"] = [100.0 * tw["lo"], 100.0 * tw["hi"]]
        r["ci_2way_fallback"] = tw["fallback"]
    P("    scored half, top DECILE by score:")
    P(fmt_row("base", base_sc))
    P(fmt_row("top decile", bucket_stats(sc, sc[dec], conv, clocks, hold)))
    P(fmt_eval(r))
    if "ci" in r:
        P("      two-way (date x symbol) CI [%+.2f,%+.2f]%s"
          % (r["ci_2way"][0], r["ci_2way"][1], "  (fallback: one-way SE)" if r.get("ci_2way_fallback") else ""))
        BQ.mech_line("scored base", sc)
        BQ.mech_line("top decile", sc[dec])
        BQ._dedupe(sc[dec], "top decile")
    widths = {}
    for lab_w, frac in (("top5", TOP5), ("top20", TOP20)):
        m = top_frac_mask(sc, score, frac)
        widths[lab_w] = 100.0 * (_nanmean(sc.loc[m, conv["hit"]]) - _nanmean(sc[conv["hit"]]))
    q_top, q_bot = top_frac_mask(sc, score, 0.25), top_frac_mask(sc, -score, 0.25)
    gap = 100.0 * (_nanmean(sc.loc[q_top, conv["hit"]]) - _nanmean(sc.loc[q_bot, conv["hit"]]))
    y = sc[conv["hit"]].to_numpy(dtype=float)
    okm = np.isfinite(y) & np.isfinite(score)
    rho = spearman(score[okm], y[okm]) if okm.sum() > 10 else np.nan
    mdl = 1.96 * r["sd"] if "sd" in r else np.nan
    P("      width sweep: top5 %+.2fpp  top10 %+.2fpp  top20 %+.2fpp | quartile gap %+.2fpp | rho %.3f | MDL %.2fpp"
      % (widths["top5"], r.get("d_hit5", np.nan), widths["top20"], gap, rho, mdl))
    sign_ok = ("d_hit5" in r and r["d_hit5"] > 0 and widths["top5"] > 0 and widths["top20"] > 0)
    two_ok = r["ci_2way"][0] == r["ci_2way"][0] and r["ci_2way"][0] > 0
    verdict = "separates" if (r.get("verdict") == "separates" and sign_ok and two_ok) else "no_signal"
    out.update({"top_decile_n": int(dec.sum()), "d_hit5": r.get("d_hit5"), "ci": r.get("ci"), "mdl_source": "top decile",
                "ci_2way": r.get("ci_2way"), "d_stop": r.get("d_stop"), "ci_stop": r.get("ci_stop"),
                "placebo": r.get("placebo_dates"), "perm_p": r.get("perm_p"),
                "d_hit5_reweighted": r.get("d_hit5_reweighted"), "ci_rw": r.get("ci_rw"),
                "d_hit5_top5": widths["top5"], "d_hit5_top20": widths["top20"],
                "quartile_gap": gap, "rho": float(rho) if rho == rho else None, "mdl": mdl,
                "bucket_verdict": r.get("verdict"), "verdict": verdict, "edges": edges})
    P("    -> split verdict: %s" % verdict)
    return out


# ═════════════════════════════════════════════════════════════════════════════
# LOADING + derived columns
# ═════════════════════════════════════════════════════════════════════════════
def _to_bool(s: pd.Series) -> pd.Series:
    m = {True: True, False: False, "True": True, "False": False, 1: True, 0: False,
         1.0: True, 0.0: False}
    return s.map(lambda v: m.get(v, np.nan) if not (isinstance(v, float) and v != v) else np.nan)


ENGINE_DEFINITION_PREFIXES = ("vc_", "sh_", "shelf_", "rp_")     # bounce_quality's gate columns


def load_events(path: str, columns=None) -> pd.DataFrame:
    """The CSV, without the engine's stationary-bottom definition columns (this
    study never reads them; ~150k rows x 200 columns would not fit beside the
    cache table in the container's free memory). `columns` = an explicit list
    (the cache table needs only its survivorship columns)."""
    if columns is not None:
        keep = set(columns)
        X = pd.read_csv(path, low_memory=False, usecols=lambda c: c in keep)
    else:
        X = pd.read_csv(path, low_memory=False,
                        usecols=lambda c: not c.startswith(ENGINE_DEFINITION_PREFIXES))
    X["date"] = X["date"].astype(str).str[:10]
    X["symbol"] = X["symbol"].astype(str)
    for c in BOOL_FEATS:
        if c in X:
            X[c] = _to_bool(X[c])
    if "dvol50_pre" in X:
        d = pd.to_numeric(X["dvol50_pre"], errors="coerce")
        tier = pd.Series("sub-thin", index=X.index).where(d.notna(), np.nan)
        for usd, name in reversed(LIQ_TIERS):
            tier = tier.mask(d >= usd, name)
        X["dvol_tier_pre"] = tier
    for tag in ("pre", "at"):
        col = "cmf20_" + tag
        if col in X:
            c = pd.to_numeric(X[col], errors="coerce")
            st = pd.Series("neutral", index=X.index).where(c.notna(), np.nan)
            st = st.mask(c >= CMF_IN, "inflow").mask(c <= CMF_OUT, "outflow")
            X["cmf_state_" + tag] = st
    return X


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        v = float(o)
        return None if (v != v or math.isinf(v)) else v
    if isinstance(o, np.ndarray):
        return _clean(o.tolist())
    return o


# ═════════════════════════════════════════════════════════════════════════════
# STAGE: stats — the §4 report and the MEASURED dict
# ═════════════════════════════════════════════════════════════════════════════
RULE_TEXT = """RULE OF READING (design §4.1, applied mechanically to every top bucket) — a bucket "separates" only if ALL of:
  1. ΔHIT5@20 date-clustered 95% CI excludes 0 (positive);
  2. guard (a): Δstop@20 date-clustered 95% CI does not lie entirely above 0 (the bucket does not measurably raise stop-outs);
  3. guard (b): the bucket's room/risk is not below the base's (else "selects smaller trades");
  4. its HIT5 sits outside (above) the DATE-BLOCK placebo band (the i.i.d. band is printed, never used);
  5. the (room x risk)-reweighted ΔHIT5 keeps the sign;
  6. the one-per-DATE and one-per-SYMBOL point estimates of ΔHIT5@20 are both > 0.
  Anything else is named inert / selects smaller trades / selects wider stops / harmful. Mean R is a tail statistic here (never a gate)."""


def stats(a) -> dict:
    t0 = time.time()
    clocks = tuple(int(x) for x in str(a.clocks).split(","))
    hold = int(a.hold)
    X = load_events(a.from_csv)
    meta = {}
    if os.path.exists(a.from_csv + ".meta.json"):
        with open(a.from_csv + ".meta.json") as fh:
            meta = json.load(fh)
    quotable = not (a.names or meta.get("names") or a.stride > 1 or (meta.get("stride") or 1) > 1)
    banner = "" if quotable else "NOT QUOTABLE — smoke (stride/names subsample)"
    if banner:
        P("=" * 118 + "\n" + banner + "\n" + "=" * 118)
    if a.min_dvol:
        d = pd.to_numeric(X["dvol50_pre"], errors="coerce")
        X = X[d >= float(a.min_dvol)].reset_index(drop=True)
        P("LIQUIDITY CONTROL RUN — cohort restricted to dvol50_pre >= %g (LIQ_OK_USD = %g)"
          % (a.min_dvol, MIN_DVOL_CONTROL))
    n_feat_nan = int(X["rsi14_pre"].isna().sum()) if "rsi14_pre" in X else len(X)
    E_all = X
    B_all = X[X["dir"] == DIRECTION_BASE].reset_index(drop=True)
    B = B_all[B_all["episode_dir"] == True].reset_index(drop=True)          # noqa: E712
    A_ep = X[X["episode"] == True].reset_index(drop=True)                    # noqa: E712
    convs = conventions(a.primary, hold)
    convP, convN = convs["P"], convs["N"]
    BN = B[B["gap_N"] == False].reset_index(drop=True)                        # noqa: E712
    dates = sorted(X["date"].unique())
    window = "%s -> %s" % (dates[0], dates[-1]) if dates else "n/a"

    P("=" * 118)
    P("🧨 EXPLOSIVE READ — STUDY  (%s)   script %s" % (_today_et(), SCRIPT))
    P("COHORT  demand band reached, room >= %g%% to the first proven lid, print <= %g%% above the band top; "
      "floor=%d bars (zone_store.MIN_BARS), clocks=%s, hold=%d; entry P = close[j], N = open[j+1]; "
      "stop = band floor -%g%%; universe=%s (%s names, %s frames)"
      % (FIVE_PCT, AG.ALERT_MAX_ABOVE_DEMAND_PCT, meta.get("floor", a.floor), clocks, hold,
         STOP_BUFFER_PCT, meta.get("universe_mode", "?"), meta.get("n_universe", "?"),
         meta.get("n_frames", "?")))
    P("        all events n=%d   bouncing n=%d   bouncing EPISODES n=%d   all-direction episodes n=%d   "
      "names=%d   dates=%d   window %s   ONE REGIME"
      % (len(E_all), len(B_all), len(B), len(A_ep), B["symbol"].nunique(), len(dates), window))
    P("        primary outcome = %s (his call; default hit5) | tail rule: today dropped %s, phantom dropped %s | "
      "features NaN rows %d | join counters %s"
      % (a.primary, meta.get("tail", {}).get("today", "?"), meta.get("tail", {}).get("phantom", "?"),
         n_feat_nan, meta.get("counters", {})))
    P("        N convention: gap-through-stop skips %d of %d bouncing episodes (%.1f%%)"
      % (int((B["gap_N"] == True).sum()), len(B), 100.0 * (B["gap_N"] == True).mean() if len(B) else 0))
    nan_cols = [c for c in dict.fromkeys(list(PREREG_P) + list(PREREG_N) + [convP["hit5"], convP["hit5b"],
                                                                             convP["hit_lid"], convP["stop"], convP["R"], convN["hit5"]]) if c in B]
    P("        NaN rate (bouncing episodes): " + "  ".join("%s %.3f" % (c, B[c].isna().mean()) for c in nan_cols))
    P("        (expected: 0.000 everywhere except dist_52wh/above_52wl = the <252-bar share, room_pct/hit_lid = the CLEAR share, _N = the gap share)")
    def _clear_share(df):        # the SAME construction as bucket_stats' clear_pct (NaN counts as not-clear)
        return 100.0 * float(pd.to_numeric(df["clear"], errors="coerce").fillna(0).mean()) if len(df) else float("nan")
    _cl_ep, _cl_ev = _clear_share(B), _clear_share(B_all)
    P("        CLEAR share (no proven lid overhead, so room_pct and HIT_LID are undefined): %.1f%% of bouncing "
      "episodes, %.1f%% of all bouncing events — HIT_LID is reported on the OTHER %.1f%% of episodes only. "
      "(design §2 anticipated ~20%% CLEAR; the measured share is the real HIT_LID denominator and is stated "
      "here rather than left in prose.)" % (_cl_ep, _cl_ev, 100.0 - _cl_ep))
    P("        cohort WIDER than what pushes: no cap floor (live demand_alert needs cap >= $%.0fM); "
      "--min-dvol %g is the only stand-in (control line below)" % (ZS.MIN_CAP_USD / 1e6, MIN_DVOL_CONTROL))
    P("=" * 118)
    if len(B) < 100:
        P("bouncing episode cohort too small (n=%d)" % len(B))
    P()
    P("DIRECTION SPLIT (all events; the shipped gate keeps `bouncing` only) — the control cohort:")
    for d, g in sorted(E_all.groupby("dir"), key=lambda kv: -len(kv[1])):
        P(BQ._line("%s%s" % (d, "  <= BASELINE" if d == DIRECTION_BASE else ""), BQ._stats(g)))
    P()
    P("BASE RATES — bouncing EPISODES (headline) and all bouncing events (control), both conventions:")
    P("    %-11s %s" % ("cohort", "hit5@5/10/20 | hit5b@20 | hit_lid@20 (n lid) | stop@20 | R20 mean/median/trimmed | win | tgt/stop/clk | room risk r/r Δrisk | clear"))
    base_P = bucket_stats(B, B, convP, clocks, hold, E_ev=B_all)
    base_N = bucket_stats(BN, BN, convN, clocks, hold, E_ev=B_all[B_all["gap_N"] == False])   # noqa: E712
    P(fmt_row("P episodes", base_P))
    P(fmt_row("N episodes", base_N))
    P(fmt_row("P all ev", bucket_stats(B_all, B_all, convP, clocks, hold)))
    P(fmt_row("P all-dir", bucket_stats(A_ep, A_ep, convP, clocks, hold)))
    P("    HIT5C@20 (close-based twin, exploratory): P episodes %.1f%%  P all events %.1f%%"
      % (base_P["hit5c_20"], bucket_stats(B_all, B_all, convP, clocks, hold)["hit5c_20"]))
    clear_P = B[B["clear"] == True]                                                # noqa: E712
    if len(clear_P):
        P(fmt_row("P CLEAR", bucket_stats(B, clear_P, convP, clocks, hold)))
    BQ._dedupe(B, "bouncing ep")
    per_band = B_all.groupby(["symbol", "band_lo"]).size()
    P("    per-(symbol, band) event count: mean %.2f  max %d  (reference only)"
      % (per_band.mean(), per_band.max()))
    P("    served band == event band: %.1f%% of bouncing events (intact is computed on the SERVED band)"
      % (100.0 * _nanmean(_to_bool(B_all["served_is_event"]).astype(float))))
    f252 = B_all[pd.to_numeric(B_all["bar_idx"], errors="coerce") >= BQ.MIN_HISTORY_BARS]
    P("    --floor 252 comparison (bouncing events with >= 252 prior bars, all events as the 2026-09-09 study): "
      "n=%d  hit5@20 %.1f%%  stop@20 %.1f%%  win %.1f%%  R20 %+.3f  (2026-09-09: 24.1%% win / 75%% stop)"
      % (len(f252), 100 * _nanmean(f252[convP["hit5"]]), 100 * _nanmean(f252[convP["stop"]]),
         100 * float((f252[convP["R"]] > 0).mean()) if len(f252) else np.nan, _nanmean(f252[convP["R"]])))
    # liquidity control (inside the headline run so MEASURED carries it)
    dv = pd.to_numeric(B["dvol50_pre"], errors="coerce")
    L = B[dv >= MIN_DVOL_CONTROL]
    liq = {"min_dvol": MIN_DVOL_CONTROL, "n": int(len(L)),
           "hit5_20": 100.0 * _nanmean(L[convP["hit5"]]) if len(L) else None,
           "stop_20": 100.0 * _nanmean(L[convP["stop"]]) if len(L) else None,
           "R20": _nanmean(L[convP["R"]]) if len(L) else None}
    P("    liquidity control (dvol50_pre >= LIQ_OK_USD %g): n=%d  hit5@20 %s  stop@20 %s  R20 %s"
      % (MIN_DVOL_CONTROL, liq["n"],
         "%.1f%%" % liq["hit5_20"] if liq["hit5_20"] is not None else "n/a",
         "%.1f%%" % liq["stop_20"] if liq["stop_20"] is not None else "n/a",
         "%+.3f" % liq["R20"] if liq["R20"] is not None else "n/a"))
    # intact reconciliation
    rec = {}
    if "intact_sh" in B_all and "intact_at" in B_all:
        m = B_all["intact_sh"].notna() & B_all["intact_ev_at"].notna()
        rec["agree_pct_vs_stop_hunt"] = 100.0 * float((B_all.loc[m, "intact_sh"] == B_all.loc[m, "intact_ev_at"]).mean()) if m.any() else None
        m2 = B_all["intact_sh"].notna() & B_all["intact_at"].notna()
        rec["agree_pct_sh_vs_served"] = 100.0 * float((B_all.loc[m2, "intact_sh"] == B_all.loc[m2, "intact_at"]).mean()) if m2.any() else None
        win = (B_all[convP["R"]] > 0).astype(float)
        for key, col in (("d_win_sh", "intact_sh"), ("d_win_at", "intact_at"), ("d_win_ev_at", "intact_ev_at")):
            mm = B_all[col] == True                                                   # noqa: E712
            rec[key] = 100.0 * (float(win[mm].mean()) - float(win.mean())) if mm.any() else None
        P("    INTACT reconciliation (all bouncing events): stop_hunt window vs AG window on the EVENT band agree %s%%; "
          "vs the SERVED band %s%% | Δwin20 stop_hunt %s pp | Δwin20 AG-window served %s pp | Δwin20 AG-window event band %s pp "
          "(2026-09-09: +8.60pp)"
          % (("%.1f" % rec["agree_pct_vs_stop_hunt"]) if rec.get("agree_pct_vs_stop_hunt") is not None else "n/a",
             ("%.1f" % rec["agree_pct_sh_vs_served"]) if rec.get("agree_pct_sh_vs_served") is not None else "n/a",
             ("%+.2f" % rec["d_win_sh"]) if rec.get("d_win_sh") is not None else "n/a",
             ("%+.2f" % rec["d_win_at"]) if rec.get("d_win_at") is not None else "n/a",
             ("%+.2f" % rec["d_win_ev_at"]) if rec.get("d_win_ev_at") is not None else "n/a"))
    # survivorship
    surv = {"cache_n_names": None, "cache_hit5_20": None, "cache_stop_20": None, "cache_R20": None,
            "cache_n_episodes": None, "d_hit5_vs_broad": None, "renames_n": None, "delisted_n": None}
    if a.cache_csv and os.path.exists(a.cache_csv):
        C = load_events(a.cache_csv, columns=["symbol", "date", "dir", "episode_dir", convP["hit5"],
                                              convP["stop"], convP["R"]])
        CB = C[(C["dir"] == DIRECTION_BASE) & (C["episode_dir"] == True)]              # noqa: E712
        cmeta = {}
        if os.path.exists(a.cache_csv + ".meta.json"):
            with open(a.cache_csv + ".meta.json") as fh:
                cmeta = json.load(fh)
        broad_syms = set(meta.get("symbols") or X["symbol"].unique().tolist())
        cache_syms = set(cmeta.get("symbols") or C["symbol"].unique().tolist())
        only = cache_syms - broad_syms
        surv = {"cache_n_names": int(CB["symbol"].nunique()), "cache_n_episodes": int(len(CB)),
                "cache_hit5_20": 100.0 * _nanmean(CB[convP["hit5"]]),
                "cache_stop_20": 100.0 * _nanmean(CB[convP["stop"]]),
                "cache_R20": _nanmean(CB[convP["R"]]),
                "d_hit5_vs_broad": 100.0 * _nanmean(CB[convP["hit5"]]) - base_P["hit5_20"],
                "d_stop_vs_broad": 100.0 * _nanmean(CB[convP["stop"]]) - base_P["stop_20"],
                "cache_only_n": int(len(only)),
                "renames_n": int(len(only & set(SY.RENAMES.keys()))),
                "delisted_n": int(len(only & set(SY.DELISTED.keys()))),
                "cache_nonpos_names": int((cmeta.get("tail") or {}).get("nonpos_names") or 0),
                "cache_nonpos_rows": int((cmeta.get("tail") or {}).get("nonpos_rows") or 0),
                "broad_nonpos_names": int((meta.get("tail") or {}).get("nonpos_names") or 0),
                "broad_nonpos_rows": int((meta.get("tail") or {}).get("nonpos_rows") or 0)}
        P("    SURVIVORSHIP  broad: names=%d ep=%d hit5@20 %.1f%% stop@20 %.1f%% R20 %+.3f | cache: names=%d ep=%d "
          "hit5@20 %.1f%% stop@20 %.1f%% R20 %+.3f | Δhit5 %+.2fpp Δstop %+.2fpp on the cached dead | cache-only names %d "
          "(RENAMES %d, DELISTED %d)"
          % (B["symbol"].nunique(), len(B), base_P["hit5_20"], base_P["stop_20"], base_P["R20"],
             surv["cache_n_names"], surv["cache_n_episodes"], surv["cache_hit5_20"], surv["cache_stop_20"],
             surv["cache_R20"], surv["d_hit5_vs_broad"], surv["d_stop_vs_broad"], surv["cache_only_n"],
             surv["renames_n"], surv["delisted_n"]))
        P("    SURVIVORSHIP hygiene: rows with a non-positive open/high/low/close dropped before any "
          "band is drawn (price_zones._cluster divides by its seed) — cache %d rows on %d names, "
          "broad %d rows on %d names."
          % (surv["cache_nonpos_rows"], surv["cache_nonpos_names"],
             surv["broad_nonpos_rows"], surv["broad_nonpos_names"]))
    else:
        P("    SURVIVORSHIP: no --cache-csv given — NO NUMBER ABOVE IS QUOTABLE WITHOUT THE CACHE LINE")
    P()
    P(RULE_TEXT)
    P("    PLACEBO for every line = the same cohort with n_kept events kept at random as WHOLE DATES (5-95th pct band);"
      " the i.i.d. band is printed second, never used.")

    per_feature = []
    for conv, D, D_ev in ((convP, B, B_all), (convN, BN, B_all[B_all["gap_N"] == False])):     # noqa: E712
        P()
        P("=" * 118)
        P("PER-FEATURE BUCKET TABLES — convention %s — bouncing EPISODES (n=%d); outcome column = %s"
          % (conv["label"], len(D), conv["hit"]))
        P("=" * 118)
        if len(D) < 100:
            P("  cohort too small")
            continue
        base = bucket_stats(D, D, conv, clocks, hold, E_ev=D_ev)
        for feat in conv["feats"]:
            if feat not in D:
                P("  %s: column missing" % feat)
                continue
            kind = feat_kind(feat)
            lab, order, edges = assign_buckets(D[feat], kind)
            lab_ev, _, _ = assign_buckets(D_ev[feat], kind, edges)
            o = orientation(D, feat, kind, lab, order, conv["hit"])
            top = top_bucket(lab, order, kind, o, D, conv["hit"])
            P()
            P("  %s [%s] orientation %+d (top = %s)%s" % (feat, kind, o, top,
                                                        "  edges %s" % ["%.4g" % e for e in edges[1:-1]] if edges else ""))
            P(fmt_row("base", base))
            rows_json = []
            for b_lab in order:
                m = lab == b_lab
                if not m.any():
                    continue
                s = bucket_stats(D, D[m], conv, clocks, hold, E_ev=D_ev[lab_ev == b_lab])
                P(fmt_row(b_lab, s))
                rb = evaluate_bucket(D, m, conv, a, base, full=False)
                P(fmt_ci_line(rb))
                rows_json.append({"label": b_lab, **{k: s[k] for k in (
                    "n_ep", "n_ev", "hit5_20", "hit5b_20", "stop_20", "R20", "room_pct", "risk_pct",
                    "room_risk", "d_risk", "clear_pct")},
                    **{k: rb.get(k) for k in ("d_hit5", "ci", "p_le0", "d_stop", "ci_stop", "d_R", "ci_R",
                                              "perm_p", "placebo_dates", "placebo_iid")}})
            r = evaluate_bucket(D, lab == top, conv, a, base)
            P("    TOP bucket %s:" % top)
            P(fmt_eval(r))
            if "ci" in r:
                BQ._dedupe(D[lab == top], "top %s" % top)
            per_feature.append({"name": feat, "variant": ("at" if feat.endswith("_at") else "pre"),
                                "convention": conv["tag"], "kind": kind, "orientation": o,
                                "buckets": rows_json,
                                "top": {"label": top, **{k: r.get(k) for k in (
                                    "n", "d_hit5", "ci", "p_le0", "d_stop", "ci_stop", "d_R", "ci_R",
                                    "d_hit5_reweighted", "ci_rw", "perm_p", "placebo_dates", "placebo_iid",
                                    "one_per_date", "one_per_symbol", "room_risk", "room_risk_base",
                                    "d_risk", "conditions", "verdict")}}})
        # controls: point tables only
        P()
        P("  CONTROLS (point estimates, no CI) — %s" % conv["tag"])
        for tag, C_ in (("all bouncing EVENTS", D_ev), ("all-direction EPISODES", A_ep if conv["tag"] == "P"
                                                       else A_ep[A_ep["gap_N"] == False])):   # noqa: E712
            P("    %s (n=%d): per-feature %s by bucket" % (tag, len(C_), conv["hit"]))
            for feat in conv["feats"]:
                if feat not in C_:
                    continue
                kind = feat_kind(feat)
                lab, order, _ = assign_buckets(C_[feat], kind)
                cells = ["%s %.1f(%d)" % (b_lab, 100.0 * _nanmean(C_.loc[lab == b_lab, conv["hit"]]),
                                          int((lab == b_lab).sum()))
                         for b_lab in order if (lab == b_lab).any()]
                P("      %-20s %s" % (feat, "  ".join(cells)))

    # exploratory tables (P episodes)
    P()
    P("=" * 118)
    n_cells = 0
    P("EXPLORATORY (printed, never scored) — P bouncing episodes; point rates by bucket")
    for feat in EXPLORATORY:
        if feat not in B:
            continue
        kind = feat_kind(feat)
        lab, order, _ = assign_buckets(B[feat], kind)
        cells = []
        for b_lab in order:
            m = lab == b_lab
            if not m.any():
                continue
            n_cells += 1
            cells.append("%s %.1f/%.1f(%d)" % (b_lab, 100.0 * _nanmean(B.loc[m, convP["hit"]]),
                                               100.0 * _nanmean(B.loc[m, convP["stop"]]), int(m.sum())))
        P("  %-22s hit5/stop(n): %s" % (feat, "  ".join(cells)))
    P("  cells tested: %d  -> expected false positives at 95%%: %.1f" % (n_cells, 0.05 * n_cells))
    P("=" * 118)

    # ── OOS splits (design §4.5) ──
    splits_out = {}
    winners = {}
    for conv, D in ((convP, B), (convN, BN)):
        P()
        P("=" * 118)
        P("COMBINED SCORE — three OOS splits — convention %s" % conv["label"])
        P("=" * 118)
        if len(D) < 200:
            P("  too small")
            continue
        ds = sorted(D["date"].unique())
        h1 = set(ds[:len(ds) // 2])
        in_h1 = D["date"].isin(h1)
        parity = D["symbol"].map(lambda s: zlib.crc32(str(s).encode()) % 2)
        res = {}
        res["s1"] = run_split(D, in_h1, ~in_h1, conv, a, "S1 date halves (fit H1 %s..%s, score H2)"
                              % (ds[0], ds[len(ds) // 2 - 1]), clocks, hold)
        res["s2"] = run_split(D, ~in_h1, in_h1, conv, a, "S2 reverse (fit H2, score H1)", clocks, hold)
        res["s3"] = run_split(D, parity == 0, parity == 1, conv, a, "S3 symbol-disjoint (fit parity 0, score parity 1)",
                              clocks, hold)
        survives = all(res[k]["verdict"] == "separates" for k in ("s1", "s2", "s3"))
        P("  CONVENTION %s: %s" % (conv["tag"], "SURVIVES on all three splits" if survives else "no_signal"))
        splits_out[conv["tag"]] = res
        winners[conv["tag"]] = survives

    status = "separates" if (winners.get("P") or winners.get("N")) else "no_signal"
    convention = "P" if winners.get("P") else ("N" if winners.get("N") else None)
    served = splits_out.get(convention or "P", {})
    s1 = served.get("s1", {})
    mdl = s1.get("mdl") if s1.get("mdl") is not None else (splits_out.get("P", {}).get("s1", {}).get("mdl"))
    splits_json = {}
    for k, r in splits_out.get(convention or "P", {}).items():
        splits_json[k] = {kk: r.get(kk) for kk in (
            "name", "n_fit", "n_scored", "top_decile_n", "d_hit5", "ci", "ci_2way", "d_stop", "ci_stop",
            "placebo", "perm_p", "d_hit5_top5", "d_hit5_top20", "quartile_gap", "rho", "mdl", "verdict",
            "selected", "expected_false_selections")}
    measured = {
        "run_date": _today_et(), "universe_mode": meta.get("universe_mode"),
        "n_names": int(B["symbol"].nunique()), "n_names_universe": meta.get("n_universe"),
        "n_events_all": int(len(E_all)), "n_events_bouncing": int(len(B_all)),
        "n_episodes": int(len(B)), "n_episodes_N": int(len(BN)), "n_dates": int(len(dates)), "window": window,
        "floor": meta.get("floor", a.floor), "clocks": list(clocks), "hold": hold,
        "convention": convention, "primary_outcome": a.primary,
        "base": {k: base_P[k] for k in ("hit5_5", "hit5_10", "hit5_20", "hit5b_20", "hit_lid_20", "n_lid",
                                        "stop_20", "R20", "R20_median", "R20_trim", "win20", "tgt_stop_clk",
                                        "room_pct", "risk_pct", "clear_pct", "hit5c_20")},
        "base_N": {k: base_N[k] for k in ("hit5_5", "hit5_10", "hit5_20", "hit5b_20", "hit_lid_20", "n_lid",
                                          "stop_20", "R20", "win20", "risk_pct")},
        "clear_pct_events": _cl_ev,                      # HIT_LID's denominator at event level
        "survivorship": surv, "liquidity_control": liq, "per_feature": per_feature,
        "selected": list(s1.get("selected") or []) if status == "separates" else [],
        "edges": (s1.get("edges") or {}) if status == "separates" else {},
        "splits": splits_json, "splits_N": {k: {kk: r.get(kk) for kk in ("d_hit5", "ci", "ci_2way", "verdict", "mdl", "selected")}
                                            for k, r in splits_out.get("N", {}).items()},
        "status": status, "fallback": "intact,room_rank", "script": SCRIPT,
        "cohort_note": ("cohort wider than what pushes: no cap floor; bands = board geometry on closed bars; "
                        "one regime %s; entry P = close[j], N = open[j+1]; stop booked at the stop through a gap; "
                        "no costs; episodes = first bouncing event per symbol + %d-bar cooldown" % (window, hold)),
        "intact_reconcile": rec, "quotable": quotable, "min_dvol_filter": a.min_dvol,
        "tail": meta.get("tail"), "counters": meta.get("counters"), "n_feature_nan": n_feat_nan,
        "walltime_stats_s": round(time.time() - t0, 1),
    }
    measured = _clean(measured)
    P()
    P("=" * 118)
    P("VERDICT: status=%s  convention=%s  MDL=%s pp  selected=%s  fallback=%s%s"
      % (status, convention, ("%.2f" % mdl) if mdl is not None else "n/a", measured["selected"],
         measured["fallback"], "   " + banner if banner else ""))
    P("=" * 118)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(measured, fh, indent=1)
        P("wrote %s" % a.json)
    if a.emit_measured:
        P()
        P("# ---- MEASURED literal (paste verbatim into supply_demand/explosive.py) ----")
        P("MEASURED = " + pprint.pformat(measured, width=100, sort_dicts=False))
    P("stats done %.0fs" % (time.time() - t0))
    return measured


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stage", default="both", choices=("replay", "stats", "both"))
    ap.add_argument("--universe", default="broad", choices=UNIVERSE_MODES)
    ap.add_argument("--floor", type=int, default=FLOOR_DEFAULT)
    ap.add_argument("--hold", type=int, default=HOLD_DEFAULT)
    ap.add_argument("--clocks", default=",".join(str(c) for c in CLOCKS_DEFAULT))
    ap.add_argument("--stride", type=int, default=1, help="every Nth of the sorted symbol list")
    ap.add_argument("--names", type=int, default=0, help="smoke only (NOT QUOTABLE)")
    ap.add_argument("--min-dvol", type=float, default=0.0)
    ap.add_argument("--chunk", type=int, default=300, help="symbols per events() call (memory)")
    ap.add_argument("--perm-draws", type=int, default=BQ.PERM_DRAWS)
    ap.add_argument("--boot-draws", type=int, default=BQ.BOOT_DRAWS)
    ap.add_argument("--placebo-draws", type=int, default=BQ.PLACEBO_DRAWS)
    ap.add_argument("--seed", type=int, default=SEED_BOOT)
    ap.add_argument("--primary", default="hit5", choices=OUTCOMES)
    ap.add_argument("--out", default="/tmp/explosive_events.csv")
    ap.add_argument("--from-csv", default=None)
    ap.add_argument("--cache-csv", default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument("--emit-measured", action="store_true")
    a = ap.parse_args(argv)
    if a.stage in ("replay", "both"):
        replay(a)
        a.from_csv = a.out
    if a.stage in ("stats", "both"):
        if not a.from_csv:
            ap.error("--from-csv is required for --stage stats")
        stats(a)


if __name__ == "__main__":
    main()
