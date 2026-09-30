"""🏷️ Under Value → vs peers (Ajay 2026-09-29: "... Market cap and stock price
is very low at least 50% low compared to peers", then "Use the same tab
actually").

Synthetic rows only: `_load_inputs` / `_load_enrichment` / scan_generation are
stubbed, the price loader is stubbed, nothing reaches Mongo or the network.
The NEGATIVES carry the weight — each is a row the live scan really has
(yfinance ADR revenue, a lower-bound cap, Massive's missing FY-Q4 quarter).
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chart_maps import board as B  # noqa: E402
from chart_maps import undervalue_peers as UVP  # noqa: E402
# Real modules imported BEFORE the price stub below replaces sepa.prices:
# ath_history reads prices.CACHE_TTL_SEC at ITS import time and board()
# imports ath_tab lazily.
import chart_maps.ath_tab  # noqa: E402,F401
import supply_demand.into_supply  # noqa: E402,F401

GEN = 1_790_000_000          # a scan mtime (2026-09-21 ET)
PERIODS8 = [8105, 8104, 8103, 8102, 8101, 8100, 8099, 8098]
# cardLadder.ts ENTRY_PREFIX / PRICE_PREFIX / PRICE_AFTER_PREFIX, literally.
LADDER_PREFIXES = ("\U0001F52A closed under the floor", "Reports ", "S4 Decline",
                   "S3 Topping", "◉ ", "→ ", "↓ ", "↑ ", "\U0001FA79 ", "\U0001F680 ",
                   "\U0001F511 ", "\U0001F3D4️ ", "↘️ ", "⚡ Tape burst",
                   "⚡ Pocket pivot", "⚡ Sell burst", "\U0001F4B0 ", "\U0001F53B ")


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
def _frame(n=200, start=90.05, step=0.05):
    idx = pd.bdate_range("2026-01-01", periods=n)
    close = [start + i * step for i in range(n)]
    return pd.DataFrame({"open": [c - 0.05 for c in close],
                         "high": [c + 0.20 for c in close],
                         "low": [c - 0.20 for c in close],
                         "close": close, "volume": [1_000_000] * n}, index=idx)


@pytest.fixture
def prices(monkeypatch):
    """Local twin of test_chart_maps' price stub (not importable across files)."""
    store: dict = {}

    class _Prices:
        PERIOD_DAYS = {"2y": 504}

        @staticmethod
        def load_prices(symbol, *a, **kw):
            return store.get(symbol.upper())

    mod = _Prices()
    monkeypatch.setitem(sys.modules, "sepa.prices", mod)
    import sepa
    monkeypatch.setattr(sepa, "prices", mod, raising=False)
    return store


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    UVP._memo.clear()
    from chart_maps import dual_momentum_tab
    monkeypatch.setattr(dual_momentum_tab, "scan_generation", lambda: GEN)
    yield
    UVP._memo.clear()


def _rev(ttm_now, ttm_prior):
    return [ttm_now / 4.0] * 4 + [ttm_prior / 4.0] * 4


class U:
    """A synthetic universe: scan rows, snapshots, caps, cap meta."""

    def __init__(self):
        self.rows, self.snaps, self.caps, self.meta = [], {}, {}, {}

    def add(self, sym, ps=10.0, ttm=1e9, prior=None, q=30.0, sector="Technology",
            industry="Semis", periods=None, source="massive", cap=None,
            cap_source="reported", rev=None, rvol=None, snap=True):
        prior = ttm / 1.25 if prior is None else prior
        liq = {"avg_dollar_vol": 50e6}
        if rvol is not None:
            liq["rvol"] = rvol
        self.rows.append({"symbol": sym, "sector": sector, "industry": industry,
                          "last_close": 100.0, "liquidity": liq})
        if snap:
            self.snaps[sym] = {
                "sales": {"tier": "strong", "growth_yoy_pct": q, "score": 55},
                "rev_q_series": rev if rev is not None else _rev(ttm, prior),
                "q_period_series": list(PERIODS8) if periods is None else periods,
                "_source": source}
        self.caps[sym] = (ps * ttm) if cap is None else cap
        self.meta[sym] = {"as_of": GEN - 86400 * 10, "cap_source": cap_source,
                          "has_shares": True}
        return self

    def peers(self, n=6, ps=10.0, **kw):
        for i in range(n):
            self.add(f"P{i}{kw.get('industry', 'Semis')[:2].upper()}", ps=ps, q=5.0, **kw)
        return self

    def build(self):
        return UVP.build(self.rows, self.snaps, self.caps, self.meta, generation=GEN,
                         scan_generated_at=GEN)

    def install(self, monkeypatch, bm=None, er=None, calls=None):
        def _inputs():
            if calls is not None:
                calls.append(1)
            return {"rows": self.rows, "snaps": self.snaps, "caps": self.caps,
                    "cap_meta": self.meta, "generation": GEN, "scan_generated_at": GEN}
        monkeypatch.setattr(UVP, "_load_inputs", _inputs)
        monkeypatch.setattr(UVP, "_load_enrichment",
                            lambda p, q: (bm or {}, er or {}))
        return self


