"""GG LIVE WP-A (spec §3.2, 2026-11-09) — the live hub core: today's pushed A+, the lane doc view, pass pointers, the
gate snapshot (no Alpaca call), the watch set, the bar clock, ONE print filter before either consumer, per-variant
interest. The consumers (`trading.gajjala_stream`, `chart_maps.gajjala.live_events`) are stubbed here — they belong
to WP-B / WP-D.
"""
from __future__ import annotations

import asyncio
import sys
import time  # noqa: F401
import types
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import live_feed
import live_hub as H
from chart_maps import live_card
from chart_maps.gajjala import constants as GC
from orderflow import tape as OT
from trading import gajjala_entry as GE

ET = ZoneInfo("America/New_York")
DAY = "2026-11-10"                                   # a Tuesday, a trading day
T0 = datetime(2026, 11, 10, 10, 3, 0, tzinfo=ET)


# ── fakes ───────────────────────────────────────────────────────────────────────────────────────────────────────
def _match(doc, q):
    for k, cond in q.items():
        v = doc.get(k)
        if isinstance(cond, dict):
            for op, x in cond.items():
                if op == "$gte" and not (v is not None and v >= x):
                    return False
                if op == "$lt" and not (v is not None and v < x):
                    return False
                if op == "$in" and v not in x:
                    return False
        elif v != cond:
            return False
    return True


class _Coll:
    def __init__(self, db, name, docs=()):
        self.db, self.name = db, name
        self.docs = [dict(d) for d in docs]

    def find(self, q=None, proj=None):
        self.db.calls.append((self.name, "find", q))
        return [dict(d) for d in self.docs if _match(d, q or {})]

    def find_one(self, q=None, proj=None):
        self.db.calls.append((self.name, "find_one", q))
        for d in self.docs:
            if _match(d, q or {}):
                return dict(d)
        return None


class _DB:
    def __init__(self):
        self.calls = []
        self.colls = {}

    def coll(self, name):
        if name not in self.colls:
            self.colls[name] = _Coll(self, name)
        return self.colls[name]


class _Rec:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        def f(*a):
            self.calls.append((name,) + a)
        return f

    def of(self, name):
        return [c[1:] for c in self.calls if c[0] == name]


@pytest.fixture
def hub(monkeypatch):
    H.reset()
    db = _DB()
    stream, events = _Rec(), _Rec()
    m_stream = types.ModuleType("trading.gajjala_stream")
    m_events = types.ModuleType("chart_maps.gajjala.live_events")
    for fn in ("on_print", "on_new_aplus", "on_bar_close"):
        setattr(m_stream, fn, getattr(stream, fn))
    for fn in ("on_print", "on_pass", "on_lane_change", "flush"):
        setattr(m_events, fn, getattr(events, fn))
    monkeypatch.setitem(sys.modules, H.STREAM_MOD, m_stream)
    monkeypatch.setitem(sys.modules, H.EVENTS_MOD, m_events)
    monkeypatch.setattr(H, "_coll", db.coll)
    monkeypatch.setattr(H, "_get_config", lambda: {"armed": False})
    monkeypatch.setattr(H, "_broker_mode", lambda: "paper")
    submitted = []

    def inline(fn, *a, **k):
        submitted.append(fn.__name__ if hasattr(fn, "__name__") else fn)
        fn(*a, **k)
    monkeypatch.setattr(H, "submit", inline)
    watch, unwatch = [], []
    monkeypatch.setattr(live_feed, "watch", lambda syms: watch.append(list(syms)) or len(syms))
    monkeypatch.setattr(live_feed, "unwatch", lambda syms: unwatch.append(list(syms)) or len(syms))
    monkeypatch.setattr(H, "_running", True)
    monkeypatch.setenv("MASSIVE_WS_ENABLED", "true")         # the feed is on (register_interest refuses an OFF feed)
    ns = types.SimpleNamespace(db=db, stream=stream, events=events, watch=watch, unwatch=unwatch,
                               submitted=submitted)
    yield ns
    H.reset()


def _alert(_id, sym="ABC", state="pushed", claimed="2026-11-10T15:02:10+00:00"):
    return {"_id": _id, "symbol": sym, "trigger": 2.5, "stop": 2.3, "setup": "flag", "claimed_at": claimed,
            "state": state}


