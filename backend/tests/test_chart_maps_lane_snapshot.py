"""WP-SNAP — chart_maps/lane_snapshot.py + GET /chart-maps/lane-snapshot
(Auto-Pilot Chart Maps lanes, spec 2026-09-27 §3.7).

Hermetic: every board, every bounce-room read and the Mongo collection are
fakes. NEGATIVE cases carry the spec's names (closed day, no stop, ICT bearish,
earnings UPCOMING, bonde not an arrival, patterns forming, overnight down,
BLOCKED/WATCH, a raising builder, record=false, vcp/topping never adapted, a
payload with no stamp → None)."""
from __future__ import annotations

import asyncio
import sys
import types
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from chart_maps import lane_snapshot as LS

ET = ZoneInfo("America/New_York")
MON_RTH = datetime(2026, 9, 28, 10, 0, tzinfo=ET)          # a Monday, market open
SUNDAY = datetime(2026, 9, 27, 10, 0, tzinfo=ET)
THANKSGIVING = datetime(2026, 11, 26, 10, 0, tzinfo=ET)


# ── fakes ────────────────────────────────────────────────────────────────────
class FakeColl:
    def __init__(self):
        self.writes = []

    def replace_one(self, flt, doc, upsert=False):
        self.writes.append((flt, doc, upsert))


def _ent(verdict="READY", reasons=None, lo=9.37, hi=9.59, px=9.45, src="live"):
    return {"kind": "demand", "verdict": verdict, "reasons": list(reasons or []),
            "reason_short": ["x"] if reasons else [],
            "gates": {"room_ok": True, "prox_ok": True, "floor_state": "intact"},
            "band": {"lo": lo, "hi": hi} if lo is not None else None,
            "room": {"state": "ROOM", "room_pct": 8.0, "target": 10.21, "touches": 2},
            "print": {"px": px, "source": src}, "measured": {"status": "no_signal"}}


def _tile(sym, *, ent=None, lines=None, **extra):
    t = {"symbol": sym, "enterable": ent if ent is not None else _ent(),
         "lines": lines if lines is not None else [
             {"price": 9.45, "label": "BUY", "tone": "buy"},
             {"price": 9.23, "label": "STOP", "tone": "stop"},
             {"price": 10.21, "label": "TARGET", "tone": "target"}],
         "band_structure": {"ceiling": {"distance_pct": 8.04}, "floor": {"distance_pct": 0.0}},
         "badges": [{"text": "🎯 swept the stops", "tone": "good"}],
         "stats": [{"k": "room", "v": "+8.0%"}], "why": "back in its 2nd demand level"}
    t.update(extra)
    return t


def _row(sym, verdict="READY", reasons=None, px=9.45, cov="store", lo=9.37):
    return {"symbol": sym, "coverage": cov, "print": px,
            "enterable": _ent(verdict, reasons, lo=lo, px=px),
            "band_structure": {"ceiling": {"distance_pct": 6.0}, "floor": {"distance_pct": 0.5}}}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    from market_hours import gate
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)
    try:
        from trading import chart_maps_lanes  # noqa: F401  (WP-GEN, may not exist yet)
    except Exception:                                            # noqa: BLE001
        monkeypatch.setattr(LS, "_lanes_consts", lambda: ("cm_lane_snapshot", "cm-lanes-v1"))
    yield


@pytest.fixture
def coll(monkeypatch):
    c = FakeColl()
    monkeypatch.setattr(LS, "_snapshot_coll", lambda: c)
    return c


def _tiles_payload(monkeypatch, payloads: dict):
    monkeypatch.setattr(LS, "_tiles", lambda tab: payloads[tab])


def _bounce(monkeypatch, rows: dict, calls: list = None):
    def fake(symbols):
        if calls is not None:
            calls.append(list(symbols))
        return {s: rows[s] for s in symbols if s in rows}
    monkeypatch.setattr(LS, "_bounce_rows", fake)


def _stop_buffer():
    from trading import zone_edge_entry as ZEE
    return ZEE.STOP_BUFFER_PCT


# ── closed day ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("now,why", [(SUNDAY, "weekend"), (THANKSGIVING, "holiday")])
def test_closed_day_writes_nothing_and_builds_nothing(monkeypatch, coll, now, why):
    called = []
    monkeypatch.setitem(LS.ADAPTERS, "amd", lambda: called.append(1) or {})
    out = LS.run(["amd"], record=True, now=now)
    assert set(out) == {"skipped"} and out["skipped"].startswith(why)
    assert coll.writes == [] and called == []


