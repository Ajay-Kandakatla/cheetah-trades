"""🔥 Hottest Sectors board (Ajay 2026-09-11).

The cases worth pinning are the ones his own example exposed: a strong name in
a COLD sector, an industry too small for a ranked row, and the two different
populations (sampled group heat vs full-membership names) never being blended.
"""
import math

from rotation import hottest as H
from rotation import tracker as T


def _payload():
    """Shaped like the persisted rotation payload, with ANDE's real 2026-09-10
    numbers: strong name, cold sector, 6-name industry with no ranked row."""
    by_symbol = {
        "ANDE": {"sector": "Consumer Defensive", "industry": "Food Distribution",
                 "name": "The Andersons, Inc.", "last_close": 71.88,
                 "ret_1d": 0.79, "ret_5d": 1.35, "ret_21d": 12.14, "ret_63d": -3.18},
        "SYY": {"sector": "Consumer Defensive", "industry": "Food Distribution",
                "name": "Sysco", "last_close": 80.0,
                "ret_1d": 0.71, "ret_5d": 0.48, "ret_21d": -2.5, "ret_63d": 1.0},
        "PM": {"sector": "Consumer Defensive", "industry": "Tobacco",
               "name": "Philip Morris", "last_close": 150.0,
               "ret_1d": 2.0, "ret_5d": 1.0, "ret_21d": 3.0, "ret_63d": 4.0},
    }
    groups = {
        "sector": {"Consumer Defensive": {"symbols": list(by_symbol), "median_21d": 0.5}},
        "industry": {"Tobacco": {"symbols": ["PM"], "median_21d": 3.0}},
        "cohort": {}, "theme": {},
    }
    return {
        "as_of": "2026-09-10", "benchmark": "RSP",
        "sectors": [{"group": "Consumer Defensive", "n": 40, "dropped": 0,
                     "rel_1d": 0.56, "rel_5d": -0.94, "rel_21d": 0.92,
                     "pct_positive_1d": 55.0}],
        "industries": [{"group": "Tobacco", "n": 3, "rel_1d": 1.0,
                        "rel_5d": 1.49, "rel_21d": 5.45, "pct_positive_1d": 66.0}],
        "sampled": {"Consumer Defensive": {"of": 76, "used": 40}},
        T.MEMBERS_KEY: {"by_symbol": by_symbol, "groups": groups,
                        "benchmark": {"ret_1d": -0.68, "ret_5d": -2.48, "ret_21d": -3.41}},
    }


def test_a_cold_sector_is_still_listed():
    """The board lists EVERY sector. His example is a strong name in a sector
    ranked 8th of 11 — a hot-sectors-only list could never reach it."""
    b = H.build(_payload())
    names = [s["group"] for s in b["sectors"]]
    assert "Consumer Defensive" in names
    cd = b["sectors"][0]
    assert cd["rel_5d"] == -0.94          # cold, and shown anyway


def test_group_heat_is_the_shipped_number_not_a_recomputed_one():
    """Reused verbatim so this board can never disagree with the Hot-sectors
    strip. The members here would median to something else entirely."""
    cd = H.build(_payload())["sectors"][0]
    assert (cd["rel_1d"], cd["rel_5d"], cd["rel_21d"]) == (0.56, -0.94, 0.92)
    assert cd["basis"] == "rotation grid sample"


def test_both_populations_are_reported_side_by_side():
    """Heat on 40, names from all 76 — and the payload says which is which."""
    cd = H.build(_payload())["sectors"][0]
    assert cd["n_measured"] == 40            # the sampled grid row
    assert cd["sampled_of"] == 76 and cd["sampled_used"] == 40
    assert cd["n_full"] == 3                 # every member in this fixture
    assert cd["names_total"] == 3


