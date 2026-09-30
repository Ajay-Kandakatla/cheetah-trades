"""🛡️ Resiliency persistence study (2026-09-30) — hermetic tests.

Synthetic frames only (no Mongo, no FRED). Pins: the walk-forward label window
never contains its own outcome event (and a mutated window is caught), strata
drop a cell with no controls, the bootstrap is reproducible with the seed and
shares its indices across series, the pre-registered verdict rule, the placebo
session is never an event session, an all-quiet universe measures nothing, the
EOD read reuses the tab's engines, the artifact <-> MEASURED literal, the RTH
refusal, and the import scope (never supply_demand.key_levels).
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from chart_maps import resiliency_measured as RM
from chart_maps import resiliency_tab as RT
from scripts import resiliency_study as S
from sepa import volume as V
from supply_demand import momentum_burst as MB

ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]
N_DAYS = 560


# ---------------------------------------------------------------------------
# synthetic universe
# ---------------------------------------------------------------------------
def _idx(n=N_DAYS, hour=0):
    return pd.bdate_range("2024-09-30", periods=n) + pd.Timedelta(hours=hour)


def _frame(idx, closes, rng, vol_scale=1e6):
    closes = np.asarray(closes, dtype=float)
    opens = closes * (1 + rng.normal(0, 0.003, len(closes)))
    hi = np.maximum(opens, closes) * (1 + rng.uniform(0.001, 0.01, len(closes)))
    lo = np.minimum(opens, closes) * (1 - rng.uniform(0.001, 0.01, len(closes)))
    vol = rng.uniform(0.5, 1.5, len(closes)) * vol_scale
    return pd.DataFrame({"open": opens, "high": hi, "low": lo, "close": closes,
                         "volume": vol}, index=idx)


def _events(idx):
    days = [d.date() for d in idx]
    ev = []
    for i, d in enumerate(days):
        if i % 20 == 5:
            ev.append({"date": d.isoformat(), "kind": "cpi", "tier": 1, "label": "CPI",
                       "source": "FRED release dates", "release_id": 10})
        if d.weekday() == 3:
            ev.append({"date": d.isoformat(), "kind": "claims", "tier": 2,
                       "label": "Jobless claims", "source": "FRED release dates",
                       "release_id": 180})
    return ev


def _universe(seed=7, n_names=10, quiet=False):
    rng = np.random.default_rng(seed)
    idx = _idx()
    spy_r = rng.normal(0.0003, 0.01, len(idx))
    frames = {"SPY": _frame(idx, 400 * np.cumprod(1 + spy_r), rng, 5e7)}
    for k in range(n_names):
        if quiet:
            closes = 50 * np.cumprod(np.full(len(idx), 1.001))
        else:
            b = 0.3 + 0.2 * k
            sd = 0.005 + 0.002 * k
            closes = 50 * np.cumprod(1 + b * spy_r + rng.normal(0, sd, len(idx)))
        frames[f"N{k:02d}"] = _frame(idx + pd.Timedelta(hours=4 * (k % 2)), closes, rng)
    return frames, _events(idx)


def _days_and_sessions(frames, events):
    days = sorted(RT.closes_by_day(frames["SPY"]))
    sess = RT.event_sessions(events, days, start=date.fromisoformat(days[0]),
                             end=date.fromisoformat(days[-1]) + timedelta(days=1))
    return days, sess


# ---------------------------------------------------------------------------
# normalization + windows + the leak check
# ---------------------------------------------------------------------------
def test_frame_days_matches_the_tab_day_iso():
    idx = pd.DatetimeIndex(["2026-03-06 00:00", "2026-03-09 04:00", "2026-11-02 04:00"])
    fr = pd.DataFrame({"close": [1.0, 2.0, 3.0]}, index=idx)
    assert S.frame_days(fr) == [RT.day_iso(t) for t in idx]
    utc = idx.tz_localize("UTC") + pd.Timedelta(hours=5)
    fr2 = pd.DataFrame({"close": [1.0, 2.0, 3.0]}, index=utc)
    assert S.frame_days(fr2) == [RT.day_iso(t) for t in utc]


def test_label_window_is_the_tabs_window():
    frames, events = _universe()
    days, sess = _days_and_sessions(frames, events)
    for e in list(sess["t1"])[-6:]:
        tab = RT.event_sessions(events, days, start=date.fromisoformat(e) - timedelta(
            days=RT.HOLD_WINDOW_DAYS), end=date.fromisoformat(e))
        assert list(S.label_window(sess["t1"], e)) == list(tab["t1"])


def test_label_window_never_contains_its_outcome_event():
    frames, events = _universe()
    days, sess = _days_and_sessions(frames, events)
    for key in ("t1", "t2"):
        for e in S.outcome_events(sess[key], days):
            win = S.label_window(sess[key], e)
            assert e not in win and all(iso < e for iso in win)
            S.check_no_leak(e, win)


def test_a_leaking_window_is_caught():
    frames, events = _universe(n_names=2)
    days, sess = _days_and_sessions(frames, events)

    def leaky(ts, e):
        lo = S._minus_days(e, RT.HOLD_WINDOW_DAYS)
        return {iso: v for iso, v in ts.items() if lo <= iso <= e}
    closes = {s: RT.closes_by_day(f) for s, f in frames.items() if s != "SPY"}
    rets = {s: RT.event_returns(c, days, sess["t1"]) for s, c in closes.items()}
    kw = dict(days=days, event_isos=set(sess["t1"]) | set(sess["t2"]), closes_by_sym=closes,
              bench_closes=RT.closes_by_day(frames["SPY"]), rets_by_sym=rets,
              bench_rets=RT.event_returns(RT.closes_by_day(frames["SPY"]), days, sess["t1"]),
              tier=1)
    assert len(S.tier_rows(sess["t1"], **kw)) > 0
    with pytest.raises(S.LeakError):
        S.tier_rows(sess["t1"], window_fn=leaky, **kw)
    with pytest.raises(S.LeakError):
        S.check_no_leak("2026-03-11", {"2026-02-11": {}, "2026-03-11": {}})


def test_outcome_events_need_a_full_trailing_year():
    frames, events = _universe(n_names=1)
    days, sess = _days_and_sessions(frames, events)
    got = S.outcome_events(sess["t1"], days)
    assert got and all(S._minus_days(e, RT.HOLD_WINDOW_DAYS) >= days[0] for e in got)
    assert [e for e in sess["t1"] if e not in got]      # the first year never tests
    assert S.outcome_events(sess["t1"], []) == []


def test_placebo_session_is_never_an_event_session():
    frames, events = _universe(n_names=1)
    days, sess = _days_and_sessions(frames, events)
    ev = set(sess["t1"]) | set(sess["t2"])
    for e in sess["t1"]:
        p = S.placebo_session(days, e, ev)
        if p is not None:
            assert p > e and p not in ev
            between = [d for d in days if e < d < p]
            assert all(d in ev for d in between)
    assert S.placebo_session(days, days[-1], ev) is None
    assert S.placebo_session(["2026-01-05", "2026-01-06"], "2026-01-05",
                             {"2026-01-06"}) is None


# ---------------------------------------------------------------------------
# strata, contrast, bootstrap, verdicts
# ---------------------------------------------------------------------------
def test_quantile_bins_are_rank_based_and_deterministic():
    b = S.quantile_bins([5, 1, 4, 2, 3, 9, 8, 7, 6, 10], 5)
    assert sorted(b.tolist()) == [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]
    assert b[1] == 0 and b[9] == 4
    ties = S.quantile_bins([1.0, 1.0, 1.0], 3, ["C", "A", "B"])
    assert ties.tolist() == [2, 0, 1]
    assert S.quantile_bins([], 5).tolist() == []


def test_strata_drop_a_cell_with_no_controls():
    cl = [0, 0, 0, 0, 0]
    cell = [0, 0, 1, 1, 1]
    lab = [1, 0, 1, 1, 1]           # cell 1 has no control
    y = [100, 0, 0, 0, 0]
    num, w = S.cell_contrast(cl, cell, lab, y, 1)
    assert w.tolist() == [1.0] and num.tolist() == [100.0]
    num, w = S.cell_contrast([0, 0], [0, 0], [1, 1], [1, 0], 1)
    assert w.tolist() == [0.0] and S.pooled(num, w) is None
    num, w = S.cell_contrast([0, 0], [0, 0], [0, 0], [1, 0], 1)     # no R at all
    assert w.tolist() == [0.0]


def test_bootstrap_is_reproducible_and_shares_indices():
    rng = np.random.default_rng(1)
    num, w = rng.normal(0, 5, 40), rng.integers(1, 5, 40).astype(float)
    a1, = S.boot_draws([(num, w)], 300, 11)
    a2, = S.boot_draws([(num, w)], 300, 11)
    a3, = S.boot_draws([(num, w)], 300, 12)
    assert np.array_equal(a1, a2) and not np.array_equal(a1, a3)
    x, y = S.boot_draws([(num, w), (num, w)], 300, 11)
    assert np.all(x - y == 0)
    assert S.ci_of(x - y) == [0.0, 0.0]
    assert S.ci_of([np.nan, np.nan]) is None
    empty, = S.boot_draws([(np.zeros(0), np.zeros(0))], 5, 1)
    assert np.isnan(empty).all()


@pytest.mark.parametrize("n,ci,want", [
    (S.MIN_BUCKET_N - 1, [1.0, 2.0], "too_small"),
    (S.MIN_BUCKET_N, [0.1, 2.0], "separates"),
    (S.MIN_BUCKET_N, [0.0, 2.0], "no_signal"),
    (S.MIN_BUCKET_N, [-1.0, 2.0], "no_signal"),
    (S.MIN_BUCKET_N, [-3.0, -0.1], "inverted"),
    (S.MIN_BUCKET_N, [-3.0, 0.0], "no_signal"),
    (S.MIN_BUCKET_N, None, "too_small"),
    (S.MIN_BUCKET_N, [None, 1.0], "too_small"),
])
def test_verdict_rule(n, ci, want):
    assert S.verdict(n, ci) == want


def test_specific_word():
    # fix round 2026-09-30: the verdict passed in is the PRIMARY one (read on the
    # event-specific CI); the second argument is the stratified lift's CI.
    assert S.specific_word("separates", [0.5, 3.0]) == "event_specific"
    assert S.specific_word("separates", [-0.5, 3.0]) == "event_specific"
    assert S.specific_word("separates", None) == "event_specific"
    assert S.specific_word("no_signal", [0.5, 3.0]) == "general"
    assert S.specific_word("inverted", [0.5, 3.0]) == "general"
    # NEGATIVE
    assert S.specific_word("no_signal", [-0.5, 3.0]) == "unclear"
    assert S.specific_word("no_signal", [0.0, 3.0]) == "unclear"
    assert S.specific_word("no_signal", None) == "unclear"
    assert S.specific_word("too_small", [0.5, 3.0]) == "unclear"


def _rows(n_events, y_r, y_c, yp_r, yp_c, per=6):
    rows = []
    for k in range(n_events):
        e = (date(2026, 1, 1) + timedelta(days=k)).isoformat()
        for j in range(per):
            r = j % 2
            rows.append((e, f"S{j}", r, 1.0 + j // 2, 0.5 + j // 2, y_r if r else y_c,
                         yp_r if r else yp_c, 0.1))
    return pd.DataFrame(rows, columns=["E", "sym", "R", "sigma", "beta", "y", "y_p", "ret"])


def test_all_quiet_contrast_measures_zero():
    out = S.analyse_tier(_rows(40, 1, 1, 1, 1), draws=200, seed=3)
    assert out["lift_pp"] == 0.0 and out["ci"] == [0.0, 0.0]
    assert out["ci"][0] <= 0 <= out["ci"][1]
    assert out["verdict"] == "no_signal" and out["specific"] == "unclear"


def test_planted_signal_event_specific_vs_general():
    spec = S.analyse_tier(_rows(40, 1, 0, 0, 0), draws=200, seed=3)
    assert spec["lift_pp"] == 100.0 and spec["verdict"] == "separates"
    assert spec["specific"] == "event_specific" and spec["specific_pp"] == 100.0
    gen = S.analyse_tier(_rows(40, 1, 0, 1, 0), draws=200, seed=3)
    # the same names hold more on ordinary days too: a trait, not an event read.
    # The PRIMARY verdict reads the event-specific contrast (fix round 2026-09-30).
    assert gen["lift_pp"] == 100.0 and gen["ci"][0] > 0
    assert gen["verdict"] == "no_signal" and gen["specific"] == "general"
    assert gen["specific_pp"] == 0.0 and gen["placebo_lift_pp"] == 100.0
    assert gen["halves"]["first"]["n_events"] == 20 and gen["halves"]["second"]["n_events"] == 20
    inv = S.analyse_tier(_rows(40, 0, 1, 0, 0), draws=200, seed=3)
    assert inv["verdict"] == "inverted"
    # NEGATIVE: an ordinary-day edge with nothing on the data day reads inverted
    # (the event-specific contrast is below zero), never separates
    ordinary = S.analyse_tier(_rows(40, 1, 1, 1, 0), draws=200, seed=3)
    assert ordinary["lift_pp"] == 0.0 and ordinary["verdict"] == "inverted"
    small = S.analyse_tier(_rows(S.MIN_BUCKET_N - 1, 1, 0, 0, 0), draws=200, seed=3)
    assert small["verdict"] == "too_small" and small["specific"] == "unclear"


# ---------------------------------------------------------------------------
# the low-volatility confound (critic 2026-09-30): a universe with NO persistence
# must read no_signal. σ quintile x β tercile does not remove the confound, so
# the stratified lift alone "separated" here; the verdict reads the
# event-specific contrast (lift on E minus lift on the ordinary-day placebo).
# ---------------------------------------------------------------------------
def _null_rows(seed, n_names=600, n_events=52, window=41):
    """Rows with NO persistence: each name holds on ANY day with a fixed
    probability set only by its volatility (Φ(0.5 / σ) — iid returns); the
    label is its own past hold rate >= 75% over `window` earlier data days, so
    R is just "a quiet name". Placebo outcomes are drawn exactly like event
    outcomes."""
    from math import erf, sqrt
    rng = np.random.default_rng(seed)
    sd = np.exp(rng.uniform(np.log(0.4), np.log(4.0), n_names))
    b = rng.uniform(0.2, 1.8, n_names)
    p = np.array([0.5 * (1 + erf(0.5 / (x * sqrt(2)))) for x in sd])
    rows = []
    for k in range(n_events):
        e = (date(2025, 10, 1) + timedelta(days=7 * k)).isoformat()
        lab = ((rng.random((n_names, window)) < p[:, None]).mean(axis=1)
               >= RT.HOLD_RATE_MIN_PCT / 100.0).astype(int)
        y = (rng.random(n_names) < p).astype(int)
        yp = (rng.random(n_names) < p).astype(float)
        sig_obs = sd * np.exp(rng.normal(0, 0.1, n_names))
        b_obs = b + rng.normal(0, 0.15, n_names)
        for i in range(n_names):
            rows.append((e, f"N{i:04d}", int(lab[i]), float(sig_obs[i]), float(b_obs[i]),
                         int(y[i]), float(yp[i]), 0.0))
    return pd.DataFrame(rows, columns=["E", "sym", "R", "sigma", "beta", "y", "y_p", "ret"])


def test_NEG_no_persistence_never_separates_across_seeds():
    """30 seeded null universes: the stratified lift alone clears zero in most
    (the confound the old rule published); the pre-registered verdict never
    says separates."""
    old_rule, verdicts = 0, {}
    for seed in range(10, 40):
        o = S.analyse_tier(_null_rows(seed), draws=400, seed=1)
        old_rule += int(o["ci"][0] > 0)
        verdicts[o["verdict"]] = verdicts.get(o["verdict"], 0) + 1
    assert old_rule >= 15, old_rule                 # the confound is real in this null
    assert verdicts.get("separates", 0) == 0, verdicts
    assert verdicts.get("no_signal", 0) >= 25, verdicts


def _confound_universe(seed, n_names=160, n_days=520):
    """The critic's synthetic null through the REAL pipeline: iid returns,
    holding driven only by each name's σ and β, a T1 print every fifth session."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2024-09-30", periods=n_days)
    spy_r = rng.normal(0.0004, 0.009, n_days)

    def frame(closes, vs):
        o = closes * (1 + rng.normal(0, 0.002, n_days))
        hi = np.maximum(o, closes) * 1.004
        lo = np.minimum(o, closes) * 0.996
        return pd.DataFrame({"open": o, "high": hi, "low": lo, "close": closes,
                             "volume": rng.uniform(0.5, 1.5, n_days) * vs}, index=idx)
    frames = {"SPY": frame(400 * np.cumprod(1 + spy_r), 5e7)}
    for k in range(n_names):
        sd = float(np.exp(rng.uniform(np.log(0.004), np.log(0.04))))
        b = float(rng.uniform(0.2, 1.8))
        frames[f"N{k:04d}"] = frame(50 * np.cumprod(1 + b * spy_r + rng.normal(0, sd, n_days)),
                                    1e6)
    ev = []
    for i, d in enumerate(idx):
        if i % 5 == 2:
            ev.append({"date": d.date().isoformat(), "kind": "cpi", "tier": 1, "label": "CPI"})
        if d.weekday() == 3 and i % 5 != 2:
            ev.append({"date": d.date().isoformat(), "kind": "claims", "tier": 2,
                       "label": "claims"})
    return frames, ev, idx[-1].date().isoformat()


