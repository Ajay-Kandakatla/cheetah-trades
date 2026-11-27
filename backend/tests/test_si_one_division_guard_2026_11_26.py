"""🩳 ONE DIVISION — `read.pct_of` is the only '% of float' / '% of shares outstanding' division (2026-11-26, spec
floatguard rev 2 §2.1, §3.1, §4.6 [C3], work package `fixtures`).

Ajay 2026-11-26 ~21:20 ET, verbatim: "Also the Float share count issue and SI discrepancy happened too many times need
to do something about it"

Eleven divisions on ten lines in four files used to compute short / float or short / shares (spec §1.1); every one now
calls `read.pct_of`. This guard fails on a TWELFTH. It reads NO variable name for (a) and (b) — critique C3: a name
regex missed `s / base` and could not see `count / shares`:
  (a) EXACT INVENTORY — `{(file, enclosing function): n}` of every `ast.BinOp` with `Div` in the short-interest file set
      equals a frozen dict. An honest new division turns it red until it is added here WITH its reason — that is the
      point.
  (b) PERCENT SHAPE — a `Div` under a multiplication by the constant 100 / 100.0 (walking the BinOp parents) is allowed
      only in `read.pct_of` and the four change / drop % (`basis_math.change_across_split`, `client.short_interest_for`
      :389, `client._build_doc` :769, `ssr._drop_pct`).
  (c) REPO TRIPWIRE for every other backend file: both sides un-parsed with `float(…)` / `int(…)` stripped; a short
      count over a float / share count is a hit. Two frozen scripts are allowed by name. Expected hits: ZERO.
  (d) CALL COUNTS of `pct_of` / `SR.pct_of`: read.py 2 (both in si_block), basis_math.py 5, client.py 3, high_si.py 1,
      source_check.py >= 1.
NEGATIVES: planted source strings run through the SAME functions (a twelfth division, a percent shape anywhere, the
tripwire's hit and non-hit shapes).

2026-11-27 guard-hole fix: a "division" is now any of three forms, read by ONE helper (`_div_parts`) that all three
walkers share — `a / b` (ast.BinOp Div), `a /= b` (ast.AugAssign Div) and a call to `operator.truediv` /
`operator.itruediv` (as `operator.x(…)` or a bare `x(…)` after `from operator import x`). Before it,
`p = si; p /= fl; return round(p * 100.0, 2)` and `operator.truediv(si, fl) * 100.0` counted ZERO divisions. The SI file
set holds none of the two new forms, so the frozen 21 is unchanged.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
SI_DIR = BACKEND / "short_interest"
GG_FILES = ("high_si.py", "si_ssr_names.py", "si_track.py", "si_follow.py")
FILE_SET = tuple(sorted(p.relative_to(BACKEND).as_posix() for p in SI_DIR.glob("*.py"))) + \
    tuple("chart_maps/gajjala/" + f for f in GG_FILES) + ("sepa/bonde_picks.py",)

# (a) the frozen inventory after the build — 21 divisions. Each line says what it divides.
INVENTORY = {
    ("short_interest/read.py", "pct_of"): 1,                    # THE one division: count / shares x 100
    ("short_interest/read.py", "_human_shares"): 1,             # a share count / 1e3 or 1e6 for the words
    ("short_interest/read.py", "dtc_computed"): 1,              # shares short / average daily volume (days to cover)
    ("short_interest/basis_math.py", "_factor"): 1,             # split_from / split_to
    ("short_interest/basis_math.py", "rebase"): 1,              # a count across splits
    ("short_interest/basis_math.py", "change_across_split"): 1,  # the SI change % (not short / shares)
    ("short_interest/basis_math.py", "verdict"): 3,             # share-count ratios (the "N× more shares" words)
    ("short_interest/borrow.py", "_per_day"): 1,                # a borrow fee per day
    ("short_interest/client.py", "_squeeze_signal"): 1,         # the squeeze score's DTC leg
    ("short_interest/client.py", "short_interest_for"): 1,      # the SI change % :389 (not short / shares)
    ("short_interest/client.py", "_build_doc"): 1,              # the SI change % :769 (not short / shares)
    ("short_interest/reg_sho.py", "_age_min"): 1,               # seconds -> minutes
    ("short_interest/ssr.py", "_drop_pct"): 1,                  # the price drop % (SSR trigger)
    ("short_interest/ssr.py", "trigger_line"): 1,               # the SSR trigger price
    ("short_interest/source_check.py", "rel_of"): 1,            # how far two counts are apart (the ONLY one there)
    ("chart_maps/gajjala/si_track.py", "_rate"): 1,             # a hit rate
    ("chart_maps/gajjala/si_track.py", "session_facts"): 1,     # a session fact ratio
    ("chart_maps/gajjala/si_track.py", "shuffle_share"): 1,     # a placebo share
    ("sepa/bonde_picks.py", "_ipo_leg"): 1,                     # the IPO-age leg
}
assert sum(INVENTORY.values()) == 21
# (b) where a Div may sit under `* 100`
PERCENT_ALLOWED = {("short_interest/read.py", "pct_of"), ("short_interest/basis_math.py", "change_across_split"),
                   ("short_interest/client.py", "short_interest_for"), ("short_interest/client.py", "_build_doc"),
                   ("short_interest/ssr.py", "_drop_pct")}
# (c)
TRIP_LEFT = re.compile(r"\b(si|si_b|si_shares|short_interest|prev_si|shares_short|short_shares)\b", re.I)
TRIP_RIGHT = re.compile(r"float|shares|\bfl\b|\bso\b|\bfd\b|\bfpd\b|\bbase\b|\bden\b|count", re.I)
TRIP_ALLOWED = {"scripts/si_cradle_squeeze_study.py", "scripts/si_share_basis_probe.py"}   # frozen, never served
TRIP_SKIP_DIRS = {"tests", ".venv", "__pycache__", "node_modules"}
# (d)
CALLS = {"short_interest/read.py": 2, "short_interest/basis_math.py": 5, "short_interest/client.py": 3,
         "chart_maps/gajjala/high_si.py": 1}


# ═════════════════════════════════════════════ the walkers (pure: source text in, findings out)
def _parents(tree) -> dict:
    par = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            par[c] = n
    return par


def _enclosing(node, par):
    q = node
    while q in par:
        q = par[q]
        if isinstance(q, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return q.name
    return None


def _is_hundred(n) -> bool:
    return isinstance(n, ast.Constant) and not isinstance(n.value, bool) and n.value in (100, 100.0)


DIV_CALLS = ("truediv", "itruediv")                              # operator.truediv / operator.itruediv


def _div_parts(n):
    """(left, right) when node `n` is a true division in any of its three spellings, else None.

    `a / b` -> (a, b); `a /= b` -> (a, b); `operator.truediv(a, b)` / `truediv(a, b)` / `operator.itruediv(a, b)` ->
    (a, b). A truediv call with other than two positional arguments still counts as a division (left / right None)."""
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div):
        return n.left, n.right
    if isinstance(n, ast.AugAssign) and isinstance(n.op, ast.Div):
        return n.target, n.value
    if isinstance(n, ast.Call):
        f = n.func
        name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
        if name in DIV_CALLS:
            if len(n.args) == 2 and not n.keywords:
                return n.args[0], n.args[1]
            return None, None
    return None


def divisions(src: str) -> dict:
    """{enclosing function: number of divisions (`/`, `/=`, operator.truediv / itruediv)} — no variable name is read."""
    tree = ast.parse(src)
    par, out = _parents(tree), {}
    for n in ast.walk(tree):
        if _div_parts(n) is not None:
            fn = _enclosing(n, par)
            out[fn] = out.get(fn, 0) + 1
    return out


def percent_divisions(src: str) -> list:
    """[(enclosing function, line)] of every Div that sits under a multiplication by the constant 100 / 100.0."""
    tree = ast.parse(src)
    par, out = _parents(tree), []
    for n in ast.walk(tree):
        if _div_parts(n) is None:
            continue
        q = n
        while q in par and isinstance(par[q], (ast.BinOp, ast.UnaryOp)):
            p = par[q]
            if isinstance(p, ast.BinOp) and isinstance(p.op, ast.Mult) and \
                    _is_hundred(p.right if p.left is q else p.left):
                out.append((_enclosing(n, par), n.lineno))
                break
            q = p
    return out


def _strip(n):
    while isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("float", "int") \
            and len(n.args) == 1 and not n.keywords:
        n = n.args[0]
    return n


def trip_hits(src: str) -> list:
    """[(line, left, right)] of every short count over a float / share count, `float(…)` / `int(…)` stripped."""
    out = []
    for n in ast.walk(ast.parse(src)):
        parts = _div_parts(n)
        if parts is not None and parts[0] is not None:
            left, right = ast.unparse(_strip(parts[0])), ast.unparse(_strip(parts[1]))
            if TRIP_LEFT.search(left) and TRIP_RIGHT.search(right):
                out.append((n.lineno, left, right))
    return out


def pct_of_calls(src: str) -> list:
    """[enclosing function] of every call named `pct_of` / `<module>.pct_of`."""
    tree = ast.parse(src)
    par, out = _parents(tree), []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
            if name == "pct_of":
                out.append(_enclosing(n, par))
    return out


def _src(rel: str) -> str:
    return (BACKEND / rel).read_text(encoding="utf-8")


def inventory() -> dict:
    out = {}
    for rel in FILE_SET:
        for fn, k in divisions(_src(rel)).items():
            out[(rel, fn)] = k
    return out


def _func_src(rel: str, name: str) -> str:
    tree = ast.parse(_src(rel))
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return ast.get_source_segment(_src(rel), n)
    raise AssertionError("%s not found in %s" % (name, rel))


# ═════════════════════════════════════════════ (a) the exact inventory
def test_the_file_set_is_the_short_interest_files():
    for rel in FILE_SET:
        assert (BACKEND / rel).exists(), rel
    assert "short_interest/read.py" in FILE_SET and "short_interest/source_check.py" in FILE_SET
    assert len([r for r in FILE_SET if r.startswith("short_interest/")]) == len(list(SI_DIR.glob("*.py")))


def test_a_the_division_inventory_is_exact():
    got = inventory()
    extra = {k: v for k, v in got.items() if INVENTORY.get(k) != v}
    missing = {k: v for k, v in INVENTORY.items() if got.get(k) != v}
    assert not extra and not missing, {"unexpected": extra, "expected": missing}
    assert sum(got.values()) == 21


def test_a_no_division_in_si_block_stale_trigger_card_pct_or_the_audit():
    got = inventory()
    for k in (("short_interest/read.py", "si_block"), ("short_interest/basis_math.py", "stale_trigger"),
              ("chart_maps/gajjala/high_si.py", "card_pct")):
        assert k not in got, k
    assert not [k for k in got if k[0] == "short_interest/source_audit.py"]


def test_a_NEGATIVE_a_twelfth_division_in_a_copy_of_si_block_is_red():
    src = _func_src("short_interest/read.py", "si_block")
    assert "si_block" not in divisions(src)
    planted = src.rstrip() + "\n    x = a / b\n"
    assert divisions(planted).get("si_block") == 1


@pytest.mark.parametrize("planted", [
    "def f(si, fl):\n    p = si\n    p /= fl\n    return round(p * 100.0, 2)\n",
    "import operator\ndef f(si, fl):\n    return operator.truediv(si, fl) * 100.0\n",
    "from operator import truediv\ndef f(si, fl):\n    return truediv(si, fl) * 100.0\n",
    "import operator\ndef f(si, fl):\n    p = si\n    p = operator.itruediv(p, fl)\n    return p\n",
    "from operator import itruediv\ndef f(si, fl):\n    return itruediv(si, fl)\n",
    "import operator as op\ndef f(si, fl):\n    return op.truediv(*(si, fl))\n",
])
def test_a_NEGATIVE_an_augmented_or_operator_division_is_counted(planted):
    assert divisions(planted) == {"f": 1}


def test_a_NEGATIVE_the_augmented_hole_in_a_copy_of_si_block_is_red():
    src = _func_src("short_interest/read.py", "si_block")
    assert divisions(src.rstrip() + "\n    p = si\n    p /= fl\n").get("si_block") == 1
    assert divisions(src.rstrip() + "\n    p = operator.truediv(si, fl) * 100.0\n").get("si_block") == 1


def test_a_NOT_a_division_floor_div_other_aug_ops_and_other_operator_calls():
    for src in ("def f(a, b):\n    return a // b\n",
                "def f(a, b):\n    a //= b\n    a *= b\n    a -= b\n    return a\n",
                "import operator\ndef f(a, b):\n    return operator.floordiv(a, b) + operator.mul(a, b)\n",
                "def f(a, b):\n    return a % b\n"):
        assert divisions(src) == {}, src


def test_a_the_si_file_set_has_no_augmented_or_operator_division():
    for rel in FILE_SET:
        tree = ast.parse(_src(rel))
        odd = [ast.unparse(n) for n in ast.walk(tree) if _div_parts(n) is not None and not isinstance(n, ast.BinOp)]
        assert odd == [], (rel, odd)


# ═════════════════════════════════════════════ (b) the percent shape
def test_b_percent_divisions_sit_only_in_pct_of_and_the_four_change_percents():
    found = []
    for rel in FILE_SET:
        for fn, line in percent_divisions(_src(rel)):
            found.append((rel, fn, line))
    bad = [f for f in found if (f[0], f[1]) not in PERCENT_ALLOWED]
    assert not bad, bad
    assert {(r, f) for r, f, _ in found} == PERCENT_ALLOWED
    assert len(found) == 5


@pytest.mark.parametrize("planted", ["def f(s, base):\n    return round(s / base * 100, 2)\n",
                                     "def g(q, r):\n    p = q / r * 100.0\n    return p\n",
                                     "def h(q, r):\n    return 100 * (q / r)\n",
                                     "def k(q, r):\n    return -(q / r) * 100\n",
                                     "import operator\ndef m(q, r):\n    return operator.truediv(q, r) * 100.0\n",
                                     "from operator import truediv\ndef n(q, r):\n    return 100 * truediv(q, r)\n"])
def test_b_NEGATIVE_a_planted_percent_shape_is_red_wherever_it_sits(planted):
    assert len(percent_divisions(planted)) == 1


def test_b_a_change_percent_inside_short_interest_for_is_allowed():
    planted = "def short_interest_for(si, prev):\n    return (si - prev) / prev * 100\n"
    hits = percent_divisions(planted)
    assert [h[0] for h in hits] == ["short_interest_for"]
    assert ("short_interest/client.py", hits[0][0]) in PERCENT_ALLOWED


def test_b_NEGATIVE_a_plain_division_or_a_bool_constant_is_not_a_percent():
    assert percent_divisions("def f(a, b):\n    return a / b\n") == []
    assert percent_divisions("def f(a, b):\n    return a / b * 10\n") == []
    assert percent_divisions("def f(a, b):\n    return a / b * True\n") == []


# ═════════════════════════════════════════════ (c) the repo tripwire
def _repo_files() -> list:
    out = []
    for p in sorted(BACKEND.rglob("*.py")):
        rel = p.relative_to(BACKEND)
        if set(rel.parts) & TRIP_SKIP_DIRS:
            continue
        out.append(rel.as_posix())
    return out


def test_c_the_repo_tripwire_finds_nothing_outside_the_two_frozen_scripts():
    files = _repo_files()
    assert len(files) > 100 and "short_interest/read.py" in files
    hits = {}
    for rel in files:
        if rel in TRIP_ALLOWED:
            continue
        h = trip_hits(_src(rel))
        if h:
            hits[rel] = h
    assert hits == {}, hits


def test_c_the_two_allowed_scripts_still_exist_and_still_divide():
    for rel in TRIP_ALLOWED:
        assert (BACKEND / rel).exists(), rel
        assert trip_hits(_src(rel)), rel                         # the allowance is not stale


@pytest.mark.parametrize("planted", ["x = float(si) / float(fl) * 100\n",
                                     "p = short_interest / doc['shares_outstanding']\n",
                                     "p = int(si_shares) / float_shares\n",
                                     "p = si / base\n",
                                     "p = shares_short / count\n",
                                     "si /= float_shares\n",
                                     "p = operator.truediv(si, fl) * 100.0\n",
                                     "p = truediv(float(short_interest), shares_outstanding)\n"])
def test_c_NEGATIVE_planted_short_over_float_trips(planted):
    assert len(trip_hits(planted)) == 1


@pytest.mark.parametrize("planted", ["d = si / float(adv)\n",
                                     "d = si_shares / avg_daily_volume\n",
                                     "t = volume / float_shares\n",
                                     "c = (si - prev_si) / prev_si * 100\n",
                                     "p = count / shares * 100.0\n",
                                     "ts /= 1000.0\n",
                                     "d = operator.truediv(si, adv)\n"])
def test_c_NOT_a_hit(planted):
    assert trip_hits(planted) == []


# ═════════════════════════════════════════════ (d) the call counts
def test_d_pct_of_call_counts():
    for rel, n in CALLS.items():
        assert len(pct_of_calls(_src(rel))) == n, rel
    assert set(pct_of_calls(_src("short_interest/read.py"))) == {"si_block"}
    assert len(pct_of_calls(_src("short_interest/source_check.py"))) >= 1


def test_d_pct_of_is_defined_once_above_EXTREME_WORD():
    src = _src("short_interest/read.py")
    tree = ast.parse(src)
    defs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "pct_of"]
    assert len(defs) == 1
    assert src.index("def pct_of(") < src.index('EXTREME_WORD = "EXTREME"')
    assert divisions(ast.get_source_segment(src, defs[0])) == {"pct_of": 1}


def test_d_NEGATIVE_a_dropped_call_is_seen():
    src = _src("short_interest/basis_math.py")
    assert len(pct_of_calls(src.replace("SR.pct_of(si, count[\"shares\"])", "None", 1))) == CALLS[
        "short_interest/basis_math.py"] - 1


def test_pct_of_is_bit_identical_to_the_old_expression():
    from short_interest import read as SR
    for c, s in ((1, 3), (0, 7), (2.5, 9), (7, 11), (1234567, 7654321)):
        assert SR.pct_of(c, s) == round(c / s * 100.0, 2)
        assert SR.pct_of(c, s, digits=None) == c / s * 100.0
    for c, s in ((None, 5), (5, None), (5, 0), (5, -1)):
        assert SR.pct_of(c, s) is None