def test_a_thin_industry_still_shows_and_is_flagged():
    """Food Distribution has no ranked row. Hiding it is how ANDE disappears."""
    cd = H.build(_payload())["sectors"][0]
    inds = {i["group"]: i for i in cd["industries"]}
    assert "Food Distribution" in inds
    fd = inds["Food Distribution"]
    assert fd["ranked"] is False and fd["thin"] is True
    assert fd["basis"] == "full membership"
    # a shipped row keeps its shipped numbers and says so
    assert inds["Tobacco"]["ranked"] is True
    assert inds["Tobacco"]["basis"] == "rotation grid sample"
    assert inds["Tobacco"]["rel_5d"] == 1.49


def test_names_rank_by_return_not_by_traction():
    """traction measures ACCELERATION. On the live board it ranks ANDE 23rd of
    76 while the 5-day ranks it 3rd — sorting on it would bury the name that
    prompted this board."""
    cd = H.build(_payload(), sort="rel_21d")["sectors"][0]
    assert cd["names"][0]["symbol"] == "ANDE"
    assert "traction" in cd["names"][0]          # still carried, just not the sort

    # and the DEFAULT must be a return leg too — a board that quietly opens on
    # traction is the same bug arriving through the front door
    assert H.DEFAULT_SORT in H.LEGS, H.DEFAULT_SORT
    assert H.DEFAULT_SORT != "traction"
    assert H.build(_payload())["sorted_by"] in H.LEGS


def test_sorting_reorders_sectors_and_names():
    for leg, top in (("rel_1d", "PM"), ("rel_5d", "ANDE"), ("rel_21d", "ANDE")):
        cd = H.build(_payload(), sort=leg)["sectors"][0]
        assert cd["names"][0]["symbol"] == top, leg


def test_NEGATIVE_an_unknown_sort_falls_back_and_never_raises():
    b = H.build(_payload(), sort="../etc/passwd")
    assert b["sorted_by"] == H.DEFAULT_SORT
    b2 = H.build(_payload(), sort="")
    assert b2["sorted_by"] == H.DEFAULT_SORT


def test_NEGATIVE_a_missing_fundamental_is_None_never_zero():
    """A blank quarter is not flat growth, and it must not win a sort."""
    cd = H.build(_payload())["sectors"][0]          # build() injects no decisions
    r = cd["names"][0]
    for k in ("sales_yoy", "q_eps_yoy", "net_margin", "eq_score", "next_earnings"):
        assert r[k] is None, k


def test_NEGATIVE_nan_never_reaches_a_row_or_a_sort():
    """NaN passes every <= comparison, so one NaN silently reorders the board."""
    p = _payload()
    p[T.MEMBERS_KEY]["by_symbol"]["ANDE"]["ret_5d"] = float("nan")
    p["sectors"][0]["rel_5d"] = float("nan")
    b = H.build(p, sort="rel_5d")
    cd = b["sectors"][0]
    assert cd["rel_5d"] is None
    for r in cd["names"]:
        for v in r.values():
            assert not (isinstance(v, float) and math.isnan(v))
    # the NaN name sorts LAST rather than winning the board
    assert cd["names"][-1]["symbol"] == "ANDE"


def test_NEGATIVE_an_empty_payload_answers_an_empty_board_not_an_exception():
    for bad in ({}, {T.MEMBERS_KEY: {}}, {T.MEMBERS_KEY: {"by_symbol": {}, "groups": {}}}):
        b = H.build(bad)
        assert b["sectors"] == []
        assert b["sorted_by"] == H.DEFAULT_SORT


def test_the_board_declares_what_it_is():
    b = H.build(_payload())
    assert "discovery list" in b["note"].lower()
    assert b["legs"] == list(H.LEGS)
    assert "rel_21d" in b["legs"], "the 21-day leg is his 2026-09-11 choice for THIS board"


def test_the_hot_sectors_strip_window_is_untouched():
    """He stripped the 21-day OFF the strip on 2026-09-10. This board adding it
    back must not reach over and change that."""
    from rotation import heat as RH
    assert RH.HEAT_KEY == "rel_5d"