def test_NEG_synthetic_null_through_run_study_is_no_signal():
    frames, ev, as_of = _confound_universe(1)
    t1 = S.run_study(frames, ev, as_of=as_of, draws=300, seed=1, shuffle_draws=2)["t1"]
    assert t1["n_events"] >= S.MIN_BUCKET_N
    assert t1["ci"][0] > 0                          # the stratified lift alone "separates"
    assert t1["placebo_ci"][0] > 0                  # ... and so do ordinary days
    assert t1["specific_ci"][0] <= 0 <= t1["specific_ci"][1]
    assert t1["verdict"] == "no_signal" and t1["specific"] == "general"


def test_analyse_on_nothing_is_too_small():
    empty = pd.DataFrame(columns=["E", "sym", "R", "sigma", "beta", "y", "y_p", "ret"])
    assert S.analyse_tier(empty, draws=10, seed=1)["verdict"] == "too_small"
    assert S.analyse_tier(None, draws=10, seed=1)["n_label_rows"] == 0
    e = pd.DataFrame(columns=["d", "sym", "R", "sigma", "y", "y_oc", "avg"])
    assert S.analyse_eod(e, draws=10, seed=1)["verdict"] == "too_small"


# ---------------------------------------------------------------------------
# Q3 — the EOD read reuses the tab's engines
# ---------------------------------------------------------------------------
def test_eod_rows_reuse_the_tab_engines():
    frames, _ev = _universe(n_names=3)
    days = sorted(RT.closes_by_day(frames["SPY"]))
    arrs = {s: S.aligned(f, days) for s, f in frames.items() if s != "SPY"}
    df = S.eod_rows(arrs, days)
    assert len(df) > 50 and set(df["R"]) == {0, 1}
    pos = {d: i for i, d in enumerate(days)}
    for _, r in df.sample(40, random_state=1).iterrows():
        fr = frames[r["sym"]]
        i = pos[r["d"]]
        mb = MB.avg_volume_before(fr, date.fromisoformat(r["d"]))
        assert r["avg"] == pytest.approx(mb, rel=1e-12)
        closes = RT.closes_by_day(fr)
        assert r["sigma"] == RT.sigma_pct(closes, days[i - RT.VOL_AVG_BARS - 1:i])
        a = arrs[r["sym"]]
        bar = {k: a[k][i] for k in ("open", "high", "low", "close", "volume")}
        er = RT.eod_read(bar, a["close"][i - 1], mb, date_iso=r["d"], source="closed")
        assert er["bullish"] == bool(r["R"])
        assert V.accumulation_day(bar["close"], a["close"][i - 1], bar["high"], bar["low"],
                                  bar["volume"], mb) == bool(r["R"])
        assert r["y"] == RT.pct_ret(a["close"][i + 1], a["close"][i])
    assert df["d"].map(pos).min() >= S.EOD_MIN_PRIOR_BARS
    assert df["d"].max() < days[-1]                       # the last day has no next session


