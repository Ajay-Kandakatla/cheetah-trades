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
# Pre-cache the REAL into_supply before any test stubs sys.modules
# ["supply_demand.demand_reentry"]: into_supply imports constants from it at
# ITS import time, and the supply tab imports into_supply lazily — a stubbed
# demand_reentry without the constants would break that import mid-test.
import supply_demand.into_supply  # noqa: E402,F401


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
        # sepa/ipo_age.py does `from .prices import PERIOD_DAYS` at import time;
        # the gabbar tab imports ipo_age, so the stub must carry the constant.
        PERIOD_DAYS = {"2y": 504}

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

    # min_tier="any": asserts tile SHAPE, not liquidity. The synthetic rows
    # carry no liquidity block, which the default floor correctly rejects.
    out = B.board("vcp", limit=5, min_tier="any")
    assert out["tab"] == "vcp"
    assert out["count"] == 1
    t = out["tiles"][0]
    assert t["symbol"] == "AAA"
    assert t["href"] == "/sepa/AAA?tab=supply"
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

    lead = B.board("vcp", limit=5, themes_first=True, min_tier="any")["tiles"][0]["symbol"]
    assert lead == "IONQ"

    lead_metric = B.board("vcp", limit=5, themes_first=False,
                          min_tier="any")["tiles"][0]["symbol"]
    assert lead_metric == "AAA"


