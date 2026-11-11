"""⚡ live_hub ↔ chart_maps.gajjala.break_watch wiring (entry spec §3.1 / §5.1 B10, N10, N13 — WP-BRK, 2026-11-11).

Ajay 2026-11-11: "Here is how he enters please tell me to enter based on this". The hub asks break_watch for a refresh
on the GG5 pass-pointer change and on the first poll of a day — NON-BLOCKING, on break_watch's OWN "gg-brk" worker,
never queued behind a lane order on the hub's worker [C5]; break_watch's symbols join the watch set; a print of one of
them reaches break_watch.on_print between the lane and the screen, each fenced.
"""
from __future__ import annotations

import sys
import threading
import types
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import live_feed
import live_hub as H
from chart_maps.gajjala import break_watch as BW
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import variant as V

ET = ZoneInfo("America/New_York")
DAY = "2026-11-11"
T0 = datetime(2026, 11, 11, 10, 6, 10, tzinfo=ET)
GG5_PASSES = ST.for_variant(V.GG5).physical(ST.PASSES)
GG1_PASSES = ST.for_variant(V.GG1).physical(ST.PASSES)


class _Rec:
    def __init__(self, order):
        self.calls, self.order = [], order

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        def f(*a):
            self.calls.append((name,) + a)
            if name == "on_print":
                self.order.append(self.tag)
        return f


@pytest.fixture
def hub(monkeypatch):
    H.reset()
    BW.reset()
    order: list = []
    stream, events = _Rec(order), _Rec(order)
    stream.tag, events.tag = "lane", "screen"
    m_stream = types.ModuleType("trading.gajjala_stream")
    m_events = types.ModuleType("chart_maps.gajjala.live_events")
    for fn in ("on_print", "on_new_aplus", "on_bar_close"):
        setattr(m_stream, fn, getattr(stream, fn))
    for fn in ("on_print", "on_pass", "on_lane_change", "flush"):
        setattr(m_events, fn, getattr(events, fn))
    monkeypatch.setitem(sys.modules, H.STREAM_MOD, m_stream)
    monkeypatch.setitem(sys.modules, H.EVENTS_MOD, m_events)
    refreshes: list = []
    monkeypatch.setattr(BW, "request_refresh", lambda day, now=None: refreshes.append((day, now)))
    watch, unwatch = [], []
    monkeypatch.setattr(live_feed, "watch", lambda syms: watch.append(list(syms)) or len(syms))
    monkeypatch.setattr(live_feed, "unwatch", lambda syms: unwatch.append(list(syms)) or len(syms))
    monkeypatch.setattr(H, "_running", True)
    monkeypatch.setenv("MASSIVE_WS_ENABLED", "true")
    monkeypatch.setattr(GC, "GAJJALA_BREAK_PUSH_MODE", "shadow")
    yield types.SimpleNamespace(order=order, stream=stream, events=events, refreshes=refreshes, watch=watch)
    H.reset()
    BW.reset()


def world(gg5="p1", gg1="q1", day=DAY):
    return {"day": day, "aplus": [], "lane": [], "cfg": {"armed": False}, "mode": "paper",
            "passes": {GG5_PASSES: {"pass_id": gg5, "finished_at": T0}, GG1_PASSES: {"pass_id": gg1, "finished_at": T0}}}


def pr(sym, p=1.18):
    return {"sym": sym, "p": p, "s": 100, "c": [], "t_ms": int(T0.timestamp() * 1000), "recv": T0.timestamp(),
            "trfi": False}


def test_constants():
    assert H.BREAK_MOD == "chart_maps.gajjala.break_watch" == BW.__name__
    assert {"brk_syms", "brk_day"} <= set(H._fresh_view())


def test_B10_first_poll_and_the_gg5_pointer_change_request_a_refresh(hub):
    H.apply(world(), T0)
    assert hub.refreshes == [(DAY, T0)]                          # the first poll of the day
    H.apply(world(), T0)
    assert len(hub.refreshes) == 1                               # nothing changed → no refresh
    H.apply(world(gg1="q2"), T0)
    assert len(hub.refreshes) == 1                               # NEGATIVE: the 1-minute page's pointer is not ours
    H.apply(world(gg5="p2"), T0)
    assert hub.refreshes[-1] == (DAY, T0) and len(hub.refreshes) == 2
    H.apply(world(gg5="p2", day="2026-11-12"), T0)
    assert hub.refreshes[-1][0] == "2026-11-12"                  # a new day → a refresh


