"""Tests for the qualifier verdict scan (patterns/scan._verdict_for_symbol) —
the load-bearing behavior is that EVERY qualifier gets an answer: a match,
candle reads, or an explicit no-match. Ajay 2026-06-09: "what pattern it
matches … [or] if it does not match."
"""
import numpy as np
import pandas as pd

from patterns import scan


def _df(closes, start="2025-06-01"):
    idx = pd.bdate_range(start, periods=len(closes))
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({"open": np.r_[c[0], c[:-1]], "high": c + 0.5, "low": c - 0.5,
                         "close": c, "volume": np.full(len(c), 1e6)}, index=idx)


def _frames():
    quiet = list(100 + np.random.RandomState(3).normal(0, 0.2, 30))
    w = (list(np.linspace(100, 80, 25)) + list(np.linspace(80, 92, 13)) +
         list(np.linspace(92, 80, 13)) + list(np.linspace(80, 95, 12)))
    return {"WSTOCK": _df(quiet + w),             # ≥80 bars, ends on a confirmed W
            "PLAIN": _df(list(np.linspace(100, 130, 120)))}


def test_verdict_row_match_and_no_match(monkeypatch):
    from sepa import prices
    frames = _frames()
    monkeypatch.setattr(prices, "load_prices", lambda s, **k: frames[s].copy())

    hit = scan._verdict_for_symbol("WSTOCK", {"rs_rank": 95})
    assert hit["matches"] and hit["no_match"] is False
    assert hit["matches"][0]["symbol"] == "WSTOCK"
    assert hit["historical"].get("double_bottom", 0) >= 1
    # one verdict per pattern kind — never two double-bottom chips on one row
    kinds = [m["pattern"] for m in hit["matches"]]
    assert len(kinds) == len(set(kinds))

    miss = scan._verdict_for_symbol("PLAIN", {"rs_rank": 50})
    assert miss["matches"] == []
    assert miss["no_match"] is True                # the explicit answer
    assert miss["candles"] is not None             # last-bar read still present


def _stub_module(monkeypatch, name, **attrs):
    """Install a fake module (and bind it on an already-imported parent) so the
    test never imports the real one — some use py3.10+ type syntax that the
    host's 3.9 venv can't parse (the container runs 3.11)."""
    import sys
    import types
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    monkeypatch.setitem(sys.modules, name, mod)
    parent, _, child = name.rpartition(".")
    if parent:
        if parent not in sys.modules:
            monkeypatch.setitem(sys.modules, parent, types.ModuleType(parent))
        monkeypatch.setattr(sys.modules[parent], child, mod, raising=False)
    return mod


def test_verdict_universe_merges_sources(monkeypatch):
    """Cross-linking contract: holdings / buyable / at-pivot / leaderboard names
    join the qualifier set, each tagged with every source it belongs to."""
    monkeypatch.setattr(scan, "_universe_with_context", lambda: (
        ["AAA", "BBB"],
        {"AAA": {"is_candidate": True, "is_buyable": True},
         "BBB": {"is_candidate": True, "is_buyable": False}}))
    _stub_module(monkeypatch, "portfolio.store",
                 list_holdings=lambda owner: [{"ticker": "CCC"}, {"ticker": "AAA"}])
    _stub_module(monkeypatch, "sepa.at_pivot",
                 get_at_pivot=lambda: {"rows": [{"symbol": "BBB"}]})
    _stub_module(monkeypatch, "sepa.leaderboard",
                 leaderboard=lambda n=12: {"leaders": [{"symbol": "DDD"}]})

    u = scan._verdict_universe()
    assert set(u) == {"AAA", "BBB", "CCC", "DDD"}
    assert u["AAA"]["sources"] == ["qualifier", "buyable", "holding"]
    assert u["CCC"]["sources"] == ["holding"] and u["CCC"]["ctx"] == {}
    assert "at_pivot" in u["BBB"]["sources"]
    assert u["DDD"]["sources"] == ["leader"]


def test_short_frame_reports_error_not_silence(monkeypatch):
    from sepa import prices
    monkeypatch.setattr(prices, "load_prices", lambda s, **k: _df([100] * 20))
    row = scan._verdict_for_symbol("TINY", {})
    assert row["error"]
    assert row["no_match"] is True