# ── deep_demand (PLAN) ──────────────────────────────────────────────────────
def test_deep_demand_tile_without_stop_line_is_rejected_no_stop(monkeypatch):
    no_stop = _tile("NOSTP", lines=[{"price": 9.45, "label": "BUY", "tone": "buy"}])
    good = _tile("CTOS")
    _tiles_payload(monkeypatch, {"deep_demand": {"generated_at": "2026-09-28T13:50:00+00:00",
                                                 "tiles": [no_stop, good]}})
    res = LS.ADAPTERS["deep_demand"]()
    assert [c["symbol"] for c in res["candidates"]] == ["CTOS"]
    assert res["rejected"] == {"no_stop": 1}
    c = res["candidates"][0]
    assert c["plan"] == {"buy": 9.45, "stop": 9.23, "target": 10.21, "source": "served"}
    assert c["board_rank"] == 2 and c["enterable"]["verdict"] == "READY"
    assert res["universe_n"] == 2 and res["source_key"] == "generated_at"


def test_deep_demand_served_stop_at_or_above_print_is_rejected(monkeypatch):
    bad = _tile("HIGH", lines=[{"price": 9.45, "label": "BUY"}, {"price": 9.45, "label": "STOP"}])
    _tiles_payload(monkeypatch, {"deep_demand": {"generated_at": None, "tiles": [bad]}})
    res = LS.ADAPTERS["deep_demand"]()
    assert res["candidates"] == [] and res["rejected"] == {"stop_not_below_print": 1}


def test_blocked_and_watch_reads_are_rejected_with_their_reason(monkeypatch):
    blk = _tile("BLK", ent=_ent("BLOCKED", ["floor_swept"]))
    wat = _tile("WAT", ent=_ent("WATCH", ["reclaim"]))
    none = _tile("NOR", ent={})
    _tiles_payload(monkeypatch, {"deep_demand": {"tiles": [blk, wat, none]}})
    res = LS.ADAPTERS["deep_demand"]()
    assert res["candidates"] == []
    assert res["rejected"] == {"blocked: floor_swept": 1, "watch: reclaim": 1, "no_read": 1}
    assert res["rejected_syms"]["blocked: floor_swept"] == ["BLK"]


# ── ict (PLAN) ──────────────────────────────────────────────────────────────
def test_ict_bearish_is_rejected_bullish_entry_is_kept(monkeypatch):
    plan = {"entry": 101.52, "stop": 99.0, "target": 106.0}
    bear = _tile("ABT", ent=_ent(px=101.3), bias="bearish", state="entry",
                 plan={"entry": 101.52, "stop": 103.94})
    conf = _tile("CNF", ent=_ent(px=101.3), bias="bullish", state="confirmed", plan=plan)
    above = _tile("ABV", ent=_ent(px=101.3), bias="bullish", state="entry",
                  plan={"entry": 101.52, "stop": 102.0})
    ok = _tile("OKK", ent=_ent(px=101.3), bias="bullish", state="entry", plan=plan)
    _tiles_payload(monkeypatch, {"ict": {"generated_at": "2026-09-28T09:40:00-04:00",
                                         "tiles": [bear, conf, above, ok]}})
    res = LS.ADAPTERS["ict"]()
    assert [c["symbol"] for c in res["candidates"]] == ["OKK"]
    assert res["rejected"] == {"not_bullish": 1, "not_entry_state": 1,
                               "stop_not_below_print": 1}
    assert res["candidates"][0]["plan"]["stop"] == 99.0
    assert res["candidates"][0]["served"]["bias"] == "bullish"


def test_ict_bullish_but_not_ready_is_rejected(monkeypatch):
    t = _tile("NRD", ent=_ent("BLOCKED", ["room"], px=101.3), bias="bullish",
              state="entry", plan={"entry": 101.5, "stop": 99.0})
    _tiles_payload(monkeypatch, {"ict": {"tiles": [t]}})
    assert LS.ADAPTERS["ict"]()["rejected"] == {"blocked: room": 1}


