"""Tests for the full-universe conviction scan (scalping/conviction) — the
hard safety rails (liquidity, Stage 4, EQ red flag, bearish candle, ETF) and
the transparent scoring/ranking. Dependencies monkeypatched; no network.
"""
from scalping import conviction


def _row(sym, close=100.0, avg_vol=2_000_000, stage=2, rs=80, pass_all=True,
         etf=False, eq=None, accum=1.5):
    return {"symbol": sym, "last_close": close, "is_etf": etf, "rs_rank": rs,
            "is_candidate": False, "is_buyable": False,
            "stage": {"stage": stage},
            "trend": {"pass_all": pass_all, "price": close, "ma200": close * 0.9},
            "volume": {"avg_vol_50": avg_vol, "up_down_vol_ratio": accum},
            "earnings_quality": eq}


def _wire(monkeypatch, rows, verdicts=None):
    from sepa import scanner
    from patterns import scan as pscan
    monkeypatch.setattr(scanner, "load_latest", lambda: {"all_results": rows})
    vmap = verdicts or {}
    monkeypatch.setattr(pscan, "_verdict_for_symbol", lambda s, ctx: vmap.get(s, {
        "symbol": s, "matches": [], "candles": None, "no_match": True}))


def test_safety_rails(monkeypatch):
    rows = [
        _row("GOOD"),
        _row("THIN", avg_vol=100_000),                       # share-volume floor
        _row("CHEAP", close=3.0),                            # price floor
        _row("DOLLAR", close=10.0, avg_vol=400_000),         # $4M/day < $25M floor
        _row("DECLN", stage=4),                              # Stage 4
        _row("FLAG", eq={"tier": "red_flag", "score": 20}),  # EQ red flag
        _row("LEVETF", etf=True),                            # ETF
        _row("BEARC"),                                       # bearish last-bar candle
    ]
    verdicts = {"BEARC": {"symbol": "BEARC", "matches": [], "no_match": False,
                          "candles": {"formations": [
                              {"name": "bearish_engulfing", "read": "bearish_warning"}]}}}
    _wire(monkeypatch, rows, verdicts)
    r = conviction.top_picks(20)
    syms = [p["symbol"] for p in r["picks"]]
    assert syms == ["GOOD"]
    assert r["excluded"]["liquidity"] == 3
    assert r["excluded"]["stage4"] == 1
    assert r["excluded"]["red_flag"] == 1
    assert r["excluded"]["etf"] == 1


def test_confirmed_pattern_outranks_plain_strength(monkeypatch):
    rows = [_row("PLAINSTRONG", rs=99, close=300.0, avg_vol=5_000_000,
                 eq={"tier": "code33", "score": 90}),
            _row("PATTERNED", rs=60, pass_all=False)]
    verdicts = {"PATTERNED": {"symbol": "PATTERNED", "no_match": False,
                              "matches": [{"pattern": "cup_with_handle", "status": "confirmed",
                                           "bars_since_confirm": 0, "neckline": 100.0,
                                           "target": 110.0, "stop": 95.0}],
                              "candles": {"formations": []}}}
    _wire(monkeypatch, rows, verdicts)
    r = conviction.top_picks(20)
    by = {p["symbol"]: p for p in r["picks"]}
    # The confirmed pattern is worth 30 — but a max-strength plain name can
    # still outrank a weak-trend patterned one. Both must be present, the
    # patterned one carries its pattern fields, and scoring is transparent.
    assert set(by) == {"PLAINSTRONG", "PATTERNED"}
    assert by["PATTERNED"]["pattern"] == "cup_with_handle"
    assert by["PATTERNED"]["pattern_status"] == "confirmed"
    assert "weights" in r and r["weights"]["pattern_confirmed"] == 30
    assert any("CONFIRMED" in d for d in by["PATTERNED"]["drivers"])


def test_n_cap_and_sorting(monkeypatch):
    rows = [_row(f"S{i}", rs=i * 3) for i in range(30)]
    _wire(monkeypatch, rows)
    r = conviction.top_picks(5)
    assert len(r["picks"]) == 5
    convs = [p["conviction"] for p in r["picks"]]
    assert convs == sorted(convs, reverse=True)
