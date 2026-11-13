"""`board.fallen_pool` — the 📉 page's selection, extracted 2026-11-12 (📅 Long
Term spec §3.8, WP-DATA) so the weekly read takes the EXACT pool the 📉 page
serves. `fallen_tiles` must stay byte-identical.

Ajay 2026-11-12: "keep updating it from all the other tabs info.." — one
engine per concept: the Long Term 📉 category reads this pool, never a copy.

Pins: (1) `fallen_pool` == the pre-extract loop on every sort and tier;
(2) the full `fallen_tiles` payload is identical with `fallen_pool` swapped for
the verbatim pre-extract code (the 📉 board fixture of test_fallen_tab.py);
(3) NEGATIVES: memo rows never mutated; an unknown turnover fails a real floor
and is counted; nothing under the depth is kept.
"""
from __future__ import annotations

import copy
import json

import pytest

from chart_maps import board as BOARD
from chart_maps import fallen_tab as FAL
from tests.test_fallen_tab import (_board_seed, _clean, _entry_of, _r,  # noqa: F401
                                   fal_board)


def _pre_extract(entry, *, sort, depth, min_tier):
    """The loop exactly as it stood inside `fallen_tiles` before 2026-11-12."""
    rows, counts = FAL.rank(entry, sort=sort, depth=depth)
    floor_on = BOARD.LIQ_TIERS.get(min_tier, BOARD.LIQ_TIERS[BOARD.DEFAULT_MIN_TIER]) > 0
    kept, no_turnover, dropped_thin = [], 0, 0
    for r in rows:
        m = dict(r.get("metrics") or {})
        if m.get("avg_turnover") is None:
            m["avg_turnover"] = r.get("adv50")
        if not BOARD.passes_liquidity(m.get("avg_turnover"), min_tier):
            dropped_thin += 1
            no_turnover += int(floor_on and m.get("avg_turnover") is None)
            continue
        kept.append((r, m))
    return kept, counts, dropped_thin, no_turnover


def _rows():
    out = []
    specs = [("AAA", 2, 45.0, 5e9, 10.0, {"avg_turnover": 60e6}, None),
             ("BBB", 4, 41.0, None, 80.0, {}, 30e6),             # no scan row -> adv50
             ("CCC", 4, 70.0, 2e8, 900.0, {"avg_turnover": 4e6}, None),
             ("DDD", 0, 55.0, 9e10, None, {}, None),             # unknown turnover
             ("EEE", 4, 70.0, 1e9, 20.0, {"avg_turnover": 25e6}, 1.0),
             ("FFF", 3, 39.9, 1e9, 50.0, {"avg_turnover": 90e6}, None)]   # under the depth
    for sym, n, pct, cap, g, met, adv in specs:
        r = _r(sym, n, pct, cap=cap, g=g, added=1e6)
        r["metrics"] = met
        r["adv50"] = adv
        out.append(r)
    return out


@pytest.mark.parametrize("sort", ["default", FAL.SORT_DEPTH, FAL.SORT_SALES, "market_cap",
                                  "market_cap_asc"])
@pytest.mark.parametrize("tier", ["deep", "ok", "thin", "all"])
def test_fallen_pool_equals_the_pre_extract_loop(sort, tier):
    e = _entry_of(_rows())
    got = BOARD.fallen_pool(e, sort=sort, depth=40, min_tier=tier)
    want = _pre_extract(e, sort=sort, depth=40, min_tier=tier)
    assert repr(got) == repr(want)


def test_NEG_unknown_turnover_fails_a_real_floor_and_is_counted():
    kept, counts, thin, no_t = BOARD.fallen_pool(_entry_of(_rows()), sort="default",
                                                 depth=40, min_tier="ok")
    syms = [r["symbol"] for r, _m in kept]
    assert "DDD" not in syms and no_t == 1
    assert "CCC" not in syms                              # $4M under the ok floor
    assert "BBB" in syms                                  # adv50 stands in for a scan row
    assert thin == 2 and counts["at_depth"] == 5


def test_NEG_nothing_under_the_depth_is_kept():
    kept, counts, _t, _n = BOARD.fallen_pool(_entry_of(_rows()), sort="default",
                                             depth=40, min_tier="all")
    assert "FFF" not in [r["symbol"] for r, _m in kept] and counts["at_depth"] == 5


def test_NEG_memo_rows_are_never_mutated():
    e = _entry_of(_rows())
    before = copy.deepcopy(e)
    kept, *_ = BOARD.fallen_pool(e, sort="default", depth=40, min_tier="ok")
    for _r_, m in kept:
        m["avg_turnover"] = -1.0                          # the copy is the caller's
    assert e == before


def test_fallen_tiles_byte_identical_with_the_pre_extract_code(_clean, fal_board, monkeypatch):
    _board_seed(fal_board)
    new = BOARD.fallen_tiles(24, 130, "full", sort="default")
    FAL._memo.clear()
    _board_seed(fal_board)
    monkeypatch.setattr(BOARD, "fallen_pool", _pre_extract)
    old = BOARD.fallen_tiles(24, 130, "full", sort="default")
    assert json.dumps(new, sort_keys=True, default=str) == json.dumps(old, sort_keys=True,
                                                                     default=str)
    assert len(new["tiles"]) == 3


def test_fallen_tiles_reads_the_pool_through_fallen_pool(_clean, fal_board, monkeypatch):
    _board_seed(fal_board)
    seen = []
    real = BOARD.fallen_pool

    def spy(entry, **kw):
        seen.append(kw)
        return real(entry, **kw)
    monkeypatch.setattr(BOARD, "fallen_pool", spy)
    BOARD.fallen_tiles(24, 130, "full", sort="default", min_tier="ok")
    assert seen == [{"sort": "default", "depth": FAL.parse_depth(None), "min_tier": "ok"}]


def test_source_pin_fallen_tiles_has_no_second_selection():
    import inspect
    body = inspect.getsource(BOARD.fallen_tiles)
    assert body.count("fallen_pool(") == 1
    assert "passes_liquidity(" not in body and "LIQ_TIERS" not in body.split("tier_label")[0]
