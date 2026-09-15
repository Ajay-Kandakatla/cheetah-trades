"""2026-09-14 alert-logic review fixes — behavioural + NEGATIVE pins.

Findings (verified on live data that day):
  1. one 🧲 delivered twice: zone_edge (1-min) and demand_alerts (5-min) raced
     on the shared dedupe key           -> atomic claim BEFORE the send
  2. one level rang twice with two stops when a broken-supply shelf and a
     demand band overlap                -> overlap skip, one $in read by symbol
  3. 🚀 growth_demand_alert rang at 09:00 on a Sunday-built board with Friday's
     close as the print                 -> live print, arrival rule, RTH window
  4. floor_held_gate read a frame that ends yesterday, so a floor swept and
     reclaimed TODAY read "intact"      -> the session's low/print merged in
  5. demand_alerts pushed on the day aggregate's close with no freshness check
                                        -> bulk_snapshot + print_from_snapshot
  6. /alerts/status said "$1B+" four days after the floor moved to $700M
                                        -> built from demand_alerts.MIN_CAP_USD
  7. the Journal lane blurb said "bounces"   -> "reversals" (his 2026-09-09 word)

Owner rules honoured: no new number anywhere (stale windows, gates and floors
are the existing constants); nothing here changes WHICH alerts pass a gate
beyond the two dedupe rules listed.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import alert_gates as AG          # noqa: E402
from supply_demand import alert_status as AS         # noqa: E402
from supply_demand import demand_alerts as DA        # noqa: E402
from supply_demand import zone_bounce_alerts as ZB   # noqa: E402
from supply_demand import zone_edge as ZE            # noqa: E402
from growth import alerts as GA                      # noqa: E402

ET = ZoneInfo("America/New_York")
NOW = datetime(2026, 9, 14, 11, 0, tzinfo=ET)          # a Monday, RTH
DAY = "2026-09-14"
DEM = {"kind": "demand", "lo": 90.0, "hi": 92.0, "touches": 3, "strength": 50.0}
SHELF = {"kind": "supply", "lo": 91.5, "hi": 93.0, "touches": 2, "strength": 30.0}   # overlaps DEM
RES = {"kind": "supply", "lo": 100.0, "hi": 102.0, "touches": 2, "strength": 40.0}


# ─────────────────────────────────────────────────────────────── fakes
class Coll:
    """pymongo-shaped: `$setOnInsert` only on an insert, update_one reports
    upserted_id / matched_count, find by `_id $in` or by `symbol $in`."""

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


class RacingColl(Coll):
    """Another pass claims `steal` the instant this one reads the key as
    unseen — the exact interleaving of finding 1."""

    def __init__(self, steal: str):
        super().__init__()
        self.steal = steal

    def find(self, q, projection=None):
        yield from super().find(q, projection)
        # the other pass wins the insert between our read and our claim
        self.docs.setdefault(self.steal, {"_id": self.steal, "symbol": self.steal.split(":")[0],
                                          "source": "the-other-pass"})


def _capture(monkeypatch, result=None):
    from push import sender
    sent = []

    def fake(owner, payload, kind=None):
        sent.append({"owner": owner, "kind_arg": kind, **payload})
        return result or {"sent": 1, "failed": 0, "total_targets": 1}
    monkeypatch.setattr(sender, "send_to_user", fake)
    return sent


def _snap(last, prev, chg=-3.0, low=None, *, now=NOW, age_sec=30):
    ts_ns = int((now - timedelta(seconds=age_sec)).timestamp() * 1e9)
    lo = last if low is None else low
    return {"open": last, "high": last, "low": lo, "close": last, "volume": 1e6,
            "change_pct": chg, "last_trade_price": last, "last_trade_ts_ms": ts_ns,
            "prev_day_close": prev}


def _bounce(last, prev, chg=-3.0, **kw):
    """Reads as a reversal off DEM: the day's low in the band, print ≥ 0.5% off it."""
    return _snap(last, prev, chg, low=round(min(91.9, last * 0.988), 2), **kw)


# The REAL structure reads, captured before the autouse stub below replaces
# them — section 4 tests the sweep read itself and puts them back.
_REAL_READS = {"sweep_read": AG.sweep_read, "daily_frame": AG.daily_frame}


@pytest.fixture
def real_sweep(monkeypatch):
    """Undo `_clean_structure` for the tests whose SUBJECT is the floor read."""
    for k, v in _REAL_READS.items():
        monkeypatch.setattr(AG, k, v)


