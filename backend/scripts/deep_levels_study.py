"""DEEP DEMAND LEVELS — the STUDY (how many supports were crossed, and is the
band it landed in worth trading).

THE ASK (Ajay 2026-09-16, verbatim)
  "For the deep demand stocks I need the logic to be, the stocks that crosses
   the first level of support and lying in second or third level of support.
   Like CRDO dropped after the earning it crossed multiple support level."

The shipped read (`supply_demand/deep_demand.arrival` / `.read`) now WALKS the
served demand window instead of hardcoding dz[0]/dz[1], and reports
`levels_broken` / `level`. Two questions follow, and they are ONE replay:

  Q1  does DEPTH separate the outcome — is a name standing at its 2nd / 3rd /
      4th support level any different from one standing at its 1st-crossed
      level? (`levels_bucket` ∈ 1 / 2 / 3 / 4+, plus the rest of the cohort.)

  Q2  does the ARRIVAL BAND'S QUALITY separate it — touches (1 / 2 / 3+),
      strength below vs at-or-above `demand_reentry.MIN_ZONE_STRENGTH`, and
      the JOINT gate `arr_gate_pass` exactly as `deep_demand.read()` applies
      it? **THIS IS THE CELL THAT MATTERS.** That joint gate is the only
      reason CRDO — his own example — does not appear on the board: on
      2026-09-16, close 150.39, its served window was
      (161.92,167.68,t1,s28) (146.34,151.55,t1,s31) (132.76,138.00,t2,s54)
      (123.87,128.80,t3,s94); the GEOMETRY qualifies at level 2, and the
      arrival band is refused for `touches 1 < MIN_TOUCHES 2` and
      `strength 31 < MIN_ZONE_STRENGTH 40`. Whether that gate earns its keep
      is HIS CALL after this number — this script never changes it.

PRIMARY OUTCOME: `hit5` at `hold` = +ALERT_MIN_ROOM_PCT% before the stop (the
band floor less STOP_BUFFER_PCT), with `stop_20`, `R20` (mean / median /
trimmed) and `win20` printed beside it. NOTHING IS EVER RANKED ON WIN RATE.

THE PRIOR IS NULL. The 2026-09-16 `band_structure` study measured `no_signal`
on the adjacent claim (a second band below "catches" the name) and measured a
BIGGER first support band as HARMFUL. Nothing here may imply depth is an edge
before this replay lands; `supply_demand/deep_levels_measured.py` stays
`MEASURED = None` / `pending` until it does.

HOUSE RULES THIS FILE IS WRITTEN UNDER. NOT ONE threshold is typed here.
Every cut is an imported constant — `explosive_study.FIVE_PCT`
(= alert_gates.ALERT_MIN_ROOM_PCT), `.STOP_BUFFER_PCT`, `.FLOOR_DEFAULT`
(= zone_store.MIN_BARS), `.HOLD_DEFAULT` (= bounce_quality_study.HOLD_SESSIONS),
`.CLOCKS_DEFAULT`, `entry_trigger_study.MIN_CELL_N`,
`price_zones.MAX_ZONES_PER_SIDE`, `price_zones.NEAR_PCT`,
`demand_reentry.MIN_TOUCHES`, `demand_reentry.MIN_ZONE_STRENGTH`,
`deep_demand.MAX_LEVELS_BROKEN` — or a QUANTILE of the cohort itself. Nothing
here gates an alert, a lane or a push; paper only; read-only container probes.

WHAT IT REUSES (nothing importable is copied)
  * `supply_demand.deep_demand.arrival()` and `.read()` — THE SHIPPED
    QUALIFIER. The level walk and the band-quality gate are never
    re-implemented here; `arr_gate_pass` is literally "did `read()` return a
    dict for this record". If the shipped rule changes, this study changes
    with it.
  * `supply_demand.price_zones.nearest_first` — the SERVED window is
    reproduced by the engine's own cut, never by arithmetic here.
  * `studies.bounce_quality_study.events()` — the cohort, untouched.
  * `scripts.explosive_study` (ES) — the tail-bar rule, the universe modes,
    the outcome blocks, the bucket machinery, the date-clustered bootstrap,
    the date-block placebo, the one-per-date / one-per-symbol reweight, the
    loader and the §4.1 RULE OF READING text.
  * `scripts.entry_trigger_study` (ETS) — the per-feature table, the cell
    floor `MIN_CELL_N`, the three OOS splits (`split_masks`), the conditional
    MDL and the survivorship merge.
  * `scripts.band_structure_study` (BS) — the CONDITIONAL CONTRAST wrapper
    (`strat_cells` / `conditional_contrast` / `cond_verdict` / `fmt_cond`),
    used here with the LEVEL buckets as the strata, so "the gate works" is
    never really "the gate picks shallow names".

THE CAP, STATED TWICE — it decides who is even in this study.
`price_zones.compute` surfaces MAX_ZONES_PER_SIDE = 4 bands per side, cut by
DISTANCE from the print (`nearest_first(...)[:4]`), then sorted high→low. So
`rec["demand_zones"]` is a SLIDING WINDOW around the print, not the top of the
stack, and `levels_broken` counts the levels crossed WITHIN THAT WINDOW. A
name that fell a long way can have older bands above the window that nobody
counts. This study reproduces the window exactly as the scan serves it —
  sorted(PZ.nearest_first(demand_all, px)[:PZ.MAX_ZONES_PER_SIDE],
         key=lambda z: -z["mid"])
— and records the UNCAPPED-depth control `levels_broken_all` (the same shipped
`arrival()` run with its depth cap temporarily widened to the window length, a
parameter of the READ, never a change to the shipped constant) plus
`arrival_within_cap` (would `deep_demand.MAX_LEVELS_BROKEN` have kept it?).
Reading levels off the UNCAPPED band stack instead is HIS CALL (spec §7.3) and
is not done here.

UNIT OF ANALYSIS = EPISODES: the first reversal event per symbol then a
`hold`-bar cooldown (`ES.flag_episodes`), so forward windows never overlap
within a name.

SHIP-ELIGIBILITY. A read may ship only when it is computable from the SERVED
band fields at decision time with no lookahead — `ship_eligible_feature()` is
the single place that says so. The depth and quality reads all are; the
uncapped control is NOT (a served board cannot see it).

RUN (read-only; the branch tree is staged under /tmp, never written into /app)
THE TRAP THIS BLOCK EXISTS TO AVOID: the container runs origin/main, where
`deep_demand` has NO `arrival()`. `deep_demand.py` is a PACKAGE MODULE, so
piping the single file to /tmp does nothing — `from supply_demand import
deep_demand` still resolves inside /app. The whole package has to shadow it:

  tar -C backend --exclude __pycache__ -cf - supply_demand studies scripts \
      | docker exec -i cheetah-market-app-api-1 sh -c 'cd /tmp && tar xf -'
  # smoke (NOT QUOTABLE)
  docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/tmp:/app python -u \
      /tmp/scripts/deep_levels_study.py --stage both --universe broad --stride 40 \
      --out /tmp/deep_smoke.csv --json /tmp/deep_smoke.json'
  # the full replay, detached (broad, then the cache universe for survivorship)
  docker exec -d -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/tmp:/app python -u \
      /tmp/scripts/deep_levels_study.py --stage replay --universe broad \
      --out /tmp/deep_events.csv > /tmp/deep_broad.log 2>&1'
  docker exec -d -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/tmp:/app python -u \
      /tmp/scripts/deep_levels_study.py --stage replay --universe cache \
      --out /tmp/deep_events_cache.csv > /tmp/deep_cache.log 2>&1'
  docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/tmp:/app python -u \
      /tmp/scripts/deep_levels_study.py --stage stats --from-csv /tmp/deep_events.csv \
      --cache-csv /tmp/deep_events_cache.csv --json /tmp/deep_levels_measured.json \
      --emit-measured' | tee report.txt

The script must be invoked BY PATH, not with `-m`: a path invocation puts
/tmp/scripts at sys.path[0] and leaves the cwd off the path entirely, so
/tmp/supply_demand wins. `python -m scripts.deep_levels_study` (or `-c`) with
`-w /app` puts /app FIRST and silently measures the OLD dz[0]/dz[1] read.
VERIFIED 2026-09-16 in the api container: `deep_demand from
/tmp/supply_demand/deep_demand.py · has arrival: True`. Never run during RTH
(the hourly cache patch rewrites frames).

DEVIATIONS (each stated, none silent)
  1. `levels_broken_all` is produced by calling the SHIPPED `arrival()` under a
     temporarily widened `deep_demand.MAX_LEVELS_BROKEN` (`levels_cap()`), not
     by a second walk. The shipped constant is restored in a `finally`, and a
     test pins that it is unchanged after the call.
  2. `arr_gate_pass` is not a re-statement of the touches/strength rule: it is
     `deep_demand.read()` returning a dict on a record built from this row.
     One engine, so a future change to the gate cannot desync the study.
  3. Rows where `arrival()` finds nothing get the level bucket "none" — that
     merges "the first level still holds" (levels_broken == 0) with "price is
     in the air / under every band", which `arrival()` reports the same way
     (None). Both are non-arrivals for this screen; neither is a depth.
  4. Q1's "4+" bucket is EMPTY on a default run: the served window is 4 bands,
     so at most 3 can be crossed. It exists so a `--max-zones` control run can
     fill it, and an empty cell prints "not shown", never 0%.
  5. Mean R is a tail statistic and is reported, never a gate (ES §4.1).
  6. The conditional contrast strata are the LEVEL buckets (BS's machinery,
     BS's verdict rule), because the Q2 gate could otherwise "work" merely by
     selecting shallow arrivals.

RESULTS — pending. `--stage stats --emit-measured` has not been run on the full
universe; `supply_demand/deep_levels_measured.py` stays `MEASURED = None` /
`STATUS = pending` and every surface prints the not-measured sentence.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import pprint
import time
import types
from typing import Optional

import numpy as np
import pandas as pd

try:                                             # the container runs origin/main
    from scripts import explosive_study as ES    # (every file is piped to /tmp)
    from scripts import entry_trigger_study as ETS
    from scripts import band_structure_study as BS
except ImportError:                              # noqa: F401
    import explosive_study as ES                 # type: ignore
    import entry_trigger_study as ETS            # type: ignore
    import band_structure_study as BS            # type: ignore

from studies import bounce_quality_study as BQ
from supply_demand import deep_demand as DD
from supply_demand import demand_reentry as DR
from supply_demand import price_zones as PZ
from sepa import prices

SCRIPT = "backend/scripts/deep_levels_study.py"

P = ES.P
_f = ES._f
_nanmean = ES._nanmean
_today_et = ES._today_et
_pp = ETS._pp
_ci = ETS._ci

# ── every threshold IMPORTED; nothing on this page is typed ──────────────────
FIVE_PCT = ES.FIVE_PCT                      # 5.0  = AG.ALERT_MIN_ROOM_PCT
STOP_BUFFER_PCT = ES.STOP_BUFFER_PCT        # 0.5  = AG.STOP_BUFFER_PCT
FLOOR_DEFAULT = ES.FLOOR_DEFAULT            # 120  = zone_store.MIN_BARS
HOLD_DEFAULT = ES.HOLD_DEFAULT              # 20   = BQ.HOLD_SESSIONS
CLOCKS_DEFAULT = ES.CLOCKS_DEFAULT          # (5, 10, 20)
BOX_BARS = ES.BOX_BARS                      # 252  = price_zones.LOOKBACK_BARS
RVOL_LONG = ES.RVOL_LONG                    # 50   = breakout_audit.VOL_AVG_BARS
DIRECTION_BASE = ES.DIRECTION_BASE          # "bouncing" — the internal identifier
SEED_BOOT, SEED_PLACEBO = ES.SEED_BOOT, ES.SEED_PLACEBO
MIN_CELL_N = ETS.MIN_CELL_N                 # 120  — the cell floor
MAX_ZONES = PZ.MAX_ZONES_PER_SIDE           # 4    — the SERVED cap
NEAR_PCT = PZ.NEAR_PCT                      # 3.0  — "approaching from above"
MIN_TOUCHES = DR.MIN_TOUCHES                # 2    — the arrival band's bar
MIN_ZONE_STRENGTH = DR.MIN_ZONE_STRENGTH    # 40.0 — the arrival band's bar
MAX_LEVELS = DD.MAX_LEVELS_BROKEN           # the shipped depth cap; 3 since
                                            # 2026-09-16 ("can you do level 4")
SUBSAMPLE_NOT_QUOTABLE = ETS.SUBSAMPLE_NOT_QUOTABLE
SURVIVORSHIP_MISSING = ETS.SURVIVORSHIP_MISSING

CAP_NOTE = (
    "the SERVED demand window is reproduced exactly as the scan serves it — "
    "sorted(price_zones.nearest_first(demand_all, px)[:%d], key=-mid) "
    "(MAX_ZONES_PER_SIDE), a SLIDING WINDOW around the print, not the top of the stack — so "
    "levels_broken counts the levels crossed INSIDE that window. levels_broken_all is the same "
    "shipped arrival() with its depth cap widened to the window length (a parameter of the READ, "
    "never of the shipped constant); arrival_within_cap says whether deep_demand."
    "MAX_LEVELS_BROKEN = %d would have kept the row." % (MAX_ZONES, MAX_LEVELS))

GATE_NOTE = (
    "arr_gate_pass is deep_demand.read() returning a dict for the row — the JOINT band bar on the "
    "ARRIVAL band (touches >= MIN_TOUCHES %d AND strength >= MIN_ZONE_STRENGTH %g), imported, "
    "never restated. It is the only reason CRDO (close 150.39, arrival band touches 1 / strength "
    "31) is hidden; relaxing it is Ajay's call, after this number."
    % (MIN_TOUCHES, MIN_ZONE_STRENGTH))

FALLBACK = "no depth ordering, no depth gate — the board stays proximity-first"

# ── bucket labels: built FROM the constants, never typed as numbers ──────────
LEVELS_NONE = "none"                        # arrival() found nothing (see deviation 3)
LEVELS_DEEPEST = "4+"
LEVELS_ORDER = ("1", "2", "3", LEVELS_DEEPEST, LEVELS_NONE)
TOUCH_MIN_LABEL = "%d" % MIN_TOUCHES
TOUCH_UNDER_LABEL = "%d" % (MIN_TOUCHES - 1)
TOUCH_OVER_LABEL = "%d+" % (MIN_TOUCHES + 1)
TOUCH_NA = "no touches"
TOUCH_ORDER = (TOUCH_UNDER_LABEL, TOUCH_MIN_LABEL, TOUCH_OVER_LABEL, TOUCH_NA)
STRENGTH_LO = "<%g" % MIN_ZONE_STRENGTH
STRENGTH_HI = ">=%g" % MIN_ZONE_STRENGTH
STRENGTH_NA = "no strength"
STRENGTH_ORDER = (STRENGTH_LO, STRENGTH_HI, STRENGTH_NA)

# ── pre-registered feature sets — FROZEN before the first full run ───────────
DEPTH_FEATS = ("levels_bucket",)
QUALITY_FEATS = ("arr_touches_bucket", "arr_strength_side", "arr_gate_pass",
                 "arr_touches", "arr_strength", "arr_height_pct", "arr_dist_pct")
STRATIFIERS = ("levels_bucket",)
EXPLORATORY = ("levels_broken", "levels_broken_all", "levels_bucket_all",
               "arrival_within_cap", "deep_state", "level")

DEEP_BOOL_FEATS = {"arr_gate_pass", "arrival_within_cap"}
DEEP_STATE_FEATS = {"levels_bucket", "levels_bucket_all", "arr_touches_bucket",
                    "arr_strength_side", "deep_state"}
ES.BOOL_FEATS |= set(DEEP_BOOL_FEATS)            # so ES.load_events casts them
ES.STATE_FEATS |= set(DEEP_STATE_FEATS)

OUTCOMES = ES.OUTCOMES


# ═════════════════════════════════════════════════════════════════════════════
# THE PURE READS — no Mongo, no pandas; the SHIPPED qualifier does the walking
# ═════════════════════════════════════════════════════════════════════════════
def served_window(demand_all, px, max_zones: int = MAX_ZONES) -> list:
    """The demand bands a scan record would actually carry, reproduced by the
    ENGINE'S OWN cut: nearest `max_zones` by distance from the print, then
    sorted high→low. Never re-derived by arithmetic here."""
    p = _f(px)
    if p is None or p <= 0:
        return []
    near = PZ.nearest_first([b for b in (demand_all or []) if isinstance(b, dict)], p)
    cut = near[:max(0, int(max_zones))]
    return sorted(cut, key=lambda z: -float(z.get("mid", z.get("hi", 0.0)) or 0.0))


@contextlib.contextmanager
def levels_cap(n: int):
    """Run the SHIPPED `arrival()` with its DEPTH cap temporarily widened — the
    cap is a parameter of this READ (like `--max-zones`), never a change to the
    shipped constant, which is restored in `finally`. Deviation #1."""
    orig = DD.MAX_LEVELS_BROKEN
    DD.MAX_LEVELS_BROKEN = int(n)
    try:
        yield
    finally:
        DD.MAX_LEVELS_BROKEN = orig