def test_eod_rows_negative_bars_never_enter():
    days = [d.date().isoformat() for d in _idx(80)]
    n = len(days)
    c = np.linspace(10, 20, n)                             # every day up
    base = {"open": c * 0.99, "high": c * 1.001, "low": c * 0.98, "close": c.copy(),
            "volume": np.full(n, 1e6)}
    ok = S.eod_rows({"A": {k: v.copy() for k, v in base.items()}}, days)
    assert len(ok) == n - 1 - S.EOD_MIN_PRIOR_BARS
    target = S.EOD_MIN_PRIOR_BARS + 3
    bad_vol = {k: v.copy() for k, v in base.items()}
    bad_vol["volume"][target] = np.nan
    bad_flat = {k: v.copy() for k, v in base.items()}
    bad_flat["high"][target] = bad_flat["low"][target] = bad_flat["close"][target]
    bad_down = {k: v.copy() for k, v in base.items()}
    bad_down["close"][target] = bad_down["close"][target - 1] * 0.99
    bad_down["low"][target] = bad_down["close"][target] * 0.98
    for arrs in (bad_vol, bad_flat, bad_down):
        got = S.eod_rows({"A": arrs}, days)
        assert days[target] not in set(got["d"])
    hole = {k: v.copy() for k, v in base.items()}
    hole["volume"][target - 5] = np.nan                   # inside the 50-bar average
    got = S.eod_rows({"A": hole}, days)
    assert days[target] not in set(got["d"])
    short = S.eod_rows({"A": {k: v[:S.EOD_MIN_PRIOR_BARS + 1] for k, v in base.items()}},
                       days[:S.EOD_MIN_PRIOR_BARS + 1])
    assert len(short) == 0
    assert S.eod_rows({}, days).empty


