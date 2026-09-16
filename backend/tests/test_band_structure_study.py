"""Study-side tests for scripts/band_structure_study.py (the 2026-09-16 band
structure brief, Part A).

Everything runs WITHOUT Mongo on synthetic frames: the script must import with
no database, every pure read must be pinned against the engine function it
reuses, and the negatives are mandatory — above all the one the brief calls out
by name, a SECOND BAND THAT IS CAPPED AWAY versus one that is genuinely ABSENT.
Those two must never look alike, and neither may ever read as a zero gap.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from scripts import band_structure_study as BS
from scripts import entry_trigger_study as ETS
from scripts import explosive_study as ES
from supply_demand import alert_gates as AG
from supply_demand import lid_break as LB
from supply_demand import price_zones as PZ

CLOCKS = (5, 10, 20)
HOLD = 20


class _A:
    """The argparse namespace the stats helpers read."""
    boot_draws = 200
    perm_draws = 100
    placebo_draws = 120


def _band(lo, hi, kind="demand", touches=2, volume=1_000_000, strength=50.0) -> dict:
    return {"kind": kind, "lo": float(lo), "hi": float(hi), "mid": (lo + hi) / 2.0,
            "touches": int(touches), "volume": int(volume), "strength": float(strength),
            "bars_since_test": 5, "oldest_touch_bars": 60, "touch_dates": None}


# ═════════════════════════════════════════════════════════════════════════════
# 1 — every threshold is IMPORTED and the pre-registered sets are frozen
# ═════════════════════════════════════════════════════════════════════════════
def test_constants_are_imported_and_nothing_is_typed():
    assert BS.FIVE_PCT is AG.ALERT_MIN_ROOM_PCT
    assert BS.STOP_BUFFER_PCT is AG.STOP_BUFFER_PCT
    assert BS.MIN_CELL_N is ETS.MIN_CELL_N and BS.MIN_CELL_N == 120
    assert BS.MAX_ZONES is PZ.MAX_ZONES_PER_SIDE
    assert BS.DIST_BUCKETS is LB.DIST_BUCKETS
    assert BS.LID_MIN_TOUCHES is AG.LID_MIN_TOUCHES
    assert BS.BOX_BARS == PZ.LOOKBACK_BARS
    assert len(BS.OVERHEAD_FEATS) == 5 and len(BS.SUPPORT_FEATS) == 6
    assert len(set(BS.OVERHEAD_FEATS)) == 5 and len(set(BS.SUPPORT_FEATS)) == 6
    assert BS.SCRIPT == "backend/scripts/band_structure_study.py"


def test_the_module_reuses_the_engines_and_re_implements_none_of_them():
    src = open(BS.__file__).read()
    # the lid is the gate's own first overhead band, the cap is the engine's cut
    assert "AG.room_read(" in src and "AG.overhead_bands(" in src
    assert "PZ.nearest_first(" in src
    # the harness comes in by import, never by transcription
    for name in ("ETS.cond_boot(", "ETS.cond_mdl(", "ETS.pooled_delta(", "ETS.split_masks(",
                 "ETS.feature_table(", "ES.run_split(", "ES.evaluate_bucket(",
                 "ES.bucket_stats(", "ES.assign_buckets(", "ETS.survivorship_read("):
        assert name in src, name
    # no parallel definition of the touch or of the outcome walk
    assert "def cond_boot" not in src and "def evaluate_bucket" not in src
    assert "def event_at" not in src and "def outcome_block" not in src


def test_docstring_results_block_is_pending_or_equals_the_json():
    doc = BS.__doc__
    assert "RESULTS" in doc
    tail = doc[doc.index("RESULTS"):]
    assert tail.startswith("RESULTS — pending") or "cohort:" in tail
    assert "DEVIATIONS" in doc and "THE CAP, STATED" in doc


# ═════════════════════════════════════════════════════════════════════════════
# 2 — the CEILING read is the alert gate's own first overhead band
# ═════════════════════════════════════════════════════════════════════════════
def test_overhead_read_is_the_gates_first_overhead_band_with_its_own_strength():
    px = 100.0
    lid = _band(105.0, 108.0, "supply", touches=3, strength=71.0)
    bands = [lid, _band(120.0, 124.0, "supply", touches=2), _band(95.0, 98.0, "demand")]
    r = BS.overhead_read(px, bands, prev_close=99.0, hi52=130.0)
    assert r["lid_clear"] is False
    assert (r["lid_lo"], r["lid_hi"]) == (105.0, 108.0)
    assert r["lid_lo"] == float(AG.room_read(px, bands, 99.0)["band"]["lo"])
    assert r["lid_height_pct"] == pytest.approx(3.0)           # (108-105)/100
    assert r["lid_dist_pct"] == pytest.approx(5.0)             # (105-100)/100
    assert r["lid_strength"] == 71.0 and r["lid_touches"] == 3
    assert r["lid_stack"] == 2                                 # both walls sit under the 52w high
    assert r["lid_to_52wh_pct"] == pytest.approx((130.0 - 108.0) / 108.0 * 100.0)
    assert r["lid_bucket"] == LB.dist_bucket(r["lid_dist_pct"]) == "≤5%"


def test_NEGATIVE_a_clear_ceiling_leaves_every_lid_read_undefined_never_zero():
    px = 100.0
    bands = [_band(90.0, 95.0, "demand"), _band(80.0, 85.0, "demand")]
    r = BS.overhead_read(px, bands, prev_close=99.0, hi52=130.0)
    assert r["lid_clear"] is True
    for k in ("lid_lo", "lid_hi", "lid_height_pct", "lid_strength", "lid_touches",
              "lid_dist_pct", "lid_to_52wh_pct", "lid_bucket", "lid52_bucket"):
        assert r[k] is None, k          # a ceiling that is not there is not a 0%-thin ceiling
    assert r["lid_stack"] == 0


def test_NEGATIVE_an_unproven_band_is_never_the_lid():
    """`is_proven_band` needs LID_MIN_TOUCHES; a 1-touch band is noise, not a
    ceiling, and must not become the thinnest lid on the board."""
    px = 100.0
    weak = _band(101.0, 101.4, "supply", touches=1)            # thinnest thing in sight
    real = _band(110.0, 116.0, "supply", touches=4)
    r = BS.overhead_read(px, [weak, real], prev_close=99.0, hi52=130.0)
    assert AG.is_proven_band(weak) is False
    assert (r["lid_lo"], r["lid_hi"]) == (110.0, 116.0)
    assert r["lid_stack"] == 1


def test_NEGATIVE_a_bad_print_reads_nothing():
    for px in (None, 0.0, -3.0):
        r = BS.overhead_read(px, [_band(105.0, 108.0, "supply")], 99.0, 130.0)
        assert r["lid_clear"] is None and r["lid_height_pct"] is None


# ═════════════════════════════════════════════════════════════════════════════
# 3 — the FLOOR read, and the brief's own negative: capped vs absent
# ═════════════════════════════════════════════════════════════════════════════
def test_support_read_serves_band1_and_the_gap_to_the_second_band():
    px = 100.0
    b1 = _band(94.0, 98.0, touches=3, volume=5_000_000, strength=62.0)
    b2 = _band(86.0, 90.0, touches=2)
    r = BS.support_read(px, b1, [b1, b2])
    assert r["sup1_height_pct"] == pytest.approx(4.0)
    assert r["sup1_dist_pct"] == pytest.approx(2.0)            # (100-98)/100
    assert r["sup1_strength"] == 62.0 and r["sup1_touches"] == 3
    assert r["sup1_volume"] == 5_000_000
    assert r["has_band2"] is True
    assert r["sup_gap_pct"] == pytest.approx(4.0)              # (94-90)/100
    assert r["band2_within_cap"] is True
    assert r["n_below"] == 1
    assert BS.parse_offsets(r["below_offsets"]) == [pytest.approx(10.0)]


def test_NEGATIVE_no_second_band_leaves_the_gap_UNDEFINED_never_zero():
    px = 100.0
    b1 = _band(94.0, 98.0)
    r = BS.support_read(px, b1, [b1])
    assert r["has_band2"] is False
    assert r["sup_gap_pct"] is None                            # never 0.0
    assert r["band2_lo"] is None and r["band2_hi"] is None
    assert r["band2_within_cap"] is None                       # not False — there is nothing to cap
    assert r["n_below"] == 0 and BS.parse_offsets(r["below_offsets"]) == []


def test_NEGATIVE_a_second_band_CAPPED_AWAY_is_not_an_ABSENT_second_band():
    """The brief's own trap. `price_zones.compute` surfaces MAX_ZONES_PER_SIDE
    bands per side, cut by DISTANCE, so demand bands ABOVE the print eat cap
    slots and a real "one right below it" can be invisible to a served read.
    Capped-away must report has_band2 True with a real gap and
    band2_within_cap False; absent must report has_band2 False and gap None."""
    px = 100.0
    b1 = _band(94.0, 98.0)
    b2 = _band(70.0, 74.0)                                     # far below: last by distance
    above = [_band(101.0, 103.0), _band(104.0, 106.0), _band(107.0, 109.0)]
    demand_all = [b1] + above + [b2]
    capped = BS.support_read(px, b1, demand_all, max_zones=PZ.MAX_ZONES_PER_SIDE)
    absent = BS.support_read(px, b1, [b1] + above, max_zones=PZ.MAX_ZONES_PER_SIDE)

    served = PZ.nearest_first(list(demand_all), px)[:PZ.MAX_ZONES_PER_SIDE]
    assert b2 not in served                                    # the engine's own cut hides it

    assert capped["has_band2"] is True
    assert capped["sup_gap_pct"] == pytest.approx(20.0)        # (94-74)/100 — a real number
    assert capped["band2_within_cap"] is False
    assert absent["has_band2"] is False and absent["sup_gap_pct"] is None
    assert capped["sup_gap_pct"] != absent["sup_gap_pct"]
    assert capped["band2_within_cap"] is not absent["band2_within_cap"]
    # and raising the READ's cap makes the same band visible again (never a
    # geometry change — a parameter of the read)
    wide = BS.support_read(px, b1, demand_all, max_zones=len(demand_all))
    assert wide["band2_within_cap"] is True
    assert wide["sup_gap_pct"] == capped["sup_gap_pct"]


def test_NEGATIVE_a_band_overlapping_band1s_floor_is_not_the_second_band():
    px = 100.0
    b1 = _band(94.0, 98.0)
    overlap = _band(90.0, 95.0)                                # hi sits INSIDE band1
    r = BS.support_read(px, b1, [b1, overlap])
    assert r["has_band2"] is False and r["sup_gap_pct"] is None


def test_ship_eligibility_names_the_cap_and_refuses_the_forward_conditioned_reads():
    ok, why = BS.ship_eligible_feature("sup_gap_pct")
    assert ok is True and "band2_within_cap" in why and "MAX_ZONES_PER_SIDE" in why
    ok, why = BS.ship_eligible_feature("depth_q50")
    assert ok is True and "band2_within_cap" in why
    assert BS.ship_eligible_feature("lid_height_pct")[0] is True
    assert BS.ship_eligible_feature("sup1_height_pct")[0] is True
    for feat in ("held_band2_20", "under_band1_20", "k_under_band1", "hit5_20"):
        ok, why = BS.ship_eligible_feature(feat)
        assert ok is False, feat


# ═════════════════════════════════════════════════════════════════════════════
# 4 — the outcomes
# ═════════════════════════════════════════════════════════════════════════════
def test_clear_lid_needs_a_CLOSE_above_the_lid_top():
    fl = np.full(20, 95.0)
    fc = np.full(20, 101.0)
    fc[6] = 109.0                                              # closes above a 108 lid
    r = BS.clear_lid_outcome(fc, fl, 108.0, 90.0, HOLD)
    assert r["clear_lid_20"] == 1.0 and r["clear_lid_bs_20"] == 1.0
    assert r["k_clear_lid"] == 7.0


def test_NEGATIVE_a_high_that_never_closes_above_the_lid_does_not_clear_it():
    fl = np.full(20, 95.0)
    fc = np.full(20, 101.0)
    fc[6] = 108.0                                              # exactly AT the top, not above
    r = BS.clear_lid_outcome(fc, fl, 108.0, 90.0, HOLD)
    assert r["clear_lid_20"] == 0.0
    assert np.isnan(r["k_clear_lid"])


def test_NEGATIVE_no_lid_leaves_the_clear_outcome_undefined_not_a_failure():
    fc = np.full(20, 101.0)
    r = BS.clear_lid_outcome(fc, np.full(20, 95.0), None, 90.0, HOLD)
    assert np.isnan(r["clear_lid_20"]) and np.isnan(r["clear_lid_bs_20"])


def test_the_before_the_stop_twin_drops_a_clear_that_came_after_the_stop():
    fl = np.full(20, 95.0)
    fl[2] = 89.0                                               # floor stop at 90 on bar 3
    fc = np.full(20, 101.0)
    fc[6] = 109.0
    r = BS.clear_lid_outcome(fc, fl, 108.0, 90.0, HOLD)
    assert r["clear_lid_20"] == 1.0                            # it did clear...
    assert r["clear_lid_bs_20"] == 0.0                         # ...but the stop came first


def test_second_band_holds_only_after_the_first_floor_is_actually_lost():
    fc = np.full(20, 95.0)
    fc[4:] = 92.0                                              # under band1 floor 94, over 90
    r = BS.under_band1_outcome(fc, 94.0, 90.0, HOLD)
    assert r["under_band1_20"] == 1.0 and r["k_under_band1"] == 5.0
    assert r["held_band2_20"] == 1.0
    fc2 = fc.copy()
    fc2[9] = 88.0                                              # through the second floor
    assert BS.under_band1_outcome(fc2, 94.0, 90.0, HOLD)["held_band2_20"] == 0.0


def test_NEGATIVE_never_under_band1_and_no_second_band_both_leave_held_UNDEFINED():
    fc = np.full(20, 96.0)
    never = BS.under_band1_outcome(fc, 94.0, 90.0, HOLD)
    assert never["under_band1_20"] == 0.0
    assert np.isnan(never["held_band2_20"])                    # not False
    assert np.isnan(never["k_under_band1"])
    fc2 = np.full(20, 92.0)
    no_b2 = BS.under_band1_outcome(fc2, 94.0, None, HOLD)
    assert no_b2["under_band1_20"] == 1.0
    assert np.isnan(no_b2["held_band2_20"])                    # nothing underneath to hold


# ═════════════════════════════════════════════════════════════════════════════
# 5 — the offsets / depth helpers
# ═════════════════════════════════════════════════════════════════════════════
def test_depth_counts_bands_inside_a_quantile_cut():
    offs = [2.0, 6.5, 11.0, 30.0]
    assert BS.depth_within(offs, 7.0) == 2
    assert BS.depth_within(offs, 100.0) == 4


def test_NEGATIVE_a_missing_offsets_cell_is_no_bands_not_a_band_at_zero():
    for blank in (None, "", float("nan"), "nan", "None"):
        assert BS.parse_offsets(blank) == []
        assert BS.depth_within(BS.parse_offsets(blank), 5.0) == 0
    assert BS.depth_within([1.0], None) is None                # no quantile = no answer


# ═════════════════════════════════════════════════════════════════════════════
# 6 — the conditional contrast: a lift that IS distance must not survive it
# ═════════════════════════════════════════════════════════════════════════════
def _strat_frame(n_per_cell: int, thin_lift: float, seed: int = 11,
                 thin_only_in_near: bool = False, bases=(0.50, 0.10)) -> pd.DataFrame:
    """Two distance strata with very different base rates. `thin_lift` is the
    extra hit rate the THIN rows carry INSIDE their own stratum. Dates and
    symbols are spread wide so the one-per-date / one-per-symbol point estimates
    are not pure noise."""
    rng = np.random.default_rng(seed)
    dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2025-01-02", periods=300)]
    rows = []
    for bucket, base in (("≤5%", bases[0]), (">15%", bases[1])):
        for thin in (True, False):
            if thin_only_in_near and thin and bucket != "≤5%":
                continue
            for i in range(n_per_cell):
                p = base + (thin_lift if thin else 0.0)
                rows.append({"symbol": "S%04d" % rng.integers(0, 300),
                             "date": dates[int(rng.integers(0, 300))],
                             "lid_bucket": bucket, "thin": thin,
                             "hit": float(rng.uniform() < min(max(p, 0.0), 1.0)),
                             "stop": float(rng.uniform() < 0.6)})
    return pd.DataFrame(rows).reset_index(drop=True)


_CONV = {"tag": "T", "hit": "hit", "stop": "stop"}


def test_a_lift_present_inside_every_distance_bucket_separates():
    D = _strat_frame(600, thin_lift=0.35, seed=3)
    r = BS.conditional_contrast(D, D["thin"], "lid_bucket", _CONV, _A(),
                                BS.strat_order(D, "lid_bucket"))
    assert r["pooled"] == ["≤5%", ">15%"]
    assert r["d_cond"] > 0 and r["ci_cond"][0] > 0
    assert r["verdict"] == "separates"


def test_NEGATIVE_a_lift_that_is_only_DISTANCE_does_not_survive_the_conditioning():
    """The whole point of the 2026-09-07 conditioning. THIN rows here carry no
    within-bucket edge at all — they merely sit in the near bucket, whose base
    rate is 70pp higher. Pooled over the cohort that reads as a huge lift; inside
    the buckets it is nothing, and the verdict must say so."""
    D = _strat_frame(600, thin_lift=0.0, seed=5, thin_only_in_near=True,
                     bases=(0.85, 0.05))
    pooled_naive = (D.loc[D["thin"], "hit"].mean() - D["hit"].mean()) * 100.0
    assert pooled_naive > 20.0                                  # the trap, unconditioned
    r = BS.conditional_contrast(D, D["thin"], "lid_bucket", _CONV, _A(),
                                BS.strat_order(D, "lid_bucket"))
    assert r["pooled"] == ["≤5%"]                               # the far bucket has no thin rows
    assert ">15%" not in r["pooled"]
    assert r["verdict"] != "separates"
    assert abs(r["d_cond"]) < 10.0


def test_a_cell_under_the_floor_is_dropped_and_named_never_silently_pooled():
    D = _strat_frame(400, thin_lift=0.1, seed=7)
    tiny = D["thin"].copy()
    far = D["lid_bucket"] == ">15%"
    tiny[far] = False
    tiny.iloc[np.flatnonzero(far.to_numpy())[:5]] = True         # 5 thin rows, under the floor
    cl = BS.strat_cells(D, "lid_bucket", tiny, BS.strat_order(D, "lid_bucket"))
    assert cl["labels"][cl["ks"][0]] == "≤5%" and len(cl["ks"]) == 1
    assert ">15%" in cl["dropped"]
    assert pytest.approx(sum(cl["weights"].values())) == 1.0
    assert cl["n_base"][">15%"] == int(far.sum())


def test_NEGATIVE_an_empty_stratifier_reports_undefined_not_a_verdict():
    D = _strat_frame(400, thin_lift=0.1, seed=9)
    D["lid52_bucket"] = np.nan
    r = BS.conditional_contrast(D, D["thin"], "lid52_bucket", _CONV, _A(), [])
    assert r["d_cond"] is None and r["ci_cond"] == [None, None]
    assert r["verdict"].startswith("n<%d" % BS.MIN_CELL_N)


def test_cond_verdict_refuses_a_lift_that_raises_stop_outs_or_loses_the_dedupe_sign():
    good = {"d_cond": 5.0, "ci_cond": [1.0, 9.0], "mdl_cond": 2.0,
            "ci_stop_cond": [-3.0, 1.0], "one_per_date": 4.0, "one_per_symbol": 3.0}
    assert BS.cond_verdict(good) == "separates"
    assert BS.cond_verdict(dict(good, mdl_cond=9.0)).startswith("inert (under")
    assert BS.cond_verdict(dict(good, ci_stop_cond=[1.0, 6.0])) == "inert (raises stop-outs)"
    assert BS.cond_verdict(dict(good, one_per_symbol=-1.0)).startswith("inert (one-per-date")
    assert BS.cond_verdict(dict(good, ci_cond=[-9.0, -1.0])) == "harmful"
    assert BS.cond_verdict({"d_cond": None}).startswith("n<%d" % BS.MIN_CELL_N)


# ═════════════════════════════════════════════════════════════════════════════
# 7 — CRDO, his own reference case, reproduced from the served band fields
# ═════════════════════════════════════════════════════════════════════════════
def test_CRDO_reference_case_from_the_brief():
    """Ajay 2026-09-16: "Something like CRDO had at 149. It has another one right
    below it". Board geometry, close 162.76, demand bands 182.61-189.12 /
    173.90-180.10 / 161.92-167.68 / 146.34-151.55. The gap from the 161.92 floor
    to the 146.34 band's top is 6.37% of price — the brief's own number."""
    px = 162.76
    bands = [_band(182.61, 189.12), _band(173.90, 180.10),
             _band(161.92, 167.68), _band(146.34, 151.55)]
    b1 = bands[2]                                               # the band the print sits in
    r = BS.support_read(px, b1, bands)
    assert r["sup_gap_pct"] == pytest.approx(6.37, abs=0.005)
    assert r["has_band2"] is True
    assert r["band2_within_cap"] is True                        # 4 bands, cap 4 — his 149 is served
    assert (r["band2_lo"], r["band2_hi"]) == (146.34, 151.55)
    assert r["sup1_height_pct"] == pytest.approx((167.68 - 161.92) / px * 100.0)
    assert r["sup1_dist_pct"] < 0                               # the print is INSIDE band1
    assert r["n_below"] == 1


# ═════════════════════════════════════════════════════════════════════════════
# 8 — the stats stage runs with no Mongo, and the CLI parses
# ═════════════════════════════════════════════════════════════════════════════
def _synthetic_events(n_sym: int = 90, n_ev: int = 10, seed: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2025-01-02", periods=420)]
    rows = []
    for s in range(n_sym):
        sym = "S%03d" % s
        off = int(rng.integers(0, 60))
        for i in range(n_ev):
            j = 130 + 25 * i + off
            entry = 50.0 + rng.uniform(0, 50)
            stop = entry * (1 - rng.uniform(0.01, 0.05))
            clear = rng.uniform() < 0.12
            target = np.nan if clear else entry * (1 + rng.uniform(0.06, 0.2))
            hit = float(rng.uniform() < 0.34)
            stp = float(rng.uniform() < 0.74) if hit == 0 else 0.0
            why = "stop" if stp else ("target" if (hit and not clear) else "clock")
            R = -1.0 if why == "stop" else rng.uniform(-0.5, 3.0)
            lid_dist = rng.uniform(5.0, 25.0)
            has2 = rng.uniform() < 0.7
            gap = rng.uniform(1.0, 12.0) if has2 else np.nan
            sup1_dist = rng.uniform(0.0, 1.0)
            offs = "%.4f" % (sup1_dist + gap) if has2 else ""
            under = float(rng.uniform() < 0.5)
            row = {"symbol": sym, "date": dates[j - 130], "bar_idx": j,
                   "dir": rng.choice(["bouncing", "falling"], p=[0.78, 0.22]),
                   "entry": entry, "stop": stop, "target": target, "clear": clear,
                   "room_pct": np.nan if clear else (target / entry - 1) * 100,
                   "risk_pct": (entry - stop) / entry * 100,
                   "R": R, "why": why, "dvol50_pre": rng.lognormal(16, 1.5),
                   "band_lo": stop / 0.995, "band_hi": stop / 0.995 * 1.02,
                   "hi52": entry * 1.4, "gap_N": rng.uniform() < 0.05,
                   "risk_pct_N": (entry - stop) / entry * 100, "entry_N": entry,
                   "lid_lo": entry * (1 + lid_dist / 100.0),
                   "lid_hi": entry * (1 + lid_dist / 100.0) * 1.03,
                   "lid_height_pct": rng.uniform(0.5, 9.0),
                   "lid_strength": rng.uniform(0, 100), "lid_touches": rng.integers(2, 6),
                   "lid_stack": rng.integers(1, 5), "lid_dist_pct": lid_dist,
                   "lid_to_52wh_pct": rng.uniform(0.0, 30.0), "lid_clear": False,
                   "sup1_lo": stop / 0.995, "sup1_hi": stop / 0.995 * 1.02,
                   "sup1_height_pct": rng.uniform(1.0, 8.0),
                   "sup1_strength": rng.uniform(0, 100), "sup1_touches": rng.integers(1, 5),
                   "sup1_volume": rng.lognormal(14, 1.0), "sup1_dist_pct": sup1_dist,
                   "band2_lo": (stop / 0.995) * 0.9 if has2 else np.nan,
                   "band2_hi": (stop / 0.995) * 0.93 if has2 else np.nan,
                   "sup_gap_pct": gap, "has_band2": has2,
                   "band2_within_cap": bool(has2 and rng.uniform() < 0.8),
                   "n_below": int(has2), "below_offsets": offs,
                   "clear_lid_20": float(rng.uniform() < 0.3),
                   "clear_lid_bs_20": float(rng.uniform() < 0.22),
                   "k_clear_lid": np.nan,
                   "under_band1_20": under, "k_under_band1": 4.0 if under else np.nan,
                   "held_band2_20": (float(rng.uniform() < 0.5)
                                     if (under and has2) else np.nan),
                   "max_gain_pct_20": rng.uniform(0, 12),
                   "hit5c_20": hit, "hit5c_20_N": hit}
            row["lid_bucket"] = LB.dist_bucket(lid_dist)
            row["lid52_bucket"] = LB.dist_bucket(row["lid_to_52wh_pct"])
            for cl in CLOCKS:
                row["hit5_%d" % cl] = hit
                row["hit5b_%d" % cl] = hit
                row["hit_lid_%d" % cl] = np.nan if clear else float(why == "target")
                row["stop_%d" % cl] = stp
                row["R%d" % cl] = R
                row["why%d" % cl] = why
                row["pct%d" % cl] = R
                row["hit5_%d_N" % cl] = hit
                row["hit_lid_%d_N" % cl] = row["hit_lid_%d" % cl]
                row["stop_%d_N" % cl] = stp
                row["R%d_N" % cl] = R
                row["why%d_N" % cl] = why
            rows.append(row)
    X = pd.DataFrame(rows)
    X["episode"] = True
    X["episode_dir"] = True
    return X


def _write(tmp_path, X: pd.DataFrame, stride: int = 1, name: str = "ev.csv"):
    csv = tmp_path / name
    X.to_csv(csv, index=False)
    with open(str(csv) + ".meta.json", "w") as fh:
        json.dump({"universe_mode": "broad", "n_universe": 400, "floor": 120,
                   "stride": stride, "names": 0, "hold": HOLD,
                   "max_zones_read": PZ.MAX_ZONES_PER_SIDE}, fh)
    return csv


def _run(csv, out, extra=()):
    BS.main(["--stage", "stats", "--from-csv", str(csv), "--json", str(out),
             "--boot-draws", "150", "--perm-draws", "60", "--placebo-draws", "60"]
            + list(extra))
    return json.load(open(out))


def test_stats_stage_runs_without_mongo_and_writes_every_measured_key(tmp_path):
    csv = _write(tmp_path, _synthetic_events())
    m = _run(csv, tmp_path / "m.json")
    for k in ("run_date", "script", "quotable", "n_episodes", "n_dates", "window",
              "cap_note", "dist_buckets", "depth_cuts", "base", "q1", "q2",
              "survivorship", "status", "fallback", "max_zones_read"):
        assert k in m, k
    assert m["script"] == BS.SCRIPT
    assert m["dist_buckets"] == [n for _, n in LB.DIST_BUCKETS]
    for q, feats in (("q1", BS.OVERHEAD_FEATS), ("q2", BS.SUPPORT_FEATS)):
        blk = m[q]
        assert blk["status"] in ("separates", "no_signal")
        assert set(blk["splits"]) == {"s1", "s2", "s3"}
        assert blk["conditional"], q
        names = {p["name"] for p in blk["per_feature"]}
        assert set(feats) <= names, q
    assert m["q2"]["held"]["ship_eligible"] is False
    assert any(b["bin"] == "NaN" and "UNDEFINED" in (b["note"] or "")
               for b in m["q2"]["gap_bins"])
    assert "MAX_ZONES_PER_SIDE" in m["cap_note"]
    assert m["q2"]["capped_only"]["n_uncapped_only"] >= 0


def test_the_depth_cuts_are_cohort_quantiles_and_never_typed(tmp_path):
    csv = _write(tmp_path, _synthetic_events(seed=6))
    m = _run(csv, tmp_path / "m.json")
    cuts = m["depth_cuts"]
    assert set(cuts) == {"depth_q%d" % int(round(q * 100)) for q in BS.DEPTH_QUANTILES}
    vals = [v for v in cuts.values() if v is not None]
    assert len(vals) == len(BS.DEPTH_QUANTILES)
    assert vals == sorted(vals) and vals[0] > 0
    src = open(BS.__file__).read()
    assert "DEPTH_QUANTILES = (0.25, 0.50, 0.75)" in src        # quantiles, not percentages


def test_NEGATIVE_a_strided_run_is_never_quotable_and_says_why(tmp_path, capsys):
    csv = _write(tmp_path, _synthetic_events(seed=8), stride=2)
    m = _run(csv, tmp_path / "m.json", extra=["--stride", "2"])
    printed = capsys.readouterr().out
    assert "NOT QUOTABLE" in printed
    assert m["quotable"] is False
    assert m["not_quotable_reason"] == BS.SUBSAMPLE_NOT_QUOTABLE


def test_NEGATIVE_without_the_survivorship_replay_the_run_is_not_quotable(tmp_path, capsys):
    csv = _write(tmp_path, _synthetic_events(seed=10))
    m = _run(csv, tmp_path / "m.json")
    assert m["quotable"] is False
    assert m["not_quotable_reason"] == BS.SURVIVORSHIP_MISSING
    assert BS.SURVIVORSHIP_MISSING in capsys.readouterr().out
    assert m["survivorship"]["cache_hit5_20"] is None


def test_quotable_only_once_the_cache_universe_replay_is_in_hand(tmp_path):
    X = _synthetic_events(seed=12)
    csv = _write(tmp_path, X)
    cache = _write(tmp_path, _synthetic_events(n_sym=40, seed=13), name="cache.csv")
    m = _run(csv, tmp_path / "m.json", extra=["--cache-csv", str(cache)])
    assert m["survivorship"]["cache_hit5_20"] is not None
    assert m["quotable"] is True


def test_block_status_needs_a_ship_eligible_feature_on_all_three_splits_and_the_conditioning():
    sep = {"verdict": "separates"}
    blk = {"per_feature": [{"name": "sup_gap_pct", "ship_eligible": True,
                            "top": {"verdict": "separates"}}],
           "conditional": {"sup_gap_pct": {"lid_bucket": sep, "lid52_bucket": sep}},
           "splits": {"s1": dict(sep, mdl=1.0), "s2": dict(sep, mdl=1.2),
                      "s3": dict(sep, mdl=0.9)}}
    status, sel, mdl = BS.block_status(blk)
    assert status == "separates" and sel == ["sup_gap_pct"] and mdl == 1.2
    # one split short -> no_signal
    bad = json.loads(json.dumps(blk))
    bad["splits"]["s3"]["verdict"] = "no_signal"
    assert BS.block_status(bad)[0] == "no_signal"
    # the conditioning short -> no_signal, and the feature is not selected
    bad2 = json.loads(json.dumps(blk))
    bad2["conditional"]["sup_gap_pct"]["lid_bucket"] = {"verdict": "inert"}
    assert BS.block_status(bad2) == ("no_signal", [], 1.2)
    # a feature that cannot ship never selects, however well it measures
    bad3 = json.loads(json.dumps(blk))
    bad3["per_feature"][0]["ship_eligible"] = False
    assert BS.block_status(bad3) == ("no_signal", [], 1.2)


def test_the_cli_parses_every_stage_and_refuses_stats_with_no_csv(capsys):
    with pytest.raises(SystemExit) as e:
        BS.main(["--stage", "stats"])
    assert e.value.code == 2
    assert "--from-csv is required" in capsys.readouterr().err
    with pytest.raises(SystemExit) as e:
        BS.main(["--help"])
    assert e.value.code == 0
    printed = capsys.readouterr().out
    for flag in ("--stage", "--universe", "--stride", "--max-zones", "--cache-csv",
                 "--survivorship", "--json", "--emit-measured"):
        assert flag in printed, flag


def test_wanted_columns_cover_every_read_the_stats_stage_makes():
    cols = set(BS.wanted_columns(CLOCKS, HOLD, "hit5"))
    convs = BS.conventions("hit5", HOLD)
    for tag in ("P", "N", "CLEAR"):
        c = convs[tag]
        for key in ("hit", "hit5", "hit5b", "hit_lid", "stop", "R", "why", "risk"):
            assert c[key] in cols, (tag, key, c[key])
        assert set(c["feats"]) <= cols, tag
    for extra in ("room_pct", "clear", "episode_dir", "dir", "below_offsets",
                  "band2_within_cap", "has_band2", "under_band1_%d" % HOLD,
                  "held_band2_%d" % HOLD, "lid_bucket", "lid52_bucket"):
        assert extra in cols, extra
    assert convs["CLEAR"]["hit"] == "clear_lid_%d" % HOLD


# ═════════════════════════════════════════════════════════════════════════════
# 9 — the replay's per-symbol pass: real bands, no Mongo, no lookahead
# ═════════════════════════════════════════════════════════════════════════════
def _frame(n: int = 400, seed: int = 5, base: float = 100.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    step = rng.normal(0, 1.0, n)
    close = np.maximum(base + np.cumsum(step), 5.0)
    wick = np.abs(rng.normal(0, 0.8, n)) + 0.05
    dates = pd.bdate_range("2025-01-02", periods=n)
    return pd.DataFrame({"date": dates, "open": close - step * 0.5, "high": close + wick,
                         "low": close - wick, "close": close,
                         "volume": rng.integers(100_000, 1_000_000, n).astype(float),
                         "d": dates.strftime("%Y-%m-%d")})


def _events_on(f: pd.DataFrame, geom: dict, want: int = 6) -> pd.DataFrame:
    o, h = f["open"].to_numpy(float), f["high"].to_numpy(float)
    l, c = f["low"].to_numpy(float), f["close"].to_numpy(float)
    rows = []
    for j in range(260, len(f) - 25):
        z = PZ.compute(f.iloc[max(0, j - BS.BOX_BARS):j], last_price=float(c[j]),
                       max_zones=None, **geom)
        if not z:
            continue
        bands = (z.get("supply_zones") or []) + (z.get("demand_zones") or [])
        ea = ETS.event_at(o, h, l, c, j, bands)
        if not ea:
            continue
        rows.append({"symbol": "SYN", "date": f["d"].iloc[j], "entry": float(c[j]),
                     "stop": ea["stop"], "target": ea["target"]})
        if len(rows) >= want:
            break
    return pd.DataFrame(rows)


def test_features_for_symbol_runs_with_no_mongo_and_serves_both_halves():
    from supply_demand import demand_reentry as DR
    geom = DR.zone_geom()
    f = _frame(400, seed=5)
    ev = _events_on(f, geom)
    if ev.empty:
        pytest.skip("the synthetic frame produced no engine event")
    counters = {"no_bar": 0, "no_band": 0, "band_mismatch": 0, "no_frame": 0}
    rows = BS.features_for_symbol("SYN", f, ev, HOLD, CLOCKS, geom, counters)
    assert rows and counters["no_band"] == 0 and counters["band_mismatch"] == 0
    r = rows[0]
    for k in ("lid_clear", "lid_stack", "sup1_height_pct", "sup1_dist_pct", "has_band2",
              "n_below", "below_offsets", "clear_lid_%d" % HOLD, "clear_lid_bs_%d" % HOLD,
              "under_band1_%d" % HOLD, "held_band2_%d" % HOLD, "hit5_%d" % HOLD,
              "stop_%d" % HOLD, "hit5_%d_N" % HOLD):
        assert k in r, k
    # the stop the engine planned IS band1's floor less the imported buffer
    assert r["sup1_lo"] == pytest.approx(float(ev["stop"].iloc[0]) /
                                        (1.0 - BS.STOP_BUFFER_PCT / 100.0))
    # gap and band2 never disagree with each other
    assert (r["sup_gap_pct"] is None) == (not r["has_band2"])


def test_LOOKAHEAD_GUARD_no_structural_column_moves_when_future_bars_change():
    from supply_demand import demand_reentry as DR
    geom = DR.zone_geom()
    f = _frame(400, seed=5)
    ev = _events_on(f, geom, want=3)
    if ev.empty:
        pytest.skip("the synthetic frame produced no engine event")
    counters = {"no_bar": 0, "no_band": 0, "band_mismatch": 0, "no_frame": 0}
    base = BS.features_for_symbol("SYN", f, ev, HOLD, CLOCKS, geom, dict(counters))
    j = int(base[0]["bar_idx"])
    g = f.copy()
    for col in ("open", "high", "low", "close"):
        g.loc[g.index[j + 1:], col] = g.loc[g.index[j + 1:], col] * 3.0
    moved = BS.features_for_symbol("SYN", g, ev.iloc[:1], HOLD, CLOCKS, geom, dict(counters))
    structural = list(BS.OVERHEAD_FEATS) + list(BS.SUPPORT_FEATS) + [
        "lid_lo", "lid_hi", "lid_clear", "sup1_lo", "sup1_hi", "band2_lo", "band2_hi",
        "has_band2", "band2_within_cap", "n_below", "below_offsets", "hi52"]
    for k in structural:
        a, b = base[0].get(k), moved[0].get(k)
        if isinstance(a, float) and a != a:
            assert isinstance(b, float) and b != b, k
        else:
            assert a == b, k
    # and the OUTCOMES must move — otherwise the guard proves nothing
    assert (moved[0]["max_gain_pct_%d" % HOLD]
            != pytest.approx(base[0]["max_gain_pct_%d" % HOLD]))
