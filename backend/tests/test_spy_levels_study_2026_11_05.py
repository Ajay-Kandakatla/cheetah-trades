"""SPY levels study 2026-11-05 (scripts/spy_levels_study_2026_11_05.py) — Mongo-free,
network-free, synthetic bars only (a planted daily frame; hand-built 1-minute days on a naive-UTC
index with `session` tags; a fake cache dict loader). NEGATIVES throughout.

NOT RUN on Ajay's data here — every frame below is synthetic.
"""
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from daytrading import data as DATA
from daytrading import indicators
from scripts import resiliency_study as RS
from scripts import spy_levels_study_2026_11_05 as S
from scripts import strategy_lab_2026_10_29 as LAB
from sepa import prices
from supply_demand import price_zones, timeframes, zone_store

ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
NIGHT = datetime(2026, 11, 5, 22, 0, tzinfo=ET)
DAY = date(2026, 6, 3)          # a Wednesday, no holiday, not a half day
N5 = len(S.expected_labels(DAY))


# ---------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------
def _utc(d, hh, mm):
    return (pd.Timestamp(datetime.combine(d, dtime(hh, mm), tzinfo=ET))
            .tz_convert("UTC").tz_localize(None))


def _mk_day(d, bars5, premarket=None, vol=1000.0):
    """1-minute RTH bars from 78 five-minute (O, H, L, C): minute 0 carries the bar's range,
    minutes 1-4 sit at the close (so the 5-minute aggregate is exactly the bar)."""
    rows, idx = [], []
    t0 = _utc(d, 9, 30)
    for k, (O, H, L, C) in enumerate(bars5):
        for m in range(5):
            idx.append(t0 + pd.Timedelta(minutes=5 * k + m))
            rows.append((O, H, L, C) if m == 0 else (C, C, C, C))
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"],
                      index=pd.DatetimeIndex(idx, name="ts_utc"))
    df["volume"] = vol
    df["session"] = "rth"
    if premarket:
        pm = pd.DataFrame([premarket], columns=["open", "high", "low", "close"],
                          index=pd.DatetimeIndex([_utc(d, 8, 0)], name="ts_utc"))
        pm["volume"] = vol
        pm["session"] = "premarket"
        df = pd.concat([pm, df]).sort_index()
    return df


def _bars(base, events=None, n=N5):
    """Flat bars at the running close; `events` {k: (O, H, L, C)} override bar k."""
    events = events or {}
    out, px = [], float(base)
    for k in range(n):
        if k in events:
            b = tuple(float(x) for x in events[k])
            px = b[3]
        else:
            b = (px, px, px, px)
        out.append(b)
    return out


def _sess(d, bars5, bands, flagged=False):
    s, why = S.session_frame(d, _mk_day(d, bars5))
    assert s is not None, why
    s.update(levels={"pdhl": bands, "fine": bands}, fine_raw=bands, pdhl_raw=bands,
             prev=d - timedelta(days=1), prev_half=False, flagged=flagged, split="is")
    return s


def _key(mode="cross", target="flatten_only", vwap=False, source="pdhl"):
    return f"{source}|{mode}|{target}|vwap_{'on' if vwap else 'off'}"


def _run(bars5, bands, **kw):
    tr, cnt = S.run_variant([_sess(DAY, bars5, bands)], _key(**kw), "is")
    return tr, cnt


def _band(lo, hi, kind="supply"):
    return {"lo": lo, "hi": hi, "kind": kind}


def _daily(n=400, end="2026-10-30", seed=7):
    idx = pd.bdate_range(end=end, periods=n)
    t = np.arange(n)
    rng = np.random.default_rng(seed)
    close = 100 + 6 * np.sin(2 * np.pi * t / 37) + 0.02 * t + rng.normal(0, 0.3, n)
    df = pd.DataFrame({"open": np.r_[close[0], close[:-1]], "close": close}, index=idx)
    df["high"] = np.maximum(df["open"], df["close"]) + 0.4
    df["low"] = np.minimum(df["open"], df["close"]) - 0.4
    df["volume"] = 1e6
    df.index.name = "date"
    return df[["open", "high", "low", "close", "volume"]]


def _loader(days_docs):
    return lambda d: days_docs.get(d)


# ---------------------------------------------------------------------------
# 1  FINE levels = the ONE engine, point-in-time
# ---------------------------------------------------------------------------
def test_01_fine_levels_are_price_zones_compute_before_the_union():
    daily = _daily()
    d = date(2026, 9, 15)
    got = S.fine_raw_for(daily, d)
    z = price_zones.compute(daily[daily.index < pd.Timestamp(d)], max_zones=None)
    want = [{"lo": b["lo"], "hi": b["hi"], "kind": k} for k, key in
            (("demand", "demand_zones"), ("supply", "supply_zones")) for b in z[key]
            if b["hi"] >= b["lo"] > 0]
    assert got == want and len(got) >= 2
    assert S.levels_for(daily, d, "fine", None) == S.union_overlaps(got)


def test_01b_NEG_a_row_dated_d_or_later_changes_nothing():
    daily = _daily()
    d = date(2026, 9, 15)
    before = S.fine_raw_for(daily, d)
    spiked = daily.copy()
    spiked.loc[spiked.index >= pd.Timestamp(d), ["high", "close"]] *= 3
    assert S.fine_raw_for(spiked, d) == before
    one = daily.copy()
    one.loc[one.index == pd.Timestamp(d), ["high", "close"]] *= 3
    incl = price_zones.compute(one[one.index <= pd.Timestamp(d) + pd.Timedelta(days=14)],
                               max_zones=None)
    assert [(b["lo"], b["hi"]) for b in incl["supply_zones"]] != [
        (b["lo"], b["hi"]) for b in before if b["kind"] == "supply"]


def test_01c_NEG_short_frame_is_excluded_no_bands():
    daily = _daily(n=zone_store.MIN_BARS - 1, end="2026-06-02")
    prev = date(2026, 6, 2)
    docs = {DAY: _mk_day(DAY, _bars(100)), prev: _mk_day(prev, _bars(100))}
    keep, excl = S.usable_sessions([DAY], _loader(docs), daily)
    assert keep == [] and excl == [{"date": DAY.isoformat(), "reason": "no_bands"}]
    keep2, excl2 = S.usable_sessions([DAY], _loader(docs), _daily(end="2026-06-02"))
    assert len(keep2) == 1 and excl2 == []