def test_aligned_leaves_holes_as_nan_and_drops_bad_values():
    idx = _idx(5)
    days = [d.date().isoformat() for d in idx]
    fr = pd.DataFrame({"open": [1, 1, 1, 1], "high": [2, 2, 2, 2], "low": [0.5] * 4,
                       "close": [1.0, -1.0, np.inf, 1.5], "volume": [10, -5, 3, np.nan]},
                      index=idx[[0, 1, 2, 4]])
    a = S.aligned(fr, days)
    assert np.isnan(a["close"][3])                         # no bar on that day
    assert np.isnan(a["close"][1]) and np.isnan(a["close"][2])
    assert np.isnan(a["volume"][1]) and np.isnan(a["volume"][4]) and a["volume"][0] == 10
    assert np.isnan(S.aligned(None, days)["close"]).all()


# ---------------------------------------------------------------------------
# the whole study on synthetic frames
# ---------------------------------------------------------------------------
TIER_KEYS = {"verdict", "specific", "lift_pp", "ci", "raw_lift_pp", "placebo_lift_pp",
             "placebo_ci", "specific_pp", "specific_ci", "ret_diff_pp", "ret_ci", "n_events",
             "n_label_rows", "halves"}
EOD_KEYS = {"verdict", "lift_pp", "ci", "placebo_pct", "n_days", "n_rows", "mean_next_pct",
            "share_up_pct"}