def levels_bucket(n) -> str:
    """1 / 2 / 3 / 4+ — and LEVELS_NONE when nothing was crossed (deviation 3).
    NEVER returns "0": a non-arrival is not a depth of zero."""
    v = _f(n)
    if v is None or v < 1:
        return LEVELS_NONE
    k = int(v)
    return str(k) if k <= 3 else LEVELS_DEEPEST


def touches_bucket(t) -> str:
    """The arrival band's touch count in the three cells the gate cares about,
    named FROM `MIN_TOUCHES`. A MISSING touch count is its own bucket — a band
    with no count is not a 1-touch band."""
    v = _f(t)
    if v is None:
        return TOUCH_NA
    k = int(v)
    if k <= MIN_TOUCHES - 1:
        return TOUCH_UNDER_LABEL
    if k == MIN_TOUCHES:
        return TOUCH_MIN_LABEL
    return TOUCH_OVER_LABEL


def strength_side(s) -> str:
    """Below vs at-or-above `MIN_ZONE_STRENGTH` — the CUT IS IMPORTED, the
    label is built from it. A MISSING strength is its own bucket and is NEVER
    silently counted as below the cut (the shipped gate treats `None` as 0 and
    refuses the row; that is a REFUSAL, not evidence about weak bands)."""
    v = _f(s)
    if v is None:
        return STRENGTH_NA
    return STRENGTH_HI if v >= MIN_ZONE_STRENGTH else STRENGTH_LO


