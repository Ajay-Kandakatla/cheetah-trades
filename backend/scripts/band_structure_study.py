"""BAND STRUCTURE — the STUDY (least resistance above, most catch below).

THE ASKS (Ajay 2026-09-16, verbatim from the brief)
  #1 "Now in all chartmaps tabs, can you prioritize stock by the thinnest over
     head or Supply zone where ever is applicable"
  #2 "Can you also make sure find stocks with greater support like the support
     bands are bigger and atleast another one very close if its falls below the
     first support level. Something like CRDO had at 149. It has another one
     right below it"

Both are about the STRUCTURE of the bands around the print and both read the
same SERVED band fields, so they are ONE replay with TWO questions:

  Q1  does a THIN first lid predict CLEARING it — a close strictly above
      lid.hi within `hold` sessions — measured INSIDE the 2026-09-07 lid-break
      distance buckets (`lid_break.DIST_BUCKETS`, imported)? That study already
      measured that DISTANCE decides (<=5% 90% / 5-15% 52% / >15% 15%), so a
      thinness claim read outside those buckets is just re-measuring distance.
  Q2  does LAYERED support predict SURVIVING — fewer stop-outs at the band
      floor and HIT5 (+5%) before the floor — i.e. does a second band close
      below actually catch the name? The GAP to that second band is read in
      quantile bins, and the descriptive twin restricts to the episodes that
      actually CLOSED under band1's floor: did the second band hold?

HOUSE RULES this file is written under: NOT ONE threshold is typed here. Every
cut is an imported constant (`alert_gates.ALERT_MIN_ROOM_PCT`,
`alert_gates.STOP_BUFFER_PCT`, `zone_store.MIN_BARS`, `price_zones.LOOKBACK_BARS`,
`price_zones.MAX_ZONES_PER_SIDE`, `lid_break.DIST_BUCKETS`,
`entry_trigger_study.MIN_CELL_N`) or a QUANTILE of the cohort itself. Nothing
here gates an alert, a lane or a push; paper only; read-only container probes.

WHAT IT REUSES (nothing importable is copied)
  * `studies.bounce_quality_study.events()` — the cohort, untouched: a demand
    band reached, `room_gate` >= 5% to the first PROVEN lid, `demand_proximity_gate`
    <= 1% above the band top, the engine's own forward pass (stop before target
    inside a bar).
  * `scripts.explosive_study` (ES) — the tail-bar rule, the universe modes, the
    outcome blocks, the bucket machinery (`assign_buckets` / `orientation` /
    `top_bucket` / `bucket_stats` / `evaluate_bucket` / `run_split`), the
    date-clustered bootstrap, the date-block placebo, the reweight, the dedupe,
    the loader and the §4.1 RULE OF READING text.
  * `scripts.entry_trigger_study` (ETS) — the CONDITIONAL-CONTRAST machinery
    (`cond_boot`, `cond_mdl`, `pooled_delta`, `MIN_CELL_N`), the per-feature
    table, the three OOS splits (`split_masks`) and the survivorship merge.
  * `supply_demand.alert_gates.room_read` / `overhead_bands` — the lid is the
    gate's OWN first overhead band, never a second definition.
  * `supply_demand.price_zones.nearest_first` — the served cut, so the cap is
    reproduced by the engine and not by arithmetic here.

THE CAP, STATED (brief 2026-09-16)
`price_zones.compute` surfaces MAX_ZONES_PER_SIDE = 4 bands per side, cut by
DISTANCE from the print. CRDO's own case shows why this matters: with demand
bands at 182.61-189.12 / 173.90-180.10 / 161.92-167.68 / 146.34-151.55 around a
162.76 print, the bands ABOVE the print consume cap slots, so "another one right
below it" can be INVISIBLE to a served read because of the cap, not because it
is absent. This study therefore draws bands UNCAPPED (`max_zones=None`, the same
call BQ.events makes) and records, per row, whether the second band would have
been inside the served cap (`band2_within_cap`). A gap that exists only OUTSIDE
the cap is NOT ship-eligible from today's served fields — it is reported, and
the report says the cap is the reason. Changing `max_zones` is a parameter of a
READ (`--max-zones`), never a change to the shipped zone geometry (Rule #10).

CONVENTIONS (ES §2.0, unchanged): P = `_pre` structure, entry close[j]; N =
entry open[j+1] (skipped when the open is already at/under the stop). Q1's
outcome `clear_lid_20` is entry-INDEPENDENT (a close above the lid top), so it
is reported once; its before-the-stop twin `clear_lid_bs_20` is printed beside
it and never scored on its own.

UNIT OF ANALYSIS = EPISODES: the first reversal event per symbol then a
`hold`-bar cooldown (`ES.flag_episodes`), so forward windows never overlap
within a name.

SHIP-ELIGIBILITY. A read may ship only when it is computable from the SERVED
band fields at decision time with no lookahead — `ship_eligible_feature()` is
the single place that says so, and `sup_gap_pct` / `depth_*` carry the CAP
caveat above. The Q2 "did the second band hold" table conditions on a FORWARD
event (price closed under band1) and can never ship: it is descriptive.

RUN (read-only; the script is piped to /tmp, never written into /app)
  docker exec -i cheetah-market-app-api-1 sh -c 'cat > /tmp/explosive_study.py' \
      < backend/scripts/explosive_study.py
  docker exec -i cheetah-market-app-api-1 sh -c 'cat > /tmp/entry_trigger_study.py' \
      < backend/scripts/entry_trigger_study.py
  docker exec -i cheetah-market-app-api-1 sh -c 'cat > /tmp/band_structure_study.py' \
      < backend/scripts/band_structure_study.py
  docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app:/tmp python -u \
      /tmp/band_structure_study.py --stage both --universe broad --stride 18 \
      --out /tmp/band_smoke.csv --json /tmp/band_smoke.json'
  docker exec -d -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app:/tmp python -u \
      /tmp/band_structure_study.py --stage replay --universe broad \
      --out /tmp/band_events.csv > /tmp/band_broad.log 2>&1'
  docker exec -d -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app:/tmp python -u \
      /tmp/band_structure_study.py --stage replay --universe cache \
      --out /tmp/band_events_cache.csv > /tmp/band_cache.log 2>&1'
  docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app:/tmp python -u \
      /tmp/band_structure_study.py --stage stats --from-csv /tmp/band_events.csv \
      --cache-csv /tmp/band_events_cache.csv --json /tmp/band_measured.json \
      --emit-measured' | tee report.txt
Never during RTH (the hourly cache patch rewrites frames from ~10:00 ET).

DEVIATIONS (each stated, none silent)
  1. THE SPEC FILE NAMED IN THE WORK ORDER (scratchpad/thin_lid/spec.md) DOES
     NOT EXIST; this module implements the brief's "Part A — the study"
     section, which is the only written statement of the work package.
  2. The brief's o5 conflates two distances. The PRIMARY stratifier is
     `lid_dist_pct` (print -> lid.lo, the read a board has at decision time);
     the 2026-09-07 study's own distance (lid.hi -> the 52-week high,
     `lid_to_52wh_pct`) is printed as a SECOND conditioning of the same
     contrast. Both use `lid_break.DIST_BUCKETS` — neither is a new cut.
  3. Bucket EDGES and the oriented TOP bucket are fixed ONCE on the pooled
     cohort and then applied inside each distance stratum, so the conditional
     contrast cannot fish a different definition per cell.
  4. `depth_*` is a count of demand bands under the print inside a percentage
     that is a QUANTILE of the cohort's own first-gap distribution
     (`DEPTH_QUANTILES`), computed at stats time from the per-row offsets the
     replay stores. No depth percentage is typed.
  5. `pooled_delta` needs a `%d` column template, so the outcome column is
     materialised once per stratum as `ystrat_<i>` on a narrow frame. The
     values are the same column; nothing is recomputed.
  6. Q1's cohort is the reversal-episode cohort (the same one Q2 uses) rather
     than every lid break, so the two questions share one replay as the brief
     asks. It is therefore a read about lids ABOVE A DEMAND-BAND TOUCH, not
     about lid breaks in general; the 2026-09-07 study remains the authority on
     the latter and its buckets are what this conditions on.
  7. Mean R is a tail statistic and is reported, never a gate (ES §4.1).

RESULTS — 2026-09-16 (broad, bar floor 120, clocks [5, 10, 20], hold 20, primary hit5)
  quotable: True
  cohort: 3,716 names · 158,327 events · 93,009 reversal events · 24,994 EPISODES (N-side 22,950) · 362 dates · window 2025-03-10 -> 2026-08-17
  base: n_lid 22,008 · hit5 28.48/32.61/34.20% (5/10/20) · clears the lid 21.17% · stop 74.48% · R 0.29 (median -1.00, trimmed 0.07) · win 24.87% · tgt/stop/clock 19/74/7 · room 15.63% · risk 2.57%
  distance buckets (imported, lid_break.DIST_BUCKETS): ['≤5%', '5–15%', '>15%']
  depth cuts (this cohort's own quantiles, never typed): {'depth_q25': 1.628, 'depth_q50': 4.081, 'depth_q75': 8.228}
  cap: bands drawn UNCAPPED (price_zones.compute(max_zones=None), the call BQ.events makes); the SERVED cut is price_zones.nearest_first(...)[:4] (MAX_ZONES_PER_SIDE) and is recorded per row as band2_within_cap. A second band that exists only OUTSIDE that cap is reported and is NOT ship-eligible from today's served fields.

  Q1 CEILING — does a THIN first lid predict a close above lid.hi within 20 sessions, inside the 2026-09-07 distance buckets?
    STATUS no_signal · selected [] · MDL 2.80 pp · n 24,994
    splits: s1 no_signal (mdl 2.51) · s2 no_signal (mdl 2.49) · s3 no_signal (mdl 2.80)
    per-feature top buckets:
      lid_height_pct   Q1   d_hit5 +6.65pp [+5.40, +7.88] · d_stop +0.62pp · reweighted +7.73pp · ship_eligible True · verdict selects smaller trades · fails room_risk_kept
      lid_strength     Q1   d_hit5 +1.72pp [+0.28, +3.18] · d_stop +1.43pp · reweighted +1.53pp · ship_eligible True · verdict inert (CI>0 but fails: stop_not_raised,outside_date_placebo,one_per_date_symbol) · fails one_per_date_symbol,outside_date_placebo,stop_not_raised
      lid_touches      Q1   d_hit5 +0.63pp [+0.30, +0.97] · d_stop +1.38pp · reweighted +6.63pp · ship_eligible True · verdict inert (CI>0 but fails: stop_not_raised,outside_date_placebo,one_per_date_symbol) · fails one_per_date_symbol,outside_date_placebo,stop_not_raised
      lid_stack        Q5   d_hit5 -0.04pp [-1.69, +1.67] · d_stop +0.54pp · reweighted +0.36pp · ship_eligible True · verdict inert · fails ci_excludes_0,one_per_date_symbol,outside_date_placebo
      lid_dist_pct     Q1   d_hit5 +9.35pp [+7.97, +10.72] · d_stop -6.26pp · reweighted n/a · ship_eligible True · verdict selects smaller trades · fails reweighted_sign,room_risk_kept

  Q2 FLOOR — does LAYERED support predict surviving — fewer floor stop-outs and +5% before the floor?
    STATUS no_signal · selected [] · MDL 2.59 pp · n 24,994
    splits: s1 no_signal (mdl 2.32) · s2 no_signal (mdl 2.47) · s3 no_signal (mdl 2.59)
    per-feature top buckets:
      sup1_height_pct  Q5   d_hit5 -4.01pp [-5.20, -2.86] · d_stop +4.32pp · reweighted -0.42pp · ship_eligible True · verdict harmful · fails ci_excludes_0,one_per_date_symbol,outside_date_placebo,reweighted_sign,stop_not_raised
      sup1_strength    Q1   d_hit5 +0.94pp [-0.45, +2.36] · d_stop -3.80pp · reweighted -1.98pp · ship_eligible True · verdict inert · fails ci_excludes_0,one_per_date_symbol,outside_date_placebo,reweighted_sign,room_risk_kept
      sup1_touches     Q1   d_hit5 +0.69pp [+0.36, +1.02] · d_stop +0.11pp · reweighted -0.21pp · ship_eligible True · verdict selects wider stops · fails one_per_date_symbol,outside_date_placebo,reweighted_sign
      sup1_volume      Q1   d_hit5 -0.55pp [-1.74, +0.64] · d_stop +0.30pp · reweighted -1.56pp · ship_eligible True · verdict inert · fails ci_excludes_0,one_per_date_symbol,outside_date_placebo,reweighted_sign
      sup_gap_pct      Q1   d_hit5 -0.20pp [-1.66, +1.25] · d_stop -3.36pp · reweighted -0.75pp · ship_eligible True · verdict inert · fails ci_excludes_0,one_per_date_symbol,outside_date_placebo,reweighted_sign,room_risk_kept
      sup1_dist_pct    Q5   d_hit5 +9.13pp [+7.74, +10.55] · d_stop -8.86pp · reweighted -1.01pp · ship_eligible True · verdict selects smaller trades · fails reweighted_sign,room_risk_kept
      depth_q25        Q1   d_hit5 n/a n/a · d_stop n/a · reweighted n/a · ship_eligible True · verdict n<120 — not shown
      depth_q50        Q1   d_hit5 n/a n/a · d_stop n/a · reweighted n/a · ship_eligible True · verdict n<120 — not shown
      depth_q75        Q1   d_hit5 +0.37pp [+0.22, +0.52] · d_stop +0.06pp · reweighted +0.83pp · ship_eligible True · verdict selects wider stops · fails outside_date_placebo
    gap quantile bins:
      Q1   n 4,318  hit5 34.00% · stop 71.12% · R 0.30 (median -1.00) · win 27.86%
      Q2   n 4,317  hit5 34.05% · stop 72.37% · R 0.28 (median -1.00) · win 26.96%
      Q3   n 4,318  hit5 33.30% · stop 74.29% · R 0.22 (median -1.00) · win 24.94%
      Q4   n 4,317  hit5 33.77% · stop 74.77% · R 0.32 (median -1.00) · win 24.67%
      Q5   n 4,318  hit5 33.97% · stop 79.71% · R 0.20 (median -1.00) · win 19.89%
      NaN  n 3,406  hit5 36.58% · stop 74.63% · R 0.45 (median -1.00) · win 24.87%
    DESCRIPTIVE TWIN — conditions on a forward event, so it is NOT
    ship-eligible and nothing orders on it:
      n closed UNDER the first band: 18,135
      Q1   n 3,019  held above the next band 34.45%
      Q2   n 3,090  held above the next band 43.11%
      Q3   n 3,195  held above the next band 52.27%
      Q4   n 3,121  held above the next band 65.46%
      Q5   n 3,266  held above the next band 81.14%
      NaN  n 2,444  held above the next band n/a
    cap control: {'n': 21282, 'd_hit5': -0.369499073537638, 'ci': [-0.8286531759839109, 0.07509203529642142], 'd_stop': -0.025285647542350187, 'ci_stop': [-0.42176237730220945, 0.3812725378928224], 'verdict': 'inert'}

  control N-side (open[j+1] entry): sup1_height_pct Q5 -3.38pp, sup1_strength Q1 +0.34pp, sup1_touches Q1 +0.74pp, sup1_volume Q1 +0.35pp, sup_gap_pct Q5 +0.04pp, sup1_dist_pct Q5 +8.02pp, depth_q25 Q1 n/a, depth_q50 Q1 n/a, depth_q75 Q1 +0.31pp
  survivorship: cache 5,284 names / 37,426 episodes · hit5 32.73% vs 34.20% broad = -1.46pp · stop 77.00% · cache-csv:/tmp/band_events_cache.csv
  cohort notes: reversal episodes only (first per symbol + 20-bar cooldown); bands on CLOSED bars strictly before the print with the board geometry; no costs; one regime 2025-03-10 -> 2026-08-17
  STATUS: no_signal · selected [] · fallback descriptive ordering — Part B's call, never a gate
  NOTHING SEPARATES. The board ships the DESCRIPTIVE ordering and a
  banner that says so; no gate, no score, no lane reads this.
"""
from __future__ import annotations

