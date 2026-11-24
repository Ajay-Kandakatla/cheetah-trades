"""▶ run Gajjala's rules on ONE Watch name — the engine, the route, the probes (2026-11-24, spec ggrun rev 2 §4 be-run).

Ajay 2026-11-24, verbatim: "On the Watch list I need a run button to run against Gajjalas rules of a stock to see for
patterns of 5 patterns he has especially reversal squeeze.. so can check for patterns mid day when I can add a small
slide in in the chart window for giving verbatim of passed rules and failed rules of that stock like you do in other
tabs.."

The REAL bars resampler and detectors run on the 🚩 pass fixture (tests/test_gajjala_run.py: the Bull Flag A+ day
expanded to 1-minute bars). Every provider is injected; every store is the in-memory FakeColl set.
NEGATIVES: not listed / malformed / closed / switched off read nothing; no prints / no bars / a provider failure;
a `none` read never prints a ✓; WRITES NOTHING (every FakeColl, the cache write, the alert / push / potential / auto
writers, Yahoo) + an AST source guard; a non-owner gets 404 and the engine is never called; busy; no memo across a bar
close; gate_text None everywhere but a 🎾 read the float gate replaced.
"""
from __future__ import annotations

import ast
import asyncio
import json
import re
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import context as CX
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala import store as GST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala_watch import api as API
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import float_read as WF
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import rest as WR
from chart_maps.gajjala_watch import run_rules as RR
from chart_maps.gajjala_watch import sections as SEC
from daytrading import data as dt
from sepa import volume_movers as VM
from tests.fixtures.gajjala import detector_frames as FX
from tests.test_gajjala_run import NOW, PREV, PRIOR_1M, S, TODAY_1M
from tests.test_gajjala_store import FakeColl, fake_store

ET = ZoneInfo("America/New_York")
OWNER = "owner@example.com"
OTHER = "doug@example.com"
SYM = "GGA"
SRC = Path(RR.__file__)


def at(hh, mm, ss=0, d=S):
    return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=ET)


def _strict(txt):
    def _refuse(tok):
        raise ValueError(f"non-JSON constant {tok}")
    return json.loads(txt, parse_constant=_refuse)


class Loader:
    """The injected minute loader: the prior day = PRIOR_1M, today = TODAY_1M (volume × `scale`). Counts every call;
    `today` counts the forced (today) calls — one per read."""

    def __init__(self, prev=True, today=True, scale=1.0, block=None, raise_on=None):
        self.calls, self.prev, self.today, self.scale, self.block, self.raise_on = [], prev, today, scale, block, raise_on

    def __call__(self, sym, day, force=False, include_premarket=True, include_afterhours=False):
        self.calls.append((sym, day, force))
        if self.raise_on is not None and day == self.raise_on:
            raise RuntimeError("provider down")
        if day == S:
            if self.block is not None:
                self.block(sym)
            if not self.today:
                return None
            df = TODAY_1M.copy()
            df["volume"] = df["volume"] * self.scale
            return df
        return PRIOR_1M.copy() if self.prev else None

    @property
    def today_calls(self):
        return [c for c in self.calls if c[2]]


def _watch_db(symbols=(SYM,), auto=None):
    docs = [{"_id": C.LIST_DOC_ID, "symbols": list(symbols)}]
    if auto is not None:
        docs.append({"_id": C.AUTO_DOC_ID, "session": S.isoformat(), "entries": [{"symbol": s} for s in auto]})
    return {C.COLL_LIST: FakeColl(docs), C.COLL_TILES: FakeColl(), C.COLL_ALERTS: FakeColl(), C.COLL_STATE: FakeColl()}


def _read_doc(sym=SYM, *, float_read=None, listed=None):
    d = {"_id": GST.key(S, sym), "date": S.isoformat(), "symbol": sym, "setups": {}, "ctx": {}}
    if float_read is not None:
        d["ctx"]["float"] = float_read
    if listed is not None:
        d["listed"] = listed
    return d


class World:
    def __init__(self, *, symbols=(SYM,), auto=None, doc=None, loader=None):
        self.db = _watch_db(symbols, auto)
        self.reads = FakeColl([doc] if doc else [])
        self.shares = FakeColl()
        self.store = fake_store(**{GST.READS: self.reads, VM.SHARES_COLL: self.shares})
        self.load = loader or Loader()

    def run(self, sym=SYM, now=NOW, clock=None, **kw):
        kw.setdefault("db", self.db)
        kw.setdefault("store", self.store)
        kw.setdefault("load", self.load)
        if clock is not None:
            kw["clock"] = clock
        return RR.run(sym, now, **kw)

    def all_colls(self):
        return list(self.db.values()) + [self.store.coll(n) for n in GST.ALL] + [self.shares]


class Trap:
    def __init__(self):
        self.calls = []

    def make(self, name):
        def _boom(*a, **k):
            self.calls.append(name)
            raise AssertionError(f"{name} was reached")
        return _boom


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    """The memo, the per-symbol locks AND the Watch's breaker never leak across cases [P2]; no outside call at all."""
    RR._reset()
    monkeypatch.setattr(WR, "_BREAKER", None)
    monkeypatch.setattr(CX, "_default_massive_lookup", lambda s: None)
    trap = Trap()
    monkeypatch.setattr(VM, "_shares_coll", trap.make("VM._shares_coll"))
    monkeypatch.setattr(VM, "_fetch_shares_status", trap.make("VM._fetch_shares_status"))
    monkeypatch.setattr(dt, "_mongo_put_day", trap.make("dt._mongo_put_day"))
    monkeypatch.setattr(dt, "_get_mongo_coll", trap.make("dt._get_mongo_coll"))
    yield trap
    RR._reset()


