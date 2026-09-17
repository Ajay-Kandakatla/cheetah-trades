"""Study-side tests for scripts/deep_levels_study.py (the 2026-09-16 deep-demand
LEVELS ask) and for supply_demand/deep_levels_measured.py.

Everything runs WITHOUT Mongo on synthetic frames. The rules this file exists to
enforce:

  * the study WALKS NOTHING ITSELF — it calls the shipped `deep_demand.arrival()`
    and `deep_demand.read()`, so the study and the board can never drift;
  * NOT ONE cut is typed — `MIN_TOUCHES`, `MIN_ZONE_STRENGTH`, `NEAR_PCT`,
    `MAX_ZONES_PER_SIDE`, `MAX_LEVELS_BROKEN`, `MIN_CELL_N`, the +5% target and
    the stop buffer all arrive by import;
  * the NEGATIVES are mandatory: an under-floor cell reads "not shown" and
    carries no rates, a MISSING strength gets its own bucket and is never
    silently counted as below the cut, a non-arrival is never a depth of zero,
    and `MEASURED = None` reads as PENDING with nothing quotable from it.
"""
from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd
import pytest

from scripts import band_structure_study as BS
from scripts import deep_levels_study as DL
from scripts import entry_trigger_study as ETS
from scripts import explosive_study as ES
from supply_demand import deep_demand as DD
from supply_demand import deep_levels_measured as DLM
from supply_demand import demand_reentry as DR
from supply_demand import price_zones as PZ

CLOCKS = (5, 10, 20)
HOLD = 20


class _A:
    """The argparse namespace the stats helpers read."""
    boot_draws = 200
    perm_draws = 100
    placebo_draws = 120


def _band(lo, hi, touches=2, volume=1_000_000, strength=50.0) -> dict:
    return {"kind": "demand", "lo": float(lo), "hi": float(hi), "mid": (lo + hi) / 2.0,
            "touches": int(touches), "volume": int(volume), "strength": float(strength),
            "bars_since_test": 5, "oldest_touch_bars": 60, "touch_dates": None}


# CRDO 2026-09-16, close 150.39 — HIS OWN EXAMPLE, the served window verbatim.
CRDO_PX = 150.39
CRDO_WINDOW = [_band(161.92, 167.68, touches=1, strength=28.0),
               _band(146.34, 151.55, touches=1, strength=31.0),
               _band(132.76, 138.00, touches=2, strength=54.0),
               _band(123.87, 128.80, touches=3, strength=94.0)]


def _code(mod) -> str:
    """The module source with its docstring and every `#` comment removed, so a
    numeric-literal scan reads CODE and not prose."""
    src = open(mod.__file__).read()
    body = src.split("from __future__ import annotations", 1)[1]
    out = []
    for line in body.splitlines():
        out.append(line.split("  #", 1)[0] if "  #" in line else line)
    return "\n".join(out)


# ═════════════════════════════════════════════════════════════════════════════
# 1 — the module imports clean, and every threshold is IMPORTED
# ═════════════════════════════════════════════════════════════════════════════
def test_the_module_imports_with_no_mongo_and_names_itself():
    assert DL.SCRIPT == "backend/scripts/deep_levels_study.py"
    assert DL.__doc__ and "RESULTS" in DL.__doc__
    tail = DL.__doc__[DL.__doc__.index("RESULTS"):]
    assert tail.startswith("RESULTS — pending") or "cohort:" in tail
    assert "DEVIATIONS" in DL.__doc__ and "THE CAP, STATED" in DL.__doc__


def test_constants_are_imported_and_nothing_is_typed():
    assert DL.FIVE_PCT is ES.FIVE_PCT
    assert DL.STOP_BUFFER_PCT is ES.STOP_BUFFER_PCT
    assert DL.FLOOR_DEFAULT is ES.FLOOR_DEFAULT
    assert DL.HOLD_DEFAULT is ES.HOLD_DEFAULT
    assert DL.CLOCKS_DEFAULT is ES.CLOCKS_DEFAULT
    assert DL.MIN_CELL_N is ETS.MIN_CELL_N and DL.MIN_CELL_N == 120
    assert DL.MAX_ZONES is PZ.MAX_ZONES_PER_SIDE
    assert DL.NEAR_PCT is PZ.NEAR_PCT
    assert DL.MIN_TOUCHES is DR.MIN_TOUCHES and DL.MIN_TOUCHES == 2
    assert DL.MIN_ZONE_STRENGTH is DR.MIN_ZONE_STRENGTH and DL.MIN_ZONE_STRENGTH == 40.0
    assert DL.MAX_LEVELS == DD.MAX_LEVELS_BROKEN


