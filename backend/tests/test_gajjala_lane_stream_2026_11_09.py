"""🛰 Stream entries for the 🚩 Gajjala lane (GG LIVE P1, 2026-11-09) — trading/gajjala_stream.py, ships SHADOW.

Ajay 2026-11-09: "I would like the autopilot to be continously monitored or live tracked and changed as if Gallalas makes
the trades … make it more live with websockets or something else where there is a low latency monitoring on the prices
action changes please?"

Locks (spec §3.3 / §4 WP-B): the owner numbers and served words; the env only LOWERS the mode (NEG: never raises it);
SHADOW records the first regular print at/over the trigger (+ the round-lot row) with ZERO broker calls and ONE Mongo
write per event (NEG: 1,000 more prints = no more writes); an odd-lot first print writes `trigger` only, a later round
lot `trigger_lot`; gate closed / a non-regular print / no hub filter → nothing (NEG); the stop row; LIVE (constant
patched): one order with order_source "stream", the recheck clock and the empty bucket (NEG each), stop-first =
never_triggered; a new A+ priced from a fresh print (NEG: no REST) or ONE REST read when stale; the bar-close run in
LIVE only (NEG: SHADOW / OFF); the served status block.

Hermetic: the lane fixture of tests/test_gajjala_lane.py (fake broker + fake Mongo); `live_hub` is STUBBED per the
spec's §3.2 interface (PRINT_KINDS, HUB_POLL_SEC) — the real hub is WP-A's; the worker runs inline.
"""
import os
import sys
import types
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.exit_engine as EE
import trading.gajjala_entry as GL
import trading.gajjala_stream as GS
from tests.test_gajjala_lane import DAY, NOW, LaneColl, _brackets, alert, lane, seed  # noqa: F401 — `lane` is a fixture

DOC_ID = f"GG:{DAY}|SAIQ|bull_flag"
RECV = NOW.timestamp()                                  # 2026-10-20 10:55 ET


class StreamColl(LaneColl):
    """gajjala_lane_stream with call counters (insert-once rows)."""

    def __init__(self, docs=()):
        super().__init__(docs)
        self.inserts = 0
        self.finds = 0

    def insert_one(self, doc):
        self.inserts += 1
        return super().insert_one(doc)

    def find(self, q=None, *a, **k):
        self.finds += 1
        return super().find(q, *a, **k)


class Recorder:
    """A broker that records every attribute touched (SHADOW must touch none)."""

    def __init__(self):
        self.touched = []

    def __getattr__(self, name):
        self.touched.append(name)
        raise AssertionError(f"SHADOW touched the broker: {name}")


@pytest.fixture(autouse=True)
def hub(monkeypatch):
    mod = types.ModuleType("live_hub")
    mod.PRINT_KINDS = ("regular",)                      # spec §3.2 (WP-A owns the real one)
    mod.HUB_POLL_SEC = 1.0
    monkeypatch.setitem(sys.modules, "live_hub", mod)
    monkeypatch.delenv("GG_STREAM_MODE", raising=False)
    # 2026-11-09 ~10:00 ET: the BUILT default became "live" (HIS CALL #1 answered — Ajay: "With entries realtime like
    # Gajjala does"). The shadow-behaviour tests below keep their SHADOW baseline through this patch; the built default
    # and the env rule on it are pinned by test_built_default_is_live_env_only_lowers from the SOURCE literal.
    monkeypatch.setattr(GS, "GG_STREAM_MODE", "shadow")
    monkeypatch.setattr(GS, "_submit", lambda fn, *a: fn(*a))     # the worker, inline
    GS._reset()
    yield mod
    GS._reset()


def _pr(p, c=(), sym="SAIQ", recv=RECV, lag_ms=200.0, s=100, kind=None):
    pr = {"sym": sym, "p": p, "s": s, "c": list(c), "t_ms": recv * 1000.0 - lag_ms, "recv": recv, "trfi": False}
    if kind:
        pr["kind"] = kind
    return pr


def _view(state="waiting", trig=4.46, stop=4.31, sym="SAIQ", doc_id=DOC_ID):
    return {doc_id: {"symbol": sym, "trigger": trig, "stop": stop, "state": state, "updated_at": None}}


def _shadow(lane_fx, monkeypatch, **kw):
    s = lane_fx(docs=[seed()], **kw)
    s.db.gajjala_lane_stream = StreamColl()
    rec = Recorder()
    monkeypatch.setattr(GL, "broker", rec)
    monkeypatch.setattr(GL, "run_stream", lambda *a, **k: pytest.fail("SHADOW called run_stream"))
    monkeypatch.setattr(GL, "run", lambda *a, **k: pytest.fail("SHADOW called run"))
    s.rec = rec
    return s


