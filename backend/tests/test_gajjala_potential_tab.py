"""🧠 Potential · 📈 Track on Gajjala's tab — the served payload (BUILD_SPEC4 §3.9 / WP-B, 2026-10-15).

Ajay 2026-10-15, three messages verbatim: "In Gajjalas setup I wanna find potential stocks this shows me what has
happened I am trying to setup for this tab to act like Gajjalas brain. So create a potential category in this
section." / "In all the sub tab and add a track and alert to show me new potential is added everyday." / "Give me an
alert all continous tracker on these specifically when I get alert I will jump on to ride the wave".

The tracker docs are the WRITER's output, never typed: every store here is built by running `potential.run_pass` (and
`potential.mark_graveyard`) over synthetic passes of today and the previous session, on in-memory FakeColls, with real
detector reads (tests/fixtures/gajjala/detector_frames.py via tests/test_gajjala_potential.py). NEGATIVES are
mandatory: a partial / A+ / base-less forming read is never a potential, the ☀️ / 🌙 / 📓 subs carry no strip, an old
store with no tracker still serves rows, no served string prints "0" / None / NaN / a forecast word / the b-word.

GOLDEN: `GG_WRITE_GOLDEN=1 python -m pytest tests/test_gajjala_potential_tab.py -k golden` writes the FE fixture
(frontend/src/components/__fixtures__/gajjala_potential_golden_2026_10_15.json); without the env the test proves the
file IS the served payload, byte for byte.
"""
from __future__ import annotations

import inspect
import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import context as CX
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from tests.fixtures.gajjala import detector_frames as FX
from tests.test_gajjala_potential import Rec, bf_armed, bf_no_pullback, frame_at, kf_building, one_per_setup, \
    real_partials
from tests.test_gajjala_store import FakeColl, fake_store
from tests.test_gajjala_tab import _walk_strings, read_doc, run_route

ET = ZoneInfo("America/New_York")
S = date(2026, 10, 13)                          # a Tuesday, a market day
PREV = date(2026, 10, 12)                       # the market day before
OK_SEND = {"sent": 1, "failed": 0, "total_targets": 1}
B_WORD = re.compile("b" + "ounc", re.I)
GOLDEN = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "__fixtures__" /
          "gajjala_potential_golden_2026_10_15.json")
RECIPE = "GG_WRITE_GOLDEN=1 python -m pytest tests/test_gajjala_potential_tab.py -k golden"
PX0, PX1, ROW_PX = 10.9, 11.4, 12.0             # the 5-minute closes at the passes; the scanner row's price differs


def at(hh, mm, d=S):
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET)


NOW = at(10, 31)


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


# ── the fixture day ──────────────────────────────────────────────────────────────────────────────────────────────
FLOATS = {"AAA": 5e6, "JJJ": 2e6, "BBB": 4e6, "CCC": 8e6, "DDD": 3e6, "EEE": 1e6, "GGG": 1e6, "HHH": None,
          "ZZZ": 6e6, "XYZ": 5e6}
VOLUME = 9e6


def ctx(sym):
    fr = FX.float_read(FLOATS.get(sym))
    out = {"float": fr, "rotation": CX.rotation(VOLUME, fr), "halts": None}
    if sym == "DDD":
        out["halts"] = CX.halts_chip("DDD", {"by_ticker": {"DDD": {"n_halts": 2, "reasons": ["LUDP"], "halts": []}}})
    return out


def row(sym):
    return {"symbol": sym, "price": ROW_PX, "prev_close": 8.0, "change_pct": 50.0, "volume": VOLUME,
            "vol_src": "min_av", "type": "CS", "tape_session": "rth"}


def bf_building():
    return dict(bf_armed(), ready=False)        # the same real flag with its pullback not complete yet


def reads_at(when: str) -> dict:
    """{SYM: {setup: Read}} of today's passes. HHH never reaches a pass (a read with no tracker doc — a doc lost or
    written before this build) so its strip row has no first sighting."""
    one = one_per_setup()
    base = {"AAA": {"bull_flag": bf_armed(), "kiss_fly": kf_building()}, "JJJ": {"bull_flag": bf_building()},
            "BBB": {"kiss_fly": kf_building()}}
    if when == "09:21":
        return base
    if when == "09:36":
        return dict(base, CCC={"horizontal_fade": one["horizontal_fade"]})
    return dict(base, BBB={"kiss_fly": dict(kf_building(), state="aplus")},
                CCC={"horizontal_fade": one["horizontal_fade"]}, DDD={"reversal_squeeze": one["reversal_squeeze"]},
                EEE={"bull_flag": real_partials()["long_flag"]}, GGG={"bull_flag": bf_no_pullback()})