@pytest.fixture()
def trap(_clean):
    return _clean


@pytest.fixture()
def world():
    return World()


def _by(ans):
    return {b["setup"]: b for b in ans["setups"]}


# ── (1)–(5) the answer ───────────────────────────────────────────────────────────────────────────────────────────
def test_1_every_block_is_read_all_on_the_same_frames_in_the_cards_words(trap):
    fl = FX.float_read(3_000_000)
    w = World(doc=_read_doc(float_read=fl))
    ans = w.run()
    assert ans["state"] == "ok"
    frames = B.frames_for([SYM], S, NOW, load_day=Loader(), budget_sec=C.RUN_BUDGET_SEC, stats={})
    fr = frames[SYM]
    reads = D.read_all(fr.detector_frames(), {"symbol": SYM, "float_read": fl, D.K11_CTX_KEY: B.session_volume(fr)})
    for k, blk in _by(ans).items():
        r = reads[k]
        assert json.dumps(blk["criteria"]) == json.dumps(r["criteria"])          # bytes, detector order
        assert blk["state"] == r["state"]
        assert blk["state_label"] == GT.state_label(r, False)                   # entries {} → nothing rang
        assert blk["plan_text"] == GT.plan_text(r) and blk["variant_label"] == GT.variant_label(r)
        assert blk["grade_label"] == GT.grade_label(r) and blk["vol_dried_text"] == GT.vol_dried_text(r)
        assert blk["label"] == GT._setup_label(k) and blk["as_of_bar_t"] == r["as_of_bar_t"]
    assert _by(ans)["bull_flag"]["state"] == "aplus"                              # the fixture is the A+ day
    assert trap.calls == []


def test_2_order_reversal_squeeze_first_then_the_setups_order(world):
    ans = world.run()
    got = [b["setup"] for b in ans["setups"]]
    assert SEC.RS_SETUP in GC.SETUPS and got[0] == SEC.RS_SETUP == "reversal_squeeze"
    assert got == [SEC.RS_SETUP] + [s for s in GC.SETUPS if s != SEC.RS_SETUP] and len(got) == 5
    assert list(RR.setup_order()) == got
    assert _by(ans)[SEC.RS_SETUP]["label"] == "🎾 Reversal Squeeze"


