"""alerts.ENTRY_WORDS — the setup's entry in GG's words, each line citing the verified_rules.json rule it comes from
(DECISIONS10 D2, BUILD_SPEC10 §3.2 / §1.4, AMENDMENTS10 F5, 2026-10-16).

Ajay 2026-10-16: "LIke for some he says we need to make sure EMA is kissed you alert me when that happens". The A+ entry
push now carries one clause per setup; nothing may put a word in GG's mouth. This file reads the alerts.py SOURCE (the
FROZEN format the contracts parse too): `ENTRY_WORDS = {` at column 0, one `"<setup>": "<template>",  # <ids>` line per
setup, `}` alone at column 0 — and checks every cited id against verified_rules.json. NEGATIVES: an id from another
topic, a missing id, a first-hand claim the file does not back.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC

PKG = Path(AL.__file__).resolve().parent
SRC = Path(AL.__file__).read_text(encoding="utf-8")
RULES = json.loads((PKG / "verified_rules.json").read_text(encoding="utf-8"))
ID_RE = re.compile(r"\b((?:BF|KF|HF|VCP|RS)\d+)\b")
LINE_RE = re.compile(r'^\s+"([a-z_]+)":\s*"((?:[^"\\]|\\.)*)",\s*#(.*)$')


def _block_lines(src: str) -> list:
    m = re.search(r"^ENTRY_WORDS = \{\n([\s\S]*?)\n\}$", src, re.M)
    assert m, "alerts.py lost the FROZEN `ENTRY_WORDS = {` … `}` block (column 0)"
    return [ln for ln in m.group(1).split("\n") if ln.strip()]


def _parsed(src: str = SRC) -> dict:
    """{setup: (template, comment)} from the source lines."""
    out = {}
    for ln in _block_lines(src):
        m = LINE_RE.match(ln)
        assert m, f"ENTRY_WORDS line is not `\"setup\": \"template\",  # ids`: {ln[:80]}"
        out[m.group(1)] = (m.group(2), m.group(3))
    return out


def _topics() -> dict:
    """{rule id: (topic key, status)}."""
    return {r["id"]: (t["key"], r.get("status")) for t in RULES["topics"] for r in t.get("verified", [])}


def _check(parsed: dict) -> list:
    errs = []
    topics = _topics()
    for setup, (_tpl, cmt) in parsed.items():
        ids = ID_RE.findall(cmt)
        if not ids:
            errs.append(f"{setup}: cites no verified_rules id")
        for i in ids:
            if i not in topics:
                errs.append(f"{setup}: cites {i} — not in verified_rules.json")
            elif topics[i][0] != setup:
                errs.append(f"{setup}: cites {i} — a rule of the {topics[i][0]} topic")
        first_hand = [i for i in ids if topics.get(i, (None, None))[1] == "confirmed_first_hand"]
        if setup == "reversal_squeeze":
            if first_hand:
                errs.append(f"{setup}: cites first-hand {first_hand} — revisit the words and this pin")
            if "no first-hand entry rule on file" not in cmt:
                errs.append(f"{setup}: the comment must say \"no first-hand entry rule on file\"")
        elif not first_hand:
            errs.append(f"{setup}: no cited id is confirmed_first_hand")
    return errs


def test_the_block_parses_and_its_keys_are_the_setups_in_order():
    parsed = _parsed()
    assert list(parsed) == list(GC.SETUPS) == list(AL.ENTRY_WORDS)
    for setup, (tpl, _c) in parsed.items():
        assert tpl == AL.ENTRY_WORDS[setup]                              # the source line IS the served template


def test_every_cited_id_exists_in_its_own_topic_and_the_first_hand_claims_hold():
    assert _check(_parsed()) == []


def test_the_reversal_squeeze_clause_is_honest_about_its_sources():
    """RS2 / RS4 are 2+ sources (confirmed_multi_source), none first-hand — a truth pin: when a first-hand entry rule
    is filed, revisit the words."""
    topics = _topics()
    _tpl, cmt = _parsed()["reversal_squeeze"]
    ids = ID_RE.findall(cmt)
    assert set(ids) >= {"RS2", "RS4"}
    assert all(topics[i][1] != "confirmed_first_hand" for i in ids)
    assert "no first-hand entry rule on file" in cmt


def test_the_words_assume_two_constants():
    assert GC.KF_HONOR_ALL_PULLBACK_CLOSES is True, \
        'ENTRY_WORDS["kiss_fly"] says "honored" — it assumes every pullback close holds the fast EMA; revisit the words'
    assert GC.HF_TRIGGER == "base_high", \
        'ENTRY_WORDS["horizontal_fade"] says "the new highs" — it assumes the base-high trigger; revisit the words'


def test_templates_use_only_the_ema_placeholders():
    for setup, tpl in AL.ENTRY_WORDS.items():
        assert set(re.findall(r"\{(\w*)\}", tpl)) <= {"fast", "slow"}, setup
        assert not re.search(r"\d", tpl), setup


# ── NEGATIVES: the checker bites ─────────────────────────────────────────────────────────────────────────────────
def _mutate(old: str, new: str) -> str:
    assert SRC.count(old) == 1, old
    return SRC.replace(old, new)


def test_NEGATIVE_an_id_from_another_topic_fails():
    bad = _mutate("# BF2 (S8 21:45", "# KF1 (S8 21:45")
    errs = _check(_parsed(bad))
    assert any("bull_flag: cites KF1" in e for e in errs)


def test_NEGATIVE_an_unknown_id_fails():
    bad = _mutate("# BF2 (S8 21:45", "# BF99 (S8 21:45")
    assert any("BF99" in e and "not in verified_rules" in e for e in _check(_parsed(bad)))


def test_NEGATIVE_a_line_citing_nothing_fails():
    parsed = dict(_parsed())
    parsed["kiss_fly"] = (parsed["kiss_fly"][0], " the kiss, no id")
    assert any("kiss_fly: cites no verified_rules id" in e for e in _check(parsed))


def test_NEGATIVE_a_multi_source_only_line_fails_the_first_hand_rule():
    parsed = dict(_parsed())
    parsed["bull_flag"] = (parsed["bull_flag"][0], " BF7 (S9 1:59:24)")   # BF7 alone is confirmed_multi_source
    assert any("bull_flag: no cited id is confirmed_first_hand" in e for e in _check(parsed))


def test_NEGATIVE_a_squeeze_line_claiming_first_hand_fails():
    parsed = dict(_parsed())
    parsed["reversal_squeeze"] = (parsed["reversal_squeeze"][0], " RS8 RS2")   # RS8 is first-hand, not an entry rule
    errs = _check(parsed)
    assert any("reversal_squeeze: cites first-hand" in e for e in errs)
    assert any("no first-hand entry rule on file" in e for e in errs)


def _key_pin_ok(parsed: dict) -> bool:
    return list(parsed) == list(GC.SETUPS) == list(AL.ENTRY_WORDS)


def test_NEGATIVE_a_dropped_setup_breaks_the_key_pin():
    """2026-10-16 polish: the dropped line is cut from a MUTATED copy of the REAL alerts.py source and re-parsed —
    never a key popped from the parsed dict."""
    assert _key_pin_ok(_parsed())                                                  # control: the source passes
    line = next(ln for ln in _block_lines(SRC) if ln.lstrip().startswith('"intraday_vcp":'))
    bad = _mutate(line + "\n", "")
    parsed = _parsed(bad)
    assert "intraday_vcp" not in parsed and len(parsed) == len(GC.SETUPS) - 1
    assert not _key_pin_ok(parsed)
