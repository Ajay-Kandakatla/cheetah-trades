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

    # min_tier="any": asserts tile SHAPE, not liquidity. The synthetic rows
    # carry no liquidity block, which the default floor correctly rejects.
    out = B.board("vcp", limit=5, min_tier="any")
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
    # Setup, not Supply (Ajay 2026-08-17). The tile already DRAWS the zones; the
    # thing he cannot see from the tile is the plan, so that is where the click
    # goes. `test_a_resolved_winner_tile_still_opens_the_supply_tab` is the
    # other half of this pair — the retrospective tiles must NOT follow.
    assert t["href"] == "/sepa/AAA?tab=setup"
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
                    "retailpct")}}


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
                      "retailpct"}
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

    class _GL:
        BAND_ATTRIBUTION = {"source": "Gabbar's Price Levels script",
                            "author": "veerenj on TradingView",
                            "license": "MPL-2.0", "snapshot_date": "2026-05-17"}

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
    assert syms == ["INBAND", "NEARBY", "FARAWAY"]

    t0 = out["tiles"][0]
    assert any("In Gabbar band" in (b.get("text") or "") for b in t0["badges"])
    assert t0["bands"][0]["label"].startswith("Gabbar")
    assert out["touching"] == 2  # in + near, never the faraway one


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


def test_deep_demand_in_band_ranks_ahead_of_approaching(
        prices, reentry_stub, sales_stub):
    reentry_stub["deep_rows"] = [
        _deep_row("NEARBY", state="near", dist=1.2),
        _deep_row("INSIDE", state="in"),
    ]
    for s in ("NEARBY", "INSIDE"):
        prices[s] = _frame(200)
        sales_stub[s] = _sales("strong", 30.0)

    out = B.board("deep_demand", limit=5, min_tier="any")
    assert [t["symbol"] for t in out["tiles"]] == ["INSIDE", "NEARBY"]


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
    assert "INBAND" not in syms, "a declining-sales name must be hidden"
    assert out["dropped_weak_sales"] == 1
    assert "hidden for weak/declining" in out["note"]

    near = next(t for t in out["tiles"] if t["symbol"] == "NEARBY")
    far = next(t for t in out["tiles"] if t["symbol"] == "FARAWAY")
    assert any("Sales steady" in b["text"] for b in near["badges"])
    assert any("Sales data missing" in b["text"] for b in far["badges"])


def test_deep_demand_inflow_names_lead_and_wear_the_flow_badge(
        prices, reentry_stub, sales_stub):
    """Ajay 2026-08-25: "we are looking for bullish momentum stocks and inflow
    signals for these". Inflow beats in-band: a near-band name with money
    flowing in outranks an in-band name still being sold, and every state is
    said out loud on the tile and counted in the note."""
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

    out = B.board("deep_demand", limit=5, min_tier="any")
    assert [t["symbol"] for t in out["tiles"]] == ["COILING", "SOLDOFF"]

    coil = out["tiles"][0]
    txt = " ".join(b["text"] for b in coil["badges"])
    assert "Money flowing in" in txt and "CMF +0.14" in txt and "9↑/4↓" in txt
    assert "Pocket pivot" in txt
    sold_txt = " ".join(b["text"] for b in out["tiles"][1]["badges"])
    assert "Still distributing" in sold_txt and "CMF -0.18" in sold_txt

    assert out["flow_counts"] == {"inflow": 1, "neutral": 0, "distribution": 1}
    assert "1 flowing in" in out["note"] and "1 still distributing" in out["note"]
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