# ---------------------------------------------------------------------------
# 2  PDH / PDL from the previous RTH minute bars
# ---------------------------------------------------------------------------
def test_02_pdhl_is_session_high_low_and_premarket_never_moves_it():
    prev = date(2026, 6, 2)
    doc = _mk_day(prev, _bars(100, {10: (100, 101.5, 99.2, 100)}), premarket=(100, 110, 90, 100))
    rth = indicators.session_high_low(doc, "rth")
    raw = S.pdhl_raw_for(doc)
    assert raw == [{"lo": rth["high"], "hi": rth["high"], "kind": "pdh"},
                   {"lo": rth["low"], "hi": rth["low"], "kind": "pdl"}]
    assert raw[0]["hi"] == 101.5 and raw[1]["lo"] == 99.2


def test_02b_NEG_daily_high_off_the_rth_print_is_suspect_only_past_the_threshold():
    prev = date(2026, 6, 2)
    doc = _mk_day(prev, _bars(100, {10: (100, 101.0, 99.0, 100)}))
    docs = {prev: doc}
    for bump, expect in ((1.0 + S.SUSPECT_DAILY_PCT * 1.5 / 100, True),
                         (1.0 + S.SUSPECT_DAILY_PCT * 0.5 / 100, False)):
        daily = pd.DataFrame({"open": [100.0, 100.0], "high": [101.0, 101.0 * bump],
                              "low": [99.0, 99.0], "close": [100.0, 100.0],
                              "volume": [1.0, 1.0]},
                             index=pd.DatetimeIndex([pd.Timestamp("2026-06-01"),
                                                     pd.Timestamp(prev)], name="date"))
        sus, dist = S.suspect_rows(daily, S.cache_loader(_loader(docs)), [prev])
        assert (len(sus) == 1) is expect, bump
        assert dist["n"] == 1
        assert S.pdhl_raw_for(doc)[0]["hi"] == 101.0


def test_02c_NEG_no_previous_doc_within_the_gap_and_a_half_day_serves():
    has = {date(2026, 5, 27)}
    assert S.prev_session(DAY, lambda d: d in has) is None
    half = date(2025, 11, 28)
    assert S.is_half_day(half)
    assert S.prev_session(date(2025, 12, 1), lambda d: d == half) == half
    docs = {DAY: _mk_day(DAY, _bars(100))}
    keep, excl = S.usable_sessions([DAY], _loader(docs), _daily())
    assert keep == [] and excl[0]["reason"] == "prev_session_gap"


# ---------------------------------------------------------------------------
# 2b  overlap union
# ---------------------------------------------------------------------------
def test_02d_union_overlaps():
    m = S.union_overlaps([_band(100.0, 101.0, "supply"), _band(100.8, 101.5, "demand")])
    assert len(m) == 1 and (m[0]["lo"], m[0]["hi"], m[0]["kind"]) == (100.0, 101.5, "merged")
    assert len(m[0]["members"]) == 2
    t = S.union_overlaps([_band(100.0, 101.0), _band(101.0, 102.0, "demand")])
    assert len(t) == 1 and (t[0]["lo"], t[0]["hi"]) == (100.0, 102.0)


def test_02e_NEG_union_never_merges_by_distance_and_keeps_disjoint_lists():
    gap = [_band(100.0, 101.0), _band(102.515, 103.0, "demand")]
    assert (gap[1]["lo"] - gap[0]["hi"]) / gap[0]["hi"] * 100 == pytest.approx(1.5)
    assert price_zones.ZONE_MERGE_PCT > 1.5
    assert S.union_overlaps(gap) == gap
    lines = [_band(101.0, 101.0, "pdh"), _band(99.0, 99.0, "pdl")]
    assert S.union_overlaps(lines) == sorted(lines, key=lambda b: b["lo"])
    same = S.union_overlaps([_band(100.0, 100.0, "pdh"), _band(100.0, 100.0, "pdl")])
    assert len(same) == 1 and same[0]["kind"] == "merged"


# ---------------------------------------------------------------------------
# 3  5-minute frame = the ONE resampler
# ---------------------------------------------------------------------------
def test_03_five_min_is_resample_ohlcv_and_right_closed_disagrees():
    rng = np.random.default_rng(3)
    px = 100 + np.cumsum(rng.normal(0, 0.05, 390))
    idx = pd.DatetimeIndex([_utc(DAY, 9, 30) + pd.Timedelta(minutes=i) for i in range(390)])
    df = pd.DataFrame({"open": px, "high": px + 0.02, "low": px - 0.02, "close": px,
                       "volume": 1.0, "session": "rth"}, index=idx)
    got = S.five_min(df)
    pd.testing.assert_frame_equal(got, timeframes.resample_ohlcv(df, "5min"))
    rc = df.resample("5min", label="right", closed="right").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    assert got["open"].iloc[0] != rc["open"].iloc[0] or got.index[0] != rc.index[0]
    assert len(got) == N5


# ---------------------------------------------------------------------------
# 4  signals
# ---------------------------------------------------------------------------
A = _band(100.5, 101.0, "supply")


def test_04_cross_long_stop_is_the_signal_bar_low_and_targets():
    ev = {8: (100.8, 101.3, 100.7, 101.2)}
    tr, cnt = _run(_bars(100.8, ev), [A], target="2R")
    assert len(tr) == 1
    t = tr.iloc[0]
    assert t["side"] == "long" and t["stop"] == 100.7 and t["entry"] == 101.2
    assert t["t_entry"].startswith(f"{DAY.isoformat()}T10:15")
    assert t["target"] == pytest.approx(101.2 + S.TARGET_R * 0.5)
    B = _band(102.0, 102.5, "supply")
    tr2, _ = _run(_bars(100.8, ev), [A, B], target="next_or_flatten")
    assert tr2.iloc[0]["target"] == pytest.approx(102.0) and not tr2.iloc[0]["no_next_level"]


def test_04b_cross_short_touch_reverse_long_and_short():
    tr, _ = _run(_bars(100.7, {8: (100.7, 100.8, 100.2, 100.3)}), [A])
    assert tr.iloc[0]["side"] == "short" and tr.iloc[0]["stop"] == 100.8
    tl, _ = _run(_bars(101.5, {8: (101.5, 101.6, 100.9, 101.4)}), [A], mode="touch_reverse")
    assert tl.iloc[0]["side"] == "long" and tl.iloc[0]["stop"] == 100.9
    ts, _ = _run(_bars(100.2, {8: (100.2, 100.6, 100.1, 100.3)}), [A], mode="touch_reverse")
    assert ts.iloc[0]["side"] == "short" and ts.iloc[0]["stop"] == 100.6


