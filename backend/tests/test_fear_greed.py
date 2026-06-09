"""Tests for the CNN Fear & Greed mirror (backend/sepa/fear_greed.py).

Pure-parse + band-cutpoint coverage on a fixture shaped exactly like CNN's
graphdata feed — no network. Guards the reshape we depend on (headline, 7
components, previous-reading bands, oldest→newest history) so a CNN field rename
fails loudly instead of silently blanking the dial.
"""
from sepa import fear_greed as fg

# Trimmed but field-faithful sample of CNN's graphdata JSON.
RAW = {
    "fear_and_greed": {
        "score": 28.6, "rating": "fear", "timestamp": "2026-06-09T16:56:24+00:00",
        "previous_close": 40.1, "previous_1_week": 56.0,
        "previous_1_month": 67.2, "previous_1_year": 63.4,
    },
    "fear_and_greed_historical": {
        "data": [
            {"x": 1780963200000.0, "y": 71.2, "rating": "greed"},
            {"x": 1781024184000.0, "y": 28.6, "rating": "fear"},
        ]
    },
    "market_momentum_sp500": {"score": 32.8, "rating": "fear", "data": []},
    "stock_price_strength": {"score": 30.2, "rating": "fear", "data": []},
    "stock_price_breadth": {"score": 19.2, "rating": "extreme fear", "data": []},
    "put_call_options": {"score": 37.6, "rating": "fear", "data": []},
    "market_volatility_vix": {"score": 50, "rating": "neutral", "data": []},
    "safe_haven_demand": {"score": 22.8, "rating": "extreme fear", "data": []},
    "junk_bond_demand": {"score": 7.4, "rating": "extreme fear", "data": []},
}


def test_parse_headline():
    p = fg._parse(RAW)
    assert p["score"] == 28.6
    assert p["score_int"] == 29              # rounded for the dial number
    assert p["rating"] == "fear"
    assert p["rating_label"] == "Fear"
    assert p["source"] == "CNN Business"


def test_parse_seven_components_with_normalized_ratings():
    p = fg._parse(RAW)
    assert len(p["components"]) == 7
    keys = {c["key"] for c in p["components"]}
    assert "market_volatility_vix" in keys and "junk_bond_demand" in keys
    breadth = next(c for c in p["components"] if c["key"] == "stock_price_breadth")
    assert breadth["rating"] == "extreme_fear"        # "extreme fear" → snake key
    assert breadth["rating_label"] == "Extreme Fear"


def test_parse_previous_readings_get_band_labels():
    p = fg._parse(RAW)
    assert p["previous"]["close"]["value"] == 40.1
    assert p["previous"]["close"]["rating"] == "fear"     # 40.1 ∈ [25,45)
    assert p["previous"]["week"]["rating"] == "greed"     # 56 ∈ [55,75)
    assert p["previous"]["month"]["rating"] == "greed"    # 67 ∈ [55,75)
    assert p["previous"]["year"]["rating"] == "greed"     # 63 ∈ [55,75)


def test_parse_history_is_oldest_to_newest():
    p = fg._parse(RAW)
    assert [h["v"] for h in p["history"]] == [71.2, 28.6]
    assert p["history"][0]["rating"] == "greed"


def test_band_cutpoints():
    assert fg._band(10)[0] == "extreme_fear"
    assert fg._band(30)[0] == "fear"
    assert fg._band(50)[0] == "neutral"
    assert fg._band(60)[0] == "greed"
    assert fg._band(90)[0] == "extreme_greed"
    assert fg._band(None)[0] == "unknown"


def test_component_without_score_is_dropped():
    raw = {**RAW, "put_call_options": {"rating": "fear"}}   # missing score
    p = fg._parse(raw)
    assert len(p["components"]) == 6
    assert all(c["key"] != "put_call_options" for c in p["components"])


def test_compute_returns_error_when_feed_down(monkeypatch):
    monkeypatch.setattr(fg, "_fetch_raw", lambda: None)
    out = fg.compute()
    assert out.get("error") == "feed_unavailable"
    assert out.get("source") == "CNN Business"
