"""👀 Gajjala's Watch — 🤖 the auto section's engine and its loop wiring (spec ggwauto 2026-11-17 §3.1–§3.3, §3.7, WP-A).

Ajay 2026-11-17, verbatim: "Can you add more stocks in to watch list basically I need portentials from Gajjals's 1 min
and regular and also Audited potentials with good volume to Watchlist on an interval.. Remove as they are not
progressing"

Pins: adds = the boards' 🧠 potentials with today's volume ≥ GG's K11 floor (scan row, else GG5's tracker number [C2]),
tagged by source (🧪 borrows GG5's), in potential.order_key order within a minute's batch and frozen after [C4], capped,
never displacing; removals = ↩️ / ✖️ on every board at once with the card's line, ⏸ KEEPS [C1], "dropped" only after
the grace [C3]; an empty listed set hides nothing and never says "gone" [C5]; his list is never written; faults keep;
dismiss resets a stale doc [C7] and ignores a non-ticker without a read [C8]; the loop hands the cross push his names
only and holds the auto names' own-minute crosses [C6]. NEGATIVES are the point.
"""
from __future__ import annotations

import ast
import copy
import inspect
import re
from datetime import date, datetime, timedelta, timezone

import pytest

from chart_maps.gajjala import breakout_state as BS
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import scanner as SC
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import variant as V
from chart_maps.gajjala_watch import auto as A
from chart_maps.gajjala_watch import build as BLD
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import cross_alerts as XA
from chart_maps.gajjala_watch import loop as L
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_watch_build_2026_11_15 import PREV, S, at
from tests.test_gajjala_watch_cross_2026_11_15 import frames_stub, up_at

ISO = S.isoformat()
T0 = at(S, 10, 1, 30)
SUNDAY = date(2026, 11, 15)


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


# ── builders ─────────────────────────────────────────────────────────────────────────────────────────────────────
def utc(t):
    return t.astimezone(timezone.utc)


def pot(setup="bull_flag", ready=True, **kw):
    r = {"setup": setup, "state": GC.POTENTIAL_STATE, "ready": ready, "base": {"bars": 2}, "variant": None,
         "grade": None, "broke": False}
    r.update(kw)
    return r


def flat(setup="bull_flag", state="partial"):
    return {"setup": setup, "state": state, "ready": False, "base": {"bars": 2}, "broke": False}


def bars5(rows, d=S, t0=(10, 0)):
    """rows = [(h, l, c, v)] oldest first, one 5-minute bar each from t0 (stamps "YYYY-MM-DD HH:MM")."""
    out = []
    for i, (h, lo, c, v) in enumerate(rows):
        mm = t0[0] * 60 + t0[1] + 5 * i
        out.append({"t": f"{d.isoformat()} {mm // 60:02d}:{mm % 60:02d}", "o": lo, "h": h, "l": lo, "c": c, "v": v})
    return out


def broke(setup="bull_flag", entry_i=0, b=None, trigger=1.00, stop=0.90):
    from chart_maps.gajjala import detectors as D
    return {"setup": setup, "state": "triggered", "broke": True, "trigger": trigger, "stop": stop, "frame": "5m",
            "entry_bar_t": b[entry_i]["t"] if b else None, "as_of_bar_t": None, "ready": False, "variant": None,
            "grade": None, "base": None,
            "criteria": [{"key": D.K3_VOL_KEY, "label": "K3", "ok": True, "value": "busiest bar 200,000", "need": ""}]}


BACK_UNDER = bars5([(1.10, 0.99, 1.05, 300_000), (1.05, 0.95, 0.97, 90_000)])
STOP_PRINTED = bars5([(1.10, 0.99, 1.05, 300_000), (1.05, 0.85, 0.88, 90_000)])
WAITING = bars5([(1.10, 0.99, 1.05, 300_000), (1.08, 1.04, 1.06, 90_000), (1.09, 1.05, 1.07, 80_000)])
CONSOLIDATION = bars5([(1.10, 0.99, 1.05, 300_000)] + [(1.09, 1.02, 1.03 + (i % 4) / 100, 50_000) for i in range(12)])
QUIET = bars5([(1.10, 0.99, 1.05, 300_000), (1.08, 1.04, 1.06, 90_000), (1.20, 1.07, 1.15, 100_000)])


def rdoc(sym, *, setups=None, ctx=None, tile=None, d=S):
    setups = setups if setups is not None else {"bull_flag": pot()}
    return {"_id": ST.key(d, sym), "date": d.isoformat(), "symbol": sym, "setups": setups, "ctx": ctx or {},
            "tile": tile or {}}


def bdoc(sym, read, b):
    """A read doc whose one setup is a broke read over the tile bars `b` (the read's own 5m frame)."""
    return rdoc(sym, setups={read["setup"]: read}, tile={"bars5": b})


def scan(sym, vol, d=S):
    return {"_id": f"{d.isoformat()}|{sym}", "date": d.isoformat(), "symbol": sym, "last": {"volume": vol}}


def tracker(sym, vol, at_=T0, setup="bull_flag", d=S):
    return {"_id": ST.potential_key(d, sym, setup), "date": d.isoformat(), "symbol": sym, "setup": setup,
            "last": {"at": utc(at_), "session_volume": vol}}


def stores(gg5=(), gg1=(), scans=(), trackers=(), *, gg5_fail=False, gg1_fail=False, trackers_fail=False):
    g5 = ST.GajjalaStore(colls={ST.READS: FakeColl(gg5, fail=gg5_fail), ST.SCAN: FakeColl(scans),
                                ST.POTENTIALS: FakeColl(trackers, fail=trackers_fail)})
    g1 = ST.GajjalaStore(colls={ST.READS: FakeColl(gg1, fail=gg1_fail)}, variant=V.GG1)
    return {V.GG5.key: g5, V.GG1.key: g1}


