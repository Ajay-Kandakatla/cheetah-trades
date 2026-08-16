"""Chart Maps board — tile assembly, honesty rules and the theme universe.

Everything here runs on SYNTHETIC data with the price loader and the Mongo
collection stubbed, so the suite is deterministic and needs no network, no
scan on disk and no database.

The negatives carry the weight: a scan with no VCP rows, a symbol whose price
frame is missing, a confirmation date that is not a trading day, a demand board
still warming, and the ledger observations that were already past target when
recorded. Each of those is a real payload this code will see.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chart_maps import board as B  # noqa: E402


# ---------------------------------------------------------------------------
# synthetic price frames
# ---------------------------------------------------------------------------
def _frame(n=200, start=10.0, step=0.05, start_date="2026-01-01"):
    idx = pd.bdate_range(start_date, periods=n)
    close = [start + i * step for i in range(n)]
    return pd.DataFrame({
        "open": [c - 0.05 for c in close],
        "high": [c + 0.20 for c in close],
        "low": [c - 0.20 for c in close],
        "close": close,
        "volume": [1_000_000] * n,
    }, index=idx)


@pytest.fixture
def prices(monkeypatch):
    """Stub sepa.prices.load_prices with a synthetic frame per symbol."""
    store: dict = {}

    class _Prices:
        @staticmethod
        def load_prices(symbol, *a, **kw):
            return store.get(symbol.upper())

    mod = _Prices()
    monkeypatch.setitem(sys.modules, "sepa.prices", mod)

    import sepa
    monkeypatch.setattr(sepa, "prices", mod, raising=False)
    return store


# ---------------------------------------------------------------------------
# bars_for
# ---------------------------------------------------------------------------
def test_bars_for_returns_the_trailing_window(prices):
    prices["AAA"] = _frame(200)
    bars = B.bars_for("AAA", days=60)
    assert len(bars) == 60
    assert set(bars[0]) == {"t", "o", "h", "l", "c", "v"}
    # oldest first, so a chart reads left to right
    assert bars[0]["t"] < bars[-1]["t"]


def test_bars_for_centres_on_a_dated_event(prices):
    df = _frame(200)
    prices["AAA"] = df
    mid = df.index[120].strftime("%Y-%m-%d")
    bars = B.bars_for("AAA", days=40, around=mid, pad_after=10)
    dates = [b["t"] for b in bars]
    assert mid in dates
    # the event is NOT the last bar — the outcome has to be visible
    assert dates.index(mid) < len(dates) - 1
    assert len(dates) - dates.index(mid) - 1 == 10


def test_bars_for_falls_back_to_the_tail_on_a_non_trading_date(prices):
    """A ledger date can land on a holiday or a halted session. Degrading to a
    usable chart beats returning a blank tile."""
    prices["AAA"] = _frame(200)
    bars = B.bars_for("AAA", days=30, around="1999-12-31")
    assert len(bars) == 30


def test_bars_for_is_empty_for_an_unknown_symbol(prices):
    assert B.bars_for("NOPE") == []


def test_bars_for_rejects_a_frame_without_ohlc(prices):
    prices["BAD"] = pd.DataFrame({"close": [1, 2, 3]},
                                 index=pd.bdate_range("2026-01-01", periods=3))
    assert B.bars_for("BAD") == []


def test_bars_for_clamps_an_absurd_day_count(prices):
    prices["AAA"] = _frame(600)
    assert len(B.bars_for("AAA", days=99_999)) <= B.BARS_MAX
    assert len(B.bars_for("AAA", days=1)) >= 20


# ---------------------------------------------------------------------------
# the strong-VCP predicate
# ---------------------------------------------------------------------------
def _vcp_row(symbol="AAA", tightness=80, setup="VCP"):
    return {
        "symbol": symbol,
        "entry_setup": {"type": setup, "pivot": 20.0, "stop": 18.5},
        "vcp": {"tightness": tightness, "tightness_band": "tight",
                "base_high": 19.0, "base_low": 15.0, "base_bars": 61,
                "n_contractions": 3, "final_contraction_pct": 4.0,
                "pivot_buy_price": 20.0, "suggested_stop": 18.5,
                "tightness_drivers": ["tightens 28%->4%"]},
        "is_candidate": True, "is_buyable": False, "setup_ready": True,
        "rs_rank": 91,
    }


def test_strong_vcp_needs_both_the_setup_name_and_the_tightness():
    assert B._is_strong_vcp(_vcp_row()) is True
    # named VCP but the base has not converged
    assert B._is_strong_vcp(_vcp_row(tightness=45)) is False
    # tight, but the scanner called this chart something else
    assert B._is_strong_vcp(_vcp_row(setup="BREAKOUT")) is False


def test_strong_vcp_survives_the_null_shapes_the_scan_really_emits():
    # vcp is null when detect() bailed on too few bars
    assert B._is_strong_vcp({"symbol": "A", "entry_setup": {"type": "VCP"}, "vcp": None}) is False
    # tightness is null when there are fewer than 2 contractions
    assert B._is_strong_vcp({"symbol": "A", "entry_setup": {"type": "VCP"},
                             "vcp": {"tightness": None}}) is False
    # entry_setup itself is null on most rows
    assert B._is_strong_vcp({"symbol": "A", "entry_setup": None, "vcp": {"tightness": 90}}) is False
    assert B._is_strong_vcp({}) is False


# ---------------------------------------------------------------------------
# the VCP tab
# ---------------------------------------------------------------------------
@pytest.fixture
def scan_stub(monkeypatch):
    payload: dict = {"all_results": [], "generated_at": "2026-08-15T21:00:00Z"}

    class _Scanner:
        @staticmethod
        def load_latest():
            return payload["_none"] if "_none" in payload else payload

    monkeypatch.setitem(sys.modules, "sepa.scanner", _Scanner())
    import sepa
    monkeypatch.setattr(sepa, "scanner", _Scanner(), raising=False)
    return payload


def test_vcp_tab_builds_tiles_with_base_band_and_plan_lines(prices, scan_stub):
    prices["AAA"] = _frame(200)
    scan_stub["all_results"] = [_vcp_row("AAA")]

    out = B.board("vcp", limit=5)
    assert out["tab"] == "vcp"
    assert out["count"] == 1
    t = out["tiles"][0]
    assert t["symbol"] == "AAA"
    assert t["href"] == "/sepa/AAA?tab=setup"
    assert t["bars"], "a tile must carry its price series"
    assert [b["kind"] for b in t["bands"]] == ["base"]
    assert {l["label"] for l in t["lines"]} == {"PIVOT", "STOP"}
    assert out["disclaimer"]


def test_vcp_tab_drops_a_symbol_whose_price_frame_is_missing(prices, scan_stub):
    scan_stub["all_results"] = [_vcp_row("GHOST")]
    out = B.board("vcp", limit=5)
    assert out["count"] == 0


def test_vcp_tab_is_empty_when_nothing_qualifies(prices, scan_stub):
    prices["AAA"] = _frame(200)
    scan_stub["all_results"] = [_vcp_row("AAA", tightness=20)]
    out = B.board("vcp", limit=5)
    assert out["count"] == 0
    assert out["matched"] == 0
    assert out["scanned"] == 1


def test_vcp_tab_says_so_when_no_scan_exists(monkeypatch):
    class _Scanner:
        @staticmethod
        def load_latest():
            return None

    # Both sys.modules AND the package attribute: `from sepa import scanner`
    # resolves via the attribute once the real module has been imported by an
    # earlier test, so patching only sys.modules passes alone and fails in the
    # full suite.
    stub = _Scanner()
    monkeypatch.setitem(sys.modules, "sepa.scanner", stub)
    import sepa
    monkeypatch.setattr(sepa, "scanner", stub, raising=False)

    out = B.board("vcp")
    assert out["count"] == 0
    assert "scan" in (out.get("note") or "").lower()


def test_vcp_badges_never_call_a_qualifier_buyable():
    """`is_candidate` is the WATCHLIST tier (trend + liquidity, p.79), not a
    buy. Conflating them is the exact mislabel the 2026-05-28 alignment fixed."""
    qualifier = {"is_candidate": True, "is_buyable": False, "setup_ready": False}
    texts = [b["text"] for b in B._vcp_badges(qualifier)]
    assert "Qualifier" in texts
    assert "Buyable" not in texts

    buyable = {"is_candidate": True, "is_buyable": True, "setup_ready": True}
    assert "Buyable" in [b["text"] for b in B._vcp_badges(buyable)]


def test_themes_lead_when_asked_and_not_when_not(prices, scan_stub, monkeypatch):
    for s in ("AAA", "IONQ"):
        prices[s] = _frame(200)
    # AAA scores higher, IONQ carries a theme
    scan_stub["all_results"] = [_vcp_row("AAA", tightness=95), _vcp_row("IONQ", tightness=71)]

    lead = B.board("vcp", limit=5, themes_first=True)["tiles"][0]["symbol"]
    assert lead == "IONQ"

    lead_metric = B.board("vcp", limit=5, themes_first=False)["tiles"][0]["symbol"]
    assert lead_metric == "AAA"


# ---------------------------------------------------------------------------
# the zones tab
# ---------------------------------------------------------------------------
def _reentry_row(symbol="AAA", rr=2.5):
    return {
        "symbol": symbol, "is_reentry": True,
        "entry_zone": {"lo": 14.0, "hi": 15.0},
        "supply_zones": [{"lo": 22.0, "hi": 23.0}],
        "plan": {"entry_ref": 14.6, "stop": 13.8, "target": 21.0, "rr": rr},
        "breakeven_win_pct": 28.6,
        "liquidity": {"tier": "deep"},
        "bars_since_above": 4, "fell_from_pct": 18.0,
        "verdict": {"state": "watch", "entry_read": "back inside the band"},
        "venues": {"rating": "A"}, "sweep": {"state": "swept"},
    }


@pytest.fixture
def reentry_stub(monkeypatch):
    payload: dict = {"rows": [], "warming": False, "universe_key": "sp1500_plus",
                     "universe_label": "S&P 1500 + themes", "scanned": 1501}

    class _D:
        @staticmethod
        def cached_or_warm(universe, limit=None):
            return payload

    monkeypatch.setitem(sys.modules, "supply_demand.demand_reentry", _D())
    import supply_demand
    monkeypatch.setattr(supply_demand, "demand_reentry", _D(), raising=False)
    return payload


def test_zones_tab_draws_the_band_and_the_whole_plan(prices, reentry_stub):
    prices["AAA"] = _frame(200)
    reentry_stub["rows"] = [_reentry_row("AAA")]

    out = B.board("zones", limit=5)
    t = out["tiles"][0]
    assert t["href"] == "/sepa/AAA?tab=supply"
    assert {b["kind"] for b in t["bands"]} == {"demand", "supply"}
    assert [l["label"] for l in t["lines"]] == ["BUY", "STOP", "TARGET"]
    assert {s["k"] for s in t["stats"]} >= {"R:R", "Break-even", "Liquidity"}


def test_zones_tab_returns_warming_instead_of_blocking(prices, reentry_stub):
    """A cold 1,500-name pass outlives Cloudflare's ~100s cut. The board must
    answer immediately and let the page poll — the 2026-08-14 524."""
    reentry_stub["warming"] = True
    out = B.board("zones")
    assert out["warming"] is True
    assert out["count"] == 0


def test_zones_tab_excludes_rows_that_are_not_re_entries(prices, reentry_stub):
    prices["AAA"] = _frame(200)
    row = _reentry_row("AAA")
    row["is_reentry"] = False
    reentry_stub["rows"] = [row]
    assert B.board("zones")["count"] == 0


def test_zones_tab_tolerates_a_null_plan(prices, reentry_stub):
    prices["AAA"] = _frame(200)
    row = _reentry_row("AAA")
    row["plan"] = None
    row["breakeven_win_pct"] = None
    reentry_stub["rows"] = [row]
    out = B.board("zones")
    assert out["count"] == 1
    assert out["tiles"][0]["lines"] == []


# ---------------------------------------------------------------------------
# the winners tab
# ---------------------------------------------------------------------------
def _obs(symbol, outcome, pattern="cup_with_handle", obs_close=15.0,
         target=18.0, date="2026-06-15"):
    return {"kind": "pattern", "status": "confirmed", "outcome": outcome,
            "pattern": pattern, "symbol": symbol, "et_date": date,
            "confirmed_date": date, "obs_close": obs_close, "neckline": 15.5,
            "target": target, "stop": 13.5, "bars_to_outcome": 7,
            "max_gain_pct": 12.0, "rs_rank": 88}


class _Coll:
    def __init__(self, docs):
        self._docs = docs

    def find(self, q, proj=None):
        pat = q.get("pattern")
        want = set((q.get("outcome") or {}).get("$in") or [])
        return [d for d in self._docs
                if d.get("kind") == q.get("kind")
                and d.get("status") == q.get("status")
                and (not want or d.get("outcome") in want)
                and (pat is None or d.get("pattern") == pat)]


@pytest.fixture
def ledger(monkeypatch):
    docs: list = []

    class _History:
        @staticmethod
        def _coll():
            return _Coll(docs)

    monkeypatch.setitem(sys.modules, "patterns.history", _History())
    import patterns
    monkeypatch.setattr(patterns, "history", _History(), raising=False)
    return docs


def test_winners_tab_charts_the_confirmation_and_its_levels(prices, ledger):
    df = _frame(200)
    prices["AAA"] = df
    day = df.index[120].strftime("%Y-%m-%d")
    ledger.append(_obs("AAA", "target_first", date=day))

    out = B.board("winners", limit=5)
    t = out["tiles"][0]
    assert t["href"] == "/sepa/AAA?tab=breakout"
    assert t["markers"][0]["date"] == day
    assert {l["label"] for l in t["lines"]} == {"BREAKOUT", "TARGET", "STOP"}
    assert day in [b["t"] for b in t["bars"]]


def test_winners_tab_reports_the_losses_next_to_the_wins(prices, ledger):
    df = _frame(200)
    day = df.index[120].strftime("%Y-%m-%d")
    for i in range(3):
        prices[f"W{i}"] = df
        ledger.append(_obs(f"W{i}", "target_first", date=day))
    for i in range(2):
        prices[f"L{i}"] = df
        ledger.append(_obs(f"L{i}", "stop_first", date=day))

    out = B.board("winners", limit=10)
    rec = out["record"]["overall"]
    assert rec["wins"] == 3 and rec["losses"] == 2 and rec["n"] == 5
    assert rec["win_pct"] == 60.0
    # only the winners are charted
    assert out["count"] == 3


def test_winners_tab_excludes_observations_already_past_target(prices, ledger):
    """Recorded after the move had happened, so the chart teaches nothing about
    the entry. Measured 2026-08-15: 8 of 117 raced observations."""
    df = _frame(200)
    prices["LATE"] = df
    day = df.index[120].strftime("%Y-%m-%d")
    ledger.append(_obs("LATE", "target_first", obs_close=19.0, target=18.0, date=day))

    out = B.board("winners")
    assert out["count"] == 0
    assert out["excluded_already_past_target"] == 1
    assert out["record"]["overall"]["n"] == 0


def test_winners_record_never_ranks_patterns_against_each_other(prices, ledger):
    """Stop brackets differ ~2x between patterns, so a cross-pattern win-rate
    ranking is meaningless — the bug the 2026-07-10 audit found. The payload
    must carry the caveat and must not emit an ordering by win_pct."""
    df = _frame(200)
    day = df.index[120].strftime("%Y-%m-%d")
    prices["A"] = prices["B"] = df
    ledger.append(_obs("A", "target_first", pattern="double_bottom", date=day))
    ledger.append(_obs("B", "stop_first", pattern="cup_with_handle", date=day))

    rec = B.board("winners")["record"]
    assert "not" in rec["caveat"].lower() and "comparable" in rec["caveat"].lower()
    # ordered by sample size, NOT by win rate
    assert [r["n"] for r in rec["by_pattern"]] == sorted(
        [r["n"] for r in rec["by_pattern"]], reverse=True)


def test_winners_tab_can_filter_to_one_pattern(prices, ledger):
    df = _frame(200)
    day = df.index[120].strftime("%Y-%m-%d")
    prices["A"] = prices["B"] = df
    ledger.append(_obs("A", "target_first", pattern="double_bottom", date=day))
    ledger.append(_obs("B", "target_first", pattern="cup_with_handle", date=day))

    out = B.board("winners", pattern="double_bottom")
    assert [t["symbol"] for t in out["tiles"]] == ["A"]


def test_winners_tab_survives_an_unavailable_ledger(monkeypatch):
    class _History:
        @staticmethod
        def _coll():
            return None

    stub = _History()
    monkeypatch.setitem(sys.modules, "patterns.history", stub)
    import patterns
    monkeypatch.setattr(patterns, "history", stub, raising=False)

    out = B.board("winners")
    assert out["count"] == 0
    assert out.get("note")


# ---------------------------------------------------------------------------
# dispatch + coercion
# ---------------------------------------------------------------------------
def test_unknown_tab_falls_back_rather_than_erroring(prices, scan_stub):
    assert B.board("nonsense")["tab"] == "vcp"
    assert B.board(None)["tab"] == "vcp"


def test_limits_are_clamped(prices, scan_stub):
    scan_stub["all_results"] = []
    assert B.board("vcp", limit=10_000)["tab"] == "vcp"       # no exception
    assert B.board("vcp", limit=0)["tab"] == "vcp"


def test_num_rejects_nan_and_inf():
    assert B._num(float("nan")) is None
    assert B._num(float("inf")) is None
    assert B._num(None) is None
    assert B._num("abc") is None
    assert B._num("3.5") == 3.5


# ===========================================================================
# Strong-VCP gates — the Minervini criteria, each with its source
#
# Ajay 2026-08-16, seeing AVGO on the Strong VCP board: "our SEPA VCP has a
# problem.. We are not differentiating between Institution selling vs not
# selling.. Its not stage 2 now. Make sure it also has a base formed not
# institutions selling."
#
# He was right. The original filter asked two questions (is the setup named
# VCP, is the base tight) and AVGO passed both while failing nearly everything
# the book requires. Measured against the live scan: of 265 names passing the
# old filter, 209 failed the trend template, 23 were late-stage bases, 11 were
# not Stage 2, 5 were distributing — 17 actually qualified.
# ===========================================================================
def _qualified_row(**over):
    """A row that passes every gate. Tests override ONE field at a time so a
    failure names the gate that broke."""
    row = {
        "symbol": "GOOD",
        "entry_setup": {"type": "VCP", "pivot": 100.0, "stop": 94.0},
        "vcp": {"tightness": 85, "tightness_band": "tight",
                "base_high": 99.0, "base_low": 80.0, "base_bars": 45,
                "n_contractions": 3, "pivot_buy_price": 100.0,
                "suggested_stop": 94.0, "tightness_drivers": ["tightens 25%->4%"]},
        "is_candidate": True,
        "rs_rank": 92,
        "stage": {"stage": 2, "label": "Advancing"},
        "base_count": {"base_count": 2, "is_late_stage": False, "is_avoid_stage": False},
        "volume": {"up_down_vol_ratio": 1.6, "up_days_on_avg_vol": 14,
                   "dn_days_on_avg_vol": 7, "accumulation_strength": "accumulating"},
        "distribution": None,
    }
    row.update(over)
    return row


def test_a_fully_qualified_vcp_passes():
    assert B.strong_vcp_reject(_qualified_row()) is None
    assert B._is_strong_vcp(_qualified_row()) is True


def test_trend_template_is_the_first_gate():
    """"Stocks must first meet my Trend Template to be considered a potential
    SEPA candidate" — TLSW p.34."""
    r = _qualified_row(is_candidate=False)
    assert "trend template" in B.strong_vcp_reject(r)


