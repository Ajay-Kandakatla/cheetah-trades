"""🎯 ENTERABLE — the BACKEND WIRING (WP2, 2026-09-15).

The read itself (`supply_demand/enterable.py`) is pinned by `test_enterable.py`.
THIS file pins where it is served and what the wiring may never do:

* `chart_maps.board.attach_enterable` decorates and NEVER filters — a board that
  hides a row silently is the one outcome the ask ("I do not want to see not
  enterable alerts or stocks") must not be implemented as. The hiding is the
  frontend's visible, reversible filter; the backend only says what it reads.
* the tile read keys on the LIVE print and the session low from the SAME
  `bulk_live_prices` fan-out `attach_live_now` already makes (spec B3). A verdict
  computed on yesterday's close would call a name READY that swept its floor
  this morning — so the order of the two overlays, and the single fan-out, are
  both pinned here.
* on the four demand PUSH paths the read runs LAST, after every existing gate,
  and the gates are passed THROUGH rather than recomputed (m8). That makes
  BLOCKED unreachable by construction: `skipped_not_enterable` is a divergence
  guard expected to stay 0, and the only counter test here is the monkeypatched
  one. There is deliberately NO "the counter is 0 today" test.
* 🪃 `zone_bounce_alert` gains the STANDING floor gate with the read — the
  identical `sweep_read` + `floor_held_gate` call the other three demand kinds
  have run since 2026-09-09, failing CLOSED (his call §7.5). Nothing here
  loosens a gate.

Every number these tests assert comes from the enforcing constant by name.
"""
from __future__ import annotations

import inspect
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chart_maps import board as B                    # noqa: E402
from growth import alerts as GA                      # noqa: E402
from supply_demand import alert_gates as AG          # noqa: E402
from supply_demand import alert_status as AS         # noqa: E402
from supply_demand import demand_alerts as DA        # noqa: E402
from supply_demand import enterable as EN            # noqa: E402
# Imported HERE on purpose: `explosive` binds `alert_gates.sweep_read` by VALUE
# at import time (the floor adapter the read uses). Importing it before the
# autouse stub below ever runs is what a real process does — otherwise the
# first test to touch it would freeze the STUB into the adapter for the run.
from supply_demand import explosive as EX             # noqa: E402,F401
from supply_demand import premarket_entry as PE      # noqa: E402
from supply_demand import rules_info as RI           # noqa: E402
from supply_demand import zone_bounce_alerts as ZB   # noqa: E402
from supply_demand import zone_edge as ZE            # noqa: E402

ET = ZoneInfo("America/New_York")
NOW = datetime(2026, 9, 15, 11, 0, tzinfo=ET)          # a Monday, RTH
DAY = "2026-09-15"
BACKEND = Path(__file__).resolve().parents[1]

# The SHIPPED sweep read, captured before the autouse stub replaces it — the
# floor tests below are about the real one.
_REAL_SWEEP = AG.sweep_read

DEM = {"kind": "demand", "lo": 90.0, "hi": 92.0, "touches": 3, "strength": 50.0}
RES = {"kind": "supply", "lo": 100.0, "hi": 102.0, "touches": 2, "strength": 40.0}


# ──────────────────────────────────────────────────────────────── fakes
class Coll:
    """pymongo-shaped enough for the claim / dedupe reads."""

    def __init__(self):
        self.docs, self.calls = {}, []

    def find_one(self, q):
        self.calls.append("find_one")
        return self.docs.get(q["_id"])

    def find(self, q, projection=None):
        self.calls.append("find")
        if "_id" in q:
            for k in q["_id"]["$in"]:
                if k in self.docs:
                    yield dict(self.docs[k])
            return
        for d in list(self.docs.values()):
            if d.get("symbol") in q["symbol"]["$in"]:
                yield dict(d)

    def update_one(self, q, u, upsert=False):
        self.calls.append("update_one")
        existed = q["_id"] in self.docs
        d = self.docs.setdefault(q["_id"], {"_id": q["_id"]})
        if not existed:
            d.update(u.get("$setOnInsert", {}))
        d.update(u.get("$set", {}))
        return SimpleNamespace(matched_count=1 if existed else 0,
                               upserted_id=None if existed else q["_id"])

    def delete_one(self, q):
        self.calls.append("delete_one")
        self.docs.pop(q["_id"], None)
        return SimpleNamespace(deleted_count=1)

    def replace_one(self, q, doc, upsert=False):
        self.docs[q["_id"]] = dict(doc)

    def insert_many(self, docs):
        pass

    def delete_many(self, q):
        return SimpleNamespace(deleted_count=0)


def _capture(monkeypatch, result=None):
    from push import sender
    sent = []

    def fake(owner, payload, kind=None):
        sent.append({"owner": owner, "kind_arg": kind, **payload})
        return result or {"sent": 1, "failed": 0, "total_targets": 1}
    monkeypatch.setattr(sender, "send_to_user", fake)
    return sent


def _snap(last, prev, chg=-1.0, low=None, *, now=NOW, age_sec=30):
    ts_ns = int((now - timedelta(seconds=age_sec)).timestamp() * 1e9)
    return {"open": last, "high": last, "low": last if low is None else low,
            "close": last, "volume": 1e6, "change_pct": chg,
            "last_trade_price": last, "last_trade_ts_ms": ts_ns,
            "prev_day_close": prev}