def _pr(sym, c=None, p=2.6):
    return {"sym": sym, "p": p, "s": 100, "c": list(c or []), "t_ms": 1, "recv": H.time.time(), "trfi": False}


# ── constants (derived, never retyped) ──────────────────────────────────────────────────────────────────────────
def test_constants_are_derived():
    assert H.INTEREST_TTL_SEC == 2 * live_card.CARD_LIVE_SEC == 60
    assert H.INTEREST_MAX == GC.TILE_LIMIT_MAX == 80
    assert H.BAR_CLOSE_OFFSET_SEC == GC.BAR_SETTLE_SEC == 30
    assert H.BAR_CLOCK_LATE_MAX_SEC == 5 * H.HUB_POLL_SEC
    assert H.LANE_WATCH_STATES == ("waiting",) + GE._LIVE_STATES
    assert H.PRINT_KINDS == ("regular",) and set(H.PRINT_KINDS) <= set(OT.PRINT_KINDS)


# ── today's pushed A+ ───────────────────────────────────────────────────────────────────────────────────────────
def test_a_new_pushed_gg_id_reaches_on_new_aplus_once(hub):
    alerts = hub.db.coll("gajjala_alerts")
    alerts.docs.append(_alert(f"GG:{DAY}|OLD|flag", "OLD"))
    assert H.tick(T0)
    assert hub.stream.of("on_new_aplus") == []                  # NEG: on file at the first read → seeded, no replay
    alerts.docs.append(_alert(f"GG:{DAY}|NEW|flag", "NEW"))
    H.tick(T0 + timedelta(seconds=1))
    H.tick(T0 + timedelta(seconds=2))
    calls = hub.stream.of("on_new_aplus")
    assert len(calls) == 1
    rows, now = calls[0]
    assert [r["_id"] for r in rows] == [f"GG:{DAY}|NEW|flag"] and now.tzinfo is not None


def test_NEG_shadow_suppressed_and_yesterday_rows_never_reach_on_new_aplus(hub):
    alerts = hub.db.coll("gajjala_alerts")
    H.tick(T0)
    alerts.docs += [
        _alert(f"SHADOW:GG:{DAY}|SHD|flag", "SHD", state="shadow"),
        _alert(f"GG:{DAY}|SUP|flag#suppressed_first15", "SUP", state="suppressed_first15"),
        _alert(f"GG:{DAY}|HSH|flag#late", "HSH", state="pushed"),
        _alert("GG:2026-11-09|OLDDAY|flag", "OLDDAY"),
        _alert(f"GG:{DAY}|CLM|flag", "CLM", state="claimed"),
    ]
    H.tick(T0 + timedelta(seconds=1))
    assert hub.stream.of("on_new_aplus") == []
    assert H._view["aplus_syms"] == frozenset()


def test_aplus_symbols_join_the_watch_set(hub):
    hub.db.coll("gajjala_alerts").docs.append(_alert(f"GG:{DAY}|ABC|flag", "ABC"))
    H.tick(T0)
    assert hub.watch == [["ABC"]] and H.watched() == {"ABC"}


# ── closed day / outside the window ─────────────────────────────────────────────────────────────────────────────
def test_NEG_closed_day_is_idle_with_no_mongo_query(hub):
    assert H.tick(datetime(2026, 11, 14, 10, 0, tzinfo=ET)) is False        # Saturday
    assert H.tick(datetime(2026, 11, 26, 10, 0, tzinfo=ET)) is False        # Thanksgiving
    assert H.tick(datetime(2026, 11, 10, 3, 59, tzinfo=ET)) is False        # before GC.PASS_OPEN_ET
    assert H.tick(datetime(2026, 11, 10, 20, 5, tzinfo=ET)) is False        # at GC.PASS_CLOSE_ET
    assert hub.db.calls == []
    assert H.tick(datetime(2026, 11, 10, 4, 0, tzinfo=ET)) is True          # the window opens
    assert hub.db.calls


def test_run_loop_idles_on_a_closed_day_without_reading(hub, monkeypatch):
    sleeps = []

    async def fake_sleep(s):
        sleeps.append(s)
        if len(sleeps) >= 3:
            raise asyncio.CancelledError()

    monkeypatch.setattr(H, "_now_et", lambda: datetime(2026, 11, 14, 10, 0, tzinfo=ET))
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(H.run(sleep=fake_sleep))
    assert sleeps == [H.HUB_IDLE_SEC] * 3 and hub.db.calls == []


