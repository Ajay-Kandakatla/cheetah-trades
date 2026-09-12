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


# ---------------------------------------------- sortable columns (2026-09-12)
# Ajay 2026-09-12: "Add sort in this". Every printed column ranks, in both
# directions, and the sort runs on the SERVER because the payload truncates to
# `names_per_group` — a browser-side sort would rank the visible 25 only.

def _fund_payload():
    """Three names in one sector, deliberately DISAGREEING across columns so a
    sort on one cannot accidentally look right because of another."""
    by_symbol = {
        "HIGHSALES": {"sector": "Technology", "industry": "Semiconductors",
                      "name": "big sales", "last_close": 10.0,
                      "ret_1d": 0.1, "ret_5d": 0.1, "ret_21d": 0.1, "ret_63d": 0.0},
        "HIGHEPS": {"sector": "Technology", "industry": "Semiconductors",
                    "name": "big eps", "last_close": 10.0,
                    "ret_1d": 9.0, "ret_5d": 9.0, "ret_21d": 9.0, "ret_63d": 0.0},
        "BLANK": {"sector": "Technology", "industry": "Semiconductors",
                  "name": "no fundamentals", "last_close": 10.0,
                  "ret_1d": 5.0, "ret_5d": 5.0, "ret_21d": 5.0, "ret_63d": 0.0},
    }
    groups = {"sector": {"Technology": {"symbols": list(by_symbol), "median_21d": 0.0}},
              "industry": {"Semiconductors": {"symbols": list(by_symbol),
                                              "median_21d": 0.0}},
              "cohort": {}, "theme": {}}
    return {
        "as_of": "2026-09-12", "benchmark": "RSP",
        "sectors": [{"group": "Technology", "n": 3, "rel_1d": 1.0,
                     "rel_5d": 1.0, "rel_21d": 1.0, "pct_positive_1d": 66.0}],
        "industries": [], "sampled": {},
        T.MEMBERS_KEY: {"by_symbol": by_symbol, "groups": groups,
                        "benchmark": {"ret_1d": 0.0, "ret_5d": 0.0, "ret_21d": 0.0}},
    }


def _decisions():
    def d(sales, eps, npm, score, tier):
        return {"rev_growth_q_pct": sales, "q_eps_growth_pct": eps,
                "sales": {"tier": tier},
                "earnings_quality": {"score": score,
                                     "components": {"npm_latest_pct": npm}}}
    return {"HIGHSALES": d(400.0, 5.0, 2.0, 10.0, "explosive"),
            "HIGHEPS": d(10.0, 900.0, 40.0, 90.0, "steady")}


def _built(sort, direction="desc"):
    return H._build(_fund_payload(), sort=sort, direction=direction,
                    names_per_group=25, decisions=_decisions(),
                    earnings={"HIGHSALES": {"next_date": "2026-11-03", "when": "BMO"},
                              "HIGHEPS": {"next_date": "2026-10-21", "when": None}})


def _names(b):
    return [r["symbol"] for r in b["sectors"][0]["names"]]


def test_every_printed_column_is_sortable():
    """The FE's column table and the backend's SORT_KEYS must agree — a header
    that ranks on a key the server rejects silently falls back to rel_5d."""
    for k in ("rel_1d", "rel_5d", "rel_21d", "sales_yoy", "sales_tier",
              "q_eps_yoy", "net_margin", "eq_score", "next_earnings"):
        assert k in H.SORT_KEYS, k
        assert H._build(_fund_payload(), sort=k, names_per_group=25,
                        decisions={}, earnings={})["sorted_by"] == k


def test_sorting_by_sales_is_not_sorting_by_eps():
    assert _names(_built("sales_yoy"))[0] == "HIGHSALES"
    assert _names(_built("q_eps_yoy"))[0] == "HIGHEPS"
    assert _names(_built("net_margin"))[0] == "HIGHEPS"
    assert _names(_built("eq_score"))[0] == "HIGHEPS"


