"""Source guards for backend/chart_maps/gajjala/*.py (BUILD_SPEC §3.4.1 / §3.6 / WP5a, 2026-10-13).

1. NOT SEPA: no module of the package imports another method's engine (sepa.scanner / bonde / vcp / trend / stage /
   qoq / sales / research). `sepa.prices` and `sepa.symbols` are the house DATA layer and stay allowed.
2. No served string names another method ("SEPA", "Minervini", "Bonde", "TLSW", "TTLAC") — EXCEPT a Playbook item
   with `verbatim: True` whose text is BYTE-equal to a fragment of one line of the FIRST_HAND notes (his own S8 9:45
   self-description). Checked on the source's string literals AND on everything the tab actually serves. Docstrings
   and comments are not served and are not checked for the names; the tile link `/sepa/SYM` is the house ticker page.
3. "Reversal", never the b-word: not in any file of the package — code, strings, docstrings or comments — except the
   house module names that keep it internally. GG's own b-word quotes are served bracket-edited ("[reverses]").
"""
from __future__ import annotations

import ast
import re
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[1] / "chart_maps" / "gajjala"
FILES = sorted(PKG.glob("*.py"))
FIXTURE_LINES = (Path(__file__).resolve().parent / "fixtures" / "gajjala" /
                 "first_hand_2026_10_13.md").read_text(encoding="utf-8").splitlines()
BANNED_IMPORTS = re.compile(r"^sepa\.(scanner|bonde|vcp|trend|stage|qoq|sales|research)\b")
BANNED_SEPA_SUBMODULES = {"scanner", "bonde", "vcp", "trend", "stage", "qoq", "sales", "research"}
NAMES = re.compile(r"\bSEPA\b|minervini|bonde|\bTLSW\b|\bTTLAC\b", re.I)
B_WORD = re.compile("b" + "ounc", re.I)
HOUSE_IDENTIFIERS = re.compile(r"bounce_room|quick_bounce|zone_bounce|sepa_bounce|BounceRoom")   # internal names keep it


def _docstring_nodes(tree) -> set:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None) or []
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                out.add(id(body[0].value))
    return out


def _string_literals(tree) -> list:
    docs = _docstring_nodes(tree)
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]


def in_one_fixture_line(text: str) -> bool:
    return any(text in line for line in FIXTURE_LINES)


def served_violations(items) -> list:
    """The served-string rule: a banned name is allowed ONLY in a verbatim item byte-equal to a fixture fragment."""
    bad = []
    for it in items:
        text = it.get("text", "") if isinstance(it, dict) else str(it)
        if not NAMES.search(text):
            continue
        ok = isinstance(it, dict) and it.get("verbatim") is True and in_one_fixture_line(text)
        if not ok:
            bad.append(text[:80])
    return bad


def test_the_package_has_the_files_this_guard_must_cover():
    names = {f.name for f in FILES}
    assert {"constants.py", "tab.py", "playbook.py", "detectors.py", "scanner.py"} <= names


