"""🧭 Setup stages on every Gajjala card — stages.py + tab._stage_tag (2026-11-11, spec WP-ST-BE).

Ajay 2026-11-11 ~08:39 ET, verbatim: "Another big thing I need is what stages a stock has crossed in the past like
Bullflag -> EMA Kiss and Fly -> and Horizontal -Fade so I know their stages may be add them like tags or some UI to show
me stages with time stamps if its same day".

Display only: the 🧠 tracker's `state_path` folded into one tag per (session, symbol, setup), with the live A+ alerts
that RANG (tab._entry_times) merged where the path has no A+ step. Clocks only for today's session. NEGATIVES are
mandatory: nothing is invented (no A+ without a tracker step or a rang live claim), nothing else on the board moves, a
fault serves the board without stages, the reads stay O(1) per board.
"""
from __future__ import annotations

import ast
import copy
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from catalysts.medical.alerts import SHADOW_CLAIM_PREFIX
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import scanner as SC
from chart_maps.gajjala import stages as SG
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from tests.test_gajjala_store import FakeColl, fake_store
from tests.test_gajjala_tab import ET, NOW, PREV, R, S, latest, read_doc, scan_doc, utc

BF, KF, HF, VCP, RS = GC.SETUPS
P2 = SC._window(S)[2]                                  # the listing window's third session (2026-10-09, a Friday)
CLOCK = re.compile(r"\d\d:\d\d")
B_WORD = re.compile("b" + "ounc", re.I)
OTHER = re.compile(r"\bSEPA\b|minervini", re.I)
SRC = Path(SG.__file__)


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


# ── helpers ───────────────────────────────────────────────────────────────────────────────────────────────────────
def e(hhmm, state, kind=None):
    return {"at": "x", "at_et": hhmm, "state": state, "kind": kind, "bar_t": None}


def pdoc(d, sym, setup, path, **kw):
    """A hand 🧠 tracker doc shaped as potential.track writes it (the tracker contract test pins the shape)."""
    doc = {"_id": ST.potential_key(d, sym, setup), "date": d.isoformat(), "symbol": sym, "setup": setup,
           "first_seen_et": path[0]["at_et"] if path else None, "state_path": list(path)}
    doc.update(kw)
    return doc


def claim(d, sym, setup, hh, mm, *, state="pushed", prefix="GG:", suffix=""):
    """An A+ claim in gajjala_alerts (the live line = a `GG:` id, state pushed, no `#`)."""
    return {"_id": f"{prefix}{d.isoformat()}|{sym}|{setup}{suffix}", "date": d.isoformat(), "symbol": sym,
            "setup": setup, "state": state, "at": utc(hh, mm, d).isoformat(), "trigger": 4.12, "stop": 3.95}


def raw(*rows):
    return [{"stage": s, "word": SG.STAGE_WORDS[s], "at_et": at} for s, at in rows]


READS = {
    "AAA": {BF: R(BF, "aplus", entry_bar_t="2026-10-13 10:25", broke=True), KF: R(KF, "partial", missed=["k2"])},
    "BBB": {BF: R(BF, "forming", ready=True, trigger=4.10)},
    "CCC": {BF: R(BF, "forming", ready=True, trigger=4.50)},
    "DDD": {BF: R(BF, "aplus", entry_bar_t="2026-10-13 10:30", broke=True)},
}
POTS = [
    pdoc(S, "AAA", BF, [e("09:52", "forming", "building"), e("09:57", "forming", "armed"), e("10:01", "partial"),
                        e("10:03", "forming", "building"), e("10:06", "aplus"), e("10:11", "triggered")]),
    pdoc(S, "AAA", KF, [e("09:40", "forming", "building"), e("10:05", "partial")]),
    pdoc(PREV, "AAA", HF, [e("11:00", "forming", "armed"), e("13:00", "stopped")]),
    pdoc(P2, "AAA", VCP, [e("10:00", "forming", "building")]),
    pdoc(S, "CCC", HF, [e("10:20", "forming", "armed"), e("10:25", "partial"), e("10:28", "graveyard")]),
    pdoc(S, "DDD", BF, [e("10:00", "forming", "building")]),     # reads say A+, the tracker has no A+ step (C6)
]


def board_store(*, reads=None, pots=None, alerts=()):
    reads = READS if reads is None else reads
    return fake_store(**{ST.READS: FakeColl([read_doc(s, r) for s, r in reads.items()]),
                         ST.SCAN: FakeColl([scan_doc(s) for s in reads]), ST.PASSES: FakeColl([latest()]),
                         ST.POTENTIALS: FakeColl(list(POTS if pots is None else pots)),
                         ST.ALERTS: FakeColl(list(alerts))})


def build(sub, st, **kw):
    return GT.build(sub, now=kw.pop("now", NOW), store=st, **kw)


def tile(out, sym):
    return next(t for t in out["tiles"] if t["symbol"] == sym)


def stages_of(out, sym):
    return tile(out, sym)["gajjala"].get("stages")


