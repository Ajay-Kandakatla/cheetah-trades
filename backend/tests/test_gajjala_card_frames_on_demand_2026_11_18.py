"""📈 Card ⤢ view — the 1m frame built ON DEMAND for a name not on the 👀 Watch (2026-11-18).

Ajay 2026-11-18, verbatim: "Also I need to keep 1 min charts when I am viewing specific stock".

The 🚩 1-minute page retired today, so its GG1 read doc is no longer written and the card's 1m frame fell back to the
Watch's stored 1m tile only — his Watch is full, so most card names showed no 1m chart. Now, when NEITHER a GG1 doc NOR
a same-session Watch tile has 1m bars, card_frames builds the frame for that ONE name through the Watch's own builder
(`gajjala_watch.build.frames` + `build.tile_update`, the update READ, never written).

Pins: on-demand only when GG1 + Watch are both empty; the Watch tile / GG1 doc still win (the builder never called);
a raising / empty loader → the served empty words, 15m / 5m byte-identical; nothing written anywhere; ONE today fetch
per GET for that symbol only; the real path (`stores=None`) uses the Watch's default loader; every frame serves its
`source`; the route serializes it. NEGATIVES throughout.
"""
from __future__ import annotations

import ast
import functools
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chart_maps import api as API
from chart_maps.gajjala import card_frames as CF
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import variant as V
from chart_maps.gajjala_watch import build as BLD
from chart_maps.gajjala_watch import payload as PL
from tests.test_gajjala_card_frames_2026_11_16 import _g1_doc, _g5_doc, _watch_doc
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_watch_build_2026_11_15 import raw_day

ET = ZoneInfo("America/New_York")
SESSION = "2026-11-13"
S = datetime(2026, 11, 13).date()
IN_RTH = datetime(2026, 11, 13, 15, 30, tzinfo=ET)
SYM = "DPU"
SRC = Path(CF.__file__).read_text()


def _utc(dt):
    return dt.astimezone(timezone.utc)


class Loader:
    """The minute loader's signature; records every call. `mode`: ok | none | raise."""

    def __init__(self, mode="ok"):
        self.mode, self.calls = mode, []

    def __call__(self, msym, day, force=False, include_premarket=True, include_afterhours=False):
        self.calls.append((msym, day, bool(force)))
        if self.mode == "raise":
            raise RuntimeError("minute feed down")
        if self.mode == "none":
            return None
        return raw_day(day, end=(15, 30)) if day == S else raw_day(day)

    def today_fetches(self):
        return [c for c in self.calls if c[2]]


class SpyColl(FakeColl):
    """FakeColl that counts every write verb (none may be called)."""

    def __init__(self, docs=()):
        super().__init__(list(docs))
        self.writes = []

    def _w(self, name):
        def f(*a, **k):
            self.writes.append(name)
            raise AssertionError(f"card view wrote {name}")
        return f

    def __getattribute__(self, name):
        if name in ("update_one", "update_many", "insert_one", "insert_many", "replace_one", "delete_one",
                    "delete_many", "bulk_write", "find_one_and_update"):
            return object.__getattribute__(self, "_w")(name)
        return object.__getattribute__(self, name)


def _stores(g5=None, g1=None, wt=None, fetch=None):
    s5 = ST.GajjalaStore({ST.READS: SpyColl([g5] if g5 else [])})
    s1 = ST.GajjalaStore({ST.READS: SpyColl([g1] if g1 else [])}, variant=V.GG1, shared=s5)
    wt = wt if wt is not None else SpyColl([])
    return (s5, s1, wt) if fetch is None else (s5, s1, wt, fetch)


def _fetch(loader):
    return functools.partial(CF._on_demand_1m, load_day=loader)


class Counting:
    """A 4th-element builder that only counts (the Watch tile / GG1 must win before it is asked)."""

    def __init__(self):
        self.calls = 0

    def __call__(self, *a, **k):
        self.calls += 1
        raise AssertionError("the on-demand builder must not be called")


def _expected_1m(loader):
    F = BLD.frames([SYM], S, IN_RTH, load_day=loader, stats={}, per_name={})
    _flt, upd = BLD.tile_update(SYM, F[SYM], S, IN_RTH, "loaded")
    return upd["$set"]["frames"]["1m"], upd["$set"]["loaded_at"]


