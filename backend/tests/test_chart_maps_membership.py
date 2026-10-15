"""Chart Maps tab membership snapshot (Ajay 2026-10-12, his-call #8).

`chart_maps/membership.py` + the ONE hook in `board.board()` + the ONE hook in
`sepa.bonde_api.bonde_board`. Pins the writer rule (default page request only,
read off `board()`'s own signature [C6], `min_room` None-or-MIN_ROOM_DEFAULT
[C1]), the as-of = the memo block's own `built_at` [C2], `limit` carried [C8],
ONE find per arrivals read, nothing about users, and that nothing here can
break a board or touch a rule (Rule #10).
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from chart_maps import board as B
from chart_maps import membership as M
from supply_demand import room_floor as RF

BACKEND = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------
# fakes (the `test_growth_arrivals.py` FakeColl shape, with replace_one)
# --------------------------------------------------------------------------
class FakeColl:
    def __init__(self):
        self.docs: dict = {}
        self.find_calls = 0
        self.writes = 0

    def replace_one(self, flt, doc, upsert=False):
        self.writes += 1
        _id = flt["_id"]
        if _id not in self.docs and not upsert:
            return
        self.docs[_id] = dict(doc)

    def find(self, flt, projection=None, *a, **k):
        self.find_calls += 1
        out = list(self.docs.values())
        if projection:
            keep = {k for k, v in projection.items() if v}
            out = [{k: v for k, v in d.items() if k in keep or k == "_id"}
                   for d in out]
        return out


class FakeDB:
    def __init__(self):
        self.coll = FakeColl()

    def __getitem__(self, name):
        assert name == M.COLL
        return self.coll


class BoomDB:
    def __getitem__(self, name):
        raise RuntimeError("mongo gone")


def _defaults() -> dict:
    """Every `board()` parameter at its SIGNATURE default, with the four page
    overrides (limit=LIMIT_MAX; the rest already equal their defaults)."""
    d = {n: p.default for n, p in inspect.signature(B.board).parameters.items()}
    d["limit"] = B.LIMIT_MAX
    return d


def _req(**over) -> dict:
    r = _defaults()
    r.update(over)
    return r


def _tiles(*syms):
    return [{"symbol": s} for s in syms]


# --------------------------------------------------------------------------
# record
# --------------------------------------------------------------------------
def test_record_writes_ONE_doc_with_the_exact_keys_upper_deduped_in_order():
    db = FakeDB()
    assert M.record("zones", ["aaa", "BBB", "aaa", " ccc ", "", None, "bbb"],
                    source_as_of="2026-10-12T10:00:00-04:00", ttl_sec=None,
                    ttl_name=None, params_note="note", limit=80, db=db) is True
    assert db.coll.writes == 1
    doc = db.coll.docs["zones"]
    assert set(doc) == {"_id", "tab", "symbols", "n", "built_at", "source_as_of",
                        "ttl_sec", "ttl_name", "params_note", "limit"}
    assert doc["symbols"] == ["AAA", "BBB", "CCC"]
    assert doc["n"] == 3 and doc["tab"] == "zones" and doc["limit"] == 80
    assert datetime.fromisoformat(doc["built_at"]).tzinfo is not None


def test_record_second_build_REPLACES_the_tab_doc_never_appends():
    db = FakeDB()
    M.record("ath", ["AAA", "BBB"], db=db)
    M.record("ath", ["CCC"], db=db)
    assert list(db.coll.docs) == ["ath"]
    assert db.coll.docs["ath"]["symbols"] == ["CCC"]


def test_NEGATIVE_record_with_empty_symbols_never_writes():
    db = FakeDB()
    M.record("ath", ["AAA"], db=db)
    assert M.record("ath", [], db=db) is False
    assert M.record("ath", ["", None], db=db) is False
    assert db.coll.docs["ath"]["symbols"] == ["AAA"]
    assert db.coll.writes == 1


def test_NEGATIVE_record_on_exception_returns_False_never_raises(caplog):
    with caplog.at_level(logging.WARNING, logger="chart_maps.membership"):
        assert M.record("ath", ["AAA"], db=BoomDB()) is False
    assert any("membership" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("tab", ["supply", "growth"])
def test_NEGATIVE_record_skips_supply_alias_and_growth_itself(tab):
    db = FakeDB()
    assert M.record(tab, ["AAA"], db=db) is False
    assert db.coll.writes == 0


def test_NEGATIVE_record_without_mongo_returns_False(monkeypatch):
    monkeypatch.setattr(M, "_db", lambda db=None: None)
    assert M.record("ath", ["AAA"]) is False


def test_NEGATIVE_doc_carries_nothing_about_users():
    db = FakeDB()
    M.record_board("zones", {"tiles": _tiles("AAA")}, request=_req(tab="zones"),
                   db=db)
    M.record_bonde({"sections": {"pivot": [{"symbol": "BBB"}]}}, db=db)
    for doc in db.coll.docs.values():
        keys = {k.lower() for k in doc}
        for bad in ("user", "email", "holdings", "owner", "account"):
            assert not any(bad in k for k in keys), (bad, keys)
        assert "@" not in repr(doc)


# --------------------------------------------------------------------------
# is_default_request [C6] [C1]
# --------------------------------------------------------------------------
def test_signature_defaults_with_the_overrides_are_default():
    assert M.is_default_request(**_req()) is True


def test_python_default_limit_is_NOT_the_page_request():
    assert B.LIMIT_DEFAULT != B.LIMIT_MAX
    assert M.is_default_request(**_req(limit=B.LIMIT_DEFAULT)) is False


def test_C6_unknown_key_is_False_with_one_warning_never_TypeError(caplog):
    with caplog.at_level(logging.WARNING, logger="chart_maps.membership"):
        assert M.is_default_request(**_req(future_arg=1)) is False
    warns = [r for r in caplog.records if "unknown board() arg" in r.getMessage()]
    assert len(warns) == 1 and "future_arg" in warns[0].getMessage()


def test_NEGATIVE_a_missing_signature_parameter_is_not_default():
    r = _req()
    r.pop("depth")
    assert M.is_default_request(**r) is False


@pytest.mark.parametrize("name", [n for n in inspect.signature(B.board).parameters
                                  if n != "tab"])
def test_every_signature_parameter_off_default_skips_the_write(name):
    """Read from the SIGNATURE, so a new board() argument is covered here
    automatically [C6]."""
    default = _req()[name]
    if name == "min_room":
        off = 0.0
    elif isinstance(default, bool):
        off = not default
    elif isinstance(default, int):
        off = default + 1
    elif default is None:
        off = "x"
    else:
        off = str(default) + "_not_default"
    db = FakeDB()
    assert M.record_board("zones", {"tiles": _tiles("AAA")},
                          request=_req(tab="zones", **{name: off}), db=db) is False
    assert db.coll.writes == 0


def test_min_tier_follows_the_tab_default_2026_10_14():
    """`min_tier` None = the tab's own default (board.default_min_tier); 🎢 High Beta
    opens with "any" (Ajay 2026-10-14), every other tab with DEFAULT_MIN_TIER."""
    assert M.is_default_request(**_req(tab="zones", min_tier=None)) is True
    assert M.is_default_request(**_req(tab="zones", min_tier=B.DEFAULT_MIN_TIER)) is True
    assert M.is_default_request(**_req(tab="high_beta", min_tier="any")) is True
    # NEGATIVE: a floor the reader chose is a filtered view on either tab
    assert M.is_default_request(**_req(tab="zones", min_tier="any")) is False
    assert M.is_default_request(**_req(tab="high_beta", min_tier=B.DEFAULT_MIN_TIER)) is False
    db = FakeDB()
    assert M.record_board("high_beta", {"tiles": _tiles("AAA")},
                          request=_req(tab="high_beta", min_tier="any"), db=db) is True
    assert db.coll.writes == 1


def test_C1_REPLAY_the_page_zones_query_writes():
    """The page sends limit=80 and min_room=5 explicitly on the room tabs."""
    db = FakeDB()
    page = _req(tab="zones", limit=80, min_room=5.0)
    assert page["limit"] == B.LIMIT_MAX and float(RF.MIN_ROOM_DEFAULT) == 5.0
    assert M.record_board("zones", {"tiles": _tiles("AAA", "BBB")}, request=page,
                          db=db) is True
    assert db.coll.docs["zones"]["symbols"] == ["AAA", "BBB"]
    assert db.coll.docs["zones"]["limit"] == 80


def test_C1_REPLAY_the_real_http_query_through_the_api_handler(monkeypatch):
    """The real door: `GET /chart-maps?tab=zones&limit=80&min_room=5` over
    HTTP (FastAPI resolves every omitted Query to its default) → the
    handler's coercion → `board()` → the hook."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from chart_maps import api as A
    _stub_board(monkeypatch)
    seen = []
    monkeypatch.setattr(M, "record_board",
                        lambda tab, out, *, request, db=None:
                        seen.append(M.is_default_request(**request)) or True)
    app = FastAPI()
    app.include_router(A.router)
    c = TestClient(app)
    assert c.get("/chart-maps?tab=zones&limit=80&min_room=5").status_code == 200
    assert seen == [True]
    seen.clear()
    assert c.get("/chart-maps?tab=zones&limit=80&min_room=0").status_code == 200
    assert seen == [False]
    seen.clear()
    assert c.get("/chart-maps?tab=vcp&limit=80").status_code == 200
    assert seen == [True]