def test_NEG_a_failing_read_never_stops_the_loop(hub, monkeypatch):
    n = {"reads": 0}
    sleeps = []

    def bad_read(now):
        n["reads"] += 1
        raise RuntimeError("mongo down")

    async def fake_sleep(s):
        sleeps.append(s)
        if len(sleeps) >= 3:
            raise asyncio.CancelledError()

    monkeypatch.setattr(H, "_now_et", lambda: T0)
    monkeypatch.setattr(H, "read_world", bad_read)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(H.run(sleep=fake_sleep))
    assert n["reads"] == 3 and sleeps == [H.HUB_POLL_SEC] * 3
    assert H._running is False


# ── the bar clock ───────────────────────────────────────────────────────────────────────────────────────────────
def _at(h, m, s):
    return datetime(2026, 11, 10, h, m, s, tzinfo=ET)


def test_bar_clock_fires_once_at_boundary_plus_settle(hub):
    H.tick(_at(10, 3, 0))
    H.tick(_at(10, 5, 29))
    assert hub.stream.of("on_bar_close") == []                  # NEG: not at + 29 s
    H.tick(_at(10, 5, 30))
    H.tick(_at(10, 5, 31))
    H.tick(_at(10, 5, 34))
    assert hub.stream.of("on_bar_close") == [(_at(10, 5, 30),)]   # NEG: never twice
    H.tick(_at(10, 10, 30))
    assert len(hub.stream.of("on_bar_close")) == 2


def test_NEG_a_boundary_missed_by_host_sleep_is_skipped(hub):
    H.tick(_at(10, 3, 0))
    H.tick(_at(10, 12, 0))                                      # slept through 10:05:30 and 10:10:30
    assert hub.stream.of("on_bar_close") == []
    H.tick(_at(10, 15, 30))
    assert hub.stream.of("on_bar_close") == [(_at(10, 15, 30),)]


def test_bar_clock_late_within_five_polls_still_fires(hub):
    H.tick(_at(10, 3, 0))
    H.tick(_at(10, 5, 35))
    assert hub.stream.of("on_bar_close") == [(_at(10, 5, 35),)]


def test_next_fire_grid():
    assert H._next_fire(_at(10, 3, 12)) == _at(10, 5, 30)
    assert H._next_fire(_at(10, 5, 29)) == _at(10, 5, 30)
    assert H._next_fire(_at(10, 5, 30)) == _at(10, 10, 30)      # strictly after
    assert H._next_fire(_at(19, 58, 0)) == _at(20, 0, 30)


# ── the gate snapshot ───────────────────────────────────────────────────────────────────────────────────────────
def test_NEG_zero_broker_clock_calls_from_the_hub_over_100_prints(hub, monkeypatch):
    from trading import broker

    class _Brk:
        clocks = 0

        @staticmethod
        def mode():
            return "paper"

        @classmethod
        def clock(cls):
            cls.clocks += 1
            return {"is_open": True}

    monkeypatch.setattr(broker, "get_broker", lambda: _Brk)
    monkeypatch.setattr(H, "_broker_mode", lambda: broker.mode())
    hub.db.coll("gajjala_lane").docs.append({"_id": f"GG:{DAY}|ABC|flag", "date": DAY, "symbol": "ABC",
                                             "state": "waiting", "trigger": 2.5, "stop": 2.3})
    H.tick(_at(10, 3, 0))
    for _ in range(100):
        H.on_print(_pr("ABC"))
    assert _Brk.clocks == 0
    assert len(hub.stream.of("on_print")) == 100
    assert all(c[2] is True for c in hub.stream.of("on_print"))      # gate_ok in the window, paper, lane on


