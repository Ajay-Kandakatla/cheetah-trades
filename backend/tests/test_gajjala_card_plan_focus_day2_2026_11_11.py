"""🚩 Gajjala's tab — the entry spec's served card / board words (WP-TAB, 2026-11-11).

Ajay 2026-11-11, verbatim: "Also apply your proposal too. / Here is how he enters please tell me to enter based on this /
Can you check for any mistakes". tab.py serves, the FE prints verbatim:
  T1 `gajjala.plan_text` — "Entry above X · stop Y · risk r%" on an entry read, "trigger … · stop … · risk …" otherwise;
  T2 `chips.vol_dried` — 💧 the read's own k3_vol criterion met on a live read (proposal #4, an indicator);
  T3 `focus` + `tile.focus` — 🔝 Focus 5 on GG5's five setup subs and 🧠 (proposal #9, display only);
  T4 `day2` — 🌅 yesterday's live A+ and after-hours movers on GG5's ☀️ sub (proposal #8, a list, never a push);
  T5 `push_break` + 🧠 Track `brk_text` — the ⚡ break_watch words, lazily imported (absent / raising → None).
NEGATIVES on every one. Nothing here is a gate, a threshold or a push.
"""
from __future__ import annotations

import sys

import pytest

from chart_maps.gajjala import break_watch as BW
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from tests import test_gajjala_potential_tab as PTT
from tests.test_gajjala_tab import NOW, ORDER_READS, EXPECTED, PREV, R, S, latest, read_doc, scan_doc, store_with

BF = "bull_flag"
B_WORD = PTT.B_WORD


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


def board(sub, st, **kw):
    return GT.build(sub, now=kw.pop("now", NOW), store=st, **kw)


def store_of(reads: dict, carry=None):
    st = store_with(reads=[read_doc(s, {BF: r}) for s, r in reads.items()], scans=[scan_doc(s) for s in reads],
                    passes=[latest()])
    if carry:
        st.replace_ah_carry(PREV, PTT.at(19, 56, PREV), carry)
    return st


def flag(st, *syms):
    st.coll(ST.STATE).docs[ST.BROKER_STATE_ID] = {"_id": ST.BROKER_STATE_ID, "added": list(syms), "removed": []}
    return st


# ── T1 the served plan line ──────────────────────────────────────────────────────────────────────────────────────
GG = dict(trigger=1.17, stop=1.12, risk_pct=(1.17 - 1.12) / 1.17 * 100)      # his §1 example, the read's own levels


def test_T1_entry_reads_say_entry_above():
    assert GT.plan_text(R(BF, "forming", ready=True, **GG)) == "Entry above 1.17 · stop 1.12 · risk 4.3%"
    assert GT.plan_text(R(BF, "aplus", broke=True, **GG)) == "Entry above 1.17 · stop 1.12 · risk 4.3%"


@pytest.mark.parametrize("read", [R(BF, "forming", ready=False, **GG), R(BF, "partial", **GG),
                                  R(BF, "stopped", **GG), R(BF, "triggered", **GG)],
                         ids=["building", "partial", "stopped", "triggered"])
def test_T1_NEGATIVE_every_other_read_with_a_trigger_says_trigger_never_entry(read):
    t = GT.plan_text(read)
    assert t == "trigger 1.17 · stop 1.12 · risk 4.3%"
    assert "Entry" not in t


@pytest.mark.parametrize("read", [R(BF, "forming", ready=True, trigger=None), {}, None,
                                  R(BF, "aplus", trigger=float("nan")), R(BF, "aplus", trigger="x")])
def test_T1_NEGATIVE_no_trigger_no_plan_line(read):
    assert GT.plan_text(read) is None


def test_T1_parts_dropped_when_missing_and_sub_dollar_on_the_broker_grid():
    assert GT.plan_text(R(BF, "forming", ready=True, trigger=1.17, stop=None, risk_pct=None)) == "trigger 1.17"
    assert GT.plan_text(R(BF, "partial", trigger=1.17, stop=1.12, risk_pct=None)) == "trigger 1.17 · stop 1.12"
    t = GT.plan_text(R(BF, "forming", ready=True, trigger=0.3101, stop=0.29, risk_pct=6.48))
    assert t == "Entry above 0.3101 · stop 0.29 · risk 6.5%"
    assert t.split(" · ")[0].split()[-1] == GT._px(0.3101)                   # the BUY line's own text