import argparse
import json
import os
import pprint
import time
import types
from typing import Optional

import numpy as np
import pandas as pd

try:                                             # the container runs origin/main
    from scripts import explosive_study as ES    # (all three files are piped to /tmp)
    from scripts import entry_trigger_study as ETS
except ImportError:                              # noqa: F401
    import explosive_study as ES                 # type: ignore
    import entry_trigger_study as ETS            # type: ignore

from studies import bounce_quality_study as BQ
from supply_demand import alert_gates as AG
from supply_demand import demand_reentry as DR
from supply_demand import lid_break as LB
from supply_demand import price_zones as PZ
from sepa import prices

SCRIPT = "backend/scripts/band_structure_study.py"

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
MIN_CELL_N = ETS.MIN_CELL_N                 # 120  — the cell floor the brief asks for
MAX_ZONES = PZ.MAX_ZONES_PER_SIDE           # 4    — the SERVED cap, stated everywhere
DIST_BUCKETS = LB.DIST_BUCKETS              # the 2026-09-07 study's own buckets
LID_MIN_TOUCHES = AG.LID_MIN_TOUCHES        # 2    — what makes a band a lid at all
SUBSAMPLE_NOT_QUOTABLE = ETS.SUBSAMPLE_NOT_QUOTABLE
SURVIVORSHIP_MISSING = ETS.SURVIVORSHIP_MISSING

