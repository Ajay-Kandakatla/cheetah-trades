"""🧾 The ℹ️ panel's journal list — supply_demand/rules_info._gg_journal_clause (spec accountability §4 WP-BE3,
2026-11-23).

Ajay, verbatim: "I think I am going outside Gajjalas now.. Please create a rule to warn me to not over trade and hold me
accountable if I am missing out any gajjalas rules". House rule: every new rule gets a rules_info line built from its
constants. The ONE list "🧾 your journal checks (GG)" rides the 🚩 section's note (the panel renders only picks / stops /
alerts + the note, and those three lists are pinned): A1–A11 and O2–O4, each with its rule words and quote ref read off
accountability.CHECK_META / QUOTES, every number a constant (MY_DAY_CAP, MY_DAY_CAP_QUIET, MY_REENTRY_MIN,
NO_TRADE_AFTER_OPEN_MIN, GG_LOSS_RISK_CUT …) read at call time. NEGATIVES: a mutated constant moves the line, a raising
module drops only the clause, no b-word, nothing lands in picks / stops / alerts.
"""
from __future__ import annotations

import ast
import inspect
import re
import sys

import pytest

from chart_maps.gajjala import accountability as AC
from chart_maps.gajjala import constants as GC
from daytrading import data as DTD
from supply_demand import rules_info as RI
from trading import gajjala_entry as GLN

TAIL = " UNMEASURED — no study here says these setups win. Not advice."


def _line() -> str:
    return RI._gg_journal_clause()


def _note() -> str:
    return RI._gajjala_section()["note"]


def _ids_in(line: str) -> list:
    return re.findall(r"(?:^|; |: )([AO]\d+) (?:a GG rule|a warning|information only|words only)", line)


# ── placement ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_list_rides_the_note_after_high_si_and_before_the_one_minute_clause():
    note, line = _note(), _line()
    assert line.startswith(" 🧾 your journal checks (GG) — ") and line in note and note.count(line) == 1
    hs, one = RI._gg_high_si_clause(), RI._gg_one_minute_clause()
    if hs:
        assert note.index(hs) < note.index(line)
    assert note.index(line) < note.index(one) < note.index(TAIL)
    assert note.endswith(RI._gg_audited_clause() + TAIL)                 # the 🧪 tail pin holds


def test_NEGATIVE_nothing_lands_in_picks_stops_or_alerts_and_no_new_key():
    sec = RI._gajjala_section()
    assert set(sec) == {"title", "emoji", "picks", "stops", "alerts", "note"}
    assert len(sec["picks"]) == 8 and len(sec["stops"]) <= 6
    body = " ".join(sec["picks"] + sec["stops"] + sec["alerts"])
    assert "🧾" not in body and "journal" not in body


# ── content: every check, its ref, read off the engine ───────────────────────────────────────────────────────────
def test_every_check_appears_once_in_order_with_its_quote_ref():
    line = _line()
    want = [c for c in AC.CHECK_IDS if c != "O4"] + [AC.WEEK_ID, "O4"]
    assert _ids_in(line) == want
    for cid, (kind, rule, ref) in AC.CHECK_META.items():
        seg = "%s %s: %s" % (cid, RI._GG_JOURNAL_KIND_WORDS[kind], rule)
        assert line.count(seg) == 1, cid
        tail = line[line.index(seg):].split("; ")[0]
        assert tail.endswith("(%s)" % ref) or tail.endswith("(%s)." % ref), (cid, tail)
    _six, week_q, _j = AC.QUOTES
    assert "%s words only" % AC.WEEK_ID in line and "(%s %s · VR M4, a paraphrase)" % (week_q["source"], week_q["ts"]) in line


def test_NEGATIVE_the_dropped_checks_are_not_listed():
    """A6 size, O1 open cap, N1 Plaid are NOT built (HIS CALLs #8 / #7 / #11) — named as not checked, never a check."""
    line = _line()
    for gone in ("A6", "O1", "N1"):
        assert gone not in _ids_in(line) and not re.search(r"\b%s\b" % gone, line), gone
    assert "size, open positions and Plaid are not checked (HIS CALLs #8 / #7 / #11)" in line


def test_the_hard_soft_info_words_follow_the_engine_kinds():
    line = _line()
    for cid, (kind, _r, _q) in AC.CHECK_META.items():
        assert "%s %s:" % (cid, RI._GG_JOURNAL_KIND_WORDS[kind]) in line
    assert "A1 a warning:" in line                                       # A1 can never make a trade 🟠 (C1)
    assert "A5 information only:" in line and "printed, never a flag" in line


def test_the_mine_lines_say_mine_his_call():
    line = _line()
    o2 = next(s for s in line.split("; ") if s.startswith("O2 "))
    a8 = next(s for s in line.split("; ") if s.startswith("A8 "))
    a7 = next(s for s in line.split("; ") if s.startswith("A7 "))
    assert "MINE — HIS CALL #2" in o2 and "GG gives no cap" in o2
    assert "MINE — HIS CALL #3" in a8
    assert "MINE — lane HIS CALL #18" in a7 and "(his cut)" in a7


def test_NEGATIVE_a_moved_engine_ref_moves_the_line(monkeypatch):
    """The rule words and refs are read off CHECK_META, never retyped here."""
    kind, rule, _ref = AC.CHECK_META["A2"]
    monkeypatch.setitem(AC.CHECK_META, "A2", (kind, rule, "S8 99:99"))
    assert "(S8 99:99)" in _line() and "(S8 14:41)" not in _line()