def test_B10_refresh_runs_on_gg_brk_while_the_hub_worker_is_blocked(monkeypatch):
    H.reset()
    BW.reset()
    gate, started, ran = threading.Event(), threading.Event(), threading.Event()
    seen = {}

    def lane_job():
        started.set()
        gate.wait(10)

    def fake_refresh(day, now_et=None):
        seen["thread"] = threading.current_thread().name
        seen["day"] = day
        ran.set()
        return 0
    monkeypatch.setattr(BW, "refresh", fake_refresh)
    monkeypatch.setattr(BW, "symbols", lambda: frozenset())
    monkeypatch.setattr(live_feed, "watch", lambda syms: len(syms))
    monkeypatch.setattr(live_feed, "unwatch", lambda syms: len(syms))
    for mod in (H.STREAM_MOD, H.EVENTS_MOD):
        m = types.ModuleType(mod)
        for fn in ("on_print", "on_new_aplus", "on_bar_close", "on_pass", "on_lane_change", "flush"):
            setattr(m, fn, lambda *a: None)
        monkeypatch.setitem(sys.modules, mod, m)
    try:
        H.submit(lane_job)                                       # the hub's ONE worker is now busy
        assert started.wait(5)
        H.apply(world(), T0)
        assert ran.wait(5), "refresh queued behind the lane job"
        assert seen["thread"].startswith("gg-brk") and seen["day"] == DAY
        src = open(BW.__file__, encoding="utf-8").read()
        assert "_submit_consumer" not in src and "live_hub.submit" not in src
    finally:
        gate.set()
        H.reset()
        BW.reset()


def test_B10_the_watch_set_includes_break_watch_symbols(hub, monkeypatch):
    monkeypatch.setattr(BW, "symbols", lambda: frozenset({"BRK"}))
    H.apply(world(), T0)
    assert "BRK" in H.watched() and ["BRK"] in hub.watch
    assert H._view["brk_syms"] == frozenset({"BRK"})
    monkeypatch.setattr(BW, "symbols", lambda: frozenset())
    H.apply(world(), T0)
    assert "BRK" not in H.watched()


def test_B10_a_print_reaches_break_watch_between_the_lane_and_the_screen(hub, monkeypatch):
    got = []
    monkeypatch.setattr(BW, "on_print", lambda p: (got.append(p), hub.order.append("break")))
    monkeypatch.setattr(BW, "symbols", lambda: frozenset({"ABC"}))
    H.apply(world(), T0)
    H._view["lane_syms"] = frozenset({"ABC"})
    assert H.register_interest("gajjala", ["ABC"])["on"] is True
    H.on_print(pr("ABC"))
    assert hub.order == ["lane", "break", "screen"]
    assert got and got[0]["sym"] == "ABC" and got[0]["kind"] == "regular"


def test_NEGATIVE_a_filtered_print_never_reaches_break_watch(hub, monkeypatch):
    got = []
    monkeypatch.setattr(BW, "on_print", lambda p: got.append(p))
    monkeypatch.setattr(BW, "symbols", lambda: frozenset({"ABC"}))
    H.apply(world(), T0)
    from orderflow import tape as OT
    bad = pr("ABC")
    bad["c"] = sorted(OT.AUCTION_OPEN_CONDITIONS)[:1]          # an opening print → not "regular"
    assert OT.print_kind(bad["c"]) not in H.PRINT_KINDS
    H.on_print(bad)
    H.on_print(pr("XYZ"))                                        # not a break_watch symbol
    assert got == []


def test_N10_mode_off_adds_nothing_to_the_watch(hub, monkeypatch):
    BW._syms = frozenset({"BRK"})
    monkeypatch.setattr(GC, "GAJJALA_BREAK_PUSH_MODE", "off")
    H.apply(world(), T0)
    assert "BRK" not in H.watched() and H._view["brk_syms"] == frozenset()
    got = []
    monkeypatch.setattr(BW, "on_print", lambda p: got.append(p))
    H.on_print(pr("BRK"))
    assert got == []


def test_N13_a_raising_break_watch_never_stops_the_lane_or_the_screen(hub, monkeypatch):
    def boom(p):
        hub.order.append("break")
        raise RuntimeError("boom")
    monkeypatch.setattr(BW, "on_print", boom)
    monkeypatch.setattr(BW, "symbols", lambda: frozenset({"ABC"}))
    H.apply(world(), T0)
    H._view["lane_syms"] = frozenset({"ABC"})
    H.register_interest("gajjala", ["ABC"])
    H.on_print(pr("ABC"))
    assert hub.order == ["lane", "break", "screen"]


def test_N13_a_raising_symbols_or_refresh_never_stops_the_poll(hub, monkeypatch):
    monkeypatch.setattr(BW, "symbols", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(BW, "request_refresh", lambda *a: (_ for _ in ()).throw(RuntimeError("y")))
    H.apply(world(), T0)
    assert H._view["brk_syms"] == frozenset() and hub.events.calls      # flush still ran


def test_NEGATIVE_a_missing_break_watch_module_is_skipped(hub, monkeypatch):
    monkeypatch.setattr(H, "_mod", lambda name: None if name == H.BREAK_MOD else sys.modules.get(name))
    H.apply(world(), T0)
    assert H._view["brk_syms"] == frozenset()
    H._view["lane_syms"] = frozenset({"ABC"})
    H.on_print(pr("ABC"))
    assert hub.order == ["lane"]