def test_04c_pdl_cross_long_targets_pdh():
    lines = S.union_overlaps([_band(101.5, 101.5, "pdh"), _band(100.0, 100.0, "pdl")])
    tr, _ = _run(_bars(99.8, {8: (99.8, 100.3, 99.7, 100.2)}), lines, target="next_or_flatten")
    assert tr.iloc[0]["target"] == pytest.approx(101.5)


def test_04d_NEG_no_signal_cases():
    tr, _ = _run(_bars(101.5, {8: (101.5, 101.6, 100.9, 100.8)}), [A], mode="touch_reverse")
    assert len(tr) == 0 or tr.iloc[0]["side"] != "long"
    tr, _ = _run(_bars(100.8, {8: (100.8, 101.0, 100.7, 101.0)}), [A])
    assert len(tr) == 0
    tr, _ = _run(_bars(101.1, {8: (101.1, 101.3, 101.05, 101.2)}), [A])
    assert len(tr) == 0


def test_04e_NEG_entry_window_and_one_trade_a_day():
    ev = {1: (100.8, 101.3, 100.7, 101.2), 4: (101.2, 101.2, 100.75, 100.8),
          6: (100.8, 101.3, 100.7, 101.2)}
    tr, cnt = _run(_bars(100.8, ev), [A])
    assert cnt["outside_window"] == 1
    assert tr.iloc[0]["t_entry"].startswith(f"{DAY.isoformat()}T10:05")
    k_late = S.expected_labels(DAY).index(datetime.combine(DAY, S.LAST_ENTRY_ET, tzinfo=ET))
    tr2, cnt2 = _run(_bars(100.8, {k_late: (100.8, 101.3, 100.7, 101.2)}), [A])
    assert len(tr2) == 0 and cnt2["outside_window"] == 1
    ev3 = {8: (100.8, 101.3, 100.7, 101.2), 12: (101.2, 101.2, 100.75, 100.8),
           16: (100.8, 101.3, 100.7, 101.2)}
    tr3, cnt3 = _run(_bars(100.8, ev3), [A])
    assert len(tr3) == 1 and cnt3["signals_skipped_same_day"] == 1


def test_04f_NEG_vwap_align_drops_the_long_below_vwap():
    ev = {0: (103, 103, 103, 103), 20: (103, 103, 100.75, 100.8),
          30: (100.8, 101.3, 100.7, 101.2)}
    off, _ = _run(_bars(103, ev), [A])
    on, _ = _run(_bars(103, ev), [A], vwap=True)
    assert len(off) == 1 and len(on) == 0


def test_04g_NEG_half_day_and_holed_frame_are_excluded():
    half = date(2026, 11, 27)
    prev = date(2026, 11, 25)
    docs = {half: _mk_day(half, _bars(100)), prev: _mk_day(prev, _bars(100))}
    _, excl = S.usable_sessions([half], _loader(docs), _daily(end="2026-11-26"))
    assert excl == [{"date": half.isoformat(), "reason": "half_day"}]
    doc = _mk_day(DAY, _bars(100))
    holed = doc.drop(doc.index[60:65])
    s, why = S.session_frame(DAY, holed)
    assert s is None and why == "hole_5m"


def test_04h_C8_both_sides_on_one_bar_skipped_and_cross_cannot():
    Aa, Bb = _band(99.0, 100.2, "demand"), _band(100.8, 102.0, "supply")
    idx = pd.DatetimeIndex([_utc(DAY, 10, 0), _utc(DAY, 10, 5)])
    b5 = pd.DataFrame({"open": [100.5, 100.5], "high": [100.5, 100.9], "low": [100.5, 100.1],
                       "close": [100.5, 100.5]}, index=idx)
    sig, cnt = S.signals_for(b5, [Aa, Bb], "touch_reverse", pd.Series(dtype=float), False)
    assert sig == [] and cnt["both_sides_same_bar"] == 1
    sig2, cnt2 = S.signals_for(b5, [Aa, Bb], "cross", pd.Series(dtype=float), False)
    assert sig2 == [] and cnt2["both_sides_same_bar"] == 0


def test_04i_C1_gap_through_the_stop_skips_and_multi_band_nearest_wins():
    ev = {8: (100.8, 101.3, 100.7, 101.2), 9: (100.6, 100.6, 100.6, 100.6)}
    tr, cnt = _run(_bars(100.8, ev), [A])
    assert len(tr) == 0 and cnt["entry_beyond_stop"] == 1
    lower = _band(99.5, 100.0, "demand")
    tr2, cnt2 = _run(_bars(99.8, {8: (99.8, 101.3, 99.7, 101.2)}), [lower, A])
    assert cnt2["multi_band_same_bar"] == 1
    assert tr2.iloc[0]["source_band_hi"] == 101.0


def test_04j_C7_cross_over_pdh_kept_with_no_target_and_in_fallback():
    lines = S.union_overlaps([_band(101.0, 101.0, "pdh"), _band(99.0, 99.0, "pdl")])
    ev = {8: (100.8, 101.3, 100.7, 101.2)}
    tr, cnt = _run(_bars(100.8, ev), lines, target="next_or_flatten")
    assert len(tr) == 1 and pd.isna(tr.iloc[0]["target"]) and cnt["no_next_level"] == 1
    assert tr.iloc[0]["exit_reason"] == S.EXIT_FLAT
    key = _key(target="next_or_flatten")
    blocks = S.split_blocks({key: (tr, cnt)}, 1, draws=50, seed=1)
    assert blocks[key]["fallback"]["n_trades"] == 1


# ---------------------------------------------------------------------------
# 5  exits
# ---------------------------------------------------------------------------
def _exit_sess(ev):
    return _sess(DAY, _bars(100.0, ev), [A])


def test_05_exit_rules_and_known_answer_cost():
    s = _exit_sess({8: (100, 100, 100, 100), 9: (100, 102.5, 98.5, 100)})
    i = 5 * 9
    o = S.candidate_outcomes(s, 1, 1.0, 2.0, idxs=[i])
    assert o["reason"][0] == S.EXIT_STOP and o["exit"][0] == 99.0
    s2 = _exit_sess({9: (100, 100, 100, 100), 10: (97.0, 97.0, 97.0, 97.0)})
    o2 = S.candidate_outcomes(s2, 1, 1.0, None, idxs=[5 * 9])
    assert o2["reason"][0] == S.EXIT_STOP and o2["exit"][0] == 97.0
    s3 = _exit_sess({9: (100, 100, 100, 100), 50: (100, 100, 100, 101.0)})
    o3 = S.candidate_outcomes(s3, 1, 5.0, None, idxs=[5 * 9])
    assert o3["reason"][0] == S.EXIT_FLAT
    assert s3["et1"][o3["exit_idx"][0]].time() == S.FLATTEN_ET
    assert o3["gross_pct"][0] == pytest.approx(1.0)
    assert o3["net_pct"][0] == pytest.approx(1.0 - 2 * (0.01 + 0.01))
    z = S.net_of(np.array([1.0]), 100.0, cost_bps=0.0, slip_usd=0.0)
    assert z[0] == pytest.approx(1.0) and z[0] != o3["net_pct"][0]


