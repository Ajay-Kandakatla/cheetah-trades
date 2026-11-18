"""⏹ The 🚩 Gajjala 1-minute page (GG1) RETIRED, reversibly — 2026-11-18 (SPEC retire-1m, WP-E).

Ajay 2026-11-18 ~00:10 ET, verbatim: "This is good info stop 1 min tab it was a good experiment"; ~00:20 ET: "But keep the
one min chart in the watch list I still want them".

What this module pins, with the switch AS SHIPPED (GC.GAJJALA_1M_ENABLED False — never monkeypatched to False here):
the ONE predicate `variant.enabled`; no spawn, no pass, no fetch, no store, no write [C5]; no A+ / 🧠 composed or sent;
the on-open 🔄 refused FIRST in every window with the retired sentence [C4]; the served words; the retired page opening on
its 🏁 WITH the today read on the first GET [C3]; the ℹ️ clause; the nightly still grading; no crontab line. Each test
ALSO flips the switch ON in-test and proves the 2026-10-27 … 2026-11-17 behaviour returns (reversibility).

GG5 / GGA bytes: tests/test_gajjala_variant_gg5_identity.py (the WRITES + BOARD goldens) is the proof and must pass
untouched; here only `enabled(GG5) and enabled(GGA)` and GG5 answers equal ON vs OFF. UNMEASURED — nothing here trades.
NEGATIVE cases are marked NEGATIVE.
"""
from __future__ import annotations

import copy
import json
import logging
import re
from datetime import date
from pathlib import Path

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import nightly as NI
from chart_maps.gajjala import on_demand as OD
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import run_1m as R1
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from push import hooks
from supply_demand import rules_info as RI
from tests.test_gajjala_potential import bf_armed, seed
from tests.test_gajjala_store import FakeColl, fake_store
from tests.test_gajjala_tab import run_route
from tests.test_gajjala_variant_2026_10_27 import _aplus, _frames, frame_1m, gg1_store
import tests.test_gajjala_1m_page_2026_10_27 as T1
import tests.test_gajjala_run_1m_2026_10_27 as TR

HIS_RETIRE = "This is good info stop 1 min tab it was a good experiment"
HIS_KEEP = "But keep the one min chart in the watch list I still want them"
B_WORD = "b" + "ounce"
OWNER = "owner-local-part" + chr(64) + "example.com"
OK_SEND = {"sent": 1, "failed": 0, "total_targets": 1}
CONSTANTS_SRC = Path(GC.__file__).read_text()
CRONTAB = Path(__file__).resolve().parents[1] / "crontab"
SUNDAY = date(2026, 10, 11)


class Raising:
    """A store whose EVERY attribute access fails — a retired path that touches it shows as a failure."""
    def __getattr__(self, name):
        raise AssertionError(f"the retired page touched the store: {name}")


class Rec:
    def __init__(self, ret=None):
        self.calls, self.ret = [], ret

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return self.ret(*a, **k) if callable(self.ret) else self.ret


def boom(*_a, **_k):
    raise AssertionError("reached while retired")