def _every_state(monkeypatch):
    out = {}
    w = World()
    out["ok"] = w.run()
    out["bad_symbol"] = w.run("$OMH")
    out["not_listed"] = w.run("ZZZ")
    out["closed"] = w.run(now=at(3, 0))
    for state, loader in (("no_prints", Loader(today=False)), ("no_bars", Loader(prev=False, today=False)),
                          ("failed", Loader(raise_on=S))):
        RR._reset()                                                             # the memo is per process
        out[state] = World(loader=loader).run()
    RR._reset()
    lk = RR._lock_for(SYM)
    lk.acquire()
    try:
        monkeypatch.setattr(C, "RUN_BUDGET_SEC", 0.01)
        out["busy"] = World().run()
    finally:
        lk.release()
    monkeypatch.setattr(C, "RUN_RULES_ON", False)
    out["off"] = w.run()
    monkeypatch.setattr(C, "RUN_RULES_ON", True)
    monkeypatch.setattr(CO, "owner_symbols", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    out["error"] = World().run()
    return out


def test_3_exact_key_sets_on_every_state(monkeypatch):
    got = _every_state(monkeypatch)
    assert set(got) == set(RR.STATES)
    assert tuple(D.criterion("k", "l", True)) == RR.CRITERION_KEYS
    for state, ans in got.items():
        assert ans["state"] == state, (state, ans.get("text"))
        assert tuple(ans) == C.RUN_ANSWER_KEYS == RR.ANSWER_KEYS
        assert isinstance(ans["title"], str) and ans["note"] == C.RUN_NOTE_TEXT
        if state != "ok":
            assert isinstance(ans["text"], str) and ans["text"] and ans["setups"] == []
            assert all(ans[k] is None for k in ("as_of", "scanner", "float_text", "volume_text", "reused_text"))
    for blk in got["ok"]["setups"]:
        assert tuple(blk) == RR.SETUP_KEYS
        for c in blk["criteria"]:
            assert tuple(c) == RR.CRITERION_KEYS


def test_4_as_of_names_the_graded_bars_and_the_read_clock(world):
    a = world.run()["as_of"]
    assert a["bar_t5"] == "2026-10-13 10:40" and a["bar_t15"] == "2026-10-13 10:30" and a["read_at_et"] == "10:41:00"
    assert a["text"] == RR.AS_OF_TEXT.format(t5="10:40", w5=C.FRAME_WORDS["5m"], at="10:41:00",
                                             slow=RR.AS_OF_SLOW_TEXT.format(w15=C.FRAME_WORDS["15m"], t15="10:30"))


def test_5_scanner_line_on_off_and_bare():
    off = World().run()["scanner"]
    assert off == {"listed": False, "text": RR.SCANNER_OFF_TEXT}
    listed = {"since": "2026-10-11", "day_n": 2, "of": 3}
    RR._reset()                                                                 # the memo is per process
    on = World(doc=_read_doc(listed=listed)).run()["scanner"]
    assert on == {"listed": True, "text": RR.SCANNER_ON_TEXT.format(listed=GT._listed_block(listed)["text"])}
    assert "listed day 2/3" in on["text"]
    RR._reset()
    assert World(doc=_read_doc()).run()["scanner"] == {"listed": True, "text": RR.SCANNER_ON_BARE_TEXT}


# ── (6) the float ────────────────────────────────────────────────────────────────────────────────────────────────
def test_6_the_stored_pass_read_wins_and_the_chain_is_not_called(monkeypatch):
    calls = []
    monkeypatch.setattr(CX, "floats_for", lambda *a, **k: calls.append(1) or {})
    fl = FX.float_read(3_000_000)
    w = World(doc=_read_doc(float_read=fl))
    assert RR.float_for(SYM, NOW, w.reads.find_one({}), w.store) == (fl, "pass")
    ans = w.run()
    assert calls == [] and ans["float_text"].startswith("Float 3.0M")


def test_6_no_read_doc_runs_steps_one_two_with_no_store_and_the_long_lived_handle(monkeypatch, trap):
    seen, status = [], []
    real = CX.floats_for

    def _spy(*a, **k):
        seen.append(k)
        return real(*a, **k)
    monkeypatch.setattr(CX, "floats_for", _spy)
    monkeypatch.setattr(VM, "shares_status", lambda s, fetch=True, coll=None: status.append((s, fetch, coll))
                        or (None, "missing"))
    monkeypatch.setattr(CX, "_default_massive_lookup", lambda s: 17_900_000)
    w = World()
    ans = w.run()
    assert len(seen) == 1 and seen[0]["refine"] is False
    assert "store" not in seen[0] and "session" not in seen[0] and callable(seen[0]["status_lookup"])
    assert status == [(SYM, False, w.shares)]                                  # fetch=False, the store's handle
    status.clear()
    assert RR.shares_lookup(w.store)(SYM, fetch=True) == (None, "missing")       # asked fetch=True → still False
    assert status == [(SYM, False, w.shares)]
    assert "shares out 17.9M (Massive)" in ans["float_text"]
    assert trap.calls == []                                                     # never a new client, never Yahoo


def test_6_NEGATIVE_no_handle_answers_error_never_a_new_client(trap):
    class NoHandle:
        def coll(self, name):
            return None
    assert RR.shares_lookup(NoHandle())(SYM, fetch=True) == (None, "error")
    assert RR.shares_lookup(None)(SYM) == (None, "error")
    assert trap.calls == []


def test_6b_float_text_is_origin_aware():
    massive = CX._massive_read(17_900_000, NOW)
    chip = GT._float_chip(massive)
    passed = RR.float_text(massive, NOW, "pass")
    assert passed.startswith(WF.title(chip, NOW)) and "once a session" in passed
    run = RR.float_text(massive, NOW, "run")
    assert "once a session" not in run
    assert run == (RR.FLOAT_RUN_TEXT.format(text=chip["text"], source=RR.FLOAT_RUN_SOURCE_WORDS["shares_out_massive"])
                   + " · " + RR.FLOAT_NOT_FLOAT_TEXT)
    yf = CX._yf_read({"float_shares": 3_100_000, "shares_outstanding": 8_000_000}, "cached", NOW)
    assert RR.float_text(yf, NOW, "run") == WF.title(GT._float_chip(yf), NOW)
    small = CX._massive_read(1_400_000, NOW)                                    # under the cap: could not be admitted
    assert RR.FLOAT_NOT_FLOAT_TEXT not in RR.float_text(small, NOW, "run")
    assert set(RR.FLOAT_RUN_SOURCE_WORDS) <= set(WF.FLOAT_SOURCE_WORDS)
    assert RR.float_text(CX.unknown_float(NOW), NOW, "run") == "float unknown"


def _matrix():
    cap = GC.K8_MAX_FLOAT
    return {"none": {"shares": None, "src": None},
            "massive_above": {"shares": cap + 1, "src": "shares_out_massive"},
            "massive_equal": {"shares": cap, "src": "shares_out_massive"},
            "massive_under": {"shares": cap - 1, "src": "shares_out_massive"},
            "float_above": {"shares": cap + 1, "src": "float"},
            "yahoo_shares_out_above": {"shares": cap + 1, "src": "shares_out_yf"}}


@pytest.mark.parametrize("cap", [None, 5_000_000])
def test_6c_yahoo_could_admit_is_refine_orders_group_zero(monkeypatch, cap):
    if cap is not None:
        monkeypatch.setattr(GC, "K8_MAX_FLOAT", cap)
    plain = {"shares": 1_000_000, "src": "float"}
    pr = {"X": {"structure_alive": True, "change_pct": 1.0}, "Y": {"structure_alive": True, "change_pct": 9.0}}
    got = {}
    for name, fl in _matrix().items():
        order = CX.refine_order(["X", "Y"], {"X": fl, "Y": plain}, pr)
        assert (order[0] == "X") is RR.yahoo_could_admit(fl), name
        got[name] = RR.yahoo_could_admit(fl)
    assert got == {"none": True, "massive_above": True, "massive_equal": False, "massive_under": False,
                   "float_above": False, "yahoo_shares_out_above": False}


def _rs(fl):
    return D.read_all({"5m": FX.rs_frame(), "15m": None}, {"symbol": "RS", "float_read": fl})["reversal_squeeze"]


def test_6d_gate_text_says_the_structure_is_there_behind_the_float_gate():
    alive = RR.GATE_ALIVE_TEXT.format(label=GT._setup_label(SEC.RS_SETUP))
    massive = CX._massive_read(17_900_000, NOW)
    r = _rs(massive)
    assert r["state"] == "none" and r["meta"]["structure_alive"] is True and r["criteria"] == []
    blk = RR.setup_block(SEC.RS_SETUP, r, None, massive)
    assert blk["state_label"] == f"none — shares out 17.9M (Massive) > {GC.K8_MAX_FLOAT:,} · UNMEASURED"
    assert blk["gate_text"] == alive + " " + RR.GATE_SHARES_OUT_TEXT.format(text="shares out 17.9M (Massive)")
    unknown = CX.unknown_float(NOW)
    assert RR.gate_text(SEC.RS_SETUP, _rs(unknown), unknown) == alive + " " + RR.GATE_NO_FLOAT_TEXT
    big = FX.float_read(14_700_000)
    assert RR.gate_text(SEC.RS_SETUP, _rs(big), big) == alive                   # a real float: nothing about Yahoo


# ── (7)–(8) K11 and the ring words ───────────────────────────────────────────────────────────────────────────────
def test_7_k11_is_the_session_volume_of_the_frames_and_a_broke_read_under_the_floor_is_partial(monkeypatch):
    seen = []
    real = RR.grade

    def _spy(frames, ctx):
        seen.append((frames, dict(ctx)))
        return real(frames, ctx)
    monkeypatch.setattr(RR, "grade", _spy)
    w = World(loader=Loader(scale=0.5))
    ans = w.run()
    frames, ctx = seen[0]
    assert D.K11_CTX_KEY in ctx and ctx[D.K11_CTX_KEY] == B.session_volume(frames)
    assert ctx[D.K11_CTX_KEY] < GC.K11_MIN_SESSION_VOLUME
    bf = _by(ans)["bull_flag"]
    assert bf["state"] == "partial" and bf["state_label"].startswith(D.NOT_APLUS_REASON)
    k11 = [c for c in bf["criteria"] if c["key"] == D.K11_KEY]
    assert len(k11) == 1 and k11[0]["ok"] is False
    assert ans["volume_text"] == RR.VOLUME_TEXT.format(vol=int(ctx[D.K11_CTX_KEY]), w1=C.FRAME_WORDS["1m"],
                                                       t5="10:40", floor=int(GC.K11_MIN_SESSION_VOLUME))


def test_8_rang_recipe_no_ring_words_only_when_the_record_is_read():
    read = {"state": "triggered", "bars_since_entry": 2, "entry_bar_t": "2026-10-13 10:35", "criteria": []}
    fl = CX.unknown_float(NOW)
    no_ring = RR.setup_block("bull_flag", read, GT._rang({}, S, SYM, "bull_flag"), fl)["state_label"]
    assert GT.NO_RING_TEXT in no_ring
    unknown = RR.setup_block("bull_flag", read, GT._rang(None, S, SYM, "bull_flag"), fl)["state_label"]
    assert unknown == GT.state_label(read, None) and GT.NO_RING_TEXT not in unknown


# ── (9) reuse ────────────────────────────────────────────────────────────────────────────────────────────────────
class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def test_9_reuse_inside_the_window_on_the_same_closable_bar(world):
    ck = Clock()
    a = world.run(clock=ck)
    ck.t += C.RUN_REUSE_SEC - 1
    b = world.run(clock=ck)
    assert len(world.load.today_calls) == 1 and a["reused_text"] is None
    assert b["reused_text"] == RR.REUSED_TEXT.format(at="10:41:00", w5=C.FRAME_WORDS["5m"], sec=C.RUN_REUSE_SEC)
    assert {k: v for k, v in b.items() if k != "reused_text"} == {k: v for k, v in a.items() if k != "reused_text"}
    ck.t += 2                                                                   # past RUN_REUSE_SEC
    c = world.run(clock=ck)
    assert len(world.load.today_calls) == 2 and c["reused_text"] is None


def test_9_NEGATIVE_no_memo_across_a_bar_close(world):
    ck = Clock()
    assert world.run(now=at(10, 35, 25), clock=ck)["state"] == "ok"
    ck.t += 1
    b = world.run(now=at(10, 35, 40), clock=ck)                                 # 10:35 became closable
    assert len(world.load.today_calls) == 2 and b["reused_text"] is None and b["state"] == "ok"
    assert RR.closable_t5(at(10, 35, 25)) == "2026-10-13 10:30" and RR.closable_t5(at(10, 35, 40)) == "2026-10-13 10:35"


def test_9_closable_t5_is_the_frames_as_of_bar_and_moves_with_the_settle_constant(monkeypatch):
    fr = B.frames_for([SYM], S, NOW, load_day=Loader(), budget_sec=C.RUN_BUDGET_SEC, stats={})[SYM]
    assert RR.closable_t5(NOW) == fr.as_of_bar_t5 == "2026-10-13 10:40"
    monkeypatch.setattr(GC, "BAR_SETTLE_SEC", 90)
    assert RR.closable_t5(NOW) == "2026-10-13 10:35"


# ── (10) the loader ──────────────────────────────────────────────────────────────────────────────────────────────
def test_10_load_day_reads_the_cache_fetches_today_once_on_the_watch_breaker_and_writes_nothing(monkeypatch, trap):
    monkeypatch.setattr(dt, "_today_et", lambda: S)
    gets, fetches = [], []
    monkeypatch.setattr(dt, "_mongo_get_day", lambda sym, day: gets.append((sym, day)) or PRIOR_1M.copy())

    def _fetch(sym, a, b, cb=None):
        fetches.append((sym, a, b, cb))
        return TODAY_1M.copy()
    monkeypatch.setattr(dt, "_fetch_massive_minute", _fetch)
    fr = B.frames_for([SYM], S, NOW, load_day=RR.load_day, budget_sec=C.RUN_BUDGET_SEC, stats={})[SYM]
    assert gets == [(SYM, PREV)] and len(fetches) == 1 and fetches[0][:3] == (SYM, S, S)
    assert fetches[0][3] is WR.breaker() and fetches[0][3] is not dt._CB            # the Watch's OWN breaker [P2]
    puts = []
    monkeypatch.setattr(dt, "_mongo_put_day", lambda *a: puts.append(a))
    ref = B.frames_for([SYM], S, NOW, load_day=dt.load_intraday, budget_sec=C.RUN_BUDGET_SEC, stats={})[SYM]
    assert fr.by["5m"].t == ref.by["5m"].t and fr.by["5m"].c == ref.by["5m"].c and fr.by["5m"].v == ref.by["5m"].v
    assert fr.by["15m"].t == ref.by["15m"].t and fr.raw.equals(ref.raw)
    assert puts == [] and trap.calls == []


def test_10_NEGATIVE_a_prior_day_cache_miss_fetches_and_never_writes_the_cache(monkeypatch):
    monkeypatch.setattr(dt, "_today_et", lambda: S)
    monkeypatch.setattr(dt, "_mongo_get_day", lambda sym, day: None)
    fetched = []
    monkeypatch.setattr(dt, "_fetch_massive_minute", lambda sym, a, b, cb=None: fetched.append(a) or PRIOR_1M.copy())
    puts = []
    monkeypatch.setattr(dt, "_mongo_put_day", lambda *a: puts.append(a))
    assert RR.load_day(SYM, PREV) is not None and fetched == [PREV] and puts == []
    dt.load_intraday(SYM, PREV)
    assert len(puts) == 1                                                       # the loader RR does NOT use writes


# ── (11) the route ───────────────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture()
def wired(monkeypatch):
    import ollama_chat.api as OA
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)
    calls = []

    def _fake(symbol, now):
        calls.append((symbol, now))
        out = RR.answer("closed", "OMH", text=RR.CLOSED_TEXT.format(open=GC.PASS_OPEN_ET, close=GC.PASS_CLOSE_ET))
        out["as_of"] = {"x": float("nan")}
        return out
    monkeypatch.setattr(RR, "run", _fake)
    app = FastAPI()
    app.include_router(API.router)
    c = TestClient(app)
    c.calls = calls
    return c