def test_05b_one_engine_vector_equals_the_traded_outcome():
    ev = {8: (100.8, 101.3, 100.7, 101.2), 30: (101.2, 101.4, 101.0, 101.3)}
    s = _sess(DAY, _bars(100.8, ev), [A])
    tr, _ = S.run_variant([s], _key(target="2R"), "is")
    t = tr.iloc[0]
    vec = S.candidate_outcomes(s, 1, t["stop_dist"], t["target_dist"])
    pos = int(np.flatnonzero(vec["idx"] == t["entry_idx"])[0])
    assert vec["net_pct"][pos] == t["net_pct"] and vec["reason"][pos] == t["exit_reason"]


def test_05c_C9_stop_inside_the_entry_minute_exits_there():
    s = _exit_sess({9: (100, 100, 100, 100), 10: (100, 100.2, 98.9, 100)})
    i = 5 * 10
    o = S.candidate_outcomes(s, 1, 1.0, None, idxs=[i])
    assert o["reason"][0] == S.EXIT_STOP and o["exit_idx"][0] == i and o["exit"][0] == 99.0
    lo = s["low"]
    later = [j for j in range(i + 1, s["flat_idx"]) if lo[j] <= 99.0]
    assert later == []


# ---------------------------------------------------------------------------
# 6  lookahead + split + seal
# ---------------------------------------------------------------------------
def test_06_entry_is_after_the_signal_bar_and_a_shifted_frame_changes_trades():
    ev = {8: (100.8, 101.3, 100.7, 101.2), 9: (101.25, 101.25, 101.25, 101.25)}
    s = _sess(DAY, _bars(100.8, ev), [A])
    tr, _ = S.run_variant([s], _key(), "is")
    last_min_of_bar = 5 * 8 + 4
    assert tr.iloc[0]["entry_idx"] == last_min_of_bar + 1 and tr.iloc[0]["entry"] == 101.25
    s2 = dict(s)
    b = s["bars5"].copy()
    b.index = b.index - pd.Timedelta(minutes=S.BAR_MINUTES)
    s2["bars5"], s2["lab_et"] = b, S.to_et(b.index)
    tr2, _ = S.run_variant([s2], _key(), "is")
    assert tr2.iloc[0]["entry_idx"] != tr.iloc[0]["entry_idx"]


def test_06b_split_weekdays_halves_and_boundary_is_a_weekday():
    a, b = date(2026, 4, 1), date(2026, 11, 4)
    is_d, oos_d = S.split_weekdays(a, b)
    W = S.weekdays(a, b)
    assert is_d + oos_d == W and len(is_d) == len(W) // 2
    assert oos_d[0].weekday() < 5 and max(is_d) < min(oos_d)


def _cohort(tmp_path, daily, cohort_first, as_of):
    csv = tmp_path / "data" / "d.csv"
    S.save_daily(daily, csv)
    p = tmp_path / "cohort.json"
    p.write_text(json.dumps({"as_of": as_of, "data": {"cohort_first": cohort_first,
                                                      "daily_csv": str(csv)}}))
    return p


def _docs_for(days, base=100.0):
    return {d: _mk_day(d, _bars(base, {8: (base, base + 0.3, base - 0.1, base + 0.2),
                                       30: (base + 0.2, base + 0.2, base - 0.6, base - 0.5)}))
            for d in days}


def test_06c_NEG_is_mode_never_touches_an_oos_weekday(tmp_path):
    cohort_first, as_of = date(2026, 6, 1), date(2026, 7, 24)
    is_d, oos_d = S.split_weekdays(cohort_first, as_of)
    docs = _docs_for(S.weekdays(date(2026, 5, 25), is_d[-1]))
    oos = set(oos_d)

    def load(d):
        if d in oos:
            raise AssertionError(f"OOS weekday {d} read in is mode")
        return docs.get(d)
    daily = _daily(end="2026-07-24")
    cs = _cohort(tmp_path, daily, cohort_first.isoformat(), as_of.isoformat())
    rc = S.main(["--mode", "is", "--as-of", as_of.isoformat(), "--out", str(tmp_path / "is"),
                 "--cohort-stats", str(cs), "--draws", "100", "--placebo-sets", "50"],
                now=NIGHT, load_day=load, daily=daily, net_block=False, colls=(None, None))
    assert rc == 0
    st = json.loads((tmp_path / "is" / "stats.json").read_text())
    assert st["data"]["split"]["is"]["n_usable"] > 0 and st["data"]["split"]["oos"]["n_usable"] == 0
    assert "oos" not in st and st["data"]["split"]["boundary"] == oos_d[0].isoformat()


def test_06d_NEG_non_fetch_without_cohort_stats_is_refused(tmp_path):
    for mode in ("smoke", "is", "outcome"):
        assert S.main(["--mode", mode, "--out", str(tmp_path / mode)], now=NIGHT) == 3
        assert not (tmp_path / mode).exists()


# ---------------------------------------------------------------------------
# 7  placebos
# ---------------------------------------------------------------------------
def _trade_at(sess, i, side, sd, td=None):
    o = S.candidate_outcomes(sess, side, sd, td, idxs=[i])
    return {"date": sess["date"].isoformat(), "sign": side, "side": "long" if side > 0 else
            "short", "stop_dist": sd, "target_dist": td, "entry_idx": i,
            "net_pct": float(o["net_pct"][0]), "gross_pct": float(o["gross_pct"][0]),
            "t_entry": sess["et1"][i].isoformat(), "flagged": False}


def _min_day(d, px):
    """A 390-minute RTH day from a per-minute price path (open = prior close)."""
    px = np.asarray(px, float)
    o = np.r_[px[0], px[:-1]]
    idx = pd.DatetimeIndex([_utc(d, 9, 30) + pd.Timedelta(minutes=i) for i in range(len(px))])
    df = pd.DataFrame({"open": o, "high": np.maximum(o, px), "low": np.minimum(o, px),
                       "close": px, "volume": 1000.0, "session": "rth"}, index=idx)
    s, why = S.session_frame(d, df)
    assert s is not None, why
    return s


def _days(n, start=date(2026, 1, 5)):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=7)
    return out