def test_rs_below_70_is_rejected_and_named():
    """"The relative strength (RS) ranking ... is no less than 70, but
    preferably in the 90s" — TTLAC §6 (ebook p.106) crit. 7; TLSW p.79."""
    assert "RS 43" in B.strong_vcp_reject(_qualified_row(rs_rank=43))
    assert B.strong_vcp_reject(_qualified_row(rs_rank=70)) is None      # at the floor
    assert B.strong_vcp_reject(_qualified_row(rs_rank=69)) is not None


def test_only_stage_2_qualifies():
    """"Stage 2 - Advancing phase: accumulation / Stage 3 - Topping phase:
    distribution" — TLSW p.66, TTLAC §6 (ebook p.104). Institutions selling IS
    Stage 3 by definition."""
    for stage in (1, 3, 4):
        rej = B.strong_vcp_reject(_qualified_row(stage={"stage": stage}))
        assert rej and "not Stage 2" in rej


def test_late_stage_bases_are_rejected():
    """"By the time a fourth or fifth base occurs ... definitely in its late
    stages. By this point, abrupt base failures" — TLSW p.81."""
    r = _qualified_row(base_count={"base_count": 6, "is_late_stage": True,
                                   "is_avoid_stage": True})
    assert "late-stage base #6" in B.strong_vcp_reject(r)
    # a 2nd base is fine
    assert B.strong_vcp_reject(_qualified_row()) is None