class ListColl(FakeColl):
    """The list collection with a record of every find_one filter and update_one filter."""
    def __init__(self, docs=None, fail=False):
        super().__init__(docs, fail)
        self.reads, self.updates = [], []

    def find_one(self, q=None, projection=None):
        self.reads.append(copy.deepcopy(q))
        return super().find_one(q, projection)

    def update_one(self, q, upd, upsert=False):
        self.updates.append(copy.deepcopy(q))
        return super().update_one(q, upd, upsert)


def fake_db(manual=("OMH",), auto=None, *, list_fail=False):
    docs = [{"_id": C.LIST_DOC_ID, "symbols": list(manual)}]
    if auto is not None:
        docs.append(auto)
    return {C.COLL_LIST: ListColl(docs, fail=list_fail), C.COLL_TILES: FakeColl(), C.COLL_ALERTS: FakeColl(),
            C.COLL_STATE: FakeColl()}


def entry(sym, *, sources=("gajjala", "gga"), setup="bull_flag", kind="armed", volume=2_000_000.0,
          added_at=T0, dropped_since=None):
    return {"symbol": sym, "sources": list(sources), "setup": setup, "kind": kind, "volume": volume,
            "volume_source": "scan", "float_shares": None, "added_at": utc(added_at),
            "added_et": PT._hhmm(added_at), "dropped_since": utc(dropped_since) if dropped_since else None}


def auto_doc(entries=(), removed=(), dismissed=(), session=ISO, rev=1):
    return {"_id": C.AUTO_DOC_ID, "session": session, "rev": rev, "entries": list(entries), "removed": list(removed),
            "dismissed": list(dismissed)}


def stored(db):
    return db[C.COLL_LIST].docs.get(C.AUTO_DOC_ID)


def run(db, st, now=T0, manual=None, session=S, dry=False):
    m = manual if manual is not None else CO.owner_symbols(db)
    return A.step(now, session, db=db, manual=m, dry=dry, stores=st)


# ── constants ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_constants_are_the_named_ones():
    assert C.AUTO_SOURCES == (V.GG5.key, V.GG1.key, V.GGA.key)
    assert "gajjala_potentials" in V.GGA.borrows and ST.READS in V.GGA.borrows
    assert C.AUTO_MAX_SYMBOLS == GC.GG_WATCH_N and C.AUTO_MIN_VOLUME == GC.K11_MIN_SESSION_VOLUME
    assert C.AUTO_DROP_GRACE_SEC == GC.PASS_CADENCE_SEC and C.AUTO_REMOVED_SHOWN == C.AUTO_MAX_SYMBOLS
    assert C.AUTO_PUSH_MODES == GC.FADE_CROSS_PUSH_MODES and C.AUTO_PUSH_MODE == "off"
    assert C.HELD_REASONS[-1] == C.AUTO_HELD_REASON == "suppressed_auto"
    assert set(C.AUTO_REMOVE_STATES) | set(C.AUTO_KEEP_STATES) <= set(BS.STATES)
    assert "waiting" not in C.AUTO_REMOVE_STATES and "waiting" in C.AUTO_KEEP_STATES                  # [C1]
    assert set(C.AUTO_READ_SOURCES) < set(C.AUTO_SOURCES) and C.AUTO_DOC_ID != C.LIST_DOC_ID


# ── adds ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_gg5_armed_potential_with_scan_volume_is_added_with_the_borrowed_tag():
    db = fake_db()
    res = run(db, stores(gg5=[rdoc("AAA")], scans=[scan("AAA", 2_000_000)]))
    assert res["added"] == ["AAA"] and res["symbols"] == ["AAA"] and res["reason"] is None
    e = stored(db)["entries"][0]
    assert e["sources"] == ["gajjala", "gga"] and e["volume_source"] == "scan" and e["volume"] == 2_000_000
    assert e["kind"] == "armed" and e["setup"] == "bull_flag" and e["added_et"] == "10:01"
    assert e["added_at"] == utc(T0) and e["dropped_since"] is None and stored(db)["session"] == ISO
    assert stored(db)["rev"] == 1


def test_a_gg1_only_potential_is_tagged_one_minute_only():
    db = fake_db()
    run(db, stores(gg1=[rdoc("BBB")], scans=[scan("BBB", 3_000_000)]))
    assert stored(db)["entries"][0]["sources"] == ["gajjala_1m"]


def test_both_boards_tag_every_source():
    db = fake_db()
    run(db, stores(gg5=[rdoc("BBB")], gg1=[rdoc("BBB")], scans=[scan("BBB", 3_000_000)]))
    assert stored(db)["entries"][0]["sources"] == ["gajjala", "gajjala_1m", "gga"]


def test_a_batch_lands_in_potential_order_key_order():
    db = fake_db()
    reads = [rdoc("BLD", setups={"bull_flag": pot(ready=False)}),                       # building, loudest
             rdoc("ARM2", setups={"bull_flag": pot()}),                                  # armed 2M
             rdoc("ARM3B", setups={"bull_flag": pot()}, ctx={"float": {"shares": 9e6}}),  # armed 3M, float 9M
             rdoc("ARM3A", setups={"bull_flag": pot()}, ctx={"float": {"shares": 4e6}})]  # armed 3M, float 4M
    sc = [scan("BLD", 9e6), scan("ARM2", 2e6), scan("ARM3B", 3e6), scan("ARM3A", 3e6)]
    res = run(db, stores(gg5=reads, scans=sc))
    assert res["added"] == ["ARM3A", "ARM3B", "ARM2", "BLD"]
    assert stored(db)["entries"][0]["float_shares"] == 4e6


# ── [C2] volume precedence ───────────────────────────────────────────────────────────────────────────────────────
def test_C2_no_scan_row_falls_back_to_the_gg5_tracker_number():
    db = fake_db()
    res = run(db, stores(gg5=[rdoc("XXII")], trackers=[tracker("XXII", 1_123_834)]))
    e = stored(db)["entries"][0]
    assert res["added"] == ["XXII"] and e["volume"] == 1_123_834 and e["volume_source"] == "tracker"