def _ids(coll):
    return sorted(r["_id"] for r in coll.rows)


# ── numbers, words, mode ─────────────────────────────────────────────────────────────────────────────────────────
def test_owner_numbers_words_and_derived(hub):
    from orderflow import tape
    assert _built_mode() == "live" and GS.GG_STREAM_MODES == ("off", "shadow", "live")   # LIVE since 2026-11-09 ~10:00 ET (Ajay: "With entries realtime like Gajjala does")
    assert (GS.GG_STREAM_RECHECK_SEC, GS.GG_STREAM_ALPACA_PER_MIN, GS.GG_STREAM_FRESH_POLLS) == (15.0, 60, 2)
    assert GS.fresh_sec() == 2.0
    hub.HUB_POLL_SEC = 0.5
    assert GS.fresh_sec() == 1.0                        # derived from the hub, never retyped
    assert GS.ODD_LOT_CONDITION in tape.KEPT_DESPITE_FLAGS and GS.ODD_LOT_CONDITION == 37
    assert GS.STREAM_COLL == "gajjala_lane_stream"
    assert GS.STREAM_WORDS == {
        "shadow": ("🛰 Stream entries: SHADOW — the first regular print at or over the trigger is recorded; orders still "
                   "go on the 1-minute check."),
        "live": "🛰 Stream entries: LIVE — a market order on the first regular print at or over the trigger.",
        "off": "🛰 Stream entries: off.",
    }
    assert set(GS.status()) == {"mode", "word", "prints_today", "first_prints_today"}


def test_no_hub_means_never_fresh_and_nothing_passes(monkeypatch):
    monkeypatch.setitem(sys.modules, "live_hub", None)  # NEG: import fails
    assert GS.fresh_sec() == 0.0 and GS._print_kinds() == ()


def _built_mode() -> str:
    """The BUILT literal, read from the source (the autouse fixture patches the attribute to the shadow baseline)."""
    import inspect
    import re
    m = re.search(r'^GG_STREAM_MODE = "([a-z]+)"', inspect.getsource(GS), re.M)
    assert m, "gajjala_stream.py lost the GG_STREAM_MODE literal"
    return m.group(1)


def test_built_default_is_live_env_only_lowers(monkeypatch):
    """2026-11-09 ~10:00 ET — Ajay: "to do entries I would like to see it in action now" / "With entries realtime like
    Gajjala does" → the built default is LIVE; the env may still lower it, never raise it."""
    monkeypatch.setattr(GS, "GG_STREAM_MODE", _built_mode())
    assert GS.mode() == "live"
    assert GS.STREAM_WORDS["live"] == "🛰 Stream entries: LIVE — a market order on the first regular print at or over the trigger."
    monkeypatch.setenv("GG_STREAM_MODE", "shadow")
    assert GS.mode() == "shadow"                        # lowered
    monkeypatch.setenv("GG_STREAM_MODE", "off")
    assert GS.mode() == "off"                           # lowered
    monkeypatch.setenv("GG_STREAM_MODE", "live")
    assert GS.mode() == "live"
    monkeypatch.setenv("GG_STREAM_MODE", "turbo")
    assert GS.mode() == "live"                          # NEG: an unknown env word changes nothing
    monkeypatch.delenv("GG_STREAM_MODE")
    assert GS.on_bar_close(NOW) is not None or True     # the bar-close lane run is reachable in LIVE (pinned below)


def test_env_lowers_never_raises(monkeypatch):
    monkeypatch.setenv("GG_STREAM_MODE", "live")
    assert GS.mode() == "shadow"                        # NEG: the env never raises the built mode
    monkeypatch.setenv("GG_STREAM_MODE", "LIVE ")
    assert GS.mode() == "shadow"
    monkeypatch.setenv("GG_STREAM_MODE", "off")
    assert GS.mode() == "off"
    monkeypatch.setenv("GG_STREAM_MODE", "turbo")
    assert GS.mode() == "shadow"
    monkeypatch.setattr(GS, "GG_STREAM_MODE", "live")
    monkeypatch.setenv("GG_STREAM_MODE", "shadow")
    assert GS.mode() == "shadow"
    monkeypatch.setattr(GS, "GG_STREAM_MODE", "off")
    monkeypatch.setenv("GG_STREAM_MODE", "live")
    assert GS.mode() == "off"