# The depth read's percentage is a QUANTILE of the cohort's own first-gap
# distribution, never a number chosen here (deviation #4).
DEPTH_QUANTILES = (0.25, 0.50, 0.75)

CAP_NOTE = (
    "bands drawn UNCAPPED (price_zones.compute(max_zones=None), the call BQ.events makes); "
    "the SERVED cut is price_zones.nearest_first(...)[:%d] (MAX_ZONES_PER_SIDE) and is recorded "
    "per row as band2_within_cap. A second band that exists only OUTSIDE that cap is reported "
    "and is NOT ship-eligible from today's served fields." % MAX_ZONES)

FALLBACK = "descriptive ordering — Part B's call, never a gate"

# ── pre-registered feature sets — FROZEN before the first full run ───────────
OVERHEAD_FEATS = ("lid_height_pct", "lid_strength", "lid_touches", "lid_stack",
                  "lid_dist_pct")
SUPPORT_FEATS = ("sup1_height_pct", "sup1_strength", "sup1_touches", "sup1_volume",
                 "sup_gap_pct", "sup1_dist_pct")
STRATIFIERS = ("lid_bucket", "lid52_bucket")
EXPLORATORY = ("lid_to_52wh_pct", "n_below", "has_band2", "band2_within_cap")
assert len(OVERHEAD_FEATS) == 5 and len(SUPPORT_FEATS) == 6

BAND_BOOL_FEATS = {"has_band2", "band2_within_cap", "lid_clear",
                   "under_band1_%d" % HOLD_DEFAULT, "held_band2_%d" % HOLD_DEFAULT}
BAND_STATE_FEATS = {"lid_bucket", "lid52_bucket"}
ES.BOOL_FEATS |= set(BAND_BOOL_FEATS)            # so ES.load_events casts them
ES.STATE_FEATS |= set(BAND_STATE_FEATS)

OUTCOMES = ES.OUTCOMES
CLEAR_LID = "clear_lid"
OFFSET_SEP = ";"


# ═════════════════════════════════════════════════════════════════════════════
# THE PURE READS — no Mongo, no pandas, importable by the shipped reader
# ═════════════════════════════════════════════════════════════════════════════
def full_band(slim: Optional[dict], bands) -> Optional[dict]:
    """`alert_gates.first_overhead` hands back a SLIM band (kind/lo/hi/touches);
    strength and volume live on the band `price_zones.compute` built. Match it
    back by (kind, lo, hi) so `_strength` is never recomputed here."""
    if not isinstance(slim, dict):
        return None
    lo, hi = _f(slim.get("lo")), _f(slim.get("hi"))
    if lo is None or hi is None:
        return None
    kind = str(slim.get("kind") or "").lower()
    for b in bands or []:
        if not isinstance(b, dict):
            continue
        if kind and str(b.get("kind") or "").lower() != kind:
            continue
        if abs(float(b.get("lo", np.nan)) - lo) < 1e-9 and abs(float(b.get("hi", np.nan)) - hi) < 1e-9:
            return b
    return dict(slim)