def test_NEGATIVE_a_direct_handler_call_with_Query_objects_never_writes(monkeypatch):
    """In-container smoke calls hand the handler Query OBJECTS; its coercion
    then picks non-default fallbacks, so such a call never snapshots."""
    from chart_maps import api as A
    _stub_board(monkeypatch)
    seen = []
    monkeypatch.setattr(M, "record_board",
                        lambda tab, out, *, request, db=None:
                        seen.append(M.is_default_request(**request)) or True)
    asyncio.run(A.chart_maps(tab="zones", limit=80, min_room=5.0))
    assert seen == [False]


def test_C1_min_room_zero_skips_the_write():
    db = FakeDB()
    assert M.record_board("zones", {"tiles": _tiles("AAA")},
                          request=_req(tab="zones", min_room=0), db=db) is False
    assert db.coll.writes == 0


def test_C1_min_room_None_writes_the_session_board_path():
    db = FakeDB()
    assert M.record_board("deep_demand", {"tiles": _tiles("AAA")},
                          request=_req(tab="deep_demand", min_room=None), db=db)


def test_NEGATIVE_studies_limit_days_each_skip():
    for over in ({"studies": True}, {"limit": 79}, {"days": B.BARS_DEFAULT + 1}):
        db = FakeDB()
        assert M.record_board("vcp", {"tiles": _tiles("AAA")},
                              request=_req(tab="vcp", **over), db=db) is False
        assert db.coll.writes == 0, over


