"""Behavioral + regression tests for the Pullback-to-MA scanner.

Book: Mark Minervini, *Trade Like a Stock Market Wizard* (2013), pp.72, 79,
237-238. See docs/sepa/pullback_ma_methodology.md.

All synthetic — no Mongo, no provider. We monkeypatch prices.load_prices and
scanner.load_latest so the gate logic is exercised in isolation.
"""
import numpy as np
import pandas as pd
import pytest

from sepa import pullback_ma as pb


# ── synthetic data builders ─────────────────────────────────────────────────
def make_df(n=120, recent_high=107.0, last_vol=600_000.0, base_vol=1_000_000.0):
    """A 120-bar OHLCV frame whose last-25-day high is `recent_high` and whose
    last bar's volume is `last_vol` against a `base_vol` baseline."""
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    close = np.linspace(95.0, 103.0, n)
    # Small baseline wick so the INJECTED `recent_high` is the true max of the
    # window (a 1.0 wick would float baseline highs to ~104 and mask a recent
    # high set just above the last close, e.g. the "still at highs" case).
    high = close + 0.1
    high[-12] = recent_high            # the swing high inside the 25-day window
    low = close - 0.1
    vol = np.full(n, base_vol, dtype=float)
    vol[-1] = last_vol
    return pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close, "volume": vol},
        index=idx,
    )


def rec(symbol, last_close, ma50=100.0, ma150=95.0, ma200=90.0,
        rs_rank=85, ret3m=12.0, is_candidate=True):
    return {
        "symbol": symbol,
        "name": f"{symbol} Co",
        "last_close": last_close,
        "trend": {"ma50": ma50, "ma150": ma150, "ma200": ma200},
        "rs_rank": rs_rank,
        "dual_momentum": {"return_3m": ret3m},
        "stage": {"stage": 2},
        "is_candidate": is_candidate,
    }


# ── pure-helper unit tests ───────────────────────────────────────────────────
def test_band_thresholds_match_spec():
    # tight < 5, mid 5-8, deep > 8 (configured from the user spec)
    assert pb._band(0.0) == "tight"
    assert pb._band(4.99) == "tight"
    assert pb._band(5.0) == "mid"
    assert pb._band(8.0) == "mid"
    assert pb._band(8.01) == "deep"
    assert pb._band(20.0) == "deep"
    assert pb._band(None) is None


def test_recent_high_uses_last_lookback_window():
    df = make_df(recent_high=112.0)
    assert pb._recent_high(df, pb.RECENT_HIGH_LOOKBACK) == pytest.approx(112.0)


def test_vol_ratio_below_one_when_volume_dries_up():
    df = make_df(last_vol=600_000.0, base_vol=1_000_000.0)
    vr = pb._vol_ratio(df, pb.VOL_AVG_LOOKBACK)
    assert vr is not None and vr < 1.0           # contracting volume (book p.72)


# ── _evaluate_row gate behavior ──────────────────────────────────────────────
def _patch_prices(monkeypatch, mapping):
    monkeypatch.setattr(pb.prices, "load_prices", lambda s: mapping.get(s))


def test_clean_tight_pullback_is_a_candidate(monkeypatch):
    _patch_prices(monkeypatch, {"AAA": make_df(recent_high=107.0)})
    # last_close 103 vs ma50 100 -> +3% above the line, inside the zone.
    # recent high 107 -> pullback 3.7% -> tight. volume drying -> healthy.
    row = pb._evaluate_row(rec("AAA", last_close=103.0))
    assert row is not None
    assert row["pullback_band"] == "tight"
    assert 3.0 < row["pullback_pct"] < 4.5
    assert row["pct_from_ma50"] == pytest.approx(3.0, abs=0.1)
    assert row["vol_healthy"] is True
    assert row["rs_3m"] == 12.0
    assert row["is_sepa_candidate"] is True