def run(st, now, reads, *, px, stale=(), tape="rth", send=None):
    session = now.astimezone(ET).date()
    frames = {s: frame_at(now, px, age_min=10 if s in stale else 1) for s in reads}
    send = send or Rec(OK_SEND)
    counts = PT.run_pass(reads, frames, now, session, store=st, ctx={s: ctx(s) for s in reads},
                         rows={s: row(s) for s in reads}, send=send, owner="owner@example.com", tape=tape)
    return counts, send


def day_store(*, post_rows=None, with_tracker=True):
    """The fixture day, every collection written by its own writer."""
    st = fake_store()
    st.record_qualifiers(PREV, at(9, 21, PREV), [dict(row("AAA"), change_pct=85.0)], "rth")
    st.replace_ah_carry(PREV, at(19, 56, PREV), [{"symbol": "AAA", "ah_move_pct": 14.0, "price": 11.0, "day_c": 10.0},
                                                 {"symbol": "CARY", "ah_move_pct": 9.0, "price": 2.0, "day_c": 1.8}])
    st.record_qualifiers(S, at(8, 0), [dict(row("AAA"), tape_session="premarket"),
                                      dict(row("PMX"), tape_session="premarket")], "premarket")
    st.record_qualifiers(S, at(9, 21), [row(s) for s in ("AAA", "JJJ", "BBB", "CCC", "DDD", "EEE", "GGG", "HHH")],
                         "rth")
    if with_tracker:
        run(st, at(9, 21, PREV), {"AAA": {"bull_flag": bf_armed()}, "ZZZ": {"kiss_fly": kf_building()}}, px=PX0,
            tape="premarket")
        run(st, at(10, 1, PREV), {"AAA": {"bull_flag": dict(bf_armed(), state="stopped")},
                                  "ZZZ": {"kiss_fly": real_partials()["near_kiss"]}}, px=PX1)
        run(st, at(9, 21), reads_at("09:21"), px=PX0, tape="premarket")
        PT.mark_graveyard(st, S, ["ZZZ"], at(9, 21))                  # ZZZ dropped off his list today
        run(st, at(9, 36), reads_at("09:36"), px=PX0)                  # CCC first seen in his first 15 minutes
        run(st, NOW, reads_at("10:31"), px=PX1, stale=("CCC",))        # CCC then waits for a print
    board = dict(reads_at("10:31"), HHH={"kiss_fly": kf_building()})
    for sym, setups in board.items():
        st.upsert_read(S, sym, read_doc(sym, setups, ctx=ctx(sym)), now=NOW)
    pm_levels = {s: {"volume": 9e6, "high": 12.5, "low": 9.0, "last": 12.0} for s in ("AAA", "PMX")}
    body = {"status": "ok", "tape_session": "rth", "premarket": {"pm_levels": pm_levels},
            "strip": {"runners_100": 1, "runners_80": 3, "best_change_pct": 120.0, "best_symbol": "AAA",
                      "quiet": False}}
    if post_rows is not None:
        body["postmarket"] = {"rows": post_rows, "unchecked_n": 0}
    st.record_pass(S, NOW, body)
    return st


@pytest.fixture(scope="module")
def store():
    return day_store()


def build(sub, st, **kw):
    return GT.build(sub, now=kw.pop("now", NOW), store=st, **kw)


def strip_syms(out):
    return [r["symbol"] for r in out["potential"]["rows"]]


def test_the_fixture_pushes_came_from_the_writer(store):
    """Sanity on the writer's output the tab reads: four first sightings rang at 09:21, CCC held, DDD rang at 10:31."""
    docs = {(d["symbol"], d["setup"]): d for d in store.potentials(S)}
    assert set(docs) == {("AAA", "bull_flag"), ("AAA", "kiss_fly"), ("BBB", "kiss_fly"), ("JJJ", "bull_flag"),
                         ("CCC", "horizontal_fade"), ("DDD", "reversal_squeeze")}
    assert [h["reason"] for h in docs[("CCC", "horizontal_fade")]["held"]] == ["muted", "stale_tape"]
    assert "push" not in docs[("CCC", "horizontal_fade")]
    assert docs[("DDD", "reversal_squeeze")]["push"]["state"] == "pushed"