def test_institutional_SELLING_is_rejected_even_when_the_label_says_neutral():
    """THE GAP AJAY POINTED AT. Stage 2 requires "more up days and up weeks on
    above-average volume than down days and down weeks" (TLSW p.71-72), but the
    coarse accumulation_strength label only says "distributing" at a ratio
    <= 0.70. AVGO's 0.91 reads "neutral" while failing the book's own test, so
    the ratio and the day counts are checked DIRECTLY."""
    r = _qualified_row(volume={"up_down_vol_ratio": 0.91,
                               "up_days_on_avg_vol": 10,
                               "dn_days_on_avg_vol": 11,
                               "accumulation_strength": "neutral"})
    rej = B.strong_vcp_reject(r)
    assert rej and "0.91" in rej and "distribution" in rej


def test_more_down_days_than_up_days_is_rejected():
    """Caught even when the volume RATIO scrapes over 1.0."""
    r = _qualified_row(volume={"up_down_vol_ratio": 1.05,
                               "up_days_on_avg_vol": 8,
                               "dn_days_on_avg_vol": 12,
                               "accumulation_strength": "neutral"})
    assert "more down days" in B.strong_vcp_reject(r)


def test_an_explicit_distribution_flag_is_rejected():
    assert B.strong_vcp_reject(_qualified_row(distribution={"days": 5})) is not None
    r = _qualified_row(volume={"up_down_vol_ratio": 1.5, "up_days_on_avg_vol": 12,
                               "dn_days_on_avg_vol": 6,
                               "accumulation_strength": "distributing"})
    assert "distributing" in B.strong_vcp_reject(r)