def _passed(entry):
    return [p["symbol"] for p in entry["passed"]]


def _row(entry, sym):
    return next(p for p in entry["passed"] if p["symbol"] == sym)


def _bm(ev=None, cash=5e8, debt=1e8, fcf=3.0, dil=-1.0, roce=12.0, meaningful=True):
    return {"ev_sales": ev, "cash": cash, "debt": debt, "fcf_yield": fcf,
            "shares_yoy_pct": dil, "roce_pct": roce, "balance_meaningful": meaningful}


# ---------------------------------------------------------------------------
# positives
# ---------------------------------------------------------------------------
def test_a_name_at_a_fifth_of_its_peers_passes_with_every_stat_in_order(monkeypatch):
    u = U().peers(6).add("CHEAP", ps=2.0, q=30.0)
    bm = {f"P{i}SE": _bm(ev=9.0) for i in range(6)}
    bm["CHEAP"] = _bm(ev=1.5)
    er = {"CHEAP": {"next_date": "2026-10-28", "when": "amc"}}
    u.install(monkeypatch, bm=bm, er=er)
    entry = UVP.read()
    assert _passed(entry) == ["CHEAP"]
    r = _row(entry, "CHEAP")
    assert r["group_kind"] == "industry" and r["peer_n"] == 6
    assert r["ratio"] == pytest.approx(0.2) and r["discount_pct"] == 80.0
    assert "peers" not in r, "peer lists are never served"
    parts = UVP.tile_parts(r)
    keys = [s["k"] for s in parts["stats"]]
    assert keys == ["P/S", "Peer P/S", "vs peers", "Peers", "EV/Sales", "Sales YoY Q",
                    "Sales TTM", "TTM rev", "Mkt cap", "Next ER"]
    v = {s["k"]: s["v"] for s in parts["stats"]}
    assert v["P/S"] == "2.0x" and v["Peer P/S"] == "10.0x"
    assert v["vs peers"] == "80% below"
    assert v["Peers"] == "Semis · 6"
    assert v["EV/Sales"] == "1.5x vs 9.0x"
    assert v["Sales YoY Q"] == "+30% · peers +5%"
    assert v["Sales TTM"] == "+25% · peers +25%"
    assert v["TTM rev"] == "$1.0B · FY2026 Q2"
    assert v["Mkt cap"].startswith("$2.0B · shares fetched ") and "× close 2026-" in v["Mkt cap"]
    assert v["Next ER"] == "2026-10-28 amc"
    assert parts["badges"][0]["text"].startswith(UVP.MARK + " 2.0x sales vs peers' 10.0x")
    assert not any(b["text"].startswith("⚠️") for b in parts["badges"]), \
        "EV/Sales also below peers -> no ⚠️"
    assert "80% below the median of 6 Semis peers" in parts["why"]


def test_deepest_discount_first_ties_by_symbol():
    u = U().peers(6).add("BBB", ps=2.0).add("AAA", ps=2.0).add("CCC", ps=1.0)
    assert _passed(u.build()) == ["CCC", "AAA", "BBB"]


def test_sector_fallback_is_counted_and_chipped():
    u = U().peers(6, industry="Other").add("LONE", ps=2.0, industry="Tiny")
    for i in range(3):
        u.add(f"T{i}", ps=10.0, q=5.0, industry="Tiny")
    e = u.build()
    r = _row(e, "LONE")
    assert r["group_kind"] == "sector" and r["peer_n"] == 9
    assert e["counts"]["sector_fallback"] == 1
    parts = UVP.tile_parts(UVP.enrich(e, {}, {})["passed"][0])
    assert any(b["text"].startswith("⚖️ Sector peers — Tiny had under 5") for b in parts["badges"])
    assert {s["k"]: s["v"] for s in parts["stats"]}["Peers"] == "Technology (sector) · 9"


def test_peer_growth_medians_and_counts():
    u = U()
    for i, q in enumerate((10.0, 20.0, 30.0, 40.0, 50.0)):
        u.add(f"G{i}", ps=10.0, q=q, prior=1e9 / (1 + q / 100.0))
    u.add("CHEAP", ps=2.0, q=60.0)
    r = _row(u.build(), "CHEAP")
    assert r["q_yoy_peer_median"] == 30.0 and r["q_yoy_peer_n"] == 5
    assert r["ttm_growth_peer_median"] == 30.0 and r["ttm_growth_peer_n"] == 5


def test_phase_reached_keeps_only_in_band(prices, monkeypatch):
    u = U().peers(6).add("INB", ps=2.0).add("AWAY", ps=2.5)
    u.install(monkeypatch)
    for s in ("INB", "AWAY"):
        prices[s] = _frame()
    monkeypatch.setattr(B, "_uv_band_state",
                        lambda z, df, last: ("in", 0.0) if df is prices["INB"] else ("away", None))
    out = B.undervalue_peer_tiles(limit=5, min_tier="any", phase="reached")
    assert [t["symbol"] for t in out["tiles"]] == ["INB"]
    assert out["tiles"][0]["badges"][0]["text"] == "◉ in the demand band"
    all_ = B.undervalue_peer_tiles(limit=5, min_tier="any")
    assert [t["symbol"] for t in all_["tiles"]] == ["INB", "AWAY"]