def overhead_read(px, bands, prev_close=None, hi52=None) -> dict:
    """The CEILING half, entirely from what the alert gate already computed.

    o1 height, o2 strength, o3 touches, o4 stack (how many overhead bands sit
    between the print and the 52-week high), o5 distance. `lid_clear` True = no
    proven band overhead at all (the gate's CLEAR state): every lid read is then
    undefined, NEVER zero."""
    out = {"lid_lo": None, "lid_hi": None, "lid_height_pct": None, "lid_strength": None,
           "lid_touches": None, "lid_stack": None, "lid_dist_pct": None,
           "lid_to_52wh_pct": None, "lid_clear": None, "lid_bucket": None,
           "lid52_bucket": None}
    p = _f(px)
    if p is None or p <= 0:
        return out
    room = AG.room_read(p, bands, prev_close)
    over = AG.overhead_bands(bands, p, prev_close)
    if room is None:
        out["lid_clear"] = True
        out["lid_stack"] = 0
        return out
    out["lid_clear"] = False
    lid = full_band(room.get("band"), bands)
    lo, hi = _f(lid.get("lo")), _f(lid.get("hi"))
    if lo is None or hi is None:
        return out
    h52 = _f(hi52)
    out.update({
        "lid_lo": lo, "lid_hi": hi,
        "lid_height_pct": (hi - lo) / p * 100.0,
        "lid_strength": _f(lid.get("strength")),
        "lid_touches": _f(lid.get("touches")),
        "lid_dist_pct": (lo - p) / p * 100.0,
        # the wall between the print and the old high; with no 52w high in the
        # frame every proven band overhead counts
        "lid_stack": int(len([b for b in over
                              if h52 is None or _f(b.get("lo")) is None or float(b["lo"]) <= h52])),
    })
    if h52 is not None and hi > 0:
        out["lid_to_52wh_pct"] = (h52 - hi) / hi * 100.0
    out["lid_bucket"] = LB.dist_bucket(out["lid_dist_pct"])
    out["lid52_bucket"] = LB.dist_bucket(out["lid_to_52wh_pct"])
    return out


def support_read(px, band1: Optional[dict], demand_all, max_zones: int = MAX_ZONES) -> dict:
    """The FLOOR half. `band1` is the event band — the nearest support UNDER the
    print, the one the stop is placed below (BQ.events' own pick). `band2` is
    the highest demand band strictly under band1's floor.

    `sup_gap_pct` is UNDEFINED (None) when there is no second band — never 0.0,
    which would read as "another band right there". `band2_within_cap` says
    whether a SERVED read (the nearest `max_zones` bands by distance) would have
    seen band2 at all."""
    out = {"sup1_lo": None, "sup1_hi": None, "sup1_height_pct": None, "sup1_strength": None,
           "sup1_touches": None, "sup1_volume": None, "sup1_dist_pct": None,
           "band2_lo": None, "band2_hi": None, "sup_gap_pct": None,
           "has_band2": None, "band2_within_cap": None, "n_below": None,
           "below_offsets": None}
    p = _f(px)
    if p is None or p <= 0 or not isinstance(band1, dict):
        return out
    lo1, hi1 = _f(band1.get("lo")), _f(band1.get("hi"))
    if lo1 is None or hi1 is None:
        return out
    out.update({"sup1_lo": lo1, "sup1_hi": hi1,
                "sup1_height_pct": (hi1 - lo1) / p * 100.0,
                "sup1_strength": _f(band1.get("strength")),
                "sup1_touches": _f(band1.get("touches")),
                "sup1_volume": _f(band1.get("volume")),
                "sup1_dist_pct": (p - hi1) / p * 100.0})
    below = [b for b in (demand_all or [])
             if isinstance(b, dict) and _f(b.get("hi")) is not None and float(b["hi"]) < lo1]
    below.sort(key=lambda b: -float(b["hi"]))
    out["n_below"] = len(below)
    out["has_band2"] = bool(below)
    out["below_offsets"] = OFFSET_SEP.join("%.4f" % ((p - float(b["hi"])) / p * 100.0)
                                           for b in below)
    if not below:
        return out
    b2 = below[0]
    out["band2_lo"], out["band2_hi"] = _f(b2.get("lo")), _f(b2.get("hi"))
    out["sup_gap_pct"] = (lo1 - float(b2["hi"])) / p * 100.0
    served = PZ.nearest_first(list(demand_all or []), p)[:max(0, int(max_zones))]
    out["band2_within_cap"] = any(
        abs(float(z.get("lo", np.nan)) - float(b2["lo"])) < 1e-9
        and abs(float(z.get("hi", np.nan)) - float(b2["hi"])) < 1e-9 for z in served)
    return out


def clear_lid_outcome(fc, fl, lid_hi, stop, hold: int) -> dict:
    """Q1's outcome. `clear_lid_<hold>` = a forward CLOSE strictly above the lid
    top within `hold` bars; `clear_lid_bs_<hold>` = the same, before the floor
    stop was hit. Both NaN when there is no lid (the gate read CLEAR) — an
    unclearable ceiling is not a failure to clear."""
    key, keyb, keyk = ("%s_%d" % (CLEAR_LID, hold), "%s_bs_%d" % (CLEAR_LID, hold),
                       "k_%s" % CLEAR_LID)
    top = _f(lid_hi)
    if top is None:
        return {key: np.nan, keyb: np.nan, keyk: np.nan}
    fc = np.asarray(fc, dtype=float)[:hold]
    fl = np.asarray(fl, dtype=float)[:hold]
    k = ES._first_k(fc > float(top))
    ks = ES._first_k(fl <= float(stop))
    hit = k is not None and k <= hold
    return {key: float(hit), keyb: float(hit and (ks is None or k < ks)),
            keyk: float(k) if k is not None else np.nan}


def under_band1_outcome(fc, band1_lo, band2_lo, hold: int) -> dict:
    """Q2's descriptive twin: the first forward CLOSE under band1's floor, and —
    from that bar on — whether every remaining close inside the window held at or
    above band2's floor. Both NaN when the floor was never lost (or when there is
    no second band): "did the second band hold" has no answer where the first one
    was never given up. CONDITIONS ON A FORWARD EVENT — never ship-eligible."""
    out = {"under_band1_%d" % hold: np.nan, "k_under_band1": np.nan,
           "held_band2_%d" % hold: np.nan}
    lo1, lo2 = _f(band1_lo), _f(band2_lo)
    if lo1 is None:
        return out
    fc = np.asarray(fc, dtype=float)[:hold]
    k = ES._first_k(fc < float(lo1))
    out["under_band1_%d" % hold] = float(k is not None)
    if k is None:
        return out
    out["k_under_band1"] = float(k)
    if lo2 is None:
        return out
    rest = fc[k - 1:]
    out["held_band2_%d" % hold] = float(bool(np.all(rest[np.isfinite(rest)] >= float(lo2))))
    return out


