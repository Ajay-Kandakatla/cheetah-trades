"""Order-flow ("Tape") pure-logic tests — synthetic tapes in, deterministic
reads out. Covers the tick rule, cumulative delta, big prints, bursts, the
volume profile, the composite verdict table (incl. the daily-trend gate that
can NEVER emit BUY when it fails), and the ledger grader. Negative/edge cases
included per Rule #6 (empty tapes, one-sided tapes, unknown-side prefixes)."""
import os
import sys
from datetime import datetime, timezone, timedelta

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orderflow.tape import (tick_rule_sides, delta_summary, find_big_prints,
                            find_bursts, volume_profile, analyze_tape,
                            BURST_MIN_TRADES)
from orderflow.signals import (composite_verdict, delta_check, big_buyers_check,
                               intraday_ema_read)
from orderflow.history import grade


# ── helpers ──────────────────────────────────────────────────────────────────
def _tape(rows, start=None, step_ms=200):
    """rows = [(price, size), ...] → trades DataFrame with ts index."""
    start = start or datetime(2026, 7, 2, 14, 0, tzinfo=timezone.utc)  # 10:00 ET
    idx = [start + timedelta(milliseconds=i * step_ms) for i in range(len(rows))]
    df = pd.DataFrame({"price": [r[0] for r in rows], "size": [r[1] for r in rows]},
                      index=pd.DatetimeIndex(idx, name="ts_utc"))
    return df


def _sided(df):
    out = df.copy()
    out["side"] = tick_rule_sides(out["price"].tolist())
    return out


PASS = {"pass": True, "detail": ""}
FAIL = {"pass": False, "detail": ""}
ZONE_OK = {"pass": True, "caution": False, "detail": ""}
ZONE_NEUTRAL = {"pass": False, "caution": False, "detail": ""}
ZONE_CAUTION = {"pass": False, "caution": True, "detail": ""}


# ── tick rule ────────────────────────────────────────────────────────────────
def test_tick_rule_upticks_downticks_and_carry():
    #        no-ref  up  carry  down  carry  up
    prices = [10.0, 10.01, 10.01, 10.0, 10.0, 10.02]
    assert tick_rule_sides(prices) == [0, 1, 1, -1, -1, 1]


def test_tick_rule_empty_and_flat_prefix():
    assert tick_rule_sides([]) == []
    # a tape that never moves has no classifiable side at all
    assert tick_rule_sides([5.0, 5.0, 5.0]) == [0, 0, 0]


# ── delta ────────────────────────────────────────────────────────────────────
def test_delta_buyers_in_control():
    rows = [(10.0, 100)] + [(10.0 + 0.01 * i, 200) for i in range(1, 6)] + [(10.04, 50)]
    d = delta_summary(_sided(_tape(rows)))
    assert d["buy_volume"] == 1000            # five upticks x 200
    assert d["sell_volume"] == 50             # one downtick x 50
    assert d["delta"] == 950
    assert d["late_delta"] == d["delta"]      # whole tape inside the late window
    assert d["series"], "per-minute cumulative series must not be empty"
    assert d["series"][-1][1] == 950


def test_per_minute_delta_is_the_pre_cumsum_series():
    """Big delta PER CANDLE (Ajay 2026-08-24: "which side is actually winning
    ... inside a specific candle"). The per-minute series must be the exact
    first-difference of the cumulative one — computed once, not twice."""
    rows = [(10.0, 100)] + [(10.0 + 0.01 * i, 200) for i in range(1, 6)] + [(10.04, 50)]
    # Spread the tape across three minutes so per-minute != cumulative.
    d = delta_summary(_sided(_tape(rows, step_ms=45_000)))
    assert d["per_minute"], "per-minute delta series must not be empty"
    # Summing the minutes reproduces the session delta exactly.
    assert sum(v for _, v in d["per_minute"]) == d["delta"]
    # And cum(per_minute) == series, point for point.
    run = 0
    for (ts_pm, v), (ts_cum, c) in zip(d["per_minute"], d["series"]):
        run += v
        assert ts_pm == ts_cum
        assert run == c


def test_per_minute_delta_single_minute_tape_is_one_bar():
    """A tape entirely inside one minute yields one per-minute bar equal to the
    session delta — not an empty list and not a fabricated zero-padded one."""
    rows = [(10.0, 100), (10.01, 200), (10.0, 50)]
    d = delta_summary(_sided(_tape(rows)))
    assert len(d["per_minute"]) == 1
    assert d["per_minute"][0][1] == d["delta"]


def test_delta_unknown_side_volume_excluded_but_counted():
    d = delta_summary(_sided(_tape([(10.0, 500), (10.0, 500)])))
    assert d["delta"] == 0
    assert d["classified_pct"] == 0.0
    assert d["n_trades"] == 2


