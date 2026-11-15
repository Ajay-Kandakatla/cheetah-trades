"""📶 GG's base count on the card — run_bases.card_block / ellipses / quote and tab.setup_tile (spec ggbase §3.1 / §3.3 /
WP-A step 7, 2026-11-15).

Ajay, verbatim: "There is a concept of 3 bases and climax run can you bake that in to the app please" · "I need that
tracked in to Gajjala's" · "Just show it". One muted card line in GG's words (served text, the FE types none) + one GG
chart mark per base of the current run, on the counting frame only. Never a counter line, never a red tone.
"""
from __future__ import annotations

import copy
import json

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import playbook as PB
from chart_maps.gajjala import run_bases as RB
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from tests.fixtures.gajjala import detector_frames as FX
from tests.test_gajjala_run_bases_2026_11_15 import THREE, frame_of

D = "2026-10-13"


def _base(n, state, a, z, broke_t=None, lo=10.0, hi=11.0):
    return {"n": n, "from_t": f"{D} {a}", "to_t": f"{D} {z}", "bars": 6, "lo": lo, "hi": hi, "state": state,
            "broke_t": f"{D} {broke_t}" if broke_t else None, "quiet": True, "shallow": True,
            "leg": {"s_t": f"{D} 09:40", "e_t": f"{D} 09:45", "bars": 2}}


def _blk(n_broke: int, *, forming: bool = False, state=None, runs_before: list | None = None):
    bases = [_base(k + 1, RB.BROKE, "10:%02d" % (k * 10), "10:%02d" % (k * 10 + 5), "10:%02d" % (k * 10 + 10))
             for k in range(n_broke)]
    if forming:
        bases.append(_base(n_broke + 1, RB.FORMING, "11:00", "11:25"))
    st = state or (RB.FORMING if forming else RB.RUNNING)
    run = {"from_t": f"{D} 09:40", "high_t": f"{D} 10:55", "state": st, "n": n_broke, "bases": bases}
    runs = list(runs_before or []) + [run]
    return {"version": RB.VERSION, "frame": "5m", "from": "rth", "until": "rth", "restart": True,
            "depth_floor": False, "as_of_bar_t": f"{D} 11:25", "runs": runs, "n": n_broke, "forming": forming,
            "state": st}


def _item(section, ts, source):
    sec = getattr(PB, section)
    items = sec[1] if isinstance(sec, tuple) else sec
    return next(it for it in items if it.get("ts") == ts and it.get("source") == source and it.get("verbatim"))


# ── quotes ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_quotes_are_the_playbook_items_byte_equal():
    for key, (section, ts, source) in {"climax": ("MANAGEMENT", "40:54–41:18", "S8"),
                                       "out": ("MANAGEMENT", "1:00:37", "S8"),
                                       "counter": ("SQUEEZE", "55:18–57:49", "S9")}.items():
        it = _item(section, ts, source)
        assert RB.quote(key) == {"text": it["text"], "ts": it["ts"], "source": it["source"]}, key
    assert "third base, this is a climax run" in RB.quote("climax")["text"]
    assert "fourth base, I came out of everything" in RB.quote("out")["text"]
    assert RB.quote("nope") == {}


# ── the line words ──────────────────────────────────────────────────────────────────────────────────────────────
def test_base_words_shape_is_pinned_to_ggs_numbers():
    assert len(RB.BASE_WORDS) == GC.RUN_BASE_OUT_N
    assert "climax" in RB.BASE_WORDS[GC.RUN_BASE_CLIMAX_N - 1]
    assert "came out of everything" in RB.BASE_WORDS[GC.RUN_BASE_OUT_N - 1]


@pytest.mark.parametrize("k", [1, 2, 3, 4, 5])
def test_words_for_every_count_with_a_forming_base(k):
    cb = RB.card_block(_blk(k - 1, forming=True))
    words = RB.BASE_WORDS[k - 1] if k <= len(RB.BASE_WORDS) else RB.PAST_WORDS.format(n=k)
    assert cb["text"] == f"📶 {words} · forming since 11:00 ET · 5-min bars"
    assert cb["n"] == k - 1 and cb["state"] == RB.FORMING and cb["frame"] == "5m"


def test_exact_words_at_one_to_four_and_five():
    texts = [RB.card_block(_blk(k))["text"] for k in (1, 2, 3, 4, 5)]
    assert texts[0] == "📶 1st base · broke out 10:10 ET · 5-min bars"
    assert texts[1] == "📶 2nd base · broke out 10:20 ET · 5-min bars"
    assert texts[2] == "📶 3rd base — climax run, GG peels early · broke out 10:30 ET · 5-min bars"
    assert texts[3] == "📶 4th base — GG came out of everything · broke out 10:40 ET · 5-min bars"
    assert texts[4] == "📶 5 bases — past GG's 4th (he came out of everything at the 4th) · broke out 10:50 ET · 5-min bars"