def parse_offsets(s) -> list:
    """The `below_offsets` cell back into floats. A blank / missing cell is an
    empty list (no band below), which is NOT the same as a zero offset."""
    if s is None or (isinstance(s, float) and s != s):
        return []
    txt = str(s).strip()
    if not txt or txt.lower() in ("nan", "none"):
        return []
    out = []
    for part in txt.split(OFFSET_SEP):
        v = _f(part)
        if v is not None:
            out.append(float(v))
    return out


def depth_within(offsets, pct) -> Optional[int]:
    """How many demand bands sit within `pct`% under the print. None when the
    percentage itself is undefined (an empty cohort has no quantile)."""
    p = _f(pct)
    if p is None:
        return None
    return int(sum(1 for v in offsets if v <= p))


def ship_eligible_feature(feat: str) -> tuple:
    """(ok, reason). Ship-eligible = computable from the SERVED band fields at
    decision time with no lookahead. The gap and depth reads carry the CAP
    caveat: they are only served when the second band is inside
    MAX_ZONES_PER_SIDE (`band2_within_cap`)."""
    if feat in ("sup_gap_pct",) or feat.startswith("depth_"):
        return True, ("served only when band2_within_cap — %s" % CAP_NOTE)
    if feat in OVERHEAD_FEATS or feat in SUPPORT_FEATS:
        return True, "served band field at the print"
    if feat.startswith("held_band2") or feat.startswith("under_band1") or feat.startswith("k_"):
        return False, "conditions on a forward event — descriptive only"
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
        dz = (z or {}).get("demand_zones") or []
        bands_all = ((z or {}).get("supply_zones") or []) + dz
        ea = ETS.event_at(o, h, l, c, j, bands_all)
        band1 = ea["band"] if ea else None
        if band1 is None:
            counters["no_band"] += 1
        elif abs(float(band1["lo"]) * buf - stop) > 1e-6:
            counters["band_mismatch"] += 1
        hi52 = float(np.nanmax(h[j - BOX_BARS:j])) if j >= BOX_BARS else None
        row.update(overhead_read(px, bands_all, prev, hi52))
        row.update(support_read(px, band1, dz, max_zones))
        row["hi52"] = hi52 if hi52 is not None else np.nan
        row["dvol50_pre"] = float(dvol[j - 1]) if np.isfinite(dvol[j - 1]) else np.nan
        band_hi = float(band1["hi"]) if band1 else None
        # ── outcomes: the engine's two conventions plus this study's two ──
        fh = h[j + 1:j + 1 + max_clock]
        fl = l[j + 1:j + 1 + max_clock]
        fc = c[j + 1:j + 1 + max_clock]
        blk = ES.outcome_block(fh, fl, fc, px, stop, target, band_hi, clocks, hold)
        for cl in sorted(set(clocks) | {hold}):
            blk.pop("R%d" % cl)                  # the engine's R{cl}/why{cl} stay authoritative
            blk.pop("why%d" % cl)
        row.update(blk)
        row.update(ES.next_open_block(o[j + 1], fh, fl, fc, stop, target, band_hi, clocks, hold))
        row.update(clear_lid_outcome(fc, fl, row.get("lid_hi"), stop, hold))
        row.update(under_band1_outcome(fc, row.get("sup1_lo"), row.get("band2_lo"), hold))
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
      "max_zones(read)=%d  today=%s"
      % (a.universe, len(syms), floor, hold, clocks, a.stride, a.min_dvol, a.max_zones,
         _today_et()))
    P("CAP: %s" % CAP_NOTE)
    counters = {"no_bar": 0, "no_band": 0, "band_mismatch": 0, "no_frame": 0}
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
            "max_zones_read": a.max_zones, "cap_note": CAP_NOTE}
    with open(a.out + ".meta.json", "w") as fh:
        json.dump(meta, fh)
    P("replay done  rows=%d  frames=%d  counters=%s  %.0fs"
      % (n_rows, ES.TAIL["names"], counters, time.time() - t0))


# ═════════════════════════════════════════════════════════════════════════════
# THE CONDITIONAL CONTRAST — ETS's pooled machinery, cells = distance buckets
# ═════════════════════════════════════════════════════════════════════════════
def strat_order(D: pd.DataFrame, col: str) -> list:
    """The stratum labels IN THE 2026-09-07 STUDY'S OWN ORDER, restricted to the
    ones the cohort actually has."""
    have = set(str(x) for x in D[col].dropna().unique()) if col in D else set()
    return [name for _, name in DIST_BUCKETS if name in have]


def strat_cells(D: pd.DataFrame, strat_col: str, mask: pd.Series, order: list) -> dict:
    """base_k = every row in stratum k; kept_k = the feature's oriented TOP
    bucket INSIDE that stratum (the labels come from the pooled cohort —
    deviation #3). Cells under MIN_CELL_N on either side are dropped and named."""
    cells, keep_n, dropped, labels = {}, {}, [], {}
    lab = D[strat_col].astype(object) if strat_col in D else pd.Series(np.nan, index=D.index)
    for i, name in enumerate(order):
        base = lab.astype(str) == name
        kept = base & mask.reindex(D.index).fillna(False).astype(bool)
        cells[i] = (base, kept)
        keep_n[i] = int(kept.sum())
        labels[i] = name
    ks = []
    for i in cells:
        base, kept = cells[i]
        if int(kept.sum()) < MIN_CELL_N or int((base & ~kept).sum()) < MIN_CELL_N:
            if int(kept.sum()):
                dropped.append(labels[i])
            continue
        ks.append(i)
    tot = float(sum(keep_n[i] for i in ks))
    weights = {i: keep_n[i] / tot for i in ks} if tot else {}
    return {"cells": cells, "ks": ks, "weights": weights, "keep_n": keep_n,
            "labels": labels, "dropped": sorted(dropped),
            "n_base": {labels[i]: int(cells[i][0].sum()) for i in cells}}


def _strat_frame(D: pd.DataFrame, cl: dict, col: str, stem: str) -> pd.DataFrame:
    """One narrow frame carrying the outcome once per stratum under a `%d`-able
    name, so ETS.pooled_delta / ETS.cond_boot read it unchanged (deviation #5)."""
    y = pd.to_numeric(D[col], errors="coerce").to_numpy(dtype=float) if col in D else \
        np.full(len(D), np.nan)
    cols = {"date": D["date"].to_numpy(), "symbol": D["symbol"].to_numpy()}
    for i in cl["ks"]:
        cols["%s_%d" % (stem, i)] = y
    return pd.DataFrame(cols, index=D.index)