def test_T1_every_card_serves_plan_text_equal_to_its_lines():
    out = board(BF, store_of(ORDER_READS))
    assert [t["symbol"] for t in out["tiles"]] == EXPECTED
    for t in out["tiles"]:
        g = t["gajjala"]
        assert "plan_text" in g
        buy = next(ln for ln in t["lines"] if ln["tone"] == "buy")
        head = "Entry above" if GT._is_entry_read(ORDER_READS[t["symbol"]]) else "trigger"
        assert g["plan_text"].startswith(f"{head} {buy['text']} · stop "), t["symbol"]
        assert buy["label"].startswith("BUY > ") == (head == "Entry above")
    by = {t["symbol"]: t["gajjala"]["plan_text"] for t in out["tiles"]}
    assert by["DDD"] == "Entry above 4.10 · stop 3.95 · risk 4.1%"            # forming-ready
    assert by["FFF"].startswith("trigger 4.12")                               # building


# 2026-11-11 critic fix — a no-risk / no-plan entry read is a level, never "Entry above" (TEAD 2026-10-30 bull_flag:
# forming-ready, trigger 0.291 = stop 0.291; the ledger calls it no_risk and the push refuses it).
@pytest.mark.parametrize("state,extra", [("forming", {"ready": True}), ("aplus", {"broke": True})], ids=["ready", "aplus"])
@pytest.mark.parametrize("trig,stop,risk,want", [
    (2.0, 2.0, 0.0, "trigger 2.00 · stop 2.00 · risk 0.0%"),                 # no_risk: trigger == stop
    (0.291, 0.291, 0.0, "trigger 0.291 · stop 0.291 · risk 0.0%"),           # the TEAD card
    (2.0, 2.05, -2.5, "trigger 2.00 · stop 2.05 · risk -2.5%"),              # no_plan: stop above the trigger
    (1.17, None, 4.3, "trigger 1.17 · risk 4.3%"),                            # no_plan: no stop
], ids=["no_risk", "tead_no_risk", "stop_above", "no_stop"])
def test_T1_NEGATIVE_no_risk_or_no_plan_entry_read_says_trigger(state, extra, trig, stop, risk, want):
    t = GT.plan_text(R(BF, state, trigger=trig, stop=stop, risk_pct=risk, **extra))
    assert t == want and "Entry" not in t


def test_T1_NEGATIVE_an_unloadable_ledger_never_says_entry(monkeypatch):
    monkeypatch.setattr(GT, "_ledger", lambda: None)
    assert GT.plan_text(R(BF, "forming", ready=True, **GG)) == "trigger 1.17 · stop 1.12 · risk 4.3%"


def test_T1_a_no_risk_card_on_the_board_says_trigger():
    out = board(BF, store_of({"AAA": R(BF, "forming", ready=True, trigger=2.0, stop=2.0, risk_pct=0.0)}))
    assert out["tiles"][0]["gajjala"]["plan_text"] == "trigger 2.00 · stop 2.00 · risk 0.0%"


# ── T2 💧 volume dried ───────────────────────────────────────────────────────────────────────────────────────────
K3 = [{"key": D.K3_VOL_KEY, "label": "K3 volume dried up on the pullback", "ok": True}]


@pytest.mark.parametrize("state", list(D.LIVE_STATES))
def test_T2_vol_dried_on_a_live_read_with_k3_met(state):
    assert GT.vol_dried_text(R(BF, state, criteria=K3)) == GT.VOL_DRIED_TEXT == "💧 volume dried up"
    out = board(BF, store_of({"AAA": R(BF, state, criteria=K3, ready=True, entry_bar_t="2026-10-13 10:25")}))
    assert out["tiles"][0]["gajjala"]["chips"]["vol_dried"] == "💧 volume dried up"


