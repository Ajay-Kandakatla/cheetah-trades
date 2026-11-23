"""⏹ The 🚩 1-minute page retired — the 👀 Watch keeps its 1-minute charts (spec ret1m 2026-11-18 §3.9, §3.13, WP-W).

Ajay 2026-11-18 ~00:10 ET, verbatim: "This is good info stop 1 min tab it was a good experiment" — then ~00:20 ET: "But
keep the one min chart in the watch list I still want them".

THE HARD KEEP, proven with the switch at its SHIPPED value (GC.GAJJALA_1M_ENABLED False, asserted, never patched): the
Watch's own minute bars path (build.frames → bars.frames_for with C.FRAMES) still serves 1-minute bars with the 9 / 21
EMA curves; one Watch loop iteration still runs (frames fetched once, tiles written, GG1's lease NUMBERS claimed and
released, the cross engine reached) without ONE call into the retired GG1 pass; the ⤢ card frame's 1-minute view draws
from the tile that loop wrote. The 🤖 auto section's ACTIVE sources drop the 🚩 1-min board while off (no GG1 store read,
a GG1-only potential / tracker / A+ never seats, the hint and the ℹ️ line name only the 🚩 5-min and 🧪 boards) and an
entry stored with "gajjala_1m" keeps its words (history). Each OFF pin flips the switch ON in-test and proves the
return (reversible). NEGATIVES are the point.
"""
from __future__ import annotations

from datetime import timedelta, timezone

import pytest

from chart_maps.gajjala import card_frames as CF
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import run_1m as R1
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import variant as V
from chart_maps.gajjala_watch import auto as A
from chart_maps.gajjala_watch import build as BLD
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import cross_alerts as XA
from chart_maps.gajjala_watch import loop as L
from chart_maps.gajjala_watch import payload as PL
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_watch_auto_2026_11_17 import (ISO, auto_doc, entry, rdoc, scan, stored, stores,
                                                      tracker)
from tests.test_gajjala_watch_auto_2026_11_17 import fake_db as auto_db
from tests.test_gajjala_watch_auto_2026_11_17 import run as auto_run
from tests.test_gajjala_watch_auto_aplus_2026_11_17 import marked, mread, stores_ap
from tests.test_gajjala_watch_build_2026_11_15 import NOW, PREV, S, at, loader, raw_day, stamp
from tests.test_gajjala_watch_loop_2026_11_15 import fake_db as loop_db

T_LOOP = at(S, 10, 6, 30)
T_GP = at(S, 17, 1, 30)
ON_SOURCES = ("gajjala", "gajjala_1m", "gga")


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.delenv("GAJJALA_1M_ENABLED", raising=False)


def _off():
    assert GC.GAJJALA_1M_ENABLED is False and V.enabled(V.GG1) is False     # the shipped value — never patched here