def test_the_rvol_sort_reorders_via_the_scan_row(prices, monkeypatch):
    u = U().peers(6).add("DEEP", ps=1.0, rvol=1.1).add("LOUD", ps=2.0, rvol=4.0)
    u.install(monkeypatch)
    for s in ("DEEP", "LOUD"):
        prices[s] = _frame()
    d = B.undervalue_peer_tiles(limit=5, min_tier="any")
    assert [t["symbol"] for t in d["tiles"]] == ["DEEP", "LOUD"]
    UVP._memo.clear()
    r = B.undervalue_peer_tiles(limit=5, min_tier="any", sort="rvol")
    assert [t["symbol"] for t in r["tiles"]] == ["LOUD", "DEEP"]


def test_board_serves_the_peers_view_with_attach_keys_and_no_flat_metrics(prices, monkeypatch):
    u = U().peers(6).add("CHEAP", ps=2.0)
    u.install(monkeypatch)
    prices["CHEAP"] = _frame()
    raw = B.undervalue_peer_tiles(limit=5, min_tier="any")
    t0 = raw["tiles"][0]
    assert "band_structure" not in t0
    for k in ("avg_turnover", "rvol", "turnover"):
        assert k not in t0, "tile_metrics must never be spread flat"
    UVP._memo.clear()
    out = B.board("undervalue", limit=5, min_tier="any", uv="peers")
    assert [t["symbol"] for t in out["tiles"]] == ["CHEAP"]
    assert "explosive" in out["tiles"][0] and "band_structure" in out["tiles"][0]
    assert "_uvp_entry" not in out
    blk = out["undervalue_view"]
    assert blk["view"] == "peers" and blk["counts"]["passed"] == 1
    assert out["note"] == UVP.NOTE
    json.dumps(out, allow_nan=False, default=str)


def test_memo_reads_once_inside_ttl_and_rebuilds_on_a_new_generation(monkeypatch):
    calls: list = []
    U().peers(6).add("CHEAP", ps=2.0).install(monkeypatch, calls=calls)
    a = UVP.read()
    b = UVP.read()
    assert len(calls) == 1 and a is b
    from chart_maps import dual_momentum_tab
    monkeypatch.setattr(dual_momentum_tab, "scan_generation", lambda: GEN + 60)
    UVP.read()
    assert len(calls) == 2


def test_view_block_carries_words_only_on_the_peers_view():
    e = U().peers(6).add("CHEAP", ps=2.0).build()
    p = UVP.view_block("peers", {"counts": e["counts"]})
    assert p["view"] == "peers" and p["default"] == "psg" and p["param"] == "uv"
    assert [o["key"] for o in p["options"]] == ["psg", "peers"]
    assert p["measured"] is False
    assert p["header"].startswith(UVP.MARK + " 1 at ≤ 50% of their peers' P/S")
    assert p["note"] == UVP.NOTE and p["counts"]["passed"] == 1
    assert p["constants"] == {"peer_ps_max_fraction": 0.5, "min_peers": 5,
                              "min_sales_yoy_q_pct": 20.0,
                              "min_sales_ttm_growth_pct": 20.0,
                              "min_ttm_revenue_usd": 100_000_000.0}
    s = UVP.view_block("psg")
    assert s["view"] == "psg"
    assert s["header"] is None and s["note"] is None
    assert s["counts"] is None and s["constants"] is None


# ---------------------------------------------------------------------------
# NEGATIVES
# ---------------------------------------------------------------------------
def test_exactly_half_passes_and_51_percent_is_not_cheap():
    e = U().peers(6).add("HALF", ps=5.0).add("OVER", ps=5.1).build()
    assert _passed(e) == ["HALF"]
    assert _row(e, "HALF")["ratio"] == 0.5
    assert e["counts"]["not_cheap"] >= 1


def test_a_name_is_never_part_of_its_own_median():
    u = U()
    for i, ps in enumerate((1.0, 1.0, 1.0, 10.0, 10.0, 10.0)):
        u.add(f"S{i}", ps=ps, q=5.0)
    u.add("SELF", ps=2.5)
    r = _row(u.build(), "SELF")        # with self the median would be 2.5 -> ratio 1.0
    assert r["peer_n"] == 6 and r["peer_ps_median"] == 5.5


@pytest.mark.parametrize("ttm", [0.0, -4e8])
def test_nonpositive_revenue_is_read_but_never_a_peer_nor_a_pass(ttm):
    u = U().peers(5).add("ZERO", ps=1.0, ttm=ttm, prior=1e8, q=500.0, cap=1e9)
    u.add("CHEAP", ps=2.0)
    e = u.build()
    assert e["counts"]["nonpositive_revenue"] == 1
    assert "ZERO" not in _passed(e)
    assert _row(e, "CHEAP")["peer_n"] == 5


