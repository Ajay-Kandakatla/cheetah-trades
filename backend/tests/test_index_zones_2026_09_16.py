"""SPY / QQQ index zones — the pinned strip on the Back in Demand tab.

Ajay 2026-09-16: *"Can you create a SPY demand and supply zone please for me?
and also QQQ supply and demand zone and keep them always in the in demand zone
page. I need everything calculation overnight."*

Everything here is PURE: hand-built `zone_store` docs, a fake collection, and
the board driven through its existing stubs. No Mongo, no provider, no network.

The fixtures are the REAL 2026-09-16 structure read out of the live store, so
these tests pin the two reads Ajay will actually be looking at: SPY standing
INSIDE a supply band with a demand band two ticks above it, and QQQ standing
inside a demand band with supply 2.46% overhead.

The negatives carry the weight — a cold store, an empty doc, a None doc,
garbage geometry, a zero close, a dead tape, a raising index read — because the
strip is PINNED: it has to render something honest in every one of those, and
it must never be able to take the board down with it.
"""
from __future__ import annotations

import ast
import inspect
import re
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import index_zones as IZ     # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# the real 2026-09-16 structure, as zone_store stores it
# ---------------------------------------------------------------------------
def _doc(symbol, close, atr14, high_252, bands, as_of="2026-09-16",
         stored="2026-09-16"):
    return {"_id": f"{symbol}:{stored}", "symbol": symbol, "date": stored,
            "geom": "board",
            "bands": [{"kind": k, "lo": lo, "hi": hi, "touches": t,
                       "strength": s} for (k, lo, hi, t, s) in bands],
            "atr14": atr14, "prev_close": close, "high_252": high_252,
            "recent": [{"date": as_of, "low": close - 1.0, "high": close + 1.0,
                        "close": close}],
            "feat": None, "computed_at": "2026-09-16T04:20:00-04:00"}


SPY_BANDS = [("supply", 749.53, 779.37, 7, 75.0),
             ("demand", 759.48, 762.04, 2, 21.0),
             ("demand", 716.58, 739.51, 5, 63.0),
             ("supply", 696.09, 697.84, 4, 52.0),
             ("supply", 667.34, 693.68, 7, 97.0),
             ("demand", 661.21, 679.82, 6, 93.0),
             ("demand", 629.28, 654.40, 4, 67.0)]
QQQ_BANDS = [("supply", 721.89, 748.65, 8, 74.0),
             ("demand", 695.25, 704.66, 5, 48.0),
             ("demand", 661.14, 686.37, 2, 25.0),
             ("supply", 629.21, 637.01, 4, 44.0),
             ("supply", 602.87, 625.51, 6, 68.0),
             ("demand", 607.05, 610.15, 2, 25.0),
             ("demand", 580.74, 600.28, 7, 94.0),
             ("demand", 545.88, 565.32, 1, 12.0)]


def spy_doc():
    return _doc("SPY", 757.39, 5.86, 779.37, SPY_BANDS)


def qqq_doc():
    return _doc("QQQ", 704.54, 7.76, 748.65, QQQ_BANDS)


class FakeColl:
    """The two calls index_zones makes on a collection, nothing more."""

    def __init__(self, docs=None):
        self.docs = dict(docs or {})
        self.writes = 0
        self.deleted = 0

    def find_one(self, q, sort=None):
        lte = ((q or {}).get("date") or {}).get("$lte")
        rows = [d for d in self.docs.values()
                if lte is None or str(d.get("date")) <= str(lte)]
        if not rows:
            return None
        return sorted(rows, key=lambda d: str(d.get("date")))[-1]

    def replace_one(self, q, doc, upsert=False):
        self.writes += 1
        self.docs[q["_id"]] = dict(doc)

    def delete_many(self, q):
        self.deleted += 1

        class _R:
            deleted_count = 0
        return _R()


class BrokenColl:
    def find_one(self, *a, **kw):
        raise RuntimeError("mongo down")

    def replace_one(self, *a, **kw):
        raise RuntimeError("mongo down")

    def delete_many(self, *a, **kw):
        raise RuntimeError("mongo down")


# ---------------------------------------------------------------------------
# read_doc — the pure read
# ---------------------------------------------------------------------------
def test_bands_come_back_high_to_low_with_the_right_side_and_distance():
    r = IZ.read_doc("SPY", spy_doc(), name="SPDR S&P 500")
    assert r["available"] is True
    mids = [b["mid"] for b in r["bands"]]
    assert mids == sorted(mids, reverse=True), "bands must read high -> low"
    assert len(r["bands"]) == len(SPY_BANDS)
    assert set(r) == set(IZ.READ_KEYS), "the read's key set is pinned"
    for b in r["bands"]:
        assert set(b) == set(IZ.BAND_KEYS)
        if b["side"] == "above":
            assert b["lo"] > r["close"] and b["dist_pct"] > 0
        elif b["side"] == "below":
            assert b["hi"] < r["close"] and b["dist_pct"] > 0
        else:
            assert b["lo"] <= r["close"] <= b["hi"] and b["dist_pct"] == 0.0
    assert r["name"] == "SPDR S&P 500"
    # closed-bar basis, never the doc's session stamp
    assert r["as_of"] == "2026-09-16"
    assert r["close"] == 757.39 and r["atr14"] == 5.86 and r["high_252"] == 779.37


def test_the_spy_read_stands_inside_the_supply_band_2026_09_16():
    """The live 2026-09-16 structure: price INSIDE 749.53-779.37 supply, with
    the 759.48-762.04 DEMAND band as the nearest thing overhead."""
    r = IZ.read_doc("SPY", spy_doc())
    assert r["in_band"]["kind"] == "supply"
    assert (r["in_band"]["lo"], r["in_band"]["hi"]) == (749.53, 779.37)
    assert r["in_band"]["touches"] == 7
    assert (r["ceiling"]["lo"], r["ceiling"]["hi"]) == (759.48, 762.04)
    assert r["ceiling"]["kind"] == "demand", "nearest above, EITHER kind"
    assert r["ceiling"]["dist_pct"] == 0.28
    assert (r["floor"]["lo"], r["floor"]["hi"]) == (716.58, 739.51)
    assert r["floor"]["dist_pct"] == 2.36
    assert r["room_pct"] == r["ceiling"]["dist_pct"]
    assert r["drop_pct"] == r["floor"]["dist_pct"]


def test_the_qqq_read_stands_inside_its_demand_band_2026_09_16():
    r = IZ.read_doc("QQQ", qqq_doc())
    assert r["in_band"]["kind"] == "demand"
    assert (r["in_band"]["lo"], r["in_band"]["hi"]) == (695.25, 704.66)
    assert (r["ceiling"]["lo"], r["ceiling"]["hi"]) == (721.89, 748.65)
    assert r["ceiling"]["kind"] == "supply" and r["ceiling"]["dist_pct"] == 2.46
    assert (r["floor"]["lo"], r["floor"]["hi"]) == (661.14, 686.37)
    assert r["floor"]["kind"] == "demand" and r["floor"]["dist_pct"] == 2.58


