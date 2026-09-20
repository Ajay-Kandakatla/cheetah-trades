"""The curated sector/industry corrections (Ajay 2026-09-19).

  "They are all wrongle categorizerd OKLO is nuclear power, IREN is mining.."

Sixteen names in his themes arrived as sector "Financial Services" / industry
"Capital Markets" — the peer group for brokers and exchanges — because their
EDGAR filer header carries SIC 6199 "Finance Services" (a crypto-assets filing
ROUTING code, not a business descriptor). Two peer-relative surfaces read that
label: the long-term fundamental score and the rotation grid's medians.

What these pin, in order of how much damage the failure does:

  1. The override moves a LABEL and NOTHING ELSE. No zone, verdict, gate,
     threshold or enterable read may move by a byte.
  2. The provider's own answer survives, so a wrong correction is visible and
     reversible rather than destructive.
  3. Every row carries a citable basis — Rule #1, no invented classification.
  4. The BATCH read path heals too. An override applied only to get() would
     fix the ticker page and leave every board on the wrong peer group.
"""
from __future__ import annotations

import pytest

from companies import sector_overrides as SO


# ── 1. the table itself ─────────────────────────────────────────────────────

def test_every_override_names_a_citable_basis():
    """Rule #1. A label with no stated grounding is a guess wearing a fact's
    clothes, and it would silently move a peer-relative score he reads."""
    assert len(SO.SECTOR_OVERRIDES) >= 10
    for tkr, row in SO.SECTOR_OVERRIDES.items():
        sector, industry, basis = row
        assert sector and isinstance(sector, str), tkr
        assert industry and isinstance(industry, str), tkr
        assert basis and len(basis) > 40, (
            f"{tkr}: basis is missing or too thin to audit: {basis!r}")
        # a basis must point at something checkable, not at taste
        low = basis.lower()
        assert any(w in low for w in
                   ("10-q", "10-k", "6-k", "sic", "gics", "revenue", "segment",
                    "mw", "peer")), f"{tkr}: basis cites nothing: {basis!r}"


def test_NEGATIVE_the_two_real_financials_are_NOT_overridden():
    """COIN runs an exchange and HOOD is a registered broker-dealer. They
    arrived in Financial Services correctly. Sweeping them up with the miners
    because they share a theme would be the same error pointed the other way."""
    for tkr in ("COIN", "HOOD", "GLXY"):
        assert SO.sector_for(tkr) is None, f"{tkr} must keep its provider label"
        assert tkr in SO.REVIEWED_NO_CHANGE, (
            f"{tkr} was left alone but no reason is recorded — a later pass "
            f"will 'discover' it and override it")


def test_NEGATIVE_the_operating_utilities_keep_their_IPP_label():
    """His complaint was OKLO, never VST. The fix is to move the pre-revenue
    developer OUT of the IPP peer group, not to dismantle the peer group."""
    for tkr in ("VST", "CEG", "TLN"):
        assert SO.sector_for(tkr) is None, f"{tkr} is an operating IPP"
    fix = SO.sector_for("OKLO")
    assert fix is not None
    assert fix[0] == "Industrials", fix
    # and it lands with the other reactor vendor, not somewhere new
    assert SO.sector_for("SMR") is None          # already correctly Industrials
    assert "SMR" in SO.REVIEWED_NO_CHANGE


def test_NEGATIVE_no_override_invents_a_sector_outside_the_provider_vocabulary():
    """A label the provider never emits would partition the rotation grid into
    a cohort of one and quietly break every median that reads it."""
    KNOWN = {"Technology", "Industrials", "Utilities", "Energy", "Healthcare",
             "Basic Materials", "Consumer Cyclical", "Consumer Defensive",
             "Communication Services", "Financial Services", "Real Estate"}
    for tkr, (sector, _industry, _b) in SO.SECTOR_OVERRIDES.items():
        assert sector in KNOWN, f"{tkr} invents sector {sector!r}"


def test_NEGATIVE_the_deliberately_undecided_names_are_absent():
    """Crypto TREASURY vehicles and pre-revenue REIT elections are judgement
    calls the owner makes, not facts a filing settles. Guessing one and
    shipping it is exactly what Rule #1 forbids."""
    for tkr in ("BTCS", "SBET", "DFDV", "FRMI"):
        assert SO.sector_for(tkr) is None, (
            f"{tkr} is an owner decision and must not be overridden silently")


def test_a_symbol_with_no_override_is_untouched():
    for tkr in ("AAPL", "NVDA", "MU", "", "   ", "zzzz"):
        assert SO.sector_for(tkr) is None