# ── big prints ───────────────────────────────────────────────────────────────
def test_big_prints_flags_the_block_and_its_side():
    rows = [(50.0, 100)] * 50 + [(50.05, 30000)]      # $1.5M uptick block
    bp = find_big_prints(_sided(_tape(rows)))
    assert len(bp["prints"]) == 1
    assert bp["prints"][0]["side"] == "buy"
    assert bp["prints"][0]["dollars"] == pytest.approx(30000 * 50.05, rel=1e-3)
    assert bp["buy_dollars"] > 0 and bp["sell_dollars"] == 0


def test_big_prints_quiet_tape_has_none():
    bp = find_big_prints(_sided(_tape([(20.0, 100)] * 40)))   # $2k prints only
    assert bp["prints"] == []


# ── bursts ───────────────────────────────────────────────────────────────────
def test_burst_detected_when_one_sided_and_heavy():
    # 20 aggressive upticks x 500 sh @ ~$100 in <10s = ~$1M, 100% buy-side
    rows = [(100.0 + 0.01 * i, 500) for i in range(BURST_MIN_TRADES + 5)]
    bursts = find_bursts(_sided(_tape(rows, step_ms=300)))
    assert bursts and bursts[0]["side"] == "buy"
    assert bursts[0]["dollars"] >= 250_000


def test_no_burst_on_balanced_tape():
    # alternating up/down — heavy but two-sided → not a flash
    rows = []
    for i in range(BURST_MIN_TRADES * 2):
        rows.append((100.0 + (0.01 if i % 2 == 0 else -0.01), 500))
    assert find_bursts(_sided(_tape(rows, step_ms=200))) == []


# ── volume profile ───────────────────────────────────────────────────────────
def test_volume_profile_poc_at_the_heavy_price():
    idx = pd.date_range("2026-07-02 14:00", periods=30, freq="1min", tz="UTC")
    close = [100.0] * 10 + [105.0] * 10 + [110.0] * 10
    vol = [100] * 10 + [10000] * 10 + [100] * 10      # all the business at 105
    bars = pd.DataFrame({"close": close, "volume": vol}, index=idx)
    p = volume_profile(bars)
    assert p is not None
    assert abs(p["poc"] - 105.0) < 1.0
    assert p["value_area_low"] <= p["poc"] <= p["value_area_high"]


def test_volume_profile_none_on_empty_or_flat():
    assert volume_profile(None) is None
    idx = pd.date_range("2026-07-02 14:00", periods=5, freq="1min", tz="UTC")
    flat = pd.DataFrame({"close": [50.0] * 5, "volume": [100] * 5}, index=idx)
    assert volume_profile(flat) is None                # zero price range


# ── intraday EMA read ────────────────────────────────────────────────────────
def _bars_trend(up=True, n=200):
    idx = pd.date_range("2026-07-02 13:30", periods=n, freq="1min", tz="UTC")
    px = [100 + (0.05 if up else -0.05) * i for i in range(n)]
    return pd.DataFrame({"close": px, "volume": [1000] * n,
                         "session": ["rth"] * n}, index=idx)


def test_intraday_ema_pass_in_uptrend_fail_in_downtrend():
    assert intraday_ema_read(_bars_trend(up=True))["pass"] is True
    assert intraday_ema_read(_bars_trend(up=False))["pass"] is False


def test_intraday_ema_insufficient_bars_fails_closed():
    assert intraday_ema_read(_bars_trend(n=20))["pass"] is False
    assert intraday_ema_read(None)["pass"] is False


# ── check adapters ───────────────────────────────────────────────────────────
def test_delta_check_needs_positive_session_and_nonnegative_late():
    assert delta_check({"delta": 5000, "late_delta": 100, "late_window_min": 30})["pass"]
    assert not delta_check({"delta": 5000, "late_delta": -200, "late_window_min": 30})["pass"]
    assert not delta_check({"delta": -1, "late_delta": 500, "late_window_min": 30})["pass"]


def test_big_buyers_check_ratio_rule():
    assert big_buyers_check({"buy_dollars": 2_000_000, "sell_dollars": 1_000_000})["pass"]
    assert not big_buyers_check({"buy_dollars": 1_000_000, "sell_dollars": 1_000_000})["pass"]
    assert big_buyers_check({"buy_dollars": 500_000, "sell_dollars": 0})["pass"]
    assert not big_buyers_check({"buy_dollars": 0, "sell_dollars": 0})["pass"]


# ── the verdict table ────────────────────────────────────────────────────────
def test_buy_when_everything_aligns():
    v = composite_verdict(PASS, PASS, PASS, PASS, ZONE_OK)
    assert v["verdict"] == "BUY"
    assert v["checks_passed"] == 5


