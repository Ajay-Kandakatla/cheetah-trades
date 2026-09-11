"""The two sectors Ajay asked for on 2026-09-10, and the wiring that is easy
to get silently wrong.

  "another sector security like AI securty and internet security like CROWD
   Strike, NTSK and Robotic software security like BB is an examaple"
  "also bio tech and personal medicine and diruptive research companies
   related to medicine"

Three things here are load-bearing and invisible if you only read the entries:
the sector IDs are reserved strings that wire macro-event risk, sp_tickers does
NOT feed the scan universe, and gap_economics is omitted on purpose.
"""
import pytest

from supply_demand import sectors as S
from sepa import macro_risk as MR
from sepa import symbols as SYM

NEW_IDS = ("cybersecurity", "biotech")


def _sector(sid):
    return S.SECTOR_BY_ID[sid]


def test_both_sectors_exist_with_his_three_anchors():
    ids = {s["id"] for s in S.SECTORS}
    assert NEW_IDS[0] in ids and NEW_IDS[1] in ids

    sec = _sector("cybersecurity")["sp_tickers"]
    # the three he named by name: AI security, internet security, embedded
    for anchor in ("CRWD", "NTSK", "BB"):
        assert anchor in sec, "%s was his own example for this sector" % anchor

    bio = _sector("biotech")["sp_tickers"]
    assert len(bio) >= 10
    # his three legs: gene editing / RNA, precision oncology, the read layer
    assert {"CRSP", "NTLA"} <= set(bio)          # disruptive research
    assert {"RVMD", "BBIO"} <= set(bio)          # targeted / precision therapy
    assert {"ILMN", "TEM", "GH", "NTRA"} <= set(bio)   # sequencing + diagnostics


# ── the IDs are wiring keys, not labels ───────────────────────────────────
# macro_risk.py's id -> bucket map already reserved these two exact strings
# before either sector existed. Rename an id to something prettier and every
# ticker in it silently falls back to "broad" with no error anywhere.
def test_sector_ids_are_the_strings_macro_risk_reserves():
    for t in _sector("cybersecurity")["sp_tickers"]:
        assert MR.sector_of(t) == "software_growth", t
    for t in _sector("biotech")["sp_tickers"]:
        assert MR.sector_of(t) == "healthcare", t


def test_NEGATIVE_a_differently_named_id_would_lose_the_bucket():
    """Pins WHY the ids look generic: this is what renaming would cost."""
    buckets = MR._build_ticker_buckets()
    assert buckets.get("CRWD") == "software_growth"
    # the map is keyed on the sector id; an unreserved id resolves to "broad"
    fake = dict(_sector("cybersecurity"))
    fake["id"] = "security_software"
    orig = S.SECTORS
    try:
        S.SECTORS = [s for s in orig if s["id"] != "cybersecurity"] + [fake]
        assert MR._build_ticker_buckets().get("SAIL") == "broad"
    finally:
        S.SECTORS = orig


# ── sp_tickers is display-only; the scan universe is a different file ─────
def test_every_roster_ticker_is_actually_scannable():
    """A roster ticker outside the scan universe is a chip that never scans,
    never charts and never alerts. NTSK was exactly that until it was added to
    the curated list in sepa/universe.py — sectors.py shares no code path with
    the universe, so the two have to be kept honest by a test."""
    from sepa import universe as U
    full = set(U.load_universe("full") or [])
    if not full:                                  # no cache in this environment
        pytest.skip("universe unavailable")
    for sid in NEW_IDS:
        missing = [t for t in _sector(sid)["sp_tickers"] if t not in full]
        assert not missing, "%s roster outside the scan universe: %s" % (sid, missing)


def test_ntsk_is_in_the_curated_universe_list():
    """He holds it and watches it. Pinned separately from the membership test
    above so the reason survives even when the universe cache is unavailable:
    the curated list is a literal in the source, not a cached fetch."""
    from sepa import universe as U
    assert "NTSK" in set(U.UNIVERSE), \
        "NTSK must stay in the curated list — no index layer carries it"


# ── the omission is deliberate ────────────────────────────────────────────
def test_neither_sector_invents_a_supply_gap():
    """gap_economics renders a $ demand-vs-supply bar with a sources line.
    Neither of these is a physical bottleneck and no filing supports a split,
    so the field stays OFF rather than carrying numbers we made up. The thesis
    says so in words instead (same shape as ai_software)."""
    for sid in NEW_IDS:
        s = _sector(sid)
        assert not s.get("gap_economics"), "%s must not carry invented gap economics" % sid
        assert "not a supply gap" in s["thesis"].lower(), sid


def test_existing_sourced_sectors_still_carry_their_sources():
    """NEGATIVE of the above: omitting is only allowed where nothing was
    sourced. Any sector that DOES carry gap_economics still needs its sources."""
    for s in S.SECTORS:
        ge = s.get("gap_economics")
        if ge:
            assert ge.get("sources"), "%s: sector economics must be sourced, not invented" % s["id"]


# ── the two medical sectors must not become one ──────────────────────────
def test_biotech_does_not_overlap_healthcare_pharma():
    """healthcare_pharma is the big-pharma GLP-1 CAPACITY thesis; biotech is a
    PIPELINE thesis. A ticker in both would double-count him into one trade."""
    bio = set(_sector("biotech")["sp_tickers"])
    pharma = set(_sector("healthcare_pharma")["sp_tickers"])
    assert not (bio & pharma), "overlap: %s" % sorted(bio & pharma)


def test_biotech_thesis_warns_that_these_names_gap():
    """These resolve on dated binary events. A stop at a band floor does not
    fill through a failed readout, and the board must say so."""
    t = _sector("biotech")["thesis"].lower()
    assert "gap" in t and ("stop" in t or "watchlist" in t)


# ── the SMAR/SQ failure mode: a dead name sitting in a roster forever ────
def test_no_roster_ticker_anywhere_is_known_dead_or_renamed():
    """symbols.py grows DELISTED/RENAMES during the weekly liveness triage.
    This makes that triage fail the build here instead of leaving a stale chip
    on a board he trades (SMAR sat dead in the universe for 19 months)."""
    dead, renamed = [], []
    for s in S.SECTORS:
        for t in (s.get("sp_tickers") or []):
            if SYM.is_delisted(t):
                dead.append((s["id"], t))
            elif SYM.resolve(t) != t:
                renamed.append((s["id"], t, SYM.resolve(t)))
    assert not dead, "delisted tickers still in sector rosters: %s" % dead
    assert not renamed, "renamed tickers still in sector rosters: %s" % renamed


def test_NEGATIVE_the_dead_ticker_guard_actually_fires():
    """Mutation guard: the test above is worthless if is_delisted never hits."""
    known_dead = next(iter(SYM.DELISTED))
    assert SYM.is_delisted(known_dead)
    assert known_dead not in {t for s in S.SECTORS for t in (s.get("sp_tickers") or [])}


# ── breakout ordering is NOT silently changed ────────────────────────────
def test_security_is_not_in_the_ai_priority_list_without_his_say():
    """AI_SECTOR_PRIORITY decides which names LEAD his breakout boards
    (standing rule, 2026-06-25: chips -> energy/nuclear -> water/cooling ->
    grid -> AI software -> DC REITs -> optical). Security is not on that list.
    Adding it would re-rank every breakout board, so it waits for his call."""
    assert "cybersecurity" not in S.AI_SECTOR_PRIORITY
    assert "biotech" not in S.AI_SECTOR_PRIORITY
    # and a security-only name therefore carries no AI chip
    assert S.ai_sector_for_ticker("SAIL") is None
