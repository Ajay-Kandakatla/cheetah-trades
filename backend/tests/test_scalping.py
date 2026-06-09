"""Tests for the scalping module — cost model, detectors, spread gate. All
synthetic 1-min frames, no network. Sources cited in docs/scalping_methodology.md.
"""
import numpy as np
import pandas as pd

from scalping import costs, detectors, nbbo


# ── cost model ───────────────────────────────────────────────────────────────
def test_round_trip_cost_known_vs_unknown_spread():
    known = costs.round_trip_cost_pct(100.0, spread_pct=0.10)
    assert known["spread_known"] is True
    assert known["total_pct"] > 0.10                    # spread + slippage + commission + fees
    unknown = costs.round_trip_cost_pct(100.0, spread_pct=None)
    assert unknown["spread_known"] is False             # never silently zero


def test_breakeven_win_rate_formula():
    # p* = (risk + cost) / (reward + risk)
    assert costs.breakeven_win_rate(1.0, 1.0, 0.2) == 60.0
    assert costs.breakeven_win_rate(2.0, 1.0, 0.0) == 33.3
    assert costs.breakeven_win_rate(1.0, 1.0, None) is None


def test_annotate_net_of_cost_flags_unknown_spread():
    s = {"entry_price": 100.0, "reward_pct": 1.0, "risk_pct": 1.0, "side": "long"}
    costs.annotate_net_of_cost(s, None)
    assert s["net_of_cost"]["spread_known"] is False
    assert "Spread unknown" in s["net_of_cost"]["verdict"]


# ── frame helpers ────────────────────────────────────────────────────────────
def _frame(closes, start="2026-06-09 14:01"):
    """1-min RTH frame, UTC tz-naive index (the detectors convert to ET)."""
    idx = pd.date_range(start, periods=len(closes), freq="1min")
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({
        "open": np.r_[c[0], c[:-1]], "high": c + 0.05, "low": c - 0.05,
        "close": c, "volume": np.full(len(c), 50000.0), "session": "rth",
    }, index=idx)


# ── Stocks-in-Play ORB ───────────────────────────────────────────────────────
def test_orb_fires_for_stock_in_play_with_clear_direction():
    rng = np.random.RandomState(0)
    closes = np.r_[np.linspace(100.0, 100.6, 5), 100.6 + np.cumsum(rng.normal(0.03, 0.04, 55))]
    sig = detectors.stocks_in_play_orb(_frame(closes), rel_vol=2.2, atr14=1.0, regime_bias="long_bias")
    assert sig is not None
    assert sig["side"] == "long" and sig["status"] in ("armed", "triggered")
    assert sig["risk_pct"] > 0 and sig["regime_aligned"] is True


def test_orb_skipped_when_not_a_stock_in_play():
    closes = np.r_[np.linspace(100.0, 100.6, 5), np.full(55, 100.6)]
    assert detectors.stocks_in_play_orb(_frame(closes), rel_vol=0.5, atr14=1.0) is None


def test_orb_skipped_on_doji_open():
    closes = np.full(60, 100.0) + np.random.RandomState(1).normal(0, 0.001, 60)
    assert detectors.stocks_in_play_orb(_frame(closes), rel_vol=2.0, atr14=1.0) is None


# ── shock fade ───────────────────────────────────────────────────────────────
def _shock_frame(start="2026-06-09 14:01", drop_pct=6.0):
    rng = np.random.RandomState(3)
    base = 100.0 + rng.normal(0, 0.03, 40)              # quiet baseline (small sigma)
    drop = np.linspace(100.0, 100.0 * (1 - drop_pct / 100.0), 20)
    return _frame(np.r_[base, drop], start=start)


def test_shock_fade_fires_on_4pct_and_8sigma_intraday_drop():
    sig = detectors.shock_fade(_shock_frame(), atr14=1.5)
    assert sig is not None
    assert sig["side"] == "long"                        # fade a drop = go long
    assert sig["move_pct"] <= -4.0 and sig["sigma_multiple"] >= 8.0
    assert sig["risk_pct"] > 0.5                         # realistic risk, not ~0


def test_shock_fade_skipped_when_move_below_threshold():
    assert detectors.shock_fade(_shock_frame(drop_pct=2.0), atr14=1.5) is None


def test_shock_fade_excluded_in_last_60_min():
    # last bar ~15:45 ET (19:45 UTC) → inside the excluded closing window
    assert detectors.shock_fade(_shock_frame(start="2026-06-09 18:46"), atr14=1.5) is None


# ── spread gate ──────────────────────────────────────────────────────────────
def test_spread_gate_states():
    assert nbbo.spread_gate(None, 1.0)["state"] == "unknown"
    assert nbbo.spread_gate(None, 1.0)["ok"] is False
    assert nbbo.spread_gate(0.05, 1.0)["state"] == "tight"
    assert nbbo.spread_gate(0.30, 1.0)["state"] == "too_wide"   # 30% of target move
    assert nbbo.spread_gate(0.30, 1.0)["ok"] is False
    assert nbbo.spread_gate(0.12, 1.0)["state"] == "wide"       # caution but tradeable
