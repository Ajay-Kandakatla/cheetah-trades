"""The cloud_infra THEME + RXT into the curated list — 2026-09-18.

Ajay's ask, verbatim, approved with "yes go":

  1. Add "RXT" (Rackspace, ~$1.88B) to the curated list so it lands in `full`
     and gets zone bands. It is DOCN's closest direct hosting peer, currently
     in `broad` only, with ZERO zone_store docs — so it can never alert.
  2. Create a cloud / SaaS theme so that class can reach the Hot Sectors strip.
     Today NONE of the 16 themes is cloud/SaaS/devtools; `infosec` is the only
     software theme at all. This is NOT a one-liner: themes are a strict
     partition.

THE CUT RULE these tests defend (steps 1-4 mechanical, STEP 5 JUDGMENT):
  1. SOURCE     Mongo `companies` industry == "Software - Infrastructure"
                — the provider's own tag. 106 docs on 2026-09-17.
  2. PARTITION  drop anything already in another theme (20 names).
  3. LIVENESS   last cached bar == the freshest session, VALIDATED BY DATE and
                never by bar count (the SDIG trap). Drops 6.
  4. LIQUIDITY  50-bar avg dollar volume >= 20_000_000, reused BY NAME from
                rotation.tracker.build's own default. 52 names survive.
  5. THESIS     JUDGMENT, mine: "is the PRODUCT ITSELF hosted capacity someone
                else's software or data runs on / is stored in?" 52 -> 18.

NO EDGE IS CLAIMED HERE. Sector/industry heat measured NULL for demand
outcomes on 2026-09-09 (-0.57pp, CI spans zero). The row is context.
"""
import inspect

import pytest

from rotation import tracker as TR
from sepa import symbols as S
from sepa import universe as U
from supply_demand import zone_store as ZS
from trading import safety_floor as SF

KEY = "cloud_infra"
ROSTER = U.THEME_UNIVERSE.get(KEY, [])
FULL = {s.upper() for s in U.load_universe("full")}


# --------------------------------------------------------------------------
# The roster itself
# --------------------------------------------------------------------------
def test_the_theme_exists_and_carries_the_hosting_anchors():
    assert KEY in U.THEME_UNIVERSE
    assert len(ROSTER) == 18
    assert len(set(ROSTER)) == len(ROSTER), "a duplicate inside one roster"
    # DOCN is the anchor of his ask, RXT is item 1, BLZE is the one name of the
    # eight originally handed over that actually passed the thesis test.
    assert {"DOCN", "RXT", "BLZE"} <= set(ROSTER)


def test_the_rosters_stay_disjoint():
    """NEGATIVE. THEME_BY_TICKER is last-wins, so a ticker in two rosters is
    silently retagged and re-sorted on the board. _assert_themes_disjoint()
    raises at import — call it directly, do not merely import the module."""
    seen: dict[str, str] = {}
    for theme, names in U.THEME_UNIVERSE.items():
        for t in names:
            assert t not in seen, "%s in both %s and %s" % (t, seen[t], theme)
            seen[t] = theme
    U._assert_themes_disjoint()
    # 18 since 2026-09-21: critical_minerals (Ajay: "Do we have critical
    # minerals in our list?"). The roster count is the only thing that moved;
    # cloud_infra and its rank are untouched.
    assert len(U.THEME_UNIVERSE) == 18, "16 before cloud_infra, 17 after, 18 with critical_minerals"


def test_NEGATIVE_it_does_not_steal_from_the_five_themes_that_hold_this_industry():
    """Step 2 of the cut rule. Twenty Software-Infrastructure names already sit
    in another roster; they STAY there. Quietly restructuring a roster he
    already watches is not mine to do."""
    holds = {
        "infosec": ["PANW", "CRWD", "ZS", "S", "OKTA", "FTNT", "TENB", "QLYS",
                    "VRNS", "RPD", "SAIL", "NTSK", "RBRK", "GEN", "OSPN"],
        "quantum": ["ARQQ"],
        "crypto": ["BKKT"],
        "ai_power": ["CORZ", "CRWV"],
        "robotics": ["PATH"],
    }
    mine = set(ROSTER)
    for theme, names in holds.items():
        for t in names:
            assert t in U.THEME_UNIVERSE[theme], "%s left %s" % (t, theme)
            assert U.theme_for(t) == theme
            assert t not in mine, "%s was stolen from %s" % (t, theme)
    assert sum(len(v) for v in holds.values()) == 20


