"""The data_infra THEME (🗄️ Data infra) — 2026-09-28.

Ajay's ask, verbatim:

  "Can you create a new sector for DATA driven companies like DATA DOG, Mongo
   DB and Snow flake in to the add them accross board where we have sectors"

THE CUT RULE these tests defend (sepa/universe.py, the block above the roster):
  1. ANCHORS    his three: DDOG, MDB, SNOW.
  2. THESIS     JUDGMENT, mine: "is the PRODUCT ITSELF the layer where a
                customer's data is stored, queried, searched or observed?"
  3. SEGMENT    a conglomerate where the data layer is one segment is OUT —
                cloud_infra's own rule (ORCL, IBM, MSFT).
  4. PARTITION  a ticker lives in ONE roster: MDB and TDC MOVED out of
                cloud_infra; nothing else moved.
  5. LIVENESS   last bar == the freshest session 2026-09-28, validated BY DATE,
                never by bar count (the SDIG trap).
  6. LIQUIDITY  50-bar average dollar volume >= 20_000_000, reused BY NAME.

NOT A SNAPSHOT. There is no universe snapshot on main: on the host
fetch_russell3000() falls back to ~1,020 names (lxml absent). Every assertion
below holds under that fallback too; the one that cannot (index reachability)
skips outside U._EXPECTED_COUNTS["russell3000"].

NO EDGE IS CLAIMED. Sector/industry heat measured NULL for demand outcomes on
2026-09-09 (-0.57pp, CI spans zero). The row is context; it gates nothing.
"""
import inspect
import re
from pathlib import Path

import pytest

from rotation import tracker as TR
from sepa import symbols as S
from sepa import universe as U
from supply_demand import zone_store as ZS
from trading import safety_floor as SF

KEY = "data_infra"
ROSTER = U.THEME_UNIVERSE.get(KEY, [])
FULL = {s.upper() for s in U.load_universe("full")}

# The validated eight, measured in the api container 2026-09-28 (last bar
# 2026-09-28, avg50 >= $20M, not DELISTED, company business checked). Pins
# equality between the repo and that probe.
VALIDATED = ["SNOW", "DDOG", "MDB", "DT", "ESTC", "TDC", "AMPL", "PLTR"]

# THEME_PRIORITY before this change, in rank order (18 keys).
PRE_CHANGE_ORDER = ["space", "quantum", "ai_semis", "semi_materials",
                    "ai_power", "nuclear", "energy", "optical", "robotics",
                    "ai_infra", "datacenter_build", "cloud_infra", "defense",
                    "rare_earth", "critical_minerals", "infosec", "crypto",
                    "biotech"]


# --------------------------------------------------------------------------
# The roster itself
# --------------------------------------------------------------------------
def test_the_theme_exists_with_his_three_anchors():
    assert KEY in U.THEME_UNIVERSE
    assert {"DDOG", "MDB", "SNOW"} <= set(ROSTER), "he named all three"
    assert len(ROSTER) == 8
    assert len(set(ROSTER)) == len(ROSTER), "a duplicate inside one roster"
    for anchor in ("DDOG", "MDB", "SNOW"):
        assert U.theme_for(anchor) == KEY


def test_the_roster_is_exactly_the_validated_eight():
    assert set(ROSTER) == set(VALIDATED)
    # His three lead the literal.
    assert ROSTER[:3] == ["SNOW", "DDOG", "MDB"]


def test_MDB_and_TDC_moved_out_of_cloud_infra():
    cloud = set(U.THEME_UNIVERSE["cloud_infra"])
    for moved in ("MDB", "TDC"):
        assert moved not in cloud, "%s is back in cloud_infra" % moved
        assert moved in ROSTER
        assert U.theme_for(moved) == KEY


# --------------------------------------------------------------------------
# NEGATIVES
# --------------------------------------------------------------------------
def test_NEGATIVE_the_rosters_stay_disjoint(monkeypatch):
    """THEME_BY_TICKER is last-wins, so a ticker in two rosters is silently
    retagged. _assert_themes_disjoint() must raise — prove it still does by
    putting MDB back in cloud_infra."""
    seen: dict[str, str] = {}
    for theme, names in U.THEME_UNIVERSE.items():
        for t in names:
            assert t not in seen, "%s in both %s and %s" % (t, seen[t], theme)
            seen[t] = theme
    U._assert_themes_disjoint()

    orig = U.THEME_UNIVERSE
    monkeypatch.setattr(U, "THEME_UNIVERSE",
                        {**orig, "cloud_infra": orig["cloud_infra"] + ["MDB"]})
    with pytest.raises(ValueError, match="MDB in both"):
        U._assert_themes_disjoint()