# ── LIST tiles ──────────────────────────────────────────────────────────────
def test_amd_ready_tile_gets_band_floor_stop_from_the_imported_buffer(monkeypatch):
    t = _tile("AMDX", lines=[], ent=_ent(lo=33.83, hi=34.4, px=34.35),
              amd_read={"grade": "raided", "phase": "manipulation"},
              bars=[{"c": 1}] * 50, curves=[{"x": 1}])
    _tiles_payload(monkeypatch, {"amd": {"built_at": "2026-09-25T21:20:21.525000",
                                         "tiles": [t]}})
    res = LS.ADAPTERS["amd"]()
    c = res["candidates"][0]
    assert c["plan"]["source"] == "band_floor"
    assert c["plan"]["stop"] == pytest.approx(33.83 * (1 - _stop_buffer() / 100), abs=1e-4)
    assert c["served"]["amd_grade"] == "raided"
    # the naive Mongo stamp is UTC: the post-close build is 17:20 ET
    got = datetime.fromtimestamp(res["source_as_of"], tz=ET)
    assert (got.date(), got.hour, got.minute) == (date(2026, 9, 25), 17, 20)


def test_list_tile_without_band_is_rejected_no_stop(monkeypatch):
    t = _tile("NOBAND", lines=[], ent=_ent(lo=None))
    _tiles_payload(monkeypatch, {"keltner": {"built_at": None, "tiles": [t]}})
    res = LS.ADAPTERS["keltner"]()
    assert res["candidates"] == [] and res["rejected"] == {"no_stop": 1}


def test_candidate_is_slim_no_bars_no_curves_and_why_capped(monkeypatch):
    t = _tile("BIG", why="w" * 900, bars=[{"c": 1}] * 300, curves=[{"k": 1}] * 50,
              markers=[{"d": 1}], key_levels={"x": 1}, _knife=True)
    _tiles_payload(monkeypatch, {"deep_demand": {"tiles": [t]}})
    c = LS.ADAPTERS["deep_demand"]()["candidates"][0]
    assert set(c) == {"symbol", "board_rank", "plan", "enterable", "band_structure",
                      "badges", "stats", "why", "print", "served"}
    assert len(c["why"]) == LS.WHY_MAX_CHARS == 280
    assert "measured" not in c["enterable"] and "print" not in c["enterable"]
    assert c["badges"] == ["🎯 swept the stops"] and c["stats"] == [["room", "+8.0%"]]
    assert c["band_structure"] == {"ceiling_pct": 8.04, "floor_pct": 0.0}


def test_candidates_capped_at_board_limit(monkeypatch):
    from chart_maps import board as B
    tiles = [_tile(f"S{i}") for i in range(B.LIMIT_MAX + 5)]
    _tiles_payload(monkeypatch, {"deep_demand": {"tiles": tiles}})
    res = LS.ADAPTERS["deep_demand"]()
    assert len(res["candidates"]) == B.LIMIT_MAX
    assert res["rejected"] == {"over_limit": 5}


# ── n/a tile tabs ───────────────────────────────────────────────────────────
def test_earnings_upcoming_is_never_a_candidate_even_when_ready(monkeypatch):
    from chart_maps import earnings as E
    up = _tile("UPC", ent={}, phase=E.UPCOMING)
    re_ = _tile("RCT", ent={}, phase=E.REACTED)
    _tiles_payload(monkeypatch, {"earnings": {"as_of": "2026-09-28", "tiles": [up, re_]}})
    calls = []
    _bounce(monkeypatch, {"UPC": _row("UPC"), "RCT": _row("RCT")}, calls)
    res = LS.ADAPTERS["earnings"]()
    assert [c["symbol"] for c in res["candidates"]] == ["RCT"]
    assert res["rejected"] == {"upcoming": 1}
    assert calls == [["RCT"]]                          # UPC was never even read
    assert res["candidates"][0]["board_rank"] == 2


def test_undervalue_pending_and_unavailable_rows_are_rejected(monkeypatch):
    tiles = [_tile("PND", ent={}), _tile("UNV", ent={}), _tile("OKR", ent={})]
    _tiles_payload(monkeypatch, {"undervalue": {"generated_at": None, "tiles": tiles}})
    _bounce(monkeypatch, {"UNV": {"symbol": "UNV", "coverage": "unavailable"},
                          "OKR": _row("OKR")})
    res = LS.ADAPTERS["undervalue"]()
    assert [c["symbol"] for c in res["candidates"]] == ["OKR"]
    assert res["rejected"] == {"pending": 1, "unavailable": 1}
    assert res["source_as_of"] is None                 # no stamp served → None


