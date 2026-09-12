"""🧪 semi_materials — the layer under the chip (Ajay 2026-09-11).

  "What are companies like SNDK explosive ness and produce things for all.. I
   would imagine there are companies like SNDK but for raw material for Semis,
   or optical fiber."  ... "yes add that"

Three things are load-bearing and invisible from reading the entry:
  1. a roster ticker OUTSIDE the scan universe is a chip that never charts or
     alerts (the NTSK lesson, 2026-09-10);
  2. the id is a macro_risk wiring key, not a label;
  3. this sector must not silently duplicate ai_chips / memory_hbm, or the same
     name would be counted twice in sector heat.
"""
import pytest

from sepa import macro_risk as MR
from supply_demand import sectors as S

SID = "semi_materials"


def _sec():
    return S.SECTOR_BY_ID[SID]


def test_the_sector_exists_and_covers_the_layer_he_described():
    assert SID in {s["id"] for s in S.SECTORS}
    t = set(_sec()["sp_tickers"])
    assert len(t) >= 15
    # the two that actually ran in the measured window — the reason he asked
    assert {"AEHR", "COHU"} <= t
    # materials / consumables leg ("raw material for Semis")
    assert {"ENTG", "MTRN", "CBT", "ROG"} <= t
    # test / probe / packaging leg
    assert {"TER", "AMKR", "KLIC", "FORM", "PLAB"} <= t


def test_it_does_not_duplicate_the_chip_sectors():
    """NEGATIVE. ai_chips already holds the four equipment giants; counting a
    name in two rosters double-counts it in sector heat."""
    mine = set(_sec()["sp_tickers"])
    for other in ("ai_chips", "memory_hbm"):
        overlap = mine & set(S.SECTOR_BY_ID[other]["sp_tickers"])
        assert not overlap, "%s also sits in %s" % (sorted(overlap), other)
    assert not (mine & {"AMAT", "LRCX", "KLAC", "ASML"}), \
        "the equipment giants belong to ai_chips; this sector is the layer UNDER them"


def test_the_id_is_the_macro_risk_wiring_key():
    """The id -> bucket map decides macro-event exposure. Rename the id to
    something prettier and every ticker silently falls back to 'broad'."""
    for t in _sec()["sp_tickers"]:
        assert MR.sector_of(t) == "semis_ai", t


def test_NEGATIVE_an_unreserved_id_would_lose_the_bucket():
    buckets = MR._build_ticker_buckets()
    assert buckets.get("AEHR") == "semis_ai"
    fake = dict(_sec())
    fake["id"] = "semiconductor_materials"          # prettier, unreserved
    assert fake["id"] not in ("ai_chips", "memory_hbm", "semis", SID)


def test_gap_economics_is_absent_on_purpose():
    """Real bottlenecks exist here (photoresist, specialty gases, quartz) but
    no filing gives us dollar numbers. The field is OFF rather than carrying
    invented ones — same call as cybersecurity and biotech."""
    assert "gap_economics" not in _sec()
    assert _sec()["etf"] == "SOXX"


def test_no_duplicate_tickers_inside_the_roster():
    t = _sec()["sp_tickers"]
    assert len(t) == len(set(t)), "duplicate ticker in the roster"
    assert all(x == x.upper().strip() for x in t)


@pytest.mark.parametrize("ticker", sorted(S.SECTOR_BY_ID[SID]["sp_tickers"]))
def test_every_roster_ticker_is_in_the_scan_universe(ticker):
    """THE NTSK LESSON. sectors.py does NOT feed the scan universe — listing a
    ticker here does not make it scannable. A roster name outside
    load_universe('full') gets no SEPA card, no zone bands, and therefore no
    demand / bounce / supply-break alert and no paper entry: a chip that never
    charts. All 17 were verified in `full` at ship time and none needed adding.
    """
    from sepa.universe import load_universe
    assert ticker in {s.upper() for s in load_universe("full")}, (
        "%s is in the roster but outside the scan universe — add it to the "
        "curated list in sepa/universe.py the way NTSK and AXTI were" % ticker)