# ── numbers: every one a constant ────────────────────────────────────────────────────────────────────────────────
def _strip_refs(line: str) -> str:
    for _cid, (_k, _r, ref) in AC.CHECK_META.items():
        line = line.replace(ref, "")
    for q in AC.QUOTES:
        line = line.replace("%s %s" % (q["source"], q["ts"]), "")
    line = re.sub(r"HIS CALLs? #\d+(?: / #\d+)*", "", line)
    line = re.sub(r"\b[A-Z]{1,2}\d+\b", "", line)                       # ids and rule codes: A2, R4, E3, X7, M4, S8
    return line


def test_every_number_in_the_list_is_a_constant_value():
    frame = int(GC.RUN_BASE_FRAME.rstrip("m"))
    allowed = {"%g" % x for x in (GC.MY_DAY_CAP, GC.MY_DAY_CAP_QUIET, GC.MY_REENTRY_MIN, GC.MY_REENTRY_BARS, frame,
                                   GC.NO_TRADE_AFTER_OPEN_MIN, GLN.GG_LOSS_RISK_CUT)}
    allowed |= {DTD.ET_RTH_OPEN.strftime("%H:%M"), DTD.ET_RTH_CLOSE.strftime("%H:%M"),
                "%02d:%02d" % (DTD.ET_RTH_OPEN.hour, DTD.ET_RTH_OPEN.minute + GC.NO_TRADE_AFTER_OPEN_MIN)}
    body = _strip_refs(_line())
    toks = re.findall(r"\d{1,2}:\d{2}|\d+(?:\.\d+)?", body)
    assert toks, "the list prints its numbers"
    bad = [t for t in toks if t not in allowed]
    assert bad == [], bad


def test_the_shipped_numbers_print():
    line = _line()
    assert "before trade #%d of the day" % GC.MY_DAY_CAP in line
    assert "(#%d on a quiet strip day)" % GC.MY_DAY_CAP_QUIET in line
    assert "under %d min (%d bars of %d min" % (GC.MY_REENTRY_MIN, GC.MY_REENTRY_BARS,
                                                int(GC.RUN_BASE_FRAME.rstrip("m"))) in line
    assert "his first %d minutes" % GC.NO_TRADE_AFTER_OPEN_MIN in line
    assert "≤ %g× that trade's $ risk" % GLN.GG_LOSS_RISK_CUT in line


MUTATIONS = [
    (GC, "MY_DAY_CAP", 4, "before trade #4 of the day"),
    (GC, "MY_DAY_CAP_QUIET", 1, "(#1 on a quiet strip day)"),
    (GC, "MY_REENTRY_MIN", 15, "under 15 min"),
    (GC, "MY_REENTRY_BARS", 3, "(3 bars of"),
    (GC, "RUN_BASE_FRAME", "3m", "bars of 3 min"),
    (GC, "NO_TRADE_AFTER_OPEN_MIN", 20, "a tap in 09:30–09:50 ET, his first 20 minutes"),
    (GLN, "GG_LOSS_RISK_CUT", 0.4, "≤ 0.4× that trade's $ risk"),
]


@pytest.mark.parametrize("mod,name,val,want", MUTATIONS, ids=[m[1] for m in MUTATIONS])
def test_NEGATIVE_mutating_a_constant_moves_the_line(monkeypatch, mod, name, val, want):
    assert want not in _line()
    monkeypatch.setattr(mod, name, val)
    assert want in _line() and want in _note()


def test_NEGATIVE_no_numeric_literal_in_the_clause_source():
    tree = ast.parse(inspect.getsource(RI._gg_journal_clause).lstrip())
    lits = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
            and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)]
    assert lits == []
    src = inspect.getsource(RI._gg_journal_clause)
    for typed in ("1:28:10", "1:29:16", "14:41", "1:17:12", "46:47", "0.5", "09:45"):
        assert typed not in src, typed


# ── the panel never breaks on it; words only ─────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_raising_import_empties_the_clause_and_the_panel_still_serves(monkeypatch):
    import chart_maps.gajjala as PKG
    monkeypatch.delattr(PKG, "accountability", raising=False)
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala.accountability", None)
    assert RI._gg_journal_clause() == ""
    secs = RI.sections()
    assert "gajjala" in secs and "fallen" in secs
    note = secs["gajjala"]["note"]
    assert "🧾" not in note and note.endswith(TAIL) and "None" not in note


def test_NEGATIVE_a_broken_engine_table_empties_the_clause(monkeypatch):
    monkeypatch.setattr(AC, "QUOTES", ())                                 # unpacking raises
    assert RI._gg_journal_clause() == ""
    assert "gajjala" in RI.sections()


def test_NEGATIVE_no_b_word_no_other_method_and_no_trade_word():
    line = _line()
    assert not re.search("b" + "ounc", line, re.I)
    assert not re.search(r"\bSEPA\b|Minervini|Bonde|TLSW|TTLAC", line)
    low = line.lower()
    for w in ("buy now", "sell now", "you should", "edge", "win rate"):
        assert w not in low, w
    assert "words only, never a gate, a push or a block on your broker" in line
    assert "times are your taps, not fills" in line


def test_NEGATIVE_none_never_prints():
    assert "None" not in _line()
