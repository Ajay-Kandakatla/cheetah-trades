"""Strategy lab 2026-10-29 (scripts/strategy_lab_2026_10_29.py) — Mongo-free, network-free,
synthetic bars only. Known answers per candidate, the lookahead / NaN / cost / seal NEGATIVES,
the placebo overlap fix, the settlement book, the guards and the refusals.

NOT RUN on Ajay's data here — every frame below is synthetic.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from chart_maps.gajjala import constants as GC
from scripts import resiliency_study as RS
from scripts import strategy_lab_2026_10_29 as L
from sepa import adr, prices, symbols

ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]
NIGHT = datetime(2026, 10, 29, 20, 0, tzinfo=ET)


# ---------------------------------------------------------------------------
# synthetic builders
# ---------------------------------------------------------------------------
def _days(T, end="2026-10-29"):
    return [d.date().isoformat() for d in pd.bdate_range(end=end, periods=T)]


def _panel(close, open_=None, vol=1e6, syms=None, days=None):
    close = np.asarray(close, dtype=float)
    n, T = close.shape
    opn = close.copy() if open_ is None else np.asarray(open_, dtype=float)
    syms = syms or [f"S{i:03d}" for i in range(n)]
    v = np.full((n, T), float(vol)) if np.isscalar(vol) else np.asarray(vol, dtype=float)
    v = np.where(np.isfinite(close), v, np.nan)
    return {"open": opn, "high": np.fmax(opn, close) * 1.01, "low": np.fmin(opn, close) * 0.99,
            "close": close, "volume": v, "syms": list(syms),
            "sym_arr": np.array(syms, dtype=str), "days": days or _days(T),
            "bench_open": np.full(T, 100.0), "bench_close": np.full(T, 100.0)}


def _iid_panel(seed, drift=0.0, N=200, T=217, mkt_sd=0.01, idio_sd=0.025):
    rng = np.random.default_rng(seed)
    r = rng.normal(drift, mkt_sd, T)[None, :] + rng.normal(0, idio_sd, (N, T))
    P = 100 * np.exp(np.cumsum(r, axis=1))
    return _panel(P)


def _frame(close, days, open_=None, vol=1e6):
    close = np.asarray(close, dtype=float)
    opn = close if open_ is None else np.asarray(open_, dtype=float)
    idx = pd.DatetimeIndex(pd.to_datetime(days))
    return pd.DataFrame({"open": opn, "high": np.fmax(opn, close) * 1.01,
                         "low": np.fmin(opn, close) * 0.99, "close": close,
                         "volume": float(vol)}, index=idx)


def _universe_frames(n_names=40, T=260, seed=2, drift=0.0):
    rng = np.random.default_rng(seed)
    days = _days(T)
    fr = {"SPY": _frame(100 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, T))), days)}
    for i in range(n_names):
        c = 100 * np.exp(np.cumsum(rng.normal(drift, 0.025, T)))
        fr[f"Q{i:03d}X"] = _frame(c, days, vol=1e6 + 1e4 * i)
    return fr, days


def _known_panel():
    """20 names x 80 sessions; PA and PB drop into t0 = 60; PA in at 100, out at 103."""
    n, T, t0 = 20, 80, 60
    syms = [f"N{i:02d}" for i in range(18)] + ["PA", "PB"]
    close = np.full((n, T), 100.0)
    close[18, t0 - 4:] = np.array([98, 96, 94, 92, 90] + [90] * (T - t0 - 1))[:T - t0 + 4]
    close[19, t0 - 4:] = np.array([99, 98, 96, 94, 92] + [92] * (T - t0 - 1))[:T - t0 + 4]
    opn = close.copy()
    opn[18, t0 + 1] = 100.0
    opn[18, t0 + 6] = 103.0
    return _panel(close, opn, syms=syms), t0


@pytest.fixture
def no_key(monkeypatch):
    for k in ("MASSIVE_API_KEY_STOCKS", "MASSIVE_API_KEY"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def restore_guards(monkeypatch):
    """Pre-register every attribute block_network / block_writes replaces, so monkeypatch
    restores them after the test."""
    import requests
    from pymongo.collection import Collection
    for mod, attr, _n in L._NET_TARGETS:
        if hasattr(mod, attr):
            monkeypatch.setattr(mod, attr, getattr(mod, attr))
    monkeypatch.setattr(requests.Session, "request", requests.Session.request)
    for verb in ("request", "get", "post", "put", "delete", "head", "patch"):
        monkeypatch.setattr(requests, verb, getattr(requests, verb))
    for m in RS.WRITE_METHODS:
        if hasattr(Collection, m):
            monkeypatch.setattr(Collection, m, getattr(Collection, m))
    L.ATTEMPTED_FETCHES.clear()
    RS.ATTEMPTED.clear()
    yield
    L.ATTEMPTED_FETCHES.clear()
    RS.ATTEMPTED.clear()


FUND_KW = {"static_fn": lambda: {"SPY"}, "cached_fn": lambda syms: set(),
           "levered_fn": lambda **k: {}, "db": None}


# ---------------------------------------------------------------------------
# 1-2 known answer, cost model
# ---------------------------------------------------------------------------
def test_01_known_answer_selection_opens_and_net():
    p, t0 = _known_panel()
    liq = L.liquidity_panel(p)
    sel = L.c5_select(p, liq, t0)
    assert {p["syms"][s] for s in sel} == {"PA", "PB"}
    o = L.trade_outcome(p, 18, t0, int(liq["rank"][18, t0]))
    assert o["entry_px"] == 100.0 and o["exit_px"] == 103.0 and o["exit_reason"] == "time"
    assert o["entry_date"] == p["days"][t0 + 1] and o["exit_date"] == p["days"][t0 + 6]
    assert o["net_ret"] == pytest.approx(0.0269146281, abs=1e-9)
    assert o["cost_tier"] == 1


def test_01b_known_answer_through_frames_and_build_panel():
    p, t0 = _known_panel()
    frames = {s: _frame(p["close"][i], p["days"], p["open"][i]) for i, s in enumerate(p["syms"])}
    bp = L.build_panel(frames, p["days"])
    liq = L.liquidity_panel(bp)
    assert {bp["syms"][s] for s in L.c5_select(bp, liq, t0)} == {"PA", "PB"}


def test_02_cost_side_boundary_and_tier2_unreachable():
    assert L.cost_side(1000) == pytest.approx(0.0015)
    assert L.cost_side(1001) == pytest.approx(0.0030)
    assert L.C5_UNIVERSE_TOP_N < L.COST_TIER1_TOP_N
    p = _iid_panel(4, N=60, T=120)
    liq = L.liquidity_panel(p)
    _co, tr = L.c5_rows(p, liq, {"oos": L.signal_sessions(120)})
    assert len(tr) and (tr["cost_tier"] == 1).all() and (tr["cost_side"] == 0.0015).all()


# ---------------------------------------------------------------------------
# 3-6 lookahead + NaN gates
# ---------------------------------------------------------------------------
def test_03_NEG_signal_offset_one_is_a_leak(monkeypatch):
    p, t0 = _known_panel()
    liq = L.liquidity_panel(p)
    monkeypatch.setattr(L, "SIGNAL_OFFSET", 1)
    with pytest.raises(L.LeakError):
        L.c5_select(p, liq, t0)


def test_04_NEG_offset_one_with_the_leak_check_disabled_changes_the_trades(monkeypatch):
    p = _iid_panel(5, N=60, T=120)
    liq = L.liquidity_panel(p)
    S = L.signal_sessions(120)
    base = [tuple(L.c5_select(p, liq, t)) for t in S]
    monkeypatch.setattr(L, "SIGNAL_OFFSET", 1)
    monkeypatch.setattr(L, "check_no_leak", lambda *a, **k: None)
    leaked = [tuple(L.c5_select(p, liq, t)) for t in S]
    assert base != leaked


def test_05_NEG_nan_open_at_entry_is_no_trade_and_counted():
    p, t0 = _known_panel()
    p["open"][18, t0 + 1] = np.nan
    liq = L.liquidity_panel(p)
    co, tr = L.c5_rows(p, liq, {"oos": [t0]})
    assert "PA" not in set(tr["sym"]) and "PB" in set(tr["sym"])
    assert co.attrs["skips"]["oos"]["no_entry_bar"] == 1


def test_06_NEG_nan_close_in_the_r5_window_is_not_ranked():
    p, t0 = _known_panel()
    p["close"][18, t0 - 2] = np.nan
    p["volume"][18, t0 - 2] = np.nan
    liq = L.liquidity_panel(p)
    assert np.isnan(L.r_lookback(p["close"], t0)[18])
    assert "PA" not in {p["syms"][s] for s in L.c5_select(p, liq, t0)}


def test_07_NEG_nan_into_statistics_raises():
    with pytest.raises(L.NaNGateError):
        L.cluster_mean_ci([0.01, float("nan")], ["a", "b"])
    with pytest.raises(L.NaNGateError):
        L.moments([1.0, float("nan"), 2.0])


def test_08_NEG_nan_into_artefacts_raises(tmp_path):
    with pytest.raises(ValueError):
        L.write_artefacts(tmp_path, stats={"x": float("nan")})
    d = pd.DataFrame({"date": ["2026-01-02"], "split": ["oos"], "book_gross": [np.nan],
                      "book_net": [0.0], "n_positions": [1], "n_cohorts": [1],
                      "n_sleeves_idle": [5], "spy_ret": [0.0]})
    with pytest.raises(ValueError):
        L.write_artefacts(tmp_path / "b", stats={"x": 1}, daily=d)


# ---------------------------------------------------------------------------
# 9-10 liquidity = the house engine
# ---------------------------------------------------------------------------
def test_09_liquidity_equals_adr_liquidity_check_on_a_holed_frame():
    assert L.LIQ_MIN_DV == 20_000_000 and L.LIQ_PERIOD == 50
    rng = np.random.default_rng(9)
    T = 200
    days = _days(T)
    close = 50 * np.exp(np.cumsum(rng.normal(0, 0.02, T)))
    vol = rng.uniform(2e5, 7e5, T)
    keep = rng.random(T) > 0.2
    fr = pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                       "volume": vol}, index=pd.DatetimeIndex(pd.to_datetime(days)))[keep]
    p = L.build_panel({"H": fr}, days)
    liq = L.liquidity_panel(p)
    seen = set()
    for t in range(T):
        want = adr.liquidity_check(fr[fr.index <= pd.Timestamp(days[t])])["liquid"]
        assert bool(liq["liquid"][0, t]) == bool(want), t
        seen.add(bool(want))
    assert seen == {True, False}


def test_10_NEG_fewer_than_50_own_bars_is_not_liquid():
    close = np.full((1, 80), 100.0)
    close[0, :20] = np.nan
    p = _panel(close, vol=1e7)
    liq = L.liquidity_panel(p)
    own_at = np.cumsum(np.isfinite(close[0]))
    assert not liq["liquid"][0, 68] and liq["liquid"][0, 69]
    for t in range(80):
        assert bool(liq["liquid"][0, t]) == (own_at[t] >= 50), t


# ---------------------------------------------------------------------------
# 11-14 split, seal, last signal, stopped / late exits
# ---------------------------------------------------------------------------
def test_11_split_embargo_and_sealed_slice():
    days = _days(200)
    S = L.signal_sessions(200)
    sp = L.split_sessions(S, days, None)
    idx = sp["idx_oos"]
    assert all(t + 1 + L.C5_HOLD <= idx for t in sp["is"])
    assert all(days[t] >= sp["oos_from"] for t in sp["oos"])
    assert sp["embargo"] and all(t < idx < t + 1 + L.C5_HOLD + 1 for t in sp["embargo"])
    p = _iid_panel(11, N=40, T=200)
    liq = L.liquidity_panel(p)
    _co, tr = L.c5_rows(p, liq, {"is": sp["is"], "oos": sp["oos"]})
    assert not set(tr["t"]) & set(sp["embargo"])
    assert tr[tr["split"] == "is"]["t"].max() + 1 + L.C5_HOLD <= idx
    with pytest.raises(ValueError):
        L.split_sessions(S, days, days[3])


def test_11b_seal_panel_keeps_only_the_seal_day_open():
    p = _iid_panel(12, N=10, T=120)
    sp = L.split_sessions(L.signal_sessions(120), p["days"], None)
    sealed = L.seal_panel(p, sp["idx_oos"])
    assert sealed["close"].shape[1] == sp["idx_oos"] + 1
    for c in ("close", "high", "low", "volume"):
        assert not np.isfinite(sealed[c][:, sp["idx_oos"]:]).any(), c
    assert np.isfinite(sealed["open"][:, sp["idx_oos"]]).all()


def test_11c_NEG_calibrate_ignores_every_oos_bar():
    fr, days = _universe_frames(n_names=30, T=200, seed=13)
    oos_from = L.split_sessions(L.signal_sessions(200), days, None)["oos_from"]
    cut = {}
    for s, f in fr.items():
        if s == "SPY":
            cut[s] = f
            continue
        g = f[f.index <= pd.Timestamp(oos_from)].copy()
        g.loc[pd.Timestamp(oos_from), ["high", "low", "close", "volume"]] = np.nan
        cut[s] = g
    kw = dict(as_of=days[-1], oos_from=oos_from, draws=200, placebo_sets=30, seed=5,
              mode="calibrate", trial_srs=[], types={}, fund_kw=FUND_KW, calib_reps=3)
    a = L.run_c5(fr, **kw)["stats"]
    b = L.run_c5(cut, **kw)["stats"]
    assert a["is"] == b["is"]
    ca, cb = dict(a["calibration"]), dict(b["calibration"])
    ca.pop("runtime_sec"), cb.pop("runtime_sec")
    assert ca == cb and ca["reps_done"] == 3


def test_12_NEG_no_row_after_the_last_signal_session():
    p = _iid_panel(14, N=40, T=120)
    S = L.signal_sessions(120)
    assert S[-1] == 120 - 2 - L.C5_HOLD
    liq = L.liquidity_panel(p)
    co, _tr = L.c5_rows(p, liq, {"oos": S})
    assert co["t"].max() <= S[-1]


def test_13_stopped_name_exits_at_its_last_close_and_delisted_is_kept():
    p, t0 = _known_panel()
    p["close"][18, t0 + 4:] = np.nan
    p["open"][18, t0 + 4:] = np.nan
    p["volume"][18, t0 + 4:] = np.nan
    o = L.trade_outcome(p, 18, t0, 1)
    assert o["exit_reason"] == "data_end" and o["exit_date"] == p["days"][t0 + 3]
    assert o["exit_px"] == p["close"][18, t0 + 3]
    dead = sorted(symbols.DELISTED)[0]
    ex = L.fund_symbols([dead], static_fn=set, cached_fn=lambda s: set(),
                        levered_fn=lambda **k: {}, types={})
    assert all(dead not in ex[r] for r in L.EXCLUSION_REASONS)


def test_14_hole_at_the_nominal_exit_is_a_late_exit_at_the_next_open():
    p, t0 = _known_panel()
    p["open"][18, t0 + 6] = np.nan
    p["close"][18, t0 + 6] = np.nan
    p["open"][18, t0 + 7] = 101.0
    o = L.trade_outcome(p, 18, t0, 1)
    assert o["exit_reason"] == "late_exit" and o["exit_px"] == 101.0
    assert o["exit_date"] == p["days"][t0 + 7]


# ---------------------------------------------------------------------------
# 15-16 exclusions, dedupe
# ---------------------------------------------------------------------------
def test_15_exclusions_by_reason_and_the_kept_names(monkeypatch):
    calls = []

    def lev(**k):
        calls.append(k)
        return {"by_underlying": {"NVDA": [{"etf": "NVDU"}]}}
    syms = ["^GSPC", "XLF", "ABCD", "NVDU", "KRE", "BTC-USD", "BRK-B", "SATS", "WBD", "AAPL"]
    types = {"KRE": "ETF", "BRK-B": "CS", "SATS": "PFD", "ECHO": "CS", "AAPL": "CS"}
    kw = dict(static_fn=lambda: {"XLF"}, cached_fn=lambda s: {"ABCD"}, levered_fn=lev,
              types=types)
    ex = L.fund_symbols(syms, **kw)
    assert ex["index_caret"] == {"^GSPC"} and ex["static_etf"] == {"XLF"}
    assert ex["cached_etf"] == {"ABCD"} and ex["levered_fund"] == {"NVDU"}
    assert ex["crypto_pair"] == {"BTC-USD"} and ex["type_not_equity"] == {"KRE"}
    excluded = set().union(*(ex[r] for r in L.EXCLUSION_REASONS))
    assert {"BRK-B", "SATS", "WBD", "AAPL"}.isdisjoint(excluded)
    assert ex["kept_unknown_type"] == {"WBD"}
    assert calls and all(c.get("ensure") is False for c in calls)
    monkeypatch.setattr(GC, "SCAN_UNKNOWN_TYPE_POLICY", "drop")
    assert L.fund_symbols(syms, **kw) == ex


def test_16_dedupe_keeps_the_later_doc():
    assert symbols.resolve("SQ") == "XYZ"
    sq = _frame(np.full(10, 50.0), _days(10, end="2026-09-14"))
    xyz = _frame(np.full(10, 60.0), _days(10, end="2026-10-29"))
    kept, merged = L.canonical_dedupe({"SQ": sq, "XYZ": xyz, "AAPL": xyz})
    assert set(kept) == {"XYZ", "AAPL"} and merged == 1


# ---------------------------------------------------------------------------
# 17-21 statistics
# ---------------------------------------------------------------------------
def test_17_cluster_ci_reproducible_and_equal_to_the_house_bootstrap():
    rng = np.random.default_rng(3)
    x = rng.normal(0.002, 0.01, 200)
    cl = np.repeat(np.arange(40), 5).astype(str)
    a = L.cluster_mean_ci(x, cl, draws=400, seed=9)
    assert a == L.cluster_mean_ci(x, cl, draws=400, seed=9)
    d, nc = L.cluster_draws(x * 100, cl, draws=400, seed=9)
    inv = np.unique(cl, return_inverse=True)[1]
    num, w = np.bincount(inv, weights=x), np.bincount(inv).astype(float)
    ref = RS.boot_draws([(num, w)], 400, 9)[0] * 100
    assert nc == 40 and np.allclose(d, ref)


def test_17b_units_fix_is_load_bearing():
    wk = np.random.default_rng(1).normal(0.004, 0.006, 31)
    weeks = [f"w{i:02d}" for i in range(31)]
    r = L.cluster_mean_ci(wk, weeks, draws=10_000, seed=7)
    assert r["word"] == "separates" and r["ci_raw_pct"][0] > 0
    assert r["mean_pct"] == pytest.approx(100 * wk.mean(), abs=1e-3)
    assert r["ci_raw_pct"][1] > 0.1
    assert r["ci_raw_pct"][0] != round(r["ci_raw_pct"][0], 4)
    d = RS.boot_draws([(wk, np.ones(31))], 10_000, 7)[0]
    assert RS.verdict(31, RS.ci_of(d, dp=2)) == "no_signal"


def test_18_psr_dsr_known_answers():
    assert L.psr(0.1, 0, 101, 0, 3) == pytest.approx(0.840741, abs=1e-6)
    assert L.psr(0.1, 0, 101, -1, 6) == pytest.approx(0.828458, abs=1e-6)
    assert L.dsr_sr0([0.05, 0.15]) == pytest.approx(0.036752, abs=1e-6)
    assert L.psr(0.1, 0.036752, 101, 0, 3) == pytest.approx(0.735948, abs=1e-6)
    assert L.dsr_sr0([0.05, 0.10, 0.15, 0.20]) == pytest.approx(0.067914, abs=1e-6)
    x = np.random.default_rng(2).normal(0.1, 1, 80)
    d = L.deflated(x, [])
    assert d["N"] == 1 and d["sr0"] == 0.0 and d["dsr"] == pytest.approx(d["psr0"])


def _cohort_frame(seed, n_sym=40, T=175):
    rng = np.random.default_rng(seed)
    rows = [{"sym": f"Z{s:02d}", "t": t, "month": f"m{t // 21}", "split": "oos",
             "net_ret": rng.normal(0, 0.02), "entry_week": f"w{(t + 1) // 5:03d}",
             "signal_date": f"d{t:03d}"} for s in range(n_sym) for t in range(T)]
    return pd.DataFrame(rows)


def test_19_placebo_random_selection_fails_and_a_planted_lift_passes():
    co = _cohort_frame(19)
    rng = np.random.default_rng(1)
    pick = rng.random(len(co)) < 0.1
    tr = co[pick].assign(row=np.flatnonzero(pick)).reset_index(drop=True)
    b = L.placebo(tr, co, sets=200, draws=2000)
    assert b["pass"] is False
    co2 = co.copy()
    co2.loc[pick, "net_ret"] += 0.02
    tr2 = co2[pick].assign(row=np.flatnonzero(pick)).reset_index(drop=True)
    b2 = L.placebo(tr2, co2, sets=200, draws=2000)
    assert b2["pass"] is True and b2["beat_share"] >= 0.95
    assert b2["diff"]["n_clusters"] >= 35


def _null_rows(seed, drift):
    p = _iid_panel(seed, drift=drift)
    liq = L.liquidity_panel(p)
    S = L.signal_sessions(p["close"].shape[1])
    return L.c5_rows(p, liq, {"oos": S})


def test_19b_placebo_overlap_fix_on_an_iid_null_and_the_v1_defect_reproduced():
    fixed, v1 = 0, 0
    for seed in range(20):
        co, tr = _null_rows(seed, 0.0)
        assert tr["entry_week"].nunique() >= 30
        fixed += L.placebo(tr, co, sets=200, draws=2000, seed=seed)["pass"]
        v1 += L.placebo(tr, co, sets=200, draws=2000, seed=seed, exclude_back=0)["pass"]
    assert fixed <= 1, fixed
    assert v1 >= 15, v1


def test_20_NEG_iid_nulls_are_not_positive():
    for drift in (0.0, 0.0012):
        pos = 0
        for seed in range(20):
            co, tr = _null_rows(100 + seed, drift)
            g = L.gate_block(tr, co, draws=1000, placebo_sets=100, seed=seed, trial_srs_others=[])
            v = L.positive_verdict(g["A"]["pass"], g["B"]["pass"], g["C"]["pass"],
                                   g["A"]["n_clusters"])
            pos += v["word"] == "POSITIVE"
        assert pos <= 1, (drift, pos)


def test_21_NEG_29_weeks_is_too_small():
    assert L.positive_verdict(True, True, True, 29)["word"] == "TOO SMALL"
    assert L.positive_verdict(True, True, True, 30)["word"] == "POSITIVE"
    assert L.positive_verdict(True, False, True, 31)["word"] == "NOT POSITIVE"


# ---------------------------------------------------------------------------
# 22-26 refusals, guards, import scope
# ---------------------------------------------------------------------------
def _boom(*a, **k):
    raise AssertionError("must not be called")


def _rc(argv, **kw):
    return L.main(argv, now=kw.pop("now", NIGHT), frames_fn=_boom, symbols_fn=_boom,
                  types_fn=_boom, block=False, **kw)


def test_22_NEG_refusals(tmp_path, monkeypatch, no_key):
    out = str(tmp_path / "o")
    base = ["--candidate", "c5_reversal", "--out", out]
    assert _rc(base + ["--smoke"], now=datetime(2026, 10, 29, 10, 0, tzinfo=ET)) == 2
    prereg = tmp_path / "p.md"
    prereg.write_text("x")
    full = ["--prereg", str(prereg), "--prereg-commit", "abcdef123456", "--oos-from",
            "2026-03-20", "--ledger", str(tmp_path / "l.json")]
    monkeypatch.setattr(L, "REFUSED_LEDGER_ROOTS", ())
    monkeypatch.setattr(L, "LEDGER_PATH", str(tmp_path / "l.json"))
    for drop in range(4):
        argv = full[:2 * drop] + full[2 * drop + 2:]
        assert _rc(base + argv) == 2, argv
    assert _rc(["--candidate", "c5_reversal", "--out", str(BACKEND / "x"), "--smoke"]) == 2
    assert _rc(base + ["--smoke", "--calibrate", "--oos-from", "2026-03-20"]) == 2
    assert _rc(base + ["--calibrate"]) == 2
    assert _rc(base + ["--stride", "3"] + full) == 2
    for bad in ("placeholder", "<hash>", "TBD", "abc12"):
        assert _rc(base + ["--prereg", str(prereg), "--prereg-commit", bad, "--oos-from",
                           "2026-03-20", "--ledger", str(tmp_path / "l.json")]) == 2, bad
    monkeypatch.setattr(L, "REFUSED_LEDGER_ROOTS", ("/tmp", "/private/tmp"))
    for led in ("/tmp/x.json", "/private/tmp/x.json"):
        assert _rc(base + ["--prereg", str(prereg), "--prereg-commit", "abcdef123456",
                           "--oos-from", "2026-03-20", "--ledger", led]) == 2, led
    monkeypatch.setenv("MASSIVE_API_KEY_STOCKS", "dummy-not-a-key")
    assert _rc(base + ["--smoke"]) == 2
    assert not Path(out).exists()


@pytest.mark.parametrize("cand", ["c1_ath_atr10", "c2_xsmom_12_1", "c3_ear_drift",
                                  "c4_spy_sma10m"])
def test_23_NEG_unmeasurable_candidates_exit_3_read_nothing(tmp_path, cand, no_key):
    led = tmp_path / "ledger.json"
    rc = _rc(["--candidate", cand, "--out", str(tmp_path / cand), "--ledger", str(led)])
    assert rc == 3 and not led.exists()
    st = json.loads((tmp_path / cand / "status.json").read_text())
    assert st["status"] == "unmeasurable" and st["candidate"] == cand


def test_24_NEG_block_network_refuses_every_fetch(restore_guards):
    import requests
    from chart_maps.gajjala import scanner
    L.block_network()
    with pytest.raises(L.FetchRefused):
        prices._fetch_massive("AAPL", "2y")
    with pytest.raises(L.FetchRefused):
        prices.load_prices("AAPL")
    with pytest.raises(L.FetchRefused):
        requests.Session().get("http://example.invalid")
    with pytest.raises(L.FetchRefused):
        scanner.fetch_type_map()
    assert L.ATTEMPTED_FETCHES == ["prices._fetch_massive", "prices.load_prices",
                                   "requests.Session.request", "scanner.fetch_type_map"]


def test_25_writes_are_recorded_no_ops(restore_guards):
    from pymongo.collection import Collection
    RS.block_writes()

    class _Fake:
        name = "price_cache"
    assert Collection.create_index(_Fake(), [("symbol", 1)]) == "blocked_index"
    assert Collection.insert_one(_Fake(), {"x": 1}) is None
    assert RS.ATTEMPTED == ["price_cache.create_index", "price_cache.insert_one"]


_FORBIDDEN_IMPORTS = ("trading", "alpaca", "autopilot", "notifications",
                      "supply_demand.alert_gates", "supply_demand.key_levels")


def test_26_import_scope_static_and_transitive():
    got = L.imported_modules()
    for m in got:
        assert not m.startswith(_FORBIDDEN_IMPORTS), m
    assert {"scripts.resiliency_study", "scripts.explosive_study.MIN_BUCKET_N", "sepa.prices",
            "sepa.adr", "chart_maps.gajjala.scanner"} <= got
    code = ("import sys; sys.path.insert(0, %r); import scripts.strategy_lab_2026_10_29; "
            "print('\\n'.join(sorted(sys.modules)))" % str(BACKEND))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120,
                       env={"PATH": "/usr/bin:/bin", "HOME": str(Path.home()),
                            "PYTHONDONTWRITEBYTECODE": "1"})
    assert r.returncode == 0, r.stderr[-800:]
    mods = r.stdout.split()
    broker = [m for m in mods if m.split(".")[0] in ("trading", "alpaca", "alpaca_trade_api",
                                                     "autopilot", "notifications")]
    assert broker == [], broker


# ---------------------------------------------------------------------------
# 27-30 report, settlement, ledger, book
# ---------------------------------------------------------------------------
def _assert_clean(text):
    assert L.forbidden_hits(text) == []


def test_27a_NEG_the_word_guard_catches_every_word_and_spares_ledger():
    for w in L.FORBIDDEN_WORDS:
        assert L.forbidden_hits(f"x {w} y") == [w], w
    assert sorted(L.forbidden_hits("an edges case; a prediction")) == ["edge", "predict"]
    assert L.forbidden_hits("--ledger /research/strategy_lab_ledger.json; hedge") == []


def test_27_report_words_positive_text_unmeasured_and_label():
    stats = {"mode": "smoke", "as_of": "2026-10-29", "calendar": {"first_day": "2024-10-29"},
             "split": {"oos_from": "2026-03-20", "oos_weeks": 31}, "universe": {},
             "costs": {"tier1_bps_side": 15.0}, "is": {"label": "IS: survivors only"},
             "calibration": None}
    rep = L.render_report(stats)
    _assert_clean(rep)
    assert L.POSITIVE_TEXT in rep and "UNMEASURED" in rep and "CI calibration" in rep
    for name in L.UNMEASURED_NAMES.values():
        assert name in rep
    assert "survivor-biased in the rule's favour" in L.SURVIVOR_LABEL
    v = L.positive_verdict(True, True, True, 31)
    assert v["label"] == L.SURVIVOR_LABEL
    assert L.POSITIVE_TEXT.startswith("## POSITIVE (exact definition, all three required)")
    assert L.POSITIVE_TEXT.rstrip().endswith("A pass on survivor-biased data is labelled "
                                             "provisional.")
    _assert_clean(" ".join(L.LIMITS) + L.RULE_TEXT + L.SURVIVOR_LABEL)


def _book_panel():
    T = 30
    close = np.full((2, T), 100.0)
    opn = close.copy()
    opn[0, 15] = 110.0
    return _panel(close, opn, syms=["B1", "B2"])


def _tr(rows):
    cols = ["s", "e", "x", "exit_reason", "entry_px", "exit_px", "cost_side", "split",
            "cohort_n", "mdv20"]
    return pd.DataFrame(rows, columns=cols)


def test_28_settlement_six_sleeves_pass_five_and_early_late_cash_raise():
    assert L.BOOK_SLEEVES == L.C5_HOLD + L.SETTLE_SESSIONS == 6
    p = _book_panel()
    six = _tr([(0, 10, 15, "time", 100.0, 110.0, 0.0015, "oos", 1, 1e8),
               (1, 16, 21, "time", 100.0, 100.0, 0.0015, "oos", 1, 1e8)])
    L.daily_book(six, p, p["days"])
    five = _tr([(0, 10, 15, "time", 100.0, 110.0, 0.0015, "oos", 1, 1e8),
                (1, 15, 20, "time", 100.0, 100.0, 0.0015, "oos", 1, 1e8)])
    with pytest.raises(L.SettlementError):
        L.daily_book(five, p, p["days"], sleeves=5)
    sched = pd.DataFrame([{"sleeve": 0, "sale_idx": 12, "buy_idx": 12, "reason": "late_exit"}])
    with pytest.raises(L.SettlementError):
        L.check_settlement(sched)
    L.check_settlement(pd.DataFrame([{"sleeve": 0, "sale_idx": 12, "buy_idx": 13,
                                      "reason": "late_exit"}]))


def test_29_ledger_idempotent_and_a_changed_prereg_raises(tmp_path):
    led = tmp_path / "ledger.json"
    e = {"trial_id": "T01", "prereg_sha256": "a" * 64, "as_of": "2026-10-29",
         "sr_per_entry_day": 0.1}
    assert len(L.ledger_append(led, e)) == 1
    assert len(L.ledger_append(led, dict(e, sr_per_entry_day=0.2))) == 1
    assert L.ledger_trial_srs(json.loads(led.read_text())) == [0.2]
    assert len(L.ledger_append(led, dict(e, as_of="2026-11-30"))) == 2
    with pytest.raises(ValueError):
        L.ledger_append(led, dict(e, prereg_sha256="b" * 64))
    assert len(json.loads(led.read_text())) == 2


def test_30_daily_book_and_capacity_known_answers():
    p = _book_panel()
    tr = _tr([(0, 10, 15, "time", 100.0, 110.0, 0.0015, "oos", 2, 1e8),
              (1, 10, 15, "time", 100.0, 100.0, 0.0015, "oos", 2, 5e7)])
    d = L.daily_book(tr, p, p["days"])
    c = 0.0015
    assert np.prod(1 + d["book_gross"]) == pytest.approx(5 / 6 + 1.1 / 12 + 1.0 / 12, abs=1e-12)
    want = 5 / 6 + (1.1 * (1 - c) / (1 + c)) / 12 + ((1 - c) / (1 + c)) / 12
    assert np.prod(1 + d["book_net"]) == pytest.approx(want, abs=1e-12)
    assert d["n_positions"].iloc[0] == 2 and d["n_sleeves_idle"].iloc[0] == 5
    assert L.capacity_usd(tr) == pytest.approx(6 * 2 * 0.01 * 5e7)


# ---------------------------------------------------------------------------
# 31 end to end
# ---------------------------------------------------------------------------
def _no_nan(text):
    json.loads(text, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))


def test_31_main_end_to_end_smoke_calibrate_outcome(tmp_path, monkeypatch, no_key,
                                                    restore_guards):
    from chart_maps.gajjala import scanner
    monkeypatch.setattr(scanner, "fetch_type_map", _boom)
    monkeypatch.setattr(scanner, "ensure_type_map", _boom)
    monkeypatch.setattr(L, "REFUSED_LEDGER_ROOTS", ())

    fr, days = _universe_frames(n_names=40, T=260, seed=21)
    syms = [s for s in fr if s != "SPY"]
    pairs = [[s, "CS"] for s in syms]

    class _State:
        def find_one(self, q):
            assert q == {"_id": L.TYPES_STATE_ID}
            return {"_id": "types", "as_of": days[-1], "complete": True, "pairs": pairs}

    class _Db(dict):
        def __getitem__(self, k):
            assert k == "gajjala_state"
            return _State()

    class _Coll:
        name = "price_cache"
        database = _Db()

        def distinct(self, key):
            return list(fr)
    the_coll = _Coll()

    def fake_mongo():
        from pymongo.collection import Collection
        Collection.create_index(the_coll, [("symbol", 1)], unique=True)
        return the_coll
    monkeypatch.setattr(prices, "_get_mongo", fake_mongo)
    kw = dict(frames_fn=lambda ss: {s: fr[s] for s in ss if s in fr}, fund_kw=FUND_KW,
              calib_reps=2, now=NIGHT)
    oos_from = L.split_sessions(L.signal_sessions(260), days, None)["oos_from"]
    small = ["--draws", "200", "--placebo-sets", "30"]

    sm = tmp_path / "smoke"
    rc = L.main(["--candidate", "c5_reversal", "--smoke", "--stride", "1", "--out", str(sm)]
                + small, block=True, **kw)
    assert rc == 0
    out_text = (sm / "run.log").read_text()
    assert "mean" not in out_text.lower()
    st = json.loads((sm / "stats.json").read_text())
    _no_nan((sm / "stats.json").read_text())
    assert st["oos"] == {"sealed": True} and st["mode"] == "smoke"
    assert st["attempted_writes"] == ["price_cache.create_index"]
    assert st["attempted_fetches"] == []
    assert not (sm / "trades.json").exists()

    cal = tmp_path / "c5" / "calibration"
    rc = L.main(["--candidate", "c5_reversal", "--calibrate", "--oos-from", oos_from, "--out",
                 str(cal)] + small, block=False, **kw)
    assert rc == 0
    cj = json.loads((cal / "calibration.json").read_text())
    assert cj["reps_done"] == 2 and all(w["last_week"] < oos_from for w in cj["windows"])

    prereg = tmp_path / "prereg.md"
    prereg.write_text("# prereg\n")
    led = tmp_path / "research" / "ledger.json"
    led.parent.mkdir()
    monkeypatch.setattr(L, "LEDGER_PATH", str(led))
    outd = tmp_path / "c5"
    rc = L.main(["--candidate", "c5_reversal", "--oos-from", oos_from, "--prereg", str(prereg),
                 "--prereg-commit", "abcdef1234567", "--ledger", str(led), "--out", str(outd)]
                + small, block=False, **kw)
    assert rc == 0
    st = json.loads((outd / "stats.json").read_text())
    for k in ("study", "script", "candidate", "trial_id", "params", "prereg", "prereg_sha256",
              "prereg_commit", "mode", "run_date", "as_of", "calendar", "signal_sessions",
              "split", "universe", "skips", "costs", "oos", "is", "calibration", "mde",
              "verdict", "limits", "attempted_writes", "attempted_fetches", "runtime_sec"):
        assert k in st, k
    for k in ("excluded_by_reason", "excluded_symbols_by_reason", "kept_unknown_type",
              "type_map_as_of", "dupes_merged", "docs_stopped", "names_ever_eligible",
              "stopped_names_ever_eligible"):
        assert k in st["universe"], k
    assert set(st["universe"]["docs_stopped"]) == {"ended_before_2026_05", "ended_before_oos",
                                                   "stopped_in_oos_active",
                                                   "stopped_in_oos_not_active"}
    assert st["costs"]["tier2_trades"] == 0 and "breakeven_bps_side" in st["costs"]
    assert st["prereg_sha256"] == L.prereg_sha256(prereg)
    assert st["verdict"]["word"] in ("POSITIVE", "NOT POSITIVE", "TOO SMALL")
    assert st["calibration"]["reps_done"] == 2
    for f in ("stats.json", "trades.json", "connector_payloads.json"):
        _no_nan((outd / f).read_text())
    pay = (outd / "connector_payloads.json").read_text()
    assert not any(s in pay for s in syms)
    rep = (outd / "report.md").read_text()
    _assert_clean(rep)
    assert L.POSITIVE_TEXT in rep and "CI calibration" in rep
    trades = json.loads((outd / "trades.json").read_text())
    assert trades and set(trades[0]) == set(L.TRADE_KEYS)
    assert max(t["signal_date"] for t in trades) <= days[L.signal_sessions(260)[-1]]
    rows = json.loads(led.read_text())
    assert len(rows) == 1 and rows[0]["trial_id"] == "T01"
    daily = pd.read_csv(outd / "daily.csv")
    assert set(daily["split"]) <= {"is", "oos"} and np.isfinite(daily["book_net"]).all()


# ---------------------------------------------------------------------------
# 32-36 v2 hygiene, docs split, gate C series, break-even, calibration
# ---------------------------------------------------------------------------
def test_32_scale_glitches_in_signal_and_hold_and_a_2to1_step_is_listed():
    n, T, t0 = 20, 80, 60
    syms = [f"G{i:02d}" for i in range(n)]
    close = np.full((n, T), 100.0)
    close[0, t0 - 2:] = 10.0
    close[1, t0 + 3:] = 10.0
    close[2, t0 + 3:] = 50.0
    p = _panel(close, syms=syms)
    liq = L.liquidity_panel(p)
    assert int(liq["rank"][0, t0]) > 0 and int(liq["rank"][1, t0]) > 0
    assert np.isnan(L.r_lookback(p["close"], t0, glitch=L._aux(p)["glitch"])[0])
    assert 0 not in L.c5_select(p, liq, t0)
    co, tr = L.c5_rows(p, liq, {"oos": [t0]})
    assert co.attrs["cohort_skips"]["oos"]["scale_glitch_signal"] >= 1
    assert "G01" in set(co["sym"]) and bool(co.loc[co["sym"] == "G01", "glitch_hold"].iloc[0])
    assert "scale_glitch_hold" not in co.attrs["cohort_skips"]["oos"]
    assert co.attrs["cohort_flags"]["oos"]["scale_glitch_hold"] == 1
    assert "G02" in set(co["sym"]) and not co.loc[co["sym"] == "G02", "glitch_hold"].any()
    moves = L.largest_moves(p, co)
    assert moves[0]["sym"] == "G01" and moves[0]["open_vs_prev_close_pct"] == pytest.approx(90.0)
    assert moves[1]["sym"] == "G02" and moves[1]["date"] == p["days"][t0 + 3]
    assert moves[1]["open_vs_prev_close_pct"] == pytest.approx(50.0)


def test_33_docs_stopped_split_buckets():
    def fr(end, n=30):
        return _frame(np.full(n, 10.0), _days(n, end=end))
    frames = {"A": fr("2025-07-15"), "B": fr("2026-04-15"), "C": fr("2026-08-14"),
              "D": fr("2026-08-14"), "E": fr("2026-10-26")}
    out = L.docs_stopped_split(frames, as_of="2026-10-29", oos_from="2026-03-20",
                               types={"C": "CS", "E": "CS"})
    assert out == {"ended_before_oos": 1, "ended_before_2026_05": 1, "stopped_in_oos_active": 1,
                   "stopped_in_oos_not_active": 1}
    assert not prices.is_stale(frames["E"], pd.Timestamp("2026-10-29"),
                               max_trading_days=L.STOPPED_SESSIONS)


def test_34_gate_c_series_is_per_entry_day():
    tr = pd.DataFrame({"t": [5, 5, 6, 6], "net_ret": [0.01, 0.03, -0.01, 0.0]})
    day = L.gate_c_series(tr)
    assert L.GATE_C_SERIES == "per_entry_day"
    assert len(day) == 2 and day == pytest.approx([2.0, -0.5])
    assert len(L.gate_c_series(tr, "per_trade")) == 4 != len(day)
    with pytest.raises(ValueError):
        L.gate_c_series(tr, "per_week")


def test_35_breakeven_cost_per_side():
    tr = pd.DataFrame({"gross_ret": [0.003] * 5})
    assert L.breakeven_cost_bps(tr) == pytest.approx(14.978, abs=1e-3)
    g, c = 0.003, L.breakeven_cost_bps(tr) / 1e4
    assert (1 + g) * (1 - c) / (1 + c) - 1 == pytest.approx(0.0, abs=1e-12)
    assert L.breakeven_cost_bps(pd.DataFrame({"gross_ret": [0.0, -0.001]})) is None


def test_36_calibrate_null_rates_deterministic_and_refuses_an_unsealed_panel():
    p = _iid_panel(36, N=60, T=220)
    sp = L.split_sessions(L.signal_sessions(220), p["days"], None)
    sealed = L.seal_panel(p, sp["idx_oos"])
    liq = L.liquidity_panel(sealed)
    a = L.calibrate_null(sealed, liq, sp, reps=4, draws=200, placebo_sets=30, seed=3)
    b = L.calibrate_null(sealed, liq, sp, reps=4, draws=200, placebo_sets=30, seed=3)
    a.pop("runtime_sec"), b.pop("runtime_sec")
    assert a == b and a["reps_done"] == 4 and len(a["windows"]) == 2
    for blk in a["pooled"].values():
        assert 0.0 <= blk["rate"] <= 1.0
    with pytest.raises(L.LeakError):
        L.calibrate_null(p, L.liquidity_panel(p), sp, reps=1, draws=50, placebo_sets=5)


# ---------------------------------------------------------------------------
# 37-40 glitch fix 2026-10-29: A and B pass with AND without the flagged rows; > 5% -> no word
# ---------------------------------------------------------------------------
def _plant_splits(p, liq, seed, k, days=(70, 195)):
    """The audit probe (critic_re/glitch_up.py): a 10x unadjusted reverse split 3 sessions into
    the hold of a selected name on k distinct signal days."""
    rng = np.random.default_rng(seed + 99)
    for t in rng.choice(np.arange(*days), size=k, replace=False):
        s = int(L.c5_select(p, liq, int(t))[0])
        p.pop("_aux", None)
        for c in ("open", "close", "high", "low"):
            p[c][s, t + 3:] = p[c][s, t + 3:] * 10.0
        liq = L.liquidity_panel(p)
    return p, liq


def _lifted_panel(seed, lift=0.01, N=200):
    """A planted genuine positive: every selected name gets +lift from t+2 on (inside its hold,
    far below the 5x glitch engine)."""
    p = _iid_panel(seed, N=N, T=217)
    liq = L.liquidity_panel(p)
    for t in range(60, 205):
        for s in L.c5_select(p, liq, t):
            for c in ("open", "close", "high", "low"):
                p[c][s, t + 2:] = p[c][s, t + 2:] * (1 + lift)
    p.pop("_aux", None)
    return p, L.liquidity_panel(p)


def _gates(p, liq):
    co, tr = L.c5_rows(p, liq, {"oos": list(range(60, 205))})
    g = L.gate_block(tr, co, draws=2000, placebo_sets=200, seed=5, trial_srs_others=[])
    return co, tr, g


def _outcome_report(g, v):
    stats = {"mode": "outcome", "verdict": v, "oos": g, "as_of": "2026-10-29",
             "calendar": {"first_day": "2026-01-02"}, "split": {"oos_weeks": 31},
             "universe": {}, "costs": {"tier1_bps_side": 15.0}, "calibration": None}
    return L.render_report(stats)


def test_37_NEG_planted_splits_in_an_iid_null_print_no_positive():
    p = _iid_panel(2, N=500, T=217)
    p, liq = _plant_splits(p, L.liquidity_panel(p), 2, 4)
    co, tr, g = _gates(p, liq)
    v = L.verdict_of(g)
    old = L.positive_verdict(g["A"]["pass"], g["B"]["pass"], g["C"]["pass"],
                             g["A"]["n_clusters"])
    assert old["word"] == "POSITIVE"
    assert 0 < v["n_flagged"] == int(tr["glitch_hold"].sum())
    assert v["n_flagged"] <= L.GLITCH_VERDICT_MAX_SHARE * len(tr)
    assert v["A"] and v["B"] and not v["A_clean"] and not v["B_clean"]
    assert v["word"] == "NOT POSITIVE" and v["label"] is None
    rep = _outcome_report(g, v)
    _assert_clean(rep)
    assert "**Verdict: NOT POSITIVE**" in rep and "**Verdict: POSITIVE**" not in rep
    assert f"n_flagged {v['n_flagged']} of {len(tr)} trade rows" in rep
    assert f"| A without the {v['n_flagged']} flagged rows |" in rep
    assert "| B without the flagged rows (trades and pool) |" in rep


def test_38_a_clean_planted_positive_still_prints_positive():
    p, liq = _lifted_panel(7)
    co, tr, g = _gates(p, liq)
    v = L.verdict_of(g)
    assert v["n_flagged"] == 0 and g["clean"]["A"] is g["A"] and g["clean"]["B"] is g["B"]
    assert v["word"] == "POSITIVE" and v["label"] == L.SURVIVOR_LABEL
    rep = _outcome_report(g, v)
    _assert_clean(rep)
    assert "**Verdict: POSITIVE**" in rep and "n_flagged 0 of" in rep
    p2, liq2 = _plant_splits(*_lifted_panel(7), 7, 2)
    _, tr2, g2 = _gates(p2, liq2)
    v2 = L.verdict_of(g2)
    assert 0 < v2["n_flagged"] <= L.GLITCH_VERDICT_MAX_SHARE * len(tr2)
    assert g2["clean"]["A"]["n"] == len(tr2) - v2["n_flagged"]
    assert v2["A_clean"] and v2["B_clean"] and v2["word"] == "POSITIVE"


def test_39_NEG_more_than_5pct_flagged_prints_no_verdict_word():
    assert L.GLITCH_VERDICT_MAX_SHARE == 0.05
    kw = {"a_clean": True, "b_clean": True}
    assert L.positive_verdict(True, True, True, 31, n_flagged=5, n_rows=100, **kw)["word"] \
        == "POSITIVE"
    for a, b, c in ((True, True, True), (False, False, False)):
        v = L.positive_verdict(a, b, c, 31, n_flagged=6, n_rows=100, **kw)
        assert v["word"] == L.UNMEASURED_GLITCH == "UNMEASURED-glitch" and v["label"] is None
    assert L.positive_verdict(True, True, True, 29, n_flagged=6, n_rows=100)["word"] \
        == L.UNMEASURED_GLITCH
    assert not L.glitch_share_exceeded(0, 0) and L.glitch_share_exceeded(1, 19)
    p, liq = _lifted_panel(7)
    _, tr, g = _gates(p, liq)
    g["clean"] = dict(g["clean"], n_flagged=int(0.05 * len(tr)) + 1)
    v = L.verdict_of(g)
    assert v["word"] == L.UNMEASURED_GLITCH
    rep = _outcome_report(g, v)
    _assert_clean(rep)
    head = rep.split("\n")[2]
    assert head.startswith("**UNMEASURED-glitch: no verdict word**")
    for w in ("Verdict:", "POSITIVE", "TOO SMALL"):
        assert w not in head, w
    assert f"n_flagged {v['n_flagged']} of {len(tr)}" in head


def test_40_NEG_either_clean_gate_failing_is_not_positive():
    for ac, bc in ((False, True), (True, False), (False, False)):
        v = L.positive_verdict(True, True, True, 31, a_clean=ac, b_clean=bc, n_flagged=1,
                               n_rows=100)
        assert v["word"] == "NOT POSITIVE", (ac, bc)
    assert L.positive_verdict(True, True, True, 31, a_clean=True, b_clean=True, n_flagged=1,
                              n_rows=100)["word"] == "POSITIVE"
    assert L.positive_verdict(True, False, True, 31, a_clean=True, b_clean=True)["word"] \
        == "NOT POSITIVE"


def test_41_c3_fact_cites_the_overwrite_lines():
    f = L.EARNINGS_DATES_FACT
    assert "earnings_watch.py:99-107 and :240-250" in f and "151-162" not in f
    src = (BACKEND / "sepa" / "earnings_watch.py").read_text().splitlines()
    assert "last_report" in "\n".join(src[98:107])
    assert "replace_one" in "\n".join(src[239:250])