def _doc(sym, bands, prev):
    return {"_id": f"{sym}:{DAY}", "symbol": sym, "date": DAY, "geom": "board",
            "bands": bands, "atr14": 1.0, "prev_close": prev, "high_252": None}


def _board_payload(sym="AAA", band=DEM):
    return {"rows": [{"symbol": sym, "name": f"{sym} Inc", "entry_zone": dict(band)}],
            "approaching_rows": []}


def _tail(n=22, lo=95.0, hi=99.0):
    """A closed-bar tail that never pierces the band floor — `intact`."""
    return [{"date": f"2026-08-{d:02d}", "open": lo + 1, "high": hi + 2,
             "low": lo + 0.5, "close": hi, "volume": 1e6}
            for d in range(1, n + 1)]


@pytest.fixture(autouse=True)
def _clean_structure(monkeypatch):
    """The daily-bar reads the push paths make, stubbed as the sibling suites
    stub them: clean structure, bullish turn, floor intact. `AG` is ONE module
    object, so patching it here covers every module that imported it."""
    monkeypatch.setattr(AG, "daily_frame", lambda sym, frame=None: frame)
    monkeypatch.setattr(AG, "mood_read", lambda sym, frame=None: None)
    monkeypatch.setattr(AG, "knife_read",
                        lambda sym, frame=None: {"knife": False, "trend": "rising"})
    monkeypatch.setattr(AG, "sweep_read",
                        lambda band, symbol=None, frame=None, window=None, **kw:
                            {"state": "intact", "pierce_pct": None,
                             "reclaim_bars": None, "vol_x": None})
    monkeypatch.setattr(AG, "reversal_mood_read",
                        lambda sym, frame=None, bars=None: {"score": 40.0, "label": "bullish",
                                                            "bars": 60, "bullish": True})
    monkeypatch.setattr(DA.BC, "bullish_context",
                        lambda sym, frame=None, with_sentiment=True: {"gex": None, "patterns": None,
                                                                      "sentiment": None})


# ═══════════════════════════════════════════ 1. attach_enterable: it decorates
def _tile(sym="AAA", last_price=None, last_close=100.0, **kw):
    t = {"symbol": sym, "theme": None, "_score": 0.0, "bars": [],
         "last_close": last_close, "_m": {"explosive": None}}
    if last_price is not None:
        t["last_price"] = last_price
    t.update(kw)
    return t


@pytest.fixture
def store(monkeypatch):
    """ONE `zone_store.load_latest` for the board, counted."""
    from supply_demand import zone_store
    calls = {"n": 0, "symbols": None, "docs": {}}

    def _latest(symbols=None, coll=None, today=None):
        calls["n"] += 1
        calls["symbols"] = list(symbols or [])
        return DAY, {s: calls["docs"].get(s, _doc(s, [DEM, RES], 95.0))
                     for s in (symbols or [])}

    monkeypatch.setattr(zone_store, "load_latest", _latest)
    return calls


def test_attach_enterable_is_idempotent_by_KEY_PRESENCE_not_truthiness(store):
    """None is a real answer ("no usable print"), so a second call must not
    re-read the store for a tile that already answered None."""
    already = _tile("AAA")
    already["enterable"] = None
    fresh = _tile("BBB", last_price=91.0)
    B.attach_enterable([already, fresh], kind=EN.KIND_DEMAND, live={})
    assert store["n"] == 1 and store["symbols"] == ["BBB"]
    assert already["enterable"] is None
    B.attach_enterable([already, fresh], kind=EN.KIND_DEMAND, live={})
    assert store["n"] == 1, "nothing left to do, no second Mongo read"


def test_attach_enterable_NEVER_drops_a_tile_and_never_raises_on_a_dead_store(monkeypatch):
    from supply_demand import zone_store

    def _boom(*a, **k):
        raise RuntimeError("mongo down")
    monkeypatch.setattr(zone_store, "load_latest", _boom)
    tiles = [_tile("AAA", last_price=91.0), _tile("BBB", last_price=0.0)]
    B.attach_enterable(tiles, kind=EN.KIND_DEMAND, live={})
    assert len(tiles) == 2, "decoration never removes a row"
    assert tiles[0]["enterable"]["verdict"] == EN.BLOCKED, "no doc -> no band -> blocked"
    assert tiles[0]["enterable"]["reasons"] == ["no_band"]
    assert tiles[1]["enterable"] is None, "an unusable print is UNKNOWN, never a verdict"


def test_SOURCE_GUARD_attach_enterable_contains_no_filtering_of_any_kind():
    """The ask is a FILTER, and the filter is the frontend's — visible, counted
    and reversible. A quiet server-side cut here would hide rows with no count
    line to restore them."""
    src = inspect.getsource(B.attach_enterable)
    for forbidden in ("min_room", "passes_liquidity", "_spread", "tiles = [",
                      "tiles.remove", "tiles[:] ="):
        assert forbidden not in src, f"attach_enterable must not filter ({forbidden})"
    assert "is_shown" not in src