def test_revenue_floor_is_inclusive_at_100m():
    e = U().peers(6).add("SMALL", ps=2.0, ttm=99.9e6).add("EDGE", ps=2.0, ttm=100e6).build()
    assert _passed(e) == ["EDGE"]
    assert e["counts"]["under_revenue_floor"] == 1


def test_quarter_growth_199_is_short_and_20_passes():
    e = U().peers(6).add("Q199", ps=2.0, q=19.9).add("Q200", ps=2.0, q=20.0).build()
    assert _passed(e) == ["Q200"]
    assert e["counts"]["q_growth_short"] == 1


def test_trailing_year_199_is_short():
    e = U().peers(6).add("T199", ps=2.0, prior=1e9 / 1.199).add(
        "T200", ps=2.0, prior=1e9 / 1.2).build()
    assert _passed(e) == ["T200"]
    assert e["counts"]["ttm_growth_short"] == 1


def test_four_industry_peers_fall_back_to_the_sector_and_a_thin_sector_has_no_group():
    u = U().peers(6, industry="Other")
    for i in range(4):
        u.add(f"I{i}", ps=10.0, q=5.0, industry="Four")
    u.add("FALL", ps=2.0, industry="Four")
    for i in range(3):
        u.add(f"H{i}", ps=10.0, q=5.0, sector="Health", industry="Bio")
    u.add("THIN", ps=2.0, sector="Health", industry="Bio")
    e = u.build()
    assert _row(e, "FALL")["group_kind"] == "sector"
    assert "THIN" not in _passed(e)
    assert e["counts"]["no_peer_group"] >= 1


def test_not_read_rows_are_counted_and_named_in_the_header():
    u = U().peers(6)
    u.add("NOCAP", ps=2.0, cap=0.0)
    u.add("NANCAP", ps=2.0, cap=float("nan"))
    u.add("FLOAT", ps=2.0, cap_source="derived_float")
    u.add("ADR", ps=0.01, source="yfinance")
    u.add("NOSNAP", snap=False)
    u.add("NOSEC", sector=None)
    u.add("HOLE0", rev=[2.5e8, None, 2.5e8, 2.5e8, 2e8, 2e8, 2e8, 2e8])
    u.add("NANREV", rev=[2.5e8, float("nan"), 2.5e8, 2.5e8, 2e8, 2e8, 2e8, 2e8])
    e = u.build()
    c = e["counts"]
    assert c["no_cap"] == 2 and c["cap_lower_bound"] == 1
    assert c["currency_unverified"] == 1 and c["no_fundamentals"] == 1
    assert c["no_sector"] == 1 and c["no_ttm_revenue"] == 2
    assert _passed(e) == []
    h = UVP.header(c)
    assert "2 no market cap" in h and "1 cap only a float lower bound" in h
    assert "1 revenue currency unverified" in h and "1 no sector" in h
    buckets = ("no_sector", "no_fundamentals", "currency_unverified", "no_ttm_revenue",
               "nonpositive_revenue", "no_cap", "cap_lower_bound", "usable")
    assert sum(c[k] for k in buckets) == c["scanned"]
    fell = ("no_peer_group", "not_cheap", "under_revenue_floor", "q_growth_not_read",
            "q_growth_short", "ttm_growth_not_read", "ttm_growth_short", "passed")
    assert sum(c[k] for k in fell) == c["usable"]


def test_trailing_year_not_read_on_a_hole_or_a_nonpositive_prior_year():
    u = U().peers(6)
    u.add("HOLE", ps=2.0, rev=[2.5e8] * 4 + [2e8, None, 2e8, 2e8])
    # prior year sums to 0 while its slot-4 quarter is positive (the Q leg reads)
    u.add("PRIOR0", ps=2.0, rev=[2.5e8] * 4 + [1e8, -1e8, 0.0, 0.0])
    # Massive omitted a quarter inside the prior year: 8 slots, 9 quarters apart
    u.add("GAP", ps=2.0, periods=[8105, 8104, 8103, 8102, 8101, 8100, 8099, 8097])
    e = u.build()
    assert e["counts"]["ttm_growth_not_read"] == 3
    assert _passed(e) == []


def test_headline_pair_not_four_quarters_apart_is_not_read():
    e = U().peers(6).add("SKEW", ps=2.0,
                         periods=[8105, 8104, 8103, 8102, 8100, 8099, 8098, 8097]).build()
    assert e["counts"]["q_growth_not_read"] == 1 and _passed(e) == []
    snap = {"sales": {"growth_yoy_pct": 40.0}, "q_period_series": PERIODS8,
            "rev_q_series": [1, 1, 1, 1, 0.0, 1, 1, 1]}
    assert UVP.q_yoy_pct(snap) is None, "year-ago quarter <= 0 -> not read"
    assert UVP.q_yoy_pct({"sales": {"growth_yoy_pct": float("nan")}}) is None