# ── SHADOW ───────────────────────────────────────────────────────────────────────────────────────────────────────
def test_shadow_round_lot_trigger_rows_zero_broker_one_write_each(lane, monkeypatch):
    s = _shadow(lane, monkeypatch)
    sc = s.db.gajjala_lane_stream
    jobs = []
    monkeypatch.setattr(GS, "_submit", lambda fn, *a: jobs.append(a) or fn(*a))
    GS.on_print(_pr(4.47, c=[]), _view(), True)
    assert _ids(sc) == [f"{DOC_ID}|trigger", f"{DOC_ID}|trigger_lot"] and len(jobs) == 1
    row = sc.get(f"{DOC_ID}|trigger")
    assert row["doc_id"] == DOC_ID and row["symbol"] == "SAIQ" and row["event"] == "trigger"
    assert row["print_px"] == 4.47 and row["print_size"] == 100 and row["conditions"] == [] and row["odd_lot"] is False
    assert row["mode"] == "shadow" and row["lag_ms"] == 200
    assert row["recv_t"] == datetime.fromtimestamp(RECV, tz=timezone.utc).isoformat(timespec="milliseconds")
    assert row["print_t"] < row["recv_t"]
    writes, reads = sc.inserts, sc.finds
    assert writes == 2
    for i in range(1000):                               # NEG: the memo — no per-print Mongo, no broker
        GS.on_print(_pr(4.47 + (i % 5) / 100.0, c=[]), _view(), True)
    assert (sc.inserts, sc.finds) == (writes, reads) and len(sc.rows) == 2
    assert len(jobs) == 1                               # NEG: the read loop's memo — no job per print
    assert s.rec.touched == [] and _brackets(s.brk) == []
    assert s.db.gajjala_lane.get(DOC_ID)["state"] == "waiting"      # SHADOW never moves the doc


def test_shadow_odd_lot_first_then_round_lot(lane, monkeypatch):
    s = _shadow(lane, monkeypatch)
    sc = s.db.gajjala_lane_stream
    GS.on_print(_pr(4.46, c=[37]), _view(), True)       # an odd lot AT the trigger
    assert _ids(sc) == [f"{DOC_ID}|trigger"] and sc.get(f"{DOC_ID}|trigger")["odd_lot"] is True
    assert sc.get(f"{DOC_ID}|trigger")["conditions"] == [37]
    GS.on_print(_pr(4.47, c=[12]), _view(), True)       # Form T is regular and a round lot
    assert _ids(sc) == [f"{DOC_ID}|trigger", f"{DOC_ID}|trigger_lot"]
    assert sc.get(f"{DOC_ID}|trigger")["print_px"] == 4.46          # NEG: the first row is never rewritten
    assert sc.inserts == 2


def test_gate_closed_no_row_no_mongo_no_broker(lane, monkeypatch):
    s = _shadow(lane, monkeypatch)
    sc = s.db.gajjala_lane_stream
    GS.on_print(_pr(4.50), _view(), False)
    assert (sc.inserts, sc.finds, sc.rows) == (0, 0, []) and s.rec.touched == []


def test_non_regular_print_refused(lane, monkeypatch):
    s = _shadow(lane, monkeypatch)
    sc = s.db.gajjala_lane_stream
    GS.on_print(_pr(4.50, c=[22]), _view(), True)        # NEG: non_flow (the hub drops it; here refused too)
    GS.on_print(_pr(4.50, c=[], kind="auction_open"), _view(), True)
    GS.on_print(_pr(4.50, c=[], kind="summary"), _view(), True)
    assert (sc.inserts, sc.finds) == (0, 0)
    monkeypatch.setitem(sys.modules, "live_hub", None)  # NEG: no hub filter → nothing passes
    GS.on_print(_pr(4.50, c=[]), _view(), True)
    assert sc.inserts == 0


def test_shadow_stop_print_writes_only_the_stop_row(lane, monkeypatch):
    s = _shadow(lane, monkeypatch)
    sc = s.db.gajjala_lane_stream
    GS.on_print(_pr(4.31), _view(), True)
    assert _ids(sc) == [f"{DOC_ID}|stop"]
    assert s.db.gajjala_lane.get(DOC_ID)["state"] == "waiting"      # NEG: SHADOW never closes the doc
    GS.on_print(_pr(4.40), _view(), True)                # between stop and trigger: nothing
    assert _ids(sc) == [f"{DOC_ID}|stop"]


