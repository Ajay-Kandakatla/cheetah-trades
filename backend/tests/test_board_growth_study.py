"""WP1 tests for `scripts/board_growth_study.py` (Study A + B-trailing).

Everything here runs WITHOUT Mongo and WITHOUT the container caches, on
synthetic frames. The pure helpers are pinned against the worktree functions
they replicate (`sepa/trend_template.py` for the 52-week high and the 25%
literal), and every negative case the spec names has its own assertion —
including the two that are absences rather than behaviours: there is NO
"beaten down" constant anywhere in the module, and `NoWriteDB` refuses every
collection method so `sepa.bonde.board` cannot stamp `bonde_seen`.

Nothing in this package changes a shipped rule, gate or threshold.
"""
from __future__ import annotations

import contextlib
import gzip
import json
import os
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from scripts import board_growth_study as S
from sepa import trend_template as TT


# ── fixtures ─────────────────────────────────────────────────────────────────
def _frame(n: int = 300, seed: int = 3, base: float = 100.0) -> pd.DataFrame:
    """A daily OHLCV frame `trend_template.evaluate` accepts (needs >= 220)."""
    rng = np.random.default_rng(seed)
    step = rng.normal(0.05, 1.0, n)
    close = np.maximum(base + np.cumsum(step), 5.0)
    wick = np.abs(rng.normal(0, 0.7, n)) + 0.05
    idx = pd.bdate_range("2025-01-02", periods=n)
    return pd.DataFrame({"open": close - step * 0.5, "high": close + wick,
                         "low": close - wick, "close": close,
                         "volume": rng.integers(1e5, 1e6, n).astype(float)},
                        index=idx)


def _flat_frame(n: int, last: float, high: float) -> pd.DataFrame:
    """A frame whose 252-bar max is `high` and whose last close is `last`."""
    close = np.full(n, high * 0.9, dtype=float)
    close[n - 30] = high
    close[-1] = last
    idx = pd.bdate_range("2025-01-02", periods=n)
    return pd.DataFrame({"open": close, "high": close, "low": close,
                         "close": close, "volume": np.full(n, 5e5)}, index=idx)


@pytest.fixture(autouse=True)
def _clear_price_memo():
    S._PRICE_CACHE.clear()
    yield
    S._PRICE_CACHE.clear()


# ── the module is importable with no Mongo, and says what it is ──────────────
def test_module_imports_with_no_mongo_and_carries_the_run_block():
    doc = S.__doc__ or ""
    assert "NOT A SIGNAL, NOT A GATE — research only (Rule #10)" in doc
    assert "/tmp/scripts" in doc and "PYTHONPATH=/tmp:/app" in doc
    assert S.HEADER.startswith("NOT A SIGNAL")


def test_constants_are_imported_never_retyped():
    from rotation.backtest import BENCHMARK, LOOKBACK, REBALANCE
    from sepa.sales import SALES_EXPLOSIVE_PCT, SALES_FLOOR_PCT
    from growth.tracker import MIN_EPS_GROWTH_PCT, MIN_SALES_GROWTH_PCT

    assert S.BENCHMARK is BENCHMARK == "RSP"
    assert dict(S.WINDOWS)["1m"] == REBALANCE
    assert dict(S.WINDOWS)["3m"] == LOOKBACK
    assert S.SALES_EXPLOSIVE_PCT is SALES_EXPLOSIVE_PCT
    assert S.SALES_FLOOR_PCT is SALES_FLOOR_PCT
    assert S.MIN_SALES_GROWTH_PCT is MIN_SALES_GROWTH_PCT
    assert S.MIN_EPS_GROWTH_PCT is MIN_EPS_GROWTH_PCT


# ── trailing_return_pct ──────────────────────────────────────────────────────
def test_trailing_return_pct_hand_series():
    assert S.trailing_return_pct([100.0, 110.0, 121.0], 2) == pytest.approx(21.0)
    assert S.trailing_return_pct([100.0, 50.0], 1) == pytest.approx(-50.0)


def test_trailing_return_pct_refuses_a_short_frame_and_a_dead_base():
    # NEGATIVE: k >= len has no base bar.
    assert S.trailing_return_pct([1.0, 2.0], 5) is None
    assert S.trailing_return_pct([1.0, 2.0], 2) is None       # len == k
    assert S.trailing_return_pct([1.0, 2.0, 3.0], 2) is not None
    # NEGATIVE: a non-positive base is not a return.
    assert S.trailing_return_pct([0.0, 5.0, 7.0], 2) is None
    assert S.trailing_return_pct([-3.0, 5.0, 7.0], 2) is None
    assert S.trailing_return_pct([1.0, 2.0, 3.0], 0) is None


# ── calendar_window_return_pct — the benchmark is NEVER bar-count aligned ────
def _bench_series(n=30):
    dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2026-08-03", periods=n)]
    close = np.array([100.0 * (1.01 ** i) for i in range(n)])
    return dates, close