def test_run_study_shape_and_json_safety():
    frames, events = _universe()
    days = sorted(RT.closes_by_day(frames["SPY"]))
    body = S.run_study(frames, events, as_of=days[-1], draws=100, seed=5, shuffle_draws=20)
    assert TIER_KEYS <= set(body["t1"]) and TIER_KEYS <= set(body["t2"])
    assert EOD_KEYS <= set(body["eod"])
    assert body["pre"] == S.Q4_BLOCK and body["pre"]["verdict"] == "unmeasured"
    assert body["t1"]["n_label_rows"] > 0 and body["eod"]["n_rows"] > 0
    assert body["t1"]["verdict"] == "too_small"        # ~14 synthetic T1 events < MIN_BUCKET_N
    json.dumps(body, allow_nan=False)                   # no NaN, no numpy scalar
    again = S.run_study(frames, events, as_of=days[-1], draws=100, seed=5, shuffle_draws=20)
    assert again == body                                # reproducible with the seed


def test_run_study_respects_as_of():
    frames, events = _universe(n_names=3)
    days = sorted(RT.closes_by_day(frames["SPY"]))
    cut = days[-60]
    body = S.run_study(frames, events, as_of=cut, draws=50, seed=5, shuffle_draws=5)
    assert body["last_bar"] == cut
    assert body["t1"]["halves"] is None or body["t1"]["halves"]["second"]["to"] is None \
        or body["t1"]["halves"]["second"]["to"] <= cut