def test_C2_the_newest_tracker_doc_wins():
    trk = [tracker("XXII", 900_000, at_=T0 - timedelta(minutes=10), setup="bull_flag"),
           tracker("XXII", 1_500_000, at_=T0 - timedelta(minutes=1), setup="kiss_fly")]
    sh = A.shared_sets(S, store=stores(trackers=trk)[V.GG5.key])
    assert A.volume_of("XXII", None, sh["trackers"]) == (1_500_000, "tracker")
    trk[0]["last"]["at"], trk[1]["last"]["at"] = trk[1]["last"]["at"], trk[0]["last"]["at"]
    sh = A.shared_sets(S, store=stores(trackers=trk)[V.GG5.key])
    assert A.volume_of("XXII", None, sh["trackers"]) == (900_000, "tracker")


def test_C2_NEGATIVE_a_scan_row_under_the_floor_wins_over_a_louder_tracker():
    db = fake_db()
    res = run(db, stores(gg5=[rdoc("AAA")], scans=[scan("AAA", 900_000)], trackers=[tracker("AAA", 2_000_000)]))
    assert res["added"] == [] and res["skipped"]["under_floor"] == 1 and stored(db) is None


def test_C2_NEGATIVE_a_gg1_only_potential_without_any_number_is_refused_and_counted():
    db = fake_db()
    res = run(db, stores(gg1=[rdoc("LGHL")]))
    assert res["added"] == [] and res["skipped"] == {"volume_unknown": 1, "under_floor": 0}


def test_C2_NEGATIVE_an_unreadable_tracker_set_is_scan_only_and_never_raises():
    db = fake_db()
    st = stores(gg5=[rdoc("AAA"), rdoc("BBB")], scans=[scan("AAA", 2_000_000), scan("BBB", None)], trackers_fail=True)
    assert A.shared_sets(S, store=st[V.GG5.key])["trackers"] is None
    res = run(db, st)
    assert res["added"] == ["AAA"] and res["skipped"]["volume_unknown"] == 1


# ── NEGATIVE adds ────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("vol", [999_999, float("nan"), None, "junk", True])
def test_NEGATIVE_under_the_floor_or_no_number_is_never_added(vol):
    db = fake_db()
    res = run(db, stores(gg5=[rdoc("AAA")], scans=[scan("AAA", vol)]))
    assert res["added"] == [] and stored(db) is None
    assert sum(res["skipped"].values()) == 1


def test_the_floor_itself_is_good_volume():
    assert A.good_volume({"volume": C.AUTO_MIN_VOLUME}) and not A.good_volume({"volume": C.AUTO_MIN_VOLUME - 1})
    assert not A.good_volume(None) and not A.good_volume({"volume": float("inf")})


@pytest.mark.parametrize("setups", [
    {"bull_flag": flat(state="partial")}, {"bull_flag": flat(state="aplus")},
    {"bull_flag": pot(base={"bars": 0})}, {"bull_flag": pot(variant="long_flag")}, {"bull_flag": pot(grade="B")},
    {"bull_flag": None}, {}])
def test_NEGATIVE_a_non_potential_is_never_added(setups):
    db = fake_db()
    res = run(db, stores(gg5=[rdoc("AAA", setups=setups)], scans=[scan("AAA", 5e6)]))
    assert res["added"] == [] and stored(db) is None


def test_NEGATIVE_a_name_on_his_list_is_never_an_entry_and_his_add_removes_an_entry():
    db = fake_db(manual=["AAA"])
    st = stores(gg5=[rdoc("AAA"), rdoc("BRK.B")], scans=[scan("AAA", 5e6), scan("BRK.B", 5e6)])
    res = run(db, st)
    assert res["added"] == ["BRK.B"]
    db[C.COLL_LIST].docs[C.LIST_DOC_ID]["symbols"] = ["AAA", "BRK-B"]                 # ➕ (the other spelling)
    res = run(db, st, now=T0 + timedelta(minutes=1))
    assert res["symbols"] == [] and res["removed"][0]["reason"] == "on_your_list"
    r = stored(db)["removed"][0]
    assert r["symbol"] == "BRK.B" and r["text"] == A._words().AUTO_ON_LIST_TEXT and r["at_et"] == "10:02"


def test_NEGATIVE_a_dismissed_name_is_not_re_added_this_session_and_is_after_the_reset():
    db = fake_db(auto=auto_doc(dismissed=["AAA"]))
    st = stores(gg5=[rdoc("AAA")], scans=[scan("AAA", 5e6)])
    assert run(db, st)["added"] == []
    nxt = date(2026, 11, 16)
    st2 = stores(gg5=[rdoc("AAA", d=nxt)], scans=[scan("AAA", 5e6, d=nxt)])
    res = run(db, st2, now=at(nxt, 9, 0), session=nxt)
    assert res["added"] == ["AAA"] and stored(db)["dismissed"] == [] and stored(db)["session"] == nxt.isoformat()


# ── cap ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_cap_keeps_the_loudest_and_a_louder_newcomer_never_displaces():
    names = [f"N{i:02d}" for i in range(20)]
    reads = [rdoc(s) for s in names]
    sc = [scan(s, 2e6 + i * 1e5) for i, s in enumerate(names)]
    db = fake_db()
    res = run(db, stores(gg5=reads, scans=sc))
    assert res["n"] == C.AUTO_MAX_SYMBOLS == len(stored(db)["entries"])
    assert res["added"] == list(reversed(names))[:C.AUTO_MAX_SYMBOLS]
    res = run(db, stores(gg5=reads + [rdoc("LOUD")], scans=sc + [scan("LOUD", 9e9)]), now=T0 + timedelta(minutes=1))
    assert "LOUD" not in res["symbols"] and res["added"] == [] and res["n"] == C.AUTO_MAX_SYMBOLS