@pytest.fixture(autouse=True)
def _clean_structure(monkeypatch):
    """Daily-bar reads stubbed as the sibling suites do: clean structure,
    bullish turn, floor intact — the subject here is dedupe and freshness."""
    for mod in (ZE.AG, DA.AG):
        monkeypatch.setattr(mod, "mood_read", lambda sym, frame=None: None)
        monkeypatch.setattr(mod, "daily_frame", lambda sym, frame=None: frame)
        monkeypatch.setattr(mod, "knife_read", lambda sym, frame=None: {"knife": False, "trend": "rising"})
        monkeypatch.setattr(mod, "sweep_read",
                            lambda band, symbol=None, frame=None, window=None, **kw:
                                {"state": "intact", "pierce_pct": None, "reclaim_bars": None, "vol_x": None})
        monkeypatch.setattr(mod, "reversal_mood_read",
                            lambda sym, frame=None, bars=None: {"score": 40.0, "label": "bullish",
                                                                "bars": 60, "bullish": True})
    monkeypatch.setattr(DA.BC, "bullish_context",
                        lambda sym, frame=None, with_sentiment=True: {"gex": None, "patterns": None,
                                                                      "sentiment": None})


def _ze(store, snapshot, caps, *, coll_demand=None, coll_break=None, now=NOW):
    colls = {"coll_break": coll_break or Coll(), "coll_demand": coll_demand or Coll(),
             "latest_coll": Coll(), "track_coll": Coll()}
    out = ZE.check_once(push=True, force=True, track=False, store=store, snapshot=snapshot,
                        caps=caps, names={}, owner="o@x", now=now, **colls)
    return out, colls


def _doc(sym, bands, prev):
    return {"_id": f"{sym}:{DAY}", "symbol": sym, "date": DAY, "geom": "board",
            "bands": bands, "atr14": 1.0, "prev_close": prev, "high_252": None}


def _board(sym="AAA", band=DEM):
    return {"rows": [{"symbol": sym, "name": f"{sym} Inc", "entry_zone": dict(band)}],
            "approaching_rows": []}


# ═════════════════════════════════════════════ 1. atomic claim (the race)
def test_claim_key_is_first_writer_wins_and_release_reopens_it():
    c = Coll()
    assert DA.claim_key(c, "K", {"symbol": "AAA"}) is True
    assert c.docs["K"]["symbol"] == "AAA"
    assert DA.claim_key(c, "K", {"symbol": "AAA", "source": "late"}) is False, "second writer sees 'claimed'"
    assert c.docs["K"].get("source") != "late", "$setOnInsert never clobbers the first claim"
    DA.release_key(c, "K")
    assert "K" not in c.docs and DA.claim_key(c, "K", {}) is True


def test_NEGATIVE_no_coll_or_a_write_error_claims_true_never_never():
    """The same side the `$in` dedupe read fails on: push again, not never."""
    assert DA.claim_key(None, "K", {}) is True
    DA.release_key(None, "K")                                          # no-op, no raise

    class Broken(Coll):
        def update_one(self, *a, **k):
            raise RuntimeError("down")

        def delete_one(self, *a, **k):
            raise RuntimeError("down")
    assert DA.claim_key(Broken(), "K", {}) is True
    DA.release_key(Broken(), "K")


def test_zone_edge_claims_before_it_sends_and_a_concurrent_claim_silences_it(monkeypatch):
    """Finding 1, the exact interleaving: the 5-min pass inserts the key
    between zone_edge's dedupe read and its send. Before: two identical 🧲.
    After: zone_edge's claim reports 'existed' and it sends nothing."""
    sent = _capture(monkeypatch)
    key = DA.state_key("AAA", DEM, DAY, "at")
    coll = RacingColl(steal=key)
    out, _ = _ze({"AAA": _doc("AAA", [DEM, RES], 95.0)}, {"AAA": _bounce(91.0, 95.0)},
                 {"AAA": 5e9}, coll_demand=coll)
    assert sent == [] and out["pushed"] == 0 and out["claimed_elsewhere"] == 1
    assert coll.docs[key]["source"] == "the-other-pass", "the other pass's claim survives untouched"


def test_demand_alerts_claims_before_it_sends_and_a_concurrent_claim_silences_it(monkeypatch):
    sent = _capture(monkeypatch)
    key = DA.state_key("AAA", DEM, DAY, "at")
    coll = RacingColl(steal=key)
    store = {"AAA": _doc("AAA", [DEM, RES], 95.0)}
    out = DA.check_once(force=True, board=_board(), snapshot={"AAA": _bounce(91.0, 95.0)},
                        caps={"AAA": 5e9}, coll=coll, owner="o@x", now=NOW, store=store)
    assert sent == [] and out["pushed"] == 0 and out["claimed_elsewhere"] == 1
    assert coll.docs[key]["source"] == "the-other-pass"