def test_cpa_not_read_and_ev_not_below_peers_and_thin_ev_peers():
    u = U().peers(6).add("NOBM", ps=2.0).add("RICHEV", ps=1.5).add("THINEV", ps=1.0)
    bm = {f"P{i}SE": _bm(ev=4.0) for i in range(6)}
    bm["RICHEV"] = _bm(ev=6.0, cash=1e8, debt=9e8, fcf=-4.2, dil=7.5, roce=-3.0)
    bm["THINEV"] = _bm(ev=2.0)
    e = UVP.enrich(u.build(), bm, {})
    assert e["counts"]["cpa_not_read"] == 1 and e["counts"]["ev_compared"] == 2
    nobm = UVP.tile_parts(_row(e, "NOBM"))
    sv = {s["k"]: s["v"] for s in nobm["stats"]}
    assert sv["CPA"] == "not read" and sv["EV/Sales"] == "not read"
    assert sv["Next ER"] == "not on file"
    assert [s["k"] for s in nobm["stats"]][-1] == "CPA"
    assert not any(b["text"][:2] in ("🏦", "🔥", "🩸", "📉") for b in nobm["badges"])
    rich = UVP.tile_parts(_row(e, "RICHEV"))
    texts = [b["text"] for b in rich["badges"]]
    assert "⚠️ EV/Sales 6.0x is not below peers' 4.0x" in texts
    assert "🏦 Net debt — cash $100M vs debt $900M" in texts
    assert "🔥 Burning cash — FCF yield -4.2%" in texts
    assert "🩸 Diluting — shares +7.5% YoY" in texts
    assert "📉 Negative ROCE -3.0%" in texts
    # EV peers under MIN_PEERS
    bm2 = {f"P{i}SE": _bm(ev=4.0) for i in range(3)}
    bm2["THINEV"] = _bm(ev=2.0)
    e2 = UVP.enrich(u.build(), bm2, {})
    tv = {s["k"]: s["v"] for s in UVP.tile_parts(_row(e2, "THINEV"))["stats"]}
    assert tv["EV/Sales"] == "2.0x · peers not read (3 of 8)"


def test_non_operating_sector_reads_ev_na_and_wears_the_scale_chip():
    u = U().peers(6, sector="Financial Services", industry="Banks").add(
        "BANK", ps=2.0, sector="Financial Services", industry="Banks")
    e = UVP.enrich(u.build(), {"BANK": _bm(ev=1.0, meaningful=False)}, {})
    parts = UVP.tile_parts(_row(e, "BANK"))
    assert {s["k"]: s["v"] for s in parts["stats"]}["EV/Sales"] == "n/a · Financial Services"
    assert any(b["text"] == "⚖️ Financial Services: sales multiples read differently here"
               for b in parts["badges"])


def test_nan_never_reaches_json(prices, monkeypatch):
    u = U().peers(6).add("CHEAP", ps=2.0)
    u.add("NANQ", ps=2.0, q=float("nan"))
    u.snaps["P0SE"]["rev_q_series"][6] = float("inf")
    u.install(monkeypatch, bm={"CHEAP": _bm(ev=float("nan"), fcf=float("nan"))})
    prices["CHEAP"] = _frame()
    out = B.board("undervalue", limit=5, min_tier="any", uv="peers")
    json.dumps(out, allow_nan=False, default=str)
    assert out["undervalue_view"]["counts"]["q_growth_not_read"] == 1


def test_read_never_raises(monkeypatch):
    def _boom():
        raise RuntimeError("mongo down")
    monkeypatch.setattr(UVP, "_load_inputs", _boom)
    e = UVP.read()
    assert e["passed"] == [] and e["error"] == "RuntimeError"
    assert set(e["counts"]) == set(UVP.COUNT_KEYS)


def test_parse_view_only_peers_switches():
    from fastapi import Query
    for v in (None, "", "bogus", "PSG", "psg", Query(""), 1):
        assert UVP.parse_view(v) == "psg"
    assert UVP.parse_view(" Peers ") == "peers"
    assert UVP.parse_view("peers") == "peers"


@pytest.mark.parametrize("uv", [None, "", "bogus", "psg"])
def test_the_default_view_calls_the_old_builder_with_the_old_args(monkeypatch, uv):
    seen = []
    base = {"tiles": [], "note": "N", "matched": 0, "screened": 0,
            "phase": "all", "generated_at": None}

    def spy(*a, **kw):
        seen.append((a, kw))
        return dict(base)

    def never(*a, **kw):
        raise AssertionError("the peers builder must not run on the default view")

    monkeypatch.setattr(B, "undervalue_tiles", spy)
    monkeypatch.setattr(B, "undervalue_peer_tiles", never)
    out = B.board("undervalue", limit=7, min_tier="any", uv=uv)
    assert seen == [((7, B.BARS_DEFAULT, B.THEMES_FIRST_DEFAULT, B.DEFAULT_SORT, "any"),
                     {"phase": "all"})]
    blk = out.pop("undervalue_view")
    assert blk["view"] == "psg" and blk["header"] is None
    ref = B.board("undervalue", limit=7, min_tier="any")
    ref.pop("undervalue_view")
    assert set(out) == set(ref)
    assert set(out) - set(base) == set(ref) - set(base)