def test_stalled_status_names_the_last_new_high():
    cb = RB.card_block(_blk(2, state=RB.STALLED))
    assert cb["text"] == "📶 2nd base · no new high since 10:55 ET · 5-min bars" and cb["state"] == RB.STALLED


def test_title_carries_his_quote_the_counter_quote_and_not_computed():
    t = RB.card_block(_blk(2))["title"]
    c, q = RB.quote("counter"), RB.quote("climax")
    assert f"GG S8 40:54–41:18: “{q['text']}”" in t
    assert f"S9 55:18–57:49: “{c['text']}” — not computed" in t
    assert "his example(s)" in t and "UNMEASURED" in t and "your call" in t
    assert f"{GC.RUN_BASE_MIN_BARS}–{GC.RUN_BASE_MAX_BARS} printed 5-min bars" in t
    assert "from the 09:30 ET open to the 16:00 ET close" in t
    assert RB.FLAG_WORDS not in t                                     # his answer: the shortest base is 6 bars
    t4 = RB.card_block(_blk(4))["title"]
    assert f"“{RB.quote('out')['text']}”" in t4 and RB.quote("climax")["text"] not in t4


def test_title_words_move_with_every_switch(monkeypatch):
    monkeypatch.setattr(GC, "RUN_BASE_MIN_BARS", GC.K4_BF_PULL_MIN)
    monkeypatch.setattr(GC, "RUN_BASE_FROM", "session")
    monkeypatch.setattr(GC, "RUN_BASE_UNTIL", "session")
    monkeypatch.setattr(GC, "RUN_BASE_DEPTH_FLOOR", True)
    monkeypatch.setattr(GC, "RUN_BASE_RESTART", False)
    t = RB.card_block(_blk(1))["title"]
    assert RB.FLAG_WORDS in t and "1–24 printed" in t
    assert "from the premarket through after hours" in t
    assert "holding the upper half of the run up's last big green bar" in t
    assert "; the count runs the whole window" in t


def test_NEGATIVE_the_card_never_carries_a_counter_key():
    for blk in (_blk(1), _blk(2, forming=True), _blk(3, state=RB.STALLED)):
        cb = RB.card_block(blk)
        assert set(cb) == {"n", "state", "text", "title", "frame"} and "counter_text" not in cb


@pytest.mark.parametrize("blk", [None, {}, {"runs": []}, {"runs": "x"}, "junk", 3])
def test_NEGATIVE_unusable_block_has_no_card(blk):
    assert RB.card_block(blk) is None


def test_NEGATIVE_no_base_in_the_current_run_has_no_line():
    assert RB.card_block(_blk(0)) is None
    # right after a restart: the earlier run had bases, the new one none yet → no line
    old = _blk(2, state=RB.STALLED)["runs"]
    assert RB.card_block(_blk(0, runs_before=old)) is None


def test_NEGATIVE_the_words_never_advise():
    blob = json.dumps([RB.card_block(_blk(k)) for k in (1, 2, 3, 4, 5)], ensure_ascii=False).lower()
    for w in ("sell", "buy", "exit", "b" + "ounce"):
        assert w not in blob, w


# ── the marks ───────────────────────────────────────────────────────────────────────────────────────────────────
def _served(blk):
    return [{"t": f"{D} %02d:%02d" % divmod(m, 60)} for m in range(9 * 60 + 35, 12 * 60, 5)]


def test_one_mark_per_base_of_the_current_run():
    blk = _blk(3, forming=True)
    marks = RB.ellipses(blk, _served(blk), "5m")
    assert [m["n"] for m in marks] == [1, 2, 3, 4]
    assert [m["label"] for m in marks] == list(RB.MARK_LABELS)
    assert all(m["kind"] == RB.MARK_KIND == "run_base" and m["tone"] == "structure" for m in marks)
    assert marks[0]["note"] == f"GG S8 40:54–41:18: “{RB.quote('climax')['text']}”"
    assert marks[3]["note"] == f"GG S8 1:00:37: “{RB.quote('out')['text']}”"
    assert (marks[0]["from_t"], marks[0]["to_t"], marks[0]["lo"], marks[0]["hi"]) == (f"{D} 10:00", f"{D} 10:05",
                                                                                       10.0, 11.0)


def test_past_the_fourth_the_mark_says_base_n():
    blk = _blk(5)
    assert RB.ellipses(blk, _served(blk), "5m")[-1]["label"] == "base 5"


def test_NEGATIVE_marks_only_on_the_counting_frame_and_served_stamps():
    blk = _blk(2)
    assert RB.ellipses(blk, _served(blk), "15m") == []
    assert RB.ellipses(blk, _served(blk), "1m") == []
    only_first = [b for b in _served(blk) if b["t"] <= f"{D} 10:05"]
    assert [m["n"] for m in RB.ellipses(blk, only_first, "5m")] == [1]
    assert RB.ellipses(blk, [], "5m") == [] and RB.ellipses(None, _served(blk), "5m") == []


def test_NEGATIVE_earlier_runs_are_never_drawn():
    old = _blk(2, state=RB.STALLED)["runs"]
    blk = _blk(1, runs_before=old)
    marks = RB.ellipses(blk, _served(blk), "5m")
    assert [m["n"] for m in marks] == [1] and len(marks) == 1


