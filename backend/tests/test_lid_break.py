"""Last-lid break → prior-high study (supply_demand/lid_break.py).

Ajay 2026-09-07: "I would like to understand when the last resistance break will
the price go to ATH." Synthetic frames: the rules are pinned on shapes whose
answer is known by construction — no market data, no lookahead.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import lid_break as LB          # noqa: E402
from supply_demand import alert_gates as AG        # noqa: E402


def _dates(n, start="2024-01-02"):
    d0 = date.fromisoformat(start)
    return [(d0 + timedelta(days=i)).isoformat() for i in range(n)]


def _frame(closes, highs=None, lows=None, opens=None, vols=None):
    n = len(closes)
    highs = highs or [c * 1.01 for c in closes]
    lows = lows or [c * 0.99 for c in closes]
    opens = opens or list(closes)
    vols = vols or [1_000_000] * n
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes,
                         "volume": vols}, index=pd.to_datetime(_dates(n)))


def _bars(closes, highs=None):
    highs = highs or [c * 1.01 for c in closes]
    return {"open": list(closes), "high": highs, "low": [c * 0.99 for c in closes],
            "close": list(closes)}


# ── pure helpers ─────────────────────────────────────────────────────────────
def test_last_lid_is_the_highest_valid_supply_band_overhead():
    bands = [{"kind": "supply", "lo": 90, "hi": 92, "touches": 2, "strength": 50},
             {"kind": "supply", "lo": 100, "hi": 103, "touches": 3, "strength": 60},
             {"kind": "supply", "lo": 110, "hi": 112, "touches": 1, "strength": 20},
             {"kind": "demand", "lo": 120, "hi": 125, "touches": 4, "strength": 90},
             {"kind": "supply", "lo": None, "hi": 130}]
    assert LB.last_lid(bands, 95)["hi"] == 112          # highest supply overhead, demand ignored
    assert LB.last_lid(bands, 113) is None               # nothing overhead
    assert LB.last_lid([], 10) is None


def test_prior_high_excludes_the_bar_itself():
    highs = [1, 5, 2, 9, 3]
    assert LB.prior_high(highs, 3, 252) == 5             # bar 3 (=9) excluded
    assert LB.prior_high(highs, 0, 252) is None


def test_reach_within_counts_sessions_and_marks_an_unresolved_tail():
    highs = [10, 10, 12, 10, 10]
    assert LB.reach_within(highs, 0, 12, 3) == 2
    assert LB.reach_within(highs, 0, 13, 3) is None      # resolved: never reached
    assert LB.reach_within(highs, 3, 13, 5) == -1        # frame ends first: unknown


def test_dist_buckets():
    assert LB.dist_bucket(3.0) == "≤5%" and LB.dist_bucket(5.0) == "≤5%"
    assert LB.dist_bucket(9.9) == "5–15%" and LB.dist_bucket(40.0) == ">15%"
    assert LB.dist_bucket(None) is None


def test_outcome_reads_hit_runup_and_fail_from_the_break_close():
    # break at i=2 (close 101 over lid 100); 52w high 110 hit on day 4 (high 111);
    # frame high 120 never; close back under the lid on day 6.
    closes = [95, 99, 101, 104, 108, 103, 99, 100, 100, 100]
    highs = [96, 100, 102, 105, 111, 104, 100, 101, 101, 101]
    out = LB.outcome(_bars(closes, highs), 2, 100.0, 110.0, 120.0)
    assert out["at_52w"] is False and out["dist_to_52w_pct"] == pytest.approx(8.91, abs=0.01)
    assert out["hit_52w_5"] is True and out["days_to_52w_5"] == 2
    assert out["hit_frame_5"] is False
    assert out["max_runup_5_pct"] == pytest.approx((111 - 101) / 101 * 100, abs=0.01)
    assert out["failed_21"] is True and out["days_to_fail"] == 4
    assert out["resolved_5"] is True and out["resolved_63"] is False


def test_outcome_at_the_52w_high_makes_the_52w_question_moot():
    closes = [95, 99, 101, 104, 108]
    out = LB.outcome(_bars(closes), 2, 100.0, 100.2, 130.0)
    assert out["at_52w"] is True and out["dist_to_52w_pct"] is None
    assert out["hit_52w_5"] is None and out["days_to_52w_5"] is None


def test_placebo_counts_every_day_under_its_own_prior_high():
    # flat tape whose highs equal its closes: no day sits UNDER its prior high → no days
    flat = {"open": [100.0] * 320, "high": [100.0] * 320, "low": [99.0] * 320, "close": [100.0] * 320}
    assert LB.placebo(flat, 270, 300, 21) == (0, 0)
    # closes 99.5 under a flat 101 prior high, then a 3-day run: only the days whose
    # 21-session window reaches the run (the last 21 of the 30) count as hits …
    closes = [99.5] * 300 + [102.0, 104.0, 105.0]
    highs = [101.0] * 300 + [103.0, 105.0, 106.0]
    bars = {"open": closes, "high": highs, "low": [c - 1 for c in closes], "close": closes}
    hits, days = LB.placebo(bars, 270, 300, 21)
    assert days == 30 and hits == 30                     # every day: tomorrow's high 101 ≥ prior high 101
    # … so the honest placebo needs highs that do NOT re-touch the prior high daily
    highs2 = [101.0] * 30 + [100.0] * 270 + [103.0, 105.0, 106.0]
    bars2 = {"open": closes, "high": highs2, "low": [c - 1 for c in closes], "close": closes}
    hits2, days2 = LB.placebo(bars2, 270, 300, 21)
    assert days2 == 30 and hits2 == 21                   # only the last 21 windows see the run
    hits_up, days_up = LB.placebo(bars2, 270, 300, 21, up_only=True)
    assert days_up == 0                                  # flat closes: no up-days


# ── one name, end to end ─────────────────────────────────────────────────────
def _compute_lid(hi, lo=None, touches=3, strength=60.0):
    def compute(hist):
        return {"supply_zones": [{"kind": "supply", "lo": lo if lo is not None else hi - 2,
                                  "hi": hi, "touches": touches, "strength": strength}],
                "demand_zones": []}
    return compute


def test_study_symbol_finds_the_break_and_the_run_to_the_prior_high():
    # 252 warm-up bars at 100 with an old spike high of 120 at bar 30 (the 52w high),
    # lid at 105; the break comes at bar 262, the high 120 is reached at bar 270.
    n = 340
    closes = [100.0] * n
    highs = [101.0] * n
    highs[30] = 120.0
    for k, i in enumerate(range(262, 275)):
        closes[i] = 106.0 + k * 1.5
        highs[i] = closes[i] + 1.0
    highs[270] = 121.0
    for i in range(275, n):
        closes[i] = 118.0
        highs[i] = 119.0
    df = _frame(closes, highs)
    stats, events = LB.study_symbol(df, "T", compute=_compute_lid(105.0))
    assert len(events) == 1
    ev = events[0]
    assert ev["date"] == str(df.index[262])[:10] and ev["lid_hi"] == 105.0
    assert ev["proven"] is True and ev["at_52w"] is False
    assert ev["high_252"] == 120.0 and ev["hit_52w_21"] is True and ev["days_to_52w_21"] == 8
    assert ev["failed_21"] is False
    assert stats["events"] == 1 and stats["hit_52w_21_pct"] == 100.0 and stats["failed_21_pct"] == 0.0
    assert stats["placebo_any_21_n"] > 0                 # the base rate rides along


def test_study_symbol_records_a_failed_break():
    n = 340
    closes = [100.0] * n
    highs = [101.0] * n
    highs[30] = 120.0
    closes[262] = 106.0; highs[262] = 107.0
    closes[263] = 103.0; highs[263] = 106.5             # back under the lid next day
    df = _frame(closes, highs)
    stats, events = LB.study_symbol(df, "F", compute=_compute_lid(105.0))
    assert len(events) == 1 and events[0]["failed_21"] is True and events[0]["days_to_fail"] == 1
    assert events[0]["hit_52w_21"] is False and stats["failed_21_pct"] == 100.0


def test_single_touch_lid_is_split_from_proven():
    n = 340
    closes = [100.0] * n
    highs = [101.0] * n
    closes[262] = 106.0; highs[262] = 107.0
    df = _frame(closes, highs)
    _, events = LB.study_symbol(df, "S", compute=_compute_lid(105.0, touches=1, strength=20.0))
    assert events and events[0]["proven"] is False
    assert AG.LID_MIN_TOUCHES == 2                       # the bar the split uses


def test_volume_confirmation_uses_the_fifty_day_average():
    n = 340
    closes = [100.0] * n
    highs = [101.0] * n
    vols = [1_000_000] * n
    vols[262] = 1_600_000
    closes[262] = 106.0; highs[262] = 107.0
    df = _frame(closes, highs, vols=vols)
    _, events = LB.study_symbol(df, "V", compute=_compute_lid(105.0))
    assert events[0]["vol_ratio"] == 1.6 and events[0]["vol_confirmed"] is True


def test_no_lid_overhead_means_no_event():
    n = 300
    closes = [100.0] * n
    closes[262] = 106.0
    df = _frame(closes)
    stats, events = LB.study_symbol(df, "N", compute=_compute_lid(95.0))    # lid under the anchor close
    assert events == [] and stats["events"] == 0


def test_short_history_is_skipped():
    assert LB.study_symbol(_frame([100.0] * 100), "X") is None


def test_bands_are_computed_on_bars_before_the_anchor_only():
    seen = []

    def compute(hist):
        seen.append(len(hist))
        return {"supply_zones": [], "demand_zones": []}
    LB.study_symbol(_frame([100.0] * 320), "A", compute=compute)
    assert seen and seen[0] == LB.MIN_HISTORY_BARS + 1 and all(s <= 320 for s in seen)


# ── the run, pooled ──────────────────────────────────────────────────────────
def test_run_pools_splits_placebo_and_persists(monkeypatch):
    n = 340
    closes = [100.0] * n
    highs = [101.0] * n
    highs[30] = 120.0
    for k, i in enumerate(range(262, 275)):
        closes[i] = 106.0 + k * 1.5
        highs[i] = closes[i] + 1.0
    highs[270] = 121.0
    for i in range(275, n):
        closes[i] = 118.0                                # holds above the lid: no fail
        highs[i] = 119.0
    good = _frame(closes, highs)
    bad_h = [101.0] * 262 + [107.0, 104.0] + [101.0] * (n - 264)
    bad_h[30] = 120.0                                    # same old high: the lid is UNDER the 52w high
    bad = _frame([100.0] * 262 + [106.0, 103.0] + [100.0] * (n - 264), bad_h)
    frames = {"GOOD": good, "BAD": bad, "SHORT": _frame([100.0] * 50)}
    res = LB.run(["GOOD", "BAD", "SHORT"], load=lambda s: frames.get(s), compute=_compute_lid(105.0))
    m = res["meta"]
    assert m["studied"] == 2 and m["skipped"] == 1 and m["names_with_events"] == 2
    assert m["pooled"]["events"] == 2 and m["pooled"]["hit_52w_21_pct"] == 50.0
    assert m["pooled"]["failed_21_pct"] == 50.0
    assert m["splits"]["proven"]["events"] == 2 and m["splits"]["single_touch"]["events"] == 0
    assert "any_21" in m["placebo"] and "up_21" in m["placebo"]
    assert m["params"]["lid_min_touches"] == AG.LID_MIN_TOUCHES

    class Coll:
        def __init__(self):
            self.docs = {}

        def replace_one(self, q, doc, upsert=False):
            self.docs[q["_id"]] = doc

        def find(self, q):
            ids = q.get("_id") or {}
            for k, d in self.docs.items():
                if k == LB.META_ID:
                    continue
                if "$in" in ids and k not in ids["$in"]:
                    continue
                yield d

        def find_one(self, q):
            return self.docs.get(q["_id"])
    coll = Coll()
    assert LB.save(res, coll=coll) == 2
    assert set(LB.load_stats(["GOOD"], coll=coll)) == {"GOOD"}
    bm = LB.board_meta(LB.load_meta(coll=coll))
    assert bm["events"] == 2 and bm["hit_52w_21_pct"] == 50.0 and "frame high" in bm["disclaimer"]


def test_card_stat_text():
    assert LB.card_stat(None) is None
    assert LB.card_stat({"events": 0}) is None
    s = LB.card_stat({"events": 3, "hit_52w_21_pct": 66.7, "hit_52w_21_n": 3, "failed_21_pct": 33.3})
    assert s == "3 breaks · 67% → 52w in 21d (n=3) · 33% back under in 21d"


def test_study_is_scheduled_weekly_after_quick_bounce():
    cron = (Path(__file__).resolve().parents[2] / "backend" / "crontab").read_text()
    lines = [l for l in cron.splitlines() if "supply_demand.lid_break" in l and not l.startswith("#")]
    assert len(lines) == 1 and lines[0].split()[:5] == ["30", "7", "*", "*", "0"]
    assert LB.STUDY_CRON == "30 7 * * 0"