def arrival_read(px, demand_all, prev_close=None, max_zones: int = MAX_ZONES) -> dict:
    """One row's deep-level read, entirely through the SHIPPED functions.

    `levels_broken` / `level` / `deep_state` come from `deep_demand.arrival()`
    under the shipped depth cap; `levels_broken_all` from the same function
    with the cap widened to the window length; `arr_gate_pass` from
    `deep_demand.read()` itself, so the joint band bar is never restated."""
    out = {"levels_broken": None, "level": None, "levels_broken_all": None,
           "arrival_within_cap": None, "deep_state": None,
           "arr_lo": None, "arr_hi": None, "arr_touches": None, "arr_strength": None,
           "arr_height_pct": None, "arr_dist_pct": None, "arr_gate_pass": None,
           "n_window": None}
    p = _f(px)
    if p is None or p <= 0:
        return out
    dz = served_window(demand_all, p, max_zones)
    out["n_window"] = len(dz)
    if len(dz) < 2:
        return out
    with levels_cap(max(1, len(dz))):
        got_all = DD.arrival(dz, p)
    if got_all is None:
        return out                       # first level still holding, or in the air
    n_all, arr, _broken_all = got_all
    out["levels_broken_all"] = int(n_all)
    out["arrival_within_cap"] = bool(int(n_all) <= DD.MAX_LEVELS_BROKEN)
    shipped = DD.arrival(dz, p)          # the SHIPPED depth cap, untouched
    if shipped is not None:
        out["levels_broken"] = int(shipped[0])
        out["level"] = int(shipped[0]) + 1
    lo, hi = _f(arr.get("lo")), _f(arr.get("hi"))
    if lo is None or hi is None:
        return out
    out.update({"arr_lo": lo, "arr_hi": hi,
                "arr_touches": _f(arr.get("touches")),
                "arr_strength": _f(arr.get("strength")),
                "arr_height_pct": (hi - lo) / p * 100.0,
                "deep_state": "in" if lo <= p <= hi else "near",
                "arr_dist_pct": 0.0 if lo <= p <= hi else (p - hi) / p * 100.0})
    # The JOINT band bar, read through `read()` itself — under the WIDENED depth
    # cap, so a row refused for being too DEEP never reads as a quality failure.
    rec = {"demand_zones": dz, "last_price": p, "prev_close": prev_close}
    with levels_cap(max(1, len(dz))):
        out["arr_gate_pass"] = DD.read(rec) is not None
    return out