def test_all_quiet_universe_measures_nothing():
    frames, events = _universe(quiet=True)
    days = sorted(RT.closes_by_day(frames["SPY"]))
    body = S.run_study(frames, events, as_of=days[-1], draws=50, seed=5, shuffle_draws=5)
    for k in ("t1", "t2"):
        assert body[k]["n_events"] == 0 and body[k]["lift_pp"] is None
        assert body[k]["verdict"] == "too_small"
    json.dumps(body, allow_nan=False)


def test_run_study_negative_inputs():
    frames, events = _universe(n_names=1)
    with pytest.raises(ValueError):
        S.run_study({k: v for k, v in frames.items() if k != "SPY"}, events, as_of="2026-01-02")
    with pytest.raises(ValueError):
        S.run_study(frames, events, as_of="2024-09-30")
    days = sorted(RT.closes_by_day(frames["SPY"]))
    body = S.run_study(frames, [], as_of=days[-1], draws=10, seed=1, shuffle_draws=2)
    assert body["t1"]["sessions"] == 0 and body["t1"]["verdict"] == "too_small"


# ---------------------------------------------------------------------------
# main(): the clock gate, the prereg gate, the artifact
# ---------------------------------------------------------------------------
def _boom():
    raise AssertionError("must not be reached")


@pytest.mark.parametrize("hh,mm", [(9, 0), (10, 0), (16, 29)])
def test_refuses_the_session_window(hh, mm):
    now = datetime(2026, 9, 30, hh, mm, tzinfo=ET)
    assert S.main(["--prereg-commit", "abc"], now=now, universe_fn=_boom, block=False) == 2