# ── row adapters ────────────────────────────────────────────────────────────
def _stub_bonde(monkeypatch, board, latest):
    """sepa.bonde / sepa.scanner as stubs: importing the real scanner pulls
    sepa/insider.py, whose module-level asyncio.Lock() needs a current event
    loop on Python 3.9 — gone after any earlier test's asyncio.run(). The
    adapter imports both lazily, so sys.modules + the package attribute win."""
    import sepa
    bonde = types.ModuleType("sepa.bonde")
    bonde.NEW_DAYS = 5
    bonde.board = lambda **kw: board
    scanner = types.ModuleType("sepa.scanner")
    scanner.load_latest = lambda: latest
    for name, mod in (("bonde", bonde), ("scanner", scanner)):
        monkeypatch.setitem(sys.modules, f"sepa.{name}", mod)
        monkeypatch.setattr(sepa, name, mod, raising=False)


def test_bonde_not_new_is_rejected_not_arrival(monkeypatch):
    board = {"scan_ts": None, "sections": {
        "pivot": [{"symbol": "PIV", "is_new": True}],
        "explosive": [{"symbol": "OLD", "is_new": False}, {"symbol": "NEW", "is_new": True}],
        "strong": [], "steady": [{"symbol": "STD", "is_new": False}],
        "rejected": [{"symbol": "REJ", "is_new": True}]}}
    _stub_bonde(monkeypatch, board, {"generated_at": 1790368296})
    _bounce(monkeypatch, {"NEW": _row("NEW")})
    res = LS.ADAPTERS["bonde"]()
    assert [c["symbol"] for c in res["candidates"]] == ["NEW"]
    assert res["rejected"] == {"not_arrival": 2}
    assert res["source_as_of"] == 1790368296
    assert res["source_key"] == "sepa_scan.generated_at"


def test_bonde_with_no_stamp_anywhere_is_none(monkeypatch):
    _stub_bonde(monkeypatch, {"scan_ts": None, "sections": {}}, None)
    res = LS.ADAPTERS["bonde"]()
    assert res["source_as_of"] is None and res["source_key"] is None


def test_patterns_forming_is_rejected(monkeypatch):
    from patterns import scan
    monkeypatch.setattr(scan, "latest", lambda: {"generated_at": 1790370439, "results": [
        {"symbol": "FRM", "status": "forming", "pattern": "cup_with_handle"},
        {"symbol": "CNF", "status": "confirmed", "pattern": "double_bottom"}]})
    _bounce(monkeypatch, {"FRM": _row("FRM"), "CNF": _row("CNF")})
    res = LS.ADAPTERS["patterns"]()
    assert [c["symbol"] for c in res["candidates"]] == ["CNF"]
    assert res["rejected"] == {"not_confirmed": 1}
    assert res["candidates"][0]["served"]["pattern"] == "double_bottom"
    assert res["source_as_of"] == 1790370439


def test_patterns_with_no_scan_yet_has_no_stamp(monkeypatch):
    from patterns import scan
    monkeypatch.setattr(scan, "latest", lambda: {"results": [], "generated_at": 0})
    assert LS.ADAPTERS["patterns"]()["source_as_of"] is None


def test_overnight_down_is_rejected(monkeypatch):
    from daytrading import premarket
    monkeypatch.setattr(premarket, "gappers", lambda *a, **k: {
        "as_of": "2026-09-28T13:31:00+00:00",
        "gappers": [{"symbol": "DWN", "direction": "down"}, {"symbol": "UPP", "direction": "up"}]})
    _bounce(monkeypatch, {"DWN": _row("DWN"), "UPP": _row("UPP")})
    res = LS.ADAPTERS["overnight"]()
    assert [c["symbol"] for c in res["candidates"]] == ["UPP"]
    assert res["rejected"] == {"not_up": 1}