def test_NEG_gate_is_false_before_the_entry_window_and_on_a_live_broker(hub, monkeypatch):
    H.tick(_at(9, 40, 0))
    assert H.gate_ok() is False                                 # before WINDOW_OPEN_ET 09:45
    H.tick(_at(10, 0, 0))
    assert H.gate_ok() is True
    monkeypatch.setattr(H, "_broker_mode", lambda: "live")
    H.tick(_at(10, 0, 1))
    assert H.gate_ok() is False                                 # paper only
    monkeypatch.setattr(H, "_broker_mode", lambda: "paper")
    monkeypatch.setattr(H, "_get_config", lambda: {"gajjala_entry": False})
    H.tick(_at(10, 0, 2))
    assert H.gate_ok() is False                                 # lane switched off


# ── lane docs ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_lane_doc_view_and_change_nudge(hub):
    lane = hub.db.coll("gajjala_lane")
    lane.docs += [{"_id": "a", "date": DAY, "symbol": "aaa", "state": "waiting", "trigger": 1, "stop": 0.9,
                   "updated_at": "t1"},
                  {"_id": "b", "date": DAY, "symbol": "BBB", "state": "closed", "updated_at": "t1"},
                  {"_id": "c", "date": "2026-11-09", "symbol": "CCC", "state": "open", "updated_at": "t1"}]
    H.tick(_at(10, 0, 0))
    assert set(H.doc_view()) == {"a"} and H.doc_view()["a"]["symbol"] == "AAA"
    assert H.watched() == {"AAA"}
    assert hub.events.of("on_lane_change") == []                # NEG: the first read is the baseline
    H.tick(_at(10, 0, 1))
    assert hub.events.of("on_lane_change") == []                # NEG: nothing changed
    lane.docs[0]["state"] = "ordered"
    lane.docs[0]["updated_at"] = "t2"
    H.tick(_at(10, 0, 2))
    assert hub.events.of("on_lane_change") == [(DAY, _at(10, 0, 2))]
    assert H.doc_view()["a"]["state"] == "ordered"


# ── pass pointers ───────────────────────────────────────────────────────────────────────────────────────────────
def test_pass_nudges_per_variant(hub):
    g5 = hub.db.coll("gajjala_passes")
    g1 = hub.db.coll("gajjala_1m_passes")
    g5.docs.append({"_id": "latest", "pass_id": f"{DAY}|10:01", "finished_at": datetime(2026, 11, 10, 15, 1, 12)})
    g1.docs.append({"_id": "latest", "pass_id": f"{DAY}|10:02", "finished_at": datetime(2026, 11, 10, 15, 2, 40)})
    H.tick(_at(10, 3, 0))
    assert hub.events.of("on_pass") == []                       # NEG: baseline
    g5.docs[0].update(pass_id=f"{DAY}|10:06", finished_at=datetime(2026, 11, 10, 15, 6, 11))
    H.tick(_at(10, 6, 20))
    calls = hub.events.of("on_pass")
    assert [c[0] for c in calls] == ["gajjala", "gajjala_audited"]          # 🧪 borrows GG5's passes
    assert all(c[1] == f"{DAY}|10:06" for c in calls)
    assert calls[0][2] == datetime(2026, 11, 10, 15, 6, 11).replace(tzinfo=ZoneInfo("UTC")).timestamp()
    g1.docs[0].update(pass_id=f"{DAY}|10:07", finished_at=datetime(2026, 11, 10, 15, 7, 40))
    H.tick(_at(10, 7, 41))
    assert [c[0] for c in hub.events.of("on_pass")][2:] == ["gajjala_1m"]   # NEG: never the 5-minute variants


# ── ONE print filter before either consumer ─────────────────────────────────────────────────────────────────────
def _lane_and_interest(hub, sym="ABC"):
    hub.db.coll("gajjala_lane").docs.append({"_id": f"GG:{DAY}|{sym}|flag", "date": DAY, "symbol": sym,
                                             "state": "waiting", "trigger": 2.5, "stop": 2.3})
    assert H.register_interest("gajjala", [sym], {sym: {"trigger": 2.5, "stop": 2.3, "tf": "5m"}})["on"]
    H.tick(_at(10, 3, 0))


def test_NEG_a_non_flow_print_reaches_neither_consumer(hub):
    _lane_and_interest(hub)
    pr = _pr("ABC", c=[22])
    H.on_print(pr)
    assert hub.stream.of("on_print") == [] and hub.events.of("on_print") == []
    assert "kind" not in pr