def strip_stages(out):
    o = copy.deepcopy(out)
    for t in o.get("tiles") or []:
        if isinstance(t, dict) and isinstance(t.get("gajjala"), dict):
            t["gajjala"].pop("stages", None)
    return o


def keys_of(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from keys_of(v)
    elif isinstance(o, list):
        for v in o:
            yield from keys_of(v)


def strings_of(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield str(k)
            yield from strings_of(v)
    elif isinstance(o, list):
        for v in o:
            yield from strings_of(v)


class Count:
    """Wraps a store method on ONE instance and counts its calls (with the args)."""

    def __init__(self, fn, fail_on=None, answer=...):
        self.fn, self.calls, self.fail_on, self.answer = fn, [], fail_on, answer

    def __call__(self, *a, **k):
        self.calls.append(a)
        if self.fail_on is not None and self.fail_on(*a):
            raise RuntimeError("mongo down")
        if self.answer is not ...:
            return self.answer
        return self.fn(*a, **k)


def counted(st):
    st.potentials = Count(st.potentials)
    st.alert_rows = Count(st.alert_rows)
    return st


# ── engine: stage_of / clock_of ──────────────────────────────────────────────────────────────────────────────────
def test_stage_of_maps_building_and_armed_to_potential_and_milestones_to_themselves():
    assert SG.stage_of(e("09:00", "forming", "building")) == "potential"
    assert SG.stage_of(e("09:00", "forming", "armed")) == "potential"
    for s in ("aplus", "triggered", "stopped"):
        assert SG.stage_of(e("09:00", s)) == s


@pytest.mark.parametrize("entry", [e("09:00", "partial"), e("09:00", "invalid"), e("09:00", "none"),
                                   e("09:00", "graveyard"), e("09:00", "forming", None), e("09:00", "forming", "x"),
                                   "aplus", None, 7, {}, {"state": None}, {"kind": "armed"}])
def test_NEGATIVE_stage_of_never_steps(entry):
    assert SG.stage_of(entry) is None


def test_clock_of():
    assert SG.clock_of("09:52") == "09:52"
    for bad in ("9:5", None, 930, "", "09:52:00", "ab:cd"):
        assert SG.clock_of(bad) is None, bad


# ── engine: steps fold ───────────────────────────────────────────────────────────────────────────────────────────
def test_fold_building_armed_and_potential_partial_potential_print_once_at_the_first_time():
    d = {"state_path": [e("09:52", "forming", "building"), e("09:57", "forming", "armed"), e("10:01", "partial"),
                        e("10:03", "forming", "building")]}
    assert SG.steps(d) == raw(("potential", "09:52"))


def test_fold_keeps_the_ladder_and_a_second_leg():
    d = {"state_path": [e("09:52", "forming", "building"), e("10:06", "aplus"), e("10:11", "triggered"),
                        e("10:20", "stopped"), e("10:40", "forming", "armed"), e("10:45", "aplus")]}
    assert SG.steps(d) == raw(("potential", "09:52"), ("aplus", "10:06"), ("triggered", "10:11"),
                              ("stopped", "10:20"), ("potential", "10:40"), ("aplus", "10:45"))


def test_NEGATIVE_a_path_of_only_partial_invalid_is_empty_and_junk_is_skipped():
    assert SG.steps({"state_path": [e("09:00", "partial"), e("09:05", "invalid"), "x", None]}) == []
    assert SG.steps(None) == [] and SG.steps({}) == [] and SG.steps({"state_path": "nope"}) == []


def test_NEGATIVE_a_malformed_at_et_is_none_never_printed():
    st = SG.steps({"state_path": [e("9:5", "forming", "building")]})
    assert st == raw(("potential", None))
    t = SG.tag(BF, st, clock=True)
    assert t["text"] == "🚩 Bull Flag · 🧠 potential" and not CLOCK.search(t["text"])


# ── engine: steps merge (C1) ─────────────────────────────────────────────────────────────────────────────────────
def test_merge_huhu_replica_an_aplus_that_rang_before_the_tracker_doc():
    d = {"state_path": [e("17:01", "forming", "armed"), e("18:01", "partial"), e("04:01", "graveyard")]}
    assert SG.steps(d, entry_at="14:46") == raw(("aplus", "14:46"), ("potential", "17:01"))


def test_merge_appends_after_and_inserts_before_a_later_step():
    d = {"state_path": [e("10:31", "forming", "armed")]}
    assert SG.steps(d, entry_at="10:41") == raw(("potential", "10:31"), ("aplus", "10:41"))
    d = {"state_path": [e("10:31", "forming", "armed"), e("10:46", "triggered")]}
    assert SG.steps(d, entry_at="10:41") == raw(("potential", "10:31"), ("aplus", "10:41"), ("triggered", "10:46"))


def test_merge_claim_only():
    assert SG.steps(None, entry_at="11:02") == raw(("aplus", "11:02"))


def test_NEGATIVE_a_path_with_its_aplus_is_never_changed_by_the_claim():
    d = {"state_path": [e("10:31", "forming", "armed"), e("10:41", "aplus")]}
    assert SG.steps(d, entry_at="10:40") == raw(("potential", "10:31"), ("aplus", "10:41"))


def test_NEGATIVE_no_merge_without_a_clock_and_no_aplus_invented_pmax():
    d = {"state_path": [e("10:31", "forming", "armed")]}
    assert SG.steps(d, entry_at=None) == SG.steps(d, entry_at="9:5") == raw(("potential", "10:31"))
    pmax = {"state_path": [e("13:36", "forming", "building"), e("14:21", "stopped")]}
    assert SG.steps(pmax) == raw(("potential", "13:36"), ("stopped", "14:21"))
    assert SG.steps(None) == [] and SG.steps(None, entry_at="") == []


# ── engine: tag / sort_key ───────────────────────────────────────────────────────────────────────────────────────
def test_tag_words_come_from_the_subs_and_the_clock_switch():
    r = raw(("potential", "10:31"), ("aplus", "10:41"))
    for setup in GC.SETUPS:
        t = SG.tag(setup, r, clock=True)
        assert (t["emoji"], t["label"]) == GT.SUB_META[setup]
        assert t["text"] == f"{t['emoji']} {t['label']} · 🧠 potential 10:31 · 🎯 A+ 10:41"
    t = SG.tag(BF, r, clock=False)
    assert all(s["at_et"] is None for s in t["steps"]) and not CLOCK.search(t["text"])
    assert t["text"] == "🚩 Bull Flag · 🧠 potential · 🎯 A+"
    assert r[0]["at_et"] == "10:31"                                   # the raw steps are never blanked in place


def test_NEGATIVE_tag_unknown_setup_or_no_step():
    r = raw(("potential", "10:31"))
    for bad in ("premarket", "postmarket", "potential", "track_record", "", None):
        assert SG.tag(bad, r, clock=True) is None
    assert SG.tag(BF, [], clock=True) is None


def test_sort_key_orders_by_first_clock_then_setups_order():
    keys = [SG.sort_key(raw(("potential", "10:00")), RS), SG.sort_key(raw(("potential", "09:00")), VCP),
            SG.sort_key(raw(("potential", "10:00")), BF), SG.sort_key(raw(("potential", None)), BF)]
    assert sorted(keys) == [keys[1], keys[2], keys[0], keys[3]]


def test_NEGATIVE_naive_aware_first_seen_and_no_clock_never_raise_and_no_clock_sorts_last():
    naive = datetime(2026, 10, 13, 9, 30)
    aware = datetime(2026, 10, 13, 13, 40, tzinfo=timezone.utc)
    docs = [pdoc(S, "AAA", BF, [e("10:00", "forming", "building")], first_seen=naive),
            pdoc(S, "AAA", KF, [e("09:40", "forming", "armed")], first_seen=aware),
            pdoc(S, "AAA", HF, [e(None, "forming", "armed")], first_seen=None)]
    out = SG.by_symbol({S: docs}, board_session=S, is_today=True, symbols={"AAA"}, cadence_min=5)
    assert [t["setup"] for t in out["AAA"]["groups"][0]["tags"]] == [KF, BF, HF]
    src = SRC.read_text(encoding="utf-8")
    assert "fromisoformat" not in src and "strptime" not in src


# ── engine: by_symbol / for_tile ─────────────────────────────────────────────────────────────────────────────────
def window_docs():
    return {P2: [d for d in POTS if d["date"] == P2.isoformat()], PREV: [d for d in POTS if d["date"] == PREV.isoformat()],
            S: [d for d in POTS if d["date"] == S.isoformat()]}


def test_by_symbol_groups_oldest_first_today_with_clocks():
    out = SG.by_symbol(window_docs(), board_session=S, is_today=True, symbols={"AAA"}, cadence_min=5)
    b = out["AAA"]
    assert b["title"] == SG.TITLE == "🧭 Setup stages" and b["sep"] == SG.TAG_SEP == " → "
    assert [(g["date"], g["label"], g["clock"]) for g in b["groups"]] == [
        (P2.isoformat(), "Fri 10-09", False), (PREV.isoformat(), "Mon 10-12", False), (S.isoformat(), "today", True)]
    assert b["text"] == ("Fri 10-09: 🌀 Intraday VCP · 🧠 potential → Mon 10-12: ➖ Horizontal Fade · 🧠 potential · "
                         "stopped → today: 💋 EMA Kiss & Fly · 🧠 potential 09:40 → 🚩 Bull Flag · 🧠 potential 09:52 · "
                         "🎯 A+ 10:06 · triggered 10:11")
    assert b["hint"] == SG.hint(5) and "5-minute pass" in b["hint"] and SG.BORROWED_TEXT not in b["hint"]


def test_C4_not_today_the_board_session_shows_its_date_and_no_clock():
    for is_today in (False, True):
        b = SG.by_symbol(window_docs(), board_session=S, is_today=is_today, symbols={"AAA"}, cadence_min=5)["AAA"]
        for g in b["groups"][:-1]:                                    # NEGATIVE: an earlier session never has a clock
            assert g["clock"] is False and not any(CLOCK.search(t["text"]) for t in g["tags"])
            assert all(s["at_et"] is None for t in g["tags"] for s in t["steps"])
    b = SG.by_symbol(window_docs(), board_session=S, is_today=False, symbols={"AAA"}, cadence_min=5)["AAA"]
    last = b["groups"][-1]
    assert (last["label"], last["clock"]) == (SG.day_label(S), False) == ("Tue 10-13", False)
    assert not CLOCK.search(b["text"])


def test_by_symbol_claim_only_tag_and_entries_none():
    ent = {(S.isoformat(), "ZZZ", RS): "11:02", (S.isoformat(), "QQQQ", RS): "11:03"}
    out = SG.by_symbol({S: []}, board_session=S, is_today=True, symbols={"ZZZ"}, cadence_min=5, entries=ent)
    assert set(out) == {"ZZZ"}                                       # NEGATIVE: a symbol not on a card → nothing
    assert out["ZZZ"]["groups"][0]["tags"][0]["text"] == "🎾 Reversal Squeeze · 🎯 A+ 11:02"
    a = SG.by_symbol(window_docs(), board_session=S, is_today=True, symbols={"AAA"}, cadence_min=5, entries=None)
    b = SG.by_symbol(window_docs(), board_session=S, is_today=True, symbols={"AAA"}, cadence_min=5, entries={})
    assert a == b


def test_NEGATIVE_by_symbol_reads_only_what_it_is_handed():
    gone = pdoc(date(2026, 10, 8), "AAA", RS, [e("10:00", "forming", "armed")])
    docs = window_docs()
    docs[S] = docs[S] + [gone]                                         # a doc dated outside the dict, filed under S
    out = SG.by_symbol(docs, board_session=S, is_today=True, symbols={"AAA", "NOPE"}, cadence_min=5,
                       entries={("2026-10-08", "AAA", RS): "10:00"})
    assert "NOPE" not in out
    assert all(t["setup"] != RS for g in out["AAA"]["groups"] for t in g["tags"])
    assert "2026-10-08" not in {g["date"] for g in out["AAA"]["groups"]}
    out = SG.by_symbol(docs, board_session=S, is_today=True, symbols={"BBB"}, cadence_min=5)
    assert out == {}                                                  # a symbol with zero tags has no entry
    junk = {S: [pdoc(S, "BBB", BF, [e("10:00", "partial")]), None, "x", {"symbol": "BBB"}]}
    assert SG.by_symbol(junk, board_session=S, is_today=True, symbols={"BBB"}, cadence_min=5) == {}


def test_by_symbol_first_doc_wins_on_a_dup_id():
    a = pdoc(S, "AAA", BF, [e("09:00", "forming", "armed")])
    b = pdoc(S, "AAA", BF, [e("09:30", "stopped")])
    out = SG.by_symbol({S: [a, b]}, board_session=S, is_today=True, symbols={"AAA"}, cadence_min=5)
    assert out["AAA"]["groups"][0]["tags"][0]["text"] == "🚩 Bull Flag · 🧠 potential 09:00"


def test_for_tile_marks_here_only_on_the_cards_setup_in_the_board_session():
    b = SG.by_symbol(window_docs(), board_session=S, is_today=True, symbols={"AAA"}, cadence_min=5)["AAA"]
    before = copy.deepcopy(b)
    t = SG.for_tile(b, BF, S)
    here = [(g["date"], x["setup"]) for g in t["groups"] for x in g["tags"] if x["here"]]
    assert here == [(S.isoformat(), BF)]
    t = SG.for_tile(b, VCP, S)                                        # NEGATIVE: VCP was on P2, not the board session
    assert not any(x["here"] for g in t["groups"] for x in g["tags"])
    for setup in ("premarket", "postmarket", None):                  # ☀️ / 🌙 cards: none
        t = SG.for_tile(b, setup, S)
        assert all(x["here"] is False for g in t["groups"] for x in g["tags"])
    assert b == before                                                # NEGATIVE: the input block is never mutated


# ── pins ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_pins_milestones_day_label_and_imports():
    assert SG.MILESTONE_STATES == GT.MARKED_STATES
    assert SG.STAGES == ("potential", "aplus", "triggered", "stopped")
    d0 = date(2026, 11, 9)
    for i in range(7):
        d = d0 + timedelta(days=i)
        assert SG.day_label(d) == LG._dow_md(d)
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mods.add(("." * n.level) + (n.module or "") + ":" + ",".join(a.name for a in n.names))
    assert mods == {"__future__:annotations", "copy", "re", "datetime:date", "typing:Optional", ".:constants"}


def _pin_ok(words) -> bool:
    for s in SG.MILESTONE_STATES:
        pill = GT.state_label({"state": s, "trigger": 1.0, "stop": 0.9, "bars_since_entry": 1,
                               "entry_bar_t": "2026-10-13 10:25"})
        if words[s].split()[-1] != pill.split()[0]:
            return False
    return True


def test_C7_tag_words_match_the_card_pill_and_the_pin_catches_a_drift():
    assert _pin_ok(SG.STAGE_WORDS)
    assert not _pin_ok(dict(SG.STAGE_WORDS, triggered="fired"))      # NEGATIVE: a drifted word goes red
    assert not _pin_ok(dict(SG.STAGE_WORDS, aplus="🎯 A plus"))


def test_tracker_contract_a_real_track_run_feeds_steps():
    st = fake_store()
    forming = R(BF, "forming", ready=False)
    seq = [(utc(9, 52), forming, "building"), (utc(9, 57), dict(forming, ready=True), "armed"),
           (utc(10, 6), R(BF, "aplus", broke=True), None), (utc(10, 11), R(BF, "triggered", broke=True), None)]
    for when, read, kind in seq:
        PT.track(st, S, "AAA", BF, read, kind, when, px=4.0, values={})
    doc = st.get_potential(S, "AAA", BF)
    assert len(doc["state_path"]) == 4
    assert SG.steps(doc) == raw(("potential", "09:52"), ("aplus", "10:06"), ("triggered", "10:11"))


# ── wiring: tab.build ────────────────────────────────────────────────────────────────────────────────────────────
def test_a_card_gets_three_groups_over_the_window_and_the_card_setup_is_here():
    out = build(BF, board_store())
    b = stages_of(out, "AAA")
    assert [g["date"] for g in b["groups"]] == [P2.isoformat(), PREV.isoformat(), S.isoformat()]
    today = b["groups"][-1]
    assert [(t["setup"], t["here"]) for t in today["tags"]] == [(KF, False), (BF, True)]
    assert today["tags"][1]["text"] == "🚩 Bull Flag · 🧠 potential 09:52 · 🎯 A+ 10:06 · triggered 10:11"
    assert b["groups"][0]["tags"][0]["text"] == "🌀 Intraday VCP · 🧠 potential"      # the prev2 read happened
    assert b["hint"] == SG.hint(5)


def test_NEGATIVE_a_card_with_no_tracker_doc_and_no_claim_has_no_stages_key():
    out = build(BF, board_store())
    assert "stages" not in tile(out, "BBB")["gajjala"]


def test_C1_a_live_claim_merges_the_aplus_the_path_lacks():
    st = board_store(alerts=[claim(S, "CCC", HF, 10, 12)])
    b = stages_of(build(BF, st), "CCC")
    assert b["groups"][-1]["tags"][0]["text"] == "➖ Horizontal Fade · 🎯 A+ 10:12 · 🧠 potential 10:20"


@pytest.mark.parametrize("bad", [
    claim(S, "CCC", HF, 10, 12, state="shadow", prefix=SHADOW_CLAIM_PREFIX + "GG:"),
    claim(S, "CCC", HF, 10, 12, state="shadow"),
    claim(S, "CCC", HF, 10, 12, state="claimed"),
    claim(S, "CCC", HF, 10, 12, state="failed"),
    claim(S, "CCC", HF, 10, 12, suffix="#aplus"),
])
def test_NEGATIVE_C1_a_claim_that_is_not_the_live_line_adds_no_step(bad):
    b = stages_of(build(BF, board_store(alerts=[bad])), "CCC")
    assert b["groups"][-1]["tags"][0]["text"] == "➖ Horizontal Fade · 🧠 potential 10:20"


def test_NEGATIVE_C6_reads_say_aplus_tracker_has_none_no_claim_nothing_invented():
    out = build(BF, board_store())
    g = tile(out, "DDD")["gajjala"]
    assert g["state_label"].startswith("A+")                                   # the card's pill says A+
    assert g["stages"]["groups"][-1]["tags"][0]["text"] == "🚩 Bull Flag · 🧠 potential 10:00"
    assert all(s["stage"] != "aplus" for gr in g["stages"]["groups"] for t in gr["tags"] for s in t["steps"])


def _many(n):
    reads = {f"S{i:02d}": {BF: R(BF, "forming", ready=True)} for i in range(n)}
    pots = [pdoc(S, s, BF, [e("10:00", "forming", "armed")]) for s in reads]
    return reads, pots


@pytest.mark.parametrize("n", [1, 30])
def test_C2_reads_are_O1_per_board_as_a_delta(n, monkeypatch):
    reads, pots = _many(n)
    on = counted(board_store(reads=reads, pots=pots))
    out_on = build(BF, on, limit=GC.TILE_LIMIT_MAX)
    assert sum(1 for t in out_on["tiles"] if "stages" in t["gajjala"]) == min(n, GC.TILE_LIMIT_MAX)
    real = GT._stage_tag
    monkeypatch.setattr(GT, "_stage_tag", lambda *a, **k: None)
    off = counted(board_store(reads=reads, pots=pots))
    build(BF, off, limit=GC.TILE_LIMIT_MAX)
    assert len(on.potentials.calls) - len(off.potentials.calls) == 1
    # MOVED 2026-11-11 (review fix, D10): the stages SHARE build's ONE alert_rows read (over the window) — no delta.
    assert len(on.alert_rows.calls) == len(off.alert_rows.calls) == 1
    assert on.alert_rows.calls == [(SC._window(S),)]
    assert (P2,) in on.potentials.calls and (P2,) not in off.potentials.calls
    assert real is not GT._stage_tag


# ── review fix 2026-11-11: ONE alert_rows read per build, shared by the words, the 🧠 entries, the recap and 🧭 ──────
@pytest.mark.parametrize("variant", [None, V.GG1])
def test_one_alert_rows_read_per_build_on_every_sub_with_stages(variant):
    for k, _e, _l in GC.SUBS:
        if k == GC.LEDGER_SUB:
            continue                                                  # 🏁 reads its own rows_for
        st = counted(board_store(alerts=[claim(S, "CCC", HF, 10, 12)]))
        build(k, st, variant=variant)
        assert len(st.alert_rows.calls) <= 1, k
        assert all(c == (SC._window(S),) for c in st.alert_rows.calls), k


def test_a_setup_sub_with_cards_reads_alert_rows_once_and_still_merges_the_claim():
    st = counted(board_store(alerts=[claim(S, "CCC", HF, 10, 12)]))
    out = build(BF, st)
    assert len(st.alert_rows.calls) == 1                              # was 2: the words' read + the stages' read
    assert "🎯 A+ 10:12" in stages_of(out, "CCC")["text"]             # the claim still reaches the stages


def test_NEGATIVE_no_card_no_consumer_no_read():
    # MOVED 2026-11-11 (entry spec #8, 🌅 day-2 list): the GG5 ☀️ board now has ONE consumer with no card — the day-2
    # list — so it makes exactly ONE alert_rows read (build's shared read over the window). A ☀️ with no card on any
    # other variant still never reads it.
    st = counted(board_store(reads={}, pots=[]))
    build("premarket", st)
    assert len(st.alert_rows.calls) == 1                              # GG5 ☀️: the 🌅 day-2 list's read, once
    win = list(SC._window(S))
    win += [PREV] if PREV not in win else []
    assert st.alert_rows.calls == [(win,)]
    for v in (V.GG1, V.GGA):
        st = counted(board_store(reads={}, pots=[]))
        build("premarket", st, variant=v)
        assert st.alert_rows.calls == [], v                           # NEGATIVE: no 🌅 off GG5 → no read
    st = counted(board_store())
    build(RS, st, variant=V.GGA)
    assert st.alert_rows.calls == []                                  # 🧪 stages read st.shared, never its own claims


def test_NEGATIVE_C2_never_a_per_card_read(monkeypatch):
    st = board_store()

    def boom(*_a, **_k):
        raise AssertionError("per-card read")
    st.potential_docs_for_symbol = boom
    assert stages_of(build(BF, st), "AAA")
    assert "_ledger_count" in GT.__dict__ and GT._ledger_count.__module__ == GT.__name__


def test_C10_no_fetch_the_board_serves_with_stages(monkeypatch):
    from chart_maps.gajjala import bars as GB
    from daytrading import data as dt_data

    def boom(*_a, **_k):
        raise AssertionError("fetch")
    monkeypatch.setattr(GB, "frames_for", boom)
    monkeypatch.setattr(dt_data, "load_intraday", boom)
    assert SC._window(S) == [S, PREV, P2]                            # the real window
    assert stages_of(build(BF, board_store()), "AAA")


def test_the_span_follows_stay_listed_sessions(monkeypatch):
    monkeypatch.setattr(GC, "STAY_LISTED_SESSIONS", 1)
    st = counted(board_store())
    b = stages_of(build(BF, st), "AAA")
    assert [g["date"] for g in b["groups"]] == [PREV.isoformat(), S.isoformat()]   # NEGATIVE: no P2 group
    assert (P2,) not in st.potentials.calls


def test_NEGATIVE_a_doc_three_sessions_back_never_shows():
    st = board_store(pots=POTS + [pdoc(date(2026, 10, 8), "AAA", RS, [e("10:00", "forming", "armed")])],
                     alerts=[claim(date(2026, 10, 8), "AAA", RS, 10, 5)])
    b = stages_of(build(BF, st), "AAA")
    assert "2026-10-08" not in {g["date"] for g in b["groups"]}
    assert all(t["setup"] != RS for g in b["groups"] for t in g["tags"])


def test_NEGATIVE_nothing_else_moves_on_any_sub(monkeypatch):
    st = board_store(alerts=[claim(S, "CCC", HF, 10, 12)])
    with_ = {k: build(k, st) for k, _e, _l in GC.SUBS}
    monkeypatch.setattr(SG, "by_symbol", lambda *a, **k: {})
    without = {k: build(k, st) for k, _e, _l in GC.SUBS}
    for k in with_:
        assert json.dumps(strip_stages(with_[k]), sort_keys=True, default=str) == \
            json.dumps(without[k], sort_keys=True, default=str), k
        assert "stages" not in set(keys_of(without[k])), k
    assert any("stages" in t["gajjala"] for t in with_[BF]["tiles"])


def test_C8_a_raise_mid_assign_leaves_no_card_with_stages(monkeypatch):
    st = board_store(pots=POTS + [pdoc(S, "BBB", BF, [e("10:00", "forming", "armed")])])
    real, n = SG.for_tile, {"k": 0}

    def flaky(*a, **k):
        n["k"] += 1
        if n["k"] == 2:
            raise RuntimeError("card 2")
        return real(*a, **k)
    monkeypatch.setattr(SG, "for_tile", flaky)
    out = build(BF, st)
    assert n["k"] == 2 and out["tiles"]
    assert not any("stages" in t["gajjala"] for t in out["tiles"])


def test_every_viewer_gets_the_same_stages():
    st = board_store(alerts=[claim(S, "CCC", HF, 10, 12)])
    a, b = build(BF, st, owner=True), build(BF, st, owner=False)
    sa = {t["symbol"]: t["gajjala"].get("stages") for t in a["tiles"]}
    sb = {t["symbol"]: t["gajjala"].get("stages") for t in b["tiles"]}
    assert sa == sb and sa["AAA"]


def test_faults_one_session_claims_and_the_engine():
    st = board_store(alerts=[claim(S, "CCC", HF, 10, 12)])
    st.potentials = Count(st.potentials, fail_on=lambda d: d == P2)
    b = stages_of(build(BF, st), "AAA")
    assert [g["date"] for g in b["groups"]] == [PREV.isoformat(), S.isoformat()]
    st = board_store(alerts=[claim(S, "CCC", HF, 10, 12)])
    st.alert_rows = Count(st.alert_rows, answer=None)                # D10: _entry_times → None → `or {}`
    out = build(BF, st)
    assert stages_of(out, "CCC")["groups"][-1]["tags"][0]["text"] == "➖ Horizontal Fade · 🧠 potential 10:20"
    assert "🎯 A+ 10:06" in stages_of(out, "AAA")["text"]           # the tracker's own A+ stays


def test_NEGATIVE_a_raising_engine_serves_the_board_without_stages(monkeypatch):
    st = board_store()
    want = [t["symbol"] for t in build(BF, st)["tiles"]]

    def boom(*_a, **_k):
        raise RuntimeError("engine down")
    monkeypatch.setattr(SG, "by_symbol", boom)
    out = build(BF, st)
    assert [t["symbol"] for t in out["tiles"]] == want
    assert not any("stages" in t["gajjala"] for t in out["tiles"])


@pytest.mark.parametrize("sub", [GC.LEDGER_SUB, "playbook"])
def test_NEGATIVE_track_record_and_playbook_have_no_stage_reads_and_no_stages(sub, monkeypatch):
    on = counted(board_store())
    out = build(sub, on)
    assert "stages" not in set(keys_of(out))
    monkeypatch.setattr(GT, "_stage_tag", lambda *a, **k: None)
    off = counted(board_store())
    build(sub, off)
    assert len(on.potentials.calls) == len(off.potentials.calls)
    assert len(on.alert_rows.calls) == len(off.alert_rows.calls)


def test_the_list_and_potential_subs_carry_stages_with_no_here_on_list_cards():
    st = board_store()
    pot = build(GC.POTENTIAL_SUB, st)
    aaa = [t for t in pot["tiles"] if t["symbol"] == "AAA"]
    for t in aaa:
        assert t["gajjala"]["stages"]["groups"]
    pm = build("premarket", st)
    for t in pm["tiles"]:
        s = t["gajjala"].get("stages")
        if s:
            assert not any(x["here"] for g in s["groups"] for x in g["tags"])


def test_served_word_guards():
    out = build(BF, board_store(alerts=[claim(S, "CCC", HF, 10, 12)]))
    blocks = [t["gajjala"]["stages"] for t in out["tiles"] if "stages" in t["gajjala"]]
    assert blocks
    for b in blocks:
        assert not any(str(k).startswith("_") for k in keys_of(b))
        for s in strings_of(b):
            assert not B_WORD.search(s) and not OTHER.search(s), s
    for s in (SG.TITLE, SG.HINT, SG.BORROWED_TEXT, *SG.STAGE_WORDS.values()):
        assert not B_WORD.search(s) and not OTHER.search(s)


# ── variants ─────────────────────────────────────────────────────────────────────────────────────────────────────
def gg1_world():
    g5 = board_store(alerts=[claim(S, "AAA", HF, 10, 12)])            # GG5's tracker + GG5's live claim
    g1 = ST.GajjalaStore(colls={n: FakeColl() for n in ST.OWN}, variant=V.GG1, shared=g5)
    g1.coll(ST.READS).docs = {d["_id"]: d for d in (read_doc("AAA", {KF: R(KF, "forming", ready=True)}),)}
    g1.coll(ST.PASSES).docs = {"latest": latest()}
    pots = [pdoc(S, "AAA", KF, [e("10:15", "forming", "armed")])]
    g1.coll(ST.POTENTIALS).docs = {d["_id"]: d for d in pots}
    c = claim(S, "AAA", VCP, 10, 18, prefix=V.GG1.claim_prefix + ":")
    g1.coll(ST.ALERTS).docs = {c["_id"]: c}
    return g5, g1


def test_gg1_reads_its_own_tracker_and_claims_only():
    _g5, g1 = gg1_world()
    out = GT.build(KF, now=NOW, store=g1)
    b = stages_of(out, "AAA")
    setups = [t["setup"] for g in b["groups"] for t in g["tags"]]
    assert setups == [KF, VCP]                       # NEGATIVE: GG5's BF / KF / HF / VCP docs and HF claim never show
    assert b["groups"][-1]["tags"][1]["text"] == "🌀 Intraday VCP · 🎯 A+ 10:18"
    assert b["hint"] == SG.hint(1) and "1-minute pass" in b["hint"] and SG.BORROWED_TEXT not in b["hint"]


def gga_world(*, shared=True):
    g5 = board_store(alerts=[claim(S, "CCC", HF, 10, 12)])
    own = claim(S, "CCC", KF, 10, 14, state="shadow", prefix=SHADOW_CLAIM_PREFIX + V.GGA.claim_prefix + ":")
    own_live = claim(S, "CCC", RS, 10, 16, prefix=V.GGA.claim_prefix + ":")
    gga_own = (ST.ALERTS, ST.STATE, ST.LEDGER, ST.OVERLAY, ST.EXITS)
    colls = {n: FakeColl([own, own_live] if n == ST.ALERTS else None) for n in gga_own}
    if not shared:
        colls.update({n: g5.coll(n) for n in ST.ALL if n not in gga_own})
    return g5, ST.GajjalaStore(colls=colls, variant=V.GGA, shared=g5 if shared else None)


def test_gga_reads_gg5s_tracker_and_live_claims_with_the_borrowed_sentence():
    _g5, gga = gga_world()
    out = GT.build(BF, now=NOW, store=gga)
    b = stages_of(out, "CCC")
    assert b["groups"][-1]["tags"][0]["text"] == "➖ Horizontal Fade · 🎯 A+ 10:12 · 🧠 potential 10:20"
    assert b["hint"] == SG.hint(5, borrowed=True) and b["hint"].endswith(SG.BORROWED_TEXT)
    setups = [t["setup"] for g in b["groups"] for t in g["tags"]]
    assert KF not in setups and RS not in setups     # NEGATIVE: GGA's own claims (shadow or not) never add a step
    assert stages_of(out, "AAA")["groups"][0]["tags"][0]["setup"] == VCP       # 🚩's borrowed tracker


def test_NEGATIVE_gga_without_shared_merges_no_claim_and_never_raises():
    _g5, gga = gga_world(shared=False)
    out = GT.build(BF, now=NOW, store=gga)
    b = stages_of(out, "CCC")
    assert b["groups"][-1]["tags"][0]["text"] == "➖ Horizontal Fade · 🧠 potential 10:20"
    assert b["hint"].endswith(SG.BORROWED_TEXT)


def test_NEGATIVE_gg5_and_gg1_hints_never_carry_the_borrowed_sentence():
    for out in (build(BF, board_store()), GT.build(KF, now=NOW, store=gg1_world()[1])):
        for t in out["tiles"]:
            s = t["gajjala"].get("stages")
            if s:
                assert SG.BORROWED_TEXT not in s["hint"]


def test_gga_held_aplus_card_keeps_aplus_held_while_its_tag_says_aplus(monkeypatch):
    from chart_maps.gajjala import audited_rules as AUD
    from tests.test_gajjala_audited_tab import NOW_B, aplus_of, entry, gga_store, plant, scenario, state_ok
    st, _out = scenario("shadow", monkeypatch)
    doc = st.get_read(S, "GGA")
    setup = aplus_of(doc)
    gga = gga_store(st)
    plant(gga, doc, setup, entry(doc["setups"][setup], failed=("G1",)))
    state_ok(gga, st)
    b = GT.build(setup, now=NOW_B, store=gga, owner=True)
    g = tile(b, "GGA")["gajjala"]
    assert g["state"] == AUD.HELD_STATE
    mine = [t for gr in g["stages"]["groups"] for t in gr["tags"] if t["setup"] == setup and t["here"]]
    assert len(mine) == 1 and "🎯 A+" in mine[0]["text"]
    assert g["stages"]["hint"].endswith(SG.BORROWED_TEXT)