def test_11_route_owner_post_strict_json_inside_to_thread(wired, monkeypatch):
    assert C.API_RUN_PATH == "/chart-maps/gajjala-watch/run/{symbol}"
    assert [(r.path, m) for r in API.router.routes for m in getattr(r, "methods", ())
            if r.path == C.API_RUN_PATH] == [(C.API_RUN_PATH, "POST")]
    seen = []
    real = asyncio.to_thread

    async def _spy(fn, *a, **k):
        seen.append(fn.__name__)
        return await real(fn, *a, **k)
    monkeypatch.setattr(API.asyncio, "to_thread", _spy)
    r = wired.post(C.API_PATH + "/run/omh", headers={"X-User-Email": OWNER})
    assert r.status_code == 200 and seen == ["_run_body"]
    body = _strict(r.text)
    assert body["state"] == "closed" and body["as_of"] == {"x": None} and tuple(body) == C.RUN_ANSWER_KEYS
    assert wired.calls[0][0] == "omh" and wired.calls[0][1].tzinfo is not None


@pytest.mark.parametrize("headers", [{"X-User-Email": OTHER}, {}])
def test_g_NEGATIVE_anyone_else_is_refused_and_the_engine_is_never_called(wired, headers):
    r = wired.post(C.API_PATH + "/run/OMH", headers=headers)
    assert r.status_code != 200 and wired.calls == []
    assert r.status_code == (404 if headers else 401)