def test_force_window_passes_the_clock_but_not_the_prereg_gate():
    now = datetime(2026, 9, 30, 10, 0, tzinfo=ET)
    assert S.main(["--force-window"], now=now, universe_fn=_boom, block=False) == 2


def test_outcome_run_needs_a_prereg_commit():
    now = datetime(2026, 9, 30, 18, 0, tzinfo=ET)
    assert S.main([], now=now, universe_fn=_boom, block=False) == 2
    assert S.main(["--prereg-commit", "  "], now=now, universe_fn=_boom, block=False) == 2


def test_smoke_never_writes_the_real_artifact_path():
    now = datetime(2026, 9, 30, 18, 0, tzinfo=ET)
    assert S.main(["--limit", "3"], now=now, universe_fn=_boom, block=False) == 2


def test_refused_window_edges():
    assert not S.refused_window(datetime(2026, 9, 30, 8, 59, tzinfo=ET))
    assert S.refused_window(datetime(2026, 9, 30, 9, 0, tzinfo=ET))
    assert not S.refused_window(datetime(2026, 9, 30, 16, 30, tzinfo=ET))


def test_default_as_of_is_the_last_closed_session():
    days = ["2026-09-28", "2026-09-29", "2026-09-30"]
    assert S.default_as_of(days, datetime(2026, 9, 30, 8, 0, tzinfo=ET)) == "2026-09-29"
    assert S.default_as_of(days, datetime(2026, 9, 30, 16, 29, tzinfo=ET)) == "2026-09-29"
    assert S.default_as_of(days, datetime(2026, 9, 30, 16, 30, tzinfo=ET)) == "2026-09-30"
    assert S.default_as_of(days, datetime(2026, 10, 3, 12, 0, tzinfo=ET)) == "2026-09-30"
    assert S.default_as_of(["2026-09-30"], datetime(2026, 9, 30, 8, 0, tzinfo=ET)) is None


def test_main_refuses_when_fred_is_unavailable(tmp_path):
    frames, _ev = _universe(n_names=2)
    now = datetime(2026, 9, 30, 18, 0, tzinfo=ET)
    rc = S.main(["--prereg-commit", "abc", "--out", str(tmp_path / "x.json")], now=now,
                universe_fn=lambda: ["N00", "N01"], frames_fn=lambda syms: frames,
                events_fn=lambda s, e: {"available": False, "events": []}, block=False)
    assert rc == 2 and not (tmp_path / "x.json").exists()
    rc = S.main(["--prereg-commit", "abc", "--out", str(tmp_path / "x.json")], now=now,
                universe_fn=lambda: ["N00"], frames_fn=lambda syms: {}, block=False)
    assert rc == 2