def _i_of(sess, hh, mm):
    return int(np.flatnonzero([t.time() == dtime(hh, mm) for t in sess["et1"]])[0])


def test_07_b1_b2_candidate_sets():
    s = _min_day(DAY, 100 + np.cumsum(np.random.default_rng(1).normal(0, 0.02, 390)))
    i = _i_of(s, 11, 0)
    tr = pd.Series(_trade_at(s, i, 1, 0.3))
    n1, i1 = S.placebo_pool(s, tr, window_min=None)
    n2, i2 = S.placebo_pool(s, tr, window_min=S.PLACEBO_WINDOW_MIN)
    assert set(i2) <= set(i1) and i not in set(i1)
    dm1 = [abs((s["et1"][j] - s["et1"][i]) / pd.Timedelta(minutes=1)) for j in i1]
    dm2 = [abs((s["et1"][j] - s["et1"][i]) / pd.Timedelta(minutes=1)) for j in i2]
    assert min(dm1) >= S.PLACEBO_EXCL_MIN and max(dm2) <= S.PLACEBO_WINDOW_MIN
    assert all(s["in_win"][j] for j in i1)
    assert len(i2) == 2 * (S.PLACEBO_WINDOW_MIN - S.PLACEBO_EXCL_MIN + 1)


def test_07b_NEG_iid_random_walk_passes_neither_placebo():
    """The joint rule (CI separates AND beat share) never passes on a random walk; the beat
    share ALONE can sit above 0.95 by chance (seed 12 B1: 0.99 with a no_signal CI), which is
    why the CI is part of the pass."""
    beats = []
    for seed in (11, 12, 13):
        rng = np.random.default_rng(seed)
        days = _days(40)
        sess = {d.isoformat(): _min_day(d, 100 + np.cumsum(rng.normal(0, 0.03, 390)))
                for d in days}
        tr = pd.DataFrame([_trade_at(s, _i_of(s, 10, 30), 1, 0.2, 0.4) for s in sess.values()])
        for wm in (None, S.PLACEBO_WINDOW_MIN):
            p = S.placebo_minutes(tr, sess, window_min=wm, sets=200, draws=500)
            assert p["pass"] is False and p["word"] != "separates"
            beats.append(p["beat_share"])
    assert sum(b >= S.PLACEBO_BEAT_SHARE for b in beats) <= 1, beats


def _planted_day(d, rng, t0):
    px = 100 + rng.normal(0, 0.01, 390)
    px[t0 - 1] = 98.8
    px[t0:t0 + 3] = 100.0
    px[t0 + 3:] = 101.5 - np.linspace(0, 4, 390 - t0 - 3)
    return px


def test_07c_a_planted_level_rule_passes_both():
    rng = np.random.default_rng(5)
    days = _days(40)
    t0 = 120
    sess = {d.isoformat(): _min_day(d, _planted_day(d, rng, t0)) for d in days}
    tr = pd.DataFrame([_trade_at(s, t0 + 1, 1, 0.5, 1.0) for s in sess.values()])
    assert (tr["net_pct"] > 0).all()
    b1 = S.placebo_minutes(tr, sess, window_min=None, sets=200, draws=500)
    b2 = S.placebo_minutes(tr, sess, window_min=S.PLACEBO_WINDOW_MIN, sets=200, draws=500)
    assert b1["pass"] and b2["pass"]


def test_07d_NEG_drift_passes_b1_on_duration_and_fails_b2():
    rng = np.random.default_rng(9)
    days = _days(60)
    sess = {}
    for d in days:
        px = np.full(390, 100.0)
        px[90:] += np.linspace(0, 3.0, 300) + rng.normal(0, 0.05, 300)
        sess[d.isoformat()] = _min_day(d, px)
    tr = pd.DataFrame([_trade_at(s, _i_of(s, 9, 45), 1, 50.0) for s in sess.values()])
    b1 = S.placebo_minutes(tr, sess, window_min=None, sets=200, draws=500)
    b2 = S.placebo_minutes(tr, sess, window_min=S.PLACEBO_WINDOW_MIN, sets=200, draws=500)
    assert b1["pass"] is True and b2["pass"] is False and b2["word"] != "separates"
    assert not (b1["pass"] and b2["pass"])


# ---------------------------------------------------------------------------
# 8  statistics
# ---------------------------------------------------------------------------
def _stat_trades(dates, net):
    n = len(dates)
    return pd.DataFrame({"date": [d.isoformat() for d in dates],
                         "week": [LAB._week_monday(d.isoformat()) for d in dates],
                         "t_entry": "10:00", "net_pct": net, "gross_pct": np.asarray(net) + 0.04,
                         "net_r": net, "exit_reason": [S.EXIT_STOP] * n, "risk_pct": 0.2,
                         "stop_over_atr": 1.0, "room_over_risk": 2.0, "side": "long",
                         "sign": 1, "flagged": False})


def test_08_cluster_ci_by_dates_and_n_weeks_gate():
    six_weeks = [d for d in pd.bdate_range("2026-01-05", periods=30)]
    six = [d.date() for d in six_weeks]
    thirty = _days(30)
    net = np.full(30, 0.1) + np.random.default_rng(2).normal(0, 0.01, 30)
    b6 = S.block(_stat_trades(six, net), draws=300, seed=4)
    b30 = S.block(_stat_trades(thirty, net), draws=300, seed=4)
    assert b6["n_dates"] == 30 and b6["n_weeks"] == 6 and b30["n_weeks"] == 30
    assert b6 == S.block(_stat_trades(six, net), draws=300, seed=4)
    assert LAB.positive_verdict(True, True, True, b6["n_weeks"])["word"] == "TOO SMALL"
    assert LAB.positive_verdict(True, True, True, b30["n_weeks"])["word"] == "POSITIVE"


def test_08b_is_pick_needs_30_weeks_and_takes_the_lower_bound():
    blk = {k: {"pooled": {"n_weeks": 40, "ci_raw_pct": [-0.1, 0.2]}} for k in S.FAMILY}
    blk[S.FAMILY[5]]["pooled"] = {"n_weeks": 40, "ci_raw_pct": [0.05, 0.3]}
    blk[S.FAMILY[3]]["pooled"] = {"n_weeks": 29, "ci_raw_pct": [0.5, 0.9]}
    p = S.is_pick(blk)
    assert p["variant"] == S.FAMILY[5] and p["is_lower_ci_pct"] == 0.05
    assert S.is_pick({k: {"pooled": {"n_weeks": 29, "ci_raw_pct": [1, 2]}}
                      for k in S.FAMILY}) is None
    tie = {k: {"pooled": {"n_weeks": 40, "ci_raw_pct": [0.1, 0.2]}} for k in S.FAMILY}
    assert S.is_pick(tie)["variant"] == S.FAMILY[0]