def test_the_two_passes_ring_one_key_exactly_once_between_them(monkeypatch):
    """End to end on ONE shared coll: zone_edge rings, demand_alerts is quiet;
    then the other order. Both claims are stamped with their source."""
    sent = _capture(monkeypatch)
    store = {"AAA": _doc("AAA", [DEM, RES], 95.0)}
    shared = Coll()
    out, _ = _ze(store, {"AAA": _bounce(91.0, 95.0)}, {"AAA": 5e9}, coll_demand=shared)
    assert out["pushed"] == 1 and len(sent) == 1
    key = DA.state_key("AAA", DEM, DAY, "at")
    assert shared.docs[key]["source"] == "zone_edge" and shared.docs[key]["tier"] == "at"
    da = DA.check_once(force=True, board=_board(), snapshot={"AAA": _bounce(91.0, 95.0)},
                       caps={"AAA": 5e9}, coll=shared, owner="o@x", now=NOW, store=store)
    assert da["pushed"] == 0 and len(sent) == 1
    # and the other way round on a fresh coll
    shared2 = Coll()
    da2 = DA.check_once(force=True, board=_board(), snapshot={"AAA": _bounce(91.0, 95.0)},
                        caps={"AAA": 5e9}, coll=shared2, owner="o@x", now=NOW, store=store)
    assert da2["pushed"] == 1 and shared2.docs[key]["source"] == "demand_alerts"
    out2, _ = _ze(store, {"AAA": _bounce(91.0, 95.0)}, {"AAA": 5e9}, coll_demand=shared2)
    assert out2["pushed"] == 0 and len(sent) == 2


def test_a_transport_failure_releases_the_claim_so_the_next_pass_retries(monkeypatch):
    """Today's semantics kept: a send that raises, or returns sent=0 with
    targets, leaves NO state — the key is free again; "nobody targeted" stays
    terminal."""
    key = DA.state_key("AAA", DEM, DAY, "at")
    store = {"AAA": _doc("AAA", [DEM, RES], 95.0)}
    coll = Coll()
    _capture(monkeypatch, result={"sent": 0, "failed": 1, "total_targets": 1})
    out, _ = _ze(store, {"AAA": _bounce(91.0, 95.0)}, {"AAA": 5e9}, coll_demand=coll)
    assert out["pushed"] == 0 and coll.docs == {} and coll.calls.count("delete_one") == 1

    from push import sender
    monkeypatch.setattr(sender, "send_to_user", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("apns")))
    out, _ = _ze(store, {"AAA": _bounce(91.0, 95.0)}, {"AAA": 5e9}, coll_demand=coll)
    assert out["pushed"] == 0 and coll.docs == {}, "an exception in transport also releases"

    _capture(monkeypatch, result={"sent": 0, "failed": 0, "total_targets": 0})
    out, _ = _ze(store, {"AAA": _bounce(91.0, 95.0)}, {"AAA": 5e9}, coll_demand=coll)
    assert out["pushed"] == 1 and key in coll.docs, "nobody targeted = done today"
    da = DA.check_once(force=True, board=_board(), snapshot={"AAA": _bounce(91.0, 95.0)},
                       caps={"AAA": 5e9}, coll=coll, owner="o@x", now=NOW, store=store)
    assert da["pushed"] == 0, "and the 5-min pass honours the terminal claim"


def test_a_digest_drops_names_another_pass_claimed_and_releases_all_on_failure(monkeypatch):
    sent = _capture(monkeypatch)
    syms = [f"D{i}" for i in range(5)]                                   # 3 singles + 2 digest
    store = {s: _doc(s, [DEM, RES], 95.0) for s in syms}
    snap = {s: _bounce(91.0 + i * 0.01, 95.0) for i, s in enumerate(syms)}
    stolen = DA.state_key("D4", DEM, DAY, "at")
    coll = RacingColl(steal=stolen)
    out, _ = _ze(store, snap, {s: 5e9 for s in syms}, coll_demand=coll)
    assert out["pushed"] == 4 and out["claimed_elsewhere"] == 1
    digest = [m for m in sent if m["title"].startswith("🧲 Demand zone")]
    assert len(digest) == 1 and "D4" not in digest[0]["body"] and "D3" in digest[0]["body"]
    # failure path: every digest claim is released
    coll2 = Coll()
    _capture(monkeypatch, result={"sent": 0, "failed": 1, "total_targets": 1})
    out2, _ = _ze(store, snap, {s: 5e9 for s in syms}, coll_demand=coll2)
    assert out2["pushed"] == 0 and coll2.docs == {}