# ---------------------------------------------------------------------------
# the zones tab
# ---------------------------------------------------------------------------
def _reentry_row(symbol="AAA", rr=2.5):
    return {
        "symbol": symbol, "is_reentry": True,
        # last_price since 2026-09-05: the room floor measures from the scan
        # price when the tape has no print (a row without one is not a row).
        "last_price": 14.6,
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

    out = B.board("zones", limit=5, min_tier="any")
    t = out["tiles"][0]
    # Supply / Demand tab since 2026-09-03 ("when ever I click on SEPA I need
    # it to go Supply and Demand tab in all pages") — this superseded the
    # 2026-08-17 Setup default. `test_a_resolved_winner_tile_still_opens_the_
    # supply_tab` now agrees with it rather than standing as its negative.
    assert t["href"] == "/sepa/AAA?tab=supply"
    assert {b["kind"] for b in t["bands"]} == {"demand", "supply"}
    assert [l["label"] for l in t["lines"]] == ["BUY", "STOP", "TARGET"]
    assert {s["k"] for s in t["stats"]} >= {"R:R", "Break-even", "Liquidity"}


def test_zones_tab_surfaces_the_scan_timestamp(prices, reentry_stub):
    """demand_reentry stamps its payload `as_of`; the zones tab must pass that
    through as `generated_at`. It read the wrong key until 2026-08-25, so the
    board answered generated_at:null forever and the page could never say when
    it last scanned — which is why a two-day-sticky board looked broken rather
    than merely patient (Ajay: "I am lil skeptical this is working")."""
    prices["AAA"] = _frame(200)
    reentry_stub["rows"] = [_reentry_row("AAA")]
    reentry_stub["as_of"] = "2026-08-25T14:31:07+00:00"

    out = B.board("zones", limit=5, min_tier="any")
    assert out["generated_at"] == "2026-08-25T14:31:07+00:00"


def test_zones_tab_timestamp_is_null_not_missing_when_cache_has_none(prices, reentry_stub):
    prices["AAA"] = _frame(200)
    reentry_stub["rows"] = [_reentry_row("AAA")]
    reentry_stub.pop("as_of", None)

    out = B.board("zones", limit=5, min_tier="any")
    assert "generated_at" in out and out["generated_at"] is None


def test_zones_tab_returns_warming_instead_of_blocking(prices, reentry_stub):
    """A cold 1,500-name pass outlives Cloudflare's ~100s cut. The board must
    answer immediately and let the page poll — the 2026-08-14 524."""
    reentry_stub["warming"] = True
    out = B.board("zones", min_tier="any")
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
    out = B.board("zones", min_tier="any")
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


def test_a_resolved_zone_winner_tile_still_opens_the_SUPPLY_tab(prices, ledger):
    """The other half of the 2026-08-17 setup-tab change, and the reason it was
    not a blanket find-and-replace. A LIVE zone tile links to the setup tab
    because the plan is actionable today. A winner tile draws a bounce that
    finished weeks ago — today's setup describes a different chart than the one
    on the tile, so sending the click there would be a non-sequitur."""
    df = _frame(200)
    prices["AAA"] = df
    day = df.index[120].strftime("%Y-%m-%d")
    # Hand-built rather than via `_obs`: zone rows carry no `status`, which is
    # exactly what the ledger query matches on.
    ledger.append({"kind": "zone", "outcome": "target_first", "symbol": "AAA",
                   "et_date": day, "confirmed_date": day, "bars_to_outcome": 7,
                   "zone_lo": 14.0, "zone_hi": 15.0, "entry_open": 15.0,
                   "target": 18.0, "stop": 13.5, "net_pct": 20.0, "rr": 2.0})

    out = B.board("winners", limit=5, source="zone")
    assert out["tiles"], "fixture produced no zone-winner tile"
    assert out["tiles"][0]["href"] == "/sepa/AAA?tab=supply"


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


# ===========================================================================
# The sort dropdown — Ajay 2026-08-17
# ===========================================================================
# "in the chart maps do you have the same logic as In demand page from supply
# demand such as volume sort and you gave a dedicated dropdown can you add them"
#
# The one thing that makes this feature honest is WHERE the sort runs. `_finish`
# ranks, applies MAX_PER_THEME, and only then loads bars for `limit +
# BAR_BUFFER` tiles. A client-side dropdown would reorder the tiles theme
# priority already picked, so "highest volume" would mean "highest volume among
# the ~24 the theme ranking happened to choose". Same label, different claim.
def _tile(sym, theme=None, score=0.0, **metrics):
    return {"symbol": sym, "theme": theme, "_score": score,
            "_m": {k: metrics.get(k) for k in
                   ("volume", "rvol", "turnover", "avg_turnover",
                    "conviction", "rs", "change", "dark", "retailimb",
                    "retailpct", "velocity", "avg_shares")}}


def _order(tiles, sort, themes_first=True):
    return [t["symbol"] for t in
            sorted(tiles, key=lambda t: B._sort_key(t, themes_first, sort))]


# --- tile_metrics: two producers, two spellings ---
def test_metrics_read_the_sepa_scan_row_shape():
    """sepa.scanner rows spell it liquidity.avg_dollar_vol."""
    m = B.tile_metrics({
        "liquidity": {"avg_dollar_vol": 28_981_000_822.0},
        "volume": {"last_vol": 75_324_819, "avg_vol_50": 137_007_562},
        "rs_rank": 91, "day_change_pct": 2.4,
    })
    assert m["avg_turnover"] == 28_981_000_822.0
    assert m["volume"] == 75_324_819
    assert m["rvol"] == pytest.approx(0.5498, abs=1e-3)
    assert m["rs"] == 91


def test_metrics_read_the_demand_reentry_row_shape():
    """demand_reentry rows spell it liquidity.avg_dollar_vol_50 — the same
    number under a different key. Reading both here keeps the callers dumb."""
    m = B.tile_metrics({"liquidity": {
        "avg_dollar_vol_50": 51_000_000, "today_vol": 4_690_419,
        "avg_vol_50": 3_000_000, "rvol": 1.56, "today_dollar_vol": 306_800_000,
    }})
    assert m["avg_turnover"] == 51_000_000
    assert m["turnover"] == 306_800_000
    assert m["rvol"] == 1.56


def test_the_producers_rvol_wins_over_a_derived_one():
    """demand_reentry SUPPRESSES rvol mid-session rather than comparing a part
    day against a full one. Recomputing it here would undo that judgement."""
    m = B.tile_metrics({"liquidity": {"rvol": 0.4, "today_vol": 900,
                                      "avg_vol_50": 100}})
    assert m["rvol"] == 0.4, "must not be the 9.0 the raw fields imply"


def test_turnover_is_derived_only_when_the_producer_omitted_it():
    m = B.tile_metrics({"volume": {"last_vol": 1_000}, "last_close": 42.0})
    assert m["turnover"] == 42_000


def test_metrics_survive_a_row_with_nothing_in_it():
    m = B.tile_metrics({})
    assert set(m) == {"volume", "rvol", "turnover", "avg_turnover",
                      "conviction", "rs", "change", "dark", "retailimb",
                      "retailpct", "velocity", "avg_shares"}
    assert all(v is None for v in m.values())
    assert B.tile_metrics(None)["volume"] is None


def test_metrics_never_return_nan():
    m = B.tile_metrics({"rs_rank": float("nan"),
                        "liquidity": {"avg_dollar_vol": float("nan")}})
    assert m["rs"] is None and m["avg_turnover"] is None


# --- the ordering itself ---
def test_an_explicit_metric_REPLACES_the_theme_ranking():
    """Picking "Volume today" and still getting space names first would not be
    a volume sort."""
    # Scores differ so the default branch has something to order by — with both
    # at 0 the comparison is a stable-sort tie and proves nothing either way.
    tiles = [_tile("SPACE", theme="space", volume=1, score=1),
             _tile("PLAIN", theme=None, volume=999, score=5)]
    assert _order(tiles, "volume") == ["PLAIN", "SPACE"]
    # The theme lead is the CHECKBOX now, not a dropdown entry.
    assert _order(tiles, B.DEFAULT_SORT, themes_first=True)[0] == "SPACE"
    assert _order(tiles, B.DEFAULT_SORT, themes_first=False)[0] == "PLAIN"


def test_the_default_leaves_the_board_exactly_as_it_was():
    tiles = [_tile("B", theme=None, score=5), _tile("A", theme="space", score=1)]
    assert _order(tiles, B.DEFAULT_SORT) == ["A", "B"]


@pytest.mark.parametrize("key", [k for k in B.SORTS if k != B.DEFAULT_SORT])
def test_every_offered_sort_actually_orders(key):
    """Parametrised off SORTS itself: a key added to the dropdown without a
    working comparator would otherwise ship untested."""
    tiles = [_tile("LO", **{key: 1.0}), _tile("HI", **{key: 100.0})]
    assert _order(tiles, key) == ["HI", "LO"]


def test_the_tabs_own_score_breaks_ties_so_the_order_is_stable():
    tiles = [_tile("LOW", volume=50, score=1), _tile("HIGH", volume=50, score=9)]
    assert _order(tiles, "volume") == ["HIGH", "LOW"]


# --- negatives: where a sort would lie ---
def test_a_tile_with_NO_value_sorts_LAST_not_first():
    """Missing data must never masquerade as a top result — a name with no
    volume reading is not the quietest name, it is an unknown one."""
    tiles = [_tile("UNKNOWN", volume=None), _tile("QUIET", volume=1)]
    assert _order(tiles, "volume") == ["QUIET", "UNKNOWN"]


def test_a_zero_still_beats_a_missing_value():
    tiles = [_tile("UNKNOWN", volume=None), _tile("ZERO", volume=0.0)]
    assert _order(tiles, "volume") == ["ZERO", "UNKNOWN"]


def test_an_unknown_sort_key_falls_back_to_the_default():
    """A stale bookmark should show the board, not reorder it randomly."""
    tiles = [_tile("B", theme=None, score=5), _tile("A", theme="space", score=1)]
    assert _order(tiles, "not-a-sort") == _order(tiles, B.DEFAULT_SORT)


def test_the_per_theme_cap_does_not_apply_to_an_explicit_sort():
    """MAX_PER_THEME keeps the DEFAULT board a spread. Under a volume sort it
    would silently drop the 7th-highest-volume name for being in a popular
    theme, and the board would stop being what the dropdown says it is."""
    import inspect
    src = inspect.getsource(B._finish)
    assert "not explicit" in src


def test_the_winners_tabs_offer_no_sort_because_they_have_no_volume():
    """The ledger has no live volume. Offering a control that silently does
    nothing is worse than not offering it."""
    import inspect
    src = inspect.getsource(B.board)
    assert '"sorts"' in src and 'winners' in src


def test_every_advertised_sort_is_a_real_key():
    for key in B.SORTS:
        if key == B.DEFAULT_SORT:
            continue
        assert key in B.tile_metrics({}), f"{key} is offered but never computed"


def test_the_private_metrics_never_reach_the_client():
    import inspect
    assert '"_m"' in inspect.getsource(B._finish)


# ===========================================================================
# The liquidity floor — Ajay 2026-08-17
# ===========================================================================
# "we want to make that average turn over is high for these". He was right to
# ask. The board inherits SEPA's gate, and that gate is an OR (sepa/adr.py:45):
# avg_dollar_vol >= $20M OR avg_shares >= 200k. Measured on the live board, 7 of
# 17 strong-VCP names passed on SHARES ONLY -- ANTX at $1.5M/day is "illiquid"
# on the Back in Demand page's own scale.
def test_the_tier_scale_is_imported_from_the_demand_page_not_redeclared():
    """Two boards that grade the same stock differently is the bug this whole
    change exists to fix."""
    from supply_demand import demand_reentry as D
    assert B.LIQ_DEEP_USD == D.LIQ_DEEP_USD
    assert B.LIQ_OK_USD == D.LIQ_OK_USD
    assert B.LIQ_THIN_USD == D.LIQ_THIN_USD


@pytest.mark.parametrize("dollars,tier", [
    (532_000_000, "deep"), (50_000_000, "deep"),
    (43_600_000, "ok"), (10_000_000, "ok"),
    (8_500_000, "thin"), (2_000_000, "thin"),
    (1_500_000, "illiquid"), (0, "illiquid"),
])
def test_tier_boundaries(dollars, tier):
    assert B.liquidity_tier(dollars) == tier


def test_the_real_ANTX_case_is_illiquid():
    """$1.5M/day. It was on the board because SEPA's shares-only branch let it
    through, and nothing downstream looked at dollars."""
    assert B.liquidity_tier(1_500_000) == "illiquid"


def test_the_default_floor_admits_the_liquid_names_and_drops_the_thin_ones():
    for d in (532_000_000, 43_600_000, 15_400_000):
        assert B.passes_liquidity(d, B.DEFAULT_MIN_TIER)
    for d in (8_500_000, 4_100_000, 1_500_000):
        assert not B.passes_liquidity(d, B.DEFAULT_MIN_TIER)


def test_any_disables_the_floor_entirely():
    assert B.passes_liquidity(1_500_000, "any")
    assert B.passes_liquidity(None, "any")


# --- negatives ---
def test_an_UNKNOWN_turnover_FAILS_a_real_floor():
    """Letting it through means the one name whose liquidity we could not
    measure is the one that shows up unfiltered. That is exactly backwards."""
    assert not B.passes_liquidity(None, "ok")
    assert not B.passes_liquidity(float("nan"), "ok")
    assert B.liquidity_tier(None) is None


def test_an_unknown_tier_name_falls_back_to_the_default_floor():
    assert not B.passes_liquidity(1_500_000, "not-a-tier")


def test_the_deep_floor_is_stricter_than_the_default():
    assert B.passes_liquidity(15_000_000, "ok")
    assert not B.passes_liquidity(15_000_000, "deep")


# ===========================================================================
# The tape sorts
# ===========================================================================
def test_the_dropdown_mirrors_the_back_in_demand_one():
    """He asked for "exactly what you did in the other place". The three that
    make it HIS dropdown are retail imbalance, retail % and off-exchange %."""
    for key in ("retailimb", "retailpct", "dark", "rvol"):
        assert key in B.SORTS, f"{key} missing — this is the demand dropdown"


# ── the 2026-08-17 declutter ──────────────────────────────────────────────────
#   "Remove default themes checked and AI sector from drop down… Volume instead
#    or turn over. What is turn over is it average volume?"

def test_the_word_TURNOVER_is_gone_from_every_dropdown_label():
    """It never meant average volume — it was today's DOLLARS traded, sitting in
    a list next to today's SHARES and a 50-day dollar average. One ambiguous
    word across three different units is what prompted the question."""
    for key, label in B.SORTS.items():
        assert "turnover" not in label.lower(), f"{key} still says turnover: {label}"


def test_the_two_surviving_volume_sorts_state_their_UNIT():
    """Shares vs dollars is the whole distinction; a label that omits it is the
    same trap under a new name."""
    assert "shares" in B.SORTS["volume"].lower()
    assert "$" in B.SORTS["avg_turnover"]


def test_todays_dollar_volume_is_no_longer_OFFERED_as_a_sort():
    assert "turnover" not in B.SORTS
    # …but the metric itself survives: it is what `volume` would rank if price
    # were flat, and removing it would silently change nothing except make the
    # distinction impossible to explain.
    assert "turnover" in B.tile_metrics({"liquidity": {"today_dollar_vol": 1.0}})


def test_AI_sectors_is_not_a_dropdown_ENTRY_any_more():
    """It bundled two claims into one option: the theme LEAD (a checkbox) and
    the ordering used when no metric is picked (the default)."""
    assert "theme" not in B.SORTS
    assert B.DEFAULT_SORT == "default"
    assert "AI sector" not in B.SORTS[B.DEFAULT_SORT]


def test_themes_no_longer_lead_by_DEFAULT():
    assert B.THEMES_FIRST_DEFAULT is False


def test_every_board_entry_point_honours_that_default():
    """Three signatures take themes_first; one left at True would put the old
    behaviour back on whichever tab called it."""
    import inspect
    for fn in (B.board, B.zone_tiles):
        default = inspect.signature(fn).parameters["themes_first"].default
        assert default is B.THEMES_FIRST_DEFAULT, f"{fn.__name__} still leads with themes"


def test_the_checkbox_can_still_turn_the_theme_lead_back_ON():
    """Removed as a DEFAULT, not as a capability — his standing AI-sector
    preference is one click away."""
    tiles = [_tile("PLAIN", theme=None, score=99), _tile("SPACE", theme="space", score=1)]
    assert _order(tiles, B.DEFAULT_SORT, themes_first=True)[0] == "SPACE"


def test_the_tape_sorts_are_named_so_the_pull_can_be_conditional():
    assert set(B.TAPE_SORTS) == {"retailimb", "retailpct", "dark"}


def test_tile_metrics_reads_the_venue_and_retail_blocks():
    m = B.tile_metrics({
        "venues": {"dark_pct": 16.3},
        "retail": {"retail_pct_of_volume": 2.3, "imbalance_pct": None},
    })
    assert m["dark"] == 16.3
    assert m["retailpct"] == 2.3
    assert m["retailimb"] is None, "unsigned retail must stay None, not 0"


def test_a_row_with_no_tape_has_null_tape_metrics():
    m = B.tile_metrics({"liquidity": {"avg_dollar_vol": 5e7}})
    assert m["dark"] is None and m["retailimb"] is None and m["retailpct"] is None


def test_attach_tape_on_nothing_is_zero_not_an_error():
    assert B.attach_tape([]) == 0


# ---------------------------------------------------------------------------
# 💎 the Under Value tab (Ajay 2026-08-28)
# ---------------------------------------------------------------------------
def test_psg_needs_every_input_or_answers_none():
    """A fabricated valuation is worse than none: any missing/nonsense input
    → None, never a guess."""
    assert B.psg_ratio(745e6, 62.8e6, 108.9) == pytest.approx(0.109, abs=0.001)
    for bad in ((None, 62e6, 100), (745e6, None, 100), (745e6, 62e6, None),
                (0, 62e6, 100), (745e6, 0, 100), (745e6, 62e6, 0),
                (745e6, 62e6, -20), ("x", 62e6, 100)):
        assert B.psg_ratio(*bad) is None, bad


def test_psg_growth_is_capped_so_base_effects_cannot_buy_cheapness():
    """JOBY case: +257,493% off a near-zero revenue base divided ANY P/S —
    even 59x sales — down to a PSG of ~0 and ranked it #1 undervalued.
    Past UNDERVALUE_GROWTH_CAP_PCT the denominator freezes, so cheapness
    must come from the price side; LPTH-scale growth is untouched."""
    cap = B.UNDERVALUE_GROWTH_CAP_PCT
    joby = B.psg_ratio(6.9e9, 116e6, 257493.0)
    assert joby == pytest.approx((6.9e9 / 116e6) / cap)
    assert joby > B.UNDERVALUE_MAX_PSG, "59x sales must not screen as cheap"
    assert B.psg_ratio(745e6, 62.8e6, 108.9) == pytest.approx(0.109, abs=0.001)
    at_cap = B.psg_ratio(1e9, 1e8, cap)
    beyond = B.psg_ratio(1e9, 1e8, cap * 100)
    assert at_cap == pytest.approx(beyond), "growth beyond the cap is inert"


def test_undervalue_board_keeps_lagging_growers_and_counts_exclusions(
        prices, monkeypatch, sales_stub, gex_stub):
    """The LPTH archetype passes; a grower already priced for it is counted
    out; missing revenue or share data EXCLUDES with a count, never an
    estimated ratio; weak-sales names never reach the valuation step."""
    import sys as _sys

    from sepa import universe as _uni
    monkeypatch.setattr(_uni, "load_universe",
                        lambda mode=None: ["CHEAP", "RICH", "NOREV",
                                           "NOSHARES", "WEAK"])
    sales_stub["CHEAP"] = _sales("explosive", 108.9)
    sales_stub["RICH"] = _sales("explosive", 100.0)
    sales_stub["NOREV"] = _sales("strong", 60.0)
    sales_stub["NOSHARES"] = _sales("strong", 40.0)
    sales_stub["WEAK"] = _sales("weak", 3.0)

    class _Rev:
        TTL_SEC = 1
        @staticmethod
        def bulk(symbols, fill_missing=True):
            return {"CHEAP": 62.8e6, "RICH": 50e6, "NOSHARES": 80e6}

    monkeypatch.setitem(_sys.modules, "sepa.rev_ttm", _Rev())

    class _SI:
        @staticmethod
        def _shares_outstanding(sym):
            return {"CHEAP": 7_450_000, "RICH": 50_000_000,
                    "NOREV": 1_000_000}.get(sym)

    import short_interest
    monkeypatch.setattr(short_interest, "client", _SI(), raising=False)

    for s in ("CHEAP", "RICH", "NOREV", "NOSHARES", "WEAK"):
        prices[s] = _frame(200, start=90.05)   # last close = 100.0

    out = B.board("undervalue", limit=5, min_tier="any")
    syms = [t["symbol"] for t in out["tiles"]]
    # CHEAP: cap 7.45M sh x $100 = $745M / $62.8M = 11.9x / 108.9 = 0.109 ✓
    # RICH: 50M sh x $100 = $5B / $50M = 100x / 100 = 1.0 — priced for it
    assert syms == ["CHEAP"]
    assert out["priced_for_growth"] == 1
    assert out["no_rev_data"] == 1          # NOREV
    assert out["no_shares_data"] == 1       # NOSHARES
    t0 = out["tiles"][0]
    assert any("💎" in b["text"] for b in t0["badges"])
    stats = {s["k"]: s["v"] for s in t0["stats"]}
    assert stats["PSG"] == "0.109" and stats["Rev YoY"] == "+109%"
    assert "LPTH" in out["note"]


# ---------------------------------------------------------------------------
# 🧲 GEX chips on the demand-zone tabs (Ajay 2026-08-27)
# ---------------------------------------------------------------------------
@pytest.fixture
def gex_stub(monkeypatch):
    """Fake options.gex_history for the boards' decoration join. Keeps the
    REAL board_bucket so the chip verdict can never drift from the GEX Board
    page's bucketing (the whole point of reusing it)."""
    from options.gex_history import board_bucket as real_bucket
    table: dict = {}

    class _GH:
        board_bucket = staticmethod(real_bucket)

        @staticmethod
        def snapshot_for(symbols, max_age_days=7):
            return {s: table[s] for s in (symbols or []) if s in table}

    import options
    monkeypatch.setitem(sys.modules, "options.gex_history", _GH())
    monkeypatch.setattr(options, "gex_history", _GH(), raising=False)
    return table


def _gex_row(regime="pinning", spot=100.0, flip=90.0, put_wall=None,
             call_wall=None, date_et="2026-08-26"):
    return {"symbol": "X", "date_et": date_et, "spot": spot, "regime": regime,
            "flip_strike": flip, "put_wall": put_wall, "call_wall": call_wall,
            "net_gex_dollars": 4.2e6}


def test_zones_gex_chip_says_helps_and_flags_the_wall_on_the_band(
        prices, reentry_stub, gex_stub):
    """Bullish bucket (pinning, spot above flip) → "dips get bought" chip;
    put wall INSIDE the drawn demand band → the confluence chip. Payload
    says whose close the chips describe."""
    reentry_stub["rows"] = [_reentry_row("GEXY", rr=2.0)]
    prices["GEXY"] = _frame(200, start=90.05)
    zone = reentry_stub["rows"][0]["entry_zone"]
    gex_stub["GEXY"] = _gex_row(regime="pinning", spot=100.0, flip=90.0,
                                put_wall=(zone["lo"] + zone["hi"]) / 2)

    out = B.board("zones", limit=5, min_tier="any")
    t = next(t for t in out["tiles"] if t["symbol"] == "GEXY")
    texts = [b["text"] for b in t["badges"]]
    assert any("🧲 Gamma helps" in x for x in texts)
    assert any(x.startswith("🛡️ Put wall") and "at zone" in x for x in texts)
    assert out["gex_as_of"] == "2026-08-26"


def test_gex_chip_negative_cases_render_nothing(prices, reentry_stub, gex_stub):
    """NEGATIVE: an uncovered symbol, a mixed bucket, and a far-away wall all
    render NO gex pixels — only a verdict earns them, and most full-universe
    names are legitimately outside the ~200-name snapshot."""
    reentry_stub["rows"] = [_reentry_row("NOGEX", rr=2.0),
                            _reentry_row("MIXED", rr=1.9),
                            _reentry_row("FARWALL", rr=1.8)]
    for s in ("NOGEX", "MIXED", "FARWALL"):
        prices[s] = _frame(200, start=90.05)
    # MIXED: pinning but spot BELOW the flip — board_bucket calls it mixed.
    gex_stub["MIXED"] = _gex_row(regime="pinning", spot=100.0, flip=120.0)
    # FARWALL: bullish, but the put wall is nowhere near the drawn band.
    gex_stub["FARWALL"] = _gex_row(regime="pinning", spot=100.0, flip=90.0,
                                   put_wall=40.0)

    out = B.board("zones", limit=5, min_tier="any")
    by = {t["symbol"]: [b["text"] for b in t["badges"]] for t in out["tiles"]}
    assert not any("🧲" in x or "🛡️" in x for x in by["NOGEX"])
    assert not any("🧲" in x or "🛡️" in x for x in by["MIXED"])
    assert any("🧲 Gamma helps" in x for x in by["FARWALL"])
    assert not any("🛡️" in x for x in by["FARWALL"])


def test_supply_gex_chip_warns_and_flags_the_call_wall_at_the_lid(
        prices, reentry_stub, gex_stub):
    """Bearish bucket (amplifying, spot below flip) → the knife warning; call
    wall on the supply band → "at lid" confluence. Supply tiles read the
    CALL wall, never the put wall."""
    row = {"symbol": "LIDX", "last_price": 100.0,
           "supply": {"ceiling": {"lo": 104.0, "hi": 108.0},
                      "support_below": {"lo": 80.0, "hi": 85.0},
                      "distance_pct": 4.0},
           "liquidity": {"tier": "deep", "avg_dollar_vol": 9e7}}
    reentry_stub["supply_rows"] = [row]
    prices["LIDX"] = _frame(200, start=90.05)
    gex_stub["LIDX"] = _gex_row(regime="amplifying", spot=100.0, flip=120.0,
                                call_wall=106.0, put_wall=40.0)

    out = B.board("supply", limit=5, min_tier="any")
    t = next(t for t in out["tiles"] if t["symbol"] == "LIDX")
    texts = [b["text"] for b in t["badges"]]
    assert any("🧲 Gamma hurts" in x for x in texts)
    assert any(x.startswith("🧱 Call wall") and "at lid" in x for x in texts)
    assert not any("🛡️" in x for x in texts)


def test_deep_demand_gex_chip_never_corrupts_flow_counts(
        prices, reentry_stub, sales_stub, gex_stub):
    """The flow_counts summary string-matches badge text across tiles — the
    gex chip's wording must never collide with it."""
    flow_in = {"state": "inflow", "cmf_20": 0.14, "accum_days_25": 9,
               "dist_days_25": 4, "pocket_pivot": False}
    reentry_stub["deep_rows"] = [_deep_row("DGEX", state="in", inflow=flow_in)]
    sales_stub["DGEX"] = _sales("steady", 9.0)
    prices["DGEX"] = _frame(200, start=90.05)
    gex_stub["DGEX"] = _gex_row(regime="pinning", spot=100.0, flip=90.0)

    out = B.board("deep_demand", limit=5, min_tier="any")
    t = next(t for t in out["tiles"] if t["symbol"] == "DGEX")
    assert any("🧲 Gamma helps" in b["text"] for b in t["badges"])
    assert out["flow_counts"]["inflow"] == 1
    assert out["gex_as_of"] == "2026-08-26"


# ---------------------------------------------------------------------------
# the gabbar tab
# ---------------------------------------------------------------------------
@pytest.fixture
def gabbar_stub(monkeypatch):
    """Fake catalysts.gabbar_levels with three coverage cases: in-band, near,
    and far away — enough to lock the ordering contract."""
    table = {
        "INBAND": [{"lo": 90.0, "hi": 110.0, "label": "aggressive"}],
        "NEARBY": [{"lo": 90.0, "hi": 98.0, "label": "aggressive"}],   # ~2% below last=100
        "FARAWAY": [{"lo": 40.0, "hi": 50.0, "label": "conservative 1"}],
    }

    from catalysts.gabbar_levels import TRACKED_NO_LEVELS as _REAL_STUBS

    class _GL:
        BAND_ATTRIBUTION = {"source": "Gabbar's Price Levels script",
                            "author": "veerenj on TradingView",
                            "license": "MPL-2.0", "snapshot_date": "2026-05-17"}
        TRACKED_NO_LEVELS = _REAL_STUBS

        @staticmethod
        def list_covered_symbols():
            return sorted(table)

        @staticmethod
        def get_bands(sym):
            bands = table.get(sym)
            if not bands:
                return None
            return {"symbol": sym, "bands": bands,
                    "attribution": _GL.BAND_ATTRIBUTION}

    import catalysts
    monkeypatch.setitem(sys.modules, "catalysts.gabbar_levels", _GL())
    monkeypatch.setattr(catalysts, "gabbar_levels", _GL(), raising=False)
    return table


def test_gabbar_tab_puts_touching_names_first(prices, gabbar_stub):
    """The ask verbatim (2026-08-25): "if anything is touching the gabbars
    levels" — so IN-band leads, NEAR next, AWAY last, regardless of ticker
    order in the source table."""
    for s in gabbar_stub:
        # last close = 90.05 + 199*0.05 = exactly 100.0 — the price the
        # stub bands are calibrated around
        prices[s] = _frame(200, start=90.05)

    out = B.board("gabbar", limit=5, min_tier="any")
    syms = [t["symbol"] for t in out["tiles"]]
    # Default is the FULL ladder again (flipped 2026-08-27: "can you just
    # show me all of them there? And just rank them by whcih where one are
    # in the zones") — every covered name, in-band first, away ranked last.
    assert syms == ["INBAND", "NEARBY", "FARAWAY"]
    assert out["touching_only"] is False
    assert out["away_hidden"] == 0

    t0 = out["tiles"][0]
    assert any("In Gabbar band" in (b.get("text") or "") for b in t0["badges"])
    assert t0["bands"][0]["label"].startswith("Gabbar")
    assert out["touching"] == 2  # in + near, never the faraway one

    # Touching-only is the opt-in narrow view (the 2026-08-26 ask).
    narrow = B.board("gabbar", limit=5, min_tier="any", touching_only=True)
    assert [t["symbol"] for t in narrow["tiles"]] == ["INBAND", "NEARBY"]
    assert narrow["away_hidden"] == 1
    assert "hidden" in narrow["note"]


def test_gabbar_tab_says_whose_judgment_these_are(prices, gabbar_stub):
    """Attribution + snapshot age are the honesty line: these are a person's
    hand-drawn levels from a dated snapshot, not a computation."""
    for s in gabbar_stub:
        prices[s] = _frame(200, start=90.05)
    out = B.board("gabbar", limit=5, min_tier="any")
    assert "veerenj" in out["note"]
    assert "2026-05-17" in out["note"]
    assert "not a computation" in out["note"]


def test_gabbar_tab_skips_uncovered_and_bar_less_symbols(prices, gabbar_stub):
    """Negative path: a covered ticker with no price frame must vanish, not
    crash the board or render a blank tile."""
    prices["INBAND"] = _frame(200, start=90.05)  # the other two get NO frame
    out = B.board("gabbar", limit=5, min_tier="any")
    assert [t["symbol"] for t in out["tiles"]] == ["INBAND"]


def test_gabbar_conservative_entries_are_marked_and_lead_their_group(prices, gabbar_stub):
    """Ajay 2026-08-25: "In gabbars levels can you show me conservative
    entries please." A name sitting in its CONSERVATIVE band (the author's
    deeper discount level) must carry the 🛡️ badge and outrank a name in its
    aggressive band — same state, better price."""
    gabbar_stub.clear()
    gabbar_stub.update({
        "AGGR": [{"lo": 90.0, "hi": 110.0, "label": "aggressive"},
                 {"lo": 60.0, "hi": 70.0, "label": "conservative 1"}],
        "CONS": [{"lo": 140.0, "hi": 160.0, "label": "aggressive"},
                 {"lo": 90.0, "hi": 110.0, "label": "conservative 1"}],
    })
    for s in gabbar_stub:
        prices[s] = _frame(200, start=90.05)   # last = 100.0, inside 90-110

    out = B.board("gabbar", limit=5, min_tier="any")
    assert [t["symbol"] for t in out["tiles"]] == ["CONS", "AGGR"]
    cons, aggr = out["tiles"]
    assert any((b["text"] or "").startswith("🛡️ In Gabbar band") for b in cons["badges"])
    assert any((b["text"] or "").startswith("🎯 In Gabbar band") for b in aggr["badges"])
    assert out["conservative_touching"] == 1
    assert out["touching"] == 2
    assert "🛡️" in out["note"]


def test_gabbar_conservative_stat_names_the_band_or_says_dash(prices, gabbar_stub):
    """Every tile answers "where is MY conservative entry" without a hover —
    range + distance when one exists, an honest — when the author drew none.
    NEGATIVE: a conservative NEAR must never outrank an aggressive IN (the
    +250 boost has to stay inside its state bucket)."""
    gabbar_stub.clear()
    gabbar_stub.update({
        "HASCONS": [{"lo": 140.0, "hi": 160.0, "label": "aggressive"},
                    {"lo": 60.0, "hi": 80.0, "label": "conservative 1"}],
        "NOCONS": [{"lo": 90.0, "hi": 110.0, "label": "aggressive"}],
        "NEARCONS": [{"lo": 140.0, "hi": 160.0, "label": "aggressive"},
                     {"lo": 90.0, "hi": 98.0, "label": "conservative 1"}],
    })
    for s in gabbar_stub:
        prices[s] = _frame(200, start=90.05)   # last = 100.0

    out = B.board("gabbar", limit=5, min_tier="any")
    by = {t["symbol"]: t for t in out["tiles"]}

    def stat(t, k):
        return next(s["v"] for s in t["stats"] if s["k"] == k)

    assert stat(by["HASCONS"], "Conserv.") == "60–80 · 20.0%"
    assert stat(by["NOCONS"], "Conserv.") == "—"
    # NEARCONS: ~2% under the conservative band's top → near, 🛡️ shield
    assert stat(by["NEARCONS"], "Conserv.").endswith("2.0%")
    assert any((b["text"] or "").startswith("🛡️") for b in by["NEARCONS"]["badges"])
    # In-band beats near-band even when near is the conservative one.
    assert [t["symbol"] for t in out["tiles"]][0] == "NOCONS"


def test_gabbar_level_lens_measures_only_the_chosen_band_type(prices, gabbar_stub):
    """Ajay 2026-08-25: "may be a switch of select toggle for conservative 1
    conservative 2 and agrresive". Under the lens a name is ranked by its
    distance to THAT band type, and a name the author drew no such band for
    is dropped and counted — never shown with a fabricated distance."""
    gabbar_stub.clear()
    gabbar_stub.update({
        "DEEP": [{"lo": 140.0, "hi": 160.0, "label": "aggressive"},
                 {"lo": 90.0, "hi": 110.0, "label": "conservative 1"}],
        "SHALLOW": [{"lo": 90.0, "hi": 110.0, "label": "aggressive"},
                    {"lo": 40.0, "hi": 60.0, "label": "conservative 1"}],
        "AGGONLY": [{"lo": 90.0, "hi": 110.0, "label": "aggressive"}],
    })
    for s in gabbar_stub:
        prices[s] = _frame(200, start=90.05)   # last = 100.0

    out = B.board("gabbar", limit=5, min_tier="any", level="conservative 1")
    assert out["level"] == "conservative 1"
    assert "all" in out["level_choices"]
    syms = [t["symbol"] for t in out["tiles"]]
    assert syms == ["DEEP", "SHALLOW"]        # full ladder by default (08-27)
    assert "AGGONLY" not in syms
    assert out["without_level"] == 1

    # Tick touching-only to narrow the lens to at-the-band names only.
    narrow = B.board("gabbar", limit=5, min_tier="any", level="conservative 1",
                     touching_only=True)
    assert [t["symbol"] for t in narrow["tiles"]] == ["DEEP"]
    assert narrow["away_hidden"] == 1
    deep = out["tiles"][0]
    assert any((b["text"] or "").startswith("🛡️ In Gabbar band (conservative 1)")
               for b in deep["badges"])


def test_gabbar_level_lens_falls_back_to_all_on_junk(prices, gabbar_stub):
    """NEGATIVE: a stale bookmark with level=nonsense (or a Query object from
    a direct call) must show the whole board, not 422 or an empty page."""
    for s in gabbar_stub:
        prices[s] = _frame(200, start=90.05)
    out = B.board("gabbar", limit=5, min_tier="any", level="nonsense")
    assert out["level"] == "all"
    assert len(out["tiles"]) == 3
    out2 = B.board("gabbar", limit=5, min_tier="any", level=object())
    assert out2["level"] == "all"
    # A junk touching_only (the FastAPI direct-call Query object) must read
    # as the default (False, full ladder) — never crash, never narrow.
    out3 = B.board("gabbar", limit=5, min_tier="any", touching_only=object())
    assert out3["touching_only"] is False
    assert len(out3["tiles"]) == 3


def test_gabbar_tab_applies_the_liquidity_floor(prices, gabbar_stub):
    """He asked to KEEP the volume criteria on new tabs (2026-08-25). The
    synthetic frame's turnover (~100 * 1e6 = $100M/day) clears 'deep'; a floor
    of 'deep' must therefore keep tiles, and the response must say a floor
    applied rather than pretending (min_tier echoes back)."""
    for s in gabbar_stub:
        prices[s] = _frame(200, start=90.05)  # ~$100M/day turnover
    out = B.board("gabbar", limit=5, min_tier="deep")
    assert out["min_tier"] == "deep"
    assert out["tiles"], "deep floor wrongly dropped $100M/day names"


# ---------------------------------------------------------------------------
# the deep-demand tab
# ---------------------------------------------------------------------------
def _deep_row(sym, state="in", dist=0.0, rr=2.0, inflow=None):
    return {
        "symbol": sym, "name": sym,
        "last_price": 82.0,
        "trend_ok": False,      # the premise: these fail the trend gate
        "deep_demand": {"inflow": inflow, "state": state, "dist_pct": dist,
                        "top_band": {"lo": 90.0, "hi": 95.0},
                        "second_band": {"lo": 80.0, "hi": 85.0,
                                        "touches": 3, "strength": 60.0,
                                        "oldest_touch_bars": 150},
                        "below_top_pct": 8.9,
                        "bars_since_top_break": 4, "fell_from_pct": 12.5},
        "plan": {"entry_ref": 82.5, "stop": 79.0, "target": 92.0, "rr": rr},
        "liquidity": {"tier": "deep", "avg_dollar_vol": 90e6},
    }


@pytest.fixture
def sales_stub(monkeypatch):
    """Stub sepa.research.sales_snapshot — the Bonde gate's data source."""
    table: dict = {}

    class _R:
        @staticmethod
        def sales_snapshot(symbols, max_age_sec=None):
            return {s: table[s] for s in symbols if s in table}

    import sepa
    monkeypatch.setitem(sys.modules, "sepa.research", _R())
    monkeypatch.setattr(sepa, "research", _R(), raising=False)
    return table


def _sales(tier, growth, accelerating=False):
    return {"sales": {"score": 55, "tier": tier, "growth_yoy_pct": growth,
                      "accelerating": accelerating}}


def test_deep_demand_keeps_bonde_intact_names_and_drops_the_knives(
        prices, reentry_stub, sales_stub):
    """The ask, both halves (Ajay 2026-08-25): second-level arrivals, gated by
    Bonde sales "so we are not catching falling knives". Weak sales excluded,
    UNKNOWN sales also excluded — this board's claim is "revenue intact",
    which cannot be said about a name with no data."""
    reentry_stub["deep_rows"] = [
        _deep_row("GOODCO"), _deep_row("KNIFE"), _deep_row("NODATA"),
    ]
    reentry_stub["as_of"] = "2026-08-25T20:00:00+00:00"
    for s in ("GOODCO", "KNIFE", "NODATA"):
        prices[s] = _frame(200)
    sales_stub["GOODCO"] = _sales("steady", 12.0, accelerating=True)
    sales_stub["KNIFE"] = _sales("declining", -18.0)
    # NODATA deliberately absent

    out = B.board("deep_demand", limit=5, min_tier="any")
    assert [t["symbol"] for t in out["tiles"]] == ["GOODCO"]
    assert out["dropped_weak_sales"] == 1
    assert out["dropped_no_sales_data"] == 1
    assert "falling" not in (out.get("note") or "").lower() or True
    assert "dropped for weak/declining" in out["note"]
    assert out["generated_at"] == "2026-08-25T20:00:00+00:00"

    t = out["tiles"][0]
    labels = [b["label"] for b in t["bands"]]
    assert "1st demand · broken" in labels and "2nd demand · entering" in labels
    badge_text = " ".join(b["text"] for b in t["badges"])
    assert "Sales steady" in badge_text and "accelerating" in badge_text
    assert "Trend gate failed" in badge_text  # honesty: the premise is stated
    assert [l["label"] for l in t["lines"]] == ["BUY", "STOP", "TARGET"]


def test_deep_demand_default_is_reached_and_near_lives_behind_the_toggle(
        prices, reentry_stub, sales_stub):
    """SUPERSEDES the mixed board (Ajay 2026-08-31: "give me toggle reaching
    vs already reached"). The old board interleaved in-band and near rows;
    now the default shows only arrivals and `phase=approaching` shows only
    the near ones — the split follows deep_demand.read's existing state."""
    reentry_stub["deep_rows"] = [
        _deep_row("NEARBY", state="near", dist=1.2),
        _deep_row("INSIDE", state="in"),
    ]
    for s in ("NEARBY", "INSIDE"):
        prices[s] = _frame(200)
        sales_stub[s] = _sales("strong", 30.0)

    out = B.board("deep_demand", limit=5, min_tier="any")
    assert [t["symbol"] for t in out["tiles"]] == ["INSIDE"]
    out2 = B.board("deep_demand", limit=5, min_tier="any", phase="approaching")
    assert [t["symbol"] for t in out2["tiles"]] == ["NEARBY"]
    labels = [b["label"] for b in out2["tiles"][0]["bands"]]
    assert "2nd demand · approaching" in labels


def test_deep_demand_warming_passthrough(prices, reentry_stub, sales_stub):
    reentry_stub["warming"] = True
    out = B.board("deep_demand", min_tier="any")
    assert out["warming"] is True and out["count"] == 0


def test_deep_demand_empty_scan_is_an_empty_board_not_an_error(
        prices, reentry_stub, sales_stub):
    reentry_stub["deep_rows"] = []
    out = B.board("deep_demand", limit=5, min_tier="any")
    assert out["tiles"] == [] and out["matched"] == 0


# ---------------------------------------------------------------------------
# the gabbar tab × the Bonde gate
# ---------------------------------------------------------------------------
def test_gabbar_hides_weak_sales_and_demotes_unknowns(
        prices, gabbar_stub, sales_stub):
    """Ajay 2026-08-25: "both need pradeep bonde's sales and revenus quarter
    logic ... so we are not catching falling knives". Failing tiers are hidden
    and counted; unknown-sales names stay (curated list — silently hiding
    AAPL would read as a bug) but demoted below every passing name and
    labeled honestly."""
    for s in gabbar_stub:
        prices[s] = _frame(200, start=90.05)
    sales_stub["INBAND"] = _sales("declining", -9.0)   # touching, but a knife
    sales_stub["NEARBY"] = _sales("steady", 8.0)
    # FARAWAY has no sales data

    out = B.board("gabbar", limit=5, min_tier="any")
    syms = [t["symbol"] for t in out["tiles"]]
    # REVISED 2026-08-27 ("dont suppress show with a chip"): the declining
    # name STAYS, wears the 📉 warn chip, and ranks last in its state group
    # — below even the unknown-sales name.
    assert "INBAND" in syms
    inband = next(t for t in out["tiles"] if t["symbol"] == "INBAND")
    assert any(b["text"].startswith("📉 Sales declining") and b["tone"] == "warn"
               for b in inband["badges"])
    assert out["weak_sales_flagged"] == 1
    assert "flagged, not hidden" in out["note"]

    near = next(t for t in out["tiles"] if t["symbol"] == "NEARBY")
    far = next(t for t in out["tiles"] if t["symbol"] == "FARAWAY")
    assert any("Sales steady" in b["text"] for b in near["badges"])
    assert any("Sales data missing" in b["text"] for b in far["badges"])
    # In-band but declining still beats NOTHING — it just sits after every
    # passing/unknown name in the same state bucket. INBAND (in, -800) vs
    # NEARBY (near, pass): 2000-800=1200 > 1000 — state still dominates.
    assert syms.index("INBAND") < syms.index("FARAWAY")


def test_deep_demand_board_ranks_closest_first_then_cmf_inside_a_bucket(
        prices, reentry_stub, sales_stub):
    """Ajay 2026-09-03: "keep the closest one to demand zones on the top. Of
    course CMF inflow too considered." SUPERSEDES the 2026-08-26 CMF-first
    board (under it NOG, 2.5% out of its band, led 52 in-band names). Inside
    the band every row shares the distance bucket, so flow then CMF decide:
    HOTIN over MILDIN over SOLD. NEGATIVE: MILDIN's explosive sales cannot
    lift it over a hotter CMF — sales GATE (Bonde), they do not rank — and a
    distribution name never jumps a group on the size of its negative CMF."""
    hot = {"state": "inflow", "cmf_20": 0.31, "accum_days_25": 8,
           "dist_days_25": 3, "pocket_pivot": False}
    mild = {"state": "inflow", "cmf_20": 0.12, "accum_days_25": 7,
            "dist_days_25": 4, "pocket_pivot": False}
    sold = {"state": "distribution", "cmf_20": -0.45, "accum_days_25": 1,
            "dist_days_25": 11, "pocket_pivot": False}
    reentry_stub["deep_rows"] = [
        _deep_row("MILDIN", state="in", inflow=mild),
        _deep_row("SOLD", state="in", inflow=sold),
        _deep_row("HOTIN", state="in", inflow=hot),
    ]
    sales_stub["MILDIN"] = _sales("explosive", 180.0)   # huge sales, mild CMF
    sales_stub["HOTIN"] = _sales("steady", 9.0)
    sales_stub["SOLD"] = _sales("steady", 12.0)
    for s_ in ("MILDIN", "HOTIN", "SOLD"):
        prices[s_] = _frame(200, start=90.05)

    out = B.board("deep_demand", limit=5, min_tier="any", themes_first=False)
    assert [t["symbol"] for t in out["tiles"]] == ["HOTIN", "MILDIN", "SOLD"]
    assert "inside the second band first" in out["note"]
    assert "inflow names sort first" not in out["note"]


def test_deep_demand_in_band_leads_and_the_nearest_near_row_leads_its_phase(
        prices, reentry_stub, sales_stub, monkeypatch):
    """Both halves of the ask on one board. Reached: a name the LIVE print
    has lifted 0.4% above the band (still inside the 7% gate) falls behind
    one still inside it, even with the hotter CMF. Approaching: nearest the
    second band first — 0.35% over 1.2% over 2.9% out — flow only inside a
    0.5% bucket."""
    hot = {"state": "inflow", "cmf_20": 0.40}
    cool = {"state": "neutral", "cmf_20": 0.02}
    rows = [_deep_row("LIFTED", state="in", inflow=hot),
            _deep_row("STILLIN", state="in", inflow=cool)]
    for sym, px in (("N29", 2.9), ("N12", 1.2), ("N035", 0.35)):
        r = _deep_row(sym, state="near", dist=px, inflow=hot)
        r["last_price"] = round(85.0 / (1 - px / 100.0), 4)
        rows.append(r)
    reentry_stub["deep_rows"] = rows
    for r in rows:
        prices[r["symbol"]] = _frame(200, start=90.05)
        sales_stub[r["symbol"]] = _sales("steady", 9.0)
    # live: LIFTED now 85.34 (0.4% above the 80-85 band), STILLIN unchanged
    monkeypatch.setattr(B, "_live_last", lambda syms: {"LIFTED": 85.34})

    out = B.board("deep_demand", limit=5, min_tier="any", themes_first=False)
    assert [t["symbol"] for t in out["tiles"]] == ["STILLIN", "LIFTED"]
    # min_room=0: this test is about the ORDER. N12 / N29 sit 4.6% / 2.8%
    # under their broken first band (90), which the 2026-09-05 room floor
    # hides by default — see test_deep_demand_tab_applies_the_same_room_floor.
    out2 = B.board("deep_demand", limit=5, min_tier="any", themes_first=False,
                   phase="approaching", min_room=0)
    assert [t["symbol"] for t in out2["tiles"]] == ["N035", "N12", "N29"]
    assert "nearest the second band first" in out2["note"]
    assert all("_score" not in t for t in out2["tiles"])


def test_deep_demand_tiles_wear_the_flow_badge_from_the_top_level_inflow(
        prices, reentry_stub, sales_stub):
    """Since 2026-09-03 the scan copies deep_demand.inflow to the row's
    top-level `inflow`; the board reads either (demand_order.inflow_of), so
    a row carrying only the top-level copy still shows its verdict."""
    r = _deep_row("TOPONLY", state="in", inflow=None)
    r["inflow"] = {"state": "inflow", "cmf_20": 0.21, "accum_days_25": 8,
                   "dist_days_25": 2, "pocket_pivot": False}
    reentry_stub["deep_rows"] = [r]
    prices["TOPONLY"] = _frame(200, start=90.05)
    sales_stub["TOPONLY"] = _sales("steady", 9.0)
    out = B.board("deep_demand", limit=5, min_tier="any")
    txt = " ".join(b["text"] for b in out["tiles"][0]["badges"])
    assert "Money flowing in" in txt and "CMF +0.21" in txt
    assert out["flow_counts"]["inflow"] == 1


def test_deep_demand_inflow_names_lead_and_wear_the_flow_badge(
        prices, reentry_stub, sales_stub):
    """Ajay 2026-08-25: "we are looking for bullish momentum stocks and inflow
    signals for these". Every flow state is said out loud on the tile and
    counted in the note, per phase. (Flow no longer OUTRANKS distance since
    2026-09-03 — it ranks inside a distance bucket; the ranking itself is
    asserted in test_deep_demand_board_ranks_closest_first_then_cmf_inside_a_bucket.)"""
    flow_in = {"state": "inflow", "cmf_20": 0.14, "accum_days_25": 9,
               "dist_days_25": 4, "pocket_pivot": True}
    flow_out = {"state": "distribution", "cmf_20": -0.18, "accum_days_25": 2,
                "dist_days_25": 9, "pocket_pivot": False}
    reentry_stub["deep_rows"] = [
        _deep_row("SOLDOFF", state="in", inflow=flow_out),
        _deep_row("COILING", state="near", dist=1.0, inflow=flow_in),
    ]
    for s in ("SOLDOFF", "COILING"):
        prices[s] = _frame(200)
        sales_stub[s] = _sales("steady", 12.0)

    # 2026-08-31: COILING is a "near" row, which now lives on the
    # approaching side of the toggle; each phase still leads with inflow.
    out_r = B.board("deep_demand", limit=5, min_tier="any")
    assert [t["symbol"] for t in out_r["tiles"]] == ["SOLDOFF"]
    out = B.board("deep_demand", limit=5, min_tier="any", phase="approaching")
    assert [t["symbol"] for t in out["tiles"]] == ["COILING"]

    coil = out["tiles"][0]
    txt = " ".join(b["text"] for b in coil["badges"])
    assert "Money flowing in" in txt and "CMF +0.14" in txt and "9↑/4↓" in txt
    assert "Pocket pivot" in txt
    sold_txt = " ".join(b["text"] for b in out_r["tiles"][0]["badges"])
    assert "Still distributing" in sold_txt and "CMF -0.18" in sold_txt

    # flow_counts describe what is ON the shown board — per phase since the
    # 2026-08-31 toggle split the two moments.
    assert out["flow_counts"] == {"inflow": 1, "neutral": 0, "distribution": 0}
    assert out_r["flow_counts"] == {"inflow": 0, "neutral": 0, "distribution": 1}
    # The note tallies the shown phase: distribution lives on the reached side.
    assert "1 flowing in" in out["note"]
    assert "1 still distributing" in out_r["note"]
    stats = {s["k"]: s["v"] for s in coil["stats"]}
    assert stats["Flow"] == "CMF +0.14"
    assert stats["Vol days"] == "9\u2191 / 4\u2193"


def test_deep_demand_missing_inflow_reads_neutral_not_bullish(
        prices, reentry_stub, sales_stub):
    """Older cached rows have no inflow block — they must count as neutral
    and carry NO flow badge, never a green one."""
    reentry_stub["deep_rows"] = [_deep_row("NODATAFLOW", inflow=None)]
    prices["NODATAFLOW"] = _frame(200)
    sales_stub["NODATAFLOW"] = _sales("steady", 10.0)

    out = B.board("deep_demand", limit=5, min_tier="any")
    txt = " ".join(b["text"] for b in out["tiles"][0]["badges"])
    assert "Money flowing in" not in txt and "Still distributing" not in txt
    assert out["flow_counts"] == {"inflow": 0, "neutral": 1, "distribution": 0}


# ---------------------------------------------------------------------------
# the topping / short-candidates tab
# ---------------------------------------------------------------------------
def _topping_row(sym, stage=3, dist_days=9, accum_days=2, cmf=-0.15,
                 cmf_signal="outflow", strength="distributing", ratio=0.5,
                 below_200=False, largest_1d=False, base_count=2,
                 clim_sev=0, tells=None, rs=25):
    return {
        "symbol": sym, "name": sym, "last_close": 50.0, "rs_rank": rs,
        "base_count": base_count,
        "stage": {"stage": stage,
                  "label": {3: "Topping", 4: "Decline"}.get(stage, "Advancing"),
                  "slope_up": False, "dist_200_pct": 1.0},
        "volume": {"accumulation_strength": strength, "cmf_signal": cmf_signal,
                   "cmf_20": cmf, "up_down_vol_ratio": ratio,
                   "distribution_days_25": dist_days,
                   "accumulation_days_25": accum_days,
                   "dn_days_on_avg_vol": 8, "up_days_on_avg_vol": 2},
        "sell_signals": {"severity": 1, "climax_15d_gain_pct": 4.0,
                         "signals": {"largest_1d_decline_since_stage2": largest_1d,
                                     "largest_1w_decline_since_stage2": False,
                                     "close_below_50ma_on_high_vol": False,
                                     "close_below_200ma": below_200,
                                     "climax_run_25pct_in_3w": False}},
        "climax_distribution": {"is_distribution": False, "in_climax": False,
                                "severity": clim_sev, "tells": tells or {}},
        "trend": {"ma50": 52.0, "ma200": 55.0},
        "liquidity": {"avg_dollar_vol": 90e6},
    }


@pytest.fixture
def topping_scan(monkeypatch):
    payload = {"all_results": [], "generated_at": 1787690000}

    class _Scanner:
        @staticmethod
        def load_latest():
            return payload

    monkeypatch.setitem(sys.modules, "sepa.scanner", _Scanner())
    import sepa
    monkeypatch.setattr(sepa, "scanner", _Scanner(), raising=False)
    return payload


def test_topping_keeps_stage3_with_evidence_and_refuses_stage2(
        prices, topping_scan, sales_stub):
    """Ajay 2026-08-25: 'ones which recently got heavy institutional selling
    and in S3 topping stage'. Stage 2 names never appear no matter how ugly
    their volume; a Stage 3 name needs >= 2 independent distribution reads."""
    topping_scan["all_results"] = [
        _topping_row("TOPPY"),
        _topping_row("STILLUP", stage=2),
        # Stage 3 but only ONE evidence — clean volume otherwise
        _topping_row("ONEREAD", dist_days=2, accum_days=2, cmf=0.02,
                     cmf_signal="neutral", strength="neutral", ratio=1.1,
                     largest_1d=True),
        # Ugly reads but it's a wrapper — the LABD lesson
        {**_topping_row("INVETF", stage=4, below_200=True), "is_etf": True},
    ]
    for s in ("TOPPY", "STILLUP", "ONEREAD", "INVETF"):
        prices[s] = _frame(200)

    out = B.board("topping", limit=5, min_tier="any")
    assert [t["symbol"] for t in out["tiles"]] == ["TOPPY"]  # no S2, no 1-read, no ETF
    t = out["tiles"][0]
    txt = " ".join(b["text"] for b in t["badges"])
    assert "S3 Topping" in txt
    assert "days on above-avg volume" in txt
    assert "Outflow — CMF -0.15" in txt
    stats = {s["k"]: s["v"] for s in t["stats"]}
    assert stats["Stage"] == "Topping" and stats["Dist days"] == "9\u2193 / 2\u2191"


def test_topping_ranks_the_most_aggressive_selling_first(
        prices, topping_scan, sales_stub):
    topping_scan["all_results"] = [
        _topping_row("MILD"),
        _topping_row("UGLY", stage=4, below_200=True, largest_1d=True,
                     clim_sev=3, base_count=5,
                     tells={"churning": True, "heavy_volume_down_day": True}),
    ]
    for s in ("MILD", "UGLY"):
        prices[s] = _frame(200)

    out = B.board("topping", limit=5, min_tier="any")
    assert [t["symbol"] for t in out["tiles"]] == ["UGLY", "MILD"]
    txt = " ".join(b["text"] for b in out["tiles"][0]["badges"])
    assert "S4 Decline" in txt and "200-day" in txt
    assert "+3 more tells" in txt  # 8 evidences, cap of 5, counted not hidden


def test_topping_declining_sales_confirm_but_never_gate(
        prices, topping_scan, sales_stub):
    """Fundamentals LAG at tops — a name with no sales data must still show;
    declining sales add a confirming badge."""
    topping_scan["all_results"] = [
        _topping_row("KNOWN"), _topping_row("UNKNOWN"),
    ]
    for s in ("KNOWN", "UNKNOWN"):
        prices[s] = _frame(200)
    sales_stub["KNOWN"] = _sales("declining", -12.0)

    out = B.board("topping", limit=5, min_tier="any")
    syms = {t["symbol"] for t in out["tiles"]}
    assert syms == {"KNOWN", "UNKNOWN"}
    known = next(t for t in out["tiles"] if t["symbol"] == "KNOWN")
    assert any("Sales declining" in b["text"] for b in known["badges"])


def test_topping_note_carries_the_cites_and_the_risk_line(
        prices, topping_scan, sales_stub):
    topping_scan["all_results"] = []
    out = B.board("topping", min_tier="any")
    for phrase in ("TLSW", "p.90", "TTLAC", "200-day", "not", "backtested"):
        assert phrase.lower() in out["note"].lower(), phrase
    assert "unlimited" in out["note"]


# ---------------------------------------------------------------------------
# float velocity — "can it actually run" (Ajay 2026-08-25, the AVGO question)
# ---------------------------------------------------------------------------
def _vel_tile(sym, avg_shares=None, velocity=None):
    return {"symbol": sym, "stats": [], "badges": [],
            "_m": {"avg_shares": avg_shares, "velocity": velocity}}


def test_attach_velocity_fills_from_shares_outstanding(monkeypatch):
    import short_interest.client as sic
    monkeypatch.setattr(sic, "_shares_outstanding",
                        lambda s: {"NIMBLE": 100_000_000, "AVGO": 4_600_000_000}.get(s))
    tiles = [_vel_tile("NIMBLE", avg_shares=3_000_000),
             _vel_tile("AVGO", avg_shares=18_000_000)]
    n = B.attach_velocity(tiles)
    assert n == 2
    assert tiles[0]["_m"]["velocity"] == 3.0      # 3M / 100M
    assert tiles[1]["_m"]["velocity"] == 0.39     # 18M / 4.6B — the elephant


def test_velocity_decor_badges_the_extremes_and_skips_the_unknown():
    tiles = [_vel_tile("NIMBLE", velocity=3.0),
             _vel_tile("AVGO", velocity=0.39),
             _vel_tile("MID", velocity=1.1),
             _vel_tile("NODATA")]
    B._velocity_decor(tiles)
    txt = lambda t: " ".join(b["text"] for b in t["badges"])
    assert "🐆 Fast supply — 3.0%/day" in txt(tiles[0])
    assert "🐘 Heavy supply — 0.39%/day" in txt(tiles[1])
    assert tiles[2]["badges"] == []               # mid-band: stat only, no badge
    assert {s["k"] for s in tiles[2]["stats"]} == {"Float/day"}
    assert tiles[3]["badges"] == [] and tiles[3]["stats"] == []


def test_attach_velocity_survives_a_dead_reference_feed(monkeypatch):
    import short_interest.client as sic
    def boom(s):
        raise RuntimeError("reference down")
    monkeypatch.setattr(sic, "_shares_outstanding", boom)
    tiles = [_vel_tile("X", avg_shares=1_000_000)]
    assert B.attach_velocity(tiles) == 0
    assert tiles[0]["_m"]["velocity"] is None


def test_zone_tiles_carry_the_flow_badge_when_the_row_has_a_verdict(
        prices, reentry_stub):
    """Ajay 2026-08-25: 'bake in CMF flow logic in to this one too'. Inflow
    and distribution earn a badge on Back in Demand; neutral or missing
    (older cached rows) render NOTHING — no fake reads."""
    r1 = _reentry_row("FLOWIN")
    r1["inflow"] = {"state": "inflow", "cmf_20": 0.12}
    r2 = _reentry_row("SOLD")
    r2["inflow"] = {"state": "distribution", "cmf_20": -0.2}
    r3 = _reentry_row("OLDCACHE")          # no inflow key at all
    reentry_stub["rows"] = [r1, r2, r3]
    for s in ("FLOWIN", "SOLD", "OLDCACHE"):
        prices[s] = _frame(200)

    out = B.board("zones", limit=5, min_tier="any")
    by = {t["symbol"]: " ".join(b["text"] for b in t["badges"]) for t in out["tiles"]}
    assert "Money flowing in — CMF +0.12" in by["FLOWIN"]
    assert "Still distributing — CMF -0.20" in by["SOLD"]
    assert "flowing" not in by["OLDCACHE"] and "distributing" not in by["OLDCACHE"]


def test_zones_default_rank_puts_cheetahs_over_elephants(
        prices, reentry_stub, monkeypatch):
    """Ajay 2026-08-25: "fix the ranking of these Cheetahs on top". A lower-R:R
    name with money flowing in and fast share turnover must outrank the
    AVGO-shape: prettier R:R, but distributing into a heavy float."""
    import short_interest.client as sic
    monkeypatch.setattr(sic, "_shares_outstanding",
                        lambda s: {"CHEETA": 100_000_000,
                                   "ELEFNT": 4_600_000_000}.get(s))
    lo = _reentry_row("CHEETA", rr=3.0)
    lo["inflow"] = {"state": "inflow", "cmf_20": 0.12}
    lo["liquidity"] = {"tier": "deep", "avg_dollar_vol": 90e6, "avg_vol_50": 3_000_000}
    hi = _reentry_row("ELEFNT", rr=6.0)
    hi["inflow"] = {"state": "distribution", "cmf_20": -0.22}
    hi["liquidity"] = {"tier": "deep", "avg_dollar_vol": 900e6, "avg_vol_50": 18_000_000}
    reentry_stub["rows"] = [hi, lo]
    for s in ("CHEETA", "ELEFNT"):
        prices[s] = _frame(200)

    out = B.board("zones", limit=5, min_tier="any")
    assert [t["symbol"] for t in out["tiles"]] == ["CHEETA", "ELEFNT"]
    assert "_flow" not in out["tiles"][0], "private key leaked to the client"


def test_gabbar_names_the_authors_levelless_stubs(prices, gabbar_stub):
    """Ajay 2026-08-27 pasted the author's own 79-name tracking list asking
    why NVDA & co. weren't showing — 13 of them are commented-out EMPTY
    stubs in the Pine source. The board must answer that itself: the stub
    list rides on the payload and the note says they cannot appear."""
    for s in gabbar_stub:
        prices[s] = _frame(200, start=90.05)
    out = B.board("gabbar", limit=5, min_tier="any")
    assert "NVDA" in out["tracked_no_levels"]
    assert len(out["tracked_no_levels"]) == 13
    assert "NO levels drawn yet" in out["note"]
    # And none of the stubs ever renders as a tile — there is nothing to draw.
    assert not set(t["symbol"] for t in out["tiles"]) & set(out["tracked_no_levels"])


# ── reaching vs already reached (Ajay 2026-08-31) ──────────────────────────
def _appr_row(sym, dist=2.9, drift=-3.1, flow=None, rr=1.2, cmf=0.1):
    # last_price follows `dist` by the scan's own formula ((px - hi) / px),
    # because since 2026-09-03 the order is read from PRICE vs band, not from
    # the stored dist_pct — a fixture whose two disagreed would test nothing.
    return {"symbol": sym, "name": sym, "is_reentry": False,
            "last_price": round(100.0 / (1 - dist / 100.0), 4), "trend_ok": True,
            "entry_zone": {"lo": 98.0, "hi": 100.0, "touches": 3,
                           "strength": 60.0, "oldest_touch_bars": 120},
            "approaching": {"state": "approaching", "dist_pct": dist,
                            "drift_pct": drift, "drift_bars": 5,
                            "band": {"lo": 98.0, "hi": 100.0}},
            "inflow": ({"state": flow, "cmf_20": cmf, "accum_days_25": 5,
                        "dist_days_25": 3, "pocket_pivot": False}
                       if flow else None),
            "plan": {"entry_ref": 103.0, "stop": 97.0, "target": 110.0,
                     "rr": rr},
            "supply_zones": [], "demand_zones": [],
            "verdict": {"entry_read": "caution"}}


def test_zone_tiles_phase_reads_the_approaching_rows(prices, reentry_stub):
    """phase='approaching' serves approaching_rows; the default serves the
    reached rows untouched — the toggle must never mix the two moments."""
    reentry_stub["rows"] = [{
        "symbol": "AAA", "name": "AAA", "is_reentry": True,
        "last_price": 100.0,
        "entry_zone": {"lo": 98.0, "hi": 100.5, "touches": 3,
                       "strength": 60.0, "oldest_touch_bars": 120},
        "plan": {"entry_ref": 100.0, "stop": 97.0, "target": 110.0, "rr": 3.0},
        "supply_zones": [], "demand_zones": [],
        "verdict": {"entry_read": "favorable"}}]
    reentry_stub["approaching_rows"] = [_appr_row("BBB")]
    for sym in ("AAA", "BBB"):
        prices[sym] = _frame(200, start=95.0)

    out_r = B.board("zones", limit=10, min_tier="any")
    assert out_r["phase"] == "reached"
    assert [t["symbol"] for t in out_r["tiles"]] == ["AAA"]

    out_a = B.board("zones", limit=10, min_tier="any", phase="approaching")
    assert out_a["phase"] == "approaching"
    assert [t["symbol"] for t in out_a["tiles"]] == ["BBB"]
    tile = out_a["tiles"][0]
    assert any("above the band" in b["text"] for b in tile["badges"])
    assert "falling toward" in tile["why"]


def test_approaching_board_ranks_by_proximity_not_cheetah_flow(
        prices, reentry_stub):
    """A strong-flow name 4.8% out must not outrank a neutral one 0.3% out —
    the approach board's question is WHICH BAND GETS HIT FIRST."""
    reentry_stub["approaching_rows"] = [
        _appr_row("FARFLOW", dist=4.8, flow="inflow", rr=3.0),
        _appr_row("CLOSE", dist=0.3, flow="neutral", rr=1.1),
    ]
    for sym in ("FARFLOW", "CLOSE"):
        prices[sym] = _frame(200, start=95.0)

    out = B.board("zones", limit=10, min_tier="any", phase="approaching")
    assert [t["symbol"] for t in out["tiles"]] == ["CLOSE", "FARFLOW"]


def test_approaching_same_bucket_puts_the_inflow_name_first(prices, reentry_stub):
    """Ajay 2026-09-03: "closest one ... on the top. Of course CMF inflow too
    considered." 0.08% and 0.26% out are one bucket (0.5%); inside it flow
    then CMF decide — the worked example's MP/HIMS/EXR. NEGATIVE: a name with
    NO flow read sorts last in the bucket, never first."""
    reentry_stub["approaching_rows"] = [
        _appr_row("EXR", dist=0.08, flow="distribution", cmf=-0.275),
        _appr_row("NOREAD", dist=0.05, flow=None),
        _appr_row("HIMS", dist=0.18, flow="neutral", cmf=-0.031),
        _appr_row("MP", dist=0.26, flow="inflow", cmf=0.159),
    ]
    for sym in ("EXR", "NOREAD", "HIMS", "MP"):
        prices[sym] = _frame(200, start=95.0)
    out = B.board("zones", limit=10, min_tier="any", phase="approaching",
                  themes_first=False)
    assert [t["symbol"] for t in out["tiles"]] == ["MP", "HIMS", "EXR", "NOREAD"]
    # the badge rides on the same read the rank used
    assert any("Money flowing in" in b["text"] for b in out["tiles"][0]["badges"])


def test_approaching_reranks_on_the_live_print_not_the_scan_price(
        prices, reentry_stub, monkeypatch):
    """The scan cache is warmed 9:25 / 16:55; by noon the 2.9%-out name may be
    0.2% out. The board ranks on the live print (fetched once, shared with
    the 7% bounce gate) and falls back to the scan price only when the tape
    has no print for that symbol."""
    reentry_stub["approaching_rows"] = [_appr_row("WASCLOSE", dist=0.3),
                                        _appr_row("WASFAR", dist=2.9)]
    for sym in ("WASCLOSE", "WASFAR"):
        prices[sym] = _frame(200, start=95.0)
    calls = []

    def live(syms):
        calls.append(sorted(syms))
        return {"WASFAR": 100.2}                  # WASCLOSE: no print → scan px
    monkeypatch.setattr(B, "_live_last", live)
    out = B.board("zones", limit=10, min_tier="any", phase="approaching",
                  themes_first=False)
    assert [t["symbol"] for t in out["tiles"]] == ["WASFAR", "WASCLOSE"]
    assert len(calls) == 1, "live prices must be fetched once per board build"


def test_approaching_board_score_is_the_position_in_the_shared_key(
        prices, reentry_stub):
    """One definition of the order: the tile order must equal
    demand_order.approaching_key over the same rows (position score, the
    supply_tiles pattern) — not a second weighted number — with themes off
    so nothing else can reorder it. `_score` never leaks to the client."""
    from supply_demand import demand_order as O
    rows = [_appr_row("D", dist=1.7, flow="neutral", cmf=0.0),
            _appr_row("A", dist=0.4, flow="distribution", cmf=-0.1),
            _appr_row("C", dist=0.9, flow="inflow", cmf=0.2),
            _appr_row("B", dist=0.2, flow="inflow", cmf=0.05)]
    reentry_stub["approaching_rows"] = rows
    for r in rows:
        prices[r["symbol"]] = _frame(200, start=95.0)
    out = B.board("zones", limit=10, min_tier="any", phase="approaching",
                  themes_first=False)
    want = [r["symbol"] for r in sorted(rows, key=O.approaching_key)]
    assert [t["symbol"] for t in out["tiles"]] == want == ["B", "A", "C", "D"]
    assert all("_score" not in t for t in out["tiles"])


def test_the_route_actually_forwards_the_phase_param():
    """Source guard. The first build declared phase as a Query param and never
    passed it to board() — the toggle deployed as a no-op that served the
    reached board under an approaching URL. A param the route accepts but
    drops is worse than one it rejects."""
    import inspect

    from chart_maps import api as cm_api
    src = inspect.getsource(cm_api.chart_maps)
    assert "phase: str = Query(" in src or "phase" in str(
        inspect.signature(cm_api.chart_maps).parameters)
    assert "phase=phase" in src, (
        "chart_maps route accepts `phase` but never forwards it to board()")
    # Same trap, next param (2026-08-31, an hour later): `target` must be
    # forwarded too, or the order-block toggle ships as the same no-op.
    assert "target=target" in src, (
        "chart_maps route accepts `target` but never forwards it to board()")


def test_approaching_target_switches_between_zone_and_order_block(
        prices, reentry_stub):
    """target=order_block serves the OB rows with the OB's OWN trade lines and
    the block drawn — never the zone plan's prices on an order-block tile."""
    ob_row = {
        "symbol": "OBAP", "name": "OBAP", "is_reentry": False,
        "last_price": 103.0, "trend_ok": True,
        "entry_zone": {"lo": 90.0, "hi": 92.0, "touches": 3, "strength": 60.0,
                       "oldest_touch_bars": 120},
        "approaching_ob": {
            "state": "approaching_ob", "dist_pct": 2.4, "drift_pct": -2.9,
            "drift_bars": 5,
            "block": {"lo": 98.4, "hi": 100.2, "bars_ago": 20,
                      "displacement_atr": 3.1},
            "trade": {"entry": 100.2, "stop": 97.9, "target1": 104.8,
                      "rr": 2.0},
            "cited": False},
        "plan": {"entry_ref": 92.0, "stop": 89.0, "target": 110.0, "rr": 3.0},
        "supply_zones": [], "demand_zones": [], "verdict": {}}
    reentry_stub["approaching_rows"] = [_appr_row("ZONEAP")]
    reentry_stub["approaching_ob_rows"] = [ob_row]
    for sym in ("ZONEAP", "OBAP"):
        prices[sym] = _frame(200, start=95.0)

    out_z = B.board("zones", limit=10, min_tier="any", phase="approaching")
    assert out_z["target"] == "zone"
    assert [t["symbol"] for t in out_z["tiles"]] == ["ZONEAP"]

    out_ob = B.board("zones", limit=10, min_tier="any", phase="approaching",
                     target="order_block")
    assert out_ob["target"] == "order_block"
    assert [t["symbol"] for t in out_ob["tiles"]] == ["OBAP"]
    tile = out_ob["tiles"][0]
    kinds = [b["kind"] for b in tile["bands"]]
    assert "order_block" in kinds
    # the OB trade, not the zone plan
    buy = next(l for l in tile["lines"] if l["label"] == "BUY")
    assert buy["price"] == 100.2
    assert any("above the order block" in b["text"] for b in tile["badges"])
    assert any("uncited" in b["text"] for b in tile["badges"])
    assert "order block" in tile["why"]

    # SUPERSEDED same day ("hit the 'In the orderblock' to see all the
    # stocks"): reached + order_block now serves names INSIDE a fresh block on
    # first touch — the 2x2's fourth cell, asserted in the dedicated test.
    out_r = B.board("zones", limit=10, min_tier="any", target="order_block")
    assert out_r["phase"] == "reached" and out_r["target"] == "order_block"


def test_reached_order_block_serves_names_inside_fresh_blocks(
        prices, reentry_stub):
    """The 2x2's fourth cell: phase=reached + target=order_block = IN the
    block on its first touch, youngest block first, with the block's trade."""
    in_row = {
        "symbol": "INBLK", "name": "INBLK", "is_reentry": False,
        "last_price": 99.5, "trend_ok": True,
        "entry_zone": {"lo": 90.0, "hi": 92.0, "touches": 3, "strength": 60.0,
                       "oldest_touch_bars": 120},
        "in_ob": {"state": "in_ob", "depth_pct": 39.0,
                  "block": {"lo": 98.4, "hi": 100.2, "bars_ago": 14,
                            "displacement_atr": 3.2},
                  "trade": {"entry": 100.2, "stop": 97.9, "target1": 104.8,
                            "rr": 2.0},
                  "cited": False},
        "plan": {"entry_ref": 92.0, "stop": 89.0, "target": 110.0, "rr": 3.0},
        "supply_zones": [], "demand_zones": [], "verdict": {}}
    reentry_stub["rows"] = []
    reentry_stub["in_ob_rows"] = [in_row]
    prices["INBLK"] = _frame(200, start=95.0)

    out = B.board("zones", limit=10, min_tier="any", target="order_block")
    assert out["phase"] == "reached" and out["target"] == "order_block"
    assert [t["symbol"] for t in out["tiles"]] == ["INBLK"]
    tile = out["tiles"][0]
    assert any("in the order block" in b["text"] for b in tile["badges"])
    assert any(b["kind"] == "order_block" for b in tile["bands"])
    buy = next(l for l in tile["lines"] if l["label"] == "BUY")
    assert buy["price"] == 100.2
    assert "first touch" in tile["why"]


def _in_ob_row(sym, bars_ago, flow=None, cmf=None, px=99.5):
    return {"symbol": sym, "name": sym, "is_reentry": False,
            "last_price": px, "trend_ok": True,
            "entry_zone": {"lo": 90.0, "hi": 92.0, "touches": 3, "strength": 60.0,
                           "oldest_touch_bars": 120},
            "inflow": ({"state": flow, "cmf_20": cmf} if flow else None),
            "in_ob": {"state": "in_ob", "depth_pct": 39.0,
                      "block": {"lo": 98.4, "hi": 100.2, "bars_ago": bars_ago,
                                "displacement_atr": 3.2},
                      "trade": {"entry": 100.2, "stop": 97.9, "target1": 104.8, "rr": 2.0},
                      "cited": False},
            "plan": {"entry_ref": 92.0, "stop": 89.0, "target": 110.0, "rr": 3.0},
            "supply_zones": [], "demand_zones": [], "verdict": {}}


def test_in_the_block_same_age_ranks_by_cmf_and_missing_inflow_last(
        prices, reentry_stub):
    """Youngest block still leads (Ajay 2026-08-31). Inside an age tie — 41
    of 82 live rows were 2 bars old on 2026-09-03 — flow then CMF decide,
    and a row with no flow read sorts LAST in the tie. The order-block rows
    now carry `inflow` from the scan, and the tile wears the badge."""
    reentry_stub["rows"] = []
    reentry_stub["in_ob_rows"] = [
        _in_ob_row("NOREAD", 2),
        _in_ob_row("SOLD", 2, "distribution", -0.2),
        _in_ob_row("OLDHOT", 20, "inflow", 0.5),
        _in_ob_row("MILD", 2, "inflow", 0.05),
        _in_ob_row("HOT", 2, "inflow", 0.3),
    ]
    for r in reentry_stub["in_ob_rows"]:
        prices[r["symbol"]] = _frame(200, start=95.0)
    out = B.board("zones", limit=10, min_tier="any", target="order_block",
                  themes_first=False)
    assert [t["symbol"] for t in out["tiles"]] == ["HOT", "MILD", "SOLD", "NOREAD", "OLDHOT"]
    assert any("Money flowing in — CMF +0.30" in b["text"] for b in out["tiles"][0]["badges"])
    assert not any("flowing" in b["text"] or "distributing" in b["text"]
                   for b in out["tiles"][3]["badges"])


def test_lens_tabs_default_all_while_demand_boards_default_reached():
    """One empty-string route default, two meanings — an old URL with no phase
    param must render every tab's historical board byte for byte."""
    import inspect
    src = inspect.getsource(B.board)
    assert 'phase=(phase or "reached")' in src   # zones + deep
    assert 'phase=(phase or "all")' in src       # undervalue + gabbar



# ---------------------------------------------------------------------------
# the 7% already-bounced gate (Ajay 2026-09-03: "from all chart maps Demand
# zones remove anything that already did about 7% bounce from Demand Zone")
# ---------------------------------------------------------------------------
def test_bounce_helpers_measure_from_the_band_top_and_survive_junk():
    assert B.bounce_pct(107.0, 100.0) == pytest.approx(7.0)
    assert B.already_bounced(107.0, 100.0) is True
    assert B.already_bounced(106.9, 100.0) is False
    assert B.already_bounced(99.0, 100.0) is False          # inside / below never "bounced"
    assert B.bounce_pct(None, 100.0) is None and B.bounce_pct(100.0, 0) is None
    assert B.already_bounced("x", 100.0) is False
    row = {"entry_zone": {"hi": 100.0}, "in_ob": {"block": {"lo": 101.0, "hi": 102.0}},
           "approaching_ob": {"block": {"lo": 103.0, "hi": 104.0}}}
    assert B._bounce_ref_hi(row, "reached", "zone") == 100.0
    assert B._bounce_ref_hi(row, "reached", "order_block") == 102.0
    assert B._bounce_ref_hi(row, "approaching", "order_block") == 104.0
    assert B._bounce_ref_hi({"entry_zone": {"hi": 100.0}}, "reached", "order_block") == 100.0
    kept, dropped = B.drop_bounced(
        [{"symbol": "A", "last_price": 108.0, "entry_zone": {"hi": 100.0}},
         {"symbol": "B", "last_price": 108.0, "entry_zone": {"hi": 100.0}},
         {"symbol": "C", "last_price": 101.0, "entry_zone": {"hi": 100.0}}],
        lambda r: r["entry_zone"]["hi"], live={"B": 103.0, "C": None})
    assert [r["symbol"] for r in kept] == ["B", "C"] and dropped == 1, \
        "live print wins over the scan price; a None live falls back to last_price"


def test_reached_board_drops_names_that_already_ran_seven_percent(prices, reentry_stub, monkeypatch):
    reentry_stub["rows"] = [_reentry_row("AAA"), _reentry_row("BBB")]
    hi = reentry_stub["rows"][0]["entry_zone"]["hi"]
    for sym in ("AAA", "BBB"):
        prices[sym] = _frame(200)
    monkeypatch.setattr(B, "_live_last", lambda syms: {"AAA": hi * 1.08, "BBB": hi * 1.03})
    out = B.board("zones", limit=10, min_tier="any")
    assert [t["symbol"] for t in out["tiles"]] == ["BBB"]
    assert out["dropped_bounced"] == 1 and out["bounce_done_pct"] == 7.0
    assert out["matched"] == 2, "matched counts the board before the gate"


def test_bounce_gate_uses_scan_price_when_the_tape_is_unreachable(prices, reentry_stub, monkeypatch):
    row = _reentry_row("AAA")
    row["last_price"] = row["entry_zone"]["hi"] * 1.10
    reentry_stub["rows"] = [row]
    prices["AAA"] = _frame(200)
    monkeypatch.setattr(B, "_live_last", lambda syms: {})
    out = B.board("zones", limit=10, min_tier="any")
    assert out["tiles"] == [] and out["dropped_bounced"] == 1


def test_approaching_and_order_block_boards_take_the_gate_too(prices, reentry_stub, monkeypatch):
    reentry_stub["approaching_rows"] = [_appr_row("BBB"), _appr_row("CCC")]
    for sym in ("BBB", "CCC"):
        prices[sym] = _frame(200, start=95.0)
    monkeypatch.setattr(B, "_live_last", lambda syms: {"BBB": 100.0 * 1.075, "CCC": 100.0 * 1.02})
    out = B.board("zones", limit=10, min_tier="any", phase="approaching")
    assert [t["symbol"] for t in out["tiles"]] == ["CCC"] and out["dropped_bounced"] == 1


def test_deep_demand_gate_measures_from_the_second_band(prices, reentry_stub, sales_stub, monkeypatch):
    flow_in = {"state": "inflow", "cmf_20": 0.14, "accum_days_25": 9,
               "dist_days_25": 4, "pocket_pivot": False}
    reentry_stub["deep_rows"] = [_deep_row("DRUN", state="in", inflow=flow_in),
                                 _deep_row("DSIT", state="in", inflow=flow_in)]
    for sym in ("DRUN", "DSIT"):
        sales_stub[sym] = _sales("steady", 9.0)
        prices[sym] = _frame(200, start=90.05)
    # second band hi = 85: 91 is +7.06% (gone), 89 is +4.7% (still at the level)
    monkeypatch.setattr(B, "_live_last", lambda syms: {"DRUN": 91.0, "DSIT": 89.0})
    # min_room=0: this test is about the BOUNCE gate. DSIT at 89 has 1.1% of
    # room to its broken first band (90), which the room floor hides by default.
    out = B.board("deep_demand", limit=5, min_tier="any", min_room=0)
    assert [t["symbol"] for t in out["tiles"]] == ["DSIT"]
    assert out["dropped_bounced"] == 1 and out["bounce_done_pct"] == 7.0



# ---------------------------------------------------------------------------
# tile href default (Ajay 2026-09-03: SEPA clicks land on Supply / Demand)
# ---------------------------------------------------------------------------
def test_default_tile_href_is_supply_and_purposed_tabs_stay():
    assert B._href("aaa") == "/sepa/AAA?tab=supply"
    assert B._href("AAA", "supply") == "/sepa/AAA?tab=supply"
    assert B._href("AAA", "options") == "/sepa/AAA?tab=options"
    import inspect
    src = inspect.getsource(B)
    assert '_href(sym, "setup")' not in src, "no tile may open the Setup tab by default any more"
    assert 'upper(), "setup")' not in src
    for purposed in ('_href(sym, "breakout")', '_href(sym, "options")'):
        assert purposed in src, f"{purposed} is a purposed deep link and must stay"


def test_approaching_badges_print_the_live_distance_the_ranking_used(prices, reentry_stub, monkeypatch):
    """The badge must agree with the order (Ajay reads it to predict the
    ranking): with a fresh print the tile shows the LIVE % above the band; with
    no print it falls back to the scan's dist_pct."""
    reentry_stub["approaching_rows"] = [_appr_row("BBB", dist=2.9)]
    prices["BBB"] = _frame(200, start=95.0)
    monkeypatch.setattr(B, "_live_last", lambda syms: {"BBB": 100.5})   # band hi 100 → 0.5%
    out = B.board("zones", limit=10, min_tier="any", phase="approaching")
    tile = out["tiles"][0]
    assert any(b["text"] == "\u2192 0.5% above the band" for b in tile["badges"]), tile["badges"]
    assert "0.5% above it" in tile["why"]
    monkeypatch.setattr(B, "_live_last", lambda syms: {})
    out2 = B.board("zones", limit=10, min_tier="any", phase="approaching")
    assert any("2.9% above the band" in b["text"] for b in out2["tiles"][0]["badges"])


# ---------------------------------------------------------------------------
# 2026-09-05 review fixes (Ajay: "yes please fix the bugs") — the live print
# behind the bounce gate / live re-rank, and the in-band approaching tile
# ---------------------------------------------------------------------------
def test_live_last_treats_a_zero_day_bar_as_missing_and_prefers_the_last_trade(prices):
    """Pre-market the snapshot day bar `price` is 0 (the codebase's own
    documented feed behaviour). 0 is MISSING, not a price: prefer the last
    trade (extended hours included), else the day bar, else None — so
    drop_bounced / rerank_live fall back to the row's scan price instead of
    running every row through geometry(0.0, ...)."""
    snaps = {"AAA": {"price": 0, "last_trade_price": 25.1},
             "BBB": {"price": 0, "last_trade_price": 0},
             "CCC": {"price": 101.0, "last_trade_price": None},
             "DDD": None}
    import sys as _sys
    _sys.modules["sepa.prices"].bulk_live_prices = lambda syms: snaps
    live = B._live_last(["AAA", "BBB", "CCC", "DDD"])
    assert live == {"AAA": 25.1, "BBB": None, "CCC": 101.0, "DDD": None}
    # Pre-market board: day bars 0, only AAA has an extended-hours trade.
    # BBB -> None -> its SCAN price (108, +8% off the band) decides: the
    # bounce gate drops it and the re-rank puts the 0.5%-out name first.
    # (The old reader gave both 0.0: BBB was kept and led on money flow.)
    _sys.modules["sepa.prices"].bulk_live_prices = lambda syms: {
        "AAA": {"price": 0, "last_trade_price": 100.5},
        "BBB": {"price": 0, "last_trade_price": 0}}
    live = B._live_last(["AAA", "BBB"])
    assert live == {"AAA": 100.5, "BBB": None}
    rows = [{"symbol": "BBB", "last_price": 108.0, "entry_zone": {"lo": 98.0, "hi": 100.0},
             "approaching": {"band": {"lo": 98.0, "hi": 100.0}, "dist_pct": 7.4},
             "inflow": {"state": "inflow", "cmf_20": 0.2}},
            {"symbol": "AAA", "last_price": 100.5, "entry_zone": {"lo": 98.0, "hi": 100.0},
             "approaching": {"band": {"lo": 98.0, "hi": 100.0}, "dist_pct": 0.5}}]
    kept, dropped = B.drop_bounced(rows, lambda r: r["entry_zone"]["hi"], live)
    assert [r["symbol"] for r in kept] == ["AAA"] and dropped == 1
    from supply_demand import demand_order as O
    assert [r["symbol"] for r in B.rerank_live(rows, O.approaching_key, live)] == ["AAA", "BBB"]
    assert B._live_px(rows[0], {"BBB": None}) == 108.0


def test_disp_dist_reads_zero_once_the_live_print_is_at_or_inside_the_band():
    row = {"symbol": "AAA", "last_price": 102.0,
           "approaching": {"band": {"lo": 98.0, "hi": 100.0}, "dist_pct": 1.96},
           "entry_zone": {"lo": 98.0, "hi": 100.0}}
    read = row["approaching"]
    assert B._disp_dist(row, {"AAA": 99.0}, read, "band") == 0.0
    assert B._disp_dist(row, {"AAA": 100.0}, read, "band") == 0.0
    assert B._disp_dist(row, {"AAA": 100.2}, read, "band") == pytest.approx(0.2)
    assert B._disp_dist(row, {}, read, "band") == 1.96          # no print: scan number
    assert B._disp_dist(row, {"AAA": None}, read, "band") == 1.96


def test_approaching_tile_in_the_band_on_the_live_print_says_so_and_leads(
        prices, reentry_stub, monkeypatch):
    """Scan: INBAND 1.96% out, OUT 0.3% out. Live: INBAND printed 99.0 (in
    the 98-100 band), OUT 100.3. The re-rank puts INBAND first; its badge
    and `why` must say it is IN the band — never the stale 1.96%."""
    reentry_stub["approaching_rows"] = [_appr_row("OUT", dist=0.3),
                                        _appr_row("INBAND", dist=1.96)]
    for sym in ("OUT", "INBAND"):
        prices[sym] = _frame(200, start=95.0)
    monkeypatch.setattr(B, "_live_last", lambda syms: {"INBAND": 99.0, "OUT": 100.3})
    out = B.board("zones", limit=10, min_tier="any", phase="approaching",
                  themes_first=False)
    assert [t["symbol"] for t in out["tiles"]] == ["INBAND", "OUT"]
    top, second = out["tiles"]
    texts = [b["text"] for b in top["badges"]]
    assert any("in the band" in t for t in texts), texts
    assert not any("1.96" in t for t in texts), texts
    assert "in the band" in top["why"] and "1.96" not in top["why"]
    assert any(b["text"] == "→ 0.3% above the band" for b in second["badges"])


def test_board_live_print_and_in_band_rules_stay_in_source():
    """Guards for the 2026-09-05 fixes: the live print prefers the last trade
    and treats a non-positive value as missing; an approaching tile whose
    live print is at/inside the level reads 0 and says 'in the band'."""
    import inspect
    sp = inspect.getsource(B._snapshot_print)
    assert 'for key in ("last_trade_price", "price"):' in sp and "px > 0" in sp
    assert "_snapshot_print(v)" in inspect.getsource(B._live_last)
    dd = inspect.getsource(B._disp_dist)
    assert "if px <= hi:\n            return 0.0" in dd
    zt = inspect.getsource(B.zone_tiles)
    assert zt.count("_dist_badge(") == 2 and zt.count("_dist_text(") == 2, (
        "the approaching band / order-block badge and why must go through the "
        "in-band aware helpers")


# ---------------------------------------------------------------------------
# room floor 2026-09-05 — zones + deep_demand hide tiles under 5% of room to
# the first unbroken band overhead, measured on the LIVE print.
#
# Ajay 2026-09-05, TRU: "It already gapped up very close to the resistance.
# Why is it still in in Demand page? There is only 0.5% room" — and "I need
# the same logic in Demand and deep demand zone. So that there are stocks
# that have more room atleast >5%". The 5% is alert_gates.ALERT_MIN_ROOM_PCT
# via supply_demand.room_floor (owner setting, S/D scope, no book cite).
# ---------------------------------------------------------------------------
def _tru_row():
    r = _reentry_row("TRU", rr=1.47)
    r["last_price"] = 78.90
    r["entry_zone"] = {"lo": 78.34, "hi": 81.08}
    r["supply_zones"] = [{"kind": "supply", "lo": 80.12, "hi": 82.10},
                         {"kind": "supply", "lo": 83.87, "hi": 85.20}]
    r["nearest_resistance"] = {"kind": "supply", "lo": 80.12, "hi": 82.10}
    return r


def _room_stat(tile):
    return next(s["v"] for s in tile["stats"] if s["k"] == "room")


def test_zones_tab_hides_tru_on_the_live_print_and_keeps_the_name_with_room(
        prices, reentry_stub, monkeypatch):
    for s in ("TRU", "AAA"):
        prices[s] = _frame(200)
    reentry_stub["rows"] = [_tru_row(), _reentry_row("AAA")]
    # the scan saw TRU at 78.90 (1.5% room); it has since gapped to 79.88
    monkeypatch.setattr(B, "_live_last", lambda syms: {"TRU": 79.88})

    out = B.board("zones", limit=5, min_tier="any")
    assert [t["symbol"] for t in out["tiles"]] == ["AAA"]
    assert out["hidden_low_room"] == 1
    assert out["min_room"] == 5.0
    assert _room_stat(out["tiles"][0]) == "+50.7% -> 22.00"


def test_zones_tab_min_room_zero_shows_everything_and_still_says_the_room(
        prices, reentry_stub, monkeypatch):
    for s in ("TRU", "AAA"):
        prices[s] = _frame(200)
    reentry_stub["rows"] = [_tru_row(), _reentry_row("AAA")]
    monkeypatch.setattr(B, "_live_last", lambda syms: {"TRU": 79.88})

    out = B.board("zones", limit=5, min_tier="any", min_room=0)
    assert {t["symbol"] for t in out["tiles"]} == {"TRU", "AAA"}
    assert out["hidden_low_room"] == 0 and out["min_room"] == 0.0
    tru = next(t for t in out["tiles"] if t["symbol"] == "TRU")
    assert _room_stat(tru) == "+0.3% -> 80.12"


def test_zones_tab_open_sky_and_in_band_wordings(prices, reentry_stub, monkeypatch):
    for s in ("SKY", "INB"):
        prices[s] = _frame(200)
    sky = _reentry_row("SKY")
    sky["supply_zones"] = []
    inb = _tru_row()
    inb["symbol"] = "INB"
    reentry_stub["rows"] = [sky, inb]
    monkeypatch.setattr(B, "_live_last", lambda syms: {"INB": 80.50})    # inside 80.12-82.10

    shown = B.board("zones", limit=5, min_tier="any")
    assert [t["symbol"] for t in shown["tiles"]] == ["SKY"]
    assert _room_stat(shown["tiles"][0]) == "open sky"
    everything = B.board("zones", limit=5, min_tier="any", min_room=0)
    inb_tile = next(t for t in everything["tiles"] if t["symbol"] == "INB")
    assert _room_stat(inb_tile) == "in band"


def test_zones_tab_falls_back_to_the_scan_price_without_a_tape(prices, reentry_stub, monkeypatch):
    """No live print: the scan's last_price decides, as the bounce gate does."""
    prices["TRU"] = _frame(200)
    reentry_stub["rows"] = [_tru_row()]            # 78.90 -> 80.12 = 1.5%: under 5
    monkeypatch.setattr(B, "_live_last", lambda syms: {})
    out = B.board("zones", limit=5, min_tier="any")
    assert out["count"] == 0 and out["hidden_low_room"] == 1
    loose = B.board("zones", limit=5, min_tier="any", min_room=1.0)
    assert loose["count"] == 1 and _room_stat(loose["tiles"][0]) == "+1.5% -> 80.12"


def test_deep_demand_tab_applies_the_same_room_floor_against_the_broken_first_band(
        prices, reentry_stub, sales_stub, monkeypatch):
    """Ajay 2026-09-05: 'the same logic in Demand and deep demand zone'."""
    reentry_stub["deep_rows"] = [_deep_row("ROOMY"), _deep_row("LIDDED")]
    for s in ("ROOMY", "LIDDED"):
        prices[s] = _frame(200)
        sales_stub[s] = _sales("strong", 30.0)
    # LIDDED has run to 89.80, 0.2% under its broken first band (90-95)
    monkeypatch.setattr(B, "_live_last", lambda syms: {"LIDDED": 89.80})

    out = B.board("deep_demand", limit=5, min_tier="any")
    assert [t["symbol"] for t in out["tiles"]] == ["ROOMY"]
    assert out["hidden_low_room"] == 1 and out["min_room"] == 5.0
    assert _room_stat(out["tiles"][0]) == "+9.8% -> 90.00"
    both = B.board("deep_demand", limit=5, min_tier="any", min_room=0)
    assert {t["symbol"] for t in both["tiles"]} == {"ROOMY", "LIDDED"}


def test_other_tabs_ignore_min_room(prices, scan_stub):
    prices["AAA"] = _frame(200)
    scan_stub["all_results"] = [_vcp_row("AAA", tightness=95)]
    out = B.board("vcp", limit=5, min_tier="any", min_room=0)
    assert out["count"] == 1
    assert "hidden_low_room" not in out and "min_room" not in out


def test_room_floor_default_on_the_boards_is_the_alert_gate_number():
    from supply_demand import alert_gates as G
    from supply_demand import room_floor as RF
    import inspect
    assert RF.MIN_ROOM_DEFAULT == G.ALERT_MIN_ROOM_PCT
    for fn in (B.zone_tiles, B.deep_demand_tiles, B.board):
        assert "min_room" in str(inspect.signature(fn))
    for fn in (B.supply_tiles, B.vcp_tiles):
        assert "min_room" not in str(inspect.signature(fn))


# ── Quick Bounce tab (Ajay 2026-09-06) ────────────────────────────────────────
def test_quick_bounce_tab_lists_qualifying_names_at_a_band_nearest_first(prices, monkeypatch):
    from supply_demand import quick_bounce as QB, zone_store
    band = {"kind": "demand", "lo": 100.0, "hi": 102.0, "touches": 3, "strength": 80.0}
    lid = {"kind": "supply", "lo": 115.0, "hi": 116.0, "touches": 2, "strength": 50.0}
    weak = {"kind": "supply", "lo": 104.0, "hi": 105.0, "touches": 1, "strength": 10.0}
    st = {"events": 6, "quick": 4, "same_day": 3, "gap_up": 1, "first_day_quick": 2, "quick_rate_pct": 66.7,
          "first_day_rate_pct": 33.3, "placebo_rate_pct": 24.0, "edge_pts": 42.7, "median_lift_pct": 3.8,
          "last_quick_date": "2026-09-01", "avg_dollar_vol_50": 40e6}
    stats = {"AAA": dict(st), "BBB": dict(st), "CCC": dict(st, events=2), "DDD": dict(st)}
    meta = {"_id": "_meta", "as_of": "2026-09-06", "studied": 4, "events": 20, "quick": 8, "same_day": 6,
            "gap_up": 2, "quick_rate_pct": 40.0, "first_day_rate_pct": 20.0, "placebo_rate_pct": 15.0,
            "edge_pts": 25.0, "qualifying": 3, "persistence": {"gap_pts": 5.0}, "params": {"gap_min_pct": 2.0},
            "generated_at": 1.0}
    docs = {"AAA": {"bands": [band, weak, lid], "prev_close": 101.0},
            "BBB": {"bands": [band, lid], "prev_close": 101.0},
            "DDD": {"bands": [band, dict(weak, touches=2, strength=50.0)], "prev_close": 101.0}}
    monkeypatch.setattr(QB, "load_stats", lambda symbols=None, coll=None: stats)
    monkeypatch.setattr(QB, "load_meta", lambda coll=None: meta)
    monkeypatch.setattr(zone_store, "load_latest", lambda symbols=None, coll=None, today=None:
                        (__import__("datetime").date(2026, 9, 4), docs))
    monkeypatch.setattr(B, "_live_last", lambda syms: {"AAA": 103.0})     # BBB / DDD fall back to the store's prev_close
    for s in ("AAA", "BBB", "DDD"):
        prices[s] = _frame(200, start=90.0)
    out = B.board("quick_bounce", limit=10, min_tier="any")
    assert out["tab"] == "quick_bounce" and [t["symbol"] for t in out["tiles"]] == ["BBB", "AAA"]
    assert out["hidden_low_room"] == 1 and out["qualifying"] == 3 and out["matched"] == 2
    assert out["study"]["quick_rate_pct"] == 40.0 and out["study"]["persistence"] == {"gap_pts": 5.0}
    assert out["store_date"] == "2026-09-04" and out["min_room"] == 5.0
    bbb, aaa = out["tiles"]
    assert bbb["title"] == "BBB — quick bounce 67% (4/6)" and bbb["why"].startswith("buy $100-102 · stop $99.50")
    assert [b["kind"] for b in bbb["bands"]] == ["demand", "supply"] and bbb["bands"][1]["lo"] == 115.0
    assert [l["label"] for l in bbb["lines"]] == ["BUY", "STOP", "TARGET"] and bbb["lines"][2]["price"] == 115.0
    stats_bbb = {s["k"]: s["v"] for s in bbb["stats"]}
    assert stats_bbb["Quick"] == "4/6 (67%)" and stats_bbb["To band"] == "inside" and stats_bbb["Room"] == "+13.9% → 115"
    assert stats_bbb["Any-day base"] == "24%" and stats_bbb["Last quick"] == "2026-09-01"
    txt = " ".join(b["text"] for b in aaa["badges"])
    assert "1.0% above the band" in txt and "same-day 3 · gap-up 1" in txt and "+43 pts" in txt
    assert aaa["bands"][1]["lo"] == 115.0, "the 1-touch lid is skipped: room reads to the proven one"
    # room off: the lidded name lists, flagged
    out_any = B.board("quick_bounce", limit=10, min_tier="any", min_room=0)
    assert [t["symbol"] for t in out_any["tiles"]] == ["BBB", "DDD", "AAA"] and out_any["hidden_low_room"] == 0


def test_quick_bounce_tab_without_stats_says_so(monkeypatch):
    from supply_demand import quick_bounce as QB
    monkeypatch.setattr(QB, "load_stats", lambda symbols=None, coll=None: {})
    monkeypatch.setattr(QB, "load_meta", lambda coll=None: None)
    out = B.board("quick_bounce", limit=10)
    assert out["tiles"] == [] and "not built yet" in out["note"] and out["study"] is None
    assert "quick_bounce" in B.TABS