def test_08c_duplicate_clusters_and_effective_vs_naive_sr0():
    rng = np.random.default_rng(3)
    a = rng.normal(0, 1, 50)
    series = {"x": a, "x_dup": a.copy(), "y": rng.normal(0, 1, 50)}
    assert S.duplicate_clusters(series, rho=S.DUP_RHO) == [["x", "x_dup"], ["y"]]
    prior = [0.05, -0.36, -0.39, -0.42, -0.55]
    eff = [0.30, -0.10]
    naive = [0.30, 0.31, -0.10]
    x = rng.normal(0.1, 1, 60)
    de, dn = LAB.deflated(x, prior + eff), LAB.deflated(x, prior + naive)
    assert de["sr0"] != dn["sr0"] and de["N"] == 7 and dn["N"] == 8
    g = 0.5772156649015329
    from statistics import NormalDist
    nd = NormalDist()
    sd = float(np.std(prior + eff, ddof=1))
    want = sd * ((1 - g) * nd.inv_cdf(1 - 1 / 7) + g * nd.inv_cdf(1 - 1 / (7 * np.e)))
    assert de["sr0"] == pytest.approx(want)


def test_08d_prior_srs_always_five(tmp_path):
    led = tmp_path / "strategy_lab_ledger.json"
    led.write_text(json.dumps([{"trial_id": "T01", "sr_per_entry_day": 0.0506}]))
    res = tmp_path / S.GATES_RESULTS_REL
    res.parent.mkdir(parents=True)
    res.write_text(json.dumps({"result": {"reads": {
        "G1": {"sr": -0.35}, "G2": {"sr": -0.38}, "G3": {"sr": -0.42}, "G4": {"sr": -0.54},
        "COMBINED": {"sr": None}}}}))
    assert S.prior_srs(led) == [0.0506, -0.35, -0.38, -0.42, -0.54]


def test_08e_NEG_flagged_share_above_5pct_is_unmeasured_glitch():
    days = _days(3)
    sess = {d.isoformat(): _min_day(d, np.full(390, 100.0)) for d in days}
    rows = [_trade_at(s, _i_of(s, 10, 30), 1, 0.5) for s in sess.values()]
    rows[0]["flagged"] = True
    tr = pd.DataFrame(rows)
    tr["week"] = [LAB._week_monday(d) for d in tr["date"]]
    tr["exit_reason"], tr["risk_pct"], tr["net_r"] = S.EXIT_FLAT, 0.5, 0.0
    tr["stop_over_atr"], tr["room_over_risk"] = None, None
    g = S.gates(tr, sess, [], [], n_sessions=3, draws=100, sets=50)
    assert g["verdict"]["word"] == LAB.UNMEASURED_GLITCH and g["verdict"]["n_flagged"] == 1


# ---------------------------------------------------------------------------
# 9  refusals + guards
# ---------------------------------------------------------------------------
def _outcome_args(tmp_path, prereg, commit="a" * 12, ledger=None, cs=None):
    return ["--mode", "outcome", "--as-of", "2026-07-24", "--out", str(tmp_path / "o"),
            "--cohort-stats", str(cs or tmp_path / "cohort.json"), "--prereg", str(prereg),
            "--prereg-commit", commit, "--ledger", str(ledger or LAB.LEDGER_PATH)]


def test_09_refusals_rc3_nothing_written(tmp_path, monkeypatch):
    prereg = tmp_path / "prereg.md"
    prereg.write_text("prereg\n")
    shaf = tmp_path / "sha"
    shaf.write_text(hashlib.sha256(prereg.read_bytes()).hexdigest() + "\n")
    monkeypatch.setattr(S, "SHA_FILE", shaf)
    rth = datetime(2026, 11, 5, 10, 0, tzinfo=ET)
    assert S.main(_outcome_args(tmp_path, prereg), now=rth) == 3
    assert S.main(["--mode", "fetch", "--as-of", "2026-11-04", "--out", str(tmp_path / "f")],
                  now=rth) == 3
    assert S.main(_outcome_args(tmp_path, prereg, commit="HASH"), now=NIGHT) == 3
    assert S.main(_outcome_args(tmp_path, prereg, ledger="/tmp/x.json"), now=NIGHT) == 3
    other = tmp_path / "other.md"
    other.write_text("changed\n")
    monkeypatch.setattr(LAB, "ledger_refusal", lambda p: None)
    assert S.main(_outcome_args(tmp_path, other, ledger=tmp_path / "l.json"), now=NIGHT) == 3
    (tmp_path / "o").mkdir()
    (tmp_path / "o" / "stats.json").write_text("{}")
    assert S.main(_outcome_args(tmp_path, prereg, ledger=tmp_path / "l.json"), now=NIGHT) == 3
    assert S.main(["--mode", "smoke", "--out", str(REPO / "x"), "--cohort-stats", "c"],
                  now=NIGHT) == 3
    assert sorted(p.name for p in tmp_path.iterdir()) == ["o", "other.md", "prereg.md", "sha"]
    assert [p.name for p in (tmp_path / "o").iterdir()] == ["stats.json"]


def test_09b_pick_null_refuses_and_keeps_the_oos_sealed(tmp_path, monkeypatch):
    prereg = tmp_path / "prereg.md"
    prereg.write_text("prereg\n")
    shaf = tmp_path / "sha"
    shaf.write_text(hashlib.sha256(prereg.read_bytes()).hexdigest())
    monkeypatch.setattr(S, "SHA_FILE", shaf)
    monkeypatch.setattr(LAB, "ledger_refusal", lambda p: None)
    led = tmp_path / "research" / "strategy_lab_ledger.json"
    led.parent.mkdir()
    led.write_text("[]")
    res = led.parent / S.GATES_RESULTS_REL
    res.parent.mkdir(parents=True)
    res.write_text(json.dumps({"result": {"reads": {"G1": {"sr": -0.3}}}}))
    cohort_first, as_of = date(2026, 6, 1), date(2026, 7, 24)
    is_d, oos_d = S.split_weekdays(cohort_first, as_of)
    docs = _docs_for(S.weekdays(date(2026, 5, 25), is_d[-1]))
    oos = set(oos_d)

    def load(d):
        if d in oos:
            raise AssertionError("OOS read before a pick")
        return docs.get(d)
    daily = _daily(end="2026-07-24")
    cs = _cohort(tmp_path, daily, cohort_first.isoformat(), as_of.isoformat())
    rc = S.main(_outcome_args(tmp_path, prereg, ledger=led, cs=cs) + ["--draws", "100"],
                now=NIGHT, load_day=load, daily=daily, net_block=False, colls=(None, None))
    assert rc == 3 and not (tmp_path / "o").exists() and json.loads(led.read_text()) == []