def test_calendar_window_return_benchmarks_a_holed_member_over_the_same_dates():
    bench_dates, bench_close = _bench_series(30)
    # The member frame is missing five interior sessions — a real data hole.
    drop = {bench_dates[i] for i in (22, 23, 24, 25, 26)}
    member_dates = [d for d in bench_dates if d not in drop]

    k = 10
    start = member_dates[len(member_dates) - 1 - k]
    got = S.calendar_window_return_pct(bench_dates, bench_close,
                                       start, member_dates[-1])
    i0 = bench_dates.index(start)
    expect = (bench_close[-1] / bench_close[i0] - 1) * 100.0
    assert got == pytest.approx(expect)

    # NEGATIVE: aligning the benchmark by BAR COUNT instead would answer a
    # different question and give a different number.
    by_bar_count = S.trailing_return_pct(bench_close, k)
    assert by_bar_count is not None
    assert abs(by_bar_count - got) > 1.0


def test_calendar_window_return_is_none_when_either_side_has_no_bar():
    dates, close = _bench_series(10)
    assert S.calendar_window_return_pct(dates, close, "2020-01-01", dates[-1]) is None
    assert S.calendar_window_return_pct([], close, dates[0], dates[-1]) is None
    # end before the frame starts -> no bar on or before it
    assert S.calendar_window_return_pct(dates, close, dates[0], "2019-01-01") is None


# ── first_close_after — never the bar ON the date ────────────────────────────
def test_first_close_after_takes_the_next_bar_never_the_filing_bar():
    dates = ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04"]
    close = np.array([10.0, 20.0, 30.0, 40.0])
    got = S.first_close_after(dates, close, "2026-09-02")
    assert got == ("2026-09-03", 30.0)
    # NEGATIVE: the 09-02 bar itself is never the anchor (a 10-Q filed after
    # that day's close is not tradable on it).
    assert got[0] != "2026-09-02" and got[1] != 20.0


def test_first_close_after_is_none_past_the_end_and_on_a_gap_date():
    dates = ["2026-09-01", "2026-09-02"]
    close = np.array([10.0, 20.0])
    assert S.first_close_after(dates, close, "2026-09-02") is None   # NEGATIVE
    assert S.first_close_after(dates, close, "2026-12-31") is None   # NEGATIVE
    # A date with no bar of its own still anchors on the next bar there is.
    assert S.first_close_after(dates, close, "2026-08-30") == ("2026-09-01", 10.0)


# ── relative_pp — rotation's own form, never raw ─────────────────────────────
def test_relative_pp_matches_rotations_form_and_refuses_a_missing_side():
    assert S.relative_pp(12.345, 4.1) == round(12.345 - 4.1, 2) == 8.25
    assert S.relative_pp(-5.0, -1.0) == -4.0
    # NEGATIVE: rotation's rule — a missing benchmark leaves it None, not raw.
    assert S.relative_pp(12.3, None) is None
    assert S.relative_pp(None, 4.1) is None
    assert S.relative_pp(None, None) is None


# ── pct_below_high — PINNED to the trend template ────────────────────────────
def test_pct_below_high_is_pinned_to_trend_template_evaluate():
    df = _frame(300, seed=11)
    res = TT.evaluate("SYNTH", df)
    assert res is not None and res.pct_below_high is not None
    ours = S.pct_below_high(df["close"].to_numpy(dtype=float))
    # the template rounds the served field to 2dp; the arithmetic is identical
    assert round(ours, 2) == pytest.approx(res.pct_below_high, abs=1e-9)
    assert float(df["close"].iloc[-252:].max()) == pytest.approx(res.week52_high)


def test_pct_below_high_is_zero_when_the_last_close_is_the_high():
    close = np.array([10.0, 20.0, 15.0, 30.0])
    assert S.pct_below_high(close) == pytest.approx(0.0)
    assert S.pct_below_high([]) is None


def test_pct_below_high_only_looks_back_252_bars():
    close = np.concatenate([np.array([1000.0]), np.full(300, 50.0)])
    # The 1000 sits outside the trailing 252 and must not count as the high.
    assert S.pct_below_high(close) == pytest.approx(0.0)


def test_pct_below_intraday_high_is_a_separate_secondary_column():
    close = np.array([10.0, 20.0, 18.0])
    high = np.array([11.0, 24.0, 19.0])
    assert S.pct_below_intraday_high(high, close) == pytest.approx(25.0)
    assert S.pct_below_high(close) == pytest.approx(10.0)


# ── NEAR_HIGH_PCT is the template's own literal ──────────────────────────────
def test_near_high_pct_is_the_templates_literal_25_boundary():
    assert S.NEAR_HIGH_PCT == 25.0
    at = TT.evaluate("AT", _flat_frame(300, last=75.0, high=100.0))
    just_past = TT.evaluate("PAST", _flat_frame(300, last=74.99, high=100.0))
    assert at is not None and just_past is not None
    assert at.pct_below_high == pytest.approx(25.0)
    assert at.checks["within_25pct_of_52w_high"] is True
    assert just_past.pct_below_high > 25.0
    assert just_past.checks["within_25pct_of_52w_high"] is False
    # our flag agrees with the template on both sides of the boundary
    assert (S.pct_below_high(np.asarray([75.0])) is not None)
    assert at.pct_below_high <= S.NEAR_HIGH_PCT
    assert just_past.pct_below_high > S.NEAR_HIGH_PCT