def test_main_writes_the_artifact_and_the_literal_round_trips(tmp_path):
    frames, events = _universe(n_names=4)
    now = datetime(2026, 11, 21, 18, 0, tzinfo=ET)          # after the synthetic last bar
    out = tmp_path / "resiliency_measured.json"
    seen = {}

    def ev_fn(s, e):
        seen["args"] = (s, e)
        return {"available": True, "events": events, "errors": []}
    rc = S.main(["--prereg-commit", "abc1234", "--out", str(out), "--draws", "50"], now=now,
                universe_fn=lambda: ["N00", "N01", "N02", "N03"],
                frames_fn=lambda syms: {s: frames[s] for s in syms}, events_fn=ev_fn,
                block=False)
    assert rc == 0
    art = json.loads(out.read_text())
    for k in ("study", "script", "prereg", "prereg_commit", "run_date", "as_of", "universe_n",
              "events_used", "definitions", "t1", "t2", "eod", "pre", "limits"):
        assert k in art, k
    assert art["prereg_commit"] == "abc1234" and art["smoke"] is False
    assert art["as_of"] == sorted(RT.closes_by_day(frames["SPY"]))[-1]
    assert seen["args"][1] == date.fromisoformat(art["as_of"])
    assert art["definitions"]["HOLD_MAX_DROP_PCT"] == RT.HOLD_MAX_DROP_PCT
    assert art["definitions"]["MIN_BUCKET_N"] == S.MIN_BUCKET_N
    assert len(art["events_used"]["events"]) == len(events)
    lit = S.measured_literal(art)
    assert lit["status"] == "measured" and lit["t1"]["verdict"] == art["t1"]["verdict"]
    blk = RT.study_block(lit)
    assert blk["status"] == "measured" and blk["pre"]["verdict"] == "unmeasured"
    for k in RT.FILTER_KEYS:
        txt = blk[k]["text"]
        assert "bounce" not in txt.lower() and "fake" not in txt.lower()
    replay = tmp_path / "replay.json"
    rc = S.main(["--prereg-commit", "abc1234", "--out", str(replay), "--draws", "50",
                 "--events-json", str(out)], now=now,
                universe_fn=lambda: ["N00", "N01", "N02", "N03"],
                frames_fn=lambda syms: {s: frames[s] for s in syms}, events_fn=_boom,
                block=False)
    assert rc == 0
    again = json.loads(replay.read_text())
    assert again["t1"] == art["t1"] and again["eod"] == art["eod"]


def test_measured_literal_pins_the_artifact_field_for_field():
    art_path = BACKEND / "scripts" / "resiliency_measured.json"
    m = RM.MEASURED
    assert m["script"] == S.SCRIPT and m["artifact"] == S.ARTIFACT
    if m["status"] == "pending":
        assert set(m) == {"status", "script", "artifact"}
        if art_path.exists():
            art = json.loads(art_path.read_text())
            assert art.get("smoke") is True or art.get("prereg_commit") is None, (
                "a real artifact exists but MEASURED is still pending — paste the literal")
        assert RT.study_block()["status"] == "pending"
        return
    art = json.loads(art_path.read_text())
    assert m == S.measured_literal(art)
    assert art["smoke"] is False and art["prereg_commit"]


# ---------------------------------------------------------------------------
# import scope
# ---------------------------------------------------------------------------
_KL_RE = re.compile(r"^\s*(from\s+supply_demand\s+import\s+[^\n]*\bkey_levels\b"
                    r"|from\s+supply_demand\.key_levels\s+import"
                    r"|import\s+supply_demand\.key_levels)", re.M)
ALLOWED_APP = {"macro_calendar", "chart_maps.resiliency_tab", "scripts.explosive_study.MIN_BUCKET_N",
               "sepa.prices", "sepa.volume", "supply_demand.demand_reentry"}
ALLOWED_OTHER = {"__future__.annotations", "argparse", "ast", "json", "math", "sys", "time",
                 "bisect.bisect_right", "datetime.date", "datetime.datetime",
                 "datetime.timedelta", "pathlib.Path", "typing.Optional", "zoneinfo.ZoneInfo",
                 "numpy", "pandas", "pymongo.collection.Collection"}


def test_the_script_never_imports_key_levels():
    src = (BACKEND / "scripts" / "resiliency_study.py").read_text(encoding="utf-8")
    assert not _KL_RE.search(src)
    assert _KL_RE.search("from supply_demand import key_levels as KL\n")


def test_the_script_imports_only_the_named_modules():
    got = S.imported_modules()
    assert got <= ALLOWED_APP | ALLOWED_OTHER, sorted(got - ALLOWED_APP - ALLOWED_OTHER)
    assert ALLOWED_APP <= got
    # a forbidden import in a mutated copy is seen by the same reader
    import tempfile
    src = (BACKEND / "scripts" / "resiliency_study.py").read_text(encoding="utf-8")
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(src + "\nfrom supply_demand import momentum_burst as MB\n")
    assert "supply_demand.momentum_burst" in S.imported_modules(fh.name)


def test_the_script_never_says_bounce_or_fake():
    src = (BACKEND / "scripts" / "resiliency_study.py").read_text(encoding="utf-8").lower()
    assert "bounce" not in src and "fake" not in src and "won't drop" not in src