# ═════════════════════════════════════════ 2. overlapping bands = one level
def test_bands_overlap_is_closed_interval_and_garbage_never_overlaps():
    assert DA.bands_overlap({"lo": 90, "hi": 92}, {"lo": 91.5, "hi": 93}) is True
    assert DA.bands_overlap({"lo": 90, "hi": 92}, {"lo": 92.0, "hi": 93}) is True, "touching = one level"
    assert DA.bands_overlap({"lo": 90, "hi": 92}, {"lo": 92.01, "hi": 93}) is False
    assert DA.bands_overlap({"lo": 90, "hi": 92}, {"lo": 80, "hi": 89.99}) is False
    assert DA.bands_overlap({"lo": 90, "hi": 92}, {"lo": None, "hi": 93}) is False
    assert DA.bands_overlap({"lo": float("nan"), "hi": 92}, {"lo": 91, "hi": 93}) is False


def test_recorded_today_is_one_read_by_symbol_and_reads_the_day_off_the_key():
    c = Coll()
    c.docs["AAA:90.00-92.00:2026-09-14:at"] = {"_id": "AAA:90.00-92.00:2026-09-14:at", "symbol": "AAA",
                                               "band": {"lo": 90.0, "hi": 92.0}}
    c.docs["AAA:80.00-82.00:2026-09-11:at"] = {"_id": "AAA:80.00-82.00:2026-09-11:at", "symbol": "AAA",
                                               "band": {"lo": 80.0, "hi": 82.0}}
    c.docs["BBB:50.00-52.00:2026-09-14:at"] = {"_id": "BBB:50.00-52.00:2026-09-14:at", "symbol": "BBB",
                                               "band": {"lo": 50.0, "hi": 52.0}}
    rec = DA.recorded_today(c, ["AAA", "bbb"], DAY)
    assert c.calls == ["find"]
    assert [r["key"] for r in rec["AAA"]] == ["AAA:90.00-92.00:2026-09-14:at"], "Friday's key never counts"
    assert rec["BBB"][0]["lo"] == 50.0
    assert DA.recorded_today(c, [], DAY) == {} and c.calls == ["find"], "no symbols = no read"
    assert DA.recorded_today(None, ["AAA"], DAY) == {}

    class Broken(Coll):
        def find(self, *a, **k):
            raise RuntimeError("down")
    assert DA.recorded_today(Broken(), ["AAA"], DAY) == {}, "read failure = push again, never never"


def test_zone_edge_skips_a_demand_band_that_overlaps_a_shelf_already_rung_today(monkeypatch):
    """Finding 2: the broken-supply shelf 91.5-93 rang at 09:41 (titled
    'demand', stop under 91.5); the demand band 90-92 under it must NOT ring
    at 09:42 with a second stop under 90 — same prices, one level."""
    sent = _capture(monkeypatch)
    coll = Coll()
    coll.docs[DA.state_key("AAA", SHELF, DAY, "at")] = {
        "_id": DA.state_key("AAA", SHELF, DAY, "at"), "symbol": "AAA",
        "band": {"lo": SHELF["lo"], "hi": SHELF["hi"]}, "source": "zone_edge"}
    store = {"AAA": _doc("AAA", [DEM, RES], 95.0)}
    out, colls = _ze(store, {"AAA": _bounce(91.0, 95.0)}, {"AAA": 5e9}, coll_demand=coll)
    assert sent == [] and out["pushed"] == 0 and out["skipped_overlap"] == 1
    assert out["payload"]["counts"]["skipped_overlap"] == 1, "the /alerts page can explain the quiet phone"
    assert len(out["near_demand"]) == 1, "the BOARD still lists it"
    assert "skipped_overlap" in ZE.empty_payload()["counts"]


def test_NEGATIVE_a_band_that_does_not_overlap_still_rings(monkeypatch):
    """The skip is about overlapping PRICES, not about the symbol: a second,
    lower band on the same name rings normally."""
    sent = _capture(monkeypatch)
    coll = Coll()
    lowband = {"kind": "demand", "lo": 80.0, "hi": 82.0, "touches": 3}
    coll.docs[DA.state_key("AAA", lowband, DAY, "at")] = {
        "_id": DA.state_key("AAA", lowband, DAY, "at"), "symbol": "AAA", "band": {"lo": 80.0, "hi": 82.0}}
    store = {"AAA": _doc("AAA", [DEM, RES], 95.0)}
    out, _ = _ze(store, {"AAA": _bounce(91.0, 95.0)}, {"AAA": 5e9}, coll_demand=coll)
    assert out["pushed"] == 1 and len(sent) == 1 and out["skipped_overlap"] == 0


