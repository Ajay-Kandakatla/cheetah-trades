"""Tests for the confirmed-bullish rally screen (scalping/rally) — the three
gates (confirmed bullish, dollar room, no bearish candle) and the confluence
ranking. All dependencies monkeypatched; no network, no Mongo.
"""
from scalping import rally


def _wire(monkeypatch, verdicts):
    import daytrading.universe as du
    from sepa import scanner
    from patterns import scan as pscan
    from scalping import sepa_watch
    monkeypatch.setattr(du, "day_trade_universe", lambda profile="aggressive", limit=120: {
        "names": [
            {"symbol": "BIGR", "adr_pct": 4.0, "last_close": 200.0, "rs_rank": 92},   # $8/day
            {"symbol": "TINY", "adr_pct": 6.0, "last_close": 9.0, "rs_rank": 80},     # $0.54/day
            {"symbol": "BEAR", "adr_pct": 5.0, "last_close": 100.0, "rs_rank": 85},   # $5/day, bearish candle
            {"symbol": "PLAIN", "adr_pct": 5.0, "last_close": 80.0, "rs_rank": 70},   # $4/day, nothing confirmed
        ]})
    monkeypatch.setattr(scanner, "load_latest", lambda: {"all_results": [
        {"symbol": "BUYM", "is_buyable": True, "adr_pct": 3.0, "last_close": 150.0,
         "rs_rank": 95, "is_etf": False}]})                                            # $4.5/day, buyable
    monkeypatch.setattr(pscan, "verdicts_for", lambda syms: {"verdicts": [
        verdicts[s] for s in syms if s in verdicts]})
    monkeypatch.setattr(sepa_watch, "tape_read", lambda s: {
        "ok": True, "read": {"state": "BREAKOUT_STRONG", "verdict": "constructive"}})


def _v(sym, confirmed=False, buyable=False, bearish=False, today=True):
    return {"symbol": sym,
            "sepa": {"is_buyable": buyable},
            "matches": ([{"pattern": "cup_with_handle", "status": "confirmed",
                          "bars_since_confirm": 0 if today else 1, "neckline": 100.0,
                          "target": 110.0, "stop": 95.0}] if confirmed else []),
            "candles": {"formations": ([{"name": "bearish_engulfing",
                                         "read": "bearish_warning"}] if bearish else [])},
            "no_match": not confirmed}


def test_gates_and_ranking(monkeypatch):
    _wire(monkeypatch, {
        "BIGR": _v("BIGR", confirmed=True, buyable=True),    # ⭐ confluence, $8
        "TINY": _v("TINY", confirmed=True),                  # confirmed but $0.54 — gated out
        "BEAR": _v("BEAR", confirmed=True, bearish=True),    # bearish candle — disqualified
        "PLAIN": _v("PLAIN"),                                # nothing confirmed — out
        "BUYM": _v("BUYM", buyable=True),                    # buyable, $4.5
    })
    r = rally.candidates("aggressive", min_dollar_move=2.0)
    syms = [c["symbol"] for c in r["candidates"]]
    assert syms == ["BIGR", "BUYM"]                # confluence first, then by $ range
    assert "TINY" not in syms and "BEAR" not in syms and "PLAIN" not in syms
    big = r["candidates"][0]
    assert big["dollar_range"] == 8.0
    assert big["confirmed_pattern"] == "cup_with_handle" and big["is_buyable"]
    assert big["tape_state"] == "BREAKOUT_STRONG"  # live tape attached to leaders
    assert "capacity" in r["disclaimer"].lower() or "TYPICALLY" in r["disclaimer"]


def test_min_dollar_is_tunable(monkeypatch):
    _wire(monkeypatch, {"BIGR": _v("BIGR", confirmed=True), "BUYM": _v("BUYM", buyable=True)})
    r = rally.candidates("aggressive", min_dollar_move=6.0)
    assert [c["symbol"] for c in r["candidates"]] == ["BIGR"]   # $4.5 BUYM gated out