def bucket_columns(r: dict) -> dict:
    """The three cell assigners, off one `arrival_read` row."""
    return {"levels_bucket": levels_bucket(r.get("levels_broken")),
            "levels_bucket_all": levels_bucket(r.get("levels_broken_all")),
            "arr_touches_bucket": (touches_bucket(r.get("arr_touches"))
                                   if r.get("levels_broken_all") is not None else None),
            "arr_strength_side": (strength_side(r.get("arr_strength"))
                                  if r.get("levels_broken_all") is not None else None)}


def ship_eligible_feature(feat: str) -> tuple:
    """(ok, reason). Ship-eligible = computable from the SERVED band fields at
    decision time with no lookahead."""
    if feat in ("levels_broken_all", "levels_bucket_all", "arrival_within_cap"):
        return False, ("uncapped-depth control — a served board cannot see it; %s" % CAP_NOTE)
    if feat in DEPTH_FEATS or feat in QUALITY_FEATS or feat in ("levels_broken", "level",
                                                                "deep_state"):
        return True, "served band field at the print"
    return False, "not a pre-registered served read"


# ═════════════════════════════════════════════════════════════════════════════
# STAGE: replay
# ═════════════════════════════════════════════════════════════════════════════
def features_for_symbol(sym: str, f: pd.DataFrame, ev: pd.DataFrame, hold: int, clocks,
                        geom: dict, counters: dict, max_zones: int = MAX_ZONES) -> list:
    pos_of = {d: i for i, d in enumerate(f["d"].tolist())}
    o = f["open"].to_numpy(dtype=float)
    h = f["high"].to_numpy(dtype=float)
    l = f["low"].to_numpy(dtype=float)
    c = f["close"].to_numpy(dtype=float)
    v = f["volume"].to_numpy(dtype=float)
    n = len(f)
    dvol = pd.Series(c * v).rolling(RVOL_LONG, min_periods=RVOL_LONG).median().to_numpy()
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
        prev = float(c[j - 1])
        row = {"symbol": sym, "date": str(r.date), "bar_idx": j}
        # ── bands at j from bars STRICTLY BEFORE j (the engine's own call) ──
        z = PZ.compute(f.iloc[max(0, j - BOX_BARS):j], last_price=px, max_zones=None, **geom)
        dz_all = (z or {}).get("demand_zones") or []
        bands_all = ((z or {}).get("supply_zones") or []) + dz_all
        ea = ETS.event_at(o, h, l, c, j, bands_all)
        band1 = ea["band"] if ea else None
        if band1 is None:
            counters["no_band"] += 1
        elif abs(float(band1["lo"]) * buf - stop) > 1e-6:
            counters["band_mismatch"] += 1
        ar = arrival_read(px, dz_all, prev, max_zones)
        if ar.get("levels_broken") is not None:
            counters["arrivals"] += 1
        row.update(ar)
        row.update(bucket_columns(ar))
        row["dvol50_pre"] = float(dvol[j - 1]) if np.isfinite(dvol[j - 1]) else np.nan
        band_hi = float(band1["hi"]) if band1 else None
        # ── outcomes: the engine's two conventions, untouched ──
        fh = h[j + 1:j + 1 + max_clock]
        fl = l[j + 1:j + 1 + max_clock]
        fc = c[j + 1:j + 1 + max_clock]
        blk = ES.outcome_block(fh, fl, fc, px, stop, target, band_hi, clocks, hold)
        for cl in sorted(set(clocks) | {hold}):
            blk.pop("R%d" % cl)                  # the engine's R{cl}/why{cl} stay authoritative
            blk.pop("why%d" % cl)                # (and a duplicate column would break the join)
        row.update(blk)
        row.update(ES.next_open_block(o[j + 1], fh, fl, fc, stop, target, band_hi, clocks, hold))
        out.append(row)
    return out


