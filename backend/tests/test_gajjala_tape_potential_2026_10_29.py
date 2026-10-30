"""📈 The 🧠 potential tape on the 🏁 Track record list (BUILD_SPEC31 D1 / D5 — 2026-10-29).

Ajay 2026-10-29 ~19:50 ET, verbatim: "I wanna see this kind of graph in our Track record page this screenshot is from
Promo circuit page."

UNMEASURED — the tape is a picture of what each 🧠 potential did, graded by the ledger's own math (as if entered at the
trigger). Every store is the in-memory FakeColl set; every loader is injected or monkeypatched — the network is NEVER
touched (an autouse guard makes the minute fetch and the ledger's forced today loader raise). NEGATIVES are marked.

The A+ BYTE PIN: APLUS_PINS are the sha256 of the A+ tape payloads (full + lite, json in key order) captured on the
untouched tree BEFORE the potential change (GG_PRINT_PINS=1 prints them) — an A+ payload never moves by one byte.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import run_1m as R1
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tape as TP
from chart_maps.gajjala import variant as V
from daytrading import data as dt_data
from tests.test_gajjala_entry_tape import (B_WORD, GOLDEN_ID, MON_NIGHT, NAMES, XLAB15_ID, Rec, _served_row, _txt,
                                           frame, load15, today_real, xlab15_store)
from tests.test_gajjala_store import FakeColl, fake_store
from tests.test_gajjala_tab import _walk_strings, run_route
from tests.test_gajjala_track_record_tab import (D15, D16, NOW, _et, _flat, _real_tape, _xlab_15_synthetic,
                                                 golden_store, ledger_store, no_split, pot_doc, tape_loader)

ET = ZoneInfo("America/New_York")
UTC = timezone.utc


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    """Memos cleared; the network refused (the minute fetch and the forced today loader RAISE); intraday_cache is an
    in-memory dict."""
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    for m in (LG._TODAY_MEMO, LG._TODAY_SPLIT, TP._MEMO, R1._PREV_MEMO):
        m.clear()
    net = Rec(exc=AssertionError("network: the minute fetch was called"))
    monkeypatch.setattr(dt_data, "_fetch_massive_minute", net)
    monkeypatch.setattr(LG, "_today_load", Rec(exc=AssertionError("network: the forced today loader was called")))
    cache = {}
    monkeypatch.setattr(dt_data, "_mongo_get_day", lambda sym, day: (cache.get((sym.upper(), str(day))).copy()
                                                                     if (sym.upper(), str(day)) in cache else None))
    monkeypatch.setattr(dt_data, "_mongo_put_day", lambda sym, day, df: cache.__setitem__((sym.upper(), str(day)), df))
    yield {"net": net, "cache": cache}
    for m in (LG._TODAY_MEMO, LG._TODAY_SPLIT, TP._MEMO, R1._PREV_MEMO):
        m.clear()


# ── the A+ byte pin (captured on the untouched tree FIRST) ──────────────────────────────────────────────────────
def _sha(p) -> str:
    return hashlib.sha256(json.dumps(p, ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def _aplus_payloads() -> dict:
    """The A+ tapes the pin covers: the 🏁 golden store's live XLAB 🌀 entry (today, the real tape), the 10-15 shadow
    WIN (fill + exit dots, both days completed) and the 1-minute page's shadow A+ — each full and lite."""
    from tests import test_gajjala_1m_page_2026_10_27 as M1
    out = {}
    for name, mk in (("golden_xlab16", lambda: (GOLDEN_ID, dict(now=NOW, store=golden_store(),
                                                                 today_bars=today_real()))),
                     ("xlab15_win", lambda: (XLAB15_ID, dict(now=MON_NIGHT, store=xlab15_store(),
                                                              load_day=load15()))),
                     ("gg1_aplus", lambda: (M1.APLUS_ID, dict(now=M1.NOW, store=M1.day()[1],
                                                               today_bars=M1._today_bars,
                                                               load_day=lambda s, d: None)))):
        _id, kw = mk()
        for lite in (False, True):
            TP._MEMO.clear()
            LG._TODAY_MEMO.clear()
            LG._TODAY_SPLIT.clear()
            out[f"{name}_{'lite' if lite else 'full'}"] = _sha(TP.entry_tape(_id, lite=lite, **kw))
    return out