def test_NEGATIVE_a_FastAPI_Query_object_is_never_default():
    from fastapi import Query
    assert M.is_default_request(**_req(universe=Query("full"))) is False


# --------------------------------------------------------------------------
# record_board
# --------------------------------------------------------------------------
def test_record_board_skips_warming():
    db = FakeDB()
    out = {"warming": True, "tiles": _tiles("AAA")}
    assert M.record_board("ath", out, request=_req(tab="ath"), db=db) is False
    assert db.coll.writes == 0


@pytest.mark.parametrize("tab", ["supply", "growth"])
def test_NEGATIVE_record_board_skips_supply_and_growth(tab):
    db = FakeDB()
    assert M.record_board(tab, {"tiles": _tiles("AAA")}, request=_req(tab=tab),
                          db=db) is False
    assert db.coll.writes == 0


def test_record_board_writes_a_default_request_with_ttl_and_as_of():
    db = FakeDB()
    out = {"tiles": _tiles("AAA", "BBB"),
           "ath_board": {"built_at": "2026-10-12T10:00:00-04:00"}}
    assert M.record_board("ath", out, request=_req(tab="ath"), db=db) is True
    doc = db.coll.docs["ath"]
    from chart_maps import ath_tab
    assert doc["ttl_sec"] == ath_tab.MEMO_TTL_SEC
    assert doc["ttl_name"] == "chart_maps.ath_tab.MEMO_TTL_SEC"
    assert doc["source_as_of"] == "2026-10-12T10:00:00-04:00"
    assert "default page request" in doc["params_note"]