@pytest.mark.parametrize("read", [
    R(BF, "forming", criteria=[dict(K3[0], ok=False)]),
    R(BF, "forming", criteria=[dict(K3[0], ok=None)]),
    R(BF, "forming", criteria=[dict(K3[0], ok="true")]),
    R(BF, "forming", criteria=[dict(K3[0], key="k2", ok=True)]),
    R(BF, "forming", criteria=[]),
    R(BF, "partial", criteria=K3), R(BF, "stopped", criteria=K3), R(BF, "invalid", criteria=K3),
], ids=["ok_false", "ok_none", "ok_truthy_str", "other_key", "no_criteria", "partial", "stopped", "invalid"])
def test_T2_NEGATIVE_no_vol_dried_key(read):
    assert GT.vol_dried_text(read) is None
    out = board(BF, store_of({"AAA": read}))
    for t in out["tiles"]:
        assert "vol_dried" not in t["gajjala"]["chips"]


def test_T2_NEGATIVE_list_cards_never_carry_it():
    st = PTT.day_store()
    for sub in ("premarket", "postmarket"):
        for t in board(sub, st)["tiles"]:
            assert "vol_dried" not in t["gajjala"]["chips"], sub


# ── T3 🔝 Focus 5 ────────────────────────────────────────────────────────────────────────────────────────────────
def test_T3_text_is_built_on_the_constant():
    assert GC.FOCUS_N == 5                       # the text says "Focus 5" / "first five" — a change here moves both
    assert GT.FOCUS_TEXT.startswith(f"🔝 Focus {GC.FOCUS_N} — the first five cards")
    assert "Display only" in GT.FOCUS_TEXT and not B_WORD.search(GT.FOCUS_TEXT)


def test_T3_more_than_five_cards_first_five_flagged_and_block_served():
    out = board(BF, store_of(ORDER_READS))
    assert len(out["tiles"]) == 9 > GC.FOCUS_N
    assert out["focus"] == {"n": GC.FOCUS_N, "text": GT.FOCUS_TEXT}
    assert [t["symbol"] for t in out["tiles"] if t.get("focus") is True] == EXPECTED[:GC.FOCUS_N]
    assert [t["symbol"] for t in out["tiles"]] == EXPECTED                   # never reorders, never drops


def test_T3_NEGATIVE_five_cards_no_block_no_flags():
    five = dict(list(ORDER_READS.items())[:5])
    out = board(BF, store_of(five))
    assert len(out["tiles"]) == GC.FOCUS_N
    assert "focus" not in out and not any("focus" in t for t in out["tiles"])


def test_T3_a_broker_name_is_never_a_focus_card_same_for_every_viewer():
    for owner in (True, False):
        out = board(BF, flag(store_of(ORDER_READS), "AAA"), owner=owner)
        syms = [t["symbol"] for t in out["tiles"]]
        assert syms[-1] == "AAA"                                              # broker_bottom ran first
        assert [t["symbol"] for t in out["tiles"] if t.get("focus")] == ["BBB", "CCC", "DDD", "EEE", "FFF"], owner


def test_T3_NEGATIVE_a_broker_name_in_the_first_five_is_skipped_the_sixth_gets_it():
    tiles = [{"symbol": s} for s in ("A1", "B2", "C3", "D4", "E5", "F6", "G7")]
    assert GT.focus_block(tiles, frozenset({"B2"})) == {"n": GC.FOCUS_N, "text": GT.FOCUS_TEXT}
    assert [t["symbol"] for t in tiles if t.get("focus")] == ["A1", "C3", "D4", "E5", "F6"]
    assert "focus" not in tiles[1] and "focus" not in tiles[6]
    assert GT.focus_block([{"symbol": "X"}] * 5, frozenset()) is None
    every = [{"symbol": s} for s in ("A1", "B2", "C3", "D4", "E5", "F6")]
    assert GT.focus_block(every, frozenset(t["symbol"] for t in every)) is None   # all 🚫 → no header over nothing
    assert not any("focus" in t for t in every)


def test_T3_NEGATIVE_fewer_than_five_non_broker_cards_no_header_no_marks():
    """2026-11-11 critic fix: 7 cards, 5 of them 🚫 → only 2 could be marked, so the "first five cards" header is not
    served and no card is marked."""
    tiles = [{"symbol": s} for s in ("A1", "B2", "C3", "D4", "E5", "F6", "G7")]
    assert GT.focus_block(tiles, frozenset({"A1", "B2", "C3", "D4", "E5"})) is None
    assert not any("focus" in t for t in tiles)
    four = [{"symbol": s} for s in ("A1", "B2", "C3", "D4", "E5", "F6", "G7")]
    assert GT.focus_block(four, frozenset({"A1", "B2", "C3"})) is None          # 4 non-🚫 → still no header
    assert not any("focus" in t for t in four)
    five = [{"symbol": s} for s in ("A1", "B2", "C3", "D4", "E5", "F6", "G7")]
    assert GT.focus_block(five, frozenset({"A1", "B2"})) == {"n": GC.FOCUS_N, "text": GT.FOCUS_TEXT}
    assert [t["symbol"] for t in five if t.get("focus")] == ["C3", "D4", "E5", "F6", "G7"]