def test_B3_the_tile_read_is_on_the_LIVE_print_not_the_scan_close(store):
    """The scan closed at 100 inside the band; the tape has run to 103, which is
    more than ALERT_MAX_ABOVE_DEMAND_PCT above the band top. READY here would be
    a verdict on yesterday."""
    store["docs"]["AAA"] = _doc("AAA", [{"kind": "demand", "lo": 98.0, "hi": 100.0,
                                         "touches": 3, "strength": 50.0}, RES], 100.0)
    t = _tile("AAA", last_close=100.0)
    B.attach_enterable([t], kind=EN.KIND_DEMAND,
                       live={"AAA": {"price": 103.0, "low": 99.0, "change_pct": 3.0,
                                     "prev_day_close": 100.0}})
    read = t["enterable"]
    assert read["print"]["px"] == 103.0 and read["print"]["source"] == "live"
    assert read["verdict"] == EN.BLOCKED and "proximity" in read["reasons"]


def test_B3_the_SESSION_LOW_is_fed_so_a_floor_swept_this_morning_reads_swept(store, monkeypatch):
    """The closed tail never pierced 98; the session low did. Without the
    session low the doc alone reads intact and the tile would say READY."""
    band = {"kind": "demand", "lo": 98.0, "hi": 100.0, "touches": 3, "strength": 50.0}
    far_lid = {"kind": "supply", "lo": 120.0, "hi": 125.0, "touches": 2, "strength": 40.0}
    doc = _doc("AAA", [band, far_lid], 100.0)      # plenty of room: the FLOOR decides
    doc["feat"] = {"tail": _tail(lo=98.0, hi=100.0)}
    store["docs"]["AAA"] = doc
    assert EX.sweep_read is _REAL_SWEEP, "the floor adapter holds the SHIPPED read"
    t = _tile("AAA", last_close=100.0)
    B.attach_enterable([t], kind=EN.KIND_DEMAND,
                       live={"AAA": {"price": 99.5, "low": 97.0, "change_pct": -0.5,
                                     "prev_day_close": 100.0}})
    read = t["enterable"]
    assert read["gates"]["session_low"] is True
    assert read["verdict"] == EN.BLOCKED
    assert read["reasons"] == [EN.FLOOR_CODE.format(state=read["gates"]["floor_state"])]
    assert read["gates"]["floor_state"] not in AG.FLOOR_HELD_STATES


def test_with_no_live_row_the_read_falls_back_to_the_scan_print_and_SAYS_so(store):
    t = _tile("AAA", last_close=91.0)
    B.attach_enterable([t], kind=EN.KIND_DEMAND, live={})
    assert t["enterable"]["print"] == {"px": 91.0, "source": "scan"}
    assert t["enterable"]["gates"]["session_low"] is False


def test_the_kind_comes_from_KIND_BY_TAB_and_an_na_tab_never_touches_the_store(store):
    breaking = [_tile("AAA", last_price=101.0)]
    B.attach_enterable(breaking, kind=EN.KIND_BY_TAB["breaking"], live={})
    assert breaking[0]["enterable"]["kind"] == EN.KIND_SUPPLY_BREAK
    assert store["n"] == 1

    vcp = [_tile("BBB", last_price=50.0)]
    B.attach_enterable(vcp, kind=EN.KIND_BY_TAB["vcp"], live={})
    assert vcp[0]["enterable"]["kind"] == EN.KIND_NA
    assert vcp[0]["enterable"]["verdict"] is None and vcp[0]["enterable"]["reasons"] == ["na"]
    assert store["n"] == 1, "an n/a tab has no demand read to make: no Mongo read"
    assert EN.KIND_BY_TAB["zones"] == EN.KIND_DEMAND


def test_the_metric_column_carries_the_verdict_RANK_and_None_for_no_read(store):
    t = _tile("AAA", last_price=91.0)
    B.attach_enterable([t], kind=EN.KIND_DEMAND, live={})
    assert t["_m"]["enterable"] == PE.GRADE_ORDER[t["enterable"]["verdict"]]
    dead = _tile("CCC", last_price=0.0)
    B.attach_enterable([dead], kind=EN.KIND_DEMAND, live={})
    assert dead["_m"]["enterable"] is None


def test_m7_the_session_day_is_the_last_day_the_market_TRADED_never_the_calendar():
    """`with_session_bar` appends the print as a NEW bar whenever the frame ends
    before the date it is given. On a Saturday the calendar date makes Friday's
    snapshot a synthetic Saturday bar on top of Friday's own row; the session
    date makes it a merge (critique m7, 2026-09-15)."""
    from market_hours.reminder import is_market_day
    sat = datetime(2026, 9, 19, 12, 0, tzinfo=ET)
    sun = datetime(2026, 9, 20, 12, 0, tzinfo=ET)
    labor_day = datetime(2026, 9, 7, 12, 0, tzinfo=ET)          # a shipped holiday
    assert B._session_day(sat).isoformat() == "2026-09-18"
    assert B._session_day(sun).isoformat() == "2026-09-18"
    assert B._session_day(labor_day).isoformat() == "2026-09-04"
    assert B._session_day(NOW) == NOW.date(), "a trading day is its own session"
    for probe in (sat, sun, labor_day, NOW):
        d = B._session_day(probe)
        assert is_market_day(datetime(d.year, d.month, d.day, 12, tzinfo=ET)), \
            "the session date must be a day the market traded"