def test_potus_and_gnt_need_their_served_arrival_flags(monkeypatch):
    from political import api as PA
    from traders import feed
    monkeypatch.setattr(PA, "_board", lambda limit, today=None: {
        "as_of": "2026-09-28", "entries": [{"ticker": "OLDP", "is_new": False},
                                           {"ticker": "NEWP", "is_new": True}]})
    monkeypatch.setattr(feed, "board", lambda **kw: {
        "newest_post_at": "2026-09-24T17:35:02+00:00",
        "tickers": [{"symbol": "STL", "fresh": False}, {"symbol": "FRS", "fresh": True}]})
    monkeypatch.setattr(feed, "stored", lambda **kw: [{"first_seen": "2026-09-25T12:00:00+00:00"}])
    _bounce(monkeypatch, {s: _row(s) for s in ("OLDP", "NEWP", "STL", "FRS")})
    p = LS.ADAPTERS["potus"]()
    assert [c["symbol"] for c in p["candidates"]] == ["NEWP"] and p["rejected"] == {"not_arrival": 1}
    got = datetime.fromtimestamp(p["source_as_of"], tz=ET)
    assert (got.date(), got.hour) == (date(2026, 9, 28), 16)      # bare date → the close
    g = LS.ADAPTERS["gnt"]()
    assert [c["symbol"] for c in g["candidates"]] == ["FRS"] and g["rejected"] == {"not_fresh": 1}
    assert g["source_key"] == "newest_post.first_seen"
    assert g["source_as_of"] == datetime(2026, 9, 25, 12, tzinfo=timezone.utc).timestamp()


def test_session_needs_a_long_served_trade(monkeypatch):
    from supply_demand import session_board
    monkeypatch.setattr(session_board, "cached_or_warm", lambda *a, **k: {"as_of": None, "rows": [
        {"symbol": "NOT", "signal": {"trade": {}}},
        {"symbol": "SHT", "signal": {"trade": {"entry": 10.0, "stop": 10.5}}},
        {"symbol": "LNG", "signal": {"action": "BUY",
                                     "trade": {"entry": 9.5, "stop": 9.2, "target1": 10.4}}}]})
    _bounce(monkeypatch, {"LNG": _row("LNG", px=9.45)})
    res = LS.ADAPTERS["session"]()
    assert [c["symbol"] for c in res["candidates"]] == ["LNG"]
    assert res["rejected"] == {"no_stop": 1, "not_long": 1}
    assert res["candidates"][0]["plan"] == {"buy": 9.5, "stop": 9.2, "target": 10.4,
                                            "source": "served"}
    assert res["source_as_of"] is None                 # warming board: no stamp, no trade


# ── the roster boundary ─────────────────────────────────────────────────────
def test_vcp_topping_and_not_a_lane_tabs_are_never_adapted():
    for sid in ("vcp", "topping", "support", "holdings", "ema_frames", "news", "winners",
                "supply", "zero_dte"):
        assert sid not in LS.ADAPTERS
    # existing lanes keep their own engines — never a generic snapshot
    for sid in ("zones", "breaking", "quick_bounce", "catalysts", "hot_pullback", "signals"):
        assert sid not in LS.ADAPTERS


def test_vcp_passed_explicitly_is_skipped_and_not_written(coll):
    out = LS.run(["vcp", "topping"], record=True, now=MON_RTH)
    assert out == {"vcp": {"skipped": "not a snapshot lane"},
                   "topping": {"skipped": "not a snapshot lane"}}
    assert coll.writes == []


def test_default_sids_are_the_generic_lanes_that_are_on(monkeypatch):
    import trading
    from trading import exit_engine as EE
    roster = ({"sid": "zones", "lane": "zone_edge"}, {"sid": "amd", "lane": "generic"},
              {"sid": "keltner", "lane": "generic"}, {"sid": "deep_demand", "lane": "generic"})
    st = types.SimpleNamespace(ROSTER=roster, lane_sids=lambda: tuple(r["sid"] for r in roster))
    pc = types.SimpleNamespace(strategy_on=lambda sid, cfg, mode: sid in ("zones", "amd",
                                                                           "deep_demand"))
    for name, mod in (("strategy_tags", st), ("program_caps", pc)):
        monkeypatch.setitem(sys.modules, f"trading.{name}", mod)
        monkeypatch.setattr(trading, name, mod, raising=False)
    monkeypatch.setattr(EE, "get_config", lambda: {"cm_program": True})
    monkeypatch.setattr(EE, "_broker_mode", lambda: "paper")
    assert LS._default_sids() == ["amd", "deep_demand"]