def test_a_loose_base_is_still_rejected():
    """The original two gates still apply — they were necessary, just not
    sufficient."""
    r = _qualified_row(vcp={"tightness": 40})
    assert "not tight enough" in B.strong_vcp_reject(r)
    assert B.strong_vcp_reject(_qualified_row(entry_setup={"type": "BREAKOUT"})) \
        == "no VCP setup"


def test_REGRESSION_the_exact_AVGO_row_is_rejected():
    """The row that put AVGO on the board on 2026-08-16, verbatim from the
    live scan. It passed the old filter on tightness 85 alone."""
    avgo = {
        "symbol": "AVGO",
        "entry_setup": {"type": "VCP", "pivot": 396.81, "stop": 370.32},
        "vcp": {"tightness": 85, "tightness_band": "tight",
                "base_high": 481.57, "base_low": 360.45, "base_bars": 50},
        "is_candidate": False, "is_buyable": False, "setup_ready": False,
        "rs_rank": 43,
        "stage": {"stage": 2, "label": "Advancing", "dist_200_pct": 6.44},
        "base_count": {"base_count": 6, "is_late_stage": True, "is_avoid_stage": True},
        "volume": {"up_down_vol_ratio": 0.91, "up_days_on_avg_vol": 10,
                   "dn_days_on_avg_vol": 11, "accumulation": False,
                   "accumulation_strength": "neutral", "vol_dryup": 0.69},
        "distribution": None,
    }
    assert B._is_strong_vcp(avgo) is False
    # and it must fail for a REASON, not by accident
    assert B.strong_vcp_reject(avgo)


def test_gates_survive_the_null_shapes_the_scan_really_emits():
    """A row missing stage/base_count/volume entirely must not crash — those
    blocks are absent on names the scanner could not fully analyse."""
    bare = {"symbol": "X", "entry_setup": {"type": "VCP"},
            "vcp": {"tightness": 90}, "is_candidate": True, "rs_rank": 95}
    assert B.strong_vcp_reject(bare) is None          # nothing to reject on
    assert B.strong_vcp_reject({"symbol": "Y", "entry_setup": None,
                                "vcp": None}) == "no VCP setup"
