"""ℹ️ the served legend for Gajjala's counts line and sub tabs (DECISIONS15 / BUILD_SPEC15 WP-A, 2026-10-18).

Ajay 2026-10-18, verbatim: "Ok Forming is still Criteria not met.. Potential is all the gajjalas criteria met. may be
add an info tag for them explicitly.. To tell me what athey are". His two readings are the wrong way round (forming =
no rule has failed yet; partial = a rule failed; potential = forming + the quiet base begun + the plain setup, not A+),
so the board serves ONE legend (`counts_legend`) and the 🧠 sub button's `title`; the FE prints, never types. Words
only — no methodology change. NEGATIVES pin his misreading the other way and the nine other subs' title as None.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import tab as GT
from tests.test_gajjala_potential_tab import GOLDEN as POT_GOLDEN
from tests.test_gajjala_potential_tab import build, day_store

B_WORD = re.compile("b" + "ounc", re.I)
TAB_DOC = Path(__file__).resolve().parents[2] / "docs" / "gajjala" / "gajjala_tab_2026_10_13.md"
TRADER_DOC = Path(__file__).resolve().parents[2] / "docs" / "gajjala" / "trader_names_2026_10_27.md"   # 2026-10-27
COUNT_KEYS = tuple(GT.COUNT_STATES) + ("awaiting_answer", "listed")    # the served `counts` keys, in order (pin)


def legend_by():
    return {r["key"]: r for r in GT.count_legend()}


# (1) shape, order, words
def test_legend_keys_are_the_legend_keys_in_order_and_every_word_and_text_is_a_string():
    rows = GT.count_legend()
    assert tuple(r["key"] for r in rows) == GT.LEGEND_KEYS
    # WIDENED 2026-10-27 (BUILD_SPEC26 §3.3): the 📌 "trader" row appended LAST
    assert GT.LEGEND_KEYS == tuple(GT.COUNT_STATES) + ("awaiting_answer", "listed", "potential", "track", "trader")
    for r in rows:
        assert set(r) == {"key", "word", "text"}
        assert isinstance(r["word"], str) and r["word"].strip(), r
        assert isinstance(r["text"], str) and r["text"].strip(), r


def test_NEGATIVE_no_b_word_no_fake_and_no_digit_in_any_legend_text():
    for r in GT.count_legend():
        for s in (r["word"], r["text"]):
            assert not B_WORD.search(s), r
            assert "fake" not in s.lower(), r
        if r["key"] == "trader":
            # WIDENED 2026-10-27 (BUILD_SPEC26 §3.3 + A2): the 📌 row's two numbers are BUILT from constants (the
            # fresh window and GG's floor in millions) — every digit in it is one of them, none typed
            from chart_maps.gajjala import trader_names as TN
            want = sorted({str(GC.TRADER_NAMES_FRESH_SESSIONS), str(GC.SCAN_MIN_VOLUME // 1_000_000)})
            assert sorted(set(re.findall(r"\d+", r["text"]))) == want, r
            assert r == TN.legend_row()
        elif r["key"] != "none":
            assert not any(ch.isdigit() for ch in r["text"]), r          # no number is typed in a legend text


def test_words_are_the_counts_line_labels():
    words = {k: r["word"] for k, r in legend_by().items()}
    assert words == {"aplus": "A+", "triggered": "triggered", "forming": "forming", "partial": "partial",
                     "stopped": "stopped", "invalid": "invalid", "none": "none",
                     "awaiting_answer": "awaiting your number", "listed": "listed", "potential": "🧠 Potential",
                     "track": "📈 Track", "trader": "📌 trader"}         # WIDENED 2026-10-27: the 📌 row


# (2) his misreading, pinned the other way
def test_forming_says_no_rule_has_failed_and_partial_says_a_rule_failed():
    by = legend_by()
    assert "no rule has failed" in by["forming"]["text"]
    assert "a rule failed" in by["partial"]["text"]


def test_NEGATIVE_forming_is_not_criteria_not_met_and_potential_is_not_every_rule_met():
    by = legend_by()
    assert "criteria not met" not in by["forming"]["text"].lower()
    assert "every rule met" not in by["potential"]["text"].lower()
    assert "a rule failed" not in by["forming"]["text"]                  # NEGATIVE: forming never reads as partial
    assert "no rule has failed" not in by["partial"]["text"]


# (3) one source for the potential text
def test_potential_text_is_the_rules_lines_sentence_plus_the_per_symbol_sentence():
    text = legend_by()["potential"]["text"]
    first = PT.rules_lines()[0]
    head = first.split(". On top")[0] + "."
    clause = PT.defaults_clauses()[0][2]
    base = clause[0].upper() + clause[1:] + ("" if clause.endswith((".", "!", "?")) else ".")
    # WIDENED 2026-10-18 (critic fix, DECISIONS15 D1 over BUILD_SPEC15's bare cut): the base clause rides along, as
    # its own sentence (capitalised, closed with ".")
    assert text == head + " " + base + GT.POTENTIAL_LEGEND_TAIL
    assert ". the " not in text and ") Counted" not in text            # NEGATIVE: no run-on punctuation
    assert first.startswith(head)
    assert text.endswith(GT.POTENTIAL_LEGEND_TAIL)
    assert "On top" not in text and "Badges" not in text                 # NEGATIVE: only the first sentence


def test_potential_text_follows_the_needs_base_setting(monkeypatch):
    monkeypatch.setattr(GC, "POTENTIAL_NEEDS_BASE", False)
    off = legend_by()["potential"]["text"]
    assert "no sideways bar is needed" in off.lower()                    # the clause words, not its punctuation
    assert "at least one sideways bar" not in off.lower()                        # NEGATIVE: never the base wording when off
    monkeypatch.setattr(GC, "POTENTIAL_NEEDS_BASE", True)
    on = legend_by()["potential"]["text"]
    assert "at least one sideways bar" in on.lower()                             # NEGATIVE with True: it names the base
    assert "no sideways bar is needed" not in on.lower()


# (4) the A+ text carries the rules_info phrase's words
def test_aplus_text_carries_every_rule_and_closed():
    t = legend_by()["aplus"]["text"]
    assert "every rule" in t and "closed" in t and "rings only when" in t
    assert "the fresh entry (rings" not in t                             # NEGATIVE: a stale A+ never rings (critic fix)


def test_none_text_names_the_held_reads():
    t = legend_by()["none"]["text"]
    assert "float rule" in t and "detector error" in t


def test_NEGATIVE_none_and_invalid_never_point_at_a_served_reason():
    """none / invalid reads never get a card (TILE_STATES), so no text may send him to a reason nothing shows."""
    by = legend_by()
    assert "none" not in GT.TILE_STATES and "invalid" not in GT.TILE_STATES
    for k in ("none", "invalid"):
        assert "served reason" not in by[k]["text"], k
    assert "every rule" not in legend_by()["forming"]["text"]           # NEGATIVE


def test_awaiting_and_track_and_listed_texts():
    by = legend_by()
    assert by["awaiting_answer"]["text"] == "held by a rule whose number you have not given"
    assert "a record, not a list to act on" in by["track"]["text"]
    assert "scanner" in by["listed"]["text"]


# (5) build() serves it on every sub; the 🧠 title only on the 🧠 sub
def test_build_serves_the_legend_on_a_setup_sub_the_potential_sub_and_premarket():
    st = day_store()
    want = GT.count_legend()
    for sub in ("bull_flag", GC.POTENTIAL_SUB, "premarket", "playbook", GC.LEDGER_SUB):
        out = build(sub, st)
        assert out["sub"] == sub
        assert out["counts_legend"] == want, sub


def test_subs_title_is_the_potential_text_on_the_brain_sub_only():
    st = day_store()
    pot = legend_by()["potential"]["text"]
    for sub in ("bull_flag", GC.POTENTIAL_SUB, "premarket"):
        subs = build(sub, st)["subs"]
        assert len(subs) == len(GC.SUBS) == 10
        titled = [s["key"] for s in subs if s["title"] is not None]
        assert titled == [GC.POTENTIAL_SUB]
        assert next(s for s in subs if s["key"] == GC.POTENTIAL_SUB)["title"] == pot
        others = [s for s in subs if s["key"] != GC.POTENTIAL_SUB]
        assert len(others) == 9 and all(s["title"] is None for s in others)   # NEGATIVE: None on the other nine
        assert all("title" in s for s in subs)


def test_NEGATIVE_the_ledger_sub_keeps_no_legend_title():
    subs = build("bull_flag", day_store())["subs"]
    assert next(s for s in subs if s["key"] == GC.LEDGER_SUB)["title"] is None


# (6) the served counts are untouched
def test_counts_dict_keys_are_unchanged():
    st = day_store()
    for sub in ("bull_flag", GC.POTENTIAL_SUB, "premarket"):
        c = build(sub, st)["counts"]
        assert tuple(c) == COUNT_KEYS, sub
        assert all(isinstance(v, int) for v in c.values())
        assert "potential" not in c and "track" not in c                 # NEGATIVE: the legend adds no count


def test_the_potential_golden_carries_the_served_legend():
    doc = json.loads(POT_GOLDEN.read_text(encoding="utf-8"))
    for name, board in doc["boards"].items():
        assert board["counts_legend"] == GT.count_legend(), name


def test_as_sentence_capitalises_and_closes_any_clause():
    assert GT._as_sentence("a clause (tag)") == "A clause (tag)."
    assert GT._as_sentence("done.") == "Done."
    assert GT._as_sentence("why?") == "Why?"
    assert GT._as_sentence("a note (it ends.)") == "A note (it ends.)"     # NEGATIVE: never a doubled stop
    assert GT._as_sentence("") == ""


def test_the_tab_doc_carries_every_served_legend_text_verbatim():
    """The doc's legend table is generated from count_legend() (keep in sync): every served word and text, verbatim,
    under the shipped settings — the potential row's middle sentence follows POTENTIAL_NEEDS_BASE."""
    doc = TAB_DOC.read_text(encoding="utf-8")
    assert "verbatim (generated from tab.count_legend(); keep in sync)" in doc
    for r in GT.count_legend():
        # WIDENED 2026-10-27 (BUILD_SPEC26 §4 WP-B): the 📌 "trader" row is documented verbatim in its own doc
        # (docs/gajjala/trader_names_2026_10_27.md) — the 10-13 tab doc is not this package's file
        where = TRADER_DOC.read_text(encoding="utf-8") if r["key"] == "trader" else doc
        assert f"| {r['word']} | {r['text']} |" in where, r["key"]