def test_NEGATIVE_a_non_finite_box_draws_nothing():
    blk = _blk(1)
    blk["runs"][-1]["bases"][0]["lo"] = float("nan")
    assert RB.ellipses(blk, _served(blk), "5m") == []


# ── tab.setup_tile ──────────────────────────────────────────────────────────────────────────────────────────────
def _tile_bars(F, tf="5m"):
    return [{"t": F.t[i], "o": F.o[i], "h": F.h[i], "l": F.l[i], "c": F.c[i], "v": F.v[i]} for i in F.today]


def _doc(setup, read=None, with_bases=True, **extra):
    F, _st = frame_of(THREE)
    bars = _tile_bars(F)
    doc = {"symbol": "ABC", "setups": {setup: dict(read or {"setup": setup, "state": "forming", "frame": "5m"})},
           "tile": {"bars5": bars, "curves5": [], "vol_avg5": None, "bars15": bars[::3], "curves15": [],
                    "vol_avg15": None}}
    if with_bases:
        doc["run_bases"] = RB.count(F)
    doc.update(extra)
    return doc


def _tile(doc, setup, tf="5m", v=None):
    return GT.setup_tile(doc, setup, tf, scan_row={}, sess={}, listed=None, v=v)


@pytest.mark.parametrize("setup", [s for s in GC.SETUPS if s != "reversal_squeeze"])
def test_every_setup_card_serves_the_line_and_the_marks(setup):
    doc = _doc(setup)
    t = _tile(doc, setup)
    rb = t["gajjala"]["run_bases"]
    assert rb == RB.card_block(doc["run_bases"])
    assert rb["text"].startswith("📶 3rd base — climax run, GG peels early · forming since")
    assert [e["n"] for e in t["ellipses"]] == [1, 2, 3] and {e["kind"] for e in t["ellipses"]} == {"run_base"}


def test_the_squeeze_card_draws_its_marks_then_the_bases():
    setup = "reversal_squeeze"
    sm_only = _tile(_doc(setup, with_bases=False), setup)["ellipses"]
    t = _tile(_doc(setup), setup)
    assert t["ellipses"][:len(sm_only)] == sm_only
    assert [e["kind"] for e in t["ellipses"][len(sm_only):]] == ["run_base"] * 3


def test_NEGATIVE_a_doc_without_run_bases_is_byte_equal_to_today():
    for setup in GC.SETUPS:
        doc = _doc(setup, with_bases=False)
        t = _tile(doc, setup)
        assert "run_bases" not in t["gajjala"], setup
        if setup != "reversal_squeeze":
            assert "ellipses" not in t, setup
        with_none = _doc(setup, with_bases=False, run_bases=None)
        assert json.dumps(_tile(with_none, setup), sort_keys=True, default=str) == json.dumps(t, sort_keys=True,
                                                                                             default=str)


def test_NEGATIVE_a_block_with_no_base_adds_no_key():
    F = FX.frame([FX.quiet(10.0)] * 30)
    doc = _doc("bull_flag", with_bases=False, run_bases=RB.count(F))
    t = _tile(doc, "bull_flag")
    assert "run_bases" not in t["gajjala"] and "ellipses" not in t


def test_NEGATIVE_fade_on_fifteen_minutes_line_yes_marks_no():
    setup = "horizontal_fade"
    t = _tile(_doc(setup, read={"setup": setup, "state": "forming", "frame": "15m"}), setup, tf="15m")
    assert t["tf"] == "15m" and "run_bases" in t["gajjala"] and "ellipses" not in t


def test_gg1_card_line_on_1m_marks_only_on_the_5m_toggle():
    setup = "bull_flag"
    F, _st = frame_of(THREE)
    bars5 = _tile_bars(F)
    doc = {"symbol": "ABC", "setups": {setup: {"setup": setup, "state": "forming", "frame": "1m"}},
           "tile": {"bars1": bars5, "curves1": [], "vol_avg1": None, "bars5": bars5, "curves5": [], "vol_avg5": None},
           "run_bases": RB.count(F)}
    t1 = _tile(doc, setup, tf="1m", v=V.GG1)
    assert t1["tf"] == "1m" and "run_bases" in t1["gajjala"] and "ellipses" not in t1
    t5 = _tile(doc, setup, tf="5m", v=V.GG1)
    assert t5["tf"] == "5m" and [e["n"] for e in t5["ellipses"]] == [1, 2, 3]


def test_gga_card_serves_the_same_line():
    setup = "bull_flag"
    doc = _doc(setup)
    t = _tile(doc, setup, v=V.GGA)
    assert t["gajjala"]["run_bases"] == RB.card_block(doc["run_bases"])


def test_NEGATIVE_the_doc_is_never_mutated():
    doc = _doc("bull_flag")
    before = copy.deepcopy(doc)
    _tile(doc, "bull_flag")
    assert doc == before
