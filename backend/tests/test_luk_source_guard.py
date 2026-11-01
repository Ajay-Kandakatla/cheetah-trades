"""Source guards for backend/chart_maps/luk/ (BUILD SPEC luk-tab WP-A1 — the gajjala source-guard pattern).

1. Not another method: no module of the package imports sepa.(scanner|bonde|vcp|trend|stage|qoq|sales|research);
   `sepa.prices`, `sepa.symbols` and `sepa.adr` are the house data layer and stay allowed.
2. "Reversal", never the b-word: not in any file of the package — code, strings, docstrings, comments — and not in
   verified_rules.json (his caption that carries it is served as a tagged paraphrase).
3. No "edge" in a served string: the string literals of every module (docstrings excluded — never served), the
   registry JSON, and everything the WP-A1 modules actually serve.
The guards walk the WHOLE package, so the modules of the later work packages are covered the day they land.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[1] / "chart_maps" / "luk"
FILES = sorted(PKG.glob("*.py"))
JSON_FILES = sorted(PKG.glob("*.json"))
BANNED_IMPORTS = re.compile(r"^sepa\.(scanner|bonde|vcp|trend|stage|qoq|sales|research)\b")
BANNED_SEPA_SUBMODULES = {"scanner", "bonde", "vcp", "trend", "stage", "qoq", "sales", "research"}
B_WORD = re.compile("b" + "ounc", re.I)
EDGE = re.compile(r"\bedge\b", re.I)
HOUSE_IDENTIFIERS = re.compile(r"bounce_room|quick_bounce|zone_bounce|sepa_bounce|BounceRoom")   # internal names keep it


def _docstring_ids(tree) -> set:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None) or []
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                out.add(id(body[0].value))
    return out


def string_literals(src: str) -> list:
    tree = ast.parse(src)
    docs = _docstring_ids(tree)
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]


def import_hits(src: str) -> list:
    hits = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            hits += [a.name for a in node.names if BANNED_IMPORTS.match(a.name) or re.search(r"bonde", a.name, re.I)]
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if BANNED_IMPORTS.match(mod) or re.search(r"bonde", mod, re.I):
                hits.append(mod)
            if mod == "sepa":
                hits += ["sepa." + a.name for a in node.names if a.name in BANNED_SEPA_SUBMODULES]
    return hits


def b_word_lines(text: str) -> list:
    return [ln for ln in HOUSE_IDENTIFIERS.sub("", text).splitlines() if B_WORD.search(ln)]


def test_the_package_has_the_files_this_guard_must_cover():
    names = {f.name for f in FILES}
    assert {"__init__.py", "constants.py", "variant.py", "playbook.py", "tiers.py", "market_state.py"} <= names
    assert [f.name for f in JSON_FILES] == ["verified_rules.json"]


@pytest.mark.parametrize("path", FILES, ids=[f.name for f in FILES])
def test_no_other_methods_engine_is_imported(path):
    assert import_hits(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("src", ["from sepa import scanner", "import sepa.bonde", "from sepa.trend import x",
                                 "from sepa.qoq import y", "from sepa import research, prices"])
def test_negative_the_import_guard_catches_a_banned_import(src):
    assert import_hits(src)


def test_the_house_data_layer_is_allowed():
    assert import_hits("from sepa import prices, symbols\nfrom sepa.adr import adr_pct\nimport sepa.prices") == []


@pytest.mark.parametrize("path", FILES + JSON_FILES, ids=[f.name for f in FILES + JSON_FILES])
def test_no_b_word_anywhere_in_the_package(path):
    assert b_word_lines(path.read_text(encoding="utf-8")) == [], path.name


def test_negative_the_b_word_guard_sees_a_comment_a_string_and_json():
    assert b_word_lines("# a quick " + "b" + "ounce off the low")
    assert b_word_lines('x = "' + "B" + 'ounces"')
    assert b_word_lines('{"rule": "' + "b" + 'ouncing into the declining 21"}')
    assert not b_word_lines("reversing into the declining 21\nbounce_room = 1")


@pytest.mark.parametrize("path", FILES, ids=[f.name for f in FILES])
def test_no_edge_in_a_string_literal(path):
    hits = [s for s in string_literals(path.read_text(encoding="utf-8")) if EDGE.search(s)]
    assert hits == [], (path.name, hits[:3])


@pytest.mark.parametrize("path", JSON_FILES, ids=[f.name for f in JSON_FILES])
def test_no_edge_in_the_registry(path):
    assert not EDGE.search(path.read_text(encoding="utf-8"))


def test_negative_the_edge_guard_sees_a_literal_but_not_a_docstring_or_a_word_inside_a_word():
    src = '"""the edge of a docstring is not served"""\nX = "a real edge here"\nY = "knowledge, hedge, ledger"\n'
    assert [s for s in string_literals(src) if EDGE.search(s)] == ["a real edge here"]


def _served_strings() -> list:
    from chart_maps.luk import market_state as MS
    from chart_maps.luk import playbook as PB
    from chart_maps.luk import tiers as T
    out = [PB.TITLE] + PB.rules_lines()
    for s in PB.playbook()["sections"]:
        out.append(s["title"])
        out += [v for it in s["items"] for v in (it["text"], it["cite_text"])]
    blk = MS.block({"QQQ": {"ema9": 1.0, "ema21": 2.0, "close": 1.0}, "IWM": {"ema9": 2.0, "ema21": 1.0}})
    out += [blk["title"], blk["note"]] + [r["text"] for r in blk["rows"]] + [r["dist_text"] or "" for r in blk["rows"]]
    out += list(T.TIER_TEXT.values()) + [T.small_cap_text(1)]
    return out


def test_nothing_served_by_these_modules_carries_the_b_word_or_edge():
    served = _served_strings()
    assert len(served) > 100
    assert [s for s in served if B_WORD.search(s) or EDGE.search(s)] == []