# ── (a) every setup sub ──────────────────────────────────────────────────────────────────────────────────────────
def test_setup_sub_strip_has_only_that_setups_potentials_armed_first(store):
    out = build("bull_flag", store)
    pot = out["potential"]
    assert strip_syms(out) == ["AAA", "JJJ"]                    # armed AAA (5M float) before building JJJ (2M)
    assert {r["setup"] for r in pot["rows"]} == {"bull_flag"}
    a, j = pot["rows"]
    assert (a["kind"], a["kind_label"], j["kind"], j["kind_label"]) == ("armed", "trigger armed", "building", "building")
    assert a["first_seen_et"] == "09:21" and a["href"] == "/chart-maps?tab=gajjala&sub=bull_flag&focus=AAA"
    assert a["again"] is True and j["again"] is False            # AAA was a bull-flag potential last session
    assert any(t["key"] == "again" and t["text"] == PT.AGAIN_TEXT for t in a["tells"])
    read = bf_armed()
    assert a["text"] == PT.row_text("AAA", "bull_flag", read, "armed", "09:21")
    assert a["trigger"] == read["trigger"] and a["stop"] == read["stop"]
    assert pot["counts"] == {"armed": 1, "building": 1, "today": 2}
    assert pot["title"] == "🧠 Potential — 1 trigger armed · 1 building · 2 first seen today · UNMEASURED"
    assert pot["empty_text"] is None


def test_strip_tells_are_ggs_badges_with_their_cites(store):
    rows = {r["symbol"]: r for r in build("bull_flag", store)["potential"]["rows"]}
    tells = {t["key"]: t for t in rows["AAA"]["tells"]}
    assert set(tells) == {"float", "rotation", "ah_mover", "prior_day", "also", "again"}
    assert tells["ah_mover"]["text"] == "🌙 after-hours mover last session +14.0%"
    assert tells["prior_day"]["text"] == f"📅 on his scanner {PREV.isoformat()}, up to +85%"
    assert tells["also"]["text"] == "🧩 also forming: 💋 EMA Kiss & Fly"
    assert all(t["cite"] == PT.TELL_CITES[k] for k, t in tells.items())


def test_negative_aplus_partial_and_baseless_forming_are_not_in_any_strip(store):
    every = [s for sub in GC.SETUPS for s in strip_syms(build(sub, store))]
    assert "EEE" not in every and "GGG" not in every              # long flag (partial); forming with no sideways bar
    assert "BBB" not in every                                     # A+ is "what has happened", not a potential
    assert strip_syms(build("kiss_fly", store)) == ["AAA", "HHH"]  # unknown float sorts after a known one


def test_negative_list_and_playbook_subs_have_no_strip(store):
    for sub in ("premarket", "postmarket", "playbook", GC.POTENTIAL_SUB):
        assert "potential" not in build(sub, store), sub


def test_old_store_with_no_tracker_docs_still_serves_rows_without_a_first_sighting():
    out = build("kiss_fly", day_store(with_tracker=False))
    rows = out["potential"]["rows"]
    assert [r["symbol"] for r in rows] == ["AAA", "HHH"] and all(r["first_seen_et"] is None for r in rows)
    assert all("first seen" not in r["text"] for r in rows) and out["potential"]["counts"]["today"] == 0
    assert all(r["again"] is False for r in rows)


def test_negative_a_raising_tracker_serves_rows_and_never_raises():
    good = day_store()
    st = fake_store(**{n: (FakeColl(fail=True) if n == ST.POTENTIALS else good.coll(n)) for n in ST.ALL})
    out = build("bull_flag", st)
    assert strip_syms(out) == ["AAA", "JJJ"] and all(r["first_seen_et"] is None for r in out["potential"]["rows"])
    p = build(GC.POTENTIAL_SUB, st)
    assert p["track"]["today"]["n"] == 0 and p["track"]["today"]["rows"] == []


def _boom(*_a, **_k):
    raise RuntimeError("potential engine down")