def test_m7_the_tile_read_is_dated_with_that_session_day(store, monkeypatch):
    """The push paths hand `sweep_read` the date of the pass; the tile path now
    hands the read the same kind of date instead of leaving it to default."""
    seen = {}
    real = EN.read

    def spy(**kw):
        seen.update(kw)
        return real(**kw)

    monkeypatch.setattr(EN, "read", spy)
    t = _tile("AAA", last_close=91.0)
    B.attach_enterable([t], kind=EN.KIND_DEMAND, live={})
    assert seen["day"] == B._session_day()
    assert seen["day"] is not None, "a defaulted date is exactly the m7 bug"


def test_m7_NEGATIVE_a_closed_day_MERGES_the_print_instead_of_inventing_a_bar():
    """The consequence, through the shipped function: dated with the session,
    the frame keeps its row count; dated with the calendar Saturday it grows by
    a bar that never traded."""
    import pandas as pd
    idx = pd.to_datetime(["2026-09-16", "2026-09-17", "2026-09-18"])
    df = pd.DataFrame({"open": [99.0] * 3, "high": [100.0] * 3, "low": [98.0] * 3,
                       "close": [99.5] * 3, "volume": [1e6] * 3}, index=idx)
    friday = B._session_day(datetime(2026, 9, 19, 12, 0, tzinfo=ET))
    merged = AG.with_session_bar(df, 97.0, 99.0, day=friday)
    assert len(merged) == len(df) and float(merged["low"].iloc[-1]) == 97.0

    saturday = datetime(2026, 9, 19, 12, 0, tzinfo=ET).date()
    invented = AG.with_session_bar(df, 97.0, 99.0, day=saturday)
    assert len(invented) == len(df) + 1, "this is the bar m7 is about"


def test_SOURCE_ORDER_the_read_is_attached_AFTER_the_live_overlay(monkeypatch):
    """`_finish` runs before the sort and before the limit cut, where no live
    print exists — so the read lives in `board()`, after `attach_live_now`."""
    src = inspect.getsource(B.board)
    assert src.index("attach_enterable(") > src.index("attach_live_now("), \
        "the read must see the live print the now-line already moved to"
    assert "attach_enterable" not in inspect.getsource(B._finish)
    assert "live=" in src.split("attach_live_now(")[1][:80], \
        "attach_live_now must be FED the shared snapshot, not refetch it"


def test_ONE_live_fan_out_feeds_both_overlays_and_the_tab_kind_is_served(monkeypatch):
    seen = {}
    sentinel = {"__one_fan_out__": True}
    monkeypatch.setattr(B, "_live_snapshot",
                        lambda tiles: seen.setdefault("snapshots", []).append(tiles) or sentinel)
    monkeypatch.setattr(B, "attach_live_now",
                        lambda tiles, out=None, *, live=None, now=None:
                            seen.__setitem__("now_live", live) or {})
    monkeypatch.setattr(B, "attach_enterable",
                        lambda tiles, kind=EN.KIND_DEMAND, *, live=None:
                            seen.__setitem__("ent", (kind, live)))
    out = B.board(tab="vcp", limit=2)
    assert len(seen["snapshots"]) == 1, "one bulk_live_prices fan-out per board"
    assert seen["now_live"] is sentinel and seen["ent"][1] is sentinel
    assert seen["ent"][0] == EN.KIND_NA and out["enterable_kind"] == EN.KIND_NA
    assert out["enterable_study"]["headline"]


def test_live_snapshot_is_empty_on_any_failure_never_None(monkeypatch):
    """`{}` and None mean different things to `attach_live_now`: None makes it
    refetch, which would be the second fan-out this design exists to avoid."""
    seen = []
    monkeypatch.setattr(B, "_live_rows", lambda syms: seen.append(list(syms)) or {})
    assert B._live_snapshot([]) == {} and seen == [[]]
    assert B._live_snapshot([{"symbol": "AAA"}, {"nope": 1}, None]) == {}
    assert seen[-1] == ["AAA"], "only real symbols reach the fan-out"

    from sepa import prices as _p
    monkeypatch.setattr(_p, "bulk_live_prices",
                        lambda syms: (_ for _ in ()).throw(RuntimeError("tape down")))
    assert B._live_snapshot([{"symbol": "AAA"}]) == {}, "a tape outage is {}, never None"


# ═══════════════════════════════════════════ 2. the support route
def test_the_support_route_feeds_ONE_snapshot_to_BOTH_overlays():
    src = BACKEND.joinpath("chart_maps", "api.py").read_text()
    assert "_live_snapshot([tile])" in src
    assert "attach_live_now([tile], res, live=live)" in src
    assert "attach_enterable([tile], kind=EN.KIND_DEMAND, live=live)" in src
    assert src.index("attach_enterable([tile]") > src.index("attach_live_now([tile]")


# ═══════════════════════════════════════════ 3. bounce_room rows + payload
def test_the_bounce_room_row_carries_the_read_and_a_pending_row_carries_no_key():
    from supply_demand import bounce_room as BR
    doc = _doc("AAA", [DEM, RES], 95.0)
    row = BR.read_symbol("AAA", doc, _snap(91.0, 95.0, low=90.5), now=NOW)
    assert row["enterable"]["kind"] == EN.KIND_DEMAND
    assert row["enterable"]["band"] == {"lo": 90.0, "hi": 92.0}
    assert "enterable" not in BR.read_symbol("AAA", None, None, now=NOW)
    assert "enterable" not in BR.read_symbol("AAA", {"error": "no data"}, None, now=NOW)
    assert "enterable" not in BR.read_symbol("AAA", doc, None, now=NOW)