# ── [C4] frozen order ────────────────────────────────────────────────────────────────────────────────────────────
def test_C4_the_order_is_the_order_added_and_never_re_sorted():
    db = fake_db()
    run(db, stores(gg5=[rdoc("A1"), rdoc("B1")], scans=[scan("A1", 5e6), scan("B1", 2e6)]))
    assert [e["symbol"] for e in stored(db)["entries"]] == ["A1", "B1"]
    reads = [rdoc("A1"), rdoc("B1"), rdoc("C1")]
    run(db, stores(gg5=reads, scans=[scan("A1", 5e6), scan("B1", 2e6), scan("C1", 9e6)]),
        now=T0 + timedelta(minutes=1))
    assert [e["symbol"] for e in stored(db)["entries"]] == ["A1", "B1", "C1"]
    for i in range(10):
        res = run(db, stores(gg5=reads, scans=[scan("A1", 5e6), scan("B1", 3e6 + i * 1e6), scan("C1", 9e6)]),
                  now=T0 + timedelta(minutes=2 + i))
        assert res["symbols"] == ["A1", "B1", "C1"]
    b = stored(db)["entries"][1]
    assert b["symbol"] == "B1" and b["volume"] == 12e6                     # the words move, the position does not


def test_C4_refreshed_kind_and_sources_move_the_words_only():
    db = fake_db()
    run(db, stores(gg5=[rdoc("A1", setups={"bull_flag": pot(ready=False)})], scans=[scan("A1", 5e6)]))
    assert stored(db)["entries"][0]["kind"] == "building"
    run(db, stores(gg5=[rdoc("A1")], gg1=[rdoc("A1")], scans=[scan("A1", 5e6)]), now=T0 + timedelta(minutes=1))
    e = stored(db)["entries"][0]
    assert e["kind"] == "armed" and e["sources"] == ["gajjala", "gajjala_1m", "gga"]


# ── [C1] removals ────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("b,state", [(BACK_UNDER, "back_under"), (STOP_PRINTED, "stop_printed")])
def test_C1_back_under_or_stop_printed_on_every_board_removes_at_once_with_the_card_line(b, state):
    r = broke(b=b)
    doc = bdoc("AAA", r, b)
    db = fake_db(auto=auto_doc([entry("AAA", sources=("gajjala", "gajjala_1m", "gga"))]))
    res = run(db, stores(gg5=[doc], gg1=[doc]))
    assert res["symbols"] == [] and res["removed"][0]["reason"] == "not_progressing"
    rec = stored(db)["removed"][0]
    assert rec["state"] == state and rec["source"] == "gajjala"
    assert rec["text"] == BS.block(r, doc, V.GG5)["text"] and rec["text"].startswith(BS.HEAD[state][:2])


@pytest.mark.parametrize("b", [WAITING, CONSOLIDATION])
def test_C1_NEGATIVE_waiting_above_the_trigger_is_never_removed(b):
    r = broke(b=b)
    doc = bdoc("AAA", r, b)
    assert BS.block(r, doc, V.GG5)["state"] == "waiting"
    db = fake_db(auto=auto_doc([entry("AAA", dropped_since=T0 - timedelta(minutes=1))]))
    for i in range(12):
        res = run(db, stores(gg5=[doc], gg1=[doc]), now=T0 + timedelta(minutes=i))
        assert res["symbols"] == ["AAA"] and res["leaving"] == []
    assert stored(db)["removed"] == [] and stored(db)["entries"][0]["dropped_since"] is None


def test_C1_progressing_names_are_kept():
    pot_doc = rdoc("AAA")
    stop = bdoc("AAA", broke(b=STOP_PRINTED), STOP_PRINTED)
    quiet = bdoc("AAA", broke(b=QUIET), QUIET)
    fresh = bdoc("AAA", broke(entry_i=1, b=BACK_UNDER), BACK_UNDER)                        # trigger bar = latest bar
    off = bdoc("AAA", broke(b=WAITING), WAITING)
    off["setups"]["bull_flag"]["entry_bar_t"] = f"{ISO} 09:00"                             # before the chart
    assert BS.block(quiet["setups"]["bull_flag"], quiet, V.GG5)["state"] == "broke_quiet"
    assert BS.block(fresh["setups"]["bull_flag"], fresh, V.GG5) is None
    assert BS.block(off["setups"]["bull_flag"], off, V.GG5)["state"] == "off_chart"
    for g5, g1 in [(stop, pot_doc), (quiet, stop), (fresh, stop), (off, stop), (stop, off)]:
        db = fake_db(auto=auto_doc([entry("AAA")]))
        res = run(db, stores(gg5=[g5], gg1=[g1]))
        assert res["symbols"] == ["AAA"] and res["removed"] == [], (g5, g1)
    p = A.progress("AAA", S, stores=stores(gg5=[off], gg1=[stop]), shared={"listed": {}})
    assert p["keep"] and p["unknown"]


def test_C1_a_remove_beside_a_dropped_board_removes_with_the_breakout_words():
    stop = bdoc("AAA", broke(b=STOP_PRINTED), STOP_PRINTED)
    db = fake_db(auto=auto_doc([entry("AAA", sources=("gajjala_1m",))]))
    res = run(db, stores(gg5=[stop], gg1=[rdoc("AAA", setups={"bull_flag": flat()})]))
    rec = stored(db)["removed"][0]
    assert res["symbols"] == [] and rec["reason"] == "not_progressing" and rec["source"] == "gajjala"
    assert rec["state"] == "stop_printed"


# ── [C3] the drop grace ──────────────────────────────────────────────────────────────────────────────────────────
def _dropped():
    return stores(gg5=[rdoc("AIMD", setups={"bull_flag": flat("bull_flag", "partial")})],
                  gg1=[rdoc("AIMD", setups={"bull_flag": flat("bull_flag", "invalid")})], scans=[scan("AIMD", 5e6)])