def test_NEGATIVE_error_block_with_empty_tiles_never_overwrites():
    db = FakeDB()
    M.record_board("fallen", {"tiles": _tiles("AAA")}, request=_req(tab="fallen"), db=db)
    assert M.record_board("fallen", {"tiles": [], "fallen_board": {"built_at": None}},
                          request=_req(tab="fallen"), db=db) is False
    assert db.coll.docs["fallen"]["symbols"] == ["AAA"]


# --------------------------------------------------------------------------
# ttl_for_tab / source_as_of_for [C2]
# --------------------------------------------------------------------------
@pytest.mark.parametrize("tab,mod", [("key_levels", "key_levels_tab"),
                                     ("ath", "ath_tab"), ("fallen", "fallen_tab"),
                                     ("dual_momentum", "dual_momentum_tab"),
                                     ("resiliency", "resiliency_tab")])
def test_ttl_for_tab_returns_the_named_module_constant(tab, mod):
    import importlib
    m = importlib.import_module("chart_maps." + mod)
    assert M.ttl_for_tab(tab, {}) == (m.MEMO_TTL_SEC,
                                      "chart_maps.%s.MEMO_TTL_SEC" % mod)


def test_drop10_ttl_reads_mode_off_its_block():
    from chart_maps import drop10_tab as D
    live = M.ttl_for_tab("drop10", {"drop10_board": {"mode": D.MODE_LIVE}})
    assert live == (D.ttl_for(D.MODE_LIVE), "chart_maps.drop10_tab.LIVE_TTL_SEC")
    assert live[0] == D.LIVE_TTL_SEC
    closed = M.ttl_for_tab("drop10", {"drop10_board": {"mode": D.MODE_CLOSED}})
    assert closed == (D.ttl_for(D.MODE_CLOSED), "chart_maps.drop10_tab.CLOSED_TTL_SEC")
    assert M.ttl_for_tab("drop10", {}) == (None, None)


@pytest.mark.parametrize("tab", ["vcp", "zones", "deep_demand", "undervalue",
                                 "gabbar", "amd", "earnings", "winners"])
def test_NEGATIVE_per_request_tabs_have_no_ttl(tab):
    assert M.ttl_for_tab(tab, {}) == (None, None)


@pytest.mark.parametrize("tab,key", sorted(M.MEMO_BLOCK_KEY.items()))
def test_C2_source_as_of_is_the_memo_blocks_own_built_at(tab, key):
    out = {key: {"built_at": "2026-10-12T09:00:00-04:00"},
           "built_at": "2026-10-12T11:00:00-04:00"}
    assert M.source_as_of_for(tab, out) == "2026-10-12T09:00:00-04:00"
    assert M.source_as_of_for(tab, {key: {"built_at": None}}) is None
    assert M.source_as_of_for(tab, {key: {"built_at": "None"}}) is None


def test_source_as_of_falls_back_to_top_level_stamps_for_per_request_tabs():
    assert M.source_as_of_for("vcp", {"as_of": "2026-10-12T09:00:00"}) == "2026-10-12T09:00:00"
    assert M.source_as_of_for("vcp", {"generated_at": datetime(2026, 10, 12, 9)}) \
        == "2026-10-12T09:00:00"
    assert M.source_as_of_for("vcp", {"built_at": "a", "as_of": "b"}) == "a"
    assert M.source_as_of_for("vcp", {}) is None


# --------------------------------------------------------------------------
# is_stale [C2]
# --------------------------------------------------------------------------
def _stale_from_block(age_sec: int):
    from chart_maps import ath_tab
    db = FakeDB()
    block_at = (NOW - timedelta(seconds=age_sec)).isoformat()
    M.record("ath", ["AAA"], built_at=NOW.isoformat(), source_as_of=block_at,
             ttl_sec=ath_tab.MEMO_TTL_SEC, ttl_name="x", db=db)
    return M.is_stale(db.coll.docs["ath"], NOW)