@pytest.mark.parametrize("variant", [V.GG1, V.GGA], ids=["gg1", "audited"])
def test_T3_NEGATIVE_gg1_and_audited_boards_have_no_focus(variant):
    out = board(BF, store_of(ORDER_READS), variant=variant)
    assert len(out["tiles"]) > GC.FOCUS_N
    assert "focus" not in out and not any("focus" in t for t in out["tiles"])


@pytest.mark.parametrize("sub", ["premarket", "postmarket", GC.LEDGER_SUB, "playbook"])
def test_T3_NEGATIVE_list_subs_and_the_track_record_have_no_focus(sub):
    out = board(sub, PTT.day_store())
    assert "focus" not in out and not any("focus" in t for t in out.get("tiles") or [])


def test_T3_the_potential_sub_takes_focus_by_the_same_rule():
    out = board(GC.POTENTIAL_SUB, PTT.day_store())
    n = len(out["tiles"])
    marked = [t["symbol"] for t in out["tiles"] if t.get("focus")]
    assert n > GC.FOCUS_N                                                     # the fixture day: six 🧠 cards
    assert out["focus"]["n"] == GC.FOCUS_N and marked == [t["symbol"] for t in out["tiles"]][:GC.FOCUS_N]
    assert "focus" not in out["tiles"][GC.FOCUS_N]


# ── T4 🌅 Day 2 ──────────────────────────────────────────────────────────────────────────────────────────────────
def day2_store():
    reads = {"AAA": R(BF, "forming"), "CAR": R(BF, "forming")}                 # listed today: AAA, CAR
    st = store_of(reads, carry=[{"symbol": "CAR", "ah_move_pct": 9.0, "price": 2.0, "day_c": 1.8},
                                {"symbol": "BBB", "ah_move_pct": 14.0, "price": 11.0, "day_c": 10.0}])
    return PTT.seed(st,
                    PTT.entry_doc(d=PREV, sym="AAA", setup="bull_flag", when=PTT.at(9, 50, PREV)),
                    PTT.entry_doc(d=PREV, sym="AAA", setup="kiss_fly", when=PTT.at(9, 41, PREV)),  # same name, earlier
                    PTT.entry_doc(d=PREV, sym="BBB", setup="bull_flag", when=PTT.at(10, 5, PREV)),
                    PTT.entry_doc(d=PREV, sym="SHD", state="shadow", prefix="SHADOW:"),           # NEG shadow
                    PTT.entry_doc(d=PREV, sym="REF", state="suppressed_first15",
                                  suffix="#suppressed_first15"),                                  # NEG refusal
                    PTT.entry_doc(d=PREV, sym="FLD", state="failed"),                             # NEG failed
                    PTT.entry_doc(d=S, sym="TOD", setup="bull_flag"))                             # NEG today's ring


def test_T4_day2_rows_in_order_one_per_name():
    out = board("premarket", day2_store())
    b = out["day2"]
    assert b["title"] == "🌅 Day 2 — last session's A+ and after-hours movers" and b["note"] == GT.DAY2_NOTE
    assert b["note"].startswith("List only, no push.") and not B_WORD.search(b["note"])
    # MOVED 2026-11-11 (T-PINS #4): the row words say "last session", never "yesterday" (a Monday reads Friday).
    assert b["empty_text"] == "No A+ rang and no after-hours mover passed his checks last session."
    assert b["rows"] == [
        {"symbol": "AAA", "text": f"AAA · {GT._setup_label('kiss_fly')} A+ rang 09:41 ET last session · on today's list",
         "href": PT.deep_link("AAA", "kiss_fly")},
        {"symbol": "BBB", "text": f"BBB · {GT._setup_label('bull_flag')} A+ rang 10:05 ET last session",
         "href": PT.deep_link("BBB", "bull_flag")},
        {"symbol": "CAR", "text": "CAR · 🌙 after-hours mover last session · on today's list",
         "href": "/chart-maps?tab=gajjala&sub=premarket&focus=CAR"},
    ]
    syms = [r["symbol"] for r in b["rows"]]
    assert not {"SHD", "REF", "FLD", "TOD"} & set(syms)                    # NEG shadow / refusal / failed / today