def test_k_NEGATIVE_a_raising_engine_or_import_is_the_string_fallback(wired, monkeypatch):
    monkeypatch.setattr(RR, "run", lambda symbol, now: (_ for _ in ()).throw(RuntimeError("boom")))
    r = wired.post(C.API_PATH + "/run/OMH", headers={"X-User-Email": OWNER})
    assert r.status_code == 200
    body = _strict(r.text)
    assert body["state"] == "error" and body["text"] == C.RUN_ERROR_TEXT and body["setups"] == []
    assert body["title"] == C.RUN_TITLE_TEXT and body["note"] == C.RUN_NOTE_TEXT and tuple(body) == C.RUN_ANSWER_KEYS
    monkeypatch.setattr(C, "RUN_MODULE", "chart_maps.gajjala_watch.no_such_engine")
    assert _strict(API._run_body("OMH", NOW).decode()) == body


def test_api_imports_the_engine_lazily():
    src = Path(API.__file__).read_text(encoding="utf-8")
    assert "run_rules" not in "\n".join(ln for ln in src.splitlines() if re.match(r"^(import|from)\s", ln))
    assert "importlib.import_module(C.RUN_MODULE)" in src and C.RUN_MODULE == RR.__name__


# ── (12)–(14) ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_12_a_todays_auto_name_is_runnable():
    w = World(auto=["AUT"])
    ans = w.run("aut")
    assert ans["state"] == "ok" and ans["symbol"] == "AUT"
    assert RR.watch_names(w.db, NOW) == [SYM, "AUT"]


def test_13_a_memo_hit_returns_while_another_symbols_loader_is_blocked():
    entered, go = threading.Event(), threading.Event()

    def block(sym):
        if sym == "OTH":
            entered.set()
            assert go.wait(5)
    w = World(symbols=(SYM, "OTH"), loader=Loader(block=block))
    assert w.run()["state"] == "ok"
    out = {}
    t = threading.Thread(target=lambda: out.setdefault("oth", w.run("OTH")))
    t.start()
    try:
        assert entered.wait(5)
        hit = w.run()                                                           # GGA: memo, while OTH is blocked
        assert hit["reused_text"] and not go.is_set()
    finally:
        go.set()
        t.join(5)
    assert out["oth"]["state"] == "ok"