def test_C2_TTL_plus_one_second_old_block_is_stale_though_written_now():
    from chart_maps import ath_tab
    assert _stale_from_block(ath_tab.MEMO_TTL_SEC + 1) is True


def test_C2_TTL_minus_one_second_is_fresh():
    from chart_maps import ath_tab
    assert _stale_from_block(ath_tab.MEMO_TTL_SEC - 1) is False


def test_is_stale_falls_back_to_built_at_and_assumes_naive_is_utc():
    doc = {"ttl_sec": 60, "source_as_of": None,
           "built_at": (NOW - timedelta(seconds=61)).replace(tzinfo=None).isoformat()}
    assert M.is_stale(doc, NOW) is True


def test_NEGATIVE_is_stale_none_without_ttl_or_with_garbage():
    assert M.is_stale({"ttl_sec": None, "source_as_of": NOW.isoformat()}, NOW) is None
    assert M.is_stale({"ttl_sec": 60, "source_as_of": "not a date",
                       "built_at": "nope"}, NOW) is None
    assert M.is_stale({"ttl_sec": 60}, NOW) is None
    assert M.is_stale(None, NOW) is None


# --------------------------------------------------------------------------
# record_bonde
# --------------------------------------------------------------------------
def test_record_bonde_walks_SECTIONS_first_placement_wins_rejected_ignored():
    from sepa import bonde as BD
    db = FakeDB()
    payload = {"scan_ts": 1760281200.0, "sections": {
        BD.SECTION_REJECTED: [{"symbol": "REJ"}],
        BD.SECTION_STEADY: [{"symbol": "SSS"}, {"symbol": "PPP"}],
        BD.SECTION_PIVOT: [{"symbol": "PPP"}, {"symbol": "QQQ"}],
        BD.SECTION_EXPLOSIVE: [{"symbol": "EEE"}, {"symbol": "qqq"}]}}
    assert M.record_bonde(payload, db=db) is True
    doc = db.coll.docs["bonde"]
    assert doc["symbols"] == ["PPP", "QQQ", "EEE", "SSS"]
    assert "REJ" not in doc["symbols"]
    assert doc["ttl_sec"] is None and doc["limit"] is None
    assert doc["source_as_of"] == datetime.fromtimestamp(
        1760281200.0, tz=timezone.utc).isoformat(timespec="seconds")


def test_record_bonde_iso_scan_ts_and_missing_stamp():
    db = FakeDB()
    M.record_bonde({"scan_ts": "2026-09-17T21:00:00+00:00",
                    "sections": {"pivot": [{"symbol": "A"}]}}, db=db)
    assert db.coll.docs["bonde"]["source_as_of"] == "2026-09-17T21:00:00+00:00"
    M.record_bonde({"sections": {"pivot": [{"symbol": "A"}]}}, db=db)
    assert db.coll.docs["bonde"]["source_as_of"] is None


def test_NEGATIVE_record_bonde_rejected_only_writes_nothing():
    db = FakeDB()
    assert M.record_bonde({"sections": {"rejected": [{"symbol": "R"}]}}, db=db) is False
    assert M.record_bonde({}, db=db) is False
    assert M.record_bonde(None, db=db) is False
    assert db.coll.writes == 0


# --------------------------------------------------------------------------
# attach_also_on [C8]
# --------------------------------------------------------------------------
def _seeded():
    from chart_maps import ath_tab
    db = FakeDB()
    M.record("zones", ["AAA", "BBB"], built_at=NOW.isoformat(), limit=80, db=db)
    M.record("ath", ["AAA"], built_at=NOW.isoformat(),
             source_as_of=(NOW - timedelta(seconds=ath_tab.MEMO_TTL_SEC + 1)).isoformat(),
             ttl_sec=ath_tab.MEMO_TTL_SEC, ttl_name="chart_maps.ath_tab.MEMO_TTL_SEC",
             limit=80, db=db)
    M.record("fallen", ["AAA"], built_at=NOW.isoformat(),
             source_as_of=NOW.isoformat(), ttl_sec=3600, ttl_name="n", limit=80, db=db)
    M.record("bonde", ["aaa"], built_at=NOW.isoformat(), db=db)
    db.coll.docs["growth"] = {"_id": "growth", "symbols": ["AAA"]}
    return db