def test_other_tabs_carry_no_undervalue_view(monkeypatch):
    monkeypatch.setattr(B, "vcp_tiles", lambda *a, **kw: {"tiles": [], "note": ""})
    out = B.board("vcp", uv="peers")
    assert "undervalue_view" not in out


def test_the_api_coerces_query_defaults(monkeypatch):
    import asyncio
    from chart_maps import api
    got = {}

    def fake_board(**kw):
        got.update(kw)
        return {"tiles": []}

    monkeypatch.setattr(api.board_mod, "board", fake_board)
    asyncio.run(api.chart_maps(tab="undervalue"))
    assert got["uv"] is None and got["tab"] == "undervalue"
    got.clear()
    asyncio.run(api.chart_maps(tab="undervalue", uv="peers"))
    assert got["uv"] == "peers"


def test_no_badge_jumps_a_card_ladder_rung():
    u = U().peers(6).add("RICHEV", ps=2.0, industry="Semis")
    u.add("FALL", ps=2.0, sector="Financial Services", industry="Tiny")
    for i in range(5):
        u.add(f"F{i}", ps=10.0, q=5.0, sector="Financial Services", industry=f"X{i}")
    bm = {f"P{i}SE": _bm(ev=4.0) for i in range(6)}
    bm["RICHEV"] = _bm(ev=6.0, cash=1e8, debt=9e8, fcf=-4.2, dil=7.5, roce=-3.0)
    e = UVP.enrich(u.build(), bm, {})
    assert len(e["passed"]) == 2
    for r in e["passed"]:
        for b in UVP.tile_parts(r)["badges"]:
            assert not b["text"].startswith(LADDER_PREFIXES), b["text"]


def test_source_guard():
    src = inspect.getsource(UVP)
    assert UVP.MEASURED is False
    assert UVP.PEER_PS_MAX_FRACTION == 0.50 and UVP.MIN_PEERS == 5
    assert UVP.MIN_SALES_YOY_Q_PCT == 20.0 and UVP.MIN_SALES_TTM_GROWTH_PCT == 20.0
    assert UVP.MIN_TTM_REVENUE_USD == 100_000_000.0
    low = src.lower()
    assert "bounce" not in low and "fake" not in low
    assert "= 4" not in src and "Financial Services" not in src and "derived_float" not in src
    from sepa.board_metrics import NON_OPERATING_SECTORS, QUARTERS_FOR_TTM
    from sepa.cap_warm import DERIVED_FLOAT
    assert UVP.QUARTERS_FOR_TTM is QUARTERS_FOR_TTM
    assert UVP.NON_OPERATING_SECTORS is NON_OPERATING_SECTORS
    assert UVP.DERIVED_FLOAT is DERIVED_FLOAT
    from growth.capital_quality import _median
    assert UVP._median is _median
    assert "never compared across companies" in UVP.NOTE and "UNMEASURED" in UVP.NOTE
    assert UVP.MARK == "\U0001F3F7️"


# ---------------------------------------------------------------------------
# Round 2 (2026-09-29): close date, failed reads, hidden-by-filter, shares
# wording, peers under the revenue floor
# ---------------------------------------------------------------------------
from datetime import datetime as _dt  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

_ET = ZoneInfo("America/New_York")


def _epoch(y, mo, d, h, mi):
    return _dt(y, mo, d, h, mi, tzinfo=_ET).timestamp()


def _cap_stat(entry, sym):
    return {s["k"]: s["v"] for s in UVP.tile_parts(_row(entry, sym))["stats"]}["Mkt cap"]


@pytest.mark.parametrize("mtime, gen_at, want", [
    # the live case: scan generated Tue 23:27 ET, the file rewritten 00:01 Wed
    (_epoch(2026, 9, 30, 0, 1), _epoch(2026, 9, 29, 23, 27), "2026-09-29"),
    # a weekend rewrite of Friday's scan
    (_epoch(2026, 10, 3, 10, 0), _epoch(2026, 10, 2, 16, 40), "2026-10-02"),
])
def test_the_close_is_dated_by_the_scans_generated_at_never_the_file_mtime(mtime, gen_at, want):
    u = U().peers(6).add("CHEAP", ps=2.0)
    e = UVP.build(u.rows, u.snaps, u.caps, u.meta, generation=mtime,
                  scan_generated_at=gen_at)
    assert e["scanned_at_date"] == want
    v = _cap_stat(e, "CHEAP")
    assert v.endswith(f"× close {want}")
    assert _dt.fromtimestamp(mtime, _ET).date().isoformat() not in v.split("× close")[1]