def add_features(E: pd.DataFrame, hold: int, clocks, counters: dict,
                 max_zones: int = MAX_ZONES) -> pd.DataFrame:
    coll = prices._get_mongo()
    geom = DR.zone_geom()
    rows = []
    for sym, ev in E.groupby("symbol", sort=True):
        f = ES.frame_with_tail_rule(coll, sym)
        if f is None:
            counters["no_frame"] += 1
            continue
        rows.extend(features_for_symbol(sym, f, ev, hold, clocks, geom, counters, max_zones))
    F = pd.DataFrame(rows)
    X = ES.join_features(E, F)
    X["bar_idx"] = pd.to_numeric(X["bar_idx"], errors="coerce")
    X["episode"] = ES.flag_episodes(X, hold)
    X["episode_dir"] = ES.flag_episodes(X, hold, within="dir")
    return X


def replay(a) -> None:
    t0 = time.time()
    clocks = tuple(int(x) for x in str(a.clocks).split(","))
    hold, floor = int(a.hold), int(a.floor)
    need = floor + hold + 2
    syms = ES.symbols_for(a.universe, need, stride=a.stride, names=a.names)
    if a.names or a.stride > 1:
        P("NOT QUOTABLE — smoke (--stride %d --names %d)" % (a.stride, a.names))
    BQ.CLOCKS = clocks
    BQ._frame = ES.frame_with_tail_rule
    P("replay  universe=%s  n=%d  floor=%d  hold=%d  clocks=%s  stride=%d  min_dvol=%g  "
      "max_zones(read)=%d  max_levels(shipped)=%d  today=%s"
      % (a.universe, len(syms), floor, hold, clocks, a.stride, a.min_dvol, a.max_zones,
         MAX_LEVELS, _today_et()))
    P("CAP: %s" % CAP_NOTE)
    P("GATE: %s" % GATE_NOTE)
    counters = {"no_bar": 0, "no_band": 0, "band_mismatch": 0, "no_frame": 0, "arrivals": 0}
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
        X = add_features(E, hold, clocks, counters, a.max_zones)
        X.to_csv(a.out, index=False, mode="a", header=first)
        first = False
        n_rows += len(X)
        P("  chunk %d..%d  events=%d  total=%d  %.0fs"
          % (k0, k0 + len(part), len(X), n_rows, time.time() - t0))
    meta = {"universe_mode": a.universe, "n_universe": len(syms), "symbols": syms,
            "n_frames": ES.TAIL["names"], "tail": dict(ES.TAIL), "counters": counters,
            "clocks": list(clocks), "floor": floor, "hold": hold, "today": _today_et(),
            "n_rows": n_rows, "walltime_s": round(time.time() - t0, 1),
            "stride": a.stride, "names": a.names, "min_dvol": a.min_dvol,
            "max_zones_read": a.max_zones, "max_levels_shipped": MAX_LEVELS,
            "cap_note": CAP_NOTE, "gate_note": GATE_NOTE}
    with open(a.out + ".meta.json", "w") as fh:
        json.dump(meta, fh)
    P("replay done  rows=%d  frames=%d  counters=%s  %.0fs"
      % (n_rows, ES.TAIL["names"], counters, time.time() - t0))


# ═════════════════════════════════════════════════════════════════════════════
# STAGE: stats
# ═════════════════════════════════════════════════════════════════════════════
def conventions(primary: str, hold: int) -> dict:
    """ES's P and N, carrying THIS study's feature sets."""
    base = ES.conventions(primary, hold)
    feats = list(DEPTH_FEATS) + list(QUALITY_FEATS)
    base["P"]["feats"] = feats
    base["N"]["feats"] = feats
    return base


def wanted_columns(clocks, hold: int, primary: str) -> list:
    cols = ["symbol", "date", "dir", "entry", "stop", "target", "room_pct", "clear",
            "risk_pct", "R", "why", "episode", "episode_dir", "bar_idx", "dvol50_pre",
            "band_lo", "band_hi", "gap_N", "risk_pct_N", "entry_N",
            "arr_lo", "arr_hi", "n_window"]
    for cl in sorted(set(clocks) | {hold}):
        cols += ["R%d" % cl, "why%d" % cl, "pct%d" % cl, "hit5_%d" % cl, "hit5b_%d" % cl,
                 "hit_lid_%d" % cl, "stop_%d" % cl, "hit5_%d_N" % cl, "hit_lid_%d_N" % cl,
                 "stop_%d_N" % cl, "R%d_N" % cl, "why%d_N" % cl]
    cols += ["hit5c_%d" % hold, "hit5c_%d_N" % hold, "max_gain_pct_%d" % hold]
    cols += list(dict.fromkeys(DEPTH_FEATS + QUALITY_FEATS + STRATIFIERS + EXPLORATORY))
    return list(dict.fromkeys(cols))


