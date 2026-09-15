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

Follow-up (adversarial review of 792cfe1, the same day — section 8):
  F1. a digest whose send RAISED kept every claim (`_terminal(None)` read
      "nobody targeted")                 -> None is never terminal; raises
                                            stand in `transport_failed`
  F2. growth counted `digest` on claim and a dry run skipped the state read
                                        -> counted on a terminal send; read always
  F3. sweep_read sliced the window AFTER appending today, dropping the
      oldest closed bar (a loosening)   -> closed window first, then today
  F4. overlap dedupe was read-then-claim: two cuts of one level in ONE pass,
      and two passes inside one minute -> one band per name per pass, and a
                                            post-claim re-read yields to the
                                            earlier claim — earlier by its
                                            WRITE stamp (claimed_at), never
                                            the pass-start `now`
  F5. Alerts.tsx typed "$1B+"           -> gate.min_cap_txt from the constant
  F6. 🚀 growth_demand_alert had become ARRIVAL-ONLY in this commit — a change
      to WHICH pushes fire the owner never asked for ("I wanna know when ever
      these are in demand")             -> in-band geometry, once per band per
                                            day; arrival-only is HIS call

Owner rules honoured: no new number anywhere (stale windows, gates and floors
are the existing constants). What reaches the phone changes ONLY by: the two
dedupe rules (one claim per key, one ring per overlapping level — now also
within a pass and across a same-minute race); the live-print / session-window
freshness rules; and F6, which puts the 🚀 growth kind back on the shipped
in-band read after 792cfe1 had narrowed it to arrivals. Every gate keeps its
constant; F3 closes a loosening rather than adding one.
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
    tape sat UNDER the band. Under the floor is not in the band (F6: the
    counter is `not_in_band` — the read is geometry, not arrival)."""
    out = GA.run(now=NOW, rows=[_grow_row()], snapshot={"HHH": _grow_snap(59.2, prev=61.5)}, coll=Coll())
    assert out["candidates"] == 0 and out["not_in_band"] == 1 and grow == []
    assert "no_arrival" not in out and "unknown_prev" not in out
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
    # F5: the page reads the cap floor off the payload, never types it
    assert p["gate"]["min_cap_usd"] == DA.MIN_CAP_USD == 700_000_000.0
    assert p["gate"]["min_cap_txt"] == AS.cap_floor_txt(DA.MIN_CAP_USD) == "$700M"
    assert p["gate"] == AS.gate_payload()


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
    # the demand side claims through settle_claims (claim + the post-claim
    # overlap re-read, F4b); a bare DA.claim( in the pass would skip that read
    assert "_claim_break(" in src and "DA.settle_claims(" in src and "DA.release_key(" in src
    assert "DA.claim(" not in src
    assert "DA.recorded_today(" in src and "DA.overlapping_key(" in src
    dsrc = inspect.getsource(DA._check_once)
    assert "_already(" not in dsrc and "settle_claims(" in dsrc and "release_key(" in dsrc
    assert "recorded_today(" in dsrc and "overlapping_key(" in dsrc
    ssrc = inspect.getsource(DA.settle_claims)
    assert "claim(" in ssrc and "recorded_today(" in ssrc and "release_key(" in ssrc


# ═════════════════════════════ 8. follow-up review of 792cfe1 (F1–F6)
def _raiser(monkeypatch):
    """A sender that RAISES on every call (APNs down), recording the attempts."""
    from push import sender
    calls = []

    def boom(owner, payload, kind=None):
        calls.append(payload)
        raise RuntimeError("apns down")
    monkeypatch.setattr(sender, "send_to_user", boom)
    return calls


def _many(n):
    """n names, every one a clean reversal at DEM with room to RES."""
    syms = [f"D{i}" for i in range(n)]
    store = {s: _doc(s, [DEM, RES], 95.0) for s in syms}
    snap = {s: _bounce(91.0 + i * 0.01, 95.0) for i, s in enumerate(syms)}
    return syms, store, snap, {s: 5e9 for s in syms}


def _board_of(syms, band=DEM):
    return {"rows": [{"symbol": s, "name": s, "entry_zone": dict(band)} for s in syms],
            "approaching_rows": []}


# ── F1: a raised digest send releases like a raised single ──────────────────
def test_F1_no_result_is_never_terminal_and_a_raise_stands_in_transport_failed():
    for mod in (DA, ZE, GA):
        assert mod._terminal(None) is False, mod.__name__
        assert mod._terminal("not a dict") is False
        assert mod._terminal(DA.transport_failed(RuntimeError("apns"))) is False
    tf = DA.transport_failed(RuntimeError("apns"))
    assert tf["sent"] == 0 and tf["failed"] == 1 and tf["total_targets"] == 1 and "apns" in tf["error"]
    # NEGATIVE: the sender's own "nobody targeted" (muted pref / no device) stays terminal
    assert DA._terminal({"sent": 0, "failed": 0, "total_targets": 0, "skipped": "muted"}) is True
    assert DA._terminal({"sent": 1, "failed": 1, "total_targets": 2}) is True
    assert DA._terminal({"sent": 0, "failed": 2, "total_targets": 2}) is False


def test_F1_zone_edge_a_digest_whose_send_raises_releases_every_claim(monkeypatch):
    n = ZE.MAX_SINGLES_PER_PASS + 3                     # 3 singles + 3 digest names
    syms, store, snap, caps = _many(n)
    calls = _raiser(monkeypatch)
    coll = Coll()
    out, _ = _ze(store, snap, caps, coll_demand=coll)
    assert len(calls) == ZE.MAX_SINGLES_PER_PASS + 1, "every single and the ONE digest were attempted"
    assert out["pushed"] == 0 and out["digest_demand"] == 3 and out["claimed_elsewhere"] == 0
    assert coll.docs == {}, "a digest claim survived the raise: those names would be muted for the day"
    # transport back next minute: every name rings — the singles and ONE digest naming the rest
    sent = _capture(monkeypatch)
    out2, _ = _ze(store, snap, caps, coll_demand=coll)
    assert out2["pushed"] == ZE.MAX_SINGLES_PER_PASS + 1 and out2["claimed_elsewhere"] == 0
    text = " ".join(m["title"] + " " + m["body"] for m in sent)
    assert all(s in text for s in syms) and len(coll.docs) == n


def test_F1_demand_alerts_a_digest_whose_send_raises_releases_every_claim(monkeypatch):
    n = DA.MAX_SINGLES_PER_PASS + 3                     # 4 singles + 3 digest names
    syms, store, snap, caps = _many(n)
    calls = _raiser(monkeypatch)
    coll = Coll()
    kw = dict(force=True, board=_board_of(syms), snapshot=snap, caps=caps, coll=coll,
              owner="o@x", now=NOW, store=store, pass_coll=Coll())
    out = DA.check_once(**kw)
    assert len(calls) == DA.MAX_SINGLES_PER_PASS + 1
    assert out["pushed"] == 0 and out["at"] == n and out["at_singles"] == DA.MAX_SINGLES_PER_PASS
    assert coll.docs == {}
    sent = _capture(monkeypatch)
    out2 = DA.check_once(**kw)
    assert out2["pushed"] == DA.MAX_SINGLES_PER_PASS + 1 and out2["claimed_elsewhere"] == 0
    text = " ".join(m["title"] + " " + m["body"] for m in sent)
    assert all(s in text for s in syms) and len(coll.docs) == n


def test_F1_growth_a_digest_whose_send_raises_releases_every_claim(grow, monkeypatch):
    n = GA.MAX_INDIVIDUAL + 3
    syms = [f"G{i}" for i in range(n)]
    rows = [dict(_grow_row(s), sales_growth_pct=100.0 - i) for i, s in enumerate(syms)]
    snap = {s: _grow_snap(61.55) for s in syms}
    calls = _raiser(monkeypatch)                        # overrides the fixture's working sender
    coll = Coll()
    out = GA.run(now=NOW, rows=rows, snapshot=snap, coll=coll)
    assert len(calls) == GA.MAX_INDIVIDUAL + 1
    assert out["fresh"] == n and out["individual"] == 0 and out["digest"] == 0
    assert coll.docs == {}
    sent = _capture(monkeypatch)
    out2 = GA.run(now=NOW, rows=rows, snapshot=snap, coll=coll)
    assert out2["fresh"] == n and out2["individual"] == GA.MAX_INDIVIDUAL and out2["digest"] == 3
    assert len(sent) == GA.MAX_INDIVIDUAL + 1 and len(coll.docs) == n
    assert all(s in sent[-1]["body"] for s in syms[GA.MAX_INDIVIDUAL:])


def test_F1_NEGATIVE_a_muted_digest_is_still_terminal_in_every_module(grow, monkeypatch):
    """The sender's own 'nobody targeted' is a fact, not a failure: the claims
    stay and the pass counts it — digest included, unchanged."""
    _capture(monkeypatch, result={"sent": 0, "failed": 0, "total_targets": 0, "skipped": "muted"})
    syms, store, snap, caps = _many(ZE.MAX_SINGLES_PER_PASS + 2)
    coll = Coll()
    out, _ = _ze(store, snap, caps, coll_demand=coll)
    assert out["pushed"] == ZE.MAX_SINGLES_PER_PASS + 1 and len(coll.docs) == len(syms)
    syms, store, snap, caps = _many(DA.MAX_SINGLES_PER_PASS + 2)
    coll = Coll()
    out = DA.check_once(force=True, board=_board_of(syms), snapshot=snap, caps=caps, coll=coll,
                        owner="o@x", now=NOW, store=store, pass_coll=Coll())
    assert out["pushed"] == DA.MAX_SINGLES_PER_PASS + 1 and len(coll.docs) == len(syms)
    gs = [f"G{i}" for i in range(GA.MAX_INDIVIDUAL + 2)]
    coll = Coll()
    out = GA.run(now=NOW, rows=[_grow_row(s) for s in gs], snapshot={s: _grow_snap(61.55) for s in gs}, coll=coll)
    assert out["individual"] == GA.MAX_INDIVIDUAL and out["digest"] == 2 and len(coll.docs) == len(gs)


# ── F2: growth's digest count and its dry run ───────────────────────────────
def test_F2_growth_counts_digest_names_only_on_a_terminal_send(grow, monkeypatch):
    gs = [f"G{i}" for i in range(GA.MAX_INDIVIDUAL + 2)]
    rows = [_grow_row(s) for s in gs]
    snap = {s: _grow_snap(61.55) for s in gs}
    # 0 of 1 devices reached: the two digest names are RELEASED and not counted
    _capture(monkeypatch, result={"sent": 0, "failed": 1, "total_targets": 1})
    coll = Coll()
    out = GA.run(now=NOW, rows=rows, snapshot=snap, coll=coll)
    assert out["fresh"] == len(gs) and out["individual"] == 0 and out["digest"] == 0 and coll.docs == {}
    # delivered: counted, claims kept
    _capture(monkeypatch)
    out = GA.run(now=NOW, rows=rows, snapshot=snap, coll=coll)
    assert out["individual"] == GA.MAX_INDIVIDUAL and out["digest"] == 2 and len(coll.docs) == len(gs)
    # NEGATIVE: names another pass claimed are neither sent nor counted as digest
    coll2 = Coll()
    stolen = GA._state_key(gs[-1], {"lo": 60.0, "hi": 62.0}, DAY)
    coll2.docs[stolen] = {"_id": stolen, "symbol": gs[-1], "source": "the-other-pass"}
    out = GA.run(now=NOW, rows=rows, snapshot=snap, coll=coll2)
    assert out["fresh"] == len(gs) - 1 and out["digest"] == 1 and out["claimed_elsewhere"] == 0


def test_F2_a_dry_run_reads_the_state_and_never_reports_a_rung_key_as_fresh(grow, monkeypatch):
    """`python -m growth alerts --dry-run` used to skip the state read (seen =
    set()) and report a key already rung today as fresh/individual."""
    coll = Coll()
    key = GA._state_key("HHH", {"lo": 60.0, "hi": 62.0}, DAY)
    coll.docs[key] = {"_id": key, "symbol": "HHH", "source": "growth_alerts"}
    kw = dict(now=NOW, rows=[_grow_row()], snapshot={"HHH": _grow_snap(61.55)})
    wet = GA.run(coll=coll, **kw)
    dry = GA.run(coll=coll, dry_run=True, **kw)
    assert wet["fresh"] == dry["fresh"] == 0 and dry["individual"] == 0 and dry["candidates"] == 1
    assert dry["dry_run"] is True and grow == [] and set(coll.docs) == {key}, "reads; writes and sends nothing"
    # the dry run RESOLVES the state coll itself when none is handed in — the read is unconditional
    reads = []

    class Resolved(Coll):
        def find(self, q, projection=None):
            reads.append(q)
            return iter(())
    monkeypatch.setattr(GA, "_state_coll", lambda: Resolved())
    dry2 = GA.run(dry_run=True, **kw)
    assert reads and reads[0]["_id"]["$in"] == [key]
    assert dry2["fresh"] == 1 and dry2["individual"] == 1, "a fresh key reports what a wet pass would send"
    assert grow == [], "and still sends nothing"


# ── F3: the closed window first, then the session bar ───────────────────────
def _sweep_at(df, bars_back):
    """Pierce the 100 floor by 1% on the bar `bars_back` from the END of the
    frame (1 = the last bar), reclaimed the same bar (closes stay at 105)."""
    df = df.copy()
    i = len(df) - bars_back
    df.iloc[i, df.columns.get_loc("low")] = 99.0
    df.iloc[i, df.columns.get_loc("volume")] = 5_000_000
    return df


def test_F3_a_sweep_exactly_SWEEP_WINDOW_BARS_closed_bars_back_still_reads_swept_with_todays_bar(real_sweep):
    """The old read sliced `df.iloc[-window:]` AFTER appending today, so on
    the append path the window was 14 closed bars + today and a floor swept
    exactly SWEEP_WINDOW_BARS closed bars back fell out: 'intact', gate True,
    where the pre-session-bar read said 'swept', gate False. A loosening.
    Now the closed window is cut first and today is added to it."""
    W = AG.SWEEP_WINDOW_BARS
    df = _sweep_at(_frame(n=30), W)                     # frame ends Fri 09-11; sweep W closed bars back
    assert AG.sweep_read(BAND, "X", frame=df, day=TODAY)["state"] == "swept", "the pre-2026-09-14 read"
    assert AG.floor_held_gate(BAND, "X", frame=df, day=TODAY) is False
    # append path with a benign day low: the SAME answer — the gate did not open
    r = AG.sweep_read(BAND, "X", frame=df, day_low=104.0, last=105.0, day=TODAY)
    assert r["state"] == "swept" and r["sweep_low"] == 99.0
    assert AG.floor_held_gate(BAND, "X", frame=df, day_low=104.0, last=105.0, day=TODAY) is False
    # NEGATIVE: one bar OLDER than the window is not "now" on either path (nothing widened)
    older = _sweep_at(_frame(n=30), W + 1)
    assert AG.sweep_read(BAND, "X", frame=older, day=TODAY)["state"] == "intact"
    assert AG.sweep_read(BAND, "X", frame=older, day_low=104.0, last=105.0, day=TODAY)["state"] == "intact"
    assert AG.floor_held_gate(BAND, "X", frame=older, day_low=104.0, last=105.0, day=TODAY) is True
    # and today's OWN pierce still counts on top of the closed window (finding 4 kept)
    r2 = AG.sweep_read(BAND, "X", frame=older, day_low=99.0, last=103.0, day=TODAY)
    assert r2["state"] == "swept" and r2["vol_x"] is None
    # merge path (the frame already holds today from the hourly patch): window rows, unchanged
    today_frame = _sweep_at(_frame(n=30, start="2026-08-04"), W)
    assert pd.Timestamp(today_frame.index[-1]).date() == TODAY
    assert AG.sweep_read(BAND, "X", frame=today_frame, day=TODAY)["state"] == "swept"
    assert AG.sweep_read(BAND, "X", frame=today_frame, day_low=104.0, last=105.0, day=TODAY)["state"] == "swept"


def test_F3_NEGATIVE_the_window_is_the_closed_bars_plus_today_never_fewer_closed_bars(real_sweep, monkeypatch):
    """Pin the shape find_sweep receives: append path window+1 rows (W closed
    + today), merge path window rows, no session bar → window rows."""
    from supply_demand import sd_liquidity as liq
    seen = []
    real = liq.find_sweep

    def spy(bars, lo, hi, **kw):
        seen.append(len(bars))
        return real(bars, lo, hi, **kw)
    monkeypatch.setattr(liq, "find_sweep", spy)
    W = AG.SWEEP_WINDOW_BARS
    AG.sweep_read(BAND, "X", frame=_frame(n=30), day=TODAY)
    AG.sweep_read(BAND, "X", frame=_frame(n=30), day_low=104.0, last=105.0, day=TODAY)
    AG.sweep_read(BAND, "X", frame=_frame(n=30, start="2026-08-04"), day_low=104.0, last=105.0, day=TODAY)
    assert seen == [W, W + 1, W]


# ── F4: one level rings once — within a pass, and across a same-minute race ─
DEM_OVER = {"kind": "demand", "lo": 88.0, "hi": 90.8, "touches": 2, "strength": 40.0}   # overlaps DEM 90-92
DEM_LOW = {"kind": "demand", "lo": 80.0, "hi": 82.0, "touches": 3, "strength": 45.0}    # does NOT overlap


def test_F4a_demand_alerts_reads_ONE_band_per_name_per_pass_the_containing_one(monkeypatch):
    """The board carried AAA on the reentry list with 90-92 and on the
    approaching list with an overlapping 88-90.8 (candidates() dedupes only an
    exact lo/hi pair): two 🧲 for one level, two stops, in ONE pass."""
    sent = _capture(monkeypatch)
    board = {"rows": [{"symbol": "AAA", "name": "AAA Inc", "entry_zone": dict(DEM)}],
             "approaching_rows": [{"symbol": "AAA", "name": "AAA Inc", "approaching": {"band": dict(DEM_OVER)}}]}
    store = {"AAA": _doc("AAA", [DEM, DEM_OVER, RES], 95.0)}
    coll = Coll()
    out = DA.check_once(force=True, board=board, snapshot={"AAA": _bounce(91.0, 95.0)},
                        caps={"AAA": 5e9}, coll=coll, owner="o@x", now=NOW, store=store)
    assert out["pushed"] == 1 and len(sent) == 1 and out["at"] == 1 and len(out["hits"]) == 1
    assert sent[0]["title"].endswith("$90–92"), "the band CONTAINING the print, not the one it sits above"
    assert set(coll.docs) == {DA.state_key("AAA", DEM, DAY, "at")}
    # two containing bands: the higher top wins (read_near_demand's rule) — deterministic
    wide = {"kind": "demand", "lo": 89.0, "hi": 93.0, "touches": 2, "strength": 40.0}
    board2 = {"rows": [{"symbol": "AAA", "name": "AAA Inc", "entry_zone": dict(DEM)}],
              "approaching_rows": [{"symbol": "AAA", "name": "AAA Inc", "approaching": {"band": dict(wide)}}]}
    sent.clear()
    out2 = DA.check_once(force=True, board=board2, snapshot={"AAA": _bounce(91.0, 95.0)},
                         caps={"AAA": 5e9}, coll=Coll(), owner="o@x", now=NOW,
                         store={"AAA": _doc("AAA", [DEM, wide, RES], 95.0)})
    assert out2["pushed"] == 1 and len(sent) == 1 and sent[0]["title"].endswith("$89–93")


def test_F4a_zone_edge_reads_ONE_band_per_name_per_pass(monkeypatch):
    sent = _capture(monkeypatch)
    coll = Coll()
    out, _ = _ze({"AAA": _doc("AAA", [DEM, DEM_OVER, RES], 95.0)}, {"AAA": _bounce(91.0, 95.0)},
                 {"AAA": 5e9}, coll_demand=coll)
    assert out["pushed"] == 1 and len(sent) == 1 and sent[0]["title"].endswith("$90–92")
    assert set(coll.docs) == {DA.state_key("AAA", DEM, DAY, "at")} and out["skipped_overlap"] == 0
    assert len(out["near_demand"]) == 1, "one row per name on the board too"


def test_F4a_NEGATIVE_two_NON_overlapping_bands_on_one_name_both_ring_in_both_modules(monkeypatch):
    """The rule is one ring per LEVEL: a name that reverses off 90-92 in the
    morning and, having fallen through it, reverses off 80-82 in the afternoon
    rings twice — once per band — from either module."""
    sent = _capture(monkeypatch)
    store = {"AAA": _doc("AAA", [DEM, DEM_LOW, RES], 95.0)}
    later = NOW + timedelta(hours=2)
    # zone_edge
    coll = Coll()
    out1, _ = _ze(store, {"AAA": _bounce(91.0, 95.0)}, {"AAA": 5e9}, coll_demand=coll)
    out2, _ = _ze(store, {"AAA": _bounce(81.0, 95.0, now=later)}, {"AAA": 5e9}, coll_demand=coll, now=later)
    assert out1["pushed"] == 1 and out2["pushed"] == 1 and out2["skipped_overlap"] == 0
    assert [m["title"][-6:] for m in sent] == ["$90–92", "$80–82"]
    # demand_alerts
    sent.clear()
    coll = Coll()
    kw = dict(force=True, caps={"AAA": 5e9}, coll=coll, owner="o@x", store=store)
    o1 = DA.check_once(board=_board("AAA", DEM), snapshot={"AAA": _bounce(91.0, 95.0)}, now=NOW, **kw)
    o2 = DA.check_once(board=_board("AAA", DEM_LOW), snapshot={"AAA": _bounce(81.0, 95.0, now=later)},
                       now=later, **kw)
    assert o1["pushed"] == 1 and o2["pushed"] == 1 and o2["skipped_overlap"] == 0 and len(coll.docs) == 2
    assert [m["title"][-6:] for m in sent] == ["$90–92", "$80–82"]


def test_F4b_claim_precedes_orders_by_stamp_then_key_and_treats_unstamped_as_older():
    t0, t1 = NOW.isoformat(), (NOW + timedelta(seconds=1)).isoformat()
    assert DA.claim_precedes(t0, "A", t1, "B") is True
    assert DA.claim_precedes(t1, "A", t0, "B") is False
    assert DA.claim_precedes(None, "A", t0, "B") is True, "an unstamped doc was there before ours"
    assert DA.claim_precedes(t0, "A", None, "B") is False
    # the tie: the smaller key wins, and the two views never BOTH yield
    assert DA.claim_precedes(t0, "A", t0, "B") is True and DA.claim_precedes(t0, "B", t0, "A") is False
    assert DA.claim_precedes(t0, "K", t0, "K") is False, "never yields to itself"
    assert DA.claim_precedes("garbage", "A", "zzz", "B") is True and DA.claim_precedes("zzz", "A", "garbage", "B") is False


class ReadBeforeTheirClaim(Coll):
    """The exact same-minute interleaving of F4b: this pass's dedupe read
    happened BEFORE the other pass's claim landed (the first `find` sees
    nothing), then both claims succeed. Only the post-claim re-read (the
    second `find`) can see the other claim."""

    def __init__(self, shared: Coll):
        super().__init__()
        self.shared, self.reads = shared, 0
        self.docs = shared.docs                          # one store, two views

    def find(self, q, projection=None):
        self.reads += 1
        self.calls.append("find")
        if self.reads == 1:
            return iter(())
        return super().find(q, projection)


def test_F4b_demand_alerts_yields_to_an_overlapping_claim_zone_edge_made_first(monkeypatch):
    sent = _capture(monkeypatch)
    shared = Coll()
    store = {"AAA": _doc("AAA", [DEM, RES], 95.0)}
    # zone_edge rang the store's cut of the level at NOW
    ZE.check_once(push=True, force=True, track=False, store=store, snapshot={"AAA": _bounce(91.0, 95.0)},
                  caps={"AAA": 5e9}, names={}, owner="o@x", now=NOW,
                  coll_break=Coll(), coll_demand=shared, latest_coll=Coll(), track_coll=Coll())
    assert len(sent) == 1
    ze_key = DA.state_key("AAA", DEM, DAY, "at")
    # demand_alerts had read "nothing recorded" a moment earlier; its board cut overlaps
    later = NOW + timedelta(seconds=5)
    view = ReadBeforeTheirClaim(shared)
    out = DA.check_once(force=True, board=_board("AAA", DEM_OVER), snapshot={"AAA": _bounce(91.0, 95.0, now=later)},
                        caps={"AAA": 5e9}, coll=view, owner="o@x", now=later,
                        store={"AAA": _doc("AAA", [DEM, DEM_OVER, RES], 95.0)})
    assert len(sent) == 1, "the same level rang from both modules inside one minute under two keys"
    assert out["pushed"] == 0 and out["skipped_overlap"] == 1 and out["claimed_elsewhere"] == 0
    assert set(shared.docs) == {ze_key}, "the later claim is RELEASED, never left to mute the name"
    assert view.reads == 2, "one pre-pass read, one post-claim re-read — never per name"


def test_F4b_zone_edge_yields_to_an_overlapping_claim_demand_alerts_made_first(monkeypatch):
    sent = _capture(monkeypatch)
    shared = Coll()
    DA.check_once(force=True, board=_board("AAA", DEM_OVER), snapshot={"AAA": _bounce(91.0, 95.0)},
                  caps={"AAA": 5e9}, coll=shared, owner="o@x", now=NOW,
                  store={"AAA": _doc("AAA", [DEM, DEM_OVER, RES], 95.0)})
    assert len(sent) == 1
    da_key = DA.state_key("AAA", DEM_OVER, DAY, "at")
    later = NOW + timedelta(seconds=5)
    view = ReadBeforeTheirClaim(shared)
    out, _ = _ze({"AAA": _doc("AAA", [DEM, RES], 95.0)}, {"AAA": _bounce(91.0, 95.0, now=later)}, {"AAA": 5e9},
                 coll_demand=view, now=later)
    assert len(sent) == 1 and out["pushed"] == 0 and out["skipped_overlap"] == 1
    assert out["payload"]["counts"]["skipped_overlap"] == 1, "the /alerts page can explain it"
    assert set(shared.docs) == {da_key} and view.reads == 2


def test_F4b_NEGATIVE_the_EARLIER_claim_keeps_ringing_and_a_tie_never_silences_the_level(monkeypatch):
    """The pass whose claim came first keeps it even when the re-read shows
    the other's — the other yields. And two claims with the SAME stamp resolve
    by key, so exactly one rings. The write clock is frozen at NOW so the
    seeded stamps mean what they say; the seeded docs carry NO `claimed_at`
    (pre-stamp shape) and order by `sent_at`."""
    sent = _capture(monkeypatch)
    monkeypatch.setattr(DA, "write_clock", lambda: NOW)
    shared = Coll()
    store = {"AAA": _doc("AAA", [DEM, DEM_OVER, RES], 95.0)}
    # the other pass's claim is LATER than ours: we keep, we ring
    later_key = DA.state_key("AAA", DEM_OVER, DAY, "at")
    shared.docs[later_key] = {"_id": later_key, "symbol": "AAA", "band": {"lo": 88.0, "hi": 90.8},
                              "sent_at": (NOW + timedelta(seconds=30)).isoformat(), "source": "demand_alerts"}
    view = ReadBeforeTheirClaim(shared)
    out, _ = _ze({"AAA": _doc("AAA", [DEM, RES], 95.0)}, {"AAA": _bounce(91.0, 95.0)}, {"AAA": 5e9},
                 coll_demand=view, now=NOW)
    assert out["pushed"] == 1 and len(sent) == 1 and out["skipped_overlap"] == 0
    assert DA.state_key("AAA", DEM, DAY, "at") in shared.docs
    # the tie: both stamped NOW; the smaller key wins on both views
    sent.clear()
    a = Coll()
    ka = DA.state_key("AAA", DEM, DAY, "at")            # "AAA:90.00-92.00…" > "AAA:88.00-90.80…"
    kb = DA.state_key("AAA", DEM_OVER, DAY, "at")
    a.docs[kb] = {"_id": kb, "symbol": "AAA", "band": {"lo": 88.0, "hi": 90.8}, "sent_at": NOW.isoformat()}
    out_a, _ = _ze({"AAA": _doc("AAA", [DEM, RES], 95.0)}, {"AAA": _bounce(91.0, 95.0)}, {"AAA": 5e9},
                   coll_demand=ReadBeforeTheirClaim(a), now=NOW)
    assert out_a["pushed"] == 0 and out_a["skipped_overlap"] == 1 and ka not in a.docs, "the larger key yields"
    b = Coll()
    b.docs[ka] = {"_id": ka, "symbol": "AAA", "band": {"lo": 90.0, "hi": 92.0}, "sent_at": NOW.isoformat()}
    out_b = DA.check_once(force=True, board=_board("AAA", DEM_OVER), snapshot={"AAA": _bounce(91.0, 95.0)},
                          caps={"AAA": 5e9}, coll=ReadBeforeTheirClaim(b), owner="o@x", now=NOW, store=store)
    assert out_b["pushed"] == 1 and out_b["skipped_overlap"] == 0 and kb in b.docs, "the smaller key keeps ringing"
    assert len(sent) == 1


def test_F4b_NEGATIVE_a_failed_re_read_keeps_the_claim_and_rings(monkeypatch):
    """Push again rather than never: if the post-claim re-read fails, nothing
    is yielded."""
    sent = _capture(monkeypatch)

    class FlakyReread(Coll):
        def __init__(self):
            super().__init__()
            self.reads = 0

        def find(self, q, projection=None):
            self.reads += 1
            if self.reads == 2:
                raise RuntimeError("mongo hiccup")
            return super().find(q, projection)
    coll = FlakyReread()
    out, _ = _ze({"AAA": _doc("AAA", [DEM, RES], 95.0)}, {"AAA": _bounce(91.0, 95.0)}, {"AAA": 5e9},
                 coll_demand=coll)
    assert out["pushed"] == 1 and len(sent) == 1 and coll.reads == 2 and len(coll.docs) == 1


def test_F4b_settle_claims_is_one_claim_per_item_and_one_re_read_for_the_batch():
    coll = Coll()
    items = [{"symbol": s, "key": DA.state_key(s, DEM, DAY, "at"), "band": dict(DEM), "last": 91.0,
              "hit": {"tier": "at", "dist_pct": 0.0}} for s in ("A", "B", "C")]
    ours, elsewhere, lost = DA.settle_claims(coll, items, NOW, DAY)
    assert [it["symbol"] for it in ours] == ["A", "B", "C"] and (elsewhere, lost) == (0, 0)
    assert coll.calls.count("update_one") == 3 and coll.calls.count("find") == 1
    assert all(coll.docs[it["key"]]["source"] == "demand_alerts" for it in items)
    # a second settle on the same keys: every one claimed elsewhere, no re-read needed
    ours2, elsewhere2, lost2 = DA.settle_claims(coll, items, NOW, DAY, source="zone_edge")
    assert ours2 == [] and elsewhere2 == 3 and lost2 == 0 and coll.calls.count("find") == 1
    assert DA.settle_claims(None, items, NOW, DAY) == (items, 0, 0), "no coll: ours to send, no read"
    assert DA.settle_claims(coll, [], NOW, DAY) == ([], 0, 0)


# ── F4b residual: the ordering stamp is the WRITE clock, never the pass `now` ──
def _tick(monkeypatch, start=NOW, step=1):
    """A write clock that advances `step` seconds per claim — a deterministic
    write ORDER independent of what `now` each pass was handed."""
    n = {"i": 0}

    def clock():
        n["i"] += 1
        return start + timedelta(seconds=step * n["i"])
    monkeypatch.setattr(DA, "write_clock", clock)
    return n


def _item(sym, band, tier="at"):
    return {"symbol": sym, "key": DA.state_key(sym, band, DAY, tier), "band": dict(band), "last": 91.0,
            "hit": {"tier": tier, "dist_pct": 0.0}}


def test_F4b_claim_key_stamps_claimed_at_at_the_upsert_and_recorded_today_surfaces_it(monkeypatch):
    """`sent_at` / `at` stay the pass clock (display); `claimed_at` is the
    write clock at the moment of the upsert, injectable, and the stamp
    recorded_today hands settle_claims — falling back to sent_at, then at,
    for docs that predate it."""
    w = NOW + timedelta(seconds=42)
    monkeypatch.setattr(DA, "write_clock", lambda: w)
    c = Coll()
    it = _item("AAA", DEM)
    assert DA.claim(c, it["key"], it, NOW) is True
    assert c.docs[it["key"]]["sent_at"] == NOW.isoformat(), "the pass clock stays, for display"
    assert c.docs[it["key"]]["claimed_at"] == w.isoformat(), "the ordering stamp is the write clock"
    assert DA.recorded_today(c, ["AAA"], DAY)["AAA"][0]["at"] == w.isoformat()
    # zone_edge's break doc and growth's docs go through the same claim_key
    b = Coll()
    ZE._claim_break(b, {"symbol": "AAA", "key": "AAA:supply:100.00-102.00:" + DAY, "tier": "at",
                        "band": dict(RES), "last": 101.0, "dist_pct": 0.5, "new_highs": 1, "cap": 5e9}, NOW)
    assert b.docs["AAA:supply:100.00-102.00:" + DAY]["claimed_at"] == w.isoformat()
    assert b.docs["AAA:supply:100.00-102.00:" + DAY]["sent_at"] == NOW.isoformat()
    # injectable: the kwarg wins over the clock
    inj = NOW + timedelta(seconds=7)
    c2 = Coll()
    assert DA.claim_key(c2, "K", {"symbol": "AAA"}, claimed_at=inj) is True
    assert c2.docs["K"]["claimed_at"] == inj.isoformat()
    assert DA.claim_key(c2, "K", {"symbol": "AAA"}, claimed_at=NOW) is False, "a claim never restamps"
    assert c2.docs["K"]["claimed_at"] == inj.isoformat()
    # NEGATIVE: pre-stamp docs order by sent_at, then at; an unstamped doc reads None (= older)
    c3 = Coll()
    k1, k2, k3 = DA.state_key("AAA", DEM, DAY, "at"), DA.state_key("AAA", DEM_OVER, DAY, "at"), \
        DA.state_key("AAA", SHELF, DAY, "at")
    c3.docs[k1] = {"_id": k1, "symbol": "AAA", "band": dict(DEM), "sent_at": NOW.isoformat()}
    c3.docs[k2] = {"_id": k2, "symbol": "AAA", "band": dict(DEM_OVER), "at": inj.isoformat()}
    c3.docs[k3] = {"_id": k3, "symbol": "AAA", "band": dict(SHELF)}
    rec = {r["key"]: r["at"] for r in DA.recorded_today(c3, ["AAA"], DAY)["AAA"]}
    assert rec == {k1: NOW.isoformat(), k2: inj.isoformat(), k3: None}
    # and settle_claims never orders by the pass clock
    import inspect
    src = inspect.getsource(DA.settle_claims)
    assert "now.isoformat()" not in src and "write_clock()" in src and "claimed_at=" in src


def test_F4b_settle_claims_orders_by_each_claims_OWN_write_stamp_not_the_pass_now(monkeypatch):
    """The exact residual: our pass STARTED earlier (`now` = t1) than the
    other's claim (t1+5s) but WROTE later (t1+10s) — we yield. Ordered by
    `now` we would have kept and the level would ring twice. NEGATIVE: started
    later, wrote earlier — we keep."""
    t1 = NOW
    other_at = (t1 + timedelta(seconds=5)).isoformat()
    other_key = DA.state_key("AAA", DEM_OVER, DAY, "at")

    def coll_with_other():
        c = Coll()
        c.docs[other_key] = {"_id": other_key, "symbol": "AAA", "band": dict(DEM_OVER),
                             "sent_at": t1.isoformat(), "claimed_at": other_at, "source": "zone_edge"}
        return c
    monkeypatch.setattr(DA, "write_clock", lambda: t1 + timedelta(seconds=10))
    c = coll_with_other()
    ours, elsewhere, lost = DA.settle_claims(c, [_item("AAA", DEM)], t1, DAY)
    assert (ours, elsewhere, lost) == ([], 0, 1), "started earlier, claimed second: yield"
    assert set(c.docs) == {other_key}, "the yielded claim is released"
    # NEGATIVE: started later (now = t1+20s) but WROTE earlier (t1+1s): keep
    monkeypatch.setattr(DA, "write_clock", lambda: t1 + timedelta(seconds=1))
    c = coll_with_other()
    ours, elsewhere, lost = DA.settle_claims(c, [_item("AAA", DEM)], t1 + timedelta(seconds=20), DAY)
    assert len(ours) == 1 and (elsewhere, lost) == (0, 0)
    assert c.docs[ours[0]["key"]]["sent_at"] == (t1 + timedelta(seconds=20)).isoformat()
    # injected stamp: the kwarg is the ordering stamp
    c = coll_with_other()
    ours, _, lost = DA.settle_claims(c, [_item("AAA", DEM)], t1, DAY, claimed_at=t1 + timedelta(seconds=30))
    assert ours == [] and lost == 1
    # NEGATIVE: a non-overlapping band never yields whatever the stamps say
    c = coll_with_other()
    far = {"kind": "demand", "lo": 70.0, "hi": 72.0, "touches": 2, "strength": 40.0}
    ours, _, lost = DA.settle_claims(c, [_item("AAA", far)], t1, DAY)
    assert len(ours) == 1 and lost == 0


def _da_over(coll, now, sent):
    return DA.check_once(force=True, board=_board("AAA", DEM_OVER), snapshot={"AAA": _bounce(91.0, 95.0, now=now)},
                         caps={"AAA": 5e9}, coll=coll, owner="o@x", now=now,
                         store={"AAA": _doc("AAA", [DEM, DEM_OVER, RES], 95.0)})


def test_F4b_the_earlier_started_pass_that_claims_SECOND_yields__zone_edge_started_first(monkeypatch):
    """The verifier's probe: zone_edge's pass began at t1, demand_alerts' at
    t1+5s — but demand_alerts reached its claim + re-read first (zone_edge was
    still on its snapshot / gates; cron aligns both to the same minute).
    Ordered by the pass clock zone_edge KEPT (its `now` was earlier): two
    rings. Ordered by the write clock it yields: one ring, its claim released."""
    sent = _capture(monkeypatch)
    ticks = _tick(monkeypatch, NOW + timedelta(seconds=10))
    shared = Coll()
    t1, t2 = NOW, NOW + timedelta(seconds=5)
    out_da = _da_over(ReadBeforeTheirClaim(shared), t2, sent)            # started t2, claimed FIRST
    assert out_da["pushed"] == 1 and len(sent) == 1
    out_ze, _ = _ze({"AAA": _doc("AAA", [DEM, RES], 95.0)}, {"AAA": _bounce(91.0, 95.0)}, {"AAA": 5e9},
                    coll_demand=ReadBeforeTheirClaim(shared), now=t1)       # started t1, claimed SECOND
    assert len(sent) == 1, "the earlier-STARTED pass claimed second and must yield"
    assert out_ze["pushed"] == 0 and out_ze["skipped_overlap"] == 1 and out_ze["claimed_elsewhere"] == 0
    da_key = DA.state_key("AAA", DEM_OVER, DAY, "at")
    assert set(shared.docs) == {da_key}, "zone_edge's claim is released, never left to mute the name"
    assert shared.docs[da_key]["sent_at"] == t2.isoformat(), "display keeps the pass clock"
    assert shared.docs[da_key]["claimed_at"] == (NOW + timedelta(seconds=11)).isoformat() and ticks["i"] == 2


def test_F4b_the_earlier_started_pass_that_claims_SECOND_yields__demand_alerts_started_first(monkeypatch):
    """The mirror: demand_alerts began at t1, zone_edge at t1+5s, zone_edge
    claimed first. demand_alerts yields; exactly one ring."""
    sent = _capture(monkeypatch)
    _tick(monkeypatch, NOW + timedelta(seconds=10))
    shared = Coll()
    t1, t2 = NOW, NOW + timedelta(seconds=5)
    out_ze, _ = _ze({"AAA": _doc("AAA", [DEM, RES], 95.0)}, {"AAA": _bounce(91.0, 95.0, now=t2)}, {"AAA": 5e9},
                    coll_demand=ReadBeforeTheirClaim(shared), now=t2)       # started t2, claimed FIRST
    assert out_ze["pushed"] == 1 and len(sent) == 1
    out_da = _da_over(ReadBeforeTheirClaim(shared), t1, sent)            # started t1, claimed SECOND
    assert len(sent) == 1
    assert out_da["pushed"] == 0 and out_da["skipped_overlap"] == 1 and out_da["claimed_elsewhere"] == 0
    assert set(shared.docs) == {DA.state_key("AAA", DEM, DAY, "at")}
    # NEGATIVE (the control): when write order matches start order nothing changes — one ring
    sent.clear()
    _tick(monkeypatch, NOW + timedelta(seconds=10))
    shared = Coll()
    _ze({"AAA": _doc("AAA", [DEM, RES], 95.0)}, {"AAA": _bounce(91.0, 95.0)}, {"AAA": 5e9},
        coll_demand=ReadBeforeTheirClaim(shared), now=t1)
    out = _da_over(ReadBeforeTheirClaim(shared), t2, sent)
    assert len(sent) == 1 and out["skipped_overlap"] == 1
    assert set(shared.docs) == {DA.state_key("AAA", DEM, DAY, "at")}


# ── F6: the 🚀 growth kind is in-band geometry, not arrival-only ─────────────
def test_F6_residence_rings_once_per_band_per_day_and_an_unknown_prior_close_still_rings(grow):
    """Ajay 2026-09-11: "I wanna know when ever these are in demand". A name
    that closed yesterday INSIDE its band and still sits there rings — once;
    the claim is the repeat guard. No prior close silences nothing."""
    coll = Coll()
    resident = {"HHH": _grow_snap(61.55, prev=61.0)}          # yesterday closed in 60-62
    out = GA.run(now=NOW, rows=[_grow_row()], snapshot=resident, coll=coll)
    assert out["candidates"] == 1 and out["individual"] == 1 and len(grow) == 1
    assert grow[0]["body"].startswith("$61.55 · in demand $60–62")
    later = NOW + timedelta(minutes=15)                     # a FRESH print 15 min on, still resident
    out2 = GA.run(now=later, rows=[_grow_row()], snapshot={"HHH": _grow_snap(61.55, prev=61.0, now=later)},
                  coll=coll)
    assert out2["candidates"] == 1 and out2["fresh"] == 0 and out2["individual"] == 0 and len(grow) == 1, \
        "once per (symbol, band, day)"
    unknown = {"HHH": _grow_snap(61.55, prev=None)}
    out3 = GA.run(now=NOW, rows=[_grow_row()], snapshot=unknown, coll=Coll())
    assert out3["candidates"] == 1 and out3["individual"] == 1 and len(grow) == 2
    assert "unknown_prev" not in out3 and "no_arrival" not in out3
    items, counts = GA._scan([_grow_row()], unknown, NOW)
    assert len(items) == 1 and items[0]["prev_close"] is None and counts["not_in_band"] == 0


def test_F6_NEGATIVE_the_growth_gates_are_untouched_by_the_geometry_read(grow, monkeypatch):
    """Under the floor is still not in the band; > 1% above the top still fails
    proximity; a pierced floor still fails; room still gates."""
    items, counts = GA._scan([_grow_row()], {"HHH": _grow_snap(59.2, prev=61.0)}, NOW)
    assert items == [] and counts["not_in_band"] == 1
    # 1.6% above the top and falling: the NEAR tier reads it (it is a level
    # in sight) and the <=1% proximity gate refuses it — unchanged
    items, counts = GA._scan([_grow_row()], {"HHH": _grow_snap(63.0, prev=64.0)}, NOW)
    assert items == [] and counts["skipped_proximity"] == 1
    # 1.6% above and RISING is departing, not at the level: nothing read at all
    items, counts = GA._scan([_grow_row()], {"HHH": _grow_snap(63.0, prev=61.0)}, NOW)
    assert items == [] and counts["not_in_band"] == 1
    monkeypatch.setattr(GA.AG, "sweep_read", lambda *a, **k: {"state": "swept"})
    items, counts = GA._scan([_grow_row()], {"HHH": _grow_snap(61.55, prev=61.0)}, NOW)
    assert items == [] and counts["skipped_floor"] == 1
    monkeypatch.setattr(GA.AG, "sweep_read", lambda *a, **k: {"state": "intact"})
    monkeypatch.setattr(GA, "_bands_for", lambda s: [{"kind": "demand", "lo": 60.0, "hi": 62.0, "touches": 3},
                                                     {"kind": "supply", "lo": 62.5, "hi": 63.0, "touches": 2}])
    items, counts = GA._scan([_grow_row()], {"HHH": _grow_snap(61.55, prev=61.0)}, NOW)
    assert items == [] and counts["skipped_room"] == 1
    # and the 🧲 pass (demand_alerts) is STILL arrivals-only — F6 is about the 🚀 kind alone
    assert DA.read(91.0, DEM, -3.0, 91.5) is None and DA.read(91.0, DEM, -3.0, None)["tier"] == "at"


def test_F6_source_guard_the_growth_read_passes_no_prior_close_and_the_docs_say_so():
    import inspect
    src = inspect.getsource(GA._scan)
    assert "prev_close=None" in src and "no_arrival" not in src and "unknown_prev" not in src
    doc = GA.__doc__
    assert "in the band" in doc and "NOT arrival-only" in doc and "owner's call" in doc
    root = Path(__file__).resolve().parents[2]
    md = root / "docs/growth/explosive_growth.md"
    if md.exists():
        text = md.read_text()
        assert "in the band or ≤ 1% above" in text and "once per (symbol, band, day)" in text
    ts = root / "frontend/src/lib/newFeatures.ts"
    if ts.exists():
        text = ts.read_text()
        assert "the same in-band geometry the \\ud83e\\uddf2 pushes use (in the band or \\u22641% above), " \
               "once per band per day, inside the session window" in text
        assert "the arrival rule and the session window the" not in text