# ── the job ─────────────────────────────────────────────────────────────────
def test_builder_that_raises_sets_error_and_others_still_build(monkeypatch, coll):
    def boom():
        raise RuntimeError("cold cache")
    monkeypatch.setitem(LS.ADAPTERS, "amd", boom)
    monkeypatch.setitem(LS.ADAPTERS, "growth", lambda: {
        "candidates": [{"symbol": "G1"}], "universe_n": 3, "rejected": {"x": 2},
        "source_as_of": 1790500000.0, "source_key": "built_at"})
    out = LS.run(["amd", "growth"], record=True, now=MON_RTH)
    assert out["amd"]["error"].startswith("RuntimeError: cold cache") and out["amd"]["n"] == 0
    assert out["growth"]["error"] is None and out["growth"]["n"] == 1
    docs = {d["_id"]: d for _, d, _ in coll.writes}
    assert set(docs) == {"amd", "growth"}
    assert docs["amd"]["candidates"] == [] and docs["amd"]["source_as_of"] is None
    g = docs["growth"]
    assert g["day"] == "2026-09-28" and g["as_of"].startswith("2026-09-28T10:00")
    assert g["source_as_of"] == 1790500000.0 and g["source_key"] == "built_at"
    assert g["source_as_of"] != MON_RTH.timestamp()
    assert g["sid"] == g["tab"] == "growth" and g["universe_n"] == 3
    assert isinstance(g["built_ms"], int) and g["adapter_version"]


def test_record_false_never_opens_or_writes_mongo(monkeypatch):
    opened = []
    monkeypatch.setattr(LS, "_snapshot_coll", lambda: opened.append(1) or FakeColl())
    monkeypatch.setitem(LS.ADAPTERS, "growth", lambda: {"candidates": [], "source_as_of": None})
    out = LS.run(["growth"], record=False, now=MON_RTH)
    assert opened == [] and out["growth"]["written"] is False


def test_no_stamp_is_stored_as_none_never_the_write_time(monkeypatch, coll):
    _tiles_payload(monkeypatch, {"gabbar": {"generated_at": None, "tiles": [_tile("GAB")]}})
    LS.run(["gabbar"], record=True, now=MON_RTH)
    doc = coll.writes[0][1]
    assert doc["source_as_of"] is None and doc["source_key"] is None and doc["as_of"]


def test_mongo_down_still_reports(monkeypatch):
    def down():
        raise RuntimeError("no mongo")
    monkeypatch.setattr(LS, "_snapshot_coll", down)
    monkeypatch.setitem(LS.ADAPTERS, "growth", lambda: {"candidates": []})
    out = LS.run(["growth"], record=True, now=MON_RTH)
    assert out["growth"]["written"] is False


# ── source time parsing (critic 11) ─────────────────────────────────────────
def test_parse_source_as_of_forms():
    P = LS.parse_source_as_of
    iso = datetime(2026, 9, 28, 2, 25, 33, tzinfo=timezone.utc).timestamp()
    assert P("2026-09-28T02:25:33+00:00") == iso
    assert P("2026-09-28T02:25:33Z") == iso
    assert P("2026-09-27T22:25:33-04:00") == iso
    assert P("2026-09-28T02:25:33") == iso                     # naive = UTC
    assert P(datetime(2026, 9, 28, 2, 25, 33)) == iso
    assert P(1790370439) == 1790370439.0
    assert P(1790370439000) == pytest.approx(1790370439.0)    # ms
    close = datetime(2026, 9, 25, 16, 0, tzinfo=ET).timestamp()
    assert P("2026-09-25") == close and P(date(2026, 9, 25)) == close


@pytest.mark.parametrize("junk", [None, "", "   ", "not a date", "2026-13-40", 0, -5,
                                  True, False, float("nan"), [], {}])
def test_parse_source_as_of_junk_is_none(junk):
    assert LS.parse_source_as_of(junk) is None


def test_payload_with_no_stamp_is_none():
    assert LS._stamp({"tiles": []}, "generated_at", "as_of") == (None, None)
    assert LS._stamp({"generated_at": None, "as_of": "junk"}, "generated_at", "as_of") == (None, None)
    assert LS._stamp(None, "as_of") == (None, None)


# ── the route ───────────────────────────────────────────────────────────────
def test_route_direct_call_defaults_to_no_write(monkeypatch):
    from chart_maps import api
    seen = []
    monkeypatch.setattr(LS, "run", lambda sids, record: seen.append((sids, record)) or {})
    asyncio.run(api.chart_maps_lane_snapshot())                # Query objects, as in-container
    asyncio.run(api.chart_maps_lane_snapshot(record=True, sids="deep_demand, amd,"))
    assert seen == [(None, False), (["deep_demand", "amd"], True)]


def test_route_is_registered_as_get():
    from chart_maps import api
    paths = {(r.path, tuple(sorted(r.methods))) for r in api.router.routes}
    assert ("/chart-maps/lane-snapshot", ("GET",)) in paths