def test_buy_possible_with_zone_neutral_if_big_buyers_pass():
    v = composite_verdict(PASS, PASS, PASS, PASS, ZONE_NEUTRAL)
    assert v["verdict"] == "BUY"


def test_daily_trend_gate_can_never_buy():
    # every other check perfect — the gate still forces AVOID
    v = composite_verdict(FAIL, PASS, PASS, PASS, ZONE_OK)
    assert v["verdict"] == "AVOID"


def test_zone_caution_blocks_buy_even_when_tape_is_bullish():
    v = composite_verdict(PASS, PASS, PASS, PASS, ZONE_CAUTION)
    assert v["verdict"] == "WAIT"


def test_avoid_into_supply_with_sellers_in_control():
    v = composite_verdict(PASS, FAIL, FAIL, FAIL, ZONE_CAUTION)
    assert v["verdict"] == "AVOID"


def test_wait_when_tape_not_confirmed():
    v = composite_verdict(PASS, PASS, FAIL, FAIL, ZONE_NEUTRAL)
    assert v["verdict"] == "WAIT"


def test_wait_when_neither_big_buyers_nor_zone():
    v = composite_verdict(PASS, PASS, PASS, FAIL, ZONE_NEUTRAL)
    assert v["verdict"] == "WAIT"


# ── thin-tape gate ───────────────────────────────────────────────────────────
def test_thin_tape_downgrades_buy_to_wait():
    from orderflow.engine import apply_thin_gate, MIN_TRADES_FOR_VERDICT
    buy = {"verdict": "BUY", "reason": "aligned", "checks": []}
    gated = apply_thin_gate(buy, MIN_TRADES_FOR_VERDICT - 1)
    assert gated["verdict"] == "WAIT" and "thin" in gated["reason"]
    # enough tape → untouched; AVOID/WAIT never upgraded or touched
    assert apply_thin_gate(buy, MIN_TRADES_FOR_VERDICT)["verdict"] == "BUY"
    avoid = {"verdict": "AVOID", "reason": "gate", "checks": []}
    assert apply_thin_gate(avoid, 10)["verdict"] == "AVOID"


# ── analyze_tape end-to-end on a synthetic session ───────────────────────────
def test_analyze_tape_shapes():
    rows = [(30.0 + 0.01 * (i % 7), 300) for i in range(500)]
    out = analyze_tape(_tape(rows))
    assert set(out) >= {"delta", "big_prints", "bursts", "truncated", "last_price"}
    assert out["truncated"] is False
    assert out["delta"]["n_trades"] == 500


# ── ledger grader ────────────────────────────────────────────────────────────
def _daily(closes, start="2026-06-01"):
    idx = pd.bdate_range(start, periods=len(closes))
    return pd.DataFrame({"close": closes}, index=idx)


def test_grade_buy_hit_and_miss():
    df = _daily([100, 102, 103, 104, 105, 106, 107])
    obs = {"et_date": "2026-06-01", "verdict": "BUY", "entry_price": 100.0}
    g = grade(df, obs)
    assert g["hit_1d"] is True and g["fwd_1d_pct"] == 2.0
    assert g["hit_5d"] is True and g["fwd_5d_pct"] == 6.0

    df_down = _daily([100, 97, 96, 95, 94, 93, 92])
    g2 = grade(df_down, {"et_date": "2026-06-01", "verdict": "BUY", "entry_price": 100.0})
    assert g2["hit_1d"] is False


def test_grade_avoid_direction_is_down():
    df = _daily([100, 97, 96, 95, 94, 93, 92])
    g = grade(df, {"et_date": "2026-06-01", "verdict": "AVOID", "entry_price": 100.0})
    assert g["hit_1d"] is True                        # AVOID hits when it FALLS


def test_grade_wait_records_returns_but_no_hit():
    df = _daily([100, 102, 103, 104, 105, 106, 107])
    g = grade(df, {"et_date": "2026-06-01", "verdict": "WAIT", "entry_price": 100.0})
    assert g["hit_1d"] is None and g["fwd_1d_pct"] == 2.0


def test_grade_waits_for_t_plus_1_and_5():
    df = _daily([100])                                 # obs day only — no T+1 yet
    assert grade(df, {"et_date": "2026-06-01", "verdict": "BUY", "entry_price": 100.0}) is None
    df2 = _daily([100, 101, 102])                      # T+1 exists, T+5 doesn't
    g = grade(df2, {"et_date": "2026-06-01", "verdict": "BUY", "entry_price": 100.0})
    assert g["fwd_1d_pct"] == 1.0 and g["fwd_5d_pct"] is None and g["hit_5d"] is None