APLUS_PINS = {          # captured 2026-10-29 on the untouched tree (wpA_aplus_pins.txt) — NEVER regenerate to pass
    "gg1_aplus_full": "4208eaae8b91b2081fdeb0a2e0345d80d5b5ca7b32f0e15ea4c53203dd6f6c0a",
    "gg1_aplus_lite": "b684bc398e192318451212944cea84a0305e28eb64b9f30fadef72ec6b2cf362",
    "golden_xlab16_full": "4d2e2ed922f9c48558b2f51343408369a08ae2317023cf5ba73fc4bbe12d33c6",
    "golden_xlab16_lite": "6eb45548dc1dfcaa1bc27a3827c7426cd1f1d4ece8ee8e5f0997e0ad5afde7b8",
    "xlab15_win_full": "4b6d59d3bfa87473af4f7b72a8e0e4f9d39c6ee5dcab6aeb025deceac8f1f38c",
    "xlab15_win_lite": "90a83ac272ef6c40655ebde645a0130a5588eca16c3fe36123d35c75e45b1fd6",
}


def test_the_aplus_tapes_are_byte_identical_to_before_the_potential_change():
    got = _aplus_payloads()
    if os.environ.get("GG_PRINT_PINS") == "1":
        print("APLUS_PINS = " + json.dumps(got, indent=1, sort_keys=True))
    assert got == APLUS_PINS


D19 = date(2026, 10, 19)
POT15 = LG.ledger_id("2026-10-15", "XLAB", "intraday_vcp", LG.KINDS[0])      # graded WIN by the 10-15 nightly
POT16 = LG.ledger_id("2026-10-16", "XLAB", "intraday_vcp", LG.KINDS[0])      # today at NOW (the real tape)
NOEN16 = LG.ledger_id("2026-10-16", "NOEN", "kiss_fly", LG.KINDS[0])         # trigger 9.99 over a flat 5.00
NPLN16 = LG.ledger_id("2026-10-16", "NPLN", "bull_flag", LG.KINDS[0])        # no trigger / stop on the push
W = TP.ENTRY_TAPE_WORDS


def _keys(xs):
    return [x["key"] for x in xs]


def _pot_store(*docs):
    return fake_store(**{ST.POTENTIALS: FakeColl(list(docs))})


# ── 1. parse_id / kind_of ────────────────────────────────────────────────────────────────────────────────────────
def test_parse_id_reads_a_potential_id_and_kind_of_names_the_kind():
    assert TP.parse_id(POT15) == (D15, "XLAB", "intraday_vcp") and TP.kind_of(POT15) == LG.KINDS[0]
    assert TP.kind_of(XLAB15_ID) == LG.KINDS[1] and TP.parse_id(XLAB15_ID) == (D15, "XLAB", "intraday_vcp")


@pytest.mark.parametrize("bad", ["2026-10-15|XLAB|intraday_vcp|Potential", "2026-10-15|XLAB|intraday_vcp|other",
                                 "2026-10-15|XLAB|intraday_vcp|potential|x", "2026-10-15|xlab|intraday_vcp|potential",
                                 "2026-13-40|XLAB|intraday_vcp|potential", "2026-10-15|XLAB| |potential",
                                 "REPLAY:2026-10-15|XLAB|intraday_vcp", "junk", "", None, 5])
def test_NEGATIVE_junk_and_other_kinds_are_never_a_ledger_id(bad):
    assert TP.parse_id(bad) is None and TP.kind_of(bad) is None, bad