def test_demand_alerts_also_skips_an_overlapping_level(monkeypatch):
    sent = _capture(monkeypatch)
    coll = Coll()
    coll.docs[DA.state_key("AAA", SHELF, DAY, "at")] = {
        "_id": DA.state_key("AAA", SHELF, DAY, "at"), "symbol": "AAA",
        "band": {"lo": SHELF["lo"], "hi": SHELF["hi"]}, "source": "zone_edge"}
    store = {"AAA": _doc("AAA", [DEM, RES], 95.0)}
    out = DA.check_once(force=True, board=_board(), snapshot={"AAA": _bounce(91.0, 95.0)},
                        caps={"AAA": 5e9}, coll=coll, owner="o@x", now=NOW, store=store)
    assert sent == [] and out["pushed"] == 0 and out["skipped_overlap"] == 1
    assert len(out["hits"]) == 1, "listed, counted, not rung"
    assert coll.calls.count("find") == 1 and "find_one" not in coll.calls, "one read, never per candidate"


# ═════════════════════════════════════════ 4. the session bar in the floor read
def _frame(n=30, close=105.0, low=104.5, start="2026-08-03"):
    idx = pd.bdate_range(start, periods=n)
    return pd.DataFrame({"open": [close] * n, "high": [close * 1.01] * n, "low": [low] * n,
                         "close": [close] * n, "volume": [1_000_000] * n}, index=idx)


BAND = {"kind": "demand", "lo": 100.0, "hi": 104.0, "touches": 3}
TODAY = datetime(2026, 9, 14).date()


def test_with_session_bar_appends_today_when_the_frame_ends_yesterday():
    df = _frame()                                              # ends 2026-09-11 (Fri)
    out = AG.with_session_bar(df, day_low=99.0, last=103.0, day=TODAY)
    assert len(out) == len(df) + 1 and pd.Timestamp(out.index[-1]).date() == TODAY
    assert out.iloc[-1]["low"] == 99.0 and out.iloc[-1]["close"] == 103.0 and out.iloc[-1]["high"] == 103.0
    assert out.iloc[-1]["volume"] != out.iloc[-1]["volume"], "the forming bar's volume is NaN, never 0"
    assert len(df) == 30, "the cached frame is never mutated"


def test_with_session_bar_merges_into_a_frame_that_already_holds_today():
    """The hourly cache patch puts today's in-progress bar in from ~10:00 ET:
    merge the fresher low/print into it instead of appending a duplicate day."""
    df = _frame(start="2026-08-04")                             # bdate_range ends 2026-09-14
    assert pd.Timestamp(df.index[-1]).date() == TODAY
    out = AG.with_session_bar(df, day_low=99.0, last=106.0, day=TODAY)
    assert len(out) == len(df)
    assert out.iloc[-1]["low"] == 99.0 and out.iloc[-1]["close"] == 106.0
    assert out.iloc[-1]["high"] == max(106.0, 105.0 * 1.01), "high widened to the print, never lowered"
    assert df.iloc[-1]["low"] == 104.5, "the cached frame is never mutated"
    out2 = AG.with_session_bar(df, day_low=104.8, last=None, day=TODAY)
    assert out2.iloc[-1]["low"] == 104.5, "merge keeps the lower low"


def test_NEGATIVE_an_unknown_day_low_leaves_the_frame_exactly_as_it_was():
    df = _frame()
    for bad in (None, 0, -1, "x", float("nan")):
        assert AG.with_session_bar(df, bad, 103.0, TODAY) is df
    assert AG.with_session_bar(None, 99.0, 103.0, TODAY) is None


def test_a_floor_swept_and_reclaimed_THIS_MORNING_is_no_longer_intact(real_sweep):
    """Finding 4. Frame ends Friday, clean. Today's low pierced the 100 floor
    (-1%) and the print is back above it: before, 'intact' (the frame never
    saw today); now 'swept' and the gate refuses."""
    df = _frame()
    assert AG.sweep_read(BAND, "X", frame=df, day=TODAY)["state"] == "intact"       # the old read
    r = AG.sweep_read(BAND, "X", frame=df, day_low=99.0, last=103.0, day=TODAY)
    assert r["state"] == "swept" and r["vol_x"] is None and 0.9 < r["pierce_pct"] < 1.1
    assert AG.floor_held_gate(BAND, "X", frame=df, day_low=99.0, last=103.0, day=TODAY) is False
    # still under the floor at the print = broken, also refused
    r2 = AG.sweep_read(BAND, "X", frame=df, day_low=99.0, last=99.5, day=TODAY)
    assert r2["state"] == "broken"
    assert AG.floor_held_gate(BAND, "X", frame=df, day_low=99.0, last=99.5, day=TODAY) is False