def test_negative_a_raising_potential_engine_never_silences_the_a_plus_board(store, monkeypatch):
    """D1 on the read path: the potential layer raising serves the setup subs' tiles untouched, with no strip."""
    want = {k: [t["symbol"] for t in build(k, store)["tiles"]] for k, _e, _l in GC.SUBS}
    monkeypatch.setattr(PT, "tells", _boom)
    for k, _e, _l in GC.SUBS:
        out = build(k, store)
        if k != GC.POTENTIAL_SUB:
            assert [t["symbol"] for t in out["tiles"]] == want[k], k
        assert out.get("potential") is None and out["push"]["mode"], k
    bf = build("bull_flag", store)
    assert bf["tiles"] and bf["counts"]["forming"] and bf["subs"][-1]["count"] == 0
    p = build(GC.POTENTIAL_SUB, store)
    assert p["tiles"] == [] and p.get("track") is None and p["watch"]["symbols"]


def test_negative_a_raising_track_or_push_line_keeps_the_rest(store, monkeypatch):
    monkeypatch.setattr(PT, "state_word", _boom)
    p = build(GC.POTENTIAL_SUB, store)
    assert p["track"] is None and [t["symbol"] for t in p["tiles"]][:2] == ["DDD", "AAA"]
    monkeypatch.undo()
    monkeypatch.setattr(PT, "push_note", _boom)
    bf = build("bull_flag", store)
    assert bf["push_potential"] is None and bf["push"]["text"] and strip_syms(bf) == ["AAA", "JJJ"]


def test_negative_a_malformed_tracker_doc_never_takes_down_the_tab():
    """A tracker doc whose setup is unhashable (the critic's case): every sub still serves its A+ tiles."""
    st = day_store()
    st.coll(ST.POTENTIALS).update_one({"_id": "bad"}, {"$set": {"date": S.isoformat(), "symbol": "BAD",
                                                                "setup": ["bull_flag"]}}, upsert=True)
    good = day_store()
    for k, _e, _l in GC.SUBS:
        out = build(k, st)
        if k != GC.POTENTIAL_SUB:
            assert [t["symbol"] for t in out["tiles"]] == [t["symbol"] for t in build(k, good)["tiles"]], k
    assert build("bull_flag", st)["potential"] is None and build(GC.POTENTIAL_SUB, st)["track"] is None


def test_strip_text_quotes_his_concept_and_names_the_cheetah_defaults(store, monkeypatch):
    text = build("bull_flag", store)["potential"]["text"]
    assert f"“{PT.CONCEPT[0]}” ({PT.CONCEPT[1]})" in text and PT.defaults_sentence() in text
    assert text.endswith("A potential, not an entry.") and "Cheetah defaults, not his" in text
    for name in ("POTENTIAL_NEEDS_BASE", "POTENTIAL_FRESH_TAPE", "POTENTIAL_DEFER_REFUSED"):
        monkeypatch.setattr(GC, name, False)
    off = build("bull_flag", day_store(with_tracker=False))["potential"]["text"]
    assert "Cheetah default" not in off and "  " not in off       # NEGATIVE: none True → the sentence is gone


def test_empty_strip_text_in_and_out_of_the_window(store):
    e, label = GT.SUB_META["intraday_vcp"]
    assert build("intraday_vcp", store)["potential"]["empty_text"] == (
        f"No {e} {label} forming right now — the next pass is at most {GC.PASS_CADENCE_SEC // 60} minutes away.")
    late = build("intraday_vcp", store, now=at(21, 0))
    assert late["potential"]["empty_text"] == f"No {e} {label} was forming at the last pass (today)."
    assert late["potential"]["rows"] == []


# ── (b) the 🧠 sub ───────────────────────────────────────────────────────────────────────────────────────────────
def test_potential_sub_one_tile_per_symbol_primary_first_by_order_key(store):
    out = build(GC.POTENTIAL_SUB, store)
    assert out["sub"] == "potential" and out["sub_resolved_from"] == "param"
    assert [t["symbol"] for t in out["tiles"]] == ["DDD", "AAA", "JJJ", "CCC", "HHH"]   # armed by float ↑, then building
    aaa = out["tiles"][1]
    p = aaa["gajjala"]["potential"]
    assert aaa["gajjala"]["setup"] == "bull_flag" and p["setup"] == "bull_flag" and p["setup_label"] == "🚩 Bull Flag"
    assert p["also"] == [{"setup": "kiss_fly", "label": "💋 EMA Kiss & Fly"}]
    assert p["text"] == "🧠 trigger armed · 🚩 Bull Flag · first seen 09:21 ET" and p["again"] is True
    assert aaa["bars"] and aaa["curves"] and aaa["lines"] and aaa["gajjala"]["state_label"]
    hhh = out["tiles"][-1]["gajjala"]["potential"]
    assert hhh["first_seen_et"] is None and hhh["text"] == "🧠 building · 💋 EMA Kiss & Fly"
    assert all("_last" not in t["gajjala"] and "_bars_to_go" not in t["gajjala"] for t in out["tiles"])
    assert len(build(GC.POTENTIAL_SUB, store, limit=2)["tiles"]) == 2


