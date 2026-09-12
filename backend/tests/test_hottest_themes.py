"""Every curated roster reaches the 🔥 Hottest table (2026-09-12).

Ajay, looking at the table: *"Where is Robitics and crypto here?"* — then, the
standing rule: *"when we talk sectors add them in to this please"*.

Robotics was never missing. The members table has carried a `theme` grain the
whole time (`tracker.MEMBER_GRAINS`) and the Hot-sectors strip has ranked those
rosters as THEME IN / THEME OUT chips for days. This board simply read `sector`
and `industry` and never asked for the third grain, so twelve rosters he named
himself — robotics, nuclear, quantum, rare_earth, optical, space, the AI
complex — were invisible on the one surface built to answer "what is hot".

THE TEST THAT MATTERS is the last one: a roster added to THEME_UNIVERSE must
appear here without anyone remembering to wire it. That is the rule he just
made standing.
"""
from __future__ import annotations

import inspect

from rotation import hottest as H
from rotation import tracker as T


def _payload(themes=None, sectors=None):
    """A minimal members payload: two symbols, one theme, one sector."""
    by_symbol = {
        "SERV": {"industry": "Specialty Industrial Machinery", "rel_1d": 1.0,
                 "rel_5d": 2.0, "rel_21d": 3.0, "last_close": 10.0},
        "ISRG": {"industry": "Medical Instruments", "rel_1d": 0.5,
                 "rel_5d": 1.0, "rel_21d": 2.0, "last_close": 500.0},
    }
    return {
        "as_of": "2026-09-12",
        T.MEMBERS_KEY: {
            "by_symbol": by_symbol,
            "benchmark": {"symbol": "RSP"},
            "groups": {
                "sector": sectors if sectors is not None else
                          {"Technology": {"symbols": ["ISRG"], "median_21d": 2.0}},
                "industry": {},
                "theme": themes if themes is not None else
                         {"robotics": {"symbols": ["SERV", "ISRG"], "median_21d": 2.5}},
            },
        },
    }


def build(payload):
    return H.build(payload)


# ── the grain exists at all ────────────────────────────────────────────────
def test_the_board_carries_THEMES_not_only_sectors_and_industries():
    out = build(_payload())
    assert "themes" in out
    assert [t["group"] for t in out["themes"]] == ["robotics"]


def test_a_theme_row_carries_the_same_columns_a_sector_row_does():
    """Otherwise sorting on Q EPS reorders the tree and the theme rows sit
    blank — the exact defect the sector rows had before 2026-09-12."""
    t = build(_payload())["themes"][0]
    for k in ("rel_1d", "rel_5d", "rel_21d", "n_full", "names", "names_total",
              "sales_yoy", "q_eps_yoy", "net_margin", "eq_score"):
        assert k in t, k


def test_a_theme_opens_into_its_MEMBER_NAMES():
    t = build(_payload())["themes"][0]
    assert {r["symbol"] for r in t["names"]} == {"SERV", "ISRG"}
    assert t["names_total"] == 2


def test_a_theme_has_NO_industry_layer_and_that_is_deliberate():
    """A curated roster cuts ACROSS the provider's industries — robotics spans
    Technology, Industrials and Consumer Cyclical. Splitting it back into them
    would undo the only thing the roster is for."""
    assert build(_payload())["themes"][0]["industries"] == []


def test_a_THIN_roster_is_kept_and_FLAGGED_never_dropped():
    """He asked for rare_earth (n=4) and nuclear by name. A four-name median is
    worth seeing as long as the row says how few names made it."""
    out = build(_payload(themes={"rare_earth": {"symbols": ["SERV"], "median_21d": 1.0}}))
    t = out["themes"][0]
    assert t["thin"] is True and t["n_full"] == 1


# ── the sectors are untouched ──────────────────────────────────────────────
def test_NEGATIVE_themes_ride_ALONGSIDE_and_never_replace_the_sectors():
    """They disagree, and not by a little: on 2026-09-09 the curated `ai_semis`
    roster read rel_21d +0.28 while the provider's `Semiconductors` cohort read
    −1.95 — opposite signs on the same question. "How are semis doing" is a
    question about all semis, so the objective label answers it."""
    out = build(_payload())
    assert [s["group"] for s in out["sectors"]] == ["Technology"]
    assert out["sectors"][0]["industries"], "sectors keep their industry layer"


def test_NEGATIVE_a_payload_with_no_theme_grain_still_builds():
    """An older stored rotation document has no theme groups. The board must
    render its sectors, not fail."""
    out = build(_payload(themes={}))
    assert out["themes"] == []
    assert out["sectors"]


# ── THE STANDING RULE ──────────────────────────────────────────────────────
def test_EVERY_curated_roster_can_reach_this_board():
    """Ajay 2026-09-12: "when we talk sectors add them in to this please".

    The board reads whatever grain the members table hands it, so a roster
    added to THEME_UNIVERSE arrives here with no extra wiring. This pins that
    wiring: `_build` must read the theme grain by the SAME constant the tracker
    writes it under, so a rename cannot quietly make rosters invisible again —
    which is precisely what happened between 2026-09-09 and today."""
    src = inspect.getsource(H._build)
    assert 'groups.get("theme")' in src
    assert "theme" in T.MEMBER_GRAINS


def test_the_crypto_roster_exists_and_the_MINERS_deliberately_do_not_move():
    """Added on the same ask. The big miners — IREN, MARA, RIOT, CIFR, WULF,
    HUT, BTDR, CORZ, APLD, GLXY — stay in `ai_power`, because themes are a
    strict partition AND because that is the actual trade: they are
    power-constrained datacenter operators converting contracted megawatts into
    AI/HPC hosting. Moving them would disturb a roster he already watches and
    tell him the wrong story about what drives them."""
    from sepa import universe as U
    assert "crypto" in U.THEME_UNIVERSE
    for coin_side in ("COIN", "HOOD", "MSTR", "CLSK"):
        assert U.THEME_BY_TICKER.get(coin_side) == "crypto"
    for miner in ("IREN", "MARA", "RIOT", "CIFR", "WULF", "HUT",
                  "BTDR", "CORZ", "APLD", "GLXY"):
        assert U.THEME_BY_TICKER.get(miner) == "ai_power", miner


def test_NEGATIVE_the_coins_themselves_are_never_in_the_roster():
    """BNB, ETH and XRP are not scannable US equities."""
    from sepa import universe as U
    for token in ("BNB", "ETH", "XRP", "BTC", "SOL", "DOGE"):
        assert token not in U.THEME_UNIVERSE["crypto"]