def conditional_contrast(D: pd.DataFrame, mask: pd.Series, strat_col: str, conv: dict,
                         a, order: list) -> dict:
    """The pooled within-stratum delta of the top bucket, its date-clustered CI,
    the study's resolution (MDL) under a random relabel, the stop twin and the
    one-per-date / one-per-symbol point estimates. Cells = the 2026-09-07
    distance buckets, so a "thin lid" claim is never a distance claim."""
    cl = strat_cells(D, strat_col, mask, order)
    out = {"stratifier": strat_col, "cells": cl["labels"], "n_base": cl["n_base"],
           "keep_n": {cl["labels"][i]: cl["keep_n"][i] for i in cl["keep_n"]},
           "pooled": [cl["labels"][i] for i in cl["ks"]], "dropped": cl["dropped"],
           "weights": {cl["labels"][i]: cl["weights"][i] for i in cl["ks"]}}
    if not cl["ks"]:
        out.update({"d_cond": None, "ci_cond": [None, None], "mdl_cond": None,
                    "d_stop_cond": None, "ci_stop_cond": [None, None],
                    "one_per_date": None, "one_per_symbol": None,
                    "contrast": "no stratum reached %d rows on both sides — undefined" % MIN_CELL_N,
                    "verdict": "n<%d — not shown" % MIN_CELL_N})
        return out
    hit_stem, stop_stem = "yhit", "ystop"
    Fh = _strat_frame(D, cl, conv["hit"], hit_stem)
    Fs = _strat_frame(D, cl, conv["stop"], stop_stem)
    ycols = {i: "%s_%d" % (hit_stem, i) for i in cl["ks"]}
    scols = {i: "%s_%d" % (stop_stem, i) for i in cl["ks"]}
    base_m = {i: cl["cells"][i][0] for i in cl["ks"]}
    kept_m = {i: cl["cells"][i][1] for i in cl["ks"]}
    d = ETS.pooled_delta(Fh, cl, hit_stem + "_%d")
    boot = ETS.cond_boot(Fh, ycols, base_m, kept_m, cl["weights"], a.boot_draws)
    ci = ([float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]
          if boot.size >= 100 else [None, None])
    mdl = ETS.cond_mdl(Fh, ycols, base_m, cl["keep_n"], cl["weights"], a.placebo_draws)
    ds = ETS.pooled_delta(Fs, cl, stop_stem + "_%d")
    boot_s = ETS.cond_boot(Fs, scols, base_m, kept_m, cl["weights"], a.boot_draws)
    ci_s = ([float(np.percentile(boot_s, 2.5)), float(np.percentile(boot_s, 97.5))]
            if boot_s.size >= 100 else [None, None])
    d1 = s1 = 0.0
    for i in cl["ks"]:
        base, kept = cl["cells"][i]
        col = ycols[i]
        a1, b1 = ES.dedupe_deltas(ETS._ydf(Fh[["date", "symbol"]][base], Fh.loc[base, col], True),
                                  ETS._ydf(Fh[["date", "symbol"]][kept], Fh.loc[kept, col], True), "y")
        d1 += cl["weights"][i] * a1
        s1 += cl["weights"][i] * b1
    out.update({"d_cond": 100.0 * d,
                "ci_cond": [100.0 * ci[0], 100.0 * ci[1]] if ci[0] is not None else [None, None],
                "mdl_cond": 100.0 * mdl if mdl == mdl else None,
                "d_stop_cond": 100.0 * ds,
                "ci_stop_cond": ([100.0 * ci_s[0], 100.0 * ci_s[1]]
                                 if ci_s[0] is not None else [None, None]),
                "one_per_date": 100.0 * d1, "one_per_symbol": 100.0 * s1,
                "contrast": "top bucket vs the rest of its own distance stratum"})
    out["verdict"] = cond_verdict(out)
    return out


def cond_verdict(r: dict) -> str:
    """Inside a stratum the rule of reading keeps the parts that still apply:
    the CI must exclude 0, the delta must beat the study's own resolution, the
    stop CI must not lie entirely above 0, and both dedupe point estimates must
    keep the sign. Anything else is inert."""
    d, ci, mdl = r.get("d_cond"), r.get("ci_cond") or [None, None], r.get("mdl_cond")
    cis = r.get("ci_stop_cond") or [None, None]
    if d is None or ci[0] is None:
        return "n<%d — not shown" % MIN_CELL_N
    if not (ci[0] > 0):
        return "harmful" if (ci[1] is not None and ci[1] < 0) else "inert"
    if mdl is None or d < mdl:
        return "inert (under the study's resolution)"
    if cis[0] is not None and cis[0] > 0:
        return "inert (raises stop-outs)"
    if not ((r.get("one_per_date") or 0.0) > 0 and (r.get("one_per_symbol") or 0.0) > 0):
        return "inert (one-per-date/symbol loses the sign)"
    return "separates"


def fmt_cond(feat: str, r: dict) -> str:
    return ("    %-18s [%s] pooled %-24s Δhit %s CI %s MDL %s | Δstop %s %s | "
            "1/date %s 1/sym %s\n      -> %s"
            % (feat, r.get("stratifier"), ",".join(r.get("pooled") or []) or "none",
               _pp(r.get("d_cond")), _ci(r.get("ci_cond")), _pp(r.get("mdl_cond")),
               _pp(r.get("d_stop_cond")), _ci(r.get("ci_stop_cond")),
               _pp(r.get("one_per_date")), _pp(r.get("one_per_symbol")), r.get("verdict")))


# ═════════════════════════════════════════════════════════════════════════════
# STAGE: stats
# ═════════════════════════════════════════════════════════════════════════════
def conventions(primary: str, hold: int) -> dict:
    """ES's P and N with this study's feature sets, plus CLEAR — the same P
    columns with Q1's clears-the-lid outcome as the scored one."""
    base = ES.conventions(primary, hold)
    base["P"]["feats"] = SUPPORT_FEATS
    base["N"]["feats"] = SUPPORT_FEATS
    clear = dict(base["P"])
    clear.update({"tag": "CLEAR",
                  "label": "CLEAR (print read, outcome = a close above the lid top within %d)" % hold,
                  "hit": "%s_%d" % (CLEAR_LID, hold), "feats": OVERHEAD_FEATS})
    base["CLEAR"] = clear
    return base