def test_lookup_is_case_and_space_insensitive():
    assert SO.sector_for("  wulf ") == SO.sector_for("WULF")


# ── 2. apply() ──────────────────────────────────────────────────────────────

def test_apply_corrects_the_label_and_KEEPS_the_provider_answer():
    doc = {"symbol": "WULF", "sector": "Financial Services",
           "industry": "Capital Markets", "name": "TeraWulf Inc."}
    out = SO.apply(doc)
    assert out["sector"] == "Technology"
    assert out["industry"] == "Information Technology Services"
    # NOTHING IS DESTROYED — a wrong correction has to stay visible
    assert out["sector_provider"] == "Financial Services"
    assert out["industry_provider"] == "Capital Markets"
    assert out["sector_override"] is True
    assert out["sector_override_basis"]
    # and it did not touch anything else on the doc
    assert out["name"] == "TeraWulf Inc."


def test_apply_is_IDEMPOTENT():
    """get() and get_many_cached() can both reach the same doc. A second pass
    that overwrote sector_provider with the ALREADY-CORRECTED value would
    erase the provider's answer and make the correction unfalsifiable."""
    doc = {"symbol": "OKLO", "sector": "Utilities",
           "industry": "Utilities - Independent Power Producers"}
    once = SO.apply(dict(doc))
    twice = SO.apply(SO.apply(dict(doc)))
    assert once == twice
    assert twice["sector_provider"] == "Utilities"
    assert twice["industry_provider"] == "Utilities - Independent Power Producers"


def test_NEGATIVE_apply_never_raises_on_junk():
    for junk in (None, {}, [], "WULF", 7, {"symbol": None},
                 {"symbol": "WULF"},              # no sector keys at all
                 {"sector": "Financial Services"}):   # no symbol
        SO.apply(junk)          # must not raise
    # a doc with a symbol but no provider sector still gets corrected, and
    # records that there was nothing to preserve
    out = SO.apply({"symbol": "WULF"})
    assert out["sector"] == "Technology"
    assert out["sector_provider"] is None


def test_NEGATIVE_an_untouched_doc_gains_no_override_keys():
    """A reader that branches on `sector_override` must not see it on the 2,600
    names nobody corrected."""
    out = SO.apply({"symbol": "AAPL", "sector": "Technology"})
    assert "sector_override" not in out
    assert "sector_provider" not in out


# ── 3. the store heals on BOTH read paths ───────────────────────────────────

def test_get_many_cached_heals_too(monkeypatch):
    """THE ONE THAT MATTERS FOR THE BOARDS. The rotation grid, the growth
    board and group-leadership all read sectors through the BATCH path. An
    override wired only into get() fixes the ticker page and leaves every
    board ranking WULF against banks."""
    from companies import store

    class _Coll:
        def find(self, q):
            return [{"_id": 1, "symbol": "WULF", "sector": "Financial Services",
                     "industry": "Capital Markets"},
                    {"_id": 2, "symbol": "AAPL", "sector": "Technology",
                     "industry": "Consumer Electronics"}]

    class _DB:
        companies = _Coll()

    monkeypatch.setattr(store, "_get_db", lambda: _DB())
    out = store.get_many_cached(["WULF", "AAPL"])
    assert out["WULF"]["sector"] == "Technology"
    assert out["WULF"]["sector_provider"] == "Financial Services"
    # the untouched name is byte-identical apart from the id coercion
    assert out["AAPL"]["sector"] == "Technology"
    assert "sector_override" not in out["AAPL"]


def test_get_heals_the_cached_path(monkeypatch):
    from companies import store

    class _Coll:
        def find_one(self, q):
            return {"_id": 1, "symbol": "IREN", "sector": "Financial Services",
                    "industry": "Capital Markets",
                    "refreshed_at": store._now()}

    class _DB:
        companies = _Coll()

    monkeypatch.setattr(store, "_get_db", lambda: _DB())
    out = store.get("IREN")
    assert out["sector"] == "Technology"
    assert out["sector_provider"] == "Financial Services"


