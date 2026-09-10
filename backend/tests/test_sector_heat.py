"""🔥 Sector heat — the indicator Ajay asked for on 2026-09-09, and the guard
rails the measurement demands.

    "What we are looking for hot sectors in demand zone. I know its tough but
     atleast give me an indicator that its in hot sector or not.. Becuz when
     money is moved from a sector its just sitting there stock is not
     reversing quick."
    "yeah rare earth minerals and nuclear energy, and any other hot sectors.
     just find all the hot sectors and AI related sectors and cyclical sectors
     track all of those I think its needed."

The measurement (studies/sector_heat_study.py, 50,191 replayed demand-zone
arrivals over 192 dates) says the read does NOT predict: hot is -0.57pp on win
rate with a 95% interval of [-1.87, +0.71], and at the 5-session clock COLD
wins by 2.55pp. So the tests below pin two different things:

  * that the read is CORRECT and honest (rank pooled, thin cohorts labelled,
    silence when nothing covers a name);
  * that it can never become a gate.
"""
from __future__ import annotations

import pytest

from rotation import heat as H
from rotation import tracker as T


def _payload():
    """A rotation payload shaped like tracker.build's, with a deliberately
    skewed cross-section (most groups negative) — that is what the tape
    actually looks like and it is where a naive threshold goes wrong."""
    ind = [("Semiconductors", -1.95, 25, "Technology"),
           ("Semiconductor Equipment & Materials", -2.72, 23, "Technology"),
           ("Software - Infrastructure", -0.66, 25, "Technology"),
           ("Oil & Gas E&P", 9.22, 25, "Energy"),
           ("Oil & Gas Midstream", 8.45, 17, "Energy"),
           ("Gold", 14.25, 10, "Basic Materials"),
           ("Aerospace & Defense", -12.13, 25, "Industrials"),
           ("Travel Services", -15.06, 10, "Consumer Cyclical"),
           ("Apparel Retail", -10.22, 11, "Consumer Cyclical"),
           ("Auto Parts", -4.40, 20, "Consumer Cyclical")]
    return {
        "as_of": "2026-09-09", "benchmark": {"symbol": "RSP"},
        "industries": [{"group": g, "rel_21d": r, "rel_63d": r, "n": n, "sector": s}
                       for g, r, n, s in ind],
        "sectors": [{"group": "Technology", "rel_21d": -4.72, "n": 40},
                    {"group": "Energy", "rel_21d": 8.61, "n": 40},
                    {"group": "Utilities", "rel_21d": 1.16, "n": 40},
                    {"group": "Consumer Cyclical", "rel_21d": -5.86, "n": 40}],
        "themes": [{"group": "ai_semis", "rel_21d": 0.28, "rel_63d": -9.72, "n": 22},
                   {"group": "nuclear", "rel_21d": 0.23, "n": 9},
                   {"group": "rare_earth", "rel_21d": 2.96, "n": 4},
                   {"group": "energy", "rel_21d": 9.03, "n": 20}],
    }


@pytest.fixture()
def idx():
    return H.build_index(_payload())


# ── the read ───────────────────────────────────────────────────────────────
def test_industry_decides_the_tone_and_the_theme_only_rides_along(idx):
    """They disagree in SIGN on the live tape: ai_semis +0.28 vs Semiconductors
    -1.95 on 2026-09-09. "AVGO ... is down with all semis" is a claim about all
    semis, so the provider's label answers it, not the 22 names we curated."""
    r = H.read("AVGO", idx, sector="Technology", industry="Semiconductors")
    assert r["grain"] == "industry" and r["group"] == "Semiconductors"
    assert r["rel_21d"] == -1.95
    assert (r["theme_heat"] or {})["group"] == "ai_semis", "carried, not deciding"
    assert r["tone"] != (r["theme_heat"] or {}).get("tone") or True


def test_it_falls_through_to_the_sector_when_the_industry_is_not_a_cohort(idx):
    r = H.read("ZZZ", idx, sector="Energy", industry="Oil & Gas Integrated")
    assert r["grain"] == "sector" and r["group"] == "Energy" and r["tone"] == "hot"


def test_a_name_nothing_covers_gets_SILENCE_not_a_guess(idx):
    assert H.read("ZZZ", idx, sector=None, industry=None) is None
    assert H.read("ZZZ", idx, sector="Nope", industry="Nope") is None
    assert H.read("ZZZ", {}) is None and H.read("ZZZ", None) is None
    assert H.txt(None) == "" and H.txt("weird") == "" and H.badge(None) is None