def test_NEGATIVE_a_delisted_name_can_never_enter():
    """CFLT (Confluent, last bar 2026-03-16) is in sepa.symbols.DELISTED. A
    dead ticker keeps its history, so nothing in the data stops it returning
    — this test does."""
    assert S.is_delisted("CFLT")
    assert "CFLT" not in ROSTER
    assert U.theme_for("CFLT") is None


def test_NEGATIVE_stale_names_stay_out_validated_by_DATE():
    """LIVENESS. The last bar date is the only test; bar count would pass a
    dead ticker (the SDIG trap)."""
    stale = {
        "DOMO": "last bar 2026-09-23 (not the freshest session)",
        "BASE": "last bar 2025-09-23 (Couchbase, taken private)",
        "FROG": "last bar 2026-08-31",
        "KVYO": "last bar 2026-08-31",
        "CWAN": "last bar 2026-06-24",
        "INFA": "no cached bars",
        "SWI": "no cached bars",
        "PSTG": "no cached bars",
    }
    for sym, why in stale.items():
        assert sym not in ROSTER, "%s — %s" % (sym, why)


def test_NEGATIVE_under_the_floor_stays_out():
    """LIQUIDITY. DOMO trades $7.2M/day (avg50). The floor is the reused
    constant, never a new number. PD is NOT listed here: PD passes the 20-day
    median ($21.7M) — the thesis excludes it, see the partition/app test."""
    assert "DOMO" not in ROSTER
    floor = inspect.signature(TR.build).parameters["min_dollar_vol"].default
    assert floor == SF.MIN_DOLLAR_VOL == 20_000_000.0


def test_NEGATIVE_conglomerates_where_data_is_a_segment_stay_out():
    """SEGMENT — cloud_infra's own rule as applied to the conglomerates MSFT
    and ORCL (universe.py, the SEGMENT line in the cloud_infra block); PLTR is
    in data_infra on the thesis test, not under this rule. ORCL, IBM and MSFT are out of data_infra AND not
    smuggled into any other roster. ORCL is HIS CALL #1 (with it the row is 9)."""
    for sym in ("ORCL", "IBM", "MSFT"):
        assert sym not in ROSTER, "%s: the data layer is one segment" % sym
        assert U.theme_for(sym) is None, "%s was tagged elsewhere" % sym


def test_NEGATIVE_data_vendors_are_not_data_infrastructure():
    """They SELL their own data; the customer's data does not live in them.
    HIS CALL, default out."""
    for sym in ("SPGI", "ICE", "MSCI", "FDS", "VRSK"):
        assert sym not in ROSTER
        assert U.theme_for(sym) is None, "%s was tagged elsewhere" % sym


def test_NEGATIVE_the_partition_holds():
    """Nothing else moved. The capacity names stay in cloud_infra, the backup
    peer stays in infosec, and the applications stay untagged."""
    for sym in ("NTAP", "NTNX", "GTLB", "DBX", "BOX", "NET", "AKAM"):
        assert U.theme_for(sym) == "cloud_infra", "%s left cloud_infra" % sym
    assert U.theme_for("RBRK") == "infosec"
    assert "DDOG" not in U.THEME_UNIVERSE["infosec"]
    for sym in ("PD", "CVLT", "P", "IOT", "AI", "AVPT", "FSLY", "OTEX", "INOD",
                "NTCT", "BRZE", "RAMP", "ZETA", "QMCO"):
        assert sym not in ROSTER, "%s fails the data-layer thesis" % sym


# --------------------------------------------------------------------------
# Reaching the scan
# --------------------------------------------------------------------------
@pytest.mark.parametrize("ticker", sorted(ROSTER))
def test_every_roster_name_survives_the_fate_filter_into_full(ticker):
    """`full` unions the rosters (universe.py load_universe "full") and then
    _with_benchmarks -> _resolve_fates drops DELISTED names and resolves
    RENAMES. A dead or renamed roster entry is therefore NOT in `full`, and
    this goes red. It is the NTSK/SQ guard, not a tautology."""
    assert ticker in FULL, "%s is in the roster but not in full" % ticker