# ── 2. a graded 🧠 WIN: ring at first-seen, trigger / stop / +1R, fill dot, exit dot, its own words ─────────────────
def test_a_graded_potential_draws_the_ring_levels_and_dots_with_its_own_words():
    st = ledger_store()
    p = TP.entry_tape(POT15, now=NOW, store=st, load_day=load15(), today_bars=today_real())
    assert set(p) == set(TP.PAYLOAD_KEYS) and p["note"] is None and p["ticker"] == "XLAB" and p["id"] == POT15
    assert [(h["key"], h["px"], h["label"]) for h in p["hlines"]] == [
        ("trigger", 1.22, "trigger 1.22"), ("stop", 1.16, "stop 1.16"), ("target", pytest.approx(1.28), "+1R 1.28")]
    assert [(r["key"], r["style"], r["label"]) for r in p["rules"]] == [("alert", "solid", "🧠 rang 15:11 ET"),
                                                                        ("fill", "dashed", "fill 15:21")]
    row = next(r for r in LG.rows_for([D15], st) if r["id"] == POT15)
    assert row["first_seen_et"] == "15:11" == row["at_et"]                       # the ring sits on the first-seen bar
    assert p["rules"][0]["at"] == _et(D15, 15, 11).astimezone(UTC).isoformat()
    assert [(d["key"], d["px"], d["label"]) for d in p["dots"]] == [("fill", 1.22, "fill 1.22 at 15:21"),
                                                                    ("exit", pytest.approx(1.28), "+1R 15:22")]
    r = _served_row(st, POT15, NOW)
    cells = f"Same session: {_txt(r['same'])}; Through next session: {_txt(r['next'])}"
    want = "🧠 potential rang 15:11 ET · trigger 1.22 · stop 1.16; entered at the trigger 15:21 ET · fill 1.22; " + cells
    assert p["read"] == want and r["same"]["state"] == "win"                     # one engine: the 🏁 cells
    assert p["title"] == want + "\n" + W["open_hint"]
    assert p["legend"] == W["pot_legend"].format(n=GC.LEDGER_TAPE_TF_MIN, m=LG._m())
    assert p["aria"] == "XLAB 5-minute tape around the 🧠 potential" and p["tf"] == "5min · pre/post market"
    lite = TP.entry_tape(POT15, lite=True, now=NOW, store=st, load_day=load15(), today_bars=today_real())
    assert set(lite) == set(TP.LITE_KEYS) and _keys(lite["rules"]) == ["alert"] and lite["title"] == p["title"]
    assert lite["rules"][0]["label"] == "🧠 rang 15:11 ET" and all(set(b) == {"t", "c", "s"} for b in lite["bars"])


def test_the_potential_and_the_aplus_of_the_same_alert_draw_the_same_marks_only_the_words_differ():
    """One engine: the 10-15 XLAB 🌀 rang as a 🧠 push AND as a shadow A+ on the same plan — the same bars, levels and
    dots; the read / legend / aria / ring label are each kind's own."""
    pot = TP.entry_tape(POT15, now=MON_NIGHT, store=ledger_store(), load_day=load15())
    ap = TP.entry_tape(XLAB15_ID, now=MON_NIGHT, store=xlab15_store(), load_day=load15())
    for k in ("bars", "hlines", "dots", "axis", "tone", "n_bars", "tf"):
        assert pot[k] == ap[k], k
    assert [(r["key"], r["at"], r["style"]) for r in pot["rules"]] == [(r["key"], r["at"], r["style"]) for r in ap["rules"]]
    assert pot["read"].endswith(ap["read"]) and pot["read"] != ap["read"]
    assert (pot["legend"], pot["aria"]) != (ap["legend"], ap["aria"])


def test_a_potential_whose_trigger_never_printed_says_so_and_draws_no_fill():
    doc = pot_doc(D16, "NOEN", "kiss_fly", _et(D16, 10, 12), trigger=9.99, stop=9.50, px=9.70)
    st = _pot_store(doc)
    out = LG.grade_step(st, _et(D19, 20, 15, 30), load_day=tape_loader(), split_lookup=lambda *a: False)
    assert out["read_fault"] is False and out["written"] == 1, out
    (ld,) = st.ledger_docs([D16])
    assert ld["same"]["entry"] == "no_entry" and ld["next"]["entry"] == "no_entry"
    p = TP.entry_tape(NOEN16, now=MON_NIGHT, store=st, load_day=lambda s, d: _flat(d, 5.00))
    assert _keys(p["hlines"]) == ["trigger", "stop"] and p["dots"] == [] and _keys(p["rules"]) == ["alert"]
    assert p["read"].startswith("🧠 potential rang 10:12 ET · trigger 9.99 · stop 9.50; " + W["pot_never"] + "; ")
    assert W["pot_entered"].split(" {")[0] not in p["read"] and p["tone"] == "dn"


def test_NEGATIVE_an_ungraded_potential_claims_neither_entered_nor_never_printed():
    p = TP.entry_tape(NOEN16, now=MON_NIGHT, store=ledger_store(), load_day=lambda s, d: _flat(d, 5.00))
    assert p["read"].startswith("🧠 potential rang 10:12 ET · trigger 9.99 · stop 9.50; Same session: ")
    assert W["pot_never"] not in p["read"] and "entered at the trigger" not in p["read"]