def test_T4_NEGATIVE_day2_row_words_never_say_yesterday():
    # 2026-11-11 (T-PINS #4): on a Monday the prior session is Friday — the row words and the empty line say
    # "last session", never "yesterday" (the title is not part of this move).
    for w in (GT.DAY2_APLUS_TEXT, GT.DAY2_CARRY_TEXT, GT.DAY2_EMPTY):
        assert "yesterday" not in w.lower() and "last session" in w, w


def test_T4_NEGATIVE_day2_only_on_gg5_premarket():
    st = day2_store()
    for k, _e, _l in GC.SUBS:
        out = board(k, st)
        assert ("day2" in out) == (k == "premarket"), k
    for variant in (V.GG1, V.GGA):
        assert "day2" not in board("premarket", st, variant=variant)


def test_T4_NEGATIVE_empty_serves_the_empty_text():
    st = store_of({"AAA": R(BF, "forming")})
    st.replace_ah_carry(PREV, PTT.at(19, 56, PREV), [])                       # a pass ran, nothing passed → names {}
    out = board("premarket", st)
    assert out["day2"]["rows"] == [] and out["day2"]["empty_text"] == GT.DAY2_EMPTY


def test_T4_NEGATIVE_an_unknown_carry_serves_no_block_never_no_mover(monkeypatch):
    """2026-11-11 critic fix: no carry doc (no after-hours pass wrote one) or a raising carry read → day2 None, never
    "no after-hours mover passed his checks" on a carry that was never read; the ☀️ board still serves and the entries
    read still runs once."""
    st = store_of({"AAA": R(BF, "forming")})
    assert st.ah_carry(PREV) is None
    out = board("premarket", st)
    assert out["day2"] is None and out["tiles"] is not None
    st = day2_store()
    monkeypatch.setattr(st, "ah_carry", PTT._boom)
    real, calls = st.alert_rows, []
    monkeypatch.setattr(st, "alert_rows", lambda sessions: (calls.append(1), real(sessions))[1])
    out = board("premarket", st)
    assert out["day2"] is None and out["tiles"] is not None and len(calls) == 1
    assert GT.day2_block(st, S, PREV, {}, None, entries={}, carry=None) is None
    assert GT.day2_block(st, S, PREV, {}, None, entries={}, carry="x") is None
    b = GT.day2_block(st, S, PREV, {}, None, entries={}, carry={"names": {}})
    assert b["rows"] == [] and b["empty_text"] == GT.DAY2_EMPTY


def test_T4_NEGATIVE_an_unknown_entries_read_serves_no_block_never_nothing_rang(monkeypatch):
    st = day2_store()
    monkeypatch.setattr(st, "alert_rows", lambda sessions: None)
    out = board("premarket", st)
    assert out["day2"] is None and out["tiles"] is not None                  # the ☀️ board still serves
    monkeypatch.setattr(st, "alert_rows", PTT._boom)
    assert board("premarket", st)["day2"] is None


def test_T4_one_alert_rows_read_per_premarket_build(monkeypatch):
    st = day2_store()
    real, calls = st.alert_rows, []
    monkeypatch.setattr(st, "alert_rows", lambda sessions: (calls.append(list(sessions)), real(sessions))[1])
    board("premarket", st)
    assert len(calls) == 1 and PREV in calls[0]


def test_T4_a_bare_call_reads_its_own_prev_session():
    st = day2_store()
    b = GT.day2_block(st, S, PREV, {"AAA": {}})
    assert [r["symbol"] for r in b["rows"]] == ["AAA", "BBB", "CAR"]
    assert b["rows"][2]["text"] == "CAR · 🌙 after-hours mover last session"     # not on the handed list