def test_attach_also_on_ONE_find_sorted_tabs_with_limit_and_stale():
    db = _seeded()
    arr = [{"symbol": "AAA"}, {"symbol": "bbb"}, {"symbol": "ZZZ"}]
    M.attach_also_on(arr, now=NOW, db=db)
    assert db.coll.find_calls == 1
    a = {t["tab"]: t for t in arr[0]["also_on"]}
    assert [t["tab"] for t in arr[0]["also_on"]] == ["ath", "bonde", "fallen", "zones"]
    assert "growth" not in a
    assert a["ath"]["stale"] is True
    assert a["fallen"]["stale"] is False
    assert a["zones"]["stale"] is None and a["bonde"]["stale"] is None
    assert a["zones"]["limit"] == 80 and a["bonde"]["limit"] is None
    assert set(a["ath"]) == {"tab", "built_at", "source_as_of", "ttl_name",
                             "limit", "stale"}
    assert [t["tab"] for t in arr[1]["also_on"]] == ["zones"]
    assert arr[2]["also_on"] == []


def test_attach_also_on_empty_collection_and_no_db_give_empty_lists(monkeypatch):
    arr = [{"symbol": "AAA"}]
    M.attach_also_on(arr, now=NOW, db=FakeDB())
    assert arr[0]["also_on"] == []
    monkeypatch.setattr(M, "_db", lambda db=None: None)
    arr = [{"symbol": "AAA"}]
    M.attach_also_on(arr, now=NOW)
    assert arr[0]["also_on"] == []


def test_NEGATIVE_attach_also_on_exception_leaves_arrivals_untouched():
    arr = [{"symbol": "AAA", "first_seen": "2026-10-12"}]
    before = [dict(a) for a in arr]
    M.attach_also_on(arr, now=NOW, db=BoomDB())
    assert arr == before


def test_NEGATIVE_attach_also_on_survives_junk_rows():
    db = _seeded()
    arr = [None, "x", {"symbol": None}, {"symbol": "AAA"}]
    M.attach_also_on(arr, now=NOW, db=db)
    assert arr[2]["also_on"] == []
    assert len(arr[3]["also_on"]) == 4


# --------------------------------------------------------------------------
# board() hook — wiring, isolation, source pins
# --------------------------------------------------------------------------
def _stub_board(monkeypatch):
    def fake_tiles(*a, **k):
        return {"tiles": _tiles("AAA", "BBB"), "note": "stub"}
    for name in ("earnings_tiles", "zone_tiles", "vcp_tiles"):
        monkeypatch.setattr(B, name, fake_tiles)
    monkeypatch.setattr(B, "attach_explosive", lambda tiles: 0)
    monkeypatch.setattr(B, "_live_snapshot", lambda tiles: {})
    monkeypatch.setattr(B, "attach_live_now", lambda tiles, out=None, **k: {})
    monkeypatch.setattr(B, "attach_enterable", lambda tiles, kind="demand", **k: 0)
    monkeypatch.setattr(B, "attach_band_structure", lambda tiles, kind="demand", **k: 0)
    monkeypatch.setattr(B, "band_structure_coverage", lambda tiles, kind="demand": {})
    monkeypatch.setattr(B, "_burst_frames", lambda syms: {})
    monkeypatch.setattr(B, "attach_burst", lambda *a, **k: None)
    monkeypatch.setattr(B, "attach_key_levels", lambda *a, **k: None)


def test_default_board_call_triggers_exactly_one_record_board(monkeypatch):
    _stub_board(monkeypatch)
    calls = []
    monkeypatch.setattr(M, "record_board",
                        lambda tab, out, *, request, db=None: calls.append(
                            (tab, M.is_default_request(**request))) or True)
    B.board(tab="earnings", limit=B.LIMIT_MAX)
    assert calls == [("earnings", True)]