def test_m5_the_row_says_SCAN_when_the_print_is_the_stored_close_not_a_live_trade():
    """`print_of` already decided fresh vs stale; the read must repeat that
    answer, because the chip title he reads is built from `print.source`
    (critique m5, 2026-09-15). NEGATIVE: an hour-old stamp is not "live"."""
    from supply_demand import bounce_room as BR
    doc = _doc("AAA", [DEM, RES], 95.0)

    live = BR.read_symbol("AAA", doc, _snap(91.0, 95.0, low=90.5, age_sec=5), now=NOW)
    assert live["fresh"] is True
    assert live["enterable"]["print"]["source"] == "live"

    stale_snap = _snap(91.0, 95.0, low=90.5, age_sec=3600)
    stale = BR.read_symbol("AAA", doc, stale_snap, now=NOW)
    assert stale["fresh"] is False
    assert stale["enterable"]["print"]["source"] == "scan", \
        "a stale print may not wear the word live"
    assert stale["enterable"]["print"]["px"] == stale["print"]


def test_the_bounce_room_payload_carries_the_study_banner_once():
    from supply_demand import bounce_room as BR
    payload = BR.build_payload(["AAA"], docs={"AAA": _doc("AAA", [DEM, RES], 95.0)},
                               snapshot={"AAA": _snap(91.0, 95.0, low=90.5)},
                               now=NOW, store_date=NOW.date())
    assert payload["enterable_study"]["headline"] == EN.measured_verdict()["headline"]
    assert payload["params"] == dict(BR.PARAMS), "the read adds no owner setting"


# ═══════════════════════════════════════════ 4. demand_alerts (🧲)
def _da(store_docs, snapshot, caps, *, coll=None, now=NOW, push=True):
    return DA.check_once(force=True, push=push, board=_board_payload(), snapshot=snapshot,
                         caps=caps, coll=coll or Coll(), owner="o@x", now=now,
                         store=store_docs)


def test_a_candidate_that_clears_every_gate_carries_the_read_and_still_pushes(monkeypatch):
    sent = _capture(monkeypatch)
    out = _da({"AAA": _doc("AAA", [DEM, RES], 95.0)}, {"AAA": _snap(91.0, 95.0, low=90.5)},
              {"AAA": 5e9})
    assert out["pushed"] == 1 and len(sent) == 1
    slim = sent[0]["enterable"]
    assert slim["kind"] == EN.KIND_DEMAND
    assert slim["verdict"] in (EN.READY, EN.WATCH), "the phone's own gates cannot block"
    assert set(slim) == {"kind", "verdict", "reasons", "reason_text", "reason_short"}
    assert out["skipped_not_enterable"] == 0


def test_GATE_ORDER_the_read_runs_after_every_existing_gate(monkeypatch):
    src = inspect.getsource(DA._check_once)
    assert src.index("EN.assess") > src.index("reversal_mood_gate"), \
        "the read is a tightening, applied LAST — never a replacement for a gate"
    assert src.index("EN.assess") > src.index("floor_held_gate")
    assert "room_ok=True" in src and "prox_ok=True" in src, \
        "the gates that already ran are passed THROUGH, never recomputed (m8)"


def test_NEGATIVE_a_BLOCKED_read_is_not_pushed_is_counted_and_never_claims_a_key(monkeypatch):
    """BLOCKED is unreachable here by construction, so the ONLY way to pin the
    counter is to force one. The claim must not have been written: a key burned
    on a row that never rang would silence the real push next pass."""
    sent = _capture(monkeypatch)
    blocked = dict(EN.assess(kind=EN.KIND_DEMAND, px=91.0, band=DEM, bands=[DEM, RES],
                             prev_close=95.0, room_ok=True, prox_ok=True),
                   verdict=EN.BLOCKED, reasons=["room"])
    monkeypatch.setattr(DA.EN, "assess", lambda **kw: blocked)
    settles = {"n": 0}
    real = DA.settle_claims
    monkeypatch.setattr(DA, "settle_claims",
                        lambda *a, **k: (settles.__setitem__("n", settles["n"] + 1),
                                         real(*a, **k))[1])
    coll = Coll()
    out = _da({"AAA": _doc("AAA", [DEM, RES], 95.0)}, {"AAA": _snap(91.0, 95.0, low=90.5)},
              {"AAA": 5e9}, coll=coll)
    assert sent == [] and out["pushed"] == 0
    assert out["skipped_not_enterable"] == 1
    assert settles["n"] == 0 and coll.docs == {}, "nothing claimed for a row that never rang"


def test_the_push_builders_carry_the_slim_read_and_survive_a_row_without_one():
    item = {"symbol": "AAA", "last": 91.0, "band": DEM, "cap": 5e9, "name": "AAA Inc",
            "hit": {"tier": "at", "state": "in", "dist_pct": 0.0}}
    assert DA.at_message(item)["enterable"] is None, "a row with no read stores None"
    item["enterable"] = EN.assess(kind=EN.KIND_DEMAND, px=91.0, band=DEM, bands=[DEM, RES],
                                  prev_close=91.0, change_pct=0.0, room_ok=True,
                                  prox_ok=True, floor_state=AG.FLOOR_HELD_STATES[0])
    msg = DA.at_message(item)
    assert msg["enterable"]["verdict"] == EN.READY
    assert DA.digest_message([item])["title"].startswith("🧲 ")


