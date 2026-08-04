"""Coverage fixes from the 2026-07-06 stale-watchlist incident (AMBA/CRWV
served 5-week-old SOIR): the always-include universe merge, the 24h
self-heal staleness rule, and the GEX-history slim row. Negative cases
included per Rule #6 (empty sources, undated rows, missing chains)."""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from options.api import _soir_row_is_stale, SOIR_STALE_HOURS
from options.gex_history import slim_row
from options import scanner as soir_scanner


# ── universe: portfolio + file-watchlist always included ────────────────────
# portfolio.store uses py3.10 `X | None` annotations, so the local py3.9 venv
# can't import the real module (prod containers are 3.11 — fine there). The
# scanner imports it lazily inside the function, so we inject a fake module.
import types


class _FakeHoldings:
    def distinct(self, field):
        assert field == "ticker"
        return ["amba", "CRWV", ""]


class _FakeDb:
    portfolio_holdings = _FakeHoldings()


def _install_fake_portfolio(monkeypatch, get_db):
    pkg = types.ModuleType("portfolio")
    store = types.ModuleType("portfolio.store")
    store._get_db = get_db
    pkg.store = store
    monkeypatch.setitem(sys.modules, "portfolio", pkg)
    monkeypatch.setitem(sys.modules, "portfolio.store", store)


def test_always_include_merges_portfolio_and_file_watchlist(monkeypatch):
    import sepa.scanner as sscanner
    _install_fake_portfolio(monkeypatch, lambda: _FakeDb())
    monkeypatch.setattr(sscanner, "load_watchlist",
                        lambda: [{"symbol": "mksi"}, {"symbol": None}, {}])
    syms = soir_scanner._always_include_symbols()
    assert "AMBA" in syms and "CRWV" in syms and "MKSI" in syms
    assert "" not in syms