@pytest.mark.parametrize("path", FILES, ids=[f.name for f in FILES])
def test_no_other_methods_engine_is_imported(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                assert not BANNED_IMPORTS.match(a.name), (path.name, a.name)
                assert not re.search(r"bonde", a.name, re.I), (path.name, a.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert not BANNED_IMPORTS.match(mod), (path.name, mod)
            assert not re.search(r"bonde", mod, re.I), (path.name, mod)
            if mod == "sepa":
                for a in node.names:
                    assert a.name not in BANNED_SEPA_SUBMODULES, (path.name, a.name)


def test_negative_the_import_guard_catches_a_banned_import():
    for src in ("from sepa import scanner", "import sepa.bonde", "from sepa.trend import x", "from sepa.qoq import y"):
        tree = ast.parse(src)
        hit = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                hit |= any(BANNED_IMPORTS.match(a.name) for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                hit |= bool(BANNED_IMPORTS.match(node.module or "")) or (
                    node.module == "sepa" and any(a.name in BANNED_SEPA_SUBMODULES for a in node.names))
        assert hit, src
    ok = ast.parse("from sepa import prices, symbols")
    assert not any(isinstance(n, ast.ImportFrom) and any(a.name in BANNED_SEPA_SUBMODULES for a in n.names)
                   for n in ast.walk(ok))


@pytest.mark.parametrize("path", FILES, ids=[f.name for f in FILES])
def test_no_string_literal_names_another_method_unless_his_verbatim_line(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for s in _string_literals(tree):
        if NAMES.search(s):
            assert in_one_fixture_line(s), (path.name, s[:80])


@pytest.mark.parametrize("path", FILES, ids=[f.name for f in FILES])
def test_no_b_word_anywhere_in_the_package(path):
    text = HOUSE_IDENTIFIERS.sub("", path.read_text(encoding="utf-8"))
    hits = [ln for ln in text.splitlines() if B_WORD.search(ln)]
    assert hits == [], (path.name, hits[:3])


def test_negative_the_b_word_guard_sees_a_comment_and_a_string():
    assert B_WORD.search("# a quick " + "b" + "ounce off the low")
    assert B_WORD.search('x = "' + "B" + 'ounces"')
    assert not B_WORD.search("[reverses] back hard")


# ── what the tab actually serves ──────────────────────────────────────────────────────────────────────────────
def _walk(o):
    if isinstance(o, dict):
        if "text" in o and isinstance(o.get("text"), str):
            yield o
        for k, v in o.items():
            if k != "text":
                yield from _walk(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _walk(v)
    elif isinstance(o, str):
        yield o


def _served_payloads():
    from chart_maps.gajjala import constants as GC
    from chart_maps.gajjala import playbook as PB
    from chart_maps.gajjala import tab as GT
    from supply_demand import rules_info as RI
    from tests.test_gajjala_tab import NOW, ordering_store, _post_store, _pm_store
    out = [PB.playbook(), RI._gajjala_section()]
    for k, _e, _l in GC.SUBS:
        st = _post_store() if k == "postmarket" else _pm_store() if k == "premarket" else ordering_store()
        out.append(GT.build(k, now=NOW, store=st))
    return out


def test_served_strings_name_no_other_method_except_his_own_verbatim_line():
    items = [x for p in _served_payloads() for x in _walk(p)]
    hrefs = [x for x in items if isinstance(x, str) and x.startswith("/sepa/")]
    items = [x for x in items if not (isinstance(x, str) and x.startswith("/sepa/"))]
    assert hrefs                                                    # the tile link is the house ticker page
    assert served_violations(items) == []
    hits = {(x["ts"], x["text"], x["verbatim"]) for x in items if isinstance(x, dict) and NAMES.search(x["text"])}
    assert len(hits) == 1 and next(iter(hits))[0] == "9:45"          # ONE item (the 📓 sub serves the same dict)


def test_served_strings_carry_no_b_word():
    import json
    for p in _served_payloads():
        assert not B_WORD.search(json.dumps(p, ensure_ascii=False))


def test_negative_the_same_name_in_a_non_verbatim_item_fails():
    text = "I consider myself as a intraday swing trader … a mix of Minervini style swing trading in intraday"
    assert served_violations([{"text": text, "verbatim": True}]) == []
    assert served_violations([{"text": text, "verbatim": False}]) != []
    assert served_violations(["A Minervini-style read of this chart"]) != []


def test_negative_a_verbatim_item_whose_text_is_not_in_the_notes_fails():
    assert served_violations([{"text": "a mix of Minervini style trend template gates", "verbatim": True}]) != []
    joined = "I consider myself as a intraday swing trader … a mix of Minervini style swing trading in intraday … I'm not compromising"
    assert served_violations([{"text": joined, "verbatim": True}]) != []     # spans two lines → not byte-equal