def load_events(path: str, clocks, hold: int, primary: str) -> pd.DataFrame:
    return ES.load_events(path, columns=wanted_columns(clocks, hold, primary))


def cell_order(D: pd.DataFrame, col: str, order) -> list:
    """The declared label order, restricted to the labels the cohort has."""
    have = set(str(x) for x in D[col].dropna().unique()) if col in D else set()
    return [name for name in order if name in have]


def cells_table(D: pd.DataFrame, col: str, order, conv: dict, clocks, hold: int) -> list:
    """Every cell of a state column with hit5 FIRST and stop / R / win beside it.
    A cell under `MIN_CELL_N` prints "not shown" and carries NO rates — an
    under-floor cell must never look like a measurement."""
    out = []
    if col not in D:
        return out
    lab = D[col].astype(object).where(D[col].notna(), None)
    for name in cell_order(D, col, order):
        m = lab.astype(str) == name
        n = int(m.sum())
        if n < MIN_CELL_N:
            out.append({"cell": name, "n": n, "shown": False,
                        "note": "n<%d — not shown" % MIN_CELL_N})
            P("    %-12s n=%-6d  n<%d — not shown" % (name, n, MIN_CELL_N))
            continue
        s = ES.bucket_stats(D, D[m], conv, clocks, hold)
        out.append({"cell": name, "n": n, "shown": True,
                    "hit5_%d" % hold: s["hit5_%d" % hold], "stop_20": s["stop_20"],
                    "R20": s["R20"], "R20_median": s["R20_median"],
                    "R20_trim": s["R20_trim"], "win20": s["win20"],
                    "tgt_stop_clk": s["tgt_stop_clk"]})
        P("    %-12s n=%-6d %s" % (name, n, ES.fmt_row(name, s).strip()))
    return out


def question_block(D: pd.DataFrame, conv: dict, a, clocks, hold: int, label: str,
                   feats, strats) -> dict:
    """One question end to end: the per-feature table, the conditional contrast
    inside each stratifier's cells (BS's machinery, BS's verdict), and the
    three OOS splits."""
    P("")
    P("-" * 118)
    P("%s — convention %s   n=%d   (%s)" % (label, conv["tag"], len(D), conv["label"]))
    P("-" * 118)
    conv = dict(conv)
    conv["feats"] = list(feats)                  # the split scores exactly what was tabled
    per_feature: list = []
    ETS.feature_table(D, conv, a, clocks, hold, feats, per_feature, label)
    cond: dict = {}
    for p in per_feature:
        feat = p["name"]
        ok, why = ship_eligible_feature(feat)
        p["ship_eligible"] = bool(ok)
        p["ship_eligible_reason"] = why
        if feat not in D:
            continue
        kind = ES.feat_kind(feat)
        lab, order, _ = ES.assign_buckets(D[feat], kind)
        o = ES.orientation(D, feat, kind, lab, order, conv["hit"])
        top = ES.top_bucket(lab, order, kind, o, D, conv["hit"])
        mask = lab == top
        cond[feat] = {}
        for sc in strats:
            if sc == feat:                       # a feature cannot stratify itself
                continue
            order_s = cell_order(D, sc, LEVELS_ORDER)
            if not order_s:
                cond[feat][sc] = {"stratifier": sc, "verdict": "stratifier absent"}
                continue
            r = BS.conditional_contrast(D, mask, sc, conv, a, order_s)
            r["top"] = top
            cond[feat][sc] = r
            P(BS.fmt_cond(feat, r))
    splits = {}
    for name, m in ETS.split_masks(D):
        key = name.split()[0]
        splits[key] = ES.run_split(D, m, ~m, conv, a, name, clocks, hold)
    return {"convention": conv["tag"], "n": int(len(D)), "per_feature": per_feature,
            "conditional": cond, "splits": splits}


def block_status(block: dict) -> tuple:
    """A question SEPARATES only when a ship-eligible feature's top bucket
    separates on ALL THREE OOS splits AND every conditional contrast it has
    separates too. Otherwise no_signal + the MDL."""
    splits = block.get("splits") or {}
    all_split = bool(splits) and all((s or {}).get("verdict") == "separates"
                                     for s in splits.values())
    mdls = [s.get("mdl") for s in splits.values() if s.get("mdl") is not None]
    mdl = max(mdls) if mdls else None
    selected = []
    for p in block.get("per_feature") or []:
        if not p.get("ship_eligible"):
            continue
        if ((p.get("top") or {}).get("verdict")) != "separates":
            continue
        conds = (block.get("conditional") or {}).get(p["name"]) or {}
        if conds and not all((c or {}).get("verdict") == "separates" for c in conds.values()):
            continue
        selected.append(p["name"])
    status = "separates" if (selected and all_split) else "no_signal"
    return status, selected, mdl


