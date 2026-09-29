"""Dead-ticker triage 2026-09-29 — Ajay: "Remove the dead ones please".

The latest SEPA scan skipped 48 universe names as stale (no bar in ~10
sessions) or 'no price data'. Each was checked against Massive live on
2026-09-29 (docs/sepa/symbol_fates_audit.md, section 2026-09-29):

  * 40 DEAD  -> sepa.symbols.DELISTED (no successor series to splice)
  * 7 RENAME -> sepa.symbols.RENAMES (same CIK, ticker_change event,
                boundary bars consecutive and inside the splice guard)
  * VSCO -> VSXY is a real rename but its boundary open is +44.6%, which
    fails SPLICE_MAX_JUMP_RATIO -> HIS CALL, deliberately NOT mapped.
  * 0 ALIVE.

All synthetic, no network, no Mongo.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pd = pytest.importorskip("pandas")

from sepa import prices as P  # noqa: E402
from sepa import symbols as S  # noqa: E402
from sepa import universe as U  # noqa: E402

NEW_DEAD = (
    "ADRO", "AKE", "AMWD", "APGE", "AVNS", "CCRN", "CEP", "CPRX", "CRNX",
    "CVGW", "CWAN", "ESPR", "FFIC", "GTLS", "GTXI", "INH", "KALV", "KW",
    "LBRDA", "LBRDK", "LEG", "LPRO", "NFBK", "NUVL", "OLPX", "P5N994", "PRA",
    "RMAX", "SEM", "SILA", "SKYT", "SMLR", "SNBR", "STEL", "TALK", "THR",
    "TMHC", "TWO", "WBS", "WSR",
)

# old: (new, effective, (old_last_bar, old_last_close), (new_first_bar, new_first_open))
NEW_RENAMES = {
    "BBBY": ("NXH", "2026-08-17", ("2026-08-14", 4.35), ("2026-08-17", 4.55)),
    "BITF": ("KEEL", "2026-04-06", ("2026-04-02", 1.98), ("2026-04-06", 2.07)),
    "EQR": ("VMRK", "2026-08-18", ("2026-08-17", 63.66), ("2026-08-18", 64.16)),
    "FDP": ("DMC", "2026-06-29", ("2026-06-26", 29.22), ("2026-06-29", 29.00)),
    "HLX": ("HOS", "2026-09-02", ("2026-09-01", 10.60), ("2026-09-02", 10.83)),
    "LC": ("HAPN", "2026-06-22", ("2026-06-18", 19.21), ("2026-06-22", 19.40)),
    "SCVL": ("SHOE", "2026-06-12", ("2026-06-11", 17.43), ("2026-06-12", 17.43)),
}

# The entries that existed before this triage. They must not move.
PRIOR_DELISTED = ("SMAR", "CFLT", "CWEN-A", "MASI", "BLD", "JHG", "NSA",
                  "EA", "AVB", "GFRR")
PRIOR_RENAMES = {"SATS": ("ECHO", "2026-06-24"), "SQ": ("XYZ", "2025-01-21"),
                 "DOOO": ("DOO", "2025-12-08"), "IAC": ("PPLI", "2026-06-04"),
                 "ZI": ("GTM", "2025-05-13")}

# Live names this triage must never touch: the rename successors, the
# acquirers that keep their own series, the HIS-CALL rename and its target,
# and the TWO notes that share TWO's CIK.
MUST_STAY_LIVE = ("NXH", "KEEL", "VMRK", "DMC", "HOS", "HAPN", "SHOE",
                  "VSCO", "VSXY", "MBC", "AVO", "OCFC", "CHTR", "IONQ",
                  "INBX", "XXI", "TWOD", "BKR", "GSK", "ABBV", "VRTX",
                  "NVDA", "FISV", "P", "Q")


# ---------------------------------------------------------------------------
# The tables
# ---------------------------------------------------------------------------
def test_the_triage_counts_are_exact():
    assert len(NEW_DEAD) == 40 and len(set(NEW_DEAD)) == 40
    assert len(NEW_RENAMES) == 7
    assert set(S.DELISTED) >= set(PRIOR_DELISTED) | set(NEW_DEAD)
    assert set(S.RENAMES) >= set(PRIOR_RENAMES) | set(NEW_RENAMES)


@pytest.mark.parametrize("sym", NEW_DEAD)
def test_every_new_dead_name_is_flagged(sym):
    assert S.is_delisted(sym)
    assert S.is_delisted(f" {sym.lower()} ")
    assert S.resolve(sym) == sym, "a delisting has no successor"


@pytest.mark.parametrize("sym", NEW_DEAD)
def test_every_new_dead_entry_carries_dated_evidence(sym):
    why = S.DELISTED[sym]
    assert len(why) > 60, sym
    assert re.search(r"\b(19|20)\d\d-\d\d-\d\d\b", why), \
        "%s: evidence must carry a dated check" % sym


@pytest.mark.parametrize("old", sorted(NEW_RENAMES))
def test_every_new_rename_resolves_with_its_effective_date(old):
    new, eff, _last, _first = NEW_RENAMES[old]
    assert S.resolve(old) == new
    assert S.rename_of(old)["effective"] == eff
    assert S.former_names(new) == [old]
    assert not S.is_delisted(old) and not S.is_delisted(new)


@pytest.mark.parametrize("old", sorted(NEW_RENAMES))
def test_the_effective_date_is_the_first_new_print(old):
    """`effective` must be the first session under the new symbol, never a
    reference list_date (the ZI lesson)."""
    new, eff, _last, (first_day, _open) = NEW_RENAMES[old]
    assert eff == first_day
    assert eff in S.RENAMES[old][2], "evidence must quote the boundary date"


# ---------------------------------------------------------------------------
# Splices
# ---------------------------------------------------------------------------
def _bar(day, px):
    return pd.DataFrame({"open": [px], "high": [px], "low": [px],
                         "close": [px], "volume": [1_000]},
                        index=pd.DatetimeIndex([pd.Timestamp(day)]))


@pytest.mark.parametrize("old", sorted(NEW_RENAMES))
def test_every_new_rename_boundary_splices(old):
    new, _eff, (last_day, last_close), (first_day, first_open) = NEW_RENAMES[old]
    out = P.splice_history(_bar(last_day, last_close),
                           _bar(first_day, first_open), f"{old}->{new}")
    assert len(out) == 2, "%s->%s boundary must pass the splice guard" % (old, new)
    assert list(out.index) == [pd.Timestamp(last_day), pd.Timestamp(first_day)]


def test_NEGATIVE_the_vsco_boundary_fails_the_splice_guard_so_it_is_not_mapped():
    """VSCO 2026-06-01 close 54.30 -> VSXY 2026-06-02 open 78.53 (+44.6%).
    Same FIGI and CIK, but the jump is over SPLICE_MAX_JUMP_RATIO: HIS CALL."""
    assert 78.53 / 54.30 > P.SPLICE_MAX_JUMP_RATIO
    out = P.splice_history(_bar("2026-06-01", 54.30), _bar("2026-06-02", 78.53),
                           "VSCO->VSXY")
    assert len(out) == 1
    assert "VSCO" not in S.RENAMES
    assert not S.is_delisted("VSCO")
    assert S.resolve("VSCO") == "VSCO"
    assert S.former_names("VSXY") == []


# ---------------------------------------------------------------------------
# Negatives: nothing live moved, nothing prior moved
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("sym", MUST_STAY_LIVE)
def test_NEGATIVE_live_names_are_untouched(sym):
    assert not S.is_delisted(sym), sym
    assert sym not in S.RENAMES, sym


def test_NEGATIVE_no_debt_or_acquirer_is_a_rename_target():
    targets = {new for new, _e, _w in S.RENAMES.values()}
    for sym in ("TWOD", "XXI", "MBC", "AVO", "OCFC", "CHTR", "IONQ", "INBX",
                "SNBRQ", "KDNY"):
        assert sym not in targets, sym


def test_NEGATIVE_prior_entries_are_unchanged():
    for sym in PRIOR_DELISTED:
        assert S.is_delisted(sym), sym
    for old, (new, eff) in PRIOR_RENAMES.items():
        assert S.RENAMES[old][:2] == (new, eff), old
    assert "AVB" not in S.RENAMES, "AVB's acquirer VMRK is not a successor"


def test_NEGATIVE_no_new_name_is_both_dead_and_renamed():
    assert not set(NEW_DEAD) & set(NEW_RENAMES)
    assert not {v[0] for v in NEW_RENAMES.values()} & set(S.DELISTED)


# ---------------------------------------------------------------------------
# load_universe: every mode drops them
# ---------------------------------------------------------------------------
LIVE = ["NVDA", "AAPL", "VSCO", "VSXY", "NXH"]
POLLUTED = LIVE + list(NEW_DEAD) + list(NEW_RENAMES)


@pytest.fixture
def polluted(monkeypatch):
    """Every component carries all 40 dead names and all 7 old spellings."""
    comps = {k: (lambda: list(POLLUTED)) for k in U._COMPONENT_FETCHERS}
    monkeypatch.setattr(U, "_COMPONENT_FETCHERS", comps)
    monkeypatch.setattr(U, "_KNOWN_COMPONENTS", frozenset(comps))
    monkeypatch.setattr(U, "UNIVERSE", list(POLLUTED))
    monkeypatch.setattr(U, "fetch_sp500", lambda *a, **k: list(POLLUTED))
    monkeypatch.setattr(U, "fetch_massive_universe", lambda *a, **k: list(POLLUTED))
    for key in ("SEPA_UNIVERSE_FILE", "SEPA_UNIVERSE", "SEPA_UNIVERSE_MODE"):
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


EXPECTED = ["NVDA", "AAPL", "VSCO", "VSXY", "NXH",
            "KEEL", "VMRK", "DMC", "HOS", "HAPN", "SHOE"]


def _modes():
    return (["curated", "expanded", "all_us", "broad", "max",
             "russell3000_etf", "sp500,russell3000", "no_such_mode"]
            + sorted(U._UNIVERSE_ALIASES) + sorted(U._COMPONENT_FETCHERS))


@pytest.mark.parametrize("mode", _modes())
def test_every_mode_drops_the_dead_and_resolves_the_renames(polluted, mode):
    out = U.load_universe(mode)
    body = [s for s in out if s not in U.RS_ANCHORS]
    assert body == EXPECTED, mode
    for dead in NEW_DEAD:
        assert dead not in out
    for old in NEW_RENAMES:
        assert old not in out


def test_the_env_literal_cannot_resurrect_a_new_dead_name(polluted):
    polluted.setenv("SEPA_UNIVERSE", ",".join(POLLUTED))
    body = [s for s in U.load_universe() if s not in U.RS_ANCHORS]
    assert body == EXPECTED


def test_the_env_file_cannot_resurrect_a_new_dead_name(polluted, tmp_path):
    f = tmp_path / "u.txt"
    f.write_text("\n".join(POLLUTED))
    polluted.setenv("SEPA_UNIVERSE_FILE", str(f))
    body = [s for s in U.load_universe() if s not in U.RS_ANCHORS]
    assert body == EXPECTED


def test_the_count_drops_by_exactly_the_number_removed():
    """40 dead gone; 7 renames collapse only where the successor is already
    present (NXH here), so 40 + 1 slots go."""
    out = U._resolve_fates(POLLUTED)
    assert len(POLLUTED) - len(out) == 40 + 1


def test_NEGATIVE_ordinary_names_keep_their_order():
    syms = ["NVDA", "VSCO", "MBC", "AVO", "OCFC", "CHTR", "IONQ", "TWOD"]
    assert U._resolve_fates(syms) == syms


# ---------------------------------------------------------------------------
# Rosters that held a dead / renamed name (final repair, 2026-09-29)
# ---------------------------------------------------------------------------
def _crypto_sector():
    from supply_demand.sectors import SECTORS
    return next(s for s in SECTORS if s["id"] == "crypto_equities")


def test_rosters_carry_the_successor_KEEL_not_BITF():
    from sepa import universe as U
    assert "KEEL" in _crypto_sector()["sp_tickers"]
    assert "KEEL" in U.THEME_UNIVERSE["crypto"]
    assert U.THEME_BY_TICKER.get("KEEL") == "crypto"
    assert "KEEL" in U.UNIVERSE


@pytest.mark.parametrize("sym", ("BITF", "SMLR", "CEP"))
def test_NEGATIVE_no_roster_still_holds_a_dead_or_renamed_crypto_name(sym):
    from sepa import universe as U
    assert sym not in _crypto_sector()["sp_tickers"]
    assert sym not in U.THEME_UNIVERSE["crypto"]
    assert sym not in U.UNIVERSE
    assert sym not in U.THEME_BY_TICKER


def test_NEGATIVE_no_theme_or_sector_roster_holds_any_fate_table_key():
    from sepa import universe as U
    from supply_demand.sectors import SECTORS
    dead = set(NEW_DEAD) | set(NEW_RENAMES)
    theme_hits = [(th, t) for th, names in U.THEME_UNIVERSE.items()
                  for t in names if t.upper() in dead]
    sector_hits = [(s["id"], t) for s in SECTORS
                   for t in s.get("sp_tickers", []) if t.upper() in dead]
    assert theme_hits == [] and sector_hits == [], (theme_hits, sector_hits)


def _tag(sym):
    from supply_demand.equity_premium import _classify_tag
    return _classify_tag(equity_share_pct=40.0, ps=1.0, pb=1.0,
                         shares_growth=0.0, ticker=sym)[0]


def test_treasury_tag_follows_the_rename():
    assert _tag("KEEL") == "TREASURY"
    assert _tag("keel") == "TREASURY"


@pytest.mark.parametrize("sym", ("BITF", "SMLR"))
def test_NEGATIVE_dead_or_renamed_names_lose_the_treasury_tag(sym):
    assert _tag(sym) == "NORMAL"


def test_tier3_peer_list_uses_HAPN_not_LC():
    import cheetah_data as CD
    src = Path(CD.__file__).read_text()
    assert '"tier3": ["LMND", "HAPN"]' in src
    assert '"LC"' not in src