def test_13_the_same_symbol_twice_at_once_is_one_fetch():
    entered, go = threading.Event(), threading.Event()

    def block(sym):
        entered.set()
        assert go.wait(5)
    w = World(loader=Loader(block=block))
    out = []
    t1 = threading.Thread(target=lambda: out.append(w.run()))
    t1.start()
    assert entered.wait(5)
    t2 = threading.Thread(target=lambda: out.append(w.run()))
    t2.start()
    t2.join(0.2)                                                                # t2 waits on the symbol's lock
    go.set()
    t1.join(5)
    t2.join(5)
    assert len(w.load.today_calls) == 1 and [a["state"] for a in out] == ["ok", "ok"]
    assert sorted(bool(a["reused_text"]) for a in out) == [False, True]          # one read, one memo answer


def test_13_two_different_symbols_read_at_the_same_time():
    barrier = threading.Barrier(2, timeout=5)
    w = World(symbols=(SYM, "OTH"), loader=Loader(block=lambda sym: barrier.wait()))
    out = {}
    ts = [threading.Thread(target=lambda s=s: out.setdefault(s, w.run(s))) for s in (SYM, "OTH")]
    for t in ts:
        t.start()
    for t in ts:
        t.join(10)
    assert out[SYM]["state"] == "ok" and out["OTH"]["state"] == "ok"           # both were inside their loaders at once


def test_14_the_equality_probe_compare_returns_exactly_the_differing_rows():
    from scripts.gajjala_watch_run_rules_equality_probe import compare, k11_ratios
    same = D.criterion("k8_tennis", "tennis ball action", True, "drop", "need")
    run = {"state": "partial", "criteria": [same, D.criterion("k8_failed", "tried", True, "1 failed try today", "n"),
                                            D.criterion("k3_vol", "K3", True, "busiest bar 10", "n")]}
    stored = {"state": "partial", "criteria": [dict(same), D.criterion("k8_failed", "tried", True, "8 failed tries today",
                                                                       "n"), D.criterion("k8_base_len", "q", True)]}
    got = compare(run, stored)
    assert got["state_diff"] is False and [r["key"] for r in got["rows"]] == ["k3_vol", "k8_base_len", "k8_failed"]
    by = {r["key"]: r for r in got["rows"]}
    assert by["k3_vol"]["stored"] is None and by["k8_base_len"]["run"] is None
    assert by["k8_failed"]["run"]["value"] != by["k8_failed"]["stored"]["value"]
    assert compare(run, run) == {"state_diff": False, "label_diff": False, "rows": []}
    assert compare({"state": "none"}, stored)["state_diff"] is True
    assert k11_ratios([(99.0, 100.0), (None, 5), (5, 0), (1.0, 1.0)]) == {"n": 2, "min": 0.99, "median": 0.995,
                                                                          "max": 1.0}


def test_probe_scripts_summary_and_timed_runs(world, monkeypatch):
    from scripts import gajjala_watch_run_rules_probe as P
    assert P.summary([]) == {"n": 0, "min": None, "median": None, "max": None}
    assert P.summary([1.0, 3.0, 2.0]) == {"n": 3, "min": 1.0, "median": 2.0, "max": 3.0}
    real = RR.run
    monkeypatch.setattr(RR, "run", lambda s, now=None: real(s, now, db=world.db, store=world.store, load=world.load))
    rows = P.timed_runs(SYM, 2, NOW)
    assert [r["state"] for r in rows] == ["ok", "ok"] and len(world.load.today_calls) == 2   # _reset() between
    assert all(r["list_read"] and r["read_doc"] == "none" and r["float_origin"] == "run" for r in rows)


@pytest.mark.parametrize("name", ["gajjala_watch_run_rules_probe.py", "gajjala_watch_run_rules_equality_probe.py"])
def test_NEGATIVE_the_probes_write_nothing(name):
    src = (Path(__file__).resolve().parents[1] / "scripts" / name).read_text(encoding="utf-8")
    for bad in ("update_", "insert_", "delete_", "replace_", "_mongo_put_day", "upsert", "set_state", "bulk_write"):
        assert bad not in src, bad


# ── NEGATIVES ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_NEGATIVE_not_listed_reads_no_bars_and_no_read_doc(world, monkeypatch):
    reads = []
    monkeypatch.setattr(GST.GajjalaStore, "get_read", lambda self, *a: reads.append(a))
    ans = world.run("zzz")
    assert ans["state"] == "not_listed" and ans["text"] == RR.NOT_LISTED_TEXT.format(sym="ZZZ")
    assert world.load.calls == [] and reads == []


@pytest.mark.parametrize("bad", ["$OMH", "TOOLONGX", "", None, 5])
def test_b_NEGATIVE_a_malformed_symbol_reads_nothing(world, monkeypatch, bad):
    monkeypatch.setattr(RR, "watch_names", lambda *a, **k: (_ for _ in ()).throw(AssertionError("read")))
    ans = world.run(bad)
    assert ans["state"] == "bad_symbol" and ans["text"] == PL.store_text("bad_symbol", None)
    assert ans["symbol"] is None and ans["title"] == C.RUN_TITLE_TEXT and world.load.calls == []


@pytest.mark.parametrize("now", [datetime(2026, 10, 18, 12, 0, tzinfo=ET), at(3, 0), at(20, 6)])
def test_c_NEGATIVE_closed_answers_the_sentence_and_fetches_nothing(world, now):
    ans = world.run(now=now)
    assert ans["state"] == "closed" and world.load.calls == []
    assert ans["text"] == RR.CLOSED_TEXT.format(open=GC.PASS_OPEN_ET, close=GC.PASS_CLOSE_ET)