# ═══════════════════════════════════════════ 5. zone_edge (🚀 + 🧲)
def _ze(store_docs, snapshot, caps, *, coll_demand=None, coll_break=None, now=NOW):
    colls = {"coll_break": coll_break or Coll(), "coll_demand": coll_demand or Coll(),
             "latest_coll": Coll(), "track_coll": Coll()}
    out = ZE.check_once(push=True, force=True, track=False, store=store_docs,
                        snapshot=snapshot, caps=caps, names={}, owner="o@x", now=now,
                        **colls)
    return out, colls


def test_the_zone_edge_demand_lane_records_the_read_and_counts_a_divergence(monkeypatch):
    sent = _capture(monkeypatch)
    out, _ = _ze({"AAA": _doc("AAA", [DEM, RES], 95.0)},
                 {"AAA": _snap(91.0, 95.0, low=90.5)}, {"AAA": 5e9})
    assert out["pushed"] == 1 and sent[0]["enterable"]["verdict"] in (EN.READY, EN.WATCH)
    assert out["skipped_not_enterable"] == 0

    blocked = dict(sent[0]["enterable"], verdict=EN.BLOCKED, reasons=["room"])
    monkeypatch.setattr(ZE.EN, "assess", lambda **kw: blocked)
    sent2 = _capture(monkeypatch)
    out2, _ = _ze({"AAA": _doc("AAA", [DEM, RES], 95.0)},
                  {"AAA": _snap(91.0, 95.0, low=90.5)}, {"AAA": 5e9})
    assert sent2 == [] and out2["pushed"] == 0 and out2["skipped_not_enterable"] == 1
    assert out2["payload"]["counts"]["skipped_not_enterable"] == 1


def test_the_supply_lane_reads_the_NEXT_LID_list_and_is_READY_by_construction(monkeypatch):
    sent = _capture(monkeypatch)
    seen = {}
    real = ZE.next_lids

    def spy(bands, band):
        seen["call"] = (bands, band)
        return real(bands, band)
    monkeypatch.setattr(ZE, "next_lids", spy)
    doc = _doc("AAA", [{"kind": "supply", "lo": 98.0, "hi": 100.0, "touches": 3}], 99.0)
    out, _ = _ze({"AAA": doc}, {"AAA": _snap(100.5, 99.0, chg=1.5, low=99.0)}, {"AAA": 5e9})
    assert out["pushed"] == 1 and seen["call"][1]["hi"] == 100.0
    slim = sent[0]["enterable"]
    assert slim["kind"] == EN.KIND_SUPPLY_BREAK and slim["verdict"] == EN.READY
    assert slim["reasons"] == []


# ═══════════════════════════════════════════ 6. zone_bounce_alerts (🪃)
def _zb(store_docs, snapshot, caps, *, coll=None, now=NOW, push=True):
    return ZB.check_once(push=push, force=True, store=store_docs, snapshot=snapshot,
                         caps=caps, names={}, coll=coll or Coll(), owner="o@x", now=now,
                         low_times={})


def _zb_case():
    """A 🪃 reversal that clears cap, proximity and room: low in the band, the
    print back above its top, yesterday well outside."""
    band = {"kind": "demand", "lo": 88.0, "hi": 92.0, "touches": 2, "strength": 40.0}
    doc = _doc("AAA", [band, RES], 99.0)
    # 6.4% off the low: STRONG, so it rides a single push and the slim read
    # travels on the payload (a digest line carries none — by design).
    return doc, {"AAA": _snap(92.6, 99.0, chg=-6.4, low=87.0)}


def test_the_standing_floor_gate_now_runs_on_the_reversal_kind_too(monkeypatch):
    sent = _capture(monkeypatch)
    doc, snapshot = _zb_case()
    out = _zb({"AAA": doc}, snapshot, {"AAA": 5e9})
    assert out["pushed"] == 1 and out["skipped_floor"] == 0
    assert sent[0]["enterable"]["kind"] == EN.KIND_DEMAND

    monkeypatch.setattr(AG, "sweep_read", lambda *a, **k: {"state": "swept"})
    sent2 = _capture(monkeypatch)
    out2 = _zb({"AAA": doc}, snapshot, {"AAA": 5e9})
    assert sent2 == [] and out2["pushed"] == 0 and out2["skipped_floor"] == 1


def test_NEGATIVE_an_unreadable_floor_is_SILENCE_on_the_phone_never_a_watch_push(monkeypatch):
    """`floor_unknown -> WATCH -> push` is the BOARD rule. On the phone the
    standing gate fails CLOSED, exactly as it does on the other three kinds."""
    sent = _capture(monkeypatch)
    monkeypatch.setattr(AG, "sweep_read", lambda *a, **k: None)
    doc, snapshot = _zb_case()
    out = _zb({"AAA": doc}, snapshot, {"AAA": 5e9})
    assert sent == [] and out["pushed"] == 0 and out["skipped_floor"] == 1
    assert out["skipped_not_enterable"] == 0
    assert AG.floor_held_gate(DEM, None, read=None) is False, "the gate itself fails closed"