# ── the on-demand path ───────────────────────────────────────────────────────────────────────────────────────────
def test_on_demand_builds_the_1m_frame_when_gg1_and_the_watch_are_both_empty():
    ld = Loader()
    g5 = _g5_doc(_utc(IN_RTH - timedelta(seconds=60)))
    out = CF.build(SYM, IN_RTH, stores=_stores(g5, None, fetch=_fetch(ld)))
    ref = CF.build(SYM, IN_RTH, stores=_stores(g5, None))                         # the 3-tuple: no fetch
    f1 = out["frames"][2]
    exp, loaded_at = _expected_1m(Loader())
    assert out["state"] == "ok" and f1["tf"] == "1m"
    assert f1["tile"]["bars"] == exp["bars"] and f1["tile"]["bars"]
    assert f1["tile"]["curves"] == exp["curves"] and f1["tile"]["vol_avg"] == exp["vol_avg"]
    assert f1["empty_text"] is None and f1["stale"] is False and f1["as_of_et"] == "15:30"
    assert f1["source"] == {"kind": CF.SOURCE_ON_DEMAND, "at": PL._to_et(loaded_at).isoformat()}
    assert f1["axis"] is not None and f1["ema_tail"] is not None
    assert f1["tile"]["bars"][-1]["t"] == f"{SESSION} 15:29"                       # closed bars only (settle rule)
    for i in (0, 1):                                                                # 15m / 5m byte-identical
        assert out["frames"][i]["tile"] == ref["frames"][i]["tile"]
        assert out["frames"][i]["source"] == ref["frames"][i]["source"] == {
            "kind": V.GG5.key, "at": PL._to_et(g5["at"]).isoformat()}
    assert out["as_of_et"] == ref["as_of_et"] and out["text"] is None              # the head = the GG5 card's doc
    assert ref["frames"][2]["tile"]["bars"] == [] and ref["frames"][2]["source"] is None


def test_on_demand_frame_rides_the_one_axis_end():
    ld = Loader()
    out = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None, fetch=_fetch(ld)))
    every = [b for f in out["frames"] for b in f["tile"]["bars"]]
    end = BLD.axis_end(SESSION, every)
    assert out["frames"][2]["axis"] == BLD.axis(SESSION, 1, out["frames"][2]["tile"]["bars"], end)


def test_one_today_fetch_per_get_for_that_symbol_only():
    ld = Loader()
    CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None, fetch=_fetch(ld)))
    assert ld.today_fetches() == [(SYM, S, True)]                                  # ONE re-fetch of today
    assert {c[0] for c in ld.calls} == {SYM}                                       # never another name
    assert len(ld.calls) == 2                                                      # + the prior day (the day cache)
    CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None, fetch=_fetch(ld)))
    assert len(ld.today_fetches()) == 2                                            # one more per GET, never a loop


def test_NEGATIVE_no_card_doc_at_all_still_builds_only_the_1m():
    ld = Loader()
    out = CF.build(SYM, IN_RTH, stores=_stores(None, None, fetch=_fetch(ld)))
    assert out["frames"][0]["tile"]["bars"] == [] and out["frames"][1]["tile"]["bars"] == []
    assert out["frames"][0]["source"] is None and out["frames"][1]["source"] is None
    assert out["frames"][2]["tile"]["bars"] and out["text"] is None
    assert len(ld.today_fetches()) == 1


# ── precedence: the Watch tile and the GG1 doc still win ────────────────────────────────────────────────────────────
def test_NEGATIVE_the_watch_tile_still_wins_and_the_builder_is_never_asked():
    c = Counting()
    wd = _watch_doc(_utc(IN_RTH - timedelta(seconds=30)))
    out = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None, wt=SpyColl([wd]), fetch=c))
    ref = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None, wt=SpyColl([wd])))
    assert c.calls == 0 and out == ref
    f1 = out["frames"][2]
    assert f1["tile"]["bars"] == wd["frames"]["1m"]["bars"]
    assert f1["source"] == {"kind": CF.SOURCE_WATCH, "at": PL._to_et(wd["loaded_at"]).isoformat()}


def test_NEGATIVE_a_gg1_doc_still_wins_and_the_builder_is_never_asked():
    c = Counting()
    g1 = _g1_doc(_utc(IN_RTH - timedelta(seconds=30)), last1="15:00")
    out = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), g1, fetch=c))
    assert c.calls == 0 and out["frames"][2]["source"]["kind"] == V.GG1.key
    assert out["frames"][2]["tile"]["bars"][-1]["t"] == f"{SESSION} 15:00"


def test_NEGATIVE_a_prior_session_watch_tile_falls_through_to_on_demand():
    ld = Loader()
    wd = _watch_doc(_utc(IN_RTH - timedelta(days=1)), session="2026-11-12")
    out = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None, wt=SpyColl([wd]), fetch=_fetch(ld)))
    f1 = out["frames"][2]
    assert f1["source"]["kind"] == CF.SOURCE_ON_DEMAND and f1["tile"]["bars"] != wd["frames"]["1m"]["bars"]
    assert len(ld.today_fetches()) == 1