def test_there_is_no_beaten_down_constant_anywhere_in_the_module():
    # NEGATIVE (Rule #1): the ask contains no such percentage, so the module
    # must not own one — distance from the high is reported as DECILES.
    assert not hasattr(S, "BEATEN_DOWN_PCT")
    assert not any("beaten" in n.lower() for n in dir(S))
    src = open(S.__file__).read()
    assert "BEATEN_DOWN" not in src
    row = S.member_metrics(["2026-09-01", "2026-09-02"], [10.0, 9.0],
                           [10.5, 9.5], None, None)
    assert not any("beaten" in k.lower() for k in row)
    summ = S.cohort_summary("x", [dict(symbol="A", **row)])
    assert not any("beaten" in k.lower() for k in summ)
    assert "p10" in summ["pct_below_high"] and "p90" in summ["pct_below_high"]


# ── distribution / median_ci / percentile_of ─────────────────────────────────
def test_distribution_deciles_on_a_known_vector():
    d = S.distribution([float(i) for i in range(0, 101)])
    assert d["n"] == 101
    assert d["median"] == 50.0 and d["mean"] == 50.0
    assert d["p10"] == 10.0 and d["p50"] == 50.0 and d["p90"] == 90.0
    assert d["n_pos"] == 100 and d["n_neg"] == 0
    assert d["share_pos"] == pytest.approx(99.0)


def test_distribution_drops_none_and_survives_an_empty_cohort():
    d = S.distribution([1.0, None, 3.0, float("nan")])
    assert d["n"] == 2 and d["median"] == 2.0
    empty = S.distribution([])
    assert empty["n"] == 0 and empty["median"] is None and empty["p50"] is None


def test_median_ci_contains_the_median_and_is_deterministic():
    vals = [float(i) for i in range(1, 51)]
    lo, hi = S.median_ci(vals)
    assert lo is not None and lo <= np.median(vals) <= hi
    assert (lo, hi) == S.median_ci(vals)
    # NEGATIVE: under three members there is nothing to resample.
    assert S.median_ci([1.0, 2.0]) == (None, None)
    assert S.median_ci([]) == (None, None)


def test_percentile_of_hand_case_and_ties():
    assert S.percentile_of([1, 2, 3, 4], 3) == 62.5          # mid-rank
    assert S.percentile_of([1, 2, 3, 4], 0) == 0.0
    assert S.percentile_of([1, 2, 3, 4], 9) == 100.0
    assert S.percentile_of([5, 5, 5, 5], 5) == 50.0          # all ties
    # NEGATIVE
    assert S.percentile_of([], 3) is None
    assert S.percentile_of([1, 2], None) is None


def test_universe_percentile_column_on_a_three_cohort_fixture():
    uni = [{"symbol": f"U{i}", "ret_3m_pct": float(i)} for i in range(101)]
    board = [{"symbol": "A", "ret_3m_pct": 90.0},
             {"symbol": "B", "ret_3m_pct": 10.0},
             {"symbol": "C", "ret_3m_pct": None}]
    S.universe_percentiles(board, uni)
    S.universe_percentiles(uni, uni)
    assert board[0]["universe_pctile_3m"] == pytest.approx(90.0, abs=0.6)
    assert board[1]["universe_pctile_3m"] == pytest.approx(10.0, abs=0.6)
    assert board[2]["universe_pctile_3m"] is None            # NEGATIVE
    # the universe's own median member sits at the middle of itself
    med = S.distribution([r["universe_pctile_3m"] for r in uni])["median"]
    assert med == pytest.approx(50.0, abs=0.6)