def test_NEGATIVE_a_day_low_that_held_the_floor_stays_intact(real_sweep):
    """Not a loosening AND not a tightening on a clean day: a low above the
    stop shelf (SWEEP_MIN_PIERCE_PCT under the floor) changes nothing."""
    df = _frame()
    assert AG.sweep_read(BAND, "X", frame=df, day_low=100.5, last=103.0, day=TODAY)["state"] == "intact"
    assert AG.floor_held_gate(BAND, "X", frame=df, day_low=100.5, last=103.0, day=TODAY) is True
    assert AG.floor_held_gate(BAND, "X", frame=df, day_low=None, last=103.0, day=TODAY) is True, \
        "unknown day low = today's read, unchanged"
    assert AG.floor_held_gate(BAND, "X", read={"state": "intact"}, day_low=99.0) is True, "a read passed in wins"


def test_zone_edge_and_demand_alerts_hand_the_sessions_low_to_the_floor_read(monkeypatch):
    seen = []

    def spy(band, symbol=None, frame=None, window=None, **kw):
        seen.append(dict(kw, symbol=symbol))
        return {"state": "intact", "pierce_pct": None, "reclaim_bars": None, "vol_x": None}
    monkeypatch.setattr(ZE.AG, "sweep_read", spy)
    _capture(monkeypatch)
    store = {"AAA": _doc("AAA", [DEM, RES], 95.0)}
    _ze(store, {"AAA": _bounce(91.0, 95.0)}, {"AAA": 5e9})
    assert seen and seen[0]["symbol"] == "AAA" and seen[0]["day_low"] == 89.91 and seen[0]["last"] == 91.0
    assert seen[0]["day"] == NOW.date()
    seen.clear()
    DA.check_once(force=True, board=_board(), snapshot={"AAA": _bounce(91.0, 95.0)}, caps={"AAA": 5e9},
                  coll=Coll(), owner="o@x", now=NOW, store=store)
    assert seen and seen[0]["day_low"] == 89.91 and seen[0]["last"] == 91.0 and seen[0]["day"] == NOW.date()


# ═════════════════════════════════════════ 5. demand_alerts reads a FRESH print
def test_live_from_snapshot_is_the_last_trade_within_the_5_min_siblings_window():
    fresh = _bounce(91.0, 95.0)
    fresh["close"] = 88.0                                       # the lagging aggregate close
    stale = _bounce(91.0, 95.0, age_sec=ZB.STALE_PRINT_SEC + 1)
    live, n = DA.live_from_snapshot({"AAA": fresh, "OLD": stale, "NIL": {}}, NOW.timestamp())
    assert n == 1 and set(live) == {"AAA"}
    assert live["AAA"] == {"price": 91.0, "change_pct": -3.0, "prev_day_close": 95.0, "low": 89.91}, \
        "the print is the last TRADE, never the aggregate close"
    assert DA.SNAPSHOT_STALE_SEC == ZB.STALE_PRINT_SEC == 600, "the existing 5-minute window, no new number"


def test_the_pass_counts_stale_prints_for_the_alerts_page_and_never_pushes_them(monkeypatch):
    sent = _capture(monkeypatch)
    store = {"AAA": _doc("AAA", [DEM, RES], 95.0), "OLD": _doc("OLD", [DEM, RES], 95.0)}
    board = {"rows": [{"symbol": s, "name": s, "entry_zone": dict(DEM)} for s in ("AAA", "OLD")],
             "approaching_rows": []}
    pc = Coll()
    out = DA.check_once(force=True, board=board,
                        snapshot={"AAA": _bounce(91.0, 95.0),
                                  "OLD": _bounce(91.0, 95.0, age_sec=3 * 3600)},   # the 13:13 Massive lag
                        caps={"AAA": 5e9, "OLD": 5e9}, coll=Coll(), owner="o@x", now=NOW,
                        store=store, pass_coll=pc)
    assert out["stale_print"] == 1 and out["priced"] == 1 and out["pushed"] == 1
    assert [m["ticker"] for m in sent] == ["AAA"]
    assert pc.docs["demand_alert"]["counts"]["stale_print"] == 1, "/alerts/status shows it like the other passes"