def test_c_the_closed_sentence_moves_with_the_constant(world, monkeypatch):
    assert world.run(now=at(4, 30))["state"] != "closed"                      # inside 04:00–20:05 (no bar yet)
    RR._reset()
    monkeypatch.setattr(GC, "PASS_OPEN_ET", "05:00")
    ans = world.run(now=at(4, 30))
    assert ans["state"] == "closed" and "05:00–" in ans["text"]


def test_d_NEGATIVE_no_prints_no_bars_and_a_provider_failure_never_memod():
    a = World(loader=Loader(today=False)).run()
    assert a["state"] == "no_prints" and a["text"] == RR.NO_PRINTS_TEXT.format(sym=SYM) and a["setups"] == []
    RR._reset()
    b = World(loader=Loader(prev=False, today=False)).run()
    assert b["state"] == "no_bars" and b["text"] == RR.NO_BARS_TEXT.format(sym=SYM)
    RR._reset()
    w = World(loader=Loader(raise_on=S))
    ck = Clock()
    f1, f2 = w.run(clock=ck), w.run(clock=ck)
    assert f1["state"] == f2["state"] == "failed" and f1["text"] == RR.FAILED_TEXT
    assert len(w.load.today_calls) == 2 and f2["reused_text"] is None and SYM not in RR._MEMO

    def provider(sym, day, force=False, include_premarket=True, include_afterhours=False):
        return dt._provider_failed()
    assert World(loader=provider).run()["state"] == "failed"


def test_d_a_memod_no_prints_carries_reused_text():
    w = World(loader=Loader(today=False))
    ck = Clock()
    w.run(clock=ck)
    again = w.run(clock=ck)
    assert again["state"] == "no_prints" and again["reused_text"] and len(w.load.today_calls) == 1


def test_e_NEGATIVE_a_none_read_never_prints_a_tick(world, monkeypatch):
    rs = _by(world.run())[SEC.RS_SETUP]
    assert rs["state"] == "none" and rs["criteria"] == [] and rs["state_label"].startswith("none — ")
    assert "no tennis ball action today" in rs["state_label"] and rs["tally_text"] is None
    assert rs["gate_text"] is None                                              # no structure → no gate sentence
    RR._reset()
    monkeypatch.setattr(D, "bull_flag", lambda *a, **k: (_ for _ in ()).throw(ValueError("x")))
    bf = _by(world.run())["bull_flag"]
    assert bf["state_label"] == "none — detector error · UNMEASURED" and bf["criteria"] == []
    unknown = CX.unknown_float(NOW)
    blk = RR.setup_block(SEC.RS_SETUP, _rs(unknown), None, unknown)
    assert blk["state_label"] == "none — float unknown · UNMEASURED" and not any(c["ok"] for c in blk["criteria"])


def test_e_NEGATIVE_gate_text_is_none_everywhere_else():
    small = FX.float_read(3_000_000)
    rows = _rs(small)
    assert rows["criteria"] and RR.gate_text(SEC.RS_SETUP, rows, small) is None       # 🎾 with rows
    alive_none = {"state": "none", "meta": {"structure_alive": True}, "criteria": []}
    for setup in GC.SETUPS:
        if setup == SEC.RS_SETUP:
            continue
        for st in D.STATES:
            for fl in (CX.unknown_float(NOW), CX._massive_read(17_900_000, NOW)):
                assert RR.gate_text(setup, dict(alive_none, state=st), fl) is None, (setup, st)
    for st in D.STATES:
        if st != "none":
            assert RR.gate_text(SEC.RS_SETUP, dict(alive_none, state=st), CX.unknown_float(NOW)) is None
    assert RR.gate_text(SEC.RS_SETUP, {"state": "none", "meta": {"structure_alive": False}}, None) is None
    assert RR.gate_text(SEC.RS_SETUP, {"state": "none"}, None) is None


def test_f_NEGATIVE_writes_nothing(monkeypatch, trap):
    import push.hooks as PH
    from chart_maps.gajjala import alerts as GA
    from chart_maps.gajjala import potential as GP
    from chart_maps.gajjala_watch import auto as AU
    from supply_demand import alert_status as AS
    monkeypatch.setattr(AS, "record_pass", trap.make("alert_status.record_pass"))
    for name in [n for n in dir(PH) if n.startswith("notify_")]:
        monkeypatch.setattr(PH, name, trap.make(f"push.hooks.{name}"))
    monkeypatch.setattr(GA, "run_pass", trap.make("alerts.run_pass"))
    monkeypatch.setattr(GP, "run_pass", trap.make("potential.run_pass"))
    monkeypatch.setattr(AU, "step", trap.make("auto.step"))
    monkeypatch.setattr(GST.GajjalaStore, "record_pass", trap.make("store.record_pass"))
    monkeypatch.setattr(dt, "_today_et", lambda: S)
    monkeypatch.setattr(dt, "_mongo_get_day", lambda sym, day: PRIOR_1M.copy())
    monkeypatch.setattr(dt, "_fetch_massive_minute", lambda sym, a, b, cb=None: TODAY_1M.copy())
    monkeypatch.setattr(CX, "_default_massive_lookup", lambda s: 17_900_000)
    w = World(auto=["AUT"], loader=None)
    w.load = None                                                               # the engine's OWN load_day
    for sym in (SYM, "AUT", "ZZZ", "$X"):
        RR.run(sym, NOW, db=w.db, store=w.store)
    assert RR.run(SYM, NOW, db=w.db, store=w.store)["state"] == "ok"
    assert all(c.writes == 0 for c in w.all_colls())
    assert trap.calls == []


def _src_tree():
    return ast.parse(SRC.read_text(encoding="utf-8"))


def _docstring_nodes(tree) -> set:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None) or []
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                out.add(id(body[0].value))
    return out


