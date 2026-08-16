"""Theme priority — which build-out themes lead the Chart Maps board.

Ajay 2026-08-16: "I do want us to give priority to Space technology, Quantum,
Semis" and then "Fiber optics, and Robotic components or any potential
bottlenecks for AI that are going to be the next big thing.. after Semis and
HBM."

Two things are pinned here because both are silent when they break:

  * The ORDER. Before this change the board only knew "theme or not", so adding
    a roster changed nothing about what led. If someone reorders THEME_PRIORITY
    the board quietly reprioritises Ajay's watchlist.
  * The CAP. Ordering alone lets the top theme take every slot on a strong day,
    which turns a study board into a single-sector feed.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sepa import universe as U  # noqa: E402
from chart_maps import board  # noqa: E402


# --------------------------------------------------------------------------
# Rosters
# --------------------------------------------------------------------------
def test_the_tickers_ajay_asked_about_are_tagged():
    """ASTS and RKLB were in the universe all along but carried no theme, so
    they sorted behind every tagged name and never reached the board."""
    assert U.theme_for("ASTS") == "space"
    assert U.theme_for("RKLB") == "space"


def test_the_new_bottleneck_themes_exist():
    for theme in ("space", "optical", "robotics", "ai_semis"):
        assert theme in U.THEME_UNIVERSE, f"{theme} roster is missing"
        assert U.THEME_UNIVERSE[theme], f"{theme} roster is empty"


def test_fiber_optics_and_robotic_components_are_actually_populated():
    """The two Ajay named specifically. Spot-check the representative names so
    a roster cannot be gutted to one ticker and still pass."""
    optical = set(U.THEME_UNIVERSE["optical"])
    assert {"COHR", "LITE", "CIEN", "GLW"} <= optical
    robotics = set(U.THEME_UNIVERSE["robotics"])
    assert {"CGNX", "MBLY", "OUST"} <= robotics


def test_hbm_and_storage_sit_inside_ai_semis():
    """"after Semis and HBM" — HBM is not its own tier, it is the semis tier."""
    semis = set(U.THEME_UNIVERSE["ai_semis"])
    assert {"MU", "SNDK", "WDC", "STX"} <= semis


def test_a_ticker_belongs_to_exactly_one_theme():
    """THEME_BY_TICKER is last-wins, so a duplicate silently retags a name and
    changes its priority. NVDA is the standing temptation — physical-AI platform
    and semi both — and it must stay in ai_semis."""
    seen: dict[str, str] = {}
    for theme, names in U.THEME_UNIVERSE.items():
        for t in names:
            assert t not in seen, f"{t} is in both {seen[t]} and {theme}"
            seen[t] = theme
    assert U.theme_for("NVDA") == "ai_semis"


def test_the_disjoint_check_actually_fires():
    """Negative: the guard must raise, not just exist."""
    import pytest
    original = U.THEME_UNIVERSE
    try:
        U.THEME_UNIVERSE = {"a": ["XYZ"], "b": ["XYZ"]}
        with pytest.raises(ValueError, match="unique"):
            U._assert_themes_disjoint()
    finally:
        U.THEME_UNIVERSE = original


def test_every_theme_ticker_reaches_the_scan():
    """A tagged name that is not in the broad universe is never scanned, so the
    tag does nothing. This is the failure mode that hid ARQQ and SYM before."""
    themed = {t for names in U.THEME_UNIVERSE.values() for t in names}
    reachable = set(U.fetch_themes())
    assert themed <= reachable, f"unreachable: {sorted(themed - reachable)}"


def test_tickers_look_like_tickers():
    """Negative: no lowercase, no whitespace, no dotted class shares (our price
    feed does not resolve MOG.A-style symbols)."""
    for theme, names in U.THEME_UNIVERSE.items():
        for t in names:
            assert t == t.strip().upper(), f"{theme}: {t!r} is not normalised"
            assert t.isalpha(), f"{theme}: {t!r} is not a plain ticker"
            assert 1 <= len(t) <= 5, f"{theme}: {t!r} has an implausible length"


# --------------------------------------------------------------------------
# Priority
# --------------------------------------------------------------------------
def test_priority_is_the_order_ajay_asked_for():
    """Space, then Quantum, then Semis — his words, in his order. Then the
    bottlenecks he expects next: optical, robotics, infra, nuclear."""
    order = sorted(U.THEME_PRIORITY, key=lambda k: U.THEME_PRIORITY[k])
    # ai_power / nuclear / energy sit together right behind Ajay's stated
    # three: AI is megawatt-constrained, so the compute hosts, the reactors
    # and the barrels are one story (2026-08-16: "energy is super important
    # now with AI").
    assert order == ["space", "quantum", "ai_semis", "ai_power", "nuclear",
                     "energy", "optical", "robotics", "ai_infra"]


def test_every_roster_has_a_priority():
    assert set(U.THEME_UNIVERSE) == set(U.THEME_PRIORITY)


def test_theme_rank_orders_themes_and_puts_untagged_last():
    assert U.theme_rank("space") < U.theme_rank("quantum") < U.theme_rank("ai_semis")
    assert U.theme_rank("ai_semis") < U.theme_rank("ai_power") < U.theme_rank("energy")
    assert U.theme_rank("energy") < U.theme_rank("optical") < U.theme_rank("robotics")
    assert U.theme_rank("robotics") < U.theme_rank("ai_infra")
    # Untagged sorts behind every theme — that is the whole point of the board.
    for theme in U.THEME_PRIORITY:
        assert U.theme_rank(theme) < U.theme_rank(None)


def test_theme_rank_negatives():
    """An unknown theme still beats an untagged name, so adding a roster and
    forgetting the priority entry degrades gracefully instead of hiding it."""
    assert U.theme_rank("not_a_theme") < U.theme_rank(None)
    assert U.theme_rank(None) == U.theme_rank("") == U.UNTAGGED_RANK


# --------------------------------------------------------------------------
# Sorting on the board
# --------------------------------------------------------------------------
def _tile(sym, theme, score):
    return {"symbol": sym, "theme": theme, "_score": score}


def test_board_sorts_space_ahead_of_a_higher_scoring_untagged_name():
    tiles = [
        _tile("RANDO", None, 99.0),
        _tile("IONQ", "quantum", 10.0),
        _tile("ASTS", "space", 1.0),
    ]
    tiles.sort(key=lambda t: board._sort_key(t, True))
    assert [t["symbol"] for t in tiles] == ["ASTS", "IONQ", "RANDO"]


def test_score_still_breaks_ties_inside_a_theme():
    tiles = [_tile("A", "space", 1.0), _tile("B", "space", 5.0)]
    tiles.sort(key=lambda t: board._sort_key(t, True))
    assert [t["symbol"] for t in tiles] == ["B", "A"]


def test_themes_first_false_ignores_priority_entirely():
    """The winners tab passes themes_first=False — a historical win is a
    historical win regardless of sector."""
    tiles = [_tile("RANDO", None, 99.0), _tile("ASTS", "space", 1.0)]
    tiles.sort(key=lambda t: board._sort_key(t, False))
    assert [t["symbol"] for t in tiles] == ["RANDO", "ASTS"]


# --------------------------------------------------------------------------
# The per-theme cap
# --------------------------------------------------------------------------
def test_one_theme_cannot_take_the_whole_board():
    """With enough competition to fill the board, the top theme is held to the
    cap and the lower-priority themes get their slots."""
    tiles = [_tile(f"S{i}", "space", 100 - i) for i in range(10)]
    tiles += [_tile(f"O{i}", "optical", 50 - i) for i in range(10)]
    out = board._spread(tiles, limit=8)[:8]
    assert sum(1 for t in out if t["theme"] == "space") == board.MAX_PER_THEME
    assert sum(1 for t in out if t["theme"] == "optical") == 2


def test_the_cap_yields_rather_than_ship_a_half_empty_board():
    """The honest limit of the cap, pinned so it is a decision and not a
    surprise: when nothing else is setting up, the capped theme's overflow
    fills the remaining slots. On a narrow day the board shows what is actually
    working rather than blank space."""
    tiles = [_tile(f"S{i}", "space", 100 - i) for i in range(10)]
    tiles += [_tile("COHR", "optical", 1.0)]
    out = board._spread(tiles, limit=8)[:8]
    assert "COHR" in [t["symbol"] for t in out], "the cap failed to reserve a slot"
    # 6 capped space + COHR, then the 8th slot comes back from space overflow.
    assert sum(1 for t in out if t["theme"] == "space") == board.MAX_PER_THEME + 1
    assert out[6]["symbol"] == "COHR" and out[7]["symbol"] == "S6"


def test_the_cap_keeps_the_best_of_the_capped_theme():
    """Capping must drop the worst, not an arbitrary slice."""
    tiles = [_tile(f"S{i}", "space", 100 - i) for i in range(10)]
    out = board._spread(tiles, limit=24)
    kept = [t["symbol"] for t in out[:board.MAX_PER_THEME]]
    assert kept == ["S0", "S1", "S2", "S3", "S4", "S5"]


def test_overflow_is_kept_so_a_quiet_day_still_fills_the_board():
    """Negative: if space is the ONLY thing setting up, do not ship 6 tiles and
    18 blanks — spill the rest back in rank order."""
    tiles = [_tile(f"S{i}", "space", 100 - i) for i in range(10)]
    out = board._spread(tiles, limit=24)
    assert len(out) == 10
    assert [t["symbol"] for t in out] == [f"S{i}" for i in range(10)]


def test_untagged_names_are_never_capped():
    tiles = [_tile(f"U{i}", None, 10 - i) for i in range(9)]
    assert len(board._spread(tiles, limit=24)) == 9


def test_spread_on_an_empty_board_is_empty():
    assert board._spread([], limit=24) == []
