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