def _keep_attrs(monkeypatch):
    import requests
    from pymongo.collection import Collection
    for mod, attr, _ in LAB._NET_TARGETS:
        if hasattr(mod, attr):
            monkeypatch.setattr(mod, attr, getattr(mod, attr))
    monkeypatch.setattr(requests.Session, "request", requests.Session.request)
    for verb in ("request", "get", "post", "put", "delete", "head", "patch"):
        monkeypatch.setattr(requests, verb, getattr(requests, verb))
    for m in RS.WRITE_METHODS:
        if hasattr(Collection, m):
            monkeypatch.setattr(Collection, m, getattr(Collection, m))
    monkeypatch.setattr(DATA, "_fetch_massive_minute", DATA._fetch_massive_minute)
    monkeypatch.setattr(DATA, "_mongo_put_day", DATA._mongo_put_day)


def test_09c_guards_refuse_fetches_and_record_puts(monkeypatch):
    _keep_attrs(monkeypatch)
    import requests
    S.block_network_and_writes()
    with pytest.raises(S.FetchRefused):
        requests.get("https://api.massive.com/x")
    with pytest.raises(S.FetchRefused):
        DATA._fetch_massive_minute("SPY", DAY, DAY)
    with pytest.raises(S.FetchRefused):
        prices._fetch_massive("SPY", "2y")
    n = len(S.RECORDED_PUTS)
    assert DATA._mongo_put_day("SPY", DAY, pd.DataFrame()) is None
    assert S.RECORDED_PUTS[n:] == [f"SPY:{DAY}"]


def test_09d_fetch_history_paces_and_never_calls_on_a_hit_or_cache_only():
    days = S.weekdays(date(2026, 6, 1), date(2026, 6, 5))
    hits = {days[0]: "doc", days[2]: "doc"}
    calls, sleeps = [], []

    def loader(d):
        calls.append(d)
        return pd.DataFrame({"x": [1]}) if d == days[1] else None
    fails = iter([True, True, False])
    fh = S.fetch_history(days[0], days[-1], pause_sec=1.0, loader=loader, cached=hits.get,
                         sleep=sleeps.append, failed=lambda: next(fails))
    assert calls == [days[1], days[3], days[3], days[4]]
    assert fh["sessions_cached_before"] == 2 and fh["sessions_fetched"] == 1
    assert fh["fetch_failed"] == [days[3].isoformat()] and fh["cohort_first"] == "2026-06-01"
    assert fh["fetch_retried"] == [days[3].isoformat()]
    assert sleeps.count(1.0) == 3 and sleeps.count(DATA._CB_COOLDOWN_SEC) == 1
    calls.clear()
    co = S.fetch_history(days[0], days[-1], pause_sec=1.0, loader=loader, cached=hits.get,
                         sleep=sleeps.append, cache_only=True)
    assert calls == [] and co["sessions_fetched"] == 0 and co["cache_only"]


def test_09f_fetch_history_retries_a_failed_day_once_after_the_cooldown():
    """Critic defect 1 (2026-11-05): 2026-01-05 was lost to one Massive read timeout because
    the cooldown slept but never retried. A failed day now gets exactly ONE retry."""
    days = S.weekdays(date(2026, 1, 5), date(2026, 1, 7))
    calls, sleeps = [], []
    first = {"seen": False}

    def loader(d):
        calls.append(d)
        if d == days[0] and not first["seen"]:
            first["seen"] = True
            return None
        return pd.DataFrame({"x": [1]}) if d == days[0] else None
    flags = iter([True, False, False])
    fh = S.fetch_history(days[0], days[-1], pause_sec=1.0, loader=loader, cached=lambda d: None,
                         sleep=sleeps.append, failed=lambda: next(flags))
    assert calls == [days[0], days[0], days[1], days[2]]
    assert fh["fetched"] == [days[0].isoformat()] and fh["fetch_failed"] == []
    assert fh["fetch_retried"] == [days[0].isoformat()] and fh["cohort_first"] == "2026-01-05"
    assert sleeps.count(DATA._CB_COOLDOWN_SEC) == 1 and sleeps.count(1.0) == 3


def test_09f_neg_a_day_failing_twice_is_retried_once_and_an_empty_day_never():
    days = S.weekdays(date(2026, 1, 5), date(2026, 1, 6))
    calls, sleeps = [], []

    def loader(d):
        calls.append(d)
        return None
    flags = iter([True, True, False])
    fh = S.fetch_history(days[0], days[-1], pause_sec=1.0, loader=loader, cached=lambda d: None,
                         sleep=sleeps.append, failed=lambda: next(flags))
    assert calls == [days[0], days[0], days[1]]
    assert fh["fetch_failed"] == [days[0].isoformat()] and fh["fetch_retried"] == [
        days[0].isoformat()]
    assert fh["empty"] == [days[1].isoformat()] and fh["cohort_first"] is None
    assert sleeps.count(DATA._CB_COOLDOWN_SEC) == 1 and sleeps.count(1.0) == 2
    calls.clear()
    sleeps.clear()
    quiet = S.fetch_history(days[0], days[-1], pause_sec=1.0, loader=loader,
                            cached=lambda d: None, sleep=sleeps.append, failed=lambda: False)
    assert calls == [days[0], days[1]] and quiet["fetch_retried"] == []
    assert DATA._CB_COOLDOWN_SEC not in sleeps


def test_09e_fetch_mode_writes_stats_and_an_exact_daily_csv(tmp_path):
    daily = _daily(end="2026-11-04")
    rc = S.main(["--mode", "fetch", "--as-of", "2026-11-04", "--out",
                 str(tmp_path / "out" / "fetch"), "--cache-only"], now=NIGHT, daily=daily,
                cached=lambda d: None, fetch_loader=lambda d: None, net_block=False,
                colls=(None, None), sleep=lambda s: None)
    assert rc == 0
    st = json.loads((tmp_path / "out" / "fetch" / "stats.json").read_text())
    back = S.load_daily(st["data"]["daily_csv"])
    pd.testing.assert_frame_equal(back, S.normalise_daily(daily), check_freq=False)
    assert st["data"]["cache_only"] is True and st["data"]["sessions_fetched"] == 0