def test_track_today_newest_first_with_push_and_held_words(store):
    tr = build(GC.POTENTIAL_SUB, store)["track"]
    today = tr["today"]
    assert [(r["symbol"], r["setup"]) for r in today["rows"]] == [
        ("DDD", "reversal_squeeze"), ("CCC", "horizontal_fade"), ("AAA", "bull_flag"), ("AAA", "kiss_fly"),
        ("BBB", "kiss_fly"), ("JJJ", "bull_flag")]
    assert (today["n"], today["armed_n"], today["building_n"], today["pushed_n"]) == (6, 2, 4, 5)
    assert tr["title"] == "📈 Track — 6 potentials first seen today · UNMEASURED"
    by = {(r["symbol"], r["setup"]): r for r in today["rows"]}
    assert by[("DDD", "reversal_squeeze")]["push_text"] == "📲 sent 10:31 ET"
    assert by[("CCC", "horizontal_fade")]["push_text"] == "held: " + PT.HELD_WORDS["stale_tape"]
    bbb = by[("BBB", "kiss_fly")]
    assert bbb["last_state"] == "aplus" and bbb["last_state_text"] == "A+ — broke the trigger"
    assert [t["text"] for t in bbb["timeline"]] == ["09:21 building", "10:31 A+ — broke the trigger"]
    aaa = by[("AAA", "bull_flag")]
    assert aaa["move_text"] == f"{GT._px(PX0)} → {GT._px(PX1)} ({(PX1 / PX0 - 1) * 100:+.1f}%) since first seen"
    assert aaa["text"] == f"AAA · 🚩 Bull Flag · first seen 09:21 ET trigger armed · now trigger armed · {aaa['move_text']}"
    assert aaa["vs_trigger_text"].endswith(f"vs the trigger at first sight ({GT._px(bf_armed()['trigger'])})")
    assert aaa["href"] == PT.deep_link("AAA", "bull_flag") and aaa["graveyard_on"] is None
    assert tr["unmeasured"].startswith("UNMEASURED") and "not a forecast" in tr["unmeasured"]
    first, last = PT.pass_times(S)
    assert tr["empty_today"] == (f"No potential first seen yet this session — the pass runs every "
                                 f"{GC.PASS_CADENCE_SEC // 60} minutes from {first} to {last} ET.")


def test_track_move_follows_the_bars_never_the_scanner_row_price(store):
    """AMENDMENTS4 D2: the move is the 5-minute close the pass wrote (PX0 → PX1), never the scanner row (ROW_PX)."""
    rows = build(GC.POTENTIAL_SUB, store)["track"]["today"]["rows"]
    assert all(GT._px(ROW_PX) not in (r["move_text"] or "") for r in rows)
    assert {r["last_px"] for r in rows} == {PX1} and {r["first_px"] for r in rows} == {PX0, PX1}


def test_track_yesterday_chronological_with_outcome_states_and_graveyard(store):
    y = build(GC.POTENTIAL_SUB, store)["track"]["yesterday"]
    assert y["date"] == PREV.isoformat() and y["n"] == 2
    assert y["title"] == (f"Last session ({PREV.isoformat()}) — 2 potentials and how each ended: states and prices "
                          "only, no win/loss maths")
    aaa, zzz = y["rows"]
    assert (aaa["symbol"], zzz["symbol"]) == ("AAA", "ZZZ")
    assert aaa["last_state_text"] == "stopped" and aaa["push_text"] == "📲 sent 09:21 ET"
    assert [t["text"] for t in aaa["timeline"]] == ["09:21 trigger armed", "10:01 stopped"]
    assert zzz["graveyard_on"] == S.isoformat()
    assert [t["text"] for t in zzz["timeline"]] == ["09:21 building", "10:01 partial — a rule failed",
                                                    f"09:21 🪦 graveyard {S.isoformat()}"]


def test_track_rows_are_capped_with_more_n(store, monkeypatch):
    monkeypatch.setattr(GC, "TILE_LIMIT_MAX", 2)
    today = build(GC.POTENTIAL_SUB, store)["track"]["today"]
    assert len(today["rows"]) == 2 and today["more_n"] == 4 and today["n"] == 6
    assert "more_n" not in build(GC.POTENTIAL_SUB, store)["track"]["yesterday"]