def test_an_odd_lot_print_reaches_both_consumers(hub):
    _lane_and_interest(hub)
    H.on_print(_pr("ABC", c=[37]))
    (s_pr, view, ok), = hub.stream.of("on_print")
    assert s_pr["kind"] == "regular" and set(view) == {f"GG:{DAY}|ABC|flag"}
    (variant, e_pr, level), = hub.events.of("on_print")
    assert variant == "gajjala" and e_pr is s_pr and level == {"trigger": 2.5, "stop": 2.3, "tf": "5m"}


def test_NEG_a_print_on_an_unwatched_symbol_reaches_nobody(hub):
    _lane_and_interest(hub)
    H.on_print(_pr("ZZZ"))
    assert hub.stream.of("on_print") == [] and hub.events.of("on_print") == []


def test_NEG_a_raising_consumer_never_stops_the_hub(hub, monkeypatch):
    _lane_and_interest(hub)

    def boom(*a):
        raise RuntimeError("consumer bug")

    monkeypatch.setattr(sys.modules[H.STREAM_MOD], "on_print", boom)
    monkeypatch.setattr(sys.modules[H.EVENTS_MOD], "flush", boom)
    H.on_print(_pr("ABC"))                                       # no raise
    assert len(hub.events.of("on_print")) == 1                   # the other consumer still ran
    assert H.tick(_at(10, 3, 1)) is True                         # a raising flush does not stop the poll


def test_NEG_a_missing_consumer_module_is_skipped(hub, monkeypatch):
    monkeypatch.delitem(sys.modules, H.STREAM_MOD)
    monkeypatch.setattr(H, "_mod", lambda name: None if name == H.STREAM_MOD else sys.modules.get(name))
    _lane_and_interest(hub)
    H.on_print(_pr("ABC"))
    assert len(hub.events.of("on_print")) == 1


# ── interest ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_interest_is_keyed_per_variant(hub):
    l5 = {"trigger": 2.5, "stop": 2.3, "tf": "5m"}
    l1 = {"trigger": 2.45, "stop": 2.4, "tf": "1m"}
    assert H.register_interest("gajjala", ["ABC"], {"ABC": l5})["on"]
    assert H.register_interest("gajjala_1m", ["abc"], {"abc": l1})["on"]
    assert H.interest_of("gajjala", "ABC")["level"] == l5        # NEG: last writer never wins
    assert H.interest_of("gajjala_1m", "ABC")["level"] == l1
    H.tick(_at(10, 3, 0))
    H.on_print(_pr("ABC"))
    assert sorted((c[0], c[2]["tf"]) for c in hub.events.of("on_print")) == [("gajjala", "5m"), ("gajjala_1m", "1m")]


def test_variant_key_normalizes_to_the_tab(hub):
    assert H.register_interest("gga", ["ABC"])["on"]
    assert H.interest_of("gajjala_audited", "ABC") is not None


def test_NEG_unknown_variant_is_off(hub):
    out = H.register_interest("sepa", ["ABC"])
    assert out["on"] is False and isinstance(out["word"], str) and out["word"]
    assert H._interest == {}


def test_NEG_hub_not_running_is_off(hub, monkeypatch):
    monkeypatch.setattr(H, "_running", False)
    assert H.register_interest("gajjala", ["ABC"])["on"] is False


def test_NEG_the_81st_symbol_of_a_variant_is_refused_never_cut(hub):
    syms = [f"S{i:02d}" for i in range(H.INTEREST_MAX)]
    assert H.register_interest("gajjala", syms)["on"] is True
    out = H.register_interest("gajjala", ["XTRA"])
    assert out["on"] is False and out["refused"] == ["XTRA"]
    assert H.interest_of("gajjala", "XTRA") is None and H.interest_of("gajjala", "S00") is not None
    assert H.register_interest("gajjala_1m", ["XTRA"])["on"] is True          # the cap is per variant
    assert H.register_interest("gajjala", ["S05"])["on"] is True              # a renewal is never refused