def test_the_tier_column_sorts_by_RANK_not_alphabetically_or_by_length():
    """Asserts the FULL five-tier order, which is the only assertion that
    isolates the ordinal.

    A two-name version of this test PASSED with the rank replaced by
    `len(tier)` (mutation N3, 2026-09-12): 'explosive' is both the top tier and
    the longest string, so length and rank agreed and the test proved nothing.
    The complete order defeats both impostors —
      by rank:   explosive strong steady weak declining
      alphabetical desc: weak strong steady explosive declining
      by length desc:    explosive/declining (9) strong/steady (6) weak (4)
    """
    tiers = ["explosive", "strong", "steady", "weak", "declining"]
    by_symbol, decisions = {}, {}
    for i, t in enumerate(tiers):
        sym = "T%d" % i
        by_symbol[sym] = {"sector": "Technology", "industry": "Semiconductors",
                          "name": t, "last_close": 10.0, "ret_1d": 0.0,
                          "ret_5d": 0.0, "ret_21d": 0.0, "ret_63d": 0.0}
        decisions[sym] = {"sales": {"tier": t}}
    payload = _fund_payload()
    payload[T.MEMBERS_KEY]["by_symbol"] = by_symbol
    payload[T.MEMBERS_KEY]["groups"]["sector"]["Technology"]["symbols"] = list(by_symbol)
    payload[T.MEMBERS_KEY]["groups"]["industry"]["Semiconductors"]["symbols"] = list(by_symbol)

    got = H._build(payload, sort="sales_tier", direction="desc",
                   names_per_group=25, decisions=decisions, earnings={})
    assert [r["sales_tier"] for r in got["sectors"][0]["names"]] == tiers

    rev = H._build(payload, sort="sales_tier", direction="asc",
                   names_per_group=25, decisions=decisions, earnings={})
    assert [r["sales_tier"] for r in rev["sectors"][0]["names"]] == tiers[::-1]


def test_next_er_ascending_is_who_reports_soonest():
    b = _built("next_earnings", "asc")
    assert _names(b)[0] == "HIGHEPS"          # 2026-10-21 before 2026-11-03


def test_direction_flips_the_order():
    desc = _names(_built("sales_yoy", "desc"))
    asc = _names(_built("sales_yoy", "asc"))
    assert desc[0] == "HIGHSALES" and asc[0] == "HIGHEPS"
    assert _built("sales_yoy", "asc")["sorted_dir"] == "asc"


def test_NEGATIVE_a_blank_sorts_LAST_in_BOTH_directions():
    """The bug this pair exists to prevent: a missing value scored as -inf is
    correct descending and puts every em-dash row FIRST when ascending."""
    for d in ("desc", "asc"):
        for key in ("sales_yoy", "q_eps_yoy", "net_margin", "eq_score",
                    "sales_tier", "next_earnings"):
            assert _names(_built(key, d))[-1] == "BLANK", (key, d)


def test_NEGATIVE_an_unknown_sort_key_falls_back_and_says_so():
    b = H._build(_fund_payload(), sort="; DROP TABLE", names_per_group=25,
                 decisions={}, earnings={})
    assert b["sorted_by"] == H.DEFAULT_SORT


def test_NEGATIVE_an_unknown_direction_falls_back_to_desc():
    assert _built("sales_yoy", "sideways")["sorted_dir"] == "desc"


def test_the_sort_runs_BEFORE_the_names_are_truncated():
    """The reason this is a server sort at all. With room for one name, the one
    returned must be the column's top — not the top of the return leg."""
    b = H._build(_fund_payload(), sort="sales_yoy", direction="desc",
                 names_per_group=1, decisions=_decisions(), earnings={})
    assert _names(b) == ["HIGHSALES"]
    assert b["sectors"][0]["names_total"] == 3     # the cut is display-only


def test_group_rows_carry_a_median_so_a_fundamental_sort_is_visible():
    """Sector and industry rows were BLANK in these columns, so sorting on one
    reordered the tree with nothing on screen to explain it."""
    sec = _built("sales_yoy")["sectors"][0]
    assert sec["sales_yoy"] == 205.0               # median(400, 10) of the two filed
    assert sec["fund_basis"] == "median of full membership"
    ind = sec["industries"][0]
    assert ind["sales_yoy"] == 205.0
    assert ind["q_eps_yoy"] == 452.5


def test_group_medians_never_invent_a_number_from_blanks():
    b = H._build(_fund_payload(), sort="rel_5d", names_per_group=25,
                 decisions={}, earnings={})
    sec = b["sectors"][0]
    for k in H.FUND_SORTS:
        assert sec[k] is None, k                   # em-dash, never a zero
    assert sec["sales_tier"] is None


def test_group_legs_are_still_the_SAMPLED_median_not_recomputed():
    """The legs must keep coming from the shipped rotation grid — that is what
    stops this board and the Hot-sectors strip disagreeing. Only the
    fundamental columns are computed here."""
    sec = _built("sales_yoy")["sectors"][0]
    assert sec["rel_5d"] == 1.0                    # the shipped value, verbatim