def test_ceiling_and_floor_ignore_the_bands_kind_broken_support_is_resistance():
    """A lid price fell THROUGH is the shelf under it, and a demand band price
    has not reached is the ceiling. The walk is by distance, never by kind."""
    doc = _doc("X", 100.0, 2.0, 130.0,
               [("demand", 104.0, 106.0, 3, 50.0),     # demand ABOVE price
                ("supply", 120.0, 125.0, 4, 60.0),
                ("supply", 94.0, 96.0, 5, 70.0),       # broken lid BELOW price
                ("demand", 80.0, 85.0, 2, 30.0)])
    r = IZ.read_doc("X", doc)
    assert r["in_band"] is None
    assert r["ceiling"]["kind"] == "demand" and r["ceiling"]["lo"] == 104.0
    assert r["floor"]["kind"] == "supply" and r["floor"]["hi"] == 96.0
    assert r["room_pct"] == 4.0 and r["drop_pct"] == 4.0


def test_a_read_with_nothing_above_or_below_says_so_instead_of_faking_a_level():
    above_only = _doc("X", 100.0, 2.0, 130.0, [("supply", 110.0, 115.0, 3, 50.0)])
    r = IZ.read_doc("X", above_only)
    assert r["ceiling"]["lo"] == 110.0 and r["floor"] is None
    assert r["drop_pct"] is None and "no band below" in r["sentence"]
    below_only = _doc("X", 100.0, 2.0, 130.0, [("demand", 80.0, 85.0, 3, 50.0)])
    r2 = IZ.read_doc("X", below_only)
    assert r2["floor"]["hi"] == 85.0 and r2["ceiling"] is None
    assert r2["room_pct"] is None and "no band above" in r2["sentence"]


# ── NEGATIVES on the read ────────────────────────────────────────────────────
@pytest.mark.parametrize("doc,why", [
    (None, "a None doc"),
    ({}, "an empty doc"),
    ({"date": "2026-09-16"}, "a doc with no bands key"),
    (_doc("SPY", 757.39, 5.86, 779.37, []), "a doc with an empty band list"),
])
def test_NEGATIVE_an_unusable_doc_reads_unavailable_and_never_raises(doc, why):
    r = IZ.read_doc("SPY", doc)
    assert r["available"] is False, why
    assert r["reason"] and isinstance(r["reason"], str)
    assert set(r) == set(IZ.READ_KEYS), "unavailable still answers every key"
    assert r["bands"] == [] and r["in_band"] is None
    assert r["ceiling"] is None and r["floor"] is None
    assert r["room_pct"] is None and r["drop_pct"] is None
    assert r["source"] == "unavailable"
    assert r["symbol"] == "SPY" and "SPY" in r["sentence"]


def test_NEGATIVE_garbage_band_geometry_is_dropped_not_served():
    doc = _doc("X", 100.0, 2.0, 130.0,
               [("demand", None, 85.0, 3, 50.0),        # missing edge
                ("supply", 115.0, 110.0, 3, 50.0),      # inverted
                ("demand", -5.0, 3.0, 3, 50.0),         # non-positive
                ("demand", float("nan"), 90.0, 3, 50.0),
                ("supply", 110.0, 115.0, 3, 50.0)])     # the only real one
    doc["bands"].append({"kind": "mystery", "lo": 50.0, "hi": 55.0})
    doc["bands"].append("not a dict")
    r = IZ.read_doc("X", doc)
    assert [(b["lo"], b["hi"]) for b in r["bands"]] == [(110.0, 115.0)]
    assert r["available"] is True


def test_NEGATIVE_every_band_garbage_reads_unavailable():
    doc = _doc("X", 100.0, 2.0, 130.0, [("supply", 115.0, 110.0, 3, 50.0)])
    r = IZ.read_doc("X", doc)
    assert r["available"] is False and "band" in r["reason"]


@pytest.mark.parametrize("close", [0.0, -12.0, None, float("nan"), "oops"])
def test_NEGATIVE_a_zero_or_garbage_close_reads_unavailable(close):
    doc = _doc("X", 100.0, 2.0, 130.0, [("supply", 110.0, 115.0, 3, 50.0)])
    doc["prev_close"] = close
    doc["recent"] = [{"date": "2026-09-16", "low": 1.0, "high": 2.0, "close": close}]
    r = IZ.read_doc("X", doc)
    assert r["available"] is False and "close" in r["reason"]


def test_NEGATIVE_an_empty_symbol_reads_unavailable():
    assert IZ.read_doc("", spy_doc())["available"] is False


def test_the_closed_bar_date_wins_over_the_session_stamp():
    """zone_store stamps the doc with the session it warmed FOR and drops
    today's bar, so the bands belong to the last `recent` row. Saying today
    would label closed-bar structure with a date it never saw."""
    doc = _doc("SPY", 757.39, 5.86, 779.37, SPY_BANDS,
               as_of="2026-09-15", stored="2026-09-16")
    assert IZ.read_doc("SPY", doc)["as_of"] == "2026-09-15"
    doc.pop("recent")
    assert IZ.read_doc("SPY", doc)["as_of"] == "2026-09-16", "falls back, never None"


# ---------------------------------------------------------------------------
# with_live — the overlay
# ---------------------------------------------------------------------------
def test_with_live_puts_the_print_in_its_own_keys():
    stored = IZ.read_doc("QQQ", qqq_doc())
    out = IZ.with_live(stored, 712.00)
    assert out["price_basis"] == "live"
    assert out["live_px"] == 712.00
    # B6, 2026-09-16: `live_dist_pct` is the distance to the NEAREST BAND EDGE
    # as a percent OF THE PRINT, magnitude only — the same convention every
    # band dist_pct uses. The day move off the stored close is its own key.
    assert out["live_dist_pct"] == round((712.00 - 704.66) / 712.00 * 100, 2)
    assert out["live_chg_pct"] == round((712.00 - 704.54) / 704.54 * 100, 2)
    assert out["live_in_band"] is None, "712 sits between the two bands"
    assert out["live_side"] == "between"
    assert out["live_side"] in IZ.LIVE_SIDES
    # …and the CLOSED-bar read is untouched
    for k in IZ.READ_KEYS:
        assert out[k] == stored[k], f"{k} moved with a live print"


def test_with_live_reads_in_above_and_below_against_the_stored_bands():
    stored = IZ.read_doc("QQQ", qqq_doc())
    assert IZ.with_live(stored, 700.0)["live_side"] == "in"
    assert IZ.with_live(stored, 700.0)["live_in_band"]["hi"] == 704.66
    assert IZ.with_live(stored, 900.0)["live_side"] == "above"
    assert IZ.with_live(stored, 100.0)["live_side"] == "below"


@pytest.mark.parametrize("px", [None, 0, 0.0, -3.5, "", "oops", float("nan")])
def test_NEGATIVE_a_dead_tape_leaves_the_read_exactly_as_stored(px):
    """A snapshot that is not a price is MISSING, not a price. The day bar
    reads 0 before the open (the 2026-09-05 board fix) and 0.0 fed through as
    a print is how a stale column starts lying."""
    stored = IZ.read_doc("SPY", spy_doc())
    out = IZ.with_live(stored, px)
    assert out["price_basis"] == "close"
    assert out["live_px"] is None and out["live_dist_pct"] is None
    assert out["live_chg_pct"] is None
    assert out["live_in_band"] is None and out["live_side"] is None
    for k in IZ.READ_KEYS:
        assert out[k] == stored[k]


def test_NEGATIVE_with_live_never_mutates_its_input():
    stored = IZ.read_doc("SPY", spy_doc())
    before = {k: stored[k] for k in stored}
    IZ.with_live(stored, 770.0)
    assert stored == before
    assert not any(k in stored for k in IZ.LIVE_KEYS), \
        "the stored read must not grow live keys"