def test_NEGATIVE_a_live_potential_today_with_a_provisional_no_entry_claims_neither():
    """Critic 2026-10-29: today's NOEN 🧠 at 11:11 ET over a flat 5.00 (trigger 9.99) — the provisional same-session
    grade reads no_entry, but the trade is live: never "the trigger never printed"."""
    doc = pot_doc(D16, "NOEN", "kiss_fly", _et(D16, 10, 12), trigger=9.99, stop=9.50, px=9.70)
    now = datetime(2026, 10, 16, 11, 11, 30, tzinfo=ET)
    bars = [b for b in _flat(D16, 5.00) if b[0] < now]
    p = TP.entry_tape(NOEN16, now=now, store=_pot_store(doc), today_bars=lambda s, d, **k: (bars, now),
                      load_day=lambda s, d: None)
    assert p["read"].startswith("🧠 potential rang 10:12 ET · trigger 9.99 · stop 9.50; Same session: ")
    assert W["pot_never"] not in p["read"] and "entered at the trigger" not in p["read"]


def test_NEGATIVE_a_potential_with_same_graded_and_next_pending_claims_neither():
    """Critic 2026-10-29: same session graded no_entry on 10-16's night, next not graded yet, viewed Mon 10-19 10:00 —
    the next session is still live: never "the trigger never printed"."""
    doc = pot_doc(D16, "NOEN", "kiss_fly", _et(D16, 10, 12), trigger=9.99, stop=9.50, px=9.70)
    st = _pot_store(doc)
    LG.grade_step(st, _et(D16, 20, 15, 30), load_day=tape_loader(), split_lookup=lambda *a: False)
    (ld,) = st.ledger_docs([D16])
    assert ld["same"]["entry"] == "no_entry"
    assert not (isinstance(ld.get("next"), dict) and ld["next"].get("entry") == "no_entry")   # next still pending
    now = datetime(2026, 10, 19, 10, 0, tzinfo=ET)
    p = TP.entry_tape(NOEN16, now=now, store=st, today_bars=lambda s, d, **k: (None, None),
                      load_day=lambda s, d: _flat(d, 5.00))
    assert p["read"].startswith("🧠 potential rang 10:12 ET · trigger 9.99 · stop 9.50; Same session: ")
    assert W["pot_never"] not in p["read"] and "entered at the trigger" not in p["read"]


def test_a_no_risk_potential_draws_the_bars_and_the_ring_only_with_the_served_sentence():
    doc = pot_doc(D15, "NRSK", "bull_flag", _et(D15, 11, 0), trigger=2.0, stop=2.0, px=2.0)
    p = TP.entry_tape(LG.ledger_id("2026-10-15", "NRSK", "bull_flag", LG.KINDS[0]), now=MON_NIGHT,
                      store=_pot_store(doc), load_day=lambda s, d: _flat(d, 2.0))
    assert p["bars"] and p["hlines"] == [] and p["dots"] == [] and _keys(p["rules"]) == ["alert"]
    sentence = W["pot_no_levels"].format(why=LG.NO_RISK_TEXT)
    assert p["read"].startswith("🧠 potential rang 11:00 ET; " + sentence + "; Same session: ")
    assert p["legend"] == W["pot_legend_no_levels"].format(n=GC.LEDGER_TAPE_TF_MIN)
    assert "trigger" not in p["legend"] and "trigger 2" not in p["read"]


def test_a_no_plan_potential_draws_the_bars_and_the_ring_only_with_the_no_plan_sentence():
    p = TP.entry_tape(NPLN16, now=MON_NIGHT, store=ledger_store(), load_day=lambda s, d: _flat(d, 3.10))
    assert p["bars"] and p["hlines"] == [] and p["dots"] == [] and _keys(p["rules"]) == ["alert"] and p["tone"] is None
    assert W["pot_no_levels"].format(why=LG.NO_PLAN_TEXT) in p["read"]
    assert LG.NO_RISK_TEXT not in p["read"]


def test_NEGATIVE_a_potential_with_no_alert_time_has_no_ring():
    doc = pot_doc(D15, "NOTM", "bull_flag", _et(D15, 11, 0), trigger=2.2, stop=2.0, px=2.1)
    doc["push"].pop("at")
    doc["push"].pop("at_et")
    p = TP.entry_tape(LG.ledger_id("2026-10-15", "NOTM", "bull_flag", LG.KINDS[0]), now=MON_NIGHT,
                      store=_pot_store(doc), load_day=lambda s, d: _flat(d, 2.1))
    assert p["rules"] == [] and p["dots"] == []
    assert p["read"].startswith(W["pot_no_time"].format(why=LG.NO_TIME_TEXT) + " · trigger 2.20")