def on(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_1M_ENABLED", True)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.delenv("GAJJALA_1M_ENABLED", raising=False)
    monkeypatch.setattr(R1, "_PREV_MEMO", {})
    monkeypatch.setattr(ST, "_VARIANT_STORES", {})
    monkeypatch.setattr(OD, "_STATE", {"proc": None, "started_at": None})
    monkeypatch.setattr(OD, "_STATES", {})
    monkeypatch.setattr(R1, "_popen", lambda *a, **k: pytest.fail("a test reached the real spawn"))
    monkeypatch.setattr(OD, "_spawn", lambda *a, **k: pytest.fail("a test reached the real on-open spawn"))


# ── the switch ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_switch_is_off_on_main_and_his_words_are_on_the_line():
    line = next(ln for ln in CONSTANTS_SRC.splitlines() if ln.startswith("GAJJALA_1M_ENABLED ="))
    code, _sep, comment = line.partition("#")
    assert code.strip() == "GAJJALA_1M_ENABLED = False" and GC.GAJJALA_1M_ENABLED is False
    assert comment.strip().startswith("Ajay 2026-11-18") and HIS_RETIRE in comment and HIS_KEEP in comment
    r_line = next(ln for ln in CONSTANTS_SRC.splitlines() if ln.startswith("GAJJALA_1M_RETIRED_ON ="))
    assert r_line.partition("#")[2].strip().startswith("Ajay 2026-11-18")
    assert GC.GAJJALA_1M_RETIRED_ON == "2026-11-18"
    assert GC.GAJJALA_1M_PUSH_MODE == "live"                                   # NEGATIVE: the mode is NOT the lever
    assert len([ln for ln in CONSTANTS_SRC.splitlines() if re.match(r"GAJJALA_1M_ENABLED\s*=", ln)]) == 1


def test_enabled_is_one_predicate(monkeypatch):
    assert V.enabled(V.GG1) is False and V.enabled(V.GG5) is True and V.enabled(V.GGA) is True
    assert V.enabled() is True                                                 # None → GG5
    assert R1.enabled() is V.enabled(V.GG1) is False
    assert V.enabled(gg1_store()[0]) is False and V.enabled(fake_store()) is True   # a store answers by its variant
    monkeypatch.setenv("GAJJALA_1M_ENABLED", "1")
    assert V.enabled(V.GG1) is False                     # NEGATIVE: the env can never turn it ON over the constant
    on(monkeypatch)
    assert V.enabled(V.GG1) is True and R1.enabled() is True                   # reversible: one word
    monkeypatch.setenv("GAJJALA_1M_ENABLED", "0")
    assert V.enabled(V.GG1) is False and R1.enabled() is False                 # NEGATIVE: env "0" still stops it
    assert V.enabled(V.GG5) is True and V.enabled(V.GGA) is True               # NEGATIVE: the env is GG1-only


# ── no spawn, no pass, no fetch, no write ────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_the_cron_pass_spawns_no_1m_child(monkeypatch, caplog):
    spawn = Rec(True)
    monkeypatch.setattr(R1, "spawn_loop", spawn)
    with caplog.at_level(logging.INFO, logger="chart_maps.gajjala.run"):
        RUN._spawn_1m()
    assert spawn.calls == []
    assert any("not spawned" in r.getMessage() and "retired 2026-11-18" in r.getMessage() for r in caplog.records)
    on(monkeypatch)
    RUN._spawn_1m()
    assert len(spawn.calls) == 1                                               # reversible: ON spawns once


def test_NEGATIVE_the_pass_entry_and_the_loop_return_without_a_store_a_fetch_or_a_write(monkeypatch):
    loads = []

    def load_day(*a, **k):
        loads.append(a)
        raise AssertionError("a retired iteration fetched bars")
    d = TR.deps(load_day=load_day)
    monkeypatch.setattr(ST, "for_variant", boom)
    monkeypatch.setattr(RUN, "dry_store", boom)
    for kw in ({}, {"dry": True}, {"on_demand": True}):
        out = R1.run_iteration(TR.NOW, store=Raising(), deps=d, **kw)
        assert out["ran"] is False and out["reason"] == "off" == R1.LOOP_REASONS[2], (kw, out)
        out = R1.run_iteration(TR.NOW, deps=d, **kw)                           # no store handed → none constructed
        assert out["reason"] == "off", kw
    assert R1.run_on_demand(TR.NOW, store=Raising(), deps=d)["reason"] == "off"
    assert loads == [] and d.send.calls == [] and d.send_potential.calls == [] and d.record_status.calls == []
    monkeypatch.setattr(R1, "run_iteration", boom)
    out = R1.loop(TR.at(10, 31, 10), store=Raising(), deps=d)                  # a set_state would raise: no _end write
    assert out["reason"] == "off" and out["iterations"] == [] and out["n"] == 0
    out = R1.loop(TR.at(10, 31, 10), deps=d)                                   # ST.for_variant raises: no store built
    assert out["reason"] == "off" and out["iterations"] == []
    fs = fake_store()
    fs.variant = V.GG1
    R1.loop(TR.at(10, 31, 10), store=fs, deps=d)
    assert fs.get_state(R1.LOOP_STATE_ID) == {}                                # NEGATIVE: no "loop" doc [C5]


def test_on_the_pass_entry_runs_again(monkeypatch):
    on(monkeypatch)
    monkeypatch.setattr(GC, "GAJJALA_1M_PUSH_MODE", "shadow")
    db, _shared, st = TR.world(monkeypatch)
    out = R1.run_iteration(TR.NOW, store=st, deps=TR.deps())
    assert out["ran"] is True and out["status"] == "ok" and out["n_read"] == 1     # reversible: the 10-27 iteration
    assert "gajjala_1m_reads" in db and db["gajjala_1m_reads"].docs


# ── no push composed or sent ─────────────────────────────────────────────────────────────────────────────────────
def _own():
    return {n: FakeColl() for n in ST.OWN}


def _snap(own):
    return {n: (copy.deepcopy(c.docs), c.writes) for n, c in own.items()}


def test_NEGATIVE_no_gg1_push_is_composed_or_sent(monkeypatch):
    monkeypatch.setattr(hooks, "notify_gajjala_1m_setup", boom)
    monkeypatch.setattr(hooks, "notify_gajjala_1m_potential", boom)
    monkeypatch.setattr(AL, "compose", boom)
    monkeypatch.setattr(PT, "compose", boom)
    monkeypatch.setattr(ST, "broker_flags", boom)
    own = _own()
    st, shared = gg1_store(**own)
    before = _snap(own)
    send = Rec(OK_SEND)
    for sender in (send, None):                                                # a handed sender AND the default one
        out = AL.run_pass({"GGA": {"bull_flag": _aplus()}}, _frames(), TR.at(10, 41), TR.S, store=st, owner=OWNER,
                          send=sender, ctx={"GGA": {"price": 11.1}})
        assert out["off"] == 1 and all(out[k] == 0 for k in AL.COUNT_KEYS), out
        assert set(out) == set(AL.COUNT_KEYS) | {"off"}
        now = TR.at(10, 6)
        pot = PT.run_pass({"BBB": {"bull_flag": bf_armed()}}, {"BBB": frame_1m(now)}, now, TR.S, store=st,
                          ctx={"BBB": {}}, rows={"BBB": {"volume": 2_000_000, "price": 11.2}}, owner=OWNER, tape="rth",
                          send=sender)
        assert pot["off"] == 1 and all(pot[k] == 0 for k in PT.COUNT_KEYS), pot
    assert send.calls == [] and _snap(own) == before and st.alerts_coll().docs == {}   # nothing written anywhere
    for fn in (AL._default_send, PT._default_send):
        with pytest.raises(RuntimeError) as ei:
            fn("o", {}, V.GG1)
        assert str(ei.value) == V.RETIRED_NEVER_SENDS
    from chart_maps.gajjala.audited_rules import NEVER_SENDS
    with pytest.raises(RuntimeError, match=re.escape(NEVER_SENDS)):            # NEGATIVE: GGA's refusal unchanged
        AL._default_send("o", {}, V.GGA)


def test_NEGATIVE_the_guard_is_gg1_only_gg5_counts_equal_on_and_off(monkeypatch):
    def gg5_counts():
        st = fake_store()
        a = AL.run_pass({"GGA": {"bull_flag": _aplus(frame="5m")}}, _frames(), TR.at(10, 41), TR.S, store=st,
                        owner=OWNER, send=Rec(OK_SEND), ctx={"GGA": {"price": 11.1}})
        seed(st)
        now = TR.at(10, 6)
        p = PT.run_pass({"BBB": {"bull_flag": bf_armed()}}, {"BBB": frame_1m(now)}, now, TR.S, store=st,
                        ctx={"BBB": {}}, rows={"BBB": {"volume": 2_000_000, "price": 11.2}}, owner=OWNER, tape="rth",
                        send=Rec(OK_SEND))
        docs = {i: {k: v for k, v in d.items() if k != "claimed_at"}                # the wall clock of the claim
                for i, d in st.alerts_coll().docs.items()}
        return json.dumps([a, p], sort_keys=True), json.dumps(docs, sort_keys=True, default=str)
    off = gg5_counts()
    assert "off" not in json.loads(off[0])[0] and "off" not in json.loads(off[0])[1]
    on(monkeypatch)
    assert gg5_counts() == off


def test_on_the_gg1_aplus_claims_and_rings_once(monkeypatch):
    on(monkeypatch)
    seen = []
    monkeypatch.setattr(hooks, "notify_gajjala_1m_setup", lambda **k: seen.append(k) or OK_SEND)
    st, _shared = gg1_store()
    out = AL.run_pass({"GGA": {"bull_flag": _aplus()}}, _frames(), TR.at(10, 41), TR.S, store=st, owner=OWNER,
                      ctx={"GGA": {"price": 11.1}})
    assert out["pushed"] == 1 and "off" not in out
    assert len(seen) == 1 and seen[0]["payload"]["kind"] == "gajjala_1m_setup"


# ── the on-open 🔄 [C4] ──────────────────────────────────────────────────────────────────────────────────────────
def _g1_with_cron():
    return TR._with_cron(ST.GajjalaStore(colls={n: FakeColl() for n in ST.ALL}, variant=V.GG1, shared=fake_store()),
                         TR.at(10, 31, 10))


@pytest.mark.parametrize("when", [TR.at(10, 34, 10), TR.at(3, 0), TR.at(20, 30), TR.at(11, 0, d=SUNDAY)])
def test_NEGATIVE_the_on_open_refuses_first_in_every_window_without_a_child(monkeypatch, when):
    st = _g1_with_cron()
    monkeypatch.setattr(st, "lease_state", boom)
    monkeypatch.setattr(OD, "_closed", boom)                                  # the refusal sits BEFORE the closed word
    spawn = TR.Spawn()
    r = OD.request(when, store=st, spawn=spawn, variant=V.GG1)
    assert tuple(r) == OD.RESPONSE_KEYS and r["state"] == "refused"
    assert r["text"] == V.word("scan_retired", V.GG1) and HIS_RETIRE in r["text"]
    assert "market closed" not in r["text"] and "store error" not in r["text"]
    assert (r["eta_sec"], r["poll_sec"], r["wait_max_sec"]) == (None, None, None)
    assert spawn.calls == [] and OD._STATES.get("gajjala_1m", {}).get("proc") is None


def test_NEGATIVE_gg5_on_open_is_byte_identical_on_and_off(monkeypatch):
    def answers():
        out = []
        for t in (TR.at(10, 34, 10), TR.at(3, 0), TR.at(11, 0, d=SUNDAY)):
            OD._STATE.update(proc=None, started_at=None)
            out.append(json.dumps(OD.request(t, store=TR._with_cron(fake_store(), TR.at(10, 31, 10)),
                                             spawn=TR.Spawn()), default=str, sort_keys=True))
        OD._STATE.update(proc=None, started_at=None)
        return out
    off = answers()
    assert [json.loads(a)["state"] for a in off] == ["started", "closed", "closed"]
    on(monkeypatch)
    assert answers() == off


def test_on_the_gg1_on_open_follows_the_10_27_order(monkeypatch):
    on(monkeypatch)
    r = OD.request(TR.at(11, 0, d=SUNDAY), store=_g1_with_cron(), spawn=TR.Spawn(), variant=V.GG1)
    assert r["state"] == "closed"                                              # reversible: closed on a Sunday
    spawn = TR.Spawn()
    r = OD.request(TR.at(10, 34, 10), store=_g1_with_cron(), spawn=spawn, variant=V.GG1)
    assert r["state"] == "started" and len(spawn.calls) == 1


# ── the served words ─────────────────────────────────────────────────────────────────────────────────────────────
WORD_KEYS = ("title", "honesty", "push", "push_potential", "ledger_title", "ledger_honesty", "ledger_empty")


def test_served_words_follow_the_switch(monkeypatch):
    for k in WORD_KEYS:
        w = V.word(k, V.GG1)
        assert w and "2026-11-18" in w, k
        assert "rings your phone" not in w and "ring your phone since" not in w, k     # NEGATIVE: nothing rings
        assert "until you say so" not in w and B_WORD not in w.lower(), k
        assert "{" not in w, k
    for k in ("honesty", "ledger_honesty", "retired", "scan_retired", "rules_clause"):
        assert HIS_RETIRE in V.word(k, V.GG1), k
    assert HIS_KEEP in V.word("retired", V.GG1)
    card = V.word("card_1m_empty", V.GG1, sym="ABC")
    assert "ABC" in card and "retired 2026-11-18" in card and "👀" in card
    assert V.served_block(V.GG1)["retired"] == {"on": "2026-11-18", "text": V.word("retired", V.GG1)}
    assert V.served_block(V.GG1)["title"] == V.word("title", V.GG1) and "RETIRED 2026-11-18" in V.word("title", V.GG1)
    assert V.served_block(V.GG5) is None
    assert set(V.WORDS_1M_RETIRED) - set(V.WORDS_1M) == {"retired", "scan_retired", "rules_clause", "card_1m_empty"}
    for k in ("title", "honesty", "push"):                                      # NEGATIVE: GGA never retired
        assert "RETIRED" not in V.word(k, V.GGA) and "2026-11-18" not in V.word(k, V.GGA)

    def gga_words():
        out = {}
        for k in V.words(V.GGA):
            try:
                out[k] = V.word(k, V.GGA)
            except (KeyError, IndexError, ValueError):
                out[k] = "needs kwargs"
        return out, V.served_block(V.GGA)
    gga_off = gga_words()
    monkeypatch.setattr(GC, "GAJJALA_1M_PUSH_MODE", "shadow")                  # retired FIRST, before the shadow swap
    assert V.word("honesty", V.GG1) == V.WORDS_1M_RETIRED["honesty"].format(
        s=5, p=1, **{"from": GC.GG1M_RECORD_FROM, "retired_on": GC.GAJJALA_1M_RETIRED_ON})
    monkeypatch.setattr(GC, "GAJJALA_1M_PUSH_MODE", "live")
    on(monkeypatch)                                                            # reversible: the 10-29 words return
    assert gga_words() == gga_off
    assert V.word("title", V.GG1) == V.WORDS_1M["title"].format(p=1)
    assert "ring your phone since 2026-10-29" in V.word("honesty", V.GG1)
    assert "retired" not in V.served_block(V.GG1)
    for k in ("retired", "scan_retired", "rules_clause", "card_1m_empty"):
        assert V.word(k, V.GG1, sym="ABC") is None, k
    monkeypatch.setattr(GC, "GAJJALA_1M_PUSH_MODE", "shadow")                  # the 10-29 precedence pinned under ON
    assert "until you say so" in V.word("honesty", V.GG1) and "until you say so" in V.word("push", V.GG1)


# ── the retired page opens on its 🏁 with the today read [C3] ────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def stores():
    with pytest.MonkeyPatch.context() as mp:                                   # the fixture day is how the page RAN
        mp.setattr(GC, "GAJJALA_1M_ENABLED", True)
        return T1.day()


def test_default_sub_is_one_helper(monkeypatch):
    assert GT.default_sub("", "", V.GG1) == GC.LEDGER_SUB
    assert GT.default_sub("  ", None, V.GG1) == GC.LEDGER_SUB
    assert GT.default_sub("bull_flag", "", V.GG1) is None                     # NEGATIVE: an explicit sub wins
    assert GT.default_sub("", "ABC", V.GG1) is None                           # NEGATIVE: a focus deep link keeps 10-27
    assert GT.default_sub("", "", V.GG5) is None and GT.default_sub("", "") is None
    assert GT.default_sub("", "", V.GGA) is None
    on(monkeypatch)
    assert GT.default_sub("", "", V.GG1) is None                              # reversible


def test_the_retired_page_opens_on_its_track_record(stores, monkeypatch):
    _g5, g1, *_ = stores
    out = GT.build("", variant=V.GG1, store=g1, now=T1.NOW)
    assert out["sub"] == GC.LEDGER_SUB and out["sub_resolved_from"] == "default"
    assert out["variant"]["retired"]["on"] == "2026-11-18"
    assert out["track_record"]["title"] == V.word("ledger_title", V.GG1)
    bf = GT.build("bull_flag", variant=V.GG1, store=g1, now=T1.NOW)
    assert bf["sub"] == "bull_flag" and bf["sub_resolved_from"] == "param"     # NEGATIVE: an explicit sub serves
    on(monkeypatch)
    back = GT.build("", variant=V.GG1, store=g1, now=T1.NOW)
    assert back["sub"] == GC.DEFAULT_SUB and "retired" not in back["variant"]  # reversible


def test_the_route_reads_today_once_on_the_first_landing(stores, monkeypatch):
    from chart_maps import api as API
    g5, g1, *_ = stores
    T1._route_env(monkeypatch, g5, g1)
    tr = Rec(ret=None)
    monkeypatch.setattr(LG, "today_read", tr)

    def get(**k):
        args = dict(sub="", tf="", focus="", sort="", limit=3, span="")
        args.update(k)
        return json.loads(run_route(API.chart_maps_gajjala_1m(**args)).body)
    body = get()
    assert tr.calls == [((None,), {"span": "", "store": g1})]                 # ONCE, on the GG1 store
    assert body["sub"] == GC.LEDGER_SUB and body["variant"]["retired"]["on"] == "2026-11-18"
    get(focus="ABC")
    assert len(tr.calls) == 1, "NEGATIVE: a focus deep link reads no today bars"
    get(sub="bull_flag")
    assert len(tr.calls) == 1, "NEGATIVE: another sub reads no today bars"
    g5_body = json.loads(run_route(API.chart_maps_gajjala(sub="", tf="", focus="", sort="", limit=3,
                                                          span="")).body)
    assert len(tr.calls) == 1 and g5_body["sub"] == GC.DEFAULT_SUB             # NEGATIVE: GG5's route untouched
    on(monkeypatch)
    body = get()
    assert len(tr.calls) == 1 and body["sub"] == GC.DEFAULT_SUB                # reversible: the 10-27 landing


# ── the ℹ️ clause ────────────────────────────────────────────────────────────────────────────────────────────────
def test_rules_clause_says_retired(monkeypatch):
    c = RI._gg_one_minute_clause()
    assert c == " " + V.word("rules_clause", V.GG1)
    assert "RETIRED 2026-11-18" in c and "👀 Watch" in c and HIS_RETIRE in c and B_WORD not in c.lower()
    assert "ring your phone" not in c                                          # NEGATIVE: the live half is gone
    on(monkeypatch)
    assert RI._gg_one_minute_clause() == (
        " 🚩 1-minute page: the same rules on CLOSED 1-minute bars (the Fade on 5-minute first), about once a minute "
        "over the same list — a Cheetah variant by your call (2026-10-27); its alerts ring your phone since 2026-10-29 "
        "by your call; from 2026-10-27 until then they were recorded in shadow, never sent.")


# ── GG5 / GGA, nightly, crontab ──────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_gg5_goldens_byte_equal():
    """The proof is tests/test_gajjala_variant_gg5_identity.py (the GG5 WRITES golden runs alerts.run_pass +
    potential.run_pass on GG5; the BOARD golden builds all ten subs) — it must pass untouched. Here: every guard reads
    `variant.enabled`, which is True for GG5 and GGA whatever the GG1 switch says."""
    assert V.enabled(V.GG5) and V.enabled(V.GGA) and not V.enabled(V.GG1)
    assert GT.default_sub("", "", V.GG5) is None


def test_NEGATIVE_nightly_still_grades_gg1_pending_rows(monkeypatch):
    g1 = ST.GajjalaStore(colls={n: FakeColl() for n in ST.ALL}, variant=V.GG1, shared=fake_store())
    seen = []
    monkeypatch.setattr(LG, "grade_step", lambda store, now, **k: (seen.append(store), {"n": 1})[1])
    assert NI.grade_1m(TR.NOW, store=g1) == {"grade": {"n": 1}}               # not skipped by the switch
    assert seen == [g1]


def test_NEGATIVE_the_crontab_has_no_1m_line():
    lines = CRONTAB.read_text().splitlines()
    assert not [ln for ln in lines if re.search(r"run_1m|gajjala-1m|gajjala_1m", ln) and not ln.lstrip().startswith("#")]
    run = [ln for ln in lines if re.search(r"-m market_hours\.gate chart_maps\.gajjala\.run(\s|$)", ln)]
    assert len(run) == 1 and run[0].split()[:5] == ["1-56/5", "4-20", "*", "*", "1-5"]
    assert not [ln for ln in lines if "GAJJALA_1M_ENABLED" in ln]               # the constant governs; no env line