def test_read_dates_the_close_from_generated_at_and_keys_the_memo_on_mtime(monkeypatch):
    u = U().peers(6).add("CHEAP", ps=2.0)
    mtime, gen_at = _epoch(2026, 9, 30, 0, 1), _epoch(2026, 9, 29, 23, 27)
    from chart_maps import dual_momentum_tab
    monkeypatch.setattr(dual_momentum_tab, "scan_generation", lambda: int(mtime))
    monkeypatch.setattr(UVP, "_load_inputs", lambda: {
        "rows": u.rows, "snaps": u.snaps, "caps": u.caps, "cap_meta": u.meta,
        "generation": int(mtime), "scan_generated_at": gen_at})
    monkeypatch.setattr(UVP, "_load_enrichment", lambda p, q: ({}, {}))
    e = UVP.read()
    assert _cap_stat(e, "CHEAP").endswith("× close 2026-09-29")
    assert UVP._memo["key"][0] == int(mtime)


def test_a_scan_without_generated_at_is_undated_never_the_mtime():
    u = U().peers(6).add("CHEAP", ps=2.0)
    e = UVP.build(u.rows, u.snaps, u.caps, u.meta, generation=_epoch(2026, 9, 30, 0, 1))
    assert e["scanned_at_date"] is None
    assert _cap_stat(e, "CHEAP").endswith("× close undated")


def test_the_shares_date_is_labelled_as_the_fetch_date():
    e = U().peers(6).add("CHEAP", ps=2.0).build()
    v = _cap_stat(e, "CHEAP")
    fetched = _dt.fromtimestamp(GEN - 86400 * 10, _ET).date().isoformat()
    assert v == f"$2.0B · shares fetched {fetched} × close 2026-09-21"
    assert f"shares {fetched}" not in v, "the fetch date must never read as a share-count period"


def _fail_inputs(monkeypatch, calls, **over):
    u = U().peers(6).add("CHEAP", ps=2.0)
    base = {"rows": u.rows, "snaps": u.snaps, "caps": u.caps, "cap_meta": u.meta,
            "generation": GEN, "scan_generated_at": GEN}
    base.update(over)

    def _inputs():
        calls.append(1)
        return dict(base)
    monkeypatch.setattr(UVP, "_load_inputs", _inputs)
    monkeypatch.setattr(UVP, "_load_enrichment", lambda p, q: ({}, {}))


@pytest.mark.parametrize("over, err, why", [
    ({"rows": []}, "no_scan", "no scan rows on disk"),
    ({"snaps": {}}, "no_fundamentals", "no fundamentals came back"),
    ({"caps": {}}, "no_usable", "had a readable P/S"),
])
def test_an_outage_reads_as_a_failed_read_and_is_never_cached(prices, monkeypatch,
                                                                 over, err, why):
    calls: list = []
    _fail_inputs(monkeypatch, calls, **over)
    e = UVP.read()
    assert e["error"] == err and e["passed"] == []
    UVP.read()
    assert len(calls) == 2, "a failed build must never be memoised"
    assert UVP._memo == {}
    out = B.board("undervalue", limit=5, min_tier="any", uv="peers")
    assert out["tiles"] == []
    assert out["note"] != UVP.EMPTY_NOTE and "No name passes" not in out["note"]
    assert "read failed" in out["note"] and why in out["note"]
    blk = out["undervalue_view"]
    assert blk["error"] == err
    assert blk["header"].startswith(UVP.MARK + " The vs-peers read failed")
    assert why in blk["header"] and "does NOT mean no name is cheap" in blk["header"]
    json.dumps(out, allow_nan=False, default=str)


def test_mongo_down_raising_reads_as_a_failed_read(prices, monkeypatch):
    class ServerSelectionTimeoutError(Exception):
        pass

    def _down():
        raise ServerSelectionTimeoutError("mongo:27017 timed out")
    monkeypatch.setattr(UVP, "_load_inputs", _down)
    out = B.board("undervalue", limit=5, min_tier="any", uv="peers")
    assert UVP._memo == {}
    assert out["note"] != UVP.EMPTY_NOTE
    assert "ServerSelectionTimeoutError while reading the inputs" in out["note"]
    assert out["undervalue_view"]["error"] == "ServerSelectionTimeoutError"
    assert "read failed" in out["undervalue_view"]["header"]


def test_NEG_a_failed_shares_meta_read_fails_the_build_never_lets_lower_bound_caps_pass(
        prices, monkeypatch):
    import types
    import sepa
    u = U().peers(6).add("CHEAP", ps=2.0)

    class _Coll:
        def find(self, *a, **k):
            raise RuntimeError("shares collection unreachable")
    stubs = {
        "sepa.scanner": types.SimpleNamespace(
            load_latest=lambda: {"all_results": u.rows, "generated_at": GEN}),
        "sepa.research": types.SimpleNamespace(decision_snapshot=lambda syms: u.snaps),
        "sepa.volume_movers": types.SimpleNamespace(_shares_coll=lambda: _Coll()),
        "catalysts.promo_circuit": types.SimpleNamespace(
            market_caps_for=lambda s, c, cap=0: u.caps),
    }
    for name, mod in stubs.items():
        monkeypatch.setitem(sys.modules, name, mod)
        if name.startswith("sepa."):
            monkeypatch.setattr(sepa, name.split(".", 1)[1], mod, raising=False)
    monkeypatch.setattr(UVP, "_generation", lambda: GEN)
    with pytest.raises(RuntimeError):
        UVP._load_inputs()
    e = UVP.read()
    assert e["error"] == "RuntimeError" and e["passed"] == []
    assert UVP._memo == {}