# ---------------------------------------------------------------------------
# 10  pins + scope
# ---------------------------------------------------------------------------
def test_10_pins_to_the_lane_and_the_house():
    import trading.zero_dte_lane as ZD
    from daytrading import signal_lab
    from options import zero_dte
    assert (S.ENTRY_OPEN_ET, S.LAST_ENTRY_ET, S.FLATTEN_ET, S.SIGNAL_MAX_AGE_SEC) == (
        ZD.ENTRY_OPEN_ET, ZD.LAST_ENTRY_ET, ZD.FLATTEN_ET, ZD.SIGNAL_MAX_AGE_SEC)
    assert S.PLACEBO_EXCL_MIN == ZD.SIGNAL_MAX_AGE_SEC // 60
    assert S.TARGET_R == signal_lab.TARGET_R and S.TARGET_DELTA == zero_dte.TARGET_DELTA
    assert S.MINE == {"FETCH_PAUSE_SEC": 1.0, "COST_BPS": 1.0, "SLIP_USD": 0.01,
                      "PLACEBO_WINDOW_MIN": 30, "DUP_RHO": 0.95, "SUSPECT_DAILY_PCT": 1.0}
    assert S.ATR_PERIOD == 14 and S.MIN_CLUSTERS == LAB.MIN_CLUSTERS == 30


def _numeric_literals(path):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
                and not isinstance(node.value, bool):
            out.append((node.lineno, node.value))
    return out


def test_10b_every_numeric_literal_is_mine_design_typed_or_a_pin():
    allowed = {0, 1, 2, 100}
    for v in S.MINE.values():
        allowed.add(v)
    for v in S.DESIGN.values():
        allowed.update(v if isinstance(v, tuple) else (v,))
    allowed.update({9, 45, 14, 30, 15, 180})
    bad = [(ln, v) for ln, v in _numeric_literals(S.__file__) if v not in allowed]
    assert bad == [], bad


def test_10c_never_imports_trading_static_and_transitive():
    got = S.imported_modules()
    assert not [m for m in got if m.split(".")[0] in ("trading", "alpaca", "autopilot")]
    code = ("import sys; sys.path.insert(0, %r); import scripts.spy_levels_study_2026_11_05; "
            "print('\\n'.join(sorted(sys.modules)))" % str(BACKEND))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120,
                       env={"PATH": "/usr/bin:/bin", "HOME": str(Path.home()),
                            "PYTHONDONTWRITEBYTECODE": "1"})
    assert r.returncode == 0, r.stderr[-800:]
    mods = [m for m in r.stdout.split() if m.split(".")[0] in
            ("trading", "alpaca", "alpaca_trade_api", "autopilot", "notifications")]
    assert mods == []


def test_10d_family_is_24_keys_in_order():
    assert len(S.FAMILY) == 24 and len(set(S.FAMILY)) == 24
    assert S.FAMILY[0] == "pdhl|cross|next_or_flatten|vwap_off"
    assert S.FAMILY[1] == "pdhl|cross|next_or_flatten|vwap_on"
    assert S.FAMILY[-1] == "fine|touch_reverse|flatten_only|vwap_on"


# ---------------------------------------------------------------------------
# 11  words
# ---------------------------------------------------------------------------
def test_11_report_words_three_side_lines_and_the_overlay_word():
    blk = S.block(None)
    stats = {"mode": "outcome", "as_of": "2026-11-04", "data": {"scale": {}},
             "pick": {"variant": S.FAMILY[0]},
             "oos": {k: {s: {"block": blk, "verdict": {"word": "TOO SMALL"}} for s in S.SIDES}
                     for k in S.FAMILY},
             "candidate": {"variant": S.FAMILY[0], "verdict_pooled": "TOO SMALL",
                           "verdict_long": "TOO SMALL", "verdict_short": "TOO SMALL",
                           "ship_word": "OFF"},
             "overlay_options": {k: S.overlay(None) for k in S.FAMILY}}
    rep = S.render_report(stats)
    assert S.forbidden_hits(rep) == [] and "bounce" not in rep.lower()
    assert "approximation" in rep and S.UNION_SENTENCE in rep
    for k in S.FAMILY:
        lines = [ln for ln in rep.splitlines() if f"`{k}` ·" in ln]
        assert [s for s in S.SIDES if any(f"**{s}**" in ln for ln in lines)] == list(S.SIDES)
    assert S.forbidden_hits("edges of overlapping bands") == ["edge"]


def test_11b_scale_medians_are_labelled_at_signal_bars_per_variant_row():
    """Critic defect 4: the two scale medians are taken over variant-rows at signal bars."""
    stats = {"mode": "smoke", "as_of": "2026-11-04", "pick": None,
             "data": {"scale": {"stop_dist_pct_median": 0.1, "atr14_5m_pct_median": 0.122,
                                "day_range_pct_median": 0.885}}}
    rep = S.render_report(stats)
    line = [ln for ln in rep.splitlines() if ln.startswith("Scale")]
    assert len(line) == 1 and "at signal bars, per variant-row" in line[0]
    assert "0.100 %" in line[0] and "0.122 %" in line[0]
    assert "day range median (per session)" in line[0]


# ---------------------------------------------------------------------------
# 12  the prereg pin (runs once WP-B lands)
# ---------------------------------------------------------------------------
def test_12_prereg_sha_pins_the_committed_copy():
    doc = REPO / S.PREREG_DOC
    if not doc.is_file() or not S.SHA_FILE.is_file():
        pytest.skip("the prereg doc or the sha file is not written yet (WP-B)")
    assert hashlib.sha256(doc.read_bytes()).hexdigest() == S.read_sha_file()


# ---- Amendment A1 (2026-11-05, stage 3 run #1 crashed): a parameter must never shadow a module callable ----
def _shadowed_params(fn, module) -> set:
    """The names of fn's parameters that are also callables in the module namespace (a shadowing bug)."""
    import inspect
    callables = {n for n, v in vars(module).items() if callable(v) and not n.startswith("__")}
    return set(inspect.signature(fn).parameters) & callables


def test_13_no_parameter_of_main_or_run_fetch_shadows_a_module_callable():
    """Stage 3 run #1 crashed: main(block=True) shadowed block() in the outcome-only fallback branch
    (`TypeError: 'bool' object is not callable`); smoke / IS never run that branch. The flag is now net_block."""
    assert _shadowed_params(S.main, S) == set()
    assert _shadowed_params(S.run_fetch, S) == set()
    assert "net_block" in __import__("inspect").signature(S.main).parameters


def test_13_NEGATIVE_the_guard_catches_a_shadowing_parameter():
    import types
    m = types.ModuleType("fake"); m.block = lambda *a, **k: None   # a module callable
    def main(argv=None, *, block=True): return block
    assert _shadowed_params(main, m) == {"block"}