def _back():
    return stores(gg5=[rdoc("AIMD")], scans=[scan("AIMD", 5e6)])


def test_C3_dropped_waits_for_the_grace_and_a_potential_again_clears_it():
    db = fake_db(auto=auto_doc([entry("AIMD")]))
    res = run(db, _dropped())
    assert res["leaving"] == ["AIMD"] and res["symbols"] == ["AIMD"]
    assert stored(db)["entries"][0]["dropped_since"] == utc(T0)
    run(db, _back(), now=T0 + timedelta(seconds=60))
    assert stored(db)["entries"][0]["dropped_since"] is None
    t1 = T0 + timedelta(seconds=120)
    run(db, _dropped(), now=t1)
    res = run(db, _dropped(), now=t1 + timedelta(seconds=C.AUTO_DROP_GRACE_SEC - 60))
    assert res["symbols"] == ["AIMD"] and stored(db)["entries"][0]["dropped_since"] == utc(t1)
    res = run(db, _dropped(), now=t1 + timedelta(seconds=C.AUTO_DROP_GRACE_SEC))
    assert res["symbols"] == [] and res["removed"][0]["reason"] == "dropped"
    rec = stored(db)["removed"][0]
    word = PT.state_word("partial", None)
    assert rec["text"] == A._words().AUTO_DROPPED_TEXT.format(grace_min=C.AUTO_DROP_GRACE_SEC // 60, word=word)
    assert str(C.AUTO_DROP_GRACE_SEC // 60) in rec["text"] and rec["state"] == "partial"


def test_C3_NEGATIVE_the_aimd_flip_never_removes():
    db = fake_db(auto=auto_doc([entry("AIMD")]))
    for i in range(20):
        res = run(db, _dropped() if i % 2 == 0 else _back(), now=T0 + timedelta(minutes=i))
        assert res["symbols"] == ["AIMD"]
    assert stored(db)["removed"] == []


def test_C3_gone_from_a_non_empty_listed_set_is_the_graveyard_after_the_same_grace():
    st = stores(gg5=[rdoc("GONE")], scans=[scan("OTHER", 5e6)])
    db = fake_db(auto=auto_doc([entry("GONE")]))
    res = run(db, st)
    assert res["leaving"] == ["GONE"]
    res = run(db, st, now=T0 + timedelta(seconds=C.AUTO_DROP_GRACE_SEC))
    assert res["symbols"] == [] and PT.state_word("graveyard", None) in stored(db)["removed"][0]["text"]


def test_C3_every_removal_event_is_stored_and_returned():
    names = [f"R{i:02d}" for i in range(25)]
    docs = [bdoc(s, broke(b=STOP_PRINTED), STOP_PRINTED) for s in names]
    db = fake_db(auto=auto_doc([entry(s) for s in names]))
    res = run(db, stores(gg5=docs))
    assert len(res["removed"]) == 25 == len(stored(db)["removed"]) == res["removed_total"]
    assert [r["symbol"] for r in stored(db)["removed"]] == names


# ── [C5] listed ──────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("how", ["empty", "raise"])
def test_C5_an_empty_or_unreadable_listed_set_hides_nothing_and_never_says_gone(monkeypatch, how):
    if how == "raise":
        monkeypatch.setattr(SC, "listed_symbols", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    st = stores(gg5=[rdoc("NEW"), rdoc("KEEP")], trackers=[tracker("NEW", 2e6)])
    assert A.shared_sets(S, store=st[V.GG5.key])["listed"] == {}
    db = fake_db(auto=auto_doc([entry("KEEP", dropped_since=T0 - timedelta(minutes=1))]))
    res = run(db, st)
    assert res["added"] == ["NEW"] and "KEEP" in res["symbols"] and res["leaving"] == []


def test_C5_a_non_empty_listed_set_filters_the_adds():
    st = stores(gg5=[rdoc("IN"), rdoc("OUT")], scans=[scan("IN", 5e6)], trackers=[tracker("OUT", 5e6)])
    assert run(fake_db(), st)["added"] == ["IN"]


# ── NEGATIVE his list ────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_his_doc_is_byte_identical_after_50_steps_of_every_state():
    db = fake_db(manual=["OMH", "BRK.B"])
    before = copy.deepcopy(db[C.COLL_LIST].docs[C.LIST_DOC_ID])
    kinds = [_back, _dropped,
             lambda: stores(gg5=[bdoc("AIMD", broke(b=STOP_PRINTED), STOP_PRINTED)]),
             lambda: stores(gg5=[rdoc("OMH"), rdoc("AIMD")], scans=[scan("OMH", 5e6), scan("AIMD", 5e6)]),
             lambda: stores(gg5_fail=True)]
    for i in range(50):
        run(db, kinds[i % len(kinds)](), now=T0 + timedelta(minutes=i))
        if i == 25:
            A.dismiss("AIMD", by="o@example.com", db=db, now=T0 + timedelta(minutes=i))
    assert db[C.COLL_LIST].docs[C.LIST_DOC_ID] == before
    assert all(q.get("_id") == C.AUTO_DOC_ID for q in db[C.COLL_LIST].updates)
    assert "OMH" not in [e["symbol"] for e in stored(db)["entries"]]


# ── window / closed day ──────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("now", [at(SUNDAY, 10, 0), at(S, 20, 30)])
def test_NEGATIVE_no_adds_out_of_the_window_but_removals_still_apply(now):
    db = fake_db()
    res = run(db, stores(gg5=[rdoc("AAA")], scans=[scan("AAA", 5e6)]), now=now)
    assert res["added"] == [] and res["reason"] == "closed" and stored(db) is None
    stop = bdoc("BBB", broke(b=STOP_PRINTED), STOP_PRINTED)
    db = fake_db(auto=auto_doc([entry("BBB")]))
    res = run(db, stores(gg5=[stop, rdoc("AAA")], scans=[scan("AAA", 5e6), scan("BBB", 5e6)]), now=now)
    assert res["symbols"] == [] and res["removed"][0]["reason"] == "not_progressing"


# ── faults ───────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("which", ["gg5", "gg1"])
def test_NEGATIVE_an_unreadable_board_adds_nothing_judges_no_drop_and_keeps_every_entry(which):
    since = T0 - timedelta(minutes=10)
    db = fake_db(auto=auto_doc([entry("AAA", dropped_since=since), entry("BBB")]))
    st = stores(gg5=[rdoc("NEW")], scans=[scan("NEW", 5e6)], gg5_fail=which == "gg5", gg1_fail=which == "gg1")
    assert A.potential_sets(S, shared=A.shared_sets(S, store=st[V.GG5.key]), stores=st) is None
    res = run(db, st)
    assert res["reason"] == "boards_unreadable" and res["added"] == [] and res["symbols"] == ["AAA", "BBB"]
    assert stored(db)["entries"][0]["dropped_since"] == utc(since) and stored(db)["removed"] == []


def test_NEGATIVE_no_store_handle_is_unreadable_never_empty():
    st = {V.GG5.key: ST.GajjalaStore(colls={ST.READS: None}), V.GG1.key: None}
    assert A.potential_sets(S, shared={"listed": {}, "scan_by": {}, "trackers": {}}, stores=st) is None


def test_NEGATIVE_an_unreadable_auto_doc_writes_nothing():
    db = fake_db(list_fail=True)
    res = run(db, stores(gg5=[rdoc("AAA")], scans=[scan("AAA", 5e6)]), manual=[])
    assert res["reason"] == "list_unreadable" and res["symbols"] == [] and db[C.COLL_LIST].writes == 0
    assert A.read_doc(None) is None and A.current_symbols(None, ISO) == []


def test_session_reset_clears_entries_removed_and_dismissed():
    db = fake_db(auto=auto_doc([entry("OLD")], removed=[{"symbol": "X"}], dismissed=["Y"], session=PREV.isoformat()))
    assert A.current_symbols(CO.colls(db), ISO) == []
    res = run(db, stores(gg5=[rdoc("Y")], scans=[scan("Y", 5e6)]))
    d = stored(db)
    assert d["session"] == ISO and res["symbols"] == ["Y"] and d["removed"] == [] and d["dismissed"] == []


def test_NEGATIVE_nothing_to_say_writes_nothing():
    db = fake_db()
    run(db, stores())
    assert db[C.COLL_LIST].writes == 0 and stored(db) is None


def test_dry_returns_the_would_be_doc_and_writes_nothing():
    db = fake_db()
    res = run(db, stores(gg5=[rdoc("AAA")], scans=[scan("AAA", 5e6)]), dry=True)
    assert res["writes"]["entries"][0]["symbol"] == "AAA" and db[C.COLL_LIST].writes == 0


# ── CAS ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_CAS_a_write_landing_between_read_and_set_re_reads_and_lands_on_top():
    db = fake_db(auto=auto_doc(rev=4))
    coll = db[C.COLL_LIST]
    real = coll.update_one
    fired = []

    def racing(q, upd, upsert=False):
        if not fired:
            fired.append(1)
            coll.docs[C.AUTO_DOC_ID].update(rev=5, dismissed=["ZZZ"])          # another writer (his ×)
        return real(q, upd, upsert)
    coll.update_one = racing
    res = run(db, stores(gg5=[rdoc("AAA"), rdoc("ZZZ")], scans=[scan("AAA", 5e6), scan("ZZZ", 9e6)]))
    d = stored(db)
    assert d["rev"] == 6 and d["dismissed"] == ["ZZZ"] and res["symbols"] == ["AAA"]
    assert [q.get("rev") for q in coll.updates] == [4, 5]


def test_NEGATIVE_a_raising_write_keeps_the_stored_names():
    db = fake_db(auto=auto_doc([entry("OLD")]))

    def boom(*a, **k):
        raise RuntimeError("down")
    db[C.COLL_LIST].update_one = boom
    res = run(db, stores(gg5=[rdoc("OLD"), rdoc("AAA")], scans=[scan("AAA", 5e6), scan("OLD", 5e6)]))
    assert res["reason"] == "write_failed" and res["symbols"] == ["OLD"] and res["added"] == []


# ── dismiss [C7][C8] ─────────────────────────────────────────────────────────────────────────────────────────────
def test_dismiss_an_entry_pulls_it_records_it_and_blocks_the_re_add():
    db = fake_db(auto=auto_doc([entry("AAA"), entry("BBB")]))
    out = A.dismiss("aaa", by="o@example.com", db=db, now=T0)
    assert out["state"] == "dismissed" and out["symbol"] == "AAA" and out["symbols"] == ["OMH"]
    assert out["text"] == A._words().store_text("dismissed", "AAA")
    d = stored(db)
    assert [e["symbol"] for e in d["entries"]] == ["BBB"] and d["dismissed"] == ["AAA"] and d["by"] == "o@example.com"
    assert d["removed"][0]["reason"] == "dismissed" and d["removed"][0]["text"] == A._words().AUTO_DISMISSED_TEXT
    res = run(db, stores(gg5=[rdoc("AAA"), rdoc("BBB")], scans=[scan("AAA", 5e6), scan("BBB", 5e6)]),
              now=T0 + timedelta(minutes=1))
    assert res["symbols"] == ["BBB"] and res["added"] == []


def test_dismiss_a_name_that_is_not_an_entry_blocks_it_today():
    db = fake_db(auto=auto_doc())
    assert A.dismiss("OMH", by="o", db=db, now=T0)["state"] == "absent"
    assert stored(db)["dismissed"] == ["OMH"]
    w = db[C.COLL_LIST].writes
    assert A.dismiss("OMH", by="o", db=db, now=T0)["state"] == "absent" and db[C.COLL_LIST].writes == w


def test_C7_dismiss_on_a_stale_doc_before_the_first_step_is_the_session_reset():
    db = fake_db(auto=auto_doc([entry("AAA")], removed=[{"symbol": "X"}], session=PREV.isoformat()))
    out = A.dismiss("XYZ", by="o", db=db, now=at(S, 4, 0, 30))
    d = stored(db)
    assert out["state"] == "absent" and d["session"] == ISO and d["entries"] == [] and d["removed"] == []
    assert d["dismissed"] == ["XYZ"]
    res = run(db, stores(gg5=[rdoc("XYZ")], scans=[scan("XYZ", 5e6)]), now=at(S, 4, 1, 30))
    assert res["added"] == [] and res["symbols"] == []


def test_C7_before_04_00_the_x_lands_in_the_last_session_and_the_session_change_clears_it():
    """BLD.session_of before 04:00 ET is the LAST market session (tab.session_for) — a × at 03:50 goes into that
    session's doc (the board shows that session's rows then); the 04:0x step's session reset clears it (HIS CALL #5)."""
    db = fake_db(auto=auto_doc([entry("XYZ")], session=PREV.isoformat()))
    out = A.dismiss("XYZ", by="o", db=db, now=at(S, 3, 50))
    assert out["state"] == "dismissed" and stored(db)["session"] == PREV.isoformat()
    res = run(db, stores(gg5=[rdoc("XYZ")], scans=[scan("XYZ", 5e6)]), now=at(S, 4, 1, 30))
    assert res["added"] == ["XYZ"]


def test_C8_a_non_ticker_is_absent_without_reading_or_writing_the_auto_doc():
    db = fake_db(auto=auto_doc([entry("AAA")]))
    out = A.dismiss("not a ticker!", by="o", db=db, now=T0)
    assert out["state"] == "absent" and out["symbol"] is None
    assert all(q.get("_id") != C.AUTO_DOC_ID for q in db[C.COLL_LIST].reads) and db[C.COLL_LIST].writes == 0
    assert A.dismiss(None, by="o", db=db)["state"] == "absent"


def test_NEGATIVE_dismiss_never_raises_on_an_unreadable_list():
    out = A.dismiss("AAA", by="o", db=fake_db(list_fail=True), now=T0)
    assert out["state"] == "error"


# ── hold_crosses ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_hold_crosses_holds_the_own_minute_up_cross_only():
    held = {}
    n = A.hold_crosses({"XYZ": frames_stub(up_at(10, 6)), "OLD": frames_stub(up_at(10, 2)), "NIL": None},
                       at(S, 10, 6, 30), S, held)
    assert n == 1 and held == {"XYZ": {"1m": {"bar_t": up_at(10, 6).t[-1], "reason": C.AUTO_HELD_REASON}}}


# ── the loop wiring [C6] ─────────────────────────────────────────────────────────────────────────────────────────
def _loop_env(monkeypatch, auto_syms=("XYZ",), *, raise_step=False):
    frames = {"OMH": frames_stub(up_at(10, 6)), "XYZ": frames_stub(up_at(10, 6))}
    calls, pushed = [], []
    monkeypatch.setattr(BLD, "frames", lambda symbols, *a, **k: (calls.append(list(symbols)),
                                                                   {s: frames[s] for s in symbols if s in frames})[1])

    def spy(F, *a, **k):
        pushed.append(list(F))
        return {"names": len(F)}
    monkeypatch.setattr(L.XA, "run", spy)

    def step(*a, **k):
        if raise_step:
            raise RuntimeError("boom")
        return {"symbols": list(auto_syms), "n": len(auto_syms), "added": [], "removed": [], "leaving": [],
                "skipped": {"volume_unknown": 0, "under_floor": 0}, "reason": None, "writes": {"x": 1}}
    monkeypatch.setattr(L.AUTO, "step", step)
    return calls, pushed


def test_C6_the_loop_builds_both_pushes_his_only_and_holds_the_auto_cross(monkeypatch):
    calls, pushed = _loop_env(monkeypatch)
    sent = []
    db = fake_db(manual=["OMH"])
    out = L.run_iteration(at(S, 10, 6, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: None,
                                                                 send=lambda o, p: sent.append(p)))
    assert calls == [["OMH", "XYZ"]] and pushed == [["OMH"]] and sent == []
    assert db[C.COLL_TILES].docs["XYZ"]["held"]["1m"]["reason"] == C.AUTO_HELD_REASON
    st = db[C.COLL_STATE].docs[C.STATE_LATEST_ID]
    assert st["n_names"] == 2 and st["alerts"]["names"] == 1 and st["alerts"][C.AUTO_HELD_REASON] == 1
    assert st["auto"]["n"] == 1 and st["auto"]["cap"] == C.AUTO_MAX_SYMBOLS and "writes" not in st["auto"]
    assert out["n_names"] == 2 and out["auto"]["n"] == 1 and "writes" not in out["auto"]
    assert "[C6]" in L.__doc__ and "`alerts.names` = his names" in L.__doc__


def test_C6_live_mode_hands_the_auto_frames_to_the_one_engine(monkeypatch):
    _calls, pushed = _loop_env(monkeypatch)
    monkeypatch.setattr(C, "AUTO_PUSH_MODE", "live")
    db = fake_db(manual=["OMH"])
    L.run_iteration(at(S, 10, 6, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    st = db[C.COLL_STATE].docs[C.STATE_LATEST_ID]
    assert pushed == [["OMH", "XYZ"]] and st["alerts"] == {"names": 2}


def test_NEGATIVE_a_junk_push_mode_fails_closed_to_off(monkeypatch):
    _calls, pushed = _loop_env(monkeypatch)
    monkeypatch.setattr(C, "AUTO_PUSH_MODE", "LIVE!")
    L.run_iteration(at(S, 10, 6, 30), db=fake_db(manual=["OMH"]), deps=L.Deps(load_day=lambda *a, **k: None))
    assert pushed == [["OMH"]] and A.push_mode() == "off"


def test_NEGATIVE_his_names_alone_keep_the_alerts_counts_byte_identical(monkeypatch):
    _calls, pushed = _loop_env(monkeypatch, auto_syms=())
    db = fake_db(manual=["OMH"])
    L.run_iteration(at(S, 10, 6, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    assert db[C.COLL_STATE].docs[C.STATE_LATEST_ID]["alerts"] == {"names": 1} and pushed == [["OMH"]]


def test_NEGATIVE_an_auto_name_he_also_listed_is_his_and_read_once(monkeypatch):
    calls, pushed = _loop_env(monkeypatch, auto_syms=("OMH", "XYZ"))
    L.run_iteration(at(S, 10, 6, 30), db=fake_db(manual=["OMH"]), deps=L.Deps(load_day=lambda *a, **k: None))
    assert calls == [["OMH", "XYZ"]] and pushed == [["OMH"]]


def test_NEGATIVE_a_raising_auto_step_keeps_the_last_entries_served(monkeypatch):
    calls, _pushed = _loop_env(monkeypatch, raise_step=True)
    db = fake_db(manual=["OMH"], auto=auto_doc([entry("XYZ")]))
    out = L.run_iteration(at(S, 10, 6, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    assert out["ran"] and calls == [["OMH", "XYZ"]] and out["auto"]["reason"] == "error"


def test_an_empty_list_with_auto_names_reads_them(monkeypatch):
    calls, pushed = _loop_env(monkeypatch)
    db = fake_db(manual=[])
    out = L.run_iteration(at(S, 10, 6, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    assert out["ran"] and calls == [["XYZ"]] and pushed == [[]]


def test_NEGATIVE_the_symbols_stub_skips_the_auto_step(monkeypatch):
    calls, _pushed = _loop_env(monkeypatch)
    monkeypatch.setattr(L.AUTO, "step", lambda *a, **k: pytest.fail("the stub never runs the auto step"))
    out = L.run_iteration(at(S, 10, 6, 30), db=fake_db(), deps=L.dry_deps(), dry=True, symbols=["OMH"])
    assert calls == [["OMH"]] and out["auto"]["reason"] == "stub"


def test_dry_run_without_symbols_returns_the_auto_writes_and_writes_nothing(monkeypatch):
    calls = []
    monkeypatch.setattr(BLD, "frames", lambda symbols, *a, **k: (calls.append(list(symbols)), {})[1])
    db = fake_db(manual=["OMH"])
    monkeypatch.setattr(CO, "_db", lambda: db)
    monkeypatch.setattr(A, "_default_stores", lambda: stores(gg5=[rdoc("AAA")], scans=[scan("AAA", 5e6)]))
    out = L.run_iteration(at(S, 10, 6, 30), deps=L.dry_deps(), dry=True)
    assert out["auto"]["writes"]["entries"][0]["symbol"] == "AAA" and calls == [["OMH", "AAA"]]
    assert all(c.writes == 0 for c in db.values())


def test_the_real_engine_inside_the_loop_adds_and_the_state_doc_says_so(monkeypatch):
    monkeypatch.setattr(BLD, "frames", lambda symbols, *a, **k: {})
    monkeypatch.setattr(A, "_default_stores", lambda: stores(gg5=[rdoc("AAA")], scans=[scan("AAA", 5e6)]))
    db = fake_db(manual=["OMH"])
    L.run_iteration(at(S, 10, 6, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    st = db[C.COLL_STATE].docs[C.STATE_LATEST_ID]
    assert st["auto"]["added"] == ["AAA"] and st["n_names"] == 2 and stored(db)["entries"][0]["symbol"] == "AAA"


# ── words / rules ────────────────────────────────────────────────────────────────────────────────────────────────
def test_rules_line_follows_the_constants(monkeypatch):
    line = A.rules_line()
    assert f"{C.AUTO_MIN_VOLUME:,}" in line and f"up to {C.AUTO_MAX_SYMBOLS}" in line and "UNMEASURED" in line
    assert f"{C.AUTO_DROP_GRACE_SEC // 60} minutes" in line and "mode off" in line and "⏸" in line
    monkeypatch.setattr(C, "AUTO_PUSH_MODE", "live")
    monkeypatch.setattr(C, "AUTO_KEEP_STATES", ("broke_vol",))
    live = A.rules_line()
    assert "mode live" in live and "⏸" not in live


def test_rules_line_types_no_digit():
    tree = ast.parse(inspect.getsource(A))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "rules_line")
    words = [n.value for n in ast.walk(fn) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    words += [v for k, v in list(A._REMOVE_WORDS.items()) + list(A._KEEP_WORDS.items())]
    bad = [w for w in words if re.search(r"[0-9]", re.sub(r"\bK[0-9]+\b", "", w))]
    assert bad == []


def test_the_rules_panel_note_carries_the_clause_and_survives_a_broken_module(monkeypatch):
    from supply_demand import rules_info as RI
    assert A.rules_line() in RI._gajjala_section()["note"]
    monkeypatch.setattr(A, "rules_line", lambda: 1 / 0)
    assert RI._gg_watch_auto_clause() == ""
    assert "🤖 Gajjala's Watch adds" not in RI._gajjala_section()["note"]


def test_source_guard_auto_never_fetches_pushes_or_writes_his_doc():
    src = inspect.getsource(A)
    for bad in ("frames_for", "load_day", "push.hooks", "from push", "claim_key", "C.LIST_DOC_ID", "send("):
        assert bad not in src, bad
    gg = inspect.getsource(A).count("chart_maps.gajjala import")
    assert gg >= 1