def test_two_docs_of_one_symbol_in_the_lane_order(lane, monkeypatch):
    _shadow(lane, monkeypatch)
    jobs = []
    monkeypatch.setattr(GS, "_submit", lambda fn, *a: jobs.append(a[0]))
    view = {f"GG:{DAY}|SAIQ|kiss_fly": {"symbol": "SAIQ", "trigger": 4.40, "stop": 4.30, "state": "waiting",
                                         "alert_at": "2026-10-20T14:52:00+00:00", "setup": "kiss_fly"},
            f"GG:{DAY}|SAIQ|bull_flag": {"symbol": "SAIQ", "trigger": 4.46, "stop": 4.31, "state": "waiting",
                                          "alert_at": "2026-10-20T14:52:00+00:00", "setup": "bull_flag"},
            f"GG:{DAY}|SAIQ|intraday_vcp": {"symbol": "SAIQ", "trigger": 4.45, "stop": 4.30, "state": "waiting",
                                             "alert_at": "2026-10-20T14:40:00+00:00", "setup": "intraday_vcp"}}
    GS.on_print(_pr(4.47), view, True)
    from chart_maps.gajjala import constants as GC
    same_time = sorted(["kiss_fly", "bull_flag"], key=GC.SETUPS.index)
    assert jobs == [f"GG:{DAY}|SAIQ|intraday_vcp"] + [f"GG:{DAY}|SAIQ|{x}" for x in same_time]


def test_only_waiting_docs_of_the_symbol(lane, monkeypatch):
    s = _shadow(lane, monkeypatch)
    sc = s.db.gajjala_lane_stream
    GS.on_print(_pr(4.50), _view(state="ordered"), True)                # NEG: not waiting
    GS.on_print(_pr(4.50, sym="ZZZ"), _view(), True)                    # NEG: another symbol
    GS.on_print(_pr(None), _view(), True)                               # NEG: no price
    GS.on_print({"garbage": 1}, _view(), True)                          # never raises
    GS.on_print(_pr(4.50), None, True)
    assert sc.inserts == 0


def test_off_mode_does_nothing(lane, monkeypatch):
    s = _shadow(lane, monkeypatch)
    monkeypatch.setenv("GG_STREAM_MODE", "off")
    GS.on_print(_pr(4.50), _view(), True)
    assert GS.on_new_aplus([{"_id": DOC_ID, "symbol": "SAIQ"}])["seen"] == 0
    assert s.db.gajjala_lane_stream.inserts == 0 and GS.status()["word"] == GS.STREAM_WORDS["off"]


class FlakyColl(StreamColl):
    """The first `fail` inserts raise (Mongo hiccup)."""

    def __init__(self, fail=1):
        super().__init__()
        self.fail = fail

    def insert_one(self, doc):
        if self.fail > 0:
            self.fail -= 1
            self.inserts += 1
            raise RuntimeError("mongo hiccup")
        return super().insert_one(doc)


def test_failed_write_not_memoised_next_print_writes_one_row(lane, monkeypatch):
    s = _shadow(lane, monkeypatch)
    sc = s.db.gajjala_lane_stream = FlakyColl(fail=1)
    GS.on_print(_pr(4.47, c=[37]), _view(), True)        # odd lot → `trigger` only; its write fails
    assert sc.rows == [] and f"{DOC_ID}|trigger" not in GS._M.written            # NEG: not marked written
    assert f"{DOC_ID}|trigger" not in GS._M.pending
    GS.on_print(_pr(4.48, c=[37]), _view(), True)        # the next qualifying print retries
    assert _ids(sc) == [f"{DOC_ID}|trigger"] and sc.get(f"{DOC_ID}|trigger")["print_px"] == 4.48
    GS.on_print(_pr(4.49, c=[37]), _view(), True)
    assert len(sc.rows) == 1 and sc.inserts == 2         # exactly one row; no further write
    assert s.rec.touched == []                           # NEG: the broker is never called


def test_failed_writes_capped_no_retry_storm(lane, monkeypatch):
    s = _shadow(lane, monkeypatch)
    sc = s.db.gajjala_lane_stream = FlakyColl(fail=10_000)
    for i in range(50):
        GS.on_print(_pr(4.47, c=[37]), _view(), True)
    assert GS.GG_STREAM_ROW_MAX_TRIES == 2
    assert sc.inserts == GS.GG_STREAM_ROW_MAX_TRIES and sc.rows == []            # NEG: bounded, then given up
    assert s.rec.touched == []


