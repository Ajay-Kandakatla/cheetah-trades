"""🟢 Gajjala sub-tab entry marks + ✨ the 30-minute blinker (SPEC dots rev 2 §3.1–§3.4 / §4 WP-BE, 2026-11-12).

Ajay 2026-11-12 ~15:22 ET, verbatim: "Can you show me green on these tabs some indicators to show be which ones have best
potential entries right now I am clicking through each one and figuring out... an Indicator or new tickers with in last
30 mins like blinkers or something would be nice".

chart_maps/gajjala/entry_marks.py serves `entry_marks.subs.<sub>.{green,new}` and the shown tiles' `new_mark`; tab.py
gains banner_clock / read_of_pass (the 🎯 banner's ONE clock), is_entry_plan (ONE "entry plan" rule, read by plan_text),
the `carded` list and ONE `_soft` call. DISPLAY ONLY. NEGATIVES mandatory on every rule; the mutation cases at the end
prove the guards bite (and were also run as real source mutations with bytecode purged — see the doc).
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import entry_marks as EM
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from tests.test_gajjala_store import FakeColl, fake_store
from tests.test_gajjala_tab import NOW, PREV, R, S, latest, read_doc, scan_doc, utc

BF, KF, RS = "bull_flag", "kiss_fly", "reversal_squeeze"
OLD = utc(4, 5)                                      # first qualified long before NOW — never "new on his list"
B_WORD = re.compile("b" + "ounc", re.I)


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


# ── fixtures ─────────────────────────────────────────────────────────────────────────────────────────────────────
def aplus(**kw):
    return R(BF, "aplus", broke=True, entry_bar_t=kw.pop("entry_bar_t", "2026-10-13 10:30"), **kw)


def ready(setup=BF, **kw):
    return R(setup, "forming", ready=True, base={"bars": 2}, **kw)


def building(setup=BF, **kw):
    return R(setup, "forming", ready=False, base={"bars": 2}, **kw)


def scan(sym, first=OLD, day=S):
    d = scan_doc(sym, day)
    d["first_qualified_at"] = first
    return d


def step(at, state="forming", kind="armed"):
    return {"at": at.isoformat() if isinstance(at, datetime) else at, "at_et": GT._hhmm(at) if isinstance(at, datetime)
            else None, "state": state, "kind": kind, "bar_t": None}


def tracker(sym, setup, path, *, first=None, mode="normal"):
    first = first if first is not None else OLD
    return {"_id": ST.potential_key(S, sym, setup), "date": S.isoformat(), "symbol": sym, "setup": setup,
            "first_seen": first, "first_seen_et": GT._hhmm(first), "first_seen_mode": mode, "state_path": path}


def alert_doc(sym, setup=BF, at="2026-10-13T10:30:30-04:00"):
    """A live A+ claim as alerts.py leaves it (test_gajjala_defects_k11_words_2026_11_11.alert_doc shape)."""
    return {"_id": f"GG:{S.isoformat()}|{sym}|{setup}", "date": S.isoformat(), "symbol": sym, "setup": setup,
            "state": "pushed", "at": at, "mode": "live", "kind": GC.PUSH_KIND, "trigger": 4.12, "stop": 3.95}


def store(reads: dict, *, at=NOW, trackers=(), scans=None, alerts=(), passes=None, upd=None):
    """reads = {SYM: {setup: read}}; every read written by the pass at `at` unless `upd` = {SYM: stamp}."""
    upd = upd or {}
    docs = [read_doc(s, su, updated_at=upd.get(s, at), at=upd.get(s, at)) for s, su in reads.items()]
    return fake_store(**{ST.READS: FakeColl(docs),
                         ST.SCAN: FakeColl(list(scans) if scans is not None else [scan(s) for s in reads]),
                         ST.PASSES: FakeColl(list(passes) if passes is not None else [latest(at=at)]),
                         ST.ALERTS: FakeColl(list(alerts)), ST.POTENTIALS: FakeColl(list(trackers))})


def board(sub, st, now=NOW, **kw):
    return GT.build(sub, now=now, store=st, **kw)


def flag(st, *syms):
    st.coll(ST.STATE).docs[ST.BROKER_STATE_ID] = {"_id": ST.BROKER_STATE_ID, "added": list(syms), "removed": []}
    return st


def marks(out, sub=BF):
    return (out.get("entry_marks") or {}).get("subs", {}).get(sub) or {}


def tile_marks(out):
    return {t["symbol"]: t.get("new_mark") for t in out["tiles"]}


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield str(k)
            yield from _strings(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _strings(v)


# ── constants / module words ─────────────────────────────────────────────────────────────────────────────────────
def test_the_constant_is_his_30_and_the_switch_tuples_are_as_specced():
    assert GC.ENTRY_MARK_NEW_MIN == 30
    assert EM.GREEN_STATES == ("aplus", "ready")
    assert EM.BREAK_STATES == ("aplus", "triggered")
    assert EM.CHIP_NEW_KINDS == ("aplus", "ready", "armed")
    assert EM.SKIP_BROKER is True and EM.NEW_ON_LIST is True
    assert not GC.__dict__.get("POTENTIAL_ENTRY_MARK_NEW_MIN")              # NEGATIVE: never a POTENTIAL_ name


# ── green on a setup sub ─────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("read,word", [(aplus(), "A+ on the latest closed bar: AAA"),
                                       (ready(), "ready — the next bar over the trigger is the entry: AAA")],
                         ids=["aplus", "ready"])
def test_green_counts_an_entry_plan(read, word):
    out = board(BF, store({"AAA": {BF: read}}))
    g = marks(out)["green"]
    assert g["n"] == 1 and g["label"] == "1"
    assert g["title"].startswith("🟢 1 close to an entry — ") and word in g["title"]
    assert g["title"].endswith("display only — no order, count or alert changes · UNMEASURED")


@pytest.mark.parametrize("read", [R(BF, "partial", missed=["k2"]), building(), R(BF, "stopped", broke=True,
                                  entry_bar_t="2026-10-13 09:50"),
                                  R(BF, "triggered", broke=True, entry_bar_t="2026-10-13 09:50", bars_since_entry=8),
                                  R(BF, "invalid", reason="x")],
                         ids=["partial", "forming_not_ready", "stopped", "triggered_old", "invalid"])
def test_NEGATIVE_no_green_for_any_other_state(read):
    out = board(BF, store({"AAA": {BF: read}}))
    assert "green" not in marks(out)
    assert EM.kind_of(read) in (None, "triggered")


def test_NEGATIVE_held_aplus_on_the_audited_tab_is_never_green():
    held = dict(aplus(), state=GT._held_state())
    assert EM.kind_of(held) is None


def test_NEGATIVE_a_sub_with_only_partial_and_listed_cards_has_no_green_key_never_n_zero():
    st = store({"AAA": {BF: R(BF, "partial", missed=["k2"])}}, scans=[scan("AAA", first=utc(10, 21))])
    out = board(BF, st)
    m = marks(out)
    assert "green" not in m and "new" not in m and m == {}                # a sub key only with a block
    assert tile_marks(out)["AAA"]["kind"] == "listed"                       # the card still blinks (card only)
    assert '"n": 0' not in json.dumps(out["entry_marks"])


# ── [C2] is_entry_plan — ONE rule; no green / no ready mark on a no-risk plan ───────────────────────────────────
@pytest.mark.parametrize("trig,stop", [(0.31, 0.31), (0.31, 0.35)], ids=["trigger_eq_stop", "stop_above"])
def test_C2_NEGATIVE_no_risk_or_no_plan_ready_is_not_green_and_not_marked(trig, stop):
    r = ready(trigger=trig, stop=stop, risk_pct=0.0)
    assert GT.is_entry_plan(r) is False and EM.kind_of(r) is None
    st = store({"AAA": {BF: r}}, trackers=[tracker("AAA", BF, [step(utc(10, 26))])])
    out = board(BF, st)
    assert marks(out) == {}
    assert tile_marks(out)["AAA"] is None
    t = next(t for t in out["tiles"] if t["symbol"] == "AAA")
    assert t["gajjala"]["plan_text"].startswith(f"trigger {GT._px(trig)} · stop {GT._px(stop)}")


def test_C2_is_entry_plan_truth_and_plan_text_reads_it(monkeypatch):
    assert GT.is_entry_plan(ready()) is True and GT.is_entry_plan(aplus()) is True
    assert GT.is_entry_plan(ready(stop=None)) is False                     # NEGATIVE: stop missing
    assert GT.is_entry_plan(ready(trigger=None)) is False
    assert GT.is_entry_plan(building()) is False and GT.is_entry_plan(None) is False
    assert GT.plan_text(ready()) == "Entry above 4.12 · stop 3.95 · risk 4.1%"
    monkeypatch.setattr(GT, "_ledger", lambda: None)
    assert GT.is_entry_plan(ready()) is False                              # NEGATIVE: unloadable ledger
    assert GT.plan_text(ready()) == "trigger 4.12 · stop 3.95 · risk 4.1%"
    monkeypatch.setattr(GT, "is_entry_plan", lambda read: True)            # plan_text reads the ONE helper
    assert GT.plan_text(building()).startswith("Entry above")


def test_C2_NEGATIVE_a_brain_armed_no_risk_plan_is_not_green_on_brain():
    st = store({"AAA": {BF: ready(trigger=2.0, stop=2.0, risk_pct=0.0)}})
    out = board(GC.POTENTIAL_SUB, st)
    assert out["tiles"] and "green" not in marks(out, GC.POTENTIAL_SUB)


# ── triggered — NOT green by default; the one tuple adds it (HIS CALL #1) ───────────────────────────────────────
def test_triggered_is_not_green_by_default_and_the_switch_works(monkeypatch):
    trig = R(BF, "triggered", broke=True, entry_bar_t="2026-10-13 09:50", bars_since_entry=8)
    assert "green" not in marks(board(BF, store({"AAA": {BF: trig}})))
    monkeypatch.setattr(EM, "GREEN_STATES", EM.GREEN_STATES + ("triggered",))
    g = marks(board(BF, store({"AAA": {BF: trig}})))["green"]
    assert g["n"] == 1 and "triggered — broke earlier, still above its stop: AAA" in g["title"]


# ── [C1] the break blinker survives the A+ → triggered turn ─────────────────────────────────────────────────────
T = utc(10, 40)                                       # the entry bar 10:40 (its close label)
EB = "2026-10-13 10:40"


def _mo(read, now, **kw):
    return EM.mark_of(read, tracker=kw.get("tracker"), scan_doc=kw.get("scan_doc"), listed_info=kw.get("listed"),
                      session=S, now=now, rang=kw.get("rang"))


def test_C1_break_marks_from_the_entry_bar_close_through_the_triggered_read():
    m = _mo(aplus(entry_bar_t=EB), T + timedelta(minutes=1))
    assert m["kind"] == "aplus" and m["at_et"] == "10:40" and m["text"] == "new 10:40 ET"
    trig = R(BF, "triggered", broke=True, entry_bar_t=EB, bars_since_entry=1)
    m = _mo(trig, T + timedelta(minutes=5))
    assert m["kind"] == "aplus" and m["until"] == (T + timedelta(minutes=30)).isoformat()
    assert _mo(trig, T + timedelta(minutes=29, seconds=59)) is not None
    assert _mo(trig, T + timedelta(minutes=30)) is None                     # 30:00 exactly → gone
    assert _mo(trig, T + timedelta(minutes=31)) is None


@pytest.mark.parametrize("state", ["stopped", "partial", "invalid"])
def test_C1_NEGATIVE_a_stopped_partial_or_invalid_break_never_blinks_as_aplus(state):
    r = R(BF, state, broke=True, entry_bar_t=EB)
    assert _mo(r, T + timedelta(minutes=5)) is None


def test_C1_chip_new_counts_a_fresh_triggered_break_while_the_chip_has_no_green():
    now = T + timedelta(minutes=5)
    trig = R(BF, "triggered", broke=True, entry_bar_t=EB, bars_since_entry=1)
    out = board(BF, store({"AAA": {BF: trig}}, at=now), now=now)
    m = marks(out)
    assert "green" not in m
    assert m["new"]["n"] == 1 and m["new"]["until"] == (T + timedelta(minutes=30)).isoformat()
    assert m["new"]["title"].startswith("✨ new in the last 30 minutes — AAA A+ on the 10:40 ET bar")
    assert tile_marks(out)["AAA"]["kind"] == "aplus"


# ── 🧠 ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_brain_armed_is_green_building_is_not_and_one_symbol_counts_once():
    out = board(GC.POTENTIAL_SUB, store({"AAA": {BF: ready(), RS: ready(RS)}, "BBB": {BF: building()}}))
    g = marks(out, GC.POTENTIAL_SUB)["green"]
    assert g["n"] == 1 and "🧠 trigger armed — the next bar over the trigger is the entry: AAA" in g["title"]
    assert "BBB" not in g["title"]
    out = board(GC.POTENTIAL_SUB, store({"BBB": {BF: building()}}))
    assert "green" not in marks(out, GC.POTENTIAL_SUB)                      # NEGATIVE: building only


def test_brain_armed_mark_is_the_newest_armed_stamp_and_pulses_the_chip():
    st = store({"AAA": {BF: ready(), RS: ready(RS)}},
               trackers=[tracker("AAA", BF, [step(utc(10, 11))]), tracker("AAA", RS, [step(utc(10, 21))])])
    out = board(GC.POTENTIAL_SUB, st)
    m = tile_marks(out)["AAA"]
    assert m["kind"] == "armed" and m["at_et"] == "10:21" and "🧠 trigger armed since the 10:21 ET pass" in m["title"]
    assert marks(out, GC.POTENTIAL_SUB)["new"]["n"] == 1



def test_C2_NEGATIVE_a_brain_armed_no_risk_plan_never_blinks_or_pulses_the_chip():
    """REFIX 2026-11-12: the 🧠 armed blinker reads is_entry_plan like the green — trigger == stop → no card mark,
    no chip `new`, even with a fresh armed stamp."""
    st = store({"AAA": {BF: ready(trigger=2.0, stop=2.0, risk_pct=0.0)}},
               trackers=[tracker("AAA", BF, [step(utc(10, 21))])])
    out = board(GC.POTENTIAL_SUB, st)
    assert out["tiles"] and tile_marks(out)["AAA"] is None
    assert marks(out, GC.POTENTIAL_SUB) == {}


def test_C2_brain_armed_mark_skips_a_newer_no_risk_setup_and_keeps_the_planned_one():
    st = store({"AAA": {BF: ready(), RS: ready(RS, trigger=2.0, stop=2.0, risk_pct=0.0)}},
               trackers=[tracker("AAA", BF, [step(utc(10, 11))]), tracker("AAA", RS, [step(utc(10, 21))])])
    out = board(GC.POTENTIAL_SUB, st)
    m = tile_marks(out)["AAA"]
    assert m["kind"] == "armed" and m["at_et"] == "10:11"                  # NEGATIVE: never the no-risk 10:21 stamp
    assert marks(out, GC.POTENTIAL_SUB)["new"]["n"] == 1 and marks(out, GC.POTENTIAL_SUB)["green"]["n"] == 1


def test_MUTATION_dropping_the_plan_check_on_the_brain_blinker_is_caught(monkeypatch):
    st = lambda: store({"AAA": {BF: ready(trigger=2.0, stop=2.0, risk_pct=0.0)}},  # noqa: E731
                       trackers=[tracker("AAA", BF, [step(utc(10, 21))])])
    assert tile_marks(board(GC.POTENTIAL_SUB, st()))["AAA"] is None
    monkeypatch.setattr(GT, "is_entry_plan", GT._is_entry_read)
    assert tile_marks(board(GC.POTENTIAL_SUB, st()))["AAA"]["kind"] == "armed"

# ── rang words ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_rang_words_on_the_green_and_on_the_break_mark():
    st = store({"AAA": {BF: aplus()}, "BBB": {BF: aplus()}}, alerts=[alert_doc("AAA")])
    out = board(BF, st)
    g = marks(out)["green"]["title"]
    assert "AAA (alert rang 10:30 ET)" in g and "BBB (no alert rang)" in g
    tm = tile_marks(out)
    assert tm["AAA"]["title"].startswith("A+ on the 10:30 ET bar — alert rang 10:30 ET · ")
    assert tm["BBB"]["title"].startswith("A+ on the 10:30 ET bar — no alert rang · ")
    assert "AAA A+ on the 10:30 ET bar — alert rang 10:30 ET" in marks(out)["new"]["title"]


def test_NEGATIVE_shadow_page_says_no_rang_clause():
    st = store({"AAA": {BF: aplus()}}, alerts=[alert_doc("AAA")])
    out = board(BF, st, variant=V.GGA)
    g = marks(out)["green"]["title"]
    assert "alert rang" not in g and "A+ on the latest closed bar: AAA · display only" in g
    assert "alert rang" not in tile_marks(out)["AAA"]["title"]


def _apply_kw(st, now=NOW, **over):
    reads_by = {d["symbol"]: d for d in st.reads(S)}
    kw = dict(reads_by=reads_by, carded={BF: sorted(reads_by)}, pots=[], trackers={}, scan_by={}, listed={},
              session=S, now=now, pass_doc=st.latest_pass(), cron=None, in_window=True, v=None, lim=24,
              flags=frozenset())
    kw.update(over)
    return kw


def test_entries_is_called_at_most_once_and_only_when_needed():
    calls = []

    def ent():
        calls.append(1)
        return {}
    st = store({"AAA": {BF: aplus()}, "BBB": {BF: aplus()}})
    out = {"sub": BF, "tiles": []}
    EM.apply(out, **_apply_kw(st, entries=ent))
    assert len(calls) == 1 and "(no alert rang)" in out["entry_marks"]["subs"][BF]["green"]["title"]
    calls.clear()
    st = store({"AAA": {BF: ready()}, "BBB": {BF: R(BF, "partial")}})
    out = {"sub": BF, "tiles": []}
    EM.apply(out, **_apply_kw(st, entries=ent))
    assert calls == []                                                     # NEGATIVE: no green A+, no new break
    out = {"sub": BF, "tiles": []}
    EM.apply(out, **_apply_kw(store({"AAA": {BF: aplus()}}), entries=None))
    assert "rang" not in out["entry_marks"]["subs"][BF]["green"]["title"]  # entries None → no clause



def _count_alert_rows(monkeypatch, st):
    calls, real = [], st.alert_rows

    def counting(sessions):
        calls.append(list(sessions))
        return real(sessions)
    monkeypatch.setattr(st, "alert_rows", counting)
    return calls


@pytest.mark.parametrize("sub,variant", [("playbook", None), ("premarket", V.GG1)], ids=["playbook_gg5", "premarket_gg1"])
def test_NEGATIVE_no_aplus_and_no_fresh_break_reads_alert_rows_zero_times_off_the_setup_subs(monkeypatch, sub, variant):
    """REFIX 2026-11-12 (spec §6): on 📖 playbook and the 1-min ☀️ the ONE alert_rows read happens only when the marks
    need the rang clause (a green A+ or a fresh break). A day of ready + partial cards still reads 0 there; the same
    board with an A+ reads exactly once (the positive control — the pins moved 0→1 in the k11 + potential-tab files)."""
    st = store({"AAA": {BF: ready()}, "BBB": {BF: R(BF, "partial")}})
    calls = _count_alert_rows(monkeypatch, st)
    out = board(sub, st, variant=variant)
    assert calls == []
    assert marks(out).get("green", {}).get("n") == 1                         # the marks still served (ready = green)
    assert "rang" not in marks(out)["green"]["title"]
    st = store({"AAA": {BF: aplus()}})
    calls = _count_alert_rows(monkeypatch, st)
    out = board(sub, st, variant=variant)
    assert len(calls) == 1                                                    # control: a green A+ reads once
    assert "(no alert rang)" in marks(out)["green"]["title"]

# ── blinker windows + stored times ───────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("ago,new", [(timedelta(minutes=29), True), (timedelta(minutes=31), False),
                                     (timedelta(minutes=30), False), (timedelta(minutes=-1), False)],
                         ids=["29m", "31m", "30m_exact", "future"])
def test_ready_blinker_window(ago, new):
    m = _mo(ready(), NOW, tracker=tracker("AAA", BF, [step(NOW - ago)]))
    assert (m is not None and m["kind"] == "ready") is new


@pytest.mark.parametrize("trk", [None, tracker("AAA", BF, [step(NOW, kind="building")]), tracker("AAA", BF, []),
                                 tracker("AAA", BF, "junk"), tracker("AAA", BF, [step(NOW), "junk"])],
                         ids=["no_doc", "last_building", "empty_path", "junk_path", "junk_last"])
def test_NEGATIVE_no_stored_time_no_blinker_but_the_green_still_counts(trk):
    assert EM.ready_since(trk) is None
    st = store({"AAA": {BF: ready()}}, trackers=[trk] if trk else [])
    out = board(BF, st)
    assert marks(out)["green"]["n"] == 1 and "new" not in marks(out)
    assert tile_marks(out)["AAA"] is None


def test_joined_first_entry_never_blinks_a_later_armed_entry_does():
    first = NOW - timedelta(minutes=5)
    assert EM.ready_since(tracker("AAA", BF, [step(first)], mode="joined")) is None
    later = tracker("AAA", BF, [step(first), step(NOW - timedelta(minutes=4), kind="building"),
                                step(NOW - timedelta(minutes=2))], mode="joined")
    assert EM.ready_since(later) == NOW - timedelta(minutes=2)
    assert EM.ready_since(tracker("AAA", BF, [step(first)])) == first       # a normal doc's first entry counts


def test_naive_utc_and_iso_stamps_parse_and_a_naive_stamp_is_never_read_as_et():
    naive = datetime(2026, 10, 13, 14, 25)                                  # = 10:25 ET as naive UTC (Mongo)
    m = _mo(ready(), NOW, tracker=tracker("AAA", BF, [step(naive.replace(tzinfo=timezone.utc))]))
    assert m["at_et"] == "10:25"
    assert EM._utc(naive) == datetime(2026, 10, 13, 14, 25, tzinfo=timezone.utc)
    assert EM._utc("2026-10-13T14:25:00") == EM._utc("2026-10-13T14:25:00+00:00") == EM._utc(naive)
    assert GT._hhmm(EM._utc(naive)) == "10:25"                             # NEGATIVE: not 14:25 (read as ET)
    path = [{"at": naive, "state": "forming", "kind": "armed"}]
    assert _mo(ready(), NOW, tracker=dict(tracker("AAA", BF, []), state_path=path))["at_et"] == "10:25"
    assert EM._utc("not a stamp") is None and EM._utc(None) is None and EM._utc(12) is None


# ── new on his list (card only — [C5]) ──────────────────────────────────────────────────────────────────────────
def test_listed_today_marks_the_card_only_never_the_chip():
    st = store({"AAA": {BF: R(BF, "partial")}}, scans=[scan("AAA", first=NOW - timedelta(minutes=10))])
    out = board(BF, st)
    m = tile_marks(out)["AAA"]
    assert m["kind"] == "listed" and m["at_et"] == "10:21" and m["text"] == "new 10:21 ET"
    assert m["title"] == ("new on his list at 10:21 ET — first qualified his scanner today · marked new for 30 "
                          "minutes · display only")
    assert "new" not in marks(out)                                         # C5 NEGATIVE: no chip pulse


def test_NEGATIVE_carried_name_or_switch_off_never_blinks_listed(monkeypatch):
    fresh = NOW - timedelta(minutes=10)
    st = store({"AAA": {BF: R(BF, "partial")}}, scans=[scan("AAA", first=fresh), scan("AAA", first=fresh, day=PREV)])
    assert tile_marks(board(BF, st))["AAA"] is None                        # listed since yesterday (carried)
    monkeypatch.setattr(EM, "NEW_ON_LIST", False)
    st = store({"AAA": {BF: R(BF, "partial")}}, scans=[scan("AAA", first=fresh)])
    assert tile_marks(board(BF, st))["AAA"] is None


# ── [C7] 🧠 first-seen — only when he turns armed-only off; card only ───────────────────────────────────────────
def test_C7_first_seen_potential_blinks_only_when_armed_only_is_off(monkeypatch):
    trk = [tracker("BBB", BF, [step(NOW - timedelta(minutes=5), kind="building")], first=NOW - timedelta(minutes=5))]
    st = store({"BBB": {BF: building()}}, trackers=trk)
    assert GC.POTENTIAL_PUSH_ARMED_ONLY is True
    assert tile_marks(board(GC.POTENTIAL_SUB, st))["BBB"] is None
    monkeypatch.setattr(GC, "POTENTIAL_PUSH_ARMED_ONLY", False)
    out = board(GC.POTENTIAL_SUB, st)
    m = tile_marks(out)["BBB"]
    assert m["kind"] == "potential" and m["title"].startswith("first seen as a 🧠 potential at the 10:26 ET pass")
    assert "new" not in marks(out, GC.POTENTIAL_SUB)                       # card only
    trk_j = [dict(trk[0], first_seen_mode="joined")]
    assert tile_marks(board(GC.POTENTIAL_SUB, store({"BBB": {BF: building()}}, trackers=trk_j)))["BBB"] is None
    assert EM.first_on_potential({("BBB", BF): trk[0], ("BBB", RS): trk_j[0]}, "BBB") is None   # ANY joined


# ── [C6] past the card cut — the shown sub only, never changes n ────────────────────────────────────────────────
def test_C6_shown_sub_names_the_counted_cards_past_the_cut():
    st = store({"AAA": {BF: aplus(entry_bar_t="2026-10-13 10:30")}, "BBB": {BF: aplus(entry_bar_t="2026-10-13 10:25")}})
    out = board(BF, st, limit=1)
    assert [t["symbol"] for t in out["tiles"]] == ["AAA"]
    g = marks(out)["green"]
    assert g["n"] == 2 and "1 not among the 1 cards shown: BBB" in g["title"]
    assert "1 not among the 1 cards shown: BBB" in marks(out)["new"]["title"]
    assert "not among" not in json.dumps(marks(board(GC.POTENTIAL_SUB, st, limit=1), BF), ensure_ascii=False)
    assert "not among" not in json.dumps(marks(board(BF, st, limit=2)), ensure_ascii=False)


# ── the clock — the 🎯 banner's own "right now" ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("case", ["outside_window", "stale_cron", "no_pass_this_session"])
def test_NEGATIVE_no_marks_outside_the_banners_clock(case):
    reads = {"AAA": {BF: aplus()}, "BBB": {BF: ready()}}
    if case == "outside_window":
        now = utc(21, 30)
        out = board(BF, store(reads, at=utc(20, 1)), now=now)
    elif case == "stale_cron":
        out = board(BF, store(reads, at=utc(10, 0)), now=NOW)
    else:
        out = board(BF, store(reads, passes=[latest(day=PREV)]), now=NOW)
    assert out["entry_marks"] == {"subs": {}}
    assert all("new_mark" not in t for t in out["tiles"])


def test_NEGATIVE_a_read_not_of_the_shown_pass_is_not_counted():
    st = store({"AAA": {BF: aplus()}, "BBB": {BF: ready()}}, upd={"AAA": utc(10, 26)})
    g = marks(board(BF, st))["green"]
    assert g["n"] == 1 and "AAA" not in g["title"]


@pytest.mark.parametrize("in_window", [True, False])
@pytest.mark.parametrize("this_session", [True, False])
@pytest.mark.parametrize("cron_ok", [True, False])
def test_banner_clock_truth_table_matches_the_banner_rows(in_window, this_session, cron_ok):
    pass_at = NOW if cron_ok else utc(10, 0)
    lp = latest(at=pass_at, day=S if this_session else PREV)
    reads = {"AAA": read_doc("AAA", {BF: aplus()}, updated_at=pass_at)}
    g = GT.banner_clock(lp, NOW, in_window=in_window, session=S)
    assert g["live"] == (in_window and this_session and cron_ok)
    blk = GT.aplus_block(reads, lp, NOW, in_window=in_window, scan={}, session=S)
    assert bool(blk["rows"]) == g["live"]


def test_banner_clock_keeps_the_pre_split_rule():
    lp = latest()
    g = GT.banner_clock(lp, NOW, in_window=True, session=S)
    assert g["c_at"] == g["at"] == NOW and g["cron_ok"] and g["live"]
    od = latest(on_demand=True)
    g = GT.banner_clock(od, NOW, in_window=True, session=S)
    assert g["c_at"] is None and g["cron_ok"] is False and g["live"] is False   # NEGATIVE: an open alone is not live
    assert GT.read_of_pass({"updated_at": NOW}, NOW) and not GT.read_of_pass({"updated_at": NOW}, None)
    assert not GT.read_of_pass({}, NOW) and not GT.read_of_pass({"updated_at": NOW - timedelta(seconds=1)}, NOW)


# ── [C4] soft — a raising piece never takes the board down ──────────────────────────────────────────────────────
def _assert_board_without_marks(out):
    assert out["subs"] and out["counts"] and out["tiles"]
    assert "entry_marks" not in out and all("new_mark" not in t for t in out["tiles"])


def test_C4_banner_clock_raising_serves_the_board_without_marks(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("clock")
    monkeypatch.setattr(GT, "banner_clock", boom)
    out = board(BF, store({"AAA": {BF: aplus()}}))
    _assert_board_without_marks(out)
    assert out["enterable"] is None                                        # the 🎯 banner's own _soft default


def test_C4_an_import_failure_serves_the_board_without_marks(monkeypatch):
    import chart_maps.gajjala as PKG
    monkeypatch.delattr(PKG, "entry_marks")                                # the from-import then hits sys.modules
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala.entry_marks", None)
    _assert_board_without_marks(board(BF, store({"AAA": {BF: aplus()}})))


@pytest.mark.parametrize("target", ["apply", "new_block"])
def test_C4_a_raise_inside_apply_assigns_nothing(monkeypatch, target):
    def boom(*a, **k):
        raise RuntimeError(target)
    monkeypatch.setattr(EM, target, boom)
    _assert_board_without_marks(board(BF, store({"AAA": {BF: aplus()}})))


# ── 🚫 his names out, every viewer alike; nothing hidden ────────────────────────────────────────────────────────
def test_broker_names_are_left_out_for_every_viewer_and_never_hidden():
    def st():
        return flag(store({"AAA": {BF: aplus()}, "BBB": {BF: aplus()}}), "BBB")
    a, b = board(BF, st(), owner=True), board(BF, st(), owner=False)
    assert a["entry_marks"] == b["entry_marks"]
    assert tile_marks(a) == tile_marks(b)
    g = marks(a)["green"]
    assert g["n"] == 1 and "BBB" not in g["title"] and tile_marks(a)["BBB"] is None
    assert {t["symbol"] for t in a["tiles"]} == {t["symbol"] for t in b["tiles"]} == {"AAA", "BBB"}


# ── invariants: nothing else moves ───────────────────────────────────────────────────────────────────────────────
def _strip(out):
    out = json.loads(json.dumps(out))
    out.pop("entry_marks", None)
    for t in out["tiles"]:
        t.pop("new_mark", None)
    return out


@pytest.mark.parametrize("sub", [BF, RS, GC.POTENTIAL_SUB, "premarket", "playbook"])
def test_invariant_the_board_is_byte_identical_without_the_marks(monkeypatch, sub):
    def st():
        return store({"AAA": {BF: aplus()}, "BBB": {BF: ready(), RS: ready(RS)}, "CCC": {BF: R(BF, "partial")}},
                     trackers=[tracker("BBB", BF, [step(utc(10, 26))])],
                     scans=[scan("AAA"), scan("BBB"), scan("CCC", first=utc(10, 21))])
    with_marks = board(sub, st())
    monkeypatch.setattr(GT, "_entry_marks", lambda out, **kw: None)
    without = board(sub, st())
    assert "entry_marks" not in without
    assert _strip(with_marks) == json.loads(json.dumps(without))


def test_invariant_carded_is_n_tiles(monkeypatch):
    seen = {}
    real = EM.apply

    def spy(out, **kw):
        seen.update(kw)
        return real(out, **kw)
    monkeypatch.setattr(EM, "apply", spy)
    out = board(BF, store({"AAA": {BF: aplus(), RS: R(RS, "partial")}, "BBB": {BF: R(BF, "invalid")},
                           "CCC": {RS: ready(RS)}}))
    counts = {s["key"]: s["count"] for s in out["subs"]}
    for s in GC.SETUPS:
        assert len(seen["carded"].get(s, [])) == counts[s], s


# ── variants inherit through the ONE builder ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("variant", [V.GG1, V.GGA], ids=["gg1", "gga"])
def test_variants_serve_entry_marks_from_the_same_engine(variant):
    out = board(BF, store({"BBB": {BF: ready()}}), variant=variant)
    assert out["tab"] != "gajjala"
    assert marks(out)["green"]["n"] == 1


# ── served JSON: allow_nan=False, no b-word, no "buy" ────────────────────────────────────────────────────────────
def test_served_marks_are_plain_json_and_carry_no_banned_word():
    st = store({"AAA": {BF: aplus()}, "BBB": {BF: ready()}, "CCC": {BF: R(BF, "partial")}},
               trackers=[tracker("BBB", BF, [step(utc(10, 26))])], scans=[scan("AAA"), scan("BBB"),
                                                                         scan("CCC", first=utc(10, 21))])
    for sub in (BF, GC.POTENTIAL_SUB):
        out = board(sub, st)
        blob = {"em": out["entry_marks"], "tiles": [t.get("new_mark") for t in out["tiles"]]}
        json.dumps(blob, allow_nan=False)
        words = " ".join(_strings(blob))
        assert words and not B_WORD.search(words) and not re.search(r"\bbuy\b", words, re.I)
    module_words = " ".join([*EM.GREEN_WORDS.values(), *EM.NEW_WORDS.values(), EM.GREEN_HEAD, EM.GREEN_TAIL,
                             EM.NEW_HEAD, EM.NEW_TAIL, EM.NEW_TEXT, EM.PAST_WORD, EM.RANG_WORD])
    assert not B_WORD.search(module_words) and not re.search(r"\bbuy\b", module_words, re.I)


# ── mutation cases (the guards bite) ─────────────────────────────────────────────────────────────────────────────
def _green_n(read):
    return marks(board(BF, store({"AAA": {BF: read}}))).get("green", {}).get("n")


def test_MUTATION_kind_of_counting_partial_is_caught(monkeypatch):
    assert _green_n(R(BF, "partial")) is None
    real = EM.kind_of
    monkeypatch.setattr(EM, "kind_of", lambda r: "ready" if (r or {}).get("state") == "partial" else real(r))
    assert _green_n(R(BF, "partial")) == 1                                 # the NEGATIVE above would fail


def test_MUTATION_dropping_the_joined_guard_is_caught(monkeypatch):
    j = tracker("AAA", BF, [step(NOW - timedelta(minutes=5))], mode="joined")
    assert EM.ready_since(j) is None
    monkeypatch.setattr(EM.PT, "FIRST_SEEN_MODES", ("normal", "never-matches"))
    assert EM.ready_since(j) is not None


def test_MUTATION_dropping_triggered_from_break_states_is_caught(monkeypatch):
    trig = R(BF, "triggered", broke=True, entry_bar_t=EB, bars_since_entry=1)
    assert _mo(trig, T + timedelta(minutes=5)) is not None
    monkeypatch.setattr(EM, "BREAK_STATES", ("aplus",))
    assert _mo(trig, T + timedelta(minutes=5)) is None


def test_MUTATION_dropping_the_plan_check_is_caught(monkeypatch):
    r = ready(trigger=0.31, stop=0.31, risk_pct=0.0)
    assert _green_n(r) is None
    monkeypatch.setattr(GT, "is_entry_plan", GT._is_entry_read)
    assert _green_n(r) == 1