def test_the_bucket_LABELS_are_built_from_the_constants_not_typed():
    assert DL.STRENGTH_LO == "<%g" % DR.MIN_ZONE_STRENGTH
    assert DL.STRENGTH_HI == ">=%g" % DR.MIN_ZONE_STRENGTH
    assert DL.TOUCH_MIN_LABEL == str(DR.MIN_TOUCHES)
    assert DL.TOUCH_UNDER_LABEL == str(DR.MIN_TOUCHES - 1)
    assert DL.TOUCH_OVER_LABEL == "%d+" % (DR.MIN_TOUCHES + 1)
    assert "%d" % DR.MIN_TOUCHES in DL.GATE_NOTE
    assert "%g" % DR.MIN_ZONE_STRENGTH in DL.GATE_NOTE


def test_NEGATIVE_no_threshold_VALUE_is_typed_anywhere_in_the_code():
    """A source scan, comments and docstring stripped: the values behind the
    imported constants must never appear as literals."""
    forbidden = re.compile(r"(?<![\w.])(40(\.0)?|3\.0|0\.5|5\.0|120|252|2\.0)(?![\w.])")
    hits = [ln for ln in _code(DL).splitlines() if forbidden.search(ln)]
    assert hits == [], hits


def test_the_study_calls_the_SHIPPED_qualifier_and_re_implements_nothing():
    src = open(DL.__file__).read()
    assert "DD.arrival(" in src and "DD.read(" in src
    assert "PZ.nearest_first(" in src
    # the harness comes in by import, never by transcription
    for name in ("ETS.feature_table(", "ETS.split_masks(", "ETS.survivorship_read(",
                 "ES.run_split(", "ES.evaluate_bucket(", "ES.bucket_stats(",
                 "ES.assign_buckets(", "BS.conditional_contrast("):
        assert name in src, name
    # no parallel definition of the walk, the gate, the touch or the outcome
    assert "def arrival(" not in src and "def read(" not in src
    assert "def event_at" not in src and "def outcome_block" not in src
    assert "def conditional_contrast" not in src and "def evaluate_bucket" not in src


# ═════════════════════════════════════════════════════════════════════════════
# 2 — the SERVED window is the engine's own cut, and the depth cap is a READ
# ═════════════════════════════════════════════════════════════════════════════
def test_served_window_is_nearest_first_cut_then_high_to_low():
    px = 150.0
    demand = [_band(100.0, 104.0), _band(110.0, 114.0), _band(120.0, 124.0),
              _band(130.0, 134.0), _band(140.0, 144.0), _band(160.0, 164.0)]
    w = DL.served_window(demand, px)
    assert len(w) == PZ.MAX_ZONES_PER_SIDE
    expect = PZ.nearest_first(list(demand), px)[:PZ.MAX_ZONES_PER_SIDE]
    assert {(b["lo"], b["hi"]) for b in w} == {(b["lo"], b["hi"]) for b in expect}
    assert [b["mid"] for b in w] == sorted([b["mid"] for b in w], reverse=True)


def test_NEGATIVE_a_bad_print_or_an_empty_stack_serves_nothing():
    assert DL.served_window([_band(1, 2)], None) == []
    assert DL.served_window([_band(1, 2)], 0.0) == []
    assert DL.served_window(None, 10.0) == []
    assert DL.arrival_read(None, CRDO_WINDOW)["levels_broken"] is None
    assert DL.arrival_read(100.0, [])["levels_broken_all"] is None


def test_levels_cap_widens_the_READ_and_always_restores_the_shipped_constant():
    orig = DD.MAX_LEVELS_BROKEN
    with DL.levels_cap(9):
        assert DD.MAX_LEVELS_BROKEN == 9
    assert DD.MAX_LEVELS_BROKEN is orig
    with pytest.raises(RuntimeError):
        with DL.levels_cap(9):
            raise RuntimeError("boom")
    assert DD.MAX_LEVELS_BROKEN is orig            # restored even on the way out