def test_joined_docs_show_their_word_in_the_track():
    """AMENDMENTS4 D9: a first pass after the mute with an empty tracker tracks without ringing — the Track says so."""
    st = day_store(with_tracker=False)
    counts, send = run(st, at(10, 6), {"XYZ": {"bull_flag": bf_armed()}}, px=PX0)
    assert counts["joined"] == 1 and send.calls == []
    r = build(GC.POTENTIAL_SUB, st)["track"]["today"]["rows"]
    assert r[0]["symbol"] == "XYZ" and r[0]["push_text"] == "held: " + PT.HELD_WORDS["joined_midsession"]


def test_track_says_sending_for_a_doc_left_claimed():
    """A pass that died between the claim and the settle leaves push.state "claimed" (it never rings again, K3); the
    Track row says so in W19's /alerts word instead of saying nothing."""
    st = day_store(with_tracker=False)
    run(st, at(9, 21), {"XYZ": {"bull_flag": bf_armed()}}, px=PX0, tape="premarket")
    st.coll(ST.POTENTIALS).update_one({"_id": PT.doc_id(S, "XYZ", "bull_flag")}, {"$set": {"push.state": "claimed"}})
    r = next(x for x in build(GC.POTENTIAL_SUB, st)["track"]["today"]["rows"] if x["symbol"] == "XYZ")
    assert r["push_text"] == "📲 sending" == GT.PUSH_TEXT["claimed"]
    assert build(GC.POTENTIAL_SUB, st)["track"]["today"]["pushed_n"] == 0      # NEGATIVE: claimed is not "sent"


def test_negative_unknown_push_state_prints_nothing():
    doc = {"symbol": "XYZ", "setup": "bull_flag", "push": {"state": "weird"}}
    assert GT._track_row(doc)["push_text"] is None


def test_watch_lists_list_names_with_no_potential():
    post = [{"symbol": "PST", "ah_gain_pct": 6.0, "close_pos": 0.9, "ah_volume": 3e5},
            {"symbol": "AAA", "ah_gain_pct": 5.0, "close_pos": 0.9, "ah_volume": 3e5}]
    w = build(GC.POTENTIAL_SUB, day_store(post_rows=post))["watch"]
    syms = [s["symbol"] for s in w["symbols"]]
    assert syms == ["PMX", "CARY", "PST"] and "AAA" not in syms    # NEGATIVE: a potential is never in the watch line
    assert w["symbols"][0]["href"] == "/chart-maps?tab=gajjala&sub=premarket&focus=PMX"
    assert w["symbols"][-1]["href"] == "/chart-maps?tab=gajjala&sub=postmarket&focus=PST"
    assert w["text"] == GT.WATCH_HEAD + "PMX, CARY, PST" and "(S8 13:21–14:34)" in w["text"]


def test_negative_watch_line_never_lists_a_name_whose_read_has_structure():
    """W14 says "no structure yet": a ☀️ name whose read already broke (BBB A+), failed a rule (EEE partial) or is
    forming without a base (GGG) has a card in a setup sub, so it is never on the watch line; PMX (no read) is."""
    st = day_store(with_tracker=False)
    st.record_qualifiers(S, at(8, 0), [dict(row(s), tape_session="premarket") for s in ("BBB", "EEE", "GGG")],
                         "premarket")
    out = build(GC.POTENTIAL_SUB, st)
    syms = [x["symbol"] for x in out["watch"]["symbols"]]
    assert not {"BBB", "EEE", "GGG", "AAA"} & set(syms)
    assert syms == ["PMX", "CARY"] and out["watch"]["text"] == GT.WATCH_HEAD + "PMX, CARY"
    pm = {t["symbol"] for t in build("premarket", st)["tiles"]}
    assert {"BBB", "EEE", "GGG"} <= pm                              # they ARE on his ☀️ list — only the line skips them


def test_watch_is_null_with_no_list_name():
    assert build(GC.POTENTIAL_SUB, fake_store())["watch"] is None


def test_potential_sub_empty_note_in_and_out_of_the_window():
    empty = fake_store()
    assert build(GC.POTENTIAL_SUB, empty)["empty_note"] == (
        f"Nothing forming on his list right now — the next pass is at most {GC.PASS_CADENCE_SEC // 60} minutes away.")
    assert build(GC.POTENTIAL_SUB, empty, now=at(21, 0))["empty_note"] == "Nothing was forming at the last pass (today)."