def test_always_include_survives_dead_sources(monkeypatch):
    import sepa.scanner as sscanner
    _install_fake_portfolio(monkeypatch, lambda: None)
    monkeypatch.setattr(sscanner, "load_watchlist",
                        lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert soir_scanner._always_include_symbols() == []


def test_build_universe_contains_always_include(monkeypatch):
    _install_fake_portfolio(monkeypatch, lambda: _FakeDb())
    universe = soir_scanner._build_universe(mode="curated", max_size=5000)
    syms = {t for t, _ in universe}
    assert "AMBA" in syms and "CRWV" in syms


# ── SOIR staleness rule ──────────────────────────────────────────────────────
NOW = datetime(2026, 7, 6, 15, 0)


def test_fresh_row_is_not_stale():
    row = {"scanned_at": NOW - timedelta(hours=2)}
    assert _soir_row_is_stale(row, now=NOW) is False


def test_old_row_is_stale():
    row = {"scanned_at": NOW - timedelta(hours=SOIR_STALE_HOURS + 1)}
    assert _soir_row_is_stale(row, now=NOW) is True


def test_undated_or_garbage_row_is_stale():
    assert _soir_row_is_stale({}, now=NOW) is True
    assert _soir_row_is_stale({"scanned_at": "not-a-date"}, now=NOW) is True


def test_iso_string_timestamps_parse():
    row = {"scanned_at": (NOW - timedelta(hours=1)).isoformat()}
    assert _soir_row_is_stale(row, now=NOW) is False


# ── GEX slim row ─────────────────────────────────────────────────────────────
def test_slim_row_maps_the_opex_payload():
    out = {"spot": 795.25, "expiration_date": "2026-07-17",
           "gex_reliability": "single_name",
           "gamma": {"regime": "pinning", "net_gex_dollars": 400000,
                     "put_wall": 790, "call_wall": 1100},
           "max_pain": {"max_pain_strike": 850, "pct_from_spot": 6.9}}
    row = slim_row("mu", out, "2026-07-06")
    assert row["symbol"] == "MU" and row["date_et"] == "2026-07-06"
    assert row["regime"] == "pinning" and row["max_pain"] == 850
    assert row["mp_pct_from_spot"] == 6.9 and row["call_wall"] == 1100


def test_slim_row_no_chain_records_nothing():
    assert slim_row("XXXX", None, "2026-07-06") is None


def test_slim_row_missing_gamma_still_keeps_max_pain():
    out = {"spot": 50.0, "gamma": None,
           "max_pain": {"max_pain_strike": 48, "pct_from_spot": -4.0}}
    row = slim_row("abc", out, "2026-07-06")
    assert row["regime"] is None and row["max_pain"] == 48


# ── GEX board (2026-07-17): bucket + slim_row flip/vex fields ────────────────

def test_slim_row_carries_flip_and_vex_none_safe():
    from options.gex_history import slim_row
    full = slim_row("mu", {
        "spot": 100.0, "gex_reliability": "single_name",
        "expiration_date": "2026-07-24",
        "gamma": {"regime": "pinning", "net_gex_dollars": 1e8,
                  "call_wall": 110.0, "put_wall": 90.0,
                  "flip_strike": 96.5, "magnet_strike": 100.0},
        "max_pain": {"max_pain_strike": 100.0, "pct_from_spot": 0.0},
        "vex": {"net_vex_dollars": 2e7, "read": "falling IV = dealer buying (vanna tailwind)"},
    }, "2026-07-17")
    assert full["flip_strike"] == 96.5 and full["magnet"] == 100.0
    assert full["net_vex_dollars"] == 2e7 and "tailwind" in full["vex_read"]

    legacy = slim_row("mu", {
        "spot": 100.0, "gamma": {"regime": "pinning", "net_gex_dollars": 1e8},
        "max_pain": {},
    }, "2026-07-17")
    assert legacy["flip_strike"] is None and legacy["net_vex_dollars"] is None


def test_board_bucket_rules():
    from options.gex_history import board_bucket
    assert board_bucket({"regime": "pinning", "spot": 100, "flip_strike": 95}) == "bullish"
    assert board_bucket({"regime": "pinning", "spot": 100, "flip_strike": None}) == "bullish"
    assert board_bucket({"regime": "amplifying", "spot": 100, "flip_strike": 105}) == "bearish"
    assert board_bucket({"regime": "amplifying", "spot": 100, "flip_strike": None}) == "bearish"
    assert board_bucket({"regime": "pinning", "spot": 100, "flip_strike": 105}) == "mixed"
    assert board_bucket({"regime": "amplifying", "spot": 100, "flip_strike": 95}) == "mixed"
    assert board_bucket({"regime": None, "spot": None, "flip_strike": None}) == "mixed"


def test_board_reads_latest_date_and_sorts_by_abs_gex(monkeypatch):
    from options import gex_history as GH

    class FakeColl:
        def __init__(self, rows):
            self.rows = rows

        def distinct(self, field):
            return sorted({r[field] for r in self.rows})

        def find(self, q, proj=None):
            return [dict(r) for r in self.rows if r["date_et"] == q["date_et"]]

    rows = [
        {"symbol": "OLD", "date_et": "2026-07-16", "regime": "pinning",
         "spot": 50, "flip_strike": None, "net_gex_dollars": 1e9},
        {"symbol": "LEGACY", "date_et": "2026-07-17", "regime": "pinning",
         "spot": 100, "net_gex_dollars": 3e8},
        {"symbol": "BIG", "date_et": "2026-07-17", "regime": "pinning",
         "spot": 100, "flip_strike": 95.0, "net_gex_dollars": 5e8},
        {"symbol": "SML", "date_et": "2026-07-17", "regime": "pinning",
         "spot": 100, "flip_strike": 95.0, "net_gex_dollars": 1e8},
        {"symbol": "BEAR", "date_et": "2026-07-17", "regime": "amplifying",
         "spot": 100, "flip_strike": 110.0, "net_gex_dollars": -9e8},
        {"symbol": "NOFLIP", "date_et": "2026-07-17", "regime": "pinning",
         "spot": 100, "flip_strike": None, "net_gex_dollars": 2e8},
    ]
    monkeypatch.setattr(GH, "_coll", lambda: FakeColl(rows))
    b = GH.board()
    assert b["as_of_date"] == "2026-07-17"
    assert [r["symbol"] for r in b["bullish"]] == ["BIG", "LEGACY", "NOFLIP", "SML"]
    assert [r["symbol"] for r in b["bearish"]] == ["BEAR"]
    assert b["counts"] == {"bullish": 4, "bearish": 1, "mixed": 0}
    # Only LEGACY (key absent) counts as legacy — NOFLIP's explicit None is a
    # legitimate one-sided profile, not a stale row.
    assert "1 of 5" in (b["note"] or "")

    monkeypatch.setattr(GH, "_coll", lambda: None)
    assert GH.board()["note"] == "mongo unavailable"


# ── Board universe: movers + add-ticker (2026-08-03 PLTR/SNAP gap) ───────────

def test_top_movers_threshold_ordering_and_garbage():
    from options.gex_history import top_movers
    rows = [
        {"symbol": "UP9", "day_change_pct": 9.0},
        {"symbol": "DN12", "day_change_pct": -12.0},
        {"symbol": "FLAT", "day_change_pct": 1.0},
        {"symbol": "EDGE", "day_change_pct": 4.0},
        {"symbol": "JUNK", "day_change_pct": "n/a"},
        {"symbol": "", "day_change_pct": 8.0},
        {"symbol": "NONE", "day_change_pct": None},
    ]
    assert top_movers(rows) == ["DN12", "UP9", "EDGE"]
    assert top_movers(rows, n=1) == ["DN12"]
    assert top_movers([]) == []
    assert top_movers(None) == []


def test_add_symbol_upserts_todays_row_with_bucket(monkeypatch):
    from options import gex_history as GH

    class FakeColl:
        def __init__(self):
            self.upserts = []

        def update_one(self, q, update, upsert=False):
            self.upserts.append((q, update["$set"]))

    coll = FakeColl()
    monkeypatch.setattr(GH, "_coll", lambda: coll)
    monkeypatch.setattr(GH, "_et_date", lambda: "2026-08-03")
    import options.opex as OP
    monkeypatch.setattr(OP, "compute_opex", lambda s: {
        "spot": 100.0, "gex_reliability": "single_name",
        "expiration_date": "2026-08-07",
        "gamma": {"regime": "pinning", "net_gex_dollars": 1e8,
                  "flip_strike": 95.0},
        "max_pain": {}, "vex": {"net_vex_dollars": 1e6, "read": "x"},
    })
    row = GH.add_symbol(" pltr ")
    assert row["symbol"] == "PLTR" and row["bucket"] == "bullish"
    assert coll.upserts[0][0] == {"_id": "PLTR:2026-08-03"}

    monkeypatch.setattr(OP, "compute_opex", lambda s: None)
    assert GH.add_symbol("ZZZX") is None
    assert GH.add_symbol("") is None