def test_a_deeper_arrival_than_the_shipped_cap_is_counted_but_not_kept():
    """4 bands, price inside the LOWEST: 3 levels crossed. The shipped cap keeps
    up to MAX_LEVELS_BROKEN, so `levels_broken` is None while
    `levels_broken_all` still says 3 and `arrival_within_cap` says why."""
    dz = [_band(160, 164), _band(150, 154), _band(140, 144), _band(130, 134)]
    r = DL.arrival_read(132.0, dz)
    assert r["levels_broken_all"] == 3
    assert r["arrival_within_cap"] is (3 <= DD.MAX_LEVELS_BROKEN)
    assert r["levels_broken"] is None and r["level"] is None
    assert DD.MAX_LEVELS_BROKEN == DL.MAX_LEVELS            # untouched by the read


def test_arrival_read_agrees_with_the_shipped_arrival_on_a_kept_row():
    dz = [_band(160, 164), _band(150, 154), _band(140, 144), _band(130, 134)]
    r = DL.arrival_read(152.0, dz)
    got = DD.arrival(DL.served_window(dz, 152.0), 152.0)
    assert got is not None
    assert r["levels_broken"] == got[0] == 1
    assert r["level"] == 2
    assert (r["arr_lo"], r["arr_hi"]) == (got[1]["lo"], got[1]["hi"])
    assert r["deep_state"] == "in" and r["arr_dist_pct"] == 0.0


def test_the_near_state_reads_the_distance_above_the_arrival_band():
    dz = [_band(160, 164), _band(150, 154), _band(140, 144), _band(130, 134)]
    px = 154.0 * (1.0 + (PZ.NEAR_PCT / 2.0) / 100.0)
    r = DL.arrival_read(px, dz)
    assert r["deep_state"] == "near"
    assert r["arr_dist_pct"] == pytest.approx((px - 154.0) / px * 100.0)
    assert 0 < r["arr_dist_pct"] <= PZ.NEAR_PCT


# ═════════════════════════════════════════════════════════════════════════════
# 3 — CRDO, his own example: the GEOMETRY qualifies, the BAND BAR hides it
# ═════════════════════════════════════════════════════════════════════════════
def test_CRDO_geometry_qualifies_and_only_the_arrival_bands_quality_refuses_it():
    r = DL.arrival_read(CRDO_PX, CRDO_WINDOW)
    assert r["levels_broken"] == 1 and r["level"] == 2      # crossed 161.92, standing in 146.34
    assert r["deep_state"] == "in"
    assert (r["arr_lo"], r["arr_hi"]) == (146.34, 151.55)
    assert r["arr_touches"] == 1.0 and r["arr_strength"] == 31.0
    assert r["arr_gate_pass"] is False                      # touches 1 < 2, strength 31 < 40
    assert DL.touches_bucket(r["arr_touches"]) == DL.TOUCH_UNDER_LABEL
    assert DL.strength_side(r["arr_strength"]) == DL.STRENGTH_LO


def test_CRDO_passes_the_moment_the_arrival_band_meets_the_IMPORTED_bar():
    fixed = [dict(b) for b in CRDO_WINDOW]
    fixed[1]["touches"] = DR.MIN_TOUCHES                    # constants by name, never literals
    fixed[1]["strength"] = DR.MIN_ZONE_STRENGTH
    r = DL.arrival_read(CRDO_PX, fixed)
    assert r["levels_broken"] == 1 and r["level"] == 2
    assert r["arr_gate_pass"] is True
    assert DL.touches_bucket(r["arr_touches"]) == DL.TOUCH_MIN_LABEL
    assert DL.strength_side(r["arr_strength"]) == DL.STRENGTH_HI


def test_the_gate_column_is_read_itself_and_is_never_a_depth_refusal():
    """A 3-level arrival is too deep for the shipped screen, but its BAND is
    perfectly good — `arr_gate_pass` must say so, or Q2 would read the depth cap
    as a quality failure."""
    dz = [_band(160, 164), _band(150, 154), _band(140, 144),
          _band(130, 134, touches=4, strength=90.0)]
    r = DL.arrival_read(132.0, dz)
    assert r["levels_broken"] is None                       # refused on DEPTH
    assert r["arr_gate_pass"] is True                       # but the band is fine