def gate_block(D: pd.DataFrame, conv: dict, a, clocks, hold: int, base: dict) -> dict:
    """THE CELL THAT MATTERS — the joint band bar `deep_demand.read()` applies
    to the arrival band, on the ARRIVALS only. If the gate does not separate
    here, the MIN_TOUCHES / MIN_ZONE_STRENGTH bar is keeping CRDO — and the
    several hundred names blocked by it on 2026-09-16 — off the board for
    nothing measurable. Relaxing it is HIS CALL, after this number."""
    out = {"note": GATE_NOTE, "n_arrivals": 0, "cells": {}, "eval": None,
           "verdict": "n<%d — not shown" % MIN_CELL_N}
    if "arr_gate_pass" not in D:
        out["verdict"] = "column absent"
        return out
    g = D["arr_gate_pass"]
    arr = g.notna()
    out["n_arrivals"] = int(arr.sum())
    P("")
    P("  THE GATE — %s" % GATE_NOTE)
    passes = arr & (g == True)                                       # noqa: E712
    fails = arr & (g == False)                                       # noqa: E712
    for name, m in (("pass", passes), ("fail", fails)):
        n = int(m.sum())
        if n < MIN_CELL_N:
            out["cells"][name] = {"n": n, "shown": False,
                                  "note": "n<%d — not shown" % MIN_CELL_N}
            P("    gate %-5s n=%-6d  n<%d — not shown" % (name, n, MIN_CELL_N))
            continue
        s = ES.bucket_stats(D, D[m], conv, clocks, hold)
        out["cells"][name] = {"n": n, "shown": True,
                              "hit5_%d" % hold: s["hit5_%d" % hold],
                              "stop_20": s["stop_20"], "R20": s["R20"],
                              "R20_median": s["R20_median"], "win20": s["win20"]}
        P("    gate %-5s n=%-6d %s" % (name, n, ES.fmt_row(name, s).strip()))
    if int(passes.sum()) >= MIN_CELL_N and int(fails.sum()) >= MIN_CELL_N:
        r = ES.evaluate_bucket(D, passes, conv, a, base)
        out["eval"] = {k: r.get(k) for k in ("n", "d_hit5", "ci", "d_stop", "ci_stop",
                                             "d_hit5_reweighted", "ci_rw", "placebo_dates",
                                             "one_per_date", "one_per_symbol", "verdict")}
        out["verdict"] = r.get("verdict")
        P(ES.fmt_eval(r))
    else:
        P("    -> n<%d on one side — not shown" % MIN_CELL_N)
    return out


def stats(a) -> dict:
    t0 = time.time()
    clocks = tuple(int(x) for x in str(a.clocks).split(","))
    hold = int(a.hold)
    X = load_events(a.from_csv, clocks, hold, a.primary)
    meta = {}
    if os.path.exists(a.from_csv + ".meta.json"):
        with open(a.from_csv + ".meta.json") as fh:
            meta = json.load(fh)
    sample_ok = not (a.names or meta.get("names") or a.stride > 1 or (meta.get("stride") or 1) > 1)
    banner = "" if sample_ok else "NOT QUOTABLE — smoke (%s)" % SUBSAMPLE_NOT_QUOTABLE
    if banner:
        P("=" * 118 + "\n" + banner + "\n" + "=" * 118)
    if a.min_dvol:
        d = pd.to_numeric(X["dvol50_pre"], errors="coerce")
        X = X[d >= float(a.min_dvol)].reset_index(drop=True)
        P("LIQUIDITY CONTROL RUN — cohort restricted to dvol50_pre >= %g" % a.min_dvol)

    convs = conventions(a.primary, hold)
    convP, convN = convs["P"], convs["N"]
    B_all = X[X["dir"] == DIRECTION_BASE].reset_index(drop=True)
    B = B_all[B_all["episode_dir"] == True].reset_index(drop=True)           # noqa: E712
    dates = sorted(X["date"].unique())
    window = "%s -> %s" % (dates[0], dates[-1]) if dates else "n/a"

    P("=" * 118)
    P("DEEP DEMAND LEVELS — STUDY  (%s)   script %s" % (_today_et(), SCRIPT))
    P("COHORT  demand band reached (bounce_quality_study.events, both standing gates); "
      "floor=%s bars, clocks=%s, hold=%d; stop = band floor -%g%%; target = +%g%%; universe=%s"
      % (meta.get("floor", a.floor), clocks, hold, STOP_BUFFER_PCT, FIVE_PCT,
         meta.get("universe_mode", "?")))
    P("        all events n=%d   reversal events n=%d   reversal EPISODES n=%d   dates=%d   window %s"
      % (len(X), len(B_all), len(B), len(dates), window))
    P("CAP: %s" % CAP_NOTE)
    P("GATE: %s" % GATE_NOTE)
    P("PRIOR: band_structure 2026-09-16 measured no_signal on the adjacent claim and a BIGGER "
      "first support band as HARMFUL. Depth starts from a null.")
    P("")
    P(ES.RULE_TEXT)

    base_P = ES.bucket_stats(B, B, convP, clocks, hold)
    P("")
    P(ES.fmt_row("base P", base_P))

    P("")
    P("  Q1 CELLS — how many demand levels the print crossed inside the served window:")
    lv_cells = cells_table(B, "levels_bucket", LEVELS_ORDER, convP, clocks, hold)
    P("  control — the same count with the DEPTH cap widened to the window (not ship-eligible):")
    lv_cells_all = cells_table(B, "levels_bucket_all", LEVELS_ORDER, convP, clocks, hold)

    q1 = question_block(B, convP, a, clocks, hold,
                        "Q1 — does DEPTH (levels crossed) separate?",
                        list(DEPTH_FEATS), [])
    q1["cells"] = lv_cells
    q1["cells_uncapped"] = lv_cells_all
    q1_status, q1_sel, q1_mdl = block_status(q1)

    P("")
    P("  Q2 CELLS — the ARRIVAL band's own quality (arrivals only):")
    ARR = B[B["levels_broken_all"].notna()].reset_index(drop=True) \
        if "levels_broken_all" in B else B.iloc[0:0]
    P("    arrivals n=%d of %d episodes" % (len(ARR), len(B)))
    t_cells = cells_table(ARR, "arr_touches_bucket", TOUCH_ORDER, convP, clocks, hold)
    s_cells = cells_table(ARR, "arr_strength_side", STRENGTH_ORDER, convP, clocks, hold)

    q2 = question_block(B, convP, a, clocks, hold,
                        "Q2 — does the ARRIVAL BAND'S QUALITY separate?",
                        list(QUALITY_FEATS), list(STRATIFIERS))
    q2["cells_touches"] = t_cells
    q2["cells_strength"] = s_cells
    q2["gate"] = gate_block(B, convP, a, clocks, hold, base_P)
    q2["n_arrivals"] = int(len(ARR))
    q2_status, q2_sel, q2_mdl = block_status(q2)

    P("")
    P("CONTROL — the same quality table under convention N (entry open[j+1]):")
    BN = B[B["gap_N"] == False].reset_index(drop=True)                        # noqa: E712
    per_N: list = []
    if len(BN) >= MIN_CELL_N:
        ETS.feature_table(BN, convN, a, clocks, hold, list(QUALITY_FEATS), per_N, "Q2 control (N)")
    for p in per_N:
        ok, why = ship_eligible_feature(p["name"])
        p["ship_eligible"], p["ship_eligible_reason"] = bool(ok), why

    surv = ETS.survivorship_read(a, convP, base_P.get("hit5_%d" % hold))
    surv_ok = ETS.survivorship_present(surv)
    if not surv_ok:
        P("    %s" % SURVIVORSHIP_MISSING)
    quotable = bool(sample_ok and surv_ok)

    status = "separates" if "separates" in (q1_status, q2_status) else "no_signal"
    measured = {
        "run_date": _today_et(), "script": SCRIPT, "quotable": quotable,
        "not_quotable_reason": (None if quotable else
                                (SUBSAMPLE_NOT_QUOTABLE if not sample_ok else SURVIVORSHIP_MISSING)),
        "universe_mode": meta.get("universe_mode"), "n_universe": meta.get("n_universe"),
        "n_events_all": int(len(X)), "n_events_reversal": int(len(B_all)),
        "n_episodes": int(len(B)), "n_episodes_N": int(len(BN)), "n_dates": int(len(dates)),
        "window": window, "floor": meta.get("floor", a.floor), "clocks": list(clocks),
        "hold": hold, "primary_outcome": a.primary,
        "max_zones_read": meta.get("max_zones_read", a.max_zones),
        "max_levels_shipped": MAX_LEVELS, "near_pct": NEAR_PCT,
        "min_touches": MIN_TOUCHES, "min_zone_strength": MIN_ZONE_STRENGTH,
        "cap_note": CAP_NOTE, "gate_note": GATE_NOTE,
        "levels_order": list(LEVELS_ORDER), "touch_order": list(TOUCH_ORDER),
        "strength_order": list(STRENGTH_ORDER),
        "base": {k: base_P[k] for k in ("hit5_5", "hit5_10", "hit5_20", "hit5b_20",
                                        "hit_lid_20", "n_lid", "stop_20", "R20", "R20_median",
                                        "R20_trim", "win20", "tgt_stop_clk", "room_pct",
                                        "risk_pct", "clear_pct")},
        "q1": dict(q1, status=q1_status, selected=q1_sel, mdl=q1_mdl,
                   question=("does the number of demand levels crossed separate +%g%% before "
                             "the floor within %d sessions?" % (FIVE_PCT, hold))),
        "q2": dict(q2, status=q2_status, selected=q2_sel, mdl=q2_mdl,
                   question=("does the ARRIVAL band's quality — touches, strength, and the "
                             "joint gate read() applies — separate the same outcome?")),
        "control_N": per_N, "survivorship": surv, "status": status, "fallback": FALLBACK,
        "cohort_note": ("reversal episodes only (first per symbol + %d-bar cooldown); bands on "
                        "CLOSED bars strictly before the print with the board geometry, then cut "
                        "to the served window; no costs; one regime %s" % (hold, window)),
        "walltime_stats_s": round(time.time() - t0, 1),
    }
    measured = ES._clean(measured)
    P("")
    P("=" * 118)
    P("VERDICT  Q1 %s (selected %s, MDL %s pp)   Q2 %s (selected %s, MDL %s pp)   gate: %s"
      % (q1_status, q1_sel or "NONE", _pp(q1_mdl), q2_status, q2_sel or "NONE", _pp(q2_mdl),
         (q2.get("gate") or {}).get("verdict")))
    P("         fallback: %s%s" % (FALLBACK, "   " + banner if banner else ""))
    P("=" * 118)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(measured, fh, indent=1)
        P("wrote %s" % a.json)
    if a.emit_measured:
        P("")
        P("# ---- MEASURED literal (paste verbatim into supply_demand/deep_levels_measured.py) ----")
        P("MEASURED = " + pprint.pformat(measured, width=100, sort_dicts=False))
    P("stats done %.0fs" % (time.time() - t0))
    return measured