def test_NEGATIVE_filtered_board_call_writes_nothing(monkeypatch):
    _stub_board(monkeypatch)
    db = FakeDB()
    monkeypatch.setattr(M, "_db", lambda d=None: db)
    B.board(tab="earnings", limit=B.LIMIT_MAX, min_tier="deep")
    B.board(tab="earnings", limit=12)
    B.board(tab="earnings", limit=B.LIMIT_MAX, studies=True)
    assert db.coll.writes == 0
    B.board(tab="earnings", limit=B.LIMIT_MAX)
    assert db.coll.writes == 1
    assert db.coll.docs["earnings"]["symbols"] == ["AAA", "BBB"]


def test_NEGATIVE_hook_raising_never_breaks_the_board(monkeypatch):
    _stub_board(monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("membership exploded")
    monkeypatch.setattr(M, "record_board", boom)
    out = B.board(tab="earnings", limit=B.LIMIT_MAX)
    assert out["tab"] == "earnings" and out["count"] == 2
    assert [t["symbol"] for t in out["tiles"]] == ["AAA", "BBB"]


def test_NEGATIVE_mongo_down_never_breaks_the_board(monkeypatch):
    _stub_board(monkeypatch)
    monkeypatch.setattr(M, "_db", lambda d=None: BoomDB())
    out = B.board(tab="earnings", limit=B.LIMIT_MAX)
    assert out["count"] == 2


def _hook_block() -> str:
    src = (BACKEND / "chart_maps" / "board.py").read_text()
    m = re.search(r"_MB\.record_board\(t, out, request=\{(.*?)\}\)", src, re.S)
    assert m, "the membership hook is missing from board()"
    return m.group(1)


def test_C6_hook_passes_EXACTLY_the_signature_parameter_set():
    keys = set(re.findall(r'"([a-z_]+)":', _hook_block()))
    assert keys == set(inspect.signature(B.board).parameters)


def test_hook_sits_after_out_tab_and_exactly_once():
    src = inspect.getsource(B.board)
    assert src.count("_MB.record_board(") == 1
    assert src.index('out["tab"] = t') < src.index("_MB.record_board(")
    assert src.index("_MB.record_board(") < src.index('out["count"] =')


def test_bonde_api_carries_exactly_one_hook_inside_run():
    src = (BACKEND / "sepa" / "bonde_api.py").read_text()
    assert src.count("_MB.record_bonde(") == 1
    run = src[src.index("def _run():"):src.index("return JSONResponse(")]
    assert "_MB.record_bonde(board)" in run
    assert run.index("SR.attach_bonde(board)") < run.index("_MB.record_bonde(board)")


def test_NEGATIVE_bonde_endpoint_survives_a_raising_hook(monkeypatch):
    from sepa import bonde_api as BA
    payload = {"sections": {"pivot": [{"symbol": "AAA"}]}, "note": "x"}
    monkeypatch.setattr(BA.B, "board", lambda new_days=None: dict(payload))
    monkeypatch.setattr(BA.BL, "attach", lambda b: b)
    from sepa import since_report as SR
    monkeypatch.setattr(SR, "attach_bonde", lambda b: b)
    calls = []

    def boom(board, db=None):
        calls.append(board)
        raise RuntimeError("membership exploded")
    monkeypatch.setattr(M, "record_bonde", boom)
    resp = asyncio.run(BA.bonde_board(new_days=7))
    assert resp.status_code == 200 and len(calls) == 1
    assert b'"AAA"' in resp.body


# --------------------------------------------------------------------------
# Rule #10 — nothing here sorts tiles, pushes, or gates
# --------------------------------------------------------------------------
def test_RULE10_membership_source_never_sorts_tiles_pushes_or_gates():
    src = (BACKEND / "chart_maps" / "membership.py").read_text()
    for bad in ("send_push", "alert_gates", "room_gate", "push.hooks",
                "entries.enter", "ALPACA"):
        assert bad not in src, bad
    assert not re.search(r"sorted\([^)]*tiles", src)
    assert not re.search(r"tiles[^\n]*\.sort\(", src)
    assert "MIN_ROOM_DEFAULT" in src and "5.0" not in src
    # no TTL number typed here — every TTL is read off its module by name
    assert not re.search(r"\b(60|1800|3600)\b", src)