# ═════════════════════════════════════════════════════════════════════════════
# 4 — the cell assigners, with the negatives that matter
# ═════════════════════════════════════════════════════════════════════════════
def test_levels_bucket_table():
    assert DL.levels_bucket(1) == "1"
    assert DL.levels_bucket(2) == "2"
    assert DL.levels_bucket(3) == "3"
    assert DL.levels_bucket(4) == DL.LEVELS_DEEPEST == "4+"
    assert DL.levels_bucket(9) == DL.LEVELS_DEEPEST


def test_NEGATIVE_a_non_arrival_is_never_a_depth_of_zero():
    for v in (None, np.nan, 0, -1, "junk"):
        assert DL.levels_bucket(v) == DL.LEVELS_NONE
    assert "0" not in DL.LEVELS_ORDER
    assert DL.LEVELS_NONE in DL.LEVELS_ORDER


def test_touches_bucket_uses_the_imported_cut():
    assert DL.touches_bucket(1) == DL.TOUCH_UNDER_LABEL
    assert DL.touches_bucket(DR.MIN_TOUCHES) == DL.TOUCH_MIN_LABEL
    assert DL.touches_bucket(DR.MIN_TOUCHES + 1) == DL.TOUCH_OVER_LABEL
    assert DL.touches_bucket(DR.MIN_TOUCHES + 7) == DL.TOUCH_OVER_LABEL


def test_NEGATIVE_a_missing_touch_count_is_its_own_bucket():
    for v in (None, np.nan, "", "n/a"):
        assert DL.touches_bucket(v) == DL.TOUCH_NA
    assert DL.TOUCH_NA not in (DL.TOUCH_UNDER_LABEL, DL.TOUCH_MIN_LABEL, DL.TOUCH_OVER_LABEL)


def test_strength_side_splits_on_the_imported_cut_exactly():
    assert DL.strength_side(DR.MIN_ZONE_STRENGTH) == DL.STRENGTH_HI       # at the cut = kept
    assert DL.strength_side(DR.MIN_ZONE_STRENGTH - 0.01) == DL.STRENGTH_LO
    assert DL.strength_side(DR.MIN_ZONE_STRENGTH + 50) == DL.STRENGTH_HI


def test_NEGATIVE_a_MISSING_strength_is_its_own_bucket_never_counted_as_below_the_cut():
    for v in (None, np.nan, "", "None"):
        assert DL.strength_side(v) == DL.STRENGTH_NA
        assert DL.strength_side(v) != DL.STRENGTH_LO
    assert DL.STRENGTH_NA in DL.STRENGTH_ORDER


def test_bucket_columns_leave_quality_cells_EMPTY_when_there_was_no_arrival():
    r = DL.arrival_read(100.0, [_band(200, 204), _band(190, 194)])   # in the air below both
    cols = DL.bucket_columns(r)
    assert cols["levels_bucket"] == DL.LEVELS_NONE
    assert cols["arr_touches_bucket"] is None and cols["arr_strength_side"] is None


def test_ship_eligibility_refuses_the_uncapped_control():
    ok, why = DL.ship_eligible_feature("levels_bucket")
    assert ok is True and "served" in why
    for feat in ("levels_bucket_all", "levels_broken_all", "arrival_within_cap"):
        ok, why = DL.ship_eligible_feature(feat)
        assert ok is False and "uncapped" in why
    assert DL.ship_eligible_feature("something_else")[0] is False