def _on(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_1M_ENABLED", True)
    assert V.enabled(V.GG1) is True


def _no_gg1_pass(monkeypatch):
    """Any call into the retired GG1 pass fails the test."""
    def boom(*a, **k):
        raise AssertionError("the retired GG1 pass was called")
    for name in ("run_iteration", "spawn_loop", "loop"):
        monkeypatch.setattr(R1, name, boom)


def _price(ts):
    mm = ts.hour * 60 + ts.minute
    return 14.0 if mm >= 10 * 60 + 5 else 10.0 - 0.002 * (mm - 4 * 60)


def _load(sym, day, force=False, include_premarket=True, include_afterhours=False):
    return (raw_day(S, end=(10, 7), price=_price, volume=5000.0) if day == S
            else raw_day(PREV, price=lambda ts: 10.0))


def _loop_iteration(monkeypatch, db):
    """ONE real Watch loop iteration (the 2026-11-15 harness) with the frames and the cross engine spied."""
    fetched, crossed = [], []
    real_frames, real_xa = BLD.frames, XA.run

    def frames_spy(symbols, session, now, **k):
        fetched.append(list(symbols))
        return real_frames(symbols, session, now, **k)

    def xa_spy(*a, **k):
        crossed.append(1)
        return real_xa(*a, **k)
    monkeypatch.setattr(BLD, "frames", frames_spy)
    monkeypatch.setattr(XA, "run", xa_spy)
    out = L.run_iteration(T_LOOP, db=db, deps=L.Deps(load_day=_load, send=lambda o, p: {"sent": 1,
                                                                                        "total_targets": 1},
                                                     owner="owner@example.com"))
    return out, fetched, crossed


def _gg5_store(sym):
    b15 = [{"t": f"{ISO} 09:45", "o": 10.0, "h": 10.2, "l": 9.9, "c": 10.1, "v": 1000}]
    b5 = [{"t": f"{ISO} 09:35", "o": 10.0, "h": 10.2, "l": 9.9, "c": 10.1, "v": 1000}]
    doc = {"_id": ST.key(ISO, sym), "date": ISO, "symbol": sym, "at": T_LOOP.astimezone(timezone.utc),
           "tile": {"bars15": b15, "curves15": [], "bars5": b5, "curves5": []}}
    return ST.GajjalaStore({ST.READS: FakeColl([doc])})


def _empty_gg1_store(s5):
    return ST.GajjalaStore({ST.READS: FakeColl([])}, variant=V.GG1, shared=s5)


# ── THE HARD KEEP ────────────────────────────────────────────────────────────────────────────────────────────────
def test_HARD_KEEP_the_watch_tile_still_serves_1_minute_bars_and_emas_with_the_switch_off(monkeypatch):
    _off()
    # RE-PINNED 2026-11-23 (Ajay: "Can you remove 3 mins just add 15 mins instead.. So 1 min, 5 and 15 accross board"):
    # the 1-minute chart he kept stays first; 3m → 15m.
    assert C.FRAMES == (("1m", "1min"), ("5m", "5min"), ("15m", "15min")) and C.AXIS_FRAME == "1m"
    assert C.PUSH_FRAMES == ("1m",)
    F = BLD.frames(["OMH"], S, NOW, load_day=loader())
    assert "OMH" in F
    fo = F["OMH"]
    f1 = fo.frame("1m")
    assert len(f1) and f1.today.stop > f1.today.start
    end = BLD.axis_end(S, [f1.t[i] for i in f1.today])
    t = BLD.tile(fo, "1m", end)
    assert t["bars"] and t["tf"] == "1m"
    tones = {c["tone"] for c in t["curves"]}
    assert {"ema9", "ema21"} <= tones
    assert set(t["ema_tail"]) == {"ema9", "ema21"}
    # the served board: his row carries the 1m / 5m / 15m charts from the stored tile doc (RE-PINNED 2026-11-23)
    db = loop_db(symbols=["OMH"])
    flt, upd = BLD.tile_update("OMH", fo, S, NOW, "loaded")
    BLD.write(db[C.COLL_TILES], [(flt, upd)])
    row = PL.build(NOW, db=db)["rows"][0]
    by = {f["tf"]: f for f in row["frames"]}
    assert row["state"] == "ok" and list(by) == ["1m", "5m", "15m"]
    assert by["1m"]["tile"]["bars"] and by["5m"]["tile"]["bars"] and by["15m"]["tile"]["bars"]
    assert {c["tone"] for c in by["1m"]["tile"]["curves"]} >= {"ema9", "ema21"}
    # NEGATIVE: the retired GG1 pass reads NOTHING — a raising loader is never called, no store is built
    calls = []

    def raising_load(*a, **k):
        calls.append(a)
        raise AssertionError("the GG1 pass fetched")
    monkeypatch.setattr(ST, "for_variant", lambda *a, **k: (_ for _ in ()).throw(AssertionError("a GG1 store")))
    out = R1.run_iteration(T_LOOP, deps=R1.Deps1m(load_day=raising_load))
    assert out["reason"] == R1.LOOP_REASONS[2] == "off" and out["ran"] is False and calls == []


def test_HARD_KEEP_the_watch_loop_iteration_runs_with_the_switch_off(monkeypatch):
    _off()
    _no_gg1_pass(monkeypatch)
    db = loop_db(symbols=["OMH"])
    out, fetched, crossed = _loop_iteration(monkeypatch, db)
    assert out["ran"] is True and fetched == [["OMH"]] and crossed == [1]
    assert out["alerts"]["pushed"] == 1                                       # the 9 / 21 cross still rings his name
    tile = db[C.COLL_TILES].docs["OMH"]
    assert tile["status"] == "loaded" and tile["session"] == ISO and tile["seen_bar_t"] == stamp(S, 10, 6)
    assert list(tile["frames"]) == ["1m", "5m", "15m"] and tile["frames"]["1m"]["bars"]   # RE-PINNED 2026-11-23
    lease = db[C.COLL_STATE].docs[ST.LEASE_ID]
    assert lease["status"] == "done"                                         # claimed and released
    assert L.lease_store(FakeColl())._lease_nums() == (GC.GG1M_LEASE_SEC, GC.GG1M_LEASE_MIN_GAP_SEC)


def test_HARD_KEEP_the_card_frame_1m_view_draws_from_the_watch_tile_written_by_that_loop(monkeypatch):
    _off()
    _no_gg1_pass(monkeypatch)
    db = loop_db(symbols=["OMH"])
    _loop_iteration(monkeypatch, db)
    wt = db[C.COLL_TILES]
    s5 = _gg5_store("OMH")
    now = T_LOOP + timedelta(seconds=10)
    out = CF.build("OMH", now, stores=(s5, _empty_gg1_store(s5), wt))
    f15, f5, f1 = out["frames"]
    assert out["state"] == "ok" and f1["tf"] == "1m"
    assert f1["tile"]["bars"] == wt.docs["OMH"]["frames"]["1m"]["bars"] and f1["tile"]["bars"]
    # re-pinned 2026-11-23 (spec vwapzones §3.7; was `curves == stored curves`): the two stored EMAs byte-equal, then
    # the Watch's VWAP curve aligned by stamp from the SAME stored frame (none when the frame carries no VWAP value)
    from chart_maps.gajjala_watch import vwap as VW
    stored_1m = wt.docs["OMH"]["frames"]["1m"]
    assert f1["tile"]["curves"][:2] == stored_1m["curves"] and len(stored_1m["curves"]) == 2
    vw = VW.align(VW.by_stamp(stored_1m), stored_1m["bars"])
    assert f1["tile"]["curves"][2:] == ([] if vw is None else [{"tone": "vwap", "label": "VWAP", "values": vw}])
    assert all(c["tone"] != "vwap" for c in stored_1m["curves"])            # NEGATIVE: the stored doc never carries the curve
    assert f1["empty_text"] is None and f1["stale"] is False and f1["as_of_et"] == "10:06"
    assert f15["tile"]["bars"] and f5["tile"]["bars"]                         # the 15m / 5m charts from GG5's doc
    # NEGATIVE: a name the loop did not write → the retired words naming the symbol, never a chart
    s5b = _gg5_store("AMD")
    neg = CF.build("AMD", now, stores=(s5b, _empty_gg1_store(s5b), wt))["frames"][2]
    assert neg["tile"]["bars"] == [] and neg["empty_text"] == V.word("card_1m_empty", V.GG1, sym="AMD")
    assert "AMD" in neg["empty_text"] and "retired" in neg["empty_text"]
    # ON (reversible): the same missing name serves the 2026-11-16 words
    _on(monkeypatch)
    on = CF.build("AMD", now, stores=(s5b, _empty_gg1_store(s5b), wt))["frames"][2]
    assert on["empty_text"] == CF.EMPTY_TEXT.format(minutes=1, sym="AMD")


# ── 🤖 auto sources ──────────────────────────────────────────────────────────────────────────────────────────────
def test_auto_sources_drop_the_1m_page_while_off(monkeypatch):
    _off()
    monkeypatch.setattr(PL, "_auto_mod", lambda: A)
    assert A.read_sources() == ("gajjala",) and A.sources() == ("gajjala", "gga")
    assert C.AUTO_SOURCES == ON_SOURCES and C.AUTO_READ_SOURCES == ("gajjala", "gajjala_1m")   # registry untouched
    rl, hint = A.rules_line(), PL.auto_hint()
    for text in (rl, hint):
        assert "🚩 5-min and 🧪" in text and "🚩 1-min" not in text
    assert "1-min cross" in hint                                              # the Watch's OWN 1m cross words stay
    monkeypatch.setattr(ST, "default", lambda: "S5")
    monkeypatch.setattr(ST, "for_variant", lambda v: f"S:{v.key}")
    assert set(A._default_stores()) == {"gajjala", "gga"}
    assert set(PL._aplus_stores()) == {"gajjala", "gga"}
    _on(monkeypatch)
    assert A.read_sources() == ("gajjala", "gajjala_1m") and A.sources() == ON_SOURCES
    assert "🚩 5-min, 🚩 1-min and 🧪" in A.rules_line() and "🚩 5-min, 🚩 1-min and 🧪" in PL.auto_hint()
    assert set(A._default_stores()) == {"gajjala", "gajjala_1m", "gga"}
    assert set(PL._aplus_stores()) == {"gajjala", "gajjala_1m", "gga"}


def test_NEGATIVE_the_env_alone_also_drops_the_source(monkeypatch):
    _on(monkeypatch)
    monkeypatch.setenv("GAJJALA_1M_ENABLED", "0")
    assert A.read_sources() == ("gajjala",) and A.sources() == ("gajjala", "gga")


def test_NEGATIVE_a_gg1_only_potential_or_tracker_or_aplus_never_seats_while_off(monkeypatch):
    _off()
    # a GG1-only potential + a GG1-only tracker; the GG1 store's reads and trackers RAISE if queried
    st = stores(gg5=[rdoc("AAA")], gg1=[rdoc("BBB")], scans=[scan("AAA", 2_000_000), scan("BBB", 3_000_000)],
                trackers1=[tracker("CCC", 3_000_000, first_seen=at(S, 9, 50))], gg1_fail=True,
                trackers1_fail=True)
    db = auto_db()
    res = auto_run(db, st)
    assert res["added"] == ["AAA"] and res["reason"] is None
    ents = stored(db)["entries"]
    assert [e["symbol"] for e in ents] == ["AAA"] and ents[0]["sources"] == ["gajjala", "gga"]
    # ON: the SAME raising GG1 store is read → unknown, nothing is added (it WAS read)
    _on(monkeypatch)
    db_on = auto_db()
    res_on = auto_run(db_on, st)
    assert res_on["added"] == []
    # healthy GG1 store, ON → the GG1-only names seat (the 2026-11-17 behaviour returns)
    ok = stores(gg5=[rdoc("AAA")], gg1=[rdoc("BBB")], scans=[scan("AAA", 2_000_000), scan("BBB", 3_000_000)])
    db_ok = auto_db()
    auto_run(db_ok, ok)
    assert {e["symbol"] for e in stored(db_ok)["entries"]} == {"AAA", "BBB"}


def test_NEGATIVE_a_gg1_only_aplus_never_seats_while_off_and_a_gg5_one_does(monkeypatch):
    _off()
    st = stores_ap(gg5=[mread("GP", marked())], gg1=[mread("SMX", marked("stopped", "15:21"))])
    db = auto_db(manual=[])
    auto_run(db, st, now=T_GP, manual=[])
    syms = {e["symbol"]: e for e in stored(db)["entries"]}
    assert "SMX" not in syms and "GP" in syms
    assert "gajjala_1m" not in syms["GP"]["sources"]
    # the served 🎯 tag without a GG1 store key works (GG5 + 🧪 only)
    no_gg1 = {k: v for k, v in st.items() if k != V.GG1.key}
    sec = PL.aplus_section(["GP", "SMX"], ISO, stores=no_gg1)
    assert "GP" in sec and "SMX" not in sec
    assert all(it["source"] != "gajjala_1m" for it in sec["GP"]["items"])
    _on(monkeypatch)
    db_on = auto_db(manual=[])
    auto_run(db_on, st, now=T_GP, manual=[])
    assert "SMX" in {e["symbol"] for e in stored(db_on)["entries"]}


def test_history_words_of_a_stored_1m_entry_stay_readable(monkeypatch):
    _off()
    monkeypatch.setattr(PL, "_aplus_stores", lambda: {})
    db = auto_db(manual=[], auto=auto_doc([entry("LGHL", sources=("gajjala_1m",))]))
    out = PL.build(at(S, 10, 30), db=db)
    a = next(r for r in out["rows"] if r["symbol"] == "LGHL")["auto"]
    assert a["sources"] == ["gajjala_1m"] and a["source_words"] == ["🚩 1-min"]
    assert "🚩 5-min and 🧪" in out["auto"]["hint"] and "🚩 1-min" not in out["auto"]["hint"]


def test_progress_reads_only_active_sources(monkeypatch):
    _off()
    st = stores(gg5=[rdoc("AAA")], gg1_fail=True)
    p = A.progress("AAA", S, stores=st, shared={}, entry=entry("AAA"))
    assert p["keep"] is True and p["unknown"] is False                         # GG5's potential alone keeps it
    gone = A.progress("AAA", S, stores=stores(gg5=[rdoc("AAA", setups={})], gg1_fail=True), shared={},
                      entry=entry("AAA"))
    assert gone["unknown"] is False and gone["keep"] is False and gone["source"] == "gajjala"
    _on(monkeypatch)
    g_on = A.progress("AAA", S, stores=stores(gg5=[rdoc("AAA", setups={})], gg1_fail=True), shared={},
                      entry=entry("AAA"))
    assert g_on["unknown"] is True and g_on["keep"] is True                    # a GG1 fault = unknown, kept (ON)


def test_NEGATIVE_the_watch_engine_reads_no_switch_constant_directly():
    """One predicate: the Watch modules read `variant.enabled`, never GC.GAJJALA_1M_ENABLED in code (docstrings may
    name it)."""
    import ast
    import inspect
    for mod in (A, PL, CF, L, BLD, CO):
        tree = ast.parse(inspect.getsource(mod))
        names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        names |= {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        assert "GAJJALA_1M_ENABLED" not in names, mod.__name__
    for mod in (A, PL, CF):
        assert "V.enabled(" in inspect.getsource(mod), mod.__name__