def wanted_columns(clocks, hold: int, primary: str) -> list:
    cols = ["symbol", "date", "dir", "entry", "stop", "target", "room_pct", "clear",
            "risk_pct", "R", "why", "episode", "episode_dir", "bar_idx", "hi52",
            "band_lo", "band_hi", "dvol50_pre", "gap_N", "risk_pct_N", "entry_N",
            "sup1_lo", "sup1_hi", "band2_lo", "band2_hi", "lid_lo", "lid_hi",
            "below_offsets"]
    for cl in sorted(set(clocks) | {hold}):
        cols += ["R%d" % cl, "why%d" % cl, "pct%d" % cl, "hit5_%d" % cl, "hit5b_%d" % cl,
                 "hit_lid_%d" % cl, "stop_%d" % cl, "hit5_%d_N" % cl, "hit_lid_%d_N" % cl,
                 "stop_%d_N" % cl, "R%d_N" % cl, "why%d_N" % cl]
    cols += ["hit5c_%d" % hold, "hit5c_%d_N" % hold, "max_gain_pct_%d" % hold,
             "%s_%d" % (CLEAR_LID, hold), "%s_bs_%d" % (CLEAR_LID, hold), "k_%s" % CLEAR_LID,
             "under_band1_%d" % hold, "k_under_band1", "held_band2_%d" % hold]
    cols += list(dict.fromkeys(OVERHEAD_FEATS + SUPPORT_FEATS + STRATIFIERS + EXPLORATORY))
    return list(dict.fromkeys(cols))


def load_events(path: str, clocks, hold: int, primary: str) -> pd.DataFrame:
    return ES.load_events(path, columns=wanted_columns(clocks, hold, primary))


def add_depth_columns(D: pd.DataFrame) -> dict:
    """`depth_q25 / q50 / q75` — how many demand bands sit within a percentage
    that is a QUANTILE of the cohort's own first-gap distribution. The
    percentages are measured here and printed; none is typed (deviation #4)."""
    offs = D["below_offsets"].map(parse_offsets) if "below_offsets" in D else \
        pd.Series([[]] * len(D), index=D.index)
    gap = pd.to_numeric(D["sup_gap_pct"], errors="coerce") if "sup_gap_pct" in D else \
        pd.Series(np.nan, index=D.index)
    first = pd.to_numeric(D["sup1_dist_pct"], errors="coerce") if "sup1_dist_pct" in D else \
        pd.Series(np.nan, index=D.index)
    span = (first + gap).dropna()               # print -> the second band's top
    cuts = {}
    for q in DEPTH_QUANTILES:
        name = "depth_q%d" % int(round(q * 100))
        pct = float(np.quantile(span.to_numpy(dtype=float), q)) if len(span) else None
        cuts[name] = pct
        D[name] = offs.map(lambda xs, p=pct: depth_within(xs, p)).astype(float) \
            if pct is not None else np.nan
    return cuts


def gap_bins(D: pd.DataFrame, conv: dict, clocks, hold: int) -> list:
    """The GAP read in QUANTILE bins (ES.assign_buckets' own quintiles), with
    the absent-second-band rows in their OWN bucket — never merged into a bin
    and never read as a zero gap."""
    lab, order, edges = ES.assign_buckets(D["sup_gap_pct"], "num")
    out = []
    for name in order:
        m = lab == name
        if not int(m.sum()):
            continue
        s = ES.bucket_stats(D, D[m], conv, clocks, hold)
        out.append({"bin": name, "n": int(m.sum()),
                    "hit5_20": s["hit5_%d" % hold], "stop_20": s["stop_20"],
                    "R20": s["R20"], "R20_median": s["R20_median"], "win20": s["win20"],
                    "note": ("no second band — gap UNDEFINED, not 0" if name == "NaN" else None)})
        P("    gap %-4s n=%-6d %s" % (name, int(m.sum()), ES.fmt_row(name, s).strip()))
    return out


def held_table(D: pd.DataFrame, hold: int) -> dict:
    """DESCRIPTIVE ONLY (conditions on a forward event): among the episodes that
    actually CLOSED under band1's floor, did the second band hold? Reported by
    gap quintile, with the no-second-band rows kept separate."""
    ucol, hcol = "under_band1_%d" % hold, "held_band2_%d" % hold
    if ucol not in D or hcol not in D:
        return {"n": 0, "note": "columns absent"}
    under = pd.to_numeric(D[ucol], errors="coerce") == 1.0
    lab, order, _ = ES.assign_buckets(D["sup_gap_pct"], "num")
    rows = []
    for name in order:
        m = under & (lab == name)
        n = int(m.sum())
        if not n:
            continue
        held = pd.to_numeric(D.loc[m, hcol], errors="coerce")
        rows.append({"bin": name, "n": n, "n_answerable": int(held.notna().sum()),
                     "held_pct": 100.0 * _nanmean(held) if held.notna().any() else None,
                     "note": ("no second band — 'held' is UNDEFINED, never False"
                              if name == "NaN" else None)})
        P("    under band1, gap %-4s n=%-6d answerable %-6d held %s"
          % (name, n, rows[-1]["n_answerable"], _pp(rows[-1]["held_pct"])))
    return {"n_under": int(under.sum()), "by_gap_bin": rows,
            "ship_eligible": False,
            "note": "conditions on a forward event (price closed under band1) — descriptive only"}


def question_block(D: pd.DataFrame, conv: dict, a, clocks, hold: int, label: str,
                   feats, strats) -> dict:
    """One question end to end: the per-feature table, the conditional contrast
    inside each stratifier's buckets, and the three OOS splits."""
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
            order_s = strat_order(D, sc)
            if not order_s:
                cond[feat][sc] = {"stratifier": sc, "verdict": "stratifier absent"}
                continue
            r = conditional_contrast(D, mask, sc, conv, a, order_s)
            r["top"] = top
            cond[feat][sc] = r
            P(fmt_cond(feat, r))
    splits = {}
    for name, m in ETS.split_masks(D):
        key = name.split()[0]
        splits[key] = ES.run_split(D, m, ~m, conv, a, name, clocks, hold)
    return {"convention": conv["tag"], "n": int(len(D)), "per_feature": per_feature,
            "conditional": cond, "splits": splits}