def test_M3_the_reversal_kind_calls_sweep_read_with_the_IDENTICAL_shape(monkeypatch):
    """One floor read in the repo. If the 🪃 call drifted from the 🧲 call the
    two kinds would disagree about the same floor on the same minute."""
    calls = []

    def spy(band, symbol=None, **kw):
        calls.append({"symbol": symbol, "kwargs": set(kw)})
        return {"state": AG.FLOOR_HELD_STATES[0]}
    monkeypatch.setattr(AG, "sweep_read", spy)
    _capture(monkeypatch)
    doc, snapshot = _zb_case()
    _zb({"AAA": doc}, snapshot, {"AAA": 5e9})
    zb_call = calls[-1]
    calls.clear()
    _da({"AAA": _doc("AAA", [DEM, RES], 95.0)}, {"AAA": _snap(91.0, 95.0, low=90.5)},
        {"AAA": 5e9})
    da_call = calls[-1]
    assert zb_call["kwargs"] == da_call["kwargs"] == {"frame", "day_low", "last", "day"}
    assert zb_call["symbol"] == da_call["symbol"] == "AAA"


# ═══════════════════════════════════════════ 7. growth (🚀 growth_demand_alert)
@pytest.fixture
def grow(monkeypatch):
    monkeypatch.setattr(GA, "_bands_for",
                        lambda s: [{"kind": "demand", "lo": 60.0, "hi": 62.0, "touches": 3},
                                   {"kind": "supply", "lo": 80.0, "hi": 82.0, "touches": 2}])
    monkeypatch.setattr(GA, "_snapshot_for",
                        lambda syms: (_ for _ in ()).throw(AssertionError("network in a unit test")))
    return _capture(monkeypatch)


def _grow_row(sym="HHH"):
    return {"symbol": sym, "price": 61.55, "sales_growth_pct": 330.2,
            "q_eps_growth_pct": 1318.2, "warnings": [],
            "zone": {"missing": False, "in_band": True, "intact": True,
                     "band": {"lo": 60.0, "hi": 62.0, "touches": 3}, "order_block": False}}


def _grow_snap(px, prev=66.0, age_sec=30, now=NOW, low=None):
    ts_ns = int((now - timedelta(seconds=age_sec)).timestamp() * 1e9)
    return {"open": px, "high": px, "low": low if low is not None else round(px * 0.995, 4),
            "close": px, "volume": 1e6,
            "change_pct": round((px / prev - 1) * 100, 2) if prev else None,
            "last_trade_price": px, "last_trade_ts_ms": ts_ns, "prev_day_close": prev}


def test_the_growth_pass_keeps_ONE_sweep_read_and_grades_that_very_state(grow, monkeypatch):
    seen = {"n": 0}

    def spy(*a, **k):
        seen["n"] += 1
        return {"state": AG.FLOOR_HELD_STATES[0], "pierce_pct": None}
    monkeypatch.setattr(AG, "sweep_read", spy)
    items, counts = GA._scan([_grow_row()], {"HHH": _grow_snap(61.55, prev=61.0)}, NOW)
    assert len(items) == 1 and seen["n"] == 1, "one floor read, kept and reused"
    assert items[0]["sweep"]["state"] == AG.FLOOR_HELD_STATES[0]
    assert items[0]["enterable"]["gates"]["floor_state"] == items[0]["sweep"]["state"]
    assert counts["skipped_not_enterable"] == 0
    assert GA.message(items[0]["row"], items[0]["band"], items[0]["room"],
                      hit=items[0]["hit"],
                      enterable=items[0]["enterable"])["enterable"]["verdict"] in (EN.READY, EN.WATCH)


def test_NEGATIVE_the_growth_floor_gate_still_refuses_a_swept_floor(grow, monkeypatch):
    monkeypatch.setattr(AG, "sweep_read", lambda *a, **k: {"state": "swept"})
    items, counts = GA._scan([_grow_row()], {"HHH": _grow_snap(61.55, prev=61.0)}, NOW)
    assert items == [] and counts["skipped_floor"] == 1 and counts["skipped_not_enterable"] == 0


def test_NEGATIVE_a_forced_BLOCKED_read_is_counted_on_the_growth_pass(grow, monkeypatch):
    monkeypatch.setattr(AG, "sweep_read", lambda *a, **k: {"state": AG.FLOOR_HELD_STATES[0]})
    monkeypatch.setattr(GA.EN, "assess", lambda **kw: {"verdict": EN.BLOCKED, "reasons": ["room"]})
    items, counts = GA._scan([_grow_row()], {"HHH": _grow_snap(61.55, prev=61.0)}, NOW)
    assert items == [] and counts["skipped_not_enterable"] == 1 and counts["skipped_floor"] == 0


# ═══════════════════════════════════════════ 8. push history + the feed
def test_push_history_persists_the_read_and_stores_None_for_anything_else(monkeypatch):
    from push import history
    rows = []
    monkeypatch.setattr(history, "_get_coll",
                        lambda: SimpleNamespace(insert_one=lambda d: rows.append(d)))
    read = EN.assess(kind=EN.KIND_DEMAND, px=91.0, band=DEM, bands=[DEM, RES],
                     prev_close=91.0, change_pct=0.0, room_ok=True, prox_ok=True,
                     floor_state=AG.FLOOR_HELD_STATES[0])
    history.record({"title": "t", "body": "b", "kind": DA.KIND, "ticker": "AAA",
                    "enterable": EN.slim(read)}, user_email="o@x", result={})
    assert rows[-1]["enterable"]["verdict"] == EN.READY
    history.record({"title": "t", "kind": DA.KIND, "enterable": "READY"}, result={})
    assert rows[-1]["enterable"] is None, "a non-dict is never stored as a read"
    history.record({"title": "t", "kind": "flashcard"}, result={})
    assert rows[-1]["enterable"] is None