def test_NEGATIVE_the_cron_path_takes_bulk_snapshot_not_bulk_live_prices(monkeypatch):
    import inspect
    from sepa import prices
    called = []
    monkeypatch.setattr(prices, "bulk_snapshot", lambda syms: called.append(("snapshot", tuple(syms))) or {})
    monkeypatch.setattr(prices, "bulk_live_prices",
                        lambda syms: (_ for _ in ()).throw(AssertionError("aggregate close")))
    out = DA.check_once(force=True, board=_board(), caps={"AAA": 5e9}, coll=Coll(), owner="o@x", now=NOW,
                        store={"AAA": _doc("AAA", [DEM, RES], 95.0)})
    assert called == [("snapshot", ("AAA",))] and out["ran"] and out["pushed"] == 0
    src = inspect.getsource(DA._check_once)
    assert "bulk_live_prices" not in src and "bulk_snapshot(syms)" in src and "live_from_snapshot(" in src


# ═════════════════════════════════════════ 3. growth alert on the live print
def _grow_row(sym="HHH"):
    return {"symbol": sym, "price": 61.55, "sales_growth_pct": 330.2, "q_eps_growth_pct": 1318.2,
            "warnings": [], "zone": {"missing": False, "in_band": True, "intact": True,
                                     "band": {"lo": 60.0, "hi": 62.0, "touches": 3}, "order_block": False}}


def _grow_snap(px, prev=66.0, age_sec=30, now=NOW, low=None):
    ts_ns = int((now - timedelta(seconds=age_sec)).timestamp() * 1e9)
    return {"open": px, "high": px, "low": low if low is not None else round(px * 0.995, 4), "close": px,
            "volume": 1e6, "change_pct": round((px / prev - 1) * 100, 2) if prev else None,
            "last_trade_price": px, "last_trade_ts_ms": ts_ns, "prev_day_close": prev}


@pytest.fixture
def grow(monkeypatch):
    monkeypatch.setattr(GA, "_bands_for", lambda s: [{"kind": "demand", "lo": 60.0, "hi": 62.0, "touches": 3},
                                                     {"kind": "supply", "lo": 80.0, "hi": 82.0, "touches": 2}])
    monkeypatch.setattr(GA.AG, "sweep_read", lambda *a, **k: {"state": "intact"})
    monkeypatch.setattr(GA, "_snapshot_for",
                        lambda syms: (_ for _ in ()).throw(AssertionError("network snapshot in a unit test")))
    return _capture(monkeypatch)


def test_the_growth_pass_is_quiet_outside_the_demand_alert_window(grow):
    sunday_9 = datetime(2026, 9, 13, 9, 0, tzinfo=ET)
    monday_9 = datetime(2026, 9, 14, 9, 0, tzinfo=ET)          # the 09:00 cron tick that rang HHH
    for when in (sunday_9, monday_9, datetime(2026, 9, 14, 16, 1, tzinfo=ET)):
        out = GA.run(now=when, rows=[_grow_row()], snapshot={"HHH": _grow_snap(61.55, now=when)}, coll=Coll())
        assert out["ran"] is False and "outside RTH" in out["reason"] and grow == []
    assert DA.in_session(datetime(2026, 9, 14, 9, 32, tzinfo=ET)) is True
    out = GA.run(now=NOW, rows=[_grow_row()], snapshot={"HHH": _grow_snap(61.55)}, coll=Coll())
    assert out["ran"] is True and out["individual"] == 1 and len(grow) == 1
    assert grow[0]["body"].startswith("$61.55 · in demand $60–62") and grow[0]["kind"] == "growth_demand_alert"


def test_HHH_below_its_band_on_fridays_close_never_rings_again(grow):
    """The live finding: the board's stored row said in_band (Friday) while the
    tape sat UNDER the band. Under the floor is not an arrival."""
    out = GA.run(now=NOW, rows=[_grow_row()], snapshot={"HHH": _grow_snap(59.2, prev=61.5)}, coll=Coll())
    assert out["candidates"] == 0 and out["no_arrival"] == 1 and grow == []
    out = GA.run(now=NOW, rows=[_grow_row()],
                 snapshot={"HHH": _grow_snap(61.55, age_sec=ZB.STALE_PRINT_SEC + 60)}, coll=Coll())
    assert out["candidates"] == 0 and out["stale_print"] == 1 and grow == []