def block_status(block: dict) -> tuple:
    """A question SEPARATES only when a ship-eligible feature's top bucket
    separates on ALL THREE OOS splits AND the pooled conditional contrast inside
    the distance buckets separates too. Otherwise no_signal + the MDL."""
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
        if not conds or not all((c or {}).get("verdict") == "separates" for c in conds.values()):
            continue
        selected.append(p["name"])
    status = "separates" if (selected and all_split) else "no_signal"
    return status, selected, mdl


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
    convP, convN, convC = convs["P"], convs["N"], convs["CLEAR"]
    B_all = X[X["dir"] == DIRECTION_BASE].reset_index(drop=True)
    B = B_all[B_all["episode_dir"] == True].reset_index(drop=True)           # noqa: E712
    dates = sorted(X["date"].unique())
    window = "%s -> %s" % (dates[0], dates[-1]) if dates else "n/a"

    P("=" * 118)
    P("BAND STRUCTURE — STUDY  (%s)   script %s" % (_today_et(), SCRIPT))
    P("COHORT  demand band reached, room >= %g%% to the first proven lid, print <= %g%% above the "
      "band top; floor=%s bars, clocks=%s, hold=%d; stop = band floor -%g%%; universe=%s"
      % (FIVE_PCT, AG.ALERT_MAX_ABOVE_DEMAND_PCT, meta.get("floor", a.floor), clocks, hold,
         STOP_BUFFER_PCT, meta.get("universe_mode", "?")))
    P("        all events n=%d   reversal events n=%d   reversal EPISODES n=%d   dates=%d   window %s"
      % (len(X), len(B_all), len(B), len(dates), window))
    P("CAP: %s" % CAP_NOTE)
    P("")
    P(ES.RULE_TEXT)
    P("CONDITIONING: every thinness claim is read INSIDE the 2026-09-07 lid-break distance "
      "buckets %s (lid_break.DIST_BUCKETS, imported) — a read outside them would only be "
      "re-measuring distance." % (tuple(n for _, n in DIST_BUCKETS),))

    depth_cuts = add_depth_columns(B)
    P("")
    P("DEPTH CUTS (quantiles of this cohort's own print->second-band span, never typed): %s"
      % {k: (None if v is None else round(v, 3)) for k, v in depth_cuts.items()})

    base_P = ES.bucket_stats(B, B, convP, clocks, hold)
    P("")
    P(ES.fmt_row("base P", base_P))
    for name, col in (("clears the lid", "%s_%d" % (CLEAR_LID, hold)),
                      ("clears before the stop", "%s_bs_%d" % (CLEAR_LID, hold))):
        v = pd.to_numeric(B[col], errors="coerce") if col in B else pd.Series(dtype=float)
        P("    %-24s %5.1f %%  (n with a lid = %d; CLEAR rows are UNDEFINED, not failures)"
          % (name, 100.0 * _nanmean(v) if len(v) else float("nan"), int(v.notna().sum())))

    q1 = question_block(B, convC, a, clocks, hold, "Q1 — a THIN first lid vs CLEARING it",
                        list(OVERHEAD_FEATS), list(STRATIFIERS))
    q1_status, q1_sel, q1_mdl = block_status(q1)

    sup_feats = list(SUPPORT_FEATS) + sorted(depth_cuts)
    q2 = question_block(B, convP, a, clocks, hold, "Q2 — LAYERED support vs SURVIVING",
                        sup_feats, list(STRATIFIERS))
    q2_status, q2_sel, q2_mdl = block_status(q2)
    P("")
    P("  GAP in quantile bins (absent second band = its own bucket):")
    q2["gap_bins"] = gap_bins(B, convP, clocks, hold)
    P("  Did the second band hold? (DESCRIPTIVE — conditions on a forward event)")
    q2["held"] = held_table(B, hold)
    P("  CAP control — the same GAP read restricted to rows a SERVED read could see:")
    cap_mask = B["band2_within_cap"] == True                                 # noqa: E712
    q2["capped_only"] = {"n": int(cap_mask.sum()),
                         "n_uncapped_only": int(((B["has_band2"] == True) & ~cap_mask).sum()),
                         "note": CAP_NOTE}
    if int(cap_mask.sum()) >= MIN_CELL_N and int((~cap_mask).sum()) >= MIN_CELL_N:
        r = ES.evaluate_bucket(B, cap_mask, convP, a, base_P)
        q2["capped_only"]["eval"] = {k: r.get(k) for k in ("n", "d_hit5", "ci", "d_stop",
                                                           "ci_stop", "verdict")}
        P(ES.fmt_eval(r))
    else:
        P("    -> n<%d on one side — not shown" % MIN_CELL_N)

    P("")
    P("CONTROL — the same support table under convention N (entry open[j+1]):")
    BN = B[B["gap_N"] == False].reset_index(drop=True)                        # noqa: E712
    per_N: list = []
    if len(BN) >= MIN_CELL_N:
        ETS.feature_table(BN, convN, a, clocks, hold, sup_feats, per_N, "Q2 control (N)")
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
        "max_zones_read": meta.get("max_zones_read", a.max_zones), "cap_note": CAP_NOTE,
        "dist_buckets": [n for _, n in DIST_BUCKETS], "depth_cuts": depth_cuts,
        "base": {k: base_P[k] for k in ("hit5_5", "hit5_10", "hit5_20", "hit5b_20",
                                        "hit_lid_20", "n_lid", "stop_20", "R20", "R20_median",
                                        "R20_trim", "win20", "tgt_stop_clk", "room_pct",
                                        "risk_pct", "clear_pct")},
        "q1": dict(q1, status=q1_status, selected=q1_sel, mdl=q1_mdl,
                   question=("does a THIN first lid predict a close above lid.hi within %d "
                             "sessions, inside the 2026-09-07 distance buckets?" % hold)),
        "q2": dict(q2, status=q2_status, selected=q2_sel, mdl=q2_mdl,
                   question=("does LAYERED support predict surviving — fewer floor stop-outs "
                             "and +%g%% before the floor?" % FIVE_PCT)),
        "control_N": per_N, "survivorship": surv, "status": status, "fallback": FALLBACK,
        "cohort_note": ("reversal episodes only (first per symbol + %d-bar cooldown); bands on "
                        "CLOSED bars strictly before the print with the board geometry; no costs; "
                        "one regime %s" % (hold, window)),
        "walltime_stats_s": round(time.time() - t0, 1),
    }
    measured = ES._clean(measured)
    P("")
    P("=" * 118)
    P("VERDICT  Q1 %s (selected %s, MDL %s pp)   Q2 %s (selected %s, MDL %s pp)   fallback: %s%s"
      % (q1_status, q1_sel or "NONE", _pp(q1_mdl), q2_status, q2_sel or "NONE", _pp(q2_mdl),
         FALLBACK, "   " + banner if banner else ""))
    P("=" * 118)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(measured, fh, indent=1)
        P("wrote %s" % a.json)
    if a.emit_measured:
        P("")
        P("# ---- MEASURED literal (paste verbatim into the served read) ----")
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
                    help="the SERVED cap this READ reproduces (price_zones.MAX_ZONES_PER_SIDE); "
                         "a parameter of the read, never of the shipped zone geometry")
    ap.add_argument("--perm-draws", type=int, default=BQ.PERM_DRAWS)
    ap.add_argument("--boot-draws", type=int, default=BQ.BOOT_DRAWS)
    ap.add_argument("--placebo-draws", type=int, default=BQ.PLACEBO_DRAWS)
    ap.add_argument("--seed", type=int, default=SEED_BOOT)
    ap.add_argument("--primary", default="hit5", choices=OUTCOMES)
    ap.add_argument("--out", default="/tmp/band_events.csv")
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
