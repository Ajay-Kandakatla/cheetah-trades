"""Tests for Money Movement — fund-centric inversion of the 13F whale cache.

Pure: a fake whales_cache + monkeypatched scan/pullback so we assert the
inversion, the type -> section grouping, the SEPA/Pullback overlap flags, and
the $-added formula.
"""
from sepa import money_movement as mm


def _doc(ticker, holders):
    return {"ticker": ticker, "payload": {"holders": holders}}


def _h(name, typ, value, pct_change, pct_held=0.02):
    return {"holder": name, "type": typ, "value": value,
            "pct_change": pct_change, "pct_held": pct_held}


def _setup(monkeypatch, docs, sepa_syms=(), pullback_syms=()):
    class _Coll:
        def find(self, q=None, proj=None):
            return iter(docs)

    class _DB:
        whales_cache = _Coll()

    monkeypatch.setattr(mm.history, "_get_db", lambda: _DB())
    tickers = {d["ticker"] for d in docs} | set(sepa_syms)
    allr = [{"symbol": s, "is_candidate": s in set(sepa_syms), "name": s} for s in tickers]
    monkeypatch.setattr(mm.sepa_scanner, "load_latest",
                        lambda: {"generated_at": 1, "all_results": allr})
    monkeypatch.setattr(mm.pullback_ma, "load_latest_pullback",
                        lambda: {"rows": [{"symbol": s} for s in pullback_syms]})
    mm._CACHE.update(at=0.0, data=None)


def test_added_usd_formula():
    assert mm._added_usd(150, 0.5) == 50.0        # 150 * 0.5 / 1.5
    assert mm._added_usd(None, 0.5) is None
    assert mm._added_usd(100, -1.0) is None       # sold to zero -> undefined


def test_section_mapping_constant():
    assert mm.SECTION_OF == {"hedge_fund": "hedge_fund",
                             "index_giant": "institutional", "other": "whales"}


def test_inversion_groups_by_type_and_flags_overlap(monkeypatch):
    docs = [
        _doc("AAA", [_h("Two Sigma Investments, LP", "hedge_fund", 100e6, 0.5),
                     _h("Vanguard Group Inc", "index_giant", 1e9, 0.1)]),
        _doc("BBB", [_h("Two Sigma Investments, LP", "hedge_fund", 50e6, 1.0),
                     _h("Morgan Stanley", "other", 200e6, 0.2)]),
    ]
    _setup(monkeypatch, docs, sepa_syms={"AAA"}, pullback_syms={"BBB"})
    o = mm.compute()

    # Two Sigma -> hedge_fund section, holds BOTH AAA and BBB in one row.
    ts = next(r for r in o["sections"]["hedge_fund"] if "Two Sigma" in r["fund"])
    assert ts["n_stocks"] == 2
    assert {s["ticker"] for s in ts["stocks"]} == {"AAA", "BBB"}
    aaa = next(s for s in ts["stocks"] if s["ticker"] == "AAA")
    bbb = next(s for s in ts["stocks"] if s["ticker"] == "BBB")
    assert aaa["is_sepa"] is True and bbb["is_pullback"] is True
    assert ts["n_sepa"] == 1 and ts["n_pullback"] == 1
    assert ts["stocks"][0]["ticker"] in ("AAA", "BBB")          # overlaps sort first

    # Vanguard -> institutional, Morgan Stanley -> whales.
    assert any("Vanguard" in r["fund"] for r in o["sections"]["institutional"])
    assert any("Morgan Stanley" in r["fund"] for r in o["sections"]["whales"])


def test_net_seller_without_overlap_is_excluded(monkeypatch):
    docs = [_doc("AAA", [_h("Some Fund LLC", "other", 100e6, -0.3)])]   # selling, no overlap
    _setup(monkeypatch, docs)
    o = mm.compute()
    assert all(len(o["sections"][s]) == 0 for s in mm.SECTIONS)