def test_the_growth_pass_claims_then_sends_and_releases_on_failure(grow, monkeypatch):
    coll = Coll()
    out = GA.run(now=NOW, rows=[_grow_row()], snapshot={"HHH": _grow_snap(61.55)}, coll=coll)
    key = GA._state_key("HHH", {"lo": 60.0, "hi": 62.0}, DAY)
    assert out["individual"] == 1 and coll.docs[key]["source"] == "growth_alerts"
    out2 = GA.run(now=NOW, rows=[_grow_row()], snapshot={"HHH": _grow_snap(61.55)}, coll=coll)
    assert out2["fresh"] == 0 and out2["individual"] == 0 and len(grow) == 1, "once per band per day"
    # transport failure: the claim is released (before 2026-09-14 the key was remembered even on a raise)
    coll2 = Coll()
    from push import sender
    monkeypatch.setattr(sender, "send_to_user", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("apns")))
    out3 = GA.run(now=NOW, rows=[_grow_row()], snapshot={"HHH": _grow_snap(61.55)}, coll=coll2)
    assert out3["individual"] == 0 and coll2.docs == {}
    # dry run reads everything, records nothing
    out4 = GA.run(dry_run=True, now=NOW, rows=[_grow_row()], snapshot={"HHH": _grow_snap(61.55)}, coll=coll2)
    assert out4["individual"] == 1 and coll2.docs == {}


# ═════════════════════════════════════════ 6. the disclaimer reads the constant
def test_the_status_disclaimer_is_built_from_the_cap_floor_constant():
    p = AS.status_payload(pass_coll=Coll(), latest_coll=Coll(), now=NOW)
    assert "$700M+" in p["disclaimer"] and "$1B" not in p["disclaimer"]
    assert AS.cap_floor_txt(DA.MIN_CAP_USD) in p["disclaimer"]
    assert AS.cap_floor_txt(700_000_000.0) == "$700M" and AS.cap_floor_txt(1e9) == "$1B"
    assert AS.cap_floor_txt(1.5e9) == "$1.5B" and AS.cap_floor_txt(2.5e8) == "$250M"
    assert "{cap}" in AS.DISCLAIMER_TEMPLATE and "not advice" in p["disclaimer"]


def test_NEGATIVE_the_disclaimer_never_retypes_a_dollar_figure():
    src = (Path(__file__).resolve().parents[2] / "backend/supply_demand/alert_status.py").read_text()
    body = src[src.index("DISCLAIMER_TEMPLATE = ("):src.index("def cap_floor_txt")]
    assert "$1B" not in body and "$700M" not in body, "the floor is read from demand_alerts.MIN_CAP_USD, never typed"
    head = src.split("def _coll")[0]
    assert "from . import demand_alerts" not in head, "module-level import back would be a cycle"


# ═════════════════════════════════════════ 7. the word he reads
def test_the_journal_lane_blurb_says_reversal_never_bounce():
    tsx = Path(__file__).resolve().parents[2] / "frontend/src/components/JournalByStrategy.tsx"
    if not tsx.exists():
        pytest.skip("frontend tree absent (api container) — pinned by JournalByStrategy.test.tsx there")
    src = tsx.read_text()
    meta = src[src.index("STRATEGY_META"):src.index("const UNKNOWN_GLYPH")]
    assert "bounc" not in meta.lower() and "reversals off a demand band" in meta


# ═════════════════════════════════════════ docs + source guards
def test_the_docs_carry_the_review_note():
    root = Path(__file__).resolve().parents[2] / "docs"
    for rel in ("supply_demand/zone_edge.md", "supply_demand/demand_alerts.md",
                "supply_demand/alerts_page.md", "supply_demand/stop_hunt.md", "growth/explosive_growth.md"):
        p = root / rel
        if not p.exists():
            pytest.skip("docs tree absent (api container)")
        assert "2026-09-14 review fixes" in p.read_text(), rel
    page = (root / "supply_demand/alerts_page.md").read_text()
    assert "known cap ≥ $700M only" in page and "$1B only" not in page, "the Universe row follows the constant"
    assert "cap known and **< $1B**" not in page and "under the floor" in page, "the skipped_cap row follows the constant"


def test_zone_edge_never_records_after_the_send_anymore():
    """The whole fix is claim-FIRST: no `_record(` after a send, no
    read-only `_already(` anywhere on the demand path."""
    import inspect
    src = inspect.getsource(ZE.check_once)
    assert "_record_break(" not in src and "DA._record(" not in src and "_already(" not in src
    assert "_claim_break(" in src and "DA.claim(" in src and "DA.release_key(" in src
    assert "DA.recorded_today(" in src and "DA.overlapping_key(" in src
    dsrc = inspect.getsource(DA._check_once)
    assert "_already(" not in dsrc and "claim(" in dsrc and "release_key(" in dsrc
    assert "recorded_today(" in dsrc and "overlapping_key(" in dsrc