# ═════════════════════════════════════════════════════════════════════════════
def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stage", default="both", choices=("replay", "stats", "both"))
    ap.add_argument("--universe", default="broad", choices=ES.UNIVERSE_MODES)
    ap.add_argument("--floor", type=int, default=FLOOR_DEFAULT)
    ap.add_argument("--hold", type=int, default=HOLD_DEFAULT)
    ap.add_argument("--clocks", default=",".join(str(c) for c in CLOCKS_DEFAULT))
    ap.add_argument("--stride", type=int, default=1, help="every Nth of the sorted symbol list")
    ap.add_argument("--names", type=int, default=0, help="smoke only (NOT QUOTABLE)")
    ap.add_argument("--min-dvol", type=float, default=0.0)
    ap.add_argument("--chunk", type=int, default=300, help="symbols per events() call (memory)")
    ap.add_argument("--max-zones", type=int, default=MAX_ZONES,
                    help="the SERVED window this READ reproduces "
                         "(price_zones.MAX_ZONES_PER_SIDE); a parameter of the read, never of "
                         "the shipped zone geometry")
    ap.add_argument("--perm-draws", type=int, default=BQ.PERM_DRAWS)
    ap.add_argument("--boot-draws", type=int, default=BQ.BOOT_DRAWS)
    ap.add_argument("--placebo-draws", type=int, default=BQ.PLACEBO_DRAWS)
    ap.add_argument("--seed", type=int, default=SEED_BOOT)
    ap.add_argument("--primary", default="hit5", choices=OUTCOMES)
    ap.add_argument("--out", default="/tmp/deep_events.csv")
    ap.add_argument("--from-csv", default=None)
    ap.add_argument("--cache-csv", default=None,
                    help="the cache-universe events CSV (survivorship); its block is parked at "
                         "<path>" + ETS.SURVIVORSHIP_SUFFIX + " for a later --stage stats to merge")
    ap.add_argument("--survivorship", default=None,
                    help="merge a survivorship block a previous --cache-csv run wrote; with "
                         "neither flag's file present the run is NOT quotable")
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