# ── fail open ──────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("mode", ["raise", "none"])
def test_NEGATIVE_a_failed_or_empty_fetch_serves_the_empty_words_and_15m_5m_intact(mode):
    ld = Loader(mode)
    g5 = _g5_doc(_utc(IN_RTH))
    out = CF.build(SYM, IN_RTH, stores=_stores(g5, None, fetch=_fetch(ld)))
    ref = CF.build(SYM, IN_RTH, stores=_stores(g5, None))
    assert out == ref                                                              # byte-identical to no fetch
    f1 = out["frames"][2]
    assert out["state"] == "ok" and f1["tile"]["bars"] == [] and f1["source"] is None
    assert f1["empty_text"] == V.word("card_1m_empty", V.GG1, sym=SYM)
    assert out["frames"][0]["tile"]["bars"] and out["frames"][1]["tile"]["bars"]
    assert len(ld.calls) >= 1


def test_NEGATIVE_a_raising_watch_builder_never_breaks_the_view(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("builder down")
    monkeypatch.setattr(CF.BLD, "frames", boom)
    assert CF._on_demand_1m(SYM, S, IN_RTH) == (None, None)
    monkeypatch.setattr(CF.BLD, "frames", lambda *a, **k: {SYM: object()})
    monkeypatch.setattr(CF.BLD, "tile_update", boom)
    assert CF._on_demand_1m(SYM, S, IN_RTH) == (None, None)
    out = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None, fetch=CF._on_demand_1m))
    assert out["state"] == "ok" and out["frames"][2]["tile"]["bars"] == []


def test_NEGATIVE_retired_switch_on_with_no_bars_serves_the_old_words(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_1M_ENABLED", True)
    out = CF.build(SYM, IN_RTH, stores=_stores(_g5_doc(_utc(IN_RTH)), None, fetch=_fetch(Loader("none"))))
    assert out["frames"][2]["empty_text"] == CF.EMPTY_TEXT.format(minutes=1, sym=SYM)


# ── never writes ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_never_writes_the_watch_tiles_or_any_store(monkeypatch):
    def no_write(*a, **k):
        raise AssertionError("BLD.write must never be called by the card view")
    monkeypatch.setattr(CF.BLD, "write", no_write)
    wt = SpyColl([])
    st = _stores(_g5_doc(_utc(IN_RTH)), None, wt=wt, fetch=_fetch(Loader()))
    out = CF.build(SYM, IN_RTH, stores=st)
    assert out["frames"][2]["tile"]["bars"] and wt.writes == [] and wt.docs == {}
    calls = [n.func.attr for n in ast.walk(ast.parse(SRC)) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == "BLD"]
    assert "write" not in calls and calls.count("frames") == 1 and calls.count("tile_update") == 1


def test_NEGATIVE_module_adds_no_seat_and_types_no_loader():
    assert not re.search(r"owner_symbols|COLL_LIST|gajjala_watch_list|AUTO\.|add_symbol", SRC)
    assert not re.search(r"load_intraday|Massive|update_one|upsert|insert", SRC)


# ── which builder runs ─────────────────────────────────────────────────────────────────────────────────────────────
def test_fetcher_real_path_only_and_a_short_tuple_never_fetches():
    assert CF._fetcher(None) is CF._on_demand_1m
    s = _stores()
    assert CF._fetcher(s[:2]) is None and CF._fetcher(s[:3]) is None
    f = _fetch(Loader())
    assert CF._fetcher((*s[:3], f)) is f
    assert CF._fetcher((*s[:3], "not callable")) is None


def test_real_path_uses_the_watch_default_loader(monkeypatch):
    from daytrading import data as dt_data
    ld = Loader()
    monkeypatch.setattr(dt_data, "load_intraday", ld)
    s5 = ST.GajjalaStore({ST.READS: SpyColl([_g5_doc(_utc(IN_RTH))])})
    s1 = ST.GajjalaStore({ST.READS: SpyColl([])}, variant=V.GG1, shared=s5)
    wt = SpyColl([])
    monkeypatch.setattr(ST, "default", lambda: s5)
    monkeypatch.setattr(ST, "for_variant", lambda v: s1)
    monkeypatch.setattr(CF.WCOLLS, "colls", lambda db=None: {"tiles": wt})
    out = CF.build(SYM, IN_RTH)
    assert out["frames"][2]["source"]["kind"] == CF.SOURCE_ON_DEMAND
    assert ld.today_fetches() == [(SYM, S, True)] and wt.writes == []


def test_route_serves_the_on_demand_frame_json_clean(monkeypatch):
    real = CF.build
    st = _stores(_g5_doc(_utc(IN_RTH)), None, fetch=_fetch(Loader()))
    monkeypatch.setattr(CF, "build", lambda symbol, now=None, **_k: real(symbol, IN_RTH, stores=st))
    app = FastAPI()
    app.include_router(API.router)
    r = TestClient(app).get(f"{CF.API_BASE}/{SYM}")
    assert r.status_code == 200
    body = json.loads(r.text)
    f1 = body["frames"][2]
    assert f1["source"]["kind"] == "on_demand" and f1["source"]["at"].startswith("2026-11-13T15:30")
    assert f1["tile"]["bars"] and "NaN" not in r.text