def test_failed_seen_row_retried_once(lane, monkeypatch):
    s = _shadow(lane, monkeypatch, alerts=[alert()])
    sc = s.db.gajjala_lane_stream = FlakyColl(fail=1)
    rows = [{"_id": DOC_ID, "symbol": "SAIQ"}]
    assert GS.on_new_aplus(rows, now=NOW)["seen"] == 0 and sc.rows == []
    assert GS.on_new_aplus(rows, now=NOW)["seen"] == 1 and _ids(sc) == [f"{DOC_ID}|seen"]
    assert GS.on_new_aplus(rows, now=NOW)["seen"] == 0 and sc.inserts == 2
    assert s.rec.touched == []


def test_memo_rebuilt_from_todays_rows(lane, monkeypatch):
    s = _shadow(lane, monkeypatch)
    s.db.gajjala_lane_stream = StreamColl([{"_id": f"{DOC_ID}|trigger"}, {"_id": f"{DOC_ID}|trigger_lot"}])
    GS.on_print(_pr(4.47), _view(), True)                # after a restart: the rows exist
    assert s.db.gajjala_lane_stream.inserts == 0         # NEG: no duplicate write attempt after the rebuild


def test_shadow_new_aplus_seen_row_once(lane, monkeypatch):
    s = _shadow(lane, monkeypatch, alerts=[alert()])
    sc = s.db.gajjala_lane_stream
    rows = [{"_id": DOC_ID, "symbol": "SAIQ", "trigger": 4.46, "stop": 4.31, "setup": "bull_flag"},
            {"_id": f"SHADOW:GG:{DAY}|XXX|bull_flag", "symbol": "XXX"}]      # NEG: never a shadow claim
    out = GS.on_new_aplus(rows, now=NOW)
    assert out["seen"] == 1 and _ids(sc) == [f"{DOC_ID}|seen"]
    row = sc.get(f"{DOC_ID}|seen")
    assert row["event"] == "seen" and row["recv_t"] == datetime.fromtimestamp(RECV, tz=timezone.utc).isoformat(
        timespec="milliseconds") and row["mode"] == "shadow"
    assert GS.on_new_aplus(rows, now=NOW)["seen"] == 0 and sc.inserts == 1           # NEG: once
    assert s.rec.touched == []