BANNED_MODULE = re.compile(r"(^|\.)(live_feed|live_hub|push\w*|alert_status|alerts|potential|break_watch)(\.|$)")
BANNED_ID = re.compile(r"^(update_one|update_many|insert_one|insert_many|replace_one|delete_one|delete_many|"
                       r"bulk_write|upsert_\w+|set_state|record_pass|notify_\w+|_mongo_put_day|claim_lease|open_read)$")


def test_f_NEGATIVE_source_guard_on_the_ast_skips_docstrings():
    tree = _src_tree()
    mods, ids = [], []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            mods += [n.module or ""] + [f"{n.module}.{a.name}" for a in n.names]
        elif isinstance(n, ast.Call) and getattr(n.func, "attr", getattr(n.func, "id", "")) == "import_module":
            mods += [a.value for a in n.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        elif isinstance(n, ast.Attribute):
            ids.append(n.attr)
        elif isinstance(n, ast.Name):
            ids.append(n.id)
    assert mods and not [m for m in mods if BANNED_MODULE.search(m)], mods
    assert not [i for i in ids if BANNED_ID.match(i)]
    assert "read_all" in ids and "frames_for" in ids                             # the pass's own calls
    doc = ast.get_docstring(tree)
    assert "no push" in doc and "On the Watch list I need a run button" in doc   # words in a docstring are fine


def test_h_NEGATIVE_switched_off_reads_nothing(world, monkeypatch):
    monkeypatch.setattr(C, "RUN_RULES_ON", False)
    monkeypatch.setattr(RR, "watch_names", lambda *a, **k: (_ for _ in ()).throw(AssertionError("read")))
    ans = world.run()
    assert ans["state"] == "off" and ans["text"] == RR.OFF_TEXT and world.load.calls == []


def test_i_NEGATIVE_a_raising_auto_engine_still_runs_his_names(world, monkeypatch):
    from chart_maps.gajjala_watch import auto as AU
    monkeypatch.setattr(AU, "current_symbols", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("auto down")))
    assert RR.watch_names(world.db, NOW) == [SYM]
    assert world.run()["state"] == "ok"


def _served_sentences():
    for name, v in vars(RR).items():
        if not name.isupper() or name in ("STATES", "ANSWER_KEYS", "SETUP_KEYS", "CRITERION_KEYS", "MEMO_STATES",
                                          "FLOAT_ORIGINS"):
            continue
        if isinstance(v, str):
            yield name, v
        elif isinstance(v, dict):
            for x in v.values():
                if isinstance(x, str):
                    yield name, x
    for name in ("RUN_TITLE_TEXT", "RUN_NOTE_TEXT", "RUN_ERROR_TEXT"):
        yield name, getattr(C, name)


def test_j_NEGATIVE_words_no_digit_no_b_word_no_email_no_ringer_claim(monkeypatch):
    from ollama_chat.api import PRIMARY_ADMIN_EMAIL
    bad = [(n, s) for n, s in _served_sentences() if re.search(r"[0-9]", re.sub(r"\{[^}]*\}", "", s))]
    assert bad == []
    for n, s in _served_sentences():
        assert not ("A+" in s and "ring" in s), n                               # no claim about who rings an A+
    assert not re.search("b" + "ounc", SRC.read_text(encoding="utf-8"), re.I)
    assert "@" not in SRC.read_text(encoding="utf-8")
    texts = json.dumps(_every_state(monkeypatch), default=str)
    assert PRIMARY_ADMIN_EMAIL not in texts and OWNER not in texts


def test_l_NEGATIVE_a_raising_float_chain_is_float_unknown_and_the_run_answers(world, monkeypatch):
    monkeypatch.setattr(CX, "floats_for", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("chain down")))
    fl, origin = RR.float_for(SYM, NOW, None, world.store)
    assert origin == "run" and fl["shares"] is None and fl["text"] == "float unknown"
    ans = world.run()
    assert ans["state"] == "ok" and ans["float_text"] == "float unknown"
    assert _by(ans)[SEC.RS_SETUP]["state"] == "none"


def test_m_NEGATIVE_busy_never_fetches_twice_and_is_never_memod(world, monkeypatch):
    monkeypatch.setattr(C, "RUN_BUDGET_SEC", 0.01)
    lk = RR._lock_for(SYM)
    lk.acquire()
    try:
        ans = world.run()
    finally:
        lk.release()
    assert ans["state"] == "busy" and ans["text"] == RR.BUSY_TEXT.format(sym=SYM) and world.load.calls == []
    assert SYM not in RR._MEMO
    assert world.run()["reused_text"] is None and len(world.load.today_calls) == 1


def test_reset_never_touches_the_watch_breaker():
    b = WR.breaker()
    RR._reset()
    assert WR.breaker() is b and RR._MEMO == {} and RR._LOCKS == {}


def test_constants_are_names_of_existing_constants():
    assert C.RUN_REUSE_SEC == GC.ON_DEMAND_REUSE_SEC and C.RUN_BUDGET_SEC == GC.ON_DEMAND_BUDGET_SEC
    assert C.RUN_RULES_ON is True and C.API_RUN_PATH == C.API_PATH + "/run/{symbol}"
    assert RR.NOTE_TEXT == C.RUN_NOTE_TEXT and RR.TITLE_NO_SYM == C.RUN_TITLE_TEXT
    src = (SRC.parent / "constants.py").read_text(encoding="utf-8")
    assert re.search(r"^RUN_REUSE_SEC = GC\.ON_DEMAND_REUSE_SEC\b", src, re.M)
    assert re.search(r"^RUN_BUDGET_SEC = GC\.ON_DEMAND_BUDGET_SEC\b", src, re.M)