def test_a_real_zero_pass_answer_keeps_the_empty_note_and_is_cached(prices, monkeypatch):
    calls: list = []
    U().peers(6).add("DEAR", ps=9.0).install(monkeypatch, calls=calls)
    out = B.board("undervalue", limit=5, min_tier="any", uv="peers")
    assert out["tiles"] == [] and out["note"] == UVP.EMPTY_NOTE
    assert out["undervalue_view"]["error"] is None
    assert "read failed" not in out["undervalue_view"]["header"]
    UVP.read()
    assert len(calls) == 1


def test_build_failure_is_none_for_real_answers():
    assert UVP.build_failure(U().peers(6).add("DEAR", ps=9.0).build()["counts"]) is None
    nosec = U()
    for i in range(3):
        nosec.add(f"N{i}", sector=None)
    assert UVP.build_failure(nosec.build()["counts"]) == "no_sector"
    assert UVP.build_failure({}) == "no_scan"


def test_names_hidden_by_the_phase_filter_are_named_not_empty(prices, monkeypatch):
    U().peers(6).add("AAA", ps=2.0).add("BBB", ps=2.5).install(monkeypatch)
    for s in ("AAA", "BBB"):
        prices[s] = _frame()
    monkeypatch.setattr(B, "_uv_band_state", lambda z, df, last: ("away", None))
    out = B.undervalue_peer_tiles(limit=5, min_tier="any", phase="reached")
    assert out["tiles"] == []
    assert out["note"] != UVP.EMPTY_NOTE
    assert out["note"].startswith(UVP.MARK + " 2 passed all four legs, but none is on the board")
    assert "2 hidden by the phase filter (in the demand band only)" in out["note"]


def test_names_under_the_liquidity_floor_are_named_not_empty(prices, monkeypatch):
    u = U().peers(6).add("THIN", ps=2.0)
    u.rows[-1]["liquidity"] = {"avg_dollar_vol": 1.0}
    u.install(monkeypatch)
    prices["THIN"] = _frame()
    out = B.undervalue_peer_tiles(limit=5, min_tier="ok")
    assert out["tiles"] == [] and out["note"] != UVP.EMPTY_NOTE
    assert "1 under the liquidity floor (ok)" in out["note"]


def test_passes_with_no_price_history_are_named_not_empty(prices, monkeypatch):
    U().peers(6).add("NOPX", ps=2.0).install(monkeypatch)
    out = B.undervalue_peer_tiles(limit=5, min_tier="any")
    assert out["tiles"] == [] and out["note"] != UVP.EMPTY_NOTE
    assert "1 with no price history on file" in out["note"]


def test_a_sub_floor_peer_at_80x_does_not_lift_the_median():
    u = U()
    for i, ps in enumerate((2.0, 4.0, 6.0, 8.0, 10.0)):
        u.add(f"B{i}", ps=ps, q=5.0)
    u.add("TINY", ps=80.0, ttm=20e6, q=5.0)
    u.add("CHEAP", ps=1.0)
    e = u.build()
    r = _row(e, "CHEAP")
    assert r["peer_ps_median"] == 6.0, "with TINY in the pool it would be 7.0"
    assert r["peer_n"] == 5 and r["group_kind"] == "industry"
    assert e["counts"]["usable"] == 7, "TINY is still read, just never a peer"


def test_a_sub_floor_crowd_cannot_make_a_name_look_cheap():
    u = U()
    for i in range(5):
        u.add(f"B{i}", ps=6.0, q=5.0)
    for i in range(5):
        u.add(f"S{i}", ps=80.0, ttm=20e6, q=5.0)
    u.add("MID", ps=4.0)                 # 0.67 of 6.0; with the small crowd 0.09 of 43
    e = u.build()
    assert "MID" not in _passed(e)
    assert e["counts"]["not_cheap"] >= 1


def test_four_floor_passing_industry_peers_fall_back_to_the_sector():
    u = U().peers(6, industry="Other")
    for i in range(4):
        u.add(f"I{i}", ps=10.0, q=5.0, industry="Four")
    for i in range(3):
        u.add(f"J{i}", ps=10.0, q=5.0, ttm=20e6, industry="Four")   # 7 usable, 4 floor-passing
    u.add("FALL", ps=2.0, industry="Four")
    e = u.build()
    r = _row(e, "FALL")
    assert r["group_kind"] == "sector" and r["peer_n"] == 10
    assert e["counts"]["sector_fallback"] == 1


def test_the_note_says_peers_clear_the_revenue_floor():
    assert "peers count only when they too have at least $100M of revenue" in UVP.NOTE
    assert "dated by when it was fetched" in UVP.NOTE