def test_NEGATIVE_an_unavailable_read_takes_no_live_overlay():
    out = IZ.with_live(IZ.read_doc("SPY", None), 770.0)
    assert out["price_basis"] == "close" and out["live_px"] is None


def test_a_read_is_identical_at_0420_and_at_1500():
    """The whole contract in one assertion: the stored half of the read cannot
    move during the session, only the live half is allowed to."""
    stored = IZ.read_doc("SPY", spy_doc())
    dawn = IZ.with_live(stored, None)
    noon = IZ.with_live(stored, 771.42)
    assert {k: dawn[k] for k in IZ.READ_KEYS} == {k: noon[k] for k in IZ.READ_KEYS}
    assert set(noon) - set(dawn) == set()
    assert noon["price_basis"] == "live" and dawn["price_basis"] == "close"


# ---------------------------------------------------------------------------
# warm — the overnight job
# ---------------------------------------------------------------------------
def test_warm_prefers_the_zone_store_and_records_the_source_per_symbol():
    coll = FakeColl()
    res = IZ.warm(coll=coll, store_docs={"SPY": spy_doc(), "QQQ": qqq_doc()},
                  loader=lambda s: None, today=date(2026, 9, 16),
                  namer=lambda s: f"{s} Trust")
    assert res["written"] is True and coll.writes == 1
    doc = coll.docs["2026-09-16"]
    assert doc["_id"] == "2026-09-16" and doc["date"] == "2026-09-16"
    assert doc["source"] == IZ.DOC_SOURCE and doc["computed_at"]
    assert set(doc["indexes"]) == set(IZ.INDEXES)
    assert all(r["source"] == "zone_store" for r in doc["indexes"].values())
    assert doc["indexes"]["SPY"]["name"] == "SPY Trust"
    assert res["sources"]["zone_store"] == 2


def test_warm_falls_back_to_computing_the_bands_and_says_so(monkeypatch):
    """No store doc for QQQ -> compute it with the SAME engine and geometry
    (zone_store.build_doc: closed bars, zone_geom, max_zones=None)."""
    from supply_demand import zone_store as ZS
    seen = {}

    def fake_build(sym, df, today, **kw):
        seen[sym] = (df, today)
        return qqq_doc()

    monkeypatch.setattr(ZS, "build_doc", fake_build)
    coll = FakeColl()
    res = IZ.warm(coll=coll, store_docs={"SPY": spy_doc()},
                  loader=lambda s: f"frame:{s}", today=date(2026, 9, 16),
                  namer=lambda s: s)
    idx = coll.docs["2026-09-16"]["indexes"]
    assert idx["SPY"]["source"] == "zone_store"
    assert idx["QQQ"]["source"] == "computed" and idx["QQQ"]["available"] is True
    assert seen["QQQ"] == ("frame:QQQ", date(2026, 9, 16))
    assert res["sources"] == {"zone_store": 1, "computed": 1, "unavailable": 0}


def test_NEGATIVE_a_symbol_that_cannot_be_read_is_stored_unavailable_with_a_reason():
    """Never silently dropped and never faked — a missing index has to say so
    on the strip, because a blank tile reads as 'no structure', which is a
    different and untrue claim."""
    def boom(sym):
        raise RuntimeError("no bars")

    coll = FakeColl()
    res = IZ.warm(coll=coll, store_docs={"SPY": spy_doc()}, loader=boom,
                  today=date(2026, 9, 16), namer=lambda s: s)
    idx = coll.docs["2026-09-16"]["indexes"]
    assert set(idx) == set(IZ.INDEXES), "the symbol is PRESENT, not dropped"
    assert idx["QQQ"]["available"] is False and idx["QQQ"]["reason"]
    assert idx["QQQ"]["source"] == "unavailable"
    assert idx["QQQ"]["bands"] == [] and idx["QQQ"]["close"] is None
    assert res["sources"]["unavailable"] == 1


def test_NEGATIVE_a_broken_collection_never_raises_out_of_warm():
    res = IZ.warm(coll=BrokenColl(), store_docs={"SPY": spy_doc(), "QQQ": qqq_doc()},
                  loader=lambda s: None, today=date(2026, 9, 16),
                  namer=lambda s: s)
    assert res["written"] is False
    assert set(res["doc"]["indexes"]) == set(IZ.INDEXES)


def test_the_module_runs_as_a_cron_entrypoint_like_zone_store():
    src = (ROOT / "backend/supply_demand/index_zones.py").read_text()
    assert 'if __name__ == "__main__":' in src
    assert "res = warm()" in src and "INDEX-ZONES:" in src


# ---------------------------------------------------------------------------
# load_latest + served
# ---------------------------------------------------------------------------
def test_load_latest_and_served_read_the_stored_doc_and_never_warm():
    coll = FakeColl()
    IZ.warm(coll=coll, store_docs={"SPY": spy_doc(), "QQQ": qqq_doc()},
            loader=lambda s: None, today=date(2026, 9, 16), namer=lambda s: s)
    day, reads = IZ.load_latest(coll=coll, today=date(2026, 9, 16))
    assert day == "2026-09-16" and set(reads) == set(IZ.INDEXES)
    out = IZ.served(live={"SPY": 760.10, "QQQ": None}, coll=coll,
                    today=date(2026, 9, 16))
    assert set(out) == set(IZ.PAYLOAD_KEYS)
    assert out["date"] == "2026-09-16" and out["stale_days"] == 0
    assert out["as_of"] == "2026-09-16" and out["stale_sessions"] == 0
    assert out["default_resolution"] == IZ.DEFAULT_RESOLUTION
    assert out["indexes"]["SPY"]["price_basis"] == "live"
    assert out["indexes"]["QQQ"]["price_basis"] == "close"
    assert out["indexes"]["SPY"]["close"] == 757.39, "the stored close stands"


def test_NEGATIVE_a_cold_store_serves_an_explained_empty_shape():
    out = IZ.served(live={}, coll=FakeColl(), today=date(2026, 9, 16))
    assert out == IZ.empty_payload(out["note"])
    assert set(out) == set(IZ.PAYLOAD_KEYS)
    assert "has not run" in out["note"]


def test_NEGATIVE_a_broken_collection_serves_the_empty_shape_not_an_exception():
    out = IZ.served(live={}, coll=BrokenColl(), today=date(2026, 9, 16))
    assert out["date"] is None and out["indexes"] == {}


def test_staleness_is_served_and_a_weekend_is_not_stale():
    """The job is weekdays-only and the bands are closed-bar, so Friday's doc
    read on Sunday is the LAST CLOSE, not a stale one."""
    sat = IZ.staleness("2026-09-18", today=date(2026, 9, 19))   # Fri -> Sat
    sun = IZ.staleness("2026-09-18", today=date(2026, 9, 20))   # Fri -> Sun
    assert sat["stale_days"] == 1 and sat["stale_sessions"] == 0
    assert sun["stale_days"] == 2 and sun["stale_sessions"] == 0
    for r in (sat, sun):
        assert "stale" not in r["note"].lower()
        assert "closed bars" in r["note"]
    mon = IZ.staleness("2026-09-18", today=date(2026, 9, 22))   # Fri -> Tue
    assert mon["stale_days"] == 4 and mon["stale_sessions"] == 2
    assert "2 sessions old" in mon["note"]
    # a holiday is not a session either (2026-11-26 Thanksgiving)
    hol = IZ.staleness("2026-11-25", today=date(2026, 11, 26))
    assert hol["stale_sessions"] == 0


