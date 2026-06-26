"""Tomorrow Bias scorer tests — pure logic on synthetic data, no network.

Behavioral + negative coverage, plus a regression test for every false-
confidence trap the 2026-06-26 adversarial review forced us to fix:
  - regime label must be the exact enum `market_in_correction` (not "correction")
  - the stock pillar is the BETA RESIDUAL (a pure-beta move scores ~0)
  - a thin after-hours print can never reach HIGH confidence
  - the earnings/event veto trusts abnormal IV, not just a news keyword
  - fast/slow options reads that disagree contribute 0 (no manufactured sign)
  - soir_percentile=None is a half-data pillar that can't unlock HIGH
  - fighting-the-tape (stock vs backdrop oppose) caps confidence
  - the market scorer's VIX-proxy can't auto-confirm the spine it came from
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from options import tomorrow_bias as TB


# --------------------------------------------------------------------------
# fixtures / builders
# --------------------------------------------------------------------------
def eh(gap, bars=20, holding=True, last_close=100.0, session="afterhours", stale=False):
    return {"eh_gap_pct": gap, "eh_bars": bars, "gap_holding": holding,
            "last_rth_close": last_close, "eh_session": session, "stale": stale,
            "data_as_of": "2026-06-26T21:30:00+00:00"}


def soir(sv=None, pct=None, signal=None, em=2.0, iv=40.0, earnings=False):
    return {"soir_volume": sv, "soir_percentile": pct, "signal": signal,
            "expected_move_pct": em, "atm_iv": iv, "earnings_flag": earnings}


def backdrop(spy=0.0, qqq=0.0, regime=TB.REGIME_UPTREND, vix=16.0, vix_pct=40.0):
    return {"spy_gap_pct": spy, "qqq_gap_pct": qqq, "regime_label": regime,
            "vix": vix, "vix_percentile_252d": vix_pct}


# ==========================================================================
# per-ticker: degrade-gracefully / NEUTRAL defaults
# ==========================================================================
def test_no_eh_data_is_neutral_react_at_open():
    out = TB.score_bias(None, soir(), backdrop())
    assert out["lean"] == "NEUTRAL"
    assert out["confidence"] == 0
    assert "no_eh_data" in out["flags"]
    assert "react at the open" in out["reason"].lower()


def test_stale_eh_window_is_neutral():
    out = TB.score_bias(eh(2.0, stale=True), soir(), backdrop())
    assert out["lean"] == "NEUTRAL"
    assert "stale_eh" in out["flags"]


def test_subthreshold_raw_stays_neutral():
    # tiny gap, flat tape, no options edge → nothing clears the lean threshold
    out = TB.score_bias(eh(0.6, bars=20), soir(sv=1.0, pct=55), backdrop(spy=0.05, qqq=0.05))
    assert out["lean"] == "NEUTRAL"


# ==========================================================================
# per-ticker: the showcase confluence + the guardrails
# ==========================================================================
def test_full_bullish_confluence_is_high():
    out = TB.score_bias(
        eh(2.1, bars=28, holding=True, last_close=100.0),
        soir(sv=0.6, pct=88, signal="BULLISH", em=1.4),
        backdrop(spy=0.5, qqq=0.7, regime=TB.REGIME_UPTREND, vix=16),
        beta=1.0,
    )
    assert out["lean"] == "LEAN_UP"
    assert out["confidence"] >= 70
    assert out["confidence_tier"] == "HIGH"
    assert out["agree_count"] == 3


def test_beta_residual_neutralises_a_pure_beta_move():
    # stock +1.5% but SPY also +1.5% with beta 1.0 → residual ~0 → P1 ~0.
    # No options edge, so the lone backdrop push must NOT manufacture a lean.
    out = TB.score_bias(eh(1.5, bars=20), None,
                        backdrop(spy=1.5, qqq=1.5, regime=TB.REGIME_UPTREND), beta=1.0)
    assert abs(out["pillars"]["stock"]["score"]) < 0.05
    assert out["lean"] == "NEUTRAL"


def test_thin_print_can_never_be_high():
    # directional on every pillar, but only 3 after-hours bars → thin print.
    out = TB.score_bias(
        eh(3.4, bars=3, holding=True, last_close=50.0),
        soir(sv=0.4, pct=92, signal="BULLISH", em=2.0),
        backdrop(spy=0.6, qqq=0.7, regime=TB.REGIME_UPTREND, vix=15),
        beta=1.0,
    )
    assert "thin_print" in out["flags"]
    assert out["confidence"] <= 40
    assert out["confidence_tier"] != "HIGH"


def test_event_mode_from_abnormal_iv_forces_neutral_band():
    # no news keyword, but an 8.5% implied move is an earnings/binary tell
    out = TB.score_bias(eh(1.0, bars=20), soir(sv=1.0, pct=55, em=8.5, iv=95),
                        backdrop(spy=0.4, qqq=0.4))
    assert out["lean"] == "NEUTRAL"
    assert "event_risk" in out["flags"]
    assert any(f.startswith("earnings_source:") for f in out["flags"])
    assert out["expected_move_band"] is not None


def test_options_conflict_zeroes_the_pillar():
    # fast (call-heavy volume → bullish) vs slow (low SOIR pct → contrarian bearish)
    out = TB.score_bias(eh(0.7, bars=20), soir(sv=0.5, pct=8),
                        backdrop(spy=0.1, qqq=0.1))
    assert out["pillars"]["options"]["score"] == 0.0
    assert "options_conflict" in out["flags"]


def test_options_partial_when_percentile_missing_cannot_be_high():
    out = TB.score_bias(
        eh(2.1, bars=28, holding=True),
        soir(sv=0.4, pct=None, signal="BULLISH", em=1.4),   # no percentile → half data
        backdrop(spy=0.5, qqq=0.7, regime=TB.REGIME_UPTREND, vix=15),
        beta=1.0,
    )
    assert "options_pillar_partial" in out["flags"]
    assert out["confidence"] <= 50
    assert out["confidence_tier"] != "HIGH"


def test_fighting_the_tape_caps_confidence():
    out = TB.score_bias(
        eh(2.0, bars=25, holding=True),
        soir(sv=0.65, pct=70, em=2.0),
        backdrop(spy=-0.9, qqq=-0.8, regime=TB.REGIME_CORRECTION, vix=31),
        beta=1.0,
    )
    assert "fighting_the_tape" in out["flags"]
    assert "high_vix" in out["flags"]
    assert out["confidence"] <= 55


def test_regime_enum_must_match_exactly_not_substring():
    # The #2 review finding: a "correction" string (wrong enum) must NOT trigger
    # the down-tilt. The exact enum lowers the backdrop pillar; the typo doesn't.
    correct = TB.score_bias(eh(0.6, bars=20), None,
                            backdrop(spy=0.3, qqq=0.3, regime=TB.REGIME_CORRECTION))
    typo = TB.score_bias(eh(0.6, bars=20), None,
                         backdrop(spy=0.3, qqq=0.3, regime="correction"))
    assert correct["pillars"]["backdrop"]["score"] < typo["pillars"]["backdrop"]["score"]


def test_bullish_confluence_in_correction_cannot_be_high():
    # Regression for the review's HIGH finding: a green 3-pillar confluence
    # (up gap + heavy calls + POSITIVE index gap) must NOT read HIGH/LEAN_UP
    # while the regime is market_in_correction — that's fighting the tape.
    out = TB.score_bias(
        eh(3.0, bars=30, holding=True),
        soir(sv=0.3, pct=95, signal="BULLISH", em=2.0),
        backdrop(spy=1.0, qqq=1.0, regime=TB.REGIME_CORRECTION, vix=12),
        beta=1.0,
    )
    assert out["confidence"] < 70
    assert out["confidence_tier"] != "HIGH"
    assert "fighting_the_tape" in out["flags"]


def test_bearish_lean_in_confirmed_uptrend_is_fighting_the_tape():
    out = TB.score_bias(
        eh(-2.5, bars=30, holding=True),
        soir(sv=1.6, pct=8, signal="BEARISH", em=2.0),
        backdrop(spy=-1.0, qqq=-1.0, regime=TB.REGIME_UPTREND, vix=14),
        beta=1.0,
    )
    assert out["lean"] == "LEAN_DOWN"
    assert "fighting_the_tape" in out["flags"]
    assert out["confidence_tier"] != "HIGH"


def test_event_mode_honors_supplied_calendar_source():
    row = soir(sv=1.0, pct=55, em=2.0, iv=40)   # IV normal — only the flag fires
    row["earnings_flag"] = True
    row["earnings_source"] = "calendar"
    out = TB.score_bias(eh(1.0, bars=20), row, backdrop(spy=0.3, qqq=0.3))
    assert out["lean"] == "NEUTRAL"
    assert "event_risk" in out["flags"]
    assert "earnings_source:calendar" in out["flags"]


def test_inside_expected_move_caps_confidence():
    # a +1.0% gap when the options market already implies ±2.0% is not news
    out = TB.score_bias(eh(1.0, bars=25, holding=True),
                        soir(sv=0.5, pct=90, signal="BULLISH", em=2.0),
                        backdrop(spy=0.6, qqq=0.7, regime=TB.REGIME_UPTREND, vix=15),
                        beta=1.0)
    assert "inside_expected_move" in out["flags"]
    assert out["confidence"] <= 60


# ==========================================================================
# market-level scorer
# ==========================================================================
def test_market_indices_disagree_is_neutral():
    out = TB.score_market_bias(0.5, -0.5, "HOLDING", 16, 40, -1,
                               TB.REGIME_UPTREND, 70, breadth=0.5)
    assert out["lean"] == "NEUTRAL"
    assert "indices_disagree" in out["flags"]


def test_market_full_confluence_is_high():
    out = TB.score_market_bias(0.6, 0.7, "HOLDING", 15, 40, -1,
                               TB.REGIME_UPTREND, 70, breadth=0.5)
    assert out["lean"] == "LEAN_UP"
    assert out["confidence_tier"] == "HIGH"
    assert out["agreement_count"] == 3


def test_market_vix_proxy_only_is_not_a_confirmer():
    # vix_dir None (premarket window) → VIX must be neutral, never auto-agree
    out = TB.score_market_bias(0.6, 0.7, "HOLDING", 15, 40, None,
                               TB.REGIME_UPTREND, 70, breadth=0.5)
    assert out["confirmers"]["vix"] == "neutral"
    assert "vix_proxy_only" in out["flags"]
    assert out["confidence_tier"] != "HIGH"   # only breadth+regime agree → 2


def test_market_fading_gap_caps_to_low():
    out = TB.score_market_bias(0.6, 0.7, "FADING", 15, 40, -1,
                               TB.REGIME_UPTREND, 70, breadth=0.5)
    assert out["confidence_tier"] == "LOW"
    assert "gap_fading" in out["flags"]


def test_market_breadth_unavailable_flagged():
    out = TB.score_market_bias(0.6, 0.7, "HOLDING", 15, 40, -1,
                               TB.REGIME_UPTREND, 70, breadth=None)
    assert out["confirmers"]["breadth"] == "neutral"
    assert "breadth_unavailable" in out["flags"]


def test_market_correction_regime_cannot_be_high():
    out = TB.score_market_bias(0.6, 0.7, "HOLDING", 15, 40, -1,
                               TB.REGIME_CORRECTION, 35, breadth=0.5)
    assert out["confidence_tier"] != "HIGH"


# ==========================================================================
# gatherer logic — exercised via the df-injection path (no network)
# ==========================================================================
def _synth_df():
    import pandas as pd
    idx = pd.to_datetime([
        "2026-06-25 19:55", "2026-06-25 19:59",                 # rth
        "2026-06-25 20:05", "2026-06-25 20:30", "2026-06-25 23:30",  # afterhours
    ], utc=True).tz_convert(None)                                # tz-naive UTC, like the loader
    return pd.DataFrame({
        "open": [100, 100, 100.5, 101, 101.8], "high": [100, 100.2, 101, 101.5, 102.1],
        "low": [99.8, 99.9, 100.4, 100.9, 101.6], "close": [100.0, 100.0, 100.8, 101.2, 102.0],
        "volume": [5000, 6000, 800, 1200, 1500],
        "session": ["rth", "rth", "afterhours", "afterhours", "afterhours"],
    }, index=idx)


def test_latest_eh_move_computes_gap_bars_holding():
    m = TB._latest_eh_move("TEST", df=_synth_df())
    assert abs(m["eh_gap_pct"] - 2.0) < 0.01
    assert m["eh_bars"] == 3
    assert m["gap_holding"] is True
    assert m["eh_session"] == "afterhours"
    assert m["last_rth_close"] == 100.0


def test_latest_eh_move_none_when_no_eh_bars():
    df = _synth_df()
    df = df[df["session"] == "rth"]          # only regular-session bars
    assert TB._latest_eh_move("TEST", df=df) is None


def test_eh_stale_afterhours_survives_weekend_but_dies_monday():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    et = lambda *a: datetime(*a, tzinfo=ZoneInfo("America/New_York"))  # noqa: E731
    fri = et(2026, 6, 26, 16, 30)
    assert TB._eh_stale("afterhours", fri, et(2026, 6, 27, 12, 0)) is False   # Sat
    assert TB._eh_stale("afterhours", fri, et(2026, 6, 29, 9, 0)) is False    # Mon pre-open
    assert TB._eh_stale("afterhours", fri, et(2026, 6, 29, 9, 40)) is True    # Mon after open


def test_eh_stale_premarket_expires_at_open():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    et = lambda *a: datetime(*a, tzinfo=ZoneInfo("America/New_York"))  # noqa: E731
    pm = et(2026, 6, 26, 8, 0)
    assert TB._eh_stale("premarket", pm, et(2026, 6, 26, 9, 0)) is False
    assert TB._eh_stale("premarket", pm, et(2026, 6, 26, 9, 40)) is True
