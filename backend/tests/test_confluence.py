"""Tests for Top Confluence — the "matches the most screens" meta-scorer."""
from sepa import confluence as cf


def _setup(monkeypatch, all_results, leaders=(), pullback_syms=(),
           whale_docs=(), d13_docs=()):
    monkeypatch.setattr(cf.sepa_scanner, "load_latest",
                        lambda: {"generated_at": 1, "all_results": all_results})
    monkeypatch.setattr(cf.leaderboard, "leaderboard",
                        lambda n=300: {"leaders": list(leaders)})
    monkeypatch.setattr(cf.pullback_ma, "load_latest_pullback",
                        lambda: {"rows": [{"symbol": s} for s in pullback_syms]})

    class _C:
        def __init__(self, docs): self._d = docs
        def find(self, q=None, proj=None): return iter(self._d)

    class _DB:
        def __init__(self):
            self.whales_cache = _C(whale_docs)
            self.whales13d_cache = _C(d13_docs)

    monkeypatch.setattr(cf.history, "_get_db", lambda: _DB())
    cf._CACHE.update(at=0.0, data=None)


def rec(sym, **kw):
    d = {"symbol": sym, "name": sym, "is_candidate": True, "score": 80}
    d.update(kw)
    return d


def test_scores_ranks_and_lists_matches(monkeypatch):
    allr = [
        rec("AAA", is_buyable=True, rating="STRONG_BUY", vcp={"tightness": 75},
            volume={"accumulation_strength": "strong", "cmf_signal": "inflow"},
            insider={"cluster_buy": True}),
        rec("BBB", rating="BUY"),
        rec("CCC", is_candidate=False, rating="STRONG_BUY"),     # not a SEPA candidate
    ]
    _setup(monkeypatch, allr,
           leaders=[{"symbol": "AAA", "persistence_pct": 80, "appearances": 8, "current_rank": 2}],
           pullback_syms={"AAA"},
           whale_docs=[{"ticker": "AAA", "payload": {"moves": {"n_buying": 12}}}],
           d13_docs=[{"ticker": "AAA", "payload": {"filings": [{"bucket": "form13"}]}}])
    o = cf.compute(top_n=5)
    syms = [r["symbol"] for r in o["rows"]]
    assert "CCC" not in syms                          # is_candidate False -> excluded
    assert syms[0] == "AAA"                           # matches the most signals
    aaa = o["rows"][0]
    assert aaa["confluence_score"] >= 20
    assert aaa["match_count"] >= 9
    for m in ("Buyable", "Pullback", "Consistent rank", "STRONG BUY", "Whales +", "13D activist"):
        assert m in aaa["matches"]


def test_political_signal_matches(monkeypatch):
    _setup(monkeypatch, [rec("INTC", rating="BUY")])         # INTC is on the curated list
    o = cf.compute()
    assert "Political" in o["rows"][0]["matches"]


def test_only_sepa_candidates_scored(monkeypatch):
    _setup(monkeypatch, [rec("X", is_candidate=False)])
    o = cf.compute()
    assert o["rows"] == [] and o["n_scored"] == 0


def test_weights_locked():
    assert cf.WEIGHTS["pullback"] == 3 and cf.WEIGHTS["consistent"] == 3
    assert cf.WEIGHTS["whales"] == 2 and cf.WEIGHTS["activist_13d"] == 2
    assert cf.WHALES_ACCUM == 8 and cf.VCP_TIGHT == 70