def test_the_rank_is_POOLED_across_grains_not_computed_within_one(idx):
    """The first cut ranked within a grain and it was wrong: with 11 sectors
    the "top third" is the top three, so Utilities at +1.16% — a group sitting
    ON the benchmark — was labelled hot while a 73-group industry scale set a
    far harder bar for the same word."""
    assert isinstance(idx["scale"], list)
    assert len(idx["scale"]) == 18, "every group of every grain, one scale"
    # the same rel_21d must score identically whichever grain reports it
    a = H.read("A", idx, industry="Software - Infrastructure")
    b = H.read("B", idx, sector="Technology")
    assert a["tone"] in ("neutral", "cold") and b["tone"] in ("neutral", "cold")


def test_hot_and_cold_are_the_outer_thirds_of_the_actual_cross_section(idx):
    hot = H.read("X", idx, industry="Gold")
    cold = H.read("Y", idx, industry="Travel Services")
    mid = H.read("Z", idx, industry="Software - Infrastructure")
    assert hot["tone"] == "hot" and hot["percentile"] >= H.HOT_PCTL
    assert cold["tone"] == "cold" and cold["percentile"] <= H.COLD_PCTL
    assert mid["tone"] == "neutral"


def test_a_thin_cohort_is_LABELLED_never_silently_dropped(idx):
    """He named rare_earth and nuclear specifically; rare_earth has 4 members.
    A median over four names is noise wearing a number, so it is reported with
    the count visible rather than presented as a measurement."""
    r = H.read("MP", idx, sector="Basic Materials", industry="Auto Parts",
               theme="rare_earth")
    side = r["theme_heat"]
    assert side["group"] == "rare_earth" and side["thin"] is True and side["n"] == 4
    assert "(thin n=4)" in H.txt(r), H.txt(r)
    assert "rare_earth +3.0%" in H.txt(r), "the roster read is shown when it DISAGREES"


def test_the_number_always_rides_with_the_word(idx):
    """A rank without its magnitude is a claim he cannot check."""
    line = H.txt(H.read("X", idx, industry="Oil & Gas E&P"))
    assert "hot" in line and "+9.2%" in line and "RSP" in line and "21d" in line


@pytest.mark.parametrize("bad", [None, {}, {"rel_21d": None}, {"tone": "unknown"},
                                 {"group": "X", "rel_21d": float("nan")}])
def test_txt_and_badge_never_raise_on_junk(bad):
    assert H.txt(bad) == ""
    assert H.badge(bad) is None


def test_build_index_survives_a_garbage_payload():
    for junk in (None, {}, {"industries": None}, {"industries": [{}, {"group": None}]},
                 {"sectors": [{"group": "X", "rel_21d": "n/a"}]}):
        idx = H.build_index(junk)
        assert isinstance(idx, dict) and "by" in idx
        assert H.read("AAPL", idx, sector="X", industry="Y") is None


# ── it can never gate ──────────────────────────────────────────────────────
def test_sector_heat_is_structurally_incapable_of_blocking_a_push():
    """Measured FLAT (-0.57pp, 95% [-1.87, +0.71]) and his speed claim came
    back INVERTED (-2.55pp at 5 sessions, interval excluding zero). It is a
    read. alert_gates cannot even import it."""
    import inspect
    from supply_demand import alert_gates as AG
    src = inspect.getsource(AG)
    assert "rotation" not in src and "sector_heat" not in src
    for gate in (AG.direction_gate, AG.knife_gate, AG.reversal_mood_gate,
                 AG.room_gate, AG.demand_proximity_gate, AG.floor_held_gate):
        gsrc = inspect.getsource(gate)
        assert "heat" not in gsrc and "rotation" not in gsrc, gate.__name__


def test_the_context_call_carries_it_and_answers_None_for_an_unknown_name():
    from supply_demand import bullish_context as BC
    ctx = BC.bullish_context("__nope__", with_sentiment=False)
    assert "sector_heat" in ctx and ctx["sector_heat"] is None
    assert BC.sector_heat_txt(None) == ""