def test_overlap_only_fund_is_kept_even_if_flat(monkeypatch):
    # No net buying ($ added 0) but it holds a SEPA name -> still surfaced.
    docs = [_doc("AAA", [_h("Niche Capital", "other", 100e6, 0.0)])]
    _setup(monkeypatch, docs, sepa_syms={"AAA"})
    o = mm.compute()
    assert any("Niche Capital" in r["fund"] for r in o["sections"]["whales"])


def test_mongo_unavailable(monkeypatch):
    monkeypatch.setattr(mm.history, "_get_db", lambda: None)
    mm._CACHE.update(at=0.0, data=None)
    o = mm.compute()
    assert o["error"] == "mongo_unavailable"
    assert all(o["sections"][s] == [] for s in mm.SECTIONS)


# ── SEC big-moves + political legs ───────────────────────────────────────────
def _full_setup(monkeypatch, whales_docs, d13_docs, allr, sepa_syms=(), pullback_syms=()):
    class _Coll:
        def __init__(self, docs): self._docs = docs
        def find(self, q=None, proj=None): return iter(self._docs)

    class _DB:
        def __init__(self):
            self.whales_cache = _Coll(whales_docs)
            self.whales13d_cache = _Coll(d13_docs)

    monkeypatch.setattr(mm.history, "_get_db", lambda: _DB())
    monkeypatch.setattr(mm.sepa_scanner, "load_latest", lambda: {"generated_at": 1, "all_results": allr})
    monkeypatch.setattr(mm.pullback_ma, "load_latest_pullback",
                        lambda: {"rows": [{"symbol": s} for s in pullback_syms]})
    mm._CACHE.update(at=0.0, data=None)


def _wd(ticker, n_buying):
    return {"ticker": ticker, "payload": {"holders": [_h("X Fund", "other", 1e6, 0.1)],
                                          "moves": {"n_buying": n_buying}}}


def _d13(ticker, n13, n4=0):
    fl = [{"bucket": "form13"} for _ in range(n13)] + [{"bucket": "form4"} for _ in range(n4)]
    return {"ticker": ticker, "payload": {"filings": fl}}


def test_sec_moves_detects_activist_cluster_and_coordinated(monkeypatch):
    allr = [
        {"symbol": "ACT", "is_candidate": True, "name": "Act Inc"},
        {"symbol": "CRD", "is_candidate": False, "name": "Crd Inc"},
        {"symbol": "INS", "is_candidate": True, "name": "Ins Inc", "insider": {"cluster_buy": True}},
    ]
    _full_setup(monkeypatch, [_wd("CRD", 15)], [_d13("ACT", 8)], allr, sepa_syms={"ACT", "INS"})
    o = mm.compute()
    sm = {r["ticker"]: r for r in o["sec_moves"]}
    assert "activist_13d" in sm["ACT"]["signals"] and sm["ACT"]["n_form13"] == 8
    assert "coordinated_funds" in sm["CRD"]["signals"]
    assert "insider_cluster" in sm["INS"]["signals"]
    assert o["sec_moves"][0]["ticker"] == "ACT"          # activist scores highest
    assert sm["ACT"]["is_sepa"] is True


def test_political_sections_and_not_wired(monkeypatch):
    allr = [{"symbol": "INTC", "is_candidate": True, "name": "Intel"}]
    _full_setup(monkeypatch, [_wd("INTC", 7)], [], allr, sepa_syms={"INTC"})
    o = mm.compute()
    pot = {r["ticker"] for r in o["political"]["potus_family"]}
    gov = {r["ticker"] for r in o["political"]["us_gov"]}
    assert "INTC" in pot and "INTC" in gov              # INTC is potus_family + govt_investment
    assert "AAPL" in pot                                # in the curated list (not in scan)
    intc = next(r for r in o["political"]["potus_family"] if r["ticker"] == "INTC")
    assert intc["is_sepa"] is True and intc["in_scan"] is True
    aapl = next(r for r in o["political"]["potus_family"] if r["ticker"] == "AAPL")
    assert aapl["in_scan"] is False
    assert any("retail" in s.lower() for s in o["not_wired"])
