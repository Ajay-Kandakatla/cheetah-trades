"""Portfolio hold/sell — market-regime defensive overlay (behavioral, 2026-06-05).

The verdict was purely bottom-up (per-stock); this adds the top-down market read so
a risk-off tape steps every holding HOLD->TIGHTEN (and toward REDUCE when the name
itself is also weak). Verifies the posture banding + that _market_posture assembles
our three reads (macro regime + S&P/Nasdaq confirmation + breadth). See
docs/sepa/market_aware_verdict_methodology.md.
"""
from sepa import position_lens as pl


def test_posture_bands():
    # risk_off: severe/high macro, OR market not confirmed for longs, OR breadth >=65% red.
    assert pl._posture_from("high", None, 58) == "risk_off"
    assert pl._posture_from("severe", True, 20) == "risk_off"        # severe macro alone
    assert pl._posture_from("low", False, 20) == "risk_off"          # S&P/Nasdaq not confirmed
    assert pl._posture_from("low", True, 70) == "risk_off"           # breadth >= 65
    # caution: elevated macro or 55-64% red.
    assert pl._posture_from("elevated", True, 40) == "caution"
    assert pl._posture_from("low", True, 56) == "caution"
    # constructive: calm + green-ish.
    assert pl._posture_from("low", True, 30) == "constructive"
    assert pl._posture_from("unknown", None, None) == "constructive"  # no data => no false alarm


def test_market_posture_assembles(monkeypatch):
    monkeypatch.setattr("sepa.macro_risk.get_market", lambda: {"level": "high", "score": 55})
    monkeypatch.setattr("sepa.market_context.market_state", lambda: {"safe_to_long": False})
    rows = [{"day_change_pct": -1.0}] * 60 + [{"day_change_pct": 1.0}] * 40   # 60% red
    monkeypatch.setattr("sepa.scanner.load_latest", lambda: {"all_results": rows})
    mp = pl._market_posture()
    assert mp["posture"] == "risk_off"
    assert mp["level"] == "high" and mp["breadth_red_pct"] == 60 and mp["safe_to_long"] is False
    assert any("macro high" in d for d in mp["drivers"])
    assert any("not in a confirmed uptrend" in d for d in mp["drivers"])


def test_market_posture_constructive_when_calm(monkeypatch):
    monkeypatch.setattr("sepa.macro_risk.get_market", lambda: {"level": "low", "score": 20})
    monkeypatch.setattr("sepa.market_context.market_state", lambda: {"safe_to_long": True})
    rows = [{"day_change_pct": 1.0}] * 70 + [{"day_change_pct": -1.0}] * 30    # 30% red
    monkeypatch.setattr("sepa.scanner.load_latest", lambda: {"all_results": rows})
    assert pl._market_posture()["posture"] == "constructive"