def test_NEGATIVE_the_store_does_not_WRITE_the_override_back_to_mongo(monkeypatch):
    """The cache must keep the PROVIDER's answer. Baking a correction into
    Mongo makes it survive the table being edited or removed, and a later
    refresh would then compare a corrected label against a provider one and
    see no drift."""
    from companies import store
    written = {}

    class _Coll:
        def find_one(self, q):
            return None

        def update_one(self, q, update, upsert=False):
            written.update(update.get("$set") or {})

    class _DB:
        companies = _Coll()

    monkeypatch.setattr(store, "_get_db", lambda: _DB())
    monkeypatch.setattr(store, "_fetch_from_yfinance",
                        lambda s: {"sector": "Financial Services",
                                   "industry": "Capital Markets"})
    out = store.get("WULF")
    assert out["sector"] == "Technology"          # the CALLER sees the fix…
    assert written.get("sector") == "Financial Services", (
        "the override leaked into the Mongo write — the provider's answer is "
        "gone and the correction can never be audited or reverted")


# ── 4. THE INVARIANT: a label moved, and nothing else did ───────────────────

def test_NO_supply_demand_or_trading_file_reads_the_override():
    """Rule #10 — never edit an S&D rule alone, and this is not one. The
    override must not have reached a module that decides a zone, a stop, a
    gate or an entry. If a future change wires it in there, that is a rule
    change and needs its own sign-off, not this table's."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    offenders = []
    # supply_demand/ and trading/ ONLY. Rule #10 is about zones, gates, stops
    # and entries. sepa/longterm.py is a peer-relative FUNDAMENTAL SCORE whose
    # whole job is to pick a peer group, so it must read the corrected label —
    # it is the surface the wrong one damaged most.
    for sub in ("supply_demand", "trading"):
        d = root / sub
        if not d.exists():
            continue
        for f in d.rglob("*.py"):
            try:
                src = f.read_text()
            except Exception:
                continue
            if "sector_overrides" in src or "sector_override" in src:
                offenders.append(str(f.relative_to(root)))
    assert not offenders, (
        "the sector override reached a decision module: " + ", ".join(offenders))


def test_the_table_covers_what_he_actually_complained_about():
    """His two named examples, plus the cohort the audit found."""
    assert SO.sector_for("IREN") is not None, "he named IREN explicitly"
    assert SO.sector_for("OKLO") is not None, "he named OKLO explicitly"
    assert SO.sector_for("WULF") is not None, "the name that started it"
    # none of the corrected miners may still read Financial Services
    for tkr in ("WULF", "IREN", "MARA", "RIOT", "HUT", "CLSK", "HIVE",
                "ARBK", "BTBT", "SLNH"):
        sector, _industry, _b = SO.SECTOR_OVERRIDES[tkr]
        assert sector != "Financial Services", tkr


# ── 5. NO READER MAY BYPASS THE CORRECTION ──────────────────────────────────

def test_every_direct_mongo_companies_reader_heals_for_itself():
    """THE STRUCTURAL TRAP, and the one that already bit.

    `companies.store` is not the only way sectors are read. Three modules query
    Mongo's `companies` collection DIRECTLY — sepa/longterm.py (which builds
    the peer POOL for the fundamental score), growth/tracker.py and
    growth/api.py. Wiring the override into the store alone healed the ticker
    page and left the score that ranked WULF against 406 banks exactly as it
    was.

    Any NEW direct reader must heal too. This scans for the query and requires
    the override beside it, so the next one cannot be added silently.
    """
    import pathlib
    import re
    root = pathlib.Path(__file__).resolve().parents[1]
    pat = re.compile(r'\bdb(?:\[["\']companies["\']\]|\.companies)\.find\b')
    missing = []
    for f in sorted(root.rglob("*.py")):
        rel = str(f.relative_to(root))
        if rel.startswith("tests/") or rel == "companies/store.py":
            continue
        try:
            src = f.read_text()
        except Exception:
            continue
        # Strip comments first: sepa/universe.py records the exact Mongo
        # query it used to derive a theme roster, in a comment. A regex that
        # counts documentation as a live read fails for the wrong reason.
        live = "\n".join(ln for ln in src.splitlines()
                          if not ln.lstrip().startswith("#"))
        if not pat.search(live):
            continue
        # a reader that does not look at the sector at all is fine
        if '"sector"' not in live and "'sector'" not in live:
            continue
        if "sector_overrides" not in live:
            missing.append(rel)
    assert not missing, (
        "these read Mongo `companies` for a SECTOR without applying the "
        "override, so they serve the provider's wrong label: "
        + ", ".join(missing))


def test_the_store_is_still_the_documented_front_door():
    """The direct readers are an exception, not the pattern. If companies.store
    ever stops healing, everything that DOES go through it silently regresses."""
    import inspect
    from companies import store
    src = inspect.getsource(store)
    assert src.count("sector_overrides.apply") >= 3, (
        "companies.store must heal get()'s fresh path, get()'s cached path and "
        "get_many_cached()")