# ── (c) every sub ────────────────────────────────────────────────────────────────────────────────────────────────
def test_subs_end_with_potential_and_the_other_eight_keep_their_order(store):
    out = build("bull_flag", store)
    assert out["subs"][-1] == {"key": "potential", "emoji": "🧠", "label": "Potential", "count": 5}
    assert [s["key"] for s in out["subs"][:-1]] == ["bull_flag", "kiss_fly", "horizontal_fade", "intraday_vcp",
                                                     "reversal_squeeze", "premarket", "postmarket", "playbook"]


def test_every_sub_serves_the_live_potential_push_line_under_the_narrowed_a_plus_line(store):
    for k, _e, _l in GC.SUBS:
        out = build(k, store)
        assert out["push_potential"] == {"mode": "live", "text": PT.push_note(S)}, k
        assert "no A+ reaches your phone" in out["push"]["text"] and "nothing reaches" not in out["push"]["text"]


def test_route_serves_the_potential_sub(store, monkeypatch):
    from chart_maps import api as API
    from chart_maps import board as board_mod
    monkeypatch.setattr(ST, "default", lambda: store)
    monkeypatch.setattr(GT, "_clock", lambda: NOW)
    monkeypatch.setattr(board_mod, "_live_snapshot", lambda tiles: {})
    monkeypatch.setattr(board_mod, "attach_live_now", lambda tiles, out, live=None: None)
    resp = run_route(API.chart_maps_gajjala(sub="potential", tf="", focus="", sort="", limit=GC.TILE_LIMIT_DEFAULT))
    assert resp.status_code == 200
    body = json.loads(resp.body)
    assert body["sub"] == "potential" and {"track", "watch", "push_potential", "tiles", "subs"} <= set(body)
    assert [t["symbol"] for t in body["tiles"]][:2] == ["DDD", "AAA"] and "NaN" not in resp.body.decode()
    desc = inspect.signature(API.chart_maps_gajjala).parameters["sub"].default.description
    assert "| potential" in desc


# ── NEGATIVES over everything served ─────────────────────────────────────────────────────────────────────────────
def _potential_blocks(out):
    blocks = [out.get("potential"), out.get("track"), out.get("watch"), out.get("push_potential")]
    blocks += [t["gajjala"].get("potential") for t in out.get("tiles") or []]
    return [b for b in blocks if b]


def test_negative_no_none_nan_undefined_zero_float_forecast_or_b_word_anywhere(store):
    from chart_maps.high_beta_tab import FORBIDDEN_WORDS
    for k, _e, _l in GC.SUBS:
        out = build(k, store)
        blob = json.dumps(out, ensure_ascii=False, allow_nan=False)
        assert not B_WORD.search(blob), k
        for s in _walk_strings(out):
            assert s not in ("None", "nan", "NaN", "undefined"), (k, s)
        for b in _potential_blocks(out):
            for s in _walk_strings(b):
                low = s.lower()
                assert "None" not in s.split() and "NaN" not in s and "undefined" not in low, (k, s)
                assert not any(w in low for w in FORBIDDEN_WORDS), (k, s)
                assert "float 0" not in low and "float none" not in low, (k, s)


def test_negative_unknown_float_prints_no_float_badge(store):
    hhh = next(r for r in build("kiss_fly", store)["potential"]["rows"] if r["symbol"] == "HHH")
    assert [t["key"] for t in hhh["tells"]] == [] and "float" not in hhh["text"]


def test_every_title_line_carries_unmeasured(store):
    p = build(GC.POTENTIAL_SUB, store)
    assert "UNMEASURED" in build("bull_flag", store)["potential"]["title"]
    assert "UNMEASURED" in p["track"]["title"] and p["track"]["unmeasured"].startswith("UNMEASURED")
    assert "UNMEASURED" in p["push_potential"]["text"]
    assert all("UNMEASURED" in t["gajjala"]["state_label"] for t in p["tiles"])


