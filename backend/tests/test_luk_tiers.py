"""chart_maps/luk/tiers.py — his Lead / Mediocre / Lag watchlists (substack, his words) + the small-cap chip
(BUILD SPEC luk-tab §3.5, WP-A1). Lead and Lag are STRICT; equal EMAs → Mediocre (MINE, HIS CALL #17). NEGATIVES."""
from __future__ import annotations

import ast
import pathlib

import pytest

from chart_maps.luk import constants as LC
from chart_maps.luk import tiers as T


@pytest.mark.parametrize("e9,e21,e50,want", [
    (12, 11, 10, "lead"),
    (10, 11, 12, "lag"),
    (12, 11, 13, "mediocre"),            # 9 > 21 < 50
    (10, 11, 9, "mediocre"),             # 9 < 21 > 50
    (11, 11, 10, "mediocre"),            # equal 9 / 21 — never lead
    (12, 11, 11, "mediocre"),            # equal 21 / 50 — never lead
    (10, 11, 11, "mediocre"),            # equal 21 / 50 — never lag
    (10, 10, 11, "mediocre"),            # equal 9 / 21 — never lag
    (5, 5, 5, "mediocre"),
    ("12", "11", "10", "lead"),
])
def test_tier_of(e9, e21, e50, want):
    assert T.tier_of(e9, e21, e50) == want


@pytest.mark.parametrize("args", [(None, 1, 2), (1, None, 2), (1, 2, None), (float("nan"), 1, 2), ("x", 1, 2)])
def test_negative_a_missing_ema_is_no_tier(args):
    assert T.tier_of(*args) is None


def test_tier_texts_are_his_words():
    assert T.TIER_TEXT == {"lead": "Lead — 9 EMA > 21 EMA > 50 EMA", "lag": "Lag — 9 EMA < 21 EMA < 50 EMA",
                           "mediocre": "Mediocre — in between"}
    assert [T.tier_text(t) for t in T.TIERS] == [T.TIER_TEXT[t] for t in T.TIERS]
    assert T.tier_text(None) is None and T.tier_text("unknown") is None


def test_small_cap_chip_boundary():
    assert T.small_cap_text(LC.LUK_SMALL_CAP_USD - 1) == "small cap (<$5B) — his second list"
    assert T.small_cap_text(LC.LUK_SMALL_CAP_USD) is None          # strict "<$5B"
    assert T.small_cap_text(LC.LUK_SMALL_CAP_USD * 2) is None


@pytest.mark.parametrize("cap", [None, 0, -1, "x", float("nan")])
def test_negative_an_unknown_cap_is_not_small(cap):
    assert T.small_cap_text(cap) is None


def test_the_chip_follows_the_constant(monkeypatch):
    monkeypatch.setattr(LC, "LUK_SMALL_CAP_USD", 2_000_000_000)
    assert T.small_cap_text(1_500_000_000) == "small cap (<$2B) — his second list"
    assert T.small_cap_text(3_000_000_000) is None


def test_no_number_is_typed_in_the_module():
    tree = ast.parse(pathlib.Path(T.__file__).read_text(encoding="utf-8"))
    nums = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
            and not isinstance(n.value, bool)}
    assert nums == {0, 1_000_000_000}                               # zero and the billion unit only