# ── Spearman, its CI and the permutation p ───────────────────────────────────
def test_spearman_rho_hand_case_and_monotone():
    assert S.spearman_rho([1, 2, 3, 4, 5], [2, 1, 4, 3, 5]) == pytest.approx(0.8)
    assert S.spearman_rho([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert S.spearman_rho([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)
    # rank-based, so a monotone NON-linear map is still exactly 1.0
    assert S.spearman_rho([1, 2, 3, 4], [1, 4, 9, 1000]) == pytest.approx(1.0)


def test_spearman_rho_refuses_a_constant_side_and_a_tiny_sample():
    # NEGATIVE: a constant side has no rank order.
    assert S.spearman_rho([1, 1, 1, 1], [1, 2, 3, 4]) is None
    assert S.spearman_rho([1, 2, 3, 4], [7, 7, 7, 7]) is None
    # NEGATIVE: fewer than three usable pairs.
    assert S.spearman_rho([1, 2], [3, 4]) is None
    assert S.spearman_rho([1, 2, 3], [None, None, 4]) is None
    assert S.spearman_rho([], []) is None


def test_spearman_ci_brackets_a_strong_relationship_and_is_deterministic():
    x = list(range(30))
    y = [v + (1 if v % 3 else -1) for v in x]
    lo, hi = S.spearman_ci(x, y, B=300, seed=11)
    assert lo is not None and lo > 0.5 and hi <= 1.0
    assert (lo, hi) == S.spearman_ci(x, y, B=300, seed=11)
    assert S.spearman_ci([1, 1, 1], [1, 2, 3], B=50) == (None, None)   # NEGATIVE


def test_perm_p_is_small_on_a_monotone_pair_and_large_on_noise():
    x = list(range(25))
    assert S.perm_p(x, x, draws=200, seed=13) < 0.02
    rng = np.random.default_rng(4)
    a = rng.normal(size=40)
    b = rng.normal(size=40)
    assert abs(S.spearman_rho(a, b)) < 0.2
    assert S.perm_p(a, b, draws=300, seed=13) > 0.05
    # NEGATIVE: no rho, no p.
    assert S.perm_p([1, 1, 1, 1], [1, 2, 3, 4], draws=50) is None


# ── refuse_lookahead ─────────────────────────────────────────────────────────
def test_refuse_lookahead_guards_strictly_greater_only():
    with pytest.raises(S.LookaheadError):
        S.refuse_lookahead("2026-09-21", "2026-09-14")
    with pytest.raises(S.LookaheadError):
        S.refuse_lookahead("2026-09-15T00:00:00Z", "2026-09-14T23:59:59Z")
    # Equality PASSES on purpose — same-day availability is handled by
    # strict=True in the replay's screen_asof, not here.
    assert S.refuse_lookahead("2026-09-14", "2026-09-14") is None
    assert S.refuse_lookahead("2026-09-01", "2026-09-14") is None
    assert S.refuse_lookahead("", "2026-09-14") is None
    doc = S.refuse_lookahead.__doc__ or ""
    assert "strict=True" in doc and "same-day" in doc.lower()


# ── period_age_days — days printed, never a staleness cut ────────────────────
def test_period_age_days_hand_case_and_missing_sides():
    assert S.period_age_days("2026-08-01", "2026-09-21") == 51
    assert S.period_age_days("2026-03-31", "2026-09-21") == 174
    assert S.period_age_days("2026-09-21", "2026-09-21") == 0
    # NEGATIVE
    assert S.period_age_days(None, "2026-09-21") is None
    assert S.period_age_days("2026-08-01", None) is None
    assert S.period_age_days("not-a-date", "2026-09-21") is None
    # NEGATIVE: no staleness threshold is owned by this module.
    assert not hasattr(S, "PERIOD_STALE_DAYS")
    assert "period_stale" not in open(S.__file__).read().split('"""')[1]


# ── NoWriteDB ────────────────────────────────────────────────────────────────
def test_nowrite_db_refuses_every_collection_method():
    db = S.NoWriteDB()
    for call in ("update_one", "insert_one", "replace_one", "delete_many",
                 "find", "find_one", "bulk_write"):
        with pytest.raises(RuntimeError):
            getattr(db["bonde_seen"], call)
    with pytest.raises(RuntimeError):
        db.bonde_seen.update_one({"_id": "X"}, {"$set": {"last_seen": "now"}})


def test_first_seen_record_returns_zero_against_nowrite_db():
    # The proof that handing NoWriteDB to bonde.board() is a CLEAN READ:
    # first_seen.record swallows the refusal and writes nothing.
    from sepa import first_seen as FS
    assert FS.record("bonde_seen", ["PTGX", "CRDO"], db=S.NoWriteDB()) == 0
    assert FS.newly_found("bonde_seen", db=S.NoWriteDB()) == set()


# ── bonde_members ────────────────────────────────────────────────────────────
def _patch_bonde(monkeypatch, raise_in_board=False):
    from sepa import bonde, scanner
    calls = {"load_latest": 0, "caps_seen": None, "db": None}

    all_results = [{"symbol": f"S{i}", "last_close": 10.0 + i} for i in range(7)]

    def fake_load_latest():
        calls["load_latest"] += 1
        return {"all_results": all_results, "generated_at": "2026-09-21T20:30:00Z"}

    def fake_board(db=None, new_days=7):
        calls["caps_seen"] = dict(bonde.SECTION_CAP)
        calls["db"] = db
        if raise_in_board:
            raise RuntimeError("boom")
        return {
            "sections": {"explosive": [{"symbol": "S0", "tier": "explosive",
                                        "growth_yoy_pct": 181.7,
                                        "prior_yoy_pct": 201.5,
                                        "last_close": 187.27,
                                        "base_state": "ok",
                                        "period": "FY2026 Q4",
                                        "period_ok": True}],
                         "strong": [], "steady": [], "pivot": [], "rejected": []},
            "counts": {"explosive": 61, "strong": 274, "steady": 666,
                       "pivot": 0, "rejected": 70},
            "n_pass": 1003, "n_period_mismatch": 0,
            "scan_ts": "2026-09-21T20:30:00Z",
        }

    monkeypatch.setattr(scanner, "load_latest", fake_load_latest)
    monkeypatch.setattr(bonde, "board", fake_board)
    return bonde, calls, all_results


def test_bonde_members_uncaps_in_process_and_restores_the_caps(monkeypatch):
    bonde, calls, all_results = _patch_bonde(monkeypatch)
    before = dict(bonde.SECTION_CAP)
    out = S.bonde_members(uncapped=True)
    assert calls["caps_seen"]["steady"] == 10 ** 9
    assert dict(bonde.SECTION_CAP) == before           # restored
    assert out["caps"] == before
    assert isinstance(calls["db"], S.NoWriteDB)        # never db=None
    # ONE scan file read, for the universe.
    assert calls["load_latest"] == 1
    assert out["universe"]["n"] == len(all_results)
    assert out["universe"]["symbols"][0] == "S0"
    assert out["universe"]["generated_at"] == "2026-09-21T20:30:00Z"
    row = out["sections"]["explosive"][0]
    assert row["section"] == "explosive" and row["tier"] == "explosive"
    assert set(S.BONDE_ROW_KEYS) <= set(row)


def test_bonde_members_restores_the_caps_even_when_the_board_raises(monkeypatch):
    # NEGATIVE: the restore lives in `finally`, so a failure cannot leave the
    # served board uncapped for every later reader in the process.
    bonde, _calls, _all = _patch_bonde(monkeypatch, raise_in_board=True)
    before = dict(bonde.SECTION_CAP)
    with pytest.raises(RuntimeError):
        S.bonde_members(uncapped=True)
    assert dict(bonde.SECTION_CAP) == before


def test_bonde_members_capped_leaves_the_caps_untouched(monkeypatch):
    bonde, calls, _all = _patch_bonde(monkeypatch)
    before = dict(bonde.SECTION_CAP)
    S.bonde_members(uncapped=False)
    assert calls["caps_seen"] == before


# ── filed_dates / filed_metrics ──────────────────────────────────────────────
FIN_FIXTURE = {
    "AAA": {"q": [
        {"fy": 2026, "fp": "Q4", "end": "2026-08-01", "filed": "2026-09-02",
         "rev": 479.0, "eps": 0.67},
        {"fy": 2026, "fp": "Q3", "end": "2026-01-31", "filed": "2026-03-03",
         "rev": 407.0, "eps": 0.82},
    ]},
    "BBB": {"q": [
        {"fy": 2026, "fp": "Q2", "end": "2026-06-30", "filed": None,
         "rev": 10.0, "eps": 0.1},
        {"fy": 2026, "fp": "Q1", "end": "2026-03-31", "filed": "2026-05-04",
         "rev": 9.0, "eps": 0.1},
    ]},
    "CCC": {"q": [{"fy": 2026, "fp": "FY", "end": "2026-06-30",
                   "filed": "2026-08-01", "rev": 1.0, "eps": 0.0}]},
    "DDD": {"q": []},
}


def test_filed_dates_takes_the_newest_quarter_and_derives_an_unfiled_one():
    got = S.filed_dates_from(FIN_FIXTURE)
    assert got["AAA"] == {"filed": "2026-09-02", "end": "2026-08-01",
                          "derived": False, "fy": 2026, "fp": "Q4"}
    # end + 90d, exactly core.prep_fin(derived="plus90")
    assert got["BBB"]["derived"] is True
    assert got["BBB"]["filed"] == "2026-09-28"
    # NEGATIVE: a non-quarterly period and an empty panel contribute nothing.
    assert "CCC" not in got and "DDD" not in got


def test_filed_dates_from_a_missing_file_is_empty_not_an_exception(tmp_path):
    assert S.filed_dates(str(tmp_path / "nope.json.gz")) == {}
    p = tmp_path / "fin.json.gz"
    with gzip.open(p, "wt") as fh:
        json.dump(FIN_FIXTURE, fh)
    assert S.filed_dates(str(p))["AAA"]["filed"] == "2026-09-02"


def test_since_10q_filed_anchors_strictly_after_the_filing_bar():
    dates = ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04"]
    close = np.array([100.0, 90.0, 120.0, 150.0])
    info = S.filed_dates_from(FIN_FIXTURE)["AAA"]      # filed 2026-09-02
    got = S.filed_metrics(dates, close, info)
    assert got["anchor_date"] == "2026-09-03"
    assert got["anchor_close"] == pytest.approx(120.0)
    assert got["since_10q_filed_pct"] == pytest.approx(25.0)
    # NEGATIVE: anchoring ON the filed bar would have printed +66.67%.
    assert got["anchor_date"] != info["filed"]
    assert got["since_10q_filed_pct"] != pytest.approx(66.67, abs=0.01)
    assert got["filed_derived"] is False
    assert got["period_end"] == "2026-08-01"
    assert got["period_age_days"] == S.period_age_days("2026-08-01", "2026-09-04")


def test_filed_metrics_is_all_none_without_a_panel_row_or_a_later_bar():
    dates = ["2026-09-01", "2026-09-02"]
    close = np.array([100.0, 110.0])
    blank = S.filed_metrics(dates, close, None)              # NEGATIVE: no row
    assert blank["since_10q_filed_pct"] is None and blank["filed"] is None
    late = S.filed_metrics(dates, close, {"filed": "2026-12-31",
                                          "end": "2026-09-30", "derived": True})
    assert late["anchor_date"] is None and late["since_10q_filed_pct"] is None
    assert late["filed_derived"] is True                     # still reported


def test_pre_filed_126_needs_126_bars_before_the_anchor():
    n = 200
    dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2025-01-02", periods=n)]
    close = np.array([100.0 * (1.005 ** i) for i in range(n)])
    info = {"filed": dates[150], "end": dates[140], "derived": False}
    got = S.filed_metrics(dates, close, info)
    assert got["anchor_date"] == dates[151]
    assert got["pre_filed_126_pct"] == pytest.approx(
        (close[151] / close[151 - 126] - 1) * 100.0, abs=0.01)
    # NEGATIVE: an anchor inside the first 126 bars has no look-back leg.
    early = S.filed_metrics(dates, close,
                            {"filed": dates[10], "end": dates[5], "derived": False})
    assert early["anchor_date"] == dates[11]
    assert early["pre_filed_126_pct"] is None


# ── member_metrics wiring ────────────────────────────────────────────────────
def test_member_metrics_benchmarks_every_window_by_date():
    n = 300
    dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2025-01-02", periods=n)]
    close = np.array([100.0 * (1.002 ** i) for i in range(n)])
    high = close * 1.01
    bdates, bclose = dates, np.array([100.0 * (1.001 ** i) for i in range(n)])
    row = S.member_metrics(dates, close, high, bdates, bclose)
    for name, k in S.WINDOWS:
        assert row[f"ret_{name}_pct"] is not None
        assert row[f"bench_{name}_pct"] is not None
        assert row[f"rel_{name}_pp"] == S.relative_pp(row[f"ret_{name}_pct"],
                                                      row[f"bench_{name}_pct"])
        assert row[f"win_{name}_start"] == dates[n - 1 - k]
    assert row["at_52w_high"] is True and row["within_near_high"] is True
    assert row["pct_below_high"] == pytest.approx(0.0)


def test_member_metrics_leaves_the_benchmark_none_when_there_is_no_bench():
    dates = ["2026-09-01", "2026-09-02", "2026-09-03"]
    row = S.member_metrics(dates, [10.0, 11.0, 9.0], [10.5, 11.5, 9.5], None, None)
    # NEGATIVE: no benchmark frame -> relative columns stay None, never raw.
    assert row["bench_1w_pct"] is None and row["rel_1w_pp"] is None
    assert row["ret_1w_pct"] is None            # 3 bars, 5-bar window
    assert row["at_52w_high"] is False


# ── load_close refuses a delisted name before touching prices ────────────────
def test_load_close_refuses_a_delisted_symbol_without_a_price_read(monkeypatch):
    from sepa import prices, symbols as SYM
    dead = sorted(SYM.DELISTED)[0]
    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise AssertionError("load_prices must not be called for a dead listing")

    monkeypatch.setattr(prices, "load_prices", boom)
    assert S.load_close(dead) is None           # NEGATIVE
    assert calls["n"] == 0
    assert S.load_close("") is None


def test_load_close_memoises_one_read_per_symbol(monkeypatch):
    from sepa import prices
    calls = {"n": 0}
    n = 30
    df = pd.DataFrame({"open": np.ones(n), "high": np.ones(n) * 1.1,
                       "low": np.ones(n) * 0.9, "close": np.arange(1.0, n + 1),
                       "volume": np.ones(n)},
                      index=pd.bdate_range("2026-08-03", periods=n))

    def fake(sym, *a, **k):
        calls["n"] += 1
        return df

    monkeypatch.setattr(prices, "load_prices", fake)
    a = S.load_close("ZZZZ")
    b = S.load_close("ZZZZ")
    assert a is b and calls["n"] == 1
    assert a[0][0] == "2026-08-03" and a[1][-1] == pytest.approx(float(n))


# ── cohort summary + Study B ─────────────────────────────────────────────────
def _cohort(vals, screen=None):
    rows = []
    for i, v in enumerate(vals):
        r = {"symbol": f"X{i}", "ret_3m_pct": v, "rel_3m_pp": None if v is None else v - 1.0,
             "universe_pctile_3m": None if v is None else float(i),
             "pct_below_high": 0.0 if i == 0 else 30.0,
             "at_52w_high": i == 0, "within_near_high": i == 0,
             "since_10q_filed_pct": v, "pre_filed_126_pct": v,
             "period_age_days": 50 + i, "n_bars": 300}
        if screen is not None:
            r["sales_growth_pct"] = screen[i]
        rows.append(r)
    return rows


def test_cohort_summary_carries_n_a_ci_and_the_high_deciles():
    rows = _cohort([float(i) for i in range(20)])
    s = S.cohort_summary("demo", rows)
    assert s["n"] == 20
    w = s["windows"]["3m"]
    assert w["raw"]["n"] == 20 and w["raw"]["median"] == pytest.approx(9.5)
    lo, hi = w["raw_median_ci"]
    assert lo is not None and lo <= 9.5 <= hi
    assert s["n_at_52w_high"] == 1
    assert s["near_high_pct"] == S.NEAR_HIGH_PCT
    assert s["n_within_near_high"] == 1
    assert s["pct_below_high"]["p90"] == pytest.approx(30.0)
    assert s["n_since_10q_filed_positive"] == 19      # the 0.0 member is not
    assert s["period_age_days"]["median"] == pytest.approx(59.5)
    assert w["crdo_pctile_in_cohort"] is None          # CRDO is not a member


def test_cohort_summary_reports_crdos_own_percentile_when_it_is_a_member():
    rows = _cohort([float(i) for i in range(10)])
    rows[7]["symbol"] = "CRDO"
    s = S.cohort_summary("demo", rows)
    w = s["windows"]["3m"]
    assert w["crdo_ret_pct"] == pytest.approx(7.0)
    assert w["crdo_pctile_in_cohort"] == pytest.approx(75.0)


def test_study_b_reads_the_screen_number_against_the_trailing_run():
    vals = [float(i) for i in range(20)]
    rows = _cohort(vals, screen=[v * 2 + 1 for v in vals])
    t = S.study_b_table("demo", rows)
    assert t["rule_of_reading"] == S.B_RULE_OF_READING
    leg = t["legs"]["sales"]["3m"]
    assert leg["rho"] == pytest.approx(1.0) and leg["n"] == 20
    assert leg["ci"][0] is not None and leg["ci"][0] > 0
    assert leg["perm_p"] is not None and leg["perm_p"] < 0.05
    assert "since_10q_filed" in t["legs"]["sales"]


def test_study_b_skips_a_leg_the_cohort_has_no_number_for():
    # NEGATIVE: the Bonde cohorts carry no EPS leg — it must be absent, not 0.
    rows = _cohort([float(i) for i in range(10)],
                   screen=[float(i) for i in range(10)])
    t = S.study_b_table("bonde", rows)
    assert "eps" not in t["legs"]
    assert "sales" in t["legs"]


def test_reading_sentence_fills_either_branch_and_never_grades_the_exit():
    vals = [float(i) for i in range(20)]
    rows = _cohort(vals, screen=[v * 2 for v in vals])
    s = S.cohort_summary("growth_21", rows)
    t = S.study_b_table("growth_21", rows)
    text = S.reading_sentence(s, t)
    assert "does track the trailing 3m return" in text
    assert "percentile of the scan universe over 3m" in text
    for banned in ("should have", "right call", "bounce", "mistake"):
        assert banned not in text.lower()

    noisy = _cohort(vals, screen=[7.0 if i % 2 else 1.0 for i in range(20)])
    t2 = S.study_b_table("growth_21", noisy)
    text2 = S.reading_sentence(S.cohort_summary("growth_21", noisy), t2)
    assert "does not track" in text2 and "right tail" in text2


# ── the CSV writer ───────────────────────────────────────────────────────────
def test_members_csv_writes_one_row_per_cohort_symbol(tmp_path):
    cohorts = {"growth_21": _cohort([1.0, 2.0]),
               "universe_all": _cohort([3.0, 4.0, 5.0])}
    p = tmp_path / "members.csv"
    assert S.write_members_csv(str(p), cohorts) == 5
    text = p.read_text().splitlines()
    assert text[0].startswith("cohort,symbol")
    assert len(text) == 6
    assert sum(1 for line in text[1:] if line.startswith("growth_21,")) == 2


def test_wording_never_says_bounce_on_a_printed_line():
    # His standing rule: "reversal", never "bounce", on anything he reads.
    src = open(S.__file__).read().lower()
    assert "bounce" not in src


# ── _iso: the C10 stamp survives the container's TZ ──────────────────────────
@contextlib.contextmanager
def _tz(name: str):
    """Run the block under a local timezone, like the api container's TZ."""
    old = os.environ.get("TZ")
    os.environ["TZ"] = name
    time.tzset()
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old
        time.tzset()


def test_iso_reads_a_naive_datetime_as_utc_under_a_non_utc_local_tz():
    # `growth_board.built_at` comes back NAIVE from pymongo and the api
    # container runs TZ=America/New_York: the C10 stamp must print verbatim.
    built_at = datetime(2026, 9, 21, 3, 38, 8, 83000)
    assert built_at.tzinfo is None
    for zone in ("America/New_York", "UTC", "Asia/Kolkata"):
        with _tz(zone):
            assert S._iso(built_at) == "2026-09-21T03:38:08.083000Z"


def test_iso_never_shifts_a_naive_stamp_by_the_local_offset():
    # NEGATIVE: the pre-fix behaviour (astimezone on a naive value) would have
    # printed 07:38:08Z in New York and 22:08:08Z the previous day in Kolkata.
    naive = datetime(2026, 9, 21, 3, 38, 8, 83000)
    with _tz("America/New_York"):
        assert S._iso(naive) != "2026-09-21T07:38:08.083000Z"
        assert naive.astimezone(timezone.utc).isoformat().startswith(
            "2026-09-21T07:38:08")
    with _tz("Asia/Kolkata"):
        assert S._iso(naive).startswith("2026-09-21T")


def test_iso_still_converts_an_aware_non_utc_datetime():
    aware = datetime(2026, 9, 20, 23, 38, 8,
                     tzinfo=timezone(timedelta(hours=-4)))
    with _tz("America/New_York"):
        assert S._iso(aware) == "2026-09-21T03:38:08Z"


def test_iso_passes_strings_through_and_refuses_nothing_else():
    assert S._iso("2026-09-12T19:51:22Z") == "2026-09-12T19:51:22Z"
    assert S._iso(None) is None


def test_growth_first_cohort_compares_last_seen_against_the_utc_built_at():
    # A name last stamped at the naive `built_at` itself is NOT dropped; the
    # local-time shift would have made every row look dropped in New York.
    built_at = datetime(2026, 9, 21, 3, 38, 8, 83000)
    built_iso = S._iso(built_at)
    with _tz("America/New_York"):
        assert S._iso(built_at) == built_iso
        assert not ("2026-09-21T03:38:08.083000Z" < built_iso)
        assert "2026-09-13T13:00:00Z" < built_iso


# ── the dropped flag on the first cohort ─────────────────────────────────────
def test_flag_dropped_uses_the_cohort_max_not_built_at():
    # `_record_seen` writes ONE stamp to every symbol in the build; `build()`
    # reads the clock AGAIN for `built_at`, microseconds later. The live shape:
    # 21 current members on the build stamp, 8 left behind on 09-13.
    build_stamp = "2026-09-21T03:38:08.081177+00:00"
    built_at = "2026-09-21T03:38:08.083000"          # the SECOND clock read
    old = "2026-09-13T13:00:00.512000+00:00"
    gone = ["DBRG", "PROP", "SNDK", "ECHO", "CDE", "AXTI", "HNI", "KOPN"]
    rows = ([{"symbol": s, "first_seen": old, "last_seen": build_stamp}
             for s in [f"SYM{i}" for i in range(21)]]
            + [{"symbol": s, "first_seen": old, "last_seen": old} for s in gone])

    out = S.flag_dropped(rows)
    assert sum(1 for r in out if r["dropped"]) == 8
    assert {r["symbol"] for r in out if r["dropped"]} == set(gone)

    # NEGATIVE — the bug this replaces: every current member's `last_seen`
    # sorts strictly BELOW `built_at`, so the old test flagged 29 of 29.
    assert all(str(r["last_seen"]) < built_at for r in rows)
    assert sum(1 for r in rows if str(r["last_seen"]) < built_at) == 29


def test_flag_dropped_never_flags_a_single_shared_stamp():
    # NEGATIVE: one build, every name re-stamped -> nothing dropped, even
    # though every stamp is below the `built_at` that follows it.
    stamp = "2026-09-21T03:38:08.081177+00:00"
    out = S.flag_dropped([{"symbol": s, "last_seen": stamp} for s in "ABC"])
    assert [r["dropped"] for r in out] == [False, False, False]


def test_flag_dropped_edge_cases():
    # No stamp anywhere -> no build to compare against -> nothing flagged.
    assert [r["dropped"] for r in S.flag_dropped([{"symbol": "A"},
                                                  {"symbol": "B"}])] == [False, False]
    # A name the latest build did not stamp at all IS dropped.
    out = S.flag_dropped([{"symbol": "A", "last_seen": "2026-09-21T03:38:08Z"},
                          {"symbol": "B", "last_seen": None}])
    assert [r["dropped"] for r in out] == [False, True]
    assert S.flag_dropped([]) == []
    # PURE: the input rows are not mutated.
    src = [{"symbol": "A", "last_seen": "2026-09-21T03:38:08Z"}]
    S.flag_dropped(src)
    assert "dropped" not in src[0]


def test_growth_first_cohort_does_not_compare_against_built_at():
    # The function body must not reach for the board doc's `built_at` at all:
    # that comparison is the defect.
    import inspect
    body = inspect.getsource(S.growth_first_cohort)
    assert "built_at" not in body.split('"""')[2]
    assert "flag_dropped" in body