# ── 3. cost rules: the mini NEVER calls the loader (F8), memo per id × lite ──────────────────────────────────────
def test_F8_NEGATIVE_the_potential_mini_never_calls_the_loader_cache_and_memo_only(monkeypatch, _clean):
    spy = Rec(ret=None)
    monkeypatch.setattr(dt_data, "load_intraday", spy)
    _clean["cache"][("XLAB", "2026-10-15")] = frame(_xlab_15_synthetic())
    _clean["cache"][("XLAB", "2026-10-16")] = frame(_real_tape())
    lite = TP.entry_tape(POT15, lite=True, now=MON_NIGHT, store=ledger_store())
    assert spy.calls == [] and _clean["net"].calls == [] and lite["n_bars"] > 0 and lite["note"] is None
    today = TP.entry_tape(POT16, lite=True, now=NOW, store=ledger_store())       # today: the memo is empty
    assert today["note"] == W["lite_today"] and LG._today_load.calls == [] and spy.calls == []
    TP._MEMO.clear()
    TP.entry_tape(POT15, now=MON_NIGHT, store=ledger_store())                      # control: the full tape loads
    assert [a[1] for a, _k in spy.calls] == [D15, D16]


def test_the_memo_is_per_id_and_mode_a_potential_never_answers_its_aplus():
    st = golden_store()                       # 10-16 XLAB 🌀 rang as a 🧠 push AND as the live A+ entry
    kw = dict(now=NOW, store=st, today_bars=today_real())
    pot = TP.entry_tape(POT16, **kw)
    ap = TP.entry_tape(GOLDEN_ID, **kw)
    assert pot["aria"] != ap["aria"] and pot["id"] == POT16 and ap["id"] == GOLDEN_ID
    assert {(POT16, "full"), (POT16, "lite"), (GOLDEN_ID, "full"), (GOLDEN_ID, "lite")} <= set(TP._MEMO)
    assert TP.entry_tape(POT16, **kw) is pot                                       # inside the memo window
    TP._MEMO.clear()
    LG._TODAY_MEMO.clear()
    assert _sha(TP.entry_tape(GOLDEN_ID, **kw)) == APLUS_PINS["golden_xlab16_full"]


# ── 4. unknown ids keep today's 404 ─────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_potential_id_off_file_joined_or_unsent_is_None_and_kinds_never_cross():
    st = ledger_store()
    for rid in (LG.ledger_id("2026-10-16", "JOIN", "bull_flag", LG.KINDS[0]),       # first seen by a join pass
                LG.ledger_id("2026-10-16", "NOTG", "bull_flag", LG.KINDS[0]),       # push state no_target
                LG.ledger_id("2026-10-16", "ZZZZ", "bull_flag", LG.KINDS[0]),
                XLAB15_ID):                                                         # an A+ id: no A+ doc on file
        assert TP.entry_tape(rid, now=MON_NIGHT, store=st, load_day=lambda s, d: None) is None, rid
    assert TP.entry_tape(POT15, now=MON_NIGHT, store=xlab15_store(), load_day=lambda s, d: None) is None


def test_NEGATIVE_an_unreadable_potentials_collection_is_the_fault_note_with_the_potential_aria():
    st = ledger_store()
    st.potential_pushes = lambda sessions: None
    p = TP.entry_tape(POT15, now=MON_NIGHT, store=st, load_day=lambda s, d: None)
    assert p["note"] == W["fault"] and p["bars"] == [] and p["aria"] == "XLAB 5-minute tape around the 🧠 potential"
    assert TP.fault_payload(XLAB15_ID, ticker="XLAB")["aria"] == "XLAB 5-minute tape around the A+ entry"


def _route(monkeypatch, st):
    from chart_maps import api as API
    monkeypatch.setattr(ST, "default", lambda: st)
    return API