# ── T5 ⚡ push_break + 🧠 Track brk_text ──────────────────────────────────────────────────────────────────────────
def test_T5_push_break_on_every_gg5_board_with_the_mode_word():
    st = PTT.day_store()
    want = BW.status()
    for k, _e, _l in GC.SUBS:
        pb = board(k, st)["push_break"]
        assert set(pb) == {"mode", "text"}, k                                 # NEG: no process counter is served
        assert pb["mode"] == BW.mode() == GC.GAJJALA_BREAK_PUSH_MODE, k
        assert pb["text"] == want["text"] and pb["text"].startswith("⚡ Break pushes:"), k


@pytest.mark.parametrize("variant", [V.GG1, V.GGA], ids=["gg1", "audited"])
def test_T5_NEGATIVE_no_push_break_off_gg5(variant):
    for sub in (BF, GC.POTENTIAL_SUB, "premarket"):
        assert "push_break" not in board(sub, PTT.day_store(), variant=variant), sub


def _brk(st, sym, setup, brk):
    doc = next(d for d in st.coll(ST.POTENTIALS).docs.values() if d.get("symbol") == sym and d.get("setup") == setup
               and d.get("date") == S.isoformat())
    doc["brk"] = brk
    return st


def test_T5_track_rows_carry_brk_text_for_pushed_and_shadow_only():
    st = PTT.day_store()
    _brk(st, "DDD", "reversal_squeeze", {"state": "pushed", "at_et": "10:07:12"})
    _brk(st, "EEE", "bull_flag", {"state": "shadow", "at_et": "10:33:05"})
    rows = PTT.track_rows(board(GC.POTENTIAL_SUB, st))
    assert rows[("DDD", "reversal_squeeze")]["brk_text"] == "⚡ break rang 10:07:12 ET"
    assert rows[("EEE", "bull_flag")]["brk_text"] == "⚡ break seen 10:33:05 ET (shadow)"
    others = [r for k, r in rows.items() if k not in (("DDD", "reversal_squeeze"), ("EEE", "bull_flag"))]
    assert others and all("brk_text" in r and r["brk_text"] is None for r in others)


@pytest.mark.parametrize("brk", [{"state": "claimed", "at_et": "10:07:12"}, {"state": "failed", "at_et": "10:07:12"},
                                 {"state": "pushed"}, {"state": "pushed", "at_et": "10:07"}, "pushed", None],
                         ids=["claimed", "failed", "no_time", "bad_time", "not_a_dict", "none"])
def test_T5_NEGATIVE_brk_text_none_otherwise(brk):
    rows = PTT.track_rows(board(GC.POTENTIAL_SUB, _brk(PTT.day_store(), "DDD", "reversal_squeeze", brk)))
    assert rows[("DDD", "reversal_squeeze")]["brk_text"] is None


def test_T5_NEGATIVE_a_raising_break_watch_serves_none_and_the_board_builds(monkeypatch):
    st = _brk(PTT.day_store(), "DDD", "reversal_squeeze", {"state": "pushed", "at_et": "10:07:12"})
    want = [t["symbol"] for t in board(GC.POTENTIAL_SUB, st)["tiles"]]
    monkeypatch.setattr(BW, "status", PTT._boom)
    monkeypatch.setattr(BW, "track_text", PTT._boom)
    out = board(GC.POTENTIAL_SUB, st)
    assert out["push_break"] is None and [t["symbol"] for t in out["tiles"]] == want
    assert all(r["brk_text"] is None for r in out["track"]["today"]["rows"])


def test_T5_NEGATIVE_an_absent_break_watch_module_serves_none(monkeypatch):
    import chart_maps.gajjala as pkg
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala.break_watch", None)        # import → ImportError
    monkeypatch.delattr(pkg, "break_watch", raising=False)
    st = _brk(PTT.day_store(), "DDD", "reversal_squeeze", {"state": "pushed", "at_et": "10:07:12"})
    out = board(GC.POTENTIAL_SUB, st)
    assert out["push_break"] is None and out["tiles"]
    assert all(r["brk_text"] is None for r in out["track"]["today"]["rows"])


def test_NEGATIVE_no_served_word_here_says_the_b_word():
    st = day2_store()
    for sub in (BF, "premarket", GC.POTENTIAL_SUB):
        out = board(sub, st)
        for s in (out.get("focus") or {}).get("text"), (out.get("push_break") or {}).get("text"):
            assert not (s and B_WORD.search(s)), sub
    assert not B_WORD.search(GT.VOL_DRIED_TEXT + GT.DAY2_NOTE + GT.DAY2_EMPTY)
