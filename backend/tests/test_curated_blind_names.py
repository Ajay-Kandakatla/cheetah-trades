"""Names curated into `full` because NO index layer carried them.

Ajay 2026-09-12 pointed his own watchlist at the app — "Can you check if these
companies are in our scans?" — and 4 of 12 came back blind. This file pins the
whole CLASS, not just those four, because the same hole has now been found
three times (NTSK 2026-09-10, AXTI 2026-09-11, these 2026-09-12).

THE RULE THIS FILE EXISTS FOR: a name reaches the alert path only if it is in
`full`. `broad` is scanned once a day by the 16:30 fast-scan and feeds NOTHING
else — not the zone store, not a board, not a push, not a paper entry. A name
in `broad` only looks covered.

AND THERE IS A SECOND GATE, discovered while fixing these four: zone_store's
`big_cap_universe()` keeps only names with a KNOWN market cap >= MIN_CAP_USD.
Curating a name is necessary and NOT sufficient — LWLG and WYFI were in `full`
and still had no zone doc because their shares-cache row did not exist.
"""
from __future__ import annotations

import ast
import io
import os

import pytest

from sepa import universe as U
from sepa import symbols as SY
from supply_demand import zone_store as Z

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Every name curated because no index carried it, with the date it was found.
CURATED_BLIND = {
    "NTSK": "2026-09-10",
    "AXTI": "2026-09-11",
    "UMAC": "2026-09-12",
    "CLYM": "2026-09-12",
    "LWLG": "2026-09-12",
    "WYFI": "2026-09-12",
}


@pytest.mark.parametrize("sym", sorted(CURATED_BLIND))
def test_a_curated_blind_name_is_in_FULL_not_merely_broad(sym):
    """`full` is the only universe that reaches an alert."""
    full = {s.upper() for s in U.load_universe("full")}
    assert sym in full, (
        "%s dropped out of `full` — it would be fast-scanned at 16:30 and "
        "invisible to the zone store, every board and every push" % sym)


@pytest.mark.parametrize("sym", sorted(CURATED_BLIND))
def test_it_is_in_the_curated_literal_so_an_index_refresh_cannot_drop_it(sym):
    """Source guard. These names are in NO index, so if they ever depend on a
    fetched list instead of the literal, the next refresh deletes them."""
    src = io.open(os.path.join(HERE, "sepa", "universe.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    node = next(n for n in tree.body
                if isinstance(n, ast.AnnAssign)
                and getattr(n.target, "id", None) == "UNIVERSE")
    literals = {e.value for e in ast.walk(node.value)
                if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    assert sym in literals, "%s must be a literal in UNIVERSE, not index-derived" % sym


def test_the_curated_list_has_no_duplicates():
    dupes = sorted({s for s in U.UNIVERSE if U.UNIVERSE.count(s) > 1})
    assert not dupes, "duplicated in UNIVERSE: %s" % dupes


@pytest.mark.parametrize("sym", sorted(CURATED_BLIND))
def test_NEGATIVE_a_curated_name_is_never_a_dead_ticker(sym):
    """Curating a delisted symbol is worse than not curating it: it burns a
    scan slot forever and prints a stale row that looks live."""
    dead = getattr(SY, "DELISTED", None) or set()
    dead = set(dead.keys()) if isinstance(dead, dict) else set(dead)
    assert sym not in dead
    renames = getattr(SY, "RENAMES", {}) or {}
    assert sym not in renames, (
        "%s is a RENAME source — curate the destination ticker instead" % sym)


# ------------------------------------------------------ the SECOND gate
def test_being_in_full_is_NOT_enough_an_unknown_cap_still_gets_no_zone_doc():
    """The half of the fix that is easy to miss.

    LWLG and WYFI were curated into `full` and STILL had no zone document,
    because `big_cap_universe` drops every name whose cap is unknown. Without
    a zone doc there are no bands, and with no bands there is no demand alert,
    no bounce, no supply break and no paper entry."""
    out = Z.big_cap_universe(universe=["KNOWN", "UNKNOWN", "TOOSMALL"],
                             caps={"KNOWN": 2e9, "UNKNOWN": None, "TOOSMALL": 1e8})
    assert out == ["KNOWN"]


def test_the_cap_gate_reads_the_SAME_floor_the_rest_of_the_app_does():
    from trading import safety_floor as SF
    assert Z.MIN_CAP_USD == SF.MIN_CAP_USD == 700_000_000.0


def test_NEGATIVE_a_nan_cap_is_dropped_not_treated_as_infinite():
    """A NaN passes every >= comparison. If one reached this filter it would
    admit the name AND then poison every median computed downstream."""
    out = Z.big_cap_universe(universe=["NANCAP", "REAL"],
                             caps={"NANCAP": float("nan"), "REAL": 2e9})
    assert out == ["REAL"]


def test_zone_store_still_reads_full_and_not_a_wider_mode():
    """Source guard on the sentence the whole file depends on. If this ever
    becomes load_universe('broad'), the `full`-vs-`broad` distinction these
    tests assert is meaningless and they would all keep passing."""
    src = io.open(os.path.join(HERE, "supply_demand", "zone_store.py"),
                  encoding="utf-8").read()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "big_cap_universe")
    modes = [a.value for c in ast.walk(fn) if isinstance(c, ast.Call)
             and getattr(c.func, "attr", getattr(c.func, "id", None)) == "load_universe"
             for a in c.args if isinstance(a, ast.Constant)]
    assert modes == ["full"], "zone_store must build from `full`, got %s" % modes