def test_route_serves_a_potential_mini_and_404s_junk_with_todays_text(monkeypatch, _clean):
    API = _route(monkeypatch, ledger_store())
    resp = run_route(API.chart_maps_gajjala_entry_tape(id=POT15, lite=1))
    body = json.loads(resp.body)
    assert resp.status_code == 200 and set(body) == set(TP.LITE_KEYS) and body["id"] == POT15
    assert _clean["net"].calls == []                                              # the mini never fetched
    for bad in ("2026-10-15|ZZZZ|bull_flag|potential", "2026-10-15|XLAB|intraday_vcp|other", "junk", ""):
        r = run_route(API.chart_maps_gajjala_entry_tape(id=bad, lite=1))
        assert r.status_code == 404 and json.loads(r.body) == {"detail": W["not_found"]}, bad
    assert W["not_found"] == "No A+ entry with that id on the 🏁 Track record."


# ── 5. the 1-minute page: its own store, 1-minute bars, the shadow 🧠 words ─────────────────────────────────────
def test_the_1m_route_resolves_a_1m_potential_with_1_minute_bars(monkeypatch, _clean):
    from tests import test_gajjala_1m_page_2026_10_27 as M1
    g5, g1, *_ = M1.day()
    pid = LG.ledger_id("2026-10-27", "GGB", "bull_flag", LG.KINDS[0])
    p = TP.entry_tape(pid, now=M1.NOW, store=g1, today_bars=M1._today_bars, load_day=lambda s, d: None)
    assert p is not None and p["id"] == pid and p["tf"] == W["tf"].format(n=GC.GG1M_TAPE_TF_MIN)
    ts = [b["t"] for b in p["bars"]]
    assert len(ts) >= 2 and {b - a for a, b in zip(ts, ts[1:])} == {60_000}
    assert p["aria"] == W["pot_aria"].format(sym="GGB", n=GC.GG1M_TAPE_TF_MIN)
    assert p["read"].startswith("🧠 potential recorded ") and " — shadow, never sent" in p["read"]
    assert p["rules"][0]["label"].startswith("🧠 recorded ")
    assert (M1.GG1.key, pid, "full") in TP._MEMO and (pid, "full") not in TP._MEMO
    assert TP.entry_tape(pid, now=M1.NOW, store=g5, load_day=lambda s, d: None) is None   # NEGATIVE: never GG5's row
    TP._MEMO.clear()
    from chart_maps import api as API
    M1._route_env(monkeypatch, g5, g1)
    resp = run_route(API.chart_maps_gajjala_1m_entry_tape(id=pid, lite=1))
    body = json.loads(resp.body)
    assert resp.status_code == 200 and set(body) == set(TP.LITE_KEYS) and body["id"] == pid
    assert body["tf"] == W["tf"].format(n=GC.GG1M_TAPE_TF_MIN) and _clean["net"].calls == []


# ── 6. the words and the source ──────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_every_potential_word_is_served_from_tape_py_and_clean():
    from chart_maps.high_beta_tab import FORBIDDEN_WORDS
    assert set(TP.POTENTIAL_TAPE_KEYS) == {k for k in W if k.startswith("pot_")} and len(TP.POTENTIAL_TAPE_KEYS) >= 12
    for k in TP.POTENTIAL_TAPE_KEYS:
        w = W[k]
        assert not B_WORD.search(w) and not NAMES.search(w) and not [x for x in FORBIDDEN_WORDS if x in w.lower()], k
    st = ledger_store()
    for p in (TP.entry_tape(POT15, now=NOW, store=st, load_day=load15(), today_bars=today_real()),
              TP.entry_tape(NPLN16, now=MON_NIGHT, store=st, load_day=lambda s, d: _flat(d, 3.10))):
        json.dumps(p, allow_nan=False)
        for s in _walk_strings(p):
            assert "{" not in s and "None" not in s.split() and "nan" not in s.lower().split(), s
            assert not B_WORD.search(s) and not NAMES.search(s), s


def test_NEGATIVE_tape_py_types_no_kind_string_and_keeps_the_cost_rules():
    src = Path(TP.__file__).read_text(encoding="utf-8")
    code = re.sub(r'"""[\s\S]*?"""', "", src)
    code = "\n".join(ln.split("#", 1)[0] for ln in code.splitlines())
    assert '"potential"' not in code and "'potential'" not in code and '"aplus"' not in code
    assert "LG.KINDS[0]" in code and '"shadow"' not in code
    assert "force=True" not in code and "_today_load(" not in code
    assert V.is_gg5(V.of(None))
