"""Chart Maps strategy roster (trading/strategy_tags.py, 2026-09-27).

Ajay: "Top 10 most-used first". Pins the roster itself: which tab is which
lane, the FROZEN ten that start ON, the not-a-lane tabs, the legacy tag map,
the usage rank, and that every prior points at a file that exists.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.strategy_tags as ST  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def test_the_frozen_top_ten_start_on():
    assert ST.DEFAULT_ON == frozenset({"zones", "deep_demand", "catalysts", "amd", "bonde",
                                       "hot_pullback", "growth", "quick_bounce", "patterns",
                                       "breaking"})
    # hot_sectors is a sector view: not counted, OFF (§7 #5)
    assert "hot_sectors" not in ST.DEFAULT_ON and ST.roster_entry("hot_sectors")["klass"] == "lane"


def test_not_a_lane_tabs_and_vcp_off_with_minervini():
    assert set(ST.NOT_A_LANE) == {"support", "holdings", "ema_frames", "news", "winners",
                                  "topping", "vcp"}
    assert "Minervini" in ST.NOT_A_LANE["vcp"] and "long-only" in ST.NOT_A_LANE["topping"]
    for tab in ST.NOT_A_LANE:
        assert tab not in ST.lane_sids() and ST.is_roster(tab) is False
        assert ST.is_not_a_lane(tab) is True


def test_existing_lanes_keep_their_journal_tags():
    assert ST.TAG_TO_SID == {"demand_zone": "zones", "breakout": "breaking",
                             "quick_bounce": "quick_bounce", "catalyst": "catalysts",
                             "hot_pullback": "hot_pullback", "zero_dte": "signals"}
    assert ST.EXISTING_LANE_SIDS == frozenset({"zones", "breaking", "quick_bounce",
                                               "catalysts", "hot_pullback", "signals"})
    for tag, sid in ST.TAG_TO_SID.items():
        assert ST.norm(tag) == sid and ST.is_roster(tag)
    assert ST.roster_entry("signals")["tabs"] == ("signals", "zero_dte")


def test_non_roster_tags_are_themselves():
    for tag in ("minervini", "options_zone", "manual"):
        assert ST.sid_for_tag(tag) is None and ST.norm(tag) == tag and not ST.is_roster(tag)
    assert ST.sid_for_tag(None) is None and ST.norm(None) == "manual"
    assert ST.sid_for_tag("nonsense") is None


def test_every_generic_sid_is_a_program_tag_and_equals_its_tab():
    for sid in ST.generic_sids():
        assert sid in ST.PROGRAM_TAGS and ST.norm(sid) == sid
        assert ST.roster_entry(sid)["adapter"] in ("PLAN", "LIST")
    assert "quick_bounce" in ST.PROGRAM_TAGS and "hot_pullback" in ST.PROGRAM_TAGS
    assert {s for s in ST.generic_sids() if ST.roster_entry(s)["adapter"] == "PLAN"} == \
        {"deep_demand", "ict", "session"}


def test_list_lanes_say_they_are_not_the_tabs_own_setup():
    """critic 10: a LIST lane buys a READY demand reversal on the tab's list."""
    for r in ST.ROSTER:
        if r.get("adapter") == "LIST":
            assert ST.LIST_NOTE in r["note"], r["sid"]
    assert "cup-with-handle" in ST.roster_entry("patterns")["note"]
    for r in ST.ROSTER:
        assert "bounce" not in r["note"].lower(), r["sid"]


def test_usage_rank_matches_the_2026_09_27_order():
    order = ST.usage_rank(*ST.frozen_counts())
    assert order[:11] == ["zones", "deep_demand", "hot_sectors", "catalysts", "amd", "bonde",
                          "hot_pullback", "growth", "quick_bounce", "patterns", "breaking"]
    assert set(order) == set(ST.lane_sids())


def test_usage_rank_edges():
    assert ST.usage_rank({}, {}) == list(ST.lane_sids())             # nothing counted: roster order
    r = ST.usage_rank({"signals": 5, "zero_dte": 10, "amd": 14}, {"amd": 1, "signals": 2})
    assert r[:2] == ["signals", "amd"]                                # 15 (two tabs) beats 14
    r = ST.usage_rank({"amd": 5, "ict": 5}, {"amd": 1, "ict": 9})
    assert r[:2] == ["ict", "amd"]                                    # tie -> newest first
    r = ST.usage_rank({"amd": 5, "ict": 5}, {})
    assert r[:2] == ["amd", "ict"]                                    # then sid ascending
    assert ST.usage_rank({"amd": "junk"}, None)[0] == ST.lane_sids()[0]


def test_every_prior_source_exists_or_is_unmeasured():
    for sid, p in ST.PRIORS.items():
        assert p["status"] in ("unmeasured", "null", "inverted", "no_signal", "inconclusive",
                               "negative"), sid
        if p["source"] is not None:
            assert os.path.exists(os.path.join(REPO, p["source"])), (sid, p["source"])
        else:
            assert p["status"] == "unmeasured", sid
    assert ST.PRIORS["amd"]["status"] == "inverted" and ST.PRIORS["bonde"]["status"] == "inverted"
    assert ST.PRIORS["catalysts"]["status"] == "unmeasured"
    assert set(ST.PRIORS) == set(ST.lane_sids())


def test_a_missing_prior_path_downgrades_to_unmeasured(monkeypatch):
    monkeypatch.setitem(ST._PRIORS_RAW, "ict", ("no_signal", "x", "backend/nope/missing.py"))
    assert ST._prior("ict") == {"status": "unmeasured", "note": "x", "source": None}


def test_the_module_is_a_stdlib_leaf():
    src = open(ST.__file__, encoding="utf-8").read()
    imports = [l for l in src.splitlines() if l.startswith(("import ", "from "))]
    assert all(l.split()[1].split(".")[0] in ("__future__", "os", "typing") for l in imports), imports