def test_interest_ttl_expiry_unwatches_but_a_tracked_symbol_stays_subscribed(hub, monkeypatch):
    clock = {"t": 1_000_000.0}
    monkeypatch.setattr(H.time, "time", lambda: clock["t"])
    H.register_interest("gajjala", ["UIX"])
    H.tick(_at(10, 3, 0))
    assert hub.watch == [["UIX"]]
    clock["t"] += H.INTEREST_TTL_SEC - 1
    H.tick(_at(10, 3, 1))
    assert hub.unwatch == []                                      # NEG: alive one second before the TTL
    clock["t"] += 2
    H.tick(_at(10, 3, 2))
    assert hub.unwatch == [["UIX"]] and "UIX" not in H.watched()
    assert H.interest_of("gajjala", "UIX") is None


def test_NEG_unwatch_of_an_expired_symbol_the_ui_tracks_sends_no_unsubscribe(monkeypatch):
    """The hub's unwatch rides live_feed's ONE queue; the pump re-checks UI-tracked at send time."""
    q = []
    monkeypatch.setattr(live_feed, "_queue", type("Q", (), {"put_nowait": staticmethod(q.append)})())
    monkeypatch.setattr(live_feed, "_subscribed_t", {"UIX"})
    monkeypatch.setattr(live_feed, "_views", {"tracked": None, "hub": H.watched})
    H.reset()
    live_feed.unwatch(["UIX"])
    sent = []

    class _WS:
        async def send(self, m):
            sent.append(m)

    for item in q:
        assert asyncio.run(live_feed._send_control(_WS(), item, {"UIX"})) is None
    assert sent == [] and "UIX" in live_feed._subscribed_t


def test_watched_is_the_same_live_set(hub):
    a = H.watched()
    hub.db.coll("gajjala_alerts").docs.append(_alert(f"GG:{DAY}|ABC|flag", "ABC"))
    H.tick(T0)
    assert H.watched() is a and "ABC" in a


def test_flush_runs_every_active_poll(hub):
    H.tick(_at(10, 3, 0))
    H.tick(_at(10, 3, 1))
    assert hub.events.of("flush") == [(_at(10, 3, 0),), (_at(10, 3, 1),)]


def test_the_audited_tab_name_is_accepted_with_its_own_level(hub):
    la = {"trigger": 3.1, "stop": 2.9, "tf": "5m"}
    l5 = {"trigger": 3.0, "stop": 2.8, "tf": "5m"}
    assert H.register_interest("gajjala_audited", ["ABC"], {"ABC": la})["on"] is True
    assert H.register_interest("gajjala", ["ABC"], {"ABC": l5})["on"] is True
    assert H.interest_of("gajjala_audited", "ABC")["level"] == la
    H.tick(_at(10, 3, 0))
    H.on_print(_pr("ABC"))
    got = {c[0]: c[2] for c in hub.events.of("on_print")}
    assert got == {"gajjala_audited": la, "gajjala": l5}


def test_NEG_an_unknown_tab_name_is_off(hub):
    assert H.register_interest("gajjala_5m", ["ABC"])["on"] is False
    assert H.register_interest("", ["ABC"])["on"] is False
    assert H._interest == {}


def test_submit_is_the_public_worker_name():
    fut = H.submit(lambda x: x * 2, 21)
    assert fut is not None and fut.result(timeout=5) == 42
    fut = H.submit(lambda: 1 / 0)                                 # NEG: a raising job is fenced, never raised
    assert fut.result(timeout=5) is None



def test_NEG_feed_off_is_off_with_the_off_word(hub, monkeypatch):
    monkeypatch.setattr(live_feed, "state_word", lambda *a, **k: ("off", live_feed.FEED_WORDS["off"]))
    out = H.register_interest("gajjala", ["ABC"])
    assert out == {"on": False, "word": "📡 Live stream off on this server.", "state": "off"}
    assert H._interest == {}


def test_NEG_feed_disabled_by_env_is_off(hub, monkeypatch):
    monkeypatch.setenv("MASSIVE_WS_ENABLED", "false")
    out = H.register_interest("gajjala", ["ABC"])
    assert out["on"] is False and out["state"] == "off"


def test_a_kicked_feed_still_registers_with_the_kicked_state(hub, monkeypatch):
    kicked = live_feed.FEED_WORDS["kicked"].format(n=2)
    monkeypatch.setattr(live_feed, "state_word", lambda *a, **k: ("kicked", kicked))
    out = H.register_interest("gajjala", ["ABC"])
    assert out == {"on": True, "word": kicked, "state": "kicked"}
    assert H.interest_of("gajjala", "ABC") is not None