def test_NEGATIVE_a_delisted_name_can_never_enter_the_roster():
    """CFLT (last bar 2026-03-16) and SMAR (2025-01-21) were removed in the
    2026-08-25 audit; GREE and SDIG failed crypto validation. A dead ticker
    keeps its history, so nothing about the data stops them coming back — this
    test does."""
    for dead in ("CFLT", "SMAR"):
        assert S.is_delisted(dead), "%s should still be flagged delisted" % dead
        assert dead not in ROSTER
    for dead in ("GREE", "SDIG"):
        assert dead not in ROSTER, "%s failed validation and must never return" % dead


def test_NEGATIVE_the_stale_names_stay_out_validated_by_DATE_not_bar_count():
    """Step 3. INFQ carries 144 bars and XNDU 104 — both clear zone_store's
    MIN_BARS 120-ish intuition, and BAR COUNT WOULD HAVE LET INFQ IN. The last
    bar date is the only liveness test (the SDIG trap)."""
    stale = {
        "INFQ": "2026-09-11 (144 bars — bar count would have passed it)",
        "XNDU": "2026-08-25 (104 bars)",
        "LIDR": "2026-09-15",
        "OLB": "2026-09-16",
        "KPLT": "2026-09-14",
        "SQ": "2026-09-14, and superseded by RENAMES['SQ'] -> XYZ",
    }
    for sym, why in stale.items():
        assert sym not in ROSTER, "%s last printed %s" % (sym, why)
    assert S.resolve("SQ") == "XYZ"


def test_NEGATIVE_the_payments_block_filed_under_this_industry_stays_out():
    """The provider files a fintech index under Software - Infrastructure.
    Admitting them would make this a payments row wearing a cloud label."""
    payments = ["XYZ", "TOST", "FOUR", "CPAY", "WEX", "RELY", "STNE", "PAGS",
                "PAYO", "PGY", "EEFT", "ACIW", "FLYW", "MQ"]
    assert not (set(payments) & set(ROSTER))


def test_NEGATIVE_the_handed_roster_that_was_rejected_is_not_the_roster():
    """The eight names originally put to him were PDYN LIDR ZENA OLB TLS VERI
    GRRR BLZE. ONE of the eight is cloud infrastructure. Reasons, one each:
      PDYN  embodied AI / collaborative autonomy — robotics
      LIDR  lidar sensing, and 2 sessions stale
      ZENA  drones that happen to ship cloud software
      OLB   payments, and stale
      TLS   cyber/cloud SECURITY — it would belong in infosec, not here
      VERI  AI applications
      GRRR  mixed security/network/IoT, and $15.0M/day, under the floor
      BLZE  a cloud storage platform — the one that passed, and it is IN."""
    for sym in ("PDYN", "LIDR", "ZENA", "OLB", "TLS", "VERI", "GRRR"):
        assert sym not in ROSTER
    assert "BLZE" in ROSTER


def test_NEGATIVE_the_step5_judgment_line_is_applied_consistently():
    """Step 5 is JUDGMENT and this test exists to make it visible and cheap to
    reverse. THE DISCRIMINATOR: the customer's bytes LIVE IN Dropbox and Box,
    so the product IS the hosted tier. AVPT manages bytes that live in
    Microsoft's cloud — it sells the management layer, the capacity is
    Microsoft's. TDC is in as a data platform others run workloads on, despite
    being on-prem-heavy, which is a delivery-model objection not a product one.
    A defensible stricter line drops DBX/BOX/TDC -> 15 names, still 7 over
    MIN_COHORT_N. If he takes that line, invert this test."""
    assert {"DBX", "BOX", "TDC"} <= set(ROSTER)
    assert "AVPT" not in ROSTER
    for app in ("FIVN", "APPN", "AI", "RZLV", "ZETA", "RAMP", "YEXT"):
        assert app not in ROSTER, "%s is an application, not hosted capacity" % app


# --------------------------------------------------------------------------
# Reaching the scan
# --------------------------------------------------------------------------
def test_RXT_reaches_the_curated_list_and_the_full_universe():
    """Item 1 of his ask. `broad` is not a scanning universe — the curated list
    is the only thing that makes a ticker scannable."""
    assert "RXT" in U.UNIVERSE
    assert "RXT" in FULL


@pytest.mark.parametrize("ticker", sorted(ROSTER))
def test_every_roster_name_reaches_the_scan(ticker):
    """A theme name outside load_universe('full') charts nowhere — the NTSK
    lesson, mirroring test_theme_semi_materials.py."""
    assert ticker in FULL, "%s is in the theme but outside the scan" % ticker


def test_the_universe_grows_by_exactly_the_two_declared_names():
    """Measured in the api container: full 2689 -> 2691. Pinned as a property
    rather than as a count, because the index counts drift every recon."""
    reachable_without_the_theme = (
        {s.upper() for s in U.fetch_sp1500()}
        | {s.upper() for s in U.fetch_russell3000()}
        | {s.upper() for s in U.UNIVERSE}
    )
    net_new = {t for t in ROSTER if t not in reachable_without_the_theme}
    # RXT is net-new via the curated list edit, not via the theme, so it may
    # fall on either side of that set; BLZE arrives only through the theme.
    assert net_new <= {"RXT", "BLZE"}, (
        "this change declared +2 names and brought %s" % sorted(net_new))
    assert "BLZE" in net_new or "BLZE" in reachable_without_the_theme