def test_deep_pullback_is_flagged_deep(monkeypatch):
    _patch_prices(monkeypatch, {"DEEP": make_df(recent_high=115.0)})
    row = pb._evaluate_row(rec("DEEP", last_close=103.0))
    assert row is not None
    assert row["pullback_band"] == "deep"      # ~10.4% off the recent high
    assert row["pullback_pct"] > 8.0


def test_price_below_ma50_is_excluded(monkeypatch):
    # Trend Template #5 (p.79): price must be ABOVE the 50-day. 99 < 100 -> out.
    _patch_prices(monkeypatch, {"BELOW": make_df()})
    assert pb._evaluate_row(rec("BELOW", last_close=99.0)) is None


def test_extended_above_ma50_is_excluded(monkeypatch):
    # 112 vs ma50 100 -> +12% > 8% zone ceiling: too extended to be a pullback.
    _patch_prices(monkeypatch, {"EXT": make_df()})
    assert pb._evaluate_row(rec("EXT", last_close=112.0)) is None


def test_broken_ma_stack_is_excluded(monkeypatch):
    # 50-day below the 150-day breaks the rising stack (p.79 #4) -> not Stage 2.
    _patch_prices(monkeypatch, {"STK": make_df()})
    assert pb._evaluate_row(
        rec("STK", last_close=103.0, ma50=100.0, ma150=101.0, ma200=90.0)
    ) is None


def test_at_highs_not_yet_pulled_back_is_excluded(monkeypatch):
    # recent high ~= last_close -> pullback < MIN_PULLBACK_PCT -> still pinned.
    _patch_prices(monkeypatch, {"HI": make_df(recent_high=103.2)})
    assert pb._evaluate_row(rec("HI", last_close=103.0)) is None


def test_heavy_volume_pullback_still_listed_but_not_healthy(monkeypatch):
    # vol ratio is a quality FLAG, not a hard gate: a heavy-volume dip still
    # appears (so the user can see it) but is marked unhealthy.
    _patch_prices(monkeypatch, {"HVY": make_df(last_vol=1_600_000.0)})
    row = pb._evaluate_row(rec("HVY", last_close=103.0))
    assert row is not None
    assert row["vol_ratio"] > 1.0
    assert row["vol_healthy"] is False


# ── compute() integration ────────────────────────────────────────────────────
def test_compute_filters_ranks_and_shapes(monkeypatch):
    dfs = {
        "AAA": make_df(recent_high=107.0),     # tight, healthy  -> in
        "DEEP": make_df(recent_high=120.0),    # deep            -> in
        "BELOW": make_df(),                     # below ma50      -> out
        "EXT": make_df(),                       # extended        -> out
    }
    _patch_prices(monkeypatch, dfs)
    monkeypatch.setattr(
        pb.sepa_scanner, "load_latest",
        lambda: {
            "generated_at": 111,
            "all_results": [
                rec("AAA", 103.0),
                rec("DEEP", 103.0),
                rec("BELOW", 99.0),
                rec("EXT", 112.0),
            ],
        },
    )
    out = pb.compute(top_n=10)
    syms = [r["symbol"] for r in out["rows"]]
    assert "AAA" in syms and "DEEP" in syms
    assert "BELOW" not in syms and "EXT" not in syms
    assert out["candidate_count"] == 2
    assert out["universe_size"] == 4
    # tighter / closer-to-line AAA should outrank the deep name.
    assert syms[0] == "AAA"
    assert out["rows"][0]["rank"] == 1
    assert out["scan_generated_at"] == 111
    assert out["config"]["vol_avg_lookback"] == pb.VOL_AVG_LOOKBACK


def test_compute_handles_no_scan(monkeypatch):
    monkeypatch.setattr(pb.sepa_scanner, "load_latest", lambda: {})
    out = pb.compute()
    assert out["error"] == "no_scan"
    assert out["rows"] == [] and out["candidate_count"] == 0