def test_nothing_is_net_new_to_full():
    r3000 = {s.upper() for s in U.fetch_russell3000()}
    lo, hi = U._EXPECTED_COUNTS["russell3000"]
    if not lo <= len(r3000) <= hi:
        pytest.skip("russell3000 returned the %d-name fallback (sane range %d-%d) — "
                    "not the index, so reachability is unmeasurable here; measured "
                    "in the api container 2026-09-28: 0 net-new" % (len(r3000), lo, hi))
    reachable = ({s.upper() for s in U.fetch_sp1500()} | r3000
                 | {s.upper() for s in U.UNIVERSE})
    assert {t for t in ROSTER if t not in reachable} == set()


# --------------------------------------------------------------------------
# Headroom, priority, the band, the gates
# --------------------------------------------------------------------------
def test_cloud_infra_keeps_its_headroom_and_data_infra_sits_on_the_line():
    """ZERO HEADROOM on data_infra: one member more than MAX_STALE_DAYS (10)
    calendar days without a bar drops out of `n` and the row prints `· thin`.
    PLTR and/or ORCL are HIS CALL (without PLTR: 7, thin; with ORCL: 9)."""
    assert TR.MIN_COHORT_N == 8
    assert TR.MAX_STALE_DAYS == 10
    cloud = U.THEME_UNIVERSE["cloud_infra"]
    assert len(cloud) == 16
    assert len(cloud) - TR.MIN_COHORT_N == 8
    assert len(ROSTER) - TR.MIN_COHORT_N == 0


def test_priority_insertion_and_nothing_else_moved():
    """THE RANK IS MINE, NOT HIS: directly behind cloud_infra, everything
    below shifted one rank, relative order unchanged."""
    P = U.THEME_PRIORITY
    assert P[KEY] == P["cloud_infra"] + 1
    assert set(P) == set(U.THEME_UNIVERSE)
    assert sorted(P.values()) == list(range(len(P)))
    assert [k for k in sorted(P, key=P.get) if k != KEY] == PRE_CHANGE_ORDER


def test_NEGATIVE_no_gate_moved():
    """A DATA change touches no gate, no threshold and no default."""
    assert ZS.MIN_CAP_USD == 700_000_000.0
    assert ZS.MIN_BARS == 120
    assert TR.MIN_COHORT_N == 8
    sig = inspect.signature(TR.build).parameters
    assert sig["min_dollar_vol"].default == 20_000_000.0
    assert sig["min_price"].default == 10.0
    assert SF.MIN_SHARE_PRICE == 2.00
    assert SF.MIN_CAP_USD == 700_000_000.0
    assert SF.MIN_DOLLAR_VOL == 20_000_000.0


def test_the_themes_band_was_not_widened():
    lo, hi = U._EXPECTED_COUNTS["themes"]
    assert (lo, hi) == (20, 300), "the size band was moved to make this fit"
    n = len(U.fetch_themes())
    assert lo <= n <= hi
    assert n == len({t for r in U.THEME_UNIVERSE.values() for t in r})


# --------------------------------------------------------------------------
# Source guard
# --------------------------------------------------------------------------
def test_the_cut_rule_rides_with_the_roster():
    """SOURCE GUARD. The derivation must sit beside the roster, JUDGMENT must
    stay labelled, excluded tickers stay UNQUOTED, and the word the app never
    uses on his surfaces never appears."""
    src = Path(U.__file__).read_text()
    start = src.index("# Data infrastructure — the DATA LAYER")
    end = src.index('"data_infra": [', start)
    block = src[start:end]
    for token in ("JUDGMENT", "DATA LAYER", "SEGMENT", "ORCL", "20_000_000",
                  "BY DATE", "CFLT", "NO EDGE IS CLAIMED", "2026-09-28"):
        assert token in block, "the cut rule lost %r" % token
    assert not re.search(r"bounce", block, re.I)
    assert '"CFLT"' not in block
    assert '"ORCL"' not in block


def test_NEGATIVE_the_segment_step_does_not_cite_pltr_as_a_segment_case():
    """Critic 2026-09-28: step 3 used to cite 'the MSFT/ORCL/PLTR line' as its
    rule while PLTR sits IN this roster — self-contradiction. The SEGMENT step
    must name the conglomerates only and say PLTR is not under it."""
    src = Path(U.__file__).read_text()
    start = src.index("# Data infrastructure — the DATA LAYER")
    step3 = src[src.index("3. SEGMENT", start):src.index("4. PARTITION", start)]
    assert "MSFT/ORCL/PLTR" not in step3
    assert "PLTR is NOT" in step3
    assert "PLTR" in ROSTER
    assert "ORCL" not in ROSTER and "MSFT" not in ROSTER