def test_the_recent_feed_carries_the_key_on_EVERY_row_even_the_legacy_ones():
    from push import recent
    legacy = {"_id": "1", "ts": 10, "title": "old", "kind": DA.KIND}
    withread = {"_id": "2", "ts": 20, "title": "new", "kind": DA.KIND,
                "enterable": {"kind": EN.KIND_DEMAND, "verdict": EN.WATCH,
                              "reasons": ["weak_day"], "reason_text": [], "reason_short": []}}
    rows = recent.gather("o@x", 10, list_recent=lambda *a, **k: [dict(withread), dict(legacy)],
                         get_db=lambda: None)
    assert [r["enterable"] for r in rows] == [withread["enterable"], None]
    assert recent.normalize_breakout({"_id": "b", "ts": 5, "ticker": "AAA"})["enterable"] is None


# ═══════════════════════════════════════════ 9. alert status + the rules panel
def test_the_gate_payload_says_whether_the_study_has_reported_and_keeps_its_keys():
    gate = AS.gate_payload()
    assert gate["enterable_status"] == EN.status()
    assert gate["min_room_pct"] == float(AG.ALERT_MIN_ROOM_PCT)
    assert gate["max_above_demand_pct"] == float(AG.ALERT_MAX_ABOVE_DEMAND_PCT)
    assert gate["min_cap_usd"] == float(DA.MIN_CAP_USD) and gate["min_cap_txt"]


def test_the_divergence_counter_reaches_the_alerts_page_by_itself():
    counts = AS.counts_from_result({"ran": True, "date": DAY, "pushed": 1,
                                    "skipped_not_enterable": 3, "skipped_floor": 2,
                                    "hits": [1, 2]})
    assert counts["skipped_not_enterable"] == 3 and counts["skipped_floor"] == 2
    assert "date" not in counts and counts["hits"] == 2


def test_the_rules_section_is_built_from_the_enforcing_constants():
    sec = RI.sections()["enterable"]
    blob = repr(sec)
    assert "enterable" in RI.SECTION_KEYS
    assert ("%g" % AG.ALERT_MIN_ROOM_PCT) in blob or str(int(AG.ALERT_MIN_ROOM_PCT)) in blob
    assert str(int(PE.RECLAIM_STOP_PCT)) in blob and str(int(PE.ARRIVAL_STOP_PCT)) in blob
    assert str(int(PE.WEAK_DAY_UP_PCT)) in blob and str(int(PE.NORMAL_DAY_UP_PCT)) in blob
    for state in AG.FLOOR_HELD_STATES:
        assert state in blob
    for tab, kind in EN.KIND_BY_TAB.items():
        if kind == EN.KIND_NA:
            assert tab in blob, f"the n/a tabs are named: {tab}"
    assert "skipped_not_enterable" in blob
    assert "bounc" not in blob.lower(), "reversal, never the other word (2026-09-09)"


def test_NEGATIVE_a_broken_measured_verdict_never_takes_the_rules_off_the_page(monkeypatch):
    monkeypatch.setattr(EN, "measured_verdict",
                        lambda: (_ for _ in ()).throw(RuntimeError("half-written MEASURED")))
    sec = RI.sections()["enterable"]
    assert sec["picks"], "the rules built from constants survive"
    assert any("has not reported" in a for a in sec["alerts"])
    assert RI.payload("enterable")["sections"]["enterable"] is not None


# ═══════════════════════════════════════════ 10. source guards
def test_SOURCE_GUARD_no_push_module_reaches_into_the_explosive_read():
    for mod in ("supply_demand/demand_alerts.py", "supply_demand/zone_edge.py",
                "supply_demand/zone_bounce_alerts.py", "growth/alerts.py"):
        src = BACKEND.joinpath(mod).read_text()
        assert "import explosive" not in src and "explosive." not in src, \
            f"{mod} must reach the floor read through enterable, not explosive"


def test_SOURCE_GUARD_every_push_path_passes_the_kind_AND_the_gates_it_already_ran():
    """m8: a call that omitted `room_ok=` would RECOMPUTE a gate the line above
    just ran, and the recorded verdict would stop being the phone's verdict."""
    for mod, fn in (("supply_demand/demand_alerts.py", None),
                    ("supply_demand/zone_edge.py", None),
                    ("supply_demand/zone_bounce_alerts.py", None),
                    ("growth/alerts.py", None)):
        src = BACKEND.joinpath(mod).read_text()
        chunks = src.split("EN.assess(")[1:]
        assert chunks, f"{mod} never records the read"
        for c in chunks:
            call = c[:400]
            assert "kind=" in call, f"{mod}: the read must be told its kind"
            assert "room_ok=" in call, f"{mod}: the room gate is passed through"
            if "KIND_SUPPLY_BREAK" not in call:
                assert "prox_ok=" in call, f"{mod}: the proximity gate is passed through"