def test_the_themes_component_stays_inside_its_size_band():
    """NEGATIVE on two counts: the band must NOT have been widened to make this
    fit, and fetch_themes() must still dedupe. 253 of a 300 ceiling is recorded
    in the doc and in the _EXPECTED_COUNTS comment — deliberately NOT asserted
    as an equality here, because that would redden a cloud_infra test on the
    next roster edit anywhere in the file."""
    lo, hi = U._EXPECTED_COUNTS["themes"]
    assert (lo, hi) == (20, 300), "the size band was moved to make this fit"
    n = len(U.fetch_themes())
    assert lo <= n <= hi
    assert n == len({t for r in U.THEME_UNIVERSE.values() for t in r})


def test_the_row_is_not_thin_and_has_room_to_lose_members():
    """`n` on the board is KEPT members, not roster size (crypto prints n=14 on
    a 17-name roster). The rejected 8-name roster sat exactly on MIN_COHORT_N,
    so one stale member would have flipped it to `thin`."""
    assert TR.MIN_COHORT_N == 8
    assert len(ROSTER) - TR.MIN_COHORT_N == 10


# --------------------------------------------------------------------------
# Source guards and the floors
# --------------------------------------------------------------------------
def test_the_cut_rule_rides_with_the_roster():
    """SOURCE GUARD. A roster whose derivation is not in the file beside it is
    a taste call wearing a number. The word JUDGMENT must survive too, so step
    5 can never quietly be quoted as if it were reproducible."""
    src = inspect.getsource(U)
    for token in ("Software - Infrastructure", "20_000_000", "INFQ", "XNDU",
                  "CFLT", "AVPT", "JUDGMENT"):
        assert token in src, "the cut rule lost %r" % token


def test_the_two_net_new_names_clear_the_unchanged_trading_floors():
    """THE HONEST COST OF "+2 NAMES". RXT and BLZE were scanning nowhere. From
    the moment `full` grows they get zone bands and can appear on the demand,
    hot-pullback, reversal and lid-break boards, and reach
    trading.entries._evaluate -> safety_floor.check.

    NO GATE IS LOOSENED AND NONE IS PROPOSED. The gates are identical; the
    population they run over grows by two. Numbers measured 2026-09-18 in the
    api container, where safety_floor.check returned blocked=[] warnings=[] for
    both."""
    assert SF.MIN_SHARE_PRICE == 2.00
    assert SF.MIN_CAP_USD == 700_000_000.0
    measured = {"RXT": (3.92, 1_876_645_504), "BLZE": (13.79, 874_646_976)}
    for sym, (px, cap) in measured.items():
        assert px >= SF.MIN_SHARE_PRICE, "%s is under the hard price floor" % sym
        assert cap >= SF.MIN_CAP_USD, "%s is under the hard cap floor" % sym
        assert cap >= ZS.MIN_CAP_USD, "%s would get no zone bands" % sym
    # BLZE sits at 1.25x the cap floor: a 20% drawdown stops its bands being
    # built. Not a bug — noted so a later session does not hunt for one.
    assert measured["BLZE"][1] / ZS.MIN_CAP_USD < 1.3


def test_no_gate_moved():
    """NEGATIVE, and the one thing a universe edit must never do. A DATA change
    touches no gate, no threshold and no default."""
    assert ZS.MIN_CAP_USD == 700_000_000.0
    assert ZS.MIN_BARS == 120
    assert TR.MIN_COHORT_N == 8
    sig = inspect.signature(TR.build).parameters
    assert sig["min_dollar_vol"].default == 20_000_000.0
    assert sig["min_price"].default == 10.0
    assert SF.MIN_SHARE_PRICE == 2.00
    assert SF.MIN_CAP_USD == 700_000_000.0
    assert SF.MIN_DOLLAR_VOL == 20_000_000.0


def test_the_theme_ranks_behind_the_buildout_that_sells_it():
    """The rank is MINE, not his — same as semi_materials and
    datacenter_build. Relative order below it is unchanged."""
    P = U.THEME_PRIORITY
    assert set(P) == set(U.THEME_UNIVERSE), "a roster with no rank sorts wrong"
    assert P[KEY] == P["datacenter_build"] + 1
    assert P["ai_infra"] < P["datacenter_build"] < P[KEY]
    for below in ("defense", "rare_earth", "infosec", "crypto", "biotech"):
        assert P[below] > P[KEY]