# ── (d) resolve_sub: the push-history link opens the sub that rang ───────────────────────────────────────────────
def focus_store(*, push_kf=True, hold_kf=False, prev_day=False, alert=False, both=False):
    st = fake_store()
    st.record_qualifiers(S, at(9, 0), [row("XYZ")], "rth")
    st.upsert_read(S, "XYZ", read_doc("XYZ", {"bull_flag": bf_armed(), "kiss_fly": kf_building()}, ctx=ctx("XYZ")),
                   now=NOW)
    if prev_day:
        run(st, at(9, 21, PREV), {"XYZ": {"kiss_fly": kf_building()}}, px=PX0)
    elif hold_kf:
        run(st, at(9, 36), {"XYZ": {"kiss_fly": kf_building()}}, px=PX0)        # muted: held, never pushed
    elif push_kf:
        reads = {"kiss_fly": kf_building()}
        if both:
            reads["bull_flag"] = bf_armed()
        run(st, at(9, 21), {"XYZ": reads}, px=PX0)
    if alert:
        st.coll(ST.ALERTS).update_one({"_id": f"GG:{S.isoformat()}|XYZ|horizontal_fade"},
                                      {"$set": {"state": "pushed", "claimed_at": at(10, 20)}}, upsert=True)
    st.record_pass(S, NOW, {"status": "ok"})
    return st


def test_focus_with_a_pushed_potential_opens_that_setup_over_the_best_ranked_read():
    out = build("", focus_store(), focus="xyz")
    assert (out["sub"], out["sub_resolved_from"]) == ("kiss_fly", "focus_potential")
    assert (build("", focus_store(push_kf=False), focus="XYZ")["sub_resolved_from"]) == "focus_read"


def test_focus_potential_tie_takes_the_setups_order():
    out = build("", focus_store(both=True), focus="XYZ")
    assert (out["sub"], out["sub_resolved_from"]) == ("bull_flag", "focus_potential")


def test_negative_an_a_plus_claim_still_wins():
    out = build("", focus_store(alert=True), focus="XYZ")
    assert (out["sub"], out["sub_resolved_from"]) == ("horizontal_fade", "focus_alert")


def test_negative_an_unpushed_potential_falls_through_to_the_read():
    out = build("", focus_store(hold_kf=True), focus="XYZ")
    assert (out["sub"], out["sub_resolved_from"]) == ("bull_flag", "focus_read")
    doc = {"date": S.isoformat(), "symbol": "XYZ", "setup": "kiss_fly", "push": {"state": "no_target", "at": "x"}}
    assert GT._pushed_potential_setup([doc], "XYZ", S.isoformat()) is None


def test_negative_yesterdays_pushed_potential_is_ignored():
    out = build("", focus_store(prev_day=True), focus="XYZ")
    assert (out["sub"], out["sub_resolved_from"]) == ("bull_flag", "focus_read")
    prev_doc = {"date": PREV.isoformat(), "symbol": "XYZ", "setup": "kiss_fly",
                "push": {"state": "pushed", "at": at(9, 21, PREV).isoformat()}}
    assert GT._pushed_potential_setup([prev_doc], "XYZ", S.isoformat()) is None


def test_negative_a_raising_potentials_coll_falls_through_and_never_raises():
    good = focus_store()
    st = fake_store(**{n: (FakeColl(fail=True) if n == ST.POTENTIALS else good.coll(n)) for n in ST.ALL})
    out = build("", st, focus="XYZ")
    assert (out["sub"], out["sub_resolved_from"]) == ("bull_flag", "focus_read")
    res = GT.resolve_sub("", "XYZ", store=st, session=S, reads_by={}, listed={}, pm_syms=set(), post_syms=set())
    assert res == (GC.DEFAULT_SUB, "default")                       # potentials=None → the store read, which failed


def test_negative_an_explicit_sub_still_wins():
    out = build("intraday_vcp", focus_store(), focus="XYZ")
    assert (out["sub"], out["sub_resolved_from"]) == ("intraday_vcp", "param")


# ── GOLDEN: the FE fixture IS the served payload ─────────────────────────────────────────────────────────────────
def golden_payload() -> str:
    st = day_store()
    doc = {"_recipe": RECIPE, "boards": {"potential": build(GC.POTENTIAL_SUB, st), "bull_flag": build("bull_flag", st)}}
    return json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n"


def test_golden_fixture_is_the_served_payload():
    text = golden_payload()
    if os.environ.get("GG_WRITE_GOLDEN") == "1":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(text, encoding="utf-8")
    assert GOLDEN.exists(), f"missing {GOLDEN.name} — run: {RECIPE}"
    assert GOLDEN.read_text(encoding="utf-8") == text, f"the golden fixture drifted — run: {RECIPE}"
    boards = json.loads(text)["boards"]
    assert boards["potential"]["track"]["today"]["rows"] and boards["bull_flag"]["potential"]["rows"]
