"""Quick Bounce (Ajay 2026-09-06): "touched the demand zone and bounced in the
same day ... or sometimes overnight down and gapped up on the morning".
Pure event rules on synthetic bars, the list rule on synthetic docs, the
persistence check, and the run() plumbing with an injected loader — no
Mongo, no provider."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import quick_bounce as QB          # noqa: E402
from supply_demand import alert_gates as AG           # noqa: E402

BAND = {"kind": "demand", "lo": 164.60, "hi": 169.81, "touches": 3, "strength": 100.0}


def _bars(rows):
    """rows = [(open, high, low, close)] -> the dict shape the rules read."""
    return {"open": [r[0] for r in rows], "high": [r[1] for r in rows],
            "low": [r[2] for r in rows], "close": [r[3] for r in rows]}


def _dates(n, start="2026-01-02"):
    d0 = date.fromisoformat(start)
    return [(d0 + timedelta(days=i)).isoformat() for i in range(n)]


def test_atr_series_uses_only_bars_up_to_each_bar():
    highs = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]
    lows = [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24]
    closes = [9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5, 17.5, 18.5, 19.5, 20.5, 21.5, 22.5, 23.5, 24.5]
    atr = QB.atr_series(highs, lows, closes)
    assert atr[:13] == [None] * 13
    assert atr[13] == pytest.approx((1.0 + 13 * 1.5) / 14), "bar 0's range is 1, every later true range 1.5"
    assert atr[15] == pytest.approx(1.5)
    assert QB.lift_floor_pct(100.0, 2.0) == 3.0, "a 2% ATR is under the 3% floor"
    assert QB.lift_floor_pct(100.0, 4.5) == 4.5 and QB.lift_floor_pct(100.0, None) == 3.0
    assert QB.lift_floor_pct(0.0, 4.5) == QB.BOUNCE_MIN_PCT


def test_touch_geometry_is_the_bounce_alerts_own():
    assert QB.is_touch(169.81 * 1.01, BAND) is True and QB.is_touch(169.81 * 1.011, BAND) is False
    assert QB.is_touch(164.60 * 0.985, BAND) is True and QB.is_touch(164.60 * 0.984, BAND) is False


def test_quick_day_same_day_lift_or_next_morning_gap():
    bars = _bars([(170, 173, 167.0, 173.0),       # +3.6% off the low: same_day
                  (170, 171, 167.0, 168.0),       # weak close ...
                  (172.9, 175, 172, 174),         # ... next open +2.9%: gap_up for bar 1
                  (168, 169, 167.0, 168.5)])      # nothing, and no next bar
    assert QB.quick_day(bars, 0, 4.0) == "same_day"
    assert QB.quick_day(bars, 0, 8.0) is None, "an 8-point ATR (4.8%) raises the floor over 3.6%"
    assert QB.quick_day(bars, 1, 3.0) == "gap_up"
    assert QB.quick_day(bars, 3, 3.0) is None
    assert QB.quick_day(_bars([(1, 1, 0, 1)]), 0, 1.0) is None, "a zero low is not a print"


def test_klac_shape_three_touch_days_then_the_gap_is_one_quick_episode():
    # Sep 1-3 inside the band (weak closes), Sep 4 opens +2.9% -> quick on touch day 3.
    rows = [(175, 176, 174, 175.5)] * 3 + [
        (171.8, 173.0, 168.07, 172.3),   # day 1 touch, +2.5% off the low (under the ATR floor)
        (171.8, 173.0, 167.56, 172.26),  # day 2 touch
        (169.5, 173.1, 167.05, 172.94),  # day 3 touch, +3.5% (ATR ~6 -> floor 3.6%): not same_day
        (177.9, 187.4, 173.5, 185.6),    # gap +2.9% -> gap_up
        (186, 188, 184, 187)]
    bars = _bars(rows)
    atrs = [6.0] * len(rows)
    evs = QB.episodes_for_band(bars, atrs, BAND, 0, len(rows), _dates(len(rows)))
    assert len(evs) == 1
    e = evs[0]
    assert e["touch_days"] == 3 and e["outcome"] == "quick" and e["kind"] == "gap_up"
    assert e["quick_day"] == 3 and e["first_day_quick"] is False and e["gap_pct"] == 2.87
    # the same visit with a 4-day rule-window still counts; with a 2-day window it is NOT quick
    old = QB.QUICK_MAX_TOUCH_DAYS
    try:
        QB.QUICK_MAX_TOUCH_DAYS = 2
        e2 = QB.episodes_for_band(bars, atrs, BAND, 0, len(rows), _dates(len(rows)))[0]
        assert e2["outcome"] == "slow" and e2["bars_to_bounce"] == 1, "the +7% close the next bar is a slow bounce"
    finally:
        QB.QUICK_MAX_TOUCH_DAYS = old


def test_episode_joins_a_one_day_gap_and_splits_on_two():
    touch = (168, 170, 167.0, 168.5)
    away = (174, 175, 173.0, 174.5)          # low 173 > 169.81 x 1.01: not a touch
    rows = [touch, away, touch, away, away, touch, (180, 181, 179, 180.5)]
    bars = _bars(rows)
    evs = QB.episodes_for_band(bars, [2.0] * len(rows), BAND, 0, len(rows), _dates(len(rows)))
    assert [e["touch_days"] for e in evs] == [2, 1], "day 0+2 join across one non-touch day; day 5 is a new visit"
    assert [e["kind"] for e in evs] == ["gap_up", "gap_up"], "each visit's next open is 3%+ over its close"


def test_failed_and_slow_outcomes_follow_sd_bounce_rules():
    closes = [168.5, 169.0, 162.0, 175.0]                    # closes under the floor first
    assert QB.slow_outcome(closes, 0, 164.60) == {"bounced": False, "bars_to_bounce": None, "broke": True}
    closes = [168.5, 169.0, 170.0, 172.5]                    # +2.4% on bar 3
    assert QB.slow_outcome(closes, 0, 164.60) == {"bounced": True, "bars_to_bounce": 3, "broke": False}
    assert QB.slow_outcome(closes, 3, 164.60)["bounced"] is False


def test_placebo_counts_every_day_the_same_way():
    rows = [(100, 104, 99, 103.5), (100, 101, 99.5, 100.0), (103, 104, 102, 103.5), (100, 101, 99, 100.2)]
    bars = _bars(rows)
    assert QB.placebo_days(bars, [1.0] * 4, 0, 4) == (2, 4)  # bar 0 lifts 4.5%; bar 1 gaps +3%


def test_summarize_and_qualifies():
    evs = [{"i": 1, "date": "2026-02-01", "outcome": "quick", "kind": "same_day", "quick_day": 1,
            "first_day_quick": True, "lift_pct": 4.0, "touch_days": 1, "band_lo": 1, "band_hi": 2, "touches": 2},
           {"i": 5, "date": "2026-03-01", "outcome": "quick", "kind": "gap_up", "quick_day": 2,
            "first_day_quick": False, "lift_pct": 1.0, "touch_days": 2, "band_lo": 1, "band_hi": 2, "touches": 2},
           {"i": 9, "date": "2026-04-01", "outcome": "failed", "kind": None, "quick_day": None,
            "first_day_quick": False, "lift_pct": None, "touch_days": 1, "band_lo": 1, "band_hi": 2, "touches": 2}]
    s = QB.summarize("X", evs, 10, 100)
    assert (s["events"], s["quick"], s["same_day"], s["gap_up"], s["first_day_quick"], s["failed"]) == (3, 2, 1, 1, 1, 1)
    assert s["quick_rate_pct"] == 66.7 and s["first_day_rate_pct"] == 33.3 and s["placebo_rate_pct"] == 10.0
    assert s["edge_pts"] == 56.7 and s["median_lift_pct"] == 4.0 and s["last_quick_date"] == "2026-03-01"
    assert QB.qualifies(s) is True
    assert QB.qualifies(dict(s, events=2)) is False, "under MIN_EVENTS"
    assert QB.qualifies(dict(s, quick_rate_pct=49.9)) is False and QB.qualifies(None) is False
    assert QB.summarize("E", [], 0, 0)["quick_rate_pct"] is None
    assert (QB.MIN_EVENTS, QB.MIN_QUICK_RATE_PCT, QB.NEAR_MAX_PCT, QB.GAP_MIN_PCT, QB.QUICK_MAX_TOUCH_DAYS) == (3, 50.0, 5.0, 2.0, 3)
    assert QB.ROOM_MIN_PCT == AG.ALERT_MIN_ROOM_PCT == 5.0 and QB.STOP_BUFFER_PCT == AG.STOP_BUFFER_PCT


def test_persistence_ranks_on_the_first_half_and_judges_on_the_second():
    def evs(sym, dates, quick_flags):
        return [{"date": d, "outcome": "quick" if q else "failed"} for d, q in zip(dates, quick_flags)]
    dates = _dates(8, "2026-01-01")
    per = {}
    for k in range(12):                                   # 12 names, 8 events each
        good = k < 6
        per["S%d" % k] = evs("S%d" % k, dates, [good] * 4 + [good] * 4)   # a stable character
    p = QB.persistence(per)
    assert p["names"] == 12 and p["quartile"] == 3
    assert p["top_q_second_half_pct"] == 100.0 and p["bottom_q_second_half_pct"] == 0.0
    assert p["gap_pts"] == 100.0 and p["rank_corr"] == pytest.approx(1.0, abs=0.05)
    assert "note" in QB.persistence({"A": evs("A", dates[:2], [True, True])})
    assert QB.persistence({}) == {"names": 0, "note": "too few events"}


def test_run_with_an_injected_loader_and_zone_compute():
    n = QB.MIN_HISTORY_BARS + 30
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    rows = [(180, 181, 179.5, 180.5)] * (n - 8) + [
        (170, 172, 167.0, 171.5),       # touch, +2.7% — under the 3% floor (ATR tiny)
        (173.9, 175, 173, 174),         # gap +1.5%: no -> slow/failed path
        (174, 176, 173.5, 175.5),       # +2.3% close over the touch close: slow
        (175, 176, 174, 175), (175, 176, 174, 175), (175, 176, 174, 175), (175, 176, 174, 175), (175, 176, 174, 175)]
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 1_000_000

    def compute(hist):
        return {"demand_zones": [dict(BAND)], "supply_zones": []}
    res = QB.run(["AAA", "BBB", "NOPE"], load=lambda s: {"AAA": df, "BBB": df.iloc[:100]}.get(s),
                 compute=compute)
    m = res["meta"]
    assert m["studied"] == 1 and m["skipped"] == 2 and m["events"] == 1
    r = res["rows"][0]
    assert r["symbol"] == "AAA" and r["slow"] == 1 and r["quick"] == 0 and r["avg_dollar_vol_50"] > 0
    assert "_pq" not in r and m["placebo_rate_pct"] is not None and m["qualifying"] == 0
    assert set(m["params"]) >= {"gap_min_pct", "quick_max_touch_days", "min_events", "min_quick_rate_pct",
                                "lid_min_touches", "lid_min_strength"}
    assert QB.STUDY_CRON == "0 7 * * 0"


def test_study_cron_is_pinned_in_the_crontab():
    tab = (Path(__file__).resolve().parents[1] / "crontab").read_text()
    line = [ln for ln in tab.splitlines() if "supply_demand.quick_bounce" in ln and not ln.startswith("#")]
    assert len(line) == 1
    assert line[0].split("/usr/local/bin/python")[0].split() == QB.STUDY_CRON.split()


# ── the live list ────────────────────────────────────────────────────────────
LID = {"kind": "supply", "lo": 191.11, "hi": 193.94, "touches": 2, "strength": 53.0}
WEAK = {"kind": "supply", "lo": 172.0, "hi": 175.0, "touches": 1, "strength": 20.0}
STATS = {"events": 6, "quick": 4, "same_day": 3, "gap_up": 1, "first_day_quick": 2, "quick_rate_pct": 66.7,
         "first_day_rate_pct": 33.3, "placebo_rate_pct": 24.0, "edge_pts": 42.7, "median_lift_pct": 3.8,
         "last_quick_date": "2026-09-01"}


def test_nearest_demand_inside_above_within_five_pct_never_under():
    bands = [BAND, LID, {"kind": "demand", "lo": 150.0, "hi": 152.0, "touches": 2, "strength": 60.0},
             {"kind": "demand", "lo": 176.0, "hi": 177.0, "touches": 1, "strength": 5.0}]   # unproven
    assert QB.nearest_demand(168.0, bands)["state"] == "inside"
    above = QB.nearest_demand(172.0, bands)
    assert above["state"] == "above" and above["dist_pct"] == 1.29 and above["band"]["lo"] == 164.6
    assert QB.nearest_demand(169.81 * 1.05 + 0.5, bands) is None, "more than 5% above every band"
    assert QB.nearest_demand(159.0, bands)["band"]["lo"] == 150.0, "under the top band: the one below it (4.6% over)"
    assert QB.nearest_demand(160.0, bands) is None, "5.3% over the lower band, under the upper: nothing to bounce off"
    assert QB.nearest_demand(140.0, bands) is None, "fell through every band"
    assert QB.nearest_demand(176.5, bands)["band"]["lo"] == 164.6, "3.9% above the proven band: still that band"
    assert QB.nearest_demand(179.0, bands) is None, "5.4% above it; the 1-touch band at 176-177 is not a level"


def test_live_row_measures_room_to_the_first_proven_lid_and_writes_the_plan():
    doc = {"bands": [BAND, WEAK, LID], "prev_close": 167.56, "atr14": 6.0}
    r = QB.live_row("KLAC", STATS, doc, 169.50)
    assert r["state"] == "inside" and r["dist_pct"] == 0.0 and r["room"]["target"] == 191.11
    assert r["stop"] == 163.78 and r["risk_pct"] == 3.37 and r["target"] == 191.11 and r["rr"] == 3.8
    assert r["plan"].startswith("buy $164.6-169.81 · stop $163.78")
    assert r["stats"]["quick_rate_pct"] == 66.7
    # a proven lid right overhead: hidden for room (and the caller counts it)
    tight = {"bands": [BAND, dict(WEAK, touches=2, strength=50.0), LID], "prev_close": 167.56}
    h = QB.live_row("KLAC", STATS, tight, 169.50)
    assert h["hidden"] == "room" and h["room"]["state"] == "ROOM" and h["room"]["room_pct"] == 1.5
    assert QB.live_row("KLAC", STATS, tight, 169.50, min_room=None)["room_ok"] is False, "room off: listed, flagged"
    assert QB.live_row("KLAC", STATS, doc, None) is None and QB.live_row("KLAC", STATS, None, 169.5) is None
    assert QB.live_row("KLAC", STATS, doc, 160.0) is None, "fell through: not a candidate"


def test_live_rows_sorts_nearest_first_then_most_room_and_counts_the_rest():
    stats = {"A": STATS, "B": STATS, "C": STATS, "D": dict(STATS, events=2), "E": STATS, "F": STATS}
    band_lo = {"kind": "demand", "lo": 100.0, "hi": 102.0, "touches": 3, "strength": 80.0}
    lid_near = {"kind": "supply", "lo": 112.0, "hi": 113.0, "touches": 2, "strength": 50.0}
    lid_far = {"kind": "supply", "lo": 130.0, "hi": 131.0, "touches": 2, "strength": 50.0}
    docs = {"A": {"bands": [band_lo, lid_near], "prev_close": 101.0},      # above 1.96%, room 9.8%
            "B": {"bands": [band_lo, lid_far], "prev_close": 101.0},       # inside, room 27%
            "C": {"bands": [band_lo, lid_near], "prev_close": 101.0},      # inside, room 10.9%
            "E": {"bands": [band_lo, dict(lid_near, lo=103.0, hi=104.0)], "prev_close": 101.0},   # inside, lid on top: hidden
            "F": {"bands": [band_lo], "prev_close": 101.0}}                # 9% above: away
    prints = {"A": 104.0, "B": 101.0, "C": 101.0, "D": 101.0, "E": 101.5, "F": 111.0}
    res = QB.live_rows(stats, docs, prints)
    assert [r["symbol"] for r in res["rows"]] == ["B", "C", "A"], "inside first (most room breaks the tie), then 2% above"
    assert res["hidden_room"] == 1 and res["no_band"] == 1 and res["no_print"] == 0
    assert QB.live_rows(stats, docs, {})["no_print"] == 5, "D never qualified; the rest had no print"