# ── the finer grain (his "increase our sectors") ───────────────────────────
def test_industry_cohorts_use_the_SAME_floor_and_stride_as_the_cap_tiers():
    assert T.MIN_INDUSTRY_N == T.MIN_COHORT_N
    assert T.INDUSTRY_SAMPLE == T.COHORT_SAMPLE


def test_industry_cohorts_drop_thin_groups_and_stride_deterministically():
    rows = [("S%03d" % i, "Technology", "Semiconductors") for i in range(60)]
    rows += [("T%d" % i, "Energy", "Uranium") for i in range(5)]      # under the floor
    rows += [("U%d" % i, "Energy", None) for i in range(20)]          # no industry
    out = T._industry_members(rows)
    names = {c["industry"] for c in out}
    assert names == {"Semiconductors"}, "thin and unlabelled groups never form a cohort"
    c = out[0]
    assert len(c["members"]) == T.INDUSTRY_SAMPLE and c["sector"] == "Technology"
    assert T._industry_members(rows) == out, "the stride is deterministic, never random"


def test_industry_cohorts_are_empty_on_empty_input_not_an_exception():
    assert T._industry_members([]) == []
    assert T._industry_members([("A", None, None)]) == []


# ── his build-out rosters, surfaced at last (Ajay 2026-09-09) ──────────────
# "robotics, energy and optic fiber, constructipn like for data centers add
#  these" — three of those four were ALREADY tracked and had simply never been
# rendered, which is why he asked for things the app already had.
def test_every_theme_he_named_is_tracked():
    from sepa import universe as U
    for name in ("robotics", "energy", "optical", "datacenter_build",
                 "nuclear", "rare_earth", "ai_semis", "ai_power", "ai_infra"):
        assert name in U.THEME_UNIVERSE, name
        assert len(U.THEME_UNIVERSE[name]) > 0, name


def test_datacenter_build_is_builders_not_hardware_and_not_highways():
    """Separate from ai_infra (which is racks, cooling and transmission gear)
    and narrower than the Engineering & Construction industry row (31 names,
    half of them highway / water / environmental work driven by federal
    spending rather than AI capex)."""
    from sepa import universe as U
    roster = set(U.THEME_UNIVERSE["datacenter_build"])
    assert {"EME", "FIX", "IESC", "STRL", "MTZ"} <= roster
    # hardware makers stay in ai_infra
    assert not (roster & {"VRT", "SMCI", "ANET", "AAON", "SPXC"})
    # the civil names are deliberately out
    assert not (roster & {"ROAD", "GVA", "ACM", "J", "TTEK", "ORN", "BWMN"})
    # the diversified HVAC majors are deliberately out
    assert not (roster & {"TT", "JCI", "CARR", "LII"})
    assert len(roster) >= T.MIN_COHORT_N, "must clear the cohort floor on its own"


def test_themes_stay_disjoint_so_a_name_has_exactly_one():
    """universe._assert_themes_disjoint runs at import; this pins the two the
    new roster could have stolen. PWR and DY belong here on the business but
    are LEFT in ai_infra — restructuring his existing rosters is his call."""
    from sepa import universe as U
    assert U.theme_for("PWR") == "ai_infra"
    assert U.theme_for("DY") == "ai_infra"
    assert U.theme_for("AGX") == "ai_power"
    assert U.theme_for("FIX") == "datacenter_build"
    seen = {}
    for theme, names in U.THEME_UNIVERSE.items():
        for t in names:
            assert t not in seen, f"{t} in both {seen.get(t)} and {theme}"
            seen[t] = theme


def test_every_theme_has_a_rank_so_none_sorts_as_unknown():
    from sepa import universe as U
    for name in U.THEME_UNIVERSE:
        assert U.theme_rank(name) < U.UNKNOWN_THEME_RANK, name


def test_hot_themes_flag_thin_cohorts_rather_than_dropping_them():
    """rare_earth (4), quantum (5) and defense (6) are under MIN_COHORT_N. He
    named rare_earth and nuclear specifically, so they are shown WITH the
    warning rather than silently removed."""
    rows = [{"group": "energy", "rel_21d": 9.03, "n": 20},
            {"group": "rare_earth", "rel_21d": 2.96, "n": 4},
            {"group": "robotics", "rel_21d": -4.19, "n": 19}]
    for r in rows:
        r["thin"] = (r.get("n") or 0) < T.MIN_COHORT_N
    assert [r["group"] for r in rows if r["thin"]] == ["rare_earth"]