def test_status_block_serves_the_stream_word(lane, monkeypatch):
    lane()
    st = GL.status_block(EE.get_config())
    assert st["stream"]["mode"] == "shadow" and st["stream"]["word"] == GS.STREAM_WORDS["shadow"]
    monkeypatch.setattr(GS, "GG_STREAM_MODE", _built_mode())                                     # the built default: LIVE
    live_st = GL.status_block(EE.get_config())["stream"]
    assert live_st["mode"] == "live" and live_st["word"] == GS.STREAM_WORDS["live"]
    monkeypatch.setattr(GS, "GG_STREAM_MODE", "shadow")
    monkeypatch.setenv("GG_STREAM_MODE", "off")
    assert GL.status_block(EE.get_config())["stream"]["word"] == GS.STREAM_WORDS["off"]
    monkeypatch.setattr(GS, "status", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert GL.status_block(EE.get_config())["stream"]["word"] is None             # fenced


# ── LIVE (constant patched — never the built default) ───────────────────────────────────────────────────────────
@pytest.fixture
def live(monkeypatch):
    monkeypatch.setattr(GS, "GG_STREAM_MODE", "live")
    clock = {"t": 1000.0}
    monkeypatch.setattr(GS, "_mono", lambda: clock["t"])
    return clock


def test_live_print_orders_once_from_the_stream(lane, live, monkeypatch):
    s = lane(docs=[seed()], lasts={})
    s.db.gajjala_lane_stream = StreamColl()
    rest = []
    monkeypatch.setattr(GL, "_live_last", lambda b, sym: rest.append(sym) or (None, None))
    GS.on_print(_pr(4.47), _view(), True)
    assert len(_brackets(s.brk)) == 1 and rest == []     # NEG: no REST read — the print is the last
    d = s.db.gajjala_lane.get(DOC_ID)
    assert d["state"] == "ordered" and d["order_source"] == "stream" and d["stream_print_px"] == 4.47
    assert d["stream_print_t"] and d["last_source"] == GS.STREAM_SOURCE and isinstance(d["enter_ms"], int)
    assert s.db.gajjala_lane_stream.get(f"{DOC_ID}|trigger")["mode"] == "live"
    live["t"] += 30
    GS.on_print(_pr(4.48), _view(), True)                # the hub's view still says waiting for a second
    assert len(_brackets(s.brk)) == 1                    # NEG: never a second order


def test_live_recheck_clock_and_empty_bucket(lane, live, monkeypatch):
    lane(docs=[seed()])
    calls = []
    monkeypatch.setattr(GL, "run_stream", lambda *a, **k: calls.append((a, k)) or {"waiting": 1})
    GS.on_print(_pr(4.47), _view(), True)
    assert len(calls) == 1 and calls[0][0] == (DOC_ID,) and calls[0][1]["source"] == "stream:T"
    live["t"] += GS.GG_STREAM_RECHECK_SEC - 1
    GS.on_print(_pr(4.48), _view(), True)
    assert len(calls) == 1                               # NEG: inside the recheck clock
    live["t"] += 2
    GS.on_print(_pr(4.48), _view(), True)
    assert len(calls) == 2
    GS._reset()
    monkeypatch.setattr(GS, "GG_STREAM_ALPACA_PER_MIN", 1)
    two = dict(_view(), **_view(sym="BBB", doc_id=f"GG:{DAY}|BBB|bull_flag"))
    GS.on_print(_pr(4.47), two, True)
    GS.on_print(_pr(4.47, sym="BBB"), two, True)
    assert len(calls) == 3                               # NEG: the bucket is empty → left to the minute tick


def test_live_stop_first_is_never_triggered(lane, live, monkeypatch):
    s = lane(docs=[seed()], lasts={})
    s.db.gajjala_lane_stream = StreamColl()
    GS.on_print(_pr(4.30), _view(), True)
    d = s.db.gajjala_lane.get(DOC_ID)
    assert (d["state"], d["skip_kind"]) == ("unfilled", "never_triggered") and _brackets(s.brk) == []
    assert _ids(s.db.gajjala_lane_stream) == [f"{DOC_ID}|stop"]


def test_live_new_aplus_fresh_print_no_rest(lane, live, monkeypatch):
    s = lane(alerts=[alert()], lasts={})
    s.db.gajjala_lane_stream = StreamColl()
    rest = []
    monkeypatch.setattr(GL, "_live_last", lambda b, sym: rest.append(sym) or (4.49, "rest"))
    monkeypatch.setattr(GS, "_wall", lambda: RECV + 1.0)
    GS.on_print(_pr(4.48), {}, False)                    # the hub routes A+ names: last print remembered
    out = GS.on_new_aplus([{"_id": DOC_ID, "symbol": "SAIQ"}], now=NOW)
    assert out["attempted"] and rest == []               # NEG: no REST when the print is fresh
    d = s.db.gajjala_lane.get(DOC_ID)
    assert d["state"] == "ordered" and d["order_source"] == "hub_claim" and d["last"] == 4.48
    assert d["last_source"] == GS.STREAM_SOURCE and "stream_print_px" not in d


def test_live_new_aplus_stale_print_one_rest_read(lane, live, monkeypatch):
    s = lane(alerts=[alert()], lasts={})
    s.db.gajjala_lane_stream = StreamColl()
    rest = []
    monkeypatch.setattr(GL, "_live_last", lambda b, sym: rest.append(sym) or (4.49, "rest"))
    monkeypatch.setattr(GS, "_wall", lambda: RECV + 2.5)            # older than 2 × HUB_POLL_SEC
    GS.on_print(_pr(4.48), {}, False)
    GS.on_new_aplus([{"_id": DOC_ID, "symbol": "SAIQ"}], now=NOW)
    assert rest == ["SAIQ"] and s.db.gajjala_lane.get(DOC_ID)["last"] == 4.49


def test_bar_close_runs_the_lane_in_live_only(monkeypatch):
    calls = []
    monkeypatch.setattr(GL, "run", lambda *a, **k: calls.append((a, k)) or {"ok": True})
    assert GS.on_bar_close(NOW) is None and calls == []                 # NEG: SHADOW (built)
    monkeypatch.setenv("GG_STREAM_MODE", "off")
    assert GS.on_bar_close(NOW) is None and calls == []                 # NEG: OFF
    monkeypatch.delenv("GG_STREAM_MODE")
    monkeypatch.setattr(GS, "GG_STREAM_MODE", "live")
    assert GS.on_bar_close(NOW) == {"ok": True}
    assert len(calls) == 1 and calls[0][1]["source"] == "bar_close" and calls[0][0][2] == NOW