def test_NEGATIVE_an_unreadable_stored_date_is_explained_not_raised():
    r = IZ.staleness("not-a-date", today=date(2026, 9, 16))
    assert r["stale_days"] is None and "unreadable" in r["note"]


def test_api_payload_swallows_everything(monkeypatch):
    monkeypatch.setattr(IZ, "served", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("x")))
    out = IZ.api_payload()
    assert set(out) == set(IZ.PAYLOAD_KEYS)
    assert out["indexes"] == {} and out["note"]


# ---------------------------------------------------------------------------
# the route
# ---------------------------------------------------------------------------
def test_the_route_serves_the_stored_read_and_never_warms(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from supply_demand import api as sd_api

    called = []
    monkeypatch.setattr(sd_api.index_zones_mod, "api_payload",
                        lambda: called.append(1) or {"date": "2026-09-16",
                                                     "indexes": {}, "stale_days": 0,
                                                     "note": "n"})
    app = FastAPI()
    app.include_router(sd_api.router)
    r = TestClient(app).get("/supply-demand/index-zones")
    assert r.status_code == 200 and r.json()["date"] == "2026-09-16"
    assert called == [1]
    src = inspect.getsource(sd_api.get_index_zones)
    assert "warm" not in src, "the route must never compute the bands"


def test_NEGATIVE_the_route_answers_200_on_a_cold_store(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from supply_demand import api as sd_api

    monkeypatch.setattr(IZ, "load_latest", lambda **kw: (None, {}))
    monkeypatch.setattr(sd_api.index_zones_mod, "api_payload", IZ.api_payload)
    app = FastAPI()
    app.include_router(sd_api.router)
    r = TestClient(app).get("/supply-demand/index-zones")
    assert r.status_code == 200
    body = r.json()
    assert body["date"] is None and body["indexes"] == {} and body["note"]


# ---------------------------------------------------------------------------
# the pinned strip on the zones board
# ---------------------------------------------------------------------------
@pytest.fixture
def board_stub(monkeypatch):
    """The Back in Demand board with demand_reentry stubbed — the same shape
    tests/test_chart_maps.py uses."""
    payload = {"rows": [], "warming": False, "universe_key": "full",
               "universe_label": "full", "scanned": 1}

    class _D:
        @staticmethod
        def cached_or_warm(universe, limit=None):
            return payload

    monkeypatch.setitem(sys.modules, "supply_demand.demand_reentry", _D())
    import supply_demand
    monkeypatch.setattr(supply_demand, "demand_reentry", _D(), raising=False)
    # No tape in the suite: the board's own bulk fetch is stubbed to the
    # outage answer ({}), which is also the shape a real outage produces.
    from chart_maps import board as B
    monkeypatch.setattr(B, "_live_rows", lambda symbols: {})
    return payload


STRIP = {"date": "2026-09-16", "stale_days": 0, "note": "n",
         "indexes": {"SPY": {"symbol": "SPY"}, "QQQ": {"symbol": "QQQ"}}}


def test_the_zones_board_pins_the_index_strip(board_stub, monkeypatch):
    from chart_maps import board as B
    monkeypatch.setattr(IZ, "served", lambda **kw: STRIP)
    out = B.board("zones", limit=5, min_tier="any")
    assert out["tiles"] == []
    assert out["index_zones"] == STRIP, "pinned even with nothing on the board"


def test_the_warming_board_still_carries_the_index_strip(board_stub, monkeypatch):
    """A strip that disappears while the board scans is not pinned — and the
    warming branch is exactly when Ajay opens the tab in the morning."""
    from chart_maps import board as B
    board_stub["warming"] = True
    board_stub["progress"] = {"done": 3, "total": 10}
    monkeypatch.setattr(IZ, "served", lambda **kw: STRIP)
    out = B.board("zones", limit=5)
    assert out["warming"] is True and out["tiles"] == []
    assert out["index_zones"] == STRIP


def test_NEGATIVE_the_board_still_renders_when_the_index_read_raises(
        board_stub, monkeypatch):
    from chart_maps import board as B

    def boom(**kw):
        raise RuntimeError("index doc exploded")

    monkeypatch.setattr(IZ, "served", boom)
    out = B.board("zones", limit=5, min_tier="any")
    assert out["tab"] == "zones" and out["tiles"] == []
    assert out["index_zones"]["indexes"] == {}
    assert out["index_zones"]["note"]
    board_stub["warming"] = True
    warming = B.board("zones", limit=5)
    assert warming["warming"] is True and warming["index_zones"]["indexes"] == {}


def test_the_strip_rides_the_boards_existing_live_fetch(board_stub, monkeypatch):
    """One bulk snapshot per board load, not two: the strip's symbols go into
    the fetch the bounce gate and the room floor already make."""
    from chart_maps import board as B
    calls = []

    def fake_rows(symbols):
        calls.append(list(symbols))
        return {}

    monkeypatch.setattr(B, "_live_rows", fake_rows)
    got = {}
    monkeypatch.setattr(IZ, "served",
                        lambda **kw: got.update(kw) or STRIP)
    B.board("zones", limit=5, min_tier="any")
    # The board makes its own decorator fetch over the finished tiles; what
    # matters is that the STRIP adds none — its symbols appear in exactly one
    # call, the row fetch the bounce gate and the room floor already make.
    idx_calls = [c for c in calls if set(IZ.INDEXES) <= set(c)]
    assert len(idx_calls) == 1, f"the strip cost an extra fetch: {calls}"
    assert set(got["live"]) == set(IZ.INDEXES), \
        "the strip is handed the prints, it does not go back to the provider"


# ---------------------------------------------------------------------------
# honesty
# ---------------------------------------------------------------------------
_BANNED = ("bounce", "buy", "sell", "target", "entry", "stop", "edge",
           "signal", "should", "expect", "likely", "favorable", "advice")


def _sentences():
    out = [IZ.read_doc("SPY", spy_doc())["sentence"],
           IZ.read_doc("QQQ", qqq_doc())["sentence"],
           IZ.read_doc("SPY", None)["sentence"],
           IZ.read_doc("X", _doc("X", 100.0, 2.0, 130.0,
                                 [("supply", 110.0, 115.0, 3, 50.0)]))["sentence"],
           IZ.read_doc("X", _doc("X", 100.0, 2.0, 130.0,
                                 [("demand", 80.0, 85.0, 3, 50.0)]))["sentence"]]
    return out


def test_NEGATIVE_no_sentence_says_bounce_or_claims_an_edge():
    """"Reversal", never "bounce", on any surface he reads — and this strip is
    CONTEXT: every measured structural S/D read this month came back null, so
    no line here may read as a call."""
    for s in _sentences():
        low = s.lower()
        for word in _BANNED:
            assert word not in low, f"{word!r} in: {s}"
    assert "bounce" not in IZ.DISCLAIMER.lower()
    for word in ("gates nothing", "not advice"):
        assert word in IZ.DISCLAIMER


def test_the_sentence_is_built_from_the_numbers_it_serves():
    r = IZ.read_doc("QQQ", qqq_doc())
    s = r["sentence"]
    assert "QQQ 704.54" in s and "2026-09-16" in s
    assert "695.25" in s and "704.66" in s
    assert "721.89" in s and "2.46" in s
    assert "686.37" in s and "2.58" in s


def test_NEGATIVE_the_module_types_no_threshold_of_its_own():
    """Every cut is imported or comes off the stored doc. The only numeric
    literals allowed are structural: 0/1 (identity, index, a one-day step),
    2 (decimal places, a midpoint) and 100 (percent)."""
    src = (ROOT / "backend/supply_demand/index_zones.py").read_text()
    tree = ast.parse(src)
    bad = sorted({n.value for n in ast.walk(tree)
                  if isinstance(n, ast.Constant)
                  and isinstance(n.value, (int, float))
                  and not isinstance(n.value, bool)
                  and n.value not in (0, 1, 2, 100)})
    assert bad == [], f"index_zones types its own numbers: {bad}"
    # the geometry and the retention come from the engines that own them
    code = _code_only(src)
    assert "zone_store" in code and "KEEP_DAYS" in code
    assert "for_symbol" not in code, "never the live-bar overlay path"
    # The FINE set is price_zones' MODULE DEFAULTS: compute is called with the
    # cap released and NOT ONE geometry kwarg, so the two surfaces cannot
    # drift and no knob is retyped here (2026-09-16).
    assert "price_zones.compute(frame, max_zones=None)" in code
    for knob in ("swing_window", "merge_pct", "half_width_pct", "lookback_bars"):
        assert knob not in code, f"index_zones retypes the {knob} geometry"
    # The chart window is chart_maps' rule, imported, never re-derived.
    assert "_zone_window" in code and "_frame_to_bars" in code
    assert "ZONE_BARS" not in code


_TRIPLE = re.compile(r"(\"\"\"|\'\'\')(?:.|\n)*?\1")


def _code_only(src: str) -> str:
    """`src` with docstrings and comments dropped, so a source scan reads what
    the code DOES, never what its prose mentions (the 2026-09-16 trap — see
    tests/test_supply_demand_contracts.py)."""
    src = _TRIPLE.sub("", src)
    keep = []
    for line in src.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        keep.append(line.split("  #")[0])
    return "\n".join(keep)


def test_the_docs_page_exists_and_is_dated():
    doc = ROOT / "docs/supply_demand/index_zones.md"
    assert doc.exists()
    text = doc.read_text()
    assert "2026-09-16" in text
    assert "SPY" in text and "QQQ" in text
    assert "closed bars" in text.lower()


# ---------------------------------------------------------------------------
# 2026-09-16, follow-up: TWO resolutions + the chart bars
#
# Ajay: *"I wanna see charts with multiple zones"* / *"For both QQQ and SPY"* /
# *"Sorry SPY only my bad"* -> SPY and QQQ, a chart each, and more bands than
# the seven the board geometry draws. The fine set is the price_zones MODULE
# DEFAULTS — an existing cited setting, not a new number.
# ---------------------------------------------------------------------------
def _frame(n=300, end="2026-09-16", base=100.0):
    """A synthetic daily frame with swings at many levels, so the two
    geometries genuinely disagree about how many bands there are."""
    import math

    import pandas as pd
    idx = pd.bdate_range(end=end, periods=n)
    rows = []
    for i in range(n):
        px = base + 12 * math.sin(i / 4.0) + 6 * math.sin(i / 17.0) + i * 0.03
        rows.append({"open": px, "high": px * 1.01, "low": px * 0.99,
                     "close": px, "volume": 1_000_000 + i})
    return pd.DataFrame(rows, index=idx)


def _warm_frames(coll=None, today=date(2026, 9, 16)):
    frames = {"SPY": _frame(), "QQQ": _frame(base=140.0)}
    coll = coll or FakeColl()
    res = IZ.warm(coll=coll, store_docs={}, loader=lambda s: frames[s],
                  today=today, namer=lambda s: s)
    return coll, res


def test_warm_serves_both_resolutions_and_the_fine_set_is_the_denser_one():
    """He asked for MULTIPLE zones. Board geometry gives seven; the fine set is
    the same engine at the price_zones module defaults and gives more. Both are
    stored, both are read-shaped, and the BOARD read stays at the top level so
    nothing built against the first cut breaks."""
    coll, _res = _warm_frames()
    entry = coll.docs["2026-09-16"]["indexes"]["SPY"]
    assert set(entry) == set(IZ.INDEX_KEYS)
    assert set(entry["resolutions"]) == set(IZ.RESOLUTIONS)
    board = entry["resolutions"][IZ.RESOLUTION_BOARD]
    fine = entry["resolutions"][IZ.RESOLUTION_FINE]
    for r in (board, fine):
        assert set(r) == set(IZ.READ_KEYS) and r["available"] is True
        for b in r["bands"]:
            assert set(b) == set(IZ.BAND_KEYS)
    assert len(fine["bands"]) > len(board["bands"]), \
        "the fine set has to be the denser one — that was the whole ask"
    # the top level IS the board read
    assert {k: entry[k] for k in IZ.READ_KEYS} == board
    assert IZ.DEFAULT_RESOLUTION == IZ.RESOLUTION_FINE


def test_the_two_resolutions_share_one_closed_bar_basis():
    coll, _res = _warm_frames()
    for sym in IZ.INDEXES:
        entry = coll.docs["2026-09-16"]["indexes"][sym]
        res = entry["resolutions"]
        assert res["board"]["as_of"] == res["fine"]["as_of"] == entry["as_of"]
        assert res["board"]["close"] == res["fine"]["close"] == entry["close"]
        assert entry["as_of"] == "2026-09-15", "today's bar is dropped"


def test_the_bars_are_closed_daily_candles_in_the_chart_maps_shape():
    """Same {t,o,h,l,c,v} every chart_maps tile draws, windowed by that
    module's own _zone_window over EVERY band in BOTH sets."""
    from chart_maps.board import ZONE_BARS_MAX, _zone_window
    coll, _res = _warm_frames()
    entry = coll.docs["2026-09-16"]["indexes"]["QQQ"]
    bars = entry["bars"]
    assert entry["bars_basis"] == IZ.BARS_BASIS == "closed"
    assert bars and len(bars) <= ZONE_BARS_MAX
    assert set(bars[0]) == {"t", "o", "h", "l", "c", "v"}
    assert [b["t"] for b in bars] == sorted(b["t"] for b in bars)
    assert bars[-1]["t"] == entry["as_of"] == "2026-09-15", \
        "the chart ends on the same closed bar the bands were drawn on"
    assert all(b["t"] < "2026-09-16" for b in bars), "today's bar is never drawn"
    # the window is chart_maps' own rule over EVERY band in BOTH sets
    windows = [_zone_window(b) for r in entry["resolutions"].values()
               for b in r["bands"]] or [_zone_window(None)]
    assert len(bars) >= min(max(windows), ZONE_BARS_MAX)
    lo = min(b["l"] for b in bars)
    hi = max(b["h"] for b in bars)
    for r in entry["resolutions"].values():
        for band in r["bands"]:
            assert band["lo"] <= hi and band["hi"] >= lo, \
                "a band drawn entirely off the chart"


def test_NEGATIVE_no_frame_means_no_bars_and_an_honest_read_not_a_fake_one():
    """A provider outage costs the chart and the fine set. It must not cost the
    board read (the store already has it) and must never fake a bar."""
    coll = FakeColl()
    IZ.warm(coll=coll, store_docs={"SPY": spy_doc(), "QQQ": qqq_doc()},
            loader=lambda s: None, today=date(2026, 9, 16), namer=lambda s: s)
    entry = coll.docs["2026-09-16"]["indexes"]["SPY"]
    assert entry["bars"] == [] and entry["bars_basis"] == IZ.BARS_BASIS
    assert entry["available"] is True and entry["source"] == "zone_store"
    assert entry["resolutions"]["board"]["available"] is True
    fine = entry["resolutions"]["fine"]
    assert fine["available"] is False and fine["reason"]
    assert fine["source"] == "unavailable" and fine["bands"] == []


def test_NEGATIVE_a_raising_loader_never_takes_the_job_down():
    def boom(sym):
        raise RuntimeError("provider down")

    coll = FakeColl()
    res = IZ.warm(coll=coll, store_docs={"SPY": spy_doc()}, loader=boom,
                  today=date(2026, 9, 16), namer=lambda s: s)
    idx = coll.docs["2026-09-16"]["indexes"]
    assert set(idx) == set(IZ.INDEXES)
    assert idx["SPY"]["available"] is True and idx["SPY"]["bars"] == []
    assert idx["QQQ"]["available"] is False
    assert set(idx["QQQ"]["resolutions"]) == set(IZ.RESOLUTIONS)
    assert res["written"] is True


def test_served_carries_both_resolutions_the_bars_and_the_live_overlay():
    coll, _res = _warm_frames()
    out = IZ.served(live={"SPY": 200.0, "QQQ": None}, coll=coll,
                    today=date(2026, 9, 16))
    assert set(out) == set(IZ.PAYLOAD_KEYS)
    assert out["default_resolution"] == IZ.DEFAULT_RESOLUTION
    spy = out["indexes"]["SPY"]
    assert spy["bars"] and set(spy["resolutions"]) == set(IZ.RESOLUTIONS)
    assert spy["price_basis"] == "live"
    for r in spy["resolutions"].values():
        assert r["price_basis"] == "live" and r["live_px"] == 200.0
        assert r["live_side"] in IZ.LIVE_SIDES
    qqq = out["indexes"]["QQQ"]
    assert qqq["price_basis"] == "close"
    assert all(r["price_basis"] == "close" for r in qqq["resolutions"].values())


def test_NEGATIVE_serving_never_recomputes_a_band_or_touches_a_frame(monkeypatch):
    """Overnight ONCE, read many. A resolution computed per request is the bug
    this whole module exists to avoid."""
    coll, _res = _warm_frames()
    from supply_demand import price_zones, zone_store as ZS

    def boom(*a, **kw):
        raise AssertionError("served() recomputed structure")

    monkeypatch.setattr(price_zones, "compute", boom)
    monkeypatch.setattr(ZS, "build_doc", boom)
    monkeypatch.setattr(IZ, "live_prints", lambda *a, **kw: {})
    out = IZ.served(coll=coll, today=date(2026, 9, 16))
    assert out["indexes"]["SPY"]["resolutions"]["fine"]["bands"]


# ---------------------------------------------------------------------------
# B1 / B2 — staleness is measured on the BAND basis, in sessions and days
# ---------------------------------------------------------------------------
def test_B1_staleness_is_measured_on_the_band_basis_not_the_job_day():
    """zone_store drops today's bar, so the doc day is ALWAYS one session ahead
    of the structure — and a store that failed days ago still gets its old
    bands re-stored under today. Measuring on the job day read stale_days 0
    with week-old bands; measuring on `as_of` shows it."""
    coll = FakeColl()
    stale = _doc("SPY", 757.39, 5.86, 779.37, SPY_BANDS,
                 as_of="2026-09-09", stored="2026-09-16")
    IZ.warm(coll=coll, store_docs={"SPY": stale, "QQQ": qqq_doc()},
            loader=lambda s: None, today=date(2026, 9, 16), namer=lambda s: s)
    out = IZ.served(live={}, coll=coll, today=date(2026, 9, 16))
    assert out["date"] == "2026-09-16", "the job day is still reported"
    assert out["as_of"] == "2026-09-16", "the freshest available read is the basis"
    # now the WHOLE store is a week behind
    coll2 = FakeColl()
    IZ.warm(coll=coll2, store_docs={"SPY": stale, "QQQ": _doc(
        "QQQ", 704.54, 7.76, 748.65, QQQ_BANDS, as_of="2026-09-09",
        stored="2026-09-16")}, loader=lambda s: None,
        today=date(2026, 9, 16), namer=lambda s: s)
    out2 = IZ.served(live={}, coll=coll2, today=date(2026, 9, 16))
    assert out2["date"] == "2026-09-16" and out2["as_of"] == "2026-09-09"
    assert out2["stale_days"] == 7 and out2["stale_sessions"] == 5
    assert "5 sessions old" in out2["note"]
    assert "2026-09-09" in out2["note"] and "2026-09-16" in out2["note"], \
        "both dates on screen — the basis and the job run that stored it"


def test_B2_stale_sessions_is_served_beside_stale_days():
    """The page prints the word 'session'. The number under it has to be
    sessions, not calendar days, and both are served so nothing infers."""
    coll = FakeColl()
    IZ.warm(coll=coll, store_docs={"SPY": spy_doc(), "QQQ": qqq_doc()},
            loader=lambda s: None, today=date(2026, 9, 16), namer=lambda s: s)
    out = IZ.served(live={}, coll=coll, today=date(2026, 9, 20))   # Sunday
    assert out["stale_days"] == 4 and out["stale_sessions"] == 2
    assert "2 sessions old" in out["note"]
    assert "4 sessions" not in out["note"], "the word on screen is sessions"


def test_NEGATIVE_a_stored_doc_with_nothing_readable_says_so(monkeypatch):
    coll = FakeColl()
    IZ.warm(coll=coll, store_docs={"SPY": {}, "QQQ": {}}, loader=lambda s: None,
            today=date(2026, 9, 16), namer=lambda s: s)
    out = IZ.served(live={}, coll=coll, today=date(2026, 9, 16))
    assert out["as_of"] is None and out["date"] == "2026-09-16"
    assert out["stale_days"] is None and out["stale_sessions"] is None
    assert "no readable structure" in out["note"]
    assert set(out["indexes"]) == set(IZ.INDEXES)


# ---------------------------------------------------------------------------
# B3 — the KIND of the band overhead / underfoot
# ---------------------------------------------------------------------------
def test_B3_ceiling_and_floor_carry_their_kind_and_the_sentence_names_it():
    """Pankaj's rule — a broken demand zone becomes supply — is only visible if
    the read says WHICH KIND the band above is. This engine already flips
    (ceiling/floor ignore kind); now it says so out loud."""
    r = IZ.read_doc("SPY", spy_doc())
    assert r["ceiling"]["kind"] in ("supply", "demand")
    assert r["floor"]["kind"] in ("supply", "demand")
    assert f"next {r['ceiling']['kind']} band above" in r["sentence"]
    assert f"next {r['floor']['kind']} band below" in r["sentence"]
    # SPY 757.39 has a DEMAND band overhead — a band price fell through
    assert r["ceiling"]["kind"] == "demand"
    assert "next demand band above" in r["sentence"]


# ---------------------------------------------------------------------------
# B4 — the date and the close come off the SAME bar
# ---------------------------------------------------------------------------
def test_B4_NEGATIVE_a_nan_low_last_bar_never_pairs_two_sessions():
    """zone_store.recent_sessions SKIPS a row with a NaN low; prev_close does
    not. Reading the date from one and the close from the other dated Tuesday's
    header with Wednesday's price."""
    doc = _doc("SPY", 757.39, 5.86, 779.37, SPY_BANDS, stored="2026-09-16")
    doc["recent"] = [{"date": "2026-09-14", "low": 748.0, "high": 760.0,
                      "close": 750.25},
                     {"date": "2026-09-15", "low": 752.0, "high": 762.0,
                      "close": 755.50}]
    assert IZ.read_doc("SPY", doc)["as_of"] == "2026-09-15"
    assert IZ.read_doc("SPY", doc)["close"] == 755.50
    # the NaN-low bar (2026-09-15) never reached `recent`, and prev_close is
    # ITS close: the read must fall back to the last row that carries both,
    # not staple 757.39 onto the 2026-09-14 date.
    doc["recent"] = [{"date": "2026-09-14", "low": 748.0, "high": 760.0,
                      "close": 750.25}]
    r = IZ.read_doc("SPY", doc)
    assert (r["as_of"], r["close"]) == ("2026-09-14", 750.25)
    assert r["close"] != 757.39, "a date from one bar and a close from another"
    assert f"SPY 750.25 at the 2026-09-14 close" in r["sentence"]


def test_B4_a_recent_row_with_no_usable_close_is_skipped_not_served():
    doc = _doc("SPY", 757.39, 5.86, 779.37, SPY_BANDS, stored="2026-09-16")
    doc["recent"] = [{"date": "2026-09-14", "low": 748.0, "close": 750.25},
                     {"date": "2026-09-15", "low": 752.0, "close": None}]
    r = IZ.read_doc("SPY", doc)
    assert (r["as_of"], r["close"]) == ("2026-09-14", 750.25)
    # nothing usable anywhere -> the doc stamp and prev_close, and served()
    # reports the two dates separately
    doc["recent"] = [{"date": "2026-09-15", "low": 752.0, "close": None}]
    r2 = IZ.read_doc("SPY", doc)
    assert (r2["as_of"], r2["close"]) == ("2026-09-16", 757.39)


# ---------------------------------------------------------------------------
# B5 — the live vocabulary, in one place
# ---------------------------------------------------------------------------
def test_B5_live_side_vocabulary_is_a_constant_and_live_in_band_never_lies():
    """'between' is a real answer (outside every band, inside the set's range).
    What must never happen is a side other than 'in' carrying a band — there is
    no 'the band it was last in'."""
    assert IZ.LIVE_SIDES == ("in", "above", "below", "between")
    stored = IZ.read_doc("QQQ", qqq_doc())
    seen = set()
    for px in (700.0, 712.00, 900.0, 100.0):
        out = IZ.with_live(stored, px)
        assert out["live_side"] in IZ.LIVE_SIDES
        seen.add(out["live_side"])
        if out["live_side"] != "in":
            assert out["live_in_band"] is None, out["live_side"]
        else:
            lo = out["live_in_band"]["lo"]
            hi = out["live_in_band"]["hi"]
            assert lo <= px <= hi
    assert seen == set(IZ.LIVE_SIDES), "every side is reachable"
    doc = IZ.__doc__ or ""
    for side in IZ.LIVE_SIDES:
        assert f'"{side}"' in doc, "the vocabulary is documented in one place"


# ---------------------------------------------------------------------------
# B6 — live_dist_pct has a definition
# ---------------------------------------------------------------------------
def test_B6_live_dist_pct_is_the_distance_to_the_nearest_band_edge():
    stored = IZ.read_doc("QQQ", qqq_doc())
    # inside a band -> zero, never a negative or a day move
    inside = IZ.with_live(stored, 700.0)
    assert inside["live_dist_pct"] == 0.0
    assert inside["live_chg_pct"] == round((700.0 - 704.54) / 704.54 * 100, 2)
    # between two bands -> the NEARER edge, whichever side it is on
    # (704.66 is 7.34 below 712.00; 721.89 is 9.89 above it)
    between = IZ.with_live(stored, 712.00)
    assert between["live_dist_pct"] == round((712.00 - 704.66) / 712.00 * 100, 2)
    # nearer to the lid than to the shelf -> the lid
    up = IZ.with_live(stored, 719.00)
    assert up["live_dist_pct"] == round((721.89 - 719.00) / 719.00 * 100, 2)
    # magnitude only — the direction is live_side's job, never a sign
    for px in (100.0, 900.0, 712.00, 700.0):
        assert IZ.with_live(stored, px)["live_dist_pct"] >= 0
    assert "nearest" in (IZ.with_live.__doc__ or "").lower()


def test_B6_NEGATIVE_a_read_with_no_bands_has_no_edge_to_measure_to():
    out = IZ.with_live(IZ.read_doc("SPY", None), 770.0)
    assert out["live_dist_pct"] is None and out["live_chg_pct"] is None
    assert out["price_basis"] == "close"


# ---------------------------------------------------------------------------
# the strip end to end on the board
# ---------------------------------------------------------------------------
def test_the_zones_board_pins_both_resolutions_and_the_bars(board_stub, monkeypatch):
    coll, _res = _warm_frames()
    monkeypatch.setattr(IZ, "_coll", lambda c=None: c if c is not None else coll)
    monkeypatch.setattr(IZ, "live_prints", lambda *a, **kw: {})
    monkeypatch.setattr(IZ, "_today_et", lambda now=None: date(2026, 9, 16))
    from chart_maps import board as B
    out = B.board("zones", limit=5, min_tier="any")
    strip = out["index_zones"]
    assert set(strip) == set(IZ.PAYLOAD_KEYS)
    assert strip["default_resolution"] == IZ.DEFAULT_RESOLUTION
    for sym in IZ.INDEXES:
        entry = strip["indexes"][sym]
        assert set(entry["resolutions"]) == set(IZ.RESOLUTIONS)
        assert len(entry["resolutions"]["fine"]["bands"]) > \
            len(entry["resolutions"]["board"]["bands"])
        assert entry["bars"] and entry["bars_basis"] == IZ.BARS_BASIS


def test_the_docs_page_covers_both_resolutions_and_the_flip_rule():
    text = (ROOT / "docs/supply_demand/index_zones.md").read_text()
    for needle in ("board", "fine", "14", "13", "bars", "closed bars",
                   "default_resolution", "stale_sessions", "as_of"):
        assert needle in text, needle
    low = text.lower()
    assert "broken" in low and "becomes" in low, "Pankaj's flip rule is stated"
    assert "no edge" in low or "not measured" in low


# ── 2026-09-16 review fixes ──────────────────────────────────────────────────
def test_V2_a_stale_board_doc_never_dates_the_fine_set_with_another_session():
    """`zone_store.load_latest` hands back the latest doc <= today, so a failed
    04:05 warm leaves a board doc days behind the fine one built from today's
    frame. The card then dated fine bands with the board's session and drew a
    close line from another day over the candles."""
    import pandas as pd
    idx = pd.bdate_range("2026-03-02", periods=200)
    frame = pd.DataFrame({
        "open": [100 + (i % 17) for i in range(200)],
        "high": [104 + (i % 17) for i in range(200)],
        "low": [96 + (i % 17) for i in range(200)],
        "close": [100 + (i % 17) for i in range(200)],
        "volume": [1_000_000] * 200,
    }, index=idx)
    stale = {"symbol": "SPY", "date": "2026-03-01",
             "recent": [{"date": "2026-03-01", "low": 90.0, "high": 95.0, "close": 92.0}],
             "prev_close": 92.0,
             "bands": [{"kind": "demand", "lo": 88.0, "hi": 94.0,
                        "touches": 3, "strength": 55.0}]}
    res = IZ.warm(symbols=("SPY",), loader=lambda s: frame,
                  store_docs={"SPY": stale}, today=date(2026, 12, 8), coll=None)
    entry = res["doc"]["indexes"]["SPY"]
    board = entry["resolutions"][IZ.RESOLUTION_BOARD]
    fine = entry["resolutions"][IZ.RESOLUTION_FINE]
    assert board["as_of"] == fine["as_of"], (board["as_of"], fine["as_of"])
    assert board["close"] == fine["close"]
    assert entry["as_of"] == fine["as_of"]
    # …and the stale band is gone: it was rebuilt from the same frame
    assert board["source"] == "computed"


def test_V2_NEGATIVE_a_board_doc_on_the_SAME_session_is_kept_as_stored():
    """The rebuild only fires on a disagreement — a healthy zone_store doc is
    still the served board set, and `source` still says zone_store."""
    import pandas as pd
    idx = pd.bdate_range("2026-03-02", periods=200)
    frame = pd.DataFrame({
        "open": [100 + (i % 13) for i in range(200)],
        "high": [103 + (i % 13) for i in range(200)],
        "low": [97 + (i % 13) for i in range(200)],
        "close": [100 + (i % 13) for i in range(200)],
        "volume": [1_000_000] * 200,
    }, index=idx)
    from supply_demand import zone_store as ZS
    same = IZ._as_of_of(IZ._build_doc(ZS, "SPY", frame, date(2026, 12, 8)))
    stored = {"symbol": "SPY", "date": same,
              "recent": [{"date": same, "low": 90.0, "high": 95.0, "close": 92.0}],
              "prev_close": 92.0,
              "bands": [{"kind": "demand", "lo": 88.0, "hi": 94.0,
                         "touches": 4, "strength": 66.0}]}
    res = IZ.warm(symbols=("SPY",), loader=lambda s: frame,
                  store_docs={"SPY": stored}, today=date(2026, 12, 8), coll=None)
    board = res["doc"]["indexes"]["SPY"]["resolutions"][IZ.RESOLUTION_BOARD]
    assert board["source"] == "zone_store"
    assert any(abs(b["lo"] - 88.0) < 1e-9 for b in board["bands"])


def test_V3_the_payload_names_the_resolution_the_page_opens_on():
    """The FE reads it off the PAYLOAD; it was only ever on the payload, so a
    read-level lookup was undefined on the real wire."""
    assert IZ.DEFAULT_RESOLUTION in (IZ.RESOLUTION_BOARD, IZ.RESOLUTION_FINE)
    out = IZ.empty_payload("nothing stored")
    assert out["default_resolution"] == IZ.DEFAULT_RESOLUTION


# ── an OPEN day is not an elapsed session (2026-09-17) ───────────────────────
#
# Found on the live wire minutes after the first warm: at 00:26 ET on 09-17,
# with bands drawn on the 09-16 close, the served note read "Bands are 1
# session old". That is the FRESHEST the strip is ever going to be — the job
# had just stored it — and the line that is supposed to mean "the overnight job
# broke" was firing every single day. `stale_days` (calendar) is right to say
# 1; `stale_sessions` is what the page prints, and today has not closed.

_ET = ZoneInfo("America/New_York")


def _at(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=_ET)


def test_an_open_session_has_not_aged_the_bands():
    """Midnight through the close on the day after the basis session: the
    calendar turned over, the structure did not."""
    for hh, mm in ((0, 26), (4, 15), (9, 31), (12, 0), (15, 59)):
        out = IZ.staleness("2026-09-16", now=_at(2026, 9, 17, hh, mm))
        assert out["stale_sessions"] == 0, (hh, mm, out)
        assert "session old" not in out["note"], (hh, mm, out["note"])
        assert "as of the 2026-09-16 session" in out["note"]
        # the CALENDAR count still tells the truth about the date
        assert out["stale_days"] == 1, out


def test_after_todays_close_the_bands_are_one_session_old():
    """The other half: once 09-17 prints its own closed bar, 09-16 structure IS
    a session behind, and the note has to say so."""
    out = IZ.staleness("2026-09-16", now=_at(2026, 9, 17, 16, 30))
    assert out["stale_sessions"] == 1
    assert "1 session old" in out["note"]


def test_a_missed_overnight_job_still_reads_stale():
    """NEGATIVE — the fix must not silence the real failure. Bands from Mon
    09-14 seen on Thu 09-17 morning: Tuesday's and Wednesday's sessions have
    both closed, so two sessions have elapsed however early in the day it
    is."""
    out = IZ.staleness("2026-09-14", now=_at(2026, 9, 17, 8, 0))
    assert out["stale_sessions"] == 2
    assert "2 sessions old" in out["note"]


def test_a_weekend_read_of_fridays_structure_never_cries_stale():
    """NEGATIVE — Sat/Sun are not sessions, so Friday's close is the last
    close, not a stale one. Pinned here because the open-day fix touches the
    same loop."""
    for day, hh in ((19, 10), (20, 18)):        # Sat, Sun
        out = IZ.staleness("2026-09-18", now=_at(2026, 9, day, hh))
        assert out["stale_sessions"] == 0, (day, out)
        assert "session old" not in out["note"]


def test_the_open_day_test_is_the_engines_own_clock_not_a_second_1600():
    """Rule #1 — no second copy of the 16:00 cutoff. `_bar_closed` has to reach
    for demand_reentry._session_fraction, the same clock split_today_partial
    uses to decide whether today's row is a real bar."""
    src = inspect.getsource(IZ._bar_closed)
    assert "_session_fraction" in src
    # strip the RAW docstring (`__doc__`, not getdoc — getdoc dedents, so the
    # replace silently misses and the scan reads the prose it just explained)
    assert "16" not in src.replace(IZ._bar_closed.__doc__ or "", "")


def test_a_broken_session_clock_never_invents_a_closed_bar():
    """NEGATIVE — if the import blows up, `_bar_closed` must answer False for
    today (do not age the bands on a guess), and never raise into the strip."""
    import builtins
    real = builtins.__import__

    def boom(name, *a, **k):
        if "demand_reentry" in name:
            raise ImportError("boom")
        return real(name, *a, **k)

    builtins.__import__ = boom
    try:
        assert IZ._bar_closed(date(2026, 9, 17), _at(2026, 9, 17, 16, 30)) is False
        assert IZ._bar_closed(date(2026, 9, 16), _at(2026, 9, 17, 16, 30)) is True
        out = IZ.staleness("2026-09-16", now=_at(2026, 9, 17, 16, 30))
        assert out["stale_sessions"] == 0
    finally:
        builtins.__import__ = real


def test_the_production_read_uses_the_live_clock_not_a_calendar_date():
    """`served()` passes `today=None`, so staleness resolves the live clock and
    an open session cannot age the bands on the page he is looking at. Pinned
    by equality with an explicit live clock rather than a hard number, because
    the answer legitimately changes at today's close."""
    now = datetime.now(_ET)
    basis = (now.date() - timedelta(days=1)).isoformat()
    assert IZ.staleness(basis) == IZ.staleness(basis, now=now)
    src = inspect.getsource(IZ.served)
    assert "staleness(basis, today=today" in src      # None in production