# ═════════════════════════════════════════════════════════════════════════════
# 5 — cells_table: hit5 first, and an UNDER-FLOOR cell carries no rates
# ═════════════════════════════════════════════════════════════════════════════
def _cell_frame(counts: dict, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2025-01-02", periods=200)]
    rows = []
    for name, n in counts.items():
        for _ in range(n):
            R = float(rng.normal(0.2, 1.0))
            rows.append({"symbol": "S%03d" % rng.integers(0, 200),
                         "date": dates[int(rng.integers(0, 200))],
                         "levels_bucket": name, "clear": False,
                         "room_pct": 12.0, "risk_pct": 2.5,
                         "hit5_5": 0.0, "hit5_10": 0.0,
                         "hit5_20": float(rng.uniform() < 0.34),
                         "hit5b_20": 0.0, "hit_lid_20": 0.0,
                         "stop_20": float(rng.uniform() < 0.74),
                         "R20": R, "why20": "clock", "hit5c_20": 0.0})
    return pd.DataFrame(rows)


_CONV = ES.conventions("hit5", HOLD)["P"]


def test_cells_table_reports_hit5_with_stop_R_and_win_beside_it():
    D = _cell_frame({"1": 400, "2": 300})
    cells = DL.cells_table(D, "levels_bucket", DL.LEVELS_ORDER, _CONV, CLOCKS, HOLD)
    assert [c["cell"] for c in cells] == ["1", "2"]            # the DECLARED order
    for c in cells:
        assert c["shown"] is True
        for k in ("hit5_20", "stop_20", "R20", "R20_median", "win20"):
            assert k in c and c[k] == c[k]


def test_NEGATIVE_a_cell_under_the_floor_reads_not_shown_and_carries_no_rates():
    D = _cell_frame({"1": 400, "3": DL.MIN_CELL_N - 1})
    cells = {c["cell"]: c for c in
             DL.cells_table(D, "levels_bucket", DL.LEVELS_ORDER, _CONV, CLOCKS, HOLD)}
    thin = cells["3"]
    assert thin["shown"] is False
    assert thin["note"] == "n<%d — not shown" % DL.MIN_CELL_N
    for k in ("hit5_20", "stop_20", "R20", "win20"):
        assert k not in thin                                   # no rate may leak out of it
    assert cells["1"]["shown"] is True


def test_NEGATIVE_a_label_the_cohort_never_saw_is_absent_not_zero():
    D = _cell_frame({"1": 300})
    cells = DL.cells_table(D, "levels_bucket", DL.LEVELS_ORDER, _CONV, CLOCKS, HOLD)
    assert [c["cell"] for c in cells] == ["1"]
    assert DL.cell_order(D, "levels_bucket", DL.LEVELS_ORDER) == ["1"]
    assert DL.cells_table(D, "not_a_column", DL.LEVELS_ORDER, _CONV, CLOCKS, HOLD) == []


# ═════════════════════════════════════════════════════════════════════════════
# 6 — the stats stage runs with no Mongo, and the CLI parses
# ═════════════════════════════════════════════════════════════════════════════
def _synthetic_events(n_sym: int = 90, n_ev: int = 10, seed: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2025-01-02", periods=420)]
    rows = []
    for s in range(n_sym):
        sym = "SYM%03d" % s
        for e in range(n_ev):
            j = 140 + e * 21
            entry = float(rng.uniform(8, 300))
            stop = entry * 0.97
            target = entry * 1.18
            hit = float(rng.uniform() < 0.34)
            stp = float(rng.uniform() < 0.74)
            why = "stop" if stp else ("target" if hit else "clock")
            R = float(rng.normal(0.2, 1.1))
            n_lv = int(rng.choice([0, 1, 2, 3], p=[0.55, 0.25, 0.14, 0.06]))
            arrived = n_lv >= 1
            touches = int(rng.choice([1, 2, 3, 5])) if arrived else None
            strength = float(rng.uniform(5, 95)) if arrived else None
            ar = {"levels_broken": (n_lv if (arrived and n_lv <= DD.MAX_LEVELS_BROKEN)
                                    else None),
                  "levels_broken_all": n_lv if arrived else None,
                  "arr_touches": touches, "arr_strength": strength}
            row = {"symbol": sym, "date": dates[j - 130], "bar_idx": j,
                   "dir": rng.choice(["bouncing", "falling"], p=[0.78, 0.22]),
                   "entry": entry, "stop": stop, "target": target, "clear": False,
                   "room_pct": (target / entry - 1) * 100,
                   "risk_pct": (entry - stop) / entry * 100,
                   "R": R, "why": why, "dvol50_pre": rng.lognormal(16, 1.5),
                   "band_lo": stop / 0.995, "band_hi": stop / 0.995 * 1.02,
                   "gap_N": rng.uniform() < 0.05,
                   "risk_pct_N": (entry - stop) / entry * 100, "entry_N": entry,
                   "n_window": 4,
                   "level": (ar["levels_broken"] + 1) if ar["levels_broken"] else None,
                   "arrival_within_cap": (bool(n_lv <= DD.MAX_LEVELS_BROKEN)
                                          if arrived else None),
                   "deep_state": ("in" if arrived else None),
                   "arr_lo": stop / 0.995 if arrived else np.nan,
                   "arr_hi": stop / 0.995 * 1.02 if arrived else np.nan,
                   "arr_height_pct": rng.uniform(1.0, 8.0) if arrived else np.nan,
                   "arr_dist_pct": 0.0 if arrived else np.nan,
                   "arr_gate_pass": (bool((touches or 0) >= DR.MIN_TOUCHES
                                          and (strength or 0) >= DR.MIN_ZONE_STRENGTH)
                                     if arrived else None),
                   "max_gain_pct_20": rng.uniform(0, 12),
                   "hit5c_20": hit, "hit5c_20_N": hit}
            row.update(ar)
            row.update(DL.bucket_columns(ar))
            for cl in CLOCKS:
                row["hit5_%d" % cl] = hit
                row["hit5b_%d" % cl] = hit
                row["hit_lid_%d" % cl] = float(why == "target")
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
    DL.main(["--stage", "stats", "--from-csv", str(csv), "--json", str(out),
             "--boot-draws", "150", "--perm-draws", "60", "--placebo-draws", "60"]
            + list(extra))
    return json.load(open(out))


def test_stats_stage_runs_without_mongo_and_writes_every_measured_key(tmp_path):
    csv = _write(tmp_path, _synthetic_events())
    m = _run(csv, tmp_path / "m.json")
    for k in ("run_date", "script", "quotable", "n_episodes", "n_dates", "window",
              "cap_note", "gate_note", "base", "q1", "q2", "survivorship", "status",
              "fallback", "max_zones_read", "max_levels_shipped", "min_touches",
              "min_zone_strength"):
        assert k in m, k
    assert m["script"] == DL.SCRIPT
    assert m["min_touches"] == DR.MIN_TOUCHES
    assert m["min_zone_strength"] == DR.MIN_ZONE_STRENGTH
    assert m["max_levels_shipped"] == DD.MAX_LEVELS_BROKEN
    for q in ("q1", "q2"):
        blk = m[q]
        assert blk["status"] in ("separates", "no_signal")
        assert set(blk["splits"]) == {"s1", "s2", "s3"}
    assert {c["cell"] for c in m["q1"]["cells"]} <= set(DL.LEVELS_ORDER)
    assert m["q2"]["gate"]["note"] == DL.GATE_NOTE
    assert "MAX_ZONES_PER_SIDE" in m["cap_note"]


def test_the_primary_outcome_is_hit5_at_the_hold_with_stop_R_and_win_beside_it(tmp_path):
    csv = _write(tmp_path, _synthetic_events(seed=6))
    m = _run(csv, tmp_path / "m.json")
    assert m["primary_outcome"] == "hit5" and m["hold"] == HOLD
    for k in ("hit5_20", "stop_20", "R20", "R20_median", "R20_trim", "win20"):
        assert k in m["base"]
    for c in m["q1"]["cells"]:
        if c.get("shown"):
            assert {"hit5_20", "stop_20", "R20", "win20"} <= set(c)


def test_NEGATIVE_a_strided_run_is_never_quotable_and_says_why(tmp_path, capsys):
    csv = _write(tmp_path, _synthetic_events(seed=8), stride=2)
    m = _run(csv, tmp_path / "m.json", extra=["--stride", "2"])
    assert "NOT QUOTABLE" in capsys.readouterr().out
    assert m["quotable"] is False
    assert m["not_quotable_reason"] == DL.SUBSAMPLE_NOT_QUOTABLE


def test_NEGATIVE_without_the_survivorship_replay_the_run_is_not_quotable(tmp_path, capsys):
    csv = _write(tmp_path, _synthetic_events(seed=10))
    m = _run(csv, tmp_path / "m.json")
    assert m["quotable"] is False
    assert m["not_quotable_reason"] == DL.SURVIVORSHIP_MISSING
    assert DL.SURVIVORSHIP_MISSING in capsys.readouterr().out


def test_block_status_needs_a_ship_eligible_feature_on_all_three_splits():
    sep = {"verdict": "separates"}
    blk = {"per_feature": [{"name": "levels_bucket", "ship_eligible": True,
                            "top": {"verdict": "separates"}}],
           "conditional": {},
           "splits": {"s1": dict(sep, mdl=1.0), "s2": dict(sep, mdl=1.2),
                      "s3": dict(sep, mdl=0.9)}}
    status, sel, mdl = DL.block_status(blk)
    assert status == "separates" and sel == ["levels_bucket"] and mdl == 1.2
    # NEGATIVE — the uncapped control can never carry a question
    blk2 = dict(blk, per_feature=[{"name": "levels_bucket_all", "ship_eligible": False,
                                   "top": {"verdict": "separates"}}])
    assert DL.block_status(blk2)[0] == "no_signal"
    # NEGATIVE — one split that does not separate sinks it
    blk3 = dict(blk, splits=dict(blk["splits"], s2={"verdict": "no_signal", "mdl": 2.0}))
    assert DL.block_status(blk3)[0] == "no_signal"


def test_the_cli_parses_every_stage_and_refuses_stats_with_no_csv(capsys):
    with pytest.raises(SystemExit):
        DL.main(["--stage", "stats"])
    assert "--from-csv" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        DL.main(["--stage", "nonsense"])


def test_wanted_columns_cover_every_read_the_stats_stage_makes():
    cols = set(DL.wanted_columns(CLOCKS, HOLD, "hit5"))
    conv = ES.conventions("hit5", HOLD)
    for c in conv["P"].values():
        if isinstance(c, str) and c.startswith(("hit5", "stop_", "R2", "why2")):
            assert c in cols, c
    for name in DL.DEPTH_FEATS + DL.QUALITY_FEATS + DL.EXPLORATORY:
        assert name in cols, name
    for name in ("symbol", "date", "dir", "entry", "stop", "target", "room_pct", "clear",
                 "risk_pct", "episode_dir", "dvol50_pre", "gap_N"):
        assert name in cols, name


# ═════════════════════════════════════════════════════════════════════════════
# 7 — the served read: MEASURED = None is PENDING, and nothing quotes it
# ═════════════════════════════════════════════════════════════════════════════
def test_MEASURED_is_pending_and_nothing_is_quotable_from_it():
    assert DLM.MEASURED is None
    assert DLM.status() == DLM.STATUS_PENDING == "pending"
    assert DLM.quotable() is False
    assert DLM.separates() is False
    assert DLM.note() == DLM.NOT_MEASURED_NOTE


def test_NEGATIVE_the_pending_note_never_claims_an_edge():
    txt = DLM.note().lower()
    for word in ("edge", "outperform", "better", "wins", "bounce"):
        assert word not in txt
    assert "not measured" in txt


def test_NEGATIVE_a_malformed_or_unquotable_MEASURED_fails_closed(monkeypatch):
    for bad in ({}, {"status": "great"}, {"status": None}, [], "separates", 0):
        monkeypatch.setattr(DLM, "MEASURED", bad)
        assert DLM.status() == DLM.STATUS_PENDING
        assert DLM.separates() is False
    # a `separates` run that is NOT quotable still may not be ordered on
    monkeypatch.setattr(DLM, "MEASURED", {"status": "separates", "quotable": False})
    assert DLM.status() == "separates" and DLM.separates() is False
    assert DLM.note() == DLM.NOT_MEASURED_NOTE
    # no_signal reads exactly like pending
    monkeypatch.setattr(DLM, "MEASURED", {"status": "no_signal", "quotable": True})
    assert DLM.note() == DLM.NOT_MEASURED_NOTE


def test_the_measured_module_carries_no_number_of_its_own():
    src = open(DLM.__file__).read()
    body = src.split('"""', 2)[-1]
    assert "MEASURED: Optional[dict] = None" in body
    assert re.search(r"MEASURED\s*=\s*\{", body) is None
